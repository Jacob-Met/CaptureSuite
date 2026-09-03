// SPDX-License-Identifier: GPL-3.0-only
#pragma once

#ifndef NOMINMAX
#define NOMINMAX
#endif
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <Windows.h>

#include <string>

namespace capture::daemon {

// Windows Job Object with JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE. Created once per
// daemon instance; workers join it before they run (WORKER_HOST.md).
class DaemonJob {
 public:
  DaemonJob() = default;
  ~DaemonJob();

  DaemonJob(const DaemonJob&) = delete;
  DaemonJob& operator=(const DaemonJob&) = delete;

  bool create(std::string& error);
  void* handle() const { return handle_; }
  bool assign_process(void* process_handle, std::string& error) const;

 private:
  void* handle_ = nullptr;
};

// True when the named-pipe peer's user SID matches this process.
bool peer_sid_matches_self(void* pipe_handle, std::string& error);

// Owner + SYSTEM GENERIC_ALL DACL for named pipes / shm (PROTOCOL.md).
// On success, *sd must be LocalFree'd by the caller.
SECURITY_ATTRIBUTES* make_pipe_sa(SECURITY_ATTRIBUTES& sa,
                                  PSECURITY_DESCRIPTOR& sd);

}  // namespace capture::daemon
