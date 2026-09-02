import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { loginApi, prepareGraduationFixture } from '../lib/api-fixture.mjs'
import { StaffLoginPage } from '../pages/login.page.mjs'

async function dismissGuide(page) {
  for (const mask of [page.locator('.app-step-guide__mask'), page.locator('.tour-mask')]) {
    if (await mask.isVisible().catch(() => false)) {
      const skip = page.getByRole('button', { name: /跳过引导|跳过/ }).first()
      if (await skip.isVisible().catch(() => false)) await skip.click()
      await mask.waitFor({ state: 'hidden', timeout: 3000 }).catch(() => {})
    }
  }
}

function archiveUrl(fixture) {
  const url = new URL(`${config.staffBaseUrl}/admin/graduation/risk-archive`)
  url.searchParams.set('batchId', fixture.batchId)
  url.searchParams.set('panel', 'archive')
  url.searchParams.set('source', 'E2E-AUDIT-20260824-GD018')
  return url.toString()
}

function riskUrl(fixture) {
  const url = new URL(`${config.staffBaseUrl}/admin/graduation/risk-archive`)
  url.searchParams.set('batchId', fixture.batchId)
  url.searchParams.set('panel', 'risk')
  url.searchParams.set('source', 'E2E-AUDIT-20260824-GD018')
  return url.toString()
}

function guidanceUrl(fixture) {
  const url = new URL(`${config.staffBaseUrl}/admin/graduation/process`)
  url.searchParams.set('batchId', fixture.batchId)
  url.searchParams.set('studentId', fixture.gdStudentId)
  url.searchParams.set('panel', 'guidance')
  url.searchParams.set('source', 'E2E-AUDIT-20260824-GD018')
  return url.toString()
}

function confirmDialog(page) {
  return page.locator('.app-confirm-dialog').first()
}

async function addGuidance(page, fixture, marker) {
  await new StaffLoginPage(page, config.staffBaseUrl).login(config.mentor)
  await page.goto(guidanceUrl(fixture))
  await dismissGuide(page)
  await expect(page.getByRole('heading', { name: '过程指导', exact: true })).toBeVisible()
  await expect(page.locator('.gp-context')).toContainText(fixture.studentNo)
  await page.getByRole('button', { name: '＋ 新增指导记录', exact: true }).click()
  const form = page.locator('form.ie-form')
  const content = `E2E-AUDIT-20260824 GD-018 ${marker}：归档冻结前复核材料、版本和最终证据一致性。`
  await form.getByPlaceholder('详细记录本次指导内容、建议…').fill(content)
  await form.locator('label').filter({ hasText: '发现的问题' }).locator('textarea').fill(
    `E2E-AUDIT-20260824 ${marker}：确认 FileVersion 与归档清单一致。`
  )
  const [response] = await Promise.all([
    page.waitForResponse((r) => r.request().method() === 'POST' && new URL(r.url()).pathname.endsWith(`/graduation/gd-guidances/${fixture.gdStudentId}`)),
    page.getByRole('button', { name: '保存', exact: true }).click(),
  ])
  expect(response.ok(), `guidance ${marker} HTTP ${response.status()}`).toBeTruthy()
  const body = await response.json()
  expect(body.code, JSON.stringify(body)).toBe(0)
  return content
}

async function closeInactiveHistoricalRisks(page, fixture) {
  const admin = await loginApi(config.sandboxAdmin)
  const before = await admin.get('/graduation/gd-risks', {
    gdStudentId: fixture.gdStudentId, batchId: fixture.batchId, page: 1, pageSize: 100,
  })
  const beforeRows = Array.isArray(before?.items) ? before.items : []
  const closable = beforeRows.filter((row) =>
    ['OPEN', 'PROCESSING'].includes(String(row.status || '').toUpperCase())
    && row.conditionActive === false
    && String(row.riskCode || '') !== 'GD-R12'
  )

  await new StaffLoginPage(page, config.staffBaseUrl).login(config.sandboxAdmin)
  await page.goto(riskUrl(fixture))
  await dismissGuide(page)
  await expect(page.getByRole('heading', { name: '问题预警 · 毕设归档 · 毕设统计', exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: '问题预警', exact: true })).toHaveClass(/is-active/)

  for (const risk of closable) {
    const row = page.locator('.rk-row').filter({ hasText: String(risk.riskName || '') }).filter({ hasText: fixture.studentNo }).first()
    await expect(row, `inactive risk row ${risk.riskCode}/${risk.id}`).toBeVisible()
    await row.click()
    const pane = page.locator('.rk-pane')
    await expect(pane).toContainText(String(risk.riskName || risk.riskCode || risk.id))
    if (risk.nextActionHint) await expect(pane).toContainText(String(risk.nextActionHint))
    const close = pane.getByRole('button', { name: '关闭风险', exact: true })
    await expect(close, `close button for ${risk.riskCode}/${risk.id}`).toBeVisible()
    await close.click()
    const dialog = page.getByRole('dialog').filter({ hasText: '关闭风险' }).first()
    await expect(dialog).toBeVisible()
    await dialog.locator('textarea').fill('E2E-AUDIT-20260824 GD-018：扫描条件已消失，归档前通过真实浏览器完成风险闭环。')
    const [response] = await Promise.all([
      page.waitForResponse((r) => r.request().method() === 'POST' && new URL(r.url()).pathname.endsWith(`/graduation/gd-risks/${risk.id}/close`)),
      dialog.getByRole('button', { name: '确认关闭', exact: true }).click(),
    ])
    expect(response.ok(), `close inactive risk ${risk.riskCode}/${risk.id} HTTP ${response.status()}`).toBeTruthy()
    const body = await response.json()
    expect(body.code, JSON.stringify(body)).toBe(0)
    await expect(dialog).toBeHidden()
  }

  // API is read-only discovery/verification only. Every state mutation above went through
  // the real PC risk workspace and its close dialog.
  const after = await admin.get('/graduation/gd-risks', {
    gdStudentId: fixture.gdStudentId, batchId: fixture.batchId, page: 1, pageSize: 100,
  })
  const afterRows = Array.isArray(after?.items) ? after.items : []
  const blockers = afterRows.filter((row) =>
    ['OPEN', 'PROCESSING'].includes(String(row.status || '').toUpperCase())
    && String(row.riskCode || '') !== 'GD-R12'
  )
  expect(blockers, `archive prerequisite risks still open: ${JSON.stringify(blockers).slice(0, 2500)}`).toHaveLength(0)
}

async function openArchivePanel(page, fixture) {
  await page.goto(archiveUrl(fixture))
  await dismissGuide(page)
  await expect(page.getByRole('heading', { name: '问题预警 · 毕设归档 · 毕设统计', exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: '毕设归档', exact: true })).toHaveClass(/is-active/)
}

async function archiveMaterialReadiness(fixture) {
  const admin = await loginApi(config.sandboxAdmin)
  const data = await admin.get(`/graduation/material-center/students/${fixture.gdStudentId}/library`, {
    includeHistory: true,
  })
  const required = (Array.isArray(data?.items) ? data.items : []).filter((item) => item.required && item.archiveRequired)
  return required.map((item) => ({
    code: item.materialCode,
    initialized: item.initialized,
    businessStatus: item.businessStatus,
    reviewStatus: item.reviewStatus,
    archiveStatus: item.archiveStatus,
    currentVersionId: item.currentVersionId,
    versionStatus: item.currentVersion?.versionStatus || '',
    fileStatus: item.currentVersion?.status || '',
    scanStatus: item.currentVersion?.scanStatus || '',
    readyForBusiness: item.currentVersion?.readyForBusiness ?? false,
  }))
}

function isArchivePath(response, suffix) {
  return response.request().method() === 'POST' && new URL(response.url()).pathname.endsWith(`/graduation/gd-archives/${suffix}`)
}

async function readJson(response) {
  const text = await response.text()
  try { return JSON.parse(text) } catch { return { raw: text } }
}

test.describe.configure({ retries: 0 })

test.describe.serial('GD-018 归档 Browser First · preview/freeze/FileVersion/stale token/export', () => {
  let fixture

  test.beforeAll(async () => {
    fixture = await prepareGraduationFixture()
  })

  test('真实指导补齐 → 关闭已消失风险 → 批量生成提交 → 旧预览被并发指导变更拒绝 → 重新预览冻结 → 导出台账', async ({ page, browser }) => {
    // Required V2 GUIDANCE_RECORD comes from a real mentor operation, never an API seed.
    await addGuidance(page, fixture, 'baseline-guidance')
    // Historical risks stay auditable instead of auto-closing. Close only conditions the
    // real UI explicitly says have disappeared; active prerequisite risks remain blockers.
    await closeInactiveHistoricalRisks(page, fixture)
    await openArchivePanel(page, fixture)

    const readiness = await archiveMaterialReadiness(fixture)
    const [generatePreviewResponse] = await Promise.all([
      page.waitForResponse((r) => isArchivePath(r, 'batch-generate/preview')),
      page.getByRole('button', { name: '批量生成提交', exact: true }).click(),
    ])
    expect(generatePreviewResponse.ok(), `batch-generate preview HTTP ${generatePreviewResponse.status()}`).toBeTruthy()
    const generatePreview = await readJson(generatePreviewResponse)
    expect(generatePreview.code, JSON.stringify(generatePreview)).toBe(0)
    expect(Number(generatePreview.data?.candidateCount || 0)).toBeGreaterThanOrEqual(1)
    expect(
      Number(generatePreview.data?.executableCount || 0),
      `archive preview=${JSON.stringify(generatePreview.data)} materialReadiness=${JSON.stringify(readiness)}`,
    ).toBeGreaterThanOrEqual(1)
    expect(String(generatePreview.data?.previewToken || '')).toBeTruthy()
    await expect(confirmDialog(page)).toContainText(/预计成功\s*1|预计成功/)

    const [generateResponse] = await Promise.all([
      page.waitForResponse((r) => isArchivePath(r, 'batch-generate')),
      confirmDialog(page).getByRole('button', { name: '确认生成提交', exact: true }).click(),
    ])
    expect(generateResponse.ok(), `batch-generate HTTP ${generateResponse.status()}`).toBeTruthy()
    const generated = await readJson(generateResponse)
    expect(generated.code, JSON.stringify(generated)).toBe(0)
    expect(Number(generated.data?.submitted || 0)).toBeGreaterThanOrEqual(1)
    await expect(page.locator('.rk-row').filter({ hasText: fixture.studentNo }).first()).toContainText(/已提交/)

    // Keep the admin confirmation dialog and its exact preview token alive while a second real
    // browser session changes a signed business source (guidance content).
    const [filePreviewResponse] = await Promise.all([
      page.waitForResponse((r) => isArchivePath(r, 'batch-file/preview')),
      page.getByRole('button', { name: '一键核验备案', exact: true }).click(),
    ])
    expect(filePreviewResponse.ok(), `batch-file preview HTTP ${filePreviewResponse.status()}`).toBeTruthy()
    const stalePreview = await readJson(filePreviewResponse)
    expect(stalePreview.code, JSON.stringify(stalePreview)).toBe(0)
    expect(Number(stalePreview.data?.executableCount || 0), JSON.stringify(stalePreview.data)).toBeGreaterThanOrEqual(1)
    const staleToken = String(stalePreview.data?.previewToken || '')
    expect(staleToken).toBeTruthy()
    await expect(confirmDialog(page)).toContainText(/预计备案/)

    const mentorContext = await browser.newContext()
    const mentorPage = await mentorContext.newPage()
    try {
      await addGuidance(mentorPage, fixture, 'after-file-preview')
    } finally {
      await mentorContext.close()
    }

    const [staleExecuteResponse] = await Promise.all([
      page.waitForResponse((r) => isArchivePath(r, 'batch-file')),
      confirmDialog(page).getByRole('button', { name: '确认核验备案', exact: true }).click(),
    ])
    const staleExecute = await readJson(staleExecuteResponse)
    expect(
      !staleExecuteResponse.ok() || staleExecute.code !== 0,
      `stale preview unexpectedly filed: HTTP ${staleExecuteResponse.status()} ${JSON.stringify(staleExecute)}`,
    ).toBeTruthy()
    expect(JSON.stringify(staleExecute)).toMatch(/预览|变化|DATA_CONFLICT|snapshot|凭证/i)
    await expect(confirmDialog(page)).toBeVisible()
    await confirmDialog(page).getByRole('button', { name: '取消', exact: true }).click()

    const [freshPreviewResponse] = await Promise.all([
      page.waitForResponse((r) => isArchivePath(r, 'batch-file/preview')),
      page.getByRole('button', { name: '一键核验备案', exact: true }).click(),
    ])
    expect(freshPreviewResponse.ok(), `fresh batch-file preview HTTP ${freshPreviewResponse.status()}`).toBeTruthy()
    const freshPreview = await readJson(freshPreviewResponse)
    expect(freshPreview.code, JSON.stringify(freshPreview)).toBe(0)
    expect(Number(freshPreview.data?.executableCount || 0), JSON.stringify(freshPreview.data)).toBeGreaterThanOrEqual(1)
    expect(String(freshPreview.data?.previewToken || '')).toBeTruthy()
    expect(String(freshPreview.data?.previewToken || '')).not.toBe(staleToken)

    const [fileResponse] = await Promise.all([
      page.waitForResponse((r) => isArchivePath(r, 'batch-file')),
      confirmDialog(page).getByRole('button', { name: '确认核验备案', exact: true }).click(),
    ])
    expect(fileResponse.ok(), `fresh batch-file HTTP ${fileResponse.status()}`).toBeTruthy()
    const filed = await readJson(fileResponse)
    expect(filed.code, JSON.stringify(filed)).toBe(0)
    expect(Number(filed.data?.filed || 0), JSON.stringify(filed.data)).toBeGreaterThanOrEqual(1)
    expect(Number(filed.data?.failed || 0), JSON.stringify(filed.data)).toBe(0)

    await expect(page.locator('.rk-row').filter({ hasText: fixture.studentNo }).first()).toContainText(/已备案/)
    await expect(page.locator('.rk-pane')).toContainText(/已正式归档备案，记录只读/)

    const [exportResponse] = await Promise.all([
      page.waitForResponse((r) => isArchivePath(r, 'export')),
      page.getByRole('button', { name: /导出台账/ }).click(),
    ])
    expect(exportResponse.ok(), `archive xlsx export HTTP ${exportResponse.status()}`).toBeTruthy()
    const exported = await readJson(exportResponse)
    expect(exported.code, JSON.stringify(exported)).toBe(0)
    expect(String(exported.data?.filename || '')).toMatch(/\.xlsx$/i)

    await page.reload()
    await dismissGuide(page)
    await expect(page.locator('.rk-row').filter({ hasText: fixture.studentNo }).first()).toContainText(/已备案/)
  })
})
