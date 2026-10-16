"""Convert independently licensed MakeHuman *asset data* to our body-prior contract.

The importer is an original, standalone implementation of the simple OBJ and
sparse `.target` text formats. It does NOT depend on or copy MakeHuman AGPL
application code. Native mesh/target indices must remain in the exact source
OBJ order: trimesh's convenient OBJ loader is not safe for this indexing task.

A MakeHuman base mesh is an anatomical MODEL, not a scan of a real person.
Native unit conversion is an explicit hypothesis, not a measurement inferred
from photographs. The caller must verify the particular asset's license.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

import numpy as np

from .prior import Prior


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_index_preserving_obj(path: str | Path):
    """Read vertex positions and polygon faces, preserving OBJ vertex indices.

    Faces are triangulated with a fan. This reader deliberately ignores
    texture/normal indices; they are not vertex-coordinate indices.
    """
    vertices, faces = [], []
    path = Path(path)
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        parts = raw.strip().split()
        if not parts or parts[0].startswith('#'):
            continue
        if parts[0] == 'v':
            if len(parts) < 4:
                raise ValueError(f'{path}:{lineno} malformed vertex')
            vertices.append([float(s) for s in parts[1:4]])
        elif parts[0] == 'f':
            if len(parts) < 4:
                raise ValueError(f'{path}:{lineno} malformed face')
            ids = []
            for item in parts[1:]:
                raw_id = item.split('/')[0]
                idx = int(raw_id)
                if idx == 0:
                    raise ValueError(f'{path}:{lineno} invalid OBJ vertex zero')
                pos = idx-1 if idx > 0 else len(vertices)+idx
                if not 0 <= pos < len(vertices):
                    raise ValueError(f'{path}:{lineno} face index outside vertices')
                ids.append(pos)
            for i in range(1, len(ids)-1):
                faces.append([ids[0], ids[i], ids[i+1]])
    v = np.asarray(vertices, dtype=np.float64)
    f = np.asarray(faces, dtype=np.int32)
    if v.ndim != 2 or v.shape[1:] != (3,) or f.ndim != 2 or f.shape[1:] != (3,):
        raise ValueError('OBJ requires vertices and triangle/polygon faces')
    if not np.isfinite(v).all():
        raise ValueError('OBJ contains nonfinite vertices')
    return v, f


def read_sparse_makehuman_target(path: str | Path, vertex_count: int):
    """Parse original sparse MakeHuman `.target`: vertex_index dx dy dz.

    A line's vertex id is zero-based. Duplicate/invalid indices are rejected
    instead of silently overwriting evidence. Comments are ignored.
    """
    if vertex_count <= 0:
        raise ValueError('vertex_count must be positive')
    data = np.zeros((vertex_count, 3), dtype=np.float64)
    seen = set()
    for lineno, raw in enumerate(Path(path).read_text(encoding='utf-8').splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        fields = line.split()
        if len(fields) != 4:
            raise ValueError(f'{path}:{lineno} expected index and three displacements')
        index = int(fields[0])
        if index < 0 or index >= vertex_count or index in seen:
            raise ValueError(f'{path}:{lineno} duplicate or out-of-range vertex index')
        value = np.asarray([float(c) for c in fields[1:]], dtype=float)
        if not np.isfinite(value).all():
            raise ValueError(f'{path}:{lineno} nonfinite displacement')
        seen.add(index)
        data[index] = value
    if not seen:
        raise ValueError(f'{path} contains no displacements')
    return data


def makehuman_to_world(native_xyz, meters_per_native_unit: float = .1):
    """Native X-right/Y-up/Z-depth -> world X-right/Y-depth/Z-up.

    Negate native Z for a right-handed coordinate transform (determinant +1).
    Horizontal centering and feet-on-ground alignment are separate operations.
    """
    if not np.isfinite(meters_per_native_unit) or meters_per_native_unit <= 0:
        raise ValueError('Explicit native-unit scale must be finite and positive')
    arr = np.asarray(native_xyz, dtype=np.float64)
    if arr.shape[-1] != 3 or not np.isfinite(arr).all():
        raise ValueError('Expected finite XYZ positions/displacements')
    return np.stack((arr[..., 0], -arr[..., 2], arr[..., 1]), axis=-1) * meters_per_native_unit


@dataclass(frozen=True)
class ImportedMakeHuman:
    prior: Prior
    provenance: dict


def import_makehuman_prior(base_obj: str | Path, *,
                           positive_targets: dict[str, str | Path],
                           negative_targets: dict[str, str | Path] | None = None,
                           meters_per_native_unit: float = .1,
                           source_revision: str = 'operator_supplied_unpinned',
                           landmark_vertex_ids: dict[str, int] | None = None):
    """Load a base mesh plus named sparse morph targets as a signed body prior.

    Positive and negative targets should be the actual named MakeHuman
    `-incr.target`/`-decr.target` files; decreasing morphs are not generally the
    negative of the increasing morph. Omitting one direction yields a zero
    displacement in that direction, not an invented mirrored morph.
    """
    positive_targets = dict(positive_targets)
    negative_targets = dict(negative_targets or {})
    names = tuple(sorted(set(positive_targets) | set(negative_targets)))
    if not names:
        raise ValueError('Provide at least one named morph target')
    if any(not n or '/' in n or '\\' in n for n in names):
        raise ValueError('Invalid parameter name')
    base_obj = Path(base_obj)
    native_vertices, faces = read_index_preserving_obj(base_obj)
    verts = makehuman_to_world(native_vertices, meters_per_native_unit)
    # Center the reference mesh and ground its lowest point. Apply this only to
    # vertex positions, never to displacement vectors.
    bounds = np.stack((verts.min(axis=0), verts.max(axis=0)))
    verts -= np.array([np.mean(bounds[:, 0]), np.mean(bounds[:, 1]), bounds[0, 2]])
    height = float(np.ptp(verts[:, 2]))
    if not 0.1 < height < 3.0:
        raise ValueError('Converted human base height implausible; check native-unit scale')
    def load_map(source_map):
        arr = []
        hashes = {}
        for name in names:
            path = source_map.get(name)
            if path is None:
                arr.append(np.zeros_like(verts))
            else:
                path = Path(path)
                arr.append(makehuman_to_world(read_sparse_makehuman_target(path, len(verts)),
                                              meters_per_native_unit))
                hashes[name] = {'path': str(path), 'sha256': _sha256(path)}
        return np.stack(arr), hashes
    pos, pos_hashes = load_map(positive_targets)
    neg, neg_hashes = load_map(negative_targets)
    prior = Prior(verts, faces, pos, names, dict(landmark_vertex_ids or {}),
                  source=f'makehuman_asset_import:{source_revision}',
                  negative_shape_deltas_m=neg)
    meta = {'kind': 'makehuman_cc0_asset_data_import_not_an_observed_body',
            'base_obj': {'path': str(base_obj), 'sha256': _sha256(base_obj),
                         'original_vertex_count': len(verts), 'triangulated_face_count': len(faces)},
            'source_revision': source_revision,
            'license_note': 'Operator must verify each asset license; MakeHuman core assets are CC0, application code is AGPL.',
            'native_to_world': '[x,-z,y] * meters_per_native_unit; centered XY; minimum Z at 0',
            'meters_per_native_unit': meters_per_native_unit,
            'reference_height_m_assuming_declared_scale': height,
            'actual_subject_measurement_validated': False,
            'parameters': list(names), 'positive_target_hashes': pos_hashes,
            'negative_target_hashes': neg_hashes}
    return ImportedMakeHuman(prior, meta)


def save_imported_prior(imported: ImportedMakeHuman, npz_path: str | Path):
    npz_path = Path(npz_path)
    npz_path.parent.mkdir(parents=True, exist_ok=True)
    imported.prior.save(npz_path)
    sidecar = npz_path.with_suffix('.provenance.json')
    sidecar.write_text(json.dumps(imported.provenance, indent=2), encoding='utf-8')
    return npz_path, sidecar
