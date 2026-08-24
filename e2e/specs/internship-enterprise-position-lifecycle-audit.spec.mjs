import fs from 'node:fs/promises'
import { execFileSync } from 'node:child_process'
import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { StaffLoginPage, StudentLoginPage } from '../pages/login.page.mjs'

const enterpriseBaseUrl = process.env.E2E_ENTERPRISE_BASE_URL || 'http://127.0.0.1:5202/enterprise'
const ENTERPRISE_PASSWORD = 'E2eEnterprise@2026'

function apiPath(response) {
  try { return new URL(response.url()).pathname } catch { return '' }
}

async function payloadOf(response) {
  const text = await response.text()
  try { return { text, body: JSON.parse(text) } } catch { return { text, body: null } }
}

function formItem(page, label) {
  return page.locator('.app-form-item').filter({ hasText: label }).first()
}

function companyRow(page, companyName) {
  return page.locator('tbody tr').filter({ hasText: companyName }).first()
}

async function staffLogin(page) {
  await new StaffLoginPage(page, config.staffBaseUrl).login(config.sandboxAdmin)
}

async function confirmStatusAction(page, positionId, triggerName, confirmName) {
  await page.getByRole('button', { name: triggerName, exact: true }).click()
  const dialog = page.getByRole('dialog')
  await expect(dialog).toBeVisible()
  const responsePromise = page.waitForResponse((response) =>
    apiPath(response) === `/api/v1/internship/positions/${positionId}/status`
      && response.request().method() === 'POST'
  )
  await dialog.getByRole('button', { name: confirmName, exact: true }).click()
  const response = await responsePromise
  const { text, body } = await payloadOf(response)
  return { response, text, body }
}

test.describe('岗位实习审计：IX-003 企业生命周期 + IX-005 岗位生命周期', () => {
  test.describe.configure({ mode: 'serial', retries: 0 })

  let fixture
  let companyId = ''
  let positionId = ''
  let inviteToken = ''
  let enterpriseLogin = ''
  let enterprisePhone = ''

  test.beforeAll(async () => {
    execFileSync('python', ['../backend/scripts/e2e_seed_internship_enterprise_position_sandbox.py'], {
      cwd: process.cwd(), env: process.env, stdio: 'inherit'
    })
    fixture = JSON.parse(await fs.readFile('./runtime/internship-enterprise-position-fixture.json', 'utf8'))
    expect(fixture.initialStatus).toBe('PREPARING')
    expect(fixture.initialDestinationType).toBe('NONE')
    enterpriseLogin = `ixep_${fixture.runId}`
    const digits = String(fixture.runId).replace(/\D/g, '').slice(-8).padStart(8, '0')
    enterprisePhone = `139${digits}`
  })

  const companyName = () => `IX003跃科浏览器企业${fixture.runId}`
  const creditCode = () => `IX${String(fixture.runId).slice(-12)}`.replace(/[^0-9A-Za-z]/g, '').slice(0, 20)
  const originalPositionTitle = () => `IX005企业报送测试岗${fixture.runId}`
  const finalPositionTitle = () => `IX005学校校审测试岗${fixture.runId}`

  test('IX-003：学校真实创建企业、审核通过、暂停并恢复，列表电话保持脱敏', async ({ page }) => {
    await staffLogin(page)
    await page.goto(`${config.staffBaseUrl}/admin/internship/enterprises`)
    await page.getByRole('button', { name: '＋ 新增企业', exact: true }).click()
    await expect(page).toHaveURL(/\/admin\/internship\/enterprises\/new/)

    await formItem(page, '企业名称').locator('input').fill(companyName())
    await formItem(page, '统一社会信用代码').locator('input').fill(creditCode())
    await formItem(page, '联系人').locator('input').fill('IX003企业联系人')
    await formItem(page, '联系电话').locator('input').fill(enterprisePhone)

    const createPromise = page.waitForResponse((response) =>
      apiPath(response) === '/api/v1/internship/enterprises'
        && response.request().method() === 'POST'
    )
    await page.getByRole('button', { name: '创建企业', exact: true }).click()
    const created = await createPromise
    const createdPayload = await payloadOf(created)
    expect(createdPayload.body?.code, createdPayload.text).toBe(0)
    companyId = String(createdPayload.body?.data?.id || '')
    expect(companyId).not.toBe('')

    await expect(page).toHaveURL(/\/admin\/internship\/enterprises(?:\?|$)/)
    let row = companyRow(page, companyName())
    await expect(row).toBeVisible()
    await expect(row).not.toContainText(enterprisePhone)

    await row.getByRole('button', { name: '审核通过', exact: true }).click()
    let dialog = page.getByRole('dialog')
    await dialog.getByRole('button', { name: '通过（资质合格）', exact: true }).click()
    row = companyRow(page, companyName())
    await expect(row).toContainText('合作中')

    await row.getByRole('button', { name: '暂停', exact: true }).click()
    dialog = page.getByRole('dialog')
    await dialog.getByRole('button', { name: '确认暂停', exact: true }).click()
    row = companyRow(page, companyName())
    await expect(row).toContainText('已暂停')

    await row.getByRole('button', { name: '恢复', exact: true }).click()
    dialog = page.getByRole('dialog')
    await dialog.getByRole('button', { name: '确认恢复', exact: true }).click()
    row = companyRow(page, companyName())
    await expect(row).toContainText('合作中')
  })

  test('IX-003：学校真实邀请企业加入当前招聘季，企业门户真实接受邀请', async ({ page }) => {
    expect(companyId).not.toBe('')
    await staffLogin(page)
    await page.goto(`${config.staffBaseUrl}/admin/internship/recruitment-campaigns/${fixture.campaignId}`)
    await expect(page.getByRole('button', { name: '邀请企业', exact: true })).toBeEnabled()
    await page.getByRole('button', { name: '邀请企业', exact: true }).click()

    await formItem(page, '选择企业').locator('select').selectOption({ label: companyName() })
    await formItem(page, '联系人姓名').locator('input').fill('IX003企业管理员')
    await formItem(page, '登录账号').locator('input').fill(enterpriseLogin)
    await formItem(page, '联系人手机号').locator('input').fill(enterprisePhone)

    const invitePromise = page.waitForResponse((response) =>
      apiPath(response) === `/api/v1/internship/recruitment-campaigns/${fixture.campaignId}/enterprises/invite`
        && response.request().method() === 'POST'
    )
    await page.getByRole('button', { name: '生成邀请', exact: true }).click()
    const invited = await invitePromise
    const invitedPayload = await payloadOf(invited)
    expect(invitedPayload.body?.code, invitedPayload.text).toBe(0)
    inviteToken = String(invitedPayload.body?.data?.inviteToken || '')
    expect(inviteToken).not.toBe('')

    await page.goto(`${enterpriseBaseUrl}/invite/accept?token=${encodeURIComponent(inviteToken)}&tenantCode=${encodeURIComponent(fixture.tenantCode)}`)
    await expect(page.getByRole('heading', { name: '企业邀请承接' })).toBeVisible()
    await page.getByLabel('验证受邀手机号').fill(enterprisePhone)
    await page.getByLabel(/设置密码/).fill(ENTERPRISE_PASSWORD)
    await page.getByRole('button', { name: '接受邀请并进入企业协同中心', exact: true }).click()
    await expect(page).toHaveURL(/\/enterprise\/home/)
    await expect(page.getByText(companyName(), { exact: false }).first()).toBeVisible()
  })

  test('IX-005：企业门户真实创建并提交岗位，岗位自动绑定招聘季和批次', async ({ page }) => {
    await page.goto(`${enterpriseBaseUrl}/login`)
    await page.getByLabel(/学校编码/).fill(fixture.tenantCode)
    await page.getByLabel(/登录账号/).fill(enterpriseLogin)
    await page.getByLabel(/密码/).fill(ENTERPRISE_PASSWORD)
    await page.getByRole('button', { name: /登录/ }).click()

    await expect(page).toHaveURL(/\/enterprise\/(?:campaign-select|home)/)
    if (page.url().includes('/campaign-select')) {
      await page.getByRole('button', { name: new RegExp(fixture.campaignName) }).click()
      await expect(page).toHaveURL(/\/enterprise\/home/)
    }
    await page.goto(`${enterpriseBaseUrl}/positions/new`)
    await expect(page.getByRole('heading', { name: '创建实习岗位' })).toBeVisible()

    await page.getByLabel(/岗位名称/).fill(originalPositionTitle())
    await page.getByLabel(/招聘人数/).fill('2')
    await page.getByLabel(/详细工作地址/).fill('湖南省长沙市岳麓区测试产业园 18 号')
    await page.getByLabel(/工作内容/).fill('软件测试、回归验证、缺陷复现与质量记录')
    await page.getByLabel(/每日工时/).fill('8')
    await page.getByLabel(/每周工时/).fill('40')
    await page.getByLabel(/每周休息天数/).fill('2')
    await page.getByLabel(/报酬金额/).fill('4200')
    await page.getByLabel(/薪资展示/).fill('4200元/月')

    await page.getByRole('button', { name: /选择省.*市.*区县/ }).click()
    await page.getByRole('textbox', { name: '搜索省、市或区县' }).fill('长沙市岳麓区')
    await page.locator('.region-picker__results button').filter({ hasText: '岳麓区' }).first().click()

    const createPromise = page.waitForResponse((response) =>
      apiPath(response) === '/api/v1/internship/enterprise-portal/positions'
        && response.request().method() === 'POST'
    )
    await page.getByRole('button', { name: '提交学校审核', exact: true }).click()
    const created = await createPromise
    const createdPayload = await payloadOf(created)
    expect(createdPayload.body?.code, createdPayload.text).toBe(0)
    positionId = String(createdPayload.body?.data?.id || '')
    expect(positionId).not.toBe('')
    expect(String(createdPayload.body?.data?.campaignId || '')).toBe(String(fixture.campaignId))
    await expect(page).toHaveURL(/\/enterprise\/positions(?:\?|$)/)
  })

  test('IX-005：学校岗位详情真实编辑携带 expectedVersion，然后发布', async ({ page }) => {
    expect(positionId).not.toBe('')
    await staffLogin(page)
    await page.goto(`${config.staffBaseUrl}/admin/internship/positions/${positionId}`)
    await expect(page.getByText(originalPositionTitle(), { exact: false }).first()).toBeVisible()
    await page.getByRole('button', { name: '编辑', exact: true }).click()

    await expect(page.getByText('编辑岗位', { exact: true })).toBeVisible()
    await page.locator('.ie-fld').filter({ hasText: '岗位名称' }).locator('input').fill(finalPositionTitle())

    const updatePromise = page.waitForResponse((response) =>
      apiPath(response) === `/api/v1/internship/positions/${positionId}`
        && response.request().method() === 'PUT'
    )
    await page.locator('.ie-actions').getByRole('button', { name: '保存', exact: true }).click()
    const updated = await updatePromise
    const requestBody = updated.request().postDataJSON()
    expect(Number.isInteger(Number(requestBody?.expectedVersion))).toBeTruthy()
    const updatedPayload = await payloadOf(updated)
    expect(updatedPayload.body?.code, updatedPayload.text).toBe(0)
    await expect(page.getByText(finalPositionTitle(), { exact: false }).first()).toBeVisible()

    const published = await confirmStatusAction(page, positionId, '上架', '确认上架')
    expect(published.body?.code, published.text).toBe(0)
    await expect(page.getByRole('button', { name: '下架', exact: true })).toBeVisible()
  })

  test('IX-003/005：Student PC 只看到 server truth 的已发布、已准入岗位', async ({ page }) => {
    await new StudentLoginPage(page, config.studentBaseUrl).login(config.student)
    await page.goto(`${config.studentBaseUrl}/internship/selection`)
    await expect(page.getByText(finalPositionTitle(), { exact: false }).first()).toBeVisible()
    await expect(page.getByText(companyName(), { exact: false }).first()).toBeVisible()
  })

  test('IX-003：企业拉黑后 Student PC 投影立即消失；黑名单岗位重新上架被后端拒绝', async ({ page }) => {
    await staffLogin(page)
    await page.goto(`${config.staffBaseUrl}/admin/internship/enterprises`)
    let row = companyRow(page, companyName())
    await expect(row).toBeVisible()
    await row.getByRole('button', { name: '拉黑', exact: true }).click()
    let dialog = page.getByRole('dialog')
    await dialog.locator('textarea').fill('IX003真实浏览器黑名单验证')
    await dialog.getByRole('button', { name: '确认拉黑', exact: true }).click()
    row = companyRow(page, companyName())
    await expect(row).toContainText('黑名单')

    await new StudentLoginPage(page, config.studentBaseUrl).login(config.student)
    await page.goto(`${config.studentBaseUrl}/internship/selection`)
    await expect(page.getByText(finalPositionTitle(), { exact: false })).toHaveCount(0)

    await staffLogin(page)
    await page.goto(`${config.staffBaseUrl}/admin/internship/positions/${positionId}`)
    let result = await confirmStatusAction(page, positionId, '下架', '确认下架')
    expect(result.body?.code, result.text).toBe(0)

    result = await confirmStatusAction(page, positionId, '上架', '确认上架')
    expect(result.body?.code, result.text).not.toBe(0)
    expect(String(result.body?.message || result.text)).toMatch(/黑名单|合作状态|准入/)
  })

  test('IX-003/005：移出黑名单后恢复上架，并真实完成风险、暂停/恢复状态机', async ({ page }) => {
    await staffLogin(page)
    await page.goto(`${config.staffBaseUrl}/admin/internship/enterprises`)
    let row = companyRow(page, companyName())
    await row.getByRole('button', { name: '移出黑名单', exact: true }).click()
    let dialog = page.getByRole('dialog')
    await dialog.getByRole('button', { name: '确认移出', exact: true }).click()
    row = companyRow(page, companyName())
    await expect(row).toContainText('合作中')

    await page.goto(`${config.staffBaseUrl}/admin/internship/positions/${positionId}`)
    let result = await confirmStatusAction(page, positionId, '上架', '确认上架')
    expect(result.body?.code, result.text).toBe(0)

    await page.getByRole('button', { name: '标记风险', exact: true }).click()
    dialog = page.getByRole('dialog')
    await dialog.locator('textarea').fill('IX005真实浏览器风险标记验证')
    const riskOnPromise = page.waitForResponse((response) =>
      apiPath(response) === `/api/v1/internship/positions/${positionId}/risk`
        && response.request().method() === 'POST'
    )
    await dialog.getByRole('button', { name: '确认标记', exact: true }).click()
    let riskResponse = await riskOnPromise
    let riskPayload = await payloadOf(riskResponse)
    expect(riskPayload.body?.code, riskPayload.text).toBe(0)
    await expect(page.getByRole('button', { name: '解除风险', exact: true })).toBeVisible()

    await page.getByRole('button', { name: '解除风险', exact: true }).click()
    dialog = page.getByRole('dialog')
    const riskOffPromise = page.waitForResponse((response) =>
      apiPath(response) === `/api/v1/internship/positions/${positionId}/risk`
        && response.request().method() === 'POST'
    )
    await dialog.getByRole('button', { name: '确认解除', exact: true }).click()
    riskResponse = await riskOffPromise
    riskPayload = await payloadOf(riskResponse)
    expect(riskPayload.body?.code, riskPayload.text).toBe(0)

    result = await confirmStatusAction(page, positionId, '上架', '确认上架')
    expect(result.body?.code, result.text).toBe(0)
    result = await confirmStatusAction(page, positionId, '暂停', '确认暂停')
    expect(result.body?.code, result.text).toBe(0)
    result = await confirmStatusAction(page, positionId, '上架', '确认上架')
    expect(result.body?.code, result.text).toBe(0)

    execFileSync('python', ['../backend/scripts/e2e_verify_internship_enterprise_position_db.py'], {
      cwd: process.cwd(),
      env: {
        ...process.env,
        E2E_IX003_COMPANY_ID: companyId,
        E2E_IX005_POSITION_ID: positionId,
        E2E_IX005_CAMPAIGN_ID: fixture.campaignId,
        E2E_IX005_BATCH_ID: fixture.batchId,
        E2E_IX005_INTERNSHIP_ID: fixture.internshipId,
        E2E_IX005_POSITION_TITLE: finalPositionTitle()
      },
      stdio: 'inherit'
    })
  })
})
