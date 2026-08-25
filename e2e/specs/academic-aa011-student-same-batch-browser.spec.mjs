import dns from 'node:dns/promises'
import fs from 'node:fs'
import http from 'node:http'
import net from 'node:net'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { StudentLoginPage } from '../pages/login.page.mjs'

const here = path.dirname(fileURLToPath(import.meta.url))
const fixture = JSON.parse(fs.readFileSync(path.resolve(here, '../academic-b-w5-fixture.json'), 'utf8'))
const staffFixture = JSON.parse(fs.readFileSync(path.resolve(here, '../academic-aa011-staff-browser-fixture.json'), 'utf8'))
const MINIAPP_UPSTREAM = new URL(process.env.E2E_MINIAPP_BASE_URL || 'http://localhost:5188')
const MINIAPP_BASE = 'http://127.0.0.1:5190'

const pcCourse = fixture.courses.find((row) => row.role === 'PC')
const miniCourse = fixture.courses.find((row) => row.role === 'MINIAPP')

function requestSelectionCourseId(response) {
  const body = response.request().postDataJSON()
  return String(body?.selectionCourseId || '')
}

async function screenshot(page, testInfo, name) {
  await page.waitForLoadState('networkidle', { timeout: 5_000 }).catch(() => {})
  await page.evaluate(async () => { if (document.fonts?.ready) await document.fonts.ready })
  const file = testInfo.outputPath(`${name}.png`)
  await page.screenshot({ path: file, fullPage: false, animations: 'disabled', caret: 'hide' })
  await testInfo.attach(name, { path: file, contentType: 'image/png' })
}

function canConnect(host, port) {
  return new Promise((resolve) => {
    const socket = net.createConnection({ host, port })
    const finish = (ok) => {
      socket.removeAllListeners()
      socket.destroy()
      resolve(ok)
    }
    socket.setTimeout(2_000)
    socket.once('connect', () => finish(true))
    socket.once('timeout', () => finish(false))
    socket.once('error', () => finish(false))
  })
}

async function reachableMiniUpstream() {
  const port = Number(MINIAPP_UPSTREAM.port || 80)
  const candidates = await dns.lookup(MINIAPP_UPSTREAM.hostname, { all: true, verbatim: true })
  for (const candidate of candidates) {
    if (await canConnect(candidate.address, port)) {
      return { ...candidate, port }
    }
  }
  throw new Error(`AA-011 Mini upstream is not reachable: ${MINIAPP_UPSTREAM.origin}`)
}

async function startMiniLoopbackBridge() {
  const upstream = await reachableMiniUpstream()
  const server = http.createServer((request, response) => {
    const upstreamRequest = http.request({
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
    upstreamRequest.on('error', (error) => {
      if (!response.headersSent) response.writeHead(502, { 'content-type': 'text/plain; charset=utf-8' })
      response.end(`AA-011 Mini loopback bridge failed: ${error.message}`)
    })
    request.pipe(upstreamRequest)
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

async function miniappLogin(page) {
  await page.goto(`${MINIAPP_BASE}/#/pages/login/student/index`)
  const authCard = page.locator('.auth-card')
  await expect(authCard).toBeVisible({ timeout: 20_000 })
  const fields = authCard.getByRole('textbox')
  await fields.nth(0).fill(config.student.username)
  await fields.nth(1).fill(config.student.password)
  const agreement = authCard.locator('.agreement__box').first()
  await agreement.click()
  await expect(agreement).toHaveClass(/\bon\b/)
  const loginResponse = page.waitForResponse((response) =>
    response.url().includes('/api/v1/auth/browser-login') && response.request().method() === 'POST'
  )
  await authCard.locator('.account-button').first().click()
  expect((await loginResponse).ok()).toBeTruthy()
  await page.waitForURL(/pages\/student\/home\/index/, { timeout: 60_000 })
}

async function pcRow(page, batchName, courseName) {
  const batch = page.locator('.batch-card').filter({ hasText: batchName }).first()
  await expect(batch).toBeVisible({ timeout: 20_000 })
  const row = batch.locator('tr').filter({ hasText: courseName }).first()
  await expect(row).toBeVisible({ timeout: 20_000 })
  return row
}

async function miniCard(page, batchName, courseName) {
  const group = page.locator('.sl__group').filter({ hasText: batchName }).first()
  await expect(group).toBeVisible({ timeout: 20_000 })
  const card = group.locator('.sl__course').filter({ hasText: courseName }).first()
  await expect(card).toBeVisible({ timeout: 20_000 })
  return card
}

test('AA-011 same Staff-created batch survives Student PC -> Mini -> Student PC relogin', async ({ browser }, testInfo) => {
  expect(pcCourse, 'AA-011 seed must expose the PC READY teaching task').toBeTruthy()
  expect(miniCourse, 'AA-011 seed must expose the Mini READY teaching task').toBeTruthy()
  expect(staffFixture.batchId, 'Staff browser step must hand off its exact batchId').toBeTruthy()
  expect(staffFixture.batchName, 'Staff browser step must hand off its exact batchName').toBeTruthy()
  expect(String(staffFixture.termId)).toBe(String(fixture.termId))
  expect(staffFixture.pcSelectionCourseId).toBeTruthy()
  expect(staffFixture.miniSelectionCourseId).toBeTruthy()

  const pcContext = await browser.newContext({ viewport: { width: 1440, height: 900 } })
  const pc = await pcContext.newPage()
  const pcLogin = new StudentLoginPage(pc, config.studentBaseUrl)
  await pcLogin.login(config.student)
  await pc.goto(`${config.studentBaseUrl}/academic/selection`)

  const pcEligible = await pcRow(pc, staffFixture.batchName, pcCourse.courseName)
  await expect(pcEligible.getByRole('button', { name: '立即选课', exact: true })).toBeVisible()
  await screenshot(pc, testInfo, 'aa011-same-batch-pc-before-select-1440x900')

  const pcPreflightPromise = pc.waitForResponse((response) =>
    response.url().includes('/portal/academic/course-selection/preflight') && response.request().method() === 'POST'
  )
  const pcEnrollPromise = pc.waitForResponse((response) =>
    response.url().includes('/portal/academic/course-selection/enroll') && response.request().method() === 'POST'
  )
  await pcEligible.getByRole('button', { name: '立即选课', exact: true }).click()
  const pcPreflight = await pcPreflightPromise
  const pcEnroll = await pcEnrollPromise
  expect(pcPreflight.ok()).toBeTruthy()
  expect(pcEnroll.ok()).toBeTruthy()
  expect(requestSelectionCourseId(pcPreflight)).toBe(String(staffFixture.pcSelectionCourseId))
  expect(requestSelectionCourseId(pcEnroll)).toBe(String(staffFixture.pcSelectionCourseId))

  const pcSelected = await pcRow(pc, staffFixture.batchName, pcCourse.courseName)
  await expect(pcSelected).toContainText('已选')
  await expect(pcSelected.getByRole('button', { name: '退课', exact: true })).toBeVisible()
  await pc.reload()
  const pcAfterRefresh = await pcRow(pc, staffFixture.batchName, pcCourse.courseName)
  await expect(pcAfterRefresh.getByRole('button', { name: '退课', exact: true })).toBeVisible()
  await pcContext.close()

  const miniBridge = await startMiniLoopbackBridge()
  try {
    const miniContext = await browser.newContext({ viewport: { width: 390, height: 844 } })
    const mini = await miniContext.newPage()
    await miniappLogin(mini)
    await mini.goto(`${MINIAPP_BASE}/#/pages/student/academic-affairs/selection`)

    const crossEnd = await miniCard(mini, staffFixture.batchName, pcCourse.courseName)
    await expect(crossEnd).toContainText('已选')
    await expect(crossEnd.locator('.sl__btn')).toHaveText('退课')
    await screenshot(mini, testInfo, 'aa011-same-batch-mini-sees-pc-selected-390x844')

    const miniEligible = await miniCard(mini, staffFixture.batchName, miniCourse.courseName)
    await expect(miniEligible.locator('.sl__btn')).toHaveText('选课')
    const miniPreflightPromise = mini.waitForResponse((response) =>
      response.url().includes('/api/v1/mobile/academic/selection/preflight') && response.request().method() === 'POST'
    )
    const miniEnrollPromise = mini.waitForResponse((response) =>
      response.url().includes('/api/v1/mobile/academic/selection/enroll') && response.request().method() === 'POST'
    )
    await miniEligible.locator('.sl__btn').click()
    const miniPreflight = await miniPreflightPromise
    const miniEnroll = await miniEnrollPromise
    expect(miniPreflight.ok()).toBeTruthy()
    expect(miniEnroll.ok()).toBeTruthy()
    expect(requestSelectionCourseId(miniPreflight)).toBe(String(staffFixture.miniSelectionCourseId))
    expect(requestSelectionCourseId(miniEnroll)).toBe(String(staffFixture.miniSelectionCourseId))

    const miniSelected = await miniCard(mini, staffFixture.batchName, miniCourse.courseName)
    await expect(miniSelected).toContainText('已选')
    await expect(miniSelected.locator('.sl__btn')).toHaveText('退课')

    const miniDropCard = await miniCard(mini, staffFixture.batchName, pcCourse.courseName)
    const miniDropPromise = mini.waitForResponse((response) =>
      response.url().includes('/api/v1/mobile/academic/selection/drop') && response.request().method() === 'POST'
    )
    await miniDropCard.locator('.sl__btn').click()
    const miniDrop = await miniDropPromise
    expect(miniDrop.ok()).toBeTruthy()
    expect(requestSelectionCourseId(miniDrop)).toBe(String(staffFixture.pcSelectionCourseId))

    const miniDropped = await miniCard(mini, staffFixture.batchName, pcCourse.courseName)
    await expect(miniDropped).toContainText('已退课')
    await expect(miniDropped.locator('.sl__btn')).toHaveText('选课')
    await mini.reload()
    const miniPersisted = await miniCard(mini, staffFixture.batchName, miniCourse.courseName)
    await expect(miniPersisted.locator('.sl__btn')).toHaveText('退课')
    await miniContext.close()
  } finally {
    await closeServer(miniBridge)
  }

  const reloginContext = await browser.newContext({ viewport: { width: 1280, height: 720 } })
  const relogin = await reloginContext.newPage()
  const reloginPage = new StudentLoginPage(relogin, config.studentBaseUrl)
  await reloginPage.login(config.student)
  await relogin.goto(`${config.studentBaseUrl}/academic/selection`)

  const miniCourseOnPc = await pcRow(relogin, staffFixture.batchName, miniCourse.courseName)
  await expect(miniCourseOnPc).toContainText('已选')
  await expect(miniCourseOnPc.getByRole('button', { name: '退课', exact: true })).toBeVisible()
  const droppedOnPc = await pcRow(relogin, staffFixture.batchName, pcCourse.courseName)
  await expect(droppedOnPc).toContainText('已退课')
  await expect(droppedOnPc.getByRole('button', { name: '立即选课', exact: true })).toBeVisible()
  await screenshot(relogin, testInfo, 'aa011-same-batch-pc-relogin-final-1280x720')
  await reloginContext.close()

  fs.writeFileSync(path.resolve(here, '../academic-aa011-student-browser-outcome.json'), JSON.stringify({
    batchId: String(staffFixture.batchId),
    batchName: staffFixture.batchName,
    termId: String(staffFixture.termId),
    studentNo: fixture.mainStudentNo,
    pcSelectionCourseId: String(staffFixture.pcSelectionCourseId),
    pcFinalStatus: 'DROPPED',
    miniSelectionCourseId: String(staffFixture.miniSelectionCourseId),
    miniFinalStatus: 'SELECTED',
  }, null, 2))
})