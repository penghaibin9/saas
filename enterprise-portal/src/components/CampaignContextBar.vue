<script setup>
defineProps({ campaign:{type:Object,default:null}, loading:Boolean })
</script>
<template>
  <div class="bar ep-card">
    <div><span class="label">当前招聘季</span><strong>{{ loading ? '加载中…' : (campaign?.name || '未开放招聘季') }}</strong></div>
    <div><span class="label">当前阶段</span><strong>{{ campaign?.phaseLabel || campaign?.phase_label || campaign?.status || '—' }}</strong></div>
    <div><span class="label">企业处理截止</span><strong>{{ campaign?.enterpriseDecisionDeadline || campaign?.enterprise_decision_deadline || '—' }}</strong></div>
  </div>
</template>
<style scoped>.bar{display:grid;grid-template-columns:2fr 1fr 1.3fr;gap:18px;padding:15px 18px;margin-bottom:18px}.bar>div{display:flex;flex-direction:column;gap:5px}.label{font-size:12px;color:var(--t3)}strong{font-size:14px}@media(max-width:800px){.bar{grid-template-columns:1fr}}</style>
