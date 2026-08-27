import fs from 'node:fs/promises'
import path from 'node:path'
import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { StudentLoginPage, StaffLoginPage } from '../pages/login.page.mjs'

const staff = {
  saAdmin: { tenant: 'sandbox-school', username: 'e2e_sa_admin', password: 'E2eTest@2026' },
  collegeAdmin: { tenant: 'sandbox-school', username: 'e2e_college_admin', password: 'E2eTest@2026' },
  counselorA: { tenant: 'sandbox-school', username: 'e2e_counselor_a', password: 'E2eTest@2026' },
  counselorB: { tenant: 'sandbox-school', username: 'e2e_counselor_b', password: 'E2eTest@2026' }
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

function apiUrl(suffix) { return `${config.apiBaseUrl}${suffix}` }

async function openFundingWorkbench(page, account) {
  const login = await freshStaffLogin(page, account)
  await page.goto(`${config.staffBaseUrl}/admin/student-affairs/funding`)
  await expect(page.getByRole('heading', { name: '奖助管理工作台', exact: true })).toBeVisible()
  return login
}

async function chooseFundingItem(page, studentName = 'E2E学生A') {
  const item = page.locator('li.fd-qitem').filter({ hasText: studentName }).first()
  await expect(item).toBeVisible({ timeout: 20_000 })
  await item.click()
  await expect(page.locator('.fd-detail')).toContainText(studentName)
  return item
}

async function confirmDialog(page, title, confirmText, reason = '') {
  const dialog = page.getByRole('dialog').filter({ hasText: title }).last()
  await expect(dialog).toBeVisible()
  if (reason) {
    const textarea = dialog.locator('textarea').first()
    await expect(textarea).toBeVisible()
    await textarea.fill(reason)
  }
  await dialog.getByRole('button', { name: confirmText, exact: true }).click()
}

test.describe.serial('Student Affairs strict browser audit · SA-004 scholarship', () => {
  test.describe.configure({ retries: 0 })

  test('student apply -> return/edit/resubmit -> three-node review -> publicity -> appeal review -> time gate', async ({ page }) => {
    test.setTimeout(300_000)

    const prefix = `E2E-SA004-${Date.now()}-${process.pid}`
    let projectName = ''
    let schoolYear = ''
    const initialStatement = `${prefix}-APPLY 本学年学习表现稳定并积极参加集体活动，申请奖学金。`
    const revisedStatement = `${prefix}-RESUBMIT 已补充本学年学习情况、实践表现和申请依据，请重新审核。`
    const returnReason = `${prefix}-RETURN 请补充本学年学习表现和实践情况后重新提交。`
    const appealReason = `${prefix}-APPEAL 对公示信息核对结果有疑问，申请复核本次奖学金资格。`
    const appealOpinion = `${prefix}-APPEAL-REVIEW 已重新核对申请材料与资格快照，申诉不成立，维持公示资格。`

    let projectId = ''
    let batchId = ''
    let applicationId = ''
    let appealId = ''
    let initialVersion = null
    let submitCount = 0
    let wrongCounselorDetailStatus = null
    let wrongCounselorReviewStatus = null
    let tenantBDetailStatus = null
    let earlyConfirmStatus = null
    let earlyConfirmBizCode = ''
    const api500 = []
    const consoleErrors = []
    const browserHttpErrors = []

    const observePage = (targetPage) => {
      targetPage.on('response', (response) => {
        if (response.url().includes('/api/') && response.status() >= 500) api500.push(`${response.status()} ${response.request().method()} ${response.url()}`)
        if (response.url().includes('/api/') && response.status() >= 400 && response.status() < 500) browserHttpErrors.push(`${response.status()} ${response.request().method()} ${response.url()}`)
        try {
          const u = new URL(response.url())
          if (u.pathname.endsWith('/api/v1/portal/affairs/funding/apply') && response.request().method() === 'POST') submitCount += 1
        } catch {}
      })
      targetPage.on('console', (message) => {
        if (message.type() !== 'error') return
        const text = message.text()
        if (/favicon|source map|Vue Devtools/i.test(text)) return
        consoleErrors.push(text)
      })
    }

    observePage(page)
    const browser = page.context().browser()
    if (!browser) throw new Error('SA-004 journey requires a real browser for the persistent student session')
    const studentContext = await browser.newContext()
    const studentPage = await studentContext.newPage()
    observePage(studentPage)

    await test.step('reuse project and one-day batch created by the preceding real Staff PC configuration gate', async () => {
      const evidencePath = path.resolve('student-affairs-scholarship-config-v3-evidence.json')
      const evidence = JSON.parse(await fs.readFile(evidencePath, 'utf8'))
      expect(String(evidence.exactHead || '')).toBe(String(process.env.E2E_TARGET_SHA || ''))
      expect(evidence.result).toBe('REAL_PASS')
      expect(evidence.surface).toBe('STAFF_PC')
      expect(Number(evidence.publicityDays)).toBe(1)
      projectId = String(evidence.projectId || '')
      batchId = String(evidence.batchId || '')
      projectName = String(evidence.projectName || '')
      schoolYear = String(evidence.schoolYear || '')
      expect(projectId).toBeTruthy()
      expect(batchId).toBeTruthy()
      expect(projectName).toBeTruthy()
      expect(schoolYear).toBeTruthy()
    })

    await test.step('student submits scholarship in real PC portal; rapid double-click creates one request', async () => {
      await freshStudentLogin(studentPage)
      await studentPage.goto(`${config.studentBaseUrl}/campus-service?tab=funding`)
      await expect(studentPage.locator('.sp-panel__head').filter({ hasText: '奖学金与助学金' }).first()).toBeVisible()
      await studentPage.getByLabel('类型').selectOption('SCHOLARSHIP')
      await studentPage.getByLabel('开放批次').selectOption(batchId)
      await studentPage.getByLabel('申请理由（5-1000字）').fill(initialStatement)
      await studentPage.getByText('本人确认申请信息真实', { exact: false }).locator('..').locator('input[type="checkbox"]').check()
      const submittedPromise = studentPage.waitForResponse((response) => {
        try { const u = new URL(response.url()); return u.pathname.endsWith('/api/v1/portal/affairs/funding/apply') && response.request().method() === 'POST' } catch { return false }
      })
      await studentPage.getByRole('button', { name: '提交申请', exact: true }).dblclick()
      const submitted = await submittedPromise
      expect(submitted.ok(), `funding apply HTTP ${submitted.status()}`).toBeTruthy()
      const env = await jsonBody(submitted)
      expect(env.code).toBe(0)
      applicationId = String(env.data?.applicationId || env.data?.id || '')
      initialVersion = Number(env.data?.version || 0)
      expect(applicationId).toBeTruthy()
      await studentPage.waitForTimeout(800)
      expect(submitCount).toBe(1)
      const record = studentPage.locator('article.record').filter({ hasText: '辅导员初审' }).first()
      await expect(record).toBeVisible({ timeout: 15_000 })
    })

    await test.step('same-tenant wrong counselor cannot read or review the scholarship application', async () => {
      const login = await openFundingWorkbench(page, staff.counselorB)
      await expect(page.locator('li.fd-qitem').filter({ hasText: 'E2E学生A' })).toHaveCount(0)
      const headers = { Authorization: `Bearer ${login.lastAccessToken}` }
      const detail = await page.request.get(apiUrl(`/student-affairs/funding/applications/${applicationId}`), { headers })
      wrongCounselorDetailStatus = detail.status()
      expect(detail.ok()).toBeFalsy()
      expect([403, 404]).toContain(detail.status())
      const review = await page.request.post(apiUrl(`/student-affairs/funding/applications/${applicationId}/review`), {
        headers, data: { action: 'APPROVE', reason: '', version: initialVersion }
      })
      wrongCounselorReviewStatus = review.status()
      expect(review.ok()).toBeFalsy()
      expect([400, 403, 404, 409]).toContain(review.status())
    })

    await test.step('assigned counselor sees the actual application statement and returns it through real workbench', async () => {
      await openFundingWorkbench(page, staff.counselorA)
      await chooseFundingItem(page)
      const detail = page.locator('.fd-detail')
      await expect(detail.getByText(initialStatement, { exact: true }), 'reviewer must see the student statement before deciding').toBeVisible({ timeout: 15_000 })
      await detail.getByRole('button', { name: '退回', exact: true }).click()
      const returnPromise = page.waitForResponse((response) => response.url().endsWith(`/api/v1/student-affairs/funding/applications/${applicationId}/review`) && response.request().method() === 'POST')
      await confirmDialog(page, '退回申请', '退回', returnReason)
      const returned = await returnPromise
      expect(returned.ok(), `funding return HTTP ${returned.status()}`).toBeTruthy()
      expect((await jsonBody(returned)).code).toBe(0)
    })

    await test.step('student sees exact return reason, edits statement and resubmits through browser', async () => {
      await studentPage.goto(`${config.studentBaseUrl}/campus-service?tab=funding`)
      const record = studentPage.locator('article.record').filter({ hasText: returnReason }).first()
      await expect(record).toBeVisible({ timeout: 15_000 })
      await record.getByRole('button', { name: '修改后重提', exact: true }).click()
      const modal = studentPage.locator('section.sp-card.modal')
      await expect(modal).toBeVisible()
      await expect(modal).toContainText(returnReason)
      const textarea = modal.locator('textarea').first()
      await textarea.fill(revisedStatement)
      const resubmitPromise = studentPage.waitForResponse((response) => response.url().endsWith(`/api/v1/mobile/affairs/funding/${applicationId}/resubmit`) && response.request().method() === 'POST')
      await modal.getByRole('button', { name: '保存并提交', exact: true }).click()
      const resubmitted = await resubmitPromise
      expect(resubmitted.ok(), `funding resubmit HTTP ${resubmitted.status()}`).toBeTruthy()
      const env = await jsonBody(resubmitted)
      expect(env.code).toBe(0)
    })

    await test.step('assigned counselor sees revised statement and approves counselor review', async () => {
      await openFundingWorkbench(page, staff.counselorA)
      await chooseFundingItem(page)
      const detail = page.locator('.fd-detail')
      await expect(detail.getByText(revisedStatement, { exact: true }), 'reviewer must see the revised statement after resubmit').toBeVisible({ timeout: 15_000 })
      const reviewPromise = page.waitForResponse((response) => response.url().endsWith(`/api/v1/student-affairs/funding/applications/${applicationId}/review`) && response.request().method() === 'POST')
      await detail.getByRole('button', { name: '审批通过', exact: true }).click()
      await confirmDialog(page, '审批通过', '审批通过')
      const reviewed = await reviewPromise
      expect(reviewed.ok(), `counselor review HTTP ${reviewed.status()}`).toBeTruthy()
    })

    await test.step('college admin approves college review through real workbench', async () => {
      await openFundingWorkbench(page, staff.collegeAdmin)
      await chooseFundingItem(page)
      const detail = page.locator('.fd-detail')
      await expect(detail.getByText(revisedStatement, { exact: true })).toBeVisible({ timeout: 15_000 })
      const reviewPromise = page.waitForResponse((response) => response.url().endsWith(`/api/v1/student-affairs/funding/applications/${applicationId}/review`) && response.request().method() === 'POST')
      await detail.getByRole('button', { name: '审批通过', exact: true }).click()
      await confirmDialog(page, '审批通过', '审批通过')
      const reviewed = await reviewPromise
      expect(reviewed.ok(), `college review HTTP ${reviewed.status()}`).toBeTruthy()
    })

    await test.step('SA admin approves school review and application enters publicity', async () => {
      await openFundingWorkbench(page, staff.saAdmin)
      await chooseFundingItem(page)
      const detail = page.locator('.fd-detail')
      await expect(detail.getByText(revisedStatement, { exact: true })).toBeVisible({ timeout: 15_000 })
      const reviewPromise = page.waitForResponse((response) => response.url().endsWith(`/api/v1/student-affairs/funding/applications/${applicationId}/review`) && response.request().method() === 'POST')
      await detail.getByRole('button', { name: '审批通过', exact: true }).click()
      await confirmDialog(page, '审批通过', '审批通过')
      const reviewed = await reviewPromise
      expect(reviewed.ok(), `school review HTTP ${reviewed.status()}`).toBeTruthy()
      await expect(detail).toContainText('公示中', { timeout: 15_000 })
    })

    await test.step('one-day publicity cannot be confirmed early', async () => {
      const detail = page.locator('.fd-detail')
      const confirmPromise = page.waitForResponse((response) => response.url().endsWith(`/api/v1/student-affairs/funding/applications/${applicationId}/publicity-confirm`) && response.request().method() === 'POST')
      await detail.getByRole('button', { name: '确认公示通过', exact: true }).click()
      await confirmDialog(page, '确认公示通过', '确认通过')
      const response = await confirmPromise
      earlyConfirmStatus = response.status()
      expect(response.status()).toBe(409)
      const env = await jsonBody(response)
      earlyConfirmBizCode = String(env.bizCode || env.code || '')
      await expect(detail).toContainText('公示中')
    })

    await test.step('student submits one real publicity appeal from PC portal', async () => {
      await studentPage.goto(`${config.studentBaseUrl}/campus-service?tab=funding`)
      const record = studentPage.locator('article.record').filter({ hasText: '公示中' }).first()
      await expect(record).toBeVisible({ timeout: 15_000 })
      await record.getByPlaceholder('公示申诉理由（5-1000字）').fill(appealReason)
      const appealPromise = studentPage.waitForResponse((response) => response.url().endsWith('/api/v1/portal/affairs/funding/appeal') && response.request().method() === 'POST')
      await record.getByRole('button', { name: '提交申诉', exact: true }).dblclick()
      const appealed = await appealPromise
      expect(appealed.ok(), `student funding appeal HTTP ${appealed.status()}`).toBeTruthy()
      const env = await jsonBody(appealed)
      expect(env.code).toBe(0)
      appealId = String(env.data?.appealId || env.data?.id || '')
      expect(appealId).toBeTruthy()
      await expect(record).toContainText('申诉待复核')
    })

    await test.step('SA admin reviews appeal as overruled through real appeal workbench', async () => {
      await freshStaffLogin(page, staff.saAdmin)
      await page.goto(`${config.staffBaseUrl}/admin/student-affairs/funding/appeals`)
      await expect(page.getByRole('heading', { name: '资助公示申诉复核', exact: true })).toBeVisible()
      const row = page.locator('tbody tr').filter({ hasText: appealReason }).first()
      await expect(row).toBeVisible({ timeout: 15_000 })
      await row.getByRole('button', { name: '复核', exact: true }).click()
      const dialog = page.getByRole('dialog').filter({ hasText: '复核申诉' }).last()
      await expect(dialog).toBeVisible()
      await dialog.locator('textarea').fill(appealOpinion)
      const reviewPromise = page.waitForResponse((response) => /\/api\/v1\/student-affairs\/funding\/appeals\/\d+\/review$/.test(new URL(response.url()).pathname) && response.request().method() === 'POST')
      await dialog.getByRole('button', { name: '提交复核', exact: true }).click()
      const reviewed = await reviewPromise
      expect(reviewed.ok(), `appeal review HTTP ${reviewed.status()}`).toBeTruthy()
      expect((await jsonBody(reviewed)).code).toBe(0)
      await expect(page.locator('tbody tr').filter({ hasText: appealReason }).first()).toContainText('申诉不成立')
    })

    await test.step('tenant B cannot read the scholarship application', async () => {
      const login = await freshStaffLogin(page, config.demoAdmin)
      const response = await page.request.get(apiUrl(`/student-affairs/funding/applications/${applicationId}`), {
        headers: { Authorization: `Bearer ${login.lastAccessToken}` }
      })
      tenantBDetailStatus = response.status()
      expect(response.ok()).toBeFalsy()
      expect([403, 404]).toContain(response.status())
    })

    expect(api500, 'no unhandled API 5xx during SA-004 journey').toEqual([])
    const expected4xx = browserHttpErrors.filter((line) => line.includes(`/funding/applications/${applicationId}/publicity-confirm`))
    expect(expected4xx.length).toBe(1)
    expect(expected4xx[0]).toMatch(/^409 POST /)
    const unexpectedConsoleErrors = [...consoleErrors]
    if (earlyConfirmStatus === 409) {
      const index = unexpectedConsoleErrors.findIndex((text) => /Failed to load resource:.*409 \(Conflict\)/i.test(text))
      if (index >= 0) unexpectedConsoleErrors.splice(index, 1)
    }
    expect(unexpectedConsoleErrors, 'no unexpected browser console errors during SA-004 journey').toEqual([])

    await fs.writeFile(path.resolve('student-affairs-scholarship-audit-evidence.json'), JSON.stringify({
      exactHead: process.env.E2E_TARGET_SHA || '', prefix, projectId, projectName, batchId, schoolYear,
      applicationId, appealId, initialVersion, initialStatement, revisedStatement, returnReason,
      appealReason, appealOpinion, submitCount, wrongCounselorDetailStatus, wrongCounselorReviewStatus,
      tenantBDetailStatus, earlyConfirmStatus, earlyConfirmBizCode,
      expectedInterimState: 'PUBLICITY_TIME_GATED_AFTER_OVERRULED_APPEAL'
    }, null, 2), 'utf8')
    await studentContext.close()
  })
})