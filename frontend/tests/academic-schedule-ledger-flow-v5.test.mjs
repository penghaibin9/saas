import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { compile } from '@vue/compiler-dom'
import * as Vue from 'vue'
import { renderToString } from 'vue/server-renderer'
import { page, deferred } from './academic-pc-parallel-b-harness.mjs'
import { matchPermission } from '../src/config/navPlan.js'

const ok = (rows = []) => ({ code: 0, data: { list: rows, total: rows.length } })
function instance(api = {}, roleCode = 'COLLEGE_ADMIN', terms = {}, permissionPatterns = []) {
  return page('AaScheduleChangeLedgerView', { CHANGE_TYPES: [], CHANGE_STATUS: [], matchPermission,
    scheduleChangeApi: { list: async () => ok(), ...api }, academicAffairsApi: { getCurrentTerm: async () => ({ code: 0, data: { termId: '52', termName: '当前秋季学期' } }), ...terms }
  }, { ctx: { currentRole: { roleCode }, dataScope: { scope: roleCode === 'ACADEMIC_TEACHER' ? 'ASSIGNED' : 'COLLEGE' }, permissionPatterns } })
}

test('只读领导台账不展示发起和撤销，点击入口也不能导航', async () => {
  const { state } = instance({}, 'LEADER', {}, ['academicAffairs.scheduleChange.view'])
  const routes = []; state.$router.push = route => routes.push(route)
  assert.equal(state.canApply, false)
  assert.equal(state.cancellable({ status: 'SUBMITTED', canCancel: true }), false)
  state.goApply()
  state.askCancel({ changeId: '15', status: 'SUBMITTED', canCancel: true })
  assert.deepEqual(routes, [])
  assert.equal(state.confirm.visible, false)

  const source = readFileSync(new URL('../src/modules/academicAffairs/views/AaScheduleChangeLedgerView.vue', import.meta.url), 'utf8')
  const actions = source.match(/<div class="sc-actions">[^]*?<\/div>/)[0]
  const render = new Function('Vue', compile(actions, { mode: 'function', prefixIdentifiers: true }).code)(Vue)
  const AppButton = { setup: (_, { slots }) => () => Vue.h('button', slots.default?.()) }
  const html = await renderToString(Vue.createSSRApp({ data: () => ({ canApply: state.canApply, isAcademicTeacher: false, selectedId: '', showHistory: false, canReview: false }), methods: { goApply() {}, toggleHistory() {}, goApproval() {} }, render, components: { AppButton } }))
  assert.doesNotMatch(html, /发起调停课|从个人课表选择课程/)
  const empty = source.match(/<EmptyState v-else-if="!rows.length"[^>]*\/>/)[0].replace('v-else-if', 'v-if')
  const renderEmpty = new Function('Vue', compile(empty, { mode: 'function', prefixIdentifiers: true }).code)(Vue)
  const EmptyState = { props: ['title', 'description'], setup: props => () => Vue.h('p', `${props.title} ${props.description}`) }
  const emptyHtml = await renderToString(Vue.createSSRApp({ data: () => ({ rows: [], canApply: state.canApply }), render: renderEmpty, components: { EmptyState } }))
  assert.doesNotMatch(emptyHtml, /发起调停课|创建/)
})

test('撤销只接受当前权限及服务端严格布尔授权，本人可办而学院他人不可办', async () => {
  let writes = 0
  const teacher = instance({ cancel: async () => { writes++; return ok() } }, 'ACADEMIC_TEACHER', {}, ['academicAffairs.scheduleChange.view', 'academicAffairs.scheduleChange.apply']).state
  assert.equal(teacher.canApply, true)
  for (const canCancel of [undefined, null, 'true', 1, false]) {
    assert.equal(teacher.cancellable({ status: 'SUBMITTED', canCancel }), false)
  }
  assert.equal(teacher.cancellable({ status: 'SUBMITTED', canCancel: true }), true)
  assert.equal(teacher.cancellable({ status: 'APPLIED', canCancel: true }), false)
  const own = { changeId: '15', status: 'SUBMITTED', canCancel: true }
  teacher.askCancel(own)
  assert.equal(teacher.confirm.visible, true)
  await teacher.onConfirm({ reason: '本人撤销申请' })
  assert.equal(writes, 1)
  const college = instance({}, 'COLLEGE_ADMIN', {}, ['academicAffairs.scheduleChange.view', 'academicAffairs.scheduleChange.apply']).state
  assert.equal(college.cancellable({ status: 'COLLEGE_REVIEW', canCancel: false }), false)
  college.askCancel({ changeId: '15', status: 'COLLEGE_REVIEW', canCancel: false })
  assert.equal(college.confirm.visible, false)
})

test('已打开撤销确认后撤权或切换身份均不得发出写请求', async () => {
  for (const switchIdentity of [false, true]) {
    let writes = 0
    const { state, definition } = instance({ cancel: async () => { writes++; return ok() } }, 'ACADEMIC_TEACHER', {}, ['academicAffairs.scheduleChange.view', 'academicAffairs.scheduleChange.apply'])
    state.askCancel({ changeId: '15', status: 'SUBMITTED', canCancel: true })
    assert.equal(state.confirm.visible, true)
    if (switchIdentity) {
      state.ctx = { ...state.ctx, currentRole: { roleCode: 'LEADER' }, permissionPatterns: ['academicAffairs.scheduleChange.view'] }
      definition.watch.identityKey.call(state)
    } else {
      state.ctx = { ...state.ctx, permissionPatterns: ['academicAffairs.scheduleChange.view'] }
      // 即使外层身份快照已同步，发送前仍必须重新判断当前权限。
      state.confirm.identity = state.identityKey
    }
    await state.onConfirm({ reason: '本人撤销申请' })
    assert.equal(writes, 0)
  }
})

test('责任深链学期用于三岗位正式列表查询，刷新保留原学期，不回落当前学期', async () => {
  for (const role of ['COLLEGE_ADMIN', 'ACADEMIC_ADMIN', 'ACADEMIC_TEACHER']) {
    const queries = []; let currentReads = 0
    const { state } = instance({ list: async query => { queries.push(query); return ok([{ changeId: '12' }]) } }, role, { getCurrentTerm: async () => { currentReads++; return { code: 0, data: { termId: '52' } } } })
    state.$route.query = { termId: '9007199254740997' }
    await state.syncRoute(); await state.load()
    assert.equal(queries.length, 2); assert.ok(queries.every(query => query.termId === '9007199254740997')); assert.equal(currentReads, 0)
  }
})

test('唯一申请深链只挂载具体详情，不额外读取跨学期列表；详情学期不符要阻断', async () => {
  let lists = 0, terms = 0
  const { state } = instance({ list: async () => { lists++; return ok() } }, 'ACADEMIC_TEACHER', { getCurrentTerm: async () => { terms++ } })
  state.$route.query = { termId: '51', changeId: '9007199254740997' }
  await state.syncRoute(); assert.equal(state.selectedId, '9007199254740997'); assert.equal(lists, 0); assert.equal(terms, 0)
  state.checkDetailTerm({ changeId: state.selectedId, termId: '51' }); assert.equal(state.detailError, '')
  state.checkDetailTerm({ changeId: state.selectedId, termId: '52' }); assert.match(state.detailError, /学期.*不一致/)
})

test('无效学期或申请数组在初读与重试均不发请求，不恢复旧列表', async () => {
  for (const query of [{ termId: ['51', '52'] }, { changeId: ['12', '13'] }, { termId: 'bad' }, { changeId: '-1' }]) {
    let reads = 0
    const { state } = instance({ list: async () => { reads++; return ok() } })
    state.rows = [{ changeId: 'old-private' }]; state.total = 1; state.filters.termId = '51'; state.$route.query = query
    await state.syncRoute(); await state.load()
    assert.equal(reads, 0); assert.equal(state.rows.length, 0); assert.equal(state.selectedId, ''); assert.match(state.error, /参数无效/)
  }
})

test('换学期清旧列表并拒绝迟到旧学期结果', async () => {
  const old = deferred(), queries = []
  const { state } = instance({ list: async query => { queries.push(query.termId); return query.termId === '51' ? old.promise : ok([{ changeId: 'new-term' }]) } })
  state.$route.query = { termId: '51' }; const pending = state.syncRoute()
  state.$route.query = { termId: '52' }; await state.syncRoute()
  old.resolve(ok([{ changeId: 'old-term' }])); await pending
  assert.deepEqual(queries, ['51', '52']); assert.equal(state.rows[0].changeId, 'new-term'); assert.equal(state.filters.termId, '52')
})

test('默认学期读取失败不查询全部学期，也不伪装空列表成功', async () => {
  let lists = 0
  const { state } = instance({ list: async () => { lists++; return ok() } }, 'ACADEMIC_TEACHER', { getCurrentTerm: async () => ({ code: 503001, message: '当前学期读取失败' }) })
  await state.syncRoute()
  assert.equal(lists, 0); assert.equal(state.error, '当前学期读取失败'); assert.equal(state.loading, false)
})

test('旧身份当前学期迟到不能覆盖新教师学期，也不能触发旧范围列表', async () => {
  const old = deferred(), queries = []; let terms = 0
  const { state, definition } = instance({ list: async query => { queries.push(query.termId); return ok([{ changeId: 'new-user' }]) } }, 'ACADEMIC_TEACHER', {
    getCurrentTerm: async () => ++terms === 1 ? old.promise : ({ code: 0, data: { termId: '53', termName: '新身份学期' } })
  })
  const pending = state.syncRoute()
  state.ctx = { ...state.ctx, dataScope: { scope: 'ASSIGNED', scopeName: '新教师范围' } }
  definition.watch.identityKey.call(state)
  await Promise.resolve(); await Promise.resolve(); await Promise.resolve()
  old.resolve({ code: 0, data: { termId: '51', termName: '旧身份学期' } }); await pending
  assert.equal(state.currentTermId, '53'); assert.equal(state.filters.termId, '53'); assert.deepEqual(queries, ['53'])
})

test('卸载后的学期错误和列表响应均不恢复旧结果', async () => {
  const term = deferred(), a = instance({}, 'ACADEMIC_TEACHER', { getCurrentTerm: () => term.promise })
  const p = a.state.syncRoute(); a.definition.beforeUnmount.call(a.state); term.reject(new Error('旧学期错误')); await p
  assert.equal(a.state.error, ''); assert.equal(a.state.currentTermId, '')
  const rows = deferred(), b = instance({ list: () => rows.promise })
  b.state.$route.query.termId = '52'; const reading = b.state.syncRoute(); b.definition.beforeUnmount.call(b.state)
  rows.resolve(ok([{ changeId: 'old' }])); await reading; assert.equal(b.state.rows.length, 0)
})

test('筛选重置、进入详情与返回保留来源学期，选择学期同步深链', async () => {
  const routes = [], { state } = instance()
  state.$route = { path: '/admin/academic-affairs/schedule-change', query: { termId: '51', returnToken: 'original' } }
  state.$router.replace = async route => routes.push(route); state.$router.push = async route => routes.push(route)
  await state.syncRoute(); state.filters.status = 'REJECTED'; state.reset()
  assert.equal(state.filters.termId, '51')
  state.goDetail({ changeId: '9007199254740997' }); assert.equal(routes[0].query.termId, '51'); assert.equal(routes[0].query.changeId, '9007199254740997')
  state.$route.query.changeId = '9007199254740997'; state.closeDetail()
  assert.equal(routes[1].query.termId, '51'); assert.equal(routes[1].query.changeId, undefined)
  await state.selectTerm('52'); assert.equal(routes[2].query.termId, '52'); assert.equal(routes[2].query.returnToken, 'original')
})

test('学期或申请深链改变后旧撤销确认不可继续写入', async () => {
  let writes = 0
  const { state } = instance({ cancel: async () => { writes++; return ok() } })
  state.$route.query = { termId: '51' }; state.askCancel({ changeId: '12', status: 'SUBMITTED' })
  state.$route.query.termId = '52'; await state.onConfirm({ reason: '旧确认不应继续执行' })
  assert.equal(writes, 0)
})

test('真实详情模板遇参数无效或学期不符时只显示可见错误', async () => {
  const source = readFileSync(new URL('../src/modules/academicAffairs/views/AaScheduleChangeLedgerView.vue', import.meta.url), 'utf8')
  const snippet = source.match(/<ErrorState v-if="routeError \|\| detailError"[^]*?<ScheduleChangeEvidence[^]*?\/>/)[0]
  const render = new Function('Vue', compile(snippet, { mode: 'function', prefixIdentifiers: true }).code)(Vue)
  const seen = []
  const components = {
    ErrorState: { props: ['description'], setup: props => () => Vue.h('p', props.description) },
    ScheduleChangeEvidence: { props: ['changeId'], setup: props => { seen.push(props.changeId); return () => Vue.h('section', '具体申请') } }
  }
  const make = (routeError, detailError) => renderToString(Vue.createSSRApp({ data: () => ({ routeError, detailError, selectedId: '12', detailKey: 'identity:52:12', ctx: {} }), methods: { syncRoute() {}, checkDetailTerm() {}, closeDetail() {}, goNotice() {} }, render, components }))
  assert.match(await make('学期参数无效', ''), /学期参数无效/)
  assert.match(await make('', '申请所属学期不一致'), /申请所属学期不一致/)
  assert.equal(seen.length, 0); await make('', ''); assert.deepEqual(seen, ['12'])
})
