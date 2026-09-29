import http from 'k6/http'
import { check, sleep } from 'k6'
import exec from 'k6/execution'

const numberEnv = (name, fallback) => {
  const value = Number(__ENV[name] || fallback)
  if (!Number.isFinite(value)) throw new Error(`${name} must be numeric`)
  return value
}

const BASE_URL = String(__ENV.G20_BASE_URL || '').replace(/\/$/, '')
const VUS = Math.trunc(numberEnv('G20_VUS', 20))
const WARMUP = String(__ENV.G20_WARMUP || '30s')
const HOLD = String(__ENV.G20_HOLD || '60s')
const RAMPDOWN = String(__ENV.G20_RAMPDOWN || '30s')
const THINK_SECONDS = Math.max(0, numberEnv('G20_THINK_SECONDS', 0.2))
const P95_MS = Math.max(1, numberEnv('G20_P95_MS', 1500))
const P99_MS = Math.max(P95_MS, numberEnv('G20_P99_MS', 3000))
const MAX_ERROR_RATE = Math.max(0, Math.min(1, numberEnv('G20_MAX_ERROR_RATE', 0.01)))
const TOKEN = String(__ENV.G20_AUTH_TOKEN || '')
const TOKEN_FILE = String(__ENV.G20_AUTH_TOKENS_FILE || '').trim()
const REAL_RUN_ACK = String(__ENV.G20_REAL_RUN_ACK || '').toUpperCase() === 'YES'
const BATCH_ID = String(__ENV.G20_BATCH_ID || '')
const INTERNSHIP_ID = String(__ENV.G20_INTERNSHIP_ID || '')

if (!BASE_URL) throw new Error('G20_BASE_URL is required')
if (VUS < 1 || VUS > 20000) throw new Error('G20_VUS must be between 1 and 20000')
if (VUS >= 5000 && !REAL_RUN_ACK) {
  throw new Error('5000+ VU run requires G20_REAL_RUN_ACK=YES to prevent accidental load against a real service')
}

const rawPaths = String(__ENV.G20_PATHS || '/health')
  .split(',')
  .map(value => value.trim())
  .filter(Boolean)

if (!rawPaths.length) throw new Error('G20_PATHS must contain at least one path')

const renderPath = path => path
  .replaceAll('{batchId}', encodeURIComponent(BATCH_ID))
  .replaceAll('{internshipId}', encodeURIComponent(INTERNSHIP_ID))

const paths = rawPaths.map(renderPath)
const businessPaths = paths.filter(path => !['/health', '/api/v1/health'].includes(path))
const missingPlaceholders = paths.filter(path => /\{[^}]+\}/.test(path))

if (missingPlaceholders.length) {
  throw new Error(`Unresolved G20 path placeholders: ${missingPlaceholders.join(', ')}`)
}

const businessScenarioConfigured = businessPaths.length > 0

const loadAuthTokens = () => {
  let values = []
  if (TOKEN_FILE) {
    const parsed = JSON.parse(open(TOKEN_FILE))
    if (!Array.isArray(parsed)) throw new Error('G20_AUTH_TOKENS_FILE must contain a JSON array')
    values = parsed
  } else if (TOKEN) {
    values = [TOKEN]
  }
  const normalized = values.map(value => String(value || '').trim()).filter(Boolean)
  const unique = Array.from(new Set(normalized))
  if (normalized.length !== unique.length) {
    throw new Error('G20 auth token pool contains duplicate identities/tokens')
  }
  return unique
}

const authTokens = loadAuthTokens()
const authIdentityCount = authTokens.length
const authConfigured = authIdentityCount > 0
const identityPoolMatchesVus = authIdentityCount >= VUS

export const options = {
  scenarios: {
    internship_procurement: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: WARMUP, target: Math.min(VUS, Math.max(1, Math.ceil(VUS * 0.2))) },
        { duration: WARMUP, target: VUS },
        { duration: HOLD, target: VUS },
        { duration: RAMPDOWN, target: 0 }
      ],
      gracefulRampDown: '30s'
    }
  },
  thresholds: {
    http_req_failed: [`rate<${MAX_ERROR_RATE}`],
    http_req_duration: [`p(95)<${P95_MS}`, `p(99)<${P99_MS}`]
  },
  summaryTrendStats: ['avg', 'min', 'med', 'max', 'p(90)', 'p(95)', 'p(99)'],
  discardResponseBodies: true,
  noConnectionReuse: false,
  userAgent: 'Yueke-Internship-G20-k6/1.0'
}

export default function () {
  const index = exec.scenario.iterationInTest % paths.length
  const path = paths[index]
  const token = authTokens.length ? authTokens[(exec.vu.idInTest - 1) % authTokens.length] : ''
  const headers = token ? { Authorization: `Bearer ${token}` } : {}
  const response = http.get(`${BASE_URL}${path}`, {
    headers,
    tags: {
      g20_path: path,
      g20_kind: path === '/health' ? 'health' : 'business'
    }
  })
  check(response, {
    'HTTP status is 2xx': res => res.status >= 200 && res.status < 300
  })
  if (THINK_SECONDS > 0) sleep(THINK_SECONDS)
}

const thresholdStatus = metrics => {
  const out = {}
  for (const [metricName, metric] of Object.entries(metrics || {})) {
    if (!metric.thresholds) continue
    out[metricName] = Object.fromEntries(
      Object.entries(metric.thresholds).map(([name, value]) => [name, Boolean(value && value.ok)])
    )
  }
  return out
}

export function handleSummary(data) {
  const evidence = {
    schemaVersion: 1,
    gate: 'G20',
    generator: 'k6',
    generatedAt: new Date().toISOString(),
    target: BASE_URL,
    requestedVus: VUS,
    procurementMinimumVus: 5000,
    realRunAcknowledged: REAL_RUN_ACK,
    warmup: WARMUP,
    hold: HOLD,
    rampdown: RAMPDOWN,
    configuredPaths: paths,
    businessPaths,
    businessScenarioConfigured,
    authConfigured,
    authIdentityCount,
    identityPoolMatchesVus,
    tokenPoolFileConfigured: Boolean(TOKEN_FILE),
    operationalThresholds: {
      p95Ms: P95_MS,
      p99Ms: P99_MS,
      maxErrorRate: MAX_ERROR_RATE,
      note: 'Operational defaults are configurable and must be replaced by the school/tender SLA when formally specified.'
    },
    thresholdStatus: thresholdStatus(data.metrics),
    metrics: data.metrics,
    qualificationHint: {
      g20QualifiedCandidate:
        VUS >= 5000 &&
        REAL_RUN_ACK &&
        businessScenarioConfigured &&
        authConfigured &&
        identityPoolMatchesVus,
      note: 'Formal PASS requires at least one distinct authenticated test identity per requested VU. Final qualification is decided by g20_validate_evidence.py.'
    }
  }

  return {
    'g20-k6-summary.json': JSON.stringify(evidence, null, 2),
    stdout: [
      '',
      '=== Yueke Internship G20 evidence ===',
      `VUs: ${VUS} (procurement minimum: 5000)`,
      `Business paths: ${businessPaths.length}`,
      `Auth identities: ${authIdentityCount}`,
      `Identity pool covers VUs: ${identityPoolMatchesVus}`,
      `Real-run acknowledged: ${REAL_RUN_ACK}`,
      'Evidence: g20-k6-summary.json',
      ''
    ].join('\n')
  }
}
