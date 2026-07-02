import { defineStore } from 'pinia'
import {
  fetchDashboardRaw,
  resolveRisk as resolveRiskApi,
  remindRisk as remindRiskApi,
  followUpRisk as followUpRiskApi,
  completeTask as completeTaskApi
} from '../provider/dashboard.provider.js'
import {
  normalizeDashboardData,
  buildDashboardMetrics,
  buildTaskCompletionMetric,
  buildRiskAlerts,
  buildTaskGroups,
  buildFocusStudents,
  buildHighRiskStudents,
  buildRiskHandleDetail,
  buildTaskHandleDetail,
  buildStudentHandleDetail,
  buildLatestOperationLogs
} from '../adapter/dashboard.adapter.js'
import { toast } from '@/utils/toast'

/**
 * 首页 Dashboard Store（前端生产级 UI 架构 V1）
 *
 * state 边界：
 * - 原始数据：provider → adapter 初始化写入（students/risks/tasks/operationLogs 等）
 * - API 快照：overviewMetrics/gdMetrics/internshipMetrics/lifecycleBannerStages（接后端后仍由 init 写入）
 * - UI 会话态：selectedRiskId/selectedTaskId/drawerVisible/drawerContext/showAllRisks
 * - 上下文：today（来自 API，供 taskGroups 截止时间比较）
 *
 * getters 边界：dashboardMetrics/taskCompletionMetric/riskAlerts/taskGroups 等均由 state 派生
 */
export const useDashboardStore = defineStore('dashboard-home', {
  state: () => ({
    loading: false,
    error: null,
    initialized: false,
    /** 原始数据 — 学生列表 */
    students: [],
    /** 原始数据 — 风险事件 */
    risks: [],
    /** 原始数据 — 教师待办（actions 会就地更新 status） */
    tasks: [],
    /** 原始数据 — 处理记录（actions 会 unshift 追加） */
    operationLogs: [],
    /** API 快照 — 生命周期阶段卡片，init 后不变；getter lifecycleStageCards 为其别名 */
    lifecycleStages: [],
    /** API 快照 — Banner 时间轴，与 lifecycleStages 结构不同，init 后不变 */
    lifecycleBannerStages: [],
    /** API 快照 — 专题 Tab「实践教学」指标，来自 getPracticeTeachingOverview */
    overviewMetrics: [],
    /** API 快照 — 专题 Tab「毕业设计」指标 */
    gdMetrics: [],
    /** API 快照 — 专题 Tab「岗位实习」指标 */
    internshipMetrics: [],
    /** 原始数据 — 数据口径说明 */
    dataQuality: {
      baseDate: '',
      updatedAt: '',
      dataSources: [],
      statisticScope: '',
      statisticRules: '',
      environment: ''
    },
    /** 原始数据 — 当前教师信息 */
    teacher: { teacherId: '', name: '', identity: '', dataScope: '' },
    /** UI 状态 — 抽屉选中风险 */
    selectedRiskId: null,
    /** UI 状态 — 抽屉选中待办 */
    selectedTaskId: null,
    drawerVisible: false,
    drawerContext: null,
    showAllRisks: false,
    /** 上下文 — 数据基准日，来自 provider，供 buildTaskGroups 比较 deadline */
    today: ''
  }),

  getters: {
    viewState(s) {
      if (s.loading) return 'loading'
      if (s.error) return 'error'
      if (!s.initialized) return 'empty'
      return 'ready'
    },

    lifecycleStageCards: (s) => s.lifecycleStages,

    highRiskStudents(s) {
      return buildHighRiskStudents({ students: s.students, risks: s.risks })
    },
    highRiskCount(s) {
      return buildHighRiskStudents({ students: s.students, risks: s.risks }).length
    },
    focusStudents(s) {
      return buildFocusStudents({ students: s.students, risks: s.risks })
    },
    focusStudentCount(s) {
      return buildFocusStudents({ students: s.students, risks: s.risks }).length
    },

    pendingRisks: (s) => s.risks.filter((r) => r.status === 'pending' || r.status === 'processing'),
    resolvedRisks: (s) => s.risks.filter((r) => r.status === 'resolved'),
    activeRisks: (s) => buildRiskAlerts({ risks: s.risks }),
    riskAlerts: (s) => buildRiskAlerts({ risks: s.risks }),

    displayedRiskAlerts(s) {
      const list = this.activeRisks
      return s.showAllRisks ? list : list.slice(0, 3)
    },

    pendingTasks: (s) => s.tasks.filter((t) => t.status !== 'done'),
    completedTasks: (s) => s.tasks.filter((t) => t.status === 'done'),
    activeTodoTotal() {
      return this.pendingTasks.length
    },

    taskGroups(s) {
      return buildTaskGroups(s.tasks, s.today)
    },

    limitedTaskGroups() {
      const cap = (arr) => arr.slice(0, 3)
      const g = this.taskGroups
      return {
        urgent: cap(g.urgent),
        weekFocus: cap(g.weekFocus),
        deferred: cap(g.deferred)
      }
    },

    /** 待办完成率指标 — 由 tasks 派生，resolveRisk/completeTask 后自动重算 */
    taskCompletionMetric(s) {
      return buildTaskCompletionMetric(s.tasks)
    },

    taskCompletionRate() {
      return this.taskCompletionMetric?.value ?? 0
    },

    /** 首页 KPI — 合并 API 快照指标与派生待办完成率 */
    dashboardMetrics(s) {
      if (!s.initialized) return []
      return buildDashboardMetrics({
        overviewMetrics: s.overviewMetrics,
        tasks: s.tasks,
        risks: s.risks,
        students: s.students,
        taskCompletionMetric: this.taskCompletionMetric
      })
    },

    bannerCapsules() {
      return [
        { type: 'todo', label: '今日待办', value: `${this.activeTodoTotal} 项` },
        { type: 'risk', label: '高风险学生', value: `${this.highRiskCount} 人` },
        { type: 'update', label: '数据更新', value: this.dataQuality.updatedAt || '14:00' }
      ]
    },

    teacherRole(s) {
      if (!s.teacher.name) return '体验管理员'
      return `${s.teacher.name} · ${s.teacher.identity}`
    },

    workbenchSubtitle(s) {
      return s.teacher.name ? `${s.teacher.name} · ${s.teacher.dataScope}` : '教师工作台'
    },

    selectedRisk(s) {
      if (!s.selectedRiskId) return null
      return s.risks.find((r) => r.riskId === s.selectedRiskId) || null
    },

    selectedTask(s) {
      if (!s.selectedTaskId) return null
      return s.tasks.find((t) => t.taskId === s.selectedTaskId) || null
    },

    selectedStudent(s) {
      const sid =
        s.drawerContext?.studentId || this.selectedRisk?.studentId || this.selectedTask?.studentId
      if (!sid) return null
      return s.students.find((st) => st.studentId === sid) || null
    },

    selectedHandleDetail(s) {
      const ctx = s.drawerContext
      if (!ctx) return null
      if (ctx.type === 'risk') {
        const risk = s.risks.find((r) => r.riskId === ctx.id)
        if (!risk) return null
        const student = risk.studentId
          ? s.students.find((st) => st.studentId === risk.studentId)
          : null
        return buildRiskHandleDetail(risk, student)
      }
      if (ctx.type === 'task') {
        const task = s.tasks.find((t) => t.taskId === ctx.id)
        if (!task) return null
        const student = task.studentId
          ? s.students.find((st) => st.studentId === task.studentId)
          : null
        return buildTaskHandleDetail(task, student, s.teacher.name)
      }
      if (ctx.type === 'student') {
        const student = s.students.find((st) => st.studentId === ctx.id)
        if (!student) return null
        return buildStudentHandleDetail(
          student,
          s.risks.some(
            (r) =>
              r.studentId === student.studentId &&
              r.status !== 'resolved' &&
              r.status !== 'ignored'
          )
        )
      }
      return null
    },

    /** @deprecated 使用 selectedHandleDetail */
    selectedRiskDetail() {
      return this.selectedHandleDetail
    },

    drawerTitle(s) {
      if (!s.drawerContext) return '风险处理'
      const map = { risk: '风险处理', task: '待办处理', student: '学生风险跟进' }
      return map[s.drawerContext.type] || '风险处理'
    },

    latestOperationLogs: (s) => buildLatestOperationLogs(s.operationLogs)
  },

  actions: {
    async initDashboard(teacherId = 't-002') {
      this.loading = true
      this.error = null
      try {
        const raw = await fetchDashboardRaw(teacherId)
        const vm = normalizeDashboardData(raw)
        this.students = vm.students
        this.risks = vm.risks
        this.tasks = vm.tasks
        this.operationLogs = vm.operationLogs
        this.lifecycleStages = vm.lifecycleStages
        this.lifecycleBannerStages = vm.lifecycleBannerStages
        this.overviewMetrics = vm.overviewMetrics
        this.gdMetrics = vm.gdMetrics
        this.internshipMetrics = vm.internshipMetrics
        this.dataQuality = vm.dataQuality
        this.teacher = vm.teacher
        this.today = raw.today
        this.initialized = true
      } catch (e) {
        this.error = e.message || '加载失败'
        this.showToast('首页数据加载失败', 'warning')
      } finally {
        this.loading = false
      }
    },

    openRiskDrawer(riskId) {
      const risk = this.risks.find((r) => r.riskId === riskId)
      if (!risk) {
        this.showToast('未找到对应风险记录', 'warning')
        return
      }
      this.selectedRiskId = riskId
      this.selectedTaskId = null
      this.drawerContext = { type: 'risk', id: riskId, studentId: risk.studentId }
      this.drawerVisible = true
    },

    openTaskDrawer(taskId) {
      const task = this.tasks.find((t) => t.taskId === taskId)
      if (!task) {
        this.showToast('未找到对应待办任务', 'warning')
        return
      }
      this.selectedTaskId = taskId
      this.drawerContext = {
        type: 'task',
        id: taskId,
        studentId: task.studentId,
        relatedRiskId: task.relatedRiskId
      }
      if (task.relatedRiskId) this.selectedRiskId = task.relatedRiskId
      this.drawerVisible = true
    },

    openStudentDrawer(studentId) {
      const student = this.students.find((s) => s.studentId === studentId)
      if (!student) {
        this.showToast('未找到对应学生', 'warning')
        return
      }
      this.selectedTaskId = null
      this.drawerContext = { type: 'student', id: studentId, studentId }
      const risk = this.risks.find((r) => r.studentId === studentId && r.status !== 'resolved')
      this.selectedRiskId = risk?.riskId || null
      this.drawerVisible = true
    },

    closeHandleDrawer() {
      this.drawerVisible = false
      this.drawerContext = null
      this.selectedRiskId = null
      this.selectedTaskId = null
    },

    /** @deprecated 使用 closeHandleDrawer */
    closeRiskDrawer() {
      this.closeHandleDrawer()
    },

    handleRiskAlert(riskId, scrollToStudent) {
      const risk = this.risks.find((r) => r.riskId === riskId)
      if (!risk) {
        this.showToast('未找到对应风险记录', 'warning')
        return
      }
      if (risk.studentId && scrollToStudent) {
        scrollToStudent(risk.studentId)
        setTimeout(() => this.openRiskDrawer(riskId), 400)
        return
      }
      this.openRiskDrawer(riskId)
    },

    async remindStudent(riskId) {
      const id = riskId || this.selectedRiskId
      const risk = this.risks.find((r) => r.riskId === id)
      if (!risk) {
        this.showToast('未找到对应风险，无法发起提醒', 'warning')
        return
      }

      try {
        await remindRiskApi(risk.riskId, { operatorId: this.teacher.teacherId || 'current-user' })
      } catch {
        this.showToast('提醒发送失败，请稍后重试', 'warning')
        return
      }

      if (risk.status === 'pending') {
        risk.status = 'processing'
        risk.statusLabel = '处理中'
      }

      const student = risk.studentId
        ? this.students.find((s) => s.studentId === risk.studentId)
        : null
      this.appendOperationLog({
        action: `发起提醒：${risk.riskTitle}`,
        target: student?.name || risk.riskTitle,
        result: '已发送',
        status: 'processing',
        relatedRiskId: risk.riskId,
        studentId: risk.studentId
      })
      this.showToast(`已向 ${student?.name || '相关对象'} 发送提醒通知`, 'success')
    },

    contactStudent() {
      const detail = this.selectedHandleDetail
      if (!detail) {
        this.showToast('当前无处理对象', 'warning')
        return
      }
      this.showToast(`已向 ${detail.studentName || '学生'} 发起联系`, 'info')
    },

    async addFollowUp(riskId, content) {
      const id = riskId || this.selectedRiskId
      const risk = this.risks.find((r) => r.riskId === id)
      if (!risk) {
        this.showToast('未找到对应风险，无法保存跟进', 'warning')
        return
      }

      try {
        await followUpRiskApi(id, {
          content: content || '填写风险跟进记录',
          operatorId: this.teacher.teacherId || 'current-user'
        })
      } catch {
        this.showToast('跟进保存失败，请稍后重试', 'warning')
        return
      }

      if (risk.status === 'pending') {
        risk.status = 'processing'
        risk.statusLabel = '处理中'
      }

      const student = risk.studentId
        ? this.students.find((s) => s.studentId === risk.studentId)
        : null
      this.appendOperationLog({
        action: content ? `填写跟进：${content}` : '填写风险跟进记录',
        target: student?.name || risk.riskTitle,
        result: '已记录',
        status: 'processing',
        relatedRiskId: risk.riskId,
        studentId: risk.studentId
      })
      this.showToast('跟进记录已保存', 'info')
    },

    async resolveRisk(riskId) {
      const ctx = this.drawerContext
      if (!ctx) {
        this.showToast('请先选择要处理的风险或待办', 'warning')
        return
      }

      if (ctx.type === 'risk' || (ctx.type === 'task' && ctx.relatedRiskId)) {
        const rid = ctx.type === 'risk' ? riskId || ctx.id : ctx.relatedRiskId
        const risk = this.risks.find((r) => r.riskId === rid)
        if (!risk) {
          this.showToast('未找到对应风险记录', 'warning')
          return
        }

        try {
          await resolveRiskApi(rid, { operatorId: this.teacher.teacherId || 'current-user' })
        } catch {
          this.showToast('风险处理失败，请稍后重试', 'warning')
          return
        }

        risk.status = 'resolved'
        risk.statusLabel = '已处理'
        // 风险解除时，同步完成关联的处理类待办
        this.tasks
          .filter((t) => t.relatedRiskId === rid || (risk.relatedTaskIds || []).includes(t.taskId))
          .forEach((t) => {
            t.status = 'done'
          })

        const student = risk.studentId
          ? this.students.find((s) => s.studentId === risk.studentId)
          : null
        this.appendOperationLog({
          action: `处理风险：${risk.riskTitle}`,
          target: student?.name || risk.riskTitle,
          result: '已跟进',
          status: 'done',
          relatedRiskId: rid,
          studentId: risk.studentId
        })
      } else if (ctx.type === 'task') {
        await this.completeTask(ctx.id)
        this.closeHandleDrawer()
        return
      } else if (ctx.type === 'student') {
        const student = this.students.find((s) => s.studentId === ctx.id)
        if (!student) {
          this.showToast('未找到对应学生', 'warning')
          return
        }
        const activeRisks = this.risks.filter(
          (r) => r.studentId === student.studentId && r.status !== 'resolved' && r.status !== 'ignored'
        )
        activeRisks.forEach((risk) => {
          risk.status = 'resolved'
          risk.statusLabel = '已处理'
        })
        this.appendOperationLog({
          action: `跟进学生：${student.name}`,
          target: student.name,
          result: '已跟进',
          status: 'done',
          studentId: student.studentId,
          relatedRiskId: activeRisks[0]?.riskId
        })
      }

      this.closeHandleDrawer()
      this.showToast('已标记处理，处理记录已自动留痕', 'success')
    },

    /**
     * 完成待办。
     *
     * 策略说明：
     * - 单独完成待办（如审核周报、退回材料）不等于风险已解除，因此不自动 resolveRisk。
     * - 风险解除请走 resolveRisk，由 resolveRisk 反向同步完成关联处理类待办。
     * - 无关联风险的待办，仅更新 task.status 并留痕。
     */
    async completeTask(taskId) {
      const task = this.tasks.find((t) => t.taskId === taskId)
      if (!task) {
        this.showToast('未找到对应待办任务', 'warning')
        return
      }
      if (task.status === 'done') {
        this.showToast('该待办已完成', 'info')
        return
      }

      try {
        await completeTaskApi(taskId, { operatorId: this.teacher.teacherId || 'current-user' })
      } catch {
        this.showToast('待办处理失败，请稍后重试', 'warning')
        return
      }

      task.status = 'done'
      this.appendOperationLog({
        action: `处理待办：${task.title}`,
        target: task.studentName || task.title,
        result: '已跟进',
        status: 'done',
        relatedTaskId: task.taskId,
        studentId: task.studentId,
        relatedRiskId: task.relatedRiskId
      })
      this.showToast('待办已标记完成', 'success')
    },

    appendOperationLog(partial) {
      if (!partial?.action) return
      const log = {
        recordId: `rec-${Date.now()}`,
        time: formatNow(this.today),
        operator: this.teacher.name || '当前用户',
        action: partial.action,
        target: partial.target || '',
        result: partial.result || '已跟进',
        status: partial.status || 'done',
        relatedRiskId: partial.relatedRiskId,
        studentId: partial.studentId,
        relatedTaskId: partial.relatedTaskId,
        closed: partial.status === 'done' || partial.closed === true,
        riskId: partial.relatedRiskId,
        taskId: partial.relatedTaskId
      }
      this.operationLogs.unshift(log)
    },

    showToast(message, type = 'success') {
      if (type === 'info') toast.info(message)
      else if (type === 'warning') toast.warning(message)
      else toast.success(message)
    },

    setShowAllRisks(v) {
      this.showAllRisks = v
    }
  }
})

/** @deprecated 使用 useDashboardStore */
export const useHomeDashboardStore = useDashboardStore

function formatNow(today) {
  const d = new Date()
  const p = (n) => String(n).padStart(2, '0')
  const base = today || d.toISOString().slice(0, 10)
  return `${base} ${p(d.getHours())}:${p(d.getMinutes())}`
}
