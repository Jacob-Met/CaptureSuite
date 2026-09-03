// SPDX-License-Identifier: GPL-3.0-only
#pragma once

#include <cstdint>
#include <filesystem>
#include <string>
#include <string_view>
#include <vector>

namespace capture::storage {

std::string blake3_hex(std::string_view data);
std::string blake3_file_hex(const std::filesystem::path& path, std::string& error);

}  // namespace capture::storage
