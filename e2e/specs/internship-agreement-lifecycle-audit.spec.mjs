import { execFileSync } from 'node:child_process'
import fs from 'node:fs/promises'
import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { StaffLoginPage, StudentLoginPage } from '../pages/login.page.mjs'

const miniBaseUrl = process.env.E2E_STUDENT_MINI_BASE_URL || 'http://127.0.0.1:5188'
const REJECT_REASON = 'IX011学生核对后发现协议内容需学校重新发起'
const ENTERPRISE_SIGNER = 'IX011企业HR张老师'

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

async function staffLogin(page) {
  await new StaffLoginPage(page, config.staffBaseUrl).login(config.sandboxAdmin)
}

async function pickInternshipStudent(page, fixture) {
  const field = formItem(page, '实习学生')
  await field.locator('[role="combobox"]').click()
  const search = field.locator('.app-remote-select__search-el')
  await expect(search).toBeVisible()
  await search.fill(fixture.studentNo)
  const option = field.locator('.app-remote-select__option')
    .filter({ hasText: fixture.studentNo }).first()
  await expect(option).toBeVisible()
  await option.click()
}

async function loginMini(page, entry, account) {
  await page.goto(`${miniBaseUrl}/#/pages/login/${entry}/index`)
  const accountHint = entry === 'teacher' ? '工号 / 手机号' : '学号 / 手机号'
  const accountField = page.locator('uni-input.field').filter({ hasText: accountHint }).first()
  const passwordField = page.locator('uni-input.field').filter({ hasText: '密码' }).first()
  await accountField.locator('input').fill(account.username)
  await passwordField.locator('input').fill(account.password)
  await page.locator('.agreement__box').click()
  await page.locator('uni-button.account-button').click()
  await expect(page).toHaveURL(entry === 'teacher'
    ? /#\/pages\/teacher\/workbench\/index/
    : /#\/pages\/student\/home\/index/)

  if (entry === 'teacher') {
    // e2e_advisor_a is intentionally multi-role (GD_MENTOR + INTERN_MENTOR).
    // Browser First must follow the real role-switch UI instead of deep-linking an
    // internship page under the graduation-mentor context and weakening 403 guards.
    await page.goto(`${miniBaseUrl}/#/pages/role-switch/index`)
    const internshipRole = page.locator('.rs__item').filter({ hasText: '实习指导教师' }).first()
    await expect(internshipRole).toBeVisible()
    const switchPromise = page.waitForResponse((response) =>
      apiPath(response) === '/api/v1/auth/switch-role'
        && response.request().method() === 'POST'
    )
    await internshipRole.click()
    const switched = await switchPromise
    const switchPayload = await payloadOf(switched)
    expect(switchPayload.body?.code, switchPayload.text).toBe(0)
    await expect(page).toHaveURL(/#\/pages\/teacher\/workbench\/index/)
  }
}

async function openStudentAgreementTab(page) {
  await page.goto(`${config.studentBaseUrl}/internship`)
  await page.getByRole('button', { name: '三方协议', exact: true }).click()
  await expect(page.getByText('实习三方协议', { exact: false }).first()).toBeVisible()
}

async function generateAgreement(page, fixture) {
  await page.goto(`${config.staffBaseUrl}/admin/internship/agreements?batchId=${encodeURIComponent(fixture.batchId)}&panel=issue`)
  await page.getByRole('button', { name: '＋ 生成协议', exact: true }).click()
  await pickInternshipStudent(page, fixture)
  const templateField = formItem(page, '协议模板')
  await templateField.locator('select').selectOption({ label: fixture.templateName })
  await expect(page.getByText(fixture.studentName, { exact: false }).first()).toBeVisible()

  const createPromise = page.waitForResponse((response) =>
    apiPath(response) === '/api/v1/internship/agreements'
      && response.request().method() === 'POST'
  )
  await page.getByRole('button', { name: '生成', exact: true }).click()
  const created = await createPromise
  const createPayload = await payloadOf(created)
  expect(createPayload.body?.code, createPayload.text).toBe(0)
  const agreementId = String(createPayload.body?.data?.id || '')
  expect(agreementId).not.toBe('')
  const requestBody = created.request().postDataJSON()
  expect(String(requestBody?.internshipId || '')).toBe(String(fixture.internshipId))
  expect(String(requestBody?.templateId || '')).toBe(String(fixture.templateId))
  return agreementId
}

async function issueAgreement(page, fixture, agreementId) {
  await page.goto(`${config.staffBaseUrl}/admin/internship/agreements/${agreementId}?batchId=${encodeURIComponent(fixture.batchId)}`)
  await expect(page.getByText(fixture.templateName, { exact: false }).first()).toBeVisible()
  await expect(page.getByText('草稿', { exact: true }).first()).toBeVisible()
  const issuePromise = page.waitForResponse((response) =>
    apiPath(response) === `/api/v1/internship/agreements/${agreementId}/issue`
      && response.request().method() === 'POST'
  )
  await page.getByRole('button', { name: '下发给学生确认', exact: true }).click()
  const dialog = page.getByRole('dialog')
  await dialog.getByRole('button', { name: '下发', exact: true }).click()
  const issued = await issuePromise
  const issuedPayload = await payloadOf(issued)
  expect(issuedPayload.body?.code, issuedPayload.text).toBe(0)
  expect(Number.isInteger(Number(issued.request().postDataJSON()?.expectedVersion))).toBeTruthy()
  await expect(page.getByText('待学生确认', { exact: true }).first()).toBeVisible()
}

test.describe('岗位实习审计：IX-011 三方协议完整链', () => {
  test.describe.configure({ mode: 'serial', retries: 0 })

  let fixture
  let oldAgreementId = ''
  let newAgreementId = ''

  test.beforeAll(async () => {
    execFileSync('python', ['../backend/scripts/e2e_seed_internship_agreement_sandbox.py'], {
      cwd: process.cwd(), env: process.env, stdio: 'inherit'
    })
    fixture = JSON.parse(await fs.readFile('./runtime/internship-agreement-fixture.json', 'utf8'))
    expect(fixture.internshipId).toBeTruthy()
    expect(fixture.templateId).toBeTruthy()
  })

  test('IX-011：Staff PC 真实选择模板、生成协议并下发学生', async ({ page }) => {
    await staffLogin(page)
    oldAgreementId = await generateAgreement(page, fixture)
    await issueAgreement(page, fixture, oldAgreementId)
  })

  test('IX-011：Student PC 真实驳回；旧协议保留，学校重新生成新版本实例并下发', async ({ page }) => {
    await new StudentLoginPage(page, config.studentBaseUrl).login(config.student)
    await openStudentAgreementTab(page)
    await expect(page.getByText(fixture.companyName, { exact: false }).first()).toBeVisible()
    await expect(page.getByText(fixture.positionName, { exact: false }).first()).toBeVisible()

    page.once('dialog', async (dialog) => {
      expect(dialog.type()).toBe('prompt')
      await dialog.accept(REJECT_REASON)
    })
    const rejectPromise = page.waitForResponse((response) =>
      apiPath(response) === `/api/v1/portal/internship/context/agreements/${oldAgreementId}/confirm`
        && response.request().method() === 'POST'
    )
    await page.getByRole('button', { name: '驳回协议', exact: true }).click()
    const rejected = await rejectPromise
    const rejectBody = rejected.request().postDataJSON()
    expect(rejectBody?.action).toBe('REJECT')
    expect(rejectBody?.reason).toBe(REJECT_REASON)
    expect(Number.isInteger(Number(rejectBody?.expectedVersion))).toBeTruthy()
    const rejectedPayload = await payloadOf(rejected)
    expect(rejectedPayload.body?.code, rejectedPayload.text).toBe(0)
    await expect(page.getByText('已驳回', { exact: false }).first()).toBeVisible()

    await staffLogin(page)
    await page.goto(`${config.staffBaseUrl}/admin/internship/agreements/${oldAgreementId}?batchId=${encodeURIComponent(fixture.batchId)}`)
    await expect(page.getByText(REJECT_REASON, { exact: false }).first()).toBeVisible()
    await expect(page.getByText('已驳回', { exact: true }).first()).toBeVisible()

    newAgreementId = await generateAgreement(page, fixture)
    expect(newAgreementId).not.toBe(oldAgreementId)
    await issueAgreement(page, fixture, newAgreementId)
  })

  test('IX-011：Student Mini 与 Student PC 读取同一新协议；Student PC 真实确认进入企业签署', async ({ page }) => {
    await loginMini(page, 'student', config.student)
    await page.goto(`${miniBaseUrl}/#/pages/student/internship/agreement/index?id=${encodeURIComponent(newAgreementId)}`)
    await expect(page.getByText(fixture.companyName, { exact: false }).first()).toBeVisible()
    await expect(page.getByText(fixture.positionName, { exact: false }).first()).toBeVisible()
    await expect(page.getByText('待学生确认', { exact: false }).first()).toBeVisible()

    await new StudentLoginPage(page, config.studentBaseUrl).login(config.student)
    await openStudentAgreementTab(page)
    const confirmPromise = page.waitForResponse((response) =>
      apiPath(response) === `/api/v1/portal/internship/context/agreements/${newAgreementId}/confirm`
        && response.request().method() === 'POST'
    )
    await page.getByRole('button', { name: '确认协议', exact: true }).click()
    const confirmed = await confirmPromise
    const confirmBody = confirmed.request().postDataJSON()
    expect(confirmBody?.action).toBe('CONFIRM')
    expect(Number.isInteger(Number(confirmBody?.expectedVersion))).toBeTruthy()
    const confirmedPayload = await payloadOf(confirmed)
    expect(confirmedPayload.body?.code, confirmedPayload.text).toBe(0)
    await expect(page.getByText('待企业确认', { exact: false }).first()).toBeVisible()
  })

  test('IX-011：Staff 上传真实签署扫描件；Teacher Mini 只读跟进；SCHOOL_ADMIN 终审生效', async ({ page }) => {
    await staffLogin(page)
    await page.goto(`${config.staffBaseUrl}/admin/internship/agreements/${newAgreementId}?batchId=${encodeURIComponent(fixture.batchId)}`)
    await expect(page.getByText('待企业确认', { exact: true }).first()).toBeVisible()

    const uploadPromise = page.waitForResponse((response) =>
      apiPath(response) === '/api/v1/files' && response.request().method() === 'POST'
    )
    await page.locator('input[type="file"].agd-file').setInputFiles(fixture.scanPath)
    const uploaded = await uploadPromise
    const uploadedPayload = await payloadOf(uploaded)
    expect(uploadedPayload.body?.code, uploadedPayload.text).toBe(0)
    expect(String(uploadedPayload.body?.data?.fileId || '')).not.toBe('')
    await expect(page.getByText('已上传：', { exact: false }).first()).toBeVisible()
    await formItem(page, '企业经办人').locator('input').fill(ENTERPRISE_SIGNER)

    const enterprisePromise = page.waitForResponse((response) =>
      apiPath(response) === `/api/v1/internship/agreements/${newAgreementId}/enterprise-confirm`
        && response.request().method() === 'POST'
    )
    await page.getByRole('button', { name: '确认企业已签署', exact: true }).click()
    const enterpriseConfirmed = await enterprisePromise
    const enterpriseBody = enterpriseConfirmed.request().postDataJSON()
    expect(enterpriseBody?.confirmBy).toBe(ENTERPRISE_SIGNER)
    expect(String(enterpriseBody?.fileId || '')).not.toBe('')
    expect(Number.isInteger(Number(enterpriseBody?.expectedVersion))).toBeTruthy()
    const enterprisePayload = await payloadOf(enterpriseConfirmed)
    expect(enterprisePayload.body?.code, enterprisePayload.text).toBe(0)
    await expect(page.getByText('待学校确认', { exact: true }).first()).toBeVisible()

    await loginMini(page, 'teacher', config.mentor)
    await page.goto(`${miniBaseUrl}/#/pages/teacher/agreement-confirm/index`)
    await expect(page.getByText(fixture.studentName, { exact: false }).first()).toBeVisible()
    await expect(page.getByText(fixture.companyName, { exact: false }).first()).toBeVisible()
    await expect(page.getByText(fixture.positionName, { exact: false }).first()).toBeVisible()
    await expect(page.getByText('待学校终审', { exact: false }).first()).toBeVisible()
    await expect(page.getByText('已上传', { exact: true }).first()).toBeVisible()
    await expect(page.getByText('企业盖章材料', { exact: false }).first()).toBeVisible()
    await expect(page.getByText('本页用于教师跟进材料完整性，不执行学校终审。', { exact: false }).first()).toBeVisible()
    await expect(page.getByRole('button', { name: /确认生效|学校确认/ })).toHaveCount(0)

    await staffLogin(page)
    await page.goto(`${config.staffBaseUrl}/admin/internship/agreements/${newAgreementId}?batchId=${encodeURIComponent(fixture.batchId)}`)
    const schoolPromise = page.waitForResponse((response) =>
      apiPath(response) === `/api/v1/internship/agreements/${newAgreementId}/school-confirm`
        && response.request().method() === 'POST'
    )
    await page.getByRole('button', { name: '学校确认生效', exact: true }).click()
    const schoolDialog = page.getByRole('dialog')
    await schoolDialog.getByRole('button', { name: '确认生效', exact: true }).click()
    const schoolConfirmed = await schoolPromise
    expect(Number.isInteger(Number(schoolConfirmed.request().postDataJSON()?.expectedVersion))).toBeTruthy()
    const schoolPayload = await payloadOf(schoolConfirmed)
    expect(schoolPayload.body?.code, schoolPayload.text).toBe(0)
    await expect(page.getByText('已生效', { exact: true }).first()).toBeVisible()
  })

  test('IX-011：生效后 PC/Mini 同源、PDF 可生成、Staff 真实归档并完成只读 MySQL seal', async ({ page }) => {
    await new StudentLoginPage(page, config.studentBaseUrl).login(config.student)
    await openStudentAgreementTab(page)
    await expect(page.getByText('已生效', { exact: false }).first()).toBeVisible()
    await expect(page.getByText(fixture.companyName, { exact: false }).first()).toBeVisible()

    await loginMini(page, 'student', config.student)
    await page.goto(`${miniBaseUrl}/#/pages/student/internship/agreement/index?id=${encodeURIComponent(newAgreementId)}`)
    await expect(page.getByText('已生效', { exact: false }).first()).toBeVisible()
    await expect(page.getByText(fixture.companyName, { exact: false }).first()).toBeVisible()

    await staffLogin(page)
    await page.goto(`${config.staffBaseUrl}/admin/internship/agreements/${newAgreementId}?batchId=${encodeURIComponent(fixture.batchId)}`)
    const pdfPromise = page.waitForResponse((response) =>
      apiPath(response) === `/api/v1/internship/agreements/${newAgreementId}/pdf`
        && response.request().method() === 'POST'
    )
    await page.getByRole('button', { name: '下载 PDF 套打', exact: true }).click()
    const pdfResponse = await pdfPromise
    const pdfPayload = await payloadOf(pdfResponse)
    expect(pdfPayload.body?.code, pdfPayload.text).toBe(0)
    expect(pdfPayload.body?.data).toBeTruthy()

    const archivePromise = page.waitForResponse((response) =>
      apiPath(response) === `/api/v1/internship/agreements/${newAgreementId}/archive`
        && response.request().method() === 'POST'
    )
    await page.getByRole('button', { name: '归档', exact: true }).click()
    const archiveDialog = page.getByRole('dialog')
    await archiveDialog.getByRole('button', { name: '归档', exact: true }).click()
    const archived = await archivePromise
    expect(Number.isInteger(Number(archived.request().postDataJSON()?.expectedVersion))).toBeTruthy()
    const archivedPayload = await payloadOf(archived)
    expect(archivedPayload.body?.code, archivedPayload.text).toBe(0)
    await expect(page.getByText('已归档', { exact: true }).first()).toBeVisible()
    await expect(page.getByText('仅可查看与打印，不可再变更', { exact: false }).first()).toBeVisible()
    await expect(page.getByRole('button', { name: '学校确认生效', exact: true })).toHaveCount(0)
    await expect(page.getByRole('button', { name: '归档', exact: true })).toHaveCount(0)

    execFileSync('python', ['../backend/scripts/e2e_verify_internship_agreement_db.py'], {
      cwd: process.cwd(),
      env: {
        ...process.env,
        E2E_IX011_OLD_AGREEMENT_ID: oldAgreementId,
        E2E_IX011_NEW_AGREEMENT_ID: newAgreementId,
        E2E_IX011_INTERNSHIP_ID: fixture.internshipId,
        E2E_IX011_STUDENT_NAME: fixture.studentName,
        E2E_IX011_COMPANY_NAME: fixture.companyName,
        E2E_IX011_POSITION_NAME: fixture.positionName,
        E2E_IX011_REJECT_REASON: REJECT_REASON,
      },
      stdio: 'inherit'
    })
  })
})
