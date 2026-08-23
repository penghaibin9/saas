import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'

test.describe('Official website P0 sales-story closure', () => {
  test('desktop homepage leads with sales value, visible login, lifecycle, products, platform and delivery', async ({ page }) => {
    await page.goto(`${config.staffBaseUrl}/`)
    await expect(page.getByRole('heading', { level: 1, name: /把学生从入校到就业/ })).toBeVisible()
    await expect(page.getByRole('heading', { name: /选择身份，直接进入系统/ })).toBeVisible()
    await expect(page.locator('#login .yk-login-card')).toHaveCount(3)
    await expect(page.getByRole('heading', { name: /把分散的工作/ })).toBeVisible()
    await expect(page.getByRole('heading', { name: /从迎新到就业/ })).toBeVisible()
    await expect(page.getByRole('heading', { name: /覆盖学校最重/ })).toBeVisible()
    await expect(page.locator('#products .yk-home-product-card')).toHaveCount(4)
    await expect(page.getByRole('heading', { name: /统一工作、协同与治理/ })).toBeVisible()
    await expect(page.getByRole('heading', { name: /四步完成部署与落地/ })).toBeVisible()
    await expect(page.locator('#faq details')).toHaveCount(6)
  })

  for (const width of [375, 390, 430]) {
    test(`mobile ${width}px keeps story sections readable without horizontal overflow`, async ({ page }) => {
      await page.setViewportSize({ width, height: 844 })
      await page.goto(`${config.staffBaseUrl}/`)
      const metrics = await page.evaluate(() => ({ scrollWidth: document.documentElement.scrollWidth, clientWidth: document.documentElement.clientWidth }))
      expect(metrics.scrollWidth).toBeLessThanOrEqual(metrics.clientWidth + 1)
      await expect(page.locator('#login')).toBeVisible()
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
    await expect(page.locator('#eight-highlights')).toBeVisible()
    await expect(page.getByText('跃科平台八大特色', { exact: true })).toBeVisible()
    await expect(page.getByRole('heading', { name: /围绕学生、材料、审批、证据与协同/ })).toBeVisible()
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
