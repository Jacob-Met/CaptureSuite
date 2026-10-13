<!-- SPDX-License-Identifier: GPL-3.0-only -->
# Review two saved QC reports offline

Use this standalone command when you already have two CaptureSuite QC JSON reports and want one directly openable comparison page:

```console
python tools/view_qc_comparison.py before-qc.json after-qc.json --output new-review.html
```

Use existing Python 3.12 or later. Keep the adjacent unchanged `compare_qc_reports.py` and `qc_comparison.html` with the command. The full desktop and numerical dependencies are not needed. Copy or download the generated HTML and open it locally in a browser with JavaScript enabled. It uses no external scripts, fonts, network calls or session-package reads.

This adds a saved-result consumer. It does not replace the native desktop, existing single-QC renderer or multi-package review command. The existing [saved QC comparator](COMPARE_SAVED_QC.md) remains the authority for complete admission and literal comparison.

## Read the page

The two identity cards show each selected file's name, recorded session and package labels, exact captured byte count and full SHA-256. Labels appear as quoted JSON strings, including explicit escapes for Unicode and control characters. The raw hash includes original formatting.

Every typed difference retains its original sorted JSON Pointer. Arrays keep saved positions: the page does not align streams by ID or merge repeated warnings or gaps. Use **Difference kind** and **Pointer contains** together. Pointer search is a case-sensitive literal substring, without regular expressions or pointer decoding. `/gaps/0/` shows fields under the first saved gap; a key containing `/` appears escaped as `~1`.

Select **Inspect** to read both complete values and their types. Selection moves keyboard focus to the detail heading. Values longer than 140 characters are abbreviated only in the table; details and the comparison download remain complete. Details can scroll independently.

Use **Previous matching change** and **Next matching change** in the detail panel to inspect adjacent differences in the complete filtered order. The position label **Matching change N of M** counts that sequence; original difference numbers and JSON Pointers remain unchanged. Moving beyond the current 50-row page automatically shows the selected change's page and focuses its detail heading. Navigation stops at either endpoint, never wraps and is disabled until a change is selected. Both buttons are disabled when only one change matches. Standard button keyboard activation works; no global shortcut is added.

Each page contains at most 50 matching differences. Filters reset to page 1. Changing filters or manually changing page, or choosing **Reset view**, clears the prior selection and position label and disables both matching-change buttons. No hits and equal parsed reports have explicit empty states. Narrow screens keep the table in its own horizontal scroll region. System light/dark preference uses CaptureSuite design tokens.

The browser receives report values as Python-formatted JSON **text**; it does not convert report integers or floats through JavaScript Number. An integer above 2^53 therefore remains exact. `false`, `0`, `0.0`, `-0.0`, `null` and `(absent)` remain distinct. Types are `boolean`, `integer`, `float`, `null`, `string`, `array`, `object` or `absent`. Present values use canonical ASCII JSON with sorted object keys, compact separators and explicit escapes. An absent side has no value; its visible label is `(absent)`.

These are parsed-value semantics, not original number-token spelling. Python binary64 parsing and the comparator's signed-zero rule still apply. `1e0` and `1.0` compare equal; integer `-0` parses as integer `0`. Original whitespace and spelling remain in the exact original downloads.

## Keep the captured evidence

- **Download first/second original JSON** saves exact captured bytes. The selected basename is a filename suggestion; browsers may normalize unsupported filename characters.
- **Download complete comparison JSON** saves `qc-comparison.json`: the existing `capture.saved_qc_comparison/1` report, both full parsed documents and every literal difference, serialized as canonical compact ASCII JSON plus one newline.
- A download request does not prove the browser or operating system wrote a file. Check actual saved bytes when transporting evidence.
- Printing captures the current filtered page and selected details. It is not an all-pages export; use the complete comparison JSON.

A captured hash identifies input bytes actually read. Recorded package paths and manifest hashes remain unverified claims. The page follows neither path, recomputes no gap duration/count and assigns no quality ranking.

## CLI and API

```python
from view_qc_comparison import render_comparison_html

html = render_comparison_html(
    before_bytes, after_bytes,
    first_name="before-qc.json", second_name="after-qc.json",
)
```

The API takes captured bytes and returns a complete string. Both reports undergo unchanged public `compare_bytes` admission before presentation or template reading. Each name must be a string of at most 4,096 characters. Complete UTF-8 HTML must fit within 64 MiB, including original captures, the comparison download and display model.

Inherited comparator bounds remain 2 MiB per input, 64 nested containers, 50,000 value nodes and a 16 MiB complete comparison. QC versions 1 and 2 retain existing required-field/type checks. Duplicate keys, invalid encoding, unsupported schemas, nonfinite values and complete-result overflow are refused. Unknown extensions and inconsistent recorded values remain visible. The comparator guide defines the exact admission contract.

The CLI captures explicit regular files once with a bounded sentinel read. Directories and FIFOs are refused without waiting for a writer; symlinks to regular inputs are permitted. Later input changes do not alter the capture or page. There is no file lock, stable-path guarantee or automatic refresh. No input package is opened or rewritten.

| Exit | Meaning |
| --- | --- |
| 0 | Complete new HTML published; equal and different comparisons both succeed. |
| 2 | An ordinary read, admission, render or publication operation failed. |
| Help/usage | Standard argparse behavior. |

Successful publication is silent on stdout. Error diagnostics quote their text on stderr. A missing or failed diagnostic stream does not turn failure into success.

The destination parent must already exist. The command writes and flushes a private temporary file beside the destination, then publishes with an exclusive hard link. Occupied names, aliases, directories and dangling symlinks are refused without replacement. Filesystems that do not support this operation receive no overwrite fallback.

Before the link succeeds, failure leaves no published output; cleanup removes only the owned temporary. Cleanup failure may leave a temporary file. After the link succeeds, cleanup failure returns 2 and explicitly states that the complete output was published. Do not interpret every exit 2 as rollback. No directory-fsync/crash durability or concurrent directory stability guarantee is made. Native Linux is the focused receiving platform; Windows filesystems and installed desktop integration need separate qualification.

Ordinary CLI use creates no caches beside these tools. API import temporarily suppresses the adjacent comparator's cache and restores the caller's bytecode policy in `finally`. The viewer's own cache follows normal importer policy, and later unrelated imports retain the caller's setting.

## Retained example and focused checks

The retained producer pair from issue135 has nine positional changes, including an open gap becoming closed with recorded duration 17 ns and a start timestamp string above 2^53. Other rows describe saved package paths, counts and positional warnings. These packages are authored synthetic fixtures; the result makes no patient-data, hardware or clinical-validity claim.

```console
python -B -m unittest discover -s tests/analysis -p test_saved_qc_comparison_view.py -v
```

Source checks cover captured-byte/comparison parity, typed display, literal labels, complete refusal, bounds, real CLI preservation, occupied/aliased outputs, nonregular inputs, arriving destinations, write/link/cleanup failures and import policy. The FIFO control is POSIX-specific. Actual browser controls, downloads, narrow layout and screenshot review are qualified separately at exact source pins; syntax checking alone is not browser acceptance.


### Focused matching-change navigation

```console
python -B -m unittest discover -s tests/analysis -p test_saved_qc_navigation.py -v
```

The focused controls require an existing Node executable. They execute the actual
inline script through a bounded DOM adapter, checking full filtered order,
endpoint refusal, page crossing, selection clearing, literal typed details and
all three complete downloads. They do not qualify native keyboard behavior or
layout; those remain separately received in a real browser. The command above
uses `-B` only to keep developer test imports from writing source-adjacent caches;
ordinary page generation needs no such override.
