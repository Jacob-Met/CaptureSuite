// SPDX-License-Identifier: GPL-3.0-only
#include <cstdio>

extern "C" int probe_abseil_dll();
extern "C" int probe_blake3();
extern "C" int probe_libprotobuf();
extern "C" int probe_lz4();
extern "C" int probe_zstd();

int main() {
  if (probe_abseil_dll() != 1 || probe_blake3() != 2 || probe_libprotobuf() != 3 ||
      probe_lz4() != 4 || probe_zstd() != 5) {
    return 3;
  }
  std::puts("CAMERA_PACKAGING_PROBE_REACHED_MAIN");
  return 0;
}
