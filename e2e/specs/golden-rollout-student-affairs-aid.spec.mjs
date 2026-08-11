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

test.describe.serial('Golden rollout · Student Affairs aid workbench · Screenshot B', () => {
  let adminApi
  let batch
  let batchName

  test.beforeAll(async () => {
    adminApi = await loginApi(config.sandboxAdmin)
    const rawRun = process.env.GITHUB_RUN_ID || `${Date.now()}`
    const runId = String(rawRun).replace(/\D/g, '').slice(-10) || String(Date.now()).slice(-10)
    batchName = `Playwright 困难认定 ${runId}`

    // Real production API fact in the isolated E2E tenant. Do not fabricate
    // student/KPI state: a real empty batch is enough to audit this workbench.
    batch = await adminApi.post('/student-affairs/aid/batches', {
      batchName,
      schoolYear: '2026-2027',
      publicityDays: 5,
      publish: true
    })
    expect(batch?.batchId).toBeTruthy()
  })

  test('real batch empty-state · Golden desktop contract · Screenshot B', async ({ page }, testInfo) => {
    await page.setViewportSize(DESKTOP)
    await openStaffWorkspace(page, adminApi, '/admin/student-affairs/aid')

    await expect(page).toHaveURL(/\/admin\/student-affairs\/aid/)
    await expect(page.getByRole('heading', { name: '困难认定工作台', exact: true })).toBeVisible()
    await expect(page.locator('.ad-batchbar')).toBeVisible()
    await expect(page.locator('.ad-toolbar')).toBeVisible()
    await expect(page.locator('.ad-workspace')).toBeVisible()
    await expect(page.locator('.ad-batchbar')).toContainText(batchName)
    await expect(page.locator('.ad-list')).toContainText('该批次暂无申请')
    await expect(page.locator('.ad-detail')).toContainText('请从左侧选择一条申请')

    const workspaceStyle = await page.locator('.ad-workspace').evaluate((el) => {
      const s = getComputedStyle(el)
      return { display: s.display, gridTemplateColumns: s.gridTemplateColumns, gap: s.gap }
    })
    expect(workspaceStyle.display).toBe('grid')
    expect(workspaceStyle.gridTemplateColumns.split(' ').filter(Boolean).length).toBe(2)
    expect(parseFloat(workspaceStyle.gap)).toBeGreaterThanOrEqual(12)

    const list = page.locator('.ad-list')
    const detail = page.locator('.ad-detail')
    const [listBox, detailBox] = await Promise.all([list.boundingBox(), detail.boundingBox()])
    expect(listBox?.width || 0).toBeGreaterThanOrEqual(330)
    expect(listBox?.width || 0).toBeLessThanOrEqual(390)
    expect(detailBox?.x || 0).toBeGreaterThan((listBox?.x || 0) + (listBox?.width || 0))
    expect(detailBox?.width || 0).toBeGreaterThan(listBox?.width || 0)

    const panelStyles = await Promise.all([list, detail].map((locator) => locator.evaluate((el) => {
      const s = getComputedStyle(el)
      return { borderRadius: s.borderRadius, borderTopStyle: s.borderTopStyle, minHeight: s.minHeight }
    })))
    for (const style of panelStyles) {
      expect(parseFloat(style.borderRadius)).toBeGreaterThanOrEqual(14)
      expect(style.borderTopStyle).not.toBe('none')
      expect(parseFloat(style.minHeight)).toBeGreaterThanOrEqual(350)
    }

    const emptyPanelStyle = await page.locator('.ad-list .ags-panel').evaluate((el) => {
      const s = getComputedStyle(el)
      return { borderTopStyle: s.borderTopStyle, boxShadow: s.boxShadow, minHeight: s.minHeight }
    })
    expect(emptyPanelStyle.borderTopStyle).toBe('none')
    expect(emptyPanelStyle.boxShadow).toBe('none')
    expect(parseFloat(emptyPanelStyle.minHeight)).toBeGreaterThanOrEqual(320)

    await expectNoHorizontalOverflow(page)
    await capture(page, testInfo, 'rollout-student-affairs-aid-b')
  })

  test('Golden responsive contract · workspace stacks at 1024px without overflow', async ({ page }) => {
    await page.setViewportSize({ width: 1024, height: 900 })
    await openStaffWorkspace(page, adminApi, '/admin/student-affairs/aid')

    const workspace = page.locator('.ad-workspace')
    const list = page.locator('.ad-list')
    const detail = page.locator('.ad-detail')
    await expect(workspace).toBeVisible()
    await expect(list).toContainText('该批次暂无申请')
    await expect(detail).toContainText('请从左侧选择一条申请')

    const cols = await workspace.evaluate((el) => getComputedStyle(el).gridTemplateColumns.split(' ').filter(Boolean).length)
    expect(cols).toBe(1)

    const [listBox, detailBox] = await Promise.all([list.boundingBox(), detail.boundingBox()])
    expect(Math.abs((listBox?.x || 0) - (detailBox?.x || 0))).toBeLessThanOrEqual(2)
    expect(detailBox?.y || 0).toBeGreaterThan((listBox?.y || 0) + (listBox?.height || 0))
    expect(listBox?.width || 0).toBeGreaterThan(500)

    const batchBar = page.locator('.ad-batchbar')
    const batchBarStyle = await batchBar.evaluate((el) => ({
      borderRadius: getComputedStyle(el).borderRadius,
      flexWrap: getComputedStyle(el).flexWrap
    }))
    expect(parseFloat(batchBarStyle.borderRadius)).toBeGreaterThanOrEqual(12)
    expect(batchBarStyle.flexWrap).toBe('wrap')

    await expectNoHorizontalOverflow(page)
  })
})