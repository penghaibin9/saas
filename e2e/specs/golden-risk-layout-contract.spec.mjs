import { test, expect } from '../lib/observability.mjs'
import { openGoldenStaffPage } from '../lib/golden-staff-page.mjs'

const VIEWPORT = { width: 1440, height: 1000 }

test('Golden risk layout contract · five metrics fit one compact desktop row', async ({ page }, testInfo) => {
  await page.setViewportSize(VIEWPORT)
  await openGoldenStaffPage(page, '/admin/student-affairs/risk')
  const metrics = page.getByLabel('业务统计', { exact: true })
  await expect(metrics).toBeVisible()
  await expect(metrics.locator('dt')).toHaveText(['风险记录', '高危/危急', '未闭环', '待分派', '超时'])
  const evidence = await metrics.evaluate((el) => ({
    width: window.innerWidth,
    rect: el.getBoundingClientRect().toJSON(),
    items: Array.from(el.children).map(item => item.getBoundingClientRect().toJSON())
  }))
  await testInfo.attach('student-affairs-risk-layout-contract', {
    body: Buffer.from(JSON.stringify(evidence, null, 2)), contentType: 'application/json'
  })
  expect(evidence.items).toHaveLength(5)
  expect(new Set(evidence.items.map(item => Math.round(item.top))).size).toBe(1)
  expect(evidence.rect.height).toBeLessThanOrEqual(100)
  expect(evidence.rect.left).toBeGreaterThanOrEqual(0)
  expect(evidence.rect.right).toBeLessThanOrEqual(VIEWPORT.width)
  await expect(page.getByRole('navigation', { name: '风险快捷队列' })).toBeVisible()
})
