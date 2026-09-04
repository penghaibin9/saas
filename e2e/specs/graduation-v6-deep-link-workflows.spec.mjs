import fs from 'node:fs/promises'

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

async function expectBusinessSuccess(response, action) {
  const body = await response.json()
  expect(response.ok(), `${action} HTTP ${response.status()}: ${JSON.stringify(body).slice(0, 800)}`).toBeTruthy()
  expect(body.code, `${action} business error: ${JSON.stringify(body).slice(0, 800)}`).toBe(0)
  return body.data
}

async function assertPageFit(page, label) {
  const result = await page.evaluate(() => ({
    viewport: window.innerWidth,
    document: document.documentElement.scrollWidth,
    body: document.body.scrollWidth,
    formShells: document.querySelectorAll('.gd-form-shell').length,
    sections: document.querySelectorAll('.gd-form-section, .gbf-section, .tlf-section, .dfg-section, .gsf-section, .dgf-fields, .dgf-command').length,
    asides: document.querySelectorAll('.gd-form-aside, .gd-form-aside-card, .gbf-aside-card, .tlf-aside-card, .dfg-aside-card, .gsf-aside-card, .dgf-aside-card').length,
  }))
  expect(result.document, `${label} document horizontal overflow`).toBeLessThanOrEqual(result.viewport + 2)
  expect(result.body, `${label} body horizontal overflow`).toBeLessThanOrEqual(result.viewport + 2)
  expect(result.formShells, `${label} must use the deep-link workflow shell`).toBeGreaterThan(0)
  expect(result.sections, `${label} must expose grouped business sections`).toBeGreaterThan(0)
  expect(result.asides, `${label} must expose completion/next-step content`).toBeGreaterThan(0)
}

async function capture(page, testInfo, name, width, height) {
  await page.setViewportSize({ width, height })
  await dismissGuide(page)
  await page.waitForLoadState('networkidle', { timeout: 5000 }).catch(() => {})
  await assertPageFit(page, `${name}-${width}`)
  const path = testInfo.outputPath(`${name}-${width}x${height}.png`)
  await page.screenshot({ path, fullPage: false, animations: 'disabled', caret: 'hide' })
  await testInfo.attach(`${name}-${width}x${height}`, { path, contentType: 'image/png' })
}

function route(base, path, params = {}) {
  const url = new URL(path, base)
  for (const [key, value] of Object.entries(params)) if (value != null && value !== '') url.searchParams.set(key, String(value))
  return url.toString()
}

test.describe.serial('V6 · graduation deep-link create workflows', () => {
  let fixture
  test.beforeAll(async () => { fixture = await prepareGraduationFixture() })

  test('batch create uses accessible labels and persists through the real API', async ({ page }, testInfo) => {
    await page.setViewportSize({ width: 1440, height: 900 })
    await new StaffLoginPage(page, config.staffBaseUrl).login(config.sandboxAdmin)
    await page.goto(route(config.staffBaseUrl, '/admin/graduation/batches/create', { returnTo: '/admin/graduation/batches?panel=list' }))
    await dismissGuide(page)

    await expect(page.getByRole('heading', { name: '新建毕业设计批次', exact: true })).toBeVisible()
    await expect(page.getByText('批次身份', { exact: false }).first()).toBeVisible()
    await expect(page.getByText('实施边界', { exact: false }).first()).toBeVisible()
    await expect(page.getByText('保存后的下一步', { exact: true })).toBeVisible()

    const retrySuffix = testInfo.retry ? `-r${testInfo.retry}` : ''
    const name = `E2E 深链批次 ${fixture.runId}${retrySuffix}`
    const number = `GD-DL-${String(fixture.runId).replace(/[^A-Za-z0-9]/g, '').slice(-12)}${retrySuffix}`
    await page.getByLabel('批次名称', { exact: false }).fill(name)
    await page.getByLabel('批次编号', { exact: false }).fill(number)
    await page.getByLabel('毕业届次', { exact: true }).fill('2026届')
    await page.getByLabel('所属学年', { exact: true }).fill('2025-2026')
    await page.getByLabel('计划学生数', { exact: true }).fill('120')
    await page.getByLabel('适用范围', { exact: true }).fill('计算机学院')

    await capture(page, testInfo, 'gd-v6-deep-batch-create', 1440, 900)
    await capture(page, testInfo, 'gd-v6-deep-batch-create', 1280, 800)

    const responsePromise = page.waitForResponse((response) => {
      const url = new URL(response.url())
      return response.request().method() === 'POST' && /\/api\/v1\/graduation\/batches$/.test(url.pathname)
    })
    await page.getByRole('button', { name: '创建批次', exact: true }).click()
    const created = await expectBusinessSuccess(await responsePromise, '创建毕业设计批次')
    expect(created?.id || created?.batchId).toBeTruthy()
    await expect(page).toHaveURL(/\/admin\/graduation\/batches/)
  })

  test('student create is a real-master relation workspace with empty-submit protection', async ({ page }, testInfo) => {
    await page.setViewportSize({ width: 1440, height: 900 })
    await new StaffLoginPage(page, config.staffBaseUrl).login(config.sandboxAdmin)
    const returnTo = `/admin/graduation/students?panel=roster&batchId=${fixture.batchId}&page=2&keyword=E2E`
    await page.goto(route(config.staffBaseUrl, '/admin/graduation/students/create', {
      batchId: fixture.batchId, source: 'students', returnPanel: 'roster', returnTo
    }))
    await dismissGuide(page)

    await expect(page.getByRole('heading', { name: '新建毕设学生档案', exact: true })).toBeVisible()
    await expect(page.getByText('选择学校学生主档', { exact: true })).toBeVisible()
    await expect(page.getByText('建立批次与指导关系', { exact: true })).toBeVisible()
    await expect(page.getByText('保存前检查', { exact: true })).toBeVisible()
    await expect(page.getByRole('button', { name: '确认建档', exact: true })).toBeDisabled()

    await capture(page, testInfo, 'gd-v6-deep-student-create', 1440, 900)
    await capture(page, testInfo, 'gd-v6-deep-student-create', 1280, 800)
    await page.getByRole('button', { name: '取消', exact: true }).click()
    await expect(page).toHaveURL(new RegExp(`/admin/graduation/students\\?.*batchId=${fixture.batchId}`))
    await expect(page).toHaveURL(/panel=roster/)
    await expect(page).toHaveURL(/page=2/)
    await expect(page).toHaveURL(/keyword=E2E/)
  })

  test('topic application preserves real review semantics and saves a draft', async ({ page }, testInfo) => {
    await page.setViewportSize({ width: 1440, height: 900 })
    await new StaffLoginPage(page, config.staffBaseUrl).login(config.sandboxAdmin)
    await page.goto(route(config.staffBaseUrl, '/admin/graduation/topic-lib/create', {
      sourceType: 'TEACHER', batchId: fixture.batchId, returnPanel: 'list',
      returnTo: `/admin/graduation/topic-lib?panel=list&batchId=${fixture.batchId}`
    }))
    await dismissGuide(page)

    await expect(page.getByRole('heading', { name: '教师申报毕业设计题目', exact: true })).toBeVisible()
    await expect(page.getByText('指导与适用范围', { exact: false }).first()).toBeVisible()
    await expect(page.getByText('完成标准', { exact: false }).first()).toBeVisible()

    const topicName = `基于真实业务流程的毕业论文跨端批阅研究-${fixture.runId}`
    await page.getByLabel(/题目名称/).fill(topicName)
    await page.getByLabel(/适用专业/).fill('软件技术')
    await page.getByLabel(/学生容量/).fill('2')
    await page.getByLabel(/题目要求/).fill('完成真实学生端提交、教师端 PDF 预览、审核回读和版本追溯。')
    await page.getByLabel(/预期成果/).fill('可运行系统、毕业论文、测试报告和部署说明。')
    await page.getByLabel(/技能要求/).fill('具备 Web 开发、数据库和测试基础。')

    await capture(page, testInfo, 'gd-v6-deep-topic-create', 1440, 900)
    await capture(page, testInfo, 'gd-v6-deep-topic-create', 1280, 800)

    const responsePromise = page.waitForResponse((response) => {
      const url = new URL(response.url())
      return response.request().method() === 'POST' && /\/api\/v1\/graduation\/gd-topics$/.test(url.pathname)
    })
    await page.getByRole('button', { name: '保存草稿', exact: true }).click()
    const created = await expectBusinessSuccess(await responsePromise, '保存毕业设计题目草稿')
    expect(created?.id || created?.topicId).toBeTruthy()
    await expect(page).toHaveURL(/\/admin\/graduation\/topic-lib/)
  })

  test('defense score locks the authenticated judge and preserves return context', async ({ page }, testInfo) => {
    await page.setViewportSize({ width: 1440, height: 900 })
    await new StaffLoginPage(page, config.staffBaseUrl).login(config.mentor)
    const returnTo = `/admin/graduation/defense-scoring?batchId=${fixture.batchId}&studentId=${fixture.gdStudentId}&panel=defense&queue=mine`
    await page.goto(route(config.staffBaseUrl, `/admin/graduation/defense-grade/${fixture.gdStudentId}/form`, {
      formKey: 'scoreEntry', batchId: fixture.batchId, studentId: fixture.gdStudentId,
      panel: 'defense', queue: 'mine', returnRoute: 'graduation-defense-scoring', returnTo
    }))
    await dismissGuide(page)

    await expect(page.getByRole('heading', { name: '录入本人答辩评分', exact: true })).toBeVisible()
    const command = page.locator('.dgf-command')
    await expect(command).toBeVisible()
    await expect(command).toContainText('答辩评委职责')
    await expect(command).toContainText('提交本人评分')
    const actor = page.locator('.dgf-actor')
    await expect(actor).toBeVisible()
    await expect(actor).toContainText('当前登录评委')
    await expect(actor).toContainText('身份已锁定')
    await expect(actor).toContainText('评分人来自登录身份与答辩组席位，不能在页面中修改。')
    await expect(page.getByLabel(/评委姓名/)).toHaveCount(0)
    await expect(page.locator('.dgf-context')).toContainText(fixture.studentNo)

    await page.getByLabel(/答辩评分/).fill('88')
    await expect(page.getByRole('button', { name: '提交本人评分', exact: true })).toBeEnabled()
    await capture(page, testInfo, 'gd-v6-deep-defense-score', 1440, 900)
    await capture(page, testInfo, 'gd-v6-deep-defense-score', 1280, 800)

    await page.getByRole('button', { name: '取消', exact: true }).click()
    await expect(page).toHaveURL(/\/admin\/graduation\/defense-scoring/)
    await expect(page).toHaveURL(new RegExp(`batchId=${fixture.batchId}`))
    await expect(page).toHaveURL(new RegExp(`studentId=${fixture.gdStudentId}`))
    await expect(page).toHaveURL(/queue=mine/)
  })

  test('defense group create continues into student assignment', async ({ page }, testInfo) => {
    await page.setViewportSize({ width: 1440, height: 900 })
    await new StaffLoginPage(page, config.staffBaseUrl).login(config.sandboxAdmin)
    await page.goto(route(config.staffBaseUrl, '/admin/graduation/defense/groups/create', {
      batchId: fixture.batchId, returnTo: `/admin/graduation/defense?batchId=${fixture.batchId}`
    }))
    await dismissGuide(page)

    await expect(page.getByRole('heading', { name: '新增答辩组', exact: true })).toBeVisible()
    await expect(page.getByText('分组与排期', { exact: false }).first()).toBeVisible()
    await expect(page.getByText('答辩职责', { exact: false }).first()).toBeVisible()
    await expect(page.getByText('发布前明显缺口', { exact: true })).toBeVisible()

    const groupName = `E2E 跨端论文答辩组 ${fixture.runId}`
    await page.getByLabel(/答辩组名称/).fill(groupName)
    await page.getByLabel(/答辩地点/).fill('实训楼 A301')
    await capture(page, testInfo, 'gd-v6-deep-defense-create', 1440, 900)
    await capture(page, testInfo, 'gd-v6-deep-defense-create', 1280, 800)

    const responsePromise = page.waitForResponse((response) => {
      const url = new URL(response.url())
      return response.request().method() === 'POST' && /\/api\/v1\/graduation\/defense-groups$/.test(url.pathname)
    })
    await page.getByRole('button', { name: '创建答辩组', exact: true }).click()
    const created = await expectBusinessSuccess(await responsePromise, '创建答辩组')
    const groupId = String(created?.id || created?.groupId || '')
    expect(groupId).toMatch(/^\d+$/)
    await expect(page).toHaveURL(new RegExp(`/admin/graduation/defense/groups/${groupId}/edit`))
    await expect(page.getByText('学生分配', { exact: false }).first()).toBeVisible()
    await expect(page.getByText('本组学生', { exact: true })).toBeVisible()
    await expect(page.getByText('可分配学生', { exact: true })).toBeVisible()

    const summaryPath = testInfo.outputPath('graduation-v6-deep-link-workflows.json')
    await fs.writeFile(summaryPath, JSON.stringify({
      contract: 'graduation-v6-deep-link-workflows-v3', head: process.env.GITHUB_SHA || 'local',
      batchId: fixture.batchId, createdGroupId: groupId,
      workflows: ['batch-create', 'student-create-empty-guard', 'topic-draft-create', 'defense-score-auth-actor', 'defense-group-create-to-assignment']
    }, null, 2), 'utf8')
    await testInfo.attach('graduation-v6-deep-link-workflows', { path: summaryPath, contentType: 'application/json' })
  })
})
