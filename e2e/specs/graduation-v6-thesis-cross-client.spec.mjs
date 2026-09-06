import { createHash } from 'node:crypto'
import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { loginApi, prepareGraduationFixture } from '../lib/api-fixture.mjs'
import {
  dismissGraduationGuide,
  ensureFinalPending,
  expectGraduationBusinessSuccess,
  expectRenderedPdfCanvas
} from '../lib/graduation-scenario-fixture.mjs'
import { StaffLoginPage } from '../pages/login.page.mjs'

const MINI_BASE = process.env.E2E_MINIAPP_BASE_URL || 'http://127.0.0.1:5188'

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

// uni-app H5 may render uni-button rather than a native HTML button. Assert
// its visible label AND disabled signals; toBeEnabled alone ignores the
// disabled attribute on custom elements and would give a false positive.
async function expectMiniControlState(control, label, disabled = false) {
  await expect(control, `unique ${label} control`).toHaveCount(1)
  await expect(control).toBeVisible()
  await expect(control).toHaveText(label)
  await expect.poll(() => control.evaluate(node => {
    const blocked = element => element.disabled === true
      || element.hasAttribute('disabled')
      || element.getAttribute('aria-disabled') === 'true'
      || element.classList.contains('uni-button-disabled')
    return blocked(node) || Array.from(node.querySelectorAll('button, uni-button')).some(blocked)
  }), { message: `${label} must expose its real ${disabled ? 'locked' : 'enabled'} state` }).toBe(disabled)
}

function assertLibraryIdentity(library, fixture, identity) {
  expect(String(library?.gdStudentId || '')).toBe(String(fixture.gdStudentId))
  expect(String(library?.studentNo || '')).toBe(String(fixture.studentNo))
  expect(String(library?.batchId || '')).toBe(String(fixture.batchId))
  const materials = (library?.items || []).filter((row) => String(row.materialId || '') === identity.materialId)
  expect(materials, 'the exact review material must belong to this authorised student library').toHaveLength(1)
  const material = materials[0]
  expect(String(material.currentVersionId || '')).toBe(identity.fileVersionId)
  expect(String(material.version ?? '')).toBe(identity.materialVersion)
  expect(material.currentVersion?.readyForBusiness).toBe(true)
  return material.currentVersion
}

function assertMobileIdentity(mobileDetail, fixture, identity, library) {
  const current = assertLibraryIdentity(library, fixture, identity)
  expect(String(mobileDetail?.id || '')).toBe(identity.recordId)
  expect(String(mobileDetail?.materialId || '')).toBe(identity.materialId)
  expect(String(mobileDetail?.studentName || '')).toBe(String(library.studentName))
  expect(String(mobileDetail?.topicTitle || '')).toBe(String(fixture.topicTitle))
  expect(String(mobileDetail?.materialVersion ?? '')).toBe(identity.materialVersion)
  expect(String(mobileDetail?.fileVersionId || '')).toBe(identity.fileVersionId)
  expect(mobileDetail?.reviewReady).toBe(true)
  const versions = (mobileDetail?.currentSafeVersions || []).filter((row) =>
    String(row.versionId || row.fileVersionId || '') === identity.fileVersionId
  )
  expect(versions, 'mobile must expose the same immutable current file').toHaveLength(1)
  expect(String(versions[0].fileId)).toBe(String(current.fileId))
  expect(String(versions[0].sha256 || versions[0].sourceSha256 || '').toLowerCase()).toBe(identity.sha256)
}

test.describe.serial('V6 · one real thesis across student PC, teacher PC and teacher miniapp', () => {
  let fixture

  test.beforeAll(async () => {
    fixture = await prepareGraduationFixture()
  })

  test('same canonical FileVersion is read on PC and downloaded through the H5 preview path', async ({ page }, testInfo) => {
    test.setTimeout(8 * 60_000)
    const submission = await ensureFinalPending(page, fixture, {
      suffix: `cross-client-${testInfo.retry || 0}`, documentPages: 20
    })
    expect(submission.state, 'preview acceptance requires a real pending review task').toBe('PENDING_REVIEW')

    const studentShot = testInfo.outputPath('cross-client-thesis-student-pc-submitted.png')
    await expect(page.locator('[data-step-key="final"]')).toBeVisible()
    await page.locator('[data-step-key="final"]').scrollIntoViewIfNeeded()
    await page.screenshot({ path: studentShot, fullPage: false, animations: 'disabled', caret: 'hide' })
    await testInfo.attach('cross-client-thesis-student-pc-submitted', { path: studentShot, contentType: 'image/png' })

    await new StaffLoginPage(page, config.staffBaseUrl).login(config.mentor)
    await page.goto(`${config.staffBaseUrl}/admin/graduation/finals?batchId=${encodeURIComponent(fixture.batchId)}&tab=PENDING_REVIEW`)
    await dismissGraduationGuide(page)

    const workspace = page.locator('.gd-review-workspace')
    await expect(workspace).toBeVisible()
    const queue = workspace.locator('.gd-review-workspace__queue')
    await expect(queue).toContainText(fixture.topicTitle)
    const target = queue.getByRole('button').filter({ hasText: fixture.topicTitle })
    await expect(target, 'select the same student, never whichever queue entry is first').toHaveCount(1)
    await target.click()
    await expect.poll(() => new URL(page.url()).searchParams.get('sel'), {
      message: 'teacher PC must expose the exact submitted final record in URL'
    }).toBe(String(submission.submitted.id))

    const recordId = String(new URL(page.url()).searchParams.get('sel'))
    const command = page.getByTestId('review-command-contract')
    await expect(command).toContainText('提交版次')
    await expect(command).toContainText('文件核对')
    await expect(command).toContainText('可以批阅')
    const materialVersion = String(await command.getAttribute('data-material-version') || '')
    const fileVersionId = String(await command.getAttribute('data-file-version-id') || '')
    expect(materialVersion).toMatch(/^\d+$/)
    expect(fileVersionId).toMatch(/^\d+$/)
    const mentorApi = await loginApi(config.mentor)
    const params = { batchId: fixture.batchId }
    const pcDetail = await mentorApi.get(`/graduation/finals/${recordId}`, params)
    expect(String(pcDetail.id)).toBe(recordId)
    expect(String(pcDetail.materialVersion)).toBe(materialVersion)
    expect(String(pcDetail.fileVersionId)).toBe(fileVersionId)
    const readLibrary = () => mentorApi.get(`/graduation/material-center/students/${fixture.gdStudentId}/library`, {
      ...params, includeHistory: true
    })
    const library = await readLibrary()
    const identity = { recordId, materialVersion, fileVersionId, materialId: String(pcDetail.materialId || '') }
    expect(identity.materialId).toMatch(/^\d+$/)
    const current = assertLibraryIdentity(library, fixture, identity)
    identity.fileId = String(current.fileId || '')
    identity.sha256 = String(current.sha256 || current.sourceSha256 || '').toLowerCase()
    expect(identity.fileId).toMatch(/^\d+$/)
    expect(identity.sha256, 'authoritative file digest is required, not just a matching filename').toMatch(/^[a-f0-9]{64}$/)
    await expectRenderedPdfCanvas(page)
    await dismissGraduationGuide(page)

    const pcShot = testInfo.outputPath('cross-client-thesis-teacher-pc.png')
    await page.screenshot({ path: pcShot, fullPage: false, animations: 'disabled', caret: 'hide' })
    await testInfo.attach('cross-client-thesis-teacher-pc', { path: pcShot, contentType: 'image/png' })

    await page.setViewportSize({ width: 390, height: 844 })
    await loginTeacherMini(page)
    const taskQuery = new URLSearchParams({
      tab: 'review', kind: 'final', batchId: String(fixture.batchId),
      gdStudentId: String(fixture.gdStudentId), recordId, materialVersion, fileVersionId
    })
    const isExactMobileDetail = (response) => {
      const url = new URL(response.url())
      return response.request().method() === 'GET'
        && url.pathname.endsWith(`/api/v1/mobile/teacher/graduation/final/${recordId}`)
        && url.searchParams.get('batchId') === String(fixture.batchId)
    }
    const detailPromise = page.waitForResponse(isExactMobileDetail)
    await page.goto(`${MINI_BASE}/#/pages/teacher/graduation-guide/index?${taskQuery}`)
    const mobileDetail = await expectGraduationBusinessSuccess(await detailPromise, '教师小程序读取成果批阅详情')
    assertMobileIdentity(mobileDetail, fixture, identity, library)

    await expect(page.getByText(/成果批阅 · 第 1 \/ 1 条/).first()).toBeVisible({ timeout: 20_000 })
    const review = page.locator('.rv__content')
    await expect(review).toBeVisible({ timeout: 20_000 })
    await expect(review).toContainText(fixture.topicTitle)
    const versionRow = page.locator('.rv__att').filter({ hasText: `FileVersion ${fileVersionId}` }).first()
    await expect(versionRow, 'teacher miniapp must show the same canonical FileVersion as teacher PC').toBeVisible({ timeout: 20_000 })
    const pass = page.locator('.rv__foot .rv__pass')
    const reject = page.locator('.rv__foot .rv__return')
    await expectMiniControlState(pass, '通过')
    await expectMiniControlState(reject, '退回')

    const exactUrl = page.url()
    for (const [key, value] of taskQuery.entries()) {
      expect(decodeURIComponent(exactUrl), `teacher miniapp exact task URL must retain ${key}`).toContain(`${key}=${value}`)
    }
    const ticketPromise = page.waitForResponse((response) =>
      response.request().method() === 'POST'
      && new URL(response.url()).pathname.endsWith(`/api/v1/mobile/graduation/material-center/files/${identity.fileId}/ticket`)
    )
    const previewPromise = page.waitForResponse((response) =>
      response.request().method() === 'GET'
      && new URL(response.url()).pathname.endsWith(`/api/v1/mobile/graduation/material-center/files/${identity.fileId}/preview`)
      && new URL(response.url()).searchParams.has('ticket')
    )
    await versionRow.click()
    const ticketData = await expectGraduationBusinessSuccess(await ticketPromise, '教师小程序签发同一论文的预览票据')
    expect(ticketData?.ticket || ticketData?.url || ticketData?.previewUrl).toBeTruthy()
    const previewResponse = await previewPromise
    expect(previewResponse.ok(), `teacher miniapp PDF preview HTTP ${previewResponse.status()}`).toBeTruthy()
    const previewBytes = await previewResponse.body()
    expect(previewBytes.subarray(0, 5).toString('ascii')).toBe('%PDF-')
    expect(createHash('sha256').update(previewBytes).digest('hex'), 'mobile preview bytes must match the canonical uploaded PDF').toBe(identity.sha256)

    let returnConfirmationVerified = false
    const confirmCurrent = page.locator('.rv__preview-confirm .rv__confirm')
    if (await confirmCurrent.isVisible()) {
      await expectMiniControlState(pass, '通过', true)
      await expectMiniControlState(reject, '退回', true)
      await expectMiniControlState(confirmCurrent, '确认当前版本')
      const revalidatePromise = page.waitForResponse(isExactMobileDetail)
      await confirmCurrent.click()
      const fresh = await expectGraduationBusinessSuccess(await revalidatePromise, '教师小程序预览返回后重验论文版本')
      assertMobileIdentity(fresh, fixture, identity, await readLibrary())
      await expectMiniControlState(pass, '通过')
      await expectMiniControlState(reject, '退回')
      returnConfirmationVerified = true
    }
    // A fresh H5 task read is mandatory even where native openDocument is not
    // implemented by the browser. Never label that as a native WeChat test.
    const reloadPromise = page.waitForResponse(isExactMobileDetail)
    await page.reload()
    const reloaded = await expectGraduationBusinessSuccess(await reloadPromise, '教师 H5 重新进入后回读同一论文任务')
    assertMobileIdentity(reloaded, fixture, identity, await readLibrary())
    await expectMiniControlState(pass, '通过')
    await expectMiniControlState(reject, '退回')
    await expect(page.locator('body')).not.toContainText(
      /版本已变化|旧版审核已锁定|批次与当前选择不一致|指定的毕业设计待办不在当前批次/
    )
    const miniShot = testInfo.outputPath('cross-client-thesis-teacher-miniapp.png')
    await page.screenshot({ path: miniShot, fullPage: false, animations: 'disabled', caret: 'hide' })
    await testInfo.attach('cross-client-thesis-teacher-miniapp', { path: miniShot, contentType: 'image/png' })

    const evidence = testInfo.outputPath('cross-client-thesis-identity.json')
    await import('node:fs/promises').then(({ writeFile }) => writeFile(evidence, JSON.stringify({
      head: process.env.E2E_EXPECTED_SHA || process.env.GITHUB_SHA || 'local',
      coverage: 'student-PC submission, teacher-PC PDF rendering, teacher-H5 authorised preview bytes and fresh task read; not full lifecycle or native WeChat',
      nativeWeChatVerified: false, returnConfirmationVerified,
      batchId: String(fixture.batchId), gdStudentId: String(fixture.gdStudentId),
      ...identity, ownershipProof: 'authorised student library -> materialId -> immutable FileVersion -> mobile review record',
      scenarioFactory: 'graduation-scenario-fixture.ensureFinalPending',
      miniappEntry: 'exact-task-direct-review'
    }, null, 2), 'utf8'))
    await testInfo.attach('cross-client-thesis-identity', { path: evidence, contentType: 'application/json' })
  })
})
