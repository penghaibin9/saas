import { execFileSync } from 'node:child_process'
import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { loadInternshipFixture } from '../lib/internship-fixture.mjs'
import { StaffLoginPage, StudentLoginPage } from '../pages/login.page.mjs'
import { StaffInternshipLeavePage, StudentInternshipPage } from '../pages/internship.page.mjs'

const PREFIX = 'E2E-XLSX-STATS-20260823'

function isoDay(offset) {
  const date = new Date()
  date.setUTCHours(0, 0, 0, 0)
  date.setUTCDate(date.getUTCDate() + offset)
  return date.toISOString().slice(0, 10)
}

function apiPath(response) {
  try { return new URL(response.url()).pathname } catch { return '' }
}

async function jsonBody(response, action) {
  const text = await response.text()
  let body = null
  try { body = JSON.parse(text) } catch { body = null }
  expect(response.ok(), `${action} HTTP ${response.status()}: ${text.slice(0, 800)}`).toBeTruthy()
  expect(body?.code, `${action} business error: ${text.slice(0, 800)}`).toBe(0)
  return body
}

test.describe('岗位实习审计：请假真实 XLSX 导出与统计一致性', () => {
  test.describe.configure({ mode: 'serial', retries: 0 })

  let fixture
  let rejectedLeaveId = ''
  let returnedLeaveId = ''
  let firstReason = ''
  let secondReason = ''
  let rejectReason = ''
  const returnNote = `${PREFIX}-销假完成`
  const startDate = isoDay(3)
  const endDate = isoDay(3)

  test.beforeAll(async () => {
    fixture = await loadInternshipFixture()
    firstReason = `${PREFIX}-${fixture.runId}-初次请假`
    secondReason = `${PREFIX}-${fixture.runId}-整改请假`
    rejectReason = `${PREFIX}-驳回原因-请补充返岗安排`
  })

  test('学生提交后导师真实驳回', async ({ page }) => {
    await new StudentLoginPage(page, config.studentBaseUrl).login(config.student)
    const student = new StudentInternshipPage(page, config.studentBaseUrl, fixture)
    await student.openLeave()
    rejectedLeaveId = await student.submitLeave({ startDate, endDate, reason: firstReason })

    const login = new StaffLoginPage(page, config.staffBaseUrl)
    await login.login(config.mentor)
    await login.switchRole(/实习指导教师|实习导师|INTERN_MENTOR/)
    await expect.poll(() => login.currentRoleText()).toMatch(/实习指导教师|实习导师|INTERN_MENTOR/)
    const staff = new StaffInternshipLeavePage(page, config.staffBaseUrl, fixture)
    await staff.openPending()
    await staff.selectLeave(rejectedLeaveId)

    const button = page.locator('.lv-foot').getByRole('button', { name: '驳回' })
    await button.click()
    const dialog = page.getByRole('dialog')
    await expect(dialog).toContainText('请假 · 驳回')
    await dialog.locator('textarea').fill(rejectReason)
    const responsePromise = page.waitForResponse((response) =>
      apiPath(response).endsWith(`/api/v1/internship/leaves/${rejectedLeaveId}/review`)
      && response.request().method() === 'POST'
    )
    await dialog.getByRole('button', { name: '驳回' }).click()
    const body = await jsonBody(await responsePromise, '导师驳回请假')
    expect(body.data.status).toBe('REJECTED')
  })

  test('学生刷新看到驳回原因并提交整改新单', async ({ page }) => {
    await new StudentLoginPage(page, config.studentBaseUrl).login(config.student)
    const student = new StudentInternshipPage(page, config.studentBaseUrl, fixture)
    await student.openLeave()
    await page.reload()
    await page.getByRole('button', { name: '实习请假' }).click()
    const rejected = student.leaveRow(firstReason)
    await expect(rejected).toContainText(`驳回原因：${rejectReason}`)
    returnedLeaveId = await student.submitLeave({ startDate, endDate, reason: secondReason })
    expect(returnedLeaveId).not.toBe(rejectedLeaveId)
  })

  test('导师通过整改单，学生刷新后真实销假', async ({ page }) => {
    const login = new StaffLoginPage(page, config.staffBaseUrl)
    await login.login(config.mentor)
    await login.switchRole(/实习指导教师|实习导师|INTERN_MENTOR/)
    await expect.poll(() => login.currentRoleText()).toMatch(/实习指导教师|实习导师|INTERN_MENTOR/)
    const staff = new StaffInternshipLeavePage(page, config.staffBaseUrl, fixture)
    await staff.approve({ leaveId: returnedLeaveId, reason: secondReason })

    await new StudentLoginPage(page, config.studentBaseUrl).login(config.student)
    const student = new StudentInternshipPage(page, config.studentBaseUrl, fixture)
    await student.openLeave()
    await page.reload()
    await expect(page.getByRole('button', { name: '实习请假' })).toBeVisible()
    await student.returnLeave({ leaveId: returnedLeaveId, reason: secondReason, note: returnNote })
  })

  test('管理员从真实页面导出 Excel，浏览器保存的 .xlsx 可被 openpyxl 打开并含驳回/销假记录', async ({ page }, testInfo) => {
    await new StaffLoginPage(page, config.staffBaseUrl).login(config.sandboxAdmin)
    const staff = new StaffInternshipLeavePage(page, config.staffBaseUrl, fixture)
    await page.goto(staff.url({ panel: 'all' }))
    await expect(page.getByText('请假审批').first()).toBeVisible()
    await staff.dismissGuideIfPresent()

    const responsePromise = page.waitForResponse((response) =>
      apiPath(response).endsWith('/api/v1/internship/leaves/export')
      && response.request().method() === 'POST'
    )
    const downloadPromise = page.waitForEvent('download')
    await page.getByRole('button', { name: /导出 Excel 台账/ }).click()
    const [response, download] = await Promise.all([responsePromise, downloadPromise])
    const body = await jsonBody(response, '管理员导出请假 Excel')
    expect(body.data.rowCount).toBeGreaterThanOrEqual(2)
    expect(download.suggestedFilename()).toMatch(/请假审批台账.*\.xlsx$/)

    const filePath = testInfo.outputPath('请假审批台账.xlsx')
    await download.saveAs(filePath)
    const output = execFileSync('python', ['../backend/scripts/e2e_verify_internship_leave_xlsx.py',
      filePath, String(body.data.rowCount), firstReason, secondReason, rejectReason, fixture.studentNo], {
      cwd: process.cwd(),
      encoding: 'utf8'
    })
    expect(output).toContain('XLSX_EVIDENCE_OK')
    console.log(output.trim())
  })

  test('管理员真实统计页的请假合规率与 MySQL 状态事实一致', async ({ page }) => {
    await new StaffLoginPage(page, config.staffBaseUrl).login(config.sandboxAdmin)
    const responsePromise = page.waitForResponse((response) =>
      apiPath(response).endsWith('/api/v1/internship/stats/overview')
      && response.request().method() === 'GET'
    )
    await page.goto(`${config.staffBaseUrl}/admin/internship/stats?batchId=${encodeURIComponent(fixture.batchId)}`)
    const body = await jsonBody(await responsePromise, '管理员读取岗位实习统计')
    const metric = (body.data?.metrics || []).find((item) => item.key === 'leaveComplyRate')
    expect(metric, '统计接口必须返回 leaveComplyRate').toBeTruthy()

    const card = page.locator('.app-metric-card').filter({ hasText: '请假合规率' }).first()
    await expect(card).toBeVisible()
    await expect(card.locator('.app-metric-card__trend')).toContainText(
      `${metric.numerator}/${metric.denominator}`
    )
    if (metric.rate == null) {
      await expect(card.locator('.app-metric-card__value')).toContainText('暂无数据')
    } else {
      await expect(card.locator('.app-metric-card__value')).toContainText(`${metric.rate}%`)
    }

    const output = execFileSync('python', ['../backend/scripts/e2e_verify_internship_leave_stats.py',
      String(fixture.batchId), String(metric.numerator), String(metric.denominator)], {
      cwd: process.cwd(),
      encoding: 'utf8',
      env: { ...process.env, E2E_INTERNSHIP_AUDIT_PREFIX: PREFIX }
    })
    expect(output).toContain('STATS_EVIDENCE_OK')
    console.log(output.trim())

    await page.reload()
    const refreshed = page.locator('.app-metric-card').filter({ hasText: '请假合规率' }).first()
    await expect(refreshed.locator('.app-metric-card__trend')).toContainText(
      `${metric.numerator}/${metric.denominator}`
    )
  })
})
