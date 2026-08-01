#!/usr/bin/env node

import fs from 'node:fs'
import http from 'node:http'
import os from 'node:os'
import path from 'node:path'
import process from 'node:process'
import { createRequire } from 'node:module'
import { fileURLToPath } from 'node:url'
import { normalizeManifestPart } from './manifest-normalizer.mjs'

const TOOL_DIR = path.dirname(fileURLToPath(import.meta.url))
const ROOT = path.resolve(TOOL_DIR, '..')
const args = process.argv.slice(2)
const concurrency = Math.min(2, Math.max(1, Number(readArg('--concurrency') || 2)))
const timeoutMs = Math.max(5000, Number(readArg('--timeout-ms') || 30000))
const retries = Math.max(0, Number(readArg('--retries') || 2))
const smokeCount = Math.max(0, Number(readArg('--smoke') || 0))
const screenshots = args.includes('--screenshots')
const reportRoot = path.resolve(readArg('--report-dir') || path.join(os.tmpdir(), 'teacher-pc-v2-persistent', stamp()))
const viewports = parseViewports(readArg('--viewports') || '1280x900,1440x1000,1920x1080')
const require = createRequire(import.meta.url)
const puppeteerPath = process.env.PUPPETEER_CORE_PATH
if (!puppeteerPath) throw new Error('PUPPETEER_CORE_PATH is required')
const puppeteer = require(puppeteerPath)

function readArg(name) {
  const inline = args.find((arg) => arg.startsWith(`${name}=`))
  if (inline) return inline.slice(name.length + 1)
  const index = args.indexOf(name)
  return index >= 0 ? args[index + 1] : ''
}

function stamp() {
  return new Date().toISOString().replace(/[:.]/g, '-').replace('T', '_').replace('Z', '')
}

function parseViewports(raw) {
  const parsed = raw.split(',').map((item) => item.trim()).filter(Boolean).map((value) => {
    const match = value.match(/^(\d+)x(\d+)$/i)
    if (!match) throw new Error(`无效分辨率：${value}`)
    return { label: value, width: Number(match[1]), height: Number(match[2]) }
  })
  if (!parsed.length) throw new Error('至少需要一个分辨率')
  return parsed
}

function safeJson(file) {
  return JSON.parse(fs.readFileSync(file, 'utf8'))
}

function collectHtml() {
  const manifest = safeJson(path.join(ROOT, 'prototype-manifest.json'))
  const entries = []
  for (const partRef of manifest.aggregation?.parts || []) {
    const part = safeJson(path.resolve(ROOT, partRef))
    entries.push(...normalizeManifestPart(part).entries)
  }
  const unique = [...new Set(entries.map((entry) => entry.html).filter(Boolean))].sort()
  const expected = manifest.coverage?.uniqueHtmlFiles
  if (typeof expected === 'number' && expected !== unique.length) {
    throw new Error(`Manifest 声明 ${expected} 个 HTML，但聚合得到 ${unique.length} 个`)
  }
  return smokeCount ? unique.slice(0, smokeCount) : unique
}

function findChrome() {
  const explicit = process.env.CHROME_PATH || readArg('--chrome')
  const candidates = [
    explicit,
    '/usr/bin/google-chrome',
    '/usr/bin/google-chrome-stable',
    '/usr/bin/chromium',
    '/usr/bin/chromium-browser',
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
    'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe'
  ].filter(Boolean)
  const found = candidates.find((candidate) => fs.existsSync(candidate))
  if (!found) throw new Error(`Chrome executable not found: ${candidates.join(', ')}`)
  return found
}

function mimeType(file) {
  const ext = path.extname(file).toLowerCase()
  return ({
    '.html': 'text/html; charset=utf-8',
    '.css': 'text/css; charset=utf-8',
    '.js': 'text/javascript; charset=utf-8',
    '.mjs': 'text/javascript; charset=utf-8',
    '.json': 'application/json; charset=utf-8',
    '.svg': 'image/svg+xml',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.webp': 'image/webp',
    '.gif': 'image/gif',
    '.ico': 'image/x-icon'
  })[ext] || 'application/octet-stream'
}

async function startServer() {
  const server = http.createServer((request, response) => {
    const raw = decodeURIComponent(String(request.url || '/').split('?')[0]).replace(/^\/+/, '')
    if (raw === 'favicon.ico') {
      response.writeHead(204)
      response.end()
      return
    }
    const target = path.resolve(ROOT, raw || 'index.html')
    const relative = path.relative(ROOT, target)
    if (relative.startsWith('..') || path.isAbsolute(relative) || !fs.existsSync(target) || !fs.statSync(target).isFile()) {
      response.writeHead(404, { 'content-type': 'text/plain; charset=utf-8', 'cache-control': 'no-store' })
      response.end('Not Found')
      return
    }
    response.writeHead(200, {
      'content-type': mimeType(target),
      'cache-control': 'no-store, max-age=0',
      'access-control-allow-origin': '*'
    })
    fs.createReadStream(target).pipe(response)
  })
  await new Promise((resolve, reject) => {
    server.once('error', reject)
    server.listen(0, '127.0.0.1', resolve)
  })
  const address = server.address()
  return { server, origin: `http://127.0.0.1:${address.port}` }
}

const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

function safeName(value) {
  return value.replace(/[^a-zA-Z0-9.-]+/g, '_')
}

function classify(result) {
  const issues = []
  const report = result.probe
  if (result.navigationError) issues.push({ severity: 'error', code: 'NAVIGATION_ERROR', message: result.navigationError })
  if (!report) {
    issues.push({ severity: 'error', code: 'NO_PROBE', message: '未取得页面探针结果' })
    return issues
  }
  if (report.readyState !== 'complete') issues.push({ severity: 'error', code: 'NOT_COMPLETE', message: `readyState=${report.readyState}` })
  if (report.blank) issues.push({ severity: 'error', code: 'BLANK_PAGE', message: '页面为空' })
  if (report.rootOverflow) issues.push({ severity: 'error', code: 'ROOT_HORIZONTAL_OVERFLOW', message: `${report.scrollWidth} > ${report.clientWidth}` })
  if (report.duplicateIds.length) issues.push({ severity: 'error', code: 'DUPLICATE_ID', message: report.duplicateIds.join(', ') })
  if (report.brokenImages.length) issues.push({ severity: 'error', code: 'BROKEN_IMAGE', message: `${report.brokenImages.length} 个图片错误` })
  if (report.missingStyles.length) issues.push({ severity: 'error', code: 'MISSING_STYLESHEET', message: `${report.missingStyles.length} 个样式加载错误` })
  if (report.focusFailures.length) issues.push({ severity: 'error', code: 'FOCUS_FAILURE', message: `${report.focusFailures.length} 个控件无法聚焦` })
  if (report.positiveTabindex.length) issues.push({ severity: 'error', code: 'POSITIVE_TABINDEX', message: `${report.positiveTabindex.length} 个正 tabindex` })
  if (report.dialogFocusOutside.length) issues.push({ severity: 'error', code: 'DIALOG_FOCUS_OUTSIDE', message: `${report.dialogFocusOutside.length} 个弹层焦点在外部` })
  if (result.runtimeErrors.length) issues.push({ severity: 'error', code: 'RUNTIME_ERROR', message: `${result.runtimeErrors.length} 个运行时错误` })
  if (result.consoleErrors.length) issues.push({ severity: 'error', code: 'CONSOLE_ERROR', message: `${result.consoleErrors.length} 个 console.error` })
  if (result.resourceErrors.length) issues.push({ severity: 'error', code: 'RESOURCE_ERROR', message: `${result.resourceErrors.length} 个资源错误` })
  if (result.consoleWarnings.length) issues.push({ severity: 'warning', code: 'CONSOLE_WARNING', message: `${result.consoleWarnings.length} 个 console.warn` })
  return issues
}

async function collectProbe(page) {
  return page.evaluate(() => {
    const visible = (element) => {
      if (!element) return false
      const style = getComputedStyle(element)
      const rect = element.getBoundingClientRect()
      return style.display !== 'none' && style.visibility !== 'hidden' && Number(style.opacity || 1) !== 0 && rect.width > 0 && rect.height > 0
    }
    const selectorOf = (element) => {
      if (!element) return ''
      if (element.id) return `#${element.id}`
      const tag = String(element.tagName || 'node').toLowerCase()
      const cls = String(element.className || '').trim().split(/\s+/).filter(Boolean).slice(0, 2).join('.')
      return cls ? `${tag}.${cls}` : tag
    }
    const root = document.documentElement
    const body = document.body
    const ids = [...document.querySelectorAll('[id]')].map((element) => element.id).filter(Boolean)
    const duplicateIds = [...new Set(ids.filter((id, index) => ids.indexOf(id) !== index))]
    const duplicateIdDetails = duplicateIds.map((id) => ({
      id,
      nodes: [...document.querySelectorAll('[id]')]
        .filter((element) => element.id === id)
        .map((element) => ({ tag: element.tagName.toLowerCase(), className: String(element.className || ''), html: element.outerHTML.slice(0, 1200) }))
    }))
    const focusables = [...document.querySelectorAll('a[href],button,input,select,textarea,summary,[contenteditable="true"],[tabindex]:not([tabindex="-1"])')]
      .filter((element) => visible(element) && !element.disabled && element.getAttribute('aria-hidden') !== 'true')
    const focusFailures = []
    const focusSequence = []
    for (const element of focusables.slice(0, 80)) {
      try {
        element.focus({ preventScroll: true })
        if (document.activeElement !== element) focusFailures.push(selectorOf(element))
        else focusSequence.push(selectorOf(element))
      } catch (error) {
        focusFailures.push(`${selectorOf(element)}:${String(error?.message || error)}`)
      }
    }
    const dialogs = [...document.querySelectorAll('dialog,[role="dialog"],[aria-modal="true"]')].filter(visible)
    const text = String(body?.innerText || '').replace(/\s+/g, ' ').trim()
    const scrollWidth = Math.max(root.scrollWidth, body?.scrollWidth || 0)
    return {
      title: document.title,
      readyState: document.readyState,
      blank: !body || (!text && !body.querySelector('svg,canvas,img,video,iframe')),
      bodyTextLength: text.length,
      rootOverflow: scrollWidth > root.clientWidth + 1,
      scrollWidth,
      clientWidth: root.clientWidth,
      duplicateIds,
      duplicateIdDetails,
      brokenImages: [...document.images].filter((image) => !image.complete || image.naturalWidth === 0).map((image) => image.currentSrc || image.src),
      missingStyles: [...document.querySelectorAll('link[rel~="stylesheet"]')].filter((link) => !link.sheet).map((link) => link.href),
      interactiveCount: focusables.length,
      focusFailures,
      focusSequence: focusSequence.slice(0, 20),
      positiveTabindex: focusables.filter((element) => Number(element.getAttribute('tabindex')) > 0).map(selectorOf),
      openDialogCount: dialogs.length,
      dialogFocusOutside: dialogs.filter((dialog) => !dialog.contains(document.activeElement)).map(selectorOf)
    }
  })
}

async function renderAttempt(browser, origin, task, attempt) {
  const page = await browser.newPage()
  const runtimeErrors = []
  const consoleErrors = []
  const consoleWarnings = []
  const resourceErrors = []
  let navigationError = ''
  page.on('pageerror', (error) => runtimeErrors.push(error.stack || error.message))
  page.on('console', (message) => {
    if (message.type() === 'error') consoleErrors.push(message.text())
    if (message.type() === 'warning') consoleWarnings.push(message.text())
  })
  page.on('requestfailed', (request) => resourceErrors.push(`${request.url()} ${request.failure()?.errorText || ''}`.trim()))
  page.on('response', (response) => {
    if (response.status() >= 400) resourceErrors.push(`${response.status()} ${response.url()}`)
  })
  try {
    await page.setViewport({ width: task.viewport.width, height: task.viewport.height, deviceScaleFactor: 1 })
    await page.goto(`${origin}/${task.html}`, { waitUntil: 'domcontentloaded', timeout: timeoutMs })
    await page.waitForFunction(() => document.readyState === 'complete' && document.body, { timeout: timeoutMs })
    await delay(850)
    const probe = await collectProbe(page)
    let screenshotPath = ''
    if (screenshots) {
      screenshotPath = path.join(reportRoot, 'screenshots', `${safeName(task.viewport.label)}__${safeName(task.html)}.png`)
      fs.mkdirSync(path.dirname(screenshotPath), { recursive: true })
      await page.screenshot({ path: screenshotPath, fullPage: true })
    }
    const result = { html: task.html, viewport: task.viewport, attempt, probe, navigationError, runtimeErrors, consoleErrors, consoleWarnings, resourceErrors, screenshotPath }
    result.issues = classify(result)
    result.status = result.issues.some((issue) => issue.severity === 'error') ? 'FAIL' : result.issues.some((issue) => issue.severity === 'warning') ? 'WARN' : 'PASS'
    return result
  } catch (error) {
    navigationError = error.stack || error.message
    const result = { html: task.html, viewport: task.viewport, attempt, probe: null, navigationError, runtimeErrors, consoleErrors, consoleWarnings, resourceErrors, screenshotPath: '' }
    result.issues = classify(result)
    result.status = 'FAIL'
    return result
  } finally {
    await page.close().catch(() => {})
  }
}

function retryable(result) {
  const codes = result.issues.filter((issue) => issue.severity === 'error').map((issue) => issue.code)
  return codes.length > 0 && codes.every((code) => code === 'NAVIGATION_ERROR' || code === 'NO_PROBE')
}

async function renderOne(browser, origin, task) {
  const attempts = []
  let result
  for (let attempt = 1; attempt <= retries + 1; attempt += 1) {
    result = await renderAttempt(browser, origin, task, attempt)
    attempts.push({ attempt, status: result.status, issueCodes: result.issues.map((issue) => issue.code) })
    if (!retryable(result) || attempt > retries) break
    await delay(500 * attempt)
  }
  result.attempts = attempts
  return result
}

async function pool(items, limit, worker) {
  const results = new Array(items.length)
  let cursor = 0
  async function run() {
    while (true) {
      const index = cursor++
      if (index >= items.length) return
      results[index] = await worker(items[index], index)
    }
  }
  await Promise.all(Array.from({ length: Math.min(limit, items.length) }, run))
  return results
}

function writeMarkdown(summary, failures) {
  const lines = [
    '# Teacher PC V2 持久浏览器回归', '',
    `- HTML：**${summary.htmlCount}**`,
    `- 分辨率：**${summary.viewportCount}**`,
    `- 总渲染：**${summary.actualRenders}/${summary.expectedRenders}**`,
    `- 通过：**${summary.passed}**`,
    `- 失败：**${summary.failed}**`,
    `- 警告：**${summary.warningRenders}**`,
    `- Chrome 进程：**1 个持久实例**`,
    `- 页面 worker：**${summary.concurrency}**`,
    `- 重试恢复：**${summary.recoveredTransientFailures}**`,
    `- 状态：**${summary.status}**`, ''
  ]
  if (failures.length) {
    lines.push('## 失败', '')
    for (const item of failures) lines.push(`- ${item.viewport.label} · ${item.html}：${item.issues.map((issue) => `${issue.code} ${issue.message}`).join('；')}`)
  }
  fs.writeFileSync(path.join(reportRoot, 'browser-regression.md'), `${lines.join('\n')}\n`)
}

fs.mkdirSync(reportRoot, { recursive: true })
const htmlFiles = collectHtml()
const tasks = viewports.flatMap((viewport) => htmlFiles.map((html) => ({ html, viewport })))
const executablePath = findChrome()
const { server, origin } = await startServer()
const browser = await puppeteer.launch({
  executablePath,
  headless: true,
  args: ['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu', '--force-color-profile=srgb', '--no-first-run', '--no-default-browser-check']
})
const started = Date.now()
let results
try {
  console.log(`开始持久浏览器回归：${htmlFiles.length} HTML × ${viewports.length} 分辨率 = ${tasks.length} 次渲染`)
  console.log(`Chrome: ${executablePath}；进程: 1；页面并发: ${concurrency}`)
  results = await pool(tasks, concurrency, async (task, index) => {
    const result = await renderOne(browser, origin, task)
    console.log(`[${index + 1}/${tasks.length}] ${result.status} ${task.viewport.label} ${task.html}`)
    return result
  })
} finally {
  await browser.close().catch(() => {})
  await new Promise((resolve) => server.close(resolve))
}

const failures = results.filter((result) => result.status === 'FAIL')
const warnings = results.filter((result) => result.status === 'WARN')
const retried = results.filter((result) => result.attempts.length > 1)
const summary = {
  generatedAt: new Date().toISOString(),
  executablePath,
  root: ROOT,
  reportRoot,
  htmlCount: htmlFiles.length,
  viewportCount: viewports.length,
  viewports,
  expectedRenders: tasks.length,
  actualRenders: results.length,
  passed: results.filter((result) => result.status === 'PASS').length,
  failed: failures.length,
  warningRenders: warnings.length,
  concurrency,
  retryLimit: retries,
  retriedRenders: retried.length,
  recoveredTransientFailures: retried.filter((result) => result.status === 'PASS').length,
  chromeProcessCount: 1,
  durationSeconds: Math.round((Date.now() - started) / 1000),
  status: failures.length ? 'FAIL' : 'PASS'
}
fs.writeFileSync(path.join(reportRoot, 'browser-regression.json'), `${JSON.stringify({ summary, results }, null, 2)}\n`)
writeMarkdown(summary, failures)
console.log(JSON.stringify(summary, null, 2))
if (failures.length) process.exit(1)
