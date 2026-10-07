import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { compile } from '@vue/compiler-dom'
import * as Vue from 'vue'
import { renderToString } from 'vue/server-renderer'
import { matchPermission } from '../src/config/navPlan.js'
import { page, deferred } from './academic-pc-parallel-b-harness.mjs'
import * as registry from '../src/modules/academicAffairs/config/academicFlowRegistry.js'
import { gradeError } from '../src/modules/academicAffairs/views/parallel-c/grade-review.js'
import { safeBusinessMessage, safeEnumLabel } from '../src/utils/presentationSafety.js'
import { readAllPages } from '../src/modules/academicAffairs/components/parallel-a/pagedRead.js'

const domainNames = ['STUDENT_STATUS', 'REGISTRATION', 'STATUS_CHANGE', 'PROGRAM', 'TEACHING_TASK', 'SCHEDULE', 'SELECTION', 'EXAM', 'GRADE', 'MAKEUP', 'EVALUATION', 'TEXTBOOK', 'GRADUATION']
const ctx = { currentRole: {}, dataScope: {}, permissionPatterns: ['academicAffairs.archive.manage'] }
const slot = { setup: (_, { slots }) => () => Vue.h('section', [slots.actions?.(), slots.default?.()]) }
const components = {
  ModulePageShell: slot, AppFormItem: slot,
  AppButton: { setup: (_, { slots }) => () => Vue.h('button', slots.default?.()) },
  StatusTag: { props: ['label'], setup: props => () => Vue.h('span', props.label) },
  AppInlineAlert: { props: ['description'], setup: props => () => Vue.h('p', props.description) },
  EmptyState: { props: ['title', 'description'], setup: props => () => Vue.h('p', `${props.title} ${props.description}`) },
  LoadingState: { render: () => Vue.h('p', '读取中') }, ErrorState: { props: ['description'], setup: props => () => Vue.h('p', props.description) },
  AppTermEntityPicker: { render: () => Vue.h('input') }, AppTextInput: { render: () => Vue.h('input') }, AppTextarea: { render: () => Vue.h('textarea') }, AppDrawer: { render: () => null }, AppConfirmDialog: { render: () => null },
  AaArchiveCorrectionWorkspace: { render: () => Vue.h('p', '学校封存纠错工作区') },
  DataTable: { props: ['rows'], setup: props => () => Vue.h('p', props.rows.map(row => row.remark).join('；')) }
}
const deps = { ...components, ...registry, gradeError, safeBusinessMessage, safeEnumLabel, matchPermission }
const archiveDeps = api => ({ ...deps, readAllPages, academicAffairsArchiveApi: api })
const batch = (overrides = {}) => ({ batchId: '9007199254740993', termId: '52', termCode: '2026-2027-1', batchName: '秋季学期归档', status: 'READY', scopeType: 'COLLEGE', scopeNote: '学校封存材料由校教务统筹；请查看本院实时预检', missingCount: null, items: [], ...overrides })
const precheck = (termId, overrides = {}) => ({ code: 0, data: { termId, termCode: `学期${termId}`, scopeType: 'COLLEGE', scopeNote: '仅核验本院学生及开课业务明细', result: 'PASS', blockingCount: 0, blockedDomains: 0, domains: domainNames.map(domain => ({ domain, domainLabel: '业务域', result: 'PASS', blockingCount: 0, recordCount: 1 })), ...overrides } })

async function renderPage(name, data, props = {}, overrides = {}) {
  const { definition } = page(name, { ...deps, ...overrides }, { ctx, ...props })
  const source = readFileSync(new URL(`../src/modules/academicAffairs/views/${name}.vue`, import.meta.url), 'utf8')
  definition.created = () => {}
  const originalData = definition.data
  definition.data = function () { return { ...originalData.call(this), ...data } }
  definition.render = new Function('Vue', compile(source.match(/<template>([\s\S]*?)<\/template>\s*<script>/)[1], { mode: 'function', prefixIdentifiers: true }).code)(Vue)
  const app = Vue.createSSRApp(definition, { ctx, ...props })
  app.config.globalProperties.$route = { query: {}, params: {} }
  return renderToString(app)
}

test('学院批次只显示学校进度与本院预检入口，空明细和空计数不冒充检查通过', async () => {
  const current = batch()
  const html = await renderPage('AaArchiveConsoleView', { loading: false, rows: [current], current })
  assert.match(html, /秋季学期归档/)
  assert.match(html, /完整可归档/)
  assert.match(html, /学校封存材料由校教务统筹/)
  assert.match(html, /查看本院实时预检/)
  assert.doesNotMatch(html, />新建归档批次<|>完整性检查<|>确认归档<|>取消<|阻断数据域 0|无阻断，可按状态继续|未检查|等待检查|学校封存纠错工作区/)
})

test('真实上下文仅有 dataScope.scope 时，无批次的学院仍展示学院责任范围', async () => {
  const props = { ctx: { currentRole: {}, dataScope: { scope: 'COLLEGE' } } }
  for (const name of ['AaArchiveConsoleView', 'ArchiveExportView', 'ArchivePrecheckView']) {
    const { state } = page(name, deps, props)
    assert.equal(state.isCollegeScope, true)
  }
  const consoleHtml = await renderPage('AaArchiveConsoleView', { loading: false, rows: [] }, props)
  assert.match(consoleHtml, /学校归档批次由校教务统筹建立/)
  assert.doesNotMatch(consoleHtml, />新建归档批次</)
  const exportHtml = await renderPage('ArchiveExportView', { loading: false, rows: [] }, props)
  assert.match(exportHtml, /查看本院实时预检/)
  assert.doesNotMatch(exportHtml, /正式检查已完成/)
})

test('只读校级身份的空批次说明交给校教务，有办理权限的学校身份仍可新建', async () => {
  const props = { ctx: { currentRole: { roleCode: 'LEADER' }, dataScope: { scope: 'SCHOOL' }, permissionPatterns: ['academicAffairs.archive.read'] } }
  const html = await renderPage('AaArchiveConsoleView', { loading: false, rows: [] }, props)
  assert.match(html, /等待校教务建立归档批次/)
  assert.match(html, /批次建立后，可在此查阅学校归档进度/)
  assert.doesNotMatch(html, /按学期新建归档批次|执行完整性检查与归档|>新建归档批次</)
  const { state } = page('AaArchiveConsoleView', deps, props)
  assert.equal(state.pageSubtitle, '查阅学校归档进度；建立批次、处理缺项和正式封存由校教务负责')
  const existing = await renderPage('AaArchiveConsoleView', { loading: false, rows: [batch({ scopeType: 'TENANT_ALL' })], current: null }, props)
  assert.match(existing, /从左侧选择批次查看学校归档进度；正式检查与封存由校教务负责/)
  assert.doesNotMatch(existing, /执行完整性检查与归档|>新建归档批次</)
  const writer = await renderPage('AaArchiveConsoleView', { loading: false, rows: [] })
  assert.match(writer, />新建归档批次</)
  assert.match(writer, /按学期新建归档批次/)
})

test('学院已封存批次保留真实封存时间，不能渲染学校材料或纠错工作区', async () => {
  const current = batch({ status: 'ARCHIVED', archivedAt: '2026-09-27T09:00:00' })
  const html = await renderPage('AaArchiveConsoleView', { loading: false, rows: [current], current, items: [{ remark: '另一学院封存明细' }] })
  assert.match(html, /已归档/)
  assert.match(html, /2026-09-27 09:00/)
  assert.doesNotMatch(html, /另一学院封存明细|学校封存纠错工作区|无当前办理阻断|阻断数据域 0/)
})

test('终态未返回责任时按正式封存或取消事实展示，不误报需配置任职', async () => {
  for (const scopeType of ['COLLEGE', 'TENANT_ALL']) {
    for (const [name, nextKey] of [['AaArchiveConsoleView', 'nextRole'], ['ArchiveExportView', 'nextOwner']]) {
      const { state } = page(name, deps, { ctx })
      for (const [status, owner, next] of [
        ['ARCHIVED', '学校已完成封存', '后续查阅或纠错由校教务统筹'],
        ['CANCELLED', '批次已取消', '无需继续办理此批次']
      ]) {
        state.current = batch({ status, scopeType, responsibility: null, nextStep: null })
        assert.equal(state.archiveOwner, owner)
        assert.equal(state[nextKey], next)
        // 导出页正式列表只接收已归档批次；取消态在归档控制台显示。
        if (name === 'ArchiveExportView' && status === 'CANCELLED') continue
        const html = await renderPage(name, { loading: false, rows: [state.current], current: state.current })
        assert.ok(html.includes(owner)); assert.ok(html.includes(next))
        assert.doesNotMatch(html, /责任组织待明确|具体责任人待配置|责任尚未配置|下一责任事项待明确/)
      }
    }
  }
})

test('终态仍优先展示服务端实际责任与下一步，不被状态或学校范围默认文字覆盖', async () => {
  const responsibility = { orgName: '校教务处', assignmentTypes: ['ACADEMIC_REVIEWER'], assigneeNames: ['测试归档责任人'], resolved: true }
  const nextStep = { label: '核对查阅申请', responsibility }
  for (const scopeType of ['COLLEGE', 'TENANT_ALL']) {
    for (const [name, nextKey] of [['AaArchiveConsoleView', 'nextRole'], ['ArchiveExportView', 'nextOwner']]) {
      const { state } = page(name, deps, { ctx })
      for (const status of ['ARCHIVED', 'CANCELLED']) {
        state.current = batch({ status, scopeType, responsibility, nextStep })
        assert.equal(state.archiveOwner, registry.academicFlowOwner(responsibility))
        assert.equal(state[nextKey], registry.academicFlowNextOwner(nextStep))
      }
      state.current.status = 'ARCHIVED'
      const html = await renderPage(name, { loading: false, rows: [state.current], current: state.current })
      assert.match(html, /测试归档责任人/); assert.match(html, /核对查阅申请/)
      assert.doesNotMatch(html, /学校已完成封存|后续查阅或纠错由校教务统筹/)
    }
  }
})

test('非终态缺失责任或未知状态仍显示待明确，责任与下一步分别使用真实字段', () => {
  for (const [name, nextKey] of [['AaArchiveConsoleView', 'nextRole'], ['ArchiveExportView', 'nextOwner']]) {
    const { state } = page(name, deps, { ctx })
    for (const status of ['DRAFT', 'CHECKING', 'READY', 'MISSING_ITEMS', undefined]) {
      state.current = batch({ status })
      assert.equal(state.archiveOwner, registry.academicFlowOwner())
      assert.equal(state[nextKey], registry.academicFlowNextOwner())
    }
    state.current = batch({ status: 'ARCHIVED', nextStep: { label: '查看学校办理结果' } })
    assert.equal(state.archiveOwner, '学校已完成封存')
    assert.equal(state[nextKey], '查看学校办理结果')
    state.current.responsibility = { orgName: '校教务处', resolved: false, reason: '正式责任仍需核对' }
    state.current.nextStep = null
    assert.match(state.archiveOwner, /正式责任仍需核对/)
    assert.equal(state[nextKey], '后续查阅或纠错由校教务统筹')
  }
})

test('学院范围阻止学校归档动作并携带字符串学期进入原预检页', async () => {
  let requests = 0, destination
  const { state } = page('AaArchiveConsoleView', { ...deps, academicAffairsArchiveApi: new Proxy({}, { get: () => async () => { requests++; throw Error('不应请求') } }) }, { ctx })
  state.current = batch()
  state.form.termId = '52'
  state.$router.push = value => { destination = value }
  state.openCreate(); await state.submitCreate(); await state.doCheck(); state.doConfirm(); state.doCancel()
  await state.runBatchWrite('check', state.current.batchId, () => true, () => { requests++ }, () => true, '错误回执')
  assert.equal(requests, 0)
  assert.equal(state.createVisible, false)
  assert.equal(state.confirmVisible, false)
  await state.goCollegePrecheck()
  assert.equal(destination.name, 'aa-archive-precheck')
  assert.equal(destination.query.termId, '52')
})

test('归档批次列表每页带有效网址学期，新建沿用本学期且无学期保持原查询', async () => {
  const calls = []
  const { state } = page('AaArchiveConsoleView', archiveDeps({
    listBatches: async params => {
      calls.push(params)
      const list = params.page === 1
        ? Array.from({ length: 100 }, (_, index) => batch({ batchId: String(index + 1), scopeType: 'TENANT_ALL' }))
        : [batch({ batchId: '101', scopeType: 'TENANT_ALL' })]
      return { code: 0, data: { list, total: 101 } }
    },
    getBatch: async id => ({ code: 0, data: batch({ batchId: id, scopeType: 'TENANT_ALL' }) })
  }), { ctx })
  state.$route.query = { termId: '52' }
  await state.load()
  assert.equal(calls[0].termId, '52')
  assert.equal(calls[1].termId, '52')
  assert.equal(state.rows.length, 101)
  assert.equal(state.current.termId, '52')
  state.openCreate()
  assert.equal(state.form.termId, '52')
  state.$route.query = {}
  await state.load()
  assert.equal(Object.hasOwn(calls[2], 'termId'), false)
  assert.equal(Object.hasOwn(calls[3], 'termId'), false)
  state.openCreate()
  assert.equal(state.form.termId, '')
})

test('归档非法学期清旧批次且不请求，显式批次深链与当前学期冲突时拒绝显示', async () => {
  let lists = 0, details = 0
  const { state } = page('AaArchiveConsoleView', archiveDeps({
    listBatches: async () => { lists++; return { code: 0, data: { list: [], total: 0 } } },
    getBatch: async () => { details++; return { code: 0, data: batch({ batchId: '12', termId: '51' }) } }
  }), { ctx })
  for (const invalid of ['0', 'abc', ['52'], null]) {
    state.$route.query = { termId: invalid, batchId: '12' }
    state.rows = [batch()]; state.current = batch(); state.items = [{ domain: 'EXAM' }]
    state.syncRoute()
    assert.equal(state.rows.length, 0)
    assert.equal(state.current, null)
    assert.equal(state.items.length, 0)
    assert.match(state.listError, /学期参数无效/)
  }
  assert.equal(lists, 0)
  assert.equal(details, 0)
  state.$route.query = { termId: '52', batchId: '12' }
  await state.selectAfterAction({ batchId: '12' })
  assert.equal(details, 1)
  assert.equal(state.current, null)
  assert.match(state.listError, /不属于当前学期/)
})

test('归档学期切换后迟到列表不能覆盖新学期，也不自动选其他学期批次', async () => {
  const old = deferred(), next = deferred(); const calls = []
  const { state } = page('AaArchiveConsoleView', archiveDeps({
    listBatches: params => { calls.push(params.termId); return params.termId === '51' ? old.promise : next.promise },
    getBatch: async batchId => ({ code: 0, data: batch({ batchId, termId: '52' }) })
  }), { ctx })
  state.$route.query = { termId: '51' }; state.$route.fullPath = '/admin/academic-affairs/archive?termId=51'
  const oldLoad = state.load()
  state.current = batch({ batchId: '12', termId: '51' }); state.createVisible = true
  state.$route.query = { termId: '52' }; state.$route.fullPath = '/admin/academic-affairs/archive?termId=52'
  state.syncRoute()
  assert.equal(state.current, null)
  assert.equal(state.createVisible, false)
  next.resolve({ code: 0, data: { list: [batch({ batchId: '14', termId: '52' })], total: 1 } })
  for (let i = 0; i < 5; i++) await Promise.resolve()
  old.resolve({ code: 0, data: { list: [batch({ batchId: '12', termId: '51' })], total: 1 } })
  await oldLoad
  assert.equal(calls.join(','), '51,52')
  assert.equal(state.rows[0].batchId, '14')
  assert.equal(state.current.batchId, '14')
})

test('未知批次写入切学期后只读核对返回原学期原批次，保持禁止重发', async () => {
  let writes = 0, destination
  const { state } = page('AaArchiveConsoleView', archiveDeps({
    listBatches: async () => ({ code: 0, data: { list: [], total: 0 } }),
    getBatch: async () => ({ code: 0, data: batch({ batchId: '12', termId: '51', scopeType: 'TENANT_ALL' }) })
  }), { ctx })
  state.$route.query = { termId: '51', batchId: '12' }
  state.$route.fullPath = '/admin/academic-affairs/archive?termId=51&batchId=12'
  state.current = batch({ batchId: '12', termId: '51', scopeType: 'TENANT_ALL' })
  await state.runBatchWrite('check', '12', () => true, async () => { writes++; return { code: 0, data: { batchId: '12' } } }, () => false, '已完成')
  assert.equal(state.pendingCommand.termId, '51')
  assert.equal(state.pendingCommand.sent, true)
  state.$route.query = { termId: '52', batchId: '12' }
  state.$route.fullPath = '/admin/academic-affairs/archive?termId=52&batchId=12'
  state.syncRoute()
  state.$router.push = value => { destination = value }
  await state.readPendingOriginal()
  assert.equal(destination.name, 'aa-archive')
  assert.equal(destination.query.termId, '51')
  assert.equal(destination.query.batchId, '12')
  assert.equal(writes, 1)
  assert.equal(state.pendingCommand.sent, true)
  state.$route.query = destination.query
  state.$route.fullPath = '/admin/academic-affairs/archive?termId=51&batchId=12'
  state.syncRoute()
  await state.readPendingOriginal()
  assert.equal(state.current.batchId, '12')
  assert.equal(writes, 1)
  assert.equal(state.pendingCommand.sent, true)
})

test('未知新建回执切学期后只读返回原学期列表，不重发创建', async () => {
  let creates = 0, destination
  const { state } = page('AaArchiveConsoleView', archiveDeps({
    listBatches: async () => ({ code: 0, data: { list: [], total: 0 } }),
    createBatch: async () => { creates++; return { code: 503 } }
  }), { ctx })
  state.$route.query = { termId: '51' }
  state.$route.fullPath = '/admin/academic-affairs/archive?termId=51'
  state.form.termId = '51'
  await state.submitCreate()
  assert.equal(state.pendingCommand.termId, '51')
  state.$route.query = { termId: '52', batchId: '14' }
  state.$route.fullPath = '/admin/academic-affairs/archive?termId=52&batchId=14'
  state.syncRoute()
  state.$router.push = value => { destination = value }
  await state.readPendingOriginal()
  assert.equal(destination.query.termId, '51')
  assert.equal(Object.hasOwn(destination.query, 'batchId'), false)
  assert.equal(creates, 1)
  assert.equal(state.pendingCommand.sent, true)
})

test('学校缺失计数为空时显示待核对，正式零计数保持真实含义', () => {
  const { state } = page('AaArchiveConsoleView', deps, { ctx })
  state.current = batch({ scopeType: 'TENANT_ALL', status: 'ARCHIVED', missingCount: null })
  assert.equal(state.blockerText, '阻断数量待核对')
  assert.equal(state.batchMissingLabel(state.current), '阻断数量待核对')
  state.current = batch({ scopeType: 'TENANT_ALL', missingCount: 0 })
  state.items = precheck('52').data.domains
  assert.equal(state.blockerText, '无阻断，可按状态继续')
  assert.equal(state.batchMissingLabel(state.current), '阻断数据域 0')
  state.current.missingCount = 3
  assert.equal(state.blockerText, '3 个数据域阻断')
})

function precheckPage(api, props = {}) {
  return page('ArchivePrecheckView', { ...deps, academicAffairsArchiveApi: api }, { ctx, $nextTick: callback => queueMicrotask(callback), ...props })
}

test('归档预检深链读取指定学期，服务端返回其他学期时拒绝展示', async () => {
  const calls = []
  const { state } = precheckPage({ precheck: async id => { calls.push(id); return precheck(id) } })
  state.$route.query.termId = '9007199254740993'
  await state.syncRoute()
  assert.deepEqual(calls, ['9007199254740993'])
  assert.equal(state.termId, '9007199254740993')
  assert.equal(state.domains.length, 13)
  assert.equal(state.isCollegeScope, true)
  const mismatch = precheckPage({ precheck: async () => precheck('53') }).state
  mismatch.$route.query.termId = '52'
  await mismatch.syncRoute()
  assert.match(mismatch.error, /预检失败/)
  assert.equal(mismatch.domains.length, 0)
  assert.equal(mismatch.precheckDecision, '尚未取得有效结论')
})

test('归档预检去处理和归档批次入口保留当前正式学期与已有查询上下文', () => {
  const { state } = precheckPage({})
  const destinations = []
  state.$router.push = value => { destinations.push(value) }
  state.$router.resolve = value => {
    const [path, search = ''] = value.split('?')
    return { path, query: Object.fromEntries(new URLSearchParams(search)) }
  }
  state.$route.query = { termId: '52', source: 'flow', batchId: '9007199254740993' }
  state.termId = '53'
  state.jump({ domain: 'EXAM', route: '/admin/academic-affairs/exam' })
  state.goBatch()
  assert.deepEqual(JSON.parse(JSON.stringify(destinations)), [
    { path: '/admin/academic-affairs/exam', query: { termId: '53' } },
    { path: '/admin/academic-affairs/archive', query: { termId: '53' } }
  ])
  state.$route.query = { source: 'workspace' }
  state.termId = '9007199254740995'
  state.jump({ domain: 'GRADUATION' })
  assert.deepEqual(JSON.parse(JSON.stringify(destinations[2])), {
    path: '/admin/academic-affairs/graduation/audit-console',
    query: { termId: '9007199254740995' }
  })
  state.$route.query = { termId: '53', batchId: '9007199254740993' }
  state.termId = '53'
  state.goBatch()
  assert.deepEqual(JSON.parse(JSON.stringify(destinations[3])), {
    path: '/admin/academic-affairs/archive',
    query: { termId: '53', batchId: '9007199254740993' }
  })
  state.jump({ domain: 'EXAM', route: '/admin/academic-affairs/exam?tab=archive&termId=54' })
  assert.deepEqual(JSON.parse(JSON.stringify(destinations[4])), {
    path: '/admin/academic-affairs/exam',
    query: { termId: '54', tab: 'archive' }
  })
})

for (const oldOutcome of ['success', 'error']) test(`换学期清除旧结论，旧请求 ${oldOutcome} 最后返回不覆盖新学期`, async () => {
  const old = deferred(), next = deferred()
  const { state } = precheckPage({ precheck: id => id === '52' ? old.promise : next.promise })
  state.$route.query.termId = '52'
  const first = state.syncRoute()
  state.domains = precheck('52').data.domains
  state.$route.query.termId = '53'
  const second = state.syncRoute()
  assert.equal(state.domains.length, 0)
  assert.equal(state.precheckDecision, '正在读取')
  next.resolve(precheck('53')); await second
  if (oldOutcome === 'success') old.resolve(precheck('52')); else old.reject(Error('旧学期连接失败'))
  await first
  assert.equal(state.termId, '53')
  assert.equal(state.termCode, '学期53')
  assert.equal(state.error, '')
  assert.equal(state.loading, false)
})

test('身份切换与卸载后的迟到预检不得恢复旧范围结果', async () => {
  for (const change of ['identity', 'unmount']) {
    const delayed = deferred()
    const { state, definition } = precheckPage({ precheck: () => delayed.promise })
    state.termId = '52'
    const read = state.load()
    if (change === 'identity') state.ctx = { currentRole: {}, dataScope: { scopeType: 'COLLEGE', collegeId: 'other' } }
    else definition.beforeUnmount.call(state)
    delayed.resolve(precheck('52')); await read
    assert.equal(state.domains.length, 0)
    assert.equal(state.scopeNote, '')
  }
})

test('无效学期深链不发请求，默认学期回填不触发第二次预检', async () => {
  let reads = 0
  const invalid = precheckPage({ precheck: async () => { reads++; return precheck('52') } }).state
  invalid.termId = '52'
  invalid.domains = precheck('52').data.domains
  invalid.$route.query.termId = ['52', '53']
  await invalid.syncRoute()
  assert.equal(reads, 0)
  assert.match(invalid.error, /学期参数无效/)
  await invalid.load()
  assert.equal(reads, 0)
  assert.equal(invalid.domains.length, 0)
  assert.match(invalid.error, /学期参数无效/)
  assert.equal(invalid.precheckDecision, '尚未取得有效结论')
  const callbacks = []
  const { state, definition } = precheckPage({ precheck: async () => { reads++; return precheck('52') } }, { $nextTick: callback => callbacks.push(callback) })
  await state.syncRoute()
  definition.watch.termId.call(state)
  assert.equal(state.termId, '52')
  assert.equal(reads, 1)
  callbacks.forEach(callback => callback())
})

test('学院可处理阻断优先于学校统筹待核验，学校范围仍按实际阻断数量排序', () => {
  const { state } = precheckPage({})
  state.loading = false
  state.scopeType = 'COLLEGE'
  const school = { domain: 'REGISTRATION', domainLabel: '注册', result: 'UNKNOWN', blockingCount: 20, evidence: [{ type: 'COLLEGE_ARCHIVE_SCOPE', schoolCheckPerformed: false, responsibleOrgType: 'SCHOOL' }] }
  const college = { domain: 'GRADE', domainLabel: '成绩', result: 'BLOCKED', blockingCount: 1 }
  state.domains = [school, college]
  assert.equal(state.firstBlockingDomain.domain, 'GRADE')
  assert.match(state.nextActionText, /先处理「成绩」/)
  assert.equal(state.schoolCheckPending(state.firstBlockingDomain), false)
  state.scopeType = 'TENANT_ALL'
  assert.equal(state.firstBlockingDomain.domain, 'REGISTRATION')
})

test('学期选择器同步正式查询参数并清旧结果，保留原查询上下文', async () => {
  let destination, reads = 0
  const { state, definition } = precheckPage({ precheck: async id => { reads++; return precheck(id) } })
  state.$route.query = { termId: '52', source: 'batch' }
  state.termId = '53'
  state.domains = precheck('52').data.domains
  state.$router.replace = value => { destination = value }
  definition.watch.termId.call(state)
  assert.equal(state.domains.length, 0)
  assert.equal(reads, 0)
  assert.equal(destination.query.termId, '53')
  assert.equal(destination.query.source, 'batch')
  state.$route.query = destination.query
  await state.syncRoute()
  assert.equal(reads, 1)
  assert.equal(state.termCode, '学期53')
})

test('学院预检明确本院范围与学校统筹待核验，读取失败不能显示零缺项结论', async () => {
  const data = precheck('52', { result: 'UNKNOWN', blockedDomains: 1 }).data
  data.domains[0] = { ...data.domains[0], result: 'UNKNOWN', summary: '学校统筹项，待学校核验', evidence: [{ type: 'COLLEGE_ARCHIVE_SCOPE', localBlockingCount: 0, schoolCheckPerformed: false, responsibleOrgType: 'SCHOOL' }] }
  const html = await renderPage('ArchivePrecheckView', { loading: false, termId: '52', termCode: data.termCode, scopeType: data.scopeType, scopeNote: data.scopeNote, domains: data.domains, overallResult: data.result, blockedDomains: 1 })
  assert.match(html, /本院预检仍有阻断或待核验事项/)
  assert.match(html, /学校统筹项，待学校核验/)
  assert.match(html, /按各项实际责任核对，学校统筹项交校教务/)
  assert.match(html, />待学校核验</)
  assert.match(html, /等待校教务核验学校统筹项/)
  assert.doesNotMatch(html, /去处理首要阻断/)
  assert.doesNotMatch(html, /可以进入归档批次|UNKNOWN|BLOCKED/)
  const failed = await renderPage('ArchivePrecheckView', { loading: false, error: '预检读取失败', domains: [] })
  assert.match(failed, /尚未取得有效结论/)
  assert.doesNotMatch(failed, /仍有 0 个|当前无阻断或待治理域|可以进入归档批次/)
})

test('学院导出页读取批次后不请求学校日志或导出，也不显示虚构零记录', async () => {
  const current = batch({ status: 'ARCHIVED', archivedAt: '2026-09-27T10:00:00' })
  const calls = []
  const api = {
    getBatch: async id => { calls.push(['detail', id]); return { code: 0, data: current } },
    downloadLog: async () => { calls.push(['log']); return { code: 0, data: [] } },
    exportAll: async () => { calls.push(['export']); return { code: 0 } }
  }
  const { state } = page('ArchiveExportView', { ...deps, academicAffairsArchiveApi: api }, { ctx })
  await state.select(current)
  await state.loadLog()
  state.openExport('GRADE'); state.exportPurpose = '本院归档准备核对'; await state.quickExport(); await state.doExport()
  assert.deepEqual(calls, [['detail', current.batchId]])
  assert.equal(state.current.batchId, current.batchId)
  assert.equal(state.exportVisible, false)
  assert.equal(state.logError, '')
  let destination
  state.$router.push = value => { destination = value }
  await state.goCollegePrecheck()
  assert.equal(destination.query.termId, '52')
  const html = await renderPage('ArchiveExportView', { loading: false, rows: [current], current, items: [], downloadLog: [] })
  assert.match(html, /学校封存材料由校教务统筹/)
  assert.match(html, /查看本院实时预检/)
  assert.match(html, /2026-09-27 10:00/)
  assert.doesNotMatch(html, /申请归档导出|确认下载|物料清单|暂无下载记录|正式记录 0 条|当前岗位拥有归档导出权限/)
})

test('学校导出页继续读取学校日志，学院身份切换拒收旧学校日志', async () => {
  const school = batch({ scopeType: 'TENANT_ALL', status: 'ARCHIVED' })
  let logs = 0
  const { state } = page('ArchiveExportView', { ...deps, academicAffairsArchiveApi: {
    getBatch: async () => ({ code: 0, data: school }),
    downloadLog: async () => { logs++; return { code: 0, data: [{ detail: '正式下载回执' }] } }
  } }, { ctx })
  await state.select(school)
  assert.equal(logs, 1)
  assert.equal(state.downloadLog[0].detail, '正式下载回执')
  state.openExport('GRADE')
  assert.equal(state.exportVisible, true)
  assert.equal(state.pendingCategory, 'GRADE')
  const delayed = deferred()
  const pending = page('ArchiveExportView', { ...deps, academicAffairsArchiveApi: { downloadLog: () => delayed.promise } }, { ctx }).state
  pending.current = school
  const read = pending.loadLog()
  pending.ctx = { currentRole: {}, dataScope: { scopeType: 'COLLEGE' } }; pending.clearPrivate()
  delayed.resolve({ code: 0, data: [{ detail: '旧学校下载明细' }] }); await read
  assert.equal(pending.downloadLog.length, 0)
})

test('导出列表或日志失败显示错误，不能伪装暂无已归档批次或暂无下载记录', async () => {
  const api = { listBatches: async () => ({ code: 503 }), downloadLog: async () => ({ code: 503 }) }
  const { state } = page('ArchiveExportView', { ...deps, academicAffairsArchiveApi: api }, { ctx })
  await state.load()
  assert.match(state.listError, /批次加载失败/)
  const failedList = await renderPage('ArchiveExportView', { loading: false, listError: state.listError })
  assert.match(failedList, /批次加载失败/)
  assert.doesNotMatch(failedList, /暂无已归档批次/)
  state.current = batch({ scopeType: 'TENANT_ALL', status: 'ARCHIVED' })
  await state.loadLog()
  assert.match(state.logError, /下载记录读取失败/)
  const failedLog = await renderPage('ArchiveExportView', { loading: false, current: state.current, logError: state.logError })
  assert.match(failedLog, /下载记录读取失败/)
  assert.doesNotMatch(failedLog, /暂无下载记录/)
})

test('导出详情真实重试按钮重新读取同一批次，身份清除后不恢复旧选择', async () => {
  const current = batch({ status: 'ARCHIVED' }), calls = []
  const api = { getBatch: async id => { calls.push(id); return { code: 0, data: current } } }
  let retry
  await renderPage('ArchiveExportView', { loading: false, detailError: '归档批次加载失败', selectedBatchId: current.batchId }, {}, {
    academicAffairsArchiveApi: api,
    ErrorState: { props: ['description'], setup: (props, { attrs }) => { retry = attrs.onRetry; return () => Vue.h('button', { onClick: retry }, props.description) } }
  })
  assert.equal(typeof retry, 'function')
  await retry()
  assert.deepEqual(calls, [current.batchId])
  const { state } = page('ArchiveExportView', { ...deps, academicAffairsArchiveApi: api }, { ctx })
  state.selectedBatchId = current.batchId
  state.clearPrivate()
  await state.retryDetail()
  assert.deepEqual(calls, [current.batchId])
  const old = deferred(), next = deferred()
  const racing = page('ArchiveExportView', { ...deps, academicAffairsArchiveApi: { getBatch: id => id === '1' ? old.promise : next.promise } }, { ctx }).state
  const first = racing.select({ batchId: '1' }), second = racing.select({ batchId: '2' })
  next.resolve({ code: 0, data: { ...current, batchId: '2' } }); await second
  old.reject(Error('旧批次网络错误')); await first
  assert.equal(racing.selectedBatchId, '2')
  assert.equal(racing.current.batchId, '2')
  assert.equal(racing.detailError, '')
})

test('学校日志权限拒绝清除全部私有材料，同时在主页面保留可见错误', async () => {
  const current = batch({ scopeType: 'TENANT_ALL', status: 'ARCHIVED' })
  const { state } = page('ArchiveExportView', { ...deps, academicAffairsArchiveApi: { downloadLog: async () => ({ code: 403, bizCode: 'NO_PERMISSION' }) } }, { ctx })
  state.current = current; state.rows = [current]; state.items = [{ recordCount: 20 }]; state.selectedBatchId = current.batchId
  await state.loadLog()
  assert.equal(state.current, null)
  assert.equal(state.rows.length, 0)
  assert.equal(state.items.length, 0)
  assert.equal(state.selectedBatchId, '')
  assert.match(state.listError, /无权/)
  const html = await renderPage('ArchiveExportView', { loading: false, current: state.current, rows: state.rows, items: state.items, logError: state.logError, listError: state.listError })
  assert.match(html, /无权/)
  assert.doesNotMatch(html, /暂无已归档批次|暂无下载记录|正式记录 20/)
})


test('学校只读领导保留正式进度且不暴露归档管理入口，范围不代替权限', async () => {
  const current = batch({ scopeType: 'TENANT_ALL', items: [], confirmAction: { allowed: true } })
  const leader = { currentRole: { roleCode: 'SCHOOL_LEADER' }, dataScope: { scope: 'TENANT_ALL' }, permissionPatterns: ['academicAffairs.archive.view'] }
  for (const status of ['READY', 'ARCHIVED']) {
    const html = await renderPage('AaArchiveConsoleView', { loading: false, rows: [current], current: { ...current, status } }, { ctx: leader })
    assert.match(html, /秋季学期归档/)
    assert.doesNotMatch(html, />新建归档批次<|>完整性检查<|>确认归档<|>取消<|学校封存纠错工作区/)
  }
  let calls = 0
  const { state } = page('AaArchiveConsoleView', archiveDeps(new Proxy({}, { get: () => async () => { calls++; throw Error('不应发送') } })), { ctx: leader })
  state.current = current; state.form.termId = '52'
  state.openCreate(); await state.submitCreate(); await state.doCheck(); await state.doConfirm(); state.doCancel()
  await state.runBatchWrite('cancel', current.batchId, () => true, () => { calls++ }, () => true, '')
  state.pendingAction = async () => { calls++ }; await state.onConfirm()
  assert.equal(calls, 0); assert.equal(state.createVisible, false); assert.equal(state.confirmVisible, false)
  assert.equal(state.canConfirmArchive, false)
})

test('归档弹窗及确认闭包在权限收回后停止写入，仍可只读学校进度', async () => {
  let writes = 0, reads = 0
  const management = () => ({ currentRole: {}, dataScope: { scope: 'TENANT_ALL' }, permissionPatterns: ['academicAffairs.archive.manage'] })
  const current = batch({ scopeType: 'TENANT_ALL', items: domainNames.map(domain => ({ domain, result: 'PASS' })), confirmAction: { allowed: true } })
  for (const kind of ['create', 'cancel', 'confirm']) {
    const { state } = page('AaArchiveConsoleView', archiveDeps({
      getBatch: async () => { reads++; return { code: 0, data: current } },
      createBatch: async () => { writes++ }, cancel: async () => { writes++ }, confirm: async () => { writes++ },
    }), { ctx: management() })
    state.current = current; state.form.termId = '52'; state.load = async () => {}
    if (kind === 'create') state.openCreate()
    if (kind === 'cancel') state.doCancel()
    if (kind === 'confirm') await state.doConfirm()
    const closure = state.pendingAction
    state.ctx.permissionPatterns = ['academicAffairs.archive.view']
    if (kind === 'create') await state.submitCreate()
    else { await state.onConfirm(); await closure() }
    assert.equal(writes, 0)
    assert.equal(state.canManageArchive, false)
    await state.refreshCurrentFromServer()
    assert.equal(state.current.batchId, current.batchId)
  }
  assert.ok(reads > 0)
})

test('归档命令异步回读期间撤权，发送前复核阻止检查取消和确认', async () => {
  for (const kind of ['check', 'cancel', 'confirm']) {
    const pending = deferred(); let writes = 0
    const { state } = page('AaArchiveConsoleView', archiveDeps({ getBatch: () => pending.promise }), {
      ctx: { currentRole: {}, dataScope: { scope: 'TENANT_ALL' }, permissionPatterns: ['academicAffairs.archive.manage'] },
    })
    state.current = batch({ scopeType: 'TENANT_ALL', confirmAction: { allowed: true } })
    const command = state.runBatchWrite(kind, state.current.batchId, () => true, () => { writes++ }, () => true, '')
    state.ctx.permissionPatterns = ['academicAffairs.archive.view']
    pending.resolve({ code: 0, data: state.current }); await command
    assert.equal(writes, 0); assert.equal(state.pendingCommand, null)
    assert.match(state.confirmError, /没有教务归档办理权限/)
  }
})
