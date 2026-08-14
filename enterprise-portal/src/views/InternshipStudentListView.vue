<script setup>
import { computed,onMounted,ref } from 'vue'
import { enterpriseInternshipApi } from '../services/enterpriseInternshipApi'
const loading=ref(true),error=ref(''),items=ref([]),keyword=ref(''),status=ref('ACTIVE'),page=ref(1),pageSize=50,total=ref(null),hasNext=ref(false)
const pageInfo=computed(()=>total.value===null?`第 ${page.value} 页`:`第 ${page.value} 页 · 共 ${total.value} 人`)
async function load(){
  loading.value=true;error.value=''
  try{
    const data=await enterpriseInternshipApi.internshipStudents({status:status.value,keyword:keyword.value,page:page.value,pageSize})
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
<template><section class="ep-page"><div class="ep-page-head"><div><h1 class="ep-title">实习学生</h1><p class="ep-subtitle">这里只读取已经正式落岗的 InternshipRecord。HR 看公司范围；MENTOR 范围由后端 member/contact scope 裁剪。</p></div></div><div class="ep-toolbar"><input v-model.trim="keyword" class="ep-input" placeholder="搜索学生/岗位/导师" @keyup.enter="applySearch"><select v-model="status" class="ep-select" @change="changeStatus"><option value="ACTIVE">在岗中</option><option value="COMPLETED">已结束</option><option value="ALL">全部正式实习</option></select><button class="ep-btn" @click="applySearch">搜索</button></div><div v-if="error" class="ep-error">{{ error }}</div><div v-if="loading" class="ep-card ep-empty">正在读取正式实习记录…</div><div v-else-if="!items.length" class="ep-card ep-empty">当前范围内暂无正式实习学生</div><div v-else class="list"><article v-for="item in items" :key="item.internship_id||item.internshipId||item.id" class="ep-card student"><div class="main"><div class="avatar">{{ String(item.name||'学').slice(0,1) }}</div><div><h3>{{ item.name }}</h3><p>{{ item.position_name||item.positionName||'岗位' }} · {{ item.major||'—' }}</p></div></div><dl><div><dt>指导教师</dt><dd>{{ item.advisor_name||item.advisorName||'—' }}</dd></div><div><dt>企业导师</dt><dd>{{ item.mentor_name||item.mentorName||'—' }}</dd></div><div><dt>实习状态</dt><dd><span class="ep-tag ok">{{ item.status_label||item.statusLabel||item.status||'正式实习' }}</span></dd></div><div><dt>实习周期</dt><dd>{{ item.period||`${item.start_date||item.startDate||'—'} ~ ${item.end_date||item.endDate||'—'}` }}</dd></div></dl><RouterLink v-if="item.evaluation_task_id||item.evaluationTaskId" to="/evaluations" class="ep-btn eval">评价任务</RouterLink></article><div class="pager ep-card"><button class="ep-btn" :disabled="page<=1" @click="previousPage">上一页</button><span>{{ pageInfo }}</span><button class="ep-btn" :disabled="!hasNext" @click="nextPage">下一页</button></div></div></section></template>
<style scoped>.ep-toolbar{margin-bottom:14px}.list{display:grid;gap:12px}.student{display:grid;grid-template-columns:1.2fr 2.4fr auto;align-items:center;gap:22px;padding:18px 20px}.main{display:flex;align-items:center;gap:12px}.avatar{width:42px;height:42px;border-radius:50%;display:grid;place-items:center;background:var(--pri-50);color:var(--pri);font-weight:800}.main h3{margin:0 0 5px;font-size:16px}.main p{margin:0;color:var(--t3);font-size:12px}dl{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:0}dt{font-size:11px;color:var(--t3)}dd{margin:5px 0 0;font-size:13px}.eval{text-decoration:none}.pager{display:flex;align-items:center;justify-content:flex-end;gap:12px;padding:12px 16px;font-size:12px;color:var(--t3)}@media(max-width:1000px){.student{grid-template-columns:1fr}.student dl{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:600px){.ep-toolbar{align-items:stretch}.ep-toolbar .ep-input,.ep-toolbar .ep-select,.ep-toolbar .ep-btn{width:100%}.pager{justify-content:space-between}}</style>
