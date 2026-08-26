import dns from 'node:dns/promises'
import fs from 'node:fs'
import http from 'node:http'
import net from 'node:net'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { StaffLoginPage, StudentLoginPage } from '../pages/login.page.mjs'

const here = path.dirname(fileURLToPath(import.meta.url))
const repoRoot = path.resolve(here, '../..')
const statePath = path.join(repoRoot, 'backend/tmp/e2e_academic_aa003_state.local.json')
const outcomePath = path.resolve(here, '../academic-aa003-browser-outcome.json')
const MINIAPP_UPSTREAM = new URL(process.env.E2E_MINIAPP_BASE_URL || 'http://localhost:5188')
const MINIAPP_BASE = 'http://127.0.0.1:5190'

const originalReason = 'AA-003浏览器真实休学申请初次事由'
const returnReason = 'AA-003材料需要补充后重新提交'
const modifiedReason = 'AA-003补充材料后修改事由并重交原申请'
const counselorAccount = {
  tenant: config.mentor.tenant,
  username: 'aa003_counselor',
  password: config.mentor.password,
  role: 'COUNSELOR',
}
const collegeAccount = {
  tenant: config.multiRole.tenant,
  username: 'aa003_college_admin',
  password: config.multiRole.password,
  role: 'COLLEGE_ADMIN',
}
const secondStudent = {
  tenant: config.student.tenant,
  username: 'E2E20260002',
  password: config.student.password,
}

function fixture() {
  return JSON.parse(fs.readFileSync(statePath, 'utf8'))
}

async function screenshot(page, testInfo, name) {
  await page.waitForLoadState('networkidle', { timeout: 4_000 }).catch(() => {})
  const file = testInfo.outputPath(`${name}.png`)
  await page.screenshot({ path: file, fullPage: false, animations: 'disabled', caret: 'hide' })
  await testInfo.attach(name, { path: file, contentType: 'image/png' })
}

function canConnect(host, port) {
  return new Promise((resolve) => {
    const socket = net.createConnection({ host, port })
    const done = (ok) => {
      socket.removeAllListeners()
      socket.destroy()
      resolve(ok)
    }
    socket.setTimeout(2_000)
    socket.once('connect', () => done(true))
    socket.once('timeout', () => done(false))
    socket.once('error', () => done(false))
  })
}

async function startMiniLoopbackBridge() {
  const port = Number(MINIAPP_UPSTREAM.port || 80)
  const candidates = await dns.lookup(MINIAPP_UPSTREAM.hostname, { all: true, verbatim: true })
  let upstream = null
  for (const candidate of candidates) {
    if (await canConnect(candidate.address, port)) {
      upstream = { ...candidate, port }
      break
    }
  }
  if (!upstream) throw new Error(`AA-003 Mini upstream is not reachable: ${MINIAPP_UPSTREAM.origin}`)

  const server = http.createServer((request, response) => {
    const proxy = http.request({
      protocol: MINIAPP_UPSTREAM.protocol,
      hostname: upstream.address,
      family: upstream.family,
      port: upstream.port,
      method: request.method,
      path: request.url,
      headers: { ...request.headers, host: MINIAPP_UPSTREAM.host },
    }, (upstreamResponse) => {
      response.writeHead(upstreamResponse.statusCode || 502, upstreamResponse.headers)
      upstreamResponse.pipe(response)
    })
    proxy.on('error', (error) => {
      if (!response.headersSent) response.writeHead(502, { 'content-type': 'text/plain; charset=utf-8' })
      response.end(`AA-003 Mini loopback bridge failed: ${error.message}`)
    })
    request.pipe(proxy)
  })
  await new Promise((resolve, reject) => {
    server.once('error', reject)
    server.listen(5190, '127.0.0.1', () => {
      server.removeListener('error', reject)
      resolve()
    })
  })
  return server
}

async function closeServer(server) {
  if (!server) return
  await new Promise((resolve) => server.close(resolve))
}

async function loginTeacherMini(page, account) {
  await page.goto(`${MINIAPP_BASE}/#/pages/login/teacher/index`)
  const fields = page.getByRole('textbox')
  await fields.nth(0).fill(account.username)
  await fields.nth(1).fill(account.password)
  await page.getByText('填写', { exact: true }).click()
  await fields.nth(2).fill(account.tenant)
  await page.getByText('我已阅读并同意学校提供的', { exact: false }).click()
  const loginResponsePromise = page.waitForResponse((response) =>
    response.url().includes('/api/v1/auth/browser-login') && response.request().method() === 'POST'
  )
  await page.getByText('进入教师工作台', { exact: true }).click()
  const loginResponse = await loginResponsePromise
  const loginPayload = await loginResponse.json()
  expect(loginResponse.ok(), JSON.stringify(loginPayload)).toBeTruthy()
  expect(loginPayload.code, JSON.stringify(loginPayload)).toBe(0)
  expect(loginPayload?.data?.currentRole?.roleCode).toBe(account.role)
  await expect(page).toHaveURL(/pages\/teacher\/workbench\/index/, { timeout: 30_000 })
}

async function loginStudentMini(page) {
  await page.goto(`${MINIAPP_BASE}/#/pages/login/student/index`)
  const authCard = page.locator('.auth-card')
  await expect(authCard).toBeVisible({ timeout: 20_000 })
  const fields = authCard.getByRole('textbox')
  await fields.nth(0).fill(config.student.username)
  await fields.nth(1).fill(config.student.password)
  await authCard.locator('.agreement__box').first().click()
  const loginResponse = page.waitForResponse((response) =>
    response.url().includes('/api/v1/auth/browser-login') && response.request().method() === 'POST'
  )
  await authCard.locator('.account-button').first().click()
  const response = await loginResponse
  expect(response.ok(), `student mini login HTTP ${response.status()}`).toBeTruthy()
  await page.waitForURL(/pages\/student\/home\/index/, { timeout: 60_000 })
}

async function apiLogin(request, account, clientType = 'PC') {
  const response = await request.post(`${config.apiBaseUrl}/auth/login`, {
    data: {
      loginName: account.username,
      password: account.password,
      tenantCode: account.tenant,
      clientType,
    },
  })
  const payload = await response.json()
  expect(response.ok(), JSON.stringify(payload)).toBeTruthy()
  expect(payload.code, JSON.stringify(payload)).toBe(0)
  expect(payload?.data?.accessToken).toBeTruthy()
  return payload.data.accessToken
}

async function teacherMiniAction(page, facts, action, reason = '') {
  const reviewUrl = `${MINIAPP_BASE}/#/pages/teacher/academic-affairs/status-change-review`
  if (page.url() === reviewUrl) await page.reload()
  else await page.goto(reviewUrl)
  await expect(page.getByText('学籍异动审批', { exact: true })).toBeVisible({ timeout: 20_000 })
  const card = page.locator('.card.ed').filter({ hasText: facts.studentName }).first()
  await expect(card, `AA-003 ${action} must show target student in Teacher Mini pending list`).toBeVisible({ timeout: 20_000 })
  const buttonLabel = action === 'RETURN' ? '退回' : '通过'
  const responsePromise = page.waitForResponse((response) =>
    response.request().method() === 'POST' &&
    response.url().includes('/api/v1/mobile/teacher/academic/status-changes/') &&
    response.url().endsWith('/review')
  , { timeout: 20_000 })
  await card.getByText(buttonLabel, { exact: true }).click()

  if (action === 'RETURN') {
    const field = page.getByRole('textbox').last()
    await expect(field).toBeVisible({ timeout: 5_000 })
    await field.fill(reason)
  }
  const confirm = page.getByText('确定', { exact: true }).last()
  await expect(confirm).toBeVisible({ timeout: 5_000 })
  await confirm.click()

  const response = await responsePromise
  const payload = await response.json()
  expect(response.ok(), JSON.stringify(payload)).toBeTruthy()
  expect(payload.code, JSON.stringify(payload)).toBe(0)
  return payload.data
}

async function staffApprove(page, account, rolePattern, facts, expectedNode) {
  const login = new StaffLoginPage(page, config.staffBaseUrl)
  await login.login(account)
  if (rolePattern) await login.switchRole(rolePattern)
  await page.goto(`${config.staffBaseUrl}/admin/academic-affairs/status-changes/approval`)
  await expect(page.getByText('异动审批', { exact: true })).toBeVisible({ timeout: 20_000 })
  const row = page.locator('tr').filter({ hasText: facts.studentName }).first()
  await expect(row, `AA-003 Staff PC ${expectedNode} row must be visible`).toBeVisible({ timeout: 20_000 })
  await expect(row).toContainText(expectedNode === 'COLLEGE_REVIEW' ? /学院|COLLEGE/ : /教务处|AA_OFFICE_FINAL/)

  const responsePromise = page.waitForResponse((response) =>
    response.request().method() === 'POST' &&
    response.url().includes('/api/v1/academic-affairs/status-changes/') &&
    response.url().endsWith('/review')
  , { timeout: 20_000 })
  await row.getByText('通过', { exact: true }).click()
  const confirm = page.getByRole('button', { name: '确认通过' })
  await expect(confirm).toBeVisible({ timeout: 5_000 })
  await confirm.click()
  const response = await responsePromise
  const payload = await response.json()
  expect(response.ok(), JSON.stringify(payload)).toBeTruthy()
  expect(payload.code, JSON.stringify(payload)).toBe(0)
  return payload.data
}

test('AA-003 real four-surface RETURN -> same-case resubmit -> effective', async ({ browser, request }, testInfo) => {
  const facts = fixture()
  const miniBridge = await startMiniLoopbackBridge()
  const contexts = []
  const outcome = {
    productSha: process.env.E2E_EXPECTED_SHA || '',
    studentId: facts.studentId,
    initialReason: originalReason,
    returnReason,
    modifiedReason,
  }

  try {
    // 1) Student PC: real wizard submit.
    const studentPcContext = await browser.newContext({ acceptDownloads: true })
    contexts.push(studentPcContext)
    const studentPc = await studentPcContext.newPage()
    const studentLogin = new StudentLoginPage(studentPc, config.studentBaseUrl)
    await studentLogin.login(config.student)
    const studentToken = studentLogin.lastAccessToken
    expect(studentToken).toBeTruthy()
    await studentPc.goto(`${config.studentBaseUrl}/academic/status`)
    await expect(studentPc.getByText('学籍异动申请向导', { exact: true })).toBeVisible({ timeout: 20_000 })
    await studentPc.getByRole('button', { name: /休学/ }).first().click()
    await studentPc.getByRole('button', { name: '下一步' }).click()
    await studentPc.getByPlaceholder('请详细说明申请原因').fill(originalReason)
    await studentPc.getByRole('button', { name: '下一步：预览' }).click()
    const submitResponse = studentPc.waitForResponse((response) =>
      response.request().method() === 'POST' && response.url().endsWith('/api/v1/portal/academic/status-change')
    , { timeout: 20_000 })
    await studentPc.getByRole('button', { name: '提交并下载申请表' }).click()
    const submitted = await submitResponse
    const submitPayload = await submitted.json()
    expect(submitted.ok(), JSON.stringify(submitPayload)).toBeTruthy()
    expect(submitPayload.code, JSON.stringify(submitPayload)).toBe(0)
    const changeId = String(submitPayload?.data?.changeId || '')
    expect(changeId).toMatch(/^\d+$/)
    expect(submitPayload?.data?.status).toBe('SUBMITTED')
    expect(submitPayload?.data?.currentNode).toBe('COUNSELOR_REVIEW')
    outcome.changeId = changeId
    outcome.initialStatus = submitPayload.data.status
    await screenshot(studentPc, testInfo, '01-student-pc-submitted')

    // 2) Teacher Mini: formal COUNSELOR identity uses the real RETURN button.
    const teacherContext = await browser.newContext()
    contexts.push(teacherContext)
    const teacherMini = await teacherContext.newPage()
    await loginTeacherMini(teacherMini, counselorAccount)
    const returned = await teacherMiniAction(teacherMini, facts, 'RETURN', returnReason)
    expect(String(returned?.changeId || '')).toBe(changeId)
    expect(returned?.status).toBe('RETURNED')
    const returnedVersion = Number(returned?.version)
    expect(Number.isInteger(returnedVersion)).toBeTruthy()
    outcome.returnedVersion = returnedVersion
    await screenshot(teacherMini, testInfo, '02-teacher-mini-returned')

    // 3a) Server negative while row is still RETURNED: stale rendered version must be rejected with no mutation.
    const stale = await request.post(`${config.apiBaseUrl}/mobile/academic/status-changes/${changeId}/resubmit`, {
      headers: { Authorization: `Bearer ${studentToken}` },
      data: { reason: modifiedReason, expectedVersion: returnedVersion - 1 },
    })
    const stalePayload = await stale.json()
    expect(stale.status()).toBe(409)
    expect(stalePayload.code, JSON.stringify(stalePayload)).not.toBe(0)
    expect(JSON.stringify(stalePayload)).toContain('APPROVAL_VERSION_CONFLICT')
    outcome.staleVersionRejected = true

    // Wrong student must not be able to reopen the target case.
    const secondToken = await apiLogin(request, secondStudent, 'STUDENT_MINI')
    const wrongStudent = await request.post(`${config.apiBaseUrl}/mobile/academic/status-changes/${changeId}/resubmit`, {
      headers: { Authorization: `Bearer ${secondToken}` },
      data: { reason: modifiedReason, expectedVersion: returnedVersion },
    })
    const wrongPayload = await wrongStudent.json()
    expect([403, 404]).toContain(wrongStudent.status())
    expect(wrongPayload.code, JSON.stringify(wrongPayload)).not.toBe(0)
    outcome.wrongStudentRejected = true

    // 3b) Student Mini: returned card must render the version and send it through the real button.
    const studentMiniContext = await browser.newContext()
    contexts.push(studentMiniContext)
    const studentMini = await studentMiniContext.newPage()
    await loginStudentMini(studentMini)
    const statusResponsePromise = studentMini.waitForResponse((response) =>
      response.request().method() === 'GET' && response.url().endsWith('/api/v1/mobile/academic/status/my')
    , { timeout: 20_000 })
    await studentMini.goto(`${MINIAPP_BASE}/#/pages/student/academic-affairs/status`)
    const statusResponse = await statusResponsePromise
    const statusPayload = await statusResponse.json()
    expect(statusResponse.ok(), JSON.stringify(statusPayload)).toBeTruthy()
    const returnedRow = (statusPayload?.data?.changes || []).find((row) => String(row.changeId) === changeId)
    expect(returnedRow, 'AA-003 Student Mini status projection must include returned case').toBeTruthy()
    expect(returnedRow.status).toBe('RETURNED')
    expect(Number(returnedRow.version)).toBe(returnedVersion)
    expect(returnedRow.reason).toBe(originalReason)

    const returnedCard = studentMini.locator('.stx__ch').filter({ hasText: '已退回' }).first()
    await expect(returnedCard).toBeVisible({ timeout: 20_000 })
    const reasonBox = returnedCard.locator('textarea.uni-textarea-textarea').first()
    await expect(reasonBox).toHaveValue(originalReason)
    await reasonBox.fill(modifiedReason)
    const resubmitResponsePromise = studentMini.waitForResponse((response) =>
      response.request().method() === 'POST' &&
      response.url().endsWith(`/api/v1/mobile/academic/status-changes/${changeId}/resubmit`)
    , { timeout: 20_000 })
    await returnedCard.getByText('修改并重交原申请', { exact: true }).click()
    const resubmitResponse = await resubmitResponsePromise
    const resubmitRequestBody = resubmitResponse.request().postDataJSON()
    expect(Number(resubmitRequestBody.expectedVersion)).toBe(returnedVersion)
    expect(resubmitRequestBody.reason).toBe(modifiedReason)
    const resubmitPayload = await resubmitResponse.json()
    expect(resubmitResponse.ok(), JSON.stringify(resubmitPayload)).toBeTruthy()
    expect(resubmitPayload.code, JSON.stringify(resubmitPayload)).toBe(0)
    expect(String(resubmitPayload?.data?.changeId || '')).toBe(changeId)
    expect(resubmitPayload?.data?.status).toBe('SUBMITTED')
    expect(resubmitPayload?.data?.currentNode).toBe('COUNSELOR_REVIEW')
    outcome.resubmittedVersion = Number(resubmitPayload?.data?.version)
    outcome.sameChangeIdAfterResubmit = String(resubmitPayload?.data?.changeId || '') === changeId
    await screenshot(studentMini, testInfo, '03-student-mini-resubmitted-same-case')

    // A second resubmit of the same original row must fail, never create a second case/workflow.
    const duplicate = await request.post(`${config.apiBaseUrl}/mobile/academic/status-changes/${changeId}/resubmit`, {
      headers: { Authorization: `Bearer ${studentToken}` },
      data: { reason: `${modifiedReason}重复`, expectedVersion: outcome.resubmittedVersion },
    })
    const duplicatePayload = await duplicate.json()
    expect(duplicate.status()).toBe(409)
    expect(duplicatePayload.code, JSON.stringify(duplicatePayload)).not.toBe(0)
    outcome.duplicateResubmitRejected = true

    // 4) The same formal COUNSELOR sees the reopened original case and approves it.
    const counselorApproved = await teacherMiniAction(teacherMini, facts, 'APPROVE')
    expect(String(counselorApproved?.changeId || '')).toBe(changeId)
    expect(counselorApproved?.status).toBe('IN_REVIEW')
    expect(counselorApproved?.currentNode).toBe('COLLEGE_REVIEW')
    outcome.counselorApproved = true
    await screenshot(teacherMini, testInfo, '04-teacher-mini-approved-resubmitted-case')

    // 5) Staff PC: formal COLLEGE_ADMIN approves the same row.
    const collegeContext = await browser.newContext()
    contexts.push(collegeContext)
    const collegePage = await collegeContext.newPage()
    const collegeApproved = await staffApprove(
      collegePage,
      collegeAccount,
      /学院管理员|COLLEGE_ADMIN/,
      facts,
      'COLLEGE_REVIEW',
    )
    expect(String(collegeApproved?.changeId || '')).toBe(changeId)
    expect(collegeApproved?.status).toBe('IN_REVIEW')
    expect(collegeApproved?.currentNode).toBe('AA_OFFICE_FINAL')
    outcome.collegeApproved = true
    await screenshot(collegePage, testInfo, '05-staff-pc-college-approved')

    // 6) Staff PC: ACADEMIC_ADMIN final approval makes the same case effective atomically.
    const officeContext = await browser.newContext()
    contexts.push(officeContext)
    const officePage = await officeContext.newPage()
    const final = await staffApprove(
      officePage,
      config.multiRole,
      /教务处管理员|教务管理员|教务老师|ACADEMIC_ADMIN/,
      facts,
      'AA_OFFICE_FINAL',
    )
    expect(String(final?.changeId || '')).toBe(changeId)
    expect(final?.status).toBe('EFFECTIVE')
    expect(final?.toStatus).toBe('SUSPENDED')
    outcome.finalStatus = final.status
    await screenshot(officePage, testInfo, '06-staff-pc-office-final-effective')

    // Final student projection: real Student Mini shows the effective academic status and history.
    const finalStatusResponse = studentMini.waitForResponse((response) =>
      response.request().method() === 'GET' && response.url().endsWith('/api/v1/mobile/academic/status/my')
    , { timeout: 20_000 })
    await studentMini.reload()
    const finalStatusPayload = await (await finalStatusResponse).json()
    expect(finalStatusPayload?.data?.studentStatus).toBe('SUSPENDED')
    const finalRow = (finalStatusPayload?.data?.changes || []).find((row) => String(row.changeId) === changeId)
    expect(finalRow?.status).toBe('EFFECTIVE')
    await expect(studentMini.getByText('休学中', { exact: true })).toBeVisible({ timeout: 20_000 })
    await expect(studentMini.getByText('已生效', { exact: true })).toBeVisible({ timeout: 20_000 })
    outcome.studentProjectionStatus = finalStatusPayload.data.studentStatus
    outcome.browserPass = true

    fs.writeFileSync(outcomePath, JSON.stringify(outcome, null, 2), 'utf8')
  } finally {
    for (const context of contexts.reverse()) await context.close().catch(() => {})
    await closeServer(miniBridge)
  }
})