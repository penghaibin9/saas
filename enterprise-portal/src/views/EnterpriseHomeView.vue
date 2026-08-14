<script setup>
import { computed, onMounted, ref } from 'vue'
import CampaignContextBar from '../components/CampaignContextBar.vue'
import { enterpriseInternshipApi } from '../services/enterpriseInternshipApi'
import { useEnterpriseContextStore } from '../stores/enterpriseContext'

const context=useEnterpriseContextStore(); const data=ref(null); const campaigns=ref([]); const loading=ref(true); const error=ref('')
const metrics=computed(()=>data.value?.metrics||null)
const tasks=computed(()=>Array.isArray(data.value?.tasks)?data.value.tasks:[])
const history=computed(()=>campaigns.value.filter(item=>['CLOSED','ARCHIVED'].includes(String(item.status||''))))
const internshipCollabAllowed=computed(()=>context.capabilities?.internshipCollab===true)
function metricValue(key){
  if(loading.value||!metrics.value)return '—'
  return Object.prototype.hasOwnProperty.call(metrics.value,key) ? metrics.value[key] : '—'
}
onMounted(async()=>{
  try{
    const [dashboardResult,campaignResult]=await Promise.allSettled([enterpriseInternshipApi.dashboard(),enterpriseInternshipApi.campaigns()])
    if(dashboardResult.status==='fulfilled')data.value=dashboardResult.value
    else error.value=dashboardResult.reason?.message||'招聘工作台数据暂不可用'
    if(campaignResult.status==='fulfilled')campaigns.value=Array.isArray(campaignResult.value)?campaignResult.value:(campaignResult.value?.items||[])
  }finally{loading.value=false}
})
</script>
<template>
  <section class="ep-page">
    <div class="ep-page-head"><div><h1 class="ep-title">企业首页</h1><p class="ep-subtitle">先看当前招聘季和今天必须处理的事项。</p></div></div>
    <CampaignContextBar :campaign="context.campaign" :loading="context.loading" />
    <div v-if="context.historyMode" class="history-mode"><strong>当前招聘季已关闭</strong><span>岗位提交、候选人 Decision 等 RECRUITMENT 写操作已关闭；岗位、申请和处理记录仅保留历史查看。</span><span v-if="internshipCollabAllowed" class="collab-ok">服务端已确认有效 INTERNSHIP_COLLAB Grant：正式 InternshipRecord 与企业评价协同仍可继续。</span><span v-else class="collab-pending">正式实习协同权限必须由服务端显式确认有效 INTERNSHIP_COLLAB Grant；当前客户端不会根据历史招聘季状态自行推断权限。</span></div>
    <div v-if="error" class="ep-error">{{ error }}。未取得真实数据时指标保持“—”，不会用 0 冒充真实统计。</div>
    <div class="metrics">
      <div v-for="item in [['published','已发布岗位'],['pending','待学校审核'],['applicants','报名学生'],['todoApplicants','待处理申请'],['interview','面试中'],['acceptIntent','拟接收'],['interns','当前实习学生'],['evaluations','待评价']]" :key="item[0]" class="metric ep-card"><strong>{{ metricValue(item[0]) }}</strong><span>{{ item[1] }}</span></div>
    </div>
    <div class="tasks ep-card"><h2 class="ep-section-title">今天要做什么</h2><div v-if="!tasks.length" class="ep-empty">当前没有可确认的待处理任务；后端未返回任务真值时这里不会生成 mock 待办。</div><div v-for="task in tasks" :key="task.key||task.title" class="task"><div><b>{{ task.title }}</b><p>{{ task.description }}</p></div><RouterLink v-if="task.href" :to="task.href" class="ep-btn">{{ task.actionLabel||'去处理' }}</RouterLink></div></div>
    <div class="history ep-card"><h2 class="ep-section-title">历史招聘季</h2><div v-if="!history.length" class="ep-muted">暂无可确认的历史招聘季；企业招聘季列表未返回前不构造历史记录。</div><div v-for="item in history" :key="item.id||item.campaignId" class="history-row"><div><b>{{ item.name||item.campaignName||`招聘季 #${item.id||item.campaignId}` }}</b><span>{{ item.status }}</span></div><div>{{ item.period||`${item.startAt||'—'} ~ ${item.endAt||'—'}` }}</div></div></div>
  </section>
</template>
<style scoped>.history-mode{display:flex;flex-direction:column;gap:5px;padding:13px 15px;margin-bottom:16px;border-radius:8px;background:var(--warn-bg);color:var(--warn-fg)}.history-mode span{font-size:12px;line-height:1.6}.collab-ok{color:var(--ok-fg)}.collab-pending{color:var(--t2)}.metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin-bottom:18px}.metric{padding:18px}.metric strong{display:block;font-size:26px;margin-bottom:7px}.metric span{color:var(--t3);font-size:13px}.tasks,.history{padding:20px;margin-bottom:18px}.task{display:flex;justify-content:space-between;gap:20px;align-items:center;padding:14px 0;border-top:1px solid var(--line)}.task:first-of-type{border-top:0}.task p{margin:5px 0 0;color:var(--t3);font-size:13px}.task a{text-decoration:none}.history-row{display:flex;justify-content:space-between;gap:16px;padding:12px 0;border-top:1px solid var(--line);font-size:13px;color:var(--t3)}.history-row b{color:var(--t1);margin-right:8px}.history-row span{font-size:11px;background:var(--pri-50);color:var(--pri);padding:2px 6px;border-radius:4px}@media(max-width:900px){.metrics{grid-template-columns:repeat(2,minmax(0,1fr))}}</style>
