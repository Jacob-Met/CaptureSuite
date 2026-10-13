# Feature CSV mirrors: native Windows receiving

## Result

On 2026-10-13, the existing five-case receiver completed on **Windows 11 (10.0.26200), CPython 3.12.10, pandas 2.2.3 and PyArrow 26.0.0**. The original writer passed 2 of 5 cases and 35 of 48 checks. The accepted writer passed 5 of 5 cases and all 48 checks. Both runs used actual Parquet and CSV writers and readers.

The cases cover ordinary forward-slash and backslash paths, an earlier `.parquet` filename component, a `.parquet` parent with no incorrectly renamed directory, and a parent/stem path with backslashes. The original reproduced misplaced CSVs, overwritten neighbour sentinels and the missing-parent failure. The accepted source preserved the neighbours, registered the intended colocated files, retained schemas and data, and passed the same checks.

Readback of the two retained receipts shows **identical Parquet bytes in all five original/candidate pairs on Windows**. Native CSV files in this run are 71 bytes; the prior Linux receiver recorded 68 bytes. Each native manifest was checked against its actual local bytes. All input source/receiver bytes stayed exact; every receiver-owned fixture directory was removed after its run.

| Evidence | Result |
|---|---|
| [Windows qualification](windows-qualification.json) | Exact commands, versions, source/receiver pins and per-run totals |
| [Parquet pair comparison](parquet-comparison.json) | Five byte-identical original/candidate Parquet pairs |
| [Independent review](independent-review.json) | Direct receipt audit and native SHA-256 verification; accepted as bounded Windows writer qualification |
| [Complete source and evidence archive](source-and-evidence.json) | Sixteen UTF-8 files with exact byte counts, SHA-256, Git blob IDs and contents |

## Source and ownership

The repaired product source is the existing owner's `libs/python/capture_analysis/capture_analysis/features/io.py`, Git blob `dfa2e34fc881a76fb461c51dbf3e94aa4c594e0c` and SHA-256 `e7c26202f02ba870e0a2db9cb840ab64c706929efe98da111b405ce4ffb47321`. Original source is blob `b998063a5036b73a67b773f70c193b1f9827c248`.

This receiving uses the exact source reviewed in [PR #124](https://github.com/Jacob-Met/CaptureSuite/pull/124), head `e557d1e0a243ade939d0de92dea9b005e752a8de`. Its existing publisher merged that contribution at `ab17b8c50af9892483b49ce4c125ef28f38eb72c` on 2026-10-13 at 00:10:19 UTC. A later readback found the same writer on main. This increment adds receiving evidence; it does not change the product implementation.

The receiver and frozen contract are reused **unchanged** from [the independent receiving handback in issue #122](https://github.com/Jacob-Met/CaptureSuite/issues/122#issuecomment-6134723948), authored by `chatgpt-f0f66340f637/runtime_integration`. The source publisher remains `582de029aa19/portfolio`. Native Windows execution and the wrapper/readback are by `HAMON deec14e7c405/runtime_worker`. This is a new platform run of that prior receiver, not a newly blinded test design.

The archived child receipts intentionally retain the prior receiver's actor and `native_windows_acceptance: false` field. The outer qualification separately records the actual Windows platform, commands and outcome. That distinction preserves the original receiver bytes and avoids treating this narrow run as full application acceptance.

Independent reviewer `HAMON deec14e7c405/source_worker` read the complete original/candidate source, receiver, frozen contract and receipts, audited every case, and independently rehashed eight native files. The [independent review record](independent-review.json) preserves those pins and accepts this bounded result. The reviewer did not rerun the product. Publication composition is reviewed separately.

## Environment and limitations

The machine's C: drive had about 4 MB free. All new interpreter, dependency and fixture work therefore used the owned `D:\hamon-capture-windows-deec14e7c405` directory, where roughly 345 GB was free at setup.

An already available official CPython 3.12.10 embeddable archive was verified against its retained SHA-256 and the official release-page checksum, then extracted into the owned directory. No existing interpreter, installed application or security setting changed. A first isolated pip install timed out at 480 seconds. Its receipt and log are retained. The seven already downloaded wheels were then verified against the resolved SHA-256 values and installed offline with `--no-compile`, completing successfully in about 117 seconds. The installed dependency versions were numpy 2.3.5, pandas 2.2.3, PyArrow 26.0.0, python-dateutil 2.9.0.post0, pytz 2026.5, six 1.17.0 and tzdata 2026.5. Exact wheel identities are in `offline-install-receipt.json` inside the archive.

The supported Python minor version and actual Windows filesystem are covered. Full analysis pytest, Ruff, Qt/desktop, C++/camera, hosted CI, installed application and physical acquisition were not run by this receiving. Existing gates and ownership remain in force. No GitHub Actions execution or workflow change is part of this increment.

## Recover and rerun

The archive stores original file text, including CRLF where recorded, rather than rewriting captured source to add packaging headers. It includes both source versions, the unchanged receiver/contract, wrapper, original/candidate receipts and logs, and both setup outcomes. Root repository licensing applies to the contribution; archived files retain their original headers and attribution.

To recover exact bytes into a new directory, run this from the repository root using Python:

```python
import hashlib, json
from pathlib import Path

archive = Path("docs/evidence/feature-table-csv-windows-deec14e7c405/source-and-evidence.json")
destination = Path("feature-csv-windows-recovered")
destination.mkdir(exist_ok=False)
for item in json.loads(archive.read_text(encoding="utf-8"))["files"]:
    data = item["content"].encode("utf-8")
    assert len(data) == item["bytes"]
    assert hashlib.sha256(data).hexdigest() == item["sha256"]
    assert hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest() == item["git_blob"]
    (destination / item["name"]).write_bytes(data)
```

Keep that recovered record intact. For a new Windows run, copy only `receive_sidecar.py`, `frozen-contract.json`, `original_feature_io.py`, `candidate_feature_io.py` and `run_qualification.py` into a **separate new directory** with an empty `temp` child. Use a Python 3.12 environment with the pinned numpy/pandas/PyArrow versions recorded above, then run `python -B run_qualification.py` there. The wrapper refuses an existing qualification receipt, executes both original and candidate, and writes fresh results with their actual paths and time.

The archived setup scripts describe this particular device's recovery, including the reused local archive path. They are execution records, not portable installers. A different receiver should use its normal approved Python installation and the recorded dependency versions.
