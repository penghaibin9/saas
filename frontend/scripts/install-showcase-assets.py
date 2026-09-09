#!/usr/bin/env python3
"""Install ONLY the 143 approved images from the user's resource ZIP; no source execution.
Run from repo root: python frontend/scripts/install-showcase-assets.py '/path/to/resource.zip'
The release marker is written last. No credentials, network, commit, push or deployment.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import zipfile

def install(archive: Path, frontend: Path) -> dict:
    manifest = json.loads((frontend / 'scripts/showcase-assets.json').read_text(encoding='utf-8'))
    if len(manifest['assets']) != 143:
        raise ValueError('Expected 143 approved asset hashes')
    destination = frontend / 'public/official-site/showcase-20260909'
    with zipfile.ZipFile(archive) as bundle:
        checked = {}
        for name, expected in manifest['assets'].items():
            if not re.fullmatch(r'(screens|boards|scenes)/[a-z0-9-]+\.webp', name):
                raise ValueError('Invalid asset path: ' + name)
            member = 'website-handoff/assets/' + name
            info = bundle.getinfo(member)
            if info.file_size > 4_000_000:
                raise ValueError('Unexpected asset size: ' + name)
            payload = bundle.read(member)
            if hashlib.sha256(payload).hexdigest() != expected:
                raise ValueError('Approved image hash mismatch: ' + name)
            if payload[:4] != b'RIFF' or payload[8:12] != b'WEBP':
                raise ValueError('Invalid WebP asset: ' + name)
            checked[name] = payload
        # Validate every image first: a bad ZIP never creates a ready marker.
        destination.mkdir(parents=True, exist_ok=True)
        for name, payload in checked.items():
            target = destination / name
            target.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as temp:
                temp.write(payload)
                temp_path = Path(temp.name)
            os.replace(temp_path, target)
        marker = {'version': manifest['version'], 'assetCount': 143, 'businessCount': 67, 'expandedCount': 60}
        marker_tmp = destination / 'release.json.tmp'
        marker_tmp.write_text(json.dumps(marker, indent=2) + '\n', encoding='utf-8')
        os.replace(marker_tmp, destination / 'release.json')
    return {'installed': len(checked), 'bytes': sum(map(len, checked.values())), 'destination': str(destination)}

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('--frontend', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    print(json.dumps(install(args.archive, args.frontend), ensure_ascii=False, indent=2))
