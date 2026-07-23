<template>
  <view class="page-wrap">
    <MobileGlobalState :state="state" @retry="load">
      <view class="wb__hero hero-band is-teacher">
        <view class="hero-band__orb" />
        <view class="mnav__status" :style="{ height: statusBarHeight + 'px' }" />
        <view class="wb__greet">
          <view class="avatar-badge">{{ (user.name||'师').slice(0,1) }}</view>
          <view class="flex-1">
            <text class="wb__greet-name">{{ user.name }}</text>
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
        <view class="page-pad" style="padding-top:0;">
          <!-- 快捷操作（按身份） -->
          <view class="section-head"><text class="section-head__title">快捷操作</text></view>
          <view class="card">
            <view class="icon-grid">
              <view v-for="(q, i) in roleConfig.quickActions" :key="q.key" class="icon-grid__item" @click="quick(q)">
                <view class="icon-grid__badge" :class="gradClass(i)">{{ q.icon }}</view>
                <text class="icon-grid__label">{{ q.label }}</text>
              </view>
            </view>
          </view>

          <!-- 即将超时 -->
          <view class="section-head">
            <text class="section-head__title">即将超时</text>
            <text class="section-head__more" @click="go('/pages/teacher/todos/index')">全部待办 ›</text>
          </view>
          <view class="stack-sm">
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

          <!-- 风险学生 -->
          <view class="section-head">
            <text class="section-head__title">风险学生</text>
            <text class="section-head__more" @click="go('/pages/teacher/affairs-review/index?type=RISK_HANDLE')">学工风险 ›</text>
          </view>
          <view class="stack-sm">
            <view v-for="r in wb.riskStudents" :key="r.id" class="wb__risk card" @click="openStudent(r)">
              <view class="wb__risk-avatar">{{ r.name.slice(0,1) }}</view>
              <view class="flex-1">
                <view class="row" style="gap:6px;">
                  <text class="t-md t-bold">{{ r.name }}</text>
                  <MobileRiskTag :level="r.level" />
                </view>
                <text class="wb__risk-type">{{ r.className }} · {{ r.type }}</text>
              </view>
              <text class="wb__risk-btn" @click.stop="handleRisk(r)">处理</text>
            </view>
          </view>

          <!-- 最近学生动态 -->
          <view class="section-head"><text class="section-head__title">最近学生动态</text></view>
          <view class="card stack-sm">
            <view v-for="a in wb.recent" :key="a.id" class="wb__act">
              <text class="wb__act-dot" />
              <text class="wb__act-text flex-1"><text class="wb__act-name">{{ a.name }}</text> {{ a.text }}</text>
              <text class="wb__act-time">{{ fromNow(a.time) }}</text>
            </view>
          </view>
        </view>
      </view>
    </MobileGlobalState>

    <MobileTabBar side="teacher" active="workbench" :badges="{ todo: todoBadge }" />
  </view>
</template>

<script>
import { tenantBrandConfig } from '@/config'
import { useSessionStore } from '@/stores/session'
import { teacherApi } from '@/services/teacherApi'
import { deadlineText, isOverdue, fromNow } from '@/utils/format'
import { go, toast } from '@/utils/nav'

const GRAD_CLASSES = ['g1', 'g4', 'g3', 'g5', 'g2', 'g7', 'g6', 'g8']

export default {
  data() { return { brand: tenantBrandConfig, wb: null, state: 'loading', user: {}, roleConfig: {}, statusBarHeight: 20 } },
  computed: {
    todoBadge() {
      if (!this.wb) return 0
      const m = this.wb.metrics.find((x) => ['todo', 'weekly', 'review', 'warning'].includes(x.key))
      return m ? Number(m.value) || 0 : 0
    }
  },
  onLoad() {
    try { this.statusBarHeight = uni.getSystemInfoSync().statusBarHeight || 20 } catch (e) {}
  },
  onShow() { this.load() },
  onPullDownRefresh() { this.load(() => uni.stopPullDownRefresh()) },
  methods: {
    go, deadlineText, isOverdue, fromNow,
    gradClass(i) { return GRAD_CLASSES[i % GRAD_CLASSES.length] },
    load(done) {
      const session = useSessionStore()
      this.user = session.mockUser || {}
      this.roleConfig = session.roleConfig
      this.state = 'loading'
      teacherApi.getWorkbench(session.currentRole).then((d) => {
        this.wb = d; this.state = 'ready'; done && done()
      }).catch(() => { this.state = 'error'; done && done() })
    },
    quick(q) {
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
      if (map[q.key]) return go(map[q.key])
      toast(q.label + '：即将开放')
    },
    handleTodo(t) { go('/pages/teacher/todos/index') },
    handleRisk(r) { go('/pages/teacher/affairs-review/index?type=RISK_HANDLE') },
    openStudent(r) { go('/pages/teacher/student-detail/index?id=' + r.id) }
  }
}
</script>

<style scoped>
.wb__hero { padding-bottom: var(--space-4); }
.wb__greet { position: relative; display: flex; align-items: center; gap: var(--space-3); margin-top: var(--space-3); }
.wb__greet-name { display: block; color: #fff; font-size: var(--font-size-lg); font-weight: var(--font-weight-semibold); }
.wb__greet-sub { display: block; color: rgba(255,255,255,0.85); font-size: var(--font-size-xs); margin-top: 3px; }
.wb__bell { width: 38px; height: 38px; border-radius: var(--radius-full); background: rgba(255,255,255,.14); display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.wb__bell-icon { color: #fff; font-size: 18px; }
.wb__rolepill {
  position: relative; display: inline-flex; align-items: center; gap: 6px; margin-top: var(--space-3);
  background: rgba(255,255,255,.16); border: 1px solid rgba(255,255,255,.3); color: #fff;
  font-size: var(--font-size-xs); padding: 6px 11px; border-radius: var(--radius-full);
}
.wb__rolepill-dot { width: 6px; height: 6px; border-radius: var(--radius-full); background: #3ddc84; }
.wb__rolepill-chev { font-size: 10px; }
.wb__risk { display: flex; align-items: center; gap: var(--space-3); }
.wb__risk-avatar { width: 40px; height: 40px; border-radius: var(--radius-full); background: var(--danger-50); color: var(--danger-600); display: flex; align-items: center; justify-content: center; }
.wb__risk-type { display: block; font-size: var(--font-size-sm); color: var(--text-secondary); margin-top: 2px; }
.wb__risk-btn { font-size: var(--font-size-sm); color: #fff; background: var(--danger-500); border-radius: var(--radius-md); padding: 6px 14px; }
.wb__act { display: flex; align-items: center; gap: var(--space-2); }
.wb__act-dot { width: 6px; height: 6px; border-radius: var(--radius-full); background: var(--teacher-500); flex-shrink: 0; }
.wb__act-text { font-size: var(--font-size-sm); color: var(--text-secondary); }
.wb__act-name { color: var(--text-primary); font-weight: var(--font-weight-medium); }
.wb__act-time { font-size: var(--font-size-xs); color: var(--text-tertiary); flex-shrink: 0; }
</style>
