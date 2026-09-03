# Capture UI / UX Specification

## Overall principle

The capture screen should be calm, glanceable, and hard to misuse.

Every source gets a compact proof-of-life card.

Expandable detail views are available when needed.

## Main controls

- Start Selected
- Start All Ready
- Checkpoint
- Annotation
- Sync Event
- Stop

Stop should be protected.

Checkpoint should be immediate and never delayed by dialogs.

## Source selection

Every source can be enabled/disabled independently.

Examples:
- radar only
- EMG only
- camera only
- Xsens only
- camera + EMG
- camera + radar
- all sources

## Source cards

### Camera
Compact:
- live preview
- status
- actual FPS
- dropped frames
- disk/write health

Expanded:
- resolution
- codec
- exposure/gain
- timing
- hardware identity
- logs
- configuration

### Delsys
Compact:
- mini EMG traces
- paired/active sensor count
- rate
- dropped batches
- disk/write health

Expanded:
- every channel
- sensor identity
- alias
- mapping
- amplitude/scaling
- connection/battery/quality if available
- timing
- modes

### Xsens
Compact:
- selected sensor alias
- orientation cube
- accel/gyro activity
- connected count
- rate
- disk/write health

Expanded:
- all sensors
- quaternions
- accel
- gyro
- magnetometer
- battery/status
- calibration
- timing
- mapping

### Radar
Compact:
- radar alias
- range profile or motion-energy display
- frame rate
- dropped frames
- write health

Expanded:
- raw/channel status
- range profile
- range-Doppler
- configuration
- timing
- calibration
- physical placement

## Preflight

Show clear checks:
- selected sources present
- pairings correct
- expected identities present
- config matches preset
- data rates healthy
- storage speed okay
- free space okay
- estimated recording capacity
- clocks/timestamps healthy
- no recent packet loss

Allow explicit override with reason for non-fatal warnings.

## Rehearsal mode

Run previews/health without permanent recording.

Use for:
- signal checks
- placement
- calibration
- camera framing
- radar response
- testing checkpoint hotkeys

## Checkpoint workflow

Press:
- timestamp captured immediately

Then:
- preset name automatically applied or quick rename panel
- tags/notes optional

Show current open section and expected next checkpoint if protocol preset exists.

## Annotations

Quick timestamped notes that do not create section boundaries.

## Alerts

Levels:
- info
- warning
- critical

Source status:
- ready
- recording
- connecting
- warning
- error
- disabled

Optional:
- sounds
- spoken checkpoint names
- visible recording border
- silent mode preset

## Layout

Support:
- drag/reorder cards
- resize
- collapse/expand
- pin
- pop-out windows
- multi-monitor
- save workspace preset
- restore last workspace
