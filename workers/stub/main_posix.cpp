// SPDX-License-Identifier: Apache-2.0
// POSIX worker-host test stub. Protocol semantics mirror the Windows stub;
// only the local transport changes from a named pipe to an AF_UNIX stream.

#include "capture/framing.hpp"
#include "capture/version.hpp"

#include "capture/v1/common.pb.h"
#include "capture/v1/source.pb.h"
#include "capture/v1/worker.pb.h"

#include <cerrno>
#include <chrono>
#include <cstdio>
#include <cstring>
#include <string>
#include <sys/socket.h>
#include <sys/un.h>
#include <thread>
#include <unistd.h>
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

void configure_socket_no_sigpipe(int fd) {
#if defined(__APPLE__)
  int enabled = 1;
  (void)setsockopt(fd, SOL_SOCKET, SO_NOSIGPIPE, &enabled, sizeof(enabled));
#else
  (void)fd;
#endif
}

bool write_all(int fd, const std::vector<uint8_t>& data) {
  std::size_t offset = 0;
  while (offset < data.size()) {
#ifdef MSG_NOSIGNAL
    constexpr int flags = MSG_NOSIGNAL;
#else
    constexpr int flags = 0;
#endif
    const ssize_t written = send(fd, data.data() + offset, data.size() - offset, flags);
    if (written < 0 && errno == EINTR) {
      continue;
    }
    if (written <= 0) {
      return false;
    }
    offset += static_cast<std::size_t>(written);
  }
  return true;
}

bool read_frame(int fd, capture::Frame& frame) {
  capture::FrameDecoder decoder;
  std::vector<uint8_t> chunk(64 * 1024);
  for (;;) {
    ssize_t got = 0;
    do {
      got = recv(fd, chunk.data(), chunk.size(), 0);
    } while (got < 0 && errno == EINTR);
    if (got <= 0) {
      return false;
    }
    decoder.feed(
        std::span<const uint8_t>(chunk.data(), static_cast<std::size_t>(got)));
    if (decoder.pop(frame)) {
      return true;
    }
  }
}

int connect_worker_socket(const std::string& path) {
  sockaddr_un address{};
  address.sun_family = AF_UNIX;
  if (path.size() >= sizeof(address.sun_path)) {
    return -1;
  }
  std::memcpy(address.sun_path, path.c_str(), path.size() + 1);

  for (int attempt = 0; attempt < 100; ++attempt) {
    const int fd = socket(AF_UNIX, SOCK_STREAM, 0);
    if (fd < 0) {
      return -1;
    }
    configure_socket_no_sigpipe(fd);
    if (connect(fd, reinterpret_cast<sockaddr*>(&address), sizeof(address)) == 0) {
      return fd;
    }
    (void)close(fd);
    std::this_thread::sleep_for(std::chrono::milliseconds(20));
  }
  return -1;
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

  const int channel = connect_worker_socket(pipe_name);
  if (channel < 0) {
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
    if (!write_all(channel, frame)) {
      (void)close(channel);
      return 1;
    }
  }

  capture::Frame ack_frame;
  if (!read_frame(channel, ack_frame) ||
      ack_frame.message_type !=
          static_cast<uint32_t>(capture::v1::MESSAGE_TYPE_HELLO_ACK)) {
    (void)close(channel);
    return 1;
  }
  capture::v1::HelloAck ack;
  if (!ack.ParseFromArray(ack_frame.payload.data(),
                          static_cast<int>(ack_frame.payload.size())) ||
      !ack.accepted()) {
    (void)close(channel);
    return 1;
  }

  capture::Frame id_req_frame;
  if (!read_frame(channel, id_req_frame) ||
      id_req_frame.message_type !=
          static_cast<uint32_t>(capture::v1::MESSAGE_TYPE_IDENTIFY)) {
    (void)close(channel);
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
    if (!write_all(channel, frame)) {
      (void)close(channel);
      return 1;
    }
  }

  // Stay alive until the host closes the socket or terminates us.
  for (;;) {
    capture::Frame ignored;
    if (!read_frame(channel, ignored)) {
      break;
    }
  }
  (void)close(channel);
  return 0;
}
