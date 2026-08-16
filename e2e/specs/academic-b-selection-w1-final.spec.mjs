import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { items, loginApi } from '../lib/api-fixture.mjs'
import { StaffLoginPage, StudentLoginPage } from '../pages/login.page.mjs'

const MINIAPP_BASE = process.env.E2E_MINIAPP_BASE_URL || 'http://localhost:5188'
const COURSE_CODES = ['E2E-B-W1-001', 'E2E-B-W1-002']

async function screenshot(page, testInfo, name) {
  await page.waitForLoadState('networkidle', { timeout: 5_000 }).catch(() => {})
  await page.evaluate(async () => { if (document.fonts?.ready) await document.fonts.ready })
  const path = testInfo.outputPath(`${name}.png`)
  await page.screenshot({ path, fullPage: false, animations: 'disabled', caret: 'hide' })
  await testInfo.attach(name, { path, contentType: 'image/png' })
}

async function dismissGuide(page) {
  const mask = page.locator('.app-step-guide__mask')
  await mask.waitFor({ state: 'visible', timeout: 1_500 }).catch(() => {})
  if (await mask.isVisible().catch(() => false)) {
    const skip = page.getByRole('button', { name: '跳过引导' })
    if (await skip.count()) await skip.click()
  }
}

async function seedSelectionFixture(testInfo) {
  const api = await loginApi(config.multiRole)
  const term = await api.get('/academic-affairs/terms/current')
  const termId = String(term?.termId || term?.id || '')
  expect(termId, `current term missing: ${JSON.stringify(term)}`).toBeTruthy()

  const catalog = items(await api.get('/academic-affairs/courses', {
    keyword: 'E2E-B-W1', status: 'ENABLED', page: 1, pageSize: 50
  }))
  const byCode = new Map(catalog.map((row) => [String(row.courseCode || ''), row]))
  const courses = COURSE_CODES.map((code) => byCode.get(code))
  expect(courses.filter(Boolean).length, `E2E B courses missing: ${JSON.stringify(catalog)}`).toBe(2)

  const suffix = `${String(Date.now()).slice(-7)}-r${testInfo.retry}`
  const create = async (name) => api.post('/academic-affairs/selection/batches', {
    batchName: `${name}-${suffix}`,
    termId,
    applyScope: {}
  })

  const blocked = await create('B-W1-阻断证据')
  const ready = await create('B-W1-跨端闭环')
  for (const row of courses) {
    await api.post(`/academic-affairs/selection/batches/${ready.batchId}/courses`, {
      courseId: String(row.courseId || row.id),
      capacity: 30,
      minCapacity: 0
    })
  }
  return {
    blocked,
    ready,
    courses: courses.map((row) => ({
      id: String(row.courseId || row.id),
      code: String(row.courseCode),
      name: String(row.courseName)
    }))
  }
}

async function loginAcademicAdmin(page) {
  const login = new StaffLoginPage(page, config.staffBaseUrl)
  await login.login(config.multiRole)
  await login.switchRole(/教务处管理员|教务管理员|教务老师|ACADEMIC_ADMIN/)
}

async function selectBatch(page, name) {
  const item = page.locator('.aasel-batches > .aasel-batch').filter({ hasText: name }).first()
  await expect(item).toBeVisible({ timeout: 20_000 })
  await item.click()
  await expect(page.locator('.aasel-detail')).toContainText(name)
}

async function expectBatchStatus(page, label) {
  await expect(page.locator('.aasel-hero-topline')).toContainText(label, { timeout: 20_000 })
}

async function expectNoStalePreflight(page) {
  await expect(page.locator('.aasel-preflight-alert')).toHaveCount(0, { timeout: 20_000 })
}

async function lifecycle(page, actionLabel, apiFragment) {
  const preflight = page.waitForResponse((response) =>
    response.url().includes('/selection/batches/') &&
    response.url().includes('/preflight') &&
    response.request().method() === 'GET'
  )
  await page.getByRole('button', { name: actionLabel, exact: true }).click()
  const checked = await preflight
  expect(checked.ok(), `${actionLabel} preflight HTTP ${checked.status()}`).toBeTruthy()
  const preflightBody = await checked.json()
  expect(preflightBody?.data?.allowed, `${actionLabel} preflight: ${JSON.stringify(preflightBody)}`).toBeTruthy()

  const dialog = page.locator('.app-confirm-dialog')
  await expect(dialog).toBeVisible()
  const command = page.waitForResponse((response) =>
    response.url().includes(apiFragment) && response.request().method() === 'POST'
  )
  await dialog.getByRole('button', { name: '确认', exact: true }).click()
  const result = await command
  expect(result.ok(), `${actionLabel} command HTTP ${result.status()}`).toBeTruthy()
  const body = await result.json()
  expect(body?.code, `${actionLabel} command: ${JSON.stringify(body)}`).toBe(0)
}

async function miniappLogin(page) {
  await page.goto(`${MINIAPP_BASE}/#/pages/login/student/index`)
  const authCard = page.locator('.auth-card')
  await expect(authCard).toBeVisible({ timeout: 20_000 })
  const fields = authCard.getByRole('textbox')
  await expect(fields.nth(0)).toBeVisible()
  await expect(fields.nth(1)).toBeVisible()
  await fields.nth(0).fill(config.student.username)
  await fields.nth(1).fill(config.student.password)
  const agreement = authCard.locator('.agreement__box').first()
  await expect(agreement).toBeVisible()
  await agreement.click()
  await expect(agreement).toHaveClass(/\bon\b/)
  const loginResponse = page.waitForResponse((response) =>
    response.url().includes('/api/v1/auth/login') && response.request().method() === 'POST'
  )
  await authCard.locator('.account-button').first().click()
  const response = await loginResponse
  expect(response.ok(), `miniapp login HTTP ${response.status()}`).toBeTruthy()
  await page.waitForURL(/pages\/student\/home\/index/, { timeout: 60_000 })
}

test.describe.serial('Academic B W1 exact-head final seal', () => {
  test('W0-preserving preflight closes admin → student PC → miniapp with refresh/relogin evidence', async ({ browser }, testInfo) => {
    const fixture = await seedSelectionFixture(testInfo)

    const staffContext = await browser.newContext({ viewport: { width: 1440, height: 900 } })
    const staff = await staffContext.newPage()
    await loginAcademicAdmin(staff)
    await staff.goto(`${config.staffBaseUrl}/admin/academic-affairs/selection`)
    await dismissGuide(staff)

    await selectBatch(staff, fixture.blocked.batchName)
    const blockedPreflight = staff.waitForResponse((response) =>
      response.url().includes(`/selection/batches/${fixture.blocked.batchId}/preflight`) &&
      response.url().includes('action=PUBLISH')
    )
    await staff.getByRole('button', { name: '发布', exact: true }).click()
    const blockedResponse = await blockedPreflight
    const blockedBody = await blockedResponse.json()
    expect(blockedBody?.data?.allowed).toBeFalsy()
    expect((blockedBody?.data?.blockers || []).map((item) => item.code)).toContain('SELECTION_COURSE_EMPTY')
    await expect(staff.locator('.aasel-preflight-alert')).toContainText('批次未配置有效可选课程')
    await expect(staff.locator('.app-confirm-dialog')).toHaveCount(0)
    await screenshot(staff, testInfo, 'w1-admin-preflight-blocked-1440x900')

    await selectBatch(staff, fixture.ready.batchName)
    await lifecycle(staff, '发布', `/selection/batches/${fixture.ready.batchId}/publish`)
    await expectBatchStatus(staff, '已发布')
    await lifecycle(staff, '开选', `/selection/batches/${fixture.ready.batchId}/open`)
    await expectBatchStatus(staff, '选课中')
    await expectNoStalePreflight(staff)
    await screenshot(staff, testInfo, 'w1-admin-open-success-1440x900')

    await staff.reload()
    await dismissGuide(staff)
    await selectBatch(staff, fixture.ready.batchName)
    await expectBatchStatus(staff, '选课中')
    await expectNoStalePreflight(staff)
    await staffContext.close()

    const reloginContext = await browser.newContext({ viewport: { width: 1280, height: 720 } })
    const relogin = await reloginContext.newPage()
    await loginAcademicAdmin(relogin)
    await relogin.goto(`${config.staffBaseUrl}/admin/academic-affairs/selection`)
    await dismissGuide(relogin)
    await selectBatch(relogin, fixture.ready.batchName)
    await expectBatchStatus(relogin, '选课中')
    await expectNoStalePreflight(relogin)
    await screenshot(relogin, testInfo, 'w1-admin-relogin-persisted-1280x720')
    await reloginContext.close()

    const studentContext = await browser.newContext({ viewport: { width: 1440, height: 900 } })
    const student = await studentContext.newPage()
    const studentLogin = new StudentLoginPage(student, config.studentBaseUrl)
    await studentLogin.login(config.student)
    await student.goto(`${config.studentBaseUrl}/academic/selection`)
    const studentBatch = student.locator('.batch-card').filter({ hasText: fixture.ready.batchName }).first()
    await expect(studentBatch).toBeVisible({ timeout: 20_000 })
    const firstRow = studentBatch.locator('tr').filter({ hasText: fixture.courses[0].name }).first()
    await expect(firstRow).toBeVisible()
    const portalPreflight = student.waitForResponse((response) =>
      response.url().includes('/portal/academic/course-selection/preflight') && response.request().method() === 'POST'
    )
    const portalEnroll = student.waitForResponse((response) =>
      response.url().includes('/portal/academic/course-selection/enroll') && response.request().method() === 'POST'
    )
    await firstRow.getByRole('button', { name: '立即选课', exact: true }).click()
    expect((await portalPreflight).ok()).toBeTruthy()
    expect((await portalEnroll).ok()).toBeTruthy()
    await expect(firstRow).toContainText('本人已选', { timeout: 15_000 })
    await screenshot(student, testInfo, 'w1-student-pc-selected-1440x900')
    await student.reload()
    const studentBatchAfterRefresh = student.locator('.batch-card').filter({ hasText: fixture.ready.batchName }).first()
    await expect(studentBatchAfterRefresh).toBeVisible({ timeout: 20_000 })
    const firstAfterRefresh = studentBatchAfterRefresh.locator('tr').filter({ hasText: fixture.courses[0].name }).first()
    await expect(firstAfterRefresh).toContainText('本人已选', { timeout: 20_000 })
    await studentContext.close()

    const miniContext = await browser.newContext({ viewport: { width: 390, height: 844 } })
    const mini = await miniContext.newPage()
    await miniappLogin(mini)
    await mini.goto(`${MINIAPP_BASE}/#/pages/student/academic-affairs/selection`)
    const miniGroup = mini.locator('.sl__group').filter({ hasText: fixture.ready.batchName }).first()
    await expect(miniGroup).toBeVisible({ timeout: 20_000 })
    const secondCard = miniGroup.locator('.sl__course').filter({ hasText: fixture.courses[1].name }).first()
    await expect(secondCard).toBeVisible()
    const miniPreflight = mini.waitForResponse((response) =>
      response.url().includes('/api/v1/mobile/academic/selection/preflight') && response.request().method() === 'POST'
    )
    const miniEnroll = mini.waitForResponse((response) =>
      response.url().includes('/api/v1/mobile/academic/selection/enroll') && response.request().method() === 'POST'
    )
    await secondCard.locator('.sl__btn').filter({ hasText: '选课' }).first().click()
    expect((await miniPreflight).ok()).toBeTruthy()
    expect((await miniEnroll).ok()).toBeTruthy()
    await expect(secondCard).toContainText('已选', { timeout: 15_000 })
    await screenshot(mini, testInfo, 'w1-miniapp-selected-390x844')
    await mini.reload()
    const miniGroupAfterRefresh = mini.locator('.sl__group').filter({ hasText: fixture.ready.batchName }).first()
    await expect(miniGroupAfterRefresh).toBeVisible({ timeout: 20_000 })
    const secondAfterRefresh = miniGroupAfterRefresh.locator('.sl__course').filter({ hasText: fixture.courses[1].name }).first()
    await expect(secondAfterRefresh).toContainText('已选', { timeout: 20_000 })
    await miniContext.close()
  })
})