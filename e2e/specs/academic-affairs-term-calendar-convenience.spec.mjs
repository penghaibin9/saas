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

async function chooseTerm(page, termName) {
  const picker = page.locator('.aa-filter .app-remote-select').first()
  await picker.locator('.app-remote-select__control').click()
  const option = picker.locator('.app-remote-select__option').filter({ hasText: termName }).first()
  await expect(option, `missing term option ${termName}`).toBeVisible()
  await option.click()
  await expect(picker.locator('.app-remote-select__single')).toContainText(termName)
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

test.describe.serial('Academic affairs D1 term/calendar usability', () => {
  test('calendar copy preview → human review → canonical write, with 3 viewport screenshots', async ({ page }, testInfo) => {
    const { token } = await loginAcademicAdmin(page)
    const suffix = String(Date.now()).slice(-6)
    const sourceName = `E2E 源校历 ${suffix}`
    const targetName = `E2E 目标校历 ${suffix}`
    const holidayRemark = `E2E 假期 ${suffix}`
    const examRemark = `E2E 考试 ${suffix}`

    const source = await expectApiOk(await browserApi(page, token, 'POST', '/academic-affairs/terms', {
      yearCode: '2088-2089',
      termNo: 1,
      termName: sourceName,
      startDate: '2088-09-01',
      endDate: '2089-01-31',
      teachingWeeks: 20,
      examWeekStart: 18
    }), 'create source term')
    const target = await expectApiOk(await browserApi(page, token, 'POST', '/academic-affairs/terms', {
      yearCode: '2089-2090',
      termNo: 1,
      termName: targetName,
      startDate: '2089-09-03',
      endDate: '2090-01-31',
      teachingWeeks: 20,
      examWeekStart: 19
    }), 'create target term')

    await expectApiOk(await browserApi(page, token, 'POST', `/academic-affairs/terms/${source.termId}/calendar`, {
      eventType: 'HOLIDAY',
      startDate: '2088-09-15',
      endDate: '2088-09-15',
      remark: holidayRemark
    }), 'seed source holiday')
    await expectApiOk(await browserApi(page, token, 'POST', `/academic-affairs/terms/${source.termId}/calendar`, {
      eventType: 'EXAM',
      startDate: '2088-12-29',
      endDate: '2088-12-30',
      remark: examRemark
    }), 'seed source exam')

    await page.setViewportSize({ width: 1440, height: 900 })
    await page.goto(`${config.staffBaseUrl}/admin/academic-affairs/calendar`)
    await expect(page).toHaveURL(/\/admin\/academic-affairs\/calendar/)
    await dismissPageGuide(page)
    await chooseTerm(page, targetName)

    const copyPanel = page.getByText('快速复制上一学期校历', { exact: true }).locator('..').locator('..')
    await expect(page.getByText('快速复制上一学期校历', { exact: true })).toBeVisible()
    await page.locator('.aa-copy-field select').selectOption({ label: sourceName })
    await page.getByRole('button', { name: '预览复制结果' }).click()

    await expect(page.getByText(holidayRemark)).toBeVisible()
    await expect(page.getByText(examRemark)).toBeVisible()
    await expect(page.getByText('需人工复核', { exact: false }).first()).toBeVisible()
    await expect(page.getByText('TEACHING_WEEK_RELATIVE_WITH_EXAM_WEEK_ALIGNMENT')).toHaveCount(0)
    await expect(page.getByText('2089-09-17', { exact: false })).toBeVisible()
    await copyPanel.scrollIntoViewIfNeeded().catch(() => {})

    await captureViewport(page, testInfo, 'd1-calendar-copy-preview', 1280, 720)
    await captureViewport(page, testInfo, 'd1-calendar-copy-preview', 1440, 900)
    await captureViewport(page, testInfo, 'd1-calendar-copy-preview', 1920, 1080)

    await page.getByLabel(/我已逐项核对节假日/).check()
    const confirm = page.getByRole('button', { name: /确认复制 2 项/ })
    await expect(confirm).toBeEnabled()
    await confirm.click()

    await expect(page.getByText(holidayRemark)).toBeVisible()
    await expect(page.getByText(examRemark)).toBeVisible()

    const targetEvents = await expectApiOk(
      await browserApi(page, token, 'GET', `/academic-affairs/terms/${target.termId}/calendar`),
      'read target calendar after canonical apply'
    )
    const remarks = (targetEvents.items || []).map((item) => item.remark)
    expect(remarks).toContain(holidayRemark)
    expect(remarks).toContain(examRemark)
  })

  test('standard 8/10 time-slot templates expose conflict preview without replacing manual CRUD', async ({ page }, testInfo) => {
    await loginAcademicAdmin(page)
    await page.setViewportSize({ width: 1440, height: 900 })
    await page.goto(`${config.staffBaseUrl}/admin/academic-affairs/time-slots`)
    await expect(page).toHaveURL(/\/admin\/academic-affairs\/time-slots/)
    await dismissPageGuide(page)

    await expect(page.getByText('标准作息模板', { exact: true })).toBeVisible()
    await expect(page.getByText('新增节次', { exact: true })).toBeVisible()
    await page.getByRole('button', { name: '标准 10 节' }).click()
    await page.getByRole('button', { name: '检查当前作息' }).click()

    await expect(page.getByText('第 10 节', { exact: true })).toBeVisible()
    await expect(page.getByText(/可新增|已存在|冲突/).first()).toBeVisible()
    await expect(page.getByText(/模板只负责给出候选/)).toBeVisible()

    await captureViewport(page, testInfo, 'd1-time-slot-template-preview', 1440, 900)
  })
})
