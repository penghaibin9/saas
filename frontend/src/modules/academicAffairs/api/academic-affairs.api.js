/**
 * 教务中心（13B）API —— 生产级：仅走真实后端 /api/v1/academic-affairs/*，不回退 mock（手册 D1）。
 *
 * 契约：所有方法返回 Promise<{ code, data, message }>，code=0 成功；request() 已解包 envelope.data。
 * 与旧「学业过程」模块（同目录 api/academic.api.js，接 /academic/* + mock 兜底）互不干扰、并存。
 *
 * 以代码为准（后端 academic_affairs.py 实测签名）：
 *  - 学期基础字段（学年/学期号/名称/起止日期）仅有 新建/列表/当前/发布 四端点，无 PUT 更新端点 →
 *    本模块不提供 updateTerm（勘误见施工记录）。
 *  - 学期状态机 DRAFT→PUBLISHED→FROZEN→ARCHIVED 全 4 态：DRAFT/PUBLISHED 走 create/publish；
 *    FROZEN 走 Tier1-R2 新增 freeze/unfreeze（学期状态）；ARCHIVED 由「教务归档」二级模块
 *    academic_affairs_archive_service 的批次确认归档写入，本模块 getTermArchiveOverview 仅只读联动。
 */
import { request, requestBlob, requestUpload, shouldTryReal, currentUserFromToken } from '@/services/http/client'
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
  /** 教务看板提醒聚合：成绩提交进度/考试安排/学籍异动/学业预警/毕业资格预警/教务待办（P4 六卡，零新表只读聚合）。 */
  getDashboardReminders() {
    return call(() => request(`${BASE}/dashboard/reminders`))
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

  /* ── 学年学期 Tier1-R2：当前学期设置 / 学期周次 / 教学周配置 / 学期状态 / 学期归档总览 ── */
  setCurrentTerm(termId) {
    return call(() => request(`${BASE}/terms/${termId}/set-current`, { method: 'POST' }))
  },
  getTermDetail(termId) {
    return call(() => request(`${BASE}/terms/${termId}`))
  },
  getTermWeeks(termId) {
    return call(async () => (await request(`${BASE}/terms/${termId}/weeks`)).items || [])
  },
  updateTeachingWeeks(termId, body) {
    return call(() => request(`${BASE}/terms/${termId}/teaching-weeks`, { method: 'PUT', body }))
  },
  freezeTerm(termId) {
    return call(() => request(`${BASE}/terms/${termId}/freeze`, { method: 'POST' }))
  },
  unfreezeTerm(termId, reason) {
    return call(() => request(`${BASE}/terms/${termId}/unfreeze`, { method: 'POST', body: { reason } }))
  },
  getTermArchiveOverview() {
    return call(async () => (await request(`${BASE}/terms/archive-overview`)).items || [])
  },

  /* ── 校历（校历节次 Tier1 R2：节假日/补课日=按 eventType 过滤同一批事件；发布走学期状态机，
     归档统一走教务归档模块正规批次流程，本模块不提供直写归档端点） ── */
  getCalendar(termId, eventType) {
    return call(async () => {
      const d = await request(`${BASE}/terms/${termId}/calendar`, { params: eventType ? { eventType } : {} })
      return d.items || []
    })
  },
  addCalendarEvent(termId, body) {
    return call(() => request(`${BASE}/terms/${termId}/calendar`, { method: 'POST', body }))
  },
  updateCalendarEvent(termId, eventId, body) {
    return call(() => request(`${BASE}/terms/${termId}/calendar/${eventId}`, { method: 'PUT', body }))
  },
  deleteCalendarEvent(termId, eventId) {
    return call(() => request(`${BASE}/terms/${termId}/calendar/${eventId}`, { method: 'DELETE' }))
  },
  getWeekCalendar(termId) {
    return call(() => request(`${BASE}/terms/${termId}/week-calendar`))
  },
  publishCalendar(termId) {
    return call(() => request(`${BASE}/terms/${termId}/calendar/publish`, { method: 'POST' }))
  },

  /* ── 作息节次（节次管理，全校统一） ── */
  getTimeSlots(includeDisabled = false) {
    return call(async () => {
      const d = await request(`${BASE}/time-slots`, { params: includeDisabled ? { includeDisabled: true } : {} })
      return d.items || []
    })
  },
  createTimeSlot(body) {
    return call(() => request(`${BASE}/time-slots`, { method: 'POST', body }))
  },
  updateTimeSlot(slotId, body) {
    return call(() => request(`${BASE}/time-slots/${slotId}`, { method: 'PUT', body }))
  },
  deleteTimeSlot(slotId) {
    return call(() => request(`${BASE}/time-slots/${slotId}`, { method: 'DELETE' }))
  },

  /* ── 上课时间段（节次的实际钟点，支持按校区/生效日期区间配置多套作息） ── */
  getTimeBands(slotId) {
    return call(async () => {
      const d = await request(`${BASE}/time-slots/${slotId}/time-bands`)
      return d.items || []
    })
  },
  createTimeBand(slotId, body) {
    return call(() => request(`${BASE}/time-slots/${slotId}/time-bands`, { method: 'POST', body }))
  },
  updateTimeBand(bandId, body) {
    return call(() => request(`${BASE}/time-bands/${bandId}`, { method: 'PUT', body }))
  },
  deleteTimeBand(bandId) {
    return call(() => request(`${BASE}/time-bands/${bandId}`, { method: 'DELETE' }))
  },

  /* ── 学籍名册（只读脱敏） ── */
  getRoster(params = {}) {
    return callList(`${BASE}/roster`, params)
  },

  /* ── 学籍档案 / 学籍状态 / 学籍导入导出（Tier1 R2） ── */
  getRosterDetail(studentId) {
    return call(() => request(`${BASE}/roster/${studentId}`))
  },
  revealRosterSensitive(studentId, reason) {
    return call(() => request(`${BASE}/roster/${studentId}/reveal`, { method: 'POST', body: { reason } }))
  },
  getRosterStatusSummary() {
    return call(() => request(`${BASE}/roster/status-summary`))
  },
  async exportRoster(body = {}) {
    try {
      const blob = await requestBlob(`${BASE}/roster/export`, { method: 'POST', body })
      return ok(blob)
    } catch (e) {
      return toErr(e)
    }
  },
  rosterImportDryRun(rows) {
    return call(() => request(`${BASE}/roster/import/dry-run`, { method: 'POST', body: { rows } }))
  },
  async downloadRosterImportTemplate() {
    const blob = await requestBlob(`${BASE}/roster/import/template`)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = '学籍导入模板.xlsx'
    a.click()
    URL.revokeObjectURL(url)
  },
  async uploadRosterImportXlsx(file) {
    try {
      return ok(await requestUpload(`${BASE}/roster/import/xlsx`, file))
    } catch (e) {
      return toErr(e)
    }
  },
  downloadRosterImportErrors(rows, errors) {
    return call(() => request(`${BASE}/roster/import/errors-xlsx`, { method: 'POST', body: { rows, errors } }))
  },
  rosterImportConfirm(rows) {
    return call(() => request(`${BASE}/roster/import/confirm`, { method: 'POST', body: { rows } }))
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

  /* ── 注册归档（续工三级卡 · academicAffairs.registration.archive.*） ── */
  closeRegistrationBatch(batchId) {
    return call(() => request(`${BASE}/registration-batches/${batchId}/close`, { method: 'POST' }))
  },
  archiveRegistrationBatch(batchId) {
    return call(() => request(`${BASE}/registration-batches/${batchId}/archive`, { method: 'POST' }))
  },
  getArchivedRegistrationBatches(params = {}) {
    return callList(`${BASE}/registration/archive`, params)
  },
  getRegistrationArchiveDetail(batchId) {
    return call(() => request(`${BASE}/registration/archive/${batchId}`))
  },
  async exportRegistrationArchive(batchId, purpose) {
    try {
      const blob = await requestBlob(`${BASE}/registration/archive/${batchId}/export`, { method: 'POST', body: { purpose } })
      return ok(blob)
    } catch (e) {
      return toErr(e)
    }
  },

  /* ── 注册资格核验（Tier1 R1 · academicAffairs.registration.eligibility.*） ── */
  getRegistrationEligibility(batchId, params = {}) {
    return callList(`${BASE}/registration-batches/${batchId}/eligibility`, params)
  },
  verifyRegistrationEligibility(batchId, studentId, body) {
    return call(() => request(`${BASE}/registration-batches/${batchId}/eligibility/${studentId}/verify`, { method: 'POST', body }))
  },

  /* ── 未注册学生（Tier1 R1 · academicAffairs.registration.unregistered.*） ── */
  getUnregisteredStudents(params = {}) {
    return callList(`${BASE}/registration/unregistered`, params)
  },
  scanUnregistered(batchId) {
    return call(() => request(`${BASE}/registration-batches/${batchId}/scan-unregistered`, { method: 'POST' }))
  },
  async exportUnregistered(body = {}) {
    try {
      const blob = await requestBlob(`${BASE}/registration/unregistered/export`, { method: 'POST', body })
      return ok(blob)
    } catch (e) {
      return toErr(e)
    }
  },

  /* ── 暂缓注册（Tier1 R1 · academicAffairs.registration.deferral.*） ── */
  applyRegistrationDeferral(batchId, body) {
    return call(() => request(`${BASE}/registration-batches/${batchId}/deferrals`, { method: 'POST', body }))
  },
  getRegistrationDeferrals(params = {}) {
    return callList(`${BASE}/registration/deferrals`, params)
  },
  reviewRegistrationDeferral(deferralId, body) {
    return call(() => request(`${BASE}/registration/deferrals/${deferralId}/review`, { method: 'POST', body }))
  },

  /* ── 注册异常（Tier1 R1 · academicAffairs.registration.exception.*） ── */
  createRegistrationException(batchId, body) {
    return call(() => request(`${BASE}/registration-batches/${batchId}/exceptions`, { method: 'POST', body }))
  },
  getRegistrationExceptions(params = {}) {
    return callList(`${BASE}/registration/exceptions`, params)
  },
  resolveRegistrationException(exceptionId, note) {
    return call(() => request(`${BASE}/registration/exceptions/${exceptionId}/resolve`, { method: 'POST', body: { note } }))
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
  /** 异动统计（Tier1「异动统计」）：按类型/状态/在途节点聚合，范围过滤同列表。 */
  getStatusChangeStats(params = {}) {
    return call(() => request(`${BASE}/status-changes/stats`, { params }))
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
  /** 课程停用（Tier1「课程停用」）：ENABLED→DISABLED，被在途/生效培养方案引用时 400 拦截。 */
  enableCourse(courseId) {
    return call(() => request(`${BASE}/courses/${courseId}/enable`, { method: 'POST' }))
  },
  disableCourse(courseId) {
    return call(() => request(`${BASE}/courses/${courseId}/disable`, { method: 'POST' }))
  },
  getCourseReferences(courseId) {
    return call(() => request(`${BASE}/courses/${courseId}/references`))
  },
  /** 课程负责人检索（Tier1「课程负责人」）：在职教师，供 AppTeacherPicker 远程搜索。 */
  searchCourseTeachers(keyword) {
    return call(() => request(`${BASE}/courses/teachers/search`, { params: keyword ? { keyword } : {} }))
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
  getProgramBindings(programId) {
    return call(() => request(`${BASE}/programs/${programId}/bindings`))
  },
  /* 课程模块：方案课程明细增删改（Tier1 续工） */
  updateProgramCourse(programCourseId, body) {
    return call(() => request(`${BASE}/programs/courses/${programCourseId}`, { method: 'PUT', body }))
  },
  deleteProgramCourse(programCourseId) {
    return call(() => request(`${BASE}/programs/courses/${programCourseId}`, { method: 'DELETE' }))
  },
  /* 学分要求：分模块学分结构（Tier1 续工） */
  getCreditRequirements(programId) {
    return call(() => request(`${BASE}/programs/${programId}/credit-requirements`))
  },
  saveCreditRequirements(programId, items) {
    return call(() => request(`${BASE}/programs/${programId}/credit-requirements`, { method: 'PUT', body: { items } }))
  },
  /* 毕业要求：结构化条目 CRUD（Tier1 续工） */
  getGraduationRequirements(programId) {
    return call(() => request(`${BASE}/programs/${programId}/graduation-requirements`))
  },
  createGraduationRequirement(programId, body) {
    return call(() => request(`${BASE}/programs/${programId}/graduation-requirements`, { method: 'POST', body }))
  },
  updateGraduationRequirement(requirementId, body) {
    return call(() => request(`${BASE}/programs/graduation-requirements/${requirementId}`, { method: 'PUT', body }))
  },
  deleteGraduationRequirement(requirementId) {
    return call(() => request(`${BASE}/programs/graduation-requirements/${requirementId}`, { method: 'DELETE' }))
  },
  /* 方案版本：版本链 + 新建版本（Tier1 续工） */
  getProgramVersions(programId) {
    return call(() => request(`${BASE}/programs/${programId}/versions`))
  },
  createProgramNewVersion(programId) {
    return call(() => request(`${BASE}/programs/${programId}/new-version`, { method: 'POST' }))
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

  /* ── 教学任务确认（教务两级：学院核对确认 → 教务终审，Tier1 新增） ── */
  collegeConfirmTaskBatch(batchId) {
    return call(() => request(`${BASE}/teaching-task-batches/${batchId}/college-confirm`, { method: 'POST' }))
  },
  reviewTaskBatch(batchId, action, reason) {
    return call(() => request(`${BASE}/teaching-task-batches/${batchId}/review`, { method: 'POST', body: { action, reason } }))
  },

  /* ── 任课教师分配 / 合班拆班 / 教师任务确认：跨批次工作队列（Tier1 新增） ── */
  listAllTasks(params = {}) {
    return callList(`${BASE}/teaching-tasks`, params)
  },
  mergeTasks(taskIds, note) {
    return call(() => request(`${BASE}/teaching-tasks/merge`, { method: 'POST', body: { taskIds, note } }))
  },
  splitTask(taskId) {
    return call(() => request(`${BASE}/teaching-tasks/${taskId}/split`, { method: 'POST' }))
  },

  /* ── 教学任务统计（Tier1 新增） ── */
  getTeachingTaskStats(params = {}) {
    return call(() => request(`${BASE}/teaching-task-batches/stats`, { params }))
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
  /* ── 排课 Tier1 R2（05教室可用时间/07自动排课预留/10排课结果/11排课调整/13排课归档） ── */
  getScheduleRoomView(batchId, classroom) {
    return call(() => request(`${BASE}/schedule-batches/${batchId}/room-view`, { params: { classroom } }))
  },
  getScheduleSummary(batchId) {
    return call(() => request(`${BASE}/schedule-batches/${batchId}/summary`))
  },
  async downloadScheduleImportTemplate() {
    const blob = await requestBlob(`${BASE}/schedule-batches/import/template`)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = '排课结果导入模板.xlsx'
    a.click()
    URL.revokeObjectURL(url)
  },
  async uploadScheduleImportXlsx(batchId, file) {
    try {
      return ok(await requestUpload(`${BASE}/schedule-batches/${batchId}/import/xlsx`, file))
    } catch (e) {
      return toErr(e)
    }
  },
  teacherObjectSchedule(batchId, itemId, reason) {
    return call(() => request(`${BASE}/schedule-batches/${batchId}/teacher-object`, { method: 'POST', body: { itemId, reason } }))
  },
  getScheduleObjections(batchId) {
    return call(() => request(`${BASE}/schedule-batches/${batchId}/objections`))
  },
  adjustScheduleItem(batchId, itemId, body) {
    return call(() => request(`${BASE}/schedule-batches/${batchId}/items/${itemId}`, { method: 'PUT', body }))
  },
  archiveSchedule(batchId) {
    return call(() => request(`${BASE}/schedule-batches/${batchId}/archive`, { method: 'POST' }))
  },

  /* ── 课表管理 Tier1 R2：班级/教师/教室独立课表（自动取当前已发布批次） + 发布记录 + 导出 ── */
  getClassSchedule(classId, params = {}) {
    return call(() => request(`${BASE}/schedule/class/${classId}`, { params }))
  },
  getTeacherSchedule(teacherKey, params = {}) {
    return call(() => request(`${BASE}/schedule/teacher/${teacherKey}`, { params }))
  },
  getRoomSchedule(classroomId, params = {}) {
    return call(() => request(`${BASE}/schedule/room/${classroomId}`, { params }))
  },
  getSchedulePublishRecords(params = {}) {
    return callList(`${BASE}/schedule/publish-records`, params)
  },
  async exportScheduleXlsx(body = {}) {
    try {
      const blob = await requestBlob(`${BASE}/schedule/export`, { method: 'POST', body })
      return ok(blob)
    } catch (e) {
      return toErr(e)
    }
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
  getGradeRecords(taskId) {
    return call(() => request(`${BASE}/grade-tasks/${taskId}/records`))
  },
  enterScore(taskId, body) {
    return call(() => request(`${BASE}/grade-tasks/${taskId}/scores`, { method: 'POST', body }))
  },
  /* 成绩批量导入（学号/平时分/期末分/异常标记；下载模板→上传预校验→确认导入→错误行下载，AppExcelImportDrawer 契约） */
  async downloadGradeImportTemplate(taskId) {
    try {
      const blob = await requestBlob(`${BASE}/grade-tasks/${taskId}/import/template`)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = '成绩导入模板.xlsx'
      a.click()
      URL.revokeObjectURL(url)
      return ok(null)
    } catch (e) {
      return toErr(e)
    }
  },
  uploadGradeImportXlsx(taskId, file) {
    return call(() => requestUpload(`${BASE}/grade-tasks/${taskId}/import/xlsx`, file))
  },
  async downloadGradeImportErrors(taskId, rows, errors) {
    try {
      const blob = await requestBlob(`${BASE}/grade-tasks/${taskId}/import/errors-xlsx`, {
        method: 'POST', body: { rows, errors }
      })
      const buf = await blob.arrayBuffer()
      const bytes = new Uint8Array(buf)
      let binary = ''
      for (let i = 0; i < bytes.length; i += 1) binary += String.fromCharCode(bytes[i])
      return ok({
        contentBase64: btoa(binary),
        filename: 'grade_import_errors.xlsx',
        mediaType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
      })
    } catch (e) {
      return toErr(e)
    }
  },
  confirmGradeImport(taskId, rows) {
    return call(() => request(`${BASE}/grade-tasks/${taskId}/import/confirm`, { method: 'POST', body: { rows } }))
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
  /** 导出学生成绩单 xlsx（同步下载）：返回 Blob；purpose 必填（≥5 字，写审计+水印）。 */
  async exportTranscript(studentId, purpose) {
    try {
      const blob = await requestBlob(`${BASE}/students/${studentId}/transcript/export`,
        { method: 'POST', body: { purpose } })
      return ok(blob)
    } catch (e) {
      return toErr(e)
    }
  },
  getFailList(params = {}) {
    return callList(`${BASE}/grade-views/fail-list`, params)
  },
  getGradeAnalysis(term) {
    return call(() => request(`${BASE}/grade-views/analysis`, { params: term ? { term } : {} }))
  },

  /* ── 学业预警（扫描 + 列表；多维分类/规则/跟进/统计见 academicAffairsWarningApi） ── */
  scanWarnings() {
    return call(() => request(`${BASE}/warnings/scan`, { method: 'POST' }))
  },
  getWarnings(params = {}) {
    return callList(`${BASE}/warnings`, params)
  },

  /* ── 毕业资格审核（批次 → 圈定 → 十项预审 → 学院初审 → 教务终审 → 归档） ── */
  listGradBatches(params = {}) {
    return callList(`${BASE}/graduation-audit-batches`, params)
  },
  createGradBatch(body) {
    return call(() => request(`${BASE}/graduation-audit-batches`, { method: 'POST', body }))
  },
  archiveGradBatch(batchId) {
    return call(() => request(`${BASE}/graduation-audit-batches/${batchId}/archive`, { method: 'POST' }))
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
  /** 导出总览 xlsx（同步下载）：返回 Blob；purpose 必填（≥5 字）。body 可携 domain 选择导出维度。 */
  async exportStats(body = {}) {
    try {
      const blob = await requestBlob(`${BASE}/stats/export`, { method: 'POST', body })
      return ok(blob)
    } catch (e) {
      return toErr(e)
    }
  },

  /* ── 教务统计 Tier1 10 项三级模块（02/03/04/05/06/10/11/12/13/15 号卡） ── */
  getStatsStatusChangeSummary(params = {}) { return call(() => request(`${BASE}/stats/status-change/summary`, { params })) },
  getStatsRegistrationSummary(params = {}) { return call(() => request(`${BASE}/stats/registration/summary`, { params })) },
  getStatsCourse(params = {}) { return call(() => request(`${BASE}/stats/course`, { params })) },
  getStatsCourseDetail(params = {}) { return callList(`${BASE}/stats/course/detail`, params) },
  getStatsTeachingTask(params = {}) { return call(() => request(`${BASE}/stats/teaching-task`, { params })) },
  getStatsTeachingTaskPending(params = {}) { return callList(`${BASE}/stats/teaching-task/pending`, params) },
  getStatsSchedule(params = {}) { return call(() => request(`${BASE}/stats/schedule`, { params })) },
  getStatsScheduleConflicts(params = {}) { return callList(`${BASE}/stats/schedule/conflicts`, params) },
  getStatsGrade(params = {}) { return call(() => request(`${BASE}/stats/grade`, { params })) },
  getStatsGradeDetail(params = {}) { return callList(`${BASE}/stats/grade/detail`, params) },
  getStatsWarningSummary(params = {}) { return call(() => request(`${BASE}/stats/warning/summary`, { params })) },
  getStatsGraduation(params = {}) { return call(() => request(`${BASE}/stats/graduation`, { params })) },
  getStatsGraduationAbnormal(params = {}) { return callList(`${BASE}/stats/graduation/abnormal`, params) },
  getStatsWorkload(params = {}) { return call(() => request(`${BASE}/stats/workload`, { params })) },
  getStatsWorkloadDetail(params = {}) { return callList(`${BASE}/stats/workload/detail`, params) },

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
  // ── 年级 / 教学班 / 班级学生 / 班级调整（个体移动，既有轻量端点）──
  listGrades(params = {}) { return call(() => request(`${BASE}/orgs/grades`, { params })) },
  listTeachingClasses(params = {}) { return callList(`${BASE}/orgs/teaching-classes`, params) },
  listClassStudents(classId, params = {}) { return callList(`${BASE}/orgs/classes/${classId}/students`, params) },
  adjustClass(body) { return call(() => request(`${BASE}/orgs/class-adjustments`, { method: 'POST', body })) },
  // ── 组织树 / 统计 / 变更审计 ──
  orgTree() { return call(() => request(`${BASE}/orgs/tree`)) },
  orgStats() { return call(() => request(`${BASE}/orgs/stats`)) },
  listAudit(params = {}) { return callList(`${BASE}/orgs/audit`, params) },
  // ── 专业方向（06号卡：总开关默认关闭，业务政策待学校确认；启用后按专业维护方向）──
  getMajorDirectionToggle() { return call(() => request(`${BASE}/orgs/major-direction-toggle`)) },
  setMajorDirectionToggle(enabled) {
    return call(() => request(`${BASE}/orgs/major-direction-toggle`, { method: 'POST', body: { enabled } }))
  },
  listDirections(majorId, params = {}) { return callList(`${BASE}/orgs/majors/${majorId}/directions`, params) },
  createDirection(majorId, body) {
    return call(() => request(`${BASE}/orgs/majors/${majorId}/directions`, { method: 'POST', body }))
  },
  updateDirection(majorId, directionId, body) {
    return call(() => request(`${BASE}/orgs/majors/${majorId}/directions/${directionId}`, { method: 'PUT', body }))
  },
  disableDirection(majorId, directionId) {
    return call(() => request(`${BASE}/orgs/majors/${majorId}/directions/${directionId}/disable`, { method: 'POST' }))
  },
  // ── 班级调整申请单（08号卡：行政班层面批量组织调整——合班/拆班/停用/毕业清班）──
  listClassAdjustments(params = {}) { return callList(`${BASE}/orgs/class-adjustment-requests`, params) },
  createClassAdjustment(body) {
    return call(() => request(`${BASE}/orgs/class-adjustment-requests`, { method: 'POST', body }))
  },
  precheckClassAdjustment(id) {
    return call(() => request(`${BASE}/orgs/class-adjustment-requests/${id}/precheck`, { method: 'POST' }))
  },
  executeClassAdjustment(id) {
    return call(() => request(`${BASE}/orgs/class-adjustment-requests/${id}/execute`, { method: 'POST' }))
  },
  cancelClassAdjustment(id) {
    return call(() => request(`${BASE}/orgs/class-adjustment-requests/${id}/cancel`, { method: 'POST' }))
  }
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
  enroll(selectionCourseId, isReselect = false) { return call(() => request(`${BASE}/selection/student/enroll`, { method: 'POST', body: { selectionCourseId, isReselect } })) },
  drop(selectionCourseId) { return call(() => request(`${BASE}/selection/student/drop`, { method: 'POST', body: { selectionCourseId } })) },
  mySelections(batchId) { return call(() => request(`${BASE}/selection/student/my`, { params: batchId ? { batchId } : {} })) },
  // ── 教务处调整 / 补选 / 统计 ──
  adjustRecord(recordId, reason) { return call(() => request(`${BASE}/selection/records/${recordId}/adjust`, { method: 'POST', body: { reason } })) },
  reselectGuide(id) { return call(() => request(`${BASE}/selection/batches/${id}/reselect-guide`)) },
  /** 学生本人补选指引（06号卡）：待补选记录 + 该批次仍有余量课程；batchId 可选。 */
  studentReselectGuide(batchId) { return call(() => request(`${BASE}/selection/student/reselect-guide`, { params: batchId ? { batchId } : {} })) },
  batchStats(id) { return call(() => request(`${BASE}/selection/batches/${id}/stats`)) },
  timeTick() { return call(() => request(`${BASE}/selection/time-tick`, { method: 'POST' })) },
  // ── 冲突检测（09号卡） ──
  conflictReport(id, studentNo) { return call(() => request(`${BASE}/selection/batches/${id}/conflict-report`, { params: studentNo ? { studentNo } : {} })) },
  async exportConflictReport(id, purpose) {
    try {
      const blob = await requestBlob(`${BASE}/selection/batches/${id}/conflict-report/export`, { method: 'POST', body: { purpose } })
      return ok(blob)
    } catch (e) { return toErr(e) }
  },
  // ── 选课归档（12号卡） ──
  listArchivedBatches(params = {}) { return callList(`${BASE}/selection/archive`, params) },
  archiveDetail(id) { return call(() => request(`${BASE}/selection/archive/${id}`)) },
  async exportArchive(id, purpose) {
    try {
      const blob = await requestBlob(`${BASE}/selection/archive/${id}/export`, { method: 'POST', body: { purpose } })
      return ok(blob)
    } catch (e) { return toErr(e) }
  }
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
  addPatrol(bid, body) { return call(() => request(`${BASE}/exam/batches/${bid}/patrols`, { method: 'POST', body })) },
  listPatrols(bid) { return call(() => request(`${BASE}/exam/batches/${bid}/patrols`)) },
  // 异常 / 统计
  recordIncident(body) { return call(() => request(`${BASE}/exam/incidents`, { method: 'POST', body })) },
  listIncidents(params = {}) { return callList(`${BASE}/exam/incidents`, params) },
  batchStats(id) { return call(() => request(`${BASE}/exam/batches/${id}/stats`)) },
  // 归档（12号卡，只读）
  listArchived(params = {}) { return callList(`${BASE}/exam/archive`, params) },
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
  collegeReview(bid) { return call(() => request(`${BASE}/makeup/batches/${bid}/college-review`, { method: 'POST' })) },
  linkExam(bid, examBatchId) { return call(() => request(`${BASE}/makeup/batches/${bid}/link-exam`, { method: 'POST', body: { examBatchId } })) },
  finishBatch(bid) { return call(() => request(`${BASE}/makeup/batches/${bid}/finish`, { method: 'POST' })) },
  stats(params = {}) { return call(() => request(`${BASE}/makeup/stats`, { params })) },
  statsDetail(params = {}) { return callList(`${BASE}/makeup/stats/detail`, params) },
  async exportStats(body = {}) {
    try {
      const blob = await requestBlob(`${BASE}/makeup/stats/export`, { method: 'POST', body })
      return ok(blob)
    } catch (e) { return toErr(e) }
  },
  printData(bid) { return call(() => request(`${BASE}/makeup/batches/${bid}/print-data`)) },
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
  mergeDeferred(did, batchId) { return call(() => request(`${BASE}/makeup/deferred-pool/${did}/merge`, { method: 'POST', body: { batchId } })) },
  // 材料归档
  archiveExemption(eid) { return call(() => request(`${BASE}/exemption/${eid}/archive`, { method: 'POST' })) },
  archiveList(params = {}) { return callList(`${BASE}/exemption/archive-list`, params) }
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
  markFee(id, action, amount, waiveReason = '') { return call(() => request(`${BASE}/textbooks/fee-ledger/${id}/mark`, { method: 'POST', body: { action, amount, waiveReason } })) },
  stock() { return call(() => request(`${BASE}/textbooks/stock`)) },
  // 统计
  stats() { return call(() => request(`${BASE}/textbooks/stats`)) }
}

/* ═══════════ 教室预约（/academic-affairs/classrooms/bookings） ═══════════ */
export const academicAffairsClassroomBookingApi = {
  list(params = {}) { return callList(`${BASE}/classrooms/bookings`, params) },
  book(body) { return call(() => request(`${BASE}/classrooms/bookings`, { method: 'POST', body })) },
  review(id, action, reason = '') { return call(() => request(`${BASE}/classrooms/bookings/${id}/review`, { method: 'POST', body: { action, reason } })) }
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
  stats(id) { return call(() => request(`${BASE}/evaluation/batches/${id}/stats`)) },
  archivedBatches(params = {}) { return callList(`${BASE}/evaluation/batches`, { ...params, status: 'ARCHIVED' }) },
  genRoleTasks(id, evaluatorType, assignments) { return call(() => request(`${BASE}/evaluation/batches/${id}/role-tasks`, { method: 'POST', body: { evaluatorType, assignments } })) },
  myRoleTasks(evaluatorType, batchId) { return call(() => request(`${BASE}/evaluation/my-role-tasks`, { params: batchId ? { evaluatorType, batchId } : { evaluatorType } })) },
  async exportEvaluation(id, domain, purpose) {
    try {
      const blob = await requestBlob(`${BASE}/evaluation/batches/${id}/export`, { method: 'POST', body: { domain, purpose } })
      return ok(blob)
    } catch (e) {
      return toErr(e)
    }
  }
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

/* ═══════════ 教务归档（/academic-affairs/archive/*） ═══════════
 * Tier1 续工（10/11/12 三级卡）新增：归档缺失提醒(precheck，不落库) / 归档导出(export+下载记录)。 */
export const academicAffairsArchiveApi = {
  listBatches(params = {}) { return callList(`${BASE}/archive/batches`, params) },
  getBatch(id) { return call(() => request(`${BASE}/archive/batches/${id}`)) },
  createBatch(body) { return call(() => request(`${BASE}/archive/batches`, { method: 'POST', body })) },
  check(id) { return call(() => request(`${BASE}/archive/batches/${id}/check`, { method: 'POST' })) },
  confirm(id, force) { return call(() => request(`${BASE}/archive/batches/${id}/confirm`, { method: 'POST', body: { force } })) },
  unfreeze(id, reason) { return call(() => request(`${BASE}/archive/batches/${id}/unfreeze`, { method: 'POST', body: { reason } })) },
  cancel(id) { return call(() => request(`${BASE}/archive/batches/${id}/cancel`, { method: 'POST' })) },
  /** 归档缺失提醒（10 卡）：9 域实时预检查，不落库。termId 缺省取当前学期。 */
  precheck(termId) { return call(() => request(`${BASE}/archive/precheck`, { params: termId ? { termId } : {} })) },
  /** 归档导出（12 卡）：下载记录查询（只读）。 */
  downloadLog(id) { return call(() => request(`${BASE}/archive/batches/${id}/download-log`)) },
  /** 单数据域水印 xlsx 下载（返回 Blob）。 */
  async exportItem(id, category, purpose) {
    try {
      const blob = await requestBlob(`${BASE}/archive/batches/${id}/items/${category}/export`, { params: { purpose } })
      return ok(blob)
    } catch (e) { return toErr(e) }
  },
  /** 批次级打包下载全部物料（zip，返回 Blob）。 */
  async exportAll(id, purpose) {
    try {
      const blob = await requestBlob(`${BASE}/archive/batches/${id}/export`, { params: { purpose } })
      return ok(blob)
    } catch (e) { return toErr(e) }
  }
}

/* ═══════════ 学业预警二级模块（Tier1：看板/多维分类/规则/跟进/统计，/academic-affairs/warnings/*） ═══════════
 * 权限：view=看板/列表/统计只读；handle=指派/干预/升级/关闭/作废/提醒；rule.manage=规则配置+扫描触发（教务处）。 */
export const academicAffairsWarningApi = {
  /** sourceKey: all | fail(挂科·历史挂 /warnings/scan) | credit | gpa | retake | graduation。 */
  scan(sourceKey = 'all') {
    const path = sourceKey === 'fail' ? `${BASE}/warnings/scan` : `${BASE}/warnings/scan/${sourceKey}`
    return call(() => request(path, { method: 'POST' }))
  },
  list(params = {}) { return callList(`${BASE}/warnings`, params) },
  summary() { return call(() => request(`${BASE}/warnings/summary`)) },
  getRules() { return call(() => request(`${BASE}/warnings/rules`)) },
  saveRule(key, value) { return call(() => request(`${BASE}/warnings/rules/${key}`, { method: 'PUT', body: { value } })) },
  detail(warningId) { return call(() => request(`${BASE}/warnings/${warningId}`)) },
  assign(warningId, ownerId, ownerName) {
    return call(() => request(`${BASE}/warnings/${warningId}/assign`, { method: 'POST', body: { ownerId, ownerName } }))
  },
  addIntervention(warningId, body) {
    return call(() => request(`${BASE}/warnings/${warningId}/interventions`, { method: 'POST', body }))
  },
  escalate(warningId, reason) {
    return call(() => request(`${BASE}/warnings/${warningId}/escalate`, { method: 'POST', body: { reason } }))
  },
  close(warningId, result) {
    return call(() => request(`${BASE}/warnings/${warningId}/close`, { method: 'POST', body: { result } }))
  },
  void(warningId, reason) {
    return call(() => request(`${BASE}/warnings/${warningId}/void`, { method: 'POST', body: { reason } }))
  },
  remind(warningId) {
    return call(() => request(`${BASE}/warnings/${warningId}/remind`, { method: 'POST' }))
  }
}

export default academicAffairsApi
