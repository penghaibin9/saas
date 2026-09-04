import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { prepareGraduationFixture } from '../lib/api-fixture.mjs'
import {
  dismissGraduationGuide,
  ensureFinalPending,
  expectGraduationBusinessSuccess,
  expectRenderedPdfCanvas
} from '../lib/graduation-scenario-fixture.mjs'
import { StaffLoginPage } from '../pages/login.page.mjs'

const MINI_BASE = process.env.E2E_MINIAPP_BASE_URL || 'http://127.0.0.1:5188'
const TEACHER_BATCH_KEY = 'gx_gd_teacher_batch_v1'

async function loginTeacherMini(page) {
  await page.goto(`${MINI_BASE}/#/pages/login/teacher/index`)
  const fields = page.getByRole('textbox')
  await fields.nth(0).fill(config.mentor.username)
  await fields.nth(1).fill(config.mentor.password)
  await page.getByText('填写', { exact: true }).click()
  await fields.nth(2).fill(config.mentor.tenant)
  await page.getByText('我已阅读并同意学校提供的', { exact: false }).click()
  await page.getByText('进入教师工作台', { exact: true }).click()
  await expect(page).toHaveURL(/pages\/teacher\/workbench\/index/, { timeout: 15_000 })
}

async function setTeacherBatch(page, fixture) {
  await page.evaluate(({ key, batch }) => {
    window.localStorage.setItem(key, JSON.stringify(batch))
  }, {
    key: TEACHER_BATCH_KEY,
    batch: { id: String(fixture.batchId), name: fixture.batchName || '', status: 'RUNNING' }
  })
}

test.describe.serial('V6 · one real thesis across student PC, teacher PC and teacher miniapp', () => {
  let fixture

  test.beforeAll(async () => {
    fixture = await prepareGraduationFixture()
  })

  test('same canonical FileVersion is visible and previewable on all required surfaces', async ({ page }, testInfo) => {
    test.setTimeout(8 * 60_000)
    await ensureFinalPending(page, fixture, {
      suffix: `cross-client-${testInfo.retry || 0}`,
      documentPages: 20
    })

    await new StaffLoginPage(page, config.staffBaseUrl).login(config.mentor)
    await page.goto(`${config.staffBaseUrl}/admin/graduation/finals?batchId=${encodeURIComponent(fixture.batchId)}&tab=PENDING_REVIEW`)
    await dismissGraduationGuide(page)

    const workspace = page.locator('.gd-review-workspace')
    await expect(workspace).toBeVisible()
    await expect(workspace.locator('.gd-review-workspace__queue')).toContainText(fixture.topicTitle)
    await expect.poll(() => new URL(page.url()).searchParams.get('sel'), {
      message: 'teacher PC must expose the exact selected final record in URL'
    }).toMatch(/^\d+$/)

    const recordId = String(new URL(page.url()).searchParams.get('sel'))
    const command = page.getByTestId('review-command-contract')
    await expect(command).toContainText('文件版本')
    await expect(command).toContainText('可以批阅')
    const materialVersion = (await command.locator('div').nth(0).locator('b').innerText()).trim()
    const fileVersionId = (await command.locator('div').nth(1).locator('b').innerText()).trim()
    expect(materialVersion).toMatch(/^\d+$/)
    expect(fileVersionId).toMatch(/^\d+$/)
    await expectRenderedPdfCanvas(page)

    const pcShot = testInfo.outputPath('cross-client-thesis-teacher-pc.png')
    await page.screenshot({ path: pcShot, fullPage: false, animations: 'disabled', caret: 'hide' })
    await testInfo.attach('cross-client-thesis-teacher-pc', { path: pcShot, contentType: 'image/png' })

    await page.setViewportSize({ width: 390, height: 844 })
    await loginTeacherMini(page)
    await setTeacherBatch(page, fixture)
    const taskQuery = new URLSearchParams({
      tab: 'review',
      kind: 'final',
      batchId: String(fixture.batchId),
      gdStudentId: String(fixture.gdStudentId),
      recordId,
      materialVersion,
      fileVersionId
    })
    await page.goto(`${MINI_BASE}/#/pages/teacher/graduation-guide/index?${taskQuery}`)

    // An exact task deep link intentionally bypasses the list page and opens the
    // frozen review record directly. The old “成果待批阅” list-title assertion
    // contradicted the task-lock architecture and made a correct handoff fail.
    await expect(page.getByText(/成果批阅 · 第 1 \/ 1 条/).first()).toBeVisible({ timeout: 20_000 })
    const review = page.locator('.rv__content')
    await expect(review).toBeVisible({ timeout: 20_000 })
    await expect(review).toContainText(fixture.topicTitle)
    await expect(page.locator('.rv__batch')).toContainText(fixture.batchName)
    const versionRow = page.locator('.rv__att').filter({ hasText: `FileVersion ${fileVersionId}` }).first()
    await expect(versionRow, 'teacher miniapp must show the same canonical FileVersion as teacher PC').toBeVisible({ timeout: 20_000 })
    await expect(page.locator('.rv__foot').getByRole('button', { name: '通过' })).toBeEnabled()
    await expect(page.locator('.rv__foot').getByRole('button', { name: '退回' })).toBeEnabled()

    const exactUrl = page.url()
    for (const [key, value] of taskQuery.entries()) {
      expect(decodeURIComponent(exactUrl), `teacher miniapp exact task URL must retain ${key}`).toContain(`${key}=${value}`)
    }

    const ticketPromise = page.waitForResponse((response) =>
      response.request().method() === 'POST'
      && /\/api\/v1\/mobile\/graduation\/material-center\/files\/[^/]+\/ticket$/.test(new URL(response.url()).pathname)
    )
    const previewPromise = page.waitForResponse((response) =>
      response.request().method() === 'GET'
      && /\/api\/v1\/mobile\/graduation\/material-center\/files\/[^/]+\/preview$/.test(new URL(response.url()).pathname)
      && new URL(response.url()).searchParams.has('ticket')
    )
    await versionRow.click()
    const ticketData = await expectGraduationBusinessSuccess(await ticketPromise, '教师小程序签发论文预览票据')
    expect(ticketData?.ticket || ticketData?.url || ticketData?.previewUrl).toBeTruthy()
    const previewResponse = await previewPromise
    expect(previewResponse.ok(), `teacher miniapp PDF preview HTTP ${previewResponse.status()}`).toBeTruthy()
    const previewBytes = await previewResponse.body()
    expect(previewBytes.subarray(0, 5).toString('ascii')).toBe('%PDF-')

    const confirmCurrent = page.getByRole('button', { name: '确认当前版本' })
    if (await confirmCurrent.isVisible().catch(() => false)) {
      const revalidatePromise = page.waitForResponse((response) =>
        response.request().method() === 'GET'
        && /\/api\/v1\/mobile\/teacher\/graduation\/final\/[^/]+$/.test(new URL(response.url()).pathname)
      )
      await confirmCurrent.click()
      const fresh = await expectGraduationBusinessSuccess(await revalidatePromise, '教师小程序预览返回后重验论文版本')
      expect(String(fresh?.materialVersion || '')).toBe(materialVersion)
      expect(String(fresh?.fileVersionId || '')).toBe(fileVersionId)
      await expect(page.locator('.rv__foot').getByRole('button', { name: '通过' })).toBeEnabled()
      await expect(page.locator('.rv__foot').getByRole('button', { name: '退回' })).toBeEnabled()
    }

    await expect(page.locator('body')).not.toContainText(
      /版本已变化|旧版审核已锁定|批次与当前选择不一致|指定的毕业设计待办不在当前批次/
    )

    const miniShot = testInfo.outputPath('cross-client-thesis-teacher-miniapp.png')
    await page.screenshot({ path: miniShot, fullPage: false, animations: 'disabled', caret: 'hide' })
    await testInfo.attach('cross-client-thesis-teacher-miniapp', { path: miniShot, contentType: 'image/png' })

    const evidence = testInfo.outputPath('cross-client-thesis-identity.json')
    await import('node:fs/promises').then(({ writeFile }) => writeFile(evidence, JSON.stringify({
      head: process.env.E2E_EXPECTED_SHA || process.env.GITHUB_SHA || 'local',
      batchId: String(fixture.batchId),
      gdStudentId: String(fixture.gdStudentId),
      recordId,
      materialVersion,
      fileVersionId,
      scenarioFactory: 'graduation-scenario-fixture.ensureFinalPending',
      miniappEntry: 'exact-task-direct-review'
    }, null, 2), 'utf8'))
    await testInfo.attach('cross-client-thesis-identity', { path: evidence, contentType: 'application/json' })
  })
})
