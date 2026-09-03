// SPDX-License-Identifier: GPL-3.0-only
#include "radar_worker/ifx_device.hpp"

#include "capture/storage/hash.hpp"

#include <ifxBase/Cube.h>
#include <ifxBase/Error.h>
#include <ifxBase/List.h>
#include <ifxBase/Version.h>
#include <ifxFmcw/DeviceFmcw.h>
#include <ifxFmcw/DeviceFmcwTypes.h>
#include <ifxLtr11/DeviceLtr11.h>
#include <ifxLtr11/DeviceLtr11Types.h>
#include <ifxRadarDeviceCommon/RadarDeviceCommon.h>

#include <nlohmann/json.hpp>

#include <algorithm>
#include <cmath>
#include <complex>
#include <cstdio>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <numeric>

#ifndef _USE_MATH_DEFINES
#define _USE_MATH_DEFINES
#endif

namespace capture::radar_worker {
namespace {

// Standard preview grid: 64 range bins × 64 Doppler bins. The HD view asks
// compute_range_doppler_matrix() for a larger FFT directly.
constexpr uint32_t kPreviewRangeFft = 128;
constexpr uint32_t kPreviewDopplerFft = 64;

ifx_Error_t peek_ifx_error() { return ifx_error_get_and_clear(); }

std::string ifx_error_message(ifx_Error_t code) {
  switch (code) {
    case IFX_OK:
      return "ok";
    case IFX_ERROR_FIFO_OVERFLOW:
      return "IFX_ERROR_FIFO_OVERFLOW";
    case IFX_ERROR_COMMUNICATION_ERROR:
      return "IFX_ERROR_COMMUNICATION_ERROR";
    case IFX_ERROR_TIMEOUT:
      return "IFX_ERROR_TIMEOUT";
    default:
      return "ifx_error=" + std::to_string(static_cast<int>(code));
  }
}

IfxFrameError map_ifx_error(ifx_Error_t code) {
  if (code == IFX_OK) {
    return IfxFrameError::None;
  }
  if (code == IFX_ERROR_TIMEOUT) {
    return IfxFrameError::Timeout;
  }
  if (code == IFX_ERROR_FIFO_OVERFLOW) {
    return IfxFrameError::FifoOverflow;
  }
  if (code == IFX_ERROR_COMMUNICATION_ERROR) {
    return IfxFrameError::CommunicationError;
  }
  return IfxFrameError::Other;
}

std::string hex_prefix(const std::string& uuid, std::size_t n = 12) {
  std::string hex;
  hex.reserve(32);
  for (char c : uuid) {
    if (c != '-') {
      hex.push_back(static_cast<char>(std::tolower(static_cast<unsigned char>(c))));
    }
  }
  if (hex.size() > n) {
    hex.resize(n);
  }
  return hex;
}

void fft_inplace(std::vector<std::complex<float>>& data) {
  const std::size_t n = data.size();
  if (n < 2 || (n & (n - 1)) != 0) {
    return;
  }
  for (std::size_t i = 1, j = 0; i < n; ++i) {
    std::size_t bit = n >> 1;
    for (; j & bit; bit >>= 1) {
      j ^= bit;
    }
    j ^= bit;
    if (i < j) {
      std::swap(data[i], data[j]);
    }
  }
  for (std::size_t len = 2; len <= n; len <<= 1) {
    const float ang =
        -2.0f * 3.14159265358979323846f / static_cast<float>(len);
    const std::complex<float> wlen(std::cos(ang), std::sin(ang));
    for (std::size_t i = 0; i < n; i += len) {
      std::complex<float> w(1.0f, 0.0f);
      for (std::size_t j = 0; j < len / 2; ++j) {
        const auto u = data[i + j];
        const auto v = data[i + j + len / 2] * w;
        data[i + j] = u + v;
        data[i + j + len / 2] = u - v;
        w *= wlen;
      }
    }
  }
}

uint32_t next_pow2_at_least(uint32_t requested, uint32_t minimum) {
  uint32_t n = 2;
  while (n < minimum || n < requested) {
    n <<= 1;
  }
  return n;
}

std::vector<float> hann_window(uint32_t n) {
  std::vector<float> w(n, 1.0f);
  if (n < 2) {
    return w;
  }
  for (uint32_t i = 0; i < n; ++i) {
    w[i] = 0.5f - 0.5f * std::cos(2.0f * 3.14159265358979323846f *
                                  static_cast<float>(i) /
                                  static_cast<float>(n - 1));
  }
  return w;
}

float cube_value(const ifx_Mda_R_t* cube, uint32_t chirp, uint32_t sample) {
  const uint32_t rows = IFX_CUBE_ROWS(cube);
  const uint32_t cols = IFX_CUBE_COLS(cube);
  const uint32_t slices = IFX_CUBE_SLICES(cube);
  if (rows >= chirp + 1 && cols >= 1 && slices >= sample + 1) {
    return IFX_CUBE_AT(cube, chirp, 0, sample);
  }
  if (rows >= 1 && cols >= chirp + 1 && slices >= sample + 1) {
    return IFX_CUBE_AT(cube, 0, chirp, sample);
  }
  return 0.0f;
}

}  // namespace

std::string source_id_from_uuid(const std::string& uuid) {
  return "radar." + hex_prefix(uuid);
}

std::vector<BoardInfo> enumerate_fmcw_boards() {
  std::vector<BoardInfo> boards;
  ifx_List_t* list = ifx_fmcw_get_list();
  if (list == nullptr) {
    (void)peek_ifx_error();
    return boards;
  }
  const size_t count = ifx_list_size(list);
  for (size_t i = 0; i < count; ++i) {
    auto* entry =
        static_cast<ifx_Radar_Sensor_List_Entry_t*>(ifx_list_get(list, i));
    if (entry == nullptr || entry->uuid[0] == '\0') {
      continue;
    }
    BoardInfo info;
    info.kind = BoardKind::Fmcw;
    info.uuid = entry->uuid;
    info.sensor_description = "BGT60TR13C";
    info.num_rx = 3;
    info.adc_bits = 12;
    boards.push_back(std::move(info));
  }
  ifx_list_destroy(list);
  return boards;
}

IfxFmcwDevice::~IfxFmcwDevice() { close(); }

bool IfxFmcwDevice::open(const std::string& uuid, std::string& error) {
  close();
  if (uuid.empty()) {
    error = "uuid required";
    return false;
  }
  handle_ = ifx_fmcw_create_by_uuid(uuid.c_str());
  if (handle_ == nullptr) {
    const auto code = peek_ifx_error();
    error = "ifx_fmcw_create_by_uuid failed: " + ifx_error_message(code);
    return false;
  }
  uuid_ = uuid;
  const auto* sensor =
      ifx_fmcw_get_sensor_information(static_cast<ifx_Device_Fmcw_t*>(handle_));
  if (sensor != nullptr) {
    num_rx_ = sensor->num_rx_antennas;
  }
  // Frame buffers are sized from the acquisition sequence; allocate in
  // apply_sequence after set_acquisition_sequence.
  return true;
}

bool IfxFmcwDevice::allocate_frames(std::string& error) {
  if (raw_frame_ != nullptr) {
    ifx_fmcw_destroy_raw_frame(static_cast<ifx_Fmcw_Raw_Frame_t*>(raw_frame_));
    raw_frame_ = nullptr;
  }
  if (float_frame_ != nullptr) {
    ifx_fmcw_destroy_frame(static_cast<ifx_Fmcw_Frame_t*>(float_frame_));
    float_frame_ = nullptr;
  }
  raw_frame_ =
      ifx_fmcw_allocate_raw_frame(static_cast<ifx_Device_Fmcw_t*>(handle_));
  float_frame_ =
      ifx_fmcw_allocate_frame(static_cast<ifx_Device_Fmcw_t*>(handle_));
  if (raw_frame_ == nullptr || float_frame_ == nullptr) {
    error = "failed to allocate frame buffers";
    return false;
  }
  return true;
}

void IfxFmcwDevice::close() {
  destroy_sequence();
  if (raw_frame_ != nullptr) {
    ifx_fmcw_destroy_raw_frame(static_cast<ifx_Fmcw_Raw_Frame_t*>(raw_frame_));
    raw_frame_ = nullptr;
  }
  if (float_frame_ != nullptr) {
    ifx_fmcw_destroy_frame(static_cast<ifx_Fmcw_Frame_t*>(float_frame_));
    float_frame_ = nullptr;
  }
  if (handle_ != nullptr) {
    ifx_fmcw_destroy(static_cast<ifx_Device_Fmcw_t*>(handle_));
    handle_ = nullptr;
  }
  uuid_.clear();
}

void IfxFmcwDevice::destroy_sequence() {
  if (sequence_ != nullptr) {
    ifx_fmcw_destroy_sequence(
        static_cast<ifx_Fmcw_Sequence_Element_t*>(sequence_));
    sequence_ = nullptr;
  }
}

bool IfxFmcwDevice::apply_sequence(const FmcwSequenceConfig& cfg,
                                   std::string& error) {
  if (handle_ == nullptr) {
    error = "device not open";
    return false;
  }
  FmcwSequenceConfig req = cfg;
  if (req.frame_repetition_time_s <= 0.0) {
    req.frame_repetition_time_s = 0.05;
  }
  if (req.chirp_repetition_time_s <= 0.0) {
    req.chirp_repetition_time_s = 500e-6;
  }
  if (req.num_chirps == 0) {
    req.num_chirps = 32;
  }
  if (req.num_samples == 0) {
    req.num_samples = 128;
  }
  if (req.end_frequency_Hz <= req.start_frequency_Hz) {
    error = "end_frequency_Hz must be greater than start_frequency_Hz";
    return false;
  }
  requested_ = req;
  frame_repetition_time_s_ = req.frame_repetition_time_s;
  nominal_frame_rate_hz_ = 1.0 / frame_repetition_time_s_;

  destroy_sequence();

  ifx_Fmcw_Simple_Sequence_Config_t sdk{};
  sdk.frame_repetition_time_s =
      static_cast<float>(req.frame_repetition_time_s);
  sdk.chirp_repetition_time_s =
      static_cast<float>(req.chirp_repetition_time_s);
  sdk.num_chirps = req.num_chirps;
  sdk.tdm_mimo = false;
  sdk.chirp.start_frequency_Hz = req.start_frequency_Hz;
  sdk.chirp.end_frequency_Hz = req.end_frequency_Hz;
  sdk.chirp.sample_rate_Hz = static_cast<float>(req.sample_rate_Hz);
  sdk.chirp.num_samples = req.num_samples;
  sdk.chirp.rx_mask = static_cast<uint8_t>(req.rx_mask & 0xffu);
  sdk.chirp.tx_mask = static_cast<uint8_t>(req.tx_mask & 0xffu);
  sdk.chirp.tx_power_level = static_cast<uint8_t>(req.tx_power_level & 0xffu);
  sdk.chirp.lp_cutoff_Hz = static_cast<int32_t>(req.lp_cutoff_Hz);
  sdk.chirp.hp_cutoff_Hz = static_cast<int32_t>(req.hp_cutoff_Hz);
  sdk.chirp.if_gain_dB = static_cast<int8_t>(req.if_gain_dB);

  sequence_ = ifx_fmcw_create_simple_sequence(&sdk);
  if (sequence_ == nullptr) {
    error = "ifx_fmcw_create_simple_sequence failed";
    return false;
  }
  ifx_fmcw_set_acquisition_sequence(
      static_cast<ifx_Device_Fmcw_t*>(handle_),
      static_cast<ifx_Fmcw_Sequence_Element_t*>(sequence_));
  const auto code = peek_ifx_error();
  if (code != IFX_OK) {
    error = "set_acquisition_sequence: " + ifx_error_message(code);
    return false;
  }
  if (!allocate_frames(error)) {
    return false;
  }
  if (!refresh_geometry(error)) {
    return false;
  }
  return build_config_snapshot(error);
}

bool IfxFmcwDevice::refresh_geometry(std::string& error) {
  (void)error;
  num_chirps_ = 32;
  num_samples_ = 128;
  auto* seq = ifx_fmcw_get_acquisition_sequence(
      static_cast<ifx_Device_Fmcw_t*>(handle_));
  if (seq == nullptr) {
    return true;
  }
  ifx_Fmcw_Simple_Sequence_Config_t* simple =
      ifx_fmcw_get_simple_sequence_config(seq);
  if (simple != nullptr) {
    num_chirps_ = simple->num_chirps;
    num_samples_ = simple->chirp.num_samples;
    frame_repetition_time_s_ = simple->frame_repetition_time_s;
    if (frame_repetition_time_s_ > 0.0) {
      nominal_frame_rate_hz_ = 1.0 / frame_repetition_time_s_;
    }
    free(simple);
  }
  return true;
}

bool IfxFmcwDevice::build_config_snapshot(std::string& error) {
  (void)error;
  nlohmann::json requested = {
      {"frame_repetition_time_s", requested_.frame_repetition_time_s},
      {"chirp_repetition_time_s", requested_.chirp_repetition_time_s},
      {"num_chirps", requested_.num_chirps},
      {"tdm_mimo", false},
      {"chirp",
       {{"start_frequency_Hz", requested_.start_frequency_Hz},
        {"end_frequency_Hz", requested_.end_frequency_Hz},
        {"sample_rate_Hz", requested_.sample_rate_Hz},
        {"num_samples", requested_.num_samples},
        {"rx_mask", requested_.rx_mask},
        {"tx_mask", requested_.tx_mask},
        {"tx_power_level", requested_.tx_power_level},
        {"lp_cutoff_Hz", requested_.lp_cutoff_Hz},
        {"hp_cutoff_Hz", requested_.hp_cutoff_Hz},
        {"if_gain_dB", requested_.if_gain_dB}}}};

  nlohmann::json applied = requested;
  auto* seq = ifx_fmcw_get_acquisition_sequence(
      static_cast<ifx_Device_Fmcw_t*>(handle_));
  if (ifx_Fmcw_Simple_Sequence_Config_t* simple =
          ifx_fmcw_get_simple_sequence_config(seq)) {
    applied["frame_repetition_time_s"] = simple->frame_repetition_time_s;
    applied["chirp_repetition_time_s"] = simple->chirp_repetition_time_s;
    applied["num_chirps"] = simple->num_chirps;
    applied["tdm_mimo"] = simple->tdm_mimo;
    applied["chirp"]["start_frequency_Hz"] = simple->chirp.start_frequency_Hz;
    applied["chirp"]["end_frequency_Hz"] = simple->chirp.end_frequency_Hz;
    applied["chirp"]["sample_rate_Hz"] = simple->chirp.sample_rate_Hz;
    applied["chirp"]["num_samples"] = simple->chirp.num_samples;
    applied["chirp"]["rx_mask"] = simple->chirp.rx_mask;
    applied["chirp"]["tx_mask"] = simple->chirp.tx_mask;
    applied["chirp"]["tx_power_level"] = simple->chirp.tx_power_level;
    applied["chirp"]["lp_cutoff_Hz"] = simple->chirp.lp_cutoff_Hz;
    applied["chirp"]["hp_cutoff_Hz"] = simple->chirp.hp_cutoff_Hz;
    applied["chirp"]["if_gain_dB"] = simple->chirp.if_gain_dB;
    free(simple);
  }

  nlohmann::json snapshot = {
      {"schema", "capture.radar_config/1"},
      {"requested", requested},
      {"applied", applied},
      {"board_uuid", uuid_},
      {"sdk_version", ifx_sdk_get_version_string_full()},
      {"num_rx", num_rx_},
      {"num_chirps", num_chirps_},
      {"num_samples", num_samples_},
  };

  std::string register_dump;
  {
    const auto tmp =
        std::filesystem::temp_directory_path() / "capture_ifx_registers.txt";
    ifx_fmcw_save_register_file(static_cast<ifx_Device_Fmcw_t*>(handle_),
                                tmp.string().c_str());
    std::ifstream in(tmp, std::ios::binary);
    if (in) {
      register_dump.assign(std::istreambuf_iterator<char>(in),
                           std::istreambuf_iterator<char>());
    }
    std::error_code ec;
    std::filesystem::remove(tmp, ec);
  }
  if (!register_dump.empty()) {
    snapshot["register_dump"] = register_dump;
  }

  config_json_ = snapshot.dump(2);
  configuration_hash_ = capture::storage::blake3_hex(config_json_);
  return true;
}

IfxFrameError IfxFmcwDevice::get_next_raw_frame(std::vector<uint16_t>& out,
                                                uint16_t timeout_ms) {
  if (handle_ == nullptr || raw_frame_ == nullptr) {
    return IfxFrameError::Other;
  }
  auto* raw = static_cast<ifx_Fmcw_Raw_Frame_t*>(raw_frame_);
  ifx_fmcw_get_next_raw_frame_timeout(static_cast<ifx_Device_Fmcw_t*>(handle_),
                                      raw, timeout_ms);
  const auto code = peek_ifx_error();
  const IfxFrameError mapped = map_ifx_error(code);
  if (mapped != IfxFrameError::None) {
    return mapped;
  }
  out.assign(raw->samples, raw->samples + raw->num_samples);
  return IfxFrameError::None;
}

bool IfxFmcwDevice::compute_range_doppler_matrix(
    const std::vector<uint16_t>& raw, uint32_t range_fft, uint32_t doppler_fft,
    std::vector<float>& values, uint32_t& rows, uint32_t& cols,
    std::string& error) {
  if (handle_ == nullptr || float_frame_ == nullptr || raw.empty()) {
    error = "preview unavailable";
    return false;
  }
  const uint32_t chirps = num_chirps_;
  const uint32_t samples = num_samples_;
  if (chirps == 0 || samples == 0) {
    error = "chirp geometry unknown";
    return false;
  }
  auto* dev = static_cast<ifx_Device_Fmcw_t*>(handle_);
  auto* view = static_cast<ifx_Fmcw_Frame_t*>(float_frame_);
  std::vector<float> converted(raw.size());
  ifx_fmcw_convert_raw_data_to_float_array(
      dev, static_cast<uint32_t>(raw.size()), raw.data(), converted.data());
  if (peek_ifx_error() != IFX_OK) {
    error = "convert_raw_data_to_float_array failed";
    return false;
  }
  ifx_fmcw_view_deinterleaved_frame(dev, converted.data(), view);
  if (peek_ifx_error() != IFX_OK || view->num_cubes == 0 ||
      view->cubes == nullptr) {
    error = "view_deinterleaved_frame failed";
    return false;
  }

  range_fft = next_pow2_at_least(range_fft, samples);
  doppler_fft = next_pow2_at_least(doppler_fft, chirps);
  rows = range_fft / 2;
  cols = doppler_fft;
  values.assign(static_cast<size_t>(rows) * cols, 0.0f);

  const std::vector<float> win_range = hann_window(samples);
  const std::vector<float> win_doppler = hann_window(chirps);

  std::vector<float> mean(samples, 0.0f);
  std::vector<std::complex<float>> chirp_buf(range_fft);
  std::vector<std::complex<float>> doppler_buf(doppler_fft);
  // Range profile per chirp, kept complex so the Doppler FFT sees phase.
  std::vector<std::complex<float>> profiles(static_cast<size_t>(chirps) * rows);

  for (uint32_t rx = 0; rx < view->num_cubes; ++rx) {
    auto* cube = view->cubes[rx];
    if (cube == nullptr) {
      continue;
    }
    // MTI: remove the per-sample mean across chirps to suppress static clutter.
    for (uint32_t s = 0; s < samples; ++s) {
      double acc = 0.0;
      for (uint32_t c = 0; c < chirps; ++c) {
        acc += cube_value(cube, c, s);
      }
      mean[s] = static_cast<float>(acc / static_cast<double>(chirps));
    }
    for (uint32_t c = 0; c < chirps; ++c) {
      for (uint32_t s = 0; s < samples; ++s) {
        chirp_buf[s] = {(cube_value(cube, c, s) - mean[s]) * win_range[s],
                        0.0f};
      }
      std::fill(chirp_buf.begin() + samples, chirp_buf.end(),
                std::complex<float>{0.0f, 0.0f});
      fft_inplace(chirp_buf);
      std::copy(chirp_buf.begin(), chirp_buf.begin() + rows,
                profiles.begin() + static_cast<size_t>(c) * rows);
    }
    for (uint32_t r = 0; r < rows; ++r) {
      for (uint32_t c = 0; c < chirps; ++c) {
        doppler_buf[c] = profiles[static_cast<size_t>(c) * rows + r] *
                         win_doppler[c];
      }
      std::fill(doppler_buf.begin() + chirps, doppler_buf.end(),
                std::complex<float>{0.0f, 0.0f});
      fft_inplace(doppler_buf);
      // Shift so zero Doppler (approaching/receding boundary) sits centre-col.
      for (uint32_t d = 0; d < cols; ++d) {
        values[static_cast<size_t>(r) * cols + d] +=
            std::abs(doppler_buf[(d + cols / 2) % cols]);
      }
    }
  }
  return true;
}

bool IfxFmcwDevice::compute_range_doppler_preview(
    const std::vector<uint16_t>& raw, uint32_t range_fft, uint32_t doppler_fft,
    std::vector<float>& values, uint32_t& rows, uint32_t& cols,
    float& display_min, float& display_max, std::string& error) {
  if (!compute_range_doppler_matrix(raw, range_fft, doppler_fft, values, rows,
                                    cols, error)) {
    return false;
  }
  float peak = 1e-9f;
  for (const float v : values) {
    peak = std::max(peak, v);
  }
  // dB against the frame peak: weak returns stay visible without the strongest
  // reflector flattening everything else, which is what Fusion shows.
  constexpr float kFloorDb = -40.0f;
  for (float& v : values) {
    const float db = 20.0f * std::log10(std::max(v, 1e-9f) / peak);
    v = std::max(db, kFloorDb);
  }
  display_min = kFloorDb;
  display_max = 0.0f;
  return true;
}

bool IfxFmcwDevice::compute_range_spectrum_preview(
    const std::vector<uint16_t>& raw, std::vector<float>& values,
    float& display_min, float& display_max, std::string& error) {
  std::vector<float> matrix;
  uint32_t rows = 0;
  uint32_t cols = 0;
  if (!compute_range_doppler_matrix(raw, kPreviewRangeFft, kPreviewDopplerFft,
                                    matrix, rows, cols, error)) {
    return false;
  }
  // Collapse Doppler (cols) → peak per range row (Fusion Range Spectrum).
  values.assign(rows, 0.0f);
  float max_v = 1e-6f;
  for (uint32_t r = 0; r < rows; ++r) {
    float peak = 0.0f;
    for (uint32_t c = 0; c < cols; ++c) {
      peak = std::max(peak, matrix[static_cast<size_t>(r) * cols + c]);
    }
    values[r] = peak;
    max_v = std::max(max_v, peak);
  }
  display_min = 0.0f;
  display_max = max_v;
  return true;
}

bool IfxFmcwDevice::compute_time_domain_preview(
    const std::vector<uint16_t>& raw, std::vector<float>& values,
    float& display_min, float& display_max, std::string& error) {
  if (handle_ == nullptr || float_frame_ == nullptr || raw.empty()) {
    error = "preview unavailable";
    return false;
  }
  auto* dev = static_cast<ifx_Device_Fmcw_t*>(handle_);
  auto* view = static_cast<ifx_Fmcw_Frame_t*>(float_frame_);
  std::vector<float> converted(raw.size());
  ifx_fmcw_convert_raw_data_to_float_array(
      dev, static_cast<uint32_t>(raw.size()), raw.data(), converted.data());
  if (peek_ifx_error() != IFX_OK) {
    error = "convert_raw_data_to_float_array failed";
    return false;
  }
  ifx_fmcw_view_deinterleaved_frame(dev, converted.data(), view);
  if (peek_ifx_error() != IFX_OK || view->num_cubes == 0 ||
      view->cubes == nullptr || view->cubes[0] == nullptr) {
    error = "view_deinterleaved_frame failed";
    return false;
  }
  auto* cube = view->cubes[0];
  constexpr uint32_t kPoints = 128;
  values.assign(kPoints, 0.0f);
  display_min = 0.0f;
  display_max = 1.0f;
  float max_v = 1e-6f;
  float min_v = 0.0f;
  const uint32_t samples = num_samples_;
  for (uint32_t p = 0; p < kPoints; ++p) {
    const uint32_t s = (p * samples) / kPoints;
    const float v = cube_value(cube, 0, s);
    values[p] = v;
    max_v = std::max(max_v, v);
    min_v = std::min(min_v, v);
  }
  display_min = min_v;
  display_max = std::max(max_v, min_v + 1e-6f);
  return true;
}

std::vector<BoardInfo> enumerate_ltr11_boards() {
  std::vector<BoardInfo> boards;
  ifx_List_t* list = ifx_ltr11_get_list();
  if (list == nullptr) {
    (void)peek_ifx_error();
    return boards;
  }
  const size_t count = ifx_list_size(list);
  for (size_t i = 0; i < count; ++i) {
    auto* entry =
        static_cast<ifx_Radar_Sensor_List_Entry_t*>(ifx_list_get(list, i));
    if (entry == nullptr || entry->uuid[0] == '\0') {
      continue;
    }
    BoardInfo info;
    info.kind = BoardKind::Ltr11;
    info.uuid = entry->uuid;
    info.sensor_description = "BGT60LTR11AIP";
    info.num_rx = 1;
    info.adc_bits = 8;
    boards.push_back(std::move(info));
  }
  ifx_list_destroy(list);
  return boards;
}

IfxLtr11Device::~IfxLtr11Device() { close(); }

double IfxLtr11Device::prt_seconds(uint32_t prt_index) {
  switch (static_cast<ifx_Ltr11_PRT_t>(prt_index)) {
    case IFX_LTR11_PRT_250us:
      return 250e-6;
    case IFX_LTR11_PRT_500us:
      return 500e-6;
    case IFX_LTR11_PRT_1000us:
      return 1000e-6;
    case IFX_LTR11_PRT_2000us:
      return 2000e-6;
    default:
      return 500e-6;
  }
}

bool IfxLtr11Device::open(const std::string& uuid, std::string& error) {
  close();
  if (uuid.empty()) {
    error = "uuid required";
    return false;
  }
  handle_ = ifx_ltr11_create_by_uuid(uuid.c_str());
  if (handle_ == nullptr) {
    const auto code = peek_ifx_error();
    error = "ifx_ltr11_create_by_uuid failed: " + ifx_error_message(code);
    return false;
  }
  uuid_ = uuid;
  return true;
}

void IfxLtr11Device::close() {
  if (frame_vec_ != nullptr) {
    ifx_vec_destroy_c(static_cast<ifx_Vector_C_t*>(frame_vec_));
    frame_vec_ = nullptr;
  }
  if (handle_ != nullptr) {
    ifx_ltr11_destroy(static_cast<ifx_Ltr11_Device_t*>(handle_));
    handle_ = nullptr;
  }
  uuid_.clear();
}

bool IfxLtr11Device::apply_defaults(std::string& error) {
  if (handle_ == nullptr) {
    error = "device not open";
    return false;
  }
  auto* dev = static_cast<ifx_Ltr11_Device_t*>(handle_);
  ifx_Ltr11_Config_t cfg{};
  ifx_ltr11_get_config_defaults(dev, &cfg);
  cfg.disable_internal_detector = true;
  ifx_ltr11_set_config(dev, &cfg);
  const auto code = peek_ifx_error();
  if (code != IFX_OK) {
    error = "ifx_ltr11_set_config: " + ifx_error_message(code);
    return false;
  }
  num_samples_ = cfg.num_samples;
  const double prt_s = prt_seconds(static_cast<uint32_t>(cfg.prt));
  if (num_samples_ > 0 && prt_s > 0.0) {
    nominal_frame_rate_hz_ = 1.0 / (prt_s * static_cast<double>(num_samples_));
  }
  ifx_ltr11_start_acquisition(dev);
  if (peek_ifx_error() != IFX_OK) {
    error = "ifx_ltr11_start_acquisition failed";
    return false;
  }
  return build_config_snapshot(error);
}

bool IfxLtr11Device::build_config_snapshot(std::string& error) {
  (void)error;
  auto* dev = static_cast<ifx_Ltr11_Device_t*>(handle_);
  ifx_Ltr11_Config_t applied{};
  ifx_ltr11_get_config(dev, &applied);

  nlohmann::json requested = {
      {"mode", static_cast<int>(applied.mode)},
      {"rf_frequency_Hz", applied.rf_frequency_Hz},
      {"num_samples", applied.num_samples},
      {"internal_detector_threshold", applied.internal_detector_threshold},
      {"prt", static_cast<int>(applied.prt)},
      {"pulse_width", static_cast<int>(applied.pulse_width)},
      {"tx_power_level", static_cast<int>(applied.tx_power_level)},
      {"rx_if_gain", static_cast<int>(applied.rx_if_gain)},
      {"aprt_factor", static_cast<int>(applied.aprt_factor)},
      {"hold_time", static_cast<int>(applied.hold_time)},
      {"disable_internal_detector", true},
  };
  nlohmann::json snapshot = {
      {"schema", "capture.radar_ltr11_config/1"},
      {"requested", requested},
      {"applied", requested},
      {"board_uuid", uuid_},
      {"sdk_version", ifx_sdk_get_version_string_full()},
      {"num_samples", num_samples_},
      {"nominal_frame_rate_hz", nominal_frame_rate_hz_},
  };

  std::string register_dump;
  {
    const auto tmp =
        std::filesystem::temp_directory_path() / "capture_ifx_ltr11_registers.txt";
    ifx_ltr11_register_dump_to_file(dev, tmp.string().c_str());
    std::ifstream in(tmp, std::ios::binary);
    if (in) {
      register_dump.assign(std::istreambuf_iterator<char>(in),
                           std::istreambuf_iterator<char>());
    }
    std::error_code ec;
    std::filesystem::remove(tmp, ec);
  }
  if (!register_dump.empty()) {
    snapshot["register_dump"] = register_dump;
  }

  config_json_ = snapshot.dump(2);
  configuration_hash_ = capture::storage::blake3_hex(config_json_);
  return true;
}

IfxFrameError IfxLtr11Device::get_next_frame(Ltr11FrameResult& out,
                                              uint16_t timeout_ms) {
  if (handle_ == nullptr) {
    return IfxFrameError::Other;
  }
  auto* dev = static_cast<ifx_Ltr11_Device_t*>(handle_);
  ifx_Ltr11_Metadata_t metadata{};
  auto* vec = ifx_ltr11_get_next_frame_timeout(
      dev, static_cast<ifx_Vector_C_t*>(frame_vec_), &metadata, timeout_ms);
  const auto code = peek_ifx_error();
  const IfxFrameError mapped = map_ifx_error(code);
  if (mapped != IfxFrameError::None) {
    return mapped;
  }
  if (vec == nullptr) {
    return IfxFrameError::Other;
  }
  frame_vec_ = vec;
  const uint32_t n = IFX_VEC_LEN(vec);
  out.num_samples = n;
  out.interleaved_iq.resize(static_cast<size_t>(n) * 2);
  for (uint32_t i = 0; i < n; ++i) {
    const ifx_Complex_t c = IFX_VEC_AT(vec, i);
    out.interleaved_iq[static_cast<size_t>(i) * 2] = c.data[0];
    out.interleaved_iq[static_cast<size_t>(i) * 2 + 1] = c.data[1];
  }
  // SDK: motion=false means target detected (active-low pin).
  out.motion_detected = !metadata.motion;
  out.direction = metadata.direction ? 1 : 0;
  num_samples_ = n;
  return IfxFrameError::None;
}

bool IfxLtr11Device::compute_magnitude_trace_preview(
    const Ltr11FrameResult& frame, std::vector<float>& trace, float& display_min,
    float& display_max, std::string& error) {
  if (frame.interleaved_iq.size() < 2 || frame.num_samples == 0) {
    error = "preview unavailable";
    return false;
  }
  constexpr uint32_t kTracePoints = 64;
  trace.assign(kTracePoints, 0.0f);
  display_min = 0.0f;
  display_max = 1.0f;
  float max_v = 1e-6f;
  const uint32_t n = frame.num_samples;
  for (uint32_t p = 0; p < kTracePoints; ++p) {
    const uint32_t start =
        (p * n) / kTracePoints;
    const uint32_t end =
        ((p + 1) * n) / kTracePoints;
    if (end <= start) {
      continue;
    }
    double acc = 0.0;
    for (uint32_t i = start; i < end; ++i) {
      const float re = frame.interleaved_iq[static_cast<size_t>(i) * 2];
      const float im = frame.interleaved_iq[static_cast<size_t>(i) * 2 + 1];
      acc += std::sqrt(static_cast<double>(re) * re + static_cast<double>(im) * im);
    }
    const float v = static_cast<float>(acc / static_cast<double>(end - start));
    trace[p] = v;
    max_v = std::max(max_v, v);
  }
  display_max = max_v;
  return true;
}

bool IfxLtr11Device::compute_doppler_spectrum_preview(
    const Ltr11FrameResult& frame, std::vector<float>& spectrum,
    float& display_min, float& display_max, std::string& error) {
  if (frame.interleaved_iq.size() < 2 || frame.num_samples == 0) {
    error = "preview unavailable";
    return false;
  }
  std::size_t n = 1;
  while (n < frame.num_samples) {
    n <<= 1;
  }
  n = (std::min)(n, static_cast<std::size_t>(256));
  std::vector<std::complex<float>> buf(n, {0.0f, 0.0f});
  const uint32_t use = (std::min)(frame.num_samples, static_cast<uint32_t>(n));
  for (uint32_t i = 0; i < use; ++i) {
    buf[i] = {frame.interleaved_iq[static_cast<size_t>(i) * 2],
              frame.interleaved_iq[static_cast<size_t>(i) * 2 + 1]};
  }
  fft_inplace(buf);

  constexpr uint32_t kBins = 64;
  spectrum.assign(kBins, 0.0f);
  display_min = 0.0f;
  display_max = 1.0f;
  float max_v = 1e-6f;
  for (uint32_t b = 0; b < kBins; ++b) {
    const std::size_t src = (static_cast<std::size_t>(b) * n) / kBins;
    const float v = std::abs(buf[src]);
    spectrum[b] = v;
    max_v = std::max(max_v, v);
  }
  display_max = max_v;
  return true;
}

}  // namespace capture::radar_worker
