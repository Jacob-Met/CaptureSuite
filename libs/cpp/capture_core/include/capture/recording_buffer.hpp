// SPDX-License-Identifier: GPL-3.0-only
#pragma once

#include <cstdint>
#include <mutex>
#include <string>
#include <unordered_map>
#include <vector>

namespace capture {

struct SampleRecord {
  int64_t sequence = 0;
  int64_t session_time_ns = 0;
  int64_t host_arrival_ns = 0;
  uint32_t quality_flags = 0;
};

struct GapRecord {
  std::string cause;
  int64_t start_session_time_ns = 0;
  int64_t end_session_time_ns = -1;  // -1 = open
  int64_t estimated_lost_count = 0;
};

struct StreamRecording {
  std::string stream_id;
  std::string source_id;
  std::string modality;
  double nominal_rate_hz = 0;
  std::vector<SampleRecord> samples;
  std::vector<GapRecord> gaps;
  int64_t first_datum_session_time_ns = -1;
  int64_t dropped_count = 0;
};

// In-memory recording sink for Milestone 2 (MCAP writers arrive in M3).
class RecordingStore {
 public:
  void clear();
  StreamRecording& ensure_stream(const std::string& stream_id,
                                 const std::string& source_id,
                                 const std::string& modality,
                                 double nominal_rate_hz);

  void append_sample(const std::string& stream_id, const SampleRecord& sample);
  void open_gap(const std::string& stream_id, GapRecord gap);
  void close_open_gaps(const std::string& stream_id, int64_t end_session_time_ns);

  std::vector<std::string> stream_ids() const;
  StreamRecording snapshot(const std::string& stream_id) const;
  std::size_t total_samples() const;

 private:
  mutable std::mutex mu_;
  std::unordered_map<std::string, StreamRecording> streams_;
};

}  // namespace capture
