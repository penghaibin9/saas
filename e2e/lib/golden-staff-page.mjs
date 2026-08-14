import { config } from './config.mjs'
import { StaffLoginPage } from '../pages/login.page.mjs'

export async function openGoldenStaffPage(page, path) {
  await new StaffLoginPage(page, config.staffBaseUrl).login(config.sandboxAdmin)
  await page.goto(`${config.staffBaseUrl}${path}`)
}
