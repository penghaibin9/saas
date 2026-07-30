<template>
  <view class="page-wrap">
    <MobileGlobalState :state="state" @retry="retryLoad">
      <view class="wb__hero hero-band is-teacher">
        <view class="hero-band__orb" />
        <view class="mnav__status" :style="{ height: statusBarHeight + 'px' }" />
        <view class="wb__greet">
          <view class="avatar-badge">{{ (user.name || '老师').slice(0,1) }}</view>
          <view class="flex-1">
            <text class="wb__greet-name">{{ user.name || '老师' }}</text>
            <text class="wb__greet-sub">{{ brand.schoolName }}</text>
          </view>
          <view class="wb__bell" @click="go('/pages/teacher/messages/index')">
            <text class="wb__bell-icon">✉</text>
          </view>
        </view>
        <view class="wb__rolepill" v-if="wb" @click="go('/pages/role-switch/index')">
          <text class="wb__rolepill-dot" />当前身份：{{ wb.contextTitle }}<text class="wb__rolepill-chev">▾</text>
        </view>
        <view class="stat-strip" v-if="wb">
          <view class="stat-strip__item" v-for="m in wb.metrics" :key="m.key"><text class="stat-strip__val">{{ m.value }}</text><text class="stat-strip__label">{{ m.label }}</text></view>
        </view>
      </view>

      <view v-if="wb">
        <view class="page-pad wb__content" style="padding-top:0;">
          <MobileInlineAlert v-if="internshipContextError" type="warning" :description="internshipContextError" />

          <view v-if="selectedInternshipBatch" class="wb__batch card">
            <view class="wb__batch-copy">
              <text class="wb__batch-label">当前岗位实习批次</text>
              <text class="wb__batch-name">{{ selectedInternshipBatch.name }}</text>
              <text class="wb__batch-meta">{{ selectedInternshipBatch.academicYear }} {{ selectedInternshipBatch.term }} · {{ selectedInternshipBatch.studentCount }}人</text>
            </view>
            <text class="wb__batch-status">{{ selectedInternshipBatch.status }}</text>
          </view>

          <view class="card wb__brief">
            <view class="wb__brief-head">
              <view>
                <text class="wb__brief-eyebrow">今日工作结论</text>
                <text class="wb__brief-title">{{ workbenchConclusion }}</text>
              </view>
              <text class="wb__brief-time">下拉可刷新</text>
            </view>
            <view class="wb__brief-metrics">
              <view class="wb__brief-metric" :class="{ 'is-warning': dueSoonCount > 0 }">
                <text>{{ dueSoonCount }}</text><text>即将超时</text>
              </view>
              <view class="wb__brief-metric" :class="{ 'is-danger': riskCount > 0 }">
                <text>{{ riskCount }}</text><text>风险学生</text>
              </view>
              <view class="wb__brief-metric">
                <text>{{ visibleQuickActions.length }}</text><text>可用操作</text>
              </view>
            </view>
            <view class="wb__brief-next">
              <text class="wb__brief-next-label">建议先做</text>
              <text class="wb__brief-next-text">{{ nextActionText }}</text>
            </view>
          </view>

          <view class="section-head"><text class="section-head__title">快捷操作</text><text class="wb__section-hint">按当前身份和权限展示</text></view>
          <view class="card wb__quick-card">
            <view class="icon-grid">
              <view v-for="(q, i) in visibleQuickActions" :key="q.key" class="icon-grid__item" @click="quick(q)">
                <view class="icon-grid__badge" :class="gradClass(i)">{{ q.icon }}</view>
                <text class="icon-grid__label">{{ q.label }}</text>
              </view>
            </view>
            <MobileGlobalState v-if="!visibleQuickActions.length" state="empty" title="当前身份暂无可操作入口"
              description="快捷操作由服务端角色权限生成；需要更多权限请联系学校管理员。" />
          </view>

          <view class="section-head">
            <view><text class="section-head__title">即将超时</text><text class="wb__section-sub">优先处理临近截止或已经逾期的事项</text></view>
            <text class="section-head__more" @click="go('/pages/teacher/todos/index')">全部待办 ›</text>
          </view>
          <view class="stack-sm" v-if="wb.dueSoon && wb.dueSoon.length">
            <MobileTodoCard
              v-for="t in wb.dueSoon"
              :key="t.id"
              :title="t.title"
              :source-module="t.module"
              :student-name="t.student"
              :deadline="deadlineText(t.deadline)"
              :status="t.status"
              :overdue="isOverdue(t.deadline)"
              action-text="去处理"
              @handle="handleTodo(t)"
              @view="handleTodo(t)"
            />
          </view>
          <view v-else class="card wb__quiet"><text class="wb__quiet-title">暂无临近超时事项</text><text class="wb__quiet-text">当前待办没有需要立即处理的截止风险。</text></view>

          <view class="section-head">
            <view><text class="section-head__title">风险学生</text><text class="wb__section-sub">关注高风险和长期未闭环问题</text></view>
            <text class="section-head__more" @click="goRiskList">风险台账 ›</text>
          </view>
          <view class="stack-sm" v-if="wb.riskStudents && wb.riskStudents.length">
            <view v-for="r in wb.riskStudents" :key="r.id" class="wb__risk card" @click="openStudent(r)">
              <view class="wb__risk-avatar">{{ r.name.slice(0,1) }}</view>
              <view class="flex-1 wb__risk-copy">
                <view class="row" style="gap:6px;">
                  <text class="t-md t-bold">{{ r.name }}</text>
                  <MobileRiskTag :level="r.level" />
                </view>
                <text class="wb__risk-type">{{ r.className }} · {{ r.type }}</text>
              </view>
              <text class="wb__risk-btn" @click.stop="handleRisk(r)">处理</text>
            </view>
          </view>
          <view v-else class="card wb__quiet"><text class="wb__quiet-title">暂无风险学生</text><text class="wb__quiet-text">当前工作台未返回需要重点处置的风险记录。</text></view>

          <view class="section-head"><view><text class="section-head__title">最近学生动态</text><text class="wb__section-sub">用于了解近期提交、审批和状态变化</text></view></view>
          <view class="card stack-sm wb__recent" v-if="wb.recent && wb.recent.length">
            <view v-for="a in wb.recent" :key="a.id" class="wb__act">
              <text class="wb__act-dot" />
              <text class="wb__act-text flex-1"><text class="wb__act-name">{{ a.name }}</text> {{ a.text }}</text>
              <text class="wb__act-time">{{ fromNow(a.time) }}</text>
            </view>
          </view>
          <view v-else class="card wb__quiet"><text class="wb__quiet-title">暂无最新动态</text><text class="wb__quiet-text">学生有新的提交或业务状态变化后会显示在这里。</text></view>
        </view>
      </view>
    </MobileGlobalState>

    <MobileTabBar side="teacher" active="workbench" :badges="{ todo: todoBadge }" />
  </view>
</template>

<script>
import { tenantBrandConfig } from '@/config'
import { useSessionStore } from '@/stores/session'
import { useInternshipContextStore } from '@/stores/internshipContext'
import { teacherApi } from '@/services/teacherApi'
import { getTeacherWorkbenchVersion } from '@/utils/viewFreshness'
import { deadlineText, isOverdue, fromNow } from '@/utils/format'
import { go, toast } from '@/utils/nav'

const WORKBENCH_TTL_MS = 20_000
const GRAD_CLASSES = ['g1', 'g4', 'g3', 'g5', 'g2', 'g7', 'g6', 'g8']
const INTERNSHIP_PERMISSIONS = {
  weekly: 'internship.report.review',
  checkin: 'internship.attendance.review',
  makeup: 'internship.makeup.review',
  leave: 'internship.leave.review',
  guidance: 'internship.guidance.manage',
  'stu-eval': 'internship.eval.self.view',
  'ent-eval': 'internship.eval.enterprise.view',
  insurance: 'internship.insurance.view',
  'internship-change': 'internship.change.view',
  'internship-score': 'internship.score.view',
  'agreement-confirm': 'internship.agreement.view',
  'process-report': 'internship.report.view',
  'plan-task': 'internship.task.view',
  'internship-application': 'internship.application.view',
  'internship-risk': 'internship.risk.view'
}

export default {
  data() {
    return {
      brand: tenantBrandConfig, wb: null, state: 'loading', user: {}, roleConfig: {},
      statusBarHeight: 20, internshipContextReady: false, internshipContextError: '',
      lastLoadedAt: 0, loadedContextKey: '', loadedFreshnessVersion: -1
    }
  },
  computed: {
    todoBadge() {
      if (!this.wb) return 0
      const m = this.wb.metrics.find((x) => ['todo', 'weekly', 'review', 'warning'].includes(x.key))
      return m ? Number(m.value) || 0 : 0
    },
    visibleQuickActions() {
      const actions = this.roleConfig.quickActions || []
      const session = useSessionStore()
      if (session.currentRole !== 'intern_mentor') return actions
      if (!this.internshipContextReady) return []
      const context = useInternshipContextStore()
      return actions.filter((q) => {
        const permission = INTERNSHIP_PERMISSIONS[q.key]
        if (!permission) return false
        return context.can(permission)
      })
    },
    selectedInternshipBatch() {
      const session = useSessionStore()
      if (session.currentRole !== 'intern_mentor') return null
      return useInternshipContextStore().selectedBatch
    },
    dueSoonCount() { return Array.isArray(this.wb?.dueSoon) ? this.wb.dueSoon.length : 0 },
    riskCount() { return Array.isArray(this.wb?.riskStudents) ? this.wb.riskStudents.length : 0 },
    workbenchConclusion() {
      if (this.riskCount > 0) return `有 ${this.riskCount} 名风险学生需要关注`
      if (this.dueSoonCount > 0) return `有 ${this.dueSoonCount} 项待办即将超时`
      return '当前没有紧急风险或临近超时事项'
    },
    nextActionText() {
      if (this.riskCount > 0) return '先进入风险台账，查看高风险学生和未闭环事项。'
      if (this.dueSoonCount > 0) return '先处理临近截止的审批与批阅任务。'
      if (this.visibleQuickActions.length > 0) return '按日常工作需要进入快捷操作，或查看最近学生动态。'
      return '当前身份暂无可执行入口，可查看待办和学生动态。'
    }
  },
  onLoad() {
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
  methods: {
    go, deadlineText, isOverdue, fromNow,
    gradClass(i) { return GRAD_CLASSES[i % GRAD_CLASSES.length] },
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
    quick(q) {
      const session = useSessionStore()
      const map = {
        weekly: '/pages/teacher/internship-review/index',
        'review-open': '/pages/teacher/graduation-guide/index?tab=review&kind=proposal',
        'review-mid': '/pages/teacher/graduation-guide/index?tab=midterm',
        'review-result': '/pages/teacher/graduation-guide/index?tab=review&kind=final',
        checkin: '/pages/teacher/internship-review/index',
        makeup: '/pages/teacher/internship-approval/index',
        leave: '/pages/teacher/internship-approval/index?tab=leave',
        guidance: '/pages/teacher/internship-guidance/index',
        'stu-eval': '/pages/teacher/student-eval/index',
        'ent-eval': '/pages/teacher/enterprise-eval/index',
        insurance: '/pages/teacher/insurance-verify/index',
        'internship-change': '/pages/teacher/internship-change/index',
        'internship-score': '/pages/teacher/internship-score/index',
        'agreement-confirm': '/pages/teacher/agreement-confirm/index',
        'process-report': '/pages/teacher/process-report-review/index',
        'plan-task': '/pages/teacher/plan-task-review/index',
        'internship-application': '/pages/teacher/internship-application/index',
        'internship-risk': '/pages/teacher/internship-risk/index',
        approval: '/pages/teacher/approval/index',
        risk: '/pages/teacher/affairs-review/index?type=RISK_HANDLE',
        follow: '/pages/teacher/employment-follow/index',
        unemployed: '/pages/teacher/employment-follow/index',
        employmentTransfer: '/pages/teacher/employment-transfer/index',
        employmentCompany: '/pages/teacher/employment-company/index',
        warning: '/pages/teacher/academic-warning/index',
        progress: '/pages/teacher/academic-affairs/index',
        status: '/pages/teacher/exam-defer/index',
        'topic-review': '/pages/teacher/graduation-topics/index',
        taskbook: '/pages/teacher/graduation-taskbook/index',
        'guide-log': '/pages/teacher/graduation-guide/index',
        'affairs-stats': '/pages/teacher/affairs/stats/index',
        'campus-service': '/pages/teacher/campus-service/index',
        myClasses: '/pages/teacher/my-classes/index',
        myStudents: '/pages/teacher/my-students/index',
        talk: '/pages/teacher/affairs/talk/index',
        mental: '/pages/teacher/affairs/mental/index',
        affairs: '/pages/teacher/affairs/index',
        familyContact: '/pages/teacher/family-contact/index',
        affairsLeave: '/pages/teacher/affairs-leave/index',
        dormReview: '/pages/teacher/dorm-review/index',
        classCadre: '/pages/teacher/class-cadre/index',
        classMaterial: '/pages/teacher/class-material/index',
        academicTask: '/pages/teacher/academic-task/index',
        scheduleChange: '/pages/teacher/schedule-change/index',
        examDefer: '/pages/teacher/exam-defer/index',
        evaluation: '/pages/teacher/evaluation/index',
        defenseScore: '/pages/teacher/defense-score/index',
        notifyPublish: '/pages/teacher/notify-publish/index',
        overview: '/pages/teacher/dashboard/index',
        orientationVerify: '/pages/teacher/orientation/verify/index',
        orientationDashboard: '/pages/teacher/orientation/dashboard/index'
      }
      if (q.key === 'risk' && session.currentRole === 'intern_mentor') return go('/pages/teacher/internship-risk/index')
      if (map[q.key]) return go(map[q.key])
      toast('当前入口尚未配置，请联系管理员')
    },
    goRiskList() {
      const session = useSessionStore()
      go(session.currentRole === 'intern_mentor'
        ? '/pages/teacher/internship-risk/index'
        : '/pages/teacher/affairs-review/index?type=RISK_HANDLE')
    },
    handleTodo(t) { go('/pages/teacher/todos/index') },
    handleRisk(r) {
      const session = useSessionStore()
      if (session.currentRole === 'intern_mentor') return go('/pages/teacher/internship-risk/index')
      if (r && r.actionType === 'RISK_HANDLE') return go('/pages/teacher/affairs-review/index?type=RISK_HANDLE')
      go('/pages/teacher/risk-students/index')
    },
    openStudent(r) { go('/pages/teacher/student-detail/index?id=' + r.id) }
  }
}
</script>

<style scoped>
.wb__hero{padding-bottom:var(--space-4)}.wb__greet{position:relative;display:flex;align-items:center;gap:var(--space-3);margin-top:var(--space-3)}.wb__greet-name{display:block;color:#fff;font-size:var(--font-size-lg);font-weight:var(--font-weight-semibold)}.wb__greet-sub{display:block;color:rgba(255,255,255,.85);font-size:var(--font-size-xs);margin-top:3px}.wb__bell{width:38px;height:38px;border-radius:var(--radius-full);background:rgba(255,255,255,.14);display:flex;align-items:center;justify-content:center;flex-shrink:0}.wb__bell-icon{color:#fff;font-size:18px}.wb__rolepill{position:relative;display:inline-flex;align-items:center;gap:6px;margin-top:var(--space-3);background:rgba(255,255,255,.16);border:1px solid rgba(255,255,255,.3);color:#fff;font-size:var(--font-size-xs);padding:6px 11px;border-radius:var(--radius-full)}.wb__rolepill-dot{width:6px;height:6px;border-radius:var(--radius-full);background:#3ddc84}.wb__rolepill-chev{font-size:10px}.wb__content{display:flex;flex-direction:column;gap:var(--space-3);padding-bottom:calc(var(--safe-bottom) + 82px)}.wb__batch{display:flex;align-items:center;justify-content:space-between;gap:var(--space-3);padding:var(--space-3);margin-top:var(--space-3);background:var(--teacher-50,#eff6ff);border-color:var(--teacher-200,#bfdbfe)}.wb__batch-copy{min-width:0;display:flex;flex-direction:column;gap:3px}.wb__batch-label{font-size:var(--font-size-xs);color:var(--text-tertiary)}.wb__batch-name{font-size:var(--font-size-base);color:var(--text-primary);font-weight:var(--font-weight-semibold);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.wb__batch-meta{font-size:var(--font-size-xs);color:var(--text-secondary)}.wb__batch-status{flex-shrink:0;padding:5px 9px;border-radius:var(--radius-full);background:var(--bg-card);color:var(--teacher-700);font-size:var(--font-size-xs);font-weight:600}.wb__brief{padding:var(--space-3);display:flex;flex-direction:column;gap:var(--space-3)}.wb__brief-head{display:flex;align-items:flex-start;justify-content:space-between;gap:var(--space-3)}.wb__brief-eyebrow{display:block;font-size:var(--font-size-xs);color:var(--text-tertiary)}.wb__brief-title{display:block;margin-top:4px;font-size:var(--font-size-md);font-weight:700;color:var(--text-primary);line-height:1.45}.wb__brief-time{flex-shrink:0;font-size:10px;color:var(--text-tertiary)}.wb__brief-metrics{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));background:var(--gray-50);border-radius:var(--radius-md);overflow:hidden}.wb__brief-metric{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:4px;padding:11px 4px;border-left:1px solid var(--border-light)}.wb__brief-metric:first-child{border-left:0}.wb__brief-metric text:first-child{font-size:var(--font-size-xl);font-weight:700;color:var(--teacher-700)}.wb__brief-metric.is-warning text:first-child{color:var(--warning-700)}.wb__brief-metric.is-danger text:first-child{color:var(--danger-600)}.wb__brief-metric text:last-child{font-size:10px;color:var(--text-tertiary)}.wb__brief-next{display:flex;gap:10px;padding:10px 12px;border-radius:var(--radius-md);background:var(--teacher-50,#eff6ff)}.wb__brief-next-label{flex-shrink:0;font-size:var(--font-size-xs);font-weight:600;color:var(--text-secondary)}.wb__brief-next-text{font-size:var(--font-size-xs);line-height:1.5;color:var(--text-secondary)}.wb__section-hint{font-size:var(--font-size-xs);color:var(--text-tertiary)}.wb__section-sub{display:block;margin-top:2px;font-size:10px;color:var(--text-tertiary)}.wb__quick-card{padding:var(--space-3)}.wb__risk{display:flex;align-items:center;gap:var(--space-3);padding:var(--space-3)}.wb__risk-avatar{width:40px;height:40px;border-radius:var(--radius-full);background:var(--danger-50);color:var(--danger-600);display:flex;align-items:center;justify-content:center;font-weight:600}.wb__risk-copy{min-width:0}.wb__risk-type{display:block;font-size:var(--font-size-sm);color:var(--text-secondary);margin-top:2px;word-break:break-word}.wb__risk-btn{font-size:var(--font-size-sm);color:#fff;background:var(--danger-500);border-radius:var(--radius-md);padding:7px 14px;flex-shrink:0}.wb__recent{padding:var(--space-3)}.wb__act{display:flex;align-items:flex-start;gap:var(--space-2);padding:4px 0}.wb__act-dot{width:6px;height:6px;border-radius:var(--radius-full);background:var(--teacher-500);flex-shrink:0;margin-top:7px}.wb__act-text{font-size:var(--font-size-sm);color:var(--text-secondary);line-height:1.5;word-break:break-word}.wb__act-name{color:var(--text-primary);font-weight:var(--font-weight-medium)}.wb__act-time{font-size:var(--font-size-xs);color:var(--text-tertiary);flex-shrink:0;padding-top:2px}.wb__quiet{padding:var(--space-3);background:var(--gray-50)}.wb__quiet-title{display:block;font-size:var(--font-size-sm);font-weight:600;color:var(--text-primary)}.wb__quiet-text{display:block;margin-top:4px;font-size:var(--font-size-xs);line-height:1.5;color:var(--text-tertiary)}@media(max-width:360px){.wb__brief-metrics{grid-template-columns:1fr}.wb__brief-metric{border-left:0;border-top:1px solid var(--border-light)}.wb__brief-metric:first-child{border-top:0}.wb__batch{align-items:flex-start}.wb__act{flex-wrap:wrap}.wb__act-time{margin-left:14px}}
</style>
