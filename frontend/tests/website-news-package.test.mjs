import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
import { mountNewsPreview } from '../src/components/official-site/showcase/news-preview.js'
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..')
const read=p=>fs.readFileSync(path.join(root,p),'utf8')
test('news page is a genuine platform route using a root-plane capability',()=>{
 const routes=read('src/modules/platform/platform.routes.js'),catalog=read('src/modules/platform/platformManagementCatalog.js')
 assert.match(routes,/PlatformWebsiteNewsView/);assert.match(routes,/platform\.websiteNews\.manage/);assert.match(catalog,/官网内容运营/);assert.match(catalog,/新闻资源包发布/)
})
test('upload and confirmation replace individual composition and daily quotas',()=>{
 const s=read('src/modules/platform/views/control/PlatformWebsiteNewsView.vue')
 for(const m of ['上传新闻资源包','确认并自动发布','reviewDigest','expectedVersion','excludedIds','confirmed:true','暂停未发布队列','导出台账 XLSX'])assert.ok(s.includes(m),m)
 assert.doesNotMatch(s,/dailyLimit\s*[:=]\s*30/);assert.doesNotMatch(s,/localStorage|mock|v-html/)
})
test('public latest news does not consume raw html or allocate when absent',()=>{
 let count=0;const dispose=mountNewsPreview({querySelector:()=>null},{fetcher:()=>count++});dispose();assert.equal(count,0)
 const s=read('src/components/official-site/showcase/news-preview.js');assert.match(s,/textContent/);assert.doesNotMatch(s,/innerHTML/)
})
test('latest news late response is canceled on unmount',async()=>{
 let resolve;let signal;let touched=false
 const dispose=mountNewsPreview({querySelector:()=>({replaceChildren:()=>touched=true})},{fetcher:(_url,opt)=>{signal=opt.signal;return new Promise(r=>resolve=r)}})
 dispose();resolve({ok:true,json:async()=>({code:0,data:{items:[{}]}})});await new Promise(r=>setImmediate(r));assert.equal(signal.aborted,true);assert.equal(touched,false)
})
test('upload timeout is opt-in; previous callers retain fifteen seconds',()=>{
 const s=read('src/services/http/client.js');assert.match(s,/requestUpload\(path, file, fieldName = 'file', \{ timeoutMs = 15000 \}/);assert.match(s,/Math\.min\(120000/)
})
