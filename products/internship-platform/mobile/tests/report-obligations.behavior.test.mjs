import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import { normalizeError } from './request-module.mjs'
import * as Vue from 'vue'
import { compile } from '@vue/compiler-dom'
import { renderToString } from '@vue/server-renderer'

const source = fs.readFileSync(new URL('../src/components/teacher/ReportObligations.vue', import.meta.url), 'utf8')
function page(api) {
  let generation = 1
  const script = source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import[^\n]*\n/gm, '').replace('export default', 'return')
  const component = new Function('teacherApi', 'normalizeError', 'currentSessionGeneration', script)(api, normalizeError, () => generation)
  const vm = { ...component.data(), batchId: '9007199254741001', canReview: true, initialType: 'DAILY' }
  for (const [key, fn] of Object.entries(component.methods)) vm[key] = fn.bind(vm)
  Object.defineProperty(vm, 'metricKey', { get: component.computed.metricKey.bind(vm) })
  return { vm, leave: () => component.beforeUnmount.call(vm), switchAccount: () => generation++ }
}
const row = id => ({ recordId: String(id), studentName: `合成学生${id}`, daily: { configured: true, required: 2, submitted: 1, approved: 0, missing: 1 } })
const deferred = () => { let resolve; const promise = new Promise(done => { resolve = done }); return { promise, resolve } }

test('全部或已交名单首屏没有欠交也能催交后页学生，空未交名单不发送', async () => {
  const sent = [], p = page({ getReportObligations: async () => ({ total: 1, items: [row(21)] }),
    remindReportObligation: async id => sent.push(id) })
  const template = source.match(/<template>([\s\S]*?)<\/template>\s*<script>/)[1]
  const render = new Function('Vue', compile(template, { prefixIdentifiers: true, isCustomElement: name => ['view', 'text', 'picker'].includes(name) }).code)(Vue)
  p.vm.opened = true; p.vm.total = 21
  p.vm.rows = Array.from({ length: 20 }, (_, index) => ({ ...row(index + 1), daily: { configured: true, required: 1, submitted: 1, approved: 1, missing: 0 } }))
  for (const submittedOnly of [false, true]) {
    p.vm.missingOnly = false; p.vm.submittedOnly = submittedOnly
    const html = await renderToString(Vue.createSSRApp({ render: () => render(p.vm, []) }))
    const attrs = html.match(/<button([^>]*)>提醒该类型全部未交学生<\/button>/)[1]
    assert.doesNotMatch(attrs, /disabled/)
  }
  await p.vm.remindAll(); assert.deepEqual(sent, ['21'])
  p.vm.missingOnly = true; p.vm.rows = []; p.vm.total = 0
  const html = await renderToString(Vue.createSSRApp({ render: () => render(p.vm, []) }))
  assert.match(html.match(/<button([^>]*)>提醒该类型全部未交学生<\/button>/)[1], /disabled/)
})

test('催交先完整读取跨页名单，逐人使用同批次和类型，重复对象只登记一次', async () => {
  const calls = [], p = page({ getReportObligations: async q => { calls.push(['read', q]); return { total: 3, items: q.page === 1 ? [row(1), row(2)] : [row(2), row(3)] } },
    remindReportObligation: async (...args) => calls.push(['send', ...args]) })
  await p.vm.remindAll()
  assert.deepEqual(calls.map(x => x[0]), ['read', 'read', 'send', 'send', 'send'])
  assert.deepEqual(calls.slice(2).map(x => x.slice(1)), ['1', '2', '3'].map(id => [id, p.vm.batchId, 'DAILY']))
  assert.match(p.vm.receipt.text, /已登记 3 人，未登记 0 人/)
})

test('五分钟重复催交是逐人拒绝，后续对象仍登记；未知响应停止，不自动重试', async () => {
  for (const known of [true, false]) {
    const sent = [], p = page({ getReportObligations: async () => ({ total: 2, items: [row(1), row(2)] }),
      remindReportObligation: async id => { sent.push(id); if (id === '1') throw known ? { statusCode: 409, bizCode: 'DATA_CONFLICT', message: '5分钟内已催交，请稍后再试' } : new Error('network') } })
    await p.vm.remindAll()
    assert.deepEqual(sent, known ? ['1', '2'] : ['1'])
    assert.equal(p.vm.receipt.failures.length, 1)
    assert.match(p.vm.receipt.text, known ? /已登记 1 人，未登记 1 人/ : /已停止后续 1 人/)
    assert.equal(p.vm.sending, false)
  }
})

test('离页或账号切换时已发请求可完成，下一人不再发送且不回填旧回执', async () => {
  for (const stop of ['leave', 'switchAccount']) {
    const pending = deferred(), sent = [], p = page({ getReportObligations: async () => ({ total: 2, items: [row(1), row(2)] }),
      remindReportObligation: async id => { sent.push(id); await pending.promise } })
    const run = p.vm.remindAll(); await Promise.resolve(); await Promise.resolve()
    assert.deepEqual(sent, ['1']); p[stop](); pending.resolve(); await run
    assert.deepEqual(sent, ['1']); assert.equal(p.vm.receipt, null)
  }
})

test('无有效绑定账号属于逐人失败，保留原因并继续其他学生', async () => {
  const sent = [], p = page({ getReportObligations: async () => ({ total: 2, items: [row(1), row(2)] }),
    remindReportObligation: async id => { sent.push(id); if (id === '1') throw { code: 1, biz: true, bizCode: 'DATA_NOT_FOUND', httpStatus: 400, message: '学生没有有效绑定账号，未发送提醒' } } })
  await p.vm.remindAll()
  assert.deepEqual(sent, ['1', '2']); assert.match(p.vm.receipt.text, /已登记 1 人，未登记 1 人/)
  assert.equal(p.vm.receipt.failures[0].message, '学生没有有效绑定账号，未发送提醒')
})

test('跨页读取时缺交人数变化或重复页导致集合不全，尚未发送便停止', async () => {
  for (const changed of [true, false]) {
    let sends = 0
    const p = page({ getReportObligations: async query => ({ total: changed && query.page === 2 ? 2 : 3, items: query.page === 1 ? [row(1), row(2)] : [row(1)] }),
      remindReportObligation: async () => sends++ })
    await p.vm.remindAll(); assert.equal(sends, 0)
    assert.match(p.vm.receipt.text, /未发送催交.*未交名单已变化/)
  }
})

test('名单读取失败、空页缺口、只读权限及重复点击均不会多发', async () => {
  let sends = 0
  for (const read of [async () => { throw new Error('offline') }, async () => ({ total: 2, items: [] })]) {
    const p = page({ getReportObligations: read, remindReportObligation: async () => sends++ })
    await p.vm.remindAll(); assert.match(p.vm.receipt.text, /未发送催交/)
  }
  const pending = deferred(), p = page({ getReportObligations: async () => { await pending.promise; return { total: 1, items: [row(1)] } }, remindReportObligation: async () => sends++ })
  p.vm.canReview = false; await p.vm.remindAll(); assert.equal(sends, 0)
  p.vm.canReview = true; const run = p.vm.remindAll(); await p.vm.remindAll(); pending.resolve(); await run; assert.equal(sends, 1)
})

test('切换类型丢弃迟到名单，失败显示错误而非无学生，零应交不伪造缺交', async () => {
  const pending = deferred(), queries = [], p = page({ getReportObligations: async q => { queries.push(q); if (q.reportType === 'DAILY') return pending.promise; return { total: 1, items: [row(2)] } } })
  const first = p.vm.load(); p.vm.typeIndex = 3; await p.vm.load(); pending.resolve({ total: 1, items: [row(1)] }); await first
  assert.equal(p.vm.rows[0].recordId, '2'); assert.equal(queries[1].reportType, 'SUMMARY')
  p.vm.typeIndex = 0; assert.match(p.vm.metricText({ daily: { configured: false, submitted: 0 } }), /应交数未配置/)
  assert.match(p.vm.metricText(row(1)), /已交 1 篇.*缺交 1 篇/)
})

test('已交、未交与全部名单使用互斥查询，批量催交仍读取真实未交名单', async () => {
  const calls = [], p = page({ getReportObligations: async query => { calls.push(query); return { items: [], total: 0 } } })
  p.vm.setSubmitted(); await Promise.resolve()
  assert.equal(calls[0].submittedOnly, true); assert.equal(calls[0].missingOnly, false)
  p.vm.setMissing(true); await Promise.resolve()
  assert.equal(calls[1].submittedOnly, false); assert.equal(calls[1].missingOnly, true)
  p.vm.setMissing(false); await Promise.resolve()
  assert.equal(calls[2].submittedOnly, false); assert.equal(calls[2].missingOnly, false)
})
