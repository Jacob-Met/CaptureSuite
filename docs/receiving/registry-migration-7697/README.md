# Registry migration transaction receiving — #126

The repair makes a failed registry migration retryable on the same database.
It implements the existing requirement that each forward version runs in its
own transaction. It does not change the registry schema or migration SQL.

- Issue: [CaptureSuite #126](https://github.com/Jacob-Met/CaptureSuite/issues/126).
- Publication parent: `ab17b8c50af9892483b49ce4c125ef28f38eb72c`,
  tree `fe779be8316c3cf677dcf8b12993476db8a87a62`.
- Isolated branch: `fix/registry-migration-atomicity-7697-20261013`.
- [Corrected source](../../../libs/python/capture_session/capture_session/registry.py):
  blob `fcf858d562b4cb361a53abfc39eccaff245b1a81`,
  SHA-256 `aafc6a17d5622ab8f095455a6d3733e0a012ac471c1f34c1c0fec9a25161e367`.
- [Four maintained regression cases](../../../tests/protocol/test_registry_migration_atomicity.py):
  blob `3ca045ebbf90c66bff3549efa40888e71fd92a95`.

## Failure and correction

The original `AppRegistry._migrate` invoked `executescript(sql)` in a connection
context, then inserted the applied version. That context did not start a
transaction for the script's DDL. An injected late first-migration SQL error
left all five tables and two indexes present without a version record. A
normal retry then failed with `table schema_migrations already exists`.

The corrected call is `executescript("BEGIN;\n" + sql)` (the source string
contains a newline escape). The existing connection context now covers the
migration statements and version insert. A failed version rolls back as a
unit; previously committed versions remain available. A valid retry performs
only the still-unapplied version.

The production change consists of that transaction opener and two explanatory
comments. The v1 SQL is byte-identical (SHA-256
`6d4fa2227b8f21523741bd0c526b4f0e21e9d045fd60fa63d59271cb9031e97f`),
and the schema stays at version 1. Open/read-only handling, registry CRUD,
settings and desktop/daemon code are unchanged.

## Receiving results

| Course | Original source | Corrected source |
| --- | --- | --- |
| Independent four-method receiver, Python 3.12.8 / SQLite 3.53.4 | 3 failures, 1 read-only control pass | 4 passes, no errors/skips |
| Four new maintained cases + nine unchanged settings/registry/read-only cases, Python 3.12.8 / pytest 8.4.2 | 4 failures, 9 passes | 13 passes, no errors/skips |
| Same maintained course, ThinkPad Python 3.14.4 / SQLite 3.46.1 diagnostic | 4 failures, 9 passes | 13 passes |
| Ruff 0.14.10 with exact repository configuration, changed source and test only | — | No diagnostics |
| Unchanged repository license checker on the declared package/test/license subset | — | Exit 0, `license check OK` |

The independent receiver was frozen before candidate inspection and uses public
`AppRegistry.open()`/close with real disposable SQLite files. It tests late
script failure, a real trigger refusing the version insert, v2 preservation
when v3 fails, explicit retries, released writer transactions after failed open,
and newer-version read-only preservation. It does not mock transaction calls.
A column-index typo in the receiver was corrected during review before its first
native execution; both inert drafts and that correction history are retained.

## Exact evidence

- [Independent receiving packet](independent-receiving.json):
  Git blob `af802a2fa60a50cbf3d28cd8d8dc04bb93337670`;
  266,062 UTF-8 bytes;
  SHA-256 `df4e6a4b73df5737fa382da628965da56720ca48091f00d2d72a5c4c7f3ea4e5`.
  This unchanged packet occurs once in this tree. Its 30 embedded files retain
  source/test identities, the original and candidate observations, commands,
  complete raw logs/JUnit, frozen receiver chronology, scoped Ruff and reused
  private tool/wheel provenance.
- [Author receiving record](author-receiving.json):
  the original native probe, original/candidate maintained receipts, exact
  runners, scoped license result, parent input guards, ownership checks and
  execution limits.

Every tested source/test/config is guarded before and after execution. The
publication parent has the exact tested package/config/instruction/workflow
blobs. All 13 open PRs were checked for source overlap, including both pages
of #94 and the newly opened #127 evidence handoff; the required progress update
preserves all previous text. The final ref, commit parent/tree, complete leaf
preservation, source identity and exact-head Actions count are read back after
publication and recorded in issue #126.

## Scope and operational limits

These are headless persistence checks. Supported runtime evidence is Python
3.12.8 on macOS arm64; the ThinkPad's Python 3.14.4 is explicitly diagnostic.
The exact small package/test/config subset does not represent a full repository
checkout, Windows desktop/daemon gate, hardware run or installed delivery.

Synthetic migration fixtures demonstrate SQLite rollback and retry, not actual
disk exhaustion, process-crash or power-loss recovery. The fix prevents new
partial migrations; it does not automatically repair a registry already left
partial by an older build.

During final license-runner preparation, the ThinkPad filesystem reported no
space and left a verified empty file that was never executed. A later read-only
capacity check found space available without any cleanup by this worker. The
unchanged runner then completed successfully; no correctness tests were rerun.
The attempted Mac fallback stopped on a read-route timeout before any writes.

Publication is branch plus issue under the standing Actions hold. No PR, merge,
workflow change/dispatch or installation is part of this result. The commit
carries `[skip ci] [skip actions]`; the final issue handoff records the actual
post-publication verification rather than treating those markers as proof.
