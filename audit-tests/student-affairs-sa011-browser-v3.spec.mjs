import fs from 'node:fs/promises'
import path from 'node:path'
import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { StaffLoginPage, StudentLoginPage } from '../pages/login.page.mjs'

const staff = {
  sa: { tenant: 'sandbox-school', username: 'e2e_sa_admin', password: 'E2eTest@2026' },
  counselorA: { tenant: 'sandbox-school', username: 'e2e_counselor_a', password: 'E2eTest@2026' },
  counselorB: { tenant: 'sandbox-school', username: 'e2e_counselor_b', password: 'E2eTest@2026' },
}
const student = { tenant: 'sandbox-school', username: 'E2E20260001', password: 'E2eTest@2026' }
const apiBase = (process.env.E2E_API_BASE_URL || 'http://127.0.0.1:8000/api/v1').replace(/\/+$/, '')
const miniBase = (process.env.E2E_MINIAPP_BASE_URL || 'http://127.0.0.1:5188').replace(/\/+$/, '')

async function staffLogin(page, account) {
  await page.context().clearCookies()
  const login = new StaffLoginPage(page, config.staffBaseUrl)
  await login.login(account)
  return login
}

async function loginTeacherMini(page, account) {
  await page.goto(`${miniBase}/#/pages/login/teacher/index`)
  const fields = page.getByRole('textbox')
  await fields.nth(0).fill(account.username)
  await fields.nth(1).fill(account.password)
  await page.getByText('填写', { exact: true }).click()
  await fields.nth(2).fill(account.tenant)
  await page.getByText('我已阅读并同意学校提供的', { exact: false }).click()
  await page.getByText('进入教师工作台', { exact: true }).click()
  await expect(page).toHaveURL(/pages\/teacher\/workbench\/index/, { timeout: 20_000 })
}

async function loginStudentMini(page, account) {
  await page.goto(`${miniBase}/#/pages/login/student/index`)
  const fields = page.getByRole('textbox')
  await fields.nth(0).fill(account.username)
  await fields.nth(1).fill(account.password)
  await page.getByText('填写', { exact: true }).click()
  await fields.nth(2).fill(account.tenant)
  await page.getByText('我已阅读并同意学校提供的', { exact: false }).click()
  await page.getByText('进入学生首页', { exact: true }).click()
  await expect(page).toHaveURL(/pages\/student\/home\/index/, { timeout: 20_000 })
}

async function json(response) {
  try { return await response.json() } catch { return {} }
}

async function api(page, token, method, pathname, data) {
  const response = await page.request.fetch(`${apiBase}${pathname}`, {
    method,
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    data,
  })
  return { response, body: await json(response) }
}

async function chooseRemote(page, placeholderText, searchPlaceholder, keyword, optionText) {
  const outerHints = [...new Set([
    placeholderText,
    searchPlaceholder,
    searchPlaceholder === '按学号 / 姓名搜索' ? '按姓名 / 学号搜索' : '',
  ].filter(Boolean))]
  let combo = null
  for (const hint of outerHints) {
    const candidate = page.getByRole('combobox').filter({ hasText: hint }).last()
    if (await candidate.count()) {
      combo = candidate
      break
    }
  }
  expect(combo, `picker ${placeholderText} must resolve to a combobox`).toBeTruthy()
  await expect(combo, `picker ${placeholderText}`).toBeVisible({ timeout: 20_000 })
  await combo.click()
  const picker = combo.locator('..')
  const search = picker.getByPlaceholder(searchPlaceholder).first()
  await expect(search, `search ${searchPlaceholder}`).toBeVisible({ timeout: 20_000 })
  await search.fill(keyword)
  const option = picker.getByRole('option').filter({ hasText: optionText }).first()
  await expect(option, `option ${optionText}`).toBeVisible({ timeout: 20_000 })
  await option.click()
}

async function confirmReason(page, buttonText, reason) {
  const textarea = page.locator('textarea:visible').last()
  await expect(textarea, `${buttonText} reason textarea`).toBeVisible({ timeout: 10_000 })
  await textarea.fill(reason)
  await page.getByRole('button', { name: buttonText, exact: true }).click()
}

async function openRisk(page, riskId) {
  await page.goto(`${config.staffBaseUrl}/admin/student-affairs/risk/${riskId}`)
  await expect(page.getByRole('heading', { name: '风险详情', exact: true })).toBeVisible({ timeout: 20_000 })
}

test.describe.serial('Student Affairs SA-011 A Gold Deep Browser First', () => {
  test.describe.configure({ retries: 0 })

  test('same risk across Staff PC + Teacher Mini + Student PC + Student Mini, then MySQL/privacy/scope seal', async ({ page, browser }) => {
    test.setTimeout(360_000)
    const unique = `${Date.now()}`
    const title = `SA011真实风险-${unique}`
    const detailText = `SA011内部处置证据-${unique}-仅工作人员可见`
    const evidence = {
      exactHead: process.env.E2E_TARGET_SHA || '',
      title,
      detailText,
      surface: 'STAFF_PC+STUDENT_PC+TEACHER_MINI_BROWSER+STUDENT_MINI_BROWSER',
    }

    // 1) Staff PC：学工管理员真实建单。
    const saLogin = await staffLogin(page, staff.sa)
    expect(saLogin.lastAccessToken).toBeTruthy()
    await page.goto(`${config.staffBaseUrl}/admin/student-affairs/risk`)
    await expect(page.getByRole('heading', { name: '风险预警', exact: true })).toBeVisible({ timeout: 20_000 })
    await page.getByRole('button', { name: '新建风险', exact: true }).click()
    await chooseRemote(page, '选择学生', '按学号 / 姓名搜索', 'E2E20260001', 'E2E学生A')
    await page.getByPlaceholder('一句话概括，如：连续两周未到课').fill(title)
    await page.locator('textarea:visible').last().fill(detailText)
    await page.getByRole('button', { name: '建单', exact: true }).click()

    const mainRow = page.locator('tbody tr').filter({ hasText: title }).first()
    await expect(mainRow, 'new risk must appear in real Staff PC list').toBeVisible({ timeout: 20_000 })
    await mainRow.getByRole('button', { name: '查看详情', exact: true }).click()
    await page.waitForURL(/\/admin\/student-affairs\/risk\/\d+$/)
    const riskId = page.url().match(/\/risk\/(\d+)$/)?.[1] || ''
    expect(riskId).toBeTruthy()
    evidence.riskId = riskId

    const mainDetail = await api(page, saLogin.lastAccessToken, 'GET', `/student-affairs/risk/records/${riskId}`)
    expect(mainDetail.response.ok(), JSON.stringify(mainDetail.body)).toBeTruthy()
    const studentId = String(mainDetail.body?.data?.studentId || '')
    expect(studentId).toBeTruthy()
    evidence.studentId = studentId

    // 2) API：同 source/ref 防重，不同 source 同 ref 独立。
    const sourceRefId = Number(`${Date.now()}`.slice(-9)) + 700000000
    const sourcePayload = {
      studentId,
      source: 'ACADEMIC_WARNING',
      sourceRefId: String(sourceRefId),
      riskLevel: 'MEDIUM',
      title: `SA011来源去重-${unique}`,
      detail: '学业预警来源的真实去重边界验证',
    }
    const sourceFirst = await api(page, saLogin.lastAccessToken, 'POST', '/student-affairs/risk/records', sourcePayload)
    expect(sourceFirst.response.status(), JSON.stringify(sourceFirst.body)).toBe(200)
    const sourceRiskId = String(sourceFirst.body?.data?.riskId || '')
    expect(sourceRiskId).toBeTruthy()
    const sourceDup = await api(page, saLogin.lastAccessToken, 'POST', '/student-affairs/risk/records', sourcePayload)
    expect(sourceDup.response.status(), JSON.stringify(sourceDup.body)).toBe(409)
    expect(sourceDup.body?.bizCode).toBe('DATA_CONFLICT')
    const crossSource = await api(page, saLogin.lastAccessToken, 'POST', '/student-affairs/risk/records', {
      ...sourcePayload,
      source: 'DORM',
      title: `SA011不同来源-${unique}`,
      detail: '同一来源编号但不同来源域必须独立建单',
    })
    expect(crossSource.response.status(), JSON.stringify(crossSource.body)).toBe(200)
    evidence.sourceRefId = sourceRefId
    evidence.sourceRiskId = sourceRiskId
    evidence.crossSourceRiskId = String(crossSource.body?.data?.riskId || '')
    evidence.duplicateSourceHttpStatus = sourceDup.response.status()

    // 3) Staff PC：真实分派 A 班辅导员。
    await openRisk(page, riskId)
    await page.getByRole('button', { name: '分派', exact: true }).click()
    await chooseRemote(page, '选择风险责任人', '按姓名 / 工号搜索', 'e2e_counselor_a', 'E2E辅导员A')
    await page.getByRole('button', { name: '确认分派', exact: true }).click()
    await expect(page.getByText('已分派', { exact: true }).first()).toBeVisible({ timeout: 15_000 })

    // 4) 权限负例：B 班辅导员读不到 A 班风险，页面也不得泄露标题/明细。
    const counselorBLogin = await staffLogin(page, staff.counselorB)
    const forbidden = await api(page, counselorBLogin.lastAccessToken, 'GET', `/student-affairs/risk/records/${riskId}`)
    expect(forbidden.response.status(), JSON.stringify(forbidden.body)).toBe(403)
    expect(forbidden.body?.bizCode).toBe('NO_DATA_SCOPE')
    evidence.crossScopeHttpStatus = forbidden.response.status()
    await openRisk(page, riskId)
    await expect(page.locator('body')).not.toContainText(detailText)
    await expect(page.locator('body')).not.toContainText(title)

    // 5) Teacher Mobile API + Teacher Mini Browser：同一 riskId 必须出现，并由教师小程序真实执行第一次处置。
    const counselorALogin = await staffLogin(page, staff.counselorA)
    const teacherPending = await api(page, counselorALogin.lastAccessToken, 'GET', '/mobile/teacher/affairs/risk/pending')
    expect(teacherPending.response.status(), JSON.stringify(teacherPending.body)).toBe(200)
    const teacherPendingItems = teacherPending.body?.data?.items || teacherPending.body?.data?.list || []
    const teacherPendingRisk = teacherPendingItems.find((item) => String(item?.riskId || item?.id || '') === riskId)
    expect(teacherPendingRisk, `teacher mobile pending must contain risk ${riskId}`).toBeTruthy()
    expect(teacherPendingRisk?.version, 'teacher mobile pending must expose visible optimistic-lock version').not.toBeUndefined()

    const teacherMobileDetail = await api(page, counselorALogin.lastAccessToken, 'GET', `/mobile/teacher/affairs/risk/${riskId}`)
    expect(teacherMobileDetail.response.status(), JSON.stringify(teacherMobileDetail.body)).toBe(200)
    const teacherMobileData = teacherMobileDetail.body?.data || {}
    expect(String(teacherMobileData.riskId || teacherMobileData.id || '')).toBe(riskId)
    expect(String(teacherMobileData.studentId || '')).toBe(studentId)
    expect(teacherMobileData.version, 'teacher mobile detail must expose current version').not.toBeUndefined()
    evidence.teacherMobileRisk = 'PASS'
    evidence.teacherMobileVersion = Number(teacherMobileData.version || teacherPendingRisk.version || 0)

    const teacherMiniContext = await browser.newContext({ viewport: { width: 390, height: 844 } })
    const teacherMiniPage = await teacherMiniContext.newPage()
    await loginTeacherMini(teacherMiniPage, staff.counselorA)
    await teacherMiniPage.goto(`${miniBase}/#/pages/teacher/affairs-review/index?type=RISK_HANDLE`)
    const miniRiskCard = teacherMiniPage.locator('.card').filter({ hasText: title }).first()
    await expect(miniRiskCard, `teacher mini must render risk ${riskId}`).toBeVisible({ timeout: 20_000 })
    await expect(miniRiskCard.getByText('填写处置', { exact: true })).toBeVisible()
    await expect(miniRiskCard.getByText('记录缺少版本号', { exact: true })).toHaveCount(0)

    const miniProcessResponse = teacherMiniPage.waitForResponse((response) => {
      const url = new URL(response.url())
      return response.request().method() === 'POST'
        && url.pathname.endsWith(`/api/v1/mobile/teacher/affairs/risk/${riskId}/process`)
    }, { timeout: 20_000 })
    await miniRiskCard.getByText('填写处置', { exact: true }).click()
    const modal = teacherMiniPage.locator('uni-modal').last()
    await expect(modal.getByText('处置内容', { exact: true })).toBeVisible({ timeout: 10_000 })
    await modal.locator('input').first().fill('教师小程序真实处置：已与学生本人完成首次面谈核实')
    await modal.getByText('确定', { exact: true }).click()
    const miniProcess = await miniProcessResponse
    const miniProcessPayload = await miniProcess.json()
    expect(miniProcessPayload.code, JSON.stringify(miniProcessPayload)).toBe(0)
    evidence.teacherMiniBrowser = 'PASS'
    evidence.teacherMiniProcess = 'PASS'
    await teacherMiniContext.close()

    // 6) Staff PC：回读教师小程序写入后的 PROCESSING，再继续跟进 + 升级。
    await openRisk(page, riskId)
    await expect(page.getByText('处置中', { exact: true }).first()).toBeVisible({ timeout: 15_000 })
    await page.getByRole('button', { name: '持续跟进', exact: true }).click()
    await confirmReason(page, '确认跟进', '第二次跟进确认到课及宿舍情况持续改善')
    await expect(page.getByText('持续跟进', { exact: true }).first()).toBeVisible({ timeout: 15_000 })
    await page.getByRole('button', { name: '升级', exact: true }).click()
    await confirmReason(page, '确认升级', '仍存在复发迹象需要上级联合处置')
    await expect(page.getByText('已升级', { exact: true }).first()).toBeVisible({ timeout: 15_000 })

    // 7) 学工处接管并关闭；复发后必须重开同一 riskId，再次处置关闭。
    await staffLogin(page, staff.sa)
    await openRisk(page, riskId)
    await page.getByRole('button', { name: '接管', exact: true }).click()
    await confirmReason(page, '确认接管', '学工处接管后组织联合复核并形成结论')
    await expect(page.getByText('处置中', { exact: true }).first()).toBeVisible({ timeout: 15_000 })
    await page.getByRole('button', { name: '关闭', exact: true }).click()
    await confirmReason(page, '确认关闭', '联合复核确认风险已解除可以关闭')
    await expect(page.getByText('已关闭', { exact: true }).first()).toBeVisible({ timeout: 15_000 })
    await page.getByRole('button', { name: '重开', exact: true }).click()
    await confirmReason(page, '确认重开', '学生情况复发，按原风险记录重新启动处置')
    await expect(page.getByText('已重开', { exact: true }).first()).toBeVisible({ timeout: 15_000 })
    await page.getByRole('button', { name: '分派', exact: true }).click()
    await chooseRemote(page, '选择风险责任人', '按姓名 / 工号搜索', 'e2e_counselor_a', 'E2E辅导员A')
    await page.getByRole('button', { name: '确认分派', exact: true }).click()

    await staffLogin(page, staff.counselorA)
    await openRisk(page, riskId)
    await page.getByRole('button', { name: '处置', exact: true }).click()
    await confirmReason(page, '确认处置', '复发后已再次面谈并落实新的跟进措施')
    await page.getByRole('button', { name: '关闭', exact: true }).click()
    await confirmReason(page, '确认关闭', '复发处置完成，学生状态恢复稳定')
    await expect(page.getByText('已关闭', { exact: true }).first()).toBeVisible({ timeout: 15_000 })

    // 8) Student PC + Student Mobile API：内部风险标题/处置明细完全不可见。
    const studentPage = await page.context().newPage()
    const studentLogin = new StudentLoginPage(studentPage, config.studentBaseUrl)
    await studentLogin.login(student)
    await expect(studentPage.locator('body')).not.toContainText(title)
    await expect(studentPage.locator('body')).not.toContainText(detailText)
    const overview = await api(studentPage, studentLogin.lastAccessToken, 'GET', '/mobile/affairs/overview')
    expect(overview.response.status(), JSON.stringify(overview.body)).toBe(200)
    const overviewData = overview.body?.data || {}
    expect(JSON.stringify(overviewData)).not.toContain(title)
    expect(JSON.stringify(overviewData)).not.toContain(detailText)
    expect(Object.keys(overviewData)).not.toContain('riskOpen')
    expect(Object.keys(overviewData)).not.toContain('riskDetail')
    expect(Number(overviewData.careActionCount || 0)).toBeGreaterThanOrEqual(0)
    evidence.studentMobilePrivacy = 'PASS'
    evidence.studentPrivacy = 'PASS'
    await studentPage.close()

    // 9) Student Mini Browser：真实登录首页和消息页都不能暴露内部风险标题/处置明细。
    const studentMiniContext = await browser.newContext({ viewport: { width: 390, height: 844 } })
    const studentMiniPage = await studentMiniContext.newPage()
    await loginStudentMini(studentMiniPage, student)
    await expect(studentMiniPage.locator('body')).not.toContainText(title)
    await expect(studentMiniPage.locator('body')).not.toContainText(detailText)
    await studentMiniPage.goto(`${miniBase}/#/pages/student/messages/index`)
    await expect(studentMiniPage.locator('body')).not.toContainText(title)
    await expect(studentMiniPage.locator('body')).not.toContainText(detailText)
    evidence.studentMiniBrowserPrivacy = 'PASS'
    await studentMiniContext.close()

    // 10) Staff PC：最终真实详情保留完整 handle 时间线。
    await staffLogin(page, staff.sa)
    await openRisk(page, riskId)
    const timeline = page.locator('.sa-audit')
    await expect(timeline).toContainText('ASSIGN')
    await expect(timeline).toContainText('PROCESS')
    await expect(timeline).toContainText('FOLLOW')
    await expect(timeline).toContainText('ESCALATE')
    await expect(timeline).toContainText('TAKEOVER')
    await expect(timeline).toContainText('CLOSE')
    await expect(timeline).toContainText('REOPEN')

    evidence.result = 'REAL_PASS'
    evidence.completedAt = new Date().toISOString()
    await fs.writeFile(path.resolve('student-affairs-sa011-evidence.json'), JSON.stringify(evidence, null, 2), 'utf8')
  })
})