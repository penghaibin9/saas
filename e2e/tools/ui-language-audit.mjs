import fs from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = fileURLToPath(new URL('../../', import.meta.url))
export const roles = {
  ADMIN: '学校管理员', ACADEMIC: '教务处', COLLEGE: '学院', TEACHER: '任课教师',
  COUNSELOR: '辅导员', AFFAIRS: '学工处', GRADUATION: '毕设管理',
  INTERNSHIP: '实习管理', LEADER: '校领导', STUDENT: '学生', ENTERPRISE: '企业联系人'
}
const authPaths = new Set([
  '/api/v1/auth/browser-login', '/api/v1/auth/browser-refresh',
  '/api/v1/auth/browser-switch-role', '/api/v1/auth/login', '/api/v1/auth/switch-role',
  '/api/v1/internship/enterprise-portal/auth/browser-login',
  '/api/v1/internship/enterprise-portal/auth/browser-refresh'
])

export function requestAllowed(method, address, origins) {
  const url = new URL(address)
  if (!origins.includes(url.origin)) return false
  if (['GET', 'HEAD', 'OPTIONS'].includes(method)) return true
  return method === 'POST' && authPaths.has(url.pathname)
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
  return '# 全页面巡检记录\n\n页面条目和角色检查次数不等于审计通过页数。\n\n|页面|入口|角色|宽度|状态|截图|自动标记|人工结论|\n|---|---|---|---|---|---|---|---|\n' + records.map(r => `|${cell(r.page)}|${cell(r.route)}|${cell(r.role)}|${r.width}|${cell(r.status)}|${r.screenshot ? `[查看截图](${r.screenshot})` : '无'}|${cell(r.flags.map(f => f.kind).join('、'))}|${cell(r.conclusion)}|`).join('\n')
}

async function openDetailFromList(page, base, route) {
  const prefix = route.split('/:')[0]
  if (!prefix || prefix === '/') throw new Error('缺少明确列表入口')
  await page.goto(base + prefix)
  await page.waitForLoadState('networkidle')
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
  const button = first.getByRole('button', { name: /^(查看|查看详情|详情)$/ }).first()
  if (!await button.count()) throw new Error('首条记录没有只读详情入口')
  await button.click()
  await page.waitForURL(url => target.test(url.pathname))
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
  const saveReport = async () => {
    await fs.writeFile(path.join(out, 'report.json'), JSON.stringify({ records, blocked: allBlocked }, null, 2))
    await fs.writeFile(path.join(out, 'report.md'), renderReport(records))
  }
  const notRun = process.argv.includes('--not-run')
  const browser = notRun ? null : await (await import('@playwright/test')).chromium.launch()
  const newContext = async blocked => {
    const context = await browser?.newContext({ serviceWorkers: 'block', acceptDownloads: false })
    if (!context) return null
    await context.routeWebSocket('**/*', socket => socket.close())
    await context.route('**/*', route => {
      const req = route.request()
      if (requestAllowed(req.method(), req.url(), origins)) return route.continue()
      blocked.push({ method: req.method(), path: new URL(req.url()).pathname })
      return route.abort('blockedbyclient')
    })
    return context
  }
  try {
    for (const [role, roleLabel] of Object.entries(roles)) {
      const clients = role === 'STUDENT' ? ['student', 'mini'] : role === 'ENTERPRISE' ? ['enterprise'] : ['staff', 'mini']
      for (const client of clients) {
        const pages = entries.filter(s => s.client === client && (client !== 'mini' || !s.route.includes(role === 'STUDENT' ? '/teacher/' : '/student/')))
        const blocked = []
        const context = await newContext(blocked)
        const page = await context?.newPage()
        page?.setDefaultTimeout(15000)
        let unavailable = ''
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
                const rolePattern = { ADMIN: /学校管理员|校级管理员/, ACADEMIC: /教务/, COLLEGE: /学院/, TEACHER: /任课教师/, COUNSELOR: /辅导员/, AFFAIRS: /学工/, GRADUATION: /毕设|毕业设计/, INTERNSHIP: /实习/, LEADER: /校领导/ }[role]
                await login.switchRole(rolePattern)
                if (!rolePattern.test(await login.currentRoleText())) throw new Error('角色未核实')
              }
            } else if (client === 'mini') {
              const { loginMiniH5 } = await import('../lib/miniapp-login.mjs')
              await loginMiniH5(page, { baseUrl: bases.mini, entry: role === 'STUDENT' ? 'student' : 'teacher', account })
              if (role !== 'STUDENT') {
                await page.goto(`${bases.mini}/#/pages/role-switch/index`)
                const roleName = process.env[`UI_AUDIT_${role}_MINI_ROLE_LABEL`] || roleLabel
                const identity = page.locator('.rs__item').filter({ has: page.getByText(roleName, { exact: true }) })
                await identity.waitFor({ state: 'visible' })
                if (!(await identity.getAttribute('class'))?.includes('is-current')) {
                  await identity.click()
                  await page.waitForURL(/pages\/teacher\/workbench\/index/)
                  await page.goto(`${bases.mini}/#/pages/role-switch/index`)
                }
                if (!(await identity.getAttribute('class'))?.includes('is-current')) throw new Error('角色未核实')
              }
            } else {
              await page.goto(`${bases.enterprise}/login`)
              await page.getByLabel('学校编码', { exact: true }).fill(account.tenant)
              await page.getByLabel('手机号或登录账号', { exact: true }).fill(username)
              await page.getByLabel('密码', { exact: true }).fill(password)
              await page.getByRole('button', { name: '登录', exact: true }).click()
              await page.waitForURL(url => !url.pathname.endsWith('/login'))
            }
          } catch { unavailable = '未执行：登录或身份核验未完成；需检查环境及账号，不重置密码' }
        }
        for (const item of pages) for (const width of item.widths) {
          const record = { ...item, role: roleLabel, width, screenshot: null, text: null, flags: [], conclusion: '未人工审阅', status: unavailable || '待检查' }
          records.push(record)
          if (notRun || (unavailable && !item.public)) continue
          if (item.platformOnly) { record.status = '未执行：需平台正常账号'; continue }
          const publicContext = item.public ? await newContext(blocked) : null
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
            const response = item.route.includes(':')
              ? await openDetailFromList(capturePage, bases[client], item.route)
              : await capturePage.goto(bases[client] + item.route)
            const expectedUrl = item.route.includes(':') ? capturePage.url() : bases[client] + item.route
            let settled = true
            try { await capturePage.waitForLoadState('networkidle', { timeout: 15000 }) }
            catch { settled = false }
            const text = await capturePage.locator('body').innerText()
            const id = String(records.length).padStart(5, '0')
            await capturePage.screenshot({ path: path.join(out, `${id}.png`), fullPage: true })
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
          } catch { record.status = '未完成：页面加载、详情入口或截图失败' }
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

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) await main()
