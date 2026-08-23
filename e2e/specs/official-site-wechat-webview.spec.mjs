import { expect, test } from '@playwright/test'

const SIGN_ENDPOINT = '**/api/v1/notification/website-wechat-signature?*'
const LEAD_ENDPOINT = '**/api/v1/notification/website-lead'
const WECHAT_IOS_UA = 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_6 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148 MicroMessenger/8.0.60 NetType/WIFI Language/zh_CN'

async function expectNoOverflow(page, width) {
  await expect.poll(async () => page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width + 1)
  await expect.poll(async () => page.evaluate(() => document.body.scrollWidth)).toBeLessThanOrEqual(width + 1)
}

async function installWxMock(context) {
  await context.addInitScript(() => {
    let readyHandler = null
    let configCalled = false
    window.__wxCalls = []
    window.wx = {
      config(payload) {
        configCalled = true
        window.__wxCalls.push({ type: 'config', payload })
        setTimeout(() => readyHandler?.(), 0)
      },
      ready(handler) {
        readyHandler = handler
        if (configCalled) setTimeout(handler, 0)
      },
      error(handler) {
        window.__wxErrorHandler = handler
      },
      updateAppMessageShareData(payload) {
        window.__wxCalls.push({ type: 'friend', payload })
      },
      updateTimelineShareData(payload) {
        window.__wxCalls.push({ type: 'timeline', payload })
      }
    }
  })
}

test.describe('official website WeChat micro-site closure', () => {
  test('iOS WeChat SPA keeps entry URL for signature while sharing the current product page', async ({ browser }) => {
    const context = await browser.newContext({ userAgent: WECHAT_IOS_UA, viewport: { width: 375, height: 812 } })
    await installWxMock(context)
    const signedUrls = []
    await context.route(SIGN_ENDPOINT, async (route) => {
      const signedUrl = new URL(route.request().url()).searchParams.get('url')
      signedUrls.push(signedUrl)
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          data: {
            enabled: true,
            appId: 'wx-e2e',
            timestamp: 1787358000,
            nonceStr: 'nonce-e2e',
            signature: 'signature-e2e'
          }
        })
      })
    })

    const page = await context.newPage()
    await page.goto('/')
    await expect(page.locator('.yk-mobile-site-dock')).toBeVisible()
    await expect(page.locator('.yk-mobile-site-dock a')).toHaveCount(4)
    await expectNoOverflow(page, 375)
    await expect.poll(async () => page.evaluate(() => window.__wxCalls.some((item) => item.type === 'friend'))).toBe(true)

    await page.locator('a[aria-label="查看岗位实习详情"]').click()
    await expect(page).toHaveURL(/\/products\/internship$/)

    for (const width of [375, 390, 430]) {
      await page.setViewportSize({ width, height: 844 })
      await expect(page.locator('.yk-mobile-site-dock')).toBeVisible()
      await expectNoOverflow(page, width)
    }

    await expect.poll(async () => page.evaluate(() => {
      const friends = window.__wxCalls.filter((item) => item.type === 'friend')
      return friends.at(-1)?.payload?.title || ''
    })).toContain('岗位实习')

    expect(signedUrls.length).toBeGreaterThanOrEqual(2)
    const entryPath = new URL(signedUrls[0]).pathname
    expect(entryPath).toBe('/')
    for (const signedUrl of signedUrls) expect(new URL(signedUrl).pathname).toBe('/')

    const share = await page.evaluate(() => {
      const friends = window.__wxCalls.filter((item) => item.type === 'friend')
      return friends.at(-1)?.payload
    })
    expect(share.link).toBe('https://hnyueke.com/products/internship')
    expect(share.imgUrl).toMatch(/^https:\/\/hnyueke\.com\/official-site\//)
    await expect.poll(async () => page.evaluate(() => window.__wxCalls.map((item) => item.type))).toEqual(
      expect.arrayContaining(['config', 'friend', 'timeline'])
    )

    await context.close()
  })

  test('WeChat product context flows through dock into inquiry payload when JSSDK is not configured', async ({ browser }) => {
    const context = await browser.newContext({ userAgent: WECHAT_IOS_UA, viewport: { width: 390, height: 844 } })
    await installWxMock(context)
    await context.route(SIGN_ENDPOINT, (route) => route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ data: { enabled: false } })
    }))

    let payload = null
    await context.route(LEAD_ENDPOINT, async (route) => {
      payload = route.request().postDataJSON()
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ data: { accepted: true } })
      })
    })

    const page = await context.newPage()
    await page.goto('/products/graduation')
    await page.locator('.yk-mobile-site-dock [data-key="contact"]').click()
    await expect(page).toHaveURL(/\/contact\?product=graduation$/)
    await expect(page.locator('.yk-lead-form select')).toHaveValue('毕业设计')

    const form = page.locator('.yk-lead-form')
    await form.locator('input[autocomplete="organization"]').fill('微信微官网验收职业学院')
    await form.locator('input[autocomplete="name"]').fill('王老师')
    await form.locator('input[autocomplete="tel"]').fill('13800138000')
    await form.locator('textarea').fill('微信内置浏览器咨询表单验收')
    await form.getByRole('button', { name: '提交并短信通知跃科' }).click()

    await expect(page.getByRole('status')).toContainText('不会写入跃科业务数据库')
    expect(payload).toEqual(expect.objectContaining({
      school_name: '微信微官网验收职业学院',
      contact_name: '王老师',
      phone: '13800138000',
      interest: '毕业设计',
      message: '微信内置浏览器咨询表单验收'
    }))
    await expectNoOverflow(page, 390)
    await context.close()
  })
})
