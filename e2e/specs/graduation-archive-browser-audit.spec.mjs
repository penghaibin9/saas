import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { prepareGraduationFixture } from '../lib/api-fixture.mjs'
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

function guidanceUrl(fixture) {
  const url = new URL(`${config.staffBaseUrl}/admin/graduation/process`)
  url.searchParams.set('batchId', fixture.batchId)
  url.searchParams.set('studentId', fixture.gdStudentId)
  url.searchParams.set('panel', 'guidance')
  url.searchParams.set('source', 'E2E-AUDIT-20260824-GD018')
  return url.toString()
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

async function loginArchiveAdmin(page, fixture) {
  await new StaffLoginPage(page, config.staffBaseUrl).login(config.sandboxAdmin)
  await page.goto(archiveUrl(fixture))
  await dismissGuide(page)
  await expect(page.getByRole('heading', { name: '问题预警 · 毕设归档 · 毕设统计', exact: true })).toBeVisible()
  await expect.soft(page.getByText('毕设材料归档', { exact: true }).first()).toBeVisible()
  await expect(page.getByRole('button', { name: '毕设归档', exact: true })).toHaveClass(/is-active/)
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

  test('真实指导补齐 → 批量生成提交 → 旧预览被并发指导变更拒绝 → 重新预览冻结 → 导出台账', async ({ page, browser }) => {
    // Required V2 GUIDANCE_RECORD comes from a real mentor operation, never an API seed.
    await addGuidance(page, fixture, 'baseline-guidance')
    await loginArchiveAdmin(page, fixture)

    const [generatePreviewResponse] = await Promise.all([
      page.waitForResponse((r) => isArchivePath(r, 'batch-generate/preview')),
      page.getByRole('button', { name: '批量生成提交', exact: true }).click(),
    ])
    expect(generatePreviewResponse.ok(), `batch-generate preview HTTP ${generatePreviewResponse.status()}`).toBeTruthy()
    const generatePreview = await readJson(generatePreviewResponse)
    expect(generatePreview.code, JSON.stringify(generatePreview)).toBe(0)
    expect(Number(generatePreview.data?.candidateCount || 0)).toBeGreaterThanOrEqual(1)
    expect(Number(generatePreview.data?.executableCount || 0), JSON.stringify(generatePreview.data)).toBeGreaterThanOrEqual(1)
    expect(String(generatePreview.data?.previewToken || '')).toBeTruthy()
    await expect(page.getByRole('dialog')).toContainText(/预计成功\s*1|预计成功/)

    const [generateResponse] = await Promise.all([
      page.waitForResponse((r) => isArchivePath(r, 'batch-generate')),
      page.getByRole('button', { name: '确认生成提交', exact: true }).click(),
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
    await expect(page.getByRole('dialog')).toContainText(/预计备案/)

    const mentorContext = await browser.newContext()
    const mentorPage = await mentorContext.newPage()
    try {
      await addGuidance(mentorPage, fixture, 'after-file-preview')
    } finally {
      await mentorContext.close()
    }

    const [staleExecuteResponse] = await Promise.all([
      page.waitForResponse((r) => isArchivePath(r, 'batch-file')),
      page.getByRole('button', { name: '确认核验备案', exact: true }).click(),
    ])
    const staleExecute = await readJson(staleExecuteResponse)
    expect(
      !staleExecuteResponse.ok() || staleExecute.code !== 0,
      `stale preview unexpectedly filed: HTTP ${staleExecuteResponse.status()} ${JSON.stringify(staleExecute)}`,
    ).toBeTruthy()
    expect(JSON.stringify(staleExecute)).toMatch(/预览|变化|DATA_CONFLICT|snapshot|凭证/i)
    await expect(page.getByRole('dialog')).toBeVisible()
    await page.getByRole('button', { name: '取消', exact: true }).click()

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
      page.getByRole('button', { name: '确认核验备案', exact: true }).click(),
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
