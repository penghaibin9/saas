<template>
  <div class="sp-page exam-page">
    <section class="exam-hero">
      <div>
        <div class="exam-hero__eyebrow">教务学业 · 考试与缓考</div>
        <h1>查看本人考试并办理缓考</h1>
        <p>考试安排只展示本人正式名单内已发布场次；缓考申请、退回补充和处理结果使用独立流程。</p>
      </div>
      <button class="sp-btn sp-btn--ghost" type="button" :disabled="loading || !!actingKey" @click="load">
        {{ loading ? '加载中…' : '刷新安排' }}
      </button>
    </section>

    <StateBlock v-if="loading" type="loading" text="正在读取本人考试与缓考数据…" />
    <section v-else-if="error" class="sp-card exam-error">
      <StateBlock type="error" :text="error" />
      <button class="sp-btn sp-btn--ghost" type="button" @click="load">重新加载</button>
    </section>

    <template v-else>
      <section class="exam-summary">
        <article class="summary-card"><span>已发布考试</span><b>{{ exams.length }}</b></article>
        <article class="summary-card" :class="{ 'is-action': deferOptions.length }"><span>可申请缓考</span><b>{{ deferOptions.length }}</b></article>
        <article class="summary-card" :class="{ 'is-action': returnedDeferrals.length }"><span>退回待补充</span><b>{{ returnedDeferrals.length }}</b></article>
      </section>

      <nav class="exam-tabs" aria-label="考试页面">
        <button type="button" :class="{ 'is-active': tab === 'schedule' }" @click="tab = 'schedule'">考试安排</button>
        <button type="button" :class="{ 'is-active': tab === 'apply' }" @click="tab = 'apply'">申请缓考</button>
        <button type="button" :class="{ 'is-active': tab === 'records' }" @click="tab = 'records'">我的申请</button>
      </nav>

      <section v-if="tab === 'schedule'" class="sp-card work-card">
        <header class="section-head">
          <div><strong>本人考试安排</strong><span>时间按学校时区显示，考场和座位以已发布安排为准</span></div>
          <StatusTag :text="`${upcomingExams.length} 场待考`" :tone="upcomingExams.length ? 'primary' : 'default'" />
        </header>
        <StateBlock v-if="!exams.length" type="empty" text="暂无已发布的本人考试安排" />
        <div v-else class="exam-list">
          <article v-for="exam in exams" :key="examKey(exam)" class="exam-item" :class="{ 'is-past': isPast(exam) }">
            <div class="exam-item__time">
              <strong>{{ dateText(exam.examDate || exam.startAt) }}</strong>
              <span>{{ timeText(exam) }}</span>
            </div>
            <div class="exam-item__main">
              <strong>{{ exam.courseName || '课程名称待补充' }}</strong>
              <span>{{ exam.courseCode || '' }}{{ exam.examTypeLabel ? ` · ${exam.examTypeLabel}` : '' }}</span>
              <small>{{ exam.campusName || exam.campusCode || '校区待定' }} · {{ exam.roomName || exam.classroom || '考场待定' }} · 座位 {{ exam.seatNo || '待定' }}</small>
            </div>
            <StatusTag :text="isPast(exam) ? '已结束' : '待参加'" :tone="isPast(exam) ? 'default' : 'primary'" />
          </article>
        </div>
      </section>

      <section v-else-if="tab === 'apply'" class="sp-card work-card">
        <header class="section-head">
          <div><strong>发起缓考申请</strong><span>只展示后端确认仍在申请窗口且本人有资格的考试课程</span></div>
          <StatusTag :text="`${deferOptions.length} 项可办`" :tone="deferOptions.length ? 'primary' : 'default'" />
        </header>
        <StateBlock v-if="!deferOptions.length" type="empty" text="暂无可申请缓考的考试" />
        <div v-else class="option-list">
          <article v-for="option in deferOptions" :key="deferOptionKey(option)" class="option-item">
            <header>
              <div>
                <strong>{{ option.courseName || '课程名称待补充' }}</strong>
                <span>{{ dateText(option.examDate || option.startAt) }} · {{ timeText(option) }} · {{ option.roomName || option.classroom || '考场待定' }}</span>
              </div>
              <StatusTag text="可申请" tone="primary" />
            </header>
            <div class="option-item__form">
              <label>
                <span>原因类型</span>
                <select v-model="drafts[deferOptionKey(option)].reasonType" class="sp-inp">
                  <option value="ILLNESS">疾病</option>
                  <option value="OFFICIAL">公务或学校安排</option>
                  <option value="FAMILY">家庭重大事项</option>
                  <option value="OTHER">其他</option>
                </select>
              </label>
              <label>
                <span>申请说明（至少 5 字，最多 300 字）</span>
                <textarea
                  v-model.trim="drafts[deferOptionKey(option)].reason"
                  class="sp-inp"
                  maxlength="300"
                  placeholder="请说明无法按时参加考试的原因；证明材料要求以学校制度为准"
                />
              </label>
            </div>
            <footer>
              <span>提交后进入学校审核，未获批准前仍应按原考试安排准备。</span>
              <button
                class="sp-btn"
                type="button"
                :disabled="!!actingKey || !canApply(option)"
                @click="applyDefer(option)"
              >{{ actingKey === `apply:${deferOptionKey(option)}` ? '提交中…' : '提交缓考申请' }}</button>
            </footer>
          </article>
        </div>
      </section>

      <section v-else class="sp-card work-card">
        <header class="section-head">
          <div><strong>我的缓考申请</strong><span>展示本人申请、退回补充和最终处理结果</span></div>
          <StatusTag :text="`${deferrals.length} 条`" tone="default" />
        </header>
        <StateBlock v-if="!deferrals.length" type="empty" text="暂无缓考申请" />
        <div v-else class="record-list">
          <article v-for="record in deferrals" :key="record.deferId || record.id" class="record-item">
            <header>
              <div>
                <strong>{{ record.courseName || '课程名称待补充' }}</strong>
                <span>{{ dateText(record.examDate || record.startAt) }} · 申请于 {{ dateTime(record.applyAt || record.createdAt) }}</span>
              </div>
              <StatusTag :text="deferStatusText(record.status)" :tone="deferStatusTone(record.status)" />
            </header>
            <dl>
              <div><dt>原因类型</dt><dd>{{ reasonTypeText(record.reasonType) }}</dd></div>
              <div><dt>申请说明</dt><dd>{{ record.reason || '—' }}</dd></div>
              <div v-if="record.reviewNote || record.rejectReason || record.returnReason"><dt>处理意见</dt><dd>{{ record.reviewNote || record.rejectReason || record.returnReason }}</dd></div>
            </dl>
            <footer v-if="String(record.status || '').toUpperCase() === 'RETURNED'">
              <span>请按处理意见补充材料后重新提交。</span>
              <button
                class="sp-btn"
                type="button"
                :disabled="!!actingKey"
                @click="resubmit(record)"
              >{{ actingKey === `resubmit:${record.deferId}` ? '重提中…' : '确认补充完成并重提' }}</button>
            </footer>
          </article>
        </div>
      </section>

      <section class="sp-card exam-note">
        <strong>重要提醒</strong>
        <span>考试日期、时间、考场、座位和缓考资格均以服务器已发布数据为准。页面不会根据课程名称或班级自行拼接考试安排。</span>
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import StateBlock from '../../components/StateBlock.vue'
import StatusTag from '../../components/StatusTag.vue'
import { portalApi } from '../../services/portalApi'
import { useUiStore } from '../../stores/ui'

const ui = useUiStore()
const loading = ref(true)
const error = ref('')
const actingKey = ref('')
const tab = ref('schedule')
const exams = ref([])
const deferOptions = ref([])
const deferrals = ref([])
const drafts = reactive({})

const upcomingExams = computed(() => exams.value.filter((exam) => !isPast(exam)))
const returnedDeferrals = computed(() => deferrals.value.filter((record) => String(record.status || '').toUpperCase() === 'RETURNED'))

function rowsOf(data) {
  if (Array.isArray(data)) return data
  return (data && (data.items || data.list || data.records || data.exams || data.options)) || []
}
function examKey(exam) { return String(exam.examRoomStudentId || exam.examCourseId || exam.examId || `${exam.courseCode}:${exam.examDate || exam.startAt}`) }
function deferOptionKey(option) { return String(option.examCourseId || option.id || examKey(option)) }
function dateText(value) { return String(value || '').slice(0, 10) || '日期待定' }
function dateTime(value) { return String(value || '').slice(0, 16).replace('T', ' ') || '—' }
function timeText(exam) {
  const start = String(exam.startTime || '').slice(0, 5)
  const end = String(exam.endTime || '').slice(0, 5)
  if (start && end) return `${start}-${end}`
  if (start) return start
  const startAt = String(exam.startAt || '')
  const endAt = String(exam.endAt || '')
  const startPart = startAt.includes('T') ? startAt.slice(11, 16) : ''
  const endPart = endAt.includes('T') ? endAt.slice(11, 16) : ''
  return startPart && endPart ? `${startPart}-${endPart}` : startPart || '时间待定'
}
function examTimestamp(exam) {
  const raw = exam.endAt || exam.startAt || (exam.examDate && `${exam.examDate}T${exam.endTime || exam.startTime || '23:59'}`)
  const value = raw ? new Date(raw).getTime() : NaN
  return Number.isFinite(value) ? value : null
}
function isPast(exam) {
  const value = examTimestamp(exam)
  return value != null && value < Date.now()
}
function reasonTypeText(value) {
  const map = { ILLNESS: '疾病', OFFICIAL: '公务或学校安排', FAMILY: '家庭重大事项', OTHER: '其他' }
  return map[String(value || '').toUpperCase()] || value || '未分类'
}
function deferStatusText(value) {
  const map = { SUBMITTED: '已提交', COUNSELOR_REVIEW: '辅导员审核中', TEACHER_CONFIRM: '任课教师确认中', ACADEMIC_REVIEW: '教务审核中', APPROVED: '已批准', REJECTED: '未批准', RETURNED: '退回待补充', CANCELLED: '已撤销' }
  return map[String(value || '').toUpperCase()] || value || '待确认'
}
function deferStatusTone(value) {
  const status = String(value || '').toUpperCase()
  if (status === 'APPROVED') return 'success'
  if (['REJECTED', 'CANCELLED'].includes(status)) return 'danger'
  if (status === 'RETURNED') return 'warn'
  return 'primary'
}
function ensureDraft(option) {
  const key = deferOptionKey(option)
  if (!drafts[key]) drafts[key] = { reasonType: 'ILLNESS', reason: '' }
}
function canApply(option) {
  const draft = drafts[deferOptionKey(option)]
  return !!option?.examCourseId && !!draft?.reasonType && String(draft.reason || '').trim().length >= 5
}
async function load() {
  loading.value = true
  error.value = ''
  try {
    const [examResult, optionResult, recordResult] = await Promise.all([
      portalApi.academicExam(),
      portalApi.academicExamDeferOptions(),
      portalApi.academicExamDefer()
    ])
    exams.value = rowsOf(examResult)
    deferOptions.value = rowsOf(optionResult)
    deferrals.value = rowsOf(recordResult)
    for (const option of deferOptions.value) ensureDraft(option)
    if (returnedDeferrals.value.length && tab.value === 'schedule') tab.value = 'records'
  } catch (e) {
    error.value = e?.message || '考试与缓考数据读取失败，请稍后重试'
  } finally {
    loading.value = false
  }
}
async function applyDefer(option) {
  const key = deferOptionKey(option)
  if (actingKey.value || !canApply(option)) return
  const draft = drafts[key]
  actingKey.value = `apply:${key}`
  try {
    await portalApi.academicExamDeferApply({
      examCourseId: option.examCourseId,
      reasonType: draft.reasonType,
      reason: String(draft.reason || '').trim()
    })
    drafts[key] = { reasonType: 'ILLNESS', reason: '' }
    ui.notify('缓考申请已提交')
    tab.value = 'records'
    await load()
  } catch (e) {
    ui.notify(e?.message || '缓考申请提交失败')
  } finally {
    actingKey.value = ''
  }
}
async function resubmit(record) {
  const id = record?.deferId || record?.id
  if (!id || actingKey.value) return
  const confirmed = window.confirm('确认已按处理意见补充材料并重新提交？')
  if (!confirmed) return
  actingKey.value = `resubmit:${id}`
  try {
    await portalApi.academicExamDeferResubmit(id)
    ui.notify('缓考申请已重新提交')
    await load()
  } catch (e) {
    ui.notify(e?.message || '重新提交失败')
  } finally {
    actingKey.value = ''
  }
}

onMounted(load)
</script>

<style scoped>
.exam-page { max-width: 1120px; margin: 0 auto; }
.exam-hero { display: flex; align-items: flex-start; justify-content: space-between; gap: 24px; margin-bottom: 16px; padding: 24px 26px; border: 1px solid var(--line); border-radius: 16px; background: linear-gradient(135deg, #fff, var(--pri-50)); }
.exam-hero__eyebrow { color: var(--pri); font-size: 12px; font-weight: 700; letter-spacing: .08em; }
.exam-hero h1 { margin: 8px 0 6px; color: var(--t1); font-size: 24px; }
.exam-hero p { margin: 0; color: var(--t3); font-size: 13px; line-height: 1.65; }
.exam-error { display: flex; flex-direction: column; align-items: center; gap: 12px; }
.exam-summary { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin-bottom: 14px; }
.summary-card { padding: 16px 18px; border: 1px solid var(--line); border-radius: 13px; background: #fff; }
.summary-card span { display: block; color: var(--t3); font-size: 12px; }
.summary-card b { display: block; margin-top: 7px; color: var(--t1); font-size: 22px; }
.summary-card.is-action b { color: var(--pri); }
.exam-tabs { display: flex; gap: 6px; margin-bottom: 14px; padding: 5px; border: 1px solid var(--line); border-radius: 11px; background: #fff; }
.exam-tabs button { flex: 1; min-height: 36px; border: 0; border-radius: 8px; background: transparent; color: var(--t3); cursor: pointer; }
.exam-tabs button.is-active { background: var(--pri-50); color: var(--pri); font-weight: 600; }
.work-card { padding: 18px 20px; }
.section-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 14px; }
.section-head strong, .section-head span { display: block; }
.section-head strong { color: var(--t1); font-size: 15px; }
.section-head span { margin-top: 4px; color: var(--t3); font-size: 12px; }
.exam-list, .option-list, .record-list { display: grid; gap: 10px; }
.exam-item { display: grid; grid-template-columns: 120px minmax(0, 1fr) auto; align-items: center; gap: 14px; padding: 14px; border: 1px solid var(--line2); border-radius: 11px; }
.exam-item.is-past { opacity: .72; }
.exam-item__time strong, .exam-item__time span, .exam-item__main strong, .exam-item__main span, .exam-item__main small { display: block; }
.exam-item__time strong { color: var(--t1); font-size: 13px; }
.exam-item__time span { margin-top: 4px; color: var(--pri); font-size: 12px; }
.exam-item__main strong { color: var(--t1); font-size: 14px; }
.exam-item__main span { margin-top: 3px; color: var(--t3); font-size: 11.5px; }
.exam-item__main small { margin-top: 5px; color: var(--t4); font-size: 11.5px; }
.option-item, .record-item { padding: 14px; border: 1px solid var(--line2); border-radius: 11px; }
.option-item > header, .record-item > header { display: flex; align-items: flex-start; justify-content: space-between; gap: 14px; }
.option-item > header strong, .option-item > header span, .record-item > header strong, .record-item > header span { display: block; }
.option-item > header strong, .record-item > header strong { color: var(--t1); font-size: 14px; }
.option-item > header span, .record-item > header span { margin-top: 4px; color: var(--t4); font-size: 11.5px; }
.option-item__form { display: grid; grid-template-columns: 220px minmax(0, 1fr); gap: 12px; margin-top: 12px; }
.option-item label { display: grid; gap: 6px; }
.option-item label span { color: var(--t2); font-size: 12px; font-weight: 600; }
.option-item textarea { min-height: 76px; resize: vertical; }
.option-item footer, .record-item footer { display: flex; align-items: center; justify-content: space-between; gap: 18px; margin-top: 12px; }
.option-item footer span, .record-item footer span { color: var(--t4); font-size: 12px; }
.record-item dl { display: grid; gap: 7px; margin: 12px 0 0; padding-top: 11px; border-top: 1px solid var(--line2); }
.record-item dl div { display: grid; grid-template-columns: 90px minmax(0, 1fr); gap: 12px; }
.record-item dt { color: var(--t4); font-size: 12px; }
.record-item dd { margin: 0; color: var(--t2); font-size: 12.5px; overflow-wrap: anywhere; }
.exam-note { display: flex; gap: 12px; margin-top: 14px; color: var(--t3); font-size: 12.5px; }
.exam-note strong { color: var(--t1); white-space: nowrap; }
@media (max-width: 760px) {
  .exam-hero, .section-head, .option-item > header, .record-item > header, .option-item footer, .record-item footer { align-items: stretch; flex-direction: column; }
  .exam-summary { grid-template-columns: 1fr; }
  .exam-item { grid-template-columns: 1fr; }
  .option-item__form { grid-template-columns: 1fr; }
  .record-item dl div { grid-template-columns: 1fr; gap: 3px; }
  .option-item footer .sp-btn, .record-item footer .sp-btn { width: 100%; }
}
</style>
