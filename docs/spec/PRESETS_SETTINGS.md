# Presets, Settings, Hotkeys, and Persistence

## Preset types

### Device preset
Expected serials/UUIDs and source bindings.

### Naming preset
Aliases and logical slots for:
- source
- sensor
- camera
- EMG sensor
- Xsens IMU
- radar
- stream

### Anatomical mapping preset
EMG -> muscle/custom region
Xsens -> body segment

### Spatial layout preset
Camera/radar positions and orientations.

### Radar array preset
- members
- aliases
- geometry
- profiles
- overrides
- timing mode
- calibration references

### Capture preset
Selected sources and source configurations.

### Checkpoint protocol preset
Expected section names, tags, fields, order.

### Hotkey preset
All operator shortcuts.

### Workspace preset
Window/card layouts and monitor assignments.

### Export preset
Export formats and folder organization.

## Preset versioning

Every preset:
- unique ID
- human name
- schema version
- preset version
- created/updated timestamps
- compatibility metadata
- description

Session stores an immutable snapshot of presets used.

## Persistent settings

Machine/user-level:
- theme
- window positions
- monitor layout
- recent projects
- last paths
- preview preferences
- update channel
- default hotkeys

Application database:
- known device registry
- preset library
- recent sessions
- plugin states
- schema migrations

Project-level:
- project metadata schema
- naming conventions
- protocol templates
- validated device layouts

Secrets:
- OS credential store
- never plain-text export

## Hotkeys

Customizable:
- start selected
- start all ready
- stop
- checkpoint
- undo latest checkpoint
- annotation
- sync event
- quick note
- expand selected source
- fullscreen preview
- acknowledge warning

Need:
- conflict detection
- safe defaults
- hotkey presets
- later USB HID/foot pedal support
- optional global hotkeys
