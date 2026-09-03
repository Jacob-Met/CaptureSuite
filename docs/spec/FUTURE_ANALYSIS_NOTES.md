# Future Analysis Requirements — Capture-Side Constraints Only

The full analysis suite is intentionally deferred.

However, capture/storage must preserve enough information to support it later.

**Radar-to-kinematics ML track:** see [`docs/PROJECT_OUTLINE.md`](../../docs/PROJECT_OUTLINE.md) and [`DATA_COLLECTION_PROTOCOL.md`](../docs/design/DATA_COLLECTION_PROTOCOL.md). Capture sessions for that track require radar + video + sync anchors + activity checkpoint tags even before analysis jobs exist.

## Future analysis must operate on

- full continuous session
- current checkpoint section
- selected checkpoint sections
- arbitrary time ranges
- tags/structured checkpoint metadata
- externally imported datasets where feasible

## Expected future outputs

- graphs
- synchronized multimodal plots
- derived streams
- EMG features
- joint/kinematic metrics
- mobility
- speed
- acceleration
- joint angles
- activation timing
- multimodal EMG-motion relationships
- checkpoint/trial summaries
- extracted features
- ML-ready matrices/sequences
- radar–kinematics aligned windows (`ml_bundle` — see [ANALYSIS.md](../docs/design/ANALYSIS.md) Phase E)
- kinematic teacher labels (`kinematics.parquet` — Phase D2)
- external graphing tables
- reports

## Analysis architecture direction

Prefer canonical non-proprietary implementations:
- Python
- NumPy
- SciPy
- pandas
- PyTorch/etc.

MATLAB:
- optional compatibility/integration
- not required for the base app
- reimplement conventional algorithms in open Python libraries when practical
- validate numerical equivalence when replacing MATLAB pipelines

## Resampling

Never modify raw stream rates.

Later analysis may:
- interpolate low-rate kinematics to a chosen timeline
- reduce high-rate EMG into windows/features
- use event-based alignment
- select an analysis master grid

Every derived resampling operation records:
- source
- target grid/rate
- method
- parameters
- provenance

## Anatomical correlation

Future defaults:
- muscles -> anatomical regions
- muscles -> joints
- muscles -> body segments
- muscles -> pose landmarks/relationships

Defaults must be user-editable.

Custom nonstandard regions need manual associations.

## Related documents

| Document | Purpose |
|----------|---------|
| [PROJECT_OUTLINE.md](../../docs/PROJECT_OUTLINE.md) | Radar-to-kinematics research master index |
| [DATA_COLLECTION_PROTOCOL.md](../docs/design/DATA_COLLECTION_PROTOCOL.md) | Multimodal capture protocol |
| [KINEMATICS_PIPELINE.md](../docs/design/KINEMATICS_PIPELINE.md) | Teacher label pipeline |
| [ANALYSIS.md](../docs/design/ANALYSIS.md) | Offline analysis phases D–F |
| [RadarKinematicsML/SPEC.md](../../RadarKinematicsML/SPEC.md) | Linux training specification |
