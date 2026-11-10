# Qt/PySide notice provenance

The installed PySide6 6.12.0 Linux wheels omit license text files. These files
are unchanged upstream notice material retained for the desktop package.

- The manifest pins eight official source archive URLs and SHA-256 hashes.
  Each retained source file records its archive member and its own hash.
- Source collection includes module LICENSES, COPYING/copyright/notice files,
  qt_attribution.json, REUSE.toml and every referenced LicenseFile. It excludes
  example/test subtrees. It deliberately retains a conservative module-level
  superset; this is not a claim that every listed component is linked.
- Qt PDF's nine third-party attribution pages and module licensing page are
  preserved from the official Qt 6.12 documentation, with exact URLs/hashes.
  These are generated upstream notices, not a substitute invented license.
- ICU 73.2 uses its upstream version-tagged LICENSE. The collector calls the
  shipped ICU binary's version function and fails if it differs.

Run `python tools/verify_qt_notice_sources.py` to check retained bytes.
Add `--fetch` to independently redownload the pinned archives/pages and
compare every retained file with its upstream original. Changed remote
documentation fails verification rather than silently changing the notices.

The collector maps actual TOC source files to wheel RECORD ownership,
including native binaries and data. Namespace sharing does not establish
ownership. A bundled PDF plugin includes Pdf; merely importing PySide6
does not include WebEngine. Unknown native Qt libraries fail explicitly.
System libraries still use their installed package copyright records.

This directory supplies notice texts and source provenance. It does not
assert that copying notices alone fulfills every redistribution obligation.
The release retains the existing project licensing and source instructions.
