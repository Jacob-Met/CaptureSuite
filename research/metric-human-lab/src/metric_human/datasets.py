"""Rights-aware dataset audit and subject-disjoint evaluation splits.

No dataset contents are redistributed, photographed people are not uploaded,
and no arbitrary provider license is assumed by this module. A dataset manifest
is a declaration by its operator, not independently verified consent.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path


_ALLOWED_MESH={'.obj','.ply','.stl','.glb','.gltf'}
_ALLOWED_IMAGE={'.png','.jpg','.jpeg','.webp','.bmp','.tiff','.tif'}


def _safe_file(root:Path,asset_name:str,extensions:set[str]):
    if not isinstance(asset_name,str) or not asset_name or Path(asset_name).is_absolute():
        raise ValueError('Assets must use nonempty relative paths')
    resolved=(root/asset_name).resolve()
    if not resolved.is_relative_to(root):
        raise ValueError('Asset path escapes manifest directory')
    if not resolved.is_file():
        raise ValueError(f'Asset missing: {asset_name}')
    if resolved.suffix.lower() not in extensions:
        raise ValueError(f'Unsupported asset file extension: {asset_name}')
    return resolved


def _sha256_file(path:Path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(2*1024*1024),b''):
            h.update(block)
    return h.hexdigest()


def _split(subject_ids:list[str], seed:int, fractions=(.7,.15,.15)):
    unique=sorted(set(subject_ids))
    if not isinstance(seed,int) or not 0<=seed<=2**32-1:
        raise ValueError('seed must be unsigned 32-bit integer')
    if len(fractions)!=3 or any(x<0 for x in fractions) or abs(sum(fractions)-1)>1e-9:
        raise ValueError('Split ratios must be nonnegative and sum to one')
    ranked=sorted(unique,key=lambda s:(hashlib.sha256(f'{seed}:{s}'.encode()).hexdigest(),s))
    n=len(ranked)
    n_train=int(round(n*fractions[0]))
    n_val=int(round(n*fractions[1]))
    if n>=3 and all(x>0 for x in fractions):
        n_train=max(1,min(n-2,n_train))
        n_val=max(1,min(n-n_train-1,n_val))
    elif n>=2:
        n_train=max(1,min(n-1,n_train));n_val=min(n-n_train,n_val)
    else:n_train=n;n_val=0
    return {**{s:'train' for s in ranked[:n_train]},
            **{s:'validation' for s in ranked[n_train:n_train+n_val]},
            **{s:'test' for s in ranked[n_train+n_val:]}}


def audit_dataset_manifest(manifest_path:str|Path,*,seed:int=17,compute_checksums:bool=True):
    """Check dataset structure, licenses, pairing and subject-level leakage.

    JSON structure:
      {"records":[{"subject_id":"pseudo-001","session_id":"capture-1",
        "reference_mesh":"mesh.obj","mesh_units":"m",
        "images":["front.png","side.png"],"license":"CC-BY-NC-4.0",
        "data_kind":"real_scan", "camera_status":"unknown"}]}
    All files must live under this manifest's directory. No scans are copied.
    """
    path=Path(manifest_path).resolve()
    doc=json.loads(path.read_text(encoding='utf8'))
    records=doc.get('records')
    if not isinstance(records,list) or not records:
        raise ValueError('Dataset manifest requires a nonempty records list')
    if len(records)>1_000_000:
        raise ValueError('Dataset manifest is unexpectedly large')
    root=path.parent.resolve()
    if not all(isinstance(record,dict) for record in records):
        raise ValueError('Every record must be an object')
    if not all(isinstance(record.get('subject_id'),str) and record['subject_id'].strip() for record in records):
        raise ValueError('Use nonempty pseudonymous subject IDs')
    split_map=_split([r['subject_id'] for r in records],seed)
    seen_keys=set();mesh_hash_subjects={};image_hash_subjects={};validated=[]
    for item in records:
        if not isinstance(item,dict):raise ValueError('Every record must be an object')
        who=item.get('subject_id');session=item.get('session_id')
        if not isinstance(who,str) or not who.strip() or len(who)>128:
            raise ValueError('Use nonempty pseudonymous subject IDs')
        if not isinstance(session,str) or not session.strip() or len(session)>128:
            raise ValueError('Use nonempty session IDs')
        key=(who,session)
        if key in seen_keys:
            raise ValueError('Duplicate subject/session pair')
        seen_keys.add(key)
        if item.get('mesh_units') not in ('m','mm'):
            raise ValueError('Reference mesh requires explicit physical units m or mm')
        if item.get('camera_status') not in ('known','unknown','partially_calibrated'):
            raise ValueError('Camera calibration status must be declared')
        if item.get('data_kind') not in ('real_scan','procedural_synthetic','anatomical_template'):
            raise ValueError('Declared data provenance kind required')
        license_name=item.get('license')
        if not isinstance(license_name,str) or len(license_name)<3 or license_name.strip().lower() in ('unknown','none','n/a'):
            raise ValueError('Explicit data rights/license required')
        images=item.get('images')
        if not isinstance(images,list) or not images or len(images)>1000:
            raise ValueError('Each session requires 1..1000 RGB images')
        mesh_path=_safe_file(root,item.get('reference_mesh'),_ALLOWED_MESH)
        image_paths=[_safe_file(root,image,_ALLOWED_IMAGE) for image in images]
        if len(set(image_paths))!=len(image_paths):
            raise ValueError('Duplicate image path within session')
        mesh_hash=_sha256_file(mesh_path) if compute_checksums else None
        image_hashes=[_sha256_file(p) for p in image_paths] if compute_checksums else None
        if mesh_hash:
            mesh_hash_subjects.setdefault(mesh_hash,set()).add(who)
            for h in image_hashes:
                image_hash_subjects.setdefault(h,set()).add(who)
        validated.append({'subject_id':who,'session_id':session,'split':split_map[who],
                          'mesh':str(mesh_path.relative_to(root)),
                          'mesh_sha256':mesh_hash,'image_count':len(image_paths),
                          'image_sha256':image_hashes,
                          'reference_kind_operator_declared':item['data_kind'],
                          'camera_status_operator_declared':item['camera_status'],
                          'mesh_units_operator_declared':item['mesh_units'],
                          'license_operator_declared':license_name,
                          'license_permits_redistribution_verified':False})
    cross_mesh={h:sorted(ids) for h,ids in mesh_hash_subjects.items() if len(ids)>1}
    cross_img={h:sorted(ids) for h,ids in image_hash_subjects.items() if len(ids)>1}
    if cross_mesh or cross_img:
        raise ValueError('Identical mesh/image bytes are attributed to different subject identities; leakage risk')
    split_counts={s:sum(split_map[x]==s for x in split_map) for s in ('train','validation','test')}
    return {'audit_type':'rights_declared_subject_disjoint_manifest_audit',
            'manifest_sha256':_sha256_file(path),
            'seed':seed,'sessions':len(validated),'unique_subjects':len(split_map),
            'split_subject_counts':split_counts,
            'records':validated,'duplicate_assets_across_subjects':False if compute_checksums else None,
            'checksums_calculated':compute_checksums,
            'real_human_measurement_accuracy_validated':False,
            'camera_calibration_independently_verified':False,
            'subject_consent_and_data_rights_independently_verified':False,
            'limitations':[
                'A dataset license declaration does not grant rights; operator must independently verify consent and usage terms.',
                'Subject-disjoint splits prevent direct identity leakage, not look-alike scans or implicit dataset duplicates.',
                'This audit does not validate geometric accuracy of source scanner or RGB-to-3D correspondence.',
                'No photograph, scan, or sensitive measurement is uploaded or included in the report.',
            ]}


def write_audit(path:str|Path,report:dict):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(report,indent=2),encoding='utf8')
    return path
