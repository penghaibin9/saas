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
const otherTeacher = {
  tenant: config.mentor.tenant,
  username: 'e2e_advisor_b',
  password: config.mentor.password,
}

function fixture() {
  return JSON.parse(fs.readFileSync(statePath, 'utf8'))
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
  if (!upstream) throw new Error(`AA-010 Mini upstream is not reachable: ${MINIAPP_UPSTREAM.origin}`)

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
      response.end(`AA-010 Mini loopback bridge failed: ${error.message}`)
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
    sessionId: String(sessionStorage.getItem('gx_h5_browser_session_id_v1') || ''),
  }))
  if (browserSession.channel && browserSession.sessionId) {
    const logout = await page.context().request.post(`${config.apiBaseUrl}/auth/browser-logout`, {
      headers: {
        'X-Browser-Session': browserSession.channel,
        'X-Browser-Session-Id': browserSession.sessionId,
      },
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
  const loginResponse = page.waitForResponse((response) =>
    response.url().includes('/api/v1/auth/browser-login') && response.request().method() === 'POST'
  )
  await authCard.locator('.account-button').first().click()
  expect((await loginResponse).ok()).toBeTruthy()
  await page.waitForURL(/pages\/student\/home\/index/, { timeout: 60_000 })
}

async function loginAcademicAdmin(page) {
  const login = new StaffLoginPage(page, config.staffBaseUrl)
  await login.login(config.multiRole)
  await login.switchRole(/教务处管理员|教务管理员|教务老师|ACADEMIC_ADMIN/)
}

async function dismissGuide(page) {
  const mask = page.locator('.app-step-guide__mask')
  await mask.waitFor({ state: 'visible', timeout: 1_500 }).catch(() => {})
  if (await mask.isVisible().catch(() => false)) {
    const skip = page.getByRole('button', { name: '跳过引导' })
    if (await skip.count()) await skip.click()
  }
}

function attendanceDocumentUrl(facts, occurrence) {
  const documentKey = encodeURIComponent(`${occurrence.label}-${occurrence.sessionDate}-${occurrence.scheduleItemId}-${occurrence.slotNo}`)
  return `${MINIAPP_BASE}/?aa010Occurrence=${documentKey}` +
    `#/pages/teacher/academic-affairs/attendance?teachingTaskId=${facts.teachingTaskId}` +
    `&sessionDate=${occurrence.sessionDate}&slotNo=${occurrence.slotNo}` +
    `&scheduleItemId=${occurrence.scheduleItemId}`
}

async function createSessionFromUi(page, facts, occurrence, fromToday = false) {
  const label = String(occurrence.label || occurrence.sessionDate)
  const sessionDate = String(occurrence.sessionDate)
  const scheduleItemId = String(occurrence.scheduleItemId)
  const slotNo = String(occurrence.slotNo)

  if (fromToday) {
    await page.goto(`${MINIAPP_BASE}/#/pages/teacher/academic-affairs/index`)
    const today = page.locator('.ta__course').filter({ hasText: facts.courseName }).first()
    await expect(today).toBeVisible({ timeout: 20_000 })
    await expect(today).toContainText('已调课')
    await expect(today).toContainText('去点名')
    await today.click()
    await expect(page).toHaveURL(new RegExp(
      `pages/teacher/academic-affairs/attendance\\?teachingTaskId=${facts.teachingTaskId}`
    ), { timeout: 10_000 })
  } else {
    // Force a real document navigation, not merely a same-page hash/query mutation. This makes
    // UniApp remount attendance.vue and rerun onLoad for every proven formal occurrence while
    // preserving same-origin browser session storage and cookies.
    await page.goto(attendanceDocumentUrl(facts, occurrence), { waitUntil: 'domcontentloaded' })
  }

  expect(page.url(), `AA-010 ${label} route must carry the proven session date`).toContain(`sessionDate=${sessionDate}`)
  expect(page.url(), `AA-010 ${label} route must carry the proven slot`).toContain(`slotNo=${slotNo}`)
  expect(page.url(), `AA-010 ${label} route must carry the proven schedule item`).toContain(`scheduleItemId=${scheduleItemId}`)
  await expect(page.getByText('课堂考勤', { exact: true })).toBeVisible({ timeout: 20_000 })

  const create = page.getByText('按教学任务圈定名单并新建', { exact: true })
  await expect(create, `AA-010 ${label} (${sessionDate} / item ${scheduleItemId} / slot ${slotNo}) must be an executable published occurrence`).toBeEnabled({ timeout: 20_000 })
  const write = page.waitForResponse((response) => {
    const url = new URL(response.url())
    return response.request().method() === 'POST' &&
      url.pathname.endsWith('/api/v1/mobile/teacher/academic/attendance/sessions')
  }, { timeout: 20_000 })
  await create.click()
  const response = await write
  const payload = await response.json()
  expect(response.ok(), JSON.stringify(payload)).toBeTruthy()
  expect(payload.code, JSON.stringify(payload)).toBe(0)
  expect(String(payload?.data?.teachingTaskId || '')).toBe(String(facts.teachingTaskId))
  expect(payload?.data?.sourceType).toBe('FORMAL_TEACHING')
  const sessionId = String(payload?.data?.sessionId || '')
  expect(sessionId).toMatch(/^\d+$/)

  // Product keeps the teacher on the session list after creation. Follow the same real-user
  // path as a teacher: find the just-created DRAFT occurrence and click it into roll-call detail.
  const createdRow = page.locator('.list-row')
    .filter({ hasText: facts.courseName })
    .filter({ hasText: sessionDate })
    .filter({ hasText: `第${slotNo}节` })
    .first()
  await expect(createdRow, `AA-010 ${label} newly created occurrence must appear in the teacher session list`).toBeVisible({ timeout: 10_000 })
  await expect(createdRow).toContainText('草稿')
  await createdRow.click()
  await expect(page.getByText('考勤详情', { exact: true })).toBeVisible({ timeout: 10_000 })
  return sessionId
}

async function markStatus(page, sessionId, facts, statusText) {
  const row = page.locator('.at__row').filter({ hasText: facts.studentName }).first()
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
  await page.getByText('确认提交', { exact: true }).click()
  const response = await write
  const payload = await response.json()
  expect(response.ok(), JSON.stringify(payload)).toBeTruthy()
  expect(payload.code, JSON.stringify(payload)).toBe(0)
  expect(payload?.data?.status).toBe('SUBMITTED')
}

async function apiLogin(request, account, clientType) {
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
  const token = payload?.data?.accessToken
  expect(token).toBeTruthy()
  return token
}

async function serverNegatives(request, facts, firstOccurrence, firstSessionId) {
  const teacherToken = await apiLogin(request, config.mentor, 'TEACHER_MINI')
  const teacherHeaders = { Authorization: `Bearer ${teacherToken}` }

  const detailResponse = await request.get(
    `${config.apiBaseUrl}/mobile/teacher/academic/attendance/sessions/${firstSessionId}`,
    { headers: teacherHeaders }
  )
  const detail = await detailResponse.json()
  expect(detailResponse.ok(), JSON.stringify(detail)).toBeTruthy()
  expect(detail.code, JSON.stringify(detail)).toBe(0)
  const target = (detail?.data?.items || []).find((row) => String(row.studentNo || '') === String(facts.studentNo))
  expect(target, 'AA-010 submitted immutability must use the real roster studentId').toBeTruthy()

  const blockedMark = await request.post(
    `${config.apiBaseUrl}/mobile/teacher/academic/attendance/sessions/${firstSessionId}/mark`,
    {
      headers: teacherHeaders,
      data: { studentId: String(target.studentId), status: 'PRESENT' },
    }
  )
  const blockedMarkPayload = await blockedMark.json()
  expect(blockedMark.status()).toBe(409)
  expect(blockedMarkPayload.code, JSON.stringify(blockedMarkPayload)).not.toBe(0)
  expect(JSON.stringify(blockedMarkPayload)).toContain('已提交的考勤不可再修改')

  const duplicate = await request.post(
    `${config.apiBaseUrl}/mobile/teacher/academic/attendance/sessions`,
    {
      headers: teacherHeaders,
      data: {
        teachingTaskId: String(facts.teachingTaskId),
        sessionDate: String(firstOccurrence.sessionDate),
        slotNo: Number(firstOccurrence.slotNo),
        scheduleItemId: String(firstOccurrence.scheduleItemId),
      },
    }
  )
  const duplicatePayload = await duplicate.json()
  expect(duplicate.status()).toBe(409)
  expect(duplicatePayload.code, JSON.stringify(duplicatePayload)).not.toBe(0)
  expect(JSON.stringify(duplicatePayload)).toContain('已创建课堂考勤场次')

  const otherToken = await apiLogin(request, otherTeacher, 'TEACHER_MINI')
  const otherRead = await request.get(
    `${config.apiBaseUrl}/mobile/teacher/academic/attendance/sessions/${firstSessionId}`,
    { headers: { Authorization: `Bearer ${otherToken}` } }
  )
  const otherPayload = await otherRead.json()
  expect(otherRead.status()).toBe(403)
  expect(otherPayload.code, JSON.stringify(otherPayload)).not.toBe(0)

  const studentToken = await apiLogin(request, config.student, 'STUDENT_MINI')
  const roleRead = await request.get(
    `${config.apiBaseUrl}/mobile/teacher/academic/attendance/sessions/${firstSessionId}`,
    { headers: { Authorization: `Bearer ${studentToken}` } }
  )
  const rolePayload = await roleRead.json()
  expect(roleRead.status()).toBe(403)
  expect(rolePayload.code, JSON.stringify(rolePayload)).not.toBe(0)
}

test('AA-010 Gold Deep: real roll-call -> immutable submit -> student projections -> warning follow-up', async ({ browser, request }, testInfo) => {
  const facts = fixture()
  const occurrences = facts.attendanceOccurrences || []
  expect(occurrences, 'AA-010 Runner must provide three DB-proven published formal occurrences').toHaveLength(3)
  const dates = occurrences.map((row) => String(row.sessionDate))
  expect(new Set(dates).size).toBe(3)
  for (const occurrence of occurrences) {
    expect(String(occurrence.sessionDate)).toMatch(/^\d{4}-\d{2}-\d{2}$/)
    expect(Number(occurrence.scheduleItemId)).toBeGreaterThan(0)
    expect(Number(occurrence.slotNo)).toBeGreaterThan(0)
    expect(Number(occurrence.weekNo)).toBeGreaterThan(0)
    expect(Number(occurrence.activeBatchId)).toBeGreaterThan(0)
  }
  expect(dates[0]).toBe(String(facts.targetDate))

  const bridge = await startMiniLoopbackBridge()
  const sessionIds = []
  let firstScan = null
  let secondScan = null

  try {
    // Teacher Mini is the only primary writer. The current occurrence starts from Teacher Today.
    const teacherContext = await browser.newContext({ viewport: { width: 390, height: 844 } })
    const teacher = await teacherContext.newPage()
    await loginTeacherMini(teacher)

    const firstId = await createSessionFromUi(teacher, facts, occurrences[0], true)
    sessionIds.push(firstId)
    await markStatus(teacher, firstId, facts, '缺勤')
    await markStatus(teacher, firstId, facts, '出勤')
    await markStatus(teacher, firstId, facts, '缺勤')
    await screenshot(teacher, testInfo, 'aa010-teacher-correction-before-reload-390x844')

    await teacher.reload()
    const reloaded = teacher.locator('.list-row')
      .filter({ hasText: facts.courseName })
      .filter({ hasText: String(occurrences[0].sessionDate) })
      .filter({ hasText: `第${occurrences[0].slotNo}节` }).first()
    await expect(reloaded).toContainText('草稿', { timeout: 15_000 })
    await reloaded.click()
    const persisted = teacher.locator('.at__row').filter({ hasText: facts.studentName }).first()
    await expect(persisted).toBeVisible({ timeout: 15_000 })
    await expect(persisted.locator('.at__seg-item.is-active')).toHaveText('缺勤')

    await clearMiniSession(teacher)
    await loginTeacherMini(teacher)
    await teacher.goto(`${MINIAPP_BASE}/#/pages/teacher/academic-affairs/attendance?sessionId=${firstId}`)
    const relogin = teacher.locator('.at__row').filter({ hasText: facts.studentName }).first()
    await expect(relogin).toBeVisible({ timeout: 15_000 })
    await expect(relogin.locator('.at__seg-item.is-active')).toHaveText('缺勤')
    await submitSession(teacher, firstId)

    // The next two writes consume DB-proven formal tuples and force a fresh UniApp page lifecycle.
    for (const occurrence of occurrences.slice(1)) {
      const sessionId = await createSessionFromUi(teacher, facts, occurrence)
      sessionIds.push(sessionId)
      await markStatus(teacher, sessionId, facts, '缺勤')
      await submitSession(teacher, sessionId)
    }
    expect(new Set(sessionIds).size).toBe(3)
    await teacherContext.close()

    // Server-side hard negatives: immutable submitted facts, duplicate occurrence, relation and role scope.
    await serverNegatives(request, facts, occurrences[0], firstId)

    // Student PC reads only the three submitted authoritative absences.
    const studentPcContext = await browser.newContext({ viewport: { width: 1440, height: 900 } })
    const studentPc = await studentPcContext.newPage()
    const studentLogin = new StudentLoginPage(studentPc, config.studentBaseUrl)
    await studentLogin.login(config.student)
    await studentPc.goto(`${config.studentBaseUrl}/academic/attendance`)
    await expect(studentPc.getByRole('heading', { name: '查看本人课堂考勤记录' })).toBeVisible({ timeout: 20_000 })
    for (const date of dates) {
      const row = studentPc.locator('.record-item').filter({ hasText: facts.courseName }).filter({ hasText: date }).first()
      await expect(row).toBeVisible({ timeout: 15_000 })
      await expect(row).toContainText('缺勤')
    }
    const abnormalMetric = studentPc.locator('.metric-card').filter({ hasText: '异常' }).first()
    await expect(abnormalMetric).toContainText('3')
    await screenshot(studentPc, testInfo, 'aa010-student-pc-three-absences-1440x900')
    await studentPcContext.close()

    // Student Mini must project the same submitted facts.
    const studentMiniContext = await browser.newContext({ viewport: { width: 390, height: 844 } })
    const studentMini = await studentMiniContext.newPage()
    await loginStudentMini(studentMini)
    await studentMini.goto(`${MINIAPP_BASE}/#/pages/student/academic-affairs/attendance`)
    await expect(studentMini.getByText('我的考勤', { exact: true })).toBeVisible({ timeout: 15_000 })
    await expect(studentMini.getByText(/旷课\s*3/)).toBeVisible({ timeout: 15_000 })
    for (const date of dates) {
      const row = studentMini.locator('.list-row').filter({ hasText: facts.courseName }).filter({ hasText: date }).first()
      await expect(row).toBeVisible({ timeout: 15_000 })
    }
    await screenshot(studentMini, testInfo, 'aa010-student-mini-three-absences-390x844')
    await studentMiniContext.close()

    // Staff PC reads the same aggregation. Warning already exists because submit auto-scans.
    const staffContext = await browser.newContext({ viewport: { width: 1440, height: 900 } })
    const staff = await staffContext.newPage()
    await loginAcademicAdmin(staff)
    await staff.goto(`${config.staffBaseUrl}/admin/academic-affairs/attendance-stats`)
    await dismissGuide(staff)
    await expect(staff.getByText('课堂考勤统计', { exact: true })).toBeVisible({ timeout: 20_000 })
    const statRow = staff.locator('tr').filter({ hasText: facts.studentName }).first()
    await expect(statRow).toBeVisible({ timeout: 20_000 })
    await expect(statRow).toContainText('3')
    await screenshot(staff, testInfo, 'aa010-staff-stats-three-absences-1440x900')

    const scanOnce = staff.waitForResponse((response) =>
      response.request().method() === 'POST' &&
      new URL(response.url()).pathname.endsWith('/api/v1/academic-affairs/warnings/scan/attendance')
    )
    await staff.getByRole('button', { name: '旷课预警扫描', exact: true }).click()
    const firstResponse = await scanOnce
    firstScan = await firstResponse.json()
    expect(firstResponse.ok(), JSON.stringify(firstScan)).toBeTruthy()
    expect(firstScan.code, JSON.stringify(firstScan)).toBe(0)
    expect(Number(firstScan?.data?.threshold)).toBe(3)
    expect(Number(firstScan?.data?.created)).toBe(0)

    const scanTwice = staff.waitForResponse((response) =>
      response.request().method() === 'POST' &&
      new URL(response.url()).pathname.endsWith('/api/v1/academic-affairs/warnings/scan/attendance')
    )
    await staff.getByRole('button', { name: '旷课预警扫描', exact: true }).click()
    const secondResponse = await scanTwice
    secondScan = await secondResponse.json()
    expect(secondResponse.ok(), JSON.stringify(secondScan)).toBeTruthy()
    expect(secondScan.code, JSON.stringify(secondScan)).toBe(0)
    expect(Number(secondScan?.data?.created)).toBe(0)
    await staffContext.close()

    // Teacher Mini consumes the auto-generated warning and closes the real follow-up loop.
    const warningContext = await browser.newContext({ viewport: { width: 390, height: 844 } })
    const warningPage = await warningContext.newPage()
    await loginTeacherMini(warningPage)
    await warningPage.goto(`${MINIAPP_BASE}/#/pages/teacher/academic-warning/index`)
    const warningCard = warningPage.locator('.card.aw')
      .filter({ hasText: facts.studentName })
      .filter({ hasText: '旷课 3 次' })
      .first()
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
      tenantCode: facts.tenantCode,
      termId: String(facts.termId),
      teachingTaskId: String(facts.teachingTaskId),
      scheduleItemId: String(facts.scheduleItemId),
      courseName: facts.courseName,
      studentName: facts.studentName,
      studentNo: facts.studentNo,
      formalOccurrences: occurrences,
      sessionDates: dates,
      sessionIds,
      firstScan: firstScan?.data || {},
      secondScan: secondScan?.data || {},
      warningCloseNote: closeNote,
    }, null, 2))
  } finally {
    await closeServer(bridge)
  }
})
