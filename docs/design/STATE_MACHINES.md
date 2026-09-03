# State Machines

Explicit states, explicit transitions, no implicit behavior. Any transition not listed is illegal.

## Resolving an ambiguity in the source model

[`ARCHITECTURE.md`](../../docs/spec/ARCHITECTURE.md) lists `warning`, `recovering`, `disconnected_during_recording`, `failed`, and `disabled` alongside the lifecycle states. Treating those as peers of `recording` makes the machine ambiguous, because a source can be recording *and* warning at the same time.

Decision: a source has three orthogonal pieces of state.

1. **Lifecycle state** — one of the values below, a strict machine
2. **Health** — `OK`, `WARNING`, or `ERROR`, independent of lifecycle
3. **Selection** — `selected` or `disabled`, an operator choice, not a device condition

So "disconnected during recording" is lifecycle `RECORDING` with health `ERROR` and an open gap. This matters because it is what allows a source to keep its place in the session while unhealthy, rather than falling out of the machine.

## Session state machine

| State | Meaning |
|---|---|
| `IDLE` | no session open |
| `PREPARING` | session package created, storage validated |
| `ARMING` | arm requests issued, awaiting readiness |
| `RECORDING` | T0 established, data flowing |
| `STOPPING` | stop issued, writers draining |
| `FINALIZED` | integrity manifest written, package closed |
| `RECOVERING` | opened an unfinalized package, repair in progress |
| `FAILED` | unrecoverable daemon-level fault |

### Transitions

| From | Event | To | Guard / effect |
|---|---|---|---|
| `IDLE` | `CreateSession` | `PREPARING` | package created, manifest written with `state=preparing` |
| `IDLE` | `OpenSession` (finalized) | `IDLE` | read-only review, no state change |
| `IDLE` | `OpenSession` (unfinalized) | `RECOVERING` | see RECOVERY.md |
| `PREPARING` | `StartSelected` / `StartAllReady` | `ARMING` | at least one selected source is `READY`; disk watchdog satisfied |
| `PREPARING` | `FinalizeSession` | `FINALIZED` | empty session, valid outcome |
| `ARMING` | all armed within 10 s | `RECORDING` | T0 established, `SESSION_STARTED` journaled |
| `ARMING` | timeout with at least one armed | `RECORDING` | unarmed sources marked health `ERROR`, gap opened from T0 |
| `ARMING` | timeout with none armed | `PREPARING` | journal `ARM_FAILED`, nothing recorded |
| `RECORDING` | `Stop` | `STOPPING` | requires confirmation token; the only normal exit from `RECORDING` |
| `RECORDING` | disk reaches hard floor | `RECORDING` | writers blocked, `WRITER_ERROR` gaps opened, session continues; never an automatic stop |
| `STOPPING` | all writers drained | `FINALIZED` | hashes completed, `integrity.json` written |
| `STOPPING` | drain timeout 30 s | `FINALIZED` | journal `PARTIAL_FINALIZE`, mark affected files |
| `RECOVERING` | repair complete | `FINALIZED` | `state=finalized_recovered` |
| `RECOVERING` | repair impossible | `FAILED` | package left intact, report written |
| any | fatal internal error | `FAILED` | flush journal, never delete data |

Illegal transition handling: reject the request with `ErrorInfo{code=INVALID_STATE}`, log at `error`, and leave state unchanged. Never assert or crash on an illegal request from the UI, because the UI is untrusted and may be stale.

### Nothing stops a recording except the operator

`RECORDING` has exactly two exits: an operator `Stop` carrying a valid confirmation token, or a fatal daemon fault that makes continuing impossible. No disk condition, no source failure, no worker crash, and no UI disconnect ends a recording. Every such condition degrades explicitly with alerts and gaps while the session keeps running.

## Source lifecycle state machine

| State | Meaning |
|---|---|
| `UNAVAILABLE` | known from a preset but not present |
| `DISCOVERED` | enumerated, not yet opened |
| `CONNECTED` | handle open, identity read |
| `PAIRING` | vendor pairing workflow in progress |
| `CONFIGURED` | configuration applied successfully |
| `VALIDATED` | self-test and rate check passed |
| `READY` | eligible for arming |
| `ARMED` | prepared to start on command |
| `RECORDING` | producing data into the session |
| `STOPPING` | draining |
| `FINALIZED` | closed for this session |
| `FAILED` | unusable until re-discovered |

### Transitions

| From | Event | To | Notes |
|---|---|---|---|
| `UNAVAILABLE` | `Discover` finds device | `DISCOVERED` | matched by stable hardware key, never by alias |
| `DISCOVERED` | `Connect` | `CONNECTED` | on failure to `FAILED` |
| `CONNECTED` | `Pair` | `PAIRING` | only if pairing advertised |
| `PAIRING` | pairing complete | `CONNECTED` | |
| `CONNECTED` | `ApplyConfig` | `CONFIGURED` | config snapshot stored |
| `CONFIGURED` | `Validate` | `VALIDATED` | rate within tolerance, identity matches preset |
| `VALIDATED` | daemon marks ready | `READY` | |
| `READY` | `Arm` | `ARMED` | sources without arming go `READY` to `RECORDING` directly |
| `ARMED` | `Start` | `RECORDING` | first datum recorded with offset from T0 |
| `RECORDING` | `Stop` | `STOPPING` | |
| `STOPPING` | writer drained | `FINALIZED` | |
| `RECORDING` | worker dead or device lost | `RECORDING` | health `ERROR`, open `DISCONNECT` gap, stay in lifecycle |
| `RECORDING` | reconnected | `RECORDING` | close gap, new segment, health back to `OK` |
| any | unrecoverable device error | `FAILED` | other sources unaffected |
| any | operator disables | unchanged | selection flag only, forbidden while `RECORDING` |

The two `RECORDING` to `RECORDING` rows are the heart of failure isolation: a disconnect changes health and creates a gap but does not remove the source from the session.

## Health rules

| Health | Set when | Cleared when |
|---|---|---|
| `OK` | measured rate within 5 percent of nominal, no open gap, writes succeeding | — |
| `WARNING` | rate deviation over 5 percent, drops in the last 10 s, or preflight override active | condition absent for 10 s |
| `ERROR` | disconnected, open gap, writer failing, or `FAILED` lifecycle | reconnect or successful write resumes |

Health transitions are events (`HealthSnapshot`), emitted at 1 Hz and immediately on change.

## Worker restart policy

On worker death during recording:

1. Journal the exact session time of last received datum
2. Open a `DISCONNECT` gap
3. Attempt restart up to 3 times with 1 s, 2 s, 4 s backoff
4. On successful restart, re-apply the stored configuration snapshot, then resume into a new segment
5. After 3 failures, set lifecycle `FAILED`, leave the gap open until session stop, and continue the session

Restart is never attempted while the session is `STOPPING` or `FINALIZED`.
