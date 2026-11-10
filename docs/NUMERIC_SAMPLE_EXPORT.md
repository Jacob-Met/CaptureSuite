# Export recorded numeric samples

Use this when an external notebook, statistics package or spreadsheet needs the
recorded channel values, rather than the derived feature table.

In the desktop, open a sealed session, choose **Export**, select **Numeric samples**,
and choose a new or empty destination. The dialog selects discovered recorded data
by default and lists its source identities, stream count and indexed message count.
A message can contain many samples; counts are not a quality or sample-count claim.
Unavailable formats are summarized. If an index cannot be read or classified,
choices remain available with an explicit incomplete-metadata note. Or use the standalone Linux executable:

```sh
./capturesuite-analysis export-session recording.mmsession exported-samples --modalities numeric --verify
```

From source, the same operation is:

```sh
python tools/export_session.py recording.mmsession exported-samples --modalities numeric --verify
```

Each recorded numeric stream produces a UTF-8 CSV under `numeric/SOURCE_ID/`.
The export manifest names each CSV, stream topic, source MCAP files, frame and
value counts, and copied stream descriptors and declared gaps. Original files
are unchanged. Only `generic.numeric_batch/1` / `capture.v1.data.NumericBatch`
are decoded; unrelated schemas are not interpreted as numeric samples.

## Read the table

The CSV uses one row per frame and channel. `channel_index` is the original
zero-based position; `channel_name`, `units` and `dtype` are recorded values
and can be empty when the producer did not supply them. `value` is the recorded
numeric value. `mcap_file`, `mcap_channel_id`, `message_index` and
`frame_index` identify its source. Rotated segments remain in file order;
messages remain in recorded order within each segment. No resampling, averaging,
sorting, gap filling or sample removal is applied.

`device_time_ns` preserves the signed native timestamp as an exact decimal
integer. `mcap_log_time_ns` and `mcap_publish_time_ns` preserve the separate
MCAP message clocks. `session_estimate_ns` adds the native within-batch delta
to the first-frame MCAP log anchor. This estimate is uncalibrated: it is not a
device-clock drift fit or evidence that two instruments were synchronized.
Without native timestamps, both device time and session estimate are empty and
`time_basis` says `unavailable`; the recorded MCAP anchors remain available.

Read nanosecond columns as integer or text, not floating point. Some spreadsheet
programs round integers larger than 2^53; import these columns explicitly as text
before interpreting clocks. Example with pandas:

```python
import pandas as pd
table = pd.read_csv("numeric/SOURCE_ID/samples-HASH.csv",
                    dtype={"device_time_ns": "Int64", "mcap_log_time_ns": "UInt64",
                           "mcap_publish_time_ns": "UInt64",
                           "session_estimate_ns": "string"})
```

Copied `health/gaps.jsonl` and `stream.json` files retain their original
meaning. They are not automatically used to delete CSV rows. Nonfinite values,
backward device steps and missing clocks are counted in the manifest; they are
not repaired. Run recorded-payload QC when deciding whether measurements are
suitable for an analysis.

Malformed selected payloads, unreadable MCAP and write failures return a nonzero
exit status without a successful export manifest. Partial CSV files may remain
for diagnosis; choose a new empty destination after fixing the problem.
`--verify` checks that a finalized package yielded data; it does not certify
instrument accuracy, calibration or a complete recording.


## Long exports in the native desktop

The native session export runs outside the UI event loop. Its progress window
shows activity and the destination while the normal desktop remains responsive;
it does not invent a percentage or a remaining-time estimate. A second export
request returns to the active progress window.

**Cancel export** stops the exporter. Closing the main window during export
requests the same stop, then waits asynchronously for the worker to finish
before closing. Original recording files are not modified. An interrupted
destination can contain partial files; choose a new or empty folder when
retrying. Cancellation never displays the completed-export message or writes
the optional provenance sidecar.

Producer checks on Linux used the actual MainWindow with automatically operated
widgets and genuine, generated MCAP data: 250,000 frames, eight channels and
two million exported values. The successful CSV was byte-identical to the
previous synchronous route. Cancellation and closing during the write stopped
the child and retained source hashes. A separate Linux process-tree course
stopped an active ffmpeg child. These are engineering checks, not hardware
validation or independent audience acceptance. Windows process-tree cleanup
has not yet been exercised on a Windows host.

An unsuccessful native export shows its actionable error in a visible dialog;
expand Details for the captured exporter output. A nonempty destination is
refused before writing, so choose a new or empty folder for a fresh attempt.
