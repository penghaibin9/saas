<template>
  <section class="gdep" aria-label="毕业设计扩展事项">
    <header>
      <div><strong>延期答辩与优秀成果</strong><p>延期答辩按学生申请、导师、专业、学院顺序审核；成绩优秀不等于已认定优秀成果。</p></div>
      <button :disabled="loading" @click="load">刷新</button>
    </header>
    <p v-if="error" class="gdep__error">{{ error }}</p>
    <template v-else-if="data">
      <article v-if="data.defenseDelay" class="gdep__card">
        <div><strong>延期答辩</strong><span>{{ data.defenseDelay.statusLabel }}</span></div>
        <p>申请理由：{{ data.defenseDelay.reason }}</p>
        <p v-if="data.defenseDelay.advisorComment">导师意见：{{ data.defenseDelay.advisorComment }}</p>
        <p v-if="data.defenseDelay.majorComment">专业意见：{{ data.defenseDelay.majorComment }}</p>
        <p v-if="data.defenseDelay.collegeComment">学院意见：{{ data.defenseDelay.collegeComment }}</p>
        <p v-if="data.defenseDelay.plannedDefenseDate">重新排期：{{ data.defenseDelay.plannedDefenseDate }} · {{ data.defenseDelay.defenseGroupName || '答辩组待发布' }}</p>
      </article>
      <article v-else-if="data.canApplyDelay" class="gdep__card">
        <div><strong>申请延期答辩</strong><span>尚未申请</span></div>
        <textarea v-model.trim="reason" maxlength="1000" placeholder="说明延期原因、当前情况和预计准备时间（至少10字）" />
        <button class="gdep__primary" :disabled="submitting || reason.length < 10" @click="applyDelay">提交延期申请</button>
      </article>
      <article v-else class="gdep__card"><div><strong>延期答辩</strong><span>当前不可申请</span></div><p>仅进入成果检查或答辩阶段、且成绩尚未发布时可申请。</p></article>

      <article v-if="data.excellentOutcome" class="gdep__card">
        <div><strong>优秀成果认定</strong><span>{{ data.excellentOutcome.statusLabel }}</span></div>
        <p>提名理由：{{ data.excellentOutcome.nominationReason }}</p>
        <p v-if="data.excellentOutcome.majorReviewComment">专业意见：{{ data.excellentOutcome.majorReviewComment }}</p>
        <p v-if="data.excellentOutcome.collegeReviewComment">学院意见：{{ data.excellentOutcome.collegeReviewComment }}</p>
      </article>
      <article v-else class="gdep__card"><div><strong>优秀成果认定</strong><span>暂无认定记录</span></div><p>成绩等级为优秀只是候选条件，须由导师提名并通过专业、学院审核。</p></article>
    </template>
  </section>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { graduationExtensionApi } from '@/services/graduationExtensionApi'

const data = ref(null)
const loading = ref(false)
const error = ref('')
const reason = ref('')
const submitting = ref(false)

async function load() {
  loading.value = true; error.value = ''
  try { data.value = await graduationExtensionApi.my() }
  catch (e) { error.value = e?.message || '延期答辩与优秀成果状态加载失败' }
  finally { loading.value = false }
}
async function applyDelay() {
  if (reason.value.length < 10 || submitting.value) return
  submitting.value = true
  try { await graduationExtensionApi.applyDelay(reason.value); reason.value = ''; await load() }
  catch (e) { error.value = e?.message || '延期答辩申请提交失败' }
  finally { submitting.value = false }
}
onMounted(load)
</script>

<style scoped>
.gdep { max-width:1120px; margin:16px auto; padding:16px; border:1px solid #e5e6eb; border-radius:12px; background:#fff; }
.gdep > header { display:flex; justify-content:space-between; gap:20px; align-items:flex-start; }.gdep header p,.gdep__card p { margin:5px 0 0; color:#86909c; font-size:13px; line-height:1.6; }.gdep header button,.gdep__primary { min-height:36px; padding:0 14px; border:1px solid #1677ff; border-radius:8px; background:#fff; color:#1677ff; cursor:pointer; }
.gdep__card { margin-top:12px; padding:13px 14px; border:1px solid #edf0f5; border-radius:10px; background:#fafcff; }.gdep__card > div { display:flex; justify-content:space-between; gap:12px; }.gdep__card span { color:#1677ff; font-size:13px; }.gdep textarea { width:100%; min-height:82px; margin:10px 0; padding:10px; box-sizing:border-box; border:1px solid #d9d9d9; border-radius:8px; }.gdep__primary { background:#1677ff; color:#fff; }.gdep__primary:disabled { opacity:.5; cursor:not-allowed; }.gdep__error { color:#cf1322; }
</style>
