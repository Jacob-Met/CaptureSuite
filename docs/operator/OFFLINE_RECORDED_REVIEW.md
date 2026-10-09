# Review a recorded package without the capture daemon

Use **File → Review recorded package…** and choose the recorded package directory. The package must have state `finalized` or `finalized_recovered`. A missing, unreadable, malformed or unfinished package produces a status message and does not open a new viewer. Cancelling the chooser leaves the current windows unchanged.

The new modeless window shows the selected package path and session identity above the existing Review screen. It includes the normal session summary, stream inventory, explicit open and closed gaps, checkpoints and recorded-video controls. A recovered package retains the existing recovery warning. Media positions remain segment-local; the viewer does not infer alignment or hide gaps.

Each window owns a separate Review context. You can open two packages for comparison, and closing one releases its media without changing the other window or the main capture session. No daemon connection is required for this File action. The main transport's **Open Session** command keeps its existing daemon-backed behavior.

Opening a recorded-package window is refused during recording, rehearsal, arming and stopping. The check runs again after the chooser returns, because capture state can change while a dialog is open. A viewer that was already open remains modeless: it does not disable the main window's Stop control.

## Export the selected window's recording

Use **Export…** inside the package window. The existing export wizard receives that window's package path. Choose a new or empty destination outside the recorded package, select the desired modalities and verification options, and confirm. Cancel leaves export preferences and the capture context unchanged. An explicit export can update the existing last-export preference and status feedback.

This command uses the maintained exporter, including its current format, modality and verification rules. It is refused when invoked during an active recording, rehearsal, arming or stopping phase. It does not change the main session ID, selected capture sources or daemon lifecycle.

## Loading and availability

The maintained package reader supplies the admission and summary data. A finalized package should remain stable while it is being reviewed; the existing readers make several ordinary filesystem reads, rather than taking an atomic snapshot. If the package becomes unavailable during loading, an incomplete new viewer is discarded. Close the viewer and reopen the package after resolving the path or data problem.

This addition changes the File menu and a separate window container. The existing Review screen, recorded-video widget, package reader, exporter, analysis and capture transport remain the same components.

## Receiving and source custody

Issue [107](https://github.com/Jacob-Met/CaptureSuite/issues/107) records the scoped ownership, pinned native source, independent receiving and installation status. The focused regression at `tests/ui/test_offline_recorded_review.py` checks package identity, cancellation, refusal, capture transitions, independent windows and export routing on actual desktop widgets; it controls the chooser input. Separate frozen native receiving operates the real menu, Qt directory chooser and export wizard against explicit synthetic recorded fixtures.

The source branch is distinct from installation. Use the matching installed desktop owner's selected receiving and activation path for adoption. A source-only qualification does not claim an installed desktop, a different Qt runtime, camera hardware acceptance or hosted workflow acceptance.
