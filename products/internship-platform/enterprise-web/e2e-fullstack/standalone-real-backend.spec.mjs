import { test, expect } from '@playwright/test'

const apiPath = (response) => new URL(response.url()).pathname

async function expectApiOk(responsePromise, expectedPath) {
  const response = await responsePromise
  expect(apiPath(response)).toBe(expectedPath)
  expect(response.ok()).toBeTruthy()
  const payload = await response.json()
  expect(payload.code).toBe(0)
  return payload.data
}

test('admin teacher PC uses real MySQL auth RBAC and internship APIs end to end', async ({ page }) => {
  await page.goto('http://127.0.0.1:5176/login')
  await expect(page.getByRole('heading', { name: '学校管理 / 指导教师登录' })).toBeVisible()

  await page.getByLabel('学校编码').fill('YIYANG-FULLSTACK')
  await page.getByLabel('账号').fill('yiyang.fullstack.admin')
  await page.getByLabel('密码').fill('Fullstack-Admin-2026!')

  const loginResponse = page.waitForResponse(r =>
    apiPath(r) === '/api/v1/auth/browser-login' && r.request().method() === 'POST')
  const rbacResponse = page.waitForResponse(r =>
    apiPath(r) === '/api/v1/rbac/current-context' && r.request().method() === 'GET')
  const batchesResponse = page.waitForResponse(r =>
    apiPath(r) === '/api/v1/internship/batches' && r.request().method() === 'GET')
  const dashboardResponse = page.waitForResponse(r =>
    apiPath(r) === '/api/v1/internship/dashboard' && r.request().method() === 'GET')

  await page.getByRole('button', { name: '登录' }).click()

  const login = await expectApiOk(loginResponse, '/api/v1/auth/browser-login')
  expect(login.currentRole.roleCode).toBe('SCHOOL_ADMIN')
  expect(login.tenantId).toBe('88101')

  const rbac = await expectApiOk(rbacResponse, '/api/v1/rbac/current-context')
  expect(rbac.permissionPatterns).toContain('internship.*')
  expect(rbac.moduleEntitlements).toEqual(['internship'])

  const batches = await expectApiOk(batchesResponse, '/api/v1/internship/batches')
  expect(batches.total).toBe(1)
  expect(batches.items[0].batchName).toBe('2026岗位实习')

  await expectApiOk(dashboardResponse, '/api/v1/internship/dashboard')
  await expect(page).toHaveURL(/\/admin\/internship(?:\?|$)/)
  await expect(page.getByRole('heading', { name: '今日工作' })).toBeVisible()
  await expect(page.locator('select option:checked')).toContainText('2026岗位实习')
  await page.screenshot({ path: 'test-results-fullstack-pc/admin-real-backend.png', fullPage: true })
})

test('student PC uses real MySQL auth portal config and internship homepage end to end', async ({ page }) => {
  await page.goto('http://127.0.0.1:5201/student/login')
  await expect(page.getByRole('heading', { name: '学生端登录' })).toBeVisible()

  await page.getByLabel('学校编码').fill('YIYANG-FULLSTACK')
  await page.getByLabel('学号 / 登录账号').fill('202688013')
  await page.getByLabel('密码').fill('Fullstack-Student-2026!')

  const loginResponse = page.waitForResponse(r =>
    apiPath(r) === '/api/v1/auth/browser-login' && r.request().method() === 'POST')
  const portalConfigResponse = page.waitForResponse(r =>
    apiPath(r) === '/api/v1/mobile/me/portal-config' && r.request().method() === 'GET')
  const internshipMyResponse = page.waitForResponse(r =>
    apiPath(r) === '/api/v1/portal/internship/my' && r.request().method() === 'GET')

  await page.getByRole('button', { name: '登录' }).click()

  const login = await expectApiOk(loginResponse, '/api/v1/auth/browser-login')
  expect(login.currentRole.roleCode).toBe('STUDENT')
  expect(login.user.studentNo).toBe('202688013')

  const portalConfig = await expectApiOk(portalConfigResponse, '/api/v1/mobile/me/portal-config')
  expect(portalConfig.enabled).toBe(true)
  expect(portalConfig.modules.internship).toBe(true)
  expect(portalConfig.brand.schoolName).toBe('益阳职业技术学院')

  const my = await expectApiOk(internshipMyResponse, '/api/v1/portal/internship/my')
  expect(my.hasData).toBe(false)
  expect(my.needSelect).toBe(false)

  await expect(page).toHaveURL(/\/student\/internship(?:\?|$)/)
  await expect(page.getByText('益阳职业技术学院 · 岗位实习')).toBeVisible()
  await expect(page.getByText('学生李明')).toBeVisible()
  await expect(page.getByText('暂无实习记录', { exact: true })).toBeVisible()
  await page.screenshot({ path: 'test-results-fullstack-pc/student-real-backend.png', fullPage: true })
})
