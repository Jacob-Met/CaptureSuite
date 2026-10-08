# Future-schema registry receiving

This receives [original PR #23](https://github.com/Jacob-Met/CaptureSuite/pull/23)
under source identity `estate-234cae4aee53`. The original contribution implements
the production behavior; the receiver composes it with current source and adds
real SQLite compatibility checks. No operator registry, application state or
device is used.

## Source custody

- Tested main parent: `c43b2819b149e1e87d7f957d8b3583881c29ffb4`.
- Original Shinogi donor: `c5854a8c5b8a33da8d9f20dd5970f6c14ad597f6`.
- Exact donor implementation blob: `c1d7799e1d2099424221b2f4af216a43a972c67a`.
- Exact donor regression blob: `3972c736dbbf03574195594a26cf94c8238bcf74`.
- Both donor files remain byte-identical. Their original progress entry is retained.
- The added `tests/protocol/test_registry_readonly_receiving.py` uses native SQLite,
  real temporary databases, public application readers and ordinary SQL statements.
- The shared progress log preserves all current entries. No framing, storage,
  camera, export or dependency source is changed by this contribution.

## Qualification

| Run | Result |
| --- | --- |
| Current main plus four independent receiving cases and four inherited tests | 3 failed, 5 passed |
| Original donor composed with current main and independent receiving | 9 passed |
| Ruff for the three Python files | Passed |
| Whitespace check for the changed Python source | Passed |

The original baseline fails because direct SQL deletes still succeed through the
connection advertised as read-only. Both ordinary and URI-sensitive filenames
fail, as does a registry whose newer version and preset are in a committed live
WAL. The existing empty-database migration remains a passing control. Retained
raw logs and JUnit XML record the actual executions. The new receiving source was
automatically formatted between runs; no test behavior changed. The accepted
source hashes are in `receipt.json`.

The successful cases also preserve public session/preset reads and existing write
guards. DELETE-journal fixtures retain all original file names and bytes; the WAL
case retains main-database and WAL bytes while a writer connection remains open.
It deliberately does not claim that SQLite shared-memory lock metadata is immutable.

## Replay

An independent source/contract review also accepted this receiver. Its original
execution source is retained verbatim as `peer-script.txt`, with actual results in
`peer-result.json`. Real SQLite controls preserve supported-registry WAL, foreign-key
and synchronous settings plus persisted public reads; query-like filename data
cannot change URI options. A deterministic connection-boundary injection commits
a newer version between the initial read-only probe and writable reopen, exercising
the existing second version guard with connection modes `ro`, `rw`, `ro`. This
is a real-database boundary control, not a cross-process race or lock guarantee.
The peer's query-like filename includes characters invalid on Windows; its script
is retained Linux receiving evidence, while the maintained pytest cases use
portable filenames and run in repository CI.

Use the project's Python 3.12 environment with its declared dependencies:

```bash
PYTHONDONTWRITEBYTECODE=1 python -m pytest \
  tests/protocol/test_settings_registry.py \
  tests/protocol/test_registry_readonly_receiving.py \
  -q -ra -p no:cacheprovider
ruff check libs/python/capture_session/capture_session/registry.py \
  tests/protocol/test_settings_registry.py \
  tests/protocol/test_registry_readonly_receiving.py
```

`tests/conftest.py` routes imports to this checkout and isolates application state.
The baseline is main `c43b281` with the new receiving file; the candidate additionally
contains the two unchanged original donor files. Current-head Windows repository
CI and the guarded merge are subsequent integration gates. This packet is not an
installed-application or hardware acceptance claim.
