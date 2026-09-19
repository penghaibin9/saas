<template>
  <div data-academic-page class="sp-page academic-prototype readonly-page">
    <AcademicPrototypeHeader :title="config.title" :group="['attendance','calendar'].includes(model) ? '注册与安排' : model === 'clearance' ? '成绩与考试' : '培养与毕业'" :description="config.description" :loading="loading" @refresh="load" />
    <StateBlock v-if="loading" type="loading" :text="'正在读取' + config.title + '…'" />
    <div v-else-if="error" class="card pad"><StateBlock type="error" :text="error" /><button class="btn" @click="load">重新加载</button></div>
    <div v-else class="stack">
      <template v-if="model === 'attendance'">
        <div class="notice"><AcademicPrototypeIcon name="circle-info" /><span>只能查看本人的已提交记录；未提交与无课不能记为缺勤。</span></div>
        <section class="card pad"><div class="metrics-inline"><div v-for="metric in attendanceMetrics" :key="metric.label" class="metric"><small>{{ metric.label }}</small><strong>{{ metric.value }}</strong></div></div></section>
        <section class="card table-wrap"><table class="table"><thead><tr><th>日期</th><th>课程</th><th>节次</th><th>本人状态</th><th>查看</th></tr></thead><tbody><tr v-for="(row, index) in rows" :key="rowKey(row, index)"><td>{{ pick(row, ['sessionDate', 'attendanceDate', 'date'], '未提供') }}</td><td>{{ primaryText(row) }}</td><td>{{ pick(row, ['slotLabel', 'slotNo'], '未提供') }}</td><td><span class="tag" :class="tagColor(row)">{{ statusText(row) }}</span></td><td><RouterLink v-if="attendanceScheduleRoute(row)" class="btn link small" :to="attendanceScheduleRoute(row)">正式课次</RouterLink><span v-else class="muted" title="该历史考勤未保留可核验的正式课位回链">课位回链未提供</span></td></tr></tbody></table><StateBlock v-if="!rows.length" type="empty" :text="config.emptyText" /></section>
      </template>
      <template v-else-if="model === 'calendar'">
        <div class="titleline"><h2>{{ calendarMonthLabel }}</h2><div class="row"><button class="btn small" aria-label="上个月" @click="shiftMonth(-1)"><AcademicPrototypeIcon name="angle-left" /></button><button class="btn small" aria-label="下个月" @click="shiftMonth(1)"><AcademicPrototypeIcon name="angle-right" /></button><span class="tag">{{ data.termLabel || '学期待提供' }}</span></div></div>
        <div v-if="data.hasTerm === false" class="notice amber">{{ data.note || '学校尚未设置当前学期，暂不能核对校历。' }}</div>
        <div class="calendar-grid"><div v-for="day in ['一','二','三','四','五','六','日']" :key="day" class="head">{{ day }}</div><div v-for="(cell,index) in calendarCells" :key="index" :class="{ today: cell.date === todayDate }"><strong>{{ cell.day || '' }}</strong><small v-for="event in cell.events" :key="event.eventId || event.startDate + event.remark">{{ primaryText(event) }}</small><small v-if="cell.week">教学第 {{ cell.week }} 周</small></div></div>
        <section class="card"><header class="card-head"><h2>本月需留意</h2></header><div class="card-body"><div v-for="(row,index) in monthEvents" :key="rowKey(row,index)" class="taskline"><AcademicPrototypeIcon name="calendar-days" /><div><strong>{{ row.startDate || row.eventDate }} · {{ primaryText(row) }}</strong><small>{{ row.remark || row.description || calendarType(row.eventType) }}<template v-if="row.swapToDate"> · 调至 {{ row.swapToDate }}</template></small></div></div><p v-if="!monthEvents.length" class="muted">本月暂无已返回的校历事件。</p><div class="taskline"><AcademicPrototypeIcon name="circle-info" /><div><strong>调休 / 补课</strong><small>实际节次以正式课表为准，不能简单按自然星期推导。</small></div></div></div></section>
        <div><RouterLink class="btn primary" to="/academic/schedule">查看正式课表</RouterLink></div>
      </template>
      <template v-else-if="model === 'credits'">
        <section class="card pad"><div class="titleline"><div><span class="label">已获得 / 方案要求</span><div class="callout-number">{{ data.earnedCredits ?? data.obtainedCredits ?? '待确认' }} <small>/ {{ data.requiredCredits ?? '待核验' }} 学分</small></div></div><span class="tag">仅正式结果计入</span></div><div class="spacer14"></div><div v-if="creditProgress !== null" class="progress"><i :style="{ width: creditProgress + '%' }"></i></div><p v-else class="muted">培养方案要求尚未完整核定，暂不计算完成比例。</p></section>
        <section class="card"><header class="card-head"><h2>模块修读情况</h2></header><div class="card-body"><p class="muted">当前未提供培养方案模块明细，请以学校适用方案核对。</p></div></section>
        <div class="notice"><AcademicPrototypeIcon name="circle-info" /><span>已选学分、已修读学分、已获得学分分别展示。实际毕业要求采用适用方案和历史身份。</span></div>
        <section v-if="rows.length" class="card"><header class="card-head"><h2>正式有效课程</h2></header><div class="table-wrap"><table class="table"><thead><tr><th>课程</th><th>课程代码</th><th>已获学分</th></tr></thead><tbody><tr v-for="(row,index) in rows" :key="rowKey(row,index)"><td>{{ primaryText(row) }}</td><td>{{ row.courseCode || '未提供' }}</td><td>{{ row.credit ?? row.earnedCredit ?? '待确认' }}</td></tr></tbody></table></div></section>
        <div><RouterLink class="btn primary" to="/academic/grades">查看正式成绩</RouterLink></div>
      </template>
      <template v-else-if="model === 'clearance'">
        <div class="notice"><AcademicPrototypeIcon name="circle-info" /><span>清考是课程补救考核，不是离校服务；不新增学生报名按钮。</span></div>
        <section class="card table-wrap"><table class="table"><thead><tr><th>课程</th><th>清考批次</th><th>结果</th><th>下一步</th></tr></thead><tbody><tr v-for="(row,index) in rows" :key="rowKey(row,index)"><td>{{ primaryText(row) }}</td><td>{{ row.batchName || row.termCode || '批次未提供' }}</td><td>{{ clearanceResult(row) }}</td><td><RouterLink class="btn link small" to="/academic/grades">查看成绩</RouterLink></td></tr></tbody></table><StateBlock v-if="!rows.length" type="empty" :text="config.emptyText" /></section>
      </template>
      <template v-else-if="model === 'warning'">
        <div v-if="warningPageReady" class="row between"><span>第 {{ warningPage }} 页 · 共 {{ warningTotal }} 条</span><div class="row"><button class="btn small" :disabled="warningPage <= 1" @click="changeWarningPage(warningPage - 1)">上一页</button><button class="btn small" :disabled="!data.hasMore" @click="changeWarningPage(warningPage + 1)">下一页</button></div></div>
        <div v-if="focusRecordId && !rows.some((row,index) => rowKey(row,index) === focusRecordId)" class="notice amber">当前页尚未定位原预警，请翻页核对；这不表示该预警已处理或不存在。</div>
        <div v-if="warningIsPartial" class="notice amber" role="status"><AcademicPrototypeIcon name="circle-info" /><span>当前接口返回 {{ rows.length }} 条，本人正式记录共 {{ warningTotal }} 条。请联系教务老师查询其余记录；本页不会把当前列表当作全部数据。</span></div>
        <StateBlock v-if="!rows.length" type="empty" :text="warningTotal ? '当前页没有预警记录，请返回上一页核对' : '当前没有学业预警'" />
        <section v-for="(row,index) in rows" :key="rowKey(row,index)" class="card" :class="{ 'is-target': rowKey(row,index) === focusRecordId }"><header class="card-head"><h2>有一项学业事项需要关注</h2></header><div class="card-body"><div class="row between"><h2>{{ primaryText(row) }}</h2><span class="tag" :class="tagColor(row)">{{ statusText(row) }}</span></div><dl class="definition"><dt>相关课程</dt><dd>{{ row.courseName || '以预警事项为准' }}</dd><dt>判定来源</dt><dd>{{ row.reason || row.triggerReason || '未提供' }}</dd><dt>责任老师</dt><dd>{{ row.responsibleTeacherName || row.teacherName || row.owner || '待学校提供' }}</dd><dt>当前建议</dt><dd>{{ row.requirement || row.handleRequirement || row.note || '请向学校责任老师核对处理要求' }}</dd></dl><footer class="form-foot"><RouterLink class="btn" to="/academic/grades">查看原成绩</RouterLink><RouterLink class="btn primary" to="/academic/makeup">打开补考重修</RouterLink></footer></div></section>
        <div class="notice"><AcademicPrototypeIcon name="circle-info" /><span>{{ config.note }}</span></div>
      </template>
      <div v-else class="notice amber">当前入口未绑定可用的教务页面，请返回学业总览。</div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import StateBlock from '../../components/StateBlock.vue'
import AcademicPrototypeHeader from '../../components/academic/AcademicPrototypeHeader.vue'
import AcademicPrototypeIcon from '../../components/academic/AcademicPrototypeIcon.vue'
import { createStudentAcademicCommandGuard, readStudentAcademicSnapshot, studentAcademicIdentity } from '../../components/academic/studentAcademicCommandGuard'

import { academicErrorKind, academicErrorMessage } from '../../components/academic/studentAcademicUi'
import { portalApi } from '../../services/portalApi'
import { useSessionStore } from '../../stores/session'

const route = useRoute()
const router = useRouter()
const session = useSessionStore()
const guard = createStudentAcademicCommandGuard(() => studentAcademicIdentity(session))
const loading = ref(true)
const error = ref('')
const data = ref({})
const focusRecordId = computed(() => String(route.query.warningId || route.query.recordId || ''))
const warningPage = computed(() => {
  const page = Number(route.query.warningPage || 1)
  return Number.isSafeInteger(page) && page >= 1 ? page : 1
})

const CONFIGS = {
  attendance: {
    title: '课堂考勤', heading: '查看本人课堂考勤记录',
    description: '只读展示教师已提交的本人课堂考勤，不允许学生端自行修改状态。',
    sectionTitle: '考勤明细', sectionDescription: '按课程和上课日期展示本人状态', emptyText: '暂无本人课堂考勤记录',
    loader: () => portalApi.academicAttendance(),
    note: '考勤状态来自教师提交的正式课堂考勤场次；存在异议请联系任课教师或辅导员。'
  },
  calendar: {
    title: '校历', heading: '查看当前学期教学校历',
    description: '展示学校发布的教学周、节假日、考试周和重要教学节点。',
    sectionTitle: '校历事件', sectionDescription: '按日期查看学校正式教学安排', emptyText: '当前学期暂无校历事件',
    loader: () => portalApi.academicCalendar(),
    note: '教学周次和日期以学校发布校历为准，客户端不自行推算节假日或考试周。'
  },
  clearance: {
    title: '清考结果', heading: '查看本人清考课程与结果',
    description: '只展示教务处已发布的本人清考安排和最终结果。',
    sectionTitle: '清考记录', sectionDescription: '本人课程、安排与发布结果', emptyText: '暂无本人清考记录',
    loader: () => portalApi.academicClearance(),
    note: '未发布成绩不在学生端展示；最终有效成绩以成绩查询件和教务归档为准。'
  },
  credits: {
    title: '学分修读', heading: '核对本人学分与培养要求',
    description: '展示已获学分、绩点和培养要求达成情况，不使用客户端自行拼接毕业结论。',
    sectionTitle: '学分明细', sectionDescription: '课程、类别和有效学分', emptyText: '暂无可展示的学分明细',
    loader: () => portalApi.academicCredits(),
    note: '学分与绩点取自当前有效成绩口径；毕业资格结论仍以学校正式审核为准。'
  },
  warning: {
    title: '学业预警', heading: '查看本人学业预警与处理要求',
    description: '展示预警原因、责任老师、处理要求和当前状态。',
    sectionTitle: '预警记录', sectionDescription: '按风险程度和时间展示本人预警', emptyText: '当前没有学业预警',
    loader: () => portalApi.academicWarning({ page: warningPage.value, pageSize: 50 }),
    note: '预警用于提前干预，不等同于处分或最终学籍结论；请按记录中的要求及时联系责任老师。'
  },
  graduation: {
    title: '毕业资格自查', heading: '逐项核对毕业条件与证据',
    description: '展示课程、学分和毕业条件的系统自查结果，不替代学校最终毕业资格审核。',
    sectionTitle: '毕业条件', sectionDescription: '逐项查看达成状态和证据来源', emptyText: '暂无毕业资格自查数据',
    loader: () => portalApi.academicGraduationAudit(),
    note: '自查结果用于发现缺口；毕业资格、证书和结业结论只能由学校正式审核发布。'
  }
}

const model = computed(() => String(route.meta.academicReadModel || ''))
const config = computed(() => CONFIGS[model.value] || {
  title: '教务数据', heading: '教务入口配置异常', description: '当前路由未绑定允许的只读教务模型。',
  sectionTitle: '数据', sectionDescription: '', emptyText: '暂无数据', note: '请联系管理员检查路由配置。',
  loader: null
})
const rows = computed(() => rowsOf(data.value))
const warningTotal = computed(() => {
  const value = Number(data.value?.total)
  return Number.isFinite(value) && value >= rows.value.length ? value : rows.value.length
})
const warningPageReady = computed(() => Number.isInteger(data.value?.page) && data.value.page === warningPage.value && data.value.pageSize === 50 && typeof data.value.hasMore === 'boolean')
const warningIsPartial = computed(() => model.value === 'warning' && !warningPageReady.value && warningTotal.value > rows.value.length)
function changeWarningPage(page) {
  if (loading.value || !warningPageReady.value || page < 1 || (page > warningPage.value && !data.value.hasMore)) return
  router.push({ path: route.path, query: { ...route.query, warningPage: String(page) } })
}
const metrics = computed(() => metricRows(model.value, data.value, rows.value))
const attendanceMetrics = computed(() => [
  { label: '已提交课次', value: rows.value.filter(row => !['UNSUBMITTED','NOT_SUBMITTED','DRAFT'].includes(String(row.status || row.attendanceStatus).toUpperCase())).length },
  metrics.value.find(item => item.label === '出勤') || { label: '出勤', value: 0 },
  { label: '迟到', value: rows.value.filter(row => String(row.status || row.attendanceStatus).toUpperCase() === 'LATE').length }
])
const todayDate = new Date().toLocaleDateString('en-CA')
const calendarMonth = ref(todayDate.slice(0,7))
const calendarMonthLabel = computed(() => calendarMonth.value.replace('-', ' 年 ') + ' 月')
const monthEvents = computed(() => rows.value.filter(row => String(row.startDate || row.eventDate || '').slice(0,7) <= calendarMonth.value && String(row.endDate || row.startDate || row.eventDate || '').slice(0,7) >= calendarMonth.value))
const calendarCells = computed(() => {
  const [year, month] = calendarMonth.value.split('-').map(Number)
  const offset = (new Date(year, month - 1, 1).getDay() + 6) % 7
  const count = new Date(year, month, 0).getDate()
  return Array.from({ length: Math.ceil((offset + count) / 7) * 7 }, (_, index) => {
    const day = index - offset + 1
    if (day < 1 || day > count) return { day: null, events: [] }
    const date = calendarMonth.value + '-' + String(day).padStart(2,'0')
    return { day, date, events: monthEvents.value.filter(event => String(event.startDate || event.eventDate).slice(0,10) === date), week: (data.value.weeks || []).find(week => String(week.startDate).slice(0,10) === date)?.weekNo }
  })
})
function shiftMonth(delta) { const [year, month] = calendarMonth.value.split('-').map(Number); const date = new Date(year, month - 1 + delta, 1); calendarMonth.value = date.getFullYear() + '-' + String(date.getMonth() + 1).padStart(2,'0') }
function tagColor(row) { return { success: 'green', danger: 'red', warn: 'amber', default: 'gray' }[statusTone(row)] }
const creditProgress = computed(() => {
  const value = data.value
  const earned = value.earnedCredits ?? value.obtainedCredits
  if (value.resolutionStatus !== 'RESOLVED' || value.requiredCredits == null || earned == null || Number(value.requiredCredits) <= 0) return null
  return Math.min(100, Math.max(0, Number(earned) / Number(value.requiredCredits) * 100))
})

function rowsOf(value) {
  if (Array.isArray(value)) return value
  if (!value || typeof value !== 'object') return []
  for (const key of ['items', 'list', 'records', 'events', 'passedCourses', 'details', 'requirements', 'courses', 'warnings']) {
    if (Array.isArray(value[key])) return value[key]
  }
  return []
}
function pick(row, keys, fallback = '') {
  for (const key of keys) {
    const value = row && row[key]
    if (value !== undefined && value !== null && value !== '') return value
  }
  return fallback
}
function attendanceScheduleRoute(row) {
  const lesson = String(row?.scheduleItemId || row?.itemId || '').trim()
  if (!/^\d+$/.test(lesson) || Number(lesson) <= 0) return null
  const week = Number(row?.weekNo)
  return {
    path: '/academic/schedule',
    query: { lesson, from: 'attendance', ...(Number.isSafeInteger(week) && week > 0 ? { week: String(week) } : {}) }
  }
}
function metricRows(type, value, list) {
  const number = (keys) => {
    const raw = pick(value, keys, null)
    return raw == null ? null : Number(raw)
  }
  if (type === 'attendance') {
    return [
      { label: '考勤记录', value: list.length },
      { label: '出勤', value: list.filter((row) => String(pick(row, ['status', 'attendanceStatus'])).toUpperCase() === 'PRESENT').length },
      { label: '异常', value: list.filter((row) => ['LATE', 'ABSENT'].includes(String(pick(row, ['status', 'attendanceStatus'])).toUpperCase())).length }
    ]
  }
  if (type === 'credits') {
    return [
      { label: '已获学分', value: number(['earnedCredits', 'totalEarnedCredits', 'creditsEarned']) ?? '待确认' },
      { label: '要求学分', value: number(['requiredCredits', 'totalRequiredCredits', 'creditsRequired']) ?? '待确认' },
      { label: '平均绩点', value: pick(value, ['gpa', 'averageGpa'], '待确认') }
    ]
  }
  if (type === 'warning') {
    return [
      { label: '预警记录', value: Number.isFinite(Number(value.total)) && Number(value.total) >= list.length ? Number(value.total) : list.length },
      { label: '高风险', value: list.filter((row) => String(pick(row, ['level', 'warningLevel'])).toUpperCase() === 'HIGH').length },
      { label: '待处理', value: list.filter((row) => !['CLOSED', 'RESOLVED', 'COMPLETED'].includes(String(pick(row, ['status'])).toUpperCase())).length }
    ]
  }
  if (type === 'graduation') {
    return [
      { label: '检查项目', value: list.length },
      { label: '已达成', value: list.filter((row) => ['MET', 'PASSED', 'COMPLETED', 'QUALIFIED'].includes(String(pick(row, ['status', 'result'])).toUpperCase())).length },
      { label: '存在缺口', value: list.filter((row) => ['GAP', 'NOT_MET', 'FAILED', 'UNQUALIFIED'].includes(String(pick(row, ['status', 'result'])).toUpperCase())).length }
    ]
  }
  if (type === 'calendar') {
    return [{ label: '教学周数', value: value.weekMeta?.teachingWeeks ?? '待确认' }, { label: '校历事件', value: list.length }, { label: '学期', value: pick(value, ['termLabel', 'termName', 'termCode'], '待确认') }]
  }
  return [{ label: config.value.title, value: list.length }]
}
function rowKey(row, index) { return String(pick(row, ['id', 'warningId', 'eventId', 'recordId', 'courseId', 'requirementId'], `${model.value}:${index}`)) }
function primaryText(row) {
  if (model.value === 'calendar') return row.eventName || row.title || row.remark || calendarType(row.eventType)
  const maps = {
    attendance: ['courseName', 'courseCode'], calendar: ['eventName', 'title', 'name'], clearance: ['courseName', 'courseCode'],
    credits: ['courseName', 'categoryName', 'requirementName'], warning: ['warningName', 'sourceLabel', 'typeLabel', 'title', 'reason'],
    graduation: ['requirementName', 'itemName', 'name', 'title']
  }
  return String(pick(row, maps[model.value] || ['name', 'title'], config.value.title))
}
function statusText(row) {
  if (model.value === 'calendar') return calendarType(row.eventType)
  const value = String(pick(row, ['statusLabel', 'resultLabel', 'status', 'result', 'attendanceStatus', 'passStatus'], '待确认'))
  const map = { PENDING_HANDLE: '待处理', PROCESSING: '跟进中', ESCALATED: '已升级', FINISHED: '已正式发布', SCORED: '成绩待发布', PRESENT: '出勤', LATE: '迟到', ABSENT: '缺勤', LEAVE: '请假', MET: '已达成', NOT_MET: '未达成', GAP: '存在缺口', PASSED: '已通过', FAILED: '未通过', ACTIVE: '待关注', CLOSED: '已关闭' }
  return map[value.toUpperCase()] || value
}
function statusTone(row) {
  const value = String(pick(row, ['status', 'result', 'attendanceStatus', 'passStatus'], '')).toUpperCase()
  if (['PRESENT', 'MET', 'PASSED', 'COMPLETED', 'QUALIFIED', 'CLOSED', 'RESOLVED'].includes(value)) return 'success'
  if (['ABSENT', 'FAILED', 'NOT_MET', 'GAP', 'UNQUALIFIED', 'HIGH', 'ESCALATED'].includes(value)) return 'danger'
  if (['LATE', 'LEAVE', 'ACTIVE', 'PENDING', 'MEDIUM', 'PENDING_HANDLE', 'PROCESSING'].includes(value)) return 'warn'
  return 'default'
}
function clearanceResult(row) {
  // FINISHED is set only when the makeup service publishes the formal grade.
  if (String(row.status || '').toUpperCase() !== 'FINISHED') return '结果尚未正式发布'
  return row.score ?? row.finalScore ?? '正式结果待核对'
}
function calendarType(value) { return ({ TEACHING: '教学周', EXAM: '考试安排', HOLIDAY: '节假日', INTERNSHIP: '实习安排', SWAP: '调课' })[value] || '校历安排' }
async function load() {
  const loader = config.value.loader
  const readModel = model.value
  const requestedPage = warningPage.value
  const title = config.value.title
  const scope = 'academic-readonly'
  data.value = {}
  loading.value = true
  error.value = ''
  const read = await readStudentAcademicSnapshot(guard, async () => {
    if (!loader) throw new Error('当前路由未绑定允许的教务读取接口')
    const result = await loader()
    if (readModel === 'warning') {
      if (!result || !Array.isArray(result.items)) throw new Error('预警记录无法核对')
      const paged = result.page != null || requestedPage > 1
      if (paged && (result.page !== requestedPage || result.pageSize !== 50 || !Number.isInteger(result.total) || result.total < 0 || result.items.length > 50 || (result.items.length > 0 && result.total < (requestedPage - 1) * 50 + result.items.length) || typeof result.hasMore !== 'boolean' || result.hasMore !== (requestedPage * 50 < result.total))) {
        throw new Error('预警分页回执无法核对，请重新加载')
      }
    }
    return result
  }, scope)
  if (read.stale) return
  if (!read.ok) {
    if (academicErrorKind(read.error) === 'forbidden') { guard.invalidate(); data.value = {} }
    error.value = academicErrorMessage(read.error, `${title}数据读取失败，请稍后重试`)
    loading.value = false
    return
  }
  data.value = read.value || {}
  loading.value = false
}

onMounted(load)
watch(() => [model.value, model.value === 'warning' ? warningPage.value : null], load)
onBeforeUnmount(() => guard.dispose())
</script>

<style src="../../components/academic/studentAcademicPrototype.css"></style>
<style scoped>
.definition{margin:14px 0}.is-target{border-color:var(--pri)}
.calendar-grid{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));border-left:1px solid var(--line);border-top:1px solid var(--line)}
.calendar-grid>div{min-height:83px;padding:8px;border-right:1px solid var(--line);border-bottom:1px solid var(--line);font-size:12px;background:var(--surface)}
.calendar-grid .head{min-height:35px;background:var(--soft);text-align:center}.calendar-grid .today{background:var(--priSoft)}.calendar-grid strong{display:block}.calendar-grid small{display:block;margin-top:6px;font-size:11px}
.callout-number{font-size:32px;color:var(--pri);font-weight:750;line-height:1.1;margin-top:6px}
</style>
