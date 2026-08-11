import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { loadInternshipFixture } from '../lib/internship-fixture.mjs'
import { Api, items, loginApi, prepareGraduationFixture } from '../lib/api-fixture.mjs'

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

async function switchApiRole(api, roleCode) {
  const me = await api.get('/auth/me')
  if (String(me.currentRole?.roleCode || '').toUpperCase() === roleCode) return api
  const context = (me.contexts || []).find((row) => String(row.roleCode || '').toUpperCase() === roleCode)
  if (!context?.contextId) throw new Error(`E2E account ${config.mentor.username} is missing role ${roleCode}`)
  const switched = await api.post('/auth/switch-role', { contextId: context.contextId, clientType: 'PC' })
  if (!switched?.accessToken) throw new Error(`Role switch to ${roleCode} did not return an access token`)
  return new Api(switched.accessToken)
}

async function prepareTalkLedger(admin, studentNo) {
  const marker = runId()
  const topic = `Golden 过程谈话 ${marker}`
  const profiles = items(await admin.get('/students', { keyword: studentNo, page: 1, pageSize: 50 }))
  const profile = profiles.find((row) => String(row.studentNo || row.loginName || '') === String(studentNo))
  if (!profile?.id) throw new Error(`Golden Batch 9 student profile ${studentNo} not found`)

  let talk = items(await admin.get('/student-affairs/talks', {
    studentId: String(profile.id), page: 1, pageSize: 200
  })).find((row) => String(row.topic || '') === topic)

  if (!talk) {
    const created = await admin.post('/student-affairs/talks', {
      studentIds: [String(profile.id)],
      talkType: 'INTERNSHIP',
      topic
    })
    const talkId = String(created?.talkIds?.[0] || '')
    if (!talkId) throw new Error('Golden Batch 9 talk creation did not return talkId')
    talk = await admin.get(`/student-affairs/talks/${talkId}`)
  }

  return { id: String(talk.talkId || talk.id || ''), topic, studentNo }
}

async function prepareInternshipGuidance(mentor, internshipFixture) {
  const marker = runId()
  const topic = '岗位任务与阶段进度复盘'
  const content = `Golden Batch 9 ${marker}：现场核对岗位任务、学习进度与安全事项，当前实践节奏正常。`
  const rows = items(await mentor.get('/internship/guidances', {
    batchId: internshipFixture.batchId, page: 1, pageSize: 200
  }))
  let guidance = rows.find((row) => String(row.content || '') === content)
  if (!guidance) {
    const created = await mentor.post('/internship/guidances', {
      internshipId: String(internshipFixture.internshipId),
      method: 'ONSITE',
      topic,
      content,
      suggestion: '继续按周完成实践任务，并保留关键过程材料。'
    })
    guidance = { id: created.id, content }
  }
  if (!guidance?.id) throw new Error('Golden Batch 9 internship guidance did not return id')
  return { id: String(guidance.id), topic, content }
}

test.describe.serial('Golden rollout · process guidance / tracking ledgers · Batch 9', () => {
  let adminApi
  let internshipFixture
  let graduationFixture
  let talkFixture
  let internshipGuidance

  test.beforeAll(async () => {
    internshipFixture = await loadInternshipFixture()
    graduationFixture = await prepareGraduationFixture()
    adminApi = await loginApi(config.sandboxAdmin)

    talkFixture = await prepareTalkLedger(adminApi, internshipFixture.studentNo)

    let mentorApi = await loginApi(config.mentor)
    mentorApi = await switchApiRole(mentorApi, 'INTERN_MENTOR')
    internshipGuidance = await prepareInternshipGuidance(mentorApi, internshipFixture)
  })

  test('Student Affairs talk ledger · Screenshot A', async ({ page }, testInfo) => {
    await page.setViewportSize(VIEWPORT)
    await openStaffWorkspace(page, adminApi, '/admin/student-affairs/talk/ledger')

    await expect(page).toHaveURL(/\/admin\/student-affairs\/talk\/ledger/)
    await expect(page.getByRole('heading', { name: '谈心谈话台账', exact: true })).toBeVisible()
    await expect(page.locator('.sa-grid--metrics')).toBeVisible()
    await expect(page.locator('.tl-filters')).toBeVisible()
    await expect(page.locator('.dt')).toBeVisible()
    await expect(page.locator('.dt__tr').filter({ hasText: talkFixture.topic }).first()).toBeVisible()

    await capture(page, testInfo, 'rollout-process-affairs-talk-ledger-a')
  })

  test('Internship guidance workspace · Screenshot A', async ({ page }, testInfo) => {
    await page.setViewportSize(VIEWPORT)
    const path = `/admin/internship/guidance?panel=guidance&batchId=${encodeURIComponent(internshipFixture.batchId)}`
    await openStaffWorkspace(page, adminApi, path, {
      'internship.selectedBatchId': internshipFixture.batchId
    })

    await expect(page).toHaveURL(/\/admin\/internship\/guidance/)
    await expect(page.getByRole('heading', { name: '指导巡访管理', exact: true })).toBeVisible()
    await expect(page.locator('.tabs')).toBeVisible()
    await expect(page.locator('.gv-list')).toBeVisible()

    const target = page.locator('.gv-item').filter({ hasText: internshipFixture.studentName })
      .filter({ hasText: internshipGuidance.topic }).first()
    await expect(target).toBeVisible()
    await target.click()
    await expect(target).toHaveClass(/is-active/)
    await expect(page.locator('.gv-main')).toContainText(internshipFixture.studentName)
    await expect(page.locator('.gv-main')).toContainText('指导详情')
    await expect(page.locator('.gv-main')).toContainText(internshipGuidance.content)

    await capture(page, testInfo, 'rollout-process-internship-guidance-a')
  })

  test('Graduation mentor assignment ledger · Screenshot A', async ({ page }, testInfo) => {
    await page.setViewportSize(VIEWPORT)
    await openStaffWorkspace(page, adminApi, '/admin/graduation/mentors?panel=assign')

    await expect(page).toHaveURL(/\/admin\/graduation\/mentors/)
    await expect(page.getByRole('heading', { name: '导师管理', exact: true })).toBeVisible()
    await expect(page.locator('.gm-tabs__item.is-active')).toContainText('导师分配')
    await expect(page.locator('.gm-assign-hint')).toBeVisible()
    await expect(page.locator('.gm-section-title')).toContainText('分配记录')

    const assignmentTable = page.locator('.dt').filter({ hasText: '学生 ← 导师' }).first()
    await expect(assignmentTable).toBeVisible()
    await expect(assignmentTable.locator('.dt__tr').filter({ hasText: graduationFixture.mentorName }).first()).toBeVisible()

    await capture(page, testInfo, 'rollout-process-graduation-mentor-assignment-a')
  })
})