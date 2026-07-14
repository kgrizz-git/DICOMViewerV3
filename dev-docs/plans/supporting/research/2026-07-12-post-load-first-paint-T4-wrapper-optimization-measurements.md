# T4: Multi-frame Wrapper Optimization Measurements

Date: 2026-07-12

## Method

Ran the GUI with `DICOM_PERF_LOG=1` and an auto-confirmed large-file warning
against the same samples used for the S1c baseline. The application completed
its real loading and first-display path; timing logs are local-only:

- XA: `/tmp/dv3-first-paint-s3-xa-241mb.log`
- Enhanced CT: `/tmp/dv3-first-paint-s3-ct-182mb.log`

## Results

| Sample | Frames | Wrapper creation before -> after | Merge before -> after | First display after |
| --- | ---: | ---: | ---: | ---: |
| XA, 241.5 MB | 450 | 4516.6 ms -> 14.5 ms | 4770.8 ms -> 562.5 ms | 49.5 ms |
| Enhanced CT, 182.1 MB | 364 | 26345.7 ms -> 44.0 ms | 26377.2 ms -> 1159.4 ms | 178.1 ms |

Loader/decode remained effectively unchanged (XA 347.5 ms -> 344.0 ms; CT
937.1 ms -> 954.3 ms), which isolates the improvement to organizer work after
the user confirms the large-file prompt.

## Interpretation

The deep copy of every non-pixel element for every frame was the reported
post-Continue stall. The lightweight metadata view removes more than 99% of
wrapper construction time for both samples. First display is now sub-200 ms
after UI handoff. XA thumbnail generation (309.8 ms) occurs after the event
loop returns; enhanced CT thumbnail generation is 13.5 ms. Neither justifies
adding deferred navigator complexity as a P1 follow-up.

Enhanced CT still spends about 575.7 ms rebuilding multiframe-info during
merge application. Treat that as a P3 investigation only if a future
measurement or user report shows it is materially visible.
