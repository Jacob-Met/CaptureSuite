# Multi-package QC: original native receiving

This immutable packet retains the real missing-capability baseline for CaptureSuite #74 / PR79.
It does not contain a passing implementation or a browser-layout claim.

Executed source head `13164f0e52ad27ca512b90ffd0165329a1fe1abd` has tree
`ad6e9d2dc3a81ec1aa1778bd60a911ba266f5ea3` and directly parents actual main
`a2fd6c58ccc97c7262b97570a85d8aae8dfb978c`. Every one of the 1,050 existing
leaves is retained, with only the three independently frozen receiver files added.

The hosted synthesized checkout was `56ec61aa8e272f3633440cc05fa39eda7c853d69`,
with the same complete tree. Both proposed product files were absent.

## Actual outcome

- [Dedicated native receiver log](baseline-native-receiver.log): run 37809326650 / job 113421774576.
  The real collector/renderer inventories both copied finalized packages, then the actual
  two-package CLI command exits 2 with Python's missing-file error. All authored input
  files/directories and application state are unchanged. One positive group precedes the expected failure.
- [Maintained Python log](baseline-maintained-python.log): run 37809326170 / job 113421772517.
  522 passed, 6 skipped and the same one expected missing-command failure; 2 warnings, 271.25 seconds.
- [Original receiving report](receiving-report.json) retains exact command arguments, output,
  source/input hashes and failure. Browser receiving was not reached.
- [Native report 1](native/001-qc.html) and [native report 2](native/002-qc.html) are the
  actual unchanged collector/renderer positive-control outputs; their JSON companions are retained.

The complete 16-chunk bounded bundle and each of its five members were independently decoded
and verified against their byte lengths and SHA256 values. Git blob hashes are also recorded.
Both the independent consumer author and the parent reviewer received the causal result separately.

[Qualification](QUALIFICATION.json) pins source, graph, full-tree preservation and runtime limits.
[Frozen acceptance criteria](ACCEPTANCE-CRITERIA.json) predate production.
The publication index binds every packet payload; all earlier source remains unchanged.

The maintained fixture contains two 28-byte MCAP placeholders. These runs inventory descriptors
and metadata; they do not decode real capture streams or certify scientific/clinical validity.

The [independent parent review](../parent-preimplementation-review.json) binds the full base/checkout tree, all 34 observed source/fixture pins, both original logs, the five native outputs and the source review of the later unexecuted candidate. Candidate source review is separate from this baseline's actual absence run.
