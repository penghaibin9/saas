import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { items, loginApi } from '../lib/api-fixture.mjs'

const DESKTOP = { width: 1440, height: 1000 }

function marker() {
  const raw = process.env.GITHUB_RUN_ID || `${Date.now()}`
  const run = String(raw).replace(/\D/g, '').slice(-10) || String(Date.now()).slice(-10)
  return `${run}-${process.pid}-${Date.now()}`
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

async function openStaffWorkspace(page, api, path) {
  await page.addInitScript((token) => {
    window.sessionStorage.setItem('gx_pc_token_v1', token)
  }, api.token)
  await page.goto(`${config.staffBaseUrl}${path}`)
  await dismissGuide(page)
}

async function expectNoHorizontalOverflow(page) {
  const overflow = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    innerWidth: window.innerWidth
  }))
  expect(overflow.scrollWidth).toBeLessThanOrEqual(overflow.innerWidth + 1)
}

test.describe.serial('Student Affairs V3 domain hubs · corrected SA-009 evidence', () => {
  let adminApi
  let dormBuildingName
  let dormBuildingCode
  let activityName

  test.beforeAll(async () => {
    adminApi = await loginApi(config.sandboxAdmin)
    const id = marker()

    dormBuildingName = `SA-009 宿舍治理 ${id}`
    dormBuildingCode = `SA009-${id}`
    const building = await adminApi.post('/student-affairs/dorm/buildings', {
      buildingName: dormBuildingName,
      buildingCode: dormBuildingCode,
      genderLimit: 'MIXED',
      floors: 2,
      roomsPerFloor: 2,
      bedsPerRoom: 4
    })
    expect(building?.buildingId).toBeTruthy()

    // Per-building capacity is 16. Global occupancy can legitimately be larger because
    // other E2E buildings exist, so never assert the page-wide metric equals 16.
    const buildings = items(await adminApi.get('/student-affairs/dorm/buildings', { page: 1, pageSize: 200 }))
    const created = buildings.find((row) => String(row.buildingCode || '') === dormBuildingCode)
    expect(created, 'new SA-009 building must be listed').toBeTruthy()
    expect(Number(created.totalBeds)).toBe(16)
    expect(Number(created.vacantBeds)).toBe(16)

    activityName = `Playwright 第二课堂治理 ${id}`
    const activity = await adminApi.post('/student-affairs/activities', {
      activityName,
      activityType: 'ACTIVITY',
      location: 'Playwright 综合活动中心',
      quota: 30,
      creditType: 'SECOND_CLASS',
      creditValue: 2
    })
    expect(activity?.activityId).toBeTruthy()
    expect(String(activity?.status || '').toUpperCase()).toBe('DRAFT')
  })

  test('SA-009 Dormitory management shows the uniquely created building', async ({ page }) => {
    await page.setViewportSize(DESKTOP)
    await openStaffWorkspace(page, adminApi, '/admin/student-affairs/dormitory')

    await expect(page).toHaveURL(/\/admin\/student-affairs\/dormitory/)
    await expect(page.getByRole('heading', { name: '宿舍管理', exact: true })).toBeVisible()
    await expect(page.getByText(dormBuildingName, { exact: true })).toHaveCount(1)
    await expect(page.getByText(dormBuildingName, { exact: true })).toBeVisible()
    await expect(page.getByText('总床位', { exact: true })).toBeVisible()
    await expect(page.getByText('房间管理', { exact: true })).toBeVisible()
    await expect(page.getByText('床位管理 / 入住退宿', { exact: true })).toBeVisible()

    const archive = page.locator('.app-desc-list').last()
    const assignItem = archive.locator('.app-desc-list__item').first()
    const assignValue = assignItem.locator('.app-desc-list__value')
    await expect(assignValue).toContainText('COUNSELOR_ASSIGN')
    await expectNoHorizontalOverflow(page)
  })

  test('SA-009 Dormitory archive remains readable at 1024px', async ({ page }) => {
    await page.setViewportSize({ width: 1024, height: 900 })
    await openStaffWorkspace(page, adminApi, '/admin/student-affairs/dormitory')

    const archive = page.locator('.app-desc-list').last()
    await expect(archive).toBeVisible()
    const columns = await archive.evaluate((el) => getComputedStyle(el).gridTemplateColumns.split(' ').filter(Boolean).length)
    expect(columns).toBe(1)
    await expect(archive.locator('.app-desc-list__value').first()).toContainText('COUNSELOR_ASSIGN')
    await expectNoHorizontalOverflow(page)
  })

  test('SA-015 Student activity real draft state', async ({ page }) => {
    await page.setViewportSize(DESKTOP)
    await openStaffWorkspace(page, adminApi, '/admin/student-affairs/activity')

    await expect(page).toHaveURL(/\/admin\/student-affairs\/activity/)
    await expect(page.getByRole('heading', { name: '学生活动管理', exact: true })).toBeVisible()
    const row = page.locator('tbody tr').filter({ hasText: activityName }).first()
    await expect(row).toBeVisible()
    await expect(row).toContainText('草稿')
    await expect(row).toContainText('2')
  })

  test('SA-014 Mental attention privacy-governed workspace', async ({ page }) => {
    await page.setViewportSize(DESKTOP)
    await openStaffWorkspace(page, adminApi, '/admin/student-affairs/mental')

    await expect(page).toHaveURL(/\/admin\/student-affairs\/mental/)
    await expect(page.getByRole('heading', { name: '心理关注名单', exact: true })).toBeVisible()
    await expect(page.locator('.mental-privacy-summary')).toBeVisible()
    await expect(page.locator('.sa-workflow-strip')).toBeVisible()
    await expect(page.getByText('关注名单（明细默认遮蔽）', { exact: true })).toBeVisible()
    await expect(page.getByText(/逐生授权|明细默认脱敏/).first()).toBeVisible()
  })
})
