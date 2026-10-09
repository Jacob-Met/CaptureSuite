# ML-bundle target names

The ML producer accepts an ordered selection of recorded teacher columns through
`target_columns`. `None` and an empty list keep the existing four default elbow
angle/velocity targets. The public analysis Job API preserves that default
behavior when `extra.target_columns` is omitted or empty.

Each selected name must be a nonempty string and must occur only once. Names are
compared exactly: case, Unicode and whitespace are not normalized. Custom
nonreserved scientific labels remain supported; this admission does not restrict
the producer to the external evaluator's separate kinematics registry.

Five names belong to the bundle's required output fields and cannot be targets:

- `window_id`
- `session_time_ns`
- `valid_mask`
- `motion_energy`
- `feature_stream_id`

The producer rejects a collision even if the teacher table contains a column
with that name. Otherwise the target dictionary could replace generated window
identity, exact integer time, validity, feature value or feature identity during
row assembly. Duplicate targets are also refused rather than writing ambiguous
manifest metadata. A missing nonreserved teacher column retains its existing
missing-column error.

Admission happens before creating the ML output directory or writing its
Parquet/manifest. Through the public Job API, a refused selection retains the
normal failed analysis record and diagnostics without publishing an ML bundle.
The job runner's existing replacement and failure policies are unchanged.

For admitted selections, column order, values, medians, nearest-feature lookup,
timing, validity, units, normalization, manifests and source inputs retain their
existing behavior. This is a target-name contract; it does not validate teacher
accuracy, assign scientific meaning to custom names, or expand evaluator support.

[Native receiving](../evidence/ml-bundle-target-admission-713adaab/README.md)
preserves the original collision and duplicate-label outcomes and paired
original/candidate controls. Supported hosted integration gates remain pending
under the operator's Actions hold.
