# Current composition

See [CURRENT.md](CURRENT.md) for receiving onto the producer's current writer-close
revision. The original qualification below is retained as a dated source-bound
record. The independent atomic receiver links the retained original atomic source;
the fixture comparison links the current production source.

# Independent receiving of CaptureSuite PR #36

## Disposition

The proposed Linux atomic-write implementation passed ten independently authored
real-file boundary cases on the local GCC 13.3 toolchain. The author's unchanged
four-case durability executable also compiled with strict warnings and passed.

One new test in the contribution needs correction before integration:
tests/cpp/test_storage_posix.cpp removes the fixed
temp_directory_path()/capturesuite_atomic_test directory before and after its
atomic-write test. A separate test invocation can already own that directory.
The native counterexample placed a fictional receipt under that name inside the
reviewer's private temporary root. The exact original test reported all six
assertions passed and exited zero, while deleting the receipt.

This companion makes only the test fixture's directory ownership explicit. It
atomically reserves a fresh random path with create_directory, then removes
only that owned path when the fixture leaves scope. Existing storage assertions
remain intact. A registered CMake receiving test exercises the actual Catch2
test with a retained sibling receipt and checks its bytes and cleanup.

Production atomic-file, disk-watchdog, clock, recovery, session and wire code
remain unchanged. This is an independent test-isolation repair for the existing
Linux-port owner, not a replacement port or a deployment.

## Exact inputs and actors

- Repository: https://github.com/Jacob-Met/CaptureSuite
- Contribution: https://github.com/Jacob-Met/CaptureSuite/pull/36
- Reviewed head: 16eb17faacff1b211005fdfdbc7f33fac9b122b6
- Reviewed tree: 7d45290f4af57d25816417cba78ad7bc29e396bf
- Receiving base: 742dd7dc0455cc8c060db06123c8432d919e93eb
- Existing producer: estate-68e476e98b77/project_delivery
- Independent receiver: estate-87eaaf0fdf63/integration
- Original offending test Git blob: 85e062fc57941d260e499c15e2f90565b7f82dfe
- Original atomic implementation Git blob:
  0fadb72fd907580605f296ff6df0b6c981c48108

The complete issue #15 ownership history, PR description/reviews/comments and
root AGENTS guidance were recovered. Existing macOS A–H, recovery scanner,
Python, daemon, host migration and product integration custody were preserved.
An attempted independent scope comment was rejected by GitHub's secondary
content-creation rate limit (HTTP 403). No accepted GitHub claim, review,
publication, merge or main-branch update is implied. No alternate write route
was used.

## Native counterexample and correction

The native run used ThinkPad UID 1000, GCC 15.2.0, CMake 4.2.3 and Catch2 3.7.1.
It copied five source files from the producer checkout only after comparing
their Git blob hashes and sizes with the published tree. All writes, builds,
fixtures and evidence stayed under the receiver's new directory:
/home/jacob/capturesuite-review-87eaaf0fdf63.

| Actual command/boundary | Result |
| --- | --- |
| Original storage source, strict GCC/Catch2 compile | Exit 0 |
| Original atomic test with unrelated sentinel in private TMPDIR | Exit 0; all 6 assertions pass; sentinel deleted |
| New CMake receiving script against original executable | Exit 1; explicitly detects deleted sibling receipt |
| Repaired storage source, strict GCC/Catch2 compile | Exit 0 |
| Repaired storage tests | 2 cases / 11 assertions; exit 0 |
| Same CMake receiving script against repaired executable | Exit 0; sibling bytes preserved and owned fixture removed |

The original sentinel SHA-256 was
a6acc843b6130187bd9fdf7ca7c4498fa75a61cb9ea0ddf2bd8851f34220874a.
Original executable SHA-256:
98699ea0c5c403fe806107fb101ac0a78554e7f4436d9ad2d0b80dd4d078e746.
Repaired executable SHA-256:
37c2dfc14b1cf33f3dde1783197708ead05e51f8a0a612815726ea3c3b83c25b.

Raw compiler/test outputs and complete command arrays are in native/.
native-evidence-manifest.json records byte counts and SHA-256 values checked
after transfer. The original passing-but-destructive result and subsequent
negative CMake result are retained.

## Independent atomic-write receiving

receiver_atomic.cpp links the unchanged production translation unit. Linker
wrappers inject failures only at its direct POSIX open/fsync/close boundaries;
all file content, renames and directory operations are real and disposable.

The ten passing cases cover binary and zero-byte replacement, failed temporary
reopen/close, parent open refusal, real directory-destination rename refusal,
two interrupted directory syncs, post-replacement directory sync/close errors,
a relative filename, and a missing parent. They distinguish preservation before
rename from complete-but-not-confirmed-durable bytes after rename.
receiver-run.json retains the actual local output. These controls do not
model physical power loss, disk firmware or multiple writers to one target.

## Replay

On Linux with the project's C++20, CMake and Catch2 3 dependencies installed:

    bash docs/evidence/storage-fixture-isolation-87eaaf0fdf63/replay.sh

This builds only the relevant unchanged storage sources and actual Catch2 test,
runs the original negative receiving control, runs the corrected native tests,
then executes the new CMake receiving test and the independent POSIX receiver.
It creates its own temporary output directory and retains logs there.

After ordinary project configuration/build, the new receiving case is part of
CTest as capture_storage_fixture_isolation. This packet's qualification used
the real CMake script and native standalone storage binary; a fresh complete
project build and Windows execution of this companion have not been run.
The reviewed producer's Windows CMake CI was still pending at the last read.
Source publication and integration remain pending the existing owner route and
the GitHub content-creation limit.
