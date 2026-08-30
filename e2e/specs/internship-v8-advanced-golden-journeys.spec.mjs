import { execFileSync } from 'node:child_process'
import fs from 'node:fs/promises'
import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { StudentLoginPage, StaffLoginPage } from '../pages/login.page.mjs'
import { StudentInternshipPage } from '../pages/internship.page.mjs'

const enterpriseBaseUrl = process.env.E2E_ENTERPRISE_BASE_URL || 'http://127.0.0.1:5202/enterprise'
const ENTERPRISE_PASSWORD = 'E2eEnterprise@2026'
const pythonExecutable = process.env.E2E_PYTHON || 'python'

function apiPath(response) {
  try { return new URL(response.url()).pathname } catch { return '' }
}

function rows(data) {
  return Array.isArray(data) ? data : (data?.items || data?.list || [])
}

async function responseData(response, action) {
  const text = await response.text()
  let body
  try { body = JSON.parse(text) } catch { body = null }
  expect(response.ok(), `${action} HTTP ${response.status()}: ${text.slice(0, 1000)}`).toBeTruthy()
  expect(body?.code, `${action} business failure: ${text.slice(0, 1000)}`).toBe(0)
  return body.data
}

async function request(method, path, { token = '', params, body } = {}) {
  const url = new URL(`${config.apiBaseUrl}${path}`)
  for (const [key, value] of Object.entries(params || {})) {
    if (value !== undefined && value !== null && value !== '') url.searchParams.set(key, String(value))
  }
  const response = await fetch(url, {
    method,
    headers: {
      Accept: 'application/json',
      'X-Forwarded-For': '10.252.8.30',
      ...(body === undefined ? {} : { 'Content-Type': 'application/json' }),
      ...(token ? { Authorization: `Bearer ${token}` } : {})
    },
    body: body === undefined ? undefined : JSON.stringify(body)
  })
  const text = await response.text()
  let envelope
  try { envelope = JSON.parse(text) } catch { envelope = null }
  if (!response.ok || envelope?.code !== 0) {
    throw new Error(`${method} ${url.pathname} failed (${response.status}): ${text.slice(0, 1600)}`)
  }
  return envelope.data
}

async function roleToken(account, roleCode = '') {
  const login = await request('POST', '/auth/login', {
    body: {
      loginName: account.username,
      password: account.password,
      tenantCode: account.tenant,
      clientType: 'PC'
    }
  })
  const currentRole = String(login?.user?.currentRoleCode || login?.currentRole?.roleCode || '')
  if (!roleCode || currentRole === roleCode) return String(login.accessToken || '')
  const contexts = login?.contexts || login?.authContexts || []
  const target = contexts.find((item) => String(item.roleCode || item.code || '') === roleCode)
  expect(target, `login must expose ${roleCode} context`).toBeTruthy()
  const switched = await request('POST', '/auth/switch-role', {
    token: String(login.accessToken || ''),
    body: { contextId: String(target.contextId || target.id), clientType: 'PC' }
  })
  return String(switched?.accessToken || '')
}

async function openStudentInternship(page, journey) {
  const login = new StudentLoginPage(page, config.studentBaseUrl)
  await login.login(config.student)
  const first = page.waitForResponse((response) => apiPath(response) === '/api/v1/portal/internship/my')
  await page.goto(`${config.studentBaseUrl}/internship`)
  await first
  const workbench = new StudentInternshipPage(page, config.studentBaseUrl, journey)
  await workbench.selectExactBatchIfNeeded()
  return workbench
}

async function staffLogin(page, account = config.mentor, role = /实习指导教师|INTERN_MENTOR/) {
  const login = new StaffLoginPage(page, config.staffBaseUrl)
  await login.login(account)
  if (role) {
    await login.switchRole(role)
    await page.waitForLoadState('networkidle', { timeout: 60_000 })
  }
  return login
}

async function findByInternship(token, path, internshipId, params = {}) {
  const data = await request('GET', path, { token, params: { page: 1, pageSize: 200, ...params } })
  const row = rows(data).find((item) => String(item.internshipId || item.internship_id || '') === String(internshipId))
  expect(row, `${path} must contain internship ${internshipId}`).toBeTruthy()
  return row
}

test.describe('岗位实习 V8 advanced golden journeys：GJ05–GJ08', () => {
  test.describe.configure({ mode: 'serial', retries: 0 })
  test.setTimeout(240_000)

  let fixture
  let enterpriseFixture
  let mentorToken
  let adminToken
  let weeklyId = ''
  let weeklyNumber = 0
  let changeId = ''
  let riskId = ''
  let enterpriseEvalId = ''
  let studentEvalId = ''
  let scoreId = ''
  let appealId = ''

  test.beforeAll(async () => {
    execFileSync(pythonExecutable, ['../backend/scripts/e2e_seed_internship_v8_advanced_sandbox.py'], {
      cwd: process.cwd(), env: process.env, stdio: 'inherit'
    })
    fixture = JSON.parse(await fs.readFile('./runtime/internship-v8-advanced-fixture.json', 'utf8'))
    enterpriseFixture = JSON.parse(await fs.readFile('./runtime/internship-enterprise-position-fixture.json', 'utf8'))
    mentorToken = await roleToken(config.mentor, 'INTERN_MENTOR')
    adminToken = await roleToken(config.sandboxAdmin, 'SCHOOL_ADMIN')
    expect(mentorToken).not.toBe('')
    expect(adminToken).not.toBe('')
    const existingReports = await request('GET', '/internship/reports', {
      token: mentorToken,
      params: { batchId: fixture.gj05.batchId, page: 1, pageSize: 200 }
    })
    const usedWeeks = new Set(rows(existingReports)
      .filter((item) => String(item.internshipId || item.internId || '') === String(fixture.gj05.internshipId))
      .map((item) => Number(item.weekNo || item.weekNumber || String(item.week || '').match(/\d+/)?.[0] || 0)))
    weeklyNumber = Array.from({ length: 32 }, (_, index) => index + 20)
      .find((week) => !usedWeeks.has(week)) || 52
  })

  test('IX-GJ-05：学生确认计划、周报退回重交，导师指导巡访整改闭环', async ({ page }) => {
    const workbench = await openStudentInternship(page, fixture.gj05)

    await workbench.openGroupedTab('安排与入岗', '实习计划')
    await expect(page.getByText('GJ05 在岗过程计划', { exact: true })).toBeVisible()
    const ack = page.waitForResponse((response) =>
      apiPath(response) === '/api/v1/portal/internship/context/plan/acknowledge'
      && response.request().method() === 'POST')
    await page.getByRole('button', { name: '确认计划', exact: true }).click()
    expect((await responseData(await ack, '学生确认计划')).status).toBe('ACKNOWLEDGED')

    const reportsLoaded = page.waitForResponse((response) =>
      apiPath(response) === '/api/v1/portal/internship/context/weekly-reports'
      && response.request().method() === 'GET')
    await workbench.openGroupedTab('在岗办理', '周报/月报/总结')
    await reportsLoaded
    const form = page.locator('section.sp-card').filter({ hasText: '周报编辑' }).first()
    await form.locator('input[type="number"]').fill(String(weeklyNumber))
    const textareas = form.locator('textarea')
    await textareas.nth(0).fill('完成质量巡检、缺陷复现与安全记录，形成第一版过程事实。')
    await textareas.nth(1).fill('掌握了基于证据的缺陷闭环方法。')
    await textareas.nth(2).fill('补充量化验证并完成导师复核。')
    const submitted = page.waitForResponse((response) =>
      apiPath(response) === '/api/v1/portal/internship/context/weekly-reports'
      && response.request().method() === 'POST')
    await form.getByRole('button', { name: '提交周报', exact: true }).click()
    const firstVersion = await responseData(await submitted, '学生提交周报')
    weeklyId = String(firstVersion.id)
    expect(weeklyId).not.toBe('')

    let weekly = await request('GET', `/internship/reports/${weeklyId}`, { token: mentorToken })
    const returned = await request('POST', `/internship/reports/${weeklyId}/review`, {
      token: mentorToken,
      body: { action: 'RETURN', comment: '请补充缺陷数量与复测结果后重新提交', expectedVersion: weekly.version }
    })
    expect(returned.status).toBe('RETURNED')

    const returnedReportsLoaded = page.waitForResponse((response) =>
      apiPath(response) === '/api/v1/portal/internship/context/weekly-reports'
      && response.request().method() === 'GET')
    await page.reload()
    await returnedReportsLoaded
    await workbench.selectExactBatchIfNeeded()
    if (!(await page.getByText('周报编辑', { exact: true }).isVisible().catch(() => false))) {
      await workbench.openGroupedTab('在岗办理', '周报/月报/总结')
    }
    const resubmitForm = page.locator('section.sp-card').filter({ hasText: '周报编辑' }).first()
    await resubmitForm.locator('input[type="number"]').fill(String(weeklyNumber))
    const revised = resubmitForm.locator('textarea')
    await revised.nth(0).fill('完成质量巡检；复现 3 个缺陷，修复后复测 3 个并全部通过，安全记录已归档。')
    await revised.nth(1).fill('能用量化证据说明复测范围和结论。')
    await revised.nth(2).fill('继续执行回归测试并沉淀检查清单。')
    const resubmitted = page.waitForResponse((response) =>
      apiPath(response) === '/api/v1/portal/internship/context/weekly-reports'
      && response.request().method() === 'POST')
    await resubmitForm.getByRole('button', { name: '提交周报', exact: true }).click()
    const secondVersion = await responseData(await resubmitted, '学生按退回意见重交周报')
    expect(Number(secondVersion.reportVersion || secondVersion.version)).toBeGreaterThan(1)

    weekly = await request('GET', `/internship/reports/${weeklyId}`, { token: mentorToken })
    const approved = await request('POST', `/internship/reports/${weeklyId}/review`, {
      token: mentorToken,
      body: { action: 'APPROVE', comment: '量化证据完整，批阅通过', expectedVersion: weekly.version }
    })
    expect(approved.status).toBe('APPROVED')

    const guidance = await request('POST', '/internship/guidances', {
      token: mentorToken,
      body: { internshipId: fixture.gj05.internshipId, method: 'ONLINE', topic: '质量复盘', content: '核对缺陷复现、复测结果与安全记录，指导形成可复核清单。' }
    })
    expect(String(guidance.id)).not.toBe('')
    const visit = await request('POST', '/internship/visits', {
      token: mentorToken,
      body: {
        internshipId: fixture.gj05.internshipId,
        method: 'ONSITE',
        enterpriseFeedback: '学生过程记录完整，能按要求复测。',
        safetyIssue: '夜间复测缺少双人确认记录',
        rectifyRequire: '补齐夜间复测双人确认并留痕',
        rectifyDeadline: '2026-09-15'
      }
    })
    expect(visit.rectifyStatus).toBe('PENDING')
    const rectified = await request('POST', `/internship/visits/${visit.id}/rectify`, {
      token: mentorToken,
      body: { status: 'DONE', note: '已补齐夜间复测双人确认记录并现场复核', expectedVersion: visit.version }
    })
    expect(rectified.rectifyStatus).toBe('DONE')

    await staffLogin(page)
    await page.goto(`${config.staffBaseUrl}/admin/internship/reports/${weeklyId}?batchId=${fixture.gj05.batchId}`)
    await expect(page.getByText(/周报详情|周报批阅/).first()).toBeVisible()
    await expect(page.locator('body')).toContainText(/已通过|APPROVED/)
    await page.screenshot({ path: test.info().outputPath('ix-gj-05-approved-weekly.png'), fullPage: true })
  })

  test('IX-GJ-06：学生换岗申请经导师审核后冻结旧关系并进入重新上岗', async ({ page }) => {
    const workbench = await openStudentInternship(page, fixture.gj06)
    await workbench.openGroupedTab('变更与结果', '调岗退岗')
    const form = page.locator('section.sp-card').filter({ hasText: '发起变更' }).first()
    await form.locator('select').nth(0).selectOption('CHANGE_POSITION')
    await form.locator('select').nth(1).selectOption(fixture.gj06.targetPositionId)
    await form.locator('textarea').fill('当前岗位与专业方向不匹配，申请转入质量工程岗位')
    const submitted = page.waitForResponse((response) =>
      apiPath(response) === '/api/v1/portal/internship/context/changes'
      && response.request().method() === 'POST')
    await form.getByRole('button', { name: '提交变更', exact: true }).click()
    const change = await responseData(await submitted, '学生提交换岗申请')
    changeId = String(change.id)
    expect(change.status).toBe('PENDING')

    const detail = await request('GET', `/internship/change-requests/${changeId}`, { token: mentorToken })
    const reviewed = await request('POST', `/internship/change-requests/${changeId}/review`, {
      token: mentorToken,
      body: {
        action: 'APPROVE',
        comment: '目标岗位容量和资质核验通过，进入重新上岗流程',
        expectedVersion: detail.version,
        recordExpectedVersion: detail.recordVersionSnapshot
      }
    })
    expect(reviewed.status).toBe('APPROVED')
    expect(reviewed.nextRecordStatus || reviewed.recordStatus).toBe('READY')

    await staffLogin(page)
    await page.goto(`${config.staffBaseUrl}/admin/internship/changes?panel=approved&batchId=${fixture.gj06.batchId}&id=${changeId}`)
    await expect(page.locator('body')).toContainText(fixture.gj06.targetPositionName)
    await expect(page.locator('body')).toContainText(/已通过|APPROVED/)
    await expect(page.locator('body')).toContainText(/重新上岗|READY/)
    await page.screenshot({ path: test.info().outputPath('ix-gj-06-reonboard.png'), fullPage: true })
  })

  test('IX-GJ-07：学生高优先级求助形成风险，导师受理、跟进、关闭并保留审计', async ({ page }) => {
    const previous = await request('GET', '/internship/risks', {
      token: mentorToken,
      params: { batchId: fixture.gj07.batchId, page: 1, pageSize: 200 }
    })
    for (const item of rows(previous).filter((row) =>
      String(row.internshipId || row.internId || '') === String(fixture.gj07.internshipId)
      && ['PENDING_HANDLE', 'PROCESSING'].includes(String(row.status)))) {
      let stale = await request('GET', `/internship/risks/${item.id}`, { token: mentorToken })
      if (stale.status === 'PENDING_HANDLE') {
        stale = await request('POST', `/internship/risks/${item.id}/handle`, {
          token: mentorToken,
          body: { comment: '续跑前完成上一轮开放风险的责任接续', ownerName: fixture.mentor.name, expectedVersion: stale.version }
        })
      }
      if (stale.status === 'PROCESSING') {
        await request('POST', `/internship/risks/${item.id}/close`, {
          token: mentorToken,
          body: { result: 'RESOLVED', comment: '续跑核验上一轮措施已落实并完成关闭', expectedVersion: stale.version }
        })
      }
    }

    const workbench = await openStudentInternship(page, fixture.gj07)
    await workbench.openGroupedTab('变更与结果', '实习求助')
    const form = page.locator('section.sp-card').filter({ hasText: '向指导教师求助' }).first()
    await form.locator('select').selectOption('HIGH')
    await form.locator('input').fill('夜间作业安全保护不足')
    await form.locator('textarea').fill('企业安排夜间单人作业，现场缺少陪同与确认记录，请学校紧急核查。')
    const submitted = page.waitForResponse((response) =>
      apiPath(response) === '/api/v1/portal/internship/help'
      && response.request().method() === 'POST')
    await form.getByRole('button', { name: '提交求助', exact: true }).click()
    const help = await responseData(await submitted, '学生提交实习求助')
    riskId = String(help.riskId || help.id)
    expect(riskId).not.toBe('')

    let risk = await request('GET', `/internship/risks/${riskId}`, { token: mentorToken })
    expect(risk.status).toBe('PENDING_HANDLE')
    risk = await request('POST', `/internship/risks/${riskId}/handle`, {
      token: mentorToken,
      body: { comment: '已联系企业暂停夜间单人作业并启动现场核查', ownerName: fixture.mentor.name, expectedVersion: risk.version }
    })
    expect(risk.status).toBe('PROCESSING')
    risk = await request('POST', `/internship/risks/${riskId}/follow`, {
      token: mentorToken,
      body: { note: '企业已增加双人陪同和班前安全确认，学生反馈措施已执行', expectedVersion: risk.version }
    })
    risk = await request('POST', `/internship/risks/${riskId}/close`, {
      token: mentorToken,
      body: { result: 'RESOLVED', comment: '现场复核整改有效，学生确认风险已消除', expectedVersion: risk.version }
    })
    expect(risk.status).toBe('CLOSED')

    await staffLogin(page)
    await page.goto(`${config.staffBaseUrl}/admin/internship/risk-disposal?stage=closed&batchId=${fixture.gj07.batchId}&id=${riskId}`)
    await expect(page.locator('body')).toContainText(/已关闭|CLOSED/)
    await expect(page.locator('body')).toContainText(/现场复核整改有效|风险已消除/)
    await page.screenshot({ path: test.info().outputPath('ix-gj-07-risk-closed.png'), fullPage: true })
  })

  test('IX-GJ-08：企业评价、学生自评、导师意见、成绩发布与申诉重算闭环', async ({ page }) => {
    const priorEnterpriseEvals = await request('GET', '/internship/enterprise-evals', {
      token: adminToken,
      params: { batchId: fixture.gj08.batchId, page: 1, pageSize: 200 }
    })
    const priorEnterpriseEval = rows(priorEnterpriseEvals)
      .find((item) => String(item.internshipId || item.internId || '') === String(fixture.gj08.internshipId))
    if (priorEnterpriseEval?.reviewStatus === 'PENDING') {
      await request('POST', `/internship/enterprise-evals/${priorEnterpriseEval.id}/review-versioned`, {
        token: adminToken,
        body: {
          action: 'RETURN',
          comment: 'GJ08 回放恢复：请企业基于当前安置事实重新确认后提交',
          expectedVersion: priorEnterpriseEval.version
        }
      })
    }
    let enterpriseEval = priorEnterpriseEval
    if (enterpriseEval?.reviewStatus !== 'APPROVED') {
      await page.goto(`${enterpriseBaseUrl}/login`)
      await page.getByLabel(/学校编码/).fill(fixture.tenantCode)
      await page.getByLabel(/登录账号/).fill(fixture.enterprise.username)
      await page.getByLabel(/密码/).fill(ENTERPRISE_PASSWORD)
      await page.getByRole('button', { name: /登录/ }).click()
      await expect(page).toHaveURL(/\/enterprise\/(?:campaign-select|home)/)
      if (page.url().includes('/campaign-select')) {
        await page.getByRole('button', { name: new RegExp(enterpriseFixture.campaignName) }).click()
        await expect(page).toHaveURL(/\/enterprise\/home/)
      }
      await page.goto(`${enterpriseBaseUrl}/evaluations`)
      const task = page.locator('article.task').filter({ hasText: fixture.student.name }).first()
      await expect(task).toBeVisible()
      await task.getByRole('button', { name: /开始评价|修改后重交/ }).click()
      const dialog = page.locator('form.dialog')
      const scoreInputs = dialog.locator('input[type="number"]')
      for (const [index, value] of ['92', '90', '94', '91', '95'].entries()) await scoreInputs.nth(index).fill(value)
      await dialog.locator('textarea').fill('出勤稳定，质量意识和安全纪律良好，能够独立完成复测与记录。')
      await dialog.locator('input[type="checkbox"]').check()
      const enterpriseSubmitted = page.waitForResponse((response) =>
        /\/api\/v1\/internship\/enterprise-portal\/evaluation-tasks\/\d+\/submit$/.test(apiPath(response))
        && response.request().method() === 'POST')
      await dialog.getByRole('button', { name: '提交企业评价', exact: true }).click()
      enterpriseEval = await responseData(await enterpriseSubmitted, '企业提交五维评价')
      enterpriseEval = await request('GET', `/internship/enterprise-evals/${enterpriseEval.id}`, { token: adminToken })
      enterpriseEval = await request('POST', `/internship/enterprise-evals/${enterpriseEval.id}/review-versioned`, {
        token: adminToken,
        body: { action: 'APPROVE', expectedVersion: enterpriseEval.version }
      })
    }
    enterpriseEvalId = String(enterpriseEval.id)
    expect(enterpriseEval.reviewStatus).toBe('APPROVED')

    const priorStudentEvals = await request('GET', '/internship/student-evals', {
      token: adminToken,
      params: { batchId: fixture.gj08.batchId, page: 1, pageSize: 200 }
    })
    let studentEval = rows(priorStudentEvals)
      .find((item) => String(item.internshipId || item.internId || '') === String(fixture.gj08.internshipId))
    const workbench = await openStudentInternship(page, fixture.gj08)
    await workbench.openGroupedTab('变更与结果', '实习成绩/自评')
    if (studentEval?.reviewStatus !== 'APPROVED') {
      const selfForm = page.locator('section.sp-card').filter({ hasText: '实习自评 / 鉴定' }).first()
      if (studentEval?.submitStatus !== 'SUBMITTED') {
        const selfTextareas = selfForm.locator('textarea')
        await selfTextareas.nth(0).fill('完成质量巡检、缺陷复测和安全记录，能按流程交付可复核成果。')
        await selfTextareas.nth(1).fill('形成了质量闭环意识，也认识到量化记录仍需持续加强。')
        await selfTextareas.nth(2).fill('复杂场景覆盖还需扩展，后续完善回归清单。')
        await selfForm.locator('select').nth(0).selectOption('5')
        await selfForm.locator('select').nth(1).selectOption('5')
        await selfTextareas.nth(3).fill('企业培养和安全保障清晰。')
        await selfTextareas.nth(4).fill('岗位内容与专业能力匹配。')
        const selfSubmitted = page.waitForResponse((response) =>
          apiPath(response) === '/api/v1/portal/internship/context/self-eval'
          && response.request().method() === 'POST')
        await selfForm.getByRole('button', { name: '提交自评', exact: true }).click()
        studentEval = await responseData(await selfSubmitted, '学生提交自评')
      }
      studentEval = await request('GET', `/internship/student-evals/${studentEval.id}`, { token: mentorToken })
      studentEval = await request('POST', `/internship/student-evals/${studentEval.id}/advisor-comment`, {
        token: mentorToken,
        body: {
          advisorOpinion: '学生实习表现良好，过程事实完整，同意进入成绩核算。',
          mentorOpinion: '企业评价与过程材料相互印证。',
          expectedVersion: studentEval.version
        }
      })
      studentEval = await request('POST', `/internship/student-evals/${studentEval.id}/review`, {
        token: adminToken,
        body: { action: 'APPROVE', expectedVersion: studentEval.version }
      })
    }
    studentEvalId = String(studentEval.id)
    expect(studentEval.reviewStatus).toBe('APPROVED')

    const existingScores = await request('GET', '/internship/scores', {
      token: mentorToken,
      params: { batchId: fixture.gj08.batchId, page: 1, pageSize: 200 }
    })
    let score = rows(existingScores)
      .find((item) => String(item.internshipId || item.internId || '') === String(fixture.gj08.internshipId))
    if (score) score = await request('GET', `/internship/scores/${score.id}`, { token: mentorToken })
    // A prior interrupted replay can leave an already-reviewed snapshot whose
    // source hash predates newly completed process facts. Formally return that
    // snapshot before recomputing; the publish guard must never be bypassed.
    if (score?.status === 'PENDING_PUBLISH') {
      score = await request('POST', `/internship/scores/${score.id}/return`, {
        token: adminToken,
        body: {
          reason: 'GJ08 过程事实已补全，退回后按当前来源快照重新核算',
          expectedVersion: score.version
        }
      })
    }
    if (!score || ['PENDING_CALC', 'WITHDRAWN'].includes(score.status)) {
      score = await request('POST', '/internship/scores/compute', {
        token: mentorToken,
        body: {
          internshipId: fixture.gj08.internshipId,
          ...(score ? { expectedVersion: score.version } : {})
        }
      })
    }
    scoreId = String(score.id)
    expect(score.incomplete).toBe(false)
    if (score.status === 'PENDING_REVIEW') {
      score = await request('POST', `/internship/scores/${scoreId}/review`, {
        token: adminToken, body: { expectedVersion: score.version }
      })
    }
    if (score.status === 'PENDING_PUBLISH') {
      score = await request('POST', `/internship/scores/${scoreId}/publish`, {
        token: adminToken, body: { expectedVersion: score.version }
      })
    }
    expect(score.status).toBe('PUBLISHED')

    await page.reload()
    await workbench.selectExactBatchIfNeeded()
    const scorePanelReady = await page.getByText('成绩与申诉', { exact: true })
      .waitFor({ state: 'visible', timeout: 20_000 })
      .then(() => true)
      .catch(() => false)
    if (!scorePanelReady) {
      await workbench.openGroupedTab('变更与结果', '实习成绩/自评')
    }
    await expect(page.locator('body')).toContainText(/发布时间|已发布|PUBLISHED/)
    const existingAppeals = await request('GET', '/internship/score-appeals', {
      token: adminToken,
      params: { batchId: fixture.gj08.batchId, page: 1, pageSize: 200 }
    })
    let appeal = rows(existingAppeals)
      .find((item) => String(item.internshipId || '') === String(fixture.gj08.internshipId))
    if (!appeal) {
      const appealForm = page.locator('section.sp-card').filter({ hasText: '成绩与申诉' }).first()
      await appealForm.locator('textarea[placeholder*="成绩有异议"]').fill('企业评价与过程材料已更新，请复核成绩构成和版本快照。')
      const appealed = page.waitForResponse((response) =>
        apiPath(response) === '/api/v1/portal/internship/score/appeal'
        && response.request().method() === 'POST')
      await appealForm.getByRole('button', { name: '提交成绩申诉', exact: true }).click()
      appeal = await responseData(await appealed, '学生提交成绩申诉')
    }
    appealId = String(appeal.id)
    expect(appealId).not.toBe('')

    let appealDetail = await request('GET', `/internship/score-appeals/${appealId}`, { token: adminToken })
    if (appealDetail.status === 'PENDING') {
      appealDetail = await request('POST', `/internship/score-appeals/${appealId}/approve`, {
        token: adminToken,
        body: { reason: '申诉材料成立，撤回原成绩并按当前来源事实重新核算', expectedVersion: appealDetail.version }
      })
    }
    expect(['APPROVED_RECALCULATING', 'CLOSED']).toContain(appealDetail.status)

    score = await request('GET', `/internship/scores/${scoreId}`, { token: mentorToken })
    if (['WITHDRAWN', 'PENDING_CALC'].includes(score.status)) {
      score = await request('POST', '/internship/scores/compute', {
        token: mentorToken,
        body: { internshipId: fixture.gj08.internshipId, expectedVersion: score.version }
      })
    }
    if (score.status === 'PENDING_REVIEW') {
      score = await request('POST', `/internship/scores/${scoreId}/review`, {
        token: adminToken, body: { expectedVersion: score.version }
      })
    }
    if (score.status === 'PENDING_PUBLISH') {
      score = await request('POST', `/internship/scores/${scoreId}/publish`, {
        token: adminToken, body: { expectedVersion: score.version }
      })
    }
    expect(score.status).toBe('PUBLISHED')
    expect(Number(score.version)).toBeGreaterThan(1)

    await staffLogin(page, config.sandboxAdmin, null)
    await page.goto(`${config.staffBaseUrl}/admin/internship/scores?stage=appeal&batchId=${fixture.gj08.batchId}`)
    await expect(page.locator('body')).toContainText(fixture.student.name)
    await expect(page.locator('body')).toContainText(/已发布|PUBLISHED/)
    await page.screenshot({ path: test.info().outputPath('ix-gj-08-republished-score.png'), fullPage: true })
  })

  test('IX-GJ-09：材料完整性、版本清单、归档包、恢复校验与就业衔接', async ({ page }) => {
    let archive = await request('GET', `/internship/archive/${fixture.gj08.internshipId}`, {
      token: adminToken
    })

    await staffLogin(page, config.sandboxAdmin, null)
    await page.evaluate((batchId) => localStorage.setItem('internship.selectedBatchId', String(batchId)), fixture.gj08.batchId)
    await page.goto(`${config.staffBaseUrl}/admin/internship/archive?panel=records&batchId=${fixture.gj08.batchId}&id=${fixture.gj08.internshipId}`)
    const workspace = page.getByRole('region', { name: /归档完整性核验/ })
    await expect(workspace).toBeVisible()
    await expect(workspace).toContainText(fixture.student.name)

    if (!archive.archived) {
      const preflightResponse = page.waitForResponse((response) =>
        apiPath(response) === `/api/v1/internship/archive/${fixture.gj08.internshipId}/preflight`
        && response.request().method() === 'POST')
      await workspace.getByRole('button', { name: '预检并提交归档', exact: true }).click()
      const preflight = await responseData(await preflightResponse, '归档业务与文件安全预检')
      expect(preflight.canArchive).toBe(true)
      expect(preflight.fileVersionSafety.status).toBe('READY')
      expect(preflight.missingActions).toEqual([])
      await expect(page.getByText('预检通过', { exact: true })).toBeVisible()
      await page.screenshot({ path: test.info().outputPath('ix-gj-09-preflight.png'), fullPage: true })

      const archiveResponse = page.waitForResponse((response) =>
        apiPath(response) === `/api/v1/internship/archive/${fixture.gj08.internshipId}/archive`
        && response.request().method() === 'POST')
      await page.getByRole('button', { name: '确认归档', exact: true }).click()
      const archived = await responseData(await archiveResponse, '冻结 FileVersion Manifest 与正式成绩')
      expect(archived.archived).toBe(true)
      expect(archived.operationReceipt.status).toBe('COMMITTED')
      expect(Number(archived.operationReceipt.fileVersionCount)).toBeGreaterThan(0)
      await expect(workspace).toContainText('已归档')
      archive = await request('GET', `/internship/archive/${fixture.gj08.internshipId}`, { token: adminToken })
    }

    let pkg = archive.latestPackage
    if (!pkg?.packageId) {
      const packageResponse = page.waitForResponse((response) =>
        apiPath(response) === `/api/v1/internship/archive/${fixture.gj08.internshipId}/package`
        && response.request().method() === 'POST')
      await workspace.getByRole('button', { name: '生成归档包', exact: true }).click()
      pkg = await responseData(await packageResponse, '生成冻结版本归档包')
    }
    expect(pkg.packageId).toBeTruthy()
    expect(Number(pkg.fileCount)).toBeGreaterThan(0)
    expect(String(pkg.sha256 || '')).toMatch(/^[a-f0-9]{64}$/)

    const restoreResponse = page.waitForResponse((response) =>
      apiPath(response) === `/api/v1/internship/archive-packages/${pkg.packageId}/restore-check`
      && response.request().method() === 'POST')
    await workspace.getByRole('button', { name: '恢复校验', exact: true }).click()
    const restore = await responseData(await restoreResponse, '档案包行数、文件数与哈希恢复校验')
    expect(restore.restoreReady).toBe(true)
    expect(restore.operationReceipt.status).toBe('VERIFIED')
    await expect(page.getByText('行数与哈希一致', { exact: true })).toBeVisible()

    await staffLogin(page, {
      tenant: fixture.tenantCode,
      username: 'e2e_ix_employment',
      password: 'E2eTest@2026'
    }, /就业老师|EMPLOYMENT_TEACHER/)
    await page.evaluate((batchId) => localStorage.setItem('internship.selectedBatchId', String(batchId)), fixture.gj08.batchId)
    await page.goto(`${config.staffBaseUrl}/admin/internship/archive?panel=records&batchId=${fixture.gj08.batchId}&id=${fixture.gj08.internshipId}`)
    const employmentWorkspace = page.getByRole('region', { name: /归档完整性核验/ })
    await expect(employmentWorkspace).toBeVisible()
    await expect(employmentWorkspace).toContainText('已归档')
    const employmentResponse = page.waitForResponse((response) =>
      apiPath(response) === `/api/v1/internship/archive/${fixture.gj08.internshipId}/employment-transition`
      && response.request().method() === 'GET')
    await employmentWorkspace.getByRole('button', { name: '衔接就业', exact: true }).click()
    const employment = await responseData(await employmentResponse, '按归档中冻结的正式结果衔接就业')
    expect(employment.finalScoreStatus).toBe('PUBLISHED')
    expect(employment.resultAuthority).toBe('PUBLISHED_FINAL_SCORE_FROZEN_IN_ARCHIVE')
    await expect(page).toHaveURL(/\/admin\/employment\/students/)
    await page.screenshot({ path: test.info().outputPath('ix-gj-09-employment-handoff.png'), fullPage: true })
  })
})
