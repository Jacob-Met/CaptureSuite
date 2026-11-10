# SPDX-License-Identifier: GPL-3.0-only
"""Optional streaming inspection of recorded MCAP payloads.

Structural MCAP inspection is not a measure of sensor accuracy. Only the
supported NumericBatch schema has decoded sample-value verification here.
"""

from __future__ import annotations

import math
from typing import Any

from capture_analysis.types import StreamRef

_NUMERIC_SCHEMAS = {"capture.v1.data.NumericBatch", "generic.numeric_batch/1"}


def inspect_stream_payloads(ref: StreamRef) -> dict[str, Any]:
    """Inspect actual segment bytes; report a bounded failure instead of hiding it.

    The segment reader streams messages rather than accumulating a session.
    A numeric frame count is only published after every matching batch passes.
    """
    result: dict[str, Any] = {
        "status": "not_applicable" if not ref.mcap_paths else "failed",
        "segmentsChecked": 0,
        "messagesChecked": 0,
        "sampleFramesChecked": None,
        "detail": "No data MCAP segments to inspect",
    }
    if not ref.mcap_paths:
        return result

    numeric = ref.data_schema_id == "generic.numeric_batch/1"
    frames = 0
    matched = 0
    layout: list[str] | None = None
    try:
        from mcap.reader import make_reader

        if numeric:
            # Exactly the existing analysis decoder, not a parallel wire format.
            from capture_analysis.loaders.numeric_batch import _decode

        for path in ref.mcap_paths:
            per_segment = 0
            with path.open("rb") as fh:
                reader = make_reader(fh, validate_crcs=True)
                for schema, _channel, message in reader.iter_messages():
                    per_segment += 1
                    result["messagesChecked"] += 1
                    if not numeric:
                        continue
                    if schema is None or schema.name not in _NUMERIC_SCHEMAS:
                        continue
                    matched += 1
                    channels, names, samples, device_times = _decode(message.data)
                    if not samples:
                        if device_times:
                            raise ValueError("numeric timestamps without sample frames")
                        continue
                    if channels < 1 or len(samples) % channels:
                        raise ValueError("numeric samples must contain whole channel frames")
                    n = len(samples) // channels
                    names = names or [f"ch{i}" for i in range(channels)]
                    if len(names) != channels or len(set(names)) != channels or not all(names):
                        raise ValueError("numeric channel names must match unique channels")
                    if layout is None:
                        layout = names
                    elif layout != names:
                        raise ValueError("numeric channel layout changes between batches")
                    if device_times and len(device_times) != n:
                        raise ValueError("numeric timestamps must match the frame count")
                    if any(b < a for a, b in zip(device_times, device_times[1:], strict=False)):
                        raise ValueError("numeric timestamps move backward within a batch")
                    if not all(math.isfinite(value) for value in samples):
                        raise ValueError("numeric samples contain NaN or infinity")
                    frames += n
            result["segmentsChecked"] += 1
            if not per_segment:
                raise ValueError(f"{path.name}: MCAP contains no data messages")
        if numeric:
            if matched == 0 or frames == 0:
                raise ValueError("no NumericBatch sample frames found in MCAP segments")
            result.update(
                status="numeric_samples_checked",
                sampleFramesChecked=frames,
                detail="Decoded NumericBatch frame values, channel layout and native time order",
            )
        else:
            result.update(
                status="mcap_messages_checked",
                detail="MCAP messages parsed; this schema's sample values were not decoded",
            )
    except Exception as exc:  # noqa: BLE001 - malformed MCAP/codec failures are report data
        result.update(
            status="failed",
            sampleFramesChecked=None,
            detail=f"{type(exc).__name__}: {str(exc)[:220]}",
        )
    return result
