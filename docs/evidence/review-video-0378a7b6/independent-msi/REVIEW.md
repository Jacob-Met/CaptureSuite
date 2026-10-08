# Independent source and native behavior acceptance

Reviewer: chatgpt-0378a7b6b7c2/msi_product. Review completed 2026-10-08, with actual native oracle exit 0 at 19:49:15.516Z.

No blocking source finding in the recorded-video contribution at these exact SHA256 pins:
- desktop/capture_desktop/review_video.py: f8116601de2b920140d430d59460e07b7f80167d8151fb90f80534eda7f181d5
- desktop/capture_desktop/widgets_review_video.py: 3d89f1f8453a3d18d2776574941a2c6197f3be59e8df3a7a278f3b5c400134d9
- desktop/capture_desktop/screen_review.py: 8ee038aaca15d6f96ae3df8b4894466f404b6da8a0016179f70f267077f3ff36

Source reviewed on parent a2c89957c2cfe6fd5347d4ac317982449d3baa3a before its author committed the contribution. Read the complete three production files, exact existing-screen diff, unchanged discovery producer, all new model/UI tests, repository instructions and author's presentation driver.

The lifecycle is coherent: retirement increments the generation and clears the active player before stop, detach and source clearing can emit signals. Every installed callback closes over both player identity and generation. Replaced native video widgets are hidden and removed immediately, then deleted later. Current errors retire the output and clock while leaving an explicit selection/reload route; old errors cannot take it over. Invalid package admission begins by resetting video state. Selection checks a currently existing regular file within the resolved package boundary. Source, stream and relative path remain explicit literal identities.

There is no playback call during package load or selection. Play is enabled only for a loaded video track; no audio output is attached. Collapse/hide pauses without a matching implicit resume. Position and seek use only the selected native media player's milliseconds and duration. No checkpoint, session alignment, interpolation, concatenation, or synchronized-camera claim is introduced.

The distinct independent oracle used the existing CPython 3.12.10 / PySide6 6.12.0 environment and Qt offscreen platform. It copied the retained synthetic fixture into its own runtime directory, changed state to finalized_recovered, and set a checkpoint timestamp to 9,876,543,210,000,000 ns. Six groups passed:
1. Recovered package inventory stays idle until explicit selection.
2. Rapid A-to-B-to-A selection with no intervening event pump, fourteen signals emitted on two actual retired QMediaPlayers, and separately deferred stale callbacks leave only the current selection; no autoplay.
3. Player identity and generation reject stale callbacks independently, including a trap object proving the wrong identity is rejected before player reads.
4. Slider value 3333 maps to 666 of 2000 segment-local milliseconds despite the unrelated large session timestamp, without playing.
5. A current-player error retires media/clock and disables playback; explicit reload creates a new stopped player at zero.
6. A failed package switch retires old identity/controls and rejects its stale callbacks.

All three source pins were exact before and after. The original fixture and changed-input package were byte-preserved during the oracle. No production edits, installs, full-suite duplication or API calls occurred.

The first oracle failed before these playback groups on an extra recovered-banner assumption. Existing ReviewScreen renders that banner from its recovered=True argument or recovery reports, rather than manifest state alone. The original driver, receipt and log are retained. Version 2 passes the existing recovered=True argument and changes only that receiver call plus output/runtime isolation paths; the production source did not change. This is a receiver correction, not a new product fix.

Acceptance is bounded to source semantics and the native control/decoder state exercised here. Actual retired-player signal emission and deferred callbacks are explicit test stimuli; this is not exhaustive validation of all backend thread race timings. The author separately observed decoded red/blue pixels through QVideoSink. Offscreen QWidget grabs omit QVideoWidget's GPU surface, and the author's native HWND grab was black. This review does not convert those failed presentation attempts into onscreen-video acceptance. No custom renderer, physical hardware, session synchronization, mobile or performance qualification is claimed.

Files: review_native.py, receipt.json, run.log, run-result.json retain the initial failure; review_native_v2.py, receipt-v2.json, run-v2.log, run-v2-result.json retain the passing oracle. manifest.json seals these exact artifacts plus this review. The author's normal full gates and integration remain their responsibility.
