#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Independently receive the feature writer's terminal suffix contract."""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import platform
import sys

import pandas as pd
import pyarrow

CONTRACT = Path(__file__).with_name("frozen-contract.json")
WRONG_NEIGHBOURS = {
    "parent_suffix_word": "results.csv/source-one.csv",
    "source_stem_suffix_word": "features/source.csv.part.csv",
    "repeated_parent_and_stem": "archive.csv/session.csv/source.csv.csv",
    "literal_unicode_space_and_punctuation": "study.csv Ω #?%/sample.csv final.csv",
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def fingerprint(file):
    stat = file.stat()
    return {"sha256": sha(file.read_bytes()), "bytes": stat.st_size,
            "mtime_ns": stat.st_mtime_ns, "inode": stat.st_ino}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--writer", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    writer = args.writer.resolve()
    out = args.output.absolute()
    if out.exists() or out.is_symlink():
        parser.error("--output must be a new directory")
    raw_source = writer.read_bytes()
    spec = importlib.util.spec_from_file_location("received_feature_writer", writer)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    out.mkdir(parents=True)
    checks, calls = [], []

    def check(case, name, good, observed=None):
        checks.append({"case": case, "check": name, "pass": bool(good),
                       "observed": observed})

    for index, case in enumerate(contract["cases"]):
        name = case["name"]
        job = out / (str(index) + "-job.parquet")
        job.mkdir()
        original = pd.DataFrame({
            "source_id": ["camera.parquet.alpha", "radar.parquet.beta"],
            "native_tick": pd.Series([1234567890123456789, 1234567890123456797],
                                     dtype="int64"),
            "feature": pd.Series([1.25, -2.5], dtype="float64"),
            "valid": pd.Series([True, False], dtype="bool"),
        })
        frame = original.copy(deep=True)
        input_file = out / ("source-" + str(index) + ".json")
        input_file.write_text(original.to_json(orient="records"), encoding="utf-8")
        input_before = fingerprint(input_file)
        prior = job / "retained/previous.csv"
        prior.parent.mkdir()
        prior.write_bytes(b"Earlier retained export stays unchanged.\n")
        prior_before = fingerprint(prior)
        initial_output = {
            "relativePath": "retained/previous.csv", "bytes": prior.stat().st_size,
            "sha256": sha(prior.read_bytes()), "kind": "retained_fixture",
        }
        outputs = [copy.deepcopy(initial_output)]
        columns = [{"name": col, "dtype": str(dtype)}
                   for col, dtype in original.dtypes.items()]
        original_columns = copy.deepcopy(columns)
        schema = {"tables": {"retained/previous.parquet": {
            "featureSchemaVersion": 1, "columns": [], "rows": 0}},
            "sourceIdentity": {"ids": original["source_id"].tolist(),
                               "timestampPolicy": "retain native ticks"}}
        prior_schema = copy.deepcopy(schema)
        wrong = None
        if name in WRONG_NEIGHBOURS:
            wrong = job / WRONG_NEIGHBOURS[name]
            wrong.parent.mkdir(parents=True, exist_ok=True)
            wrong.write_bytes(b"Unrelated filename neighbour must be preserved.\n")
            wrong_before = fingerprint(wrong)
        error = None
        try:
            module.write_feature_table(
                job, case["parquet"], frame, feature_schema_version=1,
                columns_meta=columns, schema_doc=schema, outputs=outputs,
            )
        except Exception as exc:
            error = {"type": type(exc).__name__, "message": str(exc)}
        calls.append({"case": name, "parquet": case["parquet"],
                      "expected_csv": case["csv"], "exception": error,
                      "outputs": copy.deepcopy(outputs), "schema": copy.deepcopy(schema)})
        check(name, "actual_writer_completes", error is None, error)
        try:
            pd.testing.assert_frame_equal(frame, original, check_dtype=True)
            unchanged = True
        except AssertionError:
            unchanged = False
        check(name, "source_dataframe_preserved", unchanged)
        check(name, "source_file_preserved", fingerprint(input_file) == input_before)
        check(name, "earlier_export_preserved", fingerprint(prior) == prior_before)
        check(name, "column_metadata_preserved", columns == original_columns)
        if wrong:
            check(name, "unrelated_suffix_neighbour_preserved",
                  fingerprint(wrong) == wrong_before, str(wrong.relative_to(job)))

        for kind, relative in [("feature_parquet", case["parquet"]),
                               ("feature_csv", case["csv"])]:
            target = job / relative
            check(name, kind + "_literal_destination_exists", target.is_file(), relative)
            table_error = None
            if target.is_file():
                try:
                    table = (pd.read_parquet(target) if kind == "feature_parquet"
                             else pd.read_csv(target))
                    pd.testing.assert_frame_equal(table, original, check_dtype=True)
                except Exception as exc:
                    table_error = {"type": type(exc).__name__, "message": str(exc)}
                check(name, kind + "_exact_rows_columns_types", table_error is None,
                      table_error)
            else:
                check(name, kind + "_exact_rows_columns_types", False, "missing output")
            expected = ({"relativePath": relative, "bytes": target.stat().st_size,
                         "sha256": sha(target.read_bytes()), "kind": kind}
                        if target.is_file() else None)
            check(name, kind + "_manifest_names_and_hashes_actual_file",
                  expected is not None and outputs.count(expected) == 1,
                  {"expected": expected, "actual": [v for v in outputs if v.get("kind") == kind]})
        check(name, "manifest_retains_prior_entry_and_exact_pair",
              len(outputs) == 3 and outputs[0] == initial_output
              and [o.get("relativePath") for o in outputs[1:]]
              == [case["parquet"], case["csv"]])
        expected_schema = copy.deepcopy(prior_schema)
        expected_schema["schemaId"] = "capture.analysis_feature_schema/1"
        expected_schema["tables"][case["parquet"]] = {
            "featureSchemaVersion": 1, "columns": original_columns, "rows": 2}
        check(name, "schema_and_source_identity_preserved", schema == expected_schema,
              schema)

    failures = [c for c in checks if not c["pass"]]
    result = {
        "status": "FAIL" if failures else "PASS",
        "writer": str(writer), "writer_bytes": len(raw_source),
        "writer_sha256": sha(raw_source),
        "writer_git_blob": hashlib.sha1(b"blob " + str(len(raw_source)).encode()
                                      + b"\0" + raw_source).hexdigest(),
        "receiver_sha256": sha(Path(__file__).read_bytes()),
        "contract_sha256": sha(CONTRACT.read_bytes()),
        "checks": checks, "failed_checks": failures, "writer_calls": calls,
        "environment": {"python": sys.version, "executable": sys.executable,
                        "platform": platform.platform(), "pandas": pd.__version__,
                        "pyarrow": pyarrow.__version__},
        "scope": "Actual isolated feature-writer API calls, Parquet and CSV reads, "
                 "manifest bytes and digests, and input/source-identity preservation. "
                 "No GUI, capture hardware, whole-pipeline or throughput claim.",
    }
    (out / "receiving.json").write_text(
        json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8")
    print(json.dumps({"status": result["status"], "cases": len(calls),
                      "checks": len(checks), "failed": len(failures),
                      "receipt": str(out / "receiving.json")}))
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(main())
