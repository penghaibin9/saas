import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { loadInternshipFixture } from '../lib/internship-fixture.mjs'
import { items, loginApi, prepareGraduationFixture } from '../lib/api-fixture.mjs'

const VIEWPORT = { width: 1440, height: 1000 }

async function dismissGuide(page) {
  for (const mask of [page.locator('.app-step-guide__mask'), page.locator('.tour-mask')]) {
    if (await mask.isVisible().catch(() => false)) {
      const skip = page.getByRole('button', { name: /跳过引导|跳过/ }).first()
      if (await skip.isVisible().catch(() => false)) await skip.click()
      await mask.waitFor({ state: 'hidden', timeout: 3000 }).catch(() => {})
    }
  }
}

async function settleVisual(page) {
  await page.evaluate(async () => {
    if (document.fonts?.ready) await document.fonts.ready
  })
  await page.waitForLoadState('networkidle', { timeout: 5000 }).catch(() => {})
}

async function capture(page, testInfo, name) {
  await dismissGuide(page)
  await settleVisual(page)
  const viewportPath = testInfo.outputPath(`${name}-1440x1000.png`)
  const fullPath = testInfo.outputPath(`${name}-full.png`)
  await page.screenshot({ path: viewportPath, fullPage: false, animations: 'disabled', caret: 'hide' })
  await page.screenshot({ path: fullPath, fullPage: true, animations: 'disabled', caret: 'hide' })
  await testInfo.attach(`${name}-viewport`, { path: viewportPath, contentType: 'image/png' })
  await testInfo.attach(`${name}-full`, { path: fullPath, contentType: 'image/png' })
}

async function openStaffWorkspace(page, api, path, storage = {}) {
  await page.addInitScript(({ token, entries }) => {
    window.sessionStorage.setItem('gx_pc_token_v1', token)
    for (const [key, value] of entries) window.localStorage.setItem(key, String(value))
  }, { token: api.token, entries: Object.entries(storage) })
  await page.goto(`${config.staffBaseUrl}${path}`)
  await dismissGuide(page)
}

async function findStudentProfile(admin, studentNo) {
  const rows = items(await admin.get('/students', { keyword: studentNo, page: 1, pageSize: 50 }))
  const row = rows.find((item) => String(item.studentNo || item.loginName || '') === String(studentNo))
  if (!row?.id) throw new Error(`Golden Batch 10 student profile ${studentNo} not found`)
  return row
}

test.describe.serial('Golden rollout · student 360 detail workspaces · Batch 10', () => {
  let adminApi
  let internshipFixture
  let graduationFixture
  let studentProfile

  test.beforeAll(async () => {
    internshipFixture = await loadInternshipFixture()
    graduationFixture = await prepareGraduationFixture()
    adminApi = await loginApi(config.sandboxAdmin)
    studentProfile = await findStudentProfile(adminApi, internshipFixture.studentNo)
  })

  test('Student Affairs profile detail · Screenshot A', async ({ page }, testInfo) => {
    await page.setViewportSize(VIEWPORT)
    await openStaffWorkspace(page, adminApi, `/admin/student-affairs/profile/${encodeURIComponent(studentProfile.id)}`)

    await expect(page).toHaveURL(/\/admin\/student-affairs\/profile\//)
    await expect(page.getByRole('heading', { name: '学生画像详情', exact: true })).toBeVisible()
    await expect(page.locator('.profile-summary')).toBeVisible()
    await expect(page.locator('.profile-priority-grid')).toBeVisible()
    await expect(page.locator('.sa-detail-grid')).toBeVisible()
    await expect(page.locator('.profile-summary')).toContainText(internshipFixture.studentNo)

    await capture(page, testInfo, 'rollout-student-360-affairs-profile-a')
  })

  test('Internship student detail · Screenshot A', async ({ page }, testInfo) => {
    await page.setViewportSize(VIEWPORT)
    const path = `/admin/internship/students/${encodeURIComponent(internshipFixture.internshipId)}?batchId=${encodeURIComponent(internshipFixture.batchId)}`
    await openStaffWorkspace(page, adminApi, path, {
      'internship.selectedBatchId': internshipFixture.batchId
    })

    await expect(page).toHaveURL(/\/admin\/internship\/students\//)
    await expect(page.getByRole('heading', { name: new RegExp(`${internshipFixture.studentName}.*实习详情`) })).toBeVisible()
    await expect(page.locator('.sd-summary')).toBeVisible()
    await expect(page.locator('.sd-panels')).toBeVisible()
    await expect(page.locator('.sd-audit')).toBeVisible()
    await expect(page.locator('.sd-summary')).toContainText(internshipFixture.studentName)

    await capture(page, testInfo, 'rollout-student-360-internship-detail-a')
  })

  test('Graduation student detail · Screenshot A', async ({ page }, testInfo) => {
    await page.setViewportSize(VIEWPORT)
    const path = `/admin/graduation/students/${encodeURIComponent(graduationFixture.gdStudentId)}?batchId=${encodeURIComponent(graduationFixture.batchId)}`
    await openStaffWorkspace(page, adminApi, path)

    await expect(page).toHaveURL(/\/admin\/graduation\/students\//)
    await expect(page.getByRole('heading', { name: /毕设详情/ })).toBeVisible()
    await expect(page.locator('.gsd-page')).toBeVisible()
    await expect(page.locator('.gsd-summary')).toBeVisible()
    await expect(page.locator('.gsd-tabs')).toBeVisible()
    await expect(page.locator('.gsd-summary')).toContainText(graduationFixture.studentNo)

    await capture(page, testInfo, 'rollout-student-360-graduation-detail-a')
  })
})
