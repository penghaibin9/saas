import { chromium } from 'playwright'
import fs from 'node:fs/promises'
import path from 'node:path'
import config from './v5-review-config.json' with { type: 'json' }
import { analyzeLayout, attachDiagnostics, capture, dedupe, ensureOutput, sleep, waitStable } from './review-lib.mjs'

const baseUrl = process.env.REVIEW_BASE_URL || 'http://127.0.0.1:5199'
const loginName = process.env.REVIEW_LOGIN
const password = process.env.REVIEW_PASSWORD
const tenantCode = process.env.REVIEW_TENANT
const outputDir = path.resolve(process.env.REVIEW_OUTPUT || '../docs/reviews/student-portal-v5-full-review')
if (!loginName || !password || !tenantCode) throw new Error('review credentials are required')

await ensureOutput(outputDir)
const report = {
  generatedAt: new Date().toISOString(),
  source: 'real MySQL + real password login + Chromium',
  routes: [], themeChecks: [], viewportChecks: [], authChecks: [], consoleErrors: [], networkFailures: []
}

async function login(page) {
  await page.goto(`${baseUrl}/login`, { waitUntil: 'domcontentloaded' })
  await page.fill('#student-account', loginName)
  await page.fill('#student-password', password)
  const details = page.locator('.tenant-details')
  if (!(await details.getAttribute('open'))) await page.locator('.tenant-details summary').click()
  await page.fill('#student-tenant', tenantCode)
  await page.locator('.agreement input').check()
  await page.locator('.submit-button').click()
  await page.waitForURL((url) => url.pathname.endsWith('/home'), { timeout: 20000 })
  await waitStable(page)
  report.authChecks.push({ name: 'student real password login', passed: true, url: page.url() })
}

async function unauthenticatedBoundary(browser) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } })
  const page = await context.newPage()
  await page.goto(`${baseUrl}/academic`, { waitUntil: 'domcontentloaded' })
  const passed = await page.waitForURL((url) => url.pathname.endsWith('/login') && url.searchParams.get('redirect')?.includes('/academic'), { timeout: 12000 }).then(() => true).catch(() => false)
  report.authChecks.push({ name: 'unauthenticated direct route redirects to login', passed, url: page.url() })
  await capture(page, outputDir, 'auth-unauthenticated-redirect', false)
  await context.close()
}

async function inspectRoute(page, route, viewportKey, inspectTabs = false) {
  const item = { ...route, viewport: viewportKey, accessible: false, result: '通过', issues: [], tabs: [], screenshots: [] }
  await page.goto(`${baseUrl}${route.path}`, { waitUntil: 'domcontentloaded' })
  await waitStable(page)
  item.accessible = !new URL(page.url()).pathname.endsWith('/login')
  item.layout = await analyzeLayout(page)
  item.screenshots.push(await capture(page, outputDir, `${viewportKey}-${route.path}-${route.name}`))

  if (!item.accessible) item.issues.push('页面被重定向到登录页')
  if (item.layout.horizontalOverflow) item.issues.push('文档存在横向溢出')
  if (item.layout.overflow.length) item.issues.push(`关键元素溢出 ${item.layout.overflow.length} 项`)
  if (item.layout.dialogs.some((d) => d.outside)) item.issues.push('弹窗超出视口')
  if (route.path === '/home' && !item.layout.shellClasses.includes('is-home')) item.issues.push('首页未命中 is-home 骨架')
  if (!['/home','/not-enabled'].includes(route.path) && route.module !== '公共状态页' && !item.layout.shellClasses.includes('is-compact')) item.issues.push('业务页未命中紧凑骨架')

  const before = new URL(page.url()).pathname
  await page.reload({ waitUntil: 'domcontentloaded' })
  await waitStable(page)
  const after = new URL(page.url()).pathname
  item.refresh = { before, after, passed: before === after && !after.endsWith('/login') }
  if (!item.refresh.passed && route.module !== '公共状态页') item.issues.push('刷新后路由或登录态异常')

  if (inspectTabs) {
    const tabs = page.locator('.sp-page > .sp-tabs .sp-tab:visible, .mtab:visible, [role="tab"]:visible')
    const count = await tabs.count()
    const labels = new Set()
    for (let index = 0; index < count; index += 1) {
      const tab = tabs.nth(index)
      const label = (await tab.innerText().catch(() => '')).trim().replace(/\s+/g, ' ')
      if (!label || labels.has(label)) continue
      labels.add(label)
      const row = { label, clicked: false, active: false, issues: [], screenshot: null }
      try {
        await tab.scrollIntoViewIfNeeded()
        await tab.click()
        await sleep(650)
        row.clicked = true
        row.active = await tab.evaluate((el) => el.classList.contains('is-active') || el.classList.contains('active') || el.getAttribute('aria-selected') === 'true')
        const layout = await analyzeLayout(page)
        if (!row.active) row.issues.push('点击后未呈现选中态')
        if (layout.horizontalOverflow) row.issues.push('切换后横向溢出')
        if (layout.overflow.length) row.issues.push(`切换后关键元素溢出 ${layout.overflow.length} 项`)
        row.screenshot = await capture(page, outputDir, `${viewportKey}-${route.path}-tab-${label}`)
      } catch (error) {
        row.issues.push(`点击失败：${String(error?.message || error).slice(0, 180)}`)
      }
      item.tabs.push(row)
    }
  }
  if (item.issues.length || item.tabs.some((tab) => tab.issues.length)) item.result = '有问题'
  return item
}

async function inspectThemes(page) {
  await page.setViewportSize({ width: 1440, height: 900 })
  for (const theme of config.themes) {
    await page.goto(`${baseUrl}${theme.route}`, { waitUntil: 'domcontentloaded' })
    await waitStable(page)
    const button = page.locator(`.sp-theme__item[title="${theme.label}"]`)
    const found = await button.count()
    if (found) await button.click()
    await sleep(450)
    const data = await page.evaluate(() => {
      const app = document.querySelector('.sp-app')
      const card = document.querySelector('.sp-card,.home-card,.card')
      return {
        htmlTheme: document.documentElement.dataset.spTheme || '',
        primary: app ? getComputedStyle(app).getPropertyValue('--pri').trim() : '',
        cardBackground: card ? getComputedStyle(card).backgroundColor : '',
        themeButtons: document.querySelectorAll('.sp-theme__item').length
      }
    })
    const layout = await analyzeLayout(page)
    const passed = found === 1 && data.htmlTheme === theme.key && data.themeButtons === 6 && !layout.horizontalOverflow
    report.themeChecks.push({ ...theme, passed, data, layout, screenshot: await capture(page, outputDir, `theme-${theme.key}-${theme.route}`) })
  }
}

async function inspectViewports(page) {
  for (const viewport of config.viewports.slice(1)) {
    await page.setViewportSize({ width: viewport.width, height: viewport.height })
    for (const route of config.routes.filter((entry) => entry.module !== '公共状态页')) {
      await page.goto(`${baseUrl}${route.path}`, { waitUntil: 'domcontentloaded' })
      await waitStable(page)
      const layout = await analyzeLayout(page)
      const issues = []
      if (layout.horizontalOverflow) issues.push('文档横向溢出')
      if (layout.overflow.length) issues.push(`关键元素溢出 ${layout.overflow.length} 项`)
      if (layout.dialogs.some((dialog) => dialog.outside)) issues.push('弹窗超出视口')
      const representative = ['/home','/academic','/campus-service','/internship','/graduation'].includes(route.path)
      report.viewportChecks.push({ viewport: viewport.key, route: route.path, passed: issues.length === 0, issues, layout, screenshot: representative ? await capture(page, outputDir, `${viewport.key}-${route.path}-responsive`, false) : null })
    }
  }
}

const browser = await chromium.launch({ headless: true })
try {
  await unauthenticatedBoundary(browser)
  const context = await browser.newContext({ viewport: { width: 1920, height: 1080 }, locale: 'zh-CN' })
  const page = await context.newPage()
  const scope = { value: 'login' }
  attachDiagnostics(page, report, scope)
  await login(page)

  for (const route of config.routes) {
    scope.value = `route:${route.path}`
    report.routes.push(await inspectRoute(page, route, '1920x1080', true))
  }
  scope.value = 'themes'
  await inspectThemes(page)
  scope.value = 'viewports'
  await inspectViewports(page)
  await context.close()
} finally {
  await browser.close()
}

report.consoleErrors = dedupe(report.consoleErrors, (row) => `${row.scope}|${row.text}`)
report.networkFailures = dedupe(report.networkFailures, (row) => `${row.scope}|${row.method}|${row.status}|${row.url}`)
report.summary = {
  totalRoutes: report.routes.length,
  passedRoutes: report.routes.filter((row) => row.result === '通过').length,
  problemRoutes: report.routes.filter((row) => row.result !== '通过').length,
  blockedRoutes: report.routes.filter((row) => !row.accessible).length,
  uncheckedRoutes: 0,
  tabsChecked: report.routes.reduce((sum, row) => sum + row.tabs.length, 0),
  tabProblems: report.routes.reduce((sum, row) => sum + row.tabs.filter((tab) => tab.issues.length).length, 0),
  themesChecked: report.themeChecks.length,
  themeProblems: report.themeChecks.filter((row) => !row.passed).length,
  viewportCases: report.viewportChecks.length,
  viewportProblems: report.viewportChecks.filter((row) => !row.passed).length,
  consoleErrors: report.consoleErrors.length,
  networkFailures: report.networkFailures.length
}
await fs.writeFile(path.join(outputDir, 'review-results.json'), JSON.stringify(report, null, 2), 'utf8')
console.log(JSON.stringify(report.summary, null, 2))
