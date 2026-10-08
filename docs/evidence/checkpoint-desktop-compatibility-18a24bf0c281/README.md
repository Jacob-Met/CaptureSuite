# Desktop checkpoint compatibility after the scope picker merge

This is a bounded compatibility adaptation for CaptureSuite issues #53 and #54,
composed against upstream `3e3ecc5ecc1cfc79c79901eb5cffe10b0ec5852e`.
It changes the existing real-thread test's checkpoint selection and the semantic
contract document. The already qualified closing-section resolver stays frozen.

## Maintained interval and selection

The existing test records two checkpoints named Movement: `section-one` at
50,000,001 ns and `section-two` at 150,000,001 ns. Both its Time range and Checkpoint
section branches assert the interval **[50,000,001, 150,000,001] ns**. Its original
section branch chooses `section-one`, which suited the former following-section
resolver. With the closing-section resolver, that checkpoint instead resolves
[0, 50,000,001] ns.

The adaptation selects `section-two`, which closes the same already asserted
interval. Exactly three test lines change: the picker index and the two checkpoint
identity assertions. The interval constants, repeated-label checks, real QThread
and MCAP output path, per-sample bounds, worker snapshot checks, raw file hashes,
and cleanup are byte-for-byte unchanged elsewhere in that test file.

The semantic document now describes the preceding checkpoint (or zero) through
the selected checkpoint. It preserves timestamp aliases, zero handling, stable
ordering, the ID-shadow guard, gap behavior, and the desktop's existing
positive-duration selection policy. No desktop production source or historical
peer receipt changes.

## Validation and remaining execution gate

**No native Qt test was executed in this compatibility pass.** Read-only checks
found neither PySide6 nor shiboken6 in the author's private Python 3.12.8 Capture
environment, the Mac's separately inspected Python 3.12.8 and 3.13.7 interpreters,
or the local Python 3.12.14 runtime. No dependency installation was attempted.

The original maintained assertion conflict is therefore a source-derived finding,
not a recorded runtime failure. Both original and adapted test files parse with
Python's AST parser; the adapted test equals the original after only the three
specified substitutions; `git diff --check` passes.

In a supported full checkout with Qt and the normal project dependencies, compose
the exact upstream source with frozen resolver blob
`aaafd8db78f82a5a56178135dbed5bfd4f45c634` and these two file changes, then execute:

```sh
python -m pytest 'tests/ui/test_analysis_scope.py::test_selected_scope_reaches_real_thread_job_and_mcap_outputs[section]'
```

The existing source, public CLI, numeric MCAP, and independent persisted-package
receipts remain qualified for their exact recorded source states. They do not
establish that this new desktop composition has executed. The peer's
`peer-checkpoint-after.json` records an earlier ID-shadow review on source
`36254496e386568de05148db9bd9fa4d69020dd4`; its retained following-section bounds
must not be relabeled as closing-section compatibility evidence.

## Source custody

`assessment.json` records exact upstream, resolver, original-file and adapted-file
identities, the bounded 0ed1 → 3e3 peer comparison, and the static checks.
`runtime-availability.json` retains the tool responses for the dependency checks.

The local source commit is `6878dcce23a3f439642312d845996746d5d2921c`,
on a deliberately scoped two-file baseline commit
`6d45b033c79965540fe025512c0ea130a14b3a41`. That local history is not a full
upstream checkout and must not replace upstream tree or ancestry during publication.
Apply only the two verified file deltas and this additive evidence to the complete
receiving tree.
