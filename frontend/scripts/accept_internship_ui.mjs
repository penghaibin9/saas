/* eslint-env node */
/**
 * 岗位实习 PC 页面多角色点击验收（Playwright）
 * 用法：cd frontend && node scripts/accept_internship_ui.mjs
 */
import { chromium } from 'playwright'

// eslint-disable-next-line no-undef -- Node 脚本，flat config 未启用 node globals
const BASE = process.env.UI_BASE || 'http://127.0.0.1:5173'
const PWD = '123456'

const PAGES = [
  { path: '/admin/internship/plans', expect: '实习计划书' },
  { path: '/admin/internship/plans?panel=tasks', expect: '实习任务清单' },
  { path: '/admin/internship/plans?panel=progress', expect: '任务完成度跟踪' },
  { path: '/admin/internship/insurance', expect: '实习保险核验' },
  { path: '/admin/internship/agreements', expect: '申请与协议' },
  { path: '/admin/internship/changes', expect: '实习变更审核' },
  { path: '/admin/internship/reports?type=daily', expect: '日报批阅' }
]

async function login(page, loginName) {
  await page.goto(`${BASE}/login`, { waitUntil: 'networkidle' })
  await page.locator('input.in').first().fill(loginName)
  await page.locator('input.in[type="password"]').fill(PWD)
  await page.locator('button.lg-btn--p').click({ force: true })
  await page.waitForFunction(() => !location.pathname.includes('/login'), null, { timeout: 15000 })
  await page.waitForTimeout(500)
}

async function visitPages(page, role) {
  const results = []
  for (const p of PAGES) {
    await page.goto(`${BASE}${p.path}`, { waitUntil: 'networkidle' })
    if (p.path.includes('panel=tasks') || p.path.includes('panel=progress')) {
      const sel = p.path.includes('progress') ? '.card--progress' : '.card--tasks'
      await page.waitForSelector(sel, { timeout: 20000 }).catch(() => null)
      await page.waitForTimeout(1500)
    } else {
      await page.waitForTimeout(800)
    }
    const body = await page.locator('body').innerText()
    const ok = body.includes(p.expect)
    results.push({ role, path: p.path, ok, expect: p.expect })
    console.log(`${ok ? '[OK]' : '[FAIL]'} ${role} ${p.path} -> "${p.expect}"`)
    if (!ok) console.log('  snippet:', body.slice(0, 200).replace(/\s+/g, ' '))
  }
  return results
}

// eslint-disable-next-line no-unused-vars -- 保留：计划书保存链路的备用验收步骤
async function clickPlanSave(page, role) {
  await page.goto(`${BASE}/admin/internship/plans`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(1000)
  const saveBtn = page.getByRole('button', { name: '保存草稿' })
  if (await saveBtn.count()) {
    await saveBtn.click()
    await page.waitForTimeout(1200)
    const toast = await page.locator('body').innerText()
    const ok = /保存|成功|草稿/.test(toast)
    console.log(`${ok ? '[OK]' : '[WARN]'} ${role} 点击保存草稿`)
  }
}

async function main() {
  const browser = await chromium.launch({ headless: true })
  const all = []
  for (const account of [
    { role: '演示管理员', login: 'admin' },
    { role: '演示教师', login: 'teacher' }
  ]) {
    const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } })
    const page = await ctx.newPage()
    try {
      await login(page, account.login)
      console.log(`\n=== ${account.role} (${account.login}) 已登录 ===`)
      all.push(...await visitPages(page, account.role))
    } catch (e) {
      console.error(`[FAIL] ${account.role}:`, e.message)
      all.push({ role: account.role, path: 'login', ok: false, expect: e.message })
    } finally {
      await ctx.close()
    }
  }
  await browser.close()
  const failed = all.filter((r) => !r.ok)
  if (failed.length) {
    console.error(`\n页面验收失败 ${failed.length} 项`)
    // eslint-disable-next-line no-undef -- Node 脚本
    process.exit(1)
  }
  console.log('\n多角色 PC 页面点击验收全部通过。')
}

main()
