# ML feature ordering: source and native receiving

Issue [#86](https://github.com/Jacob-Met/CaptureSuite/issues/86) addresses a
data-pairing defect in the ML-bundle producer on current main
`11cc78297d8d214407aea693548af4de855d61da`.

The loader previously handed stored row order to `numpy.searchsorted`.
Actual radar features can retain an embedded-session timestamp order different
from MCAP log order. A private MCAP fixture passes through the real radar
extractor, native feature-table writer and public analysis Job API: the final
window originally selected energy 4 instead of the nearest sample's energy 9.

Only four lines are added to `_load_feature_series`: detect an inversion,
then apply the same stable integer timestamp ordering to both arrays. Ordered
inputs avoid sorting. Duplicate relative order and the existing later-time
equal-distance choice remain unchanged. Feature writers, stored source files,
kinematics, target medians, validity, centers, public arguments, schemas and
the unrelated internal manifest self-digest are unchanged.

## Exact source

| Input | SHA-256 |
|---|---|
| Original producer | `38b7161f081ef038e6ce464dd3b82ca2b49f775ad8988010243743274d6fc5e6` |
| Candidate producer | `ed67d94ded834d63599797bbd8efb7b26f125bd216f52bcb7f01febb928922ce` |
| Final paired test | `7a5e226afb9c0f49eadf6d4c25b8bc22575f1fdd04afdac854cf8aa4adee58be` |
| Runtime patch | `3232f15dc5b9c443b04d63aa0f23503b9fc19926cda0f83882a4708fa7b5c35e` |
| Paired artifact readback | `e9f1b94c200261104ce9504b8f568a6738b957b26ee8506e8d317a8f6cb8b355` |

## Actual native results

All runs use an isolated Linux Python 3.12.10 environment. The exact standalone
runtime archive identity, declared package pins, installed versions, successful
dependency consistency check and complete installation log are retained.
This environment does not alter an installed application or shared runtime.

| Run | Passed | Failed | Errors / skips |
|---|---:|---:|---:|
| Initial original-source receiver | 4 | 11 | 0 / 0 |
| Corrected final original-source receiver | 6 | 11 | 0 / 0 |
| Same final receiver on candidate | 17 | 0 | 0 / 0 |
| Separate inherited consumers on candidate | 14 | 0 | 0 / 0 |

The initial receiver included four 2 ns windows below the existing schema
minimum of 0.1 s. Those four cases stopped at an unexpected schema warning
before their intended alignment assertion. Its original test, source, log,
JUnit, artifacts and correction note remain in `evidence/baseline/` and
`evidence/initial-receiver-correction.json`. No schema or product change was
made to accommodate that receiver error.

The final tests use valid 0.2 s windows. They cover shuffled and reversed rows,
ordered controls, exact high integer timestamps, adjacent nanoseconds above
2^53, stable duplicates, equal-distance choices, numeric-column mean fallback,
a singleton, and the actual MCAP-to-Job API path. The final same-test baseline
and candidate receipts retain process exits, full source maps and unchanged
source checks.

The separate inherited run selects the complete metadata and
pose/kinematics/ML test modules plus
`test_real_pose_kinematics_bundle_to_external_eval`. It does not repeat the
17 focused receivers.

Readback of all 17 retained output Parquets found six ordered controls
byte-identical and eleven unordered outputs corrected. Every non-energy
column remains exact. All 43 original input files in the paired runs match
byte-for-byte. Input and final output inventory assertions also execute inside
the tests.

## Capsule

[receiving.tar.gz](receiving.tar.gz), SHA-256
`d80a4d2b79d4491b66ea8227ff92471ebdbb6edd8fe2fce75327bbe755485097`,
contains 296 regular files, 1,502,844 expanded bytes and 265,323 compressed
bytes. [manifest.json](manifest.json) inventories every member's exact bytes
and SHA-256. Every member was reopened and compared after archive creation.

The capsule includes original/candidate producer snapshots, identical final
test bytes, the original rejected receiver, exact runtime/documentation
patches, receiving/readback drivers, all three initial/final paired fixture
and output sets, process/log/JUnit/source receipts, and runtime/dependency
provenance. The inherited run's complete logs, process, JUnit, source maps and
artifact-inventory receipt are included; its 309 runtime outputs remain in
native custody at the recorded private path.

Independent review and the existing full supported Windows workflow are
separate integration gates. These native results establish deterministic
alignment on the declared fixture inputs; they do not establish hardware
synchronization, clinical validity or installed-desktop adoption.
