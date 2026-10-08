# Independent receiving: portable saved-job file reader

Root receiver: ac386303dce2. Original published PR82 head1980c6920001a57f9cdbc496d9f1e3c4f54134ae; its actual tested merge029a53642c351c44659be1bdca8f2a79c7d60de6 failed two Python cases (565 passed,2 failed,6 existing daemon-unavailable skips). The same original CMake job113426182991 completed30 CTests and6 native integration cases. Both complete original logs are separately retained in the author capsule SHA17acfea120f5ab31fed7204cd5b582043cdd0448a77c02e7fc7d4a206a28c1e1.

Frozen original helper: db744e872ed3f4dfa7d1bd253aa1e4610032e973e31f91a001cc964a0b139948.
Frozen portable successor: 3fcc013cedffba87cdfdf105f80502b60bcfdca8c298e6b8feb20da2348d0966.

## Actual primary Windows receiving
Host DESKTOP-LA7CMTA; dedicated SystemTemp directory; C:\ProgramData\HamonRuntime\python-3.13.15\python.exe. No Hub source, process, service, account, provider, capture or actuator was changed. The complete probe was frozen before executing the successor, SHA dc8d41403c16300dd5af8fb9ba5cc820c9e497a3232e79abdca335db9d8a4e1c.

Original:4 passed,2 failed,0 skipped,exit1. Exact-byte restoration was rejected by cross-API ctime comparison; identical-byte replacement with a different file after closing the handle was accepted.
Successor:6 passed,0 failed,0 skipped,exit0. Positive initial loads and retained/fresh exact-byte retries work. Changed bytes, a different file opened, a real same-size in-read mutation with restored mtime, and an identical-byte different-file replacement after closing the handle are refused. These are actual filesystem operations and actual native lstat/fstat metadata. Stat integers are decimal strings to preserve all bits across JSON.

One initial combined transfer failed spawn ENAMETOOLONG before any process/test; separate bounded parts were assembled with size/SHA/readback verification. This environment failure is preserved separately and is not a test failure.

## Unchanged native Qt/API receiving
Python3.12.14,PySide6/Qt6.11.2 on Linux. Exact QtCore SHA d040e13f904ba5f6f43f5d97d8610b0eb53bfb12721710dfea16829355fe0cb1.
Unchanged keyboard/API probe dd6399443e79b2346b885c17a0fa7c1efa64403e17638d2bc46cbeacae3f970f:16/16 passed.
Unchanged wrapper probe1f3610ac80ec603fd87d3370492d1deb231feb1370e6e0677586006b0dfc9d91:5/5 passed.
No failures,errors or skips. UI bd0adca471711350b45702bf7c625b28c348321be43c6eaecd047da33304fc1d and shared plots3d9e2a5843acf530fbffd4dcb42bccff71822801ce0df0c037a72a3d6e7d07da stayed exact. All copied source remained unchanged. Only runner paths and selected source pins were adapted; full original/adapted runners and exact textual adaptations are retained. Temporary /dev copies and fixtures were created and consumed in one execution.

## Source decision and boundary
The successor uses file IDs/type across path/handle APIs, full handle metadata before/after the read, and full same-family path identity before/after close; it retains byte bounds and size checks. Source is independently accepted for normal publication. Actual hosted Windows CI on the final current-main composition remains required; these isolated tests do not replace it. No crash-atomicity or protection against every possible concurrent filesystem change is asserted.

The original 37-member independent capsule SHA19d2dac40035df242baa25c057e5fe2b21b2fdcead118aa8991d2238f4a1e704 remains unchanged, retaining the original and corrected receiver-key/depth assumptions and all original v1/v2 attribution.
