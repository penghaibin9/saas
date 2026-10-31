import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import test from 'node:test'
import { parse } from '@vue/compiler-sfc'
import { compile } from '@vue/compiler-dom'
import * as Vue from 'vue'
import { renderToString } from 'vue/server-renderer'
import { matchPermission } from '../src/config/navPlan.js'
import { academicIdentity } from '../src/modules/academicAffairs/academicFlowContext.js'
import { academicStatusLabel } from '../src/modules/academicAffairs/constants/academic-display.constants.js'
import { formatDateTime } from '../src/utils/dateUtils.js'

function workspace(api, permissions = ['*']) {
  const source = readFileSync(new URL('../src/modules/academicAffairs/components/AaStatsSnapshotWorkspace.vue', import.meta.url), 'utf8')
  const script = source.match(/<script>([\s\S]*?)<\/script>/)[1]
    .replace(/^import\s+([\s\S]*?)\s+from\s+['"][^'"]+['"]\s*$/gm, (_, binding) => `const ${binding} = dependencies${binding.startsWith('{') ? '' : '.' + binding}`)
    .replace('export default', 'component =')
  const claims = { tenantId: 'test-school', userId: 'test-user', currentRoleCode: 'ACADEMIC_ADMIN' }
  const sandbox = { dependencies: { academicStatsSnapshotApi: api, academicIdentity, academicStatusLabel, formatDateTime, currentUserFromToken: () => claims, matchPermission, getPermissionPatterns: () => permissions, toast: { success() {} } } }
  vm.runInNewContext(script, sandbox)
  const component = sandbox.component
  const state = { contextFilters: {}, ctx: {}, _component: component, _claims: claims }
  Object.assign(state, component.data.call(state), component.methods)
  for (const [key, getter] of Object.entries(component.computed)) Object.defineProperty(state, key, { get: () => getter.call(state) })
  return state
}

function renderedComponent(relativePath, dependencies = {}) {
  const source = readFileSync(new URL(relativePath, import.meta.url), 'utf8')
  const descriptor = parse(source).descriptor
  const script = descriptor.script.content
    .replace(/^import\s+([\s\S]*?)\s+from\s+['"][^'"]+['"]\s*$/gm, (_, binding) => `const ${binding} = dependencies${binding.startsWith('{') ? '' : '.' + binding}`)
    .replace('export default', 'component =')
  const sandbox = { dependencies }
  vm.runInNewContext(script, sandbox)
  return { ...sandbox.component, render: new Function('Vue', compile(descriptor.template.content, { mode: 'function', prefixIdentifiers: true }).code)(Vue) }
}

async function renderWorkspace(state) {
  const empty = { render: () => null }
  const DataTable = renderedComponent('../src/components/business/DataTable.vue', { AppPagination: empty })
  const AppSectionCard = renderedComponent('../src/components/common/layout/AppSectionCard.vue', { AppHelpTooltip: empty })
  const source = readFileSync(new URL('../src/modules/academicAffairs/components/AaStatsSnapshotWorkspace.vue', import.meta.url), 'utf8')
  const render = new Function('Vue', compile(parse(source).descriptor.template.content, { mode: 'function', prefixIdentifiers: true }).code)(Vue)
  const data = Object.fromEntries(Object.entries(state).filter(([key, value]) => !key.startsWith('_') && !['ctx', 'contextFilters'].includes(key) && typeof value !== 'function'))
  return renderToString(Vue.createSSRApp({
    ...state._component, created: undefined, beforeUnmount: undefined, watch: undefined,
    data: () => data, render,
    components: {
      DataTable, AppSectionCard, AppDrawer: empty, AppConfirmDialog: empty,
      AppTermEntityPicker: empty, AppCollegePicker: empty, AppMajorPicker: empty,
      AppButton: { props: ['disabled'], setup: (props, { slots }) => () => Vue.h('button', { disabled: props.disabled }, slots.default?.()) },
      StatusTag: { props: ['label'], setup: props => () => Vue.h('span', props.label) },
      EmptyState: { props: ['title', 'description'], setup: props => () => Vue.h('p', `${props.title} ${props.description || ''}`) },
      ErrorState: { props: ['title', 'description'], setup: props => () => Vue.h('p', `${props.title} ${props.description || ''}`) },
      AppInlineAlert: { props: ['description'], setup: props => () => Vue.h('p', props.description) },
      LoadingState: { render: () => Vue.h('p', '读取中') }
    }
  }, { ctx: state.ctx, contextFilters: state.contextFilters }))
}

test('snapshot list consumes the shared client unwrapped response, including empty schools', async () => {
  const state = workspace({ list: async () => ({ list: [], total: 0 }) })
  await state.load()
  assert.equal(state.error, '')
  assert.equal(state.loadedOnce, true)
  assert.equal(state.pagination.total, 0)
  state.rows = [{ snapshotId: 'previous' }]
  await state.load()
  assert.equal(state.rows.length, 0)
})

test('snapshot failures remain errors and clear stale rows', async () => {
  const state = workspace({ list: async () => { throw new Error('无权查看该范围') } })
  state.rows = [{ snapshotId: 'previous' }]
  await state.load()
  assert.equal(state.error, '无权查看该范围')
  assert.equal(state.rows.length, 0)
  assert.equal(state.loading, false)
})

test('snapshot creation opens the returned immutable object and uses server verification', async () => {
  const snapshot = { snapshotId: '9007199254740993123', immutable: true, payload: { count: 2 }, payloadHash: 'server-hash' }
  let openedId, verifiedId
  const state = workspace({
    create: async () => snapshot,
    list: async () => ({ list: [snapshot], total: 1 }),
    detail: async id => { openedId = id; return snapshot },
    verify: async id => { verifiedId = id; return { integrityValid: true, immutable: true } }
  })
  state.createForm.reason = '学期统计留档验收'
  state.confirmCreate()
  await state.submitCreate()
  assert.equal(state.createError, '')
  assert.equal(openedId, snapshot.snapshotId)
  assert.equal(state.detail.payloadHash, 'server-hash')
  assert.equal(state.saving, false)
  await state.verifyDetail()
  assert.equal(verifiedId, snapshot.snapshotId)
  assert.equal(state.verified[snapshot.snapshotId], true)
  assert.equal(state.detailError, '')
})

test('confirmation freezes the shown scope even when the underlying form changes', async () => {
  let sent
  const snapshot = { snapshotId: '901', immutable: true }
  const state = workspace({ create: async body => { sent = body; return snapshot }, list: async () => ({ list: [], total: 0 }), detail: async () => snapshot })
  state.createForm = { snapshotType: 'OVERVIEW', termId: '9007199254740993123', collegeId: 'college-a', majorId: '', reason: '核对学期末的正式统计' }
  state.confirmCreate()
  assert.ok(state.confirmationMessage.includes('9007199254740993123'))
  state.createForm.termId = 'other-term'
  state.createForm.reason = '不同原因'
  await state.submitCreate()
  assert.equal(sent.termId, '9007199254740993123')
  assert.equal(sent.reason, '核对学期末的正式统计')
})

test('an unconfirmed or changed-identity command cannot create a snapshot', async () => {
  let writes = 0
  const state = workspace({ create: async () => { writes++ } })
  state.createForm.reason = '本学期统计留档'
  await state.submitCreate()
  assert.equal(writes, 0)
  state.confirmCreate()
  state._claims.userId = 'another-user'
  await state.submitCreate()
  assert.equal(writes, 0)
  assert.match(state.createError, /身份或权限已变化/)
})

test('a failed detail keeps its exact ID available for retry', async () => {
  const ids = []
  const state = workspace({ detail: async id => { ids.push(id); throw new Error('网络中断') } })
  await state.openDetail({ snapshotId: '9007199254740993123' })
  state.reloadDetail()
  await new Promise((resolve) => setTimeout(resolve, 0))
  assert.deepEqual(ids, ['9007199254740993123', '9007199254740993123'])
})

test('late detail responses cannot overwrite a new object or a closed drawer', async () => {
  const pending = []
  const state = workspace({ detail: id => new Promise(resolve => pending.push({ id, resolve })) })
  const first = state.openDetail({ snapshotId: 'a' }), second = state.openDetail({ snapshotId: 'b' })
  pending[1].resolve({ snapshotId: 'b' }); await second
  pending[0].resolve({ snapshotId: 'a' }); await first
  assert.equal(state.detail.snapshotId, 'b')
  const third = state.openDetail({ snapshotId: 'c' })
  state.closeDetail()
  pending[2].resolve({ snapshotId: 'c' }); await third
  assert.equal(state.detail, null)
  assert.equal(state.detailVisible, false)
})

test('a mismatched detail and late verification never certify another snapshot', async () => {
  let finish
  const state = workspace({ detail: async () => ({ snapshotId: 'other' }), verify: () => new Promise(resolve => { finish = resolve }) })
  await state.openDetail({ snapshotId: 'selected' })
  assert.equal(state.verified.selected, false)
  state.detail = { snapshotId: 'a' }
  const pending = state.verifyDetail()
  state.closeDetail()
  state.detail = { snapshotId: 'b' }
  finish({ integrityValid: true, immutable: true }); await pending
  assert.equal(state.verified.b, undefined)
  assert.equal(state.verified.a, undefined)
})

test('a newer list request wins and malformed paging is an error, not an empty school', async () => {
  const pending = []
  const state = workspace({ list: () => new Promise(resolve => pending.push(resolve)) })
  const first = state.load(), second = state.load()
  pending[1]({ list: [{ snapshotId: 'new' }], total: 1 }); await second
  pending[0]({ list: [{ snapshotId: 'old' }], total: 1 }); await first
  assert.equal(state.rows[0].snapshotId, 'new')
  const third = state.load()
  pending[2]({}); await third
  assert.match(state.error, /回执不完整/)
})

test('a negative integrity result is never reported as verified', async () => {
  const state = workspace({ verify: async () => ({ integrityValid: false, immutable: true }) })
  state.detail = { snapshotId: '1' }
  await state.verifyDetail()
  assert.equal(state.verified['1'], false)
  assert.ok(state.detailError)
  assert.equal(state.verifying, false)
})

test('snapshot workspace puts the selected object beside the table and folds implementation fields', async () => {
  const row = { snapshotId: '9007199254740993123', snapshotType: 'OVERVIEW', termId: '51', status: 'FROZEN', generatedBy: 'seed-operator', payloadHash: 'full-hash', payload: { amount: 7 } }
  const state = workspace({ detail: async () => row })
  state.rows = [row, { ...row, snapshotId: 'another' }]
  state.loadedOnce = true
  state.pagination.total = 2
  await state.openDetail(row)
  const html = await renderWorkspace(state)
  assert.match(html, /<aside[^>]+aria-label="快照详情"/)
  assert.match(html, /class="dt__tr assw-selected"/)
  const table = html.match(/<table[\s\S]*?<\/table>/)[0]
  assert.doesNotMatch(table, /9007199254740993123|seed-operator|full-hash|payloadHash/)
  assert.match(table, /学期名称待核对/)
  const implementation = html.match(/<section class="app-section-card[\s\S]*?<\/section>/)[0]
  assert.match(implementation, /实施详情（实施人员使用）/)
  assert.match(implementation, /aria-expanded="false"/)
  assert.match(implementation, /display:none/)
  assert.match(implementation, /9007199254740993123/)
  assert.match(implementation, /seed-operator/)
  assert.match(implementation, /full-hash/)
  assert.equal(state.snapshotRowClass(state.rows[1]), '')
  state.closeDetail()
  assert.equal(state.snapshotRowClass(row), '')
  assert.doesNotMatch(await renderWorkspace(state), /<aside/)
})

test('changing snapshot list filters closes the old detail and invalidates its late response', async () => {
  let finishDetail
  const state = workspace({ detail: () => new Promise(resolve => { finishDetail = resolve }), list: async () => ({ list: [], total: 0 }) })
  const pending = state.openDetail({ snapshotId: 'old-object' })
  state.listFilters.termId = 'new-term'
  await state.load()
  finishDetail({ snapshotId: 'old-object' })
  await pending
  assert.equal(state.detailVisible, false)
  assert.equal(state.detail, null)
  assert.equal(state.selectedSnapshotId, '')
  assert.equal(state.verified['old-object'], undefined)
})

test('snapshot display uses supplied names without guessing unavailable names or losing exact confirmation scope', () => {
  const state = workspace({})
  assert.equal(state.snapshotTypeLabel('FUTURE_SNAPSHOT_TYPE'), '类型待核对')
  const scoped = { termId: '9007199254740993123', collegeId: '12', majorId: '34' }
  assert.equal(state.scopeName(scoped), '指定学院（名称待核对）')
  assert.equal(state.filterName(scoped), '学期名称待核对 · 专业名称待核对')
  assert.equal(state.scopeName({ ...scoped, collegeName: '信息学院' }), '信息学院')
  assert.equal(state.filterName({ ...scoped, termName: '2026秋', majorName: '软件技术' }), '2026秋 · 软件技术')
  state.createForm = { ...scoped, snapshotType: 'OVERVIEW', reason: '学期末统计留档' }
  state.confirmCreate()
  assert.match(state.confirmationMessage, /9007199254740993123/)
  assert.equal(state.confirmedCreate.body.majorId, '34')
})

test('read-only snapshot access keeps details while hiding freeze and verification commands', async () => {
  let writes = 0
  const row = { snapshotId: '1', snapshotType: 'OVERVIEW', status: 'FROZEN' }
  const state = workspace({ detail: async () => row, verify: async () => { writes++ }, create: async () => { writes++ } }, ['academicAffairs.stats.snapshot.view'])
  state.rows = [row]
  await state.openDetail(row)
  const html = await renderWorkspace(state)
  assert.match(html, /快照详情/)
  assert.doesNotMatch(html, /冻结当前统计|重新校验完整性/)
  state.openCreate()
  await state.verifyDetail()
  assert.equal(state.createVisible, false)
  assert.equal(writes, 0)
})

test('snapshot empty first page hides pagination while an out-of-range page can return', async () => {
  const state = workspace({})
  state.loadedOnce = true
  assert.doesNotMatch(await renderWorkspace(state), /上一页/)
  state.pagination.page = 2
  assert.match(await renderWorkspace(state), /上一页/)
})

test('inline snapshot detail receives focus without a stale selection stealing focus', async () => {
  const state = workspace({ detail: async id => ({ snapshotId: id }) })
  const queued = []
  let focused = 0
  state.$nextTick = callback => queued.push(callback)
  state.$refs = { detailPanel: { focus() { focused++ } } }
  const first = state.openDetail({ snapshotId: 'first' })
  const second = state.openDetail({ snapshotId: 'second' })
  await Promise.all([first, second])
  queued.forEach(callback => callback())
  assert.equal(focused, 1)
  await state.openDetail({ snapshotId: 'third' })
  state.closeDetail()
  queued.at(-1)()
  assert.equal(focused, 1)
})

test('snapshot dates use the shared minute format and never display invalid raw strings', () => {
  const state = workspace({})
  assert.equal(state.formatTime('2026-07-20T10:05:59'), '2026-07-20 10:05')
  assert.equal(state.formatTime('2026-07-20T02:05:00Z'), formatDateTime('2026-07-20T02:05:00Z'))
  for (const empty of [null, undefined, '', '   ']) assert.equal(state.formatTime(empty), '—')
  assert.equal(state.formatTime('not-a-date'), '时间待核对')
})
