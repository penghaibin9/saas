import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const ROOT = path.resolve(HERE, '..', '..')
const mode = process.argv.includes('--seal') ? 'seal' : 'readiness'
const manifestPath = path.resolve(ROOT, 'e2e/contracts/internship-v8-golden-journeys.json')
const resultsPath = path.resolve(ROOT, process.env.E2E_INTERNSHIP_V8_RESULTS || 'e2e/runtime/internship-v8-golden-journey-results.json')

function fail(message) {
  throw new Error(`[internship-v8-journeys] ${message}`)
}

function readJson(target) {
  try {
    return JSON.parse(fs.readFileSync(target, 'utf8'))
  } catch (error) {
    fail(`cannot read JSON ${path.relative(ROOT, target)}: ${error.message}`)
  }
}

function assertFile(relativePath, label) {
  const target = path.resolve(ROOT, relativePath)
  if (!fs.existsSync(target) || !fs.statSync(target).isFile()) {
    fail(`${label} does not exist: ${relativePath}`)
  }
}

const manifest = readJson(manifestPath)
const requiredDimensions = manifest.requiredDimensions || []
if (manifest.schemaVersion !== 1) fail('unsupported schemaVersion')
if (requiredDimensions.length !== 8 || new Set(requiredDimensions).size !== 8) {
  fail('exactly eight unique L4 dimensions are required')
}
if (!Array.isArray(manifest.journeys) || manifest.journeys.length !== 9) {
  fail('exactly nine journeys are required')
}

const ids = new Set()
const capabilities = new Set()
let browserReady = 0
for (const [index, journey] of manifest.journeys.entries()) {
  const expectedId = `IX-GJ-${String(index + 1).padStart(2, '0')}`
  if (journey.id !== expectedId) fail(`journey order mismatch: expected ${expectedId}`)
  if (ids.has(journey.id)) fail(`duplicate journey id ${journey.id}`)
  ids.add(journey.id)
  for (const key of ['title', 'participants', 'surfaces', 'homeStarts', 'canonicalSteps', 'negativeCases', 'truthTables', 'capabilities', 'playwrightSpecs', 'staticEvidence']) {
    if (!journey[key] || (Array.isArray(journey[key]) && journey[key].length === 0 && !['playwrightSpecs'].includes(key))) {
      fail(`${journey.id} is missing ${key}`)
    }
  }
  if (!(manifest.allowedStatuses || []).includes(journey.sealStatus)) {
    fail(`${journey.id} has invalid sealStatus ${journey.sealStatus}`)
  }
  journey.capabilities.forEach((item) => capabilities.add(item))
  journey.staticEvidence.forEach((item) => assertFile(item, `${journey.id} static evidence`))
  journey.playwrightSpecs.forEach((item) => assertFile(item, `${journey.id} Playwright spec`))
  if (journey.playwrightSpecs.length > 0) browserReady += 1
}

const missingCapabilities = Array.from({ length: 20 }, (_, index) => `CP-IX-${String(index + 1).padStart(2, '0')}`)
  .filter((item) => !capabilities.has(item))
if (missingCapabilities.length) fail(`capability ledger is incomplete: ${missingCapabilities.join(', ')}`)

if (mode === 'readiness') {
  console.log(JSON.stringify({
    status: 'READINESS_CONTRACT_PASS',
    journeys: manifest.journeys.length,
    browserSpecReady: browserReady,
    browserSpecPending: manifest.journeys.length - browserReady,
    capabilities: capabilities.size,
    seal: 'NOT_ATTEMPTED'
  }))
  process.exit(0)
}

if (!fs.existsSync(resultsPath)) fail(`seal results are missing: ${path.relative(ROOT, resultsPath)}`)
const results = readJson(resultsPath)
const head = execFileSync('git', ['rev-parse', 'HEAD'], { cwd: ROOT, encoding: 'utf8' }).trim()
const dirty = execFileSync('git', ['status', '--porcelain'], { cwd: ROOT, encoding: 'utf8' }).trim()
if (dirty) fail('seal requires a clean exact HEAD')
if (results.exactHead !== head) fail(`result exactHead ${results.exactHead || 'missing'} does not equal ${head}`)
if (!Array.isArray(results.journeys) || results.journeys.length !== 9) fail('seal results must contain nine journeys')

for (const journey of manifest.journeys) {
  const result = results.journeys.find((item) => item.id === journey.id)
  if (!result) fail(`${journey.id} result is missing`)
  if (result.status !== 'L4_SEALED') fail(`${journey.id} is ${result.status || 'unsealed'}`)
  for (const dimension of requiredDimensions) {
    if (result.dimensions?.[dimension] !== 'PASS') fail(`${journey.id} ${dimension} is not PASS`)
  }
  const shots = result.screenshots || {}
  for (const key of ['A', 'B', 'C']) {
    if (!shots[key]) fail(`${journey.id} screenshot ${key} is missing`)
    assertFile(shots[key], `${journey.id} screenshot ${key}`)
  }
  for (const key of ['playwrightEvidence', 'serverTruthEvidence', 'mysqlEvidence', 'capabilityEvidence']) {
    if (!result[key]) fail(`${journey.id} ${key} is missing`)
    assertFile(result[key], `${journey.id} ${key}`)
  }
}

console.log(JSON.stringify({ status: '9_OF_9_L4_SEALED', exactHead: head, journeys: 9, dimensions: requiredDimensions.length }))
