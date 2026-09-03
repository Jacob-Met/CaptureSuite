# SPDX-License-Identifier: Apache-2.0
"""CLI: ``python -m capture_worker run module:Class --pipe --worker-id --plugin``."""

from __future__ import annotations

import argparse
import importlib
import sys
from typing import Any


def _load_worker_class(spec: str) -> type[Any]:
    if ":" not in spec:
        raise SystemExit(
            f"worker class must be module:Class (got {spec!r}); "
            "example: example_sine:SineWorker"
        )
    module_name, class_name = spec.split(":", 1)
    module = importlib.import_module(module_name)
    try:
        cls = getattr(module, class_name)
    except AttributeError as exc:
        raise SystemExit(f"{module_name!r} has no attribute {class_name!r}") from exc
    return cls


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="capture_worker",
        description="CaptureSuite Python worker host (WORKER_HOST.md CLI args).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Run a Worker subclass over a named pipe")
    run.add_argument(
        "worker",
        help="Import path module:Class (e.g. example_sine:SineWorker)",
    )
    run.add_argument("--pipe", required=True, help="Named pipe path from the daemon")
    run.add_argument("--worker-id", required=True, help="Worker instance id")
    run.add_argument("--plugin", required=True, help="plugin_id (e.g. example.sine)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command != "run":
        return 2
    cls = _load_worker_class(args.worker)
    worker = cls(plugin_id=args.plugin, worker_id=args.worker_id)
    return int(worker.run(pipe_name=args.pipe))


if __name__ == "__main__":
    sys.exit(main())
