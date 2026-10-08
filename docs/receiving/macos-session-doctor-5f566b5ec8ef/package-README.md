# CaptureSuite session doctor — Mac receiver

This directory contains the native arm64 command-line receiver built from CaptureSuite commit `d43bdea867d6198a707a5f55e29216c76054517e`. It was qualified on macOS 26.6.2. The executable and its 86 non-system dynamic libraries are kept together, so this received build does not require Homebrew on its runtime search path.

## Run the received tool

Keep `bin/` and `lib/` together when moving this directory. Set the following path to the location where you extracted this receiver:

```sh
receiver_dir="/absolute/path/CaptureSuite-Session-Doctor-d43bdea-macos-arm64"
"$receiver_dir/bin/session_doctor" --help
```

The existing CLI accepts one session-directory path. Recovery can truncate an unsealed segment and write recovery metadata in that directory. Use an explicitly selected working copy when examining retained data:

```sh
session_copy="/absolute/path/to/a-working-copy.mmsession"
"$receiver_dir/bin/session_doctor" "$session_copy"
```

Exit 0 reports a successful or already-finalized result. No arguments print usage and exit 1. An ordinary recovery refusal prints `recovery failed: ...` on stderr and exits 2. A missing runtime library is an operating-system loader failure before the CLI starts.

## Try the included finalized fixture

The repository fixture is small, synthetic and already finalized. Copy it to a new private directory before invoking the tool; this demonstrates the no-op receiving path and leaves the packaged source intact:

```sh
fixture_parent="$(mktemp -d /tmp/capturesuite-doctor.XXXXXX)"
cp -R "$receiver_dir/source/tests/fixtures/mini_session" "$fixture_parent/example.mmsession"
"$receiver_dir/bin/session_doctor" "$fixture_parent/example.mmsession"
```

## What was actually qualified

- The unchanged portable CMake target configured and built with AppleClang 21.0.0, CMake 4.2.3 and Ninja 1.13.2. All 17 available native CTest cases passed.
- A copy under a path containing spaces and Unicode ran from an unrelated directory with only system command directories on `PATH`. Dynamic-loader tracing showed all 87 non-system images came from that copy.
- Actual CLI controls covered no arguments, a missing session, malformed JSON, exact preservation of the finalized repository fixture, authored unsealed-tail recovery, sealed-file and pre-existing temporary-symlink preservation, and a byte-preserving repeated call.
- The first process harness passed seven cases, then stopped on an incorrect assumed library filename before the missing-library operation began. Its original failure is retained. A focused replay using the unchanged package manifest verified missing-library refusal and exact restoration.
- The original build executable, qualified package runtime files and 96 canonical source inputs are pinned separately. Packaging changes only the copied Mach-O library references and local ad-hoc signatures; it does not change the C++ implementation.

## Scope

This is a distinct receiver for the already-merged canonical portable implementation. It does not replace the older Mac worktree or its unmerged recovery implementation. The Linux GNU linker-wrapped failure tests were not compiled on macOS. The qualification does not cover Windows, daemon or GUI operation, camera/radar hardware, Python analysis, arbitrary damaged recordings, other Mac architectures, or older macOS releases.

The copied Mach-O files have locally verified ad-hoc signatures. This packet is not an Apple-notarized installer and does not install a service, alter a default executable, or modify system trust settings.

## Contents and provenance

`CONTENTS.json` records the size, SHA-256 and mode of every payload file except the manifest and checksum list themselves. `SHA256SUMS` also covers `CONTENTS.json`. From this receiver directory, `/usr/bin/shasum -a 256 -c SHA256SUMS` verifies the file bytes.

`source/` contains the 96 exact canonical inputs used for this portable target, including its source, schemas, CMake definitions and fixtures. It is a targeted source snapshot, not a complete repository checkout. `source-dependencies/mcap/` contains the exact 13 MCAP headers used. See `BUILD.md`, `source-manifest.json`, `runtime-manifest.json`, `dependency-records/` and `notices/` for the build and library correspondence.

`qualification/` retains the native build and receiving receipts, including the original harness failure and focused replay. The archive extraction receipt lives beside the archive because it can only be written after the completed archive is extracted and exercised.
