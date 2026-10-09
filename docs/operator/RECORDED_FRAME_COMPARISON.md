# Compare two recorded frames

Use this panel to keep two visual observations while inspecting recorded video.
It reads the existing recording and does not create or modify files.

1. Open a finalized or finalized-recovered package in **Review** and expand
   **Recorded video**.
2. Choose a segment, press **Play**, then **Pause** on a frame you want to inspect.
3. Select **Compare two frames…**. In the nonmodal panel, press **Keep frame A**.
4. Return to the original video controls. Seek or choose another segment, then
   play and pause as needed. Press **Keep frame B** in the comparison panel.
5. Compare the images and their individual source, stream and package-path labels.
   Keeping A again replaces only A; keeping B again replaces only B.
   **Clear A** and **Clear B** are independent.

The panel stays open while you use the original video controls. Closing it hides
the panel and keeps the two images. Reopening it shows the same pair. Images also
survive collapsing Review, selecting or reloading another segment, and a failed
selection within the same package. Opening or resetting a package clears both
images, even when reopening the same path. Destroying the viewer releases them.
There is no saved comparison history or automatic export.

## What a retained frame means

A retained image is a detached copy of the current valid decoded frame when you
press Keep. The player must be paused. Keeping a frame never changes playback,
position, speed or the A–B repeat interval. If no frame can be copied, the panel
explains how to retry and preserves the previous pair.

**Decoded frame PTS** is the decoder's presentation timestamp in microseconds,
or **unavailable** when it supplies none. **Player position when kept** is the
player's separately observed segment-local clock. A seek can update the player
clock before a new frame is decoded; these labels deliberately remain separate.
This is not frame-exact extraction, camera synchronization, checkpoint alignment,
a session timestamp or a measurement of motion.

Images retain their decoded pixel dimensions and Qt presentation rotation and
mirroring. The panel scales them to fit without changing their aspect ratio.
Different source dimensions remain explicit; no registration or image-difference
score is computed.

## Limits and recovery

Each slot accepts at most 16,777,216 decoded pixels and 64 MiB of converted ARGB32
image storage. A larger or failed conversion leaves both previous images intact.
This bounds retained image storage, not the whole decoder/application's memory.

- **Pause Recorded video:** playback is active or has stopped at the end. Play
  and pause explicitly before keeping a frame.
- **No decoded frame / image:** play the selected segment and pause after a
  picture is available, then retry.
- **The selected video changed:** select the intended file, pause and retry.
- **Comparison limit:** inspect a smaller recording with the existing controls;
  the comparison does not resize the retained source to admit it.

The source/stream IDs and paths are literal text, including punctuation or markup.
Equal filenames in different sources remain distinct. Native qualification uses
synthetic retained MKV fixtures on Windows / Qt 6.12; it does not certify a camera,
a recording's integrity, a scientific result or every codec/backend.
