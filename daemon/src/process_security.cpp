// SPDX-License-Identifier: GPL-3.0-only
#include "capture_daemon/process_security.hpp"

#include "capture/logging.hpp"

#ifndef NOMINMAX
#define NOMINMAX
#endif
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <Windows.h>
#include <sddl.h>

#include <vector>

namespace capture::daemon {
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

DaemonJob::~DaemonJob() {
  if (handle_ != nullptr) {
    CloseHandle(static_cast<HANDLE>(handle_));
    handle_ = nullptr;
  }
}

bool DaemonJob::create(std::string& error) {
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
  return true;
}

bool DaemonJob::assign_process(void* process_handle, std::string& error) const {
  if (handle_ == nullptr) {
    error = "job object not created";
    return false;
  }
  if (!AssignProcessToJobObject(static_cast<HANDLE>(handle_),
                                static_cast<HANDLE>(process_handle))) {
    error = "AssignProcessToJobObject failed";
    return false;
  }
  return true;
}

bool peer_sid_matches_self(void* pipe_handle, std::string& error) {
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
}

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

}  // namespace capture::daemon
