import fs from 'node:fs/promises'
import path from 'node:path'
import process from 'node:process'
import { fileURLToPath } from 'node:url'
import { createHash } from 'node:crypto'

const root = fileURLToPath(new URL('../../', import.meta.url))
export const roles = {
  ADMIN: '学校管理员', ACADEMIC: '教务处', COLLEGE: '学院', TEACHER: '任课教师',
  COUNSELOR: '辅导员', AFFAIRS: '学工处', GRADUATION: '毕设管理',
  INTERNSHIP: '实习管理', LEADER: '校领导', STUDENT: '学生', ENTERPRISE: '企业联系人'
}
export const rolePatterns = {
  ADMIN: /^学校管理员/, ACADEMIC: /^(?:教务处管理员|教务老师)/,
  COLLEGE: /^学院管理员/, TEACHER: /^任课教师/,
  COUNSELOR: /^辅导员/, AFFAIRS: /^学工(?:处)?管理员/,
  GRADUATION: /^毕设管理员/, INTERNSHIP: /^(?:实习管理员|岗位实习管理员)/,
  LEADER: /^(?:校领导|校院领导)/
}
const authPaths = new Set([
  '/api/v1/auth/captcha',
  '/api/v1/auth/browser-login', '/api/v1/auth/browser-refresh',
  '/api/v1/auth/browser-switch-role', '/api/v1/auth/login', '/api/v1/auth/switch-role',
  '/api/v1/internship/enterprise-portal/auth/browser-login',
  '/api/v1/internship/enterprise-portal/auth/browser-refresh'
])
const mutatingReadPaths = new Set(['/api/v1/admin/message-campaigns/ops/reconcile'])

export function requestAllowed(method, address, origins) {
  const url = new URL(address)
  if (!origins.includes(url.origin)) return false
  if (mutatingReadPaths.has(url.pathname.replace(/\/$/, ''))) return false
  if (['GET', 'HEAD', 'OPTIONS'].includes(method)) return true
  return method === 'POST' && authPaths.has(url.pathname)
}

export function buildAssetPath(directory, pathname) {
  let decoded
  try { decoded = decodeURIComponent(pathname) } catch { return null }
  const target = path.resolve(directory, `.${decoded}`)
  const prefix = path.resolve(directory) + path.sep
  return target.toLowerCase().startsWith(prefix.toLowerCase()) ? target : null
}

async function fulfillBuildAsset(route, directory) {
  const request = route.request()
  const url = new URL(request.url())
  if (!['GET', 'HEAD'].includes(request.method()) || url.pathname.startsWith('/api/')) return false
  let file = buildAssetPath(directory, url.pathname)
  if (!file || !(await fs.stat(file).catch(() => null))?.isFile()) {
    if (request.resourceType() !== 'document') {
      await route.fulfill({ status: 404, body: '候选构建中不存在此资源' })
      return true
    }
    file = path.join(directory, 'index.html')
  }
  const realFile = await fs.realpath(file)
  const prefix = await fs.realpath(directory) + path.sep
  if (!realFile.toLowerCase().startsWith(prefix.toLowerCase())) throw new Error('候选资源超出构建目录')
  const types = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json',
    '.svg': 'image/svg+xml', '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.webp': 'image/webp',
    '.ico': 'image/x-icon', '.woff': 'font/woff', '.woff2': 'font/woff2', '.ttf': 'font/ttf', '.mp4': 'video/mp4' }
  await route.fulfill({ status: 200, contentType: types[path.extname(realFile)] || 'application/octet-stream',
    body: request.method() === 'HEAD' ? '' : await fs.readFile(realFile) })
  return true
}

export function flagText(text) {
  const flags = []
  const patterns = {
    '英文代码': /\b(?:[A-Z]{2,}_[A-Z0-9_]+|[a-z]+(?:[A-Z][a-z0-9]*)+)\b/g,
    '长数字编号（需区分学号及业务单号）': /\b\d{15,}\b/g,
    '开发词': /回读|原命令|只读核对|正式事实|真值|服务端|后端|前端|接口|数据库|字段|枚举|权限码|令牌|幂等|原子|持久化|链路|闭环|兜底|降级|投影|契约|快照版本|指纹|预检|阻断|占位|待施工/g
  }
  for (const [kind, regex] of Object.entries(patterns)) {
    const matches = [...new Set(text.match(regex) || [])]
    if (matches.length) flags.push({ kind, matches })
  }
  const counts = new Map()
  for (const line of text.split(/[\n。！？]+/).map(s => s.trim()).filter(s => s.length >= 6)) {
    counts.set(line, (counts.get(line) || 0) + 1)
  }
  const repeated = [...counts].filter(([, n]) => n > 1).map(([sentence, count]) => ({ sentence, count }))
  if (repeated.length) flags.push({ kind: '同句重复（人工复核）', matches: repeated })
  return flags
}

export async function inventory() {
  const read = async p => fs.readFile(path.join(root, p), 'utf8')
  const contract = JSON.parse(await read('shared/contracts/navigation-surface-contract.json'))
  const items = contract.surfaces.filter(s => !s.hidden && !s.disabled).map(s => ({
    client: 'staff', page: s.label, route: s.path, source: s.surfaceKey,
    platformOnly: s.platformOnly, widths: [1440]
  }))
  for (const route of ['/', '/login', '/platform-login', '/login?forcePasswordChange=1', '/platform-login?forcePasswordChange=1', '/security/401', '/security/403', '/security/419', '/security/500', '/ui-audit-missing-page']) {
    items.push({ client: 'staff', page: route, route, widths: [1440], public: true })
  }
  for (const item of [
    { page: '账号与安全（含本人手机号）', route: '/workbench', view: 'account-security' },
    { page: '顶栏账户与身份', route: '/workbench', view: 'account-menu' },
    { page: '工作台外观设置', route: '/workbench', view: 'appearance' },
    { page: '顶栏功能搜索', route: '/workbench', view: 'function-search' },
    { page: '成绩录入首条任务详情', route: '/admin/academic-affairs/grade-entry', view: 'first-grade-task' },
    { page: '成绩录入首条任务截止时间', route: '/admin/academic-affairs/grade-entry', view: 'first-grade-deadline' },
    { page: '成绩录入首条任务动态成绩项', route: '/admin/academic-affairs/grade-entry', view: 'first-grade-components' },
    { page: '班级课表首个可选班级', route: '/admin/academic-affairs/schedule/class', view: 'first-class-schedule' },
    { page: '课表导出选择首个班级', route: '/admin/academic-affairs/schedule/export', view: 'first-export-selection' },
    { page: '课表调整记录首条实施信息', route: '/admin/academic-affairs/schedule/adjustments', view: 'first-schedule-audit-technical' },
    { page: '首个课表批次详情', route: '/admin/academic-affairs/schedule', view: 'first-schedule-batch' },
    { page: '课表批次创建表单', route: '/admin/academic-affairs/schedule', view: 'schedule-create-form' },
    { page: '课表发布首个批次信息', route: '/admin/academic-affairs/schedule/publish', view: 'first-publish-batch' },
    { page: '课表维护首条版本实施信息', route: '/admin/academic-affairs/schedule', view: 'first-schedule-batch-technical' },
    { page: '课表发布首条版本实施信息', route: '/admin/academic-affairs/schedule/publish', view: 'first-publish-batch-technical' },
    { page: '课表发布首条批次条件检查', route: '/admin/academic-affairs/schedule/publish', view: 'first-publish-check' },
    { page: '首个编制中批次的首个班级课表', route: '/admin/academic-affairs/schedule', view: 'first-draft-class-schedule' },
    { page: '首个编制中批次的空白排课表单', route: '/admin/academic-affairs/schedule', view: 'first-draft-schedule-form' },
    { page: '找回密码', route: '/login', view: 'password-reset', public: true },
    { page: '我的消息首条正文', route: '/admin/messages/inbox', view: 'first-message' },
    { page: '审批模板首条详情', route: '/admin/approval/templates', view: 'first-template' },
    { page: '登录后访问不存在的页面', route: '/ui-audit-missing-page', view: 'authenticated-missing' }
  ]) items.push({ client: 'staff', widths: [1440], ...item })
  for (const [segment, label] of [['teacher', '教师'], ['student', '学生'], ['room', '教室'], ['teaching-class', '教学班'], ['week', '周'], ['semester', '学期']]) {
    items.push({ client: 'staff', widths: [1440], page: `${label}课表首个查询结果`, route: `/admin/academic-affairs/schedule/${segment}`, view: 'first-schedule-selection' })
  }
  for (const [type, name] of [['LEAVE', '请假'], ['AA_STATUS_CHANGE', '学籍异动'], ['AA_GRADE_TASK', '成绩审核']]) {
    items.push({ client: 'staff', widths: [1440], page: `${name}审批首条业务详情`,
      route: '/admin/approval/todos/:taskId', view: `approval-${type}`, listQuery: `?bizType=${type}` })
  }
  for (const file of ['approval/approval.routes.js', 'messageCenter/message-center.routes.js']) {
    const routes = (await import(new URL(`../../frontend/src/modules/${file}`, import.meta.url))).default
    const visit = (definitions, parent = '') => {
      for (const entry of definitions) {
        const route = entry.path.startsWith('/') ? entry.path : `${parent}/${entry.path}`.replace(/\/$/, '')
        if (entry.children) visit(entry.children, route)
        else if (entry.component && !entry.redirect && !items.some(item => item.client === 'staff' && item.route === route && !item.view)) {
          items.push({ client: 'staff', page: entry.meta?.title || route, route, widths: [1440], routeSource: file })
        }
      }
    }
    visit(routes)
  }
  for (const [client, folder, widths] of [
    ['student', 'student-portal', [1440, 390]], ['enterprise', 'enterprise-portal', [1440]]
  ]) {
    const source = await read(`${folder}/src/router/index.js`)
    for (const match of source.matchAll(/\{\s*path:\s*['"]([^'"]+)['"][^\n]*component:\s*\(\)\s*=>\s*import\(['"]([^'"]+)/g)) {
      items.push({ client, page: match[2], route: '/' + match[1].replace(/^\//, ''), widths, public: match[1] === '/login' })
    }
  }
  const mini = JSON.parse(await read('miniapp/src/pages.json'))
  for (const entry of [...mini.pages, ...(mini.subPackages || []).flatMap(p => p.pages.map(s => ({ ...s, path: `${p.root}/${s.path}` })))]) {
    items.push({ client: 'mini', page: entry.style?.navigationBarTitleText || entry.path, route: `/#/${entry.path}`, widths: [390], public: entry.path.startsWith('pages/login/') })
  }
  return items
}

export function detailRoutePattern(route) {
  return new RegExp('^' + route.split('/').map(part => part.startsWith(':') ? '[^/?#]+' : part.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('/') + '(?:[?#]|$)')
}

export function captureStatus({ expectedUrl, actualUrl, httpStatus, apiFailures = [], settled }) {
  const expected = new URL(expectedUrl)
  const actual = new URL(actualUrl)
  if (actual.pathname.includes('/login') && !expected.pathname.includes('/login')) return '登录失效，非目标页面'
  if ([401, 403].includes(httpStatus) || apiFailures.some(item => [401, 403].includes(item.status))) return '权限受限，已留证'
  if (httpStatus >= 400 || apiFailures.length) return '页面或数据加载失败，已留证'
  const requestedQueryMatches = [...expected.searchParams].every(([key, value]) => actual.searchParams.get(key) === value)
  if (actual.origin !== expected.origin || actual.pathname !== expected.pathname || actual.hash !== expected.hash || !requestedQueryMatches) return '页面已跳转，非目标页面'
  if (!settled) return '页面加载未稳定，已留证'
  return '已截图，待人工通读'
}

export function renderReport(records) {
  const cell = value => String(value ?? '').replaceAll('|', '／').replaceAll('\n', ' ').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
  return '# 全页面巡检记录\n\n页面条目和角色检查次数不等于审计通过页数。\n\n|页面|入口|角色|宽度|状态|截图|自动标记|人工结论|\n|---|---|---|---|---|---|---|---|\n' + records.map(r => `|${cell(r.page)}|${cell(r.route)}|${cell(r.role)}|${r.width}|${cell(r.status)}|${(r.screenshots || (r.screenshot ? [r.screenshot] : [])).map((file, i) => `[查看截图${i ? i + 1 : ''}](${file})`).join('、') || '无'}|${cell(r.flags.map(f => f.kind).join('、'))}|${cell(r.conclusion)}${r.previousReview ? `；历史结论（当前截图仍需复核）：${cell(r.previousReview.conclusion)}` : ''}|`).join('\n')
}

export function mergeAuditRuns(runs) {
  const latest = new Map()
  for (const run of [...runs].sort((a, b) => a.name.localeCompare(b.name))) {
    for (const record of run.records) {
      const role = record.public ? '未登录' : record.role
      const key = JSON.stringify([record.client, record.route, record.view || '', role, record.width])
      const previous = latest.get(key)
      latest.set(key, {
        ...record, role, sourceRun: run.name, runtimeSource: run.scope?.runtimeSource || '运行版本未记录',
        previousReview: previous?.conclusion && previous.conclusion !== '未人工审阅'
          ? { sourceRun: previous.sourceRun, conclusion: previous.conclusion } : previous?.previousReview,
        screenshot: record.screenshot ? `${run.name}/${record.screenshot}` : null,
        screenshots: (record.screenshots || (record.screenshot ? [record.screenshot] : [])).map(file => `${run.name}/${file}`),
        text: record.text ? `${run.name}/${record.text}` : null
      })
    }
  }
  return [...latest.values()]
}

async function summarizeReports() {
  const directory = path.join(root, 'e2e/runtime/ui-audit')
  const runs = [], unreadable = []
  for (const entry of await fs.readdir(directory, { withFileTypes: true })) {
    if (!entry.isDirectory() || !/^\d{4}-\d{2}-\d{2}T/.test(entry.name)) continue
    try {
      const report = JSON.parse((await fs.readFile(path.join(directory, entry.name, 'report.json'), 'utf8')).replace(/^\uFEFF/, ''))
      runs.push({ ...report, name: entry.name })
    } catch { unreadable.push(entry.name) }
  }
  const records = mergeAuditRuns(runs)
  const summary = { runs: runs.length, records: records.length, captured: records.filter(r => r.screenshot).length,
    withHumanConclusion: records.filter(r => r.conclusion && r.conclusion !== '未人工审阅').length,
    withPreviousReview: records.filter(r => r.previousReview).length, unreadable }
  await fs.writeFile(path.join(directory, '总报告.json'), JSON.stringify({ summary, records }, null, 2))
  await fs.writeFile(path.join(directory, '总报告.md'), `# 界面文案巡检总报告\n\n按端、入口、角色与宽度合并各轮最新记录；截图数量不代表验收通过。\n\n已读取 ${summary.runs} 轮记录，${summary.records} 项检查中 ${summary.captured} 项有截图，${summary.withHumanConclusion} 项最新截图有人工结论，${summary.withPreviousReview} 项保留历史人工结论待复核。\n\n运行版本须查看每条记录的来源，主目录基线不是候选修改后验收。${unreadable.length ? `另有 ${unreadable.length} 轮报告尚未完成写入或无法读取。` : ''}\n\n` + renderReport(records))
  console.log(JSON.stringify(summary))
}

export function scrollOffsets(height, viewport) {
  if (viewport <= 0 || height <= viewport) return []
  const offsets = []
  for (let top = Math.max(1, viewport - 100); top < height - viewport; top += Math.max(1, viewport - 100)) offsets.push(top)
  offsets.push(height - viewport)
  return offsets
}

export function chooseScrollRegion(regions) {
  const visible = regions.filter(region => region.visible && region.viewport > 0)
  const overlays = visible.filter(region => region.dialog)
  return (overlays.length ? overlays : visible.filter(region => region.viewport > 200 && region.height > region.viewport + 1))
    .sort((a, b) => b.area - a.area)[0]
}

async function captureScrollContent(page, out, id) {
  const files = [`${id}.png`]
  const regions = page.locator('dialog[open], [role="dialog"], .uchip__menu, .bpl-cmdk__panel, main, [role="main"], .uni-scroll-view')
  const candidates = await regions.evaluateAll(nodes => nodes.map((node, index) => ({ index, height: node.scrollHeight, viewport: node.clientHeight, area: node.clientWidth * node.clientHeight, dialog: node.matches('dialog, [role="dialog"], .uchip__menu, .bpl-cmdk__panel'), visible: !!node.getClientRects().length })))
  const region = chooseScrollRegion(candidates)
  if (!region) {
    await page.screenshot({ path: path.join(out, files[0]), fullPage: true, animations: 'disabled' })
    return files
  }
  const locator = regions.nth(region.index)
  const previousTop = await locator.evaluate(node => node.scrollTop)
  try {
    await locator.evaluate(node => { node.scrollTop = 0 })
    await page.screenshot({ path: path.join(out, files[0]), fullPage: true, animations: 'disabled' })
    for (const top of scrollOffsets(region.height, region.viewport)) {
      await locator.evaluate((node, value) => { node.scrollTop = value }, top)
      const file = `${id}-part${files.length + 1}.png`
      await page.screenshot({ path: path.join(out, file), fullPage: true, animations: 'disabled' })
      files.push(file)
    }
  } finally { await locator.evaluate((node, value) => { node.scrollTop = value }, previousTop) }
  return files
}

async function openDetailFromList(page, base, route, listQuery = '') {
  const prefix = route.split('/:')[0]
  if (!prefix || prefix === '/') throw new Error('缺少明确列表入口')
  await page.goto(base + prefix + listQuery)
  await page.waitForLoadState('networkidle')
  if (listQuery && await page.locator('.af__field').filter({ has: page.getByText('业务类型', { exact: true }) }).locator('select').inputValue() !== new URLSearchParams(listQuery).get('bizType')) throw new Error('列表业务筛选尚未生效')
  const first = page.locator('tbody tr, [role="rowgroup"] [role="row"], .el-table__row').first()
  if (!await first.count()) throw new Error('列表没有可核验的首条记录')
  const target = detailRoutePattern(new URL(base).pathname.replace(/\/$/, '') + route)
  const links = first.locator('a[href]')
  for (let i = 0; i < await links.count(); i++) {
    const link = links.nth(i)
    const url = new URL(await link.getAttribute('href'), page.url())
    const text = (await link.innerText()).trim()
    if (url.origin === new URL(base).origin && target.test(url.pathname) && !/提交|审批|删除|导出|下载|启用|停用/.test(text)) {
      await link.click()
      await page.waitForURL(url => target.test(url.pathname))
      return
    }
  }
  const detailButton = route === '/admin/approval/todos/:taskId' ? /^(查看|查看详情|详情|办理)$/ : /^(查看|查看详情|详情)$/
  const button = first.getByRole('button', { name: detailButton }).first()
  if (!await button.count()) throw new Error('首条记录没有只读详情入口')
  await button.click()
  await page.waitForURL(url => target.test(url.pathname))
}

async function openAuditView(page, view) {
  if (['first-draft-class-schedule', 'first-draft-schedule-form'].includes(view)) {
    const row = page.locator('tbody tr').filter({ has: page.getByText('编制中', { exact: true }) }).first()
    await row.getByRole('button', { name: '继续排课', exact: true }).click()
    await page.locator('.aa-batch-truth').waitFor({ state: 'visible' })
    const picker = page.locator('.aa-filter .app-remote-select').first()
    await picker.getByRole('combobox').click()
    await picker.locator('[role="option"]:not([aria-disabled="true"])').first().click()
    await page.getByRole('button', { name: '载入课表', exact: true }).click()
    await page.waitForURL(url => !!url.searchParams.get('classId'))
    const emptyCell = page.locator('.aa-grid__cell.is-editable').filter({ hasNot: page.locator('.aa-grid__item') }).first()
    await emptyCell.waitFor({ state: 'visible' })
    if (view === 'first-draft-schedule-form') {
      // No task is selected, so opening the form cannot trigger the POST preflight.
      await emptyCell.click()
      await page.getByRole('dialog').waitFor({ state: 'visible' })
    }
    return page.url()
  } else if (view === 'first-publish-check') {
    // This opens the GET-only summary; the separate confirmation button is never clicked.
    await page.locator('tbody tr').first().getByRole('button', { name: /^检查并(正式发布|预发布)$/ }).click()
    await page.locator('.aa-gate-grid').waitFor({ state: 'visible' })
  } else if (['first-publish-batch', 'first-publish-batch-technical'].includes(view)) {
    await page.locator('tbody tr').first().locator('td').first().getByRole('button').click()
    await page.locator('.aa-truth-card').waitFor({ state: 'visible' })
    if (view.endsWith('-technical')) await page.locator('.aa-truth-card details summary').click()
    return page.url()
  } else if (view === 'schedule-create-form') {
    await page.getByRole('button', { name: /创建排课批次/ }).click()
    await page.getByText('新建课表批次', { exact: true }).waitFor({ state: 'visible' })
  } else if (['first-schedule-batch', 'first-schedule-batch-technical'].includes(view)) {
    await page.locator('tbody tr').first().getByRole('button', { name: /^(继续排课|查看已发布课表|查看课表记录)$/ }).click()
    await page.waitForURL(url => /\/schedule\/[^/]+\/(edit|views)$/.test(url.pathname))
    if (new URL(page.url()).pathname.endsWith('/edit')) await page.locator('.aa-batch-truth').waitFor({ state: 'visible' })
    if (view.endsWith('-technical')) await page.locator('.aa-batch-truth details summary').click()
    return page.url()
  } else if (view === 'first-schedule-audit-technical') {
    await page.locator('tbody tr').first().locator('details summary').click()
    await page.locator('tbody tr').first().locator('details[open]').waitFor({ state: 'visible' })
  } else if (view === 'first-export-selection') {
    const picker = page.locator('.app-remote-select').filter({ has: page.getByRole('combobox').filter({ hasText: '搜索班级名称' }) })
    await picker.getByRole('combobox').click()
    await picker.locator('[role="option"]:not([aria-disabled="true"])').first().click()
  } else if (view === 'first-schedule-selection') {
    const startUrl = new URL(page.url())
    const segment = startUrl.pathname.split('/').at(-1)
    const [placeholder, keyword] = {
      teacher: ['搜索教师姓名/工号', '老师'], student: ['按姓名/学号检索学生', '学'],
      room: ['搜索楼栋/教室编号', '楼'], 'teaching-class': ['按教学班名称/课程名搜索', '班'],
      week: ['搜索班级名称', '班'], semester: ['搜索班级名称', '班']
    }[segment]
    const picker = page.locator('.app-remote-select').filter({ has: page.getByRole('combobox').filter({ hasText: placeholder }) })
    await picker.getByRole('combobox').click()
    await picker.locator('.app-remote-select__spinner').waitFor({ state: 'hidden' })
    if (!await picker.getByRole('option').count()) await picker.locator('input').fill(keyword)
    await picker.locator('[role="option"]:not([aria-disabled="true"])').first().click()
    if (!['week', 'semester'].includes(segment)) {
      await page.waitForURL(url => url.origin === startUrl.origin && url.pathname.startsWith(`${startUrl.pathname}/`) && url.pathname.slice(startUrl.pathname.length + 1).length > 0)
      return page.url()
    }
  } else if (view === 'first-class-schedule') {
    const picker = page.locator('.aa-filter__item').filter({ hasText: /^\s*班级/ }).locator('.app-remote-select')
    await picker.getByRole('combobox').click()
    await picker.locator('.app-remote-select__spinner').waitFor({ state: 'hidden' })
    if (!await picker.getByRole('option').count()) await picker.getByPlaceholder('按班级名称搜索', { exact: true }).fill('班')
    await picker.locator('[role="option"]:not([aria-disabled="true"])').first().click()
    await page.waitForURL(url => /\/schedule\/class\/[^/]+$/.test(url.pathname))
    return page.url()
  } else if (['first-grade-task', 'first-grade-deadline', 'first-grade-components'].includes(view)) {
    await page.locator('.aa-my-task-item').first().getByRole('button', { name: '进入', exact: true }).click()
    await page.locator('.aa-my-tasks').waitFor({ state: 'hidden' })
    await page.locator('.aa-mode-switch').waitFor({ state: 'visible' })
    await page.waitForFunction(() => [...document.querySelectorAll('[aria-busy="true"]')].every(node => !node.getClientRects().length))
    if (view === 'first-grade-deadline') await page.locator('.aa-task-settings summary').click()
    if (view === 'first-grade-components') {
      await page.locator('.aa-mode-switch').getByRole('button', { name: '动态成绩项', exact: true }).click()
      await page.locator('.aa-mode.is-active').filter({ hasText: '动态成绩项' }).waitFor({ state: 'visible' })
    }
  } else if (view === 'account-menu' || view === 'appearance') {
    await page.getByTitle('查看账号与切换身份', { exact: true }).click()
    await page.getByRole('region', { name: '账户与身份' }).waitFor({ state: 'visible' })
    await page.locator('.uchip__hint').filter({ hasText: '正在加载可用身份' }).waitFor({ state: 'hidden' })
    if (view === 'appearance') {
      await page.getByRole('button', { name: /^外观设置/ }).click()
      await page.getByRole('dialog').waitFor({ state: 'visible' })
    }
  } else if (view === 'function-search') {
    await page.locator('.bpl-cmdk--fn input').fill('审批')
    await page.locator('.bpl-cmdk--fn .bpl-cmdk__panel').waitFor({ state: 'visible' })
    await page.locator('.bpl-cmdk--fn .bpl-cmdk__grp').filter({ hasText: /^功能\/页面$/ }).waitFor({ state: 'visible' })
    await page.locator('.bpl-cmdk--fn .bpl-cmdk__loading').waitFor({ state: 'hidden' })
  } else if (view === 'account-security') {
    await page.getByTitle('查看账号与切换身份', { exact: true }).click()
    await page.getByRole('button', { name: /^账号安全/ }).click()
    await page.getByRole('dialog').waitFor({ state: 'visible' })
  } else if (view === 'password-reset') {
    await page.getByRole('button', { name: '忘记密码', exact: true }).click()
    await page.getByRole('dialog').waitFor({ state: 'visible' })
  } else if (view === 'first-message') {
    await page.locator('.mc-list__item').first().click()
    await page.locator('.mc-detail__body').waitFor({ state: 'visible' })
  } else if (view === 'first-template') {
    await page.locator('tbody tr').first().getByRole('button', { name: '查看', exact: true }).click()
    await page.getByRole('dialog').waitFor({ state: 'visible' })
  }
}

async function main() {
  const entries = await inventory()
  const out = path.join(root, 'e2e/runtime/ui-audit', new Date().toISOString().replace(/[:.]/g, '-'))
  await fs.mkdir(out, { recursive: true })
  const bases = {
    staff: process.env.UI_AUDIT_STAFF_URL || 'http://127.0.0.1:5173',
    student: process.env.UI_AUDIT_STUDENT_URL || 'http://127.0.0.1:5199/portal',
    enterprise: process.env.UI_AUDIT_ENTERPRISE_URL || 'http://127.0.0.1:5202/enterprise',
    mini: process.env.UI_AUDIT_MINI_URL || 'http://127.0.0.1:5188'
  }
  const origins = [...new Set([...Object.values(bases), process.env.UI_AUDIT_API_URL || 'http://127.0.0.1:8000'].map(s => {
    const url = new URL(s)
    if (!['127.0.0.1', 'localhost', '[::1]'].includes(url.hostname)) throw new Error('巡检只允许本机地址')
    return url.origin
  }))]
  const records = []
  const allBlocked = []
  let frontendBuild = null
  if (process.env.UI_AUDIT_FRONTEND_BUILD === 'true') {
    frontendBuild = path.join(out, 'frontend-build')
    await fs.access(path.join(root, 'frontend/dist/index.html'))
    await fs.cp(path.join(root, 'frontend/dist'), frontendBuild, { recursive: true, errorOnExist: true, force: false })
  }
  const scope = {
    roles: process.env.UI_AUDIT_ROLES?.split(',') || Object.keys(roles),
    clients: process.env.UI_AUDIT_CLIENTS?.split(',') || Object.keys(bases),
    routes: process.env.UI_AUDIT_ROUTES?.split(',') || null,
    views: process.env.UI_AUDIT_VIEWS?.split(',') || null,
    runtimeSource: process.env.UI_AUDIT_SOURCE_LABEL || '尚未核验运行代码目录',
    frontendBuild: frontendBuild ? {
      directory: 'frontend-build',
      indexSha256: createHash('sha256').update(await fs.readFile(path.join(frontendBuild, 'index.html'))).digest('hex'),
      apiResponsesReplaced: false
    } : null
  }
  if (scope.roles.some(role => !Object.hasOwn(roles, role)) || scope.clients.some(client => !Object.hasOwn(bases, client))) throw new Error('巡检范围无效')
  const saveReport = async () => {
    await fs.writeFile(path.join(out, 'report.json'), JSON.stringify({ scope, records, blocked: allBlocked }, null, 2))
    await fs.writeFile(path.join(out, 'report.md'), renderReport(records) + `\n\n运行版本：${scope.runtimeSource}\n本轮限定角色、端和路径详见 report.json；未采集的页面不视为通过。\n`)
  }
  const notRun = process.argv.includes('--not-run')
  const browser = notRun ? null : await (await import('@playwright/test')).chromium.launch()
  const newContext = async (blocked, client) => {
    const context = await browser?.newContext({ serviceWorkers: 'block', acceptDownloads: false })
    if (!context) return null
    await context.routeWebSocket('**/*', socket => socket.close())
    await context.route('**/*', async route => {
      const req = route.request()
      if (requestAllowed(req.method(), req.url(), origins)) {
        if (frontendBuild && client === 'staff' && new URL(req.url()).origin === new URL(bases.staff).origin
          && await fulfillBuildAsset(route, frontendBuild)) return
        return route.continue()
      }
      blocked.push({ method: req.method(), path: new URL(req.url()).pathname })
      return route.abort('blockedbyclient')
    })
    return context
  }
  try {
    for (const [role, roleLabel] of Object.entries(roles)) {
      if (!scope.roles.includes(role)) continue
      const clients = role === 'STUDENT' ? ['student', 'mini'] : role === 'ENTERPRISE' ? ['enterprise'] : ['staff', 'mini']
      for (const client of clients) {
        if (!scope.clients.includes(client)) continue
        const pages = entries.filter(s => s.client === client && (!scope.routes || scope.routes.includes(s.route)) && (!scope.views || scope.views.includes(s.view || 'page')) && (client !== 'mini' || !s.route.includes(role === 'STUDENT' ? '/teacher/' : '/student/')))
        const blocked = []
        const context = await newContext(blocked, client)
        const page = await context?.newPage()
        page?.setDefaultTimeout(15000)
        let unavailable = ''
        let loginStage = '登录'
        let loginDiagnostic = null
        const username = process.env[`UI_AUDIT_${role}_USERNAME`]
        const password = process.env[`UI_AUDIT_${role}_PASSWORD`]
        if (notRun) unavailable = '未执行：本轮服务启动被平台策略阻止，仅生成静态清单'
        else if (!username || !password) unavailable = '未执行：缺少该角色的环境变量凭据'
        else {
          try {
            const account = { username, password, tenant: 'sandbox-school' }
            if (client === 'staff' || client === 'student') {
              const { StaffLoginPage, StudentLoginPage } = await import('../pages/login.page.mjs')
              const login = client === 'staff' ? new StaffLoginPage(page, bases[client]) : new StudentLoginPage(page, bases[client])
              await login.login(account)
              if (client === 'staff') {
                loginStage = '身份切换或核验'
                const rolePattern = rolePatterns[role]
                await login.switchRole(rolePattern)
                if (!rolePattern.test(await login.currentRoleText())) throw new Error('角色未核实')
              }
            } else if (client === 'mini') {
              const { loginMiniH5 } = await import('../lib/miniapp-login.mjs')
              await loginMiniH5(page, { baseUrl: bases.mini, entry: role === 'STUDENT' ? 'student' : 'teacher', account })
              if (role !== 'STUDENT') {
                loginStage = '移动端身份切换或核验'
                await page.goto(`${bases.mini}/#/pages/role-switch/index`)
                const roleName = process.env[`UI_AUDIT_${role}_MINI_ROLE_LABEL`] || roleLabel
                const identity = page.locator('.rs__item').filter({ has: page.getByText(roleName, { exact: true }) })
                await identity.waitFor({ state: 'visible' })
                await page.locator('.rs__item.is-current').waitFor({ state: 'visible' })
                if (!(await identity.getAttribute('class'))?.includes('is-current')) {
                  await identity.click()
                  await page.waitForURL(/pages\/teacher\/workbench\/index/)
                  await page.goto(`${bases.mini}/#/pages/role-switch/index`)
                }
                await page.locator('.rs__item.is-current').filter({ has: page.getByText(roleName, { exact: true }) }).waitFor({ state: 'visible' })
              }
            } else {
              await page.goto(`${bases.enterprise}/login`)
              await page.getByLabel('学校编码', { exact: true }).fill(account.tenant)
              await page.getByLabel('手机号或登录账号', { exact: true }).fill(username)
              await page.getByLabel('密码', { exact: true }).fill(password)
              await page.getByRole('button', { name: '登录', exact: true }).click()
              await page.waitForURL(url => !url.pathname.endsWith('/login'))
            }
            loginStage = '登录后页面加载'
            await page.waitForLoadState('networkidle', { timeout: 15000 })
          } catch {
            unavailable = `未执行：${loginStage}未完成；需检查环境及账号，不重置密码`
            loginDiagnostic = `login-failed-${role}-${client}.png`
            try { await page.screenshot({ path: path.join(out, loginDiagnostic), fullPage: true, mask: [page.locator('input')] }) }
            catch { loginDiagnostic = null }
          }
        }
        for (const item of pages) for (const width of item.widths) {
          const record = { ...item, role: roleLabel, width, screenshot: null, text: null, flags: [], conclusion: '未人工审阅', status: unavailable || '待检查', loginDiagnostic }
          records.push(record)
          if (notRun || (unavailable && !item.public)) continue
          if (item.platformOnly) { record.status = '未执行：需平台正常账号'; continue }
          const publicContext = item.public ? await newContext(blocked, client) : null
          const capturePage = publicContext ? await publicContext.newPage() : page
          capturePage.setDefaultTimeout(15000)
          const apiFailures = []
          const recordResponse = response => {
            const url = new URL(response.url())
            if (url.pathname.startsWith('/api/') && response.status() >= 400) apiFailures.push({ path: url.pathname, status: response.status() })
          }
          const recordFailure = request => {
            const url = new URL(request.url())
            if (url.pathname.startsWith('/api/')) apiFailures.push({ path: url.pathname, status: null })
          }
          capturePage.on('response', recordResponse)
          capturePage.on('requestfailed', recordFailure)
          try {
            await capturePage.setViewportSize({ width, height: 1000 })
            const previousUrl = capturePage.url()
            const previousText = client === 'mini' && previousUrl !== 'about:blank' ? await capturePage.locator('body').innerText() : null
            const response = item.route.includes(':')
              ? await openDetailFromList(capturePage, bases[client], item.route, item.listQuery)
              : await capturePage.goto(bases[client] + item.route)
            let expectedUrl = item.route.includes(':') ? capturePage.url() : bases[client] + item.route
            if (client === 'staff' && role === 'TEACHER' && item.route === '/admin/academic-affairs/schedule/teacher') {
              expectedUrl += `/${encodeURIComponent(username)}`
            }
            let settled = true
            if (previousText !== null && previousUrl !== expectedUrl) {
              try { await capturePage.waitForFunction(oldText => document.body.innerText !== oldText, previousText, { timeout: 15000 }) }
              catch { settled = false }
            }
            try { await capturePage.waitForLoadState('networkidle', { timeout: 15000 }) }
            catch { settled = false }
            if (item.view) expectedUrl = await openAuditView(capturePage, item.view) || expectedUrl
            try {
              await capturePage.waitForFunction(() => [...document.querySelectorAll('[aria-busy="true"], .el-loading-mask, .mgs-loading, .ts-empty, .phone-self [role="status"]')].every(node =>
                !node.getClientRects().length || getComputedStyle(node).visibility === 'hidden'
                || (node.matches('.ts-empty') && !node.textContent.trim().startsWith('正在加载'))
                || (node.matches('.phone-self [role="status"]') && !node.textContent.trim().startsWith('正在办理'))
              ), null, { timeout: 15000 })
            } catch { settled = false }
            try { await capturePage.waitForLoadState('networkidle', { timeout: 15000 }) }
            catch { settled = false }
            const text = await capturePage.locator('body').innerText()
            const id = String(records.length).padStart(5, '0')
            record.screenshots = await captureScrollContent(capturePage, out, id)
            record.screenshot = `${id}.png`
            await fs.writeFile(path.join(out, `${id}.txt`), text)
            record.text = `${id}.txt`
            record.flags = flagText(text)
            const longNotes = await capturePage.locator('p, small, [class*="hint"], [class*="desc"], [class*="note"]').evaluateAll(nodes => nodes.filter(n => {
              const style = getComputedStyle(n)
              return n.getClientRects().length && n.textContent.trim() && n.getBoundingClientRect().height > (parseFloat(style.lineHeight) || parseFloat(style.fontSize) * 1.5) * 2.1
            }).map(n => n.innerText).filter(Boolean))
            if (longNotes.length) record.flags.push({ kind: '超过两行的说明候选', matches: longNotes })
            record.apiFailures = apiFailures
            record.status = captureStatus({ expectedUrl, actualUrl: capturePage.url(), httpStatus: response?.status(), apiFailures, settled })
          } catch (error) {
            record.status = '未完成：页面加载、详情入口或截图失败'
            record.failureReason = String(error.message || error.name).split('\n')[0].slice(0, 400)
            record.diagnostic = `failed-${String(records.length).padStart(5, '0')}.png`
            try { await capturePage.screenshot({ path: path.join(out, record.diagnostic), fullPage: true, animations: 'disabled', mask: [capturePage.locator('input')] }) }
            catch { record.diagnostic = null }
          }
          finally {
            capturePage.off('response', recordResponse)
            capturePage.off('requestfailed', recordFailure)
            record.apiFailures = apiFailures
            allBlocked.push(...blocked.splice(0).map(entry => ({ ...entry, role: roleLabel, client })))
            await publicContext?.close()
            await saveReport()
          }
        }
        allBlocked.push(...blocked.map(entry => ({ ...entry, role: roleLabel, client })))
        await context?.close()
      }
    }
  } finally {
    await browser?.close()
    await saveReport()
  }
  console.log(JSON.stringify({ report: out, inventory: entries.length, checks: records.length, captured: records.filter(r => r.screenshot).length }))
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  if (process.argv.includes('--summary')) await summarizeReports()
  else await main()
}
