import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import test from 'node:test'

function mount(name, studentApi, confirm = async () => ({ confirm: true })) {
  // 旧用例只关心“本人记录”的处理结果，未重复填写分页元数据。页面改为严格
  // 服务端分页后，测试夹具统一补齐一个单页正式响应；专门分页用例仍传入完整元数据。
  if (name === 'recognition' && typeof studentApi?.getMyRecognition === 'function') {
    const readRecognition = studentApi.getMyRecognition
    studentApi = {
      ...studentApi,
      getMyRecognition: async (params = {}) => {
        const data = await readRecognition(params)
        const items = Array.isArray(data?.items) ? data.items : []
        const page = Number.isSafeInteger(data?.page) ? data.page : Number(params.page || 1)
        const pageSize = Number.isSafeInteger(data?.pageSize) ? data.pageSize : Number(params.pageSize || 20)
        const total = Number.isSafeInteger(data?.total) ? data.total : items.length
        const hasMore = typeof data?.hasMore === 'boolean' ? data.hasMore : false
        return { ...data, items, page, pageSize, total, hasMore }
      }
    }
  }
  if (name === 'level-exam' && typeof studentApi?.getMyLevelExam === 'function') {
    const readLevelExam = studentApi.getMyLevelExam
    studentApi = {
      ...studentApi,
      getMyLevelExam: async (params = {}) => {
        const data = await readLevelExam(params)
        const openExams = Array.isArray(data?.openExams) ? data.openExams : []
        const myRegs = Array.isArray(data?.myRegs) ? data.myRegs : []
        const openPage = Number.isSafeInteger(data?.openPagination?.page) ? data.openPagination.page : Number(params.openPage || 1)
        const openPageSize = Number.isSafeInteger(data?.openPagination?.pageSize) ? data.openPagination.pageSize : Number(params.openPageSize || 20)
        const openTotal = Number.isSafeInteger(data?.openPagination?.total) ? data.openPagination.total : openExams.length
        const registrationPage = Number.isSafeInteger(data?.registrationPagination?.page) ? data.registrationPagination.page : Number(params.registrationPage || 1)
        const registrationPageSize = Number.isSafeInteger(data?.registrationPagination?.pageSize) ? data.registrationPagination.pageSize : Number(params.registrationPageSize || 20)
        const registrationTotal = Number.isSafeInteger(data?.registrationPagination?.total) ? data.registrationPagination.total : myRegs.length
        return {
          ...data,
          openExams,
          myRegs,
          openPagination: {
            page: openPage, pageSize: openPageSize, total: openTotal,
            hasMore: typeof data?.openPagination?.hasMore === 'boolean' ? data.openPagination.hasMore : false
          },
          registrationPagination: {
            page: registrationPage, pageSize: registrationPageSize, total: registrationTotal,
            hasMore: typeof data?.registrationPagination?.hasMore === 'boolean' ? data.registrationPagination.hasMore : false
          }
        }
      }
    }
  }
  if (name === 'major-split' && typeof studentApi?.getMyMajorSplit === 'function') {
    const readMajorSplit = studentApi.getMyMajorSplit
    studentApi = {
      ...studentApi,
      getMyMajorSplit: async (params = {}) => {
        const data = await readMajorSplit(params)
        const openBatches = Array.isArray(data?.openBatches) ? data.openBatches : []
        const myVolunteers = Array.isArray(data?.myVolunteers) ? data.myVolunteers : []
        const openPage = Number.isSafeInteger(data?.openPagination?.page) ? data.openPagination.page : Number(params.openPage || 1)
        const openPageSize = Number.isSafeInteger(data?.openPagination?.pageSize) ? data.openPagination.pageSize : Number(params.openPageSize || 20)
        const openTotal = Number.isSafeInteger(data?.openPagination?.total) ? data.openPagination.total : openBatches.length
        const volunteerPage = Number.isSafeInteger(data?.volunteerPagination?.page) ? data.volunteerPagination.page : Number(params.volunteerPage || 1)
        const volunteerPageSize = Number.isSafeInteger(data?.volunteerPagination?.pageSize) ? data.volunteerPagination.pageSize : Number(params.volunteerPageSize || 20)
        const volunteerTotal = Number.isSafeInteger(data?.volunteerPagination?.total) ? data.volunteerPagination.total : myVolunteers.length
        return {
          ...data, openBatches, myVolunteers,
          openPagination: { page: openPage, pageSize: openPageSize, total: openTotal, hasMore: typeof data?.openPagination?.hasMore === 'boolean' ? data.openPagination.hasMore : false },
          volunteerPagination: { page: volunteerPage, pageSize: volunteerPageSize, total: volunteerTotal, hasMore: typeof data?.volunteerPagination?.hasMore === 'boolean' ? data.volunteerPagination.hasMore : false }
        }
      }
    }
  }
  if (name === 'evaluation' && typeof studentApi?.getMyEvaluationTasks === 'function') {
    const readEvaluation = studentApi.getMyEvaluationTasks
    studentApi = {
      ...studentApi,
      getMyEvaluationTasks: async (params = {}) => {
        const data = await readEvaluation(params)
        const list = Array.isArray(data?.list) ? data.list : []
        const page = Number.isSafeInteger(data?.pagination?.page) ? data.pagination.page : Number(params.page || 1)
        const pageSize = Number.isSafeInteger(data?.pagination?.pageSize) ? data.pagination.pageSize : Number(params.pageSize || 20)
        const total = Number.isSafeInteger(data?.pagination?.total) ? data.pagination.total : list.length
        const hasMore = typeof data?.pagination?.hasMore === 'boolean' ? data.pagination.hasMore : false
        return { ...data, list, pagination: { page, pageSize, total, hasMore } }
      }
    }
  }
  if (name === 'registration' && typeof studentApi?.getMyRegistration === 'function') {
    const readRegistration = studentApi.getMyRegistration
    studentApi = {
      ...studentApi,
      getMyRegistration: async (params = {}) => {
        const data = await readRegistration(params)
        const batches = Array.isArray(data?.batches) ? data.batches : []
        const page = Number.isSafeInteger(data?.page) ? data.page : Number(params.page || 1)
        const pageSize = Number.isSafeInteger(data?.pageSize) ? data.pageSize : Number(params.pageSize || 20)
        const total = Number.isSafeInteger(data?.total) ? data.total : batches.length
        const hasMore = typeof data?.hasMore === 'boolean' ? data.hasMore : false
        return { ...data, batches, page, pageSize, total, hasMore }
      }
    }
  }
  const directory = new URL('../src/pages/student/academic-affairs/', import.meta.url)
  const session = { generation: 1 }
  const storage = new Map()
  let identityGeneration = session.generation
  const persistIdentity = () => storage.set('gx_session_v1', JSON.stringify({ logged: true, currentRole: 'student', identity: { tenantId: 'tenant-1', userId: 'user-' + identityGeneration, roleCode: 'STUDENT', activeContextId: 'student-' + identityGeneration, studentId: 'student-' + identityGeneration } }))
  persistIdentity()
  const currentSessionGeneration = () => {
    if (identityGeneration !== session.generation) { identityGeneration = session.generation; persistIdentity() }
    return session.generation
  }
  const uni = { getStorageSync: key => storage.get(key) || '', setStorageSync: (key, value) => storage.set(key, value), removeStorageSync: key => storage.delete(key) }
  const context = vm.createContext({ studentApi, uni, currentSessionGeneration,
    modalConfirm: confirm, isUncertainWriteError: e => !e?.biz, createSubmitLock: () => ({ run: fn => fn() }),
    AcademicPageNav: {}, AcademicPageState: {}, AcademicMaterials: {}, MobileAcademicDecisionCard: {}, safeToast() {}, toast() {}, go() {}, clampPercent: n => Math.max(0, Math.min(100, n)) })
  for (const helper of ['pending-ledger.js', 'read-page.js', 'application-page.js']) {
    const source = readFileSync(new URL(helper, directory), 'utf8').replace(/^import .*$/gm, '').replace(/export (const|function) /g, '$1 ')
    vm.runInContext(source, context)
  }
  const source = readFileSync(new URL(`${name}.vue`, directory), 'utf8').match(/<script>([\s\S]*?)<\/script>/)[1]
    .replace(/^import .*$/gm, '').replace('export default', 'component =')
  vm.runInContext(source, context)
  const layers = []
  function collect(component) { for (const mixin of component.mixins || []) collect(mixin); layers.push(component) }
  collect(context.component)
  const reopen = () => {
    const page = {}
    for (const layer of layers) Object.assign(page, layer.data?.call(page) || {})
    for (const layer of layers) for (const [key, fn] of Object.entries(layer.methods || {})) page[key] = fn.bind(page)
    for (const layer of layers) for (const [key, fn] of Object.entries(layer.computed || {})) Object.defineProperty(page, key, { get: () => fn.call(page) })
    layers.forEach(layer => layer.created?.call(page))
    return page
  }
  const page = reopen()
  return { page, session, storage, reopen, hook: (name, ...args) => layers.forEach(layer => layer[name]?.call(page, ...args)), ledger: vm.runInContext('({ canUpdatePendingCommand, createPendingCommand, readPending, savePending })', context) }
}

const allowRecognition = (page, courseId = '1000000000000063602', courseName = '电工技术') => {
  page.courseOptions = [{ courseId, courseCode: 'KC-01', courseName, version: '2026版' }]
}

for (const alias of ['id', 'deferId', 'recordId']) {
  test(`缓考深链 ${alias} 服务端精确读取历史对象，并可返回全部申请`, async () => {
    const calls = []
    const { page, hook } = mount('exam', {
      getMyExamSchedule: async () => ({ items: [], page: 1, pageSize: 20, total: 0, hasMore: false }),
      getMyDeferOptions: async () => ({ items: [] }),
      getMyDeferrals: async params => {
        calls.push(JSON.parse(JSON.stringify(params)))
        return { items: [{ deferId: params.deferId || 'latest', status: 'RETURNED' }], page: params.page, pageSize: 20, total: 1, hasMore: false }
      }
    })
    hook('onLoad', { [alias]: '1000000000000000009' })
    // Await the page's asynchronous onLoad read, without timers or a fake business result.
    for (let i = 0; i < 12 && page.state === 'loading'; i++) await Promise.resolve()
    assert.equal(page.state, 'ready')
    assert.equal(page.d.deferrals[0].deferId, '1000000000000000009')
    assert.deepEqual(calls, [{ page: 1, pageSize: 20, deferId: '1000000000000000009' }])
    await page.showAllDeferrals()
    assert.equal(page.targetId, '')
    assert.deepEqual(calls[1], { page: 1, pageSize: 20 })
    assert.equal(page.d.deferrals[0].deferId, 'latest')
  })
}

test('returned and excluded textbooks remain readable without a new receipt action', async () => {
  const { page } = mount('textbook', { getMyTextbook: async () => ({ distributions: [], fees: {} }) })
  assert.equal(page.statusText('RETURNED'), '已退领')
  assert.equal(page.statusText('EXCLUDED'), '当前不发放')
  for (const status of ['RETURNED', 'EXCLUDED', 'RECEIVED', 'UNKNOWN']) assert.equal(page.canSign({ status }), false)
})

test('textbook keeps distribution and fee pages on the server', async () => {
  const calls = []
  const { page } = mount('textbook', {
    getMyTextbook: async params => {
      const request = JSON.parse(JSON.stringify(params))
      calls.push(request)
      return {
        distributions: [{ recordId: 'd-' + request.distributionPage, textbookName: '教材', status: 'PENDING' }],
        distributionPagination: { total: 23, page: request.distributionPage, pageSize: 20, hasMore: request.distributionPage < 2 },
        fees: { items: [{ feeId: 'f-' + request.feePage, textbookName: '教材', amount: 10, paidAmount: 0, status: 'UNPAID' }], total: 22, page: request.feePage, pageSize: 20, hasMore: request.feePage < 2, totalDue: 220, totalPaid: 0, unpaid: 220 }
      }
    }
  })
  await page.load()
  await page.changeDistributionPage(2)
  await page.changeFeePage(2)
  assert.deepEqual(calls, [
    { distributionPage: 1, distributionPageSize: 20, feePage: 1, feePageSize: 20 },
    { distributionPage: 2, distributionPageSize: 20, feePage: 1, feePageSize: 20 },
    { distributionPage: 2, distributionPageSize: 20, feePage: 2, feePageSize: 20 }
  ])
  assert.equal(page.d.distributions[0].recordId, 'd-2')
  assert.equal(page.d.fees.items[0].feeId, 'f-2')
})

test('status history requests bounded server pages and keeps returned records actionable', async () => {
  const calls = []
  const { page } = mount('status', {
    getMyAcadStatus: async params => {
      calls.push(JSON.parse(JSON.stringify(params)))
      const current = Number(params.page)
      return {
        studentStatus: 'REGISTERED', enrolled: true,
        changes: current === 2
          ? [{ changeId: '21', changeType: 'SUSPEND', status: 'RETURNED', reason: '补充正式材料', version: 7, decisionVersion: 3 }]
          : Array.from({ length: 20 }, (_, index) => ({ changeId: String(index + 1), changeType: 'SUSPEND', status: 'SUBMITTED' })),
        page: current, pageSize: params.pageSize, total: 21, hasMore: current < 2
      }
    }
  })
  await page.load()
  await page.nextPage()
  assert.deepEqual(calls, [{ page: 1, pageSize: 20 }, { page: 2, pageSize: 20 }])
  assert.equal(page.data.changes.length, 1)
  assert.equal(page.data.changes[0].changeId, '21')
  assert.equal(page.resubmitReasons['21'], '补充正式材料')
  assert.equal(page.page, 2)
  assert.equal(page.pageCount, 2)
})

test('status transfer candidates stay server-paged, searchable, and scoped to the selected major', async () => {
  const calls = []
  const { page } = mount('status', {
    getMyAcadStatus: async params => ({
      studentStatus: 'REGISTERED', enrolled: true, changes: [],
      page: params.page, pageSize: params.pageSize, total: 0, hasMore: false
    }),
    getTransferOptions: async params => {
      calls.push(JSON.parse(JSON.stringify(params)))
      if (params.target === 'major') {
        const second = Number(params.page) === 2
        return {
          target: 'major', majorId: '', currentMajorId: 'own-major', currentClassId: 'own-class',
          items: second
            ? [{ majorId: 'm-21', majorName: '第二页专业', collegeName: '商贸学院' }]
            : [{ majorId: 'm-1', majorName: '第一页专业', collegeName: '信息学院' }],
          page: Number(params.page), pageSize: Number(params.pageSize), total: 21, hasMore: !second
        }
      }
      return {
        target: 'class', majorId: params.majorId || 'own-major', currentMajorId: 'own-major', currentClassId: 'own-class',
        items: [{ classId: `c-${params.majorId || 'own'}`, className: '目标班', grade: '2026', majorId: params.majorId || 'own-major' }],
        page: Number(params.page), pageSize: Number(params.pageSize), total: 1, hasMore: false
      }
    }
  })

  await page.onType('TRANSFER_MAJOR')
  assert.deepEqual(calls[0], { target: 'major', page: 1, pageSize: 20, keyword: '' })
  await page.onMajorPick({ detail: { value: 0 } })
  assert.deepEqual(calls[1], { target: 'class', page: 1, pageSize: 20, majorId: 'm-1', keyword: '' })
  assert.equal(page.form.toMajorId, 'm-1')
  assert.equal(page.form.toClassId, '')

  page.majorKeyword = '第二页'
  await page.searchMajorOptions()
  assert.deepEqual(calls[2], { target: 'major', page: 1, pageSize: 20, keyword: '第二页' })
  await page.nextMajorPage()
  assert.deepEqual(calls[3], { target: 'major', page: 2, pageSize: 20, keyword: '第二页' })
  assert.equal(page.form.toMajorId, 'm-1', '翻页或搜索不得错配既选专业')
  assert.equal(page.selectedMajorText, '信息学院 · 第一页专业')

  await page.onType('TRANSFER_CLASS')
  assert.deepEqual(calls[4], { target: 'class', page: 1, pageSize: 20, keyword: '' })
  assert.equal(page.sameMajorClasses[0].majorId, 'own-major')
})

test('status ignores a late transfer-candidate response after the student identity changes', async () => {
  let finish
  const delayed = new Promise(resolve => { finish = resolve })
  const { page, session } = mount('status', {
    getMyAcadStatus: async params => ({
      studentStatus: 'REGISTERED', enrolled: true, changes: [],
      page: params.page, pageSize: params.pageSize, total: 0, hasMore: false
    }),
    getTransferOptions: async () => delayed
  })
  page.form.changeType = 'TRANSFER_MAJOR'
  const pending = page.loadMajorOptions(1)
  session.generation += 1
  page.resetAcademicContext()
  finish({
    target: 'major', majorId: '', currentMajorId: 'old-major', currentClassId: 'old-class',
    items: [{ majorId: 'old-target', majorName: '旧账号专业', collegeName: '旧学院' }],
    page: 1, pageSize: 20, total: 1, hasMore: false
  })
  await pending
  assert.equal(page.majors.length, 0)
  assert.equal(page.optionsLoading, false)
})

test('clearance history requests bounded server pages rather than slicing a full result', async () => {
  const calls = []
  const { page } = mount('clearance', {
    getMyClearance: async params => {
      calls.push(JSON.parse(JSON.stringify(params)))
      const current = Number(params.page)
      return {
        note: '清考结果以学校发布为准。',
        items: current === 2
          ? [{ recordId: '21', courseName: '课程二十一', status: 'PENDING_EXAM' }]
          : Array.from({ length: 20 }, (_, index) => ({ recordId: String(index + 1), courseName: '课程', status: 'PENDING_EXAM' })),
        page: current, pageSize: params.pageSize, total: 21, hasMore: current < 2
      }
    }
  })
  await page.load()
  await page.nextPage()
  assert.deepEqual(calls, [{ page: 1, pageSize: 20 }, { page: 2, pageSize: 20 }])
  assert.equal(page.d.items.length, 1)
  assert.equal(page.d.items[0].recordId, '21')
  assert.match(page.clearanceCoverageText, /第 2\/2 页，本页 1 条，共 21 条/)
})

test('recognition history requests bounded server pages rather than slicing a full result', async () => {
  const calls = []
  const { page } = mount('recognition', {
    getMyRecognition: async params => {
      calls.push(JSON.parse(JSON.stringify(params)))
      const current = Number(params.page)
      return {
        items: current === 2
          ? [{ recognitionId: '21', sourceCourseName: '课程二十一', targetCourseName: '目标课程', status: 'REJECTED', reviewReason: '请补充材料' }]
          : Array.from({ length: 20 }, (_, index) => ({ recognitionId: String(index + 1), sourceCourseName: '课程', targetCourseName: '目标课程', status: 'SUBMITTED' })),
        page: current, pageSize: params.pageSize, total: 21, hasMore: current < 2
      }
    }
  })
  await page.load()
  await page.nextPage()
  assert.deepEqual(calls, [{ page: 1, pageSize: 20 }, { page: 2, pageSize: 20 }])
  assert.equal(page.d.items.length, 1)
  assert.equal(page.d.items[0].recognitionId, '21')
  assert.equal(page.historyPage, 2)
  assert.equal(page.historyPageCount, 2)
})

test('level exam independently requests bounded pages for open exams and personal registrations', async () => {
  const calls = []
  const { page } = mount('level-exam', {
    getMyLevelExam: async params => {
      calls.push(JSON.parse(JSON.stringify(params)))
      const openPage = Number(params.openPage)
      const registrationPage = Number(params.registrationPage)
      return {
        openExams: [{ examId: `open-${openPage}`, examName: `开放考试${openPage}`, registrationStatus: null }],
        openPagination: { page: openPage, pageSize: params.openPageSize, total: 21, hasMore: openPage < 2 },
        myRegs: [{ regId: `reg-${registrationPage}`, examId: `history-${registrationPage}`, examName: `历史考试${registrationPage}`, status: 'SCORED', examStatus: 'FINISHED' }],
        registrationPagination: { page: registrationPage, pageSize: params.registrationPageSize, total: 21, hasMore: registrationPage < 2 }
      }
    }
  })
  await page.load()
  await page.nextOpenPage()
  await page.nextRegistrationPage()
  assert.deepEqual(calls, [
    { openPage: 1, openPageSize: 20, registrationPage: 1, registrationPageSize: 20 },
    { openPage: 2, openPageSize: 20, registrationPage: 1, registrationPageSize: 20 },
    { openPage: 2, openPageSize: 20, registrationPage: 2, registrationPageSize: 20 }
  ])
  assert.equal(page.openPage, 2)
  assert.equal(page.registrationPage, 2)
  assert.equal(page.examName(page.d.myRegs[0]), '历史考试2')
})

test('attendance sends formal teaching-task filtering and paging to the server', async () => {
  const calls = []
  const { page } = mount('attendance', {
    getMyAttendance: async params => {
      calls.push(JSON.parse(JSON.stringify(params)))
      return {
        items: [{ sessionId: 's-' + params.page, courseName: params.course || '全部课程', status: 'PRESENT' }],
        summary: { PRESENT: 21, LATE: 0, ABSENT: 0, LEAVE: 0, OTHER: 0 },
        total: 21, page: params.page, pageSize: params.pageSize, hasMore: params.page < 2
      }
    }
  })
  await page.load()
  page.courseFilter = '电工'
  page.teachingTaskId = '101'
  await page.load(1)
  await page.changePage(2)
  await page.clearCourseFilter()
  assert.deepEqual(calls, [
    { page: 1, pageSize: 20 },
    { course: '电工', teachingTaskId: '101', page: 1, pageSize: 20 },
    { course: '电工', teachingTaskId: '101', page: 2, pageSize: 20 },
    { page: 1, pageSize: 20 }
  ])
  assert.equal(page.d.items[0].courseName, '全部课程')
})

test('recognition preserves draft after timeout and empty readback, and blocks a repeated command', async () => {
  let writes = 0
  const { page } = mount('recognition', { getMyRecognition: async () => ({ items: [] }), submitRecognition: async () => { writes++; throw Error('timeout') } })
  await page.load()
  Object.assign(page.form, { sourceCourseName: '电工基础', targetCourseName: '电工技术', targetCourseId: '1000000000000063602', sourceScore: '80' })
  allowRecognition(page)
  await page.submit(); await page.submit()
  assert.equal(writes, 1)
  assert.ok(page.pendingApplication)
  assert.match(page.applicationNotice, /结果待核实/)
  assert.equal(page.form.sourceCourseName, '电工基础')
})

test('recognition only clears form after its receipt and matching official record are read', async () => {
  let saved = false
  const record = { recognitionId: '2', sourceCourseName: '电工基础', targetCourseName: '电工技术', targetCourseId: '1000000000000063602', sourceScore: 80, status: 'SUBMITTED' }
  const { page } = mount('recognition', { getMyRecognition: async () => ({ items: saved ? [record] : [] }), submitRecognition: async () => { saved = true; return { recognitionId: '2' } } })
  await page.load(); Object.assign(page.form, { sourceCourseName: record.sourceCourseName, targetCourseName: record.targetCourseName, targetCourseId: record.targetCourseId, sourceScore: '80' })
  allowRecognition(page)
  await page.submit()
  assert.equal(page.pendingApplication, null)
  assert.equal(page.form.sourceCourseName, '')
  assert.match(page.applicationNotice, /已核对学校受理记录/)
})

test('recognition keeps a matching new record pending when this command has no receipt', async () => {
  let saved = false, writes = 0
  const record = { recognitionId: '2', sourceCourseName: '电工基础', targetCourseName: '电工技术', targetCourseId: '1000000000000063602', sourceScore: 80, status: 'SUBMITTED' }
  const { page } = mount('recognition', { getMyRecognition: async () => ({ items: saved ? [record] : [] }), submitRecognition: async () => { writes++; saved = true; return null } })
  await page.load(); Object.assign(page.form, { sourceCourseName: record.sourceCourseName, targetCourseName: record.targetCourseName, targetCourseId: record.targetCourseId, sourceScore: '80' })
  allowRecognition(page); await page.submit(); await page.submit()
  assert.ok(page.pendingApplication)
  assert.equal(writes, 1)
  assert.match(page.applicationNotice, /结果待核实/)
})

test('old recognition record does not count as confirmation of a new command', async () => {
  const record = { recognitionId: '1', sourceCourseName: '电工基础', targetCourseName: '电工技术', targetCourseId: '1000000000000063602', sourceScore: 80 }
  const { page } = mount('recognition', { getMyRecognition: async () => ({ items: [record] }), submitRecognition: async () => null })
  await page.load(); Object.assign(page.form, { ...record, sourceScore: '80' }); allowRecognition(page); await page.submit()
  assert.ok(page.pendingApplication)
})

test('recognition blocks unchecked materials and requires matching attachment readback', async () => {
  let writes = 0, sent
  const record = { recognitionId: '2', sourceCourseName: '电工基础', targetCourseName: '电工技术', targetCourseId: '1000000000000063602', sourceScore: 80, attachmentFileIds: [] }
  const { page } = mount('recognition', { getMyRecognition: async () => ({ items: writes ? [record] : [] }), submitRecognition: async body => { writes++; sent = body; return { recognitionId: '2' } } })
  await page.load(); Object.assign(page.form, { sourceCourseName: record.sourceCourseName, targetCourseName: record.targetCourseName, targetCourseId: record.targetCourseId, sourceScore: '80' })
  allowRecognition(page)
  page.materials = [{ fileId: '41', readyForBusiness: false }]
  await page.submit(); assert.equal(writes, 0)
  page.materials[0].readyForBusiness = true
  await page.submit(); assert.deepEqual(Array.from(sent.attachmentFileIds), ['41']); assert.ok(page.pendingApplication)
  record.attachmentFileIds = ['41']; await page.load()
  assert.equal(page.pendingApplication, null); assert.equal(page.materials.length, 0)
})

test('confirmation after identity switch sends no command; new load clears old application context', async () => {
  let answer, writes = 0
  const { page, session } = mount('recognition', { getMyRecognition: async () => ({ items: [] }), submitRecognition: async () => { writes++ } }, () => new Promise(resolve => { answer = resolve }))
  await page.load(); Object.assign(page.form, { sourceCourseName: '旧课程', targetCourseName: '目标课程', targetCourseId: '1000000000000063602', sourceScore: '80' })
  allowRecognition(page, '1000000000000063602', '目标课程')
  const pending = page.submit(); session.generation++; answer({ confirm: true }); await pending; await page.load()
  assert.equal(writes, 0); assert.equal(page.form.sourceCourseName, ''); assert.equal(page.pendingApplication, null)
})

test('read-only page ignores a late result from a previous identity', async () => {
  let resolve
  const { page, session } = mount('attendance', { getMyAttendance: () => new Promise(done => { resolve = done }) })
  const pending = page.load(); session.generation++; resolve({ items: [{ courseName: '旧身份课程' }], summary: {} }); await pending
  assert.equal(page.d, null)
})

test('malformed read is an error, not an empty successful academic list', async () => {
  const { page } = mount('credits', { getMyCredits: async () => ({ obtainedCredits: 12 }) })
  await page.load(); assert.equal(page.state, 'error'); assert.equal(page.d, null)
})

test('graduation decision content stays an object and hides technical evidence without changing formal status', () => {
  const { page } = mount('graduation', {})
  page.data = { hasAudit: false, overall: 'SYSTEM_PASSED', items: [{ item: 'CREDIT', result: 'PASS', evidence: 'SELECT * FROM student tenantId=7' }], decisionTrace: { availableResolutions: [{ label: 'SQL provider failure' }] }, decisionText: { title: 'provider exception', reason: 'tenantId=7', nextStep: '核对学校通知' } }
  assert.equal(typeof page.safeDecisionText, 'object')
  assert.equal(page.safeDecisionText.nextStep, '核对学校通知')
  assert.doesNotMatch(JSON.stringify(page.safeDecisionText) + JSON.stringify(page.safeDecisionTrace) + page.studentEvidence(page.items[0]), /SQL|tenantId|provider|SELECT/)
  assert.equal(page.formalText, '尚未纳入正式预审')
})

test('calendar month view uses actual date boundaries and only published events', () => {
  const { page } = mount('calendar', {})
  page.year = 2026; page.month = 8
  page.d = { events: [{ eventId: '1', startDate: '2026-09-12', endDate: '2026-09-12' }, { eventId: '2', startDate: '2026-10-01' }] }
  assert.equal(page.monthDays.filter(day => day.date).length, 30)
  assert.equal(page.visibleEvents.length, 1)
  page.selectedDate = '2026-09-11'; assert.equal(page.visibleEvents.length, 0)
  page.changeMonth(1); assert.equal(page.visibleEvents[0].eventId, '2')
})

test('registration sends requestedUntil through the existing adapter and confirms the exact date', async () => {
  const batch = { batchId: 'b', canDefer: true }
  let sent
  const { page } = mount('registration', { getMyRegistration: async () => ({ batches: [batch] }), deferRegistration: async (...args) => { sent = args; batch.deferral = { deferralId: 'd-other', reason: args[1], requestedUntil: '2026-09-19T00:00:00', status: 'PENDING' }; return { deferralId: 'd-1', batchId: 'b' } } })
  await page.load(); page.doDefer(batch); page.deferReason = '因病申请暂缓'
  await page.submitDefer(batch); assert.equal(sent, undefined)
  page.deferUntil = '2026-09-20'; await page.submitDefer(batch)
  assert.deepEqual(sent, ['b', '因病申请暂缓', '2026-09-20']); assert.ok(page.pendingApplication)
  batch.deferral.requestedUntil = '2026-09-20T00:00:00'; await page.load()
  assert.ok(page.pendingApplication)
  batch.deferral.deferralId = 'd-1'; await page.load()
  assert.equal(page.pendingApplication, null)
})

test('unsent recognition draft survives page recreation but never an identity switch', async () => {
  const { page, reopen, hook, session } = mount('recognition', { getMyRecognition: async () => ({ items: [] }) })
  await page.load(); page.form.sourceCourseName = '原课程'; page.showForm = true
  page.materials = [{ fileId: 'f', readyForBusiness: true }]; hook('onHide')
  const resumed = reopen(); await resumed.load()
  assert.equal(resumed.form.sourceCourseName, '原课程'); assert.equal(resumed.showForm, true)
  assert.equal(resumed.materials[0].readyForBusiness, false)
  session.generation++; const other = reopen(); await other.load()
  assert.equal(other.form.sourceCourseName, ''); assert.equal(other.materials.length, 0)
})

test('recheck draft restores by stable grade id after records change their order', async () => {
  const grades = [{ gradeId: 'a', courseName: '甲课', score: 70 }, { gradeId: 'b', courseName: '乙课', score: 60 }]
  const { page, reopen, hook } = mount('recheck', {
    getMyRecheck: async () => ({ items: [], page: 1, pageSize: 20, total: 0, hasMore: false }),
    getMyTranscript: async () => ({ items: grades })
  })
  await page.load(); page.picked = 1; page.reason = '核对平时成绩'; page.showForm = true; hook('onHide')
  grades.reverse(); const resumed = reopen(); await resumed.load()
  assert.equal(resumed.grades[resumed.picked].gradeId, 'b'); assert.equal(resumed.reason, '核对平时成绩')
})

test('403 read is restricted, not empty or a generic transient error', async () => {
  const { page } = mount('credits', { getMyCredits: async () => { throw { httpStatus: 403, code: 403001, biz: true } } })
  await page.load(); assert.equal(page.state, 'forbidden')
})

test('textbook and level registration require the explicit object acknowledgement', async () => {
  let writes = 0
  const book = { recordId: 'r', textbookName: '教材', status: 'PENDING' }
  const { page: textbook } = mount('textbook', { getMyTextbook: async () => ({ distributions: [book], fees: {} }), signTextbook: async () => { writes++ } })
  await textbook.load(); textbook.openSign(book); await textbook.sign(book)
  const exam = { examId: 'e', examName: '普通话' }
  const { page: level } = mount('level-exam', { getMyLevelExam: async () => ({ openExams: [exam], myRegs: [] }), registerLevelExam: async () => { writes++ } })
  await level.load(); level.openDetail(exam); await level.register(exam)
  assert.equal(writes, 0); assert.equal(level.feeText(null), '缴费状态待核对')
})

for (const kind of ['registration', 'textbook', 'evaluation', 'level-exam']) {
  test(`${kind}: successful transport with unchanged readback remains unconfirmed`, async () => {
    const cases = {
      registration: { api: { getMyRegistration: async () => ({ batches: [{ batchId: 'b', canRegister: true, registrationStatus: 'PENDING' }] }), registerSelf: async () => null }, run: page => page.doRegister(page.d.batches[0]) },
      textbook: { api: { getMyTextbook: async () => ({ distributions: [{ recordId: 'r', textbookName: '电工基础', status: 'PENDING' }], fees: {} }), signTextbook: async () => null }, run: page => { page.openSign(page.d.distributions[0]); page.received = true; return page.sign(page.d.distributions[0]) } },
      evaluation: { api: { getMyEvaluationTasks: async () => ({ list: [{ taskId: 't', courseName: '电工技术', canSubmit: true, submitted: false }] }), submitEvaluation: async () => null }, run: page => { page.openSubmit(page.d.list[0]); page.score = '85'; return page.submit() } },
      'level-exam': { api: { getMyLevelExam: async () => ({ openExams: [{ examId: 'e', examName: '普通话' }], myRegs: [] }), registerLevelExam: async () => null }, run: page => { page.openDetail(page.d.openExams[0]); page.confirmed = true; return page.register(page.d.openExams[0]) } }
    }
    const sample = cases[kind]
    const { page } = mount(kind, sample.api)
    await page.load(); await sample.run(page)
    assert.ok(page.pendingApplication)
    assert.match(page.applicationNotice, /结果待核实/)
  })
}


test('makeup restores unsent drafts by stable candidate and blocks removed candidates', async () => {
  let writes = 0
  const options = { retakeOptions: [{ gradeId: 'g1', courseName: '课程甲' }], exemptionOptions: [{ courseId: 'c1', courseName: '课程乙' }] }
  const run = mount('makeup', { getMyMakeup: async () => ({ retakes: [], exemptions: [] }), getMakeupOptions: async () => options, applyRetake: async () => { writes++ }, applyExemption: async () => { writes++ } })
  await run.page.load()
  run.page.retakeForm.reason = '保留重修说明'
  run.page.exForm.reason = '保留免修说明'
  run.hook('onHide')
  options.retakeOptions = []; options.exemptionOptions = []
  const restored = run.reopen(); await restored.load()
  assert.equal(restored.retakeForm.reason, '保留重修说明')
  assert.equal(restored.exForm.reason, '保留免修说明')
  assert.equal(restored.retakeAvailable, false)
  assert.equal(restored.exemptionAvailable, false)
  await restored.submitRetake(); await restored.submitExemption()
  assert.equal(writes, 0)
})

test('registration keeps batches on server pages and preserves an exact batch deep link', async () => {
  const calls = []
  const batches = Array.from({ length: 42 }, (_, index) => ({
    batchId: String(index + 1), batchName: `注册批次${index + 1}`,
    canRegister: index !== 41, canDefer: index !== 41, registrationStatus: 'PENDING_REGISTER'
  }))
  const { page } = mount('registration', {
    getMyRegistration: async params => {
      const request = JSON.parse(JSON.stringify(params))
      calls.push(request)
      const batchId = request.batchId
      if (batchId) {
        const target = batches.find(batch => batch.batchId === String(batchId))
        return { batches: target ? [target] : [], page: request.page, pageSize: request.pageSize, total: target ? 1 : 0, hasMore: false }
      }
      const start = (request.page - 1) * request.pageSize
      return {
        batches: batches.slice(start, start + request.pageSize),
        page: request.page, pageSize: request.pageSize, total: batches.length,
        hasMore: request.page * request.pageSize < batches.length
      }
    }
  })
  await page.load()
  await page.changePage(2)
  await page.changePage(3)
  assert.deepEqual(calls.slice(0, 3), [
    { page: 1, pageSize: 20 }, { page: 2, pageSize: 20 }, { page: 3, pageSize: 20 }
  ])
  assert.equal(page.d.batches.length, 2)
  assert.equal(page.d.total, 42)
  assert.equal(page.pageCount, 3)
  page.targetId = '42'
  await page.load(1)
  assert.deepEqual(calls.at(-1), { page: 1, pageSize: 20, batchId: '42' })
  assert.equal(page.d.batches[0].batchId, '42')
})


test('makeup candidate paging and search preserve reasons and query exact deep links', async () => {
  const calls = []
  const { page } = mount('makeup', {
    getMyMakeup: async () => ({ retakes: [], exemptions: [] }),
    getMakeupOptions: async params => {
      calls.push({ ...params })
      return {
        retakeOptions: [{ gradeId: params.gradeId || `grade-${params.page}`, courseName: '重修课程' }],
        exemptionOptions: [{ courseId: `course-${params.page}`, courseName: '免修课程' }],
        retakePagination: { page: params.page, pageSize: 20, total: 25, hasMore: params.page === 1 },
        exemptionPagination: { page: params.page, pageSize: 20, total: 25, hasMore: params.page === 1 }
      }
    }
  })
  page.targetId = '9223372036854775001'
  await page.load()
  assert.equal(calls[0].gradeId, page.targetId)
  assert.equal(page.retakeForm.gradeId, page.targetId)
  page.retakeForm.reason = '保留重修说明'
  page.exForm.reason = '保留免修说明'
  await page.changeOptionPage(2)
  assert.equal(calls.at(-1).page, 2)
  assert.equal(calls.at(-1).gradeId, undefined)
  assert.equal(page.retakeForm.gradeId, 'grade-2')
  assert.equal(page.retakeForm.reason, '保留重修说明')
  assert.equal(page.exForm.reason, '保留免修说明')
  page.optionKeyword = '  数学  '
  await page.searchOptions()
  assert.equal(calls.at(-1).page, 1)
  assert.equal(calls.at(-1).pageSize, 20)
  assert.equal(calls.at(-1).keyword, '数学')
  page.submitting = true
  page.optionKeyword = '不可在提交时切换'
  const count = calls.length
  await page.searchOptions()
  assert.equal(calls.length, count)
  assert.equal(page.appliedOptionKeyword, '数学')
})

test('makeup keeps retake and exemption histories on independent server pages', async () => {
  const calls = []
  const { page } = mount('makeup', {
    getMyMakeup: async params => {
      calls.push(JSON.parse(JSON.stringify(params)))
      return {
        retakes: [{ applyId: `r-${params.retakePage}`, courseName: '重修课程' }],
        retakePagination: { total: 21, page: params.retakePage, pageSize: 20, hasMore: params.retakePage < 2 },
        exemptions: [{ exemptionId: `e-${params.exemptionPage}`, courseName: '免修课程' }],
        exemptionPagination: { total: 21, page: params.exemptionPage, pageSize: 20, hasMore: params.exemptionPage < 2 }
      }
    },
    getMakeupOptions: async () => ({ retakeOptions: [], exemptionOptions: [] })
  })
  await page.load()
  await page.changeRetakePage(2)
  await page.changeExemptionPage(2)
  assert.deepEqual(calls, [
    { retakePage: 1, retakePageSize: 20, exemptionPage: 1, exemptionPageSize: 20 },
    { retakePage: 2, retakePageSize: 20, exemptionPage: 1, exemptionPageSize: 20 },
    { retakePage: 2, retakePageSize: 20, exemptionPage: 2, exemptionPageSize: 20 }
  ])
  assert.equal(page.d.retakes[0].applyId, 'r-2')
  assert.equal(page.d.exemptions[0].exemptionId, 'e-2')
})


test('returned exemption keeps its original ID, can replace evidence, and never resends a historical term', async () => {
  const returned = {
    exemptionId: '9007199254740993', courseId: '201', courseName: '课程乙', reason: '原申请说明',
    status: 'SUBMITTED', currentNode: 'STUDENT_RESUBMIT', returnReason: '请补充正式证明材料', canResubmit: true
  }
  let sent
  const { page } = mount('makeup', {
    getMyMakeup: async () => ({
      retakes: [], retakePagination: { total: 0, page: 1, pageSize: 20, hasMore: false },
      exemptions: [returned], exemptionPagination: { total: 1, page: 1, pageSize: 20, hasMore: false }
    }),
    getMakeupOptions: async () => ({ retakeOptions: [], exemptionOptions: [] }),
    resubmitExemption: async (id, body) => {
      sent = { id, body: JSON.parse(JSON.stringify(body)) }
      returned.status = 'TEACHER_REVIEW'; returned.currentNode = 'TEACHER_REVIEW'; returned.canResubmit = false
      return { exemptionId: id }
    }
  })
  await page.load()
  assert.equal(page.exemptionStatusLabel(returned.status, returned.currentNode), '已退回，待补充材料')
  page.beginExemptionResubmit(returned)
  page.materials = [{ fileId: '41', readyForBusiness: true }]
  await page.submitExemption()
  assert.deepEqual(sent, {
    id: '9007199254740993',
    body: { courseId: '201', courseName: '课程乙', reason: '原申请说明', materialFileIds: ['41'] }
  })
  assert.equal(page.pendingApplication, null)
  assert.equal(page.resubmitExemptionId, '')
  assert.equal(returned.status, 'TEACHER_REVIEW')
})


test('recognition name-only draft never sends an invalid request or substitutes a manual internal ID', async () => {
  let writes=0
  const {page}=mount('recognition',{getMyRecognition:async()=>({items:[]}),submitRecognition:async()=>{writes++}})
  await page.load();Object.assign(page.form,{sourceCourseName:'原课程',targetCourseName:'手填同名课程',sourceScore:'80'})
  await page.submit();assert.equal(writes,0);assert.equal(page.canSubmit,false);assert.equal(page.form.sourceCourseName,'原课程')
  const src=readFileSync(new URL('../src/pages/student/academic-affairs/recognition.vue',import.meta.url),'utf8')
  assert.doesNotMatch(src,/<input[^>]*v-model="form.targetCourse(Name|Id)"/)
})
test('recognition sends exact string target ID and does not accept adjacent ID with same name', async () => {
  let body,writes=0
  const target='1000000000000063602'
  const {page}=mount('recognition',{getMyRecognition:async()=>({items:writes?[{recognitionId:'NEW',sourceCourseName:'原课程',targetCourseName:'同名课程',targetCourseId:'1000000000000063603',sourceScore:80}]:[]}),submitRecognition:async value=>{body=value;writes++;return {recognitionId:'NEW'}}})
  await page.load();allowRecognition(page,target,'同名课程');Object.assign(page.form,{sourceCourseName:'原课程',targetCourseName:'同名课程',targetCourseId:target,sourceScore:'80'});await page.submit()
  assert.equal(body.targetCourseId,target);assert.equal(body.targetCourseName,'同名课程');assert.ok(page.pendingApplication)
})
test('recognition course options keep string IDs, paginate and ignore stale identity results', async () => {
  const calls=[]
  const {page}=mount('recognition',{getMyRecognition:async()=>({items:[]}),getRecognitionCourses:async q=>{calls.push(q);return {items:[{courseId:q.page===1?'1000000000000063602':'1000000000000063603',courseCode:`KC-${q.page}`,courseName:`课程${q.page}`,version:'2026版'}],total:21}}})
  await page.loadRecognitionCourses(false);await page.loadRecognitionCourses(true);assert.deepEqual(calls.map(q=>[q.page,q.pageSize]),[[1,20],[2,20]]);assert.equal(JSON.stringify(page.courseOptions.map(row=>row.courseId)),JSON.stringify(['1000000000000063602','1000000000000063603']))
  page.selectCourse(page.courseOptions[1]);assert.equal(page.form.targetCourseId,'1000000000000063603');assert.equal(typeof page.form.targetCourseId,'string')
  let release;const late=mount('recognition',{getRecognitionCourses:()=>new Promise(resolve=>{release=resolve})});const pending=late.page.loadRecognitionCourses(false);late.session.generation++;release({items:[{courseId:'9',courseName:'旧身份课程'}],total:1});await pending;assert.equal(late.page.courseOptions.length,0)
})
test('clearance only releases FINISHED formal score, preserving zero and hiding SCORED values', async () => {
  const {page}=mount('clearance',{getMyClearance:async()=>({items:[]})})
  assert.equal(page.resultLabel({status:'SCORED',score:88}),'待公布成绩');assert.equal(page.publishedScore({status:'SCORED',score:88}),'待公布或核对')
  assert.equal(page.resultLabel({status:'FINISHED',score:60}),'已公布成绩');assert.equal(page.publishedScore({status:'FINISHED',score:60}),60)
  assert.equal(page.publishedScore({status:'FINISHED',score:0}),0);assert.equal(page.resultLabel({status:'FINISHED',score:null}),'已结束，成绩待核对')
  assert.equal(page.publishedScore({status:'PUBLISHED',score:88}),'待公布或核对');assert.equal(page.resultLabel({status:'PASSED'}),'结果待核对')
})

for (const kind of ['retake', 'exemption']) {
  test(`${kind}: missing original ACK stays pending even when one new same-source record appears`, async () => {
    let writes = 0
    const idKey = kind === 'retake' ? 'applyId' : 'exemptionId'
    const row = { [idKey]: '9007199254740993', originGradeId: '101', course: { id: '201' } }
    const api = {
      getMyMakeup: async () => ({ retakes: kind === 'retake' && writes ? [row] : [], exemptions: kind === 'exemption' && writes ? [row] : [] }),
      getMakeupOptions: async () => ({ retakeOptions: [{ gradeId: '101' }], exemptionOptions: [{ courseId: '201' }] }),
      applyRetake: async () => { writes++; throw Error('timeout') },
      applyExemption: async () => { writes++; throw Error('timeout') }
    }
    const run = mount('makeup', api)
    await run.page.load()
    await run.page[kind === 'retake' ? 'submitRetake' : 'submitExemption']()
    assert.ok(run.page.pendingApplication)
    assert.match(run.page.applicationNotice, /结果待核实/)
    const reopened = run.reopen(); await reopened.load()
    await reopened[kind === 'retake' ? 'submitRetake' : 'submitExemption']()
    assert.equal(writes, 1)
    assert.ok(reopened.pendingApplication)
  })

  test(`${kind}: original ACK must also match the original source before clearing the draft`, async () => {
    let writes = 0
    const idKey = kind === 'retake' ? 'applyId' : 'exemptionId'
    const row = { [idKey]: '9007199254740993', originGradeId: '102', course: { id: '202' } }
    const api = {
      getMyMakeup: async () => ({ retakes: kind === 'retake' && writes ? [row] : [], exemptions: kind === 'exemption' && writes ? [row] : [] }),
      getMakeupOptions: async () => ({ retakeOptions: [{ gradeId: '101' }], exemptionOptions: [{ courseId: '201' }] }),
      applyRetake: async () => { writes++; return { [idKey]: row[idKey] } },
      applyExemption: async () => { writes++; return { [idKey]: row[idKey] } }
    }
    const { page } = mount('makeup', api)
    await page.load()
    const form = kind === 'retake' ? page.retakeForm : page.exForm
    form.reason = '保留原申请说明'
    await page[kind === 'retake' ? 'submitRetake' : 'submitExemption']()
    assert.ok(page.pendingApplication)
    assert.equal(form.reason, '保留原申请说明')
    row.originGradeId = '101'; row.course.id = '201'
    await page.load()
    assert.equal(page.pendingApplication, null)
    assert.equal((kind === 'retake' ? page.retakeForm : page.exForm).reason, '')
    assert.equal(writes, 1)
  })
}

test('major split keeps the command pending when a matching record lacks this command receipt', async () => {
  let writes = 0, saved = false
  const batch = { batchId: 'b-1', batchName: '2026 专业分流', maxChoices: 2, options: [{ majorId: 'm-1', majorName: '机电一体化' }] }
  const volunteer = { volunteerId: 'v-1', batchId: 'b-1', choices: ['m-1'], status: 'SUBMITTED' }
  const { page } = mount('major-split', {
    getMyMajorSplit: async () => ({ openBatches: [batch], myVolunteers: saved ? [volunteer] : [] }),
    submitMajorSplit: async () => { writes++; saved = true; return null }
  })
  await page.load(); page.picks = { 'b-1': ['m-1'] }
  await page.submit(batch); await page.submit(batch)
  assert.equal(writes, 1)
  const command = JSON.parse(JSON.stringify(page.pending['b-1']))
  assert.deepEqual({ choices: command.choices, volunteerId: command.volunteerId, batchId: command.batchId }, { choices: ['m-1'], volunteerId: '', batchId: 'b-1' })
  assert.ok(command.commandId)
  assert.match(page.notice.description, /不要重复提交/)
})

test('evaluation loads bounded server pages instead of extending a local full task list', async () => {
  const calls = []
  const { page } = mount('evaluation', {
    getMyEvaluationTasks: async (params) => {
      calls.push({ ...params })
      const current = Number(params.page)
      return {
        list: current === 1
          ? [{ taskId: 'task-1', courseName: '电工基础', canSubmit: true, submitted: false }]
          : [{ taskId: 'task-21', courseName: '电子技术', canSubmit: true, submitted: false }],
        pagination: { page: current, pageSize: 20, total: 21, hasMore: current === 1 }
      }
    }
  })
  await page.load()
  assert.deepEqual(JSON.parse(JSON.stringify(calls[0])), { page: 1, pageSize: 20 })
  assert.equal(page.d.list[0].taskId, 'task-1')
  await page.changePage(2)
  assert.deepEqual(JSON.parse(JSON.stringify(calls[1])), { page: 2, pageSize: 20 })
  assert.equal(page.d.list[0].taskId, 'task-21')
  assert.equal(page.pageCount, 2)
})

test('major split loads batch options and history through independent bounded server pages', async () => {
  const reads = []
  const optionReads = []
  const batch = { batchId: 'batch-1', batchName: '2026 专业分流', maxChoices: 2 }
  const api = {
    getMyMajorSplit: async (params) => {
      reads.push({ ...params })
      const volunteerPage = Number(params.volunteerPage)
      return {
        openBatches: [batch],
        openPagination: { page: Number(params.openPage), pageSize: 20, total: 1, hasMore: false },
        myVolunteers: volunteerPage === 2
          ? [{ volunteerId: 'v-2', batchId: 'history-2', batchName: '历史批次', choices: ['m-2'], choiceNames: ['历史专业'], status: 'ALLOCATED', statusLabel: '已分配专业，等待学校确认' }]
          : [{ volunteerId: 'v-1', batchId: 'history-1', batchName: '历史批次', choices: ['m-1'], choiceNames: ['原专业'], status: 'PENDING', statusLabel: '志愿已提交，等待学校分流' }],
        volunteerPagination: { page: volunteerPage, pageSize: 20, total: 21, hasMore: volunteerPage === 1 }
      }
    },
    getMajorSplitOptions: async (batchId, params) => {
      optionReads.push({ batchId, ...params })
      const page = Number(params.page)
      return {
        items: page === 1
          ? [{ optionId: 'o-1', majorId: 'm-1', majorName: '软件技术', capacity: 30, remain: 29 }]
          : [{ optionId: 'o-2', majorId: 'm-2', majorName: '网络技术', capacity: 30, remain: 28 }],
        page, pageSize: 20, total: 21, hasMore: page === 1
      }
    }
  }
  const { page } = mount('major-split', api)
  await page.load()
  assert.deepEqual(JSON.parse(JSON.stringify(reads[0])), { openPage: 1, openPageSize: 20, volunteerPage: 1, volunteerPageSize: 20 })
  assert.equal(batch.options, undefined)
  await page.toggleBatch(batch)
  assert.deepEqual(JSON.parse(JSON.stringify(optionReads[0])), { batchId: 'batch-1', page: 1, pageSize: 20 })
  assert.equal(page.optionState(batch).loaded, true)
  assert.equal(page.batchOptions(batch)[0].majorName, '软件技术')
  await page.loadOptions(batch, 2)
  assert.deepEqual(JSON.parse(JSON.stringify(optionReads[1])), { batchId: 'batch-1', page: 2, pageSize: 20 })
  assert.equal(page.batchOptions(batch)[0].majorName, '网络技术')
  await page.nextVolunteerPage()
  assert.deepEqual(JSON.parse(JSON.stringify(reads.at(-1))), { openPage: 1, openPageSize: 20, volunteerPage: 2, volunteerPageSize: 20 })
  assert.equal(page.d.myVolunteers[0].choiceNames[0], '历史专业')
})

test('major split releases a stale option loading lock after the page is hidden', async () => {
  let resolveOptions
  let reads = 0
  const options = new Promise(resolve => { resolveOptions = resolve })
  const batch = { batchId: 'batch-stale', batchName: '待恢复批次', maxChoices: 2 }
  const { page, hook } = mount('major-split', {
    getMyMajorSplit: async () => ({ openBatches: [batch], myVolunteers: [] }),
    getMajorSplitOptions: async () => {
      reads += 1
      if (reads === 1) return options
      return { items: [{ optionId: 'o-2', majorId: 'm-2', majorName: '网络技术' }], page: 1, pageSize: 20, total: 1, hasMore: false }
    }
  })
  await page.load()
  const staleRead = page.loadOptions(batch, 1)
  assert.equal(page.optionState(batch).loading, true)

  hook('onHide')
  assert.equal(page.optionState(batch).loading, false)
  page.hidden = false
  const retry = page.loadOptions(batch, 1)
  assert.equal(reads, 2)
  await retry
  assert.equal(page.optionState(batch).loaded, true)

  resolveOptions({ items: [{ optionId: 'o-1', majorId: 'm-1', majorName: '旧专业' }], page: 1, pageSize: 20, total: 1, hasMore: false })
  await staleRead
  assert.equal(page.batchOptions(batch)[0].majorName, '网络技术')
  assert.equal(page.optionState(batch).loading, false)
})

test('major split clears only when its volunteer receipt, batch and ordered choices match', async () => {
  const batch = { batchId: 'b-1', batchName: '2026 专业分流', maxChoices: 2, options: [{ majorId: 'm-1', majorName: '机电一体化' }] }
  const volunteer = { volunteerId: 'v-1', batchId: 'b-1', choices: ['m-1'], status: 'SUBMITTED' }
  const { page } = mount('major-split', {
    getMyMajorSplit: async () => ({ openBatches: [batch], myVolunteers: [volunteer] }),
    submitMajorSplit: async () => ({ volunteerId: 'v-other', batchId: 'b-1' })
  })
  await page.load(); page.picks = { 'b-1': ['m-1'] }
  await page.submit(batch)
  assert.ok(page.pending['b-1'])
  const exact = mount('major-split', {
    getMyMajorSplit: async () => ({ openBatches: [batch], myVolunteers: [volunteer] }),
    submitMajorSplit: async () => ({ volunteerId: 'v-1', batchId: 'b-1' })
  })
  await exact.page.load(); exact.page.picks = { 'b-1': ['m-1'] }
  await exact.page.submit(batch)
  assert.equal(exact.page.pending['b-1'], undefined)
  assert.equal(exact.page.dirty['b-1'], false)
  assert.equal(exact.page.notice.title, '志愿记录已确认')
})

test('major split 403 clears visible information while preserving the pending command', async () => {
  let denied = false
  const batch = { batchId: 'b-1', batchName: '2026 专业分流', maxChoices: 2, options: [{ majorId: 'm-1', majorName: '机电一体化' }] }
  const { page, ledger } = mount('major-split', { getMyMajorSplit: async () => {
    if (denied) throw { httpStatus: 403, code: 403001, biz: true }
    return { openBatches: [batch], myVolunteers: [] }
  } })
  await page.load()
  const pending = ledger.createPendingCommand('major-split', { action: 'MAJOR_SPLIT_SUBMIT', choices: ['m-1'], volunteerId: '', batchId: 'b-1' })
  ledger.savePending('major-split', { 'b-1': pending })
  page.picks = { 'b-1': ['m-1'] }; page.dirty = { 'b-1': true }; page.activeBatchId = 'b-1'
  denied = true; await page.load()
  assert.equal(page.state, 'forbidden')
  assert.equal(page.d, null)
  assert.deepEqual(JSON.parse(JSON.stringify(page.picks)), {})
  assert.equal(page.activeBatchId, '')
  assert.ok(page.pending['b-1'])
})

test('major split ignores a delayed old 403 after a newer successful read', async () => {
  let rejectOld, calls = 0
  const batch = { batchId: 'new', batchName: '当前批次', maxChoices: 1, options: [] }
  const { page } = mount('major-split', { getMyMajorSplit: () => {
    calls++
    return calls === 1 ? new Promise((_, reject) => { rejectOld = reject }) : Promise.resolve({ openBatches: [batch], myVolunteers: [] })
  } })
  const oldRead = page.load()
  await page.load()
  rejectOld({ httpStatus: 403, code: 403001, biz: true })
  await oldRead
  assert.equal(page.state, 'ready')
  assert.equal(page.d.openBatches[0].batchId, 'new')
})

const privacyCases = [
  {
    name: 'recognition', scope: 'recognition', payload: { body: {} }, api: denied => ({ getMyRecognition: async () => denied() ? Promise.reject({ httpStatus: 403, code: 403001 }) : ({ items: [] }) }),
    prepare: page => { page.form.sourceCourseName = '敏感原课程' }, scrubbed: page => page.form.sourceCourseName === ''
  },
  {
    name: 'recheck', scope: 'recheck', payload: { body: { acadGradeId: 'g-1', reason: '敏感复查理由' } }, api: denied => ({ getMyRecheck: async () => denied() ? Promise.reject({ httpStatus: 403, code: 403001 }) : ({ items: [], page: 1, pageSize: 20, total: 0, hasMore: false }), getMyTranscript: async () => ({ items: [{ gradeId: 'g-1', courseName: '课程' }] }) }),
    prepare: page => { page.reason = '敏感复查理由'; page.grades = [{ gradeId: 'g-1' }] }, scrubbed: page => page.reason === '' && page.grades.length === 0
  },
  {
    name: 'exam', scope: 'exam', payload: { body: { examCourseId: 'e-1', reason: '敏感缓考理由' } }, api: denied => ({ getMyExamSchedule: async () => denied() ? Promise.reject({ httpStatus: 403, code: 403001 }) : ({ items: [] }), getMyDeferOptions: async () => ({ items: [] }), getMyDeferrals: async () => ({ items: [] }) }),
    prepare: page => { page.form.reason = '敏感缓考理由'; page.selectedCourse = { examCourseId: 'e-1' } }, scrubbed: page => page.form.reason === '' && page.selectedCourse === null
  },
  {
    name: 'registration', scope: 'registration', payload: { kind: 'defer', body: { batchId: 'b-1', reason: '敏感暂缓理由', requestedUntil: '2026-09-20' } }, api: denied => ({ getMyRegistration: async () => denied() ? Promise.reject({ httpStatus: 403, code: 403001 }) : ({ batches: [] }) }),
    prepare: page => { page.deferReason = '敏感暂缓理由'; page.deferUntil = '2026-09-20' }, scrubbed: page => page.deferReason === '' && page.deferUntil === ''
  },
  {
    name: 'textbook', scope: 'textbook', payload: { body: { recordId: 'r-1' } }, api: denied => ({ getMyTextbook: async () => denied() ? Promise.reject({ httpStatus: 403, code: 403001 }) : ({ distributions: [], fees: {} }) }),
    prepare: page => { page.signingId = 'r-1'; page.received = true }, scrubbed: page => page.signingId === '' && page.received === false
  },
  {
    name: 'level-exam', scope: 'level-exam', payload: { body: { examId: 'l-1' } }, api: denied => ({ getMyLevelExam: async () => denied() ? Promise.reject({ httpStatus: 403, code: 403001 }) : ({ openExams: [], myRegs: [] }) }),
    prepare: page => { page.detailId = 'l-1'; page.confirmed = true }, scrubbed: page => page.detailId === '' && page.confirmed === false
  }
]

for (const sample of privacyCases) {
  test(`${sample.name}: a current 403 removes visible academic data but retains the command reference`, async () => {
    let denied = false
    const { page, ledger } = mount(sample.name, sample.api(() => denied))
    await page.load(); sample.prepare(page)
    const pending = ledger.createPendingCommand(sample.scope, { action: sample.scope, title: '本次办理', ...sample.payload, returnedId: '', knownIds: [], idKey: 'id' })
    ledger.savePending(sample.scope, pending)
    denied = true; await page.load()
    assert.equal(page.state, 'forbidden')
    assert.equal(page.d, null)
    assert.ok(page.pendingApplication)
    assert.ok(sample.scrubbed(page))
  })
}

test('registration cannot manufacture a current batch ACK from a different server batch', async () => {
  let writes = 0
  const batch = { batchId: '101', canRegister: true, registrationStatus: 'PENDING' }
  const { page } = mount('registration', {
    getMyRegistration: async () => ({ batches: [batch] }),
    registerSelf: async () => { writes++; batch.registrationStatus = 'REGISTERED'; return { registrationId: '901', batchId: '102' } }
  })
  await page.load(); await page.doRegister(batch)
  assert.ok(page.pendingApplication)
  assert.equal(page.pendingApplication.returnedId, '')
  assert.equal(writes, 1)
})

test('registration accepts its real registrationId ACK and confirms the same batch', async () => {
  const batch = { batchId: '101', registrationId: '', canRegister: true, registrationStatus: 'PENDING' }
  const { page } = mount('registration', {
    getMyRegistration: async () => ({ batches: [batch] }),
    registerSelf: async () => {
      batch.registrationId = '901'; batch.registrationStatus = 'REGISTERED'
      return { registrationId: '901', status: 'REGISTERED' }
    }
  })
  await page.load(); await page.doRegister(batch)
  assert.equal(page.pendingApplication, null)
  assert.match(page.applicationNotice, /本批次注册已完成/)
})

test('registration cold recovery requires both its original registrationId and batch', async () => {
  const { page, ledger } = mount('registration', { getMyRegistration: async () => ({ batches: [] }) })
  const pending = ledger.createPendingCommand('registration', {
    action: 'registration', kind: 'register', existingId: '101', idKey: 'registrationId', recordKey: 'batchId', receiptKey: 'registrationId',
    returnedId: '901', recovery: { field: 'registrationStatus', equals: 'REGISTERED' }
  })
  ledger.savePending('registration', pending)
  page.pendingApplication = { commandId: pending.commandId, _pendingOwner: pending._pendingOwner, action: 'registration', kind: 'register', objectId: '101', recordKey: 'batchId', receiptKey: 'registrationId', returnedId: '901', recovery: { field: 'registrationStatus', equals: 'REGISTERED' }, recoveryOnly: true }
  page.acceptApplication([{ batchId: '101', registrationId: '902', registrationStatus: 'REGISTERED' }], 'registrationId', () => true)
  assert.ok(page.pendingApplication)
  page.acceptApplication([{ batchId: '102', registrationId: '901', registrationStatus: 'REGISTERED' }], 'registrationId', () => true)
  assert.ok(page.pendingApplication)
  page.acceptApplication([{ batchId: '101', registrationId: '901', registrationStatus: 'REGISTERED' }], 'registrationId', () => true)
  assert.equal(page.pendingApplication, null)
})

test('recognition refreshed page can reload candidates after an older course query was invalidated', async () => {
  let resolveOld, calls = 0
  const { page } = mount('recognition', {
    getMyRecognition: async () => ({ items: [] }),
    getRecognitionCourses: () => ++calls === 1 ? new Promise(resolve => { resolveOld = resolve }) : Promise.resolve({ items: [{ courseId: '202', courseName: '最新正式课程' }], total: 1 })
  })
  await page.load(); page.showForm = true
  const old = page.loadRecognitionCourses(false)
  await page.load()
  assert.equal(calls, 2)
  await new Promise(setImmediate)
  assert.equal(page.courseLoading, false)
  resolveOld({ items: [{ courseId: '101', courseName: '旧课程' }], total: 1 }); await old
  assert.equal(page.courseOptions[0].courseId, '202')
})

for (const formalId of ['901', '902']) {
  test(`registration accepts the actual ACK without batchId only for its formal registration ${formalId}`, async () => {
    const batch = { batchId: '101', registrationId: null, canRegister: true, registrationStatus: 'PENDING_REGISTER' }
    const { page } = mount('registration', {
      getMyRegistration: async () => ({ batches: [batch] }),
      registerSelf: async () => { batch.registrationId = formalId; batch.registrationStatus = 'REGISTERED'; return { registrationId: '901', status: 'REGISTERED' } }
    })
    await page.load(); await page.doRegister(batch)
    assert.equal(page.pendingApplication === null, formalId === '901')
    if (formalId !== '901') assert.equal(page.pendingApplication.returnedId, '901')
  })
}
