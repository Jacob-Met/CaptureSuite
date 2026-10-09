# Source-only diagnosis of the second CaptureSuite observer failure

The exact admitted outer 24bed9f37bd9ec1daf6db579055667691274ff68 ended with FileNotFoundError while enumerating its **new private Chrome profile**, after the functional observations had already written their event/text/image files. Actual outer receipt 11f4e01ec4f1d3c33af757cd6e6f9231c742a76b preserves the complete traceback. Outer PID 81736 exited 1; its Node child 81778 was terminated and reaped with -15.

This document is a source review after complete native closure. It changes no source and proposes no further browser execution. Both failed attempts and all actual artifacts remain immutable.

## Exact failing operation

The frozen Python helper walks the owned tree, tests a pathname for symlink status and then calls `p.stat()`. The profile-capacity monitor calls this helper every 0.1 seconds while Chrome is active. At the recorded failure, the path was:

`browser/profile/Default/.com.google.Chrome.TransportSecurity.naJaws`

The native traceback establishes that this pathname no longer existed at `p.stat()`. A live profile is mutable: enumerating a directory does not guarantee that every listed temporary pathname remains present for the following stat call. The expected absence of a transient file was not handled by this outer helper, so it escaped to the strict outer exception handler. That handler deliberately terminated only its owned Node process group and retained the failure.

The report renderer and report HTML were not involved in that filesystem operation. All 15 original nonprofile files, the four new protected inputs and the pinned runtime files later compared exact. There is no evidence of a product-source defect from this error.

## Smallest scoped correction for any future reuse of this helper

The source-level correction would distinguish **volatile profile accounting** from protected static input/evidence inspection:

1. Add a `volatile_profile=False` argument to the size helper.
2. Opt in only at the two known `browser/` roots when combining retained and current profile allocation.
3. Catch only `FileNotFoundError` around a profile entry's stat. Record the disappearing owned relative pathname in a bounded diagnostic list and continue that census. A pathname that has disappeared contributes no extant file allocation at that observation.
4. Continue to raise for static input/evidence disappearance, permissions, unexpected file types, I/O errors, all capacity violations and all other exceptions. Do not change either floor, cap, deadline, ownership fence or final preservation check.

Illustrative local change, **not an executed or newly admitted program**:

```python
try:
    s = p.stat()
except FileNotFoundError:
    if not volatile_profile:
        raise
    # Append the owned relative path to a bounded census diagnostic.
    # Refuse if that diagnostic reaches its declared bound.
    continue
```

The existing Node observer already tolerates ENOENT while measuring its own live profile. The new Python outer's additional monitor lacked that narrow handling; it terminated the otherwise progressing observer first. Removing resource monitoring or making every filesystem error nonfatal would be broader changes and is not proposed.

Any live profile census remains a non-atomic observation. This source diagnosis must not be presented as a complete filesystem snapshot guarantee. The exact static input inventory continues to require byte/mode/mtime preservation.

## Observed useful work and the missing completion evidence

The actual saved KEYBOARD-EVENTS.json daf71f524eee83a1e7e5c84fa984c46f1010fbad records trusted Enter keydown, carriage-return keypress and keyup, with native disclosure state false before activation and true afterward. Both requested new screenshots were produced and visually inspected; FINAL-DOM.json a4fbc718f121fb45b712d2cef790eca463bc66b1 preserves all eight complete exact JSON text strings and the final #gaps URL.

The termination occurred before the Node observer wrote its final MAC-RECEIPT.json, IDENTITY-AFTER.json and Chrome stdout/stderr files. Those four files are explicitly absent. The page event arrays and direct Chrome exit receipt had existed only in process memory; they are not reconstructed. No final all-group pass, final zero-exception/network/log claim or direct Chrome exit code is inferred from the successful saved functional observations.

Read-only collector 84011 later exited 0 and measured an empty selected owned PID/group snapshot, stable original and new files and exact runtime identities. That is separate postkill closure evidence, not a replacement for the missing normal Node/Chrome completion receipt.

Root has expressly declined another browser replay of the already observed Enter, Sync, Gaps and images. Preserve this source-only diagnosis with the incomplete continuation and publish the useful product evidence with that honest qualification boundary.
