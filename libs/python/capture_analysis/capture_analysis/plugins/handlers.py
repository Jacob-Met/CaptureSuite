# SPDX-License-Identifier: GPL-3.0-only
"""Stream handlers invoked by the manifest-driven feature/plot pipeline."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from capture_session.package_reader import ReviewSummary

from capture_analysis.features.emg import extract_emg_features
from capture_analysis.features.imu import extract_imu_features
from capture_analysis.features.io import write_feature_table
from capture_analysis.features.radar_doppler import extract_radar_doppler_features
from capture_analysis.features.radar_frame import extract_radar_frame_features
from capture_analysis.features.video_qc import extract_video_qc
from capture_analysis.loaders.emg import load_emg
from capture_analysis.loaders.imu import load_imu
from capture_analysis.loaders.video import load_video_timing
from capture_analysis.plots.modality import plot_emg_channels, plot_imu_accel, plot_series
from capture_analysis.types import GapMask, StreamRef, TimeWindow


def _hash_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


@dataclass
class HandlerContext:
    root: Path
    work: Path
    summary: ReviewSummary
    window: TimeWindow
    gap_policy: str
    max_ram_bytes: int
    do_features: bool
    do_plots: bool
    all_gaps: list
    outputs: list[dict[str, Any]]
    warnings: list[str]
    schema_doc: dict[str, Any]
    feature_tables: list[dict[str, Any]]
    sync_series: list[dict[str, Any]]
    valid_fractions: dict[str, float] = field(default_factory=dict)


def handle_emg(ref: StreamRef, gap_mask: GapMask, ctx: HandlerContext) -> None:
    loaded = load_emg(ref, ctx.window, max_ram_bytes=ctx.max_ram_bytes)
    if ctx.do_features:
        df, meta, vf = extract_emg_features(loaded, gap_mask)
        ctx.valid_fractions[ref.source_id] = vf
        if not df.empty:
            rel = f"features/emg/{ref.source_id}/windows.parquet"
            write_feature_table(
                ctx.work,
                rel,
                df,
                feature_schema_version=1,
                columns_meta=meta,
                schema_doc=ctx.schema_doc,
                outputs=ctx.outputs,
            )
            ctx.feature_tables.append(
                {"relativePath": rel, "featureSchemaVersion": 1, "rows": int(len(df))}
            )
    if ctx.do_plots and loaded.X.size:
        path = ctx.work / "figures" / f"emg_{ref.source_id}_channels.png"
        plot_emg_channels(path, loaded, window=ctx.window, gaps=ctx.all_gaps)
        ctx.outputs.append(
            {
                "relativePath": path.relative_to(ctx.work).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": _hash_file(path),
                "kind": "figure",
            }
        )
        ch0 = loaded.X[0].astype(np.float64)
        step = max(1, int(loaded.fs_hz // 20))
        env = np.sqrt(np.convolve(ch0 * ch0, np.ones(step) / step, mode="same"))
        ctx.sync_series.append(
            {
                "label": f"EMG {ref.source_id[:16]}",
                "t_ns": loaded.t_sample_ns[::step],
                "y": env[::step],
                "color": "#35c46b",
            }
        )


def handle_imu(ref: StreamRef, gap_mask: GapMask, ctx: HandlerContext) -> None:
    loaded = load_imu(ref, ctx.window, max_ram_bytes=ctx.max_ram_bytes)
    if ctx.do_features:
        df, meta, vf = extract_imu_features(
            loaded, gap_mask, nominal_rate_hz=ref.nominal_rate_hz or 60.0
        )
        ctx.valid_fractions[ref.source_id] = vf
        if not df.empty:
            rel = f"features/imu/{ref.source_id}/windows.parquet"
            write_feature_table(
                ctx.work,
                rel,
                df,
                feature_schema_version=1,
                columns_meta=meta,
                schema_doc=ctx.schema_doc,
                outputs=ctx.outputs,
            )
            ctx.feature_tables.append(
                {"relativePath": rel, "featureSchemaVersion": 1, "rows": int(len(df))}
            )
    if ctx.do_plots and loaded.t_frame_ns.size:
        path = ctx.work / "figures" / f"imu_{ref.source_id}_accel.png"
        plot_imu_accel(path, loaded, window=ctx.window, gaps=ctx.all_gaps)
        ctx.outputs.append(
            {
                "relativePath": path.relative_to(ctx.work).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": _hash_file(path),
                "kind": "figure",
            }
        )
        mag = np.linalg.norm(loaded.accel[:, 0], axis=1)
        ctx.sync_series.append(
            {
                "label": f"IMU {ref.source_id[:16]}",
                "t_ns": loaded.t_frame_ns,
                "y": mag,
                "color": "#3d8bfd",
            }
        )


def handle_radar(ref: StreamRef, gap_mask: GapMask, ctx: HandlerContext) -> None:
    derived = ctx.work / "derived" / "radar" / ref.source_id if ctx.do_features else None
    df, meta, vf, warns = extract_radar_frame_features(
        ref, ctx.window, gap_mask, derived_dir=derived
    )
    ctx.warnings.extend(warns)
    ctx.valid_fractions[ref.source_id] = vf
    if ctx.do_features and not df.empty:
        rel = f"features/radar/{ref.source_id}/frame_features.parquet"
        write_feature_table(
            ctx.work,
            rel,
            df,
            feature_schema_version=1,
            columns_meta=meta,
            schema_doc=ctx.schema_doc,
            outputs=ctx.outputs,
        )
        ctx.feature_tables.append(
            {"relativePath": rel, "featureSchemaVersion": 1, "rows": int(len(df))}
        )
        if derived and derived.is_dir():
            for npy in sorted(derived.glob("*.npy")):
                ctx.outputs.append(
                    {
                        "relativePath": npy.relative_to(ctx.work).as_posix(),
                        "bytes": npy.stat().st_size,
                        "sha256": _hash_file(npy),
                        "kind": "derived_npy",
                    }
                )
    if ctx.do_plots and not df.empty:
        path = ctx.work / "figures" / f"radar_{ref.source_id}_energy.png"
        plot_series(
            path,
            df["t_ns"].to_numpy(),
            df["energy"].to_numpy(),
            window=ctx.window,
            gaps=ctx.all_gaps,
            ylabel="energy",
            title=f"Radar energy · {ref.source_id} (ADC counts)",
            color="#f0a13a",
        )
        ctx.outputs.append(
            {
                "relativePath": path.relative_to(ctx.work).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": _hash_file(path),
                "kind": "figure",
            }
        )
        ctx.sync_series.append(
            {
                "label": f"Radar {ref.source_id[:16]}",
                "t_ns": df["t_ns"].to_numpy(),
                "y": df["energy"].to_numpy(),
                "color": "#f0a13a",
            }
        )


def handle_radar_doppler(ref: StreamRef, gap_mask: GapMask, ctx: HandlerContext) -> None:
    df, meta, vf, warns = extract_radar_doppler_features(ref, ctx.window, gap_mask)
    ctx.warnings.extend(warns)
    ctx.valid_fractions[ref.source_id] = vf
    if ctx.do_features and not df.empty:
        rel = f"features/radar_doppler/{ref.source_id}/frame_features.parquet"
        write_feature_table(
            ctx.work,
            rel,
            df,
            feature_schema_version=1,
            columns_meta=meta,
            schema_doc=ctx.schema_doc,
            outputs=ctx.outputs,
        )
        ctx.feature_tables.append(
            {"relativePath": rel, "featureSchemaVersion": 1, "rows": int(len(df))}
        )
    if ctx.do_plots and not df.empty:
        path = ctx.work / "figures" / f"doppler_{ref.source_id}_mag.png"
        plot_series(
            path,
            df["t_ns"].to_numpy(),
            df["mag_mean"].to_numpy(),
            window=ctx.window,
            gaps=ctx.all_gaps,
            ylabel="|z| mean",
            title=f"Doppler magnitude · {ref.source_id}",
            color="#e5484d",
        )
        ctx.outputs.append(
            {
                "relativePath": path.relative_to(ctx.work).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": _hash_file(path),
                "kind": "figure",
            }
        )
        ctx.sync_series.append(
            {
                "label": f"Doppler {ref.source_id[:16]}",
                "t_ns": df["t_ns"].to_numpy(),
                "y": df["mag_mean"].to_numpy(),
                "color": "#e5484d",
            }
        )


def handle_video(ref: StreamRef, gap_mask: GapMask, ctx: HandlerContext) -> None:
    loaded = load_video_timing(ref, ctx.window)
    if ctx.do_features:
        df, meta, vf, warns = extract_video_qc(
            loaded, gap_mask, nominal_rate_hz=ref.nominal_rate_hz or 30.0
        )
        ctx.warnings.extend(warns)
        ctx.valid_fractions[ref.source_id] = vf
        if not df.empty:
            rel = f"features/video/{ref.source_id}/timing_qc.parquet"
            write_feature_table(
                ctx.work,
                rel,
                df,
                feature_schema_version=1,
                columns_meta=meta,
                schema_doc=ctx.schema_doc,
                outputs=ctx.outputs,
            )
            ctx.feature_tables.append(
                {"relativePath": rel, "featureSchemaVersion": 1, "rows": int(len(df))}
            )
    if ctx.do_plots and loaded.t_frame_ns.size >= 2:
        dt = np.diff(loaded.t_frame_ns.astype(np.float64)) / 1e9
        fps = np.where(dt > 0, 1.0 / dt, np.nan)
        path = ctx.work / "figures" / f"video_{ref.source_id}_fps.png"
        plot_series(
            path,
            loaded.t_frame_ns[1:],
            fps,
            window=ctx.window,
            gaps=ctx.all_gaps,
            ylabel="fps",
            title=f"Video FPS · {ref.source_id}",
            color="#888888",
        )
        ctx.outputs.append(
            {
                "relativePath": path.relative_to(ctx.work).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": _hash_file(path),
                "kind": "figure",
            }
        )
        ctx.sync_series.append(
            {
                "label": f"Video {ref.source_id[:16]}",
                "t_ns": loaded.t_frame_ns[1:],
                "y": fps,
                "color": "#888888",
            }
        )
