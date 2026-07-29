#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def path(rel: str) -> Path:
    return ROOT / rel

def read(rel: str) -> str:
    return path(rel).read_text(encoding="utf-8")

def write(rel: str, text: str) -> None:
    p = path(rel)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")

def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, got {count}")
    return text.replace(old, new, 1)

def regex_once(text: str, pattern: str, replacement: str, label: str, flags: int = re.S) -> str:
    new, count = re.subn(pattern, replacement, text, count=1, flags=flags)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one regex match, got {count}")
    return new

# ---------------------------------------------------------------------------
# Shared freshness state. Ordinary successful mutations invalidate only views;
# file uploads/downloads remain owned by the public file-center project.
# ---------------------------------------------------------------------------
write("miniapp/src/utils/viewFreshness.js", """let studentHomeVersion = 0
let teacherWorkbenchVersion = 0

export function getStudentHomeVersion() {
  return studentHomeVersion
}

export function getTeacherWorkbenchVersion() {
  return teacherWorkbenchVersion
}

export function markStudentHomeDirty() {
  studentHomeVersion += 1
  return studentHomeVersion
}

export function markTeacherWorkbenchDirty() {
  teacherWorkbenchVersion += 1
  return teacherWorkbenchVersion
}

export function markMobileViewsDirty(rawPath) {
  const requestPath = String(rawPath || '')
  if (requestPath.startsWith('/auth/')) {
    markStudentHomeDirty()
    markTeacherWorkbenchDirty()
    return
  }
  if (requestPath.startsWith('/mobile/teacher/') ||
      requestPath.startsWith('/teacher-mobile/') ||
      requestPath.startsWith('/todos/')) {
    markTeacherWorkbenchDirty()
    return
  }
  if (requestPath.startsWith('/mobile/')) markStudentHomeDirty()
}
""")

# ---------------------------------------------------------------------------
# request.js: GET single-flight, duplicate mutation rejection, real errors,
# stop hidden graduation full-page collection. Do not touch file functions.
# ---------------------------------------------------------------------------
rel = "miniapp/src/services/request.js"
text = read(rel)
text = replace_once(
    text,
    "import { ENV } from '@/config/env'\n",
    "import { ENV } from '@/config/env'\nimport { markMobileViewsDirty } from '@/utils/viewFreshness'\n",
    "request freshness import",
)
text = regex_once(
    text,
    r"async function collectTeacherGraduationPages\(path, first, options\) \{.*?\n\}\n\n\nfunction parseUnifiedBody",
    """async function collectTeacherGraduationPages(path, first, options) {
  // 移动列表只返回当前服务端页，禁止请求层静默循环抓取最多 20 页。
  // 需要更多数据的页面必须显式上拉并携带 page/pageSize。
  return normalizeTeacherGraduationData(path, first)
}


function parseUnifiedBody""",
    "disable graduation auto collect",
)
new_request = r"""/* GET 请求单飞：相同身份、路径和查询在并发期间只发送一次。
 * 写操作不共享 Promise；完全相同的并发写请求会被明确拒绝，避免双击重复落库。 */
const _getInflight = new Map()
const _mutationInflight = new Set()

function stablePayload(value) {
  if (!value || typeof value !== 'object') return String(value || '')
  const out = {}
  Object.keys(value).sort().forEach((key) => { out[key] = value[key] })
  try { return JSON.stringify(out) } catch (e) { return '' }
}

function inflightKey(method, effectivePath, data, auth) {
  const identity = auth ? getToken() : 'public'
  return `${method}|${effectivePath}|${stablePayload(data)}|${identity}`
}

function executeRealRequest(path, effectivePath, {
  method, data, auth, _retried, _rawPage
}) {
  return new Promise((resolve, reject) => {
    const header = { 'Content-Type': 'application/json' }
    const token = auth ? getToken() : ''
    if (token) header.Authorization = 'Bearer ' + token
    const internshipBatchId = selectedInternshipBatchId(path)
    if (internshipBatchId) header['X-Internship-Batch-Id'] = internshipBatchId
    uni.request({
      url: ENV.apiBaseUrl + ENV.apiPrefix + effectivePath,
      method,
      data: data || {},
      header,
      timeout: ENV.requestTimeout,
      success: (res) => {
        const body = res.data
        if (!body || typeof body.code !== 'number') {
          markOffline()
          reject({ code: 'BAD_RESPONSE', message: '响应结构异常', httpStatus: res.statusCode })
          return
        }
        if (body.code !== 0) {
          if (body.code === 401001 && auth && !_retried && !path.startsWith('/auth/')) {
            _refreshOnce()
              .then(() => realRequest(path, { method, data, auth, _retried: true, _rawPage }))
              .then(resolve)
              .catch(reject)
            return
          }
          reject({
            code: body.code,
            biz: true,
            message: body.message || '业务错误',
            traceId: body.traceId,
            httpStatus: res.statusCode
          })
          return
        }
        state.warned = false
        if (method !== 'GET') markMobileViewsDirty(path)
        if (_rawPage || method !== 'GET') { resolve(body.data); return }
        collectTeacherGraduationPages(effectivePath, body.data, { method, data, auth, _retried })
          .then(resolve).catch(reject)
      },
      fail: (err) => {
        markOffline()
        reject({ code: 'NETWORK', message: (err && err.errMsg) || '网络异常' })
      }
    })
  })
}

/** 真实后端请求：返回统一响应的 data 字段；code!==0 抛业务错（e.biz=true） */
export function realRequest(path, {
  method = 'GET', data, auth = true, _retried = false, _rawPage = false
} = {}) {
  const normalizedMethod = String(method || 'GET').toUpperCase()
  let effectivePath
  try { effectivePath = withTeacherGraduationContext(path) } catch (e) { return Promise.reject(e) }

  // 401 刷新后的重试和内部显式分页必须绕过原单飞槽位，避免等待自身 Promise。
  if (_retried || _rawPage) {
    return executeRealRequest(path, effectivePath, {
      method: normalizedMethod, data, auth, _retried, _rawPage
    })
  }

  const key = inflightKey(normalizedMethod, effectivePath, data, auth)
  if (normalizedMethod === 'GET') {
    if (_getInflight.has(key)) return _getInflight.get(key)
    const pending = executeRealRequest(path, effectivePath, {
      method: normalizedMethod, data, auth, _retried, _rawPage
    }).finally(() => _getInflight.delete(key))
    _getInflight.set(key, pending)
    return pending
  }

  if (_mutationInflight.has(key)) {
    return Promise.reject({ code: 'LOCKED', biz: true, message: '正在提交，请勿重复点击' })
  }
  _mutationInflight.add(key)
  return executeRealRequest(path, effectivePath, {
    method: normalizedMethod, data, auth, _retried, _rawPage
  }).finally(() => _mutationInflight.delete(key))
}
"""
text = regex_once(
    text,
    r"/\*\* 真实后端请求：返回统一响应的 data 字段；code!==0 抛业务错（e\.biz=true） \*/\nexport function realRequest\(.*?\n\}\n\n/\*\* 文件上传",
    new_request + "\n\n/** 文件上传",
    "replace realRequest",
)
write(rel, text)

# ---------------------------------------------------------------------------
# realApi: production-neutral student home and teacher workbench.
# ---------------------------------------------------------------------------
rel = "miniapp/src/services/realApi.js"
text = read(rel)
student_home_fn = r"""/** 学生首页：完全由真实聚合接口构造，生产不再从 mock 骨架继承课程、数量或个人信息。 */
export async function studentHomeReal() {
  const ov = await realRequest('/mobile/home')
  const stu = (ov && ov.student) || {}
  const stageCode = (ov && ov.stage && ov.stage.code) || stu.stage || ''
  const stageText = (ov && ov.stage && ov.stage.label) || STAGE_TEXT[stageCode] || '当前阶段'
  const todos = Array.isArray(ov && ov.todos) ? ov.todos.map((t) => ({
    id: t.id,
    title: t.title,
    module: t.module || t.type || '待办',
    deadline: t.dueAt || '',
    status: t.status || 'PENDING'
  })) : []
  const notices = Array.isArray(ov && ov.notices) ? ov.notices.map((n) => ({
    id: n.id,
    title: n.title,
    source: n.source || '校园通知',
    important: !!n.important
  })) : []
  const blockers = Array.isArray(ov && ov.alerts) ? ov.alerts.map((a, i) => ({
    id: a.domain || `alert-${i}`,
    title: a.title || '有事项需要处理',
    reason: a.title || '',
    solveText: '去处理',
    level: a.level || 'MEDIUM'
  })) : []
  const messageSummary = (ov && ov.messageSummary) || {
    unreadCount: Number(ov && ov.unreadCount) || 0,
    emergencyPendingCount: 0,
    latestEmergency: null
  }
  const firstTodo = todos[0]
  const firstBlocker = blockers[0]
  const nextAction = firstBlocker
    ? {
        title: firstBlocker.title,
        desc: firstBlocker.reason || '请尽快处理当前阻断事项',
        deadline: '',
        actionText: '去处理',
        route: '/pages/student/my-applications/index'
      }
    : firstTodo
      ? {
          title: firstTodo.title,
          desc: `来自${firstTodo.module}`,
          deadline: firstTodo.deadline,
          actionText: '去办理',
          route: '/pages/student/messages/index'
        }
      : null

  return {
    realApi: true,
    cacheHit: !!(ov && ov.cacheHit),
    student: {
      name: stu.name || '',
      studentNo: stu.studentNo || '',
      className: stu.className || '',
      grade: stu.grade || ''
    },
    greeting: '你好',
    stageCard: {
      title: `你正处于「${stageText}」阶段`,
      subtitle: '查看当前待办和校园通知',
      stageText,
      progress: null
    },
    metrics: {
      unread: Number(messageSummary.unreadCount) || 0,
      todoCount: todos.length,
      creditRate: null
    },
    messageSummary,
    nextAction,
    blockers,
    quickServices: [],
    todayCourses: [],
    todos,
    notices,
    orientation: (ov && ov.orientation) || null,
    orientationBatch: (ov && ov.orientationBatch) || { open: false, daysLeft: 0 }
  }
}

// 兼容旧调用名；不再接受或复制 mock 首页。
export const enrichHome = () => studentHomeReal()
"""
text = regex_once(
    text,
    r"/\*\* 学生首页：.*?\nexport async function enrichHome\(mockHome\) \{.*?\n\}\n",
    student_home_fn,
    "replace student home adapter",
)
teacher_workbench_fn = r"""/* 教师端·工作台：真实摘要、真实待办、真实风险；任一主摘要失败必须显式报错，不回落 mock。 */
export async function teacherWorkbenchReal(roleKey) {
  const [summaryResult, countResult, listResult, riskResult] = await Promise.allSettled([
    realRequest('/todos/summary'),
    realRequest('/teacher-mobile/todos/count'),
    realRequest('/teacher-mobile/todos', { data: { status: 'PENDING', page: 1, pageSize: 8 } }),
    realRequest('/mobile/teacher/risk-students-page?page=1&pageSize=5&level=all')
  ])
  if (summaryResult.status !== 'fulfilled' ||
      !summaryResult.value || typeof summaryResult.value !== 'object') {
    throw (summaryResult.status === 'rejected'
      ? summaryResult.reason
      : { code: 'BAD_RESPONSE', message: '教师工作台摘要加载失败' })
  }

  const summary = summaryResult.value
  const count = countResult.status === 'fulfilled' ? countResult.value : null
  const list = listResult.status === 'fulfilled' ? listResult.value : null
  const risk = riskResult.status === 'fulfilled' ? riskResult.value : null
  const byType = (count && count.byType) || {}
  const pending = Number(summary.pending) || 0
  const overdue = Number(summary.overdue) || 0
  const near = Number(summary.nearDeadline) || 0
  const doneToday = Number(summary.doneToday) || 0
  const role = summary.role || roleKey || ''
  const metrics = [
    { key: 'pending', label: '待我处理', value: pending },
    { key: 'overdue', label: '已逾期', value: overdue },
    { key: 'near', label: '24h到期', value: near },
    { key: 'done', label: '今日完成', value: doneToday }
  ]
  const typeEntries = Object.entries(byType).filter(([, n]) => Number(n) > 0).slice(0, 2)
  if (typeEntries.length) {
    metrics.splice(2, 2, ...typeEntries.map(([key, value]) => ({
      key, label: key, value: Number(value) || 0
    })))
  }
  const items = (list && (list.items || list.list)) || []
  return {
    contextTitle: role,
    metrics,
    pendingTotal: pending,
    dueSoon: (Array.isArray(items) ? items : []).slice(0, 5).map((t) => ({
      id: t.todoId || t.id,
      title: t.title || '',
      module: t.sourceModule || t.todoType || '',
      student: t.studentName || '',
      deadline: t.dueAt || t.deadline || '',
      status: t.status || 'PENDING',
      todoType: t.todoType
    })),
    riskStudents: (risk && Array.isArray(risk.list) ? risk.list : []).slice(0, 5).map((s) => ({
      id: s.studentId || s.studentNo || s.id,
      name: s.name || '',
      className: s.className || '—',
      type: `${s.riskType || '风险'}${s.reason ? '·' + s.reason : ''}`,
      level: s.riskLevel || s.risk || 'MEDIUM'
    })),
    recent: [],
    _real: true,
    _role: role,
    _byType: byType,
    partialFailures: {
      count: countResult.status !== 'fulfilled',
      todos: listResult.status !== 'fulfilled',
      risk: riskResult.status !== 'fulfilled'
    }
  }
}

// 兼容旧调用名；生产不再复制 mock 工作台。
export const enrichTeacherWorkbench = (_mock, roleKey) => teacherWorkbenchReal(roleKey)
"""
text = regex_once(
    text,
    r"/\* 教师端·工作台聚合.*?export async function enrichTeacherWorkbench\(mock\) \{.*?\n\}\n",
    teacher_workbench_fn,
    "replace teacher workbench adapter",
)
write(rel, text)

# ---------------------------------------------------------------------------
# API services no longer seed production home/workbench from mock.
# ---------------------------------------------------------------------------
rel = "miniapp/src/services/studentApi.js"
text = read(rel)
text = replace_once(
    text,
    """  getHome: () =>
    realFirst('student.home',
      () => mockRequest(M.studentHome).then((d) => real.enrichHome(d)),
      () => mockRequest(M.studentHome)),
""",
    """  getHome: () =>
    realFirstStrict('student.home',
      () => real.studentHomeReal(),
      () => mockRequest(M.studentHome)),
""",
    "studentApi home",
)
text = replace_once(
    text,
    """  getMessages: () =>
    realFirstStrict('student.messages',
      () => real.selfMessages({ tabs: M.studentMessageTabs, groups: M.studentMessages }),
      () => mockRequest({ tabs: M.studentMessageTabs, groups: M.studentMessages })),
""",
    """  getMessagesPage: (tab = 'todo', page = 1, pageSize = 20) =>
    realFirstStrict('student.messages.page',
      () => real.selfMessagesPage(tab, page, pageSize),
      () => mockRequest({ tabs: M.studentMessageTabs, groups: M.studentMessages })),
  getMessages: () =>
    realFirstStrict('student.messages',
      () => real.selfMessages({ tabs: M.studentMessageTabs, groups: M.studentMessages }),
      () => mockRequest({ tabs: M.studentMessageTabs, groups: M.studentMessages })),
""",
    "studentApi paged messages",
)
write(rel, text)

rel = "miniapp/src/services/teacherApi.js"
text = read(rel)
text = replace_once(
    text,
    """  getWorkbench: (roleKey) =>
    realFirstStrict('teacher.workbench',
      () => real.enrichTeacherWorkbench(M.workbenchByRole[roleKey] || M.workbenchByRole.counselor),
      () => {
        if (import.meta.env && import.meta.env.PROD) {
          return Promise.reject(new Error('生产环境教师工作台不可回落演示数据'))
        }
        return mockRequest(M.workbenchByRole[roleKey] || M.workbenchByRole.counselor)
      }),
  getTodos: () => realFirst('teacher.todos', () => real.teacherTodosReal(), () => mockRequest({ filters: M.todoFilters, list: M.teacherTodos })),
""",
    """  getWorkbench: (roleKey) =>
    realFirstStrict('teacher.workbench',
      () => real.teacherWorkbenchReal(roleKey),
      () => mockRequest(M.workbenchByRole[roleKey] || M.workbenchByRole.counselor)),
  getTodosPage: (group = 'all', page = 1, pageSize = 20) =>
    realFirstStrict('teacher.todos.page',
      () => real.teacherTodosPage(group, page, pageSize),
      () => mockRequest({ filters: M.todoFilters, list: M.teacherTodos })),
  getTodos: () => realFirst('teacher.todos', () => real.teacherTodosReal(), () => mockRequest({ filters: M.todoFilters, list: M.teacherTodos })),
""",
    "teacherApi workbench and todos",
)
text = replace_once(
    text,
    """  getRiskStudents: () => realFirst('teacher.risk', () => real.teacherRiskStudents(), () => mockRequest(M.students.filter((s) => s.risk === 'HIGH' || s.risk === 'MEDIUM'))),
""",
    """  getRiskStudentsPage: (level = 'all', page = 1, pageSize = 20) =>
    realFirstStrict('teacher.risk.page',
      () => real.teacherRiskStudentsPage(level, page, pageSize),
      () => mockRequest({ list: M.students.filter((s) => s.risk === 'HIGH' || s.risk === 'MEDIUM') })),
  getRiskStudents: () => realFirst('teacher.risk', () => real.teacherRiskStudents(), () => mockRequest(M.students.filter((s) => s.risk === 'HIGH' || s.risk === 'MEDIUM'))),
""",
    "teacherApi paged risk",
)
write(rel, text)

# Add paginated real API methods near message methods and teacher mobile helpers.
rel = "miniapp/src/services/realApi.js"
text = read(rel)
text = replace_once(
    text,
    "export const mobileTeacherTodos = () => realRequest('/mobile/teacher/todos')\n",
    """export const mobileTeacherTodos = () => realRequest('/mobile/teacher/todos')
export const teacherTodosPage = (group = 'all', page = 1, pageSize = 20) =>
  realRequest(`/mobile/teacher/todos-page?group=${encodeURIComponent(group)}&page=${page}&pageSize=${pageSize}`)
export const teacherRiskStudentsPage = (level = 'all', page = 1, pageSize = 20) =>
  realRequest(`/mobile/teacher/risk-students-page?level=${encodeURIComponent(level)}&page=${page}&pageSize=${pageSize}`)
    .then((data) => ({
      ...data,
      list: (data.list || []).map((student) => ({
        ...student,
        risk: student.riskLevel || 'MEDIUM',
        task: student.reason || student.riskType || '风险事项待处理',
        pending: 1,
        last: student.latestTime || '',
        stage: student.riskType || ''
      }))
    }))
""",
    "real API teacher pages",
)
text = replace_once(
    text,
    """/** 本人消息详情（按 messageId，杀进程后仍可重开） */
export const getMessageDetail = (id) =>
""",
    """export const selfMessagesPage = (tab = 'todo', page = 1, pageSize = 20) =>
  realRequest(`/mobile/me/messages-page?tab=${encodeURIComponent(tab)}&page=${page}&pageSize=${pageSize}`)

/** 本人消息详情（按 messageId，杀进程后仍可重开） */
export const getMessageDetail = (id) =>
""",
    "real API student messages page",
)
write(rel, text)

# ---------------------------------------------------------------------------
# Session: production uses neutral identity skeleton, never fixed mock PII.
# ---------------------------------------------------------------------------
rel = "miniapp/src/stores/session.js"
text = read(rel)
text = replace_once(
    text,
    "const STUDENT_INTERNSHIP_BATCH_KEY = 'gx_student_internship_batch_v1'\n",
    """const STUDENT_INTERNSHIP_BATCH_KEY = 'gx_student_internship_batch_v1'

function neutralUser(side) {
  return side === 'teacher'
    ? { name: '', tenantName: '', identities: [] }
    : { name: '', studentNo: '', className: '', college: '', major: '', grade: '', tenantName: '' }
}

function initialUser(side) {
  if (import.meta.env && import.meta.env.PROD) return neutralUser(side)
  return side === 'teacher' ? { ...mockTeacherUser } : { ...mockStudentUser }
}
""",
    "session neutral helper",
)
text = replace_once(text, "this.mockUser = { ...mockTeacherUser }", "this.mockUser = initialUser('teacher')", "teacher login skeleton")
text = replace_once(text, "this.mockUser = { ...mockStudentUser }", "this.mockUser = initialUser('student')", "student login skeleton")
text = replace_once(
    text,
    "const skeleton = s.isTeacher ? { ...mockTeacherUser } : { ...mockStudentUser }",
    "const skeleton = initialUser(s.isTeacher ? 'teacher' : 'student')",
    "restore skeleton",
)
write(rel, text)

# ---------------------------------------------------------------------------
# Internship context: real single-flight promise.
# ---------------------------------------------------------------------------
rel = "miniapp/src/stores/internshipContext.js"
text = read(rel)
text = replace_once(
    text,
    "const STORAGE_KEY = 'gx_internship_context_v1'\n",
    "const STORAGE_KEY = 'gx_internship_context_v1'\nlet _loadPromise = null\n",
    "internship inflight state",
)
load_replacement = r"""    async load(force = false) {
      if (_loadPromise) return _loadPromise
      if (this.loaded && !force) return this.selectedBatchId
      _loadPromise = (async () => {
        this.loading = true
        this.error = ''
        this.moduleAccessError = ''
        try {
          const data = await teacherInternshipContext()
          const healthy = data.moduleAccessHealthy !== false
          this.moduleAccessHealthy = healthy
          this.moduleAccessError = data.moduleAccessError || ''
          if (!healthy) {
            this.loaded = false
            this.permissionPatterns = []
            this.batches = []
            this.selectedBatchId = ''
            this.error = this.moduleAccessError || '权限服务加载失败，已停止显示岗位实习操作'
            throw { code: 'PERMISSION_SERVICE_UNHEALTHY', biz: true, message: this.error }
          }
          const oldRole = this.roleCode
          this.roleCode = data.roleCode || ''
          this.permissionPatterns = data.permissionPatterns || []
          this.permissionVersion = data.permissionVersion || ''
          this.batches = data.batches || []
          const exists = this.batches.some((b) => String(b.id) === String(this.selectedBatchId))
          if (!exists || (oldRole && oldRole !== this.roleCode)) {
            this.selectedBatchId = data.defaultBatchId || (this.batches[0] && String(this.batches[0].id)) || ''
          }
          this.loaded = true
          this.persist()
          return this.selectedBatchId
        } catch (e) {
          this.loaded = false
          this.permissionPatterns = []
          if (!this.error) this.error = (e && e.message) || '实习权限或批次加载失败'
          throw e
        } finally {
          this.loading = false
        }
      })().finally(() => { _loadPromise = null })
      return _loadPromise
    },
"""
text = regex_once(
    text,
    r"    async load\(force = false\) \{.*?\n    \},\n    selectBatch",
    load_replacement + "    selectBatch",
    "internship load single flight",
)
write(rel, text)

# ---------------------------------------------------------------------------
# Student homepage: one request, 20s TTL/freshness, stale result guard, true empties.
# ---------------------------------------------------------------------------
rel = "miniapp/src/pages/student/home/index.vue"
text = read(rel)
text = text.replace('@retry="load"', '@retry="retryLoad"', 1)
text = text.replace("{{ greeting }}，{{ user.name }}", "{{ greeting }}，{{ user.name || '同学' }}", 1)
text = text.replace("{{ home.stageCard.progress }}%", "{{ progressText }}", 1)
text = text.replace("{{ home.metrics.creditRate }}%", "{{ creditRateText }}", 1)
text = replace_once(
    text,
    """        <MobileActionCard
          :title="home.nextAction.title"
          :description="home.nextAction.desc + ' · ' + deadlineText(home.nextAction.deadline)"
          icon="→"
          :action-text="home.nextAction.actionText"
          @action="go(home.nextAction.route)"
          @click="go(home.nextAction.route)"
        />
""",
    """        <MobileActionCard
          v-if="home.nextAction"
          :title="home.nextAction.title"
          :description="[home.nextAction.desc, deadlineText(home.nextAction.deadline)].filter(Boolean).join(' · ')"
          icon="→"
          :action-text="home.nextAction.actionText"
          @action="go(home.nextAction.route)"
          @click="go(home.nextAction.route)"
        />
        <MobileGlobalState v-else state="empty" title="当前暂无待办"
          description="有新的审批、材料补交或校园事项时会显示在这里。" />
""",
    "student next action empty",
)
text = replace_once(
    text,
    """          <view class="icon-grid">
            <view
              v-for="(q, i) in home.quickServices"
""",
    """          <view v-if="home.quickServices.length" class="icon-grid">
            <view
              v-for="(q, i) in home.quickServices"
""",
    "student quick services v-if",
)
text = replace_once(
    text,
    """          </view>
        </view>

        <!-- 今日课程 -->
""",
    """          </view>
          <MobileGlobalState v-else state="empty" title="暂无常用服务"
            description="学校启用可办理服务后会显示在这里。" />
        </view>

        <!-- 今日课程 -->
""",
    "student quick services empty",
)
text = replace_once(
    text,
    """        <view class="card stack-sm">
          <view v-for="c in home.todayCourses" :key="c.id" class="home__course">
""",
    """        <view class="card stack-sm">
          <view v-for="c in home.todayCourses" :key="c.id" class="home__course">
""",
    "student course container anchor",
)
text = replace_once(
    text,
    """            <text v-if="c.status === 'current'" class="home__course-tag">进行中</text>
          </view>
        </view>

        <!-- 待办 -->
""",
    """            <text v-if="c.status === 'current'" class="home__course-tag">进行中</text>
          </view>
          <MobileGlobalState v-if="!home.todayCourses.length" state="empty" title="暂无今日课程"
            description="当前没有从教务系统获取到今日课程。" />
        </view>

        <!-- 待办 -->
""",
    "student courses empty",
)
text = replace_once(
    text,
    """          <MobileTodoCard
            v-for="t in home.todos"
""",
    """          <MobileTodoCard
            v-for="t in home.todos"
""",
    "student todos anchor",
)
text = replace_once(
    text,
    """            @handle="go('/pages/student/campus-service/index')"
          />
        </view>

        <!-- 通知 -->
""",
    """            @handle="go('/pages/student/campus-service/index')"
          />
          <MobileGlobalState v-if="!home.todos.length" state="empty" title="暂无待办"
            description="当前没有需要你处理的事项。" />
        </view>

        <!-- 通知 -->
""",
    "student todos empty",
)
text = replace_once(
    text,
    """          <view v-for="n in home.notices" :key="n.id" class="home__notice">
""",
    """          <view v-for="n in home.notices" :key="n.id" class="home__notice">
""",
    "student notices anchor",
)
text = replace_once(
    text,
    """            <text class="home__notice-src">{{ n.source }}</text>
          </view>
        </view>
""",
    """            <text class="home__notice-src">{{ n.source }}</text>
          </view>
          <MobileGlobalState v-if="!home.notices.length" state="empty" title="暂无校园通知"
            description="学校发布与你相关的通知后会显示在这里。" />
        </view>
""",
    "student notices empty",
)
student_script = r"""<script>
import { tenantBrandConfig } from '@/config'
import { useSessionStore } from '@/stores/session'
import { studentApi } from '@/services/studentApi'
import { getStudentHomeVersion } from '@/utils/viewFreshness'
import { deadlineText } from '@/utils/format'
import { go, toast } from '@/utils/nav'

const HOME_TTL_MS = 20_000
const GRAD_CLASSES = ['g1', 'g3', 'g7', 'g4', 'g5', 'g6', 'g2', 'g8']

const STEP_LABELS = { ACTIVATE: '账号激活', INFO: '信息核对', MATERIAL: '材料上传',
  PAYMENT: '缴费/绿色通道', DORM: '宿舍确认', CHECKIN: '现场报到', CONFIRM: '学院确认' }
const STEP_ROUTE = {
  ACTIVATE: '/pages/student/orientation/collect/index', INFO: '/pages/student/orientation/collect/index',
  MATERIAL: '/pages/student/orientation/index', PAYMENT: '/pages/student/orientation/green-channel/index',
  DORM: '/pages/student/orientation/index', CHECKIN: '/pages/student/orientation/code/index',
  CONFIRM: '/pages/student/orientation/index'
}

function sessionContextKey(session) {
  const identity = session.identity || {}
  return [identity.userId || '', identity.studentId || '', session.currentRole || ''].join('|')
}

export default {
  data() {
    return {
      brand: tenantBrandConfig, home: null, state: 'loading', user: {}, greeting: '你好',
      statusBarHeight: 20, orientation: null,
      orientationBatch: { open: false, daysLeft: 0 }, emg: null,
      lastLoadedAt: 0, loadedContextKey: '', loadedFreshnessVersion: -1
    }
  },
  computed: {
    progressText() {
      const value = Number(this.home?.stageCard?.progress)
      return Number.isFinite(value) ? `${value}%` : '—'
    },
    creditRateText() {
      const value = Number(this.home?.metrics?.creditRate)
      return Number.isFinite(value) ? `${value}%` : '—'
    },
    isOrientationGuide() {
      return !!(this.orientation && this.orientation.hasData &&
        ['NOT_REPORTED', 'PREPARED'].includes(this.orientation.reportStatus))
    },
    orientationSteps() {
      if (!this.orientation) return []
      let metCurrent = false
      return (this.orientation.steps || []).map((step) => {
        const done = step.status === 'DONE'
        const state = done ? 'done' : (metCurrent ? 'wait' : 'now')
        if (!done) metCurrent = true
        return { key: step.key, label: STEP_LABELS[step.key] || step.key, state,
          stateLabel: done ? '已完成' : (state === 'now' ? '进行中' : '待办') }
      })
    },
    orientationDoneCount() { return this.orientationSteps.filter((step) => step.state === 'done').length },
    orientationCurrentStep() {
      return this.orientationSteps.find((step) => step.state === 'now') || this.orientationSteps[0]
    },
    orientationNextLabel() {
      return this.orientationCurrentStep ? this.orientationCurrentStep.label : '报到总览'
    },
    orientationNextRoute() {
      const key = this.orientationCurrentStep && this.orientationCurrentStep.key
      return STEP_ROUTE[key] || '/pages/student/orientation/index'
    },
    ringStyle() {
      const total = this.orientationSteps.length || 1
      const deg = Math.round((this.orientationDoneCount / total) * 360)
      return `background: conic-gradient(var(--orientation-700) 0deg ${deg}deg, var(--gray-200) ${deg}deg 360deg);`
    }
  },
  onLoad() {
    this._pageActive = true
    try { this.statusBarHeight = uni.getSystemInfoSync().statusBarHeight || 20 } catch (e) {}
    this.load({ force: true })
  },
  onShow() {
    this._pageActive = true
    this.ensureFresh()
  },
  onHide() {
    this._pageActive = false
    this._loadEpoch = (this._loadEpoch || 0) + 1
  },
  onUnload() {
    this._pageActive = false
    this._loadEpoch = (this._loadEpoch || 0) + 1
  },
  onPullDownRefresh() {
    this.load({ force: true, done: () => uni.stopPullDownRefresh() })
  },
  methods: {
    go, toast, deadlineText,
    fmtDeadline(value) { return deadlineText(value) },
    gradClass(index) { return GRAD_CLASSES[index % GRAD_CLASSES.length] },
    goMessages() { go('/pages/student/messages/index') },
    retryLoad() { return this.load({ force: true }) },
    ensureFresh() {
      const session = useSessionStore()
      const contextKey = sessionContextKey(session)
      const freshness = getStudentHomeVersion()
      const fresh = this.home &&
        this.loadedContextKey === contextKey &&
        this.loadedFreshnessVersion === freshness &&
        Date.now() - this.lastLoadedAt < HOME_TTL_MS
      if (!fresh) this.load()
    },
    load({ force = false, done = null } = {}) {
      const session = useSessionStore()
      const contextKey = sessionContextKey(session)
      const freshness = getStudentHomeVersion()
      const fresh = this.home &&
        this.loadedContextKey === contextKey &&
        this.loadedFreshnessVersion === freshness &&
        Date.now() - this.lastLoadedAt < HOME_TTL_MS
      if (!force && fresh) {
        if (done) done()
        return Promise.resolve(this.home)
      }
      if (this._homePromise) {
        return this._homePromise.finally(() => { if (done) done() })
      }

      const epoch = (this._loadEpoch || 0) + 1
      this._loadEpoch = epoch
      if (!this.home || force) this.state = 'loading'
      const pending = studentApi.getHome()
        .then((data) => {
          const currentSession = useSessionStore()
          if (!this._pageActive || this._loadEpoch !== epoch ||
              sessionContextKey(currentSession) !== contextKey) return data
          this.home = data
          this.orientation = data.orientation || null
          this.orientationBatch = data.orientationBatch || { open: false, daysLeft: 0 }
          this.greeting = data.greeting || '你好'
          this.emg = data.messageSummary?.latestEmergency || null
          const student = data.student || {}
          this.user = {
            name: student.name || '',
            studentNo: student.studentNo || '',
            className: student.className || '',
            grade: student.grade || ''
          }
          currentSession.hydrateStudentProfile({
            base: { name: this.user.name, studentNo: this.user.studentNo },
            org: { className: this.user.className, grade: this.user.grade }
          })
          this.loadedContextKey = contextKey
          this.loadedFreshnessVersion = freshness
          this.lastLoadedAt = Date.now()
          this.state = 'ready'
          return data
        })
        .catch((error) => {
          if (this._pageActive && this._loadEpoch === epoch) this.state = 'error'
          throw error
        })
        .finally(() => {
          if (this._homePromise === pending) this._homePromise = null
          if (done) done()
        })
      this._homePromise = pending
      return pending
    }
  }
}
</script>"""
text = regex_once(text, r"<script>.*?</script>", student_script, "student home script")
write(rel, text)

# ---------------------------------------------------------------------------
# Teacher workbench: TTL + dirty + context key + exactly one workbench request.
# ---------------------------------------------------------------------------
rel = "miniapp/src/pages/teacher/workbench/index.vue"
text = read(rel)
text = text.replace('@retry="load"', '@retry="retryLoad"', 1)
text = text.replace("{{ (user.name||'师').slice(0,1) }}", "{{ (user.name || '老师').slice(0,1) }}", 1)
text = text.replace("{{ user.name }}</text>", "{{ user.name || '老师' }}</text>", 1)
text = replace_once(
    text,
    "import { teacherApi } from '@/services/teacherApi'\n",
    "import { teacherApi } from '@/services/teacherApi'\nimport { getTeacherWorkbenchVersion } from '@/utils/viewFreshness'\n",
    "teacher freshness import",
)
text = replace_once(
    text,
    "const GRAD_CLASSES = ['g1', 'g4', 'g3', 'g5', 'g2', 'g7', 'g6', 'g8']\n",
    """const WORKBENCH_TTL_MS = 20_000
const GRAD_CLASSES = ['g1', 'g4', 'g3', 'g5', 'g2', 'g7', 'g6', 'g8']
""",
    "teacher TTL constant",
)
text = replace_once(
    text,
    """      brand: tenantBrandConfig, wb: null, state: 'loading', user: {}, roleConfig: {},
      statusBarHeight: 20, internshipContextReady: false, internshipContextError: ''
""",
    """      brand: tenantBrandConfig, wb: null, state: 'loading', user: {}, roleConfig: {},
      statusBarHeight: 20, internshipContextReady: false, internshipContextError: '',
      lastLoadedAt: 0, loadedContextKey: '', loadedFreshnessVersion: -1
""",
    "teacher data freshness",
)
text = replace_once(
    text,
    """  onLoad() {
    try { this.statusBarHeight = uni.getSystemInfoSync().statusBarHeight || 20 } catch (e) {}
  },
  onShow() { this.load() },
  onPullDownRefresh() { this.load(() => uni.stopPullDownRefresh()) },
""",
    """  onLoad() {
    this._pageActive = true
    try { this.statusBarHeight = uni.getSystemInfoSync().statusBarHeight || 20 } catch (e) {}
  },
  onShow() {
    this._pageActive = true
    this.ensureFresh()
  },
  onHide() {
    this._pageActive = false
    this._loadEpoch = (this._loadEpoch || 0) + 1
  },
  onUnload() {
    this._pageActive = false
    this._loadEpoch = (this._loadEpoch || 0) + 1
  },
  onPullDownRefresh() {
    this.load({ force: true, done: () => uni.stopPullDownRefresh() })
  },
""",
    "teacher lifecycle",
)
teacher_load = r"""    contextKey(session) {
      const identity = session.identity || {}
      const context = useInternshipContextStore()
      return [
        identity.userId || '',
        session.currentRole || '',
        session.realUser?.tenantId || '',
        session.currentRole === 'intern_mentor' ? context.selectedBatchId || '' : ''
      ].join('|')
    },
    retryLoad() { return this.load({ force: true }) },
    ensureFresh() {
      const session = useSessionStore()
      const contextKey = this.contextKey(session)
      const freshness = getTeacherWorkbenchVersion()
      const fresh = this.wb &&
        this.loadedContextKey === contextKey &&
        this.loadedFreshnessVersion === freshness &&
        Date.now() - this.lastLoadedAt < WORKBENCH_TTL_MS
      if (!fresh) this.load()
    },
    async loadInternshipContext(session, force) {
      this.internshipContextReady = session.currentRole !== 'intern_mentor'
      this.internshipContextError = ''
      if (session.currentRole !== 'intern_mentor') return
      const context = useInternshipContextStore()
      context.restore()
      try {
        await context.load(force)
        this.internshipContextReady = true
      } catch (error) {
        this.internshipContextReady = false
        this.internshipContextError = (error && error.message) ||
          '岗位实习权限或批次上下文加载失败，已停止展示操作入口。'
      }
    },
    load({ force = false, done = null } = {}) {
      const session = useSessionStore()
      const beforeContextKey = this.contextKey(session)
      const freshness = getTeacherWorkbenchVersion()
      const fresh = this.wb &&
        this.loadedContextKey === beforeContextKey &&
        this.loadedFreshnessVersion === freshness &&
        Date.now() - this.lastLoadedAt < WORKBENCH_TTL_MS
      if (!force && fresh) {
        if (done) done()
        return Promise.resolve(this.wb)
      }
      if (this._workbenchPromise) {
        return this._workbenchPromise.finally(() => { if (done) done() })
      }

      const epoch = (this._loadEpoch || 0) + 1
      this._loadEpoch = epoch
      this.user = session.mockUser || {}
      this.roleConfig = session.roleConfig
      if (!this.wb || force) this.state = 'loading'

      const pending = (async () => {
        await this.loadInternshipContext(session, force)
        const contextKey = this.contextKey(session)
        const workbench = await teacherApi.getWorkbench(session.currentRole)
        if (!this._pageActive || this._loadEpoch !== epoch ||
            this.contextKey(useSessionStore()) !== contextKey) return workbench
        this.wb = workbench
        this.loadedContextKey = contextKey
        this.loadedFreshnessVersion = freshness
        this.lastLoadedAt = Date.now()
        this.state = 'ready'
        return workbench
      })().catch((error) => {
        if (this._pageActive && this._loadEpoch === epoch) this.state = 'error'
        throw error
      }).finally(() => {
        if (this._workbenchPromise === pending) this._workbenchPromise = null
        if (done) done()
      })
      this._workbenchPromise = pending
      return pending
    },
"""
text = regex_once(
    text,
    r"    async load\(done\) \{.*?\n    \},\n    quick\(q\)",
    teacher_load + "    quick(q)",
    "teacher load logic",
)
write(rel, text)

# ---------------------------------------------------------------------------
# High-frequency lists: server-paged and stale-result-safe.
# ---------------------------------------------------------------------------
rel = "miniapp/src/pages/student/messages/index.vue"
text = read(rel)
text = text.replace("v-for=\"m in pagedSlice(list)\"", "v-for=\"m in list\"", 1)
text = text.replace(
    """            <view v-if="pagedFooter(list) === 'more'" class="msg__paging" @click="pagedLoadMore">上拉加载更多</view>
            <view v-else-if="pagedFooter(list) === 'end'" class="msg__paging is-end">没有更多了</view>
""",
    """            <view v-if="hasMore" class="msg__paging" @click="loadMore">
              {{ loadingMore ? '加载中…' : '上拉加载更多' }}
            </view>
            <view v-else class="msg__paging is-end">没有更多了</view>
""",
    1,
)
messages_script = r"""<script>
import { studentApi } from '@/services/studentApi'
import { fromNow, deadlineText } from '@/utils/format'
import { toast, go } from '@/utils/nav'
import { stashDetail, stashSearchPool } from '@/utils/msgStash'
const TAB_ICON = { todo: '☑', notice: '📢', progress: '⏱', course: '📖' }
const TAB_GRAD = { todo: 'g1', notice: 'g1', progress: 'g3', course: 'g4' }
const PAGE_SIZE = 20

export default {
  data() {
    return {
      data: { tabs: [], groups: {} }, state: 'loading', tab: 'todo', statusBarHeight: 20,
      emg: null, emgAcking: false, page: 1, hasMore: false, loadingMore: false
    }
  },
  onLoad() {
    this._pageActive = true
    try { this.statusBarHeight = uni.getSystemInfoSync().statusBarHeight || 20 } catch (e) {}
    this.load({ reset: true })
  },
  onShow() {
    this._pageActive = true
    if (this.data) this._pickEmergency()
  },
  onHide() { this._pageActive = false; this._loadEpoch = (this._loadEpoch || 0) + 1 },
  onUnload() { this._pageActive = false; this._loadEpoch = (this._loadEpoch || 0) + 1 },
  onReachBottom() { this.loadMore() },
  watch: {
    tab() { this.load({ reset: true }) }
  },
  computed: {
    list() { return this.data?.groups?.[this.tab] || [] },
    unreadTotal() {
      return (this.data.tabs || []).reduce((sum, item) => sum + (Number(item.badge) || 0), 0)
    }
  },
  methods: {
    toast, fromNow, deadlineText,
    tabIcon(key) { return TAB_ICON[key] || '✉' },
    tabGrad(key) { return TAB_GRAD[key] || 'g8' },
    loadMore() {
      if (!this.hasMore || this.loadingMore) return
      this.load({ reset: false })
    },
    load({ reset = true } = {}) {
      if (this._messagesPromise) return this._messagesPromise
      const requestedTab = this.tab
      const requestedPage = reset ? 1 : this.page + 1
      const epoch = (this._loadEpoch || 0) + 1
      this._loadEpoch = epoch
      if (reset) this.state = 'loading'
      else this.loadingMore = true
      const pending = studentApi.getMessagesPage(requestedTab, requestedPage, PAGE_SIZE)
        .then((result) => {
          if (!this._pageActive || this._loadEpoch !== epoch || this.tab !== requestedTab) return result
          const incoming = Array.isArray(result.list) ? result.list : []
          const previous = reset ? [] : (this.data.groups[requestedTab] || [])
          this.data = {
            ...this.data,
            tabs: result.tabs || this.data.tabs || [],
            groups: { ...this.data.groups, [requestedTab]: [...previous, ...incoming] },
            emergencyPending: result.emergencyPending || this.data.emergencyPending || []
          }
          this.page = Number(result.page) || requestedPage
          this.hasMore = !!result.hasMore
          this.state = 'ready'
          this._pickEmergency()
          return result
        })
        .catch((error) => {
          if (this._pageActive && this._loadEpoch === epoch && reset) this.state = 'error'
          throw error
        })
        .finally(() => {
          if (this._messagesPromise === pending) this._messagesPromise = null
          this.loadingMore = false
        })
      this._messagesPromise = pending
      return pending
    },
    _pickEmergency() {
      const list = (this.data && this.data.emergencyPending) || []
      this.emg = list.find((item) => item && item.receipt && !item.acked) || null
    },
    openEmg() { if (this.emg) this.open(this.emg) },
    async ackEmg() {
      if (!this.emg || this.emgAcking) return
      const raw = String(this.emg.messageId || this.emg.id || '').replace('msg-', '')
      this.emgAcking = true
      try {
        await studentApi.ackMessageReceipt(raw)
        this.emg.acked = true
        this.emg.receipt = false
        this.emg.read = true
        toast('已确认')
        await this.load({ reset: true })
      } catch (e) {
        toast((e && e.message) || '确认失败')
      } finally {
        this.emgAcking = false
      }
    },
    markAllRead() {
      this.list.forEach((message) => {
        if (!message.read) { message.read = true; this._syncRead(message) }
      })
    },
    open(message) {
      message.read = true
      this._syncRead(message)
      stashDetail(message)
      go('/pages/common/message-detail/index')
    },
    openSearch() {
      stashSearchPool(Object.values((this.data && this.data.groups) || {}).flat())
      go('/pages/common/search/index')
    },
    _syncRead(message) {
      if (message._synced) return
      const raw = String(message.messageId || message.id || '').replace('msg-', '')
      const isUnified = message.kind === 'UNIFIED_MESSAGE' || /^\d+$/.test(raw)
      if (!isUnified) return
      message._synced = true
      studentApi.markMessageRead(raw).catch(() => { message._synced = false })
    },
    handle(message) {
      message.read = true
      this._syncRead(message)
      if (message.status === 'RETURNED') return go('/pages/student/my-applications/index')
      go('/pages/student/campus-service/index')
    }
  }
}
</script>"""
text = regex_once(text, r"<script>.*?</script>", messages_script, "messages script")
write(rel, text)

rel = "miniapp/src/pages/teacher/todos/index.vue"
text = read(rel)
text = text.replace("v-for=\"t in pagedSlice(filtered)\"", "v-for=\"t in list\"", 1)
text = text.replace("v-if=\"!filtered.length\"", "v-if=\"!list.length\"", 1)
text = text.replace(
    """            <view v-if="pagedFooter(filtered) === 'more'" class="td__paging" @click="pagedLoadMore">上拉加载更多</view>
            <view v-else-if="pagedFooter(filtered) === 'end'" class="td__paging is-end">没有更多了</view>
""",
    """            <view v-if="hasMore" class="td__paging" @click="loadMore">
              {{ loadingMore ? '加载中…' : '上拉加载更多' }}
            </view>
            <view v-else class="td__paging is-end">没有更多了</view>
""",
    1,
)
todos_script = r"""<script>
import { useSessionStore } from '@/stores/session'
import { teacherApi } from '@/services/teacherApi'
import { deadlineText, isOverdue } from '@/utils/format'
import { go } from '@/utils/nav'
const PAGE_SIZE = 20
export default {
  data() {
    return {
      data: { filters: [], list: [] }, state: 'loading', filter: 'all', scopeText: '',
      page: 1, hasMore: false, loadingMore: false
    }
  },
  onLoad() {
    this._pageActive = true
    this.scopeText = useSessionStore().dataScopeText
    this.load({ reset: true })
  },
  onShow() { this._pageActive = true },
  onHide() { this._pageActive = false; this._loadEpoch = (this._loadEpoch || 0) + 1 },
  onUnload() { this._pageActive = false; this._loadEpoch = (this._loadEpoch || 0) + 1 },
  onReachBottom() { this.loadMore() },
  watch: {
    filter() { this.load({ reset: true }) }
  },
  computed: {
    list() { return this.data.list || [] },
    pendingCount() { return Number(this.data.pendingCount) || 0 },
    filtersWithBadge() {
      return (this.data.filters || []).map((item) => ({
        ...item,
        badge: Number(item.badge) || 0
      }))
    }
  },
  methods: {
    deadlineText, isOverdue,
    loadMore() {
      if (!this.hasMore || this.loadingMore) return
      this.load({ reset: false })
    },
    load({ reset = true } = {}) {
      if (this._todosPromise) return this._todosPromise
      const requestedFilter = this.filter
      const requestedPage = reset ? 1 : this.page + 1
      const epoch = (this._loadEpoch || 0) + 1
      this._loadEpoch = epoch
      if (reset) this.state = 'loading'
      else this.loadingMore = true
      const pending = teacherApi.getTodosPage(requestedFilter, requestedPage, PAGE_SIZE)
        .then((result) => {
          if (!this._pageActive || this._loadEpoch !== epoch || this.filter !== requestedFilter) return result
          this.data = {
            ...result,
            list: reset ? (result.list || []) : [...this.list, ...(result.list || [])]
          }
          this.page = Number(result.page) || requestedPage
          this.hasMore = !!result.hasMore
          this.state = 'ready'
          return result
        })
        .catch((error) => {
          if (this._pageActive && this._loadEpoch === epoch && reset) this.state = 'error'
          throw error
        })
        .finally(() => {
          if (this._todosPromise === pending) this._todosPromise = null
          this.loadingMore = false
        })
      this._todosPromise = pending
      return pending
    },
    handle(todo) {
      const map = {
        review: todo.module.includes('毕业') ? '/pages/teacher/graduation-guide/index?tab=review' : '/pages/teacher/internship-review/index',
        approve: '/pages/teacher/approval/index',
        risk: '/pages/teacher/risk-students/index',
        contact: '/pages/teacher/risk-students/index',
        confirm: '/pages/teacher/internship-review/index'
      }
      go(map[todo.group] || '/pages/teacher/approval/index')
    },
    quickDone(todo) { this.handle(todo) }
  }
}
</script>"""
text = regex_once(text, r"<script>.*?</script>", todos_script, "teacher todos script")
write(rel, text)

rel = "miniapp/src/pages/teacher/risk-students/index.vue"
text = read(rel)
text = text.replace("v-for=\"s in pagedSlice(filtered)\"", "v-for=\"s in list\"", 1)
text = text.replace("{{ list.length }}</text><text class=\"rk__sum-label\">需关注", "{{ total }}</text><text class=\"rk__sum-label\">需关注", 1)
text = text.replace(
    """          <view v-if="pagedFooter(filtered) === 'more'" class="rk__paging" @click="pagedLoadMore">上拉加载更多</view>
          <view v-else-if="pagedFooter(filtered) === 'end'" class="rk__paging is-end">没有更多了</view>
""",
    """          <view v-if="hasMore" class="rk__paging" @click="loadMore">
            {{ loadingMore ? '加载中…' : '上拉加载更多' }}
          </view>
          <view v-else class="rk__paging is-end">没有更多了</view>
""",
    1,
)
risk_script = r"""<script>
import { teacherApi } from '@/services/teacherApi'
import { go } from '@/utils/nav'
const PAGE_SIZE = 20
export default {
  data() {
    return {
      list: [], state: 'loading', level: 'all', page: 1, hasMore: false,
      loadingMore: false, total: 0, counts: { HIGH: 0, MEDIUM: 0 }
    }
  },
  onLoad() { this._pageActive = true; this.load({ reset: true }) },
  onShow() { this._pageActive = true },
  onHide() { this._pageActive = false; this._loadEpoch = (this._loadEpoch || 0) + 1 },
  onUnload() { this._pageActive = false; this._loadEpoch = (this._loadEpoch || 0) + 1 },
  onReachBottom() { this.loadMore() },
  watch: {
    level() { this.load({ reset: true }) }
  },
  onPullDownRefresh() {
    this.load({ reset: true, done: () => uni.stopPullDownRefresh() })
  },
  methods: {
    loadMore() {
      if (!this.hasMore || this.loadingMore) return
      this.load({ reset: false })
    },
    load({ reset = true, done = null } = {}) {
      if (this._riskPromise) return this._riskPromise.finally(() => { if (done) done() })
      const requestedLevel = this.level
      const requestedPage = reset ? 1 : this.page + 1
      const epoch = (this._loadEpoch || 0) + 1
      this._loadEpoch = epoch
      if (reset) this.state = 'loading'
      else this.loadingMore = true
      const pending = teacherApi.getRiskStudentsPage(requestedLevel, requestedPage, PAGE_SIZE)
        .then((result) => {
          if (!this._pageActive || this._loadEpoch !== epoch || this.level !== requestedLevel) return result
          this.list = reset ? (result.list || []) : [...this.list, ...(result.list || [])]
          this.page = Number(result.page) || requestedPage
          this.hasMore = !!result.hasMore
          this.total = Number(result.total) || 0
          this.counts = result.counts || { HIGH: 0, MEDIUM: 0 }
          this.state = 'ready'
          return result
        })
        .catch((error) => {
          if (this._pageActive && this._loadEpoch === epoch && reset) this.state = 'error'
          throw error
        })
        .finally(() => {
          if (this._riskPromise === pending) this._riskPromise = null
          this.loadingMore = false
          if (done) done()
        })
      this._riskPromise = pending
      return pending
    },
    openStudent(student) { go('/pages/teacher/student-detail/index?id=' + student.id) },
    contact(student) { this.openStudent(student) }
  }
}
</script>"""
text = regex_once(text, r"<script>.*?</script>", risk_script, "teacher risk script")
write(rel, text)

# ---------------------------------------------------------------------------
# Backend: lightweight message summary, home timing/SQL count/cache jitter,
# compatibility paged list wrappers. No migration and no file-center code.
# ---------------------------------------------------------------------------
rel = "backend/app/services/mobile_student_service.py"
text = read(rel)
text = replace_once(text, "from datetime import datetime\n", "from datetime import datetime\nimport logging\nimport random\nimport time\nfrom contextvars import ContextVar\nfrom threading import Lock\n", "student service imports")
text = replace_once(text, "from sqlalchemy import func, or_, select\n", "from sqlalchemy import event, func, or_, select\n", "student sqlalchemy event import")
text = replace_once(text, "from app.db.session import db_enabled, get_sessionmaker\n", "from app.db.session import db_enabled, get_engine, get_sessionmaker\n", "student get_engine import")
text = replace_once(
    text,
    "from app.services.db_service import _iso, _mask_phone, _org_names, _primary_phone, _tid\n\n\n",
    """from app.services.db_service import _iso, _mask_phone, _org_names, _primary_phone, _tid

log = logging.getLogger("app.mobile.student")
_home_query_count: ContextVar[int | None] = ContextVar("mobile_home_query_count", default=None)
_home_listener_lock = Lock()
_home_listener_installed = False


def _count_home_query(*_args, **_kwargs):
    count = _home_query_count.get()
    if count is not None:
        _home_query_count.set(count + 1)


def _ensure_home_query_listener() -> None:
    global _home_listener_installed
    if _home_listener_installed:
        return
    with _home_listener_lock:
        if _home_listener_installed:
            return
        event.listen(get_engine(), "before_cursor_execute", _count_home_query)
        _home_listener_installed = True


""",
    "student service metrics helpers",
)
# Replace personal notices query with selected columns and emergency summary.
old_notice = """        notices = db.scalars(select(UnifiedMessage).where(
            UnifiedMessage.tenant_id == _tid(), UnifiedMessage.is_deleted.is_(False),
            UnifiedMessage.receiver_id.in_(personal_ids)
        ).order_by(UnifiedMessage.id.desc()).limit(5)).all()
"""
new_notice = """        visibility = [UnifiedMessage.receiver_id.in_(personal_ids)]
        if uid is not None:
            visibility.append(UnifiedMessage.receiver_user_id == uid)
        notice_columns = (
            UnifiedMessage.id, UnifiedMessage.title, UnifiedMessage.message_type,
            UnifiedMessage.source_module, UnifiedMessage.status, UnifiedMessage.priority,
            UnifiedMessage.category, UnifiedMessage.require_ack, UnifiedMessage.ack_at,
            UnifiedMessage.withdrawn_at, UnifiedMessage.created_at,
        )
        notices = db.execute(select(*notice_columns).where(
            UnifiedMessage.tenant_id == _tid(), UnifiedMessage.is_deleted.is_(False),
            or_(*visibility)
        ).order_by(UnifiedMessage.id.desc()).limit(5)).all()
        emergency_filter = or_(
            UnifiedMessage.priority == "EMERGENCY",
            UnifiedMessage.category == "EMERGENCY",
            UnifiedMessage.message_type == "EMERGENCY",
        )
        emergency_pending_count = db.scalar(select(func.count()).select_from(UnifiedMessage).where(
            UnifiedMessage.tenant_id == _tid(), UnifiedMessage.is_deleted.is_(False),
            or_(*visibility), emergency_filter,
            UnifiedMessage.require_ack.is_(True), UnifiedMessage.ack_at.is_(None),
            UnifiedMessage.withdrawn_at.is_(None),
        )) or 0
        latest_emergency = db.execute(select(*notice_columns).where(
            UnifiedMessage.tenant_id == _tid(), UnifiedMessage.is_deleted.is_(False),
            or_(*visibility), emergency_filter,
            UnifiedMessage.require_ack.is_(True), UnifiedMessage.ack_at.is_(None),
            UnifiedMessage.withdrawn_at.is_(None),
        ).order_by(UnifiedMessage.id.desc()).limit(1)).first()
"""
text = replace_once(text, old_notice, new_notice, "student lightweight notices")
old_result_notice = """            "notices": [{"id": str(n.id), "title": n.title, "type": n.message_type,
                          "source": n.source_module or "校园通知",
                          "important": (n.message_type or "").upper() in ("URGENT", "IMPORTANT"),
                          "status": n.status} for n in notices],
            "unreadCount": unread_count,
"""
new_result_notice = """            "notices": [{"id": str(n.id), "title": n.title, "type": n.message_type,
                          "source": n.source_module or "校园通知",
                          "important": ((n.priority or "").upper() in ("EMERGENCY", "IMPORTANT")
                                        or (n.message_type or "").upper() in ("URGENT", "IMPORTANT")),
                          "status": n.status} for n in notices],
            "unreadCount": unread_count,
            "messageSummary": {
                "unreadCount": unread_count,
                "emergencyPendingCount": int(emergency_pending_count),
                "latestEmergency": ({
                    "id": str(latest_emergency.id),
                    "messageId": str(latest_emergency.id),
                    "title": latest_emergency.title,
                    "module": latest_emergency.source_module or "通知",
                    "emergency": True,
                    "receipt": True,
                    "acked": False,
                    "kind": "UNIFIED_MESSAGE",
                    "time": _iso(latest_emergency.created_at),
                } if latest_emergency is not None else None),
            },
"""
text = replace_once(text, old_result_notice, new_result_notice, "student message summary result")
text = replace_once(
    text,
    """            return {"student": None, "stage": None, "todos": [], "alerts": [], "notices": [],
                    "domains": [], "unreadCount": 0, **_empty()}
""",
    """            return {"student": None, "stage": None, "todos": [], "alerts": [], "notices": [],
                    "domains": [], "unreadCount": 0,
                    "messageSummary": {"unreadCount": 0, "emergencyPendingCount": 0,
                                       "latestEmergency": None}, **_empty()}
""",
    "student empty summary",
)
home_fn = r'''def home(user: dict) -> dict:
    """One authenticated request for overview + orientation + lightweight message summary."""
    u = _require_student(user)
    from app.core.config import settings
    from app.core.redis_client import (
        cache_get_json,
        cache_set_json,
        cache_set_json_if_absent,
    )
    key = _home_cache_key(u)
    started = time.perf_counter()
    cached = cache_get_json(key)
    if isinstance(cached, dict):
        cached["cacheHit"] = True
        log.info("mobile_home cache_hit=true duration_ms=%.2f query_count=0",
                 (time.perf_counter() - started) * 1000)
        return cached

    lock_state = cache_set_json_if_absent(
        f"{key}:build", {"startedAt": int(time.time())}, 5)
    if lock_state is False:
        for _ in range(6):
            time.sleep(0.05)
            cached = cache_get_json(key)
            if isinstance(cached, dict):
                cached["cacheHit"] = True
                log.info("mobile_home cache_hit=waited duration_ms=%.2f query_count=0",
                         (time.perf_counter() - started) * 1000)
                return cached

    query_token = None
    query_count = 0
    if db_enabled():
        _ensure_home_query_listener()
        query_token = _home_query_count.set(0)
    try:
        data = me_overview(u, include_home=True)
        query_count = int(_home_query_count.get() or 0) if query_token is not None else 0
    finally:
        if query_token is not None:
            _home_query_count.reset(query_token)

    data["cacheHit"] = False
    base_ttl = max(1, int(settings.HOME_CACHE_TTL))
    jitter = random.randint(0, max(1, min(5, base_ttl // 4 or 1)))
    cached_ok = cache_set_json(key, data, base_ttl + jitter)
    log.info(
        "mobile_home cache_hit=false duration_ms=%.2f query_count=%d redis_cached=%s",
        (time.perf_counter() - started) * 1000,
        query_count,
        cached_ok,
    )
    return data
'''
text = regex_once(text, r"def home\(user: dict\) -> dict:.*?\n\n\ndef my_todos", home_fn + "\n\n\ndef my_todos", "student home metrics")
# Add server-side response pagination wrappers after my_messages.
paged_messages_fn = r'''

def my_messages_page(user: dict, tab: str = "todo", page: int = 1,
                     page_size: int = 20) -> dict:
    """兼容聚合上的服务端分页。底层各域查询均已有硬上限；客户端不再一次接收全部分组。"""
    key = (tab or "todo").strip().lower()
    if key not in {"todo", "notice", "progress"}:
        raise AppException("VALIDATION_ERROR", "tab 必须是 todo/notice/progress")
    current_page = max(1, int(page or 1))
    size = max(1, min(50, int(page_size or 20)))
    data = my_messages(user)
    source = list((data.get("groups") or {}).get(key) or [])
    start = (current_page - 1) * size
    items = source[start:start + size]
    return {
        "tabs": data.get("tabs") or [],
        "tab": key,
        "list": items,
        "page": current_page,
        "pageSize": size,
        "total": len(source),
        "hasMore": start + len(items) < len(source),
        "emergencyPending": data.get("emergencyPending") or [],
    }
'''
text = replace_once(text, "\n\ndef _resolve_uid(u: dict):", paged_messages_fn + "\n\ndef _resolve_uid(u: dict):", "student messages page wrapper")
write(rel, text)

# Teacher service paged wrappers.
rel = "backend/app/services/mobile_teacher_service.py"
text = read(rel)
teacher_pages = r'''

def todos_page(user: dict, group: str = "all", page: int = 1,
               page_size: int = 20) -> dict:
    """移动待办服务端分页；旧 todos() 保持兼容，移动页面不再一次接收完整聚合。"""
    data = todos(user)
    key = (group or "all").strip().lower()
    source = list(data.get("list") or [])
    if key not in {"all", "soon"}:
        source = [item for item in source if item.get("group") == key]
    elif key == "soon":
        source = [item for item in source if item.get("soon") and item.get("status") != "COMPLETED"]
    current_page = max(1, int(page or 1))
    size = max(1, min(50, int(page_size or 20)))
    start = (current_page - 1) * size
    items = source[start:start + size]
    filters = []
    for item in data.get("filters") or []:
        filter_key = item.get("key")
        if filter_key == "all":
            badge = sum(1 for row in data.get("list") or [] if row.get("status") != "COMPLETED")
        elif filter_key == "soon":
            badge = sum(1 for row in data.get("list") or []
                        if row.get("soon") and row.get("status") != "COMPLETED")
        else:
            badge = sum(1 for row in data.get("list") or []
                        if row.get("group") == filter_key and row.get("status") != "COMPLETED")
        filters.append({**item, "badge": badge})
    return {
        "filters": filters,
        "list": items,
        "page": current_page,
        "pageSize": size,
        "total": len(source),
        "pendingCount": int(data.get("pendingCount") or 0),
        "hasMore": start + len(items) < len(source),
        "scopeMode": data.get("scopeMode"),
    }


def risk_students_page(user: dict, level: str = "all", page: int = 1,
                       page_size: int = 20) -> dict:
    """风险学生服务端分页；按权限过滤完成后再分页。"""
    data = risk_students(user)
    source = list(data.get("list") or [])
    counts = {
        "HIGH": sum(1 for row in source if row.get("riskLevel") == "HIGH"),
        "MEDIUM": sum(1 for row in source if row.get("riskLevel") == "MEDIUM"),
    }
    requested = (level or "all").strip().upper()
    if requested not in {"ALL", "HIGH", "MEDIUM"}:
        raise AppException("VALIDATION_ERROR", "level 必须是 all/HIGH/MEDIUM")
    filtered = source if requested == "ALL" else [
        row for row in source if row.get("riskLevel") == requested
    ]
    current_page = max(1, int(page or 1))
    size = max(1, min(50, int(page_size or 20)))
    start = (current_page - 1) * size
    items = filtered[start:start + size]
    return {
        "list": items,
        "page": current_page,
        "pageSize": size,
        "total": len(filtered),
        "counts": counts,
        "hasMore": start + len(items) < len(filtered),
        "scopeMode": data.get("scopeMode"),
    }
'''
text = replace_once(text, "\n\n# ══════════ 风险学生（替代 PC /students 全列表） ══════════\n", teacher_pages + "\n\n# ══════════ 风险学生（替代 PC /students 全列表） ══════════\n", "teacher paged wrappers insertion")
write(rel, text)

# Routes and Query import.
rel = "backend/app/api/v1/mobile.py"
text = read(rel)
text = replace_once(
    text,
    "from fastapi import APIRouter, Body, Depends, Path, Request\n",
    "from fastapi import APIRouter, Body, Depends, Path, Query, Request\n",
    "mobile Query import",
)
text = replace_once(
    text,
    """@router.get("/me/messages", summary="我的消息（本人）")
def me_messages(user=Depends(get_current_user)):
    return success(stu.my_messages(user))


""",
    """@router.get("/me/messages", summary="我的消息（本人）")
def me_messages(user=Depends(get_current_user)):
    return success(stu.my_messages(user))


@router.get("/me/messages-page", summary="我的消息分页（本人）")
def me_messages_page(
    tab: str = Query(default="todo"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, alias="pageSize", ge=1, le=50),
    user=Depends(get_current_user),
):
    return success(stu.my_messages_page(user, tab=tab, page=page, page_size=page_size))


""",
    "mobile student messages route",
)
text = replace_once(
    text,
    """@router.get("/teacher/todos", summary="教师今日待办（本校）")
def teacher_todos(user=Depends(get_current_user)):
    return success(tea.todos(user))


""",
    """@router.get("/teacher/todos", summary="教师今日待办（本校）")
def teacher_todos(user=Depends(get_current_user)):
    return success(tea.todos(user))


@router.get("/teacher/todos-page", summary="教师今日待办分页（本校）")
def teacher_todos_page(
    group: str = Query(default="all"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, alias="pageSize", ge=1, le=50),
    user=Depends(get_current_user),
):
    return success(tea.todos_page(user, group=group, page=page, page_size=page_size))


@router.get("/teacher/risk-students-page", summary="教师风险学生分页（本校）")
def teacher_risk_students_page(
    level: str = Query(default="all"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, alias="pageSize", ge=1, le=50),
    user=Depends(get_current_user),
):
    return success(tea.risk_students_page(user, level=level, page=page, page_size=page_size))


""",
    "mobile teacher paged routes",
)
write(rel, text)

# ---------------------------------------------------------------------------
# Tests and permanent workflow.
# ---------------------------------------------------------------------------
package_rel = "miniapp/package.json"
package = json.loads(read(package_rel))
scripts = package.setdefault("scripts", {})
scripts["test"] = "node --test tests/*.test.mjs"
write(package_rel, json.dumps(package, ensure_ascii=False, indent=2) + "\n")

write("miniapp/tests/stage-a-contract.test.mjs", r"""import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const read = (relative) => fs.readFileSync(new URL(`../${relative}`, import.meta.url), 'utf8')

test('student home uses one aggregate request and lightweight message summary', () => {
  const page = read('src/pages/student/home/index.vue')
  const api = read('src/services/studentApi.js')
  const adapter = read('src/services/realApi.js')
  assert.doesNotMatch(page, /loadEmergency|getMessages\(\)/)
  assert.match(page, /messageSummary\?\.latestEmergency/)
  assert.match(page, /HOME_TTL_MS = 20_000/)
  assert.match(page, /_loadEpoch/)
  assert.match(api, /real\.studentHomeReal\(\)/)
  assert.match(adapter, /quickServices: \[\]/)
  assert.match(adapter, /todayCourses: \[\]/)
  assert.doesNotMatch(adapter.match(/export async function studentHomeReal\(\)[\s\S]*?export const enrichHome/)[0], /\.\.\.mock|mockHome/)
})

test('teacher workbench has TTL dirty-context checks and one workbench call', () => {
  const page = read('src/pages/teacher/workbench/index.vue')
  const adapter = read('src/services/realApi.js')
  assert.doesNotMatch(page, /onShow\(\) \{ this\.load\(\) \}/)
  assert.match(page, /WORKBENCH_TTL_MS = 20_000/)
  assert.match(page, /getTeacherWorkbenchVersion/)
  assert.match(page, /loadInternshipContext/)
  const loadBlock = page.match(/load\(\{ force = false[\s\S]*?\n    \},\n    quick\(q\)/)[0]
  assert.equal((loadBlock.match(/teacherApi\.getWorkbench/g) || []).length, 1)
  const adapterBlock = adapter.match(/export async function teacherWorkbenchReal[\s\S]*?export const enrichTeacherWorkbench/)[0]
  assert.doesNotMatch(adapterBlock, /\.\.\.mock/)
  assert.match(adapterBlock, /Promise\.allSettled/)
})

test('ordinary GETs are single-flight and writes are rejected rather than deduplicated', () => {
  const request = read('src/services/request.js')
  assert.match(request, /const _getInflight = new Map\(\)/)
  assert.match(request, /if \(normalizedMethod === 'GET'\)/)
  assert.match(request, /return _getInflight\.get\(key\)/)
  assert.match(request, /const _mutationInflight = new Set\(\)/)
  assert.match(request, /正在提交，请勿重复点击/)
  assert.match(request, /markMobileViewsDirty\(path\)/)
  assert.match(request, /body\.code === 401001[\s\S]*?_retried: true/)
  for (const code of ['403001', '409001', '422001', '429001']) assert.match(request, new RegExp(code))
  assert.doesNotMatch(request, /while \(current\.hasMore/)
  assert.match(request, /export function realUpload/)
  assert.match(request, /export function realDownload/)
})

test('production session skeleton contains no fixed student or teacher identity', () => {
  const session = read('src/stores/session.js')
  assert.match(session, /import\.meta\.env && import\.meta\.env\.PROD/)
  assert.match(session, /neutralUser/)
  assert.match(session, /name: '', studentNo: '', className: ''/)
})

test('high-frequency message, todo and risk pages use server pagination', () => {
  const messages = read('src/pages/student/messages/index.vue')
  const todos = read('src/pages/teacher/todos/index.vue')
  const risks = read('src/pages/teacher/risk-students/index.vue')
  assert.match(messages, /getMessagesPage/)
  assert.match(todos, /getTodosPage/)
  assert.match(risks, /getRiskStudentsPage/)
  for (const source of [messages, todos, risks]) {
    assert.match(source, /hasMore/)
    assert.match(source, /_loadEpoch/)
    assert.doesNotMatch(source, /pagedSlice/)
  }
})
""")

write("backend/tests/test_mobile_stage_a_contracts.py", r'''from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_mobile_home_returns_lightweight_message_summary_without_message_content():
    source = _read("app/services/mobile_student_service.py")
    block = source.split("def me_overview", 1)[1].split("def _home_cache_key", 1)[0]
    assert '"messageSummary"' in block
    assert '"emergencyPendingCount"' in block
    assert "notice_columns" in block
    assert "rendered_content_plain" not in block
    assert '"content"' not in block


def test_mobile_home_cache_is_tenant_and_stable_identity_scoped():
    source = _read("app/services/mobile_student_service.py")
    block = source.split("def _home_cache_key", 1)[1].split("def invalidate_home_cache", 1)[0]
    assert "tenantId" in block
    assert "studentId" in block
    assert "userId" in block
    assert "studentNo" not in block.split("return", 1)[1]


def test_mobile_home_observability_does_not_log_sql_or_parameters():
    source = _read("app/services/mobile_student_service.py")
    block = source.split("def home", 1)[1].split("def my_todos", 1)[0]
    assert "query_count=" in block
    assert "duration_ms=" in block
    assert "cache_set_json_if_absent" in block
    assert "random.randint" in block
    assert "statement" not in block
    assert "parameters" not in block


def test_stage_a_routes_are_bounded_and_do_not_touch_file_center():
    routes = _read("app/api/v1/mobile.py")
    assert '"/me/messages-page"' in routes
    assert '"/teacher/todos-page"' in routes
    assert '"/teacher/risk-students-page"' in routes
    assert "le=50" in routes
    assert "file_center" not in routes
''')

# Subpackage candidate report only; pages.json intentionally unchanged.
write("miniapp/docs/mp-weixin-subpackage-candidates.md", """# 微信小程序分包候选清单（阶段A仅审计，不施工）

当前学生端与教师端共用一个 uni-app 工程。公共文件中心正在新增页面、组件和SDK，
因此本阶段禁止大规模改动 `pages.json`，只冻结后续候选：

- 主包：登录、角色切换、学生首页、教师工作台、消息、个人中心、公共错误页。
- 学生学工分包：`pages/student/affairs/**`
- 学生教务分包：`pages/student/academic-affairs/**`
- 学生实习分包：学生 internship 相关页面。
- 学生毕设分包：学生 graduation 相关页面。
- 教师学工分包：`pages/teacher/affairs/**` 及高频审批页面。
- 教师教务分包：`pages/teacher/academic-affairs/**`、`academic-task/**`
- 教师实习分包：教师 internship 相关页面。
- 教师毕设分包：教师 graduation 相关页面。
- 公共文件中心分包：等待文件中心客户端目录稳定后由该工程统一裁决。

实施前必须重新生成页面依赖图，确认 tabBar 页面、跨分包组件、分包预下载和文件中心页面，
不得仅按目录机械拆分。
""")

# Permanent release workflow: add contracts and H5 build.
rel = ".github/workflows/miniapp-mp-weixin-release.yml"
text = read(rel)
text = replace_once(
    text,
    """      - name: 构建微信小程序生产包
        run: npm run build:mp-weixin:release
""",
    """      - name: 阶段A前端合同测试
        run: npm test

      - name: 构建 H5 兼容产物
        run: npm run build:h5

      - name: 构建微信小程序生产包
        run: npm run build:mp-weixin:release
""",
    "permanent workflow tests",
)
write(rel, text)

print("stage A patch applied")
