// SPDX-License-Identifier: GPL-3.0-only
#include "capture/storage/session_package.hpp"

#include "capture/storage/atomic_file.hpp"
#include "capture/storage/hash.hpp"

#include <nlohmann/json.hpp>

#define WIN32_LEAN_AND_MEAN
#include <Windows.h>

#include <cstring>
#include <fstream>
#include <iomanip>
#include <sstream>

namespace capture::storage {
namespace {

using json = nlohmann::json;

}  // namespace

SessionPackage::~SessionPackage() {
  std::string err;
  for (auto& [_, w] : writers_) {
    if (w) {
      w->close(err);
    }
  }
  journal_.close();
}

std::string SessionPackage::wall_now_utc() const {
  SYSTEMTIME st{};
  GetSystemTime(&st);
  std::ostringstream oss;
  oss << std::setfill('0') << std::setw(4) << st.wYear << '-' << std::setw(2)
      << st.wMonth << '-' << std::setw(2) << st.wDay << 'T' << std::setw(2)
      << st.wHour << ':' << std::setw(2) << st.wMinute << ':' << std::setw(2)
      << st.wSecond << '.' << std::setw(3) << st.wMilliseconds << 'Z';
  return oss.str();
}

std::string SessionPackage::state() const {
  std::lock_guard lock(mu_);
  return state_;
}

bool SessionPackage::create(const PackageOptions& opts, std::string& error) {
  std::lock_guard lock(mu_);
  opts_ = opts;
  session_id_ = opts.session_id;
  created_utc_ = wall_now_utc();
  std::string folder = opts.session_name.empty() ? opts.session_id : opts.session_name;
  if (folder.size() < 10 ||
      folder.substr(folder.size() - 10) != ".mmsession") {
    folder += ".mmsession";
  }
  root_ = opts.parent_dir / folder;
  std::error_code ec;
  std::filesystem::create_directories(root_, ec);
  if (ec) {
    error = "failed to create package root";
    return false;
  }
  for (const char* sub :
       {"events", "sources", "mappings", "calibrations", "presets_snapshot",
        "processing", "logs", "recovery", "exports"}) {
    std::filesystem::create_directories(root_ / sub, ec);
  }
  if (!journal_.open(root_ / "journal.sqlite", error)) {
    return false;
  }
  state_ = "preparing";
  if (!write_manifest(error)) {
    return false;
  }
  if (!journal_.append(0, created_utc_, "SESSION_CREATED", "", "",
                       json({{"session_id", session_id_}}).dump(), error)) {
    return false;
  }
  watchdog_ = std::make_unique<DiskWatchdog>(root_);
  watchdog_->set_alert_callback([this](const std::string& level,
                                       const std::string& msg) {
    std::string err;
    journal_.append(0, wall_now_utc(),
                    level == "hard_floor" ? "DISK_CRITICAL" : "DISK_WARNING", "",
                    "", json({{"level", level}, {"msg", msg}}).dump(), err);
  });
  integrity_.clear();
  if (!write_integrity(error)) {
    return false;
  }
  return true;
}

std::vector<std::byte> SessionPackage::load_schema_data() const {
  if (opts_.descriptor_set_path.empty() ||
      !std::filesystem::exists(opts_.descriptor_set_path)) {
    return {};
  }
  std::ifstream in(opts_.descriptor_set_path, std::ios::binary);
  if (!in) {
    return {};
  }
  std::string bytes((std::istreambuf_iterator<char>(in)),
                    std::istreambuf_iterator<char>());
  std::vector<std::byte> out(bytes.size());
  std::memcpy(out.data(), bytes.data(), bytes.size());
  return out;
}

std::string SessionPackage::data_schema_for(const std::string& modality) const {
  if (modality == "video") {
    return "video.segment_index/1";
  }
  if (modality == "imu") {
    return "imu.frame/1";
  }
  if (modality == "radar") {
    return "radar.frame/1";
  }
  if (modality == "radar_doppler") {
    return "radar.doppler/1";
  }
  if (modality == "emg") {
    return "emg.batch/1";
  }
  return "generic.numeric_batch/1";
}

bool SessionPackage::write_manifest(std::string& error) {
  json j;
  j["sessionSchemaVersion"] = "1.0.0";
  j["sessionId"] = session_id_;
  j["state"] = state_;
  j["identity"] = {{"sessionId", session_id_}};
  j["t0QpcTicks"] = std::to_string(t0_qpc_ticks_);
  j["qpcFrequency"] = std::to_string(qpc_frequency_);
  j["t0WallUtc"] = t0_wall_utc_;
  j["t0UncertaintyNs"] = std::to_string(t0_uncertainty_ns_);
  j["createdUtc"] = created_utc_;
  j["finalizedUtc"] = (state_ == "finalized" || state_ == "finalized_recovered")
                          ? wall_now_utc()
                          : "";
  j["appVersion"] = "0.1.0";
  j["daemonVersion"] = opts_.daemon_version;
  j["pluginVersions"] = {{"sim.builtin", "0.1.0"}};
  j["sourceIds"] = source_ids_;
  return atomic_write_text(root_ / "manifest.json", j.dump(2), error);
}

bool SessionPackage::write_integrity(std::string& error) {
  json j;
  j["sessionId"] = session_id_;
  j["sessionSchemaVersion"] = "1.0.0";
  j["files"] = json::array();
  for (const auto& e : integrity_) {
    j["files"].push_back({
        {"path", e.path},
        {"sizeBytes", std::to_string(e.size_bytes)},
        {"hashBlake3Hex", e.hash_blake3_hex},
        {"sourceId", e.source_id},
        {"streamId", e.stream_id},
        {"startSessionTimeNs", std::to_string(e.start_session_time_ns)},
        {"endSessionTimeNs", std::to_string(e.end_session_time_ns)},
        {"expectedCount", std::to_string(e.expected_count)},
        {"actualCount", std::to_string(e.actual_count)},
        {"status", e.status},
    });
  }
  return atomic_write_text(root_ / "integrity.json", j.dump(2), error);
}

bool SessionPackage::write_arrays_json(std::string& error) {
  // Snapshot of RadarArray membership for this session. Poses default to
  // identity until the spatial editor (RADAR_ARRAY.md) fills them in.
  // Timing is always SOFTWARE_COORDINATED until hardware sync is validated.
  json members = json::array();
  for (const auto& [stream_id, desc] : stream_descs_) {
    (void)stream_id;
    if (desc.modality != "radar" && desc.modality != "radar_doppler") {
      continue;
    }
    members.push_back({
        {"sourceId", desc.source_id},
        {"alias", desc.alias},
        {"enabled", true},
        {"pose",
         {{"xM", 0.0},
          {"yM", 0.0},
          {"zM", 0.0},
          {"qw", 1.0},
          {"qx", 0.0},
          {"qy", 0.0},
          {"qz", 0.0}}},
        {"coordinateFrame", "lab"},
        {"calibrationRef", ""},
    });
  }
  json arrays = json::array();
  if (!members.empty()) {
    arrays.push_back({
        {"arrayId", "session_radar"},
        {"name", "Session radar"},
        {"arrayType", "radar"},
        {"members", members},
        {"timingMode", "SOFTWARE_COORDINATED"},
        {"coordinateFrame", "lab"},
    });
  }
  json doc{{"arrays", arrays}};
  return atomic_write_text(root_ / "arrays.json", doc.dump(2), error);
}

bool SessionPackage::write_events_json(std::string& error) {
  json cps = json::array();
  for (const auto& c : checkpoints_) {
    cps.push_back({{"checkpointId", c.checkpoint_id},
                   {"originalTimestampNs", std::to_string(c.original_timestamp_ns)},
                   {"effectiveTimestampNs", std::to_string(c.effective_timestamp_ns)},
                   {"name", c.name},
                   {"createdVia", c.created_via}});
  }
  if (!atomic_write_text(root_ / "events" / "checkpoints.json", cps.dump(2),
                         error)) {
    return false;
  }
  json anns = json::array();
  for (const auto& a : annotations_) {
    anns.push_back({{"annotationId", a.annotation_id},
                    {"timestampNs", std::to_string(a.timestamp_ns)},
                    {"text", a.text},
                    {"createdVia", a.created_via}});
  }
  if (!atomic_write_text(root_ / "events" / "annotations.json", anns.dump(2),
                         error)) {
    return false;
  }
  json syncs = json::array();
  for (const auto& s : sync_anchors_) {
    syncs.push_back({{"syncAnchorId", s.sync_anchor_id},
                     {"timestampNs", std::to_string(s.timestamp_ns)},
                     {"mechanism", s.mechanism},
                     {"createdVia", s.created_via}});
  }
  return atomic_write_text(root_ / "events" / "sync_anchors.json", syncs.dump(2),
                           error);
}

bool SessionPackage::ensure_source_metadata(const PackageStreamDesc& desc,
                                            std::string& error) {
  const auto src_dir = root_ / "sources" / desc.source_id;
  const auto stream_dir = src_dir / "streams" / desc.stream_id;
  std::error_code ec;
  std::filesystem::create_directories(stream_dir / "segments", ec);
  std::filesystem::create_directories(src_dir / "health", ec);

  json source = {{"sourceId", desc.source_id},
                 {"sourceType", desc.source_type},
                 {"alias", desc.alias},
                 {"pluginId", "sim.builtin"},
                 {"pluginVersion", "0.1.0"},
                 {"enabled", true},
                 {"metadata", {{"modality", desc.modality}}}};
  if (!atomic_write_text(src_dir / "source.json", source.dump(2), error)) {
    return false;
  }
  json stream = {{"streamId", desc.stream_id},
                 {"sourceId", desc.source_id},
                 {"modality", desc.modality},
                 {"nominalRateHz", desc.nominal_rate_hz},
                 {"dataSchemaId", data_schema_for(desc.modality)},
                 {"dataSchemaVersion", "1"}};
  return atomic_write_text(stream_dir / "stream.json", stream.dump(2), error);
}

void SessionPackage::record_external_segment(const SealedSegmentInfo& info) {
  on_segment_sealed(info);
}

void SessionPackage::on_segment_sealed(const SealedSegmentInfo& info) {
  IntegrityEntry e;
  e.path = info.relative_path.generic_string();
  e.size_bytes = info.size_bytes;
  e.hash_blake3_hex = info.hash_blake3_hex;
  e.start_session_time_ns = info.start_session_time_ns;
  e.end_session_time_ns = info.end_session_time_ns;
  e.actual_count = info.actual_count;
  e.expected_count = info.actual_count;
  e.status = "sealed";
  e.source_id = info.source_id;
  e.stream_id = info.stream_id;
  if (e.source_id.empty() || e.stream_id.empty()) {
    for (const auto& [sid, desc] : stream_descs_) {
      if (e.path.find(desc.source_id) != std::string::npos ||
          e.path.find(desc.stream_id) != std::string::npos) {
        e.source_id = desc.source_id;
        e.stream_id = desc.stream_id;
        break;
      }
    }
  }
  integrity_.push_back(e);
  ++sealed_segment_count_;
  std::string err;
  write_integrity(err);
  journal_.append(
      info.end_session_time_ns, wall_now_utc(), "SEGMENT_ROTATED", e.source_id,
      e.stream_id,
      json({{"path", e.path},
            {"size_bytes", e.size_bytes},
            {"start_ns", e.start_session_time_ns},
            {"end_ns", e.end_session_time_ns}})
          .dump(),
      err);
}

bool SessionPackage::begin_recording(const std::vector<PackageStreamDesc>& streams,
                                     int64_t t0_qpc_ticks, int64_t qpc_frequency,
                                     const std::string& t0_wall_utc,
                                     int64_t t0_uncertainty_ns,
                                     std::string& error) {
  std::lock_guard lock(mu_);
  t0_qpc_ticks_ = t0_qpc_ticks;
  qpc_frequency_ = qpc_frequency;
  t0_wall_utc_ = t0_wall_utc;
  t0_uncertainty_ns_ = t0_uncertainty_ns;
  source_ids_.clear();
  auto schema = load_schema_data();

  for (const auto& desc : streams) {
    if (!ensure_source_metadata(desc, error)) {
      return false;
    }
    source_ids_.push_back(desc.source_id);
    stream_descs_[desc.stream_id] = desc;

    if (!desc.external_segments) {
      StreamWriterConfig cfg;
      cfg.source_id = desc.source_id;
      cfg.stream_id = desc.stream_id;
      cfg.modality = desc.modality;
      cfg.data_schema_id = data_schema_for(desc.modality);
      cfg.schema_data = schema;
      cfg.nominal_rate_hz = desc.nominal_rate_hz;
      cfg.rotate_bytes = opts_.rotate_bytes;
      cfg.rotate_session_ns = opts_.rotate_session_ns;

      auto writer = std::make_unique<McapStreamWriter>();
      const auto seg_dir = root_ / "sources" / desc.source_id / "streams" /
                           desc.stream_id / "segments";
      if (!writer->open(seg_dir, root_, cfg, error)) {
        return false;
      }
      writer->set_rotate_callback(
          [this](const SealedSegmentInfo& info) { on_segment_sealed(info); });
      writers_[desc.stream_id] = std::move(writer);
    }

    if (!journal_.append(0, wall_now_utc(), "SOURCE_STARTED", desc.source_id,
                         desc.stream_id, "{}", error)) {
      return false;
    }
  }
  state_ = "recording";
  if (!write_manifest(error)) {
    return false;
  }
  if (!write_arrays_json(error)) {
    return false;
  }
  return journal_.append(0, wall_now_utc(), "SESSION_STARTED", "", "",
                         json({{"t0_wall_utc", t0_wall_utc_}}).dump(), error);
}

bool SessionPackage::write_sample(const std::string& stream_id,
                                  const SamplePoint& sample, std::string& error) {
  std::lock_guard lock(mu_);
  if (writes_blocked_) {
    error = "WRITE_BLOCKED";
    return false;
  }
  auto it = writers_.find(stream_id);
  if (it == writers_.end()) {
    error = "unknown stream";
    return false;
  }
  return it->second->append(sample, error);
}

bool SessionPackage::add_checkpoint(const std::string& checkpoint_id,
                                    int64_t ts_ns, const std::string& name,
                                    const std::string& created_via,
                                    std::string& error) {
  std::lock_guard lock(mu_);
  checkpoints_.push_back({checkpoint_id, ts_ns, ts_ns, name, created_via});
  if (!write_events_json(error)) {
    return false;
  }
  return journal_.append(
      ts_ns, wall_now_utc(), "CHECKPOINT_CREATED", "", "",
      json({{"checkpoint_id", checkpoint_id}, {"name", name}}).dump(), error);
}

bool SessionPackage::add_annotation(const std::string& annotation_id,
                                    int64_t ts_ns, const std::string& text,
                                    const std::string& created_via,
                                    std::string& error) {
  std::lock_guard lock(mu_);
  annotations_.push_back({annotation_id, ts_ns, text, created_via});
  if (!write_events_json(error)) {
    return false;
  }
  return journal_.append(
      ts_ns, wall_now_utc(), "ANNOTATION", "", "",
      json({{"annotation_id", annotation_id}, {"text", text}}).dump(), error);
}

bool SessionPackage::add_sync_anchor(const std::string& sync_id, int64_t ts_ns,
                                     const std::string& mechanism,
                                     const std::string& created_via,
                                     std::string& error) {
  std::lock_guard lock(mu_);
  sync_anchors_.push_back({sync_id, ts_ns, mechanism, created_via});
  if (!write_events_json(error)) {
    return false;
  }
  return journal_.append(
      ts_ns, wall_now_utc(), "SYNC_ANCHOR", "", "",
      json({{"sync_anchor_id", sync_id}, {"mechanism", mechanism}}).dump(),
      error);
}

bool SessionPackage::open_gap(const std::string& source_id,
                              const std::string& stream_id,
                              const std::string& cause, int64_t start_ns,
                              std::string& error) {
  std::lock_guard lock(mu_);
  const auto path =
      root_ / "sources" / source_id / "health" / "gaps.jsonl";
  std::ofstream out(path, std::ios::app);
  if (!out) {
    error = "failed to open gaps.jsonl";
    return false;
  }
  out << json({{"cause", cause},
               {"start_session_time_ns", start_ns},
               {"end_session_time_ns", nullptr},
               {"stream_id", stream_id}})
             .dump()
      << "\n";
  return journal_.append(
      start_ns, wall_now_utc(), "GAP_OPENED", source_id, stream_id,
      json({{"cause", cause}}).dump(), error);
}

bool SessionPackage::close_gap(const std::string& stream_id, int64_t end_ns,
                               std::string& error) {
  std::lock_guard lock(mu_);
  auto it = stream_descs_.find(stream_id);
  if (it == stream_descs_.end()) {
    error = "unknown stream";
    return false;
  }
  return journal_.append(end_ns, wall_now_utc(), "GAP_CLOSED",
                         it->second.source_id, stream_id, "{}", error);
}

bool SessionPackage::journal_event(const std::string& kind,
                                   int64_t session_time_ns,
                                   const std::string& source_id,
                                   const std::string& stream_id,
                                   const std::string& payload_json,
                                   std::string& error) {
  std::lock_guard lock(mu_);
  return journal_.append(session_time_ns, wall_now_utc(), kind, source_id,
                         stream_id, payload_json, error);
}

void SessionPackage::poll_disk() {
  std::lock_guard lock(mu_);
  if (!watchdog_) {
    return;
  }
  watchdog_->poll();
  const bool floor = watchdog_->at_hard_floor();
  if (floor && !writes_blocked_) {
    writes_blocked_ = true;
    for (auto& [_, w] : writers_) {
      w->set_writes_blocked(true);
    }
    if (!write_blocked_journaled_) {
      std::string err;
      journal_.append(0, wall_now_utc(), "WRITE_BLOCKED", "", "", "{}", err);
      write_blocked_journaled_ = true;
      for (const auto& [sid, desc] : stream_descs_) {
        const auto path =
            root_ / "sources" / desc.source_id / "health" / "gaps.jsonl";
        std::ofstream out(path, std::ios::app);
        if (out) {
          out << json({{"cause", "WRITER_ERROR"},
                       {"start_session_time_ns", 0},
                       {"stream_id", sid}})
                     .dump()
              << "\n";
        }
        journal_.append(0, wall_now_utc(), "GAP_OPENED", desc.source_id, sid,
                        json({{"cause", "WRITER_ERROR"}}).dump(), err);
      }
    }
  } else if (!floor && writes_blocked_) {
    writes_blocked_ = false;
    write_blocked_journaled_ = false;
    for (auto& [_, w] : writers_) {
      w->set_writes_blocked(false);
    }
    std::string err;
    journal_.append(0, wall_now_utc(), "WRITE_RESUMED", "", "", "{}", err);
  }
}

void SessionPackage::set_free_bytes_override(std::optional<int64_t> bytes) {
  std::lock_guard lock(mu_);
  if (watchdog_) {
    watchdog_->set_free_bytes_override(bytes);
  }
}

bool SessionPackage::finalize(std::string& error) {
  std::lock_guard lock(mu_);
  for (auto& [sid, w] : writers_) {
    if (!w->close(error)) {
      return false;
    }
    (void)sid;
  }
  writers_.clear();
  state_ = "finalized";
  if (!write_events_json(error)) {
    return false;
  }
  if (!write_integrity(error)) {
    return false;
  }
  if (!write_manifest(error)) {
    return false;
  }
  return journal_.append(0, wall_now_utc(), "FINALIZED", "", "", "{}", error);
}

int64_t SessionPackage::sample_count(const std::string& stream_id) const {
  std::lock_guard lock(mu_);
  auto it = writers_.find(stream_id);
  if (it == writers_.end() || !it->second) {
    // After finalize, writers cleared — sum from integrity.
    int64_t n = 0;
    for (const auto& e : integrity_) {
      if (e.stream_id == stream_id) {
        n += e.actual_count;
      }
    }
    return n;
  }
  return it->second->total_samples();
}

int64_t SessionPackage::total_samples() const {
  std::lock_guard lock(mu_);
  int64_t n = 0;
  if (!writers_.empty()) {
    for (const auto& [_, w] : writers_) {
      n += w->total_samples();
    }
    return n;
  }
  for (const auto& e : integrity_) {
    n += e.actual_count;
  }
  return n;
}

}  // namespace capture::storage
