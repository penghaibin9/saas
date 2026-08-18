import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { StaffLoginPage, StudentLoginPage } from '../pages/login.page.mjs'

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

function listFrom(data) {
  return data?.list || data?.items || []
}

async function seedStudentAbnormalGraduationAudit(page, testInfo) {
  const login = new StaffLoginPage(page, config.staffBaseUrl)
  await login.login(config.multiRole)
  await login.switchRole(/教务处管理员|教务管理员|教务老师|ACADEMIC_ADMIN/)
  const token = await login.token()
  expect(token, 'academic admin access token must remain available for D-W5 seed').toBeTruthy()

  const suffix = `${String(Date.now()).slice(-7)}-r${testInfo.retry}`
  const batch = await expectApiOk(await browserApi(page, token, 'POST', '/academic-affairs/graduation-audit-batches', {
    batchName: `D-W5学生毕业资格-${suffix}`,
    gradeYear: '2024'
  }), 'create D-W5 graduation audit batch')

  await expectApiOk(await browserApi(
    page,
    token,
    'POST',
    `/academic-affairs/graduation-audit-batches/${batch.batchId}/generate`,
    {}
  ), 'generate D-W5 graduation candidates')

  const precheck = await expectApiOk(await browserApi(
    page,
    token,
    'POST',
    `/academic-affairs/graduation-audit-batches/${batch.batchId}/precheck`
  ), 'run D-W5 immutable graduation precheck')
  expect(Number(precheck.abnormal || 0), JSON.stringify(precheck)).toBeGreaterThan(0)

  const results = await expectApiOk(await browserApi(
    page,
    token,
    'GET',
    `/academic-affairs/graduation-audit-batches/${batch.batchId}/results?page=1&pageSize=200`
  ), 'read D-W5 graduation results')
  const studentResult = listFrom(results).find((row) =>
    String(row.studentNo || '') === config.student.username
      || String(row.realName || '') === 'E2E学生A'
  )
  expect(studentResult, `missing ${config.student.username} in ${JSON.stringify(results)}`).toBeTruthy()
  expect(studentResult.overall, JSON.stringify(studentResult)).toBe('SYSTEM_ABNORMAL')
  expect(studentResult.status, JSON.stringify(studentResult)).toBe('SYSTEM_ABNORMAL')
  return { batchId: String(batch.batchId), resultId: String(studentResult.resultId) }
}

async function openStudentGraduationAudit(page) {
  const responsePromise = page.waitForResponse((response) =>
    response.url().includes('/api/v1/portal/academic/graduation-audit')
      && response.request().method() === 'GET'
  )
  await page.goto(`${config.studentBaseUrl}/academic/graduation`)
  const response = await responsePromise
  expect(response.ok(), `student graduation audit HTTP ${response.status()}`).toBeTruthy()
  return response
}

async function assertAbnormalStudentSurface(page) {
  await expect(page.getByRole('heading', { name: '毕业条件还有待处理事项' })).toBeVisible({ timeout: 15_000 })
  await expect(page.getByText('正式预审存在阻断项', { exact: true })).toBeVisible()
  await expect(page.getByText('逐项核对真实业务事实', { exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: '重新核验' })).toBeVisible()
  await expect(page.getByRole('heading', { name: '当前毕业条件已通过实时核验' })).toHaveCount(0)
  await expect(page.locator('.graduation-hero')).not.toHaveClass(/is-passed/)
  await expect(page.locator('body')).not.toContainText('毕业自查暂时无法加载')
}

async function capture(page, testInfo, name, width, height) {
  await page.setViewportSize({ width, height })
  await page.waitForLoadState('networkidle', { timeout: 5000 }).catch(() => {})
  await page.evaluate(async () => { if (document.fonts?.ready) await document.fonts.ready })
  const path = testInfo.outputPath(`${name}-${width}x${height}.png`)
  await page.screenshot({ path, fullPage: false, animations: 'disabled', caret: 'hide' })
  await testInfo.attach(`${name}-${width}x${height}`, { path, contentType: 'image/png' })
}

test.describe.serial('Academic D W5 · student graduation qualification exact truth', () => {
  test('SYSTEM_ABNORMAL stays non-green across refresh and a new student browser session', async ({ page }, testInfo) => {
    const seeded = await seedStudentAbnormalGraduationAudit(page, testInfo)
    expect(seeded.batchId).toMatch(/^\d+$/)
    expect(seeded.resultId).toMatch(/^\d+$/)

    const studentLogin = new StudentLoginPage(page, config.studentBaseUrl)
    await studentLogin.login(config.student)
    await openStudentGraduationAudit(page)
    await assertAbnormalStudentSurface(page)
    await capture(page, testInfo, 'academic-d-w5-student-graduation-abnormal', 1280, 720)
    await capture(page, testInfo, 'academic-d-w5-student-graduation-abnormal', 1440, 900)

    const refreshButton = page.getByRole('button', { name: '重新核验' })
    await refreshButton.click()
    // Manual recheck is a UI truth contract, not a transport-observation contract. The
    // initial navigation already proves this surface reads the canonical endpoint; here
    // wait for the refresh lifecycle to settle and then assert SYSTEM_ABNORMAL never greens.
    await expect(refreshButton).toBeEnabled({ timeout: 20_000 })
    await assertAbnormalStudentSurface(page)

    await page.reload()
    await assertAbnormalStudentSurface(page)

    await page.evaluate(() => {
      localStorage.clear()
      sessionStorage.clear()
    })
    await page.context().clearCookies()
    await new StudentLoginPage(page, config.studentBaseUrl).login(config.student)
    await openStudentGraduationAudit(page)
    await assertAbnormalStudentSurface(page)
    await capture(page, testInfo, 'academic-d-w5-student-graduation-relogin', 1280, 720)
  })
})
