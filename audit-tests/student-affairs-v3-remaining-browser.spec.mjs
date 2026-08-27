import fs from 'node:fs'
import path from 'node:path'

import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { items, loginApi } from '../lib/api-fixture.mjs'

const DESKTOP = { width: 1440, height: 1000 }
const STUDENT_NO = 'E2E20260002'
const EVIDENCE_DIR = path.resolve(process.cwd(), '../audit-evidence')

function marker() {
  const raw = process.env.GITHUB_RUN_ID || `${Date.now()}`
  const run = String(raw).replace(/\D/g, '').slice(-10) || String(Date.now()).slice(-10)
  return `${run}-${process.pid}-${Date.now()}`
}

function writeClosure(code, evidence) {
  fs.mkdirSync(EVIDENCE_DIR, { recursive: true })
  fs.writeFileSync(
    path.join(EVIDENCE_DIR, `v3-closure-${code.toLowerCase()}.json`),
    `${JSON.stringify({
      code,
      productExactSha: process.env.PRODUCT_EXACT_SHA || '',
      browserFirst: true,
      status: 'REAL_PASS_CANDIDATE',
      evidence,
      writtenAt: new Date().toISOString()
    }, null, 2)}\n`,
    'utf8'
  )
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

async function openStaffWorkspace(page, api, route) {
  await page.addInitScript((token) => {
    window.sessionStorage.setItem('gx_pc_token_v1', token)
  }, api.token)
  await page.goto(`${config.staffBaseUrl}${route}`)
  await dismissGuide(page)
}

async function findStudent(adminApi) {
  const rows = items(await adminApi.get('/students', {
    keyword: STUDENT_NO,
    page: 1,
    pageSize: 50
  }))
  const student = rows.find((row) => String(row.studentNo || row.loginName || '') === STUDENT_NO)
  if (!student?.id) throw new Error(`Student Affairs V3 student ${STUDENT_NO} not found`)
  return student
}

function byId(rows, idKey, id) {
  return rows.find((row) => String(row?.[idKey] || row?.id || '') === String(id))
}

test.describe.serial('Student Affairs V3 remaining Browser First closures', () => {
  let adminApi
  let student

  let talkTopic
  let talkId
  let familyReason
  let familyContactId
  let creditReason
  let creditAppealId
  let volunteerName
  let volunteerRecordId
  let clubName
  let clubId
  let partyBranch
  let partyDevId
  let evalPeriod
  let evalId
  let counselorAssignmentId
  let counselorKey

  test.beforeAll(async () => {
    adminApi = await loginApi(config.sandboxAdmin)
    student = await findStudent(adminApi)
    const id = marker()

    // SA-012: API only creates the planned prerequisite. The actual talk record is written in Chromium.
    talkTopic = `SA-012 谈心谈话 ${id}`
    await adminApi.post('/student-affairs/talks', {
      studentIds: [String(student.id)],
      talkType: 'DAILY',
      topic: talkTopic
    })
    const talkRows = items(await adminApi.get('/student-affairs/talks', {
      studentId: String(student.id),
      page: 1,
      pageSize: 100
    }))
    const talk = talkRows.find((row) => String(row.topic || '') === talkTopic)
    talkId = String(talk?.talkId || talk?.id || '')
    expect(talkId).not.toBe('')
    expect(['PLANNED', 'SCHEDULED']).toContain(String(talk?.status || '').toUpperCase())

    // SA-013: API creates a real pending family contact; browser must register the parent receipt.
    familyReason = `SA-013 家校联系 ${id}`
    const contact = await adminApi.post(`/student-affairs/students/${student.id}/family-contacts`, {
      contactType: 'PHONE',
      reason: familyReason,
      result: '已向家长说明学生近期在校情况并约定持续沟通',
      fullPhoneView: false
    })
    familyContactId = String(contact?.contactId || contact?.id || '')
    if (!familyContactId) {
      const contactRows = items(await adminApi.get('/student-affairs/family-contacts', { page: 1, pageSize: 200 }))
      const found = contactRows.find((row) => String(row.reason || '') === familyReason)
      familyContactId = String(found?.contactId || found?.id || '')
    }
    expect(familyContactId).not.toBe('')

    // SA-016: create an appeal only; approval in Chromium must write the official credit ledger.
    creditReason = `SA-016 第二课堂积分缺记 ${id}`
    const appeal = await adminApi.post('/student-affairs/second-class/appeals', {
      studentId: Number(student.id),
      appealType: 'MISSING',
      claimCreditType: 'SECOND_CLASS',
      claimValue: 1.5,
      reason: creditReason
    })
    creditAppealId = String(appeal?.appealId || appeal?.id || '')
    if (!creditAppealId) {
      const appealRows = items(await adminApi.get('/student-affairs/second-class/appeals', { page: 1, pageSize: 200 }))
      const found = appealRows.find((row) => String(row.reason || '') === creditReason)
      creditAppealId = String(found?.appealId || found?.id || '')
    }
    expect(creditAppealId).not.toBe('')

    // SA-017: create a pending volunteer record; recognition must happen in Chromium.
    volunteerName = `SA-017 社区志愿服务 ${id}`
    const volunteer = await adminApi.post('/student-affairs/volunteer/records', {
      studentId: Number(student.id),
      serviceName: volunteerName,
      hours: 3.5,
      orgName: 'E2E 社区服务中心',
      serviceDate: '2099-08-17'
    })
    volunteerRecordId = String(volunteer?.recordId || volunteer?.id || '')
    if (!volunteerRecordId) {
      const volunteerRows = items(await adminApi.get('/student-affairs/volunteer/records', { page: 1, pageSize: 200 }))
      const found = volunteerRows.find((row) => String(row.serviceName || '') === volunteerName)
      volunteerRecordId = String(found?.recordId || found?.id || '')
    }
    expect(volunteerRecordId).not.toBe('')

    // SA-018: create a pending club; approval is a real PC action.
    clubName = `SA-018 学生科技社团 ${id}`
    const club = await adminApi.post('/student-affairs/clubs', {
      clubName,
      clubType: 'ACADEMIC',
      advisorName: 'E2E 指导教师',
      presidentStudentId: Number(student.id)
    })
    clubId = String(club?.clubId || club?.id || '')
    if (!clubId) {
      const clubRows = items(await adminApi.get('/student-affairs/clubs', { page: 1, pageSize: 200 }))
      const found = clubRows.find((row) => String(row.clubName || '') === clubName)
      clubId = String(found?.clubId || found?.id || '')
    }
    expect(clubId).not.toBe('')

    // SA-019: create the development dossier; browser advances exactly one legal stage.
    partyBranch = `SA-019 E2E 学生党支部 ${id}`
    const dev = await adminApi.post('/student-affairs/party-league/dev', {
      studentId: Number(student.id),
      devType: 'PARTY',
      branchName: partyBranch
    })
    partyDevId = String(dev?.devId || dev?.id || '')
    if (!partyDevId) {
      const devRows = items(await adminApi.get('/student-affairs/party-league/dev', { page: 1, pageSize: 200 }))
      const found = devRows.find((row) => String(row.branchName || '') === partyBranch)
      partyDevId = String(found?.devId || found?.id || '')
    }
    expect(partyDevId).not.toBe('')

    // SA-020: bind the evaluation to the exact counselor proven by the formal ACTIVE responsibility relation.
    const assignments = items(await adminApi.get('/student-affairs/counselor-assignments', { page: 1, pageSize: 200 }))
    const assignment = assignments.find((row) => (
      String(row.status || '').toUpperCase() === 'ACTIVE' && String(row.loginName || '').trim()
    ))
    counselorAssignmentId = String(assignment?.assignmentId || assignment?.id || '')
    counselorKey = String(assignment?.loginName || '').trim()
    expect(counselorAssignmentId, 'SA-020 requires a real ACTIVE counselor assignment').not.toBe('')
    expect(counselorKey, 'SA-020 ACTIVE counselor assignment must expose its real loginName').not.toBe('')

    const indicatorName = `SA-020 学生工作质量 ${id}`
    const indicator = await adminApi.post('/student-affairs/counselor-eval/indicators', {
      name: indicatorName,
      category: 'STUDENT_WORK',
      weight: 100,
      maxScore: 100
    })
    const indicatorId = String(indicator?.indicatorId || indicator?.id || '')
    expect(indicatorId).not.toBe('')

    evalPeriod = `SA20-${String(id).slice(-18)}`
    const evaluation = await adminApi.post('/student-affairs/counselor-eval/evals', {
      periodCode: evalPeriod,
      counselorKey,
      counselorName: String(assignment?.counselorName || counselorKey),
      scores: { [indicatorId]: 92 },
      remark: 'SA-020 Browser First 发布前评分'
    })
    evalId = String(evaluation?.evalId || evaluation?.id || '')
    if (!evalId) {
      const evalRows = items(await adminApi.get('/student-affairs/counselor-eval/evals', {
        periodCode: evalPeriod,
        page: 1,
        pageSize: 200
      }))
      const found = evalRows.find((row) => String(row.periodCode || '') === evalPeriod)
      evalId = String(found?.evalId || found?.id || '')
    }
    expect(evalId).not.toBe('')
  })

  test('SA-012 Talk plan is completed by writing the real talk record in Staff PC', async ({ page }) => {
    await page.setViewportSize(DESKTOP)
    await openStaffWorkspace(page, adminApi, '/admin/student-affairs/talk')
    await expect(page).toHaveURL(/\/admin\/student-affairs\/talk/)
    await expect(page.getByRole('heading', { name: '谈心谈话工作台', exact: true })).toBeVisible()

    const item = page.locator('.tk-qitem').filter({ hasText: talkTopic }).first()
    await expect(item).toBeVisible()
    await item.click()

    const content = `SA-012 Browser First 谈话记录：围绕学生近期学习、生活和成长情况开展正式沟通，并确认当前无需进一步跟进。`
    const textarea = page.getByPlaceholder('记录谈话过程与内容，不少于 20 字')
    await expect(textarea).toBeVisible()
    await textarea.fill(content)
    await page.getByRole('button', { name: '提交记录（进 360）', exact: true }).click()

    await expect(page.getByText(content, { exact: true })).toBeVisible()
    const talks = items(await adminApi.get('/student-affairs/talks', {
      studentId: String(student.id),
      page: 1,
      pageSize: 100
    }))
    const current = byId(talks, 'talkId', talkId)
    expect(String(current?.status || '').toUpperCase()).toBe('COMPLETED')
    writeClosure('SA-012', {
      talkId,
      finalStatus: 'COMPLETED',
      browserActions: ['选择谈话', '填写记录', '提交记录（进 360）']
    })
  })

  test('SA-013 Family contact receives a real parent receipt in Staff PC', async ({ page }) => {
    await page.setViewportSize(DESKTOP)
    await openStaffWorkspace(page, adminApi, '/admin/student-affairs/family/receipts')
    await expect(page).toHaveURL(/\/admin\/student-affairs\/family\/receipts/)
    await expect(page.getByRole('heading', { name: '家校回执', exact: true })).toBeVisible()

    const row = page.locator('tbody tr').filter({ hasText: familyReason }).first()
    await expect(row).toBeVisible()
    await row.getByRole('button', { name: '登记回执', exact: true }).click()
    const note = `SA-013 家长已知晓并同意持续配合学校跟进 ${familyContactId}`
    await page.getByPlaceholder('记录家长的反馈与后续约定').fill(note)
    await page.getByRole('button', { name: '登记回执', exact: true }).last().click()

    const contacts = items(await adminApi.get('/student-affairs/family-contacts', { page: 1, pageSize: 200 }))
    const current = byId(contacts, 'contactId', familyContactId)
    expect(String(current?.receiptStatus || '').toUpperCase()).toBe('RECEIVED')
    expect(String(current?.receiptNote || '')).toContain('SA-013')
    writeClosure('SA-013', {
      contactId: familyContactId,
      finalStatus: 'RECEIVED',
      browserActions: ['登记回执']
    })
  })

  test('SA-016 Credit appeal is approved in PC and enters the official ledger state', async ({ page }) => {
    await page.setViewportSize(DESKTOP)
    await openStaffWorkspace(page, adminApi, '/admin/student-affairs/activity/credit-appeals')
    await expect(page).toHaveURL(/\/admin\/student-affairs\/activity\/credit-appeals/)
    await expect(page.getByRole('heading', { name: '第二课堂积分申诉', exact: true })).toBeVisible()

    const row = page.locator('tbody tr').filter({ hasText: creditReason }).first()
    await expect(row).toBeVisible()
    await row.getByRole('button', { name: '核对后通过', exact: true }).click()
    await page.getByRole('button', { name: '确认通过', exact: true }).last().click()

    const appeals = items(await adminApi.get('/student-affairs/second-class/appeals', { page: 1, pageSize: 200 }))
    const current = byId(appeals, 'appealId', creditAppealId)
    expect(String(current?.status || '').toUpperCase()).toBe('APPROVED')
    const report = await adminApi.get(`/student-affairs/second-class/students/${student.id}/report`)
    expect(report).toBeTruthy()
    writeClosure('SA-016', {
      appealId: creditAppealId,
      finalStatus: 'APPROVED',
      officialStudentReportRead: true,
      browserActions: ['核对后通过', '确认通过']
    })
  })

  test('SA-017 Volunteer hours are recognized by real PC action', async ({ page }) => {
    await page.setViewportSize(DESKTOP)
    await openStaffWorkspace(page, adminApi, '/admin/student-affairs/activity/volunteer')
    await expect(page).toHaveURL(/\/admin\/student-affairs\/activity\/volunteer/)
    await expect(page.getByRole('heading', { name: '志愿服务时长', exact: true })).toBeVisible()

    const row = page.locator('tbody tr').filter({ hasText: volunteerName }).first()
    await expect(row).toBeVisible()
    await row.getByRole('button', { name: '认定', exact: true }).click()

    const records = items(await adminApi.get('/student-affairs/volunteer/records', { page: 1, pageSize: 200 }))
    const current = byId(records, 'recordId', volunteerRecordId)
    expect(String(current?.status || '').toUpperCase()).toBe('CONFIRMED')
    writeClosure('SA-017', {
      recordId: volunteerRecordId,
      finalStatus: 'CONFIRMED',
      recognizedHours: 3.5,
      browserActions: ['认定']
    })
  })

  test('SA-018 Pending club is approved into ACTIVE by Staff PC', async ({ page }) => {
    await page.setViewportSize(DESKTOP)
    await openStaffWorkspace(page, adminApi, '/admin/student-affairs/activity/clubs')
    await expect(page).toHaveURL(/\/admin\/student-affairs\/activity\/clubs/)
    await expect(page.getByRole('heading', { name: '社团管理', exact: true })).toBeVisible()

    const club = page.locator('.cf-club').filter({ hasText: clubName }).first()
    await expect(club).toBeVisible()
    await club.getByRole('button', { name: '通过', exact: true }).click()

    const clubs = items(await adminApi.get('/student-affairs/clubs', { page: 1, pageSize: 200 }))
    const current = byId(clubs, 'clubId', clubId)
    expect(String(current?.status || '').toUpperCase()).toBe('ACTIVE')
    writeClosure('SA-018', {
      clubId,
      finalStatus: 'ACTIVE',
      browserActions: ['通过']
    })
  })

  test('SA-019 Party development advances exactly one legal stage in PC', async ({ page }) => {
    await page.setViewportSize(DESKTOP)
    await openStaffWorkspace(page, adminApi, '/admin/student-affairs/activity/party-league')
    await expect(page).toHaveURL(/\/admin\/student-affairs\/activity\/party-league/)
    await expect(page.getByRole('heading', { name: '党团建设', exact: true })).toBeVisible()

    const dev = page.locator('.lg-dev').filter({ hasText: partyBranch }).first()
    await expect(dev).toBeVisible()
    await dev.click()
    const advance = page.locator('.lg-adv')
    await expect(advance).toBeVisible()
    await advance.locator('select').selectOption('ACTIVIST')
    await advance.getByRole('button', { name: '推进', exact: true }).click()

    const rows = items(await adminApi.get('/student-affairs/party-league/dev', { page: 1, pageSize: 200 }))
    const current = byId(rows, 'devId', partyDevId)
    expect(String(current?.currentStage || '').toUpperCase()).toBe('ACTIVIST')
    const stages = items(await adminApi.get(`/student-affairs/party-league/dev/${partyDevId}/stages`))
    expect(stages.some((stage) => String(stage.toStage || '').toUpperCase() === 'ACTIVIST')).toBeTruthy()
    writeClosure('SA-019', {
      devId: partyDevId,
      finalStage: 'ACTIVIST',
      stageHistorySealed: true,
      browserActions: ['选择发展档案', '选择入党积极分子', '推进']
    })
  })

  test('SA-020 Formal counselor responsibility exists and DRAFT evaluation is published in PC', async ({ page }) => {
    await page.setViewportSize(DESKTOP)
    await openStaffWorkspace(page, adminApi, '/admin/student-affairs/counselor-eval')
    await expect(page).toHaveURL(/\/admin\/student-affairs\/counselor-eval/)
    await expect(page.getByRole('heading', { name: '辅导员考评', exact: true })).toBeVisible()

    const row = page.locator('tbody tr').filter({ hasText: evalPeriod }).first()
    await expect(row).toBeVisible()
    await row.getByRole('button', { name: '发布', exact: true }).click()

    const evaluations = items(await adminApi.get('/student-affairs/counselor-eval/evals', {
      periodCode: evalPeriod,
      page: 1,
      pageSize: 200
    }))
    const current = byId(evaluations, 'evalId', evalId)
    expect(String(current?.status || '').toUpperCase()).toBe('PUBLISHED')
    expect(String(current?.counselorKey || '')).toBe(counselorKey)

    const assignments = items(await adminApi.get('/student-affairs/counselor-assignments', { page: 1, pageSize: 200 }))
    const assignment = byId(assignments, 'assignmentId', counselorAssignmentId)
    expect(String(assignment?.status || '').toUpperCase()).toBe('ACTIVE')
    expect(String(assignment?.loginName || '')).toBe(counselorKey)
    writeClosure('SA-020', {
      assignmentId: counselorAssignmentId,
      assignmentStatus: 'ACTIVE',
      counselorKey,
      evalId,
      evalStatus: 'PUBLISHED',
      browserActions: ['发布']
    })
  })
})