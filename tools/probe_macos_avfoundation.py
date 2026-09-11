# SPDX-License-Identifier: GPL-3.0-only
"""Bounded macOS AVFoundation camera capture probe.

This proves host-level camera visibility/capture for the native-mac portability
track without claiming CaptureSuite daemon/session integration.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEVICE_RE = re.compile(r"\[(\d+)\]\s+(.+)$")


def _run(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, check=check, capture_output=True, text=True)


def list_video_devices(ffmpeg: str = "ffmpeg") -> dict[int, str]:
    proc = _run(
        [ffmpeg, "-hide_banner", "-f", "avfoundation", "-list_devices", "true", "-i", ""],
        check=False,
    )
    devices: dict[int, str] = {}
    in_video = False
    for raw in proc.stderr.splitlines():
        if "AVFoundation video devices:" in raw:
            in_video = True
            continue
        if "AVFoundation audio devices:" in raw:
            break
        if not in_video:
            continue
        match = DEVICE_RE.search(raw)
        if match:
            devices[int(match.group(1))] = match.group(2).strip()
    return devices


def choose_device(devices: dict[int, str], name: str) -> tuple[int, str]:
    needle = name.casefold()
    matches = [(idx, value) for idx, value in devices.items() if needle in value.casefold()]
    if len(matches) != 1:
        rendered = ", ".join(f"{idx}:{value}" for idx, value in devices.items()) or "none"
        raise RuntimeError(
            f"expected exactly one video device matching {name!r}; "
            f"found {len(matches)} ({rendered})"
        )
    return matches[0]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_head() -> str:
    proc = _run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], check=False)
    return proc.stdout.strip() if proc.returncode == 0 else "unknown"


def probe_metadata(ffprobe: str, path: Path) -> dict[str, object]:
    proc = _run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration,size",
            "-show_entries",
            "stream=codec_name,width,height,r_frame_rate,nb_frames",
            "-of",
            "json",
            str(path),
        ]
    )
    return json.loads(proc.stdout)


def capture(
    ffmpeg: str,
    index: int,
    output: Path,
    *,
    seconds: float,
    framerate: int,
    video_size: str,
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    _run(
        [
            ffmpeg,
            "-hide_banner",
            "-y",
            "-f",
            "avfoundation",
            "-framerate",
            str(framerate),
            "-video_size",
            video_size,
            "-pixel_format",
            "uyvy422",
            "-i",
            f"{index}:none",
            "-t",
            str(seconds),
            "-c:v",
            "h264_videotoolbox",
            "-an",
            str(output),
        ]
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, nargs="?", help="MOV output path")
    parser.add_argument("--device-name", default="iPhone Camera")
    parser.add_argument("--seconds", type=float, default=2.0)
    parser.add_argument("--framerate", type=int, default=30)
    parser.add_argument("--video-size", default="1280x720")
    parser.add_argument("--list", action="store_true", help="List video devices and exit")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if sys.platform != "darwin":
        print("probe is macOS-only", file=sys.stderr)
        return 2
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        print("ffmpeg and ffprobe are required", file=sys.stderr)
        return 2

    devices = list_video_devices(ffmpeg)
    if args.list:
        print(json.dumps(devices, indent=2))
        return 0
    if args.output is None:
        print("output path is required unless --list is used", file=sys.stderr)
        return 2

    try:
        index, device_name = choose_device(devices, args.device_name)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    try:
        capture(
            ffmpeg,
            index,
            args.output,
            seconds=args.seconds,
            framerate=args.framerate,
            video_size=args.video_size,
        )
        metadata = probe_metadata(ffprobe, args.output)
    except subprocess.CalledProcessError as exc:
        if exc.stderr:
            print(exc.stderr, file=sys.stderr)
        return exc.returncode or 1
    receipt = {
        "classification": "macos_avfoundation_capture_probe",
        "status": "completed",
        "capture_suite_commit": git_head(),
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "mac_version": platform.mac_ver()[0],
        },
        "device": {"index": index, "name": device_name},
        "request": {
            "seconds": args.seconds,
            "framerate": args.framerate,
            "video_size": args.video_size,
        },
        "output": {
            "path": str(args.output),
            "sha256": sha256_file(args.output),
            "ffprobe": metadata,
        },
        "limitations": (
            "Host AVFoundation camera proof only; does not establish CaptureSuite "
            "daemon/session integration, synchronization, or hardware qualification."
        ),
    }
    receipt_path = args.output.with_suffix(args.output.suffix + ".receipt.json")
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
