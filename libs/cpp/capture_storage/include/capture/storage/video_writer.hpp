// SPDX-License-Identifier: GPL-3.0-only
#pragma once

#include <cstdint>
#include <filesystem>
#include <string>

namespace capture::storage {

// Milestone 3: interface only. Real Matroska encoding arrives with cameras.
class IVideoSegmentWriter {
 public:
  virtual ~IVideoSegmentWriter() = default;
  virtual bool open_segment(const std::filesystem::path& mkv_path,
                            std::string& error) = 0;
  virtual bool write_frame(const uint8_t* data, size_t len, int64_t session_time_ns,
                           std::string& error) = 0;
  virtual bool close_segment(std::string& error) = 0;
};

class NullVideoSegmentWriter final : public IVideoSegmentWriter {
 public:
  bool open_segment(const std::filesystem::path&, std::string& error) override {
    error = "video segment writer not implemented in M3";
    return false;
  }
  bool write_frame(const uint8_t*, size_t, int64_t, std::string& error) override {
    error = "video segment writer not implemented in M3";
    return false;
  }
  bool close_segment(std::string& error) override {
    error.clear();
    return true;
  }
};

}  // namespace capture::storage
