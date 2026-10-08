# Retained frame errors and buffer lifetime

Reviewer and implementer: `integration-72ac1419`, under Jacob's HAMON execution mandate.

## Concrete receiving failure

Exact predecessor: CaptureSuite PR #35, `65b76c9909f0c28d34c9f44f07d306b924955da8`.
Its framing blob is `40c9d03573a5f6d7c2ab3191a5af44e24ec1783e`, SHA-256
`4bc45fb94866658fe44be9ad0871dc12a9e2b1bfedf88c48fd15e2246f62e08d`.

PR #35 correctly propagates invalid-header FrameError. When an application handles that
error and resets the decoder, however, the traceback keeps decode_frame's local memoryview
alive. That view still exports the decoder bytearray, so reset raises BufferError. Saving
the exception for later diagnostics has the same effect. Direct callers of decode_frame
with a bytearray have the analogous existing lifetime defect after incomplete or invalid input.

```python
try:
    decoder.feed(invalid_complete_header)
except FrameError:
    decoder.reset()  # predecessor raises BufferError here
```

## Native change and verification

Use the temporary memoryview's context manager around the unchanged parse body.
Every exit releases only that new view. The caller's own supplied memoryview remains
usable, returned payload bytes remain owned, error messages and tracebacks remain available,
and PR #35's error propagation and all wire fields/bounds are preserved.

The actual package was imported from an isolated full Git clone, with the real generated
protobuf modules and declared protobuf version family. No initializer or platform import
was stubbed for this qualification. Environment: macOS arm64, Python 3.12.8, pytest 8.4.2,
protobuf 4.25.9, Ruff 0.14.7. Dependencies were installed only in this receiver's new venv.

- Exact predecessor plus the 11 new cases: **9 failed, 18 passed**, exit 1.
- Candidate, same four focused modules: **27 passed, zero failures**, exit 0.
- Strict Ruff on framing and the new test module: passed.
- git diff --check: passed.
- The two retained Google protobuf deprecation warnings are unchanged.
- Candidate framing SHA-256: `3ff7c7284d9907a2ad516c83fab383a4151996da3f2d5a1d27e24d7c7575d92e`.

The 11 new cases cover active exception handlers, saved diagnostic exceptions, direct
bytearray reuse after both incomplete and invalid input, caller-owned view preservation,
and payload ownership. The original 16 framing cases remain in the same run. Full raw
baseline and candidate outputs are adjacent.

```sh
python -m pytest -q \
  tests/protocol/test_framing.py \
  tests/protocol/test_framing_invalid_stream.py \
  tests/protocol/test_framing_stream_transitions.py \
  tests/protocol/test_framing_view_lifetime.py
ruff check libs/python/capture_protocol/capture_protocol/framing.py \
  tests/protocol/test_framing_view_lifetime.py
git diff --check
```

## Scope, authority and remaining receiving

Only decode_frame's temporary-view lifetime, the focused new test module, this evidence,
and the root AGENTS-required progress log are changed. The original source author branch,
C++/CMake Linux receiving #36, modality export #30, control-client/worker transport,
daemon, hardware, generated bindings and installed estate services are untouched.

The root AGENTS.md and protocol design were read before changes. Current HAMON #140
ownership has no overlapping Python framing receiver. Repeated review-registration
comments were rejected by GitHub's secondary content-creation limit; none was represented
as published. Work remained in an isolated successor and its exact failure evidence was
reported to the parent worker. Publishing will use the existing GitHub review process
after the service permits writes; another account or endpoint will not bypass that limit.

PR #35's original Windows run 37744165415 has successful Python and CMake/native-integration
jobs at its original head. Those checks do **not** qualify this new companion. Independent
peer receiving and the supported Windows gates on the companion remain required before
source integration. No Windows named-pipe teardown, actual device capture, deployment or
hardware qualification is claimed by these focused macOS tests.

## Subsequent independent peer receiving

A separate receiver accepted native commit `4359c21f3da93ed863de617331edfc853cf8385d`,
tree `43902c3fc551425acf7c3a2dc8bec177f3f29c61`, with the candidate worktree unchanged.
Its actual focused suite replay passed 27 tests. Its separate exact-predecessor probe
reproduced both active-handler failures, then passed 20 candidate combinations across
bytearrays, caller views, read-only views and contiguous sliced views. These probes overlap
the focused behaviors; their counts are not pooled as independent experiments.

The exact peer decision, raw outputs and JSON are retained under `peer/`. The retained
`peer/receiving.py` adds only the repository-required SPDX comment to the executed script;
AST equality was verified. The manifest records both hashes. Its fixed native root and
commit guard intentionally refer to the exact clean candidate it tested; replay it from
outside a checkout held at that commit. Supported Windows CI for this companion and
GitHub source publication remain pending. No product source changed after peer acceptance.
