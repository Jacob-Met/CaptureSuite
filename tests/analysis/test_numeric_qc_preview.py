# SPDX-License-Identifier: GPL-3.0-only
"""Bounded excerpts must stay faithful to real recorded values and provenance."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

import pytest
from capture_analysis.qc import collect_qc
from capture_analysis.report_html import render_qc_html
from mcap.writer import CompressionType, Writer
from test_payload_inspection_qc import SEGMENT, SOURCE, _package, _write_batched_mcap, _write_mcap


def _preview(root: Path) -> dict:
    return collect_qc(root, inspect_payloads=True).to_dict()["streams"][0]["payloadInspection"]


def test_exact_sample_order_and_native_clock_strings(tmp_path: Path) -> None:
    root = _package(tmp_path)
    _write_mcap(root, values=[1, -2, 3, -4, 5, -6], times=[2**60, 2**60 + 3, 2**60 + 8])
    before = (root / SEGMENT).read_bytes()
    result = _preview(root)
    preview = result["numericPreview"]
    assert preview["schemaId"] == "capture.numeric_qc_preview/1"
    assert preview["framesShown"] == preview["framesChecked"] == 3
    assert preview["channelIds"] == ["left", "right"]
    assert preview["units"] == "N"
    batch = preview["batches"][0]
    assert batch["values"] == [[1, -2], [3, -4], [5, -6]]
    assert batch["nativeTimeNs"] == [str(2**60), str(2**60 + 3), str(2**60 + 8)]
    assert batch["segment"] == "000000.mcap"
    assert batch["sessionTimeNs"] == "1000000000"
    assert (root / SEGMENT).read_bytes() == before


def test_frame_and_channel_caps_do_not_limit_later_qc(tmp_path: Path) -> None:
    root = _package(tmp_path)
    target = root / SEGMENT
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("wb") as output:
        writer = Writer(output, compression=CompressionType.NONE)
        writer.start()
        schema = writer.register_schema("generic.numeric_batch/1", "jsonschema", b"{}")
        channel = writer.register_channel("force", "json", schema)
        for batch in range(2):
            writer.add_message(
                channel,
                batch * 1000,
                json.dumps(
                    {
                        "channel_count": 9,
                        "channel_names": [f"c{i}" for i in range(9)],
                        "samples": [batch * 10000 + i for i in range(300 * 9)],
                        "device_time_ns": list(range(batch * 300, (batch + 1) * 300)),
                    }
                ).encode(),
                batch * 1000,
            )
        writer.finish()
    result = _preview(root)
    preview = result["numericPreview"]
    assert result["sampleFramesChecked"] == preview["framesChecked"] == 600
    assert result["messagesChecked"] == 2
    assert preview["framesShown"] == 256
    assert preview["totalChannels"] == 9
    assert preview["channelIds"] == [f"c{i}" for i in range(6)]
    assert len(preview["batches"]) == 1
    values = preview["batches"][0]["values"]
    assert len(values) == 256
    assert all(len(row) == 6 for row in values)
    assert values[-1] == list(range(255 * 9, 255 * 9 + 6))


def test_batch_and_segment_boundaries_are_not_joined(tmp_path: Path) -> None:
    root = _package(tmp_path)
    _write_batched_mcap(root, batches=[[100, 200], [300, 400]])
    _write_batched_mcap(root, batches=[[500, 600]], segment="000001.mcap")
    report = collect_qc(root, inspect_payloads=True).to_dict()
    batches = report["streams"][0]["payloadInspection"]["numericPreview"]["batches"]
    assert [b["firstFrame"] for b in batches] == [0, 2, 4]
    assert [b["segment"] for b in batches] == ["000000.mcap", "000000.mcap", "000001.mcap"]
    html = render_qc_html(report)
    assert html.count('<polyline class="signal"') == 6
    assert "First 6 of 6 recorded sample frames" in html
    assert "not elapsed time" in html
    assert "batch boundaries" in html


def test_missing_native_clock_remains_visible_and_never_synthesized(tmp_path: Path) -> None:
    root = _package(tmp_path)
    _write_mcap(root, values=[1, 2, 3, 4], times=[])
    report = collect_qc(root, inspect_payloads=True).to_dict()
    preview = report["streams"][0]["payloadInspection"]["numericPreview"]
    assert preview["batches"][0]["nativeTimeNs"] == []
    assert report["trafficLights"][SOURCE] == "warn"
    assert "not recorded" in render_qc_html(report)


def test_failed_later_batch_does_not_advertise_successful_excerpt(tmp_path: Path) -> None:
    root = _package(tmp_path)
    _write_batched_mcap(root, batches=[list(range(300)), [1]])
    result = _preview(root)
    assert result["status"] == "failed"
    assert "numericPreview" not in result


@pytest.mark.parametrize("values", [[1.0, 1.0], [1e308, -1e308], [1e-300, 2e-300]])
def test_svg_coordinates_are_finite_for_flat_and_extreme_values(values: list[float]) -> None:
    preview = {
        "framesShown": 2,
        "framesChecked": 2,
        "channelIds": ["<script>alert(1)</script>"],
        "totalChannels": 1,
        "units": "<N>",
        "batches": [
            {
                "firstFrame": 0,
                "values": [[v] for v in values],
                "segment": "<capture>.mcap",
                "messageIndex": 0,
                "sessionTimeNs": "0",
                "nativeTimeNs": [],
            }
        ],
    }
    html = render_qc_html(
        {
            "streams": [
                {
                    "payloadInspection": {
                        "status": "numeric_samples_checked",
                        "numericPreview": preview,
                    }
                }
            ]
        }
    )
    assert 'points="0.000,' in html
    coords = re.search(r'points="([^"]+)"', html).group(1)
    assert all(math.isfinite(float(x)) for pair in coords.split() for x in pair.split(","))
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "&lt;capture&gt;.mcap" in html


def test_descriptor_only_report_has_no_sample_plot(tmp_path: Path) -> None:
    root = _package(tmp_path)
    _write_mcap(root, values=[1, 2], times=[3])
    html = render_qc_html(collect_qc(root).to_dict())
    assert "<svg" not in html
    assert "Recorded numeric excerpts" not in html
