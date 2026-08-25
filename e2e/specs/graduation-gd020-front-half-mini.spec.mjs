import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { StaffLoginPage, StudentLoginPage } from '../pages/login.page.mjs'

const miniBase = process.env.E2E_MINIAPP_BASE_URL || 'http://127.0.0.1:5188'
const runId = process.env.GITHUB_RUN_ID || String(Date.now())
const batchName = `E2E-GD020-FRONT 毕设批次 ${runId}`
const batchNo = `GD020F-${runId}`
const topicTitle = `E2E-GD020-FRONT 课题 ${runId}`
const roundName = `E2E-GD020-FRONT 第一轮 ${runId}`
const mentorNo = 'e2e_advisor_a'
const mentorName = 'E2E指导教师A'
const studentNo = 'E2E20260001'
const studentName = 'E2E学生A'

function field(page, label) {
  return page.locator('.ie-fld').filter({ has: page.locator('.ie-lbl').filter({ hasText: label }) }).first()
}

async function fillField(page, label, value) {
  const target = field(page, label).locator('input:not([type=checkbox]), textarea').first()
  await expect(target, `field ${label}`).toBeVisible()
  await target.fill(String(value))
}

async function pickRemote(page, label, keyword, optionText) {
  const root = field(page, label)
  await root.locator('.app-remote-select__control').click()
  const search = root.locator('.app-remote-select__search-el')
  await expect(search).toBeVisible()
  await search.fill(keyword)
  const option = root.locator('.app-remote-select__option').filter({ hasText: optionText }).first()
  await expect(option, `remote option ${optionText}`).toBeVisible({ timeout: 15_000 })
  await option.click()
}

function rowFor(page, text) {
  return page.locator('tr').filter({ hasText: text }).first()
}

async function confirmDialog(page, buttonPattern = /确认|通过|启用|开启|保存/) {
  const dialog = page.locator('[role=dialog], .app-confirm-dialog, .confirm-dialog').filter({ has: page.getByRole('button', { name: buttonPattern }) }).last()
  if (await dialog.count()) {
    await dialog.getByRole('button', { name: buttonPattern }).last().click()
    return
  }
  await page.getByRole('button', { name: buttonPattern }).last().click()
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

async function loginTeacherMini(page) {
  await page.goto(`${miniBase}/#/pages/login/teacher/index`)
  const fields = page.getByRole('textbox')
  await fields.nth(0).fill(config.mentor.username)
  await fields.nth(1).fill(config.mentor.password)
  await page.getByText('填写', { exact: true }).click()
  await fields.nth(2).fill(config.mentor.tenant)
  await page.getByText('我已阅读并同意学校提供的', { exact: false }).click()
  await page.getByText('进入教师工作台', { exact: true }).click()
  await expect(page).toHaveURL(/pages\/teacher\/workbench\/index/, { timeout: 20_000 })
}

async function ensureNoBlockingGuide(page) {
  for (const name of [/我知道了/, /已了解/, /开始使用/, /关闭引导/, /稍后再说/]) {
    const button = page.getByRole('button', { name }).last()
    if (await button.count() && await button.isVisible().catch(() => false)) {
      await button.click().catch(() => {})
    }
  }
}

test.describe.serial('GD-020 front-half + Mini same-batch Browser First', () => {
  // 这是单 MySQL、同 runId 的状态型连续链。第一次失败后已产生的导师/批次/学生不能
  // 在原库原地重放，否则 retry 只会撞唯一键并覆盖真正第一红灯。
  test.describe.configure({ retries: 0 })

  test('create batch → join → qualify → mentor → topic → choice → taskbook → four-surface readback', async ({ browser }) => {
    test.setTimeout(1_200_000)

    const staffCtx = await browser.newContext({ extraHTTPHeaders: { 'X-Forwarded-For': '127.0.0.21' } })
    const studentMiniCtx = await browser.newContext({ extraHTTPHeaders: { 'X-Forwarded-For': '127.0.0.22' }, viewport: { width: 390, height: 844 } })
    const teacherMiniCtx = await browser.newContext({ extraHTTPHeaders: { 'X-Forwarded-For': '127.0.0.23' }, viewport: { width: 390, height: 844 } })
    const studentPcCtx = await browser.newContext({ extraHTTPHeaders: { 'X-Forwarded-For': '127.0.0.24' } })

    const staff = await staffCtx.newPage()
    const studentMini = await studentMiniCtx.newPage()
    const teacherMini = await teacherMiniCtx.newPage()
    const studentPc = await studentPcCtx.newPage()

    try {
      // 1. Staff PC: real login, create and qualify mentor.
      const staffLogin = new StaffLoginPage(staff, config.staffBaseUrl)
      await staffLogin.login(config.multiRole)
      await staffLogin.switchRole(/毕设管理员|毕业设计管理员/)
      await expect(staffLogin.currentRoleText()).resolves.toMatch(/毕设管理员|毕业设计管理员/)
      await staff.goto(`${config.staffBaseUrl}/admin/graduation/mentors/create`)
      await ensureNoBlockingGuide(staff)
      await fillField(staff, '教师工号', mentorNo)
      await fillField(staff, '教师姓名', mentorName)
      await fillField(staff, '所属学院', '智能制造学院')
      await fillField(staff, '所属专业', '软件技术')
      await fillField(staff, '最大指导人数', 8)
      const mentorCreate = staff.waitForResponse((r) => r.request().method() === 'POST' && /\/api\/v1\/graduation\/gd-mentors(?:\?|$)/.test(r.url()))
      await staff.getByRole('button', { name: '保存', exact: true }).click()
      expect((await mentorCreate).ok(), 'mentor create must be real HTTP success').toBeTruthy()
      await expect(staff).toHaveURL(/\/admin\/graduation\/mentors/)
      await ensureNoBlockingGuide(staff)
      const mentorRow = rowFor(staff, mentorNo)
      await expect(mentorRow).toBeVisible({ timeout: 15_000 })
      await mentorRow.getByRole('button', { name: '审核', exact: true }).click()
      const mentorReview = staff.waitForResponse((r) => r.request().method() === 'POST' && r.url().includes('/graduation/gd-mentors/') && r.url().includes('/review'))
      await confirmDialog(staff, /确认通过|通过|确认/)
      expect((await mentorReview).ok(), 'mentor qualification review must persist').toBeTruthy()

      // 2. Staff PC: create and activate final batch.
      await staff.goto(`${config.staffBaseUrl}/admin/graduation/batches/create`)
      await fillField(staff, '批次名称', batchName)
      await fillField(staff, '批次编号', batchNo)
      await fillField(staff, '届', '2026届')
      await fillField(staff, '学年', '2025-2026')
      await fillField(staff, '计划人数', 1)
      const batchCreate = staff.waitForResponse((r) => r.request().method() === 'POST' && /\/api\/v1\/graduation\/batches(?:\?|$)/.test(r.url()))
      await staff.getByRole('button', { name: '保存', exact: true }).click()
      const batchCreateResponse = await batchCreate
      expect(batchCreateResponse.ok(), 'batch create must be real HTTP success').toBeTruthy()
      const batchEnvelope = await batchCreateResponse.json()
      const batchId = String(batchEnvelope?.data?.id || '')
      expect(batchId, 'created batch id').toMatch(/^\d+$/)
      await expect(staff).toHaveURL(/\/admin\/graduation\/batches/)
      await ensureNoBlockingGuide(staff)
      const batchRow = rowFor(staff, batchName)
      await expect(batchRow).toBeVisible({ timeout: 15_000 })
      await batchRow.getByRole('button', { name: '启用', exact: true }).click()
      const activate = staff.waitForResponse((r) => r.request().method() === 'POST' && r.url().includes(`/graduation/batches/${batchId}/activate`))
      await confirmDialog(staff, /确认启用|确认/)
      expect((await activate).ok(), 'batch activation must persist').toBeTruthy()

      // 3. Staff PC: join the real E2E student to this exact batch.
      await staff.goto(`${config.staffBaseUrl}/admin/graduation/students/create`)
      await pickRemote(staff, '学生', studentNo, studentNo)
      await pickRemote(staff, '毕设批次', batchNo, batchName)
      const studentCreate = staff.waitForResponse((r) => r.request().method() === 'POST' && /\/api\/v1\/graduation\/gd-students(?:\?|$)/.test(r.url()))
      await staff.getByRole('button', { name: '建档', exact: true }).click()
      const studentCreateResponse = await studentCreate
      expect(studentCreateResponse.ok(), 'graduation student create must persist').toBeTruthy()
      const studentEnvelope = await studentCreateResponse.json()
      const gdStudentId = String(studentEnvelope?.data?.id || '')
      expect(gdStudentId, 'graduation student id').toMatch(/^\d+$/)

      // 4. Staff PC: real qualification decision before any student choice.
      // Product correctly rejects PENDING students at Student Mini; R9 must include the school-side qualification step.
      await staff.goto(`${config.staffBaseUrl}/admin/graduation/students?panel=eligibility&batchId=${batchId}`)
      await ensureNoBlockingGuide(staff)
      // 学号在 Staff PC 名单按安全策略脱敏显示，不能用完整 studentNo 定位真实行。
      const eligibilityRow = rowFor(staff, studentName)
      await expect(eligibilityRow, 'new graduation student must appear in qualification queue').toBeVisible({ timeout: 20_000 })
      await expect(eligibilityRow).toContainText(batchName)
      await expect(eligibilityRow).toContainText('待认定')
      await eligibilityRow.getByRole('button', { name: '认定合格', exact: true }).click()
      const eligibilityDialog = staff.locator('.app-confirm-dialog').filter({ hasText: '毕设资格认定' }).last()
      await expect(eligibilityDialog).toBeVisible()
      await eligibilityDialog.locator('textarea.app-confirm-dialog__textarea').fill('GD-020 最终验收资格认定合格，允许进入选题流程')
      const eligibilitySave = staff.waitForResponse((r) => r.request().method() === 'POST' && r.url().includes(`/graduation/gd-students/${gdStudentId}/eligibility`))
      await eligibilityDialog.getByRole('button', { name: '资格合格', exact: true }).click()
      const eligibilitySaveResponse = await eligibilitySave
      expect(eligibilitySaveResponse.ok(), 'graduation eligibility qualification must persist').toBeTruthy()
      const eligibilityEnvelope = await eligibilitySaveResponse.json()
      expect(eligibilityEnvelope?.data?.eligibilityStatus, 'eligibility API truth').toBe('QUALIFIED')

      // PENDING 成功转为 QUALIFIED 后应离开当前待认定列表；真实切换筛选回读最终状态。
      await expect(rowFor(staff, studentName)).toHaveCount(0, { timeout: 15_000 })
      const eligibilityFilter = staff.locator('.af__field').filter({ hasText: '毕设资格' }).locator('select').first()
      await eligibilityFilter.selectOption('QUALIFIED')
      const qualifiedList = staff.waitForResponse((r) => r.request().method() === 'GET' && r.url().includes('/graduation/gd-students') && r.url().includes(`batchId=${batchId}`) && r.url().includes('eligibility=QUALIFIED'))
      await staff.getByRole('button', { name: '查询', exact: true }).click()
      expect((await qualifiedList).ok(), 'qualified eligibility list must reload').toBeTruthy()
      const qualifiedRow = rowFor(staff, studentName)
      await expect(qualifiedRow, 'qualified student must be readable from Staff PC').toBeVisible({ timeout: 15_000 })
      await expect(qualifiedRow).toContainText('资格合格')

      // 5. Staff PC: bind the qualified mentor through the real assignment form.
      await staff.goto(`${config.staffBaseUrl}/admin/graduation/mentors/assign/${gdStudentId}`)
      await pickRemote(staff, '导师', mentorNo, mentorName)
      await fillField(staff, '分配原因', 'GD-020 最终同批次真实浏览器导师绑定')
      const mentorAssign = staff.waitForResponse((r) => r.request().method() === 'POST' && r.url().includes('/graduation/gd-mentor-assignments/assign'))
      await staff.getByRole('button', { name: '确认', exact: true }).click()
      expect((await mentorAssign).ok(), 'mentor assignment must persist').toBeTruthy()

      // 6. Staff PC: declare the exact topic and submit it for review.
      await staff.goto(`${config.staffBaseUrl}/admin/graduation/topic-lib/create?sourceType=TEACHER`)
      await fillField(staff, '题目名称', topicTitle)
      await pickRemote(staff, '毕设批次', batchNo, batchName)
      await fillField(staff, '题目编号', `TOP-${runId}`)
      await pickRemote(staff, '指导教师', mentorNo, mentorName)
      await fillField(staff, '专业', '软件技术')
      await fillField(staff, '容量', 1)
      await fillField(staff, '题目要求', '完成真实业务闭环并保留完整过程证据')
      const submitReviewBox = staff.locator('label').filter({ hasText: '保存后直接提交审核' }).locator('input[type=checkbox]')
      await submitReviewBox.check()
      const topicCreate = staff.waitForResponse((r) => r.request().method() === 'POST' && /\/api\/v1\/graduation\/gd-topics(?:\?|$)/.test(r.url()))
      await staff.getByRole('button', { name: '保存', exact: true }).click()
      const topicCreateResponse = await topicCreate
      expect(topicCreateResponse.ok(), 'topic create must persist').toBeTruthy()
      const topicEnvelope = await topicCreateResponse.json()
      const topicId = String(topicEnvelope?.data?.id || '')
      expect(topicId, 'topic id').toMatch(/^\d+$/)

      // Review the same topic from the pending queue.
      await staff.goto(`${config.staffBaseUrl}/admin/graduation/topic-lib?panel=pending`)
      await ensureNoBlockingGuide(staff)
      const topicRow = rowFor(staff, topicTitle)
      await expect(topicRow).toBeVisible({ timeout: 15_000 })
      await topicRow.getByRole('button', { name: '通过', exact: true }).click()
      const topicReview = staff.waitForResponse((r) => r.request().method() === 'POST' && r.url().includes(`/graduation/gd-topics/${topicId}/review`))
      await confirmDialog(staff, /确认通过|通过|确认/)
      expect((await topicReview).ok(), 'topic approval must persist').toBeTruthy()

      // 7. Staff PC: create and open a real choice round.
      await staff.goto(`${config.staffBaseUrl}/admin/graduation/topic-rounds/create`)
      await fillField(staff, '轮次名称', roundName)
      await pickRemote(staff, '毕设批次', batchNo, batchName)
      await fillField(staff, '轮次序号', 1)
      await fillField(staff, '最多志愿数', 1)
      const roundCreate = staff.waitForResponse((r) => r.request().method() === 'POST' && r.url().includes('/graduation/gd-topic-rounds'))
      await staff.getByRole('button', { name: '创建', exact: true }).click()
      const roundCreateResponse = await roundCreate
      expect(roundCreateResponse.ok(), 'choice round create must persist').toBeTruthy()
      const roundEnvelope = await roundCreateResponse.json()
      const roundId = String(roundEnvelope?.data?.id || '')
      expect(roundId, 'round id').toMatch(/^\d+$/)
      await expect(staff).toHaveURL(/\/admin\/graduation\/topic-rounds/)
      const roundRow = rowFor(staff, roundName)
      await expect(roundRow).toBeVisible({ timeout: 15_000 })
      await roundRow.getByRole('button', { name: '开启', exact: true }).click()
      const openRound = staff.waitForResponse((r) => r.request().method() === 'POST' && r.url().includes(`/graduation/gd-topic-rounds/${roundId}/open`))
      await confirmDialog(staff, /确认开启|开启|确认/)
      expect((await openRound).ok(), 'choice round open must persist').toBeTruthy()

      // 8. Student Mini: real click the exact topic and submit the choice.
      await loginStudentMini(studentMini)
      await studentMini.goto(`${miniBase}/#/pages/student/graduation/topics/index`)
      await expect(studentMini.getByText(roundName, { exact: true })).toBeVisible({ timeout: 20_000 })
      const miniTopic = studentMini.locator('.tp__topic').filter({ hasText: topicTitle }).first()
      await expect(miniTopic).toBeVisible({ timeout: 20_000 })
      await miniTopic.click()
      const choiceSubmit = studentMini.waitForResponse((r) => r.request().method() === 'POST' && r.url().includes('/api/v1/mobile/graduation/choices'))
      await studentMini.getByText(/提交志愿（已选1）/, { exact: false }).click()
      expect((await choiceSubmit).ok(), 'Student Mini choice submit must persist').toBeTruthy()
      await expect(studentMini.getByText(topicTitle, { exact: true }).first()).toBeVisible()

      // 9. Staff PC: confirm that exact student's real choice.
      await staff.goto(`${config.staffBaseUrl}/admin/graduation/topic-rounds?panel=rounds`)
      const currentRoundRow = rowFor(staff, roundName)
      await currentRoundRow.getByRole('button', { name: '志愿', exact: true }).click()
      const choiceRow = rowFor(staff, studentNo)
      await expect(choiceRow).toBeVisible({ timeout: 15_000 })
      await expect(choiceRow).toContainText(topicTitle)
      await choiceRow.getByRole('button', { name: '确认', exact: true }).click()
      const choiceConfirm = staff.waitForResponse((r) => r.request().method() === 'POST' && r.url().includes('/graduation/gd-topic-rounds/choices/') && r.url().includes('/confirm'))
      await confirmDialog(staff, /确认|通过/)
      expect((await choiceConfirm).ok(), 'Staff PC choice confirmation must persist').toBeTruthy()

      // 10. Teacher Mini: wait for real batch context, then issue taskbook.
      // The Teacher Mini request layer rejects graduation calls locally until the selected batch is persisted.
      // Do not click the issue tab during that bootstrap race; first prove the exact new batch is active.
      await loginTeacherMini(teacherMini)
      const initialTaskbooks = teacherMini.waitForResponse((r) =>
        r.request().method() === 'GET' &&
        r.url().includes('/api/v1/mobile/teacher/graduation/taskbooks') &&
        r.url().includes(`batchId=${batchId}`)
      )
      await teacherMini.goto(`${miniBase}/#/pages/teacher/graduation-taskbook/index`)
      const initialTaskbooksResponse = await initialTaskbooks
      expect(initialTaskbooksResponse.ok(), 'Teacher Mini taskbook page must bootstrap exact batch').toBeTruthy()
      await expect(teacherMini.getByText(batchName, { exact: true })).toBeVisible({ timeout: 20_000 })

      const myStudentsRequest = teacherMini.waitForResponse((r) =>
        r.request().method() === 'GET' &&
        r.url().includes('/api/v1/mobile/teacher/graduation/my-students') &&
        r.url().includes(`batchId=${batchId}`)
      )
      await teacherMini.getByText('下达任务书', { exact: true }).click()
      const myStudentsResponse = await myStudentsRequest
      expect(myStudentsResponse.ok(), 'Teacher Mini own-student query must be real HTTP success').toBeTruthy()
      const myStudentsEnvelope = await myStudentsResponse.json()
      const myStudents = Array.isArray(myStudentsEnvelope?.data)
        ? myStudentsEnvelope.data
        : (myStudentsEnvelope?.data?.items || [])
      expect(
        myStudents.some((row) =>
          String(row?.gdStudentId || row?.id || '') === gdStudentId &&
          String(row?.studentNo || '') === studentNo &&
          String(row?.topicTitle || '') === topicTitle
        ),
        'Teacher Mini own-student response must project the confirmed same-batch mentor/student/topic relation'
      ).toBeTruthy()
      const visibleStudentPicker = teacherMini.locator('.tb__pick-val').filter({ hasText: studentNo }).first()
      await expect(visibleStudentPicker, 'Teacher Mini issue form must visibly select the exact same-batch student').toBeVisible({ timeout: 20_000 })
      await expect(visibleStudentPicker).toContainText(studentName)
      await expect(visibleStudentPicker).toContainText(topicTitle)

      const textareas = teacherMini.locator('textarea')
      await textareas.nth(0).fill('完成 GD-020 同批次毕业设计真实业务闭环')
      await textareas.nth(1).fill('完成选题、开题、中期、成果、评阅、答辩、成绩和归档')
      await textareas.nth(2).fill('按最终验收计划持续推进')
      await textareas.nth(3).fill('形成可追溯的最终归档材料')
      const taskbookIssue = teacherMini.waitForResponse((r) => r.request().method() === 'POST' && r.url().includes('/api/v1/mobile/teacher/graduation/taskbooks'))
      await teacherMini.getByText('下达任务书', { exact: true }).last().click()
      expect((await taskbookIssue).ok(), 'Teacher Mini taskbook issue must persist').toBeTruthy()

      // 11. Student Mini: confirm the same taskbook.
      await studentMini.goto(`${miniBase}/#/pages/student/graduation/taskbook/index`)
      await expect(studentMini.getByText('完成 GD-020 同批次毕业设计真实业务闭环', { exact: true })).toBeVisible({ timeout: 20_000 })
      const taskbookConfirm = studentMini.waitForResponse((r) => r.request().method() === 'POST' && r.url().includes('/api/v1/mobile/graduation/taskbook/confirm'))
      await studentMini.getByText('确认任务书', { exact: true }).click()
      const taskbookConfirmResponse = await taskbookConfirm
      expect(taskbookConfirmResponse.ok(), 'Student Mini taskbook confirm must persist').toBeTruthy()
      const taskbookConfirmEnvelope = await taskbookConfirmResponse.json()
      expect(taskbookConfirmEnvelope?.data?.status, 'Student Mini confirmation API truth').toBe('CONFIRMED')
      expect(String(taskbookConfirmEnvelope?.data?.taskbook?.gdStudentId || ''), 'Student Mini confirmed exact graduation student').toBe(gdStudentId)
      expect(taskbookConfirmEnvelope?.data?.taskbook?.confirmedAt, 'Student Mini confirmation must persist confirmedAt').toBeTruthy()
      await expect(studentMini.getByText(/已确认/).first()).toBeVisible({ timeout: 20_000 })

      // 12. Four-surface same-batch readback.
      await studentMini.goto(`${miniBase}/#/pages/student/graduation/index`)
      await expect(studentMini.getByText(batchName, { exact: true })).toBeVisible({ timeout: 20_000 })
      await expect(studentMini.getByText(topicTitle, { exact: true })).toBeVisible()
      await expect(studentMini.getByText(new RegExp(mentorName))).toBeVisible()

      // Re-enter through the real Teacher Workbench quick action instead of mutating H5 hashes with page.goto.
      // This exercises the same uni-app navigation a teacher uses and guarantees the taskbook page lifecycle
      // runs again before we trust the post-confirmation status badge.
      await expect(teacherMini).toHaveURL(/pages\/teacher\/graduation-taskbook\/index/)
      await teacherMini.goto(`${miniBase}/#/pages/teacher/workbench/index`)
      await expect(teacherMini).toHaveURL(/pages\/teacher\/workbench\/index/, { timeout: 20_000 })
      const taskbookQuickAction = teacherMini.getByText('任务书', { exact: true }).first()
      await expect(taskbookQuickAction, 'Teacher Mini workbench taskbook quick action must be visible').toBeVisible({ timeout: 20_000 })
      const confirmedTaskbooks = teacherMini.waitForResponse((r) =>
        r.request().method() === 'GET' &&
        r.url().includes('/api/v1/mobile/teacher/graduation/taskbooks') &&
        r.url().includes(`batchId=${batchId}`)
      )
      await taskbookQuickAction.click()
      await expect(teacherMini).toHaveURL(/pages\/teacher\/graduation-taskbook\/index/, { timeout: 20_000 })
      const confirmedTaskbooksResponse = await confirmedTaskbooks
      expect(confirmedTaskbooksResponse.ok(), 'Teacher Mini confirmed taskbook readback must be real HTTP success').toBeTruthy()
      const confirmedTaskbooksEnvelope = await confirmedTaskbooksResponse.json()
      const confirmedTaskbookRows = Array.isArray(confirmedTaskbooksEnvelope?.data)
        ? confirmedTaskbooksEnvelope.data
        : (confirmedTaskbooksEnvelope?.data?.items || [])
      const confirmedTaskbook = confirmedTaskbookRows.find((row) => String(row?.gdStudentId || '') === gdStudentId)
      expect(confirmedTaskbook, 'Teacher Mini must read back the exact confirmed taskbook').toBeTruthy()
      expect(confirmedTaskbook?.status, 'Teacher Mini taskbook status API truth').toBe('CONFIRMED')
      expect(confirmedTaskbook?.statusLabel, 'Teacher Mini taskbook status label API truth').toMatch(/已确认/)
      expect(confirmedTaskbook?.confirmedAt, 'Teacher Mini taskbook confirmation timestamp API truth').toBeTruthy()
      const confirmedTeacherCard = teacherMini.locator('.card.tb').filter({ hasText: studentNo }).first()
      await expect(confirmedTeacherCard, 'Teacher Mini confirmed taskbook card must be visible').toBeVisible({ timeout: 20_000 })
      await expect(confirmedTeacherCard).toContainText(/已确认/)

      await new StudentLoginPage(studentPc, config.studentBaseUrl).login(config.student)
      await studentPc.goto(`${config.studentBaseUrl}/graduation`)
      await expect(studentPc.getByText(batchName, { exact: true })).toBeVisible({ timeout: 20_000 })
      await expect(studentPc.getByText(topicTitle, { exact: true })).toBeVisible()
      await expect(studentPc.getByText(new RegExp(mentorName))).toBeVisible()

      await staff.goto(`${config.staffBaseUrl}/admin/graduation/students?panel=roster&batchId=${batchId}`)
      const finalStaffRow = rowFor(staff, studentName)
      await expect(finalStaffRow).toBeVisible({ timeout: 20_000 })
      await expect(finalStaffRow).toContainText(topicTitle)
      await expect(finalStaffRow).toContainText(mentorName)

      // Attach immutable run-scoped business identity for later R9 seal composition.
      await test.info().attach('gd020-front-half-identity.json', {
        body: Buffer.from(JSON.stringify({ runId, batchId, batchName, batchNo, gdStudentId, studentNo, mentorNo, mentorName, topicId, topicTitle, roundId, roundName }, null, 2)),
        contentType: 'application/json'
      })
    } finally {
      await Promise.all([staffCtx.close(), studentMiniCtx.close(), teacherMiniCtx.close(), studentPcCtx.close()])
    }
  })
})