# CaptureSuite #112 — use, source uptake and recovery

A reviewer can keep a paused decoded frame while selecting another segment or position, then compare the two without losing the first view. [The operator guide](../../operator/RECORDED_FRAME_COMPARISON.md) describes the controls and refusal messages. [Root acceptance](ROOT.md) and [independent receiving](independent/INDEPENDENT.md) define the qualified scope.

## Using an owner-admitted source

1. Open a finalized recording in the existing Review screen and expand **Recorded video**.
2. Select a segment, press **Play**, then **Pause** after a decoded picture is available.
3. Open **Compare two frames…** and press **Keep frame A**.
4. Use the original video controls to select another segment or seek, then play/pause as needed. Press **Keep frame B**.
5. Compare both images and their literal source, stream and package-relative path labels. Keeping again replaces only that slot; **Clear A** and **Clear B** are independent.

The nonmodal panel leaves the original video controls reachable. Keep requires a valid current decoded frame and a paused player. It never plays, pauses, seeks or changes speed, repeat or the other slot. A visible refusal preserves the previous pair. After a seek, wait for the intended picture before keeping it: the **decoded frame PTS** in microseconds and **player position when kept** in milliseconds are separate observations. This is not frame-exact extraction or synchronization.

Each slot admits at most 16,777,216 decoded pixels and 64 MiB of converted ARGB32 storage. This is a retained-image bound, not a process-memory bound. Images retain aspect ratio and Qt presentation rotation/mirroring.

Closing or escaping the panel hides it while retaining the pair. Reopening, hiding/collapsing Review, selecting/reloading a segment or a failed media selection within the same package retain both slots. Loading/resetting a package, failed package admission or destruction clears them. There is no saved comparison, autosave or frame export.

## Exact delivery

| Item | Identity |
|---|---|
| Accepted dependency | #103 commit `9befdad4b8a6a5c420001ec9d77378115973ee53` |
| Qualified source | `f2c0b955f659d8a3bd8ab4b169ace0d60183a911` / tree `502613f5b7cac1d696950cb1060cef2733ed456c` |
| Source overlay | [author/source-overlay.zip](author/source-overlay.zip), 93,854 bytes |
| Overlay SHA256 | `0ed668911f4201cba3c08a73f8b3760b68d8028f7892b18b43d09cd76bc532ed` |
| Author packet | [author/author-receiving.tar.gz](author/author-receiving.tar.gz), 2,386,236 bytes / 660 members |
| Independent packet | [independent/independent-receiving.tar.gz](independent/independent-receiving.tar.gz), 2,788,705 bytes / 469 members |

The overlay contains exactly 15 members: nine `current/` source/test/document files, four exact `previous/` files, `SOURCE-MAP.json` and `READ-ME.txt`. It is a source/recovery package, not an installer or a frozen executable. Its historical author-only qualification label remains as shipped; the final receiving result is recorded separately here.

T68's retained integration owner must read the actual target before uptake. Verify `SOURCE-MAP.json` and preserve that target's unrelated files and newer documentation. Where it has advanced, apply the six additive widget spans and documentation additions against the admitted target, rather than replacing the combined checkout wholesale. The three runtime paths comprise two new helper/panel modules and the modified viewer; the unchanged interval helper and accepted #103 behavior remain dependencies. The new model/UI tests and operator guide are maintained source, not an automatic integration action.

Recovery is also conditional on the actual destination: restore the four `previous/` files only where the destination still matches the exact corresponding candidate hashes. Remove the five added files only when they remain byte-exact. If an owner has made newer changes, preserve them and review the inverse additions. Keep the admitted prior artifact and native dependency route available. The overlay itself performs no installation, playback, recording writes or Git operation.

## Practical limits and publication

Native qualification used Windows CPython 3.12.10 / Qt 6.12.0 and synthetic MKV recordings. It establishes current-frame retention and the stated Review consumer; it does not establish every codec, camera, scientific measurement, installed MainWindow or T68 target adoption.

Measured Review windows were 900×808 and 1280×808; the 900×700 request expanded to 808 pixels high. Comparison panels were 840×540 and 1000×640 with readable retained images and labels. QWidget captures omit the original GPU video plane; they show the comparison panel's actual retained QImages.

The current workflow gate permits only a separately verified event-inert receiving branch under root authority. PRs, main/master pushes, v* tags and dispatch remain held by the no-Actions direction. No ref, installed release or target replacement is performed by this source/evidence composition. Hosted checks are unexecuted, not passing CI.
