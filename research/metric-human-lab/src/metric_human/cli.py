"""Command line research runner.

  metric-human bench --out outputs/example
  metric-human reconstruct --input outputs/example/reproducible_input.json --out outputs/reloaded
  metric-human extract-mask --image person.jpg --out person_mask.png
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import numpy as np
import cv2
from .bench import run_benchmark
from .volume import Grid
from .cameras import Camera
from .reconstruct import View,fuse_views,mask_from_image
from .measurements import geometric_report
from .photos import prepare_photographs
from .depth import align_relative_depth
from .external import run_external_mesh_benchmark
from .depth_ablation import run_depth_ablation
from .makehuman import import_makehuman_prior, save_imported_prior
from .makehuman_assets import create_pinned_makehuman_prior
from .evidence import write_aligned_depth_receipt, verify_metric_depth_receipt
from .stability import silhouette_boundary_sensitivity, save_silhouette_sensitivity
from .landmarks import Observation, triangulate
from .motion import Gear,sample_rig,sample_shoulder_motion,evaluate_clip,optimize_offset_along_axis
from .prior import Prior,fit_prior_to_evidence
from .vision import generate_sam2_masks, generate_relative_depth
from .calibration import solve_perspective_pnp
from .multiview_calibration import recover_relative_cameras
from .feature_matches import match_masked_rgb_features
from .view_planner import orbit_candidates, plan_views, save_view_plan
from .mesh_measurements import measure_external_mesh, save_section_report
from .view_benchmark import run_view_planning_benchmark
from .view_centering import recenter_views_from_prior
from .robust_fit import fit_prior_coarse_to_fine
from .datasets import audit_dataset_manifest, write_audit
from .body_rig import approximate_rig_from_volume
from .visualize import write_demo_viewer,write_contact_sheet
import trimesh
from .quality import view_reprojection_diagnostics


def from_config(input_path,out_dir):
    path=Path(input_path)
    conf=json.loads(path.read_text())
    grid=Grid.from_dict(conf['grid'])
    views=[]
    depth_receipts=[]
    for entry in conf['views']:
        img=cv2.imread(str(path.parent/entry['mask']),cv2.IMREAD_GRAYSCALE)
        if img is None: raise ValueError('Mask not found: '+entry['mask'])
        depth=None
        if 'depth_m' in entry:
            depth_path=path.parent/entry['depth_m']
            # A relative-depth array MUST NOT be silently treated as metric.
            # Synthetic oracle data has distinct provenance from independently
            # anchored real model evidence.
            if entry.get('depth_evidence_source') == 'synthetic_known_reference_mesh':
                if conf.get('scale_source') != 'synthetic_world_coordinates':
                    raise ValueError('Synthetic oracle depth requires synthetic source provenance')
                depth_receipts.append({'depth_provenance':'synthetic_known_reference_mesh'})
            elif entry.get('depth_alignment_receipt'):
                receipt_path=path.parent/entry['depth_alignment_receipt']
                depth_receipts.append(verify_metric_depth_receipt(
                    depth_file=depth_path,receipt_file=receipt_path))
            else:
                raise ValueError('Metric depth_m requires an aligned-depth receipt or explicit synthetic known-mesh source')
            depth=np.load(depth_path,allow_pickle=False)
        views.append(View(Camera.from_dict(entry['camera']),img>127,
                          entry.get('label',''),float(entry.get('weight',1.0)),depth,
                          float(entry.get('depth_tolerance_m',.02)),
                          int(entry.get('segmentation_margin_px',0))))
    output=Path(out_dir);output.mkdir(parents=True,exist_ok=True)
    # Optional external 2D keypoint detectors provide identifiable, weighted
    # rays. Triangulation is independent of the volumetric visual hull. Joint
    # positions are NOT automatically promoted to an accurate rig.
    joints={}
    landmark_rows=conf.get('landmark_observations',[])
    if landmark_rows:
        cameras_by_view={v.label:v.camera for v in views}
        observations=[]
        for entry in landmark_rows:
            if entry['view'] not in cameras_by_view:
                raise ValueError('Landmark references unknown view: '+str(entry['view']))
            observations.append(Observation(
                label=entry['label'],camera=cameras_by_view[entry['view']],
                pixel_uv=tuple(entry['uv']),confidence=float(entry.get('confidence',1.0)),
                provenance=str(entry.get('provenance','external_landmark_detector'))))
        joints=triangulate(observations)
        # Neither silhouette support nor triangulation establishes anatomical joint accuracy.
        (output/'joints.json').write_text(json.dumps({
            'triangulated_landmarks':joints,
            'status':'geometry_from_camera_and_external_2d_landmarks_not_a_validated_rig',
            'source_records':landmark_rows},indent=2))
    recon=fuse_views(views,grid,min_fraction=conf.get('min_fraction',1.),
                     closing_iterations=conf.get('closing_iterations',0),
                     scale_source=conf.get('scale_source','unknown'))
    np.savez_compressed(output/'reconstruction.npz',occupancy=recon.occupancy,
                        support_fraction=recon.support_fraction)
    mesh=recon.mesh()
    mesh.export(output/'reconstruction.obj')
    mesh.export(output/'reconstruction.glb')
    report=geometric_report(recon.occupancy,grid,
                            cross_section_heights=conf.get('cross_section_heights',[]),
                            scale_source=conf.get('scale_source','unknown'))
    # Reprojection agreement is a self-consistency diagnostic, not physical accuracy.
    from .quality import view_reprojection_diagnostics
    quality=view_reprojection_diagnostics(mesh,views)
    (output/'report.json').write_text(json.dumps({"geometry":report,"provenance":recon.metadata,
                                                 "input_assumptions":{k:conf.get(k) for k in
                                                 ("calibration_status","height_prior_m","method","notes")},
                                                 "reprojection_diagnostics":quality,
                                                 "triangulated_landmarks":joints,
                                                 "depth_evidence_receipts":depth_receipts},indent=2))
    return report



def fit_prior_manifest(input_path,prior_path,out_dir,*,maxiter=75,use_landmarks=True,depth_weight=0.,alignment_radius_px=0,prealign_radius_px=0,silhouette_loss_mode='pixel_iou',holdout_labels=None):
    path=Path(input_path)
    conf=json.loads(path.read_text())
    views=[]
    for entry in conf['views']:
        img=cv2.imread(str(path.parent/entry['mask']),cv2.IMREAD_GRAYSCALE)
        if img is None:raise ValueError('Mask not found: '+str(entry['mask']))
        depth=None
        if entry.get('depth_m') is not None:
            depth_path=path.parent/entry['depth_m']
            if entry.get('depth_evidence_source')=='synthetic_known_reference_mesh':
                if conf.get('scale_source')!='synthetic_world_coordinates':
                    raise ValueError('Synthetic depth incompatible with this scale source')
            elif entry.get('depth_alignment_receipt'):
                verify_metric_depth_receipt(depth_file=depth_path,
                         receipt_file=path.parent/entry['depth_alignment_receipt'])
            else:
                raise ValueError('Metric depth prior fitting requires a validated file receipt')
            depth=np.load(depth_path,allow_pickle=False)
        views.append(View(Camera.from_dict(entry['camera']),img>127,
                          entry.get('label',''),float(entry.get('weight',1.0)),depth))
    holdout_labels=set(holdout_labels or [])
    labels=[v.label for v in views]
    if holdout_labels:
        if not all(labels) or len(labels)!=len(set(labels)) or not all(holdout_labels):
            raise ValueError('Holdout requires unique nonempty camera labels')
        if holdout_labels-set(labels):
            raise ValueError('Holdout camera label is missing from manifest')
        validation_views=[v for v in views if v.label in holdout_labels]
        views=[v for v in views if v.label not in holdout_labels]
        if not views:
            raise ValueError('Holdout cannot remove every training camera')
    else:
        validation_views=[]
    prior=Prior.load(prior_path)
    anchor_positions={}
    if use_landmarks and conf.get('landmark_observations'):
        byview={v.label:v.camera for v in views}
        observations=[]
        for row in conf['landmark_observations']:
            if row['view'] in holdout_labels:
                continue  # Never use held-out observations to triangulate training landmarks.
            if row['label'] in prior.landmark_vertex_ids:
                observations.append(Observation(row['label'],byview[row['view']],
                                                 tuple(row['uv']),float(row.get('confidence',1.))))
        triangulated=triangulate(observations)
        anchor_positions={name:row['xyz_world_units'] for name,row in triangulated.items()
                          if row['status']=='triangulated'}
    centering=None
    if prealign_radius_px:
        views,centering=recenter_views_from_prior(prior,views,max_shift_px=prealign_radius_px)
    if silhouette_loss_mode=='coarse_to_fine':
        if prealign_radius_px or alignment_radius_px:
            raise ValueError('coarse_to_fine owns its small centering adjustments')
        fitted,report=fit_prior_coarse_to_fine(prior,views,
                 landmark_positions_world=anchor_positions,depth_weight=depth_weight,
                 coarse_maxiter=maxiter,fine_maxiter=maxiter)
        if validation_views:
            # Validate the resulting mesh without leaking images into either optimization stage.
            from .quality import heldout_view_diagnostics
            projections=heldout_view_diagnostics(fitted,validation_views)
            report['held_out_validation']={
                'available':True,'num_views':len(validation_views),
                'weighted_silhouette_iou':float(np.average([row['silhouette_iou'] for row in projections],
                                    weights=[v.weight for v in validation_views])),
                'per_view_reprojection':projections,
                'status':'separate_view_reprojection_only_not_real_dimension_accuracy',
                'limitations':['Validation reprojection is not real 3D dimension ground truth.']}
    else:
        fitted,report=fit_prior_to_evidence(prior,views,
              landmark_positions_world=anchor_positions,maxiter=maxiter,depth_weight=depth_weight,
              alignment_radius_px=alignment_radius_px,
              silhouette_loss_mode=silhouette_loss_mode,validation_views=validation_views)
    out=Path(out_dir);out.mkdir(parents=True,exist_ok=True)
    fitted.export(out/'anatomical_prior_fit.glb')
    fitted.export(out/'anatomical_prior_fit.obj')
    report['prealignment_diagnostic']=centering
    report['camera_scale_source']=conf.get('scale_source','unknown')
    report['mesh_is_confirmed_real_body']=False
    report['holdout_labels']=sorted(holdout_labels)
    report['trained_view_count']=len(views)
    (out/'prior_fit_report.json').write_text(json.dumps(report,indent=2))
    return report

def main():
    p=argparse.ArgumentParser(prog='metric-human',description='Geometry-first human reconstruction research')
    sub=p.add_subparsers(dest='task',required=True)
    a=sub.add_parser('bench',help='Generate synthetic multi-view reconstruction and benchmark')
    a.add_argument('--out',default='outputs/synthetic')
    a.add_argument('--resolution',type=int,default=70)
    a.add_argument('--views',type=int,nargs='+',default=[1,2,4,8])
    a.add_argument('--loo',action='store_true')
    a=sub.add_parser('reconstruct',help='Carve calibrated masks into mesh and measurements')
    a.add_argument('--input',required=True)
    a.add_argument('--out',required=True)
    a=sub.add_parser('extract-mask',help='Generate initial GrabCut foreground mask from a photo')
    a.add_argument('--image',required=True)
    a.add_argument('--out',required=True)
    a=sub.add_parser('prepare-photos',help='Turn RGB images into approximate multi-view manifest')
    a.add_argument('--images',nargs='+',required=True)
    a.add_argument('--masks',nargs='+',help='One ground-truth/corrected silhouette mask per image')
    a.add_argument('--angles-deg',nargs='+',type=float,help='Camera angles / subject rotations, same order as images')
    a.add_argument('--out',required=True)
    a.add_argument('--segmentation',choices=['grabcut','alpha'],default='grabcut')
    a.add_argument('--assumed-height-m',type=float,default=1.70)
    a.add_argument('--known-height-m',type=float)
    a.add_argument('--resolution',type=int,default=75)
    a.add_argument('--centering',choices=['torso','image','bbox'],default='torso')
    a=sub.add_parser('align-depth',help='Convert relative depth to metric using >=3 independent surface-depth anchors')
    a.add_argument('--relative-npy',required=True)
    a.add_argument('--anchors-json',required=True)
    a.add_argument('--out',required=True)
    a.add_argument('--max-rmse-m',type=float,default=.05)
    a=sub.add_parser('bench-depth',help='Synthetic ablation of known-metric-depth carving vs silhouettes')
    a.add_argument('--out',required=True)
    a.add_argument('--resolution',type=int,default=60)
    a.add_argument('--views',type=int,nargs='+',default=[1,2,4,8])
    a.add_argument('--tolerance-voxels',type=float,default=.8)
    a=sub.add_parser('import-makehuman',help='Convert CC0 MakeHuman mesh and sparse targets to indexed anatomical NPZ')
    a.add_argument('--base-obj',required=True)
    a.add_argument('--positive-target',action='append',default=[],metavar='NAME=FILE')
    a.add_argument('--negative-target',action='append',default=[],metavar='NAME=FILE')
    a.add_argument('--native-unit-m',type=float,default=.1)
    a.add_argument('--source-revision',default='operator_supplied_unpinned')
    a.add_argument('--out',required=True,help='Output prior .npz (with .provenance.json sidecar)')
    a=sub.add_parser('fetch-makehuman-cc0',help='Download SHA-256-pinned MakeHuman CC0 core mesh/morph assets and make a body prior')
    a.add_argument('--out-dir',required=True)
    a.add_argument('--offline',action='store_true',help='Require files already in output asset cache (still verifies hashes)')
    a=sub.add_parser('mask-stability',help='Test reconstruction sensitivity to specified mask boundary error')
    a.add_argument('--input',required=True)
    a.add_argument('--out',required=True)
    a.add_argument('--radius-px',type=int,default=2)
    a.add_argument('--section-heights-m',type=float,nargs='*',default=None)
    a=sub.add_parser('bench-mesh',help='Benchmark silhouettes rendered from a licensed known-scale watertight body mesh')
    a.add_argument('--mesh',required=True)
    a.add_argument('--units',choices=['m','mm'],required=True)
    a.add_argument('--out',required=True)
    a.add_argument('--resolution',type=int,default=70)
    a.add_argument('--views',type=int,nargs='+',default=[1,2,4,8])
    a=sub.add_parser('test-gear',help='Test imported geometry against approximate preset motion/rig capsules')
    a.add_argument('--mesh',required=True)
    a.add_argument('--gear-units',choices=['m','mm'],required=True)
    a.add_argument('--anchor-joint',default='chest')
    a.add_argument('--offset-m',type=float,nargs=3,default=[0.,0.,0.])
    a.add_argument('--ignore-body-segments',nargs='*',default=[])
    a.add_argument('--body-npz',help='Optional reconstructed volume NPZ to estimate an UNVALIDATED scaled rig')
    a.add_argument('--body-input',help='Source reconstruction input manifest, needed with --body-npz for Grid')
    a.add_argument('--out',required=True)
    a.add_argument('--optimize-axis',type=float,nargs=3)
    a=sub.add_parser('audit-dataset',help='Audit licensed paired RGB/mesh manifests and assign subject-disjoint test folds')
    a.add_argument('--manifest',required=True)
    a.add_argument('--out',required=True)
    a.add_argument('--seed',type=int,default=17)
    a.add_argument('--no-checksums',action='store_true',help='Skip expensive file hashing (reduces duplicate protection)')
    a=sub.add_parser('bench-view-planning',help='Evaluate selected vs uniform camera views on unseen synthetic shape coefficients')
    a.add_argument('--prior',required=True)
    a.add_argument('--out',required=True)
    a.add_argument('--samples',type=int,default=6)
    a.add_argument('--seed',type=int,default=1234)
    a.add_argument('--candidates',type=int,default=8)
    a.add_argument('--select',type=int,default=2)
    a.add_argument('--width',type=int,default=140)
    a.add_argument('--height',type=int,default=210)
    a.add_argument('--maxiter',type=int,default=18)
    a.add_argument('--mask-shift-px',type=int,default=0,help='Synthetic segmentation displacement sensitivity control')
    a.add_argument('--alignment-radius-px',type=int,default=0,help='Optional per-view image-centering nuisance correction')
    a.add_argument('--prealign-radius-px',type=int,default=0,help='Optional one-time bbox center alignment before fitting')
    a.add_argument('--silhouette-loss-mode',choices=['pixel_iou','profile','coarse_to_fine'],default='pixel_iou')
    a=sub.add_parser('measure-mesh',help='Extract direct-surface horizontal cross-sectional perimeters from any metric mesh')
    a.add_argument('--mesh',required=True)
    a.add_argument('--units',choices=['m','mm'],required=True)
    exclusive=a.add_mutually_exclusive_group(required=True)
    exclusive.add_argument('--heights-m',type=float,nargs='+')
    exclusive.add_argument('--height-fractions',type=float,nargs='+')
    a.add_argument('--out',required=True)
    a=sub.add_parser('plan-views',help='Select informative synthetic camera angles for a supplied parametric body model')
    a.add_argument('--prior',required=True)
    a.add_argument('--out',required=True,help='Output JSON view-selection and identifiability report')
    a.add_argument('--candidates',type=int,default=12)
    a.add_argument('--select',type=int,default=4)
    a.add_argument('--width',type=int,default=192)
    a.add_argument('--height',type=int,default=256)
    a.add_argument('--elevation-deg',type=float,default=0.)
    a.add_argument('--parameters',nargs='+',help='Optional limited subset of known prior coefficient names')
    a.add_argument('--step',type=float,default=.3)
    a.add_argument('--noise-px',type=float,default=2.)
    a=sub.add_parser('fit-prior',help='Fit a licensed blend-shape body prior to multi-view masks and optional triangulated joints')
    a.add_argument('--input',required=True)
    a.add_argument('--prior',required=True,help='Prior NPZ: vertices/faces/shape deltas/landmark vertex ids')
    a.add_argument('--out',required=True)
    a.add_argument('--maxiter',type=int,default=75)
    a.add_argument('--no-landmarks',action='store_true')
    a.add_argument('--depth-weight',type=float,default=0.,help='Weight on independently calibrated metric surface-depth residuals')
    a.add_argument('--alignment-radius-px',type=int,default=0,help='Allow small per-view predicted mask shifts while fitting')
    a.add_argument('--prealign-radius-px',type=int,default=0,help='Optional one-time bbox center alignment')
    a.add_argument('--silhouette-loss-mode',choices=['pixel_iou','profile','coarse_to_fine'],default='pixel_iou')
    a.add_argument('--holdout-label',nargs='+',default=[],help='Exclude camera labels from all fitting evidence, then evaluate unseen-view agreement')
    a=sub.add_parser('segment-sam2',help='Generate inspectable RGB segmentation masks via optional SAM2.1 Tiny')
    a.add_argument('--images',nargs='+',required=True)
    a.add_argument('--out',required=True)
    a.add_argument('--boxes-json',help='JSON with boxes:[[x0,y0,x1,y1],...] (one per image), else GrabCut prompt')
    a.add_argument('--model-id',default='facebook/sam2.1-hiera-tiny')
    a.add_argument('--revision',help='Optional exact Hugging Face commit for reproducibility')
    a.add_argument('--device',default='auto',choices=['auto','cpu','cuda'])
    a=sub.add_parser('infer-depth',help='Generate *relative* RGB depth evidence via optional Depth Anything V2 Small')
    a.add_argument('--images',nargs='+',required=True)
    a.add_argument('--out',required=True)
    a.add_argument('--model-id',default='depth-anything/Depth-Anything-V2-Small-hf')
    a.add_argument('--revision',help='Optional exact Hugging Face commit for reproducibility')
    a.add_argument('--device',default='auto',choices=['auto','cpu','cuda'])
    a=sub.add_parser('calibrate-pnp',help='Recover camera pose from >=6 matched 3D anatomical/model points and 2D landmarks')
    a.add_argument('--anchors-json',required=True,help='JSON: points_world and pixels_by_label maps')
    a.add_argument('--width',type=int,required=True)
    a.add_argument('--height',type=int,required=True)
    a.add_argument('--fx',type=float,required=True)
    a.add_argument('--fy',type=float,required=True)
    a.add_argument('--cx',type=float)
    a.add_argument('--cy',type=float)
    a.add_argument('--out',required=True)
    a=sub.add_parser('match-features',help='Match foreground features from two static RGB observations for calibration')
    a.add_argument('--image-first',required=True)
    a.add_argument('--image-second',required=True)
    a.add_argument('--mask-first',required=True)
    a.add_argument('--mask-second',required=True)
    a.add_argument('--out',required=True)
    a=sub.add_parser('calibrate-two-view',help='Estimate relative camera motion from matched static 2D features; baseline in arbitrary units')
    a.add_argument('--correspondences-json',required=True,help='JSON: pixels_first and pixels_second maps with shared feature labels')
    a.add_argument('--width',required=True,type=int)
    a.add_argument('--height',required=True,type=int)
    a.add_argument('--fx',required=True,type=float)
    a.add_argument('--fy',required=True,type=float)
    a.add_argument('--fx2',type=float,help='Second camera focal length, default same as first')
    a.add_argument('--fy2',type=float)
    a.add_argument('--cx',type=float)
    a.add_argument('--cy',type=float)
    a.add_argument('--cx2',type=float)
    a.add_argument('--cy2',type=float)
    a.add_argument('--out',required=True)
    a=sub.add_parser('make-viewer',help='Write self-contained interactive viewer for procedural benchmark outputs')
    a.add_argument('--benchmark-dir',required=True)
    args=p.parse_args()
    if args.task=='bench':
        result=run_benchmark(args.out,resolution=args.resolution,view_counts=args.views,do_loo=args.loo)
        for row in result['rows']:
            print(f"{row['views']} views: IoU={row['synthetic_voxel_iou']:.4f}, "
                  f"width error={row['x_width_mm']:.1f} mm, depth error={row['y_depth_mm']:.1f} mm")
    elif args.task=='segment-sam2':
        data=json.loads(Path(args.boxes_json).read_text()) if args.boxes_json else {}
        result=generate_sam2_masks(args.images,args.out,boxes=data.get('boxes'),
                                   model_id=args.model_id,revision=args.revision,device=args.device)
        print(json.dumps({'masks':[r['mask'] for r in result['records']],
                          'manifest':str(Path(args.out)/'vision_manifest.json')},indent=2))
    elif args.task=='calibrate-pnp':
        config=json.loads(Path(args.anchors_json).read_text())
        solved=solve_perspective_pnp(config['points_world'],config['pixels_by_label'],
                image_width=args.width,image_height=args.height,fx_px=args.fx,fy_px=args.fy,
                cx_px=args.cx,cy_px=args.cy,
                coordinate_scale_source=config.get('coordinate_scale_source','unknown'))
        dest=Path(args.out);dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_text(json.dumps(solved.to_dict(),indent=2),encoding='utf8')
        print(json.dumps({'inliers':solved.n_ransac_inliers,
                          'reprojection_rmse_px':solved.reprojection_rmse_px,
                          'metric_body_geometry_independently_verified':False},indent=2))
    elif args.task=='match-features':
        match=match_masked_rgb_features(args.image_first,args.image_second,
                                        args.mask_first,args.mask_second)
        dest=Path(args.out);dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_text(json.dumps(match.to_dict(),indent=2),encoding='utf8')
        print(json.dumps({'matched_features':len(match.pixels_first),
                          'static_correspondence_verified':False,
                          'metric_scale_verified':False},indent=2))
    elif args.task=='calibrate-two-view':
        observations=json.loads(Path(args.correspondences_json).read_text())
        result=recover_relative_cameras(
            observations['pixels_first'],observations['pixels_second'],
            image_width=args.width,image_height=args.height,
            first_fx_px=args.fx,first_fy_px=args.fy,
            second_fx_px=args.fx2,second_fy_px=args.fy2,
            first_cx_px=args.cx,first_cy_px=args.cy,
            second_cx_px=args.cx2,second_cy_px=args.cy2)
        dest=Path(args.out);dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_text(json.dumps(result.to_dict(),indent=2),encoding='utf8')
        print(json.dumps({'inliers':len(result.inlier_labels),
            'rmse_px':result.reprojection_rmse_px,
            'parallax_deg':result.median_parallax_deg,
            'metric_scale_verified':False},indent=2))
    elif args.task=='infer-depth':
        result=generate_relative_depth(args.images,args.out,
                          model_id=args.model_id,revision=args.revision,device=args.device)
        print(json.dumps({'relative_depth':[r['relative_depth'] for r in result['records']],
                          'metric_depth':False,'manifest':str(Path(args.out)/'vision_manifest.json')},indent=2))
    elif args.task=='reconstruct':
        r=from_config(args.input,args.out)
        print(json.dumps(r,indent=2))
    elif args.task=='make-viewer':
        print(write_demo_viewer(args.benchmark_dir))
        print(write_contact_sheet(args.benchmark_dir))
    elif args.task=='audit-dataset':
        report=audit_dataset_manifest(args.manifest,seed=args.seed,
                                      compute_checksums=not args.no_checksums)
        write_audit(args.out,report)
        print(json.dumps({'sessions':report['sessions'],
                          'subjects':report['unique_subjects'],
                          'subject_disjoint_splits':report['split_subject_counts'],
                          'source_scans_accuracy_verified':False},indent=2))
    elif args.task=='bench-view-planning':
        report=run_view_planning_benchmark(Prior.load(args.prior),samples=args.samples,
                  seed=args.seed,candidate_count=args.candidates,select=args.select,
                  image_width=args.width,image_height=args.height,maxiter=args.maxiter,
                  mask_shift_px=args.mask_shift_px,alignment_radius_px=args.alignment_radius_px,
                  prealign_radius_px=args.prealign_radius_px,
                  silhouette_loss_mode=args.silhouette_loss_mode,out_path=args.out)
        print(json.dumps({'summary':report['summary'],
                          'selected':report['planned_labels'],
                          'real_human_accuracy_validated':False},indent=2))
    elif args.task=='measure-mesh':
        report=measure_external_mesh(args.mesh,units=args.units,
                                     heights_m=args.heights_m,fractions=args.height_fractions)
        save_section_report(args.out,report)
        print(json.dumps({'section_count':len(report['sections']),
                          'contours_per_section':[s['separate_contour_count'] for s in report['sections']],
                          'human_measurement_accuracy_validated':False},indent=2))
    elif args.task=='plan-views':
        prior=Prior.load(args.prior)
        candidates=orbit_candidates(prior,count=args.candidates,width=args.width,
                                     height=args.height,elevation_deg=args.elevation_deg)
        report=plan_views(prior,candidates,select=args.select,
                          selected_parameters=args.parameters,step=args.step,
                          mask_noise_px=args.noise_px)
        save_view_plan(args.out,report)
        print(json.dumps({'selected':[x['label'] for x in report['selected']],
                          'observable_rank':report['local_observable_rank_without_prior'],
                          'parameter_count':report['parameter_count'],
                          'real_human_accuracy_validated':False},indent=2))
    elif args.task=='fit-prior':
        report=fit_prior_manifest(args.input,args.prior,args.out,maxiter=args.maxiter,
                                  use_landmarks=not args.no_landmarks,depth_weight=args.depth_weight,
                                  alignment_radius_px=args.alignment_radius_px,
                                  prealign_radius_px=args.prealign_radius_px,
                                  silhouette_loss_mode=args.silhouette_loss_mode,
                                  holdout_labels=args.holdout_label)
        print(json.dumps({'objective':report['objective'],
                          'coefficients':report['coefficients'],
                          'landmark_error':report['landmark_euclidean_error_world_units'],
                          'held_out_validation':report.get('held_out_validation')},indent=2))
    elif args.task=='test-gear':
        partmesh=trimesh.load_mesh(args.mesh,force='mesh')
        partmesh.apply_scale(.001 if args.gear_units=='mm' else 1.)
        part=Gear('imported_gear',partmesh,args.anchor_joint,tuple(args.offset_m),
                  tuple(args.ignore_body_segments))
        if bool(args.body_npz) != bool(args.body_input):
            raise ValueError('--body-npz and --body-input must be provided together')
        if args.body_npz:
            source_conf=json.loads(Path(args.body_input).read_text())
            grid=Grid.from_dict(source_conf['grid'])
            with np.load(args.body_npz,allow_pickle=False) as container:
                rig,rig_status=approximate_rig_from_volume(container['occupancy'],grid)
            rig_status['scale_source']=source_conf.get('scale_source','unknown')
        else:
            rig=sample_rig()
            rig_status={'method':'generic_procedural_proxy', 'anatomical_joint_positions_validated':False}
        clip=sample_shoulder_motion()
        result=evaluate_clip(rig,[part],clip)
        result['rig_provenance']=rig_status
        result['geometry_input']={'mesh_path':args.mesh,'gear_units':args.gear_units,
                                  'anchor_joint':args.anchor_joint,'offset_m':args.offset_m}
        if args.optimize_axis:
            result['one_axis_offset_experiment']=optimize_offset_along_axis(
                rig,part,clip,axis=args.optimize_axis)
        out=Path(args.out);out.parent.mkdir(parents=True,exist_ok=True)
        out.write_text(json.dumps(result,indent=2))
        print(json.dumps(result['summary'],indent=2))
    elif args.task=='bench-depth':
        result=run_depth_ablation(args.out,resolution=args.resolution,
                                  view_counts=args.views,tolerance_voxels=args.tolerance_voxels)
        print(json.dumps(result['rows'],indent=2))
    elif args.task=='import-makehuman':
        def pairs(items):
            result={}
            for item in items:
                if '=' not in item:raise ValueError('Targets must be named NAME=FILE')
                name,path=item.split('=',1)
                if not name or not path or name in result:
                    raise ValueError('Duplicate/empty target name or file path')
                result[name]=path
            return result
        imported=import_makehuman_prior(args.base_obj,
                 positive_targets=pairs(args.positive_target),
                 negative_targets=pairs(args.negative_target),
                 meters_per_native_unit=args.native_unit_m,
                 source_revision=args.source_revision)
        path,sidecar=save_imported_prior(imported,args.out)
        print(json.dumps({'prior_npz':str(path),'provenance_json':str(sidecar),
                          'parameters':imported.provenance['parameters'],
                          'reference_height_m_assuming_declared_scale':imported.provenance['reference_height_m_assuming_declared_scale'],
                          'real_person_accuracy_validated':False},indent=2))
    elif args.task=='fetch-makehuman-cc0':
        ppath,receipt_path=create_pinned_makehuman_prior(args.out_dir,allow_network=not args.offline)
        print(json.dumps({'anatomical_prior':str(ppath),'provenance':str(receipt_path),
                          'not_validated_subject_geometry':True},indent=2))
    elif args.task=='mask-stability':
        config_path=Path(args.input)
        conf=json.loads(config_path.read_text())
        grid=Grid.from_dict(conf['grid'])
        views=[]
        for entry in conf['views']:
            if 'depth_m' in entry:
                raise ValueError('mask-stability is silhouette-only; metric depth evidence must not be silently ignored')
            img=cv2.imread(str(config_path.parent/entry['mask']),cv2.IMREAD_GRAYSCALE)
            if img is None:raise ValueError('Missing mask: '+entry['mask'])
            views.append(View(Camera.from_dict(entry['camera']),img>127,
                    label=entry.get('label',''),weight=float(entry.get('weight',1.))))
        categories,report=silhouette_boundary_sensitivity(views,grid,
                        radius_px=args.radius_px,
                        min_fraction=conf.get('min_fraction',1.),
                        sample_section_z=(args.section_heights_m if args.section_heights_m is not None
                                          else conf.get('cross_section_heights',[])))
        path=save_silhouette_sensitivity(args.out,categories,report)
        print(json.dumps({'report':str(path),'mask_error_radius_px':args.radius_px,
                          'this_is_calibrated_uncertainty':False},indent=2))
    elif args.task=='bench-mesh':
        result=run_external_mesh_benchmark(args.mesh,args.out,units=args.units,
                                           resolution=args.resolution,views=args.views)
        print(json.dumps(result['rows'],indent=2))
    elif args.task=='prepare-photos':
        info=prepare_photographs(args.images,args.out,masks=args.masks,
                   angles_deg=args.angles_deg,segmentation=args.segmentation,
                   assumed_height_m=args.assumed_height_m,
                   known_height_m=args.known_height_m,resolution=args.resolution,
                   centering=args.centering)
        print(json.dumps(info,indent=2))
    elif args.task=='align-depth':
        relative=np.load(args.relative_npy,allow_pickle=False)
        anchor_data=json.loads(Path(args.anchors_json).read_text())
        metric,alignment=align_relative_depth(relative,anchor_data['anchors'],max_rmse_m=args.max_rmse_m)
        out=Path(args.out);out.parent.mkdir(parents=True,exist_ok=True)
        np.save(out,metric)
        receipt,receipt_path=write_aligned_depth_receipt(
           aligned_path=out,relative_path=args.relative_npy,anchors_path=args.anchors_json,
           alignment=alignment,max_rmse_m=args.max_rmse_m)
        print(json.dumps({'calibration':alignment.to_dict(),
                          'receipt':str(receipt_path),'metric_depth_file_sha256':receipt['metric_depth_file_sha256']},indent=2))
    elif args.task=='extract-mask':
        mask=mask_from_image(args.image)
        Path(args.out).parent.mkdir(parents=True,exist_ok=True)
        cv2.imwrite(args.out,np.uint8(mask)*255)
        print(args.out)

if __name__=='__main__': main()
