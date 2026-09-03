// SPDX-License-Identifier: GPL-3.0-only
#pragma once

#include <cstddef>
#include <cstdint>
#include <span>
#include <stdexcept>
#include <string>
#include <vector>

namespace capture {

inline constexpr uint32_t kFrameMagic = 0x31505343u;  // "CSP1"
inline constexpr std::size_t kFrameHeaderSize = 16;
inline constexpr uint32_t kMaxPayloadLen = 8u * 1024u * 1024u;

struct Frame {
  uint32_t message_type = 0;
  uint32_t correlation_id = 0;
  std::vector<uint8_t> payload;
};

class FrameError : public std::runtime_error {
 public:
  using std::runtime_error::runtime_error;
};

std::vector<uint8_t> encode_frame(uint32_t message_type,
                                  std::span<const uint8_t> payload,
                                  uint32_t correlation_id = 0);

// Decode one frame from the start of buffer.
// Returns bytes consumed. Throws FrameError on bad magic/size.
// Throws std::runtime_error with "incomplete" if more data needed.
std::size_t decode_frame(std::span<const uint8_t> buffer, Frame& out);

class FrameDecoder {
 public:
  void feed(std::span<const uint8_t> data);
  bool pop(Frame& out);
  void reset();

 private:
  std::vector<uint8_t> buf_;
};

}  // namespace capture
