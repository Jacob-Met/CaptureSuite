# Export selected feature columns

Analysis jobs already retain full Parquet tables, CSV mirrors and a column schema.
Use this exporter when another analysis tool needs one retained table with a
specific set of columns, in a specific order, together with its original job records.

The exporter reads an explicitly selected completed job. It keeps every row in its
original order and does not run analysis again. Column names are literal, including
spaces, Unicode and dots. Units, provisional/calibrated flags and other feature
metadata come from the retained job.

## Command

Run from the repository with its Python 3.12 analysis environment:

```sh
python tools/export_feature_table.py SESSION.mmsession/processing/jobs/JOB_ID \
  --table features/numeric/source-73656e736f72/stream-766f6c74616765/windows.parquet \
  --column t_start_ns --column "input 1_mean" \
  --format both --output /existing/external/folder/selected-features
```

Use an exact `relativePath` whose `kind` is `feature_parquet` in the selected
job's `job_manifest.json`. Repeat `--column` in the desired export order, or omit
it to retain all columns. Formats are `csv`, `parquet` and `both` (the default).

The destination must be new, its parent must already exist, and it must be outside
the entire session package. Existing files or directories are refused. Exit 0
means a completed export; argument errors exit 2 and export refusals/failures exit 1.
The command prints the destination, row count and selected column count.

The library entrypoint is:

```python
from capture_analysis.feature_table_export import export_feature_table

manifest = export_feature_table(
    job_dir, table_relative_path, new_output_dir,
    columns=["t_start_ns", "input 1_mean"],
    output_format="both",
    batch_size=8192,
)
```

`columns=None` retains every column. A string is not a column sequence. Empty,
duplicate or unknown selections are refused. The result is the same dictionary
written to the completed export's `manifest.json`.

## Files and provenance

| Export file | Meaning |
|---|---|
| `table.csv` | Selected values, when CSV is requested. |
| `table.parquet` | Selected Arrow fields and values, when Parquet is requested. |
| `_schema.json` | Versioned selected-column schema, metadata and CSV reader settings. |
| `source/job_manifest.json` | Exact bytes of the original retained job manifest. |
| `source/params.json` | Exact bytes of the original retained job parameters. |
| `source/features_schema.json` | Exact bytes of the original complete feature schema. |
| `manifest.json` | Completed export, source identities, selection, row count and output identities. |

The export manifest's `schemaId` is `capture.feature_table_export/1`. A completed
record has `status: "completed"`, the original job/session IDs and job status,
the original parameter digest, the selected table path, actual SHA256 and byte
counts for all four selected job inputs, selected column order and row count.
Its output inventory hashes every exported data/provenance file except the
manifest itself. Export success describes a faithful data handoff; original
warnings and provisional or uncalibrated scientific status remain unchanged.

The schema sidecar's `schemaId` is `capture.feature_table_export_schema/1`.
`tableMetadata` preserves the original table metadata with its `columns` list
projected into requested order and the checked row count. Each selected column
object retains its original units and all other fields without inference.

`arrowSchemaBase64` contains a base64-encoded Arrow IPC schema for the exported
fields. `sourceArrowSchemaBase64` contains the original complete Arrow schema.
Field metadata and non-pandas schema metadata are retained in the projection.
Original pandas metadata is retained in the source schema, while the derived
schema omits it because its index and column reconstruction instructions describe
the original frame. This does not remove table values or change column types.

## Read CSV without losing types or null distinctions

CSV readers commonly infer timestamp integers as floating point or interpret
strings such as `"NaN"` as missing values. Use the exported schema and its reader
settings explicitly:

```python
import base64
import json
from pathlib import Path

import pyarrow as pa
import pyarrow.csv as csv

directory = Path("selected-features")
metadata = json.loads((directory / "_schema.json").read_bytes())
schema = pa.ipc.read_schema(
    pa.BufferReader(base64.b64decode(metadata["arrowSchemaBase64"]))
)
table = csv.read_csv(
    directory / "table.csv",
    parse_options=csv.ParseOptions(newlines_in_values=True),
    convert_options=csv.ConvertOptions(
        column_types=schema,
        null_values=[""],
        strings_can_be_null=True,
        quoted_strings_can_be_null=False,
    ),
)
```

The UTF-8 CSV uses comma separation and a header. An unquoted empty field is null;
a quoted empty string is an actual empty string. Quoted strings such as `"NaN"`,
`"null"`, Unicode text, commas, quotes and embedded newlines retain their values.
Explicit integer types preserve values above 2^53. Floating NaN, infinities and
nulls remain distinct; CSV does not promise preservation of a NaN's payload bits.

CSV supports Boolean, signed/unsigned integer, float32/float64, string and
large-string columns. Other types are explicitly refused for CSV or `both`.
Select `parquet` for nested or other Arrow types supported by the Parquet writer.
Use a typed Parquet reader such as `pyarrow.parquet.read_table` for direct import.

## Admission, immutability and failures

A selected job must be at `PACKAGE/processing/jobs/JOB_ID`, with
`capture.analysis_job/1`, a matching `jobId`, a nonempty session ID and status
`completed` or `completed_with_warnings`. The exporter validates exactly one
manifest-listed table, parameters and feature-schema output, including declared
SHA256 and byte counts. The feature-schema version, unique column names, metadata
and any declared row count must agree with the actual Parquet table.

A relocated retained package is supported: the historical absolute `packagePath`
is copied as provenance and is never followed. The current selected package path
defines the destination exclusion boundary. The exporter does not rerun raw
integrity checks or claim that retained results describe later raw/package edits.

Selected relative paths cannot escape the job, use Windows alternate streams,
or contain symlinks/junctions or hard-linked selected files. JSON metadata rejects
duplicate properties and
non-JSON numeric constants and is limited to 16 MiB per document. The selected
job's four input files are hashed again after reading to reject a concurrent change.

Reads and writes use Arrow batches. To keep names such as `a.b` literal even
beside a nested `a` field, complete source batches are read before selection by
column index. Batch size limits rows per batch, not total decoder memory or bytes;
very wide/large row groups can still require substantial memory. No time filter,
resampling, interpolation, normalization or feature recalculation occurs.

Admission failures create no destination. A later read/write failure retains the
new directory, attempts to record `failure.json` with `status: "failed"`, and
does not publish a completed `manifest.json`. A temporary
`manifest.pending.json` may remain after a manifest-write failure. If storage
cannot accept even a failure record, stderr still identifies the incomplete
directory. A directory without a valid completed manifest is not a successful
export. Pick a different new destination after fixing the cause; the exporter
does not overwrite or resume an incomplete result.
