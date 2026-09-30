<template>
  <div data-academic-page class="sp-page academic-prototype schedule-page">
    <AcademicPrototypeHeader :title="selectedLesson ? '正式课次详情' : '我的课表'" group="注册与安排" :object="!!selectedLesson" :description="selectedLesson ? '核对本次上课地点、时间与正式来源。' : '今天去哪里上课，以正式课表为准。'" :term="schedule.termCode" :loading="loading" @refresh="load" />
    <StateBlock v-if="loading" type="loading" text="正在读取已发布课表…" />
    <section v-else-if="error" class="card pad"><StateBlock type="error" :text="error" /><button class="btn" @click="load">重新加载</button></section>
    <div v-else-if="selectedLesson" class="stack">
      <div class="notice"><AcademicPrototypeIcon name="circle-info" />正式课次 · 学校课表发布后形成。当前展示不会创建新课次。</div>
      <div class="grid2">
        <section class="card">
          <header class="card-head"><h2>{{ selectedLesson.courseName || '课程名称待公布' }}</h2></header>
          <div class="card-body">
            <dl class="definition">
              <dt>上课日期</dt><dd>{{ selectedLessonDate || selectedLesson.sessionDate || '具体日期以正式课次通知为准' }} · {{ days.find(day => day.value === Number(selectedLesson.weekday))?.label || '星期待确认' }}</dd>
              <dt>上课时间</dt><dd>{{ slotLabel(selectedLesson) }}</dd>
              <dt v-if="slotDetail(selectedLesson)">校区作息</dt><dd v-if="slotDetail(selectedLesson)">{{ slotDetail(selectedLesson) }}</dd>
              <dt>教室</dt><dd>{{ selectedLesson.classroom || '待公布' }}</dd>
              <dt>任课教师</dt><dd>{{ selectedLesson.teacherName || '待公布' }}</dd>
              <dt>教学班</dt><dd>{{ selectedLesson.teachingClassName || selectedLesson.className || '待学校提供' }}</dd>
              <dt>当前周次</dt><dd>{{ selectedWeek ? '第' + selectedWeek + '周' : weekLabel(selectedLesson) }}</dd>
              <dt>正式来源</dt><dd><span class="tag green">课表已发布</span> {{ selectedLesson.source === 'ENROLLED' ? '本人选课' : '学校教学安排' }}</dd>
              <dt>调整记录</dt><dd>{{ selectedLesson.changeDescription || selectedLesson.adjustmentNote || '当前接口未提供课次调整详情，请核对学校通知。' }}</dd>
            </dl>
          </div>
        </section>
        <section class="card">
          <header class="card-head"><h2>接下来</h2></header>
          <div class="card-body stack"><p class="muted">考勤由本课任课教师提交。地点疑问先核对本课正式调整记录。</p><RouterLink class="btn primary" to="/academic/attendance">{{ returnedFromAttendance ? '返回考勤记录' : '查看本人考勤' }}</RouterLink><button class="btn link" @click="selectedLessonId = ''">返回我的课表</button></div>
        </section>
      </div>
    </div>
    <div v-else class="stack">
      <div class="toolbar" data-workspace-filter>
        <button class="btn small" aria-label="上一周" :disabled="!selectedWeek || selectedWeek <= 1" @click="moveWeek(-1)"><AcademicPrototypeIcon name="angle-left" /></button>
        <b class="week-label">{{ selectedWeek ? '第' + selectedWeek + '周' : '全部周次' }}{{ weekRange ? ' · ' + weekRange : '' }}</b>
        <button class="btn small" aria-label="下一周" :disabled="!selectedWeek || selectedWeek >= maxWeek" @click="moveWeek(1)"><AcademicPrototypeIcon name="angle-right" /></button>
        <button class="btn small" :disabled="!currentWeekInRange || selectedWeek === currentWeekInRange" @click="selectedWeek = currentWeekInRange">回到本周</button>
        <span class="grow"></span>
        <span v-if="items.length" class="tag green">正式版本 · 已发布</span>
        <button class="btn small" :disabled="printing || !filteredItems.length" @click="printSchedule"><AcademicPrototypeIcon name="file-arrow-down" />{{ printing ? '生成中…' : '打印本人课表' }}</button>
      </div>
      <section class="card schedule-grid-wrap">
        <StateBlock v-if="!items.length" type="empty" :text="schedule.note || '暂无已发布课表'" />
        <StateBlock v-else-if="!filteredItems.length" type="empty" :text="`第${selectedWeek}周没有课程安排`" />
        <div v-else class="weekgrid" :style="{ gridTemplateColumns: '74px repeat(' + visibleDays.length + ', minmax(80px, 1fr))' }" role="table" aria-label="本人正式周课表">
          <div class="wh" role="columnheader">节次</div>
          <div v-for="day in visibleDays" :key="'head-' + day.value" class="wh" role="columnheader">{{ day.label }} <small>{{ dayDate(day.value) }}</small></div>
          <template v-for="slot in slotRows" :key="slot">
            <div class="wt" role="rowheader"><span>{{ slotName(slot) }}</span><small>{{ slotClock(slot) }}</small></div>
            <div v-for="day in visibleDays" :key="day.value" class="schedule-cell" role="cell">
              <button v-for="item in cellItems(day.value, slot)" :key="itemKey(item)" class="lesson" :class="{teal: day.value % 2 === 0}" @click="selectedLessonId = itemKey(item)">
                <strong>{{ item.courseName || '课程名称待公布' }}</strong><small>{{ item.classroom || '教室待定' }}<br>{{ item.teacherName || '教师待定' }} · {{ selectedWeek ? '第' + selectedWeek + '周' : weekLabel(item) }}</small>
              </button>
            </div>
          </template>
        </div>
      </section>
      <div class="notice"><AcademicPrototypeIcon name="circle-info" />单双周、起止周按学校正式安排筛选；调停课生效后以最新发布结果为准。历史调整详情以学校通知为准。</div>
      <div v-if="calendarError" class="notice amber" role="status"><AcademicPrototypeIcon name="circle-info" />{{ calendarError }}</div>
      <div class="row muted"><AcademicPrototypeIcon name="circle-info" />点击课次可看日期节次、上课地点和关联考勤。</div>
      <details v-if="todayItems.length" class="today-summary"><summary>今天 · {{ todayDateText }} · 今天有 {{ todayItems.length }} 节课</summary><div class="stack pad"><button v-for="item in todayItems" :key="itemKey(item)" class="btn" @click="selectedLessonId = itemKey(item)">{{ slotLabel(item) }} · {{ item.courseName }}</button><small>{{ todayNote }}</small></div></details>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import AcademicPrototypeHeader from '../../components/academic/AcademicPrototypeHeader.vue'
import AcademicPrototypeIcon from '../../components/academic/AcademicPrototypeIcon.vue'
import StateBlock from '../../components/StateBlock.vue'
import { createStudentAcademicCommandGuard, readStudentAcademicSnapshot, studentAcademicIdentity } from '../../components/academic/studentAcademicCommandGuard'
import { academicErrorKind, academicErrorMessage } from '../../components/academic/studentAcademicUi'
import { portalApi } from '../../services/portalApi'
import { createInAppPrintFrame } from '../../services/printInApp'
import { useSessionStore } from '../../stores/session'
import { useUiStore } from '../../stores/ui'

const ui = useUiStore()
const session = useSessionStore()
const guard = createStudentAcademicCommandGuard(() => studentAcademicIdentity(session))
const loading = ref(true)
const error = ref('')
const calendarError = ref('')
const printing = ref(false)
const schedule = ref({ items: [], timeBands: [] })
const weekCalendar = ref([])
const selectedWeek = ref(null)
const selectedLessonId = ref('')
const route = useRoute()
const selectedLesson = computed(() => [...items.value, ...todayItems.value].find((item) => itemKey(item) === selectedLessonId.value))
const returnedFromAttendance = computed(() => route.query.from === 'attendance')

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
const visibleDays = computed(() => filteredItems.value.some(item => Number(item.weekday) > 5) ? days : days.slice(0, 5))
const slotRows = computed(() => [...new Set([...timeBands.value.map(b => Number(b.slotNo)), ...filteredItems.value.map(item => Number(item.slotNo))])].filter(n => Number.isInteger(n) && n > 0).sort((a,b) => a-b))
function cellItems(day, slot) { return dayItems(day).filter(item => Number(item.slotNo) === slot) }
function slotName(slot) { return bandsForSlot({ slotNo: slot })[0]?.slotName || '第' + slot + '节' }
function slotClock(slot) { const times = [...new Set(bandsForSlot({slotNo:slot}).map(band => band.startTime).filter(Boolean))]; return times.length === 1 ? times[0] : times.length > 1 ? '按校区作息' : '钟点待确认' }
const displayedWeek = computed(() => weekCalendar.value.find(week => Number(week.weekNo) === selectedWeek.value))
const weekRange = computed(() => displayedWeek.value ? [displayedWeek.value.startDate, displayedWeek.value.endDate].map(value => String(value).slice(5).replace('-', '/')).join('—') : '')
const selectedLessonDate = computed(() => selectedLesson.value ? dateForWeekday(Number(selectedLesson.value.weekday)) : '')
function dateForWeekday(day) {
  const startDate = String(displayedWeek.value?.startDate || '').slice(0, 10)
  if (!/^\d{4}-\d{2}-\d{2}$/.test(startDate) || !Number.isInteger(day) || day < 1 || day > 7) return ''
  const start = new Date(`${startDate}T00:00:00`)
  if (Number.isNaN(start.getTime())) return ''
  start.setDate(start.getDate() + (day - (start.getDay() || 7) + 7) % 7)
  return start.toLocaleDateString('en-CA')
}
function dayDate(day) {
  const date = dateForWeekday(day)
  return date ? date.slice(5).replace('-', '/') : ''
}
function moveWeek(delta) { const week = Number(selectedWeek.value) + delta; if (weekOptions.value.includes(week)) selectedWeek.value = week }
const todayDateText = computed(() => {
  const value = String(schedule.value.todayDate || '')
  if (!value) return '日期待确认'
  const date = new Date(`${value}T00:00:00`)
  if (Number.isNaN(date.getTime())) return value
  return `${date.getMonth() + 1}月${date.getDate()}日 ${days[date.getDay() === 0 ? 6 : date.getDay() - 1]?.label || ''}`
})
const todayNote = computed(() => {
  const source = String(schedule.value.calendarSource || 'NORMAL')
  if (source === 'HOLIDAY') return '学校校历标记今天为节假日，正式课表不执行。'
  if (source === 'SWAP_SOURCE') return '学校校历标记今天为调休停课日，正式课表不执行。'
  if (source === 'OUT_OF_TERM') return '今天不在当前学期教学日期范围内。'
  if (todayItems.value.length) return '已按学校校历、单双周和最新正式课表筛选。'
  return '已核对学校校历和最新正式课表。'
})
function occursInWeek(item, week, fallbackEndWeek = maxWeek.value) {
  const start = Number(item.startWeek) || 1
  const end = Number(item.endWeek) || Number(fallbackEndWeek) || 1
  if (week < start || week > end) return false
  if (item.weekParity === 'ODD') return week % 2 === 1
  if (item.weekParity === 'EVEN') return week % 2 === 0
  return true
}

function itemsForWeek(sourceItems, week, fallbackEndWeek) {
  const list = Array.isArray(sourceItems) ? sourceItems : []
  return week == null ? list : list.filter((item) => occursInWeek(item, week, fallbackEndWeek))
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

async function load() {
  loading.value = true
  error.value = ''
  calendarError.value = ''
  const read = await readStudentAcademicSnapshot(guard, () => Promise.allSettled([portalApi.academicSchedule(), portalApi.academicCalendar()]), 'academic-schedule')
  if (read.stale) return false
  if (!read.ok) {
    error.value = academicErrorMessage(read.error, '课表读取失败，请稍后重试')
    loading.value = false
    return false
  }
  const [scheduleResult, calendarResult] = read.value
  if (scheduleResult.status === 'rejected') {
    if (academicErrorKind(scheduleResult.reason) === 'forbidden') clearSensitive(scheduleResult.reason)
    else { error.value = academicErrorMessage(scheduleResult.reason, '课表读取失败，请稍后重试'); loading.value = false }
    return false
  }
  if (calendarResult.status === 'rejected' && academicErrorKind(calendarResult.reason) === 'forbidden') {
    clearSensitive(calendarResult.reason)
    return false
  }
  schedule.value = scheduleResult.value || { items: [], timeBands: [] }
  weekCalendar.value = calendarResult.status === 'fulfilled' ? calendarResult.value?.weeks || [] : []
  calendarError.value = calendarResult.status === 'rejected' ? academicErrorMessage(calendarResult.reason, '校历周次读取失败，课表课程仍按正式课表展示。') : ''
  const currentWeek = Number(schedule.value.currentWeek)
  selectedWeek.value = Number.isFinite(currentWeek) && currentWeek >= 1 && currentWeek <= maxWeek.value
    ? currentWeek
    : null
  applyRouteContext()
  loading.value = false
  return true
}

function clearSensitive(exception) {
  guard.invalidate()
  schedule.value = { items: [], timeBands: [] }
  weekCalendar.value = []
  selectedLessonId.value = ''
  calendarError.value = ''
  printing.value = false
  loading.value = false
  error.value = academicErrorMessage(exception)
}

function appendText(parent, tag, text) {
  const element = parent.ownerDocument.createElement(tag)
  element.textContent = text
  parent.appendChild(element)
  return element
}

async function printSchedule() {
  if (printing.value || loading.value || error.value || !filteredItems.value.length) return
  const command = guard.beginCommand({ week: selectedWeek.value })
  const printWindow = createInAppPrintFrame('个人课表')
  printWindow.document.title = '个人课表生成中'
  appendText(printWindow.document.body, 'p', '正在生成带留痕的个人课表，请稍候…')
  printing.value = true
  try {
    const audit = await portalApi.academicSchedulePrint({
      reason: command.week ? `个人课表-第${command.week}周` : '个人课表-全部周次'
    })
    if (!guard.isCurrentCommand(command)) { if (!printWindow.closed) printWindow.close(); return }
    if (!Array.isArray(audit?.document?.items)) throw new Error('学校未返回本次正式课表查询件，不能使用页面旧数据打印')
    const documentData = audit.document
    const documentItems = itemsForWeek(documentData.items, command.week, documentData.teachingWeeks).slice().sort((a, b) => Number(a.weekday) - Number(b.weekday) || Number(a.slotNo) - Number(b.slotNo))
    const documentBands = Array.isArray(documentData.timeBands) ? documentData.timeBands : []
    const documentSlotLabel = (item) => {
      const bands = documentBands.filter((band) => Number(band.slotNo) === Number(item.slotNo))
      const base = bands[0]?.slotName || `第${Number(item.slotNo) || '—'}节`
      const times = [...new Set(bands.map(timeText).filter(Boolean))]
      return times.length === 1 ? `${base} · ${times[0]}` : times.length > 1 ? `${base} · 按校区作息` : base
    }
    const documentWeekLabel = (item) => {
      const parity = item.weekParity === 'ODD' ? '单周' : item.weekParity === 'EVEN' ? '双周' : '全周'
      return `第${item.startWeek || 1}—${item.endWeek || documentData.teachingWeeks || maxWeek.value}周 · ${parity}`
    }
    const documentRef = printWindow.document
    documentRef.head.textContent = ''
    documentRef.body.textContent = ''
    documentRef.title = command.week ? `个人课表-第${command.week}周` : '个人课表'
    const style = documentRef.createElement('style')
    style.textContent = 'body{font-family:Segoe UI,Microsoft YaHei,sans-serif;padding:24px;color:#111}h1{font-size:20px;margin:0 0 8px}.meta{color:#666;font-size:12px;margin-bottom:16px}table{width:100%;border-collapse:collapse;font-size:13px}th,td{border:1px solid #ddd;padding:7px 8px;text-align:left}th{background:#f5f7fa}.wm{position:fixed;inset:28% 8%;font-size:38px;color:rgba(0,0,0,.07);transform:rotate(-24deg);pointer-events:none;text-align:center}'
    documentRef.head.appendChild(style)
    const body = documentRef.body
    const watermark = appendText(body, 'div', audit?.watermark || '')
    watermark.className = 'wm'
    appendText(body, 'h1', command.week ? `个人课表 · 第${command.week}周` : '个人课表 · 全部周次')
    const meta = appendText(body, 'div', `留痕时间：${audit?.loggedAt || '—'} · 仅供本人查询使用`)
    meta.className = 'meta'
    const table = documentRef.createElement('table')
    const tableHead = documentRef.createElement('thead')
    const headerRow = documentRef.createElement('tr')
    ;['星期', '节次与时间', '课程', '教室', '教师', '周次'].forEach((text) => appendText(headerRow, 'th', text))
    tableHead.appendChild(headerRow)
    table.appendChild(tableHead)
    const tableBody = documentRef.createElement('tbody')
    documentItems.forEach((item) => {
      const row = documentRef.createElement('tr')
      const day = days.find((entry) => entry.value === Number(item.weekday))
      ;[day?.label || `周${item.weekday}`, documentSlotLabel(item), item.courseName || '—', item.classroom || '—', item.teacherName || '—', documentWeekLabel(item)]
        .forEach((text) => appendText(row, 'td', String(text)))
      tableBody.appendChild(row)
    })
    table.appendChild(tableBody)
    body.appendChild(table)
    printWindow.focus()
    printWindow.print()
    ui.notify('课表打印留痕已记录')
  } catch (exception) {
    if (!guard.isCurrentCommand(command)) { if (!printWindow.closed) printWindow.close(); return }
    if (!printWindow.closed) printWindow.close()
    if (academicErrorKind(exception) === 'forbidden') clearSensitive(exception)
    ui.notify(academicErrorMessage(exception, '打印失败'))
  } finally {
    if (guard.isCurrentCommand(command)) printing.value = false
  }
}

onMounted(load)
function applyRouteContext() {
  selectedLessonId.value = String(route.query.lesson || '')
  const requestedWeek = Number(route.query.week)
  if (Number.isSafeInteger(requestedWeek) && weekOptions.value.includes(requestedWeek)) selectedWeek.value = requestedWeek
}
watch(() => [route.query.lesson, route.query.week], applyRouteContext, { immediate: true })
onBeforeUnmount(() => guard.dispose())
</script>
<style src="../../components/academic/studentAcademicPrototype.css"></style>
<style scoped>
.schedule-grid-wrap{overflow:auto}.week-label{border:0;background:transparent;font-weight:700;max-width:180px;padding:6px}.schedule-cell{display:grid;gap:5px;align-content:start}.weekgrid .lesson{min-height:70px;line-height:1.55}.weekgrid .wh{font-size:13px}.weekgrid .wt small{font-size:11px;text-align:center}.today-summary{color:var(--muted);font-size:12px}.today-summary summary{cursor:pointer}
</style>
