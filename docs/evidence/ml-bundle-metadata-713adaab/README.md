# ML-bundle metadata receiving — 713adaab

Issue [#72](https://github.com/Jacob-Met/CaptureSuite/issues/72) corrects the
description of existing ML-bundle outputs. The production change is confined to
the manifest dictionary in `capture_analysis/ml_bundle/job.py`.

## Source and custody

| Item | Identity |
|---|---|
| Original source commit | `70f34e3b982523b544a9370d2316a1b69d79bd70` |
| Original producer SHA-256 | `c14c74760e20c818ce5e2428d0b03a8a949899b0bba6c46e37fa8fd797631c75` |
| Candidate producer SHA-256 | `38b7161f081ef038e6ce464dd3b82ca2b49f775ad8988010243743274d6fc5e6` |
| Final identical test SHA-256 | `b2104dd43f464629e284fe946126a65fa5423531f67b9fd165b702f888cd799d` |
| Runtime patch SHA-256 | `15b0c08d3caf10b78da08883460d712e133652b000469a8bf88809663589f185` |
| Archive SHA-256 | `2314ff2c4730465eb98aa55938e57a81809bad3d0d15a39583968f914a015262` |
| Archive size | 34,438 bytes; 48 regular members; 223,962 expanded bytes |

[receiving.tar.gz](receiving.tar.gz) contains the actual Parquet inputs and
outputs, original/candidate manifests, paired test source and raw JUnit/log
receipts, source-bound drivers, and consumer/source reviews.
[manifest.json](manifest.json) inventories every archive member with its final
size and SHA-256. The archive was reopened and every member was verified.

The original and candidate producer bytes before the manifest dictionary and
after it are identical. This includes input reads, nearest-feature selection,
label medians, validity, center generation, actual Parquet serialization,
schema invocation, and output-receipt/return handling.

## Actual results

| Receiving | Original | Candidate |
|---|---|---|
| Identical final eight metadata cases | 0 passed, 8 failed | 8 passed |
| Five inherited pipeline/CLI-entry/eval cases | Existing controls | 5 passed at the same candidate producer |
| Three exact original-input Parquet witnesses | Preserved | All three window files byte-identical |
| Original witness files | 12 files | All 12 unchanged |
| Manifest schema, source preservation and final file receipts | Recorded in original evidence | Passed |
| Scoped Ruff | Original two test-only lint findings retained | Passed |

The eight negative cases include false existing declarations and missing
explanatory fields. For example, the ordinary 20 Hz control already has the
right original rate but lacks the integer-hop description. Raw failure messages
remain in the archive; these counts do not imply eight separate numeric errors.

The final baseline receipt is
`70c6d0bb039b40cd9c031f36c83b9eabf26b12039e1aa9e9cc68887ee3b362fd`;
the final candidate receipt is
`472821cef185e41dece47398d3a76f032195fe51cff8a6d333bd948d961729d0`.
The earlier combined 13-case run used the same producer and an earlier test
formatting revision. Its eight metadata cases and five inherited cases are
retained separately from the final identical eight-test comparison.

One preparation attempt referenced an absent tracked `tests/__init__.py`.
It failed before pytest or producer execution. Its explicit preparation receipt
is preserved, and the successful original replay uses the actual tracked source
subset with the exact final test bytes.

### Parquet witnesses

Regular inputs emit raw motion energies [100, 200, 300, 400, 500], with mean 300.
Labels [30, 50, 70, 90, 110] are inclusive-window medians; interpolation at those
center timestamps would yield [100, 120, 140, 160, 180].
The original manifest instead declares z-score inputs and linear interpolation.

Regular and quantized requests both advance by 300,000,000 ns and produce
window SHA-256
`2ea9e0861d4a1fa4e1bb198a87d237a906de3972b1dd09372610e05bf848a65a`.
The original manifest advertises separate requested rates of 20 and 99 Hz.
The candidate records the configured integer-hop rate, original requests,
effective timing and inclusive bounds explicitly.

A short teacher input emits one median-center window, SHA-256
`b7902d8d9a1178b6d6bf16d8cfdaa14eaebeeffb60b376a1ab6f34258137e0a1`.
Its `median_fallback` policy makes clear that the configured rate is not an
observed cadence. The paired witness receipt is
`fc27a2bb9f88c7ab2308ec2b8ff66d643823feeacdd4acc77595878236d608d6`.

## Contract and limits

[The producer contract](../../design/ML_BUNDLE_METADATA.md) distinguishes
requested configuration, effective integer-hop configuration, and actual
observations. Both normalization fields use the existing schema's `none`
value; target units remain those of their incoming columns.

Current desktop/identity-evaluator consumers read unchanged identity and target
fields. The pending external evaluator was inspected at PR65 head
`d7459fa62dd7a57d5565214e10638e055ad5877c`; it binds exact source manifest/window
bytes and registry target units, without interpreting these changed metadata
descriptions. This was a source review, not execution or modification of that
owner's contribution.

All native receiving used existing macOS arm64 Python3.12.8 and installed science
dependencies. The repository's supported Windows CI remains the independent
platform gate. The producer's numeric algorithms, schemas and unrelated
internal manifest self-digest convention remain unchanged. This packet makes
no installed, model-training, scientific-performance or hardware claim.
