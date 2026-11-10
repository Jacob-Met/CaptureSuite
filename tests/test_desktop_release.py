# SPDX-License-Identifier: GPL-3.0-only
"""Release recovery tests: never expose partial or mismatched packages."""
import copy
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

SPEC = importlib.util.spec_from_file_location(
    "release_desktop", Path(__file__).parents[1] / "tools/release_desktop.py"
)
release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release)


@pytest.fixture
def packet(tmp_path):
    files = []
    for name, data in (("native.tar.gz", b"native"), ("source.tar.gz", b"source")):
        path = tmp_path / name
        path.write_bytes(data)
        files.append(release.entry(path))
    (tmp_path / release.CHECKSUMS).write_text(
        "".join(f'{x["sha256"]}  {x["name"]}\n' for x in files)
    )
    files.append(release.entry(tmp_path / release.CHECKSUMS))
    notes = tmp_path / "release-notes.md"
    notes.write_text("Experimental build; independently reviewed.")
    value = {
        "schema": "capture.desktop.release/1", "source": "a" * 40,
        "tag": "native-test", "title": "Experimental test",
        "assets": files, "notes": release.entry(notes),
    }
    (tmp_path / release.MANIFEST).write_text(json.dumps(value))
    return SimpleNamespace(packet=tmp_path, gh="gh", github_repo="owner/repo"), value


class MemoryGitHub:
    def __init__(self, packet, folder):
        self.packet, self.folder = packet, folder
        self.current = None
        self.commands = []
        self.interrupt = False

    def api(self, path, missing_ok=False):
        if path == "commits/" + self.packet["source"] or self.current and not self.current["draft"]:
            return {"sha": self.packet["source"]}
        return None

    def release(self, tag):
        return copy.deepcopy(self.current)

    def command(self, *args):
        self.commands.append(args)
        if args[0] == "create":
            self.current = {
                "draft": True, "prerelease": True, "assets": [],
                "target_commitish": self.packet["source"],
                "body": (self.folder / "release-notes.md").read_text(),
                "html_url": "https://example.invalid/release",
            }
        elif args[0] == "upload":
            item = release.entry(Path(args[2]))
            self.current["assets"].append(item)
            # Simulate a lost response AFTER GitHub durably accepted the bytes.
            if self.interrupt:
                self.interrupt = False
                raise ConnectionError("response lost")
        elif args[0] == "edit":
            assert len(self.current["assets"]) == len(self.packet["assets"])
            self.current["draft"] = False

    def asset_digest(self, item, folder):
        return item["sha256"]


def test_interrupted_upload_inspects_and_resumes_without_replacing_bytes(packet):
    args, data = packet
    gh = MemoryGitHub(data, args.packet)
    gh.interrupt = True
    with pytest.raises(ConnectionError):
        release.publish(args, gh)
    assert gh.current["draft"]
    assert len(gh.current["assets"]) == 1
    release.publish(args, gh)
    assert not gh.current["draft"]
    assert len([cmd for cmd in gh.commands if cmd[0] == "create"]) == 1
    uploads = [cmd[2] for cmd in gh.commands if cmd[0] == "upload"]
    assert len(uploads) == len(set(uploads)) == 3
    before = len(gh.commands)
    release.publish(args, gh)
    assert len(gh.commands) == before


def test_mismatching_remote_asset_keeps_draft_and_does_not_overwrite(packet):
    args, data = packet
    gh = MemoryGitHub(data, args.packet)
    gh.interrupt = True
    with pytest.raises(ConnectionError):
        release.publish(args, gh)
    gh.current["assets"][0]["sha256"] = "0" * 64
    before = len(gh.commands)
    with pytest.raises(ValueError, match="Existing asset differs"):
        release.publish(args, gh)
    assert len(gh.commands) == before
    assert gh.current["draft"]


def test_changed_local_bytes_rejected_before_any_network_operation(packet):
    args, data = packet
    gh = MemoryGitHub(data, args.packet)
    (args.packet / "native.tar.gz").write_bytes(b"replaced")
    with pytest.raises(ValueError, match="does not match"):
        release.publish(args, gh)
    assert not gh.commands


def test_wrong_existing_tag_rejected_before_mutation(packet):
    args, data = packet
    gh = MemoryGitHub(data, args.packet)
    gh.api = lambda *a, **kw: {"sha": "b" * 40}
    with pytest.raises(ValueError, match="different source"):
        release.publish(args, gh)
    assert not gh.commands


def test_prepare_archives_exact_source_and_rejects_wrong_build_pin(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    release.run("git", "init", "-q", str(repo))
    (repo / "app.py").write_text("print('source at commit')\n")
    release.run("git", "-C", str(repo), "add", "app.py")
    release.run("git", "-C", str(repo), "-c", "user.name=Release test",
                "-c", "user.email=release@example.invalid", "commit", "-qm", "Source")
    source = release.run("git", "-C", str(repo), "rev-parse", "HEAD",
                         capture_output=True, text=True).stdout.strip()
    bundle = tmp_path / "capturesuite-desktop"
    (bundle / "THIRD_PARTY_NOTICES").mkdir(parents=True)
    for name in ("capturesuite-desktop", "NOTICE", "LICENSE", "THIRD_PARTY_NOTICES/manifest.json"):
        (bundle / name).write_text("test-only bundle")
    (bundle / "SOURCE_COMMIT").write_text(source)
    notes = tmp_path / "notes.md"
    notes.write_text("Test packet")
    args = SimpleNamespace(repo=repo, bundle=bundle, output=tmp_path / "packet",
                           source=source, tag="native-test", title="Test", notes=notes, media=[])
    # Uncommitted work must not leak into the corresponding source archive.
    (repo / "app.py").write_text("changed after build\n")
    release.prepare(args)
    result = release.verify_packet(args.output)
    assert result["source"] == source
    with release.tarfile.open(args.output / f"CaptureSuite-source-{source[:7]}.tar.gz") as archive:
        assert archive.extractfile("CaptureSuite/app.py").read() == b"print('source at commit')\n"
    (bundle / "SOURCE_COMMIT").write_text("b" * 40)
    args.output = tmp_path / "wrong-packet"
    with pytest.raises(ValueError, match="SOURCE_COMMIT"):
        release.prepare(args)
    assert not args.output.exists()
