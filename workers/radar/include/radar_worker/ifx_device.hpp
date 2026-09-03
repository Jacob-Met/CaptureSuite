// SPDX-License-Identifier: GPL-3.0-only
#pragma once

#include <cstdint>
#include <optional>
#include <string>
#include <vector>

namespace capture::radar_worker {

enum class BoardKind { Fmcw, Ltr11 };

struct BoardInfo {
  BoardKind kind = BoardKind::Fmcw;
  std::string uuid;
  std::string sensor_description;
  std::string firmware_description;
  uint32_t num_rx = 0;
  uint32_t adc_bits = 0;
};

enum class IfxFrameError {
  None,
  Timeout,
  FifoOverflow,
  CommunicationError,
  Other,
};

struct Ltr11FrameResult {
  std::vector<float> interleaved_iq;
  uint32_t num_samples = 0;
  bool motion_detected = false;
  int32_t direction = 0;
};

std::vector<BoardInfo> enumerate_fmcw_boards();
std::vector<BoardInfo> enumerate_ltr11_boards();

std::string source_id_from_uuid(const std::string& uuid);

// Requested FMCW acquisition geometry. Defaults match the vendor spike /
// Fusion-style 1.5 GHz / 32×128 / 20 Hz profile. The SDK may round cutoffs
// and gain to supported steps; stream.json records both requested and applied.
struct FmcwSequenceConfig {
  double frame_repetition_time_s = 0.05;
  double chirp_repetition_time_s = 500e-6;
  uint32_t num_chirps = 32;
  double start_frequency_Hz = 60e9;
  double end_frequency_Hz = 61.5e9;
  double sample_rate_Hz = 2e6;
  uint32_t num_samples = 128;
  uint32_t rx_mask = 7;
  uint32_t tx_mask = 1;
  uint32_t tx_power_level = 31;
  uint32_t lp_cutoff_Hz = 500000;
  uint32_t hp_cutoff_Hz = 80000;
  uint32_t if_gain_dB = 33;
};

class IfxFmcwDevice {
 public:
  IfxFmcwDevice() = default;
  ~IfxFmcwDevice();

  IfxFmcwDevice(const IfxFmcwDevice&) = delete;
  IfxFmcwDevice& operator=(const IfxFmcwDevice&) = delete;

  bool open(const std::string& uuid, std::string& error);
  void close();

  bool is_open() const { return handle_ != nullptr; }
  const std::string& uuid() const { return uuid_; }

  bool apply_sequence(const FmcwSequenceConfig& cfg, std::string& error);
  IfxFrameError get_next_raw_frame(std::vector<uint16_t>& out, uint16_t timeout_ms);

  uint32_t num_rx() const { return num_rx_; }
  uint32_t num_chirps() const { return num_chirps_; }
  uint32_t num_samples() const { return num_samples_; }
  double nominal_frame_rate_hz() const { return nominal_frame_rate_hz_; }

  std::string configuration_hash() const { return configuration_hash_; }
  std::string config_json() const { return config_json_; }

  // MTI + windowed 2D FFT summed over every RX, Doppler centred on zero.
  // `range_fft` / `doppler_fft` are rounded up to a power of two no smaller
  // than the chirp geometry; output is range_fft/2 rows by doppler_fft cols,
  // so zero-padding buys interpolation, not new information.
  bool compute_range_doppler_matrix(const std::vector<uint16_t>& raw,
                                    uint32_t range_fft, uint32_t doppler_fft,
                                    std::vector<float>& values, uint32_t& rows,
                                    uint32_t& cols, std::string& error);

  // Range-Doppler in dB relative to the frame peak, floored at -40 dB.
  bool compute_range_doppler_preview(const std::vector<uint16_t>& raw,
                                     uint32_t range_fft, uint32_t doppler_fft,
                                     std::vector<float>& values, uint32_t& rows,
                                     uint32_t& cols, float& display_min,
                                     float& display_max, std::string& error);

  // MTI + range FFT, max across chirps → 64 bins (Fusion "Range Spectrum").
  bool compute_range_spectrum_preview(const std::vector<uint16_t>& raw,
                                      std::vector<float>& values,
                                      float& display_min, float& display_max,
                                      std::string& error);

  // First-chirp RX0 time samples, decimated to 128 points.
  bool compute_time_domain_preview(const std::vector<uint16_t>& raw,
                                   std::vector<float>& values,
                                   float& display_min, float& display_max,
                                   std::string& error);

  void* handle_for_sdk() const { return handle_; }

 private:
  bool refresh_geometry(std::string& error);
  bool build_config_snapshot(std::string& error);
  void destroy_sequence();
  bool allocate_frames(std::string& error);

  void* handle_ = nullptr;  // ifx_Device_Fmcw_t*
  void* sequence_ = nullptr;  // ifx_Fmcw_Sequence_Element_t*
  void* raw_frame_ = nullptr;  // ifx_Fmcw_Raw_Frame_t*
  void* float_frame_ = nullptr;  // ifx_Fmcw_Frame_t*
  std::string uuid_;
  uint32_t num_rx_ = 0;
  uint32_t num_chirps_ = 32;
  uint32_t num_samples_ = 128;
  double frame_repetition_time_s_ = 0.05;
  double nominal_frame_rate_hz_ = 20.0;
  FmcwSequenceConfig requested_;
  std::string configuration_hash_;
  std::string config_json_;
};

class IfxLtr11Device {
 public:
  IfxLtr11Device() = default;
  ~IfxLtr11Device();

  IfxLtr11Device(const IfxLtr11Device&) = delete;
  IfxLtr11Device& operator=(const IfxLtr11Device&) = delete;

  bool open(const std::string& uuid, std::string& error);
  void close();

  bool is_open() const { return handle_ != nullptr; }
  const std::string& uuid() const { return uuid_; }

  bool apply_defaults(std::string& error);
  IfxFrameError get_next_frame(Ltr11FrameResult& out, uint16_t timeout_ms);

  uint32_t num_samples() const { return num_samples_; }
  double nominal_frame_rate_hz() const { return nominal_frame_rate_hz_; }

  std::string configuration_hash() const { return configuration_hash_; }
  std::string config_json() const { return config_json_; }

  // Rolling mean of |z| over samples as a short trace for preview.
  bool compute_magnitude_trace_preview(const Ltr11FrameResult& frame,
                                       std::vector<float>& trace,
                                       float& display_min, float& display_max,
                                       std::string& error);

  // Per-frame Doppler magnitude spectrum (64 bins) for spectrogram stacking.
  bool compute_doppler_spectrum_preview(const Ltr11FrameResult& frame,
                                        std::vector<float>& spectrum,
                                        float& display_min, float& display_max,
                                        std::string& error);

  void* handle_for_sdk() const { return handle_; }

 private:
  bool build_config_snapshot(std::string& error);
  static double prt_seconds(uint32_t prt_index);

  void* handle_ = nullptr;  // ifx_Ltr11_Device_t*
  void* frame_vec_ = nullptr;  // ifx_Vector_C_t*
  std::string uuid_;
  uint32_t num_samples_ = 256;
  double nominal_frame_rate_hz_ = 7.8;
  std::string configuration_hash_;
  std::string config_json_;
};

}  // namespace capture::radar_worker
