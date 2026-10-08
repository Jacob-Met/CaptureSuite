# Included software and source records

CaptureSuite source and license are copied from the pinned canonical commit. MCAP headers and license are copied from its pinned native checkout. The corresponding license texts are retained under `notices/`; this file does not replace them.

The packaged dynamic libraries come from the existing Homebrew versions spdlog 1.17.0, fmt 12.2.0, protobuf 36.2 (including utf8_validity), Abseil 20260817.0, Zstandard 1.5.7_1, LZ4 1.10.0 and BLAKE3 1.8.7. Their original paths, file hashes and copied load commands are in `runtime-manifest.json`. The installed license files and available formula source definitions are included.

BLAKE3's installed Cellar directory did not include license files. The three upstream license files were fetched from tag 1.8.7's exact commit `f3149ec5bb5449af877ba20377a11008ff499fa2` and checked against their Git blob IDs. Its installed formula records the source archive URL and SHA-256. `notices/manifest.json` records each notice's origin and bytes.

macOS libraries under `/usr/lib` and `/System/Library` remain system dependencies and are not copied into the receiver. This package is held as a local native receiver; no public binary release or installer has been published.

The project's own licensing split is retained in source/LICENSING.md and source/NOTICE. Included schemas retain their separate source/schemas/LICENSE and source/schemas/NOTICE. These four files are exact canonical copies, listed in source-notices-manifest.json.
