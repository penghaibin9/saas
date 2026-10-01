<template>
  <section class="gdep" aria-label="延期答辩与优秀成果">
    <header class="gdep__head">
      <div>
        <strong>延期答辩与优秀成果</strong>
        <p>先看当前状态和下一步；延期答辩与二次答辩分开处理，成绩优秀也不等于已认定优秀成果。</p>
      </div>
      <button class="gdep__refresh" :disabled="loading" @click="load">{{ loading ? '刷新中…' : '刷新' }}</button>
    </header>

    <div v-if="loading && !data" class="gdep__state">正在加载当前批次扩展事项…</div>
    <div v-else-if="error" class="gdep__state gdep__state--error">
      <div><strong>扩展事项加载失败</strong><p>{{ error }}。这不是“暂无业务”，请重试。</p></div>
      <button @click="load">重新加载</button>
    </div>

    <template v-else-if="data">
      <div class="gdep__summary">
        <div><span>当前批次</span><strong>{{ data.batchId || '未识别' }}</strong></div>
        <div><span>延期状态</span><strong>{{ data.defenseDelay?.statusLabel || '未申请' }}</strong></div>
        <div><span>优秀成果</span><strong>{{ data.excellentOutcome?.statusLabel || '暂无认定' }}</strong></div>
        <div><span>下一步</span><strong>{{ nextStep }}</strong></div>
      </div>

      <article v-if="data.defenseDelay" class="gdep__card">
        <div class="gdep__card-head">
          <div><strong>最近一次延期答辩申请</strong><small>{{ data.defenseDelay.requestedAt || '' }}</small></div>
          <span>{{ data.defenseDelay.statusLabel }}</span>
        </div>
        <p>申请理由：{{ data.defenseDelay.reason }}</p>
        <ol class="gdep__timeline">
          <li :class="{ done: data.defenseDelay.advisorReviewedBy }">导师审核：{{ data.defenseDelay.advisorComment || (data.defenseDelay.advisorReviewedBy ? '已处理' : '待处理') }}</li>
          <li :class="{ done: data.defenseDelay.majorReviewedBy }">专业复核：{{ data.defenseDelay.majorComment || (data.defenseDelay.majorReviewedBy ? '已处理' : '待处理') }}</li>
          <li :class="{ done: data.defenseDelay.collegeReviewedBy }">学院审批：{{ data.defenseDelay.collegeComment || (data.defenseDelay.collegeReviewedBy ? '已处理' : '待处理') }}</li>
          <li :class="{ done: data.defenseDelay.plannedDefenseDate }">重新排期：{{ data.defenseDelay.plannedDefenseDate ? `${data.defenseDelay.plannedDefenseDate} · ${data.defenseDelay.defenseGroupName || '答辩组待发布'}` : '待安排' }}</li>
        </ol>
      </article>

      <article v-if="data.canApplyDelay" class="gdep__card gdep__card--action">
        <div class="gdep__card-head">
          <div><strong>{{ data.defenseDelay ? '重新申请延期答辩' : '申请延期答辩' }}</strong><small>提交后依次由导师、专业负责人、学院管理员审核</small></div>
          <span>可申请</span>
        </div>
        <textarea v-model.trim="reason" maxlength="1000" placeholder="说明延期原因、当前情况和预计准备时间（至少10字）" />
        <div class="gdep__submit-row">
          <small>{{ reason.length }}/1000</small>
          <button class="gdep__primary" :disabled="submitting || reason.length < 10" @click="applyDelay">
            {{ submitting ? '提交中…' : '提交延期申请' }}
          </button>
        </div>
      </article>
      <article v-else-if="!data.defenseDelay" class="gdep__card">
        <div class="gdep__card-head"><strong>延期答辩</strong><span>当前不可申请</span></div>
        <p>仅进入成果检查或答辩阶段、且成绩尚未发布时可申请。</p>
      </article>

      <article class="gdep__card">
        <div class="gdep__card-head">
          <div><strong>优秀成果认定</strong><small>导师提名 → 专业复核 → 学院终审</small></div>
          <span>{{ data.excellentOutcome?.statusLabel || '暂无认定记录' }}</span>
        </div>
        <template v-if="data.excellentOutcome">
          <p>提名理由：{{ data.excellentOutcome.nominationReason }}</p>
          <p v-if="data.excellentOutcome.majorReviewComment">专业意见：{{ data.excellentOutcome.majorReviewComment }}</p>
          <p v-if="data.excellentOutcome.collegeReviewComment">学院意见：{{ data.excellentOutcome.collegeReviewComment }}</p>
        </template>
        <p v-else>成绩等级为优秀只是候选条件，须由导师提名并通过专业、学院审核。</p>
      </article>
    </template>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { graduationExtensionApi } from '@/services/graduationExtensionApi'

const data = ref(null)
const loading = ref(false)
const error = ref('')
const reason = ref('')
const submitting = ref(false)

const nextStep = computed(() => {
  const delay = data.value?.defenseDelay
  if (data.value?.canApplyDelay) return delay ? '可重新提交延期申请' : '可提交延期申请'
  if (!delay) return '继续完成当前毕设阶段'
  const map = {
    PENDING_ADVISOR: '等待导师审核',
    PENDING_MAJOR: '等待专业复核',
    PENDING_COLLEGE: '等待学院审批',
    APPROVED: '等待学院重新排期',
    SCHEDULED: '关注答辩组重新发布',
    REJECTED: '按意见整改后继续当前流程',
    CANCELLED: '继续当前毕设流程'
  }
  return map[delay.status] || '查看审核意见'
})

async function load() {
  if (loading.value) return
  loading.value = true
  error.value = ''
  try { data.value = await graduationExtensionApi.my() }
  catch (e) { error.value = e?.message || '延期答辩与优秀成果状态加载失败' }
  finally { loading.value = false }
}

async function applyDelay() {
  if (reason.value.length < 10 || submitting.value) return
  submitting.value = true
  error.value = ''
  try {
    await graduationExtensionApi.applyDelay(reason.value)
    reason.value = ''
    await load()
  } catch (e) {
    error.value = e?.message || '延期答辩申请提交失败'
  } finally {
    submitting.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.gdep { max-width:1120px; margin:16px auto; padding:18px; border:1px solid #e5e6eb; border-radius:14px; background:#fff; box-shadow:0 4px 18px rgb(15 23 42 / 5%); }
.gdep__head { display:flex; justify-content:space-between; gap:20px; align-items:flex-start; }
.gdep__head > div { min-width:0; }
.gdep__head strong { font-size:17px; color:#1d2129; }
.gdep__head p,.gdep__card p,.gdep__state p { margin:5px 0 0; color:#667085; font-size:13px; line-height:1.65; }
.gdep__refresh,.gdep__state button,.gdep__primary { min-height:36px; padding:0 14px; border:1px solid #1677ff; border-radius:8px; background:#fff; color:#1677ff; cursor:pointer; white-space:nowrap; }
.gdep__summary { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:10px; margin-top:16px; }
.gdep__summary > div { padding:12px; border:1px solid #edf0f5; border-radius:10px; background:#f8fbff; }
.gdep__summary span,.gdep__summary strong { display:block; }
.gdep__summary span { color:#86909c; font-size:12px; }
.gdep__summary strong { margin-top:5px; color:#1d2129; font-size:14px; }
.gdep__state { margin-top:14px; padding:14px; border-radius:10px; background:#f7f8fa; color:#4e5969; }
.gdep__state--error { display:flex; justify-content:space-between; gap:16px; align-items:flex-start; border:1px solid #ffccc7; background:#fff2f0; color:#cf1322; }
.gdep__card { margin-top:12px; padding:14px 16px; border:1px solid #edf0f5; border-radius:11px; background:#fafcff; }
.gdep__card--action { border-color:#b7d5ff; background:#f4f9ff; }
.gdep__card-head { display:flex; justify-content:space-between; gap:12px; align-items:flex-start; }
.gdep__card-head > div { min-width:0; }
.gdep__card-head strong,.gdep__card-head small { display:block; }
.gdep__card-head small { margin-top:3px; color:#86909c; font-size:12px; }
.gdep__card-head > span { flex:none; padding:3px 8px; border-radius:999px; background:#e8f3ff; color:#1677ff; font-size:12px; }
.gdep__timeline { margin:10px 0 0; padding-left:20px; color:#86909c; font-size:13px; line-height:1.8; }
.gdep__timeline li.done { color:#1f7a4d; }
.gdep textarea { width:100%; min-height:88px; margin:12px 0 8px; padding:11px; box-sizing:border-box; border:1px solid #cfd6e4; border-radius:9px; resize:vertical; background:#fff; }
.gdep__submit-row { display:flex; justify-content:space-between; gap:12px; align-items:center; }
.gdep__submit-row small { color:#86909c; }
.gdep__primary { background:#1677ff; color:#fff; }
.gdep button:disabled { opacity:.55; cursor:not-allowed; }
@media (max-width: 760px) {
  .gdep { margin:10px; padding:14px; }
  .gdep__summary { grid-template-columns:repeat(2,minmax(0,1fr)); }
  .gdep__head,.gdep__state--error { gap:12px; }
}
</style>
