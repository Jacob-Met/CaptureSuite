# CaptureSuite69: original-source layout and busy-state counterexamples

Exact source remains 424298e30d6e0f08fe4124fa282328575c40d203 / tree b69adfdf45711035963094b811760500cb76c966, based on PR65 d7459fa62dd7a57d5565214e10638e055ad5877c. No production source was changed during these observations.

## Inherited Run/Cancel state: confirmed

The actual QThread was reserved and running in a pass-through gate immediately before the unchanged capture_analysis.run call. The new evaluation input was disabled. Run remained enabled and Cancel remained disabled. The input was the receiver's own finalized-format fixture with an explicit external prediction path.

The receiver invoked worker.request_cancel solely for cleanup; this was not a successful native Cancel action. After releasing the gate, the actual evaluator entry consumed cancellation before creating job outputs. The source proof removes the candidate's only additive evaluation-input busy hook and obtains the entire d7459fa screen_analysis.py byte-for-byte. This is an inherited screen-state defect. The author recorded the narrow reservation/start-guard extension at https://github.com/Jacob-Met/CaptureSuite/issues/69#issuecomment-6064049439 .

busy-counterexample-source.json freezes the exact parent/candidate file hashes, raw receipt hash, real worker call and scope of the accepted observation.

## Original Analysis viewport layout: confirmed

The corrected receiver uses real global Qt positions to intersect every control rectangle with its ancestor rectangles, walks native keyboard focus, and compares rendered control/help height to the toolkit's actual minimum/word-wrapped height. It requests the actual standalone AnalysisScreen viewport sizes, without imposing a larger window after layout.

- At 1280 x 960, the mode control receives 25px and path/Choose/Clear 24px against 29px minimum hints. Help text receives 24px for 39px of wrapped text.
- A requested 1100 x 700 viewport is forced to 1100 x 881; the new mode/file controls and help are compressed to 11px.
- Both original mode screenshots were visually inspected and confirm the clipped content.

The corrected original-source geometry run intentionally skips the worker. The already completed original held-worker observation is not replayed.

## Receiver correction and platform limits

The first viewport attempt used ancestor.mapTo(descendant), which Qt rejects. All its calculated geometry is excluded. Its directly observed enabled booleans, actual QThread state, real worker call and cancellation do not depend on that coordinate helper. The original source, full diagnostic output, receipt and held-worker screenshot are retained.

The corrected receiver uses mapToGlobal offsets and retains its failed baseline receipt. Its SHA-256 is add4a8df6d01e870b2e35653d2551bfb1b57069d20f6d894875c65faa9f8fad6. No product source changed for this receiver correction.

These native observations use Mac Python 3.12.8 / PySide6 6.11.2 with Qt offscreen controls and explicit active-Qt-window selection. They do not qualify Cocoa dialogs or operating-system window-manager focus. Actual MainWindow cannot be imported unmodified on Mac: app.py imports the control client, which imports msvcrt and calls ctypes.WinDLL at module load. The Windows-only full shell 1100 x 700 gate therefore remains separate. No transport substitution or daemon startup is performed.

## Reproduction and custody

The helpers reuse the independent fixture and actual-dialog code from the accepted functional packet (archive SHA-256 8efa28046febd1fbadadefaf0cb35229e9cc4cefa6b621bd9c2d35f979c7737f). The baseline geometry run uses --geometry-only. The same corrected receiver's normal mode requires a geometrically accepted candidate to use real Clear, file chooser, Run, held-worker Cancel and settled re-enable, rather than replaying the six unchanged evaluator cases.

native-counter-execution.json retains the exact native commands and process completions. Both original receiver files and receipts are unchanged. The complete original candidate commit bytes are retained to support reconstructing that local commit from its public base and the four candidate files in the companion functional packet. The source files in this packet remain exact Git blobs. MANIFEST.json and archive re-reading verify every member.
