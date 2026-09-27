<script setup>
import { computed,onMounted,ref } from 'vue'
import { enterpriseInternshipApi } from '../services/enterpriseInternshipApi'
import { useEnterpriseContextStore } from '../stores/enterpriseContext'
// Authority contract: this page is InternshipRecord-only; MENTOR scope is enforced by backend member/contact scope.
const context=useEnterpriseContextStore()
const loading=ref(true),error=ref(''),items=ref([]),keyword=ref(''),status=ref('ACTIVE'),page=ref(1),pageSize=50,total=ref(null),hasNext=ref(false)
const pageInfo=computed(()=>total.value===null?`第 ${page.value} 页`:`第 ${page.value} 页 · 共 ${total.value} 人`)
const collabReady=computed(()=>context.internshipCollabReady===true)
const batchId=computed(()=>Number(context.campaign?.batchId||0))
const visibleCount=computed(()=>items.value.length)
function evaluationLabel(value){return ({PENDING:'待评价',COMPLETED:'已完成'}[String(value||'').toUpperCase()]||value||'')}
async function load(){
  loading.value=true;error.value=''
  if(!collabReady.value){items.value=[];total.value=null;hasNext.value=false;error.value='学校尚未开放当前批次的实习协同访问';loading.value=false;return}
  try{
    const data=await enterpriseInternshipApi.internshipStudents({batchId:batchId.value,status:status.value,keyword:keyword.value,page:page.value,pageSize})
    items.value=Array.isArray(data)?data:(data?.items||[])
    total.value=Array.isArray(data)||data?.total===undefined||data?.total===null?null:Number(data.total)
    hasNext.value=Array.isArray(data)?false:(data?.hasNext===true||(Number.isFinite(total.value)&&page.value*pageSize<total.value))
  }catch(e){items.value=[];total.value=null;hasNext.value=false;error.value=e.message||'实习学生加载失败'}finally{loading.value=false}
}
function applySearch(){page.value=1;load()}
function changeStatus(){page.value=1;load()}
function previousPage(){if(page.value<=1)return;page.value-=1;load()}
function nextPage(){if(!hasNext.value)return;page.value+=1;load()}
onMounted(load)
</script>
<template>
  <section class="ep-page">
    <div class="ep-page-head"><div><h1 class="ep-title">实习学生</h1><p class="ep-subtitle">这里只展示学校已正式落岗的实习学生；企业管理员和 HR 查看本企业范围，企业导师仅查看学校授权的学生。</p></div><div class="head-summary"><strong>{{ total===null?visibleCount:total }}</strong><span>当前范围学生</span></div></div>
    <div class="workspace-toolbar ep-card"><div class="toolbar-copy"><span>正式实习协同</span><strong>按学生、岗位或导师快速定位</strong></div><div class="controls"><input v-model.trim="keyword" class="ep-input" placeholder="搜索学生/岗位/导师" @keyup.enter="applySearch"><select v-model="status" class="ep-select" @change="changeStatus"><option value="ACTIVE">在岗中</option><option value="COMPLETED">已结束</option><option value="ALL">全部正式实习</option></select><button class="ep-btn" :disabled="!collabReady" @click="applySearch">搜索</button></div></div>
    <div v-if="error" class="ep-error">{{ error }}</div><div v-if="loading" class="ep-card ep-empty">正在读取正式实习记录…</div><div v-else-if="!items.length" class="ep-card ep-empty">当前范围内暂无正式实习学生</div>
    <div v-else class="list"><article v-for="item in items" :key="item.internship_id||item.internshipId||item.id" class="ep-card student"><div class="identity"><div class="avatar">{{ String(item.name||'学').slice(0,1) }}</div><div class="identity-copy"><div class="name-line"><h3>{{ item.name }}</h3><span class="ep-tag ok">{{ item.status_label||item.statusLabel||item.status||'正式实习' }}</span></div><p>{{ item.position_name||item.positionName||'岗位' }}</p></div></div><div class="facts"><div><span>校内指导教师</span><strong>{{ item.advisor_name||item.advisorName||'—' }}</strong></div><div><span>企业导师</span><strong>{{ item.mentor_name||item.mentorName||'—' }}</strong></div><div class="period"><span>实习周期</span><strong>{{ item.period||`${item.start_date||item.startDate||'—'} ~ ${item.end_date||item.endDate||'—'}` }}</strong></div></div><div class="action"><span v-if="item.evaluation_status||item.evaluationStatus" class="evaluation-state">评价：{{ evaluationLabel(item.evaluation_status||item.evaluationStatus) }}</span><RouterLink v-if="item.evaluation_task_id||item.evaluationTaskId" to="/evaluations" class="ep-btn">进入评价任务</RouterLink></div></article><div class="pager ep-card"><span>{{ pageInfo }}</span><div><button class="ep-btn" :disabled="page<=1" @click="previousPage">上一页</button><button class="ep-btn" :disabled="!hasNext" @click="nextPage">下一页</button></div></div></div>
  </section>
</template>
<style scoped>
.head-summary{min-width:130px;padding:9px 13px;border:1px solid var(--line);border-radius:12px;background:#fff;box-shadow:var(--shadow-sm);display:flex;align-items:baseline;gap:7px}.head-summary strong{font-size:22px;color:var(--pri)}.head-summary span{font-size:10px;color:var(--t3)}
.workspace-toolbar{display:flex;align-items:center;justify-content:space-between;gap:18px;padding:13px 15px;margin-bottom:14px}.toolbar-copy{display:flex;flex-direction:column;gap:3px;min-width:190px}.toolbar-copy span{font-size:10px;color:var(--pri);font-weight:750;letter-spacing:.07em}.toolbar-copy strong{font-size:12px;color:#344158}.controls{display:flex;align-items:center;gap:9px}.controls .ep-input{width:250px}.controls .ep-select{min-width:130px}
.list{display:grid;gap:11px}.student{display:grid;grid-template-columns:minmax(250px,1.15fr) minmax(440px,2fr) auto;align-items:center;gap:22px;padding:17px 19px;transition:transform .16s ease,box-shadow .16s ease,border-color .16s ease}.student:hover{transform:translateY(-1px);border-color:#dfe7f2;box-shadow:var(--shadow-md)}.identity{display:flex;align-items:center;gap:12px;min-width:0}.avatar{width:44px;height:44px;border-radius:13px;display:grid;place-items:center;flex:0 0 44px;background:linear-gradient(145deg,var(--pri-50),#fff);border:1px solid var(--pri-100);color:var(--pri);font-weight:800}.identity-copy{min-width:0}.name-line{display:flex;align-items:center;gap:8px}.name-line h3{margin:0;font-size:16px}.identity-copy p{margin:5px 0 0;color:var(--t3);font-size:11px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.facts{display:grid;grid-template-columns:.85fr .85fr 1.3fr;gap:10px}.facts>div{padding:9px 11px;border-radius:9px;background:var(--surface-soft);min-width:0}.facts span{display:block;font-size:9px;color:var(--t3);margin-bottom:4px}.facts strong{display:block;font-size:11px;color:#334158;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.action{display:flex;flex-direction:column;align-items:flex-end;gap:7px}.action .ep-btn{text-decoration:none}.evaluation-state{font-size:9px;color:var(--t3)}.pager{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:11px 13px;font-size:11px;color:var(--t3)}.pager>div{display:flex;gap:8px}.pager .ep-btn{min-height:34px;padding:0 11px}
@media(max-width:1100px){.student{grid-template-columns:1fr}.facts{grid-template-columns:repeat(3,1fr)}.action{align-items:flex-start;flex-direction:row}.workspace-toolbar{align-items:flex-start;flex-direction:column}.controls{width:100%}.controls .ep-input{flex:1;width:auto}}
@media(max-width:650px){.head-summary{display:none}.controls{align-items:stretch;flex-direction:column}.controls .ep-input,.controls .ep-select,.controls .ep-btn{width:100%}.facts{grid-template-columns:1fr}.period{grid-column:auto}.pager{align-items:flex-start;flex-direction:column}}
</style>
