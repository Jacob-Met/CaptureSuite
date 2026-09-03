# Prompt: LSL-only device (no custom plugin)

```text
Integrate a Lab Streaming Layer device into CaptureSuite without a vendor plugin.

Device / LSL stream:
- Stream name / type / channel count / nominal rate: […]
- Does it already publish an LSL outlet? [yes/no — if no, prefer vendor plugin or a thin LSL forwarder]

Do:
1. Confirm plugins/lsl_bridge is discoverable and pylsl is installed
2. Document required LSL type/name filters in a short note under
   docs/design/adapters/<device_slug>_lsl.md (discovery + timestamp honesty)
3. Configure the bridge via ApplyConfig (name_filter / type_filter / chunk_size)
4. Verify generic.numeric_batch/1 analysis path (numeric.basic.v1) is enough; if not,
   use the analysis-schema prompt
5. Do NOT fork lsl_bridge for one device unless filters are insufficient

Verify: daemon lists lsl.* sources; rehearsal preview; short record; QC job runs.

Refs: docs/plugins/03_lsl_bridge.md, plugins/lsl_bridge/
```
