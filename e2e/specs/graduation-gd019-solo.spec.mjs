import fs from 'node:fs'
import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { StaffLoginPage } from '../pages/login.page.mjs'

const fixture = JSON.parse(fs.readFileSync(new URL('../runtime-logs/gd019-solo-fixture.json', import.meta.url), 'utf8'))

async function dismissGuide(page) {
  for (const mask of [page.locator('.app-step-guide__mask'), page.locator('.tour-mask')]) {
    if (await mask.isVisible().catch(() => false)) {
      const skip = page.getByRole('button', { name: /跳过引导|跳过/ }).first()
      if (await skip.isVisible().catch(() => false)) await skip.click()
      await mask.waitFor({ state: 'hidden', timeout: 3000 }).catch(() => {})
    }
  }
}

test.describe.configure({ retries: 0 })

test('GD-019 solo: notification → XLSX export → statistics projection', async ({ page }) => {
  test.setTimeout(300000)
  await page.context().setExtraHTTPHeaders({ 'X-Forwarded-For': '10.254.19.91' })
  await new StaffLoginPage(page, config.staffBaseUrl).login(config.sandboxAdmin)
  await page.waitForLoadState('networkidle', { timeout: 60000 })

  await page.goto(`${config.staffBaseUrl}/admin/graduation/defense?batchId=${encodeURIComponent(fixture.batchId)}`)
  await dismissGuide(page)
  const row = page.locator('tbody tr').filter({ hasText: fixture.groupName }).first()
  await expect(row).toBeVisible({ timeout: 20000 })
  await expect(row).toContainText(/1 名学生/)
  await expect(row).toContainText('已发布')

  const notifyPromise = page.waitForResponse(
    (r) => r.request().method() === 'POST' && new URL(r.url()).pathname.endsWith('/graduation/gd-defense-notify')
  )
  await row.getByRole('button', { name: '通知', exact: true }).click()
  const notified = await notifyPromise
  expect(notified.ok(), `defense notify HTTP ${notified.status()}`).toBeTruthy()
  const notifyBody = await notified.json()
  console.log('GD019_NOTIFY_RESPONSE=' + JSON.stringify(notifyBody))
  expect(notifyBody.code, JSON.stringify(notifyBody)).toBe(0)
  expect(Number(notifyBody.data?.notified || 0)).toBe(1)

  const exportPromise = page.waitForResponse(
    (r) => r.request().method() === 'POST' && new URL(r.url()).pathname.endsWith('/graduation/defense-groups/export')
  )
  await page.getByRole('button', { name: /导出答辩表/ }).click()
  const exported = await exportPromise
  expect(exported.ok(), `defense export HTTP ${exported.status()}`).toBeTruthy()
  const exportBody = await exported.json()
  console.log('GD019_EXPORT_RESPONSE=' + JSON.stringify({
    code: exportBody.code,
    rowCount: exportBody.data?.rowCount,
    batchId: exportBody.data?.batchId,
    mediaType: exportBody.data?.mediaType,
    contentLength: String(exportBody.data?.contentBase64 || '').length,
  }))
  expect(exportBody.code, JSON.stringify(exportBody)).toBe(0)
  expect(Number(exportBody.data?.rowCount || 0)).toBe(1)
  expect(String(exportBody.data?.batchId || '')).toBe(String(fixture.batchId))
  expect(String(exportBody.data?.mediaType || '')).toContain('spreadsheetml')
  expect(String(exportBody.data?.contentBase64 || '').length).toBeGreaterThan(100)

  const peerStatsPromise = page.waitForResponse(
    (r) => r.request().method() === 'GET' && new URL(r.url()).pathname.endsWith('/graduation/gd-peer-reviews/stats')
  )
  const gradeStatsPromise = page.waitForResponse(
    (r) => r.request().method() === 'GET' && new URL(r.url()).pathname.endsWith('/graduation/gd-grades/stats')
  )
  await page.goto(`${config.staffBaseUrl}/admin/graduation/stats-report?batchId=${encodeURIComponent(fixture.batchId)}`)
  await dismissGuide(page)

  const [peerStatsRes, gradeStatsRes] = await Promise.all([peerStatsPromise, gradeStatsPromise])
  expect(peerStatsRes.ok(), `peer stats HTTP ${peerStatsRes.status()}`).toBeTruthy()
  expect(gradeStatsRes.ok(), `grade stats HTTP ${gradeStatsRes.status()}`).toBeTruthy()
  const peerBody = await peerStatsRes.json()
  const gradeBody = await gradeStatsRes.json()
  const peerStats = peerBody.data || peerBody
  const gradeStats = gradeBody.data || gradeBody
  console.log('GD019_PEER_STATS=' + JSON.stringify(peerStats))
  console.log('GD019_GRADE_STATS=' + JSON.stringify(gradeStats))
  expect(Number(peerStats.total || 0)).toBe(1)
  expect(Number(peerStats.RECTIFIED || peerStats.rectified || 0)).toBe(1)
  expect(Number(gradeStats.excellentCount || 0)).toBe(1)

  await expect(page.getByRole('heading', { name: '毕设统计报表', exact: true })).toBeVisible()
  const peerCard = page.locator('.mp-card').filter({ hasText: '成果互查统计' }).first()
  await expect(peerCard).toBeVisible()
  await expect(peerCard).toContainText('已整改')
  await expect(peerCard).toContainText('1')
  const gradeCard = page.locator('.mp-card').filter({ hasText: '成绩评定统计' }).first()
  await expect(gradeCard).toBeVisible()
  await expect(gradeCard).toContainText('优秀数')
  await expect(gradeCard).toContainText('1')
})
