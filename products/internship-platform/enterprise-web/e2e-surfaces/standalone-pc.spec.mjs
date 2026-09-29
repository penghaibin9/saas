import { test, expect } from '@playwright/test'

const ok = data => ({ code: 0, message: 'ok', data })

function jwt(payload) {
  const encode = value => Buffer.from(JSON.stringify(value)).toString('base64url')
  return `${encode({ alg: 'none', typ: 'JWT' })}.${encode(payload)}.standalone-evidence`
}

async function installAdminApi(page) {
  const accessToken = jwt({
    userId: '70001',
    loginName: 'yiyang.admin',
    realName: '益阳实习管理员',
    userType: 'SCHOOL_ADMIN',
    currentRoleCode: 'SCHOOL_ADMIN',
    activeContextId: 'ctx-school-admin',
    tenantId: '777',
    tid: 'YIYANG',
    tenantName: '益阳职业技术学院',
  })
  const seen = []
  await page.route('**/api/v1/**', async route => {
    const request = route.request()
    const url = new URL(request.url())
    const path = url.pathname
    seen.push({ method: request.method(), path })

    if (path.endsWith('/auth/browser-login') && request.method() === 'POST') {
      return route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify(ok({
          accessToken,
          tokenType: 'Bearer',
          expiresIn: 1800,
          user: {
            userId: '70001',
            loginName: 'yiyang.admin',
            realName: '益阳实习管理员',
            userType: 'SCHOOL_ADMIN',
            tenantId: '777',
          },
          currentRole: {
            roleCode: 'SCHOOL_ADMIN',
            roleName: '学校管理员',
            contextId: 'ctx-school-admin',
          },
          tenantId: '777',
          tenantName: '益阳职业技术学院',
        })),
      })
    }
    if (path.endsWith('/auth/browser-refresh') && request.method() === 'POST') {
      return route.fulfill({ status: 401, contentType: 'application/json', body: JSON.stringify({ code: 401001, message: 'no refresh fixture' }) })
    }
    if (path.endsWith('/auth/me')) {
      return route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify(ok({
          userId: '70001',
          loginName: 'yiyang.admin',
          realName: '益阳实习管理员',
          userType: 'SCHOOL_ADMIN',
          tenantId: '777',
          tenantName: '益阳职业技术学院',
          currentRole: { roleCode: 'SCHOOL_ADMIN', roleName: '学校管理员', contextId: 'ctx-school-admin' },
        })),
      })
    }
    if (path.endsWith('/rbac/current-context')) {
      return route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify(ok({
          permissionPatterns: ['internship.*'],
          moduleEntitlements: ['internship'],
          moduleAccessHealthy: true,
          readonlyTenant: false,
          currentRole: {
            roleCode: 'SCHOOL_ADMIN',
            roleName: '学校管理员',
            contextId: 'ctx-school-admin',
            permissionVersion: 'browser-evidence-1',
          },
        })),
      })
    }
    if (path.endsWith('/internship/batches')) {
      return route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify(ok({
          items: [{
            id: '66',
            batchName: '2026岗位实习',
            batchNo: 'YIYANG-2026',
            status: 'RUNNING',
            startDate: '2026-09-01',
            endDate: '2027-01-31',
          }],
          total: 1,
          page: 1,
          pageSize: 200,
        })),
      })
    }
    if (path.endsWith('/internship/dashboard')) {
      expect(url.searchParams.get('batchId')).toBe('66')
      return route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify(ok({
          workItems: [],
          workItemTotal: 0,
          workItemLimit: 8,
          riskAlerts: [],
        })),
      })
    }
    return route.fulfill({ contentType: 'application/json', body: JSON.stringify(ok({})) })
  })
  return seen
}

async function installStudentApi(page) {
  const seen = []
  await page.route('**/api/v1/**', async route => {
    const request = route.request()
    const url = new URL(request.url())
    const path = url.pathname
    seen.push({ method: request.method(), path })

    if (path.endsWith('/auth/browser-login') && request.method() === 'POST') {
      const body = request.postDataJSON()
      expect(body.clientType).toBe('STUDENT_PC')
      return route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify(ok({
          accessToken: 'student-browser-evidence-token',
          tokenType: 'Bearer',
          expiresIn: 1800,
          user: {
            userId: '90001',
            realName: '学生张三',
            userType: 'STUDENT',
            studentNo: '20260001',
            tenantId: '777',
          },
          currentRole: { roleCode: 'STUDENT', roleName: '学生' },
          tenantId: '777',
        })),
      })
    }
    if (path.endsWith('/mobile/me/portal-config')) {
      return route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify(ok({
          enabled: true,
          brand: {
            schoolName: '益阳职业技术学院',
            platformName: '跃科岗位实习管理平台',
            primaryColor: '#2f6bff',
          },
        })),
      })
    }
    if (path.endsWith('/portal/internship/my')) {
      return route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify(ok({
          hasData: false,
          needSelect: false,
          candidates: [],
          message: '浏览器验收账号当前暂无实习记录',
        })),
      })
    }
    if (path.endsWith('/auth/me')) {
      return route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify(ok({
          user: {
            userId: '90001',
            realName: '学生张三',
            userType: 'STUDENT',
            studentNo: '20260001',
            tenantId: '777',
          },
          currentRole: { roleCode: 'STUDENT', roleName: '学生' },
          tenantId: '777',
        })),
      })
    }
    return route.fulfill({ contentType: 'application/json', body: JSON.stringify(ok({})) })
  })
  return seen
}

test('admin teacher PC login reaches the standalone internship workbench', async ({ page }) => {
  const seen = await installAdminApi(page)
  await page.goto('http://127.0.0.1:5176/login')

  await expect(page.getByRole('heading', { name: '学校管理 / 指导教师登录' })).toBeVisible()
  await page.getByLabel('学校编码').fill('YIYANG')
  await page.getByLabel('账号').fill('yiyang.admin')
  await page.getByLabel('密码').fill('Browser-Evidence-Only')
  await page.getByRole('button', { name: '登录' }).click()

  await expect(page).toHaveURL(/\/admin\/internship(?:\?|$)/)
  await expect(page.getByRole('heading', { name: '今日工作' })).toBeVisible()
  await expect(page.getByText('按实习流程办理')).toBeVisible()
  await expect(page.getByText('2026岗位实习')).toBeVisible()
  await page.screenshot({ path: 'test-results-surfaces/admin-internship-workbench.png', fullPage: true })

  expect(seen.some(item => item.path.endsWith('/auth/browser-login'))).toBeTruthy()
  expect(seen.some(item => item.path.endsWith('/rbac/current-context'))).toBeTruthy()
  expect(seen.some(item => item.path.endsWith('/internship/batches'))).toBeTruthy()
  expect(seen.some(item => item.path.endsWith('/internship/dashboard'))).toBeTruthy()
})

test('student PC login reaches the standalone internship page without a parent portal', async ({ page }) => {
  const seen = await installStudentApi(page)
  await page.goto('http://127.0.0.1:5201/student/login')

  await expect(page.getByRole('heading', { name: '学生端登录' })).toBeVisible()
  await page.getByLabel('学校编码').fill('YIYANG')
  await page.getByLabel('学号 / 登录账号').fill('20260001')
  await page.getByLabel('密码').fill('Browser-Evidence-Only')
  await page.getByRole('button', { name: '登录' }).click()

  await expect(page).toHaveURL(/\/student\/internship(?:\?|$)/)
  await expect(page.getByText('益阳职业技术学院 · 岗位实习')).toBeVisible()
  await expect(page.getByText('学生 PC 端')).toBeVisible()
  await expect(page.getByText('学生张三')).toBeVisible()
  await expect(page.getByText('暂无实习记录')).toBeVisible()
  await expect(page.getByText('浏览器验收账号当前暂无实习记录')).toBeVisible()
  await page.screenshot({ path: 'test-results-surfaces/student-internship-home.png', fullPage: true })

  expect(seen.some(item => item.path.endsWith('/auth/browser-login'))).toBeTruthy()
  expect(seen.some(item => item.path.endsWith('/mobile/me/portal-config'))).toBeTruthy()
  expect(seen.some(item => item.path.endsWith('/portal/internship/my'))).toBeTruthy()
})
