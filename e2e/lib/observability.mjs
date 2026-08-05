import fs from 'node:fs/promises'
import path from 'node:path'
import { test as base, expect } from '@playwright/test'

const SECRET_KEY = /(authorization|cookie|set-cookie|password|token|secret)/i

function redact(value, depth = 0) {
  if (depth > 5) return '[truncated]'
  if (Array.isArray(value)) return value.slice(0, 50).map((item) => redact(item, depth + 1))
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.entries(value).map(([key, item]) => [
      key,
      SECRET_KEY.test(key) ? '[redacted]' : redact(item, depth + 1)
    ]))
  }
  if (typeof value === 'string' && value.length > 2_000) return `${value.slice(0, 2_000)}…`
  return value
}

function safeJson(text) {
  if (!text) return null
  try { return redact(JSON.parse(text)) } catch { return String(text).slice(0, 2_000) }
}

function testClientIp(testInfo) {
  const seed = [...String(testInfo.testId || testInfo.title)].reduce((sum, char) => sum + char.charCodeAt(0), 0)
  return `10.253.${Math.floor(seed / 200) % 200}.${20 + (seed % 200)}`
}

export const test = base.extend({
  page: async ({ page }, use, testInfo) => {
    const network = []
    const consoleErrors = []
    const pageErrors = []
    const started = new Map()

    // The backend still enforces its real 10 logins/minute/IP guard. Each legitimate
    // Playwright test receives a distinct trusted-proxy client IP so serial role flows
    // do not incorrectly throttle one another on the shared GitHub runner loopback.
    await page.setExtraHTTPHeaders({ 'X-Forwarded-For': testClientIp(testInfo) })

    page.on('request', (request) => {
      if (!request.url().includes('/api/')) return
      started.set(request, Date.now())
      network.push({
        type: 'request',
        at: new Date().toISOString(),
        method: request.method(),
        url: request.url(),
        headers: redact(request.headers()),
        body: safeJson(request.postData())
      })
    })
    page.on('response', (response) => {
      const request = response.request()
      if (!request.url().includes('/api/')) return
      network.push({
        type: 'response',
        at: new Date().toISOString(),
        method: request.method(),
        url: response.url(),
        status: response.status(),
        durationMs: started.has(request) ? Date.now() - started.get(request) : null
      })
    })
    page.on('requestfailed', (request) => {
      if (!request.url().includes('/api/')) return
      network.push({
        type: 'requestfailed',
        at: new Date().toISOString(),
        method: request.method(),
        url: request.url(),
        failure: request.failure()
      })
    })
    page.on('console', (message) => {
      if (message.type() !== 'error') return
      const text = message.text()
      if (/favicon|source map|Vue Devtools/i.test(text)) return
      consoleErrors.push({ at: new Date().toISOString(), text })
    })
    page.on('pageerror', (error) => {
      pageErrors.push({ at: new Date().toISOString(), message: error.message, stack: error.stack })
    })

    await use(page)

    const dir = testInfo.outputDir
    await fs.mkdir(dir, { recursive: true })
    const write = async (name, data) => {
      const file = path.join(dir, name)
      await fs.writeFile(file, data, 'utf8')
      await testInfo.attach(name, { path: file, contentType: name.endsWith('.json') ? 'application/json' : 'text/plain' })
    }
    await write('api-network.json', JSON.stringify(network, null, 2))
    await write('console-errors.json', JSON.stringify(consoleErrors, null, 2))
    await write('page-errors.json', JSON.stringify(pageErrors, null, 2))

    if (pageErrors.length) {
      throw new Error(`Unhandled browser page errors: ${pageErrors.map((item) => item.message).join(' | ')}`)
    }
  }
})

export { expect }
