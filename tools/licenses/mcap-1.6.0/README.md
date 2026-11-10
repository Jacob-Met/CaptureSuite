MCAP Python 1.6.0 license fallback
================================

The published wheel and source distribution omit the license text. This is the
unaltered LICENSE from upstream tag releases/python/mcap/v1.6.0 at commit
ceaf05f1c33a7b8bca567092865d52cf41639e2d:
https://github.com/foxglove/mcap/blob/ceaf05f1c33a7b8bca567092865d52cf41639e2d/LICENSE

SHA-256: da11235665c17d4c1634072dae92b8ba1b38d6fdde2ccf19a6bbede33253f58d

Only used when the installed mcap version is exactly 1.6.0 and has no notice
files. Other missing notices fail the bundle build rather than guessing terms.
