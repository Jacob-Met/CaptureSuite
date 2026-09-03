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

1. Load `events/checkpoints.json`.
2. Find checkpoints tagged with `section=<name>` or preset protocol mapping.
3. Resolve `t_start` = first checkpoint in section, `t_end` = next section start or session end.
4. Open gaps in range remain in gap_mask — never filled.

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

SessionHeader widgets emit `ScopeSelection` dataclass:

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
