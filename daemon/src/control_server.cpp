// SPDX-License-Identifier: GPL-3.0-only
#include "capture_daemon/control_server.hpp"

#include "capture/framing.hpp"
#include "capture/logging.hpp"
#include "capture_daemon/handshake.hpp"
#include "capture_daemon/plugin_registry.hpp"
#include "capture_daemon/process_security.hpp"

#include "capture/v1/common.pb.h"
#include "capture/v1/control.pb.h"
#include "capture/v1/health.pb.h"
#include "capture/v1/preview.pb.h"
#include "capture/v1/source.pb.h"
#include "capture/v1/worker.pb.h"

#include <nlohmann/json.hpp>

#define WIN32_LEAN_AND_MEAN
#include <Windows.h>
#include <sddl.h>

#include <chrono>
#include <cstdio>
#include <filesystem>
#include <fstream>
#include <mutex>
#include <optional>
#include <thread>
#include <unordered_map>
#include <vector>

namespace capture::daemon {
namespace {

constexpr DWORD kPipeBuffer = 256 * 1024;

capture::v1::SourceLifecycleState to_proto(SourceLifecycle life) {
  using capture::v1::SourceLifecycleState;
  switch (life) {
    case SourceLifecycle::Unavailable:
      return SourceLifecycleState::SOURCE_LIFECYCLE_UNAVAILABLE;
    case SourceLifecycle::Discovered:
      return SourceLifecycleState::SOURCE_LIFECYCLE_DISCOVERED;
    case SourceLifecycle::Connected:
      return SourceLifecycleState::SOURCE_LIFECYCLE_CONNECTED;
    case SourceLifecycle::Pairing:
      return SourceLifecycleState::SOURCE_LIFECYCLE_PAIRING;
    case SourceLifecycle::Configured:
      return SourceLifecycleState::SOURCE_LIFECYCLE_CONFIGURED;
    case SourceLifecycle::Validated:
      return SourceLifecycleState::SOURCE_LIFECYCLE_VALIDATED;
    case SourceLifecycle::Ready:
      return SourceLifecycleState::SOURCE_LIFECYCLE_READY;
    case SourceLifecycle::Armed:
      return SourceLifecycleState::SOURCE_LIFECYCLE_ARMED;
    case SourceLifecycle::Recording:
      return SourceLifecycleState::SOURCE_LIFECYCLE_RECORDING;
    case SourceLifecycle::Stopping:
      return SourceLifecycleState::SOURCE_LIFECYCLE_STOPPING;
    case SourceLifecycle::Finalized:
      return SourceLifecycleState::SOURCE_LIFECYCLE_FINALIZED;
    case SourceLifecycle::Failed:
      return SourceLifecycleState::SOURCE_LIFECYCLE_FAILED;
  }
  return SourceLifecycleState::SOURCE_LIFECYCLE_UNSPECIFIED;
}

capture::v1::SessionState to_proto(SessionState state) {
  using S = capture::v1::SessionState;
  switch (state) {
    case SessionState::Idle:
      return S::SESSION_STATE_IDLE;
    case SessionState::Preparing:
      return S::SESSION_STATE_PREPARING;
    case SessionState::Arming:
      return S::SESSION_STATE_ARMING;
    case SessionState::Recording:
      return S::SESSION_STATE_RECORDING;
    case SessionState::Stopping:
      return S::SESSION_STATE_STOPPING;
    case SessionState::Finalized:
      return S::SESSION_STATE_FINALIZED;
    case SessionState::Recovering:
      return S::SESSION_STATE_RECOVERING;
    case SessionState::Failed:
      return S::SESSION_STATE_FAILED;
  }
  return S::SESSION_STATE_UNSPECIFIED;
}

capture::v1::HealthLevel to_proto(SourceHealth h) {
  switch (h) {
    case SourceHealth::Ok:
      return capture::v1::HEALTH_LEVEL_OK;
    case SourceHealth::Warning:
      return capture::v1::HEALTH_LEVEL_WARNING;
    case SourceHealth::Error:
      return capture::v1::HEALTH_LEVEL_ERROR;
  }
  return capture::v1::HEALTH_LEVEL_UNSPECIFIED;
}

capture::v1::PreviewKind to_proto(PreviewKind k) {
  return static_cast<capture::v1::PreviewKind>(static_cast<int>(k));
}

// The pipe is opened FILE_FLAG_OVERLAPPED, so every read and write must supply
// an OVERLAPPED. That is what lets the push thread deliver events while the
// request loop is parked in a read: on a synchronous handle the write would
// queue behind the pending read, and a subscriber that never sends a request
// would receive nothing at all.
bool write_all(HANDLE pipe, const std::vector<uint8_t>& data, std::mutex& write_mu) {
  std::lock_guard lock(write_mu);
  OVERLAPPED ov{};
  ov.hEvent = CreateEventW(nullptr, TRUE, FALSE, nullptr);
  if (ov.hEvent == nullptr) {
    return false;
  }
  bool ok_all = true;
  std::size_t offset = 0;
  while (offset < data.size()) {
    ResetEvent(ov.hEvent);
    DWORD written = 0;
    if (!WriteFile(pipe, data.data() + offset,
                   static_cast<DWORD>(data.size() - offset), &written, &ov)) {
      if (GetLastError() != ERROR_IO_PENDING ||
          !GetOverlappedResult(pipe, &ov, &written, TRUE)) {
        ok_all = false;
        break;
      }
    }
    if (written == 0) {
      ok_all = false;
      break;
    }
    offset += written;
  }
  CloseHandle(ov.hEvent);
  return ok_all;
}

bool send_frame(HANDLE pipe, std::mutex& write_mu, uint32_t message_type,
                const google::protobuf::MessageLite& msg,
                uint32_t correlation_id) {
  std::string payload;
  if (!msg.SerializeToString(&payload)) {
    return false;
  }
  const auto frame = encode_frame(
      message_type,
      std::span<const uint8_t>(
          reinterpret_cast<const uint8_t*>(payload.data()), payload.size()),
      correlation_id);
  return write_all(pipe, frame, write_mu);
}

void set_error(capture::v1::ErrorInfo* err, const std::string& code,
               const std::string& message) {
  err->set_code(code);
  err->set_message(message);
}

void fill_preview_descriptor(const PreviewDescriptorData& in,
                             capture::v1::PreviewDescriptor* out) {
  out->set_source_id(in.source_id);
  out->set_stream_id(in.stream_id);
  out->set_kind(to_proto(in.kind));
  out->set_ring_slot_count(3);
  out->set_max_payload_bytes(in.max_payload_bytes);
  out->set_max_rate_hz(in.max_rate_hz);
  out->set_drop_policy(capture::v1::PREVIEW_DROP_POLICY_LATEST_WINS);
  out->set_content_type(in.content_type);
  out->set_selected_channel(in.selected_channel);
  out->set_enabled(in.enabled);
  for (const auto& ch : in.available_channels) {
    out->add_available_channels(ch);
  }
}

void fill_preview_frame(const PreviewFrameData& in, capture::v1::PreviewFrame* out) {
  out->set_source_id(in.source_id);
  out->set_stream_id(in.stream_id);
  out->set_kind(to_proto(in.kind));
  out->set_session_time_ns(in.session_time_ns);
  out->set_sequence(in.sequence);
  out->set_dropped_since_last(in.dropped_since_last);
  out->set_selected_channel(in.selected_channel);

  if (in.kind == PreviewKind::ImageThumbnail) {
    auto* img = out->mutable_image();
    img->set_data(in.image.data(), in.image.size());
    img->set_width(in.width);
    img->set_height(in.height);
    img->set_pixel_format(in.pixel_format);
  } else if (in.kind == PreviewKind::Orientation) {
    auto* o = out->mutable_orientation();
    o->set_qw(in.qw);
    o->set_qx(in.qx);
    o->set_qy(in.qy);
    o->set_qz(in.qz);
    o->set_accel_magnitude(in.accel_magnitude);
    o->set_gyro_magnitude(in.gyro_magnitude);
    o->set_accel_units("m/s^2");
    o->set_gyro_units("rad/s");
  } else if (in.kind == PreviewKind::Matrix2D) {
    auto* m = out->mutable_matrix();
    m->set_rows(in.rows);
    m->set_cols(in.cols);
    m->set_display_min(in.display_min);
    m->set_display_max(in.display_max);
    m->set_row_axis(in.row_axis.empty() ? "range" : in.row_axis);
    m->set_col_axis(in.col_axis.empty() ? "doppler" : in.col_axis);
    for (float v : in.samples) {
      m->add_values(v);
    }
  } else {
    auto* t = out->mutable_trace();
    t->set_channel_count(in.channel_count);
    t->set_points_per_channel(in.points_per_channel);
    t->set_display_min(in.display_min);
    t->set_display_max(in.display_max);
    t->set_units(in.units);
    t->set_decimated_from_rate_hz(in.decimated_from_rate_hz);
    for (const auto& n : in.channel_names) {
      t->add_channel_names(n);
    }
    for (float v : in.samples) {
      t->add_samples(v);
    }
  }
}

void fill_health(const HealthSnapshotData& in, capture::v1::HealthSnapshot* out) {
  out->set_source_id(in.source_id);
  out->set_lifecycle_state(to_proto(in.lifecycle));
  out->set_health(to_proto(in.health));
  out->set_connected(in.connected);
  out->set_data_arriving(in.data_arriving);
  out->set_measured_rate_hz(in.measured_rate_hz);
  out->set_expected_rate_hz(in.expected_rate_hz);
  out->set_dropped_count(in.dropped_count);
  out->set_dropped_last_10s(in.dropped_last_10s);
  out->set_write_ok(in.write_ok);
  out->set_current_segment(in.current_segment);
  out->set_gap_count(in.gap_count);
  out->set_session_time_ns(in.session_time_ns);
  if (in.has_open_gap) {
    auto* g = out->mutable_open_gap();
    g->set_cause(capture::v1::GAP_CAUSE_DISCONNECT);
    g->set_start_session_time_ns(in.open_gap_start_ns);
  }
  if (!in.last_error_code.empty()) {
    out->mutable_last_error()->set_code(in.last_error_code);
    out->mutable_last_error()->set_message(in.last_error_message);
  }
}

void fill_disk(const DiskStatusData& in, capture::v1::DiskStatus* out) {
  out->set_free_bytes(in.free_bytes);
  out->set_reserve_bytes(in.reserve_bytes);
  out->set_write_mb_per_s(in.write_mb_per_s);
  out->set_estimated_remaining_minutes(in.estimated_remaining_minutes);
  out->set_writers_blocked(in.writers_blocked);
  if (in.headroom_level == "CRITICAL") {
    out->set_headroom_level(capture::v1::ALERT_LEVEL_CRITICAL);
  } else if (in.headroom_level == "WARNING") {
    out->set_headroom_level(capture::v1::ALERT_LEVEL_WARNING);
  } else {
    out->set_headroom_level(capture::v1::ALERT_LEVEL_INFO);
  }
}

void fill_alert(const AlertData& in, capture::v1::Alert* out) {
  out->set_alert_id(in.alert_id);
  out->set_source_id(in.source_id);
  out->set_code(in.code);
  out->set_message(in.message);
  out->set_session_time_ns(in.session_time_ns);
  out->set_acknowledged(in.acknowledged);
  if (in.level == "CRITICAL") {
    out->set_level(capture::v1::ALERT_LEVEL_CRITICAL);
  } else if (in.level == "WARNING") {
    out->set_level(capture::v1::ALERT_LEVEL_WARNING);
  } else {
    out->set_level(capture::v1::ALERT_LEVEL_INFO);
  }
}

void fill_source_instance(SimEngine& engine, const SimSourceDesc& src,
                          capture::v1::SourceInstance* inst) {
  inst->set_source_id(src.source_id);
  inst->set_source_type(src.source_type);
  inst->set_alias(src.alias);
  // Prefer worker-/manifest-advertised plugin_id when present.
  if (!src.plugin_id.empty()) {
    inst->set_plugin_id(src.plugin_id);
  } else if (src.is_camera) {
    inst->set_plugin_id(engine.uses_camera_workers() ? "camera.gstreamer"
                                                     : "camera.mf");
  } else if (src.is_radar) {
    inst->set_plugin_id("radar.ifx");
  } else {
    inst->set_plugin_id("sim.builtin");
  }
  inst->set_plugin_version("0.1.0");
  inst->set_enabled(engine.source_fsm(src.source_id).selected());
  inst->set_lifecycle_state(to_proto(engine.source_fsm(src.source_id).lifecycle()));
  inst->mutable_metadata()->insert({"modality", src.modality});
  if (src.is_replay) {
    inst->mutable_metadata()->insert({"replay", "true"});
  }
  if (src.is_camera) {
    if (src.is_virtual_camera) {
      inst->mutable_metadata()->insert({"virtual_camera", "true"});
    }
    if (engine.uses_camera_workers()) {
      inst->mutable_metadata()->insert({"record_stack", "gstreamer"});
      inst->mutable_metadata()->insert({"record_mode", "mkv_h264"});
      const auto enc = engine.camera_worker_encoder();
      if (!enc.empty()) {
        inst->mutable_metadata()->insert({"preferred_encoder", enc});
      }
    } else {
      inst->mutable_metadata()->insert({"encoding", "deferred"});
      inst->mutable_metadata()->insert({"record_mode", "timing_only"});
    }
  }
  auto* phys = inst->add_physical_devices();
  phys->set_vendor(src.vendor);
  phys->set_model(src.model);
  phys->set_serial(src.serial);
  phys->set_stable_device_key(src.stable_device_key.empty() ? src.source_id
                                                           : src.stable_device_key);
  inst->add_physical_device_ids(phys->stable_device_key());
  auto* stream = inst->add_streams();
  stream->set_stream_id(src.stream_id);
  stream->set_source_id(src.source_id);
  stream->set_modality(src.modality);
  stream->set_nominal_rate_hz(src.nominal_rate_hz);
  // Prefer worker-advertised data_schema_id; modality map is the fallback.
  if (!src.data_schema_id.empty()) {
    stream->set_data_schema_id(src.data_schema_id);
  } else if (src.modality == "video") {
    stream->set_data_schema_id("video.segment_index/1");
  } else if (src.modality == "emg") {
    stream->set_data_schema_id("emg.batch/1");
  } else if (src.modality == "imu") {
    stream->set_data_schema_id("imu.frame/1");
  } else if (src.modality == "radar") {
    stream->set_data_schema_id("radar.frame/1");
  } else if (src.modality == "radar_doppler") {
    stream->set_data_schema_id("radar.doppler/1");
  } else {
    stream->set_data_schema_id("generic.numeric_batch/1");
  }
  const std::string cfg = engine.config_snapshot(src.source_id);
  inst->set_configuration(cfg);
  inst->set_configuration_content_type("application/json");
}

struct ClientPushState {
  std::atomic<bool> subscribed{false};
  std::atomic<bool> include_preview{true};
  std::atomic<uint32_t> health_interval_ms{1000};
  std::atomic<double> preview_rate_limit_hz{0.0};
  std::atomic<bool> stop{false};
  std::size_t next_alert = 0;
  std::chrono::steady_clock::time_point last_preview_send{};
  std::unordered_map<std::string, int64_t> last_preview_seq;
};

}  // namespace

ControlServer::ControlServer(SimEngine& engine, std::string instance_id,
                             std::string pipe_name)
    : engine_(engine),
      instance_id_(std::move(instance_id)),
      pipe_name_(std::move(pipe_name)) {}

ControlServer::~ControlServer() { stop(); }

bool ControlServer::start(std::string& error) {
  if (running_.load()) {
    return true;
  }
  running_ = true;
  accept_thread_ = std::thread([this] { accept_loop(); });
  (void)error;
  return true;
}

void ControlServer::stop() {
  running_ = false;
  HANDLE wake = CreateFileA(pipe_name_.c_str(), GENERIC_READ | GENERIC_WRITE, 0,
                            nullptr, OPEN_EXISTING, 0, nullptr);
  if (wake != INVALID_HANDLE_VALUE) {
    CloseHandle(wake);
  }
  if (accept_thread_.joinable()) {
    accept_thread_.join();
  }

  std::vector<Client> remaining;
  {
    std::lock_guard lock(clients_mu_);
    remaining = std::move(clients_);
    clients_.clear();
  }
  // Client threads sit in a blocking ReadFile; cancel it so they observe the
  // cleared running_ flag instead of waiting for a peer that may never write.
  for (auto& c : remaining) {
    CancelIoEx(static_cast<HANDLE>(c.pipe), nullptr);
  }
  for (auto& c : remaining) {
    if (c.thread.joinable()) {
      c.thread.join();
    }
    CloseHandle(static_cast<HANDLE>(c.pipe));
  }
}

void ControlServer::reap_finished_clients() {
  std::lock_guard lock(clients_mu_);
  for (auto it = clients_.begin(); it != clients_.end();) {
    if (it->done->load()) {
      if (it->thread.joinable()) {
        it->thread.join();
      }
      CloseHandle(static_cast<HANDLE>(it->pipe));
      it = clients_.erase(it);
    } else {
      ++it;
    }
  }
}

bool ControlServer::await_connection(void* pipe_handle) {
  HANDLE pipe = static_cast<HANDLE>(pipe_handle);
  OVERLAPPED ov{};
  ov.hEvent = CreateEventW(nullptr, TRUE, FALSE, nullptr);
  if (ov.hEvent == nullptr) {
    return false;
  }
  bool connected = false;
  if (ConnectNamedPipe(pipe, &ov)) {
    connected = true;
  } else if (GetLastError() == ERROR_PIPE_CONNECTED) {
    connected = true;
  } else if (GetLastError() == ERROR_IO_PENDING) {
    // Poll rather than wait forever so shutdown does not depend on a client
    // arriving to release this thread.
    while (running_.load()) {
      if (WaitForSingleObject(ov.hEvent, 100) == WAIT_OBJECT_0) {
        connected = true;
        break;
      }
    }
    if (!connected) {
      CancelIoEx(pipe, &ov);
      DWORD ignored = 0;
      GetOverlappedResult(pipe, &ov, &ignored, TRUE);
    }
  }
  CloseHandle(ov.hEvent);
  return connected;
}

void ControlServer::accept_loop() {
  while (running_.load()) {
    SECURITY_ATTRIBUTES sa{};
    PSECURITY_DESCRIPTOR sd = nullptr;
    PSECURITY_ATTRIBUTES psa = make_pipe_sa(sa, sd);

    HANDLE pipe = CreateNamedPipeA(
        pipe_name_.c_str(), PIPE_ACCESS_DUPLEX | FILE_FLAG_OVERLAPPED,
        PIPE_TYPE_BYTE | PIPE_READMODE_BYTE | PIPE_WAIT,
        PIPE_UNLIMITED_INSTANCES, kPipeBuffer, kPipeBuffer, 0, psa);
    if (sd) {
      LocalFree(sd);
    }
    if (pipe == INVALID_HANDLE_VALUE) {
      std::this_thread::sleep_for(std::chrono::milliseconds(50));
      continue;
    }

    const bool connected = await_connection(pipe);
    if (!running_.load()) {
      CloseHandle(pipe);
      break;
    }
    if (!connected) {
      CloseHandle(pipe);
      continue;
    }

    {
      std::string sid_err;
      if (!peer_sid_matches_self(pipe, sid_err)) {
        capture::log::error("peer_sid_rejected", sid_err);
        DisconnectNamedPipe(pipe);
        CloseHandle(pipe);
        continue;
      }
    }

    auto done = std::make_shared<std::atomic<bool>>(false);
    std::thread worker([this, pipe, done] {
      serve_client(pipe);
      FlushFileBuffers(pipe);
      DisconnectNamedPipe(pipe);
      done->store(true);
    });
    {
      std::lock_guard lock(clients_mu_);
      clients_.push_back(Client{std::move(worker), done, pipe});
    }
    // The loop immediately creates the next pipe instance, so a second client
    // connects without waiting for the first to disconnect.
    reap_finished_clients();
  }
}

void ControlServer::serve_client(void* pipe_handle) {
  HANDLE pipe = static_cast<HANDLE>(pipe_handle);
  FrameDecoder decoder;
  bool handshake_done = false;
  std::vector<uint8_t> read_buf(8192);
  std::mutex write_mu;
  ClientPushState push;
  std::thread push_thread;

  auto stop_push = [&] {
    push.stop = true;
    if (push_thread.joinable()) {
      push_thread.join();
    }
  };

  OVERLAPPED rov{};
  rov.hEvent = CreateEventW(nullptr, TRUE, FALSE, nullptr);
  if (rov.hEvent == nullptr) {
    return;
  }
  struct EventCloser {
    HANDLE h;
    ~EventCloser() { CloseHandle(h); }
  } closer{rov.hEvent};

  while (running_.load()) {
    ResetEvent(rov.hEvent);
    DWORD read = 0;
    if (!ReadFile(pipe, read_buf.data(), static_cast<DWORD>(read_buf.size()),
                  &read, &rov)) {
      if (GetLastError() != ERROR_IO_PENDING) {
        break;
      }
      // Poll so a disconnect or shutdown is noticed even though the peer may
      // never send another byte.
      bool ready = false;
      while (running_.load()) {
        if (WaitForSingleObject(rov.hEvent, 100) == WAIT_OBJECT_0) {
          ready = true;
          break;
        }
      }
      if (!ready) {
        CancelIoEx(pipe, &rov);
        GetOverlappedResult(pipe, &rov, &read, TRUE);
        break;
      }
      if (!GetOverlappedResult(pipe, &rov, &read, FALSE)) {
        break;
      }
    }
    if (read == 0) {
      break;
    }
    decoder.feed(std::span<const uint8_t>(read_buf.data(), read));

    Frame frame;
    while (decoder.pop(frame)) {
      try {
        if (!handshake_done) {
          if (frame.message_type !=
              static_cast<uint32_t>(capture::v1::MESSAGE_TYPE_HELLO)) {
            stop_push();
            return;
          }
          capture::v1::Hello hello;
          if (!hello.ParseFromArray(frame.payload.data(),
                                    static_cast<int>(frame.payload.size()))) {
            stop_push();
            return;
          }
          auto ack = negotiate_hello(hello, instance_id_);
          send_frame(pipe, write_mu, capture::v1::MESSAGE_TYPE_HELLO_ACK, ack,
                     frame.correlation_id);
          if (!ack.accepted()) {
            stop_push();
            return;
          }
          handshake_done = true;
          continue;
        }

        using capture::v1::MessageType;
        const auto corr = frame.correlation_id;

        switch (static_cast<MessageType>(frame.message_type)) {
          case MessageType::MESSAGE_TYPE_LIST_SOURCES: {
            capture::v1::ListSourcesReply reply;
            for (const auto& src : engine_.sources()) {
              fill_source_instance(engine_, src, reply.add_sources());
            }
            send_frame(pipe, write_mu, MessageType::MESSAGE_TYPE_LIST_SOURCES_REPLY,
                       reply, corr);
            break;
          }
          case MessageType::MESSAGE_TYPE_RESCAN_SOURCES: {
            capture::v1::RescanSourcesReply reply;
            std::string err;
            if (!engine_.rescan_sources(err)) {
              set_error(reply.mutable_error(), "RESCAN_FAILED", err);
            } else {
              for (const auto& src : engine_.sources()) {
                fill_source_instance(engine_, src, reply.add_sources());
              }
            }
            send_frame(pipe, write_mu,
                       MessageType::MESSAGE_TYPE_RESCAN_SOURCES_REPLY, reply,
                       corr);
            break;
          }
          case MessageType::MESSAGE_TYPE_CREATE_SESSION: {
            capture::v1::CreateSessionRequest req;
            capture::v1::CreateSessionReply reply;
            if (!req.ParseFromArray(frame.payload.data(),
                                    static_cast<int>(frame.payload.size()))) {
              set_error(reply.mutable_error(), "BAD_REQUEST", "parse failed");
            } else {
              std::string sid = req.identity().session_id();
              if (sid.empty()) {
                sid = "session-" + instance_id_.substr(0, 8);
              }
              std::string err;
              const std::string parent = req.package_parent_path();
              const bool ok =
                  parent.empty() ? engine_.create_session(sid, err)
                                 : engine_.create_session(sid, parent, err);
              if (!ok) {
                set_error(reply.mutable_error(), "CREATE_FAILED", err);
              } else {
                reply.set_session_id(sid);
                reply.set_package_path(engine_.package_path());
                reply.set_state(to_proto(engine_.session_state()));
              }
            }
            send_frame(pipe, write_mu,
                       MessageType::MESSAGE_TYPE_CREATE_SESSION_REPLY, reply,
                       corr);
            break;
          }
          case MessageType::MESSAGE_TYPE_OPEN_SESSION: {
            capture::v1::OpenSessionRequest req;
            capture::v1::OpenSessionReply reply;
            if (!req.ParseFromArray(frame.payload.data(),
                                    static_cast<int>(frame.payload.size()))) {
              set_error(reply.mutable_error(), "BAD_REQUEST", "parse failed");
            } else {
              bool recovered = false;
              std::string err;
              if (!engine_.open_session(req.package_path(), recovered, err)) {
                set_error(reply.mutable_error(), "OPEN_FAILED", err);
              } else {
                reply.set_recovered(recovered);
                reply.set_state(capture::v1::SESSION_STATE_IDLE);
                reply.set_session_id(engine_.session_id());
                reply.set_package_path(engine_.package_path());
              }
            }
            send_frame(pipe, write_mu, MessageType::MESSAGE_TYPE_OPEN_SESSION_REPLY,
                       reply, corr);
            break;
          }
          case MessageType::MESSAGE_TYPE_FINALIZE_SESSION: {
            capture::v1::FinalizeSessionReply reply;
            std::string err;
            if (!engine_.finalize_session(err)) {
              set_error(reply.mutable_error(), "FINALIZE_FAILED", err);
            } else {
              reply.set_state(to_proto(engine_.session_state()));
            }
            send_frame(pipe, write_mu,
                       MessageType::MESSAGE_TYPE_FINALIZE_SESSION_REPLY, reply,
                       corr);
            break;
          }
          case MessageType::MESSAGE_TYPE_SELECT_SOURCES: {
            capture::v1::SelectSourcesRequest req;
            capture::v1::SelectSourcesReply reply;
            if (!req.ParseFromArray(frame.payload.data(),
                                    static_cast<int>(frame.payload.size()))) {
              set_error(reply.mutable_error(), "BAD_REQUEST", "parse failed");
            } else {
              std::vector<std::string> ids(req.source_ids().begin(),
                                           req.source_ids().end());
              std::string err;
              if (!engine_.select_sources(ids, err)) {
                set_error(reply.mutable_error(), "SELECT_FAILED", err);
              } else {
                for (const auto& id : engine_.selected_source_ids()) {
                  reply.add_selected_source_ids(id);
                }
              }
            }
            send_frame(pipe, write_mu,
                       MessageType::MESSAGE_TYPE_SELECT_SOURCES_REPLY, reply,
                       corr);
            break;
          }
          case MessageType::MESSAGE_TYPE_GET_CONFIG_SCHEMA: {
            capture::v1::GetConfigSchemaRequest req;
            capture::v1::GetConfigSchemaReply reply;
            if (!req.ParseFromArray(frame.payload.data(),
                                    static_cast<int>(frame.payload.size()))) {
              set_error(reply.mutable_error(), "BAD_REQUEST", "parse failed");
            } else {
              std::string schema;
              std::string err;
              if (!engine_.get_config_schema(req.source_id(), schema, err)) {
                set_error(reply.mutable_error(), "NOT_FOUND", err);
              } else {
                reply.set_schema_json(schema);
                const std::string current =
                    engine_.config_snapshot(req.source_id());
                reply.set_current_json(current);
                reply.set_effective_json(current);
                try {
                  const auto parsed = nlohmann::json::parse(schema);
                  reply.set_schema_revision(
                      parsed.value("schema_revision", ""));
                } catch (...) {
                }
              }
            }
            send_frame(pipe, write_mu,
                       MessageType::MESSAGE_TYPE_GET_CONFIG_SCHEMA_REPLY, reply,
                       corr);
            break;
          }
          case MessageType::MESSAGE_TYPE_APPLY_CONFIG: {
            capture::v1::ApplyConfigRequest req;
            capture::v1::ApplyConfigReply reply;
            if (!req.ParseFromArray(frame.payload.data(),
                                    static_cast<int>(frame.payload.size()))) {
              set_error(reply.mutable_error(), "BAD_REQUEST", "parse failed");
            } else {
              std::string effective;
              std::string err;
              std::string revision;
              std::vector<std::string> coerced;
              const std::string doc(req.configuration().begin(),
                                    req.configuration().end());
              reply.set_requested_json(doc.empty() ? "{}" : doc);
              if (!engine_.apply_config(req.source_id(), doc, effective, coerced,
                                       revision, err)) {
                set_error(
                    reply.mutable_error(),
                    err == "INVALID_STATE"             ? "INVALID_STATE"
                    : err == "RESTART_REQUIRED"        ? "RESTART_REQUIRED"
                    : err.find("stopping capture") != std::string::npos
                        ? "RESTART_REQUIRED"
                    : err.find("unknown") != std::string::npos ? "NOT_FOUND"
                                                              : "VALIDATION_FAILED",
                    err);
              } else {
                reply.set_effective_json(effective);
                reply.set_schema_revision(revision);
                for (const auto& field : coerced) {
                  reply.add_coerced_fields(field);
                }
                for (const auto& src : engine_.sources()) {
                  if (src.source_id == req.source_id()) {
                    fill_source_instance(engine_, src, reply.mutable_source());
                    break;
                  }
                }
              }
            }
            send_frame(pipe, write_mu,
                       MessageType::MESSAGE_TYPE_APPLY_CONFIG_REPLY, reply, corr);
            break;
          }
          case MessageType::MESSAGE_TYPE_START_SELECTED: {
            capture::v1::StartSelectedReply reply;
            std::string err;
            if (!engine_.start_selected(err)) {
              set_error(reply.mutable_error(), "START_FAILED", err);
            } else {
              reply.set_state(to_proto(engine_.session_state()));
              reply.set_t0_session_ns(0);
            }
            send_frame(pipe, write_mu,
                       MessageType::MESSAGE_TYPE_START_SELECTED_REPLY, reply,
                       corr);
            break;
          }
          case MessageType::MESSAGE_TYPE_START_ALL_READY: {
            capture::v1::StartAllReadyReply reply;
            std::string err;
            std::vector<std::string> started;
            if (!engine_.start_all_ready(started, err)) {
              set_error(reply.mutable_error(), "START_FAILED", err);
            } else {
              reply.set_state(to_proto(engine_.session_state()));
              reply.set_t0_session_ns(0);
              for (const auto& id : started) {
                reply.add_started_source_ids(id);
              }
            }
            send_frame(pipe, write_mu,
                       MessageType::MESSAGE_TYPE_START_ALL_READY_REPLY, reply,
                       corr);
            break;
          }
          case MessageType::MESSAGE_TYPE_ACKNOWLEDGE_ALERT: {
            capture::v1::AcknowledgeAlertRequest req;
            capture::v1::AcknowledgeAlertReply reply;
            if (!req.ParseFromArray(frame.payload.data(),
                                    static_cast<int>(frame.payload.size()))) {
              set_error(reply.mutable_error(), "BAD_REQUEST", "parse failed");
            } else {
              AlertData alert;
              std::string err;
              if (!engine_.acknowledge_alert(req.alert_id(), alert, err)) {
                set_error(reply.mutable_error(), "NOT_FOUND", err);
              } else {
                fill_alert(alert, reply.mutable_alert());
              }
            }
            send_frame(pipe, write_mu,
                       MessageType::MESSAGE_TYPE_ACKNOWLEDGE_ALERT_REPLY, reply,
                       corr);
            break;
          }
          case MessageType::MESSAGE_TYPE_STOP_REHEARSAL: {
            capture::v1::StopRehearsalReply reply;
            std::string err;
            if (!engine_.stop_rehearsal(err)) {
              set_error(reply.mutable_error(), "STOP_REHEARSAL_FAILED", err);
            }
            send_frame(pipe, write_mu,
                       MessageType::MESSAGE_TYPE_STOP_REHEARSAL_REPLY, reply,
                       corr);
            break;
          }
          case MessageType::MESSAGE_TYPE_REQUEST_STOP: {
            capture::v1::RequestStopReply reply;
            reply.set_confirmation_token(engine_.request_stop_token());
            send_frame(pipe, write_mu, MessageType::MESSAGE_TYPE_REQUEST_STOP_REPLY,
                       reply, corr);
            break;
          }
          case MessageType::MESSAGE_TYPE_STOP_SESSION: {
            capture::v1::StopSessionRequest req;
            capture::v1::StopSessionReply reply;
            if (!req.ParseFromArray(frame.payload.data(),
                                    static_cast<int>(frame.payload.size()))) {
              set_error(reply.mutable_error(), "BAD_REQUEST", "parse failed");
            } else {
              std::string err;
              if (!engine_.stop(req.confirmation_token(), err)) {
                set_error(reply.mutable_error(), "STOP_FAILED", err);
              } else {
                reply.set_state(to_proto(engine_.session_state()));
              }
            }
            send_frame(pipe, write_mu, MessageType::MESSAGE_TYPE_STOP_SESSION_REPLY,
                       reply, corr);
            break;
          }
          case MessageType::MESSAGE_TYPE_CREATE_CHECKPOINT: {
            capture::v1::CreateCheckpointRequest req;
            capture::v1::CreateCheckpointReply reply;
            req.ParseFromArray(frame.payload.data(),
                               static_cast<int>(frame.payload.size()));
            auto cp = engine_.create_checkpoint(req.name(), req.created_via());
            auto* out = reply.mutable_checkpoint();
            out->set_checkpoint_id(cp.checkpoint_id);
            out->set_original_timestamp_ns(cp.original_timestamp_ns);
            out->set_effective_timestamp_ns(cp.effective_timestamp_ns);
            out->set_name(cp.name);
            out->set_created_via(cp.created_via);
            send_frame(pipe, write_mu,
                       MessageType::MESSAGE_TYPE_CREATE_CHECKPOINT_REPLY, reply,
                       corr);
            break;
          }
          case MessageType::MESSAGE_TYPE_UPDATE_CHECKPOINT: {
            capture::v1::UpdateCheckpointRequest req;
            capture::v1::UpdateCheckpointReply reply;
            if (!req.ParseFromArray(frame.payload.data(),
                                    static_cast<int>(frame.payload.size()))) {
              set_error(reply.mutable_error(), "BAD_REQUEST", "parse failed");
            } else {
              std::optional<std::string> name_storage;
              std::optional<std::string> notes_storage;
              std::optional<int64_t> eff_storage;
              if (req.has_name()) {
                name_storage = req.name();
              }
              if (req.has_notes()) {
                notes_storage = req.notes();
              }
              if (req.has_effective_timestamp_ns()) {
                eff_storage = req.effective_timestamp_ns();
              }
              const std::string* name =
                  name_storage ? &*name_storage : nullptr;
              const std::string* notes =
                  notes_storage ? &*notes_storage : nullptr;
              const int64_t* eff = eff_storage ? &*eff_storage : nullptr;
              CheckpointEvent out;
              std::string err;
              if (!engine_.update_checkpoint(req.checkpoint_id(), name, notes, eff,
                                             req.modification_reason(), out,
                                             err)) {
                set_error(reply.mutable_error(), "UPDATE_FAILED", err);
              } else {
                auto* cp = reply.mutable_checkpoint();
                cp->set_checkpoint_id(out.checkpoint_id);
                cp->set_original_timestamp_ns(out.original_timestamp_ns);
                cp->set_effective_timestamp_ns(out.effective_timestamp_ns);
                cp->set_name(out.name);
                cp->set_notes(out.notes);
                cp->set_timestamp_modified(out.timestamp_modified);
                cp->set_created_via(out.created_via);
              }
            }
            send_frame(pipe, write_mu,
                       MessageType::MESSAGE_TYPE_UPDATE_CHECKPOINT_REPLY, reply,
                       corr);
            break;
          }
          case MessageType::MESSAGE_TYPE_ANNOTATE: {
            capture::v1::AnnotateRequest req;
            capture::v1::AnnotateReply reply;
            req.ParseFromArray(frame.payload.data(),
                               static_cast<int>(frame.payload.size()));
            auto a = engine_.annotate(req.text(), req.created_via());
            auto* out = reply.mutable_annotation();
            out->set_annotation_id(a.annotation_id);
            out->set_timestamp_ns(a.timestamp_ns);
            out->set_text(a.text);
            out->set_created_via(a.created_via);
            send_frame(pipe, write_mu, MessageType::MESSAGE_TYPE_ANNOTATE_REPLY,
                       reply, corr);
            break;
          }
          case MessageType::MESSAGE_TYPE_ADD_SYNC_ANCHOR: {
            capture::v1::AddSyncAnchorRequest req;
            capture::v1::AddSyncAnchorReply reply;
            req.ParseFromArray(frame.payload.data(),
                               static_cast<int>(frame.payload.size()));
            auto s =
                engine_.add_sync_anchor(req.mechanism(), req.created_via());
            auto* out = reply.mutable_sync_anchor();
            out->set_sync_anchor_id(s.sync_anchor_id);
            out->set_timestamp_ns(s.timestamp_ns);
            out->set_mechanism(s.mechanism);
            out->set_created_via(s.created_via);
            send_frame(pipe, write_mu,
                       MessageType::MESSAGE_TYPE_ADD_SYNC_ANCHOR_REPLY, reply,
                       corr);
            break;
          }
          case MessageType::MESSAGE_TYPE_GET_RECORDING_STATS: {
            capture::v1::GetRecordingStatsReply reply;
            auto stats = engine_.recording_stats();
            reply.set_state(to_proto(stats.state));
            reply.set_elapsed_session_ns(stats.elapsed_session_ns);
            reply.set_total_samples(stats.total_samples);
            reply.set_checkpoint_count(stats.checkpoint_count);
            reply.set_annotation_count(stats.annotation_count);
            reply.set_sync_anchor_count(stats.sync_anchor_count);
            for (const auto& s : stats.streams) {
              auto* row = reply.add_streams();
              row->set_stream_id(s.stream_id);
              row->set_source_id(s.source_id);
              row->set_sample_count(s.sample_count);
              row->set_gap_count(s.gap_count);
              row->set_open_gap_count(s.open_gap_count);
            }
            send_frame(pipe, write_mu,
                       MessageType::MESSAGE_TYPE_GET_RECORDING_STATS_REPLY,
                       reply, corr);
            break;
          }
          case MessageType::MESSAGE_TYPE_INJECT_FAULT: {
            capture::v1::InjectFaultRequest req;
            capture::v1::InjectFaultReply reply;
            if (!req.ParseFromArray(frame.payload.data(),
                                    static_cast<int>(frame.payload.size()))) {
              set_error(reply.mutable_error(), "BAD_REQUEST", "parse failed");
            } else {
              std::string err;
              if (!engine_.inject_fault(req.source_id(), req.fault_type(),
                                        req.drop_count(), err)) {
                set_error(reply.mutable_error(), "FAULT_FAILED", err);
              }
            }
            send_frame(pipe, write_mu, MessageType::MESSAGE_TYPE_INJECT_FAULT_REPLY,
                       reply, corr);
            break;
          }
          case MessageType::MESSAGE_TYPE_LIST_WORKERS: {
            capture::v1::ListWorkersReply reply;
            auto* w = reply.add_workers();
            w->set_worker_id("sim-builtin");
            w->set_plugin_id("sim.builtin");
            w->set_plugin_version("0.1.0");
            w->set_connected(true);
            bool any_camera = false;
            for (const auto& src : engine_.sources()) {
              if (src.is_camera) {
                any_camera = true;
              } else {
                w->add_source_ids(src.source_id);
              }
            }
            if (any_camera) {
              auto* cam = reply.add_workers();
              if (engine_.uses_camera_workers()) {
                cam->set_worker_id("camera-gstreamer");
                cam->set_plugin_id("camera.gstreamer");
              } else {
                cam->set_worker_id("camera-mf");
                cam->set_plugin_id("camera.mf");
              }
              cam->set_plugin_version("0.1.0");
              cam->set_connected(true);
              for (const auto& src : engine_.sources()) {
                if (src.is_camera) {
                  cam->add_source_ids(src.source_id);
                }
              }
            }
            send_frame(pipe, write_mu, MessageType::MESSAGE_TYPE_LIST_WORKERS_REPLY,
                       reply, corr);
            break;
          }
          case MessageType::MESSAGE_TYPE_LIST_PLUGINS: {
            capture::v1::ListPluginsReply reply;
            PluginRegistry::instance().rescan();
            for (const auto& p : PluginRegistry::instance().plugins()) {
              auto* info = reply.add_plugins();
              info->set_plugin_id(p.spec.plugin_id);
              info->set_plugin_version(p.plugin_version);
              info->set_family(p.spec.family);
              info->set_display_name(p.display_name);
              info->set_enabled(p.enabled);
              info->set_disabled_reason(p.disabled_reason);
              info->set_hardware(p.hardware);
              info->set_isolation(p.isolation);
              for (const auto& [k, v] : p.capabilities) {
                (*info->mutable_capabilities())[k] = v;
              }
            }
            send_frame(pipe, write_mu, MessageType::MESSAGE_TYPE_LIST_PLUGINS_REPLY,
                       reply, corr);
            break;
          }
          case MessageType::MESSAGE_TYPE_RUN_PREFLIGHT: {
            capture::v1::RunPreflightRequest req;
            capture::v1::RunPreflightReply reply;
            req.ParseFromArray(frame.payload.data(),
                               static_cast<int>(frame.payload.size()));
            std::vector<std::string> ids(req.source_ids().begin(),
                                         req.source_ids().end());
            bool ok = false;
            std::string err;
            auto checks = engine_.run_preflight(ids, ok, err);
            reply.set_ok(ok);
            for (const auto& c : checks) {
              auto* row = reply.add_checks();
              row->set_check_id(c.check_id);
              row->set_name(c.name);
              row->set_status(c.status);
              row->set_message(c.message);
              row->set_overridable(c.overridable);
            }
            send_frame(pipe, write_mu, MessageType::MESSAGE_TYPE_RUN_PREFLIGHT_REPLY,
                       reply, corr);
            break;
          }
          case MessageType::MESSAGE_TYPE_START_REHEARSAL: {
            capture::v1::StartRehearsalRequest req;
            capture::v1::StartRehearsalReply reply;
            req.ParseFromArray(frame.payload.data(),
                               static_cast<int>(frame.payload.size()));
            std::vector<std::string> ids(req.source_ids().begin(),
                                         req.source_ids().end());
            std::string err;
            if (!engine_.start_rehearsal(ids, err)) {
              set_error(reply.mutable_error(), "REHEARSAL_FAILED", err);
            }
            send_frame(pipe, write_mu,
                       MessageType::MESSAGE_TYPE_START_REHEARSAL_REPLY, reply,
                       corr);
            break;
          }
          case MessageType::MESSAGE_TYPE_LIST_PREVIEW_DESCRIPTORS: {
            capture::v1::ListPreviewDescriptorsRequest req;
            capture::v1::ListPreviewDescriptorsReply reply;
            req.ParseFromArray(frame.payload.data(),
                               static_cast<int>(frame.payload.size()));
            std::vector<std::string> ids(req.source_ids().begin(),
                                         req.source_ids().end());
            for (const auto& d : engine_.list_preview_descriptors(ids)) {
              fill_preview_descriptor(d, reply.add_previews());
            }
            send_frame(pipe, write_mu,
                       MessageType::MESSAGE_TYPE_LIST_PREVIEW_DESCRIPTORS_REPLY,
                       reply, corr);
            break;
          }
          case MessageType::MESSAGE_TYPE_SET_PREVIEW_CONFIG: {
            capture::v1::SetPreviewConfigRequest req;
            capture::v1::SetPreviewConfigReply reply;
            if (!req.ParseFromArray(frame.payload.data(),
                                    static_cast<int>(frame.payload.size()))) {
              set_error(reply.mutable_error(), "BAD_REQUEST", "parse failed");
            } else {
              std::optional<bool> en_storage;
              std::optional<uint32_t> ch_storage;
              if (req.has_enabled()) {
                en_storage = req.enabled();
              }
              if (req.has_selected_channel()) {
                ch_storage = req.selected_channel();
              }
              const bool* en = en_storage ? &*en_storage : nullptr;
              const uint32_t* ch = ch_storage ? &*ch_storage : nullptr;
              PreviewDescriptorData out;
              std::string err;
              if (!engine_.set_preview_config(req.source_id(), en, ch, out, err)) {
                set_error(reply.mutable_error(), "CONFIG_FAILED", err);
              } else {
                fill_preview_descriptor(out, reply.mutable_preview());
              }
            }
            send_frame(pipe, write_mu,
                       MessageType::MESSAGE_TYPE_SET_PREVIEW_CONFIG_REPLY, reply,
                       corr);
            break;
          }
          case MessageType::MESSAGE_TYPE_GET_SESSION_VIEW: {
            capture::v1::GetSessionViewReply reply;
            auto view = engine_.session_view();
            reply.set_session_id(view.session_id);
            reply.set_package_path(view.package_path);
            reply.set_state(to_proto(view.state));
            reply.set_elapsed_session_ns(view.elapsed_session_ns);
            reply.set_t0_wall_clock_utc(view.t0_wall_clock_utc);
            reply.set_rehearsal_active(view.rehearsal_active);
            fill_disk(view.disk, reply.mutable_disk());
            for (const auto& cp : view.checkpoints) {
              auto* out = reply.add_checkpoints();
              out->set_checkpoint_id(cp.checkpoint_id);
              out->set_original_timestamp_ns(cp.original_timestamp_ns);
              out->set_effective_timestamp_ns(cp.effective_timestamp_ns);
              out->set_name(cp.name);
              out->set_notes(cp.notes);
              out->set_created_via(cp.created_via);
              out->set_timestamp_modified(cp.timestamp_modified);
            }
            for (const auto& a : view.annotations) {
              auto* out = reply.add_annotations();
              out->set_annotation_id(a.annotation_id);
              out->set_timestamp_ns(a.timestamp_ns);
              out->set_text(a.text);
              out->set_created_via(a.created_via);
            }
            for (const auto& s : view.sync_anchors) {
              auto* out = reply.add_sync_anchors();
              out->set_sync_anchor_id(s.sync_anchor_id);
              out->set_timestamp_ns(s.timestamp_ns);
              out->set_mechanism(s.mechanism);
              out->set_created_via(s.created_via);
            }
            for (const auto& lane : view.lanes) {
              auto* out = reply.add_lanes();
              out->set_source_id(lane.source_id);
              out->set_stream_id(lane.stream_id);
              out->set_modality(lane.modality);
              out->set_alias(lane.alias);
              out->set_sample_count(lane.sample_count);
              out->set_first_sample_session_ns(lane.first_sample_session_ns);
              out->set_last_sample_session_ns(lane.last_sample_session_ns);
              out->set_lifecycle_state(to_proto(lane.lifecycle));
              for (const auto& g : lane.gaps) {
                auto* ge = out->add_gaps();
                ge->set_source_id(lane.source_id);
                ge->set_stream_id(lane.stream_id);
                ge->set_cause(capture::v1::GAP_CAUSE_DISCONNECT);
                ge->set_start_session_time_ns(g.start_session_time_ns);
                if (g.end_session_time_ns >= 0) {
                  ge->set_end_session_time_ns(g.end_session_time_ns);
                  ge->set_closed(true);
                }
              }
            }
            for (const auto& a : view.alerts) {
              fill_alert(a, reply.add_alerts());
            }
            send_frame(pipe, write_mu,
                       MessageType::MESSAGE_TYPE_GET_SESSION_VIEW_REPLY, reply,
                       corr);
            break;
          }
          case MessageType::MESSAGE_TYPE_SUBSCRIBE_STATUS: {
            capture::v1::SubscribeStatusRequest req;
            capture::v1::SubscribeStatusReply reply;
            req.ParseFromArray(frame.payload.data(),
                               static_cast<int>(frame.payload.size()));
            push.include_preview = req.include_preview() || !req.ByteSizeLong();
            // Default include preview when field unset: proto3 bool defaults false.
            // Prefer explicit true from client; if request empty, include preview.
            if (frame.payload.empty()) {
              push.include_preview = true;
            } else {
              push.include_preview = req.include_preview();
            }
            uint32_t interval = req.health_interval_ms();
            if (interval == 0) {
              interval = 1000;
            }
            push.health_interval_ms = interval;
            push.preview_rate_limit_hz = req.preview_rate_limit_hz();
            reply.set_health_interval_ms(interval);
            reply.set_preview_included(push.include_preview.load());
            push.subscribed = true;
            if (!push_thread.joinable()) {
              push.stop = false;
              push.last_preview_send = std::chrono::steady_clock::now() -
                                       std::chrono::seconds(1);
              push_thread = std::thread([&, pipe] {
                auto last_health = std::chrono::steady_clock::now() -
                                   std::chrono::seconds(2);
                while (!push.stop.load() && running_.load()) {
                  const auto now = std::chrono::steady_clock::now();
                  const auto health_due =
                      now - last_health >=
                      std::chrono::milliseconds(push.health_interval_ms.load());
                  if (health_due) {
                    for (const auto& h : engine_.health_snapshots()) {
                      capture::v1::HealthSnapshot msg;
                      fill_health(h, &msg);
                      if (!send_frame(pipe, write_mu,
                                      MessageType::MESSAGE_TYPE_HEALTH_SNAPSHOT,
                                      msg, 0)) {
                        push.stop = true;
                        break;
                      }
                    }
                    capture::v1::DiskStatus disk;
                    fill_disk(engine_.disk_status(), &disk);
                    send_frame(pipe, write_mu,
                               MessageType::MESSAGE_TYPE_DISK_STATUS, disk, 0);
                    last_health = now;
                  }
                  if (push.include_preview.load()) {
                    const double limit = push.preview_rate_limit_hz.load();
                    bool preview_due = true;
                    if (limit > 0.0) {
                      const auto min_gap = std::chrono::duration<double>(1.0 / limit);
                      preview_due = (now - push.last_preview_send) >= min_gap;
                    }
                    if (preview_due) {
                      bool sent_any = false;
                      for (const auto& f : engine_.latest_preview_frames()) {
                        auto& last = push.last_preview_seq[f.source_id];
                        if (f.sequence != 0 && f.sequence == last) {
                          continue;
                        }
                        last = f.sequence;
                        capture::v1::PreviewFrame msg;
                        fill_preview_frame(f, &msg);
                        if (!send_frame(pipe, write_mu,
                                        MessageType::MESSAGE_TYPE_PREVIEW_FRAME,
                                        msg, 0)) {
                          push.stop = true;
                          break;
                        }
                        sent_any = true;
                      }
                      if (sent_any) {
                        push.last_preview_send = now;
                      }
                    }
                  }
                  {
                    auto alerts = engine_.alert_events_from(push.next_alert);
                    for (const auto& a : alerts) {
                      capture::v1::Alert msg;
                      fill_alert(a, &msg);
                      if (!send_frame(pipe, write_mu,
                                      MessageType::MESSAGE_TYPE_ALERT, msg, 0)) {
                        push.stop = true;
                        break;
                      }
                    }
                    push.next_alert += alerts.size();
                  }
                  std::this_thread::sleep_for(std::chrono::milliseconds(20));
                }
              });
            }
            send_frame(pipe, write_mu,
                       MessageType::MESSAGE_TYPE_SUBSCRIBE_STATUS_REPLY, reply,
                       corr);
            break;
          }
          default: {
            break;
          }
        }
      } catch (const FrameError&) {
        stop_push();
        return;
      }
    }
  }
  stop_push();
}

bool write_instance_file(const std::string& instance_id,
                         const std::string& pipe_name, std::string& error) {
  char* local = nullptr;
  size_t len = 0;
  if (_dupenv_s(&local, &len, "LOCALAPPDATA") != 0 || local == nullptr) {
    error = "LOCALAPPDATA not set";
    return false;
  }
  std::filesystem::path dir = std::filesystem::path(local) / "CaptureSuite";
  free(local);
  std::error_code ec;
  std::filesystem::create_directories(dir, ec);
  if (ec) {
    error = "failed to create CaptureSuite appdata dir";
    return false;
  }
  const auto path = dir / "instance.json";
  std::ofstream out(path, std::ios::trunc);
  if (!out) {
    error = "failed to write instance.json";
    return false;
  }
  auto json_escape = [](const std::string& s) {
    std::string o;
    o.reserve(s.size() + 8);
    for (char c : s) {
      if (c == '\\' || c == '"') {
        o.push_back('\\');
      }
      o.push_back(c);
    }
    return o;
  };
  out << "{\n"
      << "  \"instance_id\": \"" << json_escape(instance_id) << "\",\n"
      << "  \"control_pipe\": \"" << json_escape(pipe_name) << "\",\n"
      << "  \"protocol_major\": " << kProtocolMajor << ",\n"
      << "  \"protocol_minor\": " << kProtocolMinor << "\n"
      << "}\n";
  return true;
}

}  // namespace capture::daemon
