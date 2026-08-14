<script setup>
import { computed,onMounted,reactive,ref,watch } from 'vue'
import { enterpriseInternshipApi } from '../services/enterpriseInternshipApi'

const SCORE_FIELDS=['attendanceScore','skillScore','attitudeScore','collaborationScore','safetyScore']
const loading=ref(true),submitting=ref(false),error=ref(''),items=ref([]),tab=ref('PENDING'),selected=ref(null)
const page=ref(1),pageSize=50,total=ref(null),hasNext=ref(false)
const form=reactive({attendanceScore:null,skillScore:null,attitudeScore:null,collaborationScore:null,safetyScore:null,overallComment:'',recommendHire:false})
const pageInfo=computed(()=>total.value===null?`第 ${page.value} 页`:`第 ${page.value} 页 · 共 ${total.value} 项`)

function resetForm(){Object.assign(form,{attendanceScore:null,skillScore:null,attitudeScore:null,collaborationScore:null,safetyScore:null,overallComment:'',recommendHire:false})}
function validate(){
  for(const field of SCORE_FIELDS){
    const value=Number(form[field])
    if(form[field]===null||form[field]===''||!Number.isFinite(value)||value<0||value>100)return '五项评分均需明确填写 0–100 分'
  }
  if(!String(form.overallComment||'').trim())return '请填写总体评价'
  if(String(form.overallComment).trim().length>2000)return '总体评价不能超过 2000 字'
  return ''
}
async function load(){
  loading.value=true;error.value=''
  try{
    const data=await enterpriseInternshipApi.evaluationTasks({status:tab.value==='ALL'?'':tab.value,page:page.value,pageSize})
    items.value=Array.isArray(data)?data:(data?.items||[])
    total.value=Array.isArray(data)||data?.total===undefined||data?.total===null?null:Number(data.total)
    hasNext.value=Array.isArray(data)?false:(data?.hasNext===true||(Number.isFinite(total.value)&&page.value*pageSize<total.value))
  }catch(e){items.value=[];total.value=null;hasNext.value=false;error.value=e.message||'评价任务加载失败'}finally{loading.value=false}
}
function start(item){selected.value=item;error.value='';resetForm()}
async function submit(){
  const problem=validate();if(problem){error.value=problem;return}
  const id=selected.value?.id||selected.value?.task_id||selected.value?.taskId
  if(!id){error.value='评价任务缺少 canonical id，无法提交';return}
  submitting.value=true;error.value=''
  try{
    await enterpriseInternshipApi.submitEvaluation(id,{
      attendanceScore:Number(form.attendanceScore),skillScore:Number(form.skillScore),attitudeScore:Number(form.attitudeScore),collaborationScore:Number(form.collaborationScore),safetyScore:Number(form.safetyScore),overallComment:String(form.overallComment).trim(),recommendHire:Boolean(form.recommendHire),
    })
    selected.value=null;resetForm();await load()
  }catch(e){error.value=e.message||'企业评价提交失败'}finally{submitting.value=false}
}
function previousPage(){if(page.value<=1)return;page.value-=1;load()}
function nextPage(){if(!hasNext.value)return;page.value+=1;load()}
watch(tab,()=>{page.value=1;load()});onMounted(load)
</script>
<template><section class="ep-page"><div class="ep-page-head"><div><h1 class="ep-title">评价任务</h1><p class="ep-subtitle">复用现有企业评价 canonical；企业 actor、member、source=ENTERPRISE_ONLINE、时间和审计由后端 facade 记录。</p></div></div><div class="tabs"><button v-for="item in [['PENDING','待评价'],['COMPLETED','已完成'],['ALL','全部']]" :key="item[0]" :class="{active:tab===item[0]}" @click="tab=item[0]">{{ item[1] }}</button></div><div v-if="error" class="ep-error">{{ error }}</div><div v-if="loading" class="ep-card ep-empty">正在加载评价任务…</div><div v-else-if="!items.length" class="ep-card ep-empty">当前没有评价任务</div><div v-else class="list"><article v-for="item in items" :key="item.id||item.task_id||item.taskId" class="ep-card task"><div><h3>{{ item.student_name||item.studentName||'学生' }} · {{ item.position_name||item.positionName||'实习岗位' }}</h3><p>企业导师：{{ item.mentor_name||item.mentorName||'—' }} · 截止 {{ item.deadline||'—' }}</p></div><div><span class="ep-tag" :class="{ok:(item.task_status||item.taskStatus||item.status)==='COMPLETED'}">{{ item.status_label||item.statusLabel||item.task_status||item.taskStatus||item.status||'状态未知' }}</span><button v-if="(item.task_status||item.taskStatus||item.status)!=='COMPLETED'" class="ep-btn ep-btn-primary" @click="start(item)">开始评价</button></div></article><div class="pager ep-card"><button class="ep-btn" :disabled="page<=1" @click="previousPage">上一页</button><span>{{ pageInfo }}</span><button class="ep-btn" :disabled="!hasNext" @click="nextPage">下一页</button></div></div><div v-if="selected" class="overlay" @click.self="selected=null"><form class="ep-card dialog" @submit.prevent="submit"><div class="dialog-head"><div><h2>企业在线评价</h2><p>{{ selected.student_name||selected.studentName }} · {{ selected.position_name||selected.positionName }}</p></div><button type="button" class="close" @click="selected=null">×</button></div><div class="scores"><label v-for="field in [['attendanceScore','出勤'],['skillScore','技能'],['attitudeScore','态度'],['collaborationScore','协作'],['safetyScore','安全纪律']]" :key="field[0]">{{ field[1] }}<input v-model.number="form[field[0]]" type="number" min="0" max="100" step="1" required class="ep-input" placeholder="0-100"></label></div><label>总体评价<textarea v-model.trim="form.overallComment" class="ep-textarea" rows="5" maxlength="2000" required /></label><label class="check"><input v-model="form.recommendHire" type="checkbox">建议后续录用 / 留用</label><p class="ep-muted">五项分数必须由评价人明确填写。前端不允许伪造 source、actor、member 或提交时间；这些字段全部由服务端写入并审计。</p><div class="dialog-actions"><button type="button" class="ep-btn" @click="selected=null">取消</button><button class="ep-btn ep-btn-primary" :disabled="submitting">{{ submitting?'提交中…':'提交企业评价' }}</button></div></form></div></section></template>
<style scoped>.tabs{display:flex;border-bottom:1px solid var(--line);margin-bottom:14px}.tabs button{min-height:42px;border:0;background:transparent;padding:0 14px;color:var(--t2);border-bottom:2px solid transparent}.tabs button.active{color:var(--pri);border-bottom-color:var(--pri);font-weight:700}.list{display:grid;gap:12px}.task{display:flex;justify-content:space-between;align-items:center;gap:18px;padding:18px 20px}.task h3{margin:0 0 6px;font-size:16px}.task p{margin:0;color:var(--t3);font-size:13px}.task>div:last-child{display:flex;align-items:center;gap:10px}.pager{display:flex;align-items:center;justify-content:flex-end;gap:12px;padding:12px 16px;font-size:12px;color:var(--t3)}.overlay{position:fixed;inset:0;z-index:50;background:rgba(20,28,45,.36);display:grid;place-items:center;padding:20px}.dialog{width:min(720px,100%);max-height:90vh;overflow:auto;padding:22px}.dialog-head{display:flex;justify-content:space-between;gap:20px}.dialog-head h2{margin:0 0 5px}.dialog-head p{margin:0;color:var(--t3)}.close{border:0;background:transparent;font-size:26px}.scores{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:8px;margin:20px 0}label{display:flex;flex-direction:column;gap:7px;font-size:13px;color:var(--t2);margin-bottom:14px}.check{flex-direction:row;align-items:center}.dialog-actions{display:flex;justify-content:flex-end;gap:8px}@media(max-width:700px){.task{align-items:flex-start;flex-direction:column}.scores{grid-template-columns:repeat(2,minmax(0,1fr))}.pager{justify-content:space-between}}</style>
