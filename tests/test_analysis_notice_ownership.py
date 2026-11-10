# SPDX-License-Identifier: GPL-3.0-only
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    "notices", Path(__file__).resolve().parents[1] / "tools/collect_analysis_notices.py"
)
notices = importlib.util.module_from_spec(spec)
spec.loader.exec_module(notices)


class Dist:
    def __init__(self, name, root, files):
        self.metadata = {"Name": name}
        self.root, self.files = root, files

    def locate_file(self, file):
        return self.root / file


class NoticeOwnershipTests(unittest.TestCase):
    def test_shared_namespace_is_not_distribution_ownership(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            toc = root / "Analysis.toc"
            toc.write_text(
                repr(
                    [
                        ("PySide6", str(root / "PySide6/__init__.py"), "PYMODULE"),
                        (
                            "PySide6/QtCore.abi3.so",
                            str(root / "PySide6/QtCore.abi3.so"),
                            "EXTENSION",
                        ),
                        (
                            "PySide6/Qt/plugins/imageformats/libqpdf.so",
                            str(root / "PySide6/Qt/plugins/imageformats/libqpdf.so"),
                            "BINARY",
                        ),
                    ]
                )
            )
            distributions = [
                Dist("PySide6_Essentials", root, ["PySide6/__init__.py", "PySide6/QtCore.abi3.so"]),
                Dist("PySide6_Pdf", root, ["PySide6/Qt/plugins/imageformats/libqpdf.so"]),
                Dist("PySide6_WebEngine", root, ["PySide6/QtWebEngineCore.abi3.so"]),
                Dist("PySide6", root, ["pyside6.dist-info/METADATA"]),
            ]
            with patch.object(notices.metadata, "distributions", return_value=distributions):
                got = notices.bundled_distribution_files(toc)
            self.assertEqual(set(got), {"PySide6_Essentials", "PySide6_Pdf", "pyinstaller"})
            self.assertEqual(len(got["PySide6_Pdf"]), 1)

    def test_pdf_uses_exact_upstream_chromium_version(self):
        self.assertEqual(notices.pyside_source_version("PySide6-Pdf", "6.12.0.140"), "6.12.0")
        self.assertEqual(notices.pyside_source_version("PySide6-WebEngine", "6.12.0.140"), "6.12.0")
        with self.assertRaises(ValueError):
            notices.pyside_source_version("PySide6-WebEngine", "6.12.0.141")
        with self.assertRaises(ValueError):
            notices.pyside_source_version("PySide6-Pdf", "6.12.0.141")
        with self.assertRaises(ValueError):
            notices.pyside_source_version("PySide6_Essentials", "6.12.0.140")

    def test_uncovered_native_qt_module_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            toc = Path(temp) / "Analysis.toc"
            toc.write_text(
                repr(
                    [
                        (
                            "libQt6WebEngineCore.so.6",
                            "/venv/PySide6/Qt/lib/libQt6WebEngineCore.so.6",
                            "BINARY",
                        )
                    ]
                )
            )
            with self.assertRaisesRegex(ValueError, "WebEngineCore"):
                notices.qt_notice_groups(toc)

    def test_indirect_native_modules_are_covered(self):
        with tempfile.TemporaryDirectory() as temp:
            toc = Path(temp) / "Analysis.toc"
            modules = [
                "Core",
                "Pdf",
                "Quick",
                "VirtualKeyboardQml",
                "WaylandClient",
                "FFmpegStub-ssl",
            ]
            toc.write_text(
                repr([(m, "/venv/PySide6/Qt/lib/libQt6" + m + ".so.6", "BINARY") for m in modules])
            )
            self.assertEqual(
                notices.qt_notice_groups(toc),
                {
                    "qtbase",
                    "qtpdf",
                    "qtdeclarative",
                    "qtvirtualkeyboard",
                    "qtwayland",
                    "qtmultimedia",
                },
            )


if __name__ == "__main__":
    unittest.main()
