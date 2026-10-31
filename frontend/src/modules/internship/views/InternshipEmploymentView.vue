<template>
  <ModulePageShell title="就业上报" :watermark="false">
    <div class="employment-toolbar"><AppSelect v-model="status" :options="statuses" :disabled="processing" @change="changeFilter"/><span>共 {{ total }} 份登记</span><AppButton variant="ghost" :disabled="loading || processing" @click="load">刷新</AppButton><AppExportButton :export-fn="exportLedger" :has-permission="canExport" :disabled="loading || processing || !!error">导出当前筛选台账（脱敏）</AppExportButton></div>
    <p class="employment-hint">实习老师先核对登记材料，再由就业老师正式审批。正式审批通过后进入就业台账；导出仅含当前筛选的最新提交版，敏感信息已隐藏。</p>
    <div v-if="receipt" class="employment-receipt">{{ receipt.status==='RETURNED'?'已退回，待学生补正重交。':'实习预审已通过，已转交就业老师正式审批。' }}</div>
    <ErrorState v-if="error" :description="error" @retry="load"/><LoadingState v-else-if="loading"/>
    <div v-else class="employment-workspace">
      <section class="employment-queue"><h2>登记队列</h2><p v-if="!rows.length">当前筛选暂无登记。</p><button v-for="row in rows" :key="row.id" type="button" class="employment-object" :class="{'selected':selectedId===row.id}" :disabled="processing" @click="open(row.id)"><strong>{{ row.current?.fields?.studentName || '学生' }} · {{ row.current?.fields?.studentNo || '学号待核实' }}</strong><span>{{ row.statusLabel }} · 第 {{ row.revisionCount }} 版</span><span>{{ row.current?.fields?.companyName || '单位待核实' }} · {{ row.current?.fields?.positionName || '岗位待核实' }}</span></button><div class="employment-pager"><AppButton variant="ghost" :disabled="page<=1 || processing" @click="changePage(-1)">上一页</AppButton><span>第 {{ page }} 页</span><AppButton variant="ghost" :disabled="!hasMore || processing" @click="changePage(1)">下一页</AppButton></div></section>
      <section class="employment-detail"><LoadingState v-if="detailLoading"/><ErrorState v-else-if="detailError && !detail" :description="detailError" @retry="select(selectedId,true)"/><p v-else-if="!detail">请选择一份登记。</p>
        <template v-else><header><h2>{{ detail.current.fields.studentName }}的就业登记</h2><p>编号 {{ detail.id }} · {{ detail.statusLabel }} · 第 {{ detail.revisionCount }} 版</p></header><p v-if="detailError" class="employment-warning" role="alert">{{ detailError }}</p><p v-if="!canReview" class="employment-hint">当前身份只有查看权限，实习预审由具备权限的指导教师办理。</p>
          <section v-if="detail.formalSubmission" class="employment-review"><h3>就业正式审批</h3><p>{{ detail.statusLabel }}</p><p v-if="detail.formalSubmission.returnReason">审批意见：{{ detail.formalSubmission.returnReason }}</p><p v-if="detail.formalSubmission.empStudentId">已登记就业台账，编号 {{ detail.formalSubmission.empStudentId }}</p></section>
          <div v-if="!detail.sensitiveVisible" class="employment-disclose"><p>敏感信息已隐藏。</p><template v-if="canDisclose"><label>核验用途<input v-model="purpose" class="employment-input" maxlength="200" :disabled="processing" placeholder="核验用途，至少5字"/></label><AppButton variant="ghost" :disabled="processing || purpose.trim().length<5" @click="disclose">查看完整登记</AppButton></template></div>
          <section v-for="group in detail.current.fieldGroups" :key="group.label"><h3>{{ group.label }}</h3><p class="employment-hint">{{ group.source }}</p><dl class="employment-fields"><div v-for="field in group.fields" :key="field.key"><dt>{{ field.label }}</dt><dd>{{ field.value }}<small v-if="field.sourceLabel!==group.source">{{ field.sourceLabel }}</small></dd></div></dl></section><p>{{ detail.current.modeLabel }} · {{ formatDateTime(detail.current.submittedAt) }}</p><p v-if="detail.current.correctionReason">更正说明：{{ detail.current.correctionReason }}</p>
          <AppFilePreview v-if="detail.sensitiveVisible" :files="previewFiles(detail.current.attachments)" :downloadable="false" @preview="preview"/>
          <p v-if="fileLoading" role="status">正在读取就业佐证…</p><p v-if="fileError" class="employment-warning" role="alert">{{ fileError }}</p>
          <FilePreviewer v-if="previewFile" :key="previewFile.fileId" :file="previewFile" inline :provider="previewProvider" :allow-download="false" @error="fileError=normalizeUiError($event).userMessage"/>
          <p v-if="detail.status==='RETURNED' && detail.current.review" class="employment-review">退回原因：{{ detail.current.review.comment }}</p>
          <div v-if="canReview && (detail.status==='SUBMITTED' || (detailError && comment))" class="employment-review-form"><label>{{ detail.status==='SUBMITTED'?'审核意见':'本次未提交的审核意见' }}<textarea v-model="comment" class="employment-input reason" maxlength="1000" :disabled="processing" :readonly="detail.status!=='SUBMITTED'" placeholder="预审通过可填写核对说明；退回需不少于5字的补正要求"/></label><p v-if="detail.status==='SUBMITTED' && !detail.sensitiveVisible" class="employment-hint">请先查看完整材料，核对后再审核。</p><div v-if="detail.status==='SUBMITTED'" class="employment-actions"><AppButton variant="primary" :disabled="processing || !detail.sensitiveVisible" @click="review('APPROVE')">预审通过并转交就业</AppButton><AppButton variant="ghost" :disabled="processing || !detail.sensitiveVisible || comment.trim().length<5" @click="review('RETURN')">退回补正</AppButton></div></div>
          <h3>提交与审核历史</h3><details v-for="version in detail.history" :key="version.id" class="employment-history"><summary>第 {{ version.revisionNo }} 版 · {{ formatDateTime(version.submittedAt) }} · {{ version.review?.actionLabel || '待实习老师核对' }}</summary><p v-if="version.review">{{ version.review.reviewerName }}：{{ version.review.comment || '实习预审通过' }}</p><p v-if="version.review?.formalSubmission">就业正式审批：{{ formalOutcome(version.review.formalSubmission) }}<span v-if="version.review.formalSubmission.returnReason">；审批意见：{{ version.review.formalSubmission.returnReason }}</span></p><p v-if="version.correctionReason">更正说明：{{ version.correctionReason }}</p><section v-for="group in version.fieldGroups" :key="group.label"><h4>{{ group.label }}</h4><p class="employment-hint">{{ group.source }}</p><dl class="employment-fields"><div v-for="field in group.fields" :key="field.key"><dt>{{ field.label }}</dt><dd>{{ field.value }}<small v-if="field.sourceLabel!==group.source">{{ field.sourceLabel }}</small></dd></div></dl></section><AppFilePreview v-if="detail.sensitiveVisible" :files="previewFiles(version.attachments)" :downloadable="false" @preview="preview"/></details>
        </template>
      </section>
    </div>
  </ModulePageShell>
</template>
<script>
import { ModulePageShell, LoadingState, ErrorState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppSelect, AppFilePreview, AppExportButton } from '@/components/common'
import { internshipApi } from '@/modules/internship/api/internship.api'
import { useInternshipBatchStore } from '@/stores/internshipBatch'
import { canCode } from '@/modules/internship/composables/permission'
import { currentSessionGeneration } from '@/services/http/client'
import { normalizeUiError } from '@/utils/presentationSafety'
import { formatDateTime } from '@/utils/dateUtils'
import { fileSdk } from '@/services/file/fileSdk'
import FilePreviewer from '@/components/file/FilePreviewer.vue'
import { employmentView, employmentStatuses } from '@/modules/internship/services/employmentPresentation.mjs'

function unwrap(response){if(response?.code!==0)throw response;return response.data}
export default {
  components:{ModulePageShell,LoadingState,ErrorState,AppButton,AppSelect,AppFilePreview,AppExportButton,FilePreviewer},props:{ctx:{type:Object,required:true}},
  data:()=>({statuses:employmentStatuses,status:'SUBMITTED',page:1,total:0,hasMore:false,rows:[],loading:false,error:'',
    selectedId:'',detail:null,detailError:'',detailLoading:false,purpose:'',comment:'',processing:false,receipt:null,epoch:0,loadSequence:0,detailSequence:0,disposed:false,
    previewFile:null,fileError:'',fileLoading:false,fileSequence:0,previewProvider:{fetchBytes:descriptor=>fileSdk.blob(descriptor.fileId),dispose(){}}}),
  computed:{batchStore(){return useInternshipBatchStore()},canReview(){return canCode(this.ctx,'internship.employment.review')},canDisclose(){return canCode(this.ctx,'internship.employment.sensitive.view')},canExport(){return canCode(this.ctx,'internship.employment.view') && canCode(this.ctx,'internship.stats.export')}},
  watch:{'batchStore.selectedBatchId':{immediate:true,handler(){this.reset();this.readRoute();this.load()}},'ctx.ctxKey'(){this.reset();this.load()},'$route.query':{deep:true,handler(){this.reset();this.readRoute();this.load()}}},
  beforeUnmount(){this.disposed=true;this.reset()},
  methods:{
    formatDateTime,
    formalOutcome(submission){return employmentView({status:'APPROVED',formalSubmission:submission}).statusLabel},
    normalizeUiError,
    async exportLedger(){
      if(!this.canExport || this.loading || this.processing || this.error || !this.batchStore.selectedBatchId)throw new Error('请先加载有权限的就业台账再导出');
      const current=this.fence(),sequence=this.loadSequence,status=this.status,record=this.$route.query.internshipId||undefined,ctxKey=this.ctx.ctxKey;
      const result=await internshipApi.exportEmploymentRegistrations({batchId:String(this.batchStore.selectedBatchId),status,internshipId:record});
      if(!current() || sequence!==this.loadSequence || status!==this.status || record!==(this.$route.query.internshipId||undefined) || ctxKey!==this.ctx.ctxKey || !this.canExport)throw new Error('当前查询范围已变化，请在新范围重新导出');
      return result
    },
    clearFile(){this.fileSequence++;this.previewFile=null;this.fileError='';this.fileLoading=false},
    reset(){this.epoch++;this.loadSequence++;this.detailSequence++;this.rows=[];this.detail=null;this.selectedId='';this.purpose='';this.comment='';this.processing=false;this.detailLoading=false;this.receipt=null;this.error='';this.detailError='';this.clearFile()},
    readRoute(){this.status=employmentStatuses.some(x=>x.value===this.$route.query.status)?this.$route.query.status:'SUBMITTED';this.page=/^[1-9]\d{0,4}$/.test(String(this.$route.query.page||''))?Number(this.$route.query.page):1;this.selectedId=String(this.$route.query.registrationId||'')},
    changeFilter(){this.$router.replace({query:{...this.$route.query,status:this.status,page:'1',registrationId:undefined}})},
    changePage(direction){if(this.processing || (direction<0 && this.page<=1) || (direction>0 && !this.hasMore))return;this.$router.replace({query:{...this.$route.query,status:this.status,page:String(this.page+direction),registrationId:undefined}})},
    open(id){if(this.processing)return;this.$router.replace({query:{...this.$route.query,registrationId:String(id),status:this.status,page:String(this.page)}})},
    fence(){const epoch=this.epoch,generation=currentSessionGeneration(),batch=String(this.batchStore.selectedBatchId),id=this.selectedId,sequence=this.detailSequence;return ()=>!this.disposed && epoch===this.epoch && generation===currentSessionGeneration() && batch===String(this.batchStore.selectedBatchId) && id===this.selectedId && sequence===this.detailSequence},
    async load(){const sequence=++this.loadSequence,generation=currentSessionGeneration(),batch=String(this.batchStore.selectedBatchId),epoch=this.epoch,current=()=>!this.disposed && sequence===this.loadSequence && generation===currentSessionGeneration() && batch===String(this.batchStore.selectedBatchId) && epoch===this.epoch;
      this.loading=true;this.error='';this.detail=null;this.clearFile();
      if(!batch){this.rows=[];this.loading=false;this.error='请先在顶部选择实习批次';return}
      try{const data=unwrap(await internshipApi.listEmploymentRegistrations({batchId:batch,status:this.status,page:this.page,pageSize:20,internshipId:this.$route.query.internshipId||undefined}));if(!current())return;
        this.rows=(data.items||[]).map(employmentView);this.total=data.total;this.hasMore=!!data.hasMore;this.loading=false;if(this.selectedId)await this.select(this.selectedId,true)
      }catch(e){if(current()){this.rows=[];this.error=normalizeUiError(e).userMessage}}finally{if(current())this.loading=false}
    },
    async select(id,keepComment=false){if(this.processing || this.disposed || !id)return;this.selectedId=String(id);const sequence=++this.detailSequence,current=this.fence();this.detailLoading=true;this.detail=null;this.detailError='';this.purpose='';this.clearFile();if(!keepComment)this.comment='';
      try{const data=employmentView(unwrap(await internshipApi.getEmploymentRegistration(id)));if(!current() || sequence!==this.detailSequence)return;
        if(data.id!==this.selectedId || data.batchId!==String(this.batchStore.selectedBatchId) || (this.$route.query.internshipId && data.internshipId!==String(this.$route.query.internshipId)))throw {code:404001,message:'登记不属于当前实习记录'};this.detail=data;if(this.receipt?.id===data.id && this.receipt.version!==data.version)this.receipt=null
      }catch(e){if(current())this.detailError=normalizeUiError(e).userMessage}finally{if(current())this.detailLoading=false}
    },
    async disclose(){if(!this.detail || this.processing || !this.canDisclose || this.purpose.trim().length<5)return;const current=this.fence();this.processing=true;this.detailError='';try{const data=employmentView(unwrap(await internshipApi.discloseEmploymentRegistration(this.detail.id,this.purpose.trim())));if(current())this.detail=data}catch(e){if(current())this.detailError=normalizeUiError(e).userMessage}finally{if(current())this.processing=false}},
    async review(action){if(this.processing || !this.canReview || !this.detail?.sensitiveVisible || this.detail.status!=='SUBMITTED' || (action==='RETURN' && this.comment.trim().length<5))return;const current=this.fence(),row=this.detail;this.processing=true;this.detailError='';
      try{const data=employmentView(unwrap(await internshipApi.reviewEmploymentRegistration(row.id,{action,comment:this.comment.trim(),expectedVersion:row.version,submissionId:row.current.id})));if(!current())return;this.receipt=data;this.detail=data;this.comment='';this.purpose='';this.processing=false;await this.load()}
      catch(e){if(current()){this.detailError=normalizeUiError(e).userMessage;if(Number(e?.code)===409001 || e?.bizCode==='DATA_CONFLICT' || Number(e?.httpStatus)===409){this.processing=false;await this.select(row.id,true);this.detailError='登记已变化，审核意见已保留，请重新核对最新材料。'}}}finally{if(current())this.processing=false}
    },
    previewFiles(files){return (files||[]).map(x=>({...x,id:String(x.fileId),name:x.fileName||'就业佐证照片',type:'image',sensitive:true}))},
    async preview(file){if(!this.detail?.sensitiveVisible || this.processing || !this.canDisclose)return;this.clearFile();const sequence=this.fileSequence,current=this.fence();this.fileLoading=true;
      try{const meta=await fileSdk.metadata(file.fileId||file.id);if(!current() || sequence!==this.fileSequence)return;
        if(String(meta.fileId)!==String(file.fileId||file.id) || (file.sha256 && file.sha256!==meta.sha256))throw {message:'照片内容已变化，请重新读取登记后核对'};
        this.previewFile=meta
      }catch(e){if(current() && sequence===this.fileSequence)this.fileError=normalizeUiError(e).userMessage}finally{if(current() && sequence===this.fileSequence)this.fileLoading=false}
    }
  }
}
</script>
<style scoped>
.employment-toolbar{flex-wrap:wrap}.employment-toolbar :deep(select){width:220px}.employment-toolbar>span{white-space:nowrap}.employment-toolbar :deep(.app-select){width:auto}

.employment-toolbar{display:flex;gap:16px;align-items:center;margin-bottom:16px}.employment-workspace{display:grid;grid-template-columns:minmax(260px,320px) minmax(0,1fr);gap:20px}.employment-queue,.employment-detail{border:1px solid var(--border-base,#e5e9f0);border-radius:12px;padding:20px;background:var(--bg-card,#fff);min-width:0}.employment-object{display:flex;flex-direction:column;gap:8px;width:100%;padding:15px 10px;text-align:left;background:#fff;border:0;border-bottom:1px solid #e7ebf0;font-size:14px;cursor:pointer;overflow-wrap:anywhere}.employment-object.selected{background:#eef5ff;border-left:3px solid var(--brand-primary,#245acb)}.employment-object span{font-size:13px;color:#5b6574}.employment-pager{display:flex;gap:10px;align-items:center;justify-content:center;margin-top:20px;font-size:13px}.employment-fields{display:grid;grid-template-columns:1fr 1fr;gap:14px 24px}.employment-fields div{display:flex;flex-direction:column;gap:6px;min-width:0}.employment-fields dt{font-size:13px;color:#677386}.employment-fields dd{margin:0;font-size:14px;overflow-wrap:anywhere;line-height:1.7}.employment-fields small{display:block;color:#8490a2;font-size:12px}.employment-disclose{background:#f4f7fc;padding:16px;border-radius:8px;margin:16px 0;display:flex;flex-direction:column;align-items:flex-start;gap:12px;font-size:13px}.employment-input{display:block;width:100%;box-sizing:border-box;border:1px solid #dce2ec;border-radius:8px;padding:10px;margin-top:8px;font:inherit;min-width:300px}.reason{height:100px}.employment-hint{color:#6f7b8d;font-size:13px;line-height:1.7}.employment-review{padding:14px;background:#eef5ff;line-height:1.7}.employment-review-form{margin-top:20px}.employment-actions{display:flex;gap:12px;margin:16px 0}.employment-warning{color:#ad4e00}.employment-history{border-top:1px solid #e5e9f0;padding:16px 0}.employment-history summary{cursor:pointer;font-weight:600;font-size:14px}.employment-receipt{padding:16px;margin-bottom:18px;background:#edf8f1;border-left:4px solid #278b5f;line-height:1.7}@media(max-width:1100px){.employment-workspace{grid-template-columns:250px minmax(0,1fr)}.employment-fields{grid-template-columns:1fr}}@media(max-width:760px){.employment-workspace{grid-template-columns:1fr}.employment-toolbar{flex-wrap:wrap}.employment-input{min-width:0}}
</style>
