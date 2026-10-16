"""Optional image-space feature correspondences for two-view camera research.

Requires explicit foreground masks to avoid recovering the background camera
when the person rotates in front of a stationary phone. Geometric constancy of
clothing/body texture is NOT guaranteed by SIFT matches; use the relative-camera
solver's RANSAC, parallax and degeneracy gates. This is not human landmark
identification or evidence of calibrated body geometry.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path

import cv2
import numpy as np


@dataclass(frozen=True)
class FeatureMatches:
    pixels_first: dict[str, list[float]]
    pixels_second: dict[str, list[float]]
    input_sha256: dict[str, str]
    ratio_threshold: float

    def to_dict(self):
        return {
            'pixels_first': self.pixels_first,
            'pixels_second': self.pixels_second,
            'matched_features': len(self.pixels_first),
            'input_sha256': self.input_sha256,
            'matcher': 'bidirectional_SIFT_ratio_and_mutual_index',
            'ratio_threshold': self.ratio_threshold,
            'target_static_correspondence_verified': False,
            'body_geometry_accuracy_verified': False,
            'metric_scale_verified': False,
        }


def match_masked_rgb_features(image_first: str | Path, image_second: str | Path,
                              mask_first: str | Path, mask_second: str | Path, *,
                              ratio_threshold: float = 0.72,
                              max_features: int = 2500,
                              min_matches: int = 12) -> FeatureMatches:
    """Produce explicitly labeled pixel pairs from SIFT; never invent matches."""
    paths = [Path(p) for p in (image_first, image_second, mask_first, mask_second)]
    if len({p.resolve() for p in paths}) != len(paths):
        raise ValueError('Inputs must refer to four different source files')
    if not 0 < ratio_threshold < 1 or max_features < min_matches or min_matches < 12:
        raise ValueError('Invalid feature match thresholds')
    imgs = [cv2.imread(str(p), cv2.IMREAD_GRAYSCALE) for p in paths[:2]]
    masks = [cv2.imread(str(p), cv2.IMREAD_GRAYSCALE) for p in paths[2:]]
    if any(x is None for x in imgs + masks):
        raise ValueError('Could not read image or foreground mask')
    if any(img.shape != mask.shape for img, mask in zip(imgs, masks)):
        raise ValueError('Image and foreground mask dimensions disagree')
    if imgs[0].shape != imgs[1].shape:
        raise ValueError('Images must have the same dimensions for this adapter')
    if any(np.count_nonzero(m > 127) < 128 for m in masks):
        raise ValueError('Foreground mask is empty or tiny')
    feature_detector = cv2.SIFT_create(nfeatures=max_features)
    kp1, d1 = feature_detector.detectAndCompute(imgs[0], np.uint8(masks[0]>127) * 255)
    kp2, d2 = feature_detector.detectAndCompute(imgs[1], np.uint8(masks[1]>127) * 255)
    if d1 is None or d2 is None or len(d1)<min_matches or len(d2)<min_matches:
        raise ValueError('Insufficient foreground texture for feature matching')
    bf=cv2.BFMatcher(cv2.NORM_L2)

    def ratio_pairs(source, target):
        rows=bf.knnMatch(source, target, k=2)
        return {m.queryIdx: m.trainIdx for m, n in rows if m.distance < ratio_threshold*n.distance}

    forward = ratio_pairs(d1, d2)
    reverse = ratio_pairs(d2, d1)
    mutual = [(i, j) for i, j in sorted(forward.items()) if reverse.get(j)==i]
    if len(mutual) < min_matches:
        raise ValueError('Too few mutual foreground image matches')
    pixels_first={f'sift_{n:04d}':list(map(float,kp1[i].pt)) for n,(i,j) in enumerate(mutual)}
    pixels_second={f'sift_{n:04d}':list(map(float,kp2[j].pt)) for n,(i,j) in enumerate(mutual)}
    digests={label:hashlib.sha256(path.read_bytes()).hexdigest()
             for label,path in zip(('image_first','image_second','mask_first','mask_second'),paths)}
    return FeatureMatches(pixels_first,pixels_second,digests,ratio_threshold)
