# SPDX-License-Identifier: GPL-3.0-only
"""Compare complete saved QC values without reopening either session package."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import stat
import sys
from collections.abc import Iterator
from typing import Any

MAX_INPUT_BYTES = 2 * 1024 * 1024
MAX_DEPTH = 64
MAX_NODES = 50_000
MAX_OUTPUT_BYTES = 16 * 1024 * 1024
_MISSING = object()


class ComparisonError(ValueError):
    """A saved report or complete comparison cannot be admitted."""


def _object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ComparisonError("duplicate object key: " + repr(key))
        result[key] = value
    return result


def _nonfinite(token: str) -> None:
    raise ComparisonError("nonfinite JSON number: " + token)


def _check_tree(document: Any) -> None:
    stack = [(document, 1)]
    nodes = 0
    while stack:
        value, depth = stack.pop()
        nodes += 1
        if nodes > MAX_NODES:
            raise ComparisonError("report exceeds 50000 value nodes")
        if type(value) is float and not math.isfinite(value):
            raise ComparisonError("nonfinite parsed number")
        if type(value) in (dict, list):
            if depth > MAX_DEPTH:
                raise ComparisonError("report exceeds 64 nested containers")
            children = value.values() if type(value) is dict else value
            stack.extend((v, depth + 1) for v in children)


def _fields(record: Any, specification: dict[str, tuple[type, ...]], label: str) -> None:
    if type(record) is not dict:
        raise ComparisonError(label + " must be an object")
    for key, types in specification.items():
        if key not in record or type(record[key]) not in types:
            expected = "/".join(t.__name__ for t in types)
            raise ComparisonError(f"{label}.{key} is required with type {expected}")


def _strings(value: Any, label: str) -> None:
    if type(value) is not list or any(type(v) is not str for v in value):
        raise ComparisonError(label + " must be a list of strings")


def _admit(raw: bytes) -> dict[str, Any]:
    if type(raw) is not bytes:
        raise ComparisonError("input must be captured bytes")
    if len(raw) > MAX_INPUT_BYTES:
        raise ComparisonError("input exceeds 2 MiB")
    try:
        document = json.loads(
            raw.decode("utf-8"), object_pairs_hook=_object, parse_constant=_nonfinite
        )
    except (UnicodeError, ValueError, RecursionError) as error:
        raise ComparisonError("invalid UTF-8 JSON: " + str(error)) from error
    _check_tree(document)
    report_fields = {
        k: (str,)
        for k in ("schemaId", "packagePath", "sessionId", "packageState", "manifestSha256")
    }
    report_fields.update(
        {
            k: (int,)
            for k in (
                "durationNs",
                "sourceCount",
                "streamCount",
                "openGapCount",
                "closedGapCount",
                "checkpointCount",
                "annotationCount",
                "syncAnchorCount",
                "integrityFileCount",
            )
        }
    )
    report_fields.update({k: (list,) for k in ("recoveryReports", "streams", "warnings")})
    report_fields["trafficLights"] = (dict,)
    _fields(document, report_fields, "report")
    if document["schemaId"] not in ("capture.analysis_qc/1", "capture.analysis_qc/2"):
        raise ComparisonError("unsupported QC schema")
    _strings(document["recoveryReports"], "report.recoveryReports")
    _strings(document["warnings"], "report.warnings")
    if any(type(v) is not str for v in document["trafficLights"].values()):
        raise ComparisonError("trafficLights values must be strings")
    stream_fields = {
        k: (str,) for k in ("sourceId", "streamId", "modality", "dataSchemaId", "units")
    }
    stream_fields.update({k: (int,) for k in ("mcapSegments", "mkvSegments", "timingSegments")})
    stream_fields.update(nominalRateHz=(int, float), rateOk=(bool,), warnings=(list,))
    for index, stream in enumerate(document["streams"]):
        _fields(stream, stream_fields, f"streams[{index}]")
        _strings(stream["warnings"], f"streams[{index}].warnings")
    if document["schemaId"] == "capture.analysis_qc/2" or "gaps" in document:
        _fields(document, {"gaps": (list,)}, "report")
        gap_fields = {
            k: (str,)
            for k in (
                "sourceId",
                "streamId",
                "cause",
                "startSessionTimeNs",
                "estimatedLostCount",
                "durationStatus",
            )
        }
        gap_fields.update(
            endSessionTimeNs=(str, type(None)), durationNs=(str, type(None)), closed=(bool,)
        )
        for index, gap in enumerate(document["gaps"]):
            _fields(gap, gap_fields, f"gaps[{index}]")
    return document


def _pointer(parent: str, key: str) -> str:
    return parent + "/" + key.replace("~", "~0").replace("/", "~1")


def _side(value: Any) -> dict[str, Any]:
    return {"present": value is not _MISSING, "value": None if value is _MISSING else value}


def _differences(first: Any, second: Any, pointer: str = "") -> Iterator[dict[str, Any]]:
    if type(first) is type(second) and type(first) is dict:
        for key in sorted(first.keys() | second.keys()):
            yield from _differences(
                first.get(key, _MISSING), second.get(key, _MISSING), _pointer(pointer, key)
            )
        return
    if type(first) is type(second) and type(first) is list:
        for index in range(max(len(first), len(second))):
            yield from _differences(
                first[index] if index < len(first) else _MISSING,
                second[index] if index < len(second) else _MISSING,
                _pointer(pointer, str(index)),
            )
        return
    equal = type(first) is type(second) and first == second
    if equal and type(first) is float and first == 0.0:
        equal = math.copysign(1.0, first) == math.copysign(1.0, second)
    if not equal:
        yield {"pointer": pointer, "before": _side(first), "after": _side(second)}


def _json(value: Any) -> str:
    return json.dumps(
        value, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":")
    )


def _bounded(text: str) -> str:
    # Both renderers produce ASCII, so characters and output bytes have equal size.
    if len(text) > MAX_OUTPUT_BYTES:
        raise ComparisonError("complete comparison exceeds 16 MiB")
    return text


def compare_bytes(first: bytes, second: bytes) -> dict[str, Any]:
    """Admit both complete captures and compare their literal, typed parsed values."""
    a, b = _admit(first), _admit(second)
    rows: list[dict[str, Any]] = []
    report = {
        "schemaId": "capture.saved_qc_comparison/1",
        "scope": "saved_report_values_only",
        "equal": True,
        "first": {"bytes": len(first), "sha256": hashlib.sha256(first).hexdigest(), "document": a},
        "second": {
            "bytes": len(second),
            "sha256": hashlib.sha256(second).hexdigest(),
            "document": b,
        },
        "differences": rows,
    }
    # Charge full captured documents and each row before retaining that row.
    # This bounds repeated long paths/subtrees as well as the final serialization.
    size = len(_bounded(_json(report) + "\n"))
    for row in _differences(a, b):
        # The first row also changes true to false; later rows add a comma.
        size += len(_json(row)) + 1
        if size > MAX_OUTPUT_BYTES:
            raise ComparisonError("complete comparison exceeds 16 MiB")
        rows.append(row)
    rows.sort(key=lambda row: row["pointer"])
    report["equal"] = not rows
    return report


def _read(path: str) -> bytes:
    descriptor = os.open(
        path, os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_BINARY", 0)
    )
    with os.fdopen(descriptor, "rb") as source:
        info = os.fstat(source.fileno())
        if not stat.S_ISREG(info.st_mode):
            raise ComparisonError("input must be a regular file: " + path)
        if info.st_size > MAX_INPUT_BYTES:
            raise ComparisonError("input exceeds 2 MiB: " + path)
        raw = source.read(MAX_INPUT_BYTES + 1)
        if len(raw) > MAX_INPUT_BYTES:
            raise ComparisonError("input exceeds 2 MiB: " + path)
        return raw


def _human(report: dict[str, Any]) -> str:
    lines = [
        "Saved QC comparison: " + ("equal" if report["equal"] else "different"),
        "Scope: saved report values only; recorded observations are not independently verified.",
    ]
    for role in ("first", "second"):
        capture = report[role]
        document = capture["document"]
        lines.extend(
            [
                f"{role}: sha256={capture['sha256']} bytes={capture['bytes']}",
                "  sessionId=" + _json(document["sessionId"]),
                "  packagePath=" + _json(document["packagePath"]),
            ]
        )
    lines.append(f"Differences: {len(report['differences'])}")
    for row in report["differences"]:
        before = _json(row["before"]["value"]) if row["before"]["present"] else "<absent>"
        after = _json(row["after"]["value"]) if row["after"]["present"] else "<absent>"
        lines.append(_json(row["pointer"]) + ": " + before + " -> " + after)
    return _bounded("\n".join(lines) + "\n")


def _discard_stdout() -> None:
    """Prevent buffered output from failing a second time during shutdown."""
    try:
        with open(os.devnull, "wb") as sink:
            os.dup2(sink.fileno(), sys.stdout.fileno())
    except (OSError, ValueError):
        try:
            sys.stdout.close()
        except (OSError, ValueError):
            pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("first", help="First saved QC JSON file")
    parser.add_argument("second", help="Second saved QC JSON file")
    parser.add_argument(
        "--json", action="store_true", help="Emit full captures and literal differences"
    )
    args = parser.parse_args(argv)
    writing_output = False
    try:
        report = compare_bytes(_read(args.first), _read(args.second))
        output = _bounded(_json(report) + "\n") if args.json else _human(report)
        writing_output = True
        sys.stdout.write(output)
        sys.stdout.flush()
    except BrokenPipeError:
        _discard_stdout()
        return 2
    except (OSError, ValueError, RecursionError) as error:
        if writing_output:
            _discard_stdout()
        try:
            print("error: " + _json(str(error)), file=sys.stderr)
        except OSError:
            pass
        return 2
    return 0 if report["equal"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
