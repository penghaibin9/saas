#!/usr/bin/env node

import fs from 'node:fs'
import http from 'node:http'
import os from 'node:os'
import path from 'node:path'
import process from 'node:process'
import { createRequire } from 'node:module'
import { fileURLToPath } from 'node:url'

const TOOL_DIR = path.dirname(fileURLToPath(import.meta.url))
const ROOT = path.resolve(TOOL_DIR, '..')
const args = process.argv.slice(2)
const reportArg = args.find((value) => value.startsWith('--report='))
const REPORT = path.resolve(reportArg ? reportArg.slice('--report='.length) : path.join(os.tmpdir(), 'pr27-freeze-acceptance.json'))
const ARTIFACT_DIR = path.dirname(REPORT)
const browserName = process.env.ACCEPTANCE_BROWSER || 'chrome'
const require = createRequire(import.meta.url)
const puppeteerPath = process.env.PUPPETEER_CORE_PATH
if (!puppeteerPath) throw new Error('PUPPETEER_CORE_PATH is required')
const puppeteer = require(puppeteerPath)

const PRINT_PAGES = [
  'academic-affairs/schedule/print-schedule-class.html',
  'academic-affairs/schedule/print-schedule-teacher.html',
  'academic-affairs/status-changes/status-change-print.html',
  'academic-affairs/exam/exam-seating-print.html'
]

const STRESS_PAGES = [
  'academic-affairs/stats/stats-overview.html',
  'academic-affairs/grades/transcript.html',
  'academic-affairs/schedule/week-schedule.html',
  'academic-affairs/exam/exam-rooms-seats.html',
  'student-affairs/student-360.html',
  'student-affairs/talks-family-workbench.html',
  'student-affairs/mental-crisis.html',
  'student-affairs/discipline-workbench.html',
  'student-affairs/difficulty-workbench.html',
  'graduation/risk-archive.html',
  'internship/archive-stats.html'
]

const KEYBOARD_PAGES = [
  'student-affairs/student-360.html',
  'student-affairs/leave-workbench.html',
  'student-affairs/risk-workbench.html',
  'student-affairs/talks-family-workbench.html',
  'graduation/defense.html'
]

const SENSITIVE_CONTRACTS = [
  ['student-affairs/student-360.html', ['权限', '用途', '审计']],
  ['student-affairs/talks-family-workbench.html', ['家庭', '用途', '审计']],
  ['student-affairs/mental-crisis.html', ['心理', '权限', '审计']],
  ['student-affairs/discipline-workbench.html', ['处分', '权限', '审计']],
  ['student-affairs/difficulty-workbench.html', ['困难', '权限', '审计']]
]

for (const relative of new Set([...PRINT_PAGES, ...STRESS_PAGES, ...KEYBOARD_PAGES, ...SENSITIVE_CONTRACTS.map(([file]) => file)])) {
  const absolute = path.join(ROOT, relative)
  if (!fs.existsSync(absolute)) throw new Error(`acceptance page missing: ${relative}`)
}

function findBrowser() {
  const explicit = process.env.ACCEPTANCE_BROWSER_PATH
  const candidates = browserName === 'edge'
    ? [
        explicit,
        'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
        'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe',
        '/usr/bin/microsoft-edge',
        '/usr/bin/microsoft-edge-stable'
      ]
    : [
        explicit,
        '/usr/bin/google-chrome',
        '/usr/bin/google-chrome-stable',
        '/usr/bin/chromium',
        '/usr/bin/chromium-browser',
        'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
        'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe'
      ]
  const found = candidates.filter(Boolean).find((candidate) => fs.existsSync(candidate))
  if (!found) throw new Error(`${browserName} executable not found; checked: ${candidates.filter(Boolean).join(', ')}`)
  return found
}

function mimeType(file) {
  const extension = path.extname(file).toLowerCase()
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
    '.webp': 'image/webp'
  })[extension] || 'application/octet-stream'
}

async function startServer() {
  const server = http.createServer((request, response) => {
    const raw = decodeURIComponent(String(request.url || '/').split('?')[0]).replace(/^\/+/, '')
    const target = path.resolve(ROOT, raw || 'index.html')
    const relative = path.relative(ROOT, target)
    if (relative.startsWith('..') || path.isAbsolute(relative) || !fs.existsSync(target) || !fs.statSync(target).isFile()) {
      response.writeHead(404, { 'content-type': 'text/plain; charset=utf-8' })
      response.end('Not Found')
      return
    }
    response.writeHead(200, { 'content-type': mimeType(target), 'cache-control': 'no-store' })
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

function safeName(relative) {
  return relative.replace(/[^a-zA-Z0-9.-]+/g, '_')
}

async function openPage(browser, origin, relative, viewport = { width: 1440, height: 1000 }) {
  const page = await browser.newPage()
  const runtimeErrors = []
  const consoleErrors = []
  page.on('pageerror', (error) => runtimeErrors.push(error.stack || error.message))
  page.on('console', (message) => {
    if (message.type() === 'error') consoleErrors.push(message.text())
  })
  await page.setViewport(viewport)
  await page.goto(`${origin}/${relative}`, { waitUntil: 'networkidle0', timeout: 30000 })
  await page.waitForFunction(() => document.readyState === 'complete' && document.body, { timeout: 10000 })
  await delay(350)
  return { page, runtimeErrors, consoleErrors }
}

async function layoutMetrics(page) {
  return page.evaluate(() => {
    const root = document.documentElement
    const body = document.body
    const visible = (element) => {
      const style = getComputedStyle(element)
      const rect = element.getBoundingClientRect()
      return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0
    }
    return {
      title: document.title,
      bodyTextLength: String(body?.innerText || '').trim().length,
      rootOverflow: Math.max(root.scrollWidth, body?.scrollWidth || 0) > root.clientWidth + 1,
      scrollWidth: Math.max(root.scrollWidth, body?.scrollWidth || 0),
      clientWidth: root.clientWidth,
      duplicateIds: [...document.querySelectorAll('[id]')]
        .map((element) => element.id)
        .filter((id, index, all) => id && all.indexOf(id) !== index),
      brokenImages: [...document.images]
        .filter((image) => visible(image) && (!image.complete || image.naturalWidth === 0))
        .map((image) => image.currentSrc || image.src)
    }
  })
}

function assertMetrics(relative, stage, metrics, errors) {
  if (!metrics.title) errors.push(`${relative} [${stage}] missing title`)
  if (metrics.bodyTextLength < 20) errors.push(`${relative} [${stage}] blank or nearly blank`)
  if (metrics.rootOverflow) errors.push(`${relative} [${stage}] root overflow ${metrics.scrollWidth}>${metrics.clientWidth}`)
  if (metrics.duplicateIds.length) errors.push(`${relative} [${stage}] duplicate ids: ${[...new Set(metrics.duplicateIds)].join(', ')}`)
  if (metrics.brokenImages.length) errors.push(`${relative} [${stage}] broken images: ${metrics.brokenImages.join(', ')}`)
}

async function runStress(browser, origin, errors, results) {
  const longCn = '超长中文业务字段用于验证表格单元格换行与容器滚动边界'.repeat(12)
  const longEn = 'VERY_LONG_UNBROKEN_BUSINESS_IDENTIFIER_'.repeat(16)
  for (const relative of STRESS_PAGES) {
    const context = await openPage(browser, origin, relative)
    const { page, runtimeErrors, consoleErrors } = context
    const initial = await layoutMetrics(page)
    assertMetrics(relative, 'initial', initial, errors)

    await page.evaluate(({ longCn, longEn }) => {
      const cells = [...document.querySelectorAll('td,th')].filter((element) => element.offsetParent !== null).slice(0, 10)
      cells.forEach((cell, index) => {
        cell.textContent = index % 2 ? longEn : longCn
      })
    }, { longCn, longEn })
    await delay(150)
    const longData = await layoutMetrics(page)
    assertMetrics(relative, 'long-text', longData, errors)

    await page.evaluate(() => {
      const tbody = document.querySelector('tbody')
      const row = tbody?.querySelector('tr')
      if (!tbody || !row) return
      const fragment = document.createDocumentFragment()
      for (let index = 0; index < 80; index += 1) fragment.appendChild(row.cloneNode(true))
      tbody.appendChild(fragment)
    })
    await delay(150)
    const largeData = await layoutMetrics(page)
    assertMetrics(relative, 'large-data', largeData, errors)

    await page.evaluate(() => {
      for (const row of document.querySelectorAll('tbody tr')) row.remove()
    })
    await delay(100)
    const emptyData = await layoutMetrics(page)
    assertMetrics(relative, 'empty-data', emptyData, errors)

    if (runtimeErrors.length) errors.push(`${relative} runtime errors: ${runtimeErrors.join(' | ')}`)
    if (consoleErrors.length) errors.push(`${relative} console errors: ${consoleErrors.join(' | ')}`)
    await page.screenshot({ path: path.join(ARTIFACT_DIR, `${browserName}-${safeName(relative)}.png`), fullPage: true })
    results.stress.push({ relative, initial, longData, largeData, emptyData })
    await page.close()
  }
}

async function runKeyboard(browser, origin, errors, results) {
  for (const relative of KEYBOARD_PAGES) {
    const { page, runtimeErrors, consoleErrors } = await openPage(browser, origin, relative)
    const sequence = []
    for (let index = 0; index < 24; index += 1) {
      await page.keyboard.press('Tab')
      sequence.push(await page.evaluate(() => {
        const active = document.activeElement
        if (!active) return ''
        return active.id || active.getAttribute('data-open') || active.getAttribute('aria-label') || active.textContent?.trim().slice(0, 40) || active.tagName
      }))
    }
    const meaningful = [...new Set(sequence.filter((value) => value && value !== 'BODY'))]
    if (meaningful.length < 2) errors.push(`${relative} keyboard sequence did not advance across controls`)

    const triggerFound = await page.evaluate(() => {
      const visible = (element) => {
        const style = getComputedStyle(element)
        const rect = element.getBoundingClientRect()
        return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0 && !element.disabled
      }
      const trigger = [...document.querySelectorAll('[data-open]')].find(visible)
      if (!trigger) return false
      trigger.id = trigger.id || '__freeze_acceptance_trigger__'
      return true
    })

    let dialogResult = { tested: false }
    if (triggerFound) {
      await page.click('#__freeze_acceptance_trigger__')
      await delay(180)
      dialogResult = await page.evaluate(() => {
        const visible = (element) => {
          const style = getComputedStyle(element)
          const rect = element.getBoundingClientRect()
          return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0
        }
        const dialog = [...document.querySelectorAll('dialog,[role="dialog"],[aria-modal="true"],.modal,.drawer')].find(visible)
        return { tested: true, opened: Boolean(dialog), activeInside: Boolean(dialog && dialog.contains(document.activeElement)) }
      })
      if (!dialogResult.opened) errors.push(`${relative} data-open trigger did not open a visible dialog/drawer`)
      if (dialogResult.opened && !dialogResult.activeInside) errors.push(`${relative} dialog opened without moving focus inside`)

      if (dialogResult.opened) {
        for (let index = 0; index < 12; index += 1) {
          await page.keyboard.press(index % 3 === 0 ? 'Shift+Tab' : 'Tab')
          const inside = await page.evaluate(() => {
            const visible = (element) => {
              const style = getComputedStyle(element)
              const rect = element.getBoundingClientRect()
              return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0
            }
            const dialog = [...document.querySelectorAll('dialog,[role="dialog"],[aria-modal="true"],.modal,.drawer')].find(visible)
            return Boolean(dialog && dialog.contains(document.activeElement))
          })
          if (!inside) errors.push(`${relative} focus escaped the top dialog during Tab cycle`)
        }
        await page.keyboard.press('Escape')
        await delay(120)
        const closed = await page.evaluate(() => {
          const visible = (element) => {
            const style = getComputedStyle(element)
            const rect = element.getBoundingClientRect()
            return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0
          }
          const openDialog = [...document.querySelectorAll('dialog,[role="dialog"],[aria-modal="true"],.modal,.drawer')].some(visible)
          return { openDialog, focusReturned: document.activeElement?.id === '__freeze_acceptance_trigger__' }
        })
        if (closed.openDialog) errors.push(`${relative} Escape did not close the top dialog`)
        if (!closed.focusReturned) errors.push(`${relative} focus did not return to the opener`)
      }
    }

    if (runtimeErrors.length) errors.push(`${relative} keyboard runtime errors: ${runtimeErrors.join(' | ')}`)
    if (consoleErrors.length) errors.push(`${relative} keyboard console errors: ${consoleErrors.join(' | ')}`)
    results.keyboard.push({ relative, meaningfulFocusStops: meaningful.length, sequence, dialogResult })
    await page.close()
  }
}

async function runPrint(browser, origin, errors, results) {
  for (const relative of PRINT_PAGES) {
    const { page, runtimeErrors, consoleErrors } = await openPage(browser, origin, relative, { width: 1280, height: 900 })
    await page.emulateMediaType('print')
    const metrics = await layoutMetrics(page)
    assertMetrics(relative, 'print-media', metrics, errors)
    const pdfPath = path.join(ARTIFACT_DIR, `${browserName}-${safeName(relative)}.pdf`)
    await page.pdf({ path: pdfPath, format: 'A4', printBackground: true, preferCSSPageSize: true })
    const bytes = fs.readFileSync(pdfPath)
    const pageCount = (bytes.toString('latin1').match(/\/Type\s*\/Page\b/g) || []).length
    if (bytes.length < 5000) errors.push(`${relative} generated PDF is unexpectedly small: ${bytes.length}`)
    if (pageCount < 1) errors.push(`${relative} generated PDF has no detectable page`)
    if (runtimeErrors.length) errors.push(`${relative} print runtime errors: ${runtimeErrors.join(' | ')}`)
    if (consoleErrors.length) errors.push(`${relative} print console errors: ${consoleErrors.join(' | ')}`)
    results.print.push({ relative, pdfBytes: bytes.length, pdfPages: pageCount, metrics })
    await page.close()
  }
}

async function runSensitive(browser, origin, errors, results) {
  for (const [relative, required] of SENSITIVE_CONTRACTS) {
    const { page, runtimeErrors, consoleErrors } = await openPage(browser, origin, relative)
    const text = await page.evaluate(() => String(document.body?.innerText || '').replace(/\s+/g, ' '))
    const missing = required.filter((term) => !text.includes(term))
    if (missing.length) errors.push(`${relative} missing sensitive-business disclosure terms: ${missing.join(', ')}`)
    if (runtimeErrors.length) errors.push(`${relative} sensitive runtime errors: ${runtimeErrors.join(' | ')}`)
    if (consoleErrors.length) errors.push(`${relative} sensitive console errors: ${consoleErrors.join(' | ')}`)
    results.sensitive.push({ relative, required, missing })
    await page.close()
  }
}

fs.mkdirSync(ARTIFACT_DIR, { recursive: true })
const executablePath = findBrowser()
const { server, origin } = await startServer()
const browser = await puppeteer.launch({
  executablePath,
  headless: true,
  args: ['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu', '--force-color-profile=srgb']
})
const startedAt = new Date().toISOString()
const errors = []
const results = { stress: [], keyboard: [], print: [], sensitive: [] }
try {
  await runStress(browser, origin, errors, results)
  await runKeyboard(browser, origin, errors, results)
  await runPrint(browser, origin, errors, results)
  await runSensitive(browser, origin, errors, results)
} finally {
  await browser.close()
  await new Promise((resolve) => server.close(resolve))
}

const report = {
  startedAt,
  finishedAt: new Date().toISOString(),
  platform: process.platform,
  browser: browserName,
  executablePath,
  counts: {
    stressPages: results.stress.length,
    keyboardPages: results.keyboard.length,
    printPages: results.print.length,
    sensitivePages: results.sensitive.length,
    errors: errors.length
  },
  errors,
  results
}
fs.writeFileSync(REPORT, `${JSON.stringify(report, null, 2)}\n`)
console.log(JSON.stringify(report.counts, null, 2))
for (const error of errors) console.error(`ERROR ${error}`)
if (errors.length) process.exit(1)
