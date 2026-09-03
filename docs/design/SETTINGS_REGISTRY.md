# Settings and the Application Registry

Concrete schemas for the three persistence scopes named in [OPERATIONS.md](OPERATIONS.md) and [`PRESETS_SETTINGS.md`](../../docs/spec/PRESETS_SETTINGS.md). Pinned now because the UI and the preset library both need them before any further device milestone.

## Ownership

**Decision: the desktop app is the sole writer of `settings.json` and `registry.sqlite`. The daemon reads neither.**

Everything the daemon needs arrives as an explicit RPC parameter — `CreateSession` carries the package path, `ApplyConfig` carries the configuration document. The daemon has no configuration file at all.

This keeps the dependency arrow pointing one way. If the daemon read UI settings, a UI writing a settings file would silently change acquisition behavior, and a headless or CLI-driven recording would behave differently from a UI-driven one for reasons invisible in either. Environment variables (`CAPTURE_SESSION_PARENT` and friends) remain for tests and development only, and are documented as such rather than as a configuration surface.

**The registry is never authoritative.** It is a convenience index: recent sessions, remembered aliases, the preset library. Session packages embed their full identity chain and full preset content, so deleting `registry.sqlite` loses conveniences and no data. Anything that would become unrecoverable if the registry were deleted is in the wrong place.

## `%LOCALAPPDATA%\CaptureSuite\settings.json`

Versioned by `settings_schema_version` (semver, starts `1.0.0`) and written with the same atomic temp-file-and-rename rule as session metadata. Unknown keys are preserved and written back unchanged, so an older build cannot strip a newer build's settings.

| Key | Type | Default | Notes |
|---|---|---|---|
| `settings_schema_version` | string | `1.0.0` | |
| `theme` | enum | `system` | `system`, `light`, `dark` |
| `window_geometry` | object | null | per monitor-configuration fingerprint, so docking a laptop restores the right layout |
| `active_workspace_preset_id` | string | null | resolves in `registry.sqlite` |
| `active_hotkey_preset_id` | string | null | same |
| `global_hotkeys_enabled` | bool | `false` | off by default; a global hotkey affects other applications |
| `recent_projects` | array | `[]` | max 10, most recent first |
| `last_session_parent_path` | string | null | prefills `CreateSession`, never read by the daemon |
| `last_export_path` | string | null | |
| `preview_enabled_default` | bool | `true` | |
| `preview_rate_limit_hz` | number | `15` | UI-side cap on top of each source's own rate |
| `preview_grid_columns` | integer | `0` | 0 means auto |
| `preview_kind_styles` | object | `{}` | optional `"graph"` vs `"native"` for `ORIENTATION` / `MATRIX_2D` previews; native (cube / heatmap) remains the default |
| `audible_alerts_enabled` | bool | `true` | drives the `CRITICAL` alert sound from RECOVERY.md |
| `update_channel` | enum | `stable` | `stable`, `beta` |
| `log_level` | enum | `info` | desktop process only |
| `confirm_stop_always` | bool | `true` | cannot disable the daemon-side token; UI-side second confirmation only |

`confirm_stop_always` is a UI preference layered on top of the protected-Stop token, which is enforced in the daemon and cannot be turned off from settings. A setting must never be able to weaken an operator-safety guarantee.

Nothing secret is stored here. Delsys credentials live in Windows Credential Manager via DPAPI, per [OPERATIONS.md](OPERATIONS.md).

## `%LOCALAPPDATA%\CaptureSuite\registry.sqlite`

Pragmas: `journal_mode=WAL`, `foreign_keys=ON`, `synchronous=NORMAL`.

`NORMAL` rather than the journal's `FULL` on purpose. Losing the last recent-sessions row to a power cut costs a menu entry; the session journal has different stakes and pays for `FULL`.

```sql
CREATE TABLE schema_migrations (
  version      INTEGER PRIMARY KEY,
  applied_utc  TEXT NOT NULL
);

-- Devices seen on this machine. Keyed by hardware identity, never by alias.
CREATE TABLE devices (
  stable_device_key TEXT PRIMARY KEY,
  plugin_id         TEXT NOT NULL,
  vendor            TEXT,
  model             TEXT,
  serial            TEXT,
  friendly_name     TEXT,          -- as reported by the device or OS
  alias             TEXT,          -- operator-assigned, display only
  role              TEXT,          -- operator-assigned logical slot
  first_seen_utc    TEXT NOT NULL,
  last_seen_utc     TEXT NOT NULL,
  last_source_id    TEXT,
  notes             TEXT
);
CREATE INDEX devices_by_plugin ON devices(plugin_id);

-- The preset library. One row per preset, of any type.
CREATE TABLE presets (
  preset_id          TEXT PRIMARY KEY,
  preset_type        TEXT NOT NULL,
  name               TEXT NOT NULL,
  schema_version     TEXT NOT NULL,
  preset_version     INTEGER NOT NULL DEFAULT 1,
  description        TEXT,
  compatibility_json TEXT NOT NULL DEFAULT '{}',
  content_json       TEXT NOT NULL,
  created_utc        TEXT NOT NULL,
  updated_utc        TEXT NOT NULL,
  builtin            INTEGER NOT NULL DEFAULT 0
);
CREATE UNIQUE INDEX presets_type_name ON presets(preset_type, name);

-- Convenience index of packages this machine has touched.
CREATE TABLE recent_sessions (
  package_path     TEXT PRIMARY KEY,
  session_id       TEXT NOT NULL,
  project          TEXT,
  participant      TEXT,
  visit            TEXT,
  state            TEXT NOT NULL,
  duration_ns      INTEGER,
  created_utc      TEXT NOT NULL,
  finalized_utc    TEXT,
  last_opened_utc  TEXT NOT NULL
);

CREATE TABLE plugin_states (
  plugin_id      TEXT PRIMARY KEY,
  plugin_version TEXT,
  enabled        INTEGER NOT NULL DEFAULT 1,
  last_seen_utc  TEXT,
  last_error     TEXT
);
```

`devices.stable_device_key` is the hardware key — for cameras, the Media Foundation symbolic link, per [VIDEO_PIPELINE.md](VIDEO_PIPELINE.md). Aliases are a separate, nullable column precisely so identity and label can never be confused: matching on an alias would let two different devices inherit each other's history.

`recent_sessions.package_path` as the primary key means a moved package appears as a new row rather than a stale one. The row is an index entry, and the package remains self-describing regardless.

### Preset types

`preset_type` is one of the ten from [`PRESETS_SETTINGS.md`](../../docs/spec/PRESETS_SETTINGS.md), stored as a string rather than an integer so a database dump is readable:

`device`, `naming`, `anatomical_mapping`, `spatial_layout`, `radar_array`, `capture`, `checkpoint_protocol`, `hotkey`, `workspace`, `export`

Workspace layouts and hotkey maps are presets, not settings keys, which is why `settings.json` stores only the *active* preset ID for each. Named, shareable, versioned layouts and hotkey sets were the requirement; a settings blob would give exactly one of each per machine.

`content_json` is validated against the schema for its `preset_type` on read. An unparseable or incompatible preset is surfaced to the operator and skipped, never silently repaired — a half-applied capture preset would mean recording under settings nobody chose.

### Migrations

`schema_migrations` holds applied versions; migrations are forward-only, each in its own transaction, applied on app start before any read. A registry at a *newer* version than the running build is opened read-only, with a banner, rather than downgraded. Because the registry is non-authoritative, read-only degradation is always an acceptable outcome here.

## Project scope

Project settings live in a `project.json` inside the project folder, carrying the project metadata schema, naming conventions, checkpoint protocol templates, and validated device layouts. Same versioning and atomic write rules.

Sessions embed their full identity chain, so a session inside a project folder does not depend on `project.json` to be interpretable. The project file is where defaults for *new* sessions come from, not where existing sessions get their meaning.
