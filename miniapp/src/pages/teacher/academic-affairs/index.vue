<template>
  <view class="page-wrap">
    <MobileNavBar v-if="selectedInvig" variant="teacher" title="我的监考安排" :before-back="backToTeaching" show-back />
    <view v-else class="ta__hero hero-band is-teacher">
      <view class="hero-band__orb" />
      <view class="mnav__status" :style="{ height: statusBarHeight + 'px' }" />
      <view class="ta__navbar"><text class="ta__navbar-back" @click="back">‹</text><text class="ta__navbar-title">我的教学</text></view>
      <view class="ta__summary">
        <text class="ta__summary-label">今日教学</text>
        <text class="ta__summary-value">{{ state === 'ready' ? todaySummary : '教学信息' }}</text>
        <text class="ta__summary-sub">{{ state === 'ready' ? headline : (state === 'loading' ? '正在读取教学信息…' : '暂不可查看教学信息') }}</text>
      </view>
    </view>

    <MobileGlobalState :state="state" @retry="load" @back="back">
      <view class="page-pad ta__body">
        <view v-if="selectedInvig" class="card ta__invig-detail">
          <button class="btn btn-ghost" @click="backToTeaching">‹ 返回我的教学</button>
          <text class="t-md t-bold">{{ selectedInvig.courseName || '考试课程' }}</text>
          <text class="ta__course-sub">{{ selectedInvig.className || '教学班未提供' }}</text>
          <view class="ta__detail-fact"><text>考试日期</text><text>{{ selectedInvig.examDate || '日期待定' }}</text></view>
          <view class="ta__detail-fact"><text>考试时间</text><text>{{ selectedInvig.startTime || '--:--' }}—{{ selectedInvig.endTime || '--:--' }}</text></view>
          <view class="ta__detail-fact"><text>考场</text><text>{{ selectedInvig.classroom || '考场待定' }}</text></view>
          <view class="ta__detail-fact"><text>本人职责</text><text>{{ invigilationRoleLabel(selectedInvig.role) }}</text></view>
          <view class="ta__detail-fact"><text>确认状态</text><text>{{ selectedInvig.confirmStatus === 'CONFIRMED' ? '已确认' : selectedInvig.confirmStatus ? '待确认' : '状态未提供' }}</text></view>
          <view class="ta__detail-fact"><text>任务进度</text><text>{{ selectedInvig.workStatus === 'FINISHED' ? '已结束' : selectedInvig.workStatus ? '待监考' : '状态未提供' }}</text></view>
          <text class="ta__course-sub">安排来自正式考试日程。如有调整，请刷新后核对。</text>
          <button class="btn btn-primary" @click="load">刷新正式安排</button>
        </view>
        <template v-else>
        <view v-if="partialError" class="ta__partial" @click="load">
          <text>部分教学数据暂未更新</text><text>点击重试</text>
        </view>

        <view class="ta__today card">
          <view class="ta__section-head">
            <text>{{ courseSectionTitle }}</text>
            <text class="ta__link" @click="go('/pages/teacher/my-schedule/index')">完整课表 ›</text>
          </view>
          <view v-if="nextCourse" class="ta__next-course" @click="openTodayCourse(nextCourse)">
            <view class="ta__next-time">
              <text>第{{ nextCourse.slotNo }}节</text>
              <text>{{ courseClock(nextCourse).start || '时间以课表为准' }}</text>
            </view>
            <view class="flex-1 ta__next-main">
              <view class="ta__course-title-row">
                <text class="ta__next-name">{{ nextCourse.courseName }}</text>
                <text v-if="nextCourse.changeType === 'ADJUST'" class="ta__change-tag">已调课</text>
                <text v-else-if="nextCourse.changeType === 'MAKEUP'" class="ta__change-tag">补课</text>
              </view>
              <text class="ta__course-sub">{{ nextCourse.className || '教学班' }} · {{ nextCourse.classroom || '教室待定' }}</text>
            </view>
            <text class="ta__next-action" :class="{ 'is-disabled': !nextCourse.attendanceRoute }">
              {{ nextCourse.attendanceActionLabel || (nextCourse.attendanceRoute ? '开始点名' : '查看课次') }}
            </text>
          </view>
          <view v-if="remainingTodayCourses.length" class="ta__course-list">
            <view
              v-for="item in remainingTodayCourses"
              :key="item.scheduleItemId || item.itemId || item.courseName + item.slotNo"
              class="ta__course"
              @click="openTodayCourse(item)"
            >
              <text class="ta__course-slot">第{{ item.slotNo }}节</text>
              <view class="flex-1">
                <view class="ta__course-title-row">
                  <text class="ta__course-name">{{ item.courseName }}</text>
                  <text v-if="item.changeType === 'ADJUST'" class="ta__change-tag">已调课</text>
                  <text v-else-if="item.changeType === 'MAKEUP'" class="ta__change-tag">补课</text>
                </view>
                <text class="ta__course-sub">{{ item.className || '教学班' }} · {{ item.classroom || '教室待定' }}</text>
              </view>
              <text class="ta__course-action" :class="{ 'is-disabled': !item.attendanceRoute }">
                {{ item.attendanceActionLabel || (item.attendanceRoute ? '去点名' : '暂不可操作') }}{{ item.attendanceRoute ? ' ›' : '' }}
              </text>
            </view>
          </view>
          <text v-if="!nextCourse" class="ta__empty">{{ todayCourses.length ? '今日课程时段已结束，可从完整课表查看课次。' : todayEmptyText }}</text>
        </view>

        <view class="ta__invigilation card">
          <view class="ta__section-head">
            <text>我的监考</text>
            <text class="ta__section-sub">{{ invigilationSummary }}</text>
          </view>
          <view v-if="invigilationItems.length" class="ta__invig-list">
            <view v-for="item in visibleInvigilations" :key="item.inviglatorId || item.invigilatorId" class="ta__invig-row" @click="openInvigilation(item)">
              <view class="ta__invig-time">
                <text class="ta__invig-date">{{ item.examDate || '日期待定' }}</text>
                <text class="ta__invig-clock">{{ item.startTime || '--:--' }}-{{ item.endTime || '--:--' }}</text>
              </view>
              <view class="flex-1 ta__invig-main">
                <text class="ta__invig-course">{{ item.courseName || '考试课程' }}</text>
                <text class="ta__invig-sub">{{ item.className || '教学班' }} · {{ item.classroom || '考场待定' }}</text>
                <text class="ta__invig-meta">{{ invigilationRoleLabel(item.role) }} · {{ item.confirmStatus === 'CONFIRMED' ? '已确认' : '待确认' }}</text>
              </view>
              <text class="ta__invig-status" :class="{ 'is-finished': item.workStatus === 'FINISHED' }">
                {{ item.workStatus === 'FINISHED' ? '已结束' : '待监考' }}
              </text>
            </view>
            <view v-if="invigilationItems.length > 3" class="ta__invig-toggle" @click="showAllInvigilations = !showAllInvigilations">
              <text>{{ invigilationToggleText }}</text>
            </view>
          </view>
          <text v-else class="ta__empty">近期暂无正式监考任务</text>
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
          <view class="ta__section-head"><text>常用教务</text><text class="ta__section-sub">按当前身份办理</text></view>
          <view class="icon-grid">
            <view v-for="(it, i) in primaryEntries" :key="it.key" class="icon-grid__item" @click="go(it.route)">
              <view class="icon-grid__badge" :class="gradClass(i)">{{ it.icon }}</view>
              <text class="icon-grid__label">{{ it.label }}</text>
              <text v-if="countOf(it.key)" class="ta__badge">{{ countOf(it.key) }}</text>
            </view>
          </view>
          <view class="ta__more-trigger" @click="toggleMoreServices">
            <text>{{ showMoreServices ? '收起其它教务服务' : '其它教务服务' }}</text>
            <text>{{ showMoreServices ? '⌃' : '⌄' }}</text>
          </view>
          <view v-if="showMoreServices" class="ta__more-panel">
            <text v-if="secondaryLoading" class="ta__panel-state">正在加载可用入口…</text>
            <text v-else-if="secondaryError" class="ta__panel-state is-error" @click.stop="loadSecondary">部分入口状态未更新，点击重试</text>
            <view class="icon-grid">
              <view v-for="(it, i) in secondaryEntries" :key="it.key" class="icon-grid__item" @click="go(it.route)">
                <view class="icon-grid__badge" :class="gradClass(i + primaryEntries.length)">{{ it.icon }}</view>
                <text class="icon-grid__label">{{ it.label }}</text>
                <text v-if="countOf(it.key)" class="ta__badge">{{ countOf(it.key) }}</text>
              </view>
            </view>
          </view>
        </view>
        </template>
      </view>
    </MobileGlobalState>
    <MobileTabBar side="teacher" active="workbench" />
  </view>
</template>

<script>
import { teacherApi } from '@/services/teacherApi'
import { normalizeError } from '@/services/request'
import { decodeQueryText, go, toast, back as navigateBack } from '@/utils/nav'
import { getStatusBarHeight } from '@/utils/deviceInfo'
import { useSessionStore } from '@/stores/session'
import { isForbiddenResponse } from './write-result'

const GRAD_CLASSES = ['g1', 'g4', 'g3', 'g5', 'g2', 'g7']
const ENTRIES = [
  { key: 'schedule', label: '我的课表', icon: '📅', route: '/pages/teacher/my-schedule/index', priority: true },
  { key: 'grade', label: '成绩录入', icon: '📊', route: '/pages/teacher/academic-affairs/grade-entry', priority: true },
  { key: 'attendance', label: '课堂考勤', icon: '✅', route: '/pages/teacher/academic-affairs/attendance', priority: true },
  { key: 'academicTask', label: '教学任务', icon: '📚', route: '/pages/teacher/academic-task/index', priority: true },
  { key: 'scheduleChange', label: '调停课', icon: '🔀', route: '/pages/teacher/schedule-change/index', priority: true },
  { key: 'warning', label: '学业预警', icon: '⚠', route: '/pages/teacher/academic-warning/index', priority: true },
  { key: 'scheduleReview', label: '调课审批', icon: '✔️', route: '/pages/teacher/academic-affairs/schedule-change-review' },
  { key: 'statusReview', label: '异动审批', icon: '📋', route: '/pages/teacher/academic-affairs/status-change-review' },
  { key: 'defer', label: '缓考审批', icon: '📝', route: '/pages/teacher/exam-defer/index' },
  { key: 'workload', label: '工作量申报', icon: '🧾', route: '/pages/teacher/academic-affairs/workload' },
  { key: 'evaluation', label: '教学评价', icon: '评', route: '/pages/teacher/evaluation/index' }
]

function listOf(data) {
  if (Array.isArray(data)) return data
  return (data && (data.items || data.list)) || []
}
function isExpectedForbidden(result) {
  return result.status === 'rejected' && normalizeError(result.reason).kind === 'forbidden'
}
function pendingRows(rows, key) {
  const statuses = {
    grade: ['NOT_STARTED', 'INPUTTING', 'RETURNED'],
    academicTask: ['ASSIGNED'],
    scheduleReview: ['SUBMITTED', 'COLLEGE_REVIEW'],
    statusReview: ['SUBMITTED', 'IN_REVIEW'],
    defer: ['COUNSELOR_REVIEW', 'TEACHER_CONFIRM'],
    warning: ['PENDING_HANDLE', 'ACTIVE', 'PROCESSING', 'ESCALATED'],
    attendance: ['DRAFT'],
    scheduleChange: ['SUBMITTED', 'COLLEGE_REVIEW'],
    workload: ['PENDING', 'SUBMITTED']
  }
  const pending = new Set(statuses[key] || [])
  return (rows || []).filter((row) => pending.has(String(row.status || '').toUpperCase()))
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
function teacherContext(session = {}) {
  const identity = session.identity || {}
  const realUser = session.realUser || {}
  const realRole = realUser.currentRole || {}
  return JSON.stringify([
    String(identity.tenantId || realUser.tenantId || ''),
    String(identity.userId || realUser.userId || (realUser.user && (realUser.user.userId || realUser.user.id)) || ''),
    String(session.currentRole || identity.roleCode || realRole.roleCode || realRole.code || ''),
    String(identity.activeContextId || realUser.activeContextId || realRole.contextId || '')
  ])
}

export default {
  data() {
    return {
      statusBarHeight: 20, state: 'loading', partialError: false,
      scheduleItems: [], todayItems: [], currentWeek: null, calendarSource: '',
      timeBands: [], todayDate: '', clockDate: '', clockMinute: 0,
      invigilationWorkbench: { items: [], total: 0, upcomingCount: 0, finishedCount: 0 },
      showAllInvigilations: false, selectedInvigId: '',
      available: Object.fromEntries(ENTRIES.map((entry) => [entry.key, true])), counts: {}, entries: ENTRIES,
      taskTargets: {}, taskDetails: {}, showMoreServices: false,
      secondaryLoaded: false, secondaryLoading: false, secondaryError: false, loadedContext: ''
    }
  },
  computed: {
    selectedInvig() { return this.selectedInvigId ? this.invigilationItems.find((item) => String(item.invigilatorId || item.inviglatorId || '') === this.selectedInvigId) || null : null },
    todayCourses() {
      return (this.todayItems || []).slice().sort((a, b) => Number(a.slotNo || 0) - Number(b.slotNo || 0))
    },
    courseTimesKnown() {
      return !!this.todayCourses.length && this.todayDate === this.clockDate && this.todayCourses.every((item) => this.courseClock(item).endMinute !== null)
    },
    upcomingCourses() {
      return this.courseTimesKnown ? this.todayCourses.filter((item) => this.courseClock(item).endMinute > this.clockMinute) : this.todayCourses
    },
    nextCourse() { return this.upcomingCourses[0] || null },
    remainingTodayCourses() { return this.upcomingCourses.slice(1, 3) },
    courseSectionTitle() {
      if (!this.courseTimesKnown || !this.nextCourse) return '今日课次'
      return this.courseClock(this.nextCourse).startMinute <= this.clockMinute ? '当前课次' : '下一节课'
    },
    invigilationItems() {
      return Array.isArray(this.invigilationWorkbench && this.invigilationWorkbench.items)
        ? this.invigilationWorkbench.items : []
    },
    visibleInvigilations() {
      return this.showAllInvigilations ? this.invigilationItems : this.invigilationItems.slice(0, 3)
    },
    invigilationSummary() {
      const upcoming = Number(this.invigilationWorkbench && this.invigilationWorkbench.upcomingCount || 0)
      const finished = Number(this.invigilationWorkbench && this.invigilationWorkbench.finishedCount || 0)
      if (upcoming && finished) return `${upcoming} 场待监考 · ${finished} 场已结束`
      if (upcoming) return `${upcoming} 场待监考`
      if (finished) return `${finished} 场已结束`
      return '近期无正式安排'
    },
    invigilationToggleText() {
      return this.showAllInvigilations ? '收起' : `查看全部 ${this.invigilationItems.length} 场`
    },
    todaySummary() {
      if (this.calendarSource === 'HOLIDAY') return '今日节假日'
      if (this.calendarSource === 'SWAP_SOURCE') return '今日调休停课'
      if (this.calendarSource === 'OUT_OF_TERM') return '当前非教学期'
      if (this.currentWeek == null) return '周次待确认'
      if (Number(this.currentWeek) === 0) return '学期未开始'
      return this.todayCourses.length ? `${this.todayCourses.length} 门课程` : '今日无课'
    },
    todayEmptyText() {
      if (this.calendarSource === 'HOLIDAY') return '今天是学校校历节假日，没有正式课堂点名任务。'
      if (this.calendarSource === 'SWAP_SOURCE') return '今天是校历调休停课日，正式课程已按调休安排迁移。'
      if (this.calendarSource === 'OUT_OF_TERM') return '当前日期不在本学期教学范围内，可查看完整课表。'
      if (this.currentWeek == null) return '学校校历缺少可用时间轴，暂不判断今日课程。'
      if (Number(this.currentWeek) === 0) return '当前学期尚未开始。'
      return `第${this.currentWeek}周今天暂无正式课程，可查看完整课表安排。`
    },
    primaryEntries() { return this.entries.filter((x) => x.priority && this.available[x.key] !== false) },
    secondaryEntries() { return this.entries.filter((x) => !x.priority && this.available[x.key] !== false) },
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
      const invigilation = Number(this.invigilationWorkbench && this.invigilationWorkbench.upcomingCount || 0)
      if (total && invigilation) return `还有 ${total} 项教务任务 · ${invigilation} 场待监考`
      if (invigilation) return `还有 ${invigilation} 场正式监考安排`
      return total ? `还有 ${total} 项教务任务需要处理` : '当前没有紧急教务待办'
    }
  },
  onLoad() {
    this._pageActive = true
    this.statusBarHeight = getStatusBarHeight()
  },
  onShow() { this.load() },
  onHide() {
    this._pageActive = false
    this.showMoreServices = false
    this.secondaryLoading = false
    this._loadEpoch = (this._loadEpoch || 0) + 1
    this._priorityEpoch = (this._priorityEpoch || 0) + 1
    this._secondaryEpoch = (this._secondaryEpoch || 0) + 1
  },
  onUnload() {
    this._pageActive = false
    this._loadEpoch = (this._loadEpoch || 0) + 1
    this._priorityEpoch = (this._priorityEpoch || 0) + 1
    this._secondaryEpoch = (this._secondaryEpoch || 0) + 1
  },
  onBackPress() { if (!this.selectedInvigId) return false; this.backToTeaching(); return true },
  methods: {
    go,
    openInvigilation(item) { const id = String(item.invigilatorId || item.inviglatorId || ''); if (!id) { toast('安排编号缺失，请刷新'); return }; this.selectedInvigId = id },
    backToTeaching() { if (!this.selectedInvigId) return true; this.selectedInvigId = ''; return false },
    courseClock(item) {
      const ranges = (this.timeBands || []).filter((band) => Number(band.slotNo) === Number(item.slotNo))
      const unique = [...new Set(ranges.map((band) => `${band.startTime}|${band.endTime}`))]
      const band = item.startTime && item.endTime ? item : (unique.length === 1 ? ranges[0] : {})
      const minutes = (value) => {
        const match = /^(\d{1,2}):(\d{2})(?::\d{2})?$/.exec(String(value || ''))
        return match && Number(match[1]) < 24 && Number(match[2]) < 60 ? Number(match[1]) * 60 + Number(match[2]) : null
      }
      const startMinute = minutes(band.startTime)
      const endMinute = minutes(band.endTime)
      return { start: band.startTime || '', startMinute, endMinute: startMinute !== null && endMinute > startMinute ? endMinute : null }
    },
    back() { navigateBack('/pages/teacher/workbench/index') },
    gradClass(i) { return GRAD_CLASSES[i % GRAD_CLASSES.length] },
    countOf(key) { return this.counts[key] || '' },
    invigilationRoleLabel(role) { return String(role || '').toUpperCase() === 'CHIEF' ? '主监考' : '副监考' },
    contextKey() {
      return teacherContext(useSessionStore())
    },
    scheduleLessonRoute(item) {
      const id = String(item && (item.scheduleItemId || item.itemId) || '')
      if (!id) return '/pages/teacher/my-schedule/index'
      const query = [`scheduleItemId=${encodeURIComponent(id)}`]
      if (item.weekNo != null) query.push(`week=${encodeURIComponent(item.weekNo)}`)
      if (item.weekday != null) query.push(`weekday=${encodeURIComponent(item.weekday)}`)
      return `/pages/teacher/my-schedule/index?${query.join('&')}`
    },
    validatedAttendanceRoute(item) {
      const route = String(item && item.attendanceRoute || '')
      const prefix = '/pages/teacher/academic-affairs/attendance?'
      if (!route.startsWith(prefix)) return ''
      const params = {}
      try {
        route.slice(prefix.length).split('&').forEach((part) => {
          const index = part.indexOf('=')
          if (index > 0) params[decodeQueryText(part.slice(0, index))] = decodeQueryText(part.slice(index + 1))
        })
      } catch (_) { return '' }
      if (params.sessionId) return String(params.sessionId) === String(item.attendanceSessionId || '') ? route : ''
      if (!params.teachingTaskId || !params.sessionDate || !params.slotNo || !params.scheduleItemId) return ''
      const exact = String(params.teachingTaskId || '') === String(item.teachingTaskId || '')
        && String(params.sessionDate || '') === String(item.sessionDate || this.todayDate || '')
        && String(params.slotNo || '') === String(item.slotNo || '')
        && String(params.scheduleItemId || '') === String(item.scheduleItemId || item.itemId || '')
      return exact ? route : ''
    },
    clearPrivateHome() {
      this.scheduleItems = []; this.todayItems = []; this.timeBands = []
      this.invigilationWorkbench = { items: [], total: 0, upcomingCount: 0, finishedCount: 0 }
      this.selectedInvigId = ''; this.currentWeek = null; this.calendarSource = ''; this.todayDate = ''
      this.counts = {}; this.taskTargets = {}; this.taskDetails = {}
    },
    openTodayCourse(item) {
      if (!item || !this.todayItems.includes(item)) return
      const attendanceRoute = this.validatedAttendanceRoute(item)
      if (attendanceRoute) return go(item.attendanceRoute)
      if (item.attendanceBlockReason) toast(item.attendanceBlockReason)
      if (item.attendanceRoute) toast('点名链接与当前正式课次不一致，请从课次详情重新进入')
      return go(this.scheduleLessonRoute(item))
    },
    setResult(key, result, pendingOnly = false) {
      if (result.status !== 'fulfilled') {
        if (isExpectedForbidden(result)) this.available[key] = false
        return false
      }
      this.available[key] = true
      const rows = listOf(result.value)
      const pending = pendingOnly ? pendingRows(rows, key) : rows
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
    toggleMoreServices() {
      this.showMoreServices = !this.showMoreServices
      if (this.showMoreServices && !this.secondaryLoaded && !this.secondaryLoading) this.loadSecondary()
    },
    async loadPriority() {
      const epoch = (this._priorityEpoch || 0) + 1
      this._priorityEpoch = epoch
      const context = this.contextKey()
      const results = await Promise.allSettled([
        teacherApi.getGradeTasks(),
        teacherApi.getAcademicMyTasks()
      ])
      if (!this._pageActive || this._priorityEpoch !== epoch || this.contextKey() !== context) return
      this.setResult('grade', results[0], true)
      this.setResult('academicTask', results[1], true)
      this.partialError = this.partialError || results.some((result) => result.status === 'rejected' && !isExpectedForbidden(result))
    },
    async loadSecondary() {
      if (this.secondaryLoading) return
      const epoch = (this._secondaryEpoch || 0) + 1
      this._secondaryEpoch = epoch
      const context = this.contextKey()
      this.secondaryLoading = true
      this.secondaryError = false
      const results = await Promise.allSettled([
        teacherApi.getAttendanceSessions(),
        teacherApi.getAcademicScheduleChanges(),
        teacherApi.getScheduleChangePending(),
        teacherApi.getStatusChangePending(),
        teacherApi.getAcademicDeferPending(),
        teacherApi.getAcademicWarnings(),
        teacherApi.getWorkloadDeclarations()
      ])
      if (!this._pageActive || this._secondaryEpoch !== epoch || this.contextKey() !== context) return
      const keys = ['attendance', 'scheduleChange', 'scheduleReview', 'statusReview', 'defer', 'warning', 'workload']
      keys.forEach((key, index) => this.setResult(key, results[index], true))
      this.secondaryError = results.some((result) => result.status === 'rejected' && !isExpectedForbidden(result))
      this.secondaryLoaded = !this.secondaryError
      this.secondaryLoading = false
    },
    async load() {
      this._pageActive = true
      this._priorityEpoch = (this._priorityEpoch || 0) + 1
      this._secondaryEpoch = (this._secondaryEpoch || 0) + 1
      this.secondaryLoading = false
      this.secondaryLoaded = false
      const epoch = (this._loadEpoch || 0) + 1
      this._loadEpoch = epoch
      const context = this.contextKey()
      const now = new Date()
      this.clockDate = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
      this.clockMinute = now.getHours() * 60 + now.getMinutes()
      if (this.loadedContext !== context) {
        this.clearPrivateHome()
        this.selectedInvigId = ''
        this.available = Object.fromEntries(ENTRIES.map((entry) => [entry.key, true]))
        this.secondaryLoaded = false
        this.secondaryError = false
        this.loadedContext = context
      }
      this.state = 'loading'
      this.partialError = false
      this.counts = {}
      this.taskTargets = {}
      this.taskDetails = {}
      let data
      try {
        data = await teacherApi.getMySchedule()
      } catch (error) {
        if (!this._pageActive || this._loadEpoch !== epoch || this.contextKey() !== context) return
        if (isForbiddenResponse(error)) this.clearPrivateHome()
        this.state = normalizeError(error).pageState || 'error'
        return
      }
      if (!this._pageActive || this._loadEpoch !== epoch || this.contextKey() !== context) return
      const results = [{ status: 'fulfilled', value: data }]
      this.scheduleItems = listOf(results[0].value)
      this.todayItems = (results[0].value && results[0].value.todayItems) || []
      this.timeBands = data.timeBands || []
      this.todayDate = data.todayDate || ''
      this.calendarSource = String((results[0].value && results[0].value.calendarSource) || '')
      this.currentWeek = results[0].value && results[0].value.currentWeek != null ? Number(results[0].value.currentWeek) : null
      this.invigilationWorkbench = (results[0].value && results[0].value.invigilationWorkbench) ||
        { items: [], total: 0, upcomingCount: 0, finishedCount: 0 }
      const scheduleTimeUnknown = this.currentWeek == null && this.calendarSource !== 'OUT_OF_TERM'
      if (this.selectedInvigId && !this.selectedInvig) this.selectedInvigId = ''
      this.partialError = scheduleTimeUnknown
      this.state = 'ready'
      this.loadPriority()
      if (this.showMoreServices) this.loadSecondary()
    }
  }
}
</script>

<style scoped>
.btn.btn-primary { background: var(--teacher-600); border-color: var(--teacher-600); color: #fff; }
.btn.btn-ghost { color: var(--teacher-700); border-color: var(--teacher-200); }
.btn[disabled] { opacity: .5; }
.ta__invig-detail { display: flex; flex-direction: column; gap: 14px; }
.ta__detail-fact { display: flex; justify-content: space-between; gap: 20px; padding: 14px 0; border-bottom: 1px solid var(--border-light); font-size: 14px; }
.ta__detail-fact text:first-child { color: var(--text-tertiary); }
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
.ta__today, .ta__invigilation, .ta__tasks, .ta__services { margin-bottom: var(--space-3); }
.ta__section-head { display: flex; justify-content: space-between; align-items: center; font-weight: 600; }
.ta__link { color: var(--teacher-600); font-size: var(--font-size-xs); font-weight: 400; }
.ta__section-sub { color: var(--text-tertiary); font-size: var(--font-size-xs); font-weight: 400; }
.ta__course-list { margin-top: var(--space-2); }
.ta__next-course { display: flex; align-items: center; gap: var(--space-3); margin-top: var(--space-3); padding: var(--space-3); border-radius: var(--radius-md); background: var(--teacher-50); }
.ta__next-time { width: 72px; flex-shrink: 0; color: var(--teacher-700); font-size: var(--font-size-sm); font-weight: 700; }
.ta__next-time text { display: block; }
.ta__next-time text:last-child { margin-top: 3px; color: var(--text-tertiary); font-size: 10px; font-weight: 400; }
.ta__next-main { min-width: 0; }
.ta__next-name { display: block; min-width: 0; overflow: hidden; color: var(--text-primary); font-weight: 700; text-overflow: ellipsis; white-space: nowrap; }
.ta__next-action { flex-shrink: 0; min-height: 36px; padding: 0 12px; border-radius: var(--radius-md); background: var(--teacher-600); color: #fff; font-size: var(--font-size-xs); font-weight: 600; line-height: 36px; }
.ta__next-action.is-disabled { background: var(--gray-100, #f1f5f9); color: var(--text-tertiary); }
.ta__course { display: flex; align-items: center; gap: var(--space-3); padding: var(--space-2) 0; border-bottom: 1px solid var(--border-light); }
.ta__course:last-child { border-bottom: 0; }
.ta__course-slot { width: 54px; color: var(--teacher-600); font-size: var(--font-size-sm); font-weight: 600; }
.ta__course-title-row { display: flex; align-items: center; gap: 6px; min-width: 0; }
.ta__course-name { display: block; min-width: 0; overflow: hidden; font-weight: 600; text-overflow: ellipsis; white-space: nowrap; }
.ta__change-tag { flex-shrink: 0; padding: 1px 5px; border-radius: 4px; background: var(--teacher-50); color: var(--teacher-600); font-size: 10px; font-weight: 600; }
.ta__course-sub, .ta__empty { display: block; margin-top: 3px; color: var(--text-tertiary); font-size: var(--font-size-xs); }
.ta__course-action { flex-shrink: 0; color: var(--teacher-600); font-size: var(--font-size-xs); font-weight: 600; }
.ta__course-action.is-disabled { color: var(--text-tertiary); }
.ta__empty { padding: var(--space-4) 0 var(--space-2); text-align: center; }
.ta__invig-list { margin-top: var(--space-2); }
.ta__invig-row { display: flex; gap: var(--space-3); align-items: center; padding: var(--space-3) 0; border-bottom: 1px solid var(--border-light); }
.ta__invig-row:last-child { border-bottom: 0; }
.ta__invig-time { width: 86px; flex-shrink: 0; }
.ta__invig-date { display: block; color: var(--teacher-700); font-size: var(--font-size-sm); font-weight: 700; }
.ta__invig-clock { display: block; margin-top: 3px; color: var(--text-tertiary); font-size: 10px; }
.ta__invig-main { min-width: 0; }
.ta__invig-course { display: block; overflow: hidden; font-weight: 600; text-overflow: ellipsis; white-space: nowrap; }
.ta__invig-sub, .ta__invig-meta { display: block; margin-top: 3px; color: var(--text-tertiary); font-size: 10px; }
.ta__invig-status { flex-shrink: 0; padding: 3px 7px; border-radius: 999px; background: var(--teacher-50); color: var(--teacher-700); font-size: 10px; font-weight: 600; }
.ta__invig-status.is-finished { background: var(--gray-100, #f1f5f9); color: var(--text-tertiary); }
.ta__invig-toggle { padding: var(--space-2) 0 0; color: var(--teacher-600); font-size: var(--font-size-xs); text-align: center; }
.ta__task-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: var(--space-2); margin-top: var(--space-3); }
.ta__task { min-width: 0; padding: var(--space-3) var(--space-2); border-radius: var(--radius-md); background: var(--teacher-50); text-align: center; }
.ta__task-value { display: block; color: var(--teacher-600); font-size: 22px; font-weight: 700; }
.ta__task-label { display: block; margin-top: 2px; color: var(--text-secondary); font-size: var(--font-size-xs); }
.ta__task-detail { display: block; margin-top: 3px; overflow: hidden; color: var(--text-tertiary); font-size: 10px; text-overflow: ellipsis; white-space: nowrap; }
.icon-grid__item { position: relative; }
.ta__more-trigger { display: flex; align-items: center; justify-content: space-between; min-height: 44px; margin-top: var(--space-2); padding-top: var(--space-2); border-top: 1px solid var(--border-light); color: var(--teacher-700); font-size: var(--font-size-sm); }
.ta__more-panel { padding-top: var(--space-2); }
.ta__panel-state { display: block; padding: var(--space-3); color: var(--text-tertiary); font-size: var(--font-size-xs); text-align: center; }
.ta__panel-state.is-error { color: var(--warning-700); }
.ta__badge { position: absolute; top: 0; right: 10%; min-width: 17px; height: 17px; padding: 0 4px; border-radius: 9px; background: var(--danger-600); color: #fff; font-size: 10px; line-height: 17px; text-align: center; }
</style>
