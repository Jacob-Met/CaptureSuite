"""Optional, permissively licensed neural *evidence* adapters.

There is intentionally no dependency between reconstruction geometry and any
particular neural model. This module outputs ordinary PNG masks and relative
NPY depth arrays that can be independently inspected and replaced. No output
from a neural predictor is certified as metric body geometry.

No model weights are bundled. First use downloads weights from Hugging Face if
networking is enabled in the user's environment; processing then runs locally.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Callable, Sequence

import cv2
import numpy as np
from PIL import Image

from .reconstruct import mask_from_image

SAM2_DEFAULT = "facebook/sam2.1-hiera-tiny"
DEPTH_DEFAULT = "depth-anything/Depth-Anything-V2-Small-hf"


def _load_images(images: Sequence[str | Path]) -> list[tuple[Path, Image.Image]]:
    if not images:
        raise ValueError("Provide at least one source image")
    result = []
    for item in images:
        path = Path(item).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"No source image at {path}")
        with Image.open(path) as raw:
            img = raw.convert("RGB")
        if min(img.size) < 16:
            raise ValueError(f"Image is too small for meaningful inference: {path}")
        result.append((path, img))
    return result


def _source_record(path: Path, img: Image.Image) -> dict:
    return {
        "path": str(path),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "image_size_wh": list(img.size),
    }


def _prepare_box(box: Sequence[float], width: int, height: int) -> tuple[float, ...]:
    if len(box) != 4 or any(not np.isfinite(x) for x in box):
        raise ValueError("Bounding box must have four finite coordinates")
    x0, y0, x1, y1 = [float(x) for x in box]
    if not (0 <= x0 < x1 <= width and 0 <= y0 < y1 <= height):
        raise ValueError(f"Bounding box outside image or empty: {box}")
    if (x1 - x0) * (y1 - y0) < 64:
        raise ValueError("SAM2 prompt box is too small")
    return (x0, y0, x1, y1)


def _guess_box(image_path: Path, width: int, height: int) -> tuple[float, ...]:
    """Weak auto-prompt from GrabCut: an *initialization*, not a person detector."""
    mask = mask_from_image(str(image_path))
    yy, xx = np.nonzero(mask)
    if not len(xx):
        raise ValueError("Could not infer SAM2 bounding box; supply --boxes-json")
    margin = max(4, int(round(min(width, height) * .035)))
    return _prepare_box((max(0, int(xx.min()) - margin),
                         max(0, int(yy.min()) - margin),
                         min(width, int(xx.max()) + margin + 1),
                         min(height, int(yy.max()) + margin + 1)), width, height)


def _make_sam2_predictor(model_id: str, revision: str | None, device: str):
    try:
        import torch
        from transformers import Sam2Model, Sam2Processor
    except ImportError as exc:
        raise RuntimeError("SAM2 adapter requires the optional 'vision' dependencies: pip install '.[vision]'") from exc
    actual_device = "cuda" if device == "auto" and torch.cuda.is_available() else ("cpu" if device == "auto" else device)
    opts = {} if revision is None else {"revision": revision}
    processor = Sam2Processor.from_pretrained(model_id, **opts)
    model = Sam2Model.from_pretrained(model_id, **opts).to(actual_device).eval()
    def predict(img: Image.Image, box: tuple[float, ...]) -> np.ndarray:
        inputs = processor(images=img, input_boxes=[[list(box)]], return_tensors="pt").to(actual_device)
        with torch.inference_mode():
            outputs = model(**inputs, multimask_output=False)
        masks = processor.post_process_masks(outputs.pred_masks.cpu(), inputs["original_sizes"])[0]
        return np.asarray(masks.detach().cpu().numpy() if hasattr(masks, "detach") else masks).squeeze()
    return predict, getattr(model.config, "_commit_hash", None)


def _make_depth_predictor(model_id: str, revision: str | None, device: str):
    try:
        import torch
        from transformers import pipeline
    except ImportError as exc:
        raise RuntimeError("Depth adapter requires the optional 'vision' dependencies: pip install '.[vision]'") from exc
    actual_device = "cuda:0" if device == "auto" and torch.cuda.is_available() else ("cpu" if device == "auto" else device)
    opts = {} if revision is None else {"revision": revision}
    pipe = pipeline(task="depth-estimation", model=model_id, device=actual_device, **opts)
    def predict(img: Image.Image) -> np.ndarray:
        result = pipe(img)
        if "predicted_depth" not in result:
            raise ValueError("Depth pipeline produced no predicted_depth array")
        depth = result["predicted_depth"]
        return np.asarray(depth.detach().cpu().numpy() if hasattr(depth, "detach") else depth)
    return predict, getattr(getattr(pipe.model, "config", None), "_commit_hash", None)


def _binary_mask_from_prediction(predicted: np.ndarray) -> np.ndarray:
    """Accept bool, foreground probabilities, or signed logits without guessing."""
    values = np.asarray(predicted)
    if values.ndim != 2 or not np.all(np.isfinite(values)):
        raise ValueError("Segmentation evidence must be a finite 2D array")
    if values.dtype == np.bool_:
        return values
    if np.issubdtype(values.dtype, np.integer):
        return values > 0
    if np.issubdtype(values.dtype, np.floating):
        if float(values.min()) >= 0 and float(values.max()) <= 1:
            return values > .5
        return values > 0  # threshold for signed logits
    raise ValueError("Unsupported segmentation mask dtype")


def generate_sam2_masks(
    images: Sequence[str | Path], output_dir: str | Path, *,
    boxes: Sequence[Sequence[float]] | None = None,
    model_id: str = SAM2_DEFAULT,
    revision: str | None = None,
    device: str = "auto",
    predictor: Callable[[Image.Image, tuple[float, ...]], np.ndarray] | None = None,
) -> dict:
    """Write human-*prompted* foreground masks and evidence manifest.

    When boxes is absent, attempts a weak initial GrabCut box. SAM2 is a
    general segmenter, not an automated human identifier or body-shape model.
    `predictor` is a test-only injection point for offline contract tests.
    """
    loaded = _load_images(images)
    if boxes is not None and len(boxes) != len(loaded):
        raise ValueError("Supply exactly one bounding box per image")
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    commit = None
    if predictor is None:
        predictor, commit = _make_sam2_predictor(model_id, revision, device)
    entries = []
    for i, (path, img) in enumerate(loaded):
        w, h = img.size
        box = _prepare_box(boxes[i], w, h) if boxes is not None else _guess_box(path, w, h)
        predicted = np.asarray(predictor(img, box))
        if predicted.ndim != 2:
            raise ValueError(f"SAM2 predictor must return a 2D mask, got {predicted.shape}")
        if predicted.shape != (h, w):
            raise ValueError(f"SAM2 output shape {predicted.shape} != source {(h,w)}")
        if not np.all(np.isfinite(predicted)):
            raise ValueError("SAM2 returned nonfinite mask probabilities/logits")
        mask = _binary_mask_from_prediction(predicted)
        mask_u8 = (mask.astype(np.uint8) * 255)
        count, labels, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), 8)
        if count <= 1:
            raise ValueError(f"SAM2 produced no foreground for {path}")
        largest = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        mask_u8 = np.asarray(labels == largest, np.uint8) * 255
        fraction = float(np.mean(mask_u8 > 0))
        if not .001 < fraction < .95:
            raise ValueError(f"SAM2 foreground fraction {fraction:.3f} implausible for {path}")
        dest = out / f"mask_{i:02d}.png"
        if not cv2.imwrite(str(dest), mask_u8):
            raise OSError(f"Could not save mask: {dest}")
        entries.append({**_source_record(path, img), "mask": dest.name,
                        "prompt_box_xyxy": list(box), "foreground_fraction": fraction})
    report = {
        "kind": "segmentation_evidence_not_ground_truth",
        "model_id": model_id, "requested_revision": revision,
        "resolved_revision": commit,
        "model_license_review_required": model_id != SAM2_DEFAULT,
        "default_model_license": "Apache-2.0 (SAM2.1 Hiera Tiny, independently verify downloaded checkpoint)",
        "units": "foreground_pixels",
        "camera_pose_calibrated": False,
        "body_shape_or_scale_validated": False,
        "records": entries,
    }
    (out / "vision_manifest.json").write_text(json.dumps(report, indent=2), encoding="utf8")
    return report


def generate_relative_depth(
    images: Sequence[str | Path], output_dir: str | Path, *,
    model_id: str = DEPTH_DEFAULT,
    revision: str | None = None,
    device: str = "auto",
    predictor: Callable[[Image.Image], np.ndarray] | None = None,
) -> dict:
    """Write relative (unscaled, uncalibrated) depth arrays, never metric maps."""
    loaded = _load_images(images)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    commit = None
    if predictor is None:
        predictor, commit = _make_depth_predictor(model_id, revision, device)
    entries = []
    for i, (path, img) in enumerate(loaded):
        w, h = img.size
        raw = np.asarray(predictor(img), dtype=np.float32).squeeze()
        if raw.ndim != 2:
            raise ValueError(f"Relative-depth predictor must return a 2D map, got {raw.shape}")
        if raw.size == 0 or not np.all(np.isfinite(raw)):
            raise ValueError("Relative-depth predictor returned invalid map")
        if raw.shape != (h, w):
            raw = cv2.resize(raw, (w, h), interpolation=cv2.INTER_LINEAR)
        dest = out / f"relative_depth_{i:02d}.npy"
        np.save(dest, raw, allow_pickle=False)
        entries.append({**_source_record(path, img), "relative_depth": dest.name,
                        "relative_value_min": float(raw.min()),
                        "relative_value_max": float(raw.max()),
                        "metric_depth": False})
    report = {
        "kind": "relative_depth_evidence_not_metric_depth",
        "model_id": model_id, "requested_revision": revision,
        "resolved_revision": commit,
        "model_license_review_required": model_id != DEPTH_DEFAULT,
        "default_model_license": "Apache-2.0 (Depth Anything V2 Small, independently verify downloaded checkpoint)",
        "units": "unscaled_model_relative_values_NOT_meters",
        "depth_increases_with_camera_distance": "unknown_do_not_assume",
        "calibrated_to_metric": False,
        "may_be_used_for_hard_carving": False,
        "records": entries,
    }
    (out / "vision_manifest.json").write_text(json.dumps(report, indent=2), encoding="utf8")
    return report
