<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { enterpriseInternshipApi } from '../services/enterpriseInternshipApi'
import { setSelectedCampaignId } from '../services/request'
import { useEnterpriseContextStore } from '../stores/enterpriseContext'

const context=useEnterpriseContextStore();const router=useRouter()
const rows=ref([]);const total=ref(0);const page=ref(1);const pageSize=20;const readStatus=ref('')
const loading=ref(false);const error=ref('');const selected=ref(null);const detailLoading=ref(false);const detailError=ref('');const actionError=ref('')
let listSequence=0,detailSequence=0,alive=true
const filters=[{value:'',label:'全部'},{value:'UNREAD',label:'未读'},{value:'READ',label:'已读'}]
const pages=computed(()=>Math.max(1,Math.ceil(total.value/pageSize)))
const actionLabel=computed(()=>selected.value?.actionKey==='enterprise.internship.application'?'打开学生申请':'打开岗位详情')
function formatTime(value){if(!value)return '时间待同步';const date=new Date(value);return Number.isNaN(date.getTime())?'时间待同步':date.toLocaleString('zh-CN',{month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false})}
function typeLabel(row){if(row?.msgType==='RETURNED_NOTICE')return '待补正';if(row?.msgType==='WORKFLOW_RESULT')return '办理结果';return '状态变化'}
async function load(reset=false){
  if(reset)page.value=1
  const sequence=++listSequence;loading.value=true;error.value=''
  try{const result=await enterpriseInternshipApi.messages({readStatus:readStatus.value,page:page.value,pageSize});if(!alive||sequence!==listSequence)return;rows.value=Array.isArray(result?.items)?result.items:[];total.value=Number(result?.total)||0}
  catch(e){if(alive&&sequence===listSequence){rows.value=[];total.value=0;error.value=e?.message||'消息读取失败'}}
  finally{if(alive&&sequence===listSequence)loading.value=false}
}
async function openMessage(row){
  const sequence=++detailSequence;detailLoading.value=true;detailError.value='';actionError.value=''
  try{
    const detail=await enterpriseInternshipApi.message(row.messageId)
    if(!alive||sequence!==detailSequence)return
    selected.value=detail
    if(detail.readStatus==='UNREAD'){
      await enterpriseInternshipApi.readMessage(detail.messageId)
      if(!alive||sequence!==detailSequence)return
      selected.value={...detail,readStatus:'READ'}
      const local=rows.value.find(item=>item.messageId===detail.messageId);if(local)local.readStatus='READ'
      await context.loadMessageCount()
    }
  }catch(e){if(alive&&sequence===detailSequence)detailError.value=e?.message||'消息详情读取失败'}
  finally{if(alive&&sequence===detailSequence)detailLoading.value=false}
}
async function openAction(){
  actionError.value=''
  const message=selected.value,params=message?.actionParams||{}
  const application=message?.actionKey==='enterprise.internship.application'
  const objectId=application?params.applicationId:params.positionId
  if(!['enterprise.internship.position','enterprise.internship.application'].includes(message?.actionKey)||!/^\d+$/.test(String(objectId||''))||!/^\d+$/.test(String(params.campaignId||''))){actionError.value='这条消息没有可安全打开的企业办理对象。';return}
  setSelectedCampaignId(params.campaignId)
  try { await context.load() }
  catch(e){if(alive&&selected.value===message)actionError.value=e?.message||'招聘季权限暂时无法核验，请重试。';return}
  if(!alive||selected.value!==message)return
  if(!context.recruitmentContextReady||String(context.campaign?.id)!==String(params.campaignId)){actionError.value='当前账号已不能进入该招聘季，请从招聘季选择页核对授权。';return}
  if(application&&!context.applicationViewAllowed){actionError.value='当前企业身份没有查看学生申请的权限。';return}
  await router.push({path:application?`/applications/${objectId}`:`/positions/${objectId}/edit`,query:{campaignId:String(params.campaignId)}})
}
function previous(){if(page.value<=1)return;page.value--;load()}
function next(){if(page.value>=pages.value)return;page.value++;load()}
function closeDetail(){selected.value=null;detailError.value='';actionError.value=''}
watch(readStatus,()=>{selected.value=null;load(true)},{immediate:true})
onBeforeUnmount(()=>{alive=false;listSequence++;detailSequence++})
</script>

<template>
  <section class="ep-page message-page">
    <header class="page-head">
      <div><span class="eyebrow">INBOX</span><h1 class="ep-title">消息通知</h1><p class="ep-subtitle">学校对企业岗位的退回、上架和状态调整会留在这里。消息已读不代表岗位已经补正。</p></div>
      <div class="unread-summary"><span>当前未读</span><strong>{{ context.unreadMessages }}</strong></div>
    </header>
    <div class="filter-row" role="radiogroup" aria-label="消息阅读状态">
      <button v-for="item in filters" :key="item.value||'all'" type="button" role="radio" :aria-checked="readStatus===item.value" :class="{active:readStatus===item.value}" @click="readStatus=item.value">{{ item.label }}</button>
      <button type="button" class="refresh" :disabled="loading" @click="load()">{{ loading?'读取中…':'重新读取' }}</button>
    </div>
    <div class="message-workspace" :class="{'detail-open':selected}">
      <section class="message-list" aria-label="企业消息列表">
        <div v-if="error" class="state error" role="alert">{{ error }}，请重新读取。</div>
        <div v-else-if="loading&&!rows.length" class="state">正在读取学校通知…</div>
        <div v-else-if="!rows.length" class="state">当前筛选下没有消息。</div>
        <button v-for="row in rows" :key="row.messageId" type="button" class="message-row" :class="{selected:selected?.messageId===row.messageId,unread:row.readStatus==='UNREAD'}" :aria-label="`${row.title}，${row.readStatus==='UNREAD'?'未读':'已读'}`" @click="openMessage(row)">
          <span class="status-dot"></span><span class="message-copy"><span class="row-meta"><b>{{ typeLabel(row) }}</b><time>{{ formatTime(row.createdAt) }}</time></span><strong>{{ row.title }}</strong><small>{{ row.summary||'打开查看通知内容' }}</small></span><span v-if="row.readStatus==='UNREAD'" class="unread-mark">未读</span>
        </button>
        <footer v-if="total" class="pager"><span>第 {{ page }} / {{ pages }} 页 · 共 {{ total }} 条</span><div><button type="button" :disabled="page<=1||loading" @click="previous">上一页</button><button type="button" :disabled="page>=pages||loading" @click="next">下一页</button></div></footer>
      </section>
      <aside class="message-detail" aria-live="polite">
        <button v-if="selected" type="button" class="mobile-back" @click="closeDetail">返回消息列表</button>
        <div v-if="detailLoading" class="state">正在读取消息正文…</div>
        <div v-else-if="detailError" class="state error" role="alert">{{ detailError }}</div>
        <div v-else-if="!selected" class="detail-empty"><span>消息详情</span><strong>选择左侧一条通知</strong><p>这里会显示学校反馈、办理对象和下一步入口。</p></div>
        <article v-else>
          <div class="detail-meta"><span>{{ typeLabel(selected) }}</span><time>{{ formatTime(selected.createdAt) }}</time></div>
          <h2>{{ selected.title }}</h2><p class="message-content">{{ selected.content||selected.summary }}</p>
          <div class="boundary-note"><b>办理边界</b><span>打开消息只会标记已读；办理状态以详情页实时结果为准。</span></div>
          <button v-if="selected.actionKey" type="button" class="ep-btn ep-btn-primary action-button" @click="openAction">{{ actionLabel }}</button>
          <p v-if="actionError" class="action-error" role="alert">{{ actionError }}</p>
        </article>
      </aside>
    </div>
  </section>
</template>

<style scoped>
.message-page{max-width:1280px;margin:0 auto}.page-head{display:flex;align-items:flex-end;justify-content:space-between;gap:24px;margin-bottom:18px}.eyebrow{display:block;font-size:10px;letter-spacing:.16em;color:var(--pri);font-weight:800;margin-bottom:7px}.unread-summary{min-width:132px;border-left:3px solid var(--pri);padding:5px 0 5px 14px;display:flex;align-items:baseline;justify-content:space-between;gap:16px}.unread-summary span{font-size:11px;color:var(--t3)}.unread-summary strong{font-size:26px;color:var(--pri);letter-spacing:-.04em}.filter-row{min-height:54px;display:flex;align-items:center;gap:7px;padding:7px 9px;margin-bottom:12px;background:#fff;border:1px solid var(--line);border-radius:12px;box-shadow:var(--shadow-sm)}.filter-row button{min-height:38px;padding:0 15px;border:1px solid transparent;border-radius:8px;background:transparent;color:var(--t3);font:inherit;font-size:12px;font-weight:650;cursor:pointer}.filter-row button:hover{background:var(--pri-50);color:var(--pri)}.filter-row button.active{background:var(--pri);color:#fff;box-shadow:0 5px 13px rgba(47,107,255,.2)}.filter-row .refresh{margin-left:auto;border-color:var(--line);color:var(--t2);background:#fff}.filter-row button:disabled{opacity:.55;cursor:not-allowed}
.message-workspace{min-height:570px;display:grid;grid-template-columns:minmax(360px,43%) minmax(0,1fr);background:#fff;border:1px solid var(--line);border-radius:14px;box-shadow:var(--shadow-sm);overflow:hidden}.message-list{border-right:1px solid var(--line);min-width:0}.message-row{width:100%;min-height:100px;display:grid;grid-template-columns:8px minmax(0,1fr) auto;gap:12px;align-items:start;padding:17px 18px;border:0;border-bottom:1px solid var(--line);background:#fff;text-align:left;cursor:pointer;color:inherit}.message-row:hover{background:#f9fbff}.message-row.selected{background:linear-gradient(90deg,var(--pri-50),#fff);box-shadow:inset 3px 0 var(--pri)}.status-dot{width:7px;height:7px;margin-top:23px;border-radius:50%;background:#c6ceda}.message-row.unread .status-dot{background:var(--pri);box-shadow:0 0 0 4px var(--pri-50)}.message-copy{min-width:0;display:flex;flex-direction:column;gap:5px}.row-meta{display:flex;align-items:center;justify-content:space-between;gap:12px}.row-meta b{font-size:10px;color:var(--pri);font-weight:750}.row-meta time{font-size:10px;color:var(--t4)}.message-copy>strong{font-size:13px;color:var(--t1);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.message-copy>small{font-size:11px;line-height:1.5;color:var(--t3);display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:2;overflow:hidden}.unread-mark{align-self:center;font-size:9px;color:var(--pri);background:var(--pri-50);padding:3px 6px;border-radius:999px}.state{padding:56px 24px;text-align:center;color:var(--t3);font-size:12px;line-height:1.7}.state.error{color:var(--danger-fg)}.pager{min-height:58px;padding:10px 16px;display:flex;align-items:center;justify-content:space-between;gap:12px}.pager>span{font-size:10px;color:var(--t4)}.pager div{display:flex;gap:6px}.pager button{min-height:34px;padding:0 10px;border:1px solid var(--line);border-radius:7px;background:#fff;color:var(--t2);cursor:pointer}.pager button:disabled{opacity:.45;cursor:not-allowed}
.message-detail{min-width:0;padding:32px 36px;background:radial-gradient(circle at 100% 0,rgba(47,107,255,.045),transparent 36%),#fff}.detail-empty{min-height:470px;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;color:var(--t3)}.detail-empty>span{font-size:10px;letter-spacing:.12em;color:var(--pri);font-weight:800}.detail-empty>strong{margin:9px 0 5px;font-size:17px;color:var(--t2)}.detail-empty p{font-size:12px}.detail-meta{display:flex;align-items:center;justify-content:space-between;gap:12px;padding-bottom:16px;border-bottom:1px solid var(--line)}.detail-meta span{font-size:10px;padding:5px 8px;border-radius:999px;background:var(--pri-50);color:var(--pri);font-weight:750}.detail-meta time{font-size:11px;color:var(--t4)}.message-detail h2{font-size:22px;line-height:1.35;margin:27px 0 14px;color:var(--t1);letter-spacing:-.02em}.message-content{min-height:92px;margin:0;color:var(--t2);font-size:14px;line-height:1.9;white-space:pre-wrap;overflow-wrap:anywhere}.boundary-note{display:flex;flex-direction:column;gap:5px;margin:28px 0 18px;padding:13px 15px;border-left:3px solid var(--pri-200);background:var(--pri-50);border-radius:0 9px 9px 0}.boundary-note b{font-size:11px;color:var(--t2)}.boundary-note span{font-size:11px;line-height:1.6;color:var(--t3)}.action-button{min-height:42px}.action-error{margin:9px 0 0;color:var(--danger-fg);font-size:11px;line-height:1.6}
.mobile-back{display:none;min-height:40px;margin:0 0 18px;padding:0 13px;border:1px solid var(--line);border-radius:8px;background:#fff;color:var(--t2);font:inherit;font-size:12px;font-weight:650;cursor:pointer}
.message-row:focus-visible,.filter-row button:focus-visible,.pager button:focus-visible{outline:2px solid var(--pri);outline-offset:-3px}
@media(max-width:900px){.message-workspace{grid-template-columns:1fr;min-height:360px}.message-list{border-right:0}.message-workspace:not(.detail-open) .message-detail{display:none}.message-workspace.detail-open .message-list{display:none}.message-detail{padding:20px;min-height:360px}.mobile-back{display:inline-flex;align-items:center}.detail-empty{min-height:300px}}
@media(max-width:600px){.page-head{align-items:flex-start}.unread-summary{min-width:92px}.message-workspace{border-radius:12px}.filter-row{overflow-x:auto}.filter-row button{min-width:64px;min-height:40px}.filter-row .refresh{min-width:82px}.message-row{padding:16px 14px}.unread-mark{display:none}.message-detail h2{font-size:19px}.pager{align-items:flex-start;flex-direction:column}.pager div,.pager button{width:100%}.pager div{display:grid;grid-template-columns:1fr 1fr}}
</style>
