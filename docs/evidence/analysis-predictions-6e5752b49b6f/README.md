# Native external-prediction workbench — issue #69

The accepted change gives Analysis users an explicit choice between the existing identity-teacher simulation and a supplied predictions JSON file. The native picker preserves literal paths, cancellation and stale-dialog retirement; normal Run refuses unavailable external input. The ordinary worker captures the selected bundle/mode/path, and the existing evaluator binds and retains the actual file bytes when the job executes.

Two demonstrated workbench defects are also repaired in the shared screen hunk: the existing control column now scrolls instead of compressing controls at smaller heights, and a reserved thread immediately disables Run, enables Cancel and prevents a second launch. The evaluator, JobParams, worker lifecycle, schemas, raw/package handling and figure-export components are unchanged.

## Qualified source and current-parent preservation

Source commit **4987c99c49751461a6b53a90ce9c43e39062ad59**, tree **2d418e2094fae2caa59b17be66e1e7524ace66f0**, composes the accepted runtime onto actual main **3cbb5300bdc79c157370d1b3e599a6c82752d54a**, tree **4af105896633559b35823a7aa2710dc30b2f1740**.

The parent has 1,057 leaves and this source has 1,060. All 1,053 parent leaves outside the four intentional modifications retain exact blobs and modes. There are exactly seven source/docs paths: two existing UI modules, the new input widget, the new test module and guide, and appended ANALYSIS/PROGRESS notes. All four runtime/test files and the guide are byte-identical to independently accepted 983641cc / 4cceca0d. Both current document prefixes are preserved.

[Source preservation](source-preservation.json) records the author's literal comparison. The [independent current-parent receipt](current-parent-receiving.json) separately compares the full native and API inventories and admits all 66 unowned imported modules. Only the current checkpoint helper and explicit true-anchor refusal differ from the earlier received full-session, false-anchor execution. Those older receipts keep their original source identity.

## Actual receiving

| Evidence | Result and original provenance |
| --- | --- |
| [Author record](AUTHOR_RECEIVING.md), [complete archive](author-receiving.tar.gz) | Baseline absence capture; native 28-pass functional run; three current-parent actual jobs; retained-file/output inventory checks; original clipped screenshots; corrected native geometry tests. Historical timeouts, wrong keyboard assumption and conditional-scroll receiver correction remain intact. |
| [Independent functional record](functional-README.md), [archive](independent-functional.tar.gz) | Original source 424298e3: four groups, 12 actual Qt dialogs, six real background-worker/evaluator jobs; path, cancellation, race, isolation, external/identity/refusal/retry and execution-time byte provenance. |
| [Original counterexamples](counterexamples-README.md), [archive](independent-counterexamples.tar.gz) | Actual clipped controls and forced height; separately proven inherited Run-enabled/Cancel-disabled worker state. Baseline source and receiver corrections are retained. |
| [Independent final record](successor-README.md), [archive](independent-successor.tar.gz) | Exact source 983641cc: both 1100×700 and 1280×960 sizes, plus actual Clear → chooser → keyboard Run → held worker → keyboard Cancel → recovery. Both groups pass; source unchanged. |
| [Root source review](root-source-review.json) | Separate final controller/dispatch/queued-input and narrow repair acceptance; no remaining source finding. |
| [Current-parent packet](current-parent-receiving.tar.gz) | Complete independent literal tree/dependency comparison, exact script and original execution output. |

The production author inspected both final viewport images and actual held/recovered images. The final independent receiver admitted 62 imported project files unchanged. Its real cancellation reached the evaluator before output creation. The source and reviewer records distinguish actual Qt offscreen focus from operating-system behavior.

## Platform gate

Local execution used the existing Python 3.12.8 / PySide6 and Qt 6.11.2 Mac runtime, without installs or hardware/daemon calls. The unchanged application imports Windows named-pipe APIs before constructing MainWindow. No Windows API stub was introduced. The permanent test of actual MainWindow(auto_connect=False) at its minimum 1100×700 is explicitly skipped on Mac and must pass in the existing windows-2022 / Python3.12 hosted suite. **That supported-platform result is pending at this evidence freeze.** Hosted results are recorded on the PR with their actual checkout and tree.

The original functional source was not rerun solely to relabel it to the newer parent. Current-main source admission and the actual hosted suite qualify that composition separately.

## Operator behavior and limits

See [Evaluate a predictions file in Analysis](../../design/research/EXTERNAL_EVALUATION_WORKBENCH.md). The existing gallery does not directly tab nested eval figures; the guide points to the existing Export figures action and Windows Open job folder. The gallery owner retains that work. A selected file can change before execution; the evaluator's retained input is the execution-time provenance. The bundle selector remains editable while a queued job retains its captured value.

The evidence uses explicit synthetic sealed bundles and files. It does not assert trained-model efficacy, scientific validity, hardware capture, installed deployment, Cocoa dialogs or Mac execution of the full Windows shell.

## Integrity

Each archive was read back and every regular member compared with its manifest before preservation. The three independent archives are copied unchanged, not repacked. Their original SHA-256 values are retained in [qualification-manifest.json](qualification-manifest.json), along with every readable record. The current-parent archive is a separate byte-preserving transport of that later review.

All earlier failures remain labeled as failures. Reproduction commands, source snapshots, actual inputs/results and raw logs are inside the corresponding packet. Do not substitute these records for receiving a changed source or relabel their platform.
