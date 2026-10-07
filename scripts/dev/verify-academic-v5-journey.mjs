// Non-cleanup daily-sandbox verification. Core business writes are browser clicks only.
import { readFile, mkdir, writeFile } from 'node:fs/promises'
import { execFileSync } from 'node:child_process'
import { createRequire } from 'node:module'
import { dirname, isAbsolute, relative, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import assert from 'node:assert/strict'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '../..')
const args = process.argv.slice(2)
if (args.includes('--help')) {
  console.log('用法：node scripts/dev/verify-academic-v5-journey.mjs --config <已忽略的临时配置路径> [--execute]\n默认仅正常登录、定位同一对象和检查前置条件；--execute 才执行分配、教师确认、学院确认、教务终审。')
  process.exit(0)
}
const configIndex = args.indexOf('--config')
assert.ok(configIndex >= 0 && args[configIndex + 1], '必须通过 --config 指定已忽略的临时配置')
assert.ok(args.every((arg, index) => arg === '--config' || arg === '--execute' || index === configIndex + 1), '存在无法识别的参数')
const configPath = resolve(args[configIndex + 1])
const configRelative = relative(root, configPath)
assert.ok(configRelative && !configRelative.startsWith('..') && !isAbsolute(configRelative), '临时配置必须位于当前工作区的忽略目录内')
execFileSync('git', ['check-ignore', '--quiet', '--', configRelative], { cwd: root, stdio: 'ignore' })
let config
try { config = JSON.parse(await readFile(configPath, 'utf8')) } catch { throw new Error('临时配置无法读取，请核对文件与数据格式') }
const execute = args.includes('--execute')
const secrets = Object.values(config.accounts || {}).flatMap(account => [account.username, account.password]).filter(value => typeof value === 'string' && value)
const redact = value => secrets.reduce((text, secret) => text.split(secret).join('[已隐藏]'), String(value || ''))
const report = { mode: execute ? '正常页面办理' : '只读前置核验', batchId: config.batchId, taskId: config.taskId, steps: [], requests: [], passed: false }
const outputDir = resolve(root, '.codex-artifacts', 'academic-v5-journey', new Date().toISOString().replace(/[:.]/g, '-'))
let browser, capture
const sessions = {}

try {
  const base = new URL(config.staffBaseUrl)
  assert.ok(base.protocol === 'http:' && ['localhost', '127.0.0.1'].includes(base.hostname) && base.port === '5173' && base.pathname === '/' && !base.search && !base.username && !base.password, '仅允许已核验的本机 5173 日常入口')
  assert.equal(config.tenant, 'sandbox-school', '仅允许日常沙箱学校')
  for (const key of ['batchId', 'taskId']) assert.ok(typeof config[key] === 'string' && /^\d+$/.test(config[key]), '业务编号必须为数字字符串')
  for (const key of ['courseName', 'teachingClassName', 'teacherKey', 'teacherOptionLabel']) assert.ok(typeof config[key] === 'string' && config[key].trim(), '缺少任务或教师定位信息')
  for (const role of ['college', 'teacher', 'school']) {
    const account = config.accounts?.[role]
    assert.ok(typeof account?.username === 'string' && account.username && typeof account?.password === 'string' && account.password && typeof account?.roleLabel === 'string' && account.roleLabel.trim(), '缺少对应岗位的正常登录配置')
  }
  const require = createRequire(new URL('../../e2e/package.json', import.meta.url))
  const { chromium, expect } = require('@playwright/test')
  const { StaffLoginPage, decodeJwt } = await import('../../e2e/pages/login.page.mjs')
  browser = await chromium.launch({ headless: true, ...(process.platform === 'win32' ? { channel: 'msedge' } : {}) })
  await mkdir(outputDir, { recursive: true })
  const api = '/api/v1/academic-affairs'
  const batchPath = `${api}/teaching-task-batches/${config.batchId}`
  const taskPath = `${api}/teaching-tasks/${config.taskId}`
  const taskRow = page => page.locator('table tbody tr').filter({ hasText: config.courseName }).filter({ hasText: config.teachingClassName })
  const businessResponses = []

  async function dataOf(response) {
    assert.ok(response.ok(), `业务请求失败，状态码 ${response.status()}`)
    const body = await response.json()
    assert.equal(body.code, 0, '业务请求未被正式受理')
    return body.data
  }
  function waitRead(page, path, query = {}) {
    return page.waitForResponse(response => {
      const url = new URL(response.url())
      return response.request().method() === 'GET' && url.pathname === path && Object.entries(query).every(([key, value]) => url.searchParams.get(key) === value)
    }).then(dataOf)
  }
  async function screenshot(page, name) {
    const mask = [page.locator('.uchip, #staff-account, #staff-password, .app-remote-select__opt-desc'), ...secrets.map(secret => page.getByText(secret, { exact: true }))]
    await page.screenshot({ path: resolve(outputDir, `${name}.png`), fullPage: true, mask })
  }
  capture = screenshot
  async function login(role) {
    const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } })
    const page = await context.newPage()
    page.setDefaultTimeout(30_000)
    const account = config.accounts[role]
    const loginPage = new StaffLoginPage(page, base.origin)
    await loginPage.login({ ...account, tenant: config.tenant })
    assert.equal(String(decodeJwt(loginPage.lastAccessToken).tenantId), '1000000000000000007', '登录返回的学校并非日常沙箱')
    await loginPage.switchRole(account.roleLabel)
    await expect(page.locator('.uchip__role').first()).toContainText(account.roleLabel)
    loginPage.lastAccessToken = ''
    page.on('response', response => {
      const url = new URL(response.url())
      if (!url.pathname.startsWith(api + '/')) return
      const entry = { role, method: response.request().method(), path: url.pathname, httpStatus: response.status() }
      report.requests.push(entry)
      if (entry.method !== 'GET') businessResponses.push(entry)
    })
    sessions[role] = { page, context }
    return page
  }
  async function openBatch(page, reload = false) {
    const facts = Promise.all([waitRead(page, `${batchPath}/workbench`), waitRead(page, `${batchPath}/tasks`)])
    const navigation = reload ? page.reload() : page.goto(`${base.origin}/admin/academic-affairs/teaching-tasks/${config.batchId}?teachingTaskId=${config.taskId}`)
    const [[batch, tasks]] = await Promise.all([facts, navigation])
    assert.equal(batch.batchId, config.batchId, '读取到了其他教学任务批次')
    assert.ok(Array.isArray(tasks.items), '教学任务分页回执缺少任务行')
    const task = tasks.items.find(row => row.taskId === config.taskId)
    assert.ok(task && task.courseName === config.courseName && task.teachingClassName === config.teachingClassName, '任务身份与预置对象不一致')
    await expect(taskRow(page)).toHaveCount(1)
    return { batch, task }
  }
  async function openTeacher(page, reload = false) {
    const facts = waitRead(page, `${api}/teaching-tasks`, { taskId: config.taskId, mine: 'true' })
    const navigation = reload ? page.reload() : page.goto(`${base.origin}/admin/academic-affairs/teaching-tasks/teacher-confirm?taskId=${config.taskId}`)
    const [data] = await Promise.all([facts, navigation])
    await expect(page.getByRole('heading', { name: '教师任务确认', exact: true })).toBeVisible()
    assert.ok(Array.isArray(data.items), '教师任务分页回执缺少任务行')
    return data.items.find(row => row.taskId === config.taskId) || null
  }
  async function command(page, label, path, click, expectedPayload = {}) {
    const responsePromise = page.waitForResponse(response => response.request().method() === 'POST' && new URL(response.url()).pathname === path)
    const [response] = await Promise.all([responsePromise, click()])
    for (const [key, value] of Object.entries(expectedPayload)) assert.equal(response.request().postDataJSON()?.[key], value, '页面提交的业务对象或动作不一致')
    await dataOf(response)
    await expect(page.locator('.aa-a-receipt:not(.is-pending)')).toBeVisible({ timeout: 60_000 })
    report.steps.push({ label, received: true })
  }

  const college = await login('college')
  const initial = await openBatch(college)
  assert.ok(['DRAFT', 'RETURNED'].includes(initial.batch.status) && initial.batch.actions?.canAssign === true, '批次当前不可分配，未执行任何办理')
  assert.equal(initial.task.status, 'PENDING_ASSIGN', '验收任务应为待分配状态，禁止重复分配已办理任务')
  assert.ok(!initial.task.teacherKey, '该任务已有正式任课教师，停止验收')
  await taskRow(college).getByRole('button', { name: '分配教师', exact: true }).click()
  const assignDialog = college.getByRole('dialog', { name: '分配任课教师', exact: true })
  await assignDialog.getByRole('combobox').click()
  await assignDialog.locator('.app-remote-select__search-el').fill(config.teacherKey)
  const option = assignDialog.getByRole('option').filter({ hasText: config.teacherOptionLabel }).filter({ hasText: config.teacherKey })
  await expect(option).toHaveCount(1)
  await option.click()
  await expect(assignDialog.getByRole('button', { name: '确认分配', exact: true })).toBeEnabled()
  await assignDialog.getByRole('button', { name: '取消', exact: true }).click()
  await screenshot(college, '01-college-preflight')
  const teacher = await login('teacher')
  assert.equal(await openTeacher(teacher), null, '未分配任务不应提前出现在教师本人队列')
  const school = await login('school')
  await openBatch(school)
  await screenshot(school, '02-school-preflight')
  report.steps.push({ label: '三岗位正常登录、同对象和教师选择器已核对', received: true })

  if (execute) {
    await taskRow(college).getByRole('button', { name: '分配教师', exact: true }).click()
    await assignDialog.getByRole('combobox').click()
    await assignDialog.locator('.app-remote-select__search-el').fill(config.teacherKey)
    await expect(option).toHaveCount(1)
    await option.click()
    await command(college, '学院分配教师', `${taskPath}/assign`, () => assignDialog.getByRole('button', { name: '确认分配', exact: true }).click(), { teacherKey: config.teacherKey })
    let facts = await openBatch(college, true)
    assert.equal(facts.task.status, 'ASSIGNED'); assert.equal(facts.task.teacherKey, config.teacherKey)
    await screenshot(college, '03-assigned')
    const mine = await openTeacher(teacher, true)
    assert.ok(mine && mine.status === 'ASSIGNED' && mine.teacherKey === config.teacherKey, '任课教师未收到同一教学任务')
    await taskRow(teacher).getByRole('button', { name: '确认接受', exact: true }).click()
    await command(teacher, '教师本人确认', `${taskPath}/teacher-act`, () => teacher.getByRole('dialog', { name: '确认接受授课安排', exact: true }).getByRole('button', { name: '确认接受', exact: true }).click(), { action: 'CONFIRM' })
    assert.equal((await openTeacher(teacher, true))?.status, 'TEACHER_CONFIRMED')
    await screenshot(teacher, '04-teacher-confirmed')
    facts = await openBatch(college, true)
    assert.equal(facts.batch.actions?.canCollegeConfirm, true, '整批仍有阻断，不能学院确认')
    await command(college, '学院确认批次', `${batchPath}/college-confirm`, () => college.getByRole('button', { name: '学院确认', exact: true }).click())
    assert.equal((await openBatch(college, true)).batch.status, 'COLLEGE_CONFIRMED')
    await screenshot(college, '05-college-confirmed')
    facts = await openBatch(school, true)
    assert.equal(facts.batch.actions?.canAcademicReview, true, '校教务终审前置条件未满足')
    await school.getByRole('button', { name: '教务终审通过', exact: true }).click()
    await command(school, '校教务终审', `${batchPath}/review`, () => school.getByRole('dialog', { name: '确认教务终审通过', exact: true }).getByRole('button', { name: '确认通过', exact: true }).click(), { action: 'APPROVE' })
    facts = await openBatch(school, true)
    assert.equal(facts.batch.status, 'APPROVED'); assert.equal(facts.task.status, 'READY')
    await screenshot(school, '06-approved')
    assert.equal((await openTeacher(teacher, true))?.status, 'READY')
    await screenshot(teacher, '07-teacher-ready')
    assert.equal(businessResponses.length, 4, '业务写请求数量不等于本链四个正式动作')
  } else assert.equal(businessResponses.length, 0, '只读前置核验出现了业务写请求')
  report.passed = true
} catch (error) {
  report.error = redact(error.message)
  const lastSession = Object.values(sessions).at(-1)
  if (capture && lastSession) await capture(lastSession.page, 'failure').catch(() => {})
  process.exitCode = 1
} finally {
  for (const session of Object.values(sessions)) await session.context.close()
  await browser?.close()
  await mkdir(outputDir, { recursive: true })
  await writeFile(resolve(outputDir, 'result.json'), redact(JSON.stringify(report, null, 2)), 'utf8')
  console.log(report.passed ? `${report.mode}通过；结果已保存至忽略的验收目录。` : `验收停止：${report.error || '运行未完成'}；结果已保存至忽略的验收目录。`)
}
