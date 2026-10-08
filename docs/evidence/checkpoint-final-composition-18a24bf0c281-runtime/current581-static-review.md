# Static extension: main 70f to 581

This addendum accepts the bounded source interaction between PR68 and current main `58157fdc1b83a12bb4856ef14b0498cf524a1087` (tree `51c711928a28dc02e100fcdea44cd34512318113`). The earlier complete Windows logs remain bound to checkout `427766ed4beee603ea2e3eadcaceee9f7f76a538`, whose first parent is 70f. No execution of the 581 composition is claimed.

The parent adds external prediction evaluation in eight changed paths. `jobs.py` adds only `prediction_path=params.extra.get("prediction_path")` inside the existing `command == "eval"` arm. Removing that exact line reproduces the 70f file byte for byte. The shared window resolution and all/features/plots dispatch remain unchanged.

The CLI adds `--predictions` to the eval subparser and adds its value to `extra` only in the eval arm when supplied. Removing those two exact additions reproduces the 70f CLI bytes. `run_eval_job` imports and calls the new module only under `prediction_path is not None`. The legacy body after that guard is both byte-identical from its original NumPy import onward and AST-identical to the prior default body. The external module has no checkpoint-window resolver reference. Its numerical/scientific behavior, schema and independent tests are outside this addendum.

The four changed production pins are:

| Path | Git blob |
| --- | --- |
| libs/python/capture_analysis/capture_analysis/eval/job.py | 814cad848e7b2fcce329d407ca10cc1d87f185cf |
| libs/python/capture_analysis/capture_analysis/eval/predictions.py | f2e0e0c240d5d7018ef32d7a8075d06b1c53d7ce |
| libs/python/capture_analysis/capture_analysis/jobs.py | ad0a551e90e5d06ec38a9218277efa24b0030c75 |
| tools/run_analysis.py | a846e6e0550ec4ba1db12a1b989d5e03cfdd69b6 |

## Exact expected composition

The full 922-leaf current-main tree and all its directory hashes reconstruct exactly. The three-way document merges use Git's actual `merge-file` implementation with feature cd1, common prior d43 and current 581 bytes. Both exit zero. Each feature insertion is present once; removing it reproduces the corresponding 581 document exactly.

| Document | Current 581 blob | Expected composed blob |
| --- | --- | --- |
| ANALYSIS.md | 077afcf3943762479d98b39a9f45b72b414007e1 | 13fbc44f76c819edf38b028747fcdf8be6f39a16 |
| PROGRESS.md | 355e8a311c4f7c44fda8e5447258a797cc5a58ee | a6fb020a5276a05105ffd2305d06a16621e6e070 |

The computed expected full merge tree is **e7754d3bf2e93ac0b17cb05833f8a744c2833a3b**, containing **1,007 leaves**: 89 exact feature leaves, the two composed documents and 916 exact unrelated 581 leaves. `expected-composition.json` lists every expected path/mode/type/blob. This is a local static computation, not a claim that GitHub has executed or published this tree.

The latest retained PR response still supplied the older synthetic427 and `mergeable: null`. Root retains final merge authority and must compare the eventual actual merge parents/tree with this expected composition. No PR head, shared source, CI run or production state was changed to attach this evidence.

Run `/usr/bin/python3 verify_extension581.py` from the review root to reproduce these static checks from retained input. No CaptureSuite build, import, test or external prediction execution is part of that verifier.
