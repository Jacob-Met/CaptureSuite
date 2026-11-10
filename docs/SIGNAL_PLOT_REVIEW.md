# Static signal figures

The offline `plots` and `all` commands save per-modality PNGs and
`figures/sync_dashboard.png` inside the retained analysis job. These exported
figures use the recording's **session seconds**, including negative pre-T0
times. Selecting a later time range does not reset the axis to zero.

Each static trace breaks across that stream's recorded gap intervals, even
when the missing interval contains no stored sample. Samples recorded inside
a declared gap are hidden in the derived figure. Nonfinite values also break
the trace. Display thinning happens after these breaks are established and
keeps the first and last point of each valid run. This is a display reduction:
it does not change MCAP files, native timestamps, feature tables or their gap
policy. A single retained sample is shown as a dot.

Red bands identify the displayed portion of gaps applying to that lane.
Source-wide and package-wide gaps retain their scope; a sibling stream's gap
does not mark a healthy lane. The visible extent is the retained timestamps,
so an open-ended gap never stretches a durationless recording to an invented
end time.

To review a particular interval with the standalone Linux executable:

```bash
./capturesuite-analysis plots recording.mmsession --start-ns 10000000000 --end-ns 15000000000
```

The command prints the saved job directory. Open its PNGs with an image viewer.
Generated MCAP regression recordings have verified nonzero and negative times,
missing-sample disconnects, open/closed gaps, a healthy sibling control, and
display thinning. These checks establish recorded-time and declared-gap
presentation, not hardware synchronization or sensor calibration. Undeclared
time gaps are not inferred from spacing alone.

The native interactive dashboard consumes the existing
`capture.sync_dashboard_series/1` document and has a separate viewer. This
static-figure change does not change its saved format or its current time and
gap display behavior. EMG dashboard values remain the existing provisional
envelope; no feature or filtering definition changes here.
