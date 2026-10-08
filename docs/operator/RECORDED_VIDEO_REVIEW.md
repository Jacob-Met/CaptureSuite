# Inspect recorded video

Open a finalized or recovered finalized package in **Review**, then expand **Recorded video**.

1. Choose a **Segment**. Each entry includes the recorded source ID, stream ID and package-relative path. Equal filenames in different sources are separate choices.
2. Read the identity beneath the chooser and wait for the selected file to load.
3. Press **Play** to inspect the video. Press **Pause** to stop at the current position. The seek bar becomes available when the decoder provides a seekable duration; its arrow keys also change the position.
4. Choose another segment to inspect a different file. The old picture and controls retire immediately. The new file starts stopped; package loading and selection never start playback automatically.

Collapsing Recorded video or leaving Review pauses playback. Expanding it again does not resume automatically. At the end, Play starts the same segment again from its beginning. This viewer plays video only; it does not play audio.

## What the clock means

**Media position** is the selected media segment's own hours, minutes, seconds and milliseconds. It is not session time and does not establish which frame belongs to a checkpoint. This viewer does not align cameras, interpolate source gaps or join separate segments into a continuous recording. Use the existing gap and checkpoint records for their recorded information.

The inventory reflects files discovered when the package was opened. It is not an integrity check or a claim that all listed media is readable. The viewer reads retained files without changing them or writing analysis/export output.

## If a segment cannot play

- **No recorded MKV segments:** the package did not list retained MKV video. Other recorded modalities remain available through their existing views.
- **File unavailable:** restore access to that original file and choose **Reload selected**, or choose another listed segment. Reopen the package to refresh its inventory after files are added or removed.
- **Decoder refused the media / no video track:** the selected file may be damaged, unsupported by the installed Qt multimedia backend, or contain no video track. Read the displayed reason and choose another segment or reload after restoring a usable file.
- **Duration unavailable:** the decoder has not supplied a seekable duration. Play remains available only when a video track is ready; the seek bar is disabled until its requirements are met.
- **Playback waiting for media:** pause or reload the selected segment to retry.

A failed selection or package load clears the previous media controls and picture. Reload does not repair a recording or alter its raw bytes. Only finalized and finalized-recovered packages are admitted to this viewer.
