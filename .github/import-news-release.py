"""Hash-locked, preimage-checked website newsroom import on original PR269 only."""
import hashlib, json, os, subprocess, sys, zipfile
from pathlib import Path, PurePosixPath
CONFIG=Path('.github/official-news-release.json')
config=json.loads(CONFIG.read_text())
branch='feat/yueke-official-site-60-gallery-20260909'
archive=Path(os.environ['RUNNER_TEMP'])/'news-release.zip'
if config['branch']!=branch: raise RuntimeError('Wrong authorized branch')
if sys.argv[1]=='download':
    # Reuse the already reviewed public-share browser; no guessed download API.
    source=Path('.github/resolve-firestorage-release.py').read_text()
    replacements={
      ".github/official-showcase-release.json":'.github/official-news-release.json',
      '跃科官网-已施工源码与配乐完整包-20260909.zip':config['filename'],
      '15142223':str(config['bytes']),
      '7d28688802e96621f969320c908947f6b869c20cb5fef7d4beba07c76c1d4f51':config['sha256'],
      'showcase-release.zip':'news-release.zip'
    }
    for old,new in replacements.items():
        if source.count(old)!=1: raise RuntimeError('Download adapter source drift: '+old)
        source=source.replace(old,new)
    temp=Path(os.environ['RUNNER_TEMP'])/'resolve-news.py';temp.write_text(source)
    subprocess.run([sys.executable,str(temp)],check=True)
    raise SystemExit(0)
if sys.argv[1]!='apply':raise RuntimeError('Unknown command')
if subprocess.check_output(['git','branch','--show-current'],text=True).strip()!=branch:raise RuntimeError('Wrong branch')
if subprocess.check_output(['git','status','--porcelain'],text=True).strip():raise RuntimeError('Dirty tree; preserve other work')
data=archive.read_bytes()
if len(data)!=config['bytes'] or hashlib.sha256(data).hexdigest()!=config['sha256']:raise RuntimeError('ZIP identity mismatch')
exact={
 'backend/app/db/base.py','backend/app/main.py','backend/app/api/v1/website_news.py','backend/app/models/website_news.py','backend/app/website_news_worker.py',
 'backend/alembic/versions/20260909_website_news_packages.py',
 'deploy/nginx/nginx.mysql.conf','deploy/nginx/website-news.locations.conf.example','deploy/docker/docker-compose.website-news.yml','deploy/systemd/school-lifecycle-website-news.service',
 'frontend/scripts/prerender-official-site.mjs','frontend/scripts/website-news-browser.py',
 'frontend/src/modules/platform/platform.routes.js','frontend/src/modules/platform/platformManagementCatalog.js','frontend/src/services/http/client.js',
 'frontend/src/modules/platform/api/websiteNews.api.js','frontend/src/modules/platform/views/control/PlatformWebsiteNewsView.vue',
 'frontend/tests/official-showcase.test.mjs','frontend/tests/website-news-package.test.mjs'
}
prefixes=('backend/app/services/website_news/','backend/tests/website_news/','frontend/src/components/official-site/showcase/','frontend/public/official-site/news-media/','docs/website-news/')
planned={};root=Path.cwd().resolve()
with zipfile.ZipFile(archive) as z:
    if len(z.namelist())!=len(set(z.namelist())):raise RuntimeError('Duplicate ZIP paths')
    m=json.loads(z.read('manifest.json'))
    if m['schema']!='yueke.news-implementation/1' or m['branch']!=branch:raise RuntimeError('Invalid manifest')
    if len(m['files'])>60:raise RuntimeError('Unexpected scope size')
    total=0
    for name,entry in m['files'].items():
        p=PurePosixPath(name)
        if p.is_absolute() or '..' in p.parts or '\\' in name or not (name in exact or name.startswith(prefixes)):raise RuntimeError('Unexpected path: '+name)
        target=root/name
        if not target.resolve().is_relative_to(root):raise RuntimeError('Target escapes repository')
        info=z.getinfo('overlay/'+name);total+=info.file_size
        if info.file_size>2_000_000 or total>8_000_000:raise RuntimeError('Uncompressed size exceeded')
        raw=z.read(info)
        if len(raw)!=entry['bytes'] or hashlib.sha256(raw).hexdigest()!=entry['sha256']:raise RuntimeError('File identity mismatch: '+name)
        current=hashlib.sha256(target.read_bytes()).hexdigest() if target.exists() else None
        if current not in (entry['before'],entry['sha256']):raise RuntimeError('Concurrent source change: '+name)
        planned[name]=raw
for name,data in planned.items():
    p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
(Path(os.environ['RUNNER_TEMP'])/'news-paths.txt').write_text('\n'.join(sorted(planned))+'\n')
print('Verified original news implementation imported:',len(planned),'files; no production deployment')
