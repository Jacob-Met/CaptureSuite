# Architecture

## Recommended stack

### Desktop shell
Python + PySide6/Qt.

Responsibilities:
- UI
- setup workflows
- source cards
- presets
- session metadata
- review
- export
- post-capture pose processing orchestration
- future scientific analysis

### Capture daemon
C++20.

Responsibilities:
- session state machine
- master monotonic time
- worker lifecycle
- coordinated arm/start/stop
- checkpoints and annotations
- sync anchors
- health aggregation
- watchdogs
- journal coordination

### Source workers

Camera:
- C++ + GStreamer

Delsys:
- Python worker against official Delsys API initially
- can later migrate native-critical pieces without changing protocol

Xsens:
- C++ worker using exact installed Xsens SDK family

Radar:
- C++ worker using Infineon Radar Development Kit

Pose:
- Python worker(s)

### IPC

Use a versioned protocol.

Recommended:
- Protocol Buffers for schemas
- local sockets/named pipes for control/status
- shared memory ring buffers for preview payloads
- do not send raw full-resolution capture streams through the UI process

## Source abstraction

A source plugin should expose:

- identify
- discover
- connect
- disconnect
- pair/unpair if applicable
- get capabilities
- configuration schema
- apply configuration
- calibrate
- validate
- arm
- start
- stop
- get stream descriptors
- get health
- get preview descriptor
- recover
- shutdown

Not every source supports every operation.

## Generic stream classes

- SampledStream
- FrameStream
- ArrayFrameStream
- StructuredStream
- EventStream
- BlobStream

Modality is metadata, not a hard-coded storage class.

## Source state machine

- unavailable
- discovered
- connected
- pairing/setup
- configured
- validated
- ready
- armed
- recording
- stopping
- finalized

Additional:
- warning
- recovering
- disconnected_during_recording
- failed
- disabled

## Preview architecture

Every worker has two paths:

Raw path:
- highest priority
- native rate
- direct to disk
- bounded and deterministic
- independent of UI

Preview path:
- reduced rate/resolution
- bounded shared memory
- latest-data-wins
- old preview data may be dropped

## Failure isolation

UI crash:
- daemon/workers continue if safe

Worker crash:
- daemon records exact failure time
- healthy sources continue
- optional worker restart/reconnect

Power loss:
- segmented files + journal allow recovery

## Extensibility

Future plugins may be written in:
- C++
- Python
- C#
- Rust
- another language

as long as they implement the local protocol and stream/storage contract.
