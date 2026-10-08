# PR87 Python diagnostic follow-up

The first supported Windows Python gate at head `33c6fb3409970941521bd37d236ddda4d3bed581` timed out at the existing 300-second deadline. Its process exit, JUnit hash and test counts are null. Quiet output reached 91% plus 12 progress symbols without an assertion failure, which does not establish a passing suite or identify the active test.

The separate C++ job in the same run passed all 30 CTests and six native integration cases. Current main `a2c89957` separately passed 608 Python tests with six existing missing-daemon skips in 227.34 seconds. The same runner image and dependency versions were installed. That control is context, not qualification of this contribution.

The successor changes only `tools/run_ci_tests.py` reporting: `-q` becomes `-vv`, with `--durations=20`. It retains the complete selected suite, existing kill-test exclusion, JUnit output, 300-second timeout, source snapshots and all acceptance rules. Product source, all test assertions and the four-line feature-order repair remain unchanged. A timeout remains unaccepted.

The wrapper changes from SHA-256 `08a9d4786a6e768e0914ac5490d780c64c07f920b790dd16c5e0740bda9c2ac2` to `a35a6bb9b5293db46201857a5590b45ad77243f646a5cf729112f8130710d776`; reversing only the two argument edits restores its exact original bytes. The runtime patch was independently reviewed by the coordinating root. Project-configured Ruff passed. An initial detached-path Ruff invocation selected non-project rules; its five unrelated findings and the corrected invocation are retained without source fixes.

`first-ci-evidence.tar.gz` preserves complete decoded job logs, API artifact metadata, extracted receipts and both diagnostic sources. `manifest.json` binds all members and the archive; every member was reopened and byte-compared. The first extraction used the Python schema for the native C++ receipt and omitted that receipt; both the original extraction and explicit corrected v2 are retained. Neither alters the raw logs.

Hosted artifact archives were not downloaded or inspected because the earlier normal-download CDN refusal remains respected. The C++ receipt reports a dirty build checkout that remained unchanged during its tests; the complete source-manifest artifact was not retrieved.

This packet precedes the successor diagnostic gate and claims no result for it. Native nearest-feature receiving remains separately recorded in the parent packet: the same 17 controls change from 6 passing/11 failing on baseline to 17 passing on the repair, plus 14 inherited cases. No product replay occurred merely to change diagnostic reporting.
