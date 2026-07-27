<template>
  <view class="page-wrap">
    <view class="aa__hero hero-band is-brand">
      <view class="hero-band__orb" />
      <view class="mnav__status" :style="{ height: statusBarHeight + 'px' }" />
      <view class="aa__navbar"><text class="aa__navbar-back" @click="back">‹</text><text class="aa__navbar-title">我的教务</text></view>
      <view class="aa__status" v-if="status">
        <text class="aa__status-t">学籍状态</text>
        <text class="aa__status-v">{{ statusText(status.studentStatus) }}</text>
        <text class="aa__status-tag" :class="{ 'is-warn': !status.enrolled }">{{ status.enrolled ? '在籍' : '非在籍' }}</text>
      </view>
    </view>

    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad aa__body" v-if="status">
        <view v-if="partialError" class="aa__partial" @click="load">
          <text>部分教务数据暂未更新</text><text>点击重试</text>
        </view>

        <view v-if="taskCues.length" class="card aa__tasks">
          <view class="aa__section-head"><text>当前需要我处理</text><text class="aa__section-sub">点击直达具体事项</text></view>
          <view class="aa__task-list">
            <view v-for="task in taskCues" :key="task.key" class="aa__task" @click="go(task.route)">
              <text class="aa__task-icon">{{ task.icon }}</text>
              <view class="flex-1">
                <text class="aa__task-title">{{ task.title }}</text>
                <text class="aa__task-sub">{{ task.description }}</text>
              </view>
              <text class="aa__task-count">{{ task.count }}</text>
              <text class="aa__task-go">去处理 ›</text>
            </view>
          </view>
        </view>

        <view class="aa__focus-grid">
          <view class="aa__focus card" @click="go('/pages/student/academic-affairs/schedule')">
            <view class="aa__focus-head"><text>今日课程</text><text class="aa__link">查看课表 ›</text></view>
            <template v-if="todayCourses.length">
              <text class="aa__focus-value">{{ todayCourses.length }} 门</text>
              <text class="aa__focus-main">{{ todayCourses[0].courseName }}</text>
              <text class="aa__focus-sub">第{{ todayCourses[0].slotNo }}节 · {{ todayCourses[0].classroom || '教室待定' }}</text>
            </template>
            <text v-else class="aa__focus-empty">{{ todayEmptyText }}</text>
          </view>

          <view class="aa__focus card" @click="go('/pages/student/academic-affairs/exam')">
            <view class="aa__focus-head"><text>近期考试</text><text class="aa__link">全部 ›</text></view>
            <template v-if="upcomingExam">
              <text class="aa__focus-value aa__focus-value--sm">{{ upcomingExam.examDate || '日期待定' }}</text>
              <text class="aa__focus-main">{{ upcomingExam.courseName }}</text>
              <text class="aa__focus-sub">{{ upcomingExam.startTime || '时间待定' }} · {{ upcomingExam.classroom || '考场待定' }}</text>
            </template>
            <text v-else class="aa__focus-empty">{{ examLoaded ? '暂无已发布考试' : '考试数据暂未加载' }}</text>
          </view>
        </view>

        <view v-if="warningCount" class="aa__warning card" @click="go('/pages/student/academic-affairs/warning')">
          <view><text class="aa__warning-title">你有 {{ warningCount }} 条学业预警待关注</text><text class="aa__warning-sub">查看原因、责任老师和后续处理要求</text></view>
          <text class="aa__warning-go">去查看 ›</text>
        </view>

        <view class="card aa__section">
          <view class="aa__section-head"><text>常用服务</text><text class="aa__section-sub">高频事项优先</text></view>
          <view class="icon-grid">
            <view v-for="(it, i) in commonEntries" :key="it.key" class="icon-grid__item" @click="go(it.route)">
              <view class="icon-grid__badge" :class="gradClass(i)">{{ it.icon }}</view>
              <text class="icon-grid__label">{{ it.label }}</text>
              <text v-if="badgeOf(it.key)" class="aa__badge">{{ badgeOf(it.key) }}</text>
            </view>
          </view>
        </view>

        <view class="card aa__section">
          <view class="aa__section-head" @click="showAll = !showAll">
            <text>全部教务服务</text><text class="aa__link">{{ showAll ? '收起' : `${otherEntries.length}项 ›` }}</text>
          </view>
          <view v-if="showAll" class="icon-grid aa__all-grid">
            <view v-for="(it, i) in otherEntries" :key="it.key" class="icon-grid__item" @click="go(it.route)">
              <view class="icon-grid__badge" :class="gradClass(i + commonEntries.length)">{{ it.icon }}</view>
              <text class="icon-grid__label">{{ it.label }}</text>
              <text v-if="badgeOf(it.key)" class="aa__badge">{{ badgeOf(it.key) }}</text>
            </view>
          </view>
        </view>
      </view>
    </MobileGlobalState>
    <MobileTabBar side="student" active="home" />
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { go } from '@/utils/nav'

const ST = { REGISTERED: '在籍注册', NORMAL: '在籍', SUSPENDED: '休学中', RETAINED: '留级',
  WITHDRAWN: '已退学', GRADUATED: '已毕业', COMPLETED: '已结业', PENDING_REGISTER: '待注册' }
const GRAD_CLASSES = ['g1', 'g4', 'g3', 'g5', 'g2', 'g7', 'g6', 'g8']
const ENTRIES = [
  { key: 'schedule', label: '我的课表', icon: '📅', route: '/pages/student/academic-affairs/schedule' },
  { key: 'selection', label: '网上选课', icon: '✅', route: '/pages/student/academic-affairs/selection' },
  { key: 'transcript', label: '我的成绩', icon: '📊', route: '/pages/student/academic-affairs/transcript' },
  { key: 'exam', label: '考试/缓考', icon: '🗓', route: '/pages/student/academic-affairs/exam' },
  { key: 'credits', label: '学分修读', icon: '🎯', route: '/pages/student/academic-affairs/credits' },
  { key: 'status', label: '学籍与异动', icon: '📋', route: '/pages/student/academic-affairs/status' },
  { key: 'graduation', label: '毕业进度', icon: '🎓', route: '/pages/student/academic-affairs/graduation' },
  { key: 'registration', label: '学期注册', icon: '🪪', route: '/pages/student/academic-affairs/registration' },
  { key: 'warning', label: '学业预警', icon: '⚠', route: '/pages/student/academic-affairs/warning' },
  { key: 'makeup', label: '补考重修', icon: '📝', route: '/pages/student/academic-affairs/makeup' },
  { key: 'recognition', label: '成绩认定', icon: '🔄', route: '/pages/student/academic-affairs/recognition' },
  { key: 'recheck', label: '成绩复查', icon: '🔍', route: '/pages/student/academic-affairs/recheck' },
  { key: 'textbook', label: '我的教材', icon: '📚', route: '/pages/student/academic-affairs/textbook' },
  { key: 'levelExam', label: '等级考试', icon: '🏅', route: '/pages/student/academic-affairs/level-exam' },
  { key: 'majorSplit', label: '专业分流', icon: '🧭', route: '/pages/student/academic-affairs/major-split' },
  { key: 'attendance', label: '我的考勤', icon: '✅', route: '/pages/student/academic-affairs/attendance' },
  { key: 'calendar', label: '校历', icon: '📆', route: '/pages/student/academic-affairs/calendar' },
  { key: 'clearance', label: '清考结果', icon: '📎', route: '/pages/student/academic-affairs/clearance' },
  { key: 'evaluation', label: '学生评教', icon: '⭐', route: '/pages/student/academic-affairs/evaluation' }
]
const COMMON_KEYS = new Set(['schedule', 'selection', 'transcript', 'exam', 'credits', 'status', 'graduation', 'registration'])

function rowsOf(data) {
  if (Array.isArray(data)) return data
  return (data && (data.items || data.list || data.batches)) || []
}
function localDateKey(date) {
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}
function activeInWeek(item, week) {
  const current = Number(week)
  if (!Number.isFinite(current) || current < 1) return false
  const start = Number(item.startWeek || 1)
  const end = Number(item.endWeek || start)
  if (current < start || current > end) return false
  const parity = String(item.weekParity || 'ALL').toUpperCase()
  if (parity === 'ODD') return current % 2 === 1
  if (parity === 'EVEN') return current % 2 === 0
  return true
}
function unfinished(rows) {
  const done = new Set(['DONE', 'COMPLETED', 'APPROVED', 'REGISTERED', 'SUBMITTED', 'PUBLISHED', 'CLOSED'])
  return (rows || []).filter((row) => !done.has(String(row.status || row.registrationStatus || '').toUpperCase()))
}
function pendingEvaluationCount(data) {
  if (data && Number.isFinite(Number(data.pending))) return Number(data.pending)
  return rowsOf(data).filter((row) => row && row.canSubmit === true && row.submitted !== true).length
}

export default {
  data() {
    return {
      status: null, state: 'loading', statusBarHeight: 20, entries: ENTRIES,
      scheduleItems: [], currentWeek: null, examItems: [], examLoaded: false,
      warningCount: 0, evaluationCount: 0, registrationCount: 0, returnedDeferCount: 0,
      retakeCount: 0, partialError: false, showAll: false
    }
  },
  computed: {
    commonEntries() { return this.entries.filter((x) => COMMON_KEYS.has(x.key)) },
    otherEntries() { return this.entries.filter((x) => !COMMON_KEYS.has(x.key)) },
    taskCues() {
      return [
        { key: 'registration', icon: '🪪', title: '完成学期注册', description: '存在尚未完成的注册批次', count: this.registrationCount, route: '/pages/student/academic-affairs/registration' },
        { key: 'evaluation', icon: '⭐', title: '完成学生评教', description: '开放窗口内课程等待匿名评价', count: this.evaluationCount, route: '/pages/student/academic-affairs/evaluation' },
        { key: 'warning', icon: '⚠️', title: '跟进学业预警', description: '查看原因、责任老师和处理要求', count: this.warningCount, route: '/pages/student/academic-affairs/warning' },
        { key: 'defer', icon: '🗓', title: '补充缓考材料', description: '存在退回待重新提交的缓考申请', count: this.returnedDeferCount, route: '/pages/student/academic-affairs/exam' },
        { key: 'makeup', icon: '📝', title: '处理补考重修', description: '存在可报名的当前有效未通过课程', count: this.retakeCount, route: '/pages/student/academic-affairs/makeup' }
      ].filter((item) => Number(item.count || 0) > 0)
    },
    todayCourses() {
      const day = new Date().getDay() || 7
      return this.scheduleItems
        .filter((item) => Number(item.weekday) === day && activeInWeek(item, this.currentWeek))
        .sort((a, b) => Number(a.slotNo || 0) - Number(b.slotNo || 0))
    },
    todayEmptyText() {
      if (this.currentWeek == null) return '校历周次暂未加载'
      if (Number(this.currentWeek) === 0) return '当前学期尚未开始'
      return `第${this.currentWeek}周今天暂无课程`
    },
    upcomingExam() {
      const today = localDateKey(new Date())
      return this.examItems.filter((x) => !x.examDate || x.examDate >= today)
        .sort((a, b) => String(a.examDate || '9999').localeCompare(String(b.examDate || '9999')))[0] || null
    }
  },
  onLoad() {
    try { this.statusBarHeight = uni.getSystemInfoSync().statusBarHeight || 20 } catch (e) {}
    this.load()
  },
  methods: {
    go,
    back() { uni.navigateBack({ delta: 1, fail: () => go('/pages/student/home/index') }) },
    gradClass(i) { return GRAD_CLASSES[i % GRAD_CLASSES.length] },
    statusText(s) { return ST[s] || s || '待确认' },
    badgeOf(key) {
      if (key === 'warning') return this.warningCount || ''
      if (key === 'evaluation') return this.evaluationCount || ''
      if (key === 'registration') return this.registrationCount || ''
      if (key === 'makeup') return this.retakeCount || ''
      return ''
    },
    async load() {
      this.state = 'loading'
      this.partialError = false
      try {
        this.status = await studentApi.getMyAcadStatus()
      } catch (e) {
        this.state = 'error'
        return
      }
      const results = await Promise.allSettled([
        studentApi.getMySchedule(), studentApi.getMyExamSchedule(),
        studentApi.getMyWarnings(), studentApi.getMyEvaluationTasks(),
        studentApi.getMyRegistration(), studentApi.getMyDeferrals(), studentApi.getMakeupOptions()
      ])
      if (results[0].status === 'fulfilled') {
        this.scheduleItems = rowsOf(results[0].value)
        this.currentWeek = results[0].value && results[0].value.currentWeek != null
          ? Number(results[0].value.currentWeek) : null
      } else {
        this.scheduleItems = []
        this.currentWeek = null
      }
      this.examLoaded = results[1].status === 'fulfilled'
      this.examItems = this.examLoaded ? rowsOf(results[1].value) : []
      this.warningCount = results[2].status === 'fulfilled' ? unfinished(rowsOf(results[2].value)).length : 0
      this.evaluationCount = results[3].status === 'fulfilled' ? pendingEvaluationCount(results[3].value) : 0
      this.registrationCount = results[4].status === 'fulfilled' ? unfinished(rowsOf(results[4].value)).length : 0
      this.returnedDeferCount = results[5].status === 'fulfilled'
        ? rowsOf(results[5].value).filter((row) => String(row.status || '').toUpperCase() === 'RETURNED').length : 0
      const makeup = results[6].status === 'fulfilled' ? (results[6].value || {}) : {}
      this.retakeCount = (makeup.retakeOptions || []).length
      this.partialError = results.some((result) => result.status === 'rejected') || this.currentWeek == null
      this.state = 'ready'
    }
  }
}
</script>

<style scoped>
.aa__hero { padding: 0 var(--page-padding-mobile) var(--space-4); }
.aa__navbar { position: relative; height: 40px; display: flex; align-items: center; justify-content: center; }
.aa__navbar-back { position: absolute; left: 0; color: #fff; font-size: 22px; padding: 4px 8px; }
.aa__navbar-title { font-size: var(--font-size-lg); font-weight: var(--font-weight-semibold); color: #fff; }
.aa__status { margin-top: var(--space-2); }
.aa__status-t { display: block; font-size: var(--font-size-sm); color: rgba(255,255,255,0.85); }
.aa__status-v { display: block; font-size: 20px; font-weight: 700; color: #fff; margin-top: 4px; }
.aa__status-tag { display: inline-block; margin-top: 6px; font-size: var(--font-size-xs); color: #fff; background: rgba(255,255,255,0.25); padding: 2px 10px; border-radius: var(--radius-full); }
.aa__status-tag.is-warn { background: rgba(217,119,6,0.85); }
.aa__body { padding-top: var(--space-3); }
.aa__partial { display: flex; justify-content: space-between; margin-bottom: var(--space-3); padding: var(--space-2) var(--space-3); border-radius: var(--radius-md); background: var(--warning-50); color: var(--warning-700); font-size: var(--font-size-xs); }
.aa__tasks { margin-bottom: var(--space-3); }
.aa__task-list { display: flex; flex-direction: column; gap: var(--space-2); }
.aa__task { display: flex; align-items: center; gap: var(--space-2); padding: var(--space-2); border: 1px solid var(--border-light); border-radius: var(--radius-md); background: var(--surface-base); }
.aa__task-icon { display: grid; place-items: center; width: 32px; height: 32px; border-radius: var(--radius-sm); background: var(--brand-50); }
.aa__task-title { display: block; color: var(--text-primary); font-size: var(--font-size-sm); font-weight: 600; }
.aa__task-sub { display: block; margin-top: 2px; color: var(--text-tertiary); font-size: 10px; }
.aa__task-count { min-width: 20px; height: 20px; border-radius: 10px; background: var(--danger-50); color: var(--danger-600); font-size: 11px; line-height: 20px; text-align: center; }
.aa__task-go { color: var(--brand-primary); font-size: var(--font-size-xs); }
.aa__focus-grid { display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-3); margin-bottom: var(--space-3); }
.aa__focus { min-height: 132px; }
.aa__focus-head, .aa__section-head { display: flex; align-items: center; justify-content: space-between; font-weight: 600; }
.aa__link { color: var(--brand-primary); font-size: var(--font-size-xs); font-weight: 400; }
.aa__focus-value { display: block; margin-top: var(--space-3); color: var(--brand-primary); font-size: 24px; font-weight: 700; }
.aa__focus-value--sm { font-size: var(--font-size-md); }
.aa__focus-main { display: block; margin-top: 4px; font-weight: 600; }
.aa__focus-sub, .aa__focus-empty { display: block; margin-top: 4px; color: var(--text-tertiary); font-size: var(--font-size-xs); line-height: 1.5; }
.aa__warning { display: flex; align-items: center; justify-content: space-between; margin-bottom: var(--space-3); background: var(--warning-50); }
.aa__warning-title { display: block; color: var(--warning-700); font-weight: 600; }
.aa__warning-sub { display: block; margin-top: 3px; color: var(--text-secondary); font-size: var(--font-size-xs); }
.aa__warning-go { color: var(--warning-700); font-size: var(--font-size-sm); }
.aa__section { margin-bottom: var(--space-3); }
.aa__section-head { margin-bottom: var(--space-3); }
.aa__section-sub { color: var(--text-tertiary); font-size: var(--font-size-xs); font-weight: 400; }
.icon-grid__item { position: relative; }
.aa__badge { position: absolute; top: 0; right: 10%; min-width: 17px; height: 17px; padding: 0 4px; border-radius: 9px; background: var(--danger-600); color: #fff; font-size: 10px; line-height: 17px; text-align: center; }
.aa__all-grid { padding-top: var(--space-1); }
</style>
