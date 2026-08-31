#!/usr/bin/env node
import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { chromium } from '@playwright/test'

const targetsJson = process.env.INTERNSHIP_V8_BROWSER_TARGETS_JSON || ''
const outputPath = process.env.INTERNSHIP_V8_BROWSER_JSON_OUT || ''
if (!targetsJson || !outputPath) {
  console.error('INTERNSHIP_V8_BROWSER_TARGETS_JSON and INTERNSHIP_V8_BROWSER_JSON_OUT are required')
  process.exit(2)
}

let targets
try { targets = JSON.parse(targetsJson) } catch (error) {
  console.error(`invalid INTERNSHIP_V8_BROWSER_TARGETS_JSON: ${error.message}`)
  process.exit(2)
}
if (!Array.isArray(targets) || !targets.length) {
  console.error('browser targets must be a non-empty array of {name,url,storageState}')
  process.exit(2)
}

const longTaskBudgetMs = Number(process.env.INTERNSHIP_V8_LONG_TASK_BUDGET_MS || 200)
const heapBudgetBytes = Number(process.env.INTERNSHIP_V8_HEAP_BUDGET_BYTES || 134217728)
const browser = await chromium.launch({ headless: true, args: ['--enable-precise-memory-info'] })
const results = []
const contexts = new Map()
try {
  for (const target of targets) {
    if (!target?.name || !target?.url || !target?.storageState) {
      throw new Error('every browser target requires name, url and storageState')
    }
    const storageState = path.resolve(String(target.storageState))
    if (!fs.existsSync(storageState)) throw new Error(`${target.name}: storageState not found: ${storageState}`)
    const contextKey = JSON.stringify([storageState, target.sessionStorage || {}])
    let context = contexts.get(contextKey)
    if (!context) {
      context = await browser.newContext({ storageState })
      if (target.sessionStorage && typeof target.sessionStorage === 'object') {
        await context.addInitScript((items) => {
          for (const [key, value] of Object.entries(items)) sessionStorage.setItem(key, String(value))
        }, target.sessionStorage)
      }
      contexts.set(contextKey, context)
    }
    const page = await context.newPage()
    await page.addInitScript(() => {
      globalThis.__internshipV8LongTasks = []
      globalThis.__internshipV8LongTaskSupported = typeof PerformanceObserver !== 'undefined'
        && PerformanceObserver.supportedEntryTypes?.includes('longtask')
      if (globalThis.__internshipV8LongTaskSupported) {
        new PerformanceObserver((list) => {
          globalThis.__internshipV8LongTasks.push(...list.getEntries().map((entry) => ({
            startTime: entry.startTime, duration: entry.duration, name: entry.name
          })))
        }).observe({ type: 'longtask', buffered: true })
      }
    })
    const response = await page.goto(String(target.url), { waitUntil: 'networkidle', timeout: 60_000 })
    await page.waitForTimeout(1500)
    const metrics = await page.evaluate(() => {
      const nav = performance.getEntriesByType('navigation')[0]
      const resources = performance.getEntriesByType('resource')
      const longTasks = globalThis.__internshipV8LongTasks || []
      const memory = performance.memory || null
      return {
        title: document.title,
        longTaskSupported: globalThis.__internshipV8LongTaskSupported === true,
        longTasks,
        longTaskTotalMs: longTasks.reduce((sum, item) => sum + item.duration, 0),
        longTaskMaxMs: longTasks.reduce((max, item) => Math.max(max, item.duration), 0),
        resourceTransferBytes: resources.reduce((sum, item) => sum + Number(item.transferSize || 0), 0),
        resourceDecodedBytes: resources.reduce((sum, item) => sum + Number(item.decodedBodySize || 0), 0),
        navigationMs: nav ? nav.duration : null,
        domContentLoadedMs: nav ? nav.domContentLoadedEventEnd : null,
        loadEventMs: nav ? nav.loadEventEnd : null,
        usedJSHeapBytes: memory ? memory.usedJSHeapSize : null,
        totalJSHeapBytes: memory ? memory.totalJSHeapSize : null,
      }
    })
    const checks = {
      http: Boolean(response && response.ok()),
      authenticatedRoute: !new URL(page.url()).pathname.endsWith('/login'),
      longTaskSupported: metrics.longTaskSupported,
      longTask: metrics.longTaskMaxMs <= longTaskBudgetMs,
      memoryAvailable: Number.isFinite(metrics.usedJSHeapBytes),
      memory: Number.isFinite(metrics.usedJSHeapBytes) && metrics.usedJSHeapBytes <= heapBudgetBytes,
    }
    results.push({
      name: target.name, url: target.url, finalUrl: page.url(), status: response?.status() || null,
      budgets: { longTaskMaxMs: longTaskBudgetMs, usedJSHeapBytes: heapBudgetBytes },
      metrics, checks, passed: Object.values(checks).every(Boolean),
    })
    await page.close()
  }
} finally {
  for (const context of contexts.values()) await context.close()
  await browser.close()
}

const artifact = {
  schema: 'internship-v8-browser-scale-evidence/1',
  measuredAt: new Date().toISOString(),
  targets: results,
  passed: results.length === targets.length && results.every((item) => item.passed),
}
const resolvedOutput = path.resolve(outputPath)
fs.mkdirSync(path.dirname(resolvedOutput), { recursive: true })
fs.writeFileSync(resolvedOutput, JSON.stringify(artifact, null, 2))
console.log(`internship-v8 browser evidence passed=${artifact.passed} artifact=${resolvedOutput}`)
process.exit(artifact.passed ? 0 : 1)
