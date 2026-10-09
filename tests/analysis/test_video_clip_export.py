# SPDX-License-Identifier: GPL-3.0-only
"""Selected-video export through real FFmpeg and the maintained CLI."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from fractions import Fraction
from pathlib import Path

import pytest
import video_clip

ROOT = Path(__file__).resolve().parents[2]
FF = shutil.which("ffmpeg")
FP = shutil.which("ffprobe")


def run(argv, *, input_bytes=None):
    return subprocess.run(
        [str(x) for x in argv], input=input_bytes, capture_output=True, timeout=30,
    )


def manifest(path):
    return json.loads((path / "export_manifest.json").read_text(encoding="utf-8"))


def files(root):
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in root.rglob("*") if p.is_file()
    }


@pytest.fixture
def package(tmp_path):
    if not FF or not FP:
        pytest.skip("This real-media test needs existing FFmpeg and FFprobe.")
    p = tmp_path / "synthetic.mmsession"
    p.mkdir()
    (p / "manifest.json").write_text('{"state":"finalized_recovered"}', encoding="utf-8")
    for folder, sid, offset in [("left", "camera.A", 0), ("right", "camera.B", 100)]:
        directory = p / "sources" / folder / "streams" / "front" / "segments"
        directory.mkdir(parents=True)
        (directory.parent / "stream.json").write_text(json.dumps({
            "sourceId": sid, "streamId": "front.recorded", "modality": "video",
            "nominalRateHz": 10,
        }), encoding="utf-8")
        raw = b"".join(bytes((offset + i * 10, 40, 180 - i * 8)) * (64 * 48)
                       for i in range(12))
        args = [
            FF, "-v", "error", "-f", "rawvideo", "-pixel_format", "rgb24",
            "-video_size", "64x48", "-framerate", "10", "-i", "pipe:0",
            "-frames:v", "12", "-an", "-c:v", "libx264", "-preset", "veryfast",
            "-crf", "0", "-pix_fmt", "yuv420p", "-threads", "1", "-y",
            directory / "0001.mkv",
        ]
        done = run(args, input_bytes=raw)
        assert done.returncode == 0, done.stderr
    return p


def cli(package, output, *options):
    return run([
        sys.executable, "-B", ROOT / "tools" / "export_session.py", package, output, *options,
    ])


def options(path="sources/right/streams/front/segments/0001.mkv", start=300, end=800):
    return ["--video-segment", path, "--video-start-ms", str(start), "--video-end-ms", str(end)]


def decode(path):
    done = run([
        FF, "-v", "error", "-i", path, "-map", "0:v:0", "-f", "rawvideo",
        "-pix_fmt", "rgb24", "-threads", "1", "pipe:1",
    ])
    assert done.returncode == 0, done.stderr
    size = 64 * 48 * 3
    assert len(done.stdout) % size == 0
    return [done.stdout[i:i + size] for i in range(0, len(done.stdout), size)]


def test_actual_cli_decoded_selection_and_provenance(package, tmp_path):
    before = files(package)
    out = tmp_path / "clip"
    done = cli(package, out, *options())
    assert done.returncode == 0, done.stderr
    doc = manifest(out)
    assert doc["export_schema"] == "capture.video_clip_export/1"
    assert doc["source_id"] == "camera.B" and doc["stream_id"] == "front.recorded"
    assert doc["relative_path"] == "sources/right/streams/front/segments/0001.mkv"
    assert doc["package_state"] == "finalized_recovered"
    assert doc["source_video"]["first_selected_frame"] == 3
    assert doc["source_video"]["stop_selected_frame_exclusive"] == 8
    assert doc["output"]["frame_count"] == 5 and doc["output"]["ticks"][0] == 0
    original = decode(package / doc["relative_path"])
    actual = decode(out / "clip.mp4")
    assert len(actual) == 5
    for image, expected in zip(actual, original[3:8], strict=True):
        assert max(abs(a - b) for a, b in zip(image, expected, strict=True)) <= 8
    inspected = run([FP, "-v", "error", "-show_streams", "-of", "json", out / "clip.mp4"])
    streams = json.loads(inspected.stdout)["streams"]
    assert len(streams) == 1 and streams[0]["codec_name"] == "h264"
    assert before == files(package)


def test_nonzero_origin_vfr_half_open(package, tmp_path):
    selected = package / "sources/right/streams/front/segments/vfr.mkv"
    raw = b"".join(bytes((i * 30, 80, 180)) * (64 * 48) for i in range(6))
    done = run([
        FF, "-v", "error", "-f", "rawvideo", "-pixel_format", "rgb24",
        "-video_size", "64x48", "-framerate", "10", "-i", "pipe:0",
        "-frames:v", "6", "-vf", "settb=1/1000,setpts=N*N*25+5000",
        "-fps_mode", "passthrough", "-enc_time_base", "1/1000",
        "-c:v", "ffv1", "-threads", "1", "-y", selected,
    ], input_bytes=raw)
    assert done.returncode == 0, done.stderr
    media = video_clip._probe(selected, FP)
    tb = Fraction(media["time_base"])
    assert [tick * tb for tick in media["ticks"]] == [
        Fraction(x, 1000) for x in (5000, 5025, 5100, 5225, 5400, 5625)
    ]
    out = tmp_path / "vfr"
    before = files(package)
    relative = str(selected.relative_to(package)).replace("\\", "/")
    done = cli(package, out, *options(relative, 25, 225))
    assert done.returncode == 0, done.stderr
    doc = manifest(out)
    assert doc["source_video"]["first_selected_frame"] == 1
    assert doc["source_video"]["stop_selected_frame_exclusive"] == 3
    assert doc["source_video"]["first_decoded_pts"] == media["ticks"][0]
    assert doc["source_video"]["selected_pts"] == media["ticks"][1:3]
    assert len(decode(out / "clip.mp4")) == 2
    second_pts = Fraction(doc["output"]["ticks"][1]) * Fraction(doc["output"]["time_base"])
    assert second_pts == Fraction(75, 1000)
    assert files(package) == before


@pytest.mark.parametrize("extra", [
    ["--video-start-ms", "0"],
    ["--video-segment", "missing", "--video-start-ms", "0", "--video-end-ms", "2.5"],
    [*options(), "--modalities", "video"],
    [*options(), "--verify"],
])
def test_cli_syntax_refuses_before_output(package, tmp_path, extra):
    before = files(package)
    out = tmp_path / "refused"
    done = cli(package, out, *extra)
    assert done.returncode == 2 and not out.exists()
    assert files(package) == before


@pytest.mark.parametrize("start,end", [(-1, 5), (3, 3), (8, 4), (0, 600001), (25, 30), (0, 1500)])
def test_interval_refusal_before_output(package, tmp_path, start, end):
    before = files(package)
    out = tmp_path / "refused"
    done = cli(package, out, *options(start=start, end=end))
    assert done.returncode == 1 and b"FAIL video clip:" in done.stderr and not out.exists()
    assert files(package) == before


@pytest.mark.parametrize("relative", [
    "../outside.mkv", "sources/right/streams/front/segments/no.mkv",
    "sources/right/streams/front/segments/../segments/0001.mkv",
])
def test_exact_path_refusal(package, tmp_path, relative):
    before = files(package)
    out = tmp_path / "refused"
    done = cli(package, out, *options(path=relative))
    assert done.returncode == 1 and not out.exists()
    assert files(package) == before


def test_occupied_and_internal_destinations_preserved(package, tmp_path):
    out = tmp_path / "occupied"
    out.mkdir()
    (out / "sentinel").write_bytes(b"preserve me")
    before = files(package)
    done = cli(package, out, *options())
    assert done.returncode == 1 and (out / "sentinel").read_bytes() == b"preserve me"
    assert sorted(p.name for p in out.iterdir()) == ["sentinel"]
    done = cli(package, package / "new-output", *options())
    assert done.returncode == 1 and files(package) == before


def test_unfinalized_and_invalid_media_refuse(package, tmp_path):
    (package / "manifest.json").write_text('{"state":"recording"}', encoding="utf-8")
    before = files(package)
    out = tmp_path / "refused"
    done = cli(package, out, *options())
    assert done.returncode == 1 and not out.exists() and files(package) == before
    (package / "manifest.json").write_text('{"state":"finalized"}', encoding="utf-8")
    video = package / "sources/right/streams/front/segments/bad.mkv"
    video.write_bytes(b"not encoded video")
    before = files(package)
    done = cli(package, out, *options(path=str(video.relative_to(package)).replace("\\", "/")))
    assert done.returncode == 1 and not out.exists() and files(package) == before


def test_real_encoder_failure_retains_partial_no_success_then_retry(package, tmp_path, monkeypatch):
    original = video_clip._run
    def refuse_encoder(argv, **kwargs):
        if "libx264" in argv:
            argv = argv.copy()
            argv[argv.index("libx264")] = "deliberately_unavailable_encoder"
        return original(argv, **kwargs)
    monkeypatch.setattr(video_clip, "_run", refuse_encoder)
    before = files(package)
    out = tmp_path / "failed"
    with pytest.raises(video_clip.VideoClipError, match="exited"):
        video_clip.export_video_clip(
            package, out, "sources/right/streams/front/segments/0001.mkv", 300, 800,
        )
    assert out.is_dir() and not (out / "export_manifest.json").exists()
    assert json.loads((out / "failure.json").read_text())["state"] == "failed"
    assert files(package) == before
    monkeypatch.setattr(video_clip, "_run", original)
    done = cli(package, tmp_path / "retry", *options())
    assert done.returncode == 0, done.stderr


def test_observed_source_change_refuses_completion(package, tmp_path, monkeypatch):
    original = video_clip._probe
    meta = package / "sources/right/streams/front/stream.json"
    old = meta.read_bytes()
    def changed_after_encoding(path, executable):
        result = original(path, executable)
        if path.name == "clip.incomplete.mp4":
            meta.write_bytes(old + b" ")
        return result
    monkeypatch.setattr(video_clip, "_probe", changed_after_encoding)
    out = tmp_path / "changed"
    try:
        with pytest.raises(video_clip.VideoClipError, match="Source changed"):
            video_clip.export_video_clip(
                package, out, "sources/right/streams/front/segments/0001.mkv", 300, 800,
            )
        assert not (out / "export_manifest.json").exists()
        assert json.loads((out / "failure.json").read_text())["state"] == "failed"
    finally:
        meta.write_bytes(old)


def test_whole_video_export_still_available(package, tmp_path):
    before = files(package)
    out = tmp_path / "whole"
    done = cli(package, out, "--modalities", "video")
    assert done.returncode == 0, done.stderr
    doc = manifest(out)
    assert doc["export_schema"] == "capture.export_manifest/1"
    assert len(doc["video"]) == 2 and all(item["ok"] for item in doc["video"])
    assert files(package) == before


def test_invalid_descriptor_is_actionable_before_output(package, tmp_path):
    meta = package / "sources/right/streams/front/stream.json"
    meta.write_text('"sourceId"', encoding="utf-8")
    before = files(package)
    out = tmp_path / "refused"
    done = cli(package, out, *options())
    assert done.returncode == 1 and b"FAIL video clip:" in done.stderr
    assert b"Traceback" not in done.stderr and not out.exists()
    assert files(package) == before


@pytest.mark.skipif(sys.platform != "win32", reason="Windows junction receiver")
def test_input_junction_and_output_alias_refusal(package, tmp_path):
    junction = package / "sources/linked"
    done = run(["cmd", "/c", "mklink", "/J", junction, package / "sources/right"])
    assert done.returncode == 0, done.stderr
    before = files(package)
    try:
        out = tmp_path / "refused"
        done = cli(package, out, *options(path="sources/linked/streams/front/segments/0001.mkv"))
        assert done.returncode == 1 and not out.exists()
        alias = tmp_path / "alias-to-package"
        made = run(["cmd", "/c", "mklink", "/J", alias, package])
        assert made.returncode == 0, made.stderr
        try:
            done = cli(package, alias / "new-export", *options())
            assert done.returncode == 1 and not (package / "new-export").exists()
            assert files(package) == before
        finally:
            alias.rmdir()
    finally:
        junction.rmdir()
