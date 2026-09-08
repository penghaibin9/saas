"""One-time reviewed repair transfer. Never touches main or a production resource."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import tempfile

BASE='b9ef56ff4e29fc76679c590964b7b3273c32d7f2'
BRANCH='fix/internship-download-repair-20260909'
HASHES={
 '01-core.patch':'32c550b704f5a30bc01e28bc7d07f29182001a6a52395cf1fec8137a400fca15',
 '02-tests.patch':'5ca0271886b2f8e862e2f63787b9a948436f7a4d42a5343e0ca17f3a8efa96e5',
 '03-ci.patch':'6289f13b2e52aa35789e1b79d7fac45474d4ca2adfee6dbddd55cc62878dc956',
 '04-browser.patch':'1cf6b4275518833bb390c8820eb417f6aad2612b3b405ede16ae04a739781a49',
 '05-capacity.patch':'fdf3cc5266a9419ac65af5e4551ba303f99bdc76ec01537f54e39a2ae66d519f',
 '06-capacity-tests.patch':'0cfbc159a01d6af81c907dfb1ebeffe628a00324cc113b79726095e734562fc3',
}
def git(*args):
 return subprocess.check_output(['git',*args],text=True).strip()
assert os.environ.get('GITHUB_REF')=='refs/heads/'+BRANCH,'wrong branch'
assert not git('status','--porcelain'),'dirty workspace'
head=git('rev-parse','HEAD')
assert git('ls-remote','origin','refs/heads/'+BRANCH).split()[0]==head,'remote advanced'
chunks=[]
for name,expected in HASHES.items():
 data=(Path('scripts/repair-payload')/name).read_bytes()
 if name=='06-capacity-tests.patch':
  data=data.replace(b"'uniqueTeacherSubjects':300,'uniqueTeacherSubjects':300,",b"'uniqueTeacherSubjects':300,")
 actual=hashlib.sha256(data).hexdigest()
 assert actual==expected,(name,actual,expected)
 chunks.append(data)
patch=b''.join(chunks)
paths=sorted({line[6:] for line in patch.decode().splitlines() if line.startswith('+++ b/')})
assert len(paths)==26
for path in paths:
 assert not git('diff','--name-only',BASE,'HEAD','--',path),('source changed',path)
with tempfile.NamedTemporaryFile(suffix='.patch') as f:
 f.write(patch);f.flush()
 subprocess.run(['git','apply','--check','--unidiff-zero','--whitespace=error',f.name],check=True)
 subprocess.run(['git','apply','--unidiff-zero','--whitespace=error',f.name],check=True)
subprocess.run(['git','add','--',*paths],check=True)
subprocess.run(['git','rm','--','scripts/repair-payload/internship-20260909.00.b64'],check=True)
git('config','user.name','github-actions[bot]')
git('config','user.email','41898282+github-actions[bot]@users.noreply.github.com')
git('commit','-m','fix(internship): apply five reviewed repair groups with runtime regressions')
sha=git('rev-parse','HEAD')
assert git('ls-remote','origin','refs/heads/'+BRANCH).split()[0]==head,'remote advanced before push'
subprocess.run(['git','push','origin','HEAD:refs/heads/'+BRANCH],check=True)
out=Path('/tmp/repair-proof');out.mkdir(exist_ok=True)
(out/'manifest.json').write_text(json.dumps({'base':BASE,'sha':sha,'files':[{'path':p,'after':hashlib.sha256(Path(p).read_bytes()).hexdigest()} for p in paths]},indent=2))
(out/'repair.patch').write_text(git('diff','--binary',BASE,'HEAD','--',*paths)+'\n')
subprocess.run(['git','archive','--format=tar.gz','--output='+str(out/'source-after.tar.gz'),'HEAD',*paths],check=True)
with open(os.environ['GITHUB_OUTPUT'],'a') as f:f.write('sha='+sha+'\n')
print('applied and pushed exact repair SHA',sha)
