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

With a video button focused, Space activates Play/Pause, Reload selected or the Recorded video disclosure. Other application shortcuts retain their usual behavior.

## Repeat a short interval at a review speed

For a loaded, seekable segment, pause and move the seek bar to the start of the
motion, then choose **Set A here**. Move to its end and choose **Set B here**.
Both endpoints are shown as integer-millisecond media positions; B must be after A.
Enable **Repeat A–B**, then press **Play**. Repetition uses the half-open interval
[A, B): Play from outside that interval starts at A, and playback reaching B
returns to A. A seek outside the interval while playing also returns to A.
A paused seek may remain outside the interval until you explicitly press Play.

Setting a valid endpoint turns Repeat off until you enable it again. Setting A
clears B. An invalid B retains the previous valid endpoints and Repeat state.
**Clear interval** removes A/B and turns Repeat off. Disabling Repeat or clearing
the interval does not pause, resume or reposition the video. Endpoint and speed
changes while paused do not start playback.

**Speed** requests 0.25×, 0.5×, 1× or 2× from the native decoder. The adjacent
**Backend-reported speed** shows its reported property, not a measured promise
that every backend can sustain that rate. Choose 1× if a backend does not honor
the requested rate. Repeat is decoder-scheduled inspection, not frame-exact
extraction, an analysis window, a persisted annotation or a session time mapping.

Reload, a different segment, a new/failed package, and decoder failure clear
A/B, turn Repeat off and restore the requested speed to 1×. Collapsing or hiding
the viewer pauses playback without clearing the interval; reopening remains
paused. The original retained media is never changed. Space activates the
focused Set A, Set B, Repeat and Clear controls as it does the existing video
buttons; other application shortcuts retain their routing.
