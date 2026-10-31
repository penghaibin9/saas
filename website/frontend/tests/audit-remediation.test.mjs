import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { render } from '../.ssr/entry-server.js'
import { SOLUTION_CONTACTS, solutionContactRoute, consultationContext, PRODUCT_INTERESTS } from '../src/config/companyProducts.js'
import { portalMarkup, PORTAL_LINKS } from '../src/services/portalMarkup.js'
const dist = path => readFile(new URL('../dist/' + path, import.meta.url), 'utf8')
test('all eight solutions carry a supported product and an editable original intention', async () => {
  assert.equal(Object.keys(SOLUTION_CONTACTS).length, 8)
  for (const [slug, solution] of Object.entries(SOLUTION_CONTACTS)) {
    const route = solutionContactRoute('/solutions/' + slug)
    const context = consultationContext(route.query)
    assert.ok(PRODUCT_INTERESTS.includes(context.interest), slug)
    assert.equal(context.message, '关注方案：' + solution.name)
    const html = await render('/contact?' + new URLSearchParams(route.query))
    assert.ok(html.includes(context.interest), 'the supported interest is available')
    assert.ok(!html.includes('关注方案：' + solution.name), 'query context is applied after hydration of the shared static contact page')
    const page = await dist('solutions/' + slug + '/index.html')
    assert.ok(page.includes('solution=' + slug), slug)
  }
  assert.deepEqual(consultationContext({solution:'invalid',product:'invalid'}), {interest:'',message:''})
  assert.equal(consultationContext({product:'internship'}).interest, '岗位实习')
  assert.equal(consultationContext({product:'all'}).interest, '整体解决方案')
})
test('initial portal HTML and runtime use the same links and retain new product entries', async () => {
  const html = await dist('index.html')
  for (const key of ['teacher','student','enterprise','humanResources','teacherH5','studentH5']) {
    const anchor = html.match(new RegExp('<a\\b[^>]*data-entry="'+key+'"[^>]*>[\\s\\S]*?<\\/a>'))?.[0]
    assert.ok(anchor?.includes('href="'+PORTAL_LINKS[key]+'"'),key)
    assert.ok(!anchor.includes('aria-disabled="true"'),key)
  }
  assert.ok(html.includes('/internship/login') && html.includes('/yuqing/'))
  assert.ok(!html.includes('teacher手机网页版') && !html.includes('待部署'))
  assert.throws(()=>portalMarkup('<a data-entry="unknown">入口</a>'))
  assert.match(portalMarkup('<a data-entry="teacher" href="/old">入口</a>',{teacher:''}), /aria-disabled="true"/)
})
test('initial consultation disclosure matches verified public capability without enabling unchecked submission', async () => {
  const html = await dist('contact/index.html')
  assert.ok(html.includes('加密保存 90 天'))
  assert.ok(!html.includes('在线预约暂未启用'))
  assert.match(html, /<button[^>]*disabled[^>]*>提交预约<\/button>/)
})
test('shared screenshot renders natural dimensions; replaced orientation image uses a versioned URL', async () => {
  const html = await dist('solutions/orientation/index.html')
  assert.ok(!html.includes('/orientation-overview.webp'))
  assert.match(html, /student-affairs-orientation-dashboard\.png\?v=[a-f0-9]{12}/)
  const images = [...html.matchAll(/<img\b[^>]*>/g)].map(m=>m[0])
  for (const tag of images.filter(x=>x.includes('/official-site/'))) {
    assert.match(tag,/width="\d+"/);assert.match(tag,/height="\d+"/)
  }
})
test('prerendered styles are unique and hidden carousel images are deferred', async () => {
  const html = await dist('products/index.html')
  const css = [...html.matchAll(/<link\b[^>]*rel="stylesheet"[^>]*href="([^"]+)"/g)].map(m=>m[1])
  assert.equal(new Set(css).size,css.length)
  const slides=[...html.matchAll(/<img\b[^>]*\/boards\/[^>]+>/g)].map(m=>m[0])
  assert.equal(slides.length,4)
  assert.equal(slides.filter(x=>x.includes('loading="eager"')).length,1)
  assert.equal(slides.filter(x=>x.includes('loading="lazy"')).length,3)
})

test('capability failures preserve input, block submission, and allow a successful retry', async () => {
  const source = await readFile(new URL('../src/views/official-site/OfficialSalesPageView.vue', import.meta.url), 'utf8')
  const script = source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import[^\n]*\n/gm, '').replace('export default', 'return')
  let available = false
  const fetchCapability = async () => available ? {ok:true,json:async()=>({code:0,data:{mode:'registered'}})} : {ok:false,json:async()=>({message:'service failure'})}
  const component = new Function('publicConfig','API_BASE_URL','API_PREFIX','fetch','consultationContext','solutionContactRoute','const OfficialImageZoom={}, ProductReadingGuide={};'+script)
    ({consultation:{mode:'registered'}},'', '/api',fetchCapability,consultationContext,solutionContactRoute)
  const view = {...component.data(),...component.methods}
  view.applyContactContext({product:'orientation',solution:'orientation'})
  view.applyContactContext({product:'all',solution:'teacher-workbench'})
  assert.equal(view.leadForm.message,'关注方案：教师工作台')
  view.leadForm.schoolName='隔离测试输入'
  view.leadForm.message='保留用户填写的需求'
  await view.loadLeadMode()
  assert.equal(view.leadCapabilityState,'error')
  assert.equal(view.leadForm.schoolName,'隔离测试输入')
  available=true
  await view.loadLeadMode()
  assert.equal(view.leadCapabilityState,'ready')
  view.applyContactContext({product:'orientation',solution:'orientation'})
  assert.equal(view.leadForm.interest,'数字迎新')
  assert.equal(view.leadForm.message,'保留用户填写的需求')
  assert.deepEqual(consultationContext({product:'constructor',solution:'__proto__'}),{interest:'',message:''})
})
