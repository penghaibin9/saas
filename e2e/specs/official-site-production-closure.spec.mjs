import { expect, test } from '@playwright/test'

const LEAD_ENDPOINT = '**/api/v1/notification/website-lead'

async function expectNoHorizontalOverflow(page) {
  await expect.poll(async () => page.evaluate(() => ({
    viewport: window.innerWidth,
    documentWidth: document.documentElement.scrollWidth,
    bodyWidth: document.body?.scrollWidth || 0
  }))).toEqual(expect.objectContaining({ viewport: 390 }))

  const overflow = await page.evaluate(() => ({
    viewport: window.innerWidth,
    documentWidth: document.documentElement.scrollWidth,
    bodyWidth: document.body?.scrollWidth || 0
  }))
  expect(overflow.documentWidth, JSON.stringify(overflow)).toBeLessThanOrEqual(overflow.viewport + 1)
  expect(overflow.bodyWidth, JSON.stringify(overflow)).toBeLessThanOrEqual(overflow.viewport + 1)
}

async function fillLeadForm(page, {
  school = '跃科官网验收职业学院',
  contact = '张老师',
  phone = '13800138000',
  message = '官网上线收口自动化验证'
} = {}) {
  const form = page.locator('.yk-lead-form')
  await form.locator('input[autocomplete="organization"]').fill(school)
  await form.locator('input[autocomplete="name"]').fill(contact)
  await form.locator('input[autocomplete="tel"]').fill(phone)
  await form.locator('textarea').fill(message)
  return form
}

test.describe('official website production closure', () => {
  test('desktop product CTA carries source product into the contact form', async ({ page }) => {
    await page.goto('/')
    await expect(page.locator('.yk-site')).toBeVisible()
    await expect(page.getByText('135 4966 6867').first()).toBeVisible()

    await page.goto('/products/academic-affairs')
    await expect(page.getByRole('heading', { level: 1, name: '教务系统' })).toBeVisible()
    await page.getByRole('link', { name: '预约产品演示' }).first().click()

    await expect(page).toHaveURL(/\/contact\?product=academic-affairs$/)
    await expect(page.locator('.yk-lead-form select')).toHaveValue('教务系统')
    await expect(page.getByText('不进入业务数据库', { exact: true })).toBeVisible()
    await expect(page.locator('a[href="tel:13549666867"]').first()).toBeVisible()
  })

  test('390px mobile public pages do not overflow and invalid phone never calls the lead API', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 })

    for (const path of ['/', '/products/internship', '/contact?product=internship']) {
      await page.goto(path)
      await expect(page.locator('.yk-site')).toBeVisible()
      await expectNoHorizontalOverflow(page)
    }

    let leadRequests = 0
    page.on('request', (request) => {
      if (request.url().includes('/api/v1/notification/website-lead')) leadRequests += 1
    })

    const form = await fillLeadForm(page, { phone: '123456' })
    await form.getByRole('button', { name: '提交并短信通知跃科' }).click()
    await expect(page.getByRole('alert')).toHaveText('请输入有效的 11 位手机号')
    expect(leadRequests).toBe(0)
  })

  test('contact submission sends the intended no-database SMS payload and renders success', async ({ page }) => {
    let payload = null
    await page.route(LEAD_ENDPOINT, async (route) => {
      payload = route.request().postDataJSON()
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ data: { accepted: true } })
      })
    })

    await page.goto('/contact?product=graduation')
    const form = await fillLeadForm(page)
    await expect(form.locator('select')).toHaveValue('毕业设计')
    await form.getByRole('button', { name: '提交并短信通知跃科' }).click()

    await expect(page.getByRole('status')).toContainText('不会写入跃科业务数据库')
    expect(payload).toEqual({
      school_name: '跃科官网验收职业学院',
      contact_name: '张老师',
      phone: '13800138000',
      interest: '毕业设计',
      message: '官网上线收口自动化验证',
      website: ''
    })
  })

  test('real E2E backend fails safely when live SMS is disabled', async ({ page }) => {
    await page.goto('/contact?product=internship')
    const form = await fillLeadForm(page, {
      school: '官网短信安全降级职业学院',
      phone: '13900139000',
      message: '验证测试环境关闭短信时不会虚报成功'
    })
    await expect(form.locator('select')).toHaveValue('岗位实习')
    await form.getByRole('button', { name: '提交并短信通知跃科' }).click()

    await expect(page.getByRole('alert')).toContainText('提交失败，请直接电话联系 135 4966 6867')
    await expect(page.getByRole('status')).toHaveCount(0)
  })
})
