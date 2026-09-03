# Radar (Infineon) plugin

Reference hardware plugin for Infineon BGT60 FMCW / LTR11 Doppler boards.
Sources live under `workers/radar/` and are copied into `plugins/radar_infineon/`
at build time.

## Prerequisites

- Infineon Radar SDK (`IFX_RADAR_SDK_ROOT`)
- Configure with `CAPTURE_ENABLE_RADAR_WORKER=ON`

## License

Plugin code: GPL-3.0-only. The Infineon Radar SDK is proprietary — install it
yourself; CaptureSuite does not redistribute Infineon binaries.
