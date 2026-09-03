// SPDX-License-Identifier: Apache-2.0
// Minimal out-of-process worker for WorkerHost tests (WORKER_HOST.md).
// Speaks Hello + Identify only; no capture path.

#include "capture/framing.hpp"
#include "capture/version.hpp"

#include "capture/v1/common.pb.h"
#include "capture/v1/source.pb.h"
#include "capture/v1/worker.pb.h"

#ifndef NOMINMAX
#define NOMINMAX
#endif
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <Windows.h>

#include <cstdio>
#include <cstring>
#include <string>
#include <vector>

namespace {

std::string arg_value(int argc, char** argv, const char* key) {
  for (int i = 1; i + 1 < argc; ++i) {
    if (std::strcmp(argv[i], key) == 0) {
      return argv[i + 1];
    }
  }
  return {};
}

bool write_all(HANDLE pipe, const std::vector<uint8_t>& data) {
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

bool read_frame(HANDLE pipe, capture::Frame& frame) {
  capture::FrameDecoder decoder;
  std::vector<uint8_t> chunk(64 * 1024);
  for (;;) {
    DWORD got = 0;
    if (!ReadFile(pipe, chunk.data(), static_cast<DWORD>(chunk.size()), &got,
                  nullptr)) {
      return false;
    }
    if (got == 0) {
      return false;
    }
    decoder.feed(std::span<const uint8_t>(chunk.data(), got));
    if (decoder.pop(frame)) {
      return true;
    }
  }
}

}  // namespace

int main(int argc, char** argv) {
  const std::string pipe_name = arg_value(argc, argv, "--pipe");
  const std::string worker_id = arg_value(argc, argv, "--worker-id");
  const std::string plugin_id = arg_value(argc, argv, "--plugin");
  if (pipe_name.empty() || worker_id.empty() || plugin_id.empty()) {
    std::fprintf(stderr,
                 "usage: capture_worker_stub --pipe <name> --worker-id <id> "
                 "--plugin <plugin_id>\n");
    return 2;
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
    std::fprintf(stderr, "stub: failed to connect to %s\n", pipe_name.c_str());
    return 1;
  }

  capture::v1::Hello hello;
  hello.mutable_protocol()->set_major(1);
  hello.mutable_protocol()->set_minor(3);
  hello.set_role("worker");
  hello.set_plugin_id(plugin_id);
  hello.mutable_min_daemon_protocol()->set_major(1);
  hello.mutable_min_daemon_protocol()->set_minor(0);
  hello.mutable_max_daemon_protocol()->set_major(1);
  hello.mutable_max_daemon_protocol()->set_minor(99);
  hello.mutable_component()->set_major(0);
  hello.mutable_component()->set_minor(1);
  hello.mutable_component()->set_patch(0);
  hello.mutable_component()->set_git_describe(capture::version_string());

  {
    std::string bytes;
    hello.SerializeToString(&bytes);
    auto frame = capture::encode_frame(
        static_cast<uint32_t>(capture::v1::MESSAGE_TYPE_HELLO),
        std::span<const uint8_t>(
            reinterpret_cast<const uint8_t*>(bytes.data()), bytes.size()));
    if (!write_all(pipe, frame)) {
      CloseHandle(pipe);
      return 1;
    }
  }

  capture::Frame ack_frame;
  if (!read_frame(pipe, ack_frame) ||
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

  capture::Frame id_req_frame;
  if (!read_frame(pipe, id_req_frame) ||
      id_req_frame.message_type !=
          static_cast<uint32_t>(capture::v1::MESSAGE_TYPE_IDENTIFY)) {
    CloseHandle(pipe);
    return 1;
  }

  capture::v1::IdentifyReply reply;
  auto* manifest = reply.mutable_manifest();
  manifest->set_plugin_id(plugin_id);
  manifest->set_plugin_version("0.1.0");
  manifest->mutable_capabilities()->insert({"isolation", "per_source"});
  auto* src = manifest->add_sources();
  src->set_source_id("stub.source.1");
  src->set_source_type("stub");
  src->set_alias("Stub Source");
  src->set_plugin_id(plugin_id);
  src->set_plugin_version("0.1.0");
  src->set_enabled(true);
  src->mutable_metadata()->insert({"modality", "stub"});

  {
    std::string bytes;
    reply.SerializeToString(&bytes);
    auto frame = capture::encode_frame(
        static_cast<uint32_t>(capture::v1::MESSAGE_TYPE_IDENTIFY_REPLY),
        std::span<const uint8_t>(
            reinterpret_cast<const uint8_t*>(bytes.data()), bytes.size()),
        id_req_frame.correlation_id);
    if (!write_all(pipe, frame)) {
      CloseHandle(pipe);
      return 1;
    }
  }

  // Stay alive until the host closes the pipe or terminates us.
  for (;;) {
    capture::Frame ignored;
    if (!read_frame(pipe, ignored)) {
      break;
    }
  }
  CloseHandle(pipe);
  return 0;
}
