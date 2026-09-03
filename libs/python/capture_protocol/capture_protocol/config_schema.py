# SPDX-License-Identifier: Apache-2.0
"""JSON Schema subset for source configuration (CONFIGURATION_UI.md)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SUPPORTED_TYPES = frozenset({"string", "integer", "number", "boolean", "array"})


@dataclass(frozen=True)
class FieldSpec:
    name: str
    prop: dict[str, Any]
    group: str
    order: int
    advanced: bool


@dataclass
class ValidationResult:
    ok: bool
    errors: list[str] = field(default_factory=list)
    document: dict[str, Any] = field(default_factory=dict)


def schema_revision(schema: dict[str, Any]) -> str:
    return str(schema.get("schema_revision") or "")


def iter_fields(schema: dict[str, Any]) -> list[FieldSpec]:
    props = schema.get("properties") or {}
    if not isinstance(props, dict):
        return []
    fields: list[FieldSpec] = []
    for name, prop in props.items():
        if not isinstance(prop, dict):
            continue
        group = str(prop.get("x-capture-group") or "General")
        try:
            order = int(prop.get("x-capture-order", 1000))
        except (TypeError, ValueError):
            order = 1000
        advanced = bool(prop.get("x-capture-advanced", False))
        fields.append(
            FieldSpec(
                name=name,
                prop=prop,
                group=group,
                order=order,
                advanced=advanced,
            )
        )
    fields.sort(key=lambda f: (f.group.lower(), f.order, (f.prop.get("title") or f.name).lower()))
    return fields


def group_order(fields: list[FieldSpec]) -> list[str]:
    """Group names ordered by the lowest field order in each group."""
    best: dict[str, int] = {}
    for f in fields:
        prev = best.get(f.group)
        if prev is None or f.order < prev:
            best[f.group] = f.order
    return sorted(best.keys(), key=lambda g: (best[g], g.lower()))


def defaults_from_schema(schema: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for f in iter_fields(schema):
        if "default" in f.prop:
            out[f.name] = f.prop["default"]
    return out


def merge_current(schema: dict[str, Any], current: dict[str, Any] | None) -> dict[str, Any]:
    doc = defaults_from_schema(schema)
    if isinstance(current, dict):
        for key, value in current.items():
            if key in (schema.get("properties") or {}):
                doc[key] = value
    return doc


def _type_ok(value: Any, typ: str) -> bool:
    if typ == "string":
        return isinstance(value, str)
    if typ == "boolean":
        return isinstance(value, bool)
    if typ == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if typ == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if typ == "array":
        return isinstance(value, list)
    return False


def validate_document(schema: dict[str, Any], document: dict[str, Any]) -> ValidationResult:
    if not isinstance(document, dict):
        return ValidationResult(False, ["configuration must be a JSON object"])

    props = schema.get("properties") or {}
    if not isinstance(props, dict):
        return ValidationResult(False, ["schema has no properties"])

    errors: list[str] = []
    required = schema.get("required") or []
    if isinstance(required, list):
        for name in required:
            if name not in document:
                errors.append(f"missing required field: {name}")

    for name, value in document.items():
        prop = props.get(name)
        if prop is None:
            errors.append(f"unknown field: {name}")
            continue
        if not isinstance(prop, dict):
            continue
        if prop.get("readOnly"):
            # Read-only values may be echoed; ignore for validation of apply docs
            # that only send editable fields. If present, still type-check.
            pass
        typ = prop.get("type")
        if typ and typ not in SUPPORTED_TYPES:
            errors.append(f"{name}: unsupported type {typ}")
            continue
        if typ and not _type_ok(value, typ):
            errors.append(f"{name}: expected {typ}")
            continue
        if "enum" in prop:
            enum_vals = prop["enum"]
            if isinstance(enum_vals, list) and value not in enum_vals:
                errors.append(f"{name}: value not in enum")
        if typ in ("integer", "number") and isinstance(value, (int, float)):
            if "minimum" in prop and value < prop["minimum"]:
                errors.append(f"{name}: below minimum {prop['minimum']}")
            if "maximum" in prop and value > prop["maximum"]:
                errors.append(f"{name}: above maximum {prop['maximum']}")
            if "multipleOf" in prop:
                try:
                    step = float(prop["multipleOf"])
                    if step > 0:
                        # Allow float noise for multiples.
                        ratio = float(value) / step
                        if abs(ratio - round(ratio)) > 1e-9:
                            errors.append(f"{name}: not a multiple of {step}")
                except (TypeError, ValueError, ZeroDivisionError):
                    pass
        if typ == "array" and isinstance(value, list):
            min_items = prop.get("minItems")
            max_items = prop.get("maxItems")
            if min_items is not None and len(value) < int(min_items):
                errors.append(f"{name}: fewer than minItems")
            if max_items is not None and len(value) > int(max_items):
                errors.append(f"{name}: more than maxItems")
            items = prop.get("items") or {}
            item_type = items.get("type") if isinstance(items, dict) else None
            if item_type:
                for i, item in enumerate(value):
                    if not _type_ok(item, item_type):
                        errors.append(f"{name}[{i}]: expected {item_type}")

    return ValidationResult(ok=not errors, errors=errors, document=dict(document))


def dirty_summary(
    schema: dict[str, Any],
    baseline: dict[str, Any],
    current: dict[str, Any],
) -> tuple[list[str], bool]:
    """Return changed field titles and whether any require restart."""
    props = schema.get("properties") or {}
    changed: list[str] = []
    restart = False
    for name, value in current.items():
        if baseline.get(name) == value:
            continue
        prop = props.get(name) if isinstance(props, dict) else None
        title = name
        if isinstance(prop, dict):
            title = str(prop.get("title") or name)
            if prop.get("x-capture-restart-required"):
                restart = True
        changed.append(title)
    return changed, restart


@dataclass
class PresetMatchResult:
    ok: bool
    errors: list[str] = field(default_factory=list)
    document: dict[str, Any] = field(default_factory=dict)


def match_preset_to_schema(
    schema: dict[str, Any],
    preset_content: dict[str, Any],
) -> PresetMatchResult:
    """Validate a stored device preset against the device's *current* schema.

    On mismatch, apply nothing — dropping unknown fields silently is forbidden
    by CONFIGURATION_UI.md.
    """
    errors: list[str] = []
    revision = str(preset_content.get("schema_revision") or "")
    current_rev = schema_revision(schema)
    if revision and current_rev and revision != current_rev:
        errors.append(
            f"schema revision mismatch: preset={revision}, device={current_rev}"
        )

    configuration = preset_content.get("configuration")
    if configuration is None and isinstance(preset_content.get("document"), dict):
        configuration = preset_content["document"]
    if not isinstance(configuration, dict):
        return PresetMatchResult(False, ["preset missing configuration object"])

    props = schema.get("properties") or {}
    if not isinstance(props, dict):
        return PresetMatchResult(False, ["device schema has no properties"])

    unknown = [k for k in configuration if k not in props]
    if unknown:
        errors.append("unknown fields: " + ", ".join(sorted(unknown)))

    validated = validate_document(schema, configuration)
    if not validated.ok:
        errors.extend(validated.errors)

    return PresetMatchResult(
        ok=not errors, errors=errors, document=dict(configuration)
    )
