import { execFileSync } from 'node:child_process'
import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { loadInternshipFixture } from '../lib/internship-fixture.mjs'
import { StaffLoginPage } from '../pages/login.page.mjs'

const PREFIX = 'E2E-BATCH-20260823'

function isoDay(offset) {
  const date = new Date()
  date.setUTCHours(0, 0, 0, 0)
  date.setUTCDate(date.getUTCDate() + offset)
  return date.toISOString().slice(0, 10)
}

function apiPath(response) {
  try { return new URL(response.url()).pathname } catch { return '' }
}

async function responseJson(response) {
  const text = await response.text()
  let body = null
  try { body = JSON.parse(text) } catch { body = null }
  return { text, body }
}

async function expectBusinessOk(response, action) {
  const { text, body } = await responseJson(response)
  expect(response.ok(), `${action} HTTP ${response.status()}: ${text.slice(0, 800)}`).toBeTruthy()
  expect(body?.code, `${action} business error: ${text.slice(0, 800)}`).toBe(0)
  return body
}

function formItem(page, label) {
  const labelLocator = page.locator('.app-form-item__label').filter({ hasText: label })
  return page.locator('.app-form-item').filter({ has: labelLocator }).first()
}

async function fillText(page, label, value) {
  const input = formItem(page, label).locator('input').first()
  await expect(input, `${label} input`).toBeVisible()
  await input.fill(String(value))
}

async function fillDate(page, label, value) {
  const input = formItem(page, label).locator('input').first()
  await expect(input, `${label} date input`).toBeVisible()
  await input.fill(value)
  await input.press('Tab')
}

async function fillCreateForm(page, { batchName, batchNo, startDate, endDate }) {
  await fillText(page, '批次名称', batchName)
  await fillText(page, '批次编号', batchNo)
  await fillText(page, '学年', '2026-2027')
  await fillText(page, '学期', '第一学期')
  await fillDate(page, '实习开始', startDate)
  await fillDate(page, '实习结束', endDate)
  await fillText(page, '计划人数', 36)
}

test.describe('岗位实习审计：批次创建、规则、唯一性与状态流转', () => {
  test.describe.configure({ mode: 'serial', retries: 0 })

  let fixture
  let batchId = ''
  let batchName = ''
  let batchNo = ''
  let editedRemark = ''
  const startDate = isoDay(30)
  const endDate = isoDay(120)

  test.beforeAll(async () => {
    execFileSync('python', ['../backend/scripts/e2e_seed_internship_sandbox.py'], {
      cwd: process.cwd(),
      env: process.env,
      stdio: 'inherit'
    })
    fixture = await loadInternshipFixture()
    batchName = `${PREFIX}-${fixture.runId}-真实批次`
    batchNo = `IX-${String(fixture.runId).slice(-10)}`
    editedRemark = `${PREFIX}-${fixture.runId}-浏览器编辑后持久化`
  })

  test('管理员真实创建批次：规则权重错误先在浏览器阻断，修正后创建并刷新持久化', async ({ page }) => {
    await new StaffLoginPage(page, config.staffBaseUrl).login(config.sandboxAdmin)
    await page.goto(`${config.staffBaseUrl}/admin/internship/batches`)
    await expect(page.getByText('实习批次设置').first()).toBeVisible()
    await page.getByRole('button', { name: '新建批次' }).click()
    await expect(page.getByText('新建实习批次').first()).toBeVisible()

    await fillCreateForm(page, { batchName, batchNo, startDate, endDate })

    await page.getByRole('button', { name: '＋ 添加阶段' }).click()
    const stage = page.locator('.bf-row').first()
    await stage.locator('input').nth(0).fill('浏览器岗前准备')
    await stage.locator('input').nth(1).fill('E2E_PREP')

    await fillText(page, '电子围栏半径（米）', 650)

    let createRequests = 0
    page.on('request', (request) => {
      if (request.method() === 'POST' && apiPath({ url: () => request.url() }) === '/api/v1/internship/batches') {
        createRequests += 1
      }
    })

    await fillText(page, '企业评价 %', 30)
    await page.getByRole('button', { name: '创建批次' }).click()
    await expect(page.getByText(/评价权重合计须为 100%，当前 90%/)).toBeVisible()
    await page.waitForTimeout(300)
    expect(createRequests, 'invalid evaluation weights must not send create request').toBe(0)

    await fillText(page, '企业评价 %', 40)
    const createResponsePromise = page.waitForResponse((response) =>
      apiPath(response) === '/api/v1/internship/batches'
      && response.request().method() === 'POST'
    )
    await page.getByRole('button', { name: '创建批次' }).click()
    const body = await expectBusinessOk(await createResponsePromise, '创建实习批次')
    batchId = String(body.data.id)
    expect(batchId).not.toBe('')

    await page.goto(`${config.staffBaseUrl}/admin/internship/batches/${batchId}`)
    await expect(page.getByRole('heading', { name: `${batchName} · 批次详情` })).toBeVisible()
    await expect(page.locator('main p').filter({ hasText: batchNo }).first()).toBeVisible()
    await expect(page.getByText('浏览器岗前准备').first()).toBeVisible()
    await expect(page.getByText(/电子围栏 650 米/).first()).toBeVisible()
    await expect(page.getByText('新建批次').first()).toBeVisible()

    await page.reload()
    await expect(page.getByRole('heading', { name: `${batchName} · 批次详情` })).toBeVisible()
    await expect(page.getByText('浏览器岗前准备').first()).toBeVisible()
    await expect(page.getByText(/电子围栏 650 米/).first()).toBeVisible()
  })

  test('管理员从真实新建页重复使用 batchNo，后端业务拒绝且不产生第二条批次', async ({ page }) => {
    await new StaffLoginPage(page, config.staffBaseUrl).login(config.sandboxAdmin)
    await page.goto(`${config.staffBaseUrl}/admin/internship/batches/new`)
    await expect(page.getByText('新建实习批次').first()).toBeVisible()
    await fillCreateForm(page, {
      batchName: `${batchName}-重复编号尝试`,
      batchNo,
      startDate,
      endDate
    })

    const duplicateResponsePromise = page.waitForResponse((response) =>
      apiPath(response) === '/api/v1/internship/batches'
      && response.request().method() === 'POST'
    )
    await page.getByRole('button', { name: '创建批次' }).click()
    const response = await duplicateResponsePromise
    const { text, body } = await responseJson(response)
    expect(response.status(), `duplicate batchNo must be a handled business rejection: ${text.slice(0, 800)}`).toBeLessThan(500)
    expect(body?.code, `duplicate batchNo unexpectedly succeeded: ${text.slice(0, 800)}`).not.toBe(0)
    await expect(page).toHaveURL(/\/admin\/internship\/batches\/new/)
    await expect(page.getByText('已新建批次（草稿态）')).toHaveCount(0)
  })

  test('草稿真实编辑后启用；启用后深链编辑只读；随后结束并由页面与 MySQL 双重核验审计链', async ({ page }) => {
    expect(batchId, 'previous create stage must provide batchId').not.toBe('')
    await new StaffLoginPage(page, config.staffBaseUrl).login(config.sandboxAdmin)

    await page.goto(`${config.staffBaseUrl}/admin/internship/batches/${batchId}/edit`)
    await expect(page.getByText('编辑实习批次').first()).toBeVisible()
    await fillText(page, '计划人数', 37)
    const remark = formItem(page, '备注').locator('textarea').first()
    await remark.fill(editedRemark)

    const updateResponsePromise = page.waitForResponse((response) =>
      apiPath(response) === `/api/v1/internship/batches/${batchId}`
      && response.request().method() === 'PUT'
    )
    await page.getByRole('button', { name: '保存修改' }).click()
    await expectBusinessOk(await updateResponsePromise, '编辑实习批次')

    await page.goto(`${config.staffBaseUrl}/admin/internship/batches/${batchId}`)
    await expect(page.getByText(editedRemark).first()).toBeVisible()
    await expect(page.getByText('37 / 0').first()).toBeVisible()
    await expect(page.getByText('编辑批次').first()).toBeVisible()

    await page.getByRole('button', { name: '选择学生并启用' }).click()
    const participantCard = page.locator('.bps-card')
    await expect(participantCard.getByText('参与学生范围')).toBeVisible()

    const studentField = participantCard.locator('.bps-field').filter({ hasText: '补充指定学生' }).first()
    const studentPicker = studentField.getByRole('combobox')
    await studentPicker.click()
    const studentSearch = studentField.getByPlaceholder('按学号 / 姓名搜索')
    await studentSearch.fill(fixture.studentNo)
    const studentOption = studentField.getByRole('option').filter({ hasText: fixture.studentNo }).first()
    await expect(studentOption).toBeVisible()
    await studentOption.click()
    await studentPicker.press('Escape')

    const previewResponsePromise = page.waitForResponse((response) =>
      apiPath(response) === `/api/v1/internship/batches/${batchId}/participants/preview`
      && response.request().method() === 'POST'
    )
    await expect(participantCard.getByRole('button', { name: '预览学生名单' })).toBeEnabled()
    await participantCard.getByRole('button', { name: '预览学生名单' }).click()
    const previewed = await expectBusinessOk(await previewResponsePromise, '预览批次参与学生')
    expect(Number(previewed.data?.matchedCount || 0)).toBeGreaterThanOrEqual(1)
    await expect(participantCard.getByText(fixture.studentNo).first()).toBeVisible()

    await expect(participantCard.getByRole('button', { name: '冻结名单并启用批次' })).toBeEnabled()
    const freezeResponsePromise = page.waitForResponse((response) =>
      apiPath(response) === `/api/v1/internship/batches/${batchId}/participants/freeze`
      && response.request().method() === 'POST'
    )
    await participantCard.getByRole('button', { name: '冻结名单并启用批次' }).click()
    const activateDialog = page.getByRole('dialog')
    await expect(activateDialog).toContainText('冻结参与学生名单')
    await activateDialog.getByRole('button', { name: '确认冻结并启用' }).click()
    const activated = await expectBusinessOk(await freezeResponsePromise, '冻结参与学生并启用实习批次')
    expect(activated.data.batchStatus).toBe('RUNNING')
    await expect(participantCard.getByText('名单已冻结')).toBeVisible()
    const statusCard = page.locator('.mp-card').filter({ hasText: '状态与操作' }).first()
    await expect(statusCard.getByText('进行中').first()).toBeVisible()
    await expect(page.getByText('37 / 1').first()).toBeVisible()
    await expect(page.getByText('启用批次').first()).toBeVisible()

    await page.goto(`${config.staffBaseUrl}/admin/internship/batches/${batchId}/edit`)
    await expect(page.getByText('当前批次不可编辑').first()).toBeVisible()
    await expect(page.getByRole('button', { name: '保存修改' })).toBeDisabled()

    // 新参与学生未完成资格/企业/岗位等 BATCH_CLOSE 前置时，普通结束必须继续被后端闸门阻断。
    // 页面先读 readiness，再显式切换为“强制结束”并要求管理员填写原因，不能绕过真实 UI 直调接口。
    await page.goto(`${config.staffBaseUrl}/admin/internship/batches/${batchId}`)
    await page.getByRole('button', { name: '结束' }).click()
    const closeDialog = page.getByRole('dialog')
    await expect(closeDialog).toContainText('强制结束批次')
    await expect(closeDialog).toContainText(/当前有 1 名学生存在结束阻断/)
    await closeDialog.locator('textarea').fill('E2E验收批次存在未完成学生，强制结束释放当前批次')

    const closeResponsePromise = page.waitForResponse((response) =>
      apiPath(response) === `/api/v1/internship/batches/${batchId}/close`
      && response.request().method() === 'POST'
    )
    await closeDialog.getByRole('button', { name: '确认强制结束' }).click()
    const closed = await expectBusinessOk(await closeResponsePromise, '强制结束实习批次')
    expect(closed.data.status).toBe('CLOSED')
    expect(closed.data.forced).toBe(true)
    await expect(page.getByText('已结束').first()).toBeVisible()

    const auditCard = page.locator('.mp-card').filter({ hasText: '操作留痕' }).first()
    await expect(auditCard).toContainText('新建批次')
    await expect(auditCard).toContainText('编辑批次')
    await expect(auditCard).toContainText('启用批次')
    await expect(auditCard).toContainText('结束批次')

    const output = execFileSync('python', ['../backend/scripts/e2e_verify_internship_batch_audit.py'], {
      cwd: process.cwd(),
      encoding: 'utf8',
      env: {
        ...process.env,
        E2E_INTERNSHIP_BATCH_ID: batchId,
        E2E_INTERNSHIP_BATCH_NO: batchNo,
        E2E_INTERNSHIP_BATCH_NAME: batchName,
        E2E_INTERNSHIP_BATCH_REMARK: editedRemark
      }
    })
    expect(output).toContain('DB_EVIDENCE_OK')
    console.log(output.trim())
  })
})
