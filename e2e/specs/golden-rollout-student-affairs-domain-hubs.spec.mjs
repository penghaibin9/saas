import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { loginApi } from '../lib/api-fixture.mjs'

const DESKTOP = { width: 1440, height: 1000 }

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

test.describe.serial('Golden rollout · Student Affairs domain hubs · A/B', () => {
  let adminApi
  let dormBuildingName
  let activityName

  test.beforeAll(async () => {
    adminApi = await loginApi(config.sandboxAdmin)
    const rawRun = process.env.GITHUB_RUN_ID || `${Date.now()}`
    const runId = String(rawRun).replace(/\D/g, '').slice(-10) || String(Date.now()).slice(-10)

    dormBuildingName = `Playwright 宿舍治理 ${runId}`
    const building = await adminApi.post('/student-affairs/dorm/buildings', {
      buildingName: dormBuildingName,
      buildingCode: `PW-DORM-${runId}`,
      genderLimit: 'MIXED',
      floors: 2,
      roomsPerFloor: 2,
      bedsPerRoom: 4
    })
    expect(building?.buildingId).toBeTruthy()

    activityName = `Playwright 第二课堂治理 ${runId}`
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

  test('Dormitory management real resource state · Screenshot B', async ({ page }, testInfo) => {
    await page.setViewportSize(DESKTOP)
    await openStaffWorkspace(page, adminApi, '/admin/student-affairs/dormitory')

    await expect(page).toHaveURL(/\/admin\/student-affairs\/dormitory/)
    await expect(page.getByRole('heading', { name: '宿舍管理', exact: true })).toBeVisible()
    await expect(page.getByText(dormBuildingName, { exact: true })).toBeVisible()
    await expect(page.getByText('总床位', { exact: true })).toBeVisible()
    await expect(page.getByText('16', { exact: true }).first()).toBeVisible()
    await expect(page.getByText('房间管理', { exact: true })).toBeVisible()
    await expect(page.getByText('床位管理 / 入住退宿', { exact: true })).toBeVisible()

    const archive = page.locator('.app-desc-list').last()
    const assignItem = archive.locator('.app-desc-list__item').first()
    const assignValue = assignItem.locator('.app-desc-list__value')
    await expect(assignValue).toContainText('COUNSELOR_ASSIGN')

    const archiveStyle = await archive.evaluate((el) => {
      const s = getComputedStyle(el)
      return { borderRadius: s.borderRadius, borderTopStyle: s.borderTopStyle }
    })
    expect(parseFloat(archiveStyle.borderRadius)).toBeGreaterThanOrEqual(10)
    expect(archiveStyle.borderTopStyle).not.toBe('none')

    const [archiveBox, assignBox, valueBox] = await Promise.all([
      archive.boundingBox(),
      assignItem.boundingBox(),
      assignValue.boundingBox()
    ])
    expect(assignBox?.width || 0).toBeGreaterThan((archiveBox?.width || 0) * 0.85)
    expect(valueBox?.width || 0).toBeGreaterThanOrEqual(150)
    const valueStyle = await assignValue.evaluate((el) => ({
      wordBreak: getComputedStyle(el).wordBreak,
      overflowWrap: getComputedStyle(el).overflowWrap
    }))
    expect(valueStyle.wordBreak).toBe('normal')
    expect(['anywhere', 'break-word']).toContain(valueStyle.overflowWrap)
    await expectNoHorizontalOverflow(page)

    await capture(page, testInfo, 'rollout-student-affairs-dormitory-b')
  })

  test('Dormitory archive entry remains readable at 1024px', async ({ page }) => {
    await page.setViewportSize({ width: 1024, height: 900 })
    await openStaffWorkspace(page, adminApi, '/admin/student-affairs/dormitory')

    const archive = page.locator('.app-desc-list').last()
    await expect(archive).toBeVisible()
    const columns = await archive.evaluate((el) => getComputedStyle(el).gridTemplateColumns.split(' ').filter(Boolean).length)
    expect(columns).toBe(1)
    await expect(archive.locator('.app-desc-list__value').first()).toContainText('COUNSELOR_ASSIGN')
    await expectNoHorizontalOverflow(page)
  })

  test('Student activity real draft state · Screenshot A frozen', async ({ page }, testInfo) => {
    await page.setViewportSize(DESKTOP)
    await openStaffWorkspace(page, adminApi, '/admin/student-affairs/activity')

    await expect(page).toHaveURL(/\/admin\/student-affairs\/activity/)
    await expect(page.getByRole('heading', { name: '学生活动管理', exact: true })).toBeVisible()
    await expect(page.locator('.sa-summary-strip')).toBeVisible()
    await expect(page.locator('.sa-workflow-strip')).toBeVisible()
    const row = page.locator('tbody tr').filter({ hasText: activityName }).first()
    await expect(row).toBeVisible()
    await expect(row).toContainText('草稿')
    await expect(row).toContainText('2')

    await capture(page, testInfo, 'rollout-student-affairs-activity-a')
  })

  test('Mental attention privacy-governed state · Screenshot A frozen', async ({ page }, testInfo) => {
    await page.setViewportSize(DESKTOP)
    await openStaffWorkspace(page, adminApi, '/admin/student-affairs/mental')

    await expect(page).toHaveURL(/\/admin\/student-affairs\/mental/)
    await expect(page.getByRole('heading', { name: '心理关注名单', exact: true })).toBeVisible()
    await expect(page.locator('.mental-privacy-summary')).toBeVisible()
    await expect(page.locator('.sa-workflow-strip')).toBeVisible()
    await expect(page.getByText('关注名单（明细默认遮蔽）', { exact: true })).toBeVisible()
    await expect(page.getByText(/逐生授权|明细默认脱敏/).first()).toBeVisible()

    // Deliberately no sensitive mental-health fixture and no reveal action.
    // This evidence only audits the privacy-governed workspace shell and truthful authorized state.
    await capture(page, testInfo, 'rollout-student-affairs-mental-a')
  })
})
