// SPDX-License-Identifier: GPL-3.0-only
#pragma once

#include <atomic>
#include <cstddef>
#include <cstdint>
#include <filesystem>
#include <span>
#include <string>

namespace capture::daemon {

using ControlHandle = std::intptr_t;
inline constexpr ControlHandle kInvalidControlHandle = static_cast<ControlHandle>(-1);

// OS-native endpoint for the daemon control plane. Windows keeps the existing
// named-pipe path; POSIX/macOS uses a same-user Unix-domain socket.
std::string control_endpoint_name(const std::string& instance_id);

// Per-user location for instance.json. This is deliberately separate from the
// socket path so discovery survives the short AF_UNIX path-length limit.
std::filesystem::path control_instance_path(std::string& error);

class ControlListener {
 public:
  explicit ControlListener(std::string endpoint);
  ~ControlListener();

  ControlListener(const ControlListener&) = delete;
  ControlListener& operator=(const ControlListener&) = delete;

  bool open(std::string& error);
  ControlHandle accept(std::atomic<bool>& running, std::string& error);
  void close();

 private:
  std::string endpoint_;
  ControlHandle listener_ = kInvalidControlHandle;
};

// Full-duplex byte-stream primitives. CSP1 framing remains above this layer.
bool control_write_all(ControlHandle handle, std::span<const uint8_t> data,
                       std::string& error);
bool control_read_some(ControlHandle handle, std::span<uint8_t> buffer,
                       std::atomic<bool>& running, std::size_t& bytes_read,
                       std::string& error);

// Lifecycle helpers used by ControlServer shutdown/reaping.
void control_cancel(ControlHandle handle);
void control_disconnect(ControlHandle handle);
void control_close(ControlHandle handle);
bool wake_control_endpoint(const std::string& endpoint);

}  // namespace capture::daemon
