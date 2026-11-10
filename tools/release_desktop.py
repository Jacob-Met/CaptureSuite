#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Prepare, transfer and publish an exact-source experimental desktop release."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shlex
import shutil
import subprocess
import tarfile
from pathlib import Path

MANIFEST = "release-packet.json"
CHECKSUMS = "SHA256SUMS"


def run(*args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def safe_name(name):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", name):
        raise ValueError(f"Unsafe asset name: {name!r}")
    return name


def entry(path):
    return {"name": safe_name(path.name), "size": path.stat().st_size, "sha256": digest(path)}


def verify_packet(folder):
    packet = json.loads((folder / MANIFEST).read_text())
    if packet["schema"] != "capture.desktop.release/1":
        raise ValueError("Unsupported release packet")
    if not re.fullmatch(r"[0-9a-f]{40}", packet["source"]):
        raise ValueError("Source must be a full Git commit")
    safe_name(packet["tag"])
    names = [item["name"] for item in packet["assets"]]
    if len(names) != len(set(names)) or CHECKSUMS not in names:
        raise ValueError("Duplicate assets or missing checksums")
    for item in [*packet["assets"], packet["notes"]]:
        path = folder / safe_name(item["name"])
        if path.is_symlink() or entry(path) != item:
            raise ValueError(f"Packet does not match file: {path.name}")
    sums = "".join(
        f"{item['sha256']}  {item['name']}\n"
        for item in packet["assets"]
        if item["name"] != CHECKSUMS
    )
    if (folder / CHECKSUMS).read_text() != sums:
        raise ValueError("SHA256SUMS does not match the packet")
    return packet


def prepare(args):
    repo, bundle, out = args.repo.resolve(), args.bundle.resolve(), args.output.resolve()
    source = run(
        "git",
        "-C",
        str(repo),
        "rev-parse",
        args.source + "^{commit}",
        capture_output=True,
        text=True,
    ).stdout.strip()
    if (bundle / "SOURCE_COMMIT").read_text().strip() != source:
        raise ValueError("Built SOURCE_COMMIT differs from requested source")
    for name in ("capturesuite-desktop", "NOTICE", "LICENSE", "THIRD_PARTY_NOTICES/manifest.json"):
        if not (bundle / name).is_file():
            raise ValueError(f"Missing required bundle file: {name}")
    if bundle.name != "capturesuite-desktop":
        raise ValueError("Bundle folder must be named capturesuite-desktop")
    out.mkdir(parents=True, exist_ok=False)
    native = out / "capturesuite-desktop-linux-x86_64.tar.gz"
    with tarfile.open(native, "w:gz") as archive:
        archive.add(bundle, arcname=bundle.name)
    source_archive = out / f"CaptureSuite-source-{source[:7]}.tar.gz"
    run(
        "git",
        "-C",
        str(repo),
        "archive",
        "--format=tar.gz",
        "--prefix=CaptureSuite/",
        "-o",
        str(source_archive),
        source,
    )
    assets = [entry(native), entry(source_archive)]
    reserved = {MANIFEST, CHECKSUMS, "release-notes.md", native.name, source_archive.name}
    for media in args.media:
        name = safe_name(media.name)
        if name in reserved:
            raise ValueError(f"Duplicate or reserved asset: {name}")
        reserved.add(name)
        shutil.copyfile(media, out / name)
        assets.append(entry(out / name))
    shutil.copyfile(args.notes, out / "release-notes.md")
    (out / CHECKSUMS).write_text("".join(f"{item['sha256']}  {item['name']}\n" for item in assets))
    assets.append(entry(out / CHECKSUMS))
    packet = {
        "schema": "capture.desktop.release/1",
        "source": source,
        "tag": args.tag,
        "title": args.title,
        "assets": assets,
        "notes": entry(out / "release-notes.md"),
    }
    (out / MANIFEST).write_text(json.dumps(packet, indent=2) + "\n")
    verify_packet(out)
    print(f"Verified release packet: {out}")


def pull(args):
    """Run on an existing publisher; transfer only explicit packet files over SSH."""
    folder = args.output.resolve()
    folder.mkdir(parents=True, exist_ok=True)

    def receive(name, target):
        remote = str(args.remote_dir / safe_name(name))
        with target.open("wb") as stream:
            run(
                "tailscale",
                "ssh",
                args.host,
                "-o",
                "BatchMode=yes",
                "-o",
                "ConnectTimeout=8",
                "cat",
                shlex.quote(remote),
                stdout=stream,
            )

    pending = folder / (MANIFEST + ".incoming")
    receive(MANIFEST, pending)
    packet = json.loads(pending.read_text())
    current = folder / MANIFEST
    if current.exists() and current.read_bytes() != pending.read_bytes():
        raise ValueError("Destination contains a different packet; use a new directory")
    pending.replace(current)
    for item in [*packet["assets"], packet["notes"]]:
        name = safe_name(item["name"])
        target = folder / name
        if target.exists():
            if entry(target) != item:
                raise ValueError(f"Existing destination differs: {name}")
            print(f"Already verified: {name}")
            continue
        partial = folder / (name + ".incoming")
        receive(name, partial)
        if partial.stat().st_size != item["size"] or digest(partial) != item["sha256"]:
            raise ValueError(f"Transferred file differs: {name}")
        partial.replace(target)
        print(f"Transferred and verified: {name}")
    verify_packet(folder)


class GitHub:
    def __init__(self, executable, repo):
        self.executable, self.repo = executable, repo

    def api(self, path, missing_ok=False):
        result = subprocess.run(
            [self.executable, "api", f"repos/{self.repo}/{path}"],
            capture_output=True,
            text=True,
        )
        if result.returncode:
            # Never interpret network/auth/rate-limit failures as an absent release.
            if missing_ok and "(HTTP 404)" in result.stderr:
                return None
            raise RuntimeError(result.stderr.strip())
        return json.loads(result.stdout)

    def release(self, tag):
        return self.api("releases/tags/" + tag, missing_ok=True)

    def command(self, *args):
        run(self.executable, "release", *args, "--repo", self.repo)

    def asset_digest(self, asset, folder):
        remote_digest = asset.get("digest")
        if remote_digest and remote_digest.startswith("sha256:"):
            return remote_digest[7:]
        # Older GitHub responses lack digest. Verify bytes without replacing assets.
        target = folder / (str(asset["id"]) + ".verify-download")
        with target.open("wb") as stream:
            run(
                self.executable,
                "api",
                f"repos/{self.repo}/releases/assets/{asset['id']}",
                "-H",
                "Accept: application/octet-stream",
                stdout=stream,
            )
        result = digest(target)
        target.unlink()
        return result


def publish(args, github=None):
    folder = args.packet.resolve()
    packet = verify_packet(folder)
    gh = github or GitHub(args.gh, args.github_repo)
    source, tag = packet["source"], packet["tag"]
    # A tag is the source authority; do not rely on target_commitish after tag creation.
    tag_ref = gh.api("git/ref/tags/" + tag, missing_ok=True)
    commit = gh.api("commits/" + tag) if tag_ref is not None else None
    if commit is not None and commit["sha"] != source:
        raise ValueError("Existing tag points to a different source")
    remote_source = gh.api("commits/" + source)
    if remote_source["sha"] != source:
        raise ValueError("Requested source is not published")
    release = gh.release(tag)
    if release is None:
        gh.command(
            "create",
            tag,
            "--draft",
            "--prerelease",
            "--target",
            source,
            "--title",
            packet["title"],
            "--notes-file",
            str(folder / packet["notes"]["name"]),
        )
        release = gh.release(tag)
        if release is None:
            raise RuntimeError("Creation outcome unknown; inspect destination before retry")
    if commit is None and release.get("target_commitish") != source:
        raise ValueError("Existing draft targets a different source")
    if not release["prerelease"]:
        raise ValueError("Existing release is not experimental; refusing to alter it")
    if release.get("body", "").strip() != (folder / packet["notes"]["name"]).read_text().strip():
        raise ValueError("Existing release notes differ from reviewed packet")
    existing = {asset["name"]: asset for asset in release["assets"]}
    expected = {item["name"] for item in packet["assets"]}
    if set(existing) - expected:
        raise ValueError("Release contains unexpected assets; inspect it before proceeding")
    for item in packet["assets"]:
        asset = existing.get(item["name"])
        if asset:
            if asset["size"] != item["size"] or gh.asset_digest(asset, folder) != item["sha256"]:
                raise ValueError(f"Existing asset differs: {item['name']}")
            print(f"Already verified on GitHub: {item['name']}")
        else:
            if not release["draft"]:
                raise ValueError("Published release is incomplete; inspect before changing it")
            gh.command("upload", tag, str(folder / item["name"]))
    # Read all uploaded bytes/digests before exposing the draft.
    complete = gh.release(tag)
    assets = {item["name"]: item for item in complete["assets"]}
    if set(assets) != expected:
        raise ValueError("Remote asset set is incomplete")
    for item in packet["assets"]:
        remote = assets[item["name"]]
        if remote["size"] != item["size"] or gh.asset_digest(remote, folder) != item["sha256"]:
            raise ValueError(f"Remote verification failed: {item['name']}")
    if complete["draft"]:
        gh.command("edit", tag, "--draft=false", "--prerelease")
    final = gh.release(tag)
    tag_commit = gh.api("commits/" + tag)
    if final["draft"] or not final["prerelease"] or tag_commit["sha"] != source:
        raise ValueError("Final release identity verification failed")
    (folder / "published-release.json").write_text(json.dumps(final, indent=2) + "\n")
    print(final["html_url"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("prepare")
    p.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    p.add_argument("--source", required=True)
    p.add_argument("--bundle", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--tag", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--notes", type=Path, required=True)
    p.add_argument("--media", type=Path, action="append", default=[])
    p.set_defaults(action=prepare)
    p = commands.add_parser("pull")
    p.add_argument("--host", required=True, help="Existing Tailscale SSH user@host")
    p.add_argument("--remote-dir", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.set_defaults(action=pull)
    p = commands.add_parser("verify")
    p.add_argument("packet", type=Path)
    p.set_defaults(action=lambda a: print(json.dumps(verify_packet(a.packet), indent=2)))
    p = commands.add_parser("publish")
    p.add_argument("--packet", type=Path, required=True)
    p.add_argument("--github-repo", default="Jacob-Met/CaptureSuite")
    p.add_argument("--gh", default="gh")
    p.set_defaults(action=publish)
    args = parser.parse_args()
    args.action(args)


if __name__ == "__main__":
    main()
