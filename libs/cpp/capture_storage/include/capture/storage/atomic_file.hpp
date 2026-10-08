// SPDX-License-Identifier: GPL-3.0-only
#pragma once

#include <filesystem>
#include <string>
#include <string_view>

namespace capture::storage {

// Write bytes via a temporary file then atomic replace (one writer per path).
// Windows creates an exclusive sibling, flushes its open handle, then uses
// MoveFileExW with replacement and write-through flags. Existing path.tmp files
// and links are not reused or removed.
// POSIX creates an exclusive temporary file in the opened parent directory;
// pre-existing files, including path.tmp, are not reused or removed.
// Success on POSIX requires syncing the written descriptor and parent directory.
// If directory sync fails after replacement, returns false with an explicit
// diagnostic; the destination already contains the complete new bytes.
bool atomic_write_bytes(const std::filesystem::path& path,
                        std::string_view bytes, std::string& error);

bool atomic_write_text(const std::filesystem::path& path, std::string_view text,
                       std::string& error);

std::string read_text_file(const std::filesystem::path& path, std::string& error);

}  // namespace capture::storage
