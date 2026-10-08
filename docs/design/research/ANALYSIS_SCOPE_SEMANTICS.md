# Analysis scope semantics

Research date: **2026-09-01**  
Maps UI scope picker → [`JobParams`](../../libs/python/capture_analysis/capture_analysis/jobs.py) + `job_manifest.json`.

**Constraint:** Native rates preserved in raw; scope only limits **job time window**, never rewrites sources.

---

## 1. Scope modes

| UI mode | JobParams fields | Manifest fields |
|---------|------------------|-----------------|
| **Full session** | `start_session_ns=None`, `end_session_ns=None` | `timeRange: null` |
| **Checkpoint section** | `checkpoint_section=<name>` | `checkpointSection`, resolved `[t0,t1]` |
| **Time range** | `start_session_ns`, `end_session_ns` | `timeRange: {start,end}` |
| **Tag filter** | `extra.tags[]` | `tags[]` (future) |
| **Source subset** | `sources[]` | `sourceFilter[]` |

Multiple modes compose: e.g. section **and** source subset.

---

## 2. Checkpoint section resolution

The current desktop and CLI share `checkpoint_section_window`: load the recorded
checkpoints, stably sort by their effective timestamp, and resolve the section from
the preceding checkpoint (or session time zero for the first checkpoint) through
the selected checkpoint. The selected checkpoint closes the section; it does not
name the following interval or an implicit trailing section through session end.
Timestamp aliases, the existing missing-timestamp fallback, and explicit zero
timestamps retain the backend's existing behavior. Open gaps remain in the mask.
The desktop passes the stable checkpoint ID and shows it alongside repeated display
names. The picker displays the backend's exact resolved bounds. It requires a
positive-duration selection; nonpositive or unresolved sections remain unavailable
with a Time range fallback.
The current backend also accepts checkpoint names. If a different checkpoint's
name shadows the selected ID, that section is explicitly unavailable in the
desktop, with an explanation and Time range fallback. The UI does not offer the
other checkpoint's bounds under the selected section's name.

Resolution through `section=<name>` tags or protocol presets remains a future
extension; the desktop does not reinterpret those tags as checkpoint IDs.

If section incomplete: warn in QC; `gap_policy=fail` fails job if gap overlaps section > threshold.

---

## 3. Sync anchors

| Flag | Behavior |
|------|----------|
| `apply_sync_anchors=true` | Apply per-modality offset from `sync_anchors.json` before feature alignment |
| Record in manifest | `syncOffsetsApplied[]` with anchor id + delta_ns |

Offsets affect **derived** grids only ([AnalysisGrid](#4-analysisgrid-link)).

---

## 4. AnalysisGrid link

When job produces cross-stream alignment (Phase E):

```json
{
  "gridId": "radar_kinematics_v1",
  "nominalRateHz": 20,
  "method": "sync_anchor_offset + linear_interp_labels",
  "sourceStreams": ["radar.fmcw.primary", "kinematics.teacher"],
  "validMaskPolicy": "all_streams_required"
}
```

Scope picker sets grid **time bounds**; grid engine sets **sample times** inside bounds.

---

## 5. Gap policy interaction

| Policy | Scope with gap inside |
|--------|------------------------|
| `mask` | valid_mask false in affected windows |
| `split` | Multiple output shards per contiguous valid region |
| `fail` | Job status failed |

UI shows gap bands on SessionTimeline when selecting range.

---

## 6. Pose / kinematics scope

| Job | Scope rule |
|-----|------------|
| Pose | Decode video segments intersecting scope only |
| Kinematics | Read pose parquet rows in scope |
| ML bundle | Windows fully inside scope; drop partial windows at edges |

---

## 7. UI binding

The implemented time picker in `widgets_analysis_scope.py` emits an immutable
`ScopeSelection` containing `mode`, `section_name`, `start_ns`, and `end_ns`.
`SessionHeader.scope_changed` also carries the resolved package path. Analysis
accepts a selection only for its current package, and each worker snapshots it
before its QThread starts. A later UI selection cannot change the running job.

Full session passes the backend defaults. Checkpoint section passes the checkpoint
ID; the manifest records the backend's resolved bounds and checkpoint identity.
Time range converts decimal session seconds to integer nanoseconds without a float
round trip or rounding away sub-nanosecond input. Both endpoints follow the existing
inclusive backend window convention. Invalid or reversed bounds disable Run.

Click the sealed timeline to move its cursor. In Time range mode, **Start at cursor**
and **End at cursor** copy that position into the respective field; typed fields
support exact nanosecond values. The selected interval is outlined across the lanes
so recorded gap bands remain visible. Live capture retains its existing clock and
does not expose these offline controls. Sealed selections survive the normal UI
refresh and Review/Analysis navigation. Selecting another package starts at Full
session; a failed open disables analysis and clears its summary.

Time scopes are enabled for Features, Plots, Features + plots and Pose, whose
existing implementations consume `TimeWindow`. The QC report still describes the
whole package. QC-only, Kinematics, ML bundle and Eval require Full session in this
desktop path because they operate on the whole package or their selected input
jobs. No unsupported command silently falls back to a full-session job.

Source subsets, tag filters and sync-anchor controls remain outside this time-picker
implementation. The broader planned selection contract is:

```python
@dataclass
class ScopeSelection:
    mode: Literal["full", "section", "range", "tags"]
    section_name: str | None
    start_ns: int | None
    end_ns: int | None
    source_ids: list[str]
    apply_sync_anchors: bool
```

Analysis and Review tabs subscribe to same signal.

---

## 8. References

- [ANALYSIS_WORKBENCH.md](ANALYSIS_WORKBENCH.md)
- [DATA_COLLECTION_PROTOCOL.md](../DATA_COLLECTION_PROTOCOL.md)
- [jobs.py](../../libs/python/capture_analysis/capture_analysis/jobs.py)
