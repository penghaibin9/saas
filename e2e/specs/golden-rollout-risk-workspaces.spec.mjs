import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { items, loginApi } from '../lib/api-fixture.mjs'
import { loadInternshipFixture } from '../lib/internship-fixture.mjs'

const VIEWPORT = { width: 1440, height: 1000 }
const graduationRiskStudent = { tenant: 'sandbox-school', username: 'E2E20260003', password: 'E2eTest@2026' }

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

function runId() {
  const raw = process.env.GITHUB_RUN_ID || `${Date.now()}`
  return String(raw).replace(/\D/g, '').slice(-12) || String(Date.now()).slice(-12)
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

async function openWithApiSession(page, api, path) {
  await page.addInitScript(({ token }) => {
    window.sessionStorage.setItem('gx_pc_token_v1', token)
  }, { token: api.token })
  await page.goto(`${config.staffBaseUrl}${path}`)
}

async function setBatchStorage(page, key, value) {
  await page.evaluate(({ storageKey, storageValue }) => {
    window.localStorage.setItem(storageKey, String(storageValue))
  }, { storageKey: key, storageValue: value })
}

async function prepareStudentAffairsRisk(api) {
  const profiles = items(await api.get('/students', { keyword: 'E2E20260002', page: 1, pageSize: 50 }))
  const profile = profiles.find((item) => String(item.studentNo || item.loginName || '') === 'E2E20260002')
  if (!profile) throw new Error('Golden risk student E2E20260002 not found')

  const marker = runId()
  const created = await api.post('/student-affairs/risk/records', {
    studentId: String(profile.id || profile.studentId),
    source: 'MANUAL',
    sourceRefId: `golden-risk-${marker}`,
    riskLevel: 'HIGH',
    title: `连续缺勤风险 · Golden ${marker}`,
    detail: 'Golden UI 风险工作区验收：学生近期连续缺勤，需要辅导员尽快核实情况并分派跟进。'
  })
  return { riskId: String(created.riskId || created.id || ''), studentNo: 'E2E20260002' }
}

async function prepareInternshipRisk(api) {
  const fixture = await loadInternshipFixture()
  const marker = runId()
  const complaint = await api.post('/internship/complaints', {
    source: 'STUDENT',
    targetType: 'ENTERPRISE',
    studentId: String(fixture.studentId),
    batchId: String(fixture.batchId),
    category: '实习补贴异常',
    severity: 'HIGH',
    content: `Golden UI 风险工作区验收 ${marker}：企业未按约定时间发放实习补贴，学生已多次沟通仍未解决。`,
    complainantContact: '13800001111'
  })
  await api.post(`/internship/complaints/${complaint.id}/transition`, { action: 'ACCEPT', ownerName: 'Golden 风险责任人' })
  const linked = await api.post(`/internship/complaints/${complaint.id}/to-risk`, {})
  return { ...fixture, complaintId: String(complaint.id), riskId: String(linked.riskId || '') }
}

async function prepareGraduationRisk(api) {
  const marker = runId()
  const batchNo = `PW-GOLD-RISK-${marker}`
  let batch = items(await api.get('/graduation/batches', { keyword: batchNo, page: 1, pageSize: 50 }))
    .find((item) => item.batchNo === batchNo)

  if (!batch) {
    const year = new Date().getUTCFullYear()
    batch = await api.post('/graduation/batches', {
      batchName: `Golden 毕设风险工作区 ${marker}`,
      batchNo,
      academicYear: academicYear(),
      gradeYear: `${year + 1}届`,
      plannedCount: 1,
      remark: 'Golden risk workspace screenshot only; isolated E2E database'
    })
  }

  if (String(batch.status || '').toUpperCase() !== 'RUNNING') {
    await api.post(`/graduation/batches/${batch.id}/rules`, {
      rules: {
        score: { advisorWeight: 0.4, reviewerWeight: 0.3, defenseWeight: 0.3 },
        plagiarism: { thresholdPercent: 20, mustPassToDefense: true }
      }
    })
    await api.post(`/graduation/batches/${batch.id}/stages`, {
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
    batch = { ...batch, ...(await api.post(`/graduation/batches/${batch.id}/activate`, {})), status: 'RUNNING' }
  }

  const profiles = items(await api.get('/students', { keyword: graduationRiskStudent.username, page: 1, pageSize: 50 }))
  const profile = profiles.find((item) => String(item.studentNo || item.loginName || '') === graduationRiskStudent.username)
  if (!profile) throw new Error(`Golden graduation risk student ${graduationRiskStudent.username} not found`)

  let gdStudent = items(await api.get('/graduation/gd-students', {
    batchId: String(batch.id), keyword: graduationRiskStudent.username, page: 1, pageSize: 50
  })).find((item) => String(item.studentNo || '') === graduationRiskStudent.username)

  if (!gdStudent) {
    gdStudent = await api.post('/graduation/gd-students', {
      studentId: String(profile.id || profile.studentId),
      batchId: String(batch.id),
      remark: 'Golden risk workspace fixture'
    })
  }

  try {
    await api.post(`/graduation/gd-students/${gdStudent.id}/eligibility`, {
      status: 'QUALIFIED', reason: 'Golden 风险工作区隔离资格准备'
    })
  } catch (error) {
    if (!/状态|已认定|无需|QUALIFIED/.test(error.message)) throw error
  }

  const scan = await api.post('/graduation/gd-risks/scan', {}, { batchId: String(batch.id) })
  const risks = items(await api.get('/graduation/gd-risks', { batchId: String(batch.id), page: 1, pageSize: 50 }))
  if (!risks.length) throw new Error(`Golden graduation risk scan created no visible risk: ${JSON.stringify(scan).slice(0, 500)}`)

  return { batchId: String(batch.id), batchName: batch.batchName, riskId: String(risks[0].id || '') }
}

async function closeGraduationRiskFixture(api, fixture) {
  if (!fixture?.batchId) return
  try {
    await api.post(`/graduation/batches/${fixture.batchId}/close`, {})
  } catch (error) {
    if (!/仅「进行中」批次可结束|已结束|CLOSED/.test(error.message)) throw error
  }
}

test.describe.serial('Golden rollout · risk / exception workspaces · Batch 3', () => {
  let adminApi
  let affairsFixture
  let internshipFixture
  let graduationFixture

  test.beforeAll(async () => {
    adminApi = await loginApi(config.sandboxAdmin)
    affairsFixture = await prepareStudentAffairsRisk(adminApi)
    internshipFixture = await prepareInternshipRisk(adminApi)
    graduationFixture = await prepareGraduationRisk(adminApi)
  })

  test.afterAll(async () => {
    await closeGraduationRiskFixture(adminApi, graduationFixture)
  })

  test('Student Affairs risk warning · Screenshot A', async ({ page }, testInfo) => {
    await page.setViewportSize(VIEWPORT)
    await openWithApiSession(page, adminApi, '/admin/student-affairs/risk')

    await expect(page).toHaveURL(/\/admin\/student-affairs\/risk/)
    await expect(page.locator('.sa-grid--metrics')).toBeVisible()
    await expect(page.locator('.dt')).toBeVisible()
    await expect(page.locator('.dt__td').first()).toBeVisible()
    expect(affairsFixture.riskId).not.toBe('')

    await capture(page, testInfo, 'rollout-risk-student-affairs-a')
  })

  test('Internship risk board · Screenshot A', async ({ page }, testInfo) => {
    await page.setViewportSize(VIEWPORT)
    await openWithApiSession(page, adminApi, '/admin/internship/risks')
    await setBatchStorage(page, 'internship.selectedBatchId', internshipFixture.batchId)
    await page.goto(`${config.staffBaseUrl}/admin/internship/risks?batchId=${encodeURIComponent(internshipFixture.batchId)}&panel=board`)

    await expect(page).toHaveURL(/\/admin\/internship\/risks/)
    await expect(page.locator('.ir-focus')).toBeVisible()
    await expect(page.locator('.dt')).toBeVisible()
    await expect(page.locator('.dt__td').first()).toBeVisible()
    expect(internshipFixture.riskId).not.toBe('')

    await capture(page, testInfo, 'rollout-risk-internship-a')
  })

  test('Graduation risk workspace · Screenshot A', async ({ page }, testInfo) => {
    await page.setViewportSize(VIEWPORT)
    await openWithApiSession(page, adminApi, '/admin/graduation/risk-archive?tab=risk')
    await setBatchStorage(page, 'graduation.selectedBatchId', graduationFixture.batchId)
    await page.goto(`${config.staffBaseUrl}/admin/graduation/risk-archive?tab=risk&batchId=${encodeURIComponent(graduationFixture.batchId)}`)

    await expect(page).toHaveURL(/\/admin\/graduation\/risk-archive/)
    await expect(page.locator('.gp-tabs')).toBeVisible()
    await expect(page.locator('.rk-scan-bar')).toBeVisible()
    await expect(page.locator('.rk-split')).toBeVisible()
    await expect(page.locator('.rk-row').first()).toBeVisible()

    await capture(page, testInfo, 'rollout-risk-graduation-a')
  })
})