import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { items, loginApi } from '../lib/api-fixture.mjs'

const VIEWPORT = { width: 1440, height: 1000 }
const STUDENT_NO = 'E2E20260002'

function runMarker() {
  const raw = process.env.GITHUB_RUN_ID || `${Date.now()}`
  return `${String(raw).replace(/\D/g, '').slice(-10)}-${process.pid}-${Date.now()}`
}

async function dismissGuide(page) {
  for (const mask of [page.locator('.app-step-guide__mask'), page.locator('.tour-mask')]) {
    if (await mask.isVisible().catch(() => false)) {
      const skip = page.getByRole('button', { name: /跳过引导|跳过/ }).first()
      if (await skip.isVisible().catch(() => false)) await skip.click()
      await mask.waitFor({ state: 'hidden', timeout: 3000 }).catch(() => {})
    }
  }
}

async function openWithApiSession(page, api, path) {
  await page.addInitScript(({ token }) => {
    window.sessionStorage.setItem('gx_pc_token_v1', token)
  }, { token: api.token })
  const refresh = page.waitForResponse((response) =>
    response.url().includes('/api/v1/auth/browser-refresh') && response.request().method() === 'POST'
  )
  await page.goto(`${config.staffBaseUrl}${path}`)
  const response = await refresh
  expect(response.ok(), `browser refresh HTTP ${response.status()}`).toBeTruthy()
  await dismissGuide(page)
}

async function findStudent(adminApi) {
  const rows = items(await adminApi.get('/students', {
    keyword: STUDENT_NO,
    page: 1,
    pageSize: 50
  }))
  const student = rows.find((row) => String(row.studentNo || row.loginName || '') === STUDENT_NO)
  if (!student?.id) throw new Error(`Student Affairs V3 student ${STUDENT_NO} not found`)
  return student
}

test.describe.serial('Student Affairs V3 focused Browser First · SA-011 / SA-022', () => {
  let adminApi
  let student

  test.beforeAll(async () => {
    adminApi = await loginApi(config.sandboxAdmin)
    student = await findStudent(adminApi)
  })

  test('SA-011 risk warning workspace uses Student Affairs fixture only', async ({ page }) => {
    const marker = runMarker()
    const created = await adminApi.post('/student-affairs/risk/records', {
      studentId: String(student.id),
      source: 'MANUAL',
      sourceRefId: `sa-v3-risk-${marker}`,
      riskLevel: 'HIGH',
      title: `SA-011 风险预警 ${marker}`,
      detail: 'SA-011 Browser First：真实学工风险记录进入风险工作区并可见。'
    })
    const riskId = String(created.riskId || created.id || '')
    expect(riskId).not.toBe('')

    await page.setViewportSize(VIEWPORT)
    await openWithApiSession(page, adminApi, '/admin/student-affairs/risk')
    await expect(page).toHaveURL(/\/admin\/student-affairs\/risk/)
    await expect(page.locator('.sa-grid--metrics')).toBeVisible()
    await expect(page.locator('.dt')).toBeVisible()
    await expect(page.locator('.dt__td').first()).toBeVisible()
    await expect(page.getByText(`SA-011 风险预警 ${marker}`, { exact: true })).toBeVisible()
  })

  test('SA-022 Student 360 profile opens from Student Affairs student only', async ({ page }) => {
    await page.setViewportSize(VIEWPORT)
    await openWithApiSession(
      page,
      adminApi,
      `/admin/student-affairs/profile/${encodeURIComponent(student.id)}`
    )

    await expect(page).toHaveURL(/\/admin\/student-affairs\/profile\//)
    await expect(page.getByRole('heading', { name: '学生画像详情', exact: true })).toBeVisible()
    await expect(page.locator('.profile-summary')).toBeVisible()
    await expect(page.locator('.profile-priority-grid')).toBeVisible()
    await expect(page.locator('.sa-detail-grid')).toBeVisible()
    await expect(page.locator('.profile-summary')).toContainText(STUDENT_NO)
    await expect(page.locator('.profile-priority-card')).toHaveCount(4)
  })
})
