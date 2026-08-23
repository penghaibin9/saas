import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { StaffLoginPage } from '../pages/login.page.mjs'

const fixture = JSON.parse(readFileSync(new URL('../academic-c-grade-browser-fixture.json', import.meta.url), 'utf8'))
const account = (username) => ({ tenant: fixture.tenant, username, password: fixture.password })
const staffBase = config.staffBaseUrl.replace(/\/+$/, '')
const evidenceDir = new URL('../artifacts/academic-c-grade-score-checkpoint/', import.meta.url)
const evidenceFile = new URL('../artifacts/academic-c-grade-score-checkpoint/browser-score-checkpoint.json', import.meta.url)

function waitForRefresh(page, timeout = 20_000) {
  return page.waitForResponse(
    (r) => r.url().includes('/api/v1/auth/browser-refresh') && r.request().method() === 'POST' && r.status() === 200,
    { timeout }
  )
}

async function dismissGuide(page) {
  const dialog = page.getByRole('dialog', { name: '页面操作引导' })
  if (!(await dialog.isVisible({ timeout: 800 }).catch(() => false))) return
  const skip = dialog.getByRole('button', { name: '跳过引导' })
  if (await skip.isVisible({ timeout: 800 }).catch(() => false)) await skip.click()
}

function attachNetworkSeal(page) {
  const failures = []
  const badResponses = []
  page.on('requestfailed', (req) => failures.push(`${req.method()} ${req.url()} :: ${req.failure()?.errorText || 'failed'}`))
  page.on('response', (res) => {
    const status = res.status()
    if (status < 400) return
    const url = res.url()
    if (status === 401 && url.includes('/api/v1/')) return
    if (url.includes('/api/v1/academic-affairs/grade') || status >= 500) {
      badResponses.push(`${status} ${res.request().method()} ${url}`)
    }
  })
  return () => {
    expect(failures, 'score-checkpoint: browser requestfailed must be empty').toEqual([])
    expect(badResponses, 'score-checkpoint: no unexpected grade 4xx or any 5xx').toEqual([])
  }
}

async function loginTeacher(page) {
  const login = new StaffLoginPage(page, staffBase)
  await login.login(account(fixture.teacher))
  const refresh = waitForRefresh(page)
  await page.goto(`${staffBase}/admin/academic-affairs/grade-entry`)
  await refresh
  await page.locator('.uchip__role').first().waitFor({ state: 'visible', timeout: 20_000 })
  await dismissGuide(page)
}

async function openTeachingTaskPicker(page) {
  const field = page.locator('label.aa-field').filter({ hasText: '教学任务' }).first()
  const combo = field.locator('[role="combobox"]')
  await expect(combo).toBeVisible()
  await combo.click()
  const search = field.locator('input.app-remote-select__search-el')
  await search.fill(fixture.courseName)
  const option = field.locator('[role="option"]').filter({ hasText: fixture.courseName }).first()
  await expect(option).toBeVisible({ timeout: 15_000 })
  await option.click()
}

async function saveScores(page) {
  const rows = page.locator('table.aa-course-table tbody tr')
  await expect(rows).toHaveCount(2)
  const values = [
    { usual: 82, final: 88 },
    { usual: 55, final: 50 },
  ]
  for (let i = 0; i < values.length; i += 1) {
    const row = rows.nth(i)
    const inputs = row.locator('input[type="number"]')
    await expect(inputs).toHaveCount(2)
    await inputs.nth(0).fill(String(values[i].usual))
    await inputs.nth(1).fill(String(values[i].final))
    const responsePromise = page.waitForResponse((r) =>
      r.url().includes('/api/v1/academic-affairs/grade-tasks/') &&
      r.url().includes('/scores') && r.request().method() === 'POST'
    )
    await row.getByRole('button', { name: '录入' }).click()
    const response = await responsePromise
    expect(response.status()).toBe(200)
    const payload = await response.json()
    expect(payload.code).toBe(0)
  }
}

async function verifyReloadedScores(page) {
  await page.reload()
  await page.locator('.uchip__role').first().waitFor({ state: 'visible', timeout: 20_000 })
  await dismissGuide(page)
  const taskRow = page.locator('.aa-my-task-item').filter({ hasText: fixture.courseName }).first()
  await expect(taskRow).toBeVisible({ timeout: 20_000 })
  await taskRow.getByRole('button', { name: '进入' }).click()
  await expect(page.getByText(`录入任务：${fixture.courseName}`, { exact: false })).toBeVisible()

  const rows = page.locator('table.aa-course-table tbody tr')
  await expect(rows).toHaveCount(2)
  const expected = [
    { usual: '82', final: '88' },
    { usual: '55', final: '50' },
  ]
  for (let i = 0; i < expected.length; i += 1) {
    const inputs = rows.nth(i).locator('input[type="number"]')
    await expect(inputs.nth(0)).toHaveValue(expected[i].usual)
    await expect(inputs.nth(1)).toHaveValue(expected[i].final)
  }
}

test('Academic C grade score checkpoint: browser writes persist through reload before submit', async ({ browser }, testInfo) => {
  const ctx = await browser.newContext({ locale: 'zh-CN', timezoneId: 'Asia/Shanghai' })
  const page = await ctx.newPage()
  const assertNetwork = attachNetworkSeal(page)
  let gradeTaskId = ''
  try {
    await loginTeacher(page)
    await expect(page.getByText('新建成绩录入任务', { exact: true })).toBeVisible()
    await openTeachingTaskPicker(page)

    const createPromise = page.waitForResponse((r) =>
      r.url().includes('/api/v1/academic-affairs/grade-tasks') && r.request().method() === 'POST'
    )
    await page.getByRole('button', { name: '创建任务' }).click()
    const created = await createPromise
    expect(created.status()).toBe(200)
    const createdPayload = await created.json()
    expect(createdPayload.code).toBe(0)
    gradeTaskId = String(createdPayload.data?.gradeTaskId || createdPayload.data?.taskId || '')
    expect(gradeTaskId).toBeTruthy()

    // The create response itself must already carry the canonical server-owned authority projection.
    expect(createdPayload.data?.teacherAuthorityReady).toBe(true)
    expect(createdPayload.data?.allowedActions || []).toContain('INPUT')

    const rosterPromise = page.waitForResponse((r) =>
      r.url().includes(`/api/v1/academic-affairs/grade-tasks/${gradeTaskId}/roster`) && r.request().method() === 'GET'
    )
    await page.getByRole('button', { name: '按正式名单圈定' }).click()
    const rosterResponse = await rosterPromise
    expect(rosterResponse.status()).toBe(200)

    await saveScores(page)
    await expect(page.getByRole('button', { name: '提交进入学院审核' })).toBeVisible({ timeout: 10_000 })
    await verifyReloadedScores(page)
    await expect(page.getByRole('button', { name: '提交进入学院审核' })).toBeVisible({ timeout: 10_000 })

    mkdirSync(evidenceDir, { recursive: true })
    const checkpoint = {
      tenant: fixture.tenant,
      tenantId: Number(fixture.tenantId),
      teachingTaskId: Number(fixture.teachingTaskId),
      gradeTaskId: Number(gradeTaskId),
      studentIds: fixture.studentIds.map(Number),
      expectedScores: [
        { studentId: Number(fixture.studentIds[0]), usualScore: 82, finalScore: 88 },
        { studentId: Number(fixture.studentIds[1]), usualScore: 55, finalScore: 50 },
      ],
      browserReloadVerified: true,
      submitButtonVisible: true,
      capturedAt: new Date().toISOString(),
    }
    writeFileSync(evidenceFile, `${JSON.stringify(checkpoint, null, 2)}\n`, 'utf8')
    await testInfo.attach('score-checkpoint', { body: JSON.stringify(checkpoint, null, 2), contentType: 'application/json' })
    assertNetwork()
  } finally {
    await ctx.close()
  }
})
