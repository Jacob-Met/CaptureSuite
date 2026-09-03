// SPDX-License-Identifier: GPL-3.0-only
#include "radar_worker/capture_pipeline.hpp"

#include "capture/v1/common.pb.h"
#include "capture/v1/data/radar_doppler.pb.h"
#include "capture/v1/data/radar_frame.pb.h"

#include <nlohmann/json.hpp>

#include <algorithm>
#include <fstream>

#ifndef NOMINMAX
#define NOMINMAX
#endif
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <Windows.h>

namespace capture::radar_worker {
namespace {

constexpr int64_t kTimestampUncertaintyNs = 30'000'000;

std::string path_to_forward(const std::filesystem::path& p) {
  return p.generic_string();
}

}  // namespace

CapturePipeline::CapturePipeline() = default;

CapturePipeline::~CapturePipeline() {
  std::string err;
  stop(err);
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

double CapturePipeline::nominal_rate_hz() const {
  if (kind_ == BoardKind::Ltr11 && ltr11_ != nullptr) {
    return ltr11_->nominal_frame_rate_hz();
  }
  if (fmcw_ != nullptr) {
    return fmcw_->nominal_frame_rate_hz();
  }
  return 0.0;
}

std::string CapturePipeline::configuration_hash() const {
  if (kind_ == BoardKind::Ltr11 && ltr11_ != nullptr) {
    return ltr11_->configuration_hash();
  }
  if (fmcw_ != nullptr) {
    return fmcw_->configuration_hash();
  }
  return {};
}

bool CapturePipeline::prepare(const std::string& source_id, BoardKind kind,
                              IfxFmcwDevice* fmcw, IfxLtr11Device* ltr11,
                              std::string& error) {
  if (running_.load()) {
    error = "already running";
    return false;
  }
  if (kind == BoardKind::Fmcw) {
    if (fmcw == nullptr || !fmcw->is_open()) {
      error = "FMCW device not open";
      return false;
    }
  } else if (ltr11 == nullptr || !ltr11->is_open()) {
    error = "LTR11 device not open";
    return false;
  }
  source_id_ = source_id;
  stream_id_ = source_id + ".frame";
  kind_ = kind;
  fmcw_ = fmcw;
  ltr11_ = ltr11;
  {
    std::lock_guard lock(mu_);
    preview_view_ =
        kind == BoardKind::Ltr11 ? "motion_trace" : "range_doppler";
    spectrogram_rows_.clear();
    spectrogram_display_max_ = 1.0f;
  }
  return true;
}

void CapturePipeline::set_preview_view(std::string view) {
  std::lock_guard lock(mu_);
  if (view.empty()) {
    view = kind_ == BoardKind::Ltr11 ? "motion_trace" : "range_doppler";
  }
  if (view == preview_view_) {
    return;
  }
  preview_view_ = std::move(view);
  spectrogram_rows_.clear();
  spectrogram_display_max_ = 1.0f;
}

std::string CapturePipeline::preview_view() const {
  std::lock_guard lock(mu_);
  return preview_view_;
}

bool CapturePipeline::write_stream_json(std::string& error) const {
  const auto stream_dir =
      start_cfg_.package_path / "sources" / source_id_ / "streams" / stream_id_;
  std::error_code ec;
  std::filesystem::create_directories(stream_dir, ec);
  if (ec) {
    error = "failed to create stream directory";
    return false;
  }
  nlohmann::json cfg;
  try {
    if (kind_ == BoardKind::Ltr11 && ltr11_ != nullptr) {
      cfg = nlohmann::json::parse(ltr11_->config_json());
    } else if (fmcw_ != nullptr) {
      cfg = nlohmann::json::parse(fmcw_->config_json());
    }
  } catch (...) {
    cfg = nlohmann::json::object();
  }

  nlohmann::json j;
  if (kind_ == BoardKind::Ltr11) {
    j = {{"schema", "capture.stream/1"},
         {"source_id", source_id_},
         {"stream_id", stream_id_},
         {"modality", "radar_doppler"},
         {"data_schema_id", "radar.doppler/1"},
         {"sample_encoding", "complex_float32_le"},
         {"configuration_hash", configuration_hash()},
         {"configuration", cfg},
         {"nominal_rate_hz", nominal_rate_hz()},
         {"record_stack", "ifx_ltr11"}};
  } else {
    j = {{"schema", "capture.stream/1"},
         {"source_id", source_id_},
         {"stream_id", stream_id_},
         {"modality", "radar"},
         {"data_schema_id", "radar.frame/1"},
         {"sample_encoding", "uint16_le_raw_interleaved"},
         {"configuration_hash", configuration_hash()},
         {"configuration", cfg},
         {"nominal_rate_hz", nominal_rate_hz()},
         {"record_stack", "ifx_fmcw"}};
  }
  const auto path = stream_dir / "stream.json";
  std::ofstream out(path, std::ios::binary | std::ios::trunc);
  if (!out) {
    error = "failed to write stream.json";
    return false;
  }
  out << j.dump(2);
  return true;
}

bool CapturePipeline::start(const CaptureStartConfig& cfg, std::string& error) {
  if (running_.load()) {
    error = "already running";
    return false;
  }
  if ((kind_ == BoardKind::Fmcw && fmcw_ == nullptr) ||
      (kind_ == BoardKind::Ltr11 && ltr11_ == nullptr)) {
    error = "prepare() not called";
    return false;
  }
  start_cfg_ = cfg;
  segments_dir_ = start_cfg_.package_path / "sources" / source_id_ / "streams" /
                  stream_id_ / "segments";
  std::error_code ec;
  std::filesystem::create_directories(segments_dir_, ec);
  if (ec) {
    error = "failed to create segments directory";
    return false;
  }

  capture::storage::StreamWriterConfig wcfg;
  wcfg.source_id = source_id_;
  wcfg.stream_id = stream_id_;
  if (kind_ == BoardKind::Ltr11) {
    wcfg.modality = "radar_doppler";
    wcfg.data_schema_id = "radar.doppler/1";
  } else {
    wcfg.modality = "radar";
    wcfg.data_schema_id = "radar.frame/1";
  }
  wcfg.nominal_rate_hz = nominal_rate_hz();
  wcfg.compress = false;
  wcfg.max_batch_samples = 1;
  wcfg.max_batch_ns = 0;

  writer_.set_rotate_callback([this](const capture::storage::SealedSegmentInfo& info) {
    if (!on_segment_sealed_) {
      return;
    }
    capture::v1::SegmentSealed sealed;
    sealed.set_source_id(source_id_);
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

  if (!writer_.open(segments_dir_, start_cfg_.package_path, wcfg, error)) {
    return false;
  }

  std::string stream_err;
  if (!write_stream_json(stream_err)) {
    std::fprintf(stderr, "radar worker: %s\n", stream_err.c_str());
  }

  frame_index_ = 0;
  global_sequence_ = 0;
  last_frame_index_ = -1;
  failed_ = false;
  frames_in_window_ = 0;
  window_start_qpc_ns_ = 0;
  measured_rate_hz_ = 0;
  running_ = true;
  stop_threads_ = false;
  acquisition_thread_ = std::thread([this] { acquisition_loop(); });
  health_thread_ = std::thread([this] { health_loop(); });
  return true;
}

void CapturePipeline::handle_frame_error(IfxFrameError err) {
  if (err == IfxFrameError::Timeout) {
    return;
  }
  if (err == IfxFrameError::FifoOverflow) {
    failed_ = true;
    stop_threads_ = true;
    if (on_overload_) {
      on_overload_("IFX_ERROR_FIFO_OVERFLOW");
    }
    return;
  }
  if (err == IfxFrameError::CommunicationError) {
    failed_ = true;
    stop_threads_ = true;
    if (on_overload_) {
      on_overload_("IFX_ERROR_COMMUNICATION_ERROR");
    }
  }
}

void CapturePipeline::acquisition_loop() {
  if (kind_ == BoardKind::Ltr11) {
    acquisition_loop_ltr11();
  } else {
    acquisition_loop_fmcw();
  }
}

void CapturePipeline::acquisition_loop_fmcw() {
  std::vector<uint16_t> raw;
  int preview_skip = 0;
  const uint16_t timeout_ms = 5000;

  while (!stop_threads_.load()) {
    const int64_t host = now_qpc_ns();
    const IfxFrameError err = fmcw_->get_next_raw_frame(raw, timeout_ms);
    if (stop_threads_.load()) {
      break;
    }
    if (err == IfxFrameError::Timeout) {
      continue;
    }
    if (err != IfxFrameError::None) {
      handle_frame_error(err);
      break;
    }

    const int64_t session = session_ns_from_qpc(host);
    uint32_t quality = 0;
    if (last_frame_index_ >= 0 && frame_index_ != last_frame_index_ + 1) {
      quality |= static_cast<uint32_t>(
          capture::v1::QUALITY_FLAG_SEQUENCE_DISCONTINUITY);
    }
    last_frame_index_ = frame_index_;

    capture::v1::data::RadarFrame rf;
    auto* th = rf.mutable_timing();
    th->set_sequence_number(global_sequence_);
    th->set_device_index(frame_index_);
    th->set_device_timestamp(0);
    th->set_device_timestamp_unit("none");
    th->set_host_arrival_ns(host);
    th->set_session_time_ns(session);
    th->set_timestamp_uncertainty_ns(kTimestampUncertaintyNs);
    th->set_quality_flags(quality);
    rf.set_frame_index(frame_index_);
    rf.set_configuration_hash(fmcw_->configuration_hash());
    rf.set_num_rx(fmcw_->num_rx());
    rf.set_num_chirps(fmcw_->num_chirps());
    rf.set_num_samples(fmcw_->num_samples());
    rf.set_sample_encoding("uint16_le_raw_interleaved");
    rf.set_payload(raw.data(), raw.size() * sizeof(uint16_t));
    rf.set_quality_flags(quality);

    std::string payload;
    rf.SerializeToString(&payload);

    capture::storage::SamplePoint sample;
    sample.sequence = global_sequence_;
    sample.session_time_ns = session;
    sample.host_arrival_ns = host;
    sample.quality_flags = quality;
    sample.payload.assign(payload.begin(), payload.end());

    {
      std::lock_guard lock(mu_);
      std::string write_err;
      if (!writer_.append(sample, write_err) && on_overload_) {
        on_overload_("mcap write failed: " + write_err);
        failed_ = true;
        stop_threads_ = true;
        break;
      }
    }

    ++frame_index_;
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

    if (on_preview_ && (++preview_skip % 4) == 0) {
      emit_fmcw_preview(raw, session, global_sequence_);
    }
  }
}

void CapturePipeline::acquisition_loop_ltr11() {
  Ltr11FrameResult frame;
  int preview_skip = 0;
  const uint16_t timeout_ms = 5000;

  while (!stop_threads_.load()) {
    const int64_t host = now_qpc_ns();
    const IfxFrameError err = ltr11_->get_next_frame(frame, timeout_ms);
    if (stop_threads_.load()) {
      break;
    }
    if (err == IfxFrameError::Timeout) {
      continue;
    }
    if (err != IfxFrameError::None) {
      handle_frame_error(err);
      break;
    }

    const int64_t session = session_ns_from_qpc(host);
    uint32_t quality = 0;
    if (last_frame_index_ >= 0 && frame_index_ != last_frame_index_ + 1) {
      quality |= static_cast<uint32_t>(
          capture::v1::QUALITY_FLAG_SEQUENCE_DISCONTINUITY);
    }
    last_frame_index_ = frame_index_;

    capture::v1::data::RadarDopplerFrame rf;
    auto* th = rf.mutable_timing();
    th->set_sequence_number(global_sequence_);
    th->set_device_index(frame_index_);
    th->set_device_timestamp(0);
    th->set_device_timestamp_unit("none");
    th->set_host_arrival_ns(host);
    th->set_session_time_ns(session);
    th->set_timestamp_uncertainty_ns(kTimestampUncertaintyNs);
    th->set_quality_flags(quality);
    rf.set_frame_index(frame_index_);
    rf.set_configuration_hash(ltr11_->configuration_hash());
    rf.set_num_samples(frame.num_samples);
    rf.set_sample_encoding("complex_float32_le");
    rf.set_payload(frame.interleaved_iq.data(),
                   frame.interleaved_iq.size() * sizeof(float));
    rf.set_quality_flags(quality);
    rf.set_motion_detected(frame.motion_detected);
    rf.set_direction(frame.direction);

    std::string payload;
    rf.SerializeToString(&payload);

    capture::storage::SamplePoint sample;
    sample.sequence = global_sequence_;
    sample.session_time_ns = session;
    sample.host_arrival_ns = host;
    sample.quality_flags = quality;
    sample.payload.assign(payload.begin(), payload.end());

    {
      std::lock_guard lock(mu_);
      std::string write_err;
      if (!writer_.append(sample, write_err) && on_overload_) {
        on_overload_("mcap write failed: " + write_err);
        failed_ = true;
        stop_threads_ = true;
        break;
      }
    }

    ++frame_index_;
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

    if (on_preview_ && (++preview_skip % 4) == 0) {
      emit_ltr11_preview(frame, session, global_sequence_);
    }
  }
}

void CapturePipeline::health_loop() {
  while (!stop_threads_.load()) {
    if (on_health_) {
      capture::v1::HealthSnapshot hs;
      hs.set_source_id(source_id_);
      hs.set_lifecycle_state(failed_.load()
                                 ? capture::v1::SOURCE_LIFECYCLE_FAILED
                                 : capture::v1::SOURCE_LIFECYCLE_RECORDING);
      hs.set_health(failed_.load() ? capture::v1::HEALTH_LEVEL_ERROR
                                   : capture::v1::HEALTH_LEVEL_OK);
      hs.set_connected(!failed_.load());
      hs.set_data_arriving(measured_rate_hz_.load() > 0.1);
      hs.set_measured_rate_hz(measured_rate_hz_.load());
      hs.set_expected_rate_hz(nominal_rate_hz());
      hs.set_dropped_count(failed_.load() ? 1 : 0);
      hs.set_dropped_last_10s(0);
      hs.set_write_ok(!failed_.load());
      {
        std::lock_guard lock(mu_);
        hs.set_recorded_sample_count(writer_.total_samples());
        if (writer_.current_segment_index() >= 0) {
          char name[32];
          std::snprintf(name, sizeof(name), "%06d.mcap",
                        writer_.current_segment_index());
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

bool CapturePipeline::stop(std::string& error) {
  (void)error;
  if (!running_.exchange(false) && acquisition_thread_.joinable() == false) {
    return true;
  }
  stop_threads_ = true;
  if (acquisition_thread_.joinable()) {
    acquisition_thread_.join();
  }
  if (health_thread_.joinable()) {
    health_thread_.join();
  }
  std::string err;
  writer_.close(err);
  fmcw_ = nullptr;
  ltr11_ = nullptr;
  return true;
}

capture::v1::PreviewDescriptor CapturePipeline::preview_descriptor() const {
  capture::v1::PreviewDescriptor d;
  d.set_source_id(source_id_);
  d.set_stream_id(stream_id_);
  d.set_ring_slot_count(3);
  d.set_max_rate_hz(5.0);
  d.set_drop_policy(capture::v1::PREVIEW_DROP_POLICY_LATEST_WINS);
  d.set_enabled(true);
  const std::string view = preview_view();
  (*d.mutable_metadata())["preview_view"] = view;
  const bool matrix =
      view == "range_doppler" || view == "range_doppler_hd" ||
      view == "range_spectrogram" || view == "doppler_spectrogram";
  if (matrix) {
    d.set_kind(capture::v1::PREVIEW_KIND_MATRIX_2D);
    d.set_max_payload_bytes(128 * 128 * static_cast<uint32_t>(sizeof(float)));
    d.set_content_type("application/x-capture-matrix");
  } else {
    d.set_kind(capture::v1::PREVIEW_KIND_TRACE_BLOCK);
    d.set_max_payload_bytes(128 * static_cast<uint32_t>(sizeof(float)));
    d.set_content_type("application/x-capture-trace");
  }
  return d;
}

void CapturePipeline::push_spectrogram_row(const std::vector<float>& row,
                                           float display_max) {
  std::lock_guard lock(mu_);
  spectrogram_rows_.push_back(row);
  while (spectrogram_rows_.size() > kSpectrogramHistory) {
    spectrogram_rows_.pop_front();
  }
  spectrogram_display_max_ =
      (std::max)(spectrogram_display_max_ * 0.98f, display_max);
}

void CapturePipeline::emit_spectrogram_matrix(int64_t session, int64_t sequence,
                                              const char* row_axis,
                                              const char* col_axis) {
  if (!on_preview_) {
    return;
  }
  std::vector<float> values;
  uint32_t rows = 0;
  uint32_t cols = 0;
  float dmax = 1.0f;
  {
    std::lock_guard lock(mu_);
    if (spectrogram_rows_.empty()) {
      return;
    }
    rows = static_cast<uint32_t>(spectrogram_rows_.size());
    cols = static_cast<uint32_t>(spectrogram_rows_.front().size());
    values.assign(static_cast<size_t>(rows) * cols, 0.0f);
    uint32_t r = 0;
    for (const auto& row : spectrogram_rows_) {
      for (uint32_t c = 0; c < cols && c < row.size(); ++c) {
        values[static_cast<size_t>(r) * cols + c] = row[c];
      }
      ++r;
    }
    dmax = spectrogram_display_max_;
  }
  capture::v1::PreviewFrame frame;
  frame.set_source_id(source_id_);
  frame.set_stream_id(stream_id_);
  frame.set_kind(capture::v1::PREVIEW_KIND_MATRIX_2D);
  frame.set_session_time_ns(session);
  frame.set_sequence(sequence);
  auto* mat = frame.mutable_matrix();
  mat->set_rows(rows);
  mat->set_cols(cols);
  mat->set_display_min(0.0f);
  mat->set_display_max(dmax);
  mat->set_row_axis(row_axis);
  mat->set_col_axis(col_axis);
  for (float v : values) {
    mat->add_values(v);
  }
  on_preview_(frame);
}

void CapturePipeline::emit_fmcw_preview(const std::vector<uint16_t>& raw,
                                        int64_t session, int64_t sequence) {
  if (!on_preview_ || fmcw_ == nullptr) {
    return;
  }
  const std::string view = preview_view();
  std::string preview_err;
  if (view == "range_spectrum") {
    std::vector<float> spectrum;
    float dmin = 0.0f;
    float dmax = 1.0f;
    if (!fmcw_->compute_range_spectrum_preview(raw, spectrum, dmin, dmax,
                                               preview_err)) {
      return;
    }
    capture::v1::PreviewFrame frame;
    frame.set_source_id(source_id_);
    frame.set_stream_id(stream_id_);
    frame.set_kind(capture::v1::PREVIEW_KIND_TRACE_BLOCK);
    frame.set_session_time_ns(session);
    frame.set_sequence(sequence);
    auto* tr = frame.mutable_trace();
    tr->add_channel_names("range");
    tr->set_channel_count(1);
    tr->set_points_per_channel(static_cast<uint32_t>(spectrum.size()));
    tr->set_display_min(dmin);
    tr->set_display_max(dmax);
    tr->set_units("a.u.");
    tr->set_decimated_from_rate_hz(fmcw_->nominal_frame_rate_hz());
    for (float v : spectrum) {
      tr->add_samples(v);
    }
    on_preview_(frame);
    return;
  }
  if (view == "time_domain") {
    std::vector<float> samples;
    float dmin = 0.0f;
    float dmax = 1.0f;
    if (!fmcw_->compute_time_domain_preview(raw, samples, dmin, dmax,
                                            preview_err)) {
      return;
    }
    capture::v1::PreviewFrame frame;
    frame.set_source_id(source_id_);
    frame.set_stream_id(stream_id_);
    frame.set_kind(capture::v1::PREVIEW_KIND_TRACE_BLOCK);
    frame.set_session_time_ns(session);
    frame.set_sequence(sequence);
    auto* tr = frame.mutable_trace();
    tr->add_channel_names("if");
    tr->set_channel_count(1);
    tr->set_points_per_channel(static_cast<uint32_t>(samples.size()));
    tr->set_display_min(dmin);
    tr->set_display_max(dmax);
    tr->set_units("a.u.");
    tr->set_decimated_from_rate_hz(fmcw_->nominal_frame_rate_hz());
    for (float v : samples) {
      tr->add_samples(v);
    }
    on_preview_(frame);
    return;
  }
  if (view == "range_spectrogram") {
    std::vector<float> spectrum;
    float dmin = 0.0f;
    float dmax = 1.0f;
    if (!fmcw_->compute_range_spectrum_preview(raw, spectrum, dmin, dmax,
                                               preview_err)) {
      return;
    }
    push_spectrogram_row(spectrum, dmax);
    emit_spectrogram_matrix(session, sequence, "time", "range");
    return;
  }

  // Default: range_doppler. The HD variant zero-pads both FFTs so the same
  // 64×32 of real information is rendered on a 128×128 interpolated grid.
  const bool hd = view == "range_doppler_hd";
  std::vector<float> matrix;
  uint32_t rows = 0;
  uint32_t cols = 0;
  float dmin = 0.0f;
  float dmax = 1.0f;
  if (!fmcw_->compute_range_doppler_preview(raw, hd ? 256 : 128, hd ? 128 : 64,
                                            matrix, rows, cols, dmin, dmax,
                                            preview_err)) {
    return;
  }
  capture::v1::PreviewFrame frame;
  frame.set_source_id(source_id_);
  frame.set_stream_id(stream_id_);
  frame.set_kind(capture::v1::PREVIEW_KIND_MATRIX_2D);
  frame.set_session_time_ns(session);
  frame.set_sequence(sequence);
  auto* mat = frame.mutable_matrix();
  mat->set_rows(rows);
  mat->set_cols(cols);
  mat->set_display_min(dmin);
  mat->set_display_max(dmax);
  mat->set_row_axis("range");
  mat->set_col_axis("doppler");
  for (float v : matrix) {
    mat->add_values(v);
  }
  on_preview_(frame);
}

void CapturePipeline::emit_ltr11_preview(const Ltr11FrameResult& frame,
                                         int64_t session, int64_t sequence) {
  if (!on_preview_ || ltr11_ == nullptr) {
    return;
  }
  const std::string view = preview_view();
  std::string preview_err;
  if (view == "doppler_spectrogram") {
    std::vector<float> spectrum;
    float dmin = 0.0f;
    float dmax = 1.0f;
    if (!ltr11_->compute_doppler_spectrum_preview(frame, spectrum, dmin, dmax,
                                                  preview_err)) {
      return;
    }
    push_spectrogram_row(spectrum, dmax);
    emit_spectrogram_matrix(session, sequence, "time", "doppler");
    return;
  }

  std::vector<float> trace;
  float dmin = 0.0f;
  float dmax = 1.0f;
  if (!ltr11_->compute_magnitude_trace_preview(frame, trace, dmin, dmax,
                                               preview_err)) {
    return;
  }
  capture::v1::PreviewFrame pf;
  pf.set_source_id(source_id_);
  pf.set_stream_id(stream_id_);
  pf.set_kind(capture::v1::PREVIEW_KIND_TRACE_BLOCK);
  pf.set_session_time_ns(session);
  pf.set_sequence(sequence);
  auto* tr = pf.mutable_trace();
  tr->add_channel_names("magnitude");
  tr->set_channel_count(1);
  tr->set_points_per_channel(static_cast<uint32_t>(trace.size()));
  tr->set_display_min(dmin);
  tr->set_display_max(dmax);
  tr->set_units("a.u.");
  tr->set_decimated_from_rate_hz(ltr11_->nominal_frame_rate_hz());
  for (float v : trace) {
    tr->add_samples(v);
  }
  on_preview_(pf);
}

}  // namespace capture::radar_worker

