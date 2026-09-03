# SPDX-License-Identifier: Apache-2.0
"""Map MessageType <-> protobuf message classes."""

from __future__ import annotations

from google.protobuf.message import Message

from capture_protocol.generated.capture.v1 import (
    common_pb2,
    control_pb2,
    events_pb2,
    health_pb2,
    preview_pb2,
    worker_pb2,
)
from capture_protocol.generated.capture.v1.common_pb2 import MessageType

_REGISTRY: dict[int, type[Message]] = {
    MessageType.MESSAGE_TYPE_HELLO: common_pb2.Hello,
    MessageType.MESSAGE_TYPE_HELLO_ACK: common_pb2.HelloAck,
    MessageType.MESSAGE_TYPE_IDENTIFY: worker_pb2.IdentifyRequest,
    MessageType.MESSAGE_TYPE_IDENTIFY_REPLY: worker_pb2.IdentifyReply,
    MessageType.MESSAGE_TYPE_DISCOVER: worker_pb2.DiscoverRequest,
    MessageType.MESSAGE_TYPE_DISCOVER_REPLY: worker_pb2.DiscoverReply,
    MessageType.MESSAGE_TYPE_CONNECT: worker_pb2.ConnectRequest,
    MessageType.MESSAGE_TYPE_CONNECT_REPLY: worker_pb2.ConnectReply,
    MessageType.MESSAGE_TYPE_GET_STREAM_DESCRIPTORS: worker_pb2.GetStreamDescriptorsRequest,
    MessageType.MESSAGE_TYPE_GET_STREAM_DESCRIPTORS_REPLY: worker_pb2.GetStreamDescriptorsReply,
    MessageType.MESSAGE_TYPE_GET_HEALTH: worker_pb2.GetHealthRequest,
    MessageType.MESSAGE_TYPE_GET_HEALTH_REPLY: worker_pb2.GetHealthReply,
    MessageType.MESSAGE_TYPE_GET_PREVIEW_DESCRIPTOR: worker_pb2.GetPreviewDescriptorRequest,
    MessageType.MESSAGE_TYPE_GET_PREVIEW_DESCRIPTOR_REPLY: worker_pb2.GetPreviewDescriptorReply,
    MessageType.MESSAGE_TYPE_GET_CONFIG_SCHEMA: worker_pb2.GetConfigSchemaRequest,
    MessageType.MESSAGE_TYPE_GET_CONFIG_SCHEMA_REPLY: worker_pb2.GetConfigSchemaReply,
    MessageType.MESSAGE_TYPE_APPLY_CONFIG: worker_pb2.ApplyConfigRequest,
    MessageType.MESSAGE_TYPE_APPLY_CONFIG_REPLY: worker_pb2.ApplyConfigReply,
    MessageType.MESSAGE_TYPE_HEALTH_SNAPSHOT: health_pb2.HealthSnapshot,
    MessageType.MESSAGE_TYPE_GAP_EVENT: health_pb2.GapEvent,
    MessageType.MESSAGE_TYPE_OVERLOAD_EVENT: health_pb2.OverloadEvent,
    MessageType.MESSAGE_TYPE_CLOCK_SAMPLE: events_pb2.ClockSample,
    MessageType.MESSAGE_TYPE_STATE_CHANGED: events_pb2.StateChanged,
    MessageType.MESSAGE_TYPE_ALERT: health_pb2.Alert,
    MessageType.MESSAGE_TYPE_CREATE_CHECKPOINT: control_pb2.CreateCheckpointRequest,
    MessageType.MESSAGE_TYPE_CREATE_CHECKPOINT_REPLY: control_pb2.CreateCheckpointReply,
    MessageType.MESSAGE_TYPE_LIST_SOURCES: control_pb2.ListSourcesRequest,
    MessageType.MESSAGE_TYPE_LIST_SOURCES_REPLY: control_pb2.ListSourcesReply,
    MessageType.MESSAGE_TYPE_RESCAN_SOURCES: control_pb2.RescanSourcesRequest,
    MessageType.MESSAGE_TYPE_RESCAN_SOURCES_REPLY: control_pb2.RescanSourcesReply,
    MessageType.MESSAGE_TYPE_CREATE_SESSION: control_pb2.CreateSessionRequest,
    MessageType.MESSAGE_TYPE_CREATE_SESSION_REPLY: control_pb2.CreateSessionReply,
    MessageType.MESSAGE_TYPE_OPEN_SESSION: control_pb2.OpenSessionRequest,
    MessageType.MESSAGE_TYPE_OPEN_SESSION_REPLY: control_pb2.OpenSessionReply,
    MessageType.MESSAGE_TYPE_SELECT_SOURCES: control_pb2.SelectSourcesRequest,
    MessageType.MESSAGE_TYPE_SELECT_SOURCES_REPLY: control_pb2.SelectSourcesReply,
    MessageType.MESSAGE_TYPE_START_SELECTED: control_pb2.StartSelectedRequest,
    MessageType.MESSAGE_TYPE_START_SELECTED_REPLY: control_pb2.StartSelectedReply,
    MessageType.MESSAGE_TYPE_START_ALL_READY: control_pb2.StartAllReadyRequest,
    MessageType.MESSAGE_TYPE_START_ALL_READY_REPLY: control_pb2.StartAllReadyReply,
    MessageType.MESSAGE_TYPE_ACKNOWLEDGE_ALERT: control_pb2.AcknowledgeAlertRequest,
    MessageType.MESSAGE_TYPE_ACKNOWLEDGE_ALERT_REPLY: control_pb2.AcknowledgeAlertReply,
    MessageType.MESSAGE_TYPE_STOP_REHEARSAL: control_pb2.StopRehearsalRequest,
    MessageType.MESSAGE_TYPE_STOP_REHEARSAL_REPLY: control_pb2.StopRehearsalReply,
    MessageType.MESSAGE_TYPE_REQUEST_STOP: control_pb2.RequestStopRequest,
    MessageType.MESSAGE_TYPE_REQUEST_STOP_REPLY: control_pb2.RequestStopReply,
    MessageType.MESSAGE_TYPE_STOP_SESSION: control_pb2.StopSessionRequest,
    MessageType.MESSAGE_TYPE_STOP_SESSION_REPLY: control_pb2.StopSessionReply,
    MessageType.MESSAGE_TYPE_ANNOTATE: control_pb2.AnnotateRequest,
    MessageType.MESSAGE_TYPE_ANNOTATE_REPLY: control_pb2.AnnotateReply,
    MessageType.MESSAGE_TYPE_ADD_SYNC_ANCHOR: control_pb2.AddSyncAnchorRequest,
    MessageType.MESSAGE_TYPE_ADD_SYNC_ANCHOR_REPLY: control_pb2.AddSyncAnchorReply,
    MessageType.MESSAGE_TYPE_GET_RECORDING_STATS: control_pb2.GetRecordingStatsRequest,
    MessageType.MESSAGE_TYPE_GET_RECORDING_STATS_REPLY: control_pb2.GetRecordingStatsReply,
    MessageType.MESSAGE_TYPE_INJECT_FAULT: control_pb2.InjectFaultRequest,
    MessageType.MESSAGE_TYPE_INJECT_FAULT_REPLY: control_pb2.InjectFaultReply,
    MessageType.MESSAGE_TYPE_LIST_WORKERS: control_pb2.ListWorkersRequest,
    MessageType.MESSAGE_TYPE_LIST_WORKERS_REPLY: control_pb2.ListWorkersReply,
    MessageType.MESSAGE_TYPE_SUBSCRIBE_STATUS: control_pb2.SubscribeStatusRequest,
    MessageType.MESSAGE_TYPE_SUBSCRIBE_STATUS_REPLY: control_pb2.SubscribeStatusReply,
    MessageType.MESSAGE_TYPE_LIST_PREVIEW_DESCRIPTORS: control_pb2.ListPreviewDescriptorsRequest,
    MessageType.MESSAGE_TYPE_LIST_PREVIEW_DESCRIPTORS_REPLY: (
        control_pb2.ListPreviewDescriptorsReply
    ),
    MessageType.MESSAGE_TYPE_SET_PREVIEW_CONFIG: control_pb2.SetPreviewConfigRequest,
    MessageType.MESSAGE_TYPE_SET_PREVIEW_CONFIG_REPLY: control_pb2.SetPreviewConfigReply,
    MessageType.MESSAGE_TYPE_GET_SESSION_VIEW: control_pb2.GetSessionViewRequest,
    MessageType.MESSAGE_TYPE_GET_SESSION_VIEW_REPLY: control_pb2.GetSessionViewReply,
    MessageType.MESSAGE_TYPE_RUN_PREFLIGHT: control_pb2.RunPreflightRequest,
    MessageType.MESSAGE_TYPE_RUN_PREFLIGHT_REPLY: control_pb2.RunPreflightReply,
    MessageType.MESSAGE_TYPE_START_REHEARSAL: control_pb2.StartRehearsalRequest,
    MessageType.MESSAGE_TYPE_START_REHEARSAL_REPLY: control_pb2.StartRehearsalReply,
    MessageType.MESSAGE_TYPE_UPDATE_CHECKPOINT: control_pb2.UpdateCheckpointRequest,
    MessageType.MESSAGE_TYPE_UPDATE_CHECKPOINT_REPLY: control_pb2.UpdateCheckpointReply,
    MessageType.MESSAGE_TYPE_PREVIEW_FRAME: preview_pb2.PreviewFrame,
    MessageType.MESSAGE_TYPE_DISK_STATUS: health_pb2.DiskStatus,
}


def parse_payload(message_type: int, payload: bytes) -> Message:
    cls = _REGISTRY.get(message_type)
    if cls is None:
        raise KeyError(f"no codec registered for message_type={message_type}")
    msg = cls()
    msg.ParseFromString(payload)
    return msg


def serialize_message(message_type: int, message: Message) -> bytes:
    expected = _REGISTRY.get(message_type)
    if expected is not None and not isinstance(message, expected):
        raise TypeError(
            f"message_type={message_type} expects {expected.__name__}, "
            f"got {type(message).__name__}"
        )
    return message.SerializeToString()


def registry_keys() -> list[int]:
    return sorted(_REGISTRY.keys())
