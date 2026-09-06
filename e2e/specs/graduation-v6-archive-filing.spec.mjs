import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { graduationRoles } from '../lib/graduation-role-accounts.mjs'
import { Api, items, loginApi, prepareGraduationFixture } from '../lib/api-fixture.mjs'
import {
  dismissGraduationGuide,
  ensureDefenseScoringContext,
  ensureFinalApproved,
  expectGraduationBusinessSuccess
} from '../lib/graduation-scenario-fixture.mjs'
import { StaffLoginPage } from '../pages/login.page.mjs'

const archiveStudent = {
  tenant: process.env.E2E_GRADUATION_ARCHIVE_STUDENT_TENANT || 'sandbox-school',
  username: process.env.E2E_GRADUATION_ARCHIVE_STUDENT_USERNAME || 'E2E20260003',
  password: process.env.E2E_GRADUATION_ARCHIVE_STUDENT_PASSWORD || 'E2eTest@2026'
}

test.use({ trace: 'off' })

function dateAfterDays(days) {
  return new Date(Date.now() + Number(days || 0) * 86400000).toISOString().slice(0, 10)
}

function studentEntity(data) {
  return data?.student || data || null
}

async function switchApiRole(api, roleCode) {
  const expected = String(roleCode || '').toUpperCase()
  const me = await api.get('/auth/me')
  if (String(me.currentRole?.roleCode || '').toUpperCase() === expected) return api
  const context = (me.contexts || []).find(row => String(row.roleCode || '').toUpperCase() === expected)
  expect(context?.contextId, `account must expose role context ${expected}`).toBeTruthy()
  const switched = await api.post('/auth/switch-role', { contextId: context.contextId, clientType: 'PC' })
  expect(switched?.accessToken, `role switch to ${expected} must issue a new access token`).toBeTruthy()
  return new Api(switched.accessToken)
}

async function closePriorArchiveRetryBatches(adminApi, retry) {
  const attempt = Number(retry || 0)
  if (attempt <= 0) return []

  const runBase = String(process.env.GITHUB_RUN_ID || '').replace(/\D/g, '').slice(-12)
  if (!runBase) return []
  const batchPrefix = `PW-E2E-${runBase}-archive-filing-r`
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

async function ensureGuidance(adminApi, fixture) {
  const rows = items(await adminApi.get('/graduation/gd-guidances', {
    batchId: fixture.batchId,
    gdStudentId: fixture.gdStudentId,
    page: 1,
    pageSize: 200
  }))
  const marker = `归档闭环指导记录 ${fixture.runId}`
  const existing = rows.find(row => String(row.content || '') === marker)
  if (existing) return existing

  let mentorApi = await loginApi(config.mentor)
  mentorApi = await switchApiRole(mentorApi, 'GD_MENTOR')
  const created = await mentorApi.post(`/graduation/gd-guidances/${fixture.gdStudentId}`, {
    guidanceDate: dateAfterDays(-10),
    method: 'OFFLINE',
    content: marker,
    issues: '已核对论文完善、答辩准备与归档材料要求'
  })
  expect(String(created.gdStudentId)).toBe(String(fixture.gdStudentId))
  expect(created.content).toBe(marker)

  let persisted
  await expect.poll(async () => {
    persisted = items(await adminApi.get('/graduation/gd-guidances', {
      batchId: fixture.batchId,
      gdStudentId: fixture.gdStudentId,
      page: 1,
      pageSize: 200
    })).find(row => String(row.id) === String(created.id))
    return Boolean(persisted && persisted.content === marker)
  }, { message: 'guidance record must persist before archive preview', timeout: 30_000 }).toBe(true)
  return persisted
}

async function ensureReviewerMentor(adminApi) {
  const read = async () => items(await adminApi.get('/graduation/gd-mentors', {
    keyword: graduationRoles.reviewer.username,
    page: 1,
    pageSize: 200
  })).find(row => String(row.teacherNo || '') === String(graduationRoles.reviewer.username))

  let mentor = await read()
  if (!mentor) {
    mentor = await adminApi.post('/graduation/gd-mentors', {
      teacherNo: graduationRoles.reviewer.username,
      teacherName: 'E2E评阅教师',
      mentorType: 'INTERNAL',
      title: '副教授',
      researchDirection: '软件工程成果评阅',
      maxCapacity: 30,
      submitReview: true,
      remark: 'Playwright archive-filing formal reviewer'
    })
  }

  if (!['QUALIFIED', 'APPROVED'].includes(String(mentor.qualificationStatus || mentor.reviewStatus || '').toUpperCase())) {
    try {
      await adminApi.post(`/graduation/gd-mentors/${mentor.id}/review`, {
        action: 'APPROVE',
        comment: 'Playwright archive-filing reviewer approved'
      })
    } catch (error) {
      if (!/已审核|无需审核|状态|APPROVED|QUALIFIED/i.test(String(error?.message || ''))) throw error
    }
    mentor = await read() || mentor
  }

  expect(['QUALIFIED', 'APPROVED']).toContain(String(mentor.qualificationStatus || mentor.reviewStatus || '').toUpperCase())
  return mentor
}

async function ensureFormalReview(adminApi, fixture, final) {
  const reviewerMentor = await ensureReviewerMentor(adminApi)
  const read = async () => items(await adminApi.get('/graduation/gd-reviews', {
    batchId: fixture.batchId,
    gdStudentId: fixture.gdStudentId,
    page: 1,
    pageSize: 200
  })).find(row => String(row.reviewerMentorId || '') === String(reviewerMentor.id)
    && String(row.gdFinalId || '') === String(final.id))

  let review = await read()
  if (!review) {
    review = await adminApi.post('/graduation/gd-reviews/assign', {
      gdStudentId: String(fixture.gdStudentId),
      reviewerMentorId: Number(reviewerMentor.id),
      gdFinalId: String(final.id)
    }, { batchId: fixture.batchId })
  }

  expect(String(review.gdFinalId)).toBe(String(final.id))
  expect(String(review.fileVersionId || '')).toMatch(/^\d+$/)
  expect(String(review.sourceSha256 || '')).toMatch(/^[a-f0-9]{64}$/i)

  if (review.status !== 'COMPLETED') {
    let reviewerApi = await loginApi(graduationRoles.reviewer)
    reviewerApi = await switchApiRole(reviewerApi, 'GD_REVIEWER')
    review = await reviewerApi.post(`/graduation/gd-reviews/${review.id}/submit`, {
      score: 84,
      opinion: `归档闭环正式评阅已核对冻结 FileVersion。${fixture.runId}`,
      expectedVersion: Number(review.version),
      fileVersionId: Number(review.fileVersionId),
      categories: ['成果完整性'],
      issues: []
    }, { batchId: fixture.batchId })
  }

  expect(review.status).toBe('COMPLETED')
  expect(review.score).toBe(84)

  let persisted
  await expect.poll(async () => {
    persisted = await read()
    return persisted?.status === 'COMPLETED'
      && persisted?.score === 84
      && String(persisted?.gdFinalId || '') === String(final.id)
      && String(persisted?.fileVersionId || '') === String(review.fileVersionId)
  }, { message: 'formal review must persist against the exact approved final', timeout: 30_000 }).toBe(true)
  return persisted
}

async function confirmDefense(adminApi, fixture, scoringFixture) {
  const chairApi = await loginApi(graduationRoles.defenseChair)
  const expertApi = await loginApi(graduationRoles.defenseExpert)

  const chair = await chairApi.post('/graduation/gd-defense-scores/entry', {
    gdStudentId: String(scoringFixture.gdStudentId),
    judgeName: 'E2E答辩专家B',
    score: 78,
    comment: `归档闭环主席评分。${fixture.runId}`,
    absent: false,
    absentReason: ''
  }, { batchId: scoringFixture.batchId })
  const expert = await expertApi.post('/graduation/gd-defense-scores/entry', {
    gdStudentId: String(scoringFixture.gdStudentId),
    judgeName: scoringFixture.defenseExpertName,
    score: 88,
    comment: `归档闭环成员评分。${fixture.runId}`,
    absent: false,
    absentReason: ''
  }, { batchId: scoringFixture.batchId })

  expect(chair.status).toBe('SCORED')
  expect(expert.status).toBe('SCORED')
  expect(Number(chair.roundNo)).toBe(Number(expert.roundNo))
  expect(String(chair.judgeMentorId)).not.toBe(String(expert.judgeMentorId))

  let secretaryApi = await loginApi(graduationRoles.defenseSecretary)
  secretaryApi = await switchApiRole(secretaryApi, 'GD_DEFENSE_SECRETARY')
  const confirmation = await secretaryApi.post(
    `/graduation/gd-defense-scores/${scoringFixture.gdStudentId}/confirm`,
    {},
    { batchId: scoringFixture.batchId }
  )
  expect(confirmation.judgeCount).toBe(2)
  expect(confirmation.average).toBe(83)

  const roundNo = Number(confirmation.roundNo)
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
  }, { message: 'two genuine judge rows must be CONFIRMED before grade publication', timeout: 30_000 }).toBe(true)

  expect(confirmed.map(row => row.score).sort((a, b) => a - b)).toEqual([78, 88])
  expect(new Set(confirmed.map(row => String(row.judgeMentorId))).size).toBe(2)
  expect(new Set(confirmed.map(row => String(row.defenseGroupId))).size).toBe(1)
  return { roundNo, confirmation, confirmed }
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
  expect(grade).toBeTruthy()
  return batch
}

async function publishAuthoritativeGrade(adminApi, fixture, final, defense) {
  await openGradeWindow(adminApi, fixture)
  const source = await adminApi.get(`/graduation/gd-grades/${fixture.gdStudentId}`, {
    batchId: fixture.batchId
  })
  expect(source.status).toBe('DRAFT')
  expect(source.sourceScores?.reviewerScore).toBe(84)
  expect(source.sourceScores?.reviewSourceCount).toBe(1)
  expect(source.sourceScores?.defenseScore).toBe(83)
  expect(source.sourceScores?.defenseSourceCount).toBe(2)
  expect(Number(source.sourceScores?.defenseRound)).toBe(defense.roundNo)
  expect(String(source.sourceScores?.finalId)).toBe(String(final.id))
  expect(String(source.sourceScores?.sourceSnapshotHash || '')).toMatch(/^[a-f0-9]{64}$/i)

  let gradeApi = await loginApi(config.multiRole)
  gradeApi = await switchApiRole(gradeApi, 'GD_GRADE_ADMIN')
  const calculated = await gradeApi.post(`/graduation/gd-grades/${fixture.gdStudentId}/calculate`, {
    advisorScore: 92,
    reviewerScore: 84,
    defenseScore: 83
  }, { batchId: fixture.batchId })
  expect(calculated.status).toBe('CALCULATED')
  expect(calculated.totalScore).toBe(87)

  const reviewed = await gradeApi.post(`/graduation/gd-grades/${fixture.gdStudentId}/review`, {
    action: 'APPROVE'
  }, { batchId: fixture.batchId })
  expect(reviewed.status).toBe('REVIEWED')
  expect(reviewed.totalScore).toBe(87)

  const published = await gradeApi.post(`/graduation/gd-grades/${fixture.gdStudentId}/publish`, {}, {
    batchId: fixture.batchId
  })
  expect(published.status).toBe('PUBLISHED')
  expect(published.totalScore).toBe(87)
  expect(published.publishedAt).toBeTruthy()

  let persisted
  await expect.poll(async () => {
    persisted = await adminApi.get(`/graduation/gd-grades/${fixture.gdStudentId}`, {
      batchId: fixture.batchId
    })
    return persisted?.status === 'PUBLISHED' && persisted?.totalScore === 87 && Boolean(persisted?.publishedAt)
  }, { message: 'authoritative grade must persist as PUBLISHED before archive generation', timeout: 30_000 }).toBe(true)
  return { source: source.sourceScores, calculated, reviewed, published: persisted }
}

async function readArchive(adminApi, fixture) {
  return adminApi.get(`/graduation/gd-archives/${fixture.gdStudentId}`, {
    batchId: fixture.batchId
  })
}

test.describe.serial('V6 · formal archive generation, filing and ARCHIVED readback', () => {
  test('browser executes generate-submit then one-time filing and verifies immutable server facts', async ({ page }, testInfo) => {
    test.setTimeout(15 * 60_000)

    const adminApi = await loginApi(config.sandboxAdmin)
    const closedPriorBatchIds = await closePriorArchiveRetryBatches(adminApi, testInfo.retry)
    const fixture = await prepareGraduationFixture({
      studentAccount: archiveStudent,
      fixtureKey: `archive-filing-r${testInfo.retry || 0}`
    })

    const { final } = await ensureFinalApproved(page, adminApi, fixture, {
      suffix: `archive-filing-final-r${testInfo.retry || 0}`,
      documentPages: 20,
      timeoutMs: 30_000
    })
    const guidance = await ensureGuidance(adminApi, fixture)
    const review = await ensureFormalReview(adminApi, fixture, final)
    const scoringFixture = await ensureDefenseScoringContext(page, adminApi, {
      ...fixture,
      runId: `archive-${fixture.batchId}-${fixture.gdStudentId}`
    })
    const defense = await confirmDefense(adminApi, fixture, scoringFixture)
    const grade = await publishAuthoritativeGrade(adminApi, fixture, final, defense)

    const beforeArchive = await readArchive(adminApi, fixture)
    expect(beforeArchive.status).toBe('NOT_GENERATED')
    expect(beforeArchive.manifestHash || '').toBe('')

    await new StaffLoginPage(page, config.staffBaseUrl).login(config.sandboxAdmin)
    const url = new URL(`${config.staffBaseUrl}/admin/graduation/risk-archive`)
    url.searchParams.set('panel', 'archive')
    url.searchParams.set('batchId', fixture.batchId)
    await page.goto(url.toString())
    await dismissGraduationGuide(page)

    await expect(page.locator('body')).not.toContainText(/真实接口不可用|权限上下文加载失败/)
    await expect(page.getByRole('button', { name: '批量生成提交', exact: true })).toBeVisible()
    await expect(page.getByRole('button', { name: '一键核验备案', exact: true })).toBeVisible()

    const generatePreviewResponse = page.waitForResponse(candidate => {
      const target = new URL(candidate.url())
      return candidate.request().method() === 'POST'
        && target.pathname.endsWith('/graduation/gd-archives/batch-generate/preview')
        && target.searchParams.get('batchId') === String(fixture.batchId)
    })
    await page.getByRole('button', { name: '批量生成提交', exact: true }).click()
    const generatePreviewRaw = await generatePreviewResponse
    const generatePreview = await expectGraduationBusinessSuccess(generatePreviewRaw, '归档 PC 批量生成提交预览')
    expect(generatePreview.candidateCount).toBe(1)
    expect(generatePreview.executableCount).toBe(1)
    expect(generatePreview.skippedCount).toBe(0)
    expect(Boolean(generatePreview.previewToken)).toBe(true)

    const generateEvidence = page.getByTestId('archive-preview-token-evidence')
    await expect(generateEvidence).toBeVisible()
    await expect(generateEvidence).toContainText('1 / 1')
    const generateEvidenceText = await generateEvidence.textContent()
    const rawGenerateTokenLeaked = String(generateEvidenceText || '').includes(String(generatePreview.previewToken))
    expect(rawGenerateTokenLeaked, 'raw generate preview token must never be rendered into the page').toBe(false)

    const generateDialog = page.locator('.app-confirm-dialog')
    await expect(generateDialog).toContainText('批量生成提交')
    await expect(generateDialog).toContainText('候选 1 人，可执行 1，跳过 0')

    const generateExecuteResponse = page.waitForResponse(candidate => {
      const target = new URL(candidate.url())
      return candidate.request().method() === 'POST'
        && target.pathname.endsWith('/graduation/gd-archives/batch-generate')
        && target.searchParams.get('batchId') === String(fixture.batchId)
    })
    await generateDialog.getByRole('button', { name: '确认生成提交', exact: true }).click()
    const generateExecuteRaw = await generateExecuteResponse
    const generateBody = generateExecuteRaw.request().postDataJSON()
    expect(
      String(generateBody?.previewToken || '') === String(generatePreview.previewToken),
      'generate execute must consume the exact preview token already confirmed by the user'
    ).toBe(true)
    const generateResult = await expectGraduationBusinessSuccess(generateExecuteRaw, '归档 PC 批量生成提交执行')
    expect(generateResult.submitted).toBe(1)
    expect(generateResult.skipped).toBe(0)
    await expect(page.locator('.ra-receipt')).toContainText('批量生成提交已完成')

    let submitted
    await expect.poll(async () => {
      submitted = await readArchive(adminApi, fixture)
      return submitted?.status === 'SUBMITTED'
        && String(submitted?.gdStudentId || '') === String(fixture.gdStudentId)
        && Array.isArray(submitted?.missingItems)
        && submitted.missingItems.length === 0
        && Boolean(submitted?.submittedAt)
    }, { message: 'batch generate must persist the exact student as SUBMITTED with no missing materials', timeout: 30_000 }).toBe(true)

    const filePreviewResponse = page.waitForResponse(candidate => {
      const target = new URL(candidate.url())
      return candidate.request().method() === 'POST'
        && target.pathname.endsWith('/graduation/gd-archives/batch-file/preview')
        && target.searchParams.get('batchId') === String(fixture.batchId)
    })
    await page.getByRole('button', { name: '一键核验备案', exact: true }).click()
    const filePreviewRaw = await filePreviewResponse
    const filePreview = await expectGraduationBusinessSuccess(filePreviewRaw, '归档 PC 一键核验备案预览')
    expect(filePreview.candidateCount).toBe(1)
    expect(filePreview.executableCount).toBe(1)
    expect(filePreview.skippedCount).toBe(0)
    expect(Boolean(filePreview.previewToken)).toBe(true)
    expect(Boolean(filePreview.archiveBatchNo)).toBe(true)

    const fileEvidence = page.getByTestId('archive-preview-token-evidence')
    await expect(fileEvidence).toBeVisible()
    await expect(fileEvidence).toContainText(String(filePreview.archiveBatchNo))
    await expect(fileEvidence).toContainText('1 / 1')
    const fileEvidenceText = await fileEvidence.textContent()
    const rawFileTokenLeaked = String(fileEvidenceText || '').includes(String(filePreview.previewToken))
    expect(rawFileTokenLeaked, 'raw filing preview token must never be rendered into the page').toBe(false)

    const fileDialog = page.locator('.app-confirm-dialog')
    await expect(fileDialog).toContainText('一键核验备案')
    await expect(fileDialog).toContainText('候选 1 人，可执行 1，跳过 0')

    const fileExecuteResponse = page.waitForResponse(candidate => {
      const target = new URL(candidate.url())
      return candidate.request().method() === 'POST'
        && target.pathname.endsWith('/graduation/gd-archives/batch-file')
        && target.searchParams.get('batchId') === String(fixture.batchId)
    })
    await fileDialog.getByRole('button', { name: '确认核验备案', exact: true }).click()
    const fileExecuteRaw = await fileExecuteResponse
    const fileBody = fileExecuteRaw.request().postDataJSON()
    expect(
      String(fileBody?.previewToken || '') === String(filePreview.previewToken),
      'filing execute must consume the exact signed preview token'
    ).toBe(true)
    expect(
      String(fileBody?.archiveBatchNo || '') === String(filePreview.archiveBatchNo),
      'filing execute must keep the archive batch number bound by the preview'
    ).toBe(true)
    const fileResult = await expectGraduationBusinessSuccess(fileExecuteRaw, '归档 PC 一键核验备案执行')
    expect(fileResult.filed).toBe(1)
    expect(fileResult.skipped).toBe(0)
    expect(Number(fileResult.failed || 0)).toBe(0)
    await expect(page.locator('.ra-receipt')).toContainText('批量备案已核对')

    let filed
    await expect.poll(async () => {
      filed = await readArchive(adminApi, fixture)
      return filed?.status === 'FILED'
        && String(filed?.archiveBatchNo || '') === String(filePreview.archiveBatchNo)
        && /^[a-f0-9]{64}$/i.test(String(filed?.manifestHash || ''))
        && Boolean(filed?.filedAt)
        && Boolean(filed?.verifiedBy)
    }, { message: 'filed archive must persist batch, manifest hash, verifier and filed timestamp', timeout: 30_000 }).toBe(true)

    let archivedStudent
    await expect.poll(async () => {
      archivedStudent = studentEntity(await adminApi.get(`/graduation/gd-students/${fixture.gdStudentId}`))
      return archivedStudent?.stage
    }, { message: 'student lifecycle stage must remain server-readable after filing', timeout: 30_000 }).toBe('ARCHIVED')

    await page.reload()
    await dismissGraduationGuide(page)
    const archivedRow = page.locator('.rk-row').filter({ hasText: fixture.studentNo })
    await expect(archivedRow).toHaveCount(1)
    await expect(archivedRow).toContainText('已备案')
    await archivedRow.click()
    const detail = page.locator('.rk-detail')
    await expect(detail).toContainText(fixture.studentNo)
    await expect(detail).toContainText('已备案')
    await expect(detail).toContainText(String(filePreview.archiveBatchNo))
    await expect(detail).toContainText('已正式归档备案，记录只读')

    const closedBatch = await adminApi.post(`/graduation/batches/${fixture.batchId}/close`, {})
    expect(String(closedBatch?.status || '').toUpperCase()).toBe('CLOSED')
    const closedBatchReadback = await adminApi.get(`/graduation/batches/${fixture.batchId}`)
    expect(String(closedBatchReadback?.status || '').toUpperCase()).toBe('CLOSED')

    const screenshotPath = testInfo.outputPath('graduation-archive-filed-readback.png')
    await page.screenshot({ path: screenshotPath, fullPage: false, animations: 'disabled', caret: 'hide' })
    await testInfo.attach('graduation-archive-filed-readback', {
      path: screenshotPath,
      contentType: 'image/png'
    })

    await testInfo.attach('graduation-archive-filing-receipt', {
      body: Buffer.from(JSON.stringify({
        head: process.env.E2E_EXPECTED_SHA || process.env.GITHUB_SHA || 'local',
        batchId: String(fixture.batchId),
        gdStudentId: String(fixture.gdStudentId),
        studentNo: fixture.studentNo,
        prerequisiteEvidence: {
          finalId: String(final.id),
          finalStatus: final.status,
          guidanceId: String(guidance.id),
          formalReview: {
            id: String(review.id),
            status: review.status,
            score: review.score,
            fileVersionId: String(review.fileVersionId),
            sourceSha256: review.sourceSha256
          },
          defense: {
            roundNo: defense.roundNo,
            judgeCount: defense.confirmation.judgeCount,
            average: defense.confirmation.average,
            scores: defense.confirmed.map(row => ({
              judgeMentorId: String(row.judgeMentorId),
              defenseGroupId: String(row.defenseGroupId),
              score: row.score,
              status: row.status
            }))
          },
          grade: {
            status: grade.published.status,
            advisorScore: grade.published.advisorScore,
            reviewerScore: grade.published.reviewerScore,
            defenseScore: grade.published.defenseScore,
            totalScore: grade.published.totalScore,
            publishedAt: grade.published.publishedAt,
            sourceSnapshotHash: grade.published.sourceSnapshotHash
          }
        },
        generate: {
          candidateCount: generatePreview.candidateCount,
          executableCount: generatePreview.executableCount,
          skippedCount: generatePreview.skippedCount,
          exactPreviewTokenConsumed: true,
          submitted: generateResult.submitted,
          serverStatus: submitted.status,
          submittedAt: submitted.submittedAt
        },
        filing: {
          candidateCount: filePreview.candidateCount,
          executableCount: filePreview.executableCount,
          skippedCount: filePreview.skippedCount,
          exactSignedPreviewTokenConsumed: true,
          archiveBatchNo: filed.archiveBatchNo,
          filed: fileResult.filed,
          serverStatus: filed.status,
          manifestHash: filed.manifestHash,
          filedAt: filed.filedAt,
          verifiedBy: filed.verifiedBy
        },
        studentStage: archivedStudent.stage,
        retryCleanup: {
          attempt: Number(testInfo.retry || 0),
          closedPriorBatchIds,
          acceptedBatchClosedAfterEvidence: String(closedBatchReadback?.status || '').toUpperCase() === 'CLOSED'
        },
        security: {
          rawPreviewTokensPersisted: false,
          playwrightTrace: 'off'
        },
        coverage: 'real prerequisite chain via production APIs/browser + SCHOOL_ADMIN browser batch-generate confirmation + exact SUBMITTED readback + signed batch-file confirmation + FILED/manifestHash/verifiedBy/filedAt + student ARCHIVED reload'
      }, null, 2)),
      contentType: 'application/json'
    })
  })
})
