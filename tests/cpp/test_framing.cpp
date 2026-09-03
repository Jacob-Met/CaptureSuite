// SPDX-License-Identifier: GPL-3.0-only
#include <catch2/catch_test_macros.hpp>

#include "capture/framing.hpp"

TEST_CASE("encode/decode CSP1 frame round-trip", "[framing]") {
  const std::vector<uint8_t> payload = {'h', 'i'};
  auto bytes = capture::encode_frame(1, payload, 42);
  REQUIRE(bytes.size() == capture::kFrameHeaderSize + payload.size());

  capture::Frame frame;
  const auto consumed = capture::decode_frame(bytes, frame);
  REQUIRE(consumed == bytes.size());
  REQUIRE(frame.message_type == 1);
  REQUIRE(frame.correlation_id == 42);
  REQUIRE(frame.payload == payload);
}

TEST_CASE("FrameDecoder reassembles split reads", "[framing]") {
  const std::vector<uint8_t> payload(100, 0xAB);
  auto bytes = capture::encode_frame(7, payload, 9);

  capture::FrameDecoder dec;
  dec.feed(std::span<const uint8_t>(bytes.data(), 8));
  capture::Frame frame;
  REQUIRE_FALSE(dec.pop(frame));

  dec.feed(std::span<const uint8_t>(bytes.data() + 8, bytes.size() - 8));
  REQUIRE(dec.pop(frame));
  REQUIRE(frame.message_type == 7);
  REQUIRE(frame.payload.size() == 100);
}

TEST_CASE("bad magic rejects frame", "[framing]") {
  std::vector<uint8_t> junk(20, 0);
  capture::Frame frame;
  REQUIRE_THROWS_AS(capture::decode_frame(junk, frame), capture::FrameError);
}
