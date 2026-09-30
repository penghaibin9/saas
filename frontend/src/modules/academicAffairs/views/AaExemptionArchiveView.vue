<template>
  <ModulePageShell
    title="免修材料归档"
    subtitle="按学期/归档状态查看免修申请材料，标记已归档留存"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="mp-stack">
      <fieldset class="aamk-filter-lock" :disabled="saving || !!pending"><AdvancedFilter v-model="filters" :fields="filterFields" @search="search" @reset="resetFilters" /></fieldset>

      <ErrorState v-if="error" :description="error" @retry="reload" />
      <LoadingState v-else-if="loading" />
      <template v-else>
        <EmptyState v-if="!rows.length" title="暂无免修申请材料" description="学生免修申请审批后在此归档" />
        <section v-else class="aamk-overview" aria-label="当前页归档概况">
          <article><span>当前范围</span><strong>{{ ctx.dataScope.scopeName }}</strong><small>材料与成绩只随当前可见申请返回</small></article>
          <article><span>当前页申请</span><strong>{{ rows.length }}</strong><small>总计 {{ pagination.total }} 条</small></article>
          <article><span>证据有效</span><strong>{{ evidenceValidCount }}</strong><small>仍需文件中心实时授权</small></article>
          <article><span>待归档</span><strong>{{ pendingArchiveCount }}</strong><small>审批终态且尚未归档</small></article>
        </section>
        <DataTable v-if="rows.length" :columns="columns" :rows="rows" :pagination="pagination" @page-change="changePage" row-key="exemptionId">
          <template #cell-application="{ row }"><strong>#{{ row.exemptionId }}</strong><span class="aamk-cell-sub">{{ row.studentName }} · {{ revisionText(row) }}</span></template>
          <template #cell-course="{ row }">{{ row.course?.name || row.courseName }}<span class="aamk-cell-sub">{{ courseText(row) }}</span></template>
          <template #cell-status="{ row }"><StatusTag :type="exType(row.status)" :label="academicStatusLabel(row.status)" dot /></template>
          <template #cell-evidence="{ row }"><StatusTag :type="stateMeta(row.evidenceState,'evidence').type" :label="stateMeta(row.evidenceState,'evidence').label" dot /><span class="aamk-cell-sub">{{ evidenceSummary(row) }}</span></template>
          <template #cell-archiveStatus="{ row }">
            <StatusTag :type="row.archiveStatus === 'ARCHIVED' ? 'success' : 'default'"
                      :label="row.archiveStatus === 'ARCHIVED' ? '已归档' : row.archiveStatus === 'NOT_ARCHIVED' ? '未归档' : '待核对'" dot />
            <span class="aamk-cell-sub">{{ archiveSource(row) }}</span>
          </template>
          <template #cell-ops="{ row }">
            <button v-if="hasEvidenceContract(row)" class="mp-link" @click="openMaterials(row)">
              核对材料证据
            </button>
            <span v-else class="aamk-muted">证据合同未返回</span>
            <button v-if="canArchive(row)" class="mp-link" @click="confirmArchive(row)">标记已归档</button>
          </template>
        </DataTable>
      </template>
    </div>

    <section v-if="receipt" class="aamk-receipt" role="status"><strong>{{ receipt.verified ? '已回读正式归档状态' : '归档结果待核实' }}</strong><p>免修申请 #{{ receipt.exemptionId }} · {{ receipt.studentName }} · {{ receipt.course?.name || receipt.courseName }}</p><p>实际状态：{{ receipt.archiveStatus === 'ARCHIVED' ? '已归档' : '待核对' }} · 操作时间：{{ formatMoment(receipt.archiveOperation?.occurredAt) }}</p><p>下一步：保留原审批结论；归档后的事实纠错进入受控纠错流程。</p><AppButton v-if="pending" :loading="checking" :disabled="saving" @click="verifyArchive">只读核对结果</AppButton></section>
    <AppConfirmDialog v-model:visible="confirmVisible" title="确认标记材料归档" :message="confirmMessage" :submitting="saving" :confirm-disabled="!!pending" @confirm="markArchived" />
    <AppDrawer :visible="materialsVisible" title="免修材料" mode="modal" size="medium" @close="closeMaterials">
      <div class="aamk-object-head"><div><strong>免修申请 #{{ materialObject?.exemptionId }}</strong><p>{{ materialObject?.studentName }} · {{ materialObject?.course?.name || materialObject?.courseName }}</p></div><StatusTag :type="stateMeta(materialObject?.evidenceState,'evidence').type" :label="stateMeta(materialObject?.evidenceState,'evidence').label" /></div>
      <AppInlineAlert v-if="fileError" type="danger" :description="fileError" />
      <AppInlineAlert v-if="materialObject?.evidenceState !== 'VALID'" type="warning" title="材料证据不可宣称齐备" :description="evidenceProblemText(materialObject)" />
      <div class="aamk-manifest"><span>冻结清单</span><strong>{{ shortHash(materialObject?.evidenceManifestHash) }}</strong><small>{{ materialObject?.evidenceCount == null ? '份数待核对' : `${materialObject.evidenceCount} 份证据` }} · 文件打开时再次校验当前授权</small></div>
      <ul v-if="materialFiles.length" class="aamk-files"><li v-for="file in materialFiles" :key="file.frozenBindingId || file.fileId"><div class="aamk-file-main"><strong>{{ file.fileName || `文件 #${file.fileId}` }}</strong><StatusTag :type="fileBindingType(file)" :label="fileBindingLabel(file)" /></div><span>{{ evidenceVersion(file) }}</span><span>冻结绑定 #{{ file.frozenBindingId || '未记录' }} · SHA-256 {{ shortHash(file.sha256) }}</span><span>绑定版本 {{ file.bindingVersionNo == null ? '待核对' : file.bindingVersionNo }} · 冻结于 {{ formatMoment(file.boundAt) }}</span><div><AppButton :disabled="fileBusy || !canOpenFile(file)" @click="openFile(file,'preview')">核对并预览</AppButton><AppButton :disabled="fileBusy || !canOpenFile(file)" @click="openFile(file,'download')">核对并下载</AppButton></div></li></ul>
      <EmptyState v-else title="未返回冻结证据文件" description="不使用旧附件名称或当前文件元数据替代申请时证据清单" />
      <section class="aamk-operation"><strong>认定成绩关联</strong><p>{{ gradeIdentity(materialObject?.resultGrade) }}</p><p>{{ gradeResult(materialObject?.resultGrade) }}</p><small>当前有效：{{ gradeIdentity(materialObject?.currentGrade) }} · {{ gradeResult(materialObject?.currentGrade) }}</small></section>
      <section class="aamk-operation"><strong>归档关联</strong><p>{{ archiveSource(materialObject) }}</p><small v-if="materialObject?.archiveOperation">{{ materialObject.archiveOperation.role || '角色未记录' }} · {{ formatMoment(materialObject.archiveOperation.occurredAt) }}</small><small v-else>没有准确业务审计列时保持“未记录”，不解析审计说明文字。</small></section>
    </AppDrawer>
  </ModulePageShell>
</template>

<script>
/** 免修材料归档（三级施工卡 11-材料归档）：/admin/academic-affairs/exemption/archive。 */
import { ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState, AdvancedFilter } from '@/components/business'
import { AppDrawer, AppButton } from '@/components/ui'
import { AppConfirmDialog, AppInlineAlert } from '@/components/common'
import { academicAffairsMakeupApi as api } from '@/modules/academicAffairs/api/academic-affairs.api'
import { academicStatusLabel } from '@/modules/academicAffairs/constants/academic-display.constants'
import { currentUserFromToken } from '@/services/http/client'
import { matchPermission } from '@/config/navPlan'
import fileSdk from '@/services/file/fileSdk'
import { gradeError } from './parallel-c/grade-review'
import { evidenceFiles, evidenceVersion, formatMoment, gradeIdentity, gradeResult, rowRevision, shortHash, stateMeta } from './parallel-c/makeup-evidence'

const _TERMINAL = ['APPROVED', 'REJECTED', 'CANCELLED']

export default {
  name: 'AaExemptionArchiveView',
  components: { ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState, AdvancedFilter, AppDrawer, AppButton, AppConfirmDialog, AppInlineAlert },
  props: { ctx: { type:Object, required:true } },
  data() {
    return {
      alive:true,seq:0,fileSeq:0,saving:false,checking:false,pending:null,receipt:null,command:null,confirmVisible:false,
      pagination:{page:1,pageSize:20,total:0},materialObject:null,fileError:'',fileBusy:false,
      loading: true, error: '', rows: [],
      filters: { term: '', status: '' },
      columns: [
        { key: 'application', title: '申请/学生' }, { key: 'course', title: '申请课程' }, { key: 'status', title: '审批结论' },
        { key: 'evidence', title: '文件证据' }, { key: 'archiveStatus', title: '归档关联' }, { key: 'ops', title: '操作' }
      ],
      materialsVisible: false, materialFiles: []
    }
  },
  computed: {
    identityKey(){const u=currentUserFromToken()||{};return JSON.stringify([u.tenantId,u.userId,u.activeContextId,u.currentRoleCode,this.ctx.currentRole,this.ctx.dataScope,this.ctx.permissionPatterns])},
    confirmMessage(){return this.command ? `${this.command.row.studentName} · ${this.command.row.courseName}。标记材料留存不改变原审批结论。` : ''},
    evidenceValidCount(){return this.rows.filter(row=>row.evidenceState==='VALID').length},
    pendingArchiveCount(){return this.rows.filter(row=>_TERMINAL.includes(row.status)&&row.archiveStatus==='NOT_ARCHIVED').length},
    filterFields() {
      return [
        { key: 'term', label: '学期', type: 'text', placeholder: '如 2024-2，可空=全部' },
        { key: 'status', label: '归档状态', type: 'select', options: [
          { value: 'NOT_ARCHIVED', label: '未归档' },
          { value: 'ARCHIVED', label: '已归档' }
        ] }
      ]
    }
  },
  created() { this.restoreArchive();this.reload() },
  watch: {
    identityKey(){this.invalidate();this.filters={term:'',status:''};this.reload()},
    filters:{deep:true,flush:'sync',handler(){if(this.saving||this.pending){const frozen=this.command?.filters||this.pending?.filters;if(frozen&&JSON.stringify(this.filters)!==JSON.stringify(frozen))this.filters={...frozen};return}this.seq++;this.rows=[];this.pagination.total=0;this.loading=false;this.closeMaterials();if(!this.pending&&!this.saving){this.command=null;this.confirmVisible=false}}}
  },
  beforeUnmount(){this.alive=false;this.invalidate()},
  methods: {
    academicStatusLabel,stateMeta,formatMoment,shortHash,evidenceVersion,gradeIdentity,gradeResult,
    formalEvidenceFiles(row){return evidenceFiles(row)},
    hasEvidenceContract(row){return !!row&&Object.prototype.hasOwnProperty.call(row,'evidenceState')&&Array.isArray(row.evidenceFiles)},
    evidenceSummary(row){const files=this.formalEvidenceFiles(row);if(!files.length)return row?.evidenceCount===0?'0 份 · 无冻结文件':'文件版本待核对';return `${evidenceVersion(files[0])}${files.length>1?` 等 ${files.length} 份`:''}`},
    revisionText(row){const value=rowRevision(row,'exemption');return value==null?'版本待核对':`申请版本 ${value}`},
    courseText(row){const c=row?.course||{};return [c.id?`课程 #${c.id}`:'课程ID待核对',c.code||'课程代码待核对',c.version==null?'版本待核对':`V${c.version}`].join(' · ')},
    evidenceProblemText(row){const problems=Array.isArray(row?.evidenceProblems)?row.evidenceProblems.filter(Boolean):[];return problems.length?problems.join('；'):row?.evidenceState==='MISSING'?'该申请没有冻结材料；是否可办理仍由原业务状态机决定。':'证据状态未返回，不能把材料显示为已齐。'},
    archiveSource(row){const op=row?.archiveOperation;if(!op)return row?.archiveStatus==='ARCHIVED'?'归档操作来源未记录':'尚未归档';return `${op.operator||'操作人未记录'} · ${formatMoment(op.occurredAt)}`},
    fileBindingType(file){return file?.bindingStatus==='ACTIVE'&&file?.isCurrent?'success':file?.bindingStatus?'danger':'warning'},
    fileBindingLabel(file){return file?.bindingStatus==='ACTIVE'&&file?.isCurrent?'当前绑定有效':file?.bindingStatus?`绑定${file.bindingStatus}`:'绑定状态待核对'},
    canOpenFile(file){return this.materialObject?.evidenceState==='VALID'&&file?.bindingStatus==='ACTIVE'&&file?.isCurrent===true},
    capture(){return {identity:this.identityKey,seq:this.seq}},
    current(c){return this.alive&&c.identity===this.identityKey&&c.seq===this.seq},
    recoveryKey(c){return 'aa-exemption-archive-command:'+c.identity},
    persistArchive(c){globalThis.sessionStorage.setItem(this.recoveryKey(c),JSON.stringify({commandKey:c.commandKey,row:{exemptionId:String(c.row.exemptionId),exemptionVersion:rowRevision(c.row,'exemption'),status:c.row.status,evidenceManifestHash:c.row.evidenceManifestHash??null,course:{id:String(c.row.course?.id||'')}}}))},
    forgetArchive(c){globalThis.sessionStorage.removeItem(this.recoveryKey(c))},
    restoreArchive(){
      if(!this.alive)return
      const c=this.capture()
      try{const raw=globalThis.sessionStorage.getItem(this.recoveryKey(c));if(!raw)return
        const p=JSON.parse(raw)
        if(!/^[A-Za-z0-9_-]{8,128}$/.test(p.commandKey)||!/^[1-9]\d*$/.test(p.row?.exemptionId)||rowRevision(p.row,'exemption')==null||!_TERMINAL.includes(p.row.status))throw new Error('归档恢复引用不完整')
        this.pending={...c,...p,recovered:true,acknowledged:false};this.receipt={exemptionId:p.row.exemptionId,verified:false}
      }catch(err){this.pending={...c,recovered:true};this.receipt={verified:false};this.error=err.message}
    },
    invalidate(){this.seq++;this.rows=[];this.pagination={page:1,pageSize:20,total:0};this.closeMaterials();this.error='';this.saving=false;this.checking=false;this.pending=null;this.receipt=null;this.command=null;this.confirmVisible=false;this.loading=false;this.restoreArchive()},
    fail(err,fallback='读取失败，请重试。'){if(/403|NO_DATA_SCOPE|NO_PERMISSION|FORBIDDEN/.test(String(err?.bizCode||err?.code||'')))this.invalidate();this.error=gradeError(err,fallback)},
    resetFilters(){if(this.saving||this.pending)return;this.filters={term:'',status:''};this.search()},
    search(){if(this.saving||this.pending)return;this.pagination.page=1;this.reload()},
    changePage(page){if(this.saving||this.pending)return;this.pagination.page=page;this.reload()},
    exType(s){return s==='APPROVED'?'success':s==='REJECTED'?'danger':'primary'},
    canArchive(row){return matchPermission(this.ctx.permissionPatterns||[],'academicAffairs.makeup.archive')&&_TERMINAL.includes(row.status)&&row.archiveStatus==='NOT_ARCHIVED'&&!this.saving&&!this.pending},
    async reload(){
      if(this.saving||this.pending)return
      const c={identity:this.identityKey,seq:++this.seq},params={term:this.filters.term||undefined,status:this.filters.status||undefined,page:this.pagination.page,pageSize:20}
      this.loading=true;this.error='';this.rows=[];this.closeMaterials()
      try{const res=await api.archiveList(params);if(!this.current(c))return;if(res?.code!==0)throw res;this.rows=res.data?.list||[];this.pagination.total=res.data?.total??this.rows.length}
      catch(err){if(this.current(c))this.fail(err)}finally{if(this.current(c))this.loading=false}
    },
    openMaterials(row){if(this.saving||this.pending)return;this.closeMaterials();this.materialObject={...row,course:{...(row.course||{})},resultGrade:{...(row.resultGrade||{})},currentGrade:{...(row.currentGrade||{})},archiveOperation:row.archiveOperation?{...row.archiveOperation}:null,evidenceProblems:[...(row.evidenceProblems||[])]};this.materialFiles=this.formalEvidenceFiles(row).map(f=>({...f}));this.materialsVisible=true},
    closeMaterials(){this.fileSeq++;this.materialsVisible=false;this.materialObject=null;this.materialFiles=[];this.fileError='';this.fileBusy=false},
    async openFile(file,action){
      if(this.fileBusy||!this.materialsVisible||!this.canOpenFile(file)||!this.materialFiles.some(f=>String(f.fileId)===String(file.fileId)))return
      const c=this.capture(),seq=++this.fileSeq,id=String(file.fileId),name=file.fileName
      const valid=()=>this.current(c)&&seq===this.fileSeq&&this.materialsVisible
      this.fileBusy=true;this.fileError=''
      try{
        const meta=await fileSdk.metadata(id);if(!valid())return
        if(file.sha256&&String(meta.sha256||'')!==String(file.sha256))throw {code:409,bizCode:'EVIDENCE_CHANGED'}
        if(!meta.allowedActions?.includes(action))throw {code:403}
        if(action==='preview'){
          const preview=await fileSdk.preview(id);if(!valid())preview?.close?.()
        } else await fileSdk.download(id,name||'材料')
      }catch(err){if(valid()){this.fileError=gradeError(err,'文件暂不可用，请稍后重新核对。');if(/403|NO_DATA_SCOPE|NO_PERMISSION|FORBIDDEN/.test(String(err?.bizCode||err?.code||'')))this.fail(err)}}finally{if(valid())this.fileBusy=false}
    },
    confirmArchive(row){if(!this.canArchive(row))return;if(rowRevision(row,'exemption')==null){this.error='申请版本未返回，不能确认归档对象。';return}this.command={...this.capture(),row:{...row,course:{...(row.course||{})}},filters:{...this.filters},page:this.pagination.page,term:this.filters.term||undefined};this.confirmVisible=true},
    async readArchive(command){const res=await api.archiveList({exemptionId:String(command.row.exemptionId),page:1,pageSize:2});if(res?.code!==0)throw res;return res.data?.list?.find(r=>String(r.exemptionId)===String(command.row.exemptionId))||null},
    async markArchived(){
      const c=this.command;if(!c||!this.current(c)||!this.canArchive(c.row))return
      this.saving=true;this.error=''
      try{
        const before=await this.readArchive(c);if(!this.current(c))return
        if(!before||before.status!==c.row.status||before.archiveStatus!=='NOT_ARCHIVED'||rowRevision(before,'exemption')!==rowRevision(c.row,'exemption')||String(before.evidenceManifestHash||'')!==String(c.row.evidenceManifestHash||'')||String(before.course?.id||'')!==String(c.row.course?.id||''))throw {code:409}
        if(!globalThis.crypto?.randomUUID)throw new Error('无法生成可靠命令标识，本次未发送')
        this.pending={...c,commandKey:globalThis.crypto.randomUUID(),acknowledged:false};this.receipt={...c.row,verified:false}
        this.persistArchive(this.pending)
        const identity={expectedVersion:rowRevision(c.row,'exemption'),expectedStatus:c.row.status,expectedEvidenceManifestHash:c.row.evidenceManifestHash??null}
        let res;try{res=await api.archiveExemption(c.row.exemptionId,identity,this.pending.commandKey)}catch(err){res=err}
        if(!this.current(c))return
        if(res?.code!==0&&/403|404|409|422|NO_DATA_SCOPE|FORBIDDEN|NO_PERMISSION|CONFLICT|VALIDATION/.test(String(res?.bizCode||res?.code||''))){this.forgetArchive(this.pending);this.pending=null;this.receipt=null;throw res}
        this.pending.acknowledged=res?.code===0&&String(res.data?.exemptionId)===String(c.row.exemptionId)&&res.data?.archiveStatus==='ARCHIVED'&&rowRevision(res.data,'exemption')===identity.expectedVersion+1
        this.pending.replyVersion=rowRevision(res.data,'exemption')
        await this.verifyArchive()
      }catch(err){if(this.current(c))this.fail(err,'归档结果待核实，请只读核对，不要重复提交。')}finally{if(this.current(c))this.saving=false}
    },
    async verifyArchive(){
      const c=this.pending;if(!c||this.checking||!this.current(c))return
      this.checking=true
      try{
        if(!c.row||!c.commandKey)throw new Error('归档恢复引用不可读取，不能继续发送')
        if(!c.acknowledged){const response=await api.commandReceipt(c.commandKey,'MAKEUP_EXEMPTION_ARCHIVE');if(!this.current(c))return
          if(response?.code!==0)throw response
          const r=response.data
          if(r?.commandKey!==c.commandKey||r.operation!=='MAKEUP_EXEMPTION_ARCHIVE'||!['SUCCESS','UNRESOLVED'].includes(r.state))throw new Error('原归档命令回执标识不一致')
          c.acknowledged=r.state==='SUCCESS'&&String(r.result?.exemptionId)===String(c.row.exemptionId)&&r.result?.archiveStatus==='ARCHIVED'&&rowRevision(r.result,'exemption')===rowRevision(c.row,'exemption')+1
          if(c.acknowledged)c.replyVersion=rowRevision(r.result,'exemption')
        }
        const row=await this.readArchive(c);if(!this.current(c))return
        if(!c.acknowledged){this.error='已回读当前正式归档状态，但本次命令回执尚未确认；不能据此认定本次操作成功，请勿重复提交。';return}
        if((c.recovered?['exemptionId','status']:['exemptionId','studentId','courseName','termCode','status']).some(key=>String(row?.[key]??'')!==String(c.row[key]??''))||String(row?.evidenceManifestHash||'')!==String(c.row.evidenceManifestHash||'')||String(row?.course?.id||'')!==String(c.row.course?.id||'')){this.error='归档记录与原确认对象不一致，请只读核对。';return}
        if(row?.archiveStatus!=='ARCHIVED'||rowRevision(row,'exemption')!==c.replyVersion){this.error='归档结果待核实，当前读取尚未确认原申请的归档版本。';return}
        this.forgetArchive(c);this.receipt={...row,verified:true};this.pending=null;this.confirmVisible=false;this.command=null;this.error=''
        const visible=this.rows.find(r=>String(r.exemptionId)===String(c.row.exemptionId));if(visible)Object.assign(visible,row)
      }catch(err){if(this.current(c))this.fail(err,'归档结果待核实，请稍后只读核对。')}finally{if(this.current(c))this.checking=false}
    }
  }
}
</script>

<style scoped>
.aamk-filter-lock { border:0;padding:0;margin:0;min-width:0; }
.aamk-overview { display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px; }
.aamk-overview article { display:grid;gap:6px;padding:16px;border:1px solid var(--border-200,#e1e7ef);border-radius:8px;background:var(--bg-white,#fff); }
.aamk-overview span,.aamk-overview small { font-size:12px;color:var(--text-secondary,#64748b); }
.aamk-overview strong { font-size:20px;color:var(--text-primary,#1f2937);overflow-wrap:anywhere; }
.aamk-cell-sub { display:block;margin-top:5px;font-size:12px;color:var(--text-secondary,#64748b); }
.aamk-object-head { display:flex;align-items:flex-start;justify-content:space-between;gap:16px;padding-bottom:14px;border-bottom:1px solid var(--border-200,#e1e7ef); }
.aamk-object-head p { margin:6px 0 0;color:var(--text-secondary,#64748b); }
.aamk-manifest,.aamk-operation { display:grid;gap:6px;margin:14px 0;padding:14px;border:1px solid var(--border-200,#e1e7ef);border-radius:8px;background:var(--surface-muted,#f8fafc); }
.aamk-manifest span,.aamk-manifest small,.aamk-operation small { color:var(--text-secondary,#64748b);font-size:12px; }
.aamk-manifest strong { overflow-wrap:anywhere; }
.aamk-files {list-style:none;padding:0;display:grid;gap:12px}
.aamk-files li,.aamk-receipt {display:grid;gap:10px;border:1px solid var(--border-200, #e1e7ef);padding:16px;border-radius:8px}
.aamk-files li div {display:flex;gap:8px}
.aamk-file-main { align-items:center;justify-content:space-between; }
.aamk-files li>span { color:var(--text-secondary,#64748b);font-size:12px;overflow-wrap:anywhere; }
.aamk-receipt p { margin:0; }

.aamk-filter { display: flex; gap: 16px; align-items: flex-end; flex-wrap: wrap; }
.aamk-filter__item { display: flex; flex-direction: column; gap: 4px; font-size: 12px; color: var(--text-secondary, #64748b); }
.aamk-muted { color: var(--text-tertiary, #94a3b8); font-size: 12px; }
@media(max-width:1100px){.aamk-overview{grid-template-columns:repeat(2,minmax(0,1fr))}}
</style>
