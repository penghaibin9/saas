import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { StaffLoginPage } from '../pages/login.page.mjs'

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

async function loginAcademicAdmin(page) {
  const login = new StaffLoginPage(page, config.staffBaseUrl)
  await login.login(config.multiRole)
  await login.switchRole(/教务处管理员|教务管理员|教务老师|ACADEMIC_ADMIN/)
  return { login, token: await login.token() }
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

async function selectTermByLabel(page, label) {
  const picker = page.locator('.app-remote-select').first()
  await picker.locator('.app-remote-select__control').click()
  const input = picker.getByPlaceholder('按学年 / 学期名称搜索')
  await input.fill(label)
  const option = picker.getByRole('option').filter({ hasText: label }).first()
  await expect(option).toBeVisible({ timeout: 10000 })
  await option.click()
  await expect(picker.locator('.app-remote-select__single')).toContainText(label)
}

function listFrom(data) {
  return data?.list || data?.items || []
}

test.describe.serial('Academic D W0/W1 Graduation + Archive production closure', () => {
  test('W0 real SYSTEM_ABNORMAL cannot expose or execute ordinary graduation final', async ({ page }, testInfo) => {
    const { token } = await loginAcademicAdmin(page)
    const suffix = `${String(Date.now()).slice(-7)}-r${testInfo.retry}`

    const batch = await expectApiOk(await browserApi(page, token, 'POST', '/academic-affairs/graduation-audit-batches', {
      batchName: `D-W0浏览器异常终审-${suffix}`,
      gradeYear: '2024'
    }), 'create D-W0 graduation batch')

    await expectApiOk(await browserApi(
      page,
      token,
      'POST',
      `/academic-affairs/graduation-audit-batches/${batch.batchId}/generate`,
      {}
    ), 'generate D-W0 graduation candidates')

    const precheck = await expectApiOk(await browserApi(
      page,
      token,
      'POST',
      `/academic-affairs/graduation-audit-batches/${batch.batchId}/precheck`
    ), 'run D-W0 immutable graduation precheck')
    expect(Number(precheck.abnormal || 0), JSON.stringify(precheck)).toBeGreaterThan(0)

    const results = await expectApiOk(await browserApi(
      page,
      token,
      'GET',
      `/academic-affairs/graduation-audit-batches/${batch.batchId}/results?overall=SYSTEM_ABNORMAL&page=1&pageSize=200`
    ), 'read D-W0 abnormal results')
    const abnormal = listFrom(results).find((row) => row.overall === 'SYSTEM_ABNORMAL')
    expect(abnormal, JSON.stringify(results)).toBeTruthy()

    await expectApiOk(await browserApi(
      page,
      token,
      'POST',
      `/academic-affairs/graduation-results/${abnormal.resultId}/college-review`,
      { action: 'APPROVE', note: 'D-W0真实浏览器异常终审阻断验证' }
    ), 'move abnormal result to academic review')

    const forbiddenFinal = await browserApi(
      page,
      token,
      'POST',
      `/academic-affairs/graduation-results/${abnormal.resultId}/final`,
      { conclusion: 'GRADUATED', confirm: true }
    )
    expect(forbiddenFinal.status, JSON.stringify(forbiddenFinal.json)).toBe(409)
    expect(String(forbiddenFinal.json?.message || '')).toMatch(/SYSTEM_ABNORMAL|阻断|重新预审/)

    await page.setViewportSize({ width: 1440, height: 900 })
    await page.goto(`${config.staffBaseUrl}/admin/academic-affairs/graduation/audit-console?tab=final&batchId=${batch.batchId}`)
    await dismissPageGuide(page)
    await expect(page.getByText('毕业资格终审', { exact: true }).first()).toBeVisible()
    await expect(page.getByText('系统异常 · 先治理阻断项', { exact: true }).first()).toBeVisible({ timeout: 10000 })
    await expect(page.getByRole('button', { name: '教务终审' })).toHaveCount(0)

    await captureViewport(page, testInfo, 'academic-d-w0-abnormal-final-blocked', 1280, 720)
    await captureViewport(page, testInfo, 'academic-d-w0-abnormal-final-blocked', 1440, 900)
    await captureViewport(page, testInfo, 'academic-d-w0-abnormal-final-blocked', 1920, 1080)

    await page.getByRole('button', { name: '查看阻断证据' }).first().click()
    await expect(page.getByText(/普通教务终审不可用审核备注覆盖评估结论/)).toBeVisible()
    await expect(page.getByRole('button', { name: '确认终审并写学籍' })).toHaveCount(0)
  })

  test('W1 real Term API drives UNKNOWN and NOT_APPLICABLE UI without boolean false-green', async ({ page }, testInfo) => {
    const { token } = await loginAcademicAdmin(page)
    const suffix = `${String(Date.now()).slice(-7)}r${testInfo.retry}`
    const unknownName = `D-W1待治理学期-${suffix}`
    const notApplicableName = `D-W1不适用学期-${suffix}`

    const unknownTerm = await expectApiOk(await browserApi(page, token, 'POST', '/academic-affairs/terms', {
      yearCode: `U${suffix}`,
      termNo: 1,
      termName: unknownName
    }), 'create W1 missing-date term')
    const notApplicableTerm = await expectApiOk(await browserApi(page, token, 'POST', '/academic-affairs/terms', {
      yearCode: `N${suffix}`,
      termNo: 2,
      termName: notApplicableName,
      startDate: '2098-02-01',
      endDate: '2098-07-31'
    }), 'create W1 no-business term')

    const unknownPrecheck = await expectApiOk(await browserApi(
      page,
      token,
      'GET',
      `/academic-affairs/archive/precheck?termId=${unknownTerm.termId}`
    ), 'precheck W1 missing-date term')
    const unknownGraduation = (unknownPrecheck.domains || []).find((row) => row.domain === 'GRADUATION')
    expect(unknownGraduation?.result, JSON.stringify(unknownPrecheck)).toBe('UNKNOWN')
    expect(Number(unknownGraduation?.blockingCount || 0)).toBeGreaterThan(0)
    expect(unknownPrecheck.result).not.toBe('PASS')

    const naPrecheck = await expectApiOk(await browserApi(
      page,
      token,
      'GET',
      `/academic-affairs/archive/precheck?termId=${notApplicableTerm.termId}`
    ), 'precheck W1 not-applicable term')
    const naGraduation = (naPrecheck.domains || []).find((row) => row.domain === 'GRADUATION')
    expect(naGraduation?.result, JSON.stringify(naPrecheck)).toBe('NOT_APPLICABLE')
    expect(Number(naGraduation?.blockingCount || 0)).toBe(0)

    const archiveBatch = await expectApiOk(await browserApi(page, token, 'POST', '/academic-affairs/archive/batches', {
      termId: unknownTerm.termId,
      batchName: `D-W1待治理正式归档-${suffix}`
    }), 'create W1 archive batch')
    const checked = await expectApiOk(await browserApi(
      page,
      token,
      'POST',
      `/academic-affairs/archive/batches/${archiveBatch.batchId}/check`
    ), 'run W1 formal archive check')
    expect(checked.status).toBe('MISSING_ITEMS')
    expect(Number(checked.missingCount || 0)).toBeGreaterThan(0)
    const forbiddenArchive = await browserApi(
      page,
      token,
      'POST',
      `/academic-affairs/archive/batches/${archiveBatch.batchId}/confirm`,
      { force: false }
    )
    expect(forbiddenArchive.status, JSON.stringify(forbiddenArchive.json)).toBe(409)

    await page.setViewportSize({ width: 1440, height: 900 })
    await page.goto(`${config.staffBaseUrl}/admin/academic-affairs/archive/precheck`)
    await dismissPageGuide(page)

    await selectTermByLabel(page, unknownName)
    const unknownCard = page.locator('.aapc-card').filter({ hasText: '毕业资格' }).first()
    await expect(unknownCard).toContainText('待治理')
    await expect(unknownCard).toContainText('GRADUATION_TERM_DATES_UNKNOWN')
    await expect(page.getByText(/UNKNOWN 不会被当成 PASS/)).toBeVisible()

    await captureViewport(page, testInfo, 'academic-d-w1-archive-unknown', 1280, 720)
    await captureViewport(page, testInfo, 'academic-d-w1-archive-unknown', 1440, 900)
    await captureViewport(page, testInfo, 'academic-d-w1-archive-unknown', 1920, 1080)

    await unknownCard.getByRole('button', { name: '去处理' }).click()
    await expect(page).toHaveURL(/\/admin\/academic-affairs\/graduation\/audit-console(?:\?|$)/)

    await page.goto(`${config.staffBaseUrl}/admin/academic-affairs/archive/precheck`)
    await dismissPageGuide(page)
    await selectTermByLabel(page, notApplicableName)
    const naCard = page.locator('.aapc-card').filter({ hasText: '毕业资格' }).first()
    await expect(naCard).toContainText('不适用')
    await expect(naCard).toContainText('GRADUATION_NOT_APPLICABLE')
    await expect(naCard).not.toContainText('待治理')

    await captureViewport(page, testInfo, 'academic-d-w1-archive-not-applicable', 1280, 720)
    await captureViewport(page, testInfo, 'academic-d-w1-archive-not-applicable', 1440, 900)
    await captureViewport(page, testInfo, 'academic-d-w1-archive-not-applicable', 1920, 1080)
  })
})
