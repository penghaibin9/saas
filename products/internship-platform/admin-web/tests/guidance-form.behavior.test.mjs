import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import * as Vue from 'vue'
import { compile } from '@vue/compiler-dom'
import { renderToString } from '@vue/server-renderer'
import { normalizeUiError } from '../src/utils/presentationSafety.js'

const source = fs.readFileSync(new URL('../src/modules/internship/views/GuidanceRecordFormView.vue', import.meta.url), 'utf8')
const first = '9007199254741003', second = '9007199254741023'
const deferred = () => { let resolve; const promise = new Promise(done => { resolve = done }); return { promise, resolve } }
function page(api = {}) {
  let generation = 1
  const store = { selectedBatchId: '9007199254741001', withBatchQuery: query => ({ ...query, batchId: store.selectedBatchId }) }
  const deps = { guidanceVisitApi: api, normalizeUiError, currentSessionGeneration: () => generation,
    useInternshipBatchStore: () => store, TYPE_META: {}, window: {}, toast: { success() {} } }
  const imports = [...source.matchAll(/^import ([\s\S]*?) from [^\n]+$/gm)].flatMap(([, names]) => names.replace(/[{}]/g, '').split(',').map(x => x.trim()))
  const script = source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import[\s\S]*? from [^\n]+\n/gm, '').replace('export default', 'return')
  const names = [...imports, 'window']
  const component = new Function(...names, script)(...names.map(name => deps[name] ?? {}))
  const vm = { ...component.data(), $refs: {}, $nextTick: async () => {}, $route: { query: {} }, $router: { push() {} } }
  for (const [name, fn] of Object.entries(component.methods)) vm[name] = fn.bind(vm)
  for (const [name, fn] of Object.entries(component.computed)) Object.defineProperty(vm, name, { get: fn.bind(vm) })
  Object.assign(vm.form, { internshipIds: [first, second], guidanceDate: '2026-10-06', content: '合成批量指导正文' })
  vm.onGuidanceStudents([first, second], [{ value: first, raw: { name: '合成第一学生', studentNo: '001' } }, { value: second, raw: { name: '合成第二学生', studentNo: '021' } }])
  return { vm, component, store, switchAccount: () => generation++ }
}
const result = (body, failSecond = false) => ({ code: 0, data: { batchId: body.batchId, items: body.items.map(item =>
  failSecond && item.internshipId === second ? { internshipId: second, requestKey: item.requestKey, success: false, code: 'NO_PERMISSION', message: '该学生已不在指导范围' }
    : { internshipId: item.internshipId, requestKey: item.requestKey, success: true, id: 'guide-' + item.internshipId }) } })

test('巡访保存成功清理已提交表单后跳转原记录，失败保留内容不放行', async () => {
  for (const code of [0, 1]) {
    const writes = [], p = page({ createVisit: async body => { writes.push(body); return { code, data: { id: 'visit-8' }, message: '稍后重试' } } })
    p.vm.type = 'visit'; Object.assign(p.vm.form, { internshipId: first, title: '合成巡访', monthlyReport: '已经填写的巡访内容', fileId: '81' })
    p.vm.attachName = '合成佐证.pdf'
    let flushed = false, destination
    p.vm.$nextTick = async () => { assert.equal(p.vm.form.monthlyReport, ''); flushed = true }
    p.vm.$router.push = route => { assert.equal(flushed, true); destination = route }
    await p.vm.doSubmit()
    assert.equal(writes[0].monthlyReport, '已经填写的巡访内容')
    if (code === 0) {
      assert.equal(destination.query.id, 'visit-8'); assert.equal(destination.query.batchId, p.store.selectedBatchId)
      assert.equal(p.vm.form.internshipId, ''); assert.equal(p.vm.attachName, '')
      await p.vm.doSubmit(); assert.equal(writes.length, 1)
    } else {
      assert.equal(destination, undefined); assert.equal(flushed, false)
      assert.equal(p.vm.form.monthlyReport, '已经填写的巡访内容'); assert.equal(p.vm.attachName, '合成佐证.pdf')
    }
  }
})

async function render(p) {
  const template = source.match(/<template>([\s\S]*?)<\/template>\s*<script>/)[1]
  const render = new Function('Vue', compile(template, { prefixIdentifiers: true }).code)(Vue)
  const app = Vue.createSSRApp({ render() { return render(p.vm, []) } })
  const button = { inheritAttrs: false, props: ['disabled'], render() { return Vue.h('button', { disabled: this.disabled }, this.$slots.default?.()) } }
  for (const name of new Set([...source.matchAll(/<([A-Z][A-Za-z]+)/g)].map(match => match[1]))) {
    app.component(name, name === 'AppButton' ? button : { inheritAttrs: false, render() { return this.$slots.default?.() } })
  }
  return renderToString(app)
}
test('电脑批量为每人独立上传和绑定，成功回执逐人保留姓名', async () => {
  let file = 80; const writes = [], p = page({ uploadAttachment: async () => ({ code: 0, data: { fileId: String(++file) } }),
    getAttachmentMetadata: async id => ({ code: 0, data: { fileId: id, readyForBusiness: true } }),
    createGuidancesBatch: async body => { writes.push(body); return result(body) } })
  p.vm.selectedGuidanceFile = { name: '合成指导.png' }; await p.vm.submitGuidances()
  assert.deepEqual(writes[0].items.map(item => item.fileId), ['81', '82'])
  assert.notEqual(writes[0].items[0].requestKey, writes[0].items[1].requestKey)
  assert.equal(p.vm.guidanceResults[1].studentName, '合成第二学生'); assert.equal(p.vm.submitting, false)
})
test('部分失败只重试失败学生，原键不变，成功学生不会重复创建', async () => {
  const writes = [], p = page({ createGuidancesBatch: async body => { writes.push(body); return result(body, writes.length === 1) } })
  await p.vm.submitGuidances(); await p.vm.submitGuidances()
  assert.equal(writes[1].items.length, 1); assert.equal(writes[1].items[0].internshipId, second)
  assert.equal(writes[0].items[1].requestKey, writes[1].items[0].requestKey)
  assert.equal(p.vm.guidanceResults.length, 2); assert.ok(p.vm.guidanceResults.every(row => row.success))
})
test('未确认的网络提交保持原输入和键，不能修改；重试回执可核对原记录', async () => {
  const writes = [], p = page({ createGuidancesBatch: async body => { writes.push(body); if (writes.length === 1) throw { code: 'ERR_NETWORK' }; return result(body) } })
  await p.vm.submitGuidances(); const original = p.vm.pendingGuidance
  assert.equal(p.vm.guidanceUnconfirmed, true); p.vm.editFailedGuidances(); assert.equal(p.vm.pendingGuidance, original)
  await p.vm.submitGuidances(); assert.deepEqual(writes[0], writes[1]); assert.equal(p.vm.guidanceUnconfirmed, false)
})
test('明确校验拒绝可以修改原草稿，成功项保留且修改仅针对失败对象', async () => {
  let fail = false
  const p = page({ createGuidancesBatch: async body => fail ? { code: 1, httpStatus: 422, biz: true, message: '请补齐实际日期' } : result(body, true) })
  await p.vm.submitGuidances(); fail = true; await p.vm.submitGuidances()
  assert.equal(p.vm.guidanceUnconfirmed, false); p.vm.editFailedGuidances()
  assert.deepEqual(p.vm.form.internshipIds, [second]); assert.equal(p.vm.guidanceResults[0].internshipId, first)
  assert.equal(p.vm.form.content, '合成批量指导正文'); assert.equal(p.vm.pendingGuidance, null)
})
test('未完成安全检查不保存，可以修改尚未提交内容，学生与文件原输入保留', async () => {
  let saved = false
  const p = page({ uploadAttachment: async () => ({ code: 0, data: { fileId: '81' } }),
    getAttachmentMetadata: async id => ({ code: 0, data: { fileId: id, readyForBusiness: false } }), createGuidancesBatch: async () => { saved = true } })
  p.vm.selectedGuidanceFile = { name: '合成指导.png' }; await p.vm.submitGuidances()
  assert.equal(saved, false); assert.equal(p.vm.guidanceUnconfirmed, false)
  p.vm.editFailedGuidances(); assert.deepEqual(p.vm.form.internshipIds, [first, second]); assert.ok(p.vm.selectedGuidanceFile)
})

test('已有未知提交遇到附件撤权或命令拒绝，仍保留原键和锁定正文', async () => {
  for (const rejectMetadata of [true, false]) {
    let rejected = false
    const p = page({ uploadAttachment: async () => ({ code: 0, data: { fileId: '81' } }),
      getAttachmentMetadata: async id => {
        if (rejected && rejectMetadata) throw { httpStatus: 404, biz: true, message: '当前材料不可访问' }
        return { code: 0, data: { fileId: id, readyForBusiness: true } }
      },
      createGuidancesBatch: async () => {
        if (rejected) throw { httpStatus: 403, biz: true, message: '当前指导范围已变化' }
        throw { code: 'ERR_NETWORK' }
      } })
    p.vm.selectedGuidanceFile = { name: '合成指导.png' }
    await p.vm.submitGuidances(); const original = p.vm.pendingGuidance, keys = p.vm.guidanceTargets.map(row => row.requestKey)
    rejected = true; await p.vm.submitGuidances(); p.vm.editFailedGuidances()
    assert.equal(p.vm.guidanceUnconfirmed, true); assert.equal(p.vm.pendingGuidance, original)
    assert.deepEqual(p.vm.guidanceTargets.map(row => row.requestKey), keys)
  }
})
test('迟到回执不能进入切换后的批次、账号或卸载的页面', async () => {
  for (const change of [p => { p.store.selectedBatchId = 'other' }, p => p.switchAccount(), p => p.component.beforeUnmount.call(p.vm)]) {
    const pending = deferred(), p = page({ createGuidancesBatch: () => pending.promise })
    const saving = p.vm.submitGuidances(); change(p); pending.resolve(result({ batchId: '9007199254741001', items: [{ internshipId: first }, { internshipId: second }] })); await saving
    assert.equal(p.vm.guidanceResults.length, 0)
  }
})
test('不完整回执保持原重试合同，技术异常不出现在用户错误文案中', async () => {
  const p = page({ createGuidancesBatch: async () => ({ code: 0, data: { batchId: 'other', items: [] } }) })
  await p.vm.submitGuidances(); assert.equal(p.vm.guidanceUnconfirmed, true); assert.ok(p.vm.submitError)
  const q = page({ createGuidancesBatch: async () => { throw new Error('SQLAlchemy Internal Server Error token password') } })
  await q.vm.submitGuidances(); assert.doesNotMatch(q.vm.submitError, /SQLAlchemy|token|password|Internal/)
})

test('附件准备逐学生回执，第二人失败不阻断第一人；重试只处理失败对象并复用文件和键', async () => {
  let uploadCount = 0, ready = false
  const writes = [], p = page({ uploadAttachment: async () => ({ code: 0, data: { fileId: String(80 + ++uploadCount) } }),
    getAttachmentMetadata: async id => ({ code: 0, data: { fileId: id, readyForBusiness: id === '81' || ready } }),
    createGuidancesBatch: async body => { writes.push(structuredClone(body)); return result(body) } })
  p.vm.selectedGuidanceFile = { name: '并行A-指导.docx' }
  await p.vm.submitGuidances()
  assert.equal(writes.length, 1); assert.deepEqual(writes[0].items.map(row => row.internshipId), [first])
  assert.equal(p.vm.guidanceResults.length, 2); assert.equal(p.vm.guidanceResults.find(row => row.internshipId === second).success, false)
  const key = p.vm.guidanceTargets.find(row => row.internshipId === second).requestKey
  ready = true; await p.vm.submitGuidances()
  assert.equal(uploadCount, 2); assert.equal(writes[1].items[0].requestKey, key)
  assert.deepEqual(writes[1].items.map(row => row.internshipId), [second]); assert.ok(p.vm.guidanceResults.every(row => row.success))
})

test('未知结果重试收到逐人拒绝仍锁住原键；每名学生都有未确认回执', async () => {
  let calls = 0
  const p = page({ createGuidancesBatch: async body => {
    if (++calls === 1) throw { code: 'ERR_NETWORK' }
    return { code: 0, data: { batchId: body.batchId, items: body.items.map(row => ({ internshipId: row.internshipId, requestKey: row.requestKey, success: false, code: 'NO_PERMISSION', message: '指导关系已撤销' })) } }
  } })
  await p.vm.submitGuidances()
  assert.equal(p.vm.guidanceResults.length, 2); assert.ok(p.vm.guidanceResults.every(row => row.unconfirmed))
  const original = p.vm.pendingGuidance, keys = p.vm.guidanceTargets.map(row => row.requestKey)
  await p.vm.submitGuidances(); p.vm.editFailedGuidances()
  assert.equal(p.vm.guidanceUnconfirmed, true); assert.equal(p.vm.pendingGuidance, original)
  assert.deepEqual(p.vm.guidanceTargets.map(row => row.requestKey), keys)
})

test('明确上传拒绝逐人显示且继续其他对象；十类采购文件均保留原文件上传', async () => {
  for (const ext of ['jpg', 'jpeg', 'png', 'rar', 'zip', 'doc', 'docx', 'pdf', 'xls', 'xlsx']) {
    const picked = { name: '并行A-指导.' + ext }, writes = []; let count = 0
    const p = page({ uploadAttachment: async file => {
      assert.equal(file, picked)
      if (++count === 1) return { code: 1, biz: true, httpStatus: 422, message: '附件内容与格式不符' }
      return { code: 0, data: { fileId: '82' } }
    }, getAttachmentMetadata: async id => ({ code: 0, data: { fileId: id, readyForBusiness: true } }),
    createGuidancesBatch: async body => { writes.push(body); return result(body) } })
    p.vm.selectedGuidanceFile = picked; await p.vm.submitGuidances()
    assert.equal(p.vm.guidanceResults.length, 2); assert.equal(p.vm.guidanceUnconfirmed, false)
    assert.deepEqual(writes[0].items.map(row => row.internshipId), [second])
    assert.match(p.vm.guidanceResults.find(row => row.internshipId === first).message, /附件/)
  }
})

test('失败回执携带未确认标记或错配原键时，不能修改原内容或虚报保存', async () => {
  for (const wrongKey of [false, true]) {
    const p = page({ createGuidancesBatch: async body => ({ code: 0, data: { batchId: body.batchId, items: body.items.map(row =>
      wrongKey ? { internshipId: row.internshipId, requestKey: 'other-key', id: '901', success: true }
        : { internshipId: row.internshipId, requestKey: row.requestKey, success: false, saveUnconfirmed: true, message: '留痕暂不可用' }) } }) })
    await p.vm.submitGuidances(); const original = p.vm.pendingGuidance
    p.vm.editFailedGuidances()
    assert.equal(p.vm.pendingGuidance, original); assert.equal(p.vm.guidanceUnconfirmed, true)
    assert.equal(p.vm.guidanceResults.length, 2); assert.ok(p.vm.guidanceResults.every(row => !row.success && row.unconfirmed))
  }
})

test('缺少或空原键的回执不能报成功，重试仍使用原内容和原键', async () => {
  for (const key of [undefined, '']) {
    const writes = []; let complete = false
    const p = page({ createGuidancesBatch: async body => {
      writes.push(structuredClone(body)); const receipt = result(body)
      if (!complete) receipt.data.items[0].requestKey = key
      return receipt
    } })
    await p.vm.submitGuidances(); const original = p.vm.pendingGuidance
    assert.equal(p.vm.guidanceUnconfirmed, true); assert.ok(p.vm.guidanceResults.every(row => !row.success))
    p.vm.editFailedGuidances(); assert.equal(p.vm.pendingGuidance, original)
    complete = true; await p.vm.submitGuidances()
    assert.deepEqual(writes[0], writes[1]); assert.ok(p.vm.guidanceResults.every(row => row.success))
  }
})

test('实际表单模板显示逐人姓名和未确认结果，锁定输入，十格式选择与成功编号可见', async () => {
  let retry = false
  const p = page({ createGuidancesBatch: async body => { if (!retry) throw { code: 'ERR_NETWORK' }; return result(body) } })
  await p.vm.submitGuidances()
  const unknown = await render(p)
  assert.match(unknown, /合成第一学生（001）/); assert.match(unknown, /合成第二学生（021）/)
  assert.match(unknown, /保存结果待确认/); assert.match(unknown, /fieldset[^>]*disabled/)
  assert.doesNotMatch(unknown, /修改未完成内容|ERR_NETWORK|requestKey|SAVE_FAILED/)
  assert.match(unknown, /accept="\.jpg,\.jpeg,\.png,\.rar,\.zip,\.doc,\.docx,\.pdf,\.xls,\.xlsx"/)
  retry = true; await p.vm.submitGuidances()
  const saved = await render(p)
  assert.match(saved, /已保存，指导编号/); assert.match(saved, /查看原记录/)
})
