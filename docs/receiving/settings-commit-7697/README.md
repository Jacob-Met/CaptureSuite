# Settings persistence receiving — issue #125

A failed immediate SettingsStore change previously stayed in memory and could
be written by a later unrelated save. The corrected store prepares a candidate,
runs the unchanged atomic writer, and adopts the candidate only after success.
The original error still reaches the caller, who can retry the intended change.

Explicit `save=False` continues to stage settings in memory. A rejected immediate
change preserves earlier staged values, and a failed explicit `save()` keeps the
staged values and schema field available for retry. Successful saves preserve the
existing schema normalization, unknown keys, recent-project order/cap and geometry
siblings.

## Exact source

| Item | Git identity |
| --- | --- |
| Original receiving commit | `3960c0c756cd4e9facbde0d76eaaa3c31ab7c167` |
| Publication parent | `ab17b8c50af9892483b49ce4c125ef28f38eb72c` |
| Original settings source | `41b99cdaa78011d3d9b753c3131f32c72af9699f` |
| Corrected settings source | `acfc63cabf30bc8c6388b38dc1801941f689021d` |
| Maintained regression test | `1bbf02e7cde12ea9ce1bc4977c81770af250ee01` |
| Independent receiver frozen before candidate inspection | `6c2e9e9ea548d417aa75a945e3dd03612490fe8a` |

The publication parent retains every tested package, original test, configuration
and instruction blob. Its unrelated CSV-suffix change and progress/evidence are
preserved. The code search on that parent reports five complete named-use files;
the desktop uses normal SettingsStore instances, with no observed subclass or
override relying on the old private call sequence.

## Receiving

| Course | Original | Corrected |
| --- | --- | --- |
| Independent six-method receiver, Python 3.12.8 / macOS arm64 | 11 assertion failures; 0 errors/skips | 6 methods pass; 0 failures/errors/skips |
| 11 new cases plus 5 unchanged settings/registry cases, Python 3.12.8 / pytest 8.4.2 | 10 fail, 6 pass | 16 pass |
| Same maintained cases, ThinkPad Python 3.14.4 diagnostic | 10 fail, 6 pass | 16 pass |
| Scoped Ruff 0.14.10 with exact repository config | — | 0 diagnostics |
| Original license checker on the declared materialized subset | — | Pass |

The frozen receiver uses the public API and real disposable settings JSON with
injected `os.replace` refusal and genuinely unserializable values. It checks that
a later save cannot carry rejected state, explicit retries work, temporary
siblings are removed, unknown data survives and returned copies stay detached.

[Independent receiving](independent-receiving.json) retains the original and
candidate sources, frozen receiver, runners, native logs/JUnit, source guards
and pinned private dependency receipt. Its exact file SHA-256 is
`8c606d06f01f9dff3298037cbe8bb8d11b7c3a6d10ebd3479476f56ada98a7f0`.
[Scoped Ruff receiving](ruff-receiving.json) retains the two-file lint command,
exact config/tool identity and dependency record.
[Author receiving](author-receiving.json) retains diagnostic failures and passes,
the precise subset license check, caller review and current-parent source checks.

From a supported development checkout, the maintained course is:

```sh
python -m pytest tests/protocol/test_settings_commit.py tests/protocol/test_settings_registry.py
```

## Qualification boundary

These are headless temporary-file persistence results. No desktop instance,
Windows runtime, live settings, registry data, capture daemon or hardware was
exercised. The full-repository Windows gate and complete license scan remain
separate. The atomic file writer is unchanged; no cross-process merge or stronger
power-loss guarantee is introduced.

The source is offered through an isolated branch and
[issue #125](https://github.com/Jacob-Met/CaptureSuite/issues/125), preserving the
Actions hold. No workflow change, PR-triggered run, merge or installed delivery
is represented by this source receiving record.
