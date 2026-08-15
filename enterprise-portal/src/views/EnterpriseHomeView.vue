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
const metricItems=[['published','已发布岗位','招聘中'],['pending','待学校审核','需关注'],['applicants','报名学生','候选池'],['todoApplicants','待处理申请','今天优先'],['interview','面试中','推进中'],['acceptIntent','拟接收','待学校确认'],['interns','当前实习学生','在岗协同'],['evaluations','待评价','需完成']]
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
    <div class="hero-head"><div><span class="eyebrow">ENTERPRISE WORKSPACE</span><h1 class="ep-title">企业首页</h1><p class="ep-subtitle">先看当前招聘季、候选人推进和今天必须处理的事项，再进入具体工作区。</p></div><div class="hero-note"><span>当前企业</span><strong>{{ context.companyName || '企业协同账号' }}</strong><small>{{ context.memberRole || '企业成员' }}</small></div></div>
    <CampaignContextBar :campaign="context.campaign" :loading="context.loading" />
    <div v-if="context.historyMode" class="history-mode"><strong>当前招聘季已关闭</strong><span>岗位提交和候选人处理等招聘操作已关闭；岗位、申请和处理记录仍可作为历史查看。</span><span v-if="internshipCollabAllowed" class="collab-ok">学校已确认后续实习协同权限，正式实习学生和企业评价仍可继续处理。</span><span v-else class="collab-pending">后续实习协同权限需要学校确认；当前页面不会仅根据招聘季已结束就自动开放相关功能。</span></div>
    <div v-if="error" class="ep-error">{{ error }}。未取得真实数据时指标保持“—”。</div>
    <div class="section-head"><div><span>招聘总览</span><strong>当前招聘季关键数字</strong></div><small>所有指标以学校系统返回的实时 Authority 数据为准</small></div>
    <div class="metrics">
      <div v-for="item in metricItems" :key="item[0]" class="metric ep-card"><div class="metric-top"><span>{{ item[2] }}</span><i></i></div><strong>{{ metricValue(item[0]) }}</strong><span class="metric-label">{{ item[1] }}</span></div>
    </div>
    <div class="content-grid">
      <div class="tasks ep-card"><div class="card-head"><div><span>今日待办</span><h2 class="ep-section-title">今天要做什么</h2></div><span class="count-badge">{{ tasks.length }}</span></div><div v-if="!tasks.length" class="ep-empty compact">当前没有可确认的待处理任务。</div><div v-for="task in tasks" :key="task.key||task.title" class="task"><div><b>{{ task.title }}</b><p>{{ task.description }}</p></div><RouterLink v-if="task.href" :to="task.href" class="ep-btn">{{ task.actionLabel||'去处理' }}</RouterLink></div></div>
      <div class="history ep-card"><div class="card-head"><div><span>历史记录</span><h2 class="ep-section-title">历史招聘季</h2></div></div><div v-if="!history.length" class="ep-empty compact">暂无可确认的历史招聘季。</div><div v-for="item in history" :key="item.id||item.campaignId" class="history-row"><div><b>{{ item.name||item.campaignName||`招聘季 #${item.id||item.campaignId}` }}</b><span>{{ item.status }}</span></div><small>{{ item.period||`${item.startAt||'—'} ~ ${item.endAt||'—'}` }}</small></div></div>
    </div>
  </section>
</template>
<style scoped>
.hero-head{display:flex;align-items:flex-end;justify-content:space-between;gap:24px;margin-bottom:20px}.eyebrow{display:block;font-size:10px;letter-spacing:.16em;color:var(--pri);font-weight:800;margin-bottom:7px}.hero-note{min-width:210px;padding:12px 14px;border:1px solid var(--line);border-radius:12px;background:#fff;box-shadow:var(--shadow-sm);display:grid;grid-template-columns:auto 1fr;column-gap:10px;row-gap:2px}.hero-note>span,.hero-note small{font-size:10px;color:var(--t3)}.hero-note strong{font-size:12px;text-align:right;max-width:150px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.hero-note small{grid-column:1/-1;text-align:right}
.history-mode{display:flex;flex-direction:column;gap:5px;padding:13px 15px;margin-bottom:16px;border-radius:10px;background:var(--warn-bg);color:var(--warn-fg);border:1px solid rgba(154,91,0,.08)}.history-mode span{font-size:12px;line-height:1.6}.collab-ok{color:var(--ok-fg)}.collab-pending{color:var(--t2)}
.section-head{display:flex;align-items:flex-end;justify-content:space-between;gap:16px;margin:22px 0 11px}.section-head>div{display:flex;flex-direction:column;gap:2px}.section-head span{font-size:10px;letter-spacing:.08em;color:var(--t3);font-weight:700}.section-head strong{font-size:15px}.section-head small{font-size:10px;color:var(--t4)}
.metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin-bottom:18px}.metric{padding:16px 17px;min-height:118px;position:relative;overflow:hidden}.metric::after{content:"";position:absolute;right:-25px;bottom:-32px;width:88px;height:88px;border-radius:50%;background:var(--surface-blue)}.metric-top{display:flex;align-items:center;justify-content:space-between;position:relative;z-index:1}.metric-top>span{font-size:10px;color:var(--t3);font-weight:700}.metric-top i{width:7px;height:7px;border-radius:50%;background:var(--pri-200)}.metric strong{display:block;font-size:28px;line-height:1;margin:17px 0 7px;letter-spacing:-.03em;position:relative;z-index:1}.metric-label{color:var(--t2);font-size:12px;font-weight:600;position:relative;z-index:1}
.content-grid{display:grid;grid-template-columns:minmax(0,1.35fr) minmax(300px,.65fr);gap:14px}.tasks,.history{padding:19px 20px;margin-bottom:0}.card-head{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;margin-bottom:4px}.card-head>div>span{display:block;font-size:10px;color:var(--t3);font-weight:700;letter-spacing:.08em;margin-bottom:3px}.card-head .ep-section-title{margin-bottom:0}.count-badge{min-width:26px;height:26px;border-radius:999px;display:grid;place-items:center;background:var(--pri-50);color:var(--pri);font-size:11px;font-weight:800}.compact{padding:32px 10px}.task{display:flex;justify-content:space-between;gap:20px;align-items:center;padding:15px 0;border-top:1px solid var(--line)}.task:first-of-type{border-top:0}.task b{font-size:13px}.task p{margin:5px 0 0;color:var(--t3);font-size:12px;line-height:1.55}.task a{text-decoration:none;flex:0 0 auto}.history-row{padding:14px 0;border-top:1px solid var(--line)}.history-row:first-of-type{border-top:0}.history-row>div{display:flex;align-items:center;gap:8px}.history-row b{font-size:12px;color:var(--t1);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.history-row span{font-size:9px;background:var(--pri-50);color:var(--pri);padding:2px 6px;border-radius:999px}.history-row small{display:block;margin-top:5px;font-size:10px;color:var(--t3)}
@media(max-width:1050px){.metrics{grid-template-columns:repeat(2,minmax(0,1fr))}.content-grid{grid-template-columns:1fr}.hero-note{display:none}}
@media(max-width:640px){.hero-head{margin-bottom:16px}.metrics{gap:9px}.metric{min-height:104px;padding:14px}.metric strong{font-size:24px}.section-head small{display:none}}
</style>
