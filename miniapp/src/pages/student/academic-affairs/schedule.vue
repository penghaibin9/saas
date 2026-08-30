<template>
  <view class="page-wrap">
    <MobileNavBar variant="brand" title="我的课表" :subtitle="termCode || '当前学期'" back />
    <MobileGlobalState :state="state" @retry="load">
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
            <view v-for="item in todayItems" :key="`today-${item.itemId}`" class="sc__today-item">
              <view class="sc__today-time">
                <text>第{{ item.slotNo }}节</text>
                <text v-if="slotTime(item)">{{ slotTime(item) }}</text>
              </view>
              <view class="flex-1">
                <text class="sc__course">{{ item.courseName }}</text>
                <text class="sc__meta">{{ item.classroom || '教室待定' }} · {{ item.teacherName || '教师待定' }}</text>
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
        <view class="sc__actions">
          <button class="sc__copy" :disabled="copying" @click="copySummary">
            {{ copying ? '复制中…' : '复制当前视图摘要' }}
          </button>
          <text class="sc__hint">正式打印请在学生PC端生成带水印文件</text>
        </view>
        <view class="sc__empty" v-if="!filteredItems.length"><text>{{ emptyText }}</text></view>
        <view v-for="dayGroup in grouped" :key="dayGroup.day" class="sc__day">
          <text class="sc__day-t">{{ WEEK[dayGroup.day] }}</text>
          <view v-for="item in dayGroup.list" :key="item.itemId" class="sc__item">
            <view class="sc__slot">第{{ item.slotNo }}节</view>
            <view class="sc__main">
              <text class="sc__course">{{ item.courseName }}</text>
              <text class="sc__meta">{{ item.classroom || '教室待定' }} · {{ item.teacherName || '教师待定' }} · {{ parity(item) }}</text>
              <text v-if="item.source === 'ENROLLED'" class="sc__source">选课课程</text>
            </view>
          </view>
        </view>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { safeToast } from '@/services/request'

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
  return start && end ? `${start}-${end}` : (start || end)
}

export default {
  data() {
    return {
      items: null, state: 'loading', WEEK, copying: false,
      currentWeek: null, teachingWeeks: null, selectedWeek: 0, termCode: '',
      todayItems: [], todayDate: '', todayWeek: null, calendarSource: '', timeBands: []
    }
  },
  onShow() { this.load() },
  computed: {
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
      return this.selectedWeek ? `第${this.selectedWeek}周暂无课程` : '暂无已发布课表'
    }
  },
  methods: {
    parity(item) {
      const value = item.weekParity === 'ODD' ? '单周' : item.weekParity === 'EVEN' ? '双周' : '全周'
      return `${item.startWeek}-${item.endWeek}周·${value}`
    },
    slotTime(item) {
      const ranges = [...new Set((this.timeBands || [])
        .filter((band) => Number(band.slotNo) === Number(item.slotNo))
        .map(timeRange).filter(Boolean))]
      if (ranges.length === 1) return ranges[0]
      if (ranges.length > 1) return '按校区作息'
      return ''
    },
    onWeekChange(event) {
      this.selectedWeek = Number(event.detail.value) || 0
    },
    load() {
      this.state = 'loading'
      studentApi.getMySchedule().then((data) => {
        this.items = data.items || []
        this.todayItems = data.todayItems || []
        this.todayDate = data.todayDate || ''
        this.todayWeek = data.todayWeek != null ? Number(data.todayWeek) : null
        this.calendarSource = data.calendarSource || ''
        this.timeBands = data.timeBands || []
        this.currentWeek = data.currentWeek != null ? Number(data.currentWeek) : null
        this.teachingWeeks = data.teachingWeeks != null ? Number(data.teachingWeeks) : null
        this.termCode = data.termCode || ''
        this.selectedWeek = this.currentWeek && this.currentWeek <= this.maxWeek ? this.currentWeek : 0
        this.state = 'ready'
      }).catch(() => { this.state = 'error' })
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
.sc__week { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); margin-bottom: var(--space-3); }
.sc__today { margin-bottom: var(--space-3); padding: var(--space-4); border: 1px solid rgba(22,163,74,.20); border-radius: 18px; background: linear-gradient(135deg, rgba(248,255,250,.98), rgba(238,249,242,.96)); box-shadow: var(--shadow-card); }
.sc__today-head { display: flex; justify-content: space-between; gap: var(--space-3); align-items: flex-start; }
.sc__today-kicker { display: block; color: #15803d; font-size: 10px; font-weight: 700; }
.sc__today-title { display: block; margin-top: 4px; color: var(--text-primary); font-size: 18px; font-weight: 800; }
.sc__today-note { display: block; margin-top: 3px; color: var(--text-tertiary); font-size: 10px; line-height: 1.5; }
.sc__today-week { flex-shrink: 0; padding: 4px 8px; border-radius: var(--radius-full); background: #fff; color: #15803d; font-size: 10px; }
.sc__today-list { margin-top: var(--space-3); }
.sc__today-item { display: flex; align-items: center; gap: var(--space-3); padding: var(--space-3); margin-top: var(--space-2); border-left: 3px solid #16a34a; border-radius: 12px; background: rgba(255,255,255,.88); }
.sc__today-time { flex-shrink: 0; width: 82px; color: #15803d; font-size: var(--font-size-sm); font-weight: 700; }
.sc__today-time text { display: block; }
.sc__today-time text + text { margin-top: 2px; font-size: 10px; font-weight: 500; }
.sc__today-empty { margin-top: var(--space-3); padding: var(--space-4); border: 1px dashed rgba(22,163,74,.25); border-radius: 12px; color: var(--text-tertiary); text-align: center; font-size: var(--font-size-xs); }
.sc__week-title { display: block; color: var(--brand-primary); font-size: var(--font-size-lg); font-weight: 700; }
.sc__week-sub { display: block; margin-top: 3px; color: var(--text-tertiary); font-size: var(--font-size-xs); }
.sc__week-picker { min-width: 88px; height: 34px; padding: 0 var(--space-3); border: 1px solid var(--border-base); border-radius: var(--radius-md); background: var(--bg-card); color: var(--text-secondary); font-size: var(--font-size-sm); line-height: 34px; text-align: center; }
.sc__actions { margin-bottom: var(--space-3); }
.sc__copy { background: var(--brand-primary); color: #fff; border-radius: var(--radius-full); font-size: var(--font-size-sm); }
.sc__hint { display: block; margin-top: var(--space-2); text-align: center; color: var(--text-tertiary); font-size: var(--font-size-xs); }
.sc__empty { text-align: center; color: var(--text-tertiary); padding: var(--space-5); }
.sc__day { margin-bottom: var(--space-4); }
.sc__day-t { display: block; font-weight: 700; color: var(--brand-primary); margin-bottom: var(--space-2); }
.sc__item { display: flex; gap: var(--space-3); background: var(--bg-card); border-radius: var(--radius-lg); padding: var(--space-3); margin-bottom: var(--space-2); box-shadow: var(--shadow-card); }
.sc__slot { flex-shrink: 0; width: 56px; text-align: center; font-size: var(--font-size-sm); color: var(--text-secondary); align-self: center; }
.sc__course { display: block; font-weight: 600; }
.sc__meta { display: block; font-size: var(--font-size-sm); color: var(--text-tertiary); margin-top: 2px; }
.sc__source { display: inline-block; margin-top: 4px; padding: 1px 6px; border-radius: var(--radius-full); background: var(--primary-50); color: var(--primary-700); font-size: 10px; }
</style>
