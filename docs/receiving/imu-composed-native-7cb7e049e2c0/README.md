# CaptureSuite IMU composition: Windows receiving supplement

**Published product:** [223e6926438b63dd848225da070f71575703c4cb](https://github.com/Jacob-Met/CaptureSuite/commit/223e6926438b63dd848225da070f71575703c4cb)  
**Issue:** [CaptureSuite #121](https://github.com/Jacob-Met/CaptureSuite/issues/121)

The composed offline analysis source is now received on the existing isolated MSI Windows environment. The maintained gate passed **183 concrete tests and 24 subtests** (207 aggregate JUnit tests), with zero failures, errors or skips. Eight actual MCAP feature jobs then reproduced the expected exact signed-int64 markers while preserving raw arrays, nineteen non-time feature columns and schemas.

This supplement adds native evidence to the immutable [portable source and replay kit](https://drive.google.com/file/d/1DC4JQJ82p3BE2j-AfNi0F-kUc9k6PlgD/view). That original 707,504-byte kit, SHA256 `1194ba109ce0c351af300bff845a480d35c2d6a2f307dc3e9b15f265379a6b07`, is unchanged. Its local missing-jsonschema warning and native-pending statements describe its earlier receiving stage. This supplement does not rewrite that history.

## Exact native result

| Case | Baseline marker (ns) | Composed marker (ns) | Native job status for both |
| --- | ---: | ---: | --- |
| Ordinary control | 3 | 3 | completed |
| Large odd median | 9007199254740996 | 9007199254740995 | completed |
| Upper signed-int64 pair | 9223372036854775808 | 9223372036854775806 | completed |
| Negative pair | -9007199254740992 | -9007199254740993 | completed_with_warnings |

The negative pair retains the inherited QC warning that package duration is unknown/zero. The explicit signed selection bounds remain correct and keep loading bounded. The native interpreter already has jsonschema; none of these eight native jobs has the portable environment's missing-validator warning. All eight manifests have empty error lists. The six nonnegative jobs have no warnings.

Each candidate marker is signed int64. The original upper-limit marker is uint64, outside the signed range. Raw fixtures, decoded signed timestamps, sensor arrays, feature schemas and nineteen non-time columns are preserved exactly within each pair. The accepted numerical implementation is unchanged from the original issue #121 source `865f3900590da523ab66434b581e2ebb3688be1c`.

A read-only comparison against the retained portable run found all four raw MCAP files, eight Parquet files and eight feature schemas byte-identical across platforms. The eight CSV files differ only in line endings: Windows uses CRLF and the local run uses LF. Their bytes agree after that single normalization. No job was rerun for this comparison.

The 183-case gate recorded 34 inherited warnings: 32 missing-font-glyph warnings and two protobuf deprecation warnings. It recorded zero Windows WMI `0x8007000e` diagnostics. This is a focused analysis gate, not a full desktop build or hardware qualification.

## Identity and boundaries

Receiving used device ID `9ea77fe9-bb87-46e0-a5a8-8b3e25f6ff7e`, identity `MSI\Veria`, and the existing Python 3.12.10 x64 interpreter:

```text
D:\CaptureSuite-receiving-7cb7e049e2c0\python312\python.exe
```

The original baseline remains at `D:\CaptureSuite-receiving-7cb7e049e2c0\source-778de777`. The exact published composition was fetched into a new owned checkout, `D:\CaptureSuite-receiving-7cb7e049e2c0\source-223e6926`, and its commit, tree and ordered parents were verified. All scientific, test and documentation bytes match their published Git objects. Nine auxiliary PS1/CMD checkout byte differences are recorded; they were preserved without normalization. All 1,348 observed source-file fingerprints remain unchanged after receiving.

The active MSI pause permits CaptureSuite analysis. No unrelated project, device capture, GUI session, system setting, package installation or existing installation was changed. A newly listed second device also named MSI had user `jacob` and lacked this receiver; it was not substituted for the verified environment.

The first source transfer timed out without a process identifier. After the original route recovered, read-only reconciliation found the script and new checkout absent and no active receiving sessions. The fetch then ran once under PID 26420 and completed at 2026-10-13T13:46:04.587227Z. GitHub publication uses the inert feature branch; repeated Actions queries returned zero runs. No PR, main update, tag, dispatch or workflow edit was requested.

## Preserved receiving history

1. Native v1, PID 32072, passed all 183 tests and 24 subtests. Its public-job preflight then stopped before fixtures: the old baseline contains 39 existing derived Python bytecode files that the new checkout lacks.
2. The receiver adaptation partitions library files into source and derived-bytecode sets. Both 96-file source key sets still match, with the accepted IMU file as their only differing source. Every existing bytecode file is separately hashed and preserved. Nothing is deleted. The scientific child script, fixtures and public job operations are byte-identical to the accepted portable receiver.
3. Independent review accepted the exact adapted receiver SHA256 `4859917eb4611ce89debf74724aad4e3e6f66fcd696dce13e88460cc298cb555`.
4. Native v2, PID 1432, reused the existing successful test receipt and ran only the eight outstanding jobs. It completed successfully at **2026-10-13T14:01:23.759354Z**. The 183-case gate was not repeated.
5. The collector rechecked all 1,348 source fingerprints and packaged the original and final receipts, full JUnit/log, raw fixtures and saved job outputs without rerunning analysis.

The unpublished EMG vectorization and axis-origin/raw-point overlays remain excluded. There is no Windows performance, live acquisition, GUI, estate-wide installation or default-adoption claim.

## Verify and replay

After extracting this supplement, verify it with the standard library:

```text
python verify_packet.py .
```

The same verifier accepts the supplement ZIP directly. It checks every outer and nested payload, native source and receipt identities, exact JUnit counts, all four raw-fixture sets, all 56 saved job outputs, source-key equality and the expected integer markers. It does not rerun numerical work.

For a fresh portable replay, use the original linked kit's `replay_imu_composition.py` and a new work directory. That kit includes the exact scientific source closure and requires an existing Python 3.12 environment with its documented analysis dependencies.

On this established MSI receiver, an explicit fresh native replay can use the adapted receiver directly. Replace the final path with a new, nonexistent output directory:

```powershell
& 'D:\CaptureSuite-receiving-7cb7e049e2c0\python312\python.exe' -B `
  'D:\CaptureSuite-receiving-7cb7e049e2c0\receive_imu_composition_mcap_native_v2.py' `
  --baseline 'D:\CaptureSuite-receiving-7cb7e049e2c0\source-778de777' `
  --candidate 'D:\CaptureSuite-receiving-7cb7e049e2c0\source-223e6926' `
  --python 'D:\CaptureSuite-receiving-7cb7e049e2c0\python312\python.exe' `
  --out 'D:\CaptureSuite-receiving-7cb7e049e2c0\imu-review-new'
```

The receiver explicitly chooses package paths because the embedded interpreter ignores PYTHONPATH. It refuses an existing output directory. The retained source-fetch, gate and resume scripts are one-shot historical evidence; do not blindly rerun them against existing receiving directories.

## Contents

- `evidence/native-evidence.zip`: immutable native collector archive, 376,314 bytes, SHA256 `e4e684e1718df128d2866fe88b14b3f5159c09c823cb6a22d11e3a2655e03748`; 208 payloads plus its manifest.
- `evidence/imu-native-bytecode-adaptation-review.json`: independent bounded receiver review.
- `evidence/imu-native-independent-review.json`: independent final source/output evidence review.
- `evidence/imu-local-native-byte-comparison.json`: the 28 retained cross-platform byte comparisons, including the CSV line-ending distinction.
- `receive_imu_composition_mcap_native_v2.py`: the accepted fresh receiving entry point.
- `verify_packet.py` and `MANIFEST.json`: standard-library integrity and result verification.

The nested archive retains `native-v1/` failure history and successful gate, `native-v2/` final receipt and actual jobs, canonical source-pin records, and exact historical runners. The original portable source and its independent raw-MCAP review remain linked above.
