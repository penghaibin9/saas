#!/usr/bin/env node
import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'

const root = process.cwd()
const requiredFiles = [
  'performance/k6/capacity.js',
  'performance/k6/lib/auth.js',
  'performance/k6/lib/config.js',
  'performance/tools/prepare_k6_credentials.py',
  'performance/tools/audit_capacity_runtime.py',
  'performance/tools/probe_observability.py',
  'performance/capacity-report-template.md',
  '.github/workflows/capacity-load-gates.yml',
]

const failures = []
const read = (file) => fs.readFileSync(path.join(root, file), 'utf8')

for (const file of requiredFiles) {
  if (!fs.existsSync(path.join(root, file))) failures.push(`missing ${file}`)
}

if (failures.length === 0) {
  const k6Files = [
    'performance/k6/capacity.js',
    'performance/k6/lib/auth.js',
    'performance/k6/lib/config.js',
  ]
  const k6 = k6Files.map(read).join('\n')
  const workflow = read('.github/workflows/capacity-load-gates.yml')
  const runtimeAudit = read('performance/tools/audit_capacity_runtime.py')
  const probe = read('performance/tools/probe_observability.py')
  const forbiddenLoadPaths = [
    /\/upload(?:\/|\b)/i,
    /\/download(?:\/|\b)/i,
    /file-center/i,
    /file_center/i,
    /attachments?/i,
    /clamav/i,
    /\bcos\b/i,
  ]
  for (const pattern of forbiddenLoadPaths) {
    if (pattern.test(k6)) failures.push(`k6 scenarios must not exercise file traffic: ${pattern}`)
  }
  const requiredEndpoints = [
    '/api/v1/mobile/home',
    '/api/v1/mobile/me/messages',
    '/api/v1/mobile/teacher/overview',
    '/api/v1/mobile/teacher/todos',
  ]
  for (const endpoint of requiredEndpoints) {
    if (!k6.includes(endpoint)) failures.push(`missing core endpoint ${endpoint}`)
  }
  for (const profile of ['smoke', 'baseline', 'p500', 'p1000', 'p3000']) {
    if (!k6.includes(`${profile}:`)) failures.push(`missing profile ${profile}`)
  }
  const requiredGuards = [
    'K6_ALLOW_HIGH_LOAD',
    'K6_ALLOW_PRODUCTION_HIGH_LOAD',
    'High-load profiles require pre-issued',
  ]
  for (const guard of requiredGuards) {
    if (!k6.includes(guard)) failures.push(`missing safety guard ${guard}`)
  }
  const requiredThresholds = [
    "http_req_failed: ['rate<0.005']",
    "http_req_duration: ['p(95)<1000', 'p(99)<2000']",
    "checks: ['rate>0.995']",
  ]
  for (const threshold of requiredThresholds) {
    if (!k6.includes(threshold)) failures.push(`missing threshold ${threshold}`)
  }
  if (!/permissions:\s*\n\s*contents:\s*read/m.test(workflow)) {
    failures.push('workflow permissions must be contents: read')
  }
  if (!workflow.includes('workflow_dispatch:')) failures.push('workflow_dispatch is required')
  if (!workflow.includes('schedule:')) failures.push('nightly schedule is required')
  if (!workflow.includes('grafana/k6:0.54.0')) failures.push('k6 Docker image must be pinned')
  if (!workflow.includes('PERF_STUDENT_TOKENS_JSON')) failures.push('student token secret is required')
  if (!workflow.includes('PERF_TEACHER_TOKENS_JSON')) failures.push('teacher token secret is required')
  if (!workflow.includes('PERF_INTERNAL_OPS_TOKEN')) failures.push('ops token secret is required')
  if (!workflow.includes('probe_observability.py')) failures.push('observability probe must run before load')

  const runtimeRequirements = [
    'REDIS_URL is required before capacity validation',
    'scaled runtime requires SCHEDULER_MODE=external',
    'CAPACITY_DB_CONNECTION_BUDGET',
    'INTERNAL_OPS_TOKEN',
  ]
  for (const requirement of runtimeRequirements) {
    if (!runtimeAudit.includes(requirement)) failures.push(`runtime audit missing ${requirement}`)
  }
  for (const endpoint of ['/health/ready', '/internal/metrics']) {
    if (!probe.includes(endpoint)) failures.push(`observability probe missing ${endpoint}`)
  }
  if (!probe.includes('X-Ops-Token')) failures.push('observability probe must use X-Ops-Token')

  const secretLeakPatterns = [
    /password\s*[:=]\s*['"][^'"]+['"]/i,
    /Bearer\s+[A-Za-z0-9._-]{20,}/,
    /sk-[A-Za-z0-9_-]{16,}/,
  ]
  for (const pattern of secretLeakPatterns) {
    if (pattern.test(k6)) failures.push(`possible hard-coded secret in k6 files: ${pattern}`)
  }
}

if (failures.length) {
  console.error('Capacity gate contract failed:')
  for (const failure of failures) console.error(`- ${failure}`)
  process.exit(1)
}

console.log('Capacity gate contract passed')
