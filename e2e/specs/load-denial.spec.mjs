import { test, expect } from '@playwright/test'

// Use a real teacher in a dedicated test school without the academic module entitlement.
// No permission mutation, database cleanup, auth injection or intercepted responses.
test('teacher PC: real denied navigation explains access rather than reporting load failure', async ({ page }) => {
  const pageErrors = []
  const denials = []
  page.on('pageerror', error => pageErrors.push(error.message))
  page.on('response', response => {
    if (response.status() === 403 && response.url().includes('/api/v1/')) {
      denials.push(new URL(response.url()).pathname)
    }
  })
  await page.goto(`/login?tenant=${encodeURIComponent(process.env.E2E_DENIAL_TENANT)}`)
  await page.getByRole('button', { name: '账号登录', exact: true }).click()
  await page.locator('#staff-account').fill(process.env.E2E_DENIAL_USERNAME)
  await page.locator('#staff-password').fill(process.env.E2E_DENIAL_PASSWORD)
  await page.getByLabel('我已阅读并同意学校提供的用户协议与隐私政策').check()
  const login = page.waitForResponse(response => response.url().includes('/auth/browser-login') && response.request().method() === 'POST')
  await page.getByRole('button', { name: '进入教师工作台', exact: true }).click()
  expect((await login).status()).toBe(200)
  await expect(page.getByTitle('查看账号与切换身份').first()).toBeVisible()
  await page.goto('/admin/academic-affairs')
  const deniedNotice = page.locator('.route-access-notice')
  await expect(deniedNotice).toBeVisible()
  await expect(deniedNotice).toContainText(/暂不能办理此业务|缺少此页面所需权限|暂无访问权限|无权访问|本校未开通该模块|学校尚未开通此模块/)
  await expect(page.getByText(/教务中心加载失败|数据加载出现问题/)).toHaveCount(0)
  await expect(page.getByRole('button', { name: '重试', exact: true })).toHaveCount(0)
  expect(pageErrors).toEqual([])
  await expect(page).toHaveURL(/\/admin\/academic-affairs(?:[/?#]|$)/)
  await page.screenshot({ path: 'test-results/denial/teacher-access-denied.png', fullPage: true })

  // Separate component integration: use the real browser session/client and actual
  // protected API response. This does not bypass the production route guard.
  await page.getByRole('button', { name: '返回工作台', exact: true }).click()
  await expect(page).toHaveURL(/\/workbench/)
  const result = await page.evaluate(async () => {
    const { createApp, h } = await import('/node_modules/.vite/deps/vue.js')
    const { default: ErrorState } = await import('/src/components/business/ErrorState.vue')
    const { request } = await import('/src/services/http/client.js')
    let denied
    try { await request('/mobile/academic/teacher-schedule/my') } catch (error) { denied = error }
    if (!denied) throw new Error('Expected real backend refusal, got success')
    const container = document.createElement('section')
    container.id = 'denial-component-regression'
    document.body.append(container)
    createApp({ render: () => h(ErrorState, { error: denied, title: '教务中心加载失败' }) }).mount(container)
    return { status: denied.httpStatus, code: denied.code }
  })
  expect(result.status).toBe(403)
  const panel = page.locator('#denial-component-regression')
  await expect(panel.getByText('本校未开通该模块', { exact: true })).toBeVisible()
  await expect(panel.getByText('教务中心加载失败')).toHaveCount(0)
  await expect(panel.getByRole('button', { name: '重试', exact: true })).toHaveCount(0)
  expect(denials.length).toBeGreaterThan(0)
  expect(pageErrors).toEqual([])
  await panel.screenshot({ path: 'test-results/denial/pc-backend-403-component.png' })
  console.log('Observed denied API paths:', [...new Set(denials)])
})
