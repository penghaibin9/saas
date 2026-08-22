import fs from 'node:fs/promises'
import path from 'node:path'
import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { StudentLoginPage, StaffLoginPage } from '../pages/login.page.mjs'

const counselor = {
  tenant: 'sandbox-school',
  username: 'e2e_counselor_a',
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

function exactPath(response, suffix, method = 'POST') {
  try {
    const url = new URL(response.url())
    return url.pathname.endsWith(suffix) && response.request().method() === method
  } catch {
    return false
  }
}

async function readClosedMetric(page) {
  const responsePromise = page.waitForResponse((response) => {
    try {
      const url = new URL(response.url())
      return url.pathname.endsWith('/api/v1/student-affairs/leave/stats') && response.request().method() === 'GET'
    } catch {
      return false
    }
  })
  await page.goto(`${config.staffBaseUrl}/admin/student-affairs/leave/stats`)
  const response = await responsePromise
  expect(response.ok(), `leave stats HTTP ${response.status()}`).toBeTruthy()
  const envelope = await response.json()
  expect(envelope.code).toBe(0)
  const closed = (envelope.data?.metrics || []).find((item) => item.key === 'closed')
  expect(closed, 'leave stats must expose closed metric').toBeTruthy()
  await expect(page.getByText('已销假', { exact: true }).first()).toBeVisible()
  return Number(closed.value || 0)
}

test.describe.serial('Student Affairs strict browser audit · leave lifecycle', () => {
  test('student create -> counselor return -> student edit/resubmit -> counselor approve -> student cancel -> counselor confirm -> stats -> tenant isolation', async ({ page }, testInfo) => {
    test.setTimeout(180_000)

    const runMark = `${Date.now()}-${process.pid}`
    const prefix = `E2E-AUDIT-20260823-${runMark}`
    const initialReason = `${prefix}-LEAVE 首次请假：处理家庭事项并按时返校。`
    const returnedReason = `${prefix}-RETURN 请补充具体行程和返校安排后重新提交。`
    const revisedReason = `${prefix}-RESUBMIT 已补充返校安排与紧急联系人说明。`
    const startDate = day(20)
    const endDate = day(21)
    const api500 = []
    const consoleErrors = []
    let initialSubmitCount = 0
    let leaveId = ''
    let closedBefore = 0
    let closedAfter = 0

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
    page.on('request', (request) => {
      try {
        const url = new URL(request.url())
        if (url.pathname.endsWith('/api/v1/portal/affairs/leave') && request.method() === 'POST') {
          initialSubmitCount += 1
        }
      } catch {}
    })

    await test.step('capture counselor scoped statistics baseline in real browser', async () => {
      const staffLogin = await freshStaffLogin(page, counselor)
      expect(staffLogin.lastAccessToken).toBeTruthy()
      closedBefore = await readClosedMetric(page)
    })

    await test.step('student browser login and real leave submission', async () => {
      const studentLogin = await freshStudentLogin(page)
      expect(studentLogin.lastAccessToken).toBeTruthy()
      await page.goto(`${config.studentBaseUrl}/campus-service?tab=leave`)
      await expect(page.getByText('请假申请', { exact: true })).toBeVisible()

      const form = page.locator('section.sp-card').filter({ hasText: '请假申请' }).first()
      await form.getByLabel('开始日期').fill(startDate)
      await form.getByLabel('结束日期').fill(endDate)
      await form.locator('textarea').fill(initialReason)

      const responsePromise = page.waitForResponse((response) =>
        exactPath(response, '/api/v1/portal/affairs/leave', 'POST')
      )
      await form.getByRole('button', { name: '提交请假' }).dblclick()
      const response = await responsePromise
      expect(response.ok(), `student leave submit HTTP ${response.status()}`).toBeTruthy()
      const envelope = await response.json()
      expect(envelope.code).toBe(0)
      const data = envelope.data || {}
      leaveId = String(data.leaveId || data.id || '')
      expect(leaveId, 'leave id must come from the browser submit network response').toBeTruthy()
      testInfo.annotations.push({ type: 'leave-id', description: leaveId })
      await page.waitForTimeout(400)
      expect(initialSubmitCount, 'rapid double-click must create only one POST').toBe(1)

      await page.reload()
      const record = page.locator('article.record').filter({ hasText: startDate }).filter({ hasText: endDate }).first()
      await expect(record).toBeVisible()
      await expect(record).toContainText(/辅导员审批|审批中|已提交/)
    })

    await test.step('counselor browser login, scoped queue, return for resubmit and audit trail', async () => {
      const staffLogin = await freshStaffLogin(page, counselor)
      expect(staffLogin.lastAccessToken).toBeTruthy()
      await page.goto(`${config.staffBaseUrl}/admin/student-affairs/leave`)
      await expect(page.getByText('请假初审', { exact: true })).toBeVisible()

      const search = page.getByPlaceholder('按学生姓名 / 学号搜索')
      await search.fill(config.student.username)
      await search.press('Enter')
      const queueItem = page.locator('.lv-item').filter({ hasText: config.student.username }).first()
      await expect(queueItem).toBeVisible()
      await queueItem.click()
      await expect(page.locator('.lv-main')).toContainText(initialReason)

      const returnResponsePromise = page.waitForResponse((response) =>
        response.url().includes('/api/v1/student-affairs/leave/') && response.url().endsWith('/return') && response.request().method() === 'POST'
      )
      await page.getByRole('button', { name: '退回重提' }).click()
      const dialog = page.getByRole('dialog')
      await expect(dialog).toBeVisible()
      await dialog.locator('textarea').fill(returnedReason)
      await dialog.getByRole('button', { name: '退回', exact: true }).click()
      const returned = await returnResponsePromise
      expect(returned.ok(), `return HTTP ${returned.status()}`).toBeTruthy()
      const returnedEnv = await returned.json()
      expect(returnedEnv.code).toBe(0)
    })

    await test.step('student browser sees reason, edits and resubmits', async () => {
      await freshStudentLogin(page)
      await page.goto(`${config.studentBaseUrl}/campus-service?tab=leave`)
      const record = page.locator('article.record').filter({ hasText: startDate }).filter({ hasText: endDate }).first()
      await expect(record).toBeVisible()
      await expect(record).toContainText(returnedReason)
      await record.getByRole('button', { name: '修改后重提' }).click()

      const modal = page.locator('.mask .modal')
      await expect(modal).toBeVisible()
      await modal.locator('textarea').fill(revisedReason)
      const resubmitPromise = page.waitForResponse((response) =>
        response.url().endsWith(`/api/v1/portal/affairs/leave/${leaveId}/resubmit`) && response.request().method() === 'POST'
      )
      await modal.getByRole('button', { name: '保存并提交' }).click()
      const resubmitted = await resubmitPromise
      expect(resubmitted.ok(), `resubmit HTTP ${resubmitted.status()}`).toBeTruthy()
      const resubmitEnv = await resubmitted.json()
      expect(resubmitEnv.code).toBe(0)
      await expect(modal).toBeHidden()

      await page.reload()
      const refreshed = page.locator('article.record').filter({ hasText: startDate }).filter({ hasText: endDate }).first()
      await expect(refreshed).toBeVisible()
      await expect(refreshed).not.toContainText(returnedReason)
    })

    await test.step('counselor browser approves one-day leave to final approved state', async () => {
      await freshStaffLogin(page, counselor)
      await page.goto(`${config.staffBaseUrl}/admin/student-affairs/leave`)
      const search = page.getByPlaceholder('按学生姓名 / 学号搜索')
      await search.fill(config.student.username)
      await search.press('Enter')
      const queueItem = page.locator('.lv-item').filter({ hasText: config.student.username }).first()
      await expect(queueItem).toBeVisible()
      await queueItem.click()
      await expect(page.locator('.lv-main')).toContainText(revisedReason)

      const approvePromise = page.waitForResponse((response) =>
        response.url().endsWith(`/api/v1/student-affairs/leave/${leaveId}/approve`) && response.request().method() === 'POST'
      )
      await page.getByRole('button', { name: '通过', exact: true }).click()
      const dialog = page.getByRole('dialog')
      await dialog.getByRole('button', { name: '通过', exact: true }).click()
      const approved = await approvePromise
      expect(approved.ok(), `approve HTTP ${approved.status()}`).toBeTruthy()
      const approvedEnv = await approved.json()
      expect(approvedEnv.code).toBe(0)
    })

    await test.step('student browser refresh sees approval and submits real cancel-leave request', async () => {
      await freshStudentLogin(page)
      await page.goto(`${config.studentBaseUrl}/campus-service?tab=leave`)
      const record = page.locator('article.record').filter({ hasText: startDate }).filter({ hasText: endDate }).first()
      await expect(record).toBeVisible()
      await expect(record).toContainText('已通过')

      const cancelPromise = page.waitForResponse((response) =>
        response.url().endsWith(`/api/v1/portal/affairs/leave/${leaveId}/cancel`) && response.request().method() === 'POST'
      )
      page.once('dialog', (dialog) => dialog.accept())
      await record.getByRole('button', { name: '申请销假' }).click()
      const cancel = await cancelPromise
      expect(cancel.ok(), `cancel request HTTP ${cancel.status()}`).toBeTruthy()
      const cancelEnv = await cancel.json()
      expect(cancelEnv.code).toBe(0)
    })

    await test.step('counselor browser confirms cancel and sees audit trail', async () => {
      await freshStaffLogin(page, counselor)
      await page.goto(`${config.staffBaseUrl}/admin/student-affairs/leave/followup`)
      const search = page.getByPlaceholder('按学生姓名 / 学号搜索')
      await search.fill(config.student.username)
      await search.press('Enter')
      const item = page.locator('.lv-item').filter({ hasText: config.student.username }).first()
      await expect(item).toBeVisible()
      await item.click()
      await expect(page.locator('.lv-main')).toContainText(/待销假确认|销假记录/)
      await expect(page.locator('.lv-main')).toContainText(revisedReason)

      const confirmPromise = page.waitForResponse((response) =>
        response.url().endsWith(`/api/v1/student-affairs/leave/${leaveId}/cancel-confirm`) && response.request().method() === 'POST'
      )
      await page.getByRole('button', { name: '销假确认' }).click()
      await page.getByRole('button', { name: '确认销假' }).click()
      const confirmed = await confirmPromise
      expect(confirmed.ok(), `cancel confirm HTTP ${confirmed.status()}`).toBeTruthy()
      const confirmEnv = await confirmed.json()
      expect(confirmEnv.code).toBe(0)
    })

    await test.step('student browser re-login and refresh recovers CLOSED state', async () => {
      await freshStudentLogin(page)
      await page.goto(`${config.studentBaseUrl}/campus-service?tab=leave`)
      const record = page.locator('article.record').filter({ hasText: startDate }).filter({ hasText: endDate }).first()
      await expect(record).toBeVisible()
      await expect(record).toContainText('已销假')
    })

    await test.step('counselor statistics reflects exactly one newly closed leave', async () => {
      await freshStaffLogin(page, counselor)
      closedAfter = await readClosedMetric(page)
      expect(closedAfter).toBe(closedBefore + 1)
    })

    await test.step('Tenant B real browser cannot see Tenant A record and direct detail fails closed', async () => {
      const demoLogin = await freshStaffLogin(page, config.demoAdmin)
      await page.goto(`${config.staffBaseUrl}/admin/student-affairs/leave/followup`)
      const search = page.getByPlaceholder('按学生姓名 / 学号搜索')
      await search.fill(config.student.username)
      await search.press('Enter')
      await expect(page.locator('.lv-item').filter({ hasText: config.student.username })).toHaveCount(0)

      const direct = await page.request.get(`${config.apiBaseUrl}/student-affairs/leave/${leaveId}`, {
        headers: { Authorization: `Bearer ${demoLogin.lastAccessToken}` }
      })
      expect([403, 404], `cross-tenant detail must fail closed, got ${direct.status()}`).toContain(direct.status())
    })

    expect(api500, 'no unhandled API 5xx during journey').toEqual([])
    expect(consoleErrors, 'no browser console errors during journey').toEqual([])

    await fs.writeFile(path.resolve('student-affairs-audit-evidence.json'), JSON.stringify({
      exactHead: process.env.E2E_TARGET_SHA || '',
      prefix,
      leaveId,
      studentNo: config.student.username,
      startDate,
      endDate,
      initialReason,
      returnedReason,
      revisedReason,
      initialSubmitCount,
      closedBefore,
      closedAfter,
      finalUiState: 'CLOSED',
      tenantIsolation: 'PASS'
    }, null, 2), 'utf8')
  })
})
