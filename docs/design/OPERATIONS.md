# Operations: Logging, Diagnostics, Settings

## Structured logging

spdlog in C++, stdlib `logging` in Python, both emitting JSON Lines. One log file per process under the session's `logs/` directory while a session is open, otherwise under `%LOCALAPPDATA%\CaptureSuite\logs\`.

Rotation: 64 MiB per file, 5 files retained per process.

### Required fields

Every record carries these keys. Correlation IDs are what let a daemon log and four worker logs be merged into one timeline.

| Field | Notes |
|---|---|
| `ts_utc` | ISO 8601 with milliseconds |
| `qpc_ns` | monotonic timestamp, for ordering across processes |
| `level` | `trace`, `debug`, `info`, `warn`, `error`, `critical` |
| `component` | `daemon`, `worker.camera`, `desktop`, and so on |
| `pid` | |
| `event` | stable machine-readable identifier, for example `gap_opened` |
| `msg` | human-readable text |
| `session_id` | null when no session is open |
| `source_id`, `stream_id` | null when not source-specific |
| `seq` | sequence number when the record concerns a specific datum |

Arbitrary additional key-value pairs are permitted and encouraged. `event` values are treated as API: renaming one is a breaking change for log analysis.

### Level discipline

- `info` for lifecycle transitions and operator actions
- `warn` for anything that degrades data quality without stopping capture, including every overload and gap
- `error` for a failed source or failed write
- `critical` only for conditions threatening data already recorded
- Never log per-sample or per-frame at `info` or above; per-datum detail is `trace` and off by default

## Diagnostic bundle

`tools/diagnostic_bundle` produces a single zip for support. It excludes raw participant data by default.

Included: logs, `manifest.json`, `integrity.json`, a journal event summary, `stream.json` and `source.json` descriptors, clock mappings, gap and overload lists, preset snapshots, version and SDK provenance, machine profile (CPU, RAM, disk model, free space), and any recovery reports.

Excluded unless `--include-raw` is passed explicitly: MCAP segments, video segments, anything under `processing/`.

Participant identifiers are replaced with the participant GUID unless `--include-identifiers` is passed. The bundle prints a manifest of what it included so nobody has to guess what they are about to share.

## Persistent settings

Three scopes, per [`PRESETS_SETTINGS.md`](../../docs/spec/PRESETS_SETTINGS.md).

| Scope | Location | Contents |
|---|---|---|
| Machine and user | `%LOCALAPPDATA%\CaptureSuite\settings.json` | theme, window and monitor layout, recent projects, last paths, preview preferences, update channel, hotkeys |
| Application database | `%LOCALAPPDATA%\CaptureSuite\registry.sqlite` | known device registry, preset library, recent sessions, plugin states, applied schema migrations |
| Project | inside the project folder | project metadata schema, naming conventions, protocol templates, validated device layouts |

Secrets, specifically Delsys API credentials, live in the Windows Credential Manager via DPAPI. They are never written to settings, never logged, and never included in a diagnostic bundle.

Settings files are versioned with their own `settings_schema_version` and follow the same atomic write rule as session metadata.

## Preset envelope

Every preset, regardless of type, carries: `preset_id`, human `name`, `schema_version`, `preset_version`, `created_utc`, `updated_utc`, `description`, and compatibility metadata. Sessions store the full preset content, not a reference, so a session remains interpretable after the preset library changes.

## Operator safety enforced by the daemon

These are daemon behaviors, not UI conveniences. A stale or malicious UI cannot bypass them.

| Rule | Enforcement |
|---|---|
| Stop is protected | `Stop` requires a confirmation token issued by a prior `RequestStop`; a bare `Stop` is rejected |
| Only the operator stops a recording | no disk, source, worker, or UI condition ends a session; see STATE_MACHINES.md |
| Dangerous settings locked while recording | `ApplyConfig` and `SelectSources` return `INVALID_STATE` during `RECORDING` |
| Checkpoint is never delayed | timestamp is taken on arrival, before naming; naming is a separate `UpdateCheckpoint` |
| Checkpoint moves are audited | timestamp changes require a reason and append a revision record |
| Updates never during capture | the updater refuses to run while a session is not `IDLE` or `FINALIZED` |

## Alerts

Three levels, matching [`UI_UX.md`](../../docs/spec/UI_UX.md): `INFO`, `WARNING`, `CRITICAL`. Alerts originate in the daemon or workers and are delivered as events, so every client sees the same state.

Alerts are acknowledgeable. Acknowledgement affects operator attention only. It never alters the journal, the gap record, or the integrity manifest.

**Decision: acknowledgement is daemon-held state, not UI-local.**

`AcknowledgeAlert(alert_id)` is a control RPC. The daemon marks the alert acknowledged, includes `acknowledged` in `GetSessionView`, and emits the updated `Alert` as an event so every connected client converges. Acknowledgement is session-scoped and discarded when the session closes.

Holding it in the UI instead would mean a second operator screen keeps flashing a warning the first operator already handled, and a UI restart resurrects every acknowledged alert mid-session. The state is not journaled, because it is attention bookkeeping and not a fact about the data.

An acknowledged alert whose underlying condition is still true re-raises when the condition escalates — acknowledging a `WARNING` disk alert does not suppress the `CRITICAL` that follows it. Acknowledgement silences a notification, never a condition.
