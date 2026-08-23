import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'

test.describe('Official website P0 sales-story closure', () => {
  test('desktop homepage explains pains, lifecycle, work hub, orientation, platform and delivery without login', async ({ page }) => {
    await page.goto(`${config.staffBaseUrl}/`)
    await expect(page.getByRole('heading', { name: /系统已经不少，为什么老师还是忙/ })).toBeVisible()
    await expect(page.getByRole('heading', { name: /迎新.*在校.*教学.*实习.*毕设.*就业衔接/ })).toBeVisible()
    await expect(page.getByRole('heading', { name: /工作台、审批、消息/ })).toBeVisible()
    await expect(page.getByRole('heading', { name: /从到校前开始在线报到/ })).toBeVisible()
    await expect(page.getByRole('heading', { name: /学校级身份、权限、数据和治理边界/ })).toBeVisible()
    await expect(page.getByRole('heading', { name: /学校初始化、历史数据、角色权限/ })).toBeVisible()
    await expect(page.locator('#faq details')).toHaveCount(6)
  })

  for (const width of [375, 390, 430]) {
    test(`mobile ${width}px keeps story sections readable without horizontal overflow`, async ({ page }) => {
      await page.setViewportSize({ width, height: 844 })
      await page.goto(`${config.staffBaseUrl}/`)
      const metrics = await page.evaluate(() => ({ scrollWidth: document.documentElement.scrollWidth, clientWidth: document.documentElement.clientWidth }))
      expect(metrics.scrollWidth).toBeLessThanOrEqual(metrics.clientWidth + 1)
      await expect(page.locator('#lifecycle')).toBeVisible()
      await expect(page.locator('#platform')).toBeVisible()
    })
  }

  test('orientation sales route is public and uses real evidence', async ({ page }) => {
    await page.goto(`${config.staffBaseUrl}/solutions/orientation`)
    await expect(page.getByRole('heading', { name: /让新生从到校前就开始在线报到/ })).toBeVisible()
    await expect(page.getByText('预报到信息', { exact: true })).toBeVisible()
    await expect(page.locator('img[src="/official-site/orientation-overview.webp"]').first()).toBeVisible()
    await expect(page.locator('img[src="/official-site/orientation-progress.webp"]').first()).toBeVisible()
  })

  test('platform page presents eight highlights with truthful current and evolving states', async ({ page }) => {
    await page.goto(`${config.staffBaseUrl}/platform`)
    await expect(page.getByRole('heading', { level: 1, name: /企业级数字工作平台能力/ })).toBeVisible()
    await expect(page.getByRole('heading', { name: /跃科平台八大特色/ })).toBeVisible()
    await expect(page.getByText('学生 360° 成长工作台', { exact: true }).first()).toBeVisible()
    await expect(page.getByText('统一安全文件与版本中心', { exact: true }).first()).toBeVisible()
    await expect(page.getByText('跨业务统一审批中心', { exact: true }).first()).toBeVisible()
    await expect(page.getByText('四端在线文档预览与批阅', { exact: true })).toBeVisible()
    await expect(page.getByText('持续演进', { exact: true }).first()).toBeVisible()
    await expect(page.getByText('当前具备', { exact: true }).first()).toBeVisible()
    await expect(page.locator('img[src="/official-site/approval-center.webp"]')).toBeVisible()
  })

  test('platform page remains readable on a 390px phone', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 })
    await page.goto(`${config.staffBaseUrl}/platform`)
    const metrics = await page.evaluate(() => ({ scrollWidth: document.documentElement.scrollWidth, clientWidth: document.documentElement.clientWidth }))
    expect(metrics.scrollWidth).toBeLessThanOrEqual(metrics.clientWidth + 1)
    await expect(page.locator('#eight-highlights')).toBeVisible()
  })
})
