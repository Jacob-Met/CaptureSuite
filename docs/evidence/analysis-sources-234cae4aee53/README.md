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
