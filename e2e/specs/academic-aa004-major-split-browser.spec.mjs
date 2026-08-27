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
const statePath = path.join(repoRoot, 'backend/tmp/e2e_academic_aa004_state.local.json')
const outcomePath = path.resolve(here, '../academic-aa004-browser-outcome.json')
const MINIAPP_UPSTREAM = new URL(process.env.E2E_MINIAPP_BASE_URL || 'http://localhost:5188')
const MINIAPP_BASE = 'http://127.0.0.1:5190'

function fixture() { return JSON.parse(fs.readFileSync(statePath, 'utf8')) }

async function screenshot(page, testInfo, name) {
  await page.waitForLoadState('networkidle', { timeout: 4000 }).catch(() => {})
  const file = testInfo.outputPath(`${name}.png`)
  await page.screenshot({ path: file, fullPage: false, animations: 'disabled', caret: 'hide' })
  await testInfo.attach(name, { path: file, contentType: 'image/png' })
}

function canConnect(host, port) {
  return new Promise((resolve) => {
    const socket = net.createConnection({ host, port })
    const done = (ok) => { socket.removeAllListeners(); socket.destroy(); resolve(ok) }
    socket.setTimeout(2000)
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
    if (await canConnect(candidate.address, port)) { upstream = { ...candidate, port }; break }
  }
  if (!upstream) throw new Error(`AA-004 Mini upstream is not reachable: ${MINIAPP_UPSTREAM.origin}`)
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
      response.end(`AA-004 Mini loopback bridge failed: ${error.message}`)
    })
    request.pipe(proxy)
  })
  await new Promise((resolve, reject) => {
    server.once('error', reject)
    server.listen(5190, '127.0.0.1', () => { server.removeListener('error', reject); resolve() })
  })
  return server
}

async function closeServer(server) {
  if (!server) return
  await new Promise((resolve) => server.close(resolve))
}

async function loginStudentMini(page) {
  await page.goto(`${MINIAPP_BASE}/#/pages/login/student/index`)
  const authCard = page.locator('.auth-card')
  await expect(authCard).toBeVisible({ timeout: 20000 })
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
  await page.waitForURL(/pages\/student\/home\/index/, { timeout: 60000 })
}

async function browserApi(page, token, method, requestPath, body) {
  return page.evaluate(async ({ apiBaseUrl, tokenValue, requestMethod, pathValue, requestBody }) => {
    const response = await fetch(`${apiBaseUrl}${pathValue}`, {
      method: requestMethod,
      headers: {
        Accept: 'application/json',
        Authorization: `Bearer ${tokenValue}`,
        ...(requestBody === undefined ? {} : { 'Content-Type': 'application/json' }),
      },
      body: requestBody === undefined ? undefined : JSON.stringify(requestBody),
    })
    const text = await response.text()
    let json = null
    try { json = JSON.parse(text) } catch { json = { message: text.slice(0, 500) } }
    return { status: response.status, json }
  }, { apiBaseUrl: config.apiBaseUrl, tokenValue: token, requestMethod: method, pathValue: requestPath, requestBody: body })
}

function expectApiOk(result, label) {
  expect(result.status, `${label}: ${JSON.stringify(result.json)}`).toBe(200)
  expect(result.json?.code, `${label}: ${JSON.stringify(result.json)}`).toBe(0)
  return result.json.data
}

async function confirmDialog(page) {
  const confirm = page.getByRole('button', { name: '确认', exact: true }).last()
  await expect(confirm).toBeVisible({ timeout: 5000 })
  await confirm.click()
}

function waitForMajorSplitDetailRefresh(page, batchId) {
  return Promise.all([
    page.waitForResponse((response) =>
      response.request().method() === 'GET' && response.url().includes(`/api/v1/academic-affairs/major-split/batches/${batchId}/options`)
    , { timeout: 20000 }),
    page.waitForResponse((response) =>
      response.request().method() === 'GET' && response.url().includes(`/api/v1/academic-affairs/major-split/batches/${batchId}/volunteers`)
    , { timeout: 20000 }),
  ])
}

test('AA-004 Student PC submit -> Student Mini update -> Staff PC allocate/confirm -> cross-surface result', async ({ browser, request }, testInfo) => {
  const facts = fixture()
  const miniBridge = await startMiniLoopbackBridge()
  const contexts = []
  const outcome = {
    productSha: process.env.E2E_EXPECTED_SHA || '',
    studentId: facts.studentId,
    sourceMajorId: facts.sourceMajorId,
    targetMajorAId: facts.targetMajorAId,
    targetMajorBId: facts.targetMajorBId,
  }
  try {
    // Staff PC creates the real batch; options/open are canonical API preconditions through the same authenticated browser session.
    const staffContext = await browser.newContext()
    contexts.push(staffContext)
    const staff = await staffContext.newPage()
    const staffLogin = new StaffLoginPage(staff, config.staffBaseUrl)
    await staffLogin.login(config.multiRole)
    await staffLogin.switchRole(/教务处管理员|教务管理员|教务老师|ACADEMIC_ADMIN/)
    const staffToken = await staffLogin.token()
    await staff.goto(`${config.staffBaseUrl}/admin/academic-affairs/major-split`)
    await expect(staff.getByText('专业分流 · 教务处控制台', { exact: true })).toBeVisible({ timeout: 20000 })

    const suffix = `${Date.now()}`.slice(-8)
    const batchName = `AA-004专业分流-${suffix}`
    await staff.getByRole('button', { name: '新建分流批次' }).click()
    await staff.getByPlaceholder('如 2024级电子信息大类分流').fill(batchName)
    await staff.getByPlaceholder('如 2024', { exact: true }).fill(facts.grade)
    const createResponsePromise = staff.waitForResponse((response) =>
      response.request().method() === 'POST' && response.url().endsWith('/api/v1/academic-affairs/major-split/batches')
    , { timeout: 20000 })
    await staff.getByRole('button', { name: '创建', exact: true }).click()
    const createResponse = await createResponsePromise
    const createPayload = await createResponse.json()
    expect(createResponse.ok(), JSON.stringify(createPayload)).toBeTruthy()
    expect(createPayload.code, JSON.stringify(createPayload)).toBe(0)
    const batchId = String(createPayload?.data?.batchId || '')
    expect(batchId).toMatch(/^\d+$/)
    outcome.batchId = batchId
    outcome.batchName = batchName

    expectApiOk(await browserApi(staff, staffToken, 'POST', `/academic-affairs/major-split/batches/${batchId}/options`, {
      majorId: facts.targetMajorAId, capacity: 1,
    }), 'add target major A')
    expectApiOk(await browserApi(staff, staffToken, 'POST', `/academic-affairs/major-split/batches/${batchId}/options`, {
      majorId: facts.targetMajorBId, capacity: 1,
    }), 'add target major B')
    expectApiOk(await browserApi(staff, staffToken, 'POST', `/academic-affairs/major-split/batches/${batchId}/open`), 'open split batch')
    await staff.reload()
    await expect(staff.getByText(batchName, { exact: true })).toBeVisible({ timeout: 20000 })
    await screenshot(staff, testInfo, '01-staff-pc-open-batch')

    // Student PC uses the real page and real submit button for first choice A.
    const studentPcContext = await browser.newContext()
    contexts.push(studentPcContext)
    const studentPc = await studentPcContext.newPage()
    const studentLogin = new StudentLoginPage(studentPc, config.studentBaseUrl)
    await studentLogin.login(config.student)
    const studentToken = studentLogin.lastAccessToken
    expect(studentToken).toBeTruthy()
    await studentPc.goto(`${config.studentBaseUrl}/academic/major-split`)
    await expect(studentPc.getByRole('heading', { name: '专业分流志愿' })).toBeVisible({ timeout: 20000 })
    const pcBatch = studentPc.locator('.batch-card').filter({ hasText: batchName }).first()
    await expect(pcBatch).toBeVisible({ timeout: 20000 })
    await pcBatch.getByText(facts.targetMajorAName, { exact: true }).click()
    const pcSubmitPromise = studentPc.waitForResponse((response) =>
      response.request().method() === 'POST' && response.url().endsWith('/api/v1/portal/academic/major-split/submit')
    , { timeout: 20000 })
    await pcBatch.getByRole('button', { name: '提交志愿' }).click()
    const pcSubmit = await pcSubmitPromise
    const pcPayload = await pcSubmit.json()
    expect(pcSubmit.ok(), JSON.stringify(pcPayload)).toBeTruthy()
    expect(pcPayload.code, JSON.stringify(pcPayload)).toBe(0)
    const volunteerId = String(pcPayload?.data?.volunteerId || '')
    expect(volunteerId).toMatch(/^\d+$/)
    outcome.volunteerId = volunteerId
    outcome.studentPcSubmitted = true
    await screenshot(studentPc, testInfo, '02-student-pc-submitted-choice-a')

    // Student token must be forbidden from the staff management endpoint.
    const forbidden = await request.post(`${config.apiBaseUrl}/academic-affairs/major-split/batches`, {
      headers: { Authorization: `Bearer ${studentToken}` },
      data: { batchName: 'AA-004越权批次', grade: facts.grade, maxChoices: 1 },
    })
    expect(forbidden.status()).toBe(403)
    outcome.studentManageForbidden = true

    // Student Mini reopens the same volunteer and changes it to choice B through the real mobile page.
    const studentMiniContext = await browser.newContext()
    contexts.push(studentMiniContext)
    const studentMini = await studentMiniContext.newPage()
    await loginStudentMini(studentMini)
    await studentMini.goto(`${MINIAPP_BASE}/#/pages/student/academic-affairs/major-split`)
    await expect(studentMini.getByText(batchName, { exact: true })).toBeVisible({ timeout: 20000 })
    const miniBatch = studentMini.locator('.ms__batch').filter({ hasText: batchName }).first()
    const miniChoiceA = miniBatch.locator('.ms__opt').filter({ hasText: facts.targetMajorAName }).first()
    const miniChoiceB = miniBatch.locator('.ms__opt').filter({ hasText: facts.targetMajorBName }).first()
    const miniSubmitButton = miniBatch.locator('.btn-primary').first()
    await expect(miniChoiceA).toHaveClass(/is-picked/)
    await expect(miniChoiceB).not.toHaveClass(/is-picked/)
    await expect(miniSubmitButton).toContainText('更新志愿')
    await miniChoiceA.click()
    await expect(miniChoiceA).not.toHaveClass(/is-picked/)
    await miniChoiceB.click()
    await expect(miniChoiceB).toHaveClass(/is-picked/)
    const miniSubmitPromise = studentMini.waitForResponse((response) =>
      response.request().method() === 'POST' && response.url().includes('/api/v1/mobile/academic/major-split')
    , { timeout: 20000 })
    await miniSubmitButton.click()
    const miniSubmit = await miniSubmitPromise
    const miniPayload = await miniSubmit.json()
    expect(miniSubmit.ok(), JSON.stringify(miniPayload)).toBeTruthy()
    expect(miniPayload.code, JSON.stringify(miniPayload)).toBe(0)
    expect(String(miniPayload?.data?.volunteerId || '')).toBe(volunteerId)
    outcome.studentMiniUpdated = true
    await screenshot(studentMini, testInfo, '03-student-mini-updated-choice-b')

    // Staff PC uses real workflow buttons to close, allocate, and confirm the same batch.
    await staff.reload()
    const batchRow = staff.locator('.aams-batch').filter({ hasText: batchName }).first()
    await expect(batchRow).toBeVisible({ timeout: 20000 })
    await batchRow.click()
    await expect(staff.getByText(facts.studentName, { exact: false }).first()).toBeVisible({ timeout: 20000 })

    const closeRefreshPromise = waitForMajorSplitDetailRefresh(staff, batchId)
    const closePromise = staff.waitForResponse((response) =>
      response.request().method() === 'POST' && response.url().endsWith(`/api/v1/academic-affairs/major-split/batches/${batchId}/close`)
    , { timeout: 20000 })
    await staff.getByRole('button', { name: '截止', exact: true }).click()
    await confirmDialog(staff)
    const closeResponse = await closePromise
    expect(closeResponse.ok()).toBeTruthy()
    const closeRefreshResponses = await closeRefreshPromise
    expect(closeRefreshResponses.every((response) => response.ok())).toBeTruthy()
    await expect(staff.locator('.aams-batch').filter({ hasText: batchName }).first()).toContainText('已截止')

    const allocateRefreshPromise = waitForMajorSplitDetailRefresh(staff, batchId)
    const allocatePromise = staff.waitForResponse((response) =>
      response.request().method() === 'POST' && response.url().includes(`/api/v1/academic-affairs/major-split/batches/${batchId}/allocate`)
    , { timeout: 20000 })
    const allocateButton = staff.getByRole('button', { name: '自动分配', exact: true })
    await expect(allocateButton).toBeVisible({ timeout: 20000 })
    await allocateButton.hover()
    const allocateBox = await allocateButton.boundingBox()
    expect(allocateBox).toBeTruthy()
    await staff.mouse.click(allocateBox.x + allocateBox.width / 2, allocateBox.y + allocateBox.height / 2)
    await confirmDialog(staff)
    const allocateResponse = await allocatePromise
    const allocatePayload = await allocateResponse.json()
    expect(allocateResponse.ok(), JSON.stringify(allocatePayload)).toBeTruthy()
    expect(allocatePayload?.data?.allocated).toBe(1)
    expect(allocatePayload?.data?.unallocated).toBe(0)
    const allocateRefreshResponses = await allocateRefreshPromise
    expect(allocateRefreshResponses.every((response) => response.ok())).toBeTruthy()
    await expect(staff.locator('.aams-batch').filter({ hasText: batchName }).first()).toContainText('已分配')

    const confirmPromise = staff.waitForResponse((response) =>
      response.request().method() === 'POST' && response.url().endsWith(`/api/v1/academic-affairs/major-split/batches/${batchId}/confirm`)
    , { timeout: 20000 })
    await staff.getByRole('button', { name: '确认分流', exact: true }).click()
    await confirmDialog(staff)
    const confirmResponse = await confirmPromise
    const confirmPayload = await confirmResponse.json()
    expect(confirmResponse.ok(), JSON.stringify(confirmPayload)).toBeTruthy()
    expect(confirmPayload?.data?.confirmed).toBe(1)
    expect(confirmPayload?.data?.status).toBe('CONFIRMED')
    outcome.staffConfirmed = true
    await screenshot(staff, testInfo, '04-staff-pc-confirmed')

    // Final Student PC projection must show the server-confirmed result for the same volunteer.
    const finalPcPromise = studentPc.waitForResponse((response) =>
      response.request().method() === 'GET' && response.url().endsWith('/api/v1/portal/academic/major-split')
    , { timeout: 20000 })
    await studentPc.reload()
    const finalPcPayload = await (await finalPcPromise).json()
    expect(finalPcPayload.code, JSON.stringify(finalPcPayload)).toBe(0)
    const finalPcRow = (finalPcPayload?.data?.myVolunteers || []).find((row) => String(row.volunteerId) === volunteerId)
    expect(finalPcRow).toBeTruthy()
    expect(String(finalPcRow.resultMajorId)).toBe(String(facts.targetMajorBId))
    expect(finalPcRow.status).toBe('CONFIRMED')
    await expect(studentPc.getByText('我的志愿与学校结果', { exact: true })).toBeVisible({ timeout: 20000 })
    outcome.studentFinalProjection = true
    await screenshot(studentPc, testInfo, '05-student-pc-final-result')

    // Student Mini independently reads the same confirmed row after the batch is closed.
    const finalMiniPromise = studentMini.waitForResponse((response) =>
      response.request().method() === 'GET' && response.url().includes('/api/v1/mobile/academic/major-split')
    , { timeout: 20000 })
    await studentMini.reload()
    const finalMiniPayload = await (await finalMiniPromise).json()
    expect(finalMiniPayload.code, JSON.stringify(finalMiniPayload)).toBe(0)
    const finalMiniRow = (finalMiniPayload?.data?.myVolunteers || []).find((row) => String(row.volunteerId) === volunteerId)
    expect(finalMiniRow).toBeTruthy()
    expect(String(finalMiniRow.resultMajorId)).toBe(String(facts.targetMajorBId))
    expect(finalMiniRow.status).toBe('CONFIRMED')
    outcome.studentMiniFinalProjection = true
    await screenshot(studentMini, testInfo, '06-student-mini-final-result')

    fs.writeFileSync(outcomePath, JSON.stringify(outcome, null, 2), 'utf8')
  } finally {
    for (const context of contexts.reverse()) await context.close().catch(() => {})
    await closeServer(miniBridge)
  }
})
