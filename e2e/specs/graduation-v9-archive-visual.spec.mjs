import fs from 'node:fs/promises'

import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { loginApi, prepareGraduationFixture } from '../lib/api-fixture.mjs'
import { captureGoldCandidate, dynamicTextMasks, goldEnvironment } from '../lib/graduation-gold.mjs'
import { StaffLoginPage } from '../pages/login.page.mjs'

async function dismissGuide(page, { waitForArrival = false } = {}) {
  if (waitForArrival) {
    await page.locator('.app-step-guide__mask, .tour-mask').first()
      .waitFor({ state: 'visible', timeout: 2000 })
      .catch(() => {})
  }
  for (const mask of [page.locator('.app-step-guide__mask'), page.locator('.tour-mask')]) {
    if (await mask.isVisible().catch(() => false)) {
      const skip = page.getByRole('button', { name: /跳过引导|跳过/ }).first()
      if (await skip.isVisible().catch(() => false)) await skip.click()
      await expect(mask).toBeHidden({ timeout: 3000 })
    }
  }
}

async function settle(page) {
  await page.evaluate(async () => {
    if (document.fonts?.ready) await document.fonts.ready
  })
  await page.waitForLoadState('networkidle', { timeout: 5000 }).catch(() => {})
}

async function capture(page, testInfo, name, width, height, goldMasks = []) {
  await page.setViewportSize({ width, height })
  await dismissGuide(page)
  await settle(page)
  const path = testInfo.outputPath(`${name}-${width}x${height}.png`)
  await page.screenshot({ path, fullPage: false, animations: 'disabled', caret: 'hide' })
  await testInfo.attach(`${name}-${width}x${height}`, { path, contentType: 'image/png' })
  await captureGoldCandidate(page, testInfo, {
    name: name.replace('-B', '-GoldCandidate'), width, height, masks: goldMasks,
  })
  return path
}

function expectedTabForMissingItem(label) {
  const text = String(label || '')
  if (text.includes('任务书')) return 'taskbook'
  if (text.includes('开题')) return 'proposals'
  if (text.includes('中期')) return 'midterm'
  if (text.includes('指导')) return 'guidance'
  if (text.includes('查重')) return 'plagiarisms'
  if (text.includes('评阅') || text.includes('答辩') || text.includes('成绩')) return 'review'
  if (text.includes('成果') || text.includes('论文')) return 'finals'
  return ''
}

test.describe.serial('V9.2 U7 · archive workbench production evidence', () => {
  let fixture

  test.beforeAll(async () => {
    fixture = await prepareGraduationFixture()
    const admin = await loginApi(config.sandboxAdmin)
    await admin.request('POST', `/graduation/gd-archives/${fixture.gdStudentId}/generate`, {
      params: { batchId: fixture.batchId }
    })
  })

  test('real archive row · exact missing-item deep-link · Screenshot B 1440/1280', async ({ page }, testInfo) => {
    await page.setViewportSize({ width: 1440, height: 900 })
    await new StaffLoginPage(page, config.staffBaseUrl).login(config.sandboxAdmin)

    const url = new URL(`${config.staffBaseUrl}/admin/graduation/risk-archive`)
    url.searchParams.set('panel', 'archive')
    url.searchParams.set('batchId', fixture.batchId)
    await page.goto(url.toString())
    await dismissGuide(page, { waitForArrival: true })

    await expect(page.locator('body')).not.toContainText(/真实接口不可用|权限上下文加载失败/)
    await expect(page.getByText(fixture.studentNo, { exact: true }).first()).toBeVisible()
    await page.getByText(fixture.studentNo, { exact: true }).first().click()
    await expect(page.getByText('归档核验', { exact: false }).first()).toBeVisible()
    await expect(page.getByText(/缺失 \d+ 项/).first()).toBeVisible()

    const missingRow = page.locator('.ar-missing__item').filter({ has: page.getByRole('button', { name: '去补齐 →' }) }).first()
    const fixButton = missingRow.getByRole('button', { name: '去补齐 →' })
    await expect(fixButton).toBeVisible()
    const missingLabel = (await missingRow.locator('.ar-missing__name').textContent()) || ''
    const exactTab = expectedTabForMissingItem(missingLabel)
    expect(exactTab, `U7 missing item must have an exact deep-link mapping: ${missingLabel}`).not.toBe('')

    const goldMasks = [
      page.locator('.gbs__select'),
      ...dynamicTextMasks(page, [fixture.runId, fixture.batchName, fixture.topicTitle]),
    ]
    await capture(page, testInfo, 'gd-U7-archive-B', 1440, 900, goldMasks)
    await capture(page, testInfo, 'gd-U7-archive-B', 1280, 800, goldMasks)

    // U7 exact deep-link: exact student + batch + source + clicked missing-item destination.
    await fixButton.click()
    await expect.poll(() => {
      const current = new URL(page.url())
      return {
        path: current.pathname,
        batchId: current.searchParams.get('batchId'),
        source: current.searchParams.get('source'),
        tab: current.searchParams.get('tab')
      }
    }).toEqual({
      path: `/admin/graduation/students/${fixture.gdStudentId}`,
      batchId: fixture.batchId,
      source: 'archive',
      tab: exactTab
    })
    // Student numbers are intentionally masked on the detail page; the exact route id plus
    // the fixture's unique topic proves the intended student loaded without violating PII UI rules.
    await expect(page.locator('body')).toContainText(fixture.topicTitle)

    const environment = await goldEnvironment(page, testInfo)
    const metaPath = testInfo.outputPath('gd-U7-archive-B-meta.json')
    await fs.writeFile(metaPath, JSON.stringify({
      phase: 'B',
      card: 'U7',
      head: environment.goldHead,
      goldHead: environment.goldHead,
      tenant: config.sandboxAdmin.tenant,
      role: 'SCHOOL_ADMIN',
      batchId: fixture.batchId,
      route: `/admin/graduation/risk-archive?panel=archive&batchId=${fixture.batchId}`,
      fixtureVersion: { runId: fixture.runId, gdStudentId: fixture.gdStudentId, studentNo: fixture.studentNo },
      browserProject: environment.browserProject,
      deviceScaleFactor: environment.deviceScaleFactor,
      language: environment.language,
      fontEnvironment: environment.fontEnvironment,
      dynamicZones: ['security-watermark', 'run-scoped-batch-label', 'run-scoped-topic-title'],
      gdStudentId: fixture.gdStudentId,
      studentNo: fixture.studentNo,
      source: 'archive',
      missingItem: missingLabel,
      exactTab,
      viewports: [{ width: 1440, height: 900 }, { width: 1280, height: 800 }]
    }, null, 2), 'utf8')
    await testInfo.attach('gd-U7-archive-B-meta', { path: metaPath, contentType: 'application/json' })
  })
})
