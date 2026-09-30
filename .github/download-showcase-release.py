#!/usr/bin/env python3
"""Verify the archive downloaded from the approved public share UI."""
import hashlib
import json
import os
from pathlib import Path

config = json.loads(Path('.github/official-showcase-release.json').read_text(encoding='utf8'))
archive = Path(os.environ['RUNNER_TEMP']) / 'showcase-release.zip'
if not archive.is_file():
    raise RuntimeError('No downloaded archive; original website remains unchanged')
if archive.stat().st_size != config['bytes']:
    raise ValueError('Archive size differs from the approved release')
sha = hashlib.sha256(archive.read_bytes()).hexdigest()
if sha != config['sha256']:
    raise ValueError('Archive SHA256 differs from the approved release')
print(f'Approved artifact verified: {archive.stat().st_size} bytes; SHA256 {sha}')
with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf8') as f:
    f.write(f'ready=true\nsha256={sha}\n')
