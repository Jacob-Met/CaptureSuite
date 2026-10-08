# SPDX-License-Identifier: GPL-3.0-only
"""Offline analysis for CaptureSuite session packages."""

from importlib import import_module
from typing import TYPE_CHECKING, Any

from capture_analysis.discover import discover_streams
from capture_analysis.qc import QcReport, collect_qc
from capture_analysis.version import __version__

if TYPE_CHECKING:
    from capture_analysis.jobs import JobParams, JobResult, hash_sources_tree, run

__all__ = [
    "__version__",
    "JobParams",
    "JobResult",
    "QcReport",
    "collect_qc",
    "discover_streams",
    "hash_sources_tree",
    "run",
]


def __getattr__(name: str) -> Any:
    """Load the existing job API only when a caller requests it."""
    if name not in ("JobParams", "JobResult", "hash_sources_tree", "run"):
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module("capture_analysis.jobs"), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
