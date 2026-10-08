# Analysis source selection receiving

The frozen initial product is commit 38ffed074a89e646d5c59c0918fba3b5703d06f2.
Commit 1953c9bc8823344960c49130e6f4ddabc2369953 only preserves the exact original
baseline script alongside its required licensed runnable copy.

- baseline/ retains the actual missing-control pytest failure on untouched 2f4dcf3
  production. The directory-token / descriptor-ID assertions passed before that
  expected UI failure.
- The earlier standalone baseline produced completed numeric artifacts but did
  not finish its Qt lifetime. Its exact executed script and incomplete result
  remain distinct from a UI or raw-preservation pass.
- initial-1953c9b/ retains the first candidate pytest attempt, killed by its
  180-second driver deadline after one control passed and the first real job
  completed its backend artifacts. No JUnit was produced. All 879 source files
  were unchanged and the working tree remained clean. This attempt is rejected.
- qt-loop-control.json and qt-loop-candidate.json run actual Qt event loops with
  bounded timers, observing worker.finished and thread.finished independently of
  artifact existence. The original 2f4 screen implementation and unchanged
  candidate both finish normally in under two seconds, update the existing UI
  completion state, and preserve every raw file. No explicit quit or cancellation
  is used on either successful path. The candidate observer adds only a passive
  flag identifying whether the UI completion state has already been populated.

The candidate test wait helper is changed to run a real QEventLoop with a timer,
matching the application event-processing model. No product lifecycle, completion
handler, cancellation path, backend, or source-selection code is changed for this
harness correction. It is not an application lifecycle repair. The original
failing driver and source hashes remain retained; later qualification has its own
source pin and receipt.

The supported Windows MainWindow case remains a required gate. Local Linux skips
that case explicitly because it imports the native named-pipe transport.

## Focused accepted qualification

qualification-7b2c999/ binds the clean source commit
7b2c999584909fd7ef5623e2133b9e8f507031d8 to 10 passed tests and one explicit
Linux MainWindow skip. All 886 source files stayed unchanged. The three actual
Qt/QThread jobs cover all sources, sampler.a (two streams), and sampler.b with
an exact time range. Their JobParams, manifests, numeric tables, complete-package
QC, and all raw file hashes are retained in actual-jobs.json.

presentation-7b2c999/ contains the inspected Linux offscreen Qt screen and
checkbox chooser. The successful in-memory image capture is separate from the
prior filesystem PNG failure caused by ENOSPC. These images are not Windows
presentation and do not claim the later composed source was executed.

The Windows MainWindow test also saves its displayed window into build/evidence
for the supported-platform receiving run. This evidence-only addition follows
the local 7b2c999 qualification; production source remains byte-for-byte equal.

## Current-main composition and native custody

composition-70f34e3.json records the ordinary composition with main
70f34e3b982523b544a9370d2316a1b69d79bd70. Every one of the 959 resulting leaves
is accounted for: 41 candidate leaves, 917 unchanged main leaves, and the
composed PROGRESS document. The only shared change was PROGRESS; the new figure
export and finalized manifest implementation are retained exactly. This is a
source-composition receipt, not a run of that composed source.

qualified-source-7b2c999.bundle preserves the exact local qualified history and
tree. It requires the already-published 2f4dcf3 commit; native-custody.json records
its bytes and digest. The existing Mac source checkout also retains the later
complete composition. No additional dependency environment was allocated.

## First supported Windows attempt

windows-37803865986/ retains the actual Python job log and exact c4149a1 merge
checkout. Ruff stopped before pytest because the publication test omitted two
blank lines separating repository test imports. The prior passing stdin check
used a filename relative to the workspace, so its import classification differed
from the repository's actual check. That mistaken invocation is retained.

The controlled check with the actual repository working directory and an
absolute stdin filename rejects that same source and accepts the restored
original spacing. The parsed Python AST is identical; no product or lifecycle
source changed. No Python runtime or MainWindow pass is claimed from that run.


## Windows receiving and modal test scheduling

The first Windows run failed before pytest on native import spacing; its original evidence remains above. Run 37805203258 then passed lint but reached the existing 300-second test deadline. Its partial outcomes cannot identify an exact executing case. The raw log, receipt and source manifest are retained under `windows-37805203258/`; no JUnit or pass is claimed for that run.

A separate diagnostic branch changes only pytest verbosity, durations and 45-second stack reporting while retaining the 300-second limit. Run 37809372315 passes 490 tests with six daemon skips in 193.59 pytest seconds (194.36 wrapper seconds). All source-picker jobs and the full MainWindow case pass; the source snapshot is unchanged. CMake is deliberately skipped only on that diagnostic push, so this is positive Windows Python evidence and not a substitute for the normal complete PR gate. Two existing scope plot cases take 68.93s and 63.12s and pass after trace samples show Matplotlib layout work. No timeout cause or application lifecycle repair is inferred.

`diagnostic-37809372315/selected-evidence.tar.gz` preserves the exact received JUnit, log, receipt and source-manifest bytes. Both original full workflow ZIPs remain at their recorded native custody paths, with archive digests. The Windows MainWindow PNG is retained, but all application text renders as missing-glyph boxes in that offscreen runtime; it qualifies execution/layout only. The separately recorded Linux presentation is readable.

Root's independent actual Qt receiver demonstrated a distinct scheduling flaw in the original test helper: delivery of its single zero timer before the real click left the later modal without an operator. The original source and negative receipt are retained under `modal-scheduling/`. The repaired helper owns a timer that retries until this picker's modal exists, stops before operating its controls, bounds a stalled interaction with a targeted five-second rescue, and stops both timers on every return. The same ordinary and forced-early Qt interactions pass without the independent watchdog. One actual-screen regression retains that scheduling challenge. Production picker/screen hashes stay unchanged. The final normal Windows gate receives the repaired test and current main composition.
