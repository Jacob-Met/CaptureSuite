# SPDX-License-Identifier: GPL-3.0-only
"""Execute the exact package-reader component/tests in memory; no package init."""
import dataclasses
import hashlib
import io
import json
import linecache
import pathlib
import platform
import sys
import types
import typing
import unittest
import unittest.mock

payload = json.loads(sys.argv[1])
assert sys.dont_write_bytecode, "run with python -B"
assert payload["schema"] == "capture.gap-reader.memory-input.v1"
assert payload["variant"] in ("original", "candidate")
pins = {}
for name in ("reader", "tests"):
    raw = payload[name]["text"].encode("utf-8")
    git = hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()
    assert git == payload[name]["git_blob"], name + " Git content mismatch"
    pins[name] = {"git_blob": git, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}

package = types.ModuleType("capture_session")
package.__path__ = []
sys.modules["capture_session"] = package


def load(name, source, filename):
    module = types.ModuleType(name)
    module.__file__ = filename
    sys.modules[name] = module
    linecache.cache[filename] = (len(source), None, source.splitlines(True), filename)
    exec(compile(source, filename, "exec"), module.__dict__)
    return module


reader = load(
    "capture_session.package_reader", payload["reader"]["text"],
    "<memory>/libs/python/capture_session/capture_session/package_reader.py",
)
package.package_reader = reader
test_module = load(
    "capture_gap_reader_tests", payload["tests"]["text"],
    "<memory>/tests/test_package_reader_gaps.py",
)


class Result(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.successes = []

    def addSuccess(self, test):
        super().addSuccess(test)
        self.successes.append(test.id())


suite = unittest.defaultTestLoader.loadTestsFromTestCase(test_module.PackageReaderGapTests)
assert suite.countTestCases() == 11
stream = io.StringIO()
result = unittest.TextTestRunner(stream=stream, verbosity=2, resultclass=Result).run(suite)
receipt = {
    "schema": "capture.gap-reader.memory-result.v1",
    "variant": payload["variant"],
    "runtime": {"implementation": platform.python_implementation(), "version": sys.version,
                "platform": sys.platform, "dont_write_bytecode": sys.dont_write_bytecode},
    "input_sha256": hashlib.sha256(sys.argv[1].encode("utf-8")).hexdigest(),
    "sources": pins, "tests_run": result.testsRun, "successes": result.successes,
    "failures": [{"test": t.id(), "traceback": detail} for t, detail in result.failures],
    "errors": [{"test": t.id(), "traceback": detail} for t, detail in result.errors],
    "skipped": result.skipped, "unexpected_successes": len(result.unexpectedSuccesses),
    "expected_failures": len(result.expectedFailures),
    "all_passed": result.wasSuccessful(), "unittest_output": stream.getvalue(),
    "limits": ["Only reader.Path file I/O is adapted by the retained tests.",
               "No package initializer, real filesystem, Qt or Windows runtime qualification.",
               "This runner invokes no product child, daemon, hardware or provider."],
}
print(json.dumps(receipt, ensure_ascii=True, indent=2))
sys.exit(0 if result.wasSuccessful() else 1)
