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

async function openDisciplineWorkbench(page, account) {
  const login = await freshStaffLogin(page, account)
  await page.goto(`${config.staffBaseUrl}/admin/student-affairs/discipline`)
  await expect(page.getByRole('heading', { name: '违纪处分工作台', exact: true })).toBeVisible({ timeout: 15_000 })
  return login
}

async function chooseCase(page, marker) {
  const item = page.locator('li.dp-qitem').filter({ hasText: marker }).first()
  await expect(item).toBeVisible({ timeout: 15_000 })
  await item.click()
  await expect(page.locator('.dp-detail')).toContainText(marker)
  return item
}

async function confirmDialog(page, title, confirmText, reason = '') {
  const dialog = page.getByRole('dialog').filter({ hasText: title }).last()
  await expect(dialog).toBeVisible()
  if (reason) {
    const textarea = dialog.locator('textarea').last()
    await expect(textarea).toBeVisible()
    await textarea.fill(reason)
  }
  await dialog.getByRole('button', { name: confirmText, exact: true }).click()
}

async function approveCurrentCase(page, caseId) {
  const responsePromise = page.waitForResponse((response) => {
    try {
      const u = new URL(response.url())
      return u.pathname.endsWith(`/api/v1/student-affairs/discipline/cases/${caseId}/review`) && response.request().method() === 'POST'
    } catch { return false }
  })
  await page.locator('.dp-detail').getByRole('button', { name: '审批通过', exact: true }).click()
  await confirmDialog(page, '审批通过', '审批通过')
  const response = await responsePromise
  expect(response.ok(), `discipline review HTTP ${response.status()}`).toBeTruthy()
  const env = await jsonBody(response)
  expect(env.code).toBe(0)
  return env.data || {}
}

async function approveRemoval(page, caseId) {
  const responsePromise = page.waitForResponse((response) => {
    try {
      const u = new URL(response.url())
      return u.pathname.endsWith(`/api/v1/student-affairs/discipline/cases/${caseId}/remove-review`) && response.request().method() === 'POST'
    } catch { return false }
  })
  await page.locator('.dp-detail').getByRole('button', { name: '解除通过', exact: true }).click()
  await confirmDialog(page, '解除审批通过', '解除通过')
  const response = await responsePromise
  expect(response.ok(), `discipline remove review HTTP ${response.status()}`).toBeTruthy()
  const env = await jsonBody(response)
  expect(env.code).toBe(0)
  return env.data || {}
}

test.describe.serial('Student Affairs strict browser audit · discipline lifecycle', () => {
  test.describe.configure({ retries: 0 })

  test('register -> approve -> deliver -> student appeal -> revise decision -> three-node removal -> removed', async ({ page }) => {
    test.setTimeout(360_000)

    const prefix = `E2E-AUDIT-20260823-DISC-${Date.now()}-${process.pid}`
    const initialReason = `${prefix}-FACT 学生在校纪行为处理中存在明确违纪事实，现按程序登记警告处分。`
    const docNo = `${prefix}-DOC`
    const appealReason = `${prefix}-APPEAL 学生对原处分事实认定与处分尺度提出正式申诉，请重新复核。`
    const revisedReason = `${prefix}-REVISED 经复核补充证据后重新认定违纪事实，并依法调整处分决定。`
    const revisedDocNo = `${prefix}-REV-DOC`
    const reviewOpinion = `${prefix}-OPINION 复核确认事实依据需要调整，决定变更处分并形成新决定版本。`
    const removeReason = `${prefix}-REMOVE 学生后续表现稳定并完成整改教育，申请按流程解除处分。`

    const api500 = []
    const browserHttpErrors = []
    const consoleErrors = []
    let caseId = ''
    let appealId = ''
    let currentVersion = null
    let studentAppealSubmitCount = 0
    let wrongCounselorDetailStatus = null
    let wrongCounselorReviewStatus = null
    let tenantBDetailStatus = null
    let terminalReplayStatus = null
    let decisionVersion = null

    page.on('response', (response) => {
      if (response.url().includes('/api/') && response.status() >= 500) api500.push(`${response.status()} ${response.request().method()} ${response.url()}`)
      if (response.url().includes('/api/') && response.status() >= 400 && response.status() < 500) browserHttpErrors.push(`${response.status()} ${response.request().method()} ${response.url()}`)
      try {
        const u = new URL(response.url())
        if (u.pathname.endsWith('/api/v1/portal/affairs/discipline/appeal') && response.request().method() === 'POST') studentAppealSubmitCount += 1
      } catch {}
    })
    page.on('console', (message) => {
      if (message.type() !== 'error') return
      const text = message.text()
      if (/favicon|source map|Vue Devtools/i.test(text)) return
      consoleErrors.push(text)
    })

    await test.step('SA admin registers a real WARNING discipline and submits it to college review through UI', async () => {
      await openDisciplineWorkbench(page, staff.saAdmin)
      await page.getByRole('button', { name: '登记处分', exact: true }).click()
      await expect(page.getByText('登记违纪处分', { exact: true }).last()).toBeVisible()

      const studentSearch = page.getByPlaceholder('按姓名 / 学号搜索学生')
      await studentSearch.fill('E2E20260001')
      const studentOption = page.getByText(/E2E学生A.*E2E20260001|E2E20260001.*E2E学生A/).last()
      await expect(studentOption).toBeVisible({ timeout: 15_000 })
      await studentOption.click()

      const drawer = page.getByText('登记违纪处分', { exact: true }).last().locator('..').locator('..')
      await page.locator('select').last().selectOption('WARNING')
      await page.getByPlaceholder('客观描述违纪事实，不少于 5 字').fill(initialReason)
      await page.getByPlaceholder('选填，如「校学字〔2026〕12号」').fill(docNo)
      const createPromise = page.waitForResponse((response) => {
        try { const u = new URL(response.url()); return u.pathname.endsWith('/api/v1/student-affairs/discipline/cases') && response.request().method() === 'POST' } catch { return false }
      })
      await page.getByRole('button', { name: '登记', exact: true }).click()
      const created = await createPromise
      expect(created.ok(), `discipline register HTTP ${created.status()}`).toBeTruthy()
      const createdEnv = await jsonBody(created)
      expect(createdEnv.code).toBe(0)
      caseId = String(createdEnv.data?.caseId || createdEnv.data?.id || '')
      currentVersion = Number(createdEnv.data?.version ?? 0)
      expect(caseId).toBeTruthy()

      await chooseCase(page, prefix)
      const submitPromise = page.waitForResponse((response) => response.url().endsWith(`/api/v1/student-affairs/discipline/cases/${caseId}/submit`) && response.request().method() === 'POST')
      await page.locator('.dp-detail').getByRole('button', { name: '提交初审', exact: true }).click()
      await confirmDialog(page, '提交学院初审', '提交初审')
      const submitted = await submitPromise
      expect(submitted.ok(), `discipline submit HTTP ${submitted.status()}`).toBeTruthy()
      const submittedEnv = await jsonBody(submitted)
      expect(submittedEnv.code).toBe(0)
      currentVersion = Number(submittedEnv.data?.version ?? currentVersion)
      await expect(page.locator('.dp-detail')).toContainText('学院初审')
    })

    await test.step('same-tenant wrong counselor B cannot read or review the case', async () => {
      const login = await openDisciplineWorkbench(page, staff.counselorB)
      await expect(page.locator('li.dp-qitem').filter({ hasText: prefix })).toHaveCount(0)
      const headers = { Authorization: `Bearer ${login.lastAccessToken}` }
      const detail = await page.request.get(apiUrl(`/student-affairs/discipline/cases/${caseId}`), { headers })
      wrongCounselorDetailStatus = detail.status()
      expect(detail.ok()).toBeFalsy()
      expect([403, 404]).toContain(detail.status())
      const review = await page.request.post(apiUrl(`/student-affairs/discipline/cases/${caseId}/review`), {
        headers,
        data: { action: 'APPROVE', reason: '', version: currentVersion }
      })
      wrongCounselorReviewStatus = review.status()
      expect(review.ok()).toBeFalsy()
      expect([400, 403, 404, 409]).toContain(review.status())
    })

    await test.step('college admin approves college review through real workbench', async () => {
      await openDisciplineWorkbench(page, staff.collegeAdmin)
      await chooseCase(page, prefix)
      const data = await approveCurrentCase(page, caseId)
      currentVersion = Number(data.version ?? currentVersion)
      await expect(page.locator('.dp-detail')).toContainText('学工处复核')
    })

    await test.step('SA admin approves student-affairs review and creates the real EFFECTIVE projection', async () => {
      await openDisciplineWorkbench(page, staff.saAdmin)
      await chooseCase(page, prefix)
      const data = await approveCurrentCase(page, caseId)
      currentVersion = Number(data.version ?? currentVersion)
      await expect(page.locator('.dp-detail')).toContainText('已生效')
      await expect(page.locator('.dp-detail')).toContainText('警告')
    })

    await test.step('SA admin records formal DIRECT delivery through the delivery page', async () => {
      await page.goto(`${config.staffBaseUrl}/admin/student-affairs/discipline/appeals`)
      await expect(page.getByRole('heading', { name: '处分送达与申诉', exact: true })).toBeVisible()
      const row = page.locator('tbody tr').filter({ hasText: 'E2E学生A' }).filter({ hasText: '警告' }).filter({ hasText: '未送达' }).first()
      await expect(row).toBeVisible({ timeout: 15_000 })
      const deliverPromise = page.waitForResponse((response) => response.url().endsWith(`/api/v1/student-affairs/discipline/cases/${caseId}/deliver`) && response.request().method() === 'POST')
      await row.getByRole('button', { name: '登记送达', exact: true }).click()
      const dialog = page.getByRole('dialog').filter({ hasText: '登记处分送达' }).last()
      await expect(dialog).toBeVisible()
      await dialog.locator('select').selectOption('DIRECT')
      await dialog.getByRole('button', { name: '确认登记送达', exact: true }).click()
      const delivered = await deliverPromise
      expect(delivered.ok(), `discipline delivery HTTP ${delivered.status()}`).toBeTruthy()
      expect((await jsonBody(delivered)).code).toBe(0)
      await expect(row).toContainText('直接送达', { timeout: 15_000 })
    })

    await test.step('student sees the effective WARNING and submits exactly one real appeal from portal', async () => {
      await freshStudentLogin(page)
      await page.goto(`${config.studentBaseUrl}/campus-service?tab=discipline`)
      await expect(page.locator('.sp-panel__head').filter({ hasText: '处分申诉' })).toBeVisible()
      const record = page.locator('article.record').filter({ hasText: '警告' }).first()
      await expect(record).toBeVisible({ timeout: 15_000 })
      await record.getByPlaceholder('处分申诉理由（5-1000字）').fill(appealReason)
      const appealPromise = page.waitForResponse((response) => response.url().endsWith('/api/v1/portal/affairs/discipline/appeal') && response.request().method() === 'POST')
      await record.getByRole('button', { name: '提交处分申诉', exact: true }).dblclick()
      const appealed = await appealPromise
      expect(appealed.ok(), `student discipline appeal HTTP ${appealed.status()}`).toBeTruthy()
      const env = await jsonBody(appealed)
      expect(env.code).toBe(0)
      appealId = String(env.data?.appealId || env.data?.id || '')
      await page.waitForTimeout(800)
      expect(studentAppealSubmitCount).toBe(1)
      await expect(record).toContainText('申诉已提交')
    })

    await test.step('SA admin revises WARNING to SERIOUS_WARNING with real revised facts through appeal UI', async () => {
      await freshStaffLogin(page, staff.saAdmin)
      await page.goto(`${config.staffBaseUrl}/admin/student-affairs/discipline/appeals`)
      await expect(page.getByRole('heading', { name: '处分送达与申诉', exact: true })).toBeVisible()
      const row = page.locator('tbody tr').filter({ hasText: appealReason }).first()
      await expect(row).toBeVisible({ timeout: 15_000 })
      await row.getByRole('button', { name: '复核', exact: true }).click()
      const dialog = page.getByRole('dialog').filter({ hasText: '复核处分申诉' }).last()
      await expect(dialog).toBeVisible()
      await dialog.locator('select').first().selectOption('REVISED')
      await dialog.locator('select').nth(1).selectOption('SERIOUS_WARNING')
      await dialog.getByPlaceholder('请填写变更决定采用的完整事实依据，不得用复核意见代替').fill(revisedReason)
      await dialog.getByPlaceholder('选填；如文号不变可保留原文号').fill(revisedDocNo)
      const textareas = dialog.locator('textarea')
      const count = await textareas.count()
      expect(count).toBeGreaterThanOrEqual(2)
      await textareas.first().fill(reviewOpinion)
      const reviewPromise = page.waitForResponse((response) => /\/api\/v1\/student-affairs\/discipline\/appeals\/\d+\/review$/.test(new URL(response.url()).pathname) && response.request().method() === 'POST')
      await dialog.getByRole('button', { name: '提交复核结论', exact: true }).click()
      const reviewed = await reviewPromise
      expect(reviewed.ok(), `discipline appeal review HTTP ${reviewed.status()}`).toBeTruthy()
      const env = await jsonBody(reviewed)
      expect(env.code).toBe(0)
      decisionVersion = Number(env.data?.decisionVersion || 0)
      if (!appealId) appealId = String(env.data?.appealId || env.data?.id || '')
      await expect(page.locator('tbody tr').filter({ hasText: appealReason }).first()).toContainText('已变更')
    })

    await test.step('student refresh sees revised SERIOUS_WARNING and exact review opinion', async () => {
      await freshStudentLogin(page)
      await page.goto(`${config.studentBaseUrl}/campus-service?tab=discipline`)
      const record = page.locator('article.record').filter({ hasText: '严重警告' }).first()
      await expect(record).toBeVisible({ timeout: 15_000 })
      await expect(record).toContainText(reviewOpinion)
      await expect(record).toContainText('处分已变更')
    })

    await test.step('SA admin starts removal after appeal closes', async () => {
      await openDisciplineWorkbench(page, staff.saAdmin)
      await chooseCase(page, prefix)
      await expect(page.locator('.dp-detail')).toContainText('严重警告')
      const removePromise = page.waitForResponse((response) => response.url().endsWith(`/api/v1/student-affairs/discipline/cases/${caseId}/remove`) && response.request().method() === 'POST')
      await page.locator('.dp-detail').getByRole('button', { name: '发起解除', exact: true }).click()
      await confirmDialog(page, '发起处分解除', '发起解除', removeReason)
      const removed = await removePromise
      expect(removed.ok(), `discipline remove submit HTTP ${removed.status()}`).toBeTruthy()
      expect((await jsonBody(removed)).code).toBe(0)
      await expect(page.locator('.dp-detail')).toContainText('解除审批')
    })

    await test.step('assigned counselor A approves removal first node through browser', async () => {
      await openDisciplineWorkbench(page, staff.counselorA)
      await chooseCase(page, prefix)
      await approveRemoval(page, caseId)
      await expect(page.locator('.dp-detail')).toContainText('解除审批')
    })

    await test.step('college admin approves removal second node through browser', async () => {
      await openDisciplineWorkbench(page, staff.collegeAdmin)
      await chooseCase(page, prefix)
      await approveRemoval(page, caseId)
      await expect(page.locator('.dp-detail')).toContainText('解除审批')
    })

    let saAdminToken = ''
    await test.step('SA admin approves final removal and case reaches REMOVED terminal state', async () => {
      const login = await openDisciplineWorkbench(page, staff.saAdmin)
      saAdminToken = login.lastAccessToken
      await chooseCase(page, prefix)
      await approveRemoval(page, caseId)
      await expect(page.locator('.dp-detail')).toContainText('已解除', { timeout: 15_000 })
      await expect(page.locator('.dp-detail')).toContainText('严重警告')
      await expect(page.locator('.dp-detail')).toContainText('仅可查看')
    })

    await test.step('student refresh no longer has an active discipline case', async () => {
      await freshStudentLogin(page)
      await page.goto(`${config.studentBaseUrl}/campus-service?tab=discipline`)
      await expect(page.locator('.sp-panel__head').filter({ hasText: '处分申诉' })).toBeVisible()
      await expect(page.locator('article.record').filter({ hasText: appealReason })).toHaveCount(0)
    })

    await test.step('terminal replay fails closed and tenant B cannot read sandbox case', async () => {
      const replay = await page.request.post(apiUrl(`/student-affairs/discipline/cases/${caseId}/remove-review`), {
        headers: { Authorization: `Bearer ${saAdminToken}` },
        data: { action: 'APPROVE', reason: '', version: 999999 }
      })
      terminalReplayStatus = replay.status()
      expect(replay.ok()).toBeFalsy()
      expect([400, 409]).toContain(replay.status())

      const tenantB = await freshStaffLogin(page, config.demoAdmin)
      const response = await page.request.get(apiUrl(`/student-affairs/discipline/cases/${caseId}`), {
        headers: { Authorization: `Bearer ${tenantB.lastAccessToken}` }
      })
      tenantBDetailStatus = response.status()
      expect(response.ok()).toBeFalsy()
      expect([403, 404]).toContain(response.status())
    })

    expect(api500, 'no unhandled API 5xx during strict discipline journey').toEqual([])
    expect(browserHttpErrors, 'no unexpected browser UI 4xx during strict discipline journey').toEqual([])
    expect(consoleErrors, 'no unexpected browser console errors during strict discipline journey').toEqual([])

    await fs.writeFile(path.resolve('student-affairs-discipline-audit-evidence.json'), JSON.stringify({
      exactHead: process.env.E2E_TARGET_SHA || '',
      prefix, caseId, appealId, initialReason, docNo, appealReason, revisedReason, revisedDocNo,
      reviewOpinion, removeReason, decisionVersion, studentAppealSubmitCount,
      wrongCounselorDetailStatus, wrongCounselorReviewStatus, tenantBDetailStatus, terminalReplayStatus,
      expectedFinalState: 'REMOVED'
    }, null, 2), 'utf8')
  })
})
