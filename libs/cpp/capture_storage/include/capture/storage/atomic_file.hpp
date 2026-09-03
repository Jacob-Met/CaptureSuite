// SPDX-License-Identifier: GPL-3.0-only
#pragma once

#include <filesystem>
#include <string>
#include <string_view>

namespace capture::storage {

// Write bytes to path via path.tmp then atomic replace.
bool atomic_write_bytes(const std::filesystem::path& path,
                        std::string_view bytes, std::string& error);

bool atomic_write_text(const std::filesystem::path& path, std::string_view text,
                       std::string& error);

std::string read_text_file(const std::filesystem::path& path, std::string& error);

}  // namespace capture::storage
