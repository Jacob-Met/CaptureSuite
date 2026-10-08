# Evaluate a predictions file in Analysis

The Analysis workbench can compare a supplied predictions JSON file with an
existing ML bundle. It uses the same evaluator and source checks as the
`eval --predictions` command.

## Run an evaluation

1. Open the sealed or recovered session in **Analysis**, use **Full session**
   scope, and select **Eval report**.
2. Select the completed **ML bundle job** whose windows were used to produce
   the predictions.
3. In **Evaluation input**, select **External predictions file**.
4. Select **Choose…** and open the predictions JSON file for that bundle.
   The read-only filename field and its tooltip identify the selected file.
5. Select **Run**. Review the job status and diagnostics. If the evaluator
   refuses the input, correct the file or choose another one and run again.
6. Inspect the outputs in **Job inspector**. Use **Export figures…** to preview
   and save selected recorded PNGs with the job's provenance, or use
   **Open job folder** on Windows to inspect the report and retained inputs.

The controls column scrolls when the window is short. Keyboard focus scrolls
the focused control into view, including the file buttons and **Run**.

The input format, target coverage, file limits and scoring rules are documented
in [External prediction evaluation](../ANALYSIS.md#decision-2026-10-08-evaluate-externally-supplied-predictions).
Choose the file for the exact selected bundle: matching the model label alone
does not establish the required source and window identities.

## Choose the intended input

| Evaluation input | What runs |
|---|---|
| **Identity teacher (simulation)** | The existing fixture check compares each teacher value with itself. A previously selected external file is not used in this mode. |
| **External predictions file** | The evaluator checks and compares the supplied values. An empty or unavailable choice blocks Run; it never falls back to the simulation. |

**Cancel** in the file dialog leaves the current file choice intact.
**Clear** removes the choice and keeps external mode selected; choose another
file before running. Clearing moves keyboard focus to **Choose…**.

Changing commands or switching between the two input modes preserves the file
choice within the same session. Opening a different session clears the file
choice while retaining the explicit mode. The choice is local to this
workbench instance and is not saved as a desktop preference.

Starting a job captures its session, bundle ID and evaluation input choice.
The evaluation input controls are disabled until that worker finishes.
The choice stores a path: the evaluator reads and retains the file bytes when
the job executes. Finish writing the predictions file before starting the job.

## Read the result

An external evaluation writes these artifacts under the new job's `eval/`
directory:

- `eval_report.json`: comparison mode, caller-supplied model label, metrics,
  exclusions and input provenance.
- `prediction_input.json`: the exact predictions file received by the evaluator.
- `source_bundle_manifest.json`: the source bundle manifest used by the job.
- `predictions.parquet`: paired teacher/prediction/error rows.
- `figures/`: per-target PNG and PDF figures.

The ordinary `params.json` and `job_manifest.json` identify the request and
record final output sizes and digests. A completed job may retain warnings;
read them with the source context.

On the current workbench, evaluation figures are available through
**Export figures…** and the job folder. The central **Sync** tab is populated
by features/plots jobs, so an empty Sync dashboard after Eval does not mean
the evaluation failed.

The external report identifies `external_predictions` and has no identity
baseline. Identity mode retains `identity_teacher_sim`. Both remain
provisional research outputs. Supplied values and matching source hashes do
not establish model authorship, a held-out study design, calibration or
clinical validity. Analysis leaves the source files and raw capture unchanged.

## Maintainer verification

The input UI is isolated in `widgets_analysis_predictions.py`; the existing
worker and evaluator receive the selected path through ordinary job extras.
No evaluator formula, prediction schema or job-publication rule is replaced.

```bash
python -m pytest tests/ui/test_analysis_predictions.py
```

Native receiving and the exact supported-platform CI result are retained with
the feature's source qualification. The local Mac offscreen Qt run exercises
actual widgets, file dialogs and background jobs; it is not a Windows hardware
or OS-native file-dialog qualification.
