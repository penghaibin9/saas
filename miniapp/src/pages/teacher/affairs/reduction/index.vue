<template>
  <view class="page-wrap">
    <MobileNavBar variant="brand" title="减免与临补" subtitle="待办优先" show-back />
    <MobileGlobalState :state="state" :description="listError" @retry="load"><view v-if="state==='ready'" class="page-pad stack">
      <view v-if="focusId" class="row-between"><text>当前申请 · {{ focusId }}</text><button class="btn btn-secondary" @click="clearFocus">返回办理队列</button></view>
      <scroll-view v-else class="rd__filters" scroll-x><button v-for="item in statuses" :key="item.value||'all'" class="rd__filter" :class="{on:status===item.value}" @click="changeStatus(item.value)">{{ item.label }} {{ count(item.value) }}</button></scroll-view>
      <view v-if="!focusId" class="rd__search"><input v-model.trim="keyword" class="input" maxlength="100" placeholder="姓名、学号或申请理由" confirm-type="search" @confirm="search" /><button class="btn btn-secondary" :disabled="refreshing" @click="search">查询</button></view>
      <view v-if="items.length" class="stack"><view v-for="item in items" :key="item.feeId" class="card rd__item">
        <view class="row-between"><view class="flex-1"><text class="rd__student">{{ item.realName }} · {{ item.studentNo }}</text><text class="card-title">{{ typeLabel(item.itemType) }} · {{ item.yearCode }}</text><text class="hint">{{ categoryLabel(item.reasonCategory) }} · {{ money(item.amount) }}</text></view><MobileStatusTag :status="item.status" :label="item.statusLabel" /></view>
        <text class="rd__reason">{{ item.reason }}</text><view v-if="item.evidence?.length" class="rd__files"><text v-for="file in item.evidence" :key="file.fileId" class="link" @click="openFile(file)">{{ file.fileName||'查看材料' }}</text></view><text v-if="item.reviewOpinion" class="rd__opinion">{{ item.reviewOpinion }}</text>
        <view v-if="item.status === 'ISSUED'" class="rd__opinion"><text>落实时间：{{ item.issuedAt ? new Date(item.issuedAt).toLocaleString('zh-CN', { hour12: false }) : '时间待核对' }}</text><text>凭证摘要：{{ item.fulfillmentReference || '未填写凭证摘要' }}</text></view>
        <view class="rd__actions"><button v-if="allows(item,'APPROVE')" class="btn btn-primary" :disabled="!!busy" @click="openAction(item,'APPROVE')">批准</button><button v-if="allows(item,'RETURN')" class="btn btn-secondary" :disabled="!!busy" @click="openAction(item,'RETURN')">退回</button><button v-if="allows(item,'REJECT')" class="btn btn-danger" :disabled="!!busy" @click="openAction(item,'REJECT')">驳回</button><button v-if="allows(item,'FULFILL')" class="btn btn-primary" :disabled="!!busy" @click="openAction(item,'FULFILL')">{{ item.itemType==='REDUCTION'?'确认减免':'登记发放' }}</button><text v-if="!item.allowedActions?.length" class="hint">只读</text></view>
      </view></view><view v-else class="card rd__empty"><text class="card-title">{{ focusId ? '该申请不存在或不在当前权限范围内' : status === 'SUBMITTED' ? '当前没有待审核申请' : '当前没有匹配记录' }}</text><text v-if="!focusId" class="hint">切换状态可查看历史。</text></view><text v-if="moreError" class="rd__error">{{ moreError }}</text><button v-if="items.length<total" class="btn btn-secondary" :disabled="refreshing" @click="loadItems(true)">{{ moreError ? '重试加载' : '加载更多' }}</button>
    </view></MobileGlobalState>

    <view v-if="actionTarget" class="rd__mask" @click.self="closeAction"><view class="card rd__sheet"><view class="row-between"><view><text class="card-title">{{ actionTitle }}</text><text class="hint">{{ actionTarget.realName }} · {{ typeLabel(actionTarget.itemType) }}</text></view><text class="rd__close" @click="closeAction">×</text></view>
      <view v-if="['RETURN','REJECT'].includes(actionType)" class="fld"><text class="lbl">处理意见</text><textarea v-model.trim="form.opinion" class="input rd__textarea" maxlength="1000" :placeholder="actionType==='RETURN'?'说明需要补正的内容':'说明不予通过的依据'" /></view>
      <view v-else-if="actionType==='APPROVE'" class="fld"><text class="lbl">审核意见（选填）</text><textarea v-model.trim="form.opinion" class="input rd__textarea" maxlength="1000" /></view>
      <view v-else class="fld"><text class="lbl">结果凭证摘要（选填）</text><input v-model.trim="form.fulfillmentReference" class="input" maxlength="200" :placeholder="actionTarget.itemType==='REDUCTION'?'财务减免清单批次':'财务转账批次'" /></view>
      <text v-if="actionError" class="rd__error">{{ actionError }}</text><view class="rd__sheet-actions"><button class="btn btn-secondary flex-1" :disabled="!!busy" @click="closeAction">取消</button><button class="btn btn-primary flex-1" :disabled="!!busy||!actionValid" @click="submitAction">{{ confirmText }}</button></view>
    </view></view>
  </view>
</template>

<script>
import { teacherApi } from '@/services/teacherApi'
import fileSdk from '@/services/fileSdk'
import { normalizeError } from '@/services/request'
import { toast } from '@/utils/nav'

const categoryMap={SPECIAL_IDENTITY:'特殊身份',EXTREME_DIFFICULTY:'特别困难',SERIOUS_ILLNESS:'重大疾病',DISASTER:'自然灾害',FAMILY_CHANGE:'家庭变故',ACCIDENT:'意外事故',OTHER:'其他'}
export default{
  data(){return{state:'loading',focusId:'',requestSeq:0,listError:'',moreError:'',items:[],total:0,statusCounts:{},page:1,status:'SUBMITTED',keyword:'',appliedKeyword:'',refreshing:false,busy:'',actionTarget:null,actionType:'',actionError:'',form:{opinion:'',fulfillmentReference:''},statuses:[{value:'SUBMITTED',label:'待审核'},{value:'APPROVED',label:'已批准'},{value:'RETURNED',label:'待补正'},{value:'ISSUED',label:'已落实'},{value:'',label:'全部'}]}},
  computed:{actionTitle(){return({APPROVE:'批准申请',RETURN:'退回补正',REJECT:'驳回申请',FULFILL:this.actionTarget?.itemType==='REDUCTION'?'确认学费减免':'登记补助发放'})[this.actionType]||'处理申请'},confirmText(){return({APPROVE:'确认批准',RETURN:'确认退回',REJECT:'确认驳回',FULFILL:this.actionTarget?.itemType==='REDUCTION'?'确认减免':'登记发放'})[this.actionType]||'确认'},actionValid(){return !['RETURN','REJECT'].includes(this.actionType)||this.form.opinion.trim().length>=5}},
  onLoad(options = {}){this.focusId=String(options.recordId ?? '');return this.load()},onUnload(){this.requestSeq++},onPullDownRefresh(){this.loadItems().finally(()=>uni.stopPullDownRefresh())},onBackPress(){if(this.actionTarget){this.closeAction();return true}return false},
  methods:{allows(item,action){return Array.isArray(item&&item.allowedActions)&&item.allowedActions.includes(action)},count(value){return Number(this.statusCounts[value||'ALL']||0)},typeLabel(type){return type==='TEMP_AID'?'临时困难补助':'学费减免'},categoryLabel(value){return categoryMap[value]||'其他'},money(value) { if (value === null || value === undefined || value === '') return '—'; if (String(value).includes('*')) return '金额已隐藏'; return Number.isFinite(Number(value)) ? `¥${Number(value).toFixed(2)}` : '—' },
    load() { return this.loadItems() },
    clearFocus() { return uni.redirectTo({ url: '/pages/teacher/affairs/reduction/index' }) },
    async loadItems(more = false) {
      more = more === true
      if (more && (this.refreshing || this.items.length >= this.total)) return
      const request = ++this.requestSeq
      const page = more ? this.page + 1 : 1
      this.refreshing = true; this.listError = ''; this.moreError = ''
      if (!more) this.state = 'loading'
      try {
        if (this.focusId && !/^[1-9]\d*$/.test(this.focusId)) throw new Error('申请链接无效，请返回重新选择')
        const query = this.focusId ? { recordId: this.focusId, page: 1, pageSize: 1 } : { page, pageSize: 20, status: this.status, keyword: this.appliedKeyword }
        const data = await teacherApi.getAffairsFeeReductions(query)
        if (request !== this.requestSeq) return
        if (!Array.isArray(data?.items)) throw new Error('列表暂不可用，请重试')
        this.items = more ? [...new Map([...this.items, ...data.items].map(item => [String(item.feeId), item])).values()] : data.items
        this.total = Number(data.total || 0); this.statusCounts = data.statusCounts || {}
        this.page = page; this.state = 'ready'
      } catch (e) {
        if (request !== this.requestSeq) return
        if (more) this.moreError = '加载失败，已加载记录仍保留，请重试'
        else { this.listError = normalizeError(e).text || '列表加载失败，请重试'; this.state = 'error' }
      } finally { if (request === this.requestSeq) this.refreshing = false }
    }, search(){this.appliedKeyword=this.keyword.trim();return this.loadItems()},changeStatus(value){if(this.status===value)return;this.status=value;return this.loadItems()},openAction(item,action){this.actionTarget=item;this.actionType=action;this.actionError='';this.form={opinion:'',fulfillmentReference:''}},closeAction(){if(!this.busy)this.actionTarget=null},
    async submitAction(){if(this.busy)return;if(!this.actionTarget||!this.actionValid)return;const item=this.actionTarget;this.busy=`${this.actionType}-${item.feeId}`;this.actionError='';try{await teacherApi.actAffairsFeeReduction(item.feeId,{action:this.actionType,version:item.version,opinion:this.form.opinion||undefined,...(this.actionType==='FULFILL'?{fulfillmentChannel:item.itemType==='REDUCTION'?'TUITION_LEDGER':'BANK_TRANSFER',fulfillmentReference:this.form.fulfillmentReference||undefined}:{})});toast(this.confirmText+'成功');this.actionTarget=null;await this.loadItems()}catch(e){this.actionError=normalizeError(e).text||'处理失败，请刷新后重试'}finally{this.busy=''}},async openFile(file){if(!file?.fileId)return;this.busy=`file-${file.fileId}`;try{await fileSdk.open(file.fileId)}catch(e){toast(normalizeError(e).text||'材料读取失败')}finally{this.busy=''}}}
}
</script>

<style scoped>
.rd__filters{white-space:nowrap}.rd__filter{display:inline-flex;margin-right:8px;padding:8px 12px;border:1px solid var(--border-light);border-radius:18px;color:var(--text-secondary);background:var(--bg-card);font-size:12px}.rd__filter.on{border-color:var(--brand-primary);color:#fff;background:var(--brand-primary)}.rd__search{display:flex;gap:8px}.rd__search .input{flex:1}.rd__empty{display:flex;flex-direction:column;gap:5px;padding:22px;text-align:center}.rd__empty .card-title,.rd__empty .hint{display:block}.rd__item{display:flex;flex-direction:column;gap:10px}.rd__student{display:block;color:var(--text-secondary);font-size:12px}.rd__item .card-title,.rd__item .hint{display:block}.rd__reason{color:var(--text-secondary);font-size:13px;line-height:1.55}.rd__files{display:flex;flex-wrap:wrap;gap:10px;padding:9px 10px;border-radius:9px;background:var(--bg-page);font-size:12px}.rd__opinion{padding:8px 10px;border-radius:8px;color:#8a3d20;background:#fff5ed;font-size:12px}.rd__actions{display:flex;flex-wrap:wrap;justify-content:flex-end;gap:8px}.rd__actions .btn{margin:0;font-size:12px}.rd__mask{position:fixed;z-index:1000;inset:0;display:flex;align-items:flex-end;background:rgba(15,23,42,.52)}.rd__sheet{width:100%;max-height:90vh;overflow:auto;padding:18px;border-radius:18px 18px 0 0}.rd__close{padding:0 6px;color:var(--text-secondary);font-size:26px}.rd__textarea{min-height:86px}.rd__error{display:block;margin-top:8px;color:var(--danger-600);font-size:12px}.rd__sheet-actions{display:flex;gap:10px;margin-top:14px}
</style>
