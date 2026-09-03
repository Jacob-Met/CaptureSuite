# Presets and settings UX

Research date: **2026-09-01**  
Source of truth for keys: [SETTINGS_REGISTRY.md](../SETTINGS_REGISTRY.md), [PRESETS_SETTINGS.md](../../../docs/spec/PRESETS_SETTINGS.md).

**Constraint:** Desktop sole writer of `settings.json` and `registry.sqlite`; daemon reads neither.

---

## 1. Preferences window IA

```
Preferences
├── Appearance
│   ├── Theme (system / light / dark)
│   └── Density (comfortable / compact)
├── Capture
│   ├── Preview rate limit
│   ├── Preview grid columns
│   ├── Preview kind styles (graph vs native)
│   └── Confirm stop (UI layer)
├── Alerts
│   ├── Audible alerts
│   └── (future) spoken checkpoint names
├── Hotkeys
│   ├── Active hotkey preset
│   ├── Editor…
│   └── Global hotkeys enable
├── Workspace
│   ├── Active workspace preset
│   └── Multi-monitor restore
├── Data & privacy
│   ├── Last paths
│   └── Local plugins enable
└── Advanced
    ├── Log level
    └── Update channel
```

---

## 2. Settings key inventory → UI

| Key | Preferences section | Widget |
|-----|---------------------|--------|
| `theme` | Appearance | Combo |
| `window_geometry` | (implicit) | saved on close |
| `active_workspace_preset_id` | Workspace | preset picker |
| `active_hotkey_preset_id` | Hotkeys | preset picker |
| `global_hotkeys_enabled` | Hotkeys | checkbox (default off) |
| `preview_rate_limit_hz` | Capture | spinbox |
| `preview_grid_columns` | Capture | spinbox (0=auto) |
| `preview_kind_styles` | Capture | per-kind combo |
| `audible_alerts_enabled` | Alerts | checkbox |
| `confirm_stop_always` | Capture | checkbox |
| `log_level` | Advanced | combo |
| `update_channel` | Advanced | combo |
| `recent_projects` | (Home) | list |
| `last_session_parent_path` | Data | path label |
| `last_export_path` | Data | path label |

---

## 3. Ten preset types — UX pattern

| preset_type | Editor | Apply moment |
|-------------|--------|--------------|
| `device` | Setup tab (exists) | ApplyConfig |
| `naming` | Project wizard | CreateSession |
| `anatomical` | Analysis Mappings | Analysis job |
| `spatial` | Radar array editor | CreateSession / Setup |
| `radar_array` | Array editor | Record start → arrays.json |
| `capture` | Capture defaults | CreateSession |
| `checkpoint_protocol` | Protocol wizard | CreateSession |
| `hotkey` | Preferences | immediate |
| `workspace` | Layout menu | immediate |
| `export` | Review export wizard | export |

**Common pattern:**
1. List presets from `registry.sqlite`
2. Validate against current schema revision
3. Show compatibility warnings
4. Duplicate / rename / delete
5. Export preset JSON for lab sharing

---

## 4. Hotkey editor

| Feature | Spec |
|---------|------|
| Conflict detection | Highlight duplicate bindings |
| Contexts | global / capture / analysis |
| Protected keys | Stop token not rebindable at daemon level |

---

## 5. Preset validation UX

When schema revision mismatch:
- Block apply with clear message: “Preset built for camera.gstreamer/3, device is /4”
- Offer “open in read-only” for diff

Sessions store **full preset snapshot** — not a reference id alone.

---

## 6. References

- [DESIGN_SYSTEM.md](../DESIGN_SYSTEM.md)
- [IA_AND_PRODUCT.md](IA_AND_PRODUCT.md)
