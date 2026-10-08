# SPDX-License-Identifier: GPL-3.0-only
"""Independent real-CLI receiving for issue74, frozen before production.

Uses the maintained mini_session and real native collector/renderer. The two
28-byte MCAP placeholders are inventoried, never decoded or certified as raw
capture. No package/job implementation is imported from the proposed feature.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
import subprocess
import sys
import traceback
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from capture_analysis.qc import collect_qc
from capture_analysis.report_html import render_qc_html

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests/fixtures/mini_session"
CLI = ROOT / "tools/review_qc_packages.py"
BROWSER_HELPER = ROOT / "tools/check_qc_package_review_index_7879.mjs"
CRITERIA_BLOB = "3c6db0126cd7fa513287fde42e9cecff96bd3218"
CRITERIA_PREDECESSOR = "70f34e3b982523b544a9370d2316a1b69d79bd70"
INTERMEDIATE_BASE = "58157fdc1b83a12bb4856ef14b0498cf524a1087"
CURRENT_BASE = "9c44354cb101c76beff79265de0040b6839d249f"
LITERAL = 'Shared <img src=x onerror="window.qcInjected=true"> 海 Café 😀\nsecond line'
GAP_CAUSE = 'Gap <script>window.qcInjected=true</script> 海 & "quoted"\nnext line'
LARGE_START = 2**63 + 17
LARGE_LOSS = 2**80 + 13
SOURCE_PATHS = [
    "AGENTS.md", "CONTRIBUTING.md", "LICENSING.md", "requirements-ci.txt",
    "pyproject.toml", ".github/workflows/ci.yml", "tests/conftest.py",
    "libs/python/capture_analysis/capture_analysis/qc.py",
    "libs/python/capture_analysis/capture_analysis/report_html.py",
    "libs/python/capture_analysis/capture_analysis/discover.py",
    "libs/python/capture_analysis/capture_analysis/types.py",
    "libs/python/capture_analysis/capture_analysis/__init__.py",
    "libs/python/capture_analysis/capture_analysis/jobs.py",
    "libs/python/capture_session/capture_session/package_reader.py",
    "libs/python/capture_session/capture_session/__init__.py",
    "tools/run_analysis.py", "tools/run_ci_tests.py",
    "tests/analysis/test_phase_a_qc.py",
    "tests/analysis/test_qc_package_review_receiving_7879.py",
    "tools/check_qc_package_review_index_7879.mjs",
    ".github/workflows/qc-package-review-receiving.yml",
    "tools/review_qc_packages.py",
    "libs/python/capture_analysis/capture_analysis/qc_packages.py",
]
OPTIONAL_SOURCE = {
    "tools/review_qc_packages.py",
    "libs/python/capture_analysis/capture_analysis/qc_packages.py",
}
SUMMARY_KEYS = {"schemaId", "packageCount", "collectedCount", "failedCount", "packages"}
ENTRY_KEYS = {"ordinal", "inputPath", "packagePath", "status", "qc", "error", "reports"}


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, indent=2, sort_keys=True).encode("utf-8")


def _snapshot(root: Path) -> dict[str, Any]:
    if not root.exists():
        return {"exists": False}
    assert not root.is_symlink(), f"Authored receiving root became a symlink: {root}"
    if root.is_file():
        raw = root.read_bytes()
        return {"exists": True, "kind": "file", "bytes": len(raw), "sha256": _sha(raw)}
    directories = ["."]
    files = {}
    for path in sorted(root.rglob("*")):
        assert not path.is_symlink(), f"Authored receiving input became a symlink: {path}"
        name = path.relative_to(root).as_posix()
        if path.is_dir():
            directories.append(name)
        else:
            assert path.is_file(), f"Unexpected fixture entry: {path}"
            raw = path.read_bytes()
            files[name] = {"bytes": len(raw), "sha256": _sha(raw)}
    return {"exists": True, "kind": "directory", "directories": directories, "files": files}


def _source_snapshot() -> dict[str, Any]:
    paths = set(SOURCE_PATHS)
    paths.update(path.relative_to(ROOT).as_posix() for path in FIXTURE.rglob("*") if path.is_file())
    result = {}
    for name in sorted(paths):
        path = ROOT / name
        if name in OPTIONAL_SOURCE and not path.exists():
            result[name] = None
            continue
        assert path.is_file() and not path.is_symlink(), f"Missing native source: {name}"
        raw = path.read_bytes()
        result[name] = {"bytes": len(raw), "sha256": _sha(raw)}
    return result


def _write_json(path: Path, value: Any) -> None:
    path.write_bytes(_json_bytes(value) + b"\n")


def _copy_package(parent: Path, name: str) -> Path:
    package = parent / name
    shutil.copytree(FIXTURE, package)
    (package / "processing/retained-owner-note.bin").write_bytes(
        b"Authored prior processing output: preserve exactly.\x00\xff\n"
    )
    return package


def _native(package: Path) -> dict[str, Any]:
    before = _snapshot(package)
    qc = collect_qc(package).to_dict()
    html = render_qc_html(qc)
    assert _snapshot(package) == before, "Native positive control changed its input"
    assert isinstance(html, str) and "Analysis QC" in html
    assert qc["packagePath"] == str(package.resolve())
    assert qc["manifestSha256"] == _sha((package / "manifest.json").read_bytes())
    return qc


class _Html(HTMLParser):
    def __init__(self, content: str) -> None:
        super().__init__(convert_charrefs=True)
        self.tags: list[tuple[str, dict[str, str | None]]] = []
        self.parts: list[str] = []
        self.feed(content)
        self.close()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags.append((tag, dict(attrs)))

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


class _Receiver:
    def __init__(self, tmp_path: Path) -> None:
        self.tmp = tmp_path
        self.inputs = tmp_path / "input-packages"
        self.inputs.mkdir()
        self.outputs = tmp_path / "explicit-review-outputs"
        self.outputs.mkdir()
        self.emit = bool(os.environ.get("CAPTURE_QC_RECEIVING_OUTPUT"))
        self.artifacts = Path(os.environ.get("CAPTURE_QC_RECEIVING_OUTPUT", tmp_path / "receipt"))
        self.artifacts.mkdir(exist_ok=False)
        self.source = _source_snapshot()
        self.report: dict[str, Any] = {
            "schema": "capture.qc-package-review.browser-cli-receiving/1",
            "status": "running", "checks": [], "commands": [], "artifacts": [],
            "inputSnapshots": {}, "sourceBefore": self.source,
            "criteriaBlob": CRITERIA_BLOB, "criteriaPredecessor": CRITERIA_PREDECESSOR,
            "currentBase": CURRENT_BASE,
            "sourceBridge": {
                "from": CRITERIA_PREDECESSOR, "to": INTERMEDIATE_BASE,
                "oldLeaves": 919, "currentLeaves": 922, "unchanged": 914,
                "changed": [
                    "docs/design/ANALYSIS.md", "docs/design/research/PROGRESS.md",
                    "libs/python/capture_analysis/capture_analysis/eval/job.py",
                    "libs/python/capture_analysis/capture_analysis/jobs.py",
                    "tools/run_analysis.py",
                ],
                "added": [
                    "libs/python/capture_analysis/capture_analysis/eval/predictions.py",
                    "schemas/eval/predictions.schema.json",
                    "tests/analysis/test_external_predictions.py",
                ],
                "meaning": "70f is the predecessor; actual checkout is recorded below.",
            },
            "currentSourceBridge": {
                "from": INTERMEDIATE_BASE, "to": CURRENT_BASE,
                "oldLeaves": 922, "currentLeaves": 1012, "unchanged": 914,
                "changed": [
                    "docs/design/ANALYSIS.md",
                    "docs/design/research/ANALYSIS_SCOPE_SEMANTICS.md",
                    "docs/design/research/PROGRESS.md",
                    "libs/python/capture_analysis/capture_analysis/windows.py",
                    "tests/analysis/test_numeric_receiving.py",
                    "tests/cpp/test_worker_host.cpp",
                    "tests/ui/test_analysis_scope.py",
                    "workers/camera/src/capture_pipeline.cpp",
                ],
                "added": 90, "removed": 0,
                "meaning": "QC/readers/mini_session/requirements/maintained CI remain exact; "
                "the actual synthesized checkout and observed source hashes are recorded.",
            },
            "python": sys.version, "executable": sys.executable,
            "nativeLimit": (
                "Maintained mini_session contains two 28-byte MCAP placeholders. "
                "The native collector inventories descriptors/segment names and optional metadata; "
                "It does not certify raw capture; native optional-record omissions remain."
            ),
            "browser": {"status": "not requested in the maintained full-suite route"},
        }
        for name, command in [
            ("checkout", ["git", "rev-parse", "HEAD"]),
            ("tree", ["git", "rev-parse", "HEAD^{tree}"]),
        ]:
            self.report[name] = subprocess.check_output(
                command, cwd=ROOT, text=True, encoding="utf-8", timeout=10
            ).strip()
        print("CAPTURE_QC_REVIEW_PROVENANCE " + json.dumps({
            key: self.report[key]
            for key in ("checkout", "tree", "criteriaBlob", "currentBase", "python")
        }), flush=True)

    def artifact(self, name: str, raw: bytes, kind: str) -> None:
        path = self.artifacts / name
        assert path.resolve().is_relative_to(self.artifacts.resolve())
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            stream.write(raw)
        self.report["artifacts"].append({
            "path": name, "bytes": len(raw), "sha256": _sha(raw), "kind": kind,
        })

    def native_artifacts(self, prefix: str, ordinal: int, qc: dict[str, Any]) -> None:
        self.artifact(f"{prefix}/{ordinal:03d}-qc.json", _json_bytes(qc), "real native QC")
        self.artifact(
            f"{prefix}/{ordinal:03d}-qc.html",
            render_qc_html(qc).encode("utf-8"), "real native QC HTML",
        )

    def passed(self, label: str) -> None:
        self.report["checks"].append(label)
        print("CAPTURE_QC_REVIEW_PASS " + label, flush=True)

    def command(
        self, name: str, inputs: list[str], output: Path, expected: int,
    ) -> subprocess.CompletedProcess[str]:
        before = _snapshot(self.inputs)
        before_key = _sha(_json_bytes(before))
        self.report["inputSnapshots"][before_key] = before
        state_root = Path(os.environ["CAPTURE_TEST_STATE"])
        state_before = _snapshot(state_root)
        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        argv = [sys.executable, str(CLI), "--output", str(output), *inputs]
        result = subprocess.run(
            argv, cwd=self.tmp, env=env, capture_output=True, text=True,
            encoding="utf-8", errors="strict", timeout=90, check=False,
        )
        after = _snapshot(self.inputs)
        item = {
            "name": name, "argv": argv, "cwd": str(self.tmp), "exit": result.returncode,
            "stdout": result.stdout, "stderr": result.stderr,
            "inputsBefore": before_key, "inputsAfter": _sha(_json_bytes(after)),
            "inputUnchanged": before == after,
            "applicationStateUnchanged": _snapshot(state_root) == state_before,
        }
        self.report["commands"].append(item)
        # Print the actual command output BEFORE the expected-exit assertion.
        print("CAPTURE_QC_REVIEW_COMMAND " + json.dumps(item), flush=True)
        assert item["inputUnchanged"], name + ": complete package file/directory conservation"
        assert item["applicationStateUnchanged"], name + ": no registry/settings/job activity"
        assert result.returncode == expected, (
            f"{name}: expected exit {expected}, received {result.returncode}\n"
            + result.stdout + result.stderr
        )
        return result

    def review(
        self, output: Path, inputs: list[str], expected: list[dict[str, Any] | None],
        *, retain: str | None = None,
    ) -> dict[str, Any]:
        assert output.is_dir() and not output.is_symlink()
        doc = json.loads((output / "review.json").read_text(encoding="utf-8"))
        assert set(doc) == SUMMARY_KEYS
        assert doc["schemaId"] == "capture.qc_package_review/1"
        assert doc["packageCount"] == len(inputs)
        count = sum(qc is not None for qc in expected)
        assert doc["collectedCount"] == count
        assert doc["failedCount"] == len(inputs) - count
        assert len(doc["packages"]) == len(inputs)
        expected_files = {"review.json", "index.html"}
        links = set()
        for ordinal, (item, original, qc) in enumerate(
            zip(doc["packages"], inputs, expected, strict=True), 1,
        ):
            assert set(item) == ENTRY_KEYS
            assert item["ordinal"] == ordinal
            assert item["inputPath"] == original
            package_path = str((self.tmp / original).resolve())
            assert item["packagePath"] == package_path
            if qc is None:
                assert item["status"] == "failed"
                assert item["qc"] is None and item["reports"] is None
                assert set(item["error"]) == {"type", "message"}
                assert all(
                    isinstance(item["error"][key], str) and item["error"][key]
                    for key in ("type", "message")
                )
                continue
            assert item["status"] == "collected" and item["error"] is None
            assert item["qc"] == qc, f"Complete native dictionary differs for ordinal {ordinal}"
            names = {
                "json": f"reports/{ordinal:03d}-qc.json",
                "html": f"reports/{ordinal:03d}-qc.html",
            }
            assert item["reports"] == names
            expected_files.update(names.values())
            links.update(names.values())
            expected_bytes = {
                "json": _json_bytes(qc), "html": render_qc_html(qc).encode("utf-8"),
            }
            for kind, name in names.items():
                path = output / name
                assert path.is_file() and not path.is_symlink()
                assert path.read_bytes() == expected_bytes[kind], (
                    f"Native {kind} bytes changed for ordinal {ordinal}"
                )
        inventory = _snapshot(output)
        assert set(inventory["files"]) == expected_files, "Omitted report or extra job/stage file"
        html = (output / "index.html").read_text(encoding="utf-8")
        parsed = _Html(html)
        blocked_tags = {"script", "img", "iframe", "object", "embed"}
        assert not any(tag in blocked_tags for tag, _ in parsed.tags)
        assert not any(
            key.lower().startswith("on") for _, attrs in parsed.tags for key in attrs
        )
        actual_links = {
            attrs["href"] for tag, attrs in parsed.tags
            if tag == "a" and attrs.get("href") and not attrs["href"].startswith("#")
        }
        assert actual_links == links, "Only generated ordinal-relative report links"
        ordinals = [
            attrs["data-qc-review-ordinal"] for _, attrs in parsed.tags
            if "data-qc-review-ordinal" in attrs
        ]
        assert ordinals == [str(i) for i in range(1, len(inputs) + 1)]
        text = "".join(parsed.parts)
        for item in doc["packages"]:
            assert item["inputPath"] in text and item["packagePath"] in text
            if item["qc"] is not None:
                assert item["qc"]["sessionId"] in text
                for warning in item["qc"]["warnings"]:
                    assert warning in text, "Native warning missing from the retained index"
            else:
                assert item["error"]["message"] in text
        if retain:
            for name in sorted(expected_files):
                self.artifact(
                    retain + "/" + name, (output / name).read_bytes(), "actual CLI output",
                )
        return doc

    def finish(self, error: BaseException | None) -> None:
        self.report["status"] = "failed" if error else "passed"
        if error:
            self.report["error"] = "".join(traceback.format_exception(error))
        after = _source_snapshot()
        self.report["sourceAfter"] = after
        self.report["sourceUnchanged"] = after == self.source
        raw = _json_bytes(self.report) + b"\n"
        (self.artifacts / "receiving-report.json").write_bytes(raw)
        if self.emit:
            _bundle(self.artifacts, self.report)
        print(
            "CAPTURE_QC_REVIEW_RESULT "
            + json.dumps({
                "status": self.report["status"], "checks": len(self.report["checks"]),
                "sourceUnchanged": self.report["sourceUnchanged"],
                "browser": self.report["browser"]["status"],
                "reportBytes": len(raw), "reportSha256": _sha(raw),
            }),
            flush=True,
        )
        assert self.report["sourceUnchanged"], "Observed source changed during actual receiving"


def _recovered(package: Path) -> dict[str, Any]:
    manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    manifest.update(sessionId=LITERAL, state="finalized_recovered")
    _write_json(package / "manifest.json", manifest)
    recovery = package / "recovery"
    recovery.mkdir()
    _write_json(recovery / "report_authored.json", {"fixture": "authored recovery warning"})
    gaps = [
        {
            "sourceId": "sim.emg.main", "streamId": "sim.emg.main.batch",
            "cause": GAP_CAUSE, "startSessionTimeNs": LARGE_START,
            "endSessionTimeNs": LARGE_START + 2_000_000_007, "closed": True,
            "estimatedLostCount": LARGE_LOSS,
        },
        {
            "sourceId": "sim.emg.main", "cause": "open authored gap",
            "startSessionTimeNs": LARGE_START + 3, "closed": False,
            "estimatedLostCount": 7,
        },
        {
            "sourceId": "sim.emg.main", "cause": "closed without a recorded end",
            "startSessionTimeNs": LARGE_START + 4, "closed": True,
        },
        {
            "sourceId": "sim.emg.main", "cause": "native reversed-time warning",
            "startSessionTimeNs": LARGE_START + 9,
            "endSessionTimeNs": LARGE_START + 8, "closed": True,
        },
    ]
    raw = b"\n".join(json.dumps(row).encode("utf-8") for row in gaps)
    # The maintained reader skips malformed optional JSONL. Keep that native
    # limitation visible; this receiver does not invent stricter certification.
    (package / "sources/sim.emg.main/health/gaps.jsonl").write_bytes(
        raw + b"\n{authored malformed optional row}\n"
    )
    next((package / "sources/sim.imu.upper").rglob("*.mcap")).unlink()
    qc = _native(package)
    assert qc["packageState"] == "finalized_recovered"
    assert qc["sessionId"] == LITERAL
    assert qc["trafficLights"] == {"sim.emg.main": "warn", "sim.imu.upper": "fail"}
    assert qc["openGapCount"] == 1 and qc["closedGapCount"] == 3
    assert [gap["durationStatus"] for gap in qc["gaps"]] == [
        "known", "open", "missing_end", "end_before_start",
    ]
    assert qc["gaps"][0]["startSessionTimeNs"] == str(LARGE_START)
    assert qc["gaps"][0]["endSessionTimeNs"] == str(LARGE_START + 2_000_000_007)
    assert qc["gaps"][0]["estimatedLostCount"] == str(LARGE_LOSS)
    assert qc["gaps"][0]["durationNs"] == "2000000007"
    assert qc["gaps"][0]["cause"] == GAP_CAUSE
    assert qc["recoveryReports"] == ["recovery/report_authored.json"]
    assert any("no segment" in text for text in qc["warnings"])
    assert any("recovery reports" in text for text in qc["warnings"])
    return qc


def test_qc_package_review_receiving_7879(tmp_path: Path) -> None:
    receiver = _Receiver(tmp_path)
    error: BaseException | None = None
    try:
        fixture_before = _snapshot(FIXTURE)
        assert len(fixture_before["files"]) == 13
        placeholders = list(FIXTURE.rglob("*.mcap"))
        assert len(placeholders) == 2 and all(path.stat().st_size == 28 for path in placeholders)
        a = _copy_package(receiver.inputs, "a-first.mmsession")
        b = _copy_package(receiver.inputs, "z-last-海-Cafe.mmsession")
        qa, qb = _native(a), _native(b)
        for ordinal, qc in enumerate([qa, qb], 1):
            assert qc["sessionId"] == "mini-analysis-fixture"
            assert qc["packageState"] == "finalized"
            assert qc["streamCount"] == 2 and qc["sourceCount"] == 2
            assert {row["modality"] for row in qc["streams"]} == {"emg", "imu"}
            assert [row["mcapSegments"] for row in qc["streams"]] == [1, 1]
            receiver.native_artifacts("native", ordinal, qc)
        receiver.report["fixtureBefore"] = fixture_before
        receiver.passed(
            "real native collector/renderer inventory two copied finalized mini packages "
            "before the advertised multi-package command is required"
        )

        # Actual original negative: no pre-assert on CLI existence and no mock.
        # The original interpreter's missing-file output is printed before exit
        # admission. The same invocation/assertions govern the candidate.
        ordered_inputs = [
            os.path.join(".", "input-packages", b.name),
            str(a.resolve()),
        ]
        ordered = receiver.outputs / "ordered"
        receiver.command("original-or-candidate-two-package-command", ordered_inputs, ordered, 0)
        doc = receiver.review(ordered, ordered_inputs, [qb, qa], retain="ordered")
        assert doc["packages"][0]["qc"]["sessionId"] == doc["packages"][1]["qc"]["sessionId"]
        assert doc["packages"][0]["packagePath"] != doc["packages"][1]["packagePath"]
        old_ordered = _snapshot(ordered)
        receiver.passed(
            "actual CLI preserves requested order, original path spelling and distinct "
            "package provenance despite equal session identities"
        )

        qb = _recovered(b)
        c = _copy_package(receiver.inputs, "m-peer-海.mmsession")
        manifest = json.loads((c / "manifest.json").read_text(encoding="utf-8"))
        manifest["sessionId"] = LITERAL
        _write_json(c / "manifest.json", manifest)
        qc = _native(c)
        warning_inputs = [str(b), str(c)]
        warning_output = receiver.outputs / "warnings"
        receiver.command("native-warnings-are-still-collected", warning_inputs, warning_output, 0)
        warned = receiver.review(
            warning_output, warning_inputs, [qb, qc], retain="warnings",
        )
        assert warned["failedCount"] == 0 and warned["collectedCount"] == 2
        assert warned["packages"][0]["qc"]["trafficLights"]["sim.imu.upper"] == "fail"
        assert _snapshot(ordered) == old_ordered, "Earlier completed output changed"
        receiver.report["warningOracle"] = qb
        receiver.passed(
            "recovered-package warnings, native failure lights, open/unknown gaps and "
            "large decimal gap/loss values remain exact without collection-status substitution"
        )

        native_html = (warning_output / "reports/001-qc.html").read_text(encoding="utf-8")
        parsed = _Html(native_html)
        assert not any(tag in {"script", "img"} for tag, _ in parsed.tags)
        visible = "".join(parsed.parts)
        assert LITERAL in visible and GAP_CAUSE in visible
        assert str(LARGE_LOSS) in visible and "2.000000007" in visible
        assert "unknown (open gap)" in visible and "unknown (end not recorded)" in visible
        assert "unknown (end precedes start)" in visible
        receiver.passed(
            "actual native and aggregate HTML retain literal markup/Unicode/multiline "
            "identity, precise gap text and only ordinal-relative report links"
        )

        bad = _copy_package(receiver.inputs, "bad-manifest.mmsession")
        (bad / "manifest.json").write_bytes(b"{")
        live = _copy_package(receiver.inputs, "not-finalized.mmsession")
        manifest = json.loads((live / "manifest.json").read_text(encoding="utf-8"))
        manifest["state"] = "recording"
        _write_json(live / "manifest.json", manifest)
        missing = receiver.inputs / "missing-package.mmsession"
        mixed_inputs = [str(b), str(bad), str(a), str(missing), str(c), str(live)]
        mixed = receiver.outputs / "mixed"
        receiver.command("isolated-failures-between-good-packages", mixed_inputs, mixed, 1)
        mixed_doc = receiver.review(
            mixed, mixed_inputs, [qb, None, qa, None, qc, None], retain="mixed",
        )
        assert mixed_doc["collectedCount"] == 3 and mixed_doc["failedCount"] == 3
        assert mixed_doc["packages"][1]["error"]["type"] == "JSONDecodeError"
        assert mixed_doc["packages"][3]["error"]["type"]
        assert "final" in mixed_doc["packages"][5]["error"]["message"].lower()
        assert not missing.exists(), "Reading a missing requested package created it"
        receiver.report["mixedExpected"] = [qb, None, qa, None, qc, None]
        receiver.passed(
            "malformed, missing and nonfinalized packages remain explicit failures "
            "between complete later native reports, without partial bad QC or dropped entries"
        )

        assert all(item["inputUnchanged"] for item in receiver.report["commands"])
        assert all(item["applicationStateUnchanged"] for item in receiver.report["commands"])
        assert _snapshot(FIXTURE) == fixture_before
        receiver.passed(
            "every actual invocation conserves all owned input files and directories, "
            "retained processing sentinels, maintained fixture and native application state"
        )

        completed_before = {
            "ordered": _snapshot(ordered), "warnings": _snapshot(warning_output),
            "mixed": _snapshot(mixed),
        }
        manifest = json.loads((a / "manifest.json").read_text(encoding="utf-8"))
        manifest["sessionId"] = "fresh-explicit-review-only"
        _write_json(a / "manifest.json", manifest)
        stream = a / "sources/sim.emg.main/streams/sim.emg.main.batch/stream.json"
        metadata = json.loads(stream.read_text(encoding="utf-8"))
        metadata["nominalRateHz"] = 1750
        _write_json(stream, metadata)
        fresh_qc = _native(a)
        assert fresh_qc["manifestSha256"] != qa["manifestSha256"]
        assert fresh_qc["streams"][0]["nominalRateHz"] == 1750
        fresh = receiver.outputs / "fresh"
        receiver.command("fresh-explicit-invocation", [str(a)], fresh, 0)
        receiver.review(fresh, [str(a)], [fresh_qc], retain="fresh")
        assert completed_before == {
            "ordered": _snapshot(ordered), "warnings": _snapshot(warning_output),
            "mixed": _snapshot(mixed),
        }
        receiver.passed(
            "a new explicit collection observes then-current metadata and stream rate "
            "while every byte/directory of earlier completed review outputs stays exact"
        )

        upper = receiver.outputs / "thirty-two"
        repeated = [str(c)] * 32
        receiver.command("inclusive-thirty-two-package-boundary", repeated, upper, 0)
        upper_doc = receiver.review(upper, repeated, [qc] * 32)
        assert [item["ordinal"] for item in upper_doc["packages"]] == list(range(1, 33))
        receiver.report["upperBoundary"] = {
            "packageCount": 32, "outputInventory": _snapshot(upper),
            "reviewSha256": _sha((upper / "review.json").read_bytes()),
        }
        refusals: list[tuple[str, list[str], Path]] = [
            ("no-requested-package", [], receiver.outputs / "empty-request"),
            ("thirty-three-requested-packages", [str(c)] * 33, receiver.outputs / "too-many"),
            ("inside-existing-package", [str(a)], a / "processing/new-review"),
            ("inside-uncreated-descendant", [str(a)], a / "new-parent/new-review"),
            ("inside-normalized-parent-alias", [str(a)], a / "processing/../alias-review"),
            ("missing-output-parent", [str(c)], receiver.outputs / "no-parent/new-review"),
        ]
        for name, paths, destination in refusals:
            parents_before = _snapshot(receiver.outputs)
            destination_before = _snapshot(destination)
            receiver.command(name, paths, destination, 2)
            assert _snapshot(destination) == destination_before
            assert _snapshot(receiver.outputs) == parents_before, "Refusal created outside output"
        occupied_directory = receiver.outputs / "occupied-directory"
        occupied_directory.mkdir()
        (occupied_directory / "prior.bin").write_bytes(b"Prior authored export\x00\xff\n")
        occupied_file = receiver.outputs / "occupied-file"
        occupied_file.write_bytes(b"Prior authored file: do not replace.\x00\n")
        for destination in [occupied_directory, occupied_file, ordered, a]:
            before = _snapshot(destination)
            receiver.command("occupied-destination-" + destination.name, [str(c)], destination, 2)
            assert _snapshot(destination) == before
        receiver.passed(
            "actual CLI accepts all32 ordered positions and refuses zero/33 inputs, "
            "occupied and inside-package destinations, aliases and absent output parents"
        )

        if receiver.emit:
            _capture_browser(receiver, mixed, mixed_doc, tmp_path)
        assert _snapshot(FIXTURE) == fixture_before
        assert _snapshot(ordered) == old_ordered
    except BaseException as exc:
        error = exc
        raise
    finally:
        receiver.finish(error)


def _installed_browser() -> Path | None:
    candidates = []
    for name in ("msedge", "chrome", "google-chrome", "chromium"):
        found = shutil.which(name)
        if found:
            candidates.append(Path(found))
    for key in ("ProgramFiles", "ProgramFiles(x86)"):
        if os.environ.get(key):
            root = Path(os.environ[key])
            candidates.extend([
                root / "Microsoft/Edge/Application/msedge.exe",
                root / "Google/Chrome/Application/chrome.exe",
            ])
    return next((path for path in candidates if path.is_file()), None)


def _capture_browser(
    receiver: _Receiver, review: Path, doc: dict[str, Any], tmp_path: Path,
) -> None:
    browser = _installed_browser()
    node = shutil.which("node")
    if not browser or not node:
        receiver.report["browser"] = {
            "status": "unavailable", "installedBrowser": str(browser) if browser else None,
            "node": node, "meaning": "No actual browser-open or image claim; no runtime installed.",
        }
        return
    check = subprocess.run(
        [node, "-e",
         "console.log(process.version);process.exit(typeof WebSocket==='function'?0:3)"],
        capture_output=True, text=True, encoding="utf-8", timeout=15, check=False,
    )
    if check.returncode != 0:
        receiver.report["browser"] = {
            "status": "unavailable", "node": node, "preflightExit": check.returncode,
            "stdout": check.stdout, "stderr": check.stderr,
            "meaning": "Installed Node lacks native WebSocket; no browser framework was added.",
        }
        return
    expectations = {
        "rows": [
            {
                "ordinal": item["ordinal"], "inputPath": item["inputPath"],
                "packagePath": item["packagePath"], "status": item["status"],
                "sessionId": item["qc"]["sessionId"] if item["qc"] else None,
                "warnings": item["qc"]["warnings"] if item["qc"] else [],
                "lights": item["qc"]["trafficLights"] if item["qc"] else {},
                "error": item["error"],
            }
            for item in doc["packages"]
        ],
        "links": [
            path for item in doc["packages"] if item["reports"]
            for path in item["reports"].values()
        ],
        "nativeReport": {
            "path": "reports/001-qc.html",
            "text": [
                "Analysis QC", LITERAL, GAP_CAUSE, str(LARGE_LOSS),
                "2.000000007", doc["packages"][0]["qc"]["manifestSha256"],
            ],
        },
    }
    receiver.artifact(
        "browser/index-expectations.json", _json_bytes(expectations),
        "independent expectations from admitted native records",
    )
    argv = [
        node, str(BROWSER_HELPER), "--browser", str(browser), "--review", str(review),
        "--expectations", str(receiver.artifacts / "browser/index-expectations.json"),
        "--output", str(receiver.artifacts / "browser"),
        "--profile", str(tmp_path / "owned-qc-browser-profile"),
    ]
    process = subprocess.run(
        argv, cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
        errors="strict", timeout=180, check=False,
    )
    receiver.artifact(
        "browser/command.json",
        _json_bytes({
            "argv": argv, "exit": process.returncode, "nodePreflight": check.stdout,
            "stdout": process.stdout, "stderr": process.stderr,
        }),
        "actual installed-browser helper process",
    )
    report_path = receiver.artifacts / "browser/browser-report.json"
    if report_path.is_file():
        receiver.report["browser"] = json.loads(report_path.read_text(encoding="utf-8"))
    else:
        receiver.report["browser"] = {"status": "failed", "reason": "No actual browser report"}
    for name in (
        "browser-report.json", "index-desktop.png", "index-phone.png",
        "index-phone-failure.png", "native-report-desktop.png",
    ):
        path = receiver.artifacts / "browser" / name
        if path.is_file():
            assert not path.is_symlink()
            raw = path.read_bytes()
            receiver.report["artifacts"].append({
                "path": "browser/" + name, "bytes": len(raw), "sha256": _sha(raw),
                "kind": "actual native browser output",
            })
    print("CAPTURE_QC_REVIEW_BROWSER_PROCESS " + json.dumps({
        "exit": process.returncode, "stdout": process.stdout, "stderr": process.stderr,
    }), flush=True)
    assert process.returncode == 0, process.stdout + process.stderr
    assert receiver.report["browser"]["status"] == "passed"
    assert receiver.report["browser"]["externalPageRequests"] == []
    for name, width, height in (
        ("index-desktop.png", 1280, 1000), ("index-phone.png", 390, 844),
        ("index-phone-failure.png", 390, 844), ("native-report-desktop.png", 1280, 1000),
    ):
        raw = (receiver.artifacts / "browser" / name).read_bytes()
        assert raw[:8] == b"\x89PNG\r\n\x1a\n"
        assert int.from_bytes(raw[16:20], "big") == width
        assert int.from_bytes(raw[20:24], "big") == height


def _bundle(root: Path, report: dict[str, Any]) -> None:
    allowed = {"receiving-report.json"}
    for prefix, ordinals in (
        ("native", [1, 2]), ("ordered/reports", [1, 2]),
        ("warnings/reports", [1, 2]), ("mixed/reports", [1, 3, 5]),
        ("fresh/reports", [1]),
    ):
        for ordinal in ordinals:
            allowed.update(f"{prefix}/{ordinal:03d}-qc.{ext}" for ext in ("json", "html"))
    for prefix in ("ordered", "warnings", "mixed", "fresh"):
        allowed.update([prefix + "/review.json", prefix + "/index.html"])
    allowed.update(
        "browser/" + name for name in (
            "index-expectations.json", "command.json", "browser-report.json",
            "index-desktop.png", "index-phone.png", "index-phone-failure.png",
            "native-report-desktop.png",
        )
    )
    names = [item["path"] for item in report["artifacts"]] + ["receiving-report.json"]
    assert len(names) == len(set(names)), "Each fixed receiving member is emitted once"
    assert set(names).issubset(allowed), "No environment/source/profile file may enter the bundle"
    files = []
    total = 0
    for name in sorted(names):
        path = root / name
        assert path.resolve().is_relative_to(root.resolve())
        assert path.is_file() and not path.is_symlink()
        raw = path.read_bytes()
        assert len(raw) <= 2 * 1024 * 1024, "One fixture exceeds the 2 MiB receiving bound"
        total += len(raw)
        assert total <= 4 * 1024 * 1024, "Fixed packet exceeds its 4 MiB bound"
        expected = next((item for item in report["artifacts"] if item["path"] == name), None)
        if expected:
            assert expected["bytes"] == len(raw) and expected["sha256"] == _sha(raw)
        files.append({
            "path": name, "bytes": len(raw), "sha256": _sha(raw),
            "base64": base64.b64encode(raw).decode("ascii"),
        })
    payload = json.dumps({"version": 1, "files": files}, separators=(",", ":")).encode("utf-8")
    assert len(payload) <= 6 * 1024 * 1024, "Serialized fixture bundle exceeds 6 MiB"
    encoded = base64.b64encode(payload).decode("ascii")
    chunks = [encoded[offset:offset + 4096] for offset in range(0, len(encoded), 4096)]
    print("CAPTURE_QC_REVIEW_BUNDLE_BEGIN " + json.dumps({
        "bytes": len(payload), "sha256": _sha(payload), "chunks": len(chunks),
    }), flush=True)
    for ordinal, chunk in enumerate(chunks):
        print(f"CAPTURE_QC_REVIEW_BUNDLE_CHUNK {ordinal} {chunk}", flush=True)
    print("CAPTURE_QC_REVIEW_BUNDLE_END", flush=True)
