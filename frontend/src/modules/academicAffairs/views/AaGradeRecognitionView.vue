<template>
  <ModulePageShell
    title="成绩认定与替代"
    subtitle="核对原课程、目标课程和佐证材料，按正式认定结果办理"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton v-if="canManage" variant="primary" :disabled="saving || writeBlocked" @click="openCreate">代录认定申请</AppButton>
    </template>

    <div class="aarn-bar">
      <button v-for="s in statusTabs" :key="s.key"
              :class="['aarn-chip', { 'is-active': statusFilter === s.key }]"
              :disabled="saving || writeBlocked" @click="changeStatus(s.key)">{{ s.label }}</button>
    </div>

    <ErrorState v-if="error && !pending?.ack" :description="error" @retry="pending ? verifyCommand() : restoreRoute()" />
    <template v-else>
      <AppInlineAlert v-if="error" type="warning" :description="error" />
      <LoadingState v-if="loading" />
      <EmptyState v-else-if="!rows.length && !active" title="暂无认定申请" description="学生自助提交或教务代录后在此审核" />
      <div v-else class="aarn-review">
        <aside class="aarn-queue"><h3>责任队列</h3><button v-for="row in rows" :key="row.recognitionId" :class="['aarn-object',{selected:active?.recognitionId===row.recognitionId}]" :disabled="saving || writeBlocked" @click="selectRecord(row)"><strong>{{ row.studentName }}</strong><span>{{ row.sourceCourseName }} → {{ row.targetCourseName }}</span><StatusTag :label="statusLabel(row.status)" /></button><div class="aarn-pages"><AppButton :disabled="pagination.page <= 1 || saving || writeBlocked" @click="changePage(pagination.page-1)">上一页</AppButton><span>第{{ pagination.page }}页</span><AppButton :disabled="pagination.page * pagination.pageSize >= pagination.total || saving || writeBlocked" @click="changePage(pagination.page+1)">下一页</AppButton></div></aside>
        <section class="aarn-evidence"><EmptyState v-if="!active" title="选择认定申请" description="核对原课程、目标课程和佐证材料" /><template v-else><header><h3>{{ active.studentName }} · {{ active.studentNo }}</h3><StatusTag :label="statusLabel(active.status)" /></header><div class="aarn-facts"><article><strong>原修课程</strong><p>{{ active.sourceCourseName }}</p><p>{{ active.sourceScore ?? '待核对' }} 分 · {{ active.sourceCredit == null ? '学分未提供' : `${active.sourceCredit} 学分` }}</p><p>{{ active.sourceOrigin || '来源说明未提供' }}</p></article><article><strong>替代目标课程</strong><p>{{ active.targetCourseName }}</p><p>课程版本与培养计划适用性由服务器在审核时重新核对。</p></article><article><strong>申请依据</strong><p>{{ active.reason || '未填写申请理由' }}</p><p>当前记录含 {{ (active.attachmentFileIds || []).length }} 份绑定材料。</p><AppButton :disabled="evidenceLoading || saving || writeBlocked" @click="loadEvidence">核对材料元数据</AppButton><ul><li v-for="file in evidenceFiles" :key="file.fileId">{{ file.fileName || '材料' }} · {{ file.readyForBusiness ? '安全可用' : '暂不可用于办理' }} <button :disabled="evidenceLoading || saving || writeBlocked" @click="previewEvidence(file)">核对并查看</button></li></ul></article><article><strong>当前正式结论</strong><p>{{ statusLabel(active.status) }}</p><p>{{ active.reviewReason || '暂无审核意见' }}</p><p v-if="active.reviewedBy">办理人：{{ active.reviewedBy }} · {{ (active.reviewedAt || '').replace('T',' ').slice(0,16) }}</p><p v-else>办理人与时间尚未返回</p></article></div><footer><AppButton v-if="canManage && active.status === 'SUBMITTED'" :disabled="saving || writeBlocked" @click="approve(active)">确认通过认定</AppButton><AppButton v-if="canManage && active.status === 'SUBMITTED'" :disabled="saving || writeBlocked" variant="danger" @click="openReject(active)">驳回</AppButton><AppButton variant="ghost" :disabled="saving || writeBlocked" @click="closeRecord">返回原列表位置</AppButton><span>申请结论由回读确认；课程正式成绩请到学生成绩单核对。</span></footer></template></section>
      </div>
    </template>
    <section v-if="receipt" class="aarn-receipt" role="status"><strong>{{ receipt.verified ? '原认定命令已由持久回执确认' : '结果待核实' }}</strong><p>{{ receipt.description }}</p><p v-if="receipt.commandStatus">原命令结果：{{ statusLabel(receipt.commandStatus) }}</p><p v-if="receipt.status">当前正式记录：{{ statusLabel(receipt.status) }}<template v-if="receipt.commandStatus && receipt.commandStatus !== receipt.status">（已发生后续变化）</template></p><p v-if="!receipt.verified">只读核对不会重放提交，也不会根据当前对象状态推断原命令成功。</p><div class="aarn-receipt-actions"><AppButton v-if="pending" :disabled="saving" :loading="checking" @click="verifyCommand">只读核对持久回执</AppButton><AppButton v-if="pending?.ack" data-testid="return-queue-with-lock" variant="ghost" :disabled="saving || checking" @click="returnToQueueWithLock">返回责任队列（保持写入锁定）</AppButton></div></section>

    <AppDrawer :visible="createVisible" title="代录成绩认定申请" mode="modal" size="large" @close="closeCreate">
      <div class="aarn-form">
        <AppFormItem label="学生" required><AppStudentPicker v-model="form.studentId" :disabled="saving || writeBlocked" @change="onStudentChange" /></AppFormItem>
        <AppFormItem label="原课程名称" required><AppTextInput v-model="form.sourceCourseName" placeholder="如 高等数学A" :disabled="saving || writeBlocked" /></AppFormItem>
        <AppFormItem label="原成绩（≥60）" required><AppNumberInput v-model="form.sourceScore" :min="0" :max="100" :disabled="saving || writeBlocked" /></AppFormItem>
        <AppFormItem label="原学分"><AppNumberInput v-model="form.sourceCredit" :min="0" :max="30" :disabled="saving || writeBlocked" /></AppFormItem>
        <AppFormItem label="来源说明"><AppTextInput v-model="form.sourceOrigin" placeholder="原专业/原学校/证书折算等" :disabled="saving || writeBlocked" /></AppFormItem>
        <AppFormItem label="替代目标课程" required>
          <AppCoursePicker v-model="form.targetCourseId" placeholder="从课程库选择被替代的校内课程" :disabled="saving || writeBlocked" @change="onTargetChange" />
        </AppFormItem>
        <AppFormItem label="佐证附件">
          <div class="aarn-upload">
            <input ref="fileInput" type="file" class="aarn-file" :disabled="saving || writeBlocked || uploading" @change="onPickFile" />
            <span v-if="uploading" class="aarn-uploading">上传中…</span>
            <div v-if="form.attachments.length" class="aarn-files">
              <span v-for="(f, i) in form.attachments" :key="f.fileId" class="aarn-file-chip">
                {{ f.fileName }} · {{ f.readyForBusiness ? '安全可用' : '安全状态待核对' }}<button :disabled="saving || writeBlocked || uploading" @click="refreshFile(f)">核对</button><button type="button" class="aarn-file-x" :disabled="saving || writeBlocked || uploading" @click="removeFile(i)">✕</button>
              </span>
            </div>
          </div>
        </AppFormItem>
        <AppFormItem label="申请理由"><AppTextarea v-model="form.reason" placeholder="选填" :disabled="saving || writeBlocked" /></AppFormItem>
        <AppInlineAlert v-if="formError" type="danger" :description="formError" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="saving || writeBlocked" @click="closeCreate">取消</AppButton>
        <AppButton variant="primary" :loading="saving" :disabled="uploading || writeBlocked" @click="submitCreate">确认提交代录申请</AppButton>
      </template>
    </AppDrawer>

    <AppDrawer :visible="rejectVisible" :title="'驳回 · ' + (rejectRow ? rejectRow.studentName : '')" mode="modal" size="small" @close="rejectVisible = false">
      <div class="aarn-form">
        <AppFormItem label="驳回原因（≥5字）" required><AppTextarea v-model="rejectReason" placeholder="如：原课程学时/大纲不满足替代要求" :disabled="saving || writeBlocked" /></AppFormItem>
        <AppInlineAlert v-if="rejectError" type="danger" :description="rejectError" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="saving || writeBlocked" @click="rejectVisible = false">取消</AppButton>
        <AppButton variant="danger" :loading="saving" @click="submitReject">驳回</AppButton>
      </template>
    </AppDrawer>

    <AppConfirmDialog v-model:visible="confirmVisible" :title="confirmTitle" :message="confirmMessage" :submitting="saving" :confirm-disabled="writeBlocked" @confirm="onConfirm" />
  </ModulePageShell>
</template>

<script>
/** Page ID: AA-186 成绩认定与替代。代录+审核；通过写 RECOGNIZED 成绩并刷新台账。 */
import { ModulePageShell, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton, AppDrawer } from '@/components/ui'
import { AppTextInput, AppNumberInput, AppTextarea, AppFormItem, AppConfirmDialog, AppInlineAlert, AppCoursePicker, AppStudentPicker } from '@/components/common'
import { academicAffairsApi as api } from '@/modules/academicAffairs/api/academic-affairs.api'
import { currentUserFromToken } from '@/services/http/client'
import { matchPermission } from '@/config/navPlan'
import fileSdk from '@/services/file/fileSdk'
import { gradeError } from './parallel-c/grade-review'
import { createGradeCommandReference, findGradeCommandReference, gradeCommandIdentityRef, removeGradeCommandReference, updateGradeCommandReference } from './parallel-c/grade-command-recovery'


export default {
  name: 'AaGradeRecognitionView',
  components: {
    ModulePageShell, StatusTag, LoadingState, ErrorState, EmptyState,
    AppButton, AppDrawer, AppTextInput, AppNumberInput, AppTextarea, AppFormItem,
    AppConfirmDialog, AppInlineAlert, AppCoursePicker, AppStudentPicker
  },
  props:{ctx:{type:Object,required:true}},
  data() {
    return {
      alive:true,scopeSeq:0,readSeq:0,fileSeq:0,evidenceSeq:0,formSeq:0,uploadTask:null,evidenceLoading:false,evidenceFiles:[],active:null,
      pending:null,receipt:null,checking:false,pagination:{page:1,pageSize:20,total:0},
      loading: true, error: '', rows: [], statusFilter: 'SUBMITTED',
      statusTabs: [
        { key: 'SUBMITTED', label: '待审核' }, { key: 'APPROVED', label: '已通过' },
        { key: 'REJECTED', label: '已驳回' }, { key: '', label: '全部' }
      ],
      columns: [
        { key: 'student', title: '学生' }, { key: 'map', title: '课程替代（原→目标）' },
        { key: 'review', title: '审核信息' }, { key: 'status', title: '状态' }, { key: 'ops', title: '操作' }
      ],
      createVisible: false, formError: '', uploading: false,
      form: { studentId: '', studentNo: '', sourceCourseName: '', sourceScore: null, sourceCredit: null, sourceOrigin: '', targetCourseId: '', targetCourseName: '', attachments: [], reason: '' },
      rejectVisible: false, rejectRow: null, rejectReason: '', rejectError: '',
      saving: false, confirmVisible: false, confirmTitle: '', confirmMessage: '', pendingAction: null
    }
  },
  computed:{
    identityKey(){const u=currentUserFromToken()||{};return JSON.stringify([u.tenantId,u.userId,u.activeContextId,u.currentRoleCode,this.ctx.currentRole,this.ctx.dataScope,this.ctx.permissionPatterns])},
    recoveryIdentity(){return gradeCommandIdentityRef(currentUserFromToken()||{},this.ctx)},
    routeKey(){return this.$route?.fullPath||''},
    writeBlocked(){return !!this.pending},
    canManage(){return matchPermission(this.ctx.permissionPatterns||[],'academicAffairs.gradeRecognition.manage')}
  },
  created(){this.restoreWithRecovery()},
  watch:{identityKey(){this.invalidate();this.restoreWithRecovery()},routeKey(){this.resetForRoute()}},
  beforeUnmount(){this.alive=false;this.invalidate()},
  methods:{
    statusLabel(status){return ({SUBMITTED:'待审核',APPROVED:'已通过',REJECTED:'已驳回'})[status]||'状态待核对'},
    exactId(value){if(!['string','number'].includes(typeof value))return '';const id=String(value??'').trim();return /^[1-9]\d*$/.test(id)?id:''},
    restoreWithRecovery(){
      const found=findGradeCommandReference(this.recoveryIdentity,['RECOGNITION_SUBMIT','RECOGNITION_REVIEW'])
      if(!found.ok){this.pending={...this.capture(),recoveryUnavailable:true};this.receipt={verified:false};this.error=`恢复引用暂不可读，写入已锁定：${found.error}`;return}
      if(!found.entry){this.restoreRoute();return}
      const entry=found.entry,kind=entry.operation==='RECOGNITION_SUBMIT'?'create':'review';this.pagination.page=entry.page||1;this.statusFilter=entry.status||''
      this.pending={...this.capture(),id:entry.objectId,commandKey:entry.commandKey,operation:entry.operation,kind,page:entry.page,status:entry.status,recovered:true,description:kind==='create'?'原认定申请':'原认定审核'}
      this.receipt={description:this.pending.description,verified:false};this.error='检测到原身份的认定命令引用，正在只读核对持久回执。'
      if(kind==='review'&&!entry.objectId){this.error='恢复引用缺少认定申请编号，写入保持锁定且不会自动重放。';return}
      this.verifyCommand()
    },
    resetForRoute(){
      const pending=this.pending,receipt=this.receipt,active=this.active,rows=this.rows.map(row=>({...row,attachmentFileIds:[...(row.attachmentFileIds||[])]})),pagination={...this.pagination},form={...this.form,attachments:[...this.form.attachments]},rejectReason=this.rejectReason
      this.invalidate()
      if(pending?.identity===this.identityKey){
        this.pending={...pending,route:this.routeKey,seq:this.scopeSeq};this.receipt=receipt;this.active=this.$route.query.recognitionId?active:null;this.rows=rows;this.form=form
        this.rejectReason=rejectReason;this.pagination={...pagination,page:pending.page||pagination.page||1};this.statusFilter=pending.status||''
        this.createVisible=pending.kind==='create'&&!pending.recovered&&!pending.queueOnly
        this.error='原认定请求仍待核实；当前保留原申请，请只读核对其结果。'
        return
      }
      this.restoreRoute()
      if(receipt?.verified&&String(receipt.id)===String(this.$route.query.recognitionId))this.receipt=receipt
    },
    capture(){return {identity:this.identityKey,route:this.routeKey,seq:this.scopeSeq}},
    current(c){return this.alive&&c.identity===this.identityKey&&c.route===this.routeKey&&c.seq===this.scopeSeq},
    emptyForm(){return {studentId:'',studentNo:'',sourceCourseName:'',sourceScore:null,sourceCredit:null,sourceOrigin:'',targetCourseId:'',targetCourseName:'',attachments:[],reason:''}},
    invalidate(){this.scopeSeq++;this.readSeq++;this.fileSeq++;this.evidenceSeq++;this.formSeq++;this.uploadTask?.cancel();this.uploadTask=null;this.uploading=false;this.loading=false;this.rows=[];this.active=null;this.evidenceFiles=[];this.evidenceLoading=false;this.form=this.emptyForm();this.createVisible=false;this.rejectVisible=false;this.rejectRow=null;this.rejectReason='';this.rejectError='';this.formError='';this.pending=null;this.receipt=null;this.checking=false;this.saving=false;this.confirmVisible=false;this.pendingAction=null;this.pagination={page:1,pageSize:20,total:0};this.error=''},
    fail(err,fallback='读取失败，请重试。'){const message=gradeError(err,fallback);if(/403|NO_DATA_SCOPE|FORBIDDEN|NO_PERMISSION/.test([err?.status,err?.statusCode,err?.code,err?.bizCode].join(' ')))this.invalidate();this.error=message;this.formError=message;this.rejectError=message},
    conflict(err){return /409|CONFLICT|VERSION/.test([err?.code,err?.bizCode].join(' '))},
    explicitFailure(err){return /403|409|422|NO_DATA_SCOPE|FORBIDDEN|NO_PERMISSION|CONFLICT|VALIDATION/.test([err?.status,err?.statusCode,err?.code,err?.bizCode].join(' '))},
    async navigate(patch){const query={...this.$route.query,...patch};Object.keys(query).forEach(key=>{if(query[key]==null||query[key]==='')delete query[key]});const before=this.routeKey;try{await this.$router.replace({path:this.$route.path,query})}catch{/* duplicate navigation */}if(before===this.routeKey)this.restoreRoute()},
    restoreRoute(){if(this.saving||this.writeBlocked)return;const query=this.$route?.query||{},rawStatus=String(query.status||'');this.statusFilter=rawStatus==='ALL'?'':this.statusTabs.some(item=>item.key===rawStatus)?rawStatus:'SUBMITTED';const page=Number(query.page);this.pagination.page=Number.isInteger(page)&&page>0?page:1;if(query.recognitionId!=null&&!this.exactId(query.recognitionId)){this.error='认定申请编号无效，请从队列重新进入';return}this.load(this.exactId(query.recognitionId))},
    routeStatus(){return this.statusFilter||'ALL'},
    changeStatus(status){if(this.saving||this.writeBlocked)return;this.navigate({status:status||'ALL',page:'1',recognitionId:undefined})},
    changePage(page){if(this.saving||this.writeBlocked)return;this.navigate({status:this.routeStatus(),page:String(page),recognitionId:undefined})},
    selectRecord(row){if(this.saving||this.writeBlocked)return;const id=this.exactId(row?.recognitionId);if(id)this.navigate({status:this.routeStatus(),page:String(this.pagination.page),recognitionId:id})},
    closeRecord(){if(this.saving||this.writeBlocked)return;this.navigate({status:this.routeStatus(),page:String(this.pagination.page),recognitionId:undefined})},
    async returnToQueueWithLock(){if(this.saving||this.checking||!this.pending?.ack)return;this.pending.queueOnly=true;this.createVisible=false;this.rejectVisible=false;this.active=null;await this.navigate({status:this.routeStatus(),page:String(this.pending.page||this.pagination.page),recognitionId:undefined})},
    async readFormal(id){const exact=this.exactId(id);if(!exact)throw {code:404,bizCode:'INVALID_OBJECT_ID'};const res=await api.getRecognition(exact);if(res?.code!==0)throw res;if(!res.data||String(res.data.recognitionId)!==exact)throw {code:409,bizCode:'OBJECT_ID_MISMATCH',message:'正式认定记录与请求对象不一致'};return res.data},
    replaceFormal(row){this.active={...row,attachmentFileIds:[...(row.attachmentFileIds||[])]};const current=this.rows.find(item=>String(item.recognitionId)===String(row.recognitionId));if(current)Object.assign(current,row)},
    async load(detailId=''){
      if(this.saving||this.writeBlocked)return
      const c=this.capture(),seq=++this.readSeq,valid=()=>this.current(c)&&seq===this.readSeq
      this.loading=true;this.error='';this.rows=[];this.active=null;this.evidenceSeq++;this.evidenceFiles=[];this.evidenceLoading=false
      try{if(detailId){const formal=await this.readFormal(detailId);if(!valid())return;this.replaceFormal(formal)}const res=await api.listRecognitions({status:this.statusFilter||undefined,page:this.pagination.page,pageSize:20});if(!valid())return;if(res?.code!==0)throw res;this.rows=res.data?.list||[];this.pagination.total=res.data?.total??this.rows.length;if(this.active){const row=this.rows.find(item=>String(item.recognitionId)===String(this.active.recognitionId));if(row)Object.assign(row,this.active)}}
      catch(err){if(valid())this.fail(err)}finally{if(valid())this.loading=false}
    },
    async loadEvidence(){
      if(!this.active||this.evidenceLoading||this.saving||this.writeBlocked)return
      const c=this.capture(),seq=++this.evidenceSeq,id=this.active.recognitionId,ids=[...(this.active.attachmentFileIds||[])],valid=()=>this.current(c)&&seq===this.evidenceSeq&&this.active?.recognitionId===id
      this.evidenceLoading=true;this.evidenceFiles=[]
      try{for(const fileId of ids){const meta=await fileSdk.metadata(String(fileId));if(!valid())return;this.evidenceFiles.push({...meta,fileId:String(fileId)})}}
      catch(err){if(valid())this.fail(err,'材料元数据读取失败，请重新核对。')}finally{if(valid())this.evidenceLoading=false}
    },
    closeCreate(){if(this.saving||this.writeBlocked)return;this.formSeq++;this.fileSeq++;this.uploadTask?.cancel();this.uploadTask=null;this.uploading=false;this.createVisible=false},
    openCreate(){if(!this.canManage||this.saving||this.writeBlocked)return;this.closeCreate();this.form=this.emptyForm();this.formError='';this.createVisible=true},
    onStudentChange(_value,items){if(this.saving||this.writeBlocked)return;this.formSeq++;this.fileSeq++;this.uploadTask?.cancel();this.uploadTask=null;this.uploading=false;const id=this.form.studentId;this.form=this.emptyForm();this.form.studentId=id;const item=items?.[0];this.form.studentNo=item?.raw?.studentNo||item?.studentNo||''},
    onTargetChange(_value,items){if(this.saving||this.writeBlocked)return;this.formSeq++;this.fileSeq++;this.uploadTask?.cancel();this.uploadTask=null;this.uploading=false;this.form.attachments=[];const item=items?.[0];this.form.targetCourseName=item?.raw?.courseName||item?.name||item?.label||''},
    async previewEvidence(file){
      if(!this.active||this.evidenceLoading||this.saving||this.writeBlocked)return
      const c=this.capture(),seq=++this.evidenceSeq,id=this.active.recognitionId,valid=()=>this.current(c)&&seq===this.evidenceSeq&&this.active?.recognitionId===id
      if(!(this.active.attachmentFileIds||[]).some(x=>String(x)===String(file.fileId)))return
      this.evidenceLoading=true
      try{const meta=await fileSdk.metadata(file.fileId);if(!valid())return;if(!meta.allowedActions?.includes('preview'))throw {code:403}
        const preview=await fileSdk.preview(file.fileId);if(!valid())preview?.close?.()
      }catch(err){if(valid())this.fail(err,'材料暂不可用，请重新核对。')}finally{if(valid())this.evidenceLoading=false}
    },
    async refreshFile(file){
      if(this.saving||this.writeBlocked||this.uploading||!this.createVisible)return
      const c=this.capture(),seq=++this.fileSeq,formSeq=this.formSeq,valid=()=>this.current(c)&&seq===this.fileSeq&&formSeq===this.formSeq&&this.createVisible
      this.uploading=true
      try{const meta=await fileSdk.metadata(file.fileId);if(!valid())return;const index=this.form.attachments.findIndex(f=>String(f.fileId)===String(file.fileId));if(index>=0)this.form.attachments.splice(index,1,{...meta,fileId:String(file.fileId),fileName:meta.fileName||file.fileName})}
      catch(err){if(valid())this.fail(err,'材料安全状态读取失败。')}finally{if(valid())this.uploading=false}
    },
    removeFile(index){if(this.saving||this.writeBlocked||this.uploading)return;this.form.attachments.splice(index,1)},
    async onPickFile(event){
      const file=event.target.files?.[0];event.target.value='';if(!file||this.saving||this.writeBlocked||this.uploading||!this.createVisible)return
      if(file.size>10*1024*1024||this.form.attachments.length>=3){this.formError='最多3份材料，每份不超过10MB。';return}
      const c=this.capture(),seq=++this.fileSeq,formSeq=this.formSeq,valid=()=>this.current(c)&&seq===this.fileSeq&&formSeq===this.formSeq&&this.createVisible
      this.uploading=true;this.formError=''
      try{this.uploadTask=fileSdk.upload(file,{bizType:'AA_RECOGNITION'});const result=await this.uploadTask.promise;if(!valid())return;if(!result.fileId)throw {code:503};const meta=await fileSdk.metadata(result.fileId);if(!valid())return;this.form.attachments.push({...meta,fileId:String(result.fileId),fileName:meta.fileName||file.name})}
      catch(err){if(valid())this.fail(err,'材料上传或安全状态读取失败。')}finally{if(valid()){this.uploading=false;this.uploadTask=null}}
    },
    async submitCreate(){
      if(!this.canManage||this.saving||this.writeBlocked||this.uploading||!this.createVisible)return
      const form=this.form
      if(!form.studentNo||!form.sourceCourseName.trim()||!form.targetCourseId){this.formError='请选择学生与目标课程，并填写原课程名称。';return}
      if(form.sourceScore==null||String(form.sourceScore).trim()===''||!Number.isInteger(Number(form.sourceScore))||Number(form.sourceScore)<60||Number(form.sourceScore)>100){this.formError='原成绩须为60至100的整数，不能留空。';return}
      if(form.sourceCredit!=null&&form.sourceCredit!==''&&(!Number.isFinite(Number(form.sourceCredit))||Number(form.sourceCredit)<0||Number(form.sourceCredit)>30)){this.formError='原学分须在0至30之间。';return}
      const body={studentNo:form.studentNo,sourceCourseName:form.sourceCourseName.trim(),sourceScore:Number(form.sourceScore),sourceCredit:form.sourceCredit==null||form.sourceCredit===''?undefined:Number(form.sourceCredit),sourceOrigin:form.sourceOrigin.trim()||undefined,targetCourseId:String(form.targetCourseId),attachmentFileIds:form.attachments.map(f=>String(f.fileId)),reason:form.reason.trim()||undefined}
      const command={...this.capture(),kind:'create',body,formSeq:this.formSeq,id:null,ack:null,description:`${form.studentNo} · ${body.sourceCourseName} → ${form.targetCourseName}`}
      this.saving=true;this.formError=''
      try{for(const id of body.attachmentFileIds){const meta=await fileSdk.metadata(id);if(!this.current(command)||command.formSeq!==this.formSeq)return;if(meta.readyForBusiness!==true)throw {code:422}}
        if(!this.current(command)||command.formSeq!==this.formSeq)return
        const saved=createGradeCommandReference({identityRef:this.recoveryIdentity,operation:'RECOGNITION_SUBMIT',objectId:null,page:this.pagination.page,status:this.statusFilter})
        if(!saved.ok){this.formError=`无法保存刷新恢复引用，本次未发送：${saved.error}`;return}
        this.pending={...command,commandKey:saved.entry.commandKey,operation:'RECOGNITION_SUBMIT'};const c=this.pending;this.receipt={description:c.description,verified:false}
        if(saved.existing){c.recovered=true;this.formError='已有认定申请命令在途，本次未重复发送；正在只读核对。';await this.verifyCommand();return}
        let res;try{res=await api.submitRecognition(body,c.commandKey)}catch(err){res=err}
        if(!this.current(c)||this.pending!==c)return
        c.id=this.exactId(res?.code===0?res.data?.recognitionId:'');if(c.id)updateGradeCommandReference(c.commandKey,this.recoveryIdentity,{objectId:c.id})
        c.postFailure=res?.code===0?null:res;await this.verifyCommand()
      }catch(err){if(this.current(command))this.fail(err,this.pending?'结果待核实，请只读核对。':'申请尚未提交；填写内容与材料已保留，请核对。')}finally{if(this.current(command))this.saving=false}
    },
    approve(row){
      if(!this.canManage||this.saving||this.writeBlocked||row.status!=='SUBMITTED')return
      const c=this.capture(),snapshot={...row,attachmentFileIds:[...(row.attachmentFileIds||[])]},page=this.pagination.page,status=this.statusFilter
      this.confirmTitle='确认通过成绩认定';this.confirmMessage=`${row.studentName} · ${row.sourceCourseName} ${row.sourceScore}分 → ${row.targetCourseName}。服务器重新核对课程、原成绩和绑定证据。`
      this.pendingAction=()=>this.current(c)?this.review(snapshot,'APPROVE','',page,status):null;this.confirmVisible=true
    },
    openReject(row){if(!this.canManage||this.saving||this.writeBlocked||row.status!=='SUBMITTED')return;this.rejectRow={...row,attachmentFileIds:[...(row.attachmentFileIds||[])]};this.rejectReason='';this.rejectError='';this.rejectVisible=true},
    async submitReject(){if(!this.rejectRow||this.saving||this.writeBlocked)return;const reason=this.rejectReason.trim();if(reason.length<5){this.rejectError='原因至少5字。';return}return this.review(this.rejectRow,'REJECT',reason,this.pagination.page,this.statusFilter)},
    sameSource(a,b,versions=true){return ['recognitionId','studentId','studentNo','sourceCourseName','sourceScore','sourceCredit','sourceOrigin','targetCourseId','targetCourseName','reason',...(versions?['version','recordVersion','gradeVersion']:[])].every(k=>String(a?.[k]??'')===String(b?.[k]??''))&&JSON.stringify((a?.attachmentFileIds||[]).map(String).sort())===JSON.stringify((b?.attachmentFileIds||[]).map(String).sort())},
    sameCreate(row,body){return !!row&&['SUBMITTED','APPROVED','REJECTED'].includes(row.status)&&(row.sourceCredit==null?body.sourceCredit==null:Number(row.sourceCredit)===body.sourceCredit)&&String(row.sourceOrigin||'')===String(body.sourceOrigin||'')&&String(row.studentNo)===String(body.studentNo)&&row.sourceCourseName===body.sourceCourseName&&Number(row.sourceScore)===body.sourceScore&&String(row.targetCourseId)===body.targetCourseId&&JSON.stringify((row.attachmentFileIds||[]).map(String).sort())===JSON.stringify([...body.attachmentFileIds].sort())&&String(row.reason||'')===String(body.reason||'')},
    async review(row,action,reason,page,status){
      if(!this.canManage||this.saving||this.writeBlocked)return
      const command={...this.capture(),kind:'review',row:{...row,attachmentFileIds:[...(row.attachmentFileIds||[])]},id:this.exactId(row.recognitionId),action,reason,page,status,ack:null,description:`${row.studentName} · ${row.sourceCourseName} → ${row.targetCourseName}`}
      this.saving=true;this.error=''
      try{const before=await this.readFormal(command.id);if(!this.current(command))return;if(before.status!=='SUBMITTED'||!this.sameSource(before,command.row)){this.replaceFormal(before);throw {code:409,bizCode:'APPROVAL_VERSION_CONFLICT'}}
        const saved=createGradeCommandReference({identityRef:this.recoveryIdentity,operation:'RECOGNITION_REVIEW',objectId:command.id,page,status})
        if(!saved.ok){this.error=`无法保存刷新恢复引用，本次未发送：${saved.error}`;this.rejectError=this.error;return}
        this.pending={...command,commandKey:saved.entry.commandKey,operation:'RECOGNITION_REVIEW'};const c=this.pending;this.receipt={description:c.description,verified:false}
        if(saved.existing){c.recovered=true;this.error='同一认定申请已有审核命令在途，本次未重复发送；正在只读核对。';await this.verifyCommand();return}
        let res;try{res=await api.reviewRecognition(c.id,action,reason,c.commandKey)}catch(err){res=err}
        if(!this.current(c)||this.pending!==c)return
        c.postFailure=res?.code===0?null:res;await this.verifyCommand()
      }catch(err){if(this.current(command)){this.confirmVisible=false;this.fail(err,this.pending?'结果待核实，请只读核对原申请。':this.conflict(err)?'申请、材料或版本已变化；输入已保留，请重新确认。':'本次尚未办理，请核对最新申请。')}}finally{if(this.current(command))this.saving=false}
    },
    async readPersistentReceipt(c){
      const res=await api.getGradeCommandReceipt(c.commandKey,c.operation);if(res?.code!==0)throw res
      const data=res.data
      if(!data||data.commandKey!==c.commandKey||data.operation!==c.operation||!['SUCCESS','UNRESOLVED'].includes(data.state)||(data.state==='SUCCESS'&&!data.result)||(data.state==='UNRESOLVED'&&data.result!=null))throw {code:'GRADE_COMMAND_RECEIPT_MISMATCH',message:'命令回执与当前恢复引用不一致'}
      return data
    },
    async clearRejectedCommand(c,failure){
      if(/403|NO_DATA_SCOPE|FORBIDDEN|NO_PERMISSION/.test([failure?.status,failure?.statusCode,failure?.code,failure?.bizCode].join(' '))){this.fail(failure);return}
      const removed=removeGradeCommandReference(c.commandKey,this.recoveryIdentity)
      if(!removed.ok){const message=`服务器已明确拒绝本次操作，但本地恢复标记无法清除：${removed.error}`;this.error=message;this.formError=message;this.rejectError=message;return}
      this.pending=null;this.receipt=null;this.confirmVisible=false;this.pendingAction=null
      if(/403|NO_DATA_SCOPE|FORBIDDEN|NO_PERMISSION/.test([failure?.status,failure?.statusCode,failure?.code,failure?.bizCode].join(' '))){this.fail(failure);return}
      if(this.conflict(failure)&&c.id){try{const row=await this.readFormal(c.id);if(this.current(c))this.replaceFormal(row)}catch(readErr){if(this.current(c))this.fail(readErr,'正式认定记录读取失败，请重试。');return}}
      if(this.current(c)){const message=gradeError(failure,'本次操作未受理；已保留填写内容，请重新读取后确认。');this.error=message;this.formError=message;this.rejectError=message}
    },
    async verifyCommand(){
      if(this.pending?.recoveryUnavailable){this.pending=null;this.restoreWithRecovery();return}
      const c=this.pending;if(!c||!this.current(c)||this.pending!==c||this.checking)return
      this.checking=true
      try{
        const persisted=await this.readPersistentReceipt(c)
        if(!this.current(c)||this.pending!==c)return
        if(persisted.state==='UNRESOLVED'){
          if(c.postFailure&&this.explicitFailure(c.postFailure)){await this.clearRejectedCommand(c,c.postFailure);return}
          const message='持久回执尚未确认原认定命令；不会自动重发，请稍后只读核对。';this.error=message;this.formError=message;this.rejectError=message;return
        }
        const id=this.exactId(persisted.result?.recognitionId)
        if(!id||(c.id&&String(c.id)!==id))throw {code:'GRADE_COMMAND_RECEIPT_OBJECT_MISMATCH',message:'持久回执与原认定申请不一致'}
        if(!(c.kind==='create'?['SUBMITTED']:['APPROVED','REJECTED']).includes(persisted.result.status))throw {code:'GRADE_COMMAND_RECEIPT_MISMATCH',message:'持久回执未包含有效认定命令结果'}
        if(!c.recovered && (c.kind==='create'?!this.sameCreate(persisted.result,c.body):!this.sameSource(persisted.result,c.row,false)||persisted.result.status!==(c.action==='APPROVE'?'APPROVED':'REJECTED')||(c.action==='REJECT'&&String(persisted.result.reviewReason||'').trim()!==c.reason)))throw {code:'GRADE_COMMAND_RECEIPT_MISMATCH',message:'持久回执与已确认的认定内容不一致'}
        c.id=id
        c.ack={...persisted.result}
        this.receipt={id,description:c.description,commandStatus:persisted.result.status,status:null,acknowledged:true,verified:false}
        const row=await this.readFormal(id)
        if(!this.current(c)||this.pending!==c)return
        this.replaceFormal(row)
        const expectedStatus=c.kind==='create'?'SUBMITTED':c.recovered?persisted.result.status:c.action==='APPROVE'?'APPROVED':'REJECTED'
        const expectedContent=c.recovered?persisted.result:c.kind==='create'?c.body:c.row
        const sameObject=c.kind==='create'?this.sameCreate(row,expectedContent):this.sameSource(row,expectedContent,false)
        const expectedReason=c.recovered?String(persisted.result.reviewReason||'').trim():c.reason
        const sameDecision=c.kind!=='review'||expectedStatus!=='REJECTED'||(!!expectedReason&&String(row.reviewReason||'').trim()===expectedReason)
        const statusConsistent=c.kind==='create'?['SUBMITTED','APPROVED','REJECTED'].includes(row.status):row.status===expectedStatus
        if(!statusConsistent||!sameObject||!sameDecision){
          const message=`持久回执已确认“${this.statusLabel(persisted.result.status)}”，但原申请 #${id} 的正式记录尚未形成同一结果；不会自动重发。`
          this.receipt={id,description:c.description,commandStatus:persisted.result.status,status:row.status,acknowledged:true,verified:false}
          this.error=message;this.formError=message;this.rejectError=message
          return
        }
        const marked=updateGradeCommandReference(c.commandKey,this.recoveryIdentity,{objectId:id,confirmedAt:Date.now()})
        if(!marked.ok)throw {code:'GRADE_COMMAND_RECOVERY_UPDATE_FAILED',message:`持久回执已确认，但本地恢复引用更新失败：${marked.error}`}
        this.receipt={id,description:c.description,commandStatus:persisted.result.status,status:row.status,acknowledged:true,verified:true}
        const removed=removeGradeCommandReference(c.commandKey,this.recoveryIdentity)
        if(!removed.ok){const message=`原命令和正式记录已确认，但本地恢复标记无法清除：${removed.error}`;this.error=message;this.formError=message;this.rejectError=message;return}
        this.pending=null;this.confirmVisible=false;this.pendingAction=null;this.error='';this.formError='';this.rejectError=''
        if(c.kind==='create'){this.createVisible=false;this.form=this.emptyForm()}else this.rejectVisible=false
        await this.navigate({status:this.routeStatus(),page:String(this.pagination.page),recognitionId:id})
      }catch(err){
        if(!this.current(c)||this.pending!==c)return
        this.fail(err,'原认定命令结果待核实，请稍后只读核对；不会自动重发。')
      }finally{if(this.current(c)&&(!this.pending||this.pending===c))this.checking=false}
    },
    async onConfirm(){if(this.saving||this.writeBlocked)return;const action=this.pendingAction;if(action)await action()}
  }
}
</script>

<style scoped>
.aarn-review{display:grid;grid-template-columns:260px minmax(0,1fr);gap:16px}.aarn-queue,.aarn-evidence,.aarn-receipt{border:1px solid var(--border-200,#e1e7ef);border-radius:8px;background:var(--bg-white,#fff)}.aarn-queue h3,.aarn-evidence header{padding:16px;margin:0;border-bottom:1px solid var(--border-200,#e1e7ef)}.aarn-object{display:flex;flex-direction:column;align-items:flex-start;gap:8px;width:100%;padding:16px;text-align:left;border:0;border-bottom:1px solid #e1e7ef;background:transparent;cursor:pointer}.aarn-object.selected{background:#edf3ff;box-shadow:inset 3px 0 #2860b6}.aarn-object span{font-size:12px;color:var(--text-secondary,#64748b)}.aarn-facts{display:grid;grid-template-columns:1fr 1fr;gap:12px;padding:16px}.aarn-facts article{padding:14px;border:1px solid #e1e7ef;border-radius:8px}.aarn-facts p{font-size:13px;line-height:1.7}.aarn-pages,.aarn-evidence footer,.aarn-receipt-actions{display:flex;gap:12px;align-items:center;padding:16px}.aarn-evidence footer span{font-size:12px;color:#64748b}.aarn-receipt{padding:16px;margin:16px 0}.aarn-receipt-actions{padding:8px 0 0}@media(max-width:1000px){.aarn-review{grid-template-columns:220px minmax(0,1fr)}.aarn-facts{grid-template-columns:1fr}}

.aarn-bar { display: flex; gap: 8px; margin-bottom: 12px; }
.aarn-chip { padding: 4px 14px; border: 1px solid var(--border-color, #e5e7eb); border-radius: 14px; background: none; cursor: pointer; font-size: 13px; color: var(--text-secondary, #64748b); }
.aarn-chip.is-active { color: var(--primary-color, #2563eb); border-color: var(--primary-color, #2563eb); background: var(--primary-light, #eff6ff); }
.aarn-form { display: flex; flex-direction: column; gap: 12px; }
.aarn-upload { display: flex; flex-direction: column; gap: 8px; }
.aarn-file { font-size: 13px; }
.aarn-uploading { font-size: 12px; color: var(--primary-color, #2563eb); }
.aarn-files { display: flex; flex-wrap: wrap; gap: 6px; }
.aarn-file-chip { display: inline-flex; align-items: center; gap: 4px; padding: 2px 8px; background: var(--fill-light, #f1f5f9); border-radius: 6px; font-size: 12px; }
.aarn-file-x { border: none; background: none; cursor: pointer; color: var(--text-tertiary, #94a3b8); font-size: 12px; }
</style>
