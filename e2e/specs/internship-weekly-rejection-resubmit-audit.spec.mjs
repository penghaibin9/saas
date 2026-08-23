import { execFileSync } from 'node:child_process'
import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { loadInternshipFixture } from '../lib/internship-fixture.mjs'
import { StaffLoginPage, StudentLoginPage } from '../pages/login.page.mjs'

const PREFIX = 'E2E-WEEKLY-20260823'

function apiPath(response) {
  try { return new URL(response.url()).pathname } catch { return '' }
}

async function jsonBody(response, action) {
  const text = await response.text()
  let body = null
  try { body = JSON.parse(text) } catch { body = null }
  expect(response.ok(), `${action} HTTP ${response.status()}: ${text.slice(0, 800)}`).toBeTruthy()
  expect(body?.code, `${action} business error: ${text.slice(0, 800)}`).toBe(0)
  return body
}

async function openWeeklyEditor(page, fixture) {
  const listPromise = page.waitForResponse((response) =>
    apiPath(response).endsWith('/api/v1/portal/internship/context/weekly-reports')
    && response.request().method() === 'GET'
  )
  await page.goto(`${config.studentBaseUrl}/internship`)
  const list = await jsonBody(await listPromise, '学生读取周报列表')
  await expect(page.getByRole('button', { name: '周报/月报/总结' })).toBeVisible()
  await page.getByRole('button', { name: '周报/月报/总结' }).click()
  const editor = page.locator('section.sp-card').filter({ hasText: '周报编辑' }).first()
  await expect(editor).toBeVisible()
  return { editor, items: list.data?.items || [] }
}

async function fillWeekly(editor, { week, work, harvest, plan }) {
  await editor.locator('input[type="number"]').fill(String(week))
  const areas = editor.locator('textarea')
  await expect(areas).toHaveCount(3)
  await areas.nth(0).fill(work)
  await areas.nth(1).fill(harvest)
  await areas.nth(2).fill(plan)
}

test.describe('岗位实习审计：周报真实退回—反馈—版本化重交—通过', () => {
  test.describe.configure({ mode: 'serial', retries: 0 })

  let fixture
  let reportId = ''
  let week = 0
  let initialVersion = 0
  const firstWork = `${PREFIX}-第一版工作内容：完成接口联调、真实数据核验与问题记录。`
  const firstHarvest = `${PREFIX}-第一版收获：掌握业务状态核对与接口失败定位方法。`
  const firstPlan = `${PREFIX}-第一版计划：补充异常路径测试并完善验收证据。`
  const finalWork = `${PREFIX}-整改版工作内容：补充异常场景、边界条件和真实数据复核。`
  const finalHarvest = `${PREFIX}-整改版收获：完成退回意见整改并形成可追溯验证记录。`
  const finalPlan = `${PREFIX}-整改版计划：继续核验统计、导出和跨角色数据一致性。`
  const rejectReason = `${PREFIX}-退回原因：请补充异常场景及量化验证结果。`

  test.beforeAll(async () => {
    fixture = await loadInternshipFixture()
  })

  test('学生从真实 PC 提交一个新周次周报，刷新后仍为待审阅', async ({ page }) => {
    await new StudentLoginPage(page, config.studentBaseUrl).login(config.student)
    const { editor, items } = await openWeeklyEditor(page, fixture)
    const maxWeek = items.reduce((max, item) => Math.max(max, Number(item.weekNo || item.week || 0)), 0)
    week = maxWeek + 1
    await fillWeekly(editor, { week, work: firstWork, harvest: firstHarvest, plan: firstPlan })

    const responsePromise = page.waitForResponse((response) =>
      apiPath(response).endsWith('/api/v1/portal/internship/context/weekly-reports')
      && response.request().method() === 'POST'
    )
    await editor.getByRole('button', { name: '提交周报' }).click()
    const body = await jsonBody(await responsePromise, '学生提交第一版周报')
    reportId = String(body.data?.id || '')
    initialVersion = Number(body.data?.version || 0)
    expect(reportId).not.toBe('')
    expect(body.data?.status).toBe('PENDING_REVIEW')
    expect(Number(body.data?.reportVersion)).toBe(1)

    const { items: refreshed } = await openWeeklyEditor(page, fixture)
    const row = refreshed.find((item) => String(item.id) === reportId)
    expect(row?.status).toBe('PENDING_REVIEW')
    expect(row?.workContent).toBe(firstWork)
  })

  test('实习导师从真实批阅详情退回，原因原样写入', async ({ page }) => {
    const login = new StaffLoginPage(page, config.staffBaseUrl)
    await login.login(config.mentor)
    await login.switchRole(/实习指导教师|实习导师|INTERN_MENTOR/)
    await expect.poll(() => login.currentRoleText()).toMatch(/实习指导教师|实习导师|INTERN_MENTOR/)

    const detailPath = `/api/v1/internship/reports/${reportId}`
    const detailPromise = page.waitForResponse((response) =>
      apiPath(response) === detailPath && response.request().method() === 'GET'
    )
    await page.goto(`${config.staffBaseUrl}/admin/internship/reports/${reportId}`)
    const detail = await jsonBody(await detailPromise, '导师打开周报详情')
    expect(detail.data?.status).toBe('PENDING_REVIEW')
    expect(detail.data?.content?.work).toBe(firstWork)
    await expect(page.getByText(firstWork, { exact: false })).toBeVisible()

    await page.locator('.mp-radio').filter({ hasText: '退回修改' }).click()
    const textarea = page.locator('.mp-textarea')
    await textarea.fill(rejectReason)
    const reviewPromise = page.waitForResponse((response) =>
      apiPath(response).endsWith(`/api/v1/internship/reports/${reportId}/review`)
      && response.request().method() === 'POST'
    )
    await page.getByRole('button', { name: /退回修改/ }).click()
    const reviewed = await jsonBody(await reviewPromise, '导师退回周报')
    expect(reviewed.data?.status).toBe('RETURNED')
  })

  test('学生重新登录看到退回原因，并在同一周次整改重交', async ({ page }) => {
    await new StudentLoginPage(page, config.studentBaseUrl).login(config.student)
    const { editor, items } = await openWeeklyEditor(page, fixture)
    const returned = items.find((item) => String(item.id) === reportId)
    expect(returned?.status).toBe('RETURNED')
    expect(returned?.reviewComment).toBe(rejectReason)
    expect(Number(returned?.version)).toBeGreaterThan(initialVersion)

    const row = page.locator('.repitem').filter({ hasText: `第 ${week} 周周报` }).first()
    await expect(row).toBeVisible()
    await expect(row).toContainText('已退回')
    await expect(row).toContainText(`老师意见：${rejectReason}`)

    await fillWeekly(editor, { week, work: finalWork, harvest: finalHarvest, plan: finalPlan })
    const responsePromise = page.waitForResponse((response) =>
      apiPath(response).endsWith('/api/v1/portal/internship/context/weekly-reports')
      && response.request().method() === 'POST'
    )
    await editor.getByRole('button', { name: '提交周报' }).click()
    const body = await jsonBody(await responsePromise, '学生整改重交周报')
    expect(String(body.data?.id)).toBe(reportId)
    expect(body.data?.status).toBe('PENDING_REVIEW')
    expect(Number(body.data?.reportVersion)).toBe(2)
    expect(Number(body.data?.version)).toBeGreaterThan(Number(returned?.version || 0))
  })

  test('导师看到整改正文和第一版历史快照，再真实审批通过', async ({ page }) => {
    const login = new StaffLoginPage(page, config.staffBaseUrl)
    await login.login(config.mentor)
    await login.switchRole(/实习指导教师|实习导师|INTERN_MENTOR/)
    await expect.poll(() => login.currentRoleText()).toMatch(/实习指导教师|实习导师|INTERN_MENTOR/)

    const detailPromise = page.waitForResponse((response) =>
      apiPath(response).endsWith(`/api/v1/internship/reports/${reportId}`)
      && response.request().method() === 'GET'
    )
    await page.goto(`${config.staffBaseUrl}/admin/internship/reports/${reportId}`)
    const detail = await jsonBody(await detailPromise, '导师读取整改周报')
    expect(detail.data?.status).toBe('PENDING_REVIEW')
    expect(detail.data?.content?.work).toBe(finalWork)
    expect(Number.parseInt(String(detail.data?.reportVersion || '0').replace(/^v/i, ''), 10)).toBeGreaterThanOrEqual(2)
    await expect(page.getByText(finalWork, { exact: false })).toBeVisible()

    const historyToggle = page.getByRole('button', { name: '查看该版正文' }).first()
    await expect(historyToggle).toBeVisible()
    await historyToggle.click()
    await expect(page.getByText(firstWork, { exact: false })).toBeVisible()

    const reviewPromise = page.waitForResponse((response) =>
      apiPath(response).endsWith(`/api/v1/internship/reports/${reportId}/review`)
      && response.request().method() === 'POST'
    )
    await page.getByRole('button', { name: /✓ 通过|通过/ }).last().click()
    const approved = await jsonBody(await reviewPromise, '导师通过整改周报')
    expect(approved.data?.status).toBe('APPROVED')
  })

  test('学生刷新看到已通过；管理员与只读 MySQL 核验版本及审计链', async ({ page }) => {
    await new StudentLoginPage(page, config.studentBaseUrl).login(config.student)
    const { items } = await openWeeklyEditor(page, fixture)
    const finalRow = items.find((item) => String(item.id) === reportId)
    expect(finalRow?.status).toBe('APPROVED')
    expect(finalRow?.workContent).toBe(finalWork)
    const studentRow = page.locator('.repitem').filter({ hasText: `第 ${week} 周周报` }).first()
    await expect(studentRow).toContainText('已通过')

    await new StaffLoginPage(page, config.staffBaseUrl).login(config.sandboxAdmin)
    const detailPromise = page.waitForResponse((response) =>
      apiPath(response).endsWith(`/api/v1/internship/reports/${reportId}`)
      && response.request().method() === 'GET'
    )
    await page.goto(`${config.staffBaseUrl}/admin/internship/reports/${reportId}`)
    const detail = await jsonBody(await detailPromise, '管理员读取周报最终详情')
    expect(detail.data?.status).toBe('APPROVED')
    expect(detail.data?.content?.work).toBe(finalWork)
    const actions = (detail.data?.trail || []).map((item) => item.action)
    expect(actions).toEqual(expect.arrayContaining([
      'SUBMIT_VERSIONED', 'REVIEW_RETURN', 'RESUBMIT_VERSIONED', 'REVIEW_APPROVE'
    ]))

    const output = execFileSync('python', ['../backend/scripts/e2e_verify_internship_weekly_audit.py'], {
      cwd: process.cwd(),
      encoding: 'utf8',
      env: {
        ...process.env,
        E2E_INTERNSHIP_WEEKLY_ID: reportId,
        E2E_INTERNSHIP_WEEKLY_WEEK: String(week),
        E2E_INTERNSHIP_WEEKLY_FIRST_WORK: firstWork,
        E2E_INTERNSHIP_WEEKLY_FINAL_WORK: finalWork,
        E2E_INTERNSHIP_WEEKLY_REJECT_REASON: rejectReason
      }
    })
    expect(output).toContain('DB_EVIDENCE_OK')
    console.log(output.trim())
  })
})
