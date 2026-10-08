# Current-main kinematics CLI receiving

This appendix receives the frozen kinematics correction on CaptureSuite main
e43da3b855475c8aacf815c201fa03eddaeec0f1, tree
0ab35e58eb95ad6f0f85bd25ebce3378b93f2efa.

Since the original 72c15d6 baseline, the selected analysis runtime changed only
in the separately landed QC/report implementation and documentation. The
computation, new test and kinematics contract note remain exactly the frozen
2a42301 candidate. Its original 1,527-byte progress entry is prepended to the
entire current progress log; every existing progress byte is preserved.

## Finite receiving gate

The same frozen test method
test_sparse_non_sim_pose_cli_retains_missing_data_and_source_bytes runs once
against the current composition. It invokes the real tools/run_analysis.py
kinematics command on a synthetic sealed package and actual pose Parquet input.

Result: one passed, zero failed, zero skipped; process exit 0. All 135 selected
source files match the declared current composition before and after execution.
The persisted output contains missing non-simulated labels and truthful detection
rates, retains exact timestamps/model identity, and preserves every original
package and input-pose byte. Two inherited protobuf deprecation warnings remain.

This gate addresses the changed QC/report entry path. It does not repeat the
thirteen original missing-data tests or eight existing numerical/workflow
controls; their frozen author receipts remain in the sibling author directory.
Root independent receiving is retained separately.

## Files and boundaries

source-manifest.json maps the current selected sources to their exact Git/SHA
identities. receipt.json preserves the command, source maps, exit, timestamps and
JUnit hash. process.log and junit.xml retain the actual native result.
test-artifacts.tar.gz contains every regular file from the actual case, with
individual hashes in test-artifact-manifest.json. Pytest convenience symlink
aliases are omitted from this portable artifact archive.

No product runtime was modified during receiving. This native macOS Python 3.12
CLI result does not replace the full supported Windows Python/C++/daemon gates
required on the eventual full repository head. No inference, hardware capture,
calibration, smoothing, or physical-accuracy claim is added.
