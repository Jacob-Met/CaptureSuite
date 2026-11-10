#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Run the maintained desktop offline, using the shared frozen analysis resources."""

from __future__ import annotations

import sys

# The CLI bundle already binds the native jobs/registry to the packaged resources.
# Importing it configures those paths without invoking its command-line interface.
import analysis_bundle_entry  # noqa: F401
from capture_desktop.main import main

if __name__ == "__main__":
    raise SystemExit(main(["--offline", *sys.argv[1:]]))
