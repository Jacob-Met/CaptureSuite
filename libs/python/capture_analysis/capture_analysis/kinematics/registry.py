# SPDX-License-Identifier: GPL-3.0-only
"""Kinematics column registry loader."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

REGISTRY_PATH = (
    Path(__file__).resolve().parents[5]
    / "schemas"
    / "kinematics"
    / "kinematics_columns.registry.json"
)


@lru_cache(maxsize=1)
def load_registry() -> dict[str, Any]:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def column_names(*, tiers: tuple[str, ...] | None = None) -> list[str]:
    reg = load_registry()
    cols = reg.get("columns") or []
    if tiers is None:
        return [str(c["name"]) for c in cols]
    return [str(c["name"]) for c in cols if c.get("tier") in tiers]


def tier_a_angle_columns() -> list[str]:
    return [
        n
        for n in column_names(tiers=("A",))
        if n.startswith("theta_") or n.startswith("omega_")
    ]


def validate_parquet_columns(df_columns: list[str]) -> list[str]:
    """Return missing required registry column names."""
    required = column_names()
    have = set(df_columns)
    return [n for n in required if n not in have]
