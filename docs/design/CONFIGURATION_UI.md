# Source Configuration and the Setup Surface

How a source's settings are described, rendered, validated, and applied — without the daemon or the UI knowing anything about any vendor. Pins the mechanism the Setup tab and every device milestone build on. Vendor-specific option sets belong in `docs/design/adapters/<vendor>.md`, not here.

## The constraint

Core rule: no vendor-specific logic in core session or storage code. A camera exposes exposure and resolution, a Delsys sensor exposes sampling mode and channel gains, a radar board exposes chirp parameters. If the UI hard-codes forms per vendor, then every new device becomes a UI change, and the daemon becomes a switch statement over plugin IDs.

**Decision: the worker owns its configuration vocabulary and publishes it as a JSON Schema document. The daemon proxies and validates. The UI renders generically.**

Nothing in the daemon or UI ever names a vendor field.

## Round trip

```text
UI --GetConfigSchema(source_id)--> daemon --GetConfigSchema--> worker
UI <-------- schema + current + effective config <-----------  worker
UI --ApplyConfig(source_id, document)--> daemon (validate, state guard) --> worker
UI <----- effective config + coercions + ErrorInfo -----------------------  worker
```

The RPC names are already in the message surface in [PROTOCOL.md](PROTOCOL.md); this fixes their semantics.

### Schemas are per-source and dynamic

A schema is fetched **after** `Connect`, never from static plugin metadata, because the real option set depends on the device in hand: which resolutions this camera reports, how many channels this base station sees. A schema carries a `schema_revision` string, and `ApplyConfig` returns the current revision. A changed revision means the UI refetches, because applying one setting can change what other settings are legal.

## Supported JSON Schema subset

Deliberately small. A worker author needs to know exactly what will render, and an open-ended subset means each new plugin discovers a different set of unsupported keywords at integration time.

| Supported | Notes |
|---|---|
| `type: object` at the root, with `properties` | one level of nesting via `x-capture-group`, not nested objects |
| `type: string` | free text, or a closed set via `enum` |
| `type: integer`, `type: number` | `minimum`, `maximum`, `multipleOf` |
| `type: boolean` | rendered as a toggle |
| `type: array` of a scalar type | fixed-length only, via `minItems` equal to `maxItems`; for per-channel values |
| `enum` with `x-capture-enum-labels` | wire values stay stable while display labels can be readable |
| `title`, `description`, `default` | `title` is the field label, `description` the help text |
| `required` | a missing required field blocks apply |
| `readOnly` | displayed, never editable; for device-reported facts |

Not supported: `oneOf`, `anyOf`, `allOf`, `$ref`, conditional `if`/`then`, patterned properties, nested objects, variable-length arrays. A worker needing conditional structure re-publishes a schema with a new `schema_revision` after the governing field changes, which is the dynamic-schema mechanism already in place and needs no keyword.

### UI hint vocabulary

| Keyword | Effect |
|---|---|
| `x-capture-group` | group label the field appears under; ungrouped fields go to a default group |
| `x-capture-order` | integer sort key within a group |
| `x-capture-units` | unit suffix shown next to the control, for example `Hz`, `ms`, `dB` |
| `x-capture-advanced` | collapsed by default, so common settings stay uncluttered |
| `x-capture-restart-required` | applying this field restarts the device stream; the UI says so before applying |
| `x-capture-enum-labels` | map of enum wire value to display label |

Unknown `x-capture-*` keywords are ignored, so a worker can ship hints a UI does not yet honor without breaking it.

## Validation, in three layers

Each layer exists because the layer above it cannot be trusted for that specific thing.

| Layer | Checks | Why here |
|---|---|---|
| UI | types, ranges, enum membership, required fields, from the schema | immediate feedback while typing; convenience only |
| Daemon | the full schema again, plus session-state guards | the UI is untrusted and may be stale; an invalid document must never reach a vendor SDK |
| Worker | whether the device actually accepts the values | only the device knows its real constraints |

The daemon revalidating is not redundancy. A UI holding a schema from before a `Connect` will happily submit values the device no longer offers, and vendor SDKs handle out-of-range input with anything from an error code to a crash.

State guards, per [OPERATIONS.md](OPERATIONS.md): `ApplyConfig` returns `INVALID_STATE` during `RECORDING`. Configuration is not a live control surface.

## Apply semantics

- **Atomic per source.** The whole document applies or none of it does. A half-applied configuration is a device state nobody can reason about.
- **Failure preserves the previous configuration.** The worker rolls back and reports `ErrorInfo`; lifecycle stays `CONNECTED` rather than advancing to `CONFIGURED`.
- **Requested and effective are reported separately.** A device asked for 60 fps may deliver 59.94; asked for 2000 Hz it may deliver 2048. The reply carries the effective document alongside the requested one, and any field that was coerced is listed explicitly. Silently showing the requested value would mean the session metadata claims a rate the hardware never produced.
- **Success journals `CONFIG_CHANGED`** and stores the configuration snapshot, which is what the restart policy in [STATE_MACHINES.md](STATE_MACHINES.md) re-applies after a worker crash.
- **The snapshot goes into the session package** in `source.json`, as effective values with coercions noted.

## Presets

A source preset is a stored configuration document plus the `schema_version` it was captured against, in the envelope from [OPERATIONS.md](OPERATIONS.md) and stored per [SETTINGS_REGISTRY.md](SETTINGS_REGISTRY.md).

Applying a preset validates it against the device's *current* schema. On mismatch the UI shows exactly which fields are unknown, out of range, or missing, and applies nothing until the operator resolves it. Dropping unknown fields and applying the rest is the behavior most likely to produce a session recorded under settings the operator believes were in effect but were not.

Sessions store full preset content, never a reference, so a session stays interpretable after the preset library changes.

## Rendering rules for the Setup tab

- Group order follows `x-capture-order` on the group's lowest-ordered field; within a group, fields sort by `x-capture-order` then `title`
- Advanced fields collapse behind one disclosure per group
- A dirty form shows what will change and, if any touched field is `x-capture-restart-required`, that the stream will restart
- Read-only device facts render in the same layout as editable fields, visibly non-editable, so device truth and operator intent sit side by side
- A source in a lifecycle state that forbids configuration renders the form disabled with the reason, rather than hiding it — a hidden form looks like a missing feature
