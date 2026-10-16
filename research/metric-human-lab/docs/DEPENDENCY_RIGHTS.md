# Dataset, model and asset licensing audit (research planning)

**Open source is not automatically open data or open model weights.** This project currently ships no third-party models or human scans. External model use needs a separate review of code, checkpoint, weights, images, scans, and outputs.

| Candidate | Status for a permissive source release | Notes |
|---|---|---|
| MakeHuman **core** mesh/morph **assets** | Pinned 7-file CC0 asset path with independently verified SHA-256; no app code redistributed | MakeHuman application source is AGPL; keep code licensing separate. Third-party community assets may differ. https://github.com/makehumancommunity/makehuman/blob/master/LICENSE.md |
| OxiHuman | Promising optional parametric prior: Apache-2.0 code, CC0 packed data | Check exact version and binary pack provenance. https://github.com/cool-japan/oxihuman |
| Depth Anything V2 **Small** | Implemented optional `infer-depth` adapter; Apache-2.0 according to upstream | Base/Large/Giant models differ (CC-BY-NC-4.0); relative depth is **not metric** by default. https://huggingface.co/depth-anything/Depth-Anything-V2-Small-hf |
| SAM2.1 Hiera Tiny | Implemented optional bounding-box `segment-sam2` adapter; model card Apache-2.0 | Prompted segmentation is not a verified person recognizer and outputs must be inspected. https://huggingface.co/facebook/sam2.1-hiera-tiny |
| MediaPipe Pose Landmarker | Possible optional landmark adapter | Apache-2.0 code; separately confirm the chosen downloadable task/model weight terms. https://github.com/google-ai-edge/mediapipe |
| THuman2.0/2.1 | **Not redistributable**, restricted noncommercial research only | Upstream explicitly forbids re-sharing the dataset/derived data without permission. https://github.com/ytrock/THuman2.0-Dataset |
| SMPL-X | **Not compatible for bundling under MIT by default** | Research-focused, noncommercial source/model licensing. https://github.com/vchoutas/smplx |
| Original VGGT weights | Noncommercial model weights; do not bundle by default | A distinct newer commercial checkpoint has its own agreement. https://github.com/facebookresearch/vggt |

**Action policy:** Code in `src/` and first-party procedural benchmarks use no restricted data. Dataset download/synthesis scripts must require positive operator identification of lawful rights before importing scans. Train/evaluate artifacts must record source hashes, model versions, license status, and actual subject splits before claiming accuracy.

| TEXEL BodyScan | External evaluation candidate only, data **CC-BY-NC-4.0** | The associated parser code is MIT, but human images and scans are not MIT. Requires a subject-rights audit and cannot be included in this source release. https://github.com/m-krivov/Texel-BodyScan-Dataset |
