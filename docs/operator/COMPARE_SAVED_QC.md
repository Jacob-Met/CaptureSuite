<!-- SPDX-License-Identifier: GPL-3.0-only -->
# Compare two saved QC reports

Use this command when you already have two QC JSON reports and want to see what
their saved values say. It reads those two files, without opening the session
packages named inside them or running QC again. Python 3.12 or later and the
standard library are sufficient; the CaptureSuite application need not be installed.

```console
python tools/compare_qc_reports.py first-qc.json second-qc.json
python tools/compare_qc_reports.py first-qc.json second-qc.json --json
```

The first command prints a readable comparison. The second emits one complete
JSON comparison on stdout. Shell redirection is optional and is performed by
your shell; choose a new destination that is different from either input.
The command itself creates no files, directories, import caches or settings.

| Exit status | Meaning |
| --- | --- |
| 0 | Both reports were admitted and all parsed values are equal. |
| 1 | Both reports were admitted and the complete comparison contains differences. |
| 2 | Reading, admission or output failed. No successful comparison is emitted for invalid input. |

An output failure can occur after a recipient has received part of the output.
For example, an already closed stdout pipe or a full output device returns 2
without a second shutdown exception. Consumers should check the exit status and
parse the complete JSON. The standalone command was qualified on Python 3.12 and
3.14; this does not change the full application's supported Python environment.

## What the comparison preserves

The report includes the complete parsed first and second documents, their raw
byte counts and SHA-256 hashes, and every difference. The raw hash covers the
exact selected file bytes, including whitespace. Reports with different raw
hashes can therefore compare equal after JSON parsing.

Object key order and JSON whitespace do not affect equality. Array order and
duplicates do: warnings, streams and gaps are compared at their saved positions.
The command does not align streams by ID, reorder records, merge overlapping
gaps or recompute counts and durations. A warning moving to a different array
position is shown at that position, even when its text occurs elsewhere.

Missing fields differ from explicit null. Booleans, integers and floating point
numbers have distinct types, so `false`, `0` and `0.0` differ. Signed float zero
also differs: `-0.0` is distinct from `0.0`. JSON number spelling is otherwise
parsed using Python's integer/binary64 float behavior; `1e0` and `1.0` are equal.
This is not a decimal-token or tolerance comparison. Very long numeric tokens
remain subject to the Python JSON parser's integer conversion limit. Accepted
integers and timestamp strings retain their exact values, including values
above 2^53. The lexical spelling of integer `-0` normalizes to `0` during parsing.

Unknown extension fields remain in the captured documents and participate in
the comparison. No saved traffic light, warning, timestamp, package label or
count is interpreted as new evidence about acquisition quality. Inconsistent
saved counts remain visible as recorded; the command does not repair them.

## Admission and limits

Each explicit input must resolve to a regular UTF-8 JSON file of at most 2 MiB.
The command captures each file once; concurrent changes can yield a different
capture on a later invocation. Its hashes describe the captures actually read.
Directories, FIFOs and other nonregular inputs are refused. Symbolic links to
regular files are readable, with the same captured-byte semantics.

Duplicate object keys, malformed UTF-8/JSON, nonfinite numbers (including an
overflowing exponent such as `1e309`) and unsupported schema IDs are refused.
The following limits apply independently to each parsed input:

- 64 nested objects/arrays; the root object is level 1.
- 50,000 value nodes; object keys do not count as separate nodes.

The complete compact ASCII JSON result, including its final newline, must fit
within 16 MiB. Both captured documents and literal differences count toward
this limit. The budget is checked while accumulating rows, before retaining
an oversized result. Human output has the same final size limit. A valid input
pair can exceed the result limit because its values and pointers are repeated.
Refusal occurs before successful stdout output.

Supported schema IDs are `capture.analysis_qc/1` and `capture.analysis_qc/2`.
The required report fields are:

| Fields | Required JSON type |
| --- | --- |
| `schemaId`, `packagePath`, `sessionId`, `packageState`, `manifestSha256` | string |
| `durationNs`, `sourceCount`, `streamCount`, `openGapCount`, `closedGapCount`, `checkpointCount`, `annotationCount`, `syncAnchorCount`, `integrityFileCount` | integer, excluding boolean |
| `recoveryReports`, `warnings` | arrays of strings |
| `trafficLights` | object with string values |
| `streams` | array of stream objects |
| `gaps` | array of gap objects, required for version 2; optional for version 1 |

Each stream requires string `sourceId`, `streamId`, `modality`, `dataSchemaId`
and `units`; integer `mcapSegments`, `mkvSegments` and `timingSegments`; numeric
`nominalRateHz` (integer or finite float, excluding boolean); boolean `rateOk`;
and a string-array `warnings`.

Each gap requires string `sourceId`, `streamId`, `cause`, `startSessionTimeNs`,
`estimatedLostCount` and `durationStatus`; string-or-null `endSessionTimeNs`
and `durationNs`; and boolean `closed`. These checks recognize the recorded
structure. They do not parse timestamp strings, validate enum labels or infer
relationships among saved values. Version 1 reports that contain `gaps` receive
the same gap structural checks.

## JSON result and API

The top-level `schemaId` is `capture.saved_qc_comparison/1`, with
`scope: "saved_report_values_only"`. `equal` is true exactly when `differences`
is empty. `first` and `second` each contain `bytes`, `sha256` and `document`.
The `document` is the complete parsed saved QC report.

Each difference contains `pointer`, `before` and `after`. Each side contains
`present` and `value`. An absent side has `present: false, value: null`;
an explicit null has `present: true, value: null`. For example:

```json
{
  "pointer": "/gaps/0/durationNs",
  "before": {"present": true, "value": null},
  "after": {"present": true, "value": "17"}
}
```

Pointers follow JSON Pointer escaping: `~` becomes `~0`, and `/` becomes `~1`.
Rows are sorted lexicographically by the complete escaped pointer string;
an index ending `/10` can appear before `/2`. This sorting changes only the
order of difference rows, not the saved arrays. A missing or differently typed
container produces one row containing its complete value. Containers of the
same type are compared recursively.

The standalone module provides:

```python
comparison = compare_bytes(first_raw_bytes, second_raw_bytes)
```

It returns the same report dictionary and raises `ComparisonError` (a
`ValueError` subclass) for refused captures or an oversized comparison. The API
performs no file access. Human output JSON-escapes pointers, identities and
literal values, keeping Unicode/control characters unambiguous in a terminal.

## Validation boundary

The original QC producer from commit
`3f42f7431e3fcfcb60cb2580afaa41d7dc9deb85` was executed before implementation on
two authored synthetic package copies. Four exact existing modules formed an
explicit namespace-package projection, without unrelated package initialization.
Its saved reports record an open gap changing to a closed gap of 17 ns, with an
exact start string `9007199254740993`. Nine expected literal differences include
both package paths and positional warning changes. Input/source bytes and modes
were preserved. The synthetic segment is an inventory-only filename fixture;
no MCAP decoding, real patient data or physical device was involved.

The maintained CLI tests can run independently:

```console
python -B -m unittest discover -s tests/analysis -p test_saved_qc_comparison.py -v
```

This consumer identifies differences between recorded reports. Neither their
hashes nor the comparison authenticate authors, establish sensor coverage,
qualify an installed application, or establish clinical or hardware readiness.
