# Export a selected recorded-video interval

Use the existing export CLI to create a review clip from one retained MKV in a
finalized or finalized_recovered package. This mode writes a new, explicitly
chosen directory outside the package. Keep the original recording.

## Choose the file and interval

In Review, expand **Recorded video** and note the exact package-relative path of
the selected segment. The command uses that complete path, including its source,
stream and segment directories; a filename alone is not sufficient.

With the project's Python 3.12 environment and FFmpeg/FFprobe on PATH, run from
the repository root:

```powershell
python tools/export_session.py "D:\Recordings\session.capture" "D:\Review\clip-01" `
  --video-segment "sources/camera.1/streams/video/segments/000001.mkv" `
  --video-start-ms 2500 --video-end-ms 7000
```

Replace the example path with an actual listed segment and choose a destination
that does not yet exist. Supply all three video options and the output directory.
These options do not combine with `--modalities` or `--verify`. Omitting the
video options retains the existing whole-session exporter behavior.

The numbers are integer milliseconds relative to the first decoded presentation
timestamp of this file. A frame is included when its local start is at least
`--video-start-ms` and strictly before `--video-end-ms`. This is a half-open
interval; it can begin between frames. It is not a session, camera, checkpoint or
wall-clock interval. Review playback and decoded timestamps can differ; the
manifest records the exact decoded selection.

The request must contain at least one frame start and end no later than the last
decoded frame's known end. The exported clip begins at its first selected frame,
retimed to zero, so its actual duration need not equal the requested interval.

## Read the result

A successful exit writes:

- `clip.mp4`: lossy H.264/yuv420p video, without audio, subtitles or other streams.
- `export_manifest.json`: schema `capture.video_clip_export/1`, state `complete`,
  exact source/stream identity and selected frame indices/timestamps, source file
  and metadata hashes, tool versions/command, output hash and actual timing.

No crop, resize, rotation or continuous segment join is performed. The original
dimensions and selected frame count are checked after encoding. Relative
presentation spacing is checked within the larger source/output time-base tick.
A clip is a convenient review copy, not a replacement for raw scientific data.

The completion manifest is published last. If a command fails after reserving its
new output directory, the directory and partial files remain for inspection;
`failure.json` is written when possible. An MP4 without the completion manifest
is not a completed export. Correct the reported cause and retry with another new
destination. Existing destinations and their contents are never overwritten by
this mode.

## Refusals and limits

The exporter refuses unfinalized packages, unlisted or linked selected files,
ambiguous/multiple video streams, unusable metadata/timestamps, empty selections,
out-of-range requests and destinations inside the package. Windows junctions and
symbolic links in the selected path are refused. Metadata or source bytes observed
to change during export prevent publication of a completion manifest.

Bounds are 2 GiB per source file, one hour of decoded media, 250,000 frames,
600,000 ms per requested interval, and even positive dimensions up to 3840×2160.
FFmpeg and FFprobe each have a 180-second timeout and one-thread request.
Probe JSON is limited to 32 MiB before being read into memory; temporary tool
output is not a hard disk quota. FFmpeg must provide the libx264 encoder.

An unsupported source needs a separately agreed workflow; this command does not
silently fall back to copying the whole recording. Input hashes identify the bytes
observed before and after export. They do not make a concurrent filesystem
transaction, validate physical timing, or establish hardware or clinical accuracy.
