# Camera packaging regression

Run from the repository root with Python, CMake 3.28+ and a native C++ compiler:

```sh
python tests/cmake/camera_packaging/check_packaging.py --work build/camera-packaging
```

The output directory must be new. `--source` can select another checkout and
`--cmake` can select a CMake executable. Exit 0 means all checks passed, 1 means
the staging/launch contract failed, and 2 means the fixture could not build.
`report.json` retains commands, native output, source hashes and every result.

The runner copies the actual camera `CMakeLists.txt` and plugin manifest unchanged
into an isolated fixture. It substitutes the SDK and translation units with a
native executable linked to five native libraries bearing the production DLL
names. The production post-build commands must stage the identical executable
and dependency bytes in both the legacy and manifest-selected directories.
Both copies must reach `main()` from an unrelated working directory, without
library search-path overrides. Removing only plugin-local `libprotobuf.dll`
must prevent `main()`.

Windows builds exercise the native DLL loader. Linux builds use ELF shared
libraries with `.dll` filenames and an origin-only runtime path; they establish
the CMake copy behavior and native fixture dependency isolation. Neither mode
builds the real camera worker or validates GStreamer, Media Foundation, the daemon
handshake, actual Windows vcpkg DLL closure, or physical capture.
