# Complete historical archive

This directory includes the **entire Metric Human Lab historical bundle** (v0.1.0–v0.3.0), divided into byte-identical parts because the original 11.1 MB GitHub upload was rejected by the transfer channel.

Run `python reassemble.py` from any working directory. The script joins `parts/` in order and verifies every SHA-256 and the final 11,138,870-byte ZIP hash. After verification, the reconstructed ZIP contains the original sources, demo viewer, binary meshes, release wheels, synthetic test evidence, and prior version archives.

The browsable current v0.3.0 source is in the parent folder. No pretrained weights or real-person datasets are bundled.
