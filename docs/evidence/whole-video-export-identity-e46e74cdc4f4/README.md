# Whole-session video artifact identity

Whole-session exports must retain every selected raw video segment, including equal basenames across different sources or streams. The original native CLI witness on commit 3960c0c756cd4e9facbde0d76eaaa3c31ab7c167 mapped sim.left/front/0001.mkv and sim.right/front/0001.mkv to one video/camera/0001.mp4 while marking both successful. The left output decoded to the right source's frames. The raw recordings were unchanged.

## Output mapping

The exporter writes video/<display-stem>--<digest>.mp4. Without FFmpeg it copies the raw MKV to the same base with a .mkv extension.

The display stem is the original filename stem with each non-ASCII-alphanumeric/underscore/hyphen character replaced by one underscore, truncated to 32 characters; an empty result becomes segment. The digest is all 64 lowercase hexadecimal SHA256 digits of the exact package-relative POSIX MKV path encoded as UTF-8, without case or Unicode normalization. The digest, not the display text, carries identity. Neither absolute package ancestors nor stream metadata IDs enter this filename.

Every derived video destination is planned first. A duplicate case-insensitive output identity raises ExportOutputError before any video conversion or fallback copy. Thus a later segment cannot silently replace an earlier segment in the same export, even if allocation unexpectedly returns the same portable destination.

Consumers should follow each export_manifest.json row's mp4 or mkv_copy path. Those existing fields remain absolute; mkv remains the exact package-relative native path. The manifest schema remains capture.export_manifest/1. The existing camera-like source_id hint/default camera remains, but it only examines path components inside the package. There is no new stream_id field or stream.json parser. Literal metadata IDs such as sim.left <literal> and front & camera remain unchanged raw metadata.

This changes legacy flattened video filenames. Output mapping is deterministic across package/destination relocation and independent of enumeration order. MP4 rewrap still uses FFmpeg stream copy. Invalid media keeps the existing ok:false/error row policy; fallback copies remain byte-exact. The existing new-or-empty destination requirement, modality selection, verification policy, package-internal exports exclusion, and radar/IMU/EMG behavior are unchanged. Raw recordings are never rewritten.

## Scoped receiving

Issue 109 reserves only tools/export_session.py's whole-video identity method/helper/imports/output documentation plus this guide and the focused regression test. Selected-clip issue 104 and its separate offer remain under their existing owner; the wizard, Review UI, recording/timing/recovery and every other existing source file are outside this change.

The native author baseline uses the exact canonical review_video fixture through the actual Python 3.12.2 CLI and FFmpeg 9.0.1: 38 checks,32 pass / 6 fail, no execution errors, all 9 fixture files and 1280 canonical source inputs unchanged. The failures are four future identity names, one decoded-media mismatch, and only two distinct destinations for three valid inputs. Independent receiving uses a separately frozen native method and expectations; its evidence is bound additively after acceptance.

The focused test file covers fallback content identity, portable bounded names, case/Unicode distinctions, ancestor independence, duplicate-plan refusal before either writer, and the existing exports exclusion. It does not pretend to create an actual SHA256 collision; it forces duplicate planning explicitly to exercise that defense. Actual FFmpeg content/timing behavior is received by the native CLI methods. No hosted Actions or installed adoption is implied.

## Package relocation boundary (v2)

The exclusion check examines the segment path relative to the selected package. A directory named exports outside that package, or the selected package's own basename exports, must not suppress its recordings. Existing case-sensitive exports components inside the package remain excluded, including prior derived exports and an internal stream/component with that name.

The original and v1 exporter incorrectly tested absolute path components and could silently produce an empty video selection under an external exports directory. V1's accepted identity/media results and sealed evidence remain intact. A separately frozen four-case regression reproduced one passing control and three omission failures on v1 before this bounded v2 change. Independent actual CLI relocation receiving is retained separately. The v2 runtime delta only moves the relative-path calculation before the exclusion and uses relative.parts for that check; no other export modality or policy is changed.
