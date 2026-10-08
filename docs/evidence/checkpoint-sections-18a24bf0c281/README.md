# Receiving captured checkpoint sections

## Result

Selecting a captured checkpoint now analyzes the interval that checkpoint closes. The original resolver selected the following interval, or the trailing interval after the final checkpoint. The correction is limited to `checkpoint_section_window` in `capture_analysis/windows.py` and preserves the existing timestamp, gap, loader, pipeline, job, and export contracts.

The same frozen test file produces **25 failures and 5 passes on the original implementation**, then **30 passes on the corrected implementation**. Ten actual CLI invocations per implementation receive real synthetic protobuf MCAP data. The candidate also passes **19 existing QC, feature, and stream-gap tests**, scoped Ruff, and the existing license checker. Both test runs retain two protobuf deprecation warnings; no warning was suppressed.

Independent receiving is preserved separately in [the future-isolation review](../checkpoint-future-isolation-18a24bf0c281/README.md). Its different, four-package experiment passes all **26 checks** on this same production blob: moving a later checkpoint and changing later samples leave the selected earlier section unchanged, while changing a sample inside that section changes its feature output. That review does not reuse this author's 30-test suite.

## Source and ownership

| Boundary | Exact identity |
| --- | --- |
| Receiving repository | `Jacob-Met/CaptureSuite`, issue #54 |
| Pinned public main | `72c15d6b623e217291a824e4e4808a385df896a9` |
| Original complete tree | `221cf5c7bb3c3392a7c4186ba0bcf5a8664135d1` |
| Local baseline with that exact tree | `8076b56c99dbf4083fd23a02e4d761d309ecfc40` |
| Frozen test commit | `a0d5a89ca4117a5b432ae816929c344500707385` |
| Production correction and decision | `4fcd0aa4319b6594af637af8644c187fcbff3cf5` |
| Original windows Git blob | `80bea6bd69365a48c5b204c26d054b8ae179437a` |
| Corrected windows Git blob | `aaafd8db78f82a5a56178135dbed5bfd4f45c634` |
| Corrected windows SHA-256 | `5cf401b7b7d201225c966b804cfff39c3f6d59669da7e488dd68c4253a829c32` |
| Frozen test SHA-256 | `f08db026af80f802b0c8a491095e86bcd3436945def56f0d2f4899e2c22c368f` |

All 668 original Git blobs were verified during intake. Native baseline and candidate each contain those authored paths plus the same new test. Full before/after inventories remain in the native archives; all **669 files** were rechecked after execution. Only `windows.py` differs between the two executed source trees. The analysis decision and progress text are documentation changes bound to the local commits, not native execution dependencies.

The Git archive applied the repository's CRLF checkout rules to eight Windows scripts. Intake retained that first strict raw-byte mismatch, then verified that each CRLF-to-LF conversion recovered the exact canonical Git blob. Two historical evidence logs were also retained as their original Git blobs when creating the local baseline index. The resulting local tree exactly matches public main; these are source-materialization details, not product test failures. See [source-intake.json](source-intake.json).

The [unchanged-helper receipt](helper-custody.json) proves the entire prefix before the checkpoint resolver and the helper tail following it are byte-identical. The existing stream-gap owner's code is preserved. Native UI scope issue #53, saved-job history #55, numeric analysis #49, job provenance, and plot implementations retain their owners.

## Contract and narrowly changed behavior

[`SESSION_FORMAT.md`](../../design/SESSION_FORMAT.md#checkpoints-and-section-derivation) defines a captured checkpoint as closing and naming its preceding section. The existing public API selects a checkpoint ID or name; it does not select section-start tags. The older research note's tagged-start example is therefore a different model. The explicit [analysis decision](../../design/ANALYSIS.md#decision-2026-10-08-captured-checkpoints-close-analysis-sections) records that distinction, and the scope-picker owner was notified at issue #53 comment `6059617804`.

The selected interval begins at the previous effective checkpoint, or session time zero for the first checkpoint, and ends at the selected effective checkpoint. Original timestamp fallback, camel/snake aliases, exact integer nanoseconds, stable ordering of equal timestamps, and name/ID matching are unchanged. The final checkpoint no longer takes ownership of the session's trailing interval.

Point sections remain `[t,t]`. Existing inclusive endpoint policy means a sample exactly at that instant is retained. No one-nanosecond extension or empty-data assumption is introduced. A persisted first checkpoint before session time zero would create inverted bounds, so it now raises the same kind of explicit invalid-range error used by custom windows. It does not clamp or rewrite signed records; later ordered signed endpoints remain exact.

## Native experiment and observed data

Runtime is native macOS arm64, CPython **3.12.8**, with an isolated virtual environment populated from the existing local packages and their declared analysis dependencies. [The dependency freeze](environment-freeze.txt) and [dependency check](environment-check.txt) preserve exact installed versions. No GUI, daemon, physical sensor, or installed application was used.

The test creates 81 real IMU protobuf frames in MCAP at 10 Hz from session time 0 through 8 seconds. The wrist's x value is its frame index. Stored checkpoints are intentionally out of order and include a zero marker, a named reach section, a tied marker, and a final marker. The CLI reads the package through its ordinary reader, resolver, plugin pipeline, and artifact writer. Parquet and CSV are read back and compared to exact analytic values, and the plotted sync series is checked against the retained raw timestamps.

| CLI case | Original resolved seconds | Corrected resolved seconds |
| --- | --- | --- |
| Warm-up | 2–5 | 0–2 |
| Reach, selected by Unicode name | 5–5 because the next marker is tied | 2–5 |
| Finish | 7–8, the tail | 5–7 |
| Zero marker | 0–2 | 0–0 |
| Tied marker | 5–7 | 5–5 |
| Reach edited to 4 seconds | 4–5 | 2–4 |
| Full session | 0–8 | 0–8 |
| No checkpoints, full selection | 0–8 | 0–8 |
| Explicit trailing range | 7–8 | 7–8 |
| Persisted first marker at −1 ns | Reports completed, CLI exit 0 | Reports invalid bounds, failed manifest, CLI exit 1 |

The corrected reach output has 30 feature rows with midpoints from 2.05 to 4.95 seconds and x means from 20.5 to 49.5. The original output has only the tied boundary row. The corrected point cases retain exactly one feature row at their boundary. All eight raw package files retain their exact hashes in every baseline and candidate invocation; processing results are the only new package products. [cli-comparison.json](cli-comparison.json) records each actual result, parameters, table summary, and raw hashes.

The 20 public-resolver cases additionally cover effective edits that reorder checkpoints, all existing timestamp aliases, null fallback versus effective zero, values beyond floating-point integer precision, missing selection failures, signed endpoints, range precedence, and unchanged full/custom behavior. [run-summary.json](run-summary.json) retains exact commands, runtime imports, timestamps, test counts, and return codes.

## Actual figures and preserved presentation limit

[Corrected IMU figure](figures/candidate-imu.png) and [corrected sync figure](figures/candidate-sync.png) were inspected directly as native Matplotlib outputs. They contain the expected 20–50 signal across the selected three-second interval. [The original IMU figure](figures/baseline-imu.png) preserves the incorrect tied-point selection.

There is a preexisting label discrepancy in both untouched plot functions: they subtract the first retained timestamp but label that elapsed axis `session time (s)`. These candidate figures consequently show 0–3 on that axis while the selected absolute session interval is 2–5 seconds. The manifest, Parquet, CSV, and sync-series JSON retain the correct absolute nanoseconds. [visual-receiving.json](visual-receiving.json) records this limit and the handoff to the current plot/scope owners. This resolver repair does not claim to fix that label.

## Reproduction and evidence custody

From the repository's Python 3.12 analysis environment:

```sh
python -m pytest tests/analysis/test_checkpoint_sections.py -q
python -m pytest tests/analysis/test_phase_a_qc.py tests/analysis/test_phase_b_features.py tests/analysis/test_stream_gap_scope.py -q
python -m ruff check libs/python/capture_analysis/capture_analysis/windows.py tests/analysis/test_checkpoint_sections.py
python tools/check_licenses.py
```

The evidence includes the exact [native paired runner](receive.cjs), [regression runner](regression.cjs), and [collector](collect.py). Each native archive retains all regular test receipts, JUnit, stdout, synthetic raw packages, and derived results. Only reproducible Matplotlib caches, empty state directories, and pytest convenience symlinks are omitted; original native evidence was not removed or edited.

| Archive | Verified regular payload files | Uncompressed bytes |
| --- | ---: | ---: |
| [Original implementation](baseline-native.tar.gz) | 176 | 972,457 |
| [Corrected implementation](candidate-native.tar.gz) | 173 | 877,572 |
| [Existing regression controls](regression-native.tar.gz) | 99 | 204,387 |

Each archive has its adjacent complete file manifest. The transferred packet's SHA-256 is `414586feae8ccc75cde233dff932c4883633e4110b0a3d12c4282d957fa8b503` (774,126 bytes); all outer and nested payload hashes matched locally. [The transfer receipt](evidence-transfer.json) records that boundary. The original failing baseline and all native warnings remain available.

These results qualify the bounded offline analysis repair. Full supported Windows CI and any desktop scope-picker composition remain separate integration gates. No deployment, release, or physical-acquisition result is claimed.
