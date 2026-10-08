# Selected figure export: source and native receiving

Owner: `chatgpt-ac386303dce2/product_execution`. Native estate scope was recorded
before source edits; the repository claim is [CaptureSuite #59](https://github.com/Jacob-Met/CaptureSuite/issues/59).
The saved-history owner was coordinated through
[#55 comment 6060447723](https://github.com/Jacob-Met/CaptureSuite/issues/55#issuecomment-6060447723).

## Beneficiary outcome

A researcher can select and preview the loaded analysis job's original PNG
figures, choose a ZIP destination, and retain those exact images alongside the
job's unchanged manifest and parameters. The new bundle index identifies the
selected artifacts and computes their actual input digests. Source/job bytes
and prior user exports remain intact when source validation or output writing
fails. The native dialog supports keyboard selection, explicit replacement,
cancellation, retry and gallery clear/reload.

This implements the existing Workbench §5/§9 workflow. It adds two small desktop
modules and five gallery hook lines, plus focused tests and documentation. It
does not alter the analysis producer, numerical results, capture, source/raw
exports, history/scope screen hooks, settings, dependencies or CI rules.

## Source composition

The original base is `e43da3b855475c8aacf815c201fa03eddaeec0f1`. The source checkout
was assembled from 562 exact current Git blobs; each local source read was
checked against that authoritative blob before use. Historical receiving-only
directories were unnecessary for the local source execution and were not
materialized. The repository publication preserves them in the complete tree.

Publication is composed over current main
`d43bdea867d6198a707a5f55e29216c76054517e`, tree
`fea0e03773742d330963b89e0ceb72a22c7ad495`. Its entire 892-leaf tree is retained
except the five declared gallery additions and the required progress append;
all new feature/evidence paths are additions. The 92 paths received since the
original base belong to time-scope, generic numeric analysis, Windows atomic
writing and their evidence. Their 23 non-evidence files were materialized and
verified from the prior current source, `3e3ecc5e`, on which the focused native
suite was run. The subsequent 38-path kinematics integration is preserved
unchanged, including its computation, test, contract and all receiving evidence.
Its sole intersection with this contribution is the additive progress log.
The gallery, job producer, theme, job schema and CI contracts used by the export
remain unchanged across these current-main advances.
PROGRESS contains the full current main file followed by the exact owned entry.

`author/source-freeze.json` identifies the exact helper, dialog, gallery and
test bytes. The final dialog includes a four-line local stylesheet making its
disabled Export button visually disabled under the existing Primary theme.
Root independently inspected that exact delta and its actual dark-theme render.

## Author receiving

Actual runtime: Python 3.12.14, native PySide6/Qt 6.11.2, Linux/offscreen. Runtime
versions and the loaded QtCore binary digest are in `author/runtime.json`. The
existing read-only dependency installation was reused; no machine or project
dependency installation occurred.

| Frozen experiment | Result | Evidence |
|---|---|---|
| Original gallery in a real QApplication | No export button/capability | `author/baseline-absence.json` |
| Initial feature receiving | 35 passed | `author/author-tests.xml` |
| Expanded original-base feature/workbench receiving | 43 passed; one existing optional PyQtGraph skip | `author/author-qualified.xml` |
| Exact `3e3ecc5e` main composition feature/workbench receiving | 43 passed; the same one skip; exit 0 | `author/current-main-feature.xml`, `.log` |

All 40 new feature cases execute in the final suites. They cover exact selected
members and all original provenance; stale, missing, invalid and linked PNGs;
malformed or ambiguous job inventories/JSON; source destination refusal;
write/flush/publication failure and retry; non-overwrite when another file
arrives; keyboard selection; empty/invalid/cancelled state; explicit replacement
refusal/acceptance; and clear while a real Qt export worker is running.

The final native scenario builds an actual synthetic EMG/IMU MCAP session, runs
the existing `capture_analysis.run(command="all")`, loads its produced figures
in the gallery and exports them through actual Qt controls/QThread. It verifies
every archive byte against the producer's files and checks all source/session
bytes afterward. `author/native-preview-export.zip` is an earlier real-producer
two-figure example with the same export contract; its saved source paths are
synthetic fixture provenance. It is not an installed-app output or patient data.

One early expanded test expected a particular JSON parser refusal for a deeply
nested object that the local parser could read; the actual loader correctly
rejected its missing schema instead. The source remained unchanged, and the
test was corrected to require the promised refusal rather than a parser-specific
message. The original failed JUnit remains in `author/author-first-combined.xml`.

## Independent receiving

`root_receiving/REVIEW.md`, the unchanged independent probe, and the complete
`independent-receiving.json.gz` capsule are adopted byte-for-byte from the
separate root receiver. The capsule contains 23 hash-verified members including
source snapshots, all original logs/XML/receipts, the baseline control and the
accepted QSS successor. Its gzip digest is
`5e9964e2df5b75f79edeb8dd599dcd7a5af408faa22f51f0791860489af1f1ed`;
decoded JSON is 253,980 bytes, digest
`9c5788642d5bb2a1a4608491791007566cef465764cfc0fdf3f4e5ecf1934a0f`.

The same independent visible-export assertion fails on the original gallery.
The unchanged 16-case probe passes **16/16 with zero skips** on both the initial
source and the exact accepted helper/dialog/gallery. It separately authors PNGs
and metadata, exercises actual Qt/keyboard/QThread behavior, checks exact bytes,
tests directory replacement and destination arrival, and induces a real Linux
`RLIMIT_FSIZE` write failure while preserving the prior export and source bytes.
Its first fixture-placement attempt had setup errors because `/dev` is private
to each execution call; the unchanged probe passed after fixture creation and
execution occurred in one call. That environmental negative is retained.

To inspect the capsule without losing any original whitespace or binary bytes:

```python
import base64, gzip, hashlib, json
from pathlib import Path

packet = json.loads(gzip.decompress(Path("root_receiving/independent-receiving.json.gz").read_bytes()))
for entry in packet["files"]:
    data = entry["content"].encode("utf-8") if entry["encoding"] == "utf-8" else base64.b64decode(entry["content"])
    assert len(data) == entry["bytes"]
    assert hashlib.sha256(data).hexdigest() == entry["sha256"]
    # entry["path"] names the original member; inspect or extract into a fresh directory.
```

## Carried-source exploration and limits

A broader exploratory run including the incoming time-scope suite stalled in
an existing plotting worker and was interrupted, exit 130. It is not accepted
as a completed suite. A bounded candidate range-job replay passed in 32.46 s;
its timeout stack captured existing Matplotlib Agg `savefig` before gallery
loading. An unchanged current-main gallery control reached the same renderer
and timed out after 60 s. Both exact logs and the interrupted-run receipt remain
under `author/`; they are not a performance comparison or a whole-scope/Linux
qualification. No scope, worker or plotting adapter was added for that latency.

Local source/native receiving and independent review are publication evidence.
The actual proposed-head Windows CI and final current-tree receiving remain
separate merge gates. No Windows/hardware result, installed desktop, live capture,
patient data, concurrent-writer transaction or crash-durability result is inferred
from the local Qt work. The operator contract and explicit bounds are in
[`FIGURE_EXPORT.md`](../../design/research/FIGURE_EXPORT.md).

With the repository's declared CI dependencies installed, reproduce the focused
suite from the repository root:

```sh
QT_QPA_PLATFORM=offscreen python -m pytest tests/ui/test_analysis_figure_export.py tests/ui/test_analysis_workbench.py -q
```

`SHA256.json` inventories this receiving packet. Actual published-head CI and
independent commit binding are recorded on the pull request rather than folded
back into an already tested source commit.
