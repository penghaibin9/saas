import { config } from './config.mjs'
import { StaffLoginPage } from '../pages/login.page.mjs'

async function waitForStaffShell(page) {
  await page.locator('.uchip__role').first().waitFor({ state: 'visible', timeout: 20_000 })
}

export async function openGoldenStaffPage(page, path) {
  await new StaffLoginPage(page, config.staffBaseUrl).login(config.sandboxAdmin)

  // browser-login redirects into a fresh document. Wait until that document has completed its
  // browser-refresh and rendered the authenticated shell before starting another navigation;
  // otherwise the next goto can abort the one-time refresh response after the server consumed it.
  await waitForStaffShell(page)

  const targetUrl = new URL(path, config.staffBaseUrl).toString()
  const current = new URL(page.url())
  const target = new URL(targetUrl)
  if (`${current.pathname}${current.search}` !== `${target.pathname}${target.search}`) {
    await page.goto(targetUrl)
    await waitForStaffShell(page)
  }
}
