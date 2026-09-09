<template>
  <section class="finance-workspace" aria-label="商业财务工作区">
    <header class="finance-heading">
      <div>
        <span class="eyebrow">FINANCE CONTROL</span>
        <h3>应收、退款与发票</h3>
        <p>应收直接读取原订单；退款与发票只记录人工办理事实。系统不自动退款、不自动开票，也不自动停用学校已购模块。</p>
      </div>
      <div class="heading-actions">
        <span class="badge">M8 · 人工凭据闭环</span>
        <button :disabled="loading || !tenantId" @click="reloadCurrent">刷新财务事实</button>
      </div>
    </header>

    <div v-if="!tenantId" class="empty">先在上方销售工作区选择学校，再办理该校财务事项。</div>
    <template v-else>
      <div class="tabs" role="tablist" aria-label="财务办理步骤">
        <button v-for="item in tabs" :key="item.key" role="tab" :aria-selected="tab===item.key" @click="selectTab(item.key)">{{ item.label }}</button>
      </div>
      <p v-if="error" class="error" role="alert">{{ error }}</p>
      <p v-if="notice" class="success" role="status">{{ notice }}</p>
      <div v-if="pendingCommand" class="pending" role="status">
        <strong>上次{{ pendingCommand.kind==='refund' ? '退款' : '发票' }}申请结果仍需核对</strong>
        <p>原请求与幂等键已保留。请重试原请求，不要重新填写第二份申请。</p>
        <button class="primary" :disabled="sending || !canManage" @click="retryPending">{{ sending ? '正在核对原请求…' : '重试原请求' }}</button>
      </div>

      <section v-show="tab==='overview'" class="tab-panel">
        <div class="section-head"><div><h4>订单实时资金投影</h4><p>没有第二张“应收余额表”；金额始终从 PlatformOrder 及退款/发票控制事实派生。</p></div></div>
        <div v-if="loading" class="empty">正在读取真实订单资金事实…</div>
        <div v-else class="table-scroll">
          <table>
            <thead><tr><th>订单</th><th>成交 / 已收</th><th>未收应收</th><th>退款</th><th>发票</th><th>可办理余额</th><th>操作</th></tr></thead>
            <tbody>
              <tr v-for="row in orders" :key="row.orderId">
                <td><strong>{{ row.orderNo }}</strong><small>{{ orderStatus(row.orderStatus) }} · {{ row.orderType }}</small></td>
                <td>¥ {{ row.amount }}<small>已收 ¥ {{ row.paidAmount }}</small></td>
                <td><strong :class="Number(row.outstandingAmount)>0?'warn-text':'ok-text'">¥ {{ row.outstandingAmount }}</strong></td>
                <td>已结算 ¥ {{ row.refundSettledAmount }}<small>已批准 ¥ {{ row.refundApprovedAmount }}</small></td>
                <td>已开 ¥ {{ row.invoiceIssuedAmount }}<small>申请中 ¥ {{ row.invoiceRequestedAmount }}</small></td>
                <td><strong>¥ {{ row.availableFinanceCapacity }}</strong><small>退款/发票共享额度</small></td>
                <td class="row-actions"><button :disabled="!canManage || locked" @click="startRefund(row)">申请退款</button><button :disabled="!canManage || locked" @click="startInvoice(row)">申请发票</button></td>
              </tr>
              <tr v-if="!orders.length"><td colspan="7">当前学校没有可展示订单。</td></tr>
            </tbody>
          </table>
        </div>
        <div class="pager"><button :disabled="loading || orderPage===1" @click="loadOrders(orderPage-1)">上一页</button><span>共 {{ orderTotal }} 张 · 第 {{ orderPage }} 页</span><button :disabled="loading || orderPage*20>=orderTotal" @click="loadOrders(orderPage+1)">下一页</button></div>
      </section>

      <section v-show="tab==='refunds'" class="tab-panel">
        <div class="split">
          <article class="form-card">
            <h4>发起退款申请</h4>
            <p>这里只申请退款额度；批准后仍需在外部资金渠道完成退款，再回来登记结算凭据。</p>
            <fieldset :disabled="!canManage || sending || locked || !!pendingCommand">
              <label>订单 ID<input v-model.trim="refundForm.orderId" inputmode="numeric" placeholder="从资金总览点“申请退款”自动带入"></label>
              <div class="two-col"><label>退款金额<input v-model.trim="refundForm.amount" inputmode="decimal" placeholder="0.00"></label><label>币种<input v-model.trim="refundForm.currency" maxlength="3"></label></div>
              <label>退款原因<textarea v-model.trim="refundForm.reason" minlength="10" maxlength="500" placeholder="至少10个字符，写清合同、未使用服务或其他依据"></textarea></label>
              <button class="primary" :disabled="!refundReady" @click="submitRefund">{{ sending ? '正在登记…' : '登记退款申请（不执行退款）' }}</button>
            </fieldset>
          </article>
          <article class="form-card">
            <h4>退款办理</h4>
            <div v-if="!selectedRefund" class="empty">从下方退款台账选择一条记录。</div>
            <template v-else>
              <div class="case-summary"><strong>{{ selectedRefund.caseNo }}</strong><span>{{ refundStatus(selectedRefund.status) }} · ¥ {{ selectedRefund.amount }}</span></div>
              <template v-if="selectedRefund.status==='REQUESTED'">
                <label>审批说明<input v-model.trim="refundAction.note" maxlength="500" placeholder="批准时写合同/财务复核结论"></label>
                <label>驳回原因<input v-model.trim="refundAction.rejectReason" maxlength="500" placeholder="驳回时至少5个字符"></label>
                <div class="button-row"><button class="primary" :disabled="sending||refundAction.note.length<5" @click="approveSelectedRefund">批准额度</button><button :disabled="sending||refundAction.rejectReason.length<5" @click="rejectSelectedRefund">驳回申请</button></div>
              </template>
              <template v-else-if="selectedRefund.status==='APPROVED'">
                <label>外部退款凭据<input v-model.trim="refundAction.settlementRef" maxlength="160" placeholder="如银行/微信/支付宝退款流水号"></label>
                <button class="primary" :disabled="sending||refundAction.settlementRef.length<6" @click="settleSelectedRefund">登记外部退款已完成</button>
                <p class="notice">登记结算不会自动修改订单支付状态，也不会自动停止模块授权。</p>
              </template>
              <div v-else class="empty">此退款记录已处于终态，无需重复办理。</div>
            </template>
          </article>
        </div>
        <div class="ledger-head"><h4>退款台账</h4><label>状态<select v-model="refundStatusFilter" @change="loadRefunds(1)"><option value="">全部</option><option value="REQUESTED">待审批</option><option value="APPROVED">已批准待结算</option><option value="REJECTED">已驳回</option><option value="SETTLED">已结算</option></select></label><button :disabled="refundsLoading" @click="loadRefunds(refundPage)">刷新</button></div>
        <div class="table-scroll"><table><thead><tr><th>申请单</th><th>订单</th><th>金额</th><th>状态</th><th>外部凭据</th><th>操作</th></tr></thead><tbody><tr v-for="row in refunds" :key="row.caseId"><td>{{ row.caseNo }}<small>{{ showTime(row.requestedAt) }}</small></td><td>#{{ row.orderId }}</td><td>{{ row.currency }} {{ row.amount }}</td><td>{{ refundStatus(row.status) }}</td><td>{{ row.settlementRef || '—' }}</td><td><button @click="selectRefund(row)">办理 / 查看</button></td></tr><tr v-if="!refunds.length&&!refundsLoading"><td colspan="6">暂无退款记录</td></tr></tbody></table></div>
        <div class="pager"><button :disabled="refundsLoading||refundPage===1" @click="loadRefunds(refundPage-1)">上一页</button><span>共 {{ refundTotal }} 条</span><button :disabled="refundsLoading||refundPage*20>=refundTotal" @click="loadRefunds(refundPage+1)">下一页</button></div>
      </section>

      <section v-show="tab==='invoices'" class="tab-panel">
        <div class="split">
          <article class="form-card">
            <h4>发起发票申请</h4>
            <p>申请只占用可办理金额；系统不会调用税控或第三方开票服务。</p>
            <fieldset :disabled="!canManage || sending || locked || !!pendingCommand">
              <label>订单 ID<input v-model.trim="invoiceForm.orderId" inputmode="numeric" placeholder="从资金总览点“申请发票”自动带入"></label>
              <div class="two-col"><label>开票金额<input v-model.trim="invoiceForm.amount" inputmode="decimal" placeholder="0.00"></label><label>币种<input v-model.trim="invoiceForm.currency" maxlength="3"></label></div>
              <label>发票抬头<input v-model.trim="invoiceForm.invoiceTitle" minlength="2" maxlength="200" placeholder="学校或合同约定开票主体"></label>
              <button class="primary" :disabled="!invoiceReady" @click="submitInvoice">{{ sending ? '正在登记…' : '登记发票申请（不自动开票）' }}</button>
            </fieldset>
          </article>
          <article class="form-card">
            <h4>发票办理</h4>
            <div v-if="!selectedInvoice" class="empty">从下方发票台账选择一条记录。</div>
            <template v-else>
              <div class="case-summary"><strong>{{ selectedInvoice.requestNo }}</strong><span>{{ invoiceStatus(selectedInvoice.status) }} · ¥ {{ selectedInvoice.amount }}</span></div>
              <template v-if="selectedInvoice.status==='REQUESTED'">
                <label>外部发票凭据<input v-model.trim="invoiceAction.externalRef" maxlength="160" placeholder="税控/第三方平台返回的发票号或业务凭据"></label>
                <button class="primary" :disabled="sending||invoiceAction.externalRef.length<6" @click="issueSelectedInvoice">登记外部发票已开具</button>
                <p class="notice">不要求手填数据库文件 ID；发票文件后续应通过文件中心正式关联。</p>
              </template>
              <template v-else-if="selectedInvoice.status==='ISSUED'">
                <label>外部作废依据<input v-model.trim="invoiceAction.voidReason" maxlength="500" placeholder="至少5个字符，确认外部发票已经作废后再登记"></label>
                <button :disabled="sending||invoiceAction.voidReason.length<5" @click="voidSelectedInvoice">登记外部发票已作废</button>
              </template>
              <div v-else class="empty">此发票记录已处于终态，无需重复办理。</div>
            </template>
          </article>
        </div>
        <div class="ledger-head"><h4>发票台账</h4><label>状态<select v-model="invoiceStatusFilter" @change="loadInvoices(1)"><option value="">全部</option><option value="REQUESTED">待开具</option><option value="ISSUED">已开具</option><option value="VOIDED">已作废</option></select></label><button :disabled="invoicesLoading" @click="loadInvoices(invoicePage)">刷新</button></div>
        <div class="table-scroll"><table><thead><tr><th>申请单</th><th>订单</th><th>抬头</th><th>金额</th><th>状态</th><th>外部凭据</th><th>操作</th></tr></thead><tbody><tr v-for="row in invoices" :key="row.invoiceCaseId"><td>{{ row.requestNo }}<small>{{ showTime(row.requestedAt) }}</small></td><td>#{{ row.orderId }}</td><td>{{ row.invoiceTitle }}</td><td>{{ row.currency }} {{ row.amount }}</td><td>{{ invoiceStatus(row.status) }}</td><td>{{ row.externalInvoiceRef || '—' }}</td><td><button @click="selectInvoice(row)">办理 / 查看</button></td></tr><tr v-if="!invoices.length&&!invoicesLoading"><td colspan="7">暂无发票记录</td></tr></tbody></table></div>
        <div class="pager"><button :disabled="invoicesLoading||invoicePage===1" @click="loadInvoices(invoicePage-1)">上一页</button><span>共 {{ invoiceTotal }} 条</span><button :disabled="invoicesLoading||invoicePage*20>=invoiceTotal" @click="loadInvoices(invoicePage+1)">下一页</button></div>
      </section>

      <p v-if="!canManage" class="notice">当前平台职责没有 order.manage，只能查看资金、退款和发票台账；后端仍会逐请求复核职责。</p>
    </template>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { moduleCommerceApi as api } from '@/modules/platform/api/moduleCommerce.api'
import { ensurePlatformAccessContext } from '@/security/platformAccessGate'
import { isDefinitiveRejection } from '../../lib/moduleCommerceSales.mjs'

const props = defineProps({ tenantId:{type:String,default:''}, locked:Boolean })
const tabs=[{key:'overview',label:'资金总览'},{key:'refunds',label:'退款'},{key:'invoices',label:'发票'}]
const tab=ref('overview'), access=ref(null), error=ref(''), notice=ref(''), sending=ref(false), pendingCommand=ref(null)
const orders=ref([]), orderPage=ref(1), orderTotal=ref(0), loading=ref(false)
const refunds=ref([]), refundPage=ref(1), refundTotal=ref(0), refundsLoading=ref(false), refundStatusFilter=ref(''), selectedRefund=ref(null)
const invoices=ref([]), invoicePage=ref(1), invoiceTotal=ref(0), invoicesLoading=ref(false), invoiceStatusFilter=ref(''), selectedInvoice=ref(null)
const refundForm=ref({orderId:'',amount:'',currency:'CNY',reason:''})
const invoiceForm=ref({orderId:'',amount:'',currency:'CNY',invoiceTitle:''})
const refundAction=ref({note:'',rejectReason:'',settlementRef:''})
const invoiceAction=ref({externalRef:'',voidReason:''})
let epoch=0

const canManage=computed(()=>!!access.value?.duties?.some(d=>['*','order.manage'].includes(d)))
const moneyOk=(value)=>/^\d+(?:\.\d{1,2})?$/.test(String(value||''))&&Number(value)>0
const refundReady=computed(()=>canManage.value&&!sending.value&&!props.locked&&!pendingCommand.value&&/^\d+$/.test(refundForm.value.orderId)&&moneyOk(refundForm.value.amount)&&/^[A-Za-z]{3}$/.test(refundForm.value.currency)&&refundForm.value.reason.length>=10)
const invoiceReady=computed(()=>canManage.value&&!sending.value&&!props.locked&&!pendingCommand.value&&/^\d+$/.test(invoiceForm.value.orderId)&&moneyOk(invoiceForm.value.amount)&&/^[A-Za-z]{3}$/.test(invoiceForm.value.currency)&&invoiceForm.value.invoiceTitle.length>=2)

function showTime(v){return v?String(v).replace('T',' ').slice(0,19):'—'}
function orderStatus(v){return({paid:'已支付',unpaid:'未支付',cancelled:'已取消',refunded:'历史已退款'})[v]||v||'—'}
function refundStatus(v){return({REQUESTED:'待审批',APPROVED:'已批准待结算',REJECTED:'已驳回',SETTLED:'已结算'})[v]||v||'—'}
function invoiceStatus(v){return({REQUESTED:'待开具',ISSUED:'已开具',VOIDED:'已作废'})[v]||v||'—'}
function newKey(kind){const suffix=globalThis.crypto?.randomUUID?.()||`${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;return `m8-${kind}-${suffix}`.slice(0,160)}
function storageKey(){return `gx_module_finance_pending_v1:${access.value?.subjectId||''}:${props.tenantId}`}
function savePending(value){pendingCommand.value=value;try{value?sessionStorage.setItem(storageKey(),JSON.stringify(value)):sessionStorage.removeItem(storageKey())}catch{/* memory-only fallback */}}
function loadPending(){pendingCommand.value=null;if(!props.tenantId||!access.value?.subjectId)return;try{const raw=sessionStorage.getItem(storageKey());if(!raw)return;const parsed=JSON.parse(raw);if(parsed?.tenantId===props.tenantId&&['refund','invoice'].includes(parsed.kind)&&parsed.key&&parsed.body)pendingCommand.value=parsed}catch{savePending(null)}}
async function recheckAccess(){const current=await ensurePlatformAccessContext({force:true});if(!current||String(current.subjectId)!==String(access.value?.subjectId)||!current.duties?.some(d=>['*','order.manage'].includes(d)))throw new Error('平台身份或职责已变化，财务写操作已停止；请刷新身份后重试')}
function clearMessage(){error.value='';notice.value=''}

async function loadOrders(page=1){const id=props.tenantId,token=epoch;orders.value=[];orderTotal.value=0;loading.value=!!id;if(!id)return;try{const data=await api.listFinanceOrders(id,{page,pageSize:20});if(token!==epoch||id!==props.tenantId)return;orders.value=data.items||[];orderTotal.value=data.total||0;orderPage.value=page}catch(e){if(token===epoch)error.value=e.message}finally{if(token===epoch)loading.value=false}}
async function loadRefunds(page=1){const id=props.tenantId,token=epoch;refundsLoading.value=!!id;if(!id)return;try{const data=await api.listRefunds(id,{status:refundStatusFilter.value,page,pageSize:20});if(token!==epoch||id!==props.tenantId)return;refunds.value=data.items||[];refundTotal.value=data.total||0;refundPage.value=page;if(selectedRefund.value){selectedRefund.value=refunds.value.find(r=>r.caseId===selectedRefund.value.caseId)||null}}catch(e){if(token===epoch)error.value=e.message}finally{if(token===epoch)refundsLoading.value=false}}
async function loadInvoices(page=1){const id=props.tenantId,token=epoch;invoicesLoading.value=!!id;if(!id)return;try{const data=await api.listInvoices(id,{status:invoiceStatusFilter.value,page,pageSize:20});if(token!==epoch||id!==props.tenantId)return;invoices.value=data.items||[];invoiceTotal.value=data.total||0;invoicePage.value=page;if(selectedInvoice.value){selectedInvoice.value=invoices.value.find(r=>r.invoiceCaseId===selectedInvoice.value.invoiceCaseId)||null}}catch(e){if(token===epoch)error.value=e.message}finally{if(token===epoch)invoicesLoading.value=false}}
async function reloadCurrent(){clearMessage();if(tab.value==='overview')await loadOrders(orderPage.value);else if(tab.value==='refunds')await loadRefunds(refundPage.value);else await loadInvoices(invoicePage.value)}
async function selectTab(key){tab.value=key;clearMessage();if(key==='overview')await loadOrders(1);if(key==='refunds')await loadRefunds(1);if(key==='invoices')await loadInvoices(1)}

function startRefund(row){refundForm.value={orderId:String(row.orderId),amount:row.availableFinanceCapacity,currency:'CNY',reason:''};tab.value='refunds';loadRefunds(1)}
function startInvoice(row){invoiceForm.value={orderId:String(row.orderId),amount:row.availableFinanceCapacity,currency:'CNY',invoiceTitle:''};tab.value='invoices';loadInvoices(1)}
function selectRefund(row){selectedRefund.value={...row};refundAction.value={note:'',rejectReason:'',settlementRef:''}}
function selectInvoice(row){selectedInvoice.value={...row};invoiceAction.value={externalRef:'',voidReason:''}}

async function submitRequest(kind, body){if(sending.value||!canManage.value)return;sending.value=true;clearMessage();const token=epoch;try{await recheckAccess();let attempt=pendingCommand.value;if(!attempt){attempt={tenantId:props.tenantId,kind,key:newKey(kind),body:{...body}};savePending(attempt)}const result=kind==='refund'?await api.requestRefund(props.tenantId,attempt.body,attempt.key):await api.requestInvoice(props.tenantId,attempt.body,attempt.key);if(token!==epoch)return;savePending(null);notice.value=kind==='refund'?'退款申请已登记；系统未执行资金退款，也未改变模块授权':'发票申请已登记；系统未调用税控或第三方开票服务';if(kind==='refund'){refundForm.value={orderId:'',amount:'',currency:'CNY',reason:''};await Promise.all([loadRefunds(1),loadOrders(1)])}else{invoiceForm.value={orderId:'',amount:'',currency:'CNY',invoiceTitle:''};await Promise.all([loadInvoices(1),loadOrders(1)])}return result}catch(e){if(token!==epoch)return;error.value=e.message||'请求结果不明，请重试原请求';if(isDefinitiveRejection(e))savePending(null)}finally{sending.value=false}}
async function submitRefund(){if(refundReady.value)await submitRequest('refund',{orderId:refundForm.value.orderId,amount:refundForm.value.amount,currency:refundForm.value.currency.toUpperCase(),reason:refundForm.value.reason})}
async function submitInvoice(){if(invoiceReady.value)await submitRequest('invoice',{orderId:invoiceForm.value.orderId,amount:invoiceForm.value.amount,currency:invoiceForm.value.currency.toUpperCase(),invoiceTitle:invoiceForm.value.invoiceTitle})}
async function retryPending(){if(!pendingCommand.value)return;await submitRequest(pendingCommand.value.kind,pendingCommand.value.body)}

async function mutate(call, successText, reload){if(sending.value||!canManage.value)return;sending.value=true;clearMessage();const token=epoch;try{await recheckAccess();const result=await call();if(token!==epoch)return;notice.value=successText;await Promise.all([reload(),loadOrders(orderPage.value)]);return result}catch(e){if(token===epoch)error.value=e.message}finally{sending.value=false}}
async function approveSelectedRefund(){const row=selectedRefund.value;if(!row)return;const result=await mutate(()=>api.approveRefund(props.tenantId,row.caseId,{expectedVersion:row.version,note:refundAction.value.note}),'退款额度已批准；仍未执行外部退款',()=>loadRefunds(refundPage.value));if(result?.entitlementImpact?.followUpRequired)notice.value+='；该订单仍有有效模块授权来源，退款结算后还需人工办理售后授权处置'}
async function rejectSelectedRefund(){const row=selectedRefund.value;if(!row)return;await mutate(()=>api.rejectRefund(props.tenantId,row.caseId,{expectedVersion:row.version,reason:refundAction.value.rejectReason}),'退款申请已驳回',()=>loadRefunds(refundPage.value))}
async function settleSelectedRefund(){const row=selectedRefund.value;if(!row)return;const result=await mutate(()=>api.settleRefund(props.tenantId,row.caseId,{expectedVersion:row.version,settlementRef:refundAction.value.settlementRef}),'外部退款凭据已登记；订单支付真值未自动修改',()=>loadRefunds(refundPage.value));if(result?.entitlementImpact?.followUpRequired)notice.value+='；仍存在有效模块来源，必须继续人工处理售后授权，不得把退款等同于停权'}
async function issueSelectedInvoice(){const row=selectedInvoice.value;if(!row)return;await mutate(()=>api.issueInvoice(props.tenantId,row.invoiceCaseId,{expectedVersion:row.version,externalInvoiceRef:invoiceAction.value.externalRef}),'外部发票凭据已登记；系统未执行开票动作',()=>loadInvoices(invoicePage.value))}
async function voidSelectedInvoice(){const row=selectedInvoice.value;if(!row)return;await mutate(()=>api.voidInvoice(props.tenantId,row.invoiceCaseId,{expectedVersion:row.version,reason:invoiceAction.value.voidReason}),'外部发票作废事实已登记',()=>loadInvoices(invoicePage.value))}

watch(()=>props.tenantId,()=>{epoch++;orders.value=[];refunds.value=[];invoices.value=[];selectedRefund.value=null;selectedInvoice.value=null;refundForm.value={orderId:'',amount:'',currency:'CNY',reason:''};invoiceForm.value={orderId:'',amount:'',currency:'CNY',invoiceTitle:''};clearMessage();loadPending();if(props.tenantId)loadOrders(1)})
onMounted(async()=>{access.value=await ensurePlatformAccessContext({force:true});if(!access.value)error.value='平台职责核验失败，商业财务写操作已关闭';loadPending();if(props.tenantId)await loadOrders(1)})
onBeforeUnmount(()=>{epoch++})
</script>

<style scoped>
.finance-workspace{background:#fff;border:1px solid #dce5f0;border-radius:16px;padding:24px;color:#21354e;display:grid;gap:18px}.finance-heading,.heading-actions,.section-head,.ledger-head,.button-row{display:flex;align-items:center;justify-content:space-between;gap:14px;flex-wrap:wrap}.finance-heading h3{font-size:21px;margin:6px 0}.finance-heading p,.form-card p,.section-head p,p{line-height:1.65;color:#63748a;margin:7px 0;font-size:13px}.eyebrow{font-size:11px;font-weight:700;letter-spacing:1.5px;color:#3b67a8}.badge{font-size:12px;border-radius:20px;padding:8px 12px;background:#edf5ff;color:#265ea7}.tabs{display:flex;gap:6px;border-bottom:1px solid #dce5f0;padding-bottom:10px}.tabs button[aria-selected=true]{background:#edf4ff;border-color:#a5bde4;color:#245aa8;font-weight:700}.tab-panel{display:grid;gap:14px}.split{display:grid;grid-template-columns:1fr 1fr;gap:14px}.form-card{border:1px solid #dde6f1;background:#fbfdff;border-radius:12px;padding:18px;display:grid;gap:12px}.form-card h4,.ledger-head h4,.section-head h4{margin:0;font-size:16px}.two-col{display:grid;grid-template-columns:1fr 1fr;gap:12px}label{display:grid;gap:7px;font-size:12px;color:#53647d}input,select,textarea{border:1px solid #ccd8e8;border-radius:7px;padding:8px 10px;font:inherit;color:#223750;background:white;min-width:0}input,select{min-height:38px}textarea{min-height:86px;resize:vertical}button{min-height:36px;border:1px solid #ccd8e8;border-radius:7px;background:#fff;color:#355274;padding:8px 12px;font:inherit;font-size:12px;cursor:pointer}button:hover:not(:disabled){background:#eef5ff;border-color:#8babd4}button:disabled{opacity:.5;cursor:not-allowed}.primary{background:#2563eb;color:#fff;border-color:#2563eb}.table-scroll{overflow:auto;border:1px solid #e0e7ef;border-radius:9px}table{border-collapse:collapse;width:100%;font-size:12px}th,td{text-align:left;padding:12px;border-bottom:1px solid #e8edf4;vertical-align:top;white-space:nowrap}th{background:#f3f7fc;color:#58708f;font-weight:600}td small{display:block;color:#7b8ca1;margin-top:5px}.row-actions{display:flex;gap:6px}.pager{display:flex;align-items:center;gap:10px;font-size:12px;color:#697b94}.case-summary{display:flex;justify-content:space-between;gap:12px;padding:12px;border-radius:9px;background:#edf4ff}.notice,.success,.error,.pending,.empty{padding:12px 15px;border-radius:8px;font-size:13px;line-height:1.7}.notice,.pending{background:#fff7e8;color:#865e1c}.success{background:#edf9f2;color:#246546}.error{background:#fff0f0;color:#a93d3d}.empty{background:#f4f7fb;color:#697b94}.ok-text{color:#067647}.warn-text{color:#b54708}fieldset{border:0;margin:0;padding:0;display:grid;gap:12px}.ledger-head{justify-content:flex-start}.ledger-head h4{margin-right:auto}button:focus-visible,input:focus-visible,select:focus-visible,textarea:focus-visible{outline:2px solid #2563eb;outline-offset:3px}@media(max-width:980px){.split{grid-template-columns:1fr}}@media(max-width:620px){.finance-workspace{padding:16px}.two-col{grid-template-columns:1fr}.finance-heading{align-items:flex-start}.heading-actions{justify-content:flex-start}.row-actions{display:grid}}
</style>
