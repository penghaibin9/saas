"""Exercise the real Vue view and news API on disposable MySQL.
The harness substitutes only authentication transport; production components,
API handlers, root role dependency, DB service and worker remain the real files.
No school business records or production endpoints are touched.
"""
from pathlib import Path
import os,sys,time,json,subprocess,urllib.request,signal
from datetime import datetime,timedelta
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[2];FRONT=ROOT/'frontend';BACK=ROOT/'backend';OUT=ROOT/'news-check-output';OUT.mkdir(exist_ok=True)
sys.path.insert(0,str(BACK));sys.path.insert(0,str(BACK/'tests/website_news'))
from helpers import make_bundle
from sqlalchemy import create_engine,text,select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from app.models.website_news import NewsArticle,NewsPackage
url=os.environ['NEWS_TEST_DATABASE_URL']
if not make_url(url).database.startswith('test_'):raise RuntimeError('Disposable DB required')
engine=create_engine(url,pool_pre_ping=True);Session=sessionmaker(engine)
with engine.begin() as c:
 for name in ['media_link','article','media','audit','package']:c.execute(text('DELETE FROM t_website_news_'+name))
 c.execute(text('UPDATE t_website_news_dispatch SET next_slot=NULL,heartbeat_at=NULL WHERE id=1'))
bundle=OUT/'browser-fixture.zip';bundle.write_bytes(make_bundle(41,prefix='浏览器验收'))
H=FRONT/'.news-proof';H.mkdir(exist_ok=True)
(H/'index.html').write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>body{margin:0;background:#f5f7fb;font-family:system-ui,"Microsoft YaHei",sans-serif}</style><div id="app"></div><script type="module" src="/.news-proof/main.js"></script></html>'.replace('/\\.news','/.news'))
(H/'main.js').write_text("import {createApp} from 'vue';import View from '../src/modules/platform/views/control/PlatformWebsiteNewsView.vue';createApp(View).mount('#app')")
(H/'http.js').write_text("""async function send(path,options={}){const u=new URL('/api/v1'+path,location.origin);Object.entries(options.params||{}).forEach(([k,v])=>u.searchParams.set(k,v));const r=await fetch(u,{method:options.method||'GET',headers:options.body?{'Content-Type':'application/json'}:undefined,body:options.body?JSON.stringify(options.body):undefined});const data=await r.json();if(!r.ok||data.code!==0)throw new Error(data.message);return data.data}
export const request=send;
export async function requestUpload(path,file){const data=new FormData();data.append('file',file);const r=await fetch('/api/v1'+path,{method:'POST',body:data});const out=await r.json();if(!r.ok||out.code!==0)throw new Error(out.message);return out.data}
export async function requestBlob(path){const r=await fetch('/api/v1'+path);if(!r.ok)throw new Error('Export failed');return r.blob()}
""")
(H/'vite.config.mjs').write_text("import {defineConfig} from 'vite';import vue from '@vitejs/plugin-vue';import path from 'node:path';export default defineConfig({plugins:[vue()],resolve:{alias:[{find:'@/services/http/client',replacement:path.resolve('.news-proof/http.js')},{find:'@',replacement:path.resolve('src')}]},server:{host:'127.0.0.1',port:5179,proxy:{'/api':{target:'http://127.0.0.1:8108'},'/news':{target:'http://127.0.0.1:8108'}}}})")
processes=[];files=[];checks=[]
def spawn(cmd,cwd,env,name):
 log=(OUT/name).open('w');files.append(log);proc=subprocess.Popen(cmd,cwd=cwd,env=env,stdout=log,stderr=subprocess.STDOUT);processes.append(proc);return proc

def wait(url):
 for _ in range(90):
  try:
   with urllib.request.urlopen(url,timeout=1) as r:
    if r.status==200:return
  except Exception:time.sleep(.5)
 raise RuntimeError('Server not ready: '+url)
try:
 env={**os.environ,'NEWS_E2E_TEST_ONLY':'true','PYTHONPATH':str(BACK),'DB_ENABLED':'true','DATABASE_URL':url,'DB_DRIVER':'mysql','PYTHONDONTWRITEBYTECODE':'1'}
 spawn([sys.executable,'-m','uvicorn','e2e_server:app','--app-dir','tests/website_news','--host','127.0.0.1','--port','8108'],BACK,env,'api.log')
 spawn(['node','node_modules/vite/bin/vite.js','--config','.news-proof/vite.config.mjs'],FRONT,env,'vite.log')
 wait('http://127.0.0.1:8108/news');wait('http://127.0.0.1:5179/.news-proof/index.html')
 with sync_playwright() as p:
  browser=p.chromium.launch(headless=True);context=browser.new_context(viewport={'width':1440,'height':1000});page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  page.goto('http://127.0.0.1:5179/.news-proof/index.html');expect(page.get_by_role('heading',name='一包上传，审核后自动发布。')).to_be_visible()
  page.locator('input[type=file]').set_input_files(str(bundle));expect(page.get_by_role('button',name='确认并自动发布 41 篇',exact=True)).to_be_enabled(timeout=15000)
  page.screenshot(path=str(OUT/'01-package-review-desktop.png'),full_page=False);checks.append('41-article upload displayed with no daily cap')
  page.get_by_role('button',name='审核正文',exact=True).first.click();expect(page.locator('.wn-markdown')).to_be_visible();checks.append('real body and source review')
  page.get_by_role('button',name='确认并自动发布 41 篇',exact=True).click();expect(page.locator('dialog[open]')).to_be_visible();page.get_by_role('button',name='我已审核，确定自动发布').click();expect(page.get_by_role('button',name='暂停未发布队列')).to_be_visible(timeout=10000)
  page.get_by_role('button',name='暂停未发布队列').click();expect(page.get_by_role('button',name='恢复自动发布')).to_be_visible(timeout=10000);checks.append('whole package approved then paused')
  # Actual worker process runs without the browser and must respect the paused batch.
  with engine.begin() as c:c.execute(text('UPDATE t_website_news_article SET scheduled_at=:t'),{'t':datetime.utcnow()-timedelta(minutes=1)})
  worker=spawn([sys.executable,'-m','app.website_news_worker'],BACK,{**env,'WEBSITE_NEWS_WORKER_ENABLED':'true'},'worker.log');time.sleep(2)
  with engine.connect() as c:assert c.scalar(text("SELECT COUNT(*) FROM t_website_news_article WHERE state='PUBLISHED'"))==0
  page.get_by_role('button',name='恢复自动发布').click();expect(page.get_by_role('button',name='暂停未发布队列')).to_be_visible(timeout=10000)
  with engine.begin() as c:c.execute(text('UPDATE t_website_news_article SET scheduled_at=:t'),{'t':datetime.utcnow()-timedelta(minutes=1)})
  page.close();checks.append('browser closed while actual server worker runs')
  for _ in range(30):
   with engine.connect() as c:n=c.scalar(text("SELECT COUNT(*) FROM t_website_news_article WHERE state='PUBLISHED'"))
   if n==41:break
   time.sleep(1)
  assert n==41,f'worker did not finish: {n}'
  checks.append('all 41 articles published after browser closes')
  with engine.connect() as c:assert c.scalar(text("SELECT COUNT(*) FROM t_website_news_audit WHERE action='PUBLISH'"))==41
  page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)));page.goto('http://127.0.0.1:5179/.news-proof/index.html');page.locator('.wn-package').first.click();expect(page.locator('.wn-confirm strong')).to_have_text('发布完成',timeout=10000);page.screenshot(path=str(OUT/'02-package-complete-desktop.png'));checks.append('completed queue read back from database')
  with page.expect_download() as download:page.get_by_role('button',name='导出台账 XLSX').click()
  download.value.save_as(str(OUT/'news-ledger.xlsx'));checks.append('actual XLSX export download')
  for w in [390,768,1440]:
   page.set_viewport_size({'width':w,'height':900});page.reload();expect(page.get_by_role('heading',name='一包上传，审核后自动发布。')).to_be_visible();assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 2');checks.append(f'admin layout width {w}')
  # Reader sees real server-rendered HTML without JavaScript.
  reader=browser.new_context(java_script_enabled=False,viewport={'width':1440,'height':1000});rp=reader.new_page();rp.goto('http://127.0.0.1:8108/news');expect(rp.get_by_role('heading',name='新闻与资讯',exact=True)).to_be_visible();rp.screenshot(path=str(OUT/'03-public-news-desktop.png'));rp.locator('.card h2 a').first.click();expect(rp.get_by_role('heading',name='信息来源与延伸阅读')).to_be_visible();rp.screenshot(path=str(OUT/'04-public-article-desktop.png'));checks.append('SSR news index and detail usable with JavaScript disabled')
  rp.set_viewport_size({'width':390,'height':844});rp.screenshot(path=str(OUT/'05-public-article-h5.png'));assert rp.evaluate('document.documentElement.scrollWidth <= innerWidth + 2');checks.append('H5 article no horizontal page overflow')
  assert not errors,errors
  browser.close();checks.append('no unhandled Vue page errors')
 (OUT/'browser-results.json').write_text(json.dumps({'passed':len(checks),'checks':checks,'scope':'Real Vue view + actual news API/MySQL/worker; fixture authentication transport, not production full-shell or WeChat physical device'},ensure_ascii=False,indent=2))
 print(json.dumps({'browser_checks':len(checks),'status':'passed'}))
finally:
 for proc in reversed(processes):
  proc.terminate()
  try:proc.wait(timeout=5)
  except subprocess.TimeoutExpired:proc.kill()
 for f in files:f.close()
 engine.dispose()
