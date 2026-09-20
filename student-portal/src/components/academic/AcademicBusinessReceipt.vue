<template>
  <section v-if="receipt" class="academic-receipt receipt" :class="{ waiting: tone !== 'success' }" role="status" aria-live="polite">
    <header><div class="bigmark"><AcademicPrototypeIcon :name="tone === 'success' ? 'circle-check' : 'circle-info'" /></div><div><h2>{{ receipt.title }}</h2><p>{{ receipt.object }}</p></div></header>
    <p>{{ receipt.next }}</p>
    <div class="facts"><div><span>业务对象</span><b>{{ receipt.object }}</b></div><div><span>实际状态</span><b>{{ receiptStatusLabel(receipt.status) }}</b></div><div><span>操作时间</span><b>{{ receipt.operatedAt }}</b></div><div><span>下一步</span><b>{{ receipt.next }}</b></div></div>
    <div class="row wrap"><slot /><RouterLink v-if="receipt.relatedTo" class="btn" :to="receipt.relatedTo">{{ receipt.relatedLabel || '查看相关页面' }}</RouterLink></div>
  </section>
</template>
<script setup>
import { RouterLink } from 'vue-router'
import AcademicPrototypeIcon from './AcademicPrototypeIcon.vue'
defineProps({ receipt: { type: Object, default: null }, tone: { type: String, default: 'success' } })
const RECEIPT_STATUS_LABELS = { SUCCESS: '办理成功', SUBMITTED: '已提交', PENDING: '处理中', PROCESSING: '处理中', APPROVED: '已通过', RETURNED: '已退回', REJECTED: '已驳回', COMPLETED: '已完成', CLOSED: '已关闭' }
function receiptStatusLabel(value) {
  if (!value) return '状态待确认'
  if (/[一-鿿]/.test(value)) return value
  return RECEIPT_STATUS_LABELS[value] || `状态待确认（${value}）`
}
</script>
<style scoped>
.academic-receipt { border:1px solid #b7d8c6; border-radius:12px; background:var(--surface,#fff); padding:26px; }
.academic-receipt > header { display:flex; gap:15px; align-items:center; margin-bottom:20px; }
.bigmark { width:52px;height:52px;border-radius:50%;display:grid;place-items:center;background:#eaf5ef;color:#247354;flex:none }
.bigmark :deep(.prototype-icon) {width:26px;height:26px}
.waiting {border-color:#e5d6b2}.waiting .bigmark{background:#fff5e2;color:#956119}
.academic-receipt p {color:var(--muted,#586d89);margin:0}
.facts {display:grid;grid-template-columns:1fr 1fr;gap:12px;padding:18px;background:var(--bg,#f4f7fc);border-radius:9px;margin:16px 0}
.facts span{display:block;font-size:12px;color:var(--muted,#586d89)}.facts b{display:block;font-size:14px;margin-top:3px;overflow-wrap:anywhere}
@media(max-width:560px){.facts{grid-template-columns:1fr}}
</style>
