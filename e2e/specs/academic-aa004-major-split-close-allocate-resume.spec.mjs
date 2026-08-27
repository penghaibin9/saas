import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { StaffLoginPage } from '../pages/login.page.mjs'

const here = path.dirname(fileURLToPath(import.meta.url))
const repoRoot = path.resolve(here, '../..')
const statePath = path.join(repoRoot, 'backend/tmp/e2e_academic_aa004_state.local.json')
const outcomePath = path.resolve(here, '../academic-aa004-close-allocate-resume-outcome.json')

function fixture() {
  return JSON.parse(fs.readFileSync(statePath, 'utf8'))
}

async function browserApi(page, token, method, requestPath, body) {
  return page.evaluate(async ({ apiBaseUrl, tokenValue, requestMethod, pathValue, requestBody }) => {
    const response = await fetch(`${apiBaseUrl}${pathValue}`, {
      method: requestMethod,
      headers: {
        Accept: 'application/json',
        Authorization: `Bearer ${tokenValue}`,
        ...(requestBody === undefined ? {} : { 'Content-Type': 'application/json' }),
      },
      body: requestBody === undefined ? undefined : JSON.stringify(requestBody),
    })
    const text = await response.text()
    let json = null
    try { json = JSON.parse(text) } catch { json = { message: text.slice(0, 500) } }
    return { status: response.status, json }
  }, {
    apiBaseUrl: config.apiBaseUrl,
    tokenValue: token,
    requestMethod: method,
    pathValue: requestPath,
    requestBody: body,
  })
}

function expectApiOk(result, label) {
  expect(result.status, `${label}: ${JSON.stringify(result.json)}`).toBe(200)
  expect(result.json?.code, `${label}: ${JSON.stringify(result.json)}`).toBe(0)
  return result.json.data
}

async function clickConfirm(page) {
  const dialog = page.locator('.app-confirm-dialog__mask')
  await expect(dialog).toBeVisible({ timeout: 5000 })
  await dialog.getByRole('button', { name: '确认', exact: true }).click()
}

test('AA-004 resume: close confirm must dismiss before Staff PC can auto-allocate', async ({ browser }, testInfo) => {
  const facts = fixture()
  const context = await browser.newContext()
  const staff = await context.newPage()
  const outcome = {
    productSha: process.env.E2E_EXPECTED_SHA || '',
    scope: 'close-confirm -> dialog-dismiss -> auto-allocate',
    studentSurfacesRerun: false,
  }

  try {
    const login = new StaffLoginPage(staff, config.staffBaseUrl)
    await login.login(config.multiRole)
    await login.switchRole(/教务处管理员|教务管理员|教务老师|ACADEMIC_ADMIN/)
    const staffToken = await login.token()
    expect(staffToken, 'AA-004 focused gate requires Staff PC access token').toBeTruthy()

    // Minimum upstream only: reconstruct an OPEN batch by authenticated API.
    // Student PC/Mini steps that were already GREEN are intentionally not rerun.
    const suffix = `${Date.now()}`.slice(-8)
    const batchName = `AA-004失败点复验-${suffix}`
    const batch = expectApiOk(await browserApi(staff, staffToken, 'POST', '/academic-affairs/major-split/batches', {
      batchName,
      grade: facts.grade,
      maxChoices: 1,
    }), 'create focused split batch')
    const batchId = String(batch?.batchId || '')
    expect(batchId).toMatch(/^\d+$/)
    outcome.batchId = batchId
    outcome.batchName = batchName

    expectApiOk(await browserApi(staff, staffToken, 'POST', `/academic-affairs/major-split/batches/${batchId}/options`, {
      majorId: facts.targetMajorAId,
      capacity: 1,
    }), 'add focused target major')
    expectApiOk(await browserApi(staff, staffToken, 'POST', `/academic-affairs/major-split/batches/${batchId}/open`), 'open focused split batch')

    await staff.goto(`${config.staffBaseUrl}/admin/academic-affairs/major-split`)
    await expect(staff.getByText('专业分流 · 教务处控制台', { exact: true })).toBeVisible({ timeout: 20000 })
    const batchRow = staff.locator('.aams-batch').filter({ hasText: batchName }).first()
    await expect(batchRow).toBeVisible({ timeout: 20000 })
    await batchRow.click()
    await expect(staff.getByRole('button', { name: '截止', exact: true })).toBeVisible({ timeout: 10000 })

    const closeResponsePromise = staff.waitForResponse((response) =>
      response.request().method() === 'POST' && response.url().endsWith(`/api/v1/academic-affairs/major-split/batches/${batchId}/close`),
      { timeout: 20000 },
    )
    await staff.getByRole('button', { name: '截止', exact: true }).click()
    await clickConfirm(staff)
    const closeResponse = await closeResponsePromise
    const closePayload = await closeResponse.json()
    expect(closeResponse.ok(), JSON.stringify(closePayload)).toBeTruthy()
    expect(closePayload?.code, JSON.stringify(closePayload)).toBe(0)

    // The exact product bug fixed at 7a761d2d: successful confirm must remove the mask.
    await expect(staff.locator('.app-confirm-dialog__mask')).toHaveCount(0, { timeout: 5000 })
    outcome.closeDialogDismissed = true

    // Immediate downstream only: prove the next real Staff PC action is now operable.
    const allocateButton = staff.getByRole('button', { name: '自动分配', exact: true })
    await expect(allocateButton).toBeVisible({ timeout: 20000 })
    await allocateButton.click()
    await expect(staff.locator('.app-confirm-dialog__mask')).toBeVisible({ timeout: 5000 })

    const allocateResponsePromise = staff.waitForResponse((response) =>
      response.request().method() === 'POST' && response.url().includes(`/api/v1/academic-affairs/major-split/batches/${batchId}/allocate`),
      { timeout: 20000 },
    )
    await clickConfirm(staff)
    const allocateResponse = await allocateResponsePromise
    const allocatePayload = await allocateResponse.json()
    expect(allocateResponse.ok(), JSON.stringify(allocatePayload)).toBeTruthy()
    expect(allocatePayload?.code, JSON.stringify(allocatePayload)).toBe(0)
    expect(allocatePayload?.data?.allocated).toBe(0)
    expect(allocatePayload?.data?.unallocated).toBe(0)
    await expect(staff.locator('.app-confirm-dialog__mask')).toHaveCount(0, { timeout: 5000 })
    await expect(staff.locator('.aams-batch').filter({ hasText: batchName }).first()).toContainText('已分配', { timeout: 20000 })
    outcome.allocateDialogDismissed = true
    outcome.autoAllocateOperable = true

    fs.writeFileSync(outcomePath, JSON.stringify(outcome, null, 2))
    await testInfo.attach('aa004-close-allocate-resume-outcome', {
      body: JSON.stringify(outcome, null, 2),
      contentType: 'application/json',
    })
  } finally {
    await context.close()
  }
})
