# Nested numeric figures in the saved analysis gallery

Issue [64](https://github.com/Jacob-Met/CaptureSuite/issues/64) repairs the desktop reader for the nested PNG layout already emitted by merged numeric-analysis [PR 49](https://github.com/Jacob-Met/CaptureSuite/pull/49). A retained real numeric job had two valid channel PNGs, but both direct gallery loading and saved-job reopening showed only the Sync tab. The original negative receipt is preserved in `qualification/baseline-numeric-receipt.json`.

## Result and source boundary

The only production change is inside `FigureGallery.load_job_dir` in `desktop/capture_desktop/widgets_analysis_plots.py`. Discovery includes PNG descendants of the selected figures directory. Numeric source/stream directory identities use their existing UTF-8 hex encoding to produce readable source / stream / channel tab labels; exact relative paths remain available as tooltips. Unknown nested layouts retain their relative path labels. Legacy flat labels retain their original 24-character behavior, and only the root `sync_dashboard.png` is suppressed in favor of the existing linked dashboard.

Directories named `*.png` and file candidates that resolve outside the real figures directory are excluded while valid siblings remain visible. An unreadable PNG retains the existing explanatory image placeholder. This is a bounded saved-file reader check, not a claim about adversarial concurrent filesystem changes.

The gallery constructor, clear method, loaded-job/export ownership, SyncDashboardView, JobInspector, numeric handlers, analysis history and writer formats are unchanged. Shared-file coordination with the selected-export owner is recorded in [issue 59 comment 6061378807](https://github.com/Jacob-Met/CaptureSuite/issues/59#issuecomment-6061378807).

## Exact qualification

The genuine authored parent is `3e3ecc5ecc1cfc79c79901eb5cffe10b0ec5852e`. Runtime/test commit `f2c8b88f16f82517bd8fce118bacf63704b0a1f5` has tree `6c72934c1369cd9ccd4c466c3c0fb18038fb1cce`. The publication successor adds only this evidence and an additive PROGRESS entry.

| Observation | Exact scope | Result |
| --- | --- | --- |
| Independent real numeric baseline | Existing gallery blob `bb6c3033b5e4ed96a2e08857d38715b836926bf5`, current numeric pipeline plus saved-history receiver | Two saved nested PNGs; gallery only Sync; 6 positive checks and 1 presentation failure |
| Initial native author suite | Gallery SHA-256 `852c9059d01fac9ba38edbe228e0920e8cf3298bb8e1a9d6610b148f6d1e7ffb` | 6 passed |
| Initial retained-output receiving | Same initial gallery bytes | 15 checks passed; this predates the containment correction |
| Added containment challenge | Same initial gallery bytes, new external-PNG symlink and directory fixtures | 1 expected failure: the foreign PNG appeared as an extra tab |
| Final native author suite | Gallery SHA-256 `c3837c72285b37e486be38933ad73950ae91ba10d335ff5e1c3f37ef5d08aa26` | 7 passed, 0 skipped |
| Final real retained-output receiving | Same final gallery bytes, unchanged receiving method | 15 checks passed, process exit 0 |
| Static checks | Final production module and focused test | Ruff and whitespace passed |

The final retained-output run uses QApplication.exec with QTimer scheduling on the existing Linux Python 3.12.14 / PySide6 6.11.2 runtime. It does not generate new jobs or use manual event pumping. It verifies both actual numeric PNGs pixel-for-pixel against their saved files, exact source/stream/channel identities, the retained numeric linked series, the two older flat EMG/IMU figures and their two linked series, package switching, and every raw/saved package hash before and after reading. It also checks the executed source bytes. The five standard offscreen `propagateSizeHints()` notices are retained in the process receipt; there are no exceptions or failed checks.

The exact executed method is `methods/receive_retained_gallery.py`, SHA-256 `a83e1abed7c773b2692d7983873d9aa852603548e9c6870d85ea27ad19fb9b3a`. Final receipt `qualification/retained-final-receipt.json` has SHA-256 `d65d3bbea6ce187feb5c6aa8af97c65141c12a11419caa5e6cdb0133ee879ccd`. The seven-test source hash is `727340556a0d8e4178b62157ba9680a59d1c43158abb1bf979b21be8c98c591f`.

## Native presentation review

The three 1200 × 820 native widget captures in `visual/` were inspected after event-loop layout and paint. Numeric channel identities remain distinct and visible; the original PNG and legacy figure retain native resolution and horizontal scrolling. The linked legacy traces and their labels remain visible. The original PNG width is 1650 pixels, so these images show a scrollable viewport rather than claiming the full curve fits at that window size. Final captures are byte-identical to the initial reviewed frames.

## Reproduction and boundaries

With the project's native Qt dependencies available, run the focused suite from the full source checkout:

```sh
QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1 python -m pytest tests/ui/test_analysis_nested_gallery.py -q -ra -p no:cacheprovider
```

The symlink fixture reports an explicit skip only when the platform cannot create a symbolic link; no such skip occurred in the recorded Linux run. The source change and receipt do not claim Windows, physical capture, or a complete product acceptance result.

The durable author packet contains the exact retained numeric and legacy packages under `fixtures/`. The receiving method accepts explicit paths so they can be replayed without reconstructing analysis output:

```sh
QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1 python methods/receive_retained_gallery.py \
  --source-root /absolute/source \
  --numeric-job /absolute/packet/fixtures/numeric.mmsession/processing/jobs/retained-numeric \
  --legacy-job /absolute/packet/fixtures/legacy.mmsession/processing/jobs/retained-prior
```

The method writes its receipt and native PNG frames as JSON to stdout; redirect that output to a new owned file when replaying. No dependency installation was performed. Original selected package paths and all read hashes remain in the receipts.

The source graph is explicitly shallow at the preserved canonical input; no historical ancestry was invented. The later main `d43bdea` kinematics merge was checked separately and changed no gallery, desktop scope or numeric-feature bytes. The qualified 3e3 parent is retained, and current publication integration remains with the lead. The local SPDX check is limited to the materialized source/evidence and exact required license structure in this sparse checkout; the full existing hosted gate remains required.

`artifact-manifest.json` inventories the evidence bytes. Initial source custody, the final source-preserving Git bundle, binary patch, retained packages and native read-back hashes are sealed separately in the durable author packet.
