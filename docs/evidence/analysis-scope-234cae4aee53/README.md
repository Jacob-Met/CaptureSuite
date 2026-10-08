# Desktop analysis time scope — issue #53

Owner: `estate-234cae4aee53 / project_production`.

The sealed-session header now lets an operator choose Full session, Checkpoint
section, or an exact Time range before starting an existing analysis job. The
selection is tied to the chosen package and copied into the worker before its
thread starts. The timeline shows the selected interval without hiding recorded
gaps. Cursor buttons fill either time endpoint; decimal input retains integer
nanoseconds. Invalid bounds and commands that do not consume time windows remain
blocked, with an explanation visible to the operator.

This contribution changes five desktop modules, one focused UI test module, the
existing scope design document, its own progress entry, and this evidence folder.
It does not change backend window resolution, job publication, numeric pipelines,
QC, storage, framing, registry, camera, or plugin behavior.

## Source and receiving boundaries

| Boundary | Source |
| --- | --- |
| Original main used for the negative UI control | `72c15d6b623e217291a824e4e4808a385df896a9` |
| Initial production rejected for checkpoint identity | `27b557d58658fa8c76875833f997fa7825216abd` |
| Test-only worker-lifetime correction | `dd8bde3ace41f2c39546dffda2e592d101071bbf` |
| Production independently accepted by the estate lead agent | `36254496e386568de05148db9bd9fa4d69020dd4` |
| Final clean source tested with accepted QC main | `951e3c962f2f57e25656ba8e18d9372db74c4856` |
| Final tested tree | `25c8af5fcea93fa47167afed55a96bcdf8a23b8a` |
| QC main included in that source | `fae29ddcbc0380b7d7e307130093bc5d66bf2f90` |

These are exact local Git objects, retained in the isolated native receiver. The
published commit may have different commit metadata; `receipt.json` identifies
the production bytes, and the source manifest binds the complete tested tree.
Independent receiving here means review and a separate real Qt experiment by the
HAMON estate lead agent, not an external maintainer approval.

The subsequent publication read found main
`e43da3b855475c8aacf815c201fa03eddaeec0f1`, adding the accepted portable storage
fixture isolation. Its only executable changes are C++ test/CMake files; the
desktop, analysis dependencies and Python test inputs remain unchanged. The
publication composition preserves those owner files and the complete upstream
progress log. It does not relabel the earlier focused run as a test of new C++
fixture behavior. `publication-composition.json` records the final comparison.

## Qualification

| Evidence | Result and interpretation |
| --- | --- |
| `baseline.log` / `.xml` | Original main lacks the accessible scope picker: one intended failure, three existing positive controls pass. |
| `composed-first.log` / `.xml` | Initial real Qt/QThread/MCAP receiving: 11 passed, one explicit Windows application-window skip. |
| `admission.log` / `.xml` | 12 focused UI admission/refresh cases pass after exact decimal parsing and invalid-state retention were tightened. |
| `shadow-before.log` / `.xml` | Two record-order variants reproduce the rejected checkpoint identity bug. |
| `shadow-after.log` / `.xml` | The same two identity controls and the ordinary command/package control pass. |
| `peer-checkpoint-before.json` and `peer-checkpoint-after.json` | Independent real Qt negative and accepted rerun, with raw offered options and resolved intervals. |
| `r2.log` / `.xml` | After the test-only worker-lifetime repair: 21 passed, one Windows skip. |
| `final.log` / `.xml` and `final-receipt.json` | Clean composed source: **23 passed, one explicit Windows MainWindow skip**, exit 0. All **724 tracked source hashes** stayed unchanged. |
| `ruff-configured.log`, `spdx.log`, `source-gates.json` | Full repository-configured Ruff command and SPDX enforcement both exit 0. |

The two threaded cases invoke the actual analysis worker, read real MCAP input,
produce features/plots, check requested and resolved job-manifest bounds, inspect
derived sample timestamps, and verify every raw fixture file remains unchanged.
Changing the next UI selection while a worker runs does not change that job's
snapshot. Other cases cover exact conversion, invalid ranges, unsupported
commands, package identity, header refresh, cursor controls, gap visibility, and
the independent owner's analysis failure-note behavior.

The Linux run deliberately skips the complete `MainWindow` case because importing
the supported Windows named-pipe transport requires `msvcrt`. The PR's existing
**Windows Python job must execute that case**. The full Python job and existing
CMake/native integration workflow remain publication acceptance gates. No
physical hardware test or installed release is claimed here.

## Checkpoint identity failure and repair

The backend accepts both checkpoint names and IDs in chronological order. In the
ordinary repeated-name control, selecting `Movement (later-id)` resolves the
intended interval `[4000000003, 10000000005]`. In the rejected source, giving the
earlier checkpoint the name `later-id` made that same UI option silently resolve
to `[1000000001, 4000000003]` instead.

The repair keeps the existing backend owner's resolver unchanged. Before offering
a section, the picker checks which recorded checkpoint that resolver will match.
If a different checkpoint would win, the intended section is absent from
executable options and a visible warning names it and explains the **Time range**
fallback. A normal repeated display name remains usable with its stable ID.

The independent before/after harnesses are retained as `.py.txt` evidence. The
accepted rerun differs only in provenance reporting: it reads the actual Git
head/status and backend hash instead of carrying the original hardcoded source
pin. Fixtures, UI actions, and acceptance assertions are unchanged. The original
picker and premature test cleanup are in `source-controls/`, preserving the
rejected behavior without making those controls part of normal test collection.

## Invalid environment and harness attempts

`first.log` is a partial, invalid attempt: shared tmpfs exhaustion also prevented
complete JUnit/terminal output, and the process exited 120. It is not a pass.

The first frozen broader harness, recorded in `qualified.log` and
`qualified-receipt.json`, exited with signal 11 while leaving all 670 tracked
source hashes unchanged. Its 30-second deadline cancelled a still-active plotting
worker and its five-second cleanup could allow that worker to overlap the next
case. `cancelled-by-first-harness-manifest.json` retains the actual job's
`analysis cancelled` result and partial output inventory.

The test-only correction gives the real job a 120-second guard, continues pumping
the Qt event loop until a cancelled worker has actually finished, and deletes
fixture widgets on the GUI thread. The corrected range job took 36.83 seconds;
the final range job took 42.41 seconds. No production change is credited with
fixing that harness lifetime problem. Both the failed receipt and the corrected
source manifests remain available.

## Reproduce the focused gate

Use the project's Python 3.12 environment with `requirements-ci.txt` installed.
The retained run used actual PySide6 6.11.2, NumPy 2.5.3, MCAP 1.5.0, protobuf
4.25.9, and pytest 9.1.1. It did not substitute a Qt or backend implementation.

```sh
QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1 python -B -m pytest \
  tests/ui/test_analysis_scope.py \
  tests/ui/test_analysis_failure_notes.py \
  tests/ui/test_analysis_workbench.py \
  tests/ui/test_desktop_smoke.py::test_session_timeline_from_fixture \
  -p no:cacheprovider --durations=5 -q
```

`final-receipt.json` retains the exact invocation, temporary directory, duration,
clean Git status checks, and source-manifest hash for the qualified run. The
retained JUnit names its explicit skip. Use a fresh temporary directory with
enough space; do not delete another invocation's fixtures.

## Native custody and artifact integrity

The separate Mac receiver is
`/Users/me/Developer/capturesuite-scope-receiving-234cae4aee53`. It is an isolated
Git clone, not another owner's working tree. Its accepted production checkpoint
was read back clean at `36254496e386568de05148db9bd9fa4d69020dd4`, tree
`b40e693e0fd654dfe74ad60e39cfc76d064b5e2e`.

The original and repaired history are retained as verified native Git bundles:

| Bundle suffix | Bytes | SHA-256 |
| --- | ---: | --- |
| `-27b557d.bundle` | 13851 | `6f6ece9c3ba043b0252c9a89229b065745c44c62c2823d09af40770114d8fb9f` |
| `-3625449.bundle` | 6533 | `2063857a4198c666a118f25922b6d52c431c855cabb8d14bbc4f96fb8332790e` |

The final published source and hosted evidence receive another native checkpoint
after the hosted gates. `artifact-hashes.json` covers this folder's retained
files, excluding the hash inventory itself. Source and artifact checks establish
identity and custody; they do not substitute for the required Windows execution.
