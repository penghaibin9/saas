<script setup>
import { computed } from 'vue'
const props=defineProps({ applicant:{type:Object,required:true}, selected:Boolean })
const emit=defineEmits(['select'])
const statusLabel=computed(()=>({PENDING:'待处理',INTERESTED:'感兴趣',INTERVIEW:'面试',ACCEPT_INTENT:'拟接收',REJECTED:'不合适'}[props.applicant.decisionStatus]||'待处理'))
</script>
<template><button type="button" class="candidate" :class="{selected}" @click="emit('select',applicant)"><div class="top"><strong>{{ applicant.name || '学生' }}</strong><span>第{{ applicant.volunteerNo ?? '—' }}志愿</span></div><div class="school">{{ applicant.major || '专业待加载' }} · {{ applicant.grade || '年级待加载' }}</div><div class="position">{{ applicant.positionName || '申请岗位' }}</div><div class="meta"><span class="decision">{{ statusLabel }}</span><span>{{ applicant.appliedAt || '申请时间待加载' }}</span></div></button></template>
<style scoped>.candidate{width:100%;text-align:left;border:0;border-bottom:1px solid var(--line);background:#fff;padding:16px 17px;color:var(--t1)}.candidate:hover,.candidate.selected{background:#f7f9ff}.candidate.selected{box-shadow:inset 3px 0 var(--pri)}.top{display:flex;justify-content:space-between;gap:12px;align-items:center}.top strong{font-size:16px}.top span{font-size:12px;color:var(--pri)}.school{font-size:13px;color:var(--t2);margin-top:6px}.position{font-size:13px;font-weight:600;margin-top:8px}.meta{display:flex;justify-content:space-between;gap:12px;color:var(--t3);font-size:12px;margin-top:8px}.decision{color:var(--pri);font-weight:600}</style>
