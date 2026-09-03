# Storage and Export

## Storage goals

- crash resistant
- incremental
- raw-first
- native-rate
- indexed
- replayable
- forward-compatible
- usable without export
- suitable for future analysis

## Proposed canonical session package

Example:

project_session.mmsession/
- manifest.json
- journal.sqlite
- integrity.json
- events/
- sources/
  - Camera_Front/
  - Delsys_Main/
  - Xsens_UpperBody/
  - Radar_Front/
- mappings/
- calibrations/
- processing/
- logs/
- recovery/
- exports/

## Numeric/structured stream storage

Recommended direction:
- MCAP for timestamped non-video streams
- message batching for high-rate data

Do not create one message per EMG sample.

EMG batch should contain:
- first sample index
- timing information
- channel list
- matrix [channels x samples]
- quality flags

Xsens:
- synchronized multi-IMU frame or small batches

Radar:
- raw radar frame or small frame batch
- configuration hash/reference

## Video

Use a crash-tolerant segmented video strategy.

Store:
- encoded video segment
- exact per-frame timing sidecar where needed
- source configuration
- codec information

Rewrap/export to MP4 later if desired.

## Incremental journal

Journal:
- session creation
- source start/stop
- worker failure
- reconnect
- checkpoint
- annotation
- sync anchor
- configuration changes
- warnings
- finalization state

## Integrity manifest

For each output file:
- path
- size
- hash
- source
- time range
- expected count
- actual count
- finalization/recovery status

## Export modes

### Continuous export
Default.

### Structured checkpoint export
Creates section folders/manifests referencing original time ranges.

### Materialized sections
Actually creates cut files for each checkpoint-defined section.

### Interoperable formats
- CSV
- Parquet
- HDF5 / NumPy-friendly arrays
- JSON metadata
- MP4/video
- canonical session package

Never silently drop:
- native timestamps
- session timestamps
- indices
- quality flags
- provenance
