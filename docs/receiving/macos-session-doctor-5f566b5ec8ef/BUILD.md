# Source and build correspondence

CaptureSuite canonical commit: `d43bdea867d6198a707a5f55e29216c76054517e`.
Native immutable source snapshot: `6a1a32e6240dc89892f340f241b03ef25a8ac8fc`.
The 96 inputs in `source-manifest.json` were checked against the canonical Git blob IDs before the build and checked again afterward.

MCAP: repository `https://github.com/foxglove/mcap`, tag `releases/cpp/v2.1.1`, commit `b2953496735e7b89d5b2ea58be73abed85317c5f`. The included headers are under `source-dependencies/mcap/cpp/mcap/include`.

## Build the portable target

The recorded build used macOS 26.6.2 arm64, AppleClang 21.0.0, CMake 4.2.3 and Ninja 1.13.2. Build-time dependencies were supplied by the existing `/opt/homebrew` installation: protobuf/protoc, spdlog, fmt, Abseil, Zstandard, LZ4, BLAKE3, SQLite headers, Catch2 and nlohmann-json. The linked receiver uses the macOS system SQLite library. Runtime dependency versions and original bytes are recorded in `runtime-manifest.json`; available Homebrew formula definitions are copied under `dependency-records/`.

With equivalent build dependencies available, choose a new build directory and use the existing portable CMake path:

```sh
receiver_dir="/absolute/path/CaptureSuite-Session-Doctor-d43bdea-macos-arm64"
build_dir="/absolute/path/to/a-new-build-directory"
export MCAP_INCLUDE_DIR="$receiver_dir/source-dependencies/mcap/cpp/mcap/include"
cmake -S "$receiver_dir/source" -B "$build_dir" -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_COMPILER=/usr/bin/clang++ \
  "-DCMAKE_PREFIX_PATH=/opt/homebrew;$receiver_dir/source/cmake/linux-shims" \
  -DCAPTURE_BUILD_TESTS=ON \
  -DCAPTURE_ENABLE_CAMERA_WORKER=OFF -DCAPTURE_ENABLE_RADAR_WORKER=OFF \
  -DCAPTURE_WERROR=OFF
cmake --build "$build_dir" --parallel 2
ctest --test-dir "$build_dir" --output-on-failure --no-tests=error
```

`linux-shims` is the existing repository directory name used by this portable configuration. No preset, bootstrap, schema, recovery, storage or worker source was changed for this receiver. The host-specific snapshot scripts under `qualification/` preserve the commands and checks actually performed; their original owned paths are evidence, not a generic installation API.

## Runtime assembly

Original build binary SHA-256: `4bb8872c854d0c344150c806d55674b4d0b6743355982552b6b494f785a19ce3`.
Received binary SHA-256: `401f7ef7eb1212799c00ff7bdb22ac48a31bf6feb22a17b3a4fefcfc8e485772`.

The assembly copies the original executable and every resolved non-system dependency. It rewrites only the copies to use package-relative load commands, removes copied runtime search paths, and signs those copies ad hoc. Original build and installed library bytes are verified unchanged. The manifest records all 87 copied images and their source identities. `@rpath` admission uses the declaring image's explicit paths and refuses missing or ambiguous resolution; it does not rely on an ambient loader search.

The archive is a native receiving artifact. Its source and dependency records identify the exact received build; a newly compiled result is not claimed to be byte-identical across compiler or dependency updates.
