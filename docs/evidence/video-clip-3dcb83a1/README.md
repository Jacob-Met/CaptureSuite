# CaptureSuite selected-video interval export — qualified receiving custody

This archive preserves the native evidence for the seven-path CaptureSuite #104 contribution based on commit 3960c0c756cd4e9facbde0d76eaaa3c31ab7c167 (tree d1af33caaf7154e83def1dab035920907d417e8d). It is an evidence/source offer, not a claim of adoption, deployment, a physical recording, or an executed GitHub gate.

The existing tools/export_session.py CLI can export one explicitly identified retained video segment's local half-open millisecond interval into an explicitly named new external directory. It preserves whole-session mode, discovers the segment through existing package conventions, emits a lossy H.264 review copy with a completion manifest, and retains partial outputs plus diagnostics after admitted late failure. Source timestamps use the first decoded segment frame as local zero. They are not session or wall-clock alignment.

## Qualification and custody

Author baseline receiving verified the new options were absent and original whole-video export still worked. Initial candidate v1 passed 20 maintained tests. Final candidate v2 passed 22 maintained tests (21.74 seconds; wrapper exit 0), followed by a targeted Ruff pass. The v1 helper and test remain in the separately decoded historical supplement; the v2 source is the offered product.

Root independently froze its contract before candidate exposure. Fixture admission v1 failed due to unquoted commas in the receiver's FFmpeg setpts expression; v2 only quoted that expression and changed evidence directories, preserving literal oracles. V2 passed 155 checks, including 119 original-source pins. Root then executed the exact final candidate once: 39 cases, 538 checks, zero failed/skipped, 56 actual child commands. This includes 258 admission checks and 271 case assertions plus construction/final checks, not 538 independent behaviors. Receiver PID 83404 exited 0 in 40.56979490001686 seconds; launcher 85612 and RDC wrapper 46380 exited 0. Receiver stderr is empty; no timeout or cleanup fallback occurred. Exact root interpretation is independent/REVIEW.md, never rewritten here.

The retained binary fixtures are synthetic: author constant-rate and variable-rate clips; root ten-frame ordinal grayscale media with 7-second origin, literal nonuniform timestamps, equal-basename red decoy, real two-stream refusal, decoded RGB, produced H.264 clips, manifests and late-failure outputs. Both actual root junction cases and their targets are preserved as metadata, not followed. The manifest also records pytest convenience links without following them. No archived link is reconstructed automatically.

Five explicitly excluded items are duplicate author/source, author/baseline, independent/candidate-v1, independent/baseline trees, and the pinned original-source.zip intake archive. Their original Git and candidate pins are retained. Seven offered product/doc files are included once under product/. Every included ordinary native file is copied byte-for-byte without newline normalization, separately SHA256/Git-blob pinned and verified after ZIP decompression. Native paths in the manifest identify provenance only. Empty directories and excluded links are recorded in inventory-v1.json. Files are read only after every path component is checked for a reparse point.

The first inventory process successfully wrote both inventory JSON files, then its final console print raised a cp1252 UnicodeEncodeError on the literal Omega path. This packaging-only failure is retained in custody/inventory-execution.json. No source, test or receiving process was rerun; the subsequent archive assembly reads those exact inventory files and uses ASCII-safe console output.

## Archive layout

- product/: the exact seven proposed repository paths; source pins in custody/source-offer-admission.json.
- author/: original runtime/source admission, public contract, source freeze, exact diff, v1/v2 tests and logs, all ordinary phase fixtures/media, and original whole-export controls.
- independent/: frozen root contract, fixture generators and both attempts, receiver and freeze, launcher/actual logs, all ordinary fixture/output/decoded files, exact result and unchanged root REVIEW.
- custody/: inventory, manifest, assembler/replay source, historical-source supplement, and source/workflow admission. The historical supplement labels field projections distinctly from exact original bytes.

The archive is sealed evidence. Do not execute its files by recursive test discovery. Its preserved scripts contain original absolute paths and exclusive output expectations; the original paths/commands, actual exits and runtime pins are primary historical records, not a promise that running them in another directory is automatic.

## Reproduction on a new admitted checkout

Use the project's declared Python 3.12 runtime and dependencies, with actual FFmpeg/FFprobe available; the qualified MSI run used Python 3.12.2 and FFmpeg/FFprobe 9.0.1. Read the existing project AGENTS instructions and maintained dependency/CLI documentation. Apply only the exact offered product patch to the pinned base or a separately verified compatible checkout, preserving the original package discovery and whole-export flow.

From that checkout, the maintained focused entry is:

```text
python -m pytest tests/analysis/test_video_clip_export.py -q
python tools/export_session.py --help
python tools/export_session.py PACKAGE NEW_EXTERNAL_DIRECTORY --video-segment sources/SOURCE/streams/STREAM/segments/0001.mkv --video-start-ms START_INTEGER --video-end-ms END_INTEGER
```

Use fresh outputs and actual native-layout synthetic fixtures. The public contract and operator guide state all admissions and refusal semantics. The maintained tests generate their own synthetic media and use actual subprocesses. A new independent replay must explicitly adapt the archived receiver's absolute source/evidence/runtime paths and source pins to the admitted checkout, preserve its literal frame/timestamp/refusal oracles, record that amendment before execution, and keep fresh results separate. This archive itself does not silently rewrite or execute the frozen root receiver.

## Source/workflow disposition

The read-only preparation found main 3960c0c756cd4e9facbde0d76eaaa3c31ab7c167 unprotected, required checks empty and rulesets empty. These are time-bound facts. The three exact workflow definitions are retained: ordinary PR creation or main/master pushes select CI, and v* tag pushes select release. Under Jacob's no-GitHub-Actions direction, this contribution must not create a PR or merge into main. A separately authorized immutable Git object/non-main source branch plus existing-owner handoff is possible only after a fresh full workflow/ownership/base guard. No workflow, protection or required gate is removed or bypassed.

All seven product paths are fixed; original video widget #103, daemon, scientific/timing and later #105/#106 work remain owned and unchanged. The contribution makes no clinical, raw-data, cross-camera, general concurrent-write atomicity, or GUI-widget claim. The raw inputs and existing whole-session export remain the receiving boundary.

## Durable complete archive and compact Git projection

The complete archive is permanently attached on the existing estate continuity page:

notion-file-block://0dc8004b-c4cd-4b38-adea-e597df432fd5/bf0349f9-9b24-420b-92ab-df8708ea6e5e?space_id=847aedcd-f4a5-8159-99ed-0003ba2ee75a&name=CaptureSuite-selected-video-custody-3dcb83a1.zip

ZIP: 843813 bytes; SHA256 bb3bb0709a489473d50aa824c61029aaf56a6bd55c97dacb59a8d4e94bf1bfa0; 537 members / 2830319 decoded bytes. It downloaded HTTP200 byte-identically and all536 other manifest entries verified. The manifest itself is separately pinned in archive-assembly-receipt.json. This Git projection retains primary source/phase/independent receipts and the complete decoded archive manifest. Binary media, all per-command raw streams, fixture package files and all native replay sources remain in that archive, not omitted from custody. Selected archived Python scripts have only a .txt filename suffix; their bytes are unchanged. Historical source/replay records may say independent receiving was pending at their recording time; the later unchanged independent/REVIEW.md and result are the qualified disposition. No earlier source/receipt was relabeled.
