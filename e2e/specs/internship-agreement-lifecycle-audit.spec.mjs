import { execFileSync } from 'node:child_process'
import fs from 'node:fs/promises'
import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { StaffLoginPage, StudentLoginPage } from '../pages/login.page.mjs'
import { loginMiniH5 } from '../lib/miniapp-login.mjs'
import { submitInAppPrompt } from '../lib/in-app-dialog.mjs'

const miniBaseUrl = process.env.E2E_STUDENT_MINI_BASE_URL
  || process.env.E2E_MINIAPP_BASE_URL
  || 'http://127.0.0.1:5188'
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
  const login = new StaffLoginPage(page, config.staffBaseUrl)
  await login.login(config.sandboxAdmin)
  return login
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
  await loginMiniH5(page, { baseUrl: miniBaseUrl, entry, account })

  if (entry === 'teacher') {
    // e2e_advisor_a is intentionally multi-role (GD_MENTOR + INTERN_MENTOR).
    // Browser First must follow the real role-switch UI instead of deep-linking an
    // internship page under the graduation-mentor context and weakening 403 guards.
    await page.goto(`${miniBaseUrl}/#/pages/role-switch/index`)
    const internshipRole = page.locator('.rs__item').filter({ hasText: '实习指导教师' }).first()
    await expect(internshipRole).toBeVisible()
    const switchPromise = page.waitForResponse((response) =>
      apiPath(response) === '/api/v1/auth/browser-switch-role'
        && response.request().method() === 'POST'
    )
    await internshipRole.click()
    const switched = await switchPromise
    const switchPayload = await payloadOf(switched)
    expect(switchPayload.body?.code, switchPayload.text).toBe(0)
    await expect(page).toHaveURL(/#\/pages\/teacher\/workbench\/index/)
  }
}

async function openStudentAgreementTab(page, fixture) {
  await page.goto(`${config.studentBaseUrl}/internship`)
  await page.getByRole('button', { name: '三方协议', exact: true }).click()
  const selector = page.getByText('请选择要办理的实习批次', { exact: true })
  if (await selector.count()) {
    await expect(selector).toBeVisible()
    const exactBatch = page.getByRole('button').filter({ hasText: fixture.batchName }).first()
    await expect(exactBatch).toBeVisible()
    await exactBatch.click()
  }
  await expect(page.getByText('实习三方协议', { exact: false }).first()).toBeVisible()
}

async function openStudentInsuranceTab(page, fixture, navigate = true) {
  if (navigate) await page.goto(`${config.studentBaseUrl}/internship`)
  await page.getByRole('button', { name: '实习保险', exact: true }).click()
  const selector = page.getByText('请选择要办理的实习批次', { exact: true })
  if (await selector.count()) {
    await expect(selector).toBeVisible()
    const exactBatch = page.getByRole('button').filter({ hasText: fixture.batchName }).first()
    await expect(exactBatch).toBeVisible()
    await exactBatch.click()
  }
  await expect(page.getByText('提交保险信息', { exact: true })).toBeVisible()
}

async function isolatedInsuranceImage(page) {
  const dataUrl = await page.evaluate(() => {
    const canvas = document.createElement('canvas')
    canvas.width = 1000
    canvas.height = 500
    const ctx = canvas.getContext('2d')
    ctx.fillStyle = '#fff8f0'
    ctx.fillRect(0, 0, canvas.width, canvas.height)
    ctx.strokeStyle = '#bd2525'
    ctx.lineWidth = 12
    ctx.strokeRect(16, 16, canvas.width - 32, canvas.height - 32)
    ctx.textAlign = 'center'
    ctx.fillStyle = '#a11d1d'
    ctx.font = 'bold 76px Microsoft YaHei, sans-serif'
    ctx.fillText('隔离测试', canvas.width / 2, 190)
    ctx.font = 'bold 46px Microsoft YaHei, sans-serif'
    ctx.fillText('非真实保险凭证', canvas.width / 2, 275)
    ctx.fillStyle = '#333'
    ctx.font = '28px Microsoft YaHei, sans-serif'
    ctx.fillText('仅用于岗位实习浏览器流程验收，不代表真实保险保障', canvas.width / 2, 360)
    return canvas.toDataURL('image/png')
  })
  return Buffer.from(dataUrl.slice(dataUrl.indexOf(',') + 1), 'base64')
}

function crossCollegeReviewer() {
  return {
    tenant: 'sandbox-school',
    username: 'e2e_ix_college_b',
    password: process.env.E2E_IX_COLLEGE_B_PASSWORD || '',
  }
}

async function generateAgreement(page, fixture) {
  await page.goto(`${config.staffBaseUrl}/admin/internship/agreements?batchId=${encodeURIComponent(fixture.batchId)}&panel=issue`)
  await page.getByRole('button', { name: '生成协议', exact: true }).click()
  await pickInternshipStudent(page, fixture)
  const templateField = formItem(page, '协议模板')
  await templateField.locator('select').selectOption({ label: fixture.templateName })
  await expect(page.getByText(fixture.studentName, { exact: false }).first()).toBeVisible()

  const createPromise = page.waitForResponse((response) =>
    apiPath(response) === '/api/v1/internship/agreements'
      && response.request().method() === 'POST'
  )
  await page.getByRole('button', { name: '生成草稿', exact: true }).click()
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
    await openStudentAgreementTab(page, fixture)
    await expect(page.getByText(fixture.companyName, { exact: false }).first()).toBeVisible()
    await expect(page.getByText(fixture.positionName, { exact: false }).first()).toBeVisible()

    const rejectPromise = page.waitForResponse((response) =>
      apiPath(response) === `/api/v1/portal/internship/context/agreements/${oldAgreementId}/confirm`
        && response.request().method() === 'POST'
    )
    await page.getByRole('button', { name: '驳回协议', exact: true }).click()
    await submitInAppPrompt(page, REJECT_REASON, { confirmText: '确认驳回' })
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
    await page.goto(`${miniBaseUrl}/#/pages/student-internship/agreement/index?id=${encodeURIComponent(newAgreementId)}`)
    await expect(page.getByText(fixture.companyName, { exact: false }).first()).toBeVisible()
    await expect(page.getByText(fixture.positionName, { exact: false }).first()).toBeVisible()
    await expect(page.getByText('待学生确认', { exact: false }).first()).toBeVisible()

    await new StudentLoginPage(page, config.studentBaseUrl).login(config.student)
    await openStudentAgreementTab(page, fixture)
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
    await expect(page.locator('.agd-att')).toContainText('待确认登记')
    await expect(page.getByRole('button', { name: '确认企业已签署', exact: true })).toBeEnabled()
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
    await page.goto(`${miniBaseUrl}/#/pages/teacher-internship/agreement-confirm/index`)
    await page.getByText('切换批次', { exact: false }).click()
    await page.getByText(fixture.batchName, { exact: false }).last().click()
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
    await openStudentAgreementTab(page, fixture)
    await expect(page.getByText('已生效', { exact: false }).first()).toBeVisible()
    await expect(page.getByText(fixture.companyName, { exact: false }).first()).toBeVisible()

    await loginMini(page, 'student', config.student)
    await page.goto(`${miniBaseUrl}/#/pages/student-internship/agreement/index?id=${encodeURIComponent(newAgreementId)}`)
    await expect(page.getByText('已生效', { exact: false }).first()).toBeVisible()
    await expect(page.getByText(fixture.companyName, { exact: false }).first()).toBeVisible()

    await staffLogin(page)
    await page.goto(`${config.staffBaseUrl}/admin/internship/agreements/${newAgreementId}?batchId=${encodeURIComponent(fixture.batchId)}`)
    const pdfPromise = page.waitForResponse((response) =>
      apiPath(response) === `/api/v1/internship/agreements/${newAgreementId}/pdf`
        && response.request().method() === 'POST'
    )
    await page.getByRole('button', { name: '下载 PDF', exact: true }).click()
    const pdfResponse = await pdfPromise
    const pdfPayload = await payloadOf(pdfResponse)
    expect(pdfPayload.body?.code, pdfPayload.text).toBe(0)
    expect(pdfPayload.body?.data).toBeTruthy()

    const archivePromise = page.waitForResponse((response) =>
      apiPath(response) === `/api/v1/internship/agreements/${newAgreementId}/archive`
        && response.request().method() === 'POST'
    )
    await page.getByRole('button', { name: '归档协议', exact: true }).click()
    const archiveDialog = page.getByRole('dialog')
    await archiveDialog.getByRole('button', { name: '归档', exact: true }).click()
    const archived = await archivePromise
    expect(Number.isInteger(Number(archived.request().postDataJSON()?.expectedVersion))).toBeTruthy()
    const archivedPayload = await payloadOf(archived)
    expect(archivedPayload.body?.code, archivedPayload.text).toBe(0)
    await expect(page.getByText('已归档', { exact: true }).first()).toBeVisible()
    await expect(page.getByText('仅可查看与打印，不可再变更', { exact: false }).first()).toBeVisible()
    await expect(page.getByRole('button', { name: '学校确认生效', exact: true })).toHaveCount(0)
    await expect(page.getByRole('button', { name: '归档协议', exact: true })).toHaveCount(0)

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

  test('IX-011：学生提交隔离测试保险图、学校页面核验、学生刷新回读；跨学院详情拒绝', async ({ page }) => {
    const collegeB = crossCollegeReviewer()
    expect(collegeB.password, '隔离学院账号必须有可用的测试凭据').toBeTruthy()

    const policyNo = `IX011-隔离测试-非真实保单-${fixture.runId}`
    const imageName = `IX011-隔离测试-非真实保险凭证-${fixture.runId}.png`
    const insurerName = '隔离测试材料（非真实承保机构）'
    const coverageType = '隔离测试材料，不代表真实保障'

    await new StudentLoginPage(page, config.studentBaseUrl).login(config.student)
    await openStudentInsuranceTab(page, fixture)
    const dates = await page.evaluate(() => {
      const format = (value) => {
        const year = value.getFullYear()
        const month = String(value.getMonth() + 1).padStart(2, '0')
        const day = String(value.getDate()).padStart(2, '0')
        return `${year}-${month}-${day}`
      }
      const start = new Date()
      start.setDate(start.getDate() - 60)
      const end = new Date()
      end.setDate(end.getDate() + 180)
      return { effectiveDate: format(start), expiryDate: format(end) }
    })
    await page.getByLabel('保单号', { exact: true }).fill(policyNo)
    await page.getByLabel('承保机构', { exact: true }).fill(insurerName)
    await page.getByLabel('险种', { exact: true }).fill(coverageType)
    await page.getByLabel('生效日期', { exact: true }).fill(dates.effectiveDate)
    await page.getByLabel('到期日期', { exact: true }).fill(dates.expiryDate)

    const uploadPromise = page.waitForResponse((response) =>
      apiPath(response) === '/api/v1/files' && response.request().method() === 'POST'
    )
    await page.locator('input[type="file"]').setInputFiles({
      name: imageName,
      mimeType: 'image/png',
      buffer: await isolatedInsuranceImage(page),
    })
    const uploaded = await uploadPromise
    const uploadPayload = await payloadOf(uploaded)
    expect(uploadPayload.body?.code, uploadPayload.text).toBe(0)
    const fileId = String(uploadPayload.body?.data?.fileId || uploadPayload.body?.data?.id || '')
    expect(fileId).not.toBe('')
    await expect(page.locator('#student-workspace-main').getByText('保单文件已上传', { exact: true })).toBeVisible()

    const submitPromise = page.waitForResponse((response) =>
      apiPath(response) === '/api/v1/portal/internship/insurance'
        && response.request().method() === 'POST'
    )
    await page.getByRole('button', { name: '提交保险', exact: true }).click()
    const submitted = await submitPromise
    const submitPayload = await payloadOf(submitted)
    expect(submitPayload.body?.code, submitPayload.text).toBe(0)
    const submitBody = submitted.request().postDataJSON()
    expect(String(submitBody?.internshipId || '')).toBe(String(fixture.internshipId))
    expect(String(submitBody?.fileId || '')).toBe(fileId)
    expect(submitPayload.body?.data?.status).toBe('PENDING_VERIFY')
    expect(String(submitPayload.body?.data?.internshipId || '')).toBe(String(fixture.internshipId))
    const insuranceId = String(submitPayload.body?.data?.id || '')
    expect(insuranceId).not.toBe('')
    await expect(page.getByText(/状态：待核验/)).toBeVisible()
    await page.reload()
    await page.waitForLoadState('networkidle')
    await openStudentInsuranceTab(page, fixture, false)
    await expect(page.getByText(/状态：待核验/)).toBeVisible()
    await expect(page.getByText(policyNo, { exact: false })).toBeVisible()

    const schoolLogin = await staffLogin(page)
    const users = await page.request.get(`${config.apiBaseUrl}/system/users?keyword=e2e_ix_college_b&page=1&page_size=20`, {
      headers: { Authorization: `Bearer ${await schoolLogin.token()}` },
    })
    const userList = await payloadOf(users)
    expect(userList.body?.code, userList.text).toBe(0)
    const collegeBUser = (userList.body?.data?.list || []).find((item) => item.loginName === collegeB.username)
    expect(collegeBUser, '必须找到学院乙的独立测试账号').toBeTruthy()
    const account = await page.request.get(`${config.apiBaseUrl}/system/users/${collegeBUser.id}`, {
      headers: { Authorization: `Bearer ${await schoolLogin.token()}` },
    })
    const accountDetail = await payloadOf(account)
    expect(accountDetail.body?.code, accountDetail.text).toBe(0)
    const scopedRole = (accountDetail.body?.data?.roleAssignments || []).find((item) => item.roleCode === 'COLLEGE_ADMIN')
    expect(scopedRole?.scopeConfigured).toBe(true)
    expect(scopedRole?.scopeType).toBe('COLLEGE')
    expect(scopedRole?.scopeItems).toEqual([expect.objectContaining({ type: 'COLLEGE', name: 'E2E岗位实习测试信息工程学院' })])
    const studentResponse = await page.request.get(`${config.apiBaseUrl}/students/${fixture.studentId}`, {
      headers: { Authorization: `Bearer ${await schoolLogin.token()}` },
    })
    const studentDetail = await payloadOf(studentResponse)
    expect(studentDetail.body?.code, studentDetail.text).toBe(0)
    expect(studentDetail.body?.data?.collegeName).toBeTruthy()
    expect(studentDetail.body?.data?.collegeName).not.toBe('E2E岗位实习测试信息工程学院')
    await page.goto(`${config.staffBaseUrl}/admin/internship/insurance/${insuranceId}?batchId=${encodeURIComponent(fixture.batchId)}`)
    await expect(page.getByText(fixture.studentName, { exact: false }).first()).toBeVisible()
    await expect(page.getByText(policyNo, { exact: false }).first()).toBeVisible()
    await expect(page.getByText(insurerName, { exact: false }).first()).toBeVisible()
    await expect(page.getByText(imageName, { exact: false })).toBeVisible()
    await expect(page.getByRole('button', { name: '核验通过', exact: true })).toBeEnabled()
    await page.getByRole('button', { name: '预览', exact: true }).click()
    await expect(page.locator('.file-previewer__viewer img')).toHaveAttribute('alt', imageName)

    const verifyPromise = page.waitForResponse((response) =>
      apiPath(response) === `/api/v1/internship/insurances/${insuranceId}/verify`
        && response.request().method() === 'POST'
    )
    await page.getByRole('button', { name: '核验通过', exact: true }).click()
    await page.getByRole('dialog').getByRole('button', { name: '确认通过', exact: true }).click()
    const verified = await verifyPromise
    const verifyPayload = await payloadOf(verified)
    expect(verifyPayload.body?.code, verifyPayload.text).toBe(0)
    expect(verifyPayload.body?.data?.status).toBe('VERIFIED')
    await expect(page.getByText('已通过', { exact: true }).first()).toBeVisible()

    await new StudentLoginPage(page, config.studentBaseUrl).login(config.student)
    await openStudentInsuranceTab(page, fixture)
    await expect(page.getByText(/状态：已核验/)).toBeVisible()
    await expect(page.getByText(policyNo, { exact: false })).toBeVisible()
    await page.reload()
    await page.waitForLoadState('networkidle')
    await openStudentInsuranceTab(page, fixture, false)
    await expect(page.getByText(/状态：已核验/)).toBeVisible()

    await new StaffLoginPage(page, config.staffBaseUrl).login(collegeB)
    const deniedPromise = page.waitForResponse((response) =>
      apiPath(response) === `/api/v1/internship/insurances/${insuranceId}`
        && response.request().method() === 'GET'
    )
    await page.goto(`${config.staffBaseUrl}/admin/internship/insurance/${insuranceId}?batchId=${encodeURIComponent(fixture.batchId)}`)
    const denied = await deniedPromise
    const deniedPayload = await payloadOf(denied)
    expect([403, 404]).toContain(denied.status())
    expect(deniedPayload.body?.code).not.toBe(0)
    await expect(page.getByText(/查看范围|无权|权限|不存在/).first()).toBeVisible()
  })
})
