# SPDX-License-Identifier: GPL-3.0-only
import copy

import evaluate_vcpkg_cache as evaluator
import pytest

COMMIT = "4" * 40


def run(restore, attempt, seconds=900.0):
    hits = {"miss": None, "partial": False, "exact": True}
    return {
        "configure_seconds": seconds,
        "receipt": {
            "schema": "capturesuite.vcpkg-cache-receipt.v1",
            "cache_hit": hits[restore],
            "cache_restore": restore,
            "cache_key": "vcpkg-Windows-19.43-" + COMMIT + "-" + "a" * 64,
            "vcpkg_commit": COMMIT,
            "vcpkg_manifest_sha256": "b" * 64,
            "github": {
                "GITHUB_SHA": "candidate",
                "GITHUB_RUN_ID": "123",
                "GITHUB_RUN_ATTEMPT": str(attempt),
            },
        },
    }


def test_meaningful_same_run_warmup_is_accepted():
    result = evaluator.evaluate(run("miss", 1, 990), run("exact", 2, 180))
    assert result["accepted"]
    assert result["seconds_saved"] == 810
    assert result["configure_ratio"] < 0.5


@pytest.mark.parametrize(
    "mutation",
    [
        lambda c, w: c["receipt"].update(cache_hit=False, cache_restore="partial"),
        lambda c, w: w["receipt"].update(cache_hit=False, cache_restore="partial"),
        lambda c, w: w["receipt"].update(cache_key="different"),
        lambda c, w: w["receipt"].update(vcpkg_commit="5" * 40),
        lambda c, w: w["receipt"].update(vcpkg_manifest_sha256="different"),
        lambda c, w: w["receipt"]["github"].update(GITHUB_SHA="different"),
        lambda c, w: w["receipt"]["github"].update(GITHUB_RUN_ID="456"),
        lambda c, w: w["receipt"]["github"].update(GITHUB_RUN_ATTEMPT="1"),
        lambda c, w: w.update(configure_seconds=600),
        lambda c, w: w.update(configure_seconds=750),
    ],
)
def test_invalid_or_weak_benchmark_is_rejected(mutation):
    cold, warm = run("miss", 1, 990), run("exact", 2, 180)
    mutation(cold, warm)
    assert not evaluator.evaluate(cold, warm)["accepted"]


def test_evaluation_does_not_mutate_inputs():
    cold, warm = run("miss", 1), run("exact", 2, 100)
    before = copy.deepcopy((cold, warm))
    evaluator.evaluate(cold, warm)
    assert (cold, warm) == before
