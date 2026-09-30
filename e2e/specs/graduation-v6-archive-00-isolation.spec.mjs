import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { Api, items, loginApi, prepareGraduationFixture } from '../lib/api-fixture.mjs'
import { ensureProposalApproved } from '../lib/graduation-scenario-fixture.mjs'

const archiveStudent = {
  tenant: process.env.E2E_GRADUATION_ARCHIVE_STUDENT_TENANT || 'sandbox-school',
  username: process.env.E2E_GRADUATION_ARCHIVE_STUDENT_USERNAME || 'E2E20260003',
  password: process.env.E2E_GRADUATION_ARCHIVE_STUDENT_PASSWORD || 'E2eTest@2026'
}

function dateAfterDays(days) {
  return new Date(Date.now() + Number(days || 0) * 86400000).toISOString().slice(0, 10)
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

test.describe.serial('V6 · archive filing isolation preflight', () => {
  test('closes only RUNNING Playwright batches created by this exact GitHub run', async ({}, testInfo) => {
    const runBase = String(process.env.GITHUB_RUN_ID || '').replace(/\D/g, '').slice(-12)
    expect(runBase, 'archive isolation requires the exact GitHub Actions run id').toMatch(/^\d+$/)

    const batchPrefix = `PW-E2E-${runBase}`
    const adminApi = await loginApi(config.sandboxAdmin)
    const batches = items(await adminApi.get('/graduation/batches', {
      keyword: batchPrefix,
      page: 1,
      pageSize: 200
    }))
    const currentRunBatches = batches.filter(batch => String(batch.batchNo || '').startsWith(batchPrefix))
    const running = currentRunBatches.filter(batch => String(batch.status || '').toUpperCase() === 'RUNNING')
    const closed = []

    for (const batch of running) {
      const batchNo = String(batch.batchNo || '')
      expect(batchNo.startsWith(batchPrefix), 'preflight must never close a batch outside this exact CI run').toBe(true)

      const receipt = await adminApi.post(`/graduation/batches/${batch.id}/close`, {})
      expect(String(receipt?.status || '').toUpperCase()).toBe('CLOSED')
      const readback = await adminApi.get(`/graduation/batches/${batch.id}`)
      expect(String(readback?.status || '').toUpperCase()).toBe('CLOSED')
      closed.push({ id: String(batch.id), batchNo })
    }

    const after = items(await adminApi.get('/graduation/batches', {
      keyword: batchPrefix,
      page: 1,
      pageSize: 200
    }))
    const remainingRunning = after.filter(batch =>
      String(batch.batchNo || '').startsWith(batchPrefix)
      && String(batch.status || '').toUpperCase() === 'RUNNING'
    )
    expect(remainingRunning, 'no earlier batch from this exact run may remain RUNNING before the archive chain').toEqual([])

    await testInfo.attach('graduation-archive-isolation-receipt', {
      body: Buffer.from(JSON.stringify({
        head: process.env.E2E_EXPECTED_SHA || process.env.GITHUB_SHA || 'local',
        runId: process.env.GITHUB_RUN_ID || '',
        batchPrefix,
        closed,
        remainingRunning: []
      }, null, 2)),
      contentType: 'application/json'
    })
  })

  test('builds three real guidance records and closes only scan-proven inactive archive risks', async ({ page }, testInfo) => {
    test.setTimeout(6 * 60_000)
    const adminApi = await loginApi(config.sandboxAdmin)
    const fixture = await prepareGraduationFixture({
      studentAccount: archiveStudent,
      fixtureKey: 'archive-filing-r0'
    })

    await ensureProposalApproved(page, fixture, { suffix: 'archive-guidance-readiness' })

    let mentorApi = await loginApi(config.mentor)
    mentorApi = await switchApiRole(mentorApi, 'GD_MENTOR')
    const markerPrefix = `归档闭环指导记录 ${fixture.runId}`
    const readGuidance = async () => items(await adminApi.get('/graduation/gd-guidances', {
      batchId: fixture.batchId,
      gdStudentId: fixture.gdStudentId,
      page: 1,
      pageSize: 200
    }))

    let guidanceRows = await readGuidance()
    for (let index = 1; index <= 3; index += 1) {
      const content = `${markerPrefix} #${index}`
      if (guidanceRows.some(row => String(row.content || '') === content)) continue
      const created = await mentorApi.post(`/graduation/gd-guidances/${fixture.gdStudentId}`, {
        guidanceDate: dateAfterDays(-28 + index * 7),
        method: index === 2 ? 'ONLINE' : 'OFFLINE',
        content,
        issues: index === 1
          ? '明确论文结构、技术路线与阶段计划'
          : index === 2
            ? '复核阶段成果与中期准备，确认后续改进项'
            : '核对论文完善、答辩准备与归档材料要求'
      }, { batchId: fixture.batchId })
      expect(String(created.gdStudentId)).toBe(String(fixture.gdStudentId))
      expect(created.content).toBe(content)
      guidanceRows = await readGuidance()
    }

    const exactGuidance = guidanceRows.filter(row => String(row.content || '').startsWith(markerPrefix))
    expect(exactGuidance, 'GD-R06 readiness must be satisfied by three persisted business guidance records').toHaveLength(3)

    const scan = await adminApi.post('/graduation/gd-risks/scan', {}, { batchId: fixture.batchId })
    expect(String(scan.batchId)).toBe(String(fixture.batchId))
    expect(scan.scannedStudents).toBeGreaterThanOrEqual(1)

    const readRisks = async () => items(await adminApi.get('/graduation/gd-risks', {
      batchId: fixture.batchId,
      gdStudentId: fixture.gdStudentId,
      page: 1,
      pageSize: 200
    }))
    const risksAfterScan = await readRisks()
    const openRisks = risksAfterScan.filter(row =>
      ['OPEN', 'PROCESSING'].includes(String(row.status || '').toUpperCase())
    )
    const activeBlockers = openRisks.filter(row => row.conditionActive !== false)
    expect(
      activeBlockers,
      `archive preflight must never close an active risk: ${JSON.stringify(activeBlockers).slice(0, 2500)}`
    ).toEqual([])

    const inactiveRisks = openRisks.filter(row => row.conditionActive === false)
    const closedRisks = []
    for (const risk of inactiveRisks) {
      const reason = `归档隔离：扫描确认 ${risk.riskCode || '风险'} 触发条件已消失，关闭失效风险`
      const closed = await adminApi.post(`/graduation/gd-risks/${risk.id}/close`, { reason })
      expect(String(closed.status || '').toUpperCase()).toBe('CLOSED')
      expect(closed.conditionActive).toBe(false)
      closedRisks.push({
        id: String(risk.id),
        riskCode: risk.riskCode,
        previousStatus: risk.status,
        conditionSummary: risk.conditionSummary,
        closedStatus: closed.status
      })
    }

    await adminApi.post('/graduation/gd-risks/scan', {}, { batchId: fixture.batchId })
    const finalRisks = await readRisks()
    const remainingOpenRisks = finalRisks.filter(row =>
      ['OPEN', 'PROCESSING'].includes(String(row.status || '').toUpperCase())
    )
    expect(
      remainingOpenRisks,
      `formal archive requires zero unclosed risks, got ${JSON.stringify(remainingOpenRisks).slice(0, 2500)}`
    ).toEqual([])

    await testInfo.attach('graduation-archive-guidance-risk-readiness', {
      body: Buffer.from(JSON.stringify({
        head: process.env.E2E_EXPECTED_SHA || process.env.GITHUB_SHA || 'local',
        batchId: String(fixture.batchId),
        gdStudentId: String(fixture.gdStudentId),
        studentNo: fixture.studentNo,
        guidanceIds: exactGuidance.map(row => String(row.id)),
        guidanceCount: exactGuidance.length,
        scan,
        openRisksAfterScan: openRisks.map(row => ({
          id: String(row.id),
          riskCode: row.riskCode,
          status: row.status,
          conditionActive: row.conditionActive,
          conditionSummary: row.conditionSummary
        })),
        activeBlockers: [],
        closedRisks,
        remainingOpenRisks: []
      }, null, 2)),
      contentType: 'application/json'
    })
  })
})
