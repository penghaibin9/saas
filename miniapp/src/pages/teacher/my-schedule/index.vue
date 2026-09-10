<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" :title="lesson ? '我的正式课次' : '我的课表'" :subtitle="termCode || '当前学期授课安排'" :before-back="backToSchedule" show-back />
    <MobileGlobalState :state="state" @retry="load">
      <view v-if="lesson" class="page-pad">
        <button class="btn btn-ghost ts__back" @click="backToSchedule">‹ 返回课表</button>
        <view class="card ts__lesson">
          <text class="ts__today-kicker">{{ lessonIsToday ? todayDate : '正式课表安排' }}</text>
          <text class="ts__today-title">{{ lesson.courseName || '课程名称待确认' }}</text>
          <text class="ts__meta">{{ lesson.className || '教学班未提供' }}</text>
          <view class="ts__fact"><text>上课地点</text><text>{{ lesson.classroom || '教室待定' }}</text></view>
          <view class="ts__fact"><text>课次时间</text><text>{{ WEEK[lesson.weekday] || '以校历为准' }} 第{{ lesson.slotNo }}节 · {{ slotTime(lesson) || '作息待确认' }}</text></view>
          <view class="ts__fact"><text>教学周次</text><text>{{ parity(lesson) }}</text></view>
          <view class="ts__fact"><text>课位编号</text><text>{{ lessonId }}</text></view>
          <text v-if="lesson.changeType" class="ts__notice">{{ lesson.changeType === 'MAKEUP' ? '本课为正式补课安排' : lesson.changeType === 'ADJUST' ? '本课已按正式调课安排更新' : '课次以正式课表为准' }}</text>
          <text v-if="lessonIsToday && !lesson.attendanceRoute" class="ts__notice">{{ lesson.attendanceBlockReason || '当前课次暂不可点名' }}</text>
        </view>
        <MobileSafeAreaBar>
          <button class="btn btn-ghost flex-1" @click="requestChange(lesson)">申请调停课</button>
          <button class="btn btn-primary flex-1" :disabled="!lessonIsToday || !lesson.attendanceRoute" @click="openTodayCourse(lesson)">{{ lesson.attendanceActionLabel || '开始本课点名' }}</button>
        </MobileSafeAreaBar>
      </view>
      <view class="page-pad" v-if="items && !lesson">
        <text class="ts__section-label">今日工作 · 本人授课</text>
        <view class="ts__week">
          <view>
            <text class="ts__week-title">{{ selectedWeek ? `第 ${selectedWeek} 周` : '全部周次' }}{{ weekDateLabel ? ' · ' + weekDateLabel : '' }}</text>
          </view>
          <picker class="ts__week-control" mode="selector" :range="weekLabels" :value="selectedWeek" @change="onWeekChange">
            <view class="ts__week-picker">{{ weekLabels[selectedWeek] || '全部周次' }}⌄</view>
          </picker>
        </view>
        <text v-if="timeBands.length" class="ts__meta">节次时间来自学校作息；日期按学校教学周展示。</text>
        <view class="ts__date-strip">
          <button v-for="day in weekDays" :key="day.weekday" class="ts__date" :class="{ 'is-selected': selectedDay === day.weekday }" @click="selectedDay = day.weekday">
            <text>{{ WEEK[day.weekday] }}</text><text class="ts__date-number">{{ day.dateNumber || '—' }}</text>
          </button>
        </view>
        <text class="ts__day-t">{{ WEEK[selectedDay] }} · {{ dayIsToday ? '今日正式课次' : '周课表安排' }}</text>
        <view class="ts__empty" v-if="!dayItems.length"><text>{{ dayIsToday ? todayNote : '当天暂无授课安排' }}</text></view>
        <view v-for="item in dayItems" :key="item.scheduleItemId || item.itemId" class="ts__course-card">
          <view class="ts__card-head"><text class="ts__card-time">{{ slotTime(item) || `第${item.slotNo}节` }}</text><text class="ts__badge">{{ dayIsToday ? '正式课次' : '周课表' }}</text></view>
          <text class="ts__card-title">{{ item.courseName || '课程名称待确认' }}</text>
          <text class="ts__card-meta">{{ item.className || item.teachingClassName || '教学班待确认' }} · {{ item.classroom || '教室待定' }}</text>
          <view class="ts__card-footer">
            <text>第{{ item.slotNo }}节 · {{ dayIsToday && currentWeek ? `第${currentWeek}周` : parity(item) }}</text>
            <button class="btn btn-ghost" @click="openLesson(item, dayIsToday)">{{ dayIsToday && item.attendanceRoute ? '查看与点名' : '查看课次' }}</button>
          </view>
        </view>
      </view>
    </MobileGlobalState>
    <MobileTabBar v-if="!lesson" side="teacher" active="workbench" />
  </view>
</template>

<script>
import { teacherApi } from '@/services/teacherApi'
import { go, toast } from '@/utils/nav'
import { useSessionStore } from '@/stores/session'

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

function timeRange(band) {
  const start = String((band && band.startTime) || '').trim()
  const end = String((band && band.endTime) || '').trim()
  if (start && end) return `${start}-${end}`
  return start || end
}

export default {
  data() {
    return {
      items: null, state: 'loading', WEEK,
      currentWeek: null, teachingWeeks: null, selectedWeek: 0, selectedDay: 1, termCode: '', termStartDate: '', timeBands: [],
      todayItems: [], todayDate: '', calendarSource: '', lessonId: '', lessonIsToday: false,
      targetLessonId: '', targetWeek: null, targetDay: null
    }
  },
  onLoad(options = {}) {
    this._pageActive = true
    this.targetLessonId = String(options.scheduleItemId || options.itemId || options.id || '')
    this.targetWeek = options.week == null || options.week === '' ? null : Number(options.week)
    this.targetDay = options.weekday == null || options.weekday === '' ? null : Number(options.weekday)
  },
  onShow() { this.load() },
  onHide() { this._pageActive = false; this._loadEpoch = (this._loadEpoch || 0) + 1 },
  onUnload() { this._pageActive = false; this._loadEpoch = (this._loadEpoch || 0) + 1 },
  onBackPress() { if (!this.lessonId) return false; this.backToSchedule(); return true },
  computed: {
    todayCalendarDate() {
      if (!/^\d{4}-\d{2}-\d{2}$/.test(this.todayDate)) return null
      const date = new Date(this.todayDate + 'T00:00:00Z')
      return Number.isFinite(date.getTime()) && date.toISOString().slice(0, 10) === this.todayDate ? date : null
    },
    todayWeekday() { return this.todayCalendarDate ? this.todayCalendarDate.getUTCDay() || 7 : null },
    selectedWeekStart() {
      if (!this.selectedWeek || !/^\d{4}-\d{2}-\d{2}$/.test(this.termStartDate)) return null
      const start = new Date(this.termStartDate + 'T00:00:00Z')
      if (!Number.isFinite(start.getTime()) || start.toISOString().slice(0, 10) !== this.termStartDate) return null
      start.setUTCDate(start.getUTCDate() + (this.selectedWeek - 1) * 7)
      return start
    },
    weekDays() {
      return Array.from({ length: 7 }, (_, i) => {
        const weekday = i + 1
        // Teaching weeks follow the canonical term start, which need not be a Monday.
        if (!this.selectedWeekStart) return { weekday }
        const offset = (weekday - (this.selectedWeekStart.getUTCDay() || 7) + 7) % 7
        const date = new Date(this.selectedWeekStart.getTime() + offset * 86400000)
        return { weekday, dateNumber: date.getUTCDate(), month: date.getUTCMonth() + 1 }
      })
    },
    weekDateLabel() {
      if (!this.selectedWeekStart) return ''
      const first = this.selectedWeekStart, last = new Date(first.getTime() + 6 * 86400000)
      return `${first.getUTCMonth() + 1}月${first.getUTCDate()}日—${last.getUTCMonth() === first.getUTCMonth() ? '' : last.getUTCMonth() + 1 + '月'}${last.getUTCDate()}日`
    },
    dayIsToday() { return this.selectedWeek === this.currentWeek && this.selectedDay === this.todayWeekday },
    dayItems() {
      const rows = this.dayIsToday ? this.todayItems : this.filteredItems.filter((item) => Number(item.weekday) === this.selectedDay)
      return rows.slice().sort((a, b) => Number(a.slotNo || 0) - Number(b.slotNo || 0))
    },
    lesson() { return this.lessonId ? (this.lessonIsToday ? this.todayItems : (this.items || [])).find((item) => String(item.scheduleItemId || item.itemId || '') === this.lessonId) || null : null },
    maxWeek() {
      const itemMax = Math.max(1, ...(this.items || []).map((item) => Number(item.endWeek || 1)))
      return Math.max(1, Number(this.teachingWeeks || 0), itemMax)
    },
    weekLabels() {
      return ['全部周次', ...Array.from({ length: this.maxWeek }, (_, index) => `第${index + 1}周`)]
    },
    filteredItems() {
      return (this.items || []).filter((item) => activeInWeek(item, this.selectedWeek))
    },
    grouped() {
      const map = {}
      this.filteredItems.forEach((item) => { (map[item.weekday] = map[item.weekday] || []).push(item) })
      return Object.keys(map).sort().map((day) => ({
        day,
        list: map[day].sort((a, b) => Number(a.slotNo || 0) - Number(b.slotNo || 0))
      }))
    },
    currentWeekText() {
      if (this.currentWeek == null) return '当前周次待校历确认'
      if (Number(this.currentWeek) === 0) return '当前学期尚未开始'
      return `当前第${this.currentWeek}周`
    },
    emptyText() {
      return this.selectedWeek ? `第${this.selectedWeek}周暂无授课安排` : '暂无已发布课表'
    },
    todayNote() {
      if (this.calendarSource === 'HOLIDAY') return '学校校历标记今天为节假日，正式课表不执行。'
      if (this.calendarSource === 'SWAP_SOURCE') return '学校校历标记今天为调休停课日，正式课表不执行。'
      if (this.calendarSource === 'OUT_OF_TERM') return '今天不在当前学期教学日期范围内。'
      return this.todayItems.length ? '来自同一份正式课表、正式名单与校历课次投影。' : '已核对学校校历和本人最新正式课表。'
    }
  },
  methods: {
    openLesson(item, today) {
      const id = String(item.scheduleItemId || item.itemId || '')
      if (!id) { toast('该课位缺少正式编号，请刷新课表'); return }
      this.lessonId = id
      this.lessonIsToday = today
    },
    backToSchedule() { if (!this.lessonId) return true; this.lessonId = ''; return false },
    requestChange(item) {
      const id = String(item.scheduleItemId || item.itemId || '')
      if (!id) { toast('该课位缺少正式编号，请刷新课表'); return }
      go(`/pages/teacher/schedule-change/index?scheduleItemId=${encodeURIComponent(id)}`)
    },
    contextKey() {
      const session = useSessionStore()
      const identity = session.identity || {}
      const realUser = session.realUser || {}
      return [
        identity.tenantId != null ? identity.tenantId : (realUser.tenantId != null ? realUser.tenantId : ''),
        identity.userId != null ? identity.userId : (realUser.userId != null ? realUser.userId : ''),
        session.currentRole || identity.roleCode || '',
        identity.activeContextId || (realUser.currentRole && realUser.currentRole.contextId) || realUser.activeContextId || ''
      ].map(String).join('|')
    },
    isForbidden(error) {
      const status = Number(error && (error.status || error.statusCode || error.httpStatus || (error.response && error.response.status)))
      const codes = [error && error.code, error && error.bizCode].map((value) => String(value || '').toUpperCase())
      return status === 403 || codes.some((code) => code.startsWith('403') || /FORBIDDEN|PERMISSION|NO_DATA_SCOPE/.test(code))
    },
    focusDeepLink() {
      if (!this.targetLessonId) return
      const id = this.targetLessonId
      const todayRow = this.todayItems.find((item) => String(item.scheduleItemId || item.itemId || '') === id)
      const scheduleRow = (this.items || []).find((item) => String(item.scheduleItemId || item.itemId || '') === id)
      const row = todayRow || scheduleRow
      this.targetLessonId = ''
      if (!row) {
        this.lessonId = ''
        toast('该正式课位不存在、已调整或不在当前身份范围内')
        return
      }
      this.lessonId = id
      this.lessonIsToday = !!todayRow
      if (todayRow) {
        this.selectedWeek = this.currentWeek || 0
        this.selectedDay = this.todayWeekday || Number(row.weekday) || 1
      } else {
        if (Number.isFinite(this.targetWeek) && this.targetWeek >= 0 && activeInWeek(row, this.targetWeek)) this.selectedWeek = this.targetWeek
        else if (this.currentWeek && activeInWeek(row, this.currentWeek)) this.selectedWeek = this.currentWeek
        else this.selectedWeek = Number(row.startWeek || 0)
        this.selectedDay = Number.isFinite(this.targetDay) && this.targetDay >= 1 && this.targetDay <= 7 ? this.targetDay : Number(row.weekday || 1)
      }
    },
    parity(item) {
      const value = item.weekParity === 'ODD' ? '单周' : item.weekParity === 'EVEN' ? '双周' : '全周'
      return `${item.startWeek}-${item.endWeek}周·${value}`
    },
    slotTime(item) {
      const ranges = [...new Set(
        (this.timeBands || [])
          .filter((band) => Number(band.slotNo) === Number(item.slotNo))
          .map(timeRange)
          .filter(Boolean)
      )]
      if (ranges.length === 1) return ranges[0]
      if (ranges.length > 1) return '按校区作息'
      return ''
    },
    openTodayCourse(item) {
      if (item && item.attendanceRoute) return go(item.attendanceRoute)
      toast((item && item.attendanceBlockReason) || '该课程当前仅可查看')
    },
    onWeekChange(event) {
      this.selectedWeek = Number(event.detail.value) || 0
    },
    async load() {
      this._pageActive = true
      const epoch = (this._loadEpoch || 0) + 1
      this._loadEpoch = epoch
      const context = this.contextKey()
      if (this._viewContext !== context) { this._viewContext = context; this.lessonId = ''; this._selectionInitialized = false; this.items = null; this.todayItems = [] }
      const selectedLessonId = this.lessonId
      const selectedLessonWasToday = this.lessonIsToday
      this.state = 'loading'
      try {
        const data = await teacherApi.getMySchedule()
        if (!this._pageActive || this._loadEpoch !== epoch || this.contextKey() !== context) return
        this.items = (data && data.items) || []
        this.todayItems = (data && data.todayItems) || []
        this.todayDate = (data && data.todayDate) || ''
        this.calendarSource = (data && data.calendarSource) || ''
        this.timeBands = (data && data.timeBands) || []
        this.currentWeek = data && data.currentWeek != null ? Number(data.currentWeek) : null
        this.teachingWeeks = data && data.teachingWeeks != null ? Number(data.teachingWeeks) : null
        this.termCode = (data && data.termCode) || ''
        this.termStartDate = (data && data.termStartDate) || ''
        if (!this._selectionInitialized) {
          this.selectedWeek = this.currentWeek && this.currentWeek <= this.maxWeek ? this.currentWeek : 0
          this.selectedDay = this.todayWeekday || 1
          this._selectionInitialized = true
        } else if (this.selectedWeek > this.maxWeek) this.selectedWeek = 0
        if (this.targetLessonId) this.focusDeepLink()
        else if (selectedLessonId) {
          const rows = selectedLessonWasToday ? this.todayItems : this.items
          if (!(rows || []).some((item) => String(item.scheduleItemId || item.itemId || '') === selectedLessonId)) {
            this.lessonId = ''
            toast('该正式课位已调整，请按最新课表重新选择')
          }
        }
        this.state = 'ready'
      } catch (error) {
        if (!this._pageActive || this._loadEpoch !== epoch || this.contextKey() !== context) return
        this.items = null; this.todayItems = []; this.lessonId = ''; this.timeBands = []
        if (this.isForbidden(error)) { this.currentWeek = null; this.teachingWeeks = null; this.termCode = ''; this.termStartDate = ''; this.todayDate = ''; this.calendarSource = '' }
        this.state = 'error'
      }
    }
  }
}
</script>

<style scoped>
.ts__section-label { display: block; margin: 8px 0 20px; color: var(--text-secondary); font-size: 12px; }
.ts__week { flex-wrap: wrap; gap: 10px; }
.ts__week-control { width: 100%; }
.ts__date-strip { display: flex; justify-content: space-between; gap: 5px; margin: 20px 0 28px; }
.ts__date { display: flex; flex: 1; min-width: 0; margin: 0; padding: 8px 0; flex-direction: column; align-items: center; gap: 6px; border: 0; border-radius: 10px; background: var(--bg-card); color: var(--text-secondary); font-size: 12px; line-height: 1.4; }
.ts__date::after { border: 0; }
.ts__date-number { font-size: 20px; font-weight: 700; }
.ts__date.is-selected { color: #fff; background: var(--teacher-600); }
.ts__course-card { padding: 16px; margin-bottom: 14px; border: 1px solid var(--border-base); border-left: 3px solid var(--teacher-600); border-radius: 14px; background: var(--bg-card); }
.ts__card-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.ts__card-time { color: var(--text-primary); font-size: 15px; font-weight: 700; }
.ts__badge { flex-shrink: 0; padding: 3px 6px; background: var(--teacher-50); color: var(--teacher-700); border-radius: 5px; font-size: 11px; }
.ts__card-title { display: block; margin: 12px 0; color: var(--text-primary); font-size: 18px; font-weight: 700; line-height: 1.5; overflow-wrap: anywhere; }
.ts__card-meta { display: block; margin-bottom: 16px; color: var(--text-secondary); font-size: 13px; line-height: 1.5; }
.ts__card-footer { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding-top: 12px; border-top: 1px solid var(--border-light); color: var(--text-secondary); font-size: 12px; }
.ts__card-footer > text { flex: 1; min-width: 0; }
.ts__card-footer button { flex-shrink: 0; min-height: 44px; margin: 0; font-size: 13px; }
.btn.btn-primary { background: var(--teacher-600); border-color: var(--teacher-600); color: #fff; }
.btn.btn-ghost { color: var(--teacher-700); border-color: var(--teacher-200); }
.btn[disabled] { opacity: .5; }
.ts__back { margin-bottom: 12px; }
.ts__lesson { display: flex; flex-direction: column; gap: 12px; }
.ts__fact { display: flex; justify-content: space-between; gap: 16px; padding: 14px 0; border-bottom: 1px solid var(--border-light); font-size: 14px; }
.ts__fact text:first-child { flex-shrink: 0; color: var(--text-tertiary); }
.ts__fact text:last-child { text-align: right; overflow-wrap: anywhere; }
.ts__notice { padding: 12px; border-radius: 10px; background: var(--teacher-50); color: var(--teacher-700); font-size: 13px; line-height: 1.6; }
.ts__week { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); margin-bottom: var(--space-3); }
.ts__today { margin-bottom: var(--space-3); padding: var(--space-4); border: 1px solid var(--border-base); border-radius: var(--radius-lg); background: var(--bg-card); }
.ts__today-head { display: flex; justify-content: space-between; gap: var(--space-3); align-items: flex-start; }
.ts__today-kicker { display: block; color: var(--teacher-700); font-size: 12px; font-weight: 700; }
.ts__today-title { display: block; margin-top: 4px; color: var(--text-primary); font-size: 18px; font-weight: 700; }
.ts__today-note { display: block; margin-top: 3px; color: var(--text-tertiary); font-size: 12px; line-height: 1.5; }
.ts__today-week { flex-shrink: 0; padding: 4px 8px; border-radius: var(--radius-full); background: var(--bg-card); color: var(--teacher-700); font-size: 12px; }
.ts__today-list { margin-top: var(--space-3); }
.ts__today-item { display: flex; align-items: center; gap: var(--space-3); padding: var(--space-3); margin-top: var(--space-2); border-left: 3px solid var(--teacher-600); border-radius: 12px; background: var(--bg-page); }
.ts__today-action { flex-shrink: 0; color: var(--teacher-700); font-size: 12px; }
.ts__today-empty { margin-top: var(--space-3); padding: var(--space-4); border: 1px dashed rgba(14,116,144,.25); border-radius: 12px; color: var(--text-tertiary); text-align: center; font-size: var(--font-size-xs); }
.ts__week-title { display: block; color: var(--text-primary); font-size: 16px; font-weight: 700; line-height: 1.5; }
.ts__week-sub { display: block; margin-top: 3px; color: var(--text-tertiary); font-size: var(--font-size-xs); line-height: 1.5; }
.ts__week-picker { min-width: 88px; height: 40px; padding: 0 var(--space-3); border: 1px solid var(--border-base); border-radius: var(--radius-md); background: var(--bg-card); color: var(--text-secondary); font-size: var(--font-size-sm); line-height: 40px; text-align: center; }
.ts__empty { text-align: center; color: var(--text-tertiary); padding: var(--space-5); }
.ts__day { margin-bottom: var(--space-4); }
.ts__day-t { display: block; font-size: 12px; color: var(--text-secondary); margin-bottom: 16px; }
.ts__item { display: flex; gap: var(--space-3); background: var(--bg-card); border-radius: var(--radius-lg); padding: var(--space-3); margin-bottom: var(--space-2); border: 1px solid var(--border-base); }
.ts__slot { display: flex; flex-direction: column; justify-content: center; flex-shrink: 0; width: 82px; text-align: center; font-size: var(--font-size-sm); color: var(--text-secondary); }
.ts__time { display: block; margin-top: 3px; color: var(--text-tertiary); font-size: 12px; line-height: 1.3; }
.ts__main { min-width: 0; }
.ts__course { display: block; font-weight: 600; }
.ts__meta { display: block; font-size: var(--font-size-sm); color: var(--text-tertiary); margin-top: 2px; line-height: 1.45; }
.ts__today-head { flex-wrap: wrap; }
.ts__week > view { flex: 1; min-width: 0; }
.ts__week picker { flex-shrink: 0; }
.ts__main { flex: 1; min-width: 0; }
.ts__course { overflow-wrap: anywhere; line-height: 1.5; }
</style>
