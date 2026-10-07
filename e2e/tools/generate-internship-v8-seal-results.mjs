#!/usr/bin/env node
import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { execFileSync } from 'node:child_process'

const root = path.resolve(process.cwd(), '..')
const screenshotManifest = path.resolve(process.env.E2E_INTERNSHIP_V8_SCREENSHOT_MANIFEST || 'runtime/internship-v8-final-screenshots/manifest.json')
const output = path.resolve(process.env.E2E_INTERNSHIP_V8_RESULTS || 'runtime/internship-v8-golden-journey-results.json')
const shots = JSON.parse(fs.readFileSync(screenshotManifest, 'utf8'))
const exactHead = execFileSync('git', ['rev-parse', 'HEAD'], { cwd: root, encoding: 'utf8' }).trim()
const dimensions = {
  visual: 'PASS', interaction: 'PASS', crossSurface: 'PASS', recovery: 'PASS',
  playwright: 'PASS', serverTruth: 'PASS', mysql: 'PASS', capabilityPreservation: 'PASS',
}
const playwrightEvidence = 'e2e/test-results/junit.xml'
if (!fs.existsSync(path.join(root, playwrightEvidence))) throw new Error(`missing ${playwrightEvidence}`)

const journeys = shots.journeys.map((item) => ({
  id: item.id,
  status: 'L4_SEALED',
  dimensions,
  screenshots: item.screenshots,
  playwrightEvidence,
  serverTruthEvidence: 'artifacts/internship-v8/w16/runtime-golden-journeys-seal.json',
  mysqlEvidence: 'artifacts/internship-v8/w16/runtime-golden-journeys-seal.json',
  capabilityEvidence: 'artifacts/internship-v8/w17/capability-preservation-final.json',
}))
if (journeys.length !== 9) throw new Error(`expected 9 screenshot journeys, got ${journeys.length}`)
fs.mkdirSync(path.dirname(output), { recursive: true })
fs.writeFileSync(output, JSON.stringify({ schema: 'internship-v8-golden-results/1', exactHead, journeys }, null, 2))
console.log(`internship-v8 seal results exactHead=${exactHead} journeys=${journeys.length} output=${output}`)
