# Radar Motion Inference Seed

**State:** experimental / provisional. This is not a trained or hardware-validated radar→kinematics model.

## Why this exists

CaptureSuite already records raw FMCW radar and exposes a range–Doppler preview. Its Phase 6 analysis path already aligns radar features to kinematics teacher windows, but the current eval path is an identity-teacher fixture sanity check. This seed fills the missing *mechanical* seam between a live range–Doppler matrix and a tiny low-latency model interface without claiming that synthetic qualification proves body kinematics.

## What it does

- Converts each 2-D range–Doppler magnitude matrix into 14 bounded descriptors: energy, range/Doppler centroid/spread, signed Doppler balance, entropy, peak coordinates, and temporal change.
- Stacks a short history (default 8 frames / about 0.4 s at 20 Hz).
- Supports a deterministic multi-output ridge model artifact with explicit `training_evidence` and `calibrated` provenance.
- Refuses to call synthetic-only artifacts hardware-validated.
- Provides an attach-only live probe. It subscribes to an already-running CaptureSuite preview and makes no session/config/source-selection mutations.
- Provides deterministic synthetic fixtures, a held-out trajectory test, shuffled-label control, Doppler-sign-flip control, changed-preview-geometry control, a high-noise stress case, and an end-to-end latency gate.

## Run the synthetic qualification

```powershell
python tools/probe_radar_motion_seed.py --synthetic --write-synthetic-model artifacts/radar-motion-synthetic-only.npz
```

The written model is a fixture artifact only. It must not be described as a real radar kinematics model.

## Live descriptor probe (safe attach-only)

With CaptureSuite already running an FMCW `range_doppler` preview:

```powershell
python tools/probe_radar_motion_seed.py --live-attach --seconds 10
```

This produces only provisional motion descriptors. No learned kinematics are emitted unless `--model` is supplied.

## Qualification observed before branch publication

On the isolated seed workspace:

- unit/negative-control tests: **5/5 PASS**;
- synthetic held-out range RMSE: about **0.0017 normalized units**;
- synthetic held-out radial-velocity RMSE: about **0.011 normalized units**;
- changed 48×64 preview-geometry range RMSE: about **0.0116**;
- changed 48×64 preview-geometry radial-velocity RMSE: about **0.0181**;
- shuffled-label control: rejected;
- Doppler-sign-flip control: rejected;
- end-to-end descriptor + ridge inference p95: about **0.27 ms** in the qualification environment versus a **50 ms** 20 Hz frame budget.

Those numbers are synthetic mechanics evidence only. They are not accuracy estimates for a person in front of the BGT60TR13C.

A deliberately harsher synthetic noise case raised the joint-angle stand-in RMSE to roughly **36.7°** while the direct range/radial proxies degraded much less. Preserve that as negative evidence: kinematic quality is sensitive to domain shift and will require real paired teacher data, richer RD-window features, and held-out hardware evaluation.

## What should happen next with real paired data

1. Record radar + a trusted kinematics teacher simultaneously through CaptureSuite.
2. Materialize richer RD-window features, not only scalar motion energy.
3. Split evaluation by session/person/motion family; never random-frame split a single sequence.
4. Fit a baseline model and compare against constant/previous-value/shuffled-label controls.
5. Record latency on the actual qualified radar workstation.
6. Only set `training_evidence=hardware_validated` after independent held-out hardware evaluation and only set `calibrated=true` when output units/geometry are justified.

## Hard limit

Upscaling a heatmap can make a visualization smoother, but cannot create range/Doppler information absent from the sensor. ML may improve estimation by learning priors across time and paired teacher data; it must be evaluated as inference, not treated as recovered sensor resolution.
