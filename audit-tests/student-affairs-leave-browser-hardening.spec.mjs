import fs from 'node:fs/promises'
import path from 'node:path'
import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { StudentLoginPage, StaffLoginPage } from '../pages/login.page.mjs'

const counselorA = {
  tenant: 'sandbox-school',
  username: 'e2e_counselor_a',
  password: 'E2eTest@2026'
}

const counselorB = {
  tenant: 'sandbox-school',
  username: 'e2e_counselor_b',
  password: 'E2eTest@2026'
}

function day(offset) {
  const d = new Date()
  d.setHours(12, 0, 0, 0)
  d.setDate(d.getDate() + offset)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

async function freshStudentLogin(page) {
  await page.context().clearCookies()
  const login = new StudentLoginPage(page, config.studentBaseUrl)
  await login.login(config.student)
  return login
}

async function freshStaffLogin(page, account) {
  await page.context().clearCookies()
  const login = new StaffLoginPage(page, config.staffBaseUrl)
  await login.login(account)
  return login
}

async function jsonBody(response) {
  try { return await response.json() } catch { return {} }
}

function apiUrl(suffix) {
  return `${config.apiBaseUrl}${suffix}`
}

test.describe.serial('Student Affairs strict browser audit · leave production hardening', () => {
  test.describe.configure({ retries: 0 })

  test('wrong counselor denied -> CLOSED replay denied -> real async XLSX export/download', async ({ page }) => {
    test.setTimeout(210_000)

    const mainEvidence = JSON.parse(await fs.readFile(path.resolve('student-affairs-audit-evidence.json'), 'utf8'))
    const mainLeaveId = String(mainEvidence.leaveId)
    const prefix = `${mainEvidence.prefix}-HARDEN`
    const scopeReason = `${prefix}-SCOPE 同租户错误辅导员越权验收；完成后由主责辅导员正常驳回收口。`
    const scopeRejectReason = `${prefix}-SCOPE-REJECT 主责辅导员完成越权验收后的正常驳回收口。`
    const terminalReplayComment = `${prefix}-TERMINAL-REPLAY CLOSED 状态禁止重复审批。`
    const startDate = day(30)
    const endDate = day(31)

    const api500 = []
    const consoleErrors = []
    let mainVersionBefore = null
    let mainVersionAfter = null
    let scopeLeaveId = ''
    let scopeVersion = null
    let wrongCounselorDetailStatus = null
    let wrongCounselorApproveStatus = null
    let terminalReplayStatus = null
    let exportJobId = ''
    let exportRowCount = null
    let xlsxPath = ''

    page.on('response', (response) => {
      if (response.url().includes('/api/') && response.status() >= 500) {
        api500.push(`${response.status()} ${response.request().method()} ${response.url()}`)
      }
    })
    page.on('console', (message) => {
      if (message.type() !== 'error') return
      const text = message.text()
      if (/favicon|source map|Vue Devtools/i.test(text)) return
      consoleErrors.push(text)
    })

    await test.step('terminal CLOSED record is absent from queue and repeated approval fails closed', async () => {
      const login = await freshStaffLogin(page, counselorA)
      expect(login.lastAccessToken).toBeTruthy()
      await page.goto(`${config.staffBaseUrl}/admin/student-affairs/leave`)
      const search = page.getByPlaceholder('按学生姓名 / 学号搜索')
      await search.fill(config.student.username)
      await search.press('Enter')
      await expect(page.locator('.lv-item').filter({ hasText: mainEvidence.revisedReason })).toHaveCount(0)

      const headers = { Authorization: `Bearer ${login.lastAccessToken}` }
      const before = await page.request.get(apiUrl(`/student-affairs/leave/${mainLeaveId}`), { headers })
      expect(before.ok(), `closed detail HTTP ${before.status()}`).toBeTruthy()
      const beforeEnv = await jsonBody(before)
      expect(beforeEnv.code).toBe(0)
      expect(beforeEnv.data?.affairsStatus).toBe('CLOSED')
      mainVersionBefore = Number(beforeEnv.data?.version)
      expect(Number.isFinite(mainVersionBefore)).toBeTruthy()

      const replay = await page.request.post(apiUrl(`/student-affairs/leave/${mainLeaveId}/approve`), {
        headers,
        data: { comment: terminalReplayComment, version: mainVersionBefore }
      })
      terminalReplayStatus = replay.status()
      expect(replay.ok(), `terminal replay must fail closed, got HTTP ${replay.status()}`).toBeFalsy()
      expect([400, 403, 409]).toContain(replay.status())
      const replayEnv = await jsonBody(replay)
      expect(replayEnv.code).not.toBe(0)

      const after = await page.request.get(apiUrl(`/student-affairs/leave/${mainLeaveId}`), { headers })
      expect(after.ok()).toBeTruthy()
      const afterEnv = await jsonBody(after)
      expect(afterEnv.code).toBe(0)
      expect(afterEnv.data?.affairsStatus).toBe('CLOSED')
      mainVersionAfter = Number(afterEnv.data?.version)
      expect(mainVersionAfter).toBe(mainVersionBefore)
    })

    await test.step('student creates a new real leave for same-tenant wrong-counselor attack', async () => {
      await freshStudentLogin(page)
      await page.goto(`${config.studentBaseUrl}/campus-service?tab=leave`)
      const form = page.locator('section.sp-card').filter({ hasText: '请假申请' }).first()
      await expect(form).toBeVisible()
      await form.getByLabel('开始日期').fill(startDate)
      await form.getByLabel('结束日期').fill(endDate)
      await form.locator('textarea').fill(scopeReason)

      const submitPromise = page.waitForResponse((response) => {
        try {
          const url = new URL(response.url())
          return url.pathname.endsWith('/api/v1/portal/affairs/leave') && response.request().method() === 'POST'
        } catch { return false }
      })
      await form.getByRole('button', { name: '提交请假', exact: true }).click()
      const submitted = await submitPromise
      expect(submitted.ok(), `scope leave submit HTTP ${submitted.status()}`).toBeTruthy()
      const env = await jsonBody(submitted)
      expect(env.code).toBe(0)
      scopeLeaveId = String(env.data?.leaveId || env.data?.id || '')
      scopeVersion = Number(env.data?.version || 1)
      expect(scopeLeaveId).toBeTruthy()

      await page.reload()
      const record = page.locator('article.record').filter({ hasText: startDate }).filter({ hasText: endDate }).first()
      await expect(record).toBeVisible()
      await expect(record).toContainText(scopeReason)
    })

    await test.step('same-tenant counselor B cannot see detail or approve class A leave', async () => {
      const login = await freshStaffLogin(page, counselorB)
      expect(login.lastAccessToken).toBeTruthy()
      await page.goto(`${config.staffBaseUrl}/admin/student-affairs/leave`)
      const search = page.getByPlaceholder('按学生姓名 / 学号搜索')
      await search.fill(config.student.username)
      await search.press('Enter')
      await expect(page.locator('.lv-item').filter({ hasText: config.student.username })).toHaveCount(0)

      const headers = { Authorization: `Bearer ${login.lastAccessToken}` }
      const detail = await page.request.get(apiUrl(`/student-affairs/leave/${scopeLeaveId}`), { headers })
      wrongCounselorDetailStatus = detail.status()
      expect(detail.ok(), `wrong counselor detail must fail closed, got HTTP ${detail.status()}`).toBeFalsy()
      expect([403, 404]).toContain(detail.status())

      const approve = await page.request.post(apiUrl(`/student-affairs/leave/${scopeLeaveId}/approve`), {
        headers,
        data: { comment: `${prefix}-B-ATTACK`, version: scopeVersion }
      })
      wrongCounselorApproveStatus = approve.status()
      expect(approve.ok(), `wrong counselor approve must fail closed, got HTTP ${approve.status()}`).toBeFalsy()
      expect([400, 403, 404, 409]).toContain(approve.status())
      const approveEnv = await jsonBody(approve)
      expect(approveEnv.code).not.toBe(0)
    })

    await test.step('assigned counselor A sees the same record and rejects it through real browser UI', async () => {
      await freshStaffLogin(page, counselorA)
      await page.goto(`${config.staffBaseUrl}/admin/student-affairs/leave`)
      const search = page.getByPlaceholder('按学生姓名 / 学号搜索')
      await search.fill(config.student.username)
      await search.press('Enter')
      const item = page.locator('.lv-item').filter({ hasText: config.student.username }).first()
      await expect(item).toBeVisible()
      await item.click()
      await expect(page.locator('.lv-main')).toContainText(scopeReason)

      const rejectPromise = page.waitForResponse((response) =>
        response.url().endsWith(`/api/v1/student-affairs/leave/${scopeLeaveId}/reject`) && response.request().method() === 'POST'
      )
      await page.locator('.lv-main').getByRole('button', { name: '驳回', exact: true }).click()
      const dialog = page.getByRole('dialog')
      await expect(dialog).toBeVisible()
      await dialog.locator('textarea').fill(scopeRejectReason)
      await dialog.getByRole('button', { name: '驳回', exact: true }).click()
      const rejected = await rejectPromise
      expect(rejected.ok(), `assigned counselor reject HTTP ${rejected.status()}`).toBeTruthy()
      const rejectEnv = await jsonBody(rejected)
      expect(rejectEnv.code).toBe(0)

      await freshStudentLogin(page)
      await page.goto(`${config.studentBaseUrl}/campus-service?tab=leave`)
      const record = page.locator('article.record').filter({ hasText: startDate }).filter({ hasText: endDate }).first()
      await expect(record).toBeVisible()
      await expect(record).toContainText('已驳回')
    })

    await test.step('assigned counselor creates filtered async export and downloads real XLSX in browser', async () => {
      const login = await freshStaffLogin(page, counselorA)
      await page.goto(`${config.staffBaseUrl}/admin/student-affairs/leave/ledger`)
      await expect(page.getByText('请假台账', { exact: true }).first()).toBeVisible()
      const search = page.getByPlaceholder('学生姓名 / 学号')
      await search.fill(config.student.username)
      await search.press('Enter')
      await expect(page.getByText(mainEvidence.revisedReason, { exact: true }).first()).toBeVisible()
      await expect(page.getByText(scopeReason, { exact: true }).first()).toBeVisible()

      const createPromise = page.waitForResponse((response) => {
        try {
          const url = new URL(response.url())
          return url.pathname.endsWith('/api/v1/student-affairs/leave/export') && response.request().method() === 'POST'
        } catch { return false }
      })
      await page.getByRole('button', { name: '导出 Excel 台账', exact: true }).click()
      const created = await createPromise
      expect(created.ok(), `export create HTTP ${created.status()}`).toBeTruthy()
      const createdEnv = await jsonBody(created)
      expect(createdEnv.code).toBe(0)
      exportJobId = String(createdEnv.data?.jobId || createdEnv.data?.id || '')
      expect(exportJobId).toBeTruthy()

      const downloadButton = page.getByRole('button', { name: '下载 Excel', exact: true })
      await expect(downloadButton).toBeVisible({ timeout: 120_000 })

      const job = await page.request.get(apiUrl(`/student-affairs/leave/export-jobs/${exportJobId}`), {
        headers: { Authorization: `Bearer ${login.lastAccessToken}` }
      })
      expect(job.ok(), `export job HTTP ${job.status()}`).toBeTruthy()
      const jobEnv = await jsonBody(job)
      expect(jobEnv.code).toBe(0)
      expect(jobEnv.data?.status).toBe('SUCCEEDED')
      exportRowCount = Number(jobEnv.data?.rowCount || 0)
      expect(exportRowCount).toBeGreaterThanOrEqual(2)

      const downloadPromise = page.waitForEvent('download')
      await downloadButton.click()
      const download = await downloadPromise
      expect(await download.failure()).toBeNull()
      expect(download.suggestedFilename().toLowerCase()).toMatch(/\.xlsx$/)
      xlsxPath = path.resolve('student-affairs-leave-ledger.xlsx')
      await download.saveAs(xlsxPath)
      const stat = await fs.stat(xlsxPath)
      expect(stat.size).toBeGreaterThan(1000)
    })

    expect(api500, 'no unhandled API 5xx during hardening journey').toEqual([])
    expect(consoleErrors, 'no browser console errors during hardening journey').toEqual([])

    await fs.writeFile(path.resolve('student-affairs-leave-hardening-evidence.json'), JSON.stringify({
      exactHead: process.env.E2E_TARGET_SHA || '',
      prefix,
      mainLeaveId,
      mainVersionBefore,
      mainVersionAfter,
      terminalReplayStatus,
      scopeLeaveId,
      scopeVersion,
      scopeReason,
      scopeRejectReason,
      wrongCounselorDetailStatus,
      wrongCounselorApproveStatus,
      exportJobId,
      exportRowCount,
      xlsxPath: path.basename(xlsxPath),
      sameTenantWrongCounselor: 'PASS',
      terminalReplay: 'PASS',
      realXlsxDownload: 'PASS'
    }, null, 2), 'utf8')
  })
})
