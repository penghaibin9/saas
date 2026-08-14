import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { loadInternshipFixture } from '../lib/internship-fixture.mjs'
import { items, loginApi } from '../lib/api-fixture.mjs'
import { StaffLoginPage } from '../pages/login.page.mjs'

const VIEWPORT = { width: 1440, height: 1000 }

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

async function prepareGraduationDashboardFixture() {
  const rawRun = process.env.GITHUB_RUN_ID || `${Date.now()}`
  const runId = String(rawRun).replace(/\D/g, '').slice(-12) || String(Date.now()).slice(-12)
  const batchNo = `PW-GOLD-DASH-${runId}`
  const admin = await loginApi(config.sandboxAdmin)
  let batch = items(await admin.get('/graduation/batches', { keyword: batchNo, page: 1, pageSize: 50 }))
    .find((item) => item.batchNo === batchNo)

  if (!batch) {
    const year = new Date().getUTCFullYear()
    batch = await admin.post('/graduation/batches', {
      batchName: `Golden 毕设看板验收 ${runId}`,
      batchNo,
      academicYear: academicYear(),
      gradeYear: `${year + 1}届`,
      plannedCount: 1,
      remark: 'Golden dashboard screenshot only; isolated E2E database'
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
    batch = { ...batch, ...(await admin.post(`/graduation/batches/${batch.id}/activate`, {})), status: 'RUNNING' }
  }

  return { batchId: String(batch.id), batchName: batch.batchName }
}

async function dismissGuide(page) {
  const masks = [
    page.locator('.app-step-guide__mask'),
    page.locator('.tour-mask')
  ]
  for (const mask of masks) {
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

async function setBatchStorage(page, key, value) {
  await page.evaluate(({ storageKey, storageValue }) => {
    window.localStorage.setItem(storageKey, String(storageValue))
  }, { storageKey: key, storageValue: value })
}

test.describe.serial('Golden rollout · representative business pages', () => {
  let internshipFixture
  let graduationFixture

  test.beforeAll(async () => {
    internshipFixture = await loadInternshipFixture()
    graduationFixture = await prepareGraduationDashboardFixture()
  })

  test('Student affairs dashboard · Screenshot C', async ({ page }, testInfo) => {
    await page.setViewportSize(VIEWPORT)
    await new StaffLoginPage(page, config.staffBaseUrl).login(config.sandboxAdmin)
    await page.goto(`${config.staffBaseUrl}/admin/student-affairs/dashboard`)

    await expect(page).toHaveURL(/\/admin\/student-affairs\/dashboard/)
    await expect(page.locator('.sa-summary-strip')).toBeVisible()
    await expect(page.locator('.sa-grid--priority')).toBeVisible()
    await expect(page.locator('.sa-grid--metrics')).toBeVisible()
    await expect(page.locator('body')).not.toContainText('正在加载学工看板真实数据…')

    await capture(page, testInfo, 'rollout-student-affairs-c')
  })

  test('Internship dashboard · Screenshot C', async ({ page }, testInfo) => {
    await page.setViewportSize(VIEWPORT)
    await new StaffLoginPage(page, config.staffBaseUrl).login(config.sandboxAdmin)
    await setBatchStorage(page, 'internship.selectedBatchId', internshipFixture.batchId)
    await page.goto(`${config.staffBaseUrl}/admin/internship?batchId=${encodeURIComponent(internshipFixture.batchId)}`)

    await expect(page).toHaveURL(/\/admin\/internship/)
    await expect(page.locator('.idb-path')).toBeVisible()
    await expect(page.locator('#idb-batch-progress')).toBeVisible()
    await expect(page.locator('#idb-todos')).toBeVisible()
    await expect(page.locator('body')).not.toContainText(/请先选择实习批次|存在多个进行中批次/)

    await capture(page, testInfo, 'rollout-internship-c')
  })

  test('Graduation dashboard · Screenshot C', async ({ page }, testInfo) => {
    await page.setViewportSize(VIEWPORT)
    await new StaffLoginPage(page, config.staffBaseUrl).login(config.sandboxAdmin)
    await setBatchStorage(page, 'graduation.selectedBatchId', graduationFixture.batchId)
    await page.goto(`${config.staffBaseUrl}/admin/graduation?batchId=${encodeURIComponent(graduationFixture.batchId)}`)

    await expect(page).toHaveURL(/\/admin\/graduation/)
    await expect(page.locator('.gdb-page')).toBeVisible()
    await expect(page.locator('.gdb-overview')).toBeVisible()
    await expect(page.locator('.gdb-modstats')).toBeVisible()
    await expect(page.locator('.gdb-todos')).toBeVisible()
    await expect(page.locator('body')).not.toContainText('请先选择或创建毕设批次')

    await capture(page, testInfo, 'rollout-graduation-c')
  })
})
