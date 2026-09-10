<template>
  <view class="page-wrap">
    <AcademicPageNav variant="default" title="我的课表" :subtitle="termCode || '当前学期'" show-back />
    <AcademicPageState :state="state" @retry="load">
      <view class="page-pad" v-if="items">
        <view class="sc__today">
          <view class="sc__today-head">
            <view>
              <text class="sc__today-kicker">今天 · {{ todayDateText }}</text>
              <text class="sc__today-title">{{ todayItems.length ? `今天有 ${todayItems.length} 节课` : '今天没有课程安排' }}</text>
              <text class="sc__today-note">{{ todayNote }}</text>
            </view>
            <text v-if="todayWeek" class="sc__today-week">第{{ todayWeek }}教学周</text>
          </view>
          <view v-if="todayItems.length" class="sc__today-list">
            <view v-for="item in todayItems" :key="`today-${item.itemId}`" class="sc__today-item" @click="toggleDetail(item)">
              <view class="sc__today-time">
                <text>第{{ item.slotNo }}节</text>
                <text v-if="slotTime(item)">{{ slotTime(item) }}</text>
              </view>
              <view class="flex-1">
                <text class="sc__course">{{ item.courseName }}</text>
                <text class="sc__meta">{{ item.classroom || '教室待定' }} · {{ item.teacherName || '教师待定' }}</text>
                <view v-if="detailId === String(item.itemId)" class="sc__detail">
                  <text>{{ parity(item) }}</text>
                  <text>{{ item.courseCode || '课程代码待确认' }} · {{ item.source === 'ENROLLED' ? '本人选课记录' : '培养计划课表' }}</text>
                  <text>上课安排以学校最新正式课表与校历为准</text>
                  <button class="btn btn-ghost" @click.stop="goAttendance(item)">查看本人考勤</button>
                </view>
              </view>
              <text v-if="item.source === 'ENROLLED'" class="sc__source">选课课程</text>
            </view>
          </view>
          <view v-else class="sc__today-empty"><text>{{ todayEmptyText }}</text></view>
        </view>
        <view class="sc__week card">
          <view>
            <text class="sc__week-title">{{ currentWeekText }}</text>
            <text class="sc__week-sub">按周查看会自动处理起止周和单双周</text>
          </view>
          <picker mode="selector" :range="weekLabels" :value="selectedWeek" @change="onWeekChange">
            <view class="sc__week-picker">{{ weekLabels[selectedWeek] || '全部周次' }}⌄</view>
          </picker>
        </view>
        <view class="sc__week card sc__day-filter">
          <view>
            <text class="sc__week-title">上课日</text>
            <text class="sc__week-sub">按天收窄课次，方便核对详情</text>
          </view>
          <picker mode="selector" :range="dayLabels" :value="selectedDay" @change="onDayChange">
            <view class="sc__week-picker">{{ dayLabels[selectedDay] || '全部日期' }}⌄</view>
          </picker>
        </view>
        <view class="sc__actions">
          <button class="sc__copy" :disabled="copying" @click="copySummary">
            {{ copying ? '复制中…' : '复制当前视图摘要' }}
          </button>
          <text class="sc__hint">正式打印请在学生PC端生成带水印文件</text>
        </view>
        <view class="sc__empty" v-if="!filteredItems.length"><text>{{ emptyText }}</text></view>
        <view v-for="dayGroup in grouped" :key="dayGroup.day" class="sc__day">
          <text class="sc__day-t">{{ WEEK[dayGroup.day] }}</text>
          <view v-for="item in dayGroup.list" :key="item.itemId" class="sc__item" @click="toggleDetail(item)">
            <view class="sc__slot"><text>第{{ item.slotNo }}节</text><text v-if="slotTime(item)" class="sc__time">{{ slotTime(item) }}</text></view>
            <view class="sc__main">
              <text class="sc__course">{{ item.courseName }}</text>
              <text class="sc__meta">{{ item.classroom || '教室待定' }} · {{ item.teacherName || '教师待定' }} · {{ parity(item) }}</text>
              <text v-if="item.source === 'ENROLLED'" class="sc__source">选课课程</text>
              <view v-if="detailId === String(item.itemId)" class="sc__detail">
                <text>{{ item.courseCode || '课程代码待确认' }}</text>
                <text>第{{ item.startWeek || 1 }}–{{ item.endWeek || item.startWeek || 1 }}周 · {{ slotTime(item) || '作息时间待确认' }}</text>
                <text v-if="item.teachingClassName">教学班：{{ item.teachingClassName }}</text>
                <text v-if="item.changeType">已生效调整：{{ changeText(item.changeType) }}</text>
                <button class="btn btn-ghost" @click.stop="goAttendance(item)">查看本人考勤</button>
              </view>
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
import { safeToast } from '@/services/request'
import { currentSessionGeneration } from '@/services/sessionGeneration.mjs'
import { go } from '@/utils/nav'

const WEEK = { 1: '周一', 2: '周二', 3: '周三', 4: '周四', 5: '周五', 6: '周六', 7: '周日' }

function activeInWeek(item, week) {
  if (!week) return true
  const start = Number(item.startWeek || 1)
  const end = Number(item.endWeek || start)
  if (week < start || week > end) return false
  const parity = String(item.weekParity || 'ALL').toUpperCase()
  if (parity === 'ODD') return week % 2 === 1
  if (parity === 'EVEN') return week % 2 === 0
  return true
}

function firstActiveWeek(item) {
  const start = Math.max(1, Number(item && item.startWeek || 1))
  const end = Math.max(start, Number(item && item.endWeek || start))
  for (let week = start; week <= end; week += 1) if (activeInWeek(item, week)) return week
  return 0
}

function safeRouteNumber(value, max) {
  const number = Number(value)
  return Number.isInteger(number) && number >= 1 && number <= max ? number : 0
}

function timeRange(band) {
  const start = String((band && band.startTime) || '').trim()
  const end = String((band && band.endTime) || '').trim()
  return start && end ? `${start}-${end}` : (start || end)
}

export default {
  components: { AcademicPageNav, AcademicPageState },
  data() {
    return {
      items: null, state: 'loading', WEEK, copying: false,
      currentWeek: null, teachingWeeks: null, selectedWeek: 0, selectedDay: 0, termCode: '',
      todayItems: [], todayDate: '', todayWeek: null, calendarSource: '', timeBands: [],
      detailId: '', targetWeek: 0, targetDay: 0, routeContextApplied: false, requestEpoch: 0, hidden: false, identity: currentSessionGeneration(), loadedOnce: false
    }
  },
  onLoad(options = {}) {
    this.detailId = String(options.id || '')
    this.targetWeek = safeRouteNumber(options.week, 99)
    this.targetDay = safeRouteNumber(options.day, 7)
  },
  onShow() { this.load() },
  onHide() { this.hidden = true; this.requestEpoch += 1; this.copying = false },
  onUnload() { this.hidden = true; this.requestEpoch += 1; this.copying = false },
  computed: {
    maxWeek() {
      const itemMax = Math.max(1, ...(this.items || []).map((item) => Number(item.endWeek || 1)))
      return Math.max(1, Number(this.teachingWeeks || 0), itemMax)
    },
    weekLabels() {
      return ['全部周次', ...Array.from({ length: this.maxWeek }, (_, index) => `第${index + 1}周`)]
    },
    dayLabels() { return ['全部日期', ...Object.keys(WEEK).map((day) => WEEK[day])] },
    filteredItems() {
      return (this.items || []).filter((item) => activeInWeek(item, this.selectedWeek)
        && (!this.selectedDay || Number(item.weekday) === this.selectedDay))
    },
    grouped() {
      const map = {}
      this.filteredItems.forEach((item) => { (map[item.weekday] = map[item.weekday] || []).push(item) })
      return Object.keys(map).sort().map((day) => ({
        day, list: map[day].sort((a, b) => Number(a.slotNo || 0) - Number(b.slotNo || 0))
      }))
    },
    currentWeekText() {
      if (this.currentWeek == null) return '当前周次待校历确认'
      if (Number(this.currentWeek) === 0) return '当前学期尚未开始'
      return `当前第${this.currentWeek}周`
    },
    todayDateText() {
      const parts = String(this.todayDate || '').split('-').map(Number)
      if (parts.length !== 3 || parts.some((value) => !value)) return '日期待确认'
      return `${parts[1]}月${parts[2]}日`
    },
    todayNote() {
      if (this.calendarSource === 'HOLIDAY') return '学校校历标记今天为节假日，正式课表不执行。'
      if (this.calendarSource === 'SWAP_SOURCE') return '学校校历标记今天为调休停课日，正式课表不执行。'
      if (this.calendarSource === 'OUT_OF_TERM') return '今天不在当前学期教学日期范围内。'
      return this.todayItems.length ? '已按学校校历、单双周和最新正式课表筛选。' : '已核对学校校历和最新正式课表。'
    },
    todayEmptyText() {
      return this.items.length ? this.todayNote : '当前学期暂无已发布课表'
    },
    emptyText() {
      const scope = [this.selectedWeek ? `第${this.selectedWeek}周` : '', this.selectedDay ? WEEK[this.selectedDay] : ''].filter(Boolean).join(' · ')
      return scope ? `${scope}暂无课程` : '暂无已发布课表'
    }
  },
  methods: {
    changeText(value) { return { ROOM: '教室调整', TEACHER: '教师调整', TIME: '时间调整', CANCEL: '停课', SWAP: '调课' }[value] || '请核对学校最新安排' },
    goAttendance(item) { go('/pages/student/academic-affairs/attendance?course=' + encodeURIComponent(item.courseName || '')) },
    parity(item) {
      const value = item.weekParity === 'ODD' ? '单周' : item.weekParity === 'EVEN' ? '双周' : '全周'
      return item.startWeek && item.endWeek ? `${item.startWeek}-${item.endWeek}周·${value}` : '周次范围待确认'
    },
    slotTime(item) {
      const ranges = [...new Set((this.timeBands || [])
        .filter((band) => Number(band.slotNo) === Number(item.slotNo))
        .map(timeRange).filter(Boolean))]
      if (ranges.length === 1) return ranges[0]
      if (ranges.length > 1) return '按校区作息'
      return ''
    },
    onWeekChange(event) { this.selectedWeek = Number(event.detail.value) || 0 },
    onDayChange(event) { this.selectedDay = Number(event.detail.value) || 0 },
    toggleDetail(item) {
      const id = String(item && item.itemId || '')
      this.detailId = this.detailId === id ? '' : id
    },
    clearScheduleData() {
      this.items = null; this.todayItems = []; this.todayDate = ''; this.todayWeek = null
      this.timeBands = []; this.currentWeek = null; this.teachingWeeks = null; this.calendarSource = ''
      this.termCode = ''; this.selectedWeek = 0; this.selectedDay = 0; this.loadedOnce = false
    },
    applyRouteContext(items) {
      if (this.routeContextApplied) return false
      const target = this.detailId && items.find((item) => String(item.itemId) === this.detailId)
      if (!target) return false
      const requestedWeek = this.targetWeek && activeInWeek(target, this.targetWeek) ? this.targetWeek : firstActiveWeek(target)
      if (requestedWeek) this.selectedWeek = requestedWeek
      const targetDay = safeRouteNumber(target.weekday, 7)
      this.selectedDay = this.targetDay === targetDay ? this.targetDay : targetDay
      this.routeContextApplied = true
      return true
    },
    load() {
      this.hidden = false
      const identity = currentSessionGeneration()
      if (identity !== this.identity) {
        this.identity = identity; this.clearScheduleData(); this.detailId = ''; this.targetWeek = 0; this.targetDay = 0
      }
      const epoch = ++this.requestEpoch
      this.state = 'loading'
      return studentApi.getMySchedule().then((data) => {
        if (epoch !== this.requestEpoch || this.hidden || identity !== currentSessionGeneration()) return
        if (!data || !Array.isArray(data.items) || !Array.isArray(data.todayItems)) throw new Error('课表信息无法核对')
        const termChanged = this.termCode !== (data.termCode || '')
        this.items = data.items
        this.todayItems = data.todayItems || []
        this.todayDate = data.todayDate || ''
        this.todayWeek = data.todayWeek != null ? Number(data.todayWeek) : null
        this.calendarSource = data.calendarSource || ''
        this.timeBands = Array.isArray(data.timeBands) ? data.timeBands : []
        this.currentWeek = data.currentWeek != null ? Number(data.currentWeek) : null
        this.teachingWeeks = data.teachingWeeks != null ? Number(data.teachingWeeks) : null
        this.termCode = data.termCode || ''
        const appliedTarget = this.applyRouteContext(data.items)
        if (!appliedTarget && (!this.loadedOnce || termChanged)) {
          this.selectedWeek = this.currentWeek && this.currentWeek <= this.maxWeek ? this.currentWeek : 0
          this.selectedDay = 0
        }
        this.loadedOnce = true
        this.state = 'ready'
      }).catch((error) => {
        if (epoch !== this.requestEpoch || this.hidden || identity !== currentSessionGeneration()) return
        const forbidden = Number(error?.httpStatus) === 403 || /^403/.test(String(error?.code || ''))
        if (forbidden) this.clearScheduleData()
        this.state = forbidden ? 'forbidden' : 'error'
      })
    },
    copySummary() {
      if (this.copying) return
      this.copying = true
      const viewName = this.selectedWeek ? `第${this.selectedWeek}周` : '全部周次'
      const lines = this.filteredItems.map((item) =>
        `${WEEK[item.weekday] || item.weekday} 第${item.slotNo}节 ${item.courseName} ${item.classroom || ''} ${this.parity(item)}`).join('\n')
      const text = `个人课表摘要（${viewName}）\n\n${lines || '暂无课表'}`
      uni.setClipboardData({
        data: text,
        success: () => safeToast('课表摘要已复制', 'success'),
        fail: () => safeToast('复制失败，请稍后重试'),
        complete: () => { this.copying = false }
      })
    }
  }
}
</script>

<style scoped>
.page-wrap { font-family: -apple-system, BlinkMacSystemFont, "Microsoft YaHei", sans-serif; padding-bottom: calc(64px + env(safe-area-inset-bottom)); }
button, input, textarea { font-family: inherit; }
.sc__week { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); margin-bottom: var(--space-3); }
.sc__today { margin-bottom: var(--space-3); padding: var(--space-4); border: 1px solid var(--border-base); border-radius: var(--radius-lg); background: var(--bg-card); }
.sc__today-head { display: flex; justify-content: space-between; gap: var(--space-3); align-items: flex-start; }
.sc__today-kicker { display: block; color: #15803d; font-size: 12px; font-weight: 700; }
.sc__today-title { display: block; margin-top: 4px; color: var(--text-primary); font-size: 18px; font-weight: 700; }
.sc__today-note { display: block; margin-top: 3px; color: var(--text-tertiary); font-size: 12px; line-height: 1.5; }
.sc__today-week { flex-shrink: 0; padding: 4px 8px; border-radius: var(--radius-full); background: var(--bg-card); color: #15803d; font-size: 12px; }
.sc__today-list { margin-top: var(--space-3); }
.sc__today-item { display: flex; align-items: center; gap: var(--space-3); padding: var(--space-3); margin-top: var(--space-2); border-left: 3px solid #16a34a; border-radius: 12px; background: var(--bg-page); }
.sc__today-time { flex-shrink: 0; width: 82px; color: #15803d; font-size: var(--font-size-sm); font-weight: 700; }
.sc__today-time text { display: block; }
.sc__today-time text + text { margin-top: 2px; font-size: 12px; font-weight: 500; }
.sc__today-empty { margin-top: var(--space-3); padding: var(--space-4); border: 1px dashed rgba(22,163,74,.25); border-radius: 12px; color: var(--text-tertiary); text-align: center; font-size: var(--font-size-xs); }
.sc__week-title { display: block; color: var(--brand-primary); font-size: var(--font-size-lg); font-weight: 700; }
.sc__week-sub { display: block; margin-top: 3px; color: var(--text-tertiary); font-size: var(--font-size-xs); }
.sc__week-picker { min-width: 88px; height: 40px; padding: 0 var(--space-3); border: 1px solid var(--border-base); border-radius: var(--radius-md); background: var(--bg-card); color: var(--text-secondary); font-size: var(--font-size-sm); line-height: 40px; text-align: center; }
.sc__actions { margin-bottom: var(--space-3); }
.sc__copy { background: var(--brand-primary); color: #fff; border-radius: var(--radius-full); font-size: var(--font-size-sm); }
.sc__hint { display: block; margin-top: var(--space-2); text-align: center; color: var(--text-tertiary); font-size: var(--font-size-xs); }
.sc__empty { text-align: center; color: var(--text-tertiary); padding: var(--space-5); }
.sc__day { margin-bottom: var(--space-4); }
.sc__day-t { display: block; font-weight: 700; color: var(--brand-primary); margin-bottom: var(--space-2); }
.sc__item { display: flex; gap: var(--space-3); background: var(--bg-card); border-radius: var(--radius-lg); padding: var(--space-3); margin-bottom: var(--space-2); border: 1px solid var(--border-base); }
.sc__slot { flex-shrink: 0; width: 82px; text-align: center; font-size: var(--font-size-sm); color: var(--text-secondary); align-self: center; }
.sc__course { display: block; font-weight: 600; }
.sc__meta { display: block; font-size: var(--font-size-sm); color: var(--text-tertiary); margin-top: 2px; }
.sc__source { display: inline-block; margin-top: 4px; padding: 1px 6px; border-radius: var(--radius-full); background: var(--primary-50); color: var(--primary-700); font-size: 12px; }
.sc__detail { display: flex; flex-direction: column; gap: 3px; margin-top: 8px; padding-top: 8px; border-top: 1px solid var(--border-base); color: var(--text-secondary); font-size: 12px; line-height: 1.5; }
.sc__today-head { flex-wrap: wrap; }
.sc__week > view { flex: 1; min-width: 0; }
.sc__week picker { flex-shrink: 0; }
.sc__main { flex: 1; min-width: 0; }
.sc__course { overflow-wrap: anywhere; line-height: 1.5; }
.sc__slot text { display: block; }
.sc__time { margin-top: 4px; font-size: 12px; line-height: 1.5; }
</style>
