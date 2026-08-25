import fs from 'node:fs/promises'
import { execFileSync } from 'node:child_process'

import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { StaffLoginPage, StudentLoginPage } from '../pages/login.page.mjs'
import { StaffInternshipLeavePage, StudentInternshipPage } from '../pages/internship.page.mjs'
import {
  StaffInternshipApplicationPage,
  StudentInternshipApplicationPage,
} from '../pages/internship-application.page.mjs'

const miniBase = String(process.env.E2E_MINIAPP_BASE_URL || '').replace(/\/+$/, '')
const enterpriseBase = String(process.env.E2E_ENTERPRISE_BASE_URL || '').replace(/\/+$/, '')
const runtimeOrigin = new URL(config.staffBaseUrl).origin
const APPLICATION_STUDENT = {
  tenant: 'sandbox-school', username: 'E2E20260002', password: 'E2eTest@2026'
}

let fixture
let applicationFixture
let s1

function isoDay(offset) {
  const date = new Date()
  date.setUTCHours(0, 0, 0, 0)
  date.setUTCDate(date.getUTCDate() + offset)
  return date.toISOString().slice(0, 10)
}

function assertHttpsRuntime(page) {
  const url = new URL(page.url())
  expect(url.protocol).toBe('https:')
  expect(url.origin).toBe(runtimeOrigin)
}

async function loginMini(page, { role, account }) {
  const entry = role === 'teacher' ? 'teacher' : 'student'
  await page.goto(`${miniBase}/#/pages/login/${entry}/index`)
  assertHttpsRuntime(page)
  const fields = page.getByRole('textbox')
  await fields.nth(0).fill(account.username)
  await fields.nth(1).fill(account.password)
  await page.getByText('填写', { exact: true }).click()
  await fields.nth(2).fill(account.tenant)
  await page.getByText('我已阅读并同意学校提供的', { exact: false }).click()
  await page.getByText(role === 'teacher' ? '进入教师工作台' : '进入学生首页', { exact: true }).click()
  await expect(page).toHaveURL(role === 'teacher'
    ? /pages\/teacher\/workbench\/index/
    : /pages\/student\/home\/index/, { timeout: 30_000 })
  assertHttpsRuntime(page)
}

async function loginEnterprise(page) {
  await page.goto(`${enterpriseBase}/login`)
  assertHttpsRuntime(page)
  await page.getByLabel(/学校编码/).fill(s1.enterprise.tenantCode)
  await page.getByLabel(/登录账号/).fill(s1.enterprise.loginName)
  await page.getByLabel(/密码/).fill(s1.enterprise.password)
  const responsePromise = page.waitForResponse((response) =>
    new URL(response.url()).pathname.includes('/api/v1/internship/enterprise-portal/auth/')
      && response.request().method() === 'POST'
  )
  await page.getByRole('button', { name: /登录/ }).click()
  const response = await responsePromise
  expect(response.ok(), `enterprise login HTTP ${response.status()}`).toBeTruthy()
  await expect(page).toHaveURL(/\/enterprise\/(?:campaign-select|home)/, { timeout: 30_000 })
  if (page.url().includes('/campaign-select')) {
    await page.getByRole('button', { name: new RegExp(s1.enterprise.campaignName) }).click()
    await expect(page).toHaveURL(/\/enterprise\/home/, { timeout: 30_000 })
  }
  assertHttpsRuntime(page)
}

test.describe.serial('S1 · production build + nginx TLS + 2-worker backend representative smoke', () => {
  test.beforeAll(async () => {
    fixture = JSON.parse(await fs.readFile('./runtime/internship-fixture.json', 'utf8'))
    applicationFixture = JSON.parse(await fs.readFile('./runtime/internship-application-fixture.json', 'utf8'))
    s1 = JSON.parse(await fs.readFile('./runtime/internship-s1-production-runtime.json', 'utf8'))
    expect(s1.productExactSha).toBe(process.env.E2E_PRODUCT_EXACT_SHA)
    expect(miniBase).toContain('/miniapp')
    expect(enterpriseBase).toContain('/enterprise')
  })

  test.beforeEach(async ({ page }) => {
    page.__s1NetworkViolations = []
    page.on('request', (request) => {
      const url = new URL(request.url())
      if (url.pathname.startsWith('/api/')) {
        if (url.protocol !== 'https:' || url.origin !== runtimeOrigin) {
          page.__s1NetworkViolations.push(`${request.method()} ${request.url()}`)
        }
      }
      if (['5173', '5199', '5188', '5202', '8000'].includes(url.port)) {
        page.__s1NetworkViolations.push(`dev-port ${request.method()} ${request.url()}`)
      }
    })
  })

  test.afterEach(async ({ page }) => {
    expect(page.__s1NetworkViolations || [], 'production browser traffic escaped nginx TLS/runtime origin').toEqual([])
  })

  test('S1-01 Staff PC production build：真实登录', async ({ page }) => {
    await new StaffLoginPage(page, config.staffBaseUrl).login(config.sandboxAdmin)
    assertHttpsRuntime(page)
    await expect(page).not.toHaveURL(/\/login(?:\?|$)/)
  })

  test('S1-02 Student PC production build：真实登录', async ({ page }) => {
    await new StudentLoginPage(page, config.studentBaseUrl).login(config.student)
    assertHttpsRuntime(page)
    await expect(page).not.toHaveURL(/\/portal\/login(?:\?|$)/)
  })

  test('S1-03 BASE_PATH / route refresh：Student PC 深路由硬刷新仍可用', async ({ page }) => {
    await new StudentLoginPage(page, config.studentBaseUrl).login(config.student)
    await page.goto(`${config.studentBaseUrl}/internship`)
    await expect(page.getByRole('button', { name: '我的实习' })).toBeVisible()
    await expect(page.getByText(fixture.companyName, { exact: false }).first()).toBeVisible()
    assertHttpsRuntime(page)
    await page.reload()
    await expect(page.getByRole('button', { name: '我的实习' })).toBeVisible()
    await expect(page.getByText(fixture.positionName, { exact: false }).first()).toBeVisible()
    assertHttpsRuntime(page)
  })

  test('S1-04 application upload/download：真实 PDF 经 nginx/API 上传并由 Staff 下载', async ({ page }) => {
    await new StudentLoginPage(page, config.studentBaseUrl).login(APPLICATION_STUDENT)
    const student = new StudentInternshipApplicationPage(page, config.studentBaseUrl, applicationFixture)
    await student.open()
    const submitted = await student.submitSelfArranged({
      companyName: `S1生产运行企业-${applicationFixture.runId}`,
      positionName: `S1生产运行测试岗-${applicationFixture.runId}`,
      workAddress: '湖南省长沙市岳麓区 S1 生产运行测试地址',
      contactName: 'S1联系人',
      contactPhone: '13800138002',
      note: `S1 production runtime upload ${applicationFixture.runId}`,
      fileName: `s1-production-runtime-${applicationFixture.runId}.pdf`,
    })
    expect(submitted.appId).not.toBe('')
    expect(submitted.fileId).not.toBe('')

    const login = new StaffLoginPage(page, config.staffBaseUrl)
    await login.login(config.mentor)
    await login.switchRole(/实习指导教师|实习导师|INTERN_MENTOR/)
    await expect.poll(() => login.currentRoleText()).toMatch(/实习指导教师|实习导师|INTERN_MENTOR/)
    const staff = new StaffInternshipApplicationPage(page, config.staffBaseUrl, applicationFixture)
    const detail = await staff.openApplication(submitted.appId)
    expect(String(detail.evidenceFileId || '')).toBe(submitted.fileId)
    await staff.downloadEvidence(submitted.fileId)
    assertHttpsRuntime(page)
  })

  test('S1-05 leave xlsx：真实请假后从 Staff production page 下载可解析台账', async ({ page }, testInfo) => {
    const reason = `S1 production xlsx ${Date.now()}`
    await new StudentLoginPage(page, config.studentBaseUrl).login(config.student)
    const student = new StudentInternshipPage(page, config.studentBaseUrl, fixture)
    await student.openLeave()
    const leaveId = await student.submitLeave({
      startDate: isoDay(2), endDate: isoDay(2), reason,
    })
    expect(leaveId).not.toBe('')

    await new StaffLoginPage(page, config.staffBaseUrl).login(config.sandboxAdmin)
    const staff = new StaffInternshipLeavePage(page, config.staffBaseUrl, fixture)
    await page.goto(staff.url({ panel: 'all' }))
    await expect(page.getByText('请假审批').first()).toBeVisible()
    await staff.dismissGuideIfPresent()
    const responsePromise = page.waitForResponse((response) =>
      new URL(response.url()).pathname.endsWith('/api/v1/internship/leaves/export')
        && response.request().method() === 'POST'
    )
    const downloadPromise = page.waitForEvent('download')
    await page.getByRole('button', { name: /导出 Excel 台账/ }).click()
    const [response, download] = await Promise.all([responsePromise, downloadPromise])
    expect(response.ok(), `leave export HTTP ${response.status()}`).toBeTruthy()
    expect(download.suggestedFilename()).toMatch(/\.xlsx$/)
    const outputPath = testInfo.outputPath('s1-leave-ledger.xlsx')
    await download.saveAs(outputPath)
    const verified = execFileSync('python', ['-c', [
      'import sys, openpyxl',
      'p, needle = sys.argv[1], sys.argv[2]',
      'wb = openpyxl.load_workbook(p, read_only=True, data_only=True)',
      'values = [str(v) for ws in wb.worksheets for row in ws.iter_rows(values_only=True) for v in row if v is not None]',
      'assert any(needle in v for v in values), f"missing leave reason: {needle}"',
      'print("S1_XLSX_OK")',
    ].join('; '), outputPath, reason], { encoding: 'utf8' })
    expect(verified).toContain('S1_XLSX_OK')
    assertHttpsRuntime(page)
  })

  test('S1-06 message deep link：真实 Student PC 消息详情重验后跳业务页面', async ({ page }) => {
    await new StudentLoginPage(page, config.studentBaseUrl).login(config.student)
    await page.goto(`${config.studentBaseUrl}/messages`)
    await page.getByText('通知', { exact: true }).first().click()
    const row = page.locator('.mrow').filter({ hasText: s1.messageTitle }).first()
    await expect(row).toBeVisible()
    await row.click()
    await expect(page).toHaveURL(/\/portal\/campus-service\?.*tab=leave/, { timeout: 30_000 })
    assertHttpsRuntime(page)
  })

  test('S1-07 batch detail：Staff PC 真实读取实习批次详情', async ({ page }) => {
    await new StaffLoginPage(page, config.staffBaseUrl).login(config.sandboxAdmin)
    await page.goto(`${config.staffBaseUrl}/admin/internship/batches/${fixture.batchId}`)
    await expect(page.getByRole('heading', { name: new RegExp(fixture.batchName) })).toBeVisible()
    await expect(page.getByText(fixture.batchName, { exact: false }).first()).toBeVisible()
    assertHttpsRuntime(page)
  })

  test('S1-08 Teacher Mini H5 production build：真实教师认证', async ({ page }) => {
    await loginMini(page, { role: 'teacher', account: config.mentor })
    await expect(page.getByText(/工作台|待办|我的学生/).first()).toBeVisible()
  })

  test('S1-09 Student Mini H5 production build：真实学生认证', async ({ page }) => {
    await loginMini(page, { role: 'student', account: config.student })
    await expect(page.getByText(/首页|服务|消息|实习/).first()).toBeVisible()
  })

  test('S1-10 Enterprise Portal production build：真实企业账号登录', async ({ page }) => {
    await loginEnterprise(page)
    await expect(page.getByRole('heading', { name: /企业首页/ })).toBeVisible()
  })
})
