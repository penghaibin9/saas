import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { compile } from '@vue/compiler-dom'
import * as Vue from 'vue'
import { renderToString } from 'vue/server-renderer'
import { page, deferred } from './academic-pc-parallel-b-harness.mjs'
import { academicIdentity } from '../src/modules/academicAffairs/academicFlowContext.js'
import { normalizeUiError } from '../src/utils/presentationSafety.js'

const teacher = () => ({ currentRole: { roleCode: 'ACADEMIC_TEACHER', roleName: '任课教师' }, dataScope: { scope: 'ASSIGNED', scopeName: '本人教学范围' }, permissionPatterns: ['academicAffairs.schedule.view'] })
const claims = { tenantId: 'school-one', userId: 'teacher-one', currentRoleCode: 'ACADEMIC_TEACHER' }
function instance(api = {}, extra = {}) {
  return page('AaTeacherTodayView', { academicIdentity, normalizeUiError, currentUserFromToken: () => claims, canEnterRoute: meta => meta.allowed === true,
    academicAffairsApi: { getMyTeacherToday: async () => ({ code: 0, data: {} }), ...api }, ...extra
  }, { ctx: teacher() })
}

test('教师今日教学真实模板接入已有责任视图，同时保留今日课程和本人待办', async () => {
  const source = readFileSync(new URL('../src/modules/academicAffairs/views/AaTeacherTodayView.vue', import.meta.url), 'utf8')
  const template = source.slice(source.indexOf('<template>') + 10, source.indexOf('\n<script>')).replace(/<\/template>\s*$/, '')
  const render = new Function('Vue', compile(template, { mode: 'function', prefixIdentifiers: true }).code)(Vue)
  const { definition } = instance()
  const container = { setup: (_, { slots }) => () => Vue.h('div', [slots.actions?.(), slots.default?.()]) }
  const seen = []
  const stubs = {
    ModulePageShell: container, AppSectionCard: { props: ['title'], setup: (props, { slots }) => () => Vue.h('section', [Vue.h('h2', props.title), slots.default?.()]) },
    AppButton: { setup: (_, { slots }) => () => Vue.h('button', slots.default?.()) },
    AppInlineAlert: { props: ['description'], setup: props => () => Vue.h('p', props.description) },
    AcademicFlowOverview: { props: ['ctx', 'termId', 'canOpen'], setup: props => { seen.push(props); return () => Vue.h('section', { 'aria-label': '学期责任接力' }, '本人责任与下一岗位') } },
    LoadingState: { render: () => Vue.h('p', '正在读取正式事实') }, ErrorState: { props: ['description'], setup: props => () => Vue.h('p', props.description) }, EmptyState: { props: ['title'], setup: props => () => Vue.h('p', props.title) }
  }
  async function renderPage(query, role = teacher(), overrides = {}) {
    const app = Vue.createSSRApp({ ...definition, data() { return { ...definition.data.call(this), ...overrides } }, created: undefined, render, components: stubs }, { ctx: role })
    app.config.globalProperties.$route = { path: '/admin/academic-affairs/teacher/today', query }
    return renderToString(app)
  }
  const html = await renderPage({ termId: '9007199254740997' })
  assert.equal(seen.length, 1); assert.equal(seen[0].termId, '9007199254740997'); assert.equal(seen[0].ctx.currentRole.roleCode, 'ACADEMIC_TEACHER')
  assert.match(html, /本人责任与下一岗位/); assert.match(html, /今天的课/); assert.match(html, /我的待办/)
  assert.doesNotMatch(html, /各学院并行进度/)
  assert.match(await renderPage({ termId: ['52', '53'] }), /学期参数无效/)
  assert.equal(seen.length, 1, '无效深链不挂载责任请求组件')
  await renderPage({}, { ...teacher(), currentRole: { roleCode: 'COLLEGE_ADMIN' } })
  assert.equal(seen.length, 1, '非教师分支不误展示本人责任入口')
  const retrying = await renderPage({}, teacher(), { loading: true })
  assert.equal((retrying.match(/正在读取正式事实/g) || []).length, 2)
  assert.doesNotMatch(retrying, /今天没有授课安排|当前没有需要本人处理的事项/)
  const failed = await renderPage({}, teacher(), { todayError: '网络异常，请检查网络连接后重试' })
  assert.equal((failed.match(/网络异常，请检查网络连接后重试/g) || []).length, 2)
  assert.doesNotMatch(failed, /今天没有授课安排|当前没有需要本人处理的事项/)
})

test('教师责任学期使用字符串深链并保留原待办标签与返回位置', async () => {
  const { state } = instance(), routes = []
  state.$route = { path: '/admin/academic-affairs/teacher/today', query: { termId: '52', work: 'waiting', returnToken: 'original' } }
  state.$router.replace = async route => routes.push(route)
  assert.equal(state.flowTermId, '52'); assert.equal(state.flowTermError, '')
  await state.selectFlowTerm('9007199254740997')
  assert.equal(routes[0].query.termId, '9007199254740997'); assert.equal(routes[0].query.work, 'waiting'); assert.equal(routes[0].query.returnToken, 'original')
  await state.selectFlowTerm('invalid'); assert.equal(routes.length, 1)
  state.$route.query.termId = ['52', '53']; assert.match(state.flowTermError, /无效/)
  await state.selectFlowTerm(''); assert.equal(routes[1].query.termId, undefined)
})

test('责任动作保留正式路由权限检查，无权和未知入口不跳转', () => {
  const { state } = instance(), routes = []
  state.$router.resolve = path => ({ matched: path === '/unknown' ? [] : [{ meta: { allowed: path === '/allowed' } }] })
  state.$router.push = async path => routes.push(path)
  state.openFlow('/denied'); state.openFlow('/unknown'); assert.equal(routes.length, 0)
  state.openFlow('/allowed'); assert.deepEqual(routes, ['/allowed'])
})

test('页面刷新同时重读本人责任与今日教学，不改变学期深链', async () => {
  let flowReads = 0, todayReads = 0
  const { state } = instance({ getMyTeacherToday: async () => { todayReads++; return { code: 0, data: {} } } })
  state.$refs = { responsibilityFlow: { load: () => { flowReads++ } } }; state.$route.query.termId = '52'
  await state.refresh()
  assert.equal(flowReads, 1); assert.equal(todayReads, 1); assert.equal(state.flowTermId, '52')
})

test('切身份立即清旧今日事实，迟到响应不能覆盖新教师已加载的事实', async () => {
  const pending = deferred(); let reads = 0
  const { state, definition } = instance({ getMyTeacherToday: async () => ++reads === 1 ? pending.promise : ({ code: 0, data: { todayItems: [{ courseName: '新教师课程' }], todayDate: '2026-09-27' } }) })
  state.todayItems = [{ courseName: '旧课程' }]; const old = state.load()
  assert.equal(state.todayItems.length, 0)
  state.ctx = { ...teacher(), dataScope: { scope: 'ASSIGNED', scopeName: '另一教师本人范围' } }
  definition.watch.identityKey.call(state)
  await Promise.resolve(); await Promise.resolve()
  pending.resolve({ code: 0, data: { todayItems: [{ courseName: '迟到旧教师课程' }], todayDate: '2025-01-01' } }); await old
  assert.equal(state.todayItems[0].courseName, '新教师课程'); assert.equal(state.todayDate, '2026-09-27'); assert.equal(state.loading, false)
})

test('今日事实失败显示错误和未知数量，卸载后错误不写入', async () => {
  const { state } = instance({ getMyTeacherToday: async () => ({ code: 503001, message: '正式任课事实读取失败' }) })
  await state.load(); assert.equal(state.todayError, '系统暂时无法完成该操作，请稍后重试'); assert.ok(state.metrics.every(metric => metric.value === null))
  const pending = deferred(), late = instance({ getMyTeacherToday: () => pending.promise })
  const read = late.state.load(); late.definition.beforeUnmount.call(late.state)
  pending.reject(new Error('旧请求错误')); await read; assert.equal(late.state.todayError, '')
})

test('今日课程与待办失败后重试重读正式事实，等待中不冒充空数据', async () => {
  const retry = deferred(); let reads = 0
  const { state } = instance({ getMyTeacherToday: async () => { if (++reads === 1) throw new TypeError('Failed to fetch'); return retry.promise } })
  await state.load()
  assert.equal(state.todayError, '网络异常，请检查网络连接后重试')
  assert.equal(state.loading, false)
  assert.ok(state.metrics.every(metric => metric.value === null))
  const pending = state.load()
  assert.equal(state.loading, true); assert.equal(state.todayError, '')
  retry.resolve({ code: 0, data: { todayItems: [{ courseName: '恢复的正式课程' }], workbench: { actionItems: [{ kind: 'TEACHING_TASK', id: '42' }] } } })
  await pending
  assert.equal(reads, 2); assert.equal(state.loading, false)
  assert.equal(state.todayItems[0].courseName, '恢复的正式课程'); assert.equal(state.actionItems[0].id, '42')
})

test('待确认任务和待建成绩保留服务端精确字符串对象及上下文链接', async () => {
  const taskPath = '/admin/academic-affairs/teaching-tasks/teacher-confirm?taskId=9007199254740997'
  const gradePath = '/admin/academic-affairs/grade-entry?teachingTaskId=9007199254740999&action=create'
  const { state } = instance({ getMyTeacherToday: async () => ({ code: 0, data: { workbench: { actionItems: [
    { kind: 'TEACHING_TASK', path: taskPath }, { kind: 'GRADE_SETUP', path: gradePath }
  ], counts: { teachingTasks: 1, grades: 1 } } } }) }), routes = []
  state.$router.push = async path => routes.push(path)
  await state.load()
  state.go(state.metrics.find(row => row.key === 'task').path)
  state.go(state.metrics.find(row => row.key === 'grade').path)
  assert.deepEqual(routes, [taskPath, gradePath])
})

test('现有考勤动作保留字符串业务身份，跨身份迟到回执不能导航', async () => {
  const pending = deferred(), routes = []; let sent
  const { state } = instance({ openAttendanceSession: async body => { sent = body; return pending.promise } })
  state.$router.push = async path => routes.push(path)
  const opening = state.openAttendance({ scheduleItemId: '9007199254740997', teachingTaskId: '9007199254740993', classId: '9007199254740999', slotNo: 2, sessionDate: '2026-09-27' })
  assert.equal(sent.teachingTaskId, '9007199254740993'); assert.equal(sent.classId, '9007199254740999'); assert.equal(sent.scheduleItemId, '9007199254740997')
  state.ctx = { ...teacher(), permissionVersion: 2 }
  pending.resolve({ code: 0, data: { sessionId: '123' } }); await opening
  assert.equal(routes.length, 0)
})
