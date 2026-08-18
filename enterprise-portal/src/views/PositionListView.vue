<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { enterpriseInternshipApi } from '../services/enterpriseInternshipApi'
import { useEnterpriseContextStore } from '../stores/enterpriseContext'
const router=useRouter(),context=useEnterpriseContextStore(),loading=ref(true),error=ref(''),items=ref([]),active=ref('ALL'),keyword=ref(''),workingId=ref(null),page=ref(1),pageSize=20,total=ref(0)
const tabs=[['ALL','全部'],['DRAFT','草稿'],['PENDING','待学校审核'],['PUBLISHED','已发布'],['OFFLINE','已下线'],['RISK','风险']]
const statusLabels={DRAFT:'草稿',PENDING:'待学校审核',PUBLISHED:'已发布',OFFLINE:'已下线',SUSPENDED:'已暂停',FULL:'已招满',RISK:'风险',ARCHIVED:'已归档'}
let searchTimer=null,requestSeq=0
const totalPages=()=>Math.max(1,Math.ceil(total.value/pageSize))
function statusText(item){return item.riskFlag?'风险':(statusLabels[item.status]||item.status||'状态未知')}
function countText(value){return value===undefined||value===null?'—':value}
async function load(){
  const seq=++requestSeq;loading.value=true;error.value=''
  try{
    const data=await enterpriseInternshipApi.positions({page:page.value,pageSize,status:active.value==='ALL'?'':active.value,keyword:keyword.value.trim()})
    if(seq!==requestSeq)return
    items.value=Array.isArray(data?.items)?data.items:[];total.value=Number(data?.total||0)
    if(page.value>totalPages()){page.value=totalPages();return load()}
  }catch(e){if(seq===requestSeq){items.value=[];total.value=0;error.value=e.message||'岗位加载失败'}}finally{if(seq===requestSeq)loading.value=false}
}
function scheduleSearch(){clearTimeout(searchTimer);searchTimer=setTimeout(()=>{page.value=1;load()},300)}
async function withdrawAndEdit(item){if(!context.recruitmentWritable||item.status!=='PENDING'||item.version===null||item.version===undefined)return;workingId.value=item.id;error.value='';try{await enterpriseInternshipApi.withdrawPosition(item.id,item.version);await router.push(`/positions/${item.id}/edit`)}catch(e){error.value=e.message||'撤回岗位失败'}finally{workingId.value=null}}
function previous(){if(page.value>1){page.value-=1;load()}}
function next(){if(page.value<totalPages()){page.value+=1;load()}}
watch(active,()=>{page.value=1;load()})
watch(keyword,scheduleSearch)
onMounted(load)
onBeforeUnmount(()=>clearTimeout(searchTimer))
</script>
<template>
  <section class="ep-page">
    <div class="ep-page-head"><div><h1 class="ep-title">我的岗位</h1><p class="ep-subtitle">集中管理企业在当前招聘季的岗位草稿、学校审核、发布和下线状态；企业只处理自身岗位，发布状态由学校端统一管理。</p></div><RouterLink v-if="context.recruitmentWritable" to="/positions/new" class="ep-btn ep-btn-primary">+ 创建实习岗位</RouterLink></div>
    <div v-if="context.historyMode" class="history-note">招聘季已关闭：岗位记录保留为历史只读，不再允许创建、编辑、提交或撤回。</div>
    <div class="toolbar-card ep-card"><div class="search-wrap"><span>搜索</span><input v-model="keyword" class="ep-input" placeholder="输入岗位名称或关键词"></div><div class="tabs" role="tablist"><button v-for="tab in tabs" :key="tab[0]" class="tab" :class="{active:active===tab[0]}" @click="active=tab[0]">{{ tab[1] }}</button></div><div class="total-chip"><strong>{{ total }}</strong><span>岗位</span></div></div>
    <div v-if="error" class="ep-error">{{ error }}</div>
    <div v-if="loading" class="ep-card ep-empty">正在加载岗位…</div><div v-else-if="!items.length" class="ep-card ep-empty">暂无符合条件的岗位</div>
    <div v-else class="list"><article v-for="item in items" :key="item.id" class="position ep-card"><div class="row"><div class="position-main"><div class="title-line"><h3>{{ item.title }}</h3><span class="ep-tag" :class="{warn:item.status==='PENDING',ok:item.status==='PUBLISHED',danger:item.riskFlag}">{{ statusText(item) }}</span></div><p>{{ item.workLocation||'工作地点待完善' }} · 招 {{ item.headcount??'—' }} 人 · {{ item.majorRequirement||'专业不限/以学校核验为准' }}</p></div><div class="salary"><span>岗位待遇</span><div class="ep-money">{{ item.salaryRange||'待完善' }}</div></div></div><div class="meta"><div class="metric"><strong>{{ countText(item.applicantCount) }}</strong><span>报名</span></div><div class="metric"><strong>{{ countText(item.acceptIntentCount) }}</strong><span>拟接收</span></div><div class="metric"><strong>{{ countText(item.placementCount) }}</strong><span>已落实</span></div><div class="manage-wrap"><template v-if="context.recruitmentWritable"><RouterLink v-if="item.status==='DRAFT'" :to="`/positions/${item.id}/edit`" class="manage">编辑草稿 →</RouterLink><button v-else-if="item.status==='PENDING'" class="manage action-link" type="button" :disabled="workingId===item.id" @click="withdrawAndEdit(item)">{{ workingId===item.id?'撤回中…':'撤回修改 →' }}</button><RouterLink v-else :to="`/positions/${item.id}/edit`" class="manage">查看岗位 →</RouterLink></template><span v-else class="manage muted">历史只读</span></div></div></article></div>
    <div class="pager"><span>共 {{ total }} 个岗位 · 第 {{ page }}/{{ totalPages() }} 页</span><div><button class="ep-btn" :disabled="page<=1||loading" @click="previous">上一页</button><button class="ep-btn" :disabled="page>=totalPages()||loading" @click="next">下一页</button></div></div>
  </section>
</template>
<style scoped>
.history-note{padding:12px 14px;margin-bottom:14px;background:var(--warn-bg);color:var(--warn-fg);border-radius:10px;font-size:13px;border:1px solid rgba(154,91,0,.08)}
.toolbar-card{display:flex;align-items:flex-end;gap:16px;padding:14px 15px;margin-bottom:16px}.search-wrap{display:flex;flex-direction:column;gap:6px;min-width:240px}.search-wrap>span{font-size:10px;color:var(--t3);font-weight:700;letter-spacing:.06em}.search-wrap .ep-input{height:40px}.tabs{display:flex;align-items:center;gap:3px;overflow:auto;flex:1}.tab{min-height:38px;border:0;background:transparent;color:var(--t2);padding:0 11px;border-radius:8px;white-space:nowrap;font-weight:600}.tab:hover{background:var(--surface-soft);color:var(--pri)}.tab.active{color:var(--pri);background:var(--pri-50);font-weight:750}.total-chip{min-width:64px;display:flex;align-items:baseline;justify-content:center;gap:4px;padding:7px 10px;border-left:1px solid var(--line)}.total-chip strong{font-size:18px;color:var(--pri)}.total-chip span{font-size:10px;color:var(--t3)}
.list{display:grid;gap:12px}.position{padding:18px 20px;transition:transform .16s ease,box-shadow .16s ease,border-color .16s ease}.position:hover{transform:translateY(-1px);border-color:#dfe7f2;box-shadow:var(--shadow-md)}.row{display:flex;justify-content:space-between;gap:24px}.position-main{min-width:0}.title-line{display:flex;align-items:center;gap:10px}.title-line h3{margin:0;font-size:17px;line-height:1.35}.row p{margin:8px 0 0;color:var(--t3);font-size:12px;line-height:1.6}.salary{text-align:right;flex:0 0 auto}.salary>span{display:block;font-size:10px;color:var(--t3);margin-bottom:4px}.salary .ep-money{font-size:15px}.meta{display:grid;grid-template-columns:80px 80px 80px minmax(0,1fr);align-items:center;gap:8px;margin-top:17px;padding-top:14px;border-top:1px solid var(--line)}.metric{display:flex;align-items:baseline;gap:5px}.metric strong{font-size:15px;color:#2b374c}.metric span{font-size:10px;color:var(--t3)}.manage-wrap{justify-self:end}.manage{color:var(--pri);text-decoration:none;font-weight:700;font-size:12px}.action-link{border:0;background:transparent;padding:0}.action-link:disabled{color:var(--t3)}.muted{color:var(--t3)}.pager{display:flex;justify-content:space-between;align-items:center;gap:16px;margin-top:16px;color:var(--t3);font-size:12px}.pager>div{display:flex;gap:8px}
@media(max-width:900px){.toolbar-card{align-items:stretch;flex-direction:column}.search-wrap{min-width:0}.total-chip{display:none}.row{flex-direction:column}.salary{text-align:left}.meta{grid-template-columns:repeat(3,1fr)}.manage-wrap{grid-column:1/-1;justify-self:start}.pager{align-items:flex-start;flex-direction:column}}
</style>
