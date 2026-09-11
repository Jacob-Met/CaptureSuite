// SPDX-License-Identifier: GPL-3.0-only
#include "capture_daemon/control_transport.hpp"

#ifdef _WIN32
#include "capture_daemon/process_security.hpp"

#ifndef NOMINMAX
#define NOMINMAX
#endif
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <Windows.h>
#include <sddl.h>
#else
#include <cerrno>
#include <cstring>
#include <poll.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/un.h>
#include <unistd.h>
#endif

#include <cstdlib>
#include <filesystem>

namespace capture::daemon {
namespace {

constexpr std::size_t kPipeBuffer = 256 * 1024;

#ifdef _WIN32

HANDLE native_handle(ControlHandle handle) {
  return reinterpret_cast<HANDLE>(handle);
}

ControlHandle stored_handle(HANDLE handle) {
  return reinterpret_cast<ControlHandle>(handle);
}

#else

int native_handle(ControlHandle handle) {
  return static_cast<int>(handle);
}

ControlHandle stored_handle(int handle) {
  return static_cast<ControlHandle>(handle);
}

void set_socket_no_sigpipe(int fd) {
#ifdef SO_NOSIGPIPE
  int enabled = 1;
  (void)setsockopt(fd, SOL_SOCKET, SO_NOSIGPIPE, &enabled, sizeof(enabled));
#else
  (void)fd;
#endif
}

bool peer_uid_matches_self(int fd, std::string& error) {
#if defined(__APPLE__)
  uid_t peer_uid = 0;
  gid_t peer_gid = 0;
  if (getpeereid(fd, &peer_uid, &peer_gid) != 0) {
    error = std::string("getpeereid failed: ") + std::strerror(errno);
    return false;
  }
  if (peer_uid != geteuid()) {
    error = "peer uid mismatch";
    return false;
  }
  return true;
#elif defined(SO_PEERCRED)
  struct PeerCred {
    pid_t pid;
    uid_t uid;
    gid_t gid;
  } cred{};
  socklen_t len = sizeof(cred);
  if (getsockopt(fd, SOL_SOCKET, SO_PEERCRED, &cred, &len) != 0 ||
      len != sizeof(cred)) {
    error = std::string("SO_PEERCRED failed: ") + std::strerror(errno);
    return false;
  }
  if (cred.uid != geteuid()) {
    error = "peer uid mismatch";
    return false;
  }
  return true;
#else
  (void)fd;
  error = "same-user peer credential check is unavailable on this POSIX platform";
  return false;
#endif
}

bool ensure_socket_parent(const std::filesystem::path& endpoint,
                          std::string& error) {
  const auto parent = endpoint.parent_path();
  std::error_code ec;
  std::filesystem::create_directories(parent, ec);
  if (ec) {
    error = "failed to create control socket directory: " + ec.message();
    return false;
  }
  struct stat st {};
  if (::stat(parent.c_str(), &st) != 0) {
    error = std::string("failed to stat control socket directory: ") +
            std::strerror(errno);
    return false;
  }
  if (st.st_uid != geteuid()) {
    error = "control socket directory is not owned by the current user";
    return false;
  }
  if (::chmod(parent.c_str(), S_IRWXU) != 0) {
    error = std::string("failed to secure control socket directory: ") +
            std::strerror(errno);
    return false;
  }
  return true;
}

bool remove_stale_socket(const std::filesystem::path& endpoint,
                         std::string& error) {
  struct stat st {};
  if (::lstat(endpoint.c_str(), &st) != 0) {
    if (errno == ENOENT) {
      return true;
    }
    error = std::string("failed to inspect existing control endpoint: ") +
            std::strerror(errno);
    return false;
  }
  if (!S_ISSOCK(st.st_mode) || st.st_uid != geteuid()) {
    error = "refusing to replace non-socket or foreign-owned control endpoint";
    return false;
  }
  if (::unlink(endpoint.c_str()) != 0) {
    error = std::string("failed to remove stale control socket: ") +
            std::strerror(errno);
    return false;
  }
  return true;
}

#endif

}  // namespace

std::string control_endpoint_name(const std::string& instance_id) {
#ifdef _WIN32
  return "\\\\.\\pipe\\capturesuite." + instance_id + ".control";
#else
  const auto root = std::filesystem::path("/tmp") /
                    ("capturesuite-" +
                     std::to_string(static_cast<unsigned long>(geteuid())));
  return (root / ("capturesuite." + instance_id + ".control.sock")).string();
#endif
}

std::filesystem::path control_instance_path(std::string& error) {
#ifdef _WIN32
  char* local = nullptr;
  size_t len = 0;
  if (_dupenv_s(&local, &len, "LOCALAPPDATA") != 0 || local == nullptr) {
    error = "LOCALAPPDATA not set";
    return {};
  }
  std::filesystem::path dir = std::filesystem::path(local) / "CaptureSuite";
  free(local);
  return dir / "instance.json";
#elif defined(__APPLE__)
  const char* home = std::getenv("HOME");
  if (home == nullptr || *home == '\0') {
    error = "HOME not set";
    return {};
  }
  return std::filesystem::path(home) / "Library" / "Application Support" /
         "CaptureSuite" / "instance.json";
#else
  const char* state = std::getenv("XDG_STATE_HOME");
  if (state != nullptr && *state != '\0') {
    return std::filesystem::path(state) / "CaptureSuite" / "instance.json";
  }
  const char* home = std::getenv("HOME");
  if (home == nullptr || *home == '\0') {
    error = "HOME not set";
    return {};
  }
  return std::filesystem::path(home) / ".local" / "state" / "CaptureSuite" /
         "instance.json";
#endif
}

ControlListener::ControlListener(std::string endpoint)
    : endpoint_(std::move(endpoint)) {}

ControlListener::~ControlListener() {
  close();
}

bool ControlListener::open(std::string& error) {
#ifdef _WIN32
  (void)error;
  return true;
#else
  if (listener_ != kInvalidControlHandle) {
    return true;
  }
  const std::filesystem::path endpoint(endpoint_);
  if (!ensure_socket_parent(endpoint, error) ||
      !remove_stale_socket(endpoint, error)) {
    return false;
  }

  sockaddr_un addr{};
  if (endpoint_.size() >= sizeof(addr.sun_path)) {
    error = "control socket path exceeds AF_UNIX sun_path limit";
    return false;
  }
  addr.sun_family = AF_UNIX;
  std::memcpy(addr.sun_path, endpoint_.c_str(), endpoint_.size() + 1);

  const int fd = ::socket(AF_UNIX, SOCK_STREAM, 0);
  if (fd < 0) {
    error = std::string("socket(AF_UNIX) failed: ") + std::strerror(errno);
    return false;
  }
  set_socket_no_sigpipe(fd);

  if (::bind(fd, reinterpret_cast<sockaddr*>(&addr), sizeof(addr)) != 0) {
    error = std::string("bind control socket failed: ") + std::strerror(errno);
    ::close(fd);
    return false;
  }
  if (::chmod(endpoint_.c_str(), S_IRUSR | S_IWUSR) != 0) {
    error = std::string("chmod control socket failed: ") + std::strerror(errno);
    ::close(fd);
    ::unlink(endpoint_.c_str());
    return false;
  }
  if (::listen(fd, 16) != 0) {
    error = std::string("listen control socket failed: ") + std::strerror(errno);
    ::close(fd);
    ::unlink(endpoint_.c_str());
    return false;
  }
  listener_ = stored_handle(fd);
  return true;
#endif
}

ControlHandle ControlListener::accept(std::atomic<bool>& running,
                                      std::string& error) {
#ifdef _WIN32
  SECURITY_ATTRIBUTES sa{};
  PSECURITY_DESCRIPTOR sd = nullptr;
  PSECURITY_ATTRIBUTES psa = make_pipe_sa(sa, sd);

  HANDLE pipe = CreateNamedPipeA(
      endpoint_.c_str(), PIPE_ACCESS_DUPLEX | FILE_FLAG_OVERLAPPED,
      PIPE_TYPE_BYTE | PIPE_READMODE_BYTE | PIPE_WAIT, PIPE_UNLIMITED_INSTANCES,
      static_cast<DWORD>(kPipeBuffer), static_cast<DWORD>(kPipeBuffer), 0, psa);
  if (sd != nullptr) {
    LocalFree(sd);
  }
  if (pipe == INVALID_HANDLE_VALUE) {
    error = "CreateNamedPipe failed";
    return kInvalidControlHandle;
  }

  OVERLAPPED ov{};
  ov.hEvent = CreateEventW(nullptr, TRUE, FALSE, nullptr);
  if (ov.hEvent == nullptr) {
    CloseHandle(pipe);
    error = "CreateEvent failed while accepting control client";
    return kInvalidControlHandle;
  }

  bool connected = false;
  if (ConnectNamedPipe(pipe, &ov)) {
    connected = true;
  } else if (GetLastError() == ERROR_PIPE_CONNECTED) {
    connected = true;
  } else if (GetLastError() == ERROR_IO_PENDING) {
    while (running.load()) {
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

  if (!connected) {
    CloseHandle(pipe);
    if (running.load()) {
      error = "control pipe connection failed";
    }
    return kInvalidControlHandle;
  }

  std::string sid_error;
  if (!peer_sid_matches_self(pipe, sid_error)) {
    DisconnectNamedPipe(pipe);
    CloseHandle(pipe);
    error = "control peer rejected: " + sid_error;
    return kInvalidControlHandle;
  }
  return stored_handle(pipe);
#else
  if (listener_ == kInvalidControlHandle && !open(error)) {
    return kInvalidControlHandle;
  }
  const int fd = ::accept(native_handle(listener_), nullptr, nullptr);
  if (fd < 0) {
    if (!running.load()) {
      return kInvalidControlHandle;
    }
    error = std::string("accept control socket failed: ") + std::strerror(errno);
    return kInvalidControlHandle;
  }
  set_socket_no_sigpipe(fd);

  std::string peer_error;
  if (!peer_uid_matches_self(fd, peer_error)) {
    ::close(fd);
    error = "control peer rejected: " + peer_error;
    return kInvalidControlHandle;
  }
  return stored_handle(fd);
#endif
}

void ControlListener::close() {
#ifdef _WIN32
  listener_ = kInvalidControlHandle;
#else
  if (listener_ != kInvalidControlHandle) {
    ::close(native_handle(listener_));
    listener_ = kInvalidControlHandle;
  }
  if (!endpoint_.empty()) {
    ::unlink(endpoint_.c_str());
  }
#endif
}

bool control_write_all(ControlHandle handle, std::span<const uint8_t> data,
                       std::string& error) {
#ifdef _WIN32
  HANDLE pipe = native_handle(handle);
  OVERLAPPED ov{};
  ov.hEvent = CreateEventW(nullptr, TRUE, FALSE, nullptr);
  if (ov.hEvent == nullptr) {
    error = "CreateEvent failed while writing control frame";
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
        error = "WriteFile failed on control transport";
        ok_all = false;
        break;
      }
    }
    if (written == 0) {
      error = "zero-byte write on control transport";
      ok_all = false;
      break;
    }
    offset += written;
  }
  CloseHandle(ov.hEvent);
  return ok_all;
#else
  const int fd = native_handle(handle);
  std::size_t offset = 0;
  while (offset < data.size()) {
#ifdef MSG_NOSIGNAL
    const ssize_t written =
        ::send(fd, data.data() + offset, data.size() - offset, MSG_NOSIGNAL);
#else
    const ssize_t written =
        ::send(fd, data.data() + offset, data.size() - offset, 0);
#endif
    if (written < 0) {
      if (errno == EINTR) {
        continue;
      }
      error = std::string("send failed on control socket: ") +
              std::strerror(errno);
      return false;
    }
    if (written == 0) {
      error = "zero-byte write on control socket";
      return false;
    }
    offset += static_cast<std::size_t>(written);
  }
  return true;
#endif
}

bool control_read_some(ControlHandle handle, std::span<uint8_t> buffer,
                       std::atomic<bool>& running, std::size_t& bytes_read,
                       std::string& error) {
  bytes_read = 0;
#ifdef _WIN32
  HANDLE pipe = native_handle(handle);
  OVERLAPPED ov{};
  ov.hEvent = CreateEventW(nullptr, TRUE, FALSE, nullptr);
  if (ov.hEvent == nullptr) {
    error = "CreateEvent failed while reading control frame";
    return false;
  }

  DWORD read = 0;
  bool ok = true;
  if (!ReadFile(pipe, buffer.data(), static_cast<DWORD>(buffer.size()), &read,
                &ov)) {
    if (GetLastError() != ERROR_IO_PENDING) {
      ok = false;
    } else {
      bool ready = false;
      while (running.load()) {
        if (WaitForSingleObject(ov.hEvent, 100) == WAIT_OBJECT_0) {
          ready = true;
          break;
        }
      }
      if (!ready) {
        CancelIoEx(pipe, &ov);
        GetOverlappedResult(pipe, &ov, &read, TRUE);
        ok = false;
      } else if (!GetOverlappedResult(pipe, &ov, &read, FALSE)) {
        ok = false;
      }
    }
  }
  CloseHandle(ov.hEvent);
  if (!ok) {
    if (running.load()) {
      error = "ReadFile failed on control transport";
    }
    return false;
  }
  bytes_read = static_cast<std::size_t>(read);
  return read != 0;
#else
  const int fd = native_handle(handle);
  while (running.load()) {
    pollfd pfd{};
    pfd.fd = fd;
    pfd.events = POLLIN;
    const int rc = ::poll(&pfd, 1, 100);
    if (rc < 0) {
      if (errno == EINTR) {
        continue;
      }
      error = std::string("poll failed on control socket: ") +
              std::strerror(errno);
      return false;
    }
    if (rc == 0) {
      continue;
    }
    if ((pfd.revents & (POLLERR | POLLHUP | POLLNVAL)) != 0 &&
        (pfd.revents & POLLIN) == 0) {
      return false;
    }
    if ((pfd.revents & POLLIN) != 0) {
      const ssize_t n = ::recv(fd, buffer.data(), buffer.size(), 0);
      if (n < 0) {
        if (errno == EINTR) {
          continue;
        }
        error = std::string("recv failed on control socket: ") +
                std::strerror(errno);
        return false;
      }
      if (n == 0) {
        return false;
      }
      bytes_read = static_cast<std::size_t>(n);
      return true;
    }
  }
  return false;
#endif
}

void control_cancel(ControlHandle handle) {
  if (handle == kInvalidControlHandle) {
    return;
  }
#ifdef _WIN32
  CancelIoEx(native_handle(handle), nullptr);
#else
  ::shutdown(native_handle(handle), SHUT_RDWR);
#endif
}

void control_disconnect(ControlHandle handle) {
  if (handle == kInvalidControlHandle) {
    return;
  }
#ifdef _WIN32
  HANDLE pipe = native_handle(handle);
  FlushFileBuffers(pipe);
  DisconnectNamedPipe(pipe);
#else
  ::shutdown(native_handle(handle), SHUT_RDWR);
#endif
}

void control_close(ControlHandle handle) {
  if (handle == kInvalidControlHandle) {
    return;
  }
#ifdef _WIN32
  CloseHandle(native_handle(handle));
#else
  ::close(native_handle(handle));
#endif
}

bool wake_control_endpoint(const std::string& endpoint) {
#ifdef _WIN32
  HANDLE wake = CreateFileA(endpoint.c_str(), GENERIC_READ | GENERIC_WRITE, 0,
                            nullptr, OPEN_EXISTING, 0, nullptr);
  if (wake == INVALID_HANDLE_VALUE) {
    return false;
  }
  CloseHandle(wake);
  return true;
#else
  const int fd = ::socket(AF_UNIX, SOCK_STREAM, 0);
  if (fd < 0) {
    return false;
  }
  set_socket_no_sigpipe(fd);
  sockaddr_un addr{};
  if (endpoint.size() >= sizeof(addr.sun_path)) {
    ::close(fd);
    return false;
  }
  addr.sun_family = AF_UNIX;
  std::memcpy(addr.sun_path, endpoint.c_str(), endpoint.size() + 1);
  const bool ok =
      ::connect(fd, reinterpret_cast<sockaddr*>(&addr), sizeof(addr)) == 0;
  ::close(fd);
  return ok;
#endif
}

}  // namespace capture::daemon
