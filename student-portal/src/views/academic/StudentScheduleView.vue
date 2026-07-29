<template>
  <div class="sp-page schedule-page">
    <section class="schedule-hero">
      <div>
        <div class="schedule-hero__eyebrow">教务学业 · 我的课表</div>
        <h1>本学期课程安排</h1>
        <p>{{ schedule.note || currentWeekHint }}</p>
      </div>
      <div class="schedule-hero__actions">
        <button class="sp-btn sp-btn--ghost" @click="goAll">全部教务服务</button>
        <button class="sp-btn" :disabled="printing || loading || !filteredItems.length" @click="printSchedule">
          {{ printing ? '生成中…' : '打印当前课表视图' }}
        </button>
      </div>
    </section>

    <section class="schedule-toolbar sp-card">
      <div>
        <div class="schedule-toolbar__label">查看周次 · {{ currentWeekHint }}</div>
        <div class="week-filter">
          <button :class="{ active: selectedWeek === null }" @click="selectedWeek = null">全部周次</button>
          <button v-for="week in weekOptions" :key="week" :class="{ active: selectedWeek === week }" @click="selectedWeek = week">
            第{{ week }}周
          </button>
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

    <section v-else class="week-board">
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

    <section v-if="items.length" class="schedule-note sp-card">
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
const timeBands = computed(() => Array.isArray(schedule.value.timeBands) ? schedule.value.timeBands : [])
const maxWeek = computed(() => Math.max(
  1,
  Number(schedule.value.teachingWeeks || 0),
  ...items.value.map((item) => Number(item.endWeek) || 0)
))
const weekOptions = computed(() => Array.from({ length: Math.min(maxWeek.value, 30) }, (_, index) => index + 1))
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
  if (printing.value || !filteredItems.value.length) return
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
      reason: selectedWeek.value ? `个人课表-第${selectedWeek.value}周` : '个人课表-全部周次'
    })
    const documentRef = printWindow.document
    documentRef.head.textContent = ''
    documentRef.body.textContent = ''
    documentRef.title = selectedWeek.value ? `个人课表-第${selectedWeek.value}周` : '个人课表'
    const style = documentRef.createElement('style')
    style.textContent = 'body{font-family:Segoe UI,Microsoft YaHei,sans-serif;padding:24px;color:#111}h1{font-size:20px;margin:0 0 8px}.meta{color:#666;font-size:12px;margin-bottom:16px}table{width:100%;border-collapse:collapse;font-size:13px}th,td{border:1px solid #ddd;padding:7px 8px;text-align:left}th{background:#f5f7fa}.wm{position:fixed;inset:28% 8%;font-size:38px;color:rgba(0,0,0,.07);transform:rotate(-24deg);pointer-events:none;text-align:center}'
    documentRef.head.appendChild(style)
    const body = documentRef.body
    const watermark = appendText(body, 'div', audit?.watermark || '')
    watermark.className = 'wm'
    appendText(body, 'h1', selectedWeek.value ? `个人课表 · 第${selectedWeek.value}周` : '个人课表 · 全部周次')
    const meta = appendText(body, 'div', `留痕时间：${audit?.loggedAt || '—'} · 仅供本人查询使用`)
    meta.className = 'meta'
    const table = documentRef.createElement('table')
    const tableHead = documentRef.createElement('thead')
    const headerRow = documentRef.createElement('tr')
    ;['星期', '节次与时间', '课程', '教室', '教师', '周次'].forEach((text) => appendText(headerRow, 'th', text))
    tableHead.appendChild(headerRow)
    table.appendChild(tableHead)
    const tableBody = documentRef.createElement('tbody')
    filteredItems.value.slice().sort((a, b) => Number(a.weekday) - Number(b.weekday) || Number(a.slotNo) - Number(b.slotNo)).forEach((item) => {
      const row = documentRef.createElement('tr')
      const day = days.find((entry) => entry.value === Number(item.weekday))
      ;[day?.label || `周${item.weekday}`, slotLabel(item), item.courseName || '—', item.classroom || '—', item.teacherName || '—', weekLabel(item)]
        .forEach((text) => appendText(row, 'td', String(text)))
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
.schedule-page { max-width: 1440px; margin: 0 auto; }
.schedule-hero { display: flex; justify-content: space-between; align-items: flex-start; gap: 24px; padding: 24px 26px; margin-bottom: 16px; border: 1px solid var(--line); border-radius: 16px; background: linear-gradient(135deg, #fff, var(--pri-50)); box-shadow: 0 1px 3px rgba(16,24,40,.05); }
.schedule-hero__eyebrow { color: var(--pri); font-size: 12px; font-weight: 600; letter-spacing: .08em; }
.schedule-hero h1 { margin: 8px 0 6px; color: var(--t1); font-size: 24px; }
.schedule-hero p { margin: 0; color: var(--t3); font-size: 13px; }
.schedule-hero__actions { display: flex; gap: 10px; flex-wrap: wrap; }
.schedule-toolbar { display: flex; justify-content: space-between; align-items: flex-end; gap: 20px; margin-bottom: 16px; }
.schedule-toolbar__label { margin-bottom: 9px; color: var(--t2); font-size: 13px; font-weight: 600; }
.week-filter { display: flex; flex-wrap: wrap; gap: 6px; }
.week-filter button { border: 1px solid var(--line); border-radius: 8px; padding: 6px 10px; background: #fff; color: var(--t2); cursor: pointer; font-size: 12px; }
.week-filter button.active { border-color: var(--pri); background: var(--pri-50); color: var(--pri); font-weight: 600; }
.schedule-summary { display: flex; gap: 16px; color: var(--t3); font-size: 12.5px; white-space: nowrap; }
.schedule-summary b { color: var(--t1); }
.schedule-error { display: flex; flex-direction: column; align-items: center; gap: 12px; }
.week-board { display: grid; grid-template-columns: repeat(7, minmax(150px, 1fr)); gap: 10px; align-items: start; overflow-x: auto; padding-bottom: 8px; }
.day-column { min-width: 150px; border: 1px solid var(--line); border-radius: 13px; background: #fff; overflow: hidden; }
.day-column.is-empty { background: #fafbfc; }
.day-column__head { display: flex; justify-content: space-between; align-items: center; padding: 11px 12px; border-bottom: 1px solid var(--line2); color: var(--t1); font-size: 13px; font-weight: 600; }
.day-column__head small { color: var(--t4); font-size: 11px; font-weight: 400; }
.day-column__list { display: flex; flex-direction: column; gap: 8px; padding: 9px; }
.day-column__empty { padding: 34px 8px; text-align: center; color: var(--t4); font-size: 12px; }
.course-card { position: relative; padding: 10px; border-left: 3px solid var(--pri); border-radius: 9px; background: var(--pri-50); }
.course-card.is-enrolled { border-left-color: var(--ok-fg); background: #edf9f1; }
.course-card__slot { color: var(--pri); font-size: 11px; font-weight: 600; }
.course-card__time { margin-top: 3px; color: var(--warning-fg, #a15c00); font-size: 10px; line-height: 1.4; }
.course-card__name { margin-top: 5px; color: var(--t1); font-size: 13px; font-weight: 600; line-height: 1.4; }
.course-card__meta { display: flex; flex-direction: column; gap: 2px; margin-top: 7px; color: var(--t3); font-size: 11px; }
.course-card__weeks { margin-top: 7px; color: var(--t4); font-size: 10.5px; }
.course-card__source { display: inline-flex; margin-top: 7px; padding: 2px 6px; border-radius: 9px; background: #fff; color: var(--ok-fg); font-size: 10px; }
.schedule-note { display: flex; gap: 12px; margin-top: 16px; color: var(--t3); font-size: 12.5px; }
.schedule-note strong { color: var(--t1); white-space: nowrap; }
@media (max-width: 1100px) { .week-board { grid-template-columns: repeat(7, 180px); } }
</style>
