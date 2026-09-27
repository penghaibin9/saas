import { test, expect } from '@playwright/test'
import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { execFileSync, spawn } from 'node:child_process'
import { StaffLoginPage, decodeJwt } from '../pages/login.page.mjs'
import { assertSafeEnvironment } from '../lib/config.mjs'
import { auditRows, assertActor } from '../lib/academic-v5-evidence.mjs'

// A–F use one saved term and real browser writes. G–H remain uncovered.
const root = fileURLToPath(new URL('../../', import.meta.url))
const self = fileURLToPath(import.meta.url)
const roles = ['school', 'collegeA', 'collegeB', 'teacherA', 'teacherB', 'leader']
const apiPath = '/api/v1/academic-affairs'
const termInput = { yearCode: '2025-2026', termNo: 2, startDate: '2026-02-23', endDate: '2026-07-12', teachingWeeks: 20, examWeekStart: 19 }

function isolatedUrl(name, fallback, port, pathname) {
  const url = new URL(process.env[name] || fallback)
  assert.ok(['127.0.0.1', 'localhost'].includes(url.hostname), '仅允许本机隔离环境')
  assert.equal(url.protocol, 'http:'); assert.equal(url.port, port, '禁止连接日常端口或其它项目')
  assert.equal(url.pathname.replace(/\/$/, ''), pathname)
  assert.equal(url.username + url.password + url.search + url.hash, '')
  return url.toString().replace(/\/$/, '')
}

function ignoredFile(value) {
  assert.ok(value, '必须配置私有忽略文件路径')
  const resolved = path.resolve(root, value)
  const relative = path.relative(root, resolved)
  assert.ok(relative && !relative.startsWith('..') && !path.isAbsolute(relative), '私有文件必须在当前工作区')
  execFileSync('git', ['check-ignore', '--quiet', '--', relative], { cwd: root, stdio: 'ignore' })
  return resolved
}

async function runJourney() {
  assertSafeEnvironment()
  const staff = isolatedUrl('E2E_STAFF_BASE_URL', 'http://127.0.0.1:5174', '5174', '')
  const api = isolatedUrl('E2E_API_BASE_URL', 'http://127.0.0.1:8002/api/v1', '8002', '/api/v1')
  const fixtureFile = ignoredFile(process.env.E2E_V5_STATE)
  const credentialFile = ignoredFile(process.env.E2E_V5_CREDENTIALS)
  const resultFile = ignoredFile(`${fixtureFile}.journey.json`)
  const evidenceDir = ignoredFile(`${fixtureFile}.journey-artifacts`)
  const fixture = JSON.parse(await fs.readFile(fixtureFile, 'utf8'))
  const credentials = JSON.parse(await fs.readFile(credentialFile, 'utf8'))
  assert.ok(fixture.prefix && typeof fixture.tenantId === 'string' && fixture.tenantCode, '场景前置数据不完整')
  for (const role of roles) {
    const account = fixture.accounts?.[role]
    assert.ok(account?.loginName && account.roleCode && account.contextId && typeof account.userId === 'string', '缺少正常角色身份')
    assert.equal(typeof credentials[account.loginName]?.password, 'string', '缺少核验有效的私有凭据')
  }
  for (const key of ['A', 'B']) for (const field of ['collegeId', 'majorId', 'classId']) assert.equal(typeof fixture.colleges?.[key]?.[field], 'string', '前置学院、专业及班级编号必须是字符串')
  let report
  try { report = JSON.parse(await fs.readFile(resultFile, 'utf8')) } catch (error) { if (error.code !== 'ENOENT') throw error }
  report ||= { scenario: 'A-F', prefix: fixture.prefix, tenantId: fixture.tenantId, termId: null, eventId: null, slotIds: [], batchIds: {}, taskIds: {}, pending: null, checkpoints: [], roles: [], uncovered: ['B', 'C', 'D', 'E', 'F', 'G', 'H'] }
  assert.equal(report.prefix, fixture.prefix); assert.equal(report.tenantId, fixture.tenantId)
  report.scenario = 'A-F'; report.passed = false; report.phase = '正常学校账号登录'; report.roles = []; report.failure = null
  report.batchIds ||= {}; report.taskIds ||= {}; report.scheduleBatchIds ||= {}; report.scheduleItemIds ||= {}
  report.gradeTaskIds ||= {}; report.gradeTaskOwners ||= {}
  report.evidenceDirectory = evidenceDir
  await fs.mkdir(evidenceDir, { recursive: true })
  const save = () => fs.writeFile(resultFile, JSON.stringify(report, null, 2), 'utf8')
  const phase = async value => { report.phase = value; await save() }
  const observed = async (step, proof) => {
    let actorRole, bizType, bizId, action
    if (step.startsWith('assign-B-')) { actorRole = 'collegeB'; bizType = 'AA_TASK'; bizId = step.slice(9); action = 'ASSIGN' }
    else if (step.startsWith('assign-')) { bizId = step.slice(7); actorRole = report.taskIds.A?.includes(bizId) ? 'collegeA' : 'collegeB'; bizType = 'AA_TASK'; action = 'ASSIGN' }
    else if (step.startsWith('teacher-B-')) { actorRole = 'teacherB'; bizType = 'AA_TASK'; bizId = step.slice(10); action = 'TEACHER_CONFIRM' }
    else if (step.startsWith('teacher-')) { actorRole = 'teacherA'; bizType = 'AA_TASK'; bizId = step.slice(8); action = 'TEACHER_CONFIRM' }
    else if (/^college-[AB]-confirm$/.test(step)) { actorRole = step.includes('-A-') ? 'collegeA' : 'collegeB'; bizType = 'AA_TASK_BATCH'; bizId = report.batchIds[actorRole === 'collegeA' ? 'A' : 'B']; action = 'COLLEGE_CONFIRM' }
    else if (/^school-[AB]-review$/.test(step)) { actorRole = 'school'; bizType = 'AA_TASK_BATCH'; bizId = report.batchIds[step.includes('-A-') ? 'A' : 'B']; action = 'ACADEMIC_APPROVE' }
    else if (step.startsWith('F-submit-')) { bizId = step.slice(9); actorRole = report.gradeTaskOwners[bizId]?.teacher; bizType = 'AA_GRADE_TASK'; action = 'SUBMIT' }
    else if (step.startsWith('F-college-')) { bizId = step.slice(10); actorRole = report.gradeTaskOwners[bizId]?.college; bizType = 'AA_GRADE_TASK'; action = 'COLLEGE_APPROVE' }
    else if (step.startsWith('F-publish-')) { bizId = step.slice(10); actorRole = 'school'; bizType = 'AA_GRADE_TASK'; action = 'PUBLISH' }
    if (actorRole) {
      const account = fixture.accounts[actorRole]
      const audit = assertActor(auditRows({ tenantId: fixture.tenantId, bizType, bizId, action, account }),
        { roleCode: account.roleCode, pendingAt: report.pending?.step === step ? report.pending.sentAt : null })
      proof = { ...proof, auditId: audit.id, actorUserId: account.userId }
    }
    if (report.pending?.step === step) report.pending = null
    report.checkpoints.push({ step, proof, observedAt: new Date().toISOString() }); await save()
  }
  const beforeWrite = async step => {
    assert.equal(report.pending, null, '前一命令结果尚未核对，禁止自动重放或继续写入')
    report.pending = { step, sentAt: new Date().toISOString() }; await save()
  }
  const failures = [], receipts = [], accessTokens = {}
  await phase('启动隔离浏览器')
  const { chromium } = await import('playwright')
  const browser = await chromium.launch({ headless: process.env.PW_HEADED !== 'true', channel: process.env.E2E_BROWSER_CHANNEL || 'msedge' })
  const contexts = []
  let activePage = null, authenticated = false
  const read = async response => {
    assert.equal(new URL(response.url()).origin, new URL(api).origin, '浏览器实际请求未到隔离后端')
    assert.equal(response.status(), 200, '正式接口未成功')
    const body = await response.json(); assert.equal(body.code, 0, '正式接口业务拒绝')
    return body.data
  }
  const responseFor = (page, pathname, method = 'GET') => page.waitForResponse(response => {
    const url = new URL(response.url())
    return url.pathname === pathname && response.request().method() === method
  }, { timeout: 120_000 })
  const readOnly = async (role, pathname) => {
    const response = await pages[role].context().request.get(`${new URL(api).origin}${pathname}`, {
      headers: { Authorization: `Bearer ${accessTokens[role]}` },
    })
    return read(response)
  }
  const visit = async (page, target, pathname, reload = false) => {
    const response = responseFor(page, pathname)
    await (reload ? page.reload() : page.goto(staff + target))
    const value = await read(await response)
    const skip = page.getByRole('button', { name: '跳过引导', exact: true })
    if (await skip.isVisible().catch(() => false)) await skip.click()
    return value
  }
  const capture = async (page, name) => {
    assert.ok(!new URL(page.url()).pathname.endsWith('/login'), '登录界面禁止截图')
    await page.screenshot({ path: path.join(evidenceDir, `${name}.png`), fullPage: false, animations: 'disabled', mask: [page.locator('.uchip, input, textarea, table tbody tr td:nth-child(-n+2)')] })
  }
  const login = async role => {
    authenticated = false
    const context = await browser.newContext({ viewport: { width: 1440, height: 1100 }, locale: 'zh-CN', timezoneId: 'Asia/Shanghai' })
    contexts.push(context)
    const page = await context.newPage(); activePage = page; page.setDefaultTimeout(120_000)
    page.on('pageerror', () => failures.push({ role, kind: '页面脚本错误' }))
    page.on('response', response => {
      const url = new URL(response.url())
      if (!url.pathname.startsWith('/api/v1/')) return
      if (url.origin !== new URL(api).origin) failures.push({ role, kind: '后端目标错误' })
      if (response.status() >= 400) failures.push({ role, path: url.pathname, status: response.status() })
      if (url.pathname.startsWith(apiPath)) receipts.push({ role, method: response.request().method(), path: url.pathname, status: response.status() })
    })
    const account = fixture.accounts[role], helper = new StaffLoginPage(page, staff)
    await helper.login({ tenant: fixture.tenantCode, username: account.loginName, password: credentials[account.loginName].password })
    const claims = decodeJwt(helper.lastAccessToken)
    assert.equal(String(claims.tenantId), fixture.tenantId)
    assert.equal(String(claims.userId).replace(/^db-/, ''), account.userId)
    assert.equal(claims.currentRoleCode, account.roleCode)
    assert.equal(claims.activeContextId, account.contextId)
    accessTokens[role] = helper.lastAccessToken
    helper.lastAccessToken = ''; authenticated = true
    await page.waitForLoadState('networkidle')
    assert.equal(failures.length, 0, '登录或运行目标核验失败')
    return page
  }
  const pages = {}
  const stage = (flow, label) => {
    const unit = flow.unitProgress.find(item => item.collegeId === fixture.colleges[label].collegeId)
    assert.ok(unit, '学校责任总览缺少场景学院')
    const taskStage = unit.stages.find(item => item.stageCode === 'F40_TEACHING_TASK')
    assert.ok(taskStage, '学院教学任务阶段缺失')
    return taskStage
  }
  const batchFacts = async (page, batchId) => {
    const base = `${apiPath}/teaching-task-batches/${batchId}`
    const workbenchResponse = responseFor(page, `${base}/workbench`)
    const tasksResponse = responseFor(page, `${base}/tasks`)
    await page.goto(`${staff}/admin/academic-affairs/teaching-tasks/${batchId}`)
    const [workbench, tasks] = await Promise.all([read(await workbenchResponse), read(await tasksResponse)])
    assert.equal(workbench.batchId, batchId)
    assert.equal(Number(tasks.total), tasks.list.length, '本批次任务未读全，禁止按不完整列表办理')
    return { workbench, tasks: tasks.list }
  }
  const choose = async (scope, label, value) => {
    const picker = scope.locator('label').filter({ hasText: label }).locator('.app-remote-select')
    if ((await picker.getByRole('combobox').innerText()).includes(value)) return
    await picker.getByRole('combobox').click()
    await picker.getByRole('option').filter({ hasText: value }).click()
  }
  try {
    await phase('正常学校账号登录')
    const school = await login('school')
    await phase('学校核对并建立正式学期')
    const catalog = await visit(school, '/admin/academic-affairs/terms', `${apiPath}/terms`)
    const terms = catalog.items || []
    assert.ok(Number(catalog.total ?? terms.length) <= terms.length, '学期列表未读全，请先通过分页核对已有对象，禁止猜测新建')
    const matches = terms.filter(row => row.yearCode === termInput.yearCode && row.termNo === 2)
    assert.ok(matches.length <= 1, '同学年学期存在多个对象，需要核对正式数据')
    let term = report.termId ? terms.find(row => row.termId === report.termId) : matches[0]
    if (report.termId) assert.ok(term, '已记录学期不在正式列表，禁止重新创建')
    if (!term) {
      await school.getByRole('button', { name: '新建学期', exact: true }).click()
      await school.locator('#aa-term-year').fill(termInput.yearCode)
      await school.locator('#aa-term-number').selectOption('2')
      await school.locator('#aa-term-name').fill(`${fixture.prefix} 学期责任接力`)
      await school.getByLabel('开学日期', { exact: true }).fill(termInput.startDate)
      await school.getByLabel('结束日期', { exact: true }).fill(termInput.endDate)
      await school.locator('#aa-term-weeks').fill('20'); await school.locator('#aa-term-exam-week').fill('19')
      await beforeWrite('term')
      const created = responseFor(school, `${apiPath}/terms`, 'POST')
      await school.getByRole('button', { name: '创建学期草稿', exact: true }).click()
      term = await read(await created); assert.equal(typeof term.termId, 'string')
      report.termId = term.termId; await save()
    } else { report.termId = term.termId; await save() }
    term = await visit(school, `/admin/academic-affairs/terms/${report.termId}`, `${apiPath}/terms/${report.termId}`)
    for (const [key, value] of Object.entries(termInput)) assert.equal(term[key], value, '已有学期必须与场景正式前置条件一致')
    await observed('term', { termId: term.termId, status: term.status })
    await capture(school, 'A01-学校正式学期')

    await phase('学校核对并维护本学期校历')
    const calendarPath = `/admin/academic-affairs/calendar?termId=${report.termId}&tab=holiday`
    let events = (await visit(school, calendarPath, `${apiPath}/terms/${report.termId}/calendar`)).items || []
    const holiday = events.find(row => row.eventType === 'HOLIDAY' && row.startDate === '2026-05-01' && row.endDate === '2026-05-01')
    if (!holiday) {
      assert.equal(term.status, 'DRAFT', '已发布学期缺少目标校历事件，禁止改旧终态或重复创建学期')
      await school.getByRole('button', { name: '新增节假日', exact: true }).click()
      const form = school.locator('.aa-cal-form:visible')
      for (const label of ['开始日期', '结束日期']) {
        const input = form.locator('label').filter({ hasText: label }).locator('input')
        await input.fill('2026-05-01'); await input.press('Tab')
      }
      await form.getByPlaceholder('选填，如 国庆假期 / 国庆调休').fill(`${fixture.prefix} 校历核验`)
      await beforeWrite('calendar')
      const added = responseFor(school, `${apiPath}/terms/${report.termId}/calendar`, 'POST')
      await form.getByRole('button', { name: '添加', exact: true }).click()
      const event = await read(await added); assert.equal(typeof event.eventId, 'string'); report.eventId = event.eventId; await save()
    } else report.eventId = String(holiday.eventId)
    events = (await visit(school, calendarPath, `${apiPath}/terms/${report.termId}/calendar`, true)).items || []
    assert.ok(events.some(row => String(row.eventId) === report.eventId && row.eventType === 'HOLIDAY'))
    await observed('calendar', { termId: report.termId, eventId: report.eventId })
    await capture(school, 'A02-校历同学期刷新')

    await phase('学校核对并维护正式作息')
    await visit(school, '/admin/academic-affairs/time-slots', `${apiPath}/time-slots`)
    const template = school.locator('details.aa-slot-template')
    await template.locator('summary').click()
    const previewRequest = responseFor(school, `${apiPath}/time-slots/template-preview`, 'POST')
    await template.getByRole('button', { name: '检查当前作息', exact: true }).click()
    const preview = await read(await previewRequest)
    assert.equal(preview.blockedCount, 0, '原作息存在冲突，禁止覆盖')
    if (preview.readyCount > 0) {
      await beforeWrite('slots')
      await template.getByRole('button', { name: `创建 ${preview.readyCount} 个缺失节次`, exact: true }).click()
      await expect(template.getByRole('button', { name: '创建 0 个缺失节次', exact: true })).toBeVisible({ timeout: 120_000 })
    }
    const slots = (await visit(school, '/admin/academic-affairs/time-slots', `${apiPath}/time-slots`, true)).items || []
    for (const item of preview.items) {
      const slot = slots.find(row => row.slotNo === item.desired.slotNo)
      assert.ok(slot && slot.enabled, '正式作息节次缺失或停用')
      assert.equal(slot.startTime?.slice(0, 5), item.desired.startTime); assert.equal(slot.endTime?.slice(0, 5), item.desired.endTime)
    }
    report.slotIds = slots.map(row => String(row.slotId)); await observed('slots', { slotIds: report.slotIds })
    await capture(school, 'A03-正式作息刷新')

    await phase('学校核验并发布本学期校历')
    await visit(school, `/admin/academic-affairs/calendar?termId=${report.termId}&tab=publish`, `${apiPath}/terms/${report.termId}`)
    if (term.status === 'DRAFT') {
      const publish = school.getByRole('button', { name: '核验并发布校历', exact: true }).first()
      await expect(publish).toBeEnabled(); await publish.click()
      const dialog = school.getByRole('dialog', { name: '发布校历', exact: true })
      await expect(dialog).toContainText(report.termId)
      await beforeWrite('publish')
      const published = responseFor(school, `${apiPath}/terms/${report.termId}/calendar/publish`, 'POST')
      await dialog.getByRole('button', { name: '确认发布', exact: true }).click()
      const result = await read(await published); assert.equal(result.termId, report.termId); assert.equal(result.status, 'PUBLISHED')
    }
    const currentResponse = responseFor(school, `${apiPath}/terms/current`)
    term = await visit(school, `/admin/academic-affairs/terms/${report.termId}`, `${apiPath}/terms/${report.termId}`)
    const currentTerm = await read(await currentResponse)
    assert.equal(term.status, 'PUBLISHED'); assert.equal(currentTerm.termId, report.termId)
    await observed('publish', { termId: report.termId, status: term.status, currentTermId: currentTerm.termId })
    await capture(school, 'A04-学期发布与当前学期')

    for (const role of roles) {
      await phase(`正常角色首页范围核对：${role}`)
      const page = role === 'school' ? school : await login(role)
      pages[role] = page
      const account = fixture.accounts[role]
      const evidence = { role, userId: account.userId, reads: [] }
      for (const reload of [false, true]) {
        const flow = await visit(page, `/admin/academic-affairs?termId=${report.termId}`, `${apiPath}/flow`, reload)
        assert.equal(flow.term.termId, report.termId)
        const surface = page.locator('[aria-label="学期责任接力"]')
        await expect(surface).toBeVisible(); await expect(surface).not.toContainText('责任进度读取失败')
        if (role === 'school' || role === 'leader') {
          assert.ok(['TENANT_ALL', 'SCHOOL'].includes(flow.viewer.scopeType))
          for (const college of Object.values(fixture.colleges)) assert.ok(flow.unitProgress.some(unit => unit.collegeId === college.collegeId))
          await expect(surface.getByRole('heading', { name: '学校教学运行总控', exact: true })).toBeVisible()
          await expect(surface.getByRole('heading', { name: '各学院并行进度', exact: true })).toBeVisible()
          if (role === 'leader') {
            assert.deepEqual(flow.viewer.majorIds, [])
            assert.deepEqual(flow.viewer.assignments, [])
            assert.deepEqual(flow.currentResponsibilities, [])
            const stages = [...flow.stages, ...flow.unitProgress.flatMap(unit => unit.stages)]
            assert.ok(stages.every(stage => !stage.responsibility?.assigneeUserIds?.includes(account.userId)), '学校只读观察员不能成为当前办理人')
            assert.ok(stages.every(stage => !stage.primaryAction || /^查看/.test(stage.primaryAction.label)), '学校只读观察员只能获得查看入口')
            await expect(surface.locator('[aria-label="我的责任事项"]')).toHaveCount(0)
            await expect(surface.getByRole('button', { name: /^(新建|生成|提交|保存|确认|通过|退回|审批|发布|封存|处理)/ })).toHaveCount(0)
            assert.equal(receipts.filter(row => row.role === 'leader' && row.method !== 'GET').length, 0, '学校只读观察员不得发出教务写请求')
          }
        } else if (role.startsWith('college')) {
          const collegeId = fixture.colleges[role.endsWith('A') ? 'A' : 'B'].collegeId
          assert.equal(flow.viewer.scopeType, 'COLLEGE'); assert.deepEqual(flow.viewer.collegeIds, [collegeId])
          assert.ok(flow.unitProgress.every(unit => unit.collegeId === collegeId)); assert.equal(flow.schoolGates.length, 0)
          await expect(surface.getByRole('heading', { name: '本学院教学运行', exact: true })).toBeVisible()
        } else if (role.startsWith('teacher')) {
          assert.equal(flow.viewer.scopeType, 'ASSIGNED'); assert.equal(flow.unitProgress.length, 0); assert.equal(flow.schoolGates.length, 0)
          assert.ok(flow.currentResponsibilities.every(stage => stage.responsibility.assigneeUserIds.includes(account.userId)))
          await expect(surface.getByRole('heading', { name: '我的教学责任', exact: true })).toBeVisible()
        }
        if (!['school', 'leader'].includes(role)) await expect(surface.getByRole('heading', { name: '各学院并行进度', exact: true })).toHaveCount(0)
        evidence.reads.push({ refresh: reload, termId: flow.term.termId, scopeType: flow.viewer.scopeType, collegeIds: flow.viewer.collegeIds, majorIds: flow.viewer.majorIds, currentResponsibilityCount: flow.currentResponsibilities.length, stages: flow.stages.map(stage => ({ code: stage.stageCode, status: stage.status })) })
        await capture(page, `A05-${role}-${reload ? '刷新' : '进入'}`)
      }
      report.roles.push(evidence); await save()
    }
    // 总册 B 的“学院 A 全部 READY”须落在教师确认及两级审核之后；
    // B 先检查 A 全部分配、B 恰有两条待分配，C 再推进 A 的正式 READY。
    for (const label of ['A', 'B']) {
      const role = `college${label}`, page = pages[role], collegeId = fixture.colleges[label].collegeId
      const batchName = `${fixture.prefix} ${label}学院教学任务`
      await phase(`学院 ${label} 从已发布方案生成本学期教学任务`)
      const listed = await visit(page, `/admin/academic-affairs/teaching-tasks?termId=${report.termId}`, `${apiPath}/teaching-task-batches`)
      assert.equal(Number(listed.total), listed.list.length, '本学期批次未读全，禁止重复生成')
      const existing = listed.list.filter(item => item.batchName === batchName && item.termId === report.termId && item.collegeId === collegeId)
      assert.ok(existing.length <= 1, '同名学院批次重复，需人工核对')
      let batchId = report.batchIds[label] || existing[0]?.batchId
      if (report.batchIds[label]) assert.equal(existing[0]?.batchId, batchId, '已保存的批次未在正式列表中找到')
      if (!batchId) {
        await page.getByRole('button', { name: '从方案生成任务', exact: true }).click()
        const form = page.locator('section.app-section-card').filter({ hasText: '从已发布培养方案生成' })
        await choose(form, '学期', `${fixture.prefix} 学期责任接力`)
        await choose(form, '开课责任学院', `V5 ${label === 'A' ? '甲' : '乙'}学院 ${fixture.prefix}`)
        await form.getByPlaceholder('选填，如 2026秋教学任务').fill(batchName)
        await beforeWrite(`batch-${label}`)
        const generated = responseFor(page, `${apiPath}/teaching-task-batches/generate`, 'POST')
        await form.getByRole('button', { name: '生成并检查', exact: true }).click()
        const result = await read(await generated)
        batchId = result.batchId; assert.equal(typeof batchId, 'string')
        report.batchIds[label] = batchId; await save()
      }
      const facts = await batchFacts(page, batchId)
      assert.equal(facts.workbench.termId, report.termId)
      assert.equal(facts.workbench.collegeId, collegeId)
      assert.ok(facts.tasks.length >= (label === 'B' ? 2 : 1), '来源培养方案尚未形成足量正式任务；须先准备课程、已发布并绑定的方案')
      report.taskIds[label] = facts.tasks.map(item => item.taskId)
      await observed(`batch-${label}`, { batchId, taskIds: report.taskIds[label], termId: report.termId, collegeId })
      await capture(page, `B01-${label}学院任务批次`)
    }

    for (const label of ['A', 'B']) {
      const page = pages[`college${label}`], batchId = report.batchIds[label]
      const account = fixture.accounts[`teacher${label}`]
      const facts = await batchFacts(page, batchId)
      const targetIds = label === 'A' ? facts.tasks.map(item => item.taskId) : facts.tasks.slice(0, -2).map(item => item.taskId)
      for (const taskId of targetIds) {
        const task = facts.tasks.find(item => item.taskId === taskId)
        assert.ok(['PENDING_ASSIGN', 'ASSIGNED', 'TEACHER_CONFIRMED', 'READY'].includes(task.status), '批次已有非场景任务状态，禁止覆盖')
        if (task.status !== 'PENDING_ASSIGN') {
          assert.equal(task.teacherKey, account.teacherKey, '已分配任务属于其他教师，禁止改派')
          if (report.pending?.step === `assign-${taskId}`) await observed(`assign-${taskId}`, { batchId, taskId, teacherUserId: account.userId, status: task.status })
          continue
        }
        await phase(`学院 ${label} 为正式任务分配任课教师`)
        const row = page.locator('tr').filter({ hasText: task.courseCode }).filter({ hasText: task.teachingClassCode })
        await row.getByRole('button', { name: '分配教师', exact: true }).click()
        const dialog = page.getByRole('dialog', { name: '分配任课教师', exact: true })
        await choose(dialog, '任课教师', account.teacherKey)
        await beforeWrite(`assign-${taskId}`)
        const assignment = responseFor(page, `${apiPath}/teaching-tasks/${taskId}/assign`, 'POST')
        await dialog.getByRole('button', { name: '确认分配', exact: true }).click()
        await read(await assignment)
        const after = await batchFacts(page, batchId)
        const assigned = after.tasks.find(item => item.taskId === taskId)
        assert.equal(assigned?.status, 'ASSIGNED'); assert.equal(assigned.teacherKey, account.teacherKey)
        await observed(`assign-${taskId}`, { batchId, taskId, teacherUserId: account.userId, status: assigned.status })
      }
    }
    await phase('学校核对两院并行状态和 B 学院两条未分配阻断')
    let a = await batchFacts(pages.collegeA, report.batchIds.A)
    let b = await batchFacts(pages.collegeB, report.batchIds.B)
    assert.equal(a.workbench.unassignedCount, 0)
    assert.ok(a.tasks.every(item => item.teacherKey === fixture.accounts.teacherA.teacherKey))
    assert.equal(b.workbench.unassignedCount, 2)
    assert.ok(b.tasks.filter(item => item.status === 'PENDING_ASSIGN').length === 2)
    let flow = await visit(school, `/admin/academic-affairs?termId=${report.termId}`, `${apiPath}/flow`, true)
    assert.equal(stage(flow, 'B').status, 'BLOCKED')
    if (!report.checkpoints.some(item => item.step === 'B')) {
      assert.ok(a.tasks.every(item => item.status === 'ASSIGNED'), 'B 阶段应由教师 A 接收但尚未确认')
      assert.equal(stage(flow, 'A').status, 'ACTION_REQUIRED')
      await observed('B', { aBatchId: report.batchIds.A, bBatchId: report.batchIds.B, aAssigned: a.tasks.length, bUnassigned: 2, aStage: stage(flow, 'A').status, bStage: stage(flow, 'B').status })
      report.uncovered = ['C', 'D', 'E', 'F', 'G', 'H']; await save()
      await capture(school, 'B02-学校两院任务状态')
    }

    for (const taskId of report.taskIds.A) {
      const teacher = pages.teacherA
      await phase('教师 A 仅确认本人正式教学任务')
      const mine = await visit(teacher, `/admin/academic-affairs/teaching-tasks/teacher-confirm?taskId=${taskId}`, `${apiPath}/teaching-tasks`)
      assert.equal(mine.total, 1); assert.equal(mine.list[0]?.taskId, taskId)
      assert.equal(mine.list[0].teacherKey, fixture.accounts.teacherA.teacherKey)
      if (['TEACHER_CONFIRMED', 'READY'].includes(mine.list[0].status)) {
        if (report.pending?.step === `teacher-${taskId}`) await observed(`teacher-${taskId}`, { taskId, status: mine.list[0].status })
        continue
      }
      assert.equal(mine.list[0].status, 'ASSIGNED')
      const row = teacher.locator('tr').filter({ hasText: mine.list[0].courseCode }).filter({ hasText: mine.list[0].teachingClassCode })
      await row.getByRole('button', { name: '确认接受', exact: true }).click()
      const dialog = teacher.getByRole('dialog', { name: '确认接受授课安排', exact: true })
      await beforeWrite(`teacher-${taskId}`)
      const accepted = responseFor(teacher, `${apiPath}/teaching-tasks/${taskId}/teacher-act`, 'POST')
      await dialog.getByRole('button', { name: '确认接受', exact: true }).click()
      await read(await accepted)
      const confirmed = await visit(teacher, `/admin/academic-affairs/teaching-tasks/teacher-confirm?taskId=${taskId}`, `${apiPath}/teaching-tasks`, true)
      assert.equal(confirmed.list[0]?.taskId, taskId); assert.equal(confirmed.list[0]?.status, 'TEACHER_CONFIRMED')
      await observed(`teacher-${taskId}`, { taskId, status: confirmed.list[0].status })
    }
    const forbidden = await visit(pages.teacherB, `/admin/academic-affairs/teaching-tasks/teacher-confirm?taskId=${report.taskIds.A[0]}`, `${apiPath}/teaching-tasks`)
    assert.equal(forbidden.total, 0, '教师 B 不得看到教师 A 的任务')
    await expect(pages.teacherB.getByRole('button', { name: '确认接受', exact: true })).toHaveCount(0)
    const targetTaskId = report.taskIds.A[0]
    const beforeForbidden = auditRows({ tenantId: fixture.tenantId, bizType: 'AA_TASK', bizId: targetTaskId,
      action: 'TEACHER_CONFIRM', account: fixture.accounts.teacherA })
    const denied = await pages.teacherB.context().request.post(`${new URL(api).origin}${apiPath}/teaching-tasks/${targetTaskId}/teacher-act`, {
      headers: { Authorization: `Bearer ${accessTokens.teacherB}` }, data: { action: 'CONFIRM' },
    })
    assert.ok([403, 404].includes(denied.status()), '教师 B 越权确认必须由正式服务拒绝')
    const deniedBody = await denied.json()
    assert.notEqual(deniedBody.code, 0, '教师 B 越权请求不得返回业务成功')
    const afterForbidden = auditRows({ tenantId: fixture.tenantId, bizType: 'AA_TASK', bizId: targetTaskId,
      action: 'TEACHER_CONFIRM', account: fixture.accounts.teacherA })
    assert.deepEqual(afterForbidden.rows, beforeForbidden.rows, '越权请求不得增加目标任务确认审计')
    a = await batchFacts(pages.collegeA, report.batchIds.A)
    assert.equal(a.tasks.find(item => item.taskId === targetTaskId)?.status, 'TEACHER_CONFIRMED', '越权请求不得改变目标任务')
    assert.ok(a.tasks.every(item => ['TEACHER_CONFIRMED', 'READY'].includes(item.status)))
    flow = await visit(school, `/admin/academic-affairs?termId=${report.termId}`, `${apiPath}/flow`, true)
    assert.equal(stage(flow, 'B').status, 'BLOCKED')
    if (!report.checkpoints.some(item => item.step === 'C-teacher')) {
      assert.equal(stage(flow, 'A').status, 'ACTION_REQUIRED')
      await observed('C-teacher', { aStage: stage(flow, 'A').status, bStage: stage(flow, 'B').status, teacherTaskIds: report.taskIds.A })
    }

    await phase('学院 A 正式确认批次')
    if (a.workbench.status === 'DRAFT') {
      assert.equal(a.workbench.actions.canCollegeConfirm, true)
      await beforeWrite('college-A-confirm')
      const collegeConfirmed = responseFor(pages.collegeA, `${apiPath}/teaching-task-batches/${report.batchIds.A}/college-confirm`, 'POST')
      await pages.collegeA.getByRole('button', { name: '学院确认', exact: true }).click()
      const collegeReceipt = await read(await collegeConfirmed)
      assert.equal(collegeReceipt.status, 'COLLEGE_CONFIRMED')
    }
    a = await batchFacts(pages.collegeA, report.batchIds.A)
    assert.ok(['COLLEGE_CONFIRMED', 'APPROVED'].includes(a.workbench.status))
    await observed('college-A-confirm', { batchId: report.batchIds.A, status: a.workbench.status })

    await phase('校教务终审学院 A 教学任务')
    const schoolBatch = await batchFacts(school, report.batchIds.A)
    if (schoolBatch.workbench.status === 'COLLEGE_CONFIRMED') {
      assert.equal(schoolBatch.workbench.actions.canAcademicReview, true)
      await school.getByRole('button', { name: '教务终审通过', exact: true }).click()
      const reviewDialog = school.getByRole('dialog', { name: '确认教务终审通过', exact: true })
      await beforeWrite('school-A-review')
      const approved = responseFor(school, `${apiPath}/teaching-task-batches/${report.batchIds.A}/review`, 'POST')
      await reviewDialog.getByRole('button', { name: '确认通过', exact: true }).click()
      const schoolReceipt = await read(await approved)
      assert.equal(schoolReceipt.status, 'APPROVED')
    }
    a = await batchFacts(school, report.batchIds.A)
    assert.equal(a.workbench.status, 'APPROVED')
    assert.ok(a.tasks.every(item => item.status === 'READY'))
    await observed('school-A-review', { batchId: report.batchIds.A, status: a.workbench.status, taskIds: report.taskIds.A })
    flow = await visit(school, `/admin/academic-affairs?termId=${report.termId}`, `${apiPath}/flow`, true)
    assert.equal(stage(flow, 'A').status, 'READY')
    assert.equal(stage(flow, 'B').status, 'BLOCKED')
    const gate = flow.schoolGates.find(item => item.stageCode === 'F40_TEACHING_TASK')
    assert.equal(gate.readyUnitCount, 1); assert.equal(gate.totalUnitCount, 2); assert.equal(gate.ready, false)
    await observed('C', { aStage: stage(flow, 'A').status, bStage: stage(flow, 'B').status, gate: { readyUnitCount: gate.readyUnitCount, totalUnitCount: gate.totalUnitCount } })
    report.uncovered = ['D', 'E', 'F', 'G', 'H']; await save()
    await capture(school, 'C01-学院A就绪学校一院未就绪')

    await phase('排课前学校门禁核对与学院 A 建立正式排课批次')
    const scheduleGate = flow.schoolGates.find(item => item.stageCode === 'F50_SCHEDULE')
    assert.ok(scheduleGate && !scheduleGate.ready, '学院 B 教学任务未就绪时不得开放全校课表发布')
    const scheduleName = `${fixture.prefix} A学院排课`
    const scheduleListPath = `${apiPath}/schedule-batches`
    let schedules = await visit(pages.collegeA, `/admin/academic-affairs/schedule?termId=${report.termId}`, scheduleListPath)
    assert.equal(Number(schedules.total), schedules.list.length, '课表批次未读全，禁止猜测新建')
    const owned = schedules.list.filter(item => item.batchName === scheduleName && item.termId === report.termId && item.collegeId === fixture.colleges.A.collegeId)
    assert.ok(owned.length <= 1, '同一学院排课批次重复，需核对原命令')
    let scheduleBatchId = report.scheduleBatchIds.A || owned[0]?.batchId
    if (report.scheduleBatchIds.A) assert.equal(owned[0]?.batchId, scheduleBatchId, '已保存排课批次不在正式列表')
    if (!scheduleBatchId) {
      await pages.collegeA.getByRole('button', { name: '＋ 创建排课批次', exact: true }).click()
      const form = pages.collegeA.locator('section.app-section-card').filter({ hasText: '新建课表批次' })
      await choose(form, '学期', `${fixture.prefix} 学期责任接力`)
      await form.getByPlaceholder('选填', { exact: true }).fill(scheduleName)
      await form.getByRole('combobox', { name: '排课范围', exact: true }).selectOption('COLLEGE')
      await choose(form, '学院', `V5 甲学院 ${fixture.prefix}`)
      await beforeWrite('schedule-A-batch')
      const created = responseFor(pages.collegeA, scheduleListPath, 'POST')
      await form.getByRole('button', { name: '创建', exact: true }).click()
      scheduleBatchId = (await read(await created)).batchId
      assert.equal(typeof scheduleBatchId, 'string')
      report.scheduleBatchIds.A = scheduleBatchId; await save()
    }
    schedules = await visit(pages.collegeA, `/admin/academic-affairs/schedule?termId=${report.termId}`, scheduleListPath, true)
    const schedule = schedules.list.find(item => item.batchId === scheduleBatchId)
    assert.equal(schedule?.termId, report.termId)
    assert.equal(schedule?.collegeId, fixture.colleges.A.collegeId)
    assert.equal(schedule?.status, 'DRAFT')
    await observed('schedule-A-batch', { scheduleBatchId, termId: report.termId, collegeId: fixture.colleges.A.collegeId, status: schedule.status })
    await capture(pages.collegeA, 'D01-学院A正式排课批次')

    // 学校统一发布须等待 B 学院；由 B 本人补齐教学任务，再回读全校门禁。
    for (const taskId of report.taskIds.B) {
      let current = await batchFacts(pages.collegeB, report.batchIds.B)
      let task = current.tasks.find(item => item.taskId === taskId)
      if (task.status === 'PENDING_ASSIGN') {
        await phase('学院 B 补齐原两条未派师任务')
        const row = pages.collegeB.locator('tr').filter({ hasText: task.courseCode }).filter({ hasText: task.teachingClassCode })
        await row.getByRole('button', { name: '分配教师', exact: true }).click()
        const dialog = pages.collegeB.getByRole('dialog', { name: '分配任课教师', exact: true })
        await choose(dialog, '任课教师', fixture.accounts.teacherB.teacherKey)
        await beforeWrite(`assign-B-${taskId}`)
        const assignment = responseFor(pages.collegeB, `${apiPath}/teaching-tasks/${taskId}/assign`, 'POST')
        await dialog.getByRole('button', { name: '确认分配', exact: true }).click()
        await read(await assignment)
        current = await batchFacts(pages.collegeB, report.batchIds.B)
        task = current.tasks.find(item => item.taskId === taskId)
        assert.equal(task?.status, 'ASSIGNED')
        await observed(`assign-B-${taskId}`, { taskId, batchId: report.batchIds.B, status: task.status })
      } else if (report.pending?.step === `assign-B-${taskId}`) {
        assert.equal(task.teacherKey, fixture.accounts.teacherB.teacherKey)
        await observed(`assign-B-${taskId}`, { taskId, batchId: report.batchIds.B, status: task.status })
      }
      assert.equal(task.teacherKey, fixture.accounts.teacherB.teacherKey)
      const teacher = pages.teacherB
      const mine = await visit(teacher, `/admin/academic-affairs/teaching-tasks/teacher-confirm?taskId=${taskId}`, `${apiPath}/teaching-tasks`)
      assert.equal(mine.total, 1); assert.equal(mine.list[0]?.taskId, taskId)
      if (mine.list[0].status === 'ASSIGNED') {
        await phase('教师 B 本人确认补齐的教学任务')
        const row = teacher.locator('tr').filter({ hasText: mine.list[0].courseCode }).filter({ hasText: mine.list[0].teachingClassCode })
        await row.getByRole('button', { name: '确认接受', exact: true }).click()
        await beforeWrite(`teacher-B-${taskId}`)
        const accepted = responseFor(teacher, `${apiPath}/teaching-tasks/${taskId}/teacher-act`, 'POST')
        await teacher.getByRole('dialog', { name: '确认接受授课安排', exact: true }).getByRole('button', { name: '确认接受', exact: true }).click()
        await read(await accepted)
        const confirmed = await visit(teacher, `/admin/academic-affairs/teaching-tasks/teacher-confirm?taskId=${taskId}`, `${apiPath}/teaching-tasks`, true)
        assert.equal(confirmed.list[0]?.status, 'TEACHER_CONFIRMED')
        await observed(`teacher-B-${taskId}`, { taskId, status: confirmed.list[0].status })
      } else {
        assert.ok(['TEACHER_CONFIRMED', 'READY'].includes(mine.list[0].status))
        if (report.pending?.step === `teacher-B-${taskId}`) await observed(`teacher-B-${taskId}`, { taskId, status: mine.list[0].status })
      }
    }
    b = await batchFacts(pages.collegeB, report.batchIds.B)
    assert.equal(b.workbench.unassignedCount, 0)
    assert.ok(b.tasks.every(item => ['TEACHER_CONFIRMED', 'READY'].includes(item.status)))
    if (b.workbench.status === 'DRAFT') {
      await phase('学院 B 本人核对并确认')
      assert.equal(b.workbench.actions.canCollegeConfirm, true)
      await beforeWrite('college-B-confirm')
      const confirmed = responseFor(pages.collegeB, `${apiPath}/teaching-task-batches/${report.batchIds.B}/college-confirm`, 'POST')
      await pages.collegeB.getByRole('button', { name: '学院确认', exact: true }).click()
      assert.equal((await read(await confirmed)).status, 'COLLEGE_CONFIRMED')
    }
    b = await batchFacts(school, report.batchIds.B)
    assert.ok(['COLLEGE_CONFIRMED', 'APPROVED'].includes(b.workbench.status))
    await observed('college-B-confirm', { batchId: report.batchIds.B, status: b.workbench.status })
    if (b.workbench.status === 'COLLEGE_CONFIRMED') {
      await phase('学校终审学院 B 后重新核对全校')
      assert.equal(b.workbench.actions.canAcademicReview, true)
      await school.getByRole('button', { name: '教务终审通过', exact: true }).click()
      await beforeWrite('school-B-review')
      const approvedB = responseFor(school, `${apiPath}/teaching-task-batches/${report.batchIds.B}/review`, 'POST')
      await school.getByRole('dialog', { name: '确认教务终审通过', exact: true }).getByRole('button', { name: '确认通过', exact: true }).click()
      assert.equal((await read(await approvedB)).status, 'APPROVED')
    }
    b = await batchFacts(school, report.batchIds.B)
    assert.equal(b.workbench.status, 'APPROVED')
    assert.ok(b.tasks.every(item => item.status === 'READY'))
    await observed('school-B-review', { batchId: report.batchIds.B, status: b.workbench.status })
    flow = await visit(school, `/admin/academic-affairs?termId=${report.termId}`, `${apiPath}/flow`, true)
    assert.equal(stage(flow, 'A').status, 'READY'); assert.equal(stage(flow, 'B').status, 'READY')
    await observed('D-tasks-ready', { aBatchId: report.batchIds.A, bBatchId: report.batchIds.B, termId: report.termId })

    // D: the existing HYBRID rule lets the public course's configured offering
    // college schedule it. The school sees the whole-school conflict and publishes.
    await phase('校级核对公共课开课单位规则及正式教室资源')
    const scheduleStage = flow.stages.find(item => item.stageCode === 'F50_SCHEDULE')
    assert.ok(scheduleStage, '学校缺少排课责任阶段')
    assert.equal(scheduleStage.evidence?.publicScheduleMode, 'HYBRID',
      '本故事按当前正式开课单位编排规则验收，不得猜测公共课归属')
    const roomCode = `${fixture.prefix}ROOM`, roomName = `${fixture.prefix} 教学教室`
    const roomPath = `${apiPath}/classrooms`
    let rooms = await visit(school, '/admin/academic-affairs/classrooms', roomPath)
    let room = (rooms.items || []).find(item => item.roomCode === roomCode)
    if (!room) {
      await school.getByRole('button', { name: '单间新增', exact: true }).click()
      await school.locator('[data-field="cr-building-code"] input').fill(`${fixture.prefix}BLDG`)
      await school.locator('[data-field="cr-building-name"] input').fill(`${fixture.prefix} 教学楼`)
      await school.locator('[data-field="cr-room-code"] input').fill(roomCode)
      await school.locator('[data-field="cr-room-name"] input').fill(roomName)
      await school.locator('[data-field="cr-capacity"] input').fill('40')
      await beforeWrite('D-classroom')
      const created = responseFor(school, roomPath, 'POST')
      await school.getByRole('button', { name: '保存教室', exact: true }).click()
      room = await read(await created)
      assert.equal(typeof room.classroomId, 'string')
      report.classroomId = room.classroomId; await save()
    }
    rooms = await visit(school, '/admin/academic-affairs/classrooms', roomPath, true)
    room = (rooms.items || []).find(item => item.roomCode === roomCode)
    assert.equal(room?.classroomId, report.classroomId || room?.classroomId)
    assert.equal(room?.status, 'AVAILABLE'); assert.equal(room?.allowSchedule, true)
    report.classroomId = room.classroomId
    await observed('D-classroom', { classroomId: room.classroomId, roomCode, capacity: room.capacity })

    const ensureScheduleBatch = async (role, label, scope) => {
      const page = pages[role], name = `${fixture.prefix} ${label}排课`
      const batches = await visit(page, `/admin/academic-affairs/schedule?termId=${report.termId}`, scheduleListPath)
      assert.equal(Number(batches.total), batches.list.length, '排课批次列表未读全')
      const found = batches.list.filter(item => item.batchName === name && item.termId === report.termId)
      assert.ok(found.length <= 1, '同名排课批次重复，禁止猜测新建')
      let id = report.scheduleBatchIds[label] || found[0]?.batchId
      if (report.scheduleBatchIds[label]) assert.equal(found[0]?.batchId, id, '保存的排课批次未在正式列表')
      if (!id) {
        await page.getByRole('button', { name: '＋ 创建排课批次', exact: true }).click()
        const form = page.locator('section.app-section-card').filter({ hasText: '新建课表批次' })
        await choose(form, '学期', `${fixture.prefix} 学期责任接力`)
        await form.getByPlaceholder('选填', { exact: true }).fill(name)
        await form.getByRole('combobox', { name: '排课范围', exact: true }).selectOption(scope)
        if (scope === 'COLLEGE') await choose(form, '学院', `V5 乙学院 ${fixture.prefix}`)
        await beforeWrite(`schedule-${label}-batch`)
        const created = responseFor(page, scheduleListPath, 'POST')
        await form.getByRole('button', { name: '创建', exact: true }).click()
        id = (await read(await created)).batchId
        assert.equal(typeof id, 'string')
        report.scheduleBatchIds[label] = id; await save()
      }
      const detail = await readOnly(role, `${scheduleListPath}/${id}`)
      assert.equal(detail.termId, report.termId)
      assert.equal(detail.collegeId || null, scope === 'SCHOOL' ? null : fixture.colleges.B.collegeId)
      assert.equal(detail.status, 'DRAFT')
      await observed(`schedule-${label}-batch`, { scheduleBatchId: id, scope, termId: report.termId })
      return id
    }
    await ensureScheduleBatch('collegeB', 'B', 'COLLEGE')

    const summaries = {}
    for (const label of ['A', 'B']) {
      const role = `college${label}`
      summaries[label] = await readOnly(role, `${scheduleListPath}/${report.scheduleBatchIds[label]}/summary`)
      assert.ok(summaries[label].totalTasks > 0, `${label}正式排课范围无教学任务`)
      assert.equal(summaries[label].invalidTaskCount, 0, `${label} 教学任务的周次或周学时异常`)
    }
    if (!report.scheduleTaskIds) {
      report.scheduleTaskIds = Object.fromEntries(['A', 'B'].map(label => [label, summaries[label].missingTasks.map(item => item.taskId)]))
      await save()
    }
    const coverage = ['A', 'B'].flatMap(label => report.scheduleTaskIds[label])
    assert.equal(new Set(coverage).size, coverage.length, '排课责任范围重叠')
    assert.deepEqual(new Set(coverage), new Set([...report.taskIds.A, ...report.taskIds.B]), '公共课及两院专业课责任范围未完整覆盖')
    assert.equal(report.scheduleTaskIds.A.length, summaries.A.totalTasks)
    assert.equal(report.scheduleTaskIds.B.length, summaries.B.totalTasks)
    assert.ok(report.scheduleTaskIds.A.every(id => report.taskIds.A.includes(id)))
    assert.ok(report.scheduleTaskIds.B.every(id => report.taskIds.B.includes(id)))
    assert.equal(summaries.A.courseScopeCounts.public, 0, '学院 A 不得编排乙学院开课的公共课')
    assert.ok(summaries.B.courseScopeCounts.public >= 1, '学院 B 开课的公共课未进入其正式排课责任')
    assert.ok(summaries.A.courseScopeCounts.professional >= 1 && summaries.B.courseScopeCounts.professional >= 1)
    await observed('D-responsibility', { taskCount: coverage.length, publicTaskCount: summaries.B.courseScopeCounts.public,
      collegeATaskCount: summaries.A.totalTasks, collegeBTaskCount: summaries.B.totalTasks })

    const scheduleOne = async (role, label, task, ordinal) => {
      const page = pages[role], batchId = report.scheduleBatchIds[label]
      const target = `/admin/academic-affairs/schedule/${batchId}/edit?classId=${task.classId}&taskId=${task.taskId}&termId=${report.termId}`
      const classViewPath = `${scheduleListPath}/${batchId}/class-view`
      const classViewResponse = responseFor(page, classViewPath)
      await visit(page, target, `${scheduleListPath}/${batchId}`)
      const before = await read(await classViewResponse)
      assert.ok(Array.isArray(before.items), '班级课表未返回正式课位清单')
      await expect(page.locator('.aa-grid__cell.is-editable').first()).toBeVisible()
      const cells = page.locator('.aa-grid__cell.is-editable').filter({ has: page.locator('.aa-grid__add') })
      const count = await cells.count()
      assert.ok(count >= 7, '缺少可选课位，禁止伪造课表')
      let conflictSeen = false
      for (let index = 0; index < count; index++) {
        const cell = cells.nth(index)
        if (!(await cell.isVisible().catch(() => false))) continue
        await cell.click()
        const dialog = page.locator('.app-confirm-dialog:visible')
        await expect(dialog).toBeVisible()
        await dialog.locator('select.app-select__el').first().selectOption(task.taskId)
        const preflight = page.waitForResponse(response => {
          if (new URL(response.url()).pathname !== `${scheduleListPath}/${batchId}/items/preflight` || response.request().method() !== 'POST') return false
          try { return Boolean(response.request().postDataJSON()?.classroom) } catch { return false }
        }, { timeout: 120_000 })
        await choose(dialog, '教室', roomName)
        const checked = await preflight
        assert.equal(checked.request().postDataJSON().classroom, roomName, '正式教室选择结果与教室目录不一致')
        const check = await read(checked)
        if (!check.allowed) {
          conflictSeen = true
          await expect(dialog).toContainText('存在硬冲突')
          await dialog.getByRole('button', { name: '取消', exact: true }).click()
          continue
        }
        await expect(dialog.getByRole('button', { name: '确认排课', exact: true })).toBeEnabled()
        const step = `D-${label}-${task.taskId}-${ordinal}`
        await beforeWrite(step)
        const created = responseFor(page, `${scheduleListPath}/${batchId}/items`, 'POST')
        await dialog.getByRole('button', { name: '确认排课', exact: true }).click()
        const item = await read(await created)
        assert.equal(item.taskId, task.taskId); assert.equal(item.batchId, batchId)
        assert.equal(typeof item.itemId, 'string')
        report.scheduleItemIds[task.taskId] ||= []
        report.scheduleItemIds[task.taskId].push(item.itemId); await save()
        const persisted = await readOnly(role, `${classViewPath}?classId=${task.classId}`)
        assert.ok(persisted.items.some(row => row.itemId === item.itemId && row.taskId === task.taskId), '课位写后未从正式服务回读')
        await observed(step, { scheduleBatchId: batchId, itemId: item.itemId, taskId: task.taskId,
          classId: task.classId, weekday: item.weekday, slotNo: item.slotNo })
        return conflictSeen
      }
      assert.fail(`${label} 教学任务 ${task.taskId} 无可排课位；须在正式页面协调，不得造课表`)
    }
    let crossCollegeRoomConflict = false
    for (const label of ['A', 'B']) {
      const role = `college${label}`
      const summaryPath = `${scheduleListPath}/${report.scheduleBatchIds[label]}/summary`
      const initial = await readOnly(role, summaryPath)
      assert.equal(initial.taskQueueTotal, initial.taskQueue.length, '排课任务队列未读全')
      const queue = initial.taskQueue
      for (const task of queue) {
        assert.ok(task.canSchedule && task.remainingSessions > 0 && task.remainingSessions <= 12)
        assert.ok([fixture.colleges.A.classId, fixture.colleges.B.classId].includes(task.classId))
        for (let ordinal = 0; ordinal < task.remainingSessions; ordinal++) {
          await phase(`${label}责任账号在正式课表为 ${task.courseName} 排第 ${ordinal + 1} 节`)
          const conflict = await scheduleOne(role, label, task, ordinal)
          if (label === 'B') crossCollegeRoomConflict ||= conflict
        }
      }
      const complete = await readOnly(role, summaryPath)
      assert.equal(complete.complete, true, `${label} 排课未完成`)
      assert.equal(complete.hardConflicts, 0)
      assert.equal(complete.scheduledSessions, complete.expectedSessions)
      await observed(`D-${label}-complete`, { scheduleBatchId: report.scheduleBatchIds[label],
        totalTasks: complete.totalTasks, expectedSessions: complete.expectedSessions, hardConflicts: complete.hardConflicts })
    }
    report.crossCollegeRoomConflict ||= crossCollegeRoomConflict; await save()
    assert.equal(report.crossCollegeRoomConflict, true, '学院 B 必须在同一教室撞见 A 的课位并通过页面改到无冲突位置')
    const bTaskId = report.scheduleTaskIds.B[0]
    const bItemId = report.scheduleItemIds[bTaskId]?.[0]
    assert.ok(bItemId, '缺少学院 B 正式课位用于跨学院越权核验')
    const foreignTask = (await batchFacts(pages.collegeB, report.batchIds.B)).tasks.find(item => item.taskId === bTaskId)
    assert.ok(foreignTask?.classId)
    const foreignBefore = await readOnly('collegeB', `${scheduleListPath}/${report.scheduleBatchIds.B}/class-view?classId=${foreignTask.classId}`)
    const forbiddenMove = await pages.collegeA.context().request.put(`${new URL(api).origin}${scheduleListPath}/${report.scheduleBatchIds.B}/items/${bItemId}`, {
      headers: { Authorization: `Bearer ${accessTokens.collegeA}` },
      data: { weekday: 5, slotNo: 1, reason: 'V5 跨学院越权负向核验' },
    })
    assert.ok([403, 404].includes(forbiddenMove.status()), '学院 A 修改学院 B 课位必须由正式服务拒绝')
    assert.notEqual((await forbiddenMove.json()).code, 0)
    const foreignAfter = await readOnly('collegeB', `${scheduleListPath}/${report.scheduleBatchIds.B}/class-view?classId=${foreignTask.classId}`)
    assert.deepEqual(foreignAfter.items, foreignBefore.items, '跨学院越权请求不得修改 B 的课位')
    await observed('D', { aBatchId: report.scheduleBatchIds.A, bBatchId: report.scheduleBatchIds.B,
      publicCourseOwner: fixture.colleges.B.collegeId, classroomId: room.classroomId, crossCollegeRoomConflict })
    report.uncovered = ['E', 'F', 'G', 'H']; await save()

    // E: each college pre-publishes its own complete batch; only the school
    // account executes formal publication after the whole-school gate passes.
    const publishPath = '/admin/academic-affairs/schedule/publish'
    const publishOne = async (role, label, intent) => {
      const page = pages[role], batchId = report.scheduleBatchIds[label]
      await visit(page, `${publishPath}?batchId=${batchId}`, scheduleListPath)
      const row = page.getByRole('row').filter({ hasText: `${fixture.prefix} ${label === 'A' ? 'A学院排课' : 'B排课'}` })
      await expect(row).toBeVisible()
      const action = intent === 'pre' ? '检查并预发布' : '检查并正式发布'
      const checked = responseFor(page, `${scheduleListPath}/${batchId}/summary`)
      await row.getByRole('button', { name: action, exact: true }).click()
      const gateSummary = await read(await checked)
      assert.equal(gateSummary.complete, true, `${label} 排课漏排或冲突未清零`)
      if (intent === 'pub') {
        assert.equal(gateSummary.schoolGate?.ready, true, '全校发布门禁未通过')
        assert.equal(gateSummary.schoolGate?.hardConflicts, 0)
      }
      const buttonName = intent === 'pre' ? '确认进入预发布' : '确认正式发布并通知师生'
      const step = `E-${intent}-${label}`
      await beforeWrite(step)
      const written = responseFor(page, `${scheduleListPath}/${batchId}/${intent === 'pre' ? 'pre-publish' : 'publish'}`, 'POST')
      await page.getByRole('button', { name: buttonName, exact: true }).click()
      const receipt = await read(await written)
      assert.equal(receipt.batchId, batchId)
      const detail = await readOnly(role, `${scheduleListPath}/${batchId}`)
      assert.equal(detail.status, intent === 'pre' ? 'PRE_PUBLISHED' : 'PUBLISHED')
      await observed(step, { batchId, actorUserId: fixture.accounts[role].userId, status: detail.status,
        expectedSessions: gateSummary.expectedSessions, hardConflicts: gateSummary.hardConflicts })
    }
    for (const label of ['A', 'B']) {
      const role = `college${label}`
      await phase(`${label}责任账号在正式页面预发布完整课表`)
      const detail = await readOnly(role, `${scheduleListPath}/${report.scheduleBatchIds[label]}`)
      if (detail.status === 'DRAFT') await publishOne(role, label, 'pre')
      else assert.ok(['PRE_PUBLISHED', 'PUBLISHED'].includes(detail.status), '批次状态被其他人改变，不自动沿用')
    }
    const schoolGateSummary = await readOnly('school', `${scheduleListPath}/${report.scheduleBatchIds.A}/summary`)
    assert.equal(schoolGateSummary.schoolGate?.ready, true)
    assert.equal(schoolGateSummary.schoolGate?.missingTaskCount, 0)
    assert.equal(schoolGateSummary.schoolGate?.hardConflicts, 0)
    await observed('E-school-gate', { requiredBatchIds: schoolGateSummary.schoolGate.requiredBatchIds,
      missingTaskCount: 0, hardConflicts: 0 })
    for (const label of ['A', 'B']) {
      await phase(`校教务本人正式发布 ${label} 完整课表`)
      const detail = await readOnly('school', `${scheduleListPath}/${report.scheduleBatchIds[label]}`)
      if (detail.status === 'PRE_PUBLISHED') await publishOne('school', label, 'pub')
      else assert.equal(detail.status, 'PUBLISHED', '已发布批次需由审计证明原操作者')
    }
    for (const label of ['A', 'B']) {
      const detail = await readOnly('school', `${scheduleListPath}/${report.scheduleBatchIds[label]}`)
      assert.equal(detail.status, 'PUBLISHED')
      assert.equal(detail.activeTruth?.isCurrent, true, '发布后缺少当前正式版本')
    }
    flow = await visit(school, `/admin/academic-affairs?termId=${report.termId}`, `${apiPath}/flow`, true)
    assert.equal(stage(flow, 'A').status, 'READY'); assert.equal(stage(flow, 'B').status, 'READY')
    assert.equal(flow.schoolGates.find(item => item.stageCode === 'F50_SCHEDULE')?.ready, true)
    await observed('E', { termId: report.termId, publishedBatchIds: Object.values(report.scheduleBatchIds) })
    report.uncovered = ['F', 'G', 'H']; await save()

    // F: each formal teaching task has one grade task. Its own teacher enters
    // every roster score, its own college reviews, then school publishes.
    const gradePath = `${apiPath}/grade-tasks`
    const exactGrade = async (role, id) => {
      const result = await readOnly(role, `${gradePath}?taskId=${id}&page=1&pageSize=1`)
      assert.equal(result.total, 1, '成绩任务必须按精确编号回读')
      assert.equal(result.list[0]?.gradeTaskId, id)
      return result.list[0]
    }
    for (const label of ['A', 'B']) {
      const teacherRole = `teacher${label}`, collegeRole = `college${label}`
      for (const teachingTaskId of report.taskIds[label]) {
        let gradeTaskId = report.gradeTaskIds[teachingTaskId]
        const existing = await readOnly(teacherRole, `${gradePath}?termId=${report.termId}&page=1&pageSize=100`)
        assert.equal(existing.total, existing.list.length, '本学期教师成绩任务未读全')
        const matched = existing.list.filter(item => item.teachingTaskId === teachingTaskId)
        assert.ok(matched.length <= 1, '同一教学任务有重复成绩任务')
        if (gradeTaskId) assert.equal(matched[0]?.gradeTaskId, gradeTaskId, '保存的成绩任务不在教师本人正式列表')
        else gradeTaskId = matched[0]?.gradeTaskId
        if (!gradeTaskId) {
          await phase(`任课教师 ${label} 从本人教学任务建立正式成绩任务`)
          const page = pages[teacherRole]
          await visit(page, `/admin/academic-affairs/grade-entry?action=create&teachingTaskId=${teachingTaskId}`, gradePath)
          await expect(page.getByRole('button', { name: '创建任务', exact: true })).toBeVisible()
          await expect(page.getByLabel('已锁定教学任务')).toBeVisible()
          await beforeWrite(`F-create-${teachingTaskId}`)
          const created = responseFor(page, gradePath, 'POST')
          await page.getByRole('button', { name: '创建任务', exact: true }).click()
          gradeTaskId = (await read(await created)).gradeTaskId
          assert.equal(typeof gradeTaskId, 'string')
          report.gradeTaskIds[teachingTaskId] = gradeTaskId; await save()
        }
        report.gradeTaskOwners[gradeTaskId] = { teacher: teacherRole, college: collegeRole, teachingTaskId }
        await save()
        let grade = await exactGrade(teacherRole, gradeTaskId)
        assert.equal(grade.teachingTaskId, teachingTaskId)
        await observed(`F-create-${teachingTaskId}`, { gradeTaskId, teachingTaskId, teacherUserId: fixture.accounts[teacherRole].userId })

        if (['NOT_STARTED', 'INPUTTING', 'RETURNED'].includes(grade.status)) {
          await phase(`任课教师 ${label} 经正式教学名单逐生录入`)
          const page = pages[teacherRole]
          await visit(page, `/admin/academic-affairs/grade-entry?taskId=${gradeTaskId}`, gradePath)
          const roster = await readOnly(teacherRole, `${gradePath}/${gradeTaskId}/roster`)
          assert.equal(roster.items.length, 2, '本故事每个虚构班须有两名正式学生')
          assert.deepEqual(new Set(roster.items.map(item => item.studentId)), new Set(fixture.colleges[label].studentIds))
          await page.getByRole('button', { name: '重新读取正式名单', exact: true }).click()
          for (const student of roster.items) {
            const records = await readOnly(teacherRole, `${gradePath}/${gradeTaskId}/records`)
            const record = records.items.find(item => item.studentId === student.studentId)
            if (record?.usualScore === 75 && record?.finalScore === 85 && record?.totalScore != null) continue
            assert.ok(!record || record.usualScore == null && record.finalScore == null, '已有不同分数，禁止覆盖')
            const row = page.locator('tr').filter({ hasText: student.studentNo })
            await expect(row).toBeVisible()
            const numbers = row.locator('input[type="number"]')
            await numbers.first().fill('75'); await numbers.last().fill('85')
            await beforeWrite(`F-score-${gradeTaskId}-${student.studentId}`)
            const saved = responseFor(page, `${gradePath}/${gradeTaskId}/scores`, 'POST')
            await row.getByRole('button', { name: '保存', exact: true }).click()
            await read(await saved)
            const after = await readOnly(teacherRole, `${gradePath}/${gradeTaskId}/records`)
            const formal = after.items.find(item => item.studentId === student.studentId)
            assert.equal(Number(formal?.usualScore), 75); assert.equal(Number(formal?.finalScore), 85)
            assert.ok(formal?.totalScore != null)
            await observed(`F-score-${gradeTaskId}-${student.studentId}`, { gradeTaskId, studentId: student.studentId, totalScore: formal.totalScore })
          }
          grade = await exactGrade(teacherRole, gradeTaskId)
          assert.ok(grade.allowedActions.includes('SUBMIT'), '正式成绩未形成可提交状态')
          await phase(`任课教师 ${label} 本人提交学院审核`)
          await page.getByRole('button', { name: '提交学院审核', exact: true }).click()
          await beforeWrite(`F-submit-${gradeTaskId}`)
          const submitted = responseFor(page, `${gradePath}/${gradeTaskId}/submit`, 'POST')
          await page.getByRole('dialog', { name: '提交进入学院审核' }).getByRole('button', { name: '确认提交学院' }).click()
          await read(await submitted)
        }
        grade = await exactGrade(teacherRole, gradeTaskId)
        assert.ok(['SUBMITTED', 'ACADEMIC_REVIEW', 'PUBLISHED'].includes(grade.status))
        await observed(`F-submit-${gradeTaskId}`, { gradeTaskId, status: grade.status, actorUserId: fixture.accounts[teacherRole].userId })
        if (grade.status === 'SUBMITTED') {
          await phase(`学院 ${label} 责任账号核对证据并审核成绩`)
          const page = pages[collegeRole]
          await visit(page, `/admin/academic-affairs/grade-college-review?taskId=${gradeTaskId}`, gradePath)
          await expect(page.getByRole('button', { name: '通过并交教务', exact: true })).toBeEnabled()
          await page.getByRole('button', { name: '通过并交教务', exact: true }).click()
          await beforeWrite(`F-college-${gradeTaskId}`)
          const reviewed = responseFor(page, `${gradePath}/${gradeTaskId}/college-review`, 'POST')
          await page.getByRole('dialog', { name: '通过并交教务' }).getByRole('button', { name: '确认通过并交教务' }).click()
          await read(await reviewed)
        }
        grade = await exactGrade('school', gradeTaskId)
        assert.ok(['ACADEMIC_REVIEW', 'PUBLISHED'].includes(grade.status))
        await observed(`F-college-${gradeTaskId}`, { gradeTaskId, status: grade.status, actorUserId: fixture.accounts[collegeRole].userId })
        if (grade.status === 'ACADEMIC_REVIEW') {
          await phase('校教务本人核验并发布正式成绩')
          const page = school
          await visit(page, `/admin/academic-affairs/grade-publish?taskId=${gradeTaskId}`, gradePath)
          await page.getByRole('button', { name: '核验并正式发布', exact: true }).click()
          await beforeWrite(`F-publish-${gradeTaskId}`)
          const published = responseFor(page, `${gradePath}/${gradeTaskId}/publish`, 'POST')
          await page.getByRole('dialog', { name: /发布.*成绩/ }).getByRole('button', { name: '确认发布（不可撤销）' }).click()
          const receipt = await read(await published)
          assert.equal(receipt.gradeTaskId, gradeTaskId)
        }
        grade = await exactGrade('school', gradeTaskId)
        assert.equal(grade.status, 'PUBLISHED')
        assert.ok(grade.courseId && grade.teachingClassId, '正式成绩须回链课程版本及教学班')
        await observed(`F-publish-${gradeTaskId}`, { gradeTaskId, teachingTaskId, status: grade.status,
          courseId: grade.courseId, teachingClassId: grade.teachingClassId, actorUserId: fixture.accounts.school.userId })
      }
    }
    flow = await visit(school, `/admin/academic-affairs?termId=${report.termId}`, `${apiPath}/flow`, true)
    for (const label of ['A', 'B']) {
      const stageGrade = flow.unitProgress.find(item => item.collegeId === fixture.colleges[label].collegeId)?.stages
        .find(item => item.stageCode === 'F90_GRADE')
      assert.equal(stageGrade?.status, 'DONE', `学院 ${label} 正式成绩未完成`)
    }
    await observed('F', { termId: report.termId, gradeTaskIds: Object.values(report.gradeTaskIds) })
    report.uncovered = ['G', 'H']; await save()
    assert.equal(failures.length, 0, '实际页面或接口存在错误')
    assert.equal(report.pending, null); report.passed = true; report.phase = '场景 A 至 F 完成，G 至 H 尚未覆盖'
  } catch (error) {
    report.failure = { phase: report.phase, type: error.name || 'Error', message: '当前阶段未通过；保留正式对象及待核对命令，未自动重放写入。' }
    if (authenticated && activePage) await capture(activePage, '当前阶段-失败时脱敏页面').catch(() => {})
    throw new Error('V5 接力未完成，详见无密结果文件中的阶段与回执')
  } finally {
    report.receipts = receipts; report.errors = failures; report.finishedAt = new Date().toISOString()
    await save(); await Promise.all(contexts.map(context => context.close())); await browser.close()
  }
}

if (process.env.E2E_V5_CHILD === '1') {
  // A standalone browser process keeps login fill values out of test-runner API
  // step parameters. No trace, video, storageState, headers or auth bodies are saved.
  await runJourney().catch(() => { process.exitCode = 1 })
} else {
  test.use({ trace: 'off', video: 'off', screenshot: 'off' })
  test.describe('V5 场景 A 至 F：学期、教学任务、排课发布与成绩接力', () => {
    test.describe.configure({ mode: 'serial', retries: 0 })
    test('同一学期下六角色独立登录并接力办理至正式成绩', async ({}, testInfo) => {
      test.setTimeout(3_600_000)
      const resultFile = ignoredFile(`${ignoredFile(process.env.E2E_V5_STATE)}.journey.json`)
      const child = spawn(process.execPath, [self], { cwd: root, env: { ...process.env, E2E_V5_CHILD: '1', DEBUG: '', PWDEBUG: '0' }, stdio: 'ignore', windowsHide: true })
      const timer = setTimeout(() => child.kill(), 3_540_000)
      let code
      try { code = await new Promise((resolve, reject) => { child.once('exit', resolve); child.once('error', reject) }) }
      finally { clearTimeout(timer) }
      await testInfo.attach('场景 A-F 无密回执', { path: resultFile, contentType: 'application/json' })
      const result = JSON.parse(await fs.readFile(resultFile, 'utf8'))
      if (result.evidenceDirectory) for (const name of await fs.readdir(result.evidenceDirectory)) {
        if (name.endsWith('.png')) await testInfo.attach(name, { path: path.join(result.evidenceDirectory, name), contentType: 'image/png' })
      }
      expect(code, 'V5 接力未完成：请核对无密回执中的当前阶段，禁止自动重放未确认写入').toBe(0)
      expect(result.passed).toBe(true); expect(result.roles).toHaveLength(6)
    })
  })
}
