// SPDX-License-Identifier: GPL-3.0-only
#include "capture_daemon/camera_capture.hpp"

#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <Windows.h>
#include <mfapi.h>
#include <mfidl.h>
#include <mfreadwrite.h>
#include <mferror.h>

#include <algorithm>
#include <chrono>
#include <cmath>
#include <sstream>

#pragma comment(lib, "mfplat.lib")
#pragma comment(lib, "mf.lib")
#pragma comment(lib, "mfreadwrite.lib")
#pragma comment(lib, "mfuuid.lib")
#pragma comment(lib, "ole32.lib")

namespace capture::daemon {
namespace {

std::once_flag g_mf_once;
HRESULT g_mf_hr = E_FAIL;

void ensure_mf() {
  std::call_once(g_mf_once, [] {
    g_mf_hr = MFStartup(MF_VERSION, MFSTARTUP_LITE);
  });
}

std::string wide_to_utf8(const wchar_t* w) {
  if (!w) {
    return {};
  }
  const int n = WideCharToMultiByte(CP_UTF8, 0, w, -1, nullptr, 0, nullptr, nullptr);
  if (n <= 1) {
    return {};
  }
  std::string out(static_cast<size_t>(n - 1), '\0');
  WideCharToMultiByte(CP_UTF8, 0, w, -1, out.data(), n, nullptr, nullptr);
  return out;
}

std::string stable_key_to_source_id(const std::string& key) {
  // Short deterministic id from the symbolic link; not a secret hash.
  uint64_t h = 14695981039346656037ull;
  for (unsigned char c : key) {
    h ^= c;
    h *= 1099511628211ull;
  }
  std::ostringstream oss;
  oss << "camera." << std::hex << (h & 0xffffffffull);
  return oss.str();
}

int64_t now_qpc_ns() {
  LARGE_INTEGER freq{};
  LARGE_INTEGER counter{};
  QueryPerformanceFrequency(&freq);
  QueryPerformanceCounter(&counter);
  if (freq.QuadPart <= 0) {
    return 0;
  }
  return (counter.QuadPart * 1000000000LL) / freq.QuadPart;
}

void downscale_rgb24(const uint8_t* src, uint32_t sw, uint32_t sh,
                     std::vector<uint8_t>& dst, uint32_t& dw, uint32_t& dh) {
  const uint32_t longest = (std::max)(sw, sh);
  const double scale = longest > 480 ? (480.0 / static_cast<double>(longest)) : 1.0;
  dw = (std::max)(1u, static_cast<uint32_t>(std::lround(sw * scale)));
  dh = (std::max)(1u, static_cast<uint32_t>(std::lround(sh * scale)));
  dst.assign(static_cast<size_t>(dw) * dh * 3, 0);
  for (uint32_t y = 0; y < dh; ++y) {
    const uint32_t sy = (std::min)(sh - 1, static_cast<uint32_t>(y * sh / dh));
    for (uint32_t x = 0; x < dw; ++x) {
      const uint32_t sx = (std::min)(sw - 1, static_cast<uint32_t>(x * sw / dw));
      const size_t si = (static_cast<size_t>(sy) * sw + sx) * 3;
      const size_t di = (static_cast<size_t>(y) * dw + x) * 3;
      dst[di] = src[si];
      dst[di + 1] = src[si + 1];
      dst[di + 2] = src[si + 2];
    }
  }
}

}  // namespace

CameraCapture::CameraCapture() = default;

CameraCapture::~CameraCapture() {
  stop();
  close();
}

std::vector<CameraDeviceInfo> CameraCapture::enumerate() {
  ensure_mf();
  std::vector<CameraDeviceInfo> out;
  if (FAILED(g_mf_hr)) {
    return out;
  }

  IMFAttributes* attrs = nullptr;
  if (FAILED(MFCreateAttributes(&attrs, 1))) {
    return out;
  }
  attrs->SetGUID(MF_DEVSOURCE_ATTRIBUTE_SOURCE_TYPE,
                 MF_DEVSOURCE_ATTRIBUTE_SOURCE_TYPE_VIDCAP_GUID);

  IMFActivate** devices = nullptr;
  UINT32 count = 0;
  const HRESULT hr = MFEnumDeviceSources(attrs, &devices, &count);
  attrs->Release();
  if (FAILED(hr) || devices == nullptr) {
    return out;
  }

  for (UINT32 i = 0; i < count; ++i) {
    CameraDeviceInfo info;
    WCHAR* friendly = nullptr;
    UINT32 friendly_len = 0;
    if (SUCCEEDED(devices[i]->GetAllocatedString(
            MF_DEVSOURCE_ATTRIBUTE_FRIENDLY_NAME, &friendly, &friendly_len))) {
      info.friendly_name = wide_to_utf8(friendly);
      CoTaskMemFree(friendly);
    }
    WCHAR* symlink = nullptr;
    UINT32 symlink_len = 0;
    if (SUCCEEDED(devices[i]->GetAllocatedString(
            MF_DEVSOURCE_ATTRIBUTE_SOURCE_TYPE_VIDCAP_SYMBOLIC_LINK, &symlink,
            &symlink_len))) {
      info.symbolic_link = wide_to_utf8(symlink);
      info.stable_device_key = info.symbolic_link;
      CoTaskMemFree(symlink);
    }
    if (info.stable_device_key.empty()) {
      info.stable_device_key = "camera-index-" + std::to_string(i);
    }
    info.source_id = stable_key_to_source_id(info.stable_device_key);
    info.vendor = "Windows";
    info.model = info.friendly_name.empty() ? "Video Capture Device"
                                            : info.friendly_name;
    out.push_back(std::move(info));
    devices[i]->Release();
  }
  CoTaskMemFree(devices);
  return out;
}

bool CameraCapture::open(const CameraDeviceInfo& device, std::string& error) {
  ensure_mf();
  if (FAILED(g_mf_hr)) {
    error = "Media Foundation startup failed";
    return false;
  }
  close();
  device_ = device;

  IMFAttributes* attrs = nullptr;
  if (FAILED(MFCreateAttributes(&attrs, 2))) {
    error = "MFCreateAttributes failed";
    return false;
  }
  attrs->SetGUID(MF_DEVSOURCE_ATTRIBUTE_SOURCE_TYPE,
                 MF_DEVSOURCE_ATTRIBUTE_SOURCE_TYPE_VIDCAP_GUID);
  const std::wstring wlink(device.symbolic_link.begin(), device.symbolic_link.end());
  attrs->SetString(MF_DEVSOURCE_ATTRIBUTE_SOURCE_TYPE_VIDCAP_SYMBOLIC_LINK,
                   wlink.c_str());

  IMFMediaSource* source = nullptr;
  HRESULT hr = MFCreateDeviceSource(attrs, &source);
  attrs->Release();
  if (FAILED(hr) || source == nullptr) {
    error = "MFCreateDeviceSource failed";
    return false;
  }

  IMFSourceReader* reader = nullptr;
  hr = MFCreateSourceReaderFromMediaSource(source, nullptr, &reader);
  source->Release();
  if (FAILED(hr) || reader == nullptr) {
    error = "MFCreateSourceReaderFromMediaSource failed";
    return false;
  }

  // Prefer RGB32 for simple thumbnail conversion.
  IMFMediaType* type = nullptr;
  MFCreateMediaType(&type);
  type->SetGUID(MF_MT_MAJOR_TYPE, MFMediaType_Video);
  type->SetGUID(MF_MT_SUBTYPE, MFVideoFormat_RGB32);
  reader->SetCurrentMediaType(static_cast<DWORD>(MF_SOURCE_READER_FIRST_VIDEO_STREAM),
                              nullptr, type);
  type->Release();

  IMFMediaType* current = nullptr;
  if (SUCCEEDED(reader->GetCurrentMediaType(
          static_cast<DWORD>(MF_SOURCE_READER_FIRST_VIDEO_STREAM), &current))) {
    UINT32 w = 0;
    UINT32 h = 0;
    MFGetAttributeSize(current, MF_MT_FRAME_SIZE, &w, &h);
    native_width_ = w;
    native_height_ = h;
    current->Release();
  }

  source_reader_ = reader;
  open_ = true;
  return true;
}

void CameraCapture::close() {
  stop();
  if (source_reader_) {
    static_cast<IMFSourceReader*>(source_reader_)->Release();
    source_reader_ = nullptr;
  }
  open_ = false;
  preview_.clear();
  std::lock_guard lock(mu_);
  timings_.clear();
}

bool CameraCapture::start(std::string& error) {
  if (!open_) {
    error = "camera not open";
    return false;
  }
  if (running_.load()) {
    return true;
  }
  running_ = true;
  frame_count_ = 0;
  sequence_ = 0;
  rate_window_frames_ = 0;
  rate_window_start_ns_ = now_qpc_ns();
  worker_ = std::thread([this] { capture_loop(); });
  return true;
}

void CameraCapture::stop() {
  running_ = false;
  if (worker_.joinable()) {
    worker_.join();
  }
}

bool CameraCapture::take_preview(PreviewFrameData& out) { return preview_.take(out); }

bool CameraCapture::copy_preview(PreviewFrameData& out) const {
  return preview_.copy_latest(out);
}

std::vector<CameraFrameTiming> CameraCapture::drain_timings() {
  std::lock_guard lock(mu_);
  std::vector<CameraFrameTiming> out;
  out.swap(timings_);
  return out;
}

double CameraCapture::measured_rate_hz() const {
  std::lock_guard lock(mu_);
  return measured_rate_hz_;
}

std::string CameraCapture::last_error() const {
  std::lock_guard lock(mu_);
  return last_error_;
}

void CameraCapture::capture_loop() {
  while (running_.load()) {
    std::string err;
    if (!read_one_frame(err)) {
      if (!err.empty()) {
        std::lock_guard lock(mu_);
        last_error_ = err;
      }
      std::this_thread::sleep_for(std::chrono::milliseconds(5));
    }
  }
}

bool CameraCapture::read_one_frame(std::string& error) {
  auto* reader = static_cast<IMFSourceReader*>(source_reader_);
  if (!reader) {
    error = "no reader";
    return false;
  }

  DWORD stream = 0;
  DWORD flags = 0;
  LONGLONG timestamp = 0;
  IMFSample* sample = nullptr;
  const HRESULT hr = reader->ReadSample(
      static_cast<DWORD>(MF_SOURCE_READER_FIRST_VIDEO_STREAM), 0, &stream, &flags,
      &timestamp, &sample);
  if (FAILED(hr)) {
    error = "ReadSample failed";
    return false;
  }
  if (flags & MF_SOURCE_READERF_ENDOFSTREAM) {
    error = "end of stream";
    if (sample) {
      sample->Release();
    }
    return false;
  }
  if (!sample) {
    return false;
  }

  IMFMediaBuffer* buffer = nullptr;
  if (FAILED(sample->ConvertToContiguousBuffer(&buffer)) || !buffer) {
    sample->Release();
    error = "ConvertToContiguousBuffer failed";
    return false;
  }

  BYTE* data = nullptr;
  DWORD max_len = 0;
  DWORD cur_len = 0;
  if (FAILED(buffer->Lock(&data, &max_len, &cur_len)) || data == nullptr) {
    buffer->Release();
    sample->Release();
    error = "buffer lock failed";
    return false;
  }

  const uint32_t w = native_width_ ? native_width_ : 640;
  const uint32_t h = native_height_ ? native_height_ : 480;
  // RGB32 (B,G,R,A) bottom-up in some MF paths; convert to top-down RGB24.
  std::vector<uint8_t> rgb(static_cast<size_t>(w) * h * 3);
  const DWORD stride = w * 4;
  const bool enough = cur_len >= stride * h;
  if (enough) {
    for (uint32_t y = 0; y < h; ++y) {
      const BYTE* row = data + static_cast<size_t>(y) * stride;
      for (uint32_t x = 0; x < w; ++x) {
        const size_t di = (static_cast<size_t>(y) * w + x) * 3;
        rgb[di] = row[x * 4 + 2];
        rgb[di + 1] = row[x * 4 + 1];
        rgb[di + 2] = row[x * 4 + 0];
      }
    }
  }
  buffer->Unlock();
  buffer->Release();
  sample->Release();
  if (!enough) {
    error = "short frame buffer";
    return false;
  }

  const int64_t host_ns = now_qpc_ns();
  ++sequence_;
  frame_count_.fetch_add(1);

  PreviewFrameData preview;
  preview.source_id = device_.source_id;
  preview.stream_id = device_.source_id + ".video";
  preview.kind = PreviewKind::ImageThumbnail;
  preview.session_time_ns = 0;  // filled by engine when T0 known
  preview.sequence = sequence_;
  preview.pixel_format = "rgb24";
  downscale_rgb24(rgb.data(), w, h, preview.image, preview.width, preview.height);
  preview_.publish(std::move(preview));

  CameraFrameTiming timing;
  timing.sequence = sequence_;
  timing.host_arrival_ns = host_ns;
  timing.device_timestamp_100ns = timestamp;
  timing.width = w;
  timing.height = h;

  {
    std::lock_guard lock(mu_);
    timings_.push_back(timing);
    if (timings_.size() > 240) {
      timings_.erase(timings_.begin(), timings_.begin() + 60);
    }
    ++rate_window_frames_;
    const int64_t elapsed = host_ns - rate_window_start_ns_;
    if (elapsed >= 1000000000LL) {
      measured_rate_hz_ =
          rate_window_frames_ * 1e9 / static_cast<double>(elapsed);
      rate_window_frames_ = 0;
      rate_window_start_ns_ = host_ns;
    }
  }
  return true;
}

}  // namespace capture::daemon
