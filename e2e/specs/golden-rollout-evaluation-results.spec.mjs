import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { loadInternshipFixture } from '../lib/internship-fixture.mjs'
import { items, loginApi } from '../lib/api-fixture.mjs'

const VIEWPORT = { width: 1440, height: 1000 }

function runId() {
  const raw = process.env.GITHUB_RUN_ID || `${Date.now()}`
  return String(raw).replace(/\D/g, '').slice(-12) || String(Date.now()).slice(-12)
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

async function openWithApiSession(page, api, path) {
  await page.addInitScript(({ token }) => {
    window.sessionStorage.setItem('gx_pc_token_v1', token)
  }, { token: api.token })
  await page.goto(`${config.staffBaseUrl}${path}`)
}

async function setStorage(page, key, value) {
  await page.evaluate(({ storageKey, storageValue }) => {
    window.localStorage.setItem(storageKey, String(storageValue))
  }, { storageKey: key, storageValue: value })
}

async function prepareCounselorEvaluation(admin) {
  const marker = runId()
  const definitions = [
    { name: `师德师风 · Golden ${marker}`, weight: 30, maxScore: 100, score: 94 },
    { name: `学生工作实绩 · Golden ${marker}`, weight: 40, maxScore: 100, score: 89 },
    { name: `风险响应与协同 · Golden ${marker}`, weight: 30, maxScore: 100, score: 96 }
  ]

  // Playwright retries create a fresh worker in the same isolated database. Make
  // the fixture replay-safe instead of treating an expected retry as a duplicate
  // business create.
  const existingIndicators = items(await admin.get('/student-affairs/counselor-eval/indicators', { pageSize: 200 }))
  const scores = {}
  for (const definition of definitions) {
    let indicator = existingIndicators.find((row) => String(row.name || '') === definition.name)
    if (!indicator) {
      indicator = await admin.post('/student-affairs/counselor-eval/indicators', {
        name: definition.name,
        weight: definition.weight,
        maxScore: definition.maxScore
      })
    }
    const indicatorId = String(indicator.indicatorId || indicator.id || '')
    if (!indicatorId) throw new Error(`Golden counselor evaluation indicator missing id: ${definition.name}`)
    scores[indicatorId] = definition.score
  }

  const periodCode = `GOLD-${new Date().getUTCFullYear()}-${marker}`
  const existingEvaluations = items(await admin.get('/student-affairs/counselor-eval/evals', { pageSize: 200 }))
  let evaluation = existingEvaluations.find((row) => (
    String(row.periodCode || '') === periodCode && String(row.counselorKey || '') === 'e2e_counselor_a'
  ))
  if (!evaluation) {
    evaluation = await admin.post('/student-affairs/counselor-eval/evals', {
      periodCode,
      counselorKey: 'e2e_counselor_a',
      counselorName: 'E2E辅导员A',
      scores
    })
  }
  if (!evaluation.evalId) throw new Error('Golden counselor evaluation did not return evalId')
  return { evalId: String(evaluation.evalId), periodCode }
}

async function prepareInternshipScoreConfig(admin) {
  const saved = await admin.post('/internship/scores/config', {
    checkinWeight: 20,
    weeklyWeight: 20,
    monthlyWeight: 10,
    enterpriseWeight: 30,
    schoolWeight: 20,
    passLine: 60
  })
  if (!saved.configId) throw new Error('Golden internship score config did not return configId')
  return { configId: String(saved.configId) }
}

async function prepareGraduationStatsBatch(admin) {
  const marker = runId()
  const batchNo = `PW-GOLD-STATS-${marker}`
  let batch = items(await admin.get('/graduation/batches', { keyword: batchNo, page: 1, pageSize: 50 }))
    .find((row) => String(row.batchNo || '') === batchNo)

  if (!batch) {
    const year = new Date().getUTCFullYear()
    batch = await admin.post('/graduation/batches', {
      batchName: `Golden 毕设结果统计 ${marker}`,
      batchNo,
      academicYear: academicYear(),
      gradeYear: `${year + 1}届`,
      plannedCount: 120,
      remark: 'Golden result-analysis screenshot only; isolated E2E database'
    })
  }

  // Keep this batch DRAFT and independent. The lifecycle suite owns its own
  // student/topic/taskbook chain; visual evidence must never pre-create those facts.
  if (String(batch.status || '').toUpperCase() !== 'DRAFT') {
    throw new Error(`Golden stats batch must remain DRAFT, got ${batch.status || 'UNKNOWN'}`)
  }
  return { batchId: String(batch.id), batchName: batch.batchName, batchNo }
}

test.describe.serial('Golden rollout · evaluation / scores / result analysis · Batch 6', () => {
  let adminApi
  let affairsFixture
  let internshipFixture
  let internshipScoreFixture
  let graduationFixture

  test.beforeAll(async () => {
    // Batch 6 creates only formal, isolated facts. It intentionally does not force
    // the internship lifecycle from ONBOARD to ASSESSING merely to manufacture a score row,
    // and it does not reuse the graduation lifecycle fixture/student/taskbook chain.
    adminApi = await loginApi(config.sandboxAdmin)
    affairsFixture = await prepareCounselorEvaluation(adminApi)
    internshipFixture = await loadInternshipFixture()
    internshipScoreFixture = await prepareInternshipScoreConfig(adminApi)
    graduationFixture = await prepareGraduationStatsBatch(adminApi)
  })

  test('Student Affairs counselor evaluation · Screenshot A', async ({ page }, testInfo) => {
    await page.setViewportSize(VIEWPORT)
    await openWithApiSession(page, adminApi, '/admin/student-affairs/counselor-eval')

    await expect(page).toHaveURL(/\/admin\/student-affairs\/counselor-eval/)
    await expect(page.locator('.sa-summary-strip')).toBeVisible()
    await expect(page.locator('.sa-workflow-strip')).toBeVisible()
    await expect(page.locator('.ce-indbar')).toBeVisible()
    await expect(page.locator('.dt')).toBeVisible()
    await expect(page.locator('.dt__tr').filter({ hasText: affairsFixture.periodCode }).first()).toBeVisible()

    await capture(page, testInfo, 'rollout-results-affairs-counselor-eval-a')
  })

  test('Internship comprehensive scores · Screenshot A', async ({ page }, testInfo) => {
    await page.setViewportSize(VIEWPORT)
    await openWithApiSession(page, adminApi, '/admin/internship/scores')
    await setStorage(page, 'internship.selectedBatchId', internshipFixture.batchId)
    await page.reload()

    await expect(page).toHaveURL(/\/admin\/internship\/scores/)
    await expect(page.locator('.cfg')).toBeVisible()
    await expect(page.locator('.bar')).toBeVisible()
    await expect(page.locator('.dt')).toBeVisible()
    await expect(page.getByText('五项权重配置')).toBeVisible()
    expect(internshipScoreFixture.configId).not.toBe('')

    await capture(page, testInfo, 'rollout-results-internship-scores-a')
  })

  test('Graduation result statistics · Screenshot A', async ({ page }, testInfo) => {
    await page.setViewportSize(VIEWPORT)
    await openWithApiSession(page, adminApi, '/admin/graduation/stats-report')
    await setStorage(page, 'graduation.selectedBatchId', graduationFixture.batchId)
    await page.reload()

    await expect(page).toHaveURL(/\/admin\/graduation\/stats-report/)
    await expect(page.getByRole('heading', { name: '毕设统计报表', exact: true })).toBeVisible()
    await expect(page.locator('.gs-grid').first()).toBeVisible()
    await expect(page.locator('.mp-card').filter({ hasText: '开题统计' }).first()).toBeVisible()
    await expect(page.locator('.mp-card').filter({ hasText: '成绩评定统计' }).first()).toBeVisible()

    await capture(page, testInfo, 'rollout-results-graduation-stats-a')
  })
})