# SPDX-License-Identifier: GPL-3.0-only
"""Plugin manifest registry tests."""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests" / "fixtures" / "mini_session"
BUNDLED_MANIFEST = (
    ROOT / "libs" / "python" / "capture_analysis" / "capture_analysis" / "plugins" / "manifest.yaml"
)


pytest.importorskip("yaml")


def test_bundled_manifest_loads() -> None:
    from capture_analysis.plugins.registry import load_registry

    reg = load_registry(BUNDLED_MANIFEST)
    assert reg.manifest_version == "1.0.0"
    assert reg.stream_handlers
    assert "emg.envelope.v1" in reg.feature_ids()
    assert "test.dummy.feature.v1" in reg.feature_ids()


def test_dummy_extractor_via_manifest_only(tmp_path: Path) -> None:
    import numpy as np
    from capture_analysis.plugins.dummy import extract_dummy_features
    from capture_analysis.plugins.registry import load_registry
    from capture_analysis.types import GapMask, LoadedEmg, StreamRef, TimeWindow

    reg = load_registry(BUNDLED_MANIFEST)
    row = next(f for f in reg.features if f["id"] == "test.dummy.feature.v1")
    fn = reg.resolve_entry(row["entry"])
    assert fn is extract_dummy_features

    loaded = LoadedEmg(
        channel_ids=["ch0"],
        t_sample_ns=np.array([0], dtype=np.int64),
        X=np.array([[2.0]], dtype=np.float32),
        fs_hz=1.0,
        units="a.u.",
    )
    stream = StreamRef("dummy.src", "st", "dummy_test", "dummy.test/1", 1.0, "a.u.")
    window = TimeWindow(0, 1, "full")
    mask = GapMask(stream=stream, window=window, gaps=[], policy="mask")
    df, _meta, vf = fn(loaded, mask)
    assert vf == 1.0
    assert float(df.iloc[0]["mean"]) == 2.0


def test_dummy_stream_handler_writes_parquet(tmp_path: Path) -> None:
    from capture_analysis.plugins.handlers import HandlerContext
    from capture_analysis.plugins.registry import load_registry
    from capture_analysis.types import StreamRef, TimeWindow
    from capture_session.package_reader import load_review_summary

    reg = load_registry(BUNDLED_MANIFEST)
    ref = StreamRef(
        "dummy.src",
        "dummy.stream",
        "dummy_test",
        "dummy.test/1",
        1.0,
        "a.u.",
    )
    handler = reg.stream_handler_for(ref)
    assert handler is not None

    summary = load_review_summary(FIXTURE)
    work = tmp_path / "job"
    work.mkdir()
    outputs: list = []
    schema_doc = {"schemaId": "capture.analysis_feature_schema/1", "tables": {}}
    ctx = HandlerContext(
        root=FIXTURE,
        work=work,
        summary=summary,
        window=TimeWindow(0, summary.duration_ns or 1, "full"),
        gap_policy="mask",
        max_ram_bytes=2**30,
        do_features=True,
        do_plots=False,
        all_gaps=[],
        outputs=outputs,
        warnings=[],
        schema_doc=schema_doc,
        feature_tables=[],
        sync_series=[],
    )
    from capture_analysis.windows import build_gap_mask, gaps_to_intervals

    gaps = gaps_to_intervals(summary)
    gap_mask = build_gap_mask(ref, ctx.window, gaps, policy="mask")
    handler(ref, gap_mask, ctx)
    parquet = work / "features" / "dummy" / "dummy.src" / "probe.parquet"
    assert parquet.is_file()
    assert outputs


def test_pipeline_uses_registry_not_modality_elif(tmp_path: Path) -> None:
    import inspect

    from capture_analysis import pipeline

    source = inspect.getsource(pipeline.run_features_and_plots)
    assert "elif ref.modality" not in source
    assert "get_registry" in source or "registry" in source
