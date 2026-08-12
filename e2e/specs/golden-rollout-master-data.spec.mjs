import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { loadInternshipFixture } from '../lib/internship-fixture.mjs'
import { items, loginApi } from '../lib/api-fixture.mjs'

const VIEWPORT = { width: 1440, height: 1000 }

function runId() {
  const raw = process.env.GITHUB_RUN_ID || `${Date.now()}`
  return String(raw).replace(/\D/g, '').slice(-12) || String(Date.now()).slice(-12)
}

function academicYear() {
  const year = new Date().getUTCFullYear()
  return `${year}-${year + 1}`
}

async function dismissGuide(page) {
  for (const mask of [page.locator('.app-step-guide__mask'), page.locator('.tour-mask')]) {
    if (await mask.isVisible().catch(() => false)) {
      const skip = page.getByRole('button', { name: /跳过引导|跳过/ }).first()
      if (await skip.isVisible().catch(() => false)) await skip.click()
      await mask.waitFor({ state: 'hidden', timeout: 3000 }).catch(() => {})
    }
  }
}

async function settleVisual(page) {
  await page.evaluate(async () => {
    if (document.fonts?.ready) await document.fonts.ready
  })
  await page.waitForLoadState('networkidle', { timeout: 5000 }).catch(() => {})
}

async function capture(page, testInfo, name) {
  await dismissGuide(page)
  await settleVisual(page)
  const viewportPath = testInfo.outputPath(`${name}-1440x1000.png`)
  const fullPath = testInfo.outputPath(`${name}-full.png`)
  await page.screenshot({ path: viewportPath, fullPage: false, animations: 'disabled', caret: 'hide' })
  await page.screenshot({ path: fullPath, fullPage: true, animations: 'disabled', caret: 'hide' })
  await testInfo.attach(`${name}-viewport`, { path: viewportPath, contentType: 'image/png' })
  await testInfo.attach(`${name}-full`, { path: fullPath, contentType: 'image/png' })
}

async function openWithApiSession(page, api, path) {
  await page.addInitScript(({ token }) => {
    window.sessionStorage.setItem('gx_pc_token_v1', token)
  }, { token: api.token })
  await page.goto(`${config.staffBaseUrl}${path}`)
}

async function setStorage(page, key, value) {
  await page.evaluate(({ storageKey, storageValue }) => {
    window.localStorage.setItem(storageKey, String(storageValue))
  }, { storageKey: key, storageValue: value })
}

async function prepareClassFixture(admin) {
  const rows = items(await admin.get('/student-affairs/classes', { page: 1, pageSize: 50 }))
  if (!rows.length) throw new Error('Golden Batch 7 requires the isolated tenant organization seed to expose at least one class')
  const row = rows[0]
  return { classId: String(row.classId || row.id || ''), className: String(row.className || '') }
}

async function prepareGraduationTopicFixture(admin) {
  const marker = runId()
  const batchNo = `PW-GOLD-TOPIC-${marker}`
  let batch = items(await admin.get('/graduation/batches', { keyword: batchNo, page: 1, pageSize: 50 }))
    .find((row) => String(row.batchNo || '') === batchNo)

  if (!batch) {
    const year = new Date().getUTCFullYear()
    batch = await admin.post('/graduation/batches', {
      batchName: `Golden 题目库主数据 ${marker}`,
      batchNo,
      academicYear: academicYear(),
      gradeYear: `${year + 1}届`,
      plannedCount: 60,
      remark: 'Golden Batch 7 master-data screenshot only; isolated E2E database'
    })
  }

  if (String(batch.status || '').toUpperCase() !== 'DRAFT') {
    throw new Error(`Golden topic batch must remain DRAFT, got ${batch.status || 'UNKNOWN'}`)
  }

  const title = `Golden 智慧校园数据治理设计 ${marker}`
  let topic = items(await admin.get('/graduation/gd-topics', {
    batchId: String(batch.id), keyword: title, page: 1, pageSize: 50, archiveView: 'active'
  })).find((row) => String(row.title || '') === title)

  if (!topic) {
    topic = await admin.post('/graduation/gd-topics', {
      title,
      batchId: String(batch.id),
      topicNo: `GOLD-T-${marker}`,
      sourceType: 'TEACHER',
      advisorName: 'E2E指导教师A',
      majorName: '软件技术',
      requirements: '围绕真实校园业务完成需求分析、方案设计、实现与验收材料。',
      capacity: 3,
      submitReview: false
    })
  }

  if (!topic.id) throw new Error('Golden Batch 7 topic fixture did not return topic id')
  return { batchId: String(batch.id), batchName: String(batch.batchName || ''), topicId: String(topic.id), title }
}

test.describe.serial('Golden rollout · master data / core objects · Batch 7', () => {
  let adminApi
  let classFixture
  let internshipFixture
  let graduationFixture

  test.beforeAll(async () => {
    // Read authoritative class / enterprise facts from the isolated seed. Graduation
    // gets its own DRAFT batch + DRAFT topic and never reuses lifecycle students/taskbooks.
    adminApi = await loginApi(config.sandboxAdmin)
    classFixture = await prepareClassFixture(adminApi)
    internshipFixture = await loadInternshipFixture()
    graduationFixture = await prepareGraduationTopicFixture(adminApi)
  })

  test('Student Affairs class management · Screenshot B', async ({ page }, testInfo) => {
    await page.setViewportSize(VIEWPORT)
    await openWithApiSession(page, adminApi, '/admin/campus-service/classes')

    await expect(page).toHaveURL(/\/admin\/campus-service\/classes/)
    await expect(page.getByRole('heading', { name: '班级管理', exact: true })).toBeVisible()
    await expect(page.locator('.flt')).toBeVisible()
    await expect(page.locator('.dt')).toBeVisible()
    if (classFixture.className) {
      await expect(page.locator('.dt__tr').filter({ hasText: classFixture.className }).first()).toBeVisible()
    }

    const classContract = await page.evaluate(() => {
      const root = document.querySelector('.mps:has(.flt-input)')
      const head = root?.querySelector(':scope > .mps__head')
      const filter = root?.querySelector('.flt')
      const table = root?.querySelector('.dt')
      const note = root?.querySelector(':scope > .mp-stack > .mp-note:last-child')
      if (!root || !head || !filter || !table || !note) return null
      return {
        headRadius: getComputedStyle(head).borderRadius,
        filterRadius: getComputedStyle(filter).borderRadius,
        tableRadius: getComputedStyle(table).borderRadius,
        noteRadius: getComputedStyle(note).borderRadius
      }
    })
    expect(classContract).not.toBeNull()
    expect(classContract.headRadius).toBe('18px')
    expect(classContract.filterRadius).toBe('14px')
    expect(classContract.tableRadius).toBe('16px')
    expect(classContract.noteRadius).toBe('12px')

    await capture(page, testInfo, 'rollout-master-affairs-classes-b')
  })

  test('Internship enterprise library · Screenshot B', async ({ page }, testInfo) => {
    await page.setViewportSize(VIEWPORT)
    await openWithApiSession(page, adminApi, '/admin/internship/enterprises?panel=list')

    await expect(page).toHaveURL(/\/admin\/internship\/enterprises/)
    await expect(page.getByRole('heading', { name: '企业岗位库', exact: true })).toBeVisible()
    await expect(page.locator('.af')).toBeVisible()
    await expect(page.locator('.dt')).toBeVisible()
    await expect(page.locator('.dt__tr').filter({ hasText: internshipFixture.companyName }).first()).toBeVisible()

    const enterpriseContract = await page.evaluate(() => {
      const root = document.querySelector('.mps:has(> .mp-stack > .msr + .af)')
      const duplicateBatch = root?.querySelector(':scope > .mp-stack > .msr .msr__batch')
      const summary = root?.querySelector(':scope > .mp-stack > .msr')
      const filter = root?.querySelector('.af')
      const table = root?.querySelector('.dt')
      if (!root || !duplicateBatch || !summary || !filter || !table) return null
      return {
        duplicateBatchDisplay: getComputedStyle(duplicateBatch).display,
        summaryRadius: getComputedStyle(summary).borderRadius,
        filterRadius: getComputedStyle(filter).borderRadius,
        tableRadius: getComputedStyle(table).borderRadius
      }
    })
    expect(enterpriseContract).not.toBeNull()
    expect(enterpriseContract.duplicateBatchDisplay).toBe('none')
    expect(enterpriseContract.summaryRadius).toBe('14px')
    expect(enterpriseContract.filterRadius).toBe('14px')
    expect(enterpriseContract.tableRadius).toBe('16px')

    await capture(page, testInfo, 'rollout-master-internship-enterprises-b')
  })

  test('Graduation topic library · Screenshot B', async ({ page }, testInfo) => {
    await page.setViewportSize(VIEWPORT)
    await openWithApiSession(page, adminApi, '/admin/graduation/topic-lib?panel=list')
    await setStorage(page, 'graduation.selectedBatchId', graduationFixture.batchId)
    await page.reload()

    await expect(page).toHaveURL(/\/admin\/graduation\/topic-lib/)
    await expect(page.getByRole('heading', { name: '题目库', exact: true })).toBeVisible()
    await expect(page.locator('.mp-tabs')).toBeVisible()
    await expect(page.locator('.af')).toBeVisible()
    await expect(page.locator('.dt')).toBeVisible()
    await expect(page.locator('.dt__tr').filter({ hasText: graduationFixture.title }).first()).toBeVisible()

    const topicContract = await page.evaluate(() => {
      const root = document.querySelector('.mps:has(.gd-actions):has(.mp-tabs > .mp-tab:nth-child(11)):has(.af)')
      const head = root?.querySelector(':scope > .mps__head')
      const tabs = root?.querySelector('.mp-tabs')
      const activeTab = root?.querySelector('.mp-tab.is-active')
      const table = root?.querySelector('.dt')
      if (!root || !head || !tabs || !activeTab || !table) return null
      return {
        headRadius: getComputedStyle(head).borderRadius,
        tabsRadius: getComputedStyle(tabs).borderRadius,
        activeTabRadius: getComputedStyle(activeTab).borderRadius,
        tableRadius: getComputedStyle(table).borderRadius
      }
    })
    expect(topicContract).not.toBeNull()
    expect(topicContract.headRadius).toBe('17px')
    expect(topicContract.tabsRadius).toBe('13px')
    expect(topicContract.activeTabRadius).toBe('9px')
    expect(topicContract.tableRadius).toBe('16px')

    await capture(page, testInfo, 'rollout-master-graduation-topic-lib-b')
  })
})