# SPDX-License-Identifier: GPL-3.0-only
"""Analysis job orchestrator (Phase A QC + Phase B features/plots)."""

from __future__ import annotations

import hashlib
import json
import platform
import shutil
import sys
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from capture_session.package_reader import load_review_summary

from capture_analysis.pipeline import run_features_and_plots
from capture_analysis.qc import QcReport, collect_qc
from capture_analysis.report_html import render_qc_html
from capture_analysis.version import __version__
from capture_analysis.windows import resolve_window

ProgressFn = Callable[[str, float], None]

SCHEMA_DIR = Path(__file__).resolve().parents[4] / "schemas" / "session" / "jsonschema"


@dataclass
class JobParams:
    command: str = "qc"
    gap_policy: str = "mask"
    max_ram_bytes: int = 2 * 1024**3
    start_session_ns: int | None = None
    end_session_ns: int | None = None
    sources: list[str] = field(default_factory=list)
    apply_sync_anchors: bool = False
    overwrite_job_id: str | None = None
    checkpoint_section: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "command": self.command,
            "gapPolicy": self.gap_policy,
            "maxRamBytes": self.max_ram_bytes,
            "startSessionNs": self.start_session_ns,
            "endSessionNs": self.end_session_ns,
            "sources": list(self.sources),
            "applySyncAnchors": self.apply_sync_anchors,
            "overwriteJobId": self.overwrite_job_id,
            "checkpointSection": self.checkpoint_section,
            "extra": dict(self.extra),
        }


@dataclass
class JobResult:
    job_id: str
    job_dir: Path
    status: str
    manifest: dict[str, Any]
    qc: dict[str, Any] | None = None


def _canonical_json(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def _params_digest(params: JobParams) -> str:
    return hashlib.sha256(_canonical_json(params.to_dict())).hexdigest()


def _job_id(params: JobParams) -> str:
    if params.overwrite_job_id:
        return params.overwrite_job_id
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}_{_params_digest(params)[:8]}"


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _write_output(
    job_dir: Path,
    relative: str,
    data: bytes,
    kind: str,
    outputs: list[dict[str, Any]],
) -> Path:
    path = job_dir / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    outputs.append(
        {
            "relativePath": relative.replace("\\", "/"),
            "bytes": len(data),
            "sha256": _sha256_bytes(data),
            "kind": kind,
        }
    )
    return path


def _try_validate_manifest(manifest: dict[str, Any]) -> list[str]:
    schema_path = SCHEMA_DIR / "analysis_job.schema.json"
    if not schema_path.is_file():
        return []
    try:
        import jsonschema

        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        jsonschema.validate(manifest, schema)
    except Exception as exc:  # noqa: BLE001
        return [f"manifest schema validation: {exc}"]
    return []


def hash_sources_tree(package_root: Path) -> dict[str, str]:
    sources = package_root / "sources"
    out: dict[str, str] = {}
    if not sources.is_dir():
        return out
    for path in sorted(sources.rglob("*")):
        if path.is_file():
            out[path.relative_to(package_root).as_posix()] = _sha256_file(path)
    return out


def run(
    package_path: str | Path,
    params: JobParams | None = None,
    *,
    progress: ProgressFn | None = None,
    cancel: threading.Event | None = None,
) -> JobResult:
    params = params or JobParams()
    root = Path(package_path).resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"package not found: {root}")

    def tick(stage: str, frac: float) -> None:
        if cancel is not None and cancel.is_set():
            raise InterruptedError("analysis cancelled")
        if progress is not None:
            progress(stage, frac)

    allowed = {"qc", "features", "plots", "all", "pose", "kinematics", "ml_bundle", "eval"}
    if params.command not in allowed:
        raise NotImplementedError(
            f"command {params.command!r} not supported yet (supported: {sorted(allowed)})"
        )

    tick("start", 0.0)
    qc_dict: dict[str, Any] = {}
    summary = load_review_summary(root)
    tick("qc", 0.15)
    qc_report: QcReport = collect_qc(root)
    qc_dict = qc_report.to_dict()

    job_id = _job_id(params)
    processing = root / "processing" / "jobs"
    processing.mkdir(parents=True, exist_ok=True)
    job_dir = processing / job_id
    if job_dir.exists() and params.overwrite_job_id:
        tmp = processing / f".{job_id}.tmp"
        if tmp.exists():
            shutil.rmtree(tmp)
        tmp.mkdir(parents=True)
        work = tmp
    else:
        job_dir.mkdir(parents=True, exist_ok=False)
        work = job_dir

    outputs: list[dict[str, Any]] = []
    errors: list[str] = []
    warnings = list(qc_dict.get("warnings") or [])
    feature_tables: list[dict[str, Any]] = []
    log_lines = [
        f"capture_analysis {__version__} command={params.command}",
        f"package={root}",
        f"job_id={job_id}",
    ]

    try:
        tick("write_qc", 0.25)
        qc_bytes = json.dumps(qc_dict, indent=2, sort_keys=True).encode("utf-8")
        _write_output(work, "reports/qc.json", qc_bytes, "qc_json", outputs)
        html = render_qc_html(qc_dict).encode("utf-8")
        _write_output(work, "reports/qc.html", html, "qc_html", outputs)

        params_bytes = json.dumps(params.to_dict(), indent=2, sort_keys=True).encode("utf-8")
        _write_output(work, "params.json", params_bytes, "params", outputs)

        window = resolve_window(
            summary,
            start_ns=params.start_session_ns,
            end_ns=params.end_session_ns,
            checkpoint_section=params.checkpoint_section,
        )

        fp_extra: dict[str, Any] = {}
        do_features = params.command in ("features", "all")
        do_plots = params.command in ("plots", "all")
        # plots alone still needs series — run feature extract lightweight via pipeline
        if params.command == "plots":
            do_features = True  # compute in-memory series; tables still written (ok)

        if params.command == "pose":
            tick("pose", 0.45)
            from capture_analysis.pose.job import run_pose_job

            fp_extra = run_pose_job(
                root,
                work,
                summary,
                window=window,
                gap_policy=params.gap_policy,
                sources_filter=list(params.sources),
                outputs=outputs,
                warnings=warnings,
            )
        elif params.command == "kinematics":
            tick("kinematics", 0.45)
            from capture_analysis.kinematics.job import run_kinematics_job

            pose_job_id = str(params.extra.get("pose_job_id") or "")
            if not pose_job_id:
                raise ValueError("kinematics command requires extra.pose_job_id")
            fp_extra = run_kinematics_job(
                root,
                work,
                summary,
                pose_job_id=pose_job_id,
                outputs=outputs,
                warnings=warnings,
                imu_fusion=bool(params.extra.get("imu_fusion")),
            )
        elif params.command == "ml_bundle":
            tick("ml_bundle", 0.45)
            from capture_analysis.ml_bundle.job import run_ml_bundle_job

            kin_id = str(params.extra.get("kinematics_job_id") or "")
            feat_id = str(params.extra.get("features_job_id") or "")
            if not kin_id or not feat_id:
                raise ValueError(
                    "ml_bundle requires extra.kinematics_job_id and extra.features_job_id"
                )
            fp_extra = run_ml_bundle_job(
                root,
                work,
                summary,
                kinematics_job_id=kin_id,
                features_job_id=feat_id,
                window_sec=float(params.extra.get("window_sec") or 1.0),
                hop_sec=float(params.extra.get("hop_sec") or 0.05),
                grid_rate_hz=float(params.extra.get("grid_rate_hz") or 20.0),
                target_columns=list(params.extra.get("target_columns") or []),
                outputs=outputs,
                warnings=warnings,
            )
        elif params.command == "eval":
            tick("eval", 0.45)
            from capture_analysis.eval.job import run_eval_job

            bundle_id = str(params.extra.get("ml_bundle_job_id") or "")
            if not bundle_id:
                raise ValueError("eval command requires extra.ml_bundle_job_id")
            fp_extra = run_eval_job(
                root,
                work,
                summary,
                ml_bundle_job_id=bundle_id,
                outputs=outputs,
                warnings=warnings,
            )
        elif do_features or do_plots:
            tick("features_plots", 0.45)
            fp_extra = run_features_and_plots(
                root,
                work,
                summary,
                window,
                gap_policy=params.gap_policy,
                max_ram_bytes=params.max_ram_bytes,
                sources_filter=list(params.sources),
                do_features=do_features,
                do_plots=do_plots or params.command == "all",
                outputs=outputs,
                warnings=warnings,
                feature_tables=feature_tables,
            )

        digest = _params_digest(params)
        status = "completed_with_warnings" if warnings else "completed"
        modalities = sorted({s["modality"] for s in qc_dict["streams"] if s.get("modality")})
        sources = sorted({s["sourceId"] for s in qc_dict["streams"]})
        if params.sources:
            sources = [s for s in sources if s in params.sources]

        try:
            import matplotlib
            import numpy
            import pandas
            import scipy

            tooling_extra = {
                "numpy": numpy.__version__,
                "scipy": scipy.__version__,
                "pandas": pandas.__version__,
                "matplotlib": matplotlib.__version__,
            }
        except ImportError:
            tooling_extra = {}

        from capture_analysis.plugins.registry import get_registry

        plugin_reg = get_registry()
        manifest: dict[str, Any] = {
            "schemaId": "capture.analysis_job/1",
            "jobId": job_id,
            "createdUtc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "captureAnalysisVersion": __version__,
            "pluginManifestVersion": fp_extra.get("pluginManifestVersion")
            or plugin_reg.manifest_version,
            "pluginIds": plugin_reg.feature_ids(),
            "packagePath": str(root),
            "sessionId": qc_dict["sessionId"],
            "packageState": qc_dict["packageState"],
            "manifestSha256": qc_dict["manifestSha256"],
            "timeRange": {
                "mode": window.label,
                "startSessionNs": window.start_session_ns,
                "endSessionNs": window.end_session_ns,
                "checkpointIds": ([params.checkpoint_section] if params.checkpoint_section else []),
            },
            "sourcesSelected": sources,
            "modalities": modalities,
            "gapPolicy": params.gap_policy,
            "gapSummary": {
                "open": qc_dict["openGapCount"],
                "closed": qc_dict["closedGapCount"],
                "maskedNs": 0,
                "validFraction": None,
            },
            "analysisGrids": [],
            "syncAnchorsApplied": {
                "applied": params.apply_sync_anchors,
                "anchors": [],
            },
            "paramsDigest": digest,
            "tooling": {
                "python": sys.version.split()[0],
                "platform": platform.platform(),
                "captureAnalysis": __version__,
                **tooling_extra,
            },
            "featureTables": feature_tables,
            "poseTables": fp_extra.get("poseTables", []),
            "poseModelId": fp_extra.get("poseModelId"),
            "kinematicsRows": fp_extra.get("kinematicsRows"),
            "poseJobId": fp_extra.get("poseJobId"),
            "mlBundleWindowCount": fp_extra.get("mlBundleWindowCount"),
            "evalWindowCount": fp_extra.get("evalWindowCount"),
            "outputs": outputs,
            "warnings": warnings,
            "errors": errors,
            "status": status,
        }
        schema_warnings = _try_validate_manifest(manifest)
        warnings.extend(schema_warnings)
        manifest["warnings"] = warnings
        if schema_warnings and status == "completed":
            status = "completed_with_warnings"
            manifest["status"] = status

        tick("manifest", 0.9)
        man_path = work / "job_manifest.json"
        man_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        outputs.append(
            {
                "relativePath": "job_manifest.json",
                "bytes": man_path.stat().st_size,
                "sha256": _sha256_file(man_path),
                "kind": "manifest",
            }
        )
        manifest["outputs"] = outputs
        man_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        log_lines.append(f"status={status}")
        log_lines.append(f"feature_tables={len(feature_tables)}")
        _write_output(
            work,
            "logs/job.log",
            ("\n".join(log_lines) + "\n").encode("utf-8"),
            "log",
            outputs,
        )

        if work != job_dir:
            if job_dir.exists():
                shutil.rmtree(job_dir)
            work.rename(job_dir)

        tick("done", 1.0)
        return JobResult(
            job_id=job_id,
            job_dir=job_dir,
            status=status,
            manifest=manifest,
            qc=qc_dict,
        )
    except Exception as exc:
        errors.append(str(exc))
        log_lines.append(f"ERROR: {exc}")
        fail_manifest = {
            "schemaId": "capture.analysis_job/1",
            "jobId": job_id,
            "createdUtc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "captureAnalysisVersion": __version__,
            "packagePath": str(root),
            "sessionId": qc_dict.get("sessionId", ""),
            "status": "failed",
            "errors": errors,
            "warnings": warnings,
            "outputs": outputs,
        }
        try:
            (work / "job_manifest.json").write_text(
                json.dumps(fail_manifest, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            (work / "logs").mkdir(parents=True, exist_ok=True)
            (work / "logs" / "job.log").write_text("\n".join(log_lines) + "\n", encoding="utf-8")
            if work != job_dir and work.exists():
                if job_dir.exists():
                    shutil.rmtree(job_dir)
                work.rename(job_dir)
        except Exception:
            pass
        raise
