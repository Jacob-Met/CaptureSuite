# Independent receiving: selected analysis figure export

Disposition: source and native component workflow accepted for publication. The repository's actual supported-platform CI and final current-tree receiving remain merge gates. This is a separate root receiver, not the feature author.

## Exact source and scope

Original primary source: CaptureSuite e43da3b855475c8aacf815c201fa03eddaeec0f1. Current author composition is 3e3ecc5ecc1cfc79c79901eb5cffe10b0ec5852e; the gallery baseline, producer jobs.py, theme and schema contracts received for this workflow are unchanged. Accepted helper SHA-256 cf510ab0f9693ed6961623099be30921eb64ee1d435d00c954ef229334ffb471; accepted dialog a918adbb80e73c220e46e0923fa6ff86a7c2ab336c2832aacbc39a2821df72d6; gallery86bf46e07f9978cb3403b88c485107bad9c7110e3ee5b0722fa7e97f697d1db7. The only post-initial-freeze dialog change is a four-line local disabled-button stylesheet. Its code diff was received, its actual author-rendered dark dialog was visually inspected, and the unchanged independent probe was rerun against the exact current source with every component hash checked before and after execution.

The spec's sections5/9 require selected figures and a PNG ZIP with manifest. The receiver independently read the actual gallery, job producer, manifest schema and Workbench spec. The source job manifest includes a historical self-entry from before its last write: the exporter correctly preserves those original bytes and calculates a separate actual input digest instead of treating the self-entry as current verification. Existing raw data and original job files remain read-only.

## Independent behavior

Frozen probe SHA-256 6d43689fcda5979c26611c0f8d0fcac5b14fe9da67673a7fa780126d07cf397e. It uses independently authored valid PNG bytes and capture.analysis_job/1 metadata, actual PySide6 widgets, keyboard/mouse events and a real QThread. The OS file-picker return is supplied deterministically; the tested selection, preview, export worker, output and gallery lifecycle are real native components.

The unchanged visible-gallery assertion fails on the original baseline because no export control exists. All16 independent cases pass with zero skips on both the initial candidate and accepted current source. They cover an explicit two-of-three subset (including Unicode/nested paths); exact PNG, original manifest and params bytes; verified actual input digests; preservation of recorded warnings/tooling/source paths; immutability of decoded provenance views; changed params/manifest/image refusal and retry; empty, duplicate and unrecorded selections; traversal/case aliases, invalid JSON constants and params mismatch; replacement of the loaded job directory; a destination created by another writer after initial selection; and Qt clear/reload binding the next dialog to the new job.

One independent case induces a real Linux RLIMIT_FSIZE/EFBIG failure while writing a large valid PNG to the temporary archive. The previous user export remains byte-exact, source hashes remain unchanged and the temporary export is removed. Another case proves an occupied destination is not overwritten without explicit replacement. These results concern returned failures and observed prepublication races; they are not a general crash-atomic or cross-process filesystem transaction guarantee.

## Original environment evidence

The first candidate invocation created the temporary directory in an earlier exec call. This environment gives each exec its own /dev tmpfs, so that invocation had one passing availability case and15 fixture-setup errors. The exact output is retained as environment-first-attempt; it is not a production failure or a passing qualification. Creating the task-owned temporary root, running the unchanged probe and returning the full receipt within one exec resolved that harness placement error. The original16-case probe and production source were unchanged. All subsequent logs/XML are retained separately, with their exact source pins.

## Limits

Native receiving is Python3.12.14 and actual Linux/offscreen Qt; it does not establish supported Windows, capture hardware, installation or live-user adoption. Windows CI must receive the actual published merge tree. Root inspected the QSS-successor screenshot only as a layout/state check; scientific plots are authored fixtures. No patient data, live capture, provider, native service or other worker checkout was modified. Original negative evidence, component snapshots and all exact receipts are preserved in this capsule.
