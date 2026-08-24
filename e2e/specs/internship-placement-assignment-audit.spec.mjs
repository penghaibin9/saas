import { execFileSync } from 'node:child_process'
import fs from 'node:fs/promises'
import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { StaffLoginPage, StudentLoginPage } from '../pages/login.page.mjs'

const enterpriseBaseUrl = process.env.E2E_ENTERPRISE_BASE_URL || 'http://127.0.0.1:5202/enterprise'
const miniBaseUrl = process.env.E2E_STUDENT_MINI_BASE_URL || 'http://127.0.0.1:5188'
const ENTERPRISE_PASSWORD = 'E2eEnterprise@2026'
const ADVISOR_NAME = 'E2E指导教师A'

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

async function pickRemote(field, searchText, optionText) {
  await field.locator('[role="combobox"]').click()
  const search = field.locator('.app-remote-select__search-el')
  await expect(search).toBeVisible()
  await search.fill(searchText)
  const option = field.locator('.app-remote-select__option').filter({ hasText: optionText }).first()
  await expect(option).toBeVisible()
  await option.click()
}

async function confirmPositionStatus(page, positionId, triggerName, confirmName) {
  await page.getByRole('button', { name: triggerName, exact: true }).click()
  const dialog = page.getByRole('dialog')
  await expect(dialog).toBeVisible()
  const responsePromise = page.waitForResponse((response) =>
    apiPath(response) === `/api/v1/internship/positions/${positionId}/status`
      && response.request().method() === 'POST'
  )
  await dialog.getByRole('button', { name: confirmName, exact: true }).click()
  const response = await responsePromise
  return { response, ...(await payloadOf(response)) }
}

async function loginStudentMini(page) {
  await page.goto(`${miniBaseUrl}/#/pages/login/student/index`)
  // Uni H5 renders the visible placeholder in a sibling div, not as a native input
  // placeholder attribute. Drive the same visible fields a student sees instead of
  // assuming MP-WEIXIN template attributes survive the H5 renderer.
  const accountField = page.locator('uni-input.field').filter({ hasText: '学号 / 手机号' }).first()
  const passwordField = page.locator('uni-input.field').filter({ hasText: '密码' }).first()
  await accountField.locator('input').fill(config.student.username)
  await passwordField.locator('input').fill(config.student.password)
  await page.locator('.agreement__box').click()
  await page.locator('uni-button.account-button').click()
  await expect(page).toHaveURL(/#\/pages\/student\/home\/index/)
}

test.describe('岗位实习审计：IX-009 岗位匹配、正式落岗与指导教师分配', () => {
  test.describe.configure({ mode: 'serial', retries: 0 })

  let fixture
  let companyId = ''
  let positionId = ''
  let matchId = ''
  let applicationId = ''
  let enterpriseLogin = ''
  let enterprisePhone = ''

  test.beforeAll(async () => {
    execFileSync('python', ['../backend/scripts/e2e_seed_internship_enterprise_position_sandbox.py'], {
      cwd: process.cwd(), env: process.env, stdio: 'inherit'
    })
    fixture = JSON.parse(await fs.readFile('./runtime/internship-enterprise-position-fixture.json', 'utf8'))
    expect(fixture.initialStatus).toBe('PREPARING')
    expect(fixture.initialDestinationType).toBe('NONE')
    expect(fixture.participantStatus).toBe('ACTIVE')
    enterpriseLogin = `ix09_${fixture.runId}`
    const digits = String(fixture.runId).replace(/\D/g, '').slice(-8).padStart(8, '0')
    enterprisePhone = `137${digits}`
  })

  const companyName = () => `IX009跃科落岗企业${fixture.runId}`
  const creditCode = () => `P${String(fixture.runId).replace(/[^0-9A-Za-z]/g, '').slice(-17)}`
  const positionTitle = () => `IX009正式落岗测试岗${fixture.runId}`

  test('IX-009 前置：学校浏览器创建并准入企业，企业真实加入当前招聘季', async ({ page }) => {
    await staffLogin(page)
    await page.goto(`${config.staffBaseUrl}/admin/internship/enterprises`)
    await page.getByRole('button', { name: '＋ 新增企业', exact: true }).click()
    await formItem(page, '企业名称').locator('input').fill(companyName())
    await formItem(page, '统一社会信用代码').locator('input').fill(creditCode())
    await formItem(page, '联系人').locator('input').fill('IX009企业联系人')
    await formItem(page, '联系电话').locator('input').fill(enterprisePhone)

    const createPromise = page.waitForResponse((response) =>
      apiPath(response) === '/api/v1/internship/enterprises' && response.request().method() === 'POST'
    )
    await page.getByRole('button', { name: '创建企业', exact: true }).click()
    const created = await createPromise
    const createdPayload = await payloadOf(created)
    expect(createdPayload.body?.code, createdPayload.text).toBe(0)
    companyId = String(createdPayload.body?.data?.id || '')
    expect(companyId).not.toBe('')

    let row = companyRow(page, companyName())
    await expect(row).toBeVisible()
    await row.getByRole('button', { name: '审核通过', exact: true }).click()
    let dialog = page.getByRole('dialog')
    await dialog.getByRole('button', { name: '通过（资质合格）', exact: true }).click()
    row = companyRow(page, companyName())
    await expect(row).toContainText('合作中')

    await page.goto(`${config.staffBaseUrl}/admin/internship/recruitment-campaigns/${fixture.campaignId}`)
    await page.getByRole('button', { name: '邀请企业', exact: true }).click()
    await formItem(page, '选择企业').locator('select').selectOption({ label: companyName() })
    await formItem(page, '联系人姓名').locator('input').fill('IX009企业管理员')
    await formItem(page, '登录账号').locator('input').fill(enterpriseLogin)
    await formItem(page, '联系人手机号').locator('input').fill(enterprisePhone)
    const invitePromise = page.waitForResponse((response) =>
      apiPath(response) === `/api/v1/internship/recruitment-campaigns/${fixture.campaignId}/enterprises/invite`
        && response.request().method() === 'POST'
    )
    await page.getByRole('button', { name: '生成邀请', exact: true }).click()
    const invitedPayload = await payloadOf(await invitePromise)
    expect(invitedPayload.body?.code, invitedPayload.text).toBe(0)
    const inviteToken = String(invitedPayload.body?.data?.inviteToken || '')
    expect(inviteToken).not.toBe('')

    await page.goto(`${enterpriseBaseUrl}/invite/accept?token=${encodeURIComponent(inviteToken)}&tenantCode=${encodeURIComponent(fixture.tenantCode)}`)
    await page.getByLabel('验证受邀手机号').fill(enterprisePhone)
    await page.getByLabel(/设置密码/).fill(ENTERPRISE_PASSWORD)
    await page.getByRole('button', { name: '接受邀请并进入企业协同中心', exact: true }).click()
    await expect(page).toHaveURL(/\/enterprise\/home/)
  })

  test('IX-009 前置：企业浏览器报送合规岗位，学校浏览器发布', async ({ page }) => {
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
    await page.getByLabel(/岗位名称/).fill(positionTitle())
    await page.getByLabel(/招聘人数/).fill('2')
    await page.getByLabel(/详细工作地址/).fill('湖南省长沙市岳麓区IX009测试园区9号')
    await page.getByLabel(/工作内容/).fill('生产级软件测试、缺陷复现、质量记录与回归验证')
    await page.getByLabel(/每日工时/).fill('8')
    await page.getByLabel(/每周工时/).fill('40')
    await page.getByLabel(/每周休息天数/).fill('2')
    await page.getByLabel(/报酬金额/).fill('4300')
    await page.getByLabel(/薪资展示/).fill('4300元/月')
    await page.getByRole('button', { name: /选择省.*市.*区县/ }).click()
    await page.getByRole('textbox', { name: '搜索省、市或区县' }).fill('岳麓区')
    await page.locator('.region-picker__results button').filter({ hasText: '岳麓区' }).first().click()

    const createPromise = page.waitForResponse((response) =>
      apiPath(response) === '/api/v1/internship/enterprise-portal/positions'
        && response.request().method() === 'POST'
    )
    await page.getByRole('button', { name: '提交学校审核', exact: true }).click()
    const createdPayload = await payloadOf(await createPromise)
    expect(createdPayload.body?.code, createdPayload.text).toBe(0)
    positionId = String(createdPayload.body?.data?.id || '')
    expect(positionId).not.toBe('')
    expect(String(createdPayload.body?.data?.campaignId || '')).toBe(String(fixture.campaignId))

    await staffLogin(page)
    await page.goto(`${config.staffBaseUrl}/admin/internship/positions/${positionId}`)
    await expect(page.getByText(positionTitle(), { exact: false }).first()).toBeVisible()
    const published = await confirmPositionStatus(page, positionId, '上架', '确认上架')
    expect(published.body?.code, published.text).toBe(0)
  })

  test('IX-009：Student PC 真实加入志愿并整组投递 canonical application', async ({ page }) => {
    await new StudentLoginPage(page, config.studentBaseUrl).login(config.student)
    await page.goto(`${config.studentBaseUrl}/internship/selection`)
    await expect(page.getByText(positionTitle(), { exact: false }).first()).toBeVisible()

    const savePromise = page.waitForResponse((response) =>
      apiPath(response) === '/api/v1/portal/internship/context/volunteers'
        && response.request().method() === 'PUT'
    )
    await page.getByRole('button', { name: '加入志愿', exact: true }).click()
    const savedPayload = await payloadOf(await savePromise)
    expect(savedPayload.body?.code, savedPayload.text).toBe(0)

    await page.getByRole('button', { name: '准备整组投递', exact: true }).click()
    const confirmBox = page.locator('.confirm-box')
    await expect(confirmBox).toBeVisible()
    await confirmBox.getByRole('checkbox').check()

    const submitPromise = page.waitForResponse((response) =>
      apiPath(response) === '/api/v1/portal/internship/context/volunteers/submit'
        && response.request().method() === 'POST'
    )
    await confirmBox.getByRole('button', { name: '确认整组投递', exact: true }).click()
    const submitted = await submitPromise
    const submitBody = submitted.request().postDataJSON()
    expect(Number.isInteger(Number(submitBody?.expectedGroupVersion))).toBeTruthy()
    expect(Number.isInteger(Number(submitBody?.expectedProfileVersion))).toBeTruthy()
    expect(String(submitBody?.consentPolicyVersion || '')).not.toBe('')
    expect(String(submitBody?.confirmMaterialPreviewHash || '')).toMatch(/^sha256:/)
    const submittedPayload = await payloadOf(submitted)
    expect(submittedPayload.body?.code, submittedPayload.text).toBe(0)
    applicationId = String(submittedPayload.body?.data?.items?.[0]?.id || '')
    expect(applicationId).not.toBe('')
  })

  test('IX-009：Staff 真实手动匹配并确认，必须进入 canonical assign_position_in_tx', async ({ page }) => {
    await staffLogin(page)
    await page.goto(`${config.staffBaseUrl}/admin/internship/match?batchId=${encodeURIComponent(fixture.batchId)}&panel=manual`)
    await page.getByRole('button', { name: /手动匹配/ }).click()

    const studentField = page.locator('.ie-fld').filter({ hasText: '实习学生' }).first()
    await pickRemote(studentField, fixture.studentNo, fixture.studentName)
    const positionField = page.locator('.ie-fld').filter({ hasText: '上架岗位' }).first()
    await pickRemote(positionField, positionTitle(), positionTitle())

    const manualPromise = page.waitForResponse((response) =>
      apiPath(response) === '/api/v1/internship/match/manual'
        && response.request().method() === 'POST'
    )
    await page.getByRole('button', { name: '确认', exact: true }).click()
    const manualPayload = await payloadOf(await manualPromise)
    expect(manualPayload.body?.code, manualPayload.text).toBe(0)
    matchId = String(manualPayload.body?.data?.id || '')
    expect(matchId).not.toBe('')

    await page.goto(`${config.staffBaseUrl}/admin/internship/match?batchId=${encodeURIComponent(fixture.batchId)}&panel=confirm`)
    const row = page.locator('tbody tr').filter({ hasText: fixture.studentName }).filter({ hasText: positionTitle() }).first()
    await expect(row).toBeVisible()
    await row.getByRole('button', { name: '确认落岗', exact: true }).click()
    const dialog = page.getByRole('dialog')
    await expect(dialog).toContainText('确认匹配并落岗')

    const confirmPromise = page.waitForResponse((response) =>
      apiPath(response) === `/api/v1/internship/match/${matchId}/confirm`
        && response.request().method() === 'POST'
    )
    await dialog.getByRole('button', { name: '确认落岗', exact: true }).click()
    const confirmed = await confirmPromise
    const confirmBody = confirmed.request().postDataJSON()
    expect(Number.isInteger(Number(confirmBody?.expectedVersion))).toBeTruthy()
    expect(Number.isInteger(Number(confirmBody?.recordExpectedVersion))).toBeTruthy()
    const confirmedPayload = await payloadOf(confirmed)
    expect(confirmedPayload.body?.code, confirmedPayload.text).toBe(0)
    expect(confirmedPayload.body?.data?.status).toBe('CONFIRMED')
  })

  test('IX-009：Staff 浏览器分配校内指导教师，Student PC 立即看到岗位/企业/导师', async ({ page }) => {
    await staffLogin(page)
    await page.goto(`${config.staffBaseUrl}/admin/internship/students?batchId=${encodeURIComponent(fixture.batchId)}`)
    const row = page.locator('tbody tr').filter({ hasText: fixture.studentName }).first()
    await expect(row).toContainText(positionTitle())
    await row.getByRole('button', { name: '分配指导老师', exact: true }).click()

    const advisorField = page.locator('.ie-fld').filter({ hasText: '校内指导教师' }).first()
    await pickRemote(advisorField, 'e2e_advisor_a', ADVISOR_NAME)
    await page.getByPlaceholder('例如：按专业方向调整指导关系').fill('IX009真实浏览器指导关系分配')

    const advisorPromise = page.waitForResponse((response) =>
      apiPath(response) === `/api/v1/internship/intern-students/${fixture.internshipId}/advisor`
        && response.request().method() === 'POST'
    )
    await page.getByRole('button', { name: '确认分配', exact: true }).click()
    const advisorPayload = await payloadOf(await advisorPromise)
    expect(advisorPayload.body?.code, advisorPayload.text).toBe(0)
    expect(advisorPayload.body?.data?.advisorName).toBe(ADVISOR_NAME)

    await new StudentLoginPage(page, config.studentBaseUrl).login(config.student)
    await page.goto(`${config.studentBaseUrl}/internship`)
    await expect(page.getByText(companyName(), { exact: false }).first()).toBeVisible()
    await expect(page.getByText(positionTitle(), { exact: false }).first()).toBeVisible()
    await expect(page.getByText(ADVISOR_NAME, { exact: false }).first()).toBeVisible()
  })

  test('IX-009：Student Mini 读取同一 server truth；落岗后企业拉黑不得抹掉历史 placement', async ({ page }) => {
    await loginStudentMini(page)
    await page.goto(`${miniBaseUrl}/#/pages/student/internship/index?batchId=${encodeURIComponent(fixture.batchId)}`)
    await expect(page.getByText(positionTitle(), { exact: false }).first()).toBeVisible()
    await expect(page.getByText(companyName(), { exact: false }).first()).toBeVisible()
    await expect(page.getByText(`校内导师 ${ADVISOR_NAME}`, { exact: false }).first()).toBeVisible()

    await staffLogin(page)
    await page.goto(`${config.staffBaseUrl}/admin/internship/enterprises`)
    let row = companyRow(page, companyName())
    await row.getByRole('button', { name: '拉黑', exact: true }).click()
    let dialog = page.getByRole('dialog')
    await dialog.locator('textarea').fill('IX009落岗后历史保留验证')
    await dialog.getByRole('button', { name: '确认拉黑', exact: true }).click()
    row = companyRow(page, companyName())
    await expect(row).toContainText('黑名单')

    await new StudentLoginPage(page, config.studentBaseUrl).login(config.student)
    await page.goto(`${config.studentBaseUrl}/internship/selection`)
    await expect(page.getByText(positionTitle(), { exact: false })).toHaveCount(0)
    await page.goto(`${config.studentBaseUrl}/internship`)
    await expect(page.getByText(positionTitle(), { exact: false }).first()).toBeVisible()
    await expect(page.getByText(companyName(), { exact: false }).first()).toBeVisible()
    await expect(page.getByText(ADVISOR_NAME, { exact: false }).first()).toBeVisible()

    await page.goto(`${miniBaseUrl}/#/pages/student/internship/index?batchId=${encodeURIComponent(fixture.batchId)}`)
    await expect(page.getByText(positionTitle(), { exact: false }).first()).toBeVisible()
    await expect(page.getByText(companyName(), { exact: false }).first()).toBeVisible()
    await expect(page.getByText(`校内导师 ${ADVISOR_NAME}`, { exact: false }).first()).toBeVisible()

    execFileSync('python', ['../backend/scripts/e2e_verify_internship_placement_db.py'], {
      cwd: process.cwd(),
      env: {
        ...process.env,
        E2E_IX009_COMPANY_ID: companyId,
        E2E_IX009_POSITION_ID: positionId,
        E2E_IX009_MATCH_ID: matchId,
        E2E_IX009_APPLICATION_ID: applicationId,
        E2E_IX009_INTERNSHIP_ID: fixture.internshipId,
        E2E_IX009_BATCH_ID: fixture.batchId,
        E2E_IX009_CAMPAIGN_ID: fixture.campaignId,
        E2E_IX009_ADVISOR_NAME: ADVISOR_NAME,
        E2E_IX009_POSITION_TITLE: positionTitle(),
        E2E_IX009_COMPANY_NAME: companyName()
      },
      stdio: 'inherit'
    })
  })
})
