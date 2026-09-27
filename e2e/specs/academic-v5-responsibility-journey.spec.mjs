import { test, expect } from '@playwright/test'
import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { execFileSync, spawn } from 'node:child_process'
import { StaffLoginPage, decodeJwt } from '../pages/login.page.mjs'
import { assertSafeEnvironment } from '../lib/config.mjs'

// A–C use one saved term and real browser writes. D–H remain uncovered.
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
  report ||= { scenario: 'A-C', prefix: fixture.prefix, tenantId: fixture.tenantId, termId: null, eventId: null, slotIds: [], batchIds: {}, taskIds: {}, pending: null, checkpoints: [], roles: [], uncovered: ['B', 'C', 'D', 'E', 'F', 'G', 'H'] }
  assert.equal(report.prefix, fixture.prefix); assert.equal(report.tenantId, fixture.tenantId)
  report.scenario = 'A-C'; report.passed = false; report.phase = '正常学校账号登录'; report.roles = []; report.failure = null
  report.batchIds ||= {}; report.taskIds ||= {}
  report.evidenceDirectory = evidenceDir
  await fs.mkdir(evidenceDir, { recursive: true })
  const save = () => fs.writeFile(resultFile, JSON.stringify(report, null, 2), 'utf8')
  const phase = async value => { report.phase = value; await save() }
  const observed = async (step, proof) => {
    if (report.pending?.step === step) report.pending = null
    report.checkpoints.push({ step, proof, observedAt: new Date().toISOString() }); await save()
  }
  const beforeWrite = async step => {
    assert.equal(report.pending, null, '前一命令结果尚未核对，禁止自动重放或继续写入')
    report.pending = { step, sentAt: new Date().toISOString() }; await save()
  }
  const failures = [], receipts = []
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
    a = await batchFacts(pages.collegeA, report.batchIds.A)
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
    assert.equal(failures.length, 0, '实际页面或接口存在错误')
    assert.equal(report.pending, null); report.passed = true; report.phase = '场景 A 至 C 完成，D 至 H 尚未覆盖'
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
  test.describe('V5 场景 A 至 C：学期建立、两院教学任务与教师确认', () => {
    test.describe.configure({ mode: 'serial', retries: 0 })
    test('同一学期下六角色独立登录，学院派师、教师确认与两级审核', async ({}, testInfo) => {
      test.setTimeout(1_200_000)
      const resultFile = ignoredFile(`${ignoredFile(process.env.E2E_V5_STATE)}.journey.json`)
      const child = spawn(process.execPath, [self], { cwd: root, env: { ...process.env, E2E_V5_CHILD: '1', DEBUG: '', PWDEBUG: '0' }, stdio: 'ignore', windowsHide: true })
      const timer = setTimeout(() => child.kill(), 1_140_000)
      let code
      try { code = await new Promise((resolve, reject) => { child.once('exit', resolve); child.once('error', reject) }) }
      finally { clearTimeout(timer) }
      await testInfo.attach('场景 A-C 无密回执', { path: resultFile, contentType: 'application/json' })
      const result = JSON.parse(await fs.readFile(resultFile, 'utf8'))
      if (result.evidenceDirectory) for (const name of await fs.readdir(result.evidenceDirectory)) {
        if (name.endsWith('.png')) await testInfo.attach(name, { path: path.join(result.evidenceDirectory, name), contentType: 'image/png' })
      }
      expect(code, 'V5 接力未完成：请核对无密回执中的当前阶段，禁止自动重放未确认写入').toBe(0)
      expect(result.passed).toBe(true); expect(result.roles).toHaveLength(6)
    })
  })
}
