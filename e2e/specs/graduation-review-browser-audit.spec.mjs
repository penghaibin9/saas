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

async function chooseReviewer(page) {
  const picker = page.locator('.ra-assignment .app-remote-select').first()
  await picker.locator('.app-remote-select__control').click()
  const search = picker.locator('.app-remote-select__search-el')
  await expect(search).toBeVisible()
  await search.fill(reviewerAccount.username)
  const option = picker.locator('.app-remote-select__option').filter({ hasText: 'E2E评阅教师' }).first()
  await expect(option).toBeVisible()
  await option.click()
}

async function assignReviewer(page, fixture) {
  await new StaffLoginPage(page, config.staffBaseUrl).login(config.sandboxAdmin)
  const url = new URL(`${config.staffBaseUrl}/admin/graduation/review-assign`)
  url.searchParams.set('batchId', fixture.batchId)
  url.searchParams.set('studentId', fixture.gdStudentId)
  url.searchParams.set('source', 'E2E-AUDIT-20260823')
  await page.goto(url.toString())
  await dismissGuide(page)
  await expect(page.getByRole('heading', { name: '正式评阅分配', exact: true })).toBeVisible()
  await expect(page.locator('.ra-assignment')).toContainText(fixture.studentNo)
  await chooseReviewer(page)
  const [response] = await Promise.all([
    page.waitForResponse((r) => r.request().method() === 'POST' && new URL(r.url()).pathname.endsWith('/graduation/gd-reviews/assign')),
    page.getByRole('button', { name: '分配正式评阅', exact: true }).click(),
  ])
  expect(response.ok(), `assign review HTTP ${response.status()}`).toBeTruthy()
  const body = await response.json()
  expect(body.code, JSON.stringify(body)).toBe(0)
  expect(body.data?.id).toBeTruthy()
  await expect(page.getByRole('button', { name: '进入统一评阅中心', exact: true })).toBeVisible()
  return String(body.data.id)
}

async function openFormalTask(page, account, fixture, { reviewerOnly = false } = {}) {
  await new StaffLoginPage(page, config.staffBaseUrl).login(account)
  const url = new URL(`${config.staffBaseUrl}/admin/graduation/review-tasks`)
  url.searchParams.set('batchId', fixture.batchId)
  url.searchParams.set('source', 'E2E-AUDIT-20260823')
  await page.goto(url.toString())
  await dismissGuide(page)
  await expect(page.locator('[aria-label="评阅队列筛选"]')).toBeVisible()
  await page.getByRole('button', { name: '正式评阅', exact: true }).click()
  if (reviewerOnly) {
    const checkbox = page.getByLabel('只看分配给我的正式评阅')
    if (!(await checkbox.isChecked())) await checkbox.check()
  }
  const search = page.getByPlaceholder('学生 / 学号 / 班级 / 课题')
  await search.fill(fixture.studentNo)
  const row = page.locator('.gd-review-workspace__queue > button').filter({ hasText: fixture.topicTitle }).first()
  await expect(row).toBeVisible()
  await row.click()
  await expect(page.locator('.w74-case-type')).toContainText('正式评阅')
  return row
}

async function submitReview(page, fixture, reviewId, score, opinion) {
  await openFormalTask(page, reviewerAccount, fixture, { reviewerOnly: true })
  const form = page.locator('.w74-write-form')
  await expect(form).toBeVisible()
  await form.locator('label').filter({ hasText: '评阅评分' }).locator('input').fill(String(score))
  await form.locator('label').filter({ hasText: '评阅意见' }).locator('textarea').fill(opinion)
  const [response] = await Promise.all([
    page.waitForResponse((r) => r.request().method() === 'POST' && new URL(r.url()).pathname.endsWith(`/graduation/gd-reviews/${reviewId}/submit`)),
    page.getByRole('button', { name: '提交正式评阅', exact: true }).click(),
  ])
  expect(response.ok(), `submit review HTTP ${response.status()}`).toBeTruthy()
  const body = await response.json()
  expect(body.code, JSON.stringify(body)).toBe(0)
  expect(body.data?.status).toBe('COMPLETED')
}

async function returnReview(page, fixture, reviewId) {
  await openFormalTask(page, config.sandboxAdmin, fixture)
  const section = page.locator('.w74-return-form')
  await expect(section).toBeVisible()
  const reason = 'E2E-AUDIT-20260823 评阅退回：补充边界条件、异常路径与验证依据后重新评阅。'
  await section.locator('textarea').fill(reason)
  const [response] = await Promise.all([
    page.waitForResponse((r) => r.request().method() === 'POST' && new URL(r.url()).pathname.endsWith(`/graduation/gd-reviews/${reviewId}/return`)),
    section.getByRole('button', { name: '退回重评', exact: true }).click(),
  ])
  expect(response.ok(), `return review HTTP ${response.status()}`).toBeTruthy()
  const body = await response.json()
  expect(body.code, JSON.stringify(body)).toBe(0)
  expect(body.data?.status).toBe('RETURNED')
}

test.describe.configure({ retries: 0 })

test.describe.serial('毕业设计正式评阅 Browser First · 菜单分配/提交/退回/重评', () => {
  let fixture

  test.beforeAll(async () => {
    fixture = await prepareGraduationFixture()
    await ensureReviewerMentor()
  })

  test('管理员从正式菜单分配 → GD_REVIEWER 统一评阅中心提交 → 管理员退回 → 重评 → 刷新保持', async ({ page }) => {
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

    await openFormalTask(page, reviewerAccount, fixture, { reviewerOnly: true })
    await expect(page.locator('.w74-feedback-list')).toContainText('E2E-AUDIT-20260823 重评完成')
    await page.reload()
    await dismissGuide(page)
    await expect(page.locator('.gd-review-workspace__queue > button').filter({ hasText: fixture.topicTitle }).first()).toBeVisible()
  })
})
