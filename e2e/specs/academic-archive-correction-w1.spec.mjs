import { readFileSync } from 'node:fs'
import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { loginApi } from '../lib/api-fixture.mjs'
import { StaffLoginPage } from '../pages/login.page.mjs'

const fixture = JSON.parse(readFileSync(
  new URL('../academic-archive-correction-w1-fixture.json', import.meta.url),
  'utf8'
))
const creatorAccount = {
  tenant: fixture.tenant,
  username: fixture.creator.username,
  password: fixture.creator.password
}
const reviewerAccount = {
  tenant: fixture.tenant,
  username: fixture.reviewer.username,
  password: fixture.reviewer.password
}

function waitForBrowserRefresh(page, timeout = 20_000) {
  return page.waitForResponse(
    (response) => response.url().includes('/api/v1/auth/browser-refresh') &&
      response.request().method() === 'POST' && response.status() === 200,
    { timeout }
  )
}

async function dismissGuide(page) {
  const guide = page.getByRole('dialog', { name: '页面操作引导' })
  if (!(await guide.isVisible({ timeout: 1_000 }).catch(() => false))) return
  const skip = guide.getByRole('button', { name: '跳过引导' })
  if (await skip.isVisible({ timeout: 1_000 }).catch(() => false)) await skip.click()
}

async function gotoArchive(page) {
  const refresh = waitForBrowserRefresh(page)
  await page.goto(new URL('/admin/academic-affairs/archive', config.staffBaseUrl).toString())
  await refresh
  await page.locator('.uchip__role').first().waitFor({ state: 'visible', timeout: 20_000 })
  await dismissGuide(page)
  const batch = page.locator('.aaar-item').filter({ hasText: fixture.batchName }).first()
  await expect(batch).toBeVisible()
  await batch.click()
  await expect(page.getByRole('tab', { name: '归档事实' })).toBeVisible()
  await expect(page.getByRole('tab', { name: '归档后纠错' })).toBeVisible()
  await expect(page.getByRole('tab', { name: 'Manifest版本链' })).toBeVisible()
}

async function loginAndOpenArchive(page, account) {
  await new StaffLoginPage(page, config.staffBaseUrl).login(account)
  await page.locator('.uchip__role').first().waitFor({ state: 'visible', timeout: 20_000 })
  await gotoArchive(page)
}

async function openCorrectionTab(page) {
  await page.getByRole('tab', { name: '归档后纠错' }).click()
  await expect(page.getByRole('button', { name: '发起归档后纠错' })).toBeVisible()
}

async function createGradeCorrection(page, { targetRef, reason, score, suffix }) {
  await page.getByRole('button', { name: '发起归档后纠错' }).click()
  await page.getByLabel('业务类型').selectOption('GRADE')
  await page.getByLabel('目标正式事实 ID').fill(String(targetRef))
  await page.getByLabel('纠错原因').fill(reason)
  await page.getByLabel('修正内容（JSON）').fill(JSON.stringify({ score }, null, 2))
  await page.getByLabel('证据清单（JSON）').fill(JSON.stringify({
    kind: 'W1_BROWSER_REVIEW',
    refs: [`browser-${suffix}`],
    sha256: 'd'.repeat(64)
  }, null, 2))

  const responsePromise = page.waitForResponse(
    (response) => response.url().includes(`/api/v1/academic-affairs/archive/batches/${fixture.batchId}/corrections`) &&
      response.request().method() === 'POST',
    { timeout: 20_000 }
  )
  await page.getByRole('button', { name: '提交纠错申请' }).click()
  const response = await responsePromise
  expect(response.status()).toBe(200)
  const payload = await response.json()
  expect(payload.code).toBe(0)
  expect(payload.data.status).toBe('PENDING_SECOND_APPROVAL')
  return payload.data
}

async function openCorrectionDetail(page, targetRef, reason) {
  const row = page.getByRole('row')
    .filter({ hasText: String(targetRef) })
    .filter({ hasText: reason })
    .first()
  await expect(row).toBeVisible()
  await row.getByRole('button', { name: '查看 / 复核' }).click()
  const detail = page.getByRole('dialog').filter({ hasText: '原事实与新事实对比' }).first()
  await expect(detail).toBeVisible()
  await expect(detail.getByText('原事实与新事实对比', { exact: true })).toBeVisible()
  await expect(detail.getByText(reason, { exact: true })).toBeVisible()
}

async function capture(page, testInfo, name) {
  const path = testInfo.outputPath(`${name}.png`)
  await page.screenshot({ path, fullPage: false, animations: 'disabled', caret: 'hide' })
  await testInfo.attach(name, { path, contentType: 'image/png' })
}

test('W1 ARCHIVED correction: two-person approve appends Manifest, reject stays side-effect free', async ({ page, browser }, testInfo) => {
  const retryIndex = Math.min(testInfo.retry, fixture.approvalTargetIds.length - 1)
  const approvalTarget = fixture.approvalTargetIds[retryIndex]
  const rejectTarget = fixture.rejectTargetIds[retryIndex]
  const suffix = `${process.env.GITHUB_RUN_ID || 'local'}-r${testInfo.retry}`
  const approveReason = `W1浏览器验收批准链 ${suffix}：复核原卷确认成绩录入错误`
  const rejectReason = `W1浏览器验收驳回链 ${suffix}：证据不足，补齐后重新申请`

  const creatorApi = await loginApi(creatorAccount)
  const initialManifest = await creatorApi.get(`/academic-affairs/archive/batches/${fixture.batchId}/manifest/verify`)
  expect(initialManifest.ok).toBeTruthy()
  expect(initialManifest.versions[0].versionNo).toBe(1)
  expect(initialManifest.versions[0].hash).toBe(fixture.manifestV1Hash)
  const initialVersionCount = initialManifest.versions.length
  const initialLatestVersion = initialManifest.versions.at(-1).versionNo

  await loginAndOpenArchive(page, creatorAccount)
  await expect(page.getByText('普通解冻入口已关闭', { exact: false })).toBeVisible()
  await openCorrectionTab(page)

  const created = await createGradeCorrection(page, {
    targetRef: approvalTarget,
    reason: approveReason,
    score: retryIndex === 0 ? 66 : 76,
    suffix: `${suffix}-approve`
  })
  const approveCaseId = created.caseId
  await openCorrectionDetail(page, approvalTarget, approveReason)
  await expect(page.getByText('拟形成事实（非正式）', { exact: true })).toBeVisible()
  await expect(page.getByText('申请人本人执行二审会被服务端拒绝', { exact: false })).toBeVisible()

  await page.getByRole('button', { name: '二审通过并生成新正式事实' }).click()
  const creatorDialog = page.getByRole('dialog').filter({ hasText: '确认二次审批通过' }).first()
  await expect(creatorDialog).toBeVisible()
  const deniedPromise = page.waitForResponse(
    (response) => response.url().includes(`/api/v1/academic-affairs/archive/corrections/${approveCaseId}/approve`) &&
      response.request().method() === 'POST',
    { timeout: 20_000 }
  )
  await creatorDialog.getByRole('button', { name: '确认批准并生成新事实' }).click()
  const denied = await deniedPromise
  expect(denied.status()).toBe(403)
  const deniedPayload = await denied.json()
  expect(deniedPayload.code).not.toBe(0)
  await expect(creatorDialog).toBeVisible()
  await creatorDialog.getByRole('button', { name: '取消' }).click()
  await expect(page.getByText('待二审', { exact: true }).first()).toBeVisible()
  await capture(page, testInfo, 'w1-same-requester-second-review-denied')

  const reviewerContext = await browser.newContext({ locale: 'zh-CN', timezoneId: 'Asia/Shanghai' })
  const reviewerPage = await reviewerContext.newPage()
  const reviewerApi = await loginApi(reviewerAccount)
  try {
    await loginAndOpenArchive(reviewerPage, reviewerAccount)
    await openCorrectionTab(reviewerPage)
    await openCorrectionDetail(reviewerPage, approvalTarget, approveReason)

    await reviewerPage.getByRole('button', { name: '二审通过并生成新正式事实' }).click()
    const approveDialog = reviewerPage.getByRole('dialog').filter({ hasText: '确认二次审批通过' }).first()
    await expect(approveDialog).toBeVisible()
    const approvePromise = reviewerPage.waitForResponse(
      (response) => response.url().includes(`/api/v1/academic-affairs/archive/corrections/${approveCaseId}/approve`) &&
        response.request().method() === 'POST',
      { timeout: 20_000 }
    )
    await approveDialog.getByRole('button', { name: '确认批准并生成新事实' }).click()
    const approvedResponse = await approvePromise
    expect(approvedResponse.status()).toBe(200)
    const approvedPayload = await approvedResponse.json()
    expect(approvedPayload.code).toBe(0)
    expect(approvedPayload.data.status).toBe('APPLIED')
    expect(approvedPayload.data.manifestVersion).toBe(initialLatestVersion + 1)
    await expect(reviewerPage.getByText('新正式事实', { exact: true })).toBeVisible()
    await expect(reviewerPage.getByText('已形成正式事实', { exact: false })).toBeVisible()
    await capture(reviewerPage, testInfo, 'w1-second-reviewer-approved')

    const appliedDetail = await reviewerApi.get(`/academic-affairs/archive/corrections/${approveCaseId}`)
    expect(appliedDetail.status).toBe('APPLIED')
    expect(appliedDetail.officialFactId).toBeTruthy()
    expect(appliedDetail.resultingManifestId).toBeTruthy()
    expect(appliedDetail.originalOfficialFact.factId).toBe(String(approvalTarget))
    expect(appliedDetail.resultingOfficialFact.factId).toBe(appliedDetail.officialFactId)
    expect(appliedDetail.resultingOfficialFact.sourceBizType).toBe('POST_ARCHIVE')
    expect(appliedDetail.resultingOfficialFact.sourceBizId).toBe(String(approveCaseId))

    const afterApproveManifest = await reviewerApi.get(`/academic-affairs/archive/batches/${fixture.batchId}/manifest/verify`)
    expect(afterApproveManifest.ok).toBeTruthy()
    expect(afterApproveManifest.versions.length).toBe(initialVersionCount + 1)
    expect(afterApproveManifest.versions[0].hash).toBe(fixture.manifestV1Hash)
    expect(afterApproveManifest.versions.at(-1).versionNo).toBe(initialLatestVersion + 1)
    const manifestCountAfterApprove = afterApproveManifest.versions.length

    await gotoArchive(page)
    await openCorrectionTab(page)
    const rejectedCreated = await createGradeCorrection(page, {
      targetRef: rejectTarget,
      reason: rejectReason,
      score: retryIndex === 0 ? 69 : 88,
      suffix: `${suffix}-reject`
    })
    const rejectCaseId = rejectedCreated.caseId

    await gotoArchive(reviewerPage)
    await openCorrectionTab(reviewerPage)
    await openCorrectionDetail(reviewerPage, rejectTarget, rejectReason)
    const rejectDecisionReason = `二审驳回 ${suffix}：材料证据不能支持正式历史事实变更`
    await reviewerPage.getByRole('button', { name: '驳回', exact: true }).click()
    const rejectDialog = reviewerPage.getByRole('dialog').filter({ hasText: '确认驳回归档后纠错' }).first()
    await expect(rejectDialog).toBeVisible()
    await rejectDialog.getByLabel('驳回原因').fill(rejectDecisionReason)
    const rejectPromise = reviewerPage.waitForResponse(
      (response) => response.url().includes(`/api/v1/academic-affairs/archive/corrections/${rejectCaseId}/reject`) &&
        response.request().method() === 'POST',
      { timeout: 20_000 }
    )
    await rejectDialog.getByRole('button', { name: '确认驳回' }).click()
    const rejectedResponse = await rejectPromise
    expect(rejectedResponse.status()).toBe(200)
    const rejectedPayload = await rejectedResponse.json()
    expect(rejectedPayload.code).toBe(0)
    expect(rejectedPayload.data.status).toBe('REJECTED')
    expect(rejectedPayload.data.officialFactId).toBeNull()
    expect(rejectedPayload.data.resultingManifestId).toBeNull()
    await expect(reviewerPage.getByText('未生成正式事实，也未生成新 Manifest', { exact: false })).toBeVisible()
    await capture(reviewerPage, testInfo, 'w1-second-reviewer-rejected')

    const rejectedDetail = await reviewerApi.get(`/academic-affairs/archive/corrections/${rejectCaseId}`)
    expect(rejectedDetail.status).toBe('REJECTED')
    expect(rejectedDetail.rejectReason).toBe(rejectDecisionReason)
    expect(rejectedDetail.rejectedBy).toBe(fixture.reviewerUserId)
    expect(rejectedDetail.officialFactId).toBeNull()
    expect(rejectedDetail.resultingManifestId).toBeNull()
    expect(rejectedDetail.resultingOfficialFact).toBeNull()

    const afterRejectManifest = await reviewerApi.get(`/academic-affairs/archive/batches/${fixture.batchId}/manifest/verify`)
    expect(afterRejectManifest.ok).toBeTruthy()
    expect(afterRejectManifest.versions.length).toBe(manifestCountAfterApprove)
    expect(afterRejectManifest.versions[0].hash).toBe(fixture.manifestV1Hash)

    await reviewerPage.getByRole('button', { name: '关闭' }).click()
    await reviewerPage.getByRole('tab', { name: 'Manifest版本链' }).click()
    await expect(reviewerPage.getByText('Manifest 版本链', { exact: true })).toBeVisible()
    await expect(reviewerPage.getByText('V1', { exact: true })).toBeVisible()
    await expect(reviewerPage.getByText(`V${initialLatestVersion + 1}`, { exact: true })).toBeVisible()
    await capture(reviewerPage, testInfo, 'w1-manifest-version-chain-preserved')
  } finally {
    await reviewerContext.close()
  }
})
