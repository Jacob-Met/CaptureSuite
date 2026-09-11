# SPDX-License-Identifier: GPL-3.0-only
"""Experimental radar motion inference primitives.

The seed is intentionally conservative: live descriptors are physically interpretable,
while learned kinematics require an externally trained, provenance-carrying model.
"""

from .seed import (
    FEATURE_NAMES,
    LinearKinematicsModel,
    MotionDescriptor,
    RadarMotionFeaturizer,
    SyntheticSequence,
    fit_ridge_model,
    generate_synthetic_sequence,
)

__all__ = [
    "FEATURE_NAMES",
    "LinearKinematicsModel",
    "MotionDescriptor",
    "RadarMotionFeaturizer",
    "SyntheticSequence",
    "fit_ridge_model",
    "generate_synthetic_sequence",
]
