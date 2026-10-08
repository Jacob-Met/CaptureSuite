# Independent receiving for camera runtime packaging

This contribution adds a native dependency regression and receiving evidence for
[CaptureSuite PR #38](https://github.com/Jacob-Met/CaptureSuite/pull/38), owned by
`dd846795-production`. Its reviewed head is
`677026871c39362e9b6e2c816b841fc6393050f0`, based on
`d3edda561322a80bfc1491ae4f4c7b0bb94943ea`.

The implementation copies the existing five camera DLLs beside both staged
executables. This evidence uses compiled shared libraries to test whether the
packaged executable can actually resolve those fixture dependencies. The four
reusable fixture files live in `tests/cmake/camera_packaging/`.

## Source identity

| Subject | SHA-256 |
|---|---|
| PR #38 camera CMake | `ddb68fccae5e9b5ae66f81ff4859060f27dcc425d6a41c607e9c9c883a6bd842` |
| Camera plugin manifest | `6f921746e815083b55f5d81d10c660e9b448ff315b48a2082090b34b350eae03` |
| Original camera CMake | `7eff92acdb7d6b1c328132b8f5a78b3e3a85ffce15fb7fb95f0485934154dfad` |

`source-pins.json` also records Git blob identities. `ownership-refresh.json`
records the PR and issue state observed before preparing this handoff. Production
implementation and integration disposition remain with the existing PR owner.

The earlier local candidate `8167c9ad8b44433409e8f3d66f66c4254f879db3` was
independently qualified before the final ownership refresh found PR #38. Its
only product-file difference from the published PR is one CMake `COMMENT`
string. All runtime commands and the plugin manifest are byte-identical. The
receiving records distinguish that earlier evidence from execution on PR #38.

## Native boundary

The fixture compiles an executable that calls a distinct function in each of
five native shared libraries named `abseil_dll.dll`, `blake3.dll`,
`libprotobuf.dll`, `lz4.dll` and `zstd.dll`. The actual camera CMake file and
plugin manifest are copied unchanged into the fixture. SDK interfaces and
camera translation units are substituted only to compile the packaging probe.

The checks verify exact bytes in both package layouts, successful launches from
an unrelated directory, and a loader failure when a plugin-local dependency is
withheld. The independent controls also inspect the ELF dependency table and
origin-only search path, remove and restore each individual library, withhold
the original and legacy runtime trees, relocate the plugin package, and build
separate Debug and Release configurations using paths containing spaces.

These are Linux ELF fixture results. They do not qualify the actual Windows
camera worker, Windows DLL loader, MSVC/vcpkg/GStreamer runtime closure,
Media Foundation, daemon handshake or physical capture. The existing PR's
real Windows receiving gate remains open.

## Reproduce the maintained regression

From a checkout containing this contribution, with Python 3.12, CMake 3.28+ and
a native C++ compiler:

```sh
python tests/cmake/camera_packaging/check_packaging.py --work /absolute/new/camera-package-check
```

The output directory must not already exist. Use `--cmake` to select a CMake
executable and `--source` to select another source tree. A successful run exits
0 and preserves its full commands, outputs, source hashes and checks in
`report.json`. A package regression exits 1; configure/build failure exits 2.

The independent `review_packaging.py` accepts `--root`, `--cmake` and `--ninja`.
It consumes a fresh prepared root containing `candidate source with spaces/`,
`candidate native work with spaces/`, `baseline native work with spaces/`, and
an empty `evidence/` directory. The two native work directories are outputs of
the maintained regression; the candidate source directory contains the exact
camera CMake and manifest. The baseline uses the original camera CMake above.
Its complete executed commands and outcomes are retained with the receiving
receipts for inspection.
