import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { loginApi } from '../lib/api-fixture.mjs'

const VIEWPORT = { width: 1440, height: 1000 }

async function openWithApiSession(page, api, path) {
  await page.addInitScript(({ token }) => {
    window.sessionStorage.setItem('gx_pc_token_v1', token)
  }, { token: api.token })
  await page.goto(`${config.staffBaseUrl}${path}`)
}

test('Golden risk layout contract · capture computed metric grid evidence', async ({ page }, testInfo) => {
  await page.setViewportSize(VIEWPORT)
  const api = await loginApi(config.sandboxAdmin)
  await openWithApiSession(page, api, '/admin/student-affairs/risk')

  const metrics = page.locator('.sa-grid--metrics')
  await expect(metrics).toBeVisible()

  const evidence = await metrics.evaluate((el) => {
    const style = getComputedStyle(el)
    const rules = []

    const walkRules = (ruleList, context = '') => {
      for (const rule of Array.from(ruleList || [])) {
        if (rule instanceof CSSMediaRule) {
          const active = window.matchMedia(rule.conditionText).matches
          walkRules(rule.cssRules, `${context} @media ${rule.conditionText} active=${active}`)
          continue
        }
        if (!(rule instanceof CSSStyleRule) || !rule.selectorText?.includes('sa-grid--metrics')) continue
        try {
          if (el.matches(rule.selectorText)) {
            rules.push({ context, selector: rule.selectorText, cssText: rule.style.cssText })
          }
        } catch (_) {}
      }
    }

    for (const sheet of Array.from(document.styleSheets)) {
      try { walkRules(sheet.cssRules, sheet.href || 'inline') } catch (_) {}
    }

    return {
      innerWidth: window.innerWidth,
      outerWidth: window.outerWidth,
      devicePixelRatio: window.devicePixelRatio,
      media960: window.matchMedia('(max-width: 960px)').matches,
      media1280: window.matchMedia('(max-width: 1280px)').matches,
      display: style.display,
      width: style.width,
      flex: style.flex,
      gridTemplateColumns: style.gridTemplateColumns,
      gridAutoFlow: style.gridAutoFlow,
      className: el.className,
      ancestors: Array.from({ length: 6 }, (_, index) => {
        let node = el
        for (let i = 0; i <= index; i += 1) node = node?.parentElement
        return node ? `${node.tagName}.${String(node.className || '').replace(/\s+/g, '.')}` : null
      }).filter(Boolean),
      cards: Array.from(el.children).map((card) => {
        const cardStyle = getComputedStyle(card)
        const rect = card.getBoundingClientRect()
        return {
          className: card.className,
          width: Math.round(rect.width * 100) / 100,
          left: Math.round(rect.left * 100) / 100,
          top: Math.round(rect.top * 100) / 100,
          gridColumn: cardStyle.gridColumn,
          minWidth: cardStyle.minWidth
        }
      }),
      matchingRules: rules
    }
  })

  const body = Buffer.from(JSON.stringify(evidence, null, 2), 'utf8')
  await testInfo.attach('student-affairs-risk-layout-contract', { body, contentType: 'application/json' })

  expect(evidence.innerWidth).toBe(VIEWPORT.width)
  expect(evidence.display).toBe('grid')
})
