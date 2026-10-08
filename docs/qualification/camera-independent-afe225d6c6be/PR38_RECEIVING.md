# Receiving the existing camera packaging PR #38

The existing contribution owns camera packaging:
<https://github.com/Jacob-Met/CaptureSuite/pull/38>, reviewed receiving head
`677026871c39362e9b6e2c816b841fc6393050f0`, base
`d3edda561322a80bfc1491ae4f4c7b0bb94943ea`. Implementation and receiving remain
with `dd846795-production`; this packet adds independent evidence only.

The exact PR camera CMake is blob
`8b74080cc042c9dc60d6f4569f0c1b6e5b2c7f78`, SHA-256
`ddb68fccae5e9b5ae66f81ff4859060f27dcc425d6a41c607e9c9c883a6bd842`.
Compared with the independently accepted `8167c9a` candidate, its sole
difference is the CMake `COMMENT` wording:

```diff
-      COMMENT "Copy ${_dep}.dll to both camera package directories"
+      COMMENT "Copy ${_dep}.dll beside both packaged camera workers"
```

The complete remaining CMake bytes, including every runtime command, are
identical. The plugin manifest is also byte-identical, SHA-256
`6f921746e815083b55f5d81d10c660e9b448ff315b48a2082090b34b350eae03`.
`evidence/pr38-only-comment.diff` retains the exact comparison.

The actual native staging/launch fixture ran against a new private copy of
these exact PR files. All 17 checks passed: both package layouts contain
the identical executable and five dependencies, both launch from an unrelated
working directory, the manifest matches, and withholding plugin-local
`libprotobuf.dll` recreates loader exit 127 before `main()`. The full command,
source hashes, output and result are in `evidence/pr38-final-native-report.json`.

Before source publication, the independent helper received the required SPDX
identifier and repository Ruff formatting/import fixes. The final helper is
SHA-256 `9da0213cf76f0e37d45f3b5d8ae4d125b63c053230f1aa51d8f9d5515834d1d2`.
Repository Ruff rules (`E,F,I,UP,B`, Python 3.12, line length 100) pass.

All six small independent receiving groups then ran against the exact PR #38
source with this final helper in a fresh private work root. They all pass,
including individual necessity/restoration for all five libraries, origin-only
ELF resolution, relocation without original or legacy directories, and actual
Ninja Multi-Config Debug/Release separation. The exact original production
CMake was also replayed in that final root and retains ten passing and seven
failing checks. The final full outputs are
`evidence/pr38-final-independent-review.json` and
`evidence/pr38-final-baseline-report.json`. Historical source checks remain
retained separately; no whole-product or Windows build was repeated.

**Disposition:** accepted for this source packaging and native fixture boundary.
No duplicate runtime patch or competing camera PR is needed. This is not a
Windows DLL-loader, MSVC/vcpkg/GStreamer, daemon-handshake or hardware result;
the existing contribution retains its real Windows build and receiving gate.
