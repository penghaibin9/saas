<template>
  <div class="sp-page graduation-page">
    <section class="graduation-hero" :class="{ 'is-passed': overallPassed }">
      <div class="graduation-hero__copy">
        <div class="graduation-hero__eyebrow"><span></span>教务学业 · 毕业资格自查</div>
        <h1>{{ overallPassed ? '当前毕业条件已通过实时核验' : '毕业条件还有待处理事项' }}</h1>
        <p>{{ heroDescription }}</p>
        <div class="graduation-hero__chips">
          <span>{{ formalStatusText }}</span>
          <span>{{ passedCount }} 项已通过</span>
          <span v-if="blockingPendingCount">{{ blockingPendingCount }} 项待处理</span>
          <span v-if="advisoryPendingCount">{{ advisoryPendingCount }} 项提示</span>
        </div>
      </div>
      <aside class="graduation-hero__score">
        <span>学分达成</span>
        <strong>{{ creditPct }}<small>%</small></strong>
        <div class="graduation-hero__bar" aria-hidden="true"><i :style="{ width: `${creditPct}%` }"></i></div>
        <button class="sp-btn sp-btn--ghost sp-btn--sm" type="button" :disabled="loading" @click="refreshAudit">
          {{ loading ? '刷新中…' : '重新核验' }}
        </button>
      </aside>
    </section>

    <StateBlock v-if="loading" type="loading" text="正在读取毕业资格、学分和预警事实…" />
    <section v-else-if="error" class="sp-card graduation-error">
      <div class="graduation-error__icon" aria-hidden="true">!</div>
      <strong>毕业自查暂时无法加载</strong>
      <span>{{ error }}</span>
      <button class="sp-btn sp-btn--ghost sp-btn--sm" type="button" @click="refreshAudit">重新加载</button>
    </section>

    <template v-else>
      <AcademicDecisionTraceCard
        v-if="progress.decisionTrace || progress.decisionText"
        class="graduation-decision"
        :trace="progress.decisionTrace"
        :content="progress.decisionText"
      />

      <section class="graduation-summary" aria-label="毕业自查概览">
        <article class="graduation-metric is-success">
          <span>已通过条件</span><strong>{{ passedCount }}</strong><small>来自共享毕业 evaluator</small>
        </article>
        <article class="graduation-metric" :class="blockingPendingCount ? 'is-warn' : 'is-success'">
          <span>待处理条件</span><strong>{{ blockingPendingCount }}</strong><small>{{ blockingPendingCount ? '请优先处理阻断项' : '当前没有阻断项' }}</small>
        </article>
        <article class="graduation-metric is-blue">
          <span>已获学分</span><strong>{{ obtainedCredits }}</strong><small>应修 {{ requiredCreditsText }} 学分</small>
        </article>
        <article class="graduation-metric" :class="warningCount ? 'is-danger' : 'is-neutral'">
          <span>学业预警</span><strong>{{ warningCount }}</strong><small>{{ warningCount ? '仍有预警需要核对' : '当前无学业预警' }}</small>
        </article>
      </section>

      <section class="sp-card graduation-checklist">
        <header class="graduation-section-head">
          <div>
            <span class="graduation-section-head__eyebrow">毕业条件清单</span>
            <h2>逐项核对真实业务事实</h2>
            <p>这里只展示共享毕业核验器已经得出的结果，不在页面重新计算毕业资格。</p>
          </div>
          <div class="graduation-section-head__legend"><span class="is-ok"></span>通过 <span class="is-warn"></span>待处理 / 待核验</div>
        </header>

        <div v-if="!progressItems.length" class="graduation-empty">
          <div aria-hidden="true">—</div>
          <strong>暂时没有可展示的毕业核验项</strong>
          <span>{{ progress.note || '请稍后重新核验，或联系教务老师确认毕业预审配置。' }}</span>
        </div>
        <div v-else class="graduation-items">
          <article v-for="item in progressItems" :key="`${item.item}:${item.result}`" class="graduation-item" :class="itemTone(item)">
            <div class="graduation-item__status" aria-hidden="true">{{ itemResult(item) === 'PASS' ? '✓' : '!' }}</div>
            <div class="graduation-item__body">
              <div class="graduation-item__head">
                <strong>{{ itemLabel(item.item) }}</strong>
                <StatusTag :text="itemResultText(item)" :tone="itemResult(item) === 'PASS' ? 'success' : 'warn'" />
              </div>
              <p>{{ itemEvidenceText(item) }}</p>
            </div>
          </article>
        </div>
      </section>

      <section v-if="warningCount" class="sp-card graduation-warnings">
        <header class="graduation-section-head graduation-section-head--compact">
          <div>
            <span class="graduation-section-head__eyebrow">需要关注</span>
            <h2>学业预警</h2>
          </div>
          <span>{{ warningCount }} 项</span>
        </header>
        <div class="graduation-warning-list">
          <article v-for="(warning, index) in warningItems" :key="warning.id || index">
            <span aria-hidden="true">!</span>
            <div><strong>{{ warning.name || warning.category || warning.title || '学业预警' }}</strong><p>{{ warning.text || warning.message || warning.reason || '请按学校要求完成处理后再重新核验。' }}</p></div>
          </article>
        </div>
      </section>

      <section class="graduation-trust">
        <div class="graduation-trust__icon" aria-hidden="true">i</div>
        <div>
          <strong>{{ progress.hasAudit ? '实时自查与正式毕业结论分开保存' : '当前结果是实时自查，不等同正式毕业结论' }}</strong>
          <span>{{ progress.note || '页面刷新不会创建新的正式毕业预审记录；最终毕业结论仍以学校正式审核形成的不可变事实为准。' }}</span>
        </div>
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import AcademicDecisionTraceCard from '../../components/academic/AcademicDecisionTraceCard.vue'
import StateBlock from '../../components/StateBlock.vue'
import StatusTag from '../../components/StatusTag.vue'
import { portalApi } from '../../services/portalApi'
import { localizeVisibleEnumText } from '../../services/visibleEnumLocalization'

const loading = ref(true)
const error = ref('')
const audit = ref({ progress: {}, credits: {}, warnings: {} })

const ITEM_LABELS = {
  STATUS: '学籍状态', CREDIT: '总学分', COURSE_REQUIRED: '必修课程', COURSE_ELECTIVE: '选修学分',
  PRACTICE: '实践环节', INTERNSHIP: '岗位实习', GRADUATION_DESIGN: '毕业设计', DISCIPLINE: '处分情况',
  EMPLOYMENT: '就业填报', ARCHIVE: '学工归档', FEE: '费用结清'
}
const ADVISORY_UNKNOWN_ITEMS = new Set(['EMPLOYMENT', 'FEE'])
const FORMAL_STATUS = {
  DRAFT: '尚未正式预审', PENDING: '正式预审待处理', RUNNING: '正式预审中',
  SYSTEM_PASSED: '正式预审通过', SYSTEM_ABNORMAL: '正式预审存在阻断项', PASSED: '正式预审通过', FAILED: '正式预审未通过',
  GRADUATED: '已形成毕业结论', COMPLETED: '已形成结业结论', DELAYED: '延期毕业'
}

const progress = computed(() => audit.value.progress || {})
const credits = computed(() => audit.value.credits || {})
const progressItems = computed(() => Array.isArray(progress.value.items) ? progress.value.items : [])
const warningItems = computed(() => Array.isArray(audit.value.warnings?.items) ? audit.value.warnings.items : [])
const warningCount = computed(() => warningItems.value.length)
const passedCount = computed(() => progressItems.value.filter((item) => itemResult(item) === 'PASS').length)
const advisoryPendingCount = computed(() => progressItems.value.filter((item) =>
  itemResult(item) === 'UNKNOWN' && ADVISORY_UNKNOWN_ITEMS.has(String(item?.item || '').toUpperCase())).length)
const blockingPendingCount = computed(() => progressItems.value.filter((item) => {
  const result = itemResult(item)
  const code = String(item?.item || '').toUpperCase()
  return result !== 'PASS' && !(result === 'UNKNOWN' && ADVISORY_UNKNOWN_ITEMS.has(code))
}).length)
const overallPassed = computed(() => String(progress.value.overall || '').toUpperCase() === 'SYSTEM_PASSED')
const obtainedCredits = computed(() => Number(credits.value.obtainedCredits || 0))
const requiredCredits = computed(() => Number(credits.value.requiredCredits || 0))
const requiredCreditsText = computed(() => requiredCredits.value || '—')
const creditPct = computed(() => {
  if (!requiredCredits.value) return obtainedCredits.value ? 100 : 0
  return Math.max(0, Math.min(100, Math.round(obtainedCredits.value / requiredCredits.value * 100)))
})
const formalStatusText = computed(() => {
  if (!progress.value.hasAudit) return '尚未纳入正式预审'
  const conclusion = String(progress.value.conclusion || '').toUpperCase()
  if (conclusion && FORMAL_STATUS[conclusion]) return FORMAL_STATUS[conclusion]
  const status = String(progress.value.status || progress.value.formalOverall || '').toUpperCase()
  return FORMAL_STATUS[status] || '已纳入正式预审'
})
const heroDescription = computed(() => {
  if (overallPassed.value) return '当前实时核验未发现毕业资格阻断项。你仍可逐项核对学分、实习、毕业设计等事实；最终结论以学校正式审核为准。'
  return '系统已经按学校现有毕业规则完成实时核验。先看最上方规则解释，再逐项处理未通过或待核验条件。'
})

function itemResult(item) { return String(item?.result || 'UNKNOWN').toUpperCase() }
function itemResultText(item) {
  const value = itemResult(item)
  return value === 'PASS' ? '已通过' : value === 'FAIL' ? '未达标' : '待核验'
}
function itemLabel(code) { return ITEM_LABELS[String(code || '').toUpperCase()] || code || '毕业条件' }
function itemTone(item) { return itemResult(item) === 'PASS' ? 'is-pass' : 'is-pending' }
function itemEvidenceFallback(item) {
  return itemResult(item) === 'PASS' ? '学校业务系统已经记录满足该项条件的有效事实。' : '当前正式数据还不足以确认该项通过，请按上方建议处理后重新核验。'
}
function itemEvidenceText(item) {
  const raw = String(item?.evidence || '').trim()
  const match = raw.match(/^student_status=([A-Z0-9_]+)$/)
  if (match) {
    const localized = localizeVisibleEnumText(match[1])
    return `当前学籍状态：${localized === match[1] ? '状态待确认' : localized}`
  }
  return raw || itemEvidenceFallback(item)
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const data = await portalApi.academicGraduationAudit()
    audit.value = data && typeof data === 'object' ? data : { progress: {}, credits: {}, warnings: {} }
  } catch (e) {
    error.value = e?.message || '毕业资格数据读取失败，请稍后重试'
  } finally {
    loading.value = false
  }
}

async function refreshAudit() {
  await load()
}

onMounted(load)
</script>

<style scoped>
.graduation-page { max-width: 1180px; margin: 0 auto; }
.graduation-hero {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 230px;
  gap: 28px;
  margin-bottom: 16px;
  padding: 28px 30px;
  overflow: hidden;
  border: 1px solid #fed7aa;
  border-radius: 20px;
  background: radial-gradient(circle at 86% 12%, rgba(251,191,36,.18), transparent 27%), linear-gradient(135deg, #fff 0%, #fffdf9 55%, #fff7ed 100%);
  box-shadow: 0 18px 44px -36px rgba(180,83,9,.45);
}
.graduation-hero.is-passed { border-color: #bbf7d0; background: radial-gradient(circle at 86% 12%, rgba(34,197,94,.14), transparent 28%), linear-gradient(135deg, #fff 0%, #fbfffc 55%, #f0fdf4 100%); box-shadow: 0 18px 44px -36px rgba(22,163,74,.4); }
.graduation-hero__eyebrow { display: flex; align-items: center; gap: 8px; color: var(--warn-fg); font-size: 12px; font-weight: 700; letter-spacing: .08em; }
.graduation-hero.is-passed .graduation-hero__eyebrow { color: var(--ok-fg); }
.graduation-hero__eyebrow span { width: 7px; height: 7px; border-radius: 50%; background: currentColor; box-shadow: 0 0 0 5px rgba(180,83,9,.08); }
.graduation-hero.is-passed .graduation-hero__eyebrow span { box-shadow: 0 0 0 5px rgba(22,163,74,.08); }
.graduation-hero h1 { margin: 10px 0 7px; color: var(--t1); font-size: 27px; letter-spacing: -.02em; }
.graduation-hero p { max-width: 750px; margin: 0; color: var(--t2); font-size: 13.5px; line-height: 1.75; }
.graduation-hero__chips { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 16px; }
.graduation-hero__chips span { padding: 6px 10px; border: 1px solid rgba(180,83,9,.10); border-radius: 999px; background: rgba(255,255,255,.76); color: var(--t2); font-size: 11.5px; }
.graduation-hero.is-passed .graduation-hero__chips span { border-color: rgba(22,163,74,.10); }
.graduation-hero__score { display: grid; align-content: center; gap: 8px; padding-left: 22px; border-left: 1px solid rgba(180,83,9,.12); }
.graduation-hero.is-passed .graduation-hero__score { border-left-color: rgba(22,163,74,.12); }
.graduation-hero__score > span { color: var(--t4); font-size: 11px; }
.graduation-hero__score > strong { color: var(--t1); font-size: 36px; line-height: 1; font-variant-numeric: tabular-nums; }
.graduation-hero__score > strong small { margin-left: 2px; color: var(--t3); font-size: 13px; font-weight: 500; }
.graduation-hero__bar { height: 7px; margin: 2px 0 5px; overflow: hidden; border-radius: 999px; background: rgba(180,83,9,.09); }
.graduation-hero__bar i { display: block; height: 100%; border-radius: inherit; background: linear-gradient(90deg, #f59e0b, #d97706); }
.graduation-hero.is-passed .graduation-hero__bar { background: rgba(22,163,74,.09); }
.graduation-hero.is-passed .graduation-hero__bar i { background: linear-gradient(90deg, #4ade80, #16a34a); }
.graduation-decision { margin-bottom: 14px; }
.graduation-summary { display: grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap: 12px; margin-bottom: 14px; }
.graduation-metric { padding: 17px 18px; border: 1px solid var(--line); border-radius: 15px; background: #fff; box-shadow: 0 10px 26px -24px rgba(15,23,42,.35); }
.graduation-metric span, .graduation-metric strong, .graduation-metric small { display: block; }
.graduation-metric span { color: var(--t3); font-size: 11.5px; }
.graduation-metric strong { margin-top: 5px; color: var(--t1); font-size: 23px; font-variant-numeric: tabular-nums; }
.graduation-metric small { margin-top: 4px; color: var(--t4); font-size: 10.8px; }
.graduation-metric.is-success { border-top-color: #bbf7d0; }
.graduation-metric.is-warn { border-top-color: #fed7aa; }
.graduation-metric.is-danger { border-top-color: #fecaca; }
.graduation-metric.is-blue { border-top-color: #bfdbfe; }
.graduation-checklist { padding: 0; overflow: hidden; }
.graduation-section-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 18px; padding: 20px 22px; border-bottom: 1px solid var(--line2); background: linear-gradient(180deg,#fff,#fcfdff); }
.graduation-section-head__eyebrow { color: var(--pri); font-size: 10.5px; font-weight: 700; letter-spacing: .08em; }
.graduation-section-head h2 { margin: 5px 0 0; font-size: 16px; }
.graduation-section-head p { margin: 5px 0 0; color: var(--t3); font-size: 11.5px; line-height: 1.6; }
.graduation-section-head__legend { display: flex; align-items: center; gap: 6px; flex-shrink: 0; color: var(--t3); font-size: 11px; }
.graduation-section-head__legend span { width: 7px; height: 7px; margin-left: 6px; border-radius: 50%; }
.graduation-section-head__legend span.is-ok { background: var(--ok-fg); }
.graduation-section-head__legend span.is-warn { background: var(--warn-fg); }
.graduation-items { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 0; }
.graduation-item { display: grid; grid-template-columns: 38px minmax(0,1fr); gap: 12px; min-height: 118px; padding: 18px 20px; border-bottom: 1px solid var(--line2); }
.graduation-item:nth-child(odd) { border-right: 1px solid var(--line2); }
.graduation-item__status { display: grid; place-items: center; width: 38px; height: 38px; border-radius: 12px; background: var(--warn-bg); color: var(--warn-fg); font-size: 15px; font-weight: 800; }
.graduation-item.is-pass .graduation-item__status { background: var(--ok-bg); color: var(--ok-fg); }
.graduation-item__head { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
.graduation-item__head strong { color: var(--t1); font-size: 13.5px; }
.graduation-item p { margin: 7px 0 0; color: var(--t3); font-size: 11.5px; line-height: 1.7; word-break: break-word; }
.graduation-empty { display: grid; justify-items: center; gap: 7px; padding: 42px 22px; text-align: center; }
.graduation-empty > div { display: grid; place-items: center; width: 46px; height: 46px; border-radius: 14px; background: var(--draft-bg); color: var(--t3); }
.graduation-empty strong { font-size: 13.5px; }
.graduation-empty span { max-width: 520px; color: var(--t3); font-size: 11.5px; line-height: 1.65; }
.graduation-warnings { margin-top: 14px; padding: 0; overflow: hidden; }
.graduation-section-head--compact { align-items: center; padding: 16px 20px; }
.graduation-section-head--compact > span { padding: 5px 9px; border-radius: 8px; background: var(--danger-bg); color: var(--danger-fg); font-size: 11px; font-weight: 600; }
.graduation-warning-list article { display: grid; grid-template-columns: 30px minmax(0,1fr); gap: 11px; padding: 14px 20px; border-bottom: 1px solid var(--line2); }
.graduation-warning-list article:last-child { border-bottom: 0; }
.graduation-warning-list article > span { display: grid; place-items: center; width: 30px; height: 30px; border-radius: 9px; background: var(--danger-bg); color: var(--danger-fg); font-weight: 800; }
.graduation-warning-list strong { font-size: 12.5px; }
.graduation-warning-list p { margin: 4px 0 0; color: var(--t3); font-size: 11.5px; line-height: 1.65; }
.graduation-trust { display: grid; grid-template-columns: 34px minmax(0,1fr); gap: 12px; margin-top: 14px; padding: 15px 17px; border: 1px solid #e5edf9; border-radius: 14px; background: rgba(255,255,255,.74); }
.graduation-trust__icon { display: grid; place-items: center; width: 34px; height: 34px; border-radius: 10px; background: var(--pri-50); color: var(--pri); font-family: Georgia,serif; font-weight: 700; }
.graduation-trust strong, .graduation-trust span { display: block; }
.graduation-trust strong { color: var(--t1); font-size: 12.5px; }
.graduation-trust span { margin-top: 4px; color: var(--t3); font-size: 11.5px; line-height: 1.7; }
.graduation-error { display: grid; justify-items: center; gap: 8px; padding: 38px 22px; text-align: center; }
.graduation-error__icon { display: grid; place-items: center; width: 42px; height: 42px; border-radius: 13px; background: var(--danger-bg); color: var(--danger-fg); font-weight: 800; }
.graduation-error > span { color: var(--t3); font-size: 12px; }
@media (max-width: 900px) {
  .graduation-hero { grid-template-columns: 1fr; }
  .graduation-hero__score { grid-template-columns: auto 1fr; align-items: center; padding: 15px 0 0; border-top: 1px solid rgba(180,83,9,.12); border-left: 0; }
  .graduation-hero__score > strong { justify-self: end; }
  .graduation-hero__bar, .graduation-hero__score .sp-btn { grid-column: 1 / -1; }
  .graduation-summary { grid-template-columns: repeat(2,minmax(0,1fr)); }
}
@media (max-width: 640px) {
  .graduation-hero { padding: 22px; }
  .graduation-hero h1 { font-size: 23px; }
  .graduation-summary, .graduation-items { grid-template-columns: 1fr; }
  .graduation-item:nth-child(odd) { border-right: 0; }
  .graduation-section-head { flex-direction: column; }
}
</style>