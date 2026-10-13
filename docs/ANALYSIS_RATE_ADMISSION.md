# Finite sample-rate admission

`StreamRef.require_rate()` is the shared admission boundary for analysis that needs a sample rate. A rate must be positive and finite. The method returns the original admitted value; it does not estimate a replacement, clamp a rate, impose a new upper limit, or inspect data to infer a timebase.

## Refusal behavior

A zero or negative value keeps the existing `ValueError` text, including the source and stream identifiers. This includes negative infinity. NaN and positive infinity now raise a source-identified `ValueError` with `non-finite nominal_rate_hz` before an integer memory estimate or MCAP segment iteration can obscure the cause.

This boundary accepts the annotated floating-point metadata contract. As before, it does not normalize arbitrary strings, containers, missing values, or unrelated custom numeric classes. Finite positive values already accepted by this boundary keep their value and identity; the comparison does not round an input through a new float conversion. Downstream allocation limits, arithmetic overflow for impractical finite rates, metadata serialization, and schema validation remain separate contracts.

## Why the boundary matters

On the previous source, NaN passed the `<= 0` check and failed later as `cannot convert float NaN to integer`. Positive infinity similarly failed as an `OverflowError` during the memory estimate. Neither error named the affected stream. The generic numeric loader already had a later finite-rate guard, but its refusal did not name the source or stream. The shared boundary now gives all three loaders the same source-identified refusal.

The existing EMG, IMU, and generic numeric loaders already call `require_rate()`. The change therefore reaches their normal admission path without editing a loader, the QC report, the numeric data, or a job handler. An invalid rate is refused even when there are no segment paths to read.

## Reproduction and regression coverage

From the repository root, in the normal analysis environment:

~~~sh
python -m pytest tests/analysis/test_stream_rate_admission.py
~~~

The 30 cases cover finite positive identity (including subnormal and maximum finite float values), the unchanged nonpositive refusal, Python and NumPy NaN/infinity, both memory estimators, all three loader admission paths before segment iteration, and unchanged typed empty outputs for valid rates. The previous runtime fails 14 cases and passes 16; the candidate passes all 30. The two inherited protobuf deprecation warnings remain visible.

The regression uses a sentinel in place of segment iteration to prove the refusal ordering, and an empty iterator to check existing empty-result types. It does not claim a malformed capture was observed in production or a hardware acquisition test was run. The review packet retains two preliminary test-fixture corrections: the generic loader requires its actual `generic.numeric_batch/1` schema, and its empty data array is float64, while the EMG/IMU arrays are float32. Neither correction required a production change.

No GitHub Actions, workflow changes, hardware access, or broad runtime promotion are required for this increment.
