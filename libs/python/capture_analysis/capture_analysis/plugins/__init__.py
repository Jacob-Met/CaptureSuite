# SPDX-License-Identifier: GPL-3.0-only
"""Analysis plugin package."""

from capture_analysis.plugins.registry import PluginRegistry, get_registry, load_registry

__all__ = ["PluginRegistry", "get_registry", "load_registry"]
