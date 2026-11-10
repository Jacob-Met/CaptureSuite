# Publishing the experimental native desktop

Use fleet workers for build, tests, native use and publication. No GitHub Actions
or personal workstation is part of this path. The existing
`scripts/build-desktop-linux.sh` creates the relocatable folder; the maintained
`tools/release_desktop.py` assembles, transfers and publishes its reviewed bytes.

## Build and review one exact commit

Use an isolated clean checkout at the intended full commit. Install the
dependencies documented in OFFLINE_DESKTOP_LINUX.md, then run the existing
builder with an isolated OUTPUT_ROOT. Confirm the bundled executable reports
that source. Exercise the actual application with genuine MCAP input and obtain
independent native-use judgment before publishing. The packet tool checks the
bundle SOURCE_COMMIT against the source requested for the release; it cannot
replace that real-use judgment.

Prepare a new packet directory after the commit is published to the repository:

```sh
python3 tools/release_desktop.py prepare \
  --source FULL_SOURCE_COMMIT \
  --bundle /worker/build/dist/capturesuite-desktop \
  --output /worker/release-packet \
  --tag native-desktop-DATE-SHORT_COMMIT \
  --title 'CaptureSuite experimental Linux desktop' \
  --notes /worker/reviewed-release-notes.md \
  --media /worker/reviewed-walkthrough.mp4 \
  --media /worker/reviewed-example.zip \
  --media /worker/reviewed-sync.png
```

This archives the entire native folder, makes corresponding source with
`git archive` at the exact commit, copies only explicitly named public media,
and writes SHA256SUMS plus release-packet.json. The manifest is an internal
transport recipe, not a published asset. No directory wildcard can accidentally
include private operator-path evidence. Review the media captions against the
actual footage; label simulated inputs and older-build demonstrations accurately.
The notes and every asset are hashed. Prepare refuses an existing output
directory so an earlier packet is retained.

## Transfer through an existing estate publisher

Run the same script on an already authorized publisher. The established route
uses Tailscale SSH from the publisher to the build worker; it needs no new Serve
port, grants, credential copies or network configuration.

```sh
python3 tools/release_desktop.py pull \
  --host ubuntu@BUILD_WORKER_TAILNET_IP \
  --remote-dir /worker/release-packet \
  --output /publisher/release-packet
python3 tools/release_desktop.py verify /publisher/release-packet
```

The script reads the small packet first, transfers only its explicit files,
verifies size and SHA256 before moving each incoming file into place, and skips
already verified files. A different existing destination or asset is an error;
use a new directory instead of overwriting it.

## Publish and recover an interrupted upload

Supply the publisher's existing GitHub authentication only to this command, using
its maintained profile. Do not copy tokens to the build worker or edit global
Git configuration. The tool itself never reads or installs credentials.

```sh
python3 tools/release_desktop.py publish \
  --packet /publisher/release-packet \
  --github-repo Jacob-Met/CaptureSuite --gh /usr/bin/gh
```

The tool inspects the tag and release before every attempt. Only an actual HTTP
404 means missing; connectivity, auth and quota errors stop the operation.
A new release starts as an experimental draft. Matching uploaded assets are
verified by GitHub SHA256 (or an actual download for older API responses), and
only missing draft assets are uploaded. Conflicting bytes, source, notes or
unexpected assets stop without overwriting anything. The script exposes the
release only after every expected asset has been verified. It then checks the
published tag resolves to the exact source and saves published-release.json.

If a command loses its response, preserve its fleet command/operation IDs and
first inspect the original receipt and GitHub destination. Once that original
operation has finished, rerunning publish reconciles matching assets; it does
not replace them. Do not run competing publishers for the same packet/tag.

Finally, have a different contributor download the published archive, verify
SHA256, extract it into a fresh directory and exercise the actual executable.
A successful upload is not receiving acceptance. Keep platform and source-use
claims separate. The b520 reference release proved Linux x86_64 only.
