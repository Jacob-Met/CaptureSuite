# SPDX-License-Identifier: GPL-3.0-only
import copy

import evaluate_vcpkg_cache as evaluator
import pytest


def run(hit, attempt, seconds=900.0):
    return {
        "configure_seconds": seconds,
        "receipt": {
            "schema": "capturesuite.vcpkg-cache-receipt.v1",
            "cache_hit": hit,
            "cache_key": "vcpkg-Windows-19.43-" + "a" * 64,
            "vcpkg_manifest_sha256": "b" * 64,
            "github": {
                "GITHUB_SHA": "candidate",
                "GITHUB_RUN_ID": "123",
                "GITHUB_RUN_ATTEMPT": str(attempt),
            },
        },
    }


def test_meaningful_same_run_warmup_is_accepted():
    result = evaluator.evaluate(run(False, 1, 990), run(True, 2, 180))
    assert result["accepted"]
    assert result["seconds_saved"] == 810
    assert result["configure_ratio"] < 0.5


@pytest.mark.parametrize(
    "mutation",
    [
        lambda c, w: w["receipt"].update(cache_hit=False),
        lambda c, w: c["receipt"].update(cache_hit=True),
        lambda c, w: w["receipt"].update(cache_key="different"),
        lambda c, w: w["receipt"].update(vcpkg_manifest_sha256="different"),
        lambda c, w: w["receipt"]["github"].update(GITHUB_SHA="different"),
        lambda c, w: w["receipt"]["github"].update(GITHUB_RUN_ID="456"),
        lambda c, w: w["receipt"]["github"].update(GITHUB_RUN_ATTEMPT="1"),
        lambda c, w: w.update(configure_seconds=600),
        lambda c, w: w.update(configure_seconds=750),
    ],
)
def test_invalid_or_weak_benchmark_is_rejected(mutation):
    cold, warm = run(False, 1, 990), run(True, 2, 180)
    mutation(cold, warm)
    assert not evaluator.evaluate(cold, warm)["accepted"]


def test_evaluation_does_not_mutate_inputs():
    cold, warm = run(False, 1), run(True, 2, 100)
    before = copy.deepcopy((cold, warm))
    evaluator.evaluate(cold, warm)
    assert (cold, warm) == before
