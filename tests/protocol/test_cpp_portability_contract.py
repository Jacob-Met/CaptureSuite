# SPDX-License-Identifier: GPL-3.0-only
from pathlib import Path

import check_cpp_warning_boundary as boundary


def test_real_owned_sources_have_no_direct_getenv():
    assert boundary.find_deprecated_env_access(boundary.ROOT) == []


def test_direct_getenv_is_reported_but_safe_helper_header_is_exempt(tmp_path: Path):
    source = tmp_path / "daemon/src/example.cpp"
    source.parent.mkdir(parents=True)
    source.write_text('auto *p = std::getenv("HOME");\n', encoding="utf-8")
    helper = tmp_path / "libs/cpp/capture_core/include/capture/env.hpp"
    helper.parent.mkdir(parents=True)
    helper.write_text('auto *p = std::getenv("HOME");\n', encoding="utf-8")
    assert boundary.find_deprecated_env_access(tmp_path) == ["daemon/src/example.cpp:1"]


def test_dupenv_s_does_not_trigger(tmp_path: Path):
    source = tmp_path / "workers/example.cpp"
    source.parent.mkdir(parents=True)
    source.write_text('char *p = nullptr; size_t n = 0; _dupenv_s(&p, &n, "HOME");\n')
    assert boundary.find_deprecated_env_access(tmp_path) == []
