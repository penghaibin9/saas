<template>
  <view class="page-wrap teacher-employment">
    <MobileGlobalState :state="state" :description="error" @retry="load">
      <view class="page-pad stack">
        <view class="card stack"><text class="card-title">就业上报审核</text><text>核对本人指导或授权范围内学生的就业信息，退回时写明补正要求。</text><picker :range="batchLabels" :value="batchIndex" :disabled="busy" @change="changeBatch"><text class="filter">{{ context.selectedBatch?.name || context.selectedBatch?.batchName || '请选择批次' }} ▾</text></picker><picker :range="statusLabels" :value="statusIndex" :disabled="busy" @change="changeStatus"><text class="filter">{{ statusLabels[statusIndex] }} · 共 {{ total }} 份</text></picker><button class="minor" :disabled="busy" @click="load">刷新当前队列</button></view>
        <view v-if="receipt" class="card receipt"><text>登记 {{ receipt.id }} · {{ receipt.statusLabel }}</text><text>审核结果已保存并通知学生{{ receipt.status==='RETURNED'?'补正后在原登记上重交':'查看核验结果'}}。</text></view>
        <view class="card stack"><text class="card-title">本批次登记</text><text v-if="!rows.length">当前筛选暂无登记。</text><view v-for="row in rows" :key="row.id" class="queue" @click="select(row.id)"><text>{{ row.current?.fields?.studentName || '学生' }} · {{ row.current?.fields?.studentNo || '学号待核实' }}</text><text>{{ row.statusLabel }} · 第 {{ row.revisionCount }} 版</text><text class="hint">{{ row.current?.fields?.companyName || '单位待核实' }} · {{ row.current?.fields?.positionName || '岗位待核实' }}</text></view><view class="pager"><button class="minor" :disabled="page<=1 || busy" @click="changePage(-1)">上一页</button><text>第 {{ page }} 页</text><button class="minor" :disabled="!hasMore || busy" @click="changePage(1)">下一页</button></view></view>
        <view v-if="detailLoading" class="card">正在读取登记材料…</view>
        <view v-if="detailError" class="card warning"><text>{{ detailError }}</text><button class="minor" @click="select(selectedId)">重试读取登记</button></view>
        <view v-if="detail" class="card stack"><text class="card-title">{{ detail.current.fields.studentName }}的就业登记</text><text>编号：{{ detail.id }} · {{ detail.statusLabel }} · 第 {{ detail.revisionCount }} 版</text><text v-if="!canReview" class="hint">当前身份可以查看，审核由具备审核权限的指导教师处理。</text>
          <view v-if="!detail.sensitiveVisible" class="stack"><text class="hint">联系方式、地址、协议等已隐藏，完整材料只用于本次核验，查看会留痕。</text><input v-if="canDisclose" v-model="purpose" class="input" maxlength="200" placeholder="说明本次核验用途，至少5字" :disabled="busy" /><button v-if="canDisclose" class="minor" :disabled="busy || purpose.trim().length<5" @click="disclose">说明用途并查看完整登记</button></view>
          <view v-for="field in detail.current.fieldRows" :key="field.key" class="field"><text class="label">{{ field.label }}</text><text>{{ field.value }}</text><text class="hint">{{ field.sourceLabel }}</text></view>
          <text class="hint">{{ detail.current.modeLabel }} · {{ formatDateTime(detail.current.submittedAt) }}</text><text v-if="detail.current.correctionReason">更正说明：{{ detail.current.correctionReason }}</text>
          <button v-for="photo in detail.current.attachments" :key="photo.fileId" class="minor" :disabled="!detail.sensitiveVisible || busy" @click="openPhoto(photo)">查看{{ photo.fileName || '就业佐证照片' }}</button>
          <text v-if="detail.current.review" class="review">{{ detail.current.review.actionLabel }} · {{ detail.current.review.reviewerName }}：{{ detail.current.review.comment || '已核验' }}</text>
          <view v-if="detail.status==='SUBMITTED' && canReview" class="stack"><text class="label">审核意见</text><textarea v-model="comment" class="input reason" maxlength="1000" placeholder="通过可填写核验说明；退回需不少于5字的补正要求" :disabled="busy" /><text v-if="!detail.sensitiveVisible" class="hint">请先查看完整材料，核对后再审核。</text><view class="actions"><button class="approve" :disabled="busy || !detail.sensitiveVisible" @click="review('APPROVE')">核验通过</button><button class="return" :disabled="busy || !detail.sensitiveVisible || comment.trim().length<5" @click="review('RETURN')">退回补正</button></view></view>
        </view>
        <view v-if="detail" class="card stack"><text class="card-title">提交与审核历史</text><view v-for="version in detail.history" :key="version.id" class="history"><text>第 {{ version.revisionNo }} 版 · {{ formatDateTime(version.submittedAt) }}</text><text v-if="version.review">{{ version.review.actionLabel }} · {{ version.review.reviewerName }}：{{ version.review.comment || '已核验' }}</text><button class="minor" @click="expandedId=expandedId===version.id?'':version.id">{{ expandedId===version.id?'收起':'查看本版材料' }}</button><view v-if="expandedId===version.id" class="stack"><text v-for="field in version.fieldRows" :key="field.key" class="history-field">{{ field.label }}：{{ field.value }}</text><button v-for="photo in version.attachments" :key="photo.fileId" class="minor" :disabled="!detail.sensitiveVisible || busy" @click="openPhoto(photo)">查看{{ photo.fileName || '本版照片' }}</button></view></view></view>
        <ReportFilePreview ref="photos" />
      </view>
    </MobileGlobalState>
  </view>
</template>
<script>
import { teacherApi } from '@/services/teacherApi'
import { useInternshipContextStore } from '@/stores/internshipContext'
import { normalizeError } from '@/services/request'
import { currentSessionGeneration } from '@/services/sessionGeneration.mjs'
import { employmentView, employmentStatuses } from '@/services/employmentPresentation.mjs'
import { formatDateTime } from '@/utils/format'
import ReportFilePreview from '@/components/ReportFilePreview.vue'

export default {
  components:{ReportFilePreview},
  data:()=>({state:'loading',error:'',hidden:false,generation:currentSessionGeneration(),loadSequence:0,detailSequence:0,epoch:0,
    requestedBatch:'',requestedId:'',status:'SUBMITTED',page:1,total:0,hasMore:false,rows:[],detail:null,selectedId:'',detailLoading:false,detailError:'',
    purpose:'',comment:'',processing:false,receipt:null,expandedId:''}),
  computed:{context(){return useInternshipContextStore()},batchLabels(){return this.context.batches.map(x=>x.name||x.batchName||'实习批次')},batchIndex(){return Math.max(0,this.context.batches.findIndex(x=>String(x.id)===String(this.context.selectedBatchId)))},
    statusLabels(){return employmentStatuses.map(x=>x.label)},statusIndex(){return Math.max(0,employmentStatuses.findIndex(x=>x.value===this.status))},
    canReview(){return this.context.can('internship.employment.review')},canDisclose(){return this.context.can('internship.employment.sensitive.view')},busy(){return this.processing || this.detailLoading || this.state==='loading'}},
  onLoad(q){this.requestedBatch=String(q?.batchId||'');this.requestedId=String(q?.registrationId||'')},
  onShow(){this.hidden=false;if(this.generation!==currentSessionGeneration())this.resetAccount();this.load()},
  onHide(){this.pause()},onUnload(){this.pause();this.comment=''},
  methods:{
    formatDateTime,
    pause(){this.hidden=true;this.epoch++;this.loadSequence++;this.detailSequence++;this.detail=null;this.detailLoading=false;this.processing=false;this.purpose='';this.expandedId='';this.$refs.photos?.reset()},
    resetAccount(){this.epoch++;this.loadSequence++;this.detailSequence++;this.generation=currentSessionGeneration();this.rows=[];this.detail=null;this.selectedId='';this.requestedId='';this.requestedBatch='';this.comment='';this.purpose='';this.receipt=null;this.page=1;this.total=0;this.processing=false},
    clearSelection(){this.epoch++;this.detailSequence++;this.detail=null;this.selectedId='';this.requestedId='';this.comment='';this.purpose='';this.receipt=null;this.detailError='';this.expandedId='';this.$refs.photos?.reset()},
    changeBatch(e){if(this.busy)return;const batch=this.context.batches[Number(e.detail.value)];if(batch && this.context.selectBatch(batch.id)){this.requestedBatch=String(batch.id);this.page=1;this.clearSelection();this.rows=[];this.load()}},
    changeStatus(e){if(this.busy)return;this.status=employmentStatuses[Number(e.detail.value)]?.value||'ALL';this.page=1;this.clearSelection();this.load()},
    changePage(direction){if(this.busy || (direction<0 && this.page<=1) || (direction>0 && !this.hasMore))return;this.page+=direction;this.clearSelection();this.load()},
    async load(){
      const sequence=++this.loadSequence,generation=currentSessionGeneration(),current=()=>!this.hidden && generation===currentSessionGeneration() && sequence===this.loadSequence;
      this.state='loading';this.error='';this.detail=null;
      try{await this.context.load(true);if(!current())return;
        if(!this.context.can('internship.employment.view')){this.rows=[];this.state='forbidden';return}
        if(this.requestedBatch && !this.context.selectBatch(this.requestedBatch))throw {code:404001};
        let target=null;
        if(this.requestedId){target=employmentView(await teacherApi.getEmploymentRegistration(this.requestedId));if(!current())return;
          if((this.requestedBatch && target.batchId!==this.requestedBatch)||!this.context.selectBatch(target.batchId))throw {code:404001};this.selectedId=target.id;this.requestedId='';this.requestedBatch=target.batchId}
        const batch=String(this.context.selectedBatchId);if(!batch){this.rows=[];this.state='empty';this.error='暂无可用实习批次';return}
        const data=await teacherApi.getEmploymentRegistrations({batchId:batch,status:this.status,page:this.page,pageSize:20});if(!current() || String(this.context.selectedBatchId)!==batch)return;
        this.rows=(data.items||[]).map(employmentView);this.total=data.total;this.hasMore=!!data.hasMore;this.state='ready';
        if(target){this.detail=target;this.purpose=''}else if(this.selectedId)await this.select(this.selectedId,true);
      }catch(e){if(current()){const error=normalizeError(e);this.rows=[];this.detail=null;this.state=error.pageState||'error';this.error=error.text}}
    },
    async select(id,keepComment=false){if(this.processing || this.hidden)return;const target=String(id||'');if(!target)return;
      const sequence=++this.detailSequence,generation=currentSessionGeneration(),batch=String(this.context.selectedBatchId),epoch=this.epoch,
        current=()=>!this.hidden && sequence===this.detailSequence && generation===currentSessionGeneration() && epoch===this.epoch && batch===String(this.context.selectedBatchId);
      if(target!==this.selectedId || !keepComment)this.comment='';this.selectedId=target;this.detail=null;this.purpose='';this.expandedId='';this.detailError='';this.detailLoading=true;this.$refs.photos?.reset();
      try{const detail=employmentView(await teacherApi.getEmploymentRegistration(target));if(!current())return;if(detail.id!==target || detail.batchId!==batch)throw {code:404001};this.detail=detail;if(this.receipt?.id===detail.id && this.receipt.version!==detail.version)this.receipt=null}
      catch(e){if(current())this.detailError=normalizeError(e).text}finally{if(current())this.detailLoading=false}
    },
    fence(){const epoch=this.epoch,sequence=this.detailSequence,generation=currentSessionGeneration(),batch=String(this.context.selectedBatchId),id=this.selectedId;return ()=>!this.hidden && epoch===this.epoch && sequence===this.detailSequence && generation===currentSessionGeneration() && batch===String(this.context.selectedBatchId) && id===this.selectedId},
    async disclose(){if(!this.detail || this.busy || !this.canDisclose || this.purpose.trim().length<5)return;const current=this.fence();this.processing=true;this.detailError='';try{const data=employmentView(await teacherApi.discloseEmploymentRegistration(this.detail.id,this.purpose.trim()));if(current())this.detail=data}catch(e){if(current())this.detailError=normalizeError(e).text}finally{if(current())this.processing=false}},
    async openPhoto(photo){if(!this.detail?.sensitiveVisible || this.busy || !this.canDisclose)return;await this.$refs.photos?.open(photo)},
    async review(action){if(this.busy || !this.canReview || !this.detail?.sensitiveVisible || this.detail.status!=='SUBMITTED' || (action==='RETURN' && this.comment.trim().length<5))return;
      const current=this.fence(),row=this.detail;this.processing=true;this.detailError='';
      try{const data=employmentView(await teacherApi.reviewEmploymentRegistration(row.id,{action,comment:this.comment.trim(),expectedVersion:row.version,submissionId:row.current.id}));if(!current())return;
        this.receipt=data;this.detail=data;this.comment='';this.purpose='';this.processing=false;await this.load()
      }catch(e){if(current()){const error=normalizeError(e);this.detailError=error.text;if(error.kind==='conflict'){this.processing=false;await this.select(row.id,true);this.detailError='登记已变化，审核意见已保留，请重新核对最新材料。'}}}
      finally{if(current())this.processing=false}
    }
  }
}
</script>
<style scoped>
.teacher-employment{padding-bottom:30px}.filter{display:block;padding:10px;border:1px solid var(--border-base,#ddd);border-radius:8px}.hint{display:block;font-size:12px;color:var(--text-tertiary);line-height:1.6}.minor{font-size:13px;line-height:2;padding:4px 10px;margin:0;background:#f2f5f9;color:var(--brand-primary)}.queue{padding:12px 0;border-bottom:1px solid var(--border-base,#eee);display:flex;flex-direction:column;gap:7px;font-size:14px}.pager{display:flex;gap:12px;align-items:center;justify-content:center}.input{width:100%;height:44px;box-sizing:border-box;border:1px solid var(--border-base,#ddd);border-radius:8px;padding:10px;font-size:14px}.reason{height:110px}.field{display:flex;flex-direction:column;gap:5px;overflow-wrap:anywhere;font-size:14px;border-bottom:1px solid var(--border-base,#eee);padding-bottom:9px;line-height:1.6}.label{font-weight:600}.actions{display:flex;gap:10px}.actions button{flex:1;margin:0;font-size:14px}.approve{background:var(--brand-primary);color:#fff}.return{background:#fff1e8;color:#ad4e00}.warning{color:#ad4e00;line-height:1.6}.review{background:#eef5ff;padding:10px;line-height:1.6}.receipt{border-left:4px solid #278b5f;display:flex;flex-direction:column;gap:8px}.history{display:flex;flex-direction:column;gap:9px;padding-top:10px;border-top:1px solid var(--border-base,#eee)}.history-field{font-size:13px;line-height:1.6;overflow-wrap:anywhere}
</style>
