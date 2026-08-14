import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { StaffLoginPage } from '../pages/login.page.mjs'

const D2_E2E_CLASS_NAME = 'E2E机器人2401班'

async function dismissPageGuide(page) {
  const mask = page.locator('.app-step-guide__mask')
  await mask.waitFor({ state: 'visible', timeout: 1500 }).catch(() => {})
  if (await mask.isVisible().catch(() => false)) {
    await page.getByRole('button', { name: '跳过引导' }).click()
    await expect(mask).toBeHidden()
  }
}

async function browserApi(page, token, method, path, body) {
  return page.evaluate(async ({ apiBaseUrl, tokenValue, requestMethod, requestPath, requestBody }) => {
    const response = await fetch(`${apiBaseUrl}${requestPath}`, {
      method: requestMethod,
      headers: {
        Accept: 'application/json',
        Authorization: `Bearer ${tokenValue}`,
        ...(requestBody === undefined ? {} : { 'Content-Type': 'application/json' })
      },
      body: requestBody === undefined ? undefined : JSON.stringify(requestBody)
    })
    const text = await response.text()
    let json = null
    try { json = JSON.parse(text) } catch { json = { message: text.slice(0, 500) } }
    return { status: response.status, json }
  }, {
    apiBaseUrl: config.apiBaseUrl,
    tokenValue: token,
    requestMethod: method,
    requestPath: path,
    requestBody: body
  })
}

async function expectApiOk(result, label) {
  expect(result.status, `${label}: ${JSON.stringify(result.json)}`).toBe(200)
  expect(result.json?.code, `${label}: ${JSON.stringify(result.json)}`).toBe(0)
  return result.json.data
}

async function captureViewport(page, testInfo, name, width, height) {
  await page.setViewportSize({ width, height })
  await page.waitForLoadState('networkidle', { timeout: 5000 }).catch(() => {})
  await page.evaluate(async () => {
    if (document.fonts?.ready) await document.fonts.ready
  })
  const path = testInfo.outputPath(`${name}-${width}x${height}.png`)
  await page.screenshot({ path, fullPage: false, animations: 'disabled', caret: 'hide' })
  await testInfo.attach(`${name}-${width}x${height}`, { path, contentType: 'image/png' })
}

async function loginAcademicAdmin(page) {
  const login = new StaffLoginPage(page, config.staffBaseUrl)
  await login.login(config.multiRole)
  await login.switchRole(/教务处管理员|教务管理员|教务老师|ACADEMIC_ADMIN/)
  return { login, token: await login.token() }
}

async function seedAuthoritativeRegistrationCandidates(page, token, testInfo) {
  // D2 E2E must own its registration precondition instead of relying on the incidental
  // student_status of graduation/internship accounts. Create the two students through the
  // production roster import API, which itself defaults them to PENDING_REGISTER and writes
  // the canonical student master. The administrative class is created by the isolated CI
  // identity bootstrap before Playwright starts; no direct DB fixture or production bypass.
  const suffix = `${String(Date.now()).slice(-6)}${testInfo.retry}`
  const rows = [
    {
      studentNo: `D2E2E${suffix}01`,
      realName: `D2注册甲${suffix}`,
      gender: '男',
      className: D2_E2E_CLASS_NAME,
      initialStatus: 'PENDING_REGISTER'
    },
    {
      studentNo: `D2E2E${suffix}02`,
      realName: `D2注册乙${suffix}`,
      gender: '女',
      className: D2_E2E_CLASS_NAME,
      initialStatus: 'PENDING_REGISTER'
    }
  ]

  await expectApiOk(await browserApi(
    page,
    token,
    'POST',
    '/academic-affairs/roster/import/dry-run',
    { rows }
  ), 'pre-validate D2 registration candidates')

  const imported = await expectApiOk(await browserApi(
    page,
    token,
    'POST',
    '/academic-affairs/roster/import/confirm',
    { rows }
  ), 'import D2 registration candidates')
  expect(Number(imported?.created || 0), `D2 roster import: ${JSON.stringify(imported)}`).toBeGreaterThanOrEqual(2)
  return new Set(rows.map((row) => row.studentNo))
}

async function createBatchWithCandidates(page, token, testInfo) {
  const seededStudentNos = await seedAuthoritativeRegistrationCandidates(page, token, testInfo)
  const suffix = `${String(Date.now()).slice(-6)}-r${testInfo.retry}`
  const batch = await expectApiOk(await browserApi(page, token, 'POST', '/academic-affairs/registration-batches', {
    batchName: `E2E批量注册-ENROLL-${suffix}`,
    registerType: 'ENROLL',
    open: true
  }), 'create ENROLL registration batch')
  const candidates = await expectApiOk(await browserApi(
    page,
    token,
    'GET',
    `/academic-affairs/registration-batches/${batch.batchId}/registration-candidates?page=1&pageSize=200`
  ), 'read ENROLL candidates')
  const ready = (candidates.items || []).filter(
    (item) => seededStudentNos.has(item.studentNo) && item.eligibilityStatus !== 'INELIGIBLE'
  )
  expect(
    ready.length,
    `D2 authoritative candidate seed must yield exactly two readable candidates: ${JSON.stringify(candidates)}`
  ).toBe(2)
  return { batch, candidates: ready }
}

test.describe.serial('Academic affairs D2 roster/registration usability', () => {
  test('human-readable candidates → bulk preview → canonical registration, with 3 viewport screenshots', async ({ page }, testInfo) => {
    const { token } = await loginAcademicAdmin(page)
    const { batch, candidates } = await createBatchWithCandidates(page, token, testInfo)
    const [first, second] = candidates

    await page.setViewportSize({ width: 1440, height: 900 })
    await page.goto(`${config.staffBaseUrl}/admin/academic-affairs/registration/${batch.batchId}`)
    await expect(page).toHaveURL(new RegExp(`/admin/academic-affairs/registration/${batch.batchId}`))
    await dismissPageGuide(page)

    await expect(page.getByText('批量注册', { exact: true })).toBeVisible()
    await expect(page.getByText(first.realName, { exact: true })).toBeVisible()
    await expect(page.getByText(first.studentNo, { exact: true })).toBeVisible()
    if (first.className) await expect(page.getByText(first.className, { exact: true }).first()).toBeVisible()
    if (first.majorName) await expect(page.getByText(first.majorName, { exact: true }).first()).toBeVisible()
    await expect(page.getByText(first.currentStatusLabel, { exact: true }).first()).toBeVisible()
    await expect(page.getByText(first.eligibilityExplanation, { exact: true }).first()).toBeVisible()
    await expect(page.getByText('班级ID', { exact: true })).toHaveCount(0)

    await page.getByRole('checkbox', { name: `选择 ${first.realName || first.studentNo}` }).check()
    await page.getByRole('checkbox', { name: `选择 ${second.realName || second.studentNo}` }).check()
    await page.getByRole('button', { name: '预览批量注册' }).click()

    const preview = page.getByTestId('bulk-registration-preview')
    await expect(preview).toBeVisible()
    await expect(preview).toContainText('2 人可执行')
    await expect(preview).toContainText('0 人被阻断')
    await expect(preview).toContainText(first.realName)
    await expect(preview).toContainText(second.realName)

    await captureViewport(page, testInfo, 'd2-registration-bulk-preview', 1280, 720)
    await captureViewport(page, testInfo, 'd2-registration-bulk-preview', 1440, 900)
    await captureViewport(page, testInfo, 'd2-registration-bulk-preview', 1920, 1080)

    await page.getByLabel(/我已核对本次名单和阻断原因/).check()
    const confirm = page.getByRole('button', { name: '确认注册 2 人' })
    await expect(confirm).toBeEnabled()
    await confirm.click()

    const result = page.getByTestId('bulk-registration-result')
    await expect(result).toBeVisible({ timeout: 10000 })
    await expect(result).toContainText('成功 2 人')
    await expect(result).toContainText('未成功 0 人')

    const registrations = await expectApiOk(await browserApi(
      page,
      token,
      'GET',
      `/academic-affairs/registration-batches/${batch.batchId}/registrations?page=1&pageSize=50`
    ), 'read registrations after bulk canonical apply')
    const studentIds = new Set((registrations.items || []).map((item) => String(item.studentId)))
    expect(studentIds.has(String(first.studentId))).toBeTruthy()
    expect(studentIds.has(String(second.studentId))).toBeTruthy()
  })
})