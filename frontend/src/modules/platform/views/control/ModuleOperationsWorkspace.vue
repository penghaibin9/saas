<template>
  <section class="ops-workspace" aria-label="商业售后与持续治理">
    <header class="ops-head">
      <div><span class="eyebrow">CUSTOMER SUCCESS GOVERNANCE</span><h3>售后、SLA 与实际服务成本</h3><p>工单继续使用现有客户成功中心；这里只汇总退款后授权复核、SLA 观察、培训/续费/交付信号和真实成本。</p></div>
      <button :disabled="loading||!tenantId" @click="loadAll">刷新治理事实</button>
    </header>
    <div v-if="!tenantId" class="empty">先选择学校。</div>
    <template v-else>
      <p v-if="error" class="error">{{ error }}</p><p v-if="notice" class="success">{{ notice }}</p>
      <div v-if="overview" class="metrics">
        <article :class="{warn:overview.pendingRefundEntitlementReviews}"><strong>{{ overview.pendingRefundEntitlementReviews }}</strong><span>退款后待授权复核</span></article>
        <article :class="{warn:overview.openRefundAfterSalesTickets}"><strong>{{ overview.openRefundAfterSalesTickets }}</strong><span>退款售后工单处理中</span></article>
        <article><strong>{{ overview.scheduledTrainings }}</strong><span>待执行培训</span></article>
        <article><strong>{{ overview.openRenewalTasks }}</strong><span>续费跟进中</span></article>
        <article><strong>{{ overview.moduleDeliveryAcceptanceFacts }}</strong><span>模块交付验收事实</span></article>
      </div>

      <section class="panel sla-panel">
        <div class="section-head">
          <div><h4>商业 SLA 政策</h4><p>只有合同或正式服务政策明确后才填写。P0–P3 四级目标必须全部明确；系统不会补默认小时数。</p></div>
          <span v-if="slaEditor?.effective?.configured" class="policy-badge">当前生效：{{ slaEditor.effective.version }} · {{ slaEditor.effective.source==='TENANT'?'学校覆盖':'平台默认' }}</span>
          <span v-else class="policy-badge muted">当前未评估</span>
        </div>
        <div v-if="slaEditor" class="sla-state">
          <span>学校覆盖版本：{{ slaEditor.tenantOverride?.rowVersion ?? 0 }}</span>
          <span>{{ slaEditor.tenantOverride?.enabled ? '学校覆盖已启用' : (slaEditor.tenantOverride?.exists ? '学校覆盖已停用' : '尚无学校覆盖') }}</span>
          <span>权威：{{ slaEditor.authority }}</span>
        </div>
        <div v-if="slaEditor?.effective?.configured" class="target-preview">
          <div v-for="severity in severities" :key="severity"><strong>{{ severity }}</strong><span>{{ slaEditor.effective.targetsHours?.[severity] }} 小时</span></div>
        </div>
        <div v-else class="notice">当前没有有效的商业 SLA 明确政策，因此只展示已耗时，不判“达标/超时”；系统不会自行生成服务承诺。</div>
        <fieldset :disabled="savingSla||locked||!canCommercialManage">
          <div class="sla-form-head"><label>政策版本<input v-model.trim="slaForm.policyVersion" minlength="3" maxlength="64" placeholder="如 CONTRACT-SLA-2026-09"></label><label class="grow">变更原因<input v-model.trim="slaForm.reason" minlength="5" maxlength="500" placeholder="填写合同或正式服务政策依据"></label></div>
          <div class="sla-targets"><label v-for="severity in severities" :key="severity">{{ severity }} 目标小时<input v-model="slaForm.targets[severity]" inputmode="decimal" placeholder="必须明确填写"></label></div>
          <div class="sla-actions"><button class="primary" :disabled="!slaReady" @click="saveSla">{{ savingSla?'正在保存…':'保存学校SLA覆盖' }}</button><button v-if="slaEditor?.tenantOverride?.enabled" :disabled="savingSla||slaForm.reason.length<5" @click="resetSla">恢复平台默认 / 未评估</button><span>expectedVersion {{ slaEditor?.tenantOverride?.rowVersion ?? 0 }}</span></div>
        </fieldset>
        <p v-if="!canCommercialManage" class="notice">当前职责没有 commercial.manage，只能查看 SLA 政策。</p>
      </section>

      <section class="panel">
        <div class="section-head"><div><h4>退款后授权复核工单</h4><p>从“退款”页已结算记录显式生成；这里读取现有 SupportTicket 的状态与时间。</p></div><router-link to="/admin/platform/customer-success">进入客户成功中心处理工单</router-link></div>
        <div class="table-scroll"><table><thead><tr><th>工单</th><th>退款 / 订单</th><th>模块快照</th><th>状态</th><th>SLA</th></tr></thead><tbody>
          <tr v-for="row in afterSales" :key="row.linkId"><td>#{{ row.supportTicketId }} · {{ row.ticket.title }}<small>{{ row.ticket.severity }} · {{ showTime(row.ticket.createdAt) }}</small></td><td>退款 #{{ row.refundCaseId }}<small>订单 #{{ row.orderId }}</small></td><td>{{ modulesText(row.moduleSnapshot) }}</td><td>{{ ticketStatus(row.ticket.status) }}</td><td :class="row.sla.status==='BREACHED'?'bad-text':''">{{ slaText(row.sla) }}</td></tr>
          <tr v-if="!afterSales.length&&!loading"><td colspan="5">暂无退款后授权复核工单。</td></tr>
        </tbody></table></div>
        <div class="pager"><button :disabled="afterPage===1||loading" @click="loadAfterSales(afterPage-1)">上一页</button><span>共 {{ afterTotal }} 条</span><button :disabled="afterPage*20>=afterTotal||loading" @click="loadAfterSales(afterPage+1)">下一页</button></div>
      </section>

      <section class="panel cost-panel">
        <div class="section-head"><div><h4>登记实际服务成本</h4><p>只登记已实际发生的支持、交付、培训、退款手续费等成本；不同币种永不自动换算或合计。</p></div></div>
        <div v-if="costPending" class="pending"><strong>上次成本登记结果仍需核对</strong><p>原请求与幂等键已保留，请重试原请求。</p><button class="primary" :disabled="savingCost||!canManage" @click="submitCost">重试原请求</button></div>
        <fieldset :disabled="savingCost||locked||!canManage||!!costPending">
          <div class="form-grid"><label>成本类型<select v-model="costForm.costType"><option value="">请选择</option><option value="SUPPORT">支持</option><option value="DELIVERY">交付</option><option value="TRAINING">培训</option><option value="REFUND_FEE">退款手续费</option><option value="OTHER">其他</option></select></label><label>金额<input v-model.trim="costForm.amount" inputmode="decimal" placeholder="0.00"></label><label>币种<input v-model.trim="costForm.currency" maxlength="3" placeholder="如 CNY"></label><label>发生时间（北京时间）<input v-model="costForm.occurredAt" type="datetime-local" step="1"></label></div>
          <div class="form-grid refs"><label>关联售后工单<select v-model="costForm.afterSalesLink" @change="useAfterSales"><option value="">不从退款售后工单带入</option><option v-for="row in afterSales" :key="row.linkId" :value="row.linkId">工单 #{{ row.supportTicketId }} · 退款 #{{ row.refundCaseId }}</option></select></label><label>订单 ID<input v-model.trim="costForm.orderId" inputmode="numeric" placeholder="至少关联订单/退款/工单一个对象"></label><label>退款记录 ID<input v-model.trim="costForm.refundCaseId" inputmode="numeric"></label><label>工单 ID<input v-model.trim="costForm.supportTicketId" inputmode="numeric"></label></div>
          <div class="form-grid refs"><label>外部凭据<input v-model.trim="costForm.externalRef" maxlength="160" placeholder="工资、采购、渠道手续费等真实凭据编号（可选）"></label><label>说明<input v-model.trim="costForm.note" maxlength="500" placeholder="说明实际成本来源"></label></div>
          <button class="primary" :disabled="!costReady" @click="submitCost">{{ savingCost?'正在登记…':'登记实际成本' }}</button>
        </fieldset>
        <div v-if="Object.keys(costSummary).length" class="summary"><div v-for="(rows,currency) in costSummary" :key="currency"><strong>{{ currency }}</strong><span v-for="row in rows" :key="row.costType">{{ costTypeLabel(row.costType) }} {{ row.amount }}（{{ row.count }}笔）</span></div></div>
        <div class="table-scroll"><table><thead><tr><th>发生时间</th><th>类型</th><th>金额</th><th>关联</th><th>凭据 / 说明</th></tr></thead><tbody><tr v-for="row in costs" :key="row.costId"><td>{{ showTime(row.occurredAt) }}</td><td>{{ costTypeLabel(row.costType) }}</td><td>{{ row.currency }} {{ row.amount }}</td><td>订单 {{ row.orderId||'—' }}<small>退款 {{ row.refundCaseId||'—' }} · 工单 {{ row.supportTicketId||'—' }}</small></td><td>{{ row.externalRef||'—' }}<small>{{ row.note||'' }}</small></td></tr><tr v-if="!costs.length&&!loading"><td colspan="5">暂无实际服务成本记录。</td></tr></tbody></table></div>
        <div class="pager"><button :disabled="costPage===1||loading" @click="loadCosts(costPage-1)">上一页</button><span>共 {{ costTotal }} 条</span><button :disabled="costPage*20>=costTotal||loading" @click="loadCosts(costPage+1)">下一页</button></div>
      </section>
      <p v-if="!canManage" class="notice">当前职责没有 order.manage，只能查看售后与成本事实。</p>
    </template>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { moduleCommerceApi as api } from '@/modules/platform/api/moduleCommerce.api'
import { ensurePlatformAccessContext } from '@/security/platformAccessGate'
import { isDefinitiveRejection, localInputToUtc, utcToLocalInput } from '../../lib/moduleCommerceSales.mjs'
import { safeBusinessMessage, safeEnumLabel } from '@/utils/presentationSafety'

const props=defineProps({tenantId:{type:String,default:''},locked:Boolean})
const severities=['P0','P1','P2','P3']
const access=ref(null),overview=ref(null),afterSales=ref([]),afterPage=ref(1),afterTotal=ref(0),costs=ref([]),costPage=ref(1),costTotal=ref(0),costSummary=ref({}),slaEditor=ref(null),loading=ref(false),savingCost=ref(false),savingSla=ref(false),error=ref(''),notice=ref(''),costPending=ref(null)
const blankCost=()=>({costType:'',amount:'',currency:'',occurredAt:'',afterSalesLink:'',orderId:'',refundCaseId:'',supportTicketId:'',externalRef:'',note:''})
const blankSla=()=>({policyVersion:'',targets:{P0:'',P1:'',P2:'',P3:''},reason:''})
const costForm=ref(blankCost()),slaForm=ref(blankSla())
const canManage=computed(()=>!!access.value?.duties?.some(d=>['*','order.manage'].includes(d)))
const canCommercialManage=computed(()=>!!access.value?.duties?.some(d=>['*','commercial.manage'].includes(d)))
const moneyOk=v=>/^\d+(?:\.\d{1,2})?$/.test(String(v||''))&&Number(v)>0
const refsOk=computed(()=>[costForm.value.orderId,costForm.value.refundCaseId,costForm.value.supportTicketId].some(v=>/^\d+$/.test(String(v||''))))
const costReady=computed(()=>canManage.value&&!savingCost.value&&!props.locked&&!costPending.value&&['SUPPORT','DELIVERY','TRAINING','REFUND_FEE','OTHER'].includes(costForm.value.costType)&&moneyOk(costForm.value.amount)&&/^[A-Za-z]{3}$/.test(costForm.value.currency)&&!!costForm.value.occurredAt&&refsOk.value)
const slaReady=computed(()=>canCommercialManage.value&&!savingSla.value&&!props.locked&&slaForm.value.policyVersion.length>=3&&slaForm.value.reason.length>=5&&severities.every(s=>moneyOk(slaForm.value.targets[s])))
function showTime(v){return v?utcToLocalInput(v).replace('T',' '):'—'}
function modulesText(rows){return(rows||[]).map(r=>`${safeEnumLabel({value:r.moduleKey,dictionary:{internship:'岗位实习',graduationDesign:'毕业设计',studentAffairs:'学工',academicAffairs:'教务'}})} ×${r.sourceCount}`).join('、')||'—'}
function ticketStatus(v){return safeEnumLabel({value:v,dictionary:{OPEN:'待处理',IN_PROGRESS:'处理中',RESOLVED:'已解决',CLOSED:'已关闭'}})}
function slaText(sla){if(!sla?.policyConfigured)return`已耗时 ${sla?.elapsedHours??0}h · 未配置SLA`;return`${sla.status==='BREACHED'?'已超目标':'目标内'} · ${sla.elapsedHours}h / ${sla.targetHours}h`}
function costTypeLabel(v){return safeEnumLabel({value:v,dictionary:{SUPPORT:'支持',DELIVERY:'交付',TRAINING:'培训',REFUND_FEE:'退款手续费',OTHER:'其他'}})}
let epoch=0, overviewSeq=0, afterSeq=0, costSeq=0, slaSeq=0, disposed=false
const current=(id,token)=>id===props.tenantId&&token===epoch
function storageKey(){return`gx_module_service_cost_pending_v1:${access.value?.subjectId||''}:${props.tenantId}`}
function newKey(){const s=globalThis.crypto?.randomUUID?.()||`${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;return`m8-cost-${s}`.slice(0,160)}
function savePending(v){v?sessionStorage.setItem(storageKey(),JSON.stringify(v)):sessionStorage.removeItem(storageKey());costPending.value=v}
function restorePending(){
  costPending.value=null
  if(!access.value?.subjectId||!props.tenantId)return
  try {
    const raw=sessionStorage.getItem(storageKey())
    if(!raw)return
    const p=JSON.parse(raw)
    if(p?.tenantId!==props.tenantId||typeof p.key!=='string'||!p.key||!p.body)throw new Error('原成本请求无法核对，请联系管理员，勿重复登记')
    costPending.value=p
  } catch(e) { error.value=safeBusinessMessage(e,'无法读取原成本请求，请先核对台账');access.value=null }
}
async function recheckDuty(duty,message){const previous=access.value?.subjectId;const current=await ensurePlatformAccessContext({force:true});if(!current||String(current.subjectId)!==String(previous)||!current.duties?.some(d=>['*',duty].includes(d)))throw new Error(message)}
async function loadOverview(){
  const id=props.tenantId,token=epoch,seq=++overviewSeq
  if(!id)return
  try{const d=await api.getOperationsOverview(id);if(current(id,token)&&seq===overviewSeq)overview.value=d}
  catch(e){if(current(id,token)&&seq===overviewSeq){overview.value=null;error.value=safeBusinessMessage(e)}}
}
async function loadAfterSales(page=1){
  const id=props.tenantId,token=epoch,seq=++afterSeq
  if(!id)return
  try{const d=await api.listAfterSales(id,{page,pageSize:20});if(!current(id,token)||seq!==afterSeq)return;afterSales.value=d.items||[];afterTotal.value=d.total||0;afterPage.value=page}
  catch(e){if(current(id,token)&&seq===afterSeq){afterSales.value=[];afterTotal.value=0;error.value=safeBusinessMessage(e)}}
}
async function loadCosts(page=1){
  const id=props.tenantId,token=epoch,seq=++costSeq
  if(!id)return
  try{
    const d=await api.listServiceCosts(id,{page,pageSize:20})
    if(!current(id,token)||seq!==costSeq)return
    if(d.currencyConverted!==false)throw new Error('成本币种核对未通过，请重新读取台账')
    costs.value=d.items||[];costTotal.value=d.total||0;costPage.value=page;costSummary.value=d.summaryByCurrency||{}
  }catch(e){if(current(id,token)&&seq===costSeq){costs.value=[];costTotal.value=0;costSummary.value={};error.value=safeBusinessMessage(e)}}
}
async function loadSla(){
  const id=props.tenantId,token=epoch,seq=++slaSeq
  if(!id)return
  try {
    const d=await api.getSlaPolicy(id)
    if(!current(id,token)||seq!==slaSeq)return
    slaEditor.value=d
    const source=d.tenantOverride?.enabled?d.tenantOverride?.policy:(d.effective?.configured?{version:d.effective.version,targetsHours:d.effective.targetsHours}:null)
    slaForm.value={policyVersion:String(source?.version||''),targets:Object.fromEntries(severities.map(s=>[s,source?.targetsHours?.[s]??''])),reason:''}
  }catch(e){if(current(id,token)&&seq===slaSeq){slaEditor.value=null;error.value=safeBusinessMessage(e)}}
}
async function loadAll(){const id=props.tenantId,token=epoch;if(!id)return;loading.value=true;error.value='';try{await Promise.all([loadOverview(),loadAfterSales(afterPage.value),loadCosts(costPage.value),loadSla()])}finally{if(current(id,token))loading.value=false}}
function useAfterSales(){const row=afterSales.value.find(r=>r.linkId===costForm.value.afterSalesLink);if(!row)return;costForm.value.orderId=row.orderId;costForm.value.refundCaseId=row.refundCaseId;costForm.value.supportTicketId=row.supportTicketId}
async function submitCost(){
  if(savingCost.value||props.locked||!props.tenantId||!canManage.value)return
  const id=props.tenantId,token=epoch,form={...costForm.value},saved=costPending.value
  savingCost.value=true;error.value='';notice.value=''
  try{
    await recheckDuty('order.manage','平台身份或职责已变化，成本写操作已停止')
    if(!current(id,token)||props.locked)return
    let attempt=saved
    if(!attempt){
      const body={costType:form.costType,amount:form.amount,currency:form.currency.toUpperCase(),occurredAt:localInputToUtc(form.occurredAt),orderId:form.orderId||null,refundCaseId:form.refundCaseId||null,supportTicketId:form.supportTicketId||null,externalRef:form.externalRef,note:form.note}
      attempt={tenantId:id,key:newKey(),body};savePending(attempt)
    }
    if(attempt.tenantId!==id)throw new Error('原请求不属于当前学校，请先核对台账')
    const result=await api.recordServiceCost(id,attempt.body,attempt.key)
    if(!current(id,token))return
    if(!result?.costId||String(result.tenantId)!==id)throw new Error('未取得匹配的成本回执，请核对原请求；勿重复登记')
    savePending(null);costForm.value=blankCost();notice.value='实际服务成本已登记；不同币种仍分开汇总，未做换算'
    await Promise.all([loadCosts(1),loadOverview()])
  }catch(e){if(current(id,token)){error.value=safeBusinessMessage(e,'登记结果不明，请重试原请求');if(isDefinitiveRejection(e))savePending(null)}}
  finally{if(current(id,token))savingCost.value=false}
}
async function saveSla(){
  if(!slaReady.value||!props.tenantId)return
  const id=props.tenantId,token=epoch
  const body={expectedVersion:slaEditor.value?.tenantOverride?.rowVersion??0,policyVersion:slaForm.value.policyVersion,targetsHours:Object.fromEntries(severities.map(s=>[s,slaForm.value.targets[s]])),reason:slaForm.value.reason}
  savingSla.value=true;error.value='';notice.value=''
  try{
    await recheckDuty('commercial.manage','平台身份或职责已变化，服务政策写操作已停止')
    if(!current(id,token)||props.locked)return
    const result=await api.updateSlaPolicy(id,body)
    if(!current(id,token))return
    slaEditor.value=result;notice.value='学校服务目标已保存，各级目标均按本次填写内容执行'
    await Promise.all([loadOverview(),loadAfterSales(afterPage.value),loadSla()])
  }catch(e){if(current(id,token))error.value=safeBusinessMessage(e)}
  finally{if(current(id,token))savingSla.value=false}
}
async function resetSla(){
  if(savingSla.value||props.locked||!canCommercialManage.value||!props.tenantId||!slaEditor.value?.tenantOverride?.enabled||slaForm.value.reason.length<5)return
  const id=props.tenantId,token=epoch,body={expectedVersion:slaEditor.value.tenantOverride.rowVersion,reason:slaForm.value.reason}
  savingSla.value=true;error.value='';notice.value=''
  try{
    await recheckDuty('commercial.manage','平台身份或职责已变化，服务政策写操作已停止')
    if(!current(id,token)||props.locked)return
    const result=await api.resetSlaPolicy(id,body)
    if(!current(id,token))return
    slaEditor.value=result;notice.value=result.effective?.configured?'学校服务目标已恢复为平台明确的默认政策':'学校服务目标已停用；平台未配置默认，保持未评估'
    await Promise.all([loadOverview(),loadAfterSales(afterPage.value),loadSla()])
  }catch(e){if(current(id,token))error.value=safeBusinessMessage(e)}
  finally{if(current(id,token))savingSla.value=false}
}
watch(()=>props.tenantId,()=>{
  epoch++;overviewSeq++;afterSeq++;costSeq++;slaSeq++
  overview.value=null;afterSales.value=[];costs.value=[];costSummary.value={};slaEditor.value=null
  afterPage.value=1;costPage.value=1;afterTotal.value=0;costTotal.value=0;loading.value=false;savingCost.value=false;savingSla.value=false
  costForm.value=blankCost();slaForm.value=blankSla();error.value='';notice.value='';restorePending()
  if(props.tenantId)loadAll()
},{flush:'sync'})
onMounted(async()=>{
  try{
    const result=await ensurePlatformAccessContext({force:true})
    if(disposed)return
    access.value=result
    if(!result){error.value='平台职责核验失败，售后操作已关闭';return}
    restorePending()
    if(access.value&&props.tenantId)await loadAll()
  }catch(e){if(!disposed){access.value=null;error.value=safeBusinessMessage(e,'平台职责核验失败，请重新登录')}}
})
onBeforeUnmount(()=>{disposed=true;epoch++})
</script>

<style scoped>
.ops-workspace{background:#fff;border:1px solid #dce5f0;border-radius:16px;padding:24px;display:grid;gap:16px;color:#21354e}.ops-head,.section-head,.pager,.sla-actions,.sla-form-head{display:flex;justify-content:space-between;align-items:center;gap:14px;flex-wrap:wrap}.ops-head h3{margin:5px 0;font-size:20px}.ops-head p,.section-head p,p{font-size:13px;line-height:1.6;color:#63748a;margin:5px 0}.eyebrow{font-size:11px;font-weight:700;letter-spacing:1.5px;color:#3b67a8}.metrics{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:10px}.metrics article{background:#f7f9fc;border:1px solid #e3e9f1;border-radius:10px;padding:12px}.metrics article.warn{background:#fff8eb;border-color:#fedf89}.metrics strong,.metrics span{display:block}.metrics strong{font-size:24px}.metrics span{font-size:11px;color:#6b7c92;margin-top:3px}.panel{border:1px solid #e1e7ef;border-radius:12px;padding:16px;display:grid;gap:12px}.section-head h4{margin:0}.sla-panel{background:#fbfdff}.policy-badge{font-size:12px;padding:6px 10px;border-radius:999px;background:#edf9f2;color:#246546}.policy-badge.muted{background:#f2f4f7;color:#667085}.sla-state{display:flex;gap:10px 18px;flex-wrap:wrap;font-size:12px;color:#63748a}.target-preview{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}.target-preview div{padding:10px;border-radius:8px;background:#f3f7fc}.target-preview strong,.target-preview span{display:block}.target-preview span{font-size:12px;margin-top:3px;color:#657992}.sla-form-head label{min-width:220px}.grow{flex:1}.sla-targets{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:10px 0}.sla-actions{justify-content:flex-start}.sla-actions span{font-size:11px;color:#7a8b9e}.table-scroll{overflow:auto;border:1px solid #e5eaf1;border-radius:9px}table{border-collapse:collapse;width:100%;font-size:12px}th,td{padding:11px;border-bottom:1px solid #e8edf4;text-align:left;vertical-align:top;white-space:nowrap}th{background:#f4f7fb;color:#60758f}td small{display:block;color:#7a8b9e;margin-top:4px}.form-grid{display:grid;grid-template-columns:repeat(4,minmax(120px,1fr));gap:10px;margin:10px 0}.refs{grid-template-columns:repeat(2,minmax(180px,1fr))}label{display:grid;gap:6px;font-size:12px;color:#53647d}input,select{min-height:38px;border:1px solid #ccd8e8;border-radius:7px;padding:7px 9px;font:inherit}button{min-height:36px;border:1px solid #ccd8e8;border-radius:7px;background:#fff;color:#355274;padding:7px 11px;cursor:pointer}button:disabled{opacity:.5}.primary{background:#2563eb;color:#fff;border-color:#2563eb}.notice,.success,.error,.pending,.empty,.policy{padding:11px 13px;border-radius:8px;font-size:13px}.notice,.pending{background:#fff7e8;color:#865e1c}.success{background:#edf9f2;color:#246546}.error{background:#fff0f0;color:#a93d3d}.empty{background:#f4f7fb;color:#697b94}.summary{display:flex;gap:10px;flex-wrap:wrap}.summary>div{display:flex;gap:8px;align-items:center;border:1px solid #dce5f0;border-radius:8px;padding:8px 10px;font-size:12px}.bad-text{color:#b42318}.pager{justify-content:flex-start}fieldset{border:0;padding:0;margin:0}a{color:#245fb6}@media(max-width:1100px){.metrics{grid-template-columns:repeat(3,1fr)}.form-grid,.sla-targets{grid-template-columns:repeat(2,1fr)}}@media(max-width:650px){.ops-workspace{padding:16px}.metrics,.form-grid,.refs,.sla-targets,.target-preview{grid-template-columns:1fr}.ops-head{align-items:flex-start}.sla-form-head{display:grid}.sla-form-head label{min-width:0}}
</style>
