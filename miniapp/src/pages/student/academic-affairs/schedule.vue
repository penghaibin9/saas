<template>
  <view class="page-wrap">
    <MobileNavBar variant="brand" title="我的课表" :subtitle="termCode || '当前学期'" back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad" v-if="items">
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

export default {
  data() {
    return {
      items: null, state: 'loading', WEEK, copying: false,
      currentWeek: null, teachingWeeks: null, selectedWeek: 0, termCode: ''
    }
  },
  onLoad() { this.load() },
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
    emptyText() {
      return this.selectedWeek ? `第${this.selectedWeek}周暂无课程` : '暂无已发布课表'
    }
  },
  methods: {
    parity(item) {
      const value = item.weekParity === 'ODD' ? '单周' : item.weekParity === 'EVEN' ? '双周' : '全周'
      return `${item.startWeek}-${item.endWeek}周·${value}`
    },
    onWeekChange(event) {
      this.selectedWeek = Number(event.detail.value) || 0
    },
    load() {
      this.state = 'loading'
      studentApi.getMySchedule().then((data) => {
        this.items = data.items || []
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
