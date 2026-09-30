import { test, expect } from '@playwright/test'

async function submitMobileLogin(page) {
  // uni-app H5 compiles <button> into a custom uni-button host, so ARIA role based
  // lookup is not stable across builds. Target the product-owned login class that
  // is present on both student and teacher standalone login surfaces.
  const submit = page.locator('.login-form .btn-primary')
  await expect(submit).toBeVisible()
  await expect(submit).toContainText('登录')
  await submit.click()
}

test('real backend student H5 login reaches standalone internship home and records a real checkin', async ({ page, context }) => {
  await context.grantPermissions(['geolocation'], { origin: 'http://127.0.0.1:5203' })
  await context.setGeolocation({ latitude: 28.2282, longitude: 112.9388, accuracy: 15 })
  const seen=[]
  page.on('response', response => {
    const url=new URL(response.url())
    if(url.pathname.startsWith('/api/v1/')) seen.push({path:url.pathname,status:response.status()})
  })

  await page.goto('http://127.0.0.1:5203/#/pages/login/index')
  await expect(page.getByText('学生移动端',{exact:true})).toBeVisible()
  const inputs=page.locator('input')
  await inputs.nth(0).fill('FULLSTACK')
  await inputs.nth(1).fill('202688112')
  await inputs.nth(2).fill('Fullstack-Student-2026!')
  await submitMobileLogin(page)

  await expect(page).toHaveURL(/#\/pages\/student-internship\/index/)
  await expect(page.getByText('我的岗位实习',{exact:true})).toBeVisible()
  await expect(page.getByText('2026岗位实习全栈验收',{exact:true}).first()).toBeVisible()
  await expect(page.getByText('软件测试实习生',{exact:true}).first()).toBeVisible()
  await expect(page.getByText('全栈验收企业',{exact:true}).first()).toBeVisible()
  await page.screenshot({path:'test-results-mobile-real/student-home.png',fullPage:true})

  await page.getByText('今日打卡',{exact:true}).click()
  await expect(page).toHaveURL(/#\/pages\/student-internship\/checkin\/index/)
  await expect(page.getByText('完整签到日历',{exact:true})).toBeVisible()

  await page.locator('.ci__circle').click()
  await expect(page.getByText(/确认签到/)).toBeVisible()
  const preflightResponse = page.waitForResponse(r =>
    new URL(r.url()).pathname === '/api/v1/mobile/internship/checkin/preflight' && r.request().method() === 'POST')
  const checkinResponse = page.waitForResponse(r =>
    new URL(r.url()).pathname === '/api/v1/mobile/internship/checkin' && r.request().method() === 'POST')
  await page.getByText('确定',{exact:true}).click()

  const preflight = await preflightResponse
  expect(preflight.status()).toBe(200)
  expect((await preflight.json()).code).toBe(0)
  const checkin = await checkinResponse
  expect(checkin.status()).toBe(200)
  const checkinPayload = await checkin.json()
  expect(checkinPayload.code).toBe(0)
  expect(['RECORDED','NORMAL','OUT_OF_RANGE','LOW_ACCURACY','LOCATION_UNCERTAIN']).toContain(checkinPayload.data.result)
  await expect(page.locator('.ci__circle')).toContainText('今日已签到')
  await page.screenshot({path:'test-results-mobile-real/student-checkin.png',fullPage:true})

  expect(seen.some(x=>x.path.endsWith('/auth/login')&&x.status===200)).toBeTruthy()
  expect(seen.some(x=>x.path.endsWith('/mobile/internship/context/my')&&x.status===200)).toBeTruthy()
  expect(seen.some(x=>x.path.endsWith('/mobile/internship/compliance/my')&&x.status===200)).toBeTruthy()
  expect(seen.some(x=>x.path.endsWith('/mobile/internship/checkin/preflight')&&x.status===200)).toBeTruthy()
  expect(seen.some(x=>x.path.endsWith('/mobile/internship/checkin')&&x.status===200)).toBeTruthy()
})

test('real backend teacher H5 login reaches standalone teacher workbench', async ({ page }) => {
  const seen=[]
  page.on('response', response => {
    const url=new URL(response.url())
    if(url.pathname.startsWith('/api/v1/')) seen.push({path:url.pathname,status:response.status()})
  })

  await page.goto('http://127.0.0.1:5203/#/pages/login/index?entry=teacher')
  await expect(page.getByText('教师移动端',{exact:true})).toBeVisible()
  const inputs=page.locator('input')
  await inputs.nth(0).fill('FULLSTACK')
  await inputs.nth(1).fill('fullstack.teacher')
  await inputs.nth(2).fill('Fullstack-Teacher-2026!')
  await submitMobileLogin(page)

  await expect(page).toHaveURL(/#\/pages\/teacher-internship\/index/)
  await expect(page.getByText('岗位实习教师工作台',{exact:true})).toBeVisible()
  await expect(page.getByText('2026岗位实习全栈验收',{exact:true}).first()).toBeVisible()
  await expect(page.getByText('实习学生',{exact:true})).toBeVisible()
  await page.screenshot({path:'test-results-mobile-real/teacher-workbench.png',fullPage:true})

  const rosterResponse = page.waitForResponse(r =>
    new URL(r.url()).pathname === '/api/v1/internship/intern-students' && r.request().method() === 'GET')
  await page.getByText('实习学生',{exact:true}).click()
  await expect(page).toHaveURL(/#\/pages\/teacher-internship\/internship-students\/index/)
  const roster = await rosterResponse
  expect(roster.status()).toBe(200)
  const rosterPayload = await roster.json()
  expect(rosterPayload.code).toBe(0)
  await expect(page.getByText('全栈验收学生',{exact:true})).toBeVisible()
  await expect(page.getByText('软件测试实习生',{exact:true})).toBeVisible()
  await page.screenshot({path:'test-results-mobile-real/teacher-student-roster.png',fullPage:true})

  expect(seen.some(x=>x.path.endsWith('/auth/login')&&x.status===200)).toBeTruthy()
  expect(seen.some(x=>x.path.endsWith('/mobile/teacher/internship/context')&&x.status===200)).toBeTruthy()
  expect(seen.some(x=>x.path.endsWith('/internship/intern-students')&&x.status===200)).toBeTruthy()
})
