/**
 * 教务中心（13B）API —— 生产级：仅走真实后端 /api/v1/academic-affairs/*，不回退 mock（手册 D1）。
 *
 * 契约：所有方法返回 Promise<{ code, data, message }>，code=0 成功；request() 已解包 envelope.data。
 * 与旧「学业过程」模块（同目录 api/academic.api.js，接 /academic/* + mock 兜底）互不干扰、并存。
 *
 * 以代码为准（后端 academic_affairs.py 实测签名）：
 *  - 学期仅有 新建/列表/当前/发布 四端点，无 PUT 更新端点 → 本模块不提供 updateTerm（勘误见施工记录）。
 *  - 学期状态机当前只有 DRAFT / PUBLISHED（FROZEN/ARCHIVED 后端未实现，暂不渲染）。
 */
import { request, shouldTryReal, currentUserFromToken } from '@/services/http/client'
import { setPermissionPatterns } from '@/security/permissionGate'

const BASE = '/academic-affairs'

function ok(data) {
  return Promise.resolve({ code: 0, data, message: 'ok' })
}
function fail(message, code = 1) {
  return Promise.resolve({ code, data: null, message })
}
function toErr(e) {
  if (e?.biz) return fail(e.message, e.code || 1)
  return fail(e?.message || '真实接口不可用', 503001)
}
async function call(fn) {
  try {
    return ok(await fn())
  } catch (e) {
    return toErr(e)
  }
}
async function callList(path, params = {}) {
  try {
    const d = await request(path, { params })
    return ok({ list: d.items || [], total: d.total || 0, page: d.page || 1, pageSize: d.pageSize || 20 })
  } catch (e) {
    return toErr(e)
  }
}

export const academicAffairsApi = {
  /** 布局初始化：品牌 / 角色 / 数据范围（展示用）；真实权限边界始终以后端接口为准。 */
  async getContext() {
    const u = currentUserFromToken() || {}
    let schoolName = '管理端'
    let roleName = '教务管理员'
    let roleCode = u.currentRoleCode || ''
    const scopeName = '本校教务数据（按后端数据范围）'
    let permissionPatterns = null
    try {
      if (shouldTryReal()) {
        const me = await request('/auth/me').catch(() => null)
        const tenantName = me?.tenantName || me?.user?.tenantName || me?.tenant?.name
        if (tenantName) schoolName = tenantName
        const realName = me?.realName || me?.user?.realName
        try {
          const rc = await request('/rbac/current-context')
          if (rc && Array.isArray(rc.permissionPatterns)) {
            permissionPatterns = rc.permissionPatterns
            const cr = rc.currentRole || {}
            if (cr.roleName) roleName = cr.roleName
            if (cr.roleCode) roleCode = cr.roleCode
          }
        } catch {
          /* current-context 不可用：展示降级；后端接口仍是最终权限边界 */
        }
        if (realName) roleName = `${realName} · ${roleName}`
      }
    } catch {
      /* 离线/未登录静默回退，不阻塞布局 */
    }
    // 仅在取到真实 patterns 时落库，避免清空其它模块（如岗位实习）已设的权限投影
    if (permissionPatterns) setPermissionPatterns(permissionPatterns)
    return ok({
      tenantBrandConfig: { schoolName },
      currentRole: { roleName, roleCode },
      dataScope: { scopeName, name: scopeName },
      permissionActions: {},
      permissionPatterns
    })
  },

  /* ── 教务看板 ── */
  getDashboard() {
    return call(() => request(`${BASE}/dashboard`))
  },

  /* ── 学年学期 ── */
  getCurrentTerm() {
    return call(() => request(`${BASE}/terms/current`))
  },
  getTerms(params = {}) {
    return callList(`${BASE}/terms`, params)
  },
  createTerm(body) {
    return call(() => request(`${BASE}/terms`, { method: 'POST', body }))
  },
  publishTerm(termId) {
    return call(() => request(`${BASE}/terms/${termId}/publish`, { method: 'POST' }))
  },

  /* ── 校历 ── */
  getCalendar(termId) {
    return call(async () => {
      const d = await request(`${BASE}/terms/${termId}/calendar`)
      return d.items || []
    })
  },
  addCalendarEvent(termId, body) {
    return call(() => request(`${BASE}/terms/${termId}/calendar`, { method: 'POST', body }))
  },

  /* ── 作息节次 ── */
  getTimeSlots() {
    return call(async () => {
      const d = await request(`${BASE}/time-slots`)
      return d.items || []
    })
  },
  createTimeSlot(body) {
    return call(() => request(`${BASE}/time-slots`, { method: 'POST', body }))
  },

  /* ── 学籍名册（只读脱敏，无独立详情端点） ── */
  getRoster(params = {}) {
    return callList(`${BASE}/roster`, params)
  },

  /* ── 入学 / 学年注册 ── */
  getRegistrationBatches(params = {}) {
    return callList(`${BASE}/registration-batches`, params)
  },
  createRegistrationBatch(body) {
    return call(() => request(`${BASE}/registration-batches`, { method: 'POST', body }))
  },
  getRegistrations(batchId, params = {}) {
    return callList(`${BASE}/registration-batches/${batchId}/registrations`, params)
  },
  registerStudent(batchId, studentId) {
    return call(() => request(`${BASE}/registration-batches/${batchId}/register`, { method: 'POST', body: { studentId } }))
  },

  /* ── 学籍异动（休学/退学/复学/留级/转专业，多节点审批） ── */
  getStatusChanges(params = {}) {
    return callList(`${BASE}/status-changes`, params)
  },
  getStatusChange(changeId) {
    return call(() => request(`${BASE}/status-changes/${changeId}`))
  },
  submitStatusChange(body) {
    return call(() => request(`${BASE}/status-changes`, { method: 'POST', body }))
  },
  reviewStatusChange(changeId, action, reason) {
    return call(() => request(`${BASE}/status-changes/${changeId}/review`, { method: 'POST', body: { action, reason } }))
  },

  /* ── 课程库（两级审核 DRAFT→COLLEGE_REVIEW→ACADEMIC_REVIEW→ENABLED） ── */
  getCourses(params = {}) {
    return callList(`${BASE}/courses`, params)
  },
  getCourse(courseId) {
    return call(() => request(`${BASE}/courses/${courseId}`))
  },
  createCourse(body) {
    return call(() => request(`${BASE}/courses`, { method: 'POST', body }))
  },
  updateCourse(courseId, body) {
    return call(() => request(`${BASE}/courses/${courseId}`, { method: 'PUT', body }))
  },
  submitCourse(courseId) {
    return call(() => request(`${BASE}/courses/${courseId}/submit`, { method: 'POST' }))
  },
  reviewCourse(courseId, action, reason) {
    return call(() => request(`${BASE}/courses/${courseId}/review`, { method: 'POST', body: { action, reason } }))
  },

  /* ── 培养方案（编制 → 两级审 → PUBLISHED → 绑年级） ── */
  getPrograms(params = {}) {
    return callList(`${BASE}/programs`, params)
  },
  getProgram(programId) {
    return call(() => request(`${BASE}/programs/${programId}`))
  },
  createProgram(body) {
    return call(() => request(`${BASE}/programs`, { method: 'POST', body }))
  },
  updateProgram(programId, body) {
    return call(() => request(`${BASE}/programs/${programId}`, { method: 'PUT', body }))
  },
  addProgramCourse(programId, body) {
    return call(() => request(`${BASE}/programs/${programId}/courses`, { method: 'POST', body }))
  },
  submitProgram(programId) {
    return call(() => request(`${BASE}/programs/${programId}/submit`, { method: 'POST' }))
  },
  reviewProgram(programId, action, reason) {
    return call(() => request(`${BASE}/programs/${programId}/review`, { method: 'POST', body: { action, reason } }))
  },
  bindProgramGrade(programId, gradeYear, classId) {
    return call(() => request(`${BASE}/programs/${programId}/bind`, { method: 'POST', body: { gradeYear, classId } }))
  },

  /* ── 教学任务（生成 → 分配 → 教师确认 → 提审） ── */
  generateTaskBatch(body) {
    return call(() => request(`${BASE}/teaching-task-batches/generate`, { method: 'POST', body }))
  },
  getTaskBatches(params = {}) {
    return callList(`${BASE}/teaching-task-batches`, params)
  },
  submitTaskBatch(batchId) {
    return call(() => request(`${BASE}/teaching-task-batches/${batchId}/submit`, { method: 'POST' }))
  },
  getBatchTasks(batchId, params = {}) {
    return callList(`${BASE}/teaching-task-batches/${batchId}/tasks`, params)
  },
  assignTeacher(taskId, body) {
    return call(() => request(`${BASE}/teaching-tasks/${taskId}/assign`, { method: 'POST', body }))
  },
  teacherActTask(taskId, action, reason) {
    return call(() => request(`${BASE}/teaching-tasks/${taskId}/teacher-act`, { method: 'POST', body: { action, reason } }))
  },

  /* ── 课表（三重冲突检测 + 单双周 + 三视图 + 发布） ── */
  getScheduleBatches(params = {}) {
    return callList(`${BASE}/schedule-batches`, params)
  },
  createScheduleBatch(body) {
    return call(() => request(`${BASE}/schedule-batches`, { method: 'POST', body }))
  },
  addScheduleItem(batchId, body) {
    return call(() => request(`${BASE}/schedule-batches/${batchId}/items`, { method: 'POST', body }))
  },
  importSchedule(batchId, items) {
    return call(() => request(`${BASE}/schedule-batches/${batchId}/import`, { method: 'POST', body: { items } }))
  },
  prePublishSchedule(batchId) {
    return call(() => request(`${BASE}/schedule-batches/${batchId}/pre-publish`, { method: 'POST' }))
  },
  publishSchedule(batchId) {
    return call(() => request(`${BASE}/schedule-batches/${batchId}/publish`, { method: 'POST' }))
  },
  voidReissueSchedule(batchId, reason) {
    return call(() => request(`${BASE}/schedule-batches/${batchId}/void-reissue`, { method: 'POST', body: { reason } }))
  },
  getScheduleClassView(batchId, classId) {
    return call(() => request(`${BASE}/schedule-batches/${batchId}/class-view`, { params: { classId } }))
  },
  getScheduleTeacherView(batchId, teacherKey) {
    return call(() => request(`${BASE}/schedule-batches/${batchId}/teacher-view`, { params: { teacherKey } }))
  },
  getScheduleStudentView(batchId, studentId) {
    return call(() => request(`${BASE}/schedule-batches/${batchId}/student-view`, { params: { studentId } }))
  },

  /* ── 成绩（录入任务 → 录分 → 发布；读侧总览/挂科/成绩单） ── */
  createGradeTask(body) {
    return call(() => request(`${BASE}/grade-tasks`, { method: 'POST', body }))
  },
  enterScore(taskId, body) {
    return call(() => request(`${BASE}/grade-tasks/${taskId}/scores`, { method: 'POST', body }))
  },
  publishGrades(taskId) {
    return call(() => request(`${BASE}/grade-tasks/${taskId}/publish`, { method: 'POST' }))
  },
  getTranscript(studentId) {
    return call(() => request(`${BASE}/students/${studentId}/transcript`))
  },
  getFailList(params = {}) {
    return callList(`${BASE}/grade-views/fail-list`, params)
  },
  getGradeAnalysis(term) {
    return call(() => request(`${BASE}/grade-views/analysis`, { params: term ? { term } : {} }))
  },

  /* ── 学业预警（扫描 + 列表） ── */
  scanWarnings() {
    return call(() => request(`${BASE}/warnings/scan`, { method: 'POST' }))
  },
  getWarnings(params = {}) {
    return callList(`${BASE}/warnings`, params)
  },

  /* ── 毕业资格预审（批次 → 圈定 → 七项预审 → 学院初审 → 教务终审） ── */
  createGradBatch(body) {
    return call(() => request(`${BASE}/graduation-audit-batches`, { method: 'POST', body }))
  },
  generateGradStudents(batchId, studentIds) {
    return call(() => request(`${BASE}/graduation-audit-batches/${batchId}/generate`, { method: 'POST', body: { studentIds } }))
  },
  precheckGrad(batchId) {
    return call(() => request(`${BASE}/graduation-audit-batches/${batchId}/precheck`, { method: 'POST' }))
  },
  getGradResults(batchId, params = {}) {
    return callList(`${BASE}/graduation-audit-batches/${batchId}/results`, params)
  },
  getGradRosters(batchId) {
    return call(() => request(`${BASE}/graduation-audit-batches/${batchId}/rosters`))
  },
  getGradResult(resultId) {
    return call(() => request(`${BASE}/graduation-results/${resultId}`))
  },
  collegeReviewGrad(resultId, action, note) {
    return call(() => request(`${BASE}/graduation-results/${resultId}/college-review`, { method: 'POST', body: { action, note } }))
  },
  finalGrad(resultId, conclusion, confirm) {
    return call(() => request(`${BASE}/graduation-results/${resultId}/final`, { method: 'POST', body: { conclusion, confirm } }))
  }
}

export default academicAffairsApi
