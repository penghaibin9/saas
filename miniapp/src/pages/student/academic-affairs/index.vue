<template>
  <view class="page-wrap">
    <AcademicPageNav variant="default" title="我的教务" show-back />

    <AcademicPageState :state="state" @retry="load">
      <view class="page-pad aa__body" v-if="state === 'ready'">
        <view v-if="partialError" class="aa__partial" @click="load">
          <text>{{ failedSources.join('、') || '部分教务数据' }}暂未更新</text><text>点击重试</text>
        </view>

        <text class="aa__date">{{ todayDate || '今日' }}{{ currentWeek ? ' · 第' + currentWeek + '教学周' : '' }}</text>
        <text class="aa__greeting">今天，先安排好课程与待办</text>
        <view class="card aa__today-card">
          <view class="aa__section-head"><text>接下来上什么课</text><text class="aa__link" @click="go('/pages/student/academic-affairs/schedule')">周课表</text></view>
          <view v-for="lesson in todayCourses.slice(0, 3)" :key="lesson.itemId" class="aa__lesson">
            <view class="aa__lesson-time"><text v-if="lesson.startTime">{{ lesson.startTime.slice(0, 5) }}</text><text>第{{ lesson.slotNo || '—' }}节</text></view>
            <view class="flex-1"><text class="aa__task-title">{{ lesson.courseName }}</text><text class="aa__focus-sub">{{ lesson.teacherName || '教师待定' }} · {{ lesson.classroom || '教室待定' }}</text><button class="btn btn-ghost aa__lesson-button" @click="goScheduleDetail(lesson)">课次详情</button></view>
          </view>
          <text v-if="!todayCourses.length" class="aa__focus-empty">{{ todayEmptyText }}</text>
          <text v-if="todayCourses.length > 3" class="aa__link" @click="go('/pages/student/academic-affairs/schedule')">还有 {{ todayCourses.length - 3 }} 节课，查看完整课表</text>
        </view>
        <view class="card aa__tasks">
          <view class="aa__section-head"><text>需要我办理</text><text class="aa__section-sub">以学校当前窗口为准</text></view>
          <view class="aa__task" @click="go('/pages/student/academic-affairs/selection')"><image class="aa__task-icon" :src="academicIcons.selection" mode="aspectFit" /><view class="flex-1"><text class="aa__task-title">网上选课 · {{ selectionSummary }}</text><text class="aa__task-sub">{{ selectionDeadline ? '最早截止：' + selectionDeadline : '办理前核对时间与选课方式' }}</text></view><text class="aa__task-go">查看 ›</text></view>
          <view class="aa__task" @click="go('/pages/student/academic-affairs/registration')"><image class="aa__task-icon" :src="academicIcons.registration" mode="aspectFit" /><view class="flex-1"><text class="aa__task-title">学期注册 · {{ registrationSummary }}</text><text class="aa__task-sub">{{ registrationDeadline ? '最早截止：' + registrationDeadline : '查看批次资格与登记结果' }}</text></view><text class="aa__task-go">查看 ›</text></view>
          <view class="aa__task" @click="go('/pages/student/academic-affairs/exam')"><image class="aa__task-icon" :src="academicIcons.exam" mode="aspectFit" /><view class="flex-1"><text class="aa__task-title">{{ upcomingExam ? '下次考试 · ' + upcomingExam.courseName : examLoaded ? '暂无已发布考试' : '考试安排待核对' }}</text><text v-if="upcomingExam" class="aa__task-sub">{{ upcomingExam.examDate || '日期待定' }} {{ upcomingExam.startTime || '' }} · {{ upcomingExam.classroom || '考场待定' }}</text></view><text class="aa__task-go">查看 ›</text></view>
          <view class="aa__task" @click="go('/pages/student/academic-affairs/warning')"><image class="aa__task-icon" :src="academicIcons.warning" mode="aspectFit" /><view class="flex-1"><text class="aa__task-title">{{ warningCount ? '有 ' + warningCount + ' 条学业预警需关注' : failedSources.includes('学业预警') ? '学业预警暂时无法核对' : priorityState === 'ready' ? '当前暂无待处理学业预警' : '正在核对学业预警…' }}</text><text v-if="warningCount" class="aa__task-sub">{{ taskDetails.warning || '查看原因与后续处理要求' }}</text></view><text class="aa__task-go">查看 ›</text></view>
          <view v-for="task in secondaryTaskCues" :key="task.key" class="aa__task" @click="go(task.route)"><image class="aa__task-icon" :src="task.icon" mode="aspectFit" /><view class="flex-1"><text class="aa__task-title">{{ task.title }}</text><text class="aa__task-sub">{{ task.description }}</text></view><text class="aa__task-go">办理 ›</text></view>
        </view>

        <view class="card aa__section">
          <view class="aa__section-head"><text>常用服务</text><text class="aa__section-sub">高频事项优先</text></view>
          <view class="icon-grid">
            <view v-for="(it, i) in commonEntries" :key="it.key" class="icon-grid__item" @click="go(it.route)">
              <view class="icon-grid__badge" :class="gradClass(i)"><image class="aa__service-icon" :src="it.icon" mode="aspectFit" /></view>
              <text class="icon-grid__label">{{ it.label }}</text>
              <text v-if="badgeOf(it.key)" class="aa__badge">{{ badgeOf(it.key) }}</text>
            </view>
          </view>
        </view>

        <view class="card aa__section">
          <view class="aa__section-head" @click="toggleAll">
            <text>全部教务服务</text><text class="aa__link">{{ showAll ? '收起' : `${otherEntries.length}项 ›` }}</text>
          </view>
          <view v-if="showAll && secondaryState === 'loading'" class="aa__secondary-state"><text>正在加载评教、缓考和补考待办…</text></view>
          <view v-if="showAll" class="icon-grid aa__all-grid">
            <view v-for="(it, i) in otherEntries" :key="it.key" class="icon-grid__item" @click="go(it.route)">
              <view class="icon-grid__badge" :class="gradClass(i + commonEntries.length)"><image class="aa__service-icon" :src="it.icon" mode="aspectFit" /></view>
              <text class="icon-grid__label">{{ it.label }}</text>
              <text v-if="badgeOf(it.key)" class="aa__badge">{{ badgeOf(it.key) }}</text>
            </view>
          </view>
        </view>
      </view>
    </AcademicPageState>
    <MobileTabBar side="student" active="" />
  </view>
</template>

<script>
import AcademicPageNav from './AcademicPageNav.vue'
import AcademicPageState from './AcademicPageState.vue'
import { studentApi } from '@/services/studentApi'
import { go } from '@/utils/nav'
import { academicIcons } from './academic-icons'
import { getStatusBarHeight } from '@/utils/deviceInfo'
import { currentSessionGeneration } from '@/services/sessionGeneration.mjs'

const ST = { REGISTERED: '在籍注册', NORMAL: '在籍', SUSPENDED: '休学中', RETAINED: '留级',
  WITHDRAWN: '已退学', GRADUATED: '已毕业', COMPLETED: '已结业', PENDING_REGISTER: '待注册' }
const GRAD_CLASSES = ['g1', 'g4', 'g3', 'g5', 'g2', 'g7', 'g6', 'g8']
const ENTRIES = [
  { key: 'schedule', label: '我的课表', icon: academicIcons.schedule, route: '/pages/student/academic-affairs/schedule' },
  { key: 'selection', label: '网上选课', icon: academicIcons.selection, route: '/pages/student/academic-affairs/selection' },
  { key: 'transcript', label: '我的成绩', icon: academicIcons.transcript, route: '/pages/student/academic-affairs/transcript' },
  { key: 'exam', label: '考试/缓考', icon: academicIcons.exam, route: '/pages/student/academic-affairs/exam' },
  { key: 'credits', label: '学分修读', icon: academicIcons.credits, route: '/pages/student/academic-affairs/credits' },
  { key: 'status', label: '学籍与异动', icon: academicIcons.status, route: '/pages/student/academic-affairs/status' },
  { key: 'graduation', label: '毕业进度', icon: academicIcons.graduation, route: '/pages/student/academic-affairs/graduation' },
  { key: 'registration', label: '学期注册', icon: academicIcons.registration, route: '/pages/student/academic-affairs/registration' },
  { key: 'warning', label: '学业预警', icon: academicIcons.warning, route: '/pages/student/academic-affairs/warning' },
  { key: 'makeup', label: '补考重修', icon: academicIcons.makeup, route: '/pages/student/academic-affairs/makeup' },
  { key: 'recognition', label: '成绩认定', icon: academicIcons.recognition, route: '/pages/student/academic-affairs/recognition' },
  { key: 'recheck', label: '成绩复查', icon: academicIcons.recheck, route: '/pages/student/academic-affairs/recheck' },
  { key: 'textbook', label: '我的教材', icon: academicIcons.textbook, route: '/pages/student/academic-affairs/textbook' },
  { key: 'levelExam', label: '等级考试', icon: academicIcons.levelExam, route: '/pages/student/academic-affairs/level-exam' },
  { key: 'majorSplit', label: '专业分流', icon: academicIcons.majorSplit, route: '/pages/student/academic-affairs/major-split' },
  { key: 'attendance', label: '我的考勤', icon: academicIcons.attendance, route: '/pages/student/academic-affairs/attendance' },
  { key: 'calendar', label: '校历', icon: academicIcons.calendar, route: '/pages/student/academic-affairs/calendar' },
  { key: 'clearance', label: '清考结果', icon: academicIcons.clearance, route: '/pages/student/academic-affairs/clearance' },
  { key: 'evaluation', label: '学生评教', icon: academicIcons.evaluation, route: '/pages/student/academic-affairs/evaluation' }
]
const COMMON_KEYS = new Set(['schedule', 'selection', 'transcript', 'exam', 'textbook', 'warning', 'graduation', 'registration'])

function isObject(data) { return !!data && typeof data === 'object' && !Array.isArray(data) }
function rowsOf(data, keys = ['items', 'list', 'batches']) {
  if (Array.isArray(data)) return data
  if (!isObject(data)) return null
  for (const key of keys) if (Array.isArray(data[key])) return data[key]
  return null
}
function localDateKey(date) {
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}
function unfinished(rows) {
  const done = new Set(['DONE', 'COMPLETED', 'APPROVED', 'REGISTERED', 'SUBMITTED', 'PUBLISHED', 'CLOSED'])
  return (rows || []).filter((row) => !done.has(String(row.status || row.registrationStatus || '').toUpperCase()))
}
function pendingEvaluationCount(data) {
  if (data && Number.isFinite(Number(data.pending))) return Number(data.pending)
  return (rowsOf(data, ['list', 'items']) || []).filter((row) => row && row.canSubmit === true && row.submitted !== true).length
}
function taskTarget(key, row) {
  if (!row) return ''
  const base = {
    registration: '/pages/student/academic-affairs/registration',
    evaluation: '/pages/student/academic-affairs/evaluation',
    warning: '/pages/student/academic-affairs/warning',
    defer: '/pages/student/academic-affairs/exam',
    makeup: '/pages/student/academic-affairs/makeup'
  }[key]
  const id = {
    registration: row.batchId,
    evaluation: row.taskId,
    warning: row.warningId || row.id,
    defer: row.deferId || row.id,
    makeup: row.gradeId || row.sourceId || row.acadGradeId || row.id
  }[key]
  return base && id ? `${base}?id=${encodeURIComponent(id)}` : (base || '')
}
function taskDetail(key, row) {
  if (!row) return ''
  if (key === 'registration') return row.batchName || '完成开放批次注册'
  if (key === 'evaluation') return `${row.courseName || '课程'} · ${row.teacherName || '授课教师'}`
  if (key === 'warning') return row.reason || row.warningName || '查看原因与处理要求'
  if (key === 'defer') return `${row.courseName || '缓考申请'} · ${row.returnReason || row.reviewNote || '退回待补充'}`
  if (key === 'makeup') return `${row.courseName || '未通过课程'} · 可报名重修`
  return ''
}

export default {
  components: { AcademicPageNav, AcademicPageState },
  data() {
    return {
      status: null, state: 'loading', statusBarHeight: 20, entries: ENTRIES, academicIcons, todayDate: '', selectionDeadline: '',
      scheduleItems: [], todayItems: [], currentWeek: null, calendarSource: '', examItems: [], examLoaded: false,
      warningCount: 0, evaluationCount: 0, registrationCount: 0, returnedDeferCount: 0,
      retakeCount: 0, partialError: false, failedSources: [], showAll: false,
      taskTargets: {}, taskDetails: {}, priorityState: 'idle', secondaryState: 'idle',
      selectionCanEnroll: false, selectionOpen: false, requestEpoch: 0, hidden: false,
      registrationBatches: [], registrationTotal: null, registrationNextDeadline: '', registrationNextBatchId: '', scheduleLoaded: false, identity: currentSessionGeneration()
    }
  },
  computed: {
    secondaryTaskCues() { return this.taskCues.filter(task => !['registration', 'warning'].includes(task.key)) },
    registrationDeadline() {
      const next = String(this.registrationNextDeadline || '')
      if (next) return next.replace('T', ' ').slice(0, 16)
      return this.registrationBatches.filter(batch => batch.registrationStatus !== 'REGISTERED').map(batch => String(batch.windowEnd || '')).filter(Boolean).sort()[0]?.replace('T', ' ').slice(0, 16) || ''
    },
    commonEntries() { return this.entries.filter((x) => COMMON_KEYS.has(x.key)) },
    otherEntries() { return this.entries.filter((x) => !COMMON_KEYS.has(x.key)) },
    taskCues() {
      return [
        { key: 'registration', icon: academicIcons.registration, title: '完成学期注册', description: this.taskDetails.registration || '存在尚未完成的注册批次', count: this.registrationCount, route: this.taskTargets.registration || '/pages/student/academic-affairs/registration' },
        { key: 'evaluation', icon: academicIcons.evaluation, title: '完成学生评教', description: this.taskDetails.evaluation || '开放窗口内课程等待匿名评价', count: this.evaluationCount, route: this.taskTargets.evaluation || '/pages/student/academic-affairs/evaluation' },
        { key: 'warning', icon: academicIcons.warning, title: '跟进学业预警', description: this.taskDetails.warning || '查看原因、责任老师和处理要求', count: this.warningCount, route: this.taskTargets.warning || '/pages/student/academic-affairs/warning' },
        { key: 'defer', icon: academicIcons.defer, title: '补充缓考材料', description: this.taskDetails.defer || '存在退回待重新提交的缓考申请', count: this.returnedDeferCount, route: this.taskTargets.defer || '/pages/student/academic-affairs/exam' },
        { key: 'makeup', icon: academicIcons.makeup, title: '处理补考重修', description: this.taskDetails.makeup || '存在可报名的当前有效未通过课程', count: this.retakeCount, route: this.taskTargets.makeup || '/pages/student/academic-affairs/makeup' }
      ].filter((item) => Number(item.count || 0) > 0)
    },
    todayCourses() {
      return this.todayItems
    },
    todayEmptyText() {
      if (!this.scheduleLoaded) return '今日课表暂时无法核对'
      if (this.calendarSource === 'HOLIDAY') return '今天是学校校历节假日'
      if (this.calendarSource === 'SWAP_SOURCE') return '今天是调休停课日'
      if (this.calendarSource === 'OUT_OF_TERM') return '今天不在当前学期教学日期范围内'
      return this.currentWeek ? `第${this.currentWeek}周今天暂无课程` : '今天没有课程安排'
    },
    upcomingExam() {
      const today = localDateKey(new Date())
      return this.examItems.filter((x) => !x.examDate || x.examDate >= today)
        .sort((a, b) => String(a.examDate || '9999').localeCompare(String(b.examDate || '9999')))[0] || null
    },
    registrationSummary() {
      if (this.priorityState === 'loading' || this.priorityState === 'idle') return '核对中'
      if (this.failedSources.includes('学期注册')) return '暂时无法核对'
      if (Number.isSafeInteger(this.registrationTotal)) {
        if (this.registrationTotal === 0) return '暂无注册批次'
        return this.registrationCount ? `${this.registrationCount} 项待完成` : '当前暂无待办理'
      }
      if (!this.registrationBatches.length) return '暂无注册批次'
      if (this.registrationBatches.every((batch) => batch.registrationStatus === 'REGISTERED')) return '当前已完成'
      return this.registrationCount ? `${this.registrationCount} 项待完成` : '查看办理状态'
    },
    selectionSummary() {
      if (this.priorityState === 'loading' || this.priorityState === 'idle') return '核对中'
      if (this.failedSources.includes('网上选课')) return '暂时无法核对'
      if (this.selectionCanEnroll) return '当前可办理'
      return this.selectionOpen ? '有开放批次' : '当前未开放'
    }
  },
  onLoad() {
    this.statusBarHeight = getStatusBarHeight()
    this.load()
  },
  onShow() { if (this.hidden) { this.hidden = false; this.load() } },
  onHide() { this.hidden = true; this.requestEpoch += 1 },
  onUnload() { this.hidden = true; this.requestEpoch += 1 },
  methods: {
    go,
    goScheduleDetail(lesson) {
      const query = [`id=${encodeURIComponent(lesson && lesson.itemId || '')}`]
      if (Number.isInteger(Number(lesson && lesson.weekday))) query.push(`day=${Number(lesson.weekday)}`)
      if (Number.isInteger(Number(this.currentWeek)) && Number(this.currentWeek) > 0) query.push(`week=${Number(this.currentWeek)}`)
      go('/pages/student/academic-affairs/schedule?' + query.join('&'))
    },
    back() { uni.navigateBack({ delta: 1, fail: () => go('/pages/student/home/index') }) },
    gradClass(i) { return GRAD_CLASSES[i % GRAD_CLASSES.length] },
    statusText(s) { return ST[s] || '状态待学校核对' },
    badgeOf(key) {
      if (key === 'warning') return this.warningCount || ''
      if (key === 'evaluation') return this.evaluationCount || ''
      if (key === 'registration') return this.registrationCount || ''
      if (key === 'makeup') return this.retakeCount || ''
      return ''
    },
    addFailedSource(name) {
      if (!this.failedSources.includes(name)) this.failedSources = [...this.failedSources, name]
      this.partialError = true
    },
    applyTask(key, row) {
      const target = taskTarget(key, row)
      const detail = taskDetail(key, row)
      if (target) this.taskTargets = { ...this.taskTargets, [key]: target }
      if (detail) this.taskDetails = { ...this.taskDetails, [key]: detail }
    },
    toggleAll() {
      this.showAll = !this.showAll
      if (this.showAll && this.secondaryState === 'idle') this.loadSecondary(this.requestEpoch)
    },
    async load() {
      const epoch = ++this.requestEpoch
      this.identity = currentSessionGeneration()
      this.state = 'loading'
      this.status = null; this.todayItems = []; this.scheduleItems = []; this.examItems = []
      this.warningCount = 0; this.registrationCount = 0; this.evaluationCount = 0; this.returnedDeferCount = 0; this.retakeCount = 0
      this.registrationBatches = []; this.registrationTotal = null; this.registrationNextDeadline = ''; this.registrationNextBatchId = ''; this.scheduleLoaded = false
      this.todayDate = ''; this.selectionDeadline = ''
      this.partialError = false
      this.failedSources = []
      this.taskTargets = {}
      this.taskDetails = {}
      this.priorityState = 'idle'
      this.secondaryState = 'idle'
      this.examLoaded = false
      this.selectionCanEnroll = false
      this.selectionOpen = false
      const core = await Promise.allSettled([studentApi.getMyAcadStatus(), studentApi.getMySchedule()])
      if (epoch !== this.requestEpoch || this.hidden || this.identity !== currentSessionGeneration()) return
      if (core[0].status !== 'fulfilled' || !isObject(core[0].value)) {
        const error = core[0].reason || {}
        if (Number(error?.httpStatus) === 403 || /^403/.test(String(error?.code || ''))) {
          this.state = 'forbidden'
          return
        }
        this.addFailedSource('学籍信息')
      } else {
        this.status = core[0].value
      }
      const schedule = core[1].status === 'fulfilled' ? core[1].value : null
      if (isObject(schedule) && Array.isArray(schedule.items) && Array.isArray(schedule.todayItems)) {
        this.scheduleLoaded = true
        this.scheduleItems = schedule.items
        const bands = Array.isArray(schedule.timeBands) ? schedule.timeBands : []
        this.todayItems = (schedule.todayItems || []).map(item => ({ ...item, startTime: item.startTime || bands.find(band => String(band.slotNo) === String(item.slotNo))?.startTime || '' }))
        this.todayDate = schedule.todayDate || ''
        this.currentWeek = schedule.currentWeek != null ? Number(schedule.currentWeek) : null
        this.calendarSource = schedule.calendarSource || ''
      } else {
        this.scheduleItems = []
        this.todayItems = []
        this.currentWeek = null
        this.calendarSource = ''
        this.addFailedSource('课表')
      }
      this.state = 'ready'
      await this.loadPriority(epoch)
      if (epoch === this.requestEpoch && this.showAll) this.loadSecondary(epoch)
    },
    async loadPriority(epoch) {
      this.priorityState = 'loading'
      const results = await Promise.allSettled([
        studentApi.getMyExamSchedule(), studentApi.getMyWarnings(),
        studentApi.getMyRegistration({ page: 1, pageSize: 20 }), studentApi.getSelectionBatches({ page: 1, pageSize: 20 })
      ])
      if (epoch !== this.requestEpoch || this.hidden || this.identity !== currentSessionGeneration()) return
      const examRows = results[0].status === 'fulfilled' ? rowsOf(results[0].value, ['items', 'list']) : null
      const warningRowsRaw = results[1].status === 'fulfilled' ? rowsOf(results[1].value, ['items']) : null
      const registrationPayload = results[2].status === 'fulfilled' ? results[2].value : null
      const registrationRowsRaw = results[2].status === 'fulfilled' ? rowsOf(registrationPayload, ['batches']) : null
      const selectionPayload = results[3].status === 'fulfilled' ? results[3].value : null
      const selectionBatches = rowsOf(selectionPayload, ['items'])
      this.examLoaded = Array.isArray(examRows)
      this.examItems = examRows || []
      const warningRows = unfinished(warningRowsRaw || [])
      this.registrationBatches = registrationRowsRaw || []
      const registrationRows = this.registrationBatches.filter((row) => row.registrationStatus !== 'REGISTERED' && (row.canRegister === true || row.canDefer === true))
      this.warningCount = warningRows.length
      const registrationTotal = Number(registrationPayload?.total)
      const actionableTotal = Number(registrationPayload?.actionableTotal)
      this.registrationTotal = Number.isSafeInteger(registrationTotal) && registrationTotal >= 0 ? registrationTotal : null
      this.registrationCount = Number.isSafeInteger(actionableTotal) && actionableTotal >= 0 ? actionableTotal : registrationRows.length
      this.registrationNextDeadline = registrationPayload?.nextActionDeadline || ''
      this.registrationNextBatchId = registrationPayload?.nextActionBatchId || ''
      this.applyTask('registration', this.registrationNextBatchId ? { batchId: this.registrationNextBatchId } : registrationRows[0])
      this.applyTask('warning', warningRows[0])
      const validSelectionBatches = Array.isArray(selectionBatches)
      if (validSelectionBatches) {
        this.selectionDeadline = selectionBatches.map(batch => String(batch.selectEndAt || '')).filter(Boolean).sort()[0]?.replace('T', ' ').slice(0, 16) || ''
        // The home page deliberately reads only a bounded batch catalog.  Actual
        // eligibility and ENROLL actions are confirmed on the selected course page.
        this.selectionCanEnroll = false
        this.selectionOpen = selectionBatches.some((batch) => String(batch && batch.status || '').toUpperCase() === 'OPEN')
      }
      ;[['考试', examRows], ['学业预警', warningRowsRaw], ['学期注册', registrationRowsRaw], ['网上选课', validSelectionBatches ? selectionBatches : null]].forEach(([name, rows]) => {
        if (!Array.isArray(rows)) this.addFailedSource(name)
      })
      this.priorityState = 'ready'
    },
    async loadSecondary(epoch) {
      if (this.secondaryState === 'loading' || this.secondaryState === 'ready') return
      this.secondaryState = 'loading'
      const results = await Promise.allSettled([
        studentApi.getMyEvaluationTasks({ page: 1, pageSize: 20 }),
        studentApi.getMyDeferrals({ status: 'RETURNED', page: 1, pageSize: 20 }),
        studentApi.getMakeupOptions({ page: 1, pageSize: 1 })
      ])
      if (epoch !== this.requestEpoch || this.hidden || this.identity !== currentSessionGeneration()) return
      const evaluationRowsRaw = results[0].status === 'fulfilled' ? rowsOf(results[0].value, ['list', 'items']) : null
      const deferRowsRaw = results[1].status === 'fulfilled' ? rowsOf(results[1].value, ['items', 'list']) : null
      const makeupPayload = results[2].status === 'fulfilled' ? results[2].value : null
      const makeup = isObject(makeupPayload) && Array.isArray(makeupPayload.retakeOptions) ? makeupPayload : null
      const evaluationRows = (evaluationRowsRaw || []).filter((row) => row && row.canSubmit === true && row.submitted !== true)
      const deferRows = (deferRowsRaw || []).filter((row) => String(row.status || '').toUpperCase() === 'RETURNED')
      this.evaluationCount = evaluationRowsRaw ? Number(pendingEvaluationCount(results[0].value)) : 0
      const deferTotal = Number(results[1].status === 'fulfilled' && results[1].value && results[1].value.total)
      this.returnedDeferCount = deferRowsRaw ? (Number.isSafeInteger(deferTotal) && deferTotal >= 0 ? deferTotal : deferRows.length) : 0
      this.retakeCount = makeup ? Number(makeup.retakeTotal ?? makeup.retakeOptions.length) : 0
      const nextPendingTaskId = results[0].status === 'fulfilled' && results[0].value && results[0].value.nextPendingTaskId
      this.applyTask('evaluation', nextPendingTaskId ? { taskId: String(nextPendingTaskId) } : evaluationRows[0])
      this.applyTask('defer', deferRows[0])
      this.applyTask('makeup', makeup && makeup.retakeOptions[0])
      ;[['学生评教', evaluationRowsRaw], ['缓考申请', deferRowsRaw], ['补考重修资格', makeup && makeup.retakeOptions]].forEach(([name, rows]) => {
        if (!Array.isArray(rows)) this.addFailedSource(name)
      })
      this.secondaryState = 'ready'
    }
  }
}
</script>

<style scoped>
.aa__date { display:block; color:var(--text-secondary); font-size:12px; margin:8px 0; }
.aa__greeting { display:block; font-size:21px; font-weight:700; color:var(--text-primary); margin-bottom:16px; }
.aa__today-card { margin-bottom:14px; }
.aa__lesson { display:flex; gap:16px; padding:14px 0; border-top:1px solid var(--border-light); }
.aa__lesson-time { width:48px; flex-shrink:0; font-size:14px; color:var(--brand-primary); font-weight:600; }
.aa__lesson-time text { display:block; margin-bottom:4px; }
.aa__lesson-button { margin:10px 0 0; min-height:40px; font-size:12px; }
.aa__service-icon { width: 24px; height: 24px; }
.aa__task-icon { width: 24px; height: 24px; flex-shrink: 0; }
.icon-grid__badge { background: var(--brand-50, #edf3fc); }
.page-wrap { font-family: -apple-system, BlinkMacSystemFont, "Microsoft YaHei", sans-serif; padding-bottom: calc(64px + env(safe-area-inset-bottom)); }
button, input, textarea { font-family: inherit; }
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
.aa__task { display: flex; align-items: center; gap: 12px; padding: 14px 0; border-top:1px solid var(--border-light); }
.aa__task-icon { display: grid; place-items: center; width: 32px; height: 32px; border-radius: var(--radius-sm); background: var(--brand-50); }
.aa__task-title { display: block; color: var(--text-primary); font-size: var(--font-size-sm); font-weight: 600; }
.aa__task-sub { display: block; margin-top: 4px; color: var(--text-secondary); font-size: 12px; line-height:1.6; }
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
.aa__secondary-state { margin-bottom: var(--space-2); color: var(--text-tertiary); font-size: var(--font-size-xs); }
</style>
