# EMG transition features across recorded gaps

EMG waveform length, zero crossings and slope-sign changes use consecutive
observations within uninterrupted recorded spans. A disconnect must not create
a transition from the last sample before the gap to the first sample after it.
This applies even when no retained sample timestamp falls inside the gap.

The correction is tracked in [issue #119](https://github.com/Jacob-Met/CaptureSuite/issues/119)
and implements the existing [analysis gap contract](design/ANALYSIS.md).

## Feature definitions

For each existing sample-count window, the extractor uses the recorded gap mask
and the original ordered sample timestamps:

| Feature | Observations used |
| --- | --- |
| RMS and mean absolute value | All valid observed samples in the window, as before. |
| Waveform length (`*_wl`) | Absolute differences between originally adjacent valid samples whose time interval crosses no recorded gap. |
| Zero crossings (`*_zc`) | Those same adjacent pairs, counted when their product is strictly negative. |
| Slope-sign changes (`*_ssc`) | Originally consecutive triples for which both adjacent pairs are uninterrupted, counted when the two differences have a strictly negative product. |

Gap endpoints follow the existing inclusive masking convention. An open gap ends
at the requested analysis window's end. Integer nanoseconds remain integers for
the gap intersection comparisons. A long timestamp interval by itself does not
create an inferred gap; only explicit recorded intervals and existing invalid
samples break adjacency.

An isolated valid sample contributes to RMS and mean absolute value but has no
waveform-length, crossing or slope-sign-change contribution. Real changes
within each uninterrupted span remain in the result.

### Small deterministic examples

Each row describes valid observations separated by a recorded gap.

| Valid observations within one window | Previous WL / ZC / SSC | Corrected WL / ZC / SSC |
| --- | --- | --- |
| `1, 1` then gap then `-1, -1` | `2 / 1 / 0` | `0 / 0 / 0` |
| `0, 1` then gap then `0, 1` | `3 / 0 / 2` | `2 / 0 / 0` |
| `0, 2, 1` then gap then `2, 1, 3` | `7 / 0 / 4` | `6 / 0 / 2` |

The first example has RMS and mean absolute value of 1 on both versions.
If an additional retained sample is masked between the two spans,
`valid_fraction` is 4/5. If the recording contains only the four valid samples,
`valid_fraction` remains 1. This field describes the fraction of valid retained
observations; it is not elapsed-time coverage. Likewise, `t_mid_ns` remains the
median of valid sample timestamps and can lie within a gap.

## Using corrected results

Run a new feature job from a checkout containing the correction, using the
existing Python 3.12 analysis environment:

```powershell
python tools/run_analysis.py features "C:\captures\example.mmsession" --gap-policy mask
```

The command prints the new job ID and directory. Inspect
`processing/jobs/<job-id>/features/emg/<source-id>/windows.csv` or the adjacent
`windows.parquet`. The accompanying `_schema.json` retains feature schema
version 1 and the established columns, units and calibration flags.

Previous analysis jobs retain their original values. Keep them for comparison;
create a new job instead of passing an existing `--overwrite-job-id`. When
rebuilding an ML bundle, select the new feature job through the existing
`--features-job` argument so the downstream result records its actual input.
Raw MCAP data, sample timestamps and health records are not rewritten.

The `mask` and `split` options retain the extractor's existing window placement
and amplitude aggregation. This fix prevents transition features from joining
separate spans; it does not introduce new output rows or redefine `split`.
The existing `fail` policy is unchanged.

## Reproduce the regression

```powershell
python -m pytest tests/analysis/test_emg_gap_adjacency.py -q
```

The regression file covers retained invalid samples, gaps between observations,
multiple channels, isolated samples, overlapping windows, open gaps, strict
crossing definitions and integer timestamps beyond floating-point precision.
Its full pipeline case writes two real protobuf MCAP batches at 40 Hz, records
a 50–100 ms disconnect, runs the public feature-job API, and reads both output
tables back. It verifies the corrected values, schema metadata and unchanged
raw-source hashes. The fixture is synthetic and contains no participant data.

For the project verification gate, run the analysis and protocol suites with
the supported environment as described in the
[autonomous execution plan](design/research/AUTONOMOUS_EXECUTION_PLAN.md).
The numerical definitions remain provisional until qualified against tagged
real EMG data. These regressions establish offline analysis behavior; they do
not establish hardware or installed-desktop validation.
