import { config } from './config.mjs'
import { StaffLoginPage } from '../pages/login.page.mjs'

async function waitForStaffShell(page) {
  await page.locator('.uchip__role').first().waitFor({ state: 'visible', timeout: 20_000 })
}

function waitForBrowserRefresh(page) {
  return page.waitForResponse(
    (response) => response.url().includes('/api/v1/auth/browser-refresh') &&
      response.request().method() === 'POST' &&
      response.status() === 200,
    { timeout: 20_000 }
  )
}

async function gotoAuthenticatedDocument(page, targetUrl) {
  const refresh = waitForBrowserRefresh(page)
  await page.goto(targetUrl)
  await refresh
  await waitForStaffShell(page)
}

export async function openGoldenStaffPage(page, path) {
  const loginRefresh = waitForBrowserRefresh(page)
  await new StaffLoginPage(page, config.staffBaseUrl).login(config.sandboxAdmin)
  await loginRefresh
  await waitForStaffShell(page)

  const targetUrl = new URL(path, config.staffBaseUrl).toString()
  const current = new URL(page.url())
  const target = new URL(targetUrl)
  if (`${current.pathname}${current.search}` !== `${target.pathname}${target.search}`) {
    await gotoAuthenticatedDocument(page, targetUrl)
  }
}
