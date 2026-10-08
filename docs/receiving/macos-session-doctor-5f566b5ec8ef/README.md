# Canonical Mac session-doctor receiver

A native arm64 receiver for the current merged CaptureSuite portable `session_doctor` is available on the Mac. This contribution preserves the actual build, executable, dependency closure, source correspondence and recipient instructions. It changes no CaptureSuite product implementation, preset or bootstrap.

## Received artifact

| Item | Exact value |
| --- | --- |
| Canonical compiled source | `d43bdea867d6198a707a5f55e29216c76054517e` |
| Native immutable source snapshot | `6a1a32e6240dc89892f340f241b03ef25a8ac8fc` |
| Receiving documentation base | `70f34e3b982523b544a9370d2316a1b69d79bd70` |
| Final archive SHA-256 | `5139f00888a798e695b95d17420ddc649196d09faa6896d0c87e81d4643ba20f` |
| Final archive size | 2,393,685 bytes |
| Received executable SHA-256 | `401f7ef7eb1212799c00ff7bdb22ac48a31bf6feb22a17b3a4fefcfc8e485772` |
| Final payload | 246 exact files; 87 Mach-O runtime files |

Native custody root: `/Users/me/capturesuite-macos-session-doctor-20261008-5f566b5ec8ef`. The final archive is `distribution/CaptureSuite-Session-Doctor-d43bdea-macos-arm64-source-notices.tar.gz`; the immediately usable directory is `receiver-final/CaptureSuite-Session-Doctor-d43bdea-macos-arm64`.

Read [the packaged user guide](package-README.md), [build correspondence](BUILD.md), and [notices](NOTICE.md). Invocation uses the explicit `bin/session_doctor` path and an explicitly chosen session copy. The runtime and local dynamic libraries travel together. The package does not change an existing executable or service.

## Qualification and evidence

The original Release build used macOS 26.6.2 arm64, AppleClang 21.0.0, CMake 4.2.3 and Ninja 1.13.2, with camera and radar workers disabled through existing CMake options. The 96 exact source/build/schema/fixture inputs were admitted by canonical Git blob, size and mode. Configure, build and all 17 available CTest cases passed. The Linux GNU linker-wrapped failure cases were unavailable on this Mac; they are not counted as native passes. See [native qualification](evidence/native-qualification-first.json) and its raw CTest/build logs.

A relocated copy under a path containing spaces and Unicode ran from an unrelated directory with system-only `PATH`. Actual dyld tracing found all 87 non-system images inside that copy. Real CLI controls covered no arguments, missing session, malformed JSON, exact finalized-fixture preservation, an authored unsealed tail, sealed-file preservation, a pre-existing temporary symlink, and repeated-call byte preservation.

The [first process receipt](evidence/receiver-process-first.json) passed seven cases and retained a harness failure in the final case: the helper assumed the wrong BLAKE3 filename and stopped before moving a file or launching the missing-library control. The [focused replay](evidence/receiver-dependency-replay.json) used the unchanged runtime manifest, observed the real loader refusal, restored the exact library, and confirmed successful launch. The earlier source-hydration base64-linebreak refusal and unresolved `@rpath` assembly admission are also retained with their corrected helpers. None required product-source changes.

[Independent package review](evidence/coordination-review.json) rehashed all 87 original and copied files, read actual arm64 load commands, and resolved all 1,245 non-system references within the package. It did not repeat the build or recovery runs.

The first 241-file archive was extracted and launched successfully. Before publication, the package was completed with the canonical project's licensing split and separate schema notices. That earlier archive remains exact. The [final archive receipt](evidence/archive-receiving-final.json) verifies all 246 extracted file bytes and modes, then launches the actual extracted `--help` process from an unrelated directory. Only five notice/manifest files were added and three metadata files changed; the 96 compiled inputs and all 87 runtime files remained exact.

## Existing ownership and capability boundary

This is a distinct receiver of already-merged portable code. The older Mac port under `/Users/Shared/hamon-cs22503` has a separate, substantially different recovery implementation and retained unknown-outcome goals. It was not adopted, cleaned, trusted globally, or executed. [Final historical custody](evidence/historical-receiver-custody.json) confirms the six initially pinned source/build/executable files remain byte-identical. The Linux R3 receiver and current analysis/desktop/worker work also retain their existing ownership.

The evidence covers this local arm64 receiver and the stated synthetic/portable boundaries. It does not claim a complete Mac port, Windows or hardware qualification, arbitrary recording repair, x86_64 support, notarization, crash-atomic package construction, or deployment of a new estate default.

## Source publication

The receiving base above preserves all 96 qualified canonical inputs exactly; the newer main changes are outside this portable target. This packet is additive under its own directory, with the required append to `docs/design/research/PROGRESS.md`. The source archive and executable remain in native custody; no public binary release is created.

Published Python evidence helpers add a GPL-3.0-only SPDX comment where needed. Their original executed versions remain in native custody and the qualified package. [Header correspondence](evidence/helper-header-correspondence.json) pins both byte versions and confirms identical parsed Python syntax trees. No behavioral qualification is attributed to this comment-only adjustment.
