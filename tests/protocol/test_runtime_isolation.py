# SPDX-License-Identifier: GPL-3.0-only
import os
from pathlib import Path


def test_application_state_is_private_to_this_test_session(isolated_application_state):
    root = isolated_application_state.resolve()
    assert Path(os.environ["CAPTURE_TEST_STATE"]).resolve() == root
    for key in ["LOCALAPPDATA", "APPDATA", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME"]:
        path = Path(os.environ[key]).resolve()
        assert path.is_relative_to(root) and path.is_dir()
