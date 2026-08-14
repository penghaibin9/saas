import fs from 'node:fs/promises'
import path from 'node:path'
import { test as base, expect } from '@playwright/test'

const LEGACY_GOLDEN_FILES = new Set([
  'golden-rollout-confirmation-documents.spec.mjs',
  'golden-rollout-cyclical-work.spec.mjs',
  'golden-rollout-evaluation-results.spec.mjs',
  'golden-rollout-exception-recovery.spec.mjs',
  'golden-rollout-implementation-config.spec.mjs',
  'golden-rollout-master-data.spec.mjs',
  'golden-rollout-material-evidence.spec.mjs',
  'golden-rollout-message-campaign-records.spec.mjs',
  'golden-rollout-message-center.spec.mjs',
  'golden-rollout-message-governance.spec.mjs',
  'golden-rollout-message-settings.spec.mjs',
  'golden-rollout-process-guidance.spec.mjs',
  'golden-rollout-review-queues.spec.mjs',
  'golden-rollout-risk-workspaces.spec.mjs',
  'golden-rollout-student-360.spec.mjs',
  'golden-rollout-student-affairs-aid.spec.mjs',
  'golden-rollout-student-affairs-discipline.spec.mjs',
  'golden-rollout-student-affairs-domain-hubs.spec.mjs',
  'golden-rollout-student-affairs-funding.spec.mjs'
])

function testClientIp(testInfo) {
  const seed = [...String(testInfo.testId || testInfo.title)].reduce((sum, char) => sum + char.charCodeAt(0), 0)
  return `10.253.${Math.floor(seed / 200) % 200}.${20 + (seed % 200)}`
}

function safeLabel(label) {
  return String(label || 'page').replace(/[^a-zA-Z0-9_-]+/g, '-').replace(/^-+|-+$/g, '') || 'page'
}

async function prepareLegacyGoldenPage(page, testInfo) {
  const filename = path.basename(String(testInfo.file || ''))
  if (!LEGACY_GOLDEN_FILES.has(filename)) return
  const { openGoldenStaffPage } = await import('./golden-staff-page.mjs')
  await openGoldenStaffPage(page, '/workbench')
}

export async function attachObservability(page, testInfo, { label = 'page', clientIp = '' } = {}) {
  const network = []
  const consoleErrors = []
  const pageErrors = []
  const started = new Map()
  const prefix = safeLabel(label)
  let finalized = false

  if (clientIp) await page.setExtraHTTPHeaders({ 'X-Forwarded-For': clientIp })

  page.on('request', (request) => {
    if (!request.url().includes('/api/')) return
    started.set(request, Date.now())
    network.push({
      type: 'request',
      at: new Date().toISOString(),
      method: request.method(),
      url: request.url()
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

  return async function finalizeObservability() {
    if (finalized) return
    finalized = true
    const dir = testInfo.outputDir
    await fs.mkdir(dir, { recursive: true })
    const write = async (suffix, data) => {
      const name = `${prefix}-${suffix}`
      const file = path.join(dir, name)
      await fs.writeFile(file, data, 'utf8')
      await testInfo.attach(name, {
        path: file,
        contentType: name.endsWith('.json') ? 'application/json' : 'text/plain'
      })
    }
    await write('api-network.json', JSON.stringify(network, null, 2))
    await write('console-errors.json', JSON.stringify(consoleErrors, null, 2))
    await write('page-errors.json', JSON.stringify(pageErrors, null, 2))
    if (pageErrors.length) {
      throw new Error(`${prefix} had unhandled browser page errors: ${pageErrors.map((item) => item.message).join(' | ')}`)
    }
  }
}

export const test = base.extend({
  page: async ({ page }, use, testInfo) => {
    const clientIp = testClientIp(testInfo)
    await page.setExtraHTTPHeaders({ 'X-Forwarded-For': clientIp })
    await prepareLegacyGoldenPage(page, testInfo)
    const finalize = await attachObservability(page, testInfo, { label: 'default-page', clientIp })
    try {
      await use(page)
    } finally {
      await finalize()
    }
  }
})

export { expect }
