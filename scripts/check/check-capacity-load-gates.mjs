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
  'performance/tools/seed_local_capacity_env.py',
  'performance/tools/evaluate_capacity_result.py',
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
  const localSeed = read('performance/tools/seed_local_capacity_env.py')
  const evaluator = read('performance/tools/evaluate_capacity_result.py')
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
    '/api/v1/student-mini/todos?status=PENDING&page=1&pageSize=20',
    '/api/v1/mobile/performance/student/messages-page',
    '/api/v1/mobile/performance/teacher/workbench',
    '/api/v1/mobile/performance/teacher/todos-page',
    '/api/v1/mobile/performance/teacher/risk-students-page',
  ]
  for (const endpoint of requiredEndpoints) {
    if (!k6.includes(endpoint)) failures.push(`missing core endpoint ${endpoint}`)
  }
  for (const profile of ['smoke', 'baseline', 'p300', 'p500', 'p1000', 'p3000']) {
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
    "summaryTrendStats: ['avg', 'min', 'med', 'max', 'p(90)', 'p(95)', 'p(99)']",
  ]
  for (const threshold of requiredThresholds) {
    if (!k6.includes(threshold)) failures.push(`missing threshold/reporting contract ${threshold}`)
  }
  if (!k6.includes('LOCAL_HIGH_LOAD_DIAGNOSTIC')) {
    failures.push('local high-load diagnostic mode must be explicit')
  }
  if (!k6.includes('isLocalBaseUrl(BASE_URL) && HIGH_LOAD_PROFILES.has(PROFILE)')) {
    failures.push('only local high-load profiles may skip k6 latency thresholds')
  }
  if (!/permissions:\s*\n\s*contents:\s*read/m.test(workflow)) {
    failures.push('workflow permissions must be contents: read')
  }
  if (!workflow.includes('workflow_dispatch:')) failures.push('workflow_dispatch is required')
  if (!workflow.includes('schedule:')) failures.push('nightly schedule is required')
  if (!workflow.includes('grafana/k6:0.54.0')) failures.push('k6 Docker image must be pinned')
  if (!workflow.includes('local-capacity:')) failures.push('self-contained local capacity job is required')
  if (!workflow.includes('profile: [smoke, baseline, p300, p500]')) {
    failures.push('local capacity matrix must run smoke, baseline, p300 and p500')
  }
  if (!workflow.includes('capacity-local-${{ matrix.profile }}-${{ github.run_id }}')) {
    failures.push('local capacity artifacts must be profile-specific')
  }
  if (!workflow.includes('evaluate_capacity_result.py')) failures.push('capacity verdict evaluation step is required')
  if (!workflow.includes('capacity-verdict.json')) failures.push('capacity verdict artifact is required')
  if (!workflow.includes('mysql:8.0')) failures.push('local capacity must use MySQL 8')
  if (!workflow.includes('redis:7-alpine')) failures.push('local capacity must use Redis')
  if (!workflow.includes('alembic upgrade head')) failures.push('local capacity must run real migrations')
  if (!workflow.includes('seed_local_capacity_env.py')) failures.push('local capacity must seed ephemeral identities')
  if (!workflow.includes('--token-count "$token_count"')) failures.push('local high load must generate per-VU token pools')
  if (!workflow.includes('K6_ALLOW_HIGH_LOAD: "true"')) failures.push('local p300/p500 matrix must explicitly unlock high load')
  if (!workflow.includes('-e K6_ALLOW_HIGH_LOAD')) failures.push('local k6 container must receive high-load unlock')
  if (!workflow.includes('--network host')) failures.push('local k6 must reach the host backend explicitly')
  if (!workflow.includes('PERF_STUDENT_TOKENS_JSON')) failures.push('student token secret is required')
  if (!workflow.includes('PERF_TEACHER_TOKENS_JSON')) failures.push('teacher token secret is required')
  if (!workflow.includes('PERF_STUDENT_CREDENTIALS_JSON')) failures.push('student credential secret fallback is required')
  if (!workflow.includes('PERF_TEACHER_CREDENTIALS_JSON')) failures.push('teacher credential secret fallback is required')
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
  if (!probe.includes('"targetMode": _target_mode(base)')) {
    failures.push('observability probe must record local versus remote target mode')
  }
  if (!localSeed.includes('create_access_token')) failures.push('local seed must issue ephemeral signed tokens')
  if (!localSeed.includes('StudentProfile')) failures.push('local seed must create a real student profile')
  if (!localSeed.includes('--token-count')) failures.push('local seed must support explicit token pool size')
  if (/password|accessToken/i.test(localSeed) && /print\([^\n]*(password|token)/i.test(localSeed)) {
    failures.push('local seed must not print credentials or tokens')
  }
  for (const verdictContract of ['minimumRequests', 'httpFailureRate', 'businessCheckRate', 'p95Ms', 'p99Ms', 'readinessBefore', 'readinessAfter', 'non2xxAfter']) {
    if (!evaluator.includes(verdictContract)) failures.push(`capacity evaluator missing ${verdictContract}`)
  }
  for (const profile of ['"p300": 10000', '"p500": 20000']) {
    if (!evaluator.includes(profile)) failures.push(`capacity evaluator missing high-load minimum ${profile}`)
  }
  for (const diagnosticContract of ['"local-functional"', '"full-capacity"', '"latencyGateEnforced"', '"enforced"']) {
    if (!evaluator.includes(diagnosticContract)) {
      failures.push(`capacity evaluator missing target-aware contract ${diagnosticContract}`)
    }
  }
  if (!evaluator.includes('target_mode == "local"')) {
    failures.push('only local targets may use functional-only high-load verdicts')
  }

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
