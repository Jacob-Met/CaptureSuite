# SPDX-License-Identifier: GPL-3.0-only
"""Quick recorded-file inventory for the existing session export dialog.

Read MCAP summaries, not payloads. Missing summaries leave choices available;
an uninspected recording must never be presented as an absent modality.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

KINDS = ("radar", "video", "emg", "imu", "numeric")


@dataclass
class ExportKind:
    streams: set[tuple[str, str, str]] = field(default_factory=set)
    sources: set[str] = field(default_factory=set)
    files: set[str] = field(default_factory=set)
    messages: int = 0


@dataclass
class ExportInventory:
    kinds: dict[str, ExportKind] = field(
        default_factory=lambda: {kind: ExportKind() for kind in KINDS}
    )
    incomplete: list[str] = field(default_factory=list)


def _kind(schema: str) -> str | None:
    if schema in {"capture.v1.data.NumericBatch", "generic.numeric_batch/1"}:
        return "numeric"
    # Match the maintained session exporter's accepted schema families.
    if schema == "capture.v1.data.EmgBatch" or "emg.batch" in schema:
        return "emg"
    if schema == "capture.v1.data.ImuFrame" or "imu.frame" in schema:
        return "imu"
    if "radar" in schema.lower():
        return "radar"
    return None


def inspect_export_inventory(package: str | Path) -> ExportInventory:
    root = Path(package)
    result = ExportInventory()
    source_root = root / "sources"
    if not source_root.is_dir():
        result.incomplete.append("Recording source folders are unavailable.")
        return result
    try:
        from mcap.reader import make_reader
    except ImportError:
        make_reader = None
    for source in sorted(p for p in source_root.iterdir() if p.is_dir()):
        for video in sorted(source.rglob("*.mkv")):
            entry = result.kinds["video"]
            entry.streams.add((source.name, video.parent.as_posix(), "video"))
            entry.sources.add(source.name)
            entry.files.add(video.relative_to(root).as_posix())
        for path in sorted(source.rglob("*.mcap")):
            if path.name.endswith(".timing.mcap"):
                continue
            relative = path.relative_to(root).as_posix()
            if make_reader is None:
                result.incomplete.append(relative + ": MCAP reader unavailable.")
                continue
            try:
                with path.open("rb") as stream:
                    summary = make_reader(stream).get_summary()
                if summary is None or summary.statistics is None:
                    result.incomplete.append(relative + ": recorded index unavailable.")
                    continue
                for channel_id, channel in summary.channels.items():
                    count = summary.statistics.channel_message_counts.get(channel_id, 0)
                    if count == 0:
                        continue
                    schema = summary.schemas.get(channel.schema_id)
                    kind = _kind(schema.name) if schema else None
                    if kind is None:
                        result.incomplete.append(relative + ": unclassified recorded channel.")
                        continue
                    entry = result.kinds[kind]
                    entry.sources.add(source.name)
                    entry.streams.add((source.name, path.parent.as_posix(), channel.topic))
                    entry.files.add(relative)
                    entry.messages += count
            except Exception:
                result.incomplete.append(relative + ": recorded index could not be read.")
    return result
