# Recorded-gap reader correction

Issue [#111](https://github.com/Jacob-Met/CaptureSuite/issues/111) fixes one reader behavior:
a nonblank malformed JSON row in `gaps.jsonl` was silently omitted. The reader
now refuses that summary with its existing local `SessionPackageError`, naming
the file and physical line. Nonobject JSON gets the same contextual error
instead of an incidental attribute error. Existing valid row parsing is unchanged.

The contribution is based on commit `3960c0c756cd4e9facbde0d76eaaa3c31ab7c167`.
Production source changes only `_load_gaps_jsonl` in
`libs/python/capture_session/capture_session/package_reader.py`.
The new maintained tests are `tests/test_package_reader_gaps.py`; PROGRESS is append-only.

## Actual component result

| Exact variant | Process exit | Tests | Passed | Failed | Errors | Skipped |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Original `91fbf913c5af8489968425d7ceac51c04233d3e0` | 1 | 11 | 4 | 2 | 5 | 0 |
| Candidate `cdfba8a26736856683ea865b9df67b36ad120e40` | 0 | 11 | 11 | 0 | 0 | 0 |

Both runs used CPython 3.12.14 on Linux, bytecode disabled, with the explicit
`timeout --signal=TERM --kill-after=2s 20s` outer deadline. Each variant ran
exactly once. Full original failure/error tracebacks remain in
[original/result.json](original/result.json); candidate outcomes are in
[candidate/result.json](candidate/result.json). Exact JSON inputs and complete
command/tool outputs are retained alongside them. The tool's nonzero original
exit is a real failing baseline, not a passing product result.

Four ordinary cases cover absent, empty and blank optional files plus valid
camelCase/snake_case/default rows, row order, source fallback, negative/zero times,
exact integers above 2^53, duration and open/closed counts. The other seven
require contextual reader errors for malformed middle/tail records and
null/array/number/boolean/string rows. Blank physical lines count toward errors.

## Receiving boundary

The test fixture supplies read-only in-memory Path operations. The actual reader,
JSON decoder, gap construction, error handling and summary code run unchanged
except for the candidate production delta. Package text is compared unchanged
in every test's `finally`. This is a Python component qualification; physical
filesystem behavior, package initialization, Windows and Qt were not exercised.

Existing Review catches the reader exception and displays its message. That
handler does not clear old cards or disable export, so this change does not claim
a complete UI reset. Producer/recovery logic, schema/value coercions, optional
metadata handling elsewhere and all capture/export/hardware ownership remain
outside the contribution.

## Provenance

[frozen/expectations.json](frozen/expectations.json) and the maintained tests were
frozen before candidate exposure. The first test source, retained as
[frozen/tests-before-serialization.py](frozen/tests-before-serialization.py),
was never executed. The final tests only made JSON serialization explicit so
all eleven input maps match the frozen literal reference byte-for-byte.

The author privately prepared the patch after those immutable expectations but
before baseline execution. Root reviewed expectations blind to candidate content.
The earlier stronger claim that the patch was not yet authored is preserved,
together with its explicit correction in
[root/candidate-admission.json](root/candidate-admission.json). No expectations
were changed after observing the original, and no original run was repeated.

[qualification.json](qualification.json) binds all exact source and receipt pins.
[run_component.py](run_component.py) is the retained small loader; its isolated
package namespace intentionally does not execute the package initializer. The
complete invocation and input are in each variant's `execution.json` and
`input.json`. No branch/ref, PR, Actions, installed application or deployment
claim is made by this detached contribution.
