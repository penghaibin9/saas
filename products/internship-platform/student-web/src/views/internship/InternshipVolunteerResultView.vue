<template>
  <main class="sp-page result-page">
    <header class="result-header">
      <div><p class="sp-muted">岗位实习 / 我的投递</p><h1>志愿办理结果</h1></div>
      <div class="result-tools"><button class="sp-btn sp-btn--ghost" @click="router.push('/messages')">消息通知</button>
        <button class="sp-btn sp-btn--ghost" :disabled="loading" @click="load">刷新结果</button></div>
    </header>
    <StateBlock v-if="loading" type="loading" text="正在核对原志愿结果…" />
    <StateBlock v-else-if="error" type="error" :text="error" />
    <template v-else-if="result">
      <p v-if="updatedSinceMessage" class="sp-notice" role="status">这条消息发出后，志愿已有更新。以下展示本组志愿的当前结果，请以当前状态为准。</p>
      <section class="sp-card result-summary" :class="{ 'is-approved': result.status === 'APPROVED' }" aria-label="当前办理结果">
        <div class="result-heading"><span class="sp-muted">{{ result.batchName }} · {{ result.campaignName }}</span>
          <StatusTag :text="statusText" :tone="result.status === 'APPROVED' ? 'success' : 'warn'" /></div>
        <h2>{{ statusText }}</h2><p class="result-guidance">{{ guidance }}</p>
        <div v-if="result.status === 'NEEDS_REVISION'" class="revision"><strong>学校补正意见</strong><p>{{ result.revisionReason || '请联系指导教师核对补正要求。' }}</p></div>
        <button v-if="result.status === 'NEEDS_REVISION' && result.campaignStatus === 'OPEN'" class="sp-btn" @click="openSelection">进入原招聘季补正</button>
        <p v-else-if="result.status === 'NEEDS_REVISION'" class="sp-muted">原招聘季当前未开放补正，请联系指导教师核对安排。</p>
        <dl class="result-facts"><div><dt>本组投递次数</dt><dd>{{ result.submissionVersion }} 次</dd></div>
          <div><dt>最近投递</dt><dd>{{ fmt(result.submittedAt) }}</dd></div>
          <div v-if="result.status === 'APPROVED'"><dt>学校确认</dt><dd>{{ fmt(result.approvedAt) }}</dd></div>
          <div v-else-if="result.status === 'NEEDS_REVISION'"><dt>学校退回</dt><dd>{{ fmt(result.revisionRequestedAt) }}</dd></div>
          <div v-else-if="result.teacherConfirmDeadline"><dt>学校确认截止</dt><dd>{{ fmt(result.teacherConfirmDeadline) }}</dd></div></dl>
      </section>
      <section class="sp-card result-choices" aria-label="本组志愿">
        <div class="result-heading"><h2>本组志愿</h2><span class="sp-muted">{{ result.items.length }} 个志愿</span></div>
        <p v-if="!result.items.length" class="sp-muted">本组暂无岗位志愿。</p>
        <article v-for="item in result.items" :key="item.id" class="result-choice">
          <span class="choice-order">{{ item.volunteerNo }}</span><div class="choice-content">
            <div class="result-heading"><h3>{{ item.positionName || '岗位名称未记录' }}</h3><StatusTag :status="item.status" /></div>
            <p class="sp-muted">{{ item.companyName || '企业名称未记录' }}</p>
            <p v-if="item.applicationStatement" class="choice-statement">{{ item.applicationStatement }}</p>
          </div>
        </article>
      </section>
      <p class="sp-muted result-footnote">此页始终对应原招聘季。查看消息不会修改志愿、解除锁定或办理上岗。</p>
    </template>
  </main>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import StateBlock from '../../components/StateBlock.vue'
import StatusTag from '../../components/StatusTag.vue'
import { internshipSelectionApi } from '../../services/internshipSelectionApi'

const route = useRoute()
const router = useRouter()
const result = ref(null)
const loading = ref(false)
const error = ref('')
let sequence = 0
let alive = true
const groupId = computed(() => typeof route.query.groupId === 'string' && /^[1-9]\d*$/.test(route.query.groupId) ? route.query.groupId : '')
const statusText = computed(() => ({ DRAFT: '尚未投递', SUBMITTED: '等待企业与学校处理', LOCKED: '企业拟接收，待学校确认', NEEDS_REVISION: '学校退回，请补正后重提', APPROVED: '学校已确认岗位', CLOSED: '本组志愿已关闭' }[result.value?.status] || '请核对办理状态'))
const updatedSinceMessage = computed(() => {
  const version = route.query.groupVersion
  return result.value && typeof version === 'string' && /^\d+$/.test(version) && version !== String(result.value.version)
})
const guidance = computed(() => {
  if (result.value?.lockExpired) return '学校确认期限已过，当前仍保留锁定记录。请联系指导教师核对后续安排。'
  return ({ APPROVED: '岗位已经确定。还需完成协议、保险及上岗核验，通过学校要求后再上岗。', NEEDS_REVISION: '请先阅读学校意见，补充材料并重新投递。此前企业处理意见属于旧投递记录。', LOCKED: '企业拟接收不等于正式落岗，请等待学校最终确认。', SUBMITTED: '投递已送达，请留意企业处理与学校确认消息。', DRAFT: '本组内容尚未正式投递。', CLOSED: '本组志愿已结束，保留记录供你查看。' }[result.value?.status] || '请联系指导教师核对当前安排。')
})
function fmt(value) {
  if (!value) return '尚无记录'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '时间待核对' : date.toLocaleString('zh-CN', { hour12: false })
}
function openSelection() {
  const row = result.value
  if (!row || row.status !== 'NEEDS_REVISION' || row.campaignStatus !== 'OPEN') return
  router.push({ path: '/internship/selection', query: { batchId: row.batchId, campaignId: row.campaignId, recordId: row.recordId } })
}
async function load() {
  const current = ++sequence
  result.value = null
  error.value = ''
  loading.value = false
  if (!groupId.value) { error.value = '消息缺少有效的原志愿编号，请从消息通知重新进入。'; return }
  const id = groupId.value
  loading.value = true
  try {
    const data = await internshipSelectionApi.volunteerResult(id)
    if (!alive || current !== sequence) return
    if (String(data?.id) !== id) throw new Error('返回结果与原志愿不一致，请刷新后重试。')
    result.value = { ...data, items: Array.isArray(data.items) ? data.items : [] }
  } catch (e) {
    if (alive && current === sequence) error.value = e?.message || '暂时无法读取原志愿，请稍后重试。'
  } finally {
    if (alive && current === sequence) loading.value = false
  }
}
watch(() => route.query.groupId, load, { immediate: true })
onBeforeUnmount(() => { alive = false; sequence++ })
</script>

<style scoped>
.result-page{display:grid;width:100%;box-sizing:border-box;max-width:1120px;margin:0 auto;padding:24px;gap:20px}.result-header,.result-heading,.result-tools{display:flex;align-items:center;justify-content:space-between;gap:16px}.result-tools{flex-wrap:wrap}.result-header h1{font-size:24px;margin:4px 0 0}.result-header p{margin:0}.result-summary,.result-choices{padding:24px}.result-summary{border-top:3px solid var(--pri)}.result-summary.is-approved{border-top-color:var(--success,var(--pri))}.result-summary h2{font-size:22px;margin:22px 0 8px}.result-guidance{color:var(--t2);line-height:1.8}.result-facts{display:flex;flex-wrap:wrap;gap:24px 48px;margin:24px 0 0;padding-top:20px;border-top:1px solid var(--line)}dt{color:var(--t4);font-size:12px}dd{margin:8px 0 0;color:var(--t1);font-size:14px}.revision{padding:16px 20px;background:var(--bg);border-radius:8px;margin-top:20px}.revision p,.choice-statement{white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.8}.revision p{margin:8px 0 0}.result-choices h2{font-size:17px;margin:0}.result-choice{display:flex;gap:16px;padding:24px 0;border-bottom:1px solid var(--line)}.result-choice:last-child{border-bottom:0;padding-bottom:0}.choice-order{display:grid;place-items:center;width:32px;height:32px;flex-shrink:0;background:var(--bg);border-radius:8px;color:var(--pri);font-weight:600}.choice-content{flex:1;min-width:0}.choice-content h3{font-size:16px;margin:0}.choice-content p{margin:8px 0 0}.choice-statement{font-size:14px;color:var(--t2)}.result-footnote{font-size:12px;margin:0}@media(max-width:700px){.result-header{align-items:flex-start;flex-direction:column}.result-heading{align-items:flex-start;flex-wrap:wrap}.result-summary,.result-choices{padding:18px}.result-facts{gap:20px}.result-header h1{font-size:22px}}
</style>
