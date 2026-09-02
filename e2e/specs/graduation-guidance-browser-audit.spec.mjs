import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { prepareGraduationFixture } from '../lib/api-fixture.mjs'
import { StaffLoginPage, StudentLoginPage } from '../pages/login.page.mjs'
import { StudentGraduationPage } from '../pages/graduation.page.mjs'

async function dismissGuide(page) {
  for (const mask of [page.locator('.app-step-guide__mask'), page.locator('.tour-mask')]) {
    if (await mask.isVisible().catch(() => false)) {
      const skip = page.getByRole('button', { name: /跳过引导|跳过/ }).first()
      if (await skip.isVisible().catch(() => false)) await skip.click()
      await mask.waitFor({ state: 'hidden', timeout: 3000 }).catch(() => {})
    }
  }
}

function processUrl(fixture) {
  const url = new URL(`${config.staffBaseUrl}/admin/graduation/process`)
  url.searchParams.set('batchId', fixture.batchId)
  url.searchParams.set('studentId', fixture.gdStudentId)
  url.searchParams.set('panel', 'guidance')
  url.searchParams.set('source', 'E2E-AUDIT-20260823')
  return url.toString()
}

test.describe.configure({ retries: 0 })

test.describe.serial('毕业设计过程指导 Browser First · 新增/刷新/学生可见/审计', () => {
  let fixture

  test.beforeAll(async () => {
    fixture = await prepareGraduationFixture()
  })

  test('导师真实新增指导 → 保存 → 重新进入/刷新仍存在 → 学生端可见', async ({ page }) => {
    const content = `E2E-AUDIT-20260823 指导记录 ${fixture.runId}：检查开题准备与研究计划，要求补齐异常场景和可追溯测试证据。`
    const issues = 'E2E-AUDIT-20260823 当前问题：边界场景覆盖不足，需在中期前完成补测。'

    await new StaffLoginPage(page, config.staffBaseUrl).login(config.mentor)
    await page.goto(processUrl(fixture))
    await dismissGuide(page)
    await expect(page.getByRole('heading', { name: '过程指导', exact: true })).toBeVisible()
    await expect(page.locator('.gp-context')).toContainText(fixture.studentNo)
    await expect(page.getByRole('button', { name: '＋ 新增指导记录', exact: true })).toBeVisible()
    await page.getByRole('button', { name: '＋ 新增指导记录', exact: true }).click()

    await expect(page.getByRole('heading', { name: '新增指导记录', exact: true })).toBeVisible()
    const form = page.locator('form.ie-form')
    await expect(form).toBeVisible()
    await form.getByPlaceholder('详细记录本次指导内容、建议…').fill(content)
    await form.locator('label').filter({ hasText: '发现的问题' }).locator('textarea').fill(issues)

    const [createResponse] = await Promise.all([
      page.waitForResponse((r) => r.request().method() === 'POST' && new URL(r.url()).pathname.endsWith(`/graduation/gd-guidances/${fixture.gdStudentId}`)),
      page.getByRole('button', { name: '保存', exact: true }).click()
    ])
    expect(createResponse.ok(), `guidance create HTTP ${createResponse.status()}`).toBeTruthy()
    const body = await createResponse.json()
    expect(body.code).toBe(0)
    expect(String(body.data?.content || '')).toContain('E2E-AUDIT-20260823')

    // 保存后的返回路由可能不保留 studentId；重新从完整业务入口进入，验证不是前端内存假状态。
    await page.goto(processUrl(fixture))
    await dismissGuide(page)
    await expect(page.locator('.gp-context')).toContainText(fixture.studentNo)
    await expect(page.locator('.gp-timeline')).toContainText(content)
    await expect(page.locator('.gp-timeline')).toContainText(issues)

    await page.reload()
    await dismissGuide(page)
    await expect(page.locator('.gp-context')).toContainText(fixture.studentNo)
    await expect(page.locator('.gp-timeline')).toContainText(content)

    await new StudentLoginPage(page, config.studentBaseUrl).login(config.student)
    const student = new StudentGraduationPage(page, config.studentBaseUrl)
    await student.open()
    const guidanceStep = page.locator('.gd-step').filter({ has: page.getByRole('heading', { name: '过程指导', exact: true }) }).first()
    await expect(guidanceStep).toBeVisible()
    await expect(guidanceStep).toContainText(/已有\s*1\s*条记录|已有.*条记录/)
    await expect(guidanceStep).toContainText('E2E-AUDIT-20260823')
  })
})
