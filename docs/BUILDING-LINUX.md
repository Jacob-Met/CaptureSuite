# Building the portable CaptureSuite libraries on Linux

The Linux presets build `capture_core`, generated C++ protocol bindings,
`capture_storage`, `session_doctor`, and portable C++ tests. The full capture
application remains Windows-first. Daemon/control transport, desktop and
physical workers are outside this Linux qualification; enabling camera or
radar workers on non-Windows fails configuration explicitly.

| Target | Linux verification boundary |
| --- | --- |
| `capture_core` | Clock, framing, environment, FSM and logging tests |
| `capture_proto` | Native C++ generation with the installed Protobuf toolchain |
| `capture_storage` | Compiled library; actual file replacement/disk checks |
| `session_doctor` | Actual process on disposable synthetic session fixtures |
| POSIX durability | File/directory sync failures and interrupted sync |

The portable clock converts `steady_clock` to nanosecond ticks at a reported
frequency of 1,000,000,000. Existing serialized `qpc_*` names and the
FILETIME-compatible wall-anchor value are retained. Wire/session schemas and
the Windows implementations are unchanged.

## Dependencies and build

CMake >=3.28, a C++20 GCC/Clang toolchain, Ninja, Protobuf/protoc, Catch2 3,
spdlog, nlohmann-json, SQLite, BLAKE3, Zstandard and LZ4 are required. On an
Ubuntu/Debian system providing these packages, the package names are:

```sh
sudo apt-get install build-essential cmake ninja-build pkg-config git \
  libprotobuf-dev protobuf-compiler libspdlog-dev libfmt-dev \
  nlohmann-json3-dev catch2 libsqlite3-dev libzstd-dev liblz4-dev libblake3-dev
scripts/build-linux.sh
# Explicit checkout/configuration; default compiler parallelism is two.
CAPTURE_BUILD_JOBS=2 scripts/build-linux.sh /path/to/CaptureSuite release
```

The helper does not install system packages. Without `MCAP_INCLUDE_DIR`, it
obtains MCAP `releases/cpp/v2.1.1` at exact commit
`b2953496735e7b89d5b2ea58be73abed85317c5f` under `build/deps/mcap` (or
`$CAPTURESUITE_DEPS/mcap`). A mismatched or dirty existing checkout is refused
and left untouched. An explicit `MCAP_INCLUDE_DIR` must contain
`mcap/mcap.hpp`; its provenance is separate from the pinned default.
CMake's Linux adapters map the existing MCAP/SQLite targets to these headers
and system libraries. A separately built BLAKE3 can use `-Dblake3_DIR=...`.

The helper validates configuration/job count, preserves existing build
directories, enables tests, and runs CTest with `--no-tests=error`. Its success
marker is `CAPTURESUITE_LINUX_PORTABLE_BUILD_OK`. It does not run Python tests.
For manual use with existing dependencies:

```sh
export MCAP_INCLUDE_DIR="$PWD/build/deps/mcap/cpp/mcap/include"
cmake --preset linux-debug
cmake --build --preset linux-debug --parallel 2
ctest --test-dir build/linux-debug --output-on-failure --no-tests=error
```

## Durability and process tests

POSIX atomic replacement retains one writable file description through all
writes, `fsync`, and checked `close`, before rename and parent-directory sync.
Short writes and interrupted writes/syncs are retried; zero-progress writes
fail, and a failed close is not retried. Any writer failure preserves the old
target and removes the owned temporary file. A failed parent sync returns
failure after replacement and explicitly reports that complete new bytes
already replaced the destination but durability is uncertain. The API expects
one writer per path. Keeping the original writer also preserves the kernel's
[writeback-error observation boundary](https://cdn.kernel.org/doc/html/latest/filesystems/vfs.html#handling-errors-during-writeback).

The Linux regression executable wraps real `write`, `fsync`, and `close` calls;
all other I/O uses disposable real files. Its ten cases cover durable success,
write/sync/close failures, short writes, interrupted operations and zero progress.
The initial donor failed three of the original four sync controls. Independent
actual-process review then found that closing an `ofstream` in its destructor
could ignore a writer-close error before reopening the temporary file for sync.
The revised retained `session_doctor` passes that same injected writer-close
error: exit 2, prior recording manifest byte-identical, no temporary file or
false-success output. Independent normal-success and post-rename directory-sync
failure controls also pass, with both frozen MCAP files byte-identical.

No production API test hook is added. The committed `session_doctor` process
test checks exit codes, unchanged finalized-fixture hashes, truncation of a
synthetic incomplete MCAP header, recorded recovery state/report, and an
idempotent second invocation. It does not replace the separately owned recovery
scanner/CRC tests.

## Evidence and limits

[The revised receiving receipt](evidence/linux-port-68e476e98b77-r2.json) records
the writer-close review blocker, repair, exact source/binary hashes and native
outcomes. [The initial receipt](evidence/linux-port-68e476e98b77.json) is retained
as historical evidence for donor composition, dependency/compiler pins and the
initial qualification; its binary was superseded by the reviewed repair.
The initial whole-tree `CAPTURE_WERROR=ON` GCC probe exposed an existing
`logging.cpp` format-truncation warning. Qualification uses the project's
normal `CAPTURE_WERROR=OFF` default; that stricter gate remains separate.
The durability executable is also compiled with
`-Wall -Wextra -Wpedantic -Werror`.

This portable build establishes neither macOS support, Windows regression
acceptance, daemon/desktop integration nor physical capture/hardware timing.
Python and existing macOS A–H candidates retain their separate ownership.
