import { execFileSync } from 'node:child_process'
import fs from 'node:fs/promises'
import { fileURLToPath } from 'node:url'

import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { prepareGraduationFixture } from '../lib/api-fixture.mjs'
import { StaffLoginPage } from '../pages/login.page.mjs'

const BACKEND_DIR = fileURLToPath(new URL('../../backend/', import.meta.url))
const CONTEXT = { queue: 'U4-DEEP', source: 'v9-e2e', panel: 'guidance' }

async function dismissGuide(page) {
  for (const mask of [page.locator('.app-step-guide__mask'), page.locator('.tour-mask')]) {
    if (await mask.isVisible().catch(() => false)) {
      const skip = page.getByRole('button', { name: /跳过引导|跳过/ }).first()
      if (await skip.isVisible().catch(() => false)) await skip.click()
      await mask.waitFor({ state: 'hidden', timeout: 3000 }).catch(() => {})
    }
  }
}

async function expectProcessContext(page, target, batchId) {
  await expect(page.getByRole('heading', { name: '过程指导', exact: true })).toBeVisible()
  await expect(page.locator('.gp-context')).toContainText(target.studentName)
  await expect(page.locator('.gp-context')).toContainText(target.studentNo)
  await expect(page.locator('.gp-context')).toContainText(/指导|过程/)
  await expect.poll(() => {
    const url = new URL(page.url())
    return {
      path: url.pathname,
      batchId: url.searchParams.get('batchId'),
      studentId: url.searchParams.get('studentId'),
      panel: url.searchParams.get('panel'),
      queue: url.searchParams.get('queue'),
      source: url.searchParams.get('source')
    }
  }).toEqual({
    path: '/admin/graduation/process',
    batchId,
    studentId: target.targetId,
    panel: CONTEXT.panel,
    queue: CONTEXT.queue,
    source: CONTEXT.source
  })
}

async function expectActionContext(page, target, batchId) {
  await expect.poll(() => {
    const url = new URL(page.url())
    return {
      path: url.pathname,
      batchId: url.searchParams.get('batchId'),
      studentId: url.searchParams.get('studentId'),
      panel: url.searchParams.get('panel'),
      queue: url.searchParams.get('queue'),
      source: url.searchParams.get('source')
    }
  }).toEqual({
    path: `/admin/graduation/process/${target.targetId}/guidance`,
    batchId,
    studentId: target.targetId,
    panel: CONTEXT.panel,
    queue: CONTEXT.queue,
    source: CONTEXT.source
  })
}

async function settle(page) {
  await page.evaluate(async () => {
    if (document.fonts?.ready) await document.fonts.ready
  })
  await page.waitForLoadState('networkidle', { timeout: 5000 }).catch(() => {})
}

async function capture(page, testInfo, name, width, height) {
  await page.setViewportSize({ width, height })
  await dismissGuide(page)
  await settle(page)
  const path = testInfo.outputPath(`${name}-${width}x${height}.png`)
  await page.screenshot({ path, fullPage: false, animations: 'disabled', caret: 'hide' })
  await testInfo.attach(`${name}-${width}x${height}`, { path, contentType: 'image/png' })
  return path
}

test.describe.serial('V9.2 U4 · process WorkContext production evidence', () => {
  let fixture
  let target

  test.beforeAll(async () => {
    fixture = await prepareGraduationFixture()
    const output = execFileSync(
      'python',
      ['scripts/e2e_seed_graduation_process_context.py', fixture.gdStudentId],
      {
        cwd: BACKEND_DIR,
        env: { ...process.env, PYTHONPATH: BACKEND_DIR },
        encoding: 'utf8'
      }
    ).trim()
    target = JSON.parse(output.split(/\r?\n/).filter(Boolean).at(-1))
    expect(target.count).toBe(130)
    expect(target.targetIndex).toBe(127)
    expect(target.targetId).toBeTruthy()
  })

  test('student #127 F5 + cancel/save exact context · Screenshot B 1440/1280', async ({ page }, testInfo) => {
    await page.setViewportSize({ width: 1440, height: 900 })
    await new StaffLoginPage(page, config.staffBaseUrl).login(config.mentor)

    const url = new URL(`${config.staffBaseUrl}/admin/graduation/process`)
    url.searchParams.set('batchId', fixture.batchId)
    url.searchParams.set('studentId', target.targetId)
    url.searchParams.set('panel', CONTEXT.panel)
    url.searchParams.set('queue', CONTEXT.queue)
    url.searchParams.set('source', CONTEXT.source)
    await page.goto(url.toString())
    await dismissGuide(page)
    await expectProcessContext(page, target, fixture.batchId)
    await expect(page.locator('body')).not.toContainText(/真实接口不可用|权限上下文加载失败/)

    // M3 E4: deep-link target #127 must survive a real browser refresh exactly.
    await page.reload()
    await dismissGuide(page)
    await expectProcessContext(page, target, fixture.batchId)

    // M3 E5 cancel path: entering the action must carry the complete WorkContext,
    // and cancel must return to the same student/tab/queue/source.
    await page.getByRole('button', { name: '＋ 新增指导记录' }).click()
    await expectActionContext(page, target, fixture.batchId)
    await page.getByRole('button', { name: '取消', exact: true }).click()
    await expectProcessContext(page, target, fixture.batchId)

    // M3 E5 save path: write through the real UI/API, then return to the same context.
    const guidanceText = `U4 E5 真保存指导 ${fixture.runId}-${testInfo.retry}`
    await page.getByRole('button', { name: '＋ 新增指导记录' }).click()
    await expectActionContext(page, target, fixture.batchId)
    const content = page.locator('label').filter({ hasText: '指导内容' }).locator('textarea').first()
    await expect(content).toBeVisible()
    await content.fill(guidanceText)
    await page.getByRole('button', { name: '保存', exact: true }).click()
    await expectProcessContext(page, target, fixture.batchId)
    await expect(page.locator('.gp-panel')).toContainText(guidanceText)

    await capture(page, testInfo, 'gd-U4-process-B', 1440, 900)
    await capture(page, testInfo, 'gd-U4-process-B', 1280, 800)

    const metaPath = testInfo.outputPath('gd-U4-process-B-meta.json')
    await fs.writeFile(metaPath, JSON.stringify({
      phase: 'B',
      card: 'U4',
      head: process.env.GITHUB_SHA || 'local',
      batchId: fixture.batchId,
      targetIndex: target.targetIndex,
      targetId: target.targetId,
      studentNo: target.studentNo,
      studentName: target.studentName,
      className: target.className,
      panel: CONTEXT.panel,
      queue: CONTEXT.queue,
      source: CONTEXT.source,
      savedGuidance: guidanceText,
      viewports: [{ width: 1440, height: 900 }, { width: 1280, height: 800 }]
    }, null, 2), 'utf8')
    await testInfo.attach('gd-U4-process-B-meta', { path: metaPath, contentType: 'application/json' })
  })
})
