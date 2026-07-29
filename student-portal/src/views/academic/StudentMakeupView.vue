<template>
  <div class="sp-page makeup-page">
    <section class="makeup-hero">
      <div>
        <div class="makeup-hero__eyebrow">教务学业 · 补考重修与免修</div>
        <h1>查看结果并办理本人申请</h1>
        <p>补考结果、重修报名和免修申请分别展示。可申请范围由当前有效未通过课程和学校规则实时计算。</p>
      </div>
      <button class="sp-btn sp-btn--ghost" type="button" :disabled="loading || !!actingKey" @click="load">
        {{ loading ? '加载中…' : '刷新状态' }}
      </button>
    </section>

    <StateBlock v-if="loading" type="loading" text="正在读取本人补考重修与免修数据…" />
    <section v-else-if="error" class="sp-card makeup-error">
      <StateBlock type="error" :text="error" />
      <button class="sp-btn sp-btn--ghost" type="button" @click="load">重新加载</button>
    </section>

    <template v-else>
      <section class="makeup-summary">
        <article class="summary-card"><span>补考重修记录</span><b>{{ overviewRows.length }}</b></article>
        <article class="summary-card" :class="{ 'is-action': retakeOptions.length }"><span>可报名重修</span><b>{{ retakeOptions.length }}</b></article>
        <article class="summary-card" :class="{ 'is-action': exemptionOptions.length }"><span>可申请免修</span><b>{{ exemptionOptions.length }}</b></article>
      </section>

      <nav class="makeup-tabs" aria-label="补考重修页面">
        <button type="button" :class="{ 'is-active': tab === 'overview' }" @click="tab = 'overview'">结果与记录</button>
        <button type="button" :class="{ 'is-active': tab === 'retake' }" @click="tab = 'retake'">重修报名</button>
        <button type="button" :class="{ 'is-active': tab === 'exemption' }" @click="tab = 'exemption'">免修申请</button>
      </nav>

      <section v-if="tab === 'overview'" class="sp-card work-card">
        <header class="section-head">
          <div><strong>补考重修记录</strong><span>展示本人课程状态、申请状态和已发布结果</span></div>
          <StatusTag :text="`${overviewRows.length} 条`" tone="default" />
        </header>
        <StateBlock v-if="!overviewRows.length" type="empty" text="暂无补考、重修或免修记录" />
        <div v-else class="record-list">
          <article v-for="row in overviewRows" :key="recordKey(row)" class="record-item">
            <header>
              <div>
                <strong>{{ row.courseName || '课程名称待补充' }}</strong>
                <span>{{ row.termCode || row.termName || '学期待确认' }}</span>
              </div>
              <StatusTag :text="recordStatusText(row)" :tone="recordStatusTone(row)" />
            </header>
            <dl>
              <div><dt>课程状态</dt><dd>{{ courseStatusText(row.status) }}</dd></div>
              <div><dt>申请状态</dt><dd>{{ applicationStatusText(row.applyStatus) }}</dd></div>
              <div v-if="row.makeupScore != null"><dt>补考成绩</dt><dd>{{ row.makeupScore }} 分</dd></div>
              <div v-if="row.finalScore != null"><dt>最终成绩</dt><dd>{{ row.finalScore }} 分</dd></div>
              <div v-if="row.note || row.reviewNote"><dt>处理说明</dt><dd>{{ row.note || row.reviewNote }}</dd></div>
            </dl>
          </article>
        </div>
      </section>

      <section v-else-if="tab === 'retake'" class="sp-card work-card">
        <header class="section-head">
          <div><strong>重修报名</strong><span>只展示后端确认可报名的当前有效未通过课程</span></div>
          <StatusTag :text="`${retakeOptions.length} 门可办`" :tone="retakeOptions.length ? 'primary' : 'default'" />
        </header>
        <StateBlock v-if="!retakeOptions.length" type="empty" text="暂无可报名重修课程" />
        <div v-else class="option-list">
          <article v-for="option in retakeOptions" :key="retakeKey(option)" class="option-item">
            <header>
              <div>
                <strong>{{ option.courseName || '课程名称待补充' }}</strong>
                <span>{{ option.termCode || option.termName || '原修读学期待确认' }} · {{ sourceTypeText(option.sourceType) }}</span>
              </div>
              <StatusTag :text="scoreLabel(option)" tone="warn" />
            </header>
            <label>
              <span>报名说明（至少 2 字，最多 200 字）</span>
              <textarea
                v-model.trim="retakeReasons[retakeKey(option)]"
                class="sp-inp"
                maxlength="200"
                placeholder="说明报名原因或需学校核实的情况"
              />
            </label>
            <footer>
              <span>报名资格、时间冲突和收费规则以服务器最终校验为准。</span>
              <button
                class="sp-btn"
                type="button"
                :disabled="!!actingKey || !canApplyRetake(option)"
                @click="applyRetake(option)"
              >{{ actingKey === `retake:${retakeKey(option)}` ? '提交中…' : '提交重修报名' }}</button>
            </footer>
          </article>
        </div>
      </section>

      <section v-else class="sp-card work-card">
        <header class="section-head">
          <div><strong>免修申请</strong><span>只展示后端确认允许发起免修的课程</span></div>
          <StatusTag :text="`${exemptionOptions.length} 门可办`" :tone="exemptionOptions.length ? 'primary' : 'default'" />
        </header>
        <StateBlock v-if="!exemptionOptions.length" type="empty" text="暂无可申请免修课程" />
        <div v-else class="option-list">
          <article v-for="option in exemptionOptions" :key="exemptionKey(option)" class="option-item">
            <header>
              <div>
                <strong>{{ option.courseName || '课程名称待补充' }}</strong>
                <span>{{ option.courseCode || '课程代码待确认' }} · {{ option.termCode || option.termName || '学期待确认' }}</span>
              </div>
              <StatusTag :text="scoreLabel(option)" tone="warn" />
            </header>
            <label>
              <span>免修理由（至少 2 字，最多 300 字）</span>
              <textarea
                v-model.trim="exemptionReasons[exemptionKey(option)]"
                class="sp-inp"
                maxlength="300"
                placeholder="说明免修依据，证明材料要求以学校制度为准"
              />
            </label>
            <footer>
              <span>提交申请不等于免修生效，须经学校审核通过。</span>
              <button
                class="sp-btn"
                type="button"
                :disabled="!!actingKey || !canApplyExemption(option)"
                @click="applyExemption(option)"
              >{{ actingKey === `exemption:${exemptionKey(option)}` ? '提交中…' : '提交免修申请' }}</button>
            </footer>
          </article>
        </div>
      </section>

      <section class="sp-card makeup-note">
        <strong>数据口径</strong>
        <span>可申请课程来自有效成绩和补重修政策。页面不会自行根据分数猜测资格，也不会在接口失败时显示假成功。</span>
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
const tab = ref('overview')
const overview = ref({})
const options = ref({ retakeOptions: [], exemptionOptions: [] })
const retakeReasons = reactive({})
const exemptionReasons = reactive({})

const overviewRows = computed(() => rowsOf(overview.value))
const retakeOptions = computed(() => Array.isArray(options.value.retakeOptions) ? options.value.retakeOptions : [])
const exemptionOptions = computed(() => Array.isArray(options.value.exemptionOptions) ? options.value.exemptionOptions : [])

function rowsOf(data) {
  if (Array.isArray(data)) return data
  return (data && (data.items || data.list || data.records)) || []
}
function recordKey(row) {
  return String(row.id || row.makeupId || row.retakeId || row.exemptionId || `${row.courseCode || row.courseName}:${row.termCode || ''}`)
}
function retakeKey(option) {
  return String(option.sourceId || option.acadGradeId || option.id || `${option.sourceType || 'GRADE'}:${option.courseCode || option.courseName}`)
}
function exemptionKey(option) {
  return String(option.acadGradeId || option.sourceId || option.id || option.courseCode || option.courseName)
}
function scoreLabel(option) {
  const value = option.score ?? option.originalScore ?? option.totalScore
  return value == null ? '未通过课程' : `原成绩 ${value}`
}
function sourceTypeText(value) {
  const map = { GRADE: '成绩来源', MAKEUP: '补考来源', CLEARANCE: '清考来源' }
  return map[String(value || '').toUpperCase()] || value || '成绩来源'
}
function courseStatusText(value) {
  const map = { PENDING: '待处理', ELIGIBLE: '符合条件', SCHEDULED: '已安排', COMPLETED: '已完成', PASSED: '已通过', FAILED: '未通过' }
  return map[String(value || '').toUpperCase()] || value || '待确认'
}
function applicationStatusText(value) {
  const map = { PENDING: '审核中', SUBMITTED: '已提交', APPROVED: '已通过', REJECTED: '未通过', RETURNED: '已退回', CANCELLED: '已取消' }
  return map[String(value || '').toUpperCase()] || value || '暂无申请'
}
function recordStatusText(row) {
  return applicationStatusText(row.applyStatus) !== '暂无申请'
    ? applicationStatusText(row.applyStatus)
    : courseStatusText(row.status)
}
function recordStatusTone(row) {
  const value = String(row.applyStatus || row.status || '').toUpperCase()
  if (['APPROVED', 'COMPLETED', 'PASSED'].includes(value)) return 'success'
  if (['REJECTED', 'FAILED', 'CANCELLED'].includes(value)) return 'danger'
  return 'warn'
}
function canApplyRetake(option) {
  return !!retakeKey(option) && String(retakeReasons[retakeKey(option)] || '').trim().length >= 2
}
function canApplyExemption(option) {
  return !!exemptionKey(option) && String(exemptionReasons[exemptionKey(option)] || '').trim().length >= 2
}
async function load() {
  loading.value = true
  error.value = ''
  try {
    const [overviewResult, optionsResult] = await Promise.all([
      portalApi.academicMakeup(),
      portalApi.academicMakeupOptions()
    ])
    overview.value = overviewResult || {}
    options.value = optionsResult || { retakeOptions: [], exemptionOptions: [] }
    for (const option of retakeOptions.value) {
      const key = retakeKey(option)
      if (retakeReasons[key] == null) retakeReasons[key] = ''
    }
    for (const option of exemptionOptions.value) {
      const key = exemptionKey(option)
      if (exemptionReasons[key] == null) exemptionReasons[key] = ''
    }
  } catch (e) {
    error.value = e?.message || '补考重修数据读取失败，请稍后重试'
  } finally {
    loading.value = false
  }
}
async function applyRetake(option) {
  const key = retakeKey(option)
  if (actingKey.value || !canApplyRetake(option)) return
  actingKey.value = `retake:${key}`
  try {
    await portalApi.academicRetakeApply({
      sourceType: option.sourceType || 'GRADE',
      sourceId: option.sourceId || option.acadGradeId || option.id,
      reason: String(retakeReasons[key] || '').trim()
    })
    retakeReasons[key] = ''
    ui.notify('重修报名已提交')
    await load()
  } catch (e) {
    ui.notify(e?.message || '重修报名提交失败')
  } finally {
    actingKey.value = ''
  }
}
async function applyExemption(option) {
  const key = exemptionKey(option)
  if (actingKey.value || !canApplyExemption(option)) return
  actingKey.value = `exemption:${key}`
  try {
    await portalApi.academicExemptionApply({
      acadGradeId: option.acadGradeId || option.sourceId || option.id,
      courseCode: option.courseCode,
      reason: String(exemptionReasons[key] || '').trim()
    })
    exemptionReasons[key] = ''
    ui.notify('免修申请已提交')
    await load()
  } catch (e) {
    ui.notify(e?.message || '免修申请提交失败')
  } finally {
    actingKey.value = ''
  }
}

onMounted(load)
</script>

<style scoped>
.makeup-page { max-width: 1120px; margin: 0 auto; }
.makeup-hero { display: flex; align-items: flex-start; justify-content: space-between; gap: 24px; margin-bottom: 16px; padding: 24px 26px; border: 1px solid var(--line); border-radius: 16px; background: linear-gradient(135deg, #fff, var(--pri-50)); }
.makeup-hero__eyebrow { color: var(--pri); font-size: 12px; font-weight: 700; letter-spacing: .08em; }
.makeup-hero h1 { margin: 8px 0 6px; color: var(--t1); font-size: 24px; }
.makeup-hero p { margin: 0; color: var(--t3); font-size: 13px; line-height: 1.65; }
.makeup-error { display: flex; flex-direction: column; align-items: center; gap: 12px; }
.makeup-summary { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin-bottom: 14px; }
.summary-card { padding: 16px 18px; border: 1px solid var(--line); border-radius: 13px; background: #fff; }
.summary-card span { display: block; color: var(--t3); font-size: 12px; }
.summary-card b { display: block; margin-top: 7px; color: var(--t1); font-size: 22px; }
.summary-card.is-action b { color: var(--pri); }
.makeup-tabs { display: flex; gap: 6px; margin-bottom: 14px; padding: 5px; border: 1px solid var(--line); border-radius: 11px; background: #fff; }
.makeup-tabs button { flex: 1; min-height: 36px; border: 0; border-radius: 8px; background: transparent; color: var(--t3); cursor: pointer; }
.makeup-tabs button.is-active { background: var(--pri-50); color: var(--pri); font-weight: 600; }
.work-card { padding: 18px 20px; }
.section-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 14px; }
.section-head strong, .section-head span { display: block; }
.section-head strong { color: var(--t1); font-size: 15px; }
.section-head span { margin-top: 4px; color: var(--t3); font-size: 12px; }
.record-list, .option-list { display: grid; gap: 10px; }
.record-item, .option-item { padding: 14px; border: 1px solid var(--line2); border-radius: 11px; }
.record-item > header, .option-item > header { display: flex; align-items: flex-start; justify-content: space-between; gap: 14px; }
.record-item > header strong, .record-item > header span, .option-item > header strong, .option-item > header span { display: block; }
.record-item > header strong, .option-item > header strong { color: var(--t1); font-size: 14px; }
.record-item > header span, .option-item > header span { margin-top: 4px; color: var(--t4); font-size: 11.5px; }
.record-item dl { display: grid; gap: 7px; margin: 12px 0 0; padding-top: 11px; border-top: 1px solid var(--line2); }
.record-item dl div { display: grid; grid-template-columns: 90px minmax(0, 1fr); gap: 12px; }
.record-item dt { color: var(--t4); font-size: 12px; }
.record-item dd { margin: 0; color: var(--t2); font-size: 12.5px; overflow-wrap: anywhere; }
.option-item label { display: grid; gap: 6px; margin-top: 12px; }
.option-item label span { color: var(--t2); font-size: 12px; font-weight: 600; }
.option-item textarea { min-height: 76px; resize: vertical; }
.option-item footer { display: flex; align-items: center; justify-content: space-between; gap: 18px; margin-top: 12px; }
.option-item footer span { color: var(--t4); font-size: 12px; }
.makeup-note { display: flex; gap: 12px; margin-top: 14px; color: var(--t3); font-size: 12.5px; }
.makeup-note strong { color: var(--t1); white-space: nowrap; }
@media (max-width: 720px) {
  .makeup-hero, .section-head, .record-item > header, .option-item > header, .option-item footer { align-items: stretch; flex-direction: column; }
  .makeup-summary { grid-template-columns: 1fr; }
  .record-item dl div { grid-template-columns: 1fr; gap: 3px; }
  .option-item footer .sp-btn { width: 100%; }
}
</style>
