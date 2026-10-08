# Preserve diagnostic-bundle destinations

The diagnostic CLI requires a new output path outside the selected session
package. An occupied file, directory or link is refused, including dangling
Windows directory junctions. A destination resolving inside the package is
refused even when it does not yet exist. The CLI exits with code 2 and tells
the operator to choose a new path. Library callers receive BundleOutputError;
a file appearing at final publication raises FileExistsError.

From the repository root with the supported Python environment:

    python tools/diagnostic_bundle C:/sessions/example.mmsession -o C:/support/example-new.zip

The default inventory, participant-name redaction and explicit --include-raw
and --include-identifiers options retain their behavior. The final destination
is created exclusively so a competing file is not replaced. This is not an
atomic-completion or crash-rollback promise: a write failure after this process
creates its new output may leave a partial archive for inspection. Concurrent
replacement of ancestor directories is outside this bounded repair.

## Exact source

Parent: 3960c0c756cd4e9facbde0d76eaaa3c31ab7c167.
Tree: d1af33caaf7154e83def1dab035920907d417e8d.
This parent preserves merged video-review PR90.

The only runtime change is output admission, exclusive ZIP creation and CLI
refusal in tools/diagnostic_bundle/__main__.py. Final SHA256:
3e50de8b66e95b8f76873db3e345e99b16174227ad2cada49b22d0105d171f4e.
Original SHA256:
14ab7150f36f4076ffcd86807527655a61bb5486d67090978ba2b59775562ce7.

Six existing helper functions, archive selection, redaction, journal handling
and package traversal are unchanged. No storage/recovery, schemas, daemon,
desktop, ML, dependency or workflow changes are included. Session-doctor issue93
remains separately owned by estate-69570d292200.

## Native receiving and preserved failures

Windows Python3.13.15 author receiving passes all 17 final unittest methods,
with no failures, errors or skips. The original 16-method baseline records
4 passes, 10 assertion failures and 2 directory errors. The added dangling
directory-link regression records a separate original PermissionError.
The first 16-method candidate result remains frozen separately.

Independent receiver estate-7c2609b6545f/la7_runtime froze its contract before
opening candidate code or author tests. Original: 5 of 18 cases pass. The final
source passes all 18, plus the separately attributed dangling-directory-junction
replay. Real regular/dangling leaf symlinks and a directory junction execute;
no platform gate is counted as a pass. Actual CLI refusals return 2 with a clear
message and no success output. Fresh external, raw/identifier, competing-writer,
source preservation and temporary-staging cleanup controls pass.

The first candidate, fd6d1c6693c0907af061d0badbf50e7de21243435127b55de4ba847b365230eb,
passed the original matrices but a post-contract probe found that a dangling
directory junction was treated as absent and redirected output to its missing
target. The final correction uses lstat before resolution; only FileNotFoundError
admits an absent leaf. The same counterexample now refuses without creating its
target or changing the junction or source.

The unchanged inherited diagnostic-bundle test function was also executed
directly against the original and first candidate with its actual temporary
SQLite fixture. It passed both; this was not pytest collection. The final
six-helper byte/AST preservation remains separately proved. All source hashes
before and after the final executions match.

The independent injected write failure leaves a newly owned 22-byte empty ZIP
while temporary staging is cleaned and source/unrelated files remain exact.
This pre-existing nontransactional behavior is recorded, not labeled cleanup
of the final output.

## Replay and limits

With the project's declared Python3.12 environment:

    python -m pytest tests/protocol/test_diagnostic_bundle.py tests/protocol/test_diagnostic_bundle_output.py -q

The new test is standard unittest-compatible with tools on PYTHONPATH. Native
source, scripts and original/final receipts are held at:
C:/Users/minec/hamon/stage/capturesuite-diagnostic-output-7c2609b6545f

The historical Python3.13.15 results remain outside the project's version pin.
Later native receiving used existing official Python3.12.8, the unchanged project
pytest configuration and autouse state isolation. Both maintained test modules
passed all 18 tests; touched-file Ruff passed. Source/config bytes stayed exact.
The full protocol/UI/daemon and hosted Actions gates remain unrun.

## Installed standalone preview command

An owned, versioned command is now available on LA7:

    & 'C:/Users/minec/hamon/tools/capture-diagnostic-7c2609b6545f/capture-diagnostic.cmd' '<selected .mmsession>' --output '<new external archive.zip>'

It runs the exact module through its own official PSF Python3.12.8 runtime.
The retained NuGet archive SHA256 is
406856be971d957e0bee7a5cefe20a5ec78d70a495e9e33cd0e53d31faec049d;
a fresh official catalog read verified its SHA512 before installation.
It changes no global PATH, registry, services or existing owner's runtime.

Actual author consumer receiving passes 13 checks: package to ZIP, separate
installed-interpreter reopen, inventory/redaction, the real SQLite event summary,
explicit raw/identifier opt-ins, and occupied/source/internal/dangling-junction
refusals. All nine package files retain bytes/mtimes and all 1,327 installed
payload files retain hashes. Independent installed-command receiving is separate
from the completed independent source receiving. This is a standalone preview,
not a complete CaptureSuite deployment or hardware qualification.

New receipt root:
C:/Users/minec/hamon/stage/capturesuite-diagnostic-uptake-7c2609b6545f

- supported312-gate/RECEIPT.json: 2,166 bytes, SHA256
  9f00374e9967afabc8a15a2f934991064e42989746d95612ae4cdf6c1cf08a12.
- consumer-receiving/RECEIPT.json: 13,838 bytes, SHA256
  602f5a8712078ced894fd6d90d0c7c7e40172816e7eabc1b56acf2405b0803d0.
- UPTAKE-ACCEPTANCE.json: 2,159 bytes, SHA256
  09b7e8e3b2915769bb5e331abbee529c592306d9cd265b8bec6709f71815c7ad.

The earlier four-path packet SHA256295dfcfe3f9a3b27732ea4819973e7bd7a763939beac40baaac00d25b936dd1b
and its guide/PROGRESS are preserved under final-v2-frozen. This successor updates
only documentation; runtime3e50de8b and tests25bf0ef remain unchanged.

The separate issue93 Windows prerequisite check directly found CMake3.27.2-msvc1
and MSVC19.38/toolset14.38, below declared CMake3.28 and VS2022 17.10 minimums.
It stopped before configuration or compilation. Initial PATH/vswhere absence
was followed by actual Visual Studio executable reads; no compiler-absence
claim or weakened toolchain gate was made.

Only authored inert packages were used. Application-log lookup was redirected
process-locally to an owned empty directory. No live sessions, operator logs,
settings, credentials or screen/audio devices were used. Root retains publication
under the no-Actions hold; unrun gates stay separate from source review.
