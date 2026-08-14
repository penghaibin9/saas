import { config } from './config.mjs'
import { StaffLoginPage } from '../pages/login.page.mjs'

async function waitForStaffShell(page) {
  await page.locator('.uchip__role').first().waitFor({ state: 'visible', timeout: 20_000 })
}

function waitForBrowserRefresh(page, timeout = 20_000) {
  return page.waitForResponse(
    (response) => response.url().includes('/api/v1/auth/browser-refresh') &&
      response.request().method() === 'POST' &&
      response.status() === 200,
    { timeout }
  )
}

function waitForOptionalBrowserRefresh(page) {
  return waitForBrowserRefresh(page, 5_000)
    .then(() => true)
    .catch((error) => {
      if (String(error?.message || error).includes('Timeout')) return false
      throw error
    })
}

async function dismissPageOperationGuide(page) {
  const guide = page.getByRole('dialog', { name: '页面操作引导' })
  if (!(await guide.isVisible({ timeout: 1_000 }).catch(() => false))) return

  const skip = guide.getByRole('button', { name: '跳过引导' })
  if (await skip.isVisible({ timeout: 1_000 }).catch(() => false)) {
    await skip.click()
  }
}

async function gotoAuthenticatedDocument(page, targetUrl) {
  const refresh = waitForBrowserRefresh(page)
  await page.goto(targetUrl)
  await refresh
  await waitForStaffShell(page)
  await dismissPageOperationGuide(page)
}

export async function openGoldenStaffPage(page, path) {
  // Browser login itself is authoritative through /browser-login. Some first-entry workbench loads
  // render directly from the in-memory access token and do not issue /browser-refresh before the
  // Golden helper navigates to the target document. Treat the login refresh as an optional
  // observation, but keep the target document refresh strict because a full page load must rebuild
  // auth from the HttpOnly browser session.
  const optionalLoginRefresh = waitForOptionalBrowserRefresh(page)
  await new StaffLoginPage(page, config.staffBaseUrl).login(config.sandboxAdmin)
  await optionalLoginRefresh
  await waitForStaffShell(page)
  await dismissPageOperationGuide(page)

  const targetUrl = new URL(path, config.staffBaseUrl).toString()
  const current = new URL(page.url())
  const target = new URL(targetUrl)
  if (`${current.pathname}${current.search}` !== `${target.pathname}${target.search}`) {
    await gotoAuthenticatedDocument(page, targetUrl)
  }
}
