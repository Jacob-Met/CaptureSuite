# Operator and plugin documentation outline

Research date: **2026-09-01**

---

## 1. Documentation layers

| Layer | Audience | Location | Update trigger |
|-------|----------|----------|----------------|
| Operator manual | Lab techs, surgeons | `docs/operator/` (new) | UI change per release |
| Design specs | Engineers | `docs/design/` | Architectural decision |
| Research notes | Architects | `docs/design/research/` | Pre-implementation research |
| Plugin author guide | Lab devs, partners | `docs/plugins/` (new) | Registry schema change |
| API / protocol | Integrators | `docs/design/PROTOCOL.md`, protos | IPC change |
| Runbooks | Support | `docs/runbooks/` (new) | Incident patterns |

---

## 2. Operator manual (proposed TOC)

1. Introduction — what CaptureSuite is / is not  
2. Quick start — quick capture vs protocol capture  
3. Capture tab — rail, timeline, focus, grid  
4. Setup — device config, presets  
5. Recording — preflight, rehearsal, checkpoints, stop  
6. Review — integrity, recovery, export  
7. Analysis — jobs, scope, figures  
8. Honesty — gaps, units, software-coordinated radar  
9. Troubleshooting — daemon, disk, workers  
10. Glossary  

Screenshots in light + dark theme.

---

## 3. Plugin author guide (proposed TOC)

1. Philosophy — raw immutable, schema versioned  
2. Acquisition plugins — [ACQUISITION_PLUGIN_CONTRACT.md](ACQUISITION_PLUGIN_CONTRACT.md)  
3. Analysis plugins — [ANALYSIS_PLUGIN_ARCHITECTURE.md](ANALYSIS_PLUGIN_ARCHITECTURE.md)  
4. Manifest reference — [schemas/analysis_plugin_manifest.schema.json](schemas/analysis_plugin_manifest.schema.json)  
5. Add a feature walkthrough (5-file example)  
6. Testing requirements — analytic fixtures  
7. Publishing — entry points + local enable  
8. Vendor spike checklist — [VENDOR_SPIKE.md](../VENDOR_SPIKE.md)  

---

## 4. Test strategy for plugins

| Level | Requirement |
|-------|-------------|
| Unit | Formula/extractor on synthetic data |
| Integration | mini_session or generated MCAP |
| Regression | Frozen parquet hash optional |
| Hardware | Tagged `hardware_validated` in manifest |

Same bar as [tests/analysis/test_phase_b_features.py](../../tests/analysis/test_phase_b_features.py).

---

## 5. In-app help

| Surface | Content |
|---------|---------|
| ? on health cards | Modality scorecard excerpt |
| Setup schema | `x-capture-description` from JSON Schema |
| Analysis job | Link to operator manual section |

---

## 6. References

- [ETHICS_AND_PRIVACY.md](ETHICS_AND_PRIVACY.md)
- [AGENTS.md](../../../AGENTS.md)
