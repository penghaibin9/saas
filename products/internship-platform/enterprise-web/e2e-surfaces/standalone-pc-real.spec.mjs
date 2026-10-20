import { test, expect } from '@playwright/test'

test('real backend admin PC login reaches standalone internship workbench', async ({ page }) => {
  const seen=[]
  page.on('response', response => {
    const url=new URL(response.url())
    if(url.pathname.startsWith('/api/v1/')) seen.push({path:url.pathname,status:response.status()})
  })

  await page.goto('http://127.0.0.1:5176/login')
  await expect(page.getByRole('heading',{name:'学校管理 / 指导教师登录'})).toBeVisible()
  await page.getByLabel('学校编码').fill('FULLSTACK')
  await page.getByLabel('账号').fill('fullstack.admin')
  await page.getByLabel('密码').fill('Fullstack-Staff-2026!')
  await page.getByRole('button',{name:'登录'}).click()

  await expect(page).toHaveURL(/\/admin\/internship(?:\?|$)/)
  await expect(page.getByRole('heading',{name:'今日工作'})).toBeVisible()
  await expect(page.locator('select option:checked')).toContainText('2026岗位实习全栈验收')
  await page.screenshot({path:'test-results-surfaces-real/real-admin-workbench.png',fullPage:true})

  expect(seen.some(x=>x.path.endsWith('/auth/browser-login')&&x.status===200)).toBeTruthy()
  expect(seen.some(x=>x.path.endsWith('/rbac/current-context')&&x.status===200)).toBeTruthy()
  expect(seen.some(x=>x.path.endsWith('/internship/batches')&&x.status===200)).toBeTruthy()
  expect(seen.some(x=>x.path.endsWith('/internship/dashboard')&&x.status===200)).toBeTruthy()
})

test('real backend student PC login reaches standalone internship page', async ({ page }) => {
  const seen=[]
  page.on('response', response => {
    const url=new URL(response.url())
    if(url.pathname.startsWith('/api/v1/')) seen.push({path:url.pathname,status:response.status()})
  })

  await page.goto('http://127.0.0.1:5201/student/login')
  await expect(page.getByRole('heading',{name:'学生端登录'})).toBeVisible()
  await page.getByLabel('学校编码').fill('FULLSTACK')
  await page.getByLabel('学号 / 登录账号').fill('202688112')
  await page.getByLabel('密码').fill('Fullstack-Student-2026!')
  await page.getByRole('button',{name:'登录'}).click()

  await expect(page).toHaveURL(/\/student\/internship(?:\?|$)/)
  await expect(page.getByText('全栈浏览器验收学校 · 岗位实习')).toBeVisible()
  await expect(page.getByText('全栈验收学生')).toBeVisible()
  await expect(page.getByText('2026岗位实习全栈验收',{exact:true}).first()).toBeVisible()
  await expect(page.getByText('软件测试实习生',{exact:true}).first()).toBeVisible()
  await expect(page.getByText('全栈验收企业',{exact:true}).first()).toBeVisible()
  await page.screenshot({path:'test-results-surfaces-real/real-student-internship.png',fullPage:true})

  expect(seen.some(x=>x.path.endsWith('/auth/browser-login')&&x.status===200)).toBeTruthy()
  expect(seen.some(x=>x.path.endsWith('/mobile/me/portal-config')&&x.status===200)).toBeTruthy()
  expect(seen.some(x=>x.path.endsWith('/portal/internship/my')&&x.status===200)).toBeTruthy()
})
