# Retained feature-table preview

## Researcher workflow

The Analysis job inspector includes a feature-table selector and **Preview table**.
Choose a table listed by the loaded completed job, then open its native read-only
preview. The table retains physical column and row order. It shows at most the
first 200 rows, with the original total row count and the preview limit displayed
together. Empty retained tables remain valid and show their columns with zero rows.

The column information includes the exact retained name, Arrow type, recorded
units, calibration flag, and optional description. Provenance identifies the
loaded job, session, relative table path, actual table SHA-256 and the loaded
manifest SHA-256. The existing saved-parameter controls and output inventory
remain available. Loading or clearing a job closes its preview and invalidates
any late result from that job.

Integer cells stay integers throughout reading and display. In particular, signed
and unsigned 64-bit values and nanosecond timestamps above 2^53 are never routed
through a floating-point DataFrame. Missing values display as **NULL**, numerical
NaN as **NaN**, and infinities as **Infinity** or **-Infinity**. Strings use JSON
quotes and escapes: a recorded string containing NULL displays as **"NULL"**.
Booleans display as **true** or **false**. Float values use their retained Python
scalar representation, including negative zero. Selecting a cell exposes its
complete displayed value in a read-only text view.

This viewer reads saved outputs. It does not select a different analysis result,
recompute features, edit parameters, resample timestamps, infer units, hide gaps,
or overwrite a package. The separately owned selected-column export operation in
issue #78 remains the route for producing transferable table subsets.

## Accepted retained output

The viewer uses the existing capture.analysis_job/1 and
capture.analysis_feature_schema/1 formats. It reuses the current
analysis_job_comparison module's completed-job admission, immutable
JobParameters, bounded JSON decoding and parameter revalidation. It adds no
on-disk schema or dependency.

A preview requires one manifest-listed feature_parquet output and the single
features/_schema.json output of kind feature_schema. Their actual byte counts
and SHA-256 identities must match the loaded job inventory. The job must retain
the original valid parameter bytes and paramsDigest. The source job and parameter
identities are checked again before returning a preview.

The schema must identify the selected relative path and a positive integer
feature schema version. Metadata column names must be unique and match the
Parquet column names exactly. Every column must record string units and a boolean
calibration flag; an optional description must be a string. An optional recorded
row count must equal the Parquet row count. Metadata is matched by literal column
name while the physical Parquet order is preserved. Missing, extra, duplicate or
contradictory metadata refuses the complete preview.

The supported Arrow types are primitive boolean, integer, floating-point,
string/large-string and null. The current feature writer produces these ordinary
feature columns. Nested, binary, temporal, dictionary and extension types receive
an explicit unsupported-type message. They are never flattened or coerced into
plausible-looking values.

Relative output paths must contain real components inside the retained job.
Absolute paths, drive syntax, backslashes, empty components, "." and ".." are
refused. Linked files, linked intermediate directories and multiply linked table
or schema files are refused. The stream checks pathname and open-handle identities
without mixing Windows' different ctime semantics. Changed or replaced source
files and directories produce an actionable reload message.

## Resource and lifecycle limits

The limits apply to a complete preview. A refusal leaves the original table
available for another analysis tool and does not silently hide columns.

| Limit | Value |
|---|---:|
| Retained table choices in one job | 512 |
| Columns in one preview | 128 |
| Rows displayed | First 200 |
| Table file size | 256 MiB |
| Existing JSON admission limit | 4 MiB per document |
| Parquet Thrift total string limit | 4 MiB |
| Parquet Thrift container limit | 100,000 items |
| Uncompressed encoded row-group budget | 32 MiB |
| Arrow result and accumulated display budget | 8 MiB each |
| One text cell | 4,096 characters |
| Arrow batch size | One row |

Before reading data pages, the reader examines only the row groups needed to
cover the first 200 rows. It sums their declared uncompressed column-chunk sizes,
also respecting the row group's total-byte declaration, and refuses a budget
over 32 MiB. Invalid dimensions, negative sizes and external column-file
references also refuse.

The uncompressed encoded size does not by itself bound decoded Arrow values.
Dictionary encoding can repeat a large string many times. For that reason the
reader requests **one-row Arrow batches**, checks batch.nbytes before Python
conversion, and admits each scalar before asking for the next row. It retains
at most 200 rows and checks the accumulated Arrow and formatted-display budgets.
It uses column indices so punctuation in a name never becomes nested-field
selection. No pandas conversion occurs in the reader.

The independent native design witness is a 3,490-byte file containing 200
repetitions of a 64 KiB string. Its uncompressed encoded column data is 65,588
bytes. A 200-row batch materializes 13,108,000 bytes, while a one-row batch is
65,540 bytes. That finding changed the initial batch design before final
acceptance. The receiver preserves the actual witness and receipt; the authored
regression independently verifies complete refusal after the first bounded row.

These are admission and retained-result limits, not a claim about the entire
desktop process's resident memory. The existing Arrow decoder and operating
system still own their internal allocation behavior.

Catalog and table reads run outside the UI thread. Each feature bar permits one
active operation and at most the latest pending request. Cancellation is
cooperative at file-chunk and row boundaries. Clear, reload and destruction
invalidate the generation and close any preview immediately; an old worker
cannot repaint the new job. The UI never waits synchronously for a read or
terminates a thread.

## Source and receiving boundary

Issue #92 belongs to 7879c2abc07f/next_production. The original current base is
9e9204f76b105426b0affaa74733175c052f27ba. Authored runtime source is the new
analysis_feature_preview.py reader and widgets_analysis_feature_preview.py native
widget, plus five additive lines in widgets_analysis_plots.py: the import and
JobInspector construction, clear and load hooks. All FigureGallery methods,
saved-parameter controls, Analysis screen, history, feature writers, exporters,
numerical code and existing workflows retain their original bytes and ownership.

The first native reader attempt passed 34 cases. A separately frozen independent
receiver reproduced the absent original preview entry point and discovered the
dictionary expansion concern before inspecting the candidate. The corrected
reader passed all 35 authored cases on Python 3.12.15 with PyArrow 25.0.1.
Read-only source snapshots, source hashes, raw JUnit/output, and the original
first-pass source are retained separately. The widget author and independent
receiver qualify actual Qt controls against frozen source copies.

Qualification is native component receiving on the named environment. It does
not claim installed desktop adoption, supported Windows integration, physical
capture, scientific validation, or GitHub Actions results. Existing integration
owners and required platform gates remain in place.

## Reference APIs

The project already declares PyArrow >=14. The used metadata limits,
ParquetFile.iter_batches, row-group selection and uncompressed-size metadata
are documented in the original supported API:
[ParquetFile](https://arrow.apache.org/docs/14.0/python/generated/pyarrow.parquet.ParquetFile.html)
and
[ColumnChunkMetaData](https://arrow.apache.org/docs/14.0/python/generated/pyarrow.parquet.ColumnChunkMetaData.html).
No newer-only reader options or dependency upgrades are introduced.
