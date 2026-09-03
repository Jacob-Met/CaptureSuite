# Recovery and Storage Safety

Goal: a UI crash, a worker crash, or power loss never destroys data that was already written. Recovery is deterministic, idempotent, and never deletes recorded data.

## When recovery runs

On `OpenSession`, if `manifest.state` is anything other than `finalized` or `finalized_recovered`, the session enters `RECOVERING` and `tools/session_doctor` logic runs. The same code path is used by the CLI and by the app, so there is one implementation.

## Procedure

Intent-first, so an interruption during recovery is itself recoverable.

1. **Open the journal read-only.** Replay every event to reconstruct the expected file set, segment time ranges, open gaps, and the last known session time. The journal is the authority on what *should* exist.

2. **Reconcile the file set.** For each expected file, classify it:
   - present and listed `sealed` in `integrity.json` with matching size and hash: trust it, no read needed
   - present but `open` or missing from `integrity.json`: candidate tail, needs validation
   - missing entirely: journal `RECOVERY_INTENT` noting the loss, and open an `UNKNOWN` gap for its time range
   - present but unexpected: leave untouched, record in the report; never delete

3. **Validate each candidate tail.**
   - **MCAP**: verify the leading magic. If the file has no closing summary section (the normal state after a crash), scan records forward from the last known-good offset, tracking the offset of the last record that parses completely and whose CRC checks. That offset is the truncation point.
   - **Matroska video**: parse clusters forward to the last complete cluster; truncation point is its end. Cross-check against the timing sidecar and truncate the sidecar to the last frame index actually present in the video.

4. **Journal intent, then truncate.** Write `RECOVERY_INTENT` with the file path, current size, and intended truncation offset. Only then call `SetFileInformationByHandle` with `FileEndOfFileInfo` to truncate. Then write `RECOVERY_COMPLETE` for that file.

   This ordering is what makes recovery idempotent: on re-run, an intent without a matching completion means re-verify that file and continue. Because the intended offset is recorded, repeating the operation converges to the same result.

5. **Mark gaps at truncation points.** Any interval between the truncation point and the last session time known from the journal becomes a gap with cause `UNKNOWN` for that stream. Truncated bytes are always accounted for as lost data, never silently forgotten.

6. **Close open gaps.** Any gap still open in the journal is closed at the last known session time.

7. **Re-hash repaired files.** Only files that were truncated are re-hashed. Their `integrity.json` status becomes `truncated_recovered` with the new size, hash, and actual count.

8. **Write the report.** `recovery/report_<utc>.json` records every decision: files trusted, truncated with offsets, missing, unexpected, and gaps created.

9. **Finalize atomically.** Set `manifest.state = finalized_recovered` via the temp-file-and-rename rule.

## Invariants

- Truncation only ever removes bytes that could not be parsed. No parseable record is discarded.
- No file is deleted during recovery, including unexpected files.
- Recovery is idempotent: running it twice produces the same package state.
- Every byte lost is represented as an explicit gap.
- A session that cannot be repaired goes to `FAILED` with its package left exactly as found.

## Partial finalization

If writers do not drain within the 30 s stop timeout, the session still finalizes. Affected files are marked `unverified` in `integrity.json`, `PARTIAL_FINALIZE` is journaled, and the next open runs recovery on those specific files. Hanging forever is not an acceptable alternative to an honest partial state.

## Disk watchdog

Real behavior, not just a simulated fault. Sampled every 5 s during `PREPARING` and `RECORDING`.

Measured inputs:

- Free bytes on the session volume
- Aggregate sustained write throughput over a trailing 30 s window
- Estimated remaining recording time = (free bytes minus reserve) divided by measured throughput

Fixed reserve: 10 GiB never consumed by a session.

| Level | Trigger | Behavior |
|---|---|---|
| Info | above 60 min estimated remaining | status bar only |
| Warning | 15 min estimated remaining | `Alert` at `WARNING`, journal `DISK_WARNING`, UI banner |
| Critical | 5 min estimated remaining | `Alert` at `CRITICAL`, repeated every 30 s, audible if enabled |
| Hard floor | free space reaches the 10 GiB reserve | raw stream writes stop, `WRITE_BLOCKED` journaled, `WRITER_ERROR` gaps opened; the session stays in `RECORDING` |

**A running session is never stopped automatically.** Only the operator ends a recording. The daemon escalates alerts as loudly as it can and then degrades explicitly, but `RECORDING` is left only by an operator `Stop` or a fatal daemon fault.

The 10 GiB reserve is what makes that safe. Raw stream writers are blocked at the reserve boundary, so the journal, manifest, and integrity manifest always retain room to write. The session therefore stays recoverable and finalizable even after the volume is effectively full.

The tradeoff is explicit: data arriving after the hard floor is lost and recorded as `WRITER_ERROR` gaps for the affected streams. That is the honest cost of not terminating a session the operator did not choose to end, and it is preferable to a silent stop in the middle of a participant trial.

Recovery from the hard floor requires no restart. If space is freed while the session is still recording, writers resume automatically, the `WRITER_ERROR` gaps close, and the first datum after resumption carries the `AFTER_RECONNECT` quality flag.

### Storage preflight

Before `PREPARING` completes, measure and report:

- Sequential write throughput via a 256 MiB scratch write to the session volume, then delete
- Free space and the resulting estimated capacity at the configured source set's aggregate rate
- A hard failure if measured throughput is below 1.2 times the configured aggregate write rate

The preflight result is stored in the session so a later throughput complaint can be checked against what was known at start.

## Rehearsal mode

Rehearsal uses the same pipeline with `IScratchSink` in place of the real writers. Previews, health, rates, gaps, and checkpoint hotkeys all behave identically; nothing is persisted. Implementing rehearsal as a sink swap rather than a special case is what keeps it honest as a signal check.

## Fault injection

The simulator exposes every failure this document claims to handle, and each has a test: disconnect, reconnect with gap, jitter, dropped frames, duplicate sequence numbers, clock drift, time discontinuity, worker crash, slow disk, full disk, corrupted tail segment.

`tests/kill_tests/` force-kills a worker mid-capture and then the daemon mid-capture, asserting after each that previously written segments are intact, the journal replays, recovery is idempotent, and every lost interval appears as a gap.
