# SPDX-License-Identifier: GPL-3.0-only
import hashlib

import pytest
import record_vcpkg_cache as recorder


def env(hit="true"):
    return {
        "CAPTURE_VCPKG_CACHE_HIT": hit,
        "CAPTURE_VCPKG_CACHE_KEY": "vcpkg-Windows-19.43.1-" + "a" * 64,
        "CAPTURE_VCPKG_BINARY_SOURCES": r"clear;files,D:\a\_temp\vcpkg-binary-cache,readwrite",
        "GITHUB_ACTIONS": "true",
        "GITHUB_RUN_ID": "123",
        "UNRELATED_SECRET": "must-not-appear",
    }


def test_receipt_records_hit_manifest_and_allowlisted_context(tmp_path):
    manifest = tmp_path / "vcpkg.json"
    manifest.write_text('{"name":"fixture"}')
    result = recorder.build_receipt(tmp_path, env())
    assert result["cache_hit"] is True
    assert result["vcpkg_manifest_sha256"] == hashlib.sha256(manifest.read_bytes()).hexdigest()
    assert result["github"]["GITHUB_RUN_ID"] == "123"
    assert "UNRELATED_SECRET" not in result["github"]


@pytest.mark.parametrize("hit,expected", [("", None), ("false", False), ("true", True)])
def test_cache_hit_states_are_explicit(tmp_path, hit, expected):
    (tmp_path / "vcpkg.json").write_text("{}")
    assert recorder.build_receipt(tmp_path, env(hit))["cache_hit"] is expected


@pytest.mark.parametrize(
    "field,value",
    [
        ("CAPTURE_VCPKG_CACHE_HIT", "maybe"),
        ("CAPTURE_VCPKG_CACHE_KEY", "constant"),
        ("CAPTURE_VCPKG_BINARY_SOURCES", "clear;x-gha,readwrite"),
        ("CAPTURE_VCPKG_BINARY_SOURCES", r"files,D:\cache,readwrite"),
        ("CAPTURE_VCPKG_BINARY_SOURCES", r"clear;files,D:\cache,read"),
        (
            "CAPTURE_VCPKG_BINARY_SOURCES",
            r"clear;files,D:\cache,readwrite;files,E:\other,readwrite",
        ),
        ("CAPTURE_VCPKG_BINARY_SOURCES", r"clear;files,relative\cache,readwrite"),
    ],
)
def test_invalid_cache_claims_are_rejected(tmp_path, field, value):
    (tmp_path / "vcpkg.json").write_text("{}")
    values = env()
    values[field] = value
    with pytest.raises(ValueError):
        recorder.build_receipt(tmp_path, values)
