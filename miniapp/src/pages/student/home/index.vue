<template>
  <view class="student-shell">
    <MobileStudentHero :title="(user.name || '同学') + '，你好'" :subtitle="todayText + (home?.stageCard?.stageText ? ' ｜ ' + home.stageCard.stageText : '')" />
    <MobileGlobalState :state="state" @retry="retryLoad">
      <view class="shell-pad home__body" v-if="home">
        <!-- 待我处理：只显示服务器下发的当前动作，不生成业务状态。 -->
        <view v-if="home.nextAction" class="home__priority" @click="runAction(home.nextAction)">
          <MobileShellIcon name="alert-circle" tone="amber" :size="27" round />
          <view class="shell-row__body"><text class="shell-row__title">{{ nextActionTitle }}</text><text class="shell-muted">{{ nextActionDesc }}</text></view>
          <button class="home__priority-button" @click.stop="runAction(home.nextAction)">{{ nextActionText }}</button>
        </view>
        <view v-else-if="!isOrientationGuide" class="home__allclear">
          <MobileShellIcon name="clipboard-check" tone="teal" :size="24" />
          <view><text class="shell-row__title">当前暂无待办</text><text class="shell-muted">有新的办理事项会及时提醒你</text></view>
        </view>
        <view v-if="isOrientationGuide" class="shell-panel home__orientation">
          <view class="shell-row">
            <MobileShellIcon name="school" :size="28" round />
            <view class="shell-row__body"><text class="shell-row__title">欢迎加入！先完成入学报到</text><text class="shell-muted">已完成 {{ orientationDoneCount }}/{{ orientationSteps.length }} 项</text></view>
          </view>
          <button class="home__orientation-button" @click="go(orientationNextRoute)">继续报到 · {{ orientationNextLabel }}</button>
          <text v-if="orientationBatch.open" class="home__deadline">距报到截止还有 {{ orientationBatch.daysLeft }} 天</text>
          <view class="home__orientation-links"><text class="shell-link" @click="go('/pages/student/academic-affairs/schedule')">查看课表</text><text class="shell-link" @click="go('/pages/student/academic-affairs/selection')">网上选课</text></view>
          <view class="home__orientation-steps">
            <view v-for="s in orientationSteps" :key="s.key" class="home__orientation-step">
              <MobileShellIcon :name="s.state === 'done' ? 'check' : 'clock'" :tone="s.state === 'done' ? 'teal' : s.state === 'now' ? 'amber' : 'gray'" :size="17" />
              <text>{{ s.label }}</text><text class="shell-muted">{{ s.stateLabel }}</text>
            </view>
          </view>
        </view>
        <!-- 当前阻断 -->
        <template v-if="home.blockers.length">
          <MobileInlineAlert v-for="b in home.blockers" :key="b.id" type="warning" :title="b.title" :description="b.reason">
            <template #actions>
              <text v-if="canRun(b.action)" class="home__alert-btn" @click="runAction(b.action)">去处理</text>
              <text v-else class="home__alert-note">{{ disabledReason(b.action) }}</text>
            </template>
          </MobileInlineAlert>
        </template>

        <!-- 今日安排 / 7 天安排均消费原有 Agenda 投影。 -->
        <view class="shell-panel">
          <view class="shell-heading"><text class="shell-title">我的今天</text><view class="shell-link" @click="go('/pages/student/academic-affairs/schedule')">查看课表<MobileShellIcon name="chevron-right" :size="18" /></view></view>
          <text class="shell-muted home__today-date">{{ todayText }}</text>
          <view v-for="c in home.today" :key="c.eventId" class="home__course" @click="runAction(c.action)">
            <view class="home__course-time"><text>{{ clockOf(c.startAt) || '待定' }}</text><text class="home__course-dur">{{ clockOf(c.endAt) }}</text></view>
            <view class="home__course-line" />
            <view class="shell-row__body"><text class="shell-row__title">{{ c.title }}</text><view class="home__place"><MobileShellIcon :name="c.kind === 'COURSE' ? 'map-pin' : 'file-text'" tone="gray" :size="17" /><text>{{ [kindText(c.kind), c.location].filter(Boolean).join(' · ') }}</text></view></view>
            <text v-if="c.status === 'ONGOING'" class="home__course-tag">进行中</text>
          </view>
          <view v-if="!home.today.length" class="home__day-empty"><MobileShellIcon name="calendar" tone="gray" :size="26" /><view><text class="shell-row__title">今天没有安排</text><text class="shell-muted">课程、考试与办理截止会显示在这里</text></view></view>
          <view class="home__week shell-row" @click="go('/pages/student/agenda/index')"><MobileShellIcon name="calendar" :size="25" round /><view class="shell-row__body"><text class="shell-row__title">查看7天安排</text><text class="shell-muted">掌握本周学习与活动安排</text></view><MobileShellIcon name="chevron-right" :size="20" /></view>
        </view>

        <view v-if="home.todos.length" class="shell-panel">
          <view class="shell-heading"><text class="shell-title">待我处理</text><view class="shell-link" @click="go('/pages/student/my-work/index')">我的办理<MobileShellIcon name="chevron-right" :size="18" /></view></view>
          <view v-for="t in home.todos" :key="t.id" class="shell-row" @click="runAction(t.action)"><MobileShellIcon name="file-text" tone="amber" :size="24" round /><view class="shell-row__body"><text class="shell-row__title">{{ t.title }}</text><text class="shell-muted">{{ messageModuleLabel(t.module) }}{{ t.deadline ? ' · ' + fmtDeadline(t.deadline) : '' }}</text><MobileStatusTag :status="t.status" /></view><MobileShellIcon name="chevron-right" :size="18" /></view>
        </view>

        <HomeQuickServices :key="loadedContextKey" :defaults="home.quickServices" />

        <view v-if="!isOrientationGuide" class="shell-panel home__stage">
          <view class="shell-row"><MobileShellIcon name="home" tone="teal" :size="27" round /><view class="shell-row__body"><text class="shell-row__title">当前阶段：{{ home.stageCard.stageText || '待确认' }}</text><text class="shell-muted">{{ home.stageCard.subtitle || home.stageCard.title }}</text></view></view>
          <view v-if="home.stageCard.progress != null" class="home__stage-progress"><view class="home__stage-progress-bar"><MobileProgress :value="home.stageCard.progress" tone="brand" /></view><text class="shell-muted">{{ progressText }}</text></view>
        </view>
        <view class="shell-panel">
          <view class="shell-heading"><text class="shell-title">最近消息</text><view class="shell-link" @click="go('/pages/student/messages/index')">更多<MobileShellIcon name="chevron-right" :size="18" /></view></view>
          <view v-for="n in home.notices" :key="n.id" class="shell-row" @click="runAction(n.action)"><MobileShellIcon name="bell" :size="23" round /><view class="shell-row__body"><text class="shell-row__title">{{ n.title }}</text><text class="shell-muted">{{ messageModuleLabel(n.source) }}</text></view><text v-if="n.important" class="home__deadline">重要</text></view>
          <text v-if="!home.notices.length" class="shell-muted">暂无校园通知。学校发布后会显示在这里。</text>
        </view>
      </view>
    </MobileGlobalState>
    <MobileTabBar side="student" active="home" :badges="{ message: home ? home.metrics.unread : 0 }" />
    <view v-if="emg" class="emg-banner" @click="goMessages"><text>紧急通知</text><text class="ellipsis">{{ emg.title }}</text><text>去确认</text></view>
  </view>
</template>

<script>
import { tenantBrandConfig } from '@/config'
import { useSessionStore } from '@/stores/session'
import { studentApi } from '@/services/studentApi'
import { getStudentHomeVersion } from '@/utils/viewFreshness'
import { deadlineText } from '@/utils/format'
import { go, toast } from '@/utils/nav'
import { canNavigate, disabledReasonOf, runAction } from '@/services/actionRouter'
import { getStatusBarHeight } from '@/utils/deviceInfo'
import { messageModuleLabel } from '@/services/messagePresentation'
import { orientationStepLabel } from '@/services/orientationPresentation'
import { serviceVisual, studentDateText } from '@/services/studentShellPresentation.mjs'
import HomeQuickServices from './HomeQuickServices.vue'
import { currentSessionGeneration } from '@/services/sessionGeneration.mjs'

const HOME_TTL_MS = 20_000
const GRAD_CLASSES = ['g1', 'g3', 'g7', 'g4', 'g5', 'g6', 'g2', 'g8']

const STEP_ROUTE = {
  ACTIVATE: '/pages/student/orientation/collect/index', INFO: '/pages/student/orientation/collect/index',
  MATERIAL: '/pages/student/orientation/index', PAYMENT: '/pages/student/orientation/green-channel/index',
  DORM: '/pages/student/orientation/index', CHECKIN: '/pages/student/orientation/code/index',
  CONFIRM: '/pages/student/orientation/index'
}

function sessionContextKey(session) {
  const identity = session.identity || {}
  return [session.realUser?.tenantId || '', identity.userId || '', identity.studentId || '', session.currentRole || '', currentSessionGeneration()].join('|')
}

export default {
  components: { HomeQuickServices },
  data() {
    return {
      brand: tenantBrandConfig, home: null, state: 'loading', user: {}, greeting: '你好',
      statusBarHeight: 20, orientation: null,
      orientationBatch: { open: false, daysLeft: 0 }, emg: null,
      lastLoadedAt: 0, loadedContextKey: '', loadedFreshnessVersion: -1, loadedProjectionVersion: ''
    }
  },
  computed: {
    todayText() { return studentDateText() },
    progressText() {
      if (this.home?.stageCard?.progress == null) return '—'
      const value = Number(this.home?.stageCard?.progress)
      return Number.isFinite(value) ? `${value}%` : '—'
    },
    creditRateText() {
      if (this.home?.metrics?.creditRate == null) return '—'
      const value = Number(this.home?.metrics?.creditRate)
      return Number.isFinite(value) ? `${value}%` : '—'
    },
    nextActionTitle() {
      const action = this.home?.nextAction
      return action?.label || '查看待处理事项'
    },
    nextActionDesc() {
      const action = this.home?.nextAction
      if (!action) return ''
      if (!canNavigate(action, 'student')) return disabledReasonOf(action)
      return action.target?.routeExact ? '查看要求，继续办理这条事项' : '查看当前要求与办理进度'
    },
    nextActionText() {
      return canNavigate(this.home?.nextAction, 'student') ? '去办理' : '暂不可办理'
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
        return { key: step.key, label: orientationStepLabel(step), state,
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
    this.statusBarHeight = getStatusBarHeight()
    this.load({ force: true })
  },
  onShow() {
    this._pageActive = true
    this.ensureFresh()
  },
  onHide() {
    this._pageActive = false
    this._homePromise = null
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
    serviceVisual(label) { return serviceVisual(label) },
    messageModuleLabel,
    fmtDeadline(value) { return value ? deadlineText(value) : '' },
    gradClass(index) { return GRAD_CLASSES[index % GRAD_CLASSES.length] },
    goMessages() { go('/pages/student/messages/index') },
    retryLoad() { return this.load({ force: true }) },
    ensureFresh() {
      const session = useSessionStore()
      const contextKey = sessionContextKey(session)
      const freshness = getStudentHomeVersion()
      if (this.loadedContextKey && this.loadedContextKey !== contextKey) { this.home = null; this.user = {}; this._homePromise = null; this.lastLoadedAt = 0 }
      // V3 §5.4：客户端 20s freshness 只是网络优化。contextKey / 本地 freshness /
      // 服务端 projectionVersion 任一变化都必须立刻放弃旧结果，不能等 TTL 到期。
      const fresh = this.home &&
        this.loadedContextKey === contextKey &&
        this.loadedFreshnessVersion === freshness &&
        this.loadedProjectionVersion === (this.home.projectionVersion || '') &&
        Date.now() - this.lastLoadedAt < HOME_TTL_MS
      if (!fresh) this.load()
    },
    // V3 §4.2：页面只调用 runAction()，不再自己拼 route。
    runAction(action) { return runAction(action, { side: 'student' }) },
    canRun(action) { return canNavigate(action, 'student') },
    disabledReason(action) { return disabledReasonOf(action) },
    clockOf(iso) { return iso ? String(iso).slice(11, 16) : '' },
    kindText(kind) {
      return { COURSE: '课程', EXAM: '考试', DEADLINE: '办理截止' }[String(kind || '')] || ''
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
          // 服务端 projectionVersion 变了 = 底层事实变了：立刻记下新版本，
          // 让下一次 20s 内的短路判断不会再拿旧投影顶着（V3 §5.4 / 深审 P1-12）。
          this.loadedProjectionVersion = data.projectionVersion || ''
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
          return null
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

<style scoped lang="scss">
@import '@/styles/student-shell.scss';
.home__body { position:relative; padding-top:0; margin-top:-10px; }
.home__priority, .home__allclear { display:flex; align-items:center; gap:12px; border-radius:16px; padding:16px; margin-bottom:14px; background:#fff8e9; }
.home__allclear { background:#effaf6; }
.home__priority-button { flex-shrink:0; padding:0 12px; min-height:42px; line-height:42px; border:0; border-radius:14px; background:#1671f8; color:#fff; font-size:14px; }
.home__priority-button::after, .home__orientation-button::after { border:0; }
.home__orientation { padding-top:6px; }
.home__orientation-button { background:#1671f8; color:#fff; font-size:15px; border-radius:12px; line-height:44px; }
.home__deadline { display:block; color:#b87308; font-size:12px; margin-top:8px; }
.home__orientation-steps { margin-top:14px; }
.home__orientation-links { display:flex; justify-content:space-between; }
.home__orientation-step { display:flex; gap:8px; align-items:center; font-size:13px; min-height:30px; }
.home__orientation-step .shell-muted { margin-left:auto; }
.home__today-date { margin-top:-8px; margin-bottom:20px; }
.home__course { display:flex; gap:14px; position:relative; padding-bottom:24px; }
.home__course-time { width:52px; flex-shrink:0; font-size:18px; font-weight:700; line-height:1.5; }
.home__course-dur { display:block; font-size:13px; font-weight:400; color:#65718a; }
.home__course-line { border-left:2px solid #c9dfff; margin:6px 2px 0; }
.home__place { display:flex; gap:4px; align-items:center; margin-top:6px; font-size:13px; color:#65718a; }
.home__course-tag { font-size:11px; color:#00866e; }
.home__day-empty { display:flex; gap:12px; align-items:center; padding:10px 0 24px; }
.home__week { background:#eff6ff; padding:10px 12px; border-radius:12px; min-height:64px; }
.home__quick { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:14px 8px; }
.home__quick-item { display:flex; flex-direction:column; align-items:center; gap:9px; min-width:0; font-size:14px; line-height:1.5; text-align:center; }
.home__stage .shell-row { min-height:48px; }
.home__stage-progress { display:flex; align-items:center; gap:12px; margin-top:12px; }
.home__stage-progress-bar { flex:1; min-width:0; }
.home__alert-btn { color:#1671f8; min-height:44px; }
.home__alert-note { color:#65718a; font-size:12px; }
.emg-banner { position:fixed; bottom:calc(72px + env(safe-area-inset-bottom)); left:12px; right:12px; display:flex; gap:10px; padding:12px; background:#fff0ef; color:#bf3030; border:1px solid #ffb9b4; border-radius:12px; z-index:35; font-size:13px; }
@media (max-width:375px) { .home__priority { gap:8px; padding:14px 12px; } .home__priority-button { padding:0 10px; font-size:13px; } }
</style>
