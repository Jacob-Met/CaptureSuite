// SPDX-License-Identifier: GPL-3.0-only
#include "capture/recording_buffer.hpp"

namespace capture {

void RecordingStore::clear() {
  std::lock_guard lock(mu_);
  streams_.clear();
}

StreamRecording& RecordingStore::ensure_stream(const std::string& stream_id,
                                               const std::string& source_id,
                                               const std::string& modality,
                                               double nominal_rate_hz) {
  std::lock_guard lock(mu_);
  auto& stream = streams_[stream_id];
  if (stream.stream_id.empty()) {
    stream.stream_id = stream_id;
    stream.source_id = source_id;
    stream.modality = modality;
    stream.nominal_rate_hz = nominal_rate_hz;
  }
  return stream;
}

void RecordingStore::append_sample(const std::string& stream_id,
                                   const SampleRecord& sample) {
  std::lock_guard lock(mu_);
  auto it = streams_.find(stream_id);
  if (it == streams_.end()) {
    return;
  }
  if (it->second.first_datum_session_time_ns < 0) {
    it->second.first_datum_session_time_ns = sample.session_time_ns;
  }
  it->second.samples.push_back(sample);
}

void RecordingStore::open_gap(const std::string& stream_id, GapRecord gap) {
  std::lock_guard lock(mu_);
  auto it = streams_.find(stream_id);
  if (it == streams_.end()) {
    return;
  }
  it->second.gaps.push_back(std::move(gap));
}

void RecordingStore::close_open_gaps(const std::string& stream_id,
                                     int64_t end_session_time_ns) {
  std::lock_guard lock(mu_);
  auto it = streams_.find(stream_id);
  if (it == streams_.end()) {
    return;
  }
  for (auto& gap : it->second.gaps) {
    if (gap.end_session_time_ns < 0) {
      gap.end_session_time_ns = end_session_time_ns;
    }
  }
}

std::vector<std::string> RecordingStore::stream_ids() const {
  std::lock_guard lock(mu_);
  std::vector<std::string> ids;
  ids.reserve(streams_.size());
  for (const auto& [id, _] : streams_) {
    ids.push_back(id);
  }
  return ids;
}

StreamRecording RecordingStore::snapshot(const std::string& stream_id) const {
  std::lock_guard lock(mu_);
  auto it = streams_.find(stream_id);
  if (it == streams_.end()) {
    return {};
  }
  return it->second;
}

std::size_t RecordingStore::total_samples() const {
  std::lock_guard lock(mu_);
  std::size_t total = 0;
  for (const auto& [_, stream] : streams_) {
    total += stream.samples.size();
  }
  return total;
}

}  // namespace capture
