/**
 * 消息中心桌面四尺寸截图验收（Playwright）。
 * 用法：在 frontend 目录 npx playwright 已装好后：
 *   node ../docs/06-开发施工与质量验收/施工记录/screenshots/capture-message-center.mjs
 */
import { chromium } from 'playwright'
import { mkdir, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const OUT = __dirname
const BASE = process.env.MC_SHOT_BASE || 'http://127.0.0.1:5173'
const API = process.env.MC_SHOT_API || 'http://127.0.0.1:8000/api/v1'
const LOGIN = process.env.MC_SHOT_USER || 'teacher'
const PASS = process.env.MC_SHOT_PASS || '123456'

const VIEWPORTS = [
  { name: '1440x900', width: 1440, height: 900 },
  { name: '1366x768', width: 1366, height: 768 },
  { name: '1280x800', width: 1280, height: 800 },
  { name: '1024x768', width: 1024, height: 768 }
]

const PAGES = [
  { key: 'inbox', path: '/admin/messages/inbox', wait: '.mc-inbox, .mc-compose, .mc-settings, h1' },
  { key: 'compose', path: '/admin/messages/compose', wait: '.mc-compose, .mc-steps' },
  { key: 'settings', path: '/admin/messages/settings', wait: '.mc-settings, h3' }
]

async function loginToken() {
  const res = await fetch(`${API}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ loginName: LOGIN, password: PASS, clientType: 'PC' })
  })
  const body = await res.json()
  if (!body || body.code !== 0) {
    throw new Error(`login failed: ${JSON.stringify(body)}`)
  }
  return body.data
}

async function measureOverflow(page) {
  return page.evaluate(() => {
    const doc = document.documentElement
    const body = document.body
    const scrollW = Math.max(doc.scrollWidth, body.scrollWidth)
    const clientW = doc.clientWidth
    return {
      scrollWidth: scrollW,
      clientWidth: clientW,
      horizontalOverflow: scrollW > clientW + 2
    }
  })
}

async function main() {
  await mkdir(OUT, { recursive: true })
  const auth = await loginToken()
  const browser = await chromium.launch({ headless: true })
  const report = { capturedAt: new Date().toISOString(), base: BASE, user: LOGIN, shots: [] }

  for (const vp of VIEWPORTS) {
    const context = await browser.newContext({
      viewport: { width: vp.width, height: vp.height }
    })
    await context.addInitScript(
      ({ access, refresh }) => {
        sessionStorage.setItem('gx_pc_token_v1', access)
        sessionStorage.setItem('gx_pc_refresh_v1', refresh || '')
      },
      { access: auth.accessToken, refresh: auth.refreshToken || '' }
    )
    const page = await context.newPage()
    // 先落首页，跳过工作台引导（避免遮挡后续页面）
    await page.goto(`${BASE}/`, { waitUntil: 'domcontentloaded', timeout: 60000 })
    try {
      const skip = page.getByText('跳过引导')
      if (await skip.isVisible({ timeout: 3000 })) await skip.click()
    } catch { /* no guide */ }
    await page.waitForTimeout(500)

    for (const p of PAGES) {
      const url = `${BASE}${p.path}`
      await page.goto(url, { waitUntil: 'networkidle', timeout: 60000 })
      try {
        const skip = page.getByText('跳过引导')
        if (await skip.isVisible({ timeout: 1500 })) await skip.click()
      } catch { /* no guide */ }
      try {
        await page.waitForSelector(p.wait, { timeout: 20000 })
      } catch {
        /* 无权限或空态也截图 */
      }
      await page.waitForTimeout(800)
      const title = await page.locator('h1, .module-page-shell__title, .mc-steps').first().textContent().catch(() => '')
      const overflow = await measureOverflow(page)
      const file = `mc-${p.key}-${vp.name}.png`
      const full = path.join(OUT, file)
      await page.screenshot({ path: full, fullPage: false })
      report.shots.push({
        file,
        page: p.key,
        viewport: vp.name,
        url,
        title: (title || '').trim().slice(0, 80),
        ...overflow
      })
      console.log('wrote', file, 'title=', (title || '').trim().slice(0, 40), 'overflow=', overflow.horizontalOverflow)
    }
    await context.close()
  }

  await browser.close()
  await writeFile(path.join(OUT, 'capture-report.json'), JSON.stringify(report, null, 2), 'utf8')
  console.log('done', report.shots.length, 'shots')
  const bad = report.shots.filter((s) => s.horizontalOverflow)
  if (bad.length) {
    console.error('HORIZONTAL_OVERFLOW', bad.map((b) => b.file).join(','))
    process.exitCode = 2
  }
}

main().catch((e) => {
  console.error(e)
  process.exit(1)
})
