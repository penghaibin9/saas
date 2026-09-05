import { config } from './config.mjs'

function url(path, params) {
  const target = new URL(`${config.apiBaseUrl}${path}`)
  for (const [key, value] of Object.entries(params || {})) {
    if (value !== undefined && value !== null && value !== '') target.searchParams.set(key, String(value))
  }
  return target
}

async function readEnvelope(response) {
  const text = await response.text()
  let json
  try { json = JSON.parse(text) } catch {
    throw new Error(`${response.status} ${response.url}: ${text.slice(0, 500)}`)
  }
  if (!response.ok || json.code !== 0) {
    const details = json.details ?? json.detail ?? json.data
    const suffix = details ? ` details=${JSON.stringify(details).slice(0, 1_500)}` : ''
    throw new Error(`${response.status} ${response.url}: ${json.message || text.slice(0, 500)}${suffix}`)
  }
  return json.data
}

export class Api {
  constructor(token = '') { this.token = token }
  async request(method, path, { params, body } = {}) {
    const response = await fetch(url(path, params), {
      method,
      headers: {
        Accept: 'application/json',
        'X-Forwarded-For': '10.255.0.31',
        ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}),
        ...(this.token ? { Authorization: `Bearer ${this.token}` } : {})
      },
      body: body === undefined ? undefined : JSON.stringify(body)
    })
    return readEnvelope(response)
  }
  get(path, params) { return this.request('GET', path, { params }) }
  post(path, body, params) { return this.request('POST', path, { body, params }) }
  put(path, body, params) { return this.request('PUT', path, { body, params }) }
}

const loginTokenCache = new Map()
const browserSessionByAccessToken = new Map()

function loginCacheKey(account) {
  return `${String(account?.tenant || '')}\u0000${String(account?.username || '')}\u0000PC`
}

export function browserSessionForAccessToken(accessToken) {
  return browserSessionByAccessToken.get(String(accessToken || '')) || null
}

export async function loginApi(account) {
  const cacheKey = loginCacheKey(account)
  let tokenPromise = loginTokenCache.get(cacheKey)

  if (!tokenPromise) {
    tokenPromise = (async () => {
      const api = new Api()
      const data = await api.post('/auth/login', {
        loginName: account.username,
        password: account.password,
        tenantCode: account.tenant,
        clientType: 'PC'
      })
      const accessToken = String(data?.accessToken || '')
      const refreshToken = String(data?.refreshToken || '')
      if (!accessToken || !refreshToken) throw new Error('E2E API login must issue access and refresh tokens')
      browserSessionByAccessToken.set(accessToken, {
        refreshToken,
        userType: String(data?.user?.userType || ''),
        roleCode: String(data?.user?.currentRoleCode || data?.currentRole?.roleCode || '')
      })
      return accessToken
    })()
    loginTokenCache.set(cacheKey, tokenPromise)
  }

  try {
    return new Api(await tokenPromise)
  } catch (error) {
    if (loginTokenCache.get(cacheKey) === tokenPromise) loginTokenCache.delete(cacheKey)
    throw error
  }
}

export function items(data) {
  return Array.isArray(data) ? data : (data?.items || data?.list || [])
}

function isoDay(offset) {
  const date = new Date()
  date.setUTCHours(0, 0, 0, 0)
  date.setUTCDate(date.getUTCDate() + offset)
  return date.toISOString().slice(0, 10)
}

function academicYear() {
  const year = new Date().getUTCFullYear()
  return `${year}-${year + 1}`
}

function expectedStateError(error, patterns) {
  const message = String(error?.message || '')
  return patterns.some((pattern) => pattern.test(message))
}

function fixtureIdentity(rawRun, fixtureKey = '') {
  const base = String(rawRun).replace(/\D/g, '').slice(-12) || String(Date.now()).slice(-12)
  const key = String(fixtureKey || '').trim().toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')
  return key ? `${base}-${key}` : base
}

async function findStudentProfile(api, studentNo) {
  const data = await api.get('/students', { keyword: studentNo, page: 1, pageSize: 50 })
  const row = items(data).find((item) => String(item.studentNo || item.loginName || '') === studentNo)
  if (!row) throw new Error(`Student profile ${studentNo} is not visible to the school-wide E2E administrator.`)
  return row
}

async function ensureBatch(api, runId) {
  const batchNo = `PW-E2E-${runId}`
  let batch = items(await api.get('/graduation/batches', { keyword: batchNo, page: 1, pageSize: 200 }))
    .find((item) => item.batchNo === batchNo)

  if (!batch) {
    const year = new Date().getUTCFullYear()
    batch = await api.post('/graduation/batches', {
      batchName: `Playwright 毕设交互测试 ${runId}`,
      batchNo,
      academicYear: academicYear(),
      gradeYear: `${year + 1}届`,
      plannedCount: 1,
      remark: 'Only for isolated Playwright E2E database'
    })
  }

  const status = String(batch.status || 'DRAFT').toUpperCase()
  if (status === 'RUNNING') return batch
  if (!['DRAFT', 'UNCONFIGURED'].includes(status)) {
    throw new Error(`E2E graduation batch ${batchNo} is ${status}; retries must not reopen a closed or archived batch.`)
  }

  await api.post(`/graduation/batches/${batch.id}/rules`, {
    rules: {
      score: { advisorWeight: 0.4, reviewerWeight: 0.3, defenseWeight: 0.3 },
      plagiarism: { thresholdPercent: 20, mustPassToDefense: true }
    }
  })
  await api.post(`/graduation/batches/${batch.id}/stages`, {
    stages: [
      { code: 'TOPIC', name: '选题', startDate: isoDay(-45), endDate: isoDay(-1) },
      { code: 'PROPOSAL', name: '开题', startDate: isoDay(0), endDate: isoDay(30) },
      { code: 'MIDTERM', name: '中期', startDate: isoDay(31), endDate: isoDay(60) },
      { code: 'SUBMISSION', name: '成果', startDate: isoDay(61), endDate: isoDay(90) },
      { code: 'PLAGIARISM', name: '查重', startDate: isoDay(91), endDate: isoDay(100) },
      { code: 'REVIEW', name: '评阅', startDate: isoDay(101), endDate: isoDay(110) },
      { code: 'DEFENSE', name: '答辩', startDate: isoDay(111), endDate: isoDay(125) },
      { code: 'GRADE', name: '成绩', startDate: isoDay(126), endDate: isoDay(145) }
    ]
  })
  const activated = await api.post(`/graduation/batches/${batch.id}/activate`, {})
  return { ...batch, ...(activated || {}), status: 'RUNNING' }
}

function graduationStudentEntity(data) {
  return data?.student || data || null
}

async function readGdStudent(api, recordId) {
  return graduationStudentEntity(await api.get(`/graduation/gd-students/${recordId}`))
}

async function ensureGdStudent(api, batchId, profile, studentNo) {
  const rows = items(await api.get('/graduation/gd-students', {
    batchId, keyword: studentNo, page: 1, pageSize: 200
  }))
  let row = rows.find((item) => String(item.studentNo || '') === studentNo)
  if (!row) {
    row = await api.post('/graduation/gd-students', {
      studentId: String(profile.id || profile.studentId),
      batchId: String(batchId),
      remark: 'Playwright isolated fixture'
    })
  }

  let current = await readGdStudent(api, row.id)
  const eligibility = String(current?.eligibilityStatus || current?.eligibility?.status || '').toUpperCase()
  if (eligibility !== 'QUALIFIED') {
    try {
      await api.post(`/graduation/gd-students/${row.id}/eligibility`, {
        status: 'QUALIFIED', reason: 'Playwright 独立测试库资格准备'
      })
    } catch (error) {
      if (!expectedStateError(error, [/已经认定/i, /已认定/i, /QUALIFIED/i, /无需重复/i, /状态/i])) throw error
    }
    current = await readGdStudent(api, row.id)
  }

  const latestEligibility = String(current?.eligibilityStatus || current?.eligibility?.status || '').toUpperCase()
  if (latestEligibility !== 'QUALIFIED') {
    throw new Error(`E2E graduation student ${row.id} eligibility did not read back as QUALIFIED; got ${latestEligibility || 'EMPTY'}.`)
  }
  return current
}

async function ensureMentor(api) {
  const rows = items(await api.get('/graduation/gd-mentors', {
    keyword: config.mentor.username, page: 1, pageSize: 200
  }))
  let mentor = rows.find((item) => item.teacherNo === config.mentor.username)
  if (!mentor) {
    mentor = await api.post('/graduation/gd-mentors', {
      teacherNo: config.mentor.username,
      teacherName: 'E2E指导教师A',
      mentorType: 'INTERNAL',
      title: '讲师',
      researchDirection: '软件工程测试',
      maxCapacity: 20,
      submitReview: true,
      remark: 'Playwright isolated fixture'
    })
  }
  if (!['QUALIFIED', 'APPROVED'].includes(String(mentor.qualificationStatus || mentor.reviewStatus || '').toUpperCase())) {
    try {
      await api.post(`/graduation/gd-mentors/${mentor.id}/review`, {
        action: 'APPROVE', comment: 'Playwright 独立测试库导师资格通过'
      })
    } catch (error) {
      if (!expectedStateError(error, [/已审核/i, /无需审核/i, /状态/i, /APPROVED/i, /QUALIFIED/i])) throw error
    }
    mentor = items(await api.get('/graduation/gd-mentors', {
      keyword: config.mentor.username, page: 1, pageSize: 200
    })).find((item) => item.teacherNo === config.mentor.username) || mentor
  }
  return mentor
}

async function ensureTopic(api, batchId, runId) {
  const title = `Playwright 交互测试课题 ${runId}`
  const rows = items(await api.get('/graduation/gd-topics', {
    batchId, keyword: title, archiveView: 'active', page: 1, pageSize: 200
  }))
  let topic = rows.find((item) => item.title === title)
  if (!topic) {
    topic = await api.post('/graduation/gd-topics', {
      title,
      batchId: String(batchId),
      sourceType: 'TEACHER',
      advisorName: 'E2E指导教师A',
      category: '软件工程',
      difficulty: 'MEDIUM',
      requirements: '完成真实浏览器交互测试并保留证据',
      outcome: '测试报告、截图、录像和接口日志',
      capacity: 1,
      submitReview: true
    })
  }
  if (String(topic.reviewStatus || '').toUpperCase() !== 'APPROVED') {
    try {
      await api.post(`/graduation/gd-topics/${topic.id}/review`, {
        action: 'APPROVE', comment: 'Playwright 独立测试库课题审核通过'
      })
    } catch (error) {
      if (!expectedStateError(error, [/已审核/i, /无需审核/i, /状态/i, /APPROVED/i])) throw error
    }
    topic = items(await api.get('/graduation/gd-topics', {
      batchId, keyword: title, archiveView: 'active', page: 1, pageSize: 200
    })).find((item) => item.title === title) || topic
  }
  return topic
}

async function ensureMentorAssignment(api, gdStudent, mentor) {
  let current = await readGdStudent(api, gdStudent.id)
  const sameMentor = String(current?.mentorId || '') === String(mentor.id)
    || String(current?.advisorName || '') === String(mentor.teacherName || 'E2E指导教师A')
  if (!sameMentor) {
    try {
      await api.post('/graduation/gd-mentor-assignments/assign', {
        gdStudentId: String(gdStudent.id),
        mentorId: String(mentor.id),
        reason: 'Playwright 学生—导师—管理员完整流程'
      })
    } catch (error) {
      if (!expectedStateError(error, [/已分配/i, /已有导师/i, /重复/i, /ACTIVE/i, /存在/i])) throw error
    }
    current = await readGdStudent(api, gdStudent.id)
  }
  if (!current?.advisorName) throw new Error(`E2E mentor assignment for student ${gdStudent.id} was not visible after readback.`)
  return current
}

async function ensureTopicAssignment(api, gdStudent, topic) {
  let current = await readGdStudent(api, gdStudent.id)
  if (String(current?.topicId || '') !== String(topic.id)) {
    try {
      await api.post(`/graduation/gd-students/${gdStudent.id}/assign-topic`, { topicId: String(topic.id) })
    } catch (error) {
      if (!expectedStateError(error, [/已分配/i, /重复/i, /已选/i, /存在/i])) throw error
    }
    current = await readGdStudent(api, gdStudent.id)
  }
  if (String(current?.topicId || '') !== String(topic.id)) {
    throw new Error(`E2E topic assignment for student ${gdStudent.id} did not read back topic ${topic.id}.`)
  }
  return current
}

export async function prepareGraduationFixture({
  studentAccount = config.student,
  fixtureKey = ''
} = {}) {
  const rawRun = process.env.GITHUB_RUN_ID || `${Date.now()}`
  const runId = fixtureIdentity(rawRun, fixtureKey)
  const studentNo = String(studentAccount?.username || '').trim()
  if (!studentNo) throw new Error('Graduation fixture requires a student account username.')
  const admin = await loginApi(config.sandboxAdmin)

  const batch = await ensureBatch(admin, runId)
  const profile = await findStudentProfile(admin, studentNo)
  let gdStudent = await ensureGdStudent(admin, batch.id, profile, studentNo)
  const mentor = await ensureMentor(admin)
  gdStudent = await ensureMentorAssignment(admin, gdStudent, mentor)

  const topic = await ensureTopic(admin, batch.id, runId)
  gdStudent = await ensureTopicAssignment(admin, gdStudent, topic)

  const existingTaskbook = await admin.get(`/graduation/gd-taskbooks/${gdStudent.id}`, {
    batchId: String(batch.id)
  })
  if (!existingTaskbook?.exists) {
    await admin.post(`/graduation/gd-taskbooks/${gdStudent.id}/issue`, {
      objective: '验证毕业设计学生、导师、管理员真实交互闭环',
      content: '学生签署任务书并提交开题，导师驳回后学生重交，导师通过，管理员复核。'
    }, { batchId: String(batch.id) })
  }

  return {
    runId,
    fixtureKey: String(fixtureKey || ''),
    studentAccount: { ...studentAccount },
    batchId: String(batch.id),
    batchName: batch.batchName,
    gdStudentId: String(gdStudent.id),
    studentNo,
    mentorName: mentor.teacherName || 'E2E指导教师A',
    mentorId: String(mentor.id),
    topicId: String(topic.id),
    topicTitle: topic.title
  }
}
