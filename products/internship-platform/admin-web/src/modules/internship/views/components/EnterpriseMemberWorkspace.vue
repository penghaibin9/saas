<script setup>
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { AppCopyableText, AppInlineAlert, AppSelect, AppTextInput } from '@/components/common'
import { AppButton } from '@/components/ui'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import { enterpriseMemberApi as api } from '../../api/enterpriseMember.api'
import { internshipApi } from '../../api/internship.api'
import { recruitmentCampaignApi } from '../../api/recruitment-campaign.api'
import { canCode } from '../../composables/permission'
import { currentUserFromToken } from '@/services/http/client'
import { ENTERPRISE_LOGIN_URL } from '@/config/portalConfig'
import { formatDateTime } from '@/utils/dateUtils'

const props=defineProps({companyId:{type:String,required:true},contacts:{type:Array,default:()=>[]},ctx:{type:Object,required:true},batchId:{type:String,default:''}})
const scope=computed(()=>JSON.stringify([props.companyId,props.ctx.ctxKey,props.ctx.currentRole?.contextId,props.ctx.currentRole?.permissionVersion]))
const allowed=computed(()=>Array.isArray(props.ctx.permissionPatterns)&&canCode(props.ctx,'internship.enterprise.manage')&&
  (props.ctx.currentRole?.baseRoleCode||props.ctx.currentRole?.roleCode)==='SCHOOL_ADMIN')
const rows=ref([]),total=ref(0),page=ref(1),loading=ref(false),busy=ref(false),error=ref(''),receipt=ref(''),selected=ref(null),contactId=ref('')
const grants=ref([]),grantTotal=ref(0),grantPage=ref(1),grantLoading=ref(false),grantError=ref('')
const batchId=ref(props.batchId),batches=ref([]),batchKeyword=ref(''),batchPage=ref(1),batchTotal=ref(0),optionsLoading=ref(false)
const campaignId=ref(''),campaigns=ref([]),campaignPage=ref(1),campaignHasMore=ref(false)
const grantForm=reactive({validFrom:'',validUntil:''}),invite=reactive({loginName:'',realName:'',phone:'',memberRole:'HR',contactId:''})
const inviteOpen=ref(false),inviteUrl=ref(''),confirm=ref(null)
let epoch=0,memberRequest=0,grantRequest=0,optionRequest=0,alive=true
const roles=[{value:'COMPANY_ADMIN',label:'企业管理员'},{value:'HR',label:'招聘对接人'},{value:'MENTOR',label:'企业导师'}]
const roleLabel=value=>roles.find(item=>item.value===value)?.label||'企业成员'
const memberStatus=value=>({ACTIVE:'已开通',INVITED:'待本人激活',DISABLED:'已停用'}[value]||'状态待核对')
const grantStatus=value=>({ACTIVE:'有效',NOT_STARTED:'尚未生效',EXPIRED:'已到期',REVOKED:'已撤销'}[value]||'状态待核对')
const contactOptions=computed(()=>props.contacts.filter(item=>item.status==='ACTIVE'&&(!selected.value||selected.value.memberRole!=='MENTOR'||item.contactType==='MENTOR')).map(item=>({value:String(item.id),label:item.name})))
const inviteContacts=computed(()=>props.contacts.filter(item=>item.status==='ACTIVE'&&(invite.memberRole!=='MENTOR'||item.contactType==='MENTOR')).map(item=>({value:String(item.id),label:item.name})))
const batchOptions=computed(()=>batches.value.map(item=>({value:String(item.id),label:item.batchName||item.name||item.label})))
const campaignOptions=computed(()=>campaigns.value.map(item=>({value:String(item.id),label:item.campaignName})))
const current=ticket=>alive&&ticket===epoch
async function loadMembers(){
  const ticket=epoch,request=++memberRequest
  if(!allowed.value)return
  loading.value=true;error.value=''
  try{const data=await api.members(props.companyId,page.value);if(current(ticket)&&request===memberRequest){rows.value=data.items||[];total.value=data.total||0}}
  catch(e){if(current(ticket)&&request===memberRequest){rows.value=[];total.value=0;error.value=e.message||'企业成员读取失败'}}
  finally{if(current(ticket)&&request===memberRequest)loading.value=false}
}
async function loadGrants(){
  if(!selected.value)return
  const ticket=epoch,id=selected.value.id,request=++grantRequest
  grantLoading.value=true;grantError.value=''
  try{const data=await api.grants(props.companyId,id,grantPage.value);if(current(ticket)&&selected.value?.id===id&&request===grantRequest){grants.value=data.items||[];grantTotal.value=data.total||0}}
  catch(e){if(current(ticket)&&selected.value?.id===id&&request===grantRequest){grants.value=[];grantError.value=e.message||'授权记录读取失败'}}
  finally{if(current(ticket)&&selected.value?.id===id&&request===grantRequest)grantLoading.value=false}
}
function choose(row){if(busy.value)return;selected.value={...row};contactId.value=row.contactId||'';grants.value=[];grantTotal.value=0;grantPage.value=1;grantForm.validFrom='';grantForm.validUntil='';error.value='';loadGrants()}
async function loadOptions(reset=false){
  if(reset)batchPage.value=1
  const ticket=epoch,request=++optionRequest
  optionsLoading.value=true
  try{
    const result=await internshipApi.getBatchOptions({page:batchPage.value,pageSize:20,keyword:batchKeyword.value,selectedId:batchId.value||undefined})
    if(!current(ticket)||request!==optionRequest)return
    if(result.code!==0)throw new Error(result.message)
    batches.value=result.data.items||[];batchTotal.value=result.data.total||0
    if(result.data.selected&&!batches.value.some(row=>String(row.id)===String(result.data.selected.id)))batches.value.unshift(result.data.selected)
  }catch(e){if(current(ticket)&&request===optionRequest)error.value=e.message||'批次目录读取失败'}
  finally{if(current(ticket)&&request===optionRequest)optionsLoading.value=false}
}
async function loadCampaigns(){
  const ticket=epoch,id=batchId.value,p=campaignPage.value
  campaigns.value=[];campaignHasMore.value=false
  if(!id)return
  try{const result=await recruitmentCampaignApi.getCampaigns({batchId:id,page:p,pageSize:20});if(!current(ticket)||batchId.value!==id||campaignPage.value!==p)return;if(result.code!==0)throw new Error(result.message);campaigns.value=result.data.list||[];campaignHasMore.value=result.data.hasMore}
  catch(e){if(current(ticket)&&batchId.value===id)error.value=e.message||'招聘季读取失败'}
}
async function write(action,message){
  if(busy.value||!allowed.value)return
  const ticket=epoch;busy.value=true;error.value='';receipt.value=''
  try{await action();if(!current(ticket))return;receipt.value=message;await loadMembers();if(selected.value)await loadGrants()}
  catch(e){if(current(ticket))error.value=(e.message||'办理失败')+'。填写内容已保留；资料冲突时请明确重新选择成员核对后再提交。'}
  finally{if(current(ticket))busy.value=false}
}
function bind(){
  const target=selected.value,contact=contactId.value,ticket=epoch
  if(!target||!contact)return
  return write(async()=>{const result=await api.bind(props.companyId,target.id,{contactId:contact,expectedVersion:target.version});if(current(ticket))selected.value={...target,...result}},'导师联系人已绑定。该企业成员重新登录后，按已授权批次查看本人学生。')
}
function issue(){
  const target=selected.value
  if(!target||!batchId.value||!grantForm.validFrom||!grantForm.validUntil){error.value='请选择批次并明确填写授权起止时间';return}
  if(!Number.isFinite(Date.parse(grantForm.validFrom))||!Number.isFinite(Date.parse(grantForm.validUntil))){error.value='请完整填写有效的授权起止日期和时间';return}
  if(new Date(grantForm.validUntil)<=new Date(grantForm.validFrom)){error.value='截止时间必须晚于生效时间';return}
  return write(()=>api.issue(props.companyId,target.id,{batchId:batchId.value,validFrom:new Date(grantForm.validFrom).toISOString(),validUntil:new Date(grantForm.validUntil).toISOString(),expectedMemberVersion:target.version}), '该批次实习协同已开通。请企业成员登录后进入该范围继续评价；招聘权与实习协同权分别核验。')
}
function askStatus(){const target={...selected.value};confirm.value={type:'status',target,title:target.status==='DISABLED'?'恢复企业成员访问':'停用企业成员',message:target.status==='DISABLED'?'仅恢复已本人激活的成员；原批次授权的有效期保持原样。':'停用后该成员旧登录将被拒绝，原评价及历史材料保留。'}}
function askRevoke(grant){confirm.value={type:'revoke',target:{...selected.value},grant:{...grant},title:'撤销本批次协同授权',message:'该成员将不能再办理本批次协同；历史评价、材料和其他批次授权保留。'}}
async function confirmAction(payload){
  const operation=confirm.value,reason=String(payload?.reason||'').trim();if(!operation||reason.length<2){error.value='请至少填写两个字的办理原因';return}
  const ticket=epoch
  await write(async()=>{
    if(operation.type==='status'){const data=await api.status(props.companyId,operation.target.id,{status:operation.target.status==='DISABLED'?'ACTIVE':'DISABLED',expectedVersion:operation.target.version,reason});if(current(ticket))selected.value={...operation.target,...data}}
    else await api.revoke(props.companyId,operation.target.id,operation.grant.id,{expectedVersion:operation.grant.version,reason})
    if(current(ticket))confirm.value=null
  },operation.type==='status'?'企业成员状态已更新，重新进入将按当前身份及授权核验。':'该批次协同授权已撤销，原评价与审计记录保留。')
}
async function sendInvite(){
  if(!campaignId.value){error.value='请选择当前批次可邀请的招聘季';return}
  if(!invite.loginName.trim()||!invite.realName.trim()||invite.phone.trim().length<6){error.value='请填写登录账号、姓名和本人核验手机号';return}
  if(invite.memberRole==='MENTOR'&&!invite.contactId){error.value='请为企业导师选择已有导师联系人';return}
  const ticket=epoch,body={...invite,companyId:props.companyId,inviteSource:'MANUAL'}
  if(!body.contactId)delete body.contactId
  await write(async()=>{
    const result=await recruitmentCampaignApi.inviteEnterprise(campaignId.value,body)
    if(result.code!==0)throw new Error(result.message)
    if(!current(ticket))return
    const root=String(ENTERPRISE_LOGIN_URL||'/enterprise/login').replace(/\/login\/?$/,'')
    const url=new URL(`${root}/invite/accept`,window.location.origin)
    url.searchParams.set('token',result.data.inviteToken);url.searchParams.set('tenantCode',currentUserFromToken()?.tenantCode||'')
    inviteUrl.value=url.href;inviteOpen.value=false
  },'个人邀请已生成。请向该成员交接本次链接，由本人核对手机号并激活；正式实习协同需再按批次明确开通。')
}
watch(batchId,()=>{campaignId.value='';campaignPage.value=1;loadCampaigns()})
watch([scope,allowed],()=>{epoch++;memberRequest++;grantRequest++;optionRequest++;rows.value=[];selected.value=null;grants.value=[];confirm.value=null;inviteOpen.value=false;inviteUrl.value='';error.value='';receipt.value='';busy.value=false;page.value=1;batchId.value=props.batchId;Object.assign(invite,{loginName:'',realName:'',phone:'',memberRole:'HR',contactId:''});if(allowed.value){loadMembers();loadOptions();loadCampaigns()}},{immediate:true})
onBeforeUnmount(()=>{alive=false;epoch++})
</script>

<template>
  <section class="member-workspace">
    <h2>企业成员与访问授权</h2>
    <p>先由本人接受邀请，再绑定导师联系人、按批次明确开通实习协同。学校负责维护；企业老师只访问实际授权范围。</p>
    <AppInlineAlert v-if="!allowed" type="warning" title="需要校级企业管理身份" description="请由具有企业维护权限的校级管理员办理，不会自动增加当前身份权限。" />
    <template v-else>
      <AppInlineAlert v-if="error" type="danger" :description="error" />
      <AppInlineAlert v-if="receipt" type="success" title="办理结果" :description="receipt" />
      <div v-if="inviteUrl" class="member-receipt"><strong>本次个人邀请链接</strong><AppCopyableText :value="inviteUrl" /><AppButton variant="ghost" @click="inviteUrl=''">关闭链接</AppButton></div>
      <div class="member-actions"><AppButton :disabled="loading||busy" @click="loadMembers">重新读取成员</AppButton><AppButton :disabled="busy" @click="inviteOpen=!inviteOpen">新增个人邀请</AppButton></div>
      <div class="batch-picker"><label>办理批次<AppSelect v-model="batchId" :options="batchOptions" placeholder="请选择批次" :disabled="busy||optionsLoading" /></label><label>查找批次<AppTextInput v-model.trim="batchKeyword" :disabled="busy" placeholder="输入批次名称" /></label><AppButton :disabled="busy||optionsLoading" @click="loadOptions(true)">查找</AppButton><AppButton :disabled="busy||optionsLoading||batchPage<=1" @click="batchPage--;loadOptions()">上一组批次</AppButton><AppButton :disabled="busy||optionsLoading||batchPage*20>=batchTotal" @click="batchPage++;loadOptions()">下一组批次</AppButton></div>
      <form v-if="inviteOpen" class="member-form" @submit.prevent="sendInvite"><h3>邀请本企业的新成员</h3><p>已有账号保持原密码和身份；接受个人邀请不会重复更改企业参与状态。邀请仍须处于学校规定的招聘窗口。</p><label>所属招聘季<AppSelect v-model="campaignId" :options="campaignOptions" placeholder="请选择招聘季" :disabled="busy" /></label><div class="member-actions"><AppButton :disabled="busy||campaignPage<=1" @click="campaignPage--;loadCampaigns()">上一组招聘季</AppButton><AppButton :disabled="busy||!campaignHasMore" @click="campaignPage++;loadCampaigns()">下一组招聘季</AppButton></div><label>成员身份<AppSelect v-model="invite.memberRole" :options="roles" :disabled="busy" /></label><label>登录账号<AppTextInput v-model.trim="invite.loginName" required maxlength="100" :disabled="busy" /></label><label>姓名<AppTextInput v-model.trim="invite.realName" required maxlength="100" :disabled="busy" /></label><label>本人核验手机号<AppTextInput v-model.trim="invite.phone" required minlength="6" maxlength="30" :disabled="busy" /></label><label>导师联系人<AppSelect v-model="invite.contactId" :options="inviteContacts" placeholder="企业导师须选择；其他身份可不选" :disabled="busy" /></label><p v-if="!inviteContacts.length">尚无有效联系人，请先从“联系人与导师”新增真实对接人。</p><AppButton type="submit" variant="primary" :disabled="busy">生成个人邀请</AppButton></form>
      <p v-if="loading">正在核对企业成员…</p><p v-else-if="!error&&!rows.length">当前企业尚未开通成员，请先生成个人邀请。</p>
      <div class="member-grid"><section><h3>选择办理成员</h3><button v-for="row in rows" :key="row.id" type="button" class="member-row" :class="{active:selected?.id===row.id}" :disabled="busy" @click="choose(row)"><strong>{{ row.realName }}</strong><span>{{ roleLabel(row.memberRole) }} · {{ memberStatus(row.status) }}</span><small>导师联系人：{{ row.contactName||'尚未绑定' }}</small><small v-if="selected?.id===row.id">已选择；再次点击会重新读取并核对该成员，放弃当前未提交修改</small></button><div class="member-actions"><span>第 {{ page }} 页 · {{ total }} 人</span><AppButton :disabled="busy||loading||page<=1" @click="page--;loadMembers()">上一页</AppButton><AppButton :disabled="busy||loading||page*20>=total" @click="page++;loadMembers()">下一页</AppButton></div></section>
      <section v-if="selected" class="member-detail"><h3>{{ selected.realName }} · {{ roleLabel(selected.memberRole) }}</h3><form class="member-form" @submit.prevent="bind"><label>绑定联系人<AppSelect v-model="contactId" :options="contactOptions" placeholder="选择本企业有效联系人" :disabled="busy" /></label><AppButton type="submit" :disabled="busy||!contactId">确认绑定联系人</AppButton></form><AppButton :disabled="busy||(!selected.acceptedAt&&selected.status==='DISABLED')" @click="askStatus">{{ selected.status==='DISABLED'?'恢复已激活成员':'停用成员' }}</AppButton>
        <form class="member-form" @submit.prevent="issue"><h3>开通本批次实习协同</h3><p>企业须已接受该批次招聘，或已有正式分配的本批次学生；企业导师还须与学生导师绑定一致。此授权用于正式实习学生与评价，不扩大招聘权限。旧授权不会自动续期或恢复。</p><label>生效时间<AppTextInput v-model="grantForm.validFrom" type="datetime-local" required :disabled="busy" /></label><label>截止时间<AppTextInput v-model="grantForm.validUntil" type="datetime-local" required :disabled="busy" /></label><AppButton type="submit" variant="primary" :disabled="busy||selected.status!=='ACTIVE'||!batchId">明确开通本批次</AppButton><p v-if="selected.status!=='ACTIVE'">成员需本人激活并处于正常状态，才能开通批次协同。</p></form>
        <h3>已登记的协同授权</h3><p v-if="grantLoading">正在读取授权…</p><AppInlineAlert v-else-if="grantError" type="danger" :description="grantError" /><p v-else-if="!grants.length">尚无正式实习协同授权。</p><article v-for="grant in grants" :key="grant.id" class="member-grant"><strong>{{ grant.batchName }} · {{ grantStatus(grant.effectiveStatus) }}</strong><p>{{ formatDateTime(grant.validFrom) }} 至 {{ formatDateTime(grant.validUntil) }}</p><AppButton v-if="grant.status!=='REVOKED'" :disabled="busy" @click="askRevoke(grant)">撤销本批次授权</AppButton></article><div class="member-actions"><AppButton :disabled="busy||grantLoading||grantPage<=1" @click="grantPage--;loadGrants()">上一页授权</AppButton><AppButton :disabled="busy||grantLoading||grantPage*20>=grantTotal" @click="grantPage++;loadGrants()">下一页授权</AppButton></div>
      </section><p v-else>选择一位成员，核对绑定、状态和各批次授权。</p></div>
      <AppConfirmDialog v-if="confirm" :visible="true" :title="confirm.title" :message="confirm.message" require-reason reason-label="办理原因" :submitting="busy" @update:visible="value=>{if(!value&&!busy)confirm=null}" @confirm="confirmAction" />
    </template>
  </section>
</template>

<style scoped>
.member-workspace{padding:22px;background:var(--mp-surface,#fff);border:1px solid var(--mp-border,#dde3eb);border-radius:12px}.member-workspace>p,.member-form>p{line-height:1.7;color:var(--mp-text-secondary,#586574)}.member-actions,.batch-picker{display:flex;gap:10px;align-items:end;flex-wrap:wrap;margin:14px 0}.batch-picker>label{min-width:200px;flex:1}.member-grid{display:grid;grid-template-columns:minmax(230px,1fr) minmax(300px,2fr);gap:24px}.member-row{display:flex;flex-direction:column;gap:7px;width:100%;text-align:left;margin:8px 0;padding:14px;border:1px solid #dbe2ec;border-radius:8px;background:#fff;color:#27374d;overflow-wrap:anywhere}.member-row.active{border-color:#376cec;background:#f3f7ff}.member-row small{color:#596779}.member-form{display:grid;gap:12px;margin:20px 0;padding:18px;background:#f7f9fc;border-radius:8px}.member-form label,.batch-picker label{display:flex;flex-direction:column;gap:7px}.member-form h3,.member-form p{margin:0}.member-grant,.member-receipt{padding:14px;margin:10px 0;border:1px solid #dbe2ec;border-radius:8px;overflow-wrap:anywhere}.member-grant p{font-size:13px;line-height:1.6}.member-detail{min-width:0}@media(max-width:850px){.member-grid{grid-template-columns:1fr}.member-workspace{padding:14px}}
</style>
