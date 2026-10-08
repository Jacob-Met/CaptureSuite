# Current-source QC receiving supplement

The accepted QC/report source also passes receiving against the newer stream-gap
and registry changes. This supplement preserves that replay without changing any
of the 46 accepted source, test, documentation or evidence files.

## Exact composition

The native replay used receiving commit
`6b22d61260bff5b8304c33c48ed74366e08b414b`, with only the two already qualified
QC/report blobs applied. Since the earlier independent review, the receiving
closure changed in `capture_analysis/windows.py` (stream-gap scope) and
`capture_session/registry.py` (read-only registry opening). Both exact current
blobs were included in candidate and baseline.

The subsequent camera merge produced receiving commit
`93254f1293390b2acc6c746237ada4575f777a9e`, tree
`6219a0bda3e312c0643fe16fb5b7dc7d0a73fecf`. All 100 baseline references in
[source-closure.json](source-closure.json) remain identical on that newer
commit; all 98 unowned receiver files, including current protocol framing, are
preserved. The camera changes fall outside this closure. Root instructions are
unchanged. No additional suite was needed after that source comparison.

[receiving-equivalence.json](receiving-equivalence.json) binds the complete
receiving tree, changed dependency blobs, source pins, exact progress prefix and
unchanged owned append. It is a repository-relative publication summary of the
preflight receipt; the execution traces below retain their original bytes.

## Native results

| Replay | Result |
| --- | --- |
| Candidate on current dependencies | 7 passed; no failures, errors or skips |
| Original QC, real CLI gap control | 1 expected failure: green source, no gap inventory, exit 0 |
| Original QC, real CLI no-gap control | 1 passed |
| Candidate real CLI gap case | Exit 2; completed with warnings; affected source warned |
| Candidate real CLI no-gap case | Exit 0; completed; sources healthy |

Every actual CLI replay preserves all 12 raw package-file hashes. The existing
harness also verifies QC JSON and HTML hashes and byte counts against their job
manifest entries. Four complete CLI receipts are under `evidence/`, including
both original-code controls and both candidate outcomes.

The [execution receipt](execution-receipt.json), raw result logs and JUnit files
record the actual commands, runtime versions, outcome counts and content hashes.
The already published [independent harness](../independent-review/test_independent_capture_receiving.py)
was reused unchanged (SHA-256
`9131bec9582e80daec244f481eeb2f2cd2117d7f058676f5ae4eb41f594d02fc`).
This is the author's current-source replay of that harness, not a second
independent review. Python 3.12.14 and the same installed scientific libraries
and jsonschema 4.26.0 were reused; nothing was installed or downloaded.

For a fresh reproduction, copy the published harness into a private review
directory, set `CAPTURE_REVIEW_CHECKOUT` to the intended exact source composition,
set private `TMPDIR` and `MPLCONFIGDIR`, and invoke it with pytest and
`-p no:cacheprovider`. The baseline restores the two original QC/report blobs
while retaining the current dependency composition.

## Boundary

This replay qualifies native offline QC reporting. The earlier full-analysis
run and its two missing-dependency failures and three existing skips remain
unchanged evidence. Exact-head hosted Python and CMake/CTest/native integration
gates remain separate. This supplement makes no physical-capture, deployment,
or installed-application adoption claim.
