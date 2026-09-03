// SPDX-License-Identifier: GPL-3.0-only
#include "camera_worker/uvc_controls.hpp"

#ifndef NOMINMAX
#define NOMINMAX
#endif
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <Windows.h>
#include <mfapi.h>
#include <mfidl.h>
#include <mfobjects.h>
#include <vidcap.h>

#include <algorithm>
#include <cstdio>

#pragma comment(lib, "mfplat.lib")
#pragma comment(lib, "mf.lib")
#pragma comment(lib, "mfuuid.lib")
#pragma comment(lib, "ole32.lib")

namespace capture::camera_worker {
namespace {

std::wstring utf8_to_wide(const std::string& s) {
  if (s.empty()) {
    return {};
  }
  const int n = MultiByteToWideChar(CP_UTF8, 0, s.c_str(),
                                    static_cast<int>(s.size()), nullptr, 0);
  if (n <= 0) {
    return {};
  }
  std::wstring out(static_cast<size_t>(n), L'\0');
  MultiByteToWideChar(CP_UTF8, 0, s.c_str(), static_cast<int>(s.size()),
                      out.data(), n);
  return out;
}

bool open_device_source(const CameraDevice& device, IMFMediaSource** out,
                        std::string& err) {
  if (out == nullptr) {
    err = "internal error";
    return false;
  }
  *out = nullptr;

  IMFAttributes* attrs = nullptr;
  if (FAILED(MFCreateAttributes(&attrs, 2))) {
    err = "MFCreateAttributes failed";
    return false;
  }
  attrs->SetGUID(MF_DEVSOURCE_ATTRIBUTE_SOURCE_TYPE,
                 MF_DEVSOURCE_ATTRIBUTE_SOURCE_TYPE_VIDCAP_GUID);

  HRESULT hr = E_FAIL;
  if (!device.symbolic_link.empty()) {
    const std::wstring symlink = utf8_to_wide(device.symbolic_link);
    if (!symlink.empty()) {
      attrs->SetString(MF_DEVSOURCE_ATTRIBUTE_SOURCE_TYPE_VIDCAP_SYMBOLIC_LINK,
                       symlink.c_str());
      hr = MFCreateDeviceSource(attrs, out);
    }
  }
  if (FAILED(hr) && !device.friendly_name.empty()) {
    const std::wstring friendly = utf8_to_wide(device.friendly_name);
    if (!friendly.empty()) {
      attrs->SetString(MF_DEVSOURCE_ATTRIBUTE_FRIENDLY_NAME, friendly.c_str());
      hr = MFCreateDeviceSource(attrs, out);
    }
  }
  attrs->Release();

  if (FAILED(hr) || *out == nullptr) {
    err = "MFCreateDeviceSource failed (device may be in use by capture)";
    return false;
  }
  return true;
}

void release_source(IMFMediaSource* source) {
  if (source == nullptr) {
    return;
  }
  source->Shutdown();
  source->Release();
}

}  // namespace

bool query_uvc_limits(const CameraDevice& device, UvcControlLimits& out,
                      std::string& err) {
  out = UvcControlLimits{};
  if (device.symbolic_link.empty() && device.friendly_name.empty()) {
    return true;
  }

  IMFMediaSource* source = nullptr;
  if (!open_device_source(device, &source, err)) {
    return false;
  }

  IAMCameraControl* camera = nullptr;
  if (SUCCEEDED(source->QueryInterface(IID_PPV_ARGS(&camera))) &&
      camera != nullptr) {
    long min_v = 0;
    long max_v = 0;
    long step = 0;
    long default_v = 0;
    long flags = 0;
    if (SUCCEEDED(camera->GetRange(CameraControl_Exposure, &min_v, &max_v,
                                   &step, &default_v, &flags))) {
      out.exposure_available = true;
      out.exposure_min = static_cast<int>(min_v);
      out.exposure_max = static_cast<int>(max_v);
      out.exposure_default = static_cast<int>(default_v);
      out.exposure_step = step > 0 ? static_cast<int>(step) : 1;
    }
    camera->Release();
  }

  IAMVideoProcAmp* proc = nullptr;
  if (SUCCEEDED(source->QueryInterface(IID_PPV_ARGS(&proc))) && proc != nullptr) {
    long min_v = 0;
    long max_v = 0;
    long step = 0;
    long default_v = 0;
    long flags = 0;
    if (SUCCEEDED(proc->GetRange(VideoProcAmp_Gain, &min_v, &max_v, &step,
                                 &default_v, &flags))) {
      out.gain_available = true;
      out.gain_min = static_cast<int>(min_v);
      out.gain_max = static_cast<int>(max_v);
      out.gain_default = static_cast<int>(default_v);
      out.gain_step = step > 0 ? static_cast<int>(step) : 1;
    }
    proc->Release();
  }

  release_source(source);
  err.clear();
  return true;
}

bool apply_uvc_controls(const CameraDevice& device, bool exposure_auto,
                        std::optional<int> exposure_time,
                        std::optional<int> gain, std::string& err) {
  if (device.symbolic_link.empty() && device.friendly_name.empty()) {
    return true;
  }

  IMFMediaSource* source = nullptr;
  if (!open_device_source(device, &source, err)) {
    return false;
  }

  bool ok = true;
  std::string detail;

  IAMCameraControl* camera = nullptr;
  if (SUCCEEDED(source->QueryInterface(IID_PPV_ARGS(&camera))) &&
      camera != nullptr) {
    if (exposure_auto) {
      const HRESULT hr =
          camera->Set(CameraControl_Exposure, 0, CameraControl_Flags_Auto);
      if (FAILED(hr)) {
        ok = false;
        detail = "Set auto exposure failed";
      }
    } else if (exposure_time.has_value()) {
      const HRESULT hr = camera->Set(
          CameraControl_Exposure, static_cast<long>(*exposure_time),
          CameraControl_Flags_Manual);
      if (FAILED(hr)) {
        ok = false;
        detail = "Set manual exposure failed";
      }
    }
    camera->Release();
  } else if (!exposure_auto || exposure_time.has_value()) {
    ok = false;
    detail = "IAMCameraControl unavailable";
  }

  if (gain.has_value()) {
    IAMVideoProcAmp* proc = nullptr;
    if (SUCCEEDED(source->QueryInterface(IID_PPV_ARGS(&proc))) &&
        proc != nullptr) {
      const HRESULT hr = proc->Set(VideoProcAmp_Gain, static_cast<long>(*gain),
                                   VideoProcAmp_Flags_Manual);
      if (FAILED(hr)) {
        ok = false;
        if (!detail.empty()) {
          detail += "; ";
        }
        detail += "Set gain failed";
      }
      proc->Release();
    } else {
      ok = false;
      if (!detail.empty()) {
        detail += "; ";
      }
      detail += "IAMVideoProcAmp unavailable";
    }
  }

  release_source(source);
  if (!ok) {
    err = detail.empty() ? "UVC control apply failed" : detail;
  } else {
    err.clear();
  }
  return ok;
}

}  // namespace capture::camera_worker
