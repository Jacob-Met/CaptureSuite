// SPDX-License-Identifier: GPL-3.0-only
// Milestone 5 camera worker — GStreamer tee/encode/preview (VIDEO_PIPELINE.md).

#include "camera_worker/camera_enumerate.hpp"
#include "camera_worker/worker_session.hpp"

#include "capture/framing.hpp"
#include "capture/version.hpp"

#include "capture/v1/common.pb.h"
#include "capture/v1/preview.pb.h"
#include "capture/v1/worker.pb.h"

#ifndef NOMINMAX
#define NOMINMAX
#endif
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <Windows.h>

#include <algorithm>
#include <cstdio>
#include <cstring>
#include <mutex>
#include <string>
#include <vector>

namespace {

std::mutex g_write_mu;

std::string arg_value(int argc, char** argv, const char* key) {
  for (int i = 1; i + 1 < argc; ++i) {
    if (std::strcmp(argv[i], key) == 0) {
      return argv[i + 1];
    }
  }
  return {};
}

bool write_all(HANDLE pipe, const std::vector<uint8_t>& data) {
  std::lock_guard lock(g_write_mu);
  std::size_t offset = 0;
  while (offset < data.size()) {
    DWORD written = 0;
    if (!WriteFile(pipe, data.data() + offset,
                   static_cast<DWORD>(data.size() - offset), &written,
                   nullptr)) {
      return false;
    }
    offset += written;
  }
  return true;
}

// The control pipe is a synchronous handle, so the OS serializes I/O on it: a
// WriteFile issued from a pipeline thread would block until a pending ReadFile
// completes. Pipeline threads therefore queue frames here and the main loop is
// the only writer.
class Outbox {
 public:
  void push(capture::v1::MessageType type, const std::string& bytes) {
    auto frame = capture::encode_frame(
        static_cast<uint32_t>(type),
        std::span<const uint8_t>(
            reinterpret_cast<const uint8_t*>(bytes.data()), bytes.size()));
    std::lock_guard lock(mu_);
    if (type == capture::v1::MESSAGE_TYPE_PREVIEW_FRAME) {
      latest_preview_ = std::move(frame);  // latest-wins, never backs up
      return;
    }
    queue_.push_back(std::move(frame));
  }

  bool flush(HANDLE pipe) {
    std::vector<std::vector<uint8_t>> pending;
    std::vector<uint8_t> preview;
    {
      std::lock_guard lock(mu_);
      pending.swap(queue_);
      preview.swap(latest_preview_);
    }
    for (const auto& frame : pending) {
      if (!write_all(pipe, frame)) {
        return false;
      }
    }
    return preview.empty() || write_all(pipe, preview);
  }

 private:
  std::mutex mu_;
  std::vector<std::vector<uint8_t>> queue_;
  std::vector<uint8_t> latest_preview_;
};

// 1 = frame ready, 0 = nothing available yet, -1 = pipe closed.
int poll_frame(HANDLE pipe, capture::FrameDecoder& decoder,
               std::vector<uint8_t>& scratch, capture::Frame& frame) {
  if (decoder.pop(frame)) {
    return 1;
  }
  DWORD available = 0;
  if (!PeekNamedPipe(pipe, nullptr, 0, nullptr, &available, nullptr)) {
    return -1;
  }
  if (available == 0) {
    return 0;
  }
  DWORD got = 0;
  const DWORD to_read = static_cast<DWORD>(
      (std::min)(scratch.size(), static_cast<size_t>(available)));
  if (!ReadFile(pipe, scratch.data(), to_read, &got, nullptr) || got == 0) {
    return -1;
  }
  decoder.feed(std::span<const uint8_t>(scratch.data(), got));
  return decoder.pop(frame) ? 1 : 0;
}

bool read_frame(HANDLE pipe, capture::FrameDecoder& decoder,
                std::vector<uint8_t>& scratch, capture::Frame& frame,
                DWORD timeout_ms) {
  const auto deadline = GetTickCount64() + timeout_ms;
  for (;;) {
    const int got = poll_frame(pipe, decoder, scratch, frame);
    if (got == 1) {
      return true;
    }
    if (got < 0 || GetTickCount64() >= deadline) {
      return false;
    }
    Sleep(2);
  }
}

template <typename Msg>
bool send_msg(HANDLE pipe, capture::v1::MessageType type, const Msg& msg,
              uint32_t corr) {
  std::string bytes;
  if (!msg.SerializeToString(&bytes)) {
    return false;
  }
  auto frame = capture::encode_frame(
      static_cast<uint32_t>(type),
      std::span<const uint8_t>(reinterpret_cast<const uint8_t*>(bytes.data()),
                               bytes.size()),
      corr);
  return write_all(pipe, frame);
}

}  // namespace

int main(int argc, char** argv) {
  const std::string pipe_name = arg_value(argc, argv, "--pipe");
  const std::string worker_id = arg_value(argc, argv, "--worker-id");
  std::string plugin_id = arg_value(argc, argv, "--plugin");
  if (pipe_name.empty() || worker_id.empty()) {
    std::fprintf(stderr,
                 "usage: capture_worker_camera --pipe <name> --worker-id <id> "
                 "[--plugin camera.gstreamer]\n");
    return 2;
  }
  if (plugin_id.empty()) {
    plugin_id = "camera.gstreamer";
  }

  const std::string gst_err = capture::camera_worker::init_gstreamer();
  if (!gst_err.empty()) {
    std::fprintf(stderr, "camera worker: %s\n", gst_err.c_str());
    return 1;
  }

  HANDLE pipe = INVALID_HANDLE_VALUE;
  for (int attempt = 0; attempt < 100; ++attempt) {
    pipe = CreateFileA(pipe_name.c_str(), GENERIC_READ | GENERIC_WRITE, 0,
                       nullptr, OPEN_EXISTING, 0, nullptr);
    if (pipe != INVALID_HANDLE_VALUE) {
      break;
    }
    Sleep(20);
  }
  if (pipe == INVALID_HANDLE_VALUE) {
    std::fprintf(stderr, "camera worker: failed to connect to %s\n",
                 pipe_name.c_str());
    return 1;
  }

  Outbox outbox;
  capture::FrameDecoder decoder;
  std::vector<uint8_t> scratch(64 * 1024);

  capture::camera_worker::WorkerSession session(plugin_id);
  session.set_outbound(
      [&outbox](capture::v1::MessageType type, const std::string& bytes) {
        outbox.push(type, bytes);
      });

  capture::v1::Hello hello;
  hello.mutable_protocol()->set_major(1);
  hello.mutable_protocol()->set_minor(4);
  hello.set_role("worker");
  hello.set_plugin_id(plugin_id);
  hello.set_plugin_version("0.1.0");
  hello.set_worker_id(worker_id);
  hello.mutable_min_daemon_protocol()->set_major(1);
  hello.mutable_min_daemon_protocol()->set_minor(0);
  hello.mutable_max_daemon_protocol()->set_major(1);
  hello.mutable_max_daemon_protocol()->set_minor(99);
  hello.set_supported_operations(
      static_cast<uint32_t>(capture::v1::WORKER_OPERATION_PREVIEW) |
      static_cast<uint32_t>(capture::v1::WORKER_OPERATION_ARM));
  hello.mutable_component()->set_major(0);
  hello.mutable_component()->set_minor(1);
  hello.mutable_component()->set_patch(0);
  hello.mutable_component()->set_git_describe(capture::version_string());

  if (!send_msg(pipe, capture::v1::MESSAGE_TYPE_HELLO, hello, 0)) {
    CloseHandle(pipe);
    return 1;
  }

  capture::Frame ack_frame;
  if (!read_frame(pipe, decoder, scratch, ack_frame, 30000) ||
      ack_frame.message_type !=
          static_cast<uint32_t>(capture::v1::MESSAGE_TYPE_HELLO_ACK)) {
    CloseHandle(pipe);
    return 1;
  }
  capture::v1::HelloAck ack;
  if (!ack.ParseFromArray(ack_frame.payload.data(),
                          static_cast<int>(ack_frame.payload.size())) ||
      !ack.accepted()) {
    CloseHandle(pipe);
    return 1;
  }

  for (;;) {
    if (!outbox.flush(pipe)) {
      break;
    }
    capture::Frame frame;
    const int got = poll_frame(pipe, decoder, scratch, frame);
    if (got < 0) {
      break;
    }
    if (got == 0) {
      Sleep(2);
      continue;
    }
    const auto type = static_cast<capture::v1::MessageType>(frame.message_type);
    if (type == capture::v1::MESSAGE_TYPE_IDENTIFY) {
      capture::v1::IdentifyReply reply;
      *reply.mutable_manifest() = session.build_manifest();
      if (!send_msg(pipe, capture::v1::MESSAGE_TYPE_IDENTIFY_REPLY, reply,
                    frame.correlation_id)) {
        break;
      }
    } else if (type == capture::v1::MESSAGE_TYPE_DISCOVER) {
      session.refresh_devices();
      capture::v1::DiscoverReply reply;
      session.fill_discover(&reply);
      if (!send_msg(pipe, capture::v1::MESSAGE_TYPE_DISCOVER_REPLY, reply,
                    frame.correlation_id)) {
        break;
      }
    } else if (type == capture::v1::MESSAGE_TYPE_CONNECT) {
      capture::v1::ConnectRequest req;
      capture::v1::ConnectReply reply;
      if (!req.ParseFromArray(frame.payload.data(),
                              static_cast<int>(frame.payload.size()))) {
        reply.mutable_error()->set_code("BAD_REQUEST");
        reply.mutable_error()->set_message("parse failed");
      } else {
        session.connect_source(req.source_id(), &reply);
      }
      if (!send_msg(pipe, capture::v1::MESSAGE_TYPE_CONNECT_REPLY, reply,
                    frame.correlation_id)) {
        break;
      }
    } else if (type == capture::v1::MESSAGE_TYPE_START) {
      capture::v1::StartRequest req;
      capture::v1::StartReply reply;
      if (!req.ParseFromArray(frame.payload.data(),
                              static_cast<int>(frame.payload.size()))) {
        reply.mutable_error()->set_code("BAD_REQUEST");
        reply.mutable_error()->set_message("parse failed");
      } else {
        session.start_source(req, &reply);
      }
      if (!send_msg(pipe, capture::v1::MESSAGE_TYPE_START_REPLY, reply,
                    frame.correlation_id)) {
        break;
      }
    } else if (type == capture::v1::MESSAGE_TYPE_STOP) {
      capture::v1::StopRequest req;
      capture::v1::StopReply reply;
      if (!req.ParseFromArray(frame.payload.data(),
                              static_cast<int>(frame.payload.size()))) {
        reply.mutable_error()->set_code("BAD_REQUEST");
        reply.mutable_error()->set_message("parse failed");
      } else {
        session.stop_source(req.source_id(), &reply);
      }
      // Flush SegmentSealed (and any trailing health) before the Stop reply so
      // the daemon's RPC loop can stash them while still waiting for the reply.
      if (!outbox.flush(pipe)) {
        break;
      }
      if (!send_msg(pipe, capture::v1::MESSAGE_TYPE_STOP_REPLY, reply,
                    frame.correlation_id)) {
        break;
      }
    } else if (type == capture::v1::MESSAGE_TYPE_GET_PREVIEW_DESCRIPTOR) {
      capture::v1::GetPreviewDescriptorRequest req;
      capture::v1::GetPreviewDescriptorReply reply;
      if (!req.ParseFromArray(frame.payload.data(),
                              static_cast<int>(frame.payload.size()))) {
        reply.mutable_error()->set_code("BAD_REQUEST");
        reply.mutable_error()->set_message("parse failed");
      } else {
        session.preview_descriptor(req.source_id(), &reply);
      }
      if (!send_msg(pipe,
                    capture::v1::MESSAGE_TYPE_GET_PREVIEW_DESCRIPTOR_REPLY,
                    reply, frame.correlation_id)) {
        break;
      }
    } else if (type == capture::v1::MESSAGE_TYPE_GET_CONFIG_SCHEMA) {
      capture::v1::GetConfigSchemaRequest req;
      capture::v1::GetConfigSchemaReply reply;
      if (!req.ParseFromArray(frame.payload.data(),
                              static_cast<int>(frame.payload.size()))) {
        reply.mutable_error()->set_code("BAD_REQUEST");
        reply.mutable_error()->set_message("parse failed");
      } else {
        session.get_config_schema(req.source_id(), &reply);
      }
      if (!send_msg(pipe, capture::v1::MESSAGE_TYPE_GET_CONFIG_SCHEMA_REPLY,
                    reply, frame.correlation_id)) {
        break;
      }
    } else if (type == capture::v1::MESSAGE_TYPE_APPLY_CONFIG) {
      capture::v1::ApplyConfigRequest req;
      capture::v1::ApplyConfigReply reply;
      if (!req.ParseFromArray(frame.payload.data(),
                              static_cast<int>(frame.payload.size()))) {
        reply.mutable_error()->set_code("BAD_REQUEST");
        reply.mutable_error()->set_message("parse failed");
      } else {
        session.apply_config(req, &reply);
      }
      if (!send_msg(pipe, capture::v1::MESSAGE_TYPE_APPLY_CONFIG_REPLY, reply,
                    frame.correlation_id)) {
        break;
      }
    } else if (type == capture::v1::MESSAGE_TYPE_SHUTDOWN) {
      capture::v1::StopReply stop;
      session.stop_source("", &stop);
      capture::v1::ShutdownReply reply;
      send_msg(pipe, capture::v1::MESSAGE_TYPE_SHUTDOWN_REPLY, reply,
               frame.correlation_id);
      break;
    } else if (type == capture::v1::MESSAGE_TYPE_SEGMENT_SEALED_ACK) {
      // Fire-and-forget ack from daemon; ignore.
    } else {
      std::fprintf(stderr, "camera worker: ignoring message_type=%u\n",
                   frame.message_type);
    }
  }

  CloseHandle(pipe);
  return 0;
}
