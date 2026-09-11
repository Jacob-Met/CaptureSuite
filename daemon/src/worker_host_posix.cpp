// SPDX-License-Identifier: GPL-3.0-only
#include "capture_daemon/worker_host.hpp"

#include "capture/env.hpp"
#include "capture/framing.hpp"
#include "capture/logging.hpp"
#include "capture_daemon/handshake.hpp"

#include "capture/v1/common.pb.h"
#include "capture/v1/health.pb.h"
#include "capture/v1/preview.pb.h"

#include <algorithm>
#include <cerrno>
#include <chrono>
#include <cstdint>
#include <cstring>
#include <fcntl.h>
#include <filesystem>
#include <iomanip>
#include <poll.h>
#include <signal.h>
#include <span>
#include <sstream>
#include <string>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/un.h>
#include <sys/wait.h>
#include <thread>
#include <unistd.h>
#include <vector>

namespace capture::daemon {
namespace {

constexpr std::size_t kIoChunk = 64 * 1024;

int channel_fd(void* channel) {
  return static_cast<int>(reinterpret_cast<std::intptr_t>(channel));
}

void* channel_handle(int fd) {
  return reinterpret_cast<void*>(static_cast<std::intptr_t>(fd));
}

uint64_t monotonic_ms() {
  return static_cast<uint64_t>(
      std::chrono::duration_cast<std::chrono::milliseconds>(
          std::chrono::steady_clock::now().time_since_epoch())
          .count());
}

void configure_socket_no_sigpipe(int fd) {
#if defined(__APPLE__)
  int enabled = 1;
  (void)setsockopt(fd, SOL_SOCKET, SO_NOSIGPIPE, &enabled, sizeof(enabled));
#else
  (void)fd;
#endif
}

bool write_all(void* channel, const std::vector<uint8_t>& data) {
  const int fd = channel_fd(channel);
  std::size_t offset = 0;
  while (offset < data.size()) {
#ifdef MSG_NOSIGNAL
    constexpr int flags = MSG_NOSIGNAL;
#else
    constexpr int flags = 0;
#endif
    const ssize_t written =
        send(fd, data.data() + offset, data.size() - offset, flags);
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

bool pump_bytes(void* channel, capture::FrameDecoder& decoder,
                uint64_t timeout_ms) {
  const int fd = channel_fd(channel);
  const int timeout = static_cast<int>((std::min<uint64_t>)(timeout_ms, 60000));
  pollfd pfd{};
  pfd.fd = fd;
  pfd.events = POLLIN;
  int ready = 0;
  do {
    ready = poll(&pfd, 1, timeout);
  } while (ready < 0 && errno == EINTR);
  if (ready <= 0 || (pfd.revents & (POLLERR | POLLNVAL)) != 0) {
    return false;
  }
  std::vector<uint8_t> chunk(kIoChunk);
  ssize_t got = 0;
  do {
    got = recv(fd, chunk.data(), chunk.size(), 0);
  } while (got < 0 && errno == EINTR);
  if (got <= 0) {
    return false;
  }
  decoder.feed(std::span<const uint8_t>(chunk.data(), static_cast<std::size_t>(got)));
  return true;
}

bool read_frame(void* channel, capture::FrameDecoder& decoder,
                capture::Frame& frame, uint64_t timeout_ms) {
  if (decoder.pop(frame)) {
    return true;
  }
  const uint64_t deadline = monotonic_ms() + timeout_ms;
  while (monotonic_ms() < deadline) {
    const uint64_t now = monotonic_ms();
    const uint64_t remain = (std::max<uint64_t>)(1, deadline - now);
    if (!pump_bytes(channel, decoder, remain)) {
      return decoder.pop(frame);
    }
    if (decoder.pop(frame)) {
      return true;
    }
  }
  return decoder.pop(frame);
}

bool channel_has_data(void* channel) {
  pollfd pfd{};
  pfd.fd = channel_fd(channel);
  pfd.events = POLLIN;
  int ready = 0;
  do {
    ready = poll(&pfd, 1, 0);
  } while (ready < 0 && errno == EINTR);
  return ready > 0 && (pfd.revents & POLLIN) != 0;
}

void stash_unsolicited(SpawnedWorker& worker, const capture::Frame& frame) {
  if (frame.message_type ==
      static_cast<uint32_t>(capture::v1::MESSAGE_TYPE_PREVIEW_FRAME)) {
    capture::v1::PreviewFrame preview;
    if (preview.ParseFromArray(frame.payload.data(),
                               static_cast<int>(frame.payload.size()))) {
      worker.pending_previews.push_back(std::move(preview));
    }
    return;
  }
  if (frame.message_type ==
      static_cast<uint32_t>(capture::v1::MESSAGE_TYPE_SEGMENT_SEALED)) {
    capture::v1::SegmentSealed sealed;
    if (sealed.ParseFromArray(frame.payload.data(),
                              static_cast<int>(frame.payload.size()))) {
      worker.pending_sealed.push_back(std::move(sealed));
    }
    return;
  }
  if (frame.message_type ==
      static_cast<uint32_t>(capture::v1::MESSAGE_TYPE_HEALTH_SNAPSHOT)) {
    capture::v1::HealthSnapshot health;
    if (health.ParseFromArray(frame.payload.data(),
                              static_cast<int>(frame.payload.size()))) {
      worker.pending_health.push_back(std::move(health));
    }
    return;
  }
  if (frame.message_type ==
      static_cast<uint32_t>(capture::v1::MESSAGE_TYPE_OVERLOAD_EVENT)) {
    capture::v1::OverloadEvent overload;
    if (overload.ParseFromArray(frame.payload.data(),
                                static_cast<int>(frame.payload.size()))) {
      worker.pending_overloads.push_back(std::move(overload));
    }
  }
}

bool ack_segment_sealed(void* channel,
                        const capture::v1::SegmentSealed& /*sealed*/,
                        uint32_t correlation_id) {
  capture::v1::SegmentSealedAck ack;
  std::string bytes;
  ack.SerializeToString(&bytes);
  auto out = capture::encode_frame(
      static_cast<uint32_t>(capture::v1::MESSAGE_TYPE_SEGMENT_SEALED_ACK),
      std::span<const uint8_t>(reinterpret_cast<const uint8_t*>(bytes.data()),
                               bytes.size()),
      correlation_id);
  return write_all(channel, out);
}

int await_accept(int listener, uint64_t timeout_ms) {
  pollfd pfd{};
  pfd.fd = listener;
  pfd.events = POLLIN;
  const int timeout = static_cast<int>((std::min<uint64_t>)(timeout_ms, 60000));
  int ready = 0;
  do {
    ready = poll(&pfd, 1, timeout);
  } while (ready < 0 && errno == EINTR);
  if (ready <= 0 || (pfd.revents & POLLIN) == 0) {
    return -1;
  }
  int fd = -1;
  do {
    fd = accept(listener, nullptr, nullptr);
  } while (fd < 0 && errno == EINTR);
  if (fd >= 0) {
    configure_socket_no_sigpipe(fd);
  }
  return fd;
}

void close_channel(void*& channel) {
  if (channel != nullptr) {
    const int fd = channel_fd(channel);
    if (fd >= 0) {
      (void)close(fd);
    }
  }
  channel = nullptr;
}

uint64_t fnv1a64(std::string_view value) {
  uint64_t hash = 1469598103934665603ULL;
  for (const unsigned char ch : value) {
    hash ^= static_cast<uint64_t>(ch);
    hash *= 1099511628211ULL;
  }
  return hash;
}

bool wait_for_stopped_child(pid_t pid, std::string& error) {
  int status = 0;
  pid_t observed = -1;
  do {
    observed = waitpid(pid, &status, WUNTRACED);
  } while (observed < 0 && errno == EINTR);
  if (observed != pid || !WIFSTOPPED(status)) {
    error = "worker child did not enter suspended pre-exec state";
    return false;
  }
  return true;
}

bool terminate_child(pid_t pid) {
  int status = 0;
  pid_t observed = waitpid(pid, &status, WNOHANG);
  if (observed == pid || (observed < 0 && errno == ECHILD)) {
    return true;
  }
  if (observed < 0) {
    return false;
  }
  (void)kill(pid, SIGTERM);
  for (int i = 0; i < 20; ++i) {
    observed = waitpid(pid, &status, WNOHANG);
    if (observed == pid || (observed < 0 && errno == ECHILD)) {
      return true;
    }
    std::this_thread::sleep_for(std::chrono::milliseconds(10));
  }
  (void)kill(pid, SIGKILL);
  do {
    observed = waitpid(pid, &status, 0);
  } while (observed < 0 && errno == EINTR);
  return observed == pid || (observed < 0 && errno == ECHILD);
}

template <typename Req, typename Reply>
bool worker_rpc(SpawnedWorker& worker, capture::v1::MessageType req_type,
                capture::v1::MessageType reply_type, const Req& req,
                Reply& reply, uint32_t corr, uint64_t timeout_ms,
                std::string& error) {
  std::lock_guard io_lock(*worker.io_mutex);
  std::string bytes;
  req.SerializeToString(&bytes);
  auto frame = capture::encode_frame(
      static_cast<uint32_t>(req_type),
      std::span<const uint8_t>(reinterpret_cast<const uint8_t*>(bytes.data()),
                               bytes.size()),
      corr);
  if (!write_all(worker.pipe, frame)) {
    error = "failed to write RPC";
    return false;
  }
  const uint64_t deadline = monotonic_ms() + timeout_ms;
  while (monotonic_ms() < deadline) {
    const uint64_t now = monotonic_ms();
    const uint64_t remain = (std::max<uint64_t>)(1, deadline - now);
    capture::Frame resp;
    if (!read_frame(worker.pipe, worker.decoder, resp, remain)) {
      error = "timed out waiting for RPC reply";
      return false;
    }
    if (resp.message_type == static_cast<uint32_t>(reply_type)) {
      if (!reply.ParseFromArray(resp.payload.data(),
                                static_cast<int>(resp.payload.size()))) {
        error = "failed to parse RPC reply";
        return false;
      }
      return true;
    }
    stash_unsolicited(worker, resp);
    if (resp.message_type ==
        static_cast<uint32_t>(capture::v1::MESSAGE_TYPE_SEGMENT_SEALED)) {
      (void)ack_segment_sealed(worker.pipe, capture::v1::SegmentSealed{},
                               resp.correlation_id);
    }
  }
  error = "timed out waiting for RPC reply";
  return false;
}

}  // namespace

std::string worker_pipe_name(const std::string& instance_id,
                             const std::string& worker_id) {
  std::ostringstream hex;
  hex << std::hex << fnv1a64(instance_id + "\n" + worker_id);
  return "/tmp/capturesuite-worker-" + std::to_string(getpid()) + "-" +
         hex.str() + ".sock";
}

WorkerHost::WorkerHost(DaemonJob& job, std::string instance_id)
    : job_(job), instance_id_(std::move(instance_id)) {}

bool WorkerHost::spawn(const std::filesystem::path& executable,
                       const std::string& worker_id,
                       const std::string& plugin_id, SpawnedWorker& out,
                       std::string& error,
                       std::chrono::milliseconds connect_timeout) {
  out = SpawnedWorker{};
  out.worker_id = worker_id;
  out.plugin_id = plugin_id;
  out.pipe_name = worker_pipe_name(instance_id_, worker_id);

  if (out.pipe_name.size() >= sizeof(sockaddr_un::sun_path)) {
    error = "worker Unix socket path is too long";
    return false;
  }
  if (std::filesystem::exists(out.pipe_name)) {
    error = "worker Unix socket path already exists";
    return false;
  }

  const int listener = socket(AF_UNIX, SOCK_STREAM, 0);
  if (listener < 0) {
    error = "socket(AF_UNIX) failed";
    return false;
  }
  configure_socket_no_sigpipe(listener);
  sockaddr_un address{};
  address.sun_family = AF_UNIX;
  std::memcpy(address.sun_path, out.pipe_name.c_str(), out.pipe_name.size() + 1);
  if (bind(listener, reinterpret_cast<sockaddr*>(&address), sizeof(address)) != 0) {
    (void)close(listener);
    error = "bind worker Unix socket failed: " + std::string(std::strerror(errno));
    return false;
  }
  if (chmod(out.pipe_name.c_str(), S_IRUSR | S_IWUSR) != 0) {
    (void)close(listener);
    (void)unlink(out.pipe_name.c_str());
    error = "chmod worker Unix socket failed";
    return false;
  }
  if (listen(listener, 1) != 0) {
    (void)close(listener);
    (void)unlink(out.pipe_name.c_str());
    error = "listen worker Unix socket failed";
    return false;
  }

  const std::string executable_text = executable.string();
  const std::string executable_name = executable.filename().string();
  const std::string stderr_log =
      capture::env::get("CAPTURE_WORKER_STDERR_LOG").value_or("");

  const pid_t pid = fork();
  if (pid < 0) {
    (void)close(listener);
    (void)unlink(out.pipe_name.c_str());
    error = "fork worker failed";
    return false;
  }
  if (pid == 0) {
    (void)raise(SIGSTOP);
    if (!stderr_log.empty()) {
      const int log_fd = open(stderr_log.c_str(), O_WRONLY | O_CREAT | O_TRUNC, 0600);
      if (log_fd >= 0) {
        (void)dup2(log_fd, STDOUT_FILENO);
        (void)dup2(log_fd, STDERR_FILENO);
        if (log_fd > STDERR_FILENO) {
          (void)close(log_fd);
        }
      }
    }
    execl(executable_text.c_str(), executable_name.c_str(), "--pipe",
          out.pipe_name.c_str(), "--worker-id", worker_id.c_str(), "--plugin",
          plugin_id.c_str(), static_cast<char*>(nullptr));
    _exit(127);
  }

  out.pid = static_cast<std::uint32_t>(pid);
  out.process = reinterpret_cast<void*>(static_cast<std::intptr_t>(pid));
  out.thread = nullptr;

  if (!wait_for_stopped_child(pid, error)) {
    (void)terminate_child(pid);
    (void)close(listener);
    (void)unlink(out.pipe_name.c_str());
    out.process = nullptr;
    out.pid = 0;
    return false;
  }
  if (!job_.assign_process(out.process, error)) {
    (void)terminate_child(pid);
    (void)close(listener);
    (void)unlink(out.pipe_name.c_str());
    out.process = nullptr;
    out.pid = 0;
    return false;
  }
  if (kill(pid, SIGCONT) != 0) {
    error = "SIGCONT worker failed";
    stop(out);
    (void)close(listener);
    (void)unlink(out.pipe_name.c_str());
    return false;
  }

  const uint64_t timeout_ms =
      static_cast<uint64_t>((std::max)(connect_timeout.count(), 1LL));
  const int accepted = await_accept(listener, timeout_ms);
  (void)close(listener);
  (void)unlink(out.pipe_name.c_str());
  if (accepted < 0) {
    error = "worker did not connect to Unix socket";
    stop(out);
    return false;
  }
  out.pipe = channel_handle(accepted);

  {
    std::string peer_error;
    if (!peer_sid_matches_self(out.pipe, peer_error)) {
      error = "worker peer UID rejected: " + peer_error;
      stop(out);
      return false;
    }
  }

  capture::Frame hello_frame;
  if (!read_frame(out.pipe, out.decoder, hello_frame, timeout_ms)) {
    error = "timed out waiting for worker Hello";
    stop(out);
    return false;
  }
  if (hello_frame.message_type !=
      static_cast<uint32_t>(capture::v1::MESSAGE_TYPE_HELLO)) {
    error = "first worker frame was not Hello";
    stop(out);
    return false;
  }
  capture::v1::Hello hello;
  if (!hello.ParseFromArray(hello_frame.payload.data(),
                            static_cast<int>(hello_frame.payload.size()))) {
    error = "failed to parse worker Hello";
    stop(out);
    return false;
  }
  const auto ack = negotiate_hello(hello, instance_id_);
  {
    std::string bytes;
    ack.SerializeToString(&bytes);
    auto frame = capture::encode_frame(
        static_cast<uint32_t>(capture::v1::MESSAGE_TYPE_HELLO_ACK),
        std::span<const uint8_t>(
            reinterpret_cast<const uint8_t*>(bytes.data()), bytes.size()),
        hello_frame.correlation_id);
    if (!write_all(out.pipe, frame)) {
      error = "failed to write HelloAck";
      stop(out);
      return false;
    }
  }
  if (!ack.accepted()) {
    error = "worker Hello rejected: " + ack.error().message();
    stop(out);
    return false;
  }

  capture::v1::IdentifyRequest identify;
  {
    std::string bytes;
    identify.SerializeToString(&bytes);
    auto frame = capture::encode_frame(
        static_cast<uint32_t>(capture::v1::MESSAGE_TYPE_IDENTIFY),
        std::span<const uint8_t>(
            reinterpret_cast<const uint8_t*>(bytes.data()), bytes.size()),
        1);
    if (!write_all(out.pipe, frame)) {
      error = "failed to write Identify";
      stop(out);
      return false;
    }
  }

  capture::Frame id_frame;
  if (!read_frame(out.pipe, out.decoder, id_frame, timeout_ms)) {
    error = "timed out waiting for IdentifyReply";
    stop(out);
    return false;
  }
  if (id_frame.message_type !=
      static_cast<uint32_t>(capture::v1::MESSAGE_TYPE_IDENTIFY_REPLY)) {
    error = "expected IdentifyReply";
    stop(out);
    return false;
  }
  capture::v1::IdentifyReply id_reply;
  if (!id_reply.ParseFromArray(id_frame.payload.data(),
                               static_cast<int>(id_frame.payload.size()))) {
    error = "failed to parse IdentifyReply";
    stop(out);
    return false;
  }
  if (!id_reply.error().code().empty()) {
    error = "Identify failed: " + id_reply.error().message();
    stop(out);
    return false;
  }

  out.manifest = id_reply.manifest();
  capture::log::info("worker_spawned", "worker Hello+Identify complete",
                     {{"worker_id", worker_id},
                      {"plugin_id", plugin_id},
                      {"pid", std::to_string(out.pid)}});
  return true;
}

void WorkerHost::stop(SpawnedWorker& worker) {
  close_channel(worker.pipe);
  if (worker.pid != 0) {
    (void)terminate_child(static_cast<pid_t>(worker.pid));
    job_.release_process(worker.pid);
  }
  worker.thread = nullptr;
  worker.process = nullptr;
  worker.pid = 0;
}

bool WorkerHost::discover(SpawnedWorker& worker,
                          capture::v1::DiscoverReply& reply, std::string& error,
                          std::chrono::milliseconds timeout) {
  if (worker.pipe == nullptr) {
    error = "worker pipe not connected";
    return false;
  }
  capture::v1::DiscoverRequest req;
  return worker_rpc(worker, capture::v1::MESSAGE_TYPE_DISCOVER,
                    capture::v1::MESSAGE_TYPE_DISCOVER_REPLY, req, reply, 2,
                    static_cast<uint64_t>((std::max)(timeout.count(), 1LL)),
                    error);
}

bool WorkerHost::connect(SpawnedWorker& worker, const std::string& source_id,
                         capture::v1::ConnectReply& reply, std::string& error,
                         std::chrono::milliseconds timeout) {
  if (worker.pipe == nullptr) {
    error = "worker pipe not connected";
    return false;
  }
  capture::v1::ConnectRequest req;
  req.set_source_id(source_id);
  return worker_rpc(worker, capture::v1::MESSAGE_TYPE_CONNECT,
                    capture::v1::MESSAGE_TYPE_CONNECT_REPLY, req, reply, 3,
                    static_cast<uint64_t>((std::max)(timeout.count(), 1LL)),
                    error);
}

bool WorkerHost::start_capture(SpawnedWorker& worker,
                               const capture::v1::StartRequest& req,
                               capture::v1::StartReply& reply,
                               std::string& error,
                               std::chrono::milliseconds timeout) {
  if (worker.pipe == nullptr) {
    error = "worker pipe not connected";
    return false;
  }
  return worker_rpc(worker, capture::v1::MESSAGE_TYPE_START,
                    capture::v1::MESSAGE_TYPE_START_REPLY, req, reply, 4,
                    static_cast<uint64_t>((std::max)(timeout.count(), 1LL)),
                    error);
}

bool WorkerHost::stop_capture(SpawnedWorker& worker,
                              const std::string& source_id,
                              capture::v1::StopReply& reply, std::string& error,
                              std::chrono::milliseconds timeout) {
  if (worker.pipe == nullptr) {
    error = "worker pipe not connected";
    return false;
  }
  capture::v1::StopRequest req;
  req.set_source_id(source_id);
  return worker_rpc(worker, capture::v1::MESSAGE_TYPE_STOP,
                    capture::v1::MESSAGE_TYPE_STOP_REPLY, req, reply, 5,
                    static_cast<uint64_t>((std::max)(timeout.count(), 1LL)),
                    error);
}

bool WorkerHost::get_config_schema(SpawnedWorker& worker,
                                   const std::string& source_id,
                                   capture::v1::GetConfigSchemaReply& reply,
                                   std::string& error,
                                   std::chrono::milliseconds timeout) {
  if (worker.pipe == nullptr) {
    error = "worker pipe not connected";
    return false;
  }
  capture::v1::GetConfigSchemaRequest req;
  req.set_source_id(source_id);
  return worker_rpc(worker, capture::v1::MESSAGE_TYPE_GET_CONFIG_SCHEMA,
                    capture::v1::MESSAGE_TYPE_GET_CONFIG_SCHEMA_REPLY, req,
                    reply, 6,
                    static_cast<uint64_t>((std::max)(timeout.count(), 1LL)),
                    error);
}

bool WorkerHost::apply_config(SpawnedWorker& worker,
                              const capture::v1::ApplyConfigRequest& req,
                              capture::v1::ApplyConfigReply& reply,
                              std::string& error,
                              std::chrono::milliseconds timeout) {
  if (worker.pipe == nullptr) {
    error = "worker pipe not connected";
    return false;
  }
  return worker_rpc(worker, capture::v1::MESSAGE_TYPE_APPLY_CONFIG,
                    capture::v1::MESSAGE_TYPE_APPLY_CONFIG_REPLY, req, reply, 7,
                    static_cast<uint64_t>((std::max)(timeout.count(), 1LL)),
                    error);
}

int WorkerHost::drain_events(
    SpawnedWorker& worker,
    const std::function<void(const capture::v1::SegmentSealed&)>& on_sealed,
    const std::function<void(const capture::v1::PreviewFrame&)>& on_preview,
    const std::function<void(const capture::v1::HealthSnapshot&)>& on_health,
    const std::function<void(const capture::v1::OverloadEvent&)>& on_overload) {
  if (worker.pipe == nullptr) {
    return 0;
  }
  std::unique_lock io_lock(*worker.io_mutex, std::try_to_lock);
  if (!io_lock.owns_lock()) {
    return 0;
  }

  for (;;) {
    capture::Frame frame;
    if (worker.decoder.pop(frame)) {
      stash_unsolicited(worker, frame);
      if (frame.message_type ==
          static_cast<uint32_t>(capture::v1::MESSAGE_TYPE_SEGMENT_SEALED)) {
        (void)ack_segment_sealed(worker.pipe, capture::v1::SegmentSealed{},
                                 frame.correlation_id);
      }
      continue;
    }
    if (!channel_has_data(worker.pipe)) {
      break;
    }
    if (!pump_bytes(worker.pipe, worker.decoder, 50)) {
      break;
    }
  }

  int handled = 0;
  if (on_sealed) {
    for (auto& sealed : worker.pending_sealed) {
      on_sealed(sealed);
      ++handled;
    }
  }
  worker.pending_sealed.clear();
  if (on_preview) {
    for (auto& preview : worker.pending_previews) {
      on_preview(preview);
      ++handled;
    }
  }
  worker.pending_previews.clear();
  if (on_health) {
    for (auto& health : worker.pending_health) {
      on_health(health);
      ++handled;
    }
  }
  worker.pending_health.clear();
  if (on_overload) {
    for (auto& overload : worker.pending_overloads) {
      on_overload(overload);
      ++handled;
    }
  }
  worker.pending_overloads.clear();
  return handled;
}

}  // namespace capture::daemon
