<template>
  <div class="sp-page schedule-page">
    <section class="schedule-hero">
      <div>
        <div class="schedule-hero__eyebrow">教务学业 · 我的课表</div>
        <h1>我的课表</h1>
        <p>{{ loading ? '正在读取课表…' : error ? '课表暂时无法读取' : schedule.note || currentWeekHint }}</p>
      </div>
      <div class="schedule-hero__actions">
        <button class="sp-btn sp-btn--ghost" @click="goAll">全部教务服务</button>
        <button class="sp-btn" :disabled="printing || loading || !!error || !filteredItems.length" @click="printSchedule">
          {{ printing ? '生成中…' : '打印当前课表视图' }}
        </button>
      </div>
    </section>

    <section v-if="!error" class="today-board" aria-labelledby="today-heading" :aria-busy="loading">
      <header class="today-board__head">
        <div>
          <div class="today-board__eyebrow">今天 · {{ todayDateText }}</div>
          <h2 id="today-heading">{{ todayHeading }}</h2>
          <p v-if="!loading">{{ todayNote }}</p>
        </div>
        <span v-if="!loading && schedule.todayWeek" class="today-board__week">第{{ schedule.todayWeek }}教学周</span>
      </header>
      <StateBlock v-if="loading" type="loading" text="正在读取今天的正式课程…" />
      <div v-else-if="todayItems.length" class="today-course-list">
        <article v-for="item in todayItems" :key="`today-${itemKey(item)}`" class="today-course" :class="sourceClass(item)">
          <div class="today-course__time">{{ slotLabel(item) }}</div>
          <div class="today-course__body">
            <strong>{{ item.courseName || '未命名课程' }}</strong>
            <span>{{ item.classroom || '教室待定' }} · {{ item.teacherName || '教师待定' }}</span>
          </div>
          <span v-if="item.source === 'ENROLLED'" class="today-course__source">选课课程</span>
        </article>
      </div>
      <div v-else-if="!loading" class="today-empty">{{ todayEmptyText }}</div>
    </section>

    <section v-if="!loading && !error" class="schedule-toolbar sp-card" data-workspace-filter>
      <div>
        <label class="schedule-toolbar__label" for="schedule-week">周课表 · {{ currentWeekHint }}</label>
        <div class="week-filter">
          <select id="schedule-week" v-model="selectedWeek" :disabled="printing">
            <option :value="null">全部周次</option>
            <option v-for="week in weekOptions" :key="week" :value="week">第{{ week }}周</option>
          </select>
          <button v-if="currentWeekInRange" class="sp-btn sp-btn--ghost" :disabled="printing || selectedWeek === currentWeekInRange" @click="selectedWeek = currentWeekInRange">回到本周</button>
        </div>
      </div>
      <div class="schedule-summary">
        <span><b>{{ filteredItems.length }}</b> 个课表安排</span>
        <span><b>{{ courseCount }}</b> 门课程</span>
        <span v-if="selectedWeek"><b>第{{ selectedWeek }}周</b></span>
      </div>
    </section>

    <StateBlock v-if="loading" type="loading" text="正在读取已发布课表…" />
    <section v-else-if="error" class="schedule-error sp-card">
      <StateBlock type="error" :text="error" />
      <button class="sp-btn sp-btn--ghost" @click="load">重新加载</button>
    </section>
    <StateBlock v-else-if="!items.length" type="empty" text="暂无已发布课表" />
    <StateBlock v-else-if="!filteredItems.length" type="empty" :text="`第${selectedWeek}周没有课程安排`" />

    <section v-else class="week-board" aria-label="一周课程，窄屏可横向滚动" tabindex="0">
      <article v-for="day in days" :key="day.value" class="day-column" :class="{ 'is-empty': !dayItems(day.value).length }">
        <header class="day-column__head">
          <span>{{ day.label }}</span>
          <small>{{ dayItems(day.value).length ? `${dayItems(day.value).length}项` : '无课' }}</small>
        </header>
        <div v-if="dayItems(day.value).length" class="day-column__list">
          <div v-for="item in dayItems(day.value)" :key="itemKey(item)" class="course-card" :class="sourceClass(item)">
            <div class="course-card__slot">{{ slotLabel(item) }}</div>
            <div v-if="slotDetail(item)" class="course-card__time">{{ slotDetail(item) }}</div>
            <div class="course-card__name">{{ item.courseName || '未命名课程' }}</div>
            <div class="course-card__meta">
              <span>{{ item.classroom || '教室待定' }}</span>
              <span>{{ item.teacherName || '教师待定' }}</span>
            </div>
            <div class="course-card__weeks">{{ weekLabel(item) }}</div>
            <span v-if="item.source === 'ENROLLED'" class="course-card__source">选课课程</span>
          </div>
        </div>
        <div v-else class="day-column__empty">暂无课程</div>
      </article>
    </section>

    <section v-if="!loading && !error && items.length" class="schedule-note sp-card">
      <strong>看课表时请注意</strong>
      <span>单双周、起止周以每门课程卡片为准；钟点来自学校当前生效作息。多校区同一节次时间不一致时，本页会明确显示“按校区作息”，不会擅自猜测。调停课生效后请以最新发布结果和消息通知为准。</span>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import StateBlock from '../../components/StateBlock.vue'
import { portalApi } from '../../services/portalApi'
import { useUiStore } from '../../stores/ui'

const router = useRouter()
const ui = useUiStore()
const loading = ref(true)
const error = ref('')
const printing = ref(false)
const schedule = ref({ items: [], timeBands: [] })
const selectedWeek = ref(null)

const days = [
  { value: 1, label: '周一' }, { value: 2, label: '周二' }, { value: 3, label: '周三' },
  { value: 4, label: '周四' }, { value: 5, label: '周五' }, { value: 6, label: '周六' },
  { value: 7, label: '周日' }
]

const items = computed(() => Array.isArray(schedule.value.items) ? schedule.value.items : [])
const todayItems = computed(() => Array.isArray(schedule.value.todayItems) ? schedule.value.todayItems : [])
const timeBands = computed(() => Array.isArray(schedule.value.timeBands) ? schedule.value.timeBands : [])
const maxWeek = computed(() => Math.max(
  1,
  Number(schedule.value.teachingWeeks || 0),
  ...items.value.map((item) => Number(item.endWeek) || 0)
))
const weekOptions = computed(() => Array.from({ length: Math.min(maxWeek.value, 30) }, (_, index) => index + 1))
const currentWeekInRange = computed(() => {
  const week = Number(schedule.value.currentWeek)
  return weekOptions.value.includes(week) ? week : null
})
const filteredItems = computed(() => selectedWeek.value == null
  ? items.value
  : items.value.filter((item) => occursInWeek(item, selectedWeek.value)))
const courseCount = computed(() => new Set(filteredItems.value.map((item) => `${item.courseName || ''}|${item.teacherName || ''}`)).size)
const currentWeekHint = computed(() => {
  const week = schedule.value.currentWeek
  if (week == null) return '校历周次尚未确认，当前展示全部周次'
  if (Number(week) === 0) return '学期尚未开始，当前展示全部周次'
  return `当前第${week}周`
})
const todayDateText = computed(() => {
  const value = String(schedule.value.todayDate || '')
  if (!value) return '日期待确认'
  const date = new Date(`${value}T00:00:00`)
  if (Number.isNaN(date.getTime())) return value
  return `${date.getMonth() + 1}月${date.getDate()}日 ${days[date.getDay() === 0 ? 6 : date.getDay() - 1]?.label || ''}`
})
const todayHeading = computed(() => loading.value ? '正在读取今天的课程' : (todayItems.value.length ? `今天有 ${todayItems.value.length} 节课` : '今天没有课程安排'))
const todayNote = computed(() => {
  const source = String(schedule.value.calendarSource || 'NORMAL')
  if (source === 'HOLIDAY') return '学校校历标记今天为节假日，正式课表不执行。'
  if (source === 'SWAP_SOURCE') return '学校校历标记今天为调休停课日，正式课表不执行。'
  if (source === 'OUT_OF_TERM') return '今天不在当前学期教学日期范围内。'
  if (todayItems.value.length) return '已按学校校历、单双周和最新正式课表筛选。'
  return '已核对学校校历和最新正式课表。'
})
const todayEmptyText = computed(() => {
  if (!items.value.length) return schedule.value.note || '当前学期暂无已发布课表'
  return todayNote.value
})

function occursInWeek(item, week) {
  const start = Number(item.startWeek) || 1
  const end = Number(item.endWeek) || maxWeek.value
  if (week < start || week > end) return false
  if (item.weekParity === 'ODD') return week % 2 === 1
  if (item.weekParity === 'EVEN') return week % 2 === 0
  return true
}

function dayItems(weekday) {
  return filteredItems.value
    .filter((item) => Number(item.weekday) === weekday)
    .sort((a, b) => Number(a.slotNo || 0) - Number(b.slotNo || 0)
      || Number(a.startWeek || 0) - Number(b.startWeek || 0))
}

function itemKey(item) {
  return item.itemId || [item.weekday, item.slotNo, item.startWeek, item.endWeek, item.courseName, item.source].join('-')
}

function weekLabel(item) {
  const parity = item.weekParity === 'ODD' ? '单周' : item.weekParity === 'EVEN' ? '双周' : '全周'
  return `第${item.startWeek || 1}—${item.endWeek || maxWeek.value}周 · ${parity}`
}

function sourceClass(item) {
  return item.source === 'ENROLLED' ? 'is-enrolled' : ''
}

function bandsForSlot(item) {
  const slotNo = Number(item.slotNo)
  return timeBands.value.filter((band) => Number(band.slotNo) === slotNo)
}

function timeText(band) {
  const start = String(band?.startTime || '').trim()
  const end = String(band?.endTime || '').trim()
  return start && end ? `${start}–${end}` : ''
}

function distinctSlotTimes(item) {
  return [...new Set(bandsForSlot(item).map(timeText).filter(Boolean))]
}

function slotLabel(item) {
  const bands = bandsForSlot(item)
  const base = bands[0]?.slotName || `第${Number(item.slotNo) || '—'}节`
  const times = distinctSlotTimes(item)
  if (times.length === 1) return `${base} · ${times[0]}`
  if (times.length > 1) return `${base} · 按校区作息`
  return base
}

function slotDetail(item) {
  const bands = bandsForSlot(item)
  const times = distinctSlotTimes(item)
  if (times.length <= 1) return ''
  return bands
    .map((band) => `${band.campusCode || band.bandName || '默认校区'} ${timeText(band) || '时间待定'}`)
    .join('；')
}

function goAll() {
  router.push('/academic/all')
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    schedule.value = await portalApi.academicSchedule() || { items: [], timeBands: [] }
    const currentWeek = Number(schedule.value.currentWeek)
    selectedWeek.value = Number.isFinite(currentWeek) && currentWeek >= 1 && currentWeek <= maxWeek.value
      ? currentWeek
      : null
  } catch (exception) {
    error.value = exception?.message || '课表读取失败，请稍后重试'
  } finally {
    loading.value = false
  }
}

function appendText(parent, tag, text) {
  const element = parent.ownerDocument.createElement(tag)
  element.textContent = text
  parent.appendChild(element)
  return element
}

async function printSchedule() {
  if (printing.value || loading.value || error.value || !filteredItems.value.length) return
  // Capture display values before the asynchronous audit request. The printed view
  // must match the audited week even if data reloads while that request is pending.
  const printWeek = selectedWeek.value
  const printRows = filteredItems.value.slice()
    .sort((a, b) => Number(a.weekday) - Number(b.weekday) || Number(a.slotNo) - Number(b.slotNo))
    .map((item) => {
      const day = days.find((entry) => entry.value === Number(item.weekday))
      return [day?.label || `周${item.weekday}`, slotLabel(item), item.courseName || '—',
        item.classroom || '—', item.teacherName || '—', weekLabel(item)].map(String)
    })
  const printWindow = window.open('', '_blank')
  if (!printWindow) {
    ui.notify('浏览器阻止了打印窗口，请允许弹出窗口后重试')
    return
  }
  printWindow.opener = null
  printWindow.document.title = '个人课表生成中'
  appendText(printWindow.document.body, 'p', '正在生成带留痕的个人课表，请稍候…')
  printing.value = true
  try {
    const audit = await portalApi.academicSchedulePrint({
      reason: printWeek ? `个人课表-第${printWeek}周` : '个人课表-全部周次'
    })
    const documentRef = printWindow.document
    documentRef.head.textContent = ''
    documentRef.body.textContent = ''
    documentRef.title = printWeek ? `个人课表-第${printWeek}周` : '个人课表'
    const style = documentRef.createElement('style')
    style.textContent = 'body{font-family:Segoe UI,Microsoft YaHei,sans-serif;padding:24px;color:#111}h1{font-size:20px;margin:0 0 8px}.meta{color:#666;font-size:12px;margin-bottom:16px}table{width:100%;border-collapse:collapse;font-size:13px}th,td{border:1px solid #ddd;padding:7px 8px;text-align:left}th{background:#f5f7fa}.wm{position:fixed;inset:28% 8%;font-size:38px;color:rgba(0,0,0,.07);transform:rotate(-24deg);pointer-events:none;text-align:center}'
    documentRef.head.appendChild(style)
    const body = documentRef.body
    const watermark = appendText(body, 'div', audit?.watermark || '')
    watermark.className = 'wm'
    appendText(body, 'h1', printWeek ? `个人课表 · 第${printWeek}周` : '个人课表 · 全部周次')
    const meta = appendText(body, 'div', `留痕时间：${audit?.loggedAt || '—'} · 仅供本人查询使用`)
    meta.className = 'meta'
    const table = documentRef.createElement('table')
    const tableHead = documentRef.createElement('thead')
    const headerRow = documentRef.createElement('tr')
    ;['星期', '节次与时间', '课程', '教室', '教师', '周次'].forEach((text) => appendText(headerRow, 'th', text))
    tableHead.appendChild(headerRow)
    table.appendChild(tableHead)
    const tableBody = documentRef.createElement('tbody')
    printRows.forEach((cells) => {
      const row = documentRef.createElement('tr')
      cells.forEach((text) => appendText(row, 'td', text))
      tableBody.appendChild(row)
    })
    table.appendChild(tableBody)
    body.appendChild(table)
    printWindow.focus()
    printWindow.print()
    ui.notify('课表打印留痕已记录')
  } catch (exception) {
    if (!printWindow.closed) printWindow.close()
    ui.notify(exception?.message || '打印失败')
  } finally {
    printing.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.schedule-page { max-width: 1600px; min-width: 0; margin: 0 auto; }
.schedule-hero { display: flex; justify-content: space-between; align-items: center; gap: 20px; padding: 0 0 18px; margin-bottom: 18px; border-bottom: 1px solid var(--line); }
.schedule-hero__eyebrow { color: var(--t3); font-size: 12px; }
.schedule-hero h1 { margin: 5px 0; color: var(--t1); font-size: 22px; line-height: 1.4; }
.schedule-hero p { margin: 0; color: var(--t3); font-size: 13px; }
.schedule-hero__actions { display: flex; gap: 8px; flex-wrap: wrap; }
.today-board { margin-bottom: 16px; padding: 18px 20px; border: 1px solid var(--line); border-radius: 12px; background: var(--surface, var(--bg-card)); }
.today-board__head { display: flex; justify-content: space-between; gap: 16px; align-items: flex-start; }
.today-board__eyebrow { color: var(--pri); font-size: 12px; font-weight: 600; }
.today-board h2 { margin: 6px 0; color: var(--t1); font-size: 18px; }
.today-board p { margin: 0; color: var(--t3); font-size: 13px; line-height: 1.6; }
.today-board__week { flex-shrink: 0; padding: 6px 9px; border-radius: 6px; background: var(--pri-50); color: var(--pri); font-size: 12px; }
.today-course-list { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 10px; margin-top: 16px; }
.today-course { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; padding: 14px; border: 1px solid var(--line); border-left: 3px solid var(--pri); border-radius: 8px; background: var(--field-bg, var(--bg-page)); }
.today-course__time { width: 100%; color: var(--pri); font-size: 12px; font-weight: 600; }
.today-course__body { min-width: 0; flex: 1; }
.today-course__body strong, .today-course__body span { display: block; overflow-wrap: anywhere; }
.today-course__body strong { color: var(--t1); font-size: 14px; }
.today-course__body span { margin-top: 5px; color: var(--t3); font-size: 12px; line-height: 1.5; }
.today-course__source, .course-card__source { padding: 3px 6px; border: 1px solid var(--line); border-radius: 4px; background: var(--surface, var(--bg-card)); color: var(--pri); font-size: 12px; }
.today-empty { margin-top: 16px; padding: 20px; border: 1px dashed var(--line); border-radius: 8px; color: var(--t3); text-align: center; font-size: 13px; }
.schedule-toolbar { display: flex; justify-content: space-between; align-items: flex-end; flex-wrap: wrap; gap: 16px; margin-bottom: 16px; background: var(--surface, var(--bg-card)); }
.schedule-toolbar__label { display: block; margin-bottom: 8px; color: var(--t2); font-size: 13px; font-weight: 600; }
.week-filter { display: flex; align-items: center; gap: 8px; }
.week-filter select { min-width: 160px; height: 36px; border: 1px solid var(--line); border-radius: 6px; padding: 0 10px; background: var(--field-bg, var(--bg-page)); color: var(--t1); font: inherit; font-size: 13px; }
.schedule-page :is(button, select, [tabindex]):focus-visible { outline: 2px solid var(--pri); outline-offset: 3px; }
.schedule-summary { display: flex; flex-wrap: wrap; gap: 16px; color: var(--t3); font-size: 13px; }
.schedule-summary b { color: var(--t1); }
.schedule-error { display: flex; flex-direction: column; align-items: center; gap: 12px; background: var(--surface, var(--bg-card)); }
.week-board { display: grid; grid-template-columns: repeat(7, minmax(155px, 1fr)); gap: 10px; align-items: start; overflow-x: auto; padding-bottom: 10px; }
.day-column { min-width: 155px; border: 1px solid var(--line); border-radius: 10px; background: var(--surface, var(--bg-card)); overflow: hidden; }
.day-column.is-empty { background: var(--field-bg, var(--bg-page)); }
.day-column__head { display: flex; justify-content: space-between; align-items: center; padding: 12px; border-bottom: 1px solid var(--line); color: var(--t1); font-size: 13px; font-weight: 600; }
.day-column__head small { color: var(--t3); font-size: 12px; font-weight: 400; }
.day-column__list { display: flex; flex-direction: column; gap: 8px; padding: 8px; }
.day-column__empty { padding: 32px 8px; text-align: center; color: var(--t3); font-size: 12px; }
.course-card { padding: 12px 10px; border-left: 3px solid var(--pri); border-radius: 6px; background: var(--pri-50); overflow-wrap: anywhere; }
.course-card.is-enrolled { border-left-style: dashed; }
.course-card__slot { color: var(--pri); font-size: 12px; font-weight: 600; line-height: 1.5; }
.course-card__time { margin-top: 4px; color: var(--t3); font-size: 12px; line-height: 1.5; }
.course-card__name { margin-top: 7px; color: var(--t1); font-size: 14px; font-weight: 600; line-height: 1.5; }
.course-card__meta { display: flex; flex-direction: column; gap: 3px; margin-top: 10px; color: var(--t3); font-size: 12px; }
.course-card__weeks { margin-top: 10px; color: var(--t3); font-size: 12px; line-height: 1.5; }
.course-card__source { display: inline-flex; margin-top: 8px; }
.schedule-note { display: flex; gap: 12px; margin-top: 16px; background: var(--surface, var(--bg-card)); color: var(--t3); font-size: 13px; line-height: 1.7; }
.schedule-note strong { color: var(--t1); white-space: nowrap; }
@media (max-width: 760px) {
  .schedule-hero { align-items: flex-start; flex-direction: column; gap: 12px; }
  .today-board { padding: 16px; }
  .today-board__head { flex-wrap: wrap; gap: 10px; }
  .today-course-list { grid-template-columns: minmax(0, 1fr); }
  .schedule-note { flex-direction: column; gap: 5px; }
}
</style>
