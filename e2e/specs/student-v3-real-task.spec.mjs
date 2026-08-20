import { execFileSync } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'

/**
 * 手册 §13 测试矩阵 · Real Task 行的真实点击回放。
 *
 * 这一行要求的不是"接口能返回"，而是"人真的能点过去并把事办完"：
 *   1. 请假退回 → 消息 → 原请假对象 → 修改重提；
 *   2. 消息确认回执；
 *   3. Agenda 跳考试；
 *   4. 资助带附件。
 *
 * 每一步都在真实浏览器里点，且每一步之后都回读 server truth——只认服务端状态，
 * 不认 toast（手册 §13.1：禁止 toast 成功但服务器未落状态）。
 *
 * 前置事实由 backend/scripts/e2e_seed_student_v3_realtask.py 用正式 API 造，
 * 见该脚本的说明。
 */

const here = path.dirname(fileURLToPath(import.meta.url))
const repoRoot = path.resolve(here, '../..')
const backendDir = path.join(repoRoot, 'backend')
const statePath = path.join(backendDir, 'tmp/e2e_student_v3_realtask_state.local.json')
const miniBase = process.env.E2E_MINIAPP_BASE_URL || 'http://localhost:5188'
const apiBase = config.apiBaseUrl
// 1x1 透明 PNG：附件内容不重要，重要的是它真的走完上传→扫描→绑定这条链。
const ONE_PIXEL_PNG_BASE64 = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=='

function runFixture(command) {
  execFileSync('python3', ['scripts/e2e_seed_student_v3_realtask.py', command], {
    cwd: backendDir,
    env: process.env,
    stdio: 'inherit'
  })
}

function readFixture() {
  return JSON.parse(fs.readFileSync(statePath, 'utf8'))
}

/** 直接问服务端要真相，不经过被测页面。 */
async function serverTruth(request, pathname) {
  const login = await request.post(`${apiBase}/auth/login`, {
    data: {
      loginName: config.student.username,
      password: config.student.password,
      tenantCode: config.student.tenant
    }
  })
  expect(login.ok()).toBeTruthy()
  const token = (await login.json()).data.accessToken
  const response = await request.get(`${apiBase}${pathname}`, {
    headers: { Authorization: `Bearer ${token}` }
  })
  expect(response.ok()).toBeTruthy()
  return (await response.json()).data
}

async function loginStudentMini(page) {
  await page.goto(`${miniBase}/#/pages/login/student/index`)
  const fields = page.getByRole('textbox')
  await fields.nth(0).fill(config.student.username)
  await fields.nth(1).fill(config.student.password)
  await page.getByText('填写', { exact: true }).click()
  await fields.nth(2).fill(config.student.tenant)
  await page.getByText('我已阅读并同意学校提供的', { exact: false }).click()
  await page.getByText('进入学生首页', { exact: true }).click()
  await expect(page).toHaveURL(/pages\/student\/home\/index/, { timeout: 20_000 })
}

test.describe.serial('Student V3 · Real Task 真实点击回放', () => {
  let fixture

  test.beforeAll(() => {
    runFixture('seed')
    fixture = readFixture()
  })

  test.afterAll(() => {
    runFixture('cleanup')
  })

  test('请假退回 → 消息 → 原请假对象 → 修改重提', async ({ page, request }) => {
    const leaveId = fixture.leave.leaveId

    const before = await serverTruth(request, '/mobile/affairs/leave/my')
    const beforeRow = before.items.find((row) => String(row.leaveId) === String(leaveId))
    expect(beforeRow.status).toBe('RETURNED')
    expect(beforeRow.allowedActions).toContain('RESUBMIT')

    await loginStudentMini(page)

    // 从消息进入，而不是直接敲 URL——被测的正是"点得进去"。
    await page.goto(`${miniBase}/#/pages/student/messages/index`)
    await page.getByText('通知', { exact: true }).first().click()
    const card = page.locator('.msg__item', { hasText: '请假被退回' }).first()
    await expect(card).toBeVisible({ timeout: 20_000 })
    // 按钮文案来自服务端 action.label（这里是「请假详情」），所以按结构选，不按文案选。
    await card.locator('.msg__btn').first().click()

    // 服务端下发的 target 必须把人带到请假页并带上 recordId（focusMode=LIST_FOCUS）。
    await expect(page).toHaveURL(new RegExp(`pages/student/affairs/leave.*recordId=${leaveId}`), {
      timeout: 20_000
    })

    // LIST_FOCUS 的实质：那一条真的被定位出来了，而不是让用户自己在列表里找。
    const focused = page.locator(`#leave-${leaveId}.is-focus`)
    await expect(focused).toBeVisible({ timeout: 20_000 })
    await expect(page.getByText('没有找到这条记录')).toHaveCount(0)
    await expect(focused.getByText(fixture.leave.returnReason, { exact: false })).toBeVisible()

    // 修改重提：改事由 → 保存并重新提交。
    await focused.getByText('修改后重提', { exact: true }).click()
    const sheet = page.locator('.lv__sheet')
    await expect(sheet).toBeVisible()
    const reason = sheet.locator('textarea')
    await reason.fill('已补交家长同意证明，按退回意见修改后重新提交审批')
    await sheet.getByText('保存并重新提交', { exact: true }).click()
    await expect(sheet).toBeHidden({ timeout: 20_000 })

    // 只认 server truth：状态离开 RETURNED，版本推进。
    const after = await serverTruth(request, '/mobile/affairs/leave/my')
    const afterRow = after.items.find((row) => String(row.leaveId) === String(leaveId))
    expect(afterRow.status).not.toBe('RETURNED')
    expect(Number(afterRow.version)).toBeGreaterThan(Number(beforeRow.version))
    expect(afterRow.reason).toContain('已补交家长同意证明')
  })

  test('需回执的消息：点开详情确认已阅后服务端 acked 为真', async ({ page, request }) => {
    await loginStudentMini(page)
    await page.goto(`${miniBase}/#/pages/student/messages/index`)
    await page.getByText('通知', { exact: true }).first().click()

    const card = page.locator('.msg__item', { hasText: fixture.ackMessage.title }).first()
    await expect(card).toBeVisible({ timeout: 20_000 })
    await expect(card.getByText('待确认回执', { exact: true })).toBeVisible()

    // 回执按钮在消息详情页，不在列表上——列表只标"待确认回执"。
    await card.click()
    await expect(page).toHaveURL(/pages\/common\/message-detail\/index/, { timeout: 20_000 })
    await page.getByText('确认已阅', { exact: true }).click()
    await expect(page.getByText('你已确认回执', { exact: true })).toBeVisible({ timeout: 20_000 })

    await expect.poll(async () => {
      const data = await serverTruth(request, '/student-mini/messages?page=1&pageSize=50')
      const row = (data.items || []).find((item) => item.title === fixture.ackMessage.title)
      return row ? row.acked : null
    }, { timeout: 20_000 }).toBe(true)
  })

  test('Agenda 显示已排考的考试并能跳到教务考试页', async ({ page }) => {
    await loginStudentMini(page)
    await page.goto(`${miniBase}/#/pages/student/agenda/index`)

    const row = page.locator('.ag__row', { hasText: fixture.exam.courseName }).first()
    await expect(row).toBeVisible({ timeout: 20_000 })
    await expect(row).toContainText('09:00')
    await expect(page.getByText('考试', { exact: true }).first()).toBeVisible()

    await row.click()
    // 学生端考试页是列表（focusMode=NONE），所以只断言"到了考试页"，
    // 不断言定位到某一场——服务端也没宣称 routeExact。
    await expect(page).toHaveURL(/pages\/student\/academic-affairs\/exam/, { timeout: 20_000 })
  })

  test('资助申请带附件：上传后服务端把附件绑到该申请名下', async ({ page, request }) => {
    await loginStudentMini(page)
    await page.goto(`${miniBase}/#/pages/student/affairs/funding`)

    // 夹具开的是奖学金批次（助学金要求先通过困难认定，是另一条业务链）。
    await page.getByText('奖学金', { exact: true }).first().click()
    const form = page.locator('.card', { hasText: '奖学金 / 助学金申请' }).first()
    await expect(form).toBeVisible({ timeout: 20_000 })

    // H5 下 uni.chooseMessageFile 不存在，回落到 chooseImage 的隐藏 file input，
    // 所以走 filechooser 事件，并且必须是图片。
    const evidence = path.join(repoRoot, 'e2e/test-results/s9-rt-funding-evidence.png')
    fs.mkdirSync(path.dirname(evidence), { recursive: true })
    fs.writeFileSync(evidence, Buffer.from(ONE_PIXEL_PNG_BASE64, 'base64'))
    const [chooser] = await Promise.all([
      page.waitForEvent('filechooser'),
      form.getByText('添加附件', { exact: true }).click()
    ])
    await chooser.setFiles(evidence)

    // 组件必须先把附件判成可用于业务，页面才允许提交（扫描中/被拒时 ready=false）。
    // 不按具体扫描文案断言——小图片走 NOT_REQUIRED（"无需扫描"），大文件才会 PENDING/CLEAN；
    // 真正的合同是"列出来了，且没有阻断提交的告警"。
    await expect(form.locator('.map__row')).toHaveCount(1, { timeout: 30_000 })
    await expect(form.getByText('附件还不能用于提交', { exact: false })).toHaveCount(0)

    await form.locator('textarea').first().fill('学业成绩优秀，附成绩与获奖证明材料')
    await form.getByText('已阅读并确认诚信承诺', { exact: false }).click()
    await form.getByText('提交奖学金申请', { exact: true }).click()

    // 只认 server truth：申请真的落库，且附件真的绑在这笔申请名下。
    await expect.poll(async () => {
      const data = await serverTruth(request, '/mobile/affairs/funding/my')
      const rows = data.items || []
      return rows.length ? Number(rows[0].attachmentCount || 0) : 0
    }, { timeout: 30_000 }).toBeGreaterThan(0)

    // 页面也要把它显示出来，不能只有服务端知道。
    await expect(page.getByText('已附佐证材料', { exact: false })).toBeVisible({ timeout: 20_000 })
  })
})
