import fs from 'node:fs/promises'
import path from 'node:path'

export function sleep(ms) { return new Promise((resolve) => setTimeout(resolve, ms)) }

export function slug(value) {
  return String(value || 'page').normalize('NFKC')
    .replace(/[\\/:*?"<>|\s]+/g, '-')
    .replace(/^-+|-+$/g, '').slice(0, 90)
}

export async function ensureOutput(outputDir) {
  await fs.rm(outputDir, { recursive: true, force: true })
  await fs.mkdir(path.join(outputDir, 'screenshots'), { recursive: true })
}

export async function capture(page, outputDir, name, fullPage = true) {
  const file = path.join(outputDir, 'screenshots', `${slug(name)}.jpg`)
  await page.screenshot({ path: file, type: 'jpeg', quality: 76, fullPage })
  return path.relative(outputDir, file).replaceAll('\\', '/')
}

export function attachDiagnostics(page, report, scope) {
  page.on('console', (msg) => {
    if (msg.type() === 'error') report.consoleErrors.push({ scope: scope.value, text: msg.text().slice(0, 800) })
  })
  page.on('pageerror', (err) => report.consoleErrors.push({ scope: scope.value, text: String(err?.stack || err).slice(0, 1200) }))
  page.on('response', (res) => {
    if (res.status() < 400) return
    const url = res.url()
    if (!url.includes('/api/') && !url.includes('127.0.0.1:5199')) return
    report.networkFailures.push({ scope: scope.value, status: res.status(), method: res.request().method(), url })
  })
  page.on('requestfailed', (req) => report.networkFailures.push({
    scope: scope.value, status: 0, method: req.method(), url: req.url(), error: req.failure()?.errorText || 'request failed'
  }))
}

export async function waitStable(page) {
  await page.waitForLoadState('domcontentloaded')
  await sleep(900)
  await page.locator('.sp-state').filter({ hasText: /加载中|正在加载/ }).first()
    .waitFor({ state: 'hidden', timeout: 12000 }).catch(() => {})
  await sleep(250)
}

export async function analyzeLayout(page) {
  return page.evaluate(() => {
    const vw = document.documentElement.clientWidth
    const vh = document.documentElement.clientHeight
    const rect = (el) => {
      if (!el) return null
      const r = el.getBoundingClientRect()
      return { left: Math.round(r.left), top: Math.round(r.top), right: Math.round(r.right), bottom: Math.round(r.bottom), width: Math.round(r.width), height: Math.round(r.height) }
    }
    const shell = document.querySelector('.sp-shell')
    const tabs = document.querySelector('.sp-page > .sp-tabs')
    const keys = [...document.querySelectorAll('.sp-header,.sp-aside,.sp-content,.sp-tabs,.sp-card,.sp-table,.sp-inp,.sp-btn,.home-hero,.home-card,[role="dialog"],dialog,.modal,.dialog,.drawer')]
    const overflow = keys.flatMap((el) => {
      const r = el.getBoundingClientRect()
      if (!r.width || !r.height) return []
      const bad = r.left < -2 || r.right > vw + 2 || el.scrollWidth > el.clientWidth + 4
      return bad ? [{ cls: String(el.className || '').slice(0, 140), ...rect(el), scrollWidth: el.scrollWidth, clientWidth: el.clientWidth }] : []
    }).slice(0, 30)
    const dialogs = [...document.querySelectorAll('[role="dialog"],dialog,.modal,.dialog,.drawer')]
      .filter((el) => { const s = getComputedStyle(el); return s.display !== 'none' && s.visibility !== 'hidden' })
      .map((el) => { const r = rect(el); return { ...r, outside: r.left < 0 || r.top < 0 || r.right > vw || r.bottom > vh } })
    return {
      url: location.pathname + location.search,
      viewport: { width: vw, height: vh },
      document: { scrollWidth: document.documentElement.scrollWidth, scrollHeight: document.documentElement.scrollHeight },
      horizontalOverflow: document.documentElement.scrollWidth > vw + 4,
      shellClasses: shell?.className || '',
      aside: rect(document.querySelector('.sp-aside')),
      header: rect(document.querySelector('.sp-header')),
      tabs: tabs ? { ...rect(tabs), count: tabs.querySelectorAll('.sp-tab').length } : null,
      overflow,
      dialogs,
      states: [...document.querySelectorAll('.sp-state,[role="alert"],.error,.domain-error,.gd-health')]
        .map((el) => (el.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 240)).filter(Boolean),
      tables: document.querySelectorAll('table').length,
      controls: document.querySelectorAll('input,select,textarea,button').length,
      disabledButtons: [...document.querySelectorAll('button:disabled')].map((el) => (el.textContent || '').trim()).filter(Boolean).slice(0, 20)
    }
  })
}

export function dedupe(rows, keyFn) { return [...new Map(rows.map((row) => [keyFn(row), row])).values()] }
