# SPDX-License-Identifier: GPL-3.0-only
import hashlib
import json

import pytest
import record_vcpkg_cache as recorder

COMMIT = "4" * 40
KEY_HASH = "a" * 64


def write_manifest(root, commit=COMMIT):
    path = root / "vcpkg.json"
    path.write_text(json.dumps({"builtin-baseline": commit}))
    return path


def env(hit="true", commit=COMMIT):
    return {
        "CAPTURE_VCPKG_CACHE_HIT": hit,
        "CAPTURE_VCPKG_CACHE_KEY": f"vcpkg-Windows-19.43.1-{commit}-{KEY_HASH}",
        "CAPTURE_VCPKG_COMMIT": commit,
        "CAPTURE_VCPKG_BINARY_SOURCES": r"clear;files,D:\a\_temp\vcpkg-binary-cache,readwrite",
        "GITHUB_ACTIONS": "true",
        "GITHUB_RUN_ID": "123",
        "UNRELATED_SECRET": "must-not-appear",
    }


def test_receipt_records_exact_hit_manifest_checkout_and_allowlisted_context(tmp_path):
    manifest = write_manifest(tmp_path)
    result = recorder.build_receipt(tmp_path, env())
    assert result["cache_hit"] is True and result["cache_restore"] == "exact"
    assert result["vcpkg_commit"] == COMMIT
    assert result["vcpkg_manifest_sha256"] == hashlib.sha256(manifest.read_bytes()).hexdigest()
    assert result["github"]["GITHUB_RUN_ID"] == "123"
    assert "UNRELATED_SECRET" not in result["github"]


@pytest.mark.parametrize(
    "hit,expected,restore",
    [("", None, "miss"), ("false", False, "partial"), ("true", True, "exact")],
)
def test_cache_restore_states_are_explicit(tmp_path, hit, expected, restore):
    write_manifest(tmp_path)
    result = recorder.build_receipt(tmp_path, env(hit))
    assert result["cache_hit"] is expected
    assert result["cache_restore"] == restore


@pytest.mark.parametrize(
    "field,value",
    [
        ("CAPTURE_VCPKG_CACHE_HIT", "maybe"),
        ("CAPTURE_VCPKG_CACHE_KEY", "constant"),
        ("CAPTURE_VCPKG_COMMIT", "5" * 40),
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
    write_manifest(tmp_path)
    values = env()
    values[field] = value
    with pytest.raises(ValueError):
        recorder.build_receipt(tmp_path, values)


def test_manifest_baseline_must_equal_actual_checkout(tmp_path):
    write_manifest(tmp_path, "5" * 40)
    with pytest.raises(ValueError, match="builtin-baseline"):
        recorder.build_receipt(tmp_path, env())


def test_invalid_manifest_is_not_accepted(tmp_path):
    (tmp_path / "vcpkg.json").write_text("not json")
    with pytest.raises(json.JSONDecodeError):
        recorder.build_receipt(tmp_path, env())
