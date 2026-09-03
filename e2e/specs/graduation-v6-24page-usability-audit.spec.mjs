import fs from 'node:fs/promises'

import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { prepareGraduationFixture } from '../lib/api-fixture.mjs'
import { StaffLoginPage } from '../pages/login.page.mjs'

const VIEWPORTS = [
  { key: '1760', width: 1760, height: 900, zoom: 1 },
  { key: '1440', width: 1440, height: 900, zoom: 1, screenshot: true },
  { key: '1366', width: 1366, height: 768, zoom: 1 },
  { key: '1280', width: 1280, height: 800, zoom: 1, screenshot: true },
  { key: '1366-125pct', width: 1366, height: 768, zoom: 1.25 }
]

const SCREENS = [
  { id: 'dashboard', title: '毕设总览', path: '/admin/graduation' },
  { id: 'proposal-pending', title: '待评阅开题', path: '/admin/graduation/proposals?tab=PENDING_REVIEW' },
  { id: 'final-pending', title: '待评阅成果', path: '/admin/graduation/finals?tab=PENDING_REVIEW' },
  { id: 'defense-mine', title: '我的答辩评分', path: '/admin/graduation/defense-scoring' },
  { id: 'batches', title: '批次与规则', path: '/admin/graduation/batches?panel=list' },
  { id: 'students', title: '学生与进度', path: '/admin/graduation/students?panel=roster' },
  { id: 'mentors', title: '导师与分配', path: '/admin/graduation/mentors?panel=list' },
  { id: 'mentor-conflicts', title: '分配冲突检测', path: '/admin/graduation/mentors/conflicts' },
  { id: 'topic-lib', title: '题目库', path: '/admin/graduation/topic-lib?panel=list' },
  { id: 'topic-rounds', title: '选题轮次', path: '/admin/graduation/topic-rounds?panel=rounds' },
  { id: 'topic-changes', title: '题目调整申请', path: '/admin/graduation/topic-changes' },
  { id: 'process', title: '过程指导台', path: '/admin/graduation/process?panel=taskbook' },
  { id: 'proposals', title: '开题报告批阅', path: '/admin/graduation/proposals' },
  { id: 'finals', title: '成果提交与批阅', path: '/admin/graduation/finals' },
  { id: 'material-center', title: '毕设材料中心', path: '/admin/graduation/material-center' },
  { id: 'plagiarism', title: '查重记录', path: '/admin/graduation/plagiarism-ledger' },
  { id: 'review-center', title: '统一评阅中心', path: '/admin/graduation/review-tasks' },
  { id: 'defense', title: '答辩安排', path: '/admin/graduation/defense' },
  { id: 'defense-score', title: '答辩评分', path: '/admin/graduation/defense-scoring' },
  { id: 'defense-confirmation', title: '答辩秘书确认', path: '/admin/graduation/defense-confirmation' },
  { id: 'grade-ledger', title: '成绩台账', path: '/admin/graduation/grade-ledger?mode=batch' },
  { id: 'risk', title: '问题预警', path: '/admin/graduation/risk-archive?panel=risk' },
  { id: 'archive', title: '毕设材料归档', path: '/admin/graduation/risk-archive?panel=archive' },
  { id: 'templates', title: '全部模板', path: '/admin/graduation/templates' }
]

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

async function measure(page, screen, viewport) {
  return page.evaluate(({ screenId, screenTitle, viewportKey }) => {
    const visible = (element) => {
      if (!(element instanceof HTMLElement)) return false
      const style = getComputedStyle(element)
      const rect = element.getBoundingClientRect()
      return style.display !== 'none' && style.visibility !== 'hidden' && Number(style.opacity || 1) > 0 && rect.width > 0 && rect.height > 0
    }
    const visibleElements = (selector) => [...document.querySelectorAll(selector)].filter(visible)
    const root = document.querySelector('.gd-business-view') || document.querySelector('main') || document.body
    const heading = visibleElements('h1').map((node) => String(node.textContent || '').trim()).filter(Boolean)
    const operationalSelectors = [
      '.gdb-work', '.pr-split', '.gd-review-workspace', '.gp-layout', '.rk-split',
      '.dg-batch', '.dt', 'table', 'form', '[role="tabpanel"]', '.mp-card',
      '.empty-state', '.mp-empty', '.app-empty-state'
    ]
    const operational = operationalSelectors
      .flatMap((selector) => visibleElements(selector))
      .map((node) => ({ node, rect: node.getBoundingClientRect() }))
      .filter(({ rect }) => rect.bottom > 0)
      .sort((a, b) => a.rect.top - b.rect.top)[0]
    const operationalTop = operational ? Math.round(operational.rect.top) : null
    const foldLimit = Math.min(window.innerHeight, operationalTop == null ? window.innerHeight : Math.max(operationalTop + 80, 0))
    const explanatoryNodes = visibleElements('p, .mp-note, small')
      .filter((node) => {
        const rect = node.getBoundingClientRect()
        return root.contains(node) && rect.top >= 0 && rect.top < foldLimit && !node.closest('table, .dt, .gd-review-workspace__queue, .pr-rows, .rk-rows')
      })
    const explanationText = explanatoryNodes.map((node) => String(node.textContent || '').replace(/\s+/g, ' ').trim()).filter(Boolean)
    const shellTitle = heading[0] || ''
    const duplicateTitleCount = shellTitle
      ? visibleElements('h1, h2, h3, .mp-card__title, .gm-section-title')
        .filter((node) => String(node.textContent || '').replace(/\s+/g, ' ').trim() === shellTitle).length
      : 0
    const hero = document.querySelector('.gdb-overview')
    const bodyText = String(root.textContent || '').replace(/\s+/g, ' ').trim()
    return {
      screenId,
      screenTitle,
      viewportKey,
      url: location.pathname + location.search,
      h1Count: heading.length,
      headings: heading,
      duplicateTitleCount,
      deprecatedIntroCount: visibleElements('.gd-page-intro').length,
      horizontalOverflow: Math.max(0, Math.round(document.documentElement.scrollWidth - window.innerWidth)),
      operationalTop,
      operationalAboveFold: operationalTop != null && operationalTop < window.innerHeight,
      visibleActionCountAboveFold: visibleElements('button, a[href]').filter((node) => {
        const rect = node.getBoundingClientRect()
        return rect.top >= 0 && rect.bottom <= window.innerHeight
      }).length,
      explanationBlocksAboveWork: explanationText.length,
      explanationCharsAboveWork: explanationText.join(' ').length,
      bodyChars: bodyText.length,
      dashboardHeroHeight: hero && visible(hero) ? Math.round(hero.getBoundingClientRect().height) : null,
      proposalNestedQueueVisible: visibleElements('.pr-pane .prc .gd-review-workspace__queue').length,
      proposalNestedBusinessBarVisible: visibleElements('.pr-pane .prc .gd-review-workspace__business-bar').length,
      proposalOuterQueueVisible: visibleElements('.pr-list').length,
      forbiddenVisible: visibleElements('.forbidden-state, [data-state="forbidden"]').length,
      documentTitle: document.title
    }
  }, { screenId: screen.id, screenTitle: screen.title, viewportKey: viewport.key })
}

test.describe.serial('V6 · 24-page real-browser usability and text-density audit', () => {
  test.setTimeout(20 * 60_000)

  test('24 pages · four widths + 125% · engineering surface before explanation', async ({ page }, testInfo) => {
    const fixture = await prepareGraduationFixture()
    await new StaffLoginPage(page, config.staffBaseUrl).login(config.sandboxAdmin)

    const results = []
    const hardFailures = []

    for (const screen of SCREENS) {
      await page.setViewportSize({ width: 1760, height: 900 })
      await page.goto(screenUrl(config.staffBaseUrl, screen.path, fixture.batchId))
      await dismissGuide(page)
      await page.waitForLoadState('networkidle', { timeout: 8000 }).catch(() => {})
      await expect(page.locator('body')).not.toContainText(/页面加载失败|路由加载失败|Cannot read properties of|Unexpected token/)

      for (const viewport of VIEWPORTS) {
        await page.setViewportSize({ width: viewport.width, height: viewport.height })
        await page.evaluate((zoom) => { document.documentElement.style.zoom = String(zoom) }, viewport.zoom)
        await page.waitForTimeout(120)
        const row = await measure(page, screen, viewport)
        results.push(row)

        if (row.deprecatedIntroCount > 0) hardFailures.push(`${screen.id}/${viewport.key}: 仍显示 gd-page-intro`)
        if (row.horizontalOverflow > 8) hardFailures.push(`${screen.id}/${viewport.key}: 横向溢出 ${row.horizontalOverflow}px`)
        if (row.h1Count > 1) hardFailures.push(`${screen.id}/${viewport.key}: 可见 H1 ${row.h1Count} 个`)
        if (!row.operationalAboveFold) hardFailures.push(`${screen.id}/${viewport.key}: 首屏没有真实工程操作面`)
        if (row.forbiddenVisible > 0) hardFailures.push(`${screen.id}/${viewport.key}: 管理员上下文出现 Forbidden`)
        if (screen.id === 'dashboard' && row.dashboardHeroHeight != null && row.dashboardHeroHeight > 150) {
          hardFailures.push(`${screen.id}/${viewport.key}: 摘要区 ${row.dashboardHeroHeight}px，挤占真实待办`)
        }
        if (['proposal-pending', 'proposals'].includes(screen.id)) {
          if (row.proposalNestedQueueVisible > 0) hardFailures.push(`${screen.id}/${viewport.key}: 出现队列套队列`)
          if (row.proposalNestedBusinessBarVisible > 0) hardFailures.push(`${screen.id}/${viewport.key}: 当前学生/课题重复显示`)
          if (row.proposalOuterQueueVisible !== 1) hardFailures.push(`${screen.id}/${viewport.key}: 外层真实队列数量 ${row.proposalOuterQueueVisible}`)
        }

        if (viewport.screenshot) {
          const file = testInfo.outputPath(`gd-v6-${screen.id}-${viewport.key}.png`)
          await page.screenshot({ path: file, fullPage: false, animations: 'disabled', caret: 'hide' })
          await testInfo.attach(`gd-v6-${screen.id}-${viewport.key}`, { path: file, contentType: 'image/png' })
        }
      }

      await page.evaluate(() => { document.documentElement.style.zoom = '1' })
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
        visibleActionCountAboveFold: row.visibleActionCountAboveFold
      }))

    const report = {
      contract: 'graduation-v6-24page-usability-audit-v1',
      head: process.env.GITHUB_SHA || 'local',
      batchId: fixture.batchId,
      screenCount: SCREENS.length,
      viewports: VIEWPORTS,
      hardFailures,
      densityRanking,
      results
    }
    const reportPath = testInfo.outputPath('graduation-v6-24page-usability-audit.json')
    await fs.writeFile(reportPath, JSON.stringify(report, null, 2), 'utf8')
    await testInfo.attach('graduation-v6-24page-usability-audit', { path: reportPath, contentType: 'application/json' })

    expect(SCREENS).toHaveLength(24)
    expect(hardFailures, '24-page browser audit must have no structural usability blocker').toEqual([])
  })
})
