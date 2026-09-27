import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import { compile } from '@vue/compiler-dom'
import * as Vue from 'vue'
import { renderToString } from 'vue/server-renderer'
import * as registry from '../src/modules/academicAffairs/config/academicFlowRegistry.js'
import * as context from '../src/modules/academicAffairs/academicFlowContext.js'
import { projectAcademicCollegeModules } from '../src/modules/academicAffairs/config/academicCollegeNavigation.js'
import { NAV_PLAN, getVisibleNavPlan } from '../src/config/navPlan.js'
import { page, deferred } from './academic-pc-parallel-b-harness.mjs'
import { isDeniedResult } from '../src/modules/academicAffairs/components/parallel-a/resultState.js'
import * as gradeHelpers from '../src/modules/academicAffairs/views/parallel-c/grade-review.js'
import * as programConstants from '../src/modules/academicAffairs/constants/course-program.js'
import { normalizeUiError } from '../src/utils/presentationSafety.js'

const responsibility = { orgType: 'COLLEGE', orgId: '9007199254740993', orgName: '信息学院', assignmentTypes: ['SECRETARY'], roleCodes: ['COLLEGE_ADMIN'], assigneeUserIds: ['9007199254740995'], assigneeNames: ['李老师'], resolved: true, source: 'STAFF_ASSIGNMENT' }
const stage = (status = 'READY', extra = {}) => ({ stageCode: 'F40_TEACHING_TASK', label: '教学任务落实', status, termId: '9007199254740997', responsibility, blockers: [], risks: [], primaryAction: null, nextStep: null, ...extra })
const unit = (id, name, status) => ({ collegeId: id, collegeName: name, status, stages: [stage(status)], blockers: status === 'BLOCKED' ? [{ code: 'COLLEGE_NOT_READY', message: '2门课程尚未落实教师' }] : [], responsibility })
const payload = () => ({ term: { termId: '9007199254740997', termLabel: '秋季学期', status: 'ACTIVE' }, viewer: { roleCode: 'ACADEMIC_ADMIN', scopeType: 'TENANT_ALL', collegeIds: ['9007199254740993', '2'], assignments: [] }, schoolStage: stage(), myStage: stage(), unitProgress: [unit('9007199254740993', '信息学院', 'READY'), unit('2', '机电学院', 'BLOCKED')], currentResponsibilities: [], stages: [stage()], schoolGates: [] })
const tag = { props: ['label'], setup: props => () => Vue.h('span', props.label) }
const button = { setup: (_, { slots }) => () => Vue.h('button', slots.default?.()) }
const components = { StatusTag: tag, AppButton: button, LoadingState: { template: '<p>加载中</p>' }, ErrorState: { template: '<p>读取失败</p>' }, EmptyState: { template: '<p>暂无进度</p>' }, AppTermEntityPicker: { template: '<input aria-label="选择学期" />' } }
function loadComponent(name, overrides = {}) {
  const source = readFileSync(new URL(`../src/modules/academicAffairs/components/${name}.vue`, import.meta.url), 'utf8')
  const script = source.match(/<script>([\s\S]*?)<\/script>/)[1]
    .replace(/^import (.*?) from .*$/gm, (_, binding) => `const ${binding.replace(/ as /g, ': ')} = dependencies${binding.startsWith('{') ? '' : '.' + binding}`)
    .replace('export default', 'component =')
  const environment = { Function, Object, Array, String, Boolean, dependencies: { ...components, ...registry, ...context, normalizeUiError, currentUserFromToken: () => ({ tenantId: 'school', userId: 'user', currentRoleCode: 'ACADEMIC_ADMIN' }), ...overrides }, window: { addEventListener() {}, removeEventListener() {} } }
  vm.runInNewContext(script, environment)
  environment.component.render = new Function('Vue', compile(source.match(/<template>([\s\S]*?)<\/template>\s*<script>/)[1], { mode: 'function', prefixIdentifiers: true }).code)(Vue)
  return environment.component
}
const responsibilityComponent = loadComponent('AcademicResponsibilityBar')
const handoffComponent = loadComponent('AcademicHandoffCard')
const gateComponent = loadComponent('AcademicSchoolGateCard')
const matrixComponent = loadComponent('AcademicUnitProgressMatrix')
const render = (component, props) => renderToString(Vue.createSSRApp(component, props))

test('V5 has exactly six states and unknown machine values never become business success or English labels', () => {
  assert.equal(Object.keys(registry.ACADEMIC_FLOW_STATUS).length, 6)
  assert.equal(registry.ACADEMIC_FLOW_STAGES.length, 12)
  assert.equal(registry.academicFlowStatus('PARTIAL_DONE').label, '状态待核对')
  assert.equal(registry.academicFlowStageLabel({ label: 'UNRESOLVED_INTERNAL_CODE' }), '责任事项')
  assert.equal(registry.academicFlowText('SQLSTATE bad SQL', '读取失败'), '读取失败')
  assert.equal(registry.academicFlowCount(undefined), '待核对')
  assert.equal(registry.academicFlowCount(-1), '待核对')
  assert.equal(registry.academicFlowCount(0), '0')
})

test('responsibility keeps business names but never guesses a user from a role or revives expired assignment', async () => {
  const html = await render(responsibilityComponent, { responsibility: { ...responsibility, orgName: 'AI学院', assigneeNames: ['Alex老师'], resolved: false, reason: 'ASSIGNMENT_EXPIRED' } })
  assert.match(html, /AI学院/)
  assert.match(html, /具体责任人待配置/)
  assert.match(html, /责任任职已到期/)
  assert.doesNotMatch(html, /Alex老师|ASSIGNMENT_EXPIRED|COLLEGE_ADMIN|SECRETARY/)
  const active = registry.academicFlowResponsibility({ ...responsibility, assigneeNames: ['Alex'] })
  assert.equal(active.assigneeLabel, 'Alex')
})

test('flow payload validation rejects incomplete data, wrong term, unsafe numeric IDs and cross-college results', () => {
  assert.equal(registry.validateAcademicFlow(payload()).unitProgress.length, 2)
  assert.throws(() => registry.validateAcademicFlow({ ...payload(), unitProgress: null }), /返回不完整/)
  assert.throws(() => registry.validateAcademicFlow({ ...payload(), stages: [null] }), /返回不完整/)
  assert.throws(() => registry.validateAcademicFlow(payload(), { termId: '1' }), /学期.*不一致/)
  assert.throws(() => registry.validateAcademicFlow({ ...payload(), term: { termId: Number('9007199254740997') } }), /无法安全读取/)
  const college = { ...payload(), viewer: { roleCode: 'COLLEGE_ADMIN', scopeType: 'COLLEGE', collegeIds: ['9007199254740993'] } }
  assert.throws(() => registry.validateAcademicFlow(college), /授权范围不一致/)
  college.unitProgress = [college.unitProgress[0]]
  assert.equal(registry.validateAcademicFlow(college).unitProgress[0].collegeId, '9007199254740993')
})

test('专业视角仅接受服务端字符串专业范围，不从班级范围推断专业', async () => {
  for (const ids of [null, '1', [1], ['']]) assert.throws(() => registry.validateAcademicFlow({ ...payload(), viewer: { ...payload().viewer, majorIds: ids } }), /专业责任范围/)
  const data = { ...payload(), viewer: { roleCode: 'CUSTOM_MAJOR', scopeType: 'CLASS', collegeIds: [], majorIds: ['9007199254740993'] }, unitProgress: [] }
  assert.equal(registry.validateAcademicFlow(data).viewer.majorIds[0], '9007199254740993')
  const component = loadComponent('AcademicFlowOverview')
  const state = { flow: data }
  for (const [key, getter] of Object.entries(component.computed)) Object.defineProperty(state, key, { get: () => getter.call(state) })
  assert.equal(state.majorView, true); assert.equal(state.heading, '本专业教学对账')
  data.viewer.majorIds = []; assert.equal(state.majorView, false); assert.equal(state.heading, '当前授权范围教学进度')
  delete data.viewer.majorIds; assert.equal(state.majorView, false)
})

test('专业培养方案与应开对账只展示正式摘要和计数，不渲染学院办理或学校矩阵', async () => {
  const data = { ...payload(), viewer: { roleCode: 'CUSTOM_MAJOR', scopeType: 'MAJOR', collegeIds: [], majorIds: ['7'] }, unitProgress: [], stages: [
    stage('READY', { stageCode: 'F30_PROGRAM_COURSE', label: '培养方案与课程', evidence: { programCount: 3, summary: '本专业3份正式培养方案可查阅' } }),
    stage('BLOCKED', { stageCode: 'F40_TEACHING_TASK', label: '教学任务落实', evidence: { readOnly: true, expectedCourseCount: 6, actualTaskCount: 5, pendingTeacherCount: null, blockerCount: 1, summary: '应开6项，1项尚未生成教学任务' }, primaryAction: { label: '不可出现的学院分配', route: '/admin/academic-affairs/teaching-tasks/assign' }, blockers: [{ message: '请由开课学院核对缺少的任务' }] })
  ] }
  data.currentResponsibilities = data.stages; data.myStage = data.stages[1]
  const component = loadComponent('AcademicFlowOverview', { AcademicResponsibilityBar: responsibilityComponent, AcademicUnitProgressMatrix: matrixComponent, AcademicSchoolGateCard: gateComponent, AcademicHandoffCard: handoffComponent })
  component.created = undefined; const initial = component.data
  component.data = () => ({ ...initial(), flow: data })
  const html = await render(component, { ctx: { currentRole: { roleCode: 'CUSTOM_MAJOR' }, dataScope: {} }, canOpen: () => true })
  assert.match(html, /本专业教学对账/); assert.match(html, /本专业3份正式培养方案可查阅/); assert.match(html, /培养方案数<\/dt><dd>3/)
  assert.match(html, /应开课程项<\/dt><dd>6/); assert.match(html, /实际教学任务<\/dt><dd>5/); assert.match(html, /待教师确认<\/dt><dd>待核对/)
  assert.match(html, /存在阻断/); assert.match(html, /请由开课学院核对缺少的任务/)
  assert.doesNotMatch(html, /不可出现的学院分配|各学院并行进度|本学院教学进度|学校统一办理条件/)
})

test('college navigation preserves all 17 workspaces, routes, leaf identities and permissions without mutating the catalog', () => {
  const modules = getVisibleNavPlan({ permissionPatterns: ['*'], ctxKey: 'college-v5' }).find(group => group.key === 'academic-affairs').children
  const before = JSON.stringify(modules), catalog = JSON.stringify(NAV_PLAN)
  const projected = projectAcademicCollegeModules(modules, { currentRole: { roleCode: 'COLLEGE_ADMIN' }, dataScope: { scopeType: 'COLLEGE' } })
  assert.equal(projected.length, 17)
  assert.equal(projected[0].label, '本学院工作台')
  const leaves = projected.flatMap(mod => mod.children)
  for (const leaf of modules.flatMap(mod => mod.children)) {
    const result = leaves.find(item => item.leafId === leaf.leafId)
    for (const key of ['path', 'permissionKey', 'permissionAny', 'permissionAll', 'leafId', 'status', 'disabled', 'hidden']) assert.deepEqual(result[key], leaf[key])
  }
  for (const id of ['aa.schedule.schedule.publish', 'aa.grade-review.grade.publish', 'aa.training.programs.console.tab.publish']) assert.equal(leaves.find(leaf => leaf.leafId === id).menuSecondary, true)
  assert.equal(JSON.stringify(modules), before)
  assert.equal(JSON.stringify(NAV_PLAN), catalog)
  assert.equal(projectAcademicCollegeModules(modules, { currentRole: { roleCode: 'ACADEMIC_TEACHER' } }), modules)
})

test('matrix renders the ready college independently of the blocked college and shows real offering responsibility', async () => {
  const html = await render(matrixComponent, { units: payload().unitProgress })
  assert.match(html, /信息学院[\s\S]*已就绪/)
  assert.match(html, /机电学院[\s\S]*存在阻断/)
  assert.match(html, /2门课程尚未落实教师/)
  assert.doesNotMatch(html, />READY<|>BLOCKED<|F40_TEACHING_TASK/)
  const handoff = await render(handoffComponent, { nextStep: { label: '进入专业课排课', responsibility: { ...responsibility, orgName: '公共教学部' } } })
  assert.match(handoff, /公共教学部/)
  assert.match(handoff, /进入专业课排课/)
})

test('school gate does not render a publish command or invent readiness from unit counts', async () => {
  const html = await render(gateComponent, { gate: { label: '全校课表发布条件', ready: false, readyUnitCount: 1, totalUnitCount: 2, blockedUnitCount: 1, blockers: [{ code: 'SCHOOL_GATE_NOT_READY' }] } })
  assert.match(html, /条件未满足/)
  assert.match(html, /1 \/ 2/)
  assert.doesNotMatch(html, /<button|SCHOOL_GATE_NOT_READY/)
  const unknown = await render(gateComponent, { gate: { label: '全校课表发布条件', readyUnitCount: 2, totalUnitCount: 2, blockers: [] } })
  assert.match(unknown, /条件待核对/)
  assert.doesNotMatch(unknown, /条件已满足/)
  const unrelated = await render(gateComponent, { gate: { required: false, ready: false, blockers: [] } })
  assert.match(unrelated, /本范围不适用/)
  assert.doesNotMatch(unrelated, /条件未满足/)
})

function overviewState(api) {
  const component = loadComponent('AcademicFlowOverview', { academicFlowApi: api, AcademicResponsibilityBar: responsibilityComponent, AcademicUnitProgressMatrix: matrixComponent, AcademicSchoolGateCard: gateComponent, AcademicHandoffCard: handoffComponent })
  const state = { ...component.data(), ...component.methods, ctx: { currentRole: { roleCode: 'ACADEMIC_ADMIN' }, permissionPatterns: ['a'], dataScope: { scopeType: 'TENANT_ALL' } }, termId: '', collegeId: '' }
  Object.defineProperty(state, 'contextKey', { get: () => component.computed.contextKey.call(state) })
  state.readGate = context.createAcademicRequestGate(() => state.contextKey)
  return { component, state }
}
test('term, role and scope changes discard late flow results and clear previous facts before reloading', async () => {
  let resolveOld
  const old = new Promise(resolve => { resolveOld = resolve })
  let calls = 0
  const { state } = overviewState({ get: () => ++calls === 1 ? old : Promise.resolve({ ...payload(), term: { termId: '2' } }) })
  const pending = state.load()
  state.termId = '2'; state.ctx.currentRole = { roleCode: 'COLLEGE_ADMIN' }; state.ctx.dataScope = { scopeType: 'COLLEGE' }
  const fresh = state.load()
  assert.equal(state.flow, null)
  await fresh
  resolveOld(payload()); await pending
  assert.equal(state.flow.term.termId, '2')
  assert.equal(state.loading, false)
})

test('refresh after assignment expiry reads again; failed or forbidden requests never become empty progress', async () => {
  let denied = false, calls = 0
  const { state } = overviewState({ get: async () => { calls++; if (denied) throw { httpStatus: 403, message: 'NO_PERMISSION' }; return payload() } })
  await state.load(); denied = true; await state.load()
  assert.equal(calls, 2)
  assert.equal(state.flow, null)
  assert.match(state.error, /学院、教师或校教务人员继续办理/)
  assert.equal(state.loading, false)
})

test('API preserves string identifiers and rejects malformed parameters before sending requests', async () => {
  let sent
  const source = readFileSync(new URL('../src/modules/academicAffairs/api/academic-flow.api.js', import.meta.url), 'utf8')
    .replace(/^import .*$/gm, '').replace('export const academicFlowApi', 'api')
  const environment = { validateAcademicFlow: registry.validateAcademicFlow, request: async (path, options) => { sent = { path, options }; return payload() } }
  vm.runInNewContext(source, environment)
  await environment.api.get({ termId: '9007199254740997', collegeId: '9007199254740993' })
  assert.equal(sent.options.params.termId, '9007199254740997')
  assert.equal(sent.options.params.collegeId, '9007199254740993')
  sent = null
  await assert.rejects(environment.api.get({ termId: ['1', '2'] }), /参数无效/)
  assert.equal(sent, null)
})

test('overview actions retain selected term and a scoped return token on the existing navigation preflight', async () => {
  let destination, stored = ''
  const source = readFileSync(new URL('../src/modules/academicAffairs/components/AaOverviewWorkspace.vue', import.meta.url), 'utf8')
    .match(/<script>([\s\S]*?)<\/script>/)[1]
    .replace(/^import (.*?) from .*$/gm, (_, binding) => `const ${binding.replace(/ as /g, ': ')} = dependencies${binding.startsWith('{') ? '' : '.' + binding}`)
    .replace('export default', 'component =')
  const environment = { dependencies: { ...context, request: async () => ({ rbacOk: true, permissionPatterns: ['academicAffairs.teachingTask.view'] }), routeAllowed: () => true }, window: { sessionStorage: { getItem: () => stored, setItem: (_, value) => { stored = value } } } }
  vm.runInNewContext(source, environment)
  const state = { ...environment.component.data(), ...environment.component.methods, disposed: false, termId: '9007199254740997', identity: () => 'school-role', canOpen: () => true, target: () => ({ path: '/admin/academic-affairs/teaching-tasks' }), $route: { path: '/admin/academic-affairs', query: { termId: '9007199254740997', page: '2' } }, $el: { closest: () => ({ scrollTop: 23 }) }, $router: { resolve: value => ({ ...value, query: {} }), push: async value => { destination = value } } }
  await state.go('aa-teaching-tasks')
  assert.equal(destination.query.termId, '9007199254740997')
  assert.ok(destination.query.returnToken)
  const back = context.createAcademicReturnStore(environment.window.sessionStorage).resolve(destination.query.returnToken, 'school-role')
  assert.equal(back.path, '/admin/academic-affairs?termId=9007199254740997&page=2')
  assert.equal(back.scrollTop, 23)
})


test('formal program blocker summaries are shown in business Chinese', () => {
  assert.equal(registry.academicFlowText('方案覆盖率100%，方案BLOCKER 2项'), '方案覆盖率100%，方案阻断 2项')
  assert.equal(registry.academicFlowText('生效方案均无BLOCKER'), '生效方案均无阻断项')
  assert.equal(registry.academicFlowText('课表阻断1项：漏排0、HARD冲突0；本学期没有课表批次'), '课表阻断1项：漏排0、严重冲突0；本学期没有课表批次')
})

test('object responsibility is bound to its string ID and does not infer assignees or render another command', async () => {
  const component = loadComponent('AcademicObjectResponsibility')
  const html = await render(component, { objectId: '9007199254740997', responsibility, nextStep: { label: '交开课单位排课', responsibility: { ...responsibility, orgName: '公共教学部' } } })
  assert.match(html, /data-object-id="9007199254740997"/)
  assert.match(html, /信息学院.*李老师/)
  assert.match(html, /交开课单位排课.*公共教学部/)
  assert.doesNotMatch(html, /<button|COLLEGE_ADMIN|SECRETARY/)
  const expired = await render(component, { objectId: '2', responsibility: { ...responsibility, resolved: false, reason: 'ASSIGNMENT_EXPIRED' } })
  assert.doesNotMatch(expired, /李老师/)
  assert.match(expired, /责任任职已到期/)
  const noObject = await render(component, { objectId: '', responsibility })
  assert.doesNotMatch(noObject, /信息学院|李老师/)
})

function programPage(api) {
  const result = page('AaProgramConsoleView', { ...registry, ...programConstants, academicAffairsApi: api, programQualityApi: { validate: async () => ({ code: 0, data: { issues: [] } }) } }, { ctx: { ctxKey: 'school:user:role', currentRole: { roleCode: 'COLLEGE_ADMIN' }, dataScope: { scopeType: 'COLLEGE' } } })
  result.state.tab = 'publish'; result.state.activeProgramId = '9007199254740993'; result.state.rows = [{ programId: '9007199254740993' }, { programId: '9007199254740995' }]
  return result
}

test('program editor uses live responsibility and next step, without reviving expired assignees', () => {
  const { state } = page('AaProgramEditorView', { ...registry, ...programConstants }, { ctx: { currentRole: {}, dataScope: {} } })
  state.program = { status: 'PUBLISHED', responsibility, nextStep: { label: '由校教务绑定适用年级后启用' } }
  assert.match(state.programOwner, /信息学院.*李老师/)
  assert.equal(state.programNextOwner, '由校教务绑定适用年级后启用')
  state.program.responsibility = { ...responsibility, resolved: false, reason: 'ASSIGNMENT_EXPIRED' }
  assert.match(state.programOwner, /责任任职已到期/)
  assert.doesNotMatch(state.programOwner, /李老师/)
  state.program = { status: 'ENABLED' }
  assert.equal(state.programOwner, '本轮方案编制已结束')
  assert.equal(state.programNextOwner, '')
  state.program = { status: 'DRAFT' }
  assert.match(state.programOwner, /具体责任人待配置/)
})

test('program publishing reads responsibility from the exact program detail without requiring a term', async () => {
  const ids = []
  const { state } = programPage({ getProgram: async programId => { ids.push(programId); return { code: 0, data: { programId, responsibility, nextStep: { label: '生成正式教学任务' } } } } })
  await state.loadWorkflowEvidence()
  assert.deepEqual(ids, ['9007199254740993'])
  assert.equal(state.workflowProgram.responsibility, responsibility)
  assert.equal(state.workflowEvidenceError, '')
  assert.equal(state.workflowProgram.termId, undefined)
})

test('late program detail from another object, identity, or disposed page cannot restore old responsibility', async () => {
  const old = deferred()
  const { state } = programPage({ getProgram: () => old.promise })
  const pending = state.loadWorkflowEvidence()
  state.activeProgramId = '9007199254740995'
  old.resolve({ code: 0, data: { programId: '9007199254740993', responsibility } }); await pending
  assert.equal(state.workflowProgram, null)
  for (const change of ['identity', 'unmount']) {
    const read = deferred(), next = programPage({ getProgram: () => read.promise })
    const loading = next.state.loadWorkflowEvidence()
    if (change === 'unmount') next.definition.beforeUnmount.call(next.state)
    else next.state.ctx.currentRole = { roleCode: 'ACADEMIC_ADMIN' }
    read.resolve({ code: 0, data: { programId: '9007199254740993', responsibility } }); await loading
    assert.equal(next.state.workflowProgram, null)
  }
})

test('wrong program detail is a visible failure instead of a responsibility fallback from its list row', async () => {
  const { state } = programPage({ getProgram: async () => ({ code: 0, data: { programId: 'another', responsibility } }) })
  state.rows[0].responsibility = responsibility
  await state.loadWorkflowEvidence()
  assert.equal(state.workflowProgram, null)
  assert.match(state.workflowEvidenceError, /当前方案详情未能读取/)
})

function examPage(getBatch) {
  return page('AaExamConsoleView', { ...registry, academicAffairsExamApi: { getBatch, listCourses: async () => ({ code: 0, data: { list: [], total: 0 } }), batchStats: async () => ({ code: 0, data: {} }) }, academicAffairsExamConvenienceApi: { getReadiness: async () => ({ code: 0, data: null }) } })
}

test('exam responsibility replaces the list snapshot only after reading the selected batch detail', async () => {
  const detail = deferred(), { state } = examPage(() => detail.promise)
  const pending = state.select({ batchId: '9007199254740993', status: 'DRAFT', responsibility: { ...responsibility, orgName: '旧学院' } })
  assert.equal(state.current.responsibility, null)
  assert.equal(state.current.status, null)
  assert.match(state.objectBar.owner, /正在读取/)
  detail.resolve({ code: 0, data: { batchId: '9007199254740993', status: 'COURSE_CONFIRMED', responsibility, nextStep: { label: '校教务发布' } } }); await pending
  assert.match(state.objectBar.owner, /信息学院/)
  assert.equal(state.objectBar.nextOwner, '校教务发布')
  assert.equal(state.batchDetailLoading, false)
})

test('failed or mismatched exam detail never exposes list responsibility or authorizes old status actions', async () => {
  for (const result of [{ code: 403, message: '范围已撤销' }, { code: 0, data: { batchId: 'other', responsibility } }]) {
    const { state } = examPage(async () => result)
    await state.select({ batchId: '1', status: 'DRAFT', responsibility })
    assert.equal(state.current.responsibility, null)
    assert.equal(state.current.status, null)
    assert.equal(state.courses.length, 0)
    assert.ok(state.readinessError)
    assert.doesNotMatch(state.objectBar.owner, /李老师/)
  }
})

test('late exam details are discarded after batch and identity changes', async () => {
  const old = deferred()
  const { state } = examPage(id => id === '1' ? old.promise : Promise.resolve({ code: 0, data: { batchId: id, responsibility: { ...responsibility, orgName: '新学院' } } }))
  const pending = state.select({ batchId: '1' }); await state.select({ batchId: '2' })
  old.resolve({ code: 0, data: { batchId: '1', responsibility } }); await pending
  assert.equal(state.current.batchId, '2'); assert.match(state.objectBar.owner, /新学院/)
  const late = deferred(), next = examPage(() => late.promise)
  const loading = next.state.select({ batchId: '1' }); next.state.ctx.currentRole = { roleCode: 'ACADEMIC_TEACHER' }
  late.resolve({ code: 0, data: { batchId: '1', responsibility } }); await loading
  assert.equal(next.state.current.responsibility, null)
})

test('public course scheduling mode is the server mode and missing configuration is never school-centralized by default', () => {
  const { state } = page('AaSchedulingConsoleView', { ...registry }, { ctx: { currentRole: {}, dataScope: {} } })
  for (const [mode, label] of [['SCHOOL_CENTRALIZED', '校教务统排'], ['OFFERING_UNIT', '开课单位编排'], ['HYBRID', '校院协同']]) {
    state.workbench = { publicScheduleMode: mode }
    assert.match(state.publicScheduleResponsibility, new RegExp(label))
  }
  state.workbench = { courseScopeCounts: { public: 0, professional: 3 } }
  assert.match(state.publicScheduleResponsibility, /模式待核对/)
  assert.equal(state.academicFlowCount(state.workbench.courseScopeCounts.public), '0')
  assert.equal(state.academicFlowCount(undefined), '待核对')
})

test('归档终态说明已完成事项，不把空责任冒充缺少任职；真实责任各自优先', () => {
  const { state } = page('AaArchiveConsoleView', { ...registry }, { ctx: { currentRole: {}, dataScope: {} } })
  for (const [status, owner, nextRole] of [
    ['ARCHIVED', '学校已完成封存', '后续查阅或纠错由校教务统筹'],
    ['CANCELLED', '批次已取消', '无需继续办理此批次']
  ]) {
    state.current = { batchId: '1', status, responsibility: null, nextStep: null }
    assert.equal(state.archiveOwner, owner)
    assert.equal(state.nextRole, nextRole)
    assert.doesNotMatch(`${state.archiveOwner} ${state.nextRole}`, /李老师|9007199254740995|任职|待明确/)
    state.current.responsibility = responsibility
    assert.match(state.archiveOwner, /信息学院.*李老师/)
    assert.equal(state.nextRole, nextRole)
    state.current.responsibility = null
    state.current.nextStep = { label: '核对受控纠错材料', responsibility: { ...responsibility, orgName: '校教务处' } }
    assert.equal(state.archiveOwner, owner)
    assert.match(state.nextRole, /校教务处.*李老师/)
  }
})

test('非终态或未知归档状态缺少责任时仍明确待核对，不猜测办理人', () => {
  const { state } = page('AaArchiveConsoleView', { ...registry }, { ctx: { currentRole: {}, dataScope: {} } })
  for (const status of ['DRAFT', 'CHECKING', 'READY', 'MISSING_ITEMS', undefined]) {
    state.current = { batchId: '1', status, responsibility: null, nextStep: null }
    assert.match(state.archiveOwner, /责任岗位待明确/)
    assert.equal(state.nextRole, '下一责任事项待明确')
    assert.doesNotMatch(`${state.archiveOwner} ${state.nextRole}`, /已完成封存|李老师|9007199254740995/)
    state.current.responsibility = responsibility
    state.current.nextStep = { label: '核对归档材料', responsibility: { ...responsibility, orgName: '校教务处' } }
    assert.match(state.archiveOwner, /信息学院.*李老师/)
    assert.match(state.nextRole, /校教务处.*李老师/)
  }
})


test('exam archive responsibility is re-read from its exact detail rather than an archived list snapshot', async () => {
  const { state } = examPage(async batchId => ({ code: 0, data: { batchId, responsibility: { ...responsibility, orgName: '正式归档责任单位' } } }))
  await state.selectArchive({ batchId: '9007199254740993', responsibility: { ...responsibility, orgName: '旧列表责任单位' }, archiveSnapshot: { courseCount: 2 } })
  assert.equal(state.selectedArchive.responsibility.orgName, '正式归档责任单位')
  assert.equal(state.selectedArchive.archiveSnapshot.courseCount, 2)
})


test('grade queue renders separate responsibility and handoff for every concrete task row', async () => {
  const { definition } = page('AaGradeOverviewView', { ...gradeHelpers }, { ctx: { currentRole: {}, dataScope: {} } })
  const source = readFileSync(new URL('../src/modules/academicAffairs/views/AaGradeOverviewView.vue', import.meta.url), 'utf8')
  const baseData = definition.data()
  const rows = [
    { gradeTaskId: '9007199254740993', courseName: '公共英语', status: 'SUBMITTED', responsibility: { ...responsibility, orgName: '公共教学部' }, nextStep: { label: '英语课程学院审核' } },
    { gradeTaskId: '9007199254740995', courseName: '机电技术', status: 'INPUTTING', responsibility: { ...responsibility, orgName: '机电学院' }, nextStep: { label: '机电课程教师提交' } }
  ]
  const wrapper = { setup: (_, { slots }) => () => Vue.h('section', slots.default?.()) }
  const table = { props: ['columns', 'rows'], setup: (props, { slots }) => () => Vue.h('table', props.rows.map(row => Vue.h('tr', { 'data-task-id': row.gradeTaskId }, props.columns.map(column => Vue.h('td', slots['cell-' + column.key]?.({ row }) || row[column.key]))))) }
  definition.created = undefined
  definition.data = () => ({ ...baseData, tasks: rows, taskTotal: rows.length })
  definition.components = Object.fromEntries(Object.keys(definition.components).map(name => [name, wrapper]))
  definition.components.DataTable = table
  definition.components.AcademicObjectResponsibility = loadComponent('AcademicObjectResponsibility')
  definition.render = new Function('Vue', compile(source.match(/<template>([\s\S]*?)<\/template>\s*<script>/)[1], { mode: 'function', prefixIdentifiers: true }).code)(Vue)
  const html = await render(definition, { ctx: { currentRole: {}, dataScope: {} } })
  const first = html.match(/<tr data-task-id="9007199254740993">([\s\S]*?)<\/tr>/)[1]
  const second = html.match(/<tr data-task-id="9007199254740995">([\s\S]*?)<\/tr>/)[1]
  assert.match(first, /公共教学部.*英语课程学院审核/)
  assert.doesNotMatch(first, /机电学院/)
  assert.match(second, /机电学院.*机电课程教师提交/)
  assert.doesNotMatch(second, /公共教学部/)
})


test('selection detail failures release loading, preserve an error and do not revive list responsibility', async () => {
  for (const getBatch of [async () => { throw Error('连接中断，请重试') }, async () => ({ code: 0, data: { batchId: 'other', responsibility } })]) {
    const { state } = page('AaSelectionConsoleView', { ...context, isDeniedResult, academicAffairsSelectionApi: { getBatch } }, { ctx: {} })
    await state.select({ batchId: '9007199254740993', responsibility })
    assert.equal(state.detailLoading, false)
    assert.ok(state.detailError)
    assert.equal(state.current.responsibility, null)
  }
})
