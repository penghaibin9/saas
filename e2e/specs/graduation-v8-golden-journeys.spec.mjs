import fs from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { graduationRoles } from '../lib/graduation-role-accounts.mjs'
import { items, loginApi, prepareGraduationFixture } from '../lib/api-fixture.mjs'
import { ensureArchiveProjection } from '../lib/graduation-scenario-fixture.mjs'
import { prepareGraduationTeacherMobileGoldFixture, u8TeacherAccount } from '../lib/graduation-u8-fixture.mjs'
import { StaffLoginPage, StudentLoginPage } from '../pages/login.page.mjs'

const MINI_BASE_URL = process.env.E2E_MINIAPP_BASE_URL || 'http://127.0.0.1:5188'
const ARTIFACT_DIR = process.env.E2E_ARTIFACT_DIR
  ? path.resolve(process.env.E2E_ARTIFACT_DIR, 'graduation-v8/golden-journeys')
  : fileURLToPath(new URL('../artifacts/graduation-v8/golden-journeys/', import.meta.url))

let fixture
let teacherFixture
let adminApi

async function settle(page) {
  await page.evaluate(async () => {
    if (document.fonts?.ready) await document.fonts.ready
  })
  await page.waitForLoadState('networkidle', { timeout: 5_000 }).catch(() => {})
  await page.waitForTimeout(150)
}

async function dismissGuide(page) {
  for (const mask of [page.locator('.app-step-guide__mask'), page.locator('.tour-mask')]) {
    if (await mask.isVisible().catch(() => false)) {
      const skip = page.getByRole('button', { name: /跳过引导|跳过/ }).first()
      if (await skip.isVisible().catch(() => false)) await skip.click()
      await mask.waitFor({ state: 'hidden', timeout: 3_000 }).catch(() => {})
    }
  }
}

async function capture(page, journey, phase) {
  await fs.mkdir(ARTIFACT_DIR, { recursive: true })
  await settle(page)
  await dismissGuide(page)
  const path = `${ARTIFACT_DIR}/${journey}-${phase}.png`
  await page.screenshot({ path, fullPage: false, animations: 'disabled', caret: 'hide' })
  return path
}

async function assertHealthyPage(page) {
  await expect(page.locator('body')).not.toContainText(/真实接口不可用|权限上下文加载失败|登录已失效|数据加载出现问题/)
  const fit = await page.evaluate(() => ({
    width: window.innerWidth,
    scrollWidth: document.documentElement.scrollWidth,
  }))
  expect(fit.scrollWidth, JSON.stringify(fit)).toBeLessThanOrEqual(fit.width + 1)
}

const ROLE_HOME_QUERY = {
  '待评阅开题': { tab: 'PENDING_REVIEW' },
  '待评阅成果': { tab: 'PENDING_REVIEW' },
  '批次与规则': { panel: 'list' },
  '题目库': { panel: 'list' },
  '过程指导台': { panel: 'taskbook' },
  '毕设材料归档': { panel: 'archive' },
}

async function assertRoleHomeDestination(page, entryLabel, expectedPath) {
  await expect.poll(() => new URL(page.url()).pathname, {
    message: `${entryLabel} must land on ${expectedPath}`
  }).toBe(expectedPath)
  for (const [key, expected] of Object.entries(ROLE_HOME_QUERY[entryLabel] || {})) {
    await expect.poll(() => new URL(page.url()).searchParams.get(key), {
      message: `${entryLabel} must preserve ${key}=${expected}`
    }).toBe(expected)
  }
  await expect.poll(() => new URL(page.url()).searchParams.get('batchId'), {
    message: `${entryLabel} must preserve the selected graduation batch`
  }).toBe(String(fixture.batchId))
  await expect(page.locator('.gbs__select')).toHaveValue(String(fixture.batchId))
}

async function openStaffFromRoleHome(page, entryLabel, expectedPath) {
  await page.setViewportSize({ width: 1440, height: 900 })
  await new StaffLoginPage(page, config.staffBaseUrl).login(config.sandboxAdmin)

  const graduationRail = page.locator('.bpl-rail__item').filter({ hasText: '毕业设计中心' }).first()
  await expect(graduationRail).toBeVisible()
  await graduationRail.click()
  await expect(page).toHaveURL(/\/admin\/graduation(?:\?|$)/)
  await page.evaluate((batchId) => localStorage.setItem('graduation.selectedBatchId', batchId), fixture.batchId)
  await page.goto(`${config.staffBaseUrl}/admin/graduation?batchId=${encodeURIComponent(fixture.batchId)}`)
  await dismissGuide(page)
  await expect(page.locator('.gbs__select')).toHaveValue(String(fixture.batchId))

  const roleHomeTask = {
    '待评阅开题': '开题材料待审阅',
    '待评阅成果': '成果待审阅',
  }[entryLabel]
  if (roleHomeTask) {
    const taskButton = page.getByRole('button').filter({ hasText: roleHomeTask }).first()
    await expect(taskButton, `Role Home 必须显示 ${roleHomeTask}`).toBeVisible()
    await taskButton.click()
    await assertRoleHomeDestination(page, entryLabel, expectedPath)
    await dismissGuide(page)
    await assertHealthyPage(page)
    return
  }

  const workspaceByEntry = {
    '批次与规则': '批次与实施',
    '题目库': '题目与选题',
    '过程指导台': '过程指导',
    '答辩安排': '答辩与成绩',
    '成绩台账': '答辩与成绩',
    '毕设材料归档': '风险与归档',
  }
  const workspaceLabel = workspaceByEntry[entryLabel]
  expect(workspaceLabel, `缺少 ${entryLabel} 的 Role Home 工作区映射`).toBeTruthy()
  const workspace = page.locator('.bpl-tree__mod').filter({ hasText: workspaceLabel }).first()
  const leaf = page.locator('.bpl-tree__leaf').filter({ hasText: entryLabel }).first()
  if (!(await leaf.isVisible().catch(() => false))) {
    await expect(workspace).toBeVisible()
    await workspace.click()
    await expect(leaf, `Role Home 侧栏必须展开 ${workspaceLabel}`).toBeVisible()
    await settle(page)
  }
  await expect(leaf, `Role Home 侧栏必须能找到 ${workspaceLabel} → ${entryLabel}`).toBeVisible()
  await leaf.click()
  await assertRoleHomeDestination(page, entryLabel, expectedPath)
  await dismissGuide(page)
  await assertHealthyPage(page)
}

async function loginTeacherMini(page, account = u8TeacherAccount) {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto(`${MINI_BASE_URL}/#/pages/login/teacher/index`)
  const fields = page.getByRole('textbox')
  await fields.nth(0).fill(account.username)
  await fields.nth(1).fill(account.password)
  await page.getByText('填写', { exact: true }).click()
  await fields.nth(2).fill(account.tenant)
  await page.getByText('我已阅读并同意学校提供的', { exact: false }).click()
  await page.getByText('进入教师工作台', { exact: true }).click()
  await expect(page).toHaveURL(/pages\/teacher\/workbench\/index/, { timeout: 15_000 })
  await assertHealthyPage(page)
}

async function openStudentFromRoleHome(page, { materials = false } = {}) {
  await page.setViewportSize({ width: 1440, height: 900 })
  await new StudentLoginPage(page, config.studentBaseUrl).login(config.student)
  await page.goto(`${config.studentBaseUrl}/home`)
  const graduation = page.getByText('毕业设计', { exact: true }).first()
  await expect(graduation).toBeVisible()
  await graduation.click()
  await expect(page).toHaveURL(/\/portal\/graduation(?:\?|$)/)
  await assertHealthyPage(page)
  if (materials) {
    const library = page.getByRole('button', { name: '我的材料库', exact: true }).first()
    await expect(library).toBeVisible()
    await library.click()
    await expect(page).toHaveURL(/\/portal\/graduation\/materials/)
    await assertHealthyPage(page)
  }
}

async function firstVisible(locator) {
  const count = await locator.count()
  for (let index = 0; index < count; index += 1) {
    const candidate = locator.nth(index)
    if (await candidate.isVisible().catch(() => false)) return candidate
  }
  return null
}

async function clickFirstVisible(page, names) {
  await dismissGuide(page)
  for (const name of names) {
    const candidate = await firstVisible(page.getByRole('button', { name }))
    if (candidate) {
      await candidate.click()
      await settle(page)
      return String(name)
    }
  }
  throw new Error(`没有找到当前 Journey 的可见主动作：${names.join(' / ')}`)
}

async function writeMeta(journey, payload) {
  await fs.mkdir(ARTIFACT_DIR, { recursive: true })
  await fs.writeFile(`${ARTIFACT_DIR}/${journey}-seal.json`, JSON.stringify({
    journey,
    result: 'BROWSER_PASS',
    batchId: fixture.batchId,
    gdStudentId: fixture.gdStudentId,
    ...payload,
  }, null, 2), 'utf8')
}

test.describe.serial('Graduation V8 W15 · eight zero-training Golden Journeys', () => {
  test.beforeAll(async () => {
    fixture = await prepareGraduationFixture()
    teacherFixture = await prepareGraduationTeacherMobileGoldFixture()
    adminApi = await loginApi(config.sandboxAdmin)
  })

  test('GDJ-01 batch, student and mentor handoff', async ({ page }) => {
    await openStaffFromRoleHome(page, '批次与规则', '/admin/graduation/batches')
    const screenshotA = await capture(page, 'GDJ-01', 'A-first-screen')
    const row = page.locator('.dt__tr').filter({ hasText: fixture.batchName }).first()
    await expect(row).toBeVisible()
    await row.getByRole('button', { name: '详情/配置' }).click()
    await expect(page).toHaveURL(new RegExp(`/admin/graduation/batches/${fixture.batchId}`))
    await assertHealthyPage(page)
    const screenshotB = await capture(page, 'GDJ-01', 'B-action-receipt')

    const context = await page.context().browser().newContext()
    const handoff = await context.newPage()
    try {
      await loginTeacherMini(handoff)
      await expect(handoff.getByText(/当前身份：\s*GD_MENTOR/).first()).toBeVisible()
      const screenshotC = await capture(handoff, 'GDJ-01', 'C-handoff')
      const students = await adminApi.get('/graduation/gd-students', { batchId: fixture.batchId, page: 1, pageSize: 30 })
      await writeMeta('GDJ-01', { screenshotA, screenshotB, screenshotC, action: '打开批次详情/配置', serverTruth: { studentCount: items(students).length, teacherBatchId: teacherFixture.batchId } })
    } finally { await context.close() }
  })

  test('GDJ-02 topic library to student topic handoff', async ({ page }) => {
    await openStaffFromRoleHome(page, '题目库', '/admin/graduation/topic-lib')
    const screenshotA = await capture(page, 'GDJ-02', 'A-first-screen')
    await page.getByPlaceholder('题目 / 教师 / 企业').fill(fixture.topicTitle)
    await page.getByRole('button', { name: '查询', exact: true }).click()
    const topicRow = page.locator('.dt__tr').filter({ hasText: fixture.topicTitle }).first()
    await expect(topicRow).toBeVisible()
    await topicRow.getByRole('button', { name: '详情', exact: true }).click()
    const action = '搜索真实题目并打开详情'
    await assertHealthyPage(page)
    const screenshotB = await capture(page, 'GDJ-02', 'B-action-receipt')

    const context = await page.context().browser().newContext()
    const handoff = await context.newPage()
    try {
      await openStudentFromRoleHome(handoff)
      const topicStep = handoff.locator('.gd-step').filter({ hasText: /选题|题目/ }).first()
      await expect(topicStep).toBeVisible()
      const screenshotC = await capture(handoff, 'GDJ-02', 'C-handoff')
      const topics = await adminApi.get('/graduation/gd-topics', { batchId: fixture.batchId, page: 1, pageSize: 30, archiveView: 'active' })
      await writeMeta('GDJ-02', { screenshotA, screenshotB, screenshotC, action, serverTruth: { topicCount: items(topics).length, stableTopic: fixture.topicTitle } })
    } finally { await context.close() }
  })

  test('GDJ-03 taskbook and proposal continuous review handoff', async ({ page }) => {
    await openStaffFromRoleHome(page, '待评阅开题', '/admin/graduation/proposals')
    const screenshotA = await capture(page, 'GDJ-03', 'A-first-screen')
    const queueItem = page.getByRole('button').filter({ hasText: teacherFixture.topicTitle }).first()
    await expect(queueItem).toBeVisible()
    await queueItem.click()
    await expect(page.locator('.gd-review-workspace__document')).toBeVisible()
    const screenshotB = await capture(page, 'GDJ-03', 'B-action-receipt')

    const context = await page.context().browser().newContext()
    const handoff = await context.newPage()
    try {
      await loginTeacherMini(handoff)
      await handoff.getByText('任务书', { exact: true }).first().click()
      await expect(handoff.getByText(/任务书列表/).first()).toBeVisible()
      const screenshotC = await capture(handoff, 'GDJ-03', 'C-handoff')
      const taskbook = await adminApi.get(`/graduation/gd-taskbooks/${teacherFixture.gdStudentId}`, { batchId: fixture.batchId })
      const proposals = await adminApi.get('/graduation/proposals', { batchId: fixture.batchId, keyword: teacherFixture.studentNo, page: 1, pageSize: 30 })
      await writeMeta('GDJ-03', { screenshotA, screenshotB, screenshotC, action: '从待办队列打开真实待审开题', serverTruth: { taskbookStatus: taskbook.status, proposalCount: items(proposals).length } })
    } finally { await context.close() }
  })

  test('GDJ-04 process and midterm exact-context handoff', async ({ page }) => {
    await openStaffFromRoleHome(page, '过程指导台', '/admin/graduation/process')
    const screenshotA = await capture(page, 'GDJ-04', 'A-first-screen')
    const action = await clickFirstVisible(page, ['指导记录', '中期检查', '任务书'])
    await assertHealthyPage(page)
    const screenshotB = await capture(page, 'GDJ-04', 'B-action-receipt')

    const context = await page.context().browser().newContext()
    const handoff = await context.newPage()
    try {
      await loginTeacherMini(handoff)
      await handoff.getByText('批阅中期', { exact: true }).click()
      await expect(handoff.getByText(/中期/).first()).toBeVisible()
      const screenshotC = await capture(handoff, 'GDJ-04', 'C-handoff')
      const rows = await adminApi.get('/graduation/gd-guidances', { batchId: fixture.batchId, gdStudentId: fixture.gdStudentId, page: 1, pageSize: 30 })
      await writeMeta('GDJ-04', { screenshotA, screenshotB, screenshotC, action, serverTruth: { guidanceCount: items(rows).length } })
    } finally { await context.close() }
  })

  test('GDJ-05 final review and human material evidence handoff', async ({ page }) => {
    await openStaffFromRoleHome(page, '待评阅成果', '/admin/graduation/finals')
    const screenshotA = await capture(page, 'GDJ-05', 'A-first-screen')
    const action = await clickFirstVisible(page, ['待评阅', '全部', '已退回'])
    await assertHealthyPage(page)
    const screenshotB = await capture(page, 'GDJ-05', 'B-action-receipt')

    const context = await page.context().browser().newContext()
    const handoff = await context.newPage()
    try {
      await openStudentFromRoleHome(handoff, { materials: true })
      await expect(handoff.getByText(/材料库|材料状态/).first()).toBeVisible()
      const screenshotC = await capture(handoff, 'GDJ-05', 'C-handoff')
      const finals = await adminApi.get('/graduation/finals', { batchId: fixture.batchId, page: 1, pageSize: 30 })
      await writeMeta('GDJ-05', { screenshotA, screenshotB, screenshotC, action, serverTruth: { finalCount: items(finals).length } })
    } finally { await context.close() }
  })

  test('GDJ-06 defense arrangement to defense-day Mini handoff', async ({ page }) => {
    await openStaffFromRoleHome(page, '答辩安排', '/admin/graduation/defense')
    const screenshotA = await capture(page, 'GDJ-06', 'A-first-screen')
    const action = await clickFirstVisible(page, ['＋ 新增答辩组', '答辩分组', '待发布', '已发布', '刷新'])
    await assertHealthyPage(page)
    const screenshotB = await capture(page, 'GDJ-06', 'B-action-receipt')

    const context = await page.context().browser().newContext()
    const handoff = await context.newPage()
    try {
      await loginTeacherMini(handoff, graduationRoles.defenseExpert)
      await handoff.getByText('答辩评分', { exact: true }).click()
      await expect(handoff.getByText(/答辩评分/).first()).toBeVisible()
      const screenshotC = await capture(handoff, 'GDJ-06', 'C-handoff')
      const groups = await adminApi.get('/graduation/defense-groups', { batchId: fixture.batchId, page: 1, pageSize: 30 })
      await writeMeta('GDJ-06', { screenshotA, screenshotB, screenshotC, action, serverTruth: { defenseGroupCount: items(groups).length } })
    } finally { await context.close() }
  })

  test('GDJ-07 grade ledger and bound student result handoff', async ({ page }) => {
    await openStaffFromRoleHome(page, '成绩台账', '/admin/graduation/grade-ledger')
    const screenshotA = await capture(page, 'GDJ-07', 'A-first-screen')
    const action = await clickFirstVisible(page, ['成绩', '待核算', '待复核', '已发布'])
    await assertHealthyPage(page)
    const screenshotB = await capture(page, 'GDJ-07', 'B-action-receipt')

    const context = await page.context().browser().newContext()
    const handoff = await context.newPage()
    try {
      await openStudentFromRoleHome(handoff)
      await expect(handoff.locator('.gd-step').filter({ hasText: /成绩|答辩/ }).first()).toBeVisible()
      const screenshotC = await capture(handoff, 'GDJ-07', 'C-handoff')
      const grades = await adminApi.get('/graduation/gd-grades', { batchId: fixture.batchId, page: 1, pageSize: 30 })
      await writeMeta('GDJ-07', { screenshotA, screenshotB, screenshotC, action, serverTruth: { gradeCount: items(grades).length } })
    } finally { await context.close() }
  })

  test('GDJ-08 risk scan and exact archive-fix handoff', async ({ page }) => {
    const archiveProjection = await ensureArchiveProjection(adminApi, fixture)
    await openStaffFromRoleHome(page, '毕设材料归档', '/admin/graduation/risk-archive')
    await expect.poll(() => new URL(page.url()).searchParams.get('panel')).toBe('archive')
    const screenshotA = await capture(page, 'GDJ-08', 'A-first-screen')
    const archiveRow = page.getByText(fixture.studentNo, { exact: true }).first()
    await expect(archiveRow).toBeVisible()
    await archiveRow.click()
    await expect(page.getByText(/归档核验/).first()).toBeVisible()
    const screenshotB = await capture(page, 'GDJ-08', 'B-action-receipt')

    const context = await page.context().browser().newContext()
    const handoff = await context.newPage()
    try {
      await openStudentFromRoleHome(handoff, { materials: true })
      await expect(handoff.getByText(/尚未上传版本|等待扫描|材料库/).first()).toBeVisible()
      const screenshotC = await capture(handoff, 'GDJ-08', 'C-handoff')
      const archives = await adminApi.get('/graduation/gd-archives', { batchId: fixture.batchId, page: 1, pageSize: 30 })
      await writeMeta('GDJ-08', {
        screenshotA,
        screenshotB,
        screenshotC,
        action: '从风险与归档工作区进入精确归档页并读取逐项缺口',
        serverTruth: {
          archiveCount: items(archives).length,
          archiveId: String(archiveProjection.id || archiveProjection.archiveId || ''),
          archiveStatus: archiveProjection.status || ''
        }
      })
    } finally { await context.close() }
  })
})
