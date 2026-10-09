# SPDX-License-Identifier: GPL-3.0-only
"""Export one explicitly selected local-media interval without changing its package."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from fractions import Fraction
from pathlib import Path, PurePosixPath

MAX_SOURCE_BYTES = 2 * 1024**3
MAX_FRAMES = 250_000
MAX_PROBE_BYTES = 32 * 1024**2
MAX_SOURCE_SECONDS = 3600
MAX_CLIP_MS = 600_000
PROCESS_TIMEOUT = 180


class VideoClipError(ValueError):
    """An interval could not be admitted or completely exported."""


def _pin(path: Path) -> dict:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
            size += len(block)
    return {"bytes": size, "sha256": digest.hexdigest()}


def _unlinked(path: Path) -> None:
    if path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
        raise VideoClipError(f"Linked input is not admitted: {path}")


def _json(path: Path) -> dict:
    _unlinked(path)
    if not path.is_file() or path.stat().st_size > 1024 * 1024:
        raise VideoClipError(f"Expected a regular metadata file of at most 1 MiB: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise VideoClipError(f"Expected a JSON object: {path}")
    return value


def _selected_source(package: Path, relative: str) -> tuple[Path, dict, list[Path]]:
    _unlinked(package)
    root = package.resolve(strict=True)
    manifest_path = root / "manifest.json"
    manifest = _json(manifest_path)
    state = manifest.get("state")
    if state not in {"finalized", "finalized_recovered"}:
        raise VideoClipError("Choose a finalized or finalized_recovered package.")
    rel = PurePosixPath(relative)
    if (
        not relative
        or "\\" in relative
        or rel.is_absolute()
        or rel.as_posix() != relative
        or any(part in {"", ".", ".."} or ":" in part for part in rel.parts)
    ):
        raise VideoClipError("Use the exact package-relative POSIX path shown in Review.")
    selected = root
    for part in rel.parts:
        selected = selected / part
        _unlinked(selected)
    selected = selected.resolve(strict=True)
    if not selected.is_relative_to(root) or not selected.is_file():
        raise VideoClipError("Selected video must be a regular file within the package.")
    if selected.stat().st_size > MAX_SOURCE_BYTES:
        raise VideoClipError("Selected video exceeds the 2 GiB source limit.")
    # Use the maintained package and discovery imports, not another descriptor parser.
    repo = Path(__file__).resolve().parents[1]
    for name in ("capture_protocol", "capture_session", "capture_analysis"):
        path = str(repo / "libs" / "python" / name)
        if path not in sys.path:
            sys.path.insert(0, path)
    from capture_analysis.discover import discover_streams

    _json(selected.parent.parent / "stream.json")
    try:
        refs = discover_streams(root)
    except (TypeError, KeyError, ValueError) as exc:
        raise VideoClipError(
            "Package stream metadata is unusable; repair or choose another package."
        ) from exc
    matches = [
        ref
        for ref in refs
        for path in ref.mkv_paths
        if path.relative_to(root).as_posix() == relative
    ]
    if len(matches) != 1:
        raise VideoClipError("Choose one exact MKV path listed by the package's stream discovery.")
    ref = matches[0]
    if ref.stream_json_path is None:
        raise VideoClipError("Selected stream has no descriptor.")
    _json(ref.stream_json_path)
    inputs = [manifest_path, ref.stream_json_path, selected]
    source_json = selected.parents[3] / "source.json"
    if source_json.exists():
        _json(source_json)
        inputs.append(source_json)
    return selected, {
        "package_state": state,
        "source_id": ref.source_id,
        "stream_id": ref.stream_id,
        "relative_path": relative,
    }, inputs


def _run(argv: list[str], *, limit: int = MAX_PROBE_BYTES) -> bytes:
    """Bound in-memory output; retain a bounded actionable diagnostic on refusal."""
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        try:
            process = subprocess.run(
                argv, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
                timeout=PROCESS_TIMEOUT, check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise VideoClipError(
                f"{Path(argv[0]).name} exceeded {PROCESS_TIMEOUT}s; choose a shorter segment."
            ) from exc
        stderr.seek(0, os.SEEK_END)
        size = stderr.tell()
        stderr.seek(max(0, size - 8192))
        detail = stderr.read().decode("utf-8", errors="replace").strip()
        if process.returncode:
            raise VideoClipError(
                f"{Path(argv[0]).name} exited {process.returncode}: {detail or 'no diagnostic'}"
            )
        stdout.seek(0, os.SEEK_END)
        if stdout.tell() > limit:
            raise VideoClipError("Media inspection exceeded the bounded output limit.")
        stdout.seek(0)
        return stdout.read()


def _integer(value, label: str) -> int:
    if isinstance(value, bool) or not re.fullmatch(r"-?[0-9]+", str(value)):
        raise VideoClipError(f"Media has no exact integer {label}.")
    return int(value)


def _probe(path: Path, executable: str) -> dict:
    argv = [
        executable, "-v", "error", "-threads", "1", "-protocol_whitelist", "file",
        "-show_streams", "-show_frames", "-select_streams", "v",
        "-show_entries",
        "stream=index,codec_name,codec_type,width,height,time_base:"
        "frame=stream_index,best_effort_timestamp,duration,pkt_duration",
        "-of", "json", str(path),
    ]
    doc = json.loads(_run(argv))
    streams = doc.get("streams", [])
    if len(streams) != 1 or streams[0].get("codec_type") != "video":
        raise VideoClipError("Exactly one video stream is required.")
    stream = streams[0]
    width = _integer(stream.get("width"), "width")
    height = _integer(stream.get("height"), "height")
    if width <= 0 or height <= 0 or width > 3840 or height > 2160 or width % 2 or height % 2:
        raise VideoClipError("Video must have even positive dimensions no larger than 3840x2160.")
    try:
        time_base = Fraction(stream["time_base"])
    except (KeyError, TypeError, ValueError, ZeroDivisionError) as exc:
        raise VideoClipError("Video has no usable rational time base.") from exc
    if time_base <= 0:
        raise VideoClipError("Video time base must be positive.")
    frames = doc.get("frames", [])
    if not isinstance(frames, list) or not 1 <= len(frames) <= MAX_FRAMES:
        raise VideoClipError(f"Video must contain 1..{MAX_FRAMES} decoded frames.")
    ticks = [
        _integer(frame.get("best_effort_timestamp"), "presentation timestamp") for frame in frames
    ]
    if any(right <= left for left, right in zip(ticks, ticks[1:], strict=False)):
        raise VideoClipError("Decoded video timestamps must be strictly increasing.")
    duration = _integer(
        frames[-1].get("duration", frames[-1].get("pkt_duration")), "final-frame duration"
    )
    if duration <= 0:
        raise VideoClipError("The final decoded frame must have a known positive duration.")
    span = (ticks[-1] + duration - ticks[0]) * time_base
    if span > MAX_SOURCE_SECONDS:
        raise VideoClipError("Video exceeds the one-hour decoded-media bound.")
    return {
        "width": width, "height": height, "codec": stream.get("codec_name"),
        "stream_index": _integer(stream.get("index"), "stream index"),
        "time_base": str(time_base), "ticks": ticks, "final_duration_ticks": duration,
        "duration_seconds": str(span), "command": argv,
    }


def _selection(media: dict, start_ms: int, end_ms: int) -> tuple[int, int]:
    if (
        type(start_ms) is not int or type(end_ms) is not int
        or start_ms < 0 or end_ms <= start_ms or end_ms - start_ms > MAX_CLIP_MS
    ):
        raise VideoClipError("Use 0 <= start-ms < end-ms with an interval of at most 600000 ms.")
    time_base = Fraction(media["time_base"])
    ticks = media["ticks"]
    end = Fraction(end_ms, 1000)
    if end > Fraction(media["duration_seconds"]):
        raise VideoClipError("Requested interval extends beyond the last decoded frame's end.")
    start = Fraction(start_ms, 1000)
    selected = [
        i for i, tick in enumerate(ticks)
        if start <= (tick - ticks[0]) * time_base < end
    ]
    if not selected:
        raise VideoClipError("No decoded frame begins within this half-open media interval.")
    return selected[0], selected[-1] + 1


def _toolchain() -> dict:
    paths = {name: shutil.which(name) for name in ("ffmpeg", "ffprobe")}
    if any(path is None for path in paths.values()):
        raise VideoClipError("Install/use an existing FFmpeg and FFprobe on PATH, then retry.")
    versions = {}
    for name, path in paths.items():
        versions[name] = _run([path, "-version"], limit=1024 * 1024).decode(
            "utf-8", errors="replace"
        ).splitlines()[0]
    encoders = _run([paths["ffmpeg"], "-hide_banner", "-encoders"], limit=1024 * 1024)
    if not re.search(rb"\blibx264\b", encoders):
        raise VideoClipError("This FFmpeg has no libx264 encoder; use a build that provides it.")
    return {"paths": paths, "versions": versions}


def export_video_clip(
    package: str | Path, destination: str | Path, relative: str, start_ms: int, end_ms: int,
) -> dict:
    """Publish a new external review directory; completion manifest is written last."""
    # Cheap request admission precedes discovery, subprocesses and destination writes.
    if (
        type(start_ms) is not int or type(end_ms) is not int
        or start_ms < 0 or end_ms <= start_ms or end_ms - start_ms > MAX_CLIP_MS
    ):
        raise VideoClipError("Use 0 <= start-ms < end-ms with an interval of at most 600000 ms.")
    package = Path(package)
    source, identity, input_paths = _selected_source(package, relative)
    root = package.resolve(strict=True)
    out_arg = Path(destination)
    if os.path.lexists(out_arg):
        raise VideoClipError("Destination already exists; choose a new external directory.")
    parent = out_arg.parent.resolve(strict=True)
    out = parent / out_arg.name
    if not parent.is_dir() or out.is_relative_to(root):
        raise VideoClipError("Choose a new destination outside the source package.")
    before = {str(path.relative_to(root)): _pin(path) for path in input_paths}
    tools = _toolchain()
    media = _probe(source, tools["paths"]["ffprobe"])
    first, stop = _selection(media, start_ms, end_ms)
    out.mkdir(exist_ok=False)
    incomplete = out / "clip.incomplete.mp4"
    command = [
        tools["paths"]["ffmpeg"], "-hide_banner", "-v", "error", "-nostdin", "-n",
        "-threads", "1", "-noautorotate", "-protocol_whitelist", "file", "-i", str(source),
        "-map", f"0:{media['stream_index']}", "-an", "-sn", "-dn", "-map_metadata", "-1",
        "-vf", f"trim=start_frame={first}:end_frame={stop},setpts=PTS-STARTPTS",
        "-fps_mode", "passthrough", "-enc_time_base", media["time_base"],
        "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
        "-threads", "1", "-movflags", "+faststart", str(incomplete),
    ]
    try:
        _run(command, limit=1024 * 1024)
        actual = _probe(incomplete, tools["paths"]["ffprobe"])
        if (
            actual["codec"] != "h264" or len(actual["ticks"]) != stop - first
            or actual["ticks"][0] != 0
            or (actual["width"], actual["height"]) != (media["width"], media["height"])
        ):
            raise VideoClipError(
                "Encoded output does not match the selected frame/dimension contract."
            )
        # Check relative presentation spacing without claiming identical container ticks.
        source_tb, output_tb = Fraction(media["time_base"]), Fraction(actual["time_base"])
        tolerance = max(source_tb, output_tb)
        for index, tick in enumerate(actual["ticks"]):
            expected = (media["ticks"][first + index] - media["ticks"][first]) * source_tb
            if abs(tick * output_tb - expected) > tolerance:
                raise VideoClipError(
                    "Encoded output changed the selected frame presentation spacing."
                )
        after = {str(path.relative_to(root)): _pin(path) for path in input_paths}
        if before != after:
            raise VideoClipError("Source changed during export; no completed export is published.")
        output_pin = _pin(incomplete)
        report = {
            "export_schema": "capture.video_clip_export/1",
            "state": "complete", "package": str(root), **identity,
            "inputs": before, "requested_interval_ms": {"start": start_ms, "end": end_ms},
            "selection_rule": "start <= (frame_pts-first_decoded_pts)*time_base < end",
            "source_video": {
                "width": media["width"], "height": media["height"], "codec": media["codec"],
                "time_base": media["time_base"], "first_decoded_pts": media["ticks"][0],
                "decoded_frame_count": len(media["ticks"]),
                "decoded_duration_seconds": media["duration_seconds"],
                "first_selected_frame": first, "stop_selected_frame_exclusive": stop,
                "selected_pts": media["ticks"][first:stop],
            },
            "output": {
                "path": "clip.mp4", **output_pin,
                **{key: actual[key] for key in (
                    "width", "height", "codec", "time_base", "ticks",
                    "final_duration_ticks", "duration_seconds",
                )},
                "frame_count": stop - first,
            },
            "tools": tools, "encode_command": command, "probe_command": media["command"],
            "limitations": [
                "Lossy H.264/yuv420p review copy; retain the original recording.",
                "Local decoded media time only; no session, camera or checkpoint alignment.",
                "Video only. Audio, subtitles, metadata and unselected streams are omitted.",
                "Frame starts determine inclusion; "
                "output duration need not equal requested duration.",
                "Source hashes describe observed bytes; "
                "no integrity, hardware or clinical assurance.",
            ],
        }
        # A final name without the completion manifest is still an incomplete export.
        incomplete.rename(out / "clip.mp4")
        temporary = out / "export_manifest.incomplete.json"
        with temporary.open("x", encoding="utf-8", newline="\n") as handle:
            json.dump(report, handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.write("\n")
        temporary.rename(out / "export_manifest.json")
        return report
    except Exception as exc:
        # Retain only this newly created directory. Never erase a previous destination.
        try:
            with (out / "failure.json").open("x", encoding="utf-8", newline="\n") as handle:
                json.dump({"state": "failed", "error": str(exc), "completion_manifest": False},
                          handle, ensure_ascii=False, indent=2)
                handle.write("\n")
        except OSError:
            pass
        raise
