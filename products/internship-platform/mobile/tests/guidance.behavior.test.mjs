import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import * as Vue from 'vue'
import { compile } from '@vue/compiler-dom'
import { renderToString } from '@vue/server-renderer'
import { normalizeFileReadiness, refreshFileReadiness } from '../src/services/fileReadiness.mjs'

const source = fs.readFileSync(new URL('../src/pages/teacher-internship/internship-guidance/index.vue', import.meta.url), 'utf8')
const first = { id: '9007199254741003', batchId: '9007199254741001', name: '合成第一页学生', studentNo: '001', enterpriseName: '合成企业' }
const second = { ...first, id: '9007199254741023', name: '合成第二页学生', studentNo: '021' }
const deferred = () => { let resolve; const promise = new Promise(done => { resolve = done }); return { promise, resolve } }

test('从指导页返回学生档案重新读取状态，离页旧响应不能覆盖新归档事实',async()=>{
  const text=fs.readFileSync(new URL('../src/pages/teacher-internship/internship-students/detail.vue',import.meta.url),'utf8')
  const script=text.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import[\s\S]*?from\s+['"][^'"]+['"];?\s*/gm,'').replace('export default','return')
  const reads=[],links=[],context={loaded:true,can:()=>false}
  const component=new Function('teacherInternshipStudentDetail','useInternshipContextStore','formatDateTime','uni',script)(()=>{const pending=deferred();reads.push(pending);return pending.promise},()=>context,v=>v,{navigateTo:value=>links.push(value)})
  const vm=component.data();for(const [name,fn]of Object.entries(component.methods))vm[name]=fn.bind(vm);for(const [name,fn]of Object.entries(component.computed))Object.defineProperty(vm,name,{get:fn.bind(vm)})
  vm.id=first.id;vm.batchId=first.batchId;vm.detail={status:'ONBOARD'}
  const old=vm.load();component.onHide?.call(vm);assert.equal(vm.detail,null)
  const latest=component.onShow?.call(vm);assert.equal(reads.length,2)
  reads[1].resolve({id:first.id,batchId:first.batchId,status:'ARCHIVED'});await latest
  reads[0].resolve({id:first.id,batchId:first.batchId,status:'ONBOARD'});await old
  assert.equal(vm.detail.status,'ARCHIVED');assert.equal(vm.state,'ready');vm.openGuidance();assert.deepEqual(links,[])
})
function page(extra = {}) {
  let generation = 1
  const redirects = [], store = { selectedBatchId: first.batchId, batches: [{ id: first.batchId, name: '合成批次' }],
    restore() {}, load: async () => first.batchId, selectBatch(id) { this.selectedBatchId = String(id) }, can: () => true }
  const deps = { teacherApi: {}, teacherInternshipRoster: async () => ({ items: [first], total: 21 }),
    teacherInternshipStudentDetail: async () => second, useInternshipContextStore: () => store,
    currentSessionGeneration: () => generation, normalizeError: () => ({ text: '操作未完成，请保留输入重试' }),
    realRequest: async () => ({}), fileSdk: {}, uploadBusinessFile: async () => ({}),
    normalizeFileReadiness, refreshFileReadiness, ReportFilePreview: {}, toast() {},
    uni: { redirectTo: x => redirects.push(x) }, ...extra }
  const script = source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import[^\n]+\n/gm, '').replace('export default', 'return')
  const component = new Function(...Object.keys(deps), script)(...Object.values(deps))
  const vm = Vue.reactive(component.data())
  vm.$refs = {}
  for (const [name, fn] of Object.entries(component.methods)) vm[name] = fn.bind(vm)
  for (const [name, fn] of Object.entries(component.computed)) Object.defineProperty(vm, name, { get: fn.bind(vm) })
  return { vm, component, store, redirects, switchAccount: () => generation++ }
}
async function render(p, inspect) {
  const template = source.match(/<template>([\s\S]*?)<\/template>\s*<script>/)[1]
  const render = new Function('Vue', compile(template, { prefixIdentifiers: true, isCustomElement: name => ['view', 'text', 'picker', 'switch'].includes(name) }).code)(Vue)
  const app = Vue.createSSRApp({ render() { const node = render(p.vm, []); inspect?.(node); return node } })
  for (const name of ['MobileGlobalState', 'MobileSafeAreaBar']) app.component(name, { inheritAttrs: false, render() { return this.$slots.default?.() } })
  for (const name of ['MobileNavBar', 'MobileInlineAlert', 'ReportFilePreview']) app.component(name, { render: () => null })
  return renderToString(app)
}
test('分页名单未全部加载仍可指导，正式名单姓名显示正确', async () => {
  const p = page(); await p.vm.load()
  assert.equal(p.vm.selectedStudent.name, first.name)
  assert.match(await render(p), /本次指导内容/)
  assert.match(await render(p), /合成第一页学生/)
})
test('第二页精确深链及隐藏重进保留同一学生正文，目标失效不回退首项', async () => {
  const p = page(); p.vm.requestedRecord = second.id; await p.vm.load()
  assert.equal(p.vm.selectedStudent.id, second.id)
  p.vm.content = '合成第二页指导正文'; p.component.onHide.call(p.vm); p.vm.active = true; await p.vm.load(true)
  assert.equal(p.vm.selectedStudent.id, second.id); assert.equal(p.vm.content, '合成第二页指导正文')
  const q = page({ teacherInternshipStudentDetail: async () => { throw { httpStatus: 403 } } })
  q.vm.requestedRecord = second.id; await q.vm.load()
  assert.equal(q.vm.state, 'error'); assert.equal(q.vm.selectedStudent, null)
})
test('未确认提交保持原内容与稳定键，重试成功转原记录详情', async () => {
  const writes = []; let retry = false
  const p = page({ teacherApi: { createInternshipGuidance: async body => {
    writes.push({ ...body }); if (!retry) throw { biz: true, code: 'REQUEST_TIMEOUT' }
    return { id: '901', internshipId: first.id, batchId: first.batchId }
  } } })
  await p.vm.load(); p.vm.content = '合成指导正文'; p.vm.guidanceDate = '2026-10-06'
  await p.vm.submit(); assert.ok(p.vm.pendingBody)
  assert.match(await render(p), /textarea[^>]*disabled/)
  retry = true; await p.vm.submit()
  assert.deepEqual(writes[0], writes[1]); assert.match(p.redirects[0].url, /guidanceId=901/)
})

test('未知保存后名单加载失败，再恢复仍锁定原学生和批次并按原键核对', async () => {
  let rosterFails = false, saved = false
  const writes = [], p = page({
    teacherInternshipRoster: async () => { if (rosterFails) throw { code: 'ERR_NETWORK' }; return { items: [first], total: 21 } },
    teacherApi: { createInternshipGuidance: async body => {
      writes.push({ ...body }); if (!saved) throw { code: 'ERR_NETWORK' }
      return { id: '901', internshipId: second.id, batchId: second.batchId }
    } }
  })
  p.vm.requestedRecord = second.id; await p.vm.load(); p.vm.requestedRecord = ''
  p.vm.content = '合成第二页指导正文'; p.vm.guidanceDate = '2026-10-06'
  await p.vm.submit(); const original = p.vm.pendingBody
  function findButton(node) {
    if (node?.type === 'button' && node.children === '重新读取学生名单') return node
    for (const child of Array.isArray(node?.children) ? node.children : []) {
      const found = findButton(child); if (found) return found
    }
    return node?.children?.default ? findButton({ children: node.children.default() }) : null
  }
  let reloadButton
  await render(p, node => { reloadButton = findButton(node) })
  assert.ok(reloadButton); assert.equal(reloadButton.props.disabled, false)
  rosterFails = true; await reloadButton.props.onClick()
  assert.equal(p.vm.state, 'error'); assert.equal(p.vm.selectedStudent, null)
  p.component.onHide.call(p.vm); p.vm.active = true; await p.vm.load(true)
  assert.equal(p.vm.state, 'error'); assert.equal(p.vm.selectedStudent, null)
  rosterFails = false; await p.vm.load()
  assert.equal(p.vm.selectedStudent.id, second.id); assert.equal(p.vm.pendingBody, original)
  saved = true; await p.vm.submit()
  assert.deepEqual(writes[0], writes[1]); assert.match(p.redirects[0].url, /guidanceId=901/)

  const q = page(); await q.vm.load()
  q.vm.pendingBody = { internshipId: first.id, batchId: first.batchId, requestKey: 'original-key' }
  q.store.selectedBatchId = 'other-batch'; await q.vm.load()
  assert.equal(q.vm.state, 'error'); assert.equal(q.vm.selectedStudent, null)
  assert.equal(q.vm.pendingBody.requestKey, 'original-key')
})
test('相册临时隐藏不丢弃同一对象选择，换对象或账号的迟到照片拒绝', async () => {
  const ready = { fileId: '81', fileName: '合成原图.png', storageStatus: 'AVAILABLE', scanStatus: 'CLEAN' }
  const pick = deferred(), p = page({ fileSdk: { choose: () => pick.promise }, uploadBusinessFile: async () => ready })
  await p.vm.load(); const choosing = p.vm.choosePhoto()
  p.component.onHide.call(p.vm); p.component.onShow.call(p.vm)
  pick.resolve({ path: '合成原图.png', name: '合成原图.png' }); await choosing
  assert.equal(p.vm.photo?.fileId, '81'); assert.equal(p.vm.uploading, false)
  for (const change of [q => q.switchAccount(), q => q.component.onUnload.call(q.vm)]) {
    const late = deferred(), q = page({ fileSdk: { choose: () => late.promise }, uploadBusinessFile: async () => ready })
    await q.vm.load(); const pending = q.vm.choosePhoto(); change(q)
    late.resolve({ path: '合成原图.png', name: '合成原图.png' }); await pending
    assert.equal(q.vm.photo, null)
  }
})

test('已有未知提交后权限拒绝仍锁住原正文，首次明确拒绝才允许改正', async () => {
  for (const unknownFirst of [true, false]) {
    let attempts = 0
    const p = page({ teacherApi: { createInternshipGuidance: async () => {
      if (unknownFirst && ++attempts === 1) throw { code: 'ERR_NETWORK' }
      throw { biz: true, httpStatus: 403, message: '当前学生已不在指导范围' }
    } } })
    await p.vm.load(); p.vm.content = '合成指导正文'; p.vm.guidanceDate = '2026-10-06'
    await p.vm.submit(); const original = p.vm.pendingBody, key = p.vm.requestKey
    if (unknownFirst) {
      await p.vm.submit(); assert.equal(p.vm.pendingBody, original); assert.equal(p.vm.requestKey, key)
      assert.match(await render(p), /textarea[^>]*disabled/)
    } else { assert.equal(p.vm.pendingBody, null); assert.equal(p.vm.requestKey, '') }
  }
})
test('已保存详情刷新按同编号读取，拒绝跨批次回执且不虚报保存', async () => {
  const p = page({ realRequest: async () => ({ id: '901', batchId: first.batchId, internshipId: first.id, content: '合成已保存正文' }) })
  p.vm.receiptId = '901'; await p.vm.load(); assert.equal(p.vm.receipt.content, '合成已保存正文')
  const q = page({ realRequest: async () => ({ id: '901', batchId: 'other' }) })
  q.vm.receiptId = '901'; await q.vm.load(); assert.equal(q.vm.receipt, null)
  assert.doesNotMatch(q.vm.actionError, /记录已保存/)
})

test('移动回读显示同编号并调用现有查看器；隐藏与迟到附件不会串入另一原单', async () => {
  const attachment = { fileId: '81', fileName: '并行A-指导.png' }
  const p = page({ realRequest: async () => ({ id: '901', batchId: first.batchId, internId: first.id, attachment }) })
  p.vm.receiptId = '901'; p.vm.requestedRecord = first.id; await p.vm.load()
  assert.match(await render(p), /指导编号：901/); assert.match(await render(p), /查看指导佐证/)
  const opened = [], late = deferred(); let resets = 0
  p.vm.$refs.receiptPreview = { open: file => { opened.push(file.fileId); return late.promise }, reset: () => resets++ }
  const reading = p.vm.openReceiptAttachment(); p.component.onHide.call(p.vm)
  late.resolve(); await reading
  assert.deepEqual(opened, ['81']); assert.equal(resets, 2)
  p.vm.active = true; p.vm.receipt = null; await p.vm.openReceiptAttachment()
  assert.deepEqual(opened, ['81'])
})
