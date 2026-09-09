<template>
  <section class="ops-workspace" aria-label="商业售后与持续治理">
    <header class="ops-head"><div><span class="eyebrow">CUSTOMER SUCCESS GOVERNANCE</span><h3>售后、SLA 与实际服务成本</h3><p>工单继续使用现有客户成功中心；这里只汇总退款后授权复核、SLA 观察、培训/续费/交付信号和真实成本。</p></div><button :disabled="loading||!tenantId" @click="loadAll">刷新治理事实</button></header>
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
      <div v-if="overview?.slaPolicy?.configured" class="policy success">SLA 已按明确政策 {{ overview.slaPolicy.version }} 观察（{{ overview.slaPolicy.source==='TENANT'?'学校覆盖':'平台默认' }}）。</div>
      <div v-else class="policy notice">当前没有有效的商业 SLA 明确政策，因此只展示已耗时，不判“达标/超时”；系统不会自行生成服务承诺。</div>

      <section class="panel"><div class="section-head"><div><h4>退款后授权复核工单</h4><p>从“退款”页已结算记录显式生成；这里读取现有 SupportTicket 的状态与时间。</p></div><router-link to="/admin/platform/customer-success">进入客户成功中心处理工单</router-link></div>
        <div class="table-scroll"><table><thead><tr><th>工单</th><th>退款 / 订单</th><th>模块快照</th><th>状态</th><th>SLA</th></tr></thead><tbody>
          <tr v-for="row in afterSales" :key="row.linkId"><td>#{{ row.supportTicketId }} · {{ row.ticket.title }}<small>{{ row.ticket.severity }} · {{ showTime(row.ticket.createdAt) }}</small></td><td>退款 #{{ row.refundCaseId }}<small>订单 #{{ row.orderId }}</small></td><td>{{ modulesText(row.moduleSnapshot) }}</td><td>{{ ticketStatus(row.ticket.status) }}</td><td :class="row.sla.status==='BREACHED'?'bad-text':''">{{ slaText(row.sla) }}</td></tr>
          <tr v-if="!afterSales.length&&!loading"><td colspan="5">暂无退款后授权复核工单。</td></tr>
        </tbody></table></div>
        <div class="pager"><button :disabled="afterPage===1||loading" @click="loadAfterSales(afterPage-1)">上一页</button><span>共 {{ afterTotal }} 条</span><button :disabled="afterPage*20>=afterTotal||loading" @click="loadAfterSales(afterPage+1)">下一页</button></div>
      </section>

      <section class="panel cost-panel"><div class="section-head"><div><h4>登记实际服务成本</h4><p>只登记已实际发生的支持、交付、培训、退款手续费等成本；不同币种永不自动换算或合计。</p></div></div>
        <div v-if="costPending" class="pending"><strong>上次成本登记结果仍需核对</strong><p>原请求与幂等键已保留，请重试原请求。</p><button class="primary" :disabled="savingCost||!canManage" @click="submitCost">重试原请求</button></div>
        <fieldset :disabled="savingCost||locked||!canManage||!!costPending">
          <div class="form-grid"><label>成本类型<select v-model="costForm.costType"><option value="">请选择</option><option value="SUPPORT">支持</option><option value="DELIVERY">交付</option><option value="TRAINING">培训</option><option value="REFUND_FEE">退款手续费</option><option value="OTHER">其他</option></select></label><label>金额<input v-model.trim="costForm.amount" inputmode="decimal" placeholder="0.00"></label><label>币种<input v-model.trim="costForm.currency" maxlength="3" placeholder="如 CNY"></label><label>发生时间<input v-model="costForm.occurredAt" type="datetime-local" step="1"></label></div>
          <div class="form-grid refs"><label>关联售后工单<select v-model="costForm.afterSalesLink" @change="useAfterSales"><option value="">不从退款售后工单带入</option><option v-for="row in afterSales" :key="row.linkId" :value="row.linkId">工单 #{{ row.supportTicketId }} · 退款 #{{ row.refundCaseId }}</option></select></label><label>订单 ID<input v-model.trim="costForm.orderId" inputmode="numeric" placeholder="至少关联订单/退款/工单一个对象"></label><label>退款记录 ID<input v-model.trim="costForm.refundCaseId" inputmode="numeric"></label><label>工单 ID<input v-model.trim="costForm.supportTicketId" inputmode="numeric"></label></div>
          <div class="form-grid refs"><label>外部凭据<input v-model.trim="costForm.externalRef" maxlength="160" placeholder="工资、采购、渠道手续费等真实凭据编号（可选）"></label><label>说明<input v-model.trim="costForm.note" maxlength="500" placeholder="说明实际成本来源"></label></div>
          <button class="primary" :disabled="!costReady" @click="submitCost">{{ savingCost?'正在登记…':'登记实际成本' }}</button>
        </fieldset>
        <div v-if="Object.keys(costSummary).length" class="summary"><div v-for="(rows,currency) in costSummary" :key="currency"><strong>{{ currency }}</strong><span v-for="row in rows" :key="row.costType">{{ costTypeLabel(row.costType) }} {{ row.amount }}（{{ row.count }}笔）</span></div></div>
        <div class="table-scroll"><table><thead><tr><th>发生时间</th><th>类型</th><th>金额</th><th>关联</th><th>凭据 / 说明</th></tr></thead><tbody><tr v-for="row in costs" :key="row.costId"><td>{{ showTime(row.occurredAt) }}</td><td>{{ costTypeLabel(row.costType) }}</td><td>{{ row.currency }} {{ row.amount }}</td><td>订单 {{ row.orderId||'—' }}<small>退款 {{ row.refundCaseId||'—' }} · 工单 {{ row.supportTicketId||'—' }}</small></td><td>{{ row.externalRef||'—' }}<small>{{ row.note||'' }}</small></td></tr><tr v-if="!costs.length&&!loading"><td colspan="5">暂无实际服务成本记录。</td></tr></tbody></table></div>
        <div class="pager"><button :disabled="costPage===1||loading" @click="loadCosts(costPage-1)">上一页</button><span>共 {{ costTotal }} 条</span><button :disabled="costPage*20>=costTotal||loading" @click="loadCosts(costPage+1)">下一页</button></div>
      </section>
      <p v-if="!canManage" class="notice">当前职责没有 order.manage，只能查看售后、SLA 与成本事实。</p>
    </template>
  </section>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { moduleCommerceApi as api } from '@/modules/platform/api/moduleCommerce.api'
import { ensurePlatformAccessContext } from '@/security/platformAccessGate'
import { isDefinitiveRejection } from '../../lib/moduleCommerceSales.mjs'

const props=defineProps({tenantId:{type:String,default:''},locked:Boolean})
const access=ref(null),overview=ref(null),afterSales=ref([]),afterPage=ref(1),afterTotal=ref(0),costs=ref([]),costPage=ref(1),costTotal=ref(0),costSummary=ref({}),loading=ref(false),savingCost=ref(false),error=ref(''),notice=ref(''),costPending=ref(null)
const blankCost=()=>({costType:'',amount:'',currency:'',occurredAt:'',afterSalesLink:'',orderId:'',refundCaseId:'',supportTicketId:'',externalRef:'',note:''})
const costForm=ref(blankCost())
const canManage=computed(()=>!!access.value?.duties?.some(d=>['*','order.manage'].includes(d)))
const moneyOk=v=>/^\d+(?:\.\d{1,2})?$/.test(String(v||''))&&Number(v)>0
const refsOk=computed(()=>[costForm.value.orderId,costForm.value.refundCaseId,costForm.value.supportTicketId].some(v=>/^\d+$/.test(String(v||''))))
const costReady=computed(()=>canManage.value&&!savingCost.value&&!props.locked&&!costPending.value&&['SUPPORT','DELIVERY','TRAINING','REFUND_FEE','OTHER'].includes(costForm.value.costType)&&moneyOk(costForm.value.amount)&&/^[A-Za-z]{3}$/.test(costForm.value.currency)&&!!costForm.value.occurredAt&&refsOk.value)
function showTime(v){return v?String(v).replace('T',' ').slice(0,19):'—'}
function modulesText(rows){return(rows||[]).map(r=>`${r.moduleKey} ×${r.sourceCount}`).join('、')||'—'}
function ticketStatus(v){return({OPEN:'待处理',IN_PROGRESS:'处理中',RESOLVED:'已解决',CLOSED:'已关闭'})[v]||v||'—'}
function slaText(sla){if(!sla?.policyConfigured)return`已耗时 ${sla?.elapsedHours??0}h · 未配置SLA`;return`${sla.status==='BREACHED'?'已超目标':'目标内'} · ${sla.elapsedHours}h / ${sla.targetHours}h`}
function costTypeLabel(v){return({SUPPORT:'支持',DELIVERY:'交付',TRAINING:'培训',REFUND_FEE:'退款手续费',OTHER:'其他'})[v]||v}
function storageKey(){return`gx_module_service_cost_pending_v1:${access.value?.subjectId||''}:${props.tenantId}`}
function newKey(){const s=globalThis.crypto?.randomUUID?.()||`${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;return`m8-cost-${s}`.slice(0,160)}
function savePending(v){costPending.value=v;try{v?sessionStorage.setItem(storageKey(),JSON.stringify(v)):sessionStorage.removeItem(storageKey())}catch{/* memory fallback */}}
function restorePending(){costPending.value=null;if(!access.value?.subjectId||!props.tenantId)return;try{const raw=sessionStorage.getItem(storageKey());const p=raw?JSON.parse(raw):null;if(p?.tenantId===props.tenantId&&p.key&&p.body)costPending.value=p}catch{savePending(null)}}
async function recheck(){const current=await ensurePlatformAccessContext({force:true});if(!current||String(current.subjectId)!==String(access.value?.subjectId)||!current.duties?.some(d=>['*','order.manage'].includes(d)))throw new Error('平台身份或职责已变化，成本写操作已停止')}
async function loadOverview(){overview.value=await api.getOperationsOverview(props.tenantId)}
async function loadAfterSales(page=1){const d=await api.listAfterSales(props.tenantId,{page,pageSize:20});afterSales.value=d.items||[];afterTotal.value=d.total||0;afterPage.value=page}
async function loadCosts(page=1){const d=await api.listServiceCosts(props.tenantId,{page,pageSize:20});costs.value=d.items||[];costTotal.value=d.total||0;costPage.value=page;costSummary.value=d.summaryByCurrency||{}}
async function loadAll(){if(!props.tenantId)return;loading.value=true;error.value='';try{await Promise.all([loadOverview(),loadAfterSales(afterPage.value),loadCosts(costPage.value)])}catch(e){error.value=e.message}finally{loading.value=false}}
function useAfterSales(){const row=afterSales.value.find(r=>r.linkId===costForm.value.afterSalesLink);if(!row)return;costForm.value.orderId=row.orderId;costForm.value.refundCaseId=row.refundCaseId;costForm.value.supportTicketId=row.supportTicketId}
async function submitCost(){if(savingCost.value||!canManage.value)return;savingCost.value=true;error.value='';notice.value='';try{await recheck();let attempt=costPending.value;if(!attempt){const local=costForm.value.occurredAt;const date=new Date(local);if(!Number.isFinite(date.getTime()))throw new Error('发生时间无效');const body={costType:costForm.value.costType,amount:costForm.value.amount,currency:costForm.value.currency.toUpperCase(),occurredAt:date.toISOString(),orderId:costForm.value.orderId||null,refundCaseId:costForm.value.refundCaseId||null,supportTicketId:costForm.value.supportTicketId||null,externalRef:costForm.value.externalRef,note:costForm.value.note};attempt={tenantId:props.tenantId,key:newKey(),body};savePending(attempt)}await api.recordServiceCost(props.tenantId,attempt.body,attempt.key);savePending(null);costForm.value=blankCost();notice.value='实际服务成本已登记；不同币种仍分开汇总，未做换算';await Promise.all([loadCosts(1),loadOverview()])}catch(e){error.value=e.message||'登记结果不明，请重试原请求';if(isDefinitiveRejection(e))savePending(null)}finally{savingCost.value=false}}
watch(()=>props.tenantId,()=>{overview.value=null;afterSales.value=[];costs.value=[];afterPage.value=1;costPage.value=1;costForm.value=blankCost();error.value='';notice.value='';restorePending();if(props.tenantId)loadAll()})
onMounted(async()=>{access.value=await ensurePlatformAccessContext({force:true});restorePending();if(props.tenantId)await loadAll()})
</script>

<style scoped>
.ops-workspace{background:#fff;border:1px solid #dce5f0;border-radius:16px;padding:24px;display:grid;gap:16px;color:#21354e}.ops-head,.section-head,.pager{display:flex;justify-content:space-between;align-items:center;gap:14px;flex-wrap:wrap}.ops-head h3{margin:5px 0;font-size:20px}.ops-head p,.section-head p,p{font-size:13px;line-height:1.6;color:#63748a;margin:5px 0}.eyebrow{font-size:11px;font-weight:700;letter-spacing:1.5px;color:#3b67a8}.metrics{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:10px}.metrics article{background:#f7f9fc;border:1px solid #e3e9f1;border-radius:10px;padding:12px}.metrics article.warn{background:#fff8eb;border-color:#fedf89}.metrics strong,.metrics span{display:block}.metrics strong{font-size:24px}.metrics span{font-size:11px;color:#6b7c92;margin-top:3px}.panel{border:1px solid #e1e7ef;border-radius:12px;padding:16px;display:grid;gap:12px}.section-head h4{margin:0}.table-scroll{overflow:auto;border:1px solid #e5eaf1;border-radius:9px}table{border-collapse:collapse;width:100%;font-size:12px}th,td{padding:11px;border-bottom:1px solid #e8edf4;text-align:left;vertical-align:top;white-space:nowrap}th{background:#f4f7fb;color:#60758f}td small{display:block;color:#7a8b9e;margin-top:4px}.form-grid{display:grid;grid-template-columns:repeat(4,minmax(120px,1fr));gap:10px;margin:10px 0}.refs{grid-template-columns:repeat(2,minmax(180px,1fr))}label{display:grid;gap:6px;font-size:12px;color:#53647d}input,select{min-height:38px;border:1px solid #ccd8e8;border-radius:7px;padding:7px 9px;font:inherit}button{min-height:36px;border:1px solid #ccd8e8;border-radius:7px;background:#fff;color:#355274;padding:7px 11px;cursor:pointer}button:disabled{opacity:.5}.primary{background:#2563eb;color:#fff;border-color:#2563eb}.notice,.success,.error,.pending,.empty,.policy{padding:11px 13px;border-radius:8px;font-size:13px}.notice,.pending{background:#fff7e8;color:#865e1c}.success{background:#edf9f2;color:#246546}.error{background:#fff0f0;color:#a93d3d}.empty{background:#f4f7fb;color:#697b94}.summary{display:flex;gap:10px;flex-wrap:wrap}.summary>div{display:flex;gap:8px;align-items:center;border:1px solid #dce5f0;border-radius:8px;padding:8px 10px;font-size:12px}.bad-text{color:#b42318}.pager{justify-content:flex-start}fieldset{border:0;padding:0;margin:0}a{color:#245fb6}@media(max-width:1100px){.metrics{grid-template-columns:repeat(3,1fr)}.form-grid{grid-template-columns:repeat(2,1fr)}}@media(max-width:650px){.ops-workspace{padding:16px}.metrics,.form-grid,.refs{grid-template-columns:1fr}.ops-head{align-items:flex-start}}
</style>
