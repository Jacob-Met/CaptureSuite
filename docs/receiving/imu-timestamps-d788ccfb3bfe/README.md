# Exact IMU timestamp receiving

CaptureSuite issue [#121](https://github.com/Jacob-Met/CaptureSuite/issues/121).
Source baseline: `3960c0c756cd4e9facbde0d76eaaa3c31ab7c167`.
Review branch: `work/imu-timestamps-d788ccfb3bfe`.

The public IMU feature extractor previously calculated timestamp medians through
float64. The original extractor changed `9007199254740993` to
`9007199254740992`; the median of the two largest signed-int64 timestamps
became `9223372036854775808`, outside the declared timestamp domain. These
original observations remain in `baseline-reproduction.json`.

The production change is confined to
`libs/python/capture_analysis/capture_analysis/features/imu.py`: select the
central integer(s), add the even pair as Python integers, and truncate a half
nanosecond toward zero. The protocol uses signed timestamps; negative pre-T0
values and signed extremes are deliberately included. Other feature values,
gap handling, window/hop selection, metadata and input arrays retain their
existing behavior. See [operator semantics](../../IMU_FEATURE_TIMESTAMPS.md).

## Maintained verification

`tests/analysis/test_imu_feature_timestamps.py` contains seven public-extractor
test methods. On the exact original source it reports 13 failing assertions
across subcases; the candidate passes all seven methods. The separate stdout,
stderr and `executions.json` preserve both outcomes and source/test identities.

Independent reviewer `source_reliability` accepted the exact production source
SHA-256 `e325a2bb5312ae4816a34b25b4ae62256a50e7eb71f1fd1deee20b7922a15c8e`.
The reviewer traced the loader's one-dimensional int64 inputs, the nonempty
callsite, copy-preserving partition, overflow-safe addition and signed
truncation. A distinct public-extractor oracle sorts Python integers and uses
`fractions.Fraction`; it shares neither `numpy.median` nor `numpy.partition`
with the implementation. Its 512 cases include 15 extrema, every pair of
those extrema, and 272 seeded varied windows with strided input arrays.

The independent oracle found 148 failures in the original and zero in the
candidate, both with ordinary Python and `python -O`. Input arrays remained
unchanged. The original review receipt and reusable script are included here.
The published script adds only the repository's SPDX header to the reviewed
script; `independent-review.json` records both identities.

Run from an existing development environment with NumPy and Pandas:

```console
PYTHONPATH=libs/python/capture_analysis:libs/python/capture_session:libs/python/capture_protocol python -B -m unittest discover -s tests/analysis -p test_imu_feature_timestamps.py -v
python -B docs/receiving/imu-timestamps-d788ccfb3bfe/check_public_median.py .
```

The separate source kit contains the pinned original and candidate package
closures and a `check.py` entrypoint. It can repeat the maintained tests and
both ordinary/optimized oracle comparisons after unpacking, without replacing
an installed CaptureSuite environment. The kit records file hashes and
includes the production patch and licensing files.

## Scope

Receiving used Python 3.12.14, NumPy 2.3.5 and Pandas 2.2.3 with the actual
CaptureSuite Python source imports. No substitute package or extractor stub
was used. The focused source closure passed the project's SPDX check. This
record does not claim the full Windows desktop, native build, all repository
tests, hardware timing calibration, or scientific validation of derived
sensor features. Existing recordings and previously retained feature results
are not rewritten. No GitHub Actions were dispatched or required for this
branch-only increment.
