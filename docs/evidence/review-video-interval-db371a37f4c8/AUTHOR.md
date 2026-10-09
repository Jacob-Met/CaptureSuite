# CaptureSuite selected-video repeat and review speed

Issue: https://github.com/Jacob-Met/CaptureSuite/issues/103
Actor: estate-db371a37f4c8 / production.
Canonical parent: 3960c0c756cd4e9facbde0d76eaaa3c31ab7c167, true tree d1af33caaf7154e83def1dab035920907d417e8d.
The seven proposed source/test/doc paths are enumerated in SOURCE-FREEZE.json.
The complete repository remains outside this selected native executable closure.

## Result and source boundary

The existing RecordedVideoReview now offers Set A, Set B, Repeat A–B, Clear
interval and four explicit native playback speeds. The new pure helper uses
integer media milliseconds and [A, B); it is never a session clock or scientific
scope. Setting A clears B; valid endpoint edits disable Repeat until re-enabled.
Invalid B preserves previous endpoints and enabled state. Paused seek may stay
outside the interval, and explicit Play enters at A. Playing outside-seek and
reaching B return to A. Clear/disable preserve position and playing state.

An explicit play-intent fence prevents decoder end events from restarting an
operator-paused, collapsed or hidden player. Existing player identity and
generation guards are preserved. Reload, selection, reset and decoder failure
clear interval and rate. The backend-reported rate is labeled; native measured
progression is qualified on this backend, not promised for every codec/platform.
No shared screen, event browser, timeline, raw writer, schema, dependency or
workflow is edited. Product widget/helper remained byte-identical throughout
candidate qualification: e2e02b417b75d590f118608cd63bf0e9b9af94f12170c43776f3643c06ecd4eb /
798a836270de8a586eb3341ebccfc142ed59541822982187b3d14d79f2eecc97.

## Original-first and native author receiving

The author first qualified four actual original Windows Qt groups against 121
canonical source files and nine canonical retained fixture files, all unchanged.
A separate receiver independently admitted the complete runtime, ran seven
original groups and calibrated all four rates before reading candidate code.
Its immutable original contract/semantic fixtures were frozen separately; author
tests were not used as its oracle.

Author model gate: 21 passes (original video helpers plus new interval cases),
zero skips, 3.34s. Source formatting/import corrections and the first lint
failures are retained; final scoped Ruff and the repository license policy's
four-file SPDX check pass. This is not the repository-wide license topology gate.

Native R1: after eight completed pytest cases, Python aborted while opening
the next decoder. The uncompleted repeat case passes in an isolated process
without any source/test change; a new-file-only run reproduces the cross-case
abort. Both exact logs/source hashes remain. Native R2 adds only explicit
test-owned QWidget deferred deletion before the next case, leaving every
assertion/fixture/deadline unchanged. All twelve cases then execute: eleven pass,
one fails because a receiver rewrite used Windows default decoding and corrupted
the expected multiplication sign. The product QLabel correctly held U+00D7.
Native R3 corrects only that one test literal and passes the unfinished speed/reset
case: 0.25× advanced100ms in0.656s and2× advanced1000ms in0.563s. These are observed
samples within the predeclared bounds, not exact rate guarantees. No broad
twelve-case replay or product correction is claimed. All scoped source bytes
remain exact during each individual run.

The combined maintained coverage includes the inherited real MainWindow shortcut
countercontrols, decoded frame/seek behavior, missing and invalid media, package
retirement and selection guards, plus A/B preservation, actual repeated cycles,
B=duration, paused/playing outside seeks, clear/disable, measured speed/reset and
new focused-control Space handling. Independent candidate receiving passes its
seven separate frozen native semantic groups (receipt6578f3abf013824687858c0526eac102628653cedf2688796493c83424face9c);
its distinct packet is delivered alongside this author's custody.

## Native presentation and limitations

Presentation R1 intentionally remains negative: its paused-only script expected
a decoded frame before ever pressing Play; offscreen Qt also displayed missing
font glyphs. The exact failed screenshots/receipt are retained. Presentation R2
uses the canonical #89 receiving route: read-only addApplicationFont for the
existing Windows Segoe UI regular/bold files, and explicit Play/decode/Pause.
No installed font, production theme, graphics protection or source is changed.
The final dark1060×720, compact720×620 and light1060×720 control captures are
readable and geometrically contained. The actual QVideoSink frame is160×120 red
RGBA(255,0,0,255). QWidget captures omit the GPU video surface. No physical
foreground input, hardware capture, onscreen GPU presentation, frame-exact
extraction or camera/checkpoint alignment is claimed.

## Runtime provenance

The known LA7 donor was offline, and bounded MSI donor discovery found only
unsupported Python3.11/noQt environments. These negatives precede the isolated
supported runtime. Root authorized a task-owned CPython3.12.10/Qt6.12 environment.
Official PyPI uv0.12.23 wheel SHAfb8a4117a5224d73abe2204a1e744ae34b544f1b9a0b761576851deaa7215c12
was verified; uv's private managed Python install used --no-registry and no PATH
or registry edits. Exact direct dependency versions were resolved into a
hash-bearing lock, then synced with --require-hashes --only-binary :all:.
Version/import/check commands succeeded. The complete private runtime manifest
pins18,539 regular files/1,171,247,985 bytes; source, caches and bootstrap tooling
are explicitly outside that manifest. Independent receiving rehashed the entire
runtime and loaded-module/DLL paths. The final author audit rechecks that closure.
No dependency binary copy is included in Git custody; complete manifests,
official provenance, lock and commands are retained. The original wheel is kept
natively and excluded from the archive with its exact pin.

## Evidence and custody

The archive retains original selected source/fixtures, candidate source, every
negative/positive driver and receipt, native outputs/images, the original
Windows-decoded diff and separately corrected UTF-8 diff, dependency manifests,
bootstrap/fetch provenance, capacity/process receipts and root static review.
The review-diff corruption did not alter product bytes; native codepoint audit
proves U+00D7 and U+2013. The first start RPC stalled without a receipt. It was
cancelled only at orchestration level; reads found no run directory, started
record or owned native process before one atomic-directory-guarded retry.
No duplicate launch or unobserved process exit is inferred.

Reproducible runtime/cache/download bytes are omitted from the archive, not
deleted. Ordinary subprocess wrappers have their actual returned codes; expired
RDC sessions are described by durable child receipts and later process census,
not invented wrapper exit observations. Source/evidence Git custody is additive
and workflow-safe; no Actions-triggering PR/main write is part of this handoff.
