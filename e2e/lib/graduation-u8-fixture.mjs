import { config } from './config.mjs'
import { items, loginApi, prepareGraduationFixture } from './api-fixture.mjs'

const u8StudentAccount = {
  tenant: process.env.E2E_GRADUATION_U8_STUDENT_TENANT || config.student.tenant,
  username: process.env.E2E_GRADUATION_U8_STUDENT_USERNAME || 'E2E20260002',
  password: process.env.E2E_GRADUATION_U8_STUDENT_PASSWORD || config.student.password,
}

export const u8TeacherAccount = {
  tenant: process.env.E2E_GRADUATION_U8_TEACHER_TENANT || config.mentor.tenant,
  username: process.env.E2E_GRADUATION_U8_TEACHER_USERNAME || 'e2e_advisor_b',
  password: process.env.E2E_GRADUATION_U8_TEACHER_PASSWORD || config.mentor.password,
}

async function proposalRows(admin, fixture) {
  const data = await admin.get('/graduation/proposals', {
    batchId: fixture.batchId,
    keyword: fixture.studentNo,
    page: 1,
    pageSize: 200,
  })
  return items(data).filter((row) =>
    String(row.studentNo || '') === fixture.studentNo
      || String(row.gdStudentId || '') === fixture.gdStudentId
      || String(row.projectId || '') === fixture.gdStudentId
  )
}

async function proposalMaterialVersion(student) {
  const library = await student.get('/mobile/graduation/material-center/library')
  const material = items(library).find((row) => String(row.materialCode || '') === 'PROPOSAL_REPORT')
  return Number(material?.version || 0)
}

async function ensureU8StudentFixture(admin, fixture) {
  const studentRows = items(await admin.get('/students', {
    keyword: u8StudentAccount.username,
    page: 1,
    pageSize: 50,
  }))
  const profile = studentRows.find((row) =>
    String(row.studentNo || row.loginName || '') === u8StudentAccount.username
  )
  if (!profile) {
    throw new Error(`U8 Gold student ${u8StudentAccount.username} is not visible to the E2E administrator.`)
  }

  const gdRows = items(await admin.get('/graduation/gd-students', {
    batchId: fixture.batchId,
    keyword: u8StudentAccount.username,
    page: 1,
    pageSize: 200,
  }))
  let gdStudent = gdRows.find((row) => String(row.studentNo || '') === u8StudentAccount.username)
  if (!gdStudent) {
    gdStudent = await admin.post('/graduation/gd-students', {
      studentId: String(profile.id || profile.studentId),
      batchId: fixture.batchId,
      remark: 'Playwright U8 isolated teacher-mobile fixture',
    })
  }
  await admin.post(`/graduation/gd-students/${gdStudent.id}/eligibility`, {
    status: 'QUALIFIED',
    reason: 'Playwright U8 独立教师移动端 Gold 夹具',
  })

  const mentors = items(await admin.get('/graduation/gd-mentors', {
    keyword: u8TeacherAccount.username,
    page: 1,
    pageSize: 200,
  }))
  let mentor = mentors.find((row) => String(row.teacherNo || '') === u8TeacherAccount.username)
  if (!mentor) {
    mentor = await admin.post('/graduation/gd-mentors', {
      teacherNo: u8TeacherAccount.username,
      teacherName: 'E2E指导教师B',
      mentorType: 'INTERNAL',
      title: '讲师',
      researchDirection: '软件工程测试',
      maxCapacity: 20,
      submitReview: true,
      remark: 'Playwright U8 isolated teacher-mobile fixture',
    })
  }
  const mentorStatus = String(mentor.qualificationStatus || mentor.reviewStatus || '').toUpperCase()
  if (!['QUALIFIED', 'APPROVED'].includes(mentorStatus)) {
    try {
      mentor = await admin.post(`/graduation/gd-mentors/${mentor.id}/review`, {
        action: 'APPROVE',
        comment: 'Playwright U8 独立教师移动端 Gold 导师资格通过',
      })
    } catch (error) {
      if (!/已审核|无需审核|状态/.test(error.message)) throw error
    }
  }
  try {
    await admin.post('/graduation/gd-mentor-assignments/assign', {
      gdStudentId: String(gdStudent.id),
      mentorId: String(mentor.id),
      reason: 'Playwright U8 独立教师移动端 Gold 夹具',
    })
  } catch (error) {
    if (!/已分配|已有导师|重复|ACTIVE|存在/.test(error.message)) throw error
  }

  const topicTitle = `Playwright U8 教师移动端课题 ${fixture.runId}`
  const topics = items(await admin.get('/graduation/gd-topics', {
    batchId: fixture.batchId,
    keyword: topicTitle,
    archiveView: 'active',
    page: 1,
    pageSize: 200,
  }))
  let topic = topics.find((row) => String(row.title || '') === topicTitle)
  if (!topic) {
    topic = await admin.post('/graduation/gd-topics', {
      title: topicTitle,
      batchId: fixture.batchId,
      sourceType: 'TEACHER',
      advisorName: 'E2E指导教师B',
      category: '软件工程',
      difficulty: 'MEDIUM',
      requirements: '验证教师小程序毕设工作台与任务书真实分页上下文',
      outcome: '真实待审开题、任务书和移动端 Gold 证据',
      capacity: 1,
      submitReview: true,
    })
  }
  if (String(topic.reviewStatus || '').toUpperCase() !== 'APPROVED') {
    try {
      topic = await admin.post(`/graduation/gd-topics/${topic.id}/review`, {
        action: 'APPROVE',
        comment: 'Playwright U8 独立教师移动端 Gold 课题审核通过',
      })
    } catch (error) {
      if (!/已审核|无需审核|状态/.test(error.message)) throw error
    }
  }
  try {
    await admin.post(`/graduation/gd-students/${gdStudent.id}/assign-topic`, {
      topicId: String(topic.id),
    })
  } catch (error) {
    if (!/已分配|重复|已选|存在/.test(error.message)) throw error
  }

  const taskbook = await admin.get(`/graduation/gd-taskbooks/${gdStudent.id}`, {
    batchId: fixture.batchId,
  })
  if (!taskbook?.exists) {
    await admin.post(`/graduation/gd-taskbooks/${gdStudent.id}/issue`, {
      objective: '形成一条独立真实的开题待审记录',
      content: '学生签署独立任务书并提交待审开题，供 U8 教师移动端 Gold 使用。',
    }, { batchId: fixture.batchId })
  }

  return {
    ...fixture,
    gdStudentId: String(gdStudent.id),
    studentNo: u8StudentAccount.username,
    topicTitle: topic.title,
  }
}

/**
 * U8 Gold must render one deterministic, real teacher review queue from the
 * exact fixture batch. The lifecycle suite deliberately advances student A's
 * proposal to APPROVED, so U8 uses separately bootstrapped student B + mentor B
 * in the same run-scoped batch. This keeps both flows real without sharing a
 * mentor queue, mutating an approved proposal backwards, or weakening the API.
 */
export async function prepareGraduationTeacherMobileGoldFixture() {
  const baseFixture = await prepareGraduationFixture()
  const admin = await loginApi(config.sandboxAdmin)
  const fixture = await ensureU8StudentFixture(admin, baseFixture)
  const student = await loginApi(u8StudentAccount)

  let taskbook = await admin.get(`/graduation/gd-taskbooks/${fixture.gdStudentId}`, {
    batchId: fixture.batchId,
  })
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
    taskbook = await admin.get(`/graduation/gd-taskbooks/${fixture.gdStudentId}`, {
      batchId: fixture.batchId,
    })
    if (String(taskbook.status || '').toUpperCase() !== 'CONFIRMED') {
      throw new Error(`U8 Gold taskbook did not become CONFIRMED: ${JSON.stringify(taskbook)}`)
    }
  }

  let proposals = await proposalRows(admin, fixture)
  let pending = proposals.find((row) => String(row.status || '').toUpperCase() === 'PENDING_REVIEW')
  if (!pending) {
    const existingStatuses = proposals.map((row) => String(row.status || '').toUpperCase())
    const blocking = existingStatuses.filter((status) => status && status !== 'NOT_SUBMITTED')
    if (blocking.length) {
      throw new Error(`U8 Gold fixture has unexpected existing proposal state: ${JSON.stringify(proposals)}`)
    }
    if (proposals.length > 1) {
      throw new Error(`U8 Gold fixture has duplicate NOT_SUBMITTED proposal projections: ${JSON.stringify(proposals)}`)
    }
    await student.post('/mobile/graduation/proposal', {
      background: `U8 Gold 开题背景 ${fixture.runId}`,
      plan: '需求分析、方案设计、实现验证、测试复盘，按真实毕设过程推进。',
      outcome: '形成可运行成果、测试证据与毕业设计文档。',
      attachments: [],
      expectedVersion: await proposalMaterialVersion(student),
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
