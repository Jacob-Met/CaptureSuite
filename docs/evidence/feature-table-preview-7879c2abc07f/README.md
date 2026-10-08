# Retained feature-table preview — source and evidence custody

CaptureSuite [issue #92](https://github.com/Jacob-Met/CaptureSuite/issues/92) adds a native preview for a retained feature table in the loaded Analysis job inspector. The feature has passed the native component and actual-workbench receiving described below. This custody branch preserves its source and evidence for the existing supported-platform integration process.

## Researcher-facing behavior

In the loaded completed job, choose a listed feature table and press **Preview retained feature table…**. The native dialog shows the first 200 retained rows, the original total row count, and the selected table and job identity. Separate column and provenance views show exact Arrow types, recorded units and calibration flags, optional descriptions, session identity, and table/manifest hashes. Selecting a cell exposes its complete displayed value as plain text.

Signed and unsigned 64-bit integers and nanosecond timestamps remain exact. Null, numerical NaN, infinities, booleans and quoted strings remain distinguishable. Empty tables display their schema and zero rows. Unsupported, changed, unlisted or oversized inputs produce a refusal without presenting a partial set of columns. Clearing or loading a job closes the old preview and invalidates late results.

The reader reuses the existing completed-job/parameter admission code. It verifies listed table/schema identities and contained paths before reading, checks them again before publishing, and reads Arrow data one row at a time outside the UI thread. The documented limits are 200 displayed rows, 128 columns, a 256 MiB file, bounded JSON/Parquet metadata, a 32 MiB admitted uncompressed row-group budget, 8 MiB decoded/display result budgets, and 4,096 characters per text cell. These are admission and retained-result limits; they do not assert a process-wide memory ceiling.

See the complete [feature contract](../../design/research/FEATURE_TABLE_PREVIEW.md) for accepted types, identity checks, limits and lifecycle behavior.

## Exact source anchors

| Role | Commit | Tree |
|---|---|---|
| Original current base used for native receiving | `9e9204f76b105426b0affaa74733175c052f27ba` | `a1b37ec1ab291a90cb2a383aa8f50b797ac09932` |
| Final qualified source | [`9aa4fd1d913e1be5a8cc8908149826ec2f6f59e7`](https://github.com/Jacob-Met/CaptureSuite/commit/9aa4fd1d913e1be5a8cc8908149826ec2f6f59e7) | `ae2bf0a6d98fae911f08beecef3ac25c029c02af` |
| Later main containing recorded-video review | `3960c0c756cd4e9facbde0d76eaaa3c31ab7c167` | `d1af33caaf7154e83def1dab035920907d417e8d` |
| Source composition preserving that later main | [`618ef768a519cce60b74d18cdab4375203e65c58`](https://github.com/Jacob-Met/CaptureSuite/commit/618ef768a519cce60b74d18cdab4375203e65c58) | `3660f0b33a5770a873c133b4760afbe6cccc295a` |

The qualified commit has sole parent `9e9204f7`. The composed commit has ordered parents `3960c0c7` and `9aa4fd1d`. Root read back both commit objects and complete trees.

The seven owned paths are two new native modules, their two test files, the feature contract, a PROGRESS append, and five additive lines in `widgets_analysis_plots.py`. Those five lines add the import, FeatureTableBar construction/layout, clear hook and load hook inside JobInspector. Existing saved-parameter controls, FigureGallery methods, Analysis screen, job runner, feature producer, exporter, schemas, dependencies and workflows retain their ownership and source. [manifest.json](manifest.json) records every original and final blob, size and SHA256.

## Actual receiving and preserved corrections

| Evidence phase | Observed result | Qualification |
|---|---|---|
| Original native baseline | Healthy current writer and inspector prerequisites passed; the feature-preview control was absent, with the causal process failure retained | Exact pre-candidate source and fixtures |
| Final authored gate | **90 passed; 0 failures, errors or skips**, 20.1116 seconds process time under the unchanged 300-second deadline | 35 reader + 6 widget + 45 existing comparison + 4 existing file-read cases; all 321 selected files conserved |
| Frozen independent native consumer | **21 of 21 groups passed; 0 failures or skips**, process exit 0 | The same 31,875-byte consumer was frozen before candidate inspection and used for both attempts |
| Actual AnalysisScreen continuation | **Passed**, process exit 0; a real QC worker completed job `20261008T215331Z_57fbeb84` | Real Preview and Run/QC controls; 82 GUI heartbeat ticks; old dialog deleted and its late result rejected |
| Current-source composition | Complete 1,285-leaf tree and all **67 executed project paths** verified | Static comparison to the actual earlier receiving; no new execution is claimed |

The authored gates overlap. The earlier 34-case reader, 35-case reader, three six-case widget runs and two 90-case integrations are preserved as separate phases and are not added into a synthetic total. The test runtime was the existing native Python 3.12.15 / PySide6 and Qt 6.12.0 / PyArrow 25.0.1 environment. Archive-building runtime metadata is labeled separately.

Three corrections remain visible in the evidence:

1. Before candidate acceptance, independent review demonstrated that dictionary encoding could expand a small retained string column when decoded in a 200-row batch. The reader changed to one-row batches with per-batch and per-cell admission. The original reader, the actual witness and the corrected receiving remain preserved.
2. The first independent widget run passed 20 groups and failed the absent-selection action-state check: setting the selector to index -1 left Preview enabled. Its existing action guard prevented an unlisted table from opening. The final widget updates enabled state and explicitly guards the absent index. The original failed source/receipt and the same unchanged consumer's final 21-group pass remain preserved.
3. The separate first workbench receiver called `isVisible()` on a dialog that the application had already correctly deleted. Its one-line receiver correction accepts a deleted object as closed before inspecting visibility. The original harness, error, exact diff and corrected real-control run remain preserved. This was a receiver error, not a product failure.

The actual Run/QC continuation used an isolated fixture package. All 12 raw/non-processing files and seven files belonging to the prior retained job remained exact. The explicitly launched QC job produced five new retained outputs. Source origins and before/after records show that the exercised code came from the qualified source, not the environment's older editable installation.

Actual native captures of the Rows, Columns and Provenance views, plus the corrected disabled action, are included in the author packet. Root inspected the native presentation and requested the visible table/job heading before acceptance.

## Preservation on the later main

The later main added 72 recorded-video leaves and modified four existing paths. All of its contribution is retained. Composition changes only the two existing owned paths and adds the five new feature paths: **1,278 unrelated current leaves and their modes remain exact**.

Independent review reconstructed every Git directory hash from complete leaf maps for the original base, qualified source and later main, then independently derived the composed tree above. It verified the full 76,964-byte current PROGRESS prefix, the exact 1,584-byte authored feature suffix and a separate 1,385-byte receiving note.

Of the 321 files in the earlier qualified projection, 319 remain byte-identical in composition. The two expected differences are the later, unexecuted `screen_review.py` and reconciled PROGRESS. All 67 project paths actually executed by the final author and independent runs retain their exact blobs and modes. The new video modules and their QtMultimedia imports remain outside this feature's execution claim.

The final custody commit also corrects the feature contract's abbreviated button label to the actual **Preview retained feature table…** text. This is a documentation-only successor to the source composition; historical qualified and composed anchors remain intact. No executable source or test changes accompany it. The final custody tree has 318 of the original 321 projected files unchanged: the newer Review screen, reconciled PROGRESS, and this label correction are its three documented, unexecuted differences. All 67 executed project paths remain exact.

## Evidence files

| File | Contents |
|---|---|
| [manifest.json](manifest.json) | Source anchors, seven owned path identities, final receipt hashes, archive identities, limits and custody rules |
| [author-native-evidence.json](author-native-evidence.json) | Exact UTF-8 envelope with a 1,442,849-byte gzip archive: 458 members, baseline files, original/final authored sources, phase-specific tests and receipts, origins, lint, preservation records and native captures |
| [independent-native-receiving.json](independent-native-receiving.json) | Exact UTF-8 envelope with a 1,283,025-byte gzip archive: 801 members, original baseline, full final 321-file selected source, failed-source reconstruction, both consumer/workbench attempts, fixtures, actual outputs, raw logs, JUnit, origins and conservation records |
| [reviews.json](reviews.json) | Exact root and independent review documents, including full-tree derivation and cross-reception of both evidence packets |

The independent receiver's packet was independently received by the source integrator. The author packet was independently received by the consumer reviewer. These are byte/provenance reviews of existing evidence; they do not represent additional product test executions. Every archived member and its declared identity is checked, and original failures retain their historical source labels.

Both envelopes store their compressed bytes at `archive.base64`, with `archive.bytes` and `archive.sha256`. The author archive uses `archive.filename`; the independent archive uses `archive.name`. The following standard-library snippet verifies either envelope and writes its archive only if that filename does not already exist:

```python
import base64
import hashlib
import json
import sys
from pathlib import Path

envelope = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
archive = envelope["archive"]
raw = base64.b64decode(archive["base64"], validate=True)
assert len(raw) == archive["bytes"]
assert hashlib.sha256(raw).hexdigest() == archive["sha256"]
name = archive.get("filename") or archive["name"]
assert isinstance(name, str) and Path(name).name == name
with Path(name).open("xb") as output:
    output.write(raw)
print(f"Verified {name}: {len(raw)} bytes, SHA256 {archive['sha256']}")
```

## Integration and ownership boundary

Supported Windows integration, full-application behavior and installed-runtime adoption remain pending under the existing gates and owners. This work does not claim physical capture or scientific validation.

The [newer direct-execution instruction](https://github.com/Jacob-Met/hamon/issues/143#issuecomment-6069904551), updated at 22:22 UTC, authorizes existing owners to build, test and integrate directly on LA7 through their actual permitted native/MCP route while preserving equivalent quality gates and installed-source evidence. Source custody alone is not adoption. This team's RDC route now reaches LA7; existing CaptureSuite ownership and toolchains are being inspected for the next native receiving step. The [current migration notice](https://github.com/Jacob-Met/hamon/issues/140#issuecomment-6070395002) keeps the ThinkPad dispatcher and current routes active; this component lane does not change them.

The [active no-Actions instruction](https://github.com/Jacob-Met/hamon/issues/143#issuecomment-6067592767) holds any PR update, merge, dispatch or other step that would start a workflow. Existing workflow definitions and required gates are preserved. Custody uses a new non-main branch without a pull request after checking the exact workflow events; the issue checkpoint records its final ref and post-publication Actions observations.

Saved-job/package lifecycle work remains with [#55 / PR71](https://github.com/Jacob-Met/CaptureSuite/issues/55). This feature composes through JobInspector's existing clear/load hooks. The current AnalysisScreen package-change boundary is recorded for that owner. Selected-column export remains with [#78](https://github.com/Jacob-Met/CaptureSuite/issues/78); preview adds no export operation.
