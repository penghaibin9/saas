<template>
  <view class="page-wrap">
    <AcademicPageNav variant="default" title="校历" show-back />
    <AcademicPageState :state="state" @retry="load">
      <view class="page-pad stack" v-if="d">
        <view class="card" v-if="d.hasTerm">
          <text class="t-md t-bold">当前学期 {{ d.termLabel }}</text>
          <text class="mk__sub" v-if="d.note">{{ d.note }}</text>
        </view>
        <AcademicPageState v-else state="empty" :title="d.note || '尚未设置当前学期'" />
        <view class="card">
          <view class="cal__head"><button @click="changeMonth(-1)">上月</button><text>{{ monthLabel }}</text><button @click="changeMonth(1)">下月</button></view>
          <view class="cal__grid">
            <text v-for="label in ['一','二','三','四','五','六','日']" :key="label" class="cal__weekday">{{ label }}</text>
            <view v-for="(day, i) in monthDays" :key="i" class="cal__day" :class="{ 'is-selected': day.date === selectedDate, 'has-event': day.event }" @click="selectedDate = day.date === selectedDate ? '' : day.date">
              <text>{{ day.label }}</text><text v-if="day.event" class="cal__marker">有事项</text>
            </view>
          </view>
        </view>
        <view class="section-head"><text class="section-head__title">校历事件</text></view>
        <text class="mk__sub">{{ calendarCoverageText }}</text>
        <AcademicPageState v-if="!visibleEvents.length" state="empty" :title="selectedDate ? '当天暂无已发布事项' : '本月暂无已发布事项'" />
        <view v-for="e in visibleEvents.slice(0, listLimit)" :key="e.eventId || e.id" class="list-row">
          <view class="flex-1">
            <text class="t-md">{{ e.remark || e.title || eventType(e.eventType || e.type) }}</text>
            <text class="mk__sub">{{ (e.startDate || '').slice(0,10) }} ~ {{ (e.endDate || e.startDate || '').slice(0,10) }}</text>
          </view>
        </view>
        <button v-if="visibleEvents.length > listLimit" class="btn" @click="listLimit += 20">查看更多事项</button>
        <view class="section-head"><text class="section-head__title">教学周</text></view>
        <view v-for="w in (d.weeks || []).slice(0, weekLimit)" :key="w.weekNo" class="list-row">
          <text class="t-md">第{{ w.weekNo }}周</text>
          <text class="mk__sub">{{ (w.startDate || '').slice(0,10) }} ~ {{ (w.endDate || '').slice(0,10) }}</text>
        </view>
        <button v-if="(d.weeks || []).length > weekLimit" class="btn" @click="weekLimit += 20">查看更多教学周</button>
        <text class="mk__sub">调休、补课的实际节次以正式课表为准。</text>
        <button class="btn btn-primary" @click="go('/pages/student/academic-affairs/schedule')">查看正式课表</button>
      </view>
    </AcademicPageState>
    <MobileTabBar side="student" active="" />
  </view>
</template>
<script>
import AcademicPageNav from './AcademicPageNav.vue'
import AcademicPageState from './AcademicPageState.vue'
import { studentApi } from '@/services/studentApi'
import { academicReadPage } from './read-page'
import { go } from '@/utils/nav'
export default {
  components: { AcademicPageNav, AcademicPageState },
  mixins: [academicReadPage],
  data() { const today = new Date(); return { d: null, state: 'loading', year: today.getFullYear(), month: today.getMonth(), selectedDate: '', weekLimit: 20, clearReadDataOnForbidden: true } },
  onLoad() { this.load() },
  computed: {
    monthLabel() { return `${this.year}年${this.month + 1}月` },
    monthPrefix() { return `${this.year}-${String(this.month + 1).padStart(2, '0')}` },
    calendarCoverageText() {
      const events = (this.d && this.d.events || []).length
      const weeks = (this.d && this.d.weeks || []).length
      return `当前返回 ${events} 条已发布校历事项和 ${weeks} 个教学周；学校暂未提供总条数。`
    },
    visibleEvents() {
      const start = this.selectedDate || `${this.monthPrefix}-01`
      const end = this.selectedDate || `${this.monthPrefix}-${new Date(this.year, this.month + 1, 0).getDate()}`
      return ((this.d && this.d.events) || []).filter(e => String(e.startDate || '').slice(0, 10) <= end && String(e.endDate || e.startDate || '').slice(0, 10) >= start)
    },
    monthDays() {
      const days = Array.from({ length: (new Date(this.year, this.month, 1).getDay() + 6) % 7 }, () => ({ label: '', date: '' }))
      for (let n = 1; n <= new Date(this.year, this.month + 1, 0).getDate(); n++) {
        const date = `${this.monthPrefix}-${String(n).padStart(2, '0')}`
        const event = ((this.d && this.d.events) || []).some(e => String(e.startDate || '').slice(0, 10) <= date && String(e.endDate || e.startDate || '').slice(0, 10) >= date)
        days.push({ label: n, date, event })
      }
      return days
    }
  },
  methods: {
    go,
    resetAcademicContext() { this.selectedDate = ''; this.weekLimit = 20 },
    eventType(type) { return { HOLIDAY: '节假日', EXAM: '考试周', REGISTRATION: '注册事项', MAKEUP: '调休补课' }[type] || '学校事项' },
    changeMonth(delta) { const date = new Date(this.year, this.month + delta, 1); this.year = date.getFullYear(); this.month = date.getMonth(); this.selectedDate = ''; this.listLimit = 20 },
    load() {
      return this.readAcademic(() => studentApi.getMyCalendar(), (d) => {
        if (!d || typeof d.hasTerm !== 'boolean' || !Array.isArray(d.events) || !Array.isArray(d.weeks)) throw new Error('校历信息无法核对')
        this.d = d
      })
    }
  }
}
</script>
<style scoped>
.page-wrap { font-family: -apple-system, BlinkMacSystemFont, "Microsoft YaHei", sans-serif; padding-bottom: calc(64px + env(safe-area-inset-bottom)); }
button, input, textarea { font-family: inherit; }
.cal__head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.cal__head button { margin: 0; padding: 0 10px; font-size: 12px; background: var(--bg-page); color: var(--brand-primary); }
.cal__grid { display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); }
.cal__weekday { text-align: center; font-size: 12px; color: var(--text-tertiary); padding: 8px 0; }
.cal__day { min-height: 48px; display: flex; flex-direction: column; align-items: center; padding: 6px 0; border-radius: 8px; font-size: 14px; }
.cal__day.is-selected { background: var(--brand-primary); color: white; }
.cal__marker { font-size: 9px; color: var(--brand-primary); margin-top: 3px; }
.is-selected .cal__marker { color: white; }
.mk__sub { display:block; color: var(--t3); font-size: 12px; margin-top: 4px; }
</style>
