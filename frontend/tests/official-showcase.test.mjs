import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { SHOWCASE, CAMPUS_MODULES } from '../src/components/official-site/showcase/content.js'
import { consultationPath, INTERESTS } from '../src/components/official-site/showcase/runtime.js'
import { hasShowcaseAssets, validRelease } from '../src/components/official-site/showcase/asset-gate.js'
import { SCORE, TourSoundtrack } from '../src/components/official-site/showcase/tour-audio.js'
const frontend = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const manifest = JSON.parse(fs.readFileSync(path.join(frontend, 'scripts/showcase-assets.json'), 'utf8'))
const base = path.join(frontend, 'src/components/official-site/showcase')

test('four PC galleries and two WeChat galleries each contain ten different pages', () => {
  const expanded = ['academic','affairs','internship','graduation','teacher','student']
  const ids = expanded.flatMap(key => {
    const group = SHOWCASE.galleries[key]
    assert.equal(group.slides.length, 10, key)
    assert.equal(new Set(group.slides.map(slide => slide[0])).size, 10, key)
    assert.equal(Boolean(group.mobile), ['teacher','student'].includes(key))
    return group.slides.map(slide => slide[0])
  })
  assert.equal(new Set(ids).size, 60)
})
test('HR five and student PC two remain additional to the sixty pages', () => {
  assert.equal(SHOWCASE.galleries.hr.slides.length, 5)
  assert.equal(SHOWCASE.galleries.studentpc.slides.length, 2)
  assert.equal(Object.values(SHOWCASE.galleries).reduce((total, group) => total + group.slides.length, 0), 67)
})
test('every full-size gallery image and thumbnail belongs to the approved manifest', () => {
  assert.equal(manifest.count, 143)
  assert.equal(Object.keys(manifest.assets).length, 143)
  for (const group of Object.values(SHOWCASE.galleries)) for (const [id,title,copy] of group.slides) {
    assert.match(id,/^[a-z0-9-]+$/)
    assert.ok(title.length > 1 && copy.length > 8)
    assert.match(manifest.assets[`screens/${id}.webp`], /^[a-f0-9]{64}$/)
    assert.match(manifest.assets[`screens/${id}-thumb.webp`], /^[a-f0-9]{64}$/)
  }
})
test('covers are mapped by identity rather than stale slide indexes', () => {
  for (const p of Object.values(SHOWCASE.products)) assert.ok(SHOWCASE.galleries[p.gallery].slides.some(slide => p.image.endsWith('/'+slide[0]+'.webp')))
})
test('school HR intent and source propagate as safe contact query parameters', () => {
  const url = new URL(consultationPath('高校人事系统'), 'https://example.test')
  assert.equal(url.pathname, '/contact')
  assert.equal(url.searchParams.get('product'), 'renshi')
  assert.equal(url.searchParams.get('interest'), '高校人事系统')
  assert.equal(url.searchParams.get('source'), 'official-showcase')
  const invalid = new URL(consultationPath('https://attacker.invalid'), 'https://example.test')
  assert.equal(invalid.origin, 'https://example.test')
  assert.equal(invalid.searchParams.get('product'), 'all')
  assert.equal(INTERESTS['wechat-academic'], '教务与微信小程序')
})
test('no complete prototypes, user input or executable scripts are shipped in the public markup', () => {
  const html = fs.readFileSync(path.join(base,'approved-home.html'),'utf8')
  assert.ok(html.includes('精选界面'))
  assert.ok(!/<script\b|<iframe\b|onerror=|onclick=/i.test(html))
  assert.ok(!/MODEL=|AA_DESIGN|sourceUrl|sha256|baseline|字段代入|生产三级入口全部设计/.test(html))
  for (const name of ['tour-sound','tour-volume','tour-canvas','gallery-consult-short']) assert.ok(html.includes(`id="${name}"`))
})
test('asset readiness is strict, not an HTTP 200 or an HTML SPA fallback', async () => {
  const release = { version: '20260909-pc40-wechat20', assetCount:143,businessCount:67,expandedCount:60 }
  assert.equal(validRelease(release), true)
  assert.equal(validRelease({...release,assetCount:'143'}), false)
  assert.equal(validRelease({...release,expandedCount:22}), false)
  assert.equal(await hasShowcaseAssets({fetcher:async()=>new Response(JSON.stringify(release))}), true)
  assert.equal(await hasShowcaseAssets({fetcher:async()=>new Response('<html>fallback</html>')}), false)
  assert.equal(await hasShowcaseAssets({fetcher:async()=>new Response('',{status:404})}), false)
})
test('unmount cancellation does not activate a late homepage fetch', async () => {
  const c = new AbortController(); c.abort()
  let called = false
  assert.equal(await hasShowcaseAssets({signal:c.signal,fetcher:async()=>{called=true;throw Error()}}), false)
  assert.equal(called,false)
})
test('network timeout fails closed to legacy homepage', async () => {
  const result = await hasShowcaseAssets({timeoutMs:10,fetcher:(_,options)=>new Promise((resolve,reject)=>options.signal.addEventListener('abort',()=>reject(Error('aborted'))))})
  assert.equal(result,false)
})
test('licensed replacement cue retains the 32-second tour duration and attribution', () => {
  assert.equal(SCORE.duration,32)
  assert.equal(SCORE.author,'Scott Buckley')
  assert.equal(SCORE.license,'CC BY 4.0')
  assert.equal(CAMPUS_MODULES.length,4)
  const html=fs.readFileSync(path.join(base,'approved-home.html'),'utf8')
  assert.ok(html.includes('Scott Buckley'))
  assert.ok(html.includes('CC BY 4.0'))
})
class FakeContext {
  constructor(){ this.state='running';this.currentTime=0;this.destination={};this.starts=0;this.stops=0 }
  createGain(){return {gain:{value:0,setTargetAtTime(){},setValueAtTime(){},linearRampToValueAtTime(){}},connect(){return this},disconnect(){}}}
  createBufferSource(){const c=this;return {buffer:null,connect(){return this},disconnect(){},start(){c.starts++},stop(){c.stops++}}}
  resume(){this.state='running';return Promise.resolve()}
  close(){this.state='closed';return Promise.resolve()}
}
test('audio is silent and allocates no AudioContext on a normal page visit', async () => {
  const sound=new TourSoundtrack({Context:FakeContext})
  assert.equal(await sound.playAt(0),false)
  assert.equal(sound.context,null)
  sound.destroy()
})
test('pause before asynchronous score readiness prevents ghost playback', async () => {
  const sound=new TourSoundtrack({Context:FakeContext})
  let resolve
  sound.pending=new Promise(done=>{resolve=done})
  sound.setEnabled(true)
  const playing=sound.playAt(()=>4)
  sound.pause()
  resolve({duration:32})
  assert.equal(await playing,false)
  assert.equal(sound.context.starts,0)
  sound.destroy()
})
test('playing, pausing, muting and disposal release the source and context', async () => {
  const sound=new TourSoundtrack({Context:FakeContext})
  sound.pending=Promise.resolve({duration:32})
  sound.setEnabled(true)
  assert.equal(await sound.playAt(7),true)
  assert.equal(sound.context.starts,1)
  sound.setEnabled(false)
  assert.equal(sound.context.stops,1)
  sound.destroy()
  assert.equal(sound.context.state,'closed')
  assert.equal(await sound.playAt(0),false)
})
test('all component listeners have a disposal path and there is no public debug global', () => {
  const source=fs.readFileSync(path.join(base,'runtime.js'),'utf8')
  assert.ok(source.includes('removeEventListener'))
  assert.ok(source.includes('audio?.destroy()'))
  assert.ok(source.includes('releaseScroll()'))
  assert.ok(!source.includes('window.YuekeWebsite='))
  const css=fs.readFileSync(path.join(base,'showcase.css'),'utf8')
  assert.ok(css.includes('#ykw-site .btn'))
  assert.ok(css.includes('body[data-yueke-showcase="active"] .yk-mobile-site-dock'))
})
