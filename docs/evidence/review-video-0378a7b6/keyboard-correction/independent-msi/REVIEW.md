# Independent acceptance of the focused-button Space correction

Accepted at widgets_review_video.py SHA256 126c4ec87d5af60d151292ff1b2d7f7f3d5ad2f63112507c71d05385bf80f594 and test_review_video.py SHA256 e897fc66292ace197df134ad9d6b23433c27b05774b384a2f301420efc5a836c. The previous generation/media-lifecycle acceptance remains pinned to its historical source; this receipt reviews the later correction separately.

Read the exact local event-filter addition, the complete new actual-MainWindow regression, and keyboard-original.json. The original full-window witness showed focused Play remaining StoppedState while checkpoint_hits became 1 at public source e9728100b7c27b175b04e0fc776f8d9984713698. The candidate handles only ShortcutOverride for unmodified Space on its own Play, Reload and toggle buttons. It accepts that event, allowing the native button's regular key activation to proceed. The global MainWindow shortcut implementation and other controls remain untouched.

No blocking finding. Installing the filter only on those three buttons keeps the exception local; checking the exact event type, key and modifiers preserves other shortcut routing. The owner regression exercises the actual MainWindow, all three controls, Play/Pause, reload and collapse, with C, Ctrl+Space and an outside-viewer Space countercontrol. Its 24-test qualification and original negative witness are separate from this review.

The independent native boundary matrix completed with exit 0 at 20:10:18Z. It considered six controls (three owned, choice, seek and a foreign button), Space/C/Return, and no/Ctrl/Alt/Shift/Meta modifiers: exactly the three intended events were claimed among 90 cases. This is one bounded matrix, not 90 separate product tests. Source SHA remained exact. review_shortcut_boundary.py, receipt.json, run.log and run-result.json preserve the actual result.

This review does not repeat the full suite or establish onscreen GPU-video rendering. It does not replace the author's actual MainWindow test with the direct matrix; the two have different boundaries. No source, runtime installation, application shortcut or user data was modified by this reviewer.
