import fs from 'node:fs'
import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { StaffLoginPage } from '../pages/login.page.mjs'

const fixture = JSON.parse(fs.readFileSync(new URL('../runtime-logs/gd013-solo-fixture.json', import.meta.url), 'utf8'))
const groupName = `GD013-DIAG-${fixture.runId}`

function field(page, label) {
  return page.locator('.ie-fld').filter({ has: page.locator('.ie-lbl').filter({ hasText: label }) }).first()
}

async function pickMentor(page, label, keyword, text) {
  const root = field(page, label)
  await root.locator('.app-remote-select__control').click()
  const search = root.locator('.app-remote-select__search-el')
  await expect(search).toBeVisible()
  await search.fill(keyword)
  const option = root.locator('.app-remote-select__option').filter({ hasText: text }).first()
  await expect(option).toBeVisible({ timeout: 15000 })
  await option.click()
}

async function dismissGuide(page) {
  const skip = page.getByRole('button', { name: /跳过引导|跳过/ }).first()
  if (await skip.isVisible().catch(() => false)) await skip.click()
}

test.describe.configure({ retries: 0 })

test('GD-013 solo: create payload → assign response → list projection → no publish POST', async ({ page }) => {
  test.setTimeout(360000)
  await page.context().setExtraHTTPHeaders({ 'X-Forwarded-For': '10.254.13.91' })
  await new StaffLoginPage(page, config.staffBaseUrl).login(config.sandboxAdmin)
  await page.waitForLoadState('networkidle', { timeout: 60000 })

  await page.goto(`${config.staffBaseUrl}/admin/graduation/defense/groups/create?batchId=${encodeURIComponent(fixture.batchId)}`)
  await dismissGuide(page)
  await expect(page.getByRole('heading', { name: '新增答辩组', exact: true })).toBeVisible()
  await page.getByPlaceholder('如 软件工程专业第一答辩组').fill(groupName)
  await page.getByPlaceholder('如 实训楼 A301').fill('GD013 SOLO A301')
  await pickMentor(page, '答辩组长', 'e2e_advisor_a', 'E2E指导教师A')
  await pickMentor(page, '答辩秘书', 'e2e_reviewer', 'E2E评阅教师')

  const createReqP = page.waitForRequest((r) => r.method() === 'POST' && new URL(r.url()).pathname.endsWith('/graduation/defense-groups'))
  const createResP = page.waitForResponse((r) => r.request().method() === 'POST' && new URL(r.url()).pathname.endsWith('/graduation/defense-groups'))
  await page.getByRole('button', { name: '创建', exact: true }).click()
  const createReq = await createReqP
  const createRes = await createResP
  expect(createRes.ok(), `create HTTP ${createRes.status()}`).toBeTruthy()
  const createPayload = createReq.postDataJSON()
  const createBody = await createRes.json()
  console.log('GD013_CREATE_PAYLOAD=' + JSON.stringify(createPayload))
  console.log('GD013_CREATE_RESPONSE=' + JSON.stringify(createBody))
  expect(String(createPayload.chairMentorId || '')).toBe(String(fixture.mentorId))
  expect(String(createBody.data?.chairMentorId || '')).toBe(String(fixture.mentorId))
  const groupId = String(createBody.data?.id || '')
  expect(groupId).toMatch(/^\d+$/)

  await expect(page.getByPlaceholder('搜索姓名')).toBeVisible({ timeout: 15000 })
  const search = page.getByPlaceholder('搜索姓名')
  const eligibleP = page.waitForResponse((r) => r.request().method() === 'GET' && new URL(r.url()).pathname.endsWith('/graduation/defense-groups/eligible-students'))
  await search.fill(fixture.student.name)
  expect((await eligibleP).ok()).toBeTruthy()
  const candidate = page.locator('.dg-row--pick').filter({ hasText: fixture.student.name }).first()
  await expect(candidate).toBeVisible({ timeout: 15000 })
  await candidate.click()

  const assignReqP = page.waitForRequest((r) => r.method() === 'POST' && new URL(r.url()).pathname.endsWith(`/graduation/defense-groups/${groupId}/assign`))
  const assignResP = page.waitForResponse((r) => r.request().method() === 'POST' && new URL(r.url()).pathname.endsWith(`/graduation/defense-groups/${groupId}/assign`))
  await page.getByRole('button', { name: /分配所选/ }).click()
  const assignReq = await assignReqP
  const assignRes = await assignResP
  expect(assignRes.ok(), `assign HTTP ${assignRes.status()}`).toBeTruthy()
  const assignBody = await assignRes.json()
  console.log('GD013_ASSIGN_PAYLOAD=' + JSON.stringify(assignReq.postDataJSON()))
  console.log('GD013_ASSIGN_RESPONSE=' + JSON.stringify(assignBody))
  expect(Number(assignBody.data?.studentCount || 0)).toBe(1)
  expect(String(assignBody.data?.conflict || '')).toContain('冲突')
  await expect(page.locator('.dg-sec').filter({ hasText: '已分配学生' })).toContainText('与评委冲突')

  const listResP = page.waitForResponse((r) => r.request().method() === 'GET' && new URL(r.url()).pathname.endsWith('/graduation/defense-groups'))
  await page.goto(`${config.staffBaseUrl}/admin/graduation/defense?batchId=${encodeURIComponent(fixture.batchId)}`)
  await dismissGuide(page)
  const listRes = await listResP
  expect(listRes.ok(), `list HTTP ${listRes.status()}`).toBeTruthy()
  const listBody = await listRes.json()
  const rows = listBody.data?.list || listBody.data?.items || listBody.data || []
  const projected = rows.find((r) => String(r.id) === groupId)
  console.log('GD013_LIST_GROUP=' + JSON.stringify(projected || null))
  expect(projected, 'created group must be in defense list').toBeTruthy()
  expect(Number(projected.studentCount || 0)).toBe(1)
  expect(String(projected.conflict || '')).toContain('冲突')
  expect(String(projected.chairMentorId || '')).toBe(String(fixture.mentorId))

  const row = page.locator('tbody tr').filter({ hasText: groupName }).first()
  await expect(row).toBeVisible()
  await expect(row).toContainText('⚠')
  await expect(row).toContainText('评委与指导教师冲突')
  const publish = row.getByRole('button', { name: '发布', exact: true })
  await expect(publish).toHaveClass(/is-disabled/)
  let publishPosts = 0
  const count = (req) => {
    if (req.method() === 'POST' && /\/graduation\/defense-groups\/\d+\/publish$/.test(new URL(req.url()).pathname)) publishPosts += 1
  }
  page.on('request', count)
  await publish.click()
  await page.waitForTimeout(500)
  page.off('request', count)
  expect(publishPosts).toBe(0)
})
