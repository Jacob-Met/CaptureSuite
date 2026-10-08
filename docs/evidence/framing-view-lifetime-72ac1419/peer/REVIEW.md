# Independent CaptureSuite framing companion review

Receiver: integration/capture_peer
Observed: 2026-10-08 08:10:06 UTC
Decision: ACCEPT source and focused native regression coverage. No blocking correctness or coverage defect found for the temporary-view lifetime change.

## Exact receiving target

- Candidate: 4359c21f3da93ed863de617331edfc853cf8385d
- Parent: 65b76c9909f0c28d34c9f44f07d306b924955da8 (PR #35)
- Tree: 43902c3fc551425acf7c3a2dc8bec177f3f29c61
- Native root: /Users/me/Developer/capturesuite-framing-integration-72ac1419
- RDC device: Mac.lan, 5f462f1b-490d-4a0d-8caa-51742c9d09b4
- Runtime: macOS 26.6.2 arm64, Python 3.12.8, protobuf 4.25.9
- Candidate framing SHA-256: 3ff7c7284d9907a2ad516c83fab383a4151996da3f2d5a1d27e24d7c7575d92e
- Predecessor framing SHA-256: 4bc45fb94866658fe44be9ad0871dc12a9e2b1bfedf88c48fd15e2246f62e08d
- Read actual native root AGENTS.md before execution. Native worktree was clean before and after. Candidate, predecessor branch, installed services and other worker files were not modified.

## Review findings

The only parser change is the fresh memoryview context at libs/python/capture_protocol/capture_protocol/framing.py:49. It releases the parser's own buffer export on normal and exceptional exits, including retained FrameError and incomplete ValueError tracebacks. The parsing body remains unchanged; the payload is still copied into owned bytes at line 62. PR #35's separate FrameError propagation at line 78 remains intact.

New tests meaningfully retain the active traceback (tests/protocol/test_framing_view_lifetime.py:21), save errors beyond their handler (line 35), reuse bytearrays after each of the four parser errors (line 60), preserve caller-owned views (line 76), and keep returned payload ownership (line 91). The retained predecessor log's 9 failures are the expected BufferError recovery/ownership failures; it is not a synthetic expected-error substitution.

## Independent execution

1. Ran the four actual focused pytest modules from the native candidate with bytecode and pytest cache writes disabled: 27 passed, 2 unchanged protobuf deprecation warnings; process 98387, exit 0.
2. Independently executed the exact predecessor framing bytes read by git show at 65b76c9 in a separate in-memory module, after importing the real package and dependencies. Both invalid magic and excessive length propagated FrameError, then reset inside the active handler raised BufferError as expected.
3. Independently exercised 20 candidate combinations: bytearray, caller-owned view, read-only view and contiguous sliced view, each with incomplete header, incomplete payload, invalid magic, excessive length and valid input. Exact error types/messages and retained tracebacks survived recovery; caller views stayed usable and continued to prevent resize until explicitly released; the parser retained no extra export afterward; successful payloads remained owned bytes. All 20 passed; process 98061, exit 0.

The standalone peer script is a supplemental receiving probe, not a replacement package or a production patch. Its predecessor module is the exact hashed historical framing source; no package initializer or dependency was stubbed. Full raw tool output and process exit receipts are adjacent.

## Remaining integration gates

This acceptance completes independent peer receiving only. Supported Windows CI for this companion remains pending. It does not assert named-pipe lifecycle, device/hardware, deployment, merge, or production qualification. The original PR #35 Windows checks do not qualify the new companion.

No GitHub write was attempted. The existing secondary-write limit remains respected. Integration owner should preserve this receipt through the existing source/evidence process and append the required session progress entry; this peer kept the candidate immutable.

