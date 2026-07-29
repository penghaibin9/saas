<template>
  <div class="sp-page recheck-page">
    <section class="recheck-hero">
      <div>
        <div class="recheck-hero__eyebrow">教务学业 · 成绩复查</div>
        <h1>对本人已发布成绩发起复查</h1>
        <p>复查用于核对卷面、平时成绩或统计遗漏，不直接在学生端修改成绩。同一成绩存在在途申请时不可重复提交。</p>
      </div>
      <button class="sp-btn sp-btn--ghost" type="button" :disabled="loading || submitting" @click="load">
        {{ loading ? '加载中…' : '刷新记录' }}
      </button>
    </section>

    <StateBlock v-if="loading" type="loading" text="正在读取本人已发布成绩和复查记录…" />
    <section v-else-if="error" class="sp-card recheck-error">
      <StateBlock type="error" :text="error" />
      <button class="sp-btn sp-btn--ghost" type="button" @click="load">重新加载</button>
    </section>
    <template v-else>
      <section class="sp-card apply-card">
        <header class="section-head">
          <div><strong>发起复查</strong><span>仅可选择本人当前有效、已发布且具有稳定 gradeId 的成绩</span></div>
          <StatusTag :text="`${eligibleGrades.length} 门可申请`" :tone="eligibleGrades.length ? 'primary' : 'default'" />
        </header>
        <StateBlock v-if="!eligibleGrades.length" type="empty" text="暂无可发起复查的已发布成绩" />
        <form v-else class="apply-form" @submit.prevent="submit">
          <label>
            <span>选择成绩</span>
            <select v-model="selectedGradeId" class="sp-inp">
              <option value="">请选择已发布成绩</option>
              <option v-for="grade in eligibleGrades" :key="grade.gradeId" :value="String(grade.gradeId)">
                {{ grade.courseName || '课程' }}{{ grade.term ? ` · ${grade.term}` : '' }}（{{ scoreText(grade.score) }}）
              </option>
            </select>
          </label>
          <label>
            <span>复查理由（至少 5 字，最多 200 字）</span>
            <textarea
              v-model.trim="reason"
              class="sp-inp"
              maxlength="200"
              placeholder="例如：请核对卷面分与系统录入分数是否一致"
            />
          </label>
          <footer>
            <span>申请提交后由教务处复审；处理结果以正式成绩记录为准。</span>
            <button class="sp-btn" type="submit" :disabled="!canSubmit || submitting">
              {{ submitting ? '提交中…' : '提交复查申请' }}
            </button>
          </footer>
        </form>
      </section>

      <section class="sp-card records-card">
        <header class="section-head">
          <div><strong>我的复查申请</strong><span>按申请时间倒序展示本人处理结果</span></div>
          <StatusTag :text="`${records.length} 条`" tone="default" />
        </header>
        <StateBlock v-if="!records.length" type="empty" text="暂无复查申请" />
        <div v-else class="record-list">
          <article v-for="record in records" :key="record.recheckId" class="record-item">
            <header>
              <div>
                <strong>{{ record.courseName || '课程名称待补充' }}</strong>
                <span>{{ record.term || '学期待确认' }} · 申请于 {{ dateTime(record.createdAt) }}</span>
              </div>
              <StatusTag :text="statusText(record.status)" :tone="statusTone(record.status)" />
            </header>
            <dl>
              <div><dt>原成绩</dt><dd>{{ scoreText(record.originalScore) }}</dd></div>
              <div v-if="record.newScore != null"><dt>复查后成绩</dt><dd>{{ scoreText(record.newScore) }}</dd></div>
              <div><dt>复查理由</dt><dd>{{ record.reason || '—' }}</dd></div>
              <div v-if="record.reviewNote"><dt>复审意见</dt><dd>{{ record.reviewNote }}</dd></div>
            </dl>
          </article>
        </div>
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import StateBlock from '../../components/StateBlock.vue'
import StatusTag from '../../components/StatusTag.vue'
import { portalApi } from '../../services/portalApi'
import { useUiStore } from '../../stores/ui'

const ui = useUiStore()
const loading = ref(true)
const error = ref('')
const submitting = ref(false)
const records = ref([])
const grades = ref([])
const selectedGradeId = ref('')
const reason = ref('')

const inFlightGradeIds = computed(() => new Set(
  records.value
    .filter((record) => String(record.status || '').toUpperCase() === 'SUBMITTED')
    .map((record) => String(record.acadGradeId || ''))
))
const eligibleGrades = computed(() => grades.value.filter((grade) =>
  grade.gradeId != null && !inFlightGradeIds.value.has(String(grade.gradeId))))
const canSubmit = computed(() =>
  !!selectedGradeId.value && reason.value.trim().length >= 5 && reason.value.trim().length <= 200)

function rowsOf(data) {
  if (Array.isArray(data)) return data
  return (data && (data.items || data.list || data.records)) || []
}
function scoreText(value) { return value == null || value === '' ? '待确认' : `${value} 分` }
function dateTime(value) { return String(value || '').slice(0, 16).replace('T', ' ') || '—' }
function statusText(status) {
  const map = { SUBMITTED: '复查中', UPHELD: '维持原成绩', ADJUSTED: '已调整', REJECTED: '不予受理' }
  return map[String(status || '').toUpperCase()] || status || '待确认'
}
function statusTone(status) {
  const value = String(status || '').toUpperCase()
  if (value === 'ADJUSTED') return 'success'
  if (value === 'SUBMITTED') return 'warn'
  if (value === 'REJECTED') return 'danger'
  return 'default'
}
async function load() {
  loading.value = true
  error.value = ''
  try {
    const [recheckResult, transcriptResult] = await Promise.all([
      portalApi.academicGradeRecheck(),
      portalApi.academicTranscript()
    ])
    records.value = rowsOf(recheckResult)
    grades.value = rowsOf(transcriptResult).filter((grade) => grade.gradeId != null)
    if (selectedGradeId.value && !eligibleGrades.value.some((grade) => String(grade.gradeId) === selectedGradeId.value)) {
      selectedGradeId.value = ''
    }
  } catch (e) {
    error.value = e?.message || '成绩复查数据读取失败，请稍后重试'
  } finally {
    loading.value = false
  }
}
async function submit() {
  if (!canSubmit.value || submitting.value) return
  submitting.value = true
  try {
    await portalApi.academicGradeRecheckSubmit({
      acadGradeId: Number(selectedGradeId.value),
      reason: reason.value.trim()
    })
    selectedGradeId.value = ''
    reason.value = ''
    ui.notify('复查申请已提交')
    await load()
  } catch (e) {
    ui.notify(e?.message || '复查申请提交失败')
  } finally {
    submitting.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.recheck-page { max-width: 1080px; margin: 0 auto; }
.recheck-hero { display: flex; align-items: flex-start; justify-content: space-between; gap: 24px; margin-bottom: 16px; padding: 24px 26px; border: 1px solid var(--line); border-radius: 16px; background: linear-gradient(135deg, #fff, var(--pri-50)); }
.recheck-hero__eyebrow { color: var(--pri); font-size: 12px; font-weight: 700; letter-spacing: .08em; }
.recheck-hero h1 { margin: 8px 0 6px; color: var(--t1); font-size: 24px; }
.recheck-hero p { margin: 0; color: var(--t3); font-size: 13px; line-height: 1.65; }
.recheck-error { display: flex; flex-direction: column; align-items: center; gap: 12px; }
.apply-card, .records-card { padding: 18px 20px; }
.records-card { margin-top: 14px; }
.section-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 14px; }
.section-head strong, .section-head span { display: block; }
.section-head strong { color: var(--t1); font-size: 15px; }
.section-head span { margin-top: 4px; color: var(--t3); font-size: 12px; }
.apply-form { display: grid; gap: 12px; }
.apply-form label > span { display: block; margin-bottom: 6px; color: var(--t2); font-size: 12px; font-weight: 600; }
.apply-form textarea { min-height: 86px; resize: vertical; }
.apply-form footer { display: flex; align-items: center; justify-content: space-between; gap: 18px; }
.apply-form footer span { color: var(--t4); font-size: 12px; }
.record-list { display: grid; gap: 10px; }
.record-item { padding: 14px; border: 1px solid var(--line2); border-radius: 11px; }
.record-item > header { display: flex; align-items: flex-start; justify-content: space-between; gap: 14px; }
.record-item > header strong, .record-item > header span { display: block; }
.record-item > header strong { color: var(--t1); font-size: 14px; }
.record-item > header span { margin-top: 4px; color: var(--t4); font-size: 11.5px; }
.record-item dl { display: grid; gap: 7px; margin: 12px 0 0; padding-top: 11px; border-top: 1px solid var(--line2); }
.record-item dl div { display: grid; grid-template-columns: 90px minmax(0, 1fr); gap: 12px; }
.record-item dt { color: var(--t4); font-size: 12px; }
.record-item dd { margin: 0; color: var(--t2); font-size: 12.5px; overflow-wrap: anywhere; }
@media (max-width: 720px) {
  .recheck-hero, .section-head, .apply-form footer, .record-item > header { align-items: stretch; flex-direction: column; }
  .apply-form footer .sp-btn { width: 100%; }
  .record-item dl div { grid-template-columns: 1fr; gap: 3px; }
}
</style>
