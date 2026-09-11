// SPDX-License-Identifier: GPL-3.0-only
#include "capture_daemon/process_security.hpp"

#include "capture/logging.hpp"

#include <algorithm>
#include <chrono>
#include <cstdint>
#include <thread>

#ifdef _WIN32
#ifndef NOMINMAX
#define NOMINMAX
#endif
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <Windows.h>
#include <sddl.h>

#include <vector>
#else
#include <cerrno>
#include <csignal>
#include <sys/socket.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>
#endif

namespace capture::daemon {
#ifdef _WIN32
namespace {

bool token_user_sid(HANDLE token, std::vector<BYTE>& sid_bytes, std::string& error) {
  DWORD needed = 0;
  GetTokenInformation(token, TokenUser, nullptr, 0, &needed);
  if (needed == 0) {
    error = "GetTokenInformation size failed";
    return false;
  }
  sid_bytes.resize(needed);
  if (!GetTokenInformation(token, TokenUser, sid_bytes.data(), needed, &needed)) {
    error = "GetTokenInformation TokenUser failed";
    return false;
  }
  return true;
}

bool current_process_sid(std::vector<BYTE>& sid_bytes, std::string& error) {
  HANDLE token = nullptr;
  if (!OpenProcessToken(GetCurrentProcess(), TOKEN_QUERY, &token)) {
    error = "OpenProcessToken self failed";
    return false;
  }
  const bool ok = token_user_sid(token, sid_bytes, error);
  CloseHandle(token);
  return ok;
}

}  // namespace
#endif

DaemonJob::~DaemonJob() {
#ifdef _WIN32
  if (handle_ != nullptr) {
    CloseHandle(static_cast<HANDLE>(handle_));
    handle_ = nullptr;
  }
#else
  std::vector<std::uint32_t> pids;
  {
    std::lock_guard lock(mu_);
    pids = pids_;
    pids_.clear();
    created_ = false;
  }
  for (const auto raw_pid : pids) {
    const pid_t pid = static_cast<pid_t>(raw_pid);
    int status = 0;
    const pid_t observed = waitpid(pid, &status, WNOHANG);
    if (observed == pid || (observed < 0 && errno == ECHILD)) {
      continue;
    }
    if (observed == 0) {
      (void)kill(pid, SIGTERM);
      bool reaped = false;
      for (int i = 0; i < 20; ++i) {
        const pid_t waited = waitpid(pid, &status, WNOHANG);
        if (waited == pid || (waited < 0 && errno == ECHILD)) {
          reaped = true;
          break;
        }
        std::this_thread::sleep_for(std::chrono::milliseconds(10));
      }
      if (!reaped) {
        (void)kill(pid, SIGKILL);
        (void)waitpid(pid, &status, 0);
      }
    }
  }
#endif
}

bool DaemonJob::create(std::string& error) {
#ifdef _WIN32
  if (handle_ != nullptr) {
    return true;
  }
  HANDLE job = CreateJobObjectW(nullptr, nullptr);
  if (job == nullptr) {
    error = "CreateJobObject failed";
    return false;
  }
  JOBOBJECT_EXTENDED_LIMIT_INFORMATION info{};
  info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
  if (!SetInformationJobObject(job, JobObjectExtendedLimitInformation, &info,
                               sizeof(info))) {
    CloseHandle(job);
    error = "SetInformationJobObject KILL_ON_JOB_CLOSE failed";
    return false;
  }
  handle_ = job;
  capture::log::info("job_object_created",
                     "worker job object ready (kill-on-close)");
#else
  {
    std::lock_guard lock(mu_);
    created_ = true;
  }
  capture::log::info("worker_registry_created",
                     "POSIX worker child registry ready");
  (void)error;
#endif
  return true;
}

bool DaemonJob::assign_process(void* process_handle, std::string& error) {
#ifdef _WIN32
  if (handle_ == nullptr) {
    error = "job object not created";
    return false;
  }
  if (!AssignProcessToJobObject(static_cast<HANDLE>(handle_),
                                static_cast<HANDLE>(process_handle))) {
    error = "AssignProcessToJobObject failed";
    return false;
  }
#else
  const auto raw = reinterpret_cast<std::intptr_t>(process_handle);
  if (raw <= 0) {
    error = "invalid POSIX child pid";
    return false;
  }
  const auto pid = static_cast<std::uint32_t>(raw);
  std::lock_guard lock(mu_);
  if (!created_) {
    error = "worker child registry not created";
    return false;
  }
  if (std::find(pids_.begin(), pids_.end(), pid) == pids_.end()) {
    pids_.push_back(pid);
  }
#endif
  return true;
}

void DaemonJob::release_process(std::uint32_t pid) {
#ifdef _WIN32
  (void)pid;
#else
  std::lock_guard lock(mu_);
  pids_.erase(std::remove(pids_.begin(), pids_.end(), pid), pids_.end());
#endif
}

bool peer_sid_matches_self(void* pipe_handle, std::string& error) {
#ifdef _WIN32
  HANDLE pipe = static_cast<HANDLE>(pipe_handle);
  ULONG pid = 0;
  if (!GetNamedPipeClientProcessId(pipe, &pid) || pid == 0) {
    error = "GetNamedPipeClientProcessId failed";
    return false;
  }
  HANDLE process =
      OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, FALSE, pid);
  if (process == nullptr) {
    error = "OpenProcess peer failed";
    return false;
  }
  HANDLE token = nullptr;
  if (!OpenProcessToken(process, TOKEN_QUERY, &token)) {
    CloseHandle(process);
    error = "OpenProcessToken peer failed";
    return false;
  }

  std::vector<BYTE> peer_sid;
  std::vector<BYTE> self_sid;
  bool ok = token_user_sid(token, peer_sid, error) &&
            current_process_sid(self_sid, error);
  CloseHandle(token);
  CloseHandle(process);
  if (!ok) {
    return false;
  }

  auto* peer_user = reinterpret_cast<TOKEN_USER*>(peer_sid.data());
  auto* self_user = reinterpret_cast<TOKEN_USER*>(self_sid.data());
  if (EqualSid(peer_user->User.Sid, self_user->User.Sid) != TRUE) {
    error = "peer SID mismatch";
    return false;
  }
  return true;
#else
  const auto raw = reinterpret_cast<std::intptr_t>(pipe_handle);
  if (raw < 0) {
    error = "invalid POSIX peer socket";
    return false;
  }
  const int fd = static_cast<int>(raw);
  uid_t peer_uid = static_cast<uid_t>(-1);
#if defined(__APPLE__)
  gid_t peer_gid = 0;
  if (getpeereid(fd, &peer_uid, &peer_gid) != 0) {
    error = "getpeereid failed";
    return false;
  }
#else
  struct PeerCred {
    pid_t pid;
    uid_t uid;
    gid_t gid;
  } cred{};
  socklen_t size = sizeof(cred);
  if (getsockopt(fd, SOL_SOCKET, SO_PEERCRED, &cred, &size) != 0 ||
      size != sizeof(cred)) {
    error = "SO_PEERCRED failed";
    return false;
  }
  peer_uid = cred.uid;
#endif
  if (peer_uid != geteuid()) {
    error = "peer UID mismatch";
    return false;
  }
  return true;
#endif
}

#ifdef _WIN32
SECURITY_ATTRIBUTES* make_pipe_sa(SECURITY_ATTRIBUTES& sa,
                                  PSECURITY_DESCRIPTOR& sd) {
  const wchar_t* sddl = L"D:(A;;GA;;;SY)(A;;GA;;;OW)";
  sd = nullptr;
  if (!ConvertStringSecurityDescriptorToSecurityDescriptorW(
          sddl, SDDL_REVISION_1, &sd, nullptr)) {
    return nullptr;
  }
  sa.nLength = sizeof(sa);
  sa.lpSecurityDescriptor = sd;
  sa.bInheritHandle = FALSE;
  return &sa;
}
#endif

}  // namespace capture::daemon
