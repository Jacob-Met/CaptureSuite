// SPDX-License-Identifier: GPL-3.0-only
#include "capture_daemon/worker_host.hpp"

#include "capture/env.hpp"

#include "capture/framing.hpp"
#include "capture/logging.hpp"
#include "capture_daemon/handshake.hpp"

#include "capture/v1/common.pb.h"
#include "capture/v1/health.pb.h"
#include "capture/v1/preview.pb.h"

#ifndef NOMINMAX
#define NOMINMAX
#endif
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <Windows.h>

#include <algorithm>
#include <cstring>
#include <string>
#include <vector>

namespace capture::daemon {
namespace {

constexpr DWORD kPipeBuffer = 256 * 1024;

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

bool pump_bytes(HANDLE pipe, capture::FrameDecoder& decoder, DWORD timeout_ms) {
  const auto deadline = GetTickCount64() + timeout_ms;
  std::vector<uint8_t> chunk(64 * 1024);
  while (GetTickCount64() < deadline) {
    DWORD available = 0;
    if (!PeekNamedPipe(pipe, nullptr, 0, nullptr, &available, nullptr)) {
      return false;
    }
    if (available == 0) {
      Sleep(5);
      continue;
    }
    DWORD got = 0;
    const DWORD to_read =
        static_cast<DWORD>((std::min)(chunk.size(), static_cast<size_t>(available)));
    if (!ReadFile(pipe, chunk.data(), to_read, &got, nullptr) || got == 0) {
      return false;
    }
    decoder.feed(std::span<const uint8_t>(chunk.data(), got));
    return true;
  }
  return false;
}

bool read_frame(HANDLE pipe, capture::FrameDecoder& decoder, capture::Frame& frame,
                DWORD timeout_ms) {
  if (decoder.pop(frame)) {
    return true;
  }
  const auto deadline = GetTickCount64() + timeout_ms;
  while (GetTickCount64() < deadline) {
    const DWORD remain =
        static_cast<DWORD>((std::max)(1ULL, deadline - GetTickCount64()));
    if (!pump_bytes(pipe, decoder, remain)) {
      // Timeout with no new bytes — still try pop in case feed completed a frame.
      return decoder.pop(frame);
    }
    if (decoder.pop(frame)) {
      return true;
    }
  }
  return decoder.pop(frame);
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

bool ack_segment_sealed(HANDLE pipe, const capture::v1::SegmentSealed& /*sealed*/,
                        uint32_t correlation_id) {
  capture::v1::SegmentSealedAck ack;
  std::string bytes;
  ack.SerializeToString(&bytes);
  auto out = capture::encode_frame(
      static_cast<uint32_t>(capture::v1::MESSAGE_TYPE_SEGMENT_SEALED_ACK),
      std::span<const uint8_t>(reinterpret_cast<const uint8_t*>(bytes.data()),
                               bytes.size()),
      correlation_id);
  return write_all(pipe, out);
}

bool await_connect(HANDLE pipe, DWORD timeout_ms) {
  OVERLAPPED ov{};
  ov.hEvent = CreateEventW(nullptr, TRUE, FALSE, nullptr);
  if (ov.hEvent == nullptr) {
    return false;
  }
  bool ok = false;
  if (ConnectNamedPipe(pipe, &ov)) {
    ok = true;
  } else {
    const DWORD err = GetLastError();
    if (err == ERROR_PIPE_CONNECTED) {
      ok = true;
    } else if (err == ERROR_IO_PENDING) {
      const DWORD wait = WaitForSingleObject(ov.hEvent, timeout_ms);
      if (wait == WAIT_OBJECT_0) {
        DWORD ignored = 0;
        ok = GetOverlappedResult(pipe, &ov, &ignored, FALSE) != FALSE;
      } else {
        CancelIoEx(pipe, &ov);
        DWORD ignored = 0;
        GetOverlappedResult(pipe, &ov, &ignored, TRUE);
      }
    }
  }
  CloseHandle(ov.hEvent);
  return ok;
}

void close_handle(void*& h) {
  if (h != nullptr && h != INVALID_HANDLE_VALUE) {
    CloseHandle(static_cast<HANDLE>(h));
  }
  h = nullptr;
}

}  // namespace

std::string worker_pipe_name(const std::string& instance_id,
                             const std::string& worker_id) {
  return "\\\\.\\pipe\\capturesuite." + instance_id + ".worker." + worker_id;
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

  SECURITY_ATTRIBUTES sa{};
  PSECURITY_DESCRIPTOR sd = nullptr;
  SECURITY_ATTRIBUTES* psa = make_pipe_sa(sa, sd);
  HANDLE pipe = CreateNamedPipeA(
      out.pipe_name.c_str(), PIPE_ACCESS_DUPLEX | FILE_FLAG_OVERLAPPED,
      PIPE_TYPE_BYTE | PIPE_READMODE_BYTE | PIPE_WAIT, 1, kPipeBuffer,
      kPipeBuffer, 0, psa);
  if (sd) {
    LocalFree(sd);
  }
  if (pipe == INVALID_HANDLE_VALUE) {
    error = "CreateNamedPipe failed for worker pipe";
    return false;
  }

  const std::wstring exe_w = executable.wstring();
  std::wstring cmd = L"\"" + exe_w + L"\" --pipe " +
                     std::wstring(out.pipe_name.begin(), out.pipe_name.end()) +
                     L" --worker-id " +
                     std::wstring(worker_id.begin(), worker_id.end()) +
                     L" --plugin " +
                     std::wstring(plugin_id.begin(), plugin_id.end());

  STARTUPINFOW si{};
  si.cb = sizeof(si);
  PROCESS_INFORMATION pi{};
  std::vector<wchar_t> cmd_buf(cmd.begin(), cmd.end());
  cmd_buf.push_back(L'\0');

  // Build an environment block that prepends GStreamer bin and Infineon SDK
  // runtime to PATH so workers find DLLs even when the daemon was not launched
  // from a dev shell.
  std::wstring env_block;
  {
    std::wstring path_prefix;
    auto append_path = [&path_prefix](const std::filesystem::path& dir) {
      if (dir.empty() || !std::filesystem::exists(dir)) {
        return;
      }
      path_prefix.append(dir.wstring());
      path_prefix.append(L";");
    };
    char* gst = nullptr;
    size_t glen = 0;
    if (_dupenv_s(&gst, &glen, "GSTREAMER_1_0_ROOT_MSVC_X86_64") == 0 &&
        gst != nullptr) {
      append_path(std::filesystem::path(gst) / "bin");
      free(gst);
    } else {
      // Same relative layout CameraWorkerBridge::resolve_gstreamer_root uses.
      wchar_t mod[MAX_PATH];
      if (GetModuleFileNameW(nullptr, mod, MAX_PATH) > 0) {
        const auto dir = std::filesystem::path(mod).parent_path();
        const std::filesystem::path candidates[] = {
            dir / ".." / ".." / ".." / "third_party" / "gstreamer" /
                "gstreamer" / "1.0" / "msvc_x86_64",
            dir / ".." / ".." / "third_party" / "gstreamer" / "gstreamer" /
                "1.0" / "msvc_x86_64",
        };
        for (const auto& c : candidates) {
          std::error_code ec;
          const auto canon = std::filesystem::weakly_canonical(c, ec);
          if (!ec && std::filesystem::exists(canon / "bin")) {
            append_path(canon / "bin");
            break;
          }
        }
      }
    }
    auto resolve_ifx_runtime = []() -> std::filesystem::path {
      for (const char* var :
           {"IFX_RADAR_SDK_ROOT", "CAPTURE_IFX_RADAR_SDK_ROOT"}) {
        char* root = nullptr;
        size_t len = 0;
        if (_dupenv_s(&root, &len, var) == 0 && root != nullptr) {
          const auto runtime =
              std::filesystem::path(root) / "libs" / "win32_x64";
          free(root);
          if (std::filesystem::exists(runtime)) {
            return runtime;
          }
        }
      }
      if (const auto profile = capture::env::get("USERPROFILE")) {
        const auto runtime =
            std::filesystem::path(*profile) / "Infineon" / "Tools" /
            "radar_sdk_3.6.5" / "radar_sdk" / "libs" / "win32_x64";
        if (std::filesystem::exists(runtime)) {
          return runtime;
        }
      }
      return {};
    };
    append_path(resolve_ifx_runtime());
    LPWCH strings = GetEnvironmentStringsW();
    if (strings) {
      for (LPWCH p = strings; *p != L'\0';) {
        std::wstring entry = p;
        p += entry.size() + 1;
        if (entry.rfind(L"PATH=", 0) == 0 || entry.rfind(L"Path=", 0) == 0) {
          const auto eq = entry.find(L'=');
          env_block.append(entry.substr(0, eq + 1));
          env_block.append(path_prefix);
          env_block.append(entry.substr(eq + 1));
        } else {
          env_block.append(entry);
        }
        env_block.push_back(L'\0');
      }
      FreeEnvironmentStringsW(strings);
      if (!path_prefix.empty() &&
          env_block.find(L"PATH=") == std::wstring::npos &&
          env_block.find(L"Path=") == std::wstring::npos) {
        env_block.append(L"PATH=");
        env_block.append(path_prefix);
        env_block.push_back(L'\0');
      }
      env_block.push_back(L'\0');
    }
  }

  // Optional worker stderr capture for CI diagnosis.
  HANDLE err_file = INVALID_HANDLE_VALUE;
  if (const auto log = capture::env::get("CAPTURE_WORKER_STDERR_LOG")) {
    SECURITY_ATTRIBUTES sa_log{};
    sa_log.nLength = sizeof(sa_log);
    sa_log.bInheritHandle = TRUE;
    err_file = CreateFileA(log->c_str(), GENERIC_WRITE, FILE_SHARE_READ, &sa_log,
                           CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (err_file != INVALID_HANDLE_VALUE) {
      si.dwFlags |= STARTF_USESTDHANDLES;
      si.hStdInput = GetStdHandle(STD_INPUT_HANDLE);
      si.hStdOutput = err_file;
      si.hStdError = err_file;
    }
  }

  const BOOL inherit_handles = (err_file != INVALID_HANDLE_VALUE) ? TRUE : FALSE;
  const DWORD create_flags =
      CREATE_SUSPENDED | CREATE_NO_WINDOW |
      (env_block.empty() ? 0u : CREATE_UNICODE_ENVIRONMENT);
  if (!CreateProcessW(exe_w.c_str(), cmd_buf.data(), nullptr, nullptr,
                      inherit_handles, create_flags,
                      env_block.empty() ? nullptr : env_block.data(), nullptr,
                      &si, &pi)) {
    if (err_file != INVALID_HANDLE_VALUE) {
      CloseHandle(err_file);
    }
    CloseHandle(pipe);
    error = "CreateProcessW CREATE_SUSPENDED failed";
    return false;
  }
  if (err_file != INVALID_HANDLE_VALUE) {
    CloseHandle(err_file);
  }

  if (!job_.assign_process(pi.hProcess, error)) {
    TerminateProcess(pi.hProcess, 1);
    CloseHandle(pi.hThread);
    CloseHandle(pi.hProcess);
    CloseHandle(pipe);
    return false;
  }

  if (ResumeThread(pi.hThread) == static_cast<DWORD>(-1)) {
    error = "ResumeThread failed";
    TerminateProcess(pi.hProcess, 1);
    CloseHandle(pi.hThread);
    CloseHandle(pi.hProcess);
    CloseHandle(pipe);
    return false;
  }

  out.pid = pi.dwProcessId;
  out.process = pi.hProcess;
  out.thread = pi.hThread;

  const DWORD timeout_ms =
      static_cast<DWORD>((std::max)(connect_timeout.count(), 1LL));
  if (!await_connect(pipe, timeout_ms)) {
    error = "worker did not connect to pipe";
    stop(out);
    CloseHandle(pipe);
    return false;
  }

  // Switch to blocking mode for the handshake exchange.
  DWORD mode = PIPE_READMODE_BYTE | PIPE_WAIT;
  SetNamedPipeHandleState(pipe, &mode, nullptr, nullptr);

  {
    std::string sid_err;
    if (!peer_sid_matches_self(pipe, sid_err)) {
      error = "worker peer SID rejected: " + sid_err;
      stop(out);
      CloseHandle(pipe);
      return false;
    }
  }

  capture::Frame hello_frame;
  if (!read_frame(pipe, out.decoder, hello_frame, timeout_ms)) {
    error = "timed out waiting for worker Hello";
    stop(out);
    CloseHandle(pipe);
    return false;
  }
  if (hello_frame.message_type !=
      static_cast<uint32_t>(capture::v1::MESSAGE_TYPE_HELLO)) {
    error = "first worker frame was not Hello";
    stop(out);
    CloseHandle(pipe);
    return false;
  }
  capture::v1::Hello hello;
  if (!hello.ParseFromArray(hello_frame.payload.data(),
                            static_cast<int>(hello_frame.payload.size()))) {
    error = "failed to parse worker Hello";
    stop(out);
    CloseHandle(pipe);
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
    if (!write_all(pipe, frame)) {
      error = "failed to write HelloAck";
      stop(out);
      CloseHandle(pipe);
      return false;
    }
  }
  if (!ack.accepted()) {
    error = "worker Hello rejected: " + ack.error().message();
    stop(out);
    CloseHandle(pipe);
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
    if (!write_all(pipe, frame)) {
      error = "failed to write Identify";
      stop(out);
      CloseHandle(pipe);
      return false;
    }
  }

  capture::Frame id_frame;
  if (!read_frame(pipe, out.decoder, id_frame, timeout_ms)) {
    error = "timed out waiting for IdentifyReply";
    stop(out);
    CloseHandle(pipe);
    return false;
  }
  if (id_frame.message_type !=
      static_cast<uint32_t>(capture::v1::MESSAGE_TYPE_IDENTIFY_REPLY)) {
    error = "expected IdentifyReply";
    stop(out);
    CloseHandle(pipe);
    return false;
  }
  capture::v1::IdentifyReply id_reply;
  if (!id_reply.ParseFromArray(id_frame.payload.data(),
                               static_cast<int>(id_frame.payload.size()))) {
    error = "failed to parse IdentifyReply";
    stop(out);
    CloseHandle(pipe);
    return false;
  }
  if (id_reply.error().code().size() > 0) {
    error = "Identify failed: " + id_reply.error().message();
    stop(out);
    CloseHandle(pipe);
    return false;
  }

  out.pipe = pipe;
  out.manifest = id_reply.manifest();
  capture::log::info("worker_spawned", "worker Hello+Identify complete",
                     {{"worker_id", worker_id},
                      {"plugin_id", plugin_id},
                      {"pid", std::to_string(out.pid)}});
  return true;
}

void WorkerHost::stop(SpawnedWorker& worker) {
  if (worker.pipe != nullptr) {
    FlushFileBuffers(static_cast<HANDLE>(worker.pipe));
    DisconnectNamedPipe(static_cast<HANDLE>(worker.pipe));
    close_handle(worker.pipe);
  }
  if (worker.process != nullptr) {
    if (WaitForSingleObject(static_cast<HANDLE>(worker.process), 200) ==
        WAIT_TIMEOUT) {
      TerminateProcess(static_cast<HANDLE>(worker.process), 0);
      WaitForSingleObject(static_cast<HANDLE>(worker.process), 2000);
    }
  }
  close_handle(worker.thread);
  close_handle(worker.process);
  worker.pid = 0;
}

namespace {

template <typename Req, typename Reply>
bool worker_rpc(SpawnedWorker& worker, capture::v1::MessageType req_type,
                capture::v1::MessageType reply_type, const Req& req,
                Reply& reply, uint32_t corr, DWORD timeout_ms,
                std::string& error) {
  std::lock_guard io_lock(*worker.io_mutex);
  HANDLE pipe = static_cast<HANDLE>(worker.pipe);
  std::string bytes;
  req.SerializeToString(&bytes);
  auto frame = capture::encode_frame(
      static_cast<uint32_t>(req_type),
      std::span<const uint8_t>(reinterpret_cast<const uint8_t*>(bytes.data()),
                               bytes.size()),
      corr);
  if (!write_all(pipe, frame)) {
    error = "failed to write RPC";
    return false;
  }
  const auto deadline = GetTickCount64() + timeout_ms;
  while (GetTickCount64() < deadline) {
    const DWORD remain =
        static_cast<DWORD>((std::max)(1ULL, deadline - GetTickCount64()));
    capture::Frame resp;
    if (!read_frame(pipe, worker.decoder, resp, remain)) {
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
      // Ack immediately so the worker is never blocked on metadata.
      ack_segment_sealed(pipe, capture::v1::SegmentSealed{},
                         resp.correlation_id);
    }
  }
  error = "timed out waiting for RPC reply";
  return false;
}

}  // namespace

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
                    static_cast<DWORD>((std::max)(timeout.count(), 1LL)),
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
                    static_cast<DWORD>((std::max)(timeout.count(), 1LL)),
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
                    static_cast<DWORD>((std::max)(timeout.count(), 1LL)),
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
                    static_cast<DWORD>((std::max)(timeout.count(), 1LL)),
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
                    static_cast<DWORD>((std::max)(timeout.count(), 1LL)),
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
                    static_cast<DWORD>((std::max)(timeout.count(), 1LL)),
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
  // Preview is best-effort, so yield the pipe to an in-flight RPC rather than
  // blocking behind it (PREVIEW_TRANSPORT.md).
  std::unique_lock io_lock(*worker.io_mutex, std::try_to_lock);
  if (!io_lock.owns_lock()) {
    return 0;
  }
  HANDLE pipe = static_cast<HANDLE>(worker.pipe);

  // Pull any complete frames already buffered, then any bytes currently in the
  // pipe (non-blocking: only pump while PeekNamedPipe reports data).
  for (;;) {
    capture::Frame frame;
    if (worker.decoder.pop(frame)) {
      stash_unsolicited(worker, frame);
      if (frame.message_type ==
          static_cast<uint32_t>(capture::v1::MESSAGE_TYPE_SEGMENT_SEALED)) {
        ack_segment_sealed(pipe, capture::v1::SegmentSealed{},
                           frame.correlation_id);
      }
      continue;
    }
    DWORD available = 0;
    if (!PeekNamedPipe(pipe, nullptr, 0, nullptr, &available, nullptr) ||
        available == 0) {
      break;
    }
    if (!pump_bytes(pipe, worker.decoder, 50)) {
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
    for (auto& ov : worker.pending_overloads) {
      on_overload(ov);
      ++handled;
    }
  }
  worker.pending_overloads.clear();
  return handled;
}

}  // namespace capture::daemon
