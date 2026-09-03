// SPDX-License-Identifier: GPL-3.0-only
#include "capture/storage/mcap_stream_writer.hpp"

#include "capture/storage/hash.hpp"

#include "capture/v1/common.pb.h"
#include "capture/v1/data/emg_batch.pb.h"
#include "capture/v1/data/imu_frame.pb.h"
#include "capture/v1/data/numeric_batch.pb.h"
#include "capture/v1/data/radar_frame.pb.h"
#include "capture/v1/data/video_timing.pb.h"

#include <mcap/mcap.hpp>

#include <cmath>
#include <cstring>
#include <string>

namespace capture::storage {

McapStreamWriter::McapStreamWriter() = default;

McapStreamWriter::~McapStreamWriter() {
  std::string err;
  close(err);
}

bool McapStreamWriter::open(std::filesystem::path segments_dir,
                            std::filesystem::path package_root,
                            StreamWriterConfig config, std::string& error,
                            int initial_segment_index) {
  segments_dir_ = std::move(segments_dir);
  package_root_ = std::move(package_root);
  config_ = std::move(config);
  segment_index_ = initial_segment_index;
  total_samples_ = 0;
  std::error_code ec;
  std::filesystem::create_directories(segments_dir_, ec);
  if (ec) {
    error = "failed to create segments dir";
    return false;
  }
  // Tune batch window by modality. Producers pack complete schema messages
  // (ImuFrame / EmgBatch / radar frames) into SamplePoint.payload — flush one
  // MCAP message per sample so later payloads are not discarded.
  if (config_.modality == "video" || config_.modality == "radar" ||
      config_.modality == "radar_doppler" || config_.modality == "imu" ||
      config_.modality == "emg") {
    config_.max_batch_samples = 1;
    config_.max_batch_ns = 0;
  } else if (config_.modality == "mixed") {
    config_.max_batch_ns = 100LL * 1000000LL;
  }
  return open_segment(error);
}

bool McapStreamWriter::open_segment(std::string& error) {
  char name[64];
  const std::string suffix =
      config_.filename_suffix.empty() ? ".mcap" : config_.filename_suffix;
  std::snprintf(name, sizeof(name), "%06d%s", segment_index_, suffix.c_str());
  const auto abs = segments_dir_ / name;
  file_ = std::make_unique<std::ofstream>(abs, std::ios::binary | std::ios::trunc);
  if (!*file_) {
    error = "failed to open mcap segment: " + abs.string();
    return false;
  }
  writer_ = std::make_unique<mcap::McapWriter>();
  mcap::McapWriterOptions opts("capturesuite");
  if (config_.compress) {
    opts.compression = mcap::Compression::Zstd;
    opts.compressionLevel = mcap::CompressionLevel::Fastest;
  } else {
    opts.compression = mcap::Compression::None;
  }
  // Smaller chunks so rotation thresholds are observable during recording.
  opts.chunkSize = 64 * 1024;
  writer_->open(*file_, opts);
  approx_bytes_ = 0;

  mcap::Schema schema;
  schema.name = config_.data_schema_id;
  schema.encoding = config_.schema_encoding;
  schema.data = config_.schema_data;
  writer_->addSchema(schema);

  mcap::Channel channel;
  channel.topic = config_.stream_id;
  channel.schemaId = schema.id;
  channel.messageEncoding = "protobuf";
  channel.metadata["source_id"] = config_.source_id;
  channel.metadata["modality"] = config_.modality;
  writer_->addChannel(channel);
  channel_id_ = channel.id;

  segment_start_ns_ = -1;
  segment_end_ns_ = -1;
  segment_count_ = 0;
  batch_.clear();
  batch_start_ns_ = -1;
  return true;
}

bool McapStreamWriter::should_rotate() const {
  if (!file_ || config_.external_rotation) {
    return false;
  }
  if (approx_bytes_ >= config_.rotate_bytes) {
    return true;
  }
  const auto pos = file_->tellp();
  if (pos > 0 && static_cast<int64_t>(pos) >= config_.rotate_bytes) {
    return true;
  }
  if (segment_start_ns_ >= 0 && segment_end_ns_ >= 0 &&
      (segment_end_ns_ - segment_start_ns_) >= config_.rotate_session_ns) {
    return true;
  }
  return false;
}

std::string McapStreamWriter::serialize_batch() const {
  if (batch_.empty()) {
    return {};
  }
  // Workers / sim may pre-serialize the schema message into SamplePoint.payload.
  // Prefer that when present so the writer does not re-encode and lose fields.
  if (!batch_.front().payload.empty()) {
    return std::string(batch_.front().payload.begin(),
                       batch_.front().payload.end());
  }
  if (config_.modality == "video") {
    capture::v1::data::VideoFrameTiming msg;
    auto* t = msg.mutable_timing();
    t->set_sequence_number(batch_.front().sequence);
    t->set_host_arrival_ns(batch_.front().host_arrival_ns);
    t->set_session_time_ns(batch_.front().session_time_ns);
    t->set_quality_flags(batch_.front().quality_flags);
    msg.set_frame_index(batch_.front().sequence);
    msg.set_segment_index(static_cast<uint32_t>(segment_index_));
    msg.set_quality_flags(batch_.front().quality_flags);
    return msg.SerializeAsString();
  }
  if (config_.modality == "imu" || config_.data_schema_id == "imu.frame/1") {
    // Fallback when producers omit payload: synthetic multi-sensor IMU frame.
    constexpr int kSensors = 7;
    capture::v1::data::ImuFrame msg;
    auto* t = msg.mutable_timing();
    t->set_sequence_number(batch_.front().sequence);
    t->set_host_arrival_ns(batch_.front().host_arrival_ns);
    t->set_session_time_ns(batch_.front().session_time_ns);
    t->set_quality_flags(batch_.front().quality_flags);
    msg.set_frame_index(batch_.front().sequence);
    msg.set_quality_flags(batch_.front().quality_flags);
    const double phase = static_cast<double>(batch_.front().sequence) * 0.02;
    for (int i = 0; i < kSensors; ++i) {
      auto* s = msg.add_sensors();
      s->set_sensor_id("ch" + std::to_string(i));
      const double ang = phase + static_cast<double>(i) * 0.15;
      s->set_qw(static_cast<float>(std::cos(ang * 0.5)));
      s->set_qx(0.f);
      s->set_qy(static_cast<float>(std::sin(ang * 0.5)));
      s->set_qz(0.f);
      s->set_accel_x(0.f);
      s->set_accel_y(0.f);
      s->set_accel_z(static_cast<float>(9.81 + 0.2 * std::sin(ang * 3.0)));
      s->set_gyro_x(0.f);
      s->set_gyro_y(static_cast<float>(0.1 + 0.05 * std::cos(ang * 2.0)));
      s->set_gyro_z(0.f);
    }
    return msg.SerializeAsString();
  }

  if (config_.modality == "emg" || config_.data_schema_id == "emg.batch/1") {
    // EMG: multi-channel EmgBatch, row-major channels × samples.
    constexpr int kChannels = 8;
    capture::v1::data::EmgBatch msg;
    auto* t = msg.mutable_timing();
    t->set_sequence_number(batch_.front().sequence);
    t->set_host_arrival_ns(batch_.front().host_arrival_ns);
    t->set_session_time_ns(batch_.front().session_time_ns);
    t->set_quality_flags(batch_.front().quality_flags);
    msg.set_first_sample_index(batch_.front().sequence);
    msg.set_sample_count(static_cast<int32_t>(batch_.size()));
    for (int c = 0; c < kChannels; ++c) {
      msg.add_channel_ids("ch" + std::to_string(c));
    }
    const size_t n = static_cast<size_t>(kChannels) * batch_.size();
    std::string samples;
    samples.resize(n * sizeof(float));
    auto* f = reinterpret_cast<float*>(samples.data());
    for (int c = 0; c < kChannels; ++c) {
      for (size_t i = 0; i < batch_.size(); ++i) {
        const float phase =
            static_cast<float>(batch_[i].sequence) * 0.08f + c * 0.4f;
        f[static_cast<size_t>(c) * batch_.size() + i] =
            std::sin(phase) * 0.7f;
      }
    }
    msg.set_samples_f32_le(samples);
    msg.set_quality_flags(batch_.front().quality_flags);
    return msg.SerializeAsString();
  }

  // Generic numeric fallback (force / mixed / unknown modalities).
  constexpr uint32_t kChannels = 8;
  capture::v1::data::NumericBatch msg;
  msg.set_channel_count(kChannels);
  msg.set_units("");
  msg.set_dtype("f32");
  for (uint32_t c = 0; c < kChannels; ++c) {
    msg.add_channel_names("ch" + std::to_string(c));
  }
  for (size_t i = 0; i < batch_.size(); ++i) {
    msg.add_device_time_ns(batch_[i].session_time_ns);
    for (uint32_t c = 0; c < kChannels; ++c) {
      const double phase =
          static_cast<double>(batch_[i].sequence) * 0.08 + c * 0.4;
      msg.add_samples(std::sin(phase) * 0.7);
    }
  }
  return msg.SerializeAsString();
}

bool McapStreamWriter::flush_batch(std::string& error) {
  if (batch_.empty() || !writer_) {
    return true;
  }
  if (writes_blocked_) {
    batch_.clear();
    batch_start_ns_ = -1;
    error = "WRITE_BLOCKED";
    return false;
  }
  const auto payload = serialize_batch();
  mcap::Message msg;
  msg.channelId = channel_id_;
  msg.sequence = static_cast<uint32_t>(batch_.front().sequence & 0xffffffffu);
  msg.logTime = static_cast<uint64_t>(batch_.front().session_time_ns);
  msg.publishTime = static_cast<uint64_t>(batch_.front().host_arrival_ns);
  msg.data = reinterpret_cast<const std::byte*>(payload.data());
  msg.dataSize = payload.size();
  const auto st = writer_->write(msg);
  if (!st.ok()) {
    error = std::string(st.message);
    return false;
  }
  approx_bytes_ += static_cast<int64_t>(payload.size()) + 64;
  if (segment_start_ns_ < 0) {
    segment_start_ns_ = batch_.front().session_time_ns;
  }
  segment_end_ns_ = batch_.back().session_time_ns;
  segment_count_ += static_cast<int64_t>(batch_.size());
  total_samples_ += static_cast<int64_t>(batch_.size());
  batch_.clear();
  batch_start_ns_ = -1;
  return true;
}

bool McapStreamWriter::append(const SamplePoint& sample, std::string& error) {
  if (writes_blocked_) {
    error = "WRITE_BLOCKED";
    return false;
  }
  if (batch_.empty()) {
    batch_start_ns_ = sample.session_time_ns;
  }
  batch_.push_back(sample);
  const bool time_full =
      config_.max_batch_ns > 0 &&
      (sample.session_time_ns - batch_start_ns_) >= config_.max_batch_ns;
  const bool count_full =
      static_cast<int>(batch_.size()) >= config_.max_batch_samples;
  if (time_full || count_full || config_.max_batch_samples == 1) {
    if (!flush_batch(error)) {
      return false;
    }
    if (should_rotate()) {
      if (!close_segment(true, error)) {
        return false;
      }
      ++segment_index_;
      return open_segment(error);
    }
  }
  return true;
}

bool McapStreamWriter::flush(std::string& error) { return flush_batch(error); }

bool McapStreamWriter::close_segment(bool seal, std::string& error) {
  if (!flush_batch(error)) {
    // still try to close file
  }
  if (writer_) {
    writer_->close();
    writer_.reset();
  }
  if (file_) {
    file_->flush();
    file_.reset();
  }
  if (!seal) {
    return true;
  }

  char name[64];
  const std::string suffix =
      config_.filename_suffix.empty() ? ".mcap" : config_.filename_suffix;
  std::snprintf(name, sizeof(name), "%06d%s", segment_index_, suffix.c_str());
  const auto abs = segments_dir_ / name;
  SealedSegmentInfo info;
  info.absolute_path = abs;
  info.relative_path = std::filesystem::relative(abs, package_root_);
  info.size_bytes = static_cast<int64_t>(std::filesystem::file_size(abs));
  info.hash_blake3_hex = blake3_file_hex(abs, error);
  if (info.hash_blake3_hex.empty()) {
    return false;
  }
  info.start_session_time_ns = segment_start_ns_ < 0 ? 0 : segment_start_ns_;
  info.end_session_time_ns = segment_end_ns_ < 0 ? 0 : segment_end_ns_;
  info.actual_count = segment_count_;
  info.segment_index = segment_index_;
  if (on_rotate_) {
    on_rotate_(info);
  }
  return true;
}

bool McapStreamWriter::close(std::string& error) {
  if (!file_ && !writer_) {
    return true;
  }
  return close_segment(true, error);
}

bool McapStreamWriter::open_segment_index(int index, std::string& error) {
  if (file_ || writer_) {
    if (!close_segment(true, error)) {
      return false;
    }
  }
  segment_index_ = index;
  return open_segment(error);
}

}  // namespace capture::storage
