<script setup>
import { computed,onMounted,reactive,ref,watch } from 'vue'
import { enterpriseInternshipApi } from '../services/enterpriseInternshipApi'
import { useEnterpriseContextStore } from '../stores/enterpriseContext'

// Authority contract: canonical source=ENTERPRISE_ONLINE; actor/member/time 由服务端写入并审计，客户端 payload 不得伪造。
const context=useEnterpriseContextStore()
const SCORE_FIELDS=['attendanceScore','skillScore','attitudeScore','collaborationScore','safetyScore']
const loading=ref(true),submitting=ref(false),error=ref(''),items=ref([]),tab=ref('PENDING'),selected=ref(null)
const page=ref(1),pageSize=50,total=ref(null),hasNext=ref(false)
const form=reactive({attendanceScore:null,skillScore:null,attitudeScore:null,collaborationScore:null,safetyScore:null,overallComment:'',recommendHire:false})
const pageInfo=computed(()=>total.value===null?`第 ${page.value} 页`:`第 ${page.value} 页 · 共 ${total.value} 项`)
const collabReady=computed(()=>context.internshipCollabReady===true)
const batchId=computed(()=>Number(context.campaign?.batchId||0))
const taskCount=computed(()=>total.value===null?items.value.length:total.value)

function resetForm(){Object.assign(form,{attendanceScore:null,skillScore:null,attitudeScore:null,collaborationScore:null,safetyScore:null,overallComment:'',recommendHire:false})}
function validate(){
  for(const field of SCORE_FIELDS){
    const value=Number(form[field])
    if(form[field]===null||form[field]===''||!Number.isFinite(value)||!Number.isInteger(value)||value<0||value>100)return '五项评分均需明确填写 0–100 的整数分'
  }
  if(!String(form.overallComment||'').trim())return '请填写总体评价'
  if(String(form.overallComment).trim().length>2000)return '总体评价不能超过 2000 字'
  return ''
}
async function load(){
  loading.value=true;error.value=''
  if(!collabReady.value){items.value=[];total.value=null;hasNext.value=false;error.value='学校尚未开放当前批次的实习评价协同';loading.value=false;return}
  try{
    const data=await enterpriseInternshipApi.evaluationTasks({batchId:batchId.value,status:tab.value==='ALL'?'':tab.value,page:page.value,pageSize})
    items.value=Array.isArray(data)?data:(data?.items||[])
    total.value=Array.isArray(data)||data?.total===undefined||data?.total===null?null:Number(data.total)
    hasNext.value=Array.isArray(data)?false:(data?.hasNext===true||(Number.isFinite(total.value)&&page.value*pageSize<total.value))
  }catch(e){items.value=[];total.value=null;hasNext.value=false;error.value=e.message||'评价任务加载失败'}finally{loading.value=false}
}
function start(item){
  selected.value=item;error.value='';resetForm()
  if(item?.schoolReviewStatus==='RETURNED'){
    for(const field of SCORE_FIELDS)if(item[field]!==undefined&&item[field]!==null)form[field]=Number(item[field])
    form.overallComment=item.overallComment||''
    form.recommendHire=Boolean(item.recommendHire)
  }
}
async function submit(){
  const problem=validate();if(problem){error.value=problem;return}
  const id=selected.value?.internshipId||selected.value?.id||selected.value?.task_id||selected.value?.taskId
  if(!id){error.value='评价任务信息不完整，暂时无法提交';return}
  submitting.value=true;error.value=''
  try{
    const payload={attendanceScore:Number(form.attendanceScore),skillScore:Number(form.skillScore),attitudeScore:Number(form.attitudeScore),collaborationScore:Number(form.collaborationScore),safetyScore:Number(form.safetyScore),overallComment:String(form.overallComment).trim(),recommendHire:Boolean(form.recommendHire)}
    if(selected.value?.evaluationVersion!==null&&selected.value?.evaluationVersion!==undefined)payload.expectedVersion=selected.value.evaluationVersion
    await enterpriseInternshipApi.submitEvaluation(id,payload,batchId.value)
    selected.value=null;resetForm();await load()
  }catch(e){error.value=e.message||'企业评价提交失败'}finally{submitting.value=false}
}
function previousPage(){if(page.value<=1)return;page.value-=1;load()}
function nextPage(){if(!hasNext.value)return;page.value+=1;load()}
watch(tab,()=>{page.value=1;load()});onMounted(load)
</script>
<template>
  <section class="ep-page">
    <div class="ep-page-head"><div><h1 class="ep-title">评价任务</h1><p class="ep-subtitle">按学校统一规则完成企业评价。企业填写评分与意见，评价人身份、提交来源、提交时间和审计记录由系统自动记录。</p></div><div class="head-summary"><strong>{{ taskCount }}</strong><span>当前筛选任务</span></div></div>
    <div class="filter-card ep-card"><div class="filter-copy"><span>企业评价工作台</span><strong>先完成待评价，再核对已提交记录</strong></div><div class="tabs"><button v-for="item in [['PENDING','待评价'],['COMPLETED','已完成'],['ALL','全部']]" :key="item[0]" :class="{active:tab===item[0]}" @click="tab=item[0]">{{ item[1] }}</button></div></div>
    <div v-if="error" class="ep-error">{{ error }}</div><div v-if="loading" class="ep-card ep-empty">正在加载评价任务…</div><div v-else-if="!items.length" class="ep-card ep-empty">当前没有评价任务</div>
    <div v-else class="list"><article v-for="item in items" :key="item.id||item.task_id||item.taskId" class="ep-card task"><div class="task-main"><div class="avatar">{{ String(item.student_name||item.studentName||'学').slice(0,1) }}</div><div class="task-copy"><div class="name-line"><h3>{{ item.student_name||item.studentName||'学生' }} · {{ item.position_name||item.positionName||'实习岗位' }}</h3><span class="ep-tag" :class="{ok:(item.task_status||item.taskStatus||item.status)==='COMPLETED',warn:item.schoolReviewStatus==='RETURNED'}">{{ item.status_label||item.statusLabel||item.task_status||item.taskStatus||item.status||'状态未知' }}</span></div><p>企业导师：{{ item.mentor_name||item.mentorName||'—' }}</p><p v-if="item.returnReason" class="return-reason">学校退回：{{ item.returnReason }}</p></div></div><div class="deadline"><span>评价截止</span><strong>{{ item.deadline||'—' }}</strong></div><div class="task-action"><span v-if="(item.task_status||item.taskStatus||item.status)==='COMPLETED'" class="completed-note">已完成并留痕</span><button v-else class="ep-btn ep-btn-primary" :disabled="!collabReady" @click="start(item)">{{ item.schoolReviewStatus==='RETURNED'?'修改后重交':'开始评价' }}</button></div></article><div class="pager ep-card"><span>{{ pageInfo }}</span><div><button class="ep-btn" :disabled="page<=1" @click="previousPage">上一页</button><button class="ep-btn" :disabled="!hasNext" @click="nextPage">下一页</button></div></div></div>
    <div v-if="selected" class="overlay" @click.self="selected=null"><form class="ep-card dialog" @submit.prevent="submit"><div class="dialog-head"><div><span>企业在线评价</span><h2>{{ selected.student_name||selected.studentName }} · {{ selected.position_name||selected.positionName }}</h2><p>五项评分均需明确填写 0–100 的整数分。</p></div><button type="button" class="close" aria-label="关闭评价弹窗" @click="selected=null">×</button></div><div class="scores"><label v-for="field in [['attendanceScore','出勤'],['skillScore','技能'],['attitudeScore','态度'],['collaborationScore','协作'],['safetyScore','安全纪律']]" :key="field[0]"><span>{{ field[1] }}</span><input v-model.number="form[field[0]]" type="number" min="0" max="100" step="1" required class="ep-input" placeholder="0-100"></label></div><label class="comment-label"><span>总体评价</span><textarea v-model.trim="form.overallComment" class="ep-textarea" rows="5" maxlength="2000" required placeholder="请结合学生出勤、技能、态度、协作和安全表现填写评价" /></label><label class="check"><input v-model="form.recommendHire" type="checkbox">建议后续录用 / 留用</label><div class="audit-note"><strong>系统自动留痕</strong><span>评价人、企业成员身份、提交来源和提交时间由系统记录，企业无需填写。</span></div><div class="dialog-actions"><button type="button" class="ep-btn" @click="selected=null">取消</button><button class="ep-btn ep-btn-primary" :disabled="submitting||!collabReady">{{ submitting?'提交中…':'提交企业评价' }}</button></div></form></div>
  </section>
</template>
<style scoped>
.head-summary{min-width:130px;padding:9px 13px;border:1px solid var(--line);border-radius:12px;background:#fff;box-shadow:var(--shadow-sm);display:flex;align-items:baseline;gap:7px}.head-summary strong{font-size:22px;color:var(--pri)}.head-summary span{font-size:10px;color:var(--t3)}
.filter-card{display:flex;align-items:center;justify-content:space-between;gap:18px;padding:11px 14px;margin-bottom:14px}.filter-copy{display:flex;flex-direction:column;gap:3px}.filter-copy span{font-size:10px;color:var(--pri);font-weight:750;letter-spacing:.07em}.filter-copy strong{font-size:12px;color:#344158}.tabs{display:flex;gap:3px}.tabs button{min-height:38px;border:0;background:transparent;padding:0 13px;color:var(--t2);border-radius:8px;font-weight:600}.tabs button:hover{color:var(--pri);background:var(--surface-soft)}.tabs button.active{color:var(--pri);background:var(--pri-50);font-weight:750}
.list{display:grid;gap:11px}.task{display:grid;grid-template-columns:minmax(0,1fr) 150px auto;align-items:center;gap:20px;padding:17px 19px;transition:transform .16s ease,box-shadow .16s ease,border-color .16s ease}.task:hover{transform:translateY(-1px);border-color:#dfe7f2;box-shadow:var(--shadow-md)}.task-main{display:flex;align-items:center;gap:12px;min-width:0}.avatar{width:42px;height:42px;border-radius:13px;display:grid;place-items:center;flex:0 0 42px;background:linear-gradient(145deg,var(--pri-50),#fff);border:1px solid var(--pri-100);color:var(--pri);font-weight:800}.task-copy{min-width:0}.name-line{display:flex;align-items:center;gap:8px;min-width:0}.task h3{margin:0;font-size:15px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.task p{margin:5px 0 0;color:var(--t3);font-size:11px}.task .return-reason{color:var(--warn-fg)}.deadline{padding:9px 11px;border-radius:9px;background:var(--surface-soft)}.deadline span{display:block;font-size:9px;color:var(--t3);margin-bottom:4px}.deadline strong{font-size:11px;color:#334158}.task-action{display:flex;justify-content:flex-end}.completed-note{font-size:10px;color:var(--ok-fg);font-weight:700}.pager{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:11px 13px;font-size:11px;color:var(--t3)}.pager>div{display:flex;gap:8px}.pager .ep-btn{min-height:34px;padding:0 11px}
.overlay{position:fixed;inset:0;z-index:50;background:rgba(20,28,45,.42);backdrop-filter:blur(3px);display:grid;place-items:center;padding:20px}.dialog{width:min(760px,100%);max-height:90vh;overflow:auto;padding:22px;box-shadow:0 24px 70px rgba(20,28,45,.22)}.dialog-head{display:flex;justify-content:space-between;gap:20px;padding-bottom:15px;border-bottom:1px solid var(--line)}.dialog-head>div>span{font-size:10px;color:var(--pri);font-weight:750;letter-spacing:.07em}.dialog-head h2{margin:4px 0 5px;font-size:19px}.dialog-head p{margin:0;color:var(--t3);font-size:11px}.close{border:0;background:transparent;font-size:26px;color:var(--t3)}.scores{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:8px;margin:20px 0}.scores label,.comment-label{display:flex;flex-direction:column;gap:7px;font-size:11px;color:var(--t2)}.scores label span{font-weight:650}.check{display:flex;align-items:center;gap:8px;font-size:12px;color:var(--t2);margin-top:14px}.audit-note{display:flex;align-items:center;gap:10px;margin-top:16px;padding:11px 12px;border-radius:9px;background:var(--surface-blue);border:1px solid var(--pri-100)}.audit-note strong{font-size:10px;color:var(--pri)}.audit-note span{font-size:10px;color:var(--t3)}.dialog-actions{display:flex;justify-content:flex-end;gap:8px;margin-top:18px;padding-top:15px;border-top:1px solid var(--line)}
@media(max-width:800px){.task{grid-template-columns:1fr}.deadline{width:max-content}.task-action{justify-content:flex-start}.filter-card{align-items:flex-start;flex-direction:column}.scores{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:620px){.head-summary{display:none}.tabs{width:100%;overflow:auto}.pager{align-items:flex-start;flex-direction:column}.audit-note{align-items:flex-start;flex-direction:column}}
</style>
