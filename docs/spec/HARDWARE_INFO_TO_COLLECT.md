# Hardware Information Still Needed

These are not conceptual ambiguities. They are concrete implementation details to collect before the corresponding real device worker is written.

## Delsys

Record:
- exact Trigno receiver/base model
- exact sensor models
- number of sensors
- Delsys API version
- whether sensors expose IMU channels in the intended modes
- expected EMG sample rates/modes
- trigger/sync hardware available
- current license/key deployment constraints
- vendor DLL/runtime installation path
- redistributable restrictions

## Xsens

Record:
- exact Xsens family
- exact receiver/base if applicable
- exact sensor model(s)
- number of sensors
- SDK currently installed/available
- supported output rates
- available device timestamps/counters
- pairing procedure
- calibration workflow
- available synchronization/trigger mechanisms
- redistributable runtime restrictions

Potential families must not be assumed interchangeable.

## Infineon BGT60TR13C

Record:
- exact development board/evaluation board used around BGT60TR13C
- board revision
- number of radar boards expected simultaneously
- connection method for each board
- RDK version
- stable identifiers exposed by the SDK/USB layer
- desired chirp/frame configurations
- raw-data format exposed by the current setup
- simultaneous multi-device behavior
- USB controller topology
- whether hardware triggering/synchronization is exposed
- physical mounting arrangement

Run a dedicated multi-radar spike before finalizing the array scheduler.

## Cameras

Record:
- camera make/model
- maximum number expected simultaneously
- USB/UVC/capture-card connection
- supported resolutions/FPS
- whether hardware timestamps are exposed
- whether exposure can be locked
- whether external trigger/genlock is possible
- desired codecs
- estimated session duration
- desired image quality/storage tradeoffs

## Host Computer

Record:
- Windows version
- CPU
- RAM
- GPU and VRAM
- system drive
- recording drive
- sustained write speed
- USB controller topology
- network interfaces
- available PCIe/capture hardware

## Sync Hardware

Inventory any:
- TTL trigger generators
- DAQ hardware
- LEDs
- audio devices
- sync boxes
- common clock sources
- GPIO/serial trigger interfaces

The software should exploit these where possible but must also operate without them.

## Naming / Lab Layout

Collect:
- preferred source aliases
- preferred sensor aliases
- common anatomical layouts
- common camera roles
- common radar positions/orientations
- lab coordinate convention
- common checkpoint protocols

These become initial presets, not hard-coded defaults.
