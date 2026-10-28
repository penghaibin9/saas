import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { page, deferred } from './academic-pc-parallel-b-harness.mjs'
import { COURSE_CATEGORY, COURSE_NATURE, REVIEW_STATUS, canPublishBind } from '../src/modules/academicAffairs/constants/course-program.js'

const context = { currentRole: {}, dataScope: {}, permissionPatterns: ['manage'] }
const dependencies = { COURSE_CATEGORY, COURSE_NATURE, REVIEW_STATUS, canPublishBind, matchPermission: patterns => patterns.includes('manage') }

test('正式方案在发布和变更页不倒退，未知或停用状态不猜流程进度', () => {
  const { state } = page('AaProgramConsoleView', dependencies, { ctx: context })
  state.rows = [{ programId: '9', status: 'ENABLED' }]
  for (const tab of ['review', 'publish', 'changeStatus']) {
    state.tab = tab
    assert.equal(state.workflowStages[state.workflowStageIndex], '已启用')
  }
  for (const [status, label] of Object.entries({ COLLEGE_REVIEW: '学院审核', ACADEMIC_REVIEW: '教务审核', PUBLISHED: '已发布' })) {
    state.rows[0].status = status
    assert.equal(state.workflowStages[state.workflowStageIndex], label)
  }
  for (const status of ['FROZEN', 'DISABLED', 'UNKNOWN']) {
    state.rows[0].status = status
    assert.equal(state.workflowStageIndex, -1)
  }
})

test('适用范围带入原方案年级，非法状态和无权限不能打开绑定', () => {
  const { state } = page('AaProgramConsoleView', dependencies, { ctx: context })
  const row = { programId: '9', majorId: '17', gradeYear: '2026', status: 'ENABLED' }
  state.openBind(row)
  assert.equal(state.bindRow, row)
  assert.equal(state.bindForm.gradeYear, '2026')
  assert.equal(state.bindForm.classId, '')
  state.bindVisible = false
  state.openBind({ ...row, status: 'DRAFT' })
  assert.equal(state.bindVisible, false)
  state.ctx = { ...context, permissionPatterns: [] }
  state.openBind(row)
  assert.equal(state.bindVisible, false)
})

test('学分展示只采用正式校验阻断，不自行把选修课程合计大于毕业要求判成失败', () => {
  const { state } = page('AaProgramConsoleView', dependencies, { ctx: context })
  state.rows = [{ programId: '9', totalCredits: 140, status: 'ENABLED' }]
  state.workflowEvidence = { courseCreditSum: 186, courseCount: 37, issues: [] }
  assert.equal(state.evidenceCards.find(card => card.title === '学分学时').tone, 'success')
  state.workflowEvidence.issues = [{ level: 'BLOCKER', fieldPath: 'credit', message: '课程学分未设置' }]
  const card = state.evidenceCards.find(card => card.title === '学分学时')
  assert.equal(card.tone, 'danger')
  assert.equal(card.detail, '课程学分未设置')
})

test('课程筛选发送到分页接口，深链恢复筛选和页码', async () => {
  const requests = []
  const { state } = page('AaCourseListView', { ...dependencies, academicAffairsApi: { getCourses: async params => { requests.push(params); return { code: 0, data: { list: [], total: 0 } } } } }, {
    ctx: context, $route: { query: { keyword: '计算机', category: 'MAJOR_CORE', nature: 'REQUIRED', status: 'DRAFT', page: '3' } }
  })
  state.restoreQuery()
  await state.load()
  assert.equal(requests[0].keyword, '计算机')
  assert.equal(requests[0].category, 'MAJOR_CORE')
  assert.equal(requests[0].nature, 'REQUIRED')
  assert.equal(requests[0].status, 'DRAFT')
  assert.equal(requests[0].page, 3)
  assert.equal(state.hasFilters, true)
  state.$route.query = {}
  state.restoreQuery()
  assert.equal(state.hasFilters, false)
  state.$route.query.page = '-3'
  state.restoreQuery()
  assert.equal(state.pagination.page, 1)
})

test('列表草稿直达编辑并保留来源，正式或只读课程仍进入详情', () => {
  const calls = []
  const { state } = page('AaCourseListView', dependencies, { ctx: context, $route: { query: {}, fullPath: '/admin/academic-affairs/courses?status=DRAFT&page=3' }, $router: { push: value => calls.push(value) } })
  state.openCourse({ courseId: '9007199254740993', status: 'DRAFT' })
  assert.equal(calls[0].path, '/admin/academic-affairs/courses/9007199254740993/edit')
  assert.equal(calls[0].query.returnTo, state.$route.fullPath)
  state.openCourse({ courseId: '9', status: 'ENABLED' })
  assert.equal(calls[1].path, '/admin/academic-affairs/courses/9')
  state.ctx = { ...context, permissionPatterns: [] }
  state.openCourse({ courseId: '9', status: 'DRAFT' })
  assert.equal(calls[2].path, '/admin/academic-affairs/courses/9')
})

test('载入有简介的课程保持干净，修改任意字段才保护，还原后恢复干净', async () => {
  const { state } = page('AaCourseFormView', { ...dependencies, academicAffairsApi: { getCourse: async () => ({ code: 0, data: { courseCode: 'CS101', courseName: '课程', description: '原有简介', prerequisiteCodes: ['CS100'], applicableMajors: ['17'], status: 'DRAFT' } }) } }, { ctx: context, $route: { params: { id: '9' }, query: {} } })
  await state.resetCourseContext()
  assert.equal(state.hasChanges, false)
  state.form.courseName = '改后名称'
  assert.equal(state.hasChanges, true)
  state.form.courseName = '课程'
  assert.equal(state.hasChanges, false)
  state.prereqText = 'CS102'
  assert.equal(state.hasChanges, true)
  state.saveCompleted = true
  assert.equal(state.hasChanges, false)
})

test('公共工作区尊重表单明确状态，保存中禁止离开，其他旧表单保留保护', async () => {
  const source = readFileSync(new URL('../src/components/workspace/TeacherWorkspaceFrame.vue', import.meta.url), 'utf8')
  const guard = source.slice(source.indexOf('async function confirmUnsubmitted('), source.indexOf('\nonBeforeRouteLeave(confirmUnsubmitted)'))
  let status = 'clean', confirmations = 0
  const document = { querySelector: () => status ? { getAttribute: () => status } : null, querySelectorAll: () => [{ value: '已有内容', getClientRects: () => [1] }] }
  const run = new Function('document', 'window', 'props', 'systemConfirm', `${guard}; return confirmUnsubmitted`) (document, {}, { activeCenter: 'other' }, async () => { confirmations++; return false })
  const to = { path: '/list' }, from = { path: '/edit' }
  assert.equal(await run(to, from), true)
  assert.equal(confirmations, 0)
  status = 'dirty'
  assert.equal(await run(to, from), false)
  assert.equal(confirmations, 1)
  status = 'busy'
  assert.equal(await run(to, from), false)
  assert.equal(confirmations, 1)
  status = ''
  assert.equal(await run(to, from), false)
  assert.equal(confirmations, 2)
  status = 'dirty'
  assert.equal(await run({ path: '/edit', fullPath: '/edit?tab=other' }, from), false)
  assert.equal(confirmations, 3)
})

test('学分读取后无需保存，修改后保存失败保留条目，再试成功后恢复干净', async () => {
  let failing = true, writes = 0
  const { state } = page('AaProgramConsoleView', { ...dependencies, canSubmit: s => s === 'DRAFT', academicAffairsApi: {
    getCreditRequirements: async () => ({ code: 0, data: { items: [{ module: '公共基础', creditTarget: 10, note: '' }] } }),
    saveCreditRequirements: async () => { writes++; if (failing) throw Error('断网'); return { code: 0, data: { targetSum: 12 } } }
  } }, { ctx: context })
  state.tab = 'creditRequirements'; state.loading = false
  state.selectedProgramId = '9'; state.selectedProgram = { status: 'DRAFT' }
  await state.loadCreditRequirements()
  assert.equal(state.creditDirty, false)
  await state.saveCredit(); assert.equal(writes, 0)
  state.openCreditForm(state.creditItems[0])
  state.creditForm.creditTarget = 12
  assert.equal(state.creditDirty, true)
  state.submitCreditRow()
  await state.saveCredit()
  assert.equal(state.savingCredit, false)
  assert.equal(state.creditDirty, true)
  assert.equal(state.creditItems[0].creditTarget, 12)
  assert.match(state.creditSaveError, /保留修改/)
  assert.equal(state.error, '')
  failing = false
  await state.saveCredit()
  assert.equal(state.creditDirty, false)
  assert.equal(state.creditSaveError, '')
})

test('学分保存中不重复提交或修改条目，切换对象后的迟到回执不能确认新对象', async () => {
  const pending = deferred(); let writes = 0
  const { state } = page('AaProgramConsoleView', { ...dependencies, canSubmit: s => s === 'DRAFT', academicAffairsApi: { saveCreditRequirements: async () => { writes++; return pending.promise } } }, { ctx: context })
  state.tab = 'creditRequirements'; state.loading = false; state.selectedProgramId = '9'; state.selectedProgram = { status: 'DRAFT' }
  state.creditBaseline = '[]'; state.creditItems = [{ module: '公共基础', creditTarget: 10 }]
  const saving = state.saveCredit()
  await state.saveCredit()
  state.removeCreditRow(state.creditItems[0])
  assert.equal(writes, 1); assert.equal(state.creditItems.length, 1)
  state.selectedProgramId = '10'
  pending.resolve({ code: 0, data: { targetSum: 10 } })
  await saving
  assert.equal(state.creditBaseline, '[]')
  assert.equal(state.creditDirty, true)
})

test('选另一个方案先等待路由确认，不提前覆盖当前未保存学分', async () => {
  const calls = []
  const { state } = page('AaProgramConsoleView', dependencies, { ctx: context, $router: { replace: async value => { calls.push(value); return false } } })
  state.selectedProgramId = '9'; state.creditBaseline = '[]'; state.creditItems = [{ module: '公共基础', creditTarget: 10 }]
  await state.onProgramPicked('10')
  assert.equal(calls[0].query.programId, '10')
  assert.equal(state.selectedProgramId, '9')
  assert.equal(state.creditDirty, true)
})

test('方案入口说明下一步，审核中直达审核区并携带原筛选', () => {
  const calls = []
  const { state } = page('AaProgramListView', dependencies, { ctx: context, $route: { query: { keyword: '软件', page: '2' }, fullPath: '/admin/academic-affairs/programs?keyword=软件&page=2' }, $router: { push: value => calls.push(value) } })
  state.restoreQuery()
  assert.equal(state.pagination.page, 2)
  assert.equal(state.keyword, '软件')
  assert.equal(state.programActionLabel({ status: 'DRAFT' }), '继续编制')
  assert.equal(state.programActionLabel({ status: 'RETURNED' }), '按意见修改')
  state.openProgram({ programId: '19', status: 'COLLEGE_REVIEW' })
  assert.equal(calls[0].query.step, 'review')
  assert.equal(calls[0].query.returnTo, state.$route.fullPath)
  state.ctx = { ...context, permissionPatterns: [] }
  assert.equal(state.programActionLabel({ status: 'DRAFT' }), '查看方案')
})

test('方案队列用服务端分页，指定对象不在首页时精确读取，不误开首条', async () => {
  const requests = []
  const { state } = page('AaProgramConsoleView', { ...dependencies, academicAffairsApi: {
    getPrograms: async args => { requests.push(args); return { code: 0, data: { total: 131, list: [{ programId: '1', status: 'ENABLED' }] } } },
    getProgram: async id => ({ code: 0, data: { programId: id, status: 'ENABLED' } })
  } }, { ctx: context, $route: { query: { programId: '129' } } })
  state.tab = 'publish'; state.workflowPage = 4
  state.loadWorkflowEvidence = async () => {}
  await state.loadPublish()
  assert.equal(requests[0].page, 4)
  assert.equal(requests[0].pageSize, 20)
  assert.equal(state.workflowTotal, 131)
  assert.equal(state.activeProgramId, '129')
})

test('指定方案无权读取时保留错误，不用另一方案替代；旧队列响应不覆盖新页签', async () => {
  const pending = deferred()
  let delayed = false
  const { state } = page('AaProgramConsoleView', { ...dependencies, academicAffairsApi: {
    getPrograms: async () => delayed ? pending.promise : { code: 0, data: { total: 1, list: [{ programId: '1', status: 'ENABLED' }] } },
    getProgram: async () => ({ code: 403 })
  } }, { ctx: context, $route: { query: { programId: '99' } } })
  state.tab = 'publish'
  await state.loadPublish()
  assert.match(state.error, /指定方案/)
  assert.equal(state.rows.length, 0)
  delayed = true
  const loading = state.loadPublish()
  state.tab = 'review'
  state.rows = [{ programId: 'new' }]
  pending.resolve({ code: 0, data: { total: 1, list: [{ programId: 'old' }] } })
  await loading
  assert.equal(state.rows[0].programId, 'new')
})
