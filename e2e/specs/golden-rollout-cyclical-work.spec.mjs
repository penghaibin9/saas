import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { loadInternshipFixture } from '../lib/internship-fixture.mjs'
import { items, loginApi, prepareGraduationFixture } from '../lib/api-fixture.mjs'

const VIEWPORT = { width: 1440, height: 1000 }

function runId() {
  const raw = process.env.GITHUB_RUN_ID || `${Date.now()}`
  return String(raw).replace(/\D/g, '').slice(-12) || String(Date.now()).slice(-12)
}

async function dismissGuide(page) {
  for (const mask of [page.locator('.app-step-guide__mask'), page.locator('.tour-mask')]) {
    if (await mask.isVisible().catch(() => false)) {
      const skip = page.getByRole('button', { name: /跳过引导|跳过/ }).first()
      if (await skip.isVisible().catch(() => false)) await skip.click()
      await mask.waitFor({ state: 'hidden', timeout: 3000 }).catch(() => {})
    }
  }
}

async function settleVisual(page) {
  await page.evaluate(async () => {
    if (document.fonts?.ready) await document.fonts.ready
  })
  await page.waitForLoadState('networkidle', { timeout: 5000 }).catch(() => {})
}

async function capture(page, testInfo, name) {
  await dismissGuide(page)
  await settleVisual(page)
  const viewportPath = testInfo.outputPath(`${name}-1440x1000.png`)
  const fullPath = testInfo.outputPath(`${name}-full.png`)
  await page.screenshot({ path: viewportPath, fullPage: false, animations: 'disabled', caret: 'hide' })
  await page.screenshot({ path: fullPath, fullPage: true, animations: 'disabled', caret: 'hide' })
  await testInfo.attach(`${name}-viewport`, { path: viewportPath, contentType: 'image/png' })
  await testInfo.attach(`${name}-full`, { path: fullPath, contentType: 'image/png' })
}

async function openStaffWorkspace(page, api, path, storage = {}) {
  await page.addInitScript(({ token, entries }) => {
    window.sessionStorage.setItem('gx_pc_token_v1', token)
    for (const [key, value] of entries) window.localStorage.setItem(key, String(value))
  }, { token: api.token, entries: Object.entries(storage) })
  await page.goto(`${config.staffBaseUrl}${path}`)
  await dismissGuide(page)
}

async function prepareTalkPlan(admin, studentNo) {
  const topic = `Golden 周期任务谈话 ${runId()}`
  const profiles = items(await admin.get('/students', { keyword: studentNo, page: 1, pageSize: 50 }))
  const profile = profiles.find((row) => String(row.studentNo || row.loginName || '') === String(studentNo))
  if (!profile?.id) throw new Error(`Golden Batch 12 student profile ${studentNo} not found`)

  let talk = items(await admin.get('/student-affairs/talks', {
    studentId: String(profile.id), page: 1, pageSize: 200
  })).find((row) => String(row.topic || '') === topic)

  if (!talk) {
    const created = await admin.post('/student-affairs/talks', {
      studentIds: [String(profile.id)],
      talkType: 'ACADEMIC',
      topic
    })
    const talkId = String(created?.talkIds?.[0] || '')
    if (!talkId) throw new Error('Golden Batch 12 talk creation did not return talkId')
    talk = await admin.get(`/student-affairs/talks/${talkId}`)
  }

  return { id: String(talk.talkId || talk.id || ''), topic }
}

test.describe.serial('Golden rollout · cyclical task / planning and review · Batch 12', () => {
  let adminApi
  let internshipFixture
  let graduationFixture
  let talkFixture

  test.beforeAll(async () => {
    internshipFixture = await loadInternshipFixture()
    graduationFixture = await prepareGraduationFixture()
    adminApi = await loginApi(config.sandboxAdmin)
    talkFixture = await prepareTalkPlan(adminApi, internshipFixture.studentNo)
  })

  test('Student Affairs talk planning workspace · Screenshot B', async ({ page }, testInfo) => {
    await page.setViewportSize(VIEWPORT)
    await openStaffWorkspace(page, adminApi, '/admin/student-affairs/talk')

    await expect(page).toHaveURL(/\/admin\/student-affairs\/talk/)
    await expect(page.getByRole('heading', { name: '谈心谈话工作台', exact: true })).toBeVisible()
    await expect(page.locator('.tk-toolbar')).toBeVisible()
    await expect(page.locator('.tk-workspace')).toBeVisible()

    const target = page.locator('.tk-qitem').filter({ hasText: talkFixture.topic }).first()
    await expect(target).toBeVisible()
    await target.click()
    await expect(target).toHaveClass(/is-active/)
    await expect(page.locator('.tk-detail')).toContainText(talkFixture.topic)
    await expect(page.locator('.tk-record-prompt')).toBeVisible()
    await page.getByRole('button', { name: '填写记录', exact: true }).click()
    const record = page.getByRole('dialog', { name: /填写谈话记录/ })
    await expect(record).toBeVisible()
    await record.getByPlaceholder('客观记录谈话过程与主要内容').fill('本次核对学生近期学习与生活情况，约定后续跟进时间。')
    await expect(record.getByRole('button', { name: '提交记录', exact: true })).toBeEnabled()
    await record.getByRole('button', { name: '取消', exact: true }).click()
    await expect(record).toBeHidden()
    await expect(page.locator('.tk-detail')).toContainText(talkFixture.topic)

    await capture(page, testInfo, 'rollout-cyclical-affairs-talk-planning-b')
  })

  test('Internship plan / task workspace · Screenshot B', async ({ page }, testInfo) => {
    await page.setViewportSize(VIEWPORT)
    await openStaffWorkspace(page, adminApi, `/admin/internship/plans?batchId=${encodeURIComponent(internshipFixture.batchId)}`)

    await expect(page).toHaveURL(/\/admin\/internship\/plans/)
    await expect(page.getByRole('heading', { name: '计划任务', exact: true })).toBeVisible()
    const navigation = page.getByRole('navigation', { name: '计划任务工作区' })
    await expect(page.getByRole('heading', { name: '计划编制', exact: true })).toBeVisible()
    await expect(page.locator('.card--editor textarea').last()).toBeVisible()
    await navigation.getByRole('button', { name: '学生确认', exact: true }).click()
    await expect(page.getByRole('heading', { name: '学生确认台账', exact: true })).toBeVisible()
    await expect(page.locator('.card--editor')).toBeHidden()
    await navigation.getByRole('button', { name: '任务清单', exact: true }).click()
    await expect(page.getByRole('heading', { name: '实习任务清单', exact: true })).toBeVisible()
    await expect(page.locator('.card--tasks')).toBeVisible()
    await navigation.getByRole('button', { name: '计划编制', exact: true }).click()
    await expect(page.locator('.card--editor')).toBeVisible()

    await capture(page, testInfo, 'rollout-cyclical-internship-plan-tasks-b')
  })

  test('Graduation defense scheduling workspace · Screenshot B', async ({ page }, testInfo) => {
    await page.setViewportSize(VIEWPORT)
    const path = `/admin/graduation/defense?batchId=${encodeURIComponent(graduationFixture.batchId)}`
    await openStaffWorkspace(page, adminApi, path)

    await expect(page).toHaveURL(/\/admin\/graduation\/defense/)
    await expect(page.getByRole('heading', { name: '答辩安排', exact: true })).toBeVisible()
    await expect(page.locator('.gd-actions')).toBeVisible()
    await expect(page.getByRole('button', { name: /新增答辩组/ }).first()).toBeVisible()

    await capture(page, testInfo, 'rollout-cyclical-graduation-defense-schedule-b')
  })
})
