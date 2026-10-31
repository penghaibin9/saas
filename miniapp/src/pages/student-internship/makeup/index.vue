<template>
  <view class="internship-surface mobile-page mobile-student page-wrap lv">
    <MobileNavBar title="补卡申请" show-back :fallback-url="'/pages/student-internship/index' + (context.batchId ? '?batchId=' + encodeURIComponent(context.batchId) : '')" />
    <MobilePrivacyGate />
    <MobileGlobalState :state="pageState" :description="errorMessage" @retry="loadList()">
      <view class="page-pad stack">
        <MobileInlineAlert v-if="historyMode" type="info" description="历史实习仅可查看补卡记录，不可新增或撤回申请。" />
        <MobileInlineAlert v-if="errorMessage" type="warning" :description="errorMessage" />
        <button class="mobile-control lv__refresh" :disabled="busy" @click="loadList()">刷新记录</button>

        <view v-if="receipt" class="card lv__receipt">
          <view class="row-between">
            <text class="lv__receipt-title">{{ statusLabel(receipt.status) }}</text>
            <text class="lv__receipt-close" @click="receipt = null">关闭</text>
          </view>
          <text class="lv__meta">申请编号 {{ receipt.id }} · 第{{ Number(receipt.version ?? 0)+1 }}版记录</text>
          <text class="lv__receipt-next">学校审核人员办理后，可在本页查看结果。</text>
        </view>

        <view v-for="item in list" :key="item.id" class="card lv__item">
          <view class="row-between">
            <text class="lv__range">{{ item.checkinDate }}</text>
            <MobileStatusTag :label="statusLabel(item.status)" />
          </view>
          <text class="lv__days">{{ typeLabel(item.makeupType) }}</text>
          <text class="lv__reason">{{ item.reason }}</text>
          <text class="lv__meta">证据材料：{{ item.hasEvidence || item.evidenceFileId ? '已上传' : (item.evidenceRequired ? '缺少必需材料' : '未上传') }}</text>
          <text class="lv__meta">提交时间：{{ formatTime(item.submittedAt || item.createdAt) }}</text>
          <view v-if="item.reviewComment" class="lv__review">
            <text class="lv__review-title">审批意见</text>
            <text class="lv__review-text">{{ item.reviewComment }}</text>
          </view>
          <button v-if="item.status === 'PENDING'" class="mobile-control btn btn-ghost lv__withdraw" :disabled="!canWrite || busy" @click="withdraw(item)">撤回</button>
        </view>
        <MobileInlineAlert v-if="!list.length" type="info" description="暂无补卡申请。漏签或签到异常需要补正时，可从签到日历选中缺卡日期带入；请假、免签日期按学校规则处理。" />
      </view>
    </MobileGlobalState>

    <MobileSafeAreaBar v-if="!formVisible">
      <button class="mobile-control btn btn-primary flex-1" :disabled="!canWrite || busy" @click="openApply">新建补卡申请</button>
    </MobileSafeAreaBar>

    <view v-if="formVisible" class="lv__mask" @click.self="closeForm">
      <view class="lv__sheet card">
        <text class="card-title">补卡申请</text>
        <MobileInlineAlert v-if="formError" type="warning" :description="formError" />
        <view class="lv__field">
          <text class="lv__label">补卡类型 <text class="lv__req">*</text></text>
          <picker class="mobile-picker" mode="selector" :range="makeupTypeLabels" :value="makeupTypeIndex" :disabled="!canWrite || busy" @change="onMakeupType">
            <view class="lv__picker">{{ makeupTypeLabels[makeupTypeIndex] }} <text>▾</text></view>
          </picker>
        </view>
        <view class="lv__field">
          <text class="lv__label">缺卡日期 <text class="lv__req">*</text></text>
          <picker class="mobile-picker" mode="date" :value="form.checkinDate" :disabled="!canWrite || busy" @change="onDate">
            <view class="lv__picker">{{ form.checkinDate || '请选择' }}</view>
          </picker>
        </view>
        <view class="lv__field">
          <text class="lv__label">补卡事由 <text class="lv__req">*</text></text>
          <textarea v-model="form.reason" :disabled="!canWrite || busy" class="mobile-textarea lv__textarea" maxlength="300" placeholder="详细说明缺卡原因（不少于5字）" />
        </view>
        <view class="lv__field lv__evidence" :class="{ required: evidenceRequired }">
          <text class="lv__label">证据材料 {{ evidenceRequired ? '（必需）' : '（选传）' }}</text>
          <text class="lv__rule">{{ evidenceRuleText }}</text>
          <button class="mobile-control btn btn-ghost lv__upload" :disabled="!canWrite || busy" @click="chooseEvidence">
            {{ uploading ? '上传中…' : (form.fileName || '选择并上传证据') }}
          </button>
          <text v-if="pendingEvidence" class="lv__rule">{{ pendingEvidence.statusText }}</text>
          <button class="mobile-control" v-if="pendingEvidence" :disabled="!canWrite || busy" @click="refreshEvidence">{{ scanning ? '正在读取安全检查…' : '刷新证据安全状态' }}</button>
        </view>
        <view class="lv__actions">
          <button class="mobile-control btn btn-ghost flex-1" :disabled="busy" @click="closeForm">取消</button>
          <button class="mobile-control btn btn-primary flex-1" :disabled="!canWrite || busy || !evidenceReady" @click="submit">{{ submitting ? '提交中…' : '提交申请' }}</button>
        </view>
      </view>
    </view>
  </view>
</template>

<script>
import { studentInternshipMakeupApply, studentInternshipMakeups, studentInternshipMakeupWithdraw } from '@/services/internshipApi'
import { studentApi } from '@/services/studentApi'
import { normalizeError } from '@/services/request'
import { chooseSingleFile, uploadBusinessFile, fileSdk } from '@/services/fileApi'
import { normalizeFileReadiness, refreshFileReadiness } from '@/services/fileReadiness.mjs'
import { currentSessionGeneration } from '@/services/sessionGeneration.mjs'
import { formatDateTime } from '@/utils/format'
import { toast } from '@/utils/nav'
const MAKEUP_TYPES=[{value:'MISSING',label:'缺卡补录'},{value:'OUT_OF_RANGE',label:'定位异常补录'}]
const blank=()=>({checkinDate:'',reason:'',makeupType:'MISSING',evidenceFileId:'',fileName:''})
export default {
  data(){return {list:[],pageState:'loading',formVisible:false,context:{},requestedBatchId:'',historyMode:false,
    submitting:false,uploading:false,scanning:false,selectingEvidence:false,resumeEvidence:null,makeupTypeIndex:0,
    receipt:null,form:blank(),pendingEvidence:null,errorMessage:'',formError:'',hidden:false,epoch:0,generation:currentSessionGeneration()}},
  computed:{
    makeupTypeLabels(){return MAKEUP_TYPES.map(item=>item.label)},
    evidenceRequired(){return this.form.makeupType==='OUT_OF_RANGE'},
    evidenceRuleText(){return this.evidenceRequired?'定位异常补卡必须上传考勤、定位截图或现场佐证。':'普通缺卡可按学校要求选传考勤或现场佐证。'},
    evidenceReady(){return this.pendingEvidence?this.pendingEvidence.readyForBusiness===true:!this.evidenceRequired},
    busy(){return this.submitting||this.uploading||this.scanning},
    canWrite(){return this.pageState==='ready'&&!this.hidden&&!this.historyMode&&!!this.context.batchId&&!!this.context.internshipId&&this.generation===currentSessionGeneration()}
  },
  onLoad(options={}){this.requestedBatchId=String(options.batchId||'');this.loadList()},
  onShow(){
    const wasHidden=this.hidden;this.hidden=false
    if(this.selectingEvidence&&this.generation===currentSessionGeneration()){const resume=this.resumeEvidence;this.resumeEvidence=null;resume?.();return}
    const resume=this.resumeEvidence;this.resumeEvidence=null;resume?.()
    if(wasHidden||this.generation!==currentSessionGeneration())this.loadList()
  },
  onHide(){this.hidden=true;if(!this.selectingEvidence)this.epoch++},
  onUnload(){this.hidden=true;this.epoch++;this.selectingEvidence=false;const resume=this.resumeEvidence;this.resumeEvidence=null;resume?.();this.context={};this.list=[];this.resetDraft();this.receipt=null},
  onPullDownRefresh(){if(this.busy)return uni.stopPullDownRefresh();this.loadList().finally(()=>uni.stopPullDownRefresh())},
  methods:{
    formatTime:formatDateTime,
    statusLabel(status){return ({PENDING:'待审核',APPROVED:'已通过',REJECTED:'已驳回',WITHDRAWN:'已撤回'})[status]||'状态待确认'},
    typeLabel(type){return MAKEUP_TYPES.find(item=>item.value===type)?.label||'补卡类型待确认'},
    capture(){return {epoch:this.epoch,generation:currentSessionGeneration(),batchId:this.context.batchId,internshipId:this.context.internshipId}},
    current(t,allowPicker=false){return (!this.hidden||(allowPicker&&this.selectingEvidence))&&t.epoch===this.epoch&&t.generation===currentSessionGeneration()&&t.batchId===this.context.batchId&&t.internshipId===this.context.internshipId},
    resetDraft(){this.form=blank();this.pendingEvidence=null;this.makeupTypeIndex=0;this.formVisible=false;this.formError=''},
    async loadList(){
      const generation=currentSessionGeneration(),epoch=++this.epoch,current=()=>!this.hidden&&epoch===this.epoch&&generation===currentSessionGeneration()
      if(this.generation!==generation){this.resetDraft();this.context={};this.receipt=null}
      this.generation=generation;this.pageState='loading';this.errorMessage='';this.list=[];this.submitting=false;this.uploading=false;this.scanning=false;this.selectingEvidence=false
      try{
        const dashboard=await studentApi.getInternship(this.requestedBatchId);if(!current())return
        const context={batchId:String(dashboard?.batchId||''),internshipId:String(dashboard?.recordId||dashboard?.internshipId||'')}
        if(this.context.batchId&&(context.batchId!==this.context.batchId||context.internshipId!==this.context.internshipId)){this.resetDraft();this.receipt=null}
        this.context=context;this.historyMode=dashboard?.historyMode===true
        if(!context.batchId||!context.internshipId){this.pageState='empty';this.errorMessage='当前没有可用实习记录，请先核对批次安排。';return}
        const rows=await studentInternshipMakeups(context.batchId,context.internshipId);if(!current())return
        const items=Array.isArray(rows)?rows:rows?.items;if(!Array.isArray(items))throw Error('invalid makeup list')
        this.list=items;this.pageState='ready'
      }catch(error){if(current()){this.errorMessage=normalizeError(error).text;this.pageState='error'}}
    },
    async refreshList(t){
      try{const rows=await studentInternshipMakeups(t.batchId,t.internshipId);if(!this.current(t))return;const items=Array.isArray(rows)?rows:rows?.items;if(!Array.isArray(items)||!items.some(row=>String(row.id)===String(this.receipt?.id)))throw Error('missing receipt');this.list=items}
      catch(error){if(this.current(t))this.errorMessage='补卡办理已登记，列表回读未完成，请重新读取；无需重复提交。'}
    },
    openApply(){if(!this.canWrite||this.busy)return;this.formVisible=true;this.formError=''},
    closeForm(){if(!this.busy)this.formVisible=false},
    onMakeupType(event){if(!this.canWrite||this.busy)return;this.makeupTypeIndex=Number(event.detail.value)||0;this.form.makeupType=MAKEUP_TYPES[this.makeupTypeIndex]?.value||'MISSING'},
    onDate(event){if(this.canWrite&&!this.busy)this.form.checkinDate=event.detail.value},
    async chooseEvidence(){
      if(!this.canWrite||this.busy)return
      const t=this.capture(),form=this.form;this.uploading=true;this.selectingEvidence=true;this.formError=''
      try{
        const file=await chooseSingleFile();if(!file||!this.current(t,true)||this.form!==form)return
        if(this.hidden)await new Promise(resolve=>{this.resumeEvidence=resolve})
        if(!this.current(t)||this.form!==form)return
        this.selectingEvidence=false
        if(Number(file.size||0)>20*1024*1024)return toast('单个证据文件不能超过20兆字节')
        const uploaded=await uploadBusinessFile(file,{bizType:'INTERNSHIP',bizId:''})
        if(!this.current(t)||this.form!==form)return
        if(!uploaded?.fileId)throw Error('missing evidence file')
        this.pendingEvidence=normalizeFileReadiness({...uploaded,fileName:uploaded.fileName||file.name||'补卡证据'})
        form.evidenceFileId=this.pendingEvidence.readyForBusiness?this.pendingEvidence.fileId:'';form.fileName=this.pendingEvidence.fileName
        toast(this.pendingEvidence.readyForBusiness?'补卡证据安全可用':'证明已接收，请等待安全检查并刷新状态')
      }catch(error){if(this.current(t,true)&&this.form===form)this.formError=normalizeError(error).text}
      finally{if(t.epoch===this.epoch&&t.generation===currentSessionGeneration()&&this.form===form){this.uploading=false;this.selectingEvidence=false;this.resumeEvidence=null}}
    },
    async refreshEvidence(){
      if(!this.canWrite||this.busy||!this.pendingEvidence)return
      const t=this.capture(),form=this.form,original=this.pendingEvidence,current=()=>this.current(t)&&this.form===form&&this.pendingEvidence===original
      this.scanning=true;this.formError=''
      try{const rows=await refreshFileReadiness([original],id=>fileSdk.metadata(id),current);if(!rows)return;this.pendingEvidence=rows[0];form.evidenceFileId=rows[0].readyForBusiness?rows[0].fileId:''}
      catch(error){if(current()){this.pendingEvidence={...original,readyForBusiness:false,statusText:'安全状态读取失败，请重试'};form.evidenceFileId='';this.formError='证明安全检查结果读取失败，日期、原因和已上传文件均已保留。'}}
      finally{if(this.current(t)&&this.form===form)this.scanning=false}
    },
    async submit(){
      if(!this.canWrite||this.busy)return
      if(!this.form.checkinDate||this.form.reason.trim().length<5)return toast('请填写缺卡日期与详细事由（不少于5字）')
      if(!this.evidenceReady){this.formError=this.pendingEvidence?'证明尚未安全可用，请刷新安全状态后提交。':this.evidenceRuleText;return}
      const t=this.capture(),form=this.form;this.submitting=true;this.formError='';this.errorMessage=''
      try{
        const result=await studentInternshipMakeupApply({batchId:t.batchId,internshipId:t.internshipId,checkinDate:form.checkinDate,reason:form.reason.trim(),makeupType:form.makeupType,evidenceFileId:form.evidenceFileId||''})
        if(!this.current(t)||this.form!==form)return
        if(!result?.id)throw Error('invalid makeup receipt')
        this.receipt=result;toast('补卡申请已登记');this.resetDraft();await this.refreshList(t)
      }catch(error){if(this.current(t)){const shown=normalizeError(error);this.formError=shown.text+(['network','unknown'].includes(shown.kind)?'。请先核对补卡记录，勿重复申请。':'');toast(this.formError)}}
      finally{if(this.current(t))this.submitting=false}
    },
    withdraw(item){
      if(!this.canWrite||this.busy||item?.status!=='PENDING')return
      const t=this.capture(),id=String(item.id),version=item.version
      uni.showModal({title:'撤回补卡',content:'确认撤回该待审核补卡申请？',success:async result=>{
        if(!result.confirm||!this.current(t)||!this.canWrite||this.busy)return
        this.submitting=true;this.errorMessage=''
        try{const updated=await studentInternshipMakeupWithdraw(id,{batchId:t.batchId,internshipId:t.internshipId,expectedVersion:version});if(!this.current(t))return;if(String(updated?.id)!==id)throw Error('invalid makeup receipt');this.receipt=updated;toast('补卡已撤回');await this.refreshList(t)}
        catch(error){if(this.current(t))this.errorMessage=normalizeError(error).text}
        finally{if(this.current(t))this.submitting=false}
      }})
    }
  }
}
</script>

<style scoped>
.lv__hint{display:block;margin-top:8rpx;color:var(--text-secondary);font-size:var(--font-size-base);line-height:1.5}.lv__item{margin-bottom:16rpx}.lv__range{font-weight:600;color:var(--text-primary)}.lv__days{display:block;margin-top:8rpx;color:var(--text-secondary);font-size:var(--font-size-base)}.lv__reason{display:block;margin-top:8rpx;color:var(--text-secondary);font-size:var(--font-size-base);line-height:1.5}.lv__meta{display:block;margin-top:6rpx;color:var(--text-tertiary);font-size:var(--font-size-base)}.lv__review{margin-top:12rpx;padding:16rpx 18rpx;border-radius:12rpx;background:var(--warning-50,#fff7ed)}.lv__review-title{display:block;font-size:var(--font-size-base);font-weight:600;color:var(--warning-800,#9a3412)}.lv__review-text{display:block;margin-top:5rpx;font-size:var(--font-size-base);line-height:1.5}.lv__withdraw{margin-top:16rpx}.lv__mask{position:fixed;inset:0;background:rgba(0,0,0,.45);z-index:99;display:flex;align-items:flex-end}.lv__sheet{width:100%;border-radius:24rpx 24rpx 0 0;padding:32rpx;max-height:88vh;overflow-y:auto;box-sizing:border-box}.lv__field{margin-top:24rpx}.lv__label{display:block;margin-bottom:8rpx;color:var(--text-secondary);font-size:var(--font-size-base)}.lv__req{color:#c0392b}.lv__picker,.lv__textarea{background:var(--bg-soft,#f5f6f8);border-radius:12rpx;padding:20rpx}.lv__textarea{width:100%;min-height:160rpx;box-sizing:border-box}.lv__evidence{padding:20rpx;border:1px solid var(--border-base);border-radius:14rpx;background:var(--gray-50)}.lv__evidence.required{border-color:var(--warning-400,#fb923c);background:var(--warning-50,#fff7ed)}.lv__rule{display:block;color:var(--text-secondary);font-size:var(--font-size-base);line-height:1.45}.lv__upload{margin-top:14rpx}.lv__actions{display:flex;gap:16rpx;margin-top:32rpx}
.lv__receipt{border-color:var(--success-200,#bbf7d0);background:var(--success-50,#f0fdf4)}.lv__receipt-title{color:var(--success-800,#166534);font-size:28rpx;font-weight:600}.lv__receipt-close{color:var(--success-700,#15803d);font-size:var(--font-size-base)}.lv__receipt-next{display:block;margin-top:8rpx;color:var(--success-700,#15803d);font-size:var(--font-size-base);line-height:1.5}
.lv__refresh{align-self:flex-end;min-height:44px;margin:0;padding:0 8px;background:transparent;border:0;color:var(--text-link);font-size:var(--font-size-base);line-height:44px}.lv__refresh::after{border:0}.lv__picker{min-height:44px;box-sizing:border-box}.lv__sheet{padding-bottom:calc(16px + env(safe-area-inset-bottom))}.lv__receipt-close{min-height:44px;display:flex;align-items:center}</style>
