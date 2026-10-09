# Standalone recorded-event report

Create a new HTML file to inspect and share the records returned from a retained
CaptureSuite package. The file opens in an ordinary browser without CaptureSuite,
Qt, a daemon, a server or a network connection.

## Use the command

Use the project's supported Python 3.12 environment and a checkout containing
this report and the qualified gap reader. From that checkout:

~~~sh
python tools/report_recorded_events.py /path/to/session.mmsession /path/to/new-report.html
~~~

The same command works from another directory when the script and input/output
paths are absolute. The output's parent must already exist. Choose a new file
outside the original package; the command refuses an existing path, including
a dangling symbolic link. It does not create output directories or overwrite a
previous report.

A successful command exits 0 and prints JSON containing the actual package and
output paths, report byte count and SHA-256, reported state and returned record
counts. Open the resulting HTML file directly. Section links move between the
package summary, checkpoints, annotations, sync records and normalized gaps.
Every record starts expanded; its native disclosure control can collapse it.
Expand any collapsed records before using the browser's print command.

A refused command exits 1 with an actionable message on stderr. Invalid command
arguments use argparse's ordinary exit 2. Reader or state errors happen before
output creation. Exclusive creation protects a destination that appears between
admission and writing. A write, flush, synchronization or close error produces
no success receipt and retains any new partial file for inspection; it does not
replace an earlier report or claim whole-package rollback.

## What the document shows

The overview labels metadata as reported by the existing package reader:
package path, session identity, state, wall times, source identifiers and
recovery report paths. A recovered-state notice remains visible for
`finalized_recovered`; the report does not interpret recovery report bodies.

Checkpoint, annotation and sync records keep their full returned dictionaries,
unknown keys, values and list order. Each is a plain-text JSON representation.
Integers and decimal timestamp strings are preserved without conversion through
floating point. Original and effective timestamps remain separate fields; the
report does not choose one, order events by time or infer a section boundary.
Unicode and markup remain literal text. Escaped lone surrogate values retain
their escape notation so the output remains valid UTF-8.

Gaps are labeled as normalized `GapSummary` projections with seven fields.
Their aliases, defaults and coercions have already been applied by the reader;
unknown original gap fields are unavailable. Start/end integers are nanoseconds,
and JSON null remains distinct from an end value. The closed flag and end value
remain independent. No gap duration or total lost time is calculated.

Counts always mean records returned by the reader. Missing optional event files,
unsupported container shapes and nonobject entries filtered from a recognized
list can cause omissions that this reader cannot count or explain individually.
An empty section therefore says that no records were returned, not that none
ever existed. This report cannot establish capture completeness or repair loss.

The CLI accepts only the exact reported states `finalized` and
`finalized_recovered`. That is metadata admission, not integrity verification,
proof that another process has stopped writing, or an atomic filesystem snapshot.
The reader may observe concurrent package changes. Raw streams, arrays, integrity
contents and recovery bodies are not presented as verified evidence.

## Read-only scope and dependency

The new renderer consumes `ReviewSummary`; the CLI calls the original
`capture_session.package_reader.load_review_summary` through a normal physical
package import. The current source parent is the independently received
[c0437668fbc9d7ce6292c7b733f91dc8b2fd94f5](https://github.com/Jacob-Met/CaptureSuite/commit/c0437668fbc9d7ce6292c7b733f91dc8b2fd94f5),
with unchanged reader blob `cdfba8a26736856683ea865b9df67b36ad120e40`.

That reader's existing error contains the physical file path and line number
for malformed or nonobject gap rows. This consumer preserves that error rather
than skipping the row or exporting a reduced result. Its exception is
`capture_session.package_reader.SessionPackageError`, distinct from the
package-level class of the same name.

Normal import includes the existing initializer, app paths, registry and
settings modules. Their classes are not constructed by this command. It does not
open an app registry, write preferences, initiate recovery, register a new
package/bin entry, create a processing job, invoke a provider or process raw
capture streams. No dependency manifest changes are needed for this standard
library consumer; the project's Python version range remains `>=3.12,<3.13`.

A report is a view, not an archival replacement for the original package.
Keep the package and any original integrity/recovery evidence when sharing the
HTML. The command does not calculate or promise a source-wide before/after
digest; the execution receipts separately record input preservation for their
specific frozen fixture.

## Design and ownership

This is an additive document exporter following the existing offline CLI and
static QC HTML pattern. It does not add a web application or replace the single
tabbed PySide6 interface. Its flat panels, light/dark colors, metric typography,
spacing, borders and keyboard focus treatment follow the existing
[design system](../DESIGN_SYSTEM.md). All styling is inline; there are no scripts,
external fonts, remote resources or generated links from record content.

The document's content security policy disallows resource loads and permits
only its inline style. All record and metadata values are escaped text.
Navigation uses fixed local fragment links. Browser print uses a light palette.

Reader owner 2479534e1930 retains the parser. The native event/Review owners
(#76/#83), offline Qt viewer (#107), video/export owners (#109/#110) and QC
collector/report owner (#79) keep their source and receiving boundaries.
This command adds a portable user artifact without adopting their application
containers, private interfaces or acceptance results.

## Focused qualification

The maintained standard-library tests cover literal structured records and
returned order, exact normalized gap values, visible omissions and recovered
state, valid UTF-8 escape handling, an actual physical CLI output, exclusive
destination preservation, the qualified reader's downstream error and
nonfinalized-state refusal. These are report consumer cases, not another run
of the old eleven gap-reader, native Qt, video or analysis campaigns.

The dedicated delivery records distinguish supported Linux Python 3.12 CLI
execution from a later browser opening the resulting physical HTML on macOS.
They also retain the exact source inputs, input/output files, original
refusals, command exits and resource observations. Native Windows/full-suite
qualification and any unavailable Ruff/pytest gate remain separate; an unrun
gate is not a pass.

Source coordination and complete actual evidence are recorded in
[the report's evidence directory](../../evidence/recorded-events-report-c945953fdeb7/README.md)
and [the existing reader issue reservation](https://github.com/Jacob-Met/CaptureSuite/issues/111#issuecomment-6078399030).
