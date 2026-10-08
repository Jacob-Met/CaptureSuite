# Mainline receiving of the storage fixture repair

## Later accepted-main alignment

The next native merge receives pinned main 6b22d61260bff5b8304c33c48ed74366e08b414b
(tree 7b544a0b0ac87160f636b41dbb70fb07be2cfce0), including accepted registry PR47.
Its twelve incoming paths are Python registry/tests, their receipts and progress.
All incoming blobs and the complete upstream progress suffix are preserved.
Every C++/CMake/build input remains identical to the qualified revision below.
No native build was repeated and no later main was chased.
PINNED-MAIN-ALIGNMENT.json records exact source correspondence and ownership.
The existing nineteen-case native result below remains a run at its original
source tree, and a fresh hosted gate remains a publication-stage requirement.

## Current composition

This revision composes the fixture companion from PR42 at
0dcee1ca5165f260c0cfb7bea3c02e364c959538 with accepted main
ac52c3ca7164a6ab457d11a8a1448957093eb592, tree
dc53011c8cebcb1b8d7d7683c7dd0dcdb6947bba. Main contains the owner-merged
Linux port PR36 and separately owned POSIX alias repair PR44. Their production
and fault/identity receivers are preserved exactly.

The reviewed fixture and CMake receiver retain their earlier blobs. The only
existing paths changed against accepted main are the portable storage test,
the additive CMake registration and the additive progress log. The complete
upstream progress file is retained as an unchanged suffix. All 564 unrelated
upstream leaves are preserved.

The lead previously reviewed this fixture's atomic directory acquisition,
scoped cleanup and actual sibling-evidence receiver with no blocker. This
composition does not replace the producer's durability or alias-safety
receiving. Historical evidence in CURRENT.md and the original native/ and
current-native/ directories stays at its recorded source pins.

## Native result

The documented Linux build completed on the ThinkPad as UID1000 with GCC15.2,
CMake4.2.3 and the project's normal CAPTURE_WERROR=OFF. All **19/19 CTest entries
passed**, including capture_storage_fixture_isolation,
capture_session_doctor_portable, the inherited POSIX durability receiver and
the inherited POSIX identity receiver.

The command was:

    bash scripts/build-linux.sh <this-checkout> debug

The build used two jobs, a private compiler temporary directory, installed
system dependencies and an existing pinned MCAP header checkout read-only.
MCAP commit b2953496735e7b89d5b2ea58be73abed85317c5f remained clean. No package
installation, physical capture, protected-directory change or global-default
change was made.

The source tree before adding these receipts was
c84a6a10251b0259380d65c318793d7d45778929. Every composed leaf was checked
against its exact Git bytes or its explicitly declared CRLF checkout form.
All compiled fixture, storage, test and CMake inputs match their exact raw
Git blobs; the unstaged diff is empty.

The first post-build guard refused an inherited PowerShell file because Git
stores LF and the repository checks it out with CRLF. A blanket normalization
probe then refused an inherited raw CI log whose original bytes are preserved
in Git. The corrected guard accepts exact raw Git blobs first and otherwise
requires the explicit CRLF attribute and exact normalized equality. All eight
declared CRLF checkout differences and both refusals are retained in
mainline-native/post-build-guard-refusal.json. No rebuild or source edit was
needed. The first runner is recorded as exit1 after its successful build.

## Hosted gate and publication boundary

The original published companion has a completed supported Windows gate:
[run37756929537](https://github.com/Jacob-Met/CaptureSuite/actions/runs/37756929537),
finished 2026-10-08T09:47:56Z. Its actual checkout
ca577a2755bb8f0adbaf4d4466a14ddd2ab222fe has the exact companion tree
04219699e07206bc01c6459ac1d2069671541972. Actual logs report Windows CTest26/26,
including this fixture receiver; native daemon/recovery6/6 with zero skips;
and Python208pass with six daemon-build-dependent skips.

That is a run of the earlier companion. This current mainline composition's
publication was held after the lead observed a new GitHub secondary
content-creation rate limit in another lane. No retry or alternate publication
route was used. The complete source, native logs, Git bundle and planned
exact-parent publication remain in the receiver's own native checkpoint.
The PR and later integration receipt record subsequent publication and hosted
gate results without changing these historical facts.

All data used here is disposable fixture/replay data. Linux native and hosted
Windows fixture results do not establish physical-device, power-cut, macOS,
or whole-application acceptance.
