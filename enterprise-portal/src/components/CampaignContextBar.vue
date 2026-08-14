<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
const props=defineProps({ campaign:{type:Object,default:null}, loading:Boolean })
const now=ref(Date.now())
let timer=null
onMounted(()=>{timer=setInterval(()=>{now.value=Date.now()},60_000)})
onUnmounted(()=>{if(timer)clearInterval(timer)})
const deadline=computed(()=>props.campaign?.currentDeadlineAt||props.campaign?.phaseDeadlineAt||props.campaign?.enterpriseDecisionDeadline||props.campaign?.enterpriseDecisionEndAt||'')
const campaignLabel=computed(()=>props.campaign?.name||props.campaign?.campaignName||(props.campaign?.id?`招聘季 #${props.campaign.id}`:'未选择招聘季'))
const phaseLabel=computed(()=>props.campaign?.phaseLabel||props.campaign?.status||'状态待服务端返回')
const remaining=computed(()=>{
  if(!deadline.value)return '—'
  const at=new Date(deadline.value).getTime()
  if(!Number.isFinite(at))return '—'
  const ms=at-now.value
  if(ms<=0)return '已截止'
  const minutes=Math.ceil(ms/60_000)
  if(minutes<60)return `${minutes} 分钟`
  const hours=Math.ceil(minutes/60)
  if(hours<24)return `${hours} 小时`
  const days=Math.floor(hours/24),rest=hours%24
  return rest ? `${days} 天 ${rest} 小时` : `${days} 天`
})
</script>
<template>
  <div class="bar ep-card">
    <div><span class="label">当前招聘季</span><strong>{{ loading ? '加载中…' : campaignLabel }}</strong></div>
    <div><span class="label">当前阶段</span><strong>{{ phaseLabel }}</strong></div>
    <div><span class="label">当前阶段截止</span><strong>{{ deadline || '—' }}</strong></div>
    <div><span class="label">距离截止</span><strong class="remaining">{{ remaining }}</strong></div>
  </div>
</template>
<style scoped>.bar{display:grid;grid-template-columns:2fr 1fr 1.4fr 1fr;gap:18px;padding:15px 18px;margin-bottom:18px}.bar>div{display:flex;flex-direction:column;gap:5px}.label{font-size:12px;color:var(--t3)}strong{font-size:14px}.remaining{color:var(--pri)}@media(max-width:900px){.bar{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:600px){.bar{grid-template-columns:1fr}}</style>
