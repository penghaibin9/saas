import fs from 'node:fs'
import fsp from 'node:fs/promises'

const GOLD_STABILITY_STYLE = `
  .security-watermark,
  .security-watermark__tile {
    visibility: hidden !important;
  }
`

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

  const output = testInfo.outputPath(`${name}-${width}x${height}.png`)
  await page.screenshot({
    path: output,
    fullPage,
    animations: 'disabled',
    caret: 'hide',
    style: GOLD_STABILITY_STYLE,
    mask: masks.filter(Boolean),
    maskColor: '#D8DEE9',
  })
  await testInfo.attach(`${name}-${width}x${height}`, { path: output, contentType: 'image/png' })
  return output
}

export async function goldEnvironment(page, testInfo) {
  const browser = await page.evaluate(() => ({
    deviceScaleFactor: window.devicePixelRatio || 1,
    language: navigator.language || '',
    bodyFontFamily: getComputedStyle(document.body).fontFamily || '',
    bodyFontSize: getComputedStyle(document.body).fontSize || '',
    fontStatus: document.fonts?.status || 'unsupported',
  }))
  return {
    goldHead: goldHead(),
    browserProject: testInfo.project.name,
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
