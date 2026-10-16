import hashlib
from pathlib import Path

import pytest

import metric_human.makehuman_assets as assets


def test_pinned_asset_cache_is_fail_closed(tmp_path,monkeypatch):
    # The test supplies a tiny simulated upstream; no third-party files bundled.
    content=b'v 0 0 0\n'
    name='3dobjs/base.obj'
    monkeypatch.setattr(assets,'PINNED_FILES',{name:hashlib.sha256(content).hexdigest()})
    folder=tmp_path/'assets'; dest=folder/name
    dest.parent.mkdir(parents=True)
    dest.write_bytes(content)
    assert assets.download_verified_core_assets(folder,allow_network=False)[name]==dest
    dest.write_bytes(b'wrong')
    with pytest.raises(ValueError,match='SHA-256'):
        assets.download_verified_core_assets(folder,allow_network=False)
    dest.unlink()
    with pytest.raises(ValueError,match='offline'):
        assets.download_verified_core_assets(folder,allow_network=False)


def test_all_pinned_paths_are_asset_data_only():
    assert len(assets.UPSTREAM_COMMIT)==40
    assert len(assets.PINNED_FILES)==7
    assert all(k.startswith(('3dobjs/','targets/')) and len(v)==64
               for k,v in assets.PINNED_FILES.items())
