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
const statePath = path.join(repoRoot, 'backend/tmp/e2e_academic_c_teacher_today_state.local.json')
const outcomePath = path.resolve(here, '../academic-aa010-browser-outcome.json')
const MINIAPP_UPSTREAM = new URL(process.env.E2E_MINIAPP_BASE_URL || 'http://localhost:5188')
const MINIAPP_BASE = 'http://127.0.0.1:5190'
const closeNote = 'AA-010真实课堂缺勤已完成教师跟进闭环'

function fixture() {
  return JSON.parse(fs.readFileSync(statePath, 'utf8'))
}

function dateMinus(iso, days) {
  const d = new Date(`${iso}T12:00:00Z`)
  d.setUTCDate(d.getUTCDate() - days)
  return d.toISOString().slice(0, 10)
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

async function reachableMiniUpstream() {
  const port = Number(MINIAPP_UPSTREAM.port || 80)
  const candidates = await dns.lookup(MINIAPP_UPSTREAM.hostname, { all: true, verbatim: true })
  for (const candidate of candidates) {
    if (await canConnect(candidate.address, port)) return { ...candidate, port }
  }
  throw new Error(`AA-010 Mini upstream is not reachable: ${MINIAPP_UPSTREAM.origin}`)
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
      response.end(`AA-010 Mini loopback bridge failed: ${error.message}`)
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

async function loginTeacherMini(page, account = config.mentor) {
  await page.goto(`${MINIAPP_BASE}/#/pages/login/teacher/index`)
  const fields = page.getByRole('textbox')
  await fields.nth(0).fill(account.username)
  await fields.nth(1).fill(account.password)
  await page.getByText('填写', { exact: true }).click()
  await fields.nth(2).fill(account.tenant)
  await page.getByText('我已阅读并同意学校提供的', { exact: false }).click()
  await page.getByText('进入教师工作台', { exact: true }).click()
  await expect(page).toHaveURL(/pages\/teacher\/workbench\/index/, { timeout: 20_000 })
}

async function clearMiniSession(page) {
  const browserSession = await page.evaluate(() => ({
    channel: String(sessionStorage.getItem('gx_h5_browser_channel_v1') || ''),
    sessionId: String(sessionStorage.getItem('gx_h5_browser_session_id_v1') || '')
  }))
  if (browserSession.channel && browserSession.sessionId) {
    const logout = await page.context().request.post(`${config.apiBaseUrl}/auth/browser-logout`, {
      headers: {
        'X-Browser-Session': browserSession.channel,
        'X-Browser-Session-Id': browserSession.sessionId
      }
    })
    expect(logout.ok(), `H5 browser logout HTTP ${logout.status()}`).toBeTruthy()
  }
  await page.context().clearCookies()
  await page.goto('about:blank')
}

async function loginStudentMini(page) {
  await page.goto(`${MINIAPP_BASE}/#/pages/login/student/index`)
  const authCard = page.locator('.auth-card')
  await expect(authCard).toBeVisible({ timeout: 20_000 })
  const fields = authCard.getByRole('textbox')
  await fields.nth(0).fill(config.student.username)
  await fields.nth(1).fill(config.student.password)
  const agreement = authCard.locator('.agreement__box').first()
  await agreement.click()
  const write = page.waitForResponse((response) =>
    response.url().includes('/api/v1/auth/browser-login') && response.request().method() === 'POST'
  )
  await authCard.locator('.account-button').first().click()
  expect((await write).ok()).toBeTruthy()
  await page.waitForURL(/pages\/student\/home\/index/, { timeout: 60_000 })
}

async function dismissGuide(page) {
  const mask = page.locator('.app-step-guide__mask')
  await mask.waitFor({ state: 'visible', timeout: 1_500 }).catch(() => {})
  if (await mask.isVisible().catch(() => false)) {
    const skip = page.getByRole('button', { name: '跳过引导' })
    if (await skip.count()) await skip.click()
  }
}

async function loginAcademicAdmin(page) {
  const login = new StaffLoginPage(page, config.staffBaseUrl)
  await login.login(config.multiRole)
  await login.switchRole(/教务处管理员|教务管理员|教务老师|ACADEMIC_ADMIN/)
}

async function createSessionFromSeed(page, f, sessionDate, { fromToday = false } = {}) {
  if (fromToday) {
    await page.goto(`${MINIAPP_BASE}/#/pages/teacher/academic-affairs/index`)
    const todayCard = page.locator('.ta__course').filter({ hasText: f.courseName }).first()
    await expect(todayCard).toBeVisible({ timeout: 20_000 })
    await expect(todayCard).toContainText('已调课')
    await expect(todayCard).toContainText('去点名')
    await todayCard.click()
    await expect(page).toHaveURL(new RegExp(
      `pages/teacher/academic-affairs/attendance\\?teachingTaskId=${f.teachingTaskId}`
    ), { timeout: 10_000 })
    expect(page.url()).toContain(`sessionDate=${sessionDate}`)
    expect(page.url()).toContain(`scheduleItemId=${f.scheduleItemId}`)
  } else {
    const url = `${MINIAPP_BASE}/#/pages/teacher/academic-affairs/attendance` +
      `?teachingTaskId=${f.teachingTaskId}&sessionDate=${sessionDate}` +
      `&slotNo=${f.slotNo}&scheduleItemId=${f.scheduleItemId}`
    await page.goto(url)
  }

  const createButton = page.getByText('按教学任务圈定名单并新建', { exact: true })
  await expect(createButton).toBeEnabled({ timeout: 20_000 })
  const write = page.waitForResponse((response) => {
    const url = new URL(response.url())
    return response.request().method() === 'POST' &&
      url.pathname.endsWith('/api/v1/mobile/teacher/academic/attendance/sessions')
  }, { timeout: 20_000 })
  await createButton.click()
  const response = await write
  const payload = await response.json()
  expect(response.ok(), JSON.stringify(payload)).toBeTruthy()
  expect(payload.code, JSON.stringify(payload)).toBe(0)
  const sessionId = String(payload?.data?.sessionId || '')
  expect(sessionId).toMatch(/^\d+$/)
  expect(String(payload?.data?.teachingTaskId || '')).toBe(String(f.teachingTaskId))
  expect(payload?.data?.sourceType).toBe('FORMAL_TEACHING')
  await expect(page.getByText('考勤详情', { exact: true })).toBeVisible({ timeout: 10_000 })
  return sessionId
}

async function markStatus(page, sessionId, f, statusText) {
  const row = page.locator('.at__row').filter({ hasText: f.studentName }).first()
  await expect(row).toBeVisible({ timeout: 10_000 })
  const write = page.waitForResponse((response) => {
    const url = new URL(response.url())
    return response.request().method() === 'POST' &&
      url.pathname.endsWith(`/api/v1/mobile/teacher/academic/attendance/sessions/${sessionId}/mark`)
  }, { timeout: 15_000 })
  await row.getByText(statusText, { exact: true }).click()
  const response = await write
  const payload = await response.json()
  expect(response.ok(), JSON.stringify(payload)).toBeTruthy()
  expect(payload.code, JSON.stringify(payload)).toBe(0)
  await expect(row.locator('.at__seg-item.is-active')).toHaveText(statusText)
  return payload.data
}

async function submitSession(page, sessionId) {
  const submit = page.getByText('提交考勤（提交后不可再改）', { exact: true })
  await expect(submit).toBeEnabled({ timeout: 10_000 })
  const write = page.waitForResponse((response) => {
    const url = new URL(response.url())
    return response.request().method() === 'POST' &&
      url.pathname.endsWith(`/api/v1/mobile/teacher/academic/attendance/sessions/${sessionId}/submit`)
  }, { timeout: 15_000 })
  await submit.click()
  const confirm = page.getByText('确认提交', { exact: true })
  await expect(confirm).toBeVisible({ timeout: 5_000 })
  await confirm.click()
  const response = await write
  const payload = await response.json()
  expect(response.ok(), JSON.stringify(payload)).toBeTruthy()
  expect(payload.code, JSON.stringify(payload)).toBe(0)
  expect(payload?.data?.status).toBe('SUBMITTED')
  return payload.data
}

async function duplicateCreateMustFail(page, f) {
  const url = `${MINIAPP_BASE}/#/pages/teacher/academic-affairs/attendance` +
    `?teachingTaskId=${f.teachingTaskId}&sessionDate=${f.targetDate}` +
    `&slotNo=${f.slotNo}&scheduleItemId=${f.scheduleItemId}`
  await page.goto(url)
  const createButton = page.getByText('按教学任务圈定名单并新建', { exact: true })
  await expect(createButton).toBeEnabled({ timeout: 20_000 })
  const write = page.waitForResponse((response) => {
    const u = new URL(response.url())
    return response.request().method() === 'POST' &&
      u.pathname.endsWith('/api/v1/mobile/teacher/academic/attendance/sessions')
  }, { timeout: 15_000 })
  await createButton.click()
  const response = await write
  const payload = await response.json()
  expect(payload.code, JSON.stringify(payload)).not.toBe(0)
  expect(response.status()).toBe(409)
  expect(JSON.stringify(payload)).toContain('已创建')
}

test('AA-010 Gold Deep: Teacher Mini roll-call -> Student PC/Mini -> Staff stats/warning -> Teacher close', async ({ browser, request }, testInfo) => {
  const f = fixture()
  const dates = [f.targetDate, dateMinus(f.targetDate, 7), dateMinus(f.targetDate, 14)]
  const miniBridge = await startMiniLoopbackBridge()
  const sessionIds = []
  let firstScan = null
  let secondScan = null

  try {
    // 1) Teacher Mini is the primary writer. Start from Teacher Today for the current real occurrence.
    const teacherContext = await browser.newContext({ viewport: { width: 390, height: 844 } })
    const teacher = await teacherContext.newPage()
    await loginTeacherMini(teacher)

    const firstId = await createSessionFromSeed(teacher, f, dates[0], { fromToday: true })
    sessionIds.push(firstId)
    await markStatus(teacher, firstId, f, '缺勤')
    // Status correction history inside DRAFT must survive and finish at ABSENT.
    await markStatus(teacher, firstId, f, '出勤')
    await markStatus(teacher, firstId, f, '缺勤')
    await screenshot(teacher, testInfo, 'aa010-teacher-current-absent-before-reload-390x844')

    await teacher.reload()
    const persisted = teacher.locator('.at__row').filter({ hasText: f.studentName }).first()
    await expect(persisted).toBeVisible({ timeout: 15_000 })
    await expect(persisted.locator('.at__seg-item.is-active')).toHaveText('缺勤')

    await clearMiniSession(teacher)
    await loginTeacherMini(teacher)
    await teacher.goto(`${MINIAPP_BASE}/#/pages/teacher/academic-affairs/attendance?sessionId=${firstId}`)
    const reloginRow = teacher.locator('.at__row').filter({ hasText: f.studentName }).first()
    await expect(reloginRow).toBeVisible({ timeout: 15_000 })
    await expect(reloginRow.locator('.at__seg-item.is-active')).toHaveText('缺勤')
    await submitSession(teacher, firstId)

    // 2) Create two earlier formal occurrences through the same real UI so cumulative absence reaches threshold 3.
    for (const sessionDate of dates.slice(1)) {
      const sessionId = await createSessionFromSeed(teacher, f, sessionDate)
      sessionIds.push(sessionId)
      await markStatus(teacher, sessionId, f, '缺勤')
      await submitSession(teacher, sessionId)
    }
    expect(new Set(sessionIds).size).toBe(3)
    await duplicateCreateMustFail(teacher, f)
    await teacherContext.close()

    // 3) Server must also reject mutation after SUBMITTED, independent of disabled UI.
    const teacherLogin = await request.post(`${config.apiBaseUrl}/auth/login`, {
      data: {
        loginName: config.mentor.username,
        password: config.mentor.password,
        tenantCode: config.mentor.tenant,
        clientType: 'TEACHER_MINI'
      }
    })
    const teacherAuth = await teacherLogin.json()
    expect(teacherAuth.code, JSON.stringify(teacherAuth)).toBe(0)
    const blocked = await request.post(
      `${config.apiBaseUrl}/mobile/teacher/academic/attendance/sessions/${firstId}/mark`,
      {
        headers: { Authorization: `Bearer ${teacherAuth?.data?.accessToken}` },
        data: { studentId: String(f.studentId || ''), status: 'PRESENT' }
      }
    )
    const blockedPayload = await blocked.json()
    expect(blockedPayload.code, JSON.stringify(blockedPayload)).not.toBe(0)

    // 4) Student PC real projection: same course/date facts and three absences.
    const studentPcContext = await browser.newContext({ viewport: { width: 1440, height: 900 } })
    const studentPc = await studentPcContext.newPage()
    const pcLogin = new StudentLoginPage(studentPc, config.studentBaseUrl)
    await pcLogin.login(config.student)
    await studentPc.goto(`${config.studentBaseUrl}/academic/attendance`)
    await expect(studentPc.getByRole('heading', { name: '查看本人课堂考勤记录' })).toBeVisible({ timeout: 20_000 })
    for (const date of dates) {
      const card = studentPc.locator('.record-item').filter({ hasText: f.courseName }).filter({ hasText: date }).first()
      await expect(card).toBeVisible({ timeout: 15_000 })
      await expect(card).toContainText('缺勤')
    }
    await expect(studentPc.locator('.metric-card').filter({ hasText: '异常' })).toContainText('3')
    await screenshot(studentPc, testInfo, 'aa010-student-pc-three-absences-1440x900')
    await studentPcContext.close()

    // 5) Student Mini real projection: same authoritative submitted attendance.
    const studentMiniContext = await browser.newContext({ viewport: { width: 390, height: 844 } })
    const studentMini = await studentMiniContext.newPage()
    await loginStudentMini(studentMini)
    await studentMini.goto(`${MINIAPP_BASE}/#/pages/student/academic-affairs/attendance`)
    await expect(studentMini.getByText('我的考勤', { exact: true })).toBeVisible({ timeout: 15_000 })
    await expect(studentMini.getByText(/旷课 3/)).toBeVisible({ timeout: 15_000 })
    for (const date of dates) {
      const row = studentMini.locator('.list-row').filter({ hasText: f.courseName }).filter({ hasText: date }).first()
      await expect(row).toBeVisible({ timeout: 15_000 })
    }
    await screenshot(studentMini, testInfo, 'aa010-student-mini-three-absences-390x844')
    await studentMiniContext.close()

    // 6) Staff PC reads the same submitted facts and triggers the product warning rule by a real button.
    const staffContext = await browser.newContext({ viewport: { width: 1440, height: 900 } })
    const staff = await staffContext.newPage()
    await loginAcademicAdmin(staff)
    await staff.goto(`${config.staffBaseUrl}/admin/academic-affairs/attendance-stats`)
    await dismissGuide(staff)
    await expect(staff.getByText('课堂考勤统计', { exact: true })).toBeVisible({ timeout: 20_000 })
    const statRow = staff.locator('tr').filter({ hasText: f.studentName }).first()
    await expect(statRow).toBeVisible({ timeout: 20_000 })
    await expect(statRow).toContainText('3')
    await screenshot(staff, testInfo, 'aa010-staff-stats-before-warning-scan-1440x900')

    const scanOnce = staff.waitForResponse((response) =>
      response.request().method() === 'POST' &&
      new URL(response.url()).pathname.endsWith('/api/v1/academic-affairs/warnings/scan/attendance')
    )
    await staff.getByRole('button', { name: '旷课预警扫描', exact: true }).click()
    const scanResponse = await scanOnce
    firstScan = await scanResponse.json()
    expect(scanResponse.ok(), JSON.stringify(firstScan)).toBeTruthy()
    expect(firstScan.code, JSON.stringify(firstScan)).toBe(0)
    expect(Number(firstScan?.data?.threshold)).toBe(3)
    expect(Number(firstScan?.data?.created)).toBe(1)

    const scanTwice = staff.waitForResponse((response) =>
      response.request().method() === 'POST' &&
      new URL(response.url()).pathname.endsWith('/api/v1/academic-affairs/warnings/scan/attendance')
    )
    await staff.getByRole('button', { name: '旷课预警扫描', exact: true }).click()
    const scanAgainResponse = await scanTwice
    secondScan = await scanAgainResponse.json()
    expect(scanAgainResponse.ok(), JSON.stringify(secondScan)).toBeTruthy()
    expect(secondScan.code, JSON.stringify(secondScan)).toBe(0)
    expect(Number(secondScan?.data?.created)).toBe(0)
    await staffContext.close()

    // 7) Teacher Mini consumes the generated warning and closes it through the real page/action.
    const warningContext = await browser.newContext({ viewport: { width: 390, height: 844 } })
    const warningPage = await warningContext.newPage()
    await loginTeacherMini(warningPage)
    await warningPage.goto(`${MINIAPP_BASE}/#/pages/teacher/academic-warning/index`)
    const warningCard = warningPage.locator('.card.aw').filter({ hasText: f.studentName }).filter({ hasText: '旷课 3 次' }).first()
    await expect(warningCard).toBeVisible({ timeout: 20_000 })
    await screenshot(warningPage, testInfo, 'aa010-teacher-warning-before-close-390x844')
    await warningCard.getByRole('button', { name: '关闭预警', exact: true }).click()
    const modalInput = warningPage.getByRole('textbox').last()
    await expect(modalInput).toBeVisible({ timeout: 5_000 })
    await modalInput.fill(closeNote)
    const handleWrite = warningPage.waitForResponse((response) =>
      response.request().method() === 'POST' &&
      response.url().includes('/api/v1/mobile/teacher/academic/warning/') &&
      response.url().endsWith('/handle')
    )
    await warningPage.getByText('确定', { exact: true }).last().click()
    const handleResponse = await handleWrite
    const handlePayload = await handleResponse.json()
    expect(handleResponse.ok(), JSON.stringify(handlePayload)).toBeTruthy()
    expect(handlePayload.code, JSON.stringify(handlePayload)).toBe(0)
    await expect(warningPage.locator('.card.aw').filter({ hasText: '旷课 3 次' })).toHaveCount(0, { timeout: 15_000 })
    await screenshot(warningPage, testInfo, 'aa010-teacher-warning-after-close-390x844')
    await warningContext.close()

    fs.writeFileSync(outcomePath, JSON.stringify({
      tenantCode: f.tenantCode,
      termId: String(f.termId),
      teachingTaskId: String(f.teachingTaskId),
      scheduleItemId: String(f.scheduleItemId),
      courseName: f.courseName,
      studentName: f.studentName,
      studentNo: f.studentNo,
      sessionDates: dates,
      sessionIds,
      firstScan: firstScan?.data || {},
      secondScan: secondScan?.data || {},
      warningCloseNote: closeNote
    }, null, 2))
  } finally {
    await closeServer(miniBridge)
  }
})
