# Inspect recorded session events

Open a finalized or recovered package, choose **Review**, then **Events**. The
event browser presents the checkpoints, annotations and gap summaries loaded for
that package. The **Overview** tab retains the complete stream, gap and checkpoint
lists and session cards.

Use **Kind**, **Source** and the search field together to narrow the list. Search
matches literal text without case sensitivity across each complete displayed
record, including notes, tags, IDs and structured fields. It does not interpret
regular expressions. Source matching preserves exact case: `Source.A` and
`source.a` are different choices. **No usable source ID** groups records whose
source field is absent, empty or not a string; this does not assign those records
to every source.

The count line always shows the number of visible rows, the number of loaded
events and the complete loaded counts by kind. **Clear filters** restores the
whole loaded list. Filtering changes the view; it does not alter a recording,
select an analysis scope or change export options.

## Inspect the selected record

Select a table row with the mouse or use the arrow keys to inspect its details.
The lower text pane is read-only and supports normal text selection and copying.
Markup, Unicode, quotes and newlines remain plain text.

Checkpoint and annotation details retain every field returned by the package
reader, including unknown fields, tags, notes, structured fields and checkpoint
revision history. The table's compact summary is only a label; select the row for
the full record.

Gap details are explicitly labeled **Gap summary from package reader**. They
contain the reader's source and stream IDs, cause, start, end, closed flag and
estimated lost count. They are not copies of complete original JSONL records.
The reader's closed flag and end time remain separate facts: an open gap may
have an end value in a contradictory input, and a closed gap may lack one. The
browser does not silently reconcile them, combine intervals or calculate
downtime.

## Understand session times

The time column contains exact integer **session nanoseconds**, without passing
through a floating-point number. Zero, negative times and values above the
floating-point exact-integer range remain distinct. The Overview checkpoint
labels also identify their value in nanoseconds.

For checkpoints, a present `effectiveTimestampNs` field takes precedence.
`originalTimestampNs` supplies the displayed time only when the effective field
is absent. An explicitly null or malformed effective field is **Unavailable**;
the details retain the original timestamp and explain which preferred field
was invalid. This avoids presenting a different time as the effective one.

Annotations use `timestampNs`; gap summaries use their loaded
`startSessionTimeNs`. Integer values and signed decimal-integer strings are
accepted for display. Boolean, floating-point, empty, exponential and otherwise
malformed time fields remain unavailable. The original loaded value is retained
in the details.

Rows are ordered by exact known time, followed by unavailable times. Equal-time
records are not deduplicated. Their input order is stable within each kind; the
browser does not establish causal order between simultaneous records of
different kinds.

## Package changes and interpretation limits

Loading a package resets filters and selected details. An empty package has no
invented events. A failed package load clears the previous event list, details
and Overview values, displays the load error and disables export for the failed
path. Open a valid package to resume review.

This browser uses the existing `load_review_summary` result. That reader treats
missing optional event files as empty, drops non-object entries from supported
event lists, skips malformed JSONL lines and coerces gap fields according to its
existing rules. A malformed complete event JSON file can refuse package loading.
The browser does not repair or independently validate those source files.

Consequently, **loaded-event counts do not prove complete recording coverage,
intact segments, synchronization, scientific validity or absence of unrecorded
loss**. Inspect the retained package records and existing QC/recovery tools when
those questions matter. Capture, raw data, checkpoint revisions, shared timeline,
analysis jobs and export behavior retain their existing owners and contracts.

## Source and receiving

The bounded contribution is tracked in [issue #76](https://github.com/Jacob-Met/CaptureSuite/issues/76).
Its original-screen control, actual native model result, attempted runtime
availability checks and current hosted receiving disposition are retained in
[the source evidence](evidence/review-events-31a349052b90/README.md).
