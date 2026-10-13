# SPDX-License-Identifier: GPL-3.0-only
"""Validate the rate before unchanged loader admission or segment iteration."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import numpy as np
import pytest
from capture_analysis.loaders import emg, imu, numeric_batch
from capture_analysis.loaders.base import estimate_emg_bytes, estimate_imu_bytes
from capture_analysis.types import StreamRef, TimeWindow


def _ref(rate):
    return StreamRef("source.分析", "stream.rate", "emg", "emg.batch/1", rate, "mV")


def _loader_ref(module, rate):
    modality, schema = {
        emg: ("emg", "emg.batch/1"),
        imu: ("imu", "imu.frame/1"),
        numeric_batch: ("numeric", "generic.numeric_batch/1"),
    }[module]
    return replace(_ref(rate), modality=modality, data_schema_id=schema)


@pytest.mark.parametrize(
    "rate",
    [
        1,
        0.25,
        1000.0,
        np.float32(60),
        np.float64(2000),
        np.nextafter(0.0, 1.0),
        np.finfo(np.float64).max,
        10**400,
        Decimal("1e1000"),
    ],
)
def test_finite_positive_rates_return_the_original_value(rate):
    assert _ref(rate).require_rate() is rate


@pytest.mark.parametrize("rate", [0, -0.0, -1.0, float("-inf")])
def test_nonpositive_rate_refusal_keeps_its_existing_message(rate):
    with pytest.raises(ValueError) as caught:
        _ref(rate).require_rate()
    assert str(caught.value) == (
        "stream source.分析/stream.rate missing nominal_rate_hz (refusing to invent a timebase)"
    )


@pytest.mark.parametrize("rate", [float("nan"), float("inf"), np.float32("nan"), np.float64("inf")])
def test_nonfinite_rate_names_the_stream_and_refuses_a_replacement(rate):
    with pytest.raises(ValueError, match="source.分析/stream.rate.*non-finite nominal_rate_hz"):
        _ref(rate).require_rate()


@pytest.mark.parametrize("estimate", [estimate_emg_bytes, estimate_imu_bytes])
@pytest.mark.parametrize("rate", [float("nan"), float("inf")])
def test_memory_admission_reports_invalid_rate_before_integer_conversion(estimate, rate):
    with pytest.raises(ValueError, match="source.分析/stream.rate.*non-finite nominal_rate_hz"):
        estimate(_ref(rate), TimeWindow(0, 1_000_000_000))


@pytest.mark.parametrize("module", [emg, imu, numeric_batch])
@pytest.mark.parametrize("rate", [float("nan"), float("inf")])
def test_loaders_refuse_nonfinite_rate_before_reading_a_segment(module, rate, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("segment iteration happened after invalid rate admission")

    monkeypatch.setattr(module, "iter_mcap_messages", forbidden)
    load = getattr(module, "load_" + module.__name__.rsplit(".", 1)[-1])
    with pytest.raises(ValueError, match="source.分析/stream.rate.*non-finite nominal_rate_hz"):
        load(_loader_ref(module, rate), TimeWindow(0, 1_000_000_000), max_ram_bytes=8 * 1024**2)


@pytest.mark.parametrize("module", [emg, imu, numeric_batch])
def test_valid_rate_keeps_typed_empty_loader_results(module, monkeypatch):
    monkeypatch.setattr(module, "iter_mcap_messages", lambda *args, **kwargs: iter(()))
    load = getattr(module, "load_" + module.__name__.rsplit(".", 1)[-1])
    loaded = load(
        _loader_ref(module, 1000.0), TimeWindow(0, 1_000_000_000), max_ram_bytes=8 * 1024**2
    )
    times = loaded.t_frame_ns if module is imu else loaded.t_sample_ns
    data = loaded.accel if module is imu else loaded.X
    assert times.shape == (0,) and times.dtype == np.int64
    expected_dtype = np.float64 if module is numeric_batch else np.float32
    assert data.size == 0 and data.dtype == expected_dtype
