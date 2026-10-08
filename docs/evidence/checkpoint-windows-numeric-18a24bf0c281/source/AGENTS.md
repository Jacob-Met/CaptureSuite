# CaptureSuite — Agent Instructions

Read before architectural or schema changes:

1. [`docs/spec/`](docs/spec/) — product specification
2. [`docs/design/`](docs/design/) — implementation decisions (source of truth for M1–M4)

Start with [`docs/design/README.md`](docs/design/README.md), which also lists what is deliberately left unspecified and why.

Milestone 5 onward already has pinned decisions in `WORKER_HOST.md`, `VIDEO_PIPELINE.md`, `PREVIEW_TRANSPORT.md`, `CONFIGURATION_UI.md`, `SETTINGS_REGISTRY.md`, and `PLUGIN_REGISTRY.md`. Follow them rather than re-deciding; change them only with a stated reason recorded in the document.

**Adding hardware / modalities:** use [docs/prompts/](docs/prompts/) (copy-paste agent prompts), `.cursor/rules/add-acquisition-plugin.mdc`, and `tools/new_plugin.ps1`. Prefer plugins over daemon core edits.

## Core rules

- Do not hard-code the app around one camera or one EMG source.
- Do not route raw capture through the GUI process.
- Do not make preview reliability equivalent to capture reliability.
- Do not overwrite raw data with processed data.
- Do not bake analysis overlays into the only retained camera file; keep raw/sealed source video and put overlays under `processing/…`.
- Do not resample raw streams during acquisition.
- Do not discard native device timestamps.
- Do not use aliases as hardware identity.
- Do not silently hide source gaps or dropped data.
- Do not make checkpoint naming delay checkpoint timestamp capture.
- Do not create vendor-specific logic in core session/storage code — extend via `plugins/*/plugin.json` instead ([docs/design/PLUGIN_REGISTRY.md](docs/design/PLUGIN_REGISTRY.md)).
- Do not assume multi-radar hardware sync until validated on real boards.
- Preserve forward compatibility; version every on-disk and IPC schema.
- A recording session stops only on operator Stop (or fatal daemon fault).

## Autonomy

Between milestones, run the builds and tests yourself and fix failures without waiting for the operator. Prefer a tight loop: change → build → test → fix. **Develop on sim, fixtures, and replay data** — physical hardware validation comes last and never blocks feature work. Only stop for operator input on genuinely product-level forks (not missing bench hardware).

**Autonomous execution playbook:** [`docs/design/research/AUTONOMOUS_EXECUTION_PLAN.md`](docs/design/research/AUTONOMOUS_EXECUTION_PLAN.md) — simulation-first development, industry-quality bar (machine + presentation + operator UX), phases, debug playbooks. Update [`docs/design/research/PROGRESS.md`](docs/design/research/PROGRESS.md) each session.

**Full-stack research (2026-09):** [`docs/design/research/README.md`](docs/design/research/README.md) → [`IMPLEMENTATION_ROADMAP_FROM_RESEARCH.md`](docs/design/research/IMPLEMENTATION_ROADMAP_FROM_RESEARCH.md).

## Implementation order

1. schemas → 2. protocol → 3. simulator → 4. daemon → 5. storage/recovery → 6. UI → 7. real backends

## Milestone 1 exit

A simulated worker can advertise arbitrary source/stream types over the versioned handshake.

## Milestone 2 exit

Arbitrary simulated modalities record together via the C++ daemon (QPC clock, session/source FSMs, named-pipe Hello + control, checkpoints/annotations/sync, fault injection). Storage/MCAP is Milestone 3.

## Milestone 3 exit

Killing the UI or daemon does not destroy previously sealed segment data; incomplete packages recover via `session_doctor` / `OpenSession` to `finalized_recovered` with explicit gaps.

## Milestone 4 exit

PySide6 UI drives the daemon over named pipes: source rail, timeline/focus/grid, live preview (all contract kinds), health, checkpoints with immediate timestamps, protected Stop, preflight, and rehearsal. Real webcams via Media Foundation for preview + timing-only record; other modalities remain simulated at contract rates/sizes until their hardware milestones.
