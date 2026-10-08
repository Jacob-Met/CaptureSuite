# SPDX-License-Identifier: GPL-3.0-only
"""Read-only event projection from the existing loaded ReviewSummary."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from capture_session.package_reader import ReviewSummary

_INTEGER = re.compile(r"-?[0-9]+\Z")


@dataclass(frozen=True)
class ReviewEvent:
    kind: str
    position: int
    time_ns: int | None
    time_basis: str
    source_id: str | None
    stream_id: str | None
    label: str
    details: str
    search_text: str


def _time(record: dict[str, Any], fields: tuple[str, ...]) -> tuple[int | None, str]:
    for field in fields:
        if field not in record:
            continue
        value = record[field]
        if type(value) is int:
            return value, field
        if isinstance(value, str) and _INTEGER.fullmatch(value):
            try:
                return int(value), field
            except ValueError:
                pass
        # An explicitly malformed preferred field must not acquire another time.
        return None, f"Unavailable: invalid {field}"
    return None, "Unavailable: no recorded timestamp"


def checkpoint_time(record: dict[str, Any]) -> tuple[int | None, str]:
    return _time(record, ("effectiveTimestampNs", "originalTimestampNs"))


def _text(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _event(kind: str, position: int, record: dict[str, Any]) -> ReviewEvent:
    if kind == "Checkpoint":
        time_ns, basis = checkpoint_time(record)
        label = (
            _text(record.get("name")) or _text(record.get("checkpointId")) or "Unnamed checkpoint"
        )
    elif kind == "Annotation":
        time_ns, basis = _time(record, ("timestampNs",))
        label = _text(record.get("text")) or _text(record.get("category")) or "Unnamed annotation"
    else:
        time_ns, basis = _time(record, ("startSessionTimeNs",))
        status = "Closed" if record["closed"] else "Open"
        label = f"{status} · {record['cause']}"
    source_id = _text(record.get("sourceId"))
    stream_id = _text(record.get("streamId"))
    body = json.dumps(record, ensure_ascii=False, indent=2)
    origin = "Gap summary from package reader" if kind == "Gap" else "Loaded record"
    displayed_time = f"{time_ns} ns ({basis})" if time_ns is not None else basis
    details = (
        f"{kind}\nSession time: {displayed_time}\n"
        f"Source: {source_id if source_id is not None else 'No usable source ID'}\n"
        f"Stream: {stream_id if stream_id is not None else 'No usable stream ID'}\n\n"
        f"{origin}:\n{body}"
    )
    return ReviewEvent(
        kind, position, time_ns, basis, source_id, stream_id, label, details,
        f"{kind}\n{details}".casefold(),
    )


def events_from_summary(summary: ReviewSummary) -> tuple[ReviewEvent, ...]:
    """Keep loaded records distinct; never infer missing events or interval coverage."""
    events: list[ReviewEvent] = []
    for gap in summary.gaps:
        events.append(_event("Gap", len(events), {
            "sourceId": gap.source_id,
            "streamId": gap.stream_id,
            "cause": gap.cause,
            "startSessionTimeNs": gap.start_session_time_ns,
            "endSessionTimeNs": gap.end_session_time_ns,
            "closed": gap.closed,
            "estimatedLostCount": gap.estimated_lost_count,
        }))
    for kind, records in (("Checkpoint", summary.checkpoints), ("Annotation", summary.annotations)):
        for record in records:
            events.append(_event(kind, len(events), record))
    return tuple(sorted(
        events,
        key=lambda event: (
            event.time_ns is None,
            event.time_ns if event.time_ns is not None else 0,
            event.position,
        ),
    ))


def filter_events(
    events: tuple[ReviewEvent, ...],
    *,
    kind: str | None = None,
    source_id: str | None = None,
    query: str = "",
) -> tuple[ReviewEvent, ...]:
    """None means all sources; the empty filter selects no usable source ID."""
    needle = query.casefold()
    return tuple(
        event for event in events
        if (kind is None or event.kind == kind)
        and (source_id is None or (event.source_id or "") == source_id)
        and needle in event.search_text
    )
