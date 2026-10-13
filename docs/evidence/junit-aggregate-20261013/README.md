# JUnit aggregate-count receiving

The Python test receipt could accept a `testsuites` root whose declared totals
contradicted its child cases. The reader already checked each `testsuite`;
it omitted the corresponding check on optional root attributes.

The repair adds five lines to `summarize()` in `tools/run_ci_tests.py`.
Present root `tests`, `failures`, `errors` and `skipped` counts must now
match totals calculated from the case evidence. Invalid integer declarations
are refused by the existing error path. Omitted aggregate attributes remain
supported. The receipt schema, case counting, single-suite support, process
exit checks, source binding and 300-second test-process deadline are unchanged.

## Source and ownership

- Accepted source: `ab17b8c50af9892483b49ce4c125ef28f38eb72c`.
- Original runner Git blob: `b5717e9f605ee7de6474cf4d3ecba45e5eaa44ba`.
- Original runner SHA-256: `a35a6bb9b5293db46201857a5590b45ad77243f646a5cf729112f8130710d776`.
- Repaired runner SHA-256: `54ae0026ad0f90969c63815ffbbadcf84e47a70cf921fb7115d1b95abe9fe445`.
- Identical maintained test bytes used for both runs, SHA-256:
  `286847068b472032815f6378c6e2407264ee8ac79a80ddf37076d0de595c08cc`.

All 13 open PR filename lists were inspected. PR71 and PR94 change only
`main()`'s timeout in this runner; their proposed 600-second timeout is not
part of this change. Their source remains separately owned. No open PR
changed `tests/protocol/test_ci_evidence.py`.

## Actual receiving

Both runs used existing CPython 3.12.2 on Windows 11 and the same maintained
test file: 21 inherited cases plus 19 aggregate cases. Source came from
explicit sparse fixture directories with the accepted `pyproject.toml`,
`tests/conftest.py` and license checker. No dependency was installed.

| Source | Passed | Failed | Errors | Skipped | Process exit |
| --- | ---: | ---: | ---: | ---: | ---: |
| Original runner | 24 | 16 | 0 | 0 | 1 |
| Repaired runner | 40 | 0 | 0 | 0 | 0 |

The 16 original failures cover four contradictory root declarations and
malformed, empty or negative counts for each of the four aggregate fields.
Three multi-suite controls preserve complete, partial and omitted root
counts. Existing process-exit, empty-suite, skipped-test, failure/error,
unsupported-XML, size, single-suite, source-snapshot and environment
allowlist cases remain in the same run.

The command was `python -B -m pytest -q -p no:cacheprovider
tests/protocol/test_ci_evidence.py`, with fresh explicit `--basetemp` and
`--junitxml` paths. `PYTHONDONTWRITEBYTECODE=1` and
`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` were set for both runs. Exact commands,
paths, completion codes, source manifests, output hashes and runtimes are
retained in [VALIDATION.json](VALIDATION.json). All five fixture source files
were byte-identical before and after each run.

Scoped Ruff on the runner and maintained test file passed. The repository
license checker's `check_spdx(enforce=True)` returned no errors on the sparse
source fixture. This was not the full repository license-structure check.

Raw original and candidate stdout, stderr and JUnit XML are retained beside
the receipt. Empty stderr files are intentional. The receipt's SHA-256 is
`649d50ab63d528413fc2d479e7abd230d6a2f1e54d1c6da30f2748ea32d4b7cc`.
The directory's attributes preserve the original Windows line endings.

## Independent review

Reviewer `/root/engine_research` read the frozen production and maintained
test blobs, reconciled the author receipt and verified that the complete
production diff is exactly the five-line aggregate check. A separately
authored 13-case `summarize()` matrix ran under Windows CPython 3.12.2:
the original matched 6/13 expected outcomes and the candidate matched 13/13.
Valid complete, optional and single-suite receipts remained byte-equivalent.
The reviewer checked input hashes and preservation, and both production
files remained unchanged.

[Independent receipt](independent-receipt.json) SHA-256:
`c1222e9aa20879d2807b436063b6b1f2fb496591d9a5b9ee0d185a66c4d72560`.
The [exact review driver](independent-review.py.txt) is retained as text with
its original paths and bytes. This review accepted bounded source
publication; it did not rerun the 40-case author suite or qualify a live app.

## Limits

This qualifies the selected receipt tests and the bounded source change.
It does not qualify the complete Python suite, C++ or daemon integration,
desktop behavior, physical acquisition, scientific or clinical validity.
No application data, device stream or retained recording was opened.

GitHub Actions remain unrun under the standing no-Actions instruction.
Publication uses an isolated non-release branch and skip markers; no workflow
definition is changed and no Actions dispatch is requested. Full integration
and any separately required receiving remain distinct from this local result.
