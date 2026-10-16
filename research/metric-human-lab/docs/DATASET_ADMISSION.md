# Rights-aware RGB/3D dataset admission

This project must not confuse public internet access with permission to
redistribute biometric scans, photographs, or model weights. An open-source
code repository may evaluate a dataset locally under its permitted research
terms, but cannot automatically bundle the data or distribute trained weights
if the dataset's license or subject consent prohibits it.

## Manifest contract

Create `dataset.json` beside the original files (here `subject-001` is a
pseudonymous identifier, not a person's actual name):

```json
{
  "records": [
    {
      "subject_id": "subject-001",
      "session_id": "session-a",
      "reference_mesh": "subject-001/scan.obj",
      "mesh_units": "m",
      "images": ["subject-001/front.png", "subject-001/side.png"],
      "license": "CC-BY-NC-4.0",
      "data_kind": "real_scan",
      "camera_status": "unknown"
    }
  ]
}
```

The manifest is an *operator declaration*, not an independent proof of
copyright, subject consent, image-ground-truth registration, scan accuracy, or
image-to-mesh suitability.

```bash
python -m metric_human audit-dataset \
  --manifest /path/to/local/dataset.json \
  --out outputs/local_dataset_audit.json --seed 17
```

The command checks that all assets exist under the manifest directory,
requires explicit source units/licenses, hashes images/meshes for cross-identity
leakage detection, and assigns identity-disjoint train/validation/test folds.
It writes a JSON report, not a copy of any photo, mesh, or annotation.

The audit is not yet a full RGB-to-metric benchmark. Camera calibration,
subject consent, collection rights, accurate body segmentation and independent
measurement validation are separate gates.

## Candidate research datasets (evaluate each license independently)

- **TEXEL BodyScan Dataset**: scanned humans and RGB-D capture information,
  some part-specific mesh/measurement data. Dataset **CC-BY-NC-4.0**, while its
  parser code is MIT. Never bundle the photographs/scans in our MIT package.
  https://github.com/m-krivov/Texel-BodyScan-Dataset
- **Fraunhofer multiview human sequences**: calibrated multiview images and
  reconstructed meshes for a small number of participants. Check the actual
  download/license before admitting a dataset.
  https://cvg.hhi.fraunhofer.de/mv-3d-seq.htm
- **THuman2.0**: scan geometry with associated textures and SMPL fits,
  subject to restrictive research-only agreements. Do not redistribute.
  https://github.com/ytrock/THuman2.0-Dataset

Open human data is not interchangeable with CC0 synthetic anatomy; keeping
files outside the source tree avoids accidental publication. Human scans and
images are potentially sensitive biometric information, so restrict access
and do not publish face-bearing scans or images without specific consent.
