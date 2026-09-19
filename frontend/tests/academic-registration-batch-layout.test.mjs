import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import test from 'node:test'
import { compile, createSSRApp, h } from 'vue'
import { renderToString } from '@vue/server-renderer'
import { matchPermission } from '../src/config/navPlan.js'
import { academicReturnPath } from '../src/modules/academicAffairs/academicFlowContext.js'

const source = readFileSync(new URL('../src/modules/academicAffairs/views/AaRegistrationBatchListView.vue', import.meta.url), 'utf8')
const template = source.match(/<template>([\s\S]*?)<\/template>\s*<script>/)[1]
const id = '9007199254740993001'
const row = (extra = {}) => ({ batchId: id, batchName: '本学年原始批次', registerType: 'ANNUAL', status: 'OPEN', ...extra })
const deferred = () => { let resolve; const promise = new Promise(done => { resolve = done }); return { promise, resolve } }
const context = () => ({ currentRole: { roleName: '教务测试管理员' }, dataScope: { scopeName: '本校' },
  permissionPatterns: ['academicAffairs.registration.view', 'academicAffairs.registration.manage', 'academicAffairs.registration.archive.manage'] })
const wrapper = (props, { slots }) => h('section', [slots.actions?.(), slots.default?.()])
const plain = (props, { slots }) => h('span', slots.default?.())
const components = {
  ModulePageShell: wrapper, AppSectionCard: wrapper, AppInlineAlert: plain, AppStatusTag: plain,
  AppButton: (props, { slots }) => h('button', slots.default?.()),
  AppSelect: () => h('select'), AppConfirmDialog: () => null, AppDateRangePicker: () => null,
  ErrorState: { props: ['description'], render() { return h('p', this.description) } },
  LoadingState: () => h('p', '正在读取'), EmptyState: { props: ['title', 'description'], render() { return h('p', `${this.title} ${this.description}`) } },
  AppStepBar: { props: ['steps'], render() { return h('ol', this.steps.map(step => h('li', step.title))) } },
  DataTable: { props: ['rows', 'columns'], render() {
    return h('table', [h('thead', h('tr', this.columns.map(column => h('th', column.title)))),
      h('tbody', this.rows.map(item => h('tr', this.columns.map(column => h('td',
        this.$slots[`cell-${column.key}`]?.({ row: item }) || String(item[column.key] ?? ''))))))])
  } }
}
function options(api = {}) {
  const sandbox = { dependencies: { ...components, matchPermission, academicAffairsApi: api } }
  vm.runInNewContext(source.match(/<script>([\s\S]*?)<\/script>/)[1]
    .replace(/^import (.*?) from .*$/gm, (_, binding) => `const ${binding} = dependencies${binding.startsWith('{') ? '' : '.' + binding}`)
    .replace('export default', 'component ='), sandbox)
  return sandbox.component
}
function page(api = {}, query = { type: 'ANNUAL' }) {
  const reads = [], writes = [], destinations = []
  const component = options({ getRegistrationBatches: async params => { reads.push(params); return { code: 0, data: { list: [], total: 0 } } },
    closeRegistrationBatch: async value => { writes.push(value); return { code: 503001 } }, ...api })
  const state = { ...component.data(), ...component.methods, ctx: context(), $route: { path: '/admin/academic-affairs/registration', query },
    $router: { replace: destination => { destinations.push(destination); state.$route.query = destination.query }, push: destination => destinations.push(destination) } }
  for (const [key, value] of Object.entries(component.computed)) {
    const get = typeof value === 'function' ? value : value.get
    Object.defineProperty(state, key, { get: () => get.call(state), ...(value.set ? { set: next => value.set.call(state, next) } : {}) })
  }
  return { state, component, reads, writes, destinations }
}
async function render(type, rows, extra = {}) {
  const component = options()
  const app = createSSRApp({ ...component, created: undefined, render: compile(template),
    data: () => ({ ...component.data(), loading: false, rows, pagination: { page: 1, pageSize: 20, total: rows.length }, ...extra }) }, { ctx: context() })
  app.config.globalProperties.$route = { query: { type } }
  return renderToString(app)
}

test('AA056/057/058 render their design columns and keep unavailable fields separate from actual batch facts', async () => {
  for (const [type, headings] of [['ENROLL', ['招生年级', '学期', '候选学生']], ['ANNUAL', ['学年', '学生范围', '已注册人数']], ['SEMESTER', ['学期', '学生范围', '已注册人数']]]) {
    const html = await render(type, [row({ registerType: type, year: '2099学年', registeredCount: 987654, studentScope: '虚构全校范围' })])
    for (const title of ['批次名称', ...headings, '状态', '办理入口']) assert.ok(html.includes(`<th>${title}</th>`), title)
    assert.ok(html.includes(id)); assert.ok(html.includes('本学年原始批次')); assert.ok(html.includes('开放中'))
    assert.equal((html.match(/批次列表未提供<\/span>/g) || []).length, 3)
    assert.doesNotMatch(html, /2099学年|987654|虚构全校范围/)
    assert.match(html, /人数未提供不表示 0 人/)
  }
})

test('five workflow stages are reference navigation and never report all batches as completed', async () => {
  const { state } = page()
  assert.deepEqual(Array.from(state.registrationSteps, step => step.title), ['创建批次', '圈定候选', '资格核验', '正式注册', '关闭归档'])
  assert.ok(state.registrationSteps.every(step => step.status === 'wait'))
  const html = await render('ANNUAL', [row()])
  assert.match(html, /办理顺序参考/); assert.match(html, /当前状态以列表中的正式记录为准/)
})

test('local name and exact large-ID search never invents a server keyword query or alters the real total', () => {
  const { state, reads } = page()
  state.rows = [row(), row({ batchId: '42', batchName: '另一个批次' })]; state.pagination.total = 412
  state.filters.keyword = id; state.applyFilters()
  assert.deepEqual(Array.from(state.visibleRows, item => item.batchId), [id]); assert.equal(reads.length, 0)
  assert.equal(state.pagination.total, 412); assert.equal(state.$route.query.keyword, id)
  state.filters.keyword = '另一个'; state.applyFilters(); assert.equal(state.visibleRows[0].batchId, '42')
  state.clearFilters(); assert.equal(state.visibleRows.length, 2)
})

test('zero local matches disclose the page boundary without claiming that the database has no batches', async () => {
  const html = await render('ANNUAL', [row()], { appliedKeyword: '本页找不到' })
  assert.match(html, /其他页尚未搜索/); assert.match(html, /名称 \/ ID 仅检索本页 1 条记录/)
  assert.doesNotMatch(html, /当前页暂无注册批次/)
})

test('status filters use the existing formal parameter and newer status reads supersede earlier responses', async () => {
  const old = deferred(), requests = []
  const { state } = page({ getRegistrationBatches: params => {
    requests.push(params)
    return params.status === 'CLOSED' ? Promise.resolve({ code: 0, data: { list: [row({ status: 'CLOSED' })], total: 1 } }) : old.promise
  } })
  const pending = state.load(); state.filters.status = 'CLOSED'; state.applyFilters()
  await Promise.resolve(); old.resolve({ code: 0, data: { list: [row({ status: 'OPEN' })], total: 7 } }); await pending
  assert.equal(requests.length, 2); assert.equal(requests[1].status, 'CLOSED'); assert.equal(requests[1].registerType, 'ANNUAL')
  assert.equal(requests[1].keyword, undefined); assert.equal(state.rows[0].status, 'CLOSED'); assert.equal(state.pagination.total, 1)
})

test('return restoration keeps exact type, status, keyword and server page instead of resetting the queue', () => {
  const query = { type: 'SEMESTER', keyword: '精确批次', status: 'OPEN', page: '3', pageSize: '50' }
  const { state, destinations } = page({}, query)
  state.restoreListQuery(); assert.equal(state.appliedKeyword, '精确批次'); assert.equal(state.appliedStatus, 'OPEN')
  assert.equal(state.pagination.page, 3); assert.equal(state.pagination.pageSize, 50)
  state.academicFlow = { captureReturn: () => academicReturnPath(state.$route) }
  state.goDetail(row())
  assert.equal(destinations[0].path, `/admin/academic-affairs/registration/${id}`)
  assert.ok(destinations[0].query.returnToken.includes('page=3')); assert.ok(destinations[0].query.returnToken.includes('pageSize=50'))
  assert.ok(destinations[0].query.returnToken.includes('status=OPEN')); assert.ok(destinations[0].query.returnToken.includes('keyword='))
})

test('filter changes cancel only unsent confirmation and cannot clear an unknown close lock', async () => {
  const { state, writes } = page()
  state.askClose(row()); state.filters.keyword = '其他'; state.applyFilters()
  assert.equal(state.confirm.visible, false); assert.equal(state.pendingAction, null)
  state.askClose(row()); await state.onConfirm(); assert.ok(state.batchWrite.pending)
  state.clearFilters(); await state.onConfirm()
  assert.equal(writes.length, 1); assert.ok(state.batchWrite.pending); assert.equal(state.batchActionsBlocked, true)
})

test('formal states stay distinct and archive wording does not promise that all linked records are read-only', () => {
  const { state } = page()
  assert.deepEqual(['DRAFT', 'OPEN', 'CLOSED', 'ARCHIVED', 'UNKNOWN'].map(value => state.statusLabel(value)), ['草稿', '开放中', '已关闭', '已归档', '状态待确认'])
  state.askArchive(row({ status: 'CLOSED' }))
  assert.match(state.confirm.message, /暂缓与异常记录尚未统一封存/)
  assert.doesNotMatch(state.confirm.message, /归档后台账只读/)
})

test('failed and malformed list receipts clear old records and show failure instead of an empty success', async () => {
  for (const reply of [async () => ({ code: 403001, message: '当前无权查看' }), async () => ({ code: 0, data: { list: null, total: 0 } }), async () => { throw new Error('timeout') }]) {
    const { state } = page({ getRegistrationBatches: reply }); state.rows = [row()]
    await state.load(); assert.equal(state.rows.length, 0); assert.ok(state.error); assert.equal(state.loading, false)
  }
})
