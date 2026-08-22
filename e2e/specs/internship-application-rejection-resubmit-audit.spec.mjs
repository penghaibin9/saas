import fs from 'node:fs/promises'
import { execFileSync } from 'node:child_process'
import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { StaffLoginPage, StudentLoginPage } from '../pages/login.page.mjs'
import {
  StaffInternshipApplicationPage,
  StudentInternshipApplicationPage
} from '../pages/internship-application.page.mjs'

const PREFIX = 'E2E-AUDIT-20260823'
const APPLICATION_STUDENT = {
  tenant: 'sandbox-school', username: 'E2E20260002', password: 'E2eTest@2026'
}

function apiPath(response) {
  try { return new URL(response.url()).pathname } catch { return '' }
}

async function responseBody(response) {
  const text = await response.text()
  try { return { text, body: JSON.parse(text) } } catch { return { text, body: null } }
}

test.describe('岗位实习审计：自主实习真实文件—驳回—反馈—整改重交—落实去向', () => {
  test.describe.configure({ mode: 'serial', retries: 0 })

  let fixture
  let appId = ''
  let firstFileId = ''
  let finalFileId = ''
  const companyName = `${PREFIX}-自主实习企业`
  const firstPosition = `${PREFIX}-测试实习生`
  const finalPosition = `${PREFIX}-质量测试实习生`
  const firstNote = `${PREFIX}-自主实习申请-初次提交`
  const resubmitNote = `${PREFIX}-自主实习申请-整改重交`
  const rejectReason = `${PREFIX}-驳回-请补充岗位职责并更新证明材料`

  test.beforeAll(async () => {
    execFileSync('python', ['../backend/scripts/e2e_seed_internship_application_sandbox.py'], {
      cwd: process.cwd(), env: process.env, stdio: 'inherit'
    })
    fixture = JSON.parse(await fs.readFile('./runtime/internship-application-fixture.json', 'utf8'))
    expect(fixture.initialStatus).toBe('PREPARING')
    expect(fixture.initialDestinationType).toBe('NONE')
  })

  test('学生从真实 PC 上传 PDF 并提交自主实习申请，刷新后仍存在', async ({ page }) => {
    await new StudentLoginPage(page, config.studentBaseUrl).login(APPLICATION_STUDENT)
    const application = new StudentInternshipApplicationPage(page, config.studentBaseUrl, fixture)
    await application.open()
    const submitted = await application.submitSelfArranged({
      companyName,
      positionName: firstPosition,
      workAddress: '湖南省长沙市岳麓区测试产业园 18 号',
      contactName: 'E2E企业联系人',
      contactPhone: '13800138002',
      note: firstNote,
      fileName: `${PREFIX}-自主实习接收函-v1.pdf`
    })
    appId = submitted.appId
    firstFileId = submitted.fileId
    expect(appId).not.toBe('')
    expect(firstFileId).not.toBe('')

    await page.reload()
    await expect(page.getByRole('button', { name: '正式申请' })).toBeVisible()
    await page.getByRole('button', { name: '正式申请' }).click()
    await expect(page.getByText(firstNote, { exact: false }).first()).toBeVisible()
    await expect(page.getByText(/待审核|PENDING_REVIEW/).first()).toBeVisible()
  })

  test('Tenant B 通过真实后台页面直接打开 Tenant A application id 仍无法读取', async ({ page }) => {
    expect(appId).not.toBe('')
    await new StaffLoginPage(page, config.staffBaseUrl).login(config.demoAdmin)
    const detailPath = `/api/v1/internship/applications/${appId}`
    const responsePromise = page.waitForResponse((response) =>
      apiPath(response) === detailPath && response.request().method() === 'GET'
    ).catch(() => null)
    const query = new URLSearchParams({
      batchId: fixture.batchId, type: 'SELF_ARRANGED', status: 'ALL', id: appId
    })
    await page.goto(`${config.staffBaseUrl}/admin/internship/applications?${query}`)
    const response = await responsePromise
    if (response) {
      const { text, body } = await responseBody(response)
      const leaked = response.ok() && body?.code === 0 && String(body?.data?.id || '') === appId
      expect(leaked, `跨租户申请详情泄漏: ${text.slice(0, 800)}`).toBeFalsy()
    }
    await expect(page.getByText(firstNote, { exact: false })).toHaveCount(0)
  })

  test('实习导师打开申请、真实下载证明材料后驳回', async ({ page }) => {
    expect(appId).not.toBe('')
    const login = new StaffLoginPage(page, config.staffBaseUrl)
    await login.login(config.mentor)
    await login.switchRole(/实习指导教师|实习导师|INTERN_MENTOR/)
    await expect.poll(() => login.currentRoleText()).toMatch(/实习指导教师|实习导师|INTERN_MENTOR/)

    const application = new StaffInternshipApplicationPage(page, config.staffBaseUrl, fixture)
    const detail = await application.openApplication(appId)
    expect(detail.status).toBe('PENDING_REVIEW')
    expect(String(detail.evidenceFileId || '')).toBe(firstFileId)
    await application.downloadEvidence(firstFileId)
    await application.reject(appId, rejectReason)
  })

  test('学生重新登录刷新后看到驳回原因，更新内容和 PDF 后整改重交', async ({ page }) => {
    await new StudentLoginPage(page, config.studentBaseUrl).login(APPLICATION_STUDENT)
    const application = new StudentInternshipApplicationPage(page, config.studentBaseUrl, fixture)
    await application.expectRejectedFeedback(firstNote, rejectReason)

    const resubmitted = await application.submitSelfArranged({
      companyName,
      positionName: finalPosition,
      workAddress: '湖南省长沙市岳麓区测试产业园 18 号 A 座 5 层',
      contactName: 'E2E企业联系人',
      contactPhone: '13800138002',
      note: resubmitNote,
      fileName: `${PREFIX}-自主实习接收函-v2.pdf`
    })
    expect(resubmitted.appId).toBe(appId)
    finalFileId = resubmitted.fileId
    expect(finalFileId).not.toBe(firstFileId)
  })

  test('实习导师核验整改后的新证明材料并通过，真实落实自主实习去向', async ({ page }) => {
    expect(finalFileId).not.toBe('')
    const login = new StaffLoginPage(page, config.staffBaseUrl)
    await login.login(config.mentor)
    await login.switchRole(/实习指导教师|实习导师|INTERN_MENTOR/)
    await expect.poll(() => login.currentRoleText()).toMatch(/实习指导教师|实习导师|INTERN_MENTOR/)

    const application = new StaffInternshipApplicationPage(page, config.staffBaseUrl, fixture)
    const detail = await application.openApplication(appId)
    expect(detail.positionName).toBe(finalPosition)
    expect(String(detail.evidenceFileId || '')).toBe(finalFileId)
    await application.downloadEvidence(finalFileId)
    await application.approve(appId)
  })

  test('学生重新登录后看到真实落地的企业和岗位，不依赖本地状态', async ({ page }) => {
    await new StudentLoginPage(page, config.studentBaseUrl).login(APPLICATION_STUDENT)
    const application = new StudentInternshipApplicationPage(page, config.studentBaseUrl, fixture)
    await application.expectApprovedAndLanded({ companyName, positionName: finalPosition })
    await page.reload()
    await expect(page.getByText(companyName, { exact: false }).first()).toBeVisible()
    await expect(page.getByText(finalPosition, { exact: false }).first()).toBeVisible()
  })

  test('学校管理员核验审批审计后，只读 MySQL 检查申请、去向、文件绑定和版本历史', async ({ page }) => {
    await new StaffLoginPage(page, config.staffBaseUrl).login(config.sandboxAdmin)
    const application = new StaffInternshipApplicationPage(page, config.staffBaseUrl, fixture)
    const detail = await application.openFinal(appId)
    expect(detail.status).toBe('APPROVED')
    expect(detail.companyName).toBe(companyName)
    expect(detail.positionName).toBe(finalPosition)
    const actions = (detail.auditTrail || []).map((item) => item.action)
    expect(actions).toEqual(expect.arrayContaining(['SAVE_DRAFT', 'SUBMIT', 'REJECT', 'APPROVE']))
    expect(actions.filter((action) => action === 'SAVE_DRAFT').length).toBeGreaterThanOrEqual(2)
    expect(actions.filter((action) => action === 'SUBMIT').length).toBeGreaterThanOrEqual(2)

    execFileSync('python', ['../backend/scripts/e2e_verify_internship_application_db.py'], {
      cwd: process.cwd(),
      env: {
        ...process.env,
        E2E_INTERNSHIP_APPLICATION_ID: appId,
        E2E_INTERNSHIP_APPLICATION_FILE_ID: finalFileId,
        E2E_INTERNSHIP_APPLICATION_COMPANY: companyName,
        E2E_INTERNSHIP_APPLICATION_POSITION: finalPosition
      },
      stdio: 'inherit'
    })
  })
})
