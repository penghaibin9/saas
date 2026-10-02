import { test, expect } from '@playwright/test'
import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { execFileSync, spawn } from 'node:child_process'
import { createHash } from 'node:crypto'
import { StaffLoginPage, StudentLoginPage, decodeJwt } from '../pages/login.page.mjs'
import { assertSafeEnvironment } from '../lib/config.mjs'
import { auditRows, assertActor } from '../lib/academic-v5-evidence.mjs'

// One saved term and the same students carry A–H. External domain evidence
// must exist before G/H; an abnormal precheck is a real blocking result.
const root = fileURLToPath(new URL('../../', import.meta.url))
const self = fileURLToPath(import.meta.url)
const roles = ['school', 'collegeA', 'collegeB', 'teacherA', 'teacherB', 'leader']
const apiPath = '/api/v1/academic-affairs'
const originalTermInput = { yearCode: '2026-2027', termNo: 2, startDate: '2027-02-22', endDate: '2027-07-11', teachingWeeks: 20, examWeekStart: 19 }
const closedJourneyInput = { scenarioId: 'v5-closed-term-20261002', objectPrefix: 'v5j_closed01_',
  term: { yearCode: '2025-2026', termNo: 2, startDate: '2026-02-23', endDate: '2026-07-12', teachingWeeks: 20, examWeekStart: 19 },
  holidayDate: '2026-05-01', examDates: { A: '2026-07-07', B: '2026-07-08' }, databasePort: 3314 }

function journeyContract(fixture) {
  if (!fixture.journeyInput) return null
  assert.deepEqual(fixture.journeyInput, closedJourneyInput, '新故事输入必须对应冻结的已结束学期及独立副本')
  assert.deepEqual(fixture.cohort, { entryYear: 2023, expectedGraduateYear: 2026 }, '新故事必须对应2023级、2026届测试学生')
  return fixture.journeyInput
}

function scheduleResumeMode(status) {
  assert.ok(['DRAFT', 'PRE_PUBLISHED', 'PUBLISHED'].includes(status), '课表批次状态不在可核验续跑范围')
  return { DRAFT: 'schedule', PRE_PUBLISHED: 'publish', PUBLISHED: 'read' }[status]
}

function registrationResumeAction(registration, step, pending) {
  assert.equal(pending, null, '注册命令结果尚未核对；禁止按现状态重放或解除待核对命令')
  const action = registration.actions[step]
  if (!action) return true
  assert.ok(action.receipt && action.audits?.length && action.observedAt, '注册动作必须保留正式回执及本次审计，不能凭同状态续跑')
  return false
}

function isolatedUrl(name, fallback, port, pathname) {
  const url = new URL(process.env[name] || fallback)
  assert.ok(['127.0.0.1', 'localhost'].includes(url.hostname), '仅允许本机隔离环境')
  assert.equal(url.protocol, 'http:'); assert.ok((Array.isArray(port) ? port : [port]).includes(url.port), '禁止连接日常端口或其它项目')
  assert.equal(url.pathname.replace(/\/$/, ''), pathname)
  assert.equal(url.username + url.password + url.search + url.hash, '')
  return url.toString().replace(/\/$/, '')
}

function ignoredFile(value) {
  assert.ok(value, '必须配置私有忽略文件路径')
  const resolved = path.resolve(root, value)
  const relative = path.relative(root, resolved)
  assert.ok(relative && !relative.startsWith('..') && !path.isAbsolute(relative), '私有文件必须在当前工作区')
  execFileSync('git', ['check-ignore', '--quiet', '--', relative], { cwd: root, stdio: 'ignore' })
  return resolved
}

function sourceLocation(error) {
  const stack = typeof error?.stack === 'string' ? error.stack : ''
  const message = typeof error?.message === 'string' ? error.message : null
  const messageStart = message === null ? -1 : stack.indexOf(message)
  if (messageStart < 0) return null
  const frames = stack.slice(messageStart + message.length).split(/\r?\n/)
  for (const frame of frames) {
    const match = frame.match(/^\s*at\s+(?:.*\s+\()?[^()\s]*academic-v5-responsibility-journey\.spec\.mjs:(\d+):(\d+)\)?$/)
    if (match) return `e2e/specs/academic-v5-responsibility-journey.spec.mjs:${match[1]}:${match[2]}`
  }
  return null
}

function rejectedInvigilatorProof(report, roomId) {
  const step = 'H-selection-exam-invigilator-A-1'
  assert.equal(report.pending?.step, step, '只允许核对已知监考冲突，其他未知命令不得解除')
  assert.ok(Number.isFinite(Date.parse(report.pending.sentAt)))
  assert.equal(report.failure?.phase, '校教务为学院 A 指定正式教师监考')
  const pathname = `${apiPath}/exam/rooms/${roomId}/invigilators`
  const rejected = (report.receipts || []).filter(row => row.role === 'school' && row.path === pathname && row.method === 'POST')
  assert.equal(rejected.length, 1); assert.equal(rejected[0].status, 409)
  assert.deepEqual(report.errors, [{ role: 'school', path: pathname, status: 409 }])
  return { step, sentAt: report.pending.sentAt, rejectedResponse: rejected[0] }
}

async function runJourney() {
  assertSafeEnvironment()
  const fixtureFile = ignoredFile(process.env.E2E_V5_STATE)
  const credentialFile = ignoredFile(process.env.E2E_V5_CREDENTIALS)
  const resultFile = ignoredFile(`${fixtureFile}.journey.json`)
  const evidenceDir = ignoredFile(`${fixtureFile}.journey-artifacts`)
  const fixture = JSON.parse(await fs.readFile(fixtureFile, 'utf8'))
  const journeyInput = journeyContract(fixture)
  const closedJourney = !!journeyInput
  if (closedJourney) {
    const closedCase = path.basename(fixtureFile).match(/^(v5closed0[12])-state\.json$/)?.[1]
    assert.ok(closedCase, '已结束学期必须使用明确的独立前置文件')
    assert.equal(path.basename(credentialFile), `${closedCase}-credentials.json`, '同一副本必须使用同名私有凭据')
    if (closedCase === 'v5closed02') {
      const copy = JSON.parse(await fs.readFile(path.join(root, '.codex-artifacts/v5-closed02-checkpoint-copy-20261003.json'), 'utf8'))
      const runtime = JSON.parse(await fs.readFile(ignoredFile(process.env.E2E_V5_RUNTIME), 'utf8'))
      assert.equal(runtime.containerName, 'codex-academic-v5-closed02')
      assert.equal(copy.container, runtime.containerName); assert.equal(copy.port, 3314)
      assert.match(String(copy.sourceBackupSha256 || ''), /^[a-f0-9]{64}$/i)
      assert.equal(copy.sourceBackupSha256, runtime.sourceBackupSha256)
      assert.equal(copy.oldCasePreserved, true); assert.equal(copy.decisionCountBeforeRetest, 0)
    }
  }
  const termInput = journeyInput?.term || originalTermInput
  const objectPrefix = journeyInput?.objectPrefix || fixture.prefix
  const holidayDate = journeyInput?.holidayDate || '2027-05-01'
  const staff = isolatedUrl('E2E_STAFF_BASE_URL', 'http://127.0.0.1:5174', closedJourney ? '5175' : '5174', '')
  const api = isolatedUrl('E2E_API_BASE_URL', 'http://127.0.0.1:8002/api/v1', closedJourney ? '8005' : ['8002', '8004'], '/api/v1')
  const databaseUrl = new URL(process.env.DATABASE_URL || '')
  assert.equal(databaseUrl.protocol, 'mysql+pymysql:'); assert.equal(databaseUrl.hostname, '127.0.0.1')
  assert.equal(databaseUrl.port, closedJourney ? '3314' : '3311'); assert.equal(databaseUrl.pathname, '/student_lifecycle_v5_e2e')
  const credentials = JSON.parse(await fs.readFile(credentialFile, 'utf8'))
  assert.ok(fixture.prefix && typeof fixture.tenantId === 'string' && fixture.tenantCode, '场景前置数据不完整')
  for (const role of roles) {
    const account = fixture.accounts?.[role]
    assert.ok(account?.loginName && account.roleCode && account.contextId && typeof account.userId === 'string', '缺少正常角色身份')
    assert.equal(typeof credentials[account.loginName]?.password, 'string', '缺少核验有效的私有凭据')
  }
  for (const key of ['A', 'B']) for (const field of ['collegeId', 'majorId', 'classId']) assert.equal(typeof fixture.colleges?.[key]?.[field], 'string', '前置学院、专业及班级编号必须是字符串')
  let report
  try { report = JSON.parse(await fs.readFile(resultFile, 'utf8')) } catch (error) { if (error.code !== 'ENOENT') throw error }
  report ||= { scenario: 'A-H', prefix: fixture.prefix, tenantId: fixture.tenantId, termId: null, eventId: null, slotIds: [], batchIds: {}, taskIds: {}, pending: null, checkpoints: [], roles: [], uncovered: ['B', 'C', 'D', 'E', 'F', 'G', 'H'] }
  assert.equal(report.prefix, fixture.prefix); assert.equal(report.tenantId, fixture.tenantId)
  if (closedJourney) {
    assert.ok(fixture.accounts.teacherC?.userId && fixture.accounts.teacherC.teacherKey && fixture.accounts.teacherC.loginName, '新故事须保留原第三监考教师资源身份')
    const identity = { accounts: Object.fromEntries([...roles, 'teacherC'].map(role => [role, fixture.accounts[role]])), colleges: fixture.colleges, cohort: fixture.cohort }
    if (report.journeyInput) { assert.deepEqual(report.journeyInput, journeyInput); assert.deepEqual(report.identity, identity) }
    else {
      assert.equal(report.termId, null, '新合同不得接管旧学期办理记录')
      assert.equal(report.checkpoints.length, 0, '新合同不得继承原故事检查点')
      for (const key of ['batchIds', 'taskIds', 'gradeTaskIds', 'scheduleBatchIds']) assert.equal(Object.keys(report[key] || {}).length, 0, '新合同不得继承原业务对象')
      for (const key of ['examBatchId', 'selectionExamPlan', 'graduationBatchId', 'archiveBatchId', 'selectionBatchId', 'registration']) assert.ok(!report[key], '新合同不得继承原终态对象')
      report.journeyInput = journeyInput; report.identity = identity
    }
  }
  if (!closedJourney && report.pending?.step === 'H-selection-exam-invigilator-A-1' && !report.exam409Proof) {
    const protection = JSON.parse(await fs.readFile(path.join(root, '.codex-artifacts/v5-original-exam-repair-protection-20261002.json'), 'utf8'))
    assert.equal(protection.databasePort, 3311)
    const protectedBytes = await fs.readFile(ignoredFile(protection.journalPath))
    assert.equal(createHash('sha256').update(protectedBytes).digest('hex'), protection.journalSha256, '原拒绝保护点字节已变化，停止恢复')
    const protectedReport = JSON.parse(protectedBytes.toString('utf8'))
    assert.equal(protectedReport.prefix, report.prefix); assert.equal(protectedReport.tenantId, report.tenantId)
    assert.deepEqual(protectedReport.pending, report.pending, '保护点必须对应同一原命令及发送时间')
    const roomId = protectedReport.selectionExamPlan?.examRoomIds?.A
    assert.equal(roomId, report.selectionExamPlan?.examRoomIds?.A)
    const rejection = rejectedInvigilatorProof(protectedReport, roomId)
    report.exam409Proof = { pending: protectedReport.pending, failure: { phase: protectedReport.failure.phase },
      receipts: [rejection.rejectedResponse], errors: protectedReport.errors, protectionSha256: protection.journalSha256 }
    const temporary = `${resultFile}.recovery.tmp`
    await fs.writeFile(temporary, JSON.stringify(report, null, 2), 'utf8'); await fs.rename(temporary, resultFile)
  }
  const previousRoleEvidence = report.roles
  const previousRun = report.exam409Proof || { pending: report.pending, failure: report.failure, receipts: report.receipts, errors: report.errors }
  report.scenario = 'A-H'; report.passed = false; report.phase = '正常学校账号登录'; report.roles = []; report.failure = null
  report.batchIds ||= {}; report.taskIds ||= {}; report.scheduleBatchIds ||= {}; report.scheduleItemIds ||= {}
  report.gradeTaskIds ||= {}; report.gradeTaskOwners ||= {}; report.graduationResultOwners ||= {}; report.examCourseOwners ||= {}
  report.examCourseIds ||= {}; report.examRoomIds ||= {}; report.examInvigilatorIds ||= {}
  report.evidenceDirectory = evidenceDir
  await fs.mkdir(evidenceDir, { recursive: true })
  const save = () => fs.writeFile(resultFile, JSON.stringify(report, null, 2), 'utf8')
  const phase = async value => { report.phase = value; await save() }
  const observed = async (step, proof) => {
    const examStep = step.replace(/^H-selection-/, 'H-')
    const examReport = step.startsWith('H-selection-') ? report.selectionExamPlan : report
    let actorRole, bizType, bizId, action, studentId
    if (step.startsWith('assign-B-')) { actorRole = 'collegeB'; bizType = 'AA_TASK'; bizId = step.slice(9); action = 'ASSIGN' }
    else if (step.startsWith('assign-')) { bizId = step.slice(7); actorRole = report.taskIds.A?.includes(bizId) ? 'collegeA' : 'collegeB'; bizType = 'AA_TASK'; action = 'ASSIGN' }
    else if (step.startsWith('teacher-B-')) { actorRole = 'teacherB'; bizType = 'AA_TASK'; bizId = step.slice(10); action = 'TEACHER_CONFIRM' }
    else if (step.startsWith('teacher-')) { actorRole = 'teacherA'; bizType = 'AA_TASK'; bizId = step.slice(8); action = 'TEACHER_CONFIRM' }
    else if (/^college-[AB]-confirm$/.test(step)) { actorRole = step.includes('-A-') ? 'collegeA' : 'collegeB'; bizType = 'AA_TASK_BATCH'; bizId = report.batchIds[actorRole === 'collegeA' ? 'A' : 'B']; action = 'COLLEGE_CONFIRM' }
    else if (/^school-[AB]-review$/.test(step)) { actorRole = 'school'; bizType = 'AA_TASK_BATCH'; bizId = report.batchIds[step.includes('-A-') ? 'A' : 'B']; action = 'ACADEMIC_APPROVE' }
    else if (/^schedule-[AB]-batch$/.test(step)) { actorRole = step.includes('-A-') ? 'collegeA' : 'collegeB'; bizType = 'AA_SCHEDULE_BATCH'; bizId = report.scheduleBatchIds[step.includes('-A-') ? 'A' : 'B']; action = 'CREATE' }
    else if (/^E-pre-[AB]$/.test(step)) { actorRole = step.endsWith('A') ? 'collegeA' : 'collegeB'; bizType = 'AA_SCHEDULE_BATCH'; bizId = report.scheduleBatchIds[step.at(-1)]; action = 'PRE_PUBLISH' }
    else if (/^E-pub-[AB]$/.test(step)) { actorRole = 'school'; bizType = 'AA_SCHEDULE_BATCH'; bizId = report.scheduleBatchIds[step.at(-1)]; action = 'PUBLISH' }
    else if (/^R6-(publish|open|close|lock)$/.test(step)) {
      actorRole = 'school'; bizType = 'AA_SELECTION'; bizId = report.selectionBatchId
      action = { publish: 'SELECTION_BATCH_PUBLISH', open: 'SELECTION_BATCH_OPEN', close: 'SELECTION_BATCH_CLOSE', lock: 'SELECTION_LOCK' }[step.slice(3)]
    }
    else if (/^R6-(enroll|reenroll|drop)-/.test(step)) {
      actorRole = step.replace(/^R6-(enroll|reenroll|drop)-/, ''); bizType = 'AA_SELECTION'; bizId = proof.recordId
      action = step.startsWith('R6-drop-') ? 'SELECTION_DROP' : 'SELECTION_ENROLL'
    }
    else if (step.startsWith('F-submit-')) { bizId = step.slice(9); actorRole = report.gradeTaskOwners[bizId]?.teacher; bizType = 'AA_GRADE_TASK'; action = 'SUBMIT' }
    else if (step.startsWith('F-college-')) { bizId = step.slice(10); actorRole = report.gradeTaskOwners[bizId]?.college; bizType = 'AA_GRADE_TASK'; action = 'COLLEGE_APPROVE' }
    else if (step.startsWith('F-publish-')) { bizId = step.slice(10); actorRole = 'school'; bizType = 'AA_GRADE_TASK'; action = 'PUBLISH' }
    else if (['G-batch', 'G-generate', 'G-precheck', 'G-archive'].includes(step)) {
      actorRole = 'school'; bizType = 'AA_GRAD_AUDIT'; bizId = report.graduationBatchId
      action = { 'G-batch': 'CREATE', 'G-generate': 'GENERATE', 'G-precheck': 'PRECHECK_IMMUTABLE', 'G-archive': 'ARCHIVE' }[step]
    }
    else if (step.startsWith('G-college-')) { bizId = step.slice(10); actorRole = report.graduationResultOwners[bizId]; bizType = 'AA_GRAD_AUDIT'; action = 'COLLEGE_APPROVE' }
    else if (step.startsWith('G-final-')) { bizId = step.slice(8); actorRole = 'school'; bizType = 'AA_GRAD_AUDIT'; action = 'ACADEMIC_FINAL_IMMUTABLE' }
    else if (['H-batch', 'H-check', 'H-confirm'].includes(step)) {
      actorRole = 'school'; bizType = 'AA_ARCHIVE'; bizId = report.archiveBatchId
      action = { 'H-batch': 'ARCHIVE_BATCH_CREATE', 'H-check': 'ARCHIVE_CHECK_V2', 'H-confirm': 'ARCHIVE_CONFIRM_IMMUTABLE' }[step]
    }
    else if (examStep === 'H-exam-batch') { actorRole = 'school'; bizType = 'EXAM_BATCH'; bizId = examReport.examBatchId; action = 'EXAM_BATCH_CREATE' }
    else if (examStep.startsWith('H-exam-course-add-')) { actorRole = 'school'; bizType = 'EXAM_COURSE'; bizId = examStep.slice(18); action = 'EXAM_COURSE_ADD' }
    else if (examStep.startsWith('H-exam-course-confirm-')) {
      bizType = 'EXAM_COURSE'; bizId = examStep.slice(22); action = 'EXAM_COURSE_CONFIRM'; actorRole = examReport.examCourseOwners[bizId]
    }
    else if (['H-exam-batch-confirm', 'H-exam-batch-publish', 'H-exam-batch-finish', 'H-exam-batch-archive'].includes(examStep)) {
      actorRole = 'school'; bizType = 'EXAM_BATCH'; bizId = examReport.examBatchId
      action = { 'H-exam-batch-confirm': 'EXAM_BATCH_CONFIRM', 'H-exam-batch-publish': 'EXAM_BATCH_PUBLISH',
        'H-exam-batch-finish': 'EXAM_BATCH_FINISH', 'H-exam-batch-archive': 'EXAM_BATCH_ARCHIVE' }[examStep]
    }
    else if (/^H-exam-schedule(-replan)?-[AB]$/.test(examStep)) { actorRole = 'school'; bizType = 'EXAM_COURSE'; bizId = examReport.examCourseIds[examStep.at(-1)]; action = 'EXAM_COURSE_SCHEDULE' }
    else if (/^H-exam-room-[AB]$/.test(examStep)) { actorRole = 'school'; bizType = 'EXAM_ROOM'; bizId = examReport.examRoomIds[examStep.at(-1)]; action = 'EXAM_ROOM_ADD' }
    else if (/^H-exam-seats-\d+$/.test(examStep)) { actorRole = 'school'; bizType = 'EXAM_ROOM'; bizId = examStep.match(/\d+$/)[0]; action = 'EXAM_SEAT_ASSIGN' }
    else if (/^H-exam-invigilator-[AB]-[12]$/.test(examStep)) { actorRole = 'school'; bizType = 'EXAM_INVIGILATOR'; bizId = examReport.examInvigilatorIds[examStep.slice(-3)]; action = 'EXAM_INVIGILATOR_ADD' }
    else if (/^H-exam-attendance-\d+-\d+$/.test(examStep)) {
      const match = examStep.match(/^H-exam-attendance-(\d+)-(\d+)$/)
      actorRole = Object.entries(examReport.examRoomIds).find(([, roomId]) => roomId === match[1])?.[0]
      assert.ok(actorRole, '正式考场未绑定本故事监考教师')
      actorRole = `teacher${actorRole === 'A' ? 'B' : 'A'}`; bizType = 'EXAM_ROOM_STUDENT'; bizId = match[1]; studentId = match[2]; action = 'EXAM_ATTENDANCE_PRESENT'
    }
    if (actorRole) {
      const account = fixture.accounts[actorRole]
      let rows = auditRows({ tenantId: fixture.tenantId, bizType, bizId, action, account, studentId })
      const previousCollegeAudits = step.startsWith('G-college-') && report.graduationReapprovalAuditIds?.[bizId]
      if (previousCollegeAudits) {
        assert.deepEqual(rows.rows.slice(0, previousCollegeAudits.length).map(row => row.id), previousCollegeAudits,
          '重新预审前的学院初审审计必须完整保留')
        rows = { ...rows, rows: rows.rows.slice(previousCollegeAudits.length) }
      }
      if (step === 'G-archive' && report.graduationPartialArchive) {
        assert.equal(rows.rows[0]?.id, report.graduationPartialArchive.auditId, '首次部分归档审计必须保留')
        rows = { ...rows, rows: rows.rows.slice(1) }
      }
      const repeatEnrollment = action === 'SELECTION_ENROLL' && report.checkpoints.some(item => item.step === `R6-drop-${actorRole}`)
      const rescheduled = step === 'H-selection-exam-schedule-replan-A' && examReport.scheduleRecovery?.originalDate === '2027-07-05'
      if (rescheduled) {
        assert.equal(rows.rows.length, 2, '改期只允许原设时间及本次正式改期两条审计')
        assert.equal(rows.rows[0].id, examReport.scheduleRecovery.originalScheduleAuditId, '原考试时间审计必须保留')
      }
      if (repeatEnrollment) assert.equal(rows.rows.length, 2, '退课后仅允许一次真实重选审计')
      const audit = assertActor(rows,
        { roleCode: account.roleCode, pendingAt: report.pending?.step === step ? report.pending.sentAt : null,
          allowRepeated: step === 'G-precheck' || repeatEnrollment || rescheduled })
      proof = { ...proof, auditId: audit.id, actorUserId: account.userId }
    }
    if (report.pending?.step === step) report.pending = null
    report.checkpoints.push({ step, proof, observedAt: new Date().toISOString() }); await save()
  }
  const beforeWrite = async step => {
    const examStep = step.replace(/^H-selection-/, 'H-')
    const examReport = step.startsWith('H-selection-') ? report.selectionExamPlan : report
    const today = new Date().toLocaleDateString('sv-SE', { timeZone: 'Asia/Shanghai' })
    if (/^F-(score|submit|college|publish)-|^G-(final-|archive$)|^H-(confirm$|exam-batch-(finish|archive)$)/.test(examStep)) {
      assert.ok(today >= termInput.endDate, '原学期尚未结束；最终成绩、毕业终审及全校封存不能提前冒充发生')
    }
    if (examStep.startsWith('H-exam-attendance-')) {
      const roomId = examStep.match(/^H-exam-attendance-(\d+)-/)[1]
      const label = Object.keys(examReport.examRoomIds).find(key => examReport.examRoomIds[key] === roomId)
      const examDate = report.checkpoints.findLast(item => item.step === `${step.startsWith('H-selection-') ? 'H-selection' : 'H'}-exam-schedule-${label}` || (step.startsWith('H-selection-') && item.step === `H-selection-exam-schedule-replan-${label}`))?.proof.examDate
      assert.ok(examDate && today >= examDate, '尚未到原考场实际考试日期，不得提前登记到考')
    }
    assert.equal(report.pending, null, '前一命令结果尚未核对，禁止自动重放或继续写入')
    report.pending = { step, sentAt: new Date().toISOString() }; await save()
  }
  const failures = [], receipts = [], accessTokens = {}
  await phase('启动隔离浏览器')
  const { chromium } = await import('playwright')
  const browser = await chromium.launch({ headless: process.env.PW_HEADED !== 'true', channel: process.env.E2E_BROWSER_CHANNEL || 'msedge' })
  const contexts = []
  let activePage = null, authenticated = false
  const read = async response => {
    assert.equal(new URL(response.url()).origin, new URL(api).origin, '浏览器实际请求未到隔离后端')
    assert.equal(response.status(), 200, '正式接口未成功')
    const body = await response.json(); assert.equal(body.code, 0, '正式接口业务拒绝')
    return body.data
  }
  const responseFor = (page, pathname, method = 'GET') => page.waitForResponse(response => {
    const url = new URL(response.url())
    return url.pathname === pathname && response.request().method() === method
  }, { timeout: 120_000 })
  const readOnly = async (role, pathname) => {
    const response = await pages[role].context().request.get(`${new URL(api).origin}${pathname}`, {
      headers: { Authorization: `Bearer ${accessTokens[role]}` },
    })
    return read(response)
  }
  const visit = async (page, target, pathname, reload = false) => {
    activePage = page
    // Finish the prior document's write-related readback before observing a new navigation.
    await page.waitForLoadState('networkidle')
    const response = responseFor(page, pathname)
    const destination = new URL(staff + target)
    const current = new URL(page.url())
    await (reload && current.pathname + current.search === destination.pathname + destination.search
      ? page.reload() : page.goto(destination.toString()))
    const value = await read(await response)
    const skip = page.getByRole('button', { name: '跳过引导', exact: true })
    if (await skip.isVisible().catch(() => false)) await skip.click()
    return value
  }
  const capture = async (page, name) => {
    assert.ok(!new URL(page.url()).pathname.endsWith('/login'), '登录界面禁止截图')
    await page.screenshot({ path: path.join(evidenceDir, `${name}.png`), fullPage: false, animations: 'disabled', mask: [page.locator('.uchip, input, textarea, table tbody tr td:nth-child(-n+2)')] })
  }
  const login = async role => {
    authenticated = false
    const context = await browser.newContext({ viewport: { width: 1440, height: 1100 }, locale: 'zh-CN', timezoneId: 'Asia/Shanghai' })
    contexts.push(context)
    const page = await context.newPage(); activePage = page; page.setDefaultTimeout(120_000)
    page.on('pageerror', error => {
      const locations = (String(error.stack || '').match(/https?:\/\/[^\s)]+/g) || []).map(value => {
        try { const url = new URL(value); return url.origin === new URL(staff).origin && /^\/(src\/|node_modules\/\.vite\/deps\/)[A-Za-z0-9_./-]+\.(vue|js|mjs)(:\d+:\d+)?$/.test(url.pathname) ? url.pathname : null } catch { return null }
      }).filter(Boolean)
      failures.push({ role, kind: '页面脚本错误', errorName: ['Error', 'TypeError', 'ReferenceError', 'SyntaxError', 'RangeError'].includes(error.name) ? error.name : 'Error', codeLocation: locations[0] || null })
    })
    page.on('response', response => {
      const url = new URL(response.url())
      if (!url.pathname.startsWith('/api/v1/')) return
      if (url.origin !== new URL(api).origin) failures.push({ role, kind: '后端目标错误' })
      if (response.status() >= 400) failures.push({ role, path: url.pathname, status: response.status() })
      if (url.pathname.startsWith(apiPath)) receipts.push({ role, method: response.request().method(), path: url.pathname, status: response.status() })
    })
    const account = fixture.accounts[role], helper = new StaffLoginPage(page, staff)
    await helper.login({ tenant: fixture.tenantCode, username: account.loginName, password: credentials[account.loginName].password })
    const claims = decodeJwt(helper.lastAccessToken)
    assert.equal(String(claims.tenantId), fixture.tenantId)
    assert.equal(String(claims.userId).replace(/^db-/, ''), account.userId)
    assert.equal(claims.currentRoleCode, account.roleCode)
    assert.equal(claims.activeContextId, account.contextId)
    accessTokens[role] = helper.lastAccessToken
    helper.lastAccessToken = ''; authenticated = true
    await page.waitForLoadState('networkidle')
    assert.equal(failures.length, 0, '登录或运行目标核验失败')
    if (['collegeA', 'collegeB'].includes(role)) {
      assert.equal(new URL(page.url()).pathname, '/admin/academic-affairs', '学院正常登录应默认进入本学院教务首页')
      await expect(page.getByRole('heading', { name: '本学院教学运行', exact: true })).toBeVisible()
      const refreshed = responseFor(page, `${apiPath}/flow`)
      await page.reload()
      const flow = await read(await refreshed)
      const collegeId = fixture.colleges[role === 'collegeA' ? 'A' : 'B'].collegeId
      assert.equal(flow.viewer.scopeType, 'COLLEGE')
      assert.deepEqual(flow.viewer.collegeIds, [collegeId], '学院首页刷新后仍只能显示本院范围')
      await expect(page.getByRole('heading', { name: '本学院教学运行', exact: true })).toBeVisible()
      report.loginLandings ||= {}
      report.loginLandings[role] = { path: new URL(page.url()).pathname, scopeType: flow.viewer.scopeType, collegeIds: flow.viewer.collegeIds, refreshed: true }
      await save(); await capture(page, `R3-${role}-正常登录与刷新`)
    }
    return page
  }
  const pages = {}
  assert.ok(process.env.E2E_STUDENT_BASE_URL, '必须显式配置已核验的隔离学生门户；配置不代表已获准启动')
  const studentBase = isolatedUrl('E2E_STUDENT_BASE_URL', '', closedJourney ? '5201' : '5200', '') + '/portal'
  const preparation = JSON.parse(await fs.readFile(ignoredFile(process.env.E2E_V5_STUDENTS), 'utf8'))
  assert.equal(preparation.prefix, fixture.prefix)
  assert.equal(typeof preparation.tenantId, 'string')
  assert.equal(preparation.tenantId, fixture.tenantId)
  if (closedJourney) {
    assert.equal(preparation.scenarioId, journeyInput.scenarioId)
    assert.equal(preparation.termId, report.termId)
  }
  const loginStudents = async (supplies = [], supplyOwners = []) => {
    const studentPages = []
    const studentKeys = ['A', 'B'].flatMap(label => [1, 2].map(ordinal => `${fixture.prefix}${label}${ordinal}`))
    assert.deepEqual(Object.keys(preparation.studentLoginCredentials || {}).sort(), studentKeys.sort(), '四名原学生凭据不完整')
    for (const label of ['A', 'B']) for (let ordinal = 1; ordinal <= 2; ordinal++) {
      const key = `${fixture.prefix}${label}${ordinal}`
      const credential = preparation.studentLoginCredentials?.[key]
      const activation = preparation.studentActivationReceipts?.[key]
      assert.equal(credential?.mustChangePassword, false); assert.equal(activation?.completed, true)
      assert.equal(credential.tenantCode, fixture.tenantCode)
      assert.equal(credential.loginName, key); assert.equal(typeof credential.password, 'string'); assert.ok(credential.password.length > 0)
      assert.equal(activation.newLogin.roleCode, 'STUDENT')
      const context = await browser.newContext({ viewport: { width: 1440, height: 1100 }, locale: 'zh-CN', timezoneId: 'Asia/Shanghai' })
      contexts.push(context); const page = await context.newPage(); activePage = page
      authenticated = false
      page.on('pageerror', () => failures.push({ role: key, kind: '页面脚本错误' }))
      page.on('response', response => {
        const url = new URL(response.url())
        if (!url.pathname.startsWith('/api/v1/')) return
        if (url.origin !== new URL(api).origin) failures.push({ role: key, kind: '后端目标错误' })
        if (response.status() >= 400) failures.push({ role: key, path: url.pathname, status: response.status() })
        receipts.push({ role: key, method: response.request().method(), path: url.pathname, status: response.status() })
      })
      const helper = new StudentLoginPage(page, studentBase)
      await helper.login({ tenant: credential.tenantCode, username: credential.loginName, password: credential.password })
      const claims = decodeJwt(helper.lastAccessToken)
      assert.equal(String(claims.tenantId), fixture.tenantId)
      assert.equal(String(claims.userId), String(activation.newLogin.userId))
      assert.equal(claims.currentRoleCode, 'STUDENT')
      assert.equal(claims.studentId, fixture.colleges[label].studentIds[ordinal - 1], '实际登录未对应原学院原学生编号')
      helper.lastAccessToken = ''
      fixture.accounts[key] = { loginName: credential.loginName, userId: String(claims.userId).replace(/^db-/, ''), roleCode: claims.currentRoleCode }
      const supply = supplies[supplyOwners.indexOf(label)]
      studentPages.push({ key, label, ordinal, page, supply, studentId: claims.studentId })
    }
    assert.equal(new Set(studentPages.map(item => item.studentId)).size, 4, '四个登录必须对应四名不同的原学生')
    assert.equal(failures.length, 0, '学生登录或后端目标未验证通过，不发布选课批次')
    authenticated = true; return studentPages
  }
  const finishReadback = async studentPages => {
    await phase('封存后六种正常职责与四名学生刷新回读')
    const isBusinessWrite = row => ['POST', 'PUT', 'PATCH', 'DELETE'].includes(row.method)
      && (row.path.startsWith(apiPath) || row.path.startsWith('/api/v1/portal/academic/'))
    const businessWrites = () => receipts.filter(isBusinessWrite).length
    const readbackWriteAttempts = []
    for (const page of [...roles.map(role => pages[role]), ...studentPages.map(item => item.page)]) {
      page.on('request', request => {
        const row = { method: request.method(), path: new URL(request.url()).pathname }
        if (isBusinessWrite(row)) readbackWriteAttempts.push(row)
      })
    }
    const writesBeforeReadback = businessWrites()
    for (const role of roles) {
      const page = pages[role], expectedScope = report.roles.find(item => item.role === role).reads[0]
      for (const reload of [false, true]) {
        const flow = await visit(page, `/admin/academic-affairs?termId=${report.termId}`, `${apiPath}/flow`, reload)
        assert.equal(flow.term.termId, report.termId); assert.equal(flow.term.status, 'ARCHIVED')
        assert.equal(flow.viewer.scopeType, expectedScope.scopeType)
        assert.deepEqual(flow.viewer.collegeIds, expectedScope.collegeIds)
        await expect(page.locator('[aria-label="学期责任接力"]')).toBeVisible()
      }
      await capture(page, `终态-${role}-封存后刷新`)
      await observed(`final-read-${role}`, { termId: report.termId, termStatus: 'ARCHIVED', scopeType: expectedScope.scopeType, refreshed: true })
    }
    for (const { page, studentId } of studentPages) {
      for (const reload of [false, true]) {
        const response = responseFor(page, '/api/v1/portal/academic/graduation-audit')
        if (reload) await page.reload()
        else await page.goto(`${studentBase}/academic/graduation`)
        const result = await read(await response)
        assert.equal(result.progress.hasAudit, true); assert.equal(result.progress.conclusion, 'GRADUATED')
        await expect(page.getByRole('heading', { name: '已形成毕业结论', exact: true })).toBeVisible()
      }
      await capture(page, `终态-学生${studentId}-毕业结果刷新`)
      await observed(`final-read-student-${studentId}`, { studentId, conclusion: 'GRADUATED', refreshed: true })
    }
    assert.equal(businessWrites(), writesBeforeReadback, '封存后结果回读不得触发业务写入')
    assert.deepEqual(readbackWriteAttempts, [], '封存后只读回读不得尝试业务写入，包括尚未响应的请求')
    report.uncovered = []; await save()
    assert.equal(failures.length, 0, '实际页面或接口存在错误')
    assert.equal(report.pending, null); report.passed = true; report.phase = '场景 A 至 H 完成'
  }
  const stage = (flow, label) => {
    const unit = flow.unitProgress.find(item => item.collegeId === fixture.colleges[label].collegeId)
    assert.ok(unit, '学校责任总览缺少场景学院')
    const taskStage = unit.stages.find(item => item.stageCode === 'F40_TEACHING_TASK')
    assert.ok(taskStage, '学院教学任务阶段缺失')
    return taskStage
  }
  const batchFacts = async (page, batchId) => {
    const base = `${apiPath}/teaching-task-batches/${batchId}`
    const workbenchResponse = responseFor(page, `${base}/workbench`)
    const tasksResponse = responseFor(page, `${base}/tasks`)
    await page.goto(`${staff}/admin/academic-affairs/teaching-tasks/${batchId}`)
    const [workbench, tasks] = await Promise.all([read(await workbenchResponse), read(await tasksResponse)])
    assert.equal(workbench.batchId, batchId)
    assert.equal(Number(tasks.total), tasks.items.length, '本批次任务未读全，禁止按不完整列表办理')
    return { workbench, tasks: tasks.items }
  }
  const choose = async (scope, label, value) => {
    const formItems = scope.locator('.app-form-item').filter({ has: scope.page().locator('label').filter({ hasText: label }) })
    const picker = await formItems.count() ? formItems.locator('.app-remote-select') : scope.locator('label').filter({ hasText: label }).locator('.app-remote-select')
    await expect(picker).toHaveCount(1)
    const control = picker.getByRole('combobox')
    if ((await control.innerText()).includes(value)) return
    if (await control.getAttribute('aria-expanded') !== 'true') await control.press('Enter')
    await picker.getByRole('option').filter({ hasText: value }).click()
  }
  try {
    await phase('正常学校账号登录')
    const school = await login('school')
    pages.school = school
    if (closedJourney && (previousRun.pending?.step === 'H-confirm' || report.checkpoints.some(item => item.step === 'H' && item.proof.termStatus === 'ARCHIVED'))) {
      assert.equal(path.basename(fixtureFile), 'v5closed02-state.json')
      assert.ok(report.pending === null || report.pending.step === 'H-confirm')
      assert.deepEqual(previousRoleEvidence.map(item => item.role).sort(), [...roles].sort())
      report.roles = previousRoleEvidence
      const checked = report.checkpoints.filter(item => item.step === 'H-check').at(-1)
      assert.equal(checked.proof.batchId, report.archiveBatchId)
      assert.equal(checked.proof.domains.length, 13)
      assert.ok(checked.proof.domains.every(item => ['PASS', 'NOT_APPLICABLE'].includes(item.result)))
      const archive = await readOnly('school', `${apiPath}/archive/batches/${report.archiveBatchId}`)
      const term = await readOnly('school', `${apiPath}/terms/${report.termId}`)
      assert.equal(archive.termId, report.termId); assert.equal(archive.status, 'ARCHIVED')
      assert.equal(term.status, 'ARCHIVED')
      const manifest = await readOnly('school', `${apiPath}/archive/batches/${report.archiveBatchId}/manifest/verify`)
      assert.equal(manifest.ok, true); assert.equal(manifest.versions.length, 1)
      await observed('H-confirm', { batchId: report.archiveBatchId, status: archive.status, manifestVerified: true })
      await observed('H', { termId: report.termId, batchId: report.archiveBatchId, termStatus: term.status })
      for (const role of roles.filter(role => role !== 'school')) pages[role] = await login(role)
      await finishReadback(await loginStudents())
      return
    }
    // Read-only authorization calculation: an older receipt from another
    // database cannot certify this instance's narrowed college templates.
    await phase('第九阶段：学院校级动作收窄门禁')
    report.authorityGate = { permissionCode: 'academicAffairs.timeslot.manage', checks: [], verified: false }
    for (const role of ['collegeA', 'collegeB']) {
      pages[role] = await login(role)
      const checked = await pages[role].context().request.post(`${new URL(api).origin}/api/v1/authz/check`, {
        headers: { Authorization: `Bearer ${accessTokens[role]}` }, data: { permissionCode: report.authorityGate.permissionCode },
      })
      const decision = await read(checked)
      assert.equal(typeof decision.allowed, 'boolean', '权限计算未返回明确裁决')
      report.authorityGate.checks.push({ role, allowed: decision.allowed }); await save()
    }
    report.authorityGate.verified = report.authorityGate.checks.every(item => item.allowed === false)
    await save()
    assert.equal(report.authorityGate.verified, true, '当前隔离库学院仍持校级作息管理权限；第九阶段未完成，停止所有新增业务写入')
    const schoolColleges = await readOnly('school', `${apiPath}/orgs/colleges?page=1&pageSize=100`)
    assert.deepEqual(schoolColleges.items?.map(row => row.id).sort(),
      Object.values(fixture.colleges).map(row => row.collegeId).sort(),
      '隔离学校必须只有本场景两学院，禁止把其他学院从全校门禁中排除')
    await phase('学校核对并建立正式学期')
    const catalog = await visit(school, '/admin/academic-affairs/terms', `${apiPath}/terms`)
    const terms = catalog.items || []
    assert.ok(Number(catalog.total ?? terms.length) <= terms.length, '学期列表未读全，请先通过分页核对已有对象，禁止猜测新建')
    const matches = terms.filter(row => row.yearCode === termInput.yearCode && row.termNo === termInput.termNo)
    assert.ok(matches.length <= 1, '同学年学期存在多个对象，需要核对正式数据')
    let term = report.termId ? terms.find(row => row.termId === report.termId) : matches[0]
    if (report.termId) assert.ok(term, '已记录学期不在正式列表，禁止重新创建')
    if (!term) {
      await school.getByRole('button', { name: '新建学期', exact: true }).click()
      await school.locator('#aa-term-year').fill(termInput.yearCode)
      await school.locator('#aa-term-number').selectOption(String(termInput.termNo))
      await school.locator('#aa-term-name').fill(`${objectPrefix} 学期责任接力`)
      await school.getByLabel('开学日期', { exact: true }).fill(termInput.startDate)
      await school.getByLabel('结束日期', { exact: true }).fill(termInput.endDate)
      await school.locator('#aa-term-weeks').fill(String(termInput.teachingWeeks)); await school.locator('#aa-term-exam-week').fill(String(termInput.examWeekStart))
      await beforeWrite('term')
      const created = responseFor(school, `${apiPath}/terms`, 'POST')
      await school.getByRole('button', { name: '创建学期草稿', exact: true }).click()
      term = await read(await created); assert.equal(typeof term.termId, 'string')
      report.termId = term.termId; await save()
    } else { report.termId = term.termId; await save() }
    term = await visit(school, `/admin/academic-affairs/terms/${report.termId}`, `${apiPath}/terms/${report.termId}/workspace`)
    assert.equal(term.termId, report.termId, '学期详情必须返回本场景学期')
    for (const [key, value] of Object.entries(termInput)) {
      const actual = ['startDate', 'endDate'].includes(key) ? String(term[key] || '').slice(0, 10) : term[key]
      assert.equal(actual, value, '已有学期必须与场景正式前置条件一致')
    }
    await observed('term', { termId: term.termId, status: term.status })
    await capture(school, 'A01-学校正式学期')

    await phase('学校核对并维护本学期校历')
    const calendarPath = `/admin/academic-affairs/calendar?termId=${report.termId}&tab=holiday`
    let events = (await visit(school, calendarPath, `${apiPath}/terms/${report.termId}/calendar`)).items || []
    const holiday = events.find(row => row.eventType === 'HOLIDAY' && String(row.startDate).slice(0, 10) === holidayDate && String(row.endDate).slice(0, 10) === holidayDate)
    if (!holiday) {
      assert.equal(term.status, 'DRAFT', '已发布学期缺少目标校历事件，禁止改旧终态或重复创建学期')
      await school.getByRole('button', { name: '新增节假日', exact: true }).click()
      const form = school.locator('.aa-cal-form:visible')
      for (const label of ['开始日期', '结束日期']) {
        const input = form.locator('label').filter({ hasText: label }).locator('input')
        await input.fill(holidayDate); await input.press('Tab')
      }
      await form.getByPlaceholder('选填，如 国庆假期 / 国庆调休').fill(`${objectPrefix} 校历核验`)
      await beforeWrite('calendar')
      const added = responseFor(school, `${apiPath}/terms/${report.termId}/calendar`, 'POST')
      await form.getByRole('button', { name: '添加', exact: true }).click()
      const event = await read(await added); assert.equal(typeof event.eventId, 'string'); report.eventId = event.eventId; await save()
    } else report.eventId = String(holiday.eventId)
    events = (await visit(school, calendarPath, `${apiPath}/terms/${report.termId}/calendar`, true)).items || []
    assert.ok(events.some(row => String(row.eventId) === report.eventId && row.eventType === 'HOLIDAY'))
    await observed('calendar', { termId: report.termId, eventId: report.eventId })
    await capture(school, 'A02-校历同学期刷新')

    await phase('学校核对并维护正式作息')
    await visit(school, '/admin/academic-affairs/time-slots', `${apiPath}/time-slots`)
    const template = school.locator('details.aa-slot-template')
    await template.locator('summary').click()
    const previewRequest = responseFor(school, `${apiPath}/time-slots/template-preview`, 'POST')
    await template.getByRole('button', { name: '检查当前作息', exact: true }).click()
    const preview = await read(await previewRequest)
    assert.equal(preview.blockedCount, 0, '原作息存在冲突，禁止覆盖')
    if (preview.readyCount > 0) {
      await beforeWrite('slots')
      await template.getByRole('button', { name: `创建 ${preview.readyCount} 个缺失节次`, exact: true }).click()
      await expect(template.getByRole('button', { name: '创建 0 个缺失节次', exact: true })).toBeVisible({ timeout: 120_000 })
    }
    const slots = (await visit(school, '/admin/academic-affairs/time-slots', `${apiPath}/time-slots`, true)).items || []
    for (const item of preview.items) {
      const slot = slots.find(row => row.slotNo === item.desired.slotNo)
      assert.ok(slot && slot.enabled, '正式作息节次缺失或停用')
      assert.equal(slot.startTime?.slice(0, 5), item.desired.startTime); assert.equal(slot.endTime?.slice(0, 5), item.desired.endTime)
    }
    report.slotIds = slots.map(row => String(row.slotId)); await observed('slots', { slotIds: report.slotIds })
    await capture(school, 'A03-正式作息刷新')

    await phase('学校核验并发布本学期校历')
    const publishTerm = await visit(school, `/admin/academic-affairs/calendar?termId=${report.termId}&tab=publish`, `${apiPath}/terms/${report.termId}/workspace`)
    assert.equal(publishTerm.termId, report.termId, '校历发布依据必须属于本场景学期')
    await expect(school.locator('.aa-publish-evidence')).toBeVisible({ timeout: 120_000 })
    if (term.status === 'DRAFT') {
      const publish = school.getByRole('button', { name: '核验并发布校历', exact: true }).first()
      await expect(publish).toBeEnabled(); await publish.click()
      const dialog = school.getByRole('dialog', { name: '发布校历', exact: true })
      await expect(dialog).toContainText(report.termId)
      await beforeWrite('publish')
      const published = responseFor(school, `${apiPath}/terms/${report.termId}/calendar/publish`, 'POST')
      await dialog.getByRole('button', { name: '确认发布', exact: true }).click()
      const result = await read(await published); assert.equal(result.termId, report.termId); assert.equal(result.status, 'PUBLISHED')
    }
    const currentResponse = responseFor(school, `${apiPath}/terms/current`).then(read)
    term = await visit(school, `/admin/academic-affairs/terms/${report.termId}`, `${apiPath}/terms/${report.termId}/workspace`)
    const currentTerm = await currentResponse
    assert.equal(term.termId, report.termId); assert.equal(term.status, 'PUBLISHED'); assert.equal(currentTerm.termId, report.termId)
    await observed('publish', { termId: report.termId, status: term.status, currentTermId: currentTerm.termId })
    await capture(school, 'A04-学期发布与当前学期')

    for (const role of roles) {
      await phase(`正常角色首页范围核对：${role}`)
      const page = pages[role] || await login(role)
      pages[role] = page
      const account = fixture.accounts[role]
      const evidence = { role, userId: account.userId, reads: [] }
      for (const reload of [false, true]) {
        const flow = await visit(page, `/admin/academic-affairs?termId=${report.termId}`, `${apiPath}/flow`, reload)
        assert.equal(flow.term.termId, report.termId)
        const surface = page.locator('[aria-label="学期责任接力"]')
        await expect(surface).toBeVisible(); await expect(surface).not.toContainText('责任进度读取失败')
        if (role === 'school' || role === 'leader') {
          assert.ok(['TENANT_ALL', 'SCHOOL'].includes(flow.viewer.scopeType))
          for (const college of Object.values(fixture.colleges)) assert.ok(flow.unitProgress.some(unit => unit.collegeId === college.collegeId))
          await expect(surface.getByRole('heading', { name: '学校教学运行总控', exact: true })).toBeVisible()
          await expect(surface.getByRole('heading', { name: '各学院并行进度', exact: true })).toBeVisible()
          if (role === 'leader') {
            assert.deepEqual(flow.viewer.majorIds, [])
            assert.deepEqual(flow.viewer.assignments, [])
            assert.deepEqual(flow.currentResponsibilities, [])
            const stages = [...flow.stages, ...flow.unitProgress.flatMap(unit => unit.stages)]
            assert.ok(stages.every(stage => !stage.responsibility?.assigneeUserIds?.includes(account.userId)), '学校只读观察员不能成为当前办理人')
            assert.ok(stages.every(stage => !stage.primaryAction || /^查看/.test(stage.primaryAction.label)), '学校只读观察员只能获得查看入口')
            await expect(surface.locator('[aria-label="我的责任事项"]')).toHaveCount(0)
            await expect(surface.getByRole('button', { name: /^(新建|生成|提交|保存|确认|通过|退回|审批|发布|封存|处理)/ })).toHaveCount(0)
            assert.equal(receipts.filter(row => row.role === 'leader' && row.method !== 'GET').length, 0, '学校只读观察员不得发出教务写请求')
          }
        } else if (role.startsWith('college')) {
          const collegeId = fixture.colleges[role.endsWith('A') ? 'A' : 'B'].collegeId
          assert.equal(flow.viewer.scopeType, 'COLLEGE'); assert.deepEqual(flow.viewer.collegeIds, [collegeId])
          assert.ok(flow.unitProgress.every(unit => unit.collegeId === collegeId)); assert.equal(flow.schoolGates.length, 0)
          await expect(surface.getByRole('heading', { name: '本学院教学运行', exact: true })).toBeVisible()
        } else if (role.startsWith('teacher')) {
          assert.equal(flow.viewer.scopeType, 'ASSIGNED'); assert.equal(flow.unitProgress.length, 0); assert.equal(flow.schoolGates.length, 0)
          assert.ok(flow.currentResponsibilities.every(stage => stage.responsibility.assigneeUserIds.includes(account.userId)))
          await expect(surface.getByRole('heading', { name: '我的教学责任', exact: true })).toBeVisible()
        }
        if (!['school', 'leader'].includes(role)) await expect(surface.getByRole('heading', { name: '各学院并行进度', exact: true })).toHaveCount(0)
        evidence.reads.push({ refresh: reload, termId: flow.term.termId, scopeType: flow.viewer.scopeType, collegeIds: flow.viewer.collegeIds, majorIds: flow.viewer.majorIds, currentResponsibilityCount: flow.currentResponsibilities.length, stages: flow.stages.map(stage => ({ code: stage.stageCode, status: stage.status })) })
        await capture(page, `A05-${role}-${reload ? '刷新' : '进入'}`)
      }
      report.roles.push(evidence); await save()
    }
    if (report.pending?.step === 'G-archive') {
      assert.equal(path.basename(fixtureFile), 'v5closed02-state.json')
      const batchId = report.graduationBatchId
      assert.match(String(batchId), /^[1-9]\d*$/)
      const batches = (await readOnly('school', `${apiPath}/graduation-audit-batches?batchId=${batchId}&page=1&pageSize=1`)).items
      assert.equal(batches.length, 1); assert.equal(batches[0].batchId, batchId)
      assert.equal(batches[0].status, 'PRECHECKED')
      const results = (await readOnly('school', `${apiPath}/graduation-audit-batches/${batchId}/results?page=1&pageSize=20`)).items
      assert.equal(results.length, 4); assert.ok(results.every(result => result.status === 'ARCHIVED'))
      assert.deepEqual(results.map(result => result.studentId).sort(), Object.values(fixture.colleges).flatMap(college => college.studentIds).sort())
      const evidence = auditRows({ tenantId: fixture.tenantId, bizType: 'AA_GRAD_AUDIT',
        bizId: batchId, action: 'ARCHIVE', account: fixture.accounts.school })
      const audit = assertActor(evidence, { roleCode: fixture.accounts.school.roleCode, pendingAt: report.pending.sentAt })
      report.graduationPartialArchive = { batchId, auditId: audit.id,
        resultIds: results.map(result => result.resultId), originalCommand: report.pending }
      report.pending = null; await save()
    }
    if (closedJourney) {
      await phase('已结束学期：学校与两学院接力办理原四名学生注册')
      report.registration ||= { scenarioId: journeyInput.scenarioId, termId: report.termId, batchId: null, actions: {}, reads: [] }
      const registration = report.registration
      assert.equal(registration.scenarioId, journeyInput.scenarioId); assert.equal(registration.termId, report.termId)
      assert.equal(report.pending, null, '注册原命令仍待核对，不允许重放')
      for (const step of Object.keys(registration.actions)) assert.equal(registrationResumeAction(registration, step, report.pending), false)
      const registrationBase = `${apiPath}/registration-batches`
      // 只读3314：创建响应没有termId，正式绑定及本次操作者必须从服务端事实独立核实。
      const registrationProof = (batchId, audits = [], role = 'school', sentAt = null) => {
        const account = fixture.accounts[role]
        const result = JSON.parse(execFileSync(process.env.E2E_V5_PYTHON, ['-c', String.raw`
import json, os, sys
from datetime import datetime, timedelta
from urllib.parse import urlsplit, unquote
import pymysql
u = urlsplit(os.environ['DATABASE_URL'])
assert (u.scheme, u.hostname, u.port, u.path) == ('mysql+pymysql', '127.0.0.1', 3314, '/student_lifecycle_v5_e2e')
tenant, batch_id, descriptors, user_id, login_name, sent_at = sys.argv[1:7]
assert tenant.isdecimal() and batch_id.isdecimal() and user_id.isdecimal()
conn = pymysql.connect(host=u.hostname, port=u.port, user=unquote(u.username or ''), password=unquote(u.password or ''), database=u.path[1:], charset='utf8mb4', autocommit=False)
try:
    with conn.cursor() as cur:
        cur.execute('START TRANSACTION READ ONLY')
        cur.execute('SELECT term_id, status, batch_name FROM t_aa_registration_batch WHERE tenant_id=%s AND id=%s AND is_deleted=0', (tenant, batch_id))
        batch = cur.fetchone(); assert batch
        cur.execute('SELECT student_id, status, eligibility_status, id FROM t_aa_registration WHERE tenant_id=%s AND batch_id=%s AND is_deleted=0 ORDER BY student_id', (tenant, batch_id))
        records = [{'studentId':str(r[0]), 'status':r[1], 'eligibilityStatus':r[2], 'registrationId':str(r[3])} for r in cur.fetchall()]
        cur.execute('SELECT id, student_id, status FROM t_aa_registration_exception WHERE tenant_id=%s AND batch_id=%s AND is_deleted=0 ORDER BY id', (tenant, batch_id))
        exceptions = [{'exceptionId':str(r[0]), 'studentId':str(r[1]), 'status':r[2]} for r in cur.fetchall()]
        cur.execute('SELECT real_name, login_name FROM t_user WHERE tenant_id=%s AND id=%s AND is_deleted=0', (tenant, user_id))
        identity = cur.fetchone(); assert identity and identity[1] == login_name
        evidence = []
        for descriptor in json.loads(descriptors):
            kind, object_id, action, detail = descriptor
            assert kind in ('AA_REG_BATCH','AA_REGISTRATION','AA_REG_EXCEPTION') and action in ('CREATE','ELIGIBILITY_VERIFY','REGISTER','RESOLVE','CLOSE','ARCHIVE') and str(object_id).isdecimal()
            since = datetime.fromisoformat(sent_at.replace('Z','+00:00')).replace(tzinfo=None) - timedelta(seconds=2)
            cur.execute('SELECT id, operator, role_name, occurred_at FROM t_affairs_audit_trail WHERE tenant_id=%s AND biz_type=%s AND biz_id=%s AND action=%s AND occurred_at>=%s AND detail LIKE %s ORDER BY id', (tenant,kind,object_id,action,since,detail or '%'))
            evidence.append({'operator':identity[0] or user_id, 'rows':[{'id':str(r[0]),'operator':r[1],'role':r[2],'occurredAt':r[3].isoformat()} for r in cur.fetchall()]})
        print(json.dumps({'termId':str(batch[0]), 'status':batch[1], 'batchName':batch[2], 'records':records, 'exceptions':exceptions, 'audits':evidence}))
finally:
    conn.rollback(); conn.close()
`, fixture.tenantId, String(batchId), JSON.stringify(audits), account.userId, account.loginName, sentAt || ''],
        { cwd: root, env: process.env, encoding: 'utf8', windowsHide: true, timeout: 30_000, stdio: ['ignore', 'pipe', 'ignore'] }))
        assert.equal(result.termId, report.termId, '注册批次实际绑定必须属于新学期')
        return result
      }
      const registrationWrite = async (step, role, pathname, click, descriptors) => {
        if (!registrationResumeAction(registration, step, report.pending)) return registration.actions[step].receipt
        await beforeWrite(step)
        const sentAt = report.pending.sentAt, response = responseFor(pages[role], pathname, 'POST')
        await click()
        const receipt = await read(await response)
        // 先存正式返回编号；回读或审计失败时保留pending，不重建、不重放。
        registration.actions[step] = { receipt, role, sentAt }; await save()
        if (!registration.batchId) registration.batchId = String(receipt.batchId)
        await save()
        const proof = registrationProof(registration.batchId, descriptors(receipt), role, sentAt)
        registration.actions[step].audits = proof.audits.map(evidence => assertActor(evidence, { roleCode: fixture.accounts[role].roleCode, pendingAt: sentAt }))
        registration.actions[step].observedAt = new Date().toISOString(); await save()
        await observed(step, { batchId: registration.batchId, termId: proof.termId, status: proof.status, auditIds: registration.actions[step].audits.map(row => row.id) })
        return receipt
      }
      const listPath = `/admin/academic-affairs/registration?type=SEMESTER&termId=${report.termId}`
      await visit(school, listPath, registrationBase)
      const batchName = `${objectPrefix} 学期注册`
      if (!registration.batchId) {
        assert.equal(report.pending, null)
        await school.getByRole('button', { name: '创建学期注册批次', exact: true }).click()
        await school.getByPlaceholder('如 2026级新生入学注册').fill(batchName)
        await expect(school.locator('.aa-cal-form .app-remote-select').getByRole('combobox')).toContainText(`${objectPrefix} 学期责任接力`)
        await school.getByLabel('创建后立即开放').check()
        await registrationWrite('registration-create', 'school', registrationBase,
          () => school.getByRole('button', { name: '创建', exact: true }).click(), receipt => [['AA_REG_BATCH', receipt.batchId, 'CREATE', 'SEMESTER']])
      }
      const batchId = registration.batchId
      assert.equal(registrationProof(batchId).batchName, batchName)
      registration.exceptionId ||= registration.actions['registration-ineligible']?.receipt.exceptionId
      const eligibilityPath = `${registrationBase}/${batchId}/eligibility`
      const eligibilityTarget = `/admin/academic-affairs/registration/workbench?tab=eligibility&batchId=${batchId}`
      for (const label of ['A', 'B']) {
        const role = `college${label}`, page = pages[role], ids = fixture.colleges[label].studentIds
        const completed = registration.actions[`registration-register-${label}`]?.observedAt
        if (completed) continue
        const eligible = await visit(page, eligibilityTarget, eligibilityPath)
        assert.deepEqual(eligible.items.map(row => row.studentId).sort(), [...ids].sort(), '学院只能核验本院原两名学生')
        for (const studentId of ids) {
          const row = eligible.items.find(item => item.studentId === studentId)
          const selectStudent = async () => page.locator('.aarw-elig-item').filter({ hasText: row.studentNo }).click()
          if (label === 'A' && studentId === ids[0]) {
            if (!registration.actions['registration-ineligible']) {
              await selectStudent(); await page.getByRole('button', { name: '标记不合格', exact: true }).click()
              const drawer = page.getByRole('dialog', { name: '核验不合格', exact: true })
              await drawer.getByPlaceholder('不合格原因（将转入注册异常并通知辅导员）').fill('虚构验收：材料需补齐，验证原单恢复')
              const rejected = await registrationWrite('registration-ineligible', role, `${eligibilityPath}/${studentId}/verify`,
                () => drawer.getByRole('button', { name: '提交', exact: true }).click(), receipt => [['AA_REGISTRATION', receipt.registrationId, 'ELIGIBILITY_VERIFY', 'INELIGIBLE:%']])
              assert.equal(rejected.eligibilityStatus, 'INELIGIBLE'); assert.match(rejected.exceptionId, /^[1-9]\d*$/)
              registration.exceptionId = rejected.exceptionId; await save()
            }
            if (!registration.actions['registration-resolve']) {
              const exceptionsPath = `${apiPath}/registration/exceptions`
              await visit(page, `/admin/academic-affairs/registration/workbench?tab=exception&batchId=${batchId}`, exceptionsPath)
              const exceptionRow = page.getByRole('row').filter({ hasText: row.studentNo })
              await expect(exceptionRow).toHaveCount(1)
              await expect(exceptionRow.getByRole('button', { name: '处理', exact: true })).toBeEnabled()
              await exceptionRow.getByRole('button', { name: '处理', exact: true }).click()
              const dialog = page.getByRole('dialog', { name: '处理注册异常', exact: true })
              await dialog.getByLabel('处理说明', { exact: true }).fill('虚构材料已补齐，保留原批次重新核验')
              const resolved = await registrationWrite('registration-resolve', role, `${exceptionsPath}/${registration.exceptionId}/resolve`,
                () => dialog.getByRole('button', { name: '确认处理', exact: true }).click(), receipt => [['AA_REG_EXCEPTION', receipt.exceptionId, 'RESOLVE', '%']])
              assert.equal(resolved.status, 'RESOLVED'); assert.equal(resolved.studentId, studentId)
            }
            await visit(page, eligibilityTarget, eligibilityPath)
          }
          const step = `registration-eligible-${studentId}`
          if (!registration.actions[step]) {
            await selectStudent(); await page.getByRole('button', { name: '核验通过', exact: true }).click()
            const dialog = page.getByRole('dialog', { name: '核验通过', exact: true })
            const verified = await registrationWrite(step, role, `${eligibilityPath}/${studentId}/verify`,
              () => dialog.getByRole('button', { name: '确认', exact: true }).click(), receipt => [['AA_REGISTRATION', receipt.registrationId, 'ELIGIBILITY_VERIFY', 'ELIGIBLE:%']])
            assert.equal(verified.studentId, studentId); assert.equal(verified.eligibilityStatus, 'ELIGIBLE')
          }
        }
        const candidatesPath = `${registrationBase}/${batchId}/registration-candidates`
        const candidates = await visit(page, `/admin/academic-affairs/registration/${batchId}`, candidatesPath)
        assert.deepEqual(candidates.items.map(row => row.studentId).sort(), [...ids].sort())
        for (const row of candidates.items) await page.getByRole('checkbox', { name: `选择 ${row.realName || row.studentNo}` }).check()
        const previewResponse = responseFor(page, `${registrationBase}/${batchId}/bulk-register-preview`, 'POST')
        await page.getByRole('button', { name: '预览批量注册', exact: true }).click()
        const preview = await read(await previewResponse)
        assert.equal(preview.ready, 2); assert.equal(preview.blocked, 0)
        await expect(page.getByTestId('bulk-registration-preview')).toContainText('2 人可执行')
        await page.getByLabel(/我已核对本次名单和阻断原因/).check()
        const registered = await registrationWrite(`registration-register-${label}`, role, `${registrationBase}/${batchId}/bulk-register`,
          () => page.getByRole('button', { name: '确认注册 2 人', exact: true }).click(), receipt => receipt.items.map(item => ['AA_REGISTRATION', item.registrationId, 'REGISTER', '%']))
        assert.equal(registered.succeeded, 2); assert.equal(registered.failed, 0)
        assert.deepEqual(registered.items.map(row => row.studentId).sort(), [...ids].sort())
        await expect(page.getByTestId('bulk-registration-result')).toContainText('成功 2 人')
        await capture(page, `注册-${label}学院原两学生正式办理`)
      }
      const proof = registrationProof(batchId)
      assert.equal(proof.records.length, 4); assert.ok(proof.records.every(row => row.status === 'REGISTERED'))
      assert.equal(proof.exceptions.length, 1); assert.equal(proof.exceptions[0].status, 'RESOLVED')
      for (const [action, name, dialogName, status] of [['close', '关闭', '关闭注册批次', 'CLOSED'], ['archive', '归档', '归档注册批次', 'ARCHIVED']]) {
        const step = `registration-${action}`
        if (registration.actions[step]?.observedAt) continue
        await visit(school, listPath, registrationBase)
        await school.getByRole('row').filter({ hasText: batchName }).getByRole('button', { name, exact: true }).click()
        const dialog = school.getByRole('dialog', { name: dialogName, exact: true })
        const receipt = await registrationWrite(step, 'school', `${registrationBase}/${batchId}/${action}`,
          () => dialog.getByRole('button', { name: '确认', exact: true }).click(), value => [['AA_REG_BATCH', value.batchId, action.toUpperCase(), '%']])
        assert.equal(receipt.status, status)
      }
      registration.reads = []
      for (const role of ['school', 'collegeA', 'collegeB']) {
        const expectedIds = role === 'school' ? Object.values(fixture.colleges).flatMap(group => group.studentIds) : fixture.colleges[role.at(-1)].studentIds
        for (const reload of [false, true]) {
          const records = await visit(pages[role], `/admin/academic-affairs/registration/${batchId}`, `${registrationBase}/${batchId}/registrations`, reload)
          assert.equal(records.total, expectedIds.length); assert.deepEqual(records.items.map(row => row.studentId).sort(), [...expectedIds].sort())
          assert.ok(records.items.every(row => row.status === 'REGISTERED'))
          await expect(pages[role].locator('.aa-bulk__state')).toContainText('已归档')
          registration.reads.push({ role, refresh: reload, studentIds: records.items.map(row => row.studentId), status: registrationProof(batchId).status }); await save()
        }
        await capture(pages[role], `注册-${role}-原批次归档刷新`)
      }
      assert.ok(registration.reads.every(item => item.status === 'ARCHIVED'))
      registration.complete = true; await observed('registration-relay', { batchId, termId: report.termId, studentCount: 4, exceptionId: registration.exceptionId, refreshedRoleCount: 3 })
    }
    // 总册 B 的“学院 A 全部 READY”须落在教师确认及两级审核之后；
    // B 先检查 A 全部分配、B 恰有两条待分配，C 再推进 A 的正式 READY。
    for (const label of ['A', 'B']) {
      const role = `college${label}`, page = pages[role], collegeId = fixture.colleges[label].collegeId
      const batchName = `${objectPrefix} ${label}学院教学任务`
      await phase(`学院 ${label} 从已发布方案生成本学期教学任务`)
      const listed = await visit(page, `/admin/academic-affairs/teaching-tasks?termId=${report.termId}`, `${apiPath}/teaching-task-batches`)
      assert.equal(Number(listed.total), listed.items.length, '本学期批次未读全，禁止重复生成')
      const availableColleges = await readOnly(role, `${apiPath}/orgs/colleges?page=1&pageSize=100`)
      assert.ok(availableColleges.items?.some(item => item.id === collegeId), '开课责任学院不在当前办理人正式授权范围')
      const existing = listed.items.filter(item => item.batchName === batchName && item.termId === report.termId && item.collegeId === collegeId)
      assert.ok(existing.length <= 1, '同名学院批次重复，需人工核对')
      let batchId = report.batchIds[label] || existing[0]?.batchId
      if (report.batchIds[label]) assert.equal(existing[0]?.batchId, batchId, '已保存的批次未在正式列表中找到')
      if (!batchId) {
        await page.getByRole('button', { name: '从方案生成任务', exact: true }).click()
        const form = page.locator('section.app-section-card').filter({ hasText: '从已发布培养方案生成' })
        await choose(form, '学期', `${objectPrefix} 学期责任接力`)
        await choose(form, '开课责任学院', `V5 ${label === 'A' ? '甲' : '乙'}学院 ${fixture.prefix}`)
        await form.getByPlaceholder('选填，如 2026秋教学任务').fill(batchName)
        await beforeWrite(`batch-${label}`)
        const generated = responseFor(page, `${apiPath}/teaching-task-batches/generate`, 'POST')
        await form.getByRole('button', { name: '生成并检查', exact: true }).click()
        const result = await read(await generated)
        batchId = result.batchId; assert.equal(typeof batchId, 'string')
        report.batchIds[label] = batchId; await save()
      }
      const facts = await batchFacts(page, batchId)
      assert.equal(facts.workbench.termId, report.termId)
      assert.equal(facts.workbench.collegeId, collegeId)
      assert.ok(facts.tasks.length >= (label === 'B' ? 2 : 1), '来源培养方案尚未形成足量正式任务；须先准备课程、已发布并绑定的方案')
      report.taskIds[label] = facts.tasks.map(item => item.taskId)
      await observed(`batch-${label}`, { batchId, taskIds: report.taskIds[label], termId: report.termId, collegeId })
      await capture(page, `B01-${label}学院任务批次`)
    }

    for (const label of ['A', 'B']) {
      const page = pages[`college${label}`], batchId = report.batchIds[label]
      const account = fixture.accounts[`teacher${label}`]
      const facts = await batchFacts(page, batchId)
      const targetIds = label === 'A' ? facts.tasks.map(item => item.taskId) : facts.tasks.slice(0, -2).map(item => item.taskId)
      for (const taskId of targetIds) {
        const task = facts.tasks.find(item => item.taskId === taskId)
        assert.ok(['PENDING_ASSIGN', 'ASSIGNED', 'TEACHER_CONFIRMED', 'READY'].includes(task.status), '批次已有非场景任务状态，禁止覆盖')
        if (task.status !== 'PENDING_ASSIGN') {
          assert.equal(task.teacherKey, account.teacherKey, '已分配任务属于其他教师，禁止改派')
          if (report.pending?.step === `assign-${taskId}`) await observed(`assign-${taskId}`, { batchId, taskId, teacherUserId: account.userId, status: task.status })
          continue
        }
        await phase(`学院 ${label} 为正式任务分配任课教师`)
        const row = page.locator('tr').filter({ hasText: task.courseCode }).filter({ hasText: task.teachingClassCode })
        await row.getByRole('button', { name: '分配教师', exact: true }).click()
        const dialog = page.getByRole('dialog', { name: '分配任课教师', exact: true })
        await choose(dialog, '任课教师', account.teacherKey)
        await beforeWrite(`assign-${taskId}`)
        const assignment = responseFor(page, `${apiPath}/teaching-tasks/${taskId}/assign`, 'POST')
        await dialog.getByRole('button', { name: '确认分配', exact: true }).click()
        await read(await assignment)
        const after = await batchFacts(page, batchId)
        const assigned = after.tasks.find(item => item.taskId === taskId)
        assert.equal(assigned?.status, 'ASSIGNED'); assert.equal(assigned.teacherKey, account.teacherKey)
        await observed(`assign-${taskId}`, { batchId, taskId, teacherUserId: account.userId, status: assigned.status })
      }
    }
    await phase('学校核对两院并行状态和 B 学院两条未分配阻断')
    let a = await batchFacts(pages.collegeA, report.batchIds.A)
    let b = await batchFacts(pages.collegeB, report.batchIds.B)
    assert.equal(a.workbench.unassignedCount, 0)
    assert.ok(a.tasks.every(item => item.teacherKey === fixture.accounts.teacherA.teacherKey))
    let flow = await visit(school, `/admin/academic-affairs?termId=${report.termId}`, `${apiPath}/flow`, true)
    if (!report.checkpoints.some(item => item.step === 'B')) {
      assert.equal(b.workbench.unassignedCount, 2)
      assert.ok(b.tasks.filter(item => item.status === 'PENDING_ASSIGN').length === 2)
      assert.equal(stage(flow, 'B').status, 'BLOCKED')
      assert.ok(a.tasks.every(item => item.status === 'ASSIGNED'), 'B 阶段应由教师 A 接收但尚未确认')
      assert.equal(stage(flow, 'A').status, 'ACTION_REQUIRED')
      await observed('B', { aBatchId: report.batchIds.A, bBatchId: report.batchIds.B, aAssigned: a.tasks.length, bUnassigned: 2, aStage: stage(flow, 'A').status, bStage: stage(flow, 'B').status })
      report.uncovered = ['C', 'D', 'E', 'F', 'G', 'H']; await save()
      await capture(school, 'B02-学校两院任务状态')
    }

    if (b.workbench.status === 'DRAFT' && !report.checkpoints.some(item => item.step === 'D-tasks-ready')) {
    for (const taskId of report.taskIds.A) {
      const teacher = pages.teacherA
      await phase('教师 A 仅确认本人正式教学任务')
      const mine = await visit(teacher, `/admin/academic-affairs/teaching-tasks/teacher-confirm?taskId=${taskId}`, `${apiPath}/teaching-tasks`)
      assert.equal(mine.total, 1); assert.equal(mine.items[0]?.taskId, taskId)
      assert.equal(mine.items[0].teacherKey, fixture.accounts.teacherA.teacherKey)
      if (['TEACHER_CONFIRMED', 'READY'].includes(mine.items[0].status)) {
        if (report.pending?.step === `teacher-${taskId}`) await observed(`teacher-${taskId}`, { taskId, status: mine.items[0].status })
        continue
      }
      assert.equal(mine.items[0].status, 'ASSIGNED')
      const row = teacher.locator('tr').filter({ hasText: mine.items[0].courseCode }).filter({ hasText: mine.items[0].teachingClassCode })
      await row.getByRole('button', { name: '确认接受', exact: true }).click()
      const dialog = teacher.getByRole('dialog', { name: '确认接受授课安排', exact: true })
      await beforeWrite(`teacher-${taskId}`)
      const accepted = responseFor(teacher, `${apiPath}/teaching-tasks/${taskId}/teacher-act`, 'POST')
      await dialog.getByRole('button', { name: '确认接受', exact: true }).click()
      await read(await accepted)
      const confirmed = await visit(teacher, `/admin/academic-affairs/teaching-tasks/teacher-confirm?taskId=${taskId}`, `${apiPath}/teaching-tasks`, true)
      assert.equal(confirmed.items[0]?.taskId, taskId); assert.equal(confirmed.items[0]?.status, 'TEACHER_CONFIRMED')
      await observed(`teacher-${taskId}`, { taskId, status: confirmed.items[0].status })
    }
    const forbidden = await visit(pages.teacherB, `/admin/academic-affairs/teaching-tasks/teacher-confirm?taskId=${report.taskIds.A[0]}`, `${apiPath}/teaching-tasks`)
    assert.equal(forbidden.total, 0, '教师 B 不得看到教师 A 的任务')
    await expect(pages.teacherB.getByRole('button', { name: '确认接受', exact: true })).toHaveCount(0)
    const targetTaskId = report.taskIds.A[0]
    const targetStatusBefore = (await batchFacts(pages.collegeA, report.batchIds.A)).tasks.find(item => item.taskId === targetTaskId)?.status
    const beforeForbidden = auditRows({ tenantId: fixture.tenantId, bizType: 'AA_TASK', bizId: targetTaskId,
      action: 'TEACHER_CONFIRM', account: fixture.accounts.teacherA })
    const denied = await pages.teacherB.context().request.post(`${new URL(api).origin}${apiPath}/teaching-tasks/${targetTaskId}/teacher-act`, {
      headers: { Authorization: `Bearer ${accessTokens.teacherB}` }, data: { action: 'CONFIRM' },
    })
    assert.ok([403, 404].includes(denied.status()), '教师 B 越权确认必须由正式服务拒绝')
    const deniedBody = await denied.json()
    assert.notEqual(deniedBody.code, 0, '教师 B 越权请求不得返回业务成功')
    const afterForbidden = auditRows({ tenantId: fixture.tenantId, bizType: 'AA_TASK', bizId: targetTaskId,
      action: 'TEACHER_CONFIRM', account: fixture.accounts.teacherA })
    assert.deepEqual(afterForbidden.rows, beforeForbidden.rows, '越权请求不得增加目标任务确认审计')
    a = await batchFacts(pages.collegeA, report.batchIds.A)
    assert.equal(a.tasks.find(item => item.taskId === targetTaskId)?.status, targetStatusBefore, '越权请求不得改变目标任务')
    assert.ok(a.tasks.every(item => ['TEACHER_CONFIRMED', 'READY'].includes(item.status)))
    flow = await visit(school, `/admin/academic-affairs?termId=${report.termId}`, `${apiPath}/flow`, true)
    assert.equal(stage(flow, 'B').status, 'BLOCKED')
    if (!report.checkpoints.some(item => item.step === 'C-teacher')) {
      assert.equal(stage(flow, 'A').status, 'ACTION_REQUIRED')
      await observed('C-teacher', { aStage: stage(flow, 'A').status, bStage: stage(flow, 'B').status, teacherTaskIds: report.taskIds.A })
    }

    await phase('学院 A 正式确认批次')
    if (a.workbench.status === 'DRAFT') {
      assert.equal(a.workbench.actions.canCollegeConfirm, true)
      await beforeWrite('college-A-confirm')
      const collegeConfirmed = responseFor(pages.collegeA, `${apiPath}/teaching-task-batches/${report.batchIds.A}/college-confirm`, 'POST')
      await pages.collegeA.getByRole('button', { name: '学院确认', exact: true }).click()
      const collegeReceipt = await read(await collegeConfirmed)
      assert.equal(collegeReceipt.status, 'COLLEGE_CONFIRMED')
    }
    a = await batchFacts(pages.collegeA, report.batchIds.A)
    assert.ok(['COLLEGE_CONFIRMED', 'APPROVED'].includes(a.workbench.status))
    await observed('college-A-confirm', { batchId: report.batchIds.A, status: a.workbench.status })

    await phase('校教务终审学院 A 教学任务')
    const schoolBatch = await batchFacts(school, report.batchIds.A)
    if (schoolBatch.workbench.status === 'COLLEGE_CONFIRMED') {
      assert.equal(schoolBatch.workbench.actions.canAcademicReview, true)
      await school.getByRole('button', { name: '教务终审通过', exact: true }).click()
      const reviewDialog = school.getByRole('dialog', { name: '确认教务终审通过', exact: true })
      await beforeWrite('school-A-review')
      const approved = responseFor(school, `${apiPath}/teaching-task-batches/${report.batchIds.A}/review`, 'POST')
      await reviewDialog.getByRole('button', { name: '确认通过', exact: true }).click()
      const schoolReceipt = await read(await approved)
      assert.equal(schoolReceipt.status, 'APPROVED')
    }
    a = await batchFacts(school, report.batchIds.A)
    assert.equal(a.workbench.status, 'APPROVED')
    assert.ok(a.tasks.every(item => item.status === 'READY'))
    await observed('school-A-review', { batchId: report.batchIds.A, status: a.workbench.status, taskIds: report.taskIds.A })
    flow = await visit(school, `/admin/academic-affairs?termId=${report.termId}`, `${apiPath}/flow`, true)
    assert.equal(stage(flow, 'A').status, 'READY')
    assert.equal(stage(flow, 'B').status, 'BLOCKED')
    const gate = flow.schoolGates.find(item => item.stageCode === 'F40_TEACHING_TASK')
    assert.equal(gate.readyUnitCount, 1); assert.equal(gate.totalUnitCount, 2); assert.equal(gate.ready, false)
    await observed('C', { aStage: stage(flow, 'A').status, bStage: stage(flow, 'B').status, gate: { readyUnitCount: gate.readyUnitCount, totalUnitCount: gate.totalUnitCount } })
    report.uncovered = ['D', 'E', 'F', 'G', 'H']; await save()
    await capture(school, 'C01-学院A就绪学校一院未就绪')
    }

    const roomCode = `${objectPrefix}ROOM`, roomName = `${objectPrefix} 教学教室`
    const scheduleListPath = `${apiPath}/schedule-batches`
    if (!report.checkpoints.some(item => item.step === 'E')) {
    if (!report.checkpoints.some(item => item.step === 'D')) {
    await phase('排课前学校门禁核对与学院 A 建立正式排课批次')
    const scheduleGate = flow.schoolGates.find(item => item.stageCode === 'F50_SCHEDULE')
    assert.ok(scheduleGate, '学校必须返回正式排课门禁')
    if (b.workbench.status !== 'APPROVED') assert.equal(scheduleGate.ready, false, '学院 B 教学任务未就绪时不得开放全校课表发布')
    const scheduleName = `${objectPrefix} A学院排课`
    let schedules = await visit(pages.collegeA, `/admin/academic-affairs/schedule?termId=${report.termId}`, scheduleListPath)
    assert.equal(Number(schedules.total), schedules.items.length, '课表批次未读全，禁止猜测新建')
    const owned = schedules.items.filter(item => item.batchName === scheduleName && item.termId === report.termId && item.collegeId === fixture.colleges.A.collegeId)
    assert.ok(owned.length <= 1, '同一学院排课批次重复，需核对原命令')
    let scheduleBatchId = report.scheduleBatchIds.A || owned[0]?.batchId
    if (report.scheduleBatchIds.A) assert.equal(owned[0]?.batchId, scheduleBatchId, '已保存排课批次不在正式列表')
    if (!scheduleBatchId) {
      await pages.collegeA.getByRole('button', { name: '＋ 创建排课批次', exact: true }).click()
      const form = pages.collegeA.locator('section.app-section-card').filter({ hasText: '新建课表批次' })
      await choose(form, '学期', `${objectPrefix} 学期责任接力`)
      await form.getByPlaceholder('选填', { exact: true }).fill(scheduleName)
      await form.getByRole('combobox', { name: '排课范围', exact: true }).selectOption('COLLEGE')
      await choose(form, '学院', `V5 甲学院 ${fixture.prefix}`)
      await beforeWrite('schedule-A-batch')
      const created = responseFor(pages.collegeA, scheduleListPath, 'POST')
      await form.getByRole('button', { name: '创建', exact: true }).click()
      scheduleBatchId = (await read(await created)).batchId
      assert.equal(typeof scheduleBatchId, 'string')
      report.scheduleBatchIds.A = scheduleBatchId; await save()
    }
    schedules = await visit(pages.collegeA, `/admin/academic-affairs/schedule?termId=${report.termId}`, scheduleListPath, true)
    const schedule = schedules.items.find(item => item.batchId === scheduleBatchId)
    assert.equal(schedule?.termId, report.termId)
    assert.equal(schedule?.collegeId, fixture.colleges.A.collegeId)
    scheduleResumeMode(schedule?.status)
    await observed('schedule-A-batch', { scheduleBatchId, termId: report.termId, collegeId: fixture.colleges.A.collegeId, status: schedule.status })
    if (schedule.status !== 'DRAFT') {
      await observed('E-pre-A', { batchId: scheduleBatchId, status: schedule.status })
      if (schedule.status === 'PUBLISHED') {
        const current = await readOnly('school', `${scheduleListPath}/${scheduleBatchId}`)
        assert.equal(current.activeTruth?.isCurrent, true); assert.equal(current.activeTruth.truthStatus, 'VERIFIED')
        await observed('E-pub-A', { batchId: scheduleBatchId, status: current.status })
      }
    }
    await capture(pages.collegeA, 'D01-学院A正式排课批次')

    // 学校统一发布须等待 B 学院；由 B 本人补齐教学任务，再回读全校门禁。
    for (const taskId of report.taskIds.B) {
      let current = await batchFacts(pages.collegeB, report.batchIds.B)
      let task = current.tasks.find(item => item.taskId === taskId)
      if (task.status === 'PENDING_ASSIGN') {
        await phase('学院 B 补齐原两条未派师任务')
        const row = pages.collegeB.locator('tr').filter({ hasText: task.courseCode }).filter({ hasText: task.teachingClassCode })
        await row.getByRole('button', { name: '分配教师', exact: true }).click()
        const dialog = pages.collegeB.getByRole('dialog', { name: '分配任课教师', exact: true })
        await choose(dialog, '任课教师', fixture.accounts.teacherB.teacherKey)
        await beforeWrite(`assign-B-${taskId}`)
        const assignment = responseFor(pages.collegeB, `${apiPath}/teaching-tasks/${taskId}/assign`, 'POST')
        await dialog.getByRole('button', { name: '确认分配', exact: true }).click()
        await read(await assignment)
        current = await batchFacts(pages.collegeB, report.batchIds.B)
        task = current.tasks.find(item => item.taskId === taskId)
        assert.equal(task?.status, 'ASSIGNED')
        await observed(`assign-B-${taskId}`, { taskId, batchId: report.batchIds.B, status: task.status })
      } else if (report.pending?.step === `assign-B-${taskId}`) {
        assert.equal(task.teacherKey, fixture.accounts.teacherB.teacherKey)
        await observed(`assign-B-${taskId}`, { taskId, batchId: report.batchIds.B, status: task.status })
      }
      assert.equal(task.teacherKey, fixture.accounts.teacherB.teacherKey)
      const teacher = pages.teacherB
      const mine = await visit(teacher, `/admin/academic-affairs/teaching-tasks/teacher-confirm?taskId=${taskId}`, `${apiPath}/teaching-tasks`)
      assert.equal(mine.total, 1); assert.equal(mine.items[0]?.taskId, taskId)
      if (mine.items[0].status === 'ASSIGNED') {
        await phase('教师 B 本人确认补齐的教学任务')
        const row = teacher.locator('tr').filter({ hasText: mine.items[0].courseCode }).filter({ hasText: mine.items[0].teachingClassCode })
        await row.getByRole('button', { name: '确认接受', exact: true }).click()
        await beforeWrite(`teacher-B-${taskId}`)
        const accepted = responseFor(teacher, `${apiPath}/teaching-tasks/${taskId}/teacher-act`, 'POST')
        await teacher.getByRole('dialog', { name: '确认接受授课安排', exact: true }).getByRole('button', { name: '确认接受', exact: true }).click()
        await read(await accepted)
        const confirmed = await visit(teacher, `/admin/academic-affairs/teaching-tasks/teacher-confirm?taskId=${taskId}`, `${apiPath}/teaching-tasks`, true)
        assert.equal(confirmed.items[0]?.status, 'TEACHER_CONFIRMED')
        await observed(`teacher-B-${taskId}`, { taskId, status: confirmed.items[0].status })
      } else {
        assert.ok(['TEACHER_CONFIRMED', 'READY'].includes(mine.items[0].status))
        if (report.pending?.step === `teacher-B-${taskId}`) await observed(`teacher-B-${taskId}`, { taskId, status: mine.items[0].status })
      }
    }
    b = await batchFacts(pages.collegeB, report.batchIds.B)
    assert.equal(b.workbench.unassignedCount, 0)
    assert.ok(b.tasks.every(item => ['TEACHER_CONFIRMED', 'READY'].includes(item.status)))
    if (b.workbench.status === 'DRAFT') {
      await phase('学院 B 本人核对并确认')
      assert.equal(b.workbench.actions.canCollegeConfirm, true)
      await beforeWrite('college-B-confirm')
      const confirmed = responseFor(pages.collegeB, `${apiPath}/teaching-task-batches/${report.batchIds.B}/college-confirm`, 'POST')
      await pages.collegeB.getByRole('button', { name: '学院确认', exact: true }).click()
      assert.equal((await read(await confirmed)).status, 'COLLEGE_CONFIRMED')
    }
    b = await batchFacts(school, report.batchIds.B)
    assert.ok(['COLLEGE_CONFIRMED', 'APPROVED'].includes(b.workbench.status))
    await observed('college-B-confirm', { batchId: report.batchIds.B, status: b.workbench.status })
    if (b.workbench.status === 'COLLEGE_CONFIRMED') {
      await phase('学校终审学院 B 后重新核对全校')
      assert.equal(b.workbench.actions.canAcademicReview, true)
      await school.getByRole('button', { name: '教务终审通过', exact: true }).click()
      await beforeWrite('school-B-review')
      const approvedB = responseFor(school, `${apiPath}/teaching-task-batches/${report.batchIds.B}/review`, 'POST')
      await school.getByRole('dialog', { name: '确认教务终审通过', exact: true }).getByRole('button', { name: '确认通过', exact: true }).click()
      assert.equal((await read(await approvedB)).status, 'APPROVED')
    }
    b = await batchFacts(school, report.batchIds.B)
    assert.equal(b.workbench.status, 'APPROVED')
    assert.ok(b.tasks.every(item => item.status === 'READY'))
    await observed('school-B-review', { batchId: report.batchIds.B, status: b.workbench.status })
    flow = await visit(school, `/admin/academic-affairs?termId=${report.termId}`, `${apiPath}/flow`, true)
    assert.equal(stage(flow, 'A').status, 'READY'); assert.equal(stage(flow, 'B').status, 'READY')
    await observed('D-tasks-ready', { aBatchId: report.batchIds.A, bBatchId: report.batchIds.B, termId: report.termId })

    // D: the existing HYBRID rule lets the public course's configured offering
    // college schedule it. The school sees the whole-school conflict and publishes.
    await phase('校级核对公共课开课单位规则及正式教室资源')
    const scheduleStage = flow.stages.find(item => item.stageCode === 'F50_SCHEDULE')
    assert.ok(scheduleStage, '学校缺少排课责任阶段')
    assert.equal(scheduleStage.evidence?.schoolSchedule?.publicScheduleMode, 'HYBRID',
      '本故事按当前正式开课单位编排规则验收，不得猜测公共课归属')
    const roomPath = `${apiPath}/classrooms`
    let rooms = await visit(school, '/admin/academic-affairs/classrooms', roomPath)
    let room = (rooms.items || []).find(item => item.roomCode === roomCode)
    if (!room) {
      await school.getByRole('button', { name: '单间新增', exact: true }).click()
      await school.locator('[data-field="cr-building-code"] input').fill(`${objectPrefix}BLDG`)
      await school.locator('[data-field="cr-building-name"] input').fill(`${objectPrefix} 教学楼`)
      await school.locator('[data-field="cr-room-code"] input').fill(roomCode)
      await school.locator('[data-field="cr-room-name"] input').fill(roomName)
      await school.locator('[data-field="cr-capacity"] input').fill('40')
      await beforeWrite('D-classroom')
      const created = responseFor(school, roomPath, 'POST')
      await school.getByRole('button', { name: '保存教室', exact: true }).click()
      room = await read(await created)
      assert.equal(typeof room.classroomId, 'string')
      report.classroomId = room.classroomId; await save()
    }
    rooms = await visit(school, '/admin/academic-affairs/classrooms', roomPath, true)
    room = (rooms.items || []).find(item => item.roomCode === roomCode)
    assert.equal(room?.classroomId, report.classroomId || room?.classroomId)
    assert.equal(room?.status, 'AVAILABLE'); assert.equal(room?.allowSchedule, true); assert.equal(room?.allowExam, true)
    report.classroomId = room.classroomId
    await observed('D-classroom', { classroomId: room.classroomId, roomCode, capacity: room.capacity })

    const ensureScheduleBatch = async (role, label, scope) => {
      const page = pages[role], name = `${objectPrefix} ${label}排课`
      const batches = await visit(page, `/admin/academic-affairs/schedule?termId=${report.termId}`, scheduleListPath)
      assert.equal(Number(batches.total), batches.items.length, '排课批次列表未读全')
      const found = batches.items.filter(item => item.batchName === name && item.termId === report.termId)
      assert.ok(found.length <= 1, '同名排课批次重复，禁止猜测新建')
      let id = report.scheduleBatchIds[label] || found[0]?.batchId
      if (report.scheduleBatchIds[label]) assert.equal(found[0]?.batchId, id, '保存的排课批次未在正式列表')
      if (!id) {
        await page.getByRole('button', { name: '＋ 创建排课批次', exact: true }).click()
        const form = page.locator('section.app-section-card').filter({ hasText: '新建课表批次' })
        await choose(form, '学期', `${objectPrefix} 学期责任接力`)
        await form.getByPlaceholder('选填', { exact: true }).fill(name)
        await form.getByRole('combobox', { name: '排课范围', exact: true }).selectOption(scope)
        if (scope === 'COLLEGE') await choose(form, '学院', `V5 乙学院 ${fixture.prefix}`)
        await beforeWrite(`schedule-${label}-batch`)
        const created = responseFor(page, scheduleListPath, 'POST')
        await form.getByRole('button', { name: '创建', exact: true }).click()
        id = (await read(await created)).batchId
        assert.equal(typeof id, 'string')
        report.scheduleBatchIds[label] = id; await save()
      }
      const detail = await readOnly(role, `${scheduleListPath}/${id}`)
      assert.equal(detail.termId, report.termId)
      assert.equal(detail.collegeId || null, scope === 'SCHOOL' ? null : fixture.colleges.B.collegeId)
      scheduleResumeMode(detail.status)
      await observed(`schedule-${label}-batch`, { scheduleBatchId: id, scope, termId: report.termId })
      return id
    }
    await ensureScheduleBatch('collegeB', 'B', 'COLLEGE')

    const summaries = {}
    for (const label of ['A', 'B']) {
      const role = `college${label}`
      summaries[label] = await readOnly(role, `${scheduleListPath}/${report.scheduleBatchIds[label]}/summary`)
      assert.ok(summaries[label].totalTasks > 0, `${label}正式排课范围无教学任务`)
      assert.equal(summaries[label].invalidTaskCount, 0, `${label} 教学任务的周次或周学时异常`)
    }
    if (!report.scheduleTaskIds) {
      report.scheduleTaskIds = Object.fromEntries(['A', 'B'].map(label => [label, report.taskIds[label].slice()]))
      await save()
    }
    const coverage = ['A', 'B'].flatMap(label => report.scheduleTaskIds[label])
    assert.equal(new Set(coverage).size, coverage.length, '排课责任范围重叠')
    assert.deepEqual(new Set(coverage), new Set([...report.taskIds.A, ...report.taskIds.B]), '公共课及两院专业课责任范围未完整覆盖')
    assert.equal(report.scheduleTaskIds.A.length, summaries.A.totalTasks)
    assert.equal(report.scheduleTaskIds.B.length, summaries.B.totalTasks)
    assert.ok(report.scheduleTaskIds.A.every(id => report.taskIds.A.includes(id)))
    assert.ok(report.scheduleTaskIds.B.every(id => report.taskIds.B.includes(id)))
    assert.equal(summaries.A.courseScopeCounts.public, 0, '学院 A 不得编排乙学院开课的公共课')
    assert.ok(summaries.B.courseScopeCounts.public >= 1, '学院 B 开课的公共课未进入其正式排课责任')
    assert.ok(summaries.A.courseScopeCounts.professional >= 1 && summaries.B.courseScopeCounts.professional >= 1)
    await observed('D-responsibility', { taskCount: coverage.length, publicTaskCount: summaries.B.courseScopeCounts.public,
      collegeATaskCount: summaries.A.totalTasks, collegeBTaskCount: summaries.B.totalTasks })

    let schoolConflictEvidence = report.schoolConflictEvidence || null
    const scheduleOne = async (role, label, task, ordinal) => {
      const page = pages[role], batchId = report.scheduleBatchIds[label]
      const target = `/admin/academic-affairs/schedule/${batchId}/edit?classId=${task.classId}&taskId=${task.taskId}&termId=${report.termId}`
      const classViewPath = `${scheduleListPath}/${batchId}/class-view`
      await page.waitForLoadState('networkidle')
      const classViewResponse = responseFor(page, classViewPath)
      await visit(page, target, `${scheduleListPath}/${batchId}`, true)
      const before = await read(await classViewResponse)
      assert.ok(Array.isArray(before.items), '班级课表未返回正式课位清单')
      await expect(page.locator('.aa-grid__cell.is-editable').first()).toBeVisible()
      const cells = page.locator('.aa-grid__cell.is-editable').filter({ has: page.locator('.aa-grid__add') })
      const count = await cells.count()
      assert.ok(count >= 7, '缺少可选课位，禁止伪造课表')
      let conflictSeen = false
      for (let index = 0; index < count; index++) {
        const cell = cells.nth(index)
        if (!(await cell.isVisible().catch(() => false))) continue
        await cell.click()
        const dialog = page.locator('.app-confirm-dialog:visible')
        await expect(dialog).toBeVisible()
        await dialog.locator('select.app-select__el').first().selectOption(task.taskId)
        const preflight = page.waitForResponse(response => {
          if (new URL(response.url()).pathname !== `${scheduleListPath}/${batchId}/items/preflight` || response.request().method() !== 'POST') return false
          try { return Boolean(response.request().postDataJSON()?.classroom) } catch { return false }
        }, { timeout: 120_000 })
        await choose(dialog, '教室', roomName)
        const checked = await preflight
        assert.equal(checked.request().postDataJSON().classroom, roomName, '正式教室选择结果与教室目录不一致')
        const check = await read(checked)
        if (!check.allowed) {
          conflictSeen = true
          await expect(dialog).toContainText('存在硬冲突')
          if (label === 'B' && !schoolConflictEvidence) {
            assert.equal(check.conflict?.type, 'CLASSROOM', '须核对 A 学院教室占用这一跨院硬冲突')
            const candidate = check.candidate
            const aTask = (await batchFacts(pages.collegeA, report.batchIds.A)).tasks[0]
            const aView = await readOnly('school', `${scheduleListPath}/${report.scheduleBatchIds.A}/class-view?classId=${aTask.classId}`)
            const source = aView.items.find(item => item.weekday === candidate.weekday && item.slotNo === candidate.slotNo &&
              item.classroom === candidate.classroom && report.scheduleItemIds[aTask.taskId]?.includes(item.itemId))
            assert.ok(source, '跨院冲突须回链学院 A 已通过页面排入的具体课位')
            const schoolPage = pages.school
            const schoolTarget = `/admin/academic-affairs/schedule/${batchId}/edit?classId=${task.classId}&taskId=${task.taskId}&termId=${report.termId}`
            const schoolClassView = responseFor(schoolPage, `${scheduleListPath}/${batchId}/class-view`)
            await visit(schoolPage, schoolTarget, `${scheduleListPath}/${batchId}`)
            await read(await schoolClassView)
            const schoolRow = schoolPage.locator('.aa-grid tbody tr').filter({ has: schoolPage.locator('th', { hasText: `第 ${candidate.slotNo} 节` }) })
            await schoolRow.locator('td.aa-grid__cell').nth(candidate.weekday - 1).click()
            const schoolDialog = schoolPage.locator('.app-confirm-dialog:visible')
            await expect(schoolDialog).toBeVisible()
            await schoolDialog.locator('select.app-select__el').first().selectOption(task.taskId)
            const schoolPreflight = schoolPage.waitForResponse(response => {
              if (new URL(response.url()).pathname !== `${scheduleListPath}/${batchId}/items/preflight` || response.request().method() !== 'POST') return false
              try { return Boolean(response.request().postDataJSON()?.classroom) } catch { return false }
            }, { timeout: 120_000 })
            await choose(schoolDialog, '教室', roomName)
            const schoolCheck = await read(await schoolPreflight)
            assert.equal(schoolCheck.allowed, false, '校级必须在正式页面看到同一硬冲突')
            assert.deepEqual(schoolCheck.candidate, candidate, '校级预检坐标必须与学院 B 一致')
            assert.deepEqual(schoolCheck.conflict, check.conflict, '校级与学院 B 须看到同一冲突来源')
            await expect(schoolDialog).toContainText(check.conflict.detail)
            await expect(schoolDialog.getByRole('button', { name: '确认排课', exact: true })).toBeDisabled()
            await capture(schoolPage, 'D02-学校全校冲突预检')
            await schoolDialog.getByRole('button', { name: '取消', exact: true }).click()
            schoolConflictEvidence = { aItemId: source.itemId, bTaskId: task.taskId, weekday: candidate.weekday,
              slotNo: candidate.slotNo, classroom: candidate.classroom, conflictType: check.conflict.type }
            report.schoolConflictEvidence = schoolConflictEvidence; await save()
          }
          await dialog.getByRole('button', { name: '取消', exact: true }).click()
          continue
        }
        await expect(dialog.getByRole('button', { name: '确认排课', exact: true })).toBeEnabled()
        const step = `D-${label}-${task.taskId}-${ordinal}`
        await beforeWrite(step)
        const created = responseFor(page, `${scheduleListPath}/${batchId}/items`, 'POST')
        await dialog.getByRole('button', { name: '确认排课', exact: true }).click()
        const item = await read(await created)
        assert.equal(item.taskId, task.taskId); assert.equal(item.batchId, batchId)
        assert.equal(typeof item.itemId, 'string')
        report.scheduleItemIds[task.taskId] ||= []
        report.scheduleItemIds[task.taskId].push(item.itemId); await save()
        const persisted = await readOnly(role, `${classViewPath}?classId=${task.classId}`)
        assert.ok(persisted.items.some(row => row.itemId === item.itemId && row.taskId === task.taskId), '课位写后未从正式服务回读')
        await observed(step, { scheduleBatchId: batchId, itemId: item.itemId, taskId: task.taskId,
          classId: task.classId, weekday: item.weekday, slotNo: item.slotNo })
        return conflictSeen
      }
      assert.fail(`${label} 教学任务 ${task.taskId} 无可排课位；须在正式页面协调，不得造课表`)
    }
    let crossCollegeRoomConflict = report.crossCollegeRoomConflict || false
    for (const label of ['A', 'B']) {
      const role = `college${label}`
      const summaryPath = `${scheduleListPath}/${report.scheduleBatchIds[label]}/summary`
      const detail = await readOnly(role, `${scheduleListPath}/${report.scheduleBatchIds[label]}`)
      const mode = scheduleResumeMode(detail.status)
      const initial = await readOnly(role, summaryPath)
      assert.equal(initial.taskQueueTotal, initial.taskQueue.length, '排课任务队列未读全')
      if (mode !== 'schedule') {
        assert.equal(initial.complete, true, '已预发布或发布课表必须完整，不能重新编排')
        await observed(`E-pre-${label}`, { batchId: detail.batchId, status: detail.status })
        if (mode === 'read') {
          assert.equal(detail.activeTruth?.isCurrent, true)
          assert.equal(detail.activeTruth.truthStatus, 'VERIFIED')
          await observed(`E-pub-${label}`, { batchId: detail.batchId, status: detail.status })
        }
      }
      const queue = mode === 'schedule' ? initial.taskQueue : []
      for (const task of queue) {
        assert.ok(task.canSchedule && task.remainingSessions > 0 && task.remainingSessions <= 12)
        assert.ok([fixture.colleges.A.classId, fixture.colleges.B.classId].includes(task.classId))
        for (let ordinal = 0; ordinal < task.remainingSessions; ordinal++) {
          await phase(`${label}责任账号在正式课表为 ${task.courseName} 排第 ${ordinal + 1} 节`)
          const conflict = await scheduleOne(role, label, task, ordinal)
          if (label === 'B') crossCollegeRoomConflict ||= conflict
        }
      }
      const complete = await readOnly(role, summaryPath)
      assert.equal(complete.complete, true, `${label} 排课未完成`)
      assert.equal(complete.hardConflicts, 0)
      assert.equal(complete.scheduledSessions, complete.expectedSessions)
      await observed(`D-${label}-complete`, { scheduleBatchId: report.scheduleBatchIds[label],
        totalTasks: complete.totalTasks, expectedSessions: complete.expectedSessions, hardConflicts: complete.hardConflicts })
    }
    report.crossCollegeRoomConflict ||= crossCollegeRoomConflict; await save()
    assert.equal(report.crossCollegeRoomConflict, true, '学院 B 必须在同一教室撞见 A 的课位并通过页面改到无冲突位置')
    assert.ok(schoolConflictEvidence?.aItemId && schoolConflictEvidence?.bTaskId, '学校须经正式排课页面预检同一跨院冲突')
    const bTaskId = report.scheduleTaskIds.B[0]
    const bItemId = report.scheduleItemIds[bTaskId]?.[0]
    assert.ok(bItemId, '缺少学院 B 正式课位用于跨学院越权核验')
    const foreignTask = (await batchFacts(pages.collegeB, report.batchIds.B)).tasks.find(item => item.taskId === bTaskId)
    assert.ok(foreignTask?.classId)
    const foreignBefore = await readOnly('collegeB', `${scheduleListPath}/${report.scheduleBatchIds.B}/class-view?classId=${foreignTask.classId}`)
    const forbiddenMove = await pages.collegeA.context().request.put(`${new URL(api).origin}${scheduleListPath}/${report.scheduleBatchIds.B}/items/${bItemId}`, {
      headers: { Authorization: `Bearer ${accessTokens.collegeA}` },
      data: { weekday: 5, slotNo: 1, reason: 'V5 跨学院越权负向核验' },
    })
    assert.ok([403, 404].includes(forbiddenMove.status()), '学院 A 修改学院 B 课位必须由正式服务拒绝')
    assert.notEqual((await forbiddenMove.json()).code, 0)
    const foreignAfter = await readOnly('collegeB', `${scheduleListPath}/${report.scheduleBatchIds.B}/class-view?classId=${foreignTask.classId}`)
    assert.deepEqual(foreignAfter.items, foreignBefore.items, '跨学院越权请求不得修改 B 的课位')
    await observed('D', { aBatchId: report.scheduleBatchIds.A, bBatchId: report.scheduleBatchIds.B,
      publicCourseOwner: fixture.colleges.B.collegeId, classroomId: room.classroomId,
      crossCollegeRoomConflict, schoolConflictEvidence })
    report.uncovered = ['E', 'F', 'G', 'H']; await save()
    }

    // E: each college pre-publishes its own complete batch; only the school
    // account executes formal publication after the whole-school gate passes.
    const publishPath = '/admin/academic-affairs/schedule/publish'
    const publishOne = async (role, label, intent) => {
      const page = pages[role], batchId = report.scheduleBatchIds[label]
      await visit(page, `${publishPath}?batchId=${batchId}`, scheduleListPath)
      const row = page.getByRole('row').filter({ hasText: `${objectPrefix} ${label === 'A' ? 'A学院排课' : 'B排课'}` })
      await expect(row).toBeVisible()
      const action = intent === 'pre' ? '检查并预发布' : '检查并正式发布'
      const checked = responseFor(page, `${scheduleListPath}/${batchId}/summary`)
      await row.getByRole('button', { name: action, exact: true }).click()
      const gateSummary = await read(await checked)
      assert.equal(gateSummary.complete, true, `${label} 排课漏排或冲突未清零`)
      if (intent === 'pub') {
        assert.equal(gateSummary.schoolGate?.ready, true, '全校发布门禁未通过')
        assert.equal(gateSummary.schoolGate?.hardConflicts, 0)
      }
      const buttonName = intent === 'pre' ? '确认进入预发布' : '确认正式发布并通知师生'
      const step = `E-${intent}-${label}`
      await beforeWrite(step)
      const written = responseFor(page, `${scheduleListPath}/${batchId}/${intent === 'pre' ? 'pre-publish' : 'publish'}`, 'POST')
      await page.getByRole('button', { name: buttonName, exact: true }).click()
      const receipt = await read(await written)
      assert.equal(receipt.batchId, batchId)
      const detail = await readOnly(role, `${scheduleListPath}/${batchId}`)
      assert.equal(detail.status, intent === 'pre' ? 'PRE_PUBLISHED' : 'PUBLISHED')
      await observed(step, { batchId, status: detail.status,
        expectedSessions: gateSummary.expectedSessions, hardConflicts: gateSummary.hardConflicts })
    }
    for (const label of ['A', 'B']) {
      const role = `college${label}`
      await phase(`${label}责任账号在正式页面预发布完整课表`)
      const detail = await readOnly(role, `${scheduleListPath}/${report.scheduleBatchIds[label]}`)
      if (scheduleResumeMode(detail.status) === 'schedule') await publishOne(role, label, 'pre')
      else {
        await observed(`E-pre-${label}`, { batchId: report.scheduleBatchIds[label], status: detail.status })
        if (detail.status === 'PUBLISHED') {
          assert.equal(detail.activeTruth?.isCurrent, true)
          assert.equal(detail.activeTruth.truthStatus, 'VERIFIED')
          await observed(`E-pub-${label}`, { batchId: detail.batchId, status: detail.status })
        }
      }
    }
    const schoolGateSummary = await readOnly('school', `${scheduleListPath}/${report.scheduleBatchIds.A}/summary`)
    assert.equal(schoolGateSummary.schoolGate?.ready, true)
    assert.equal(schoolGateSummary.schoolGate?.missingTaskCount, 0)
    assert.equal(schoolGateSummary.schoolGate?.hardConflicts, 0)
    await observed('E-school-gate', { requiredBatchIds: schoolGateSummary.schoolGate.requiredBatchIds,
      missingTaskCount: 0, hardConflicts: 0 })
    for (const label of ['A', 'B']) {
      await phase(`校教务本人正式发布 ${label} 完整课表`)
      const detail = await readOnly('school', `${scheduleListPath}/${report.scheduleBatchIds[label]}`)
      if (detail.status === 'PRE_PUBLISHED') await publishOne('school', label, 'pub')
      else assert.equal(detail.status, 'PUBLISHED', '已发布批次需由审计证明原操作者')
      if (detail.status === 'PUBLISHED')
        await observed(`E-pub-${label}`, { batchId: report.scheduleBatchIds[label], status: detail.status })
    }
    for (const label of ['A', 'B']) {
      const detail = await readOnly('school', `${scheduleListPath}/${report.scheduleBatchIds[label]}`)
      assert.equal(detail.status, 'PUBLISHED')
      assert.equal(detail.activeTruth?.isCurrent, true, '发布后缺少当前正式版本')
    }
    flow = await visit(school, `/admin/academic-affairs?termId=${report.termId}`, `${apiPath}/flow`, true)
    assert.equal(stage(flow, 'A').status, 'READY'); assert.equal(stage(flow, 'B').status, 'READY')
    assert.equal(flow.schoolGates.find(item => item.stageCode === 'F50_SCHEDULE')?.ready, true)
    await observed('E', { termId: report.termId, publishedBatchIds: Object.values(report.scheduleBatchIds) })
    report.uncovered = ['F', 'G', 'H']; await save()
    } else {
      await phase('学校回读已验收课表的当前正式继任版本')
    }
    const currentScheduleSources = {}
    const currentScheduleIds = {}
    for (const label of ['A', 'B']) {
      const oldId = report.scheduleBatchIds[label], collegeId = fixture.colleges[label].collegeId
      let detail = await readOnly('school', `${apiPath}/schedule-batches/${oldId}`)
      if (detail.status === 'SUPERSEDED') {
        assert.equal(detail.activeTruth?.truthStatus, 'VERIFIED')
        const activeId = detail.activeTruth.activeBatchId
        assert.ok(activeId && activeId !== oldId, '已替代课表没有可信当前版本')
        assertActor(auditRows({ tenantId: fixture.tenantId, bizType: 'AA_SCHEDULE_BATCH', bizId: oldId,
          action: 'PUBLISH', account: fixture.accounts.school }), { roleCode: fixture.accounts.school.roleCode })
        detail = await readOnly('school', `${apiPath}/schedule-batches/${activeId}`)
        assert.equal(detail.batchId, activeId); assert.equal(detail.supersedesBatchId, oldId, '只能承认原课表的精确正式继任版本')
      }
      assert.equal(detail.termId, report.termId); assert.equal(detail.collegeId, collegeId)
      assert.equal(detail.status, 'PUBLISHED'); assert.equal(detail.activeTruth?.isCurrent, true, '已验收课表缺少当前正式版本')
      assert.equal(detail.activeTruth.truthStatus, 'VERIFIED'); assert.equal(detail.activeTruth.scopeType, 'COLLEGE')
      assert.equal(detail.activeTruth.scopeId, collegeId); assert.equal(detail.activeTruth.activeBatchId, detail.batchId)
      const summary = await readOnly('school', `${apiPath}/schedule-batches/${detail.batchId}/summary`)
      assert.equal(summary.batchId, detail.batchId); assert.equal(summary.termId, report.termId)
      assert.equal(summary.complete, true); assert.equal(summary.schoolGate?.ready, true)
      assert.equal(summary.schoolGate.missingTaskCount, 0); assert.equal(summary.schoolGate.hardConflicts, 0)
      const items = []
      for (const group of Object.values(fixture.colleges)) {
        const view = await readOnly('school', `${apiPath}/schedule-batches/${detail.batchId}/class-view?classId=${group.classId}`)
        assert.ok(Array.isArray(view.items)); items.push(...view.items)
      }
      assert.equal(new Set(items.map(item => item.itemId)).size, items.length, '正式课位重复')
      assert.equal(items.length, summary.scheduledSessions, '原两班未覆盖当前课表完整课位')
      const taskIds = [...new Set(items.map(item => item.taskId))]
      assert.ok(taskIds.length > 0 && taskIds.every(Boolean))
      assert.equal(taskIds.length, summary.totalTasks); assert.equal(summary.scheduledTasks, summary.totalTasks)
      assert.ok(report.taskIds[label].every(id => taskIds.includes(id)), '正式继任课表丢失原故事教学任务')
      assertActor(auditRows({ tenantId: fixture.tenantId, bizType: 'AA_SCHEDULE_BATCH', bizId: detail.batchId,
        action: 'PUBLISH', account: fixture.accounts.school }), { roleCode: fixture.accounts.school.roleCode })
      currentScheduleSources[label] = taskIds; currentScheduleIds[label] = detail.batchId
    }
    if (['A', 'B'].some(label => report.scheduleBatchIds[label] !== currentScheduleIds[label])) {
      report.scheduleBatchHistory ||= []
      report.scheduleBatchHistory.push({ batchIds: { ...report.scheduleBatchIds }, currentBatchIds: currentScheduleIds, verifiedAt: new Date().toISOString() })
      report.scheduleBatchIds = currentScheduleIds; await save()
    }

    // Reuse the saved supply and activated students. Earlier A-H checkpoints do
    // not certify this new phase; every resume re-reads the same formal objects.
    await phase('学校与原四名学生办理同一选课批次')
    assert.equal(preparation.prefix, fixture.prefix)
    assert.equal(typeof preparation.tenantId, 'string', '私有学生准备租户编号必须为字符串，避免长编号精度丢失')
    assert.equal(preparation.tenantId, fixture.tenantId)
    const selection = preparation.selectionDraftCreate
    if (closedJourney) {
      assert.equal(preparation.scenarioId, journeyInput.scenarioId); assert.equal(preparation.termId, report.termId)
      assert.match(selection?.batchId || '', /^[1-9]\d*$/)
    } else assert.equal(selection?.batchId, '1')
    assert.equal(selection.termId, report.termId)
    assert.deepEqual(new Set(selection.applyScope?.classIds), new Set(Object.values(fixture.colleges).map(item => item.classId)))
    report.selectionBatchId = selection.batchId
    const selectionPath = `${apiPath}/selection/batches/${selection.batchId}`
    const supplies = closedJourney ? ['A', 'B'].map(label => preparation.selectionSupplies?.[label]) :
      ['selectionDraftSupply:6', 'selectionDraftSupply:8'].map(key => preparation[key])
    if (closedJourney) {
      for (const item of supplies) { assert.match(item?.selectionCourseId || '', /^[1-9]\d*$/); assert.match(item?.teachingTaskId || '', /^[1-9]\d*$/) }
      assert.equal(new Set(supplies.map(item => item.selectionCourseId)).size, 2)
    } else assert.deepEqual(supplies.map(item => item?.selectionCourseId), ['1', '2'])
    const supplySources = JSON.parse(execFileSync(process.env.E2E_V5_PYTHON || 'python', [
      path.join(root, '.codex-temp/v5-gold-run.py'), '-c', String.raw`
import importlib.util, json, os, sys
from pathlib import Path
from sqlalchemy import create_engine, event
from sqlalchemy.engine import make_url
root = Path.cwd().parent
url = make_url(os.environ['DATABASE_URL'])
expected_port = int(sys.argv[1])
assert expected_port in (3311, 3314)
assert (url.host, url.port, url.database) == ('127.0.0.1', expected_port, 'student_lifecycle_v5_e2e')
os.environ.update(DB_ENABLED='false', DATABASE_URL='', TEST_DATABASE_URL='')
sys.dont_write_bytecode = True
from app.models import College
spec = importlib.util.spec_from_file_location('v5_existing_readonly', root / '.codex-temp/v5-gold-student-preparation.py')
h = importlib.util.module_from_spec(spec); spec.loader.exec_module(h)
h.fixture = json.loads(Path(sys.argv[2]).read_text(encoding='utf-8-sig')); h.TID = int(h.fixture['tenantId']); h.College = College
if expected_port == 3314: h.configure_scenario(h.fixture, {'termId': sys.argv[3]})
h.engine = create_engine(url, hide_parameters=True, connect_args={'connect_timeout': 10, 'read_timeout': 30})
@event.listens_for(h.engine, 'checkout')
def readonly(raw, *_):
    with raw.cursor() as cursor: cursor.execute('SET SESSION TRANSACTION READ ONLY')
try:
    snapshot = h.selection_snapshot()
    print(json.dumps([{'taskId': str(x['task']['id']), 'collegeId': str(x['taskBatch']['college_id']),
        'termId': str(x['taskBatch']['term_id']), 'classId': str(x['task']['class_id']),
        'teacherKey': x['task']['teacher_key'], 'status': x['task']['status'],
        'formationMode': x['task']['formation_mode'], 'sourceProgramCourseId': str(x['task']['source_program_course_id']),
        'provenanceMatches': x['task']['course_id'] == x['programCourse']['course_id'] and
            x['task']['formation_mode'] == x['programCourse']['formation_mode']} for x in snapshot['sources']]))
finally:
    h.engine.dispose()
`, closedJourney ? '3314' : '3311', fixtureFile, report.termId], { cwd: root, env: process.env, encoding: 'utf8', windowsHide: true, timeout: 45_000, stdio: ['ignore', 'pipe', 'ignore'] }))
    assert.equal(supplySources.length, 2)
    const supplyOwners = supplies.map(item => {
      const source = supplySources.find(row => row.taskId === item.teachingTaskId)
      assert.ok(source, '选课供给缺少当前可信正式形成来源')
      const label = ['A', 'B'].find(key => source.collegeId === fixture.colleges[key].collegeId)
      assert.ok(label && currentScheduleSources[label].includes(source.taskId), '选课供给必须属于当前正式课表完整任务来源')
      assert.equal(source.termId, report.termId); assert.equal(source.classId, fixture.colleges[label].classId)
      assert.equal(source.teacherKey, fixture.accounts[`teacher${label}`].teacherKey); assert.equal(source.status, 'READY')
      assert.equal(source.formationMode, 'SELECTABLE'); assert.equal(source.provenanceMatches, true)
      assert.match(source.sourceProgramCourseId, /^[1-9]\d*$/)
      return label
    })
    assert.deepEqual(new Set(supplyOwners), new Set(['A', 'B']))
    const selectSavedBatch = async page => {
      const detail = responseFor(page, selectionPath).then(read)
      await visit(page, `/admin/academic-affairs/selection?termId=${report.termId}&batchId=${selection.batchId}`, `${apiPath}/selection/batches`)
      const result = await detail
      assert.equal(result.batchId, selection.batchId); assert.equal(result.termId, report.termId)
      assert.deepEqual(new Set(result.applyScope?.classIds), new Set(Object.values(fixture.colleges).map(item => item.classId)), '实际批次适用班级与原四学生不符')
      await expect(page.locator('.aa-selection-detail')).toContainText(selection.batchName)
      const actions = page.locator('.aa-selection-actions')
      if (page === school) {
        await expect(actions).toBeVisible()
        await expect.poll(() => actions.evaluate(element => element.inert), { timeout: 120_000 }).toBe(false)
      } else await expect(actions).toHaveCount(0)
      await expect(page.locator('.aa-selection-detail .aa-selection-summary')).toBeVisible()
      await expect(page.locator('.aa-selection-detail .aa-selection-owner-card')).not.toContainText('待重新核对')
      return result
    }
    let savedBatch = await selectSavedBatch(school)
    const formalSupply = await readOnly('school', `${selectionPath}/courses?page=1&pageSize=100`)
    assert.equal(formalSupply.total, 2); assert.equal(formalSupply.items.length, 2)
    for (const item of supplies) {
      const actual = formalSupply.items.find(row => row.selectionCourseId === item.selectionCourseId)
      assert.equal(actual?.teachingTaskId, item.teachingTaskId); assert.equal(actual.status, 'OPEN')
    }
    const selectionCommand = async (from, to, label, action) => {
      const step = `R6-${action}`
      savedBatch = await readOnly('school', selectionPath)
      if (savedBatch.status === from) {
        assert.notEqual(report.pending?.step, step, '待核对选课命令未推进状态，禁止自动重放')
        const checked = responseFor(school, `${selectionPath}/preflight`)
        await school.getByRole('button', { name: label, exact: true }).click()
        assert.equal((await read(await checked)).allowed, true)
        const dialog = school.getByRole('dialog').filter({ hasText: `确认对批次「${selection.batchName}」` })
        await expect(dialog).toBeVisible(); await beforeWrite(step)
        const written = responseFor(school, `${selectionPath}/${action}`, 'POST')
        await dialog.getByRole('button', { name: '确认', exact: true }).click(); await read(await written)
        savedBatch = await readOnly('school', selectionPath)
      }
      assert.ok(['DRAFT', 'PUBLISHED', 'OPEN', 'CLOSED', 'LOCKED'].indexOf(savedBatch.status) >=
        ['DRAFT', 'PUBLISHED', 'OPEN', 'CLOSED', 'LOCKED'].indexOf(to), '选课批次未达到已办理状态')
      await observed(step, { batchId: selection.batchId, status: savedBatch.status })
    }
    const studentPages = await loginStudents(supplies, supplyOwners)
    await selectSavedBatch(school)
    authenticated = true
    await selectionCommand('DRAFT', 'PUBLISHED', '发布', 'publish')
    await selectionCommand('PUBLISHED', 'OPEN', '开选', 'open')
    for (const { key, label, ordinal, page, supply } of studentPages) {
      activePage = page; authenticated = false
      const recordsPath = '/api/v1/portal/academic/course-selection/records'
      const recordsResponse = responseFor(page, recordsPath).then(read)
      await page.goto(`${studentBase}/academic/selection`); let records = await recordsResponse
      if (savedBatch.status === 'OPEN') {
        const picker = page.getByLabel('选课批次', { exact: true })
        await expect(picker.locator(`option[value="${selection.batchId}"]`)).toHaveText(selection.batchName)
        const refreshedRecords = responseFor(page, recordsPath).then(read)
        await picker.selectOption(selection.batchId); records = await refreshedRecords
      } else assert.ok(['CLOSED', 'LOCKED'].includes(savedBatch.status), '只能从已截止或已锁定原批次恢复本人记录')
      const rows = value => Array.isArray(value) ? value : value.items || value.list || []
      let record = rows(records).find(item => item.selectionCourseId === supply.selectionCourseId)
      const step = `R6-enroll-${key}`
      const droppedStep = `R6-drop-${key}`
      let originalRecordId = null
      if (savedBatch.status !== 'OPEN') {
        const original = [...report.checkpoints].reverse().find(item => [step, `R6-reenroll-${key}`].includes(item.step))
        assert.ok(original?.proof.recordId, '已截止批次缺少原学生办理回执，禁止补造选课')
        assert.equal(rows(records).filter(item => item.selectionCourseId === supply.selectionCourseId).length, 1)
        assert.equal(record?.recordId, original.proof.recordId); originalRecordId = record.recordId
        assert.equal(record.batchId, selection.batchId)
        assert.equal(record.studentId, fixture.colleges[label].studentIds[ordinal - 1])
        assert.equal(record.status, savedBatch.status === 'LOCKED' ? 'LOCKED' : 'SELECTED')
      }
      if (report.pending?.step === droppedStep) {
        assert.equal(record?.status, 'DROPPED', '原退课命令尚未确认，禁止自动重放')
        await observed(droppedStep, { recordId: record.recordId, selectionCourseId: supply.selectionCourseId })
      }
      const submitEnrollment = async commandStep => {
        assert.notEqual(report.pending?.step, commandStep, '报名结果尚未确认，禁止自动重放')
        assert.equal(savedBatch.status, 'OPEN', '批次已截止且没有原学生选课记录，禁止伪造')
        const row = page.locator('.course-table tbody tr').filter({ hasText: supply.courseName })
        await expect(row).toHaveCount(1)
        await row.getByRole('button', { name: '查看与办理', exact: true }).click()
        await beforeWrite(commandStep)
        const preflight = responseFor(page, '/api/v1/portal/academic/course-selection/preflight', 'POST')
        const enrolled = responseFor(page, '/api/v1/portal/academic/course-selection/enroll', 'POST')
        await page.getByRole('button', { name: '核对并提交', exact: true }).click()
        assert.equal((await read(await preflight)).allowed, true); await read(await enrolled)
        await expect(page.getByRole('heading', { name: '选课已确认', exact: true })).toBeVisible()
        await page.getByRole('button', { name: '查看我的选课与报名', exact: true }).click()
      }
      if (!record || !['SELECTED', 'LOCKED'].includes(record.status)) {
        await submitEnrollment(report.checkpoints.some(item => item.step === droppedStep) ? `R6-reenroll-${key}` : step)
      }
      const reloaded = responseFor(page, recordsPath); await page.reload(); records = await read(await reloaded)
      record = rows(records).find(item => item.selectionCourseId === supply.selectionCourseId)
      assert.ok(record && ['SELECTED', 'LOCKED'].includes(record.status))
      assert.equal(record.batchId, selection.batchId); assert.equal(record.studentId, fixture.colleges[label].studentIds[ordinal - 1])
      if (originalRecordId) assert.equal(record.recordId, originalRecordId, '刷新后必须仍为原本人记录')
      if (savedBatch.status === 'LOCKED') assert.equal(record.status, 'LOCKED')
      await page.getByRole('button', { name: '我的选课与报名', exact: true }).click()
      await expect(page.locator('.selection-record').filter({ hasText: supply.courseName }).filter({ hasText: `记录 ${record.recordId} ·` })).toContainText(record.status === 'LOCKED' ? '名单已锁定' : '已取得名额')
      const reenrollStep = `R6-reenroll-${key}`
      await observed(report.pending?.step === reenrollStep ? reenrollStep : step, { recordId: record.recordId, selectionCourseId: supply.selectionCourseId })
      if (label === 'A' && ordinal === 1 && !report.checkpoints.some(item => item.step === droppedStep)) {
        assert.equal(savedBatch.status, 'OPEN', '原批次已截止，不能补造退课重选页面验收')
        assert.notEqual(report.pending?.step, droppedStep, '退课命令未确认，禁止自动重放')
        await page.locator('.selection-record').filter({ hasText: supply.courseName }).filter({ hasText: `记录 ${record.recordId} ·` }).getByRole('button', { name: '核对退课', exact: true }).click()
        const dialog = page.getByRole('dialog').filter({ hasText: '确认退课' })
        await expect(dialog).toBeVisible(); await beforeWrite(droppedStep)
        const dropped = responseFor(page, '/api/v1/portal/academic/course-selection/drop', 'POST')
        await dialog.getByRole('button', { name: '确认退课', exact: true }).click(); await read(await dropped)
        await expect(page.getByRole('heading', { name: '退课已确认', exact: true })).toBeVisible()
        const readDrop = responseFor(page, recordsPath); await page.reload()
        record = rows(await read(await readDrop)).find(item => item.selectionCourseId === supply.selectionCourseId)
        assert.equal(record?.status, 'DROPPED')
        await page.getByRole('button', { name: '我的选课与报名', exact: true }).click()
        await expect(page.locator('.selection-record').filter({ hasText: supply.courseName }).filter({ hasText: `记录 ${record.recordId} ·` })).toContainText('已退')
        await observed(droppedStep, { recordId: record.recordId, selectionCourseId: supply.selectionCourseId })
        await page.getByRole('button', { name: '可办理课程', exact: true }).click()
        await submitEnrollment(reenrollStep)
        const readAgain = responseFor(page, recordsPath); await page.reload()
        record = rows(await read(await readAgain)).find(item => item.selectionCourseId === supply.selectionCourseId)
        assert.equal(record?.status, 'SELECTED')
        await page.getByRole('button', { name: '我的选课与报名', exact: true }).click()
        await expect(page.locator('.selection-record').filter({ hasText: supply.courseName }).filter({ hasText: `记录 ${record.recordId} ·` })).toContainText('已取得名额')
        await observed(reenrollStep, { recordId: record.recordId, selectionCourseId: supply.selectionCourseId })
      }
    }
    authenticated = true
    await selectSavedBatch(school)
    await selectionCommand('OPEN', 'CLOSED', '截止', 'close')
    await selectionCommand('CLOSED', 'LOCKED', '锁定名单', 'lock')
    report.selectionGradeImpact = {}; await save()
    const existingGrades = []
    let gradeTotal = null
    for (let page = 1; gradeTotal === null || existingGrades.length < gradeTotal; page++) {
      const result = await readOnly('school', `${apiPath}/grade-tasks?termId=${report.termId}&page=${page}&pageSize=100`)
      assert.ok(Number.isInteger(result.total) && result.total >= 0 && Array.isArray(result.items), '正式成绩分页回执不完整')
      if (gradeTotal === null) gradeTotal = result.total
      assert.equal(result.total, gradeTotal, '成绩任务列表办理期间发生变化，禁止推断不存在')
      assert.ok(result.items.length || existingGrades.length === gradeTotal, '成绩任务分页缺项，不能把缺项当成无旧成绩')
      existingGrades.push(...result.items)
      assert.ok(existingGrades.length <= gradeTotal)
      assert.equal(new Set(existingGrades.map(item => item.gradeTaskId)).size, existingGrades.length, '成绩任务分页重复')
    }
    for (let index = 0; index < supplies.length; index++) {
      const supply = supplies[index], label = supplyOwners[index]
      for (const role of ['school', `college${label}`, `teacher${label}`]) {
        const page = pages[role]; await selectSavedBatch(page)
        const courseRow = page.locator('.aa-selection-detail table tbody tr').filter({ hasText: supply.courseName })
        const rosterResponse = responseFor(page, `${apiPath}/selection/courses/${supply.selectionCourseId}/roster`)
        await courseRow.getByRole('button', { name: '名单', exact: true }).click()
        const roster = await read(await rosterResponse)
        assert.equal(roster.total, 2); assert.deepEqual(new Set(roster.items.map(item => item.studentId)), new Set(fixture.colleges[label].studentIds))
        assert.ok(roster.items.every(item => item.status === 'LOCKED'))
        await expect(page.getByRole('dialog').filter({ hasText: '选课名单' })).toContainText('名单已锁定')
        await observed(`R6-roster-${role}-${supply.selectionCourseId}`, { selectionCourseId: supply.selectionCourseId, memberCount: 2 })
      }
      const matched = existingGrades.filter(item => item.teachingTaskId === supply.teachingTaskId)
      const impact = { noGradeTasks: matched.length === 0, gradeTaskIds: matched.map(item => item.gradeTaskId), evidence: [] }
      report.selectionGradeImpact[supply.teachingTaskId] = impact
      if (matched.length === 1) report.gradeTaskIds[supply.teachingTaskId] = matched[0].gradeTaskId
      for (const task of matched) {
        assert.equal(task.termId, report.termId, '旧成绩任务必须属于原学期')
        const evidence = await readOnly(`college${label}`, `${apiPath}/grade-tasks/${task.gradeTaskId}/review-evidence`)
        impact.evidence.push({ gradeTaskId: task.gradeTaskId, current: evidence.roster?.current === true,
          rosterVersionId: evidence.roster?.rosterVersionId || null, blockers: evidence.blockers?.map(item => item.code) || [] })
      }
      await save()
    }
    for (const { page, supply, studentId } of studentPages) {
      authenticated = false
      const readback = responseFor(page, '/api/v1/portal/academic/course-selection/records')
      await page.reload(); const confirmed = await read(await readback)
      const records = Array.isArray(confirmed) ? confirmed : confirmed.items || confirmed.list || []
      const record = records.find(item => item.selectionCourseId === supply.selectionCourseId)
      assert.equal(record?.batchId, selection.batchId); assert.equal(record?.studentId, studentId)
      assert.equal(record?.status, 'LOCKED')
      await page.getByRole('button', { name: '我的选课与报名', exact: true }).click()
      await expect(page.locator('.selection-record').filter({ hasText: supply.courseName }).filter({ hasText: `记录 ${record.recordId} ·` })).toContainText('名单已锁定')
    }
    await observed('R6-selection', { batchId: selection.batchId, studentCount: 4, supplyCount: 2, status: 'LOCKED' })

    // R6 prepares the same exam before graduation can block later closure.
    // The H local-gap proof is read-only and never certifies the school archive.
    activePage = school; authenticated = true
    const examClassrooms = await readOnly('school', `${apiPath}/classrooms?keyword=${encodeURIComponent(roomCode)}&page=1&pageSize=100`)
    assert.equal(examClassrooms.total, examClassrooms.items.length, '原教室检索未读全')
    const examClassroom = examClassrooms.items.find(item => item.roomCode === roomCode)
    assert.ok(report.classroomId, '缺少原排课教室编号，不得猜测考场资源')
    assert.equal(examClassroom?.classroomId, report.classroomId)
    assert.equal(examClassroom.roomName, roomName)
    assert.equal(examClassroom.status, 'AVAILABLE'); assert.equal(examClassroom.allowExam, true)
    const thirdTeacher = fixture.accounts.teacherC
    assert.ok(thirdTeacher?.loginName && thirdTeacher.teacherKey && thirdTeacher.userId, '缺少原第三监考教师资料')
    const thirdTeacherResult = await readOnly('school', `${apiPath}/courses/teachers/search?keyword=${encodeURIComponent(thirdTeacher.loginName)}`)
    const thirdTeacherMatches = thirdTeacherResult.items.filter(item => item.loginName === thirdTeacher.loginName)
    assert.equal(thirdTeacherMatches.length, 1, '原第三监考教师必须是本租户在职正规教师')
    assert.equal(thirdTeacherMatches[0].teacherKey, thirdTeacher.teacherKey)
    assert.equal(thirdTeacherMatches[0].value, thirdTeacher.userId)
    await observed('R6-exam-resources', { classroomId: examClassroom.classroomId, thirdTeacherUserId: thirdTeacher.userId, teacherDirectoryVerified: true, teacherLoginVerified: false })
    assert.equal((await readOnly('school', selectionPath)).status, 'LOCKED', '补充考试计划仅使用已正式锁定选课批次')
    const examSourceTasks = Object.fromEntries(['A', 'B'].map(label => [label, supplies[supplyOwners.indexOf(label)].teachingTaskId]))
    const examSources = Object.fromEntries(['A', 'B'].map(label => [label, {
      teachingTaskId: examSourceTasks[label], selectionCourseId: supplies[supplyOwners.indexOf(label)].selectionCourseId,
      collegeId: fixture.colleges[label].collegeId, classId: fixture.colleges[label].classId,
      teacherKey: fixture.accounts[`teacher${label}`].teacherKey, studentIds: fixture.colleges[label].studentIds.map(String),
    }]))
    if (!closedJourney) {
      const historicalExam = await readOnly('school', `${apiPath}/exam/batches/${report.examBatchId}`)
      assert.equal(historicalExam.termId, report.termId); assert.equal(historicalExam.status, 'ARCHIVED')
      const historicalCourses = await readOnly('school', `${apiPath}/exam/batches/${report.examBatchId}/courses?page=1&pageSize=20`)
      assert.equal(historicalCourses.total, 2)
      assert.deepEqual(new Set(historicalCourses.items.map(item => item.teachingTaskId)), new Set([report.taskIds.A[0], report.taskIds.B[0]]))
    }
    report.selectionExamPlan ||= { termId: report.termId, selectionBatchId: selection.batchId,
      historicalExamBatchId: closedJourney ? null : report.examBatchId, sources: examSources, examCourseIds: {}, examCourseOwners: {}, examRoomIds: {}, examInvigilatorIds: {} }
    const examPlan = report.selectionExamPlan
    assert.equal(examPlan.termId, report.termId); assert.equal(examPlan.selectionBatchId, selection.batchId)
    assert.equal(examPlan.historicalExamBatchId, closedJourney ? null : report.examBatchId)
    assert.deepEqual(examPlan.sources, examSources, '补充考试计划来源、学院、教师和本人冻结名单必须每次恢复重核')
    await save()
    const examPath = `${apiPath}/exam/batches`
    const examName = `${objectPrefix} 选课锁定补充考试计划`
    let examList = await visit(school, '/admin/academic-affairs/exam', examPath)
    assert.equal(examList.total, examList.items.length, '考试批次列表未读全')
    const examMatches = examList.items.filter(item => item.batchName === examName && item.termId === report.termId)
    assert.ok(examMatches.length <= 1, '同学期同名考试批次重复')
    let examBatchId = examPlan.examBatchId || examMatches[0]?.batchId
    if (examPlan.examBatchId) assert.equal(examMatches[0]?.batchId, examBatchId)
    if (!examBatchId) {
      await phase('校教务通过考务页面建立同学期两院考试批次')
      await school.getByRole('button', { name: '创建考试批次', exact: true }).click()
      const drawer = school.getByRole('dialog', { name: '新建考试批次', exact: true })
      await choose(drawer, '学期', `${objectPrefix} 学期责任接力`)
      await drawer.getByPlaceholder('如 2024秋期末考试').fill(examName)
      await beforeWrite('H-selection-exam-batch')
      const created = responseFor(school, examPath, 'POST')
      await drawer.getByRole('button', { name: '创建', exact: true }).click()
      examBatchId = (await read(await created)).batchId
      assert.equal(typeof examBatchId, 'string')
      examPlan.examBatchId = examBatchId; await save()
    } else examPlan.examBatchId = examBatchId
    let examBatch = await readOnly('school', `${examPath}/${examBatchId}`)
    assert.equal(examBatch.termId, report.termId)
    assert.ok(['DRAFT', 'COURSE_CONFIRMED', 'ARRANGED', 'PUBLISHED', 'FINISHED', 'ARCHIVED'].includes(examBatch.status))
    await observed('H-selection-exam-batch', { batchId: examBatchId, termId: report.termId })
    const examCoursesPath = `${examPath}/${examBatchId}/courses`
    const examTaskIds = [examSourceTasks.A, examSourceTasks.B]
    assert.equal(new Set(examTaskIds).size, 2)
    let examCourses = await readOnly('school', `${examCoursesPath}?page=1&pageSize=20`)
    assert.equal(examCourses.total, examCourses.items.length)
    if (examCourses.total === 0) {
      await phase('学校从两院已终审教学任务真实圈定考试课程')
      await visit(school, '/admin/academic-affairs/exam', examPath)
      await school.locator('.aaexam-batch').filter({ hasText: examName }).click()
      const candidatesResponse = responseFor(school, `${examPath}/${examBatchId}/course-candidates`)
      await school.getByRole('button', { name: '+ 批量圈课', exact: true }).click()
      const candidates = await read(await candidatesResponse)
      assert.equal(candidates.total, candidates.items.length, '考试候选任务未读全')
      const courseDrawer = school.getByRole('dialog', { name: '批量圈定应考课程', exact: true })
      for (const taskId of examTaskIds) {
        const candidate = candidates.items.find(item => item.teachingTaskId === taskId)
        assert.ok(candidate, '同学期已终审教学任务未进入正式考试候选')
        const checkbox = courseDrawer.locator('label.app-checkbox').filter({ hasText: candidate.courseName })
          .filter({ hasText: candidate.teachingClassName })
        await expect(checkbox).toHaveCount(1)
        await checkbox.click()
        await expect(checkbox.locator('input[type="checkbox"]')).toBeChecked()
      }
      const previewResponse = responseFor(school, `${examPath}/${examBatchId}/course-candidates/preview`, 'POST')
      await courseDrawer.getByRole('button', { name: '预览圈课', exact: true }).click()
      const preview = await read(await previewResponse)
      assert.equal(preview.ready, 2); assert.equal(preview.blocked, 0)
      await beforeWrite('H-selection-exam-courses')
      const circled = responseFor(school, `${examPath}/${examBatchId}/course-candidates/confirm`, 'POST')
      await courseDrawer.getByRole('button', { name: '确认圈定 2 门', exact: true }).click()
      const receipt = await read(await circled)
      assert.equal(receipt.succeeded, 2); assert.equal(receipt.failed, 0)
      examCourses = await readOnly('school', `${examCoursesPath}?page=1&pageSize=20`)
      assert.equal(examCourses.total, 2)
      assert.ok(examCourses.items.every(row => row.status === 'PENDING_CONFIRM'))
    }
    assert.equal(examCourses.total, 2)
    assert.deepEqual(new Set(examCourses.items.map(row => row.teachingTaskId)), new Set(examTaskIds))
    const courseAudits = []
    for (const row of examCourses.items) {
      const account = fixture.accounts.school
      const audit = assertActor(auditRows({ tenantId: fixture.tenantId, bizType: 'EXAM_COURSE',
        bizId: row.examCourseId, action: 'EXAM_COURSE_ADD', account }),
      { roleCode: account.roleCode, pendingAt: report.pending?.step === 'H-selection-exam-courses' ? report.pending.sentAt : null })
      courseAudits.push(audit.id)
    }
    await observed('H-selection-exam-courses', { batchId: examBatchId, taskIds: examTaskIds, courseAuditIds: courseAudits })
    const examCourseIds = {}
    for (const label of ['A', 'B']) {
      const row = examCourses.items.find(item => item.teachingTaskId === examSourceTasks[label])
      assert.equal(row?.collegeId, fixture.colleges[label].collegeId)
      assert.equal(row.batchId, examBatchId); assert.equal(row.classId, examSources[label].classId)
      assert.equal(row.teacherKey, examSources[label].teacherKey)
      examCourseIds[label] = row.examCourseId
      examPlan.examCourseIds[label] = row.examCourseId
      examPlan.examCourseOwners[row.examCourseId] = `college${label}`
    }
    await save()
    const confirmOwnExamCourse = async label => {
      const role = `college${label}`, page = pages[role], courseId = examCourseIds[label]
      let own = await readOnly(role, `${examCoursesPath}?page=1&pageSize=20`)
      assert.equal(own.total, 1); assert.equal(own.items[0]?.examCourseId, courseId)
      if (own.items[0].status === 'PENDING_CONFIRM') {
        await phase(`学院 ${label} 在本人考务队列确认本院考试课程`)
        await visit(page, '/admin/academic-affairs/exam', examPath)
        await page.locator('.aaexam-batch').filter({ hasText: examName }).click()
        const row = page.getByRole('row').filter({ hasText: own.items[0].courseName })
        await expect(row).toHaveCount(1)
        await beforeWrite(`H-selection-exam-course-confirm-${courseId}`)
        const confirmed = responseFor(page, `${apiPath}/exam/courses/${courseId}/confirm`, 'POST')
        await row.getByRole('button', { name: '确认', exact: true }).click()
        const receipt = await read(await confirmed)
        assert.equal(receipt.examCourseId, courseId)
      }
      own = await readOnly(role, `${examCoursesPath}?page=1&pageSize=20`)
      assert.equal(own.items[0]?.status, 'CONFIRMED')
      assert.equal(own.items[0].teachingTaskId, examSourceTasks[label])
      assert.equal(own.items[0].teacherKey, examSources[label].teacherKey)
      assert.deepEqual(new Set((own.items[0].rosterIdentity?.studentIds || []).map(String)), new Set(examSources[label].studentIds))
      await observed(`H-selection-exam-course-confirm-${courseId}`, { courseId, collegeId: fixture.colleges[label].collegeId })
    }
    await confirmOwnExamCourse('B')

    const archivePath = `${apiPath}/archive/batches`
    const precheckPath = `${apiPath}/archive/precheck`
    const missingProof = report.checkpoints.find(item => item.step === 'H-selection-A-missing')?.proof
    const repairedProof = report.checkpoints.find(item => item.step === 'H-selection-A-repaired')?.proof
    if (missingProof) {
      assert.equal(missingProof.batchId, examBatchId); assert.equal(missingProof.aExamCourseId, examCourseIds.A); assert.equal(missingProof.bExamCourseId, examCourseIds.B)
      assert.ok(missingProof.aLocalExamGap > 0); assert.equal(missingProof.bLocalExamGap, 0); assert.equal(missingProof.bSchoolResult, 'UNKNOWN')
    }
    if (repairedProof) {
      assert.ok(missingProof, '补充计划必须保留原始缺项现场证据')
      assert.equal(repairedProof.batchId, examBatchId); assert.equal(repairedProof.aExamCourseId, examCourseIds.A); assert.equal(repairedProof.bExamCourseId, examCourseIds.B); assert.equal(repairedProof.aLocalExamGap, 0)
      await confirmOwnExamCourse('A')
    } else {
    const collegeArchive = {}
    for (const label of ['A', 'B']) {
      const role = `college${label}`
      collegeArchive[label] = await visit(pages[role], `/admin/academic-affairs/archive/precheck?termId=${report.termId}`, precheckPath)
      assert.equal(collegeArchive[label].termId, report.termId)
      assert.equal(collegeArchive[label].scopeType, 'COLLEGE')
      assert.equal(collegeArchive[label].domains.length, 13)
    }
    examPlan.archiveCollegePrecheck = Object.fromEntries(['A', 'B'].map(label => [label, {
      result: collegeArchive[label].result,
      blockers: collegeArchive[label].domains.filter(item => ['BLOCKED', 'UNKNOWN'].includes(item.result))
        .map(item => ({ domain: item.domain, ruleCode: item.ruleCode, route: item.route })),
    }]))
    await save()
    const examDomain = label => collegeArchive[label].domains.find(item => item.domain === 'EXAM')
    const localExamGap = label => examDomain(label)?.evidence?.find(item => item.type === 'COLLEGE_ARCHIVE_SCOPE')?.localBlockingCount
    assert.equal(localExamGap('B'), 0, '学院 B 本院考试课程已确认，局部缺项应归零')
    assert.equal(examDomain('B').result, 'UNKNOWN', '本院补齐不等于学校全校考务已封存')
    if (examCourses.items.find(item => item.examCourseId === examCourseIds.A)?.status === 'PENDING_CONFIRM') {
      assert.ok(localExamGap('A') > 0, '学院 A 考试课程仍待本人确认，应出现本院局部缺项')
      await observed('H-selection-A-missing', { batchId: examBatchId, aExamCourseId: examCourseIds.A, bExamCourseId: examCourseIds.B, aRuleCode: examDomain('A').ruleCode,
        aLocalExamGap: localExamGap('A'), bLocalExamGap: localExamGap('B'), bSchoolResult: examDomain('B').result })
    } else assert.ok(report.checkpoints.some(item => item.step === 'H-selection-A-missing'), '学院 A 局部缺项的原始证据尚未记录')
    await confirmOwnExamCourse('A')
    collegeArchive.A = await visit(pages.collegeA, `/admin/academic-affairs/archive/precheck?termId=${report.termId}`, precheckPath, true)
    assert.equal(collegeArchive.A.termId, report.termId)
    assert.equal(collegeArchive.A.domains.find(item => item.domain === 'EXAM')?.evidence?.find(item => item.type === 'COLLEGE_ARCHIVE_SCOPE')?.localBlockingCount, 0,
      '学院 A 确认课程后本院考务缺项须经正式预检归零')
    await observed('H-selection-A-repaired', { batchId: examBatchId, aExamCourseId: examCourseIds.A, bExamCourseId: examCourseIds.B, aLocalExamGap: 0 })

    }

    // The college-local repair above only clears each college's own pending
    // course confirmation. School coordination remains UNKNOWN until the same
    // exam batch is arranged, published, attended, finished and archived.
    const selectExamBatch = async () => {
      const list = await visit(school, `/admin/academic-affairs/exam?termId=${report.termId}`, examPath)
      assert.ok(list.items.some(item => item.batchId === examBatchId && item.termId === report.termId))
      await school.locator('.aaexam-batch').filter({ hasText: examName }).click()
      await expect(school.locator('.aaexam-title')).toHaveText(examName)
    }
    examBatch = await readOnly('school', `${examPath}/${examBatchId}`)
    if (examBatch.status === 'DRAFT') {
      await phase('校教务核对两院课程已由本人确认并推进考试批次')
      await selectExamBatch()
      await school.getByRole('button', { name: '推进', exact: true }).click()
      await beforeWrite('H-selection-exam-batch-confirm')
      const advanced = responseFor(school, `${examPath}/${examBatchId}/confirm-courses`, 'POST')
      await school.getByRole('dialog', { name: '推进(课程确认完成)', exact: true }).getByRole('button', { name: '确认', exact: true }).click()
      assert.equal((await read(await advanced)).batchId, examBatchId)
    }
    examBatch = await readOnly('school', `${examPath}/${examBatchId}`)
    assert.ok(['COURSE_CONFIRMED', 'ARRANGED', 'PUBLISHED', 'FINISHED', 'ARCHIVED'].includes(examBatch.status))
    await observed('H-selection-exam-batch-confirm', { batchId: examBatchId, status: examBatch.status })

    if (!closedJourney && report.pending?.step === 'H-selection-exam-invigilator-A-1') {
      const roomId = examPlan.examRoomIds.A, courseId = examCourseIds.A
      assert.ok(roomId && courseId); assert.equal(examBatch.publishedAt, null)
      assert.ok(['COURSE_CONFIRMED', 'ARRANGED'].includes(examBatch.status), '已发布批次不得通过此恢复改期')
      const rejection = rejectedInvigilatorProof(previousRun, roomId)
      assert.deepEqual(previousRun.pending, report.pending, '保留拒绝证据必须对应当前同一命令及发送时间')
      assert.deepEqual((await readOnly('school', `${apiPath}/exam/rooms/${roomId}/invigilators`)).items, [], '被拒绝的考场必须仍无监考')
      const query = String.raw`
import json, os, sys
from urllib.parse import urlsplit, unquote
import pymysql
u = urlsplit(os.environ['DATABASE_URL'])
assert (u.scheme, u.hostname, u.port, u.path) == ('mysql+pymysql', '127.0.0.1', 3311, '/student_lifecycle_v5_e2e')
tenant, room, course, actor, pending = sys.argv[1:]
assert all(x.isdecimal() for x in (tenant, room, course, actor))
conn = pymysql.connect(host=u.hostname, port=u.port, user=unquote(u.username or ''), password=unquote(u.password or ''), database=u.path[1:], autocommit=False)
try:
    with conn.cursor() as cur:
        cur.execute('START TRANSACTION READ ONLY')
        cur.execute('SELECT exam_course_id FROM t_aa_exam_room WHERE tenant_id=%s AND id=%s AND is_deleted=0', (tenant, room))
        assert cur.fetchone() == (int(course),)
        cur.execute('SELECT COUNT(*) FROM t_aa_exam_invigilator WHERE tenant_id=%s AND exam_room_id=%s', (tenant, room))
        assert cur.fetchone()[0] == 0
        cur.execute('SELECT COUNT(*) FROM t_aa_exam_audit_trail WHERE tenant_id=%s AND biz_type=%s AND action=%s AND operator=%s AND occurred_at >= %s', (tenant, 'EXAM_INVIGILATOR', 'EXAM_INVIGILATOR_ADD', 'db-' + actor, pending))
        assert cur.fetchone()[0] == 0
        conn.rollback()
    print(json.dumps({'roomRows': 0, 'actorAddAuditsSincePending': 0}))
finally:
    conn.close()
`
      const noWrite = JSON.parse(execFileSync(process.env.E2E_V5_PYTHON, ['-c', query, fixture.tenantId, roomId, courseId,
        fixture.accounts.school.userId, new Date(rejection.sentAt).toISOString().replace('T', ' ').replace('Z', '')],
      { cwd: root, env: process.env, encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] }))
      const original = (await readOnly('school', `${examCoursesPath}?page=1&pageSize=20`)).items.find(item => item.examCourseId === courseId)
      assert.equal(original.examDate, '2027-07-05'); assert.equal(original.startTime, '09:00'); assert.equal(original.endTime, '11:00')
      const originalAudit = assertActor(auditRows({ tenantId: fixture.tenantId, bizType: 'EXAM_COURSE', bizId: courseId,
        action: 'EXAM_COURSE_SCHEDULE', account: fixture.accounts.school }), { roleCode: fixture.accounts.school.roleCode })
      examPlan.scheduleRecovery = { originalDate: original.examDate, originalScheduleAuditId: originalAudit.id,
        dates: { A: '2027-07-07', B: '2027-07-08' }, rejectedCommand: rejection, noWrite }
      await observed(`${rejection.step}-rejected`, { ...rejection, ...noWrite, resolution: '正式拒绝且无新增，不重放原命令；另行经页面改期' })
      report.pending = null; await save()
    }
    const expectedExamDates = journeyInput?.examDates || { A: '2027-07-07', B: '2027-07-08' }
    const examDates = examPlan.scheduleRecovery?.dates || expectedExamDates
    assert.deepEqual(examDates, expectedExamDates)
    assert.ok(Object.values(examDates).every(date => date >= termInput.startDate && date <= termInput.endDate))
    const historicalSchedule = []
    for (const batch of examList.items.filter(item => item.batchId !== examBatchId)) {
      const list = await readOnly('school', `${examPath}/${batch.batchId}/courses?page=1&pageSize=100`)
      assert.equal(list.total, list.items.length, '历史考试安排必须读全，不能猜测空闲日期')
      for (const course of list.items) {
        assert.ok(!Object.values(examDates).includes(course.examDate), '候选改期日期已有历史考试，停止办理')
        historicalSchedule.push({ batchId: batch.batchId, courseId: course.examCourseId, examDate: course.examDate, startTime: course.startTime, endTime: course.endTime })
      }
    }
    if (examPlan.scheduleRecovery) { examPlan.scheduleRecovery.historicalSchedule = historicalSchedule; await save() }
    for (const label of ['A', 'B']) {
      const courseId = examCourseIds[label]
      const expectedStudents = fixture.colleges[label].studentIds.map(String)
      const coursePath = `${apiPath}/exam/courses/${courseId}`
      const courseRows = () => readOnly('school', `${examCoursesPath}?page=1&pageSize=20`)
      const exactCourse = async () => {
        const list = await courseRows()
        assert.equal(list.total, 2)
        const course = list.items.find(item => item.examCourseId === courseId)
        assert.ok(course && course.status === 'CONFIRMED')
        assert.deepEqual(new Set((course.rosterIdentity?.studentIds || []).map(String)), new Set(expectedStudents),
          '考试课程必须使用对应教学任务的正式冻结名单')
        return course
      }
      let course = await exactCourse()
      const examRow = () => school.getByRole('row').filter({ hasText: course.courseName }).filter({ hasText: course.className })
      const replan = label === 'A' && !!examPlan.scheduleRecovery
      const scheduleStep = `H-selection-exam-schedule-${replan ? 'replan-' : ''}${label}`
      if (course.examDate && course.examDate !== examDates[label]) {
        assert.ok(replan && course.examDate === examPlan.scheduleRecovery.originalDate, '已有考试日期不符，禁止未经核对覆盖')
        assert.ok(['COURSE_CONFIRMED', 'ARRANGED'].includes(examBatch.status) && !examBatch.publishedAt)
      }
      if (course.examDate !== examDates[label]) {
        await phase(`校教务为学院 ${label} 正式考试课程设置本学期考试时间`)
        await selectExamBatch()
        await expect(examRow()).toHaveCount(1)
        await examRow().getByRole('button', { name: '设时间', exact: true }).click()
        const drawer = school.getByRole('dialog', { name: '设置考试时间', exact: true })
        await drawer.locator('.app-date input').fill(examDates[label])
        await drawer.locator('.app-date input').press('Enter')
        await drawer.locator('input[type="time"]').nth(0).fill('09:00')
        await drawer.locator('input[type="time"]').nth(1).fill('11:00')
        await beforeWrite(scheduleStep)
        const scheduled = responseFor(school, `${coursePath}/schedule`, 'PUT')
        await drawer.getByRole('button', { name: '保存', exact: true }).click()
        const response = await scheduled
        assert.equal(response.request().postDataJSON().examDate, examDates[label], '考试日期选择器须提交正式学期内的日期')
        assert.equal((await read(response)).examCourseId, courseId)
      }
      course = await exactCourse()
      assert.equal(course.examDate, examDates[label]); assert.equal(course.startTime, '09:00'); assert.equal(course.endTime, '11:00')
      await observed(scheduleStep, { courseId, examDate: course.examDate, startTime: course.startTime, endTime: course.endTime,
        ...(replan ? { originalDate: examPlan.scheduleRecovery.originalDate, originalScheduleAuditId: examPlan.scheduleRecovery.originalScheduleAuditId } : {}) })

      const roomsPath = `${coursePath}/rooms`
      let rooms = await readOnly('school', roomsPath)
      assert.ok(rooms.items.length <= 1, '本故事一门课程只使用一间正式考场，已有多间须人工核对')
      if (!rooms.items.length) {
        await phase(`校教务为学院 ${label} 考试课程编排正式考场`)
        await selectExamBatch()
        await expect(examRow()).toHaveCount(1)
        await examRow().getByRole('button', { name: '考场', exact: true }).click()
        const drawer = school.getByRole('dialog', { name: `考场编排 · ${course.courseName}`, exact: true })
        const picker = drawer.locator('.app-remote-select').filter({ hasText: '选择教室' })
        await picker.getByRole('combobox').click()
        await picker.locator('input').fill(roomCode)
        await picker.getByRole('option').filter({ hasText: roomName }).click()
        await beforeWrite(`H-selection-exam-room-${label}`)
        const added = responseFor(school, roomsPath, 'POST')
        await drawer.getByRole('button', { name: '添加考场', exact: true }).click()
        const receipt = await read(await added)
        assert.equal(receipt.examCourseId, courseId)
        examPlan.examRoomIds[label] = receipt.examRoomId; await save()
      }
      rooms = await readOnly('school', roomsPath)
      assert.equal(rooms.items.length, 1)
      const examRoom = rooms.items[0], roomId = examRoom.examRoomId
      assert.equal(roomId, examPlan.examRoomIds[label] || roomId)
      assert.equal(examRoom.classroomText, roomName)
      assert.ok(examRoom.capacity >= expectedStudents.length)
      examPlan.examRoomIds[label] = roomId; await save()
      await observed(`H-selection-exam-room-${label}`, { courseId, roomId, classroomId: examClassroom.classroomId })

      const seatsPath = `${apiPath}/exam/rooms/${roomId}/seats`
      let seats = await readOnly('school', seatsPath)
      if (!seats.items.length) {
        await phase(`校教务按学院 ${label} 冻结名单经页面铺位`)
        await selectExamBatch()
        await examRow().getByRole('button', { name: '考场', exact: true }).click()
        const drawer = school.getByRole('dialog', { name: `考场编排 · ${course.courseName}`, exact: true })
        await beforeWrite(`H-selection-exam-seats-${roomId}`)
        const assigned = responseFor(school, seatsPath, 'POST')
        await drawer.getByRole('button', { name: '按冻结名单铺位', exact: true }).click()
        assert.equal((await read(await assigned)).seatCount, expectedStudents.length)
      }
      seats = await readOnly('school', seatsPath)
      assert.deepEqual(new Set(seats.items.map(item => item.studentId)), new Set(expectedStudents))
      assert.ok(seats.items.every(item => item.attendanceStatus === 'NOT_STARTED' || item.attendanceStatus === 'PRESENT'))
      await observed(`H-selection-exam-seats-${roomId}`, { roomId, studentIds: expectedStudents })

      const invigilatorsPath = `${apiPath}/exam/rooms/${roomId}/invigilators`
      let invigilators = await readOnly('school', invigilatorsPath)
      // 正式考务规则禁止任课教师监考本人课程，两院教师交叉监考。
      const teachers = [fixture.accounts[`teacher${label === 'A' ? 'B' : 'A'}`], fixture.accounts.teacherC]
      assert.ok(invigilators.items.every(item => teachers.some(teacher => teacher.teacherKey === item.teacherKey)),
        '考场已有非预期监考安排，禁止猜测本人责任')
      for (const teacher of teachers) {
        const key = `${label}-${teachers.indexOf(teacher) + 1}`
        if (!invigilators.items.some(item => item.teacherKey === teacher.teacherKey)) {
          await phase(`校教务为学院 ${label} 指定正式教师监考`)
          await selectExamBatch()
          await examRow().getByRole('button', { name: '考场', exact: true }).click()
          const drawer = school.getByRole('dialog', { name: `考场编排 · ${course.courseName}`, exact: true })
          const picker = drawer.locator('.app-remote-select').filter({ hasText: '选择监考教师' })
          await picker.getByRole('combobox').click()
          const searched = school.waitForResponse(response => {
            const url = new URL(response.url())
            return url.pathname === `${apiPath}/courses/teachers/search` && url.searchParams.get('keyword') === teacher.loginName
          }, { timeout: 120_000 })
          await picker.locator('input').fill(teacher.loginName)
          const teacherOptions = await read(await searched)
          const matchedTeacher = (teacherOptions.items || teacherOptions.list || teacherOptions)
            .find(item => item.loginName === teacher.loginName || item.teacherKey === teacher.teacherKey)
          assert.ok(matchedTeacher, '正式教师检索未返回原监考教师资料')
          await picker.getByRole('option').filter({ hasText: matchedTeacher.label || matchedTeacher.teacherName || matchedTeacher.realName }).click()
          await beforeWrite(`H-selection-exam-invigilator-${key}`)
          const assigned = responseFor(school, invigilatorsPath, 'POST')
          await drawer.getByRole('button', { name: '指定监考', exact: true }).click()
          const receipt = await read(await assigned)
          assert.equal(receipt.examRoomId, roomId); assert.equal(receipt.teacherKey, teacher.teacherKey)
          invigilators = await readOnly('school', invigilatorsPath)
        }
        const invigilatorId = invigilators.items.find(item => item.teacherKey === teacher.teacherKey)?.invigilatorId
        assert.ok(invigilatorId, '正式监考指派未写入考场')
        examPlan.examInvigilatorIds[key] = invigilatorId
        if (!report.checkpoints.some(item => item.step === `H-selection-exam-invigilator-${key}`))
          await observed(`H-selection-exam-invigilator-${key}`, { roomId, invigilatorId, teacherUserId: teacher.userId })
      }
      assert.deepEqual(new Set(invigilators.items.map(item => item.teacherKey)), new Set(teachers.map(item => item.teacherKey)))
      await save()
    }

    examBatch = await readOnly('school', `${examPath}/${examBatchId}`)
    if (['COURSE_CONFIRMED', 'ARRANGED'].includes(examBatch.status)) {
      const readiness = await readOnly('school', `${examPath}/${examBatchId}/readiness`)
      assert.equal(readiness.batchId, examBatchId)
      assert.equal(readiness.canPublish, true, '两院冻结名单、考场、铺位与监考未通过正式发布就绪检查')
      for (const key of ['missedCourseCount', 'invigilatorGapCount', 'roomShortageCount']) assert.equal(readiness[key], 0)
      await phase('校教务核对完整就绪后正式发布同一考试批次')
      await selectExamBatch()
      await expect(school.getByRole('button', { name: '发布', exact: true })).toBeEnabled()
      await school.getByRole('button', { name: '发布', exact: true }).click()
      await beforeWrite('H-selection-exam-batch-publish')
      const published = responseFor(school, `${examPath}/${examBatchId}/publish`, 'POST')
      await school.getByRole('dialog', { name: '发布', exact: true }).getByRole('button', { name: '确认', exact: true }).click()
      assert.equal((await read(await published)).batchId, examBatchId)
    }
    examBatch = await readOnly('school', `${examPath}/${examBatchId}`)
    assert.ok(['PUBLISHED', 'FINISHED', 'ARCHIVED'].includes(examBatch.status))
    await observed('H-selection-exam-batch-publish', { batchId: examBatchId, status: examBatch.status })

    report.unverified = ['日常教学', '考务实际到考与结束', '毕业真实上游证据', '全校封存']; await save()
    activePage = school; authenticated = true
    assert.deepEqual(new Set(Object.keys(report.selectionGradeImpact)), new Set(supplies.map(item => item.teachingTaskId)), '必须完成原两个教学任务的正式旧成绩核对')
    assert.ok(Object.values(report.selectionGradeImpact).every(item => item.noGradeTasks ||
      (item.gradeTaskIds.length > 0 && item.evidence.length === item.gradeTaskIds.length && item.evidence.every(value => value.current))),
      '选课锁定后原已发布成绩冻结名单已过期；保留原成绩，需责任人核对后再继续')
    assert.ok(new Date().toLocaleDateString('sv-SE', { timeZone: 'Asia/Shanghai' }) >= termInput.endDate,
      '原学期尚未结束；旧成绩检查点仅作历史证据，本轮不提前办理最终成绩或封存')

    // 隔离虚构学校的策略前置：正式服务拒绝无策略的成绩审核；此配置不计作页面接力动作。
    await phase('学校核验本学期有效成绩策略前置')
    const policyPath = `${apiPath}/grade-policies`
    const policyCode = `${objectPrefix}LATEST_ATTEMPT`.toUpperCase()
    let policies = await readOnly('school', policyPath)
    let activePolicies = policies.filter(row => row.status === 'ACTIVE' && row.effectiveFromTermId === report.termId)
    assert.ok(activePolicies.length <= 1, '同一学期有效成绩策略不唯一，禁止覆盖')
    if (!activePolicies.length) {
      await beforeWrite('F-policy')
      const activated = await school.context().request.post(`${new URL(api).origin}${policyPath}/activate`, {
        headers: { Authorization: `Bearer ${accessTokens.school}` },
        data: { policyCode, attemptStrategy: 'LATEST_ATTEMPT', effectiveFromTermId: report.termId },
      })
      await read(activated)
      policies = await readOnly('school', policyPath)
      activePolicies = policies.filter(row => row.status === 'ACTIVE' && row.effectiveFromTermId === report.termId)
    }
    assert.equal(activePolicies.length, 1)
    assert.equal(activePolicies[0].policyCode, policyCode, '隔离学校已存在不同正式策略，不得自动替换')
    assert.equal(activePolicies[0].attemptStrategy, 'LATEST_ATTEMPT')
    await observed('F-policy', { policyId: activePolicies[0].policyId, termId: report.termId, source: 'isolated-fixture-prerequisite' })

    // F: each formal teaching task has one grade task. Its own teacher enters
    // every roster score, its own college reviews, then school publishes.
    const gradePath = `${apiPath}/grade-tasks`
    const exactGrade = async (role, id) => {
      const result = await readOnly(role, `${gradePath}?taskId=${id}&page=1&pageSize=1`)
      assert.equal(result.total, 1, '成绩任务必须按精确编号回读')
      assert.equal(result.items[0]?.gradeTaskId, id)
      return result.items[0]
    }
    for (const label of ['A', 'B']) {
      const teacherRole = `teacher${label}`, collegeRole = `college${label}`
      for (const teachingTaskId of report.taskIds[label]) {
        let gradeTaskId = report.gradeTaskIds[teachingTaskId]
        const existing = await readOnly(teacherRole, `${gradePath}?termId=${report.termId}&page=1&pageSize=100`)
        assert.equal(existing.total, existing.items.length, '本学期教师成绩任务未读全')
        const matched = existing.items.filter(item => item.teachingTaskId === teachingTaskId)
        assert.ok(matched.length <= 1, '同一教学任务有重复成绩任务')
        if (gradeTaskId) assert.equal(matched[0]?.gradeTaskId, gradeTaskId, '保存的成绩任务不在教师本人正式列表')
        else gradeTaskId = matched[0]?.gradeTaskId
        if (!gradeTaskId) {
          await phase(`任课教师 ${label} 从本人教学任务建立正式成绩任务`)
          const page = pages[teacherRole]
          await visit(page, `/admin/academic-affairs/grade-entry?action=create&teachingTaskId=${teachingTaskId}`, gradePath)
          await expect(page.getByRole('button', { name: '创建任务', exact: true })).toBeVisible()
          await expect(page.getByLabel('已锁定教学任务')).toBeVisible()
          await beforeWrite(`F-create-${teachingTaskId}`)
          const created = responseFor(page, gradePath, 'POST')
          await page.getByRole('button', { name: '创建任务', exact: true }).click()
          gradeTaskId = (await read(await created)).gradeTaskId
          assert.equal(typeof gradeTaskId, 'string')
          report.gradeTaskIds[teachingTaskId] = gradeTaskId; await save()
        }
        report.gradeTaskOwners[gradeTaskId] = { teacher: teacherRole, college: collegeRole, teachingTaskId }
        await save()
        let grade = await exactGrade(teacherRole, gradeTaskId)
        assert.equal(grade.teachingTaskId, teachingTaskId)
        await observed(`F-create-${teachingTaskId}`, { gradeTaskId, teachingTaskId, teacherUserId: fixture.accounts[teacherRole].userId })

        if (['NOT_STARTED', 'INPUTTING', 'RETURNED'].includes(grade.status)) {
          await phase(`任课教师 ${label} 经正式教学名单逐生录入`)
          const page = pages[teacherRole]
          await visit(page, `/admin/academic-affairs/grade-entry?taskId=${gradeTaskId}`, gradePath, true)
          const roster = await readOnly(teacherRole, `${gradePath}/${gradeTaskId}/roster`)
          assert.equal(roster.items.length, 2, '本故事每个虚构班须有两名正式学生')
          assert.deepEqual(new Set(roster.items.map(item => item.studentId)), new Set(fixture.colleges[label].studentIds))
          await page.getByRole('button', { name: '重新读取正式名单', exact: true }).click()
          for (const student of roster.items) {
            const records = await readOnly(teacherRole, `${gradePath}/${gradeTaskId}/records`)
            const record = records.items.find(item => item.studentId === student.studentId)
            if (record?.usualScore === 75 && record?.finalScore === 85 && record?.totalScore != null) {
              await observed(`F-score-${gradeTaskId}-${student.studentId}`, { gradeTaskId, studentId: student.studentId, totalScore: record.totalScore })
              continue
            }
            assert.ok(!record || record.usualScore == null && record.finalScore == null, '已有不同分数，禁止覆盖')
            const row = page.locator('tr').filter({ hasText: student.studentNo })
            await expect(row).toBeVisible()
            const numbers = row.locator('input[type="number"]')
            await numbers.first().fill('75'); await numbers.last().fill('85')
            await beforeWrite(`F-score-${gradeTaskId}-${student.studentId}`)
            const saved = responseFor(page, `${gradePath}/${gradeTaskId}/scores`, 'POST')
            await row.getByRole('button', { name: '保存', exact: true }).click()
            await read(await saved)
            const after = await readOnly(teacherRole, `${gradePath}/${gradeTaskId}/records`)
            const formal = after.items.find(item => item.studentId === student.studentId)
            assert.equal(Number(formal?.usualScore), 75); assert.equal(Number(formal?.finalScore), 85)
            assert.ok(formal?.totalScore != null)
            await observed(`F-score-${gradeTaskId}-${student.studentId}`, { gradeTaskId, studentId: student.studentId, totalScore: formal.totalScore })
          }
          grade = await exactGrade(teacherRole, gradeTaskId)
          assert.ok(grade.allowedActions.includes('SUBMIT'), '正式成绩未形成可提交状态')
          await phase(`任课教师 ${label} 本人提交学院审核`)
          await page.getByRole('button', { name: '提交学院审核', exact: true }).click()
          await beforeWrite(`F-submit-${gradeTaskId}`)
          const submitted = responseFor(page, `${gradePath}/${gradeTaskId}/submit`, 'POST')
          await page.getByRole('dialog', { name: '提交进入学院审核' }).getByRole('button', { name: '确认提交学院' }).click()
          await read(await submitted)
        }
        grade = await exactGrade(teacherRole, gradeTaskId)
        assert.ok(['SUBMITTED', 'ACADEMIC_REVIEW', 'PUBLISHED'].includes(grade.status))
        await observed(`F-submit-${gradeTaskId}`, { gradeTaskId, status: grade.status, actorUserId: fixture.accounts[teacherRole].userId })
        if (grade.status === 'SUBMITTED') {
          await phase(`学院 ${label} 责任账号核对证据并审核成绩`)
          const page = pages[collegeRole]
          await visit(page, `/admin/academic-affairs/grade-college-review?taskId=${gradeTaskId}`, gradePath)
          await expect(page.getByRole('button', { name: '通过并交教务', exact: true })).toBeEnabled()
          await page.getByRole('button', { name: '通过并交教务', exact: true }).click()
          await beforeWrite(`F-college-${gradeTaskId}`)
          const reviewed = responseFor(page, `${gradePath}/${gradeTaskId}/college-review`, 'POST')
          await page.getByRole('dialog', { name: '通过并交教务' }).getByRole('button', { name: '确认通过并交教务' }).click()
          await read(await reviewed)
        }
        grade = await exactGrade('school', gradeTaskId)
        assert.ok(['ACADEMIC_REVIEW', 'PUBLISHED'].includes(grade.status))
        await observed(`F-college-${gradeTaskId}`, { gradeTaskId, status: grade.status, actorUserId: fixture.accounts[collegeRole].userId })
        if (grade.status === 'ACADEMIC_REVIEW') {
          await phase('校教务本人核验并发布正式成绩')
          const page = school
          await visit(page, `/admin/academic-affairs/grade-publish?taskId=${gradeTaskId}`, gradePath)
          await page.getByRole('button', { name: '核验并正式发布', exact: true }).click()
          await beforeWrite(`F-publish-${gradeTaskId}`)
          const published = responseFor(page, `${gradePath}/${gradeTaskId}/publish`, 'POST')
          await page.getByRole('dialog', { name: /发布.*成绩/ }).getByRole('button', { name: '确认发布（不可撤销）' }).click()
          const receipt = await read(await published)
          assert.equal(receipt.gradeTaskId, gradeTaskId)
        }
        grade = await exactGrade('school', gradeTaskId)
        assert.equal(grade.status, 'PUBLISHED')
        assert.ok(grade.courseId && grade.teachingClassId, '正式成绩须回链课程版本及教学班')
        await observed(`F-publish-${gradeTaskId}`, { gradeTaskId, teachingTaskId, status: grade.status,
          courseId: grade.courseId, teachingClassId: grade.teachingClassId, actorUserId: fixture.accounts.school.userId })
      }
    }
    flow = await visit(school, `/admin/academic-affairs?termId=${report.termId}`, `${apiPath}/flow`, true)
    for (const label of ['A', 'B']) {
      const stageGrade = flow.unitProgress.find(item => item.collegeId === fixture.colleges[label].collegeId)?.stages
        .find(item => item.stageCode === 'F90_GRADE')
      assert.equal(stageGrade?.status, 'DONE', `学院 ${label} 正式成绩未完成`)
    }
    await observed('F', { termId: report.termId, gradeTaskIds: Object.values(report.gradeTaskIds) })
    report.uncovered = ['G', 'H']; await save()
    for (const label of ['A', 'B']) {
      const role = `teacher${label === 'A' ? 'B' : 'A'}`, teacherPage = pages[role], roomId = examPlan.examRoomIds[label]
      const attendancePath = `${apiPath}/exam/rooms/${roomId}/attendance`
      const expectedStudents = fixture.colleges[label].studentIds.map(String)
      const pendingAttendance = await readOnly(role, attendancePath)
      assert.deepEqual(new Set(pendingAttendance.items.map(item => item.studentId)), new Set(expectedStudents))
      const needsUiAttendance = pendingAttendance.items.some(item => item.attendanceStatus === 'NOT_STARTED')
      if (needsUiAttendance) {
        assert.equal(examBatch.status, 'PUBLISHED', '未到考座位仍存在时不能将批次当作已结束或归档')
        const invigilations = await visit(teacherPage, '/admin/academic-affairs/exam', `${apiPath}/exam/my-invigilation`)
        assert.ok(invigilations.items.some(item => item.batchId === examBatchId && item.examRoomId === roomId &&
          item.teacherKey === fixture.accounts[role].teacherKey), '正常教师本人监考队列缺少本场正式指派')
        const courseName = (await readOnly('school', `${examCoursesPath}?page=1&pageSize=20`)).items
          .find(item => item.examCourseId === examCourseIds[label])?.courseName
        assert.ok(courseName)
        const teacherRow = teacherPage.getByRole('row').filter({ hasText: examName }).filter({ hasText: courseName })
        await expect(teacherRow).toHaveCount(1)
        const loaded = responseFor(teacherPage, attendancePath)
        await teacherRow.getByRole('button', { name: '到考登记', exact: true }).click()
        await read(await loaded)
      }
      for (const studentId of expectedStudents) {
        const before = await readOnly(role, attendancePath)
        assert.equal(before.examRoomId, roomId); assert.equal(before.batchId, examBatchId)
        const seat = before.items.find(item => item.studentId === studentId)
        assert.ok(seat && Number.isInteger(seat.version), '正式考场缺少当前学生及版本')
        if (seat.attendanceStatus === 'NOT_STARTED') {
          assert.equal(seat.markPresentAction?.allowed, true, '教师本人未获得正式到考办理许可')
          await phase(`监考教师 ${label} 在本人考场逐生登记正常到考`)
          const studentRow = teacherPage.locator('[aria-label="本场到考登记"] table tbody tr').filter({ hasText: seat.studentNo })
          await expect(studentRow).toHaveCount(1)
          await beforeWrite(`H-selection-exam-attendance-${roomId}-${studentId}`)
          const marked = responseFor(teacherPage, `${attendancePath}/${studentId}`, 'PUT')
          await studentRow.getByRole('button', { name: '登记到考', exact: true }).click()
          const receipt = await read(await marked)
          assert.equal(receipt.examRoomId, roomId); assert.equal(receipt.batchId, examBatchId)
          const after = await readOnly(role, attendancePath)
          const updated = after.items.find(item => item.studentId === studentId)
          assert.equal(updated?.attendanceStatus, 'PRESENT')
          assert.equal(updated.version, seat.version + 1, '本人正常到考必须推进该座位版本')
        }
        const confirmed = (await readOnly(role, attendancePath)).items.find(item => item.studentId === studentId)
        assert.equal(confirmed?.attendanceStatus, 'PRESENT')
        await observed(`H-selection-exam-attendance-${roomId}-${studentId}`, { roomId, studentId, version: confirmed.version })
      }
      const collegeAttendance = await readOnly(`college${label}`, attendancePath)
      assert.deepEqual(new Set(collegeAttendance.items.map(item => item.studentId)), new Set(expectedStudents))
      assert.ok(collegeAttendance.items.every(item => item.attendanceStatus === 'PRESENT'))
      const schoolAttendance = await readOnly('school', attendancePath)
      assert.equal(schoolAttendance.batchId, examBatchId)
      assert.deepEqual(schoolAttendance.items.map(item => [item.studentId, item.attendanceStatus, item.version]),
        collegeAttendance.items.map(item => [item.studentId, item.attendanceStatus, item.version]),
        '校级与本院应回读同一考场的到考状态和版本')
      if (needsUiAttendance) await capture(teacherPage, `H-selection-${label}-本人到考登记`)
    }

    for (const [from, to, button, suffix, step] of [
      ['PUBLISHED', 'FINISHED', '结束', 'finish', 'H-selection-exam-batch-finish'],
      ['FINISHED', 'ARCHIVED', '归档', 'archive', 'H-selection-exam-batch-archive'],
    ]) {
      examBatch = await readOnly('school', `${examPath}/${examBatchId}`)
      if (examBatch.status === to || (to === 'FINISHED' && examBatch.status === 'ARCHIVED')) {
        await observed(step, { batchId: examBatchId, status: examBatch.status })
        continue
      }
      assert.equal(examBatch.status, from)
      await phase(`校教务按同一考务批次完成${button}并核对正式终态`)
      await selectExamBatch()
      await school.getByRole('button', { name: button, exact: true }).click()
      await beforeWrite(step)
      const completed = responseFor(school, `${examPath}/${examBatchId}/${suffix}`, 'POST')
      await school.getByRole('dialog', { name: to === 'FINISHED' ? '结束考试' : '归档', exact: true })
        .getByRole('button', { name: '确认', exact: true }).click()
      assert.equal((await read(await completed)).batchId, examBatchId)
      examBatch = await readOnly('school', `${examPath}/${examBatchId}`)
      assert.equal(examBatch.status, to)
      await observed(step, { batchId: examBatchId, status: examBatch.status })
    }
    assert.equal(examBatch.status, 'ARCHIVED')
    await observed('H-selection-exam-closed', { batchId: examBatchId, roomIds: examPlan.examRoomIds })

    // G: graduate only on a complete formal SYSTEM_PASSED evaluation. Missing
    // internship, thesis, student-service or curriculum facts must remain real
    // blockers; reviewer text may not turn UNKNOWN into PASS.
    const gradPath = `${apiPath}/graduation-audit-batches`
    const gradName = `${objectPrefix} ${fixture.cohort.entryYear}级毕业资格审核`
    const gradList = await visit(school, `/admin/academic-affairs/graduation?termId=${report.termId}`, gradPath)
    assert.equal(gradList.total, gradList.items.length, '毕业批次列表未读全')
    const matchingGrad = gradList.items.filter(item => item.batchName === gradName && item.termId === report.termId)
    assert.ok(matchingGrad.length <= 1, '同学期同名毕业审核批次重复')
    let gradBatchId = report.graduationBatchId || matchingGrad[0]?.batchId
    if (report.graduationBatchId) assert.equal(matchingGrad[0]?.batchId, gradBatchId)
    if (!gradBatchId) {
      await phase(`学校通过毕业批次页面圈定同学期 ${fixture.cohort.entryYear} 级学生`)
      await school.getByRole('button', { name: '新建审核批次', exact: true }).click()
      const form = school.locator('section.app-section-card').filter({ hasText: '新建审核批次' })
      await choose(form, '所属学期', `${objectPrefix} 学期责任接力`)
      await form.getByPlaceholder('如 2026届毕业资格审核').fill(gradName)
      await form.getByPlaceholder('如 2023').fill(String(fixture.cohort.entryYear))
      await beforeWrite('G-batch')
      const created = responseFor(school, gradPath, 'POST')
      await form.getByRole('button', { name: '创建', exact: true }).click()
      gradBatchId = (await read(await created)).batchId
      assert.equal(typeof gradBatchId, 'string')
      report.graduationBatchId = gradBatchId; await save()
    } else report.graduationBatchId = gradBatchId
    const exactGradBatch = async () => {
      const result = await readOnly('school', `${gradPath}?batchId=${gradBatchId}&page=1&pageSize=1`)
      assert.equal(result.total, 1); assert.equal(result.items[0]?.batchId, gradBatchId)
      return result.items[0]
    }
    let gradBatch = await exactGradBatch()
    assert.equal(gradBatch.termId, report.termId); assert.equal(gradBatch.gradeYear, String(fixture.cohort.entryYear))
    await observed('G-batch', { batchId: gradBatchId, termId: report.termId, gradeYear: gradBatch.gradeYear })
    const openGradBatch = async () => {
      await visit(school, `/admin/academic-affairs/graduation?termId=${report.termId}`, gradPath)
      const row = school.getByRole('row').filter({ hasText: gradName })
      await expect(row).toBeVisible()
      await row.getByRole('button', { name: '继续预审', exact: true }).click()
    }
    if (gradBatch.status === 'DRAFT') {
      await openGradBatch()
      await beforeWrite('G-generate')
      const generated = responseFor(school, `${gradPath}/${gradBatchId}/generate`, 'POST')
      await school.getByRole('button', { name: '圈定应届生', exact: true }).click()
      const receipt = await read(await generated)
      assert.equal(receipt.batchId, gradBatchId)
    }
    gradBatch = await exactGradBatch()
    assert.equal(gradBatch.total, 4, '应按同一批次圈定两学院四名虚构学生')
    await observed('G-generate', { batchId: gradBatchId, studentCount: gradBatch.total, status: gradBatch.status })
    if (report.requireGraduationReprecheckAfterIdentityRepair) {
      assert.ok(closedJourney && report.checkpointCopy?.originalFailedCasePreserved, '重新预审仅承接已保护的隔离恢复案例')
    }
    if (report.requireGraduationReprecheckAfterIdentityRepair || gradBatch.status === 'GENERATED' || (gradBatch.status === 'PRECHECKED' && gradBatch.abnormal > 0 && report.pending?.step !== 'G-precheck')) {
      await openGradBatch()
      await phase('学校通过正式页面执行十一项毕业资格预审')
      await beforeWrite('G-precheck')
      const prechecked = responseFor(school, `${gradPath}/${gradBatchId}/precheck`, 'POST')
      await school.getByRole('button', { name: '执行十一项预审', exact: true }).click()
      const receipt = await read(await prechecked)
      assert.equal(receipt.batchId, gradBatchId)
      report.requireGraduationReprecheckAfterIdentityRepair = false; await save()
    }
    gradBatch = await exactGradBatch()
    assert.ok(['PRECHECKED', 'ARCHIVED'].includes(gradBatch.status))
    const gradResultsPath = `${gradPath}/${gradBatchId}/results`
    const gradResults = await visit(school, `/admin/academic-affairs/graduation/${gradBatchId}/results`, gradResultsPath)
    assert.equal(gradResults.total, 4, '毕业预审结果须覆盖原四名学生')
    assert.equal(gradResults.items.length, 4)
    const allStudentIds = ['A', 'B'].flatMap(label => fixture.colleges[label].studentIds)
    assert.deepEqual(new Set(gradResults.items.map(item => item.studentId)), new Set(allStudentIds))
    report.graduationBlockers = gradResults.items.flatMap(item => item.items
      .filter(evidence => ['UNKNOWN', 'FAIL'].includes(evidence.result))
      .map(evidence => ({ studentId: item.studentId, domain: evidence.item, result: evidence.result })))
    await save()
    await observed('G-precheck', { batchId: gradBatchId, passed: gradBatch.passed, abnormal: gradBatch.abnormal,
      blockingDomains: [...new Set(report.graduationBlockers.map(item => item.domain))] })
    const schoolResultCard = school.locator('.aa-result-list section').filter({ hasText: gradResults.items[0].realName })
    await expect(schoolResultCard).toHaveCount(1)
    await expect(schoolResultCard.getByRole('button', { name: '学院初审通过', exact: true })).toHaveCount(0)
    await expect(schoolResultCard.getByRole('button', { name: '学院驳回', exact: true })).toHaveCount(0)
    const guardedResultId = gradResults.items[0].resultId
    const guardedBefore = await readOnly('school', `${apiPath}/graduation-results/${guardedResultId}`)
    const guardedCollege = fixture.colleges.A.studentIds.includes(guardedBefore.studentId) ? 'collegeA' : 'collegeB'
    const guardedAudit = () => auditRows({ tenantId: fixture.tenantId, bizType: 'AA_GRAD_AUDIT',
      bizId: guardedResultId, action: 'COLLEGE_APPROVE', account: fixture.accounts[guardedCollege] }).rows
    const auditBefore = guardedAudit()
    const forbiddenReview = await school.context().request.post(`${new URL(api).origin}${apiPath}/graduation-results/${guardedResultId}/college-review`, {
      headers: { Authorization: `Bearer ${accessTokens.school}` }, data: { action: 'APPROVE', note: '' },
    })
    assert.equal(forbiddenReview.status(), 403, '校教务不得代学院做毕业初审')
    const guardedAfter = await readOnly('school', `${apiPath}/graduation-results/${guardedResultId}`)
    assert.equal(guardedAfter.status, guardedBefore.status)
    assert.equal(guardedAfter.reviewNote, guardedBefore.reviewNote)
    assert.deepEqual(guardedAudit(), auditBefore, '拒绝命令不得产生学院初审审计')
    await observed('G-school-college-denied', { resultId: guardedResultId, status: guardedAfter.status, httpStatus: forbiddenReview.status() })
    if (gradBatch.abnormal > 0) {
      await capture(school, 'G01-十一项真实阻断')
      assert.fail('毕业正式预审仍有异常；须由实习、毕设、学工及培养责任页面补齐真实证据后重新预审，禁止越过学院初审与校级终审')
    }
    assert.equal(gradBatch.passed, 4)
    assert.ok(gradResults.items.every(item => item.overall === 'SYSTEM_PASSED'))
    for (const item of gradResults.items) {
      const label = fixture.colleges.A.studentIds.includes(item.studentId) ? 'A' : 'B'
      report.graduationResultOwners[item.resultId] = `college${label}`
    }
    await save()
    for (const label of ['A', 'B']) {
      const role = `college${label}`, page = pages[role]
      for (const studentId of fixture.colleges[label].studentIds) {
        let result = (await readOnly(role, `${gradResultsPath}?page=1&pageSize=20`)).items.find(item => item.studentId === studentId)
        assert.ok(result && result.overall === 'SYSTEM_PASSED')
        if (result.status === 'SYSTEM_PASSED') {
          await phase(`学院 ${label} 对本人学生逐项核对后初审`)
          await visit(page, `/admin/academic-affairs/graduation/${gradBatchId}/results`, gradResultsPath)
          const card = page.locator('.aa-result-list section').filter({ hasText: result.realName })
          await expect(card).toHaveCount(1)
          report.graduationReapprovalAuditIds ||= {}
          report.graduationReapprovalAuditIds[result.resultId] = auditRows({ tenantId: fixture.tenantId,
            bizType: 'AA_GRAD_AUDIT', bizId: result.resultId, action: 'COLLEGE_APPROVE', account: fixture.accounts[role] }).rows.map(row => row.id)
          await save()
          await beforeWrite(`G-college-${result.resultId}`)
          const reviewed = responseFor(page, `${apiPath}/graduation-results/${result.resultId}/college-review`, 'POST')
          await card.getByRole('button', { name: '学院初审通过', exact: true }).click()
          const receipt = await read(await reviewed)
          assert.equal(receipt.resultId, result.resultId)
        }
        result = await readOnly(role, `${apiPath}/graduation-results/${result.resultId}`)
        assert.ok(['ACADEMIC_REVIEW', 'GRADUATED', 'ARCHIVED'].includes(result.status))
        await observed(`G-college-${result.resultId}`, { resultId: result.resultId, studentId, status: result.status })
      }
    }
    for (const studentId of allStudentIds) {
      let result = (await readOnly('school', `${gradResultsPath}?page=1&pageSize=20`)).items.find(item => item.studentId === studentId)
      assert.ok(result && result.overall === 'SYSTEM_PASSED')
      if (studentId === allStudentIds[0]) {
        if (result.status === 'ACADEMIC_REVIEW') {
          const collegeRole = report.graduationResultOwners[result.resultId]
          const collegePage = pages[collegeRole]
          await visit(collegePage, `/admin/academic-affairs/graduation/${gradBatchId}/results`, gradResultsPath)
          const collegeCard = collegePage.locator('.aa-result-list section').filter({ hasText: result.realName })
          await expect(collegeCard).toHaveCount(1)
          await expect(collegeCard.getByRole('button', { name: '教务终审', exact: true })).toHaveCount(0)
          const before = await readOnly(collegeRole, `${apiPath}/graduation-results/${result.resultId}`)
          const schoolFinalAudit = () => auditRows({ tenantId: fixture.tenantId, bizType: 'AA_GRAD_AUDIT',
            bizId: result.resultId, action: 'ACADEMIC_FINAL_IMMUTABLE', account: fixture.accounts.school }).rows
          const auditBefore = schoolFinalAudit()
          const forbiddenFinal = await collegePage.context().request.post(`${new URL(api).origin}${apiPath}/graduation-results/${result.resultId}/final`, {
            headers: { Authorization: `Bearer ${accessTokens[collegeRole]}` }, data: { conclusion: 'GRADUATED', confirm: true },
          })
          assert.equal(forbiddenFinal.status(), 403, '学院初审账号不得代校教务做毕业终审')
          const after = await readOnly(collegeRole, `${apiPath}/graduation-results/${result.resultId}`)
          assert.equal(after.status, before.status)
          assert.equal(after.conclusion, before.conclusion)
          assert.equal(after.reviewNote, before.reviewNote)
          assert.deepEqual(schoolFinalAudit(), auditBefore, '拒绝命令不得产生教务终审审计')
          await observed('G-college-school-denied', { resultId: result.resultId, collegeRole, status: after.status,
            httpStatus: forbiddenFinal.status() })
        } else assert.ok(report.checkpoints.some(item => item.step === 'G-college-school-denied'),
          '已终审结果缺少学院代校级终审被拒的原始证据')
      }
      if (result.status === 'ACADEMIC_REVIEW') {
        await phase('校教务对学院已初审通过的学生做正式毕业终审')
        await visit(school, `/admin/academic-affairs/graduation/${gradBatchId}/results`, gradResultsPath)
        const card = school.locator('.aa-result-list section').filter({ hasText: result.realName })
        await expect(card).toHaveCount(1)
        await card.getByRole('button', { name: '教务终审', exact: true }).click()
        const dialog = school.getByRole('dialog', { name: '教务终审', exact: true })
        await expect(dialog.getByRole('radio', { name: '毕业', exact: true })).toBeChecked()
        await beforeWrite(`G-final-${result.resultId}`)
        const decided = responseFor(school, `${apiPath}/graduation-results/${result.resultId}/final`, 'POST')
        await dialog.getByRole('button', { name: '确认终审并写学籍', exact: true }).click()
        const receipt = await read(await decided)
        assert.equal(receipt.resultId, result.resultId)
      }
      result = await readOnly('school', `${apiPath}/graduation-results/${result.resultId}`)
      assert.ok(['GRADUATED', 'ARCHIVED'].includes(result.status)); assert.equal(result.conclusion, 'GRADUATED')
      await observed(`G-final-${result.resultId}`, { resultId: result.resultId, studentId, conclusion: result.conclusion })
    }
    gradBatch = await exactGradBatch()
    assert.equal(gradBatch.concluded, 4)
    await observed('G', { batchId: gradBatchId, concluded: gradBatch.concluded })
    report.uncovered = ['H']; await save()

    // H starts with the graduation-batch closure. It is distinct from the
    // thirteen-domain term archive that follows.
    if (gradBatch.status !== 'ARCHIVED') {
      await phase('校教务通过审核工作台封存已终审毕业名单')
      await visit(school, `/admin/academic-affairs/graduation/audit-console?batchId=${gradBatchId}&tab=archive`, gradPath)
      await school.getByRole('button', { name: '执行归档', exact: true }).click()
      await beforeWrite('G-archive')
      const archived = responseFor(school, `${gradPath}/${gradBatchId}/archive`, 'POST')
      await school.getByRole('dialog', { name: '确认审核归档', exact: true }).getByRole('button', { name: '确认', exact: true }).click()
      const receipt = await read(await archived)
      assert.equal(receipt.batchId, gradBatchId); assert.equal(receipt.batchClosed, true)
    }
    gradBatch = await exactGradBatch()
    assert.equal(gradBatch.status, 'ARCHIVED')
    await observed('G-archive', { batchId: gradBatchId, status: gradBatch.status })

    const schoolPrecheck = await visit(school, `/admin/academic-affairs/archive/precheck?termId=${report.termId}`, precheckPath)
    assert.equal(schoolPrecheck.scopeType, 'TENANT_ALL')
    assert.equal(schoolPrecheck.termId, report.termId)
    assert.equal(schoolPrecheck.domains.length, 13)
    report.schoolArchiveBlockers = schoolPrecheck.domains.filter(item => ['BLOCKED', 'UNKNOWN'].includes(item.result))
      .map(item => ({ domain: item.domain, result: item.result, ruleCode: item.ruleCode, route: item.route }))
    await observed('H-school-gate', { result: schoolPrecheck.result, blockers: report.schoolArchiveBlockers })
    assert.equal(schoolPrecheck.result, 'PASS', '全校十三域未通过，不得确认学期归档')
    const archiveList = await visit(school, '/admin/academic-affairs/archive', archivePath)
    assert.equal(archiveList.total, archiveList.items.length, '归档批次列表未读全')
    const matchingArchive = archiveList.items.filter(item => item.termId === report.termId && item.status !== 'CANCELLED')
    assert.ok(matchingArchive.length <= 1, '同学期有多个在用归档批次')
    let archiveBatchId = report.archiveBatchId || matchingArchive[0]?.batchId
    if (report.archiveBatchId) assert.equal(matchingArchive[0]?.batchId, archiveBatchId)
    if (!archiveBatchId) {
      await phase('学校通过归档控制台建立同学期十三域批次')
      await school.getByRole('button', { name: '新建归档批次', exact: true }).click()
      const drawer = school.getByRole('dialog', { name: '新建归档批次', exact: true })
      await choose(drawer, '学期', `${objectPrefix} 学期责任接力`)
      await beforeWrite('H-batch')
      const created = responseFor(school, archivePath, 'POST')
      await drawer.getByRole('button', { name: '创建', exact: true }).click()
      archiveBatchId = (await read(await created)).batchId
      assert.equal(typeof archiveBatchId, 'string')
      report.archiveBatchId = archiveBatchId; await save()
    } else report.archiveBatchId = archiveBatchId
    let archive = await readOnly('school', `${archivePath}/${archiveBatchId}`)
    assert.equal(archive.termId, report.termId)
    await observed('H-batch', { batchId: archiveBatchId, termId: report.termId })
    if (archive.status !== 'ARCHIVED') {
      await visit(school, `/admin/academic-affairs/archive?batchId=${archiveBatchId}`, archivePath)
      await phase('学校通过归档控制台执行完整十三域检查')
      await beforeWrite('H-check')
      const checked = responseFor(school, `${archivePath}/${archiveBatchId}/check`, 'POST')
      await school.getByRole('button', { name: '完整性检查', exact: true }).click()
      const receipt = await read(await checked)
      assert.equal(receipt.batchId, archiveBatchId)
      archive = await readOnly('school', `${archivePath}/${archiveBatchId}`)
      assert.equal(archive.status, 'READY'); assert.equal(archive.missingCount, 0)
      assert.equal(archive.items.length, 13)
      assert.ok(archive.items.every(item => ['PASS', 'NOT_APPLICABLE'].includes(item.result)))
      await observed('H-check', { batchId: archiveBatchId, domains: archive.items.map(item => ({ domain: item.domain, result: item.result })) })
      await phase('校教务本人正式封存本学期')
      await school.getByRole('button', { name: '确认归档', exact: true }).click()
      await beforeWrite('H-confirm')
      const confirmed = responseFor(school, `${archivePath}/${archiveBatchId}/confirm`, 'POST')
      await school.getByRole('dialog', { name: '确认归档', exact: true }).getByRole('button', { name: '确认', exact: true }).click()
      const receiptConfirm = await read(await confirmed)
      assert.equal(receiptConfirm.batchId, archiveBatchId)
    }
    archive = await readOnly('school', `${archivePath}/${archiveBatchId}`)
    assert.equal(archive.status, 'ARCHIVED')
    await observed('H-confirm', { batchId: archiveBatchId, status: archive.status })
    const termAfterArchive = await readOnly('school', `${apiPath}/terms/${report.termId}`)
    assert.equal(termAfterArchive.status, 'ARCHIVED')
    await observed('H', { termId: report.termId, batchId: archiveBatchId, termStatus: termAfterArchive.status })
    await finishReadback(studentPages)
  } catch (error) {
    report.failure = { phase: report.phase, type: error.name || 'Error', message: '当前阶段未通过；保留正式对象及待核对命令，未自动重放写入。', sourceLocation: sourceLocation(error) }
    if (authenticated && activePage) await capture(activePage, '当前阶段-失败时脱敏页面').catch(() => {})
    throw new Error('V5 接力未完成，详见无密结果文件中的阶段与回执')
  } finally {
    report.receipts = receipts; report.errors = failures; report.finishedAt = new Date().toISOString()
    await save(); await Promise.all(contexts.map(context => context.close())); await browser.close()
  }
}

if (process.env.E2E_V5_CONTRACT_CHECK === '1') {
  const registration = { actions: {} }
  assert.equal(registrationResumeAction(registration, 'create', null), true)
  assert.throws(() => registrationResumeAction(registration, 'create', { step: 'create' }))
  registration.actions.create = { receipt: { batchId: '2' } }
  assert.throws(() => registrationResumeAction(registration, 'create', null))
  registration.actions.create = { receipt: { batchId: '2' }, audits: [{ id: '10' }], observedAt: '2026-10-02T10:00:00Z' }
  assert.equal(registrationResumeAction(registration, 'create', null), false)
  assert.deepEqual(['PUBLISHED', 'DRAFT'].map(scheduleResumeMode), ['read', 'schedule'])
  assert.equal(scheduleResumeMode('PRE_PUBLISHED'), 'publish')
  assert.throws(() => scheduleResumeMode('SUPERSEDED'))
  assert.equal(journeyContract({}), null)
  const cohort = { entryYear: 2023, expectedGraduateYear: 2026 }
  assert.deepEqual(journeyContract({ journeyInput: structuredClone(closedJourneyInput), cohort }), closedJourneyInput)
  for (const change of [{ databasePort: 3307 }, { scenarioId: 'A-H' }, { objectPrefix: 'v5j_v5gold01_' },
    { term: originalTermInput }, { examDates: { A: '2027-07-07', B: '2027-07-08' } }]) {
    assert.throws(() => journeyContract({ journeyInput: { ...closedJourneyInput, ...change }, cohort }))
  }
  assert.throws(() => journeyContract({ journeyInput: closedJourneyInput, cohort: { entryYear: 2024, expectedGraduateYear: 2027 } }))
  assert.ok(Object.values(closedJourneyInput.examDates).every(date => date >= closedJourneyInput.term.startDate && date <= closedJourneyInput.term.endDate))
  assert.equal((Date.parse(closedJourneyInput.term.endDate) - Date.parse(closedJourneyInput.term.startDate)) / 86_400_000 + 1, 20 * 7)
  console.log('合同及续跑自检通过：原故事兼容、六项串场拒绝、排课分状态续办、注册未知命令与缺审计均阻止重放；未连接浏览器或数据库')
} else if (process.env.E2E_V5_RECOVERY_CHECK === '1') {
  const pathname = `${apiPath}/exam/rooms/3/invigilators`
  const known = { pending: { step: 'H-selection-exam-invigilator-A-1', sentAt: '2026-10-02T09:30:00Z' },
    failure: { phase: '校教务为学院 A 指定正式教师监考' }, receipts: [{ role: 'school', path: pathname, method: 'POST', status: 409 }],
    errors: [{ role: 'school', path: pathname, status: 409 }] }
  assert.equal(rejectedInvigilatorProof(known, '3').step, known.pending.step)
  assert.throws(() => rejectedInvigilatorProof({ ...known, pending: { ...known.pending, step: 'H-selection-exam-schedule-A' } }, '3'))
  assert.throws(() => rejectedInvigilatorProof({ ...known, receipts: [{ ...known.receipts[0], status: 200 }] }, '3'))
  assert.throws(() => rejectedInvigilatorProof(known, '4'))
  assert.throws(() => rejectedInvigilatorProof({ ...known, errors: [...known.errors, { kind: '页面脚本错误' }] }, '3'))
  console.log('已知监考拒绝恢复边界自检通过：1项准入、4项拒绝；未连接浏览器或数据库')
} else if (process.env.E2E_V5_CHILD === '1') {
  // A standalone browser process keeps login fill values out of test-runner API
  // step parameters. No trace, video, storageState, headers or auth bodies are saved.
  await runJourney().catch(error => {
    console.error(JSON.stringify({ type: error.name, sourceLocation: sourceLocation(error) }))
    process.exitCode = 1
  })
} else {
  test.use({ trace: 'off', video: 'off', screenshot: 'off' })
  test.describe('V5 场景 A 至 H：同学期两院责任接力与真实归档门禁', () => {
    test.describe.configure({ mode: 'serial', retries: 0 })
    test('同一学期下六名教职工与原四名学生独立登录并接力办理至正式学期归档', async ({}, testInfo) => {
      test.setTimeout(3_600_000)
      const resultFile = ignoredFile(`${ignoredFile(process.env.E2E_V5_STATE)}.journey.json`)
      const child = spawn(process.execPath, [self], { cwd: root, env: { ...process.env, E2E_V5_CHILD: '1', DEBUG: '', PWDEBUG: '0' }, stdio: 'ignore', windowsHide: true })
      const timer = setTimeout(() => child.kill(), 3_540_000)
      let code
      try { code = await new Promise((resolve, reject) => { child.once('exit', resolve); child.once('error', reject) }) }
      finally { clearTimeout(timer) }
      await testInfo.attach('场景 A-H 无密回执', { path: resultFile, contentType: 'application/json' })
      const result = JSON.parse(await fs.readFile(resultFile, 'utf8'))
      if (result.evidenceDirectory) for (const name of await fs.readdir(result.evidenceDirectory)) {
        if (name.endsWith('.png')) await testInfo.attach(name, { path: path.join(result.evidenceDirectory, name), contentType: 'image/png' })
      }
      expect(code, 'V5 接力未完成：请核对无密回执中的当前阶段，禁止自动重放未确认写入').toBe(0)
      expect(result.passed).toBe(true); expect(result.roles).toHaveLength(6)
    })
  })
}
