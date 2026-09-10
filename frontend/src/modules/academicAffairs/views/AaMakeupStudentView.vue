<template>
  <ModulePageShell title="重修免修申请" subtitle="选择本人课程，核对申请依据后提交">
    <div class="aamks-tabs">
      <button :class="['aamks-tab', { 'is-active': tab === 'retake' }]" :disabled="saving || !!pending || uploading" @click="switchTab('retake')">我的重修</button>
      <button :class="['aamks-tab', { 'is-active': tab === 'exemption' }]" :disabled="saving || !!pending || uploading" @click="switchTab('exemption')">我的免修</button>
    </div>

    <AppInlineAlert
      v-if="options.identityDebtCount"
      type="warning"
      :title="`${options.identityDebtCount}条历史成绩暂不可办理`"
      description="这些记录缺少完整课程和修读信息，请联系教务处核对。"
    />

    <div class="aamks-application"><AppSectionCard :title="tab === 'retake' ? '提交重修报名' : '提交免修申请'">
      <div class="aamks-form">
        <label class="aamks-field">
          <span>{{ tab === 'retake' ? '挂科成绩' : '目标课程版本' }}</span>
          <select v-if="tab === 'retake'" v-model="form.gradeId" class="aamks-select" :disabled="saving || !!pending || uploading">
            <option value="">请选择当前有效挂科成绩</option>
            <option v-for="item in options.retakeOptions" :key="item.gradeId" :value="item.gradeId">
              {{ optionLabel(item, true) }}
            </option>
          </select>
          <select v-else v-model="form.courseId" class="aamks-select" :disabled="saving || !!pending || uploading">
            <option value="">请选择课程具体版本</option>
            <option v-for="item in options.exemptionOptions" :key="item.courseId" :value="item.courseId">
              {{ optionLabel(item, false) }}
            </option>
          </select>
        </label>
        <label class="aamks-field">
          <span>申请理由</span>
          <AppTextarea v-model="form.reason" placeholder="选填；说明本次申请情况" :disabled="saving || !!pending || uploading" />
        </label>
        <AppInlineAlert v-if="formError" type="danger" :description="formError" />
        <AppInlineAlert
          v-if="tab === 'exemption'"
          type="info"
          description="免修终审通过后生成计学分、不计分数的正式成绩；如附佐证材料，须核对安全状态后提交。"
        />
        <div v-if="tab === 'exemption'" class="aamks-field"><label>佐证材料（最多3份，每份不超过10MB）<input type="file" :disabled="saving || !!pending || uploading || materials.length >= 3" @change="pickMaterial" /></label><span v-if="uploading">正在上传或核对材料…</span><ul><li v-for="file in materials" :key="file.fileId">{{ file.fileName }} · {{ file.readyForBusiness ? '安全可用' : '需重新核对安全状态' }} <button :disabled="saving || !!pending || uploading" @click="refreshMaterial(file)">核对</button> <button :disabled="saving || !!pending || uploading" @click="removeMaterial(file)">移除</button></li></ul></div>
        <p v-if="selectedOption">本次对象：{{ optionLabel(selectedOption,tab === 'retake') }}</p>
        <div class="aamks-actions">
          <AppButton variant="primary" :loading="saving" :disabled="!canSubmit" @click="openConfirm">提交申请</AppButton>
        </div>
      </div>
    </AppSectionCard><aside class="aamks-conditions"><h3>提交条件</h3><p>{{ isStudent ? '当前为学生本人入口' : '请使用学生本人身份办理' }}</p><p>{{ selectedOption ? '已选定正式课程对象' : '请选择本人课程' }}</p><p v-if="selectedOption && tab === 'retake'">原正式分数：{{ selectedOption.score ?? '待核对' }}</p><p v-if="tab === 'exemption'">{{ !materials.length ? '本次未附材料，请核对申请依据' : materials.every(f => f.readyForBusiness) ? '材料安全检查已就绪，提交前再次核对' : '请核对佐证材料安全状态' }}</p><p>登记申请后进入学校审批；申请回执不等于修读完成或已取得学分。</p></aside></div>

    <section v-if="receipt" class="aamks-receipt" role="status"><strong>{{ receipt.verified ? '本人申请已登记' : '结果待核实' }}</strong><p>{{ receipt.courseName }} · {{ receipt.verified ? academicStatusLabel(receipt.status) : '请勿重复提交' }}</p><AppButton v-if="pending" :disabled="saving" :loading="checking" @click="verifyApply">只读核对本人申请</AppButton></section>
    <AppInlineAlert v-if="readError" type="danger" :description="readError" />
    <AppButton v-if="readError" :disabled="saving || !!pending" @click="reload();loadOptions()">重新读取</AppButton>
    <LoadingState v-if="loading" />
    <EmptyState v-else-if="!rows.length" :title="tab === 'retake' ? '暂无重修申请' : '暂无免修申请'" description="上方选择正式成绩或课程版本后提交" />
    <ul v-else class="aamks-list">
      <li v-for="row in rows.slice(0,visibleCount)" :key="row.applyId || row.exemptionId">
        <div>
          <div class="mp-cell-main">{{ row.courseName }}</div>
          <div class="mp-cell-sub">{{ row.termCode || '' }}<template v-if="row.retakeCount"> · 第{{ row.retakeCount }}次重修</template></div>
        </div>
        <StatusTag :type="stType(row.status)" :label="academicStatusLabel(row.status)" dot />
      </li>
    </ul>
    <AppButton v-if="visibleCount < rows.length" @click="visibleCount += 20">显示更多申请</AppButton>
    <AppConfirmDialog v-model:visible="confirmVisible" title="确认提交本人申请" :message="confirmMessage" :submitting="saving" :confirm-disabled="!!pending" @confirm="submitApply" />
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, StatusTag, LoadingState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppTextarea, AppInlineAlert, AppSectionCard, AppConfirmDialog } from '@/components/common'
import { academicAffairsMakeupApi as api } from '@/modules/academicAffairs/api/academic-affairs.api'
import { gradeIdentityApi } from '@/modules/academicAffairs/api/grade-identity.api'
import { academicStatusLabel } from '@/modules/academicAffairs/constants/academic-display.constants'
import { currentUserFromToken } from '@/services/http/client'
import fileSdk from '@/services/file/fileSdk'
import { gradeError } from './parallel-c/grade-review'

export default {
  name: 'AaMakeupStudentView',
  components: { ModulePageShell, StatusTag, LoadingState, EmptyState, AppButton, AppTextarea, AppInlineAlert, AppSectionCard, AppConfirmDialog },
  props:{ctx:{type:Object,default:()=>({})}},
  data() {
    return {
      alive:true,scopeSeq:0,readSeq:0,optionSeq:0,fileSeq:0,uploadTask:null,uploading:false,materials:[],
      pending:null,receipt:null,checking:false,command:null,confirmVisible:false,readError:'',visibleCount:20,
      tab: 'retake', loading: true, rows: [], loadingOptions: false,
      options: { retakeOptions: [], exemptionOptions: [], identityDebtCount: 0 },
      form: { gradeId: '', courseId: '', reason: '', materialFileIds: [] },
      formError: '', saving: false
    }
  },
  computed: {
    identityKey(){const u=currentUserFromToken()||{};return JSON.stringify([u.tenantId,u.userId,u.userType,u.activeContextId,u.currentRoleCode,this.ctx.currentRole,this.ctx.dataScope])},
    isStudent(){return String(currentUserFromToken()?.userType||'').toUpperCase()==='STUDENT'},
    selectedOption(){return (this.tab==='retake'?this.options.retakeOptions:this.options.exemptionOptions)?.find(r=>String(this.tab==='retake'?r.gradeId:r.courseId)===String(this.tab==='retake'?this.form.gradeId:this.form.courseId))||null},
    canSubmit(){return this.isStudent&&!this.saving&&!this.pending&&!this.uploading&&!this.loadingOptions&&!!this.selectedOption&&(this.tab==='retake'||this.materials.every(f=>f.readyForBusiness===true))},
    confirmMessage(){return this.command ? `${this.command.tab==='retake'?'重修报名':'免修申请'} · ${this.command.option.courseName}。提交只登记申请，后续按学校审批结果办理。` : ''}
  },
  created(){this.reload();this.loadOptions()},
  watch:{identityKey(){this.invalidate();this.reload();this.loadOptions()},'form.gradeId'(){if(!this.saving&&!this.pending)this.cancelConfirm()},'form.courseId'(){if(!this.saving&&!this.pending)this.cancelConfirm()}},
  beforeUnmount(){this.alive=false;this.invalidate()},
  methods:{
    academicStatusLabel,
    capture(){return {identity:this.identityKey,seq:this.scopeSeq,tab:this.tab}},
    current(c){return this.alive&&c.identity===this.identityKey&&c.seq===this.scopeSeq&&c.tab===this.tab},
    cancelConfirm(){this.command=null;this.confirmVisible=false},
    invalidate(){this.scopeSeq++;this.readSeq++;this.optionSeq++;this.fileSeq++;this.uploadTask?.cancel();this.uploadTask=null;this.uploading=false;this.materials=[];this.form={gradeId:'',courseId:'',reason:'',materialFileIds:[]};this.options={retakeOptions:[],exemptionOptions:[],identityDebtCount:0};this.rows=[];this.visibleCount=20;this.loading=false;this.loadingOptions=false;this.pending=null;this.receipt=null;this.checking=false;this.saving=false;this.readError='';this.formError='';this.cancelConfirm()},
    fail(err,fallback){if(/403|FORBIDDEN|NO_PERMISSION/.test(String(err?.bizCode||err?.code||'')))this.invalidate();this.readError=gradeError(err,fallback||'读取失败，请重新核对。')},
    stType(status){return ['APPROVED','ENROLLED','FINISHED'].includes(status)?'success':status==='REJECTED'?'danger':'primary'},
    optionLabel(item,includeAttempt){return `${item.courseName} · ${item.courseCode||'课程编码待核对'} · ${item.courseVersion==null?'版本待核对':`版本${item.courseVersion}`}${includeAttempt?` · ${item.attemptNo==null?'修读次数待核对':`第${item.attemptNo}次修读`} · ${item.score??'—'}分`:''}`},
    switchTab(key){if(this.saving||this.pending||this.uploading||this.tab===key)return;this.invalidate();this.tab=key;this.reload();this.loadOptions()},
    async loadOptions(){
      const c=this.capture(),seq=++this.optionSeq,valid=()=>this.current(c)&&seq===this.optionSeq
      this.loadingOptions=true
      try{const res=await gradeIdentityApi.myMakeupOptions();if(!valid())return;if(res?.code!==0)throw res;this.options={retakeOptions:[],exemptionOptions:[],identityDebtCount:0,...res.data}}
      catch(err){if(valid()){this.options={retakeOptions:[],exemptionOptions:[],identityDebtCount:0};this.fail(err,'本人课程读取失败，请重试。')}}finally{if(valid())this.loadingOptions=false}
    },
    async readMy(tab){const res=await (tab==='retake'?api.retakeMy:api.exemptionMy)();if(res?.code!==0)throw res;return res.data?.items||[]},
    async reload(){
      if(this.saving||this.pending)return
      const c=this.capture(),seq=++this.readSeq,valid=()=>this.current(c)&&seq===this.readSeq
      this.loading=true;this.readError='';this.rows=[];this.visibleCount=20
      try{const rows=await this.readMy(c.tab);if(valid())this.rows=rows}catch(err){if(valid())this.fail(err)}finally{if(valid())this.loading=false}
    },
    async pickMaterial(event){
      const file=event.target.files?.[0];event.target.value=''
      if(!file||this.tab!=='exemption'||this.saving||this.pending||this.uploading||this.materials.length>=3)return
      if(file.size>10*1024*1024){this.formError='单份材料不能超过10MB。';return}
      const c=this.capture(),seq=++this.fileSeq,valid=()=>this.current(c)&&seq===this.fileSeq
      this.uploading=true;this.formError='';this.cancelConfirm()
      try{this.uploadTask=fileSdk.upload(file,{bizType:'AA_EXEMPTION'});const uploaded=await this.uploadTask.promise;if(!valid())return;if(!uploaded.fileId)throw {code:503};const meta=await fileSdk.metadata(uploaded.fileId);if(!valid())return;this.materials.push({...meta,fileId:String(uploaded.fileId),fileName:meta.fileName||file.name})}
      catch(err){if(valid()){this.formError=gradeError(err,'材料上传或安全核对失败，请重试。');if(/403|NO_PERMISSION|FORBIDDEN/.test(String(err?.bizCode||err?.code||'')))this.fail(err)}}finally{if(valid()){this.uploading=false;this.uploadTask=null}}
    },
    async refreshMaterial(file){
      if(this.saving||this.pending||this.uploading)return
      const c=this.capture(),seq=++this.fileSeq;this.uploading=true
      try{const meta=await fileSdk.metadata(file.fileId);if(!this.current(c)||seq!==this.fileSeq)return;const index=this.materials.findIndex(f=>String(f.fileId)===String(file.fileId));if(index>=0)this.materials.splice(index,1,{...meta,fileId:String(file.fileId),fileName:meta.fileName||file.fileName})}
      catch(err){if(this.current(c)&&seq===this.fileSeq)this.fail(err,'材料状态核对失败。')}finally{if(this.current(c)&&seq===this.fileSeq)this.uploading=false}
    },
    removeMaterial(file){if(this.saving||this.pending||this.uploading)return;this.materials=this.materials.filter(f=>String(f.fileId)!==String(file.fileId));this.cancelConfirm()},
    openConfirm(){
      if(!this.canSubmit)return
      const option={...this.selectedOption},id=this.tab==='retake'?option.gradeId:option.courseId
      if((typeof id==='number'&&!Number.isSafeInteger(id))||!/^\d+$/.test(String(id))){this.formError='课程对象无法准确读取，请刷新候选。';return}
      const body=this.tab==='retake'?{gradeId:String(id),reason:this.form.reason.trim()}:{courseId:String(id),reason:this.form.reason.trim(),materialFileIds:this.materials.map(f=>String(f.fileId))}
      this.command={...this.capture(),option,body,replyId:null};this.confirmVisible=true
    },
    async submitApply(){
      const c=this.command;if(!c||!this.current(c)||!this.canSubmit)return
      this.saving=true;this.formError=''
      try{
        const options=await gradeIdentityApi.myMakeupOptions();if(!this.current(c))return;if(options?.code!==0)throw options
        const key=c.tab==='retake'?'gradeId':'courseId',option=(c.tab==='retake'?options.data?.retakeOptions:options.data?.exemptionOptions)?.find(r=>String(r[key])===String(c.option[key]))
        if(!option||['courseCode','courseVersion','attemptNo','score'].some(k=>option[k]!==c.option[k]))throw {code:409}
        if(c.tab==='exemption')for(const fileId of c.body.materialFileIds){const meta=await fileSdk.metadata(fileId);if(!this.current(c))return;if(meta.readyForBusiness!==true)throw {code:422}}
        this.pending=c;this.receipt={courseName:c.option.courseName,verified:false}
        let res;try{res=await (c.tab==='retake'?api.retakeApply:api.exemptionApply)(c.body)}catch(err){res=err}
        if(!this.current(c))return
        if(res?.code!==0&&/403|404|409|422|NO_PERMISSION|FORBIDDEN|CONFLICT|VALIDATION/.test(String(res?.bizCode||res?.code||''))){this.pending=null;this.receipt=null;throw res}
        c.replyId=res?.code===0?(c.tab==='retake'?res.data?.applyId:res.data?.exemptionId):null
        await this.verifyApply()
      }catch(err){if(this.current(c)){this.formError=gradeError(err,'申请结果待核实，请核对本人记录。');if(!this.pending)this.formError=gradeError(err,'申请尚未提交，请重新核对课程和材料。');if(/403|NO_PERMISSION|FORBIDDEN/.test(String(err?.bizCode||err?.code||'')))this.fail(err)}}finally{if(this.current(c))this.saving=false}
    },
    async verifyApply(){
      const c=this.pending;if(!c||!this.current(c)||this.checking)return
      this.checking=true
      try{const rows=await this.readMy(c.tab);if(!this.current(c))return;this.rows=rows
        const key=c.tab==='retake'?'applyId':'exemptionId',formal=c.replyId&&rows.find(r=>String(r[key])===String(c.replyId))
        if(!formal||String(formal.reason||'').trim()!==c.body.reason){this.formError='结果待核实：未能从本人记录准确关联本次申请，请勿重复提交。';return}
        this.receipt={courseName:c.option.courseName,status:formal.status,verified:true};this.pending=null;this.confirmVisible=false;this.command=null;this.formError='';this.form={gradeId:'',courseId:'',reason:'',materialFileIds:[]};this.materials=[]
      }catch(err){if(this.current(c))this.fail(err,'结果待核实，请稍后只读核对。')}finally{if(this.current(c))this.checking=false}
    }
  }
}
</script>

<style scoped>
.aamks-application{display:grid;grid-template-columns:minmax(0,1fr) 280px;gap:16px}.aamks-conditions{padding:18px;border:1px solid var(--border-200, #e1e7ef);border-radius:8px;background:var(--bg-white, #fff)}.aamks-conditions p{font-size:13px;line-height:1.8}@media(max-width:950px){.aamks-application{grid-template-columns:1fr}}
.aamks-receipt { padding:16px;border:1px solid var(--border-200, #e1e7ef);border-radius:8px;margin-top:16px; }
.aamks-tabs { display: flex; gap: 4px; border-bottom: 1px solid var(--border-color, #e5e7eb); margin-bottom: 12px; }
.aamks-tab { padding: 8px 16px; border: none; background: none; cursor: pointer; font-size: 14px; color: var(--text-secondary, #64748b); border-bottom: 2px solid transparent; }
.aamks-tab.is-active { color: var(--primary-color, #2563eb); border-bottom-color: var(--primary-color, #2563eb); font-weight: 600; }
.aamks-form { display: grid; gap: 14px; }
.aamks-field { display: grid; gap: 6px; font-size: 13px; color: var(--text-700, #4e5969); }
.aamks-select { min-height: 38px; padding: 0 10px; border: 1px solid var(--border-300, #d0d3d9); border-radius: 7px; background: #fff; }
.aamks-actions { display: flex; justify-content: flex-end; }
.aamks-list { list-style: none; margin: 12px 0 0; padding: 0; display: flex; flex-direction: column; gap: 8px; }
.aamks-list li { display: flex; justify-content: space-between; align-items: center; padding: 10px 12px; background: var(--fill-light, #f8fafc); border-radius: 8px; }
</style>
