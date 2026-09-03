# Device Integration Requirements

## Delsys Trigno

Needs:
- secure API credentials
- base detection
- pairing
- scanning
- sensor allocation
- sensor modes
- channel metadata
- serials/identities
- custom aliases
- anatomical mapping
- rawest accessible EMG
- auxiliary channels if enabled
- compact EMG preview
- full expanded diagnostics
- drop/disconnect detection
- reconnect strategy
- trigger support where available
- version/provenance capture

Pairing is a first-class workflow.

## Cameras

Needs:
- enumeration
- stable identity where possible
- custom aliases
- role names
- resolution/FPS/pixel format
- codec
- exposure/gain/white balance where available
- live preview
- full-quality direct recording
- per-frame timing
- dropped-frame detection
- multiple simultaneous cameras
- camera presets

No pairing workflow.

## Xsens

Exact model family must be inventoried before implementation.

Common requirements:
- receiver/system discovery
- sensor discovery
- pairing
- custom aliases
- logical slots
- anatomical segment assignment
- update rate/configuration
- accelerometer
- gyroscope
- magnetometer where available
- orientation/quaternion
- device timestamps/counters
- battery/status where available
- calibration
- heading/reset where applicable
- compact orientation cube
- motion activity preview
- expanded all-sensor view
- reconnect with explicit gap logging

Pairing is a first-class workflow.

## Infineon BGT60TR13C

Needs:
- actual development board/interface inventory
- device discovery
- stable device identity
- custom aliases
- logical slots
- rawest accessible radar frames
- configuration capture
- frame timing
- dropped-frame detection
- compact range profile or motion-energy preview
- expanded range-Doppler/raw/configuration diagnostics

### Multi-radar

Capture V1 requirement.

Support a RadarArray configuration:
- array name
- member radar IDs
- per-radar aliases
- per-radar enable/disable
- physical position
- orientation
- coordinate frame
- profile
- per-device overrides
- timing/acquisition mode
- calibration references
- preview selection

Need an early hardware validation spike for:
- simultaneous enumeration
- stable addressing
- concurrent acquisition
- USB throughput
- multi-radar RF interference
- staggered/sequential operation
- hardware triggering/sync if available
- per-radar worker vs shared worker tradeoff

Do not promise synchronization modes that have not been verified on the actual board/RDK setup.

## Vicon

Not a Capture V1 blocker.

Future approaches:
- import exported Vicon data
- Vicon DataStream SDK bridge
- live source plugin later

Do not try to replace Nexus.

## Future wearables

Add later through the same source/stream/plugin interfaces.

Do not hard-code the current hardware list into core session logic.
