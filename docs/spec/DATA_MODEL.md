# Data and Session Model

## Hierarchy

Project
- Participant/specimen (optional)
  - Visit/day (optional)
    - Session
      - Sources
      - Sensors
      - Streams
      - Checkpoints
      - Sections
      - Annotations
      - Sync anchors
      - Clock mappings
      - Health events
      - Calibration
      - Anatomical mappings
      - Spatial mappings
      - Preset snapshots
      - Raw data
      - Derived post-processing

## PhysicalDevice

Fields should include:
- vendor
- product/model
- serial/UUID/stable device key
- firmware
- connection path
- driver/SDK version
- hardware metadata

## SourceInstance

- source_id
- source_type
- physical_device_ids
- alias
- logical_role
- enabled
- plugin_id
- plugin_version
- configuration snapshot
- health history

## SensorInstance

For multi-sensor systems:
- sensor_id
- physical identity
- alias
- logical slot
- parent source
- anatomical/spatial mapping
- sensor-specific metadata

## StreamDescriptor

Suggested fields:
- stream_id
- source_id
- sensor_id if applicable
- stream_class
- modality
- quantity
- units
- dimensions
- nominal_rate_hz
- timestamp_source
- data schema/version
- metadata

## Timing record

Where meaningful:
- sequence_number
- device_index
- device_timestamp
- host_arrival_time_ns
- session_time_ns
- timestamp_uncertainty_ns
- clock_mapping_id
- quality_flags

## Checkpoint

- checkpoint_id
- original_timestamp_ns
- effective_timestamp_ns
- name
- tags
- structured_fields
- notes
- created_via
- created_by
- timestamp_modified
- modification_reason
- revision_history

## Section

Derived from boundaries:
- section_id
- start_session_time_ns
- end_session_time_ns
- name
- source checkpoint IDs
- tags
- structured metadata

## Annotation

- annotation_id
- timestamp_ns
- category
- text
- tags
- source or global scope

## SyncAnchor

- sync_anchor_id
- timestamp_ns
- modalities targeted
- mechanism
- metadata
- observed verification results later

## ClockMapping

- mapping_id
- source/device clock ID
- valid interval
- rate correction
- offset
- anchor points
- method
- uncertainty
- provenance

## Preset snapshot

A session must store the exact preset versions used, not references only.

## Version metadata

Every session should record:
- session schema version
- app version
- daemon version
- source plugin versions
- vendor SDK versions
- relevant firmware versions
- pose model versions for post-processing
