<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import CandidateCard from '../components/applicant/CandidateCard.vue'
import ApplicantDetailView from './ApplicantDetailView.vue'
import { enterpriseInternshipApi } from '../services/enterpriseInternshipApi'
import { useEnterpriseContextStore } from '../stores/enterpriseContext'
const route=useRoute(),router=useRouter(),context=useEnterpriseContextStore(),loading=ref(false),error=ref(''),items=ref([]),pipeline=ref('ALL')
const page=ref(1),pageSize=50,total=ref(0),initialized=ref(false)
const selectedId=computed(()=>route.params.id||'')
const selectedApplicant=computed(()=>items.value.find(item=>String(item.applicationId)===String(selectedId.value))||null)
const roleDenied=computed(()=>context.contextReady&&!context.applicationViewAllowed)
const tabs=[['ALL','全部'],['PENDING','待处理'],['INTERESTED','感兴趣'],['INTERVIEW','面试'],['ACCEPT_INTENT','拟接收'],['REJECTED','不合适']]
const hasNext=computed(()=>page.value*pageSize<total.value)
const pageInfo=computed(()=>`第 ${page.value} 页 · 共 ${total.value} 人`)
async function load(){
  if(!context.contextReady||!context.applicationViewAllowed){loading.value=false;return}
  loading.value=true;error.value=''
  try{
    const data=await enterpriseInternshipApi.applications({page:page.value,pageSize,decisionStatus:pipeline.value==='ALL'?'':pipeline.value})
    items.value=data.items||[];total.value=Number(data.total||0)
    if(!selectedId.value&&items.value.length&&window.innerWidth>=1000)router.replace(`/applications/${items.value[0].applicationId}`)
  }catch(e){items.value=[];total.value=0;error.value=e.message||'报名学生加载失败'}finally{loading.value=false}
}
async function initialize(){
  if(!context.contextReady||!context.applicationViewAllowed||initialized.value)return
  initialized.value=true
  await load()
}
function resetDeniedState(){items.value=[];total.value=0;loading.value=false;error.value=''}
function select(item){router.push(`/applications/${item.applicationId}`)}
function refresh(){load()}
function backToCandidates(){router.push('/applications')}
function previousPage(){if(page.value<=1)return;page.value-=1;load()}
function nextPage(){if(!hasNext.value)return;page.value+=1;load()}
watch(()=>[context.contextReady,context.memberRole],()=>{
  if(!context.contextReady||!context.applicationViewAllowed){initialized.value=false;resetDeniedState();return}
  initialize()
},{immediate:true})
watch(pipeline,()=>{page.value=1;load()})
</script>
<template><section class="ep-page wide"><div class="ep-page-head"><div><h1 class="ep-title">报名学生</h1><p class="ep-subtitle">只展示本企业岗位的正式报名学生；筛选与分页均由学校系统按当前招聘季和企业范围校验。</p></div></div><div v-if="roleDenied" class="role-denied ep-card"><span class="ep-tag">仅企业管理员 / HR</span><h2>当前成员角色不能处理报名学生</h2><p>企业导师可参与后续实习协同，但不能查看学生投递材料、候选人工作台或作出企业招聘处理决定。系统还会校验你的企业成员关系和招聘季授权范围。</p></div><template v-else><div v-if="context.historyMode" class="history-note">历史招聘季：申请材料与企业处理记录保留只读，新的候选人处理动作已关闭。</div><div class="pipeline"><button v-for="tab in tabs" :key="tab[0]" type="button" :class="{active:pipeline===tab[0]}" @click="pipeline=tab[0]">{{ tab[1] }}</button></div><div class="scope-note">当前只开放处理状态筛选；岗位、专业、年级等组合筛选将在学校端开放对应查询能力后提供。</div><div v-if="error" class="ep-error">{{ error }}</div><div class="workbench ep-card" :class="{showDetail:Boolean(selectedId)}"><aside class="candidates"><div v-if="loading" class="ep-empty">正在加载报名学生…</div><div v-else-if="!items.length" class="ep-empty">暂无报名学生</div><CandidateCard v-for="item in items" :key="item.applicationId" :applicant="item" :selected="String(selectedId)===String(item.applicationId)" @select="select" /><div v-if="!loading" class="pager"><button class="ep-btn" :disabled="page<=1" @click="previousPage">上一页</button><span>{{ pageInfo }}</span><button class="ep-btn" :disabled="!hasNext" @click="nextPage">下一页</button></div></aside><main class="detail-pane"><button v-if="selectedId" type="button" class="mobile-back" @click="backToCandidates">← 返回候选列表</button><ApplicantDetailView :application-id="selectedId" :summary="selectedApplicant" :campaign-writable="context.recruitmentWritable" @changed="refresh" /></main></div></template></section></template>
<style scoped>.wide{max-width:1400px}.role-denied{padding:30px;max-width:760px}.role-denied h2{margin:14px 0 8px;font-size:20px}.role-denied p{margin:0;color:var(--t3);line-height:1.7}.history-note{padding:12px 14px;margin-bottom:12px;background:var(--warn-bg);color:var(--warn-fg);border-radius:8px;font-size:13px}.pipeline{display:flex;gap:2px;border-bottom:1px solid var(--line);margin-bottom:10px;background:#fff;border-radius:10px 10px 0 0;overflow:auto}.pipeline button{border:0;background:transparent;min-height:46px;padding:0 14px;color:var(--t2);border-bottom:2px solid transparent;white-space:nowrap}.pipeline button.active{color:var(--pri);border-bottom-color:var(--pri);font-weight:700}.scope-note{margin:0 0 12px;color:var(--t3);font-size:12px}.workbench{display:grid;grid-template-columns:420px minmax(0,1fr);min-height:650px;overflow:hidden}.candidates{border-right:1px solid var(--line);max-height:calc(100vh - 245px);overflow:auto}.pager{position:sticky;bottom:0;display:flex;align-items:center;justify-content:space-between;gap:8px;padding:10px;border-top:1px solid var(--line);background:#fff;font-size:12px;color:var(--t3)}.pager .ep-btn{min-height:34px;padding:0 10px}.detail-pane{position:relative;min-width:0;min-height:650px;background:#fff}.mobile-back{display:none}@media(max-width:1279px) and (min-width:1000px){.workbench{grid-template-columns:360px minmax(0,1fr)}}@media(max-width:999px){.workbench{display:block}.candidates{max-height:none;border-right:0}.detail-pane{display:none}.workbench.showDetail .candidates{display:none}.workbench.showDetail .detail-pane{display:block}.mobile-back{display:block;width:100%;height:44px;border:0;border-bottom:1px solid var(--line);background:#fff;text-align:left;padding:0 16px;color:var(--pri);font-weight:600}}</style>
