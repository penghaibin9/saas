import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { graduationRoles } from '../lib/graduation-role-accounts.mjs'
import { items, loginApi, prepareGraduationFixture } from '../lib/api-fixture.mjs'
import { ensureDefenseScoringContext, ensureFinalApproved } from '../lib/graduation-scenario-fixture.mjs'
import { StaffLoginPage, StudentLoginPage } from '../pages/login.page.mjs'

const gradeStudent = {
  tenant: process.env.E2E_GRADUATION_GRADE_STUDENT_TENANT || 'sandbox-school',
  username: process.env.E2E_GRADUATION_GRADE_STUDENT_USERNAME || 'E2E20260003',
  password: process.env.E2E_GRADUATION_GRADE_STUDENT_PASSWORD || 'E2eTest@2026'
}

function dateAfterDays(days) {
  return new Date(Date.now() + Number(days || 0) * 86400000).toISOString().slice(0, 10)
}

function route(base, path, params = {}) {
  const url = new URL(path, base)
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') url.searchParams.set(key, String(value))
  }
  return url.toString()
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

async function expectBusinessSuccess(response, action) {
  const body = await response.json()
  expect(response.ok(), `${action} HTTP ${response.status()}: ${JSON.stringify(body).slice(0, 1200)}`).toBeTruthy()
  expect(body.code, `${action} business error: ${JSON.stringify(body).slice(0, 1200)}`).toBe(0)
  return body.data
}

async function ensureReviewerMentor(adminApi) {
  const read = async () => items(await adminApi.get('/graduation/gd-mentors', {
    keyword: graduationRoles.reviewer.username, page: 1, pageSize: 200
  })).find(row => String(row.teacherNo || '') === String(graduationRoles.reviewer.username))
  let mentor = await read()
  if (!mentor) mentor = await adminApi.post('/graduation/gd-mentors', {
    teacherNo: graduationRoles.reviewer.username,
    teacherName: 'E2E评阅教师',
    mentorType: 'INTERNAL',
    title: '副教授',
    researchDirection: '软件工程成果评阅',
    maxCapacity: 30,
    submitReview: true,
    remark: 'Playwright grade-publication formal reviewer'
  })
  const status = String(mentor.qualificationStatus || mentor.reviewStatus || '').toUpperCase()
  if (!['QUALIFIED', 'APPROVED'].includes(status)) {
    try {
      await adminApi.post(`/graduation/gd-mentors/${mentor.id}/review`, {
        action: 'APPROVE', comment: 'Playwright grade-publication reviewer approved'
      })
    } catch (error) {
      if (!/已审核|无需审核|状态|APPROVED|QUALIFIED/i.test(String(error?.message || ''))) throw error
    }
    mentor = await read() || mentor
  }
  expect(['QUALIFIED', 'APPROVED']).toContain(String(mentor.qualificationStatus || mentor.reviewStatus || '').toUpperCase())
  expect(String(mentor.id || '')).toMatch(/^\d+$/)
  return mentor
}

async function ensureFormalReview(adminApi, fixture, final) {
  const reviewerMentor = await ensureReviewerMentor(adminApi)
  let review = items(await adminApi.get('/graduation/gd-reviews', {
    batchId: fixture.batchId,
    gdStudentId: fixture.gdStudentId,
    page: 1,
    pageSize: 200
  })).find(row => String(row.reviewerMentorId || '') === String(reviewerMentor.id)
    && String(row.gdFinalId || '') === String(final.id))

  if (!review) {
    review = await adminApi.post('/graduation/gd-reviews/assign', {
      gdStudentId: String(fixture.gdStudentId),
      reviewerMentorId: Number(reviewerMentor.id),
      gdFinalId: String(final.id)
    }, { batchId: fixture.batchId })
  }

  expect(String(review.gdStudentId)).toBe(String(fixture.gdStudentId))
  expect(String(review.gdFinalId)).toBe(String(final.id))
  expect(String(review.reviewerMentorId)).toBe(String(reviewerMentor.id))
  expect(String(review.fileVersionId || '')).toMatch(/^\d+$/)
  expect(String(review.sourceSha256 || '')).toMatch(/^[a-f0-9]{64}$/i)

  if (review.status !== 'COMPLETED') {
    expect(['ASSIGNED', 'REVIEWING', 'RETURNED']).toContain(review.status)
    const reviewerApi = await loginApi(graduationRoles.reviewer)
    review = await reviewerApi.post(`/graduation/gd-reviews/${review.id}/submit`, {
      score: 84,
      opinion: `已核对冻结定稿 FileVersion，正式评阅通过。${fixture.runId}`,
      expectedVersion: Number(review.version),
      fileVersionId: Number(review.fileVersionId),
      categories: ['成果完整性'],
      issues: []
    }, { batchId: fixture.batchId })
  }

  expect(review.status).toBe('COMPLETED')
  expect(review.score).toBe(84)
  expect(String(review.gdFinalId)).toBe(String(final.id))
  expect(String(review.fileVersionId || '')).toMatch(/^\d+$/)
  expect(String(review.sourceSha256 || '')).toMatch(/^[a-f0-9]{64}$/i)

  let persisted
  await expect.poll(async () => {
    persisted = items(await adminApi.get('/graduation/gd-reviews', {
      batchId: fixture.batchId,
      gdStudentId: fixture.gdStudentId,
      page: 1,
      pageSize: 200
    })).find(row => String(row.id) === String(review.id))
    return persisted?.status === 'COMPLETED' && persisted?.score === 84
      && String(persisted?.gdFinalId || '') === String(final.id)
      && String(persisted?.fileVersionId || '') === String(review.fileVersionId)
      && String(persisted?.sourceSha256 || '').toLowerCase() === String(review.sourceSha256 || '').toLowerCase()
  }, { message: 'formal reviewer score must persist against the frozen final FileVersion', timeout: 30_000 }).toBe(true)
  return persisted
}

async function confirmDefenseAsSecretary(page, fixture, scoringFixture, adminApi) {
  const chairApi = await loginApi(graduationRoles.defenseChair)
  const expertApi = await loginApi(graduationRoles.defenseExpert)
  const chair = await chairApi.post('/graduation/gd-defense-scores/entry', {
    gdStudentId: String(scoringFixture.gdStudentId),
    judgeName: 'E2E答辩专家B',
    score: 78,
    comment: `成绩链主席评分。${fixture.runId}`,
    absent: false,
    absentReason: ''
  }, { batchId: scoringFixture.batchId })
  const expert = await expertApi.post('/graduation/gd-defense-scores/entry', {
    gdStudentId: String(scoringFixture.gdStudentId),
    judgeName: scoringFixture.defenseExpertName,
    score: 88,
    comment: `成绩链成员评分。${fixture.runId}`,
    absent: false,
    absentReason: ''
  }, { batchId: scoringFixture.batchId })

  expect(chair.status).toBe('SCORED')
  expect(expert.status).toBe('SCORED')
  expect(chair.score).toBe(78)
  expect(expert.score).toBe(88)
  expect(Number(chair.roundNo)).toBe(Number(expert.roundNo))
  expect(String(chair.judgeMentorId || '')).toMatch(/^\d+$/)
  expect(String(expert.judgeMentorId || '')).toBe(String(scoringFixture.defenseExpertMentorId))
  expect(String(chair.judgeMentorId)).not.toBe(String(expert.judgeMentorId))
  const roundNo = Number(expert.roundNo)

  const login = new StaffLoginPage(page, config.staffBaseUrl)
  await login.login(graduationRoles.defenseSecretary)
  await login.switchRole(/答辩秘书|GD_DEFENSE_SECRETARY/)
  await expect(page.locator('.uchip__role')).toContainText(/答辩秘书|GD_DEFENSE_SECRETARY/)
  await page.goto(route(config.staffBaseUrl, '/admin/graduation/defense-confirmation', {
    batchId: scoringFixture.batchId,
    studentId: scoringFixture.gdStudentId,
    panel: 'defense',
    mode: 'single',
    queue: 'confirm'
  }))
  await dismissGuide(page)
  await expect(page.locator('.gp-context')).toContainText(scoringFixture.studentNo)
  await expect(page.locator('.gp-timeline-item').filter({ hasText: 'E2E答辩专家A' })).toContainText(/88.*已评分/)
  await expect(page.locator('.gp-timeline-item').filter({ hasText: 'E2E答辩专家B' })).toContainText(/78.*已评分/)

  await page.getByRole('button', { name: '确认本轮成绩', exact: true }).click()
  await expect(page.getByText('确认本轮答辩成绩', { exact: true })).toBeVisible()
  const responsePromise = page.waitForResponse(candidate => {
    const target = new URL(candidate.url())
    return candidate.request().method() === 'POST'
      && target.pathname.endsWith(`/graduation/gd-defense-scores/${scoringFixture.gdStudentId}/confirm`)
      && target.searchParams.get('batchId') === String(scoringFixture.batchId)
  })
  await page.getByRole('button', { name: '确认本轮', exact: true }).click()
  const confirmation = await expectBusinessSuccess(await responsePromise, '答辩秘书确认成绩链的完整轮次')
  expect(String(confirmation.gdStudentId)).toBe(String(scoringFixture.gdStudentId))
  expect(Number(confirmation.roundNo)).toBe(roundNo)
  expect(confirmation.judgeCount).toBe(2)
  expect(confirmation.average).toBe(83)

  let confirmed
  await expect.poll(async () => {
    const ledger = await adminApi.get('/graduation/gd-defense-scores', {
      batchId: scoringFixture.batchId,
      gdStudentId: scoringFixture.gdStudentId,
      page: 1,
      pageSize: 200
    })
    confirmed = (ledger.items || []).filter(row => Number(row.roundNo) === roundNo)
    return confirmed.length === 2 && confirmed.every(row => row.status === 'CONFIRMED' && row.confirmedAt)
  }, { message: 'both judge rows must persist as CONFIRMED before grade calculation', timeout: 30_000 }).toBe(true)
  expect(confirmed.map(row => row.score).sort((a, b) => a - b)).toEqual([78, 88])
  expect(new Set(confirmed.map(row => String(row.judgeMentorId))).size).toBe(2)
  return { roundNo, chair, expert, confirmation, confirmed }
}

async function closePriorGradeRetryBatches(adminApi, retry) {
  const attempt = Number(retry || 0)
  if (attempt <= 0) return []

  const runBase = String(process.env.GITHUB_RUN_ID || '').replace(/\D/g, '').slice(-12)
  if (!runBase) return []
  const batchPrefix = `PW-E2E-${runBase}-grade-publication-r`
  const batches = items(await adminApi.get('/graduation/batches', {
    keyword: batchPrefix,
    page: 1,
    pageSize: 200
  }))
  const closed = []

  for (const batch of batches) {
    const batchNo = String(batch.batchNo || '')
    const match = batchNo.match(/-r(\d+)$/)
    if (!batchNo.startsWith(batchPrefix) || !match || Number(match[1]) >= attempt) continue
    if (String(batch.status || '').toUpperCase() !== 'RUNNING') continue

    const receipt = await adminApi.post(`/graduation/batches/${batch.id}/close`, {})
    expect(String(receipt?.status || '').toUpperCase()).toBe('CLOSED')
    const readback = await adminApi.get(`/graduation/batches/${batch.id}`)
    expect(String(readback?.status || '').toUpperCase()).toBe('CLOSED')
    closed.push(String(batch.id))
  }
  return closed
}

async function openGradeWindow(adminApi, fixture) {
  await adminApi.post(`/graduation/batches/${fixture.batchId}/stages`, {
    stages: [
      { code: 'TOPIC', name: '选题', startDate: dateAfterDays(-190), endDate: dateAfterDays(-161) },
      { code: 'PROPOSAL', name: '开题', startDate: dateAfterDays(-160), endDate: dateAfterDays(-131) },
      { code: 'MIDTERM', name: '中期', startDate: dateAfterDays(-130), endDate: dateAfterDays(-101) },
      { code: 'SUBMISSION', name: '成果', startDate: dateAfterDays(-100), endDate: dateAfterDays(-71) },
      { code: 'PLAGIARISM', name: '查重', startDate: dateAfterDays(-70), endDate: dateAfterDays(-51) },
      { code: 'REVIEW', name: '评阅', startDate: dateAfterDays(-50), endDate: dateAfterDays(-21) },
      { code: 'DEFENSE', name: '答辩', startDate: dateAfterDays(-20), endDate: dateAfterDays(-1) },
      { code: 'GRADE', name: '成绩', startDate: dateAfterDays(0), endDate: dateAfterDays(30) }
    ]
  })
  const batch = await adminApi.get(`/graduation/batches/${fixture.batchId}`)
  expect(String(batch?.status || '').toUpperCase()).toBe('RUNNING')
  const grade = (batch?.stages || []).find(row => String(row?.code || row?.key || '').toUpperCase() === 'GRADE')
  expect(grade, 'isolated grade-publication batch must contain a GRADE stage').toBeTruthy()

  const today = Date.parse(`${dateAfterDays(0)}T00:00:00Z`)
  const gradeStart = Date.parse(`${String(grade.startDate || '').slice(0, 10)}T00:00:00Z`)
  const gradeEnd = Date.parse(`${String(grade.endDate || '').slice(0, 10)}T00:00:00Z`)
  expect(Number.isFinite(gradeStart), 'GRADE startDate must be a parseable ISO date').toBe(true)
  expect(Number.isFinite(gradeEnd), 'GRADE endDate must be a parseable ISO date').toBe(true)
  expect(gradeStart).toBeLessThanOrEqual(today)
  expect(gradeEnd).toBeGreaterThanOrEqual(today)
  return batch
}

test.describe.serial('V6 · grade calculation, review, publication and student readback', () => {
  test('grade admin publishes authoritative scores and the exact student reads them back', async ({ page }, testInfo) => {
    test.setTimeout(12 * 60_000)
    const adminApi = await loginApi(config.sandboxAdmin)
    const closedPriorBatchIds = await closePriorGradeRetryBatches(adminApi, testInfo.retry)
    const fixture = await prepareGraduationFixture({
      studentAccount: gradeStudent,
      fixtureKey: `grade-publication-r${testInfo.retry || 0}`
    })

    const { final } = await ensureFinalApproved(page, adminApi, fixture, {
      suffix: `grade-publication-final-r${testInfo.retry || 0}`,
      documentPages: 20,
      timeoutMs: 30_000
    })
    const review = await ensureFormalReview(adminApi, fixture, final)
    expect(review.score).toBe(84)

    const scoringFixture = await ensureDefenseScoringContext(page, adminApi, fixture)
    const defense = await confirmDefenseAsSecretary(page, fixture, scoringFixture, adminApi)
    expect(defense.confirmation.average).toBe(83)
    await openGradeWindow(adminApi, fixture)

    const sourcesBefore = await adminApi.get(`/graduation/gd-grades/${fixture.gdStudentId}`, {
      batchId: fixture.batchId
    })
    expect(sourcesBefore.status).toBe('DRAFT')
    expect(sourcesBefore.sourceScores?.reviewerScore).toBe(84)
    expect(sourcesBefore.sourceScores?.reviewSourceCount).toBe(1)
    expect(sourcesBefore.sourceScores?.defenseScore).toBe(83)
    expect(sourcesBefore.sourceScores?.defenseSourceCount).toBe(2)
    expect(Number(sourcesBefore.sourceScores?.defenseRound)).toBe(defense.roundNo)
    expect(String(sourcesBefore.sourceScores?.finalId)).toBe(String(final.id))
    expect(String(sourcesBefore.sourceScores?.sourceSnapshotHash || '')).toMatch(/^[a-f0-9]{64}$/)

    const staffLogin = new StaffLoginPage(page, config.staffBaseUrl)
    await staffLogin.login(config.multiRole)
    await staffLogin.switchRole(/毕设成绩管理员|GD_GRADE_ADMIN/)
    await expect(page.locator('.uchip__role')).toContainText(/毕设成绩管理员|GD_GRADE_ADMIN/)

    const ledgerPath = `/admin/graduation/grade-ledger?batchId=${encodeURIComponent(fixture.batchId)}&studentId=${encodeURIComponent(fixture.gdStudentId)}&panel=grade&mode=single&queue=ledger`
    await page.goto(route(config.staffBaseUrl, `/admin/graduation/defense-grade/${fixture.gdStudentId}/form`, {
      formKey: 'calculate',
      batchId: fixture.batchId,
      studentId: fixture.gdStudentId,
      panel: 'grade',
      returnRoute: 'graduation-grade-ledger',
      returnTo: ledgerPath
    }))
    await dismissGuide(page)

    await expect(page.getByRole('heading', { name: '核算毕业设计成绩', exact: true })).toBeVisible()
    await expect(page.locator('.dgf-context')).toContainText(fixture.studentNo)
    await expect(page.getByLabel('评阅分（服务器汇总）', { exact: true })).toHaveValue('84')
    await expect(page.getByLabel('评阅分（服务器汇总）', { exact: true })).toHaveAttribute('readonly')
    await expect(page.getByLabel('答辩分（服务器汇总） *', { exact: true })).toHaveValue('83')
    await expect(page.getByLabel('答辩分（服务器汇总） *', { exact: true })).toHaveAttribute('readonly')
    await page.getByLabel('导师分 *', { exact: true }).fill('92')

    const calculateResponse = page.waitForResponse(candidate => {
      const target = new URL(candidate.url())
      return candidate.request().method() === 'POST'
        && target.pathname.endsWith(`/graduation/gd-grades/${fixture.gdStudentId}/calculate`)
        && target.searchParams.get('batchId') === String(fixture.batchId)
    })
    await page.getByRole('button', { name: '确认核算', exact: true }).click()
    const calculateRaw = await calculateResponse
    const calculatePayload = calculateRaw.request().postDataJSON()
    expect(calculatePayload).toMatchObject({ advisorScore: 92, reviewerScore: 84, defenseScore: 83 })
    const calculated = await expectBusinessSuccess(calculateRaw, '成绩管理员 PC 核算权威成绩')
    expect(calculated.status).toBe('CALCULATED')
    expect(calculated.advisorScore).toBe(92)
    expect(calculated.reviewerScore).toBe(84)
    expect(calculated.defenseScore).toBe(83)
    expect(calculated.totalScore).toBe(87)
    expect(calculated.gradeLevel).toBe('良好')
    expect(String(calculated.sourceSnapshotHash || '')).toBe(String(sourcesBefore.sourceScores.sourceSnapshotHash))
    await expect(page).toHaveURL(/\/admin\/graduation\/grade-ledger/)

    await dismissGuide(page)
    await expect(page.locator('.gp-context')).toContainText(fixture.studentNo)
    const gradeGrid = page.locator('.gp-grade-grid')
    await expect(gradeGrid).toContainText('92')
    await expect(gradeGrid).toContainText('84')
    await expect(gradeGrid).toContainText('83')
    await expect(gradeGrid).toContainText('87')
    await expect(page.getByRole('button', { name: '复核通过', exact: true })).toBeVisible()

    await page.getByRole('button', { name: '复核通过', exact: true }).click()
    await expect(page.getByText('成绩复核通过', { exact: true })).toBeVisible()
    const reviewResponse = page.waitForResponse(candidate => {
      const target = new URL(candidate.url())
      return candidate.request().method() === 'POST'
        && target.pathname.endsWith(`/graduation/gd-grades/${fixture.gdStudentId}/review`)
        && target.searchParams.get('batchId') === String(fixture.batchId)
    })
    await page.getByRole('button', { name: '复核通过', exact: true }).last().click()
    const reviewed = await expectBusinessSuccess(await reviewResponse, '成绩管理员 PC 复核通过')
    expect(reviewed.status).toBe('REVIEWED')
    expect(reviewed.totalScore).toBe(87)
    expect(String(reviewed.sourceSnapshotHash || '')).toBe(String(calculated.sourceSnapshotHash))
    await expect(page.getByText('成绩复核已通过', { exact: true })).toBeVisible()
    await expect(page.getByRole('button', { name: '发布成绩', exact: true })).toBeVisible()

    await page.getByRole('button', { name: '发布成绩', exact: true }).click()
    await expect(page.getByText('发布成绩', { exact: true }).last()).toBeVisible()
    const publishResponse = page.waitForResponse(candidate => {
      const target = new URL(candidate.url())
      return candidate.request().method() === 'POST'
        && target.pathname.endsWith(`/graduation/gd-grades/${fixture.gdStudentId}/publish`)
        && target.searchParams.get('batchId') === String(fixture.batchId)
    })
    await page.getByRole('button', { name: '确认发布', exact: true }).click()
    const published = await expectBusinessSuccess(await publishResponse, '成绩管理员 PC 发布毕业设计成绩')
    expect(published.status).toBe('PUBLISHED')
    expect(published.totalScore).toBe(87)
    expect(published.gradeLevel).toBe('良好')
    expect(published.publishedAt).toBeTruthy()
    expect(String(published.sourceSnapshotHash || '')).toBe(String(calculated.sourceSnapshotHash))
    await expect(page.getByText('成绩已发布', { exact: true })).toBeVisible()

    let serverGrade
    await expect.poll(async () => {
      serverGrade = await adminApi.get(`/graduation/gd-grades/${fixture.gdStudentId}`, {
        batchId: fixture.batchId
      })
      return serverGrade?.status === 'PUBLISHED' && serverGrade?.totalScore === 87 && Boolean(serverGrade?.publishedAt)
    }, { message: 'published grade must read back from the school-side authority', timeout: 30_000 }).toBe(true)
    expect(serverGrade.advisorScore).toBe(92)
    expect(serverGrade.reviewerScore).toBe(84)
    expect(serverGrade.defenseScore).toBe(83)
    expect(serverGrade.gradeLevel).toBe('良好')
    expect(String(serverGrade.sourceSnapshotHash || '')).toBe(String(calculated.sourceSnapshotHash))

    await page.reload()
    await dismissGuide(page)
    await expect(page.locator('.gp-context')).toContainText(fixture.studentNo)
    await expect(page.locator('.gp-grade-grid')).toContainText('87')
    await expect(page.getByRole('button', { name: '撤回', exact: true })).toBeVisible()

    const studentApi = await loginApi(gradeStudent)
    const studentGrade = await studentApi.get('/portal/graduation/grade')
    expect(studentGrade.published).toBe(true)
    expect(studentGrade.status).toBe('PUBLISHED')
    expect(studentGrade.advisorScore).toBe(92)
    expect(studentGrade.reviewerScore).toBe(84)
    expect(studentGrade.defenseScore).toBe(83)
    expect(studentGrade.totalScore).toBe(87)
    expect(studentGrade.gradeLevel).toBe('良好')
    expect(studentGrade.canAppeal).toBe(true)

    const studentLogin = new StudentLoginPage(page, config.studentBaseUrl)
    await studentLogin.login(gradeStudent)
    const portalGradeResponse = page.waitForResponse(candidate =>
      candidate.request().method() === 'GET'
        && new URL(candidate.url()).pathname.endsWith('/api/v1/portal/graduation/grade'))
    await page.goto(`${config.studentBaseUrl}/graduation`)
    const portalGrade = await expectBusinessSuccess(await portalGradeResponse, '学生 PC 读取本人已发布毕业设计成绩')
    expect(portalGrade.published).toBe(true)
    expect(portalGrade.totalScore).toBe(87)
    expect(portalGrade.gradeLevel).toBe('良好')
    const gradeBox = page.locator('.gd-grade-box')
    await expect(gradeBox).toBeVisible()
    await expect(gradeBox).toContainText('综合成绩 87 分（良好）')
    await expect(gradeBox).toContainText('指导 92 · 评阅 84 · 答辩 83')

    const reloadGradeResponse = page.waitForResponse(candidate =>
      candidate.request().method() === 'GET'
        && new URL(candidate.url()).pathname.endsWith('/api/v1/portal/graduation/grade'))
    await page.reload()
    const portalReload = await expectBusinessSuccess(await reloadGradeResponse, '学生 PC 刷新后重新读取已发布成绩')
    expect(portalReload.published).toBe(true)
    expect(portalReload.totalScore).toBe(87)
    await expect(page.locator('.gd-grade-box')).toContainText('综合成绩 87 分（良好）')

    await testInfo.attach('graduation-grade-publication-receipt', {
      body: Buffer.from(JSON.stringify({
        head: process.env.E2E_EXPECTED_SHA || process.env.GITHUB_SHA || 'local',
        batchId: String(fixture.batchId),
        gdStudentId: String(fixture.gdStudentId),
        studentNo: fixture.studentNo,
        finalId: String(final.id),
        formalReview: {
          id: String(review.id), score: review.score,
          fileVersionId: String(review.fileVersionId), sourceSha256: review.sourceSha256
        },
        defense: {
          roundNo: defense.roundNo,
          confirmation: defense.confirmation,
          scores: defense.confirmed
        },
        grade: {
          sourceBefore: sourcesBefore.sourceScores,
          calculated,
          reviewed,
          published,
          schoolReadback: serverGrade,
          studentApiReadback: studentGrade,
          studentPortalReadback: portalReload
        },
        retryCleanup: {
          attempt: Number(testInfo.retry || 0),
          closedPriorBatchIds
        },
        coverage: 'formal review + real secretary confirmation + GD_GRADE_ADMIN browser calculate/review/publish + exact student PC readback; archive execution and native WeChat remain separate gates'
      }, null, 2)),
      contentType: 'application/json'
    })
  })
})