#!/usr/bin/env python3
"""Apply a hash-verified official-site overlay without touching business modules.
The caller supplies the local ZIP; this program never sends credentials or deploys.
"""
from __future__ import annotations
import argparse, hashlib, json, os, re, subprocess, tempfile, zipfile
from pathlib import Path, PurePosixPath

BRANCH = 'feat/yueke-official-site-60-gallery-20260909'
BASE = 'b9ef56ff4e29fc76679c590964b7b3273c32d7f2'
LEGACY_SHA = 'f48242828c5a25369bc04eb66bfca43927fb432c'
PATCHABLE = {
    'frontend/src/views/official-site/OfficialSalesPageView.vue',
    'frontend/src/services/officialWechatRuntime.js',
    'frontend/scripts/prerender-official-site.mjs',
    'frontend/tests/official-site-story-contract.test.mjs',
    'frontend/tests/portal-enterprise-entry-contract.test.mjs',
}

def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(['git', '-C', str(repo), *args], text=True).strip()

def allowed(name: str) -> bool:
    p = PurePosixPath(name)
    if p.is_absolute() or '..' in p.parts or '\\' in name: return False
    exact = {'frontend/src/views/PortalHomeView.vue', 'frontend/src/views/official-site/ApprovedShowcaseView.vue', 'frontend/tests/official-showcase.test.mjs'}
    if name in exact: return True
    if name.startswith('frontend/src/components/official-site/showcase/') and p.suffix in {'.js','.css','.html'}: return True
    if name.startswith('frontend/public/official-site/showcase-20260909/') and p.suffix in {'.webp','.json','.mp3'}: return True
    return name in {'frontend/scripts/install-showcase-assets.py','frontend/scripts/check-showcase-assets.mjs','frontend/scripts/showcase-assets.json','frontend/scripts/prerender-showcase.mjs'}

def apply(archive: Path, repo: Path, expected_sha: str | None = None) -> list[str]:
    if git(repo,'branch','--show-current') != BRANCH:
        raise RuntimeError('Refusing to write outside the authorized showcase branch')
    if git(repo,'status','--porcelain'):
        raise RuntimeError('Working tree is not clean; preserve and reconcile existing work first')
    if subprocess.run(['git','-C',str(repo),'merge-base','--is-ancestor',BASE,'HEAD']).returncode:
        raise RuntimeError('The authorized main baseline is not an ancestor of this branch')
    blob = archive.read_bytes()
    if len(blob) > 80_000_000: raise ValueError('Release archive exceeds limit')
    if expected_sha and hashlib.sha256(blob).hexdigest() != expected_sha:
        raise ValueError('Release ZIP SHA256 mismatch')
    planned: dict[str, bytes] = {}
    with zipfile.ZipFile(archive) as z:
        names = z.namelist()
        if len(names) != len(set(names)): raise ValueError('Duplicate ZIP members')
        manifest = json.loads(z.read('manifest.json'))
        if manifest['base'] != BASE or manifest['branch'] != BRANCH: raise ValueError('Wrong release base or branch')
        total = 0
        for name, digest in manifest['files'].items():
            if not allowed(name): raise ValueError('Unexpected source path: '+name)
            info = z.getinfo('overlay/'+name)
            if info.file_size > 5_000_000: raise ValueError('Unexpected member size: '+name)
            total += info.file_size
            if total > 80_000_000: raise ValueError('Uncompressed release exceeds limit')
            data = z.read(info)
            if hashlib.sha256(data).hexdigest() != digest: raise ValueError('Source hash mismatch: '+name)
            planned[name] = data
        patches = json.loads(z.read('patches.json'))
        patched = {}
        for item in patches:
            name = item['path']
            if name not in PATCHABLE: raise ValueError('Unexpected patch target: '+name)
            source = patched.get(name)
            if source is None: source = (repo/name).read_text(encoding='utf-8')
            if 'append' in item:
                if item['append'] not in source: source += item['append']
            elif item['new'] not in source:
                if source.count(item['old']) != 1: raise RuntimeError('Source drift requires review: '+name)
                source = source.replace(item['old'],item['new'],1)
            patched[name] = source
        planned.update({name: source.encode('utf-8') for name, source in patched.items()})
    legacy_name = 'frontend/src/views/PortalLegacyView.vue'
    legacy = repo/legacy_name
    origin_name = legacy_name if legacy.exists() else 'frontend/src/views/PortalHomeView.vue'
    original = subprocess.check_output(['git','-C',str(repo),'show','HEAD:'+origin_name])
    blob_sha = hashlib.sha1(b'blob '+str(len(original)).encode()+b'\0'+original).hexdigest()
    if blob_sha != LEGACY_SHA: raise RuntimeError('The legacy homepage has changed; review before replacing')
    planned[legacy_name] = original
    release_path = 'frontend/public/official-site/showcase-20260909/release.json'
    # Write activation marker last; never present a partial image upload as ready.
    order = sorted(name for name in planned if name != release_path) + ([release_path] if release_path in planned else [])
    for name in order:
        target = repo/name
        target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists() and target.read_bytes() == planned[name]: continue
        with tempfile.NamedTemporaryFile(dir=target.parent,delete=False) as tmp:
            tmp.write(planned[name]); temp_path = tmp.name
        os.replace(temp_path,target)
    return sorted(planned)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive',type=Path)
    parser.add_argument('--repo',type=Path,default=Path.cwd())
    parser.add_argument('--sha256')
    parser.add_argument('--paths-output',type=Path)
    args = parser.parse_args()
    changed = apply(args.archive,args.repo.resolve(),args.sha256)
    if args.paths_output: args.paths_output.write_text('\n'.join(changed)+'\n',encoding='utf-8')
    print(json.dumps({'prepared_paths':len(changed),'branch':BRANCH,'deployed':False},ensure_ascii=False))
