import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { loginApi, prepareGraduationFixture } from '../lib/api-fixture.mjs'

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

async function openStaffWorkspace(page, api, path) {
  await page.addInitScript(({ token }) => {
    window.sessionStorage.setItem('gx_pc_token_v1', token)
  }, { token: api.token })
  await page.goto(`${config.staffBaseUrl}${path}`)
  await dismissGuide(page)
}

test.describe.serial('Golden rollout · exception / recovery workspaces · Batch 11', () => {
  let adminApi
  let graduationFixture

  test.beforeAll(async () => {
    adminApi = await loginApi(config.sandboxAdmin)
    graduationFixture = await prepareGraduationFixture()
  })

  test('Student Affairs leave follow-up · Screenshot B', async ({ page }, testInfo) => {
    await page.setViewportSize(VIEWPORT)
    await openStaffWorkspace(page, adminApi, '/admin/student-affairs/leave/followup')

    await expect(page).toHaveURL(/\/admin\/student-affairs\/leave\/followup/)
    await expect(page.getByRole('heading', { name: '延期销假', exact: true })).toBeVisible()
    await expect(page.locator('.bar')).toBeVisible()
    await expect(page.locator('.dpw')).toBeVisible()
    await expect(page.locator('.lv-main')).toBeVisible()
    await expect(page.getByRole('button', { name: '扫描逾期未销', exact: true })).toBeVisible()

    const affairsVisual = await page.locator('.dpw').evaluate((node) => {
      const aside = node.querySelector('.dpw__aside')
      const main = node.querySelector('.lv-main')
      const asideRect = aside.getBoundingClientRect()
      const mainRect = main.getBoundingClientRect()
      return {
        asideMinHeight: parseFloat(getComputedStyle(aside).minHeight),
        mainMinHeight: parseFloat(getComputedStyle(main).minHeight),
        asideWidth: asideRect.width,
        mainWidth: mainRect.width
      }
    })
    expect(affairsVisual.asideMinHeight).toBeLessThanOrEqual(250)
    expect(affairsVisual.mainMinHeight).toBeLessThanOrEqual(250)
    expect(affairsVisual.asideWidth).toBeGreaterThanOrEqual(340)
    expect(affairsVisual.mainWidth).toBeGreaterThan(600)

    await capture(page, testInfo, 'rollout-exception-affairs-leave-followup-b')
  })

  test('Graduation delayed-defense administration · Screenshot B', async ({ page }, testInfo) => {
    await page.setViewportSize(VIEWPORT)
    const path = `/admin/graduation?extension=delay&batchId=${encodeURIComponent(graduationFixture.batchId)}`
    await openStaffWorkspace(page, adminApi, path)

    await expect(page).toHaveURL(/\/admin\/graduation\?extension=delay/)
    await expect(page.getByRole('heading', { name: '延期答辩管理', exact: true })).toBeVisible()
    await expect(page.locator('.ext-hero')).toBeVisible()
    await expect(page.locator('.ext-main-tabs')).toBeVisible()
    await expect(page.locator('.ext-filter-bar')).toBeVisible()
    await expect(page.getByText(/学生申请 → 导师审核 → 专业复核 → 学院审批 → 重新排期/)).toBeVisible()
    await expect(page.locator('.ext-main-tabs .mp-tab.is-active')).toContainText('延期答辩')

    const graduationVisual = await page.locator('.ext-hero').evaluate((node) => {
      const style = getComputedStyle(node)
      const kpis = node.querySelectorAll('.ext-kpis > div')
      return {
        radius: parseFloat(style.borderTopLeftRadius),
        paddingTop: parseFloat(style.paddingTop),
        kpiCount: kpis.length
      }
    })
    const filterHeight = await page.locator('.ext-filter').first().evaluate((node) => parseFloat(getComputedStyle(node).minHeight))
    const cardRadius = await page.locator('.mp-stack > .mp-card').first().evaluate((node) => parseFloat(getComputedStyle(node).borderTopLeftRadius))
    expect(graduationVisual.radius).toBeGreaterThanOrEqual(16)
    expect(graduationVisual.paddingTop).toBeGreaterThanOrEqual(14)
    expect(graduationVisual.kpiCount).toBe(3)
    expect(filterHeight).toBeGreaterThanOrEqual(32)
    expect(cardRadius).toBeGreaterThanOrEqual(14)

    await capture(page, testInfo, 'rollout-exception-graduation-delay-b')
  })
})
