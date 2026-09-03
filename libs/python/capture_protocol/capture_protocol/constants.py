# SPDX-License-Identifier: Apache-2.0
"""Wire-level constants from docs/design/PROTOCOL.md."""

from __future__ import annotations

# Frame magic ASCII "CSP1" little-endian uint32 = 0x31505343
FRAME_MAGIC = 0x31505343
FRAME_MAGIC_BYTES = b"CSP1"
FRAME_HEADER_SIZE = 16
MAX_PAYLOAD_LEN = 8 * 1024 * 1024  # 8 MiB

PROTOCOL_MAJOR = 1
PROTOCOL_MINOR = 5

# WorkerOperation bitmasks (match WorkerOperation enum values)
OP_PAIR = 1
OP_CALIBRATE = 2
OP_ARM = 4
OP_RECOVER = 8
OP_PREVIEW = 16
