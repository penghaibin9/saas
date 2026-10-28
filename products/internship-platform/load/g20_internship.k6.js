import http from 'k6/http'
import { check, sleep } from 'k6'
import exec from 'k6/execution'
import { Counter, Gauge, Rate, Trend } from 'k6/metrics'

const numberEnv = (name, fallback) => {
  const value = Number(__ENV[name] || fallback)
  if (!Number.isFinite(value)) throw new Error(`${name} must be numeric`)
  return value
}

const BASE_URL = String(__ENV.G20_BASE_URL || '').replace(/\/$/, '')
const VUS = numberEnv('G20_VUS', 20)
const WARMUP = String(__ENV.G20_WARMUP || '30s')
const HOLD = String(__ENV.G20_HOLD || '60s')
const RAMPDOWN = String(__ENV.G20_RAMPDOWN || '30s')
const THINK_SECONDS = numberEnv('G20_THINK_SECONDS', 0.2)
const P95_MS = numberEnv('G20_P95_MS', 1500)
const P99_MS = numberEnv('G20_P99_MS', 3000)
const MAX_ERROR_RATE = numberEnv('G20_MAX_ERROR_RATE', 0.01)
const TOKEN = String(__ENV.G20_AUTH_TOKEN || '')
const TOKEN_FILE = String(__ENV.G20_AUTH_TOKENS_FILE || '').trim()
const REAL_RUN_ACK = String(__ENV.G20_REAL_RUN_ACK || '').toUpperCase() === 'YES'
const BATCH_ID = String(__ENV.G20_BATCH_ID || '')
const INTERNSHIP_ID = String(__ENV.G20_INTERNSHIP_ID || '')
const durationSeconds = value => {
  const parts = String(value).match(/\d+(?:\.\d+)?(?:ms|s|m|h)/g) || []
  if (!parts.length || parts.join('') !== value) throw new Error('G20 stage duration is invalid')
  const seconds = parts.reduce((total, part) => {
    const match = part.match(/^(\d+(?:\.\d+)?)(ms|s|m|h)$/)
    return total + Number(match[1]) * ({ ms: .001, s: 1, m: 60, h: 3600 }[match[2]])
  }, 0)
  if (!Number.isFinite(seconds) || seconds <= 0) throw new Error('G20 stage duration must be positive')
  return seconds
}
const warmupSeconds = durationSeconds(WARMUP)
const holdSeconds = durationSeconds(HOLD)
durationSeconds(RAMPDOWN)
const businessDuration = new Trend('g20_business_duration', true)
const businessFailure = new Rate('g20_business_failure')
const businessRequests = new Counter('g20_business_requests')
const businessUsers = new Counter('g20_business_users')
const holdVus = new Trend('g20_hold_vus') // Trend supports a minimum threshold over every observed sample.
const holdSamples = new Counter('g20_hold_samples')
const holdElapsed = new Trend('g20_hold_elapsed_seconds')
const verifiedTokens = new Gauge('g20_verified_tokens')
const verifiedAccounts = new Gauge('g20_verified_accounts')
const identityVerificationRate = new Rate('g20_identity_verification_rate')
let contributedBusiness = false // k6 initializes a separate script context per VU.

if (!BASE_URL) throw new Error('G20_BASE_URL is required')
if (!/^https?:\/\/[^/?#@\s]+(?:\/[^?#\s]*)?$/.test(BASE_URL)) throw new Error('G20 target must not contain credentials, query or fragment')
if (!Number.isInteger(VUS) || VUS < 1 || VUS > 20000) throw new Error('G20_VUS must be an integer between 1 and 20000')
if (THINK_SECONDS < 0 || P95_MS <= 0 || P99_MS < P95_MS || MAX_ERROR_RATE <= 0 || MAX_ERROR_RATE > 1) {
  throw new Error('G20 operational thresholds or think time are invalid')
}
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
const businessPaths = paths.filter(path => /^\/api\/v1\/(internship|mobile\/internship|student-portal\/internship)\//.test(path))
const missingPlaceholders = paths.filter(path => /\{[^}]+\}/.test(path))

if (missingPlaceholders.length) {
  throw new Error(`Unresolved G20 path placeholders: ${missingPlaceholders.join(', ')}`)
}

const businessScenarioConfigured = businessPaths.length > 0
if (paths.some(path => !path.startsWith('/') || path.startsWith('//') || /[\s\r\n]/.test(path)
    || /[?&](token|access_token|password|secret|authorization)=/i.test(path))) {
  throw new Error('G20 paths must be relative business paths without credentials')
}

const loadAuthTokens = () => {
  let values = []
  if (TOKEN_FILE) {
    const parsed = JSON.parse(open(TOKEN_FILE))
    if (!Array.isArray(parsed)) throw new Error('G20_AUTH_TOKENS_FILE must contain a JSON array')
    values = parsed
  } else if (TOKEN) {
    values = [TOKEN]
  }
  if (values.some(value => typeof value !== 'string' || !value.trim())) throw new Error('G20 token entries must be nonempty strings')
  const normalized = values.map(value => value.trim())
  const unique = Array.from(new Set(normalized))
  if (normalized.length !== unique.length) {
    throw new Error('G20 auth token pool contains duplicate identities/tokens')
  }
  return unique
}

const authTokens = loadAuthTokens()
const authConfigured = authTokens.length > 0
if (VUS >= 5000 && (authTokens.length < VUS || !businessScenarioConfigured || holdSeconds < 60)) {
  throw new Error('Formal G20 requires a complete token pool, business paths and at least a 60-second observation window')
}

export function setup() {
  const identities = new Set()
  let verified = 0
  const tokens = authTokens.slice(0, VUS)
  for (let start = 0; start < tokens.length; start += 50) {
    const responses = http.batch(tokens.slice(start, start + 50).map(token => ({
      method: 'GET', url: `${BASE_URL}/api/v1/auth/me`,
      params: { headers: { Authorization: `Bearer ${token}` }, responseType: 'text', redirects: 0,
        tags: { g20_kind: 'identity-verification' } }
    })))
    for (const response of responses) {
      let profile
      try { const body = response.json(); if (response.status === 200 && body.code === 0) profile = body.data } catch (_) { /* No response or credential text is logged. */ }
      const valid = Boolean(profile && typeof profile.tenantId === 'string' && /^\d+$/.test(profile.tenantId)
        && typeof profile.userId === 'string' && /^db-\d+$/.test(profile.userId) && profile.mustChangePassword === false)
      identityVerificationRate.add(valid)
      if (valid) { verified++; identities.add(`${profile.tenantId}:${profile.userId}`) }
    }
  }
  verifiedTokens.add(verified)
  verifiedAccounts.add(identities.size)
  const allVerified = verified === tokens.length && tokens.length > 0
  if (VUS >= 5000 && (!allVerified || identities.size !== VUS)) {
    throw new Error('Formal G20 account verification failed: tokens must authenticate distinct active database accounts')
  }
  return { allVerified } // Only a boolean crosses into VU contexts; no tokens or account details.
}

export const options = {
  setupTimeout: '10m',
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
    http_req_duration: [`p(95)<${P95_MS}`, `p(99)<${P99_MS}`],
    g20_business_duration: ['avg<=3000', `p(95)<${P95_MS}`, `p(99)<${P99_MS}`],
    g20_business_failure: [`rate<${MAX_ERROR_RATE}`],
    g20_hold_vus: [`min>=${VUS}`]
  },
  summaryTrendStats: ['avg', 'min', 'med', 'max', 'p(90)', 'p(95)', 'p(99)'],
  discardResponseBodies: true,
  noConnectionReuse: false,
  userAgent: 'Yueke-Internship-G20-k6/1.0'
}

export default function () {
  const index = exec.vu.iterationInScenario % paths.length
  const path = paths[index]
  if (VUS >= 5000 && exec.vu.idInTest > VUS) throw new Error('This G20 evidence protocol requires a single load generator')
  const token = authTokens.length ? authTokens[(exec.vu.idInTest - 1) % Math.min(authTokens.length, VUS)] : ''
  const headers = token ? { Authorization: `Bearer ${token}` } : {}
  const elapsed = (Date.now() - exec.scenario.startTime) / 1000 - 2 * warmupSeconds
  const inHold = elapsed >= 0 && elapsed < holdSeconds
  const isBusiness = businessPaths.includes(path)
  if (inHold) {
    holdVus.add(exec.instance.vusActive)
    holdSamples.add(1)
    holdElapsed.add(elapsed)
  }
  const response = http.get(`${BASE_URL}${path}`, {
    headers, responseType: isBusiness ? 'text' : 'none', redirects: 0,
    tags: {
      g20_path: path,
      g20_kind: isBusiness ? 'business' : 'non-business',
      g20_phase: inHold ? 'hold' : 'ramp'
    }
  })
  let succeeded = response.status >= 200 && response.status < 300
  if (isBusiness) {
    try { succeeded = succeeded && response.json().code === 0 } catch (_) { succeeded = false }
  }
  check(response, { 'HTTP and business result succeeded': () => succeeded })
  if (isBusiness && inHold) {
    businessDuration.add(response.timings.duration)
    businessFailure.add(!succeeded)
    businessRequests.add(1)
    if (succeeded && !contributedBusiness) { contributedBusiness = true; businessUsers.add(1) }
  }
  if (THINK_SECONDS > 0) sleep(THINK_SECONDS)
}

const thresholdStatus = metrics => {
  const out = {}
  for (const [metricName, metric] of Object.entries(metrics || {})) {
    if (!metric.thresholds) continue
    out[metricName] = Object.fromEntries(
      Object.entries(metric.thresholds).map(([name, value]) => [name, value?.ok === true])
    )
  }
  return out
}

export function handleSummary(data) {
  const metricValue = (name, key) => data.metrics?.[name]?.values?.[key]
  const authIdentityCount = metricValue('g20_verified_accounts', 'value') || 0
  const verifiedTokenCount = metricValue('g20_verified_tokens', 'value') || 0
  const allVerified = verifiedTokenCount > 0 && metricValue('g20_identity_verification_rate', 'rate') === 1
  const identityPoolMatchesVus = allVerified && authIdentityCount === VUS && verifiedTokenCount === VUS
  const evidence = {
    schemaVersion: 2,
    gate: 'G20',
    generator: 'k6',
    runMode: 'single-generator',
    generatedAt: new Date().toISOString(),
    target: BASE_URL,
    requestedVus: VUS,
    procurementMinimumVus: 5000,
    realRunAcknowledged: REAL_RUN_ACK,
    warmup: WARMUP,
    hold: HOLD,
    holdSeconds,
    rampdown: RAMPDOWN,
    configuredPaths: paths,
    businessPaths,
    businessScenarioConfigured,
    authConfigured,
    authIdentityCount,
    identityPoolMatchesVus,
    identityVerification: { method: 'server-auth-me', endpoint: '/api/v1/auth/me',
      verifiedTokenCount, distinctAccountCount: authIdentityCount, allVerified },
    tokenPoolFileConfigured: Boolean(TOKEN_FILE),
    operationalThresholds: {
      averageMaxMs: 3000,
      p95Ms: P95_MS,
      p99Ms: P99_MS,
      maxErrorRate: MAX_ERROR_RATE,
      note: 'Mean <=3000ms is fixed. Percentiles and error limits retain the operational policy; annual availability is separate evidence.'
    },
    thresholdStatus: thresholdStatus(data.metrics),
    metrics: data.metrics,
    preflight: {
      configurationAndIdentityReady:
        VUS >= 5000 &&
        REAL_RUN_ACK &&
        businessScenarioConfigured &&
        authConfigured &&
        identityPoolMatchesVus,
      note: 'Configuration and identity readiness does not qualify the measured run. Final qualification is decided by g20_validate_evidence.py.'
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
