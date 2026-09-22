import { execFileSync } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { StaffLoginPage } from '../pages/login.page.mjs'

const here = path.dirname(fileURLToPath(import.meta.url))
const repoRoot = path.resolve(here, '../..')
const backendDir = path.join(repoRoot, 'backend')
const statePath = path.join(backendDir, 'tmp/e2e_academic_c_teacher_today_state.local.json')
const otherTeacher = {
  tenant: config.mentor.tenant,
  username: 'e2e_advisor_b',
  password: config.mentor.password
}

function runFixture(command) {
  execFileSync('python', ['scripts/e2e_seed_academic_c_teacher_today.py', command], {
    cwd: backendDir,
    env: process.env,
    stdio: 'inherit'
  })
}

function readFixture() {
  return JSON.parse(fs.readFileSync(statePath, 'utf8'))
}

async function loginTeacherPc(page) {
  const login = new StaffLoginPage(page, config.staffBaseUrl)
  await login.login(config.mentor)
  await login.switchRole(/任课教师|ACADEMIC_TEACHER/)
  await expect(page.locator('.uchip__role').first()).toContainText(/任课教师|ACADEMIC_TEACHER/)
}

async function loginApiAsAcademicTeacher(request, account, forwardedFor) {
  const login = await request.post(`${config.apiBaseUrl}/auth/login`, {
    headers: { 'X-Forwarded-For': forwardedFor },
    data: {
      loginName: account.username,
      password: account.password,
      tenantCode: account.tenant,
      clientType: 'PC'
    }
  })
  const payload = await login.json()
  expect(payload.code, JSON.stringify(payload)).toBe(0)
  const context = (payload?.data?.contexts || []).find(
    (item) => String(item?.roleCode || '').toUpperCase() === 'ACADEMIC_TEACHER'
  )
  expect(context?.contextId, JSON.stringify(payload)).toBeTruthy()
  const switched = await request.post(`${config.apiBaseUrl}/auth/switch-role`, {
    headers: { Authorization: `Bearer ${payload?.data?.accessToken}` },
    data: { contextId: context.contextId, clientType: 'PC' }
  })
  const switchedPayload = await switched.json()
  expect(switchedPayload.code, JSON.stringify(switchedPayload)).toBe(0)
  return switchedPayload?.data?.accessToken
}

test.describe.serial('Academic teacher V2 · real PC flow', () => {
  let fixture

  test.beforeAll(() => {
    runFixture('seed')
    fixture = readFixture()
  })

  test.afterAll(() => {
    runFixture('cleanup')
  })

  test('today -> canonical attendance -> mark all -> submit -> cross-teacher denied', async ({ page, request }) => {
    await page.setViewportSize({ width: 1440, height: 900 })
    await loginTeacherPc(page)

    await page.goto(`${config.staffBaseUrl}/admin/academic-affairs/teacher/today`)
    await expect(page.getByRole('heading', { name: '今日教学' })).toBeVisible({ timeout: 20_000 })
    const course = page.locator('.aat-course').filter({ hasText: fixture.courseName }).first()
    await expect(course).toBeVisible({ timeout: 20_000 })
    await expect(course.getByRole('button', { name: '考勤', exact: true })).toBeEnabled()

    const openResponsePromise = page.waitForResponse((response) => {
      const url = new URL(response.url())
      return response.request().method() === 'POST'
        && url.pathname.endsWith('/api/v1/academic-affairs/attendance/sessions/open')
    }, { timeout: 20_000 })
    await course.getByRole('button', { name: '考勤', exact: true }).click()
    const openResponse = await openResponsePromise
    const openPayload = await openResponse.json()
    expect(openPayload.code, JSON.stringify(openPayload)).toBe(0)
    const sessionId = String(openPayload?.data?.sessionId || '')
    expect(sessionId).toMatch(/^\d+$/)

    await expect(page).toHaveURL(new RegExp(`attendance-stats\\?panel=sessions&sessionId=${sessionId}`), { timeout: 15_000 })
    await expect(page.getByText(fixture.courseName, { exact: false }).first()).toBeVisible({ timeout: 15_000 })

    const targetRow = page.locator('table tbody tr').filter({ hasText: fixture.studentName }).first()
    await expect(targetRow).toBeVisible()
    const absentResponsePromise = page.waitForResponse((response) =>
      response.request().method() === 'POST'
        && new URL(response.url()).pathname.endsWith(`/api/v1/academic-affairs/attendance/sessions/${sessionId}/mark`)
    )
    await targetRow.getByRole('button', { name: '旷课', exact: true }).click()
    expect((await (await absentResponsePromise).json()).code).toBe(0)

    for (let guard = 0; guard < 10; guard += 1) {
      const unmarked = page.locator('table tbody tr').filter({ hasText: '未点名' }).first()
      if (!(await unmarked.count()) || !(await unmarked.isVisible().catch(() => false))) break
      const markResponsePromise = page.waitForResponse((response) =>
        response.request().method() === 'POST'
          && new URL(response.url()).pathname.endsWith(`/api/v1/academic-affairs/attendance/sessions/${sessionId}/mark`)
      )
      await unmarked.getByRole('button', { name: '出勤', exact: true }).click()
      expect((await (await markResponsePromise).json()).code).toBe(0)
    }

    await expect(page.getByText(/未点名 0 人/)).toBeVisible({ timeout: 15_000 })
    const submitResponsePromise = page.waitForResponse((response) =>
      response.request().method() === 'POST'
        && new URL(response.url()).pathname.endsWith(`/api/v1/academic-affairs/attendance/sessions/${sessionId}/submit`)
    )
    await page.getByRole('button', { name: '提交本场考勤' }).click()
    const submitPayload = await (await submitResponsePromise).json()
    expect(submitPayload.code, JSON.stringify(submitPayload)).toBe(0)
    await expect(page.getByText('已提交', { exact: true }).first()).toBeVisible({ timeout: 15_000 })

    const otherToken = await loginApiAsAcademicTeacher(request, otherTeacher, '10.254.0.82')
    expect(otherToken).toBeTruthy()
    const blocked = await request.get(
      `${config.apiBaseUrl}/academic-affairs/attendance/sessions/${sessionId}`,
      { headers: { Authorization: `Bearer ${otherToken}` } }
    )
    const blockedPayload = await blocked.json()
    expect(blockedPayload.code, JSON.stringify(blockedPayload)).not.toBe(0)
  })
})
