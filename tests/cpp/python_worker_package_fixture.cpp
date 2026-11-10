// SPDX-License-Identifier: GPL-3.0-only
// Test bridge to the same SessionPackage lifecycle used by the native daemon.
// Worker samples and SegmentSealed events come from the real Python worker.
#include "capture/storage/session_package.hpp"

#include <iostream>
#include <nlohmann/json.hpp>
#include <string>

int main() {
  using nlohmann::json;
  capture::storage::SessionPackage package;
  std::string line;
  while (std::getline(std::cin, line)) {
    try {
      const auto request = json::parse(line);
      const auto operation = request.at("operation").get<std::string>();
      std::string error;
      if (operation == "create") {
        capture::storage::PackageOptions options;
        options.parent_dir = request.at("parent").get<std::string>();
        options.session_id = request.at("session_id").get<std::string>();
        options.session_name = "Live Python worker handoff";
        if (!package.create(options, error)) throw std::runtime_error(error);
        std::vector<capture::storage::PackageStreamDesc> streams;
        for (const auto& item : request.at("streams")) {
          capture::storage::PackageStreamDesc stream;
          stream.source_id = item.at("source_id").get<std::string>();
          stream.stream_id = item.at("stream_id").get<std::string>();
          stream.modality = item.at("modality").get<std::string>();
          stream.alias = item.value("alias", stream.source_id);
          stream.source_type = item.value("source_type", "lsl");
          stream.nominal_rate_hz = item.at("nominal_rate_hz").get<double>();
          stream.external_segments = true;
          streams.push_back(stream);
        }
        if (!package.begin_recording(streams, request.at("t0_ns").get<int64_t>(),
              1000000000LL, request.at("wall_utc").get<std::string>(), 0, error)) {
          throw std::runtime_error(error);
        }
      } else if (operation == "sealed") {
        capture::storage::SealedSegmentInfo segment;
        segment.relative_path = request.at("path").get<std::string>();
        segment.absolute_path = package.root() / segment.relative_path;
        segment.source_id = request.at("source_id").get<std::string>();
        segment.stream_id = request.at("stream_id").get<std::string>();
        segment.size_bytes = request.at("size_bytes").get<int64_t>();
        segment.hash_blake3_hex = request.at("hash_blake3_hex").get<std::string>();
        segment.start_session_time_ns = request.at("start_session_time_ns").get<int64_t>();
        segment.end_session_time_ns = request.at("end_session_time_ns").get<int64_t>();
        segment.actual_count = request.at("actual_count").get<int64_t>();
        segment.segment_index = request.at("segment_index").get<int>();
        package.record_external_segment(segment);
      } else if (operation == "finalize") {
        if (!package.finalize(error)) throw std::runtime_error(error);
      } else {
        throw std::runtime_error("unknown operation");
      }
      std::cout << json({{"ok", true}, {"root", package.root().string()},
                         {"state", package.state()}}).dump() << std::endl;
      if (operation == "finalize") return 0;
    } catch (const std::exception& error) {
      std::cout << json({{"ok", false}, {"error", error.what()}}).dump() << std::endl;
      return 1;
    }
  }
  return 0;
}
