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

function apiUrl(suffix) {
  return `${config.apiBaseUrl}${suffix}`
}

async function openAidWorkbench(page, account) {
  const login = await freshStaffLogin(page, account)
  await page.goto(`${config.staffBaseUrl}/admin/student-affairs/aid`)
  await expect(page.getByRole('heading', { name: '困难认定工作台', exact: true })).toBeVisible()
  return login
}

async function chooseAidItem(page, studentName = 'E2E学生A') {
  const item = page.locator('li.ad-qitem').filter({ hasText: studentName }).first()
  await expect(item).toBeVisible({ timeout: 15_000 })
  await item.click()
  await expect(page.locator('.ad-detail')).toContainText(studentName)
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

test.describe.serial('Student Affairs strict browser audit · aid / difficulty recognition', () => {
  test.describe.configure({ retries: 0 })

  test('browser-created batch -> student apply -> return/edit/resubmit -> four-node review -> publicity time gate -> objection review', async ({ page }) => {
    test.setTimeout(300_000)

    const prefix = `E2E-AUDIT-20260823-AID-${Date.now()}-${process.pid}`
    const batchName = `${prefix}-BATCH 家庭经济困难认定`
    const schoolYear = '2026-2027'
    const initialStatement = `${prefix}-APPLY 家庭主要收入来源不稳定，近期医疗和学习支出较大，申请困难认定。`
    const revisedStatement = `${prefix}-RESUBMIT 已补充家庭收入变化、医疗支出及返校后学习生活安排，请重新评议。`
    const returnReason = `${prefix}-RETURN 请补充家庭收入变化和近期医疗支出说明后重新提交。`
    const revealReason = `${prefix}-REVEAL 为本次困难认定核验家庭经济明细并留审计。`
    const objectionReason = `${prefix}-OBJECTION 对公示材料完整性提出异议，请资助工作组复核。`
    const objectionReviewOpinion = `${prefix}-OBJECTION-REVIEW 已核验原始材料，异议不成立，维持原认定结果。`

    const api500 = []
    const consoleErrors = []
    let batchId = ''
    let applyId = ''
    let submitCount = 0
    let initialVersion = null
    let wrongCounselorDetailStatus = null
    let wrongCounselorReviewStatus = null
    let tenantBDetailStatus = null
    let publicityConfirmStatus = null
    let publicityConfirmBizCode = ''
    let reviewerStatementVisible = null
    let maskedBeforeReveal = null
    let sensitiveRevealSucceeded = false
    let objectionId = ''

    page.on('response', (response) => {
      if (response.url().includes('/api/') && response.status() >= 500) api500.push(`${response.status()} ${response.request().method()} ${response.url()}`)
      try {
        const u = new URL(response.url())
        if (u.pathname.endsWith('/api/v1/portal/affairs/aid/apply') && response.request().method() === 'POST') submitCount += 1
      } catch {}
    })
    page.on('console', (message) => {
      if (message.type() !== 'error') return
      const text = message.text()
      if (/favicon|source map|Vue Devtools/i.test(text)) return
      consoleErrors.push(text)
    })

    await test.step('SA admin creates and publishes the real aid batch through browser UI', async () => {
      await freshStaffLogin(page, staff.saAdmin)
      await page.goto(`${config.staffBaseUrl}/admin/student-affairs/aid/batches`)
      await expect(page.getByText('认定批次管理', { exact: true }).first()).toBeVisible()
      await page.getByRole('button', { name: '建批次', exact: true }).click()
      await page.getByPlaceholder('如：2025-2026 学年家庭经济困难认定').fill(batchName)
      await page.getByPlaceholder('如：2025-2026', { exact: true }).fill(schoolYear)
      await page.locator('input[type="number"]').first().fill('1')
      const publish = page.getByText('立即发布（开放受理）', { exact: true }).locator('..').locator('input[type="checkbox"]')
      if (!(await publish.isChecked())) await publish.check()
      const createdPromise = page.waitForResponse((response) => {
        try { const u = new URL(response.url()); return u.pathname.endsWith('/api/v1/student-affairs/aid/batches') && response.request().method() === 'POST' } catch { return false }
      })
      await page.getByRole('button', { name: '保存', exact: true }).click()
      const created = await createdPromise
      expect(created.ok(), `aid batch create HTTP ${created.status()}`).toBeTruthy()
      const env = await jsonBody(created)
      expect(env.code).toBe(0)
      batchId = String(env.data?.batchId || env.data?.id || '')
      expect(batchId).toBeTruthy()
      const row = page.locator('tbody tr').filter({ hasText: batchName }).first()
      await expect(row).toBeVisible()
      await expect(row).toContainText('开放中')
      await expect(row).toContainText('1 天')
    })

    await test.step('student uses real portal form and rapid double-click creates only one application', async () => {
      await freshStudentLogin(page)
      await page.goto(`${config.studentBaseUrl}/campus-service?tab=aid`)
      await expect(page.getByText('家庭经济困难认定', { exact: true }).first()).toBeVisible()
      await page.getByLabel('开放批次').selectOption(batchId)
      await page.getByLabel('申请等级').selectOption('DIFFICULT')
      await page.getByLabel('家庭成员数（1-30）').fill('4')
      await page.getByLabel('家庭年收入（元）').fill('18000')
      await page.getByLabel('家庭债务（元）').fill('5000')
      await page.getByLabel('特殊情况标签').fill('低保，重大疾病')
      await page.getByLabel('困难情况说明（10-500字）').fill(initialStatement)
      await page.getByText('本人确认上述信息真实', { exact: false }).locator('..').locator('input[type="checkbox"]').check()
      const submittedPromise = page.waitForResponse((response) => {
        try { const u = new URL(response.url()); return u.pathname.endsWith('/api/v1/portal/affairs/aid/apply') && response.request().method() === 'POST' } catch { return false }
      })
      await page.getByRole('button', { name: '提交认定申请', exact: true }).dblclick()
      const submitted = await submittedPromise
      expect(submitted.ok(), `student aid apply HTTP ${submitted.status()}`).toBeTruthy()
      const env = await jsonBody(submitted)
      expect(env.code).toBe(0)
      applyId = String(env.data?.applyId || env.data?.id || '')
      initialVersion = Number(env.data?.version || 1)
      expect(applyId).toBeTruthy()
      await page.waitForTimeout(800)
      expect(submitCount).toBe(1)
      await page.reload()
      const record = page.locator('article.record').filter({ hasText: '班级评议' }).first()
      await expect(record).toBeVisible()
    })

    await test.step('same-tenant wrong counselor B is denied before any review', async () => {
      const login = await openAidWorkbench(page, staff.counselorB)
      await expect(page.locator('li.ad-qitem').filter({ hasText: 'E2E学生A' })).toHaveCount(0)
      const headers = { Authorization: `Bearer ${login.lastAccessToken}` }
      const detail = await page.request.get(apiUrl(`/student-affairs/aid/applications/${applyId}`), { headers })
      wrongCounselorDetailStatus = detail.status()
      expect(detail.ok()).toBeFalsy()
      expect([403, 404]).toContain(detail.status())
      const review = await page.request.post(apiUrl(`/student-affairs/aid/applications/${applyId}/review`), { headers, data: { action: 'APPROVE', level: 'DIFFICULT', reason: '', version: initialVersion } })
      wrongCounselorReviewStatus = review.status()
      expect(review.ok()).toBeFalsy()
      expect([400, 403, 404, 409]).toContain(review.status())
    })

    await test.step('assigned counselor sees masked family economy, can reveal only with audited reason, then returns through UI', async () => {
      await openAidWorkbench(page, staff.counselorA)
      await chooseAidItem(page)
      const detail = page.locator('.ad-detail')
      reviewerStatementVisible = await detail.getByText(initialStatement, { exact: true }).isVisible().catch(() => false)
      const detailText = await detail.innerText()
      maskedBeforeReveal = !detailText.includes('18000') && detailText.includes('1-2万')
      expect(maskedBeforeReveal).toBeTruthy()
      await detail.getByRole('button', { name: /查看完整/ }).click()
      const revealModal = page.locator('.ad-modal').filter({ hasText: '查看完整家庭经济' })
      await expect(revealModal).toBeVisible()
      await revealModal.locator('textarea').fill(revealReason)
      const revealPromise = page.waitForResponse((response) => response.url().endsWith(`/api/v1/student-affairs/aid/applications/${applyId}/reveal`) && response.request().method() === 'POST')
      await revealModal.getByRole('button', { name: '确认查看', exact: true }).click()
      const revealResponse = await revealPromise
      expect(revealResponse.ok(), `sensitive reveal HTTP ${revealResponse.status()}`).toBeTruthy()
      const revealEnv = await jsonBody(revealResponse)
      expect(revealEnv.code).toBe(0)
      sensitiveRevealSucceeded = true
      await expect(detail).toContainText('18000')
      await expect(detail).toContainText('5000')
      await detail.getByRole('button', { name: '退回', exact: true }).click()
      const returnPromise = page.waitForResponse((response) => response.url().endsWith(`/api/v1/student-affairs/aid/applications/${applyId}/review`) && response.request().method() === 'POST')
      await confirmDialog(page, '退回申请', '退回', returnReason)
      const returned = await returnPromise
      expect(returned.ok(), `aid return HTTP ${returned.status()}`).toBeTruthy()
      expect((await jsonBody(returned)).code).toBe(0)
    })

    await test.step('student sees exact return reason, edits sensitive fields and statement, then resubmits via browser', async () => {
      await freshStudentLogin(page)
      await page.goto(`${config.studentBaseUrl}/campus-service?tab=aid`)
      const record = page.locator('article.record').filter({ hasText: returnReason }).first()
      await expect(record).toBeVisible()
      await expect(record).toContainText('草稿')
      await record.getByRole('button', { name: '修改后重提', exact: true }).click()
      const modal = page.locator('section.sp-card.modal')
      await expect(modal).toBeVisible()
      await expect(modal).toContainText(returnReason)
      await modal.getByLabel('年收入').fill('16500')
      await modal.getByLabel('债务').fill('6200')
      await modal.getByLabel('情况说明（10-500字）').fill(revisedStatement)
      const resubmitPromise = page.waitForResponse((response) => response.url().endsWith(`/api/v1/mobile/affairs/aid/${applyId}/resubmit`) && response.request().method() === 'POST')
      await modal.getByRole('button', { name: '保存并提交', exact: true }).click()
      const resubmitted = await resubmitPromise
      expect(resubmitted.ok(), `aid resubmit HTTP ${resubmitted.status()}`).toBeTruthy()
      expect((await jsonBody(resubmitted)).code).toBe(0)
      await expect(record).toContainText('班级评议', { timeout: 15_000 })
    })

    await test.step('assigned counselor completes class review and counselor initial review via real workbench', async () => {
      await openAidWorkbench(page, staff.counselorA)
      await chooseAidItem(page)
      const detail = page.locator('.ad-detail')
      let reviewPromise = page.waitForResponse((response) => response.url().endsWith(`/api/v1/student-affairs/aid/applications/${applyId}/review`) && response.request().method() === 'POST')
      await detail.getByRole('button', { name: '评议通过', exact: true }).click()
      await confirmDialog(page, '评审通过', '评审通过')
      let reviewed = await reviewPromise
      expect(reviewed.ok(), `class review HTTP ${reviewed.status()}`).toBeTruthy()
      await expect(detail.getByRole('button', { name: '初审通过', exact: true })).toBeVisible({ timeout: 15_000 })
      reviewPromise = page.waitForResponse((response) => response.url().endsWith(`/api/v1/student-affairs/aid/applications/${applyId}/review`) && response.request().method() === 'POST')
      await detail.getByRole('button', { name: '初审通过', exact: true }).click()
      await confirmDialog(page, '评审通过', '评审通过')
      reviewed = await reviewPromise
      expect(reviewed.ok(), `counselor review HTTP ${reviewed.status()}`).toBeTruthy()
    })

    await test.step('college admin completes college review through real workbench', async () => {
      await openAidWorkbench(page, staff.collegeAdmin)
      await chooseAidItem(page)
      const detail = page.locator('.ad-detail')
      const reviewPromise = page.waitForResponse((response) => response.url().endsWith(`/api/v1/student-affairs/aid/applications/${applyId}/review`) && response.request().method() === 'POST')
      await detail.getByRole('button', { name: '复审通过', exact: true }).click()
      await confirmDialog(page, '评审通过', '评审通过')
      const reviewed = await reviewPromise
      expect(reviewed.ok(), `college review HTTP ${reviewed.status()}`).toBeTruthy()
    })

    await test.step('SA admin completes school review and application enters real publicity', async () => {
      await openAidWorkbench(page, staff.saAdmin)
      await chooseAidItem(page)
      const detail = page.locator('.ad-detail')
      const reviewPromise = page.waitForResponse((response) => response.url().endsWith(`/api/v1/student-affairs/aid/applications/${applyId}/review`) && response.request().method() === 'POST')
      await detail.getByRole('button', { name: '终审通过', exact: true }).click()
      await confirmDialog(page, '评审通过', '评审通过')
      const reviewed = await reviewPromise
      expect(reviewed.ok(), `school review HTTP ${reviewed.status()}`).toBeTruthy()
      await expect(detail).toContainText('公示中', { timeout: 15_000 })
    })

    await test.step('manual publicity confirmation before one full day fails closed and does not approve', async () => {
      const detail = page.locator('.ad-detail')
      const confirmPromise = page.waitForResponse((response) => response.url().endsWith(`/api/v1/student-affairs/aid/applications/${applyId}/publicity-confirm`) && response.request().method() === 'POST')
      await detail.getByRole('button', { name: '确认公示通过', exact: true }).click()
      await confirmDialog(page, '确认公示通过', '确认通过')
      const response = await confirmPromise
      publicityConfirmStatus = response.status()
      expect(response.ok(), `early publicity confirm must fail closed, got HTTP ${response.status()}`).toBeFalsy()
      const env = await jsonBody(response)
      publicityConfirmBizCode = String(env.bizCode || env.code || '')
      await page.waitForTimeout(300)
      await expect(detail).toContainText('公示中')
    })

    await test.step('student submits a real publicity objection from portal', async () => {
      await freshStudentLogin(page)
      await page.goto(`${config.studentBaseUrl}/campus-service?tab=aid`)
      const record = page.locator('article.record').filter({ hasText: '公示中' }).first()
      await expect(record).toBeVisible()
      await record.getByPlaceholder('公示异议理由（5-500字）').fill(objectionReason)
      const objectPromise = page.waitForResponse((response) => response.url().endsWith('/api/v1/portal/affairs/aid/objection') && response.request().method() === 'POST')
      await record.getByRole('button', { name: '提交异议', exact: true }).click()
      const objected = await objectPromise
      expect(objected.ok(), `student objection HTTP ${objected.status()}`).toBeTruthy()
      const env = await jsonBody(objected)
      expect(env.code).toBe(0)
      objectionId = String(env.data?.objectionId || env.data?.id || '')
      await expect(record).toContainText('异议已进入具体老师待办')
    })

    await test.step('SA admin reviews objection as overruled through real objection workbench', async () => {
      await freshStaffLogin(page, staff.saAdmin)
      await page.goto(`${config.staffBaseUrl}/admin/student-affairs/aid/objections`)
      await expect(page.getByText('困难认定异议复核', { exact: true }).first()).toBeVisible()
      const row = page.locator('tbody tr').filter({ hasText: objectionReason }).first()
      await expect(row).toBeVisible({ timeout: 15_000 })
      const reviewPromise = page.waitForResponse((response) => /\/api\/v1\/student-affairs\/aid\/objections\/\d+\/review$/.test(new URL(response.url()).pathname) && response.request().method() === 'POST')
      await row.getByRole('button', { name: '复核', exact: true }).click()
      const dialog = page.getByRole('dialog').filter({ hasText: '复核异议' }).last()
      await expect(dialog).toBeVisible()
      await dialog.locator('textarea').fill(objectionReviewOpinion)
      await dialog.getByRole('button', { name: '提交复核', exact: true }).click()
      const reviewed = await reviewPromise
      expect(reviewed.ok(), `objection review HTTP ${reviewed.status()}`).toBeTruthy()
      const env = await jsonBody(reviewed)
      expect(env.code).toBe(0)
      if (!objectionId) objectionId = String(env.data?.objectionId || env.data?.id || '')
      await expect(page.locator('tbody tr').filter({ hasText: objectionReason }).first()).toContainText('异议不成立')
    })

    await test.step('tenant B cannot read sandbox aid application by direct authenticated request', async () => {
      const login = await freshStaffLogin(page, config.demoAdmin)
      expect(login.lastAccessToken).toBeTruthy()
      const response = await page.request.get(apiUrl(`/student-affairs/aid/applications/${applyId}`), { headers: { Authorization: `Bearer ${login.lastAccessToken}` } })
      tenantBDetailStatus = response.status()
      expect(response.ok()).toBeFalsy()
      expect([403, 404]).toContain(response.status())
    })

    expect(api500, 'no unhandled API 5xx during strict aid journey').toEqual([])
    expect(consoleErrors, 'no browser console errors during strict aid journey').toEqual([])

    await fs.writeFile(path.resolve('student-affairs-aid-audit-evidence.json'), JSON.stringify({
      exactHead: process.env.E2E_TARGET_SHA || '', prefix, batchId, batchName, schoolYear, applyId,
      initialVersion, initialStatement, revisedStatement, returnReason, revealReason, objectionReason,
      objectionReviewOpinion, objectionId, submitCount, wrongCounselorDetailStatus,
      wrongCounselorReviewStatus, tenantBDetailStatus, publicityConfirmStatus, publicityConfirmBizCode,
      reviewerStatementVisible, maskedBeforeReveal, sensitiveRevealSucceeded,
      expectedFinalState: 'PUBLICITY_TIME_GATED'
    }, null, 2), 'utf8')
  })
})