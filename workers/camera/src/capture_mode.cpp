// SPDX-License-Identifier: GPL-3.0-only
#include "camera_worker/capture_mode.hpp"

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

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <map>
#include <sstream>

#pragma comment(lib, "mfplat.lib")
#pragma comment(lib, "mf.lib")
#pragma comment(lib, "mfuuid.lib")
#pragma comment(lib, "ole32.lib")

namespace capture::camera_worker {
namespace {

const char* resolution_name(int width, int height) {
  if (width == 3840 && height == 2160) {
    return "4K (UHD)";
  }
  if (width == 2560 && height == 1440) {
    return "2K (QHD)";
  }
  if (width == 1920 && height == 1080) {
    return "1080p (FHD)";
  }
  if (width == 1280 && height == 720) {
    return "720p (HD)";
  }
  if (width == 640 && height == 480) {
    return "480p";
  }
  return nullptr;
}

// Cheapest first: NV12 is what the H.264 encoders consume, so selecting it
// makes the record branch's videoconvert a passthrough.
int pixel_format_rank(const std::string& format) {
  if (format == "NV12") {
    return 4;
  }
  if (format == "I420" || format == "YV12") {
    return 3;
  }
  if (format == "YUY2" || format == "UYVY") {
    return 2;
  }
  return 1;
}

// Chooses between variants of the same resolution and rate. Raw wins over
// MJPEG when the device offers both; MJPEG-only devices still get their mode.
int mode_score(const CaptureMode& m) {
  return m.is_jpeg ? 0 : 10 + pixel_format_rank(m.pixel_format);
}

void reduce_fraction(int& n, int& d) {
  if (n <= 0 || d <= 0) {
    return;
  }
  int a = n;
  int b = d;
  while (b != 0) {
    const int t = a % b;
    a = b;
    b = t;
  }
  if (a > 1) {
    n /= a;
    d /= a;
  }
}

// MF reports rates such as 10000000/1333333 for nominal 7.5 fps. Snap those to
// the intended simple fraction so keys stay stable and readable.
void normalize_frame_rate(int& n, int& d) {
  reduce_fraction(n, d);
  if (d <= 1) {
    return;
  }
  const double fps = static_cast<double>(n) / d;
  if (std::fabs(fps - std::round(fps)) < 0.01) {
    n = static_cast<int>(std::lround(fps));
    d = 1;
    return;
  }
  const double ntsc = fps * 1001.0 / 1000.0;
  if (std::fabs(ntsc - std::round(ntsc)) < 0.01) {
    n = static_cast<int>(std::lround(ntsc)) * 1000;
    d = 1001;
    return;
  }
  const double halves = fps * 2.0;
  if (std::fabs(halves - std::round(halves)) < 0.02) {
    n = static_cast<int>(std::lround(halves));
    d = 2;
    reduce_fraction(n, d);
  }
}

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

// GStreamer format name for an MF video subtype, or nullptr when the subtype is
// not something the raw branch can carry.
const char* raw_format_for_subtype(const GUID& subtype) {
  struct Entry {
    const GUID* guid;
    const char* format;
  };
  static const Entry kTable[] = {
      {&MFVideoFormat_NV12, "NV12"},   {&MFVideoFormat_YUY2, "YUY2"},
      {&MFVideoFormat_UYVY, "UYVY"},   {&MFVideoFormat_YV12, "YV12"},
      {&MFVideoFormat_I420, "I420"},   {&MFVideoFormat_IYUV, "I420"},
      {&MFVideoFormat_RGB24, "BGR"},   {&MFVideoFormat_RGB32, "BGRx"},
      {&MFVideoFormat_ARGB32, "BGRA"}, {&MFVideoFormat_P010, "P010"},
  };
  for (const auto& entry : kTable) {
    if (IsEqualGUID(subtype, *entry.guid)) {
      return entry.format;
    }
  }
  return nullptr;
}

// Native media types reported by the device itself. This mirrors the mode list
// Windows and vendor utilities show, including per-resolution frame rates.
std::vector<CaptureMode> probe_modes_mf(const CameraDevice& device) {
  std::vector<CaptureMode> out;
  const std::wstring symlink = utf8_to_wide(device.symbolic_link);
  if (symlink.empty()) {
    return out;
  }

  IMFAttributes* attrs = nullptr;
  if (FAILED(MFCreateAttributes(&attrs, 2))) {
    return out;
  }
  attrs->SetGUID(MF_DEVSOURCE_ATTRIBUTE_SOURCE_TYPE,
                 MF_DEVSOURCE_ATTRIBUTE_SOURCE_TYPE_VIDCAP_GUID);
  attrs->SetString(MF_DEVSOURCE_ATTRIBUTE_SOURCE_TYPE_VIDCAP_SYMBOLIC_LINK,
                   symlink.c_str());

  IMFMediaSource* source = nullptr;
  const HRESULT hr = MFCreateDeviceSource(attrs, &source);
  attrs->Release();
  if (FAILED(hr) || source == nullptr) {
    return out;
  }

  IMFPresentationDescriptor* pd = nullptr;
  if (SUCCEEDED(source->CreatePresentationDescriptor(&pd)) && pd != nullptr) {
    DWORD stream_count = 0;
    pd->GetStreamDescriptorCount(&stream_count);
    for (DWORD si = 0; si < stream_count; ++si) {
      BOOL selected = FALSE;
      IMFStreamDescriptor* sd = nullptr;
      if (FAILED(pd->GetStreamDescriptorByIndex(si, &selected, &sd)) ||
          sd == nullptr) {
        continue;
      }
      IMFMediaTypeHandler* handler = nullptr;
      if (SUCCEEDED(sd->GetMediaTypeHandler(&handler)) && handler != nullptr) {
        DWORD type_count = 0;
        handler->GetMediaTypeCount(&type_count);
        for (DWORD ti = 0; ti < type_count; ++ti) {
          IMFMediaType* type = nullptr;
          if (FAILED(handler->GetMediaTypeByIndex(ti, &type)) ||
              type == nullptr) {
            continue;
          }
          GUID subtype = GUID_NULL;
          UINT32 width = 0;
          UINT32 height = 0;
          UINT32 fps_n = 0;
          UINT32 fps_d = 0;
          const bool ok =
              SUCCEEDED(type->GetGUID(MF_MT_SUBTYPE, &subtype)) &&
              SUCCEEDED(MFGetAttributeSize(type, MF_MT_FRAME_SIZE, &width,
                                           &height)) &&
              width > 0 && height > 0;
          if (ok) {
            if (FAILED(MFGetAttributeRatio(type, MF_MT_FRAME_RATE, &fps_n,
                                           &fps_d)) ||
                fps_n == 0 || fps_d == 0) {
              fps_n = 30;
              fps_d = 1;
            }
            CaptureMode mode;
            mode.width = static_cast<int>(width);
            mode.height = static_cast<int>(height);
            mode.fps_n = static_cast<int>(fps_n);
            mode.fps_d = static_cast<int>(fps_d);
            normalize_frame_rate(mode.fps_n, mode.fps_d);
            if (IsEqualGUID(subtype, MFVideoFormat_MJPG)) {
              mode.is_jpeg = true;
              out.push_back(std::move(mode));
            } else if (const char* fmt = raw_format_for_subtype(subtype)) {
              mode.pixel_format = fmt;
              out.push_back(std::move(mode));
            }
          }
          type->Release();
        }
        handler->Release();
      }
      sd->Release();
    }
    pd->Release();
  }

  source->Shutdown();
  source->Release();
  return out;
}

// Fallback for devices MF cannot open directly: negotiate through mfvideosrc.
// The device is only opened in PAUSED, where the pad advertises real caps.
std::vector<CaptureMode> probe_modes_gst(const CameraDevice& device) {
  std::vector<CaptureMode> out;
  GstElement* pipeline = gst_pipeline_new("mode-probe");
  GstElement* src = gst_element_factory_make("mfvideosrc", "src");
  GstElement* sink = gst_element_factory_make("fakesink", "sink");
  if (!pipeline || !src || !sink) {
    if (pipeline) {
      gst_object_unref(pipeline);
    }
    return out;
  }
  g_object_set(src, "device-path", device.symbolic_link.c_str(), nullptr);
  g_object_set(sink, "sync", FALSE, nullptr);
  gst_bin_add_many(GST_BIN(pipeline), src, sink, nullptr);
  if (!gst_element_link(src, sink)) {
    gst_object_unref(pipeline);
    return out;
  }
  if (gst_element_set_state(pipeline, GST_STATE_PAUSED) ==
      GST_STATE_CHANGE_FAILURE) {
    gst_element_set_state(pipeline, GST_STATE_NULL);
    gst_object_unref(pipeline);
    return out;
  }
  gst_element_get_state(pipeline, nullptr, nullptr, 3 * GST_SECOND);

  GstPad* pad = gst_element_get_static_pad(src, "src");
  if (pad != nullptr) {
    GstCaps* caps = gst_pad_query_caps(pad, nullptr);
    if (caps != nullptr) {
      for (guint i = 0; i < gst_caps_get_size(caps); ++i) {
        const GstStructure* s = gst_caps_get_structure(caps, i);
        const gchar* name = gst_structure_get_name(s);
        if (name == nullptr) {
          continue;
        }
        CaptureMode mode;
        mode.is_jpeg = g_str_has_prefix(name, "image/jpeg") != FALSE;
        if (!mode.is_jpeg && !g_str_has_prefix(name, "video/x-raw")) {
          continue;
        }
        gint width = 0;
        gint height = 0;
        if (!gst_structure_get_int(s, "width", &width) ||
            !gst_structure_get_int(s, "height", &height) || width <= 0 ||
            height <= 0) {
          continue;
        }
        mode.width = width;
        mode.height = height;
        gint fps_n = 0;
        gint fps_d = 1;
        if (gst_structure_get_fraction(s, "framerate", &fps_n, &fps_d) &&
            fps_n > 0 && fps_d > 0) {
          mode.fps_n = fps_n;
          mode.fps_d = fps_d;
        } else {
          const GValue* fr = gst_structure_get_value(s, "framerate");
          if (fr != nullptr && GST_VALUE_HOLDS_LIST(fr) &&
              gst_value_list_get_size(fr) > 0) {
            for (guint k = 0; k < gst_value_list_get_size(fr); ++k) {
              const GValue* item = gst_value_list_get_value(fr, k);
              if (item == nullptr || !GST_VALUE_HOLDS_FRACTION(item)) {
                continue;
              }
              CaptureMode variant = mode;
              variant.fps_n = gst_value_get_fraction_numerator(item);
              variant.fps_d = gst_value_get_fraction_denominator(item);
              if (!mode.is_jpeg) {
                const gchar* fmt = gst_structure_get_string(s, "format");
                if (fmt != nullptr) {
                  variant.pixel_format = fmt;
                }
              }
              if (variant.fps_n > 0 && variant.fps_d > 0) {
                out.push_back(std::move(variant));
              }
            }
            continue;
          }
          if (fr != nullptr && GST_VALUE_HOLDS_FRACTION_RANGE(fr)) {
            const GValue* maxv = gst_value_get_fraction_range_max(fr);
            if (maxv != nullptr) {
              mode.fps_n = gst_value_get_fraction_numerator(maxv);
              mode.fps_d = gst_value_get_fraction_denominator(maxv);
            }
          }
          if (mode.fps_n <= 0) {
            mode.fps_n = 30;
            mode.fps_d = 1;
          }
        }
        if (!mode.is_jpeg) {
          const gchar* fmt = gst_structure_get_string(s, "format");
          if (fmt != nullptr) {
            mode.pixel_format = fmt;
          }
        }
        out.push_back(std::move(mode));
      }
      gst_caps_unref(caps);
    }
    gst_object_unref(pad);
  }
  gst_element_set_state(pipeline, GST_STATE_NULL);
  gst_object_unref(pipeline);
  return out;
}

}  // namespace

std::string CaptureMode::key() const {
  std::ostringstream oss;
  oss << width << 'x' << height << '@' << fps_n;
  if (fps_d != 1) {
    oss << '/' << fps_d;
  }
  oss << ':' << (is_jpeg ? "MJPG" : (pixel_format.empty() ? "RAW" : pixel_format));
  return oss.str();
}

std::string CaptureMode::label() const {
  const double fps =
      fps_d > 0 ? static_cast<double>(fps_n) / static_cast<double>(fps_d) : 0.0;
  char fps_buf[32];
  if (std::fabs(fps - std::round(fps)) < 0.05) {
    std::snprintf(fps_buf, sizeof(fps_buf), "%.0f", fps);
  } else {
    std::snprintf(fps_buf, sizeof(fps_buf), "%.2f", fps);
  }
  const char* named = resolution_name(width, height);
  std::ostringstream oss;
  if (named != nullptr) {
    oss << named << " · ";
  }
  oss << width << 'x' << height << " @ " << fps_buf << " fps";
  if (is_jpeg) {
    oss << " (MJPEG)";
  } else if (!pixel_format.empty()) {
    oss << " (" << pixel_format << ')';
  }
  return oss.str();
}

std::string CaptureMode::caps_string() const {
  std::ostringstream oss;
  if (is_jpeg) {
    oss << "image/jpeg,width=" << width << ",height=" << height;
  } else {
    oss << "video/x-raw";
    if (!pixel_format.empty()) {
      oss << ",format=" << pixel_format;
    }
    oss << ",width=" << width << ",height=" << height;
  }
  if (fps_n > 0 && fps_d > 0) {
    oss << ",framerate=" << fps_n << '/' << fps_d;
  }
  return oss.str();
}

std::vector<CaptureMode> enumerate_capture_modes(const CameraDevice& device) {
  if (device.symbolic_link.empty() || !mfvideosrc_available()) {
    return {};
  }

  std::vector<CaptureMode> candidates = probe_modes_mf(device);
  if (candidates.empty()) {
    candidates = probe_modes_gst(device);
  }

  // Collapse to one entry per WxH@fps, preferring raw over MJPEG.
  std::map<std::string, CaptureMode> best;
  for (auto& mode : candidates) {
    if (mode.width <= 0 || mode.height <= 0 || mode.fps_n <= 0 ||
        mode.fps_d <= 0) {
      continue;
    }
    normalize_frame_rate(mode.fps_n, mode.fps_d);
    std::ostringstream dedup;
    dedup << mode.width << 'x' << mode.height << '@' << mode.fps_n << '/'
          << mode.fps_d;
    const std::string dk = dedup.str();
    auto it = best.find(dk);
    if (it == best.end() || mode_score(mode) > mode_score(it->second)) {
      best[dk] = std::move(mode);
    }
  }

  std::vector<CaptureMode> out;
  out.reserve(best.size());
  for (auto& [_, mode] : best) {
    (void)_;
    out.push_back(std::move(mode));
  }
  std::sort(out.begin(), out.end(),
            [](const CaptureMode& a, const CaptureMode& b) {
              if (a.width * a.height != b.width * b.height) {
                return a.width * a.height > b.width * b.height;
              }
              const double af =
                  a.fps_d ? static_cast<double>(a.fps_n) / a.fps_d : 0;
              const double bf =
                  b.fps_d ? static_cast<double>(b.fps_n) / b.fps_d : 0;
              return af > bf;
            });
  return out;
}

std::string default_capture_mode_key(const std::vector<CaptureMode>& modes) {
  if (modes.empty()) {
    return {};
  }
  auto score_default = [](const CaptureMode& m) {
    // Prefer 1080p30, then 1440p30, then anything below 4K, then 4K.
    const int pixels = m.width * m.height;
    const double fps =
        m.fps_d ? static_cast<double>(m.fps_n) / m.fps_d : 0.0;
    int tier = 0;
    if (m.width == 1920 && m.height == 1080) {
      tier = 300;
    } else if (m.width == 2560 && m.height == 1440) {
      tier = 200;
    } else if (pixels < 3840 * 2160) {
      tier = 100;
    } else {
      tier = 50;
    }
    const int fps_closeness = 100 - std::abs(static_cast<int>(fps) - 30);
    return tier * 1000 + fps_closeness;
  };
  const CaptureMode* best = &modes.front();
  for (const auto& m : modes) {
    if (score_default(m) > score_default(*best)) {
      best = &m;
    }
  }
  return best->key();
}

}  // namespace capture::camera_worker
