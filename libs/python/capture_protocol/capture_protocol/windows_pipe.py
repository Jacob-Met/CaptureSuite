# SPDX-License-Identifier: Apache-2.0
"""Windows named-pipe adapter, loaded only by a live capture connection."""

from __future__ import annotations

import ctypes
import msvcrt
from ctypes import wintypes

_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_kernel32.PeekNamedPipe.argtypes = [
    wintypes.HANDLE,
    wintypes.LPVOID,
    wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD),
    ctypes.POINTER(wintypes.DWORD),
    ctypes.POINTER(wintypes.DWORD),
]
_kernel32.PeekNamedPipe.restype = wintypes.BOOL


def peek_available(fd: int) -> int:
    handle = msvcrt.get_osfhandle(fd)
    avail = wintypes.DWORD(0)
    ok = _kernel32.PeekNamedPipe(handle, None, 0, None, ctypes.byref(avail), None)
    if not ok:
        raise OSError(ctypes.get_last_error(), "PeekNamedPipe failed")
    return int(avail.value)
