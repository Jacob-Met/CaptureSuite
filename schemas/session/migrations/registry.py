# SPDX-License-Identifier: Apache-2.0
"""Session schema migration registry. Steps land with Milestone 3."""

from __future__ import annotations

# version -> ordered list of upgrade callables (package_path) -> None
MIGRATIONS: dict[str, list] = {
    "1.0.0": [],
}


def latest_version() -> str:
    return "1.0.0"
