import { config } from './config.mjs'
import { items, loginApi, prepareGraduationFixture } from './api-fixture.mjs'

async function proposalRows(admin, fixture) {
  const data = await admin.get('/graduation/proposals', {
    batchId: fixture.batchId,
    keyword: config.student.username,
    page: 1,
    pageSize: 200,
  })
  return items(data).filter((row) =>
    String(row.studentNo || '') === config.student.username
      || String(row.gdStudentId || '') === fixture.gdStudentId
  )
}

/**
 * U8 Gold must render one deterministic, real teacher review queue from the
 * exact fixture batch. The historical U8 Gold source accidentally selected a
 * different RUNNING batch than prepareGraduationFixture() created, so its
 * screenshot depended on unrelated sandbox residue. This helper advances only
 * the isolated U8 fixture through real APIs: student confirms the taskbook and
 * submits one proposal, which remains PENDING_REVIEW for the teacher surface.
 */
export async function prepareGraduationTeacherMobileGoldFixture() {
  const fixture = await prepareGraduationFixture()
  const admin = await loginApi(config.sandboxAdmin)
  const student = await loginApi(config.student)

  let taskbook = await admin.get(`/graduation/gd-taskbooks/${fixture.gdStudentId}`)
  if (!taskbook?.exists) {
    throw new Error(`U8 Gold fixture taskbook missing for gdStudentId=${fixture.gdStudentId}`)
  }

  if (String(taskbook.status || '').toUpperCase() !== 'CONFIRMED') {
    const studentTaskbook = await student.get('/portal/graduation/taskbook')
    if (!studentTaskbook?.hasData || !studentTaskbook?.taskbookVersion) {
      throw new Error(`U8 Gold student taskbook is not confirmable: ${JSON.stringify(studentTaskbook)}`)
    }
    await student.post('/portal/graduation/taskbook/sign', {
      confirm: true,
      taskbookVersion: studentTaskbook.taskbookVersion,
    })
    taskbook = await admin.get(`/graduation/gd-taskbooks/${fixture.gdStudentId}`)
    if (String(taskbook.status || '').toUpperCase() !== 'CONFIRMED') {
      throw new Error(`U8 Gold taskbook did not become CONFIRMED: ${JSON.stringify(taskbook)}`)
    }
  }

  let proposals = await proposalRows(admin, fixture)
  let pending = proposals.find((row) => String(row.status || '').toUpperCase() === 'PENDING_REVIEW')
  if (!pending) {
    if (proposals.length) {
      throw new Error(`U8 Gold fixture has unexpected existing proposal state: ${JSON.stringify(proposals)}`)
    }
    await student.post('/mobile/graduation/proposal', {
      background: `U8 Gold 开题背景 ${fixture.runId}`,
      plan: '需求分析、方案设计、实现验证、测试复盘，按真实毕设过程推进。',
      outcome: '形成可运行成果、测试证据与毕业设计文档。',
      attachments: [],
    })
    proposals = await proposalRows(admin, fixture)
    pending = proposals.find((row) => String(row.status || '').toUpperCase() === 'PENDING_REVIEW')
  }

  if (!pending) {
    throw new Error(`U8 Gold pending proposal was not created: ${JSON.stringify(proposals)}`)
  }

  return {
    ...fixture,
    proposalId: String(pending.id || ''),
  }
}
