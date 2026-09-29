import { test, expect } from '@playwright/test'

const apiPath = response => new URL(response.url()).pathname

async function payload(responsePromise, path) {
  const response = await responsePromise
  expect(apiPath(response)).toBe(path)
  expect(response.ok()).toBeTruthy()
  const body = await response.json()
  expect(body.code).toBe(0)
  return body.data
}

test('enterprise HR logs into real MySQL context and enters recruitment home', async ({ page }) => {
  await page.goto('login')
  await expect(page.getByRole('heading', { name: '企业协同中心' })).toBeVisible()

  await page.getByLabel('学校编码').fill('YIYANG-ENTERPRISE')
  await page.getByLabel('手机号或登录账号').fill('enterprise.fullstack.hr')
  await page.getByLabel('密码').fill('Enterprise-Evidence-2026!')

  const loginResponse = page.waitForResponse(r =>
    apiPath(r) === '/api/v1/internship/enterprise-portal/auth/browser-login' &&
    r.request().method() === 'POST')
  const campaignsResponse = page.waitForResponse(r =>
    apiPath(r) === '/api/v1/internship/enterprise-portal/campaigns' &&
    r.request().method() === 'GET')

  await page.getByRole('button', { name: '登录' }).click()

  const login = await payload(loginResponse, '/api/v1/internship/enterprise-portal/auth/browser-login')
  expect(login.context.tenantCode).toBe('YIYANG-ENTERPRISE')
  expect(login.context.memberRole).toBe('HR')
  expect(login.context.companyId).toBe('88251')

  const campaigns = await payload(campaignsResponse, '/api/v1/internship/enterprise-portal/campaigns')
  expect(campaigns).toHaveLength(1)
  expect(campaigns[0].campaignName).toBe('2026岗位实习企业双选')
  expect(campaigns[0].recruitmentAvailable).toBe(true)

  await expect(page.getByRole('heading', { name: '选择招聘季' })).toBeVisible()

  const contextResponse = page.waitForResponse(r =>
    apiPath(r) === '/api/v1/internship/enterprise-portal/context' &&
    r.request().method() === 'GET')
  const dashboardResponse = page.waitForResponse(r =>
    apiPath(r) === '/api/v1/internship/enterprise-portal/dashboard' &&
    r.request().method() === 'GET')
  const companyResponse = page.waitForResponse(r =>
    apiPath(r) === '/api/v1/internship/enterprise-portal/company' &&
    r.request().method() === 'GET')

  await page.getByRole('button').filter({ hasText: '2026岗位实习企业双选' }).click()

  const context = await payload(contextResponse, '/api/v1/internship/enterprise-portal/context')
  expect(context.memberRole).toBe('HR')
  expect(context.campaignId).toBe('88271')
  expect(context.batchId).toBe('88241')
  expect(context.capabilities.recruitmentWrite).toBe(true)

  const company = await payload(companyResponse, '/api/v1/internship/enterprise-portal/company')
  expect(company.name).toBe('益阳智能制造有限公司')
  expect(company.qualificationStatus).toBe('PASSED')

  const dashboard = await payload(dashboardResponse, '/api/v1/internship/enterprise-portal/dashboard')
  expect(dashboard.metrics.published).toBe(1)
  expect(dashboard.metrics.applicants).toBe(0)

  await expect(page.getByRole('heading', { name: '企业首页' })).toBeVisible()
  await expect(page.getByRole('banner').getByText('2026岗位实习企业双选', { exact: true })).toBeVisible()
  await page.screenshot({ path: 'test-results-fullstack-enterprise/enterprise-real-backend.png', fullPage: true })

  const positionsResponse = page.waitForResponse(r =>
    apiPath(r) === '/api/v1/internship/enterprise-portal/positions' &&
    r.request().method() === 'GET')
  await page.getByRole('link', { name: '我的岗位' }).click()
  const positions = await payload(positionsResponse, '/api/v1/internship/enterprise-portal/positions')
  expect(positions.total).toBe(1)
  expect(positions.items[0].title).toBe('智能制造产线运维实习生')
  expect(positions.items[0].status).toBe('PUBLISHED')
  await expect(page.getByRole('heading', { name: '我的岗位', exact: true })).toBeVisible()
  await expect(page.getByText('智能制造产线运维实习生')).toBeVisible()
  await page.screenshot({ path: 'test-results-fullstack-enterprise/enterprise-real-position-list.png', fullPage: true })

  const studentsResponse = page.waitForResponse(r =>
    apiPath(r) === '/api/v1/internship/enterprise-portal/internship-students' &&
    r.request().method() === 'GET')
  await page.getByRole('link', { name: '实习学生' }).click()
  const students = await payload(studentsResponse, '/api/v1/internship/enterprise-portal/internship-students')
  expect(students.total).toBe(1)
  expect(students.items[0].name).toBe('企业协同学生王强')
  expect(students.items[0].positionName).toBe('智能制造产线运维实习生')
  expect(students.items[0].status).toBe('ONBOARD')
  await expect(page.getByRole('heading', { name: '实习学生' })).toBeVisible()
  await expect(page.getByText('企业协同学生王强')).toBeVisible()
  await page.screenshot({ path: 'test-results-fullstack-enterprise/enterprise-real-students.png', fullPage: true })

  const evaluationsResponse = page.waitForResponse(r =>
    apiPath(r) === '/api/v1/internship/enterprise-portal/evaluation-tasks' &&
    r.request().method() === 'GET')
  await page.getByRole('link', { name: '评价任务', exact: true }).click()
  const evaluations = await payload(evaluationsResponse, '/api/v1/internship/enterprise-portal/evaluation-tasks')
  expect(evaluations.total).toBe(1)
  expect(evaluations.items[0].studentName).toBe('企业协同学生王强')
  expect(evaluations.items[0].status).toBe('PENDING')
  expect(evaluations.items[0].placementSnapshotId).toBe('88311')
  await expect(page.getByRole('heading', { name: '评价任务' })).toBeVisible()
  await expect(page.getByText('企业协同学生王强 · 智能制造产线运维实习生')).toBeVisible()
  await page.screenshot({ path: 'test-results-fullstack-enterprise/enterprise-real-evaluations.png', fullPage: true })
})
