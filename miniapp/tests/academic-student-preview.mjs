// Explicitly launched local visual-test fixture. Never imported by the app.
import http from 'node:http'
import { readFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../dist/academic-student-preview')
let mode = 'normal'
let records = []
const calls = []
const batch = { batchId: 'fixture-batch', batchName: '演练 · 2026秋季通识选修' }
const courses = [
  { selectionCourseId: 'fixture-1', courseName: '演练 · 人工智能应用基础', courseCode: 'AI101', teacherName: '李老师', credit: 2, capacity: 40, remain: 1, lottery: { mode: 'FCFS' }, scheduleItems: [{ weekday: 3, slotNo: 5, classroom: '知行楼302' }] },
  { selectionCourseId: 'fixture-2', courseName: '演练 · 职业沟通与表达', courseCode: 'GE206', teacherName: '陈老师', credit: 2, capacity: 30, remain: null, lottery: { mode: 'LOTTERY' }, scheduleItems: [{ weekday: 5, slotNo: 3, classroom: '明德楼205' }] }
]
const grades = [{ gradeId: 'fixture-grade', courseName: '演练 · PLC应用基础', score: 58, passStatus: 'FAILED', term: '2026春季', credit: 3 }]
const fixtures = {
  '/transfer-options': { majors: [{ majorId: 'fixture-m1', majorName: '机电技术' }, { majorId: 'fixture-m2', majorName: '电气技术' }], classes: [{ classId: 'fixture-c1', className: '机电2402' }], majorClasses: { 'fixture-m2': [{ classId: 'fixture-c2', className: '电气2401' }] } },
  '/transcript/my': { items: grades, earnedCredits: 36, gpa: 3.18, failCount: 1 },
  '/grade-recheck/my': { items: [] }, '/recognition/my': { items: [] },
  '/graduation/my': { overall: 'SYSTEM_PASSED', hasAudit: false, items: [{ item: 'STATUS', result: 'PASS', evidence: '演练：学籍状态正常。' }, { item: 'CREDIT', result: 'PASS', evidence: '演练：已获学分满足当前要求。' }], decisionText: { title: '演练 · 当前实时自查通过', reason: '当前自查通过不代表学校已批准毕业。', nextStep: '关注学校正式毕业审核通知。' } },
  '/registration/my': { realName: '演练学生', studentNo: 'TEST-001', batches: [{ batchId: 'fixture-reg', batchName: '演练 · 秋季学期注册', registrationStatus: 'PENDING', eligibilityStatus: 'ELIGIBLE', canRegister: true, canDefer: true, windowStart: '2026-09-08', windowEnd: '2026-09-12' }] },
  '/calendar/my': { hasTerm: true, termLabel: '演练 · 2026秋季', events: [{ eventId: 'fixture-event', title: '演练 · 注册截止', startDate: '2026-09-12', endDate: '2026-09-12' }], weeks: [{ weekNo: 2, startDate: '2026-09-07', endDate: '2026-09-13' }] },
  '/attendance/my': { items: [{ sessionId: 'fixture-session', courseName: '演练 · PLC应用基础', sessionDate: '2026-09-08', slotNo: 1, status: 'PRESENT' }], summary: { PRESENT: 1 } },
  '/warning/my': { items: [{ warningId: 'fixture-warning', warnType: 'MULTI_FAIL', level: 'MEDIUM', reason: '演练 · 请关注未通过课程，核对补考安排。', status: 'ACTIVE' }] },
  '/status/my': { enrolled: true, studentStatus: 'REGISTERED', studentNo: 'TEST-001', realName: '演练学生', majorName: '机电技术', className: '机电2401', changes: [] },
  '/credits/my': { obtainedCredits: 36, requiredCredits: 144, resolutionStatus: 'RESOLVED', gpa: 3.18, failCount: 1, passedCourses: [{ courseName: '演练 · 大学英语', term: '2026春季', credit: 2, score: 85 }] },
  '/clearance/my': { items: [{ recordId: 'fixture-clearance', courseName: '演练 · PLC应用基础', batchName: '演练 · 本届清考', originScore: 58, score: 65, status: 'PASSED' }], total: 1, page: 1, pageSize: 20, hasMore: false, note: '演练 · 学校正式发布的清考结果。' },
  '/makeup/my': { retakes: [], exemptions: [] }, '/makeup/options': { retakeOptions: [{ gradeId: 'fixture-grade', courseId: 'fixture-course', courseName: '演练 · PLC应用基础', termCode: '2026春季', score: 58 }], exemptionOptions: [{ courseId: 'fixture-course', courseName: '演练 · PLC应用基础', termCode: '2026秋季' }], identityDebtCount: 0 },
  '/exam/my': { items: [{ examCourseId: 'fixture-exam', courseName: '演练 · PLC应用基础', examDate: '2026-12-22', startTime: '09:00', endTime: '10:40', classroom: '知行楼302', seatNo: '12' }] },
  '/exam/defer-options': { items: [{ examCourseId: 'fixture-exam', courseName: '演练 · PLC应用基础', examDate: '2026-12-22', startTime: '09:00', canApply: true, hasActiveDefer: false }] }, '/exam/defer/my': { items: [] },
  '/textbook/my': { distributions: [{ recordId: 'fixture-book', textbookName: '演练 · PLC技术与应用', qty: 1, status: 'PENDING' }], fees: { totalDue: 36, totalPaid: 0, unpaid: 36, items: [] } },
  '/level-exam/my': {
    openExams: [{ examId: 'fixture-level', examName: '演练 · 普通话等级考试', category: 'PUTONGHUA', fee: 50 }],
    openPagination: { page: 1, pageSize: 20, total: 1, hasMore: false },
    myRegs: [], registrationPagination: { page: 1, pageSize: 20, total: 0, hasMore: false }
  },
  '/major-split/my': {
    openBatches: [{ batchId: 'fixture-major', batchName: '演练 · 专业方向选择', maxChoices: 2 }],
    openPagination: { page: 1, pageSize: 20, total: 1, hasMore: false },
    myVolunteers: [], volunteerPagination: { page: 1, pageSize: 20, total: 0, hasMore: false }
  },
  '/major-split/fixture-major/options': { items: [{ majorId: 'fixture-m1', majorName: '机电技术' }, { majorId: 'fixture-m2', majorName: '电气技术' }], page: 1, pageSize: 20, total: 2, hasMore: false },
  '/evaluation/tasks': { list: [{ taskId: 'fixture-evaluation', courseName: '演练 · PLC应用基础', teacherName: '李老师', canSubmit: true, submitted: false, windowStatus: 'OPEN' }], total: 1, pending: 1 },
  '/schedule/my': { items: [{ itemId: 'fixture-lesson', courseName: '演练 · PLC应用基础', teacherName: '李老师', classroom: '知行楼302', weekday: 2, slotNo: 1, startWeek: 1, endWeek: 18, weekParity: 'ALL' }], todayItems: [{ itemId: 'fixture-lesson', courseName: '演练 · PLC应用基础', teacherName: '李老师', classroom: '知行楼302', weekday: 2, slotNo: 1 }], todayDate: '2026-09-08', currentWeek: 2, teachingWeeks: 18, termCode: '2026秋季', calendarSource: 'NORMAL', timeBands: [{ slotNo: 1, startTime: '08:30', endTime: '09:15' }] }
}
const baseline = JSON.parse(JSON.stringify(fixtures))
let sequence = 0
function emptyProjection(value) {
  if (Array.isArray(value)) return []
  if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, emptyProjection(item)]))
  return typeof value === 'number' ? 0 : typeof value === 'boolean' ? false : ''
}
const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, 'http://127.0.0.1:4175')
  const json = (data, code = 0, status = 200) => { res.writeHead(status, { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store' }); res.end(JSON.stringify({ code, data, message: code ? '演练：当前办理条件不允许' : '演练数据' })) }
  if (url.pathname === '/__fixture') { mode = url.searchParams.get('mode') || 'normal'; records = []; calls.length = 0; sequence = 0; Object.assign(fixtures, JSON.parse(JSON.stringify(baseline))); return json({ mode, fixture: true }) }
  if (url.pathname === '/__calls') return json(calls)
  if (url.pathname.startsWith('/api/')) {
    const route = url.pathname.replace('/api/v1/mobile/academic', '').replace('/exam-v2/', '/exam/')
    calls.push({ route, method: req.method })
    if (mode === 'read-error' && req.method === 'GET') return json(null, 503, 503)
    if (mode === 'read-403' && req.method === 'GET') return json(null, 403001, 403)
    if (mode === 'empty' && req.method === 'GET') return json(route.startsWith('/selection/') ? [] : emptyProjection(fixtures[route] || {}))
    if (route === '/selection/courses') return json([{ batch, courses: courses.map(c => ({ ...c, allowedActions: records.some(r => r.selectionCourseId === c.selectionCourseId && r.status !== 'DROPPED') ? ['DROP'] : ['ENROLL'], window: { endAt: '2026-09-12T18:00:00' } })) }])
    if (route === '/selection/my') return json(records)
    if (route === '/selection/preflight') return mode === '403' || mode === '409' ? json(null, Number(mode), Number(mode)) : json({ allowed: true })
    if (route === '/selection/enroll' || route === '/selection/drop') {
      let raw = ''; for await (const chunk of req) raw += chunk
      const body = JSON.parse(raw || '{}')
      if (mode === 'timeout') { setTimeout(() => { if (!res.destroyed) json(null) }, 10000); return }
      const selected = courses.find(c => c.selectionCourseId === String(body.selectionCourseId)) || courses[0]
      records = [{ recordId: 'fixture-receipt', batchId: batch.batchId, selectionCourseId: selected.selectionCourseId, courseName: selected.courseName, status: route.endsWith('/drop') ? 'DROPPED' : selected.lottery.mode === 'LOTTERY' ? 'PENDING_LOTTERY' : 'SELECTED' }]
      return json(null)
    }
    if (req.method === 'GET' && route in fixtures) return json(fixtures[route])
    if (req.method === 'POST') {
      let raw = ''; for await (const chunk of req) raw += chunk
      const body = JSON.parse(raw || '{}')
      const id = 'fixture-application-' + (++sequence)
      if (mode === 'stale-read') return json(null)
      if (route.startsWith('/registration/')) {
        const target = fixtures['/registration/my'].batches[0]
        if (route.endsWith('/defer')) { target.deferral = { ...body, deferralId: id, status: 'PENDING' }; target.canDefer = false }
        else { target.registrationStatus = 'REGISTERED'; target.canRegister = false; target.canDefer = false }
        return json(null)
      }
      if (route.startsWith('/textbook/') && route.endsWith('/sign')) { fixtures['/textbook/my'].distributions[0].status = 'RECEIVED'; return json(null) }
      if (route.startsWith('/level-exam/')) { fixtures['/level-exam/my'].myRegs = [{ regId: id, examId: 'fixture-level', examName: '演练 · 普通话等级考试', feeStatus: 'UNPAID', status: route.endsWith('/cancel') ? 'CANCELLED' : 'REGISTERED' }]; return json(null) }
      if (route === '/recognition/submit') { const row = { ...body, recognitionId: id, status: 'SUBMITTED' }; fixtures['/recognition/my'].items.push(row); return json(row) }
      if (route === '/grade-recheck/submit') { const row = { ...body, recheckId: id, courseName: grades[0].courseName, originalScore: grades[0].score, status: 'SUBMITTED' }; fixtures['/grade-recheck/my'].items.push(row); return json(row) }
      if (route === '/status-change') { const row = { ...body, changeId: id, status: 'SUBMITTED', version: 1 }; fixtures['/status/my'].changes.push(row); return json(row) }
      if (route === '/exam/defer/apply') { const row = { ...body, deferId: id, courseName: '演练 · PLC应用基础', status: 'SUBMITTED' }; fixtures['/exam/defer/my'].items.push(row); fixtures['/exam/defer-options'].items[0].hasActiveDefer = true; return json(row) }
      if (route === '/evaluation/submit') { fixtures['/evaluation/tasks'].list[0].submitted = true; fixtures['/evaluation/tasks'].list[0].canSubmit = false; return json(null) }
      if (route === '/major-split/submit') { fixtures['/major-split/my'].myVolunteers = [{ ...body, volunteerId: id, status: 'PENDING', choiceNames: (body.choices || []).map(choice => choice === 'fixture-m1' ? '机电技术' : '电气技术') }]; fixtures['/major-split/my'].volunteerPagination = { page: 1, pageSize: 20, total: 1, hasMore: false }; return json({ volunteerId: id, batchId: body.batchId }) }
      if (route === '/makeup/retake-apply') { const row = { ...body, applyId: id, courseName: '演练 · PLC应用基础', status: 'SUBMITTED' }; fixtures['/makeup/my'].retakes.push(row); return json(row) }
      if (route === '/makeup/exemption-apply') { const row = { ...body, exemptionId: id, courseName: '演练 · PLC应用基础', status: 'SUBMITTED' }; fixtures['/makeup/my'].exemptions.push(row); return json(row) }
    }
    return json(null, 503, 503)
  }
  try {
    const relative = decodeURIComponent(url.pathname).replace(/^\/+/, '') || 'index.html'
    let target = path.resolve(root, relative)
    if (!target.startsWith(root + path.sep) && target !== root) { res.writeHead(403); res.end(); return }
    if (!path.extname(target)) target = path.join(root, 'index.html')
    const data = await readFile(target)
    const type = { '.html': 'text/html', '.js': 'application/javascript', '.css': 'text/css', '.svg': 'image/svg+xml', '.png': 'image/png', '.woff2': 'font/woff2' }[path.extname(target)] || 'application/octet-stream'
    res.writeHead(200, { 'Content-Type': type, 'Cache-Control': 'no-store' }); res.end(data)
  } catch (_) { res.writeHead(404); res.end('Local fixture file not found') }
})
server.listen(4175, '127.0.0.1', () => process.stdout.write('Academic visual fixture: http://127.0.0.1:4175 (synthetic data only)\n'))
