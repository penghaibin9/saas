<template>
  <view class="page-wrap">
    <MobileNavBar variant="brand" title="减免与临补" subtitle="申请与办理进度" show-back />
    <MobileGlobalState :state="state" @retry="load"><view v-if="state === 'ready'" class="page-pad stack">
      <view v-if="recordId" class="rd__bar"><text>申请 {{ recordId }}</text><button class="btn btn-secondary" @click="clearFocus">全部申请</button></view>
      <view class="rd__bar"><text>{{ activeCount }} 笔办理中</text><button class="btn btn-primary" :disabled="!!busy" @click="openCreate">发起申请</button></view>
      <view v-if="visibleItems.length" class="stack"><view v-for="item in visibleItems" :key="item.feeId" class="card rd__item">
        <view class="row-between"><view class="flex-1"><text class="card-title">{{ typeLabel(item.itemType) }} · {{ item.yearCode }}</text><text class="hint">{{ categoryLabel(item.reasonCategory) }} · {{ money(item.amount) }}</text></view><MobileStatusTag :status="item.status" :label="item.statusLabel" /></view>
        <text class="rd__reason">{{ item.reason }}</text>
        <view v-if="item.evidence?.length" class="rd__files"><text v-for="file in item.evidence" :key="file.fileId" class="link" @click="openFile(file)">{{ file.fileName || '查看材料' }}</text></view>
        <text v-if="item.reviewOpinion" class="rd__opinion">{{ item.reviewOpinion }}</text>
        <view v-if="item.status === 'ISSUED'" class="rd__receipt">
          <text class="rd__receipt-title">{{ item.itemType === 'REDUCTION' ? '减免落实回执' : '补助发放登记回执' }}</text>
          <text>申请编号：{{ item.feeId }}</text>
          <text>落实时间：{{ receiptTime(item.issuedAt) }}</text>
          <text>办理方式：{{ ({ TUITION_LEDGER: '学费账务减免', BANK_TRANSFER: '银行转账', OTHER: '其他方式' })[item.fulfillmentChannel] || '学校尚未记录' }}</text>
          <text>凭证摘要：{{ item.fulfillmentReference || '学校未填写凭证摘要' }}</text>
          <text v-if="item.itemType === 'TEMP_AID'" class="hint">学校已登记发放，实际到账请核对收款记录。</text>
        </view>
        <view class="rd__actions"><button v-if="allows(item,'RESUBMIT')" class="btn btn-primary" :disabled="!!busy" @click="openEdit(item)">补正后重提</button><button v-if="allows(item,'WITHDRAW')" class="btn btn-secondary" :disabled="!!busy" @click="confirmWithdraw(item)">撤回</button><text v-if="!item.allowedActions?.length" class="hint">{{ nextHint(item.status) }}</text></view>
      </view></view>
      <view v-else class="card rd__empty"><text class="card-title">{{ recordId ? '未找到这笔申请' : '还没有申请' }}</text><text class="hint">{{ recordId ? '请核对入口，或返回全部申请查看。' : '需要时可直接发起。' }}</text></view>
    </view></MobileGlobalState>

    <view v-if="formOpen" class="rd__mask" @click.self="closeForm"><view class="card rd__sheet">
      <view class="row-between"><view><text class="card-title">{{ editing ? '补正申请' : '发起申请' }}</text><text class="hint">信息和材料须真实一致</text></view><text class="rd__close" @click="closeForm">×</text></view>
      <view class="rd__form">
        <view class="fld"><text class="lbl">申请类型</text><picker mode="selector" :range="types" range-key="label" :value="typeIndex" @change="changeType"><view class="input rd__picker">{{ typeLabel(form.itemType) }}</view></picker></view>
        <view class="fld"><text class="lbl">申请学年</text><input v-model.trim="form.yearCode" class="input" maxlength="9" placeholder="2026-2027" /></view>
        <view class="fld"><text class="lbl">困难类别</text><picker mode="selector" :range="categoryOptions" range-key="label" :value="categoryIndex" @change="form.reasonCategory = categoryOptions[$event.detail.value].value"><view class="input rd__picker">{{ categoryLabel(form.reasonCategory) }}</view></picker></view>
        <view class="fld"><text class="lbl">申请金额（元）</text><input v-model="form.amount" class="input" type="digit" placeholder="请输入金额" /></view>
        <view class="fld rd__wide"><text class="lbl">困难情况与申请理由</text><textarea v-model.trim="form.reason" class="input rd__textarea" maxlength="1000" placeholder="至少10字" /></view>
        <MobileAttachmentPicker class="rd__attachments" :file-ids="fileIds" biz-purpose="REDUCTION" :label="editing ? '补充证明材料' : '证明材料'" :max-count="5" :required="!editing" :disabled="!!busy" @update:fileIds="fileIds=$event" @update:ready="fileReady=$event" @error="attachmentError" />
      </view>
      <checkbox-group @change="form.confirm = $event.detail.value.includes('confirmed')"><label class="rd__check"><checkbox class="rd__box" value="confirmed" :checked="form.confirm" color="#2468dc" /><text>本人确认申请信息和材料真实、完整。</text></label></checkbox-group>
      <text v-if="formError" class="rd__error">{{ formError }}</text>
      <view class="rd__sheet-actions"><button class="btn btn-secondary flex-1" :disabled="!!busy" @click="closeForm">取消</button><button class="btn btn-primary flex-1" :disabled="!!busy || !formValid" @click="submit">{{ busy?'正在提交…':'提交待审核' }}</button></view>
    </view></view>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import fileSdk from '@/services/fileSdk'
import { normalizeError } from '@/services/request'
import { toast } from '@/utils/nav'

const categories={REDUCTION:[{label:'特殊身份',value:'SPECIAL_IDENTITY'},{label:'特别困难',value:'EXTREME_DIFFICULTY'},{label:'其他',value:'OTHER'}],TEMP_AID:[{label:'重大疾病',value:'SERIOUS_ILLNESS'},{label:'自然灾害',value:'DISASTER'},{label:'家庭变故',value:'FAMILY_CHANGE'},{label:'意外事故',value:'ACCIDENT'},{label:'其他',value:'OTHER'}]}
const academicYear=()=>{const d=new Date();const start=d.getMonth()>=7?d.getFullYear():d.getFullYear()-1;return `${start}-${start+1}`}
const freshForm=()=>({itemType:'REDUCTION',yearCode:academicYear(),reasonCategory:'OTHER',amount:'',reason:'',confirm:false})
export default{
  data(){return{state:'loading',recordId:'',items:[],busy:'',formOpen:false,editing:null,form:freshForm(),fileIds:[],fileReady:true,formError:'',types:[{label:'学费减免',value:'REDUCTION'},{label:'临时困难补助',value:'TEMP_AID'}]}},
  computed:{visibleItems(){return this.recordId?this.items.filter(item=>String(item.feeId)===this.recordId):this.items},activeCount(){return this.items.filter(item=>['SUBMITTED','RETURNED','APPROVED'].includes(item.status)).length},typeIndex(){return Math.max(0,this.types.findIndex(item=>item.value===this.form.itemType))},categoryOptions(){return categories[this.form.itemType]||categories.REDUCTION},categoryIndex(){return Math.max(0,this.categoryOptions.findIndex(item=>item.value===this.form.reasonCategory))},formValid(){const year=/^(\d{4})-(\d{4})$/.exec(this.form.yearCode);return !!year&&Number(year[2])===Number(year[1])+1&&Number(this.form.amount)>0&&this.form.reason.trim().length>=10&&this.form.confirm&&this.fileReady&&(!!this.editing||this.fileIds.length>0)}},
  onLoad(options){this.recordId=String(options?.recordId||'');this.load()},onPullDownRefresh(){this.load().finally(()=>uni.stopPullDownRefresh())},onBackPress(){if(this.formOpen){this.closeForm();return true}return false},
  methods:{clearFocus(){uni.redirectTo({url:'/pages/student/affairs/reduction'})},receiptTime(value){if(!value)return '学校尚未记录';const date=new Date(value);return Number.isNaN(date.getTime())?'时间待核对':date.toLocaleString('zh-CN',{hour12:false})},allows(item,action){return Array.isArray(item&&item.allowedActions)&&item.allowedActions.includes(action)},typeLabel(type){return type==='TEMP_AID'?'临时困难补助':'学费减免'},categoryLabel(value){return Object.values(categories).flat().find(item=>item.value===value)?.label||'其他'},nextHint(status){return({APPROVED:'等待学校落实结果',REJECTED:'本次申请已结束',ISSUED:'办理完成',WITHDRAWN:'已撤回'})[status]||'等待处理'},money(value){return Number.isFinite(Number(value))?`¥${Number(value).toFixed(2)}`:'—'},
    async load(){this.state='loading';try{const data=await studentApi.getMyFeeReductions();this.items=data.items||[];this.state='ready'}catch(e){this.state='error';toast(normalizeError(e).text||'申请记录加载失败')}},openCreate(){this.editing=null;this.form=freshForm();this.fileIds=[];this.fileReady=false;this.formError='';this.formOpen=true},openEdit(item){this.editing=item;this.form={itemType:item.itemType||'REDUCTION',yearCode:item.yearCode||academicYear(),reasonCategory:item.reasonCategory||'OTHER',amount:item.amount||'',reason:item.reason||'',confirm:false};this.fileIds=[];this.fileReady=true;this.formError='';this.formOpen=true},closeForm(){if(!this.busy)this.formOpen=false},changeType(e){this.form.itemType=this.types[e.detail.value].value;this.form.reasonCategory='OTHER'},attachmentError(error){this.formError=normalizeError(error).text||'证明材料处理失败'},payload(){return{itemType:this.form.itemType,yearCode:this.form.yearCode,reasonCategory:this.form.reasonCategory,amount:String(this.form.amount),reason:this.form.reason.trim(),attachmentIds:this.fileIds,confirm:true,...(this.editing?{version:this.editing.version}:{})}},
    async submit(){if(this.busy)return;if(!this.formValid){this.formError=this.fileReady?'请核对学年、金额、至少10字理由、材料和本人确认':'证明材料仍在安全检查';return}this.busy='submit';this.formError='';try{if(this.editing)await studentApi.resubmitFeeReduction(this.editing.feeId,this.payload());else await studentApi.submitFeeReduction(this.payload());toast(this.editing?'申请已补正并重提':'申请已提交');this.formOpen=false;await this.load()}catch(e){this.formError=normalizeError(e).text||'提交失败，请重试'}finally{this.busy=''}},confirmWithdraw(item){uni.showModal({title:'撤回这笔申请？',content:'撤回后本次申请结束；需要时可重新发起。',confirmText:'确认撤回',success:res=>{if(res.confirm)this.withdraw(item)}})},async withdraw(item){if(this.busy)return;this.busy=`withdraw-${item.feeId}`;try{await studentApi.withdrawFeeReduction(item.feeId,item.version);toast('申请已撤回');await this.load()}catch(e){toast(normalizeError(e).text||'撤回失败')}finally{this.busy=''}},async openFile(file){if(!file?.fileId)return;this.busy=`file-${file.fileId}`;try{await fileSdk.open(file.fileId)}catch(e){toast(normalizeError(e).text||'材料读取失败')}finally{this.busy=''}}}
}
</script>

<style scoped>
.rd__receipt{display:flex;flex-direction:column;gap:8px;padding-top:12px;border-top:1px solid var(--border-light);color:var(--text-secondary);font-size:12px;line-height:1.6;word-break:break-all}.rd__receipt-title{color:var(--text-primary);font-weight:600;font-size:14px}
.rd__bar{display:flex;justify-content:space-between;align-items:center;min-height:42px;color:var(--text-secondary);font-size:13px}.rd__bar .btn{margin:0}.rd__empty{display:flex;flex-direction:column;gap:5px;padding:22px;text-align:center}.rd__empty .card-title,.rd__empty .hint{display:block}.rd__item{display:flex;flex-direction:column;gap:10px}.rd__item .card-title,.rd__item .hint{display:block}.rd__reason{color:var(--text-secondary);font-size:13px;line-height:1.55}.rd__files{display:flex;flex-wrap:wrap;gap:10px;padding:9px 10px;border-radius:9px;background:var(--bg-page);font-size:12px}.rd__opinion{padding:8px 10px;border-radius:8px;color:#8a3d20;background:#fff5ed;font-size:12px}.rd__actions{display:flex;flex-wrap:wrap;justify-content:flex-end;gap:8px}.rd__actions .btn{margin:0}.rd__mask{position:fixed;z-index:1000;inset:0;display:flex;align-items:flex-end;background:rgba(15,23,42,.52)}.rd__sheet{width:100%;max-height:90vh;overflow:auto;padding:18px;border-radius:18px 18px 0 0}.rd__close{padding:0 6px;color:var(--text-secondary);font-size:26px}.rd__form{display:grid;grid-template-columns:1fr 1fr;gap:0 10px}.rd__wide,.rd__attachments{grid-column:1/-1}.rd__textarea{min-height:78px}.rd__picker{display:flex;align-items:center}.rd__check{display:flex;gap:8px;align-items:flex-start;margin-top:14px;color:var(--text-secondary);font-size:12px;line-height:1.5}.rd__box{transform:scale(.8);transform-origin:top left}.rd__error{display:block;margin-top:8px;color:var(--danger-600);font-size:12px}.rd__sheet-actions{display:flex;gap:10px;margin-top:14px}
</style>
