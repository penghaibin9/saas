import fs from 'node:fs'
import path from 'node:path'
import { test } from '@playwright/test'
import { config } from '../lib/config.mjs'
import { StaffLoginPage, StudentLoginPage } from '../pages/login.page.mjs'

const ROOT = path.resolve(process.cwd(), 'test-results', 'website-assets')
const SCREENSHOT_ROOT = path.join(ROOT, 'screenshots')
const manifest = []

function ensureDir(dir) {
  fs.mkdirSync(dir, { recursive: true })
}

function safeName(value) {
  return String(value).replace(/[^a-zA-Z0-9-_]+/g, '-').replace(/^-+|-+$/g, '')
}

function failed(group, key, label, route, error) {
  manifest.push({
    group, key, label, route, status: 'FAILED',
    error: String(error?.message || error).slice(0, 800),
    capturedAt: new Date().toISOString()
  })
}

async function dismissGuides(page) {
  const guide = page.getByRole('dialog', { name: '页面操作引导' })
  if (await guide.isVisible({ timeout: 600 }).catch(() => false)) {
    const skip = guide.getByRole('button', { name: '跳过引导' })
    if (await skip.isVisible({ timeout: 600 }).catch(() => false)) await skip.click()
  }
  for (const label of ['知道了', '以后再说', '关闭']) {
    const button = page.getByRole('button', { name: label }).first()
    if (await button.isVisible({ timeout: 250 }).catch(() => false)) await button.click().catch(() => {})
  }
}

async function settle(page) {
  await page.waitForLoadState('domcontentloaded').catch(() => {})
  await page.waitForLoadState('networkidle', { timeout: 5_000 }).catch(() => {})
  await dismissGuides(page)
  await page.waitForTimeout(1_000)
}

async function recordShot(page, { group, key, label, route, viewport = false }) {
  const dir = path.join(SCREENSHOT_ROOT, group)
  ensureDir(dir)
  const file = `${safeName(key)}.png`
  const output = path.join(dir, file)
  const bodyText = (await page.locator('body').innerText().catch(() => '')).slice(0, 5_000)
  const finalUrl = page.url()
  const status = /403|无权限|禁止访问|页面不存在|404|登录失败/.test(bodyText) || /\/login(?:\?|$)/.test(finalUrl)
    ? 'REVIEW'
    : 'CAPTURED'
  await page.screenshot({ path: output, fullPage: !viewport, animations: 'disabled' })
  manifest.push({ group, key, label, route, finalUrl, file: path.relative(ROOT, output), status, capturedAt: new Date().toISOString() })
}

async function gotoStaff(page, staffLogin, route) {
  const target = new URL(route, config.staffBaseUrl).toString()
  await page.goto(target, { waitUntil: 'domcontentloaded', timeout: 30_000 })
  await settle(page)
  if (/\/login(?:\?|$)/.test(page.url())) {
    await staffLogin.login(config.sandboxAdmin)
    await settle(page)
    await page.goto(target, { waitUntil: 'domcontentloaded', timeout: 30_000 })
    await settle(page)
  }
  await page.locator('body').waitFor({ state: 'visible', timeout: 10_000 })
}

async function captureStaff(page) {
  await page.setViewportSize({ width: 1536, height: 1024 })
  const login = new StaffLoginPage(page, config.staffBaseUrl)
  await login.login(config.sandboxAdmin)
  await settle(page)

  const pages = [
    ['workbench', 'workbench', '统一工作台', '/workbench'],
    ['workbench', 'leadership-cockpit', '领导数据驾驶舱', '/admin/data-center'],
    ['workbench', 'approval-center', '审批中心', '/admin/approval'],
    ['workbench', 'message-center', '消息中心', '/admin/messages/inbox'],
    ['internship', 'overview', '岗位实习总览', '/admin/internship'],
    ['internship', 'risk-dashboard', '岗位实习风险看板', '/admin/internship/risks'],
    ['internship', 'enterprise-list', '实习企业管理', '/admin/internship/enterprises'],
    ['internship', 'weekly-reports', '实习周报与任务', '/admin/internship/reports'],
    ['graduation', 'overview', '毕业设计总览', '/admin/graduation'],
    ['graduation', 'student-progress', '毕业设计学生进度', '/admin/graduation/students?panel=progress'],
    ['graduation', 'defense', '毕业设计答辩安排', '/admin/graduation/defense'],
    ['student-affairs', 'overview', '学工总览', '/admin/student-affairs/dashboard'],
    ['student-affairs', 'student-master', '学生主档', '/admin/student/list'],
    ['academic-affairs', 'overview', '教务运行总览', '/admin/academic-affairs'],
    ['academic-affairs', 'quality', '教学质量', '/admin/academic-affairs/quality'],
    ['orientation', 'overview', '数字迎新看板', '/admin/orientation'],
    ['orientation', 'progress', '数字迎新报到进度', '/admin/orientation/progress']
  ]

  for (const [group, key, label, route] of pages) {
    try {
      await gotoStaff(page, login, route)
      await recordShot(page, { group, key, label, route })
    } catch (error) {
      failed(group, key, label, route, error)
    }
  }
}

async function captureStudentPortal(browser) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } })
  const page = await context.newPage()
  try {
    const login = new StudentLoginPage(page, config.studentBaseUrl)
    await login.login(config.student)
    await settle(page)
    await recordShot(page, { group: 'student-portal', key: 'home', label: '学生PC门户首页', route: page.url() })
  } catch (error) {
    failed('student-portal', 'home', '学生PC门户首页', '/portal', error)
  } finally {
    await context.close()
  }
}

async function miniLogin(page, role, account) {
  const base = String(process.env.E2E_MINIAPP_BASE_URL || 'http://127.0.0.1:5188').replace(/\/+$/, '')
  const loginPath = role === 'student' ? '/#/pages/login/student/index' : '/#/pages/login/teacher/index'
  await page.goto(`${base}${loginPath}`, { waitUntil: 'domcontentloaded', timeout: 30_000 })
  await settle(page)

  // Reuse the exact selector strategy already proven by the repository's
  // student-v3 and graduation teacher-mobile Playwright suites. uni-app H5
  // does not expose its input placeholder consistently to Playwright.
  const fields = page.getByRole('textbox')
  await fields.nth(0).fill(account.username)
  await fields.nth(1).fill(account.password)
  await page.getByText('填写', { exact: true }).click()
  await fields.nth(2).fill(account.tenant)
  await page.getByText('我已阅读并同意学校提供的', { exact: false }).click()

  const buttonText = role === 'student' ? '进入学生首页' : '进入教师工作台'
  await page.getByText(buttonText, { exact: true }).click()
  const targetUrl = role === 'student' ? /pages\/student\/home\/index/ : /pages\/teacher\/workbench\/index/
  await page.waitForURL(targetUrl, { timeout: 20_000 })
  await settle(page)
  return base
}

async function captureMiniappRole(browser, role, account, targets) {
  const group = role === 'student' ? 'student-mobile' : 'teacher-mobile'
  const context = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1 })
  const page = await context.newPage()
  try {
    const base = await miniLogin(page, role, account)
    for (const [key, label, route] of targets) {
      try {
        await page.goto(`${base}/#${route}`, { waitUntil: 'domcontentloaded', timeout: 30_000 })
        await settle(page)
        await recordShot(page, { group, key, label, route, viewport: true })
      } catch (error) {
        failed(group, key, label, route, error)
      }
    }
  } catch (error) {
    failed(group, 'login', `${role}移动端登录`, '', error)
  } finally {
    await context.close()
  }
}

function writeManifest() {
  ensureDir(ROOT)
  fs.writeFileSync(path.join(ROOT, 'capture-manifest.json'), JSON.stringify({
    baseCommit: process.env.E2E_EXPECTED_SHA || '',
    branch: process.env.GITHUB_HEAD_REF || process.env.GITHUB_REF_NAME || '',
    capturedAt: new Date().toISOString(),
    items: manifest
  }, null, 2))

  const lines = [
    '# 跃科官网真实产品截图采集清单',
    '',
    `- 基线：${process.env.E2E_EXPECTED_SHA || 'unknown'}`,
    `- 分支：${process.env.GITHUB_HEAD_REF || process.env.GITHUB_REF_NAME || 'unknown'}`,
    `- 采集时间：${new Date().toISOString()}`,
    '- 环境：GitHub Actions / isolated MySQL / real FastAPI / real Vue / Chromium',
    '- 数据：仅 E2E 沙箱测试数据，不连接生产数据库',
    '',
    '| 状态 | 分组 | 素材 | 文件 | 路由 |',
    '|---|---|---|---|---|',
    ...manifest.map((item) => `| ${item.status} | ${item.group} | ${item.label || item.key} | ${item.file || '-'} | ${item.route || item.finalUrl || '-'} |`),
    ''
  ]
  fs.writeFileSync(path.join(ROOT, 'README.md'), lines.join('\n'))
}

test('capture website marketing assets from isolated real stack', async ({ page, browser }) => {
  ensureDir(SCREENSHOT_ROOT)
  try {
    await captureStaff(page)
  } catch (error) {
    failed('staff-pc', 'login', '教师/管理PC登录', '/login', error)
  }
  await captureStudentPortal(browser)
  await captureMiniappRole(browser, 'student', config.student, [
    ['home', '学生移动端首页', '/pages/student/home/index'],
    ['internship', '学生移动端岗位实习', '/pages/student/internship/index'],
    ['graduation', '学生移动端毕业设计', '/pages/student/graduation/index'],
    ['schedule', '学生移动端我的课表', '/pages/student/academic-affairs/schedule']
  ])
  await captureMiniappRole(browser, 'teacher', config.mentor, [
    ['workbench', '教师移动工作台', '/pages/teacher/workbench/index'],
    ['todos', '教师今日待办', '/pages/teacher/todos/index'],
    ['internship-review', '教师实习周报批阅', '/pages/teacher/internship-review/index']
  ])
  writeManifest()
})
