# Ordinary deep Windows paths in atomic metadata publication

Issue: [CaptureSuite #108](https://github.com/Jacob-Met/CaptureSuite/issues/108). Source base: `3960c0c756cd4e9facbde0d76eaaa3c31ab7c167`.

An ordinary destination can fit below the legacy Windows path limit while its generated same-directory temporary sibling exceeds it. The original writer therefore refused an ordinary 242 UTF-16-unit destination in a 240-unit parent before writing any metadata. A separate 357-unit Unicode destination also failed at temporary creation.

The Windows writer now resolves an ordinary relative or absolute spelling once with `GetFullPathNameW`, then derives both the destination and temporary sibling from that snapshot. It adds the extended drive or UNC representation only when an actual I/O path reaches the legacy boundary. Existing explicit namespace paths retain their spelling. Long components ending in a dot or space are refused instead of silently changing their meaning under extended-path rules. The original public API, POSIX implementation, exclusive temporary creation, write/flush/close checks, replacement flags and cleanup remain unchanged. No registry or application-manifest change is required by this repair.

## Focused native evidence

The independent receiver froze complete payload, target, neighbour and directory expectations before candidate source access. It then ran the same nine cases once against each exact native probe, using a receiving executable whose embedded manifest declares `longPathAware=false`.

| Case | Original writer | Candidate writer |
| --- | --- | --- |
| Short ordinary binary replacement | Exact bytes | Exact bytes |
| 240-unit parent, 242-unit destination | Refused at temporary creation; prior inventory exact | Exact 538-byte publication |
| 357-unit Unicode destination | Refused at temporary creation; prior inventory exact | Exact 538-byte publication |
| Relative dot/slash spelling | Exact bytes | Exact bytes |
| Filename-only empty payload | Exact empty file | Exact empty file |
| Explicit extended drive path | Exact bytes | Exact bytes |
| Deep target held without delete sharing | Refused at temporary creation | Reached replacement refusal; full prior inventory exact; no temporary sibling |
| Missing parent | Refused without side effects | Refused without side effects |
| Deep directory as destination | Refused at temporary creation | Reached replacement refusal; full prior inventory exact; no temporary sibling |

Both receiving Jobs completed with 20 total processes, zero active and zero terminated processes; complete raw streams and actual file inventories were independently read back. The probe is a small test transport that calls the real `atomic_write_bytes`; it is not a new CaptureSuite user command.

Candidate source SHA-256: `2b4c6ccb454584ebf79206706c9aa0da40d183171ba193ed71bf299cd99672f0`.
Candidate executable: 244224 bytes, SHA-256 `06f763f5cfbde25de321f4070e5940e50ce9503bb0c063aa5fc3286ecbe23c6a`.
Frozen independent expectations: `d2a98631a896676d6e44b1dbb5f96bc0533648d9572dd1f0f2f1086ea0435c10`.
Independent original receipt: `e8f94501e13d4ab17decbe0ec8e7dcbbc29c0e20519d4f6fc78f9230234b18f2`.
Independent candidate receipt: `ebda8017a186f093aafb0e12c60591216e94f4e963b31e3597c8d35536f3218d`.
Independent source review: `61ef09775cad0616573a9c43a284affbe7fb7045ba2af68d463eeb0d295b6c70`.
Independent final archive: 427427 bytes, SHA-256 `4e171b14da4c9e97d23389dd4d208c27cfaf63b1fc069a0c019e74ddaa48c34e`.

## Build history and remaining gates

The first original compile failed during manifest-tool setup because the child environment could not find the installed `mt.exe`. Both compiled objects were retained. A corrected, pinned child environment linked those exact objects without recompiling them. That linker parent and the single candidate compiler parent exited zero, but both strict clean-settlement gates remained **false** because owned descendants had not settled at the checkpoint; the owned Jobs were retired and final absence was observed. No descendant identity or precise forced-termination count is inferred. Successful product receiving does not relabel either build gate.

Two maintained Catch cases were appended for ordinary deep publication and held-target cleanup; the complete previous test-file prefix is preserved. These additions were source-reviewed only and have **not** been compiled or run. Full Catch/CTest, daemon/native-six, LA7 hardware, security-alias regressions, UNC/network shares, maximum-length paths, concurrent publication and crash durability were not qualified in this increment. Short device-name handling and long trailing-dot/space refusal received source review, not additional native cases.

The existing LA7/feature-table and atomic-preservation owners retain their scopes. This isolated repair is available for their later native integration; it does not claim that their downstream campaign passed. No GitHub Actions run, PR, default-branch update or merge is part of this handoff.
