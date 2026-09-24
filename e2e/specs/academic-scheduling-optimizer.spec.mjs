import fs from 'node:fs'
import crypto from 'node:crypto'
import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'

const miniBase = process.env.E2E_MINIAPP_BASE_URL || 'http://127.0.0.1:5184'
let publishedItemIds=[]

test('智能候选由真实页面采用至原课表草稿', async ({ page, context }, testInfo) => {
  const fixture = JSON.parse(fs.readFileSync(process.env.E2E_OPTIMIZER_FIXTURE, 'utf8'))
  const course=fixture.courseName || '实训课'
  const id = crypto.randomUUID()
  // Normal password authentication prepares the browser session; every scheduling command below is UI driven.
  const response = await context.request.post(`${config.staffBaseUrl}/api/v1/auth/browser-login`, {
    headers: { 'X-Browser-Session': 'staff', 'X-Browser-Session-Id': id },
    data: { loginName: fixture.user.loginName, password: process.env.E2E_OPTIMIZER_PASSWORD,
      tenantCode: fixture.tenantCode, clientType: 'PC' }
  })
  expect(response.status()).toBe(200)
  expect((await response.json()).code).toBe(0)
  await context.addInitScript(value => sessionStorage.setItem('gx_browser_session_id_v2', value), id)
  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.goto(`${config.staffBaseUrl}/admin/academic-affairs/scheduling?tab=auto&batchId=${fixture.batch}&termId=${fixture.term}`)
  const panel = page.locator('.optimizer-panel')
  await expect(panel).toBeVisible()
  await panel.getByRole('button', { name: '第一步：检查排课条件' }).click()
  await expect(panel.getByText('待排课程 1', { exact: true })).toBeVisible()
  await panel.getByLabel('连排模式'+course, { exact: true }).fill('2+2')
  await panel.getByLabel('最小间隔天数'+course, { exact: true }).fill('1')
  await panel.getByLabel('试排原因', { exact: true }).fill('真实浏览器智能排课验收')
  await panel.getByRole('checkbox', { name: '已核对教学周、校区、连排及时段组设置' }).check()
  await page.screenshot({ path: testInfo.outputPath('01-ready.png'), fullPage: true })
  await panel.getByRole('button', { name: '第二步：智能试排' }).click()
  await expect(panel.getByRole('button', { name: '采用此方案' })).toBeEnabled({ timeout: 90000 })
  await expect(panel.getByText(/硬冲突 0/)).toBeVisible()
  for (const value of ['className', 'teacherName', 'classroom']) {
    await panel.getByLabel('查看方式', { exact: true }).selectOption(value)
    await expect(panel.getByText(course, { exact: true }).first()).toBeVisible()
  }
  await page.screenshot({ path: testInfo.outputPath('02-candidate.png'), fullPage: true })
  const applied = page.waitForResponse(r => r.request().method() === 'POST' && /\/jobs\/\d+\/apply$/.test(r.url()))
  await panel.getByRole('button', { name: '采用此方案' }).click()
  const receipt = await (await applied).json()
  expect(receipt.code).toBe(0)
  expect(receipt.data.status).toBe('DRAFT')
  expect(receipt.data.writtenItems).toBe(4)
  publishedItemIds=receipt.data.itemIds.map(String).sort()
  await expect(panel.getByText(/方案已写入原课表草稿/)).toBeVisible()
  await page.reload()
  await panel.getByRole('button', { name: '第一步：检查排课条件' }).click()
  await expect(panel.getByText(/方案已写入原课表草稿/)).toBeVisible()
  await page.screenshot({ path: testInfo.outputPath('03-applied-refresh.png'), fullPage: true })
  await panel.getByRole('link', { name: '人工调整课表' }).click()
  await expect(page.locator('.aa-grid__item')).toHaveCount(4)
  await page.locator('.aa-grid__item').first().scrollIntoViewIfNeeded()
  const movePreflight=page.waitForResponse(r=>r.request().method()==='POST' && r.url().includes('/move-preflight'))
  const moveWritten=page.waitForResponse(r=>r.request().method()==='PUT' && /\/schedule-items\/\d+\/move$/.test(r.url()))
  // Move one actual card to an empty Friday slot through the original drag handler.
  const source=await page.locator('.aa-grid__item').first().boundingBox()
  const target=await page.locator('.aa-grid tbody tr').first().locator('td').nth(4).boundingBox()
  await page.mouse.move(source.x+15,source.y+15);await page.mouse.down()
  await page.mouse.move(source.x+35,source.y+25,{steps:5})
  await page.mouse.move(target.x+20,target.y+20,{steps:20})
  await page.mouse.move(target.x+25,target.y+25);await page.mouse.up()
  expect((await(await movePreflight).json()).data.allowed).toBe(true)
  const moved=await(await moveWritten).json();expect(moved.code).toBe(0)
  await page.reload()
  await expect(page.locator('.aa-grid tbody tr').first().locator('td').nth(4).getByText(course,{exact:true})).toBeVisible()
  await page.screenshot({ path: testInfo.outputPath('04-original-editor.png'), fullPage: true })
  await page.goto(`${config.staffBaseUrl}/admin/academic-affairs/schedule/publish?batchId=${fixture.batch}`)
  await page.getByRole('button', { name: '检查并预发布', exact: true }).click()
  await expect(page.getByText('全部通过', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: '确认进入预发布', exact: true }).click()
  await page.getByRole('button', { name: '检查并正式发布', exact: true }).click()
  await expect(page.getByText('全部通过', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: '确认正式发布并通知师生', exact: true }).click()
  await expect(page.getByRole('button', { name: '复核发布门禁', exact: true })).toBeVisible()
  await page.reload()
  await expect(page.getByRole('button', { name: '复核发布门禁', exact: true })).toBeVisible()
  await page.screenshot({ path: testInfo.outputPath('05-published-refresh.png'), fullPage: true })
})

for (const surface of ['teacher-pc','student-pc','teacher-h5','student-h5']) {
  test(`正式课表跨端回读 ${surface}`,async({page,context},testInfo)=>{
    const fixture=JSON.parse(fs.readFileSync(process.env.E2E_OPTIMIZER_FIXTURE,'utf8'))
    const course=fixture.courseName || '实训课'
    const teacher=surface.startsWith('teacher'), h5=surface.endsWith('h5')
    const actor=fixture[teacher?'teacher':'student'], channel=teacher?'staff':'student'
    const base=h5?miniBase:teacher?config.staffBaseUrl:new URL(config.studentBaseUrl).origin
    const id=crypto.randomUUID()
    const response=await context.request.post(`${base}/api/v1/auth/browser-login`,{
      headers:{'X-Browser-Session':channel,'X-Browser-Session-Id':id},
      data:{loginName:actor.loginName,password:process.env.E2E_OPTIMIZER_PASSWORD,tenantCode:fixture.tenantCode,clientType:teacher?'PC':'STUDENT_PC'}
    })
    const login=await response.json();expect(login.code).toBe(0)
    const candidateRead=await context.request.get(`${base}/api/v1/academic-affairs/scheduling/batches/${fixture.batch}/optimizer/context`,{
      headers:{'X-Browser-Session':channel,'X-Browser-Session-Id':id,Authorization:`Bearer ${login.data.accessToken}`}
    })
    expect(candidateRead.status()).toBe(403)
    await context.addInitScript(({id,channel,h5,user,teacher})=>{
      if(h5){
        sessionStorage.setItem('gx_h5_browser_session_id_v1',id)
        sessionStorage.setItem('gx_h5_browser_channel_v1',channel)
        localStorage.setItem('gx_session_v1',JSON.stringify({logged:true,currentRole:teacher?'academic':'student',
          availableRoles:[teacher?'academic':'student'],isTeacher:teacher,user:{name:user.realName,tenantName:user.tenantName}}))
      }else sessionStorage.setItem('gx_browser_session_id_v2',id)
    },{id,channel,h5,user:login.data.user,teacher})
    const endpoint=h5?(teacher?'/mobile/academic/teacher-schedule/my':'/mobile/academic/schedule/my')
      :teacher?'/academic-affairs/schedule/teacher/':'/portal/academic/schedule'
    const result=page.waitForResponse(r=>r.request().method()==='GET' && r.url().includes('/api/v1'+endpoint))
    const route=h5?(teacher?'/#/pages/teacher/my-schedule/index':'/#/pages/student/academic-affairs/schedule')
      :teacher?`/admin/academic-affairs/schedule/teacher/${encodeURIComponent(actor.loginName)}?termId=${fixture.term}`:'/portal/academic/schedule'
    await page.setViewportSize(h5?{width:390,height:844}:{width:1440,height:1000})
    await page.goto(base+route)
    const read=await(await result).json();expect(read.code).toBe(0)
    expect(read.data.items).toHaveLength(4)
    const ids=read.data.items.map(row=>String(row.scheduleItemId || row.itemId)).sort()
    if(!publishedItemIds.length)publishedItemIds=ids
    expect(ids).toEqual(publishedItemIds)
    if(teacher && h5) expect([...new Set(read.data.items.map(i=>i.activeBatchId))]).toEqual([fixture.batch])
    else if(read.data.batchId) expect(String(read.data.batchId)).toBe(fixture.batch)
    const selectTeachingDay=async()=>{
      if(teacher && h5)await page.locator('.ts__date').filter({has:page.getByText(['周一','周二','周三','周四','周五','周六','周日'][Number(read.data.items[0].weekday)-1],{exact:true})}).click()
    }
    await selectTeachingDay()
    await expect(page.getByText(course,{exact:true}).first()).toBeVisible()
    await page.reload()
    await selectTeachingDay()
    await expect(page.getByText(course,{exact:true}).first()).toBeVisible()
    await page.screenshot({path:testInfo.outputPath(`${surface}-published.png`),fullPage:true})
  })
}
