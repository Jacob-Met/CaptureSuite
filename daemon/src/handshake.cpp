// SPDX-License-Identifier: GPL-3.0-only
#include "capture_daemon/handshake.hpp"

#include "capture/version.hpp"

#include <algorithm>
#include <cstdint>
#include <string>

namespace capture::daemon {
namespace {

capture::v1::VersionInfo make_version() {
  capture::v1::VersionInfo info;
  info.set_major(0);
  info.set_minor(1);
  info.set_patch(0);
  info.set_git_describe(capture::version_string());
  return info;
}

capture::v1::HelloAck reject(const std::string& instance_id, const std::string& code,
                             const std::string& message) {
  capture::v1::HelloAck ack;
  ack.set_accepted(false);
  ack.mutable_negotiated()->set_major(kProtocolMajor);
  ack.mutable_negotiated()->set_minor(kProtocolMinor);
  *ack.mutable_daemon() = make_version();
  ack.set_instance_id(instance_id);
  ack.mutable_error()->set_code(code);
  ack.mutable_error()->set_message(message);
  return ack;
}

bool protocol_in_range(int daemon_major, int daemon_minor,
                       const capture::v1::ProtocolVersion& min_v,
                       const capture::v1::ProtocolVersion& max_v) {
  const auto key = [](int major, int minor) {
    return (static_cast<int64_t>(major) << 32) | static_cast<uint32_t>(minor);
  };
  return key(min_v.major(), min_v.minor()) <= key(daemon_major, daemon_minor) &&
         key(daemon_major, daemon_minor) <= key(max_v.major(), max_v.minor());
}

}  // namespace

capture::v1::HelloAck negotiate_hello(const capture::v1::Hello& hello,
                                      const std::string& instance_id) {
  if (hello.protocol().major() != kProtocolMajor) {
    return reject(instance_id, "PROTOCOL_MISMATCH",
                  "protocol major mismatch: peer=" +
                      std::to_string(hello.protocol().major()) +
                      " daemon=" + std::to_string(kProtocolMajor));
  }

  if (hello.role() == "worker") {
    if (hello.plugin_id().empty()) {
      return reject(instance_id, "INVALID_HELLO",
                    "worker Hello must include plugin_id");
    }
    if (!protocol_in_range(kProtocolMajor, kProtocolMinor,
                           hello.min_daemon_protocol(),
                           hello.max_daemon_protocol())) {
      return reject(instance_id, "PLUGIN_INCOMPATIBLE",
                    "daemon outside plugin protocol range");
    }
  }

  capture::v1::HelloAck ack;
  ack.set_accepted(true);
  ack.mutable_negotiated()->set_major(kProtocolMajor);
  const int negotiated_minor = static_cast<int>(
      std::min(hello.protocol().minor(),
               static_cast<uint32_t>(kProtocolMinor)));
  ack.mutable_negotiated()->set_minor(negotiated_minor);
  *ack.mutable_daemon() = make_version();
  ack.set_instance_id(instance_id);
  return ack;
}

}  // namespace capture::daemon
