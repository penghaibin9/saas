#!/usr/bin/env node

import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const toolDir = path.dirname(fileURLToPath(import.meta.url))
const runnerPath = path.join(toolDir, 'run-browser-regression-persistent.mjs')
let source = fs.readFileSync(runnerPath, 'utf8').replace(/\r\n/g, '\n')

if (!source.includes('function withTimeout(')) {
  source = source.replace(
    "const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms))",
    `const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

function withTimeout(promise, ms, label) {
  let timer
  const timeout = new Promise((_, reject) => {
    timer = setTimeout(() => reject(new Error(\`${'${label}'} exceeded ${'${ms}'}ms\`)), ms)
  })
  return Promise.race([promise, timeout]).finally(() => clearTimeout(timer))
}`
  )
}

source = source.replace(
  "  const page = await browser.newPage()",
  "  const page = await withTimeout(browser.newPage(), 10000, 'browser.newPage')\n  page.setDefaultTimeout(timeoutMs)\n  page.setDefaultNavigationTimeout(timeoutMs)"
)
source = source.replace(
  "    const probe = await collectProbe(page)",
  "    const probe = await withTimeout(collectProbe(page), Math.min(timeoutMs, 15000), 'collectProbe')"
)
source = source.replace(
  "      await page.screenshot({ path: screenshotPath, fullPage: true })",
  "      await withTimeout(page.screenshot({ path: screenshotPath, fullPage: true }), Math.min(timeoutMs, 15000), 'screenshot')"
)
source = source.replace(
  "    await page.close().catch(() => {})",
  "    await Promise.race([page.close().catch(() => {}), delay(3000)])"
)

const required = [
  'function withTimeout(',
  "withTimeout(browser.newPage(), 10000, 'browser.newPage')",
  "withTimeout(collectProbe(page), Math.min(timeoutMs, 15000), 'collectProbe')",
  "Promise.race([page.close().catch(() => {}), delay(3000)])"
]
for (const marker of required) {
  if (!source.includes(marker)) throw new Error(`persistent stability marker missing: ${marker}`)
}

fs.writeFileSync(runnerPath, source, 'utf8')
console.log('persistent browser page operation bounds prepared')
