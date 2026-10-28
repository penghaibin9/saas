<template>
  <ModulePageShell class="tr-page" :title="managed ? '教师本人报告台账' : '我的指导报告'" subtitle="按当前批次填写或查看教师本人周报、月报和总结，保存后同步到学校台账。" :watermark="false">
    <div class="tr-toolbar">
      <label>报告类型<select v-model="typeFilter" :disabled="busy" @change="filterChanged"><option value="">全部</option><option v-for="type in types" :key="type.value" :value="type.value">{{ type.label }}</option></select></label>
      <span>共 {{ total }} 份报告</span><AppButton variant="ghost" :disabled="loading || busy" @click="load">刷新</AppButton>
      <AppButton variant="ghost" :disabled="loading || busy || !batchId || !canExport" @click="exportReports">导出报告正文</AppButton>
      <AppButton v-if="!managed && canSave" :disabled="busy || loading" @click="newReport">填写新报告</AppButton>
    </div>
    <p v-if="exportFile" class="tr-receipt" role="status"><a :href="exportFile.url" :download="exportFile.filename">下载已生成报告（{{ exportFile.rowCount }}份）</a>。文件包含生成时的正文与版本，修改后请重新导出。</p>
    <p v-if="receipt" class="tr-receipt" role="status">{{ receipt.typeLabel }}已保存，第{{ receipt.edition }}版。学校管理人员可在教师本人报告台账查看；电脑与移动端读取同一份记录。</p>
    <ErrorState v-if="error" :description="error" @retry="load"/><LoadingState v-else-if="loading"/>
    <div v-else class="tr-workspace">
      <section class="tr-list"><h2>{{ managed ? '当前批次报告' : '我已提交的报告' }}</h2>
        <p v-if="!rows.length">当前条件暂无报告。</p>
        <button v-for="row in rows" :key="row.id" class="tr-item" :class="{selected:selectedId===row.id}" :disabled="busy" @click="selectReport(row)">
          <strong>{{ row.typeLabel }} · {{ row.periodLabel }}</strong><span v-if="managed">{{ row.teacherName }}</span><span>第{{ row.edition }}版 · {{ formatDateTime(row.submittedAt) }}</span>
        </button>
        <div class="tr-actions"><AppButton variant="ghost" :disabled="busy || page<=1" @click="changePage(-1)">上一页</AppButton><span>第{{ page }}页</span><AppButton variant="ghost" :disabled="busy || page*20>=total" @click="changePage(1)">下一页</AppButton></div>
      </section>
      <section class="tr-form">
        <template v-if="managed"><p v-if="!selected">选择一份报告查看正文和附件。</p><template v-else><h2>{{ selected.teacherName }} · {{ selected.typeLabel }}</h2><p>{{ selected.periodLabel }} · 第{{ selected.edition }}版</p><p class="tr-content">{{ selected.content }}</p><p class="tr-content">问题与风险：{{ selected.issueContent || '未填写' }}</p><p class="tr-content">下一步计划：{{ selected.nextPlan || '未填写' }}</p><p>涉及学生：{{ selected.studentCount ?? '未填写' }}</p></template></template>
        <template v-else>
          <h2>{{ selectedId ? (editingExisting ? '修改原报告' : '已保存的本人报告') : '填写本人报告' }}</h2><p v-if="!canSave">当前身份只有查看权限，请切换到有提交权限的教师身份。</p>
          <fieldset v-if="canEdit" :disabled="busy || !batchId">
            <label>报告类型<select v-model="form.reportType" :disabled="!!selectedId" @change="typeChanged"><option v-for="type in types" :key="type.value" :value="type.value">{{ type.label }}</option></select></label>
            <label v-if="form.reportType!=='SUMMARY'">{{ form.reportType==='WEEKLY'?'报告周次':'报告月份' }}<input v-model="form.periodKey" :type="form.reportType==='WEEKLY'?'week':'month'" :disabled="!!selectedId"/></label><p v-else>当前批次实习总结</p>
            <label>工作正文<textarea v-model="form.content" placeholder="填写本周期指导工作、办理结果和学生问题跟进情况" :maxlength="maximum" rows="9"/></label><span>{{ wordCount }}字；至少{{ minimum }}字，最多{{ maximum }}字</span>
            <label>问题与风险（选填）<textarea v-model="form.issueContent" maxlength="4000" rows="3"/></label>
            <label>下一步计划（选填）<textarea v-model="form.nextPlan" maxlength="4000" rows="3"/></label>
            <label>涉及学生人数（选填）<input v-model="form.studentCount" type="number" min="0" max="2147483647" step="1"/></label>
          </fieldset>
          <div v-else-if="selected" class="tr-readonly"><p>{{ selected?.periodLabel }} · 第{{ selected?.edition }}版</p><h3>工作正文</h3><p class="tr-content">{{ form.content || '未填写' }}</p><template v-if="form.issueContent"><h3>问题与风险</h3><p class="tr-content">{{ form.issueContent }}</p></template><template v-if="form.nextPlan"><h3>下一步计划</h3><p class="tr-content">{{ form.nextPlan }}</p></template><p v-if="form.studentCount != null && form.studentCount !== ''">涉及学生：{{ form.studentCount }}</p></div>
        </template>
        <div v-if="!managed || selected" class="tr-files"><h3>照片与附件（{{ attachments.length }}/9）</h3>
          <div v-for="file in attachments" :key="file.fileId" class="tr-file"><span>{{ file.fileName || '报告附件' }} · {{ attachmentStatus(file) }}</span><AppButton variant="ghost" size="sm" :disabled="busy" @click="preview(file)">查看附件</AppButton><AppButton variant="ghost" size="sm" :disabled="busy || file.readyForBusiness !== true || !file.canDownload" @click="downloadAttachment(file)">下载附件</AppButton><AppButton v-if="canEdit" variant="ghost" size="sm" :disabled="busy" @click="removeAttachment(file.fileId)">移除</AppButton></div>
          <AppButton v-if="attachments.length" variant="ghost" :disabled="busy" @click="refreshAttachments">{{ refreshingFiles ? '正在读取安全检查结果…' : '刷新附件安全检查' }}</AppButton>
          <p v-if="attachments.length && !attachmentsReady">附件安全检查尚未完成或状态未确认，请刷新检查结果；正文与已上传附件会保留。</p>
          <template v-if="canEdit"><input ref="fileInput" type="file" hidden multiple accept=".png,.jpg,.jpeg,.gif,.rar,.zip,.doc,.docx,.pdf,.xls,.xlsx" @change="uploadAttachments"/><AppButton variant="ghost" :disabled="busy || attachments.length>=9" @click="$refs.fileInput?.click()">{{ uploading ? '附件上传中…' : '添加照片或附件' }}</AppButton><p>最多9个附件，支持图片、压缩包和办公文档；安全检查未完成时保留输入并提示重试。</p></template>
        </div>
        <FilePreviewer v-if="previewFile" :file="previewFile" inline :provider="previewProvider" :allow-download="previewFile.readyForBusiness === true && previewFile.canDownload" :download-handler="downloadAttachment" @error="fileError"/>
        <p v-if="formError" class="tr-error" role="alert">{{ formError }}</p>
        <div v-if="!managed && canSave" class="tr-actions"><AppButton v-if="selectedId && !editingExisting" :disabled="busy" @click="editReport">修改原报告</AppButton><template v-else><AppButton :disabled="busy || !batchId || !attachmentsReady" @click="save">{{ saving ? '保存中…' : '保存本人报告' }}</AppButton><AppButton v-if="selectedId" variant="ghost" :disabled="busy" @click="cancelEdit">取消修改</AppButton></template></div>
      </section>
    </div>
  </ModulePageShell>
</template>
<script>
import { ModulePageShell, ErrorState, LoadingState } from '@/components/business'
import { AppButton } from '@/components/ui'
import FilePreviewer from '@/components/file/FilePreviewer.vue'
import { internshipApi } from '@/modules/internship/api/internship.api'
import { useInternshipBatchStore } from '@/stores/internshipBatch'
import { canCode } from '@/modules/internship/composables/permission'
import { fileSdk } from '@/services/file/fileSdk'
import { currentSessionGeneration } from '@/services/http/client'
import { normalizeUiError } from '@/utils/presentationSafety'
import { formatDateTime } from '@/utils/dateUtils'
import { prepareXlsxDownload } from '@/utils/xlsxDownload'
import { teacherReportTypes, teacherReportView, reportValidation } from '@/modules/internship/services/teacherReportPresentation.mjs'
function blank(){return {reportType:'WEEKLY',periodKey:'',content:'',issueContent:'',nextPlan:'',studentCount:'',attachments:[],expectedVersion:null}}
function unwrap(r){if(r?.code!==0)throw r;return r.data}
export default {
  components:{ModulePageShell,ErrorState,LoadingState,AppButton,FilePreviewer},props:{ctx:{type:Object,required:true}},
  data:()=>({types:teacherReportTypes,typeFilter:'',page:1,total:0,rows:[],rules:{},form:blank(),editingExisting:false,selectedId:'',selected:null,receipt:null,exportFile:null,loading:false,saving:false,uploading:false,exporting:false,refreshingFiles:false,downloading:false,error:'',formError:'',previewFile:null,previewProvider:{fetchBytes:descriptor=>fileSdk.blob(descriptor.fileId),dispose(){}},fileSequence:0,epoch:0,sequence:0,disposed:false}),
  computed:{batchStore(){return useInternshipBatchStore()},batchId(){return String(this.batchStore.selectedBatchId||'')},managed(){return this.$route.meta.managedTeacherReports===true},canSave(){return !this.managed && canCode(this.ctx,'internship.guidance.manage')},canEdit(){return this.canSave && (!this.selectedId || this.editingExisting)},canExport(){return this.managed?canCode(this.ctx,'internship.stats.export'):canCode(this.ctx,'internship.guidance.view')},busy(){return this.saving||this.uploading||this.exporting||this.refreshingFiles||this.downloading},attachmentsReady(){return this.attachments.every(file=>file.readyForBusiness===true)},attachments(){return this.managed?(this.selected?.attachments||[]):this.form.attachments},minimum(){return this.types.find(t=>t.value===this.form.reportType)?.minimum||30},maximum(){return this.rules[this.types.find(t=>t.value===this.form.reportType)?.maximumKey]||12000},wordCount(){return Array.from(this.form.content.trim()).length}},
  watch:{'batchStore.selectedBatchId':{immediate:true,handler(){this.reset();this.load()}},'ctx.ctxKey'(){this.reset();this.load()},'$route.meta.managedTeacherReports'(){this.reset();this.load()}},
  beforeUnmount(){this.disposed=true;this.reset()},
  methods:{formatDateTime,
    editReport(){if(this.busy || !this.canSave || !this.selectedId)return;this.editingExisting=true;this.formError=''},
    cancelEdit(){if(this.busy)return;if(this.selected)return this.selectReport(this.selected);this.newReport()},
    attachmentStatus(file){if(file.readyForBusiness===true)return '安全可用';return (['PENDING','RUNNING','INFECTED','ERROR'].includes(file.scanStatus) && fileSdk.statusText?.[file.scanStatus]) || '安全检查状态待确认'},
    async refreshAttachments(){
      if(this.busy || !this.attachments.length)return
      const current=this.fence(),sequence=++this.fileSequence,files=[...this.attachments]
      const replace=items=>{if(this.managed)this.selected={...this.selected,attachments:items};else this.form.attachments=items}
      replace(files.map(file=>({...file,readyForBusiness:false,canDownload:false})))
      this.refreshingFiles=true;this.formError='';this.previewFile=null
      try{
        const result=await Promise.all(files.map(async file=>{const meta=await fileSdk.metadata(file.fileId);if(String(meta?.fileId)!==String(file.fileId))throw new Error('附件状态编号不一致');return {...file,...meta,fileId:String(file.fileId)}}))
        if(current() && sequence===this.fileSequence)replace(result)
      }catch(e){if(current() && sequence===this.fileSequence)this.formError='附件安全检查状态读取失败，正文与附件已保留，请重试刷新'}
      finally{if(current() && sequence===this.fileSequence)this.refreshingFiles=false}
    },
    async downloadAttachment(file){
      if(this.busy || !this.attachments.some(item=>String(item.fileId)===String(file.fileId)))return
      const current=this.fence(),sequence=this.fileSequence
      this.downloading=true;this.formError=''
      try{
        const meta=await fileSdk.metadata(file.fileId)
        if(!current() || sequence!==this.fileSequence)return
        if(String(meta?.fileId)!==String(file.fileId) || meta.readyForBusiness!==true || !meta.canDownload){this.formError='附件尚未安全可用或当前账号无下载权限，请刷新附件安全检查';return}
        await fileSdk.download(String(meta.fileId),meta.fileName||file.fileName||'报告附件')
      }catch(e){if(current() && sequence===this.fileSequence)this.formError=normalizeUiError(e).userMessage}
      finally{if(current())this.downloading=false}
    },
    clearExport(){if(this.exportFile?.url)URL.revokeObjectURL(this.exportFile.url);this.exportFile=null},
    reset(){this.clearExport();this.fileSequence++;this.epoch++;this.sequence++;this.rows=[];this.total=0;this.page=1;this.rules={};this.form=blank();this.editingExisting=false;this.selectedId='';this.selected=null;this.receipt=null;this.previewFile=null;this.formError='';this.error='';this.saving=false;this.uploading=false;this.exporting=false;this.refreshingFiles=false;this.downloading=false},
    fence(){const epoch=this.epoch,generation=currentSessionGeneration(),batch=this.batchId,managed=this.managed;return ()=>!this.disposed && epoch===this.epoch && generation===currentSessionGeneration() && batch===this.batchId && managed===this.managed},
    params(){return {batchId:this.batchId,reportType:this.typeFilter||undefined,page:this.page,pageSize:20}},
    async load(){if(!this.batchId){this.loading=false;this.error='请先选择实习批次';return}const current=this.fence(),sequence=++this.sequence;this.loading=true;this.error='';try{const data=unwrap(await internshipApi.getTeacherPeriodReports(this.params(),this.managed));if(!current() || sequence!==this.sequence)return;this.rows=(data.items||[]).map(teacherReportView);this.total=data.total;this.rules=data.rules||{};if(this.selectedId){const selected=this.rows.find(r=>r.id===this.selectedId);if(selected)this.selected=selected}}catch(e){if(current() && sequence===this.sequence){this.rows=[];this.error=normalizeUiError(e).userMessage}}finally{if(current() && sequence===this.sequence)this.loading=false}},
    filterChanged(){if(this.busy)return;this.page=1;this.newReport();this.load()},
    changePage(direction){if(this.busy)return;this.page+=direction;this.newReport();this.load()},
    newReport(){if(this.busy)return;this.fileSequence++;this.form=blank();this.editingExisting=false;this.selectedId='';this.selected=null;this.previewFile=null;this.formError=''},
    typeChanged(){if(this.busy || !this.canEdit)return;this.form.periodKey=this.form.reportType==='SUMMARY'?'SUMMARY':''},
    selectReport(row){if(this.busy)return;this.fileSequence++;this.editingExisting=false;this.selectedId=row.id;this.selected=row;this.previewFile=null;this.formError='';if(!this.managed)this.form={reportType:row.reportType,periodKey:row.periodKey,content:row.content,issueContent:row.issueContent||'',nextPlan:row.nextPlan||'',studentCount:row.studentCount??'',expectedVersion:row.version,attachments:[...row.attachments]};if(this.attachments.length)return this.refreshAttachments()},
    removeAttachment(id){if(this.busy || !this.canEdit)return;this.fileSequence++;this.previewFile=null;this.form.attachments=this.form.attachments.filter(f=>f.fileId!==id)},
    async uploadAttachments(event){const files=Array.from(event.target.files||[]);event.target.value='';if(this.busy || !this.canEdit || !files.length)return;if(this.attachments.length+files.length>9){this.formError='报告附件最多上传9个';return}const current=this.fence();this.uploading=true;this.formError='';try{for(const file of files){const uploaded=await fileSdk.upload(file,{bizType:'INTERNSHIP_REPORT',clientType:'ADMIN_PC'}).promise;if(!current())return;if(!uploaded?.fileId)throw {message:'附件上传结果不完整'};this.form.attachments.push({...uploaded,fileId:String(uploaded.fileId),fileName:uploaded.fileName||file.name})}}catch(e){if(current())this.formError=normalizeUiError(e).userMessage}finally{if(current())this.uploading=false}},
    async preview(file){if(this.busy)return;const current=this.fence(),sequence=++this.fileSequence;this.formError='';this.previewFile=null;try{const result=await fileSdk.metadata(file.fileId);if(current() && sequence===this.fileSequence)this.previewFile=result}catch(e){if(current() && sequence===this.fileSequence)this.formError=normalizeUiError(e).userMessage}},
    fileError(e){this.formError=normalizeUiError(e).userMessage},
    async save(){if(this.busy || !this.canEdit)return;this.formError=reportValidation(this.form,this.rules);if(this.formError)return;const current=this.fence(),f=this.form;if(this.attachments.length){await this.refreshAttachments();if(!current())return;if(!this.attachmentsReady){this.formError=this.formError||'附件安全检查尚未完成，正文与附件已保留，请刷新检查结果后再保存';return}}this.saving=true;this.receipt=null;try{const body={batchId:this.batchId,reportType:f.reportType,periodKey:f.reportType==='SUMMARY'?'SUMMARY':f.periodKey,content:f.content.trim(),issueContent:f.issueContent.trim(),nextPlan:f.nextPlan.trim(),studentCount:f.studentCount===''?null:Number(f.studentCount),attachmentFileIds:f.attachments.map(x=>x.fileId)};if(f.expectedVersion!==null)body.expectedVersion=f.expectedVersion;const row=teacherReportView(unwrap(await internshipApi.saveTeacherPeriodReport(body)));if(!current())return;this.clearExport();this.receipt=row;this.form=blank();this.editingExisting=false;this.selectedId='';this.selected=null;this.previewFile=null;await this.load()}catch(e){if(current())this.formError=e?.bizCode==='DATA_CONFLICT'?'这份报告已发生变化，输入已保留。请先刷新列表核对最新版本，再决定是否重新修改。':normalizeUiError(e).userMessage}finally{if(current())this.saving=false}},
    async exportReports(){if(this.busy || !this.canExport)return;const current=this.fence();this.exporting=true;this.formError='';try{const data=unwrap(await internshipApi.exportTeacherPeriodReports(this.params(),this.managed));if(current()){this.clearExport();this.exportFile=prepareXlsxDownload(data)}}catch(e){if(current())this.formError=normalizeUiError(e).userMessage}finally{if(current())this.exporting=false}}
  }
}
</script>
<style scoped>
.tr-page{padding:24px;box-sizing:border-box}@media(max-width:900px){.tr-page{padding:16px}}
.tr-toolbar,.tr-actions,.tr-file{display:flex;align-items:center;gap:12px;flex-wrap:wrap}.tr-toolbar{margin-bottom:20px}.tr-workspace{display:grid;grid-template-columns:280px minmax(0,1fr);gap:24px}.tr-list,.tr-form{border:1px solid #e0e6ef;border-radius:12px;padding:20px;background:#fff;min-width:0}.tr-item{display:flex;flex-direction:column;gap:8px;width:100%;text-align:left;padding:16px 10px;background:white;border:0;border-bottom:1px solid #e5e9ef;cursor:pointer;line-height:1.6}.tr-item.selected{background:#edf4ff;border-left:3px solid #2861ca}.tr-item span{font-size:12px;color:#677386}.tr-form label{display:flex;flex-direction:column;gap:8px;margin-bottom:18px;font-size:14px}.tr-form input,.tr-form textarea,.tr-form select,.tr-toolbar select{border:1px solid #ccd6e6;border-radius:7px;padding:10px;font:inherit;box-sizing:border-box;min-width:0;width:100%}.tr-toolbar label{display:flex;align-items:center;gap:10px}.tr-toolbar select{width:120px}.tr-form fieldset{border:0;padding:0;margin:0;min-width:0}.tr-files{margin:24px 0}.tr-file{padding:8px 0}.tr-file span{overflow-wrap:anywhere;flex:1}.tr-files p,.tr-form fieldset>span{color:#677386;font-size:13px}.tr-content{white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.8}.tr-error{color:#ad3c25;line-height:1.7}.tr-receipt{padding:15px;background:#edf8f0;border-left:4px solid #318c58;line-height:1.7;margin-bottom:18px}@media(max-width:900px){.tr-workspace{grid-template-columns:1fr}.tr-form,.tr-list{padding:16px}}
</style>
