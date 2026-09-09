# SPDX-License-Identifier: GPL-3.0-only
"""Load and resolve analysis plugins from YAML manifest."""

from __future__ import annotations

import importlib
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from capture_analysis.types import StreamRef

PLUGIN_DIR = Path(__file__).resolve().parent
DEFAULT_MANIFEST = PLUGIN_DIR / "manifest.yaml"
SCHEMA_PATH = (
    Path(__file__).resolve().parents[5]
    / "docs"
    / "design"
    / "research"
    / "schemas"
    / "analysis_plugin_manifest.schema.json"
)

StreamHandlerFn = Callable[..., None]


@dataclass(frozen=True)
class StreamHandlerSpec:
    id: str
    modality: str
    entry: str
    requires_mcap: bool = False


@dataclass
class PluginRegistry:
    manifest_version: str
    stream_handlers: list[StreamHandlerSpec] = field(default_factory=list)
    loaders: list[dict[str, Any]] = field(default_factory=list)
    features: list[dict[str, Any]] = field(default_factory=list)
    plots: list[dict[str, Any]] = field(default_factory=list)
    jobs: list[dict[str, Any]] = field(default_factory=list)
    manifest_path: Path = DEFAULT_MANIFEST
    _handler_cache: dict[str, StreamHandlerFn] = field(default_factory=dict, repr=False)

    def resolve_entry(self, entry: str) -> Any:
        if entry in self._handler_cache:
            return self._handler_cache[entry]
        module_name, _, attr = entry.partition(":")
        if not module_name or not attr:
            raise ValueError(f"invalid plugin entry (want module:function): {entry!r}")
        mod = importlib.import_module(module_name)
        fn = getattr(mod, attr)
        self._handler_cache[entry] = fn
        return fn

    def stream_handler_for(self, ref: StreamRef) -> StreamHandlerFn | None:
        for spec in self.stream_handlers:
            if spec.modality != ref.modality:
                continue
            if spec.requires_mcap and not ref.mcap_paths:
                continue
            return self.resolve_entry(spec.entry)
        return None

    def feature_ids(self) -> list[str]:
        return [str(row["id"]) for row in self.features if row.get("id")]

    def loader_for_schema(self, schema_id: str) -> dict[str, Any] | None:
        for row in self.loaders:
            if row.get("schemaId") == schema_id:
                return row
        return None


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "PyYAML is required to load analysis plugin manifests "
            "(pip install pyyaml or capture-analysis[analysis])"
        ) from exc
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"manifest must be a mapping: {path}")
    return raw


def _parse_stream_handlers(raw: dict[str, Any]) -> list[StreamHandlerSpec]:
    out: list[StreamHandlerSpec] = []
    for row in raw.get("streamHandlers") or []:
        if not isinstance(row, dict):
            continue
        out.append(
            StreamHandlerSpec(
                id=str(row["id"]),
                modality=str(row["modality"]),
                entry=str(row["entry"]),
                requires_mcap=bool(row.get("requiresMcap", False)),
            )
        )
    return out


def _validate_manifest(doc: dict[str, Any]) -> list[str]:
    if not SCHEMA_PATH.is_file():
        return []
    try:
        import jsonschema
    except ImportError:
        return []
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    base = {k: doc.get(k) for k in ("manifestVersion", "loaders", "features", "plots", "jobs")}
    try:
        jsonschema.validate(base, schema)
    except Exception as exc:  # noqa: BLE001
        return [str(exc)]
    return []


def load_registry(path: Path | None = None) -> PluginRegistry:
    manifest_path = path or DEFAULT_MANIFEST
    doc = _load_yaml(manifest_path)
    warnings = _validate_manifest(doc)
    if warnings:
        raise ValueError(f"invalid plugin manifest {manifest_path}: {'; '.join(warnings)}")
    return PluginRegistry(
        manifest_version=str(doc.get("manifestVersion") or "0"),
        stream_handlers=_parse_stream_handlers(doc),
        loaders=list(doc.get("loaders") or []),
        features=list(doc.get("features") or []),
        plots=list(doc.get("plots") or []),
        jobs=list(doc.get("jobs") or []),
        manifest_path=manifest_path,
    )


@lru_cache(maxsize=4)
def get_registry(manifest_path: str | None = None) -> PluginRegistry:
    path = Path(manifest_path) if manifest_path else DEFAULT_MANIFEST
    return load_registry(path)


def reset_registry_cache() -> None:
    get_registry.cache_clear()
