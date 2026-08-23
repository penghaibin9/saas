import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { items, loginApi, prepareGraduationFixture } from '../lib/api-fixture.mjs'
import { StaffLoginPage } from '../pages/login.page.mjs'

const accounts = {
  expertA: { tenant: config.mentor.tenant, username: 'e2e_defense_a', password: config.mentor.password },
  expertB: { tenant: config.mentor.tenant, username: 'e2e_defense_b', password: config.mentor.password },
  secretary: { tenant: config.mentor.tenant, username: 'e2e_defense_secretary', password: config.mentor.password },
}

const people = {
  expertA: { teacherNo: 'e2e_defense_a', teacherName: 'E2E答辩专家A', title: '副教授' },
  expertB: { teacherNo: 'e2e_defense_b', teacherName: 'E2E答辩专家B', title: '副教授' },
  secretary: { teacherNo: 'e2e_defense_secretary', teacherName: 'E2E答辩秘书', title: '讲师' },
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

async function ensureMentor(admin, person) {
  const rows = items(await admin.get('/graduation/gd-mentors', { keyword: person.teacherNo, page: 1, pageSize: 200 }))
  let mentor = rows.find((row) => String(row.teacherNo || '') === person.teacherNo)
  if (!mentor) {
    mentor = await admin.post('/graduation/gd-mentors', {
      teacherNo: person.teacherNo,
      teacherName: person.teacherName,
      mentorType: 'INTERNAL',
      title: person.title,
      researchDirection: 'E2E-AUDIT-20260823 答辩质量保障',
      maxCapacity: 20,
      submitReview: true,
      remark: 'E2E-AUDIT-20260823 defense specialist fixture',
    })
  }
  const status = String(mentor.qualificationStatus || mentor.reviewStatus || '').toUpperCase()
  if (!['QUALIFIED', 'APPROVED'].includes(status)) {
    try {
      mentor = await admin.post(`/graduation/gd-mentors/${mentor.id}/review`, {
        action: 'APPROVE', comment: 'E2E-AUDIT-20260823 答辩人员资格通过',
      })
    } catch (error) {
      if (!/已审核|无需审核|状态/.test(error.message)) throw error
    }
  }
  return mentor
}

async function loginStaff(page, account, octet) {
  await page.context().setExtraHTTPHeaders({ 'X-Forwarded-For': `10.253.0.${octet}` })
  await new StaffLoginPage(page, config.staffBaseUrl).login(account)
}

async function chooseMentor(field, query, visibleName) {
  const picker = field.locator('.app-remote-select').first()
  await picker.locator('.app-remote-select__control').click()
  const search = picker.locator('.app-remote-select__search-el')
  await expect(search).toBeVisible()
  await search.fill(query)
  const option = picker.locator('.app-remote-select__option').filter({ hasText: visibleName }).first()
  await expect(option).toBeVisible()
  await option.click()
}

async function openScoring(page, account, fixture, octet) {
  await loginStaff(page, account, octet)
  const url = new URL(`${config.staffBaseUrl}/admin/graduation/defense-scoring`)
  url.searchParams.set('batchId', fixture.batchId)
  url.searchParams.set('studentId', fixture.gdStudentId)
  url.searchParams.set('panel', 'defense')
  url.searchParams.set('source', 'E2E-AUDIT-20260823')
  await page.goto(url.toString())
  await dismissGuide(page)
  await expect(page.getByRole('heading', { name: '答辩与成绩', exact: true })).toBeVisible()
  await expect(page.locator('.gp-context')).toContainText(fixture.studentNo)
  await expect(page.getByRole('button', { name: '答辩评分', exact: true })).toBeVisible()
}

async function enterOwnScore(page, fixture, account, person, score, roundNo, octet) {
  await openScoring(page, account, fixture, octet)
  await page.getByRole('button', { name: '录入评委评分', exact: true }).click()
  await expect(page.getByRole('heading', { name: '录入评委评分', exact: true })).toBeVisible()
  const form = page.locator('form.ie-form')
  await form.locator('label').filter({ hasText: '评委姓名' }).locator('input').fill(person.teacherName)
  await form.locator('label').filter({ hasText: '评分(0-100' }).locator('input').fill(String(score))
  await form.locator('label').filter({ hasText: '评语' }).locator('textarea').fill(
    `E2E-AUDIT-20260823 第${roundNo}轮 ${person.teacherName} 实名评分，结论 ${score}。`,
  )
  const [response] = await Promise.all([
    page.waitForResponse((r) => r.request().method() === 'POST' && new URL(r.url()).pathname.endsWith('/graduation/gd-defense-scores/entry')),
    page.getByRole('button', { name: '提交', exact: true }).click(),
  ])
  expect(response.ok(), `defense score HTTP ${response.status()}`).toBeTruthy()
  const body = await response.json()
  expect(body.code, JSON.stringify(body)).toBe(0)
  expect(Number(body.data?.roundNo)).toBe(roundNo)
  expect(Number(body.data?.score)).toBe(score)
  await expect(page.locator('.gp-timeline-item').filter({ hasText: person.teacherName }).first()).toContainText(String(score))
}

async function confirmRound(page, fixture, roundNo, octet) {
  await openScoring(page, accounts.secretary, fixture, octet)
  const [response] = await Promise.all([
    page.waitForResponse((r) => r.request().method() === 'POST' && new URL(r.url()).pathname.endsWith(`/graduation/gd-defense-scores/${fixture.gdStudentId}/confirm`)),
    page.getByRole('button', { name: '确认本轮成绩', exact: true }).click(),
  ])
  expect(response.ok(), `confirm defense HTTP ${response.status()}`).toBeTruthy()
  const body = await response.json()
  expect(body.code, JSON.stringify(body)).toBe(0)
  expect(Number(body.data?.roundNo)).toBe(roundNo)
  await expect(page.locator('.gp-timeline-item').filter({ hasText: `第${roundNo}轮` }).first()).toContainText(/已确认|确认/)
}

test.describe.configure({ retries: 0 })

test.describe.serial('毕业设计答辩 Browser First · 建组发布/专家评分/秘书确认/二辩', () => {
  let fixture
  let groupName

  test.beforeAll(async () => {
    fixture = await prepareGraduationFixture()
    groupName = `E2E-AUDIT-20260823 答辩组 ${fixture.runId}`
    const admin = await loginApi(config.sandboxAdmin)
    await ensureMentor(admin, people.expertA)
    await ensureMentor(admin, people.expertB)
    await ensureMentor(admin, people.secretary)
  })

  test('管理员真实建组、分配学生并发布', async ({ page }) => {
    await loginStaff(page, config.sandboxAdmin, 61)
    await page.goto(`${config.staffBaseUrl}/admin/graduation/defense?batchId=${encodeURIComponent(fixture.batchId)}`)
    await dismissGuide(page)
    await expect(page.getByRole('heading', { name: '答辩安排', exact: true })).toBeVisible()
    await page.getByRole('button', { name: /新增答辩组/ }).first().click()
    await expect(page.getByRole('heading', { name: '新增答辩组', exact: true })).toBeVisible()

    await page.getByPlaceholder('如 软件工程专业第一答辩组').fill(groupName)
    await page.getByPlaceholder('如 实训楼 A301').fill('E2E-AUDIT-20260823 实训楼 A301')
    await chooseMentor(page.locator('.ie-fld').filter({ hasText: '答辩组长' }).first(), people.expertA.teacherNo, people.expertA.teacherName)
    await chooseMentor(page.locator('.ie-fld').filter({ hasText: '答辩秘书' }).first(), people.secretary.teacherNo, people.secretary.teacherName)
    await chooseMentor(page.locator('.ie-fld').filter({ hasText: '评委名单' }).first(), people.expertB.teacherNo, people.expertB.teacherName)

    const [created] = await Promise.all([
      page.waitForResponse((r) => r.request().method() === 'POST' && new URL(r.url()).pathname.endsWith('/graduation/defense-groups')),
      page.getByRole('button', { name: '创建', exact: true }).click(),
    ])
    expect(created.ok(), `create defense group HTTP ${created.status()}`).toBeTruthy()
    const createdBody = await created.json()
    expect(createdBody.code, JSON.stringify(createdBody)).toBe(0)
    expect(createdBody.data?.id).toBeTruthy()
    await expect(page).toHaveURL(/\/admin\/graduation\/defense\/groups\/[^/]+\/edit/)

    const search = page.getByPlaceholder('搜索姓名')
    await search.fill(fixture.studentNo)
    await expect(page.locator('.dg-row--pick').first()).toBeVisible()
    await page.locator('.dg-row--pick').first().click()
    const [assigned] = await Promise.all([
      page.waitForResponse((r) => r.request().method() === 'POST' && new URL(r.url()).pathname.includes('/graduation/defense-groups/') && new URL(r.url()).pathname.endsWith('/assign')),
      page.getByRole('button', { name: /分配所选/ }).click(),
    ])
    expect(assigned.ok(), `assign defense student HTTP ${assigned.status()}`).toBeTruthy()
    const assignedBody = await assigned.json()
    expect(assignedBody.code, JSON.stringify(assignedBody)).toBe(0)
    await expect(page.locator('.dg-sec').filter({ hasText: '已分配学生' })).toContainText(fixture.topicTitle)

    await page.getByRole('button', { name: '取消', exact: true }).click()
    await expect(page.getByRole('heading', { name: '答辩安排', exact: true })).toBeVisible()
    const row = page.locator('tbody tr').filter({ hasText: groupName }).first()
    await expect(row).toBeVisible()
    await row.getByRole('button', { name: '发布', exact: true }).click()
    const [published] = await Promise.all([
      page.waitForResponse((r) => r.request().method() === 'POST' && new URL(r.url()).pathname.includes('/graduation/defense-groups/') && new URL(r.url()).pathname.endsWith('/publish')),
      page.getByRole('button', { name: '确认发布', exact: true }).click(),
    ])
    expect(published.ok(), `publish defense group HTTP ${published.status()}`).toBeTruthy()
    const publishedBody = await published.json()
    expect(publishedBody.code, JSON.stringify(publishedBody)).toBe(0)
    await expect(row).toContainText(/已发布|发布/)
  })

  test('两位专家实名评分 → 秘书确认 → 发起二辩 → 再评分再确认', async ({ page }) => {
    await enterOwnScore(page, fixture, accounts.expertA, people.expertA, 91, 1, 62)
    await enterOwnScore(page, fixture, accounts.expertB, people.expertB, 89, 1, 63)
    await confirmRound(page, fixture, 1, 64)

    await openScoring(page, accounts.secretary, fixture, 65)
    await page.getByRole('button', { name: '发起二次答辩', exact: true }).click()
    await expect(page.getByRole('heading', { name: '创建二次答辩', exact: true })).toBeVisible()
    await page.locator('form.ie-form textarea').fill('E2E-AUDIT-20260823 首轮答辩需进一步验证异常路径与现场问答完整性。')
    const [second] = await Promise.all([
      page.waitForResponse((r) => r.request().method() === 'POST' && new URL(r.url()).pathname.endsWith(`/graduation/gd-defense-scores/${fixture.gdStudentId}/second-defense`)),
      page.getByRole('button', { name: '提交', exact: true }).click(),
    ])
    expect(second.ok(), `second defense HTTP ${second.status()}`).toBeTruthy()
    const secondBody = await second.json()
    expect(secondBody.code, JSON.stringify(secondBody)).toBe(0)
    expect(Number(secondBody.data?.roundNo)).toBe(2)

    await enterOwnScore(page, fixture, accounts.expertA, people.expertA, 94, 2, 66)
    await enterOwnScore(page, fixture, accounts.expertB, people.expertB, 92, 2, 67)
    await confirmRound(page, fixture, 2, 68)

    await page.reload()
    await dismissGuide(page)
    await expect(page.locator('.gp-timeline-item').filter({ hasText: '第2轮' })).toHaveCount(2)
    await expect(page.locator('.gp-timeline-item').filter({ hasText: '第2轮' }).first()).toContainText(/已确认|确认/)
  })
})
