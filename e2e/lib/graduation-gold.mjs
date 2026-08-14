import { createHash } from 'node:crypto'
import fs from 'node:fs'
import fsp from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { expect } from '@playwright/test'

const GOLD_DIR = fileURLToPath(new URL('../gold/', import.meta.url))
const GOLD_MANIFEST_PATH = path.join(GOLD_DIR, 'graduation-v9-gold-manifest.json')
const GOLD_STABILITY_STYLE_PATH = path.join(GOLD_DIR, 'graduation-gold-stability.css')
const GOLD_STABILITY_STYLE = fs.readFileSync(GOLD_STABILITY_STYLE_PATH, 'utf8')
const GOLD_MANIFEST = JSON.parse(fs.readFileSync(GOLD_MANIFEST_PATH, 'utf8'))

function eventHeadSha() {
  const eventPath = process.env.GITHUB_EVENT_PATH
  if (!eventPath) return ''
  try {
    const event = JSON.parse(fs.readFileSync(eventPath, 'utf8'))
    return String(event?.pull_request?.head?.sha || event?.workflow_run?.head_sha || '')
  } catch {
    return ''
  }
}

function sha256(buffer) {
  return createHash('sha256').update(buffer).digest('hex')
}

function assertGoldEnvironment(page, testInfo) {
  const browser = page.context().browser()?.browserType().name() || ''
  if (browser !== GOLD_MANIFEST.environment.browser) {
    throw new Error(`U11 Gold requires ${GOLD_MANIFEST.environment.browser}; got ${browser || 'unknown'}`)
  }
  if (process.platform !== GOLD_MANIFEST.environment.os) {
    throw new Error(`U11 Gold requires ${GOLD_MANIFEST.environment.os}; got ${process.platform}`)
  }
  if (testInfo.project.name) {
    throw new Error(`U11 Gold expects the default unnamed Playwright project; got ${testInfo.project.name}`)
  }
  testInfo.snapshotSuffix = GOLD_MANIFEST.environment.snapshotSuffix
  return browser
}

function goldBaseline(page, testInfo, logicalName) {
  assertGoldEnvironment(page, testInfo)
  const baseline = GOLD_MANIFEST.baselines.find((item) => item.logicalName === logicalName)
  if (!baseline) throw new Error(`U11 Gold manifest has no baseline for ${logicalName}`)
  if (path.basename(testInfo.file) !== baseline.spec) {
    throw new Error(`U11 Gold spec drift for ${logicalName}: expected ${baseline.spec}, got ${path.basename(testInfo.file)}`)
  }

  const snapshotPath = testInfo.snapshotPath(logicalName, { kind: 'screenshot' })
  if (path.basename(snapshotPath) !== baseline.frozenFile) {
    throw new Error(`U11 Gold snapshot path drift for ${logicalName}: expected ${baseline.frozenFile}, got ${path.basename(snapshotPath)}`)
  }
  if (!fs.existsSync(snapshotPath)) throw new Error(`U11 Gold baseline missing: ${snapshotPath}`)
  const bytes = fs.readFileSync(snapshotPath)
  const actualSha = sha256(bytes)
  if (actualSha !== baseline.sha256) {
    throw new Error(`U11 Gold baseline SHA mismatch for ${baseline.frozenFile}: expected ${baseline.sha256}, got ${actualSha}`)
  }
  return baseline
}

export function goldHead() {
  return String(process.env.GITHUB_HEAD_SHA || eventHeadSha() || process.env.GITHUB_SHA || 'local')
}

export function dynamicTextMasks(page, values = []) {
  return values
    .map((value) => String(value || '').trim())
    .filter(Boolean)
    .map((value) => page.getByText(value, { exact: false }))
}

export async function captureGoldCandidate(page, testInfo, {
  name,
  width,
  height,
  masks = [],
  fullPage = false,
}) {
  await page.setViewportSize({ width, height })
  await page.evaluate(async () => {
    if (document.fonts?.ready) await document.fonts.ready
  })
  await page.waitForLoadState('networkidle', { timeout: 5000 }).catch(() => {})

  const stableMasks = masks.filter(Boolean)
  const logicalName = `${name}-${width}x${height}.png`
  const baseline = goldBaseline(page, testInfo, logicalName)
  const output = testInfo.outputPath(logicalName)
  await page.screenshot({
    path: output,
    fullPage,
    animations: 'disabled',
    caret: 'hide',
    style: GOLD_STABILITY_STYLE,
    mask: stableMasks,
    maskColor: GOLD_MANIFEST.stability.maskColor,
  })
  await testInfo.attach(`${name}-${width}x${height}`, { path: output, contentType: 'image/png' })

  await expect(page).toHaveScreenshot(logicalName, {
    fullPage,
    animations: 'disabled',
    caret: 'hide',
    stylePath: GOLD_STABILITY_STYLE_PATH,
    mask: stableMasks,
    maskColor: GOLD_MANIFEST.stability.maskColor,
    maxDiffPixelRatio: baseline.maxDiffPixelRatio,
  })
  return output
}

export async function goldEnvironment(page, testInfo) {
  const browserName = assertGoldEnvironment(page, testInfo)
  const browser = await page.evaluate(() => ({
    deviceScaleFactor: window.devicePixelRatio || 1,
    language: navigator.language || '',
    bodyFontFamily: getComputedStyle(document.body).fontFamily || '',
    bodyFontSize: getComputedStyle(document.body).fontSize || '',
    fontStatus: document.fonts?.status || 'unsupported',
  }))
  return {
    goldHead: goldHead(),
    browser: browserName,
    browserProject: GOLD_MANIFEST.environment.browserProject,
    snapshotSuffix: testInfo.snapshotSuffix,
    deviceScaleFactor: browser.deviceScaleFactor,
    language: browser.language,
    fontEnvironment: {
      bodyFontFamily: browser.bodyFontFamily,
      bodyFontSize: browser.bodyFontSize,
      status: browser.fontStatus,
    },
  }
}

export async function writeGoldMeta(testInfo, name, payload) {
  const output = testInfo.outputPath(`${name}.json`)
  await fsp.writeFile(output, JSON.stringify(payload, null, 2), 'utf8')
  await testInfo.attach(name, { path: output, contentType: 'application/json' })
  return output
}
