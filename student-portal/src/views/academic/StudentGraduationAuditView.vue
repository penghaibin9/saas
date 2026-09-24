<template>
  <div data-academic-page class="sp-page academic-prototype graduation-page">
    <AcademicPrototypeHeader :title="showEvidence ? '毕业自查证据' : '毕业资格自查'" group="培养与毕业" :object="showEvidence" description="实时自查与正式审核分开，逐项核对缺口和补正路径。" :loading="loading" @refresh="refreshAudit" />
    <StateBlock v-if="loading" type="loading" text="正在读取毕业资格、学分和预警事实…" />
    <div v-else-if="error" class="card pad"><StateBlock type="error" :text="error" /><button class="btn" @click="refreshAudit">重新加载</button></div>
    <div v-else class="stack">
      <div class="notice amber"><AcademicPrototypeIcon name="circle-info" /><span>实时自查只读计算，不创建正式审核记录。正式毕业结论另列。</span></div>
      <div class="grid-equal">
        <section class="card pad"><small>当前实时自查</small><h2 class="summary-title">{{ !progressItems.length ? '当前事实待核对' : overallPassed ? '当前实时核验已通过' : '尚有条件需要补齐' }}</h2><p class="muted">根据当前正式业务事实计算</p><small>{{ passedCount }} 项通过 · {{ blockingPendingCount }} 项待处理 · {{ advisoryPendingCount }} 项提示</small></section>
        <section class="card pad"><small>最近正式审核</small><h2 class="summary-title">{{ formalStatusText }}</h2><p class="muted">不能把实时通过显示成已批准毕业</p></section>
      </div>
      <section class="card"><header class="card-head"><h2>{{ showEvidence ? '当前证据与补正路径' : '需要关注的证据' }}</h2></header><div class="card-body">
        <StateBlock v-if="!progressItems.length" type="empty" :text="progress.note || '暂时没有可展示的毕业核验项，请重新核对。'" />
        <div class="timeline"><div v-for="item in progressItems" :key="item.item" class="taskline" :class="itemTone(item)"><div class="iconbox" :class="itemResult(item) === 'PASS' ? 'green' : 'amber'"><AcademicPrototypeIcon :name="itemResult(item) === 'PASS' ? 'circle-check' : 'circle-info'" /></div><div class="grow"><strong>{{ itemLabel(item.item) }}</strong><small>{{ itemEvidenceText(item) }}</small><RouterLink v-if="showEvidence && remedyRoute(item)" class="btn link small" :to="remedyRoute(item)">查看相关事项</RouterLink></div><StatusTag :text="itemResultText(item)" :tone="itemResult(item) === 'PASS' ? 'success' : 'warn'" /></div></div>
        <div class="spacer14"></div><button v-if="!showEvidence" class="btn primary" @click="showEvidence = true">展开证据与补正路径</button><div v-else class="row wrap"><RouterLink class="btn primary" to="/academic/makeup">查看课程补救</RouterLink><button class="btn" @click="showEvidence = false">返回毕业自查</button></div>
      </div></section>
      <template v-if="showEvidence">
        <AcademicDecisionTraceCard v-if="decisionTrace" :trace="decisionTrace" :content="decisionContent" />
        <section v-if="safeDecisionText" class="card pad"><h2>规则说明</h2><p class="muted">{{ safeDecisionText }}</p></section>
        <section class="card pad"><p>{{ blockingPendingCount ? '请优先处理阻断项' : '当前没有阻断项' }}</p><p class="muted">{{ heroDescription }}</p><div class="spacer14"></div><div class="row between"><span>{{ creditProgressLabel }}：{{ obtainedCreditsText }} / {{ requiredCreditsText }} 学分</span><span>{{ creditPctText }}{{ creditPct !== null ? '%' : '' }}</span></div><div class="progress"><i :style="{ width: creditBarWidth }"></i></div><p v-if="warningCount" class="muted">{{ warningCount }} 项学业预警需核对，请前往学业预警查看责任人与处理要求。</p></section>
      </template>
      <div class="notice"><AcademicPrototypeIcon name="circle-info" /><span>缺少证据不代表通过，最终毕业结论以学校正式审核为准。</span></div>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import StateBlock from '../../components/StateBlock.vue'
import StatusTag from '../../components/StatusTag.vue'
import AcademicPrototypeHeader from '../../components/academic/AcademicPrototypeHeader.vue'
import AcademicPrototypeIcon from '../../components/academic/AcademicPrototypeIcon.vue'
import AcademicDecisionTraceCard from '../../components/academic/AcademicDecisionTraceCard.vue'
import { createStudentAcademicCommandGuard, readStudentAcademicSnapshot, studentAcademicIdentity } from '../../components/academic/studentAcademicCommandGuard'

import { academicErrorKind, academicErrorMessage } from '../../components/academic/studentAcademicUi'
import { portalApi } from '../../services/portalApi'
import { localizeVisibleEnumText } from '../../services/visibleEnumLocalization'
import { useSessionStore } from '../../stores/session'

const session = useSessionStore()
const guard = createStudentAcademicCommandGuard(() => studentAcademicIdentity(session))
const loading = ref(true)
const error = ref('')
const showEvidence = ref(false)
function remedyRoute(item) { return ({ STATUS:'/academic/status', CREDIT:'/academic/credits', COURSE_REQUIRED:'/academic/makeup', COURSE_ELECTIVE:'/academic/selection', PRACTICE:'/academic/credits', INTERNSHIP:'/internship', GRADUATION_DESIGN:'/graduation', EMPLOYMENT:'/employment' })[String(item.item).toUpperCase()] || '' }
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
function traceOf(progress) { return progress && typeof progress.decisionTrace === 'object' ? progress.decisionTrace : null }
function decisionTextOf(progress) { return progress && progress.decisionText }
const decisionTrace = computed(() => traceOf(progress.value))
const decisionContent = computed(() => {
  const source = decisionTextOf(progress.value)
  return source && typeof source === 'object' ? source : null
})
const credits = computed(() => audit.value.credits || {})
const progressItems = computed(() => Array.isArray(progress.value.items) ? progress.value.items : [])
const warningItems = computed(() => Array.isArray(audit.value.warnings?.items) ? audit.value.warnings.items : [])
const warningCount = computed(() => {
  const total = Number(audit.value.warnings?.total)
  return Number.isFinite(total) && total >= warningItems.value.length ? total : warningItems.value.length
})
const passedCount = computed(() => progressItems.value.filter((item) => itemResult(item) === 'PASS').length)
const advisoryPendingCount = computed(() => progressItems.value.filter((item) =>
  itemResult(item) === 'UNKNOWN' && ADVISORY_UNKNOWN_ITEMS.has(String(item?.item || '').toUpperCase())).length)
const blockingPendingCount = computed(() => progressItems.value.filter((item) => {
  const result = itemResult(item)
  const code = String(item?.item || '').toUpperCase()
  return result !== 'PASS' && !(result === 'UNKNOWN' && ADVISORY_UNKNOWN_ITEMS.has(code))
}).length)
const overallPassed = computed(() => String(progress.value.overall || '').toUpperCase() === 'SYSTEM_PASSED')
const obtainedCredits = computed(() => {
  const raw = credits.value.obtainedCredits
  if (raw === null || raw === undefined || raw === '') return null
  const value = Number(raw)
  return Number.isFinite(value) && value >= 0 ? value : null
})
const obtainedCreditsText = computed(() => obtainedCredits.value === null ? '待核验' : obtainedCredits.value)
const requiredCredits = computed(() => {
  const raw = credits.value.requiredCredits
  if (raw === null || raw === undefined || raw === '') return null
  const value = Number(raw)
  return Number.isFinite(value) && value > 0 ? value : null
})
const requiredCreditsText = computed(() => requiredCredits.value === null ? '待核验' : requiredCredits.value)
const creditPct = computed(() => {
  if (requiredCredits.value === null || obtainedCredits.value === null) return null
  return Math.max(0, Math.min(100, Math.round(obtainedCredits.value / requiredCredits.value * 100)))
})
const creditPctText = computed(() => creditPct.value === null ? '—' : creditPct.value)
const creditBarWidth = computed(() => `${creditPct.value === null ? 0 : creditPct.value}%`)
const creditProgressLabel = computed(() => requiredCredits.value === null || obtainedCredits.value === null ? '学分要求待核验' : '学分达成')
const safeDecisionText = computed(() => {
  const source = decisionTextOf(progress.value)
  const text = String(source && typeof source === 'object'
    ? [source.title, source.reason, source.nextStep].filter(Boolean).join('。')
    : source || '').trim()
  if (!text) return ''
  const lowered = text.toLowerCase()
  if (/[a-z][a-z0-9_]*(id|_id)\b/i.test(text) || /\b(traceback|sqlalchemy|select |insert |update |delete |tenant|permission|scope=|refid)\b/i.test(lowered)) return '学校已按当前毕业规则完成实时核验，请根据下方逐项结果处理。'
  return text.slice(0, 300)
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
  const code = String(item?.item || '').toUpperCase()
  if (!raw) return itemEvidenceFallback(item)
  if (code === 'ARCHIVE') {
    if (raw.includes('已归档')) return '学工归档包已经完成归档。'
    if (/待补齐|退回/.test(raw)) return '学工归档包需要补充或重新提交。'
    if (/处理中/.test(raw)) return '学工归档包正在办理中。'
    if (/未生成/.test(raw)) return '学工归档包尚未生成，当前需要人工核对。'
    return itemEvidenceFallback(item)
  }
  if (code === 'FEE') {
    const amount = raw.match(/(\d+)\s*笔约\s*([\d.]+)\s*元/)
    if (amount) return `教材费台账有 ${amount[1]} 笔约 ${amount[2]} 元待结清；学费、住宿费仍以财务核验为准。`
    return '费用结清状态待财务核验；该提示不直接形成毕业阻断结论。'
  }
  if (/供数查询失败|traceback|sqlalchemy|operationalerror|integrityerror|dataerror|\b(?:program|binding|ref|tenant)[a-z_]*id\b|\bscope=/i.test(raw)) {
    return '相关业务数据暂时无法完成核验，请稍后重试或联系负责老师。'
  }
  if (code === 'STATUS') {
    const match = raw.match(/^student_status=([A-Z0-9_]+)/i) || raw.match(/^status=([A-Z0-9_]+)/i)
    if (!match) return itemEvidenceFallback(item)
    const localized = localizeVisibleEnumText(match[1])
    return `当前学籍状态：${localized === match[1] ? '状态待确认' : localized}`
  }
  if (/\bstatus=|\b[A-Za-z]+(?:Error|Exception)\b|[A-Za-z]+Id\b/.test(raw)) return itemEvidenceFallback(item)
  return raw.slice(0, 180)
}

async function load() {
  loading.value = true
  error.value = ''
  const read = await readStudentAcademicSnapshot(guard, () => portalApi.academicGraduationAudit(), 'academic-graduation')
  if (read.stale) return false
  if (!read.ok) {
    if (academicErrorKind(read.error) === 'forbidden') { guard.invalidate(); audit.value = { progress: {}, credits: {}, warnings: {} }; showEvidence.value = false }
    error.value = academicErrorMessage(read.error, '毕业资格数据读取失败，请稍后重试')
    loading.value = false
    return false
  }
  const data = read.value
  audit.value = data && typeof data === 'object' ? data : { progress: {}, credits: {}, warnings: {} }
  loading.value = false
  return true
}

async function refreshAudit() {
  await load()
}

onMounted(load)
onBeforeUnmount(() => guard.dispose())
</script>

<style src="../../components/academic/studentAcademicPrototype.css"></style>
<style scoped>.summary-title{margin-top:6px}.progress{margin-top:10px}.taskline :deep(.sp-tag){font-size:12px;border-radius:5px;padding:2px 7px}</style>
