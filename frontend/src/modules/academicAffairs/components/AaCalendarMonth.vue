<template>
  <div class="acm-layout">
    <section class="acm-calendar" aria-label="学期月历">
      <h2>{{ monthLabel }} · {{ title }}</h2>
      <div class="acm-toolbar">
        <AppButton @click="moveMonth(-1)">上一月</AppButton>
        <strong>{{ monthLabel }}</strong>
        <AppButton @click="moveMonth(1)">下一月</AppButton>
        <span>{{ weekMode ? '周次来自正式学期配置' : '日历日期下显示已登记的正式事件' }}</span>
      </div>
      <ErrorState v-if="error" :description="error" @retry="$emit('retry')" />
      <LoadingState v-else-if="loading" />
      <template v-else>
        <div class="acm-weekdays"><span v-for="day in weekdays" :key="day">{{ day }}</span></div>
        <div class="acm-days">
          <div v-for="day in days" :key="day.key" class="acm-day" :class="{ 'is-padding': !day.date, 'is-today': day.date === today }">
            <template v-if="day.date">
              <time :datetime="day.date">{{ day.number }}</time>
              <span v-if="weekMode && day.week" class="acm-event">第 {{ day.week.weekNo }} 周</span>
              <span v-for="event in day.events" :key="event.eventId" class="acm-event" :class="`is-${event.eventType.toLowerCase()}`" :title="`${event.label} · ${event.remark || '无备注'} · 事件 ${event.eventId}`">
                {{ event.label }}<span v-if="event.remark"> · {{ event.remark }}</span>
              </span>
            </template>
          </div>
        </div>
      </template>
    </section>
    <aside class="acm-notes">
      <h2>本月需要核对</h2>
      <div class="acm-note"><strong>校历定义与激活分开</strong><p>{{ authorityHint }}</p></div>
      <div class="acm-note"><strong>{{ loading || error ? '安排待核对' : weekMode ? `本月包含 ${monthWeeks.length} 个教学周` : `本月已登记 ${monthEvents.length} 项事件` }}</strong><p>{{ weekMode ? '周次按正式学期起止日期和教学周配置展开；具体课程以正式课表为准。' : '教学、假期与补课安排以正式事件为准；空白日期不代表没有教学任务。' }}</p></div>
      <div class="acm-note"><strong>引用影响</strong><p>调整前核对正式课表、考试与调休配对。已发布学期按学校变更流程办理。</p></div>
      <AppButton v-if="canCreate" variant="primary" @click="$emit('create')">新增校历事件</AppButton>
      <p v-else class="acm-readonly">{{ weekMode ? '按正式学期配置查阅' : '当前学期仅供查阅' }}</p>
    </aside>
  </div>
</template>

<script>
import { ErrorState, LoadingState } from '@/components/business'
import { AppButton } from '@/components/ui'

const labels = { TEACHING: '教学', EXAM: '考试', INTERNSHIP: '实习', HOLIDAY: '节假日', SWAP: '调休' }
const dateOnly = value => String(value || '').slice(0, 10)
export default {
  name: 'AaCalendarMonth',
  components: { ErrorState, LoadingState, AppButton },
  props: {
    term: { type: Object, required: true }, events: { type: Array, default: () => [] },
    weeks: { type: Array, default: () => [] }, weekMode: Boolean,
    loading: Boolean, error: { type: String, default: '' }, canCreate: Boolean,
    title: { type: String, default: '校历管理' }, authorityHint: { type: String, default: '当前学期的启用方式以学校当前权威结论为准。' }
  },
  emits: ['retry', 'create'],
  data() { const now = new Date(); return { month: '', today: `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`, weekdays: ['周一', '周二', '周三', '周四', '周五', '周六', '周日'] } },
  computed: {
    monthLabel() { const [year, month] = this.month.split('-').map(Number); return `${year}年${month}月` },
    monthEvents() {
      return this.events.filter(event => dateOnly(event.startDate).slice(0, 7) <= this.month && dateOnly(event.endDate || event.startDate).slice(0, 7) >= this.month || dateOnly(event.swapToDate).slice(0, 7) === this.month)
    },
    monthWeeks() { return (this.weeks || []).filter(week => dateOnly(week.startDate).slice(0, 7) <= this.month && dateOnly(week.endDate).slice(0, 7) >= this.month) },
    days() {
      const [year, month] = this.month.split('-').map(Number)
      if (!year || !month) return []
      const first = new Date(Date.UTC(year, month - 1, 1))
      const offset = (first.getUTCDay() + 6) % 7, count = new Date(Date.UTC(year, month, 0)).getUTCDate()
      return Array.from({ length: Math.ceil((offset + count) / 7) * 7 }, (_, i) => {
        const number = i - offset + 1
        if (number < 1 || number > count) return { key: `padding-${i}` }
        const date = `${this.month}-${String(number).padStart(2, '0')}`
        const events = this.monthEvents.filter(event => date >= dateOnly(event.startDate) && date <= dateOnly(event.endDate || event.startDate) || date === dateOnly(event.swapToDate))
          .map(event => ({ ...event, eventType: event.eventType || 'UNKNOWN', label: event.eventType === 'SWAP' ? date === dateOnly(event.swapToDate) ? `补课（原 ${dateOnly(event.startDate)}）` : `调休（至 ${dateOnly(event.swapToDate)}）` : labels[event.eventType] || '事件类型待核对' }))
        return { key: date, date, number, events, week: this.monthWeeks.find(week => date >= dateOnly(week.startDate) && date <= dateOnly(week.endDate)) }
      })
    }
  },
  watch: { 'term.termId': { immediate: true, handler() {
    const start = dateOnly(this.term.startDate), end = dateOnly(this.term.endDate)
    this.month = (start && (this.today < start || end && this.today > end) ? start : this.today).slice(0, 7)
  } } },
  methods: {
    moveMonth(delta) { const [year, month] = this.month.split('-').map(Number); const next = new Date(Date.UTC(year, month - 1 + delta, 1)); this.month = next.toISOString().slice(0, 7) }
  }
}
</script>

<style scoped>
.acm-layout { display: grid; grid-template-columns: minmax(0, 1fr) 280px; align-items: start; gap: 16px; }
.acm-calendar, .acm-notes { overflow: hidden; border: 1px solid var(--border-base); border-radius: 10px; background: var(--bg-card); }
.acm-layout h2 { margin: 0; padding: 15px 17px; border-bottom: 1px solid var(--border-base); font-size: 14px; color: var(--text-primary); }
.acm-toolbar { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; padding: 12px 16px; font-size: 13px; }
.acm-toolbar > span { margin-left: auto; font-size: 12px; color: var(--text-tertiary); }
.acm-weekdays, .acm-days { display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); }
.acm-weekdays { background: var(--primary-50, #edf3fc); border-block: 1px solid var(--border-base); }
.acm-weekdays span { padding: 10px 6px; text-align: center; font-size: 12px; color: var(--text-secondary); }
.acm-day { min-height: 94px; padding: 10px 7px; box-sizing: border-box; border-right: 1px solid var(--border-base); border-bottom: 1px solid var(--border-base); overflow-wrap: anywhere; }
.acm-day:nth-child(7n) { border-right: 0; }
.acm-day time { display: block; margin-bottom: 7px; font-size: 12px; }
.acm-day.is-padding { background: var(--bg-page); }
.acm-day.is-today { box-shadow: inset 0 0 0 2px var(--pri); }
.acm-event { display: block; margin-top: 4px; color: var(--pri); font-size: 11px; line-height: 1.55; }
.acm-event.is-holiday, .acm-event.is-swap { color: var(--warning-700, #926318); }
.acm-note { position: relative; margin: 19px 17px 0 25px; padding-left: 12px; border-left: 1px solid var(--border-base); }
.acm-note::before { content: ''; position: absolute; top: 5px; left: -4px; width: 7px; height: 7px; border-radius: 50%; background: var(--pri); }
.acm-note strong { font-size: 13px; color: var(--text-primary); }
.acm-note p, .acm-readonly { font-size: 12px; line-height: 1.7; color: var(--text-secondary); }
.acm-notes > button, .acm-readonly { margin: 16px; }
@media (max-width: 1100px) { .acm-layout { grid-template-columns: minmax(0, 1fr); } .acm-notes { display: flex; flex-wrap: wrap; gap: 6px; } .acm-notes h2 { width: 100%; } .acm-note { flex: 1; min-width: 180px; } }
</style>
