import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { graduationRoles } from '../lib/graduation-role-accounts.mjs'
import { loginApi, prepareGraduationFixture } from '../lib/api-fixture.mjs'
import { ensureDefenseScoringContext } from '../lib/graduation-scenario-fixture.mjs'
import { StaffLoginPage } from '../pages/login.page.mjs'

async function dismissGuide(page) {
  for (const mask of [page.locator('.app-step-guide__mask'), page.locator('.tour-mask')]) {
    if (await mask.isVisible().catch(() => false)) {
      const skip = page.getByRole('button', { name: /跳过引导|跳过/ }).first()
      if (await skip.isVisible().catch(() => false)) await skip.click()
      await mask.waitFor({ state: 'hidden', timeout: 3000 }).catch(() => {})
    }
  }
}

async function expectBusinessSuccess(response, action) {
  const body = await response.json()
  expect(response.ok(), `${action} HTTP ${response.status()}: ${JSON.stringify(body).slice(0, 1000)}`).toBeTruthy()
  expect(body.code, `${action} business error: ${JSON.stringify(body).slice(0, 1000)}`).toBe(0)
  return body.data
}

test.describe.serial('V6 · defense secretary confirmation writes the complete round', () => {
  let fixture
  let adminApi

  test.beforeAll(async () => {
    fixture = await prepareGraduationFixture({
      studentAccount: graduationRoles.defenseStudent,
      fixtureKey: 'defense-secretary-confirmation'
    })
    adminApi = await loginApi(config.sandboxAdmin)
  })

  test('real secretary role confirms two genuine judge scores and reads both records back', async ({ page }, testInfo) => {
    test.setTimeout(8 * 60_000)
    const scoringFixture = await ensureDefenseScoringContext(page, adminApi, fixture)
    const scoreParams = {
      batchId: scoringFixture.batchId,
      gdStudentId: scoringFixture.gdStudentId,
      page: 1,
      pageSize: 200
    }
    const readScores = async () => {
      const ledger = await adminApi.get('/graduation/gd-defense-scores', scoreParams)
      expect(Array.isArray(ledger?.items), 'secretary verification requires a real paginated score ledger').toBe(true)
      expect(ledger.items.length, 'secretary verification must not compare a truncated score ledger').toBe(Number(ledger.total))
      return ledger.items
        .filter(row => String(row.gdStudentId) === String(scoringFixture.gdStudentId))
        .sort((a, b) => String(a.id).localeCompare(String(b.id)))
    }

    const chairApi = await loginApi(graduationRoles.defenseChair)
    const expertApi = await loginApi(graduationRoles.defenseExpert)
    const chairReceipt = await chairApi.post('/graduation/gd-defense-scores/entry', {
      gdStudentId: String(scoringFixture.gdStudentId),
      judgeName: 'E2E答辩专家B',
      score: 77,
      comment: `秘书确认前的主席评分。${scoringFixture.runId}`,
      absent: false,
      absentReason: ''
    }, { batchId: scoringFixture.batchId })
    const expertReceipt = await expertApi.post('/graduation/gd-defense-scores/entry', {
      gdStudentId: String(scoringFixture.gdStudentId),
      judgeName: scoringFixture.defenseExpertName,
      score: 88,
      comment: `秘书确认前的成员评分。${scoringFixture.runId}`,
      absent: false,
      absentReason: ''
    }, { batchId: scoringFixture.batchId })

    expect(String(chairReceipt?.judgeMentorId || '')).toMatch(/^\d+$/)
    expect(String(expertReceipt?.judgeMentorId || '')).toBe(String(scoringFixture.defenseExpertMentorId))
    expect(String(chairReceipt.judgeMentorId)).not.toBe(String(expertReceipt.judgeMentorId))
    expect(Number(chairReceipt.roundNo)).toBe(Number(expertReceipt.roundNo))
    expect(chairReceipt.status).toBe('SCORED')
    expect(expertReceipt.status).toBe('SCORED')
    expect(chairReceipt.score).toBe(77)
    expect(expertReceipt.score).toBe(88)

    const roundNo = Number(expertReceipt.roundNo)
    const baseline = (await readScores()).filter(row => Number(row.roundNo) === roundNo)
    expect(baseline).toHaveLength(2)
    expect(baseline.map(row => row.score).sort((a, b) => a - b)).toEqual([77, 88])
    expect(baseline.every(row => row.status === 'SCORED')).toBe(true)
    expect(new Set(baseline.map(row => String(row.judgeMentorId))).size).toBe(2)

    const login = new StaffLoginPage(page, config.staffBaseUrl)
    await login.login(graduationRoles.defenseSecretary)
    await login.switchRole(/答辩秘书|GD_DEFENSE_SECRETARY/)
    await expect(page.locator('.uchip__role')).toContainText(/答辩秘书|GD_DEFENSE_SECRETARY/)

    const url = new URL('/admin/graduation/defense-confirmation', config.staffBaseUrl)
    url.searchParams.set('batchId', String(scoringFixture.batchId))
    url.searchParams.set('studentId', String(scoringFixture.gdStudentId))
    url.searchParams.set('panel', 'defense')
    url.searchParams.set('mode', 'single')
    url.searchParams.set('queue', 'confirm')
    await page.goto(url.toString())
    await dismissGuide(page)

    await expect(page.locator('.gp-context')).toContainText(scoringFixture.studentNo)
    await expect(page.getByText('完整评分轮次确认', { exact: true })).toBeVisible()
    await expect(page.getByText('评委只能提交本人评分；秘书只能确认服务端判定为完整的评分轮次，不能代替评委补分。', { exact: true })).toBeVisible()
    const rows = page.locator('.gp-timeline-item')
    await expect(rows.filter({ hasText: 'E2E答辩专家A' })).toContainText(/88.*已评分/)
    await expect(rows.filter({ hasText: 'E2E答辩专家B' })).toContainText(/77.*已评分/)

    await page.getByRole('button', { name: '确认本轮成绩', exact: true }).click()
    await expect(page.getByText('确认本轮答辩成绩', { exact: true })).toBeVisible()
    const responsePromise = page.waitForResponse(candidate => {
      const target = new URL(candidate.url())
      return candidate.request().method() === 'POST'
        && target.pathname.endsWith(`/graduation/gd-defense-scores/${scoringFixture.gdStudentId}/confirm`)
        && target.searchParams.get('batchId') === String(scoringFixture.batchId)
    })
    await page.getByRole('button', { name: '确认本轮', exact: true }).click()
    const response = await responsePromise
    const receipt = await expectBusinessSuccess(response, '答辩秘书 PC 确认完整评分轮次')
    expect(String(receipt.gdStudentId)).toBe(String(scoringFixture.gdStudentId))
    expect(Number(receipt.roundNo)).toBe(roundNo)
    expect(receipt.judgeCount).toBe(2)
    expect(receipt.average).toBe(82.5)

    let confirmed
    await expect.poll(async () => {
      confirmed = (await readScores()).filter(row => Number(row.roundNo) === roundNo)
      return confirmed.length === 2 && confirmed.every(row => row.status === 'CONFIRMED' && row.confirmedAt)
    }, { message: 'secretary confirmation must persist on both judge rows', timeout: 30_000 }).toBe(true)

    const byJudge = new Map(confirmed.map(row => [String(row.judgeMentorId), row]))
    const chairPersisted = byJudge.get(String(chairReceipt.judgeMentorId))
    const expertPersisted = byJudge.get(String(expertReceipt.judgeMentorId))
    expect(chairPersisted?.score).toBe(77)
    expect(expertPersisted?.score).toBe(88)
    expect(chairPersisted?.judgeName).toBe(chairReceipt.judgeName)
    expect(expertPersisted?.judgeName).toBe(expertReceipt.judgeName)
    expect(String(chairPersisted?.defenseGroupId)).toBe(String(scoringFixture.defenseGroupId))
    expect(String(expertPersisted?.defenseGroupId)).toBe(String(scoringFixture.defenseGroupId))
    await expect(page.getByText('本轮成绩已确认', { exact: true })).toBeVisible()

    await page.reload()
    await dismissGuide(page)
    await expect(page.locator('.gp-context')).toContainText(scoringFixture.studentNo)
    await expect(page.locator('.gp-timeline-item').filter({ hasText: 'E2E答辩专家A' })).toContainText(/88.*已确认/)
    await expect(page.locator('.gp-timeline-item').filter({ hasText: 'E2E答辩专家B' })).toContainText(/77.*已确认/)

    await testInfo.attach('defense-secretary-confirmation-receipt', {
      body: Buffer.from(JSON.stringify({
        head: process.env.E2E_EXPECTED_SHA || process.env.GITHUB_SHA || 'local',
        batchId: String(scoringFixture.batchId),
        gdStudentId: String(scoringFixture.gdStudentId),
        defenseGroupId: String(scoringFixture.defenseGroupId),
        role: 'GD_DEFENSE_SECRETARY',
        roundNo,
        confirmation: receipt,
        scoresBefore: baseline,
        scoresAfter: confirmed,
        coverage: 'secretary confirmation only; grade calculation/review/publication, archive execution and native WeChat remain separate gates'
      }, null, 2)),
      contentType: 'application/json'
    })
  })
})
