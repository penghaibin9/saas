import fs from 'node:fs/promises'

import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { prepareGraduationFixture } from '../lib/api-fixture.mjs'
import { StaffLoginPage } from '../pages/login.page.mjs'
import { GRADUATION_WORKSPACES } from '../../frontend/src/modules/graduation/config/graduationWorkspaces.js'

const VIEWPORTS = [
  { key: '1760', width: 1760, height: 900, zoom: 1 },
  { key: '1440', width: 1440, height: 900, zoom: 1, screenshot: true },
  { key: '1366', width: 1366, height: 768, zoom: 1 },
  { key: '1280', width: 1280, height: 800, zoom: 1, screenshot: true },
  { key: '1366-125pct', width: 1366, height: 768, zoom: 1.25 }
]

const SCREEN_META = {
  '毕设总览': { id: 'dashboard', surfaces: ['.gdb-work', '.gdb-work-empty'] },
  '待评阅开题': { id: 'proposal-pending', surfaces: ['.pr-split'] },
  '待评阅成果': { id: 'final-pending', surfaces: ['.gd-review-workspace', '.fr-split'] },
  '我的答辩评分': { id: 'defense-mine', surfaces: ['.gp-layout', '.dg-batch'] },
  '批次与规则': { id: 'batches', surfaces: ['.dt', 'table', '.mp-card'] },
  '学生与进度': { id: 'students', surfaces: ['.dt', 'table', '.gd-student-hero'] },
  '导师与分配': { id: 'mentors', surfaces: ['.dt', 'table', '.mp-card'] },
  '分配冲突检测': { id: 'mentor-conflicts', surfaces: ['.dt', 'table', '.mp-card'] },
  '题目库': { id: 'topic-lib', surfaces: ['.dt', 'table', '.mp-card'] },
  '选题轮次': { id: 'topic-rounds', surfaces: ['.dt', 'table', '.mp-card'] },
  '题目调整申请': { id: 'topic-changes', surfaces: ['.dt', 'table', '.mp-card'] },
  '过程指导台': { id: 'process', surfaces: ['.gp-layout'] },
  '开题报告批阅': { id: 'proposals', surfaces: ['.pr-split'] },
  '成果提交与批阅': { id: 'finals', surfaces: ['.gd-review-workspace', '.fr-split'] },
  '毕设材料中心': { id: 'material-center', surfaces: ['.mc-table-wrap', '.mc-panel'] },
  '查重记录': { id: 'plagiarism', surfaces: ['.gp-layout', '.dg-batch'] },
  '统一评阅中心': { id: 'review-center', surfaces: ['.gd-review-workspace', '.dt', 'table'] },
  '答辩安排': { id: 'defense', surfaces: ['.dt', 'table', '.mp-card'] },
  '答辩评分': { id: 'defense-score', surfaces: ['.gp-layout', '.dg-batch'] },
  '答辩秘书确认': { id: 'defense-confirmation', surfaces: ['.gp-layout', '.dg-batch'] },
  '成绩台账': { id: 'grade-ledger', surfaces: ['.dg-batch', '.dt', 'table'] },
  '问题预警': { id: 'risk', surfaces: ['.rk-split', '.rk-list'] },
  '毕设材料归档': { id: 'archive', surfaces: ['.rk-split', '.rk-list'] },
  '全部模板': { id: 'templates', surfaces: ['.dt', 'table', '.mp-card'] }
}

const SCREENS = GRADUATION_WORKSPACES.flatMap((workspace) => workspace.children)
  .filter((item) => !item.hidden)
  .map((item) => {
    const meta = SCREEN_META[item.label]
    if (!meta) throw new Error(`Missing V6 audit metadata for production menu item: ${item.label}`)
    return {
      ...meta,
      title: item.label,
      path: item.path,
      entryType: item.entryType,
      permissionKey: item.permissionKey
    }
  })

const CHUNKS = Array.from({ length: 4 }, (_, index) => SCREENS.slice(index * 6, index * 6 + 6))
const EMPTY_SELECTORS = ['.empty-state', '.mp-empty', '.app-empty-state', '[data-state="empty"]']
const ERROR_SELECTORS = ['.error-state', '.app-error-state', '[data-state="error"]', '.forbidden-state', '[data-state="forbidden"]']
const LOADING_SELECTORS = ['.loading-state', '.app-loading-state', '[data-state="loading"]', '.skeleton', '.app-skeleton']

async function dismissGuide(page) {
  for (let attempt = 0; attempt < 3; attempt += 1) {
    const masks = [page.locator('.app-step-guide__mask'), page.locator('.tour-mask')]
    const visible = []
    for (const mask of masks) {
      if (await mask.isVisible().catch(() => false)) visible.push(mask)
    }
    if (!visible.length) return
    const skip = page.getByRole('button', { name: /跳过引导|跳过/ }).first()
    if (await skip.isVisible().catch(() => false)) await skip.click()
    else await page.keyboard.press('Escape').catch(() => {})
    await Promise.all(visible.map((mask) => mask.waitFor({ state: 'hidden', timeout: 3000 }).catch(() => {})))
  }
}

function screenUrl(baseUrl, path, batchId) {
  const url = new URL(path, baseUrl)
  if (!url.searchParams.has('batchId')) url.searchParams.set('batchId', String(batchId))
  return url.toString()
}

async function resetViewportState(page, zoom) {
  await page.evaluate((nextZoom) => {
    document.documentElement.style.zoom = String(nextZoom)
    window.scrollTo(0, 0)
    const scrollSelectors = [
      '.gd-business-view', '.base-portal-layout__main', '.portal-content',
      '.mc-table-wrap', '.rk-rows', '.pr-rows', '.gp-stu-list', '.dt__body'
    ]
    for (const selector of scrollSelectors) {
      for (const element of document.querySelectorAll(selector)) {
        if (element instanceof HTMLElement) {
          element.scrollTop = 0
          element.scrollLeft = 0
        }
      }
    }
  }, zoom)
}

async function waitForPageReady(page, screen) {
  const selectors = [...screen.surfaces, ...EMPTY_SELECTORS, ...ERROR_SELECTORS]
  await page.waitForFunction(({ candidates, loadingSelectors }) => {
    const visible = (element) => {
      if (!(element instanceof HTMLElement)) return false
      const style = getComputedStyle(element)
      const rect = element.getBoundingClientRect()
      return style.display !== 'none' && style.visibility !== 'hidden' && Number(style.opacity || 1) > 0 && rect.width > 0 && rect.height > 0
    }
    const loading = loadingSelectors.some((selector) => [...document.querySelectorAll(selector)].some(visible))
    if (loading) return false
    return candidates.some((selector) => [...document.querySelectorAll(selector)].some(visible))
  }, { candidates: selectors, loadingSelectors: LOADING_SELECTORS }, { timeout: 20_000 })
}

async function measure(page, screen, viewport) {
  return page.evaluate(({ screenId, screenTitle, viewportKey, surfaceSelectors, emptySelectors, errorSelectors }) => {
    const visible = (element) => {
      if (!(element instanceof HTMLElement)) return false
      const style = getComputedStyle(element)
      const rect = element.getBoundingClientRect()
      return style.display !== 'none' && style.visibility !== 'hidden' && Number(style.opacity || 1) > 0 && rect.width > 0 && rect.height > 0
    }
    const firstVisible = (selectors) => {
      for (const selector of selectors) {
        const node = [...document.querySelectorAll(selector)].find(visible)
        if (node) return { selector, node, rect: node.getBoundingClientRect() }
      }
      return null
    }
    const visibleElements = (selector) => [...document.querySelectorAll(selector)].filter(visible)
    const root = document.querySelector('.gd-business-view') || document.querySelector('main') || document.body
    const surface = firstVisible(surfaceSelectors)
    const empty = firstVisible(emptySelectors)
    const failure = firstVisible(errorSelectors)
    const detected = surface || empty || failure
    const detectorStatus = surface ? 'surface' : empty ? 'legitimate-empty' : failure ? 'error-state' : 'not-found'
    const matchedSelector = detected?.selector || null
    const matchedBox = detected ? {
      x: Math.round(detected.rect.x), y: Math.round(detected.rect.y),
      width: Math.round(detected.rect.width), height: Math.round(detected.rect.height),
      right: Math.round(detected.rect.right), bottom: Math.round(detected.rect.bottom)
    } : null
    const operationalTop = matchedBox?.y ?? null
    const foldLimit = Math.min(window.innerHeight, operationalTop == null ? window.innerHeight : Math.max(operationalTop + 80, 0))
    const explanationText = visibleElements('p, .mp-note, small')
      .filter((node) => {
        const rect = node.getBoundingClientRect()
        return root.contains(node) && rect.top >= 0 && rect.top < foldLimit && !node.closest('table, .dt, .gd-review-workspace__queue, .pr-rows, .rk-rows')
      })
      .map((node) => String(node.textContent || '').replace(/\s+/g, ' ').trim())
      .filter(Boolean)
    const headings = visibleElements('h1').map((node) => String(node.textContent || '').trim()).filter(Boolean)
    const shellTitle = headings[0] || ''
    const duplicateTitleCount = shellTitle
      ? visibleElements('h1, h2, h3, .mp-card__title, .gm-section-title')
        .filter((node) => String(node.textContent || '').replace(/\s+/g, ' ').trim() === shellTitle).length
      : 0
    const viewportWidth = document.documentElement.clientWidth
    const horizontalOverflow = Math.max(0, Math.round(document.documentElement.scrollWidth - viewportWidth))
    const overflowOffenders = [...document.body.querySelectorAll('*')]
      .filter((element) => {
        if (!(element instanceof HTMLElement) || !visible(element)) return false
        const style = getComputedStyle(element)
        const rect = element.getBoundingClientRect()
        if (style.position === 'fixed' || style.position === 'sticky') return false
        if (element.closest('.mc-table-wrap, .dt__scroll, .table-scroll, [data-horizontal-scroll]')) return false
        return rect.right > viewportWidth + 8 || rect.left < -8
      })
      .slice(0, 8)
      .map((element) => {
        const rect = element.getBoundingClientRect()
        return {
          tag: element.tagName.toLowerCase(),
          className: String(element.className || '').slice(0, 120),
          left: Math.round(rect.left), right: Math.round(rect.right), width: Math.round(rect.width)
        }
      })
    const hero = document.querySelector('.gdb-overview')
    return {
      screenId, screenTitle, viewportKey,
      url: location.pathname + location.search,
      detectorStatus, matchedSelector, matchedBox,
      h1Count: headings.length, headings, duplicateTitleCount,
      deprecatedIntroCount: visibleElements('.gd-page-intro').length,
      horizontalOverflow, overflowOffenders,
      operationalTop,
      operationalAboveFold: operationalTop != null && operationalTop < window.innerHeight,
      visibleActionCountAboveFold: visibleElements('button, a[href]').filter((node) => {
        const rect = node.getBoundingClientRect()
        return rect.top >= 0 && rect.bottom <= window.innerHeight
      }).length,
      explanationBlocksAboveWork: explanationText.length,
      explanationCharsAboveWork: explanationText.join(' ').length,
      dashboardHeroHeight: hero && visible(hero) ? Math.round(hero.getBoundingClientRect().height) : null,
      proposalNestedQueueVisible: visibleElements('.pr-pane .prc .gd-review-workspace__queue').length,
      proposalNestedBusinessBarVisible: visibleElements('.pr-pane .prc .gd-review-workspace__business-bar').length,
      proposalOuterQueueVisible: visibleElements('.pr-list').length,
      forbiddenVisible: visibleElements('.forbidden-state, [data-state="forbidden"]').length,
      errorText: failure ? String(failure.node.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 500) : ''
    }
  }, {
    screenId: screen.id,
    screenTitle: screen.title,
    viewportKey: viewport.key,
    surfaceSelectors: screen.surfaces,
    emptySelectors: EMPTY_SELECTORS,
    errorSelectors: ERROR_SELECTORS
  })
}

function collectHardFailures(row) {
  const failures = []
  const prefix = `${row.screenId}/${row.viewportKey}`
  if (row.detectorStatus === 'not-found') failures.push(`${prefix}: 检测器未找到工作面或合法空态；selectors=${row.matchedSelector || 'none'}`)
  if (row.detectorStatus === 'error-state') failures.push(`${prefix}: 页面进入错误态：${row.errorText || '无错误说明'}`)
  if (row.deprecatedIntroCount > 0) failures.push(`${prefix}: 仍显示 gd-page-intro`)
  if (row.horizontalOverflow > 8) failures.push(`${prefix}: 页面横向溢出 ${row.horizontalOverflow}px；offenders=${JSON.stringify(row.overflowOffenders)}`)
  if (row.h1Count > 1) failures.push(`${prefix}: 可见 H1 ${row.h1Count} 个`)
  if (!row.operationalAboveFold) failures.push(`${prefix}: 工作面 ${row.matchedSelector || '未识别'} 未进入首屏；box=${JSON.stringify(row.matchedBox)}`)
  if (row.forbiddenVisible > 0) failures.push(`${prefix}: 学校管理员上下文出现 Forbidden`)
  if (row.screenId === 'dashboard' && row.dashboardHeroHeight != null && row.dashboardHeroHeight > 135) {
    failures.push(`${prefix}: 总览摘要区 ${row.dashboardHeroHeight}px，挤占真实待办`)
  }
  if (['proposal-pending', 'proposals'].includes(row.screenId)) {
    if (row.proposalNestedQueueVisible > 0) failures.push(`${prefix}: 出现队列套队列`)
    if (row.proposalNestedBusinessBarVisible > 0) failures.push(`${prefix}: 当前学生/课题重复显示`)
    if (row.detectorStatus === 'surface' && row.proposalOuterQueueVisible !== 1) failures.push(`${prefix}: 外层真实队列数量 ${row.proposalOuterQueueVisible}`)
  }
  return failures
}

test.describe.serial('V6 · 24-page real-browser usability and text-density audit', () => {
  test.setTimeout(22 * 60_000)
  let fixture

  test.beforeAll(async () => {
    expect(SCREENS, 'production graduation navigation must expose exactly 24 audit targets').toHaveLength(24)
    expect(CHUNKS.every((chunk) => chunk.length === 6)).toBeTruthy()
    fixture = await prepareGraduationFixture()
  })

  for (const [chunkIndex, screens] of CHUNKS.entries()) {
    test(`chunk ${chunkIndex + 1}/4 · six production menu pages`, async ({ page }, testInfo) => {
      await page.setViewportSize({ width: 1760, height: 900 })
      await new StaffLoginPage(page, config.staffBaseUrl).login(config.sandboxAdmin)
      const results = []
      const hardFailures = []
      const setupErrors = []

      for (const screen of screens) {
        try {
          await page.setViewportSize({ width: 1760, height: 900 })
          await resetViewportState(page, 1)
          await page.goto(screenUrl(config.staffBaseUrl, screen.path, fixture.batchId))
          await dismissGuide(page)
          await page.waitForLoadState('domcontentloaded')
          await waitForPageReady(page, screen)
          await expect(page.locator('body')).not.toContainText(/页面加载失败|路由加载失败|Cannot read properties of|Unexpected token/)

          for (const viewport of VIEWPORTS) {
            await page.setViewportSize({ width: viewport.width, height: viewport.height })
            await resetViewportState(page, viewport.zoom)
            await page.waitForTimeout(180)
            const row = await measure(page, screen, viewport)
            results.push(row)
            hardFailures.push(...collectHardFailures(row))

            if (viewport.screenshot) {
              const file = testInfo.outputPath(`gd-v6-${screen.id}-${viewport.key}.png`)
              await page.screenshot({ path: file, fullPage: false, animations: 'disabled', caret: 'hide' })
              await testInfo.attach(`gd-v6-${screen.id}-${viewport.key}`, { path: file, contentType: 'image/png' })
            }
          }
        } catch (error) {
          const message = `${screen.id}: ${error instanceof Error ? error.message : String(error)}`
          setupErrors.push(message)
          hardFailures.push(`setup/${message}`)
          const file = testInfo.outputPath(`gd-v6-${screen.id}-setup-failure.png`)
          await page.screenshot({ path: file, fullPage: false, animations: 'disabled', caret: 'hide' }).catch(() => {})
          if (await fs.stat(file).catch(() => null)) {
            await testInfo.attach(`gd-v6-${screen.id}-setup-failure`, { path: file, contentType: 'image/png' })
          }
        } finally {
          await resetViewportState(page, 1).catch(() => {})
        }
      }

      const densityRanking = results
        .filter((row) => row.viewportKey === '1440')
        .slice()
        .sort((a, b) => b.explanationCharsAboveWork - a.explanationCharsAboveWork)
        .map((row) => ({
          screenId: row.screenId,
          screenTitle: row.screenTitle,
          explanationCharsAboveWork: row.explanationCharsAboveWork,
          explanationBlocksAboveWork: row.explanationBlocksAboveWork,
          operationalTop: row.operationalTop,
          matchedSelector: row.matchedSelector,
          matchedBox: row.matchedBox,
          detectorStatus: row.detectorStatus,
          visibleActionCountAboveFold: row.visibleActionCountAboveFold
        }))

      const report = {
        contract: 'graduation-v6-24page-usability-audit-v2',
        head: process.env.GITHUB_SHA || 'local',
        batchId: fixture.batchId,
        chunkIndex: chunkIndex + 1,
        expectedScreens: screens.map((screen) => screen.id),
        measuredScreens: [...new Set(results.map((row) => row.screenId))],
        viewports: VIEWPORTS,
        setupErrors,
        hardFailures,
        densityRanking,
        results
      }
      const reportPath = testInfo.outputPath(`graduation-v6-24page-usability-audit-chunk-${chunkIndex + 1}.json`)
      await fs.writeFile(reportPath, JSON.stringify(report, null, 2), 'utf8')
      await testInfo.attach(`graduation-v6-24page-usability-audit-chunk-${chunkIndex + 1}`, { path: reportPath, contentType: 'application/json' })

      expect(report.measuredScreens, `chunk ${chunkIndex + 1} must retain evidence for all six production screens`).toHaveLength(6)
      expect(hardFailures, `chunk ${chunkIndex + 1} must have no structural usability blocker`).toEqual([])
    })
  }
})
