// SPDX-License-Identifier: GPL-3.0-only
#include "camera_worker/camera_enumerate.hpp"

#include <gst/gst.h>

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

#include <cstdint>
#include <sstream>
#include <string>
#include <vector>

#pragma comment(lib, "mfplat.lib")
#pragma comment(lib, "mf.lib")
#pragma comment(lib, "mfuuid.lib")
#pragma comment(lib, "ole32.lib")

namespace capture::camera_worker {
namespace {

std::string wide_to_utf8(const wchar_t* w) {
  if (w == nullptr) {
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
  uint64_t h = 14695981039346656037ull;
  for (unsigned char c : key) {
    h ^= c;
    h *= 1099511628211ull;
  }
  std::ostringstream oss;
  oss << "camera." << std::hex << (h & 0xffffffffull);
  return oss.str();
}

bool g_mf_ready = false;
HRESULT g_mf_hr = E_FAIL;

void ensure_mf() {
  if (g_mf_ready) {
    return;
  }
  g_mf_hr = MFStartup(MF_VERSION, MFSTARTUP_LITE);
  g_mf_ready = true;
}

}  // namespace

std::string init_gstreamer() {
  GError* err = nullptr;
  if (!gst_init_check(nullptr, nullptr, &err)) {
    std::string msg = "gst_init_check failed";
    if (err != nullptr) {
      msg += ": ";
      msg += err->message ? err->message : "(no message)";
      g_error_free(err);
    }
    return msg;
  }
  return {};
}

bool mfvideosrc_available() {
  GstElementFactory* factory = gst_element_factory_find("mfvideosrc");
  if (factory == nullptr) {
    return false;
  }
  gst_object_unref(factory);
  return true;
}

std::vector<CameraDevice> enumerate_cameras() {
  ensure_mf();
  std::vector<CameraDevice> out;
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
    CameraDevice info;
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

}  // namespace capture::camera_worker
