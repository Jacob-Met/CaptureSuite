# Competitive and peer-tool audit

Research date: **2026-09-01**  
Purpose: Inform professional polish without copying consumer UX or sacrificing depth.

Scoring: **0–5** per dimension (5 = best in class for research/lab use).

---

## 1. Scoring dimensions

| Dimension | Meaning |
|-----------|---------|
| **Live density** | Glanceable multi-device health during acquisition |
| **Offline workbench** | In-app analysis depth (plots, scopes, jobs) |
| **Plugin / extensibility** | Third-party or lab-defined tools without fork |
| **Export honesty** | Raw preserved, provenance, gap visibility |
| **Multi-device sync UX** | Honest about what is/isn't hardware-synced |

---

## 2. Peer matrix

| Tool | Domain | Live | Workbench | Plugins | Export | Sync UX | Notes |
|------|--------|------|-----------|---------|--------|---------|-------|
| **Delsys EMGworks / Trigno** | EMG | 5 | 4 | 2 | 4 | 3 | Strong live traces; analysis export-centric |
| **Xsens MVN Analyze** | IMU mocap | 4 | 5 | 2 | 4 | 4 | Excellent offline; weak as generic multimodal hub |
| **Qualisys / Vicon** | Optical mocap | 4 | 5 | 3 | 5 | 5 | Gold standard sync; not radar/EMG native |
| **OpenCap** | Video pose | 2 | 4 | 3 | 4 | 2 | Cloud-optional; video-first |
| **LabChart (ADInstruments)** | General physiology | 4 | 4 | 3 | 4 | 3 | Great traces; not multimodal device orchestration |
| **Infineon Radar SDK / RadarView-class** | Radar | 3 | 3 | 1 | 3 | 2 | Deep radar; no session package model |
| **UrologyMoCap (internal)** | Surgical video pose | 4 | 5 | 1 | 3 | 1 | Excellent pose/hand; not `.mmsession` |
| **CaptureSuite (today)** | Multimodal | 4 | 2 | 1 | 5 | 4 | Strong capture + honesty; thin analysis UI |

---

## 3. Steal list (adapt, don’t copy)

| Source | Steal | CaptureSuite mapping |
|--------|-------|----------------------|
| Xsens / Qualisys | Unified timeline scrubber across modalities | SessionTimeline component |
| Delsys | Per-channel compact/expanded EMG cards | Modality expanded cards |
| LabChart | Gap-aware trace zoom | PyQtGraph sync dashboard |
| OpenCap | Clear “processing job” metaphor with logs | Analysis job inspector |
| Qualisys | Export wizard with format + scope | Review export matrix |
| MVN | 3D orientation preview toggle | IMU native vs graph preview setting |

---

## 4. Reject list (explicit non-goals)

| Pattern | Why reject |
|---------|------------|
| Dashboard-of-cards landing page | Violates research density; Capture tab is already the live surface |
| Purple gradient “AI platform” chrome | Off-brand for lab instrument |
| Web-only analysis | Locked to PySide6 desktop |
| Silent interpolation across gaps | Violates AGENTS core rules |
| Single-modality app shell | Product is multimodal platform |
| Overlay-as-record | Preview ≠ capture path |
| Claiming hardware sync without validation | Radar arrays stay software-coordinated |

---

## 5. Professional polish checklist (mapped to files)

| # | Checklist item | Target implementation |
|---|----------------|----------------------|
| 1 | Product branding, no milestone banner | `app.py`, [DESIGN_SYSTEM.md](../DESIGN_SYSTEM.md) |
| 2 | Light/dark/system theme | `theme.py`, `settings.theme` |
| 3 | Unified session timeline | New `widgets_session_timeline.py` |
| 4 | In-app analysis figures | `screen_analysis.py`, [ANALYSIS_WORKBENCH.md](ANALYSIS_WORKBENCH.md) |
| 5 | Preferences window | `screen_settings.py`, [PRESETS_AND_SETTINGS_UX.md](PRESETS_AND_SETTINGS_UX.md) |
| 6 | Preset library UI (10 types) | `registry.sqlite` + preset editor |
| 7 | Project/protocol create flow | Transport bar + wizard |
| 8 | Per-modality expanded cards | `screen_capture.py`, modality scorecards |
| 9 | Recovery/recovered banners | Review tab + SessionHeader |
| 10 | Provenance chips (units, calibrated) | Analysis inspector + figure captions |
| 11 | Export scope wizard | Review tab |
| 12 | Plugin registry docs | [ANALYSIS_PLUGIN_ARCHITECTURE.md](ANALYSIS_PLUGIN_ARCHITECTURE.md) |

---

## 6. Positioning statement (for docs/marketing)

CaptureSuite is the **session-honest multimodal recorder** with an extensible analysis workbench—not a pose app, not an EMG app, not a radar demo. Depth comes from modality-specific cards and plugin registries, not from hiding advanced controls.

---

## 7. References

- [IA_AND_PRODUCT.md](IA_AND_PRODUCT.md)
- [docs/spec/MASTER_SPEC.md](../../../docs/spec/MASTER_SPEC.md)
