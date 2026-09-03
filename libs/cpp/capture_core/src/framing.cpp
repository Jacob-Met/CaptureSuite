// SPDX-License-Identifier: GPL-3.0-only
#include "capture/framing.hpp"

#include <cstring>
#include <stdexcept>

namespace capture {
namespace {

void write_u32_le(uint8_t* dst, uint32_t value) {
  dst[0] = static_cast<uint8_t>(value & 0xFF);
  dst[1] = static_cast<uint8_t>((value >> 8) & 0xFF);
  dst[2] = static_cast<uint8_t>((value >> 16) & 0xFF);
  dst[3] = static_cast<uint8_t>((value >> 24) & 0xFF);
}

uint32_t read_u32_le(const uint8_t* src) {
  return static_cast<uint32_t>(src[0]) |
         (static_cast<uint32_t>(src[1]) << 8) |
         (static_cast<uint32_t>(src[2]) << 16) |
         (static_cast<uint32_t>(src[3]) << 24);
}

}  // namespace

std::vector<uint8_t> encode_frame(uint32_t message_type,
                                  std::span<const uint8_t> payload,
                                  uint32_t correlation_id) {
  if (payload.size() > kMaxPayloadLen) {
    throw FrameError("payload exceeds max length");
  }
  std::vector<uint8_t> out(kFrameHeaderSize + payload.size());
  write_u32_le(out.data() + 0, kFrameMagic);
  write_u32_le(out.data() + 4, static_cast<uint32_t>(payload.size()));
  write_u32_le(out.data() + 8, message_type);
  write_u32_le(out.data() + 12, correlation_id);
  if (!payload.empty()) {
    std::memcpy(out.data() + kFrameHeaderSize, payload.data(), payload.size());
  }
  return out;
}

std::size_t decode_frame(std::span<const uint8_t> buffer, Frame& out) {
  if (buffer.size() < kFrameHeaderSize) {
    throw std::runtime_error("incomplete header");
  }
  const uint32_t magic = read_u32_le(buffer.data());
  if (magic != kFrameMagic) {
    throw FrameError("bad magic");
  }
  const uint32_t payload_len = read_u32_le(buffer.data() + 4);
  if (payload_len > kMaxPayloadLen) {
    throw FrameError("payload_len exceeds max");
  }
  const std::size_t total = kFrameHeaderSize + payload_len;
  if (buffer.size() < total) {
    throw std::runtime_error("incomplete payload");
  }
  out.message_type = read_u32_le(buffer.data() + 8);
  out.correlation_id = read_u32_le(buffer.data() + 12);
  out.payload.assign(buffer.begin() + static_cast<std::ptrdiff_t>(kFrameHeaderSize),
                    buffer.begin() + static_cast<std::ptrdiff_t>(total));
  return total;
}

void FrameDecoder::feed(std::span<const uint8_t> data) {
  buf_.insert(buf_.end(), data.begin(), data.end());
}

bool FrameDecoder::pop(Frame& out) {
  try {
    const std::size_t consumed = decode_frame(buf_, out);
    buf_.erase(buf_.begin(),
               buf_.begin() + static_cast<std::ptrdiff_t>(consumed));
    return true;
  } catch (const std::runtime_error& ex) {
    const std::string msg = ex.what();
    if (msg.find("incomplete") != std::string::npos) {
      return false;
    }
    throw;
  }
}

void FrameDecoder::reset() { buf_.clear(); }

}  // namespace capture
