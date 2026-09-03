# CaptureSuite licensing

CaptureSuite uses a **split license** so the application stays copyleft while
third parties can ship plugins that wrap proprietary vendor SDKs.

## GPL-3.0 (application)

Covered by the root [LICENSE](LICENSE) (GNU GPL v3):

- `daemon/`
- `libs/cpp/`
- `desktop/`
- `libs/python/capture_session/`
- `libs/python/capture_analysis/`
- `tools/` (except where noted)
- `tests/`
- `cmake/`, root build files

If you distribute a modified CaptureSuite application (daemon, UI, analysis),
you must provide corresponding source under GPL-3.0.

## Apache-2.0 (contract + SDK)

Each of these trees carries its own `LICENSE` (Apache License 2.0) and
`NOTICE`:

| Tree | Purpose |
|------|---------|
| `schemas/` | Protobuf + JSON Schema contracts |
| `libs/python/capture_protocol/` | Generated bindings + thin Python wrappers |
| `libs/python/capture_worker/` | Python worker SDK |
| `workers/stub/` | Minimal C++ worker template |

You may implement plugins against these APIs under any license, including
closed-source wrappers around vendor SDKs. Linking a proprietary SDK into a
**plugin process** that speaks the Apache-licensed protocol does **not** force
that plugin under GPL. Shipping a modified daemon/UI still requires GPL.

## Plugin license freedom

Reference plugins under `plugins/` may use whatever license fits (often
Apache-2.0 for examples; vendor SDK terms still apply to those SDKs). Document
the plugin's license in its `plugin.json` `license` field and `README.md`.

## SPDX identifiers

Source files should carry:

```text
SPDX-License-Identifier: GPL-3.0-only
```

or

```text
SPDX-License-Identifier: Apache-2.0
```

matching the subtree. `tools/check_licenses.py` enforces this in CI.
