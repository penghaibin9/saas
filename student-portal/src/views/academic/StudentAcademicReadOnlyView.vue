<template>
  <div class="sp-page read-page">
    <section class="read-hero">
      <div>
        <div class="read-hero__eyebrow">教务学业 · {{ config.title }}</div>
        <h1>{{ config.heading }}</h1>
        <p>{{ config.description }}</p>
      </div>
      <button class="sp-btn sp-btn--ghost" type="button" :disabled="loading" @click="load">
        {{ loading ? '加载中…' : '刷新数据' }}
      </button>
    </section>

    <StateBlock v-if="loading" type="loading" :text="`正在读取本人${config.title}数据…`" />
    <section v-else-if="error" class="sp-card read-error">
      <StateBlock type="error" :text="error" />
      <button class="sp-btn sp-btn--ghost" type="button" @click="load">重新加载</button>
    </section>

    <template v-else>
      <section v-if="metrics.length" class="metric-grid">
        <article v-for="metric in metrics" :key="metric.label" class="metric-card">
          <span>{{ metric.label }}</span><b>{{ metric.value }}</b><small v-if="metric.note">{{ metric.note }}</small>
        </article>
      </section>

      <section class="sp-card content-card">
        <header class="section-head">
          <div><strong>{{ config.sectionTitle }}</strong><span>{{ config.sectionDescription }}</span></div>
          <StatusTag :text="summaryTag" :tone="summaryTone" />
        </header>
        <StateBlock v-if="!rows.length" type="empty" :text="data.note || config.emptyText" />
        <div v-else class="record-list">
          <article v-for="(row, index) in rows" :key="rowKey(row, index)" class="record-item">
            <header>
              <div>
                <strong>{{ primaryText(row) }}</strong>
                <span>{{ secondaryText(row) }}</span>
              </div>
              <StatusTag :text="statusText(row)" :tone="statusTone(row)" />
            </header>
            <dl>
              <div v-for="field in detailFields(row)" :key="field.label">
                <dt>{{ field.label }}</dt><dd>{{ field.value }}</dd>
              </div>
            </dl>
          </article>
        </div>
      </section>

      <section class="sp-card read-note">
        <strong>数据口径</strong>
        <span>{{ config.note }}</span>
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import StateBlock from '../../components/StateBlock.vue'
import StatusTag from '../../components/StatusTag.vue'
import { portalApi } from '../../services/portalApi'

const route = useRoute()
const loading = ref(true)
const error = ref('')
const data = ref({})

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
    loader: () => portalApi.academicWarning(),
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
const metrics = computed(() => metricRows(model.value, data.value, rows.value))
const summaryTag = computed(() => {
  if (model.value === 'warning') return rows.value.length ? `${rows.value.length} 条待关注` : '暂无预警'
  if (model.value === 'graduation') return graduationSummary(data.value)
  return `${rows.value.length} 条`
})
const summaryTone = computed(() => {
  if (model.value === 'warning' && rows.value.length) return 'warn'
  if (model.value === 'graduation') return graduationTone(data.value)
  return 'default'
})

function rowsOf(value) {
  if (Array.isArray(value)) return value
  if (!value || typeof value !== 'object') return []
  for (const key of ['items', 'list', 'records', 'events', 'details', 'requirements', 'courses', 'warnings']) {
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
      { label: '预警记录', value: list.length },
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
    return [{ label: '当前教学周', value: pick(value, ['currentWeek', 'weekNo'], '待确认') }, { label: '校历事件', value: list.length }, { label: '学期', value: pick(value, ['termName', 'termCode'], '当前学期') }]
  }
  return [{ label: config.value.title, value: list.length }]
}
function rowKey(row, index) { return String(pick(row, ['id', 'warningId', 'eventId', 'recordId', 'courseId', 'requirementId'], `${model.value}:${index}`)) }
function primaryText(row) {
  const maps = {
    attendance: ['courseName', 'courseCode'], calendar: ['eventName', 'title', 'name'], clearance: ['courseName', 'courseCode'],
    credits: ['courseName', 'categoryName', 'requirementName'], warning: ['warningName', 'typeLabel', 'title', 'reason'],
    graduation: ['requirementName', 'itemName', 'name', 'title']
  }
  return String(pick(row, maps[model.value] || ['name', 'title'], config.value.title))
}
function secondaryText(row) {
  const maps = {
    attendance: ['sessionDate', 'attendanceDate', 'termCode'], calendar: ['eventDate', 'startDate', 'date'], clearance: ['termCode', 'examDate'],
    credits: ['termCode', 'courseCode', 'categoryCode'], warning: ['triggerTime', 'createdAt', 'levelLabel'],
    graduation: ['categoryName', 'evidenceSource', 'source']
  }
  return String(pick(row, maps[model.value] || ['createdAt'], ''))
}
function statusText(row) {
  const value = String(pick(row, ['statusLabel', 'resultLabel', 'status', 'result', 'attendanceStatus'], '待确认'))
  const map = { PRESENT: '出勤', LATE: '迟到', ABSENT: '缺勤', LEAVE: '请假', MET: '已达成', NOT_MET: '未达成', GAP: '存在缺口', PASSED: '已通过', FAILED: '未通过', ACTIVE: '待关注', CLOSED: '已关闭' }
  return map[value.toUpperCase()] || value
}
function statusTone(row) {
  const value = String(pick(row, ['status', 'result', 'attendanceStatus'], '')).toUpperCase()
  if (['PRESENT', 'MET', 'PASSED', 'COMPLETED', 'QUALIFIED', 'CLOSED', 'RESOLVED'].includes(value)) return 'success'
  if (['ABSENT', 'FAILED', 'NOT_MET', 'GAP', 'UNQUALIFIED', 'HIGH'].includes(value)) return 'danger'
  if (['LATE', 'LEAVE', 'ACTIVE', 'PENDING', 'MEDIUM'].includes(value)) return 'warn'
  return 'default'
}
function detailFields(row) {
  const definitions = {
    attendance: [['日期', ['sessionDate', 'attendanceDate']], ['节次', ['slotLabel', 'slotNo']], ['教师', ['teacherName']], ['说明', ['note', 'remark']]],
    calendar: [['开始', ['startDate', 'eventDate', 'startAt']], ['结束', ['endDate', 'endAt']], ['类型', ['eventTypeLabel', 'eventType']], ['说明', ['description', 'note']]],
    clearance: [['课程代码', ['courseCode']], ['考试时间', ['examDate', 'startAt']], ['成绩', ['score', 'finalScore']], ['说明', ['note', 'reviewNote']]],
    credits: [['课程代码', ['courseCode']], ['课程类别', ['categoryName', 'courseType']], ['学分', ['credit', 'earnedCredit']], ['绩点', ['gpa', 'gradePoint']]],
    warning: [['预警等级', ['levelLabel', 'level']], ['触发原因', ['reason', 'triggerReason']], ['责任老师', ['responsibleTeacherName', 'teacherName']], ['处理要求', ['requirement', 'handleRequirement', 'note']]],
    graduation: [['要求值', ['requiredValue', 'requiredCredits']], ['当前值', ['currentValue', 'earnedCredits']], ['证据来源', ['evidenceSource', 'source']], ['缺口说明', ['gapReason', 'note']]]
  }
  return (definitions[model.value] || []).map(([label, keys]) => ({ label, value: String(pick(row, keys, '—')) }))
}
function graduationSummary(value) {
  const result = String(pick(value, ['result', 'status', 'qualificationStatus'], '')).toUpperCase()
  if (['QUALIFIED', 'PASSED', 'MET'].includes(result)) return '系统自查已达成'
  if (['UNQUALIFIED', 'FAILED', 'GAP', 'NOT_MET'].includes(result)) return '系统自查存在缺口'
  return `${rows.value.length} 项`
}
function graduationTone(value) {
  const result = String(pick(value, ['result', 'status', 'qualificationStatus'], '')).toUpperCase()
  if (['QUALIFIED', 'PASSED', 'MET'].includes(result)) return 'success'
  if (['UNQUALIFIED', 'FAILED', 'GAP', 'NOT_MET'].includes(result)) return 'danger'
  return 'default'
}
async function load() {
  loading.value = true
  error.value = ''
  try {
    if (!config.value.loader) throw new Error('当前路由未绑定允许的教务读取接口')
    data.value = await config.value.loader() || {}
  } catch (e) {
    error.value = e?.message || `${config.value.title}数据读取失败，请稍后重试`
  } finally {
    loading.value = false
  }
}

onMounted(load)
watch(model, load)
</script>

<style scoped>
.read-page { max-width: 1080px; margin: 0 auto; }
.read-hero { display: flex; align-items: flex-start; justify-content: space-between; gap: 24px; margin-bottom: 16px; padding: 24px 26px; border: 1px solid var(--line); border-radius: 16px; background: linear-gradient(135deg, #fff, var(--pri-50)); }
.read-hero__eyebrow { color: var(--pri); font-size: 12px; font-weight: 700; letter-spacing: .08em; }
.read-hero h1 { margin: 8px 0 6px; color: var(--t1); font-size: 24px; }
.read-hero p { margin: 0; color: var(--t3); font-size: 13px; line-height: 1.65; }
.read-error { display: flex; flex-direction: column; align-items: center; gap: 12px; }
.metric-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin-bottom: 14px; }
.metric-card { padding: 16px 18px; border: 1px solid var(--line); border-radius: 13px; background: #fff; }
.metric-card span, .metric-card b, .metric-card small { display: block; }
.metric-card span { color: var(--t3); font-size: 12px; }
.metric-card b { margin-top: 7px; color: var(--t1); font-size: 22px; }
.metric-card small { margin-top: 4px; color: var(--t4); font-size: 11px; }
.content-card { padding: 18px 20px; }
.section-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 14px; }
.section-head strong, .section-head span { display: block; }
.section-head strong { color: var(--t1); font-size: 15px; }
.section-head span { margin-top: 4px; color: var(--t3); font-size: 12px; }
.record-list { display: grid; gap: 10px; }
.record-item { padding: 14px; border: 1px solid var(--line2); border-radius: 11px; }
.record-item > header { display: flex; align-items: flex-start; justify-content: space-between; gap: 14px; }
.record-item > header strong, .record-item > header span { display: block; }
.record-item > header strong { color: var(--t1); font-size: 14px; }
.record-item > header span { margin-top: 4px; color: var(--t4); font-size: 11.5px; }
.record-item dl { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px 16px; margin: 12px 0 0; padding-top: 11px; border-top: 1px solid var(--line2); }
.record-item dl div { display: grid; grid-template-columns: 78px minmax(0, 1fr); gap: 8px; }
.record-item dt { color: var(--t4); font-size: 12px; }
.record-item dd { margin: 0; color: var(--t2); font-size: 12.5px; overflow-wrap: anywhere; }
.read-note { display: flex; gap: 12px; margin-top: 14px; color: var(--t3); font-size: 12.5px; }
.read-note strong { color: var(--t1); white-space: nowrap; }
@media (max-width: 720px) {
  .read-hero, .section-head, .record-item > header { align-items: stretch; flex-direction: column; }
  .metric-grid { grid-template-columns: 1fr; }
  .record-item dl { grid-template-columns: 1fr; }
  .record-item dl div { grid-template-columns: 1fr; gap: 3px; }
}
</style>
