<template>
  <div class="rd-student">
    <section class="sp-card rd-head"><div><strong>减免与临时补助</strong><span>{{ activeCount }} 笔办理中</span></div><button class="sp-btn" type="button" :disabled="loading || !!busy" @click="openCreate">发起申请</button></section>
    <div v-if="error" class="rd-error" role="alert"><span>{{ error }}</span><button class="sp-btn sp-btn--ghost" type="button" @click="load">重试</button></div>
    <StateBlock v-else-if="loading" type="loading" text="正在同步申请进度…" />
    <section v-else class="sp-card rd-list">
      <header><strong>我的申请</strong><button class="sp-btn sp-btn--ghost" type="button" :disabled="!!busy" @click="load">刷新</button></header>
      <StateBlock v-if="!items.length" type="empty" text="还没有减免或临时补助申请" />
      <article v-for="item in items" :key="item.feeId" class="rd-row">
        <div class="rd-main"><strong>{{ typeLabel(item.itemType) }} · {{ item.yearCode }}</strong><span>{{ categoryLabel(item.reasonCategory) }} · {{ money(item.amount) }}</span></div>
        <div class="rd-reason"><span>{{ item.reason }}</span><div v-if="item.evidence?.length"><button v-for="file in item.evidence" :key="file.fileId" type="button" :disabled="!!busy" @click="openFile(file)">{{ file.fileName || '查看材料' }}</button></div></div>
        <div class="rd-state"><StatusTag :text="item.statusLabel" :tone="statusTone(item.status)" /><small v-if="item.reviewOpinion">{{ item.reviewOpinion }}</small></div>
        <div class="rd-actions"><button v-if="allows(item, 'RESUBMIT')" class="sp-btn" type="button" :disabled="!!busy" @click="openEdit(item)">补正后重提</button><button v-if="allows(item, 'WITHDRAW')" class="sp-btn sp-btn--ghost" type="button" :disabled="!!busy" @click="withdrawTarget = item">撤回</button><span v-if="!item.allowedActions?.length">{{ nextHint(item.status) }}</span></div>
      </article>
    </section>

    <div v-if="drawer.visible" class="rd-mask" @click.self="closeDrawer"><section class="sp-card rd-dialog" role="dialog" aria-modal="true" aria-labelledby="rd-form-title">
      <header><div><strong id="rd-form-title">{{ drawer.item ? '补正减免或临补申请' : '申请减免或临时补助' }}</strong><span>困难事实、金额和证明材料须相互对应</span></div><button type="button" aria-label="关闭" @click="closeDrawer">×</button></header>
      <div class="rd-form">
        <label><span>申请类型</span><select v-model="form.itemType" class="sp-inp" :disabled="!!busy" @change="form.reasonCategory='OTHER'"><option value="REDUCTION">学费减免</option><option value="TEMP_AID">临时困难补助</option></select></label>
        <label><span>申请学年</span><input v-model.trim="form.yearCode" class="sp-inp" maxlength="9" placeholder="2026-2027" :disabled="!!busy" /></label>
        <label><span>困难类别</span><select v-model="form.reasonCategory" class="sp-inp" :disabled="!!busy"><option v-for="option in categoryOptions" :key="option.value" :value="option.value">{{ option.label }}</option></select></label>
        <label><span>申请金额（元）</span><input v-model="form.amount" class="sp-inp" type="number" min="0.01" step="0.01" :disabled="!!busy" /></label>
        <label class="rd-wide"><span>困难情况与申请理由（10-1000字）</span><textarea v-model.trim="form.reason" class="sp-inp" maxlength="1000" rows="4" :disabled="!!busy" /></label>
        <FundingAttachments :key="attachmentEpoch" class="rd-wide" biz-type="REDUCTION" :max-count="5" :title="drawer.item ? '补充证明材料' : '证明材料'" :description="drawer.item ? '原材料继续保留；如退回意见要求补件，请在这里添加。' : '至少上传一份与困难情况相关的证明。'" :disabled="!!busy" @change="Object.assign(attachments, $event)" />
      </div>
      <label class="rd-confirm"><input v-model="form.confirm" type="checkbox" :disabled="!!busy" />本人确认申请信息和材料真实、完整。</label>
      <p v-if="formError" class="field-error" role="alert">{{ formError }}</p>
      <footer><button class="sp-btn sp-btn--ghost" type="button" :disabled="!!busy" @click="closeDrawer">取消</button><button class="sp-btn" type="button" :disabled="!!busy || !formValid" @click="submit">{{ busy ? '正在提交…' : '提交待审核' }}</button></footer>
    </section></div>

    <div v-if="withdrawTarget" class="rd-mask" @click.self="withdrawTarget = null"><section class="sp-card rd-dialog rd-dialog--small" role="alertdialog" aria-modal="true"><h3>撤回这笔申请？</h3><p class="sp-muted">撤回后本次申请结束；需要办理时可重新发起。</p><footer><button class="sp-btn sp-btn--ghost" type="button" :disabled="!!busy" @click="withdrawTarget = null">继续保留</button><button class="sp-btn" type="button" :disabled="!!busy" @click="withdraw">确认撤回</button></footer></section></div>
  </div>
</template>

<script setup>
import { computed, inject, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import FundingAttachments from './FundingAttachments.vue'
import StateBlock from '../../components/StateBlock.vue'
import StatusTag from '../../components/StatusTag.vue'
import { portalApi } from '../../services/portalApi'
import { fileSdk } from '../../services/fileSdk'
import { useUiStore } from '../../stores/ui'

const ui = useUiStore(); const loading = ref(true); const error = ref(''); const items = ref([]); const busy = ref(''); const formError = ref(''); const drawer = reactive({ visible:false, item:null }); const withdrawTarget = ref(null); const attachments = reactive({ fileIds:[], ready:true, hasDraft:false, busy:false, items:[] }); const attachmentEpoch = ref(0)
const categories = { REDUCTION:[{label:'特殊身份',value:'SPECIAL_IDENTITY'},{label:'特别困难',value:'EXTREME_DIFFICULTY'},{label:'其他',value:'OTHER'}], TEMP_AID:[{label:'重大疾病',value:'SERIOUS_ILLNESS'},{label:'自然灾害',value:'DISASTER'},{label:'家庭变故',value:'FAMILY_CHANGE'},{label:'意外事故',value:'ACCIDENT'},{label:'其他',value:'OTHER'}] }
const academicYear = () => { const d=new Date(); const start=d.getMonth()>=7?d.getFullYear():d.getFullYear()-1; return `${start}-${start+1}` }
const freshForm = () => ({ itemType:'REDUCTION', yearCode:academicYear(), reasonCategory:'OTHER', amount:'', reason:'', confirm:false })
const form = reactive(freshForm())
const activeCount = computed(() => items.value.filter(item => ['SUBMITTED','RETURNED','APPROVED'].includes(item.status)).length)
const categoryOptions = computed(() => categories[form.itemType] || categories.REDUCTION)
const formValid = computed(() => { const year=/^(\d{4})-(\d{4})$/.exec(form.yearCode); return !!year && Number(year[2])===Number(year[1])+1 && Number(form.amount)>0 && form.reason.trim().length>=10 && form.confirm && attachments.ready && !attachments.busy && (!!drawer.item || attachments.fileIds.length>0) })
const allows=(item,action)=>Array.isArray(item?.allowedActions)&&item.allowedActions.includes(action)
const typeLabel=type=>type==='TEMP_AID'?'临时困难补助':'学费减免'
const categoryLabel=value=>Object.values(categories).flat().find(item=>item.value===value)?.label||'其他'
const statusTone=status=>({SUBMITTED:'warn',RETURNED:'danger',APPROVED:'success',ISSUED:'success'})[status]||'default'
const nextHint=status=>({APPROVED:'等待学校落实结果',REJECTED:'本次申请已结束',ISSUED:'办理完成',WITHDRAWN:'已撤回'})[status]||'等待处理'
const money=value=>Number.isFinite(Number(value))?`¥${Number(value).toLocaleString('zh-CN',{minimumFractionDigits:2,maximumFractionDigits:2})}`:'—'
function resetAttachments(){ Object.assign(attachments,{fileIds:[],ready:true,hasDraft:false,busy:false,items:[]}); attachmentEpoch.value++ }
function openCreate(){ drawer.item=null; Object.assign(form,freshForm()); resetAttachments(); formError.value=''; drawer.visible=true }
function openEdit(item){ drawer.item=item; Object.assign(form,{itemType:item.itemType||'REDUCTION',yearCode:item.yearCode||academicYear(),reasonCategory:item.reasonCategory||'OTHER',amount:item.amount||'',reason:item.reason||'',confirm:false}); resetAttachments(); formError.value=''; drawer.visible=true }
function closeDrawer(){ if(!busy.value) drawer.visible=false }
function payload(){ return {itemType:form.itemType,yearCode:form.yearCode,reasonCategory:form.reasonCategory,amount:String(form.amount),reason:form.reason.trim(),attachmentIds:attachments.fileIds,confirm:true,...(drawer.item?{version:drawer.item.version}:{})} }
async function load(){ loading.value=true; error.value=''; try{ const data=await portalApi.affairsFeeReductions(); items.value=data?.items||[] }catch(e){ error.value=e?.message||'申请记录加载失败' }finally{ loading.value=false } }
async function submit(){ if(!formValid.value){ formError.value=attachments.busy||!attachments.ready?'证明材料仍在安全检查':'请核对学年、金额、至少10字理由、证明材料和本人确认'; return } busy.value=drawer.item?`resubmit-${drawer.item.feeId}`:'submit'; formError.value=''; try{ if(drawer.item) await portalApi.affairsFeeReductionResubmit(drawer.item.feeId,payload()); else await portalApi.affairsFeeReductionSubmit(payload()); ui.notify(drawer.item?'申请已补正并重新提交':'申请已提交，等待学校审核'); drawer.visible=false; await load() }catch(e){ formError.value=e?.message||'提交失败，请重试' }finally{ busy.value='' } }
async function withdraw(){ const item=withdrawTarget.value; if(!item)return; busy.value=`withdraw-${item.feeId}`; try{ await portalApi.affairsFeeReductionWithdraw(item.feeId,item.version); ui.notify('申请已撤回'); withdrawTarget.value=null; await load() }catch(e){ ui.notify(e?.message||'撤回失败，请刷新后重试') }finally{ busy.value='' } }
async function openFile(file){ if(!file?.fileId)return; busy.value=`file-${file.fileId}`; try{ await fileSdk.download(file.fileId,file.fileName||'证明材料') }catch(e){ ui.notify(e?.message||'材料读取失败') }finally{ busy.value='' } }
const registerWorkspaceForm=inject('registerWorkspaceForm',null); const unregister=registerWorkspaceForm?.(()=>drawer.visible&&(!!form.amount||!!form.reason||attachments.hasDraft),()=>!!busy.value)
onMounted(load); onBeforeUnmount(()=>unregister?.())
</script>

<style scoped>
.rd-student{display:grid;gap:12px}.rd-head{display:flex;justify-content:space-between;align-items:center;padding:12px 16px}.rd-head div{display:flex;gap:10px;align-items:baseline}.rd-head strong{color:var(--t1);font-size:16px}.rd-head span{color:var(--t3);font-size:12px}.rd-list{overflow:hidden;padding:0}.rd-list>header{display:flex;justify-content:space-between;align-items:center;min-height:48px;padding:0 16px;border-bottom:1px solid var(--line)}.rd-row{display:grid;grid-template-columns:minmax(200px,1fr) minmax(260px,1.4fr) minmax(150px,.8fr) auto;gap:16px;align-items:center;min-height:78px;padding:12px 16px;border-bottom:1px solid var(--line)}.rd-main,.rd-reason,.rd-state{display:grid;gap:4px;min-width:0}.rd-main span,.rd-reason>span,.rd-state small,.rd-actions>span{overflow:hidden;color:var(--t3);font-size:12px;text-overflow:ellipsis;white-space:nowrap}.rd-reason div{display:flex;gap:7px;overflow:hidden}.rd-reason button{overflow:hidden;padding:0;border:0;color:var(--pri);background:transparent;text-overflow:ellipsis;white-space:nowrap;cursor:pointer}.rd-actions{display:flex;justify-content:flex-end;gap:7px}.rd-error{display:flex;justify-content:space-between;align-items:center;padding:12px 16px;border:1px solid #f1b9b9;border-radius:10px;color:#9a2929;background:#fff7f7}.rd-mask{position:fixed;z-index:2200;inset:0;display:grid;place-items:center;padding:20px;background:rgba(13,18,28,.52)}.rd-dialog{width:min(680px,100%);max-height:calc(100vh - 40px);overflow:auto;padding:18px}.rd-dialog--small{width:min(420px,100%)}.rd-dialog>header{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:14px}.rd-dialog>header div{display:grid;gap:4px}.rd-dialog>header span{color:var(--t3);font-size:12px}.rd-dialog>header button{width:34px;height:34px;border:0;border-radius:8px;color:var(--t2);background:var(--bg);font-size:22px;cursor:pointer}.rd-form{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px 16px}.rd-form>label{display:grid;gap:6px;color:var(--t2);font-size:13px}.rd-wide{grid-column:1/-1}.rd-confirm{display:flex;gap:8px;align-items:flex-start;margin-top:14px;color:var(--t2);font-size:13px}.rd-dialog>footer{display:flex;justify-content:flex-end;gap:8px;margin-top:16px}@media(max-width:900px){.rd-row{grid-template-columns:1fr 1fr}.rd-actions{justify-content:flex-start}}@media(max-width:640px){.rd-row,.rd-form{grid-template-columns:1fr}.rd-wide{grid-column:auto}.rd-head div{display:grid;gap:2px}.rd-actions{flex-wrap:wrap}}
</style>
