<template>
  <view class="page-wrap">
    <MobileGlobalState :state="state" @retry="retryLoad">
      <view class="home__hero hero-band is-brand">
        <view class="hero-band__orb" />
        <view class="mnav__status" :style="{ height: statusBarHeight + 'px' }" />
        <view class="home__greet">
          <view class="avatar-badge">{{ (user.name || '同').slice(0,1) }}</view>
          <view class="flex-1">
            <text class="home__greet-name">{{ greeting }}，{{ user.name || '同学' }}<text v-if="isOrientationGuide" class="home__newtag">新生</text></text>
            <text class="home__greet-sub">
              <template v-if="isOrientationGuide">{{ user.className || '2026级新生' }} · 尚未完成报到</template>
              <template v-else>{{ user.className || '在校学生' }}{{ user.studentNo ? ' · 学号 ' + user.studentNo : '' }}</template>
            </text>
          </view>
          <view class="home__bell" @click="go('/pages/student/messages/index')">
            <text class="home__bell-icon">✉</text>
            <text v-if="home && home.metrics.unread" class="home__bell-badge">{{ home.metrics.unread }}</text>
          </view>
        </view>
        <view class="stat-strip" v-if="home && !isOrientationGuide">
          <view class="stat-strip__item"><text class="stat-strip__val">{{ progressText }}</text><text class="stat-strip__label">阶段进度</text></view>
          <view class="stat-strip__item"><text class="stat-strip__val">{{ home.metrics.todoCount }}</text><text class="stat-strip__label">待办事项</text></view>
          <view class="stat-strip__item"><text class="stat-strip__val">{{ creditRateText }}</text><text class="stat-strip__label">学分完成率</text></view>
        </view>
      </view>

      <!-- 未报到新生：首屏整块为迎新引导卡，其余功能收起 -->
      <view class="page-pad stack" v-if="isOrientationGuide">
        <view class="home__guide">
          <view class="home__guide-hd">
            <view class="home__guide-ring" :style="ringStyle">
              <view class="home__guide-ring-in">
                <text class="home__guide-ring-num">{{ orientationDoneCount }}/{{ orientationSteps.length }}</text>
                <text class="home__guide-ring-lb">已完成</text>
              </view>
            </view>
            <view class="flex-1">
              <text class="home__guide-title">欢迎加入！先完成入学报到</text>
              <text v-if="orientationBatch.open" class="home__guide-count">距报到截止还有 {{ orientationBatch.daysLeft }} 天</text>
            </view>
          </view>
          <button class="home__guide-btn" @click="go(orientationNextRoute)">继续报到 · {{ orientationNextLabel }} ›</button>
          <view class="home__guide-steps">
            <view v-for="s in orientationSteps" :key="s.key" class="home__guide-step" :class="s.state">
              <view class="home__guide-step-dot">
                <text v-if="s.state === 'done'">✓</text>
              </view>
              <text class="home__guide-step-name">{{ s.label }}</text>
              <text class="home__guide-step-st">{{ s.stateLabel }}</text>
            </view>
          </view>
        </view>
        <view class="home__locked">
          <text class="home__locked-icon">🔒</text>
          <text class="home__locked-tx">完成报到后，课表、成绩、校园服务等{{ '\n' }}功能将自动解锁</text>
        </view>
      </view>

      <view class="page-pad stack" v-else-if="home">
        <!-- 阶段主卡 -->
        <view class="home__stage card">
          <view class="row-between">
            <text class="home__stage-title">{{ home.stageCard.title }}</text>
            <MobileStatusTag :label="home.stageCard.stageText" type="processing" />
          </view>
          <text class="home__stage-sub">{{ home.stageCard.subtitle }}</text>
          <view class="home__stage-prog">
            <MobileProgress :value="home.stageCard.progress" tone="brand" />
          </view>
        </view>

        <!-- 下一步行动 -->
        <view class="section-head"><text class="section-head__title">下一步该做什么</text></view>
        <MobileActionCard
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

        <!-- 当前阻断 -->
        <template v-if="home.blockers.length">
          <MobileInlineAlert
            v-for="b in home.blockers"
            :key="b.id"
            type="warning"
            :title="b.title"
            :description="b.reason"
          >
            <template #actions>
              <text class="home__alert-btn" @click="go('/pages/student/my-applications/index')">{{ b.solveText }}</text>
            </template>
          </MobileInlineAlert>
        </template>

        <!-- 常用服务 -->
        <view class="card">
          <view class="row-between" style="margin-bottom: var(--space-2);"><text class="card-title">常用服务</text></view>
          <view v-if="home.quickServices.length" class="icon-grid">
            <view
              v-for="(q, i) in home.quickServices"
              :key="q.key"
              class="icon-grid__item"
              @click="go(q.route)"
            >
              <view class="icon-grid__badge" :class="gradClass(i)">{{ q.icon }}</view>
              <text class="icon-grid__label">{{ q.label }}</text>
            </view>
          </view>
          <MobileGlobalState v-else state="empty" title="暂无常用服务"
            description="学校启用可办理服务后会显示在这里。" />
        </view>

        <!-- 今日课程 -->
        <view class="section-head">
          <text class="section-head__title">今日课程</text>
          <text class="section-head__more" @click="go('/pages/student/academic-affairs/index')">学业进度 ›</text>
        </view>
        <view class="card stack-sm">
          <view v-for="c in home.todayCourses" :key="c.id" class="home__course">
            <view class="home__course-time" :class="{ 'is-now': c.status === 'current' }">
              <text>{{ c.time.split('-')[0] }}</text>
              <text class="home__course-dur">{{ c.time.split('-')[1] }}</text>
            </view>
            <view class="home__course-line" :class="{ 'is-now': c.status === 'current' }" />
            <view class="flex-1">
              <text class="home__course-name">{{ c.name }}</text>
              <text class="home__course-place">{{ c.place }}</text>
            </view>
            <text v-if="c.status === 'current'" class="home__course-tag">进行中</text>
          </view>
          <MobileGlobalState v-if="!home.todayCourses.length" state="empty" title="暂无今日课程"
            description="当前没有从教务系统获取到今日课程。" />
        </view>

        <!-- 待办 -->
        <view class="section-head">
          <text class="section-head__title">我的待办</text>
          <text class="section-head__more" @click="go('/pages/student/messages/index')">全部 ›</text>
        </view>
        <view class="stack-sm">
          <MobileTodoCard
            v-for="t in home.todos"
            :key="t.id"
            :title="t.title"
            :source-module="t.module"
            :deadline="fmtDeadline(t.deadline)"
            :status="t.status"
            action-text="去办理"
            @handle="go('/pages/student/campus-service/index')"
          />
          <MobileGlobalState v-if="!home.todos.length" state="empty" title="暂无待办"
            description="当前没有需要你处理的事项。" />
        </view>

        <!-- 通知 -->
        <view class="section-head"><text class="section-head__title">校园通知</text></view>
        <view class="card stack-sm">
          <view v-for="n in home.notices" :key="n.id" class="home__notice">
            <text v-if="n.important" class="home__notice-tag">重要</text>
            <text class="home__notice-title ellipsis flex-1">{{ n.title }}</text>
            <text class="home__notice-src">{{ n.source }}</text>
          </view>
          <MobileGlobalState v-if="!home.notices.length" state="empty" title="暂无校园通知"
            description="学校发布与你相关的通知后会显示在这里。" />
        </view>
      </view>
    </MobileGlobalState>

    <MobileTabBar side="student" active="home" :badges="{ message: home ? home.metrics.unread : 0 }" />

    <view v-if="emg" class="emg-banner" @click="goMessages">
      <text class="emg-banner__tag">紧急</text>
      <text class="emg-banner__tx ellipsis">{{ emg.title }}</text>
      <text class="emg-banner__go">去确认 ›</text>
    </view>
  </view>
</template>

<script>
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
</script>

<style scoped>
.home__hero { padding-bottom: var(--space-6); }
.mnav__status { width: 100%; }
.home__greet { position: relative; display: flex; align-items: center; gap: var(--space-3); margin-top: var(--space-3); }
.home__greet-name { display: block; color: #fff; font-size: var(--font-size-lg); font-weight: var(--font-weight-semibold); }
.home__greet-sub { display: block; color: rgba(255,255,255,0.85); font-size: var(--font-size-xs); margin-top: 3px; }
.home__bell { position: relative; width: 38px; height: 38px; border-radius: var(--radius-full); background: rgba(255,255,255,.14); display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.home__bell-icon { color: #fff; font-size: 18px; }
.home__bell-badge {
  position: absolute; top: -4px; right: -4px; min-width: 15px; height: 15px; padding: 0 3px;
  background: var(--danger-500); color: #fff; font-size: 10px; line-height: 15px; text-align: center; border-radius: var(--radius-full);
}
.home__newtag { font-size: 10px; font-weight: var(--font-weight-semibold); color: var(--orientation-700); background: #fff; padding: 2px 7px; border-radius: var(--radius-base); margin-left: 6px; vertical-align: middle; }
.home__stage { margin-top: calc(-1 * var(--space-6) - 6px); box-shadow: var(--shadow-float); }
.home__guide {
  position: relative; margin-top: calc(-1 * var(--space-6) - 6px); background: var(--bg-card);
  border-radius: var(--radius-lg); padding: var(--card-padding-mobile); box-shadow: var(--shadow-float);
  border: 1px solid #ffe6cc;
}
.home__guide-hd { display: flex; align-items: center; gap: var(--space-4); }
.home__guide-ring { width: 66px; height: 66px; border-radius: var(--radius-full); display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.home__guide-ring-in { width: 52px; height: 52px; border-radius: var(--radius-full); background: var(--bg-card); display: flex; flex-direction: column; align-items: center; justify-content: center; }
.home__guide-ring-num { font-size: var(--font-size-md); color: var(--orientation-700); font-weight: var(--font-weight-semibold); line-height: 1; }
.home__guide-ring-lb { font-size: 9px; color: var(--text-tertiary); margin-top: 2px; }
.home__guide-title { display: block; font-size: var(--font-size-md); color: var(--text-primary); font-weight: var(--font-weight-semibold); }
.home__guide-count { display: block; margin-top: var(--space-2); font-size: var(--font-size-sm); color: var(--orientation-700); font-weight: var(--font-weight-medium); }
.home__guide-btn {
  width: 100%; margin-top: var(--space-4); height: 44px; border-radius: var(--radius-md); border: none;
  background: var(--orientation-gradient); color: #fff; font-size: var(--font-size-md); font-weight: var(--font-weight-semibold);
  box-shadow: 0 8px 18px -8px rgba(245,122,30,.6);
}
.home__guide-steps { margin-top: var(--space-4); border-top: 1px solid #f4ede2; padding-top: var(--space-3); }
.home__guide-step { display: flex; align-items: center; gap: var(--space-2); padding: 6px 0; }
.home__guide-step-dot { width: 18px; height: 18px; border-radius: var(--radius-full); flex-shrink: 0; display: flex; align-items: center; justify-content: center; background: var(--gray-100); color: var(--text-tertiary); font-size: 10px; }
.home__guide-step.done .home__guide-step-dot { background: var(--success-500); color: #fff; }
.home__guide-step.now .home__guide-step-dot { background: var(--orientation-700); }
.home__guide-step-name { font-size: var(--font-size-sm); color: var(--text-secondary); }
.home__guide-step.wait .home__guide-step-name { color: var(--text-disabled); }
.home__guide-step-st { margin-left: auto; font-size: var(--font-size-xs); font-weight: var(--font-weight-medium); color: var(--text-tertiary); }
.home__guide-step.done .home__guide-step-st { color: var(--success-600); }
.home__guide-step.now .home__guide-step-st { color: var(--orientation-700); }
.home__locked { margin-top: var(--card-gap-mobile); background: var(--bg-card); border-radius: var(--radius-lg); padding: var(--space-6) var(--space-4); box-shadow: var(--shadow-card); text-align: center; }
.home__locked-icon { display: block; font-size: 28px; }
.home__locked-tx { display: block; margin-top: var(--space-2); font-size: var(--font-size-sm); color: var(--text-tertiary); line-height: 1.6; white-space: pre-line; }
.home__stage-title { font-size: var(--font-size-lg); font-weight: var(--font-weight-semibold); color: var(--text-primary); }
.home__stage-sub { display: block; font-size: var(--font-size-sm); color: var(--text-secondary); margin: var(--space-2) 0 var(--space-3); }
.home__alert-btn { font-size: var(--font-size-sm); color: var(--warning-700); font-weight: var(--font-weight-medium); }
.home__course { display: flex; align-items: stretch; gap: var(--space-3); }
.home__course-time { width: 52px; display: flex; flex-direction: column; color: var(--text-secondary); font-size: var(--font-size-sm); }
.home__course-time.is-now { color: var(--brand-primary); font-weight: var(--font-weight-semibold); }
.home__course-dur { font-size: 11px; color: var(--text-tertiary); }
.home__course-line { width: 3px; border-radius: 3px; background: var(--border-base); }
.home__course-line.is-now { background: var(--brand-primary); }
.home__course-name { font-size: var(--font-size-md); color: var(--text-primary); }
.home__course-place { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }
.home__course-tag { align-self: center; font-size: var(--font-size-xs); color: var(--brand-primary); background: var(--primary-50); padding: 2px 8px; border-radius: var(--radius-full); }
.home__notice { display: flex; align-items: center; gap: var(--space-2); }
.home__notice-tag { font-size: 10px; color: #fff; background: var(--danger-500); padding: 1px 5px; border-radius: var(--radius-sm); flex-shrink: 0; }
.home__notice-title { font-size: var(--font-size-base); color: var(--text-primary); }
.home__notice-src { font-size: var(--font-size-xs); color: var(--text-tertiary); flex-shrink: 0; }
.emg-banner {
  position: fixed; left: 12px; right: 12px; bottom: calc(56px + env(safe-area-inset-bottom));
  z-index: 50; display: flex; align-items: center; gap: 8px;
  background: #7f1d1d; color: #fff; border-radius: 10px; padding: 10px 12px;
  box-shadow: 0 8px 24px rgba(127, 29, 29, 0.35);
}
.emg-banner__tag {
  font-size: 10px; font-weight: 600; background: #fff; color: #7f1d1d;
  padding: 2px 6px; border-radius: 4px; flex-shrink: 0;
}
.emg-banner__tx { flex: 1; font-size: 13px; }
.emg-banner__go { font-size: 12px; opacity: 0.9; flex-shrink: 0; }
</style>
