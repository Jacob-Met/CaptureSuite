# Full-application keyboard correction

After the original candidate was published as e9728100b7c27b175b04e0fc776f8d9984713698, a fresh native checkout passed all 15 focused cases and preserved all 1,215 tracked files. The original standalone ReviewScreen keyboard case did not include MainWindow's application-wide checkpoint shortcut.

The additional actual MainWindow receiver at 20:03:31Z found focused Play + Space leaving the selected media in StoppedState and invoking the existing checkpoint shortcut once. `keyboard_original.py`, `keyboard-original.json` and `keyboard-original.log` preserve that failing assertion on the exact original viewer SHA `3d89f1f8453a3d18d2776574941a2c6197f3be59e8df3a7a278f3b5c400134d9`. The checkpoint action was replaced only in this isolated receiver with a hit recorder, avoiding any daemon call.

The production successor adds a viewer-local event filter on its Play, Reload selected and disclosure buttons. It accepts only their unmodified Space ShortcutOverride events, allowing Qt's normal focused-button activation. Every other key, modifier, event and watched control follows the inherited route. No application shortcut, `app.py`, event-browser source, decoder lifecycle or other owner's contribution is changed.

Final viewer SHA-256: `126c4ec87d5af60d151292ff1b2d7f7f3d5ad2f63112507c71d05385bf80f594`.
Final UI test SHA-256: `e897fc66292ace197df134ad9d6b23433c27b05774b384a2f301420efc5a836c`.
The pure model and shared ReviewScreen retain their previously reviewed exact hashes.

The maintained actual MainWindow regression activates disclosure, Play, Pause, Reload, collapse and reopen with Space. It proves no autoplay after reload/reopen. Countercontrols send C on Play to the original checkpoint path, Ctrl+Space to an independently installed shortcut, and Space on the existing stream list to the original checkpoint path. All synthetic raw fixture bytes remain exact.

`focused.log` / `focused.xml`: 24 native model, video and desktop-smoke cases pass, zero failures/errors/skips, in 3.58 seconds. The original two protobuf deprecations and a receiving-only QApplication.setActiveWindow deprecation remain visible. Scoped Ruff passes. This successor changes one owned runtime module and its maintained tests; the original 151-case and independent six-group receipts retain their historical source pins and are not relabeled as a replay of this successor.

The original presentation limitation remains: actual decoder output/control state is received, while onscreen GPU rendering is not certified by the failed whole-window grab. The same unchanged hosted full Windows gates are required on the final PR head before integration.
