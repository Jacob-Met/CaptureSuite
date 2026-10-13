# Offline analysis output on legacy consoles

The offline analysis command prints its job identifier, status, result directory,
and available QC counts. A successful job must retain its normal exit status even
when a result path contains characters outside the output pipe's encoding.

The CLI now formats each existing result or error line for that stream's own
encoding. Representable characters remain unchanged; unrepresentable characters
appear as explicit backslash escapes. For example, a cp1252 pipe displays the
Chinese characters in a path as Unicode escapes. A UTF-8 stream retains the
original characters. Stored paths, job manifests and data keep their exact text.
The output stream's encoding and error policy are not reconfigured.

Exit semantics remain those of the analysis result: ordinary completion and
completion with warnings return 0, --strict-warnings returns 2 for a warning
result, and failed jobs or exceptions return 1. Exceptions retain their recovery
notes, including the path to a retained failed attempt. Genuine output I/O errors
such as a broken pipe still propagate. Argument parsing and help are unchanged.

## Observed Windows failure

The original CLI was invoked on a copied video recording named
video-分析.mmsession using the existing MSI Python 3.12.10 environment. Its default
redirected output used cp1252. The analysis job completed with warnings and no job
errors, writing its feature table and both figures; all nine original and copied
raw-session fingerprints stayed unchanged. Printing the final result directory
then raised UnicodeEncodeError, incorrectly changing the CLI exit to 1.

The original job and traceback remain preserved. Receiving of this correction
uses fresh copied recordings and new result jobs rather than overwriting that
original evidence.

## Focused verification

The new tests exercise real ASCII, cp1252 and UTF-8 TextIOWrapper streams, success,
warning/strict-warning and failed statuses, exception notes, a Unicode StringIO
stream, and broken-pipe/ordinary output errors. Two real subprocess tests run QC
against copied Unicode-named session fixtures under explicit cp1252 and UTF-8
pipes, inspect the resulting job and verify raw input fingerprints.

The independent review and exact native receiving result are recorded in
https://github.com/Jacob-Met/CaptureSuite/issues/131 . The separate current CLI
reference owned by issue115 remains unchanged. This adjustment concerns human
readable console text only; machine-readable paths remain in the saved job files.
