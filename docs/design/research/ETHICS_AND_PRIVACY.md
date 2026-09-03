# Ethics and privacy

Research date: **2026-09-01**  
Applies to: surgical/clinical video, gaze/face, retention, cloud.

**Constraint:** No silent cloud upload; raw stays local unless operator exports ([MASTER_SPEC.md](../../../docs/spec/MASTER_SPEC.md)).

---

## 1. Video (camera)

| Topic | Policy |
|-------|--------|
| Retention | Operator-controlled; app does not auto-delete |
| Identifiable imagery | Treat all sealed MKV as sensitive |
| Preview | Same sensitivity as record path |
| Overlay | Processing overlays under `processing/` only — never replace MKV |
| Export | Export wizard warns when leaving machine |
| De-identification | Out of scope V1 — no auto face blur in capture path |

---

## 2. Gaze / face (future)

| Topic | Policy |
|-------|--------|
| Opt-in | Gaze record disabled by default until protocol enables |
| Preview | Optional face blur preview (research) — not record substitute |
| Analysis | Face mesh under `pose/native/` with access same as session ACL |
| Consent | Project metadata field `consent_version` recommended |

---

## 3. Cloud and network

| Topic | Policy |
|-------|--------|
| Telemetry | Opt-in only if ever added; not in V1 |
| Update channel | `settings.update_channel` — no session data in update checks |
| Remote analysis | Operator export only — no built-in upload |

---

## 4. Data honesty (UI)

Always visible when relevant:

- `calibrated: false` / `a.u.`  
- `finalized_recovered`  
- Software-coordinated radar (not HW sync)  
- Teacher labels from AI models (not clinical ground truth)  

See [IA_AND_PRODUCT.md](IA_AND_PRODUCT.md) provenance principles.

---

## 5. IRB / protocol

Recommend `project.json` fields:

- `irb_protocol_id`  
- `consent_version`  
- `data_use_agreement`  

CaptureSuite stores; does not enforce IRB logic.

---

## 6. References

- [POSE_HAND_TEACHER_POLICY.md](POSE_HAND_TEACHER_POLICY.md)
- [OPERATOR_AND_PLUGIN_DOCS_OUTLINE.md](OPERATOR_AND_PLUGIN_DOCS_OUTLINE.md)
