# Compact source handoff versus the complete Windows kit

This directory retains the exact source guide, receiving scripts and compact receipts for the Windows acceptance of product commit `223e6926438b63dd848225da070f71575703c4cb`. It adds no product change and does not change an existing installation.

The complete immutable supplement is `CaptureSuite-IMU-composed-223e6926-Windows-v1.zip`, 299,049 bytes, SHA256 `ce2e508840dd8619b1439182c20ee0533686ea4272567b84b2a4cfc4931fa90c`. It contains nine outer members and the unchanged 208-payload native evidence archive. The delivery URL is recorded in CaptureSuite issue #121 and the existing project ledger. The earlier portable source/replay kit remains at https://drive.google.com/file/d/1DC4JQJ82p3BE2j-AfNi0F-kUc9k6PlgD/view .

`README.md` is the exact complete-kit guide. Its `verify_packet.py` command requires the complete downloaded supplement, including `MANIFEST.json` and `evidence/native-evidence.zip`; these large artifact payloads are deliberately not duplicated in this compact source handoff. Run the retained verifier against the full ZIP or its complete extraction, not against this source directory. The large raw fixtures, CSV/Parquet outputs, full native source map, JUnit and logs remain in the immutable supplement.

The files under `receivers/` are byte-identical historical source/receiving scripts. The v1 gate passed 183 tests and 24 subtests before a source-comparison preflight stopped on existing bytecode. The v2 replay partitions and preserves those derived files; it reuses the successful gate and completes eight actual jobs. Source, numerical operations, raw inputs and the original failure receipt remain unchanged. The adapted public-job receiver supports a fresh explicit output directory; do not blindly rerun the one-shot source/gate/resume scripts against their existing native paths.

The native acceptance is one isolated MSI CaptureSuite analysis environment. It carries no hardware, live-acquisition, GUI, performance, estate-wide or default-installation claim. Product identity remains `223e6926`; this successor records evidence only.
