// SPDX-License-Identifier: GPL-3.0-only
#pragma once

#include <cstdint>
#include <mutex>
#include <string>
#include <vector>

#ifdef _WIN32
#ifndef NOMINMAX
#define NOMINMAX
#endif
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <Windows.h>
#endif

namespace capture::daemon {

// Worker lifetime owner. Windows uses a kill-on-close Job Object. POSIX keeps
// an explicit child registry for orderly daemon teardown; worker channels also
// close on daemon exit so children can observe EOF after abrupt parent loss.
class DaemonJob {
 public:
  DaemonJob() = default;
  ~DaemonJob();

  DaemonJob(const DaemonJob&) = delete;
  DaemonJob& operator=(const DaemonJob&) = delete;

  bool create(std::string& error);
  void* handle() const { return handle_; }
  bool assign_process(void* process_handle, std::string& error);
  void release_process(std::uint32_t pid);

 private:
  void* handle_ = nullptr;
#ifndef _WIN32
  bool created_ = false;
  mutable std::mutex mu_;
  std::vector<std::uint32_t> pids_;
#endif
};

// True when the connected local peer belongs to the same user identity.
// Windows checks the named-pipe client SID; macOS/POSIX checks socket peer UID.
bool peer_sid_matches_self(void* pipe_handle, std::string& error);

#ifdef _WIN32
// Owner + SYSTEM GENERIC_ALL DACL for named pipes / shm (PROTOCOL.md).
// On success, *sd must be LocalFree'd by the caller.
SECURITY_ATTRIBUTES* make_pipe_sa(SECURITY_ATTRIBUTES& sa,
                                  PSECURITY_DESCRIPTOR& sd);
#endif

}  // namespace capture::daemon
