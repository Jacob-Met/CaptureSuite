"""Explicit, pinned download of MakeHuman CC0 *asset data* (not application code).

No automatic network access occurs when installing or importing Metric Human.
The operator requests this command to obtain the officially published core
mesh and a tiny subset of matching measurement morphs. File hashes are pinned
and revalidated before use, including cached downloads.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from urllib.request import Request, urlopen

from .makehuman import import_makehuman_prior, save_imported_prior
from .evidence import sha256_file

UPSTREAM_REPOSITORY = 'https://github.com/makehumancommunity/makehuman'
UPSTREAM_COMMIT = '1f508f6083b2f823dab15de924b3bde72e08d77c'
ASSET_URL_ROOT = f'https://raw.githubusercontent.com/makehumancommunity/makehuman/{UPSTREAM_COMMIT}/makehuman/data/'
# SHA-256 independently checked against the exact pinned upstream paths.
PINNED_FILES = {
    '3dobjs/base.obj': '8e761e6624b8f54536409135d1636da63b32486a90d4897f84e121d144f6fb4c',
    'targets/measure/measure-shoulder-dist-incr.target': 'af7394300c91d64fb0b032377aae72e546c778d1d5c00daed88858c04ee9150b',
    'targets/measure/measure-shoulder-dist-decr.target': '15034d390da69ce7a3e46dfee0e248d0649bf6fc0bfec575b4cacf48b7a1ba5a',
    'targets/measure/measure-bust-circ-incr.target': '46394c7f9cdfac31654f14950b57bbfb874c9a2fa68e48c9cc3e7bba619b75f4',
    'targets/measure/measure-bust-circ-decr.target': '3d4c9f8c7d084e4d6c35ffc3a798bc35bdbe80fd56929d03e0c6f1b31ec5c736',
    'targets/measure/measure-thigh-circ-incr.target': '5dca89b139df6f9b7c7641485dee18e9f0da10087359b9df5ca6a1e752ea0bcc',
    'targets/measure/measure-thigh-circ-decr.target': 'fe5303874b0ffe26a69cefd3e213b6478eec4648f60b0b110a1e176ccf24eaa9',
}


def download_verified_core_assets(out_dir, *, timeout=30, allow_network=True):
    """Fetch/cache exact pinned source files under a new isolated directory.

    Verification happens before any file is used. Existing files with the
    wrong digest are rejected; a corrupt payload cannot replace a valid file.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {}
    for rel, expected in PINNED_FILES.items():
        dest = out_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.is_file():
            digest = sha256_file(dest)
            if digest != expected:
                raise ValueError(f'Existing pinned asset has incorrect SHA-256: {rel}')
        else:
            if not allow_network:
                raise ValueError(f'Asset missing from offline cache: {rel}')
            req = Request(ASSET_URL_ROOT + rel, headers={'User-Agent':'metric-human-lab/0.2'})
            with urlopen(req, timeout=timeout) as response:
                payload = response.read()
            if hashlib.sha256(payload).hexdigest() != expected:
                raise ValueError(f'Downloaded pinned asset SHA-256 mismatch: {rel}')
            # Only write bytes after verification. Never mix mismatched versions.
            dest.write_bytes(payload)
        paths[rel] = dest
    return paths


def create_pinned_makehuman_prior(out_dir, *, allow_network=True, meters_per_native_unit=.1):
    """Produce a 3-parameter paired MakeHuman prior with original-source hashes."""
    out_dir = Path(out_dir)
    paths=download_verified_core_assets(out_dir/'upstream_assets',allow_network=allow_network)
    pos,neg = {},{}
    for name in ('shoulder-dist','bust-circ','thigh-circ'):
        for suffix,collection in [('incr',pos),('decr',neg)]:
            key=f'targets/measure/measure-{name}-{suffix}.target'
            collection[name]=paths[key]
    imported=import_makehuman_prior(paths['3dobjs/base.obj'],
                                     positive_targets=pos,negative_targets=neg,
                                     source_revision=UPSTREAM_COMMIT,
                                     meters_per_native_unit=meters_per_native_unit)
    prior_path,provenance_path=save_imported_prior(imported,out_dir/'makehuman_cc0_body_prior.npz')
    meta=json.loads(provenance_path.read_text())
    meta['upstream_repository']=UPSTREAM_REPOSITORY
    meta['upstream_commit']=UPSTREAM_COMMIT
    meta['upstream_assets_cc0_license_url']=UPSTREAM_REPOSITORY+'/blob/'+UPSTREAM_COMMIT+'/LICENSE.ASSETS.md'
    meta['asset_sha256_verified']=True
    meta['source_code_license_of_makehuman_application']='AGPL; no MakeHuman application code imported'
    provenance_path.write_text(json.dumps(meta,indent=2),encoding='utf8')
    return prior_path,provenance_path
