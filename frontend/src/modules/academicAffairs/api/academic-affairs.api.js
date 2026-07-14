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
import { request, requestBlob, shouldTryReal, currentUserFromToken } from '@/services/http/client'
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

  /* ── 成绩（R1 九态：录入→提交→学院审→教务发布→[更正两级审]→归档） ── */
  createGradeTask(body) {
    return call(() => request(`${BASE}/grade-tasks`, { method: 'POST', body }))
  },
  getGradeTasks(params = {}) {
    return callList(`${BASE}/grade-tasks`, params)
  },
  getGradeRoster(taskId) {
    return call(() => request(`${BASE}/grade-tasks/${taskId}/roster`))
  },
  enterScore(taskId, body) {
    return call(() => request(`${BASE}/grade-tasks/${taskId}/scores`, { method: 'POST', body }))
  },
  submitGradeTask(taskId) {
    return call(() => request(`${BASE}/grade-tasks/${taskId}/submit`, { method: 'POST' }))
  },
  collegeReviewGrade(taskId, action, reason) {
    return call(() => request(`${BASE}/grade-tasks/${taskId}/college-review`, { method: 'POST', body: { action, reason } }))
  },
  publishGrades(taskId) {
    return call(() => request(`${BASE}/grade-tasks/${taskId}/publish`, { method: 'POST' }))
  },
  returnGradeTask(taskId, reason) {
    return call(() => request(`${BASE}/grade-tasks/${taskId}/return`, { method: 'POST', body: { reason } }))
  },
  archiveGradeTask(taskId) {
    return call(() => request(`${BASE}/grade-tasks/${taskId}/archive`, { method: 'POST' }))
  },
  requestGradeChange(taskId, recordId, body) {
    return call(() => request(`${BASE}/grade-tasks/${taskId}/records/${recordId}/change-request`, { method: 'POST', body }))
  },
  changeCollegeReview(recordId, action, reason) {
    return call(() => request(`${BASE}/grade-change/${recordId}/college-review`, { method: 'POST', body: { action, reason } }))
  },
  changeAcademicReview(recordId, action, reason) {
    return call(() => request(`${BASE}/grade-change/${recordId}/academic-review`, { method: 'POST', body: { action, reason } }))
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
  },

  /* ── 教务统计（只读聚合：11 项指标 + 多维筛选 + 下钻明细 + 导出） ── */
  getStatsOverview(params = {}) {
    return call(() => request(`${BASE}/stats/overview`, { params }))
  },
  getStatsFilters() {
    return call(() => request(`${BASE}/stats/filters`))
  },
  getStatsRegistration(params = {}) {
    return callList(`${BASE}/stats/registration`, params)
  },
  getStatsStatusChange(params = {}) {
    return callList(`${BASE}/stats/status-change`, params)
  },
  getStatsWarning(params = {}) {
    return callList(`${BASE}/stats/warning`, params)
  },
  /** 导出总览 xlsx（同步下载）：返回 Blob；purpose 必填（≥5 字）。 */
  async exportStats(body = {}) {
    try {
      const blob = await requestBlob(`${BASE}/stats/export`, { method: 'POST', body })
      return ok(blob)
    } catch (e) {
      return toErr(e)
    }
  },

  /* ── 教学资源 · 教室字典（R4 · /academic-affairs/classrooms/*；细粒度权限 academicAffairs.classroom.*） ── */
  listClassrooms({ keyword = '', buildingCode = '', roomType = '', status = '', page = 1, pageSize = 20 } = {}) {
    const params = { page, pageSize }
    if (keyword) params.keyword = keyword
    if (buildingCode) params.buildingCode = buildingCode
    if (roomType) params.roomType = roomType
    if (status) params.status = status
    return call(() => request(`${BASE}/classrooms`, { params }))
  },
  getClassroomOptions(keyword = '') {
    const params = keyword ? { keyword } : {}
    return call(() => request(`${BASE}/classrooms/options`, { params }))
  },
  getClassroom(id) {
    return call(() => request(`${BASE}/classrooms/${id}`))
  },
  createClassroom(body) {
    return call(() => request(`${BASE}/classrooms`, { method: 'POST', body }))
  },
  updateClassroom(id, body) {
    return call(() => request(`${BASE}/classrooms/${id}`, { method: 'PUT', body }))
  },
  setClassroomStatus(id, status, reason = '') {
    return call(() => request(`${BASE}/classrooms/${id}/status`, { method: 'POST', body: { status, reason } }))
  },
  deleteClassroom(id) {
    return call(() => request(`${BASE}/classrooms/${id}`, { method: 'DELETE' }))
  }
}

/* ═══════════ 学院专业班级（组织架构，R3 · /academic-affairs/orgs/*） ═══════════
 * 读=academicAffairs.org.view，写=academicAffairs.org.manage；数据范围经后端 build_affairs_context 收敛。 */
export const academicAffairsOrgApi = {
  // ── 学院 ──
  listColleges(params = {}) { return callList(`${BASE}/orgs/colleges`, params) },
  createCollege(body) { return call(() => request(`${BASE}/orgs/colleges`, { method: 'POST', body })) },
  updateCollege(id, body) { return call(() => request(`${BASE}/orgs/colleges/${id}`, { method: 'PUT', body })) },
  deleteCollege(id) { return call(() => request(`${BASE}/orgs/colleges/${id}`, { method: 'DELETE' })) },
  bindSecretary(id, secretaryId) {
    return call(() => request(`${BASE}/orgs/colleges/${id}/secretary`, { method: 'POST', body: { secretaryId } }))
  },
  // ── 专业 ──
  listMajors(params = {}) { return callList(`${BASE}/orgs/majors`, params) },
  createMajor(body) { return call(() => request(`${BASE}/orgs/majors`, { method: 'POST', body })) },
  updateMajor(id, body) { return call(() => request(`${BASE}/orgs/majors/${id}`, { method: 'PUT', body })) },
  deleteMajor(id) { return call(() => request(`${BASE}/orgs/majors/${id}`, { method: 'DELETE' })) },
  // ── 行政班 ──
  listClasses(params = {}) { return callList(`${BASE}/orgs/classes`, params) },
  createClass(body) { return call(() => request(`${BASE}/orgs/classes`, { method: 'POST', body })) },
  updateClass(id, body) { return call(() => request(`${BASE}/orgs/classes/${id}`, { method: 'PUT', body })) },
  deleteClass(id) { return call(() => request(`${BASE}/orgs/classes/${id}`, { method: 'DELETE' })) },
  // ── 年级 / 教学班 / 班级学生 / 班级调整 ──
  listGrades(params = {}) { return call(() => request(`${BASE}/orgs/grades`, { params })) },
  listTeachingClasses(params = {}) { return callList(`${BASE}/orgs/teaching-classes`, params) },
  listClassStudents(classId, params = {}) { return callList(`${BASE}/orgs/classes/${classId}/students`, params) },
  adjustClass(body) { return call(() => request(`${BASE}/orgs/class-adjustments`, { method: 'POST', body })) },
  // ── 组织树 / 统计 / 变更审计 ──
  orgTree() { return call(() => request(`${BASE}/orgs/tree`)) },
  orgStats() { return call(() => request(`${BASE}/orgs/stats`)) },
  listAudit(params = {}) { return callList(`${BASE}/orgs/audit`, params) }
}

/* ═══════════ 选课管理（SM-09 · /academic-affairs/selection/*） ═══════════
 * 教务处管理批次/课程/规则/锁定；学生自助选课/退课/我的选课；补选指引+统计。 */
export const academicAffairsSelectionApi = {
  // ── 批次 ──
  listBatches(params = {}) { return callList(`${BASE}/selection/batches`, params) },
  getBatch(id) { return call(() => request(`${BASE}/selection/batches/${id}`)) },
  createBatch(body) { return call(() => request(`${BASE}/selection/batches`, { method: 'POST', body })) },
  publishBatch(id) { return call(() => request(`${BASE}/selection/batches/${id}/publish`, { method: 'POST' })) },
  openBatch(id) { return call(() => request(`${BASE}/selection/batches/${id}/open`, { method: 'POST' })) },
  closeBatch(id) { return call(() => request(`${BASE}/selection/batches/${id}/close`, { method: 'POST' })) },
  lockBatch(id) { return call(() => request(`${BASE}/selection/batches/${id}/lock`, { method: 'POST' })) },
  archiveBatch(id) { return call(() => request(`${BASE}/selection/batches/${id}/archive`, { method: 'POST' })) },
  saveRule(id, rule) { return call(() => request(`${BASE}/selection/batches/${id}/rule`, { method: 'PUT', body: { rule } })) },
  // ── 课程供给 ──
  listCourses(id, params = {}) { return callList(`${BASE}/selection/batches/${id}/courses`, params) },
  addCourse(id, body) { return call(() => request(`${BASE}/selection/batches/${id}/courses`, { method: 'POST', body })) },
  updateCourse(courseId, body) { return call(() => request(`${BASE}/selection/courses/${courseId}`, { method: 'PUT', body })) },
  cancelCourse(courseId) { return call(() => request(`${BASE}/selection/courses/${courseId}/cancel`, { method: 'POST' })) },
  courseRoster(courseId, params = {}) { return callList(`${BASE}/selection/courses/${courseId}/roster`, params) },
  // ── 学生自助 ──
  studentCourses(batchId) { return call(() => request(`${BASE}/selection/student/courses`, { params: batchId ? { batchId } : {} })) },
  enroll(selectionCourseId) { return call(() => request(`${BASE}/selection/student/enroll`, { method: 'POST', body: { selectionCourseId } })) },
  drop(selectionCourseId) { return call(() => request(`${BASE}/selection/student/drop`, { method: 'POST', body: { selectionCourseId } })) },
  mySelections(batchId) { return call(() => request(`${BASE}/selection/student/my`, { params: batchId ? { batchId } : {} })) },
  // ── 教务处调整 / 补选 / 统计 ──
  adjustRecord(recordId, reason) { return call(() => request(`${BASE}/selection/records/${recordId}/adjust`, { method: 'POST', body: { reason } })) },
  reselectGuide(id) { return call(() => request(`${BASE}/selection/batches/${id}/reselect-guide`)) },
  batchStats(id) { return call(() => request(`${BASE}/selection/batches/${id}/stats`)) }
}

/* ═══════════ 考务管理（SM-10 · /academic-affairs/exam/*、/deferred-exams*） ═══════════ */
export const academicAffairsExamApi = {
  // 批次
  listBatches(params = {}) { return callList(`${BASE}/exam/batches`, params) },
  getBatch(id) { return call(() => request(`${BASE}/exam/batches/${id}`)) },
  createBatch(body) { return call(() => request(`${BASE}/exam/batches`, { method: 'POST', body })) },
  addCourse(id, teachingTaskId) { return call(() => request(`${BASE}/exam/batches/${id}/courses`, { method: 'POST', body: { teachingTaskId } })) },
  listCourses(id, params = {}) { return callList(`${BASE}/exam/batches/${id}/courses`, params) },
  confirmCourse(cid, action) { return call(() => request(`${BASE}/exam/courses/${cid}/confirm`, { method: 'POST', body: { action } })) },
  setSchedule(cid, body) { return call(() => request(`${BASE}/exam/courses/${cid}/schedule`, { method: 'PUT', body })) },
  confirmBatchCourses(id) { return call(() => request(`${BASE}/exam/batches/${id}/confirm-courses`, { method: 'POST' })) },
  publishBatch(id) { return call(() => request(`${BASE}/exam/batches/${id}/publish`, { method: 'POST' })) },
  finishBatch(id) { return call(() => request(`${BASE}/exam/batches/${id}/finish`, { method: 'POST' })) },
  archiveBatch(id) { return call(() => request(`${BASE}/exam/batches/${id}/archive`, { method: 'POST' })) },
  // 考场 / 座位 / 监考
  addRoom(cid, body) { return call(() => request(`${BASE}/exam/courses/${cid}/rooms`, { method: 'POST', body })) },
  listRooms(cid) { return call(() => request(`${BASE}/exam/courses/${cid}/rooms`)) },
  assignSeats(roomId, studentIds) { return call(() => request(`${BASE}/exam/rooms/${roomId}/seats`, { method: 'POST', body: { studentIds } })) },
  roomSeats(roomId) { return call(() => request(`${BASE}/exam/rooms/${roomId}/seats`)) },
  addInvigilator(roomId, body) { return call(() => request(`${BASE}/exam/rooms/${roomId}/invigilators`, { method: 'POST', body })) },
  listInvigilators(roomId) { return call(() => request(`${BASE}/exam/rooms/${roomId}/invigilators`)) },
  // 异常 / 统计
  recordIncident(body) { return call(() => request(`${BASE}/exam/incidents`, { method: 'POST', body })) },
  listIncidents(params = {}) { return callList(`${BASE}/exam/incidents`, params) },
  batchStats(id) { return call(() => request(`${BASE}/exam/batches/${id}/stats`)) },
  // 缓考
  deferList(params = {}) { return callList(`${BASE}/deferred-exams`, params) },
  deferCounselorReview(id, action, reason = '') { return call(() => request(`${BASE}/deferred-exams/${id}/counselor-review`, { method: 'POST', body: { action, reason } })) },
  deferReview(id, action, reason = '') { return call(() => request(`${BASE}/deferred-exams/${id}/review`, { method: 'POST', body: { action, reason } })) },
  // 学生
  deferApply(body) { return call(() => request(`${BASE}/deferred-exams`, { method: 'POST', body })) },
  deferMy(params = {}) { return call(() => request(`${BASE}/deferred-exams/my`, { params })) },
  deferResubmit(id) { return call(() => request(`${BASE}/deferred-exams/${id}/resubmit`, { method: 'POST' })) }
}

/* ═══════════ 补考重修缓考免修（SM-12 · /academic-affairs/makeup|retake|exemption/*） ═══════════ */
export const academicAffairsMakeupApi = {
  // 补考
  makeupPending(params = {}) { return callList(`${BASE}/makeup/pending`, params) },
  listBatches(params = {}) { return callList(`${BASE}/makeup/batches`, params) },
  createBatch(body) { return call(() => request(`${BASE}/makeup/batches`, { method: 'POST', body })) },
  enroll(bid, body) { return call(() => request(`${BASE}/makeup/batches/${bid}/enroll`, { method: 'POST', body })) },
  publishBatch(bid) { return call(() => request(`${BASE}/makeup/batches/${bid}/publish`, { method: 'POST' })) },
  score(mid, score) { return call(() => request(`${BASE}/makeup/records/${mid}/score`, { method: 'POST', body: { score } })) },
  finishBatch(bid) { return call(() => request(`${BASE}/makeup/batches/${bid}/finish`, { method: 'POST' })) },
  stats() { return call(() => request(`${BASE}/makeup/stats`)) },
  // 重修
  retakeApply(body) { return call(() => request(`${BASE}/retake/apply`, { method: 'POST', body })) },
  retakeMy(params = {}) { return call(() => request(`${BASE}/retake/my`, { params })) },
  retakeApplies(params = {}) { return callList(`${BASE}/retake/applies`, params) },
  retakeReview(aid, action, reason = '') { return call(() => request(`${BASE}/retake/applies/${aid}/review`, { method: 'POST', body: { action, reason } })) },
  retakeEnroll(aid, teachingTaskRef) { return call(() => request(`${BASE}/retake/applies/${aid}/enroll`, { method: 'POST', body: { teachingTaskRef } })) },
  // 免修
  exemptionApply(body) { return call(() => request(`${BASE}/exemption/apply`, { method: 'POST', body })) },
  exemptionMy(params = {}) { return call(() => request(`${BASE}/exemption/my`, { params })) },
  exemptionApplies(params = {}) { return callList(`${BASE}/exemption/applies`, params) },
  exemptionReview(eid, action, reason = '') { return call(() => request(`${BASE}/exemption/applies/${eid}/review`, { method: 'POST', body: { action, reason } })) },
  // 缓考合流
  deferredPool(params = {}) { return callList(`${BASE}/makeup/deferred-pool`, params) },
  mergeDeferred(did, batchId) { return call(() => request(`${BASE}/makeup/deferred-pool/${did}/merge`, { method: 'POST', body: { batchId } })) }
}

/* ═══════════ 教材管理（/academic-affairs/textbooks/*） ═══════════ */
export const academicAffairsTextbookApi = {
  // 目录
  listTextbooks(params = {}) { return callList(`${BASE}/textbooks`, params) },
  createTextbook(body) { return call(() => request(`${BASE}/textbooks`, { method: 'POST', body })) },
  updateTextbook(id, body) { return call(() => request(`${BASE}/textbooks/${id}`, { method: 'PUT', body })) },
  // 选用
  listSelections(params = {}) { return callList(`${BASE}/textbooks/selections`, params) },
  createSelection(body) { return call(() => request(`${BASE}/textbooks/selections`, { method: 'POST', body })) },
  submitSelection(id) { return call(() => request(`${BASE}/textbooks/selections/${id}/submit`, { method: 'POST' })) },
  withdrawSelection(id) { return call(() => request(`${BASE}/textbooks/selections/${id}/withdraw`, { method: 'POST' })) },
  // 审核
  listReviewBatches(params = {}) { return callList(`${BASE}/textbooks/review-batches`, params) },
  createReviewBatch(body) { return call(() => request(`${BASE}/textbooks/review-batches`, { method: 'POST', body })) },
  reviewAdvance(id, action, reason = '') { return call(() => request(`${BASE}/textbooks/review-batches/${id}/advance`, { method: 'POST', body: { action, reason } })) },
  // 征订
  listOrderBatches(params = {}) { return callList(`${BASE}/textbooks/order-batches`, params) },
  createOrderBatch(body) { return call(() => request(`${BASE}/textbooks/order-batches`, { method: 'POST', body })) },
  orderItems(id) { return call(() => request(`${BASE}/textbooks/order-batches/${id}/items`)) },
  submitOrder(id) { return call(() => request(`${BASE}/textbooks/order-batches/${id}/submit`, { method: 'POST' })) },
  recordArrival(itemId, arrivedQty) { return call(() => request(`${BASE}/textbooks/order-items/${itemId}/arrival`, { method: 'POST', body: { arrivedQty } })) },
  archiveOrder(id) { return call(() => request(`${BASE}/textbooks/order-batches/${id}/archive`, { method: 'POST' })) },
  // 发放
  generateDistribution(body) { return call(() => request(`${BASE}/textbooks/distribution-batches`, { method: 'POST', body })) },
  distributionRecords(id, params = {}) { return callList(`${BASE}/textbooks/distribution-batches/${id}/records`, params) },
  sign(rid) { return call(() => request(`${BASE}/textbooks/distribution-records/${rid}/sign`, { method: 'POST' })) },
  // 费用
  feeLedger(params = {}) { return callList(`${BASE}/textbooks/fee-ledger`, params) },
  markFee(id, action, waiveReason = '') { return call(() => request(`${BASE}/textbooks/fee-ledger/${id}/mark`, { method: 'POST', body: { action, waiveReason } })) },
  // 统计
  stats() { return call(() => request(`${BASE}/textbooks/stats`)) }
}

/* ═══════════ 排课管理增强（SM-07 · /academic-affairs/scheduling/*） ═══════════ */
export const academicAffairsSchedulingApi = {
  listRules(params = {}) { return call(() => request(`${BASE}/scheduling/rules`, { params })) },
  saveRule(body) { return call(() => request(`${BASE}/scheduling/rules`, { method: 'PUT', body })) },
  deleteRule(id) { return call(() => request(`${BASE}/scheduling/rules/${id}`, { method: 'DELETE' })) },
  submitAvailability(body) { return call(() => request(`${BASE}/scheduling/teacher-availability`, { method: 'POST', body })) },
  myAvailability(params = {}) { return call(() => request(`${BASE}/scheduling/teacher-availability/my`, { params })) },
  listAvailability(params = {}) { return call(() => request(`${BASE}/scheduling/teacher-availability`, { params })) },
  reviewAvailability(id, action, reason = '') { return call(() => request(`${BASE}/scheduling/teacher-availability/${id}/review`, { method: 'POST', body: { action, reason } })) },
  conflictReport(batchId) { return call(() => request(`${BASE}/scheduling/batches/${batchId}/conflict-report`)) }
}

/* ═══════════ 教学评价（/academic-affairs/evaluation/*） ═══════════ */
export const academicAffairsEvaluationApi = {
  listBatches(params = {}) { return callList(`${BASE}/evaluation/batches`, params) },
  getBatch(id) { return call(() => request(`${BASE}/evaluation/batches/${id}`)) },
  createBatch(body) { return call(() => request(`${BASE}/evaluation/batches`, { method: 'POST', body })) },
  genTasks(id, teachingTaskIds) { return call(() => request(`${BASE}/evaluation/batches/${id}/tasks`, { method: 'POST', body: { teachingTaskIds } })) },
  listTasks(id, params = {}) { return call(() => request(`${BASE}/evaluation/batches/${id}/tasks`, { params })) },
  publish(id) { return call(() => request(`${BASE}/evaluation/batches/${id}/publish`, { method: 'POST' })) },
  open(id) { return call(() => request(`${BASE}/evaluation/batches/${id}/open`, { method: 'POST' })) },
  closeScore(id) { return call(() => request(`${BASE}/evaluation/batches/${id}/close-score`, { method: 'POST' })) },
  publishResults(id) { return call(() => request(`${BASE}/evaluation/batches/${id}/publish-results`, { method: 'POST' })) },
  archive(id) { return call(() => request(`${BASE}/evaluation/batches/${id}/archive`, { method: 'POST' })) },
  submit(body) { return call(() => request(`${BASE}/evaluation/submit`, { method: 'POST', body })) },
  results(id, params = {}) { return callList(`${BASE}/evaluation/batches/${id}/results`, params) },
  myResults(id) { return call(() => request(`${BASE}/evaluation/batches/${id}/my-results`)) },
  submitAppeal(resultId, reason) { return call(() => request(`${BASE}/evaluation/appeals`, { method: 'POST', body: { resultId, reason } })) },
  listAppeals(params = {}) { return callList(`${BASE}/evaluation/appeals`, params) },
  reviewAppeal(id, action, reason = '') { return call(() => request(`${BASE}/evaluation/appeals/${id}/review`, { method: 'POST', body: { action, reason } })) },
  stats(id) { return call(() => request(`${BASE}/evaluation/batches/${id}/stats`)) }
}

/* ═══════════ 教学质量（零新表 · /academic-affairs/quality/*） ═══════════ */
export const academicAffairsQualityApi = {
  dashboard(params = {}) { return call(() => request(`${BASE}/quality/dashboard`, { params })) },
  reports(params = {}) { return callList(`${BASE}/quality/reports`, params) },
  async exportReport(body = {}) {
    try {
      const blob = await requestBlob(`${BASE}/quality/reports/export`, { method: 'POST', body })
      return ok(blob)
    } catch (e) {
      return toErr(e)
    }
  }
}

export default academicAffairsApi
