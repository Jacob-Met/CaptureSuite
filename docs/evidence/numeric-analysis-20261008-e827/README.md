# Generic numeric analysis: author receiving

Coordination: [CaptureSuite #43](https://github.com/Jacob-Met/CaptureSuite/issues/43).
Implementation author: `estate-e82707f2bc62/source_discovery`. Independent numerical
receiving belongs to `coordination_discovery`; actual CLI/visual receiving belongs
to `runtime_discovery`. Their fixtures and receipts are preserved separately.

## Concrete baseline failures

The existing numeric loader passed nonexistent `stream` and `quality_flags`
arguments to `LoadedEmg`, selected the wrong MCAP schema-name substring, swallowed
its own RAM refusal and invented a rate or nanosecond grid when timing was absent.
The bundled registry routed numeric streams into the EMG reader, so an ordinary
feature job could finish with no numeric table and no numeric-reader error.

Baseline analysis source was copied from exact `d3edda561322a80bfc1491ae4f4c7b0bb94943ea`;
the four modified existing numeric files were independently checked unchanged at
`c43b2819b149e1e87d7f957d8b3583881c29ffb4` and receiving main
`52203f5ceedfa0da8f1813e700a41ec8c364263e`. The new handler has no baseline blob.
The merged stream-gap fix from PR #41 is preserved in the final composition.

## Frozen author experiment

`tests/analysis/test_numeric_batch_pipeline.py`, SHA-256
`43369bd0fea48d2c8b7dee1d8128b3bb131b508b7b0a14512fc457fcfdb0ba3c`,
was copied unchanged to the isolated baseline and candidate.

| Source | Passed | Failures | Errors | Total |
|---|---:|---:|---:|---:|
| Original numeric path | 2 | 5 | 19 | 26 |
| Five-file candidate | 26 | 0 | 0 | 26 |

The tests use real MCAP writer/reader, native protobuf messages and descriptors,
public loader/registry/pipeline APIs, real Parquet/CSV output and actual matplotlib
PNG figures. One focused pre-I/O budget test replaces only the message iterator
with an assertion that iteration must not begin after a refused minimum budget.
No production loader, handler, feature writer or plotted output is replaced.

Coverage includes the production `capture.v1.data.NumericBatch` schema name;
the JSON alias; native timing and explicitly flagged nominal-rate fallback; valid
empty results; finite required rates; actual and cumulative buffer estimates;
malformed frame/timestamp/channel layouts; nonfinite values; signed timestamp
overflow; actual gap masking/splitting; finite extreme-value reductions; schema
dispatch; unrelated modality routes; durationless packages; multiple stream IDs;
real hashed feature/figure outputs; and unchanged raw source bytes.

`author-baseline.log` preserves the original failures, and `author-candidate.log`
preserves the successful identical replay. Source Git blob and SHA-256 identities
are in `source-freeze-v1.json` and `source-freeze.json`.

## Final successor and independent checks

The final successor adds a backwards-compatible optional `xlabel` in
`plots/modality.py`, and the numeric handler supplies an elapsed-time label plus
the exact first-retained session timestamp. That measured output-fidelity finding
came from independent visual review. Existing plot callers retain their default.
No loader, feature, registry or manifest bytes changed in this successor.

The independent receiver replayed the affected actual `all` process on the exact
six-file composition and inspected both real output PNGs. Its earlier complete
seven-case CLI result remains bound to the five-file source snapshot. Independent
nine-case MCAP/numerical receiving also retains its original unchanged test and
baseline/candidate logs, with a formatting-only native-test adaptation if required
by the repository's Ruff configuration.

The exact unchanged repository Ruff configuration passes the final scoped source
and author/CLI tests. No workflow, dependency, protocol, session schema or job
orchestration was weakened or changed. All new tests use ordinary test methods;
they do not add reporting subtests that conflict with the strict native JUnit
receipt validator.

## Qualification boundary at publication

Local Python 3.12.14 used real MCAP 1.5.0, protobuf 4.25.9, NumPy 2.3.5,
pandas 2.2.3, PyArrow 25.0.1 and matplotlib 3.10.8. Numeric protobuf bindings were
generated from the repository's exact schema with grpcio-tools 1.62.3; they were
not substituted with a test decoder.

The isolated local environment lacks `jsonschema`. Local CLI receiving explicitly
allows only its known missing-validator warning; the reusable native CLI test
defaults to requiring the real validator and both exact repository schema files.
Existing hosted Python/Windows C++ gates, schema generation/drift checks, and the
full new test suite remain mandatory for the published current-source candidate.
Their final result is recorded on the pull request linked from issue #43.

External scope annotation hit GitHub's explicit secondary content-creation limit;
publication writes were held for cooldown. The final narrow plotting-helper
extension was coordinated with the lead and receiver, and a fresh open issue/PR
path search found no competing helper owner. The source/evidence remained frozen
while writes were held. Shared filesystem exhaustion caused new receipt assembly
to use the author's own temporary memory-backed directory; no other owner's
source or artifacts were removed.

These are synthetic, source-offline receiving results. They establish usable
analysis behavior and preserved raw bytes; they do not establish hardware timing,
sensor calibration, an installed estate host, or deployment.
