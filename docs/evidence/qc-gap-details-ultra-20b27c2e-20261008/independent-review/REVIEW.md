# Independent CaptureSuite QC receiving review

**Qualified:** the frozen QC and HTML changes pass seven independent native cases on current receiving source. No blocking finding was reproduced. The original QC fails the same real CLI gap challenge while its no-gap control remains healthy.

## Exact source and receiving closure

Repository: Jacob-Met/CaptureSuite. Receiving commit: `a1b3c966bc8df46fd8160d3854c30a9e03c6a478`; primary tree: `afd26ca94b2bfd2762e4ec9c1be5dfb5e5a22bd7`.

| File | Candidate SHA256 | Candidate Git blob | Original Git blob |
| --- | --- | --- | --- |
| libs/python/capture_analysis/capture_analysis/qc.py | f24e0593a3723311d41054aef40b56c4bb46d4f3ba5ef4b01afcae3a6cc4440a | 530b86af1247599c127e2d0c3fa5e4d7d12169f6 | 7221b26a129b7915a42fed900908a04eae213454 |
| libs/python/capture_analysis/capture_analysis/report_html.py | f2c89c7faf6e4edc265540140272396b4195eb5aed9edf05c4912aac74286f03 | bb8032024cfce30c6fe9a2bd2c13b0d2cbc2d102 | a0bb34d71fe03a4426ef0479619fa8d22a7bc8fa |

The isolated receiving copy contains 100 files: three Python packages, the actual CLI, the native mini-session fixture, the analysis-job schema, and AGENTS. The reviewer independently fetched the complete immutable primary tree (688 entries, not truncated) and verified all 100 baseline blob references and all 98 unowned candidate blobs. The owner source copy had an older framing.py. The review copy explicitly incorporates current `capture_protocol/framing.py` blob `9dd5021b815b31ab02eaaa814210525ebb543862`, fetched from the receiving commit, in both candidate and baseline. No owner source was edited.

See [source-closure.json](source-closure.json), [primary-receiving.json](primary-receiving.json), and [owner-current-drift.json](owner-current-drift.json). The latter includes the two intended QC changes and the independently preserved framing update.

## Native results

| Replay | Result | Meaning |
| --- | --- | --- |
| Candidate independent cases | 7 passed; 0 failed/errors/skips | All compound checks below passed |
| Original QC, real CLI gap challenge | 1 expected failure | Closed gap remains green, no details, exit 0 under strict warnings |
| Original QC, real CLI no-gap control | 1 passed | Receiving environment and ordinary native job remain usable |
| Candidate real CLI, one closed gap | exit 2; completed_with_warnings | Attributed detail present; affected source warn; healthy neighbor green |
| Candidate real CLI, no gaps | exit 0; completed | Zero warnings; sources green |

The reviewed cases cover:

- Three sources and four streams: one failed stream plus a healthy sibling, a separate gapped source, and a healthy source. Failure severity remains dominant, gaps retain the supplied source/stream/cause, and multiple streams do not duplicate gap rows.
- Full signed 64-bit endpoints: duration `18446744073709551615` ns renders exactly as `18446744073.709551615` seconds. Explicitly open/reversed, closed/missing-end, and native start-only records keep distinct unknown-duration states. Native start zero is preserved as a valid supplied value.
- Snapshot custody: modifying a returned dictionary or later changing the owned fixture does not mutate the previously collected report. A later collection sees the later fixture.
- Legacy missing/null details remain “not available”; an actual empty detail list reports no listed records.
- Untrusted recorded text survives decoded HTML cells exactly, without becoming executable markup.
- The actual unmodified `tools/run_analysis.py qc` path produces the expected JSON, HTML, job status and strict-warning exit behavior.
- All 12 raw package-file hashes remain unchanged in each actual CLI replay. Both QC JSON and HTML byte counts and SHA256 digests match their job-manifest output entries.

Actual CLI receipts and HTML are under `evidence/candidate/` and `evidence/baseline/`. The gap control records a one-nanosecond interval near the signed 64-bit ceiling and a loss estimate above JavaScript's exact integer range.

## Reproduction and evidence

The tested independent harness is [test_independent_capture_receiving.py](test_independent_capture_receiving.py), SHA256 `9131bec9582e80daec244f481eeb2f2cd2117d7f058676f5ae4eb41f594d02fc`. It imports real native code, writes only owned synthetic fixture copies, and invokes the native CLI as a subprocess. It does not patch production payloads or use an account, device, broker, service or live capture.

Set `CAPTURE_REVIEW_CHECKOUT` to the intended exact checkout, `PYTHONDONTWRITEBYTECODE=1`, and private `TMPDIR` and `MPLCONFIGDIR`; run the harness with pytest and `-p no:cacheprovider`. The preserved [run_review.py](run_review.py) and [execution-receipt.json](execution-receipt.json) record the exact historical commands and existing dependency paths.

Runtime: Python 3.12.14, pytest 9.1.1, NumPy 2.3.5, SciPy 1.17.0, pandas 2.2.3, Matplotlib 3.10.8, PyYAML 6.0.3, jsonschema 4.26.0. jsonschema was reused from an already installed environment; no installation or download was required. Manifest validation ran for these CLI controls, so their statuses are not explained by a missing-validator warning.

The receiving namespace peaked at 1,912,832 allocated bytes, below its 20 MiB abort threshold. Tests disabled bytecode and pytest caches; each child had a 3 MiB file limit. Frozen candidate closure and owner production hashes were verified unchanged afterward. Shared storage became full after the completed runs. Only the reviewer's reproducible Matplotlib font-list cache was reclaimed to save this final mapping; test logs, source, fixtures and CLI receipts remain preserved.

## Scope and remaining integration work

This review qualifies local offline QC inventory and reporting with the current native source composition. It does not qualify physical acquisition, wire protocol behavior, feature extraction, a deployed host, or the entire CaptureSuite suite. It adds no device-failure interpretation for unknown causes and makes no hardware-sync claim. Existing malformed raw-reader coercion rules were not changed or broadened by this review.

Publication must use a fresh complete primary tree, preserve the current framing and all other unowned changes, and retain these exact two qualified production blobs. No GitHub write, merge, deployment, service change, or raw-data mutation was performed by the reviewer.
