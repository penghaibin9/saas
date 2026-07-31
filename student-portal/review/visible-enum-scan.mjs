import { chromium } from 'playwright'
import fs from 'node:fs/promises'
import path from 'node:path'
import config from './v5-review-config.json' with { type: 'json' }
import { capture, setTheme, sleep, waitStable } from './review-lib.mjs'
import { VISIBLE_ENUM_LABELS, VISIBLE_ENUM_WHITELIST } from '../src/services/visibleEnumLocalization.js'

const baseUrl = process.env.REVIEW_BASE_URL || 'http://127.0.0.1:5199'
const loginName = process.env.REVIEW_LOGIN
const password = process.env.REVIEW_PASSWORD
const tenantCode = process.env.REVIEW_TENANT
const outputDir = path.resolve(process.env.REVIEW_OUTPUT || '../docs/reviews/student-portal-v5-full-review')
if (!loginName || !password || !tenantCode) throw new Error('review credentials are required')

await fs.mkdir(path.join(outputDir, 'screenshots'), { recursive: true })
const knownTokens = Object.keys(VISIBLE_ENUM_LABELS)
const whitelist = [...VISIBLE_ENUM_WHITELIST]
const result = {
  generatedAt: new Date().toISOString(),
  routesChecked: 0,
  tabsChecked: 0,
  issues: [],
  screenshots: {},
  darkSidebar: null,
  whitelist
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
}

async function scanVisibleText(page, scope) {
  const issues = await page.evaluate(({ knownTokens: known, whitelist: legal }) => {
    const knownSet = new Set(known)
    const legalSet = new Set(legal)
    const skipTags = new Set(['SCRIPT', 'STYLE', 'NOSCRIPT', 'TEXTAREA', 'INPUT', 'OPTION', 'CODE', 'PRE'])
    const underscoreRe = /\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b/g
    const upperWordRe = /\b[A-Z][A-Z0-9]{2,}\b/g
    const visible = (element) => {
      if (!element || skipTags.has(element.tagName) || element.closest('[data-raw-enum="true"]')) return false
      const style = getComputedStyle(element)
      const rect = element.getBoundingClientRect()
      return style.display !== 'none' && style.visibility !== 'hidden' && Number(style.opacity || 1) > 0 && rect.width > 0 && rect.height > 0
    }
    const rows = []
    const seen = new Set()
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT)
    let node = walker.nextNode()
    while (node) {
      const parent = node.parentElement
      const text = String(node.nodeValue || '').trim()
      if (text && visible(parent)) {
        const tokens = new Set(text.match(underscoreRe) || [])
        for (const token of text.match(upperWordRe) || []) {
          if (knownSet.has(token)) tokens.add(token)
        }
        for (const token of tokens) {
          if (legalSet.has(token)) continue
          const key = `${token}|${text}`
          if (seen.has(key)) continue
          seen.add(key)
          rows.push({
            token,
            text: text.replace(/\s+/g, ' ').slice(0, 180),
            tag: parent?.tagName || '',
            className: String(parent?.className || '').slice(0, 120)
          })
        }
      }
      node = walker.nextNode()
    }
    return rows
  }, { knownTokens, whitelist })
  result.issues.push(...issues.map((issue) => ({ scope, ...issue })))
}

async function scanRouteAndTabs(page, route) {
  await page.goto(`${baseUrl}${route.path}`, { waitUntil: 'domcontentloaded' })
  await waitStable(page)
  await scanVisibleText(page, `route:${route.path}`)
  result.routesChecked += 1

  const tabs = page.locator('button.sp-tab:visible, button.mtab:visible, [role="tab"]:visible')
  const count = await tabs.count()
  const visited = new Set()
  for (let index = 0; index < count; index += 1) {
    const tab = tabs.nth(index)
    const label = (await tab.innerText().catch(() => '')).trim().replace(/\s+/g, ' ')
    if (!label || visited.has(label)) continue
    visited.add(label)
    await tab.scrollIntoViewIfNeeded().catch(() => {})
    await tab.click().catch(() => {})
    await sleep(500)
    await scanVisibleText(page, `route:${route.path}|tab:${label}`)
    result.tabsChecked += 1
  }
}

const browser = await chromium.launch({ headless: true })
try {
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, locale: 'zh-CN' })
  const page = await context.newPage()
  await login(page)

  for (const route of config.routes) await scanRouteAndTabs(page, route)

  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto(`${baseUrl}/home`, { waitUntil: 'domcontentloaded' })
  await waitStable(page)
  await setTheme(page, 'blue')
  result.screenshots.home = await capture(page, outputDir, 'final-home-enum-localized')

  await page.goto(`${baseUrl}/campus-service`, { waitUntil: 'domcontentloaded' })
  await waitStable(page)
  await setTheme(page, 'orange')
  const leaveTab = page.locator('button.sp-tab:visible', { hasText: '请假销假' }).first()
  if (await leaveTab.count()) await leaveTab.click()
  await sleep(500)
  result.screenshots.leave = await capture(page, outputDir, 'final-campus-service-leave-localized')

  await page.goto(`${baseUrl}/service-hall`, { waitUntil: 'domcontentloaded' })
  await waitStable(page)
  await setTheme(page, 'dark')
  result.darkSidebar = await page.evaluate(() => {
    const aside = document.querySelector('.sp-aside')
    const style = aside ? getComputedStyle(aside) : null
    return {
      backgroundImage: style?.backgroundImage || '',
      backgroundColor: style?.backgroundColor || '',
      matchesV5DarkBaseline: Boolean(style?.backgroundImage?.includes('rgb(7, 12, 19)') && style?.backgroundImage?.includes('rgb(40, 59, 102)'))
    }
  })
  result.screenshots.dark = await capture(page, outputDir, 'final-dark-sidebar')

  await page.setViewportSize({ width: 1024, height: 768 })
  await page.goto(`${baseUrl}/academic/warning`, { waitUntil: 'domcontentloaded' })
  await waitStable(page)
  await setTheme(page, 'blue')
  result.screenshots.viewport1024 = await capture(page, outputDir, 'final-1024-academic-warning', false)

  await context.close()
} finally {
  await browser.close()
}

result.passed = result.issues.length === 0 && result.darkSidebar?.matchesV5DarkBaseline === true
await fs.writeFile(path.join(outputDir, 'visible-enum-results.json'), JSON.stringify(result, null, 2), 'utf8')
console.log(JSON.stringify({
  routesChecked: result.routesChecked,
  tabsChecked: result.tabsChecked,
  visibleEnumIssues: result.issues.length,
  darkSidebarMatchesV5: result.darkSidebar?.matchesV5DarkBaseline,
  passed: result.passed
}, null, 2))
if (!result.passed) process.exitCode = 1
