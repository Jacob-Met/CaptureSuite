# First candidate: retained state-conservation failure

PR79 source `2717861936b0d3a68f235ebe65f28f4e08dd1dd6` / tree
`34ce1440bf3dbe9f01f455a881b2a3c903213ea0` was actually executed at
`c527b3af92eb01daf10087a51196c07281e31dfc` on the current sync-anchor composition.

## Dedicated native receiver

[Run 37811117397 / job 113427903017](native-receiver.log) passed the two real
native collector/renderer controls. The actual multi-package command then returned 0
and reported two collected packages. All authored package and observed source bytes
stayed exact, but the unchanged receiver detected `applicationStateUnchanged=false`.

That assertion preceded product-output admission. This phase does **not** establish
exact product-report equality or browser behavior. The initial receipt retained a
state-conservation boolean, not the changed filenames; that diagnostic limit is preserved.

The complete 16-chunk bundle and all five [native/report members](receiving-report.json)
are decoded and hash-verified. These HTML/JSON files are the native positive controls,
not admitted product outputs. The independent parent review is retained
[verbatim](parent-first-candidate-review.json).

## Maintained gate

[Run 37811117403 / Python job 113427903637](maintained-python.log) reached the
existing 300-second whole-suite limit. The native receipt reports no process exit,
no final counts and no JUnit, with all 1,065 source files unchanged. No count is
inferred from partial dots. This is a separate observed boundary, and its limit was
not relaxed. Native CMake was still in progress at this phase seal.

## Next bounded change

Source review found the eager package → jobs → pipeline → sync-dashboard → plot-style
import chain, including module-time Matplotlib/pyplot initialization. No initial changed
state filename is invented. Issue74 comment6064791357 and the owner notice6064791892
reserve a lazy boundary for the four actual existing job exports. A separate independently
authored fresh-process receiver will observe the old import's isolated state and then
check no-write QC imports plus public API identity/signature compatibility.

The original three receiver/workflow files and state assertion remain unchanged.
No cache relocation, warmup or guessed passing result is used. The source at this
phase still contains the original eager initializer.

[Qualification](QUALIFICATION.json) binds the graph, complete-tree bridge, all36 observed
source inputs, both raw native logs, actual bundle members and remaining limits.
The original missing-capability packet remains immutable in the parent evidence history.
