import { expect } from './observability.mjs'
import { config } from './config.mjs'
import { StaffLoginPage } from '../pages/login.page.mjs'

export function internshipApiPath(response) {
  try { return new URL(response.url()).pathname } catch { return '' }
}

export async function internshipPayloadOf(response) {
  const text = await response.text()
  try { return { text, body: JSON.parse(text) } } catch { return { text, body: null } }
}

export function internshipFormItem(page, label) {
  return page.locator('.app-form-item').filter({ hasText: label }).first()
}

export function internshipCompanyRow(page, companyName) {
  return page.locator('tbody tr').filter({ hasText: companyName }).first()
}

export async function internshipStaffLogin(page) {
  await new StaffLoginPage(page, config.staffBaseUrl).login(config.sandboxAdmin)
}

export async function confirmInternshipPositionStatus(page, positionId, triggerName, confirmName) {
  await page.getByRole('button', { name: triggerName, exact: true }).click()
  const dialog = page.getByRole('dialog')
  await expect(dialog).toBeVisible()
  const responsePromise = page.waitForResponse((response) =>
    internshipApiPath(response) === `/api/v1/internship/positions/${positionId}/status`
      && response.request().method() === 'POST'
  )
  await dialog.getByRole('button', { name: confirmName, exact: true }).click()
  const response = await responsePromise
  const { text, body } = await internshipPayloadOf(response)
  return { response, text, body }
}
