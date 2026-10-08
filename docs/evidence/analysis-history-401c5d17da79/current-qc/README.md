# Current QC output and saved-history receiving

The author's runtime `37443f0d4d5ffa684b5423d58501856cadbe0655`
was qualified on canonical `72c15d6b623e217291a824e4e4808a385df896a9`.
Current main `e43da3b855475c8aacf815c201fa03eddaeec0f1` changes no
desktop or session-reader source, but its accepted QC producer now writes
`capture.analysis_qc/2` and HTML with recorded gap rows. This packet closes that
specific changed-input boundary.

Git's actual three-way merge, using the observed canonical base, produced
runtime tree `ba5b4b925b00ecb17895a8c8ad29410e787f97dc`. It changes only
the three history/runtime files and one focused test relative to current main;
779 unrelated current leaves and their modes remain exact. The publication
adds documentation and evidence after this runtime tree without changing its
Python or fixture bytes.

## Result

One real `QApplication.exec` event-loop scenario passed 14 assertions, exit 0,
in 3.471 seconds using the existing Python/PySide6 environment. A private copy
of the existing mini-session fixture receives one authored recorded gap,
then the unchanged current producer creates the retained QC result.

The receiver confirms the QC/2 schema, exact gap duration of 1,000,000,002 ns
and reported loss count of 3, plus the current HTML gap row. It opens that job
through the actual history controls, existing inspector and read-only Details
dialog; the existing report action is available and no computation thread is
started. All 18 retained package/job files and all 139 frozen source/fixture
files remain unchanged while browsing.

`current.stderr.log` retains Qt's standard offscreen
`This plugin does not support propagateSizeHints()` message. It contains no
other diagnostic. This is one current-dependency receiving scenario, separate
from the author's 14 tests and the independent receiver's 19 native checks.
It is not a full Windows, daemon, hardware or installed-release qualification.

## Exact receipts

| File | SHA-256 |
| --- | --- |
| `check_current_qc_history.py` | `469b3e3fd0403e420c847e1e4c11525b968055447aa2ecdd1024714e2c12039e` |
| `source-inputs.json` | `c41b5857ca1cca774d85298827c8f63a85dada025e2e326b51ce96de08e0ab0e` |
| `current-run/receipt.json` | `e12a6c87e4786a87b2adf5a295e1184d12e4a3ecebad6e4ca6e3b24beb1bd4ec` |
| `current.stdout.log` | `34b2748419db7460c2abff30184db5e7f12b075c1808667abcb065177dfd5025` |
| `current.stderr.log` | `caeb11f6473c6c7125dd27478e588b85ffd6b31784e9adb1371a60f1661eb00f` |

`process.json` retains the exact command, duration and process result. The
source manifest lists every input's Git blob, mode, byte length and SHA-256.
The fixture mutations are confined to the receiver's newly created directory;
the authored and canonical checkouts are never used as output directories.

## Replay

Use an existing Python 3.12 environment with CaptureSuite's dependencies. From
the composed checkout, materialize exactly the files listed by
`source-inputs.json` into a new source projection and verify their hashes.
Preserve their relative paths. Keep output outside that source and choose a
path that does not exist:

```sh
python -B check_current_qc_history.py \
  --source /absolute/path/to/verified-source-projection \
  --inputs /absolute/path/to/source-inputs.json \
  --output /absolute/path/to/new-private-output
```

The companion performs no dependency installation, uses private application
state directories and rejects changed or extra projected source files before
opening a widget. It uses the existing mini-session fixture and current
producer.
