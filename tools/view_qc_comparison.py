# SPDX-License-Identifier: GPL-3.0-only
"""Create an offline review of two complete saved QC reports."""

from __future__ import annotations

import argparse
import base64
import json
import os
import stat
import sys
import tempfile
from pathlib import Path
from typing import Any

_saved_bytecode_policy = sys.dont_write_bytecode
try:
    sys.dont_write_bytecode = True
    from compare_qc_reports import MAX_INPUT_BYTES, ComparisonError, compare_bytes
finally:
    sys.dont_write_bytecode = _saved_bytecode_policy
    del _saved_bytecode_policy

MAX_HTML_BYTES = 64 * 1024 * 1024
MAX_NAME_CHARS = 4096
TEMPLATE = Path(__file__).with_name("qc_comparison.html")


def _literal(value: Any) -> str:
    return json.dumps(
        value, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":")
    )


def _side(side: dict[str, Any]) -> dict[str, Any]:
    if not side["present"]:
        return {"present": False, "type": "absent", "text": "(absent)"}
    value = side["value"]
    kind = {
        type(None): "null", bool: "boolean", int: "integer", float: "float",
        str: "string", list: "array", dict: "object",
    }[type(value)]
    return {"present": True, "type": kind, "text": _literal(value)}


def _capture(path: Path) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_BINARY", 0)
    descriptor = os.open(path, flags)
    with os.fdopen(descriptor, "rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ComparisonError("selected input must be a regular file: " + str(path))
        raw = stream.read(MAX_INPUT_BYTES + 1)
    if len(raw) > MAX_INPUT_BYTES:
        raise ComparisonError("selected input exceeds 2 MiB: " + str(path))
    return raw


def render_comparison_html(
    first: bytes,
    second: bytes,
    *,
    first_name: str = "first-qc.json",
    second_name: str = "second-qc.json",
) -> str:
    """Admit both captures and format report values before browser presentation."""
    report = compare_bytes(first, second)
    for name in (first_name, second_name):
        if type(name) is not str or len(name) > MAX_NAME_CHARS:
            raise ComparisonError("each report name must be a string of at most 4096 characters")
    rows = []
    for index, row in enumerate(report["differences"]):
        kind = (
            "added" if not row["before"]["present"]
            else "removed" if not row["after"]["present"]
            else "changed"
        )
        rows.append({
            "index": index, "pointer": row["pointer"], "kind": kind,
            "before": _side(row["before"]), "after": _side(row["after"]),
        })
    captures = {}
    for role, raw, name in (("first", first, first_name), ("second", second, second_name)):
        capture = report[role]
        captures[role] = {
            "name": _literal(name),
            "session": _literal(capture["document"]["sessionId"]),
            "package": _literal(capture["document"]["packagePath"]),
            "bytes": str(capture["bytes"]),
            "sha256": capture["sha256"],
            "downloadName": name,
            "base64": base64.b64encode(raw).decode("ascii"),
        }
    model = {
        "schemaId": "capture.saved_qc_comparison_view/1",
        "equal": report["equal"], "captures": captures, "rows": rows,
        "comparisonBase64": base64.b64encode(
            (_literal(report) + "\n").encode("ascii")
        ).decode("ascii"),
    }
    encoded = base64.b64encode(_literal(model).encode("ascii")).decode("ascii")
    template = TEMPLATE.read_text(encoding="utf-8")
    marker = "@@DATA_BASE64@@"
    if template.count(marker) != 1:
        raise ComparisonError("the adjacent HTML template must contain exactly one data marker")
    result = template.replace(marker, encoded)
    if len(result.encode("utf-8")) > MAX_HTML_BYTES:
        raise ComparisonError("complete HTML report exceeds 64 MiB")
    return result


def _publish_new(destination: Path, raw: bytes) -> None:
    """Stage a complete body, then exclusively link it to the requested name."""
    destination = destination.absolute()
    stage = None
    published = False
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", prefix=".qc-review-", suffix=".tmp",
            dir=destination.parent, delete=False,
        ) as handle:
            stage = Path(handle.name)
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(stage, destination)
        published = True
    finally:
        if stage is not None:
            try:
                stage.unlink()
            except OSError as error:
                state = (
                    "complete output was published; temporary cleanup failed"
                    if published else "output was not published; temporary cleanup failed"
                )
                raise OSError(state + ": " + str(stage)) from error


def _diagnose(error: BaseException) -> None:
    stream = sys.stderr
    if stream is None:
        return
    try:
        stream.write("QC comparison view failed: " + _literal(str(error)) + "\n")
        stream.flush()
    except (OSError, UnicodeError, ValueError):
        try:
            with open(os.devnull, "wb") as sink:
                os.dup2(sink.fileno(), stream.fileno())
        except (OSError, ValueError, AttributeError):
            try:
                stream.close()
            except (OSError, ValueError):
                pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("first", type=Path, help="first saved QC JSON")
    parser.add_argument("second", type=Path, help="second saved QC JSON")
    parser.add_argument("--output", type=Path, required=True, help="new offline HTML file")
    args = parser.parse_args(argv)
    try:
        first = _capture(args.first)
        second = _capture(args.second)
        html = render_comparison_html(
            first, second, first_name=args.first.name, second_name=args.second.name
        )
        _publish_new(args.output, html.encode("utf-8"))
    except (OSError, ValueError, RecursionError) as error:
        _diagnose(error)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
