import fs from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { prepareGraduationFixture } from '../lib/api-fixture.mjs'
import { prepareGraduationTeacherMobileGoldFixture, u8TeacherAccount } from '../lib/graduation-u8-fixture.mjs'
import { StaffLoginPage, StudentLoginPage } from '../pages/login.page.mjs'

const VIEWPORTS = [
  { width: 1920, height: 1080 },
  { width: 1440, height: 900 },
  { width: 1280, height: 800 }
]
const MOBILE_VIEWPORTS = [
  { width: 390, height: 844 },
  { width: 375, height: 812 }
]
const MINI_BASE_URL = process.env.E2E_MINIAPP_BASE_URL || 'http://127.0.0.1:5188'
const ARTIFACT_DIR = process.env.E2E_ARTIFACT_DIR
  ? path.resolve(process.env.E2E_ARTIFACT_DIR, 'graduation-v8/viewport-accessibility')
  : fileURLToPath(new URL('../artifacts/graduation-v8/viewport-accessibility/', import.meta.url))

async function settle(page) {
  await page.evaluate(async () => {
    if (document.fonts?.ready) await document.fonts.ready
  })
  await page.waitForLoadState('networkidle', { timeout: 5000 }).catch(() => {})
}

async function auditPage(page, expectedViewport) {
  const result = await page.evaluate(({ width, height }) => {
    const visible = (element) => {
      const style = window.getComputedStyle(element)
      const rect = element.getBoundingClientRect()
      return style.visibility !== 'hidden' && style.display !== 'none' && rect.width > 0 && rect.height > 0
    }
    const labelText = (element) => {
      const explicit = element.getAttribute('aria-label') || element.getAttribute('title') || element.getAttribute('placeholder')
      const labelledBy = element.getAttribute('aria-labelledby')
      const referenced = labelledBy
        ? labelledBy.split(/\s+/).map((id) => document.getElementById(id)?.textContent || '').join(' ')
        : ''
      const wrapped = element.closest('label')?.textContent || ''
      const byFor = element.id ? document.querySelector(`label[for="${CSS.escape(element.id)}"]`)?.textContent || '' : ''
      return [element.textContent, explicit, referenced, wrapped, byFor, element.getAttribute('alt')]
        .map((value) => String(value || '').trim()).find(Boolean) || ''
    }
    const interactives = [...document.querySelectorAll('button, a[href], input, select, textarea, [role="button"]')]
      .filter(visible)
    const unnamed = interactives.filter((element) => !labelText(element)).map((element) => element.outerHTML.slice(0, 240))
    const missingAlt = [...document.querySelectorAll('img')].filter(visible)
      .filter((image) => !image.hasAttribute('alt')).map((image) => image.outerHTML.slice(0, 240))
    return {
      viewport: { width: window.innerWidth, height: window.innerHeight },
      expectedViewport: { width, height },
      bodyScrollWidth: document.documentElement.scrollWidth,
      bodyClientWidth: document.documentElement.clientWidth,
      horizontalOverflow: document.documentElement.scrollWidth > window.innerWidth + 1,
      visibleInteractiveCount: interactives.length,
      unnamed,
      missingAlt,
      h1Count: document.querySelectorAll('h1').length
    }
  }, expectedViewport)
  expect(result.viewport).toEqual(expectedViewport)
  expect(result.horizontalOverflow, JSON.stringify(result, null, 2)).toBeFalsy()
  expect(result.unnamed, JSON.stringify(result, null, 2)).toEqual([])
  expect(result.missingAlt, JSON.stringify(result, null, 2)).toEqual([])
  expect(result.h1Count).toBeGreaterThan(0)

  await page.keyboard.press('Tab')
  const focused = await page.evaluate(() => {
    const element = document.activeElement
    return {
      tag: element?.tagName || '',
      text: String(element?.textContent || element?.getAttribute?.('aria-label') || element?.getAttribute?.('title') || '').trim(),
      body: element === document.body
    }
  })
  expect(focused.body, JSON.stringify(focused)).toBeFalsy()
  return { ...result, keyboardFocus: focused }
}

async function auditMobileFit(page, expectedViewport) {
  const result = await page.evaluate(({ width, height }) => ({
    viewport: { width: window.innerWidth, height: window.innerHeight },
    expectedViewport: { width, height },
    bodyScrollWidth: document.documentElement.scrollWidth,
    bodyClientWidth: document.documentElement.clientWidth,
    horizontalOverflow: document.documentElement.scrollWidth > window.innerWidth + 1,
    missingAlt: [...document.querySelectorAll('img')].filter((image) => {
      const rect = image.getBoundingClientRect()
      return rect.width > 0 && rect.height > 0 && !image.hasAttribute('alt')
    }).map((image) => image.outerHTML.slice(0, 240))
  }), expectedViewport)
  expect(result.viewport).toEqual(expectedViewport)
  expect(result.horizontalOverflow, JSON.stringify(result, null, 2)).toBeFalsy()
  expect(result.missingAlt, JSON.stringify(result, null, 2)).toEqual([])
  return result
}

async function loginMini(page, account, kind) {
  await page.goto(`${MINI_BASE_URL}/#/pages/login/${kind}/index`)
  const fields = page.getByRole('textbox')
  await fields.nth(0).fill(account.username)
  await fields.nth(1).fill(account.password)
  await page.getByText('填写', { exact: true }).click()
  await fields.nth(2).fill(account.tenant)
  await page.getByText('我已阅读并同意', { exact: false }).click()
  await expect(page.locator('.agreement__box')).toHaveClass(/agreement__box--checked/)
  const action = kind === 'teacher' ? '进入教师工作台' : '进入学生首页'
  const loginButton = page.locator('.account-button').filter({ hasText: action })
  await expect(loginButton).toBeEnabled()
  await loginButton.click()
  await expect(page).toHaveURL(kind === 'teacher' ? /pages\/teacher\/workbench\/index/ : /pages\/student\/home\/index/, { timeout: 20_000 })
  await expect(page.locator('body')).not.toContainText(/操作过于频繁|登录失败|验证码加载失败/)
  if (kind === 'teacher') await expect(page.getByText('当前身份：GD_MENTOR', { exact: false })).toBeVisible()
}

test.describe.serial('Graduation V8 W14 exact viewport and accessibility evidence', () => {
  let fixture

  test.beforeAll(async () => {
    await fs.mkdir(ARTIFACT_DIR, { recursive: true })
    fixture = await prepareGraduationFixture()
    await prepareGraduationTeacherMobileGoldFixture()
  })

  test('staff PC dashboard is usable at 1920/1440/1280', async ({ browser }) => {
    const evidence = []
    const context = await browser.newContext({ viewport: VIEWPORTS[0], locale: 'zh-CN', timezoneId: 'Asia/Shanghai' })
    const page = await context.newPage()
    await new StaffLoginPage(page, config.staffBaseUrl).login(config.sandboxAdmin)

    for (const viewport of VIEWPORTS) {
      await page.setViewportSize(viewport)
      await page.goto(`${config.staffBaseUrl}/admin/graduation?batchId=${encodeURIComponent(fixture.batchId)}`)
      await expect(page.locator('.gdb-page')).toBeVisible()
      await expect(page.locator('.gdb-work')).toBeVisible()
      await expect(page.locator('.gdb-focus')).toBeVisible()
      await expect(page.locator('.gdb-kpi')).toHaveCount(5)
      await expect(page.locator('.gdb-todos')).toBeVisible()
      await expect(page.locator('body')).not.toContainText(/真实接口不可用|权限上下文加载失败|加载失败/)
      await settle(page)
      const audit = await auditPage(page, viewport)
      const screenshot = path.join(ARTIFACT_DIR, `staff-dashboard-${viewport.width}x${viewport.height}.png`)
      await page.screenshot({ path: screenshot, fullPage: false, animations: 'disabled', caret: 'hide' })
      evidence.push({ surface: 'staff-pc', route: page.url(), screenshot, ...audit })
    }
    await context.close()
    await fs.writeFile(path.join(ARTIFACT_DIR, 'staff-viewport-accessibility.json'), JSON.stringify(evidence, null, 2), 'utf8')
  })

  test('student PC puts the eight-step workbench before low-frequency extensions at 1920/1440/1280', async ({ browser }) => {
    const evidence = []
    const context = await browser.newContext({ viewport: VIEWPORTS[0], locale: 'zh-CN', timezoneId: 'Asia/Shanghai' })
    const page = await context.newPage()
    await new StudentLoginPage(page, config.studentBaseUrl).login(config.student)

    for (const viewport of VIEWPORTS) {
      await page.setViewportSize(viewport)
      await page.goto(`${config.studentBaseUrl}/graduation`)
      await expect(page.locator('.gd-workbench')).toBeVisible()
      await expect(page.getByRole('heading', { name: '按步骤完成我的毕业设计' })).toBeVisible()
      await expect(page.locator('.gd-step')).toHaveCount(8)
      await expect(page.getByText(fixture.topicTitle, { exact: true }).first()).toBeVisible()
      await expect(page.locator('body')).not.toContainText(/真实接口不可用|登录已失效|加载失败/)
      const order = await page.evaluate(() => {
        const workbench = document.querySelector('.gd-workbench')
        const extension = document.querySelector('.gd-extension, [data-graduation-extension]')
        if (!workbench || !extension) return { workbench: !!workbench, extension: !!extension, workbenchBeforeExtension: true }
        return { workbench: true, extension: true, workbenchBeforeExtension: Boolean(workbench.compareDocumentPosition(extension) & Node.DOCUMENT_POSITION_FOLLOWING) }
      })
      expect(order.workbenchBeforeExtension, JSON.stringify(order)).toBeTruthy()
      await settle(page)
      const audit = await auditPage(page, viewport)
      const screenshot = path.join(ARTIFACT_DIR, `student-pc-workbench-${viewport.width}x${viewport.height}.png`)
      await page.screenshot({ path: screenshot, fullPage: false, animations: 'disabled', caret: 'hide' })
      evidence.push({ surface: 'student-pc', route: page.url(), screenshot, order, ...audit })
    }
    await context.close()
    await fs.writeFile(path.join(ARTIFACT_DIR, 'student-pc-viewport-accessibility.json'), JSON.stringify(evidence, null, 2), 'utf8')
  })

  test('teacher miniapp keeps the focused graduation queue and taskbook usable at 390/375', async ({ browser }) => {
    const evidence = []
    const context = await browser.newContext({ viewport: MOBILE_VIEWPORTS[0], locale: 'zh-CN', timezoneId: 'Asia/Shanghai' })
    const page = await context.newPage()
    await loginMini(page, u8TeacherAccount, 'teacher')

    for (const viewport of MOBILE_VIEWPORTS) {
      await page.setViewportSize(viewport)
      await page.goto(`${MINI_BASE_URL}/#/pages/teacher/workbench/index`)
      await expect(page.getByText('当前身份：GD_MENTOR', { exact: false })).toBeVisible()
      await expect(page.getByText('批阅开题', { exact: true })).toBeVisible()
      await expect(page.getByText('任务书', { exact: true }).first()).toBeVisible()
      await expect(page.locator('body')).not.toContainText(/真实接口不可用|加载失败|网络不稳定，开发演示数据/)
      await settle(page)
      const workbenchAudit = await auditMobileFit(page, viewport)
      const workbenchShot = path.join(ARTIFACT_DIR, `teacher-mini-workbench-${viewport.width}x${viewport.height}.png`)
      await page.screenshot({ path: workbenchShot, fullPage: false, animations: 'disabled', caret: 'hide' })

      await page.getByText('任务书', { exact: true }).first().click()
      await expect(page).toHaveURL(/pages\/teacher\/graduation-taskbook\/index/)
      await expect(page.getByText('毕设任务书', { exact: true })).toBeVisible()
      await expect(page.getByText(/任务书列表/).first()).toBeVisible()
      await expect(page.locator('body')).not.toContainText(/真实接口不可用|加载失败|网络不稳定，开发演示数据/)
      await settle(page)
      const taskbookAudit = await auditMobileFit(page, viewport)
      const taskbookShot = path.join(ARTIFACT_DIR, `teacher-mini-taskbook-${viewport.width}x${viewport.height}.png`)
      await page.screenshot({ path: taskbookShot, fullPage: false, animations: 'disabled', caret: 'hide' })
      evidence.push({ surface: 'teacher-mini', viewport, workbenchShot, taskbookShot, workbenchAudit, taskbookAudit })
    }
    await context.close()
    await fs.writeFile(path.join(ARTIFACT_DIR, 'teacher-mini-viewport-accessibility.json'), JSON.stringify(evidence, null, 2), 'utf8')
  })

  test('student miniapp shows human material states and a truthful retryable topic empty state at 390/375', async ({ browser }) => {
    const evidence = []
    const context = await browser.newContext({ viewport: MOBILE_VIEWPORTS[0], locale: 'zh-CN', timezoneId: 'Asia/Shanghai' })
    const page = await context.newPage()
    await loginMini(page, config.student, 'student')

    for (const viewport of MOBILE_VIEWPORTS) {
      await page.setViewportSize(viewport)
      await page.goto(`${MINI_BASE_URL}/#/pages/student/graduation/index`)
      await expect(page.getByText('材料库', { exact: true })).toBeVisible()
      await expect(page.getByText('尚未上传版本', { exact: false }).first()).toBeVisible()
      await expect(page.locator('body')).not.toContainText(/TOPIC_ATTACHMENT|NOT_SUBMITTED|真实接口不可用|登录已失效/)
      await settle(page)
      const overviewAudit = await auditMobileFit(page, viewport)
      const overviewShot = path.join(ARTIFACT_DIR, `student-mini-overview-${viewport.width}x${viewport.height}.png`)
      await page.screenshot({ path: overviewShot, fullPage: false, animations: 'disabled', caret: 'hide' })

      await page.goto(`${MINI_BASE_URL}/#/pages/student/graduation/topics/index`)
      const changeButton = page.getByText('申请更换课题', { exact: true }).last()
      await expect(changeButton).toBeVisible()
      await changeButton.click()
      await expect(page.getByText('当前没有其他可更换题目', { exact: true })).toBeVisible()
      await expect(page.getByText('清空搜索并刷新', { exact: true })).toBeVisible()
      const topicAudit = await auditMobileFit(page, viewport)
      const topicShot = path.join(ARTIFACT_DIR, `student-mini-topics-${viewport.width}x${viewport.height}.png`)
      await page.screenshot({ path: topicShot, fullPage: false, animations: 'disabled', caret: 'hide' })
      evidence.push({ surface: 'student-mini', viewport, overviewShot, topicShot, overviewAudit, topicAudit })
    }
    await context.close()
    await fs.writeFile(path.join(ARTIFACT_DIR, 'student-mini-viewport-accessibility.json'), JSON.stringify(evidence, null, 2), 'utf8')
  })
})