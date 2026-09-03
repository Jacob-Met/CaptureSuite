#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Generate Python protobuf bindings and the capture_v1 descriptor set.

Uses grpc_tools.protoc (or CAPTURE_PROTOC / vcpkg protoc when available).
Run from repo root:

    py -3.12 tools/gen_protos.py
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PROTO_ROOT = REPO_ROOT / "schemas" / "proto"
OUT_PY = REPO_ROOT / "libs" / "python" / "capture_protocol" / "capture_protocol" / "generated"
OUT_DESC = REPO_ROOT / "build" / "generated" / "capture_v1.desc"
INIT_PATH = OUT_PY / "__init__.py"


def _find_protoc() -> list[str]:
    env = os.environ.get("CAPTURE_PROTOC")
    if env and Path(env).exists():
        return [env]
    which = shutil.which("protoc")
    if which:
        return [which]
    # grpc_tools ships a protoc binary
    try:
        import grpc_tools  # noqa: F401

        # Invoke via python -m grpc_tools.protoc
        return [sys.executable, "-m", "grpc_tools.protoc"]
    except ImportError as exc:
        raise SystemExit(
            "No protoc found. Install grpcio-tools or set CAPTURE_PROTOC."
        ) from exc


def _proto_files() -> list[Path]:
    return sorted(PROTO_ROOT.rglob("*.proto"))


def main() -> int:
    protoc_cmd = _find_protoc()
    OUT_PY.mkdir(parents=True, exist_ok=True)
    OUT_DESC.parent.mkdir(parents=True, exist_ok=True)

    # Clean previous generated *_pb2.py (keep __init__.py)
    for stale in OUT_PY.rglob("*_pb2.py"):
        stale.unlink()
    for stale in OUT_PY.rglob("*_pb2.pyi"):
        stale.unlink()

    protos = _proto_files()
    if not protos:
        raise SystemExit(f"No .proto files under {PROTO_ROOT}")

    rel_protos = [p.relative_to(PROTO_ROOT).as_posix() for p in protos]

    args = [
        *protoc_cmd,
        f"--proto_path={PROTO_ROOT}",
        f"--python_out={OUT_PY}",
        f"--descriptor_set_out={OUT_DESC}",
        "--include_imports",
        *rel_protos,
    ]

    # grpc_tools.protoc needs well-known types path
    try:
        import grpc_tools

        well_known = Path(grpc_tools.__file__).parent / "_proto"
        if well_known.is_dir():
            args.insert(-len(rel_protos), f"--proto_path={well_known}")
    except ImportError:
        pass

    print("Running:", " ".join(args))
    result = subprocess.run(args, cwd=REPO_ROOT)
    if result.returncode != 0:
        return result.returncode

    # Fix imports: generated files use `from capture.v1 import X_pb2`
    # but we emit into a package tree that needs relative/package imports.
    # grpc_tools with python_out under generated/ creates capture/v1/*.py
    # when proto path includes package dirs — verify layout.
    _rewrite_imports(OUT_PY)
    _ensure_package_inits(OUT_PY)
    INIT_PATH.write_text(
        '"""Generated protobuf modules. Do not edit by hand."""\n'
        "from __future__ import annotations\n",
        encoding="utf-8",
    )
    print(f"Wrote Python bindings under {OUT_PY}")
    print(f"Wrote descriptor set {OUT_DESC}")
    return 0


def _ensure_package_inits(root: Path) -> None:
    for directory in {root, *root.rglob("*")}:
        if directory.is_dir():
            init = directory / "__init__.py"
            if not init.exists():
                init.write_text("", encoding="utf-8")


def _rewrite_imports(root: Path) -> None:
    """Rewrite absolute `capture.v1` imports to package-relative ones."""
    for path in root.rglob("*_pb2.py"):
        text = path.read_text(encoding="utf-8")
        # Packages land as root/capture/v1/foo_pb2.py
        rewritten = text.replace(
            "from capture.v1 import ",
            "from capture_protocol.generated.capture.v1 import ",
        ).replace(
            "from capture.v1.data import ",
            "from capture_protocol.generated.capture.v1.data import ",
        ).replace(
            "import capture.v1.",
            "import capture_protocol.generated.capture.v1.",
        )
        if rewritten != text:
            path.write_text(rewritten, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
