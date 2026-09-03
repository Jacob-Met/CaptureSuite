# SPDX-License-Identifier: GPL-3.0-only
"""Offline export of a sealed .mmsession package.

Produces:
  <out>/export_manifest.json
  <out>/radar/<source_id>/frames.npy   (FMCW uint16 or LTR11 complex64)
  <out>/radar/<source_id>/stream.json  (copy of config snapshot)
  <out>/video/<source_id>/*.mp4        (ffmpeg rewrap of MKV segments when available)
  <out>/imu/<source_id>/frames.jsonl   (decoded ImuFrame summaries when mcap available)
  <out>/emg/<source_id>/batches.jsonl  (decoded EmgBatch summaries when mcap available)

Usage:
  python tools/export_session.py path/to/session.mmsession [out_dir]
"""

from __future__ import annotations

import json
import shutil
import struct
import subprocess
import sys
from pathlib import Path

try:
    import numpy as np
except ImportError:  # pragma: no cover
    np = None  # type: ignore


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _find_mcap_files(root: Path) -> list[Path]:
    return sorted(root.rglob("*.mcap"))


def _find_mkv_files(root: Path) -> list[Path]:
    return sorted(root.rglob("*.mkv"))


def _deinterleave_hint(stream_json: dict) -> tuple[int, int, int]:
    applied = (stream_json.get("applied") or stream_json.get("requested") or {})
    chirp = applied.get("chirp") or {}
    num_rx = int(stream_json.get("num_rx") or 3)
    num_chirps = int(applied.get("num_chirps") or stream_json.get("num_chirps") or 32)
    num_samples = int(chirp.get("num_samples") or stream_json.get("num_samples") or 128)
    return num_rx, num_chirps, num_samples


def export_radar_mcaps(root: Path, out: Path, manifest: dict) -> None:
    """Best-effort: copy stream.json and note MCAP paths.

    Full MCAP decode depends on the installed `mcap` Python package and the
    registered protobuf schemas. When unavailable we still export provenance
    and leave the MCAP path in the manifest for offline tooling.
    """
    radar_out = out / "radar"
    radar_out.mkdir(parents=True, exist_ok=True)
    for stream_json in root.rglob("stream.json"):
        if "exports" in stream_json.parts:
            continue
        text = stream_json.read_text(encoding="utf-8")
        try:
            doc = json.loads(text)
        except json.JSONDecodeError:
            continue
        schema = doc.get("schema") or ""
        if "radar" not in schema and "num_chirps" not in doc and "board_uuid" not in doc:
            # Keep any stream.json under a radar-looking folder.
            if "radar" not in str(stream_json).lower():
                continue
        # Infer source id from parent directory name when possible.
        parent = stream_json.parent.name
        sid = parent if parent.startswith("radar.") else stream_json.parent.parent.name
        dest_dir = radar_out / sid
        dest_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(stream_json, dest_dir / "stream.json")
        mcaps = list(stream_json.parent.glob("*.mcap")) + list(
            stream_json.parent.glob("**/*.mcap")
        )
        entry = {
            "source_id": sid,
            "stream_json": str(dest_dir / "stream.json"),
            "mcap_files": [str(p.relative_to(root)) for p in mcaps],
            "geometry": None,
        }
        if "num_chirps" in doc or "board_uuid" in doc:
            rx, chirps, samples = _deinterleave_hint(doc)
            entry["geometry"] = {
                "num_rx": rx,
                "num_chirps": chirps,
                "num_samples": samples,
                "bytes_per_frame": rx * chirps * samples * 2,
            }
        # Optional: decode with mcap if installed.
        frames_path = dest_dir / "frames.npy"
        if np is not None and mcaps:
            try:
                from mcap.reader import make_reader  # type: ignore
            except ImportError:
                entry["frames_npy"] = None
                entry["note"] = "install mcap+numpy to materialize frames.npy"
            else:
                payloads: list[bytes] = []
                for mcap_path in mcaps:
                    with mcap_path.open("rb") as fh:
                        reader = make_reader(fh)
                        for _schema, channel, message in reader.iter_messages():
                            # Prefer channels that look like radar frames.
                            topic = getattr(channel, "topic", "") or ""
                            if "radar" not in topic and "frame" not in topic:
                                continue
                            payloads.append(message.data)
                if payloads and entry.get("geometry"):
                    bpf = entry["geometry"]["bytes_per_frame"]
                    # Try to peel protobuf framing: look for raw payload size match
                    # at the end of each message; otherwise store opaque bytes.
                    mats = []
                    for raw in payloads:
                        if len(raw) >= bpf:
                            # Often the ADC bytes are a protobuf `bytes` field near the end.
                            blob = raw[-bpf:]
                            arr = np.frombuffer(blob, dtype="<u2")
                            rx, chirps, samples = (
                                entry["geometry"]["num_rx"],
                                entry["geometry"]["num_chirps"],
                                entry["geometry"]["num_samples"],
                            )
                            if arr.size == rx * chirps * samples:
                                mats.append(arr.reshape(rx, chirps, samples))
                    if mats:
                        stacked = np.stack(mats, axis=0)
                        np.save(frames_path, stacked)
                        entry["frames_npy"] = str(frames_path)
                        entry["frame_count"] = int(stacked.shape[0])
                    else:
                        # Save opaque message payloads for a dedicated decoder.
                        bin_path = dest_dir / "messages.bin"
                        with bin_path.open("wb") as out_bin:
                            for raw in payloads:
                                out_bin.write(struct.pack("<I", len(raw)))
                                out_bin.write(raw)
                        entry["messages_bin"] = str(bin_path)
                        entry["message_count"] = len(payloads)
                else:
                    entry["frames_npy"] = None
        manifest.setdefault("radar", []).append(entry)


def export_imu_emg(root: Path, out: Path, manifest: dict) -> None:
    """Decode sim/vendor IMU and EMG MCAP into lightweight JSONL summaries."""
    try:
        from mcap.reader import make_reader
    except ImportError:
        manifest["imu_emg_note"] = "install mcap to decode imu/emg segments"
        return

    def _safe_reader(mf):
        try:
            return make_reader(mf)
        except Exception:
            return None

    proto_root = Path(__file__).resolve().parents[1] / "libs" / "python" / "capture_protocol"
    if str(proto_root) not in sys.path:
        sys.path[:0] = [str(proto_root)]
    from capture_protocol.generated.capture.v1.data import (  # type: ignore
        emg_batch_pb2,
        imu_frame_pb2,
    )

    specs = (
        ("imu", "imu.frame", imu_frame_pb2.ImuFrame, "frames.jsonl", "imu"),
        ("emg", "emg.batch", emg_batch_pb2.EmgBatch, "batches.jsonl", "emg"),
    )
    sources_root = root / "sources"
    if not sources_root.is_dir():
        return

    for kind, schema_needle, decoder, out_name, manifest_key in specs:
        kind_out = out / kind
        for src_dir in sorted(p for p in sources_root.iterdir() if p.is_dir()):
            mcaps = sorted(src_dir.rglob("*.mcap"))
            if not mcaps:
                continue
            # Match by source id prefix or by schema name inside the first mcap.
            name_hint = kind in src_dir.name.lower()
            if not name_hint:
                try:
                    with mcaps[0].open("rb") as mf:
                        reader = _safe_reader(mf)
                        if reader is None:
                            continue
                        for schema, _ch, _msg in reader.iter_messages():
                            sname = schema.name if schema else ""
                            if schema_needle in sname:
                                name_hint = True
                            break
                except OSError:
                    continue
            if not name_hint:
                continue

            dest = kind_out / src_dir.name
            dest.mkdir(parents=True, exist_ok=True)
            jsonl = dest / out_name
            count = 0
            with jsonl.open("w", encoding="utf-8") as fh:
                for mcap_path in mcaps:
                    try:
                        with mcap_path.open("rb") as mf:
                            reader = _safe_reader(mf)
                            if reader is None:
                                continue
                            for schema, _ch, message in reader.iter_messages():
                                sname = schema.name if schema else ""
                                if schema_needle not in sname:
                                    continue
                                msg = decoder()
                                msg.ParseFromString(message.data)
                                if kind == "imu":
                                    row = {
                                        "sequence": msg.timing.sequence_number,
                                        "session_time_ns": msg.timing.session_time_ns,
                                        "sensor_count": len(msg.sensors),
                                        "sensors": [s.sensor_id for s in msg.sensors],
                                        "accel_z0": (
                                            msg.sensors[0].accel_z if msg.sensors else None
                                        ),
                                    }
                                else:
                                    row = {
                                        "sequence": msg.timing.sequence_number,
                                        "session_time_ns": msg.timing.session_time_ns,
                                        "channel_ids": list(msg.channel_ids),
                                        "sample_count": msg.sample_count,
                                        "bytes": len(msg.samples_f32_le),
                                    }
                                fh.write(json.dumps(row) + "\n")
                                count += 1
                    except OSError:
                        continue
            if count == 0:
                continue
            manifest.setdefault(manifest_key, []).append(
                {
                    "source_id": src_dir.name,
                    "mcap_files": [str(p.relative_to(root)) for p in mcaps],
                    "summary": str(jsonl.relative_to(out)),
                    "message_count": count,
                }
            )


def export_video(root: Path, out: Path, manifest: dict) -> None:
    video_out = out / "video"
    video_out.mkdir(parents=True, exist_ok=True)
    ffmpeg = shutil.which("ffmpeg")
    for mkv in _find_mkv_files(root):
        if "exports" in mkv.parts:
            continue
        # sources/<id>/.../segment.mkv → group by nearest source-like folder
        sid = "camera"
        for part in mkv.parts:
            if part.startswith("camera.") or part.startswith("Camera"):
                sid = part
                break
        dest_dir = video_out / sid
        dest_dir.mkdir(parents=True, exist_ok=True)
        mp4 = dest_dir / (mkv.stem + ".mp4")
        entry = {
            "source_id": sid,
            "mkv": str(mkv.relative_to(root)),
            "mp4": str(mp4) if ffmpeg else None,
        }
        if ffmpeg:
            cmd = [
                ffmpeg,
                "-y",
                "-i",
                str(mkv),
                "-c",
                "copy",
                str(mp4),
            ]
            try:
                subprocess.run(cmd, check=True, capture_output=True)
                entry["ok"] = True
            except subprocess.CalledProcessError as exc:
                entry["ok"] = False
                entry["error"] = exc.stderr.decode("utf-8", errors="replace")[-500:]
        else:
            # Still copy the MKV next to the export so analysis can proceed.
            shutil.copy2(mkv, dest_dir / mkv.name)
            entry["mkv_copy"] = str(dest_dir / mkv.name)
            entry["note"] = "ffmpeg not on PATH; copied MKV instead of MP4"
        manifest.setdefault("video", []).append(entry)


def main(argv: list[str] | None = None) -> int:
    import argparse
    from datetime import datetime, timezone

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("package")
    ap.add_argument("out_dir", nargs="?")
    ap.add_argument(
        "--verify",
        action="store_true",
        help="fail if a finalized package yields zero exportable streams",
    )
    args = ap.parse_args(argv)

    root = Path(args.package).resolve()
    if not root.exists():
        print("package not found:", root)
        return 1
    if args.out_dir:
        out = Path(args.out_dir).resolve()
    else:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        out = root / "exports" / stamp
    out.mkdir(parents=True, exist_ok=True)

    manifest: dict = {
        "package": str(root),
        "export_schema": "capture.export_manifest/1",
        "radar": [],
        "video": [],
        "imu": [],
        "emg": [],
        "integrity": None,
        "arrays": None,
        "events": {},
    }
    integrity = root / "integrity.json"
    if integrity.exists():
        manifest["integrity"] = _load_json(integrity)
    arrays = root / "arrays.json"
    if arrays.exists():
        manifest["arrays"] = _load_json(arrays)
        shutil.copy2(arrays, out / "arrays.json")
    events = root / "events"
    for name in ("checkpoints.json", "annotations.json", "sync_anchors.json"):
        path = events / name
        if path.is_file():
            try:
                manifest["events"][name] = _load_json(path)
            except json.JSONDecodeError:
                manifest["events"][name] = {"error": "parse_failed"}
    recovery = root / "recovery"
    if recovery.is_dir():
        reports = sorted(recovery.glob("report_*.json"))
        if reports:
            manifest["recovery_report"] = str(reports[-1].relative_to(root))

    export_radar_mcaps(root, out, manifest)
    export_video(root, out, manifest)
    export_imu_emg(root, out, manifest)

    man_path = out / "export_manifest.json"
    man_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print("wrote", man_path)
    print(
        "radar",
        len(manifest["radar"]),
        "video",
        len(manifest["video"]),
        "imu",
        len(manifest["imu"]),
        "emg",
        len(manifest["emg"]),
    )
    if args.verify:
        stream_count = (
            len(manifest["radar"])
            + len(manifest["video"])
            + len(manifest["imu"])
            + len(manifest["emg"])
        )
        state = ""
        try:
            state = str((_load_json(root / "manifest.json") or {}).get("state") or "")
        except Exception:
            pass
        if state.startswith("finalized") and stream_count == 0:
            print("FAIL --verify: finalized package exported zero streams")
            return 1
        # Prefer non-empty message/frame counts when present.
        radar_msgs = sum(
            int(e.get("frame_count") or e.get("message_count") or 0)
            for e in manifest["radar"]
        )
        imu_msgs = sum(int(e.get("message_count") or 0) for e in manifest["imu"])
        emg_msgs = sum(int(e.get("message_count") or 0) for e in manifest["emg"])
        if (
            state.startswith("finalized")
            and (manifest["radar"] or manifest["imu"] or manifest["emg"])
            and (radar_msgs + imu_msgs + emg_msgs) == 0
            and not manifest["video"]
        ):
            print("FAIL --verify: no decoded messages in exported streams")
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
