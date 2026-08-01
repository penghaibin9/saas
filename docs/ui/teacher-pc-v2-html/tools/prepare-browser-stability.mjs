#!/usr/bin/env node

import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const toolDir = path.dirname(fileURLToPath(import.meta.url))
const runnerPath = path.join(toolDir, 'run-browser-regression.mjs')
let source = fs.readFileSync(runnerPath, 'utf8').replace(/\r\n/g, '\n')

source = source.replace(
  "const concurrency = Math.max(1, Number(readArg('--concurrency') || 4))",
  "const concurrency = Math.min(2, Math.max(1, Number(readArg('--concurrency') || 2)))"
)
source = source.replace(
  "const concurrency = Math.min(3, Math.max(1, Number(readArg('--concurrency') || 3)))",
  "const concurrency = Math.min(2, Math.max(1, Number(readArg('--concurrency') || 2)))"
)
source = source.replace(
  "const retries = Math.max(0, Number(readArg('--retries') || 0))",
  "const retries = Math.max(0, Number(readArg('--retries') || 3))"
)
source = source.replace(
  "const retries = Math.max(0, Number(readArg('--retries') || 2))",
  "const retries = Math.max(0, Number(readArg('--retries') || 3))"
)
if (!source.includes("const retries = Math.max(0, Number(readArg('--retries') || 3))")) {
  source = source.replace(
    "const virtualTimeMs = Math.max(1000, Number(readArg('--virtual-time-ms') || 4500))\nconst smokeCount",
    "const virtualTimeMs = Math.max(1000, Number(readArg('--virtual-time-ms') || 4500))\nconst retries = Math.max(0, Number(readArg('--retries') || 3))\nconst smokeCount"
  )
}

if (!source.includes('const duplicateIdDetails = duplicateIds.map')) {
  source = source.replace(
    "    const duplicateIds = [...new Set(ids.filter((id, index) => ids.indexOf(id) !== index))];\n    const focusables",
    `    const duplicateIds = [...new Set(ids.filter((id, index) => ids.indexOf(id) !== index))];
    const duplicateIdDetails = duplicateIds.map((id) => ({
      id,
      nodes: [...document.querySelectorAll('[id]')]
        .filter((element) => element.id === id)
        .map((element) => ({
          tag: String(element.tagName || '').toLowerCase(),
          className: String(element.className || ''),
          role: element.getAttribute('role') || '',
          ariaModal: element.getAttribute('aria-modal') || '',
          hidden: Boolean(element.hidden),
          html: String(element.outerHTML || '').slice(0, 1200)
        }))
    }));
    const focusables`
  )
  source = source.replace(
    "      duplicateIds,\n      brokenImages,",
    "      duplicateIds,\n      duplicateIdDetails,\n      brokenImages,"
  )
}

if (!source.includes('async function renderAttempt(')) {
  source = source.replace('async function renderOne(chrome, origin, html, viewport) {', 'async function renderAttempt(chrome, origin, html, viewport) {')
}

if (!source.includes('const transientIssueCodes = new Set')) {
  const anchor = '\nasync function pool(items, limit, worker) {'
  const wrapper = `
const transientIssueCodes = new Set(['NO_PROBE', 'TIMEOUT', 'CHROME_EXIT'])

function shouldRetry(result) {
  const errors = result.issues.filter((issue) => issue.severity === 'error')
  return errors.length > 0 && errors.every((issue) => transientIssueCodes.has(issue.code))
}

function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

async function renderOne(chrome, origin, html, viewport) {
  const attempts = []
  let result
  for (let attempt = 1; attempt <= retries + 1; attempt += 1) {
    result = await renderAttempt(chrome, origin, html, viewport)
    attempts.push({
      attempt,
      status: result.status,
      issueCodes: result.issues.map((issue) => issue.code),
      exitCode: result.exitCode,
      timedOut: result.timedOut,
      probeCaptured: Boolean(result.probe)
    })
    if (!shouldRetry(result) || attempt > retries) break
    await wait(300 * (2 ** (attempt - 1)))
  }
  result.attempts = attempts
  return result
}
`
  if (!source.includes(anchor)) throw new Error('pool anchor missing')
  source = source.replace(anchor, `${wrapper}${anchor}`)
}

source = source.replace(
  "  if (report.duplicateIds.length) issues.push({ severity: 'error', code: 'DUPLICATE_ID', message: `${report.duplicateIds.length} 个重复 id` })",
  "  if (report.duplicateIds.length) issues.push({ severity: 'error', code: 'DUPLICATE_ID', message: `${report.duplicateIds.length} 个重复 id：${report.duplicateIds.join(', ')}` })"
)

if (!source.includes('`- 重试上限：**${summary.retryLimit}**`')) {
  source = source.replace(
    "    `- 警告：**${summary.warningRenders}**`,\n    `- 最终状态",
    "    `- 警告：**${summary.warningRenders}**`,\n    `- 重试上限：**${summary.retryLimit}**`,\n    `- 发生重试的渲染：**${summary.retriedRenders}**`,\n    `- 瞬态失败重试后恢复：**${summary.recoveredTransientFailures}**`,\n    `- 最终状态"
  )
}

if (!source.includes('retryLimit: retries')) {
  source = source.replace(
    "    warningRenders: warnings.length,\n    durationSeconds:",
    "    warningRenders: warnings.length,\n    retryLimit: retries,\n    retriedRenders: results.filter((result) => (result.attempts || []).length > 1).length,\n    recoveredTransientFailures: results.filter((result) => result.status === 'PASS' && (result.attempts || []).length > 1).length,\n    durationSeconds:"
  )
}

source = source.replace(
  "  console.log(`并发: ${concurrency}，报告目录: ${reportRoot}`)",
  "  console.log(`并发: ${concurrency}，瞬态重试: ${retries}，报告目录: ${reportRoot}`)"
)

const requiredMarkers = [
  "const concurrency = Math.min(2, Math.max(1, Number(readArg('--concurrency') || 2)))",
  "const retries = Math.max(0, Number(readArg('--retries') || 3))",
  'const duplicateIdDetails = duplicateIds.map',
  'async function renderAttempt(',
  'const transientIssueCodes = new Set',
  'retryLimit: retries'
]
for (const marker of requiredMarkers) {
  if (!source.includes(marker)) throw new Error(`browser stability marker missing: ${marker}`)
}

fs.writeFileSync(runnerPath, source, 'utf8')
console.log('browser regression stability and diagnostics prepared')
