"""Read-only-to-GitHub verification: apply reviewed patches to a disposable CI worktree.
No commit, push, credential changes, deployment or production access.
"""
from pathlib import Path
import hashlib
import json
import subprocess
import tarfile
import tempfile

BASE='b9ef56ff4e29fc76679c590964b7b3273c32d7f2'
HASHES={
 '01-core.patch':'32c550b704f5a30bc01e28bc7d07f29182001a6a52395cf1fec8137a400fca15',
 '02-tests.patch':'5ca0271886b2f8e862e2f63787b9a948436f7a4d42a5343e0ca17f3a8efa96e5',
 '03-ci.patch':'6289f13b2e52aa35789e1b79d7fac45474d4ca2adfee6dbddd55cc62878dc956',
 '04-browser.patch':'1cf6b4275518833bb390c8820eb417f6aad2612b3b405ede16ae04a739781a49',
 '05-capacity.patch':'fdf3cc5266a9419ac65af5e4551ba303f99bdc76ec01537f54e39a2ae66d519f',
 '06-capacity-tests.patch':'0cfbc159a01d6af81c907dfb1ebeffe628a00324cc113b79726095e734562fc3',
}
chunks=[]
for name,expected in HASHES.items():
 data=(Path('scripts/repair-payload')/name).read_bytes()
 if name=='06-capacity-tests.patch':
  data=data.replace(b"'uniqueTeacherSubjects':300,'uniqueTeacherSubjects':300,",b"'uniqueTeacherSubjects':300,")
 actual=hashlib.sha256(data).hexdigest()
 if actual!=expected:raise SystemExit(f'checksum mismatch: {name}: {actual}, expected {expected}')
 chunks.append(data)
patch=b''.join(chunks)
paths=sorted({line[6:] for line in patch.decode().splitlines() if line.startswith('+++ b/')})
if len(paths)!=26:raise SystemExit('unexpected file count')
for path in paths:
 if Path(path).is_absolute() or '..' in Path(path).parts:raise SystemExit('unsafe path')
 subprocess.run(['git','diff','--exit-code',BASE,'HEAD','--',path],check=True)
with tempfile.NamedTemporaryFile(suffix='.patch') as f:
 f.write(patch);f.flush()
 subprocess.run(['git','apply','--check','--unidiff-zero','--whitespace=error',f.name],check=True)
 subprocess.run(['git','apply','--unidiff-zero','--whitespace=error',f.name],check=True)
out=Path('/tmp/repair-proof');out.mkdir(exist_ok=True)
head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
manifest={'base':BASE,'transportCommit':head,'testedSource':'base-plus-verified-patch',
 'patchSha256':hashlib.sha256(patch).hexdigest(),
 'files':[{'path':p,'after':hashlib.sha256(Path(p).read_bytes()).hexdigest()} for p in paths]}
(out/'manifest.json').write_text(json.dumps(manifest,indent=2))
(out/'repair-zero-context.patch').write_bytes(patch)
with tarfile.open(out/'source-after.tar.gz','w:gz') as archive:
 for path in paths:archive.add(path,arcname=path,recursive=False)
print(json.dumps(manifest,indent=2))
