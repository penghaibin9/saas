import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import vm from 'node:vm'
import * as Vue from 'vue'
import { compile } from '@vue/compiler-dom'
import { parse } from '@vue/compiler-sfc'
import { renderToString } from 'vue/server-renderer'
import * as labels from '../src/modules/messageCenter/constants/message-center.constants.js'
import { safeBusinessMessage, safeEnumLabel } from '../src/utils/presentationSafety.js'

function component(file, overrides = {}) {
  const source = readFileSync(new URL(`../src/modules/messageCenter/views/${file}`, import.meta.url), 'utf8')
  const { descriptor } = parse(source)
  const script = descriptor.script.content
    .replace(/^import\s+([\s\S]*?)\s+from\s+['"][^'"]+['"]\s*$/gm, (_, binding) => `const ${binding} = dependencies${binding.startsWith('{') ? '' : '.' + binding}`)
    .replace('export default', 'component =')
  const shell = { setup: (_, { slots }) => () => Vue.h('main', slots.default?.()) }
  const error = { props: ['description'], setup: props => () => Vue.h('p', { role: 'alert' }, props.description) }
  const dependencies = { ...labels, safeBusinessMessage, safeEnumLabel, ModulePageShell: shell, ErrorState: error,
    LoadingState: { render: () => Vue.h('p', '正在加载') },
    EmptyState: { props: ['title'], setup: props => () => Vue.h('p', props.title) }, ...overrides }
  const sandbox = { dependencies }
  vm.runInNewContext(script, sandbox)
  sandbox.component.render = new Function('Vue', compile(descriptor.template.content, { mode: 'function', prefixIdentifiers: true }).code)(Vue)
  return sandbox.component
}

async function render(file, data) {
  const page = component(file)
  return renderToString(Vue.createSSRApp({ ...page, created: undefined, mounted: undefined, data: () => ({ ...page.data(), ...data }) }))
}

const visible = html => html.replace(/<details\b[^>]*>[\s\S]*?<\/details>/g, '')

test('消息渠道、任务和告警采用中文，未知值及特殊属性名不外露', () => {
  assert.equal(labels.messageChannelLabel('IN_APP'), '站内消息')
  assert.equal(labels.messageChannelLabel('SMS'), '短信')
  assert.equal(labels.messageJobKindLabel('OUTBOX'), '业务通知')
  assert.equal(labels.messageAlertLabel('DELIVERY_JOB_DEAD'), '消息投递失败')
  assert.equal(labels.messageChannelStatusLabel('DEGRADED'), '部分功能暂不可用')
  for (const value of ['NEW_CHANNEL', 'constructor', '__proto__', '中文 INTERNAL_CODE']) {
    assert.equal(labels.messageChannelLabel(value), '其他渠道')
  }
})

test('模板正文不再以内部编号补标题，实施信息默认折叠', async () => {
  const html = await render('MessageTemplateView.vue', { items: [{ templateId: '1', templateCode: 'HUMAN_ANNOUNCE', eventCode: 'INTERNAL_EVENT', channel: 'SMS', version: 4, enabled: true, title: '', previewSample: '测试通知' }] })
  assert.match(visible(html), /未命名模板/)
  assert.match(visible(html), /短信/)
  assert.doesNotMatch(visible(html), /HUMAN_ANNOUNCE|INTERNAL_EVENT/)
  assert.match(html, /<summary>实施人员使用<\/summary>/)
  assert.doesNotMatch(html, /<details[^>]*\bopen\b/)
})

test('投递运维正文显示中文统计，原始编号与对账结果折叠保留', async () => {
  const html = await render('MessageOpsView.vue', {
    letters: [{ jobId: '1000000000000000007', kind: 'OUTBOX', campaignId: '1000000000000000008', eventCode: 'INTERNAL_EVENT', attemptCount: 3, lastError: 'SQLSTATE 23000' }],
    reconcile: { backlog: { outboxPending: 0, outboxDead: 2, deliveryPending: 4, deliveryDead: 1 }, driftFixed: 0, alerts: [{ code: 'DELIVERY_JOB_DEAD', count: 1 }] }
  })
  assert.match(visible(html), /待处理通知 0/)
  assert.match(visible(html), /消息投递失败：1/)
  assert.match(visible(html), /业务通知/)
  assert.doesNotMatch(visible(html), /1000000000000000007|INTERNAL_EVENT|outboxPending|SQLSTATE|partial/)
  assert.doesNotMatch(html, /<details[^>]*\bopen\b/)
})

test('运维加载中和对账错误不能展示为无失败任务或零统计', async () => {
  const loading = await render('MessageOpsView.vue', { loading: true })
  assert.match(loading, /正在加载/)
  assert.doesNotMatch(loading, /暂无失败任务/)
  const failed = await render('MessageOpsView.vue', { reconcile: { error: '对账读取失败' } })
  assert.match(failed, /role="alert"/)
  assert.match(failed, /对账读取失败/)
  assert.doesNotMatch(failed, /待处理通知 0/)
})

test('重试继续使用原始任务编号和任务类型，显示转换不改写请求', async () => {
  let sent
  const page = component('MessageOpsView.vue', { retryDeadLetter: async (...args) => { sent = args } })
  const state = { load: async () => {}, error: '' }
  await page.methods.retry.call(state, { jobId: '1000000000000000007', kind: 'OUTBOX' })
  assert.equal(sent[0], '1000000000000000007')
  assert.equal(sent[1].kind, 'OUTBOX')
  assert.equal(state.error, '')
})

test('发布记录中的风险预警和重要等级不再被当作未知值', async () => {
  const html = await render('MessageOutboxView.vue', { rows: [{ campaignId: '1', title: '风险提醒', category: 'WARNING', priority: 'IMPORTANT', status: 'PARTIAL_FAILED', recipientCount: 1, deliveredCount: 0, createdAt: '2026-10-24T00:00:00Z' }], total: 1 })
  assert.match(visible(html), /风险预警 · 重要/)
  assert.match(visible(html), /部分失败/)
  assert.doesNotMatch(visible(html), /WARNING|IMPORTANT|PARTIAL_FAILED|类型待确认|优先级待确认/)
})
