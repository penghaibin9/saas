<template>
  <view class="teacher-shell">
    <MobileTeacherHero title="工作台" :subtitle="user.tenantName || brand.schoolName" :role-label="currentRoleTitle" :primary-text="(user.name || '老师') + '，' + greeting" :secondary-text="today" />
    <MobileGlobalState v-if="state !== 'ready'" :state="state" @retry="retryLoad" />
    <view v-else-if="wb" class="ts-pad">
        <MobileInlineAlert v-if="internshipContextError" type="warning" :description="internshipContextError" />
        <view v-if="selectedInternshipBatch" class="ts-panel wb-batch"><text class="ts-muted">当前岗位实习批次</text><text class="ts-row-title">{{ selectedInternshipBatch.name }}</text><text class="ts-muted">{{ selectedInternshipBatch.academicYear }} {{ selectedInternshipBatch.term }} · {{ internshipBatchStatus(selectedInternshipBatch.status) }}</text></view>
        <view class="ts-panel">
          <view class="ts-heading"><view class="ts-title"><view class="ts-marker" /><text>待我处理</text><text class="ts-count">（{{ todoBadge }}）</text></view><button class="ts-link ts-plain" @click="go('/pages/teacher/todos/index')">全部待办<MobileShellIcon name="chevron-right" :size="16" /></button></view>
          <view v-if="wb.partialFailures && wb.partialFailures.todos" class="ts-error"><text>待办加载失败</text><button class="ts-link ts-plain" @click="retryLoad">重试</button></view>
          <view v-else-if="!priorityTodos.length" class="ts-empty">暂无待处理事项，新的任务会显示在这里。</view>
          <view v-else>
            <view v-for="(t,index) in priorityTodos" :key="t.todoId || t.id" class="ts-row wb-task" @click="handleTodo(t)">
              <MobileShellIcon :name="visual(t.title).icon" :tone="visual(t.title).tone" :size="26" round />
              <view class="ts-body"><view class="wb-task-head"><text class="ts-row-title">{{ t.title }}</text><MobileStatusTag :status="t.status" /></view>
                <text v-if="t.student || t.studentName" class="ts-muted">{{ t.student || t.studentName }}{{ t.className ? ' · ' + t.className : '' }}</text>
                <text class="ts-muted">{{ messageModuleLabel(t.module || t.sourceModule) }}</text>
                <view class="wb-task-foot"><text v-if="t.deadline" class="ts-muted" :class="{ 'wb-overdue': isOverdue(t.deadline) }">{{ deadlineText(t.deadline) }}</text>
                  <button v-if="canOpen(t)" :class="index === 0 ? 'ts-action' : 'ts-link ts-plain'" @click.stop="handleTodo(t)">{{ index === 0 ? '查看办理' : '查看' }}<MobileShellIcon v-if="index !== 0" name="chevron-right" :size="16" /></button>
                </view><text v-if="!canOpen(t)" class="ts-muted">{{ blockedReason(t) }}</text>
              </view>
            </view>
          </view>
          <view v-if="extraMetrics.length" class="wb-metrics"><text v-for="m in extraMetrics" :key="m.key">{{ m.label }} {{ m.value }}</text></view>
        </view>
        <view v-if="riskCount || wb.partialFailures?.risk" class="ts-panel">
          <view class="ts-heading"><view class="ts-title"><view class="ts-marker wb-risk-marker" /><text>需要关注</text></view><button class="ts-link ts-plain" @click="goRiskList">风险台账<MobileShellIcon name="chevron-right" :size="16" /></button></view>
          <view v-if="wb.partialFailures?.risk" class="ts-error"><text>关注事项加载失败</text><button class="ts-link ts-plain" @click="retryLoad">重试</button></view>
          <view v-for="r in wb.riskStudents" :key="r.id || r.studentId" class="ts-row" @click="openStudent(r)"><MobileShellIcon name="alert-circle" tone="red" :size="24" round /><view class="ts-body"><text class="ts-row-title">{{ r.name }}</text><text class="ts-muted">{{ r.className }} · {{ r.typeLabel || riskTypeLabel(r.type) }}</text></view><button class="ts-link ts-plain" @click.stop="handleRisk(r)">查看</button></view>
        </view>
        <view class="ts-panel"><MobileTeacherCommonServices ref="commonServices" :services="commonServices" :storage-key="commonServicesStorageKey" :role="roleConfig.key" @open="quick" /></view>
        <view class="ts-panel"><view class="ts-heading"><view class="ts-title"><view class="ts-marker" /><text>学校通知</text></view><button class="ts-link ts-plain" @click="go('/pages/teacher/messages/index')">更多<MobileShellIcon name="chevron-right" :size="16" /></button></view>
          <view v-if="noticeState === 'loading' && !notices.length" class="ts-empty">正在加载通知…</view>
          <view v-else-if="noticeState === 'error'" class="ts-error"><text>通知加载失败</text><button class="ts-link ts-plain" @click="loadNotices()">重试</button></view>
          <view v-else-if="!notices.length" class="ts-empty">暂无学校通知。</view>
          <view v-for="n in notices" :key="n.id" class="ts-row" @click="openNotice(n)"><MobileShellIcon name="bell" tone="violet" :size="24" round /><view class="ts-body"><text class="ts-row-title">{{ n.title }}</text><text class="ts-muted">{{ n.module }} · {{ fromNow(n.time || n.eventAt) }}</text></view></view>
        </view>
        <view v-if="wb.recent && wb.recent.length" class="ts-panel"><view class="ts-heading"><text class="ts-title">最近学生动态</text></view><view v-for="a in wb.recent" :key="a.id" class="ts-row"><view class="ts-body"><text class="ts-row-title">{{ a.name }} {{ a.text }}</text><text class="ts-muted">{{ fromNow(a.time) }}</text></view></view></view>
    </view>
    <MobileTeacherTabBar ref="badges" active="workbench" :pending="wb ? todoBadge : null" />
  </view>
</template>

<script>
import { normalizeError } from '@/services/request'
import { tenantBrandConfig } from '@/config'
import { useSessionStore } from '@/stores/session'
import { useInternshipContextStore } from '@/stores/internshipContext'
import { teacherApi } from '@/services/teacherApi'
import { me } from '@/services/realApi'
import { currentSessionGeneration } from '@/services/sessionGeneration.mjs'
import { commonServiceStorageKey } from '@/services/teacherCommonServices.mjs'
import { ensureTeacherPerformanceApi } from '@/services/mobilePerformanceInstaller.teacher'
import { runAction } from '@/services/actionRouter'
import { canNavigate, disabledReasonOf } from '@/services/actionRouter'
import { getTeacherWorkbenchVersion } from '@/utils/viewFreshness'
import { deadlineText, isOverdue, fromNow } from '@/utils/format'
import { go, toast } from '@/utils/nav'
import { getTeacherMessagesPage } from '@/services/teacherMessagesV3Api'
import { messageModuleLabel } from '@/services/messagePresentation'
import { stashDetail } from '@/utils/msgStash'
import { teacherServiceRoute, teacherServices, teacherVisual, teacherDateText, teacherGreeting } from '@/services/teacherServiceCatalog.mjs'

const WORKBENCH_TTL_MS = 20_000



ensureTeacherPerformanceApi()

export default {
  data() {
    return {
      brand: tenantBrandConfig, wb: null, state: 'loading', user: {}, roleConfig: {},
      internshipContextReady: false, internshipContextError: '',
      lastLoadedAt: 0, loadedContextKey: '', loadedFreshnessVersion: -1, notices: [], noticeState: 'loading', today: teacherDateText(), greeting: teacherGreeting()
    }
  },
  computed: {
    commonServicesStorageKey() { return commonServiceStorageKey(useSessionStore()) },
    commonServices() {
      const session = useSessionStore()
      const context = this.internshipContextReady ? useInternshipContextStore() : null
      return teacherServices(this.roleConfig, session.currentRole, context).filter(q => q.path && !q.disabledReason)
    },
    priorityTodos() { return (this.wb?.dueSoon || []).slice(0,2) },
    extraMetrics() { return (this.wb?.metrics || []).filter(m => !['pending','todo'].includes(m.key)).map(m => ({ ...m, label: m.label === '24h到期' ? '24小时内到期' : m.label })) },
    todoBadge() {
      if (!this.wb) return 0
      if (this.wb.pendingTotal != null) return Number(this.wb.pendingTotal) || 0
      const m = (this.wb.metrics || []).find((x) => ['pending', 'todo', 'weekly', 'review', 'warning'].includes(x.key))
      return m ? Number(m.value) || 0 : 0
    },
    selectedInternshipBatch() {
      const session = useSessionStore()
      if (session.currentRole !== 'intern_mentor') return null
      return useInternshipContextStore().selectedBatch
    },
    currentRoleTitle() {
      const title = String(this.wb?.contextTitle || '').trim()
      return !title || /^[A-Z][A-Z0-9_]*$/.test(title) ? (this.roleConfig.label || title || '教师') : title
    },
    riskCount() { return Array.isArray(this.wb?.riskStudents) ? this.wb.riskStudents.length : 0 }
  },
  onLoad() {
    this._pageActive = true
  },
  onShow() {
    this._pageActive = true
    this.today = teacherDateText(); this.greeting = teacherGreeting()
    this.ensureFresh().catch(() => {})
    this.$refs?.badges?.refresh()
  },
  onHide() {
    this.$refs?.badges?.invalidate()
    this.$refs?.commonServices?.cancelEdit()
    this._pageActive = false
    this._loadEpoch = (this._loadEpoch || 0) + 1
    this._workbenchPromise = null
  },
  onUnload() {
    this._pageActive = false
    this._loadEpoch = (this._loadEpoch || 0) + 1
    this._workbenchPromise = null
  },
  onPullDownRefresh() {
    this.load({ force: true, done: () => uni.stopPullDownRefresh() })
  },
  methods: {
    internshipBatchStatus(value) { return ({ DRAFT: '草稿', RUNNING: '进行中', CLOSED: '已结束', ARCHIVED: '已归档', VOIDED: '已作废' }[value] || '状态待确认') },
    riskTypeLabel(value) { return ({ ACADEMIC: '学业风险', ATTENDANCE: '考勤风险', DISCIPLINE: '纪律风险', MENTAL: '心理关注', FINANCIAL: '资助风险', INTERNSHIP: '实习风险', EMPLOYMENT: '就业风险', SAFETY: '安全风险' }[value] || '风险类型待确认') },
    go, deadlineText, isOverdue, fromNow, visual: teacherVisual, messageModuleLabel,
    canOpen(t) { return canNavigate(t?.action, 'teacher') },
    blockedReason(t) { return disabledReasonOf(t?.action) || '该事项暂不可办理，请进入全部待办查看。' },
    async loadNotices(contextKey = this.contextKey(useSessionStore())) {
      const seq = (this._noticeSeq || 0) + 1; this._noticeSeq = seq
      this.noticeState = 'loading'
      try {
        const data = await getTeacherMessagesPage({ tab: 'system', pageSize: 2 })
        if (!this._pageActive || seq !== this._noticeSeq || contextKey !== this.contextKey(useSessionStore())) return
        this.notices = data.items || []; this.noticeState = 'ready'
      } catch (_) {
        if (this._pageActive && seq === this._noticeSeq && contextKey === this.contextKey(useSessionStore())) this.noticeState = 'error'
      }
    },
    openNotice(message) {
      stashDetail(message)
      go('/pages/common/message-detail/index?messageId=' + encodeURIComponent(String(message.messageId || message.id || '')))
    },

    contextKey(session) {
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
      if (!fresh) return this.load()
      this.loadNotices(contextKey)
      return Promise.resolve(this.wb)
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

      const epoch = (this._loadEpoch || 0) + 1, generation = currentSessionGeneration()
      this._loadEpoch = epoch
      this.user = session.mockUser || {}
      this.roleConfig = session.roleConfig
      if (!this.wb || force) this.state = 'loading'
      if (this.loadedContextKey !== beforeContextKey) { this.wb = null; this.notices = []; this.state = 'loading' }

      const pending = (async () => {
        const identity = await me()
        if (!this._pageActive || this._loadEpoch !== epoch || generation !== currentSessionGeneration()) return
        session.applyRealUser(identity)
        if (!session.isTeacher) { this.state = 'forbidden'; return }
        this.user = session.mockUser || {}; this.roleConfig = session.roleConfig
        await this.loadInternshipContext(session, force)
        if (!this._pageActive || this._loadEpoch !== epoch || generation !== currentSessionGeneration()) return
        const contextKey = this.contextKey(session)
        const workbench = await teacherApi.getWorkbench(session.currentRole)
        if (!this._pageActive || this._loadEpoch !== epoch || generation !== currentSessionGeneration() ||
            this.contextKey(useSessionStore()) !== contextKey) return workbench
        this.wb = workbench
        this.loadedContextKey = contextKey
        this.loadedFreshnessVersion = freshness
        this.lastLoadedAt = Date.now()
        this.state = 'ready'
        this.loadNotices(contextKey)
        return workbench
      })().catch((error) => {
        if (this._pageActive && this._loadEpoch === epoch && generation === currentSessionGeneration()) this.state = normalizeError(error).pageState || 'error'
        throw error
      }).finally(() => {
        if (this._workbenchPromise === pending) this._workbenchPromise = null
        if (done) done()
      })
      this._workbenchPromise = pending
      return pending
    },
    quick(q) {
      const session = useSessionStore()
      const path = teacherServiceRoute(q.key, session.currentRole)
      if (path) return go(path)
      toast('当前入口尚未配置，请联系管理员')
    },
    goRiskList() {
      const session = useSessionStore()
      go(session.currentRole === 'intern_mentor'
        ? '/pages/teacher-internship/internship-risk/index'
        : '/pages/teacher/affairs-review/index?type=RISK_HANDLE')
    },
    handleTodo(t) { return runAction(t && t.action, { side: 'teacher' }) },
    handleRisk(r) {
      const session = useSessionStore()
      if (session.currentRole === 'intern_mentor') return go('/pages/teacher-internship/internship-risk/index')
      if (r && r.actionType === 'RISK_HANDLE') return go('/pages/teacher/affairs-review/index?type=RISK_HANDLE')
      go('/pages/teacher/risk-students/index')
    },
    openStudent(r) { go('/pages/teacher/student-detail/index?id=' + r.id) }
  }
}
</script>

<style lang="scss">
@import '@/styles/teacher-shell.scss';
.teacher-shell {
.wb-task { align-items: flex-start !important; }
.wb-task-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 8px; margin-bottom: 4px; }
.wb-task-head .ts-row-title { flex: 1; }
.wb-task-foot { display: flex; flex-wrap: wrap; align-items: center; justify-content: flex-end; gap: 8px; margin-top: 8px; }
.wb-task-foot > text { flex: 1; }
.wb-overdue { color: #dc4545 !important; }.wb-risk-marker { background: #ed5353 !important; }
.wb-batch { padding-top: 14px !important; padding-bottom: 14px !important; }
.wb-metrics { display: flex; gap: 6px 14px; flex-wrap: wrap; padding: 12px 0; border-top: 1px solid #edf0f5; font-size: 12px; color: #62738e; }
}
</style>
