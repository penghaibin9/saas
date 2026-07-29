<template>
  <view class="page-wrap">
    <view class="ta__hero hero-band is-teacher">
      <view class="hero-band__orb" />
      <view class="mnav__status" :style="{ height: statusBarHeight + 'px' }" />
      <view class="ta__navbar"><text class="ta__navbar-back" @click="back">‹</text><text class="ta__navbar-title">我的教学</text></view>
      <view class="ta__summary">
        <text class="ta__summary-label">今日教学</text>
        <text class="ta__summary-value">{{ todaySummary }}</text>
        <text class="ta__summary-sub">{{ headline }}</text>
      </view>
    </view>

    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad ta__body">
        <view v-if="partialError" class="ta__partial" @click="load">
          <text>部分教学数据暂未更新</text><text>点击重试</text>
        </view>

        <view class="ta__today card" @click="go('/pages/teacher/my-schedule/index')">
          <view class="ta__section-head"><text>今日课表</text><text class="ta__link">完整课表 ›</text></view>
          <view v-if="todayCourses.length" class="ta__course-list">
            <view v-for="item in todayCourses.slice(0, 3)" :key="item.itemId || item.courseName + item.slotNo" class="ta__course">
              <text class="ta__course-slot">第{{ item.slotNo }}节</text>
              <view class="flex-1"><text class="ta__course-name">{{ item.courseName }}</text><text class="ta__course-sub">{{ item.className || '教学班' }} · {{ item.classroom || '教室待定' }}</text></view>
            </view>
          </view>
          <text v-else class="ta__empty">{{ todayEmptyText }}</text>
        </view>

        <view v-if="taskCues.length" class="ta__tasks card">
          <view class="ta__section-head"><text>待处理</text><text class="ta__section-sub">点击直达第一条具体任务</text></view>
          <view class="ta__task-grid">
            <view v-for="cue in taskCues" :key="cue.key" class="ta__task" @click="go(cue.route)">
              <text class="ta__task-value">{{ cue.count }}</text>
              <text class="ta__task-label">{{ cue.label }}</text>
              <text v-if="cue.detail" class="ta__task-detail">{{ cue.detail }}</text>
            </view>
          </view>
        </view>

        <view class="card ta__services">
          <view class="ta__section-head"><text>我的教务服务</text><text class="ta__section-sub">无权限入口不会显示</text></view>
          <view class="icon-grid">
            <view v-for="(it, i) in visibleEntries" :key="it.key" class="icon-grid__item" @click="go(it.route)">
              <view class="icon-grid__badge" :class="gradClass(i)">{{ it.icon }}</view>
              <text class="icon-grid__label">{{ it.label }}</text>
              <text v-if="countOf(it.key)" class="ta__badge">{{ countOf(it.key) }}</text>
            </view>
          </view>
        </view>
      </view>
    </MobileGlobalState>
    <MobileTabBar side="teacher" active="home" />
  </view>
</template>

<script>
import { teacherApi } from '@/services/teacherApi'
import { normalizeError } from '@/services/request'
import { go } from '@/utils/nav'

const GRAD_CLASSES = ['g1', 'g4', 'g3', 'g5', 'g2', 'g7']
const ENTRIES = [
  { key: 'schedule', label: '我的课表', icon: '📅', route: '/pages/teacher/my-schedule/index', always: true },
  { key: 'grade', label: '成绩录入', icon: '📊', route: '/pages/teacher/academic-affairs/grade-entry', source: 'grade' },
  { key: 'attendance', label: '课堂考勤', icon: '✅', route: '/pages/teacher/academic-affairs/attendance', source: 'attendance' },
  { key: 'scheduleChange', label: '调停课', icon: '🔀', route: '/pages/teacher/schedule-change/index', source: 'scheduleChange' },
  { key: 'scheduleReview', label: '调课审批', icon: '✔️', route: '/pages/teacher/academic-affairs/schedule-change-review', source: 'scheduleReview' },
  { key: 'statusReview', label: '异动审批', icon: '📋', route: '/pages/teacher/academic-affairs/status-change-review', source: 'statusReview' },
  { key: 'defer', label: '缓考审批', icon: '📝', route: '/pages/teacher/exam-defer/index', source: 'defer' },
  { key: 'academicTask', label: '教学任务', icon: '📚', route: '/pages/teacher/academic-task/index', source: 'academicTask' },
  { key: 'workload', label: '工作量申报', icon: '🧾', route: '/pages/teacher/academic-affairs/workload', source: 'workload' },
  { key: 'warning', label: '学业预警', icon: '⚠', route: '/pages/teacher/academic-warning/index', source: 'warning' }
]

function listOf(data) {
  if (Array.isArray(data)) return data
  return (data && (data.items || data.list)) || []
}
function isExpectedForbidden(result) {
  return result.status === 'rejected' && normalizeError(result.reason).kind === 'forbidden'
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
function pendingRows(rows) {
  const pending = new Set(['PENDING', 'NOT_STARTED', 'INPUTTING', 'RETURNED', 'PENDING_CONFIRM', 'PROCESSING', 'ESCALATED'])
  return (rows || []).filter((row) => !row.status || pending.has(String(row.status).toUpperCase()))
}
function taskTarget(key, row) {
  if (!row) return ''
  const idMap = {
    grade: row.gradeTaskId || row.taskId,
    academicTask: row.taskId || row.teachingTaskId,
    scheduleReview: row.changeId || row.scheduleChangeId,
    defer: row.deferId || row.id,
    warning: row.warningId || row.id
  }
  const base = {
    grade: '/pages/teacher/academic-affairs/grade-entry',
    academicTask: '/pages/teacher/academic-task/index',
    scheduleReview: '/pages/teacher/academic-affairs/schedule-change-review',
    defer: '/pages/teacher/exam-defer/index',
    warning: '/pages/teacher/academic-warning/index'
  }[key]
  const id = idMap[key]
  return base && id ? `${base}?id=${encodeURIComponent(id)}` : (base || '')
}
function taskDetail(key, row) {
  if (!row) return ''
  if (key === 'grade') return row.courseName || row.className || '打开成绩任务'
  if (key === 'academicTask') return row.courseName || row.taskName || '确认教学任务'
  if (key === 'scheduleReview') return row.courseName || row.changeTypeLabel || '处理调课申请'
  if (key === 'defer') return row.studentName || row.courseName || '处理缓考申请'
  if (key === 'warning') return row.studentName || row.reason || '跟进预警学生'
  return ''
}

export default {
  data() {
    return {
      statusBarHeight: 20, state: 'loading', partialError: false,
      scheduleItems: [], currentWeek: null, available: { schedule: true }, counts: {}, entries: ENTRIES,
      taskTargets: {}, taskDetails: {}
    }
  },
  computed: {
    todayCourses() {
      const day = new Date().getDay() || 7
      return this.scheduleItems
        .filter((item) => Number(item.weekday) === day && activeInWeek(item, this.currentWeek))
        .sort((a, b) => Number(a.slotNo || 0) - Number(b.slotNo || 0))
    },
    todaySummary() {
      if (this.currentWeek == null) return '周次待确认'
      if (Number(this.currentWeek) === 0) return '学期未开始'
      return this.todayCourses.length ? `${this.todayCourses.length} 门课程` : '今日无课'
    },
    todayEmptyText() {
      if (this.currentWeek == null) return '学校校历缺少学期开始日期，暂不判断今日课程。'
      if (Number(this.currentWeek) === 0) return '当前学期尚未开始。'
      return `第${this.currentWeek}周今天暂无课程，可查看完整课表安排。`
    },
    visibleEntries() { return this.entries.filter((x) => x.always || this.available[x.source]) },
    taskCues() {
      return [
        { key: 'grade', label: '待录成绩', count: this.counts.grade || 0, route: this.taskTargets.grade || '/pages/teacher/academic-affairs/grade-entry', detail: this.taskDetails.grade },
        { key: 'academicTask', label: '任务确认', count: this.counts.academicTask || 0, route: this.taskTargets.academicTask || '/pages/teacher/academic-task/index', detail: this.taskDetails.academicTask },
        { key: 'scheduleReview', label: '调课审批', count: this.counts.scheduleReview || 0, route: this.taskTargets.scheduleReview || '/pages/teacher/academic-affairs/schedule-change-review', detail: this.taskDetails.scheduleReview },
        { key: 'defer', label: '缓考审批', count: this.counts.defer || 0, route: this.taskTargets.defer || '/pages/teacher/exam-defer/index', detail: this.taskDetails.defer },
        { key: 'warning', label: '学业预警', count: this.counts.warning || 0, route: this.taskTargets.warning || '/pages/teacher/academic-warning/index', detail: this.taskDetails.warning }
      ].filter((x) => this.available[x.key] && x.count > 0)
    },
    headline() {
      if (this.partialError) return '部分待办未完全加载，请点击页面提示重试'
      const total = this.taskCues.reduce((sum, x) => sum + Number(x.count || 0), 0)
      return total ? `还有 ${total} 项教务任务需要处理` : '当前没有紧急教务待办'
    }
  },
  onLoad() {
    try { this.statusBarHeight = uni.getSystemInfoSync().statusBarHeight || 20 } catch (e) {}
    this.load()
  },
  methods: {
    go,
    back() { uni.navigateBack({ delta: 1, fail: () => go('/pages/teacher/workbench/index') }) },
    gradClass(i) { return GRAD_CLASSES[i % GRAD_CLASSES.length] },
    countOf(key) { return this.counts[key] || '' },
    setResult(key, result, pendingOnly = false) {
      if (result.status !== 'fulfilled') return false
      this.available[key] = true
      const rows = listOf(result.value)
      const pending = pendingOnly ? pendingRows(rows) : rows
      this.counts[key] = pendingOnly
        ? pending.length
        : Number(result.value && result.value.total != null ? result.value.total : rows.length) || 0
      const first = pending[0]
      const target = taskTarget(key, first)
      if (target) this.taskTargets[key] = target
      const detail = taskDetail(key, first)
      if (detail) this.taskDetails[key] = detail
      return true
    },
    async load() {
      this.state = 'loading'
      this.partialError = false
      const results = await Promise.allSettled([
        teacherApi.getMySchedule(),
        teacherApi.getGradeTasks(),
        teacherApi.getAcademicMyTasks(),
        teacherApi.getAttendanceSessions(),
        teacherApi.getAcademicScheduleChanges(),
        teacherApi.getScheduleChangePending(),
        teacherApi.getStatusChangePending(),
        teacherApi.getAcademicDeferPending(),
        teacherApi.getAcademicWarnings(),
        teacherApi.getWorkloadDeclarations()
      ])
      if (results.every((r) => r.status === 'rejected')) {
        this.state = 'error'
        return
      }
      if (results[0].status === 'fulfilled') {
        this.scheduleItems = listOf(results[0].value)
        this.currentWeek = results[0].value && results[0].value.currentWeek != null
          ? Number(results[0].value.currentWeek) : null
      } else {
        this.scheduleItems = []
        this.currentWeek = null
      }
      this.available = { schedule: true }
      this.counts = {}
      this.taskTargets = {}
      this.taskDetails = {}
      this.setResult('grade', results[1], true)
      this.setResult('academicTask', results[2], true)
      this.setResult('attendance', results[3])
      this.setResult('scheduleChange', results[4], true)
      this.setResult('scheduleReview', results[5], true)
      this.setResult('statusReview', results[6], true)
      this.setResult('defer', results[7], true)
      this.setResult('warning', results[8], true)
      this.setResult('workload', results[9], true)
      this.partialError = results.some((r) => r.status === 'rejected' && !isExpectedForbidden(r)) || this.currentWeek == null
      this.state = 'ready'
    }
  }
}
</script>

<style scoped>
.ta__hero { padding: 0 var(--page-padding-mobile) var(--space-4); }
.ta__navbar { position: relative; height: 40px; display: flex; align-items: center; justify-content: center; }
.ta__navbar-back { position: absolute; left: 0; color: #fff; font-size: 22px; padding: 4px 8px; }
.ta__navbar-title { font-size: var(--font-size-lg); font-weight: var(--font-weight-semibold); color: #fff; }
.ta__summary { margin-top: var(--space-2); }
.ta__summary-label { display: block; color: rgba(255,255,255,.82); font-size: var(--font-size-sm); }
.ta__summary-value { display: block; margin-top: 3px; color: #fff; font-size: 22px; font-weight: 700; }
.ta__summary-sub { display: block; margin-top: 4px; color: rgba(255,255,255,.88); font-size: var(--font-size-xs); }
.ta__body { padding-top: var(--space-3); }
.ta__partial { display: flex; justify-content: space-between; margin-bottom: var(--space-3); padding: var(--space-2) var(--space-3); border-radius: var(--radius-md); background: var(--warning-50); color: var(--warning-700); font-size: var(--font-size-xs); }
.ta__today, .ta__tasks, .ta__services { margin-bottom: var(--space-3); }
.ta__section-head { display: flex; justify-content: space-between; align-items: center; font-weight: 600; }
.ta__link { color: var(--teacher-600); font-size: var(--font-size-xs); font-weight: 400; }
.ta__section-sub { color: var(--text-tertiary); font-size: var(--font-size-xs); font-weight: 400; }
.ta__course-list { margin-top: var(--space-2); }
.ta__course { display: flex; gap: var(--space-3); padding: var(--space-2) 0; border-bottom: 1px solid var(--border-light); }
.ta__course:last-child { border-bottom: 0; }
.ta__course-slot { width: 54px; color: var(--teacher-600); font-size: var(--font-size-sm); font-weight: 600; }
.ta__course-name { display: block; font-weight: 600; }
.ta__course-sub, .ta__empty { display: block; margin-top: 3px; color: var(--text-tertiary); font-size: var(--font-size-xs); }
.ta__empty { padding: var(--space-4) 0 var(--space-2); text-align: center; }
.ta__task-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: var(--space-2); margin-top: var(--space-3); }
.ta__task { padding: var(--space-3) var(--space-2); border-radius: var(--radius-md); background: var(--teacher-50); text-align: center; }
.ta__task-value { display: block; color: var(--teacher-600); font-size: 22px; font-weight: 700; }
.ta__task-label { display: block; margin-top: 2px; color: var(--text-secondary); font-size: var(--font-size-xs); }
.ta__task-detail { display: block; margin-top: 3px; overflow: hidden; color: var(--text-tertiary); font-size: 10px; text-overflow: ellipsis; white-space: nowrap; }
.icon-grid__item { position: relative; }
.ta__badge { position: absolute; top: 0; right: 10%; min-width: 17px; height: 17px; padding: 0 4px; border-radius: 9px; background: var(--danger-600); color: #fff; font-size: 10px; line-height: 17px; text-align: center; }
</style>
