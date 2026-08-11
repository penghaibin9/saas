import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { loadInternshipFixture } from '../lib/internship-fixture.mjs'
import { items, loginApi } from '../lib/api-fixture.mjs'
import { StudentLoginPage } from '../pages/login.page.mjs'
import { StaffGraduationPage, StudentGraduationPage } from '../pages/graduation.page.mjs'

const VIEWPORT = { width: 1440, height: 1000 }
const STUDENT_TWO = { tenant: 'sandbox-school', username: 'E2E20260002', password: 'E2eTest@2026' }

function runId() {
  const raw = process.env.GITHUB_RUN_ID || `${Date.now()}`
  return String(raw).replace(/\D/g, '').slice(-12) || String(Date.now()).slice(-12)
}

function isoDay(offset) {
  const date = new Date()
  date.setUTCHours(0, 0, 0, 0)
  date.setUTCDate(date.getUTCDate() + offset)
  return date.toISOString().slice(0, 10)
}

function academicYear() {
  const year = new Date().getUTCFullYear()
  return `${year}-${year + 1}`
}

async function dismissGuide(page) {
  for (const mask of [page.locator('.app-step-guide__mask'), page.locator('.tour-mask')]) {
    if (await mask.isVisible().catch(() => false)) {
      const skip = page.getByRole('button', { name: /跳过引导|跳过/ }).first()
      if (await skip.isVisible().catch(() => false)) await skip.click()
      await mask.waitFor({ state: 'hidden', timeout: 3000 }).catch(() => {})
    }
  }
}

async function settleVisual(page) {
  await page.evaluate(async () => {
    if (document.fonts?.ready) await document.fonts.ready
  })
  await page.waitForLoadState('networkidle', { timeout: 5000 }).catch(() => {})
}

async function capture(page, testInfo, name) {
  await dismissGuide(page)
  await settleVisual(page)
  const viewportPath = testInfo.outputPath(`${name}-1440x1000.png`)
  const fullPath = testInfo.outputPath(`${name}-full.png`)
  await page.screenshot({ path: viewportPath, fullPage: false, animations: 'disabled', caret: 'hide' })
  await page.screenshot({ path: fullPath, fullPage: true, animations: 'disabled', caret: 'hide' })
  await testInfo.attach(`${name}-viewport`, { path: viewportPath, contentType: 'image/png' })
  await testInfo.attach(`${name}-full`, { path: fullPath, contentType: 'image/png' })
}

async function addStaffSession(page, api) {
  await page.addInitScript(({ token }) => {
    window.sessionStorage.setItem('gx_pc_token_v1', token)
  }, { token: api.token })
}

async function openWithApiSession(page, api, path) {
  await addStaffSession(page, api)
  await page.goto(`${config.staffBaseUrl}${path}`)
}

async function setStorage(page, key, value) {
  await page.evaluate(({ storageKey, storageValue }) => {
    window.localStorage.setItem(storageKey, String(storageValue))
  }, { storageKey: key, storageValue: value })
}

async function prepareAidPublicity(admin, studentId) {
  const marker = runId()
  const batchName = `Golden 公示审核 ${marker}`
  const batches = items(await admin.get('/student-affairs/aid/batches', { page: 1, pageSize: 200 }))
  let batch = batches.find((row) => String(row.batchName || '') === batchName)
  if (!batch) {
    batch = await admin.post('/student-affairs/aid/batches', {
      batchName,
      schoolYear: academicYear(),
      publicityDays: 7,
      levelConfig: { levels: ['SPECIAL', 'DIFFICULT', 'GENERAL'] },
      publish: true
    })
  }
  const batchId = String(batch.batchId || batch.id || '')
  if (!batchId) throw new Error('Golden aid publicity batch did not return id')

  let application = items(await admin.get('/student-affairs/aid/applications', {
    batchId, page: 1, pageSize: 200
  })).find((row) => String(row.studentId || '') === String(studentId))

  if (!application) {
    application = await admin.post('/student-affairs/aid/applications', {
      batchId,
      studentId: String(studentId),
      applyLevel: 'DIFFICULT',
      statement: '家庭经济压力较大，需要资助支持完成当前学业与实习安排。',
      memberCount: 4,
      annualIncome: '28000',
      specialTags: ['单亲']
    })
  }

  let current = application
  if (String(current.status || '') !== 'PUBLICITY') {
    current = await admin.get(`/student-affairs/aid/applications/${current.applyId}`)
    for (let i = 0; i < 3 && String(current.status || '') !== 'PUBLICITY'; i += 1) {
      current = await admin.post(`/student-affairs/aid/applications/${current.applyId}/review`, {
        action: 'APPROVE',
        version: current.version
      })
    }
    if (String(current.status || '') !== 'PUBLICITY') {
      current = await admin.post(`/student-affairs/aid/applications/${current.applyId}/review`, {
        action: 'APPROVE',
        level: 'DIFFICULT',
        version: current.version
      })
    }
  }
  if (String(current.status || '') !== 'PUBLICITY') {
    throw new Error(`Golden aid application must stop at PUBLICITY, got ${current.status || 'UNKNOWN'}`)
  }
  return { applyId: String(current.applyId), batchId, studentNo: String(current.studentNo || config.student.username) }
}

async function prepareInternshipChange(studentApi, internshipFixture) {
  const existing = items(await studentApi.get('/portal/internship/change'))
    .find((row) => String(row.status || '') === 'PENDING')
  if (existing) return { id: String(existing.id), batchId: internshipFixture.batchId }

  const created = await studentApi.post('/portal/internship/change', {
    changeType: 'WITHDRAW_POST',
    reason: '当前岗位与后续实践方向不一致，申请退岗后重新接受学校岗位匹配。',
    targetEnterpriseName: '',
    targetPositionName: ''
  })
  if (!created.id) throw new Error('Golden internship change request did not return id')
  if (String(created.status || '') !== 'PENDING') {
    throw new Error(`Golden internship change request must be PENDING, got ${created.status || 'UNKNOWN'}`)
  }
  return { id: String(created.id), batchId: internshipFixture.batchId }
}

async function prepareGraduationReviewFixture(admin) {
  const marker = runId()
  const batchNo = `PW-GOLD-REVIEW-${marker}`
  let batch = items(await admin.get('/graduation/batches', { keyword: batchNo, page: 1, pageSize: 200 }))
    .find((row) => String(row.batchNo || '') === batchNo)

  if (!batch) {
    const year = new Date().getUTCFullYear()
    batch = await admin.post('/graduation/batches', {
      batchName: `Golden 开题审核 ${marker}`,
      batchNo,
      academicYear: academicYear(),
      gradeYear: `${year + 1}届`,
      plannedCount: 1,
      remark: 'Golden Batch 8 review queue; isolated E2E database only'
    })
  }

  if (String(batch.status || '').toUpperCase() !== 'RUNNING') {
    await admin.post(`/graduation/batches/${batch.id}/rules`, {
      rules: {
        score: { advisorWeight: 0.4, reviewerWeight: 0.3, defenseWeight: 0.3 },
        plagiarism: { thresholdPercent: 20, mustPassToDefense: true }
      }
    })
    await admin.post(`/graduation/batches/${batch.id}/stages`, {
      stages: [
        { code: 'TOPIC', name: '选题', startDate: isoDay(-45), endDate: isoDay(-1) },
        { code: 'PROPOSAL', name: '开题', startDate: isoDay(0), endDate: isoDay(30) },
        { code: 'MIDTERM', name: '中期', startDate: isoDay(31), endDate: isoDay(60) },
        { code: 'SUBMISSION', name: '成果', startDate: isoDay(61), endDate: isoDay(90) },
        { code: 'PLAGIARISM', name: '查重', startDate: isoDay(91), endDate: isoDay(100) },
        { code: 'REVIEW', name: '评阅', startDate: isoDay(101), endDate: isoDay(110) },
        { code: 'DEFENSE', name: '答辩', startDate: isoDay(111), endDate: isoDay(125) },
        { code: 'GRADE', name: '成绩', startDate: isoDay(126), endDate: isoDay(145) }
      ]
    })
    const activated = await admin.post(`/graduation/batches/${batch.id}/activate`, {})
    batch = { ...batch, ...(activated || {}), status: 'RUNNING' }
  }

  const profile = items(await admin.get('/students', { keyword: STUDENT_TWO.username, page: 1, pageSize: 50 }))
    .find((row) => String(row.studentNo || row.loginName || '') === STUDENT_TWO.username)
  if (!profile) throw new Error(`Golden graduation review student ${STUDENT_TWO.username} not found`)

  let gdStudent = items(await admin.get('/graduation/gd-students', {
    batchId: String(batch.id), keyword: STUDENT_TWO.username, page: 1, pageSize: 200
  })).find((row) => String(row.studentNo || '') === STUDENT_TWO.username)
  if (!gdStudent) {
    gdStudent = await admin.post('/graduation/gd-students', {
      studentId: String(profile.id || profile.studentId),
      batchId: String(batch.id),
      remark: 'Golden Batch 8 isolated proposal-review student'
    })
  }
  await admin.post(`/graduation/gd-students/${gdStudent.id}/eligibility`, {
    status: 'QUALIFIED', reason: 'Golden Batch 8 proposal review fixture'
  })

  let mentor = items(await admin.get('/graduation/gd-mentors', {
    keyword: config.mentor.username, page: 1, pageSize: 200
  })).find((row) => String(row.teacherNo || '') === config.mentor.username)
  if (!mentor) throw new Error('Golden Batch 8 requires the dedicated E2E mentor bootstrap')

  try {
    await admin.post('/graduation/gd-mentor-assignments/assign', {
      gdStudentId: String(gdStudent.id),
      mentorId: String(mentor.id),
      reason: 'Golden Batch 8 isolated proposal-review fixture'
    })
  } catch (error) {
    if (!/已分配|已有导师|重复|ACTIVE|存在/.test(error.message)) throw error
  }

  const title = `Golden 开题审核课题 ${marker}`
  let topic = items(await admin.get('/graduation/gd-topics', {
    batchId: String(batch.id), keyword: title, archiveView: 'active', page: 1, pageSize: 200
  })).find((row) => String(row.title || '') === title)
  if (!topic) {
    topic = await admin.post('/graduation/gd-topics', {
      title,
      batchId: String(batch.id),
      sourceType: 'TEACHER',
      advisorName: 'E2E指导教师A',
      category: '软件工程',
      difficulty: 'MEDIUM',
      requirements: '完成真实开题审核队列的需求、方案、风险与进度说明。',
      outcome: '开题报告与完整审核证据链',
      capacity: 1,
      submitReview: true
    })
  }
  if (String(topic.reviewStatus || '') !== 'APPROVED') {
    try {
      topic = await admin.post(`/graduation/gd-topics/${topic.id}/review`, {
        action: 'APPROVE', comment: 'Golden Batch 8 课题审核通过'
      })
    } catch (error) {
      if (!/已审核|无需审核|状态/.test(error.message)) throw error
    }
  }

  try {
    await admin.post(`/graduation/gd-students/${gdStudent.id}/assign-topic`, { topicId: String(topic.id) })
  } catch (error) {
    if (!/已分配|重复|已选|存在/.test(error.message)) throw error
  }

  try {
    await admin.post(`/graduation/gd-taskbooks/${gdStudent.id}/issue`, {
      objective: '形成一条独立真实的开题待审记录',
      content: '学生签署任务书后，通过学生 PC 上传并提交开题报告，管理端只做 Screenshot A。'
    }, { batchId: String(batch.id) })
  } catch (error) {
    if (!/已下发|已存在|状态/.test(error.message)) throw error
  }

  return {
    runId: marker,
    batchId: String(batch.id),
    batchName: String(batch.batchName || ''),
    gdStudentId: String(gdStudent.id),
    studentNo: STUDENT_TWO.username,
    topicTitle: title
  }
}

test.describe.serial('Golden rollout · review / workflow queues · Batch 8', () => {
  let adminApi
  let internshipFixture
  let aidFixture
  let internshipChangeFixture
  let graduationFixture

  test.beforeAll(async () => {
    adminApi = await loginApi(config.sandboxAdmin)
    internshipFixture = await loadInternshipFixture()
    const studentApi = await loginApi(config.student)

    aidFixture = await prepareAidPublicity(adminApi, internshipFixture.studentId)
    internshipChangeFixture = await prepareInternshipChange(studentApi, internshipFixture)
    graduationFixture = await prepareGraduationReviewFixture(adminApi)
  })

  test('Student Affairs aid publicity review · Screenshot A', async ({ page }, testInfo) => {
    await page.setViewportSize(VIEWPORT)
    await openWithApiSession(page, adminApi, '/admin/student-affairs/aid/publicity')

    await expect(page).toHaveURL(/\/admin\/student-affairs\/aid\/publicity/)
    await expect(page.getByRole('heading', { name: '困难认定公示待办', exact: true })).toBeVisible()
    await expect(page.locator('.sa-toolbar')).toBeVisible()
    await expect(page.locator('.sa-grid--metrics')).toBeVisible()
    await expect(page.locator('.dt')).toBeVisible()
    await expect(page.locator('.dt__tr').filter({ hasText: aidFixture.studentNo }).first()).toBeVisible()

    await capture(page, testInfo, 'rollout-review-affairs-aid-publicity-a')
  })

  test('Internship change review queue · Screenshot A', async ({ page }, testInfo) => {
    await page.setViewportSize(VIEWPORT)
    await openWithApiSession(page, adminApi, `/admin/internship/changes?panel=pending&id=${encodeURIComponent(internshipChangeFixture.id)}`)
    await setStorage(page, 'internship.selectedBatchId', internshipChangeFixture.batchId)
    await page.reload()

    await expect(page).toHaveURL(/\/admin\/internship\/changes/)
    await expect(page.getByRole('heading', { name: '实习变更审核', exact: true })).toBeVisible()
    await expect(page.locator('.mp-tabs')).toBeVisible()
    await expect(page.locator('.lv-list')).toBeVisible()
    await expect(page.locator('.lv-main')).toBeVisible()
    await expect(page.locator('.lv-main')).toContainText(internshipFixture.studentName)
    await expect(page.locator('.lv-main')).toContainText(/退岗|当前岗位与后续实践方向不一致/)

    await capture(page, testInfo, 'rollout-review-internship-change-a')
  })

  test('Graduation proposal review queue · Screenshot A', async ({ page }, testInfo) => {
    await page.setViewportSize(VIEWPORT)

    await new StudentLoginPage(page, config.studentBaseUrl).login(STUDENT_TWO)
    const studentGraduation = new StudentGraduationPage(page, config.studentBaseUrl)
    await studentGraduation.open()
    const proposalStep = studentGraduation.step('开题')
    if (!(await proposalStep.getByText(/待审核|待审阅|已提交/).count())) {
      await studentGraduation.signTaskbookIfNeeded()
      await studentGraduation.submitProposal({
        suffix: graduationFixture.runId,
        fileName: `proposal-review-${graduationFixture.runId}.pdf`
      })
    }

    await addStaffSession(page, adminApi)
    const staffGraduation = new StaffGraduationPage(page, config.staffBaseUrl, graduationFixture)
    await staffGraduation.openProposals('PENDING_REVIEW')
    await staffGraduation.selectStudent()

    await expect(page).toHaveURL(/\/admin\/graduation\/proposals/)
    await expect(page.getByRole('heading', { name: '开题审核', exact: true })).toBeVisible()
    await expect(page.locator('.pr-split')).toBeVisible()
    await expect(page.locator('.pr-list')).toBeVisible()
    await expect(page.locator('.pr-pane')).toBeVisible()
    await expect(page.locator('.prc')).toContainText(graduationFixture.topicTitle)

    await capture(page, testInfo, 'rollout-review-graduation-proposal-a')
  })
})