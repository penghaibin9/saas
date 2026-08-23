import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { items, loginApi, prepareGraduationFixture } from '../lib/api-fixture.mjs'
import { StaffLoginPage } from '../pages/login.page.mjs'

const reviewerAccount = {
  tenant: config.mentor.tenant,
  username: 'e2e_reviewer',
  password: config.mentor.password,
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

async function ensureReviewerMentor() {
  const admin = await loginApi(config.sandboxAdmin)
  const rows = items(await admin.get('/graduation/gd-mentors', {
    keyword: reviewerAccount.username,
    page: 1,
    pageSize: 200,
  }))
  let mentor = rows.find((row) => String(row.teacherNo || '') === reviewerAccount.username)
  if (!mentor) {
    mentor = await admin.post('/graduation/gd-mentors', {
      teacherNo: reviewerAccount.username,
      teacherName: 'E2E评阅教师',
      mentorType: 'INTERNAL',
      title: '讲师',
      researchDirection: '软件工程评阅与质量保障',
      maxCapacity: 20,
      submitReview: true,
      remark: 'E2E-AUDIT-20260823 independent reviewer fixture',
    })
  }
  const status = String(mentor.qualificationStatus || mentor.reviewStatus || '').toUpperCase()
  if (!['QUALIFIED', 'APPROVED'].includes(status)) {
    try {
      mentor = await admin.post(`/graduation/gd-mentors/${mentor.id}/review`, {
        action: 'APPROVE',
        comment: 'E2E-AUDIT-20260823 独立评阅教师资格通过',
      })
    } catch (error) {
      if (!/已审核|无需审核|状态/.test(error.message)) throw error
    }
  }
  return mentor
}

async function openReviewWorkspace(page, account, fixture) {
  await new StaffLoginPage(page, config.staffBaseUrl).login(account)
  const url = new URL(`${config.staffBaseUrl}/admin/graduation/review-tasks`)
  url.searchParams.set('batchId', fixture.batchId)
  url.searchParams.set('studentId', fixture.gdStudentId)
  url.searchParams.set('panel', 'review')
  url.searchParams.set('source', 'E2E-AUDIT-20260823')
  await page.goto(url.toString())
  await dismissGuide(page)
  await expect(page.getByRole('heading', { name: '答辩与成绩', exact: true })).toBeVisible()
  await expect(page.locator('.gp-context')).toContainText(fixture.studentNo)
  await expect(page.getByRole('button', { name: '教师评阅', exact: true })).toBeVisible()
}

async function assignReviewer(page, fixture) {
  await openReviewWorkspace(page, config.sandboxAdmin, fixture)
  const panel = page.locator('.gp-panel')
  const picker = panel.locator('.app-remote-select').first()
  await picker.locator('.app-remote-select__control').click()
  const search = picker.locator('.app-remote-select__search-el')
  await expect(search).toBeVisible()
  await search.fill(reviewerAccount.username)
  const option = picker.locator('.app-remote-select__option').filter({ hasText: 'E2E评阅教师' }).first()
  await expect(option).toBeVisible()
  await option.click()

  const [response] = await Promise.all([
    page.waitForResponse((r) => r.request().method() === 'POST' && new URL(r.url()).pathname.endsWith('/graduation/gd-reviews/assign')),
    page.getByRole('button', { name: '分配评阅', exact: true }).click(),
  ])
  expect(response.ok(), `assign review HTTP ${response.status()}`).toBeTruthy()
  const body = await response.json()
  expect(body.code).toBe(0)
  expect(body.data?.id).toBeTruthy()
  await expect(page.locator('.gp-timeline-item').filter({ hasText: 'E2E评阅教师' }).first()).toContainText(/待评阅|评阅/)
  return String(body.data.id)
}

async function submitReview(page, fixture, reviewId, score, opinion) {
  await openReviewWorkspace(page, reviewerAccount, fixture)
  const row = page.locator('.gp-timeline-item').filter({ hasText: 'E2E评阅教师' }).first()
  await expect(row).toBeVisible()
  await row.getByRole('button', { name: '提交评阅', exact: true }).click()
  await expect(page.getByRole('heading', { name: '提交评阅', exact: true })).toBeVisible()
  const form = page.locator('form.ie-form')
  await form.locator('label').filter({ hasText: '评分(0-100)' }).locator('input').fill(String(score))
  await form.locator('label').filter({ hasText: '评阅意见' }).locator('textarea').fill(opinion)
  const [response] = await Promise.all([
    page.waitForResponse((r) => r.request().method() === 'POST' && new URL(r.url()).pathname.endsWith(`/graduation/gd-reviews/${reviewId}/submit`)),
    page.getByRole('button', { name: '提交', exact: true }).click(),
  ])
  expect(response.ok(), `submit review HTTP ${response.status()}`).toBeTruthy()
  const body = await response.json()
  expect(body.code).toBe(0)
  expect(body.data?.status).toBe('COMPLETED')
  await expect(page.locator('.gp-timeline-item').filter({ hasText: 'E2E评阅教师' }).first()).toContainText(String(score))
}

async function returnReview(page, fixture, reviewId) {
  await openReviewWorkspace(page, config.sandboxAdmin, fixture)
  const row = page.locator('.gp-timeline-item').filter({ hasText: 'E2E评阅教师' }).first()
  await expect(row).toContainText(/已完成|完成/)
  await row.getByRole('button', { name: '退回重评', exact: true }).click()
  await expect(page.getByRole('heading', { name: '退回重评', exact: true })).toBeVisible()
  const reason = 'E2E-AUDIT-20260823 评阅退回：补充边界条件、异常路径与验证依据后重新评阅。'
  await page.locator('form.ie-form textarea').fill(reason)
  const [response] = await Promise.all([
    page.waitForResponse((r) => r.request().method() === 'POST' && new URL(r.url()).pathname.endsWith(`/graduation/gd-reviews/${reviewId}/return`)),
    page.getByRole('button', { name: '提交', exact: true }).click(),
  ])
  expect(response.ok(), `return review HTTP ${response.status()}`).toBeTruthy()
  const body = await response.json()
  expect(body.code).toBe(0)
  expect(body.data?.status).toBe('RETURNED')
  await expect(page.locator('.gp-timeline-item').filter({ hasText: 'E2E评阅教师' }).first()).toContainText(/已退回|退回/)
}

test.describe.configure({ retries: 0 })

test.describe.serial('毕业设计独立评阅 Browser First · 分配/提交/退回/重评', () => {
  let fixture

  test.beforeAll(async () => {
    fixture = await prepareGraduationFixture()
    await ensureReviewerMentor()
  })

  test('管理员真实分配 → 独立评阅教师提交 → 管理员退回 → 评阅教师重评 → 刷新保持', async ({ page }) => {
    const reviewId = await assignReviewer(page, fixture)
    await submitReview(
      page,
      fixture,
      reviewId,
      88,
      'E2E-AUDIT-20260823 首次独立评阅：总体完成度良好，但异常路径与证据链需要补强。',
    )
    await returnReview(page, fixture, reviewId)
    await submitReview(
      page,
      fixture,
      reviewId,
      92,
      'E2E-AUDIT-20260823 重评完成：已复核异常路径、边界条件与测试证据，结论通过。',
    )

    await page.reload()
    await dismissGuide(page)
    const row = page.locator('.gp-timeline-item').filter({ hasText: 'E2E评阅教师' }).first()
    await expect(row).toContainText('92')
    await expect(row).toContainText('E2E-AUDIT-20260823 重评完成')
    await expect(row.getByRole('button', { name: '提交评阅', exact: true })).toHaveCount(0)
  })
})
