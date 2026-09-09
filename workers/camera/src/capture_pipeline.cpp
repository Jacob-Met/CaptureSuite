// SPDX-License-Identifier: GPL-3.0-only
#include "camera_worker/capture_pipeline.hpp"

#include "capture/env.hpp"

#include "capture/storage/hash.hpp"
#include "capture/v1/data/video_timing.pb.h"

#include <gst/app/gstappsink.h>
#include <gst/gst.h>
#include <gst/video/video.h>

#include <nlohmann/json.hpp>

#include <fstream>

#ifndef NOMINMAX
#define NOMINMAX
#endif
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <Windows.h>

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstring>

namespace capture::camera_worker {
namespace {

gboolean link_many(GstElement* a, GstElement* b, GstElement* c = nullptr,
                   GstElement* d = nullptr, GstElement* e = nullptr,
                   GstElement* f = nullptr) {
  if (!gst_element_link(a, b)) {
    return FALSE;
  }
  if (c && !gst_element_link(b, c)) {
    return FALSE;
  }
  if (d && !gst_element_link(c, d)) {
    return FALSE;
  }
  if (e && !gst_element_link(d, e)) {
    return FALSE;
  }
  if (f && !gst_element_link(e, f)) {
    return FALSE;
  }
  return TRUE;
}

gchar* format_location_trampoline(GstElement* /*splitmux*/, guint fragment_id,
                                  GstSample* /*sample*/, gpointer user_data) {
  auto* self = static_cast<CapturePipeline*>(user_data);
  return self->format_location(fragment_id);
}

GstPadProbeReturn record_probe_trampoline(GstPad* /*pad*/,
                                          GstPadProbeInfo* info,
                                          gpointer user_data) {
  if ((info->type & GST_PAD_PROBE_TYPE_BUFFER) == 0) {
    return GST_PAD_PROBE_OK;
  }
  auto* self = static_cast<CapturePipeline*>(user_data);
  self->on_record_buffer(GST_PAD_PROBE_INFO_BUFFER(info));
  return GST_PAD_PROBE_OK;
}

std::string path_to_forward(const std::filesystem::path& p) {
  return p.generic_string();
}

gboolean link_tee_branch(GstElement* tee, GstElement* sink_elem) {
  GstPad* tee_src = gst_element_request_pad_simple(tee, "src_%u");
  GstPad* sink_pad = gst_element_get_static_pad(sink_elem, "sink");
  if (tee_src == nullptr || sink_pad == nullptr) {
    if (tee_src) {
      gst_object_unref(tee_src);
    }
    if (sink_pad) {
      gst_object_unref(sink_pad);
    }
    return FALSE;
  }
  const GstPadLinkReturn link_ret = gst_pad_link(tee_src, sink_pad);
  gst_object_unref(tee_src);
  gst_object_unref(sink_pad);
  return GST_PAD_LINK_FAILED(link_ret) ? FALSE : TRUE;
}

void on_queue_overrun(GstElement*, gpointer user_data) {
  auto* self = static_cast<CapturePipeline*>(user_data);
  if (self) {
    self->notify_overload("record queue overrun");
  }
}

// A factory existing does not mean the encoder can be configured: hardware
// encoders routinely fail at set_format over driver/preset mismatches, so run
// a couple of frames through the candidate before committing to it.
bool encoder_usable(const char* name) {
  GstElement* pipeline = gst_pipeline_new("enc-probe");
  GstElement* src = gst_element_factory_make("videotestsrc", nullptr);
  GstElement* conv = gst_element_factory_make("videoconvert", nullptr);
  GstElement* enc = gst_element_factory_make(name, nullptr);
  GstElement* sink = gst_element_factory_make("fakesink", nullptr);
  if (!pipeline || !src || !conv || !enc || !sink) {
    for (GstElement* e : {src, conv, enc, sink}) {
      if (e != nullptr) {
        gst_object_unref(e);
      }
    }
    if (pipeline != nullptr) {
      gst_object_unref(pipeline);
    }
    return false;
  }

  g_object_set(src, "num-buffers", 2, nullptr);
  g_object_set(sink, "sync", FALSE, nullptr);
  gst_bin_add_many(GST_BIN(pipeline), src, conv, enc, sink, nullptr);

  bool ok = gst_element_link_many(src, conv, enc, sink, nullptr) == TRUE;
  if (ok && gst_element_set_state(pipeline, GST_STATE_PLAYING) !=
                GST_STATE_CHANGE_FAILURE) {
    GstBus* bus = gst_element_get_bus(GST_ELEMENT(pipeline));
    GstMessage* msg = gst_bus_timed_pop_filtered(
        bus, 5 * GST_SECOND,
        static_cast<GstMessageType>(GST_MESSAGE_ERROR | GST_MESSAGE_EOS));
    ok = msg != nullptr && GST_MESSAGE_TYPE(msg) == GST_MESSAGE_EOS;
    if (msg != nullptr) {
      gst_message_unref(msg);
    }
    gst_object_unref(bus);
  } else {
    ok = false;
  }

  gst_element_set_state(pipeline, GST_STATE_NULL);
  gst_object_unref(pipeline);
  return ok;
}

// Ask the device what it can deliver. Queried in READY because mfvideosrc only
// probes the hardware once it has opened it.
void source_media_types(GstElement* src, bool& has_raw, bool& has_jpeg) {
  has_raw = false;
  has_jpeg = false;
  if (gst_element_set_state(src, GST_STATE_READY) == GST_STATE_CHANGE_FAILURE) {
    return;
  }
  GstPad* pad = gst_element_get_static_pad(src, "src");
  if (pad != nullptr) {
    GstCaps* caps = gst_pad_query_caps(pad, nullptr);
    if (caps != nullptr) {
      for (guint i = 0; i < gst_caps_get_size(caps); ++i) {
        const gchar* name =
            gst_structure_get_name(gst_caps_get_structure(caps, i));
        if (name == nullptr) {
          continue;
        }
        if (g_str_has_prefix(name, "video/x-raw")) {
          has_raw = true;
        } else if (g_str_has_prefix(name, "image/jpeg")) {
          has_jpeg = true;
        }
      }
      gst_caps_unref(caps);
    }
    gst_object_unref(pad);
  }
  gst_element_set_state(src, GST_STATE_NULL);
}

}  // namespace

CapturePipeline::CapturePipeline() = default;

CapturePipeline::~CapturePipeline() {
  std::string err;
  stop(err);
}

std::string CapturePipeline::negotiated_caps() const {
  std::lock_guard lock(mu_);
  return negotiated_caps_;
}

int64_t CapturePipeline::now_qpc_ns() {
  LARGE_INTEGER freq{};
  LARGE_INTEGER counter{};
  QueryPerformanceFrequency(&freq);
  QueryPerformanceCounter(&counter);
  if (freq.QuadPart <= 0) {
    return 0;
  }
  return (counter.QuadPart * 1000000000LL) / freq.QuadPart;
}

int64_t CapturePipeline::session_ns_from_qpc(int64_t qpc_ns) const {
  if (start_cfg_.session_t0_qpc_ns == 0) {
    return qpc_ns;
  }
  return qpc_ns - start_cfg_.session_t0_qpc_ns;
}

bool CapturePipeline::prepare(const CameraDevice& device,
                              const CapturePipelineOptions& opts,
                              std::string& error) {
  if (running_.load()) {
    error = "already running";
    return false;
  }
  device_ = device;
  opts_ = opts;
  if (opts_.preview_max_rate_hz < 1.0) {
    opts_.preview_max_rate_hz = 1.0;
  }
  if (opts_.preview_max_rate_hz > 30.0) {
    opts_.preview_max_rate_hz = 30.0;
  }
  stream_id_ = device.source_id + ".video";
  return choose_encoder(error);
}

const char* CapturePipeline::encode_mode_name(EncodeMode mode) {
  switch (mode) {
    case EncodeMode::Passthrough:
      return "passthrough";
    case EncodeMode::EncodeRaw:
      return "encode_raw";
    case EncodeMode::EncodeTranscoded:
      return "encode_transcoded";
  }
  return "unknown";
}

std::string CapturePipeline::probe_preferred_encoder() {
  // Probing costs a pipeline round-trip per candidate, and the answer cannot
  // change while the process lives.
  static const std::string cached = []() -> std::string {
    const bool use_fake = capture::env::enabled("CAPTURE_CAMERA_FAKE");
    if (use_fake && encoder_usable("x264enc")) {
      return "x264enc";
    }
    const char* candidates[] = {"nvh264enc", "qsvh264enc", "amfh264enc",
                                "mfh264enc", "x264enc"};
    for (const char* name : candidates) {
      if (encoder_usable(name)) {
        return name;
      }
      std::fprintf(stderr, "camera worker: encoder %s unusable, trying next\n",
                   name);
    }
    return {};
  }();
  return cached;
}

bool CapturePipeline::choose_encoder(std::string& error) {
  // Config preference first; CAPTURE_CAMERA_ENCODER is a developer override.
  std::string pref = opts_.encoder_preference;
  if (pref.empty() || pref == "auto") {
    const auto env = capture::env::get("CAPTURE_CAMERA_ENCODER");
    if (env.has_value() && !env->empty() && *env != "auto") {
      pref = *env;
    }
  }
  if (!pref.empty() && pref != "auto") {
    if (encoder_usable(pref.c_str())) {
      encoder_name_ = pref;
      return true;
    }
    std::fprintf(stderr,
                 "camera worker: preferred encoder %s unavailable, falling back\n",
                 pref.c_str());
  }
  encoder_name_ = probe_preferred_encoder();
  if (encoder_name_.empty()) {
    error = "no H.264 encoder element found (nv/qsv/amf/mf/x264)";
    return false;
  }
  return true;
}

bool CapturePipeline::build_pipeline(std::string& error) {
  teardown();

  pipeline_ = gst_pipeline_new("camera-capture");
  GstElement* src = nullptr;
  std::string src_media_type = "video/x-raw";
  if (capture::env::enabled("CAPTURE_CAMERA_FAKE")) {
    src = gst_element_factory_make("videotestsrc", "src");
    if (src) {
      g_object_set(src, "is-live", TRUE, "pattern", 0, "horizontal-speed", 1,
                   nullptr);
    }
    encode_mode_ = EncodeMode::EncodeRaw;
    if (!opts_.source_caps.empty()) {
      src_media_type = opts_.source_caps;
    }
  } else {
    src = gst_element_factory_make("mfvideosrc", "src");
    if (src) {
      g_object_set(src, "device-path", device_.symbolic_link.c_str(), nullptr);
      if (!opts_.source_caps.empty()) {
        // Operator-selected mode from ApplyConfig (CONFIGURATION_UI.md).
        src_media_type = opts_.source_caps;
        encode_mode_ = opts_.source_is_jpeg ? EncodeMode::EncodeTranscoded
                                            : EncodeMode::EncodeRaw;
      } else {
        // Record and preview both hang off one tee, so the tee has to carry a
        // format both can consume: prefer raw, and decode MJPEG-only devices
        // once, ahead of the tee.
        bool has_raw = false;
        bool has_jpeg = false;
        source_media_types(src, has_raw, has_jpeg);
        if (has_raw) {
          encode_mode_ = EncodeMode::EncodeRaw;
        } else if (has_jpeg) {
          encode_mode_ = EncodeMode::EncodeTranscoded;
          src_media_type = "image/jpeg";
        } else {
          error = "camera offers neither raw video nor MJPEG";
          teardown();
          return false;
        }
      }
    }
  }
  GstElement* src_caps = gst_element_factory_make("capsfilter", "src_caps");
  GstElement* tee = gst_element_factory_make("tee", "t");
  GstElement* q_rec = gst_element_factory_make("queue", "q_rec");
  GstElement* q_prev = gst_element_factory_make("queue", "q_prev");
  GstElement* enc = gst_element_factory_make(encoder_name_.c_str(), "enc");
  GstElement* parse = gst_element_factory_make("h264parse", "parse");
  GstElement* split = gst_element_factory_make("splitmuxsink", "split");
  GstElement* rate = gst_element_factory_make("videorate", "rate");
  GstElement* scale = gst_element_factory_make("videoscale", "scale");
  GstElement* conv_prev = gst_element_factory_make("videoconvert", "conv_prev");
  GstElement* prev_caps = gst_element_factory_make("capsfilter", "prev_caps");
  GstElement* jpeg = gst_element_factory_make("jpegenc", "jpeg");
  GstElement* sink = gst_element_factory_make("appsink", "preview");

  if (!pipeline_ || !src || !src_caps || !tee || !q_rec || !q_prev || !enc ||
      !parse || !split || !rate || !scale || !conv_prev || !prev_caps ||
      !jpeg || !sink) {
    error = "failed to create one or more GStreamer elements";
    teardown();
    return false;
  }

  record_queue_ = q_rec;
  appsink_ = sink;
  splitmux_ = split;
  preview_rate_ = rate;
  preview_caps_ = prev_caps;
  preview_jpeg_ = jpeg;

  g_object_set(q_rec, "max-size-buffers", 8, "max-size-bytes", 0,
               "max-size-time", (guint64)0, "leaky", 0, nullptr);
  g_object_set(q_prev, "max-size-buffers", 1, "max-size-bytes", 0,
               "max-size-time", (guint64)0, "leaky", 2, nullptr);  // downstream

  g_object_set(split, "max-size-bytes", (guint64)(512ull * 1024ull * 1024ull),
               "max-size-time", (guint64)(300ull * GST_SECOND),
               "send-keyframe-requests", TRUE, "muxer-factory", "matroskamux",
               nullptr);
  g_signal_connect(split, "format-location-full",
                   G_CALLBACK(format_location_trampoline), this);

  if (encoder_name_ == "x264enc") {
    // byte-stream=false (AVC) for matroskamux; zerolatency keeps live pipelines moving.
    g_object_set(enc, "speed-preset", 1 /* veryfast */, "tune", 0x4 /* zerolatency */,
                 "key-int-max",
                 (gint)std::max(1, (int)start_cfg_.nominal_fps), "bframes", 0,
                 "byte-stream", FALSE, nullptr);
  } else {
    // Hardware encoders: best-effort common props; ignore if unsupported.
    g_object_set(enc, "bitrate", 8000, nullptr);
  }
  g_object_set(parse, "config-interval", -1, nullptr);
  g_object_set(src_caps, "caps", gst_caps_from_string(src_media_type.c_str()),
               nullptr);

  // Size-only caps after videoscale so the preview branch cannot force the
  // camera/tee resolution (record must keep native mode).
  apply_preview_element_settings();
  g_object_set(sink, "emit-signals", FALSE, "sync", FALSE, "max-buffers", 1,
               "drop", TRUE, "caps",
               gst_caps_from_string("image/jpeg"), nullptr);

  GstElement* jpegdec = nullptr;
  GstElement* conv_rec = gst_element_factory_make("videoconvert", "conv_rec");
  if (encode_mode_ == EncodeMode::EncodeTranscoded) {
    jpegdec = gst_element_factory_make("jpegdec", "jpegdec");
    if (!jpegdec || !conv_rec) {
      error = "jpegdec/videoconvert missing for transcoded path";
      teardown();
      return false;
    }
  } else if (!conv_rec) {
    error = "videoconvert missing";
    teardown();
    return false;
  }

  gst_bin_add_many(GST_BIN(pipeline_), src, src_caps, tee, q_rec, q_prev,
                   nullptr);
  if (jpegdec) {
    gst_bin_add(GST_BIN(pipeline_), jpegdec);
  }
  gst_bin_add_many(GST_BIN(pipeline_), conv_rec, enc, parse, split, rate, scale,
                   conv_prev, prev_caps, jpeg, sink, nullptr);

  const bool src_linked = jpegdec ? link_many(src, src_caps, jpegdec, tee)
                                  : link_many(src, src_caps, tee);
  if (!src_linked) {
    error = "failed to link source to tee";
    teardown();
    return false;
  }
  if (!link_tee_branch(tee, q_rec)) {
    error = "failed to link tee to record queue";
    teardown();
    return false;
  }
  if (!link_many(q_rec, conv_rec, enc, parse, split)) {
    error = "failed to link record branch";
    teardown();
    return false;
  }
  if (!link_tee_branch(tee, q_prev) ||
      !link_many(q_prev, rate, scale, conv_prev, prev_caps, jpeg) ||
      !gst_element_link(jpeg, sink)) {
    error = "failed to link preview branch";
    teardown();
    return false;
  }

  GstPad* rec_src = gst_element_get_static_pad(q_rec, "src");
  if (rec_src) {
    gst_pad_add_probe(rec_src, GST_PAD_PROBE_TYPE_BUFFER,
                      record_probe_trampoline, this, nullptr);
    gst_object_unref(rec_src);
  }

  g_signal_connect(q_rec, "overrun", G_CALLBACK(on_queue_overrun), this);
  return true;
}

void CapturePipeline::notify_overload(const std::string& reason) {
  dropped_count_.fetch_add(1);
  if (on_overload_) {
    on_overload_(reason);
  }
}

bool CapturePipeline::write_stream_json(std::string& error) const {
  const auto stream_dir = start_cfg_.package_path / "sources" /
                          device_.source_id / "streams" / "video";
  std::error_code ec;
  std::filesystem::create_directories(stream_dir, ec);
  if (ec) {
    error = "failed to create stream directory";
    return false;
  }
  nlohmann::json j = {
      {"schema", "capture.stream/1"},
      {"source_id", device_.source_id},
      {"stream_id", stream_id_},
      {"modality", "video"},
      {"data_schema_id", "video.frame_timing/1"},
      {"container", "matroska"},
      {"codec", "h264"},
      {"encoder", encoder_name_},
      {"encode_mode", encode_mode_name(encode_mode_)},
      {"transcoded", encode_mode_ == EncodeMode::EncodeTranscoded},
      {"negotiated_caps", negotiated_caps_},
      {"nominal_rate_hz", start_cfg_.nominal_fps},
      {"record_stack", "gstreamer"},
  };
  const auto path = stream_dir / "stream.json";
  std::ofstream out(path, std::ios::binary | std::ios::trunc);
  if (!out) {
    error = "failed to write stream.json";
    return false;
  }
  out << j.dump(2);
  return true;
}

char* CapturePipeline::format_location(unsigned int fragment_id) {
  std::lock_guard lock(mu_);
  if (current_fragment_ >= 0 &&
      current_fragment_ != static_cast<int>(fragment_id)) {
    // Previous fragment is complete from splitmux's POV; seal MKV + timing.
    seal_mkv_segment(current_fragment_);
    std::string err;
    timing_writer_.close(err);
  }
  current_fragment_ = static_cast<int>(fragment_id);
  frame_index_in_segment_ = 0;
  segment_start_session_ns_ = -1;
  segment_end_session_ns_ = -1;
  segment_frame_count_ = 0;

  std::string err;
  if (!open_timing_segment(static_cast<int>(fragment_id), err)) {
    std::fprintf(stderr, "camera worker: timing open failed: %s\n", err.c_str());
  }

  char name[32];
  std::snprintf(name, sizeof(name), "%06u.mkv", fragment_id);
  const auto abs = segments_dir_ / name;
  // splitmuxsink on Windows is happier with forward slashes.
  const std::string loc = abs.generic_string();
  return g_strdup(loc.c_str());
}

bool CapturePipeline::open_timing_segment(int fragment_id, std::string& error) {
  capture::storage::StreamWriterConfig cfg;
  cfg.source_id = device_.source_id;
  cfg.stream_id = stream_id_;
  cfg.modality = "video";
  cfg.data_schema_id = "video.frame_timing/1";
  cfg.nominal_rate_hz = start_cfg_.nominal_fps;
  cfg.filename_suffix = ".timing.mcap";
  cfg.compress = false;
  cfg.external_rotation = true;
  cfg.max_batch_samples = 1;
  cfg.max_batch_ns = 0;

  timing_writer_.set_rotate_callback(
      [this](const capture::storage::SealedSegmentInfo& info) {
        if (!on_segment_sealed_) {
          return;
        }
        capture::v1::SegmentSealed sealed;
        sealed.set_source_id(device_.source_id);
        sealed.set_stream_id(stream_id_);
        sealed.set_path(path_to_forward(info.relative_path));
        sealed.set_size_bytes(info.size_bytes);
        sealed.set_hash_blake3_hex(info.hash_blake3_hex);
        sealed.set_start_session_time_ns(info.start_session_time_ns);
        sealed.set_end_session_time_ns(info.end_session_time_ns);
        sealed.set_actual_count(info.actual_count);
        sealed.set_segment_index(static_cast<uint32_t>(info.segment_index));
        on_segment_sealed_(sealed);
      });

  return timing_writer_.open(segments_dir_, start_cfg_.package_path, cfg, error,
                             fragment_id);
}

void CapturePipeline::seal_mkv_segment(int fragment_id) {
  char name[32];
  std::snprintf(name, sizeof(name), "%06d.mkv", fragment_id);
  const auto abs = segments_dir_ / name;
  if (!std::filesystem::exists(abs)) {
    return;
  }
  std::string hash_err;
  capture::v1::SegmentSealed sealed;
  sealed.set_source_id(device_.source_id);
  sealed.set_stream_id(stream_id_);
  sealed.set_path(path_to_forward(
      std::filesystem::relative(abs, start_cfg_.package_path)));
  sealed.set_size_bytes(
      static_cast<int64_t>(std::filesystem::file_size(abs)));
  sealed.set_hash_blake3_hex(capture::storage::blake3_file_hex(abs, hash_err));
  sealed.set_start_session_time_ns(
      segment_start_session_ns_ < 0 ? 0 : segment_start_session_ns_);
  sealed.set_end_session_time_ns(
      segment_end_session_ns_ < 0 ? 0 : segment_end_session_ns_);
  sealed.set_actual_count(segment_frame_count_);
  sealed.set_segment_index(static_cast<uint32_t>(fragment_id));
  if (on_segment_sealed_ && !sealed.hash_blake3_hex().empty()) {
    on_segment_sealed_(sealed);
  }
}

void CapturePipeline::on_record_buffer(void* buffer_ptr) {
  auto* buffer = static_cast<GstBuffer*>(buffer_ptr);
  if (buffer == nullptr || !running_.load()) {
    return;
  }
  const int64_t host = now_qpc_ns();
  const int64_t session = session_ns_from_qpc(host);
  const int64_t pts = GST_BUFFER_PTS_IS_VALID(buffer)
                          ? static_cast<int64_t>(GST_BUFFER_PTS(buffer))
                          : session;
  const bool keyframe = !GST_BUFFER_FLAG_IS_SET(buffer, GST_BUFFER_FLAG_DELTA_UNIT);
  const uint32_t bytes = static_cast<uint32_t>(gst_buffer_get_size(buffer));

  capture::v1::data::VideoFrameTiming timing;
  auto* th = timing.mutable_timing();
  th->set_sequence_number(global_sequence_);
  th->set_device_index(global_sequence_);
  th->set_device_timestamp(pts);
  th->set_device_timestamp_unit("ns");
  th->set_host_arrival_ns(host);
  th->set_session_time_ns(session);
  th->set_timestamp_uncertainty_ns(
      static_cast<int64_t>((1e9 / std::max(1.0, start_cfg_.nominal_fps)) / 2.0));
  timing.set_frame_index(frame_index_in_segment_);
  timing.set_segment_index(static_cast<uint32_t>(std::max(0, current_fragment_)));
  timing.set_pts_ns(pts);
  timing.set_keyframe(keyframe);
  timing.set_encoded_bytes(bytes);

  std::string payload;
  timing.SerializeToString(&payload);

  capture::storage::SamplePoint sample;
  sample.sequence = global_sequence_;
  sample.session_time_ns = session;
  sample.host_arrival_ns = host;
  sample.payload.assign(payload.begin(), payload.end());

  {
    std::lock_guard lock(mu_);
    if (segment_start_session_ns_ < 0) {
      segment_start_session_ns_ = session;
    }
    segment_end_session_ns_ = session;
    ++segment_frame_count_;
    ++frame_index_in_segment_;
    ++global_sequence_;
    frames_in_window_.fetch_add(1);
    if (window_start_qpc_ns_.load() == 0) {
      window_start_qpc_ns_ = host;
    }
    const int64_t w0 = window_start_qpc_ns_.load();
    if (host - w0 >= 1000000000LL) {
      const int64_t n = frames_in_window_.exchange(0);
      measured_rate_hz_ = n * 1e9 / static_cast<double>(host - w0);
      window_start_qpc_ns_ = host;
    }
    std::string err;
    if (!timing_writer_.append(sample, err) && on_overload_) {
      on_overload_("timing write failed: " + err);
    }
  }
}

bool CapturePipeline::start(const CaptureStartConfig& cfg, std::string& error) {
  if (running_.load()) {
    error = "already running";
    return false;
  }
  if (device_.source_id.empty()) {
    error = "prepare() not called";
    return false;
  }
  start_cfg_ = cfg;
  segments_dir_ = start_cfg_.package_path / "sources" / device_.source_id /
                  "streams" / "video" / "segments";
  std::error_code ec;
  std::filesystem::create_directories(segments_dir_, ec);
  if (ec) {
    error = "failed to create segments directory";
    return false;
  }

  if (!build_pipeline(error)) {
    return false;
  }

  const GstStateChangeReturn ret =
      gst_element_set_state(GST_ELEMENT(pipeline_), GST_STATE_PLAYING);
  if (ret == GST_STATE_CHANGE_FAILURE) {
    error = "pipeline failed to reach PLAYING";
    teardown();
    return false;
  }

  // Capture negotiated caps after a short settle.
  GstState state = GST_STATE_NULL;
  gst_element_get_state(GST_ELEMENT(pipeline_), &state, nullptr, 2 * GST_SECOND);
  GstElement* src = gst_bin_get_by_name(GST_BIN(pipeline_), "src");
  if (src) {
    GstPad* pad = gst_element_get_static_pad(src, "src");
    if (pad) {
      GstCaps* caps = gst_pad_get_current_caps(pad);
      if (caps) {
        gchar* text = gst_caps_to_string(caps);
        if (text) {
          negotiated_caps_ = text;
          g_free(text);
        }
        gst_caps_unref(caps);
      }
      gst_object_unref(pad);
    }
    gst_object_unref(src);
  }

  std::string stream_err;
  if (!write_stream_json(stream_err)) {
    std::fprintf(stderr, "camera worker: %s\n", stream_err.c_str());
  }

  running_ = true;
  stop_threads_ = false;
  dropped_count_ = 0;
  frames_in_window_ = 0;
  window_start_qpc_ns_ = 0;
  measured_rate_hz_ = 0;
  preview_thread_ = std::thread([this] { preview_loop(); });
  bus_thread_ = std::thread([this] { bus_loop(); });
  health_thread_ = std::thread([this] { health_loop(); });
  return true;
}

bool CapturePipeline::stop(std::string& error) {
  (void)error;
  if (!running_.exchange(false) && pipeline_ == nullptr) {
    return true;
  }
  // Stop polling threads first so they do not race the EOS/NULL transition.
  stop_threads_ = true;
  if (preview_thread_.joinable()) {
    preview_thread_.join();
  }
  if (bus_thread_.joinable()) {
    bus_thread_.join();
  }
  if (health_thread_.joinable()) {
    health_thread_.join();
  }
  if (pipeline_) {
    // splitmuxsink / matroskamux only finalize the open fragment on EOS.
    // Dropping straight to NULL leaves a 0-byte .mkv with a populated timing
    // sidecar — which is exactly the multi-cam smoke failure we hit.
    gst_element_send_event(GST_ELEMENT(pipeline_), gst_event_new_eos());
    GstBus* bus = gst_element_get_bus(GST_ELEMENT(pipeline_));
    if (bus) {
      // Bound the wait: multi-cam Stop RPCs stop workers sequentially and must
      // stay inside the control-pipe timeout.
      GstMessage* msg = gst_bus_timed_pop_filtered(
          bus, 1500 * GST_MSECOND,
          static_cast<GstMessageType>(GST_MESSAGE_EOS | GST_MESSAGE_ERROR));
      if (msg) {
        gst_message_unref(msg);
      }
      gst_object_unref(bus);
    }
    gst_element_set_state(GST_ELEMENT(pipeline_), GST_STATE_NULL);
  }
  {
    std::lock_guard lock(mu_);
    if (current_fragment_ >= 0) {
      seal_mkv_segment(current_fragment_);
    }
    std::string err;
    timing_writer_.close(err);
    current_fragment_ = -1;
  }
  teardown();
  return true;
}

void CapturePipeline::teardown() {
  if (pipeline_) {
    gst_object_unref(pipeline_);
    pipeline_ = nullptr;
  }
  appsink_ = nullptr;
  splitmux_ = nullptr;
  record_queue_ = nullptr;
  preview_rate_ = nullptr;
  preview_caps_ = nullptr;
  preview_jpeg_ = nullptr;
}

void CapturePipeline::apply_preview_element_settings() {
  if (preview_rate_ == nullptr || preview_caps_ == nullptr ||
      preview_jpeg_ == nullptr) {
    return;
  }
  const int prev_w = opts_.preview_width > 0 ? opts_.preview_width : 320;
  const int prev_h = opts_.preview_height > 0 ? opts_.preview_height : 240;
  double rate = opts_.preview_max_rate_hz;
  if (rate < 1.0) {
    rate = 1.0;
  }
  if (rate > 30.0) {
    rate = 30.0;
  }
  g_object_set(GST_ELEMENT(preview_rate_), "max-rate",
               static_cast<gint>(std::lround(rate)), nullptr);
  {
    const std::string prev = "video/x-raw,width=" + std::to_string(prev_w) +
                             ",height=" + std::to_string(prev_h);
    GstCaps* caps = gst_caps_from_string(prev.c_str());
    g_object_set(GST_ELEMENT(preview_caps_), "caps", caps, nullptr);
    if (caps) {
      gst_caps_unref(caps);
    }
  }
  g_object_set(GST_ELEMENT(preview_jpeg_), "quality",
               opts_.preview_quality == "capture" ? 90 : 70, nullptr);
}

bool CapturePipeline::update_preview_options(const CapturePipelineOptions& opts,
                                             std::string& error) {
  if (pipeline_ == nullptr) {
    error = "pipeline not built";
    return false;
  }
  opts_.preview_enabled = opts.preview_enabled;
  opts_.preview_max_rate_hz = opts.preview_max_rate_hz;
  opts_.preview_quality = opts.preview_quality;
  opts_.preview_width = opts.preview_width > 0 ? opts.preview_width : 320;
  opts_.preview_height = opts.preview_height > 0 ? opts.preview_height : 240;
  apply_preview_element_settings();
  std::fprintf(stderr,
               "camera worker: preview updated quality=%s %dx%d max_rate=%.1f\n",
               opts_.preview_quality.c_str(), opts_.preview_width,
               opts_.preview_height, opts_.preview_max_rate_hz);
  return true;
}

void CapturePipeline::preview_loop() {
  while (!stop_threads_.load()) {
    if (appsink_ == nullptr) {
      Sleep(50);
      continue;
    }
    GstSample* sample = gst_app_sink_try_pull_sample(GST_APP_SINK(appsink_),
                                                     50 * GST_MSECOND);
    if (sample == nullptr) {
      continue;
    }
    GstBuffer* buffer = gst_sample_get_buffer(sample);
    GstCaps* caps = gst_sample_get_caps(sample);
    uint32_t width = 0;
    uint32_t height = 0;
    if (caps) {
      const GstStructure* s = gst_caps_get_structure(caps, 0);
      gint w = 0;
      gint h = 0;
      gst_structure_get_int(s, "width", &w);
      gst_structure_get_int(s, "height", &h);
      width = static_cast<uint32_t>(w);
      height = static_cast<uint32_t>(h);
    }
    if (buffer && on_preview_ && opts_.preview_enabled) {
      GstMapInfo map{};
      if (gst_buffer_map(buffer, &map, GST_MAP_READ)) {
        capture::v1::PreviewFrame frame;
        frame.set_source_id(device_.source_id);
        frame.set_stream_id(stream_id_);
        frame.set_kind(capture::v1::PREVIEW_KIND_IMAGE_THUMBNAIL);
        frame.set_session_time_ns(session_ns_from_qpc(now_qpc_ns()));
        frame.set_sequence(global_sequence_);
        auto* img = frame.mutable_image();
        img->set_data(map.data, map.size);
        img->set_width(width);
        img->set_height(height);
        img->set_pixel_format("jpeg");
        on_preview_(frame);
        gst_buffer_unmap(buffer, &map);
      }
    }
    gst_sample_unref(sample);
  }
}

void CapturePipeline::bus_loop() {
  if (pipeline_ == nullptr) {
    return;
  }
  GstBus* bus = gst_element_get_bus(GST_ELEMENT(pipeline_));
  while (!stop_threads_.load()) {
    GstMessage* msg = gst_bus_timed_pop(bus, 100 * GST_MSECOND);
    if (msg == nullptr) {
      continue;
    }
    if (GST_MESSAGE_TYPE(msg) == GST_MESSAGE_ERROR) {
      GError* err = nullptr;
      gchar* dbg = nullptr;
      gst_message_parse_error(msg, &err, &dbg);
      std::fprintf(stderr, "camera worker pipeline error: %s (%s)\n",
                   err ? err->message : "?", dbg ? dbg : "");
      if (err) {
        g_error_free(err);
      }
      g_free(dbg);
    }
    gst_message_unref(msg);
  }
  gst_object_unref(bus);
}

void CapturePipeline::health_loop() {
  while (!stop_threads_.load()) {
    if (on_health_) {
      capture::v1::HealthSnapshot hs;
      hs.set_source_id(device_.source_id);
      hs.set_lifecycle_state(capture::v1::SOURCE_LIFECYCLE_RECORDING);
      hs.set_health(dropped_count_.load() > 0
                        ? capture::v1::HEALTH_LEVEL_WARNING
                        : capture::v1::HEALTH_LEVEL_OK);
      hs.set_connected(true);
      hs.set_data_arriving(measured_rate_hz_.load() > 0.1);
      hs.set_measured_rate_hz(measured_rate_hz_.load());
      hs.set_expected_rate_hz(start_cfg_.nominal_fps);
      hs.set_dropped_count(dropped_count_.load());
      hs.set_dropped_last_10s(0);
      hs.set_write_ok(dropped_count_.load() == 0);
      {
        std::lock_guard lock(mu_);
        hs.set_recorded_sample_count(timing_writer_.total_samples());
        if (current_fragment_ >= 0) {
          char name[32];
          std::snprintf(name, sizeof(name), "%06d.mkv", current_fragment_);
          hs.set_current_segment(name);
        }
      }
      hs.set_session_time_ns(session_ns_from_qpc(now_qpc_ns()));
      on_health_(hs);
    }
    for (int i = 0; i < 10 && !stop_threads_.load(); ++i) {
      Sleep(100);
    }
  }
}

capture::v1::PreviewDescriptor CapturePipeline::preview_descriptor() const {
  capture::v1::PreviewDescriptor d;
  d.set_source_id(device_.source_id);
  d.set_stream_id(stream_id_);
  d.set_kind(capture::v1::PREVIEW_KIND_IMAGE_THUMBNAIL);
  d.set_ring_slot_count(3);
  d.set_max_payload_bytes(256 * 1024);
  d.set_max_rate_hz(15.0);
  d.set_drop_policy(capture::v1::PREVIEW_DROP_POLICY_LATEST_WINS);
  d.set_content_type("image/jpeg");
  d.set_enabled(true);
  return d;
}

}  // namespace capture::camera_worker
