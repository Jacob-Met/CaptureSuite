# Release old native image pages when saved analysis is reopened

This companion contribution targets the existing PR80 owner branch
`fix/nested-figure-gallery-401c5d17da79`, pinned at
`837fa1fbf2c5ad471cbb3924c212fc08d0e0f0ed`.
The product change is exactly two added lines in `FigureGallery.clear`:
retain the page before removing its tab, then schedule that page for Qt deletion.
The retained Sync page, export invalidation, and existing sync-plot cleanup are unchanged.

## Demonstrated user-facing defect

The current received history/gallery composition completed a real range-scoped
analysis job from synthetic protobuf/MCAP input. That job produced three nested
numeric PNGs. Opening the saved result repeatedly correctly showed three current
tabs, but Qt still owned the removed image pages and their pixmaps.

After explicit Qt DeferredDelete processing, the original code retained
**3, 6, 9, 12** image pages across the first view and three reopens; nine replaced
pages remained valid. Switching packages left **15** image pages alive.
With this repair, the same receiver observed **3, 3, 3, 3**, no replaced live
pages, and **zero** image pages after switching packages.

This is an inherited gallery lifetime defect exposed by repeated saved-history
opens. It is not attributed to either contribution's author and is not a
diagnosis of the separate CI suite deadline.

## Exact source and ownership

| Input | Commit |
| --- | --- |
| Canonical main selected for this receiving | `11cc78297d8d214407aea693548af4de855d61da` |
| Saved-history PR71 diagnostic successor | `8747cb95bfb2ac91aa4f1ff604ad677f3597fa12` |
| Nested-gallery PR80, including received PR85 correction | `837fa1fbf2c5ad471cbb3924c212fc08d0e0f0ed` |
| Actual native combined baseline | `9d90abb574f7fbadc85f323e73b4b268acc0f5b3` |
| Combined baseline tree | `7eee55fbe0b28011edf3aa5bb33f9ad409ca444e` |
| Actual native combined repair | `a5e6e7ed4052a71c22c3d385d562f4de1263a7aa` |
| Combined repair tree | `fa4d573334b06ce2879dfb6542de7489780e2c52` |
| Narrow native source/test child of PR80 | `123d39ee1ff38b9f622a778635fbb1ef60b438cd` |

The combined baseline was built through real merge parents. Its 1,175 leaves
preserve the exact current-main, history, and gallery input union. The only
content conflict was the progress document, resolved as the complete current
prefix followed by both owners' exact additions. Original and diagnostic source
union receipts are retained in the raw evidence.

Owner `estate-401c5d17da79` retains feature integration and the proposed-main gate.
This worker owns only the independent receiving and narrow page-lifetime repair.
Current main later advanced to `a2c89957c2cfe6fd5347d4ac317982449d3baa3a`,
adding the source picker and saved-parameter comparison. The owner is already
composing those changes. The 11cc-based results here do not qualify that later
Analysis-screen/inspector composition. PR71 also advanced to `c2e1d9c1`,
removing its diagnostic fixture and changing its suite deadline; it has no
product runtime delta from the history input tested here.

## Qualification

| Evidence | Original | Repaired |
| --- | --- | --- |
| Same native 18-check cross-feature receiver | 16 pass, 2 lifetime failures | 18 pass, 0 failures |
| Focused maintained native Qt regression | fails with 6 pages where 3 are expected | 1 pass |
| Root exact-byte source review | original gallery SHA256 `002327b8e6303412269c0ca8c4a105d9e8eeb96491eec0836e39ce199e2c18fd` | only the two specified lines added |
| Independent semantic review | confirms Qt retains removed pages | accepts deferred page deletion and unchanged Sync/export boundaries |

The native receiver uses Python 3.12.15, Qt/PySide6 6.12, real synthetic MCAP,
the actual analysis QThread and actual export QThread. It checks range
provenance, saved-result association, native PNG decoding, exact exported PNG
bytes, read-only parameters, unchanged retained/raw inputs, history/export
dialog invalidation, page lifetime, package switching, and source immutability.
It uses offscreen Qt Widgets. The purpose-limited environment excludes unused
WebEngine/PDF/Addons; it is not a full hosted Windows or hardware environment.

An initial receiver attempt completed the real analysis job, then stopped on
a receiver-only snake_case versus saved camelCase parameter-key mistake.
Its source and non-accepting setup-error receipt are retained separately.
The corrected receiver was then frozen and used unchanged for both the
16/18 original and 18/18 repaired runs. No prior 14-test result is relabeled.

## Evidence layout and reproduction

- `receiving-summary.json` is a compact projection of the original complete
  receipts, with their byte hashes and all checks.
- `receive_history_gallery.py` is the exact corrected receiver.
- `raw-evidence.tar.gz` contains the complete original records, logs, source
  manifests, synthetic fixture/job outputs, PNG frames, exported ZIPs, and the
  initial receiver setup failure. `raw-evidence-manifest.json` binds every member.
- `root-gallery-source-review.json` and
  `coordination-gallery-semantic-review.json` are copied unchanged from the
  two independent reviewers.
- Focused pytest logs, process receipts, and JUnit are retained separately.

Run the maintained focused regression from this branch with the normal
repository dependencies:

```sh
QT_QPA_PLATFORM=offscreen python -m pytest tests/ui/test_analysis_gallery_lifetime.py -q
```

The combined receiver must run against the recorded combined source, because
the companion PR80 branch intentionally does not introduce PR71 history:

```sh
python receive_history_gallery.py --source /path/to/combined-source --out /path/to/new-evidence --variant unique-run
```

The native source bundle is retained at
`/home/jacob/hamon-capture-composition-f5c5ccd6-proof/current-history-gallery-source.bundle`.
Its SHA256 is `6afb8d675b1d9549ba8cf5a74627c363d5a5cabb39e5ec36ac3717fb989a47ac`;
the verified prerequisites are `a2fd6c58ccc97c7262b97570a85d8aae8dfb978c`
and `9c44354cb101c76beff79265de0040b6839d249f`.
It retains the native combined repair ref at `a5e6e7ed`.

The later owner composition, its hosted gate, main integration, and installed
release remain separate actions. This contribution changes no runtime service,
capture state, dependency manifest, or CI workflow.
