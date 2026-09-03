# v0.1.0 cut checklist (operator)

Local CaptureSuite git repo is initialized with the public tree. Complete these
on your machine:

1. Create an empty GitHub repository (do **not** push to `uci-pose-realtime`).
2. Point `CITATION.cff` `repository-code` at the real URL.
3. Add the remote and push:
   ```powershell
   cd C:\SoangraLab\CaptureSuite
   git remote add origin https://github.com/<you>/CaptureSuite.git
   git push -u origin main
   ```
4. Enable branch protection on `main` (require CI).
5. Connect [Zenodo](https://zenodo.org/) to the GitHub repo.
6. Tag and push the release:
   ```powershell
   git tag -a v0.1.0 -m "CaptureSuite 0.1.0"
   git push origin v0.1.0
   ```
7. Paste the Zenodo DOI into `CITATION.cff` and the README badge; commit + push.
8. Confirm the Release workflow attached `CaptureSuite-v0.1.0-win64.zip` and
   `capture_desktop.exe`.

Lab-only trees were moved to `C:\SoangraLab\_lab_sidecar\` (UrologyMoCap,
RadarKinematicsML, data, weights, etc.) and are **not** part of this repo.
