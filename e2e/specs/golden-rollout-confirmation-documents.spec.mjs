import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { loadInternshipFixture } from '../lib/internship-fixture.mjs'
import { items, loginApi, prepareGraduationFixture } from '../lib/api-fixture.mjs'

const VIEWPORT = { width: 1440, height: 1000 }

function runId() {
  const raw = process.env.GITHUB_RUN_ID || `${Date.now()}`
  return String(raw).replace(/\D/g, '').slice(-12) || String(Date.now()).slice(-12)
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

async function preparePendingFamilyReceipt(admin, studentNo) {
  const marker = runId()
  const reason = `Golden 关键确认回执 ${marker}`
  const result = '已向家长同步近期学习与实践安排，等待家长回执确认。'
  const profiles = items(await admin.get('/students', { keyword: studentNo, page: 1, pageSize: 50 }))
  const profile = profiles.find((row) => String(row.studentNo || row.loginName || '') === String(studentNo))
  if (!profile?.id) throw new Error(`Golden Batch 13 student profile ${studentNo} not found`)

  const existing = items(await admin.get(`/student-affairs/students/${profile.id}/family-contacts`, {
    page: 1, pageSize: 100
  })).find((row) => String(row.reason || '') === reason)

  if (!existing) {
    await admin.post(`/student-affairs/students/${profile.id}/family-contacts`, {
      contactType: 'PHONE',
      reason,
      result,
      fullPhoneView: false,
      viewReason: ''
    })
  }

  return {
    reason,
    studentId: String(profile.id),
    studentName: profile.realName || profile.studentName || studentNo
  }
}

test.describe.serial('Golden rollout · confirmation / document status · Batch 13', () => {
  let adminApi
  let internshipFixture
  let graduationFixture
  let familyReceipt

  test.beforeAll(async () => {
    internshipFixture = await loadInternshipFixture()
    graduationFixture = await prepareGraduationFixture()
    adminApi = await loginApi(config.sandboxAdmin)
    familyReceipt = await preparePendingFamilyReceipt(adminApi, internshipFixture.studentNo)
  })

  test('Student Affairs family receipt workspace · Screenshot A', async ({ page }, testInfo) => {
    await page.setViewportSize(VIEWPORT)
    await openStaffWorkspace(page, adminApi, '/admin/student-affairs/family/receipts')

    await expect(page).toHaveURL(/\/admin\/student-affairs\/family\/receipts/)
    await expect(page.getByRole('heading', { name: '家校回执', exact: true })).toBeVisible()
    await expect(page.locator('.sa-grid--metrics')).toBeVisible()
    await expect(page.locator('.fr-filters')).toBeVisible()

    const row = page.locator('.dt__tr').filter({ hasText: familyReceipt.reason }).first()
    await expect(row).toBeVisible()
    await expect(row).toContainText(familyReceipt.studentName)
    await expect(row).toContainText('待回执')
    await expect(row.getByRole('button', { name: '登记回执', exact: true })).toBeVisible()

    await capture(page, testInfo, 'rollout-confirmation-affairs-family-receipt-a')
  })

  test('Internship three-party agreement workspace · Screenshot A', async ({ page }, testInfo) => {
    await page.setViewportSize(VIEWPORT)
    const path = `/admin/internship/agreements?panel=issue&batchId=${encodeURIComponent(internshipFixture.batchId)}`
    await openStaffWorkspace(page, adminApi, path, {
      'internship.selectedBatchId': internshipFixture.batchId
    })

    await expect(page).toHaveURL(/\/admin\/internship\/agreements/)
    await expect(page.getByRole('heading', { name: '申请与协议办理', exact: true })).toBeVisible()
    await expect(page.locator('.ag-flow')).toBeVisible()
    await expect(page.locator('.ag-flow')).toContainText('发起协议')
    await expect(page.locator('.ag-flow')).toContainText('学生确认')
    await expect(page.locator('.ag-flow')).toContainText('企业确认')
    await expect(page.locator('.ag-flow')).toContainText('学校确认')
    await expect(page.locator('.ag-flow')).toContainText('归档留存')
    await expect(page.locator('.ag-flow__step.is-active')).toContainText('发起协议')
    await expect(page.getByText('请先选择批次', { exact: true })).toHaveCount(0)
    await expect(page.locator('.dt')).toBeVisible()

    await capture(page, testInfo, 'rollout-confirmation-internship-agreement-a')
  })

  test('Graduation final-submission confirmation workspace · Screenshot A', async ({ page }, testInfo) => {
    await page.setViewportSize(VIEWPORT)
    const path = `/admin/graduation/finals?batchId=${encodeURIComponent(graduationFixture.batchId)}`
    await openStaffWorkspace(page, adminApi, path)

    await expect(page).toHaveURL(/\/admin\/graduation\/finals/)
    await expect(page.getByRole('heading', { name: '成果检查', exact: true })).toBeVisible()
    await expect(page.locator('.mp-tabs')).toBeVisible()
    const pendingTab = page.getByRole('button', { name: /待审阅/ }).first()
    await expect(pendingTab).toBeVisible()
    await pendingTab.click()
    await expect(pendingTab).toHaveClass(/is-active/)
    await expect(page.locator('.fr-split')).toBeVisible()
    await expect(page.locator('.fr-list')).toBeVisible()
    await expect(page.locator('.fr-pane')).toBeVisible()

    await capture(page, testInfo, 'rollout-confirmation-graduation-finals-a')
  })
})
