<template>
  <ModulePageShell title="成绩复查" subtitle="核对复查申请与原成绩，按当前权限办理复审" :role-name="ctx.currentRole.roleName" :data-scope-name="ctx.dataScope.scopeName">
    <div class="mp-stack">
      <div class="aa-filter"><label class="aa-filter-field"><span>状态</span><AppSelect v-model="status" :options="statusOptions" :disabled="busy || !!pending" @change="search" /></label><AppButton variant="ghost" :disabled="busy || !!pending" @click="search">查询</AppButton></div>
      <section v-if="receipt" class="aa-recheck-receipt" role="status"><strong>{{ receipt.verified ? '原复查命令已由持久回执确认' : '结果待核实' }}</strong><p>{{ receipt.studentName || active?.studentName || '原申请' }} · {{ receipt.courseName || active?.courseName || '课程待回读' }}</p><p v-if="receipt.commandStatus">原命令结果：{{ statusLabel(receipt.commandStatus) }}</p><p v-if="receipt.status">当前正式记录：{{ statusLabel(receipt.status) }}<template v-if="receipt.commandStatus && receipt.commandStatus !== receipt.status">（已发生后续变化）</template></p><AppButton v-if="pending" :loading="checking" @click="verifyReceipt">只读核对持久回执</AppButton><p v-else>原命令成功与当前状态分别展示；当前记录后续变化不会否认原命令成功。</p></section>
      <ErrorState v-if="error" :description="error" @retry="pending ? verifyReceipt() : restoreRoute()" />
      <AppButton v-if="pending?.postFailure?.bizCode === 'TERM_ARCHIVED'" variant="ghost" :disabled="checking" @click="clearRejectedCommand(pending, pending.postFailure)">本次因学期封存未受理，保留意见返回办理</AppButton>
      <div class="aa-recheck-workspace">
        <AppSectionCard title="复查申请队列">
          <LoadingState v-if="loading" />
          <EmptyState v-else-if="!rows.length" title="暂无复查申请" description="可切换状态或页码查询" />
          <ul v-else class="aa-recheck-queue"><li v-for="row in rows" :key="row.recheckId"><button :class="['aa-recheck-item', { 'is-active': active?.recheckId === row.recheckId }]" :disabled="busy || !!pending" @click="openReview(row)"><strong>{{ row.studentName }} · {{ row.courseName }}</strong><span>{{ row.studentNo }} · {{ row.term || '学期待核对' }}</span><AppStatusTag :type="statusColor(row.status)">{{ statusLabel(row.status) }}</AppStatusTag></button></li></ul>
          <div class="aa-pages"><AppButton variant="ghost" :disabled="pagination.page <= 1 || busy || !!pending" @click="changePage(pagination.page - 1)">上一页</AppButton><span>{{ pagination.page }} / {{ Math.max(1, Math.ceil(pagination.total / pagination.pageSize)) }}</span><AppButton variant="ghost" :disabled="pagination.page * pagination.pageSize >= pagination.total || busy || !!pending" @click="changePage(pagination.page + 1)">下一页</AppButton></div>
        </AppSectionCard>
        <div v-if="active" class="mp-stack">
          <AppSectionCard :title="`${active.studentName} · ${active.courseName}`">
            <dl class="aa-facts"><div><dt>学号 / 学期</dt><dd>{{ active.studentNo }} / {{ active.term || '待核对' }}</dd></div><div><dt>原正式成绩</dt><dd>{{ active.originalScore ?? '待核对' }}</dd></div><div><dt>复查理由</dt><dd>{{ active.reason || '待核对' }}</dd></div><div><dt>正式受理状态</dt><dd>{{ statusLabel(active.status) }}</dd></div><div><dt>复审意见</dt><dd>{{ active.reviewNote || '暂无' }}</dd></div><div><dt>复审后成绩</dt><dd>{{ active.newScore ?? '暂无调整记录' }}</dd></div></dl>
            <p class="mp-note">名单版本、策略版本与源成绩新鲜度未在当前读接口中提供，页面不将其标为已核验。</p>
          </AppSectionCard>
          <AppSectionCard v-if="active.status === 'SUBMITTED'" title="本岗位办理">
            <p v-if="!canReview" class="mp-note">当前身份可查看申请，没有成绩复审办理权限。</p>
            <template v-else>
              <AppFormItem label="复审结论"><AppSelect v-model="form.action" :options="actionOptions" :disabled="busy || !!pending" /></AppFormItem>
              <AppFormItem v-if="form.action === 'ADJUST'" label="调整后成绩" required><AppTextInput v-model="form.newScore" type="number" :disabled="busy || !!pending" size="compact" /></AppFormItem>
              <AppFormItem :label="form.action === 'REJECT' ? '不予受理原因' : '复审意见'" :required="form.action !== 'UPHOLD'"><AppTextarea v-model="form.note" :rows="3" :disabled="busy || !!pending" placeholder="填写核验依据；调整成绩或不予受理至少5字" /></AppFormItem>
              <div class="aa-actions"><AppButton variant="primary" :disabled="!!pending" :loading="busy" @click="openConfirm">确认复审结果</AppButton><AppButton variant="ghost" :disabled="busy || !!pending" @click="closeReview">返回原列表位置</AppButton></div>
            </template>
          </AppSectionCard>
          <div v-else class="aa-actions"><AppButton variant="ghost" :disabled="busy || !!pending" @click="closeReview">返回原列表位置</AppButton></div>
        </div>
        <EmptyState v-else title="选择一条复查申请" description="先核对学生、课程、原成绩与申请理由" />
      </div>
    </div>
    <AppConfirmDialog v-model:visible="confirmVisible" title="确认当前复查结果" confirm-text="提交复审结果" :submitting="busy" @confirm="doReview">
      <p>{{ command?.studentName }} · {{ command?.courseName }}</p><p>结论：{{ actionLabel(command?.action) }}<template v-if="command?.action === 'ADJUST'">，拟调整为 {{ command.newScore }} 分</template></p><p>意见：{{ command?.note || '未填写' }}</p><p class="mp-note">由服务器重新校验并办理；提交后读取正式申请结果。</p>
    </AppConfirmDialog>
  </ModulePageShell>
</template>
<script>
/** Page ID: AA-195 成绩复查。 */
import { ModulePageShell, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppSectionCard, AppStatusTag, AppFormItem, AppSelect, AppTextInput, AppTextarea, AppConfirmDialog } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { currentUserFromToken } from '@/services/http/client'
import { matchPermission } from '@/config/navPlan'
import { gradeError } from './parallel-c/grade-review'
import { createGradeCommandReference, findGradeCommandReference, gradeCommandIdentityRef, removeGradeCommandReference, updateGradeCommandReference } from './parallel-c/grade-command-recovery'
import { toast } from '@/utils/toast'
const STATUS = { SUBMITTED: '待复审', UPHELD: '已维持原成绩', ADJUSTED: '已调整成绩', REJECTED: '不予受理' }
export default {
  name: 'AaGradeRecheckView',
  components: { ModulePageShell, LoadingState, ErrorState, EmptyState, AppButton, AppSectionCard, AppStatusTag, AppFormItem, AppSelect, AppTextInput, AppTextarea, AppConfirmDialog },
  props: { ctx: { type: Object, required: true } },
  data() { return {
    alive: true, readSeq: 0, objectSeq: 0, loading: false, error: '', status: '', rows: [], active: null, busy: false, checking: false,
    pagination: {page: 1, pageSize: 20, total: 0}, pending: null, receipt: null, command: null, confirmVisible: false,
    form: {action: 'UPHOLD', newScore: '', note: ''},
    statusOptions: [{label:'全部',value:''}, ...Object.entries(STATUS).map(([value,label])=>({value,label}))],
    actionOptions: [{label:'维持原成绩',value:'UPHOLD'},{label:'调整成绩',value:'ADJUST'},{label:'不予受理',value:'REJECT'}]
  } },
  computed: {
    identityKey() { const u=currentUserFromToken() || {}; return JSON.stringify([u.tenantId,u.userId,u.activeContextId,u.currentRoleCode,this.ctx.currentRole,this.ctx.dataScope,this.ctx.permissionPatterns]) },
    recoveryIdentity() { return gradeCommandIdentityRef(currentUserFromToken() || {}, this.ctx) },
    routeKey() { return this.$route?.fullPath || '' },
    canReview() { return matchPermission(this.ctx.permissionPatterns || [], 'academicAffairs.grade.publish') }
  },
  watch: {
    identityKey() { this.invalidate(); this.restoreWithRecovery() },
    routeKey() { this.resetForRoute() }
  },
  created() { this.restoreWithRecovery() },
  beforeUnmount() { this.alive=false; this.invalidate() },
  methods: {
    statusLabel(s) { return STATUS[s] || '状态待确认' },
    statusColor(s) { return s==='ADJUSTED'?'success':s==='REJECTED'?'danger':s==='SUBMITTED'?'primary':'default' },
    actionLabel(s) { return this.actionOptions.find(x=>x.value===s)?.label || '待核对' },
    invalidate() { this.readSeq++; this.objectSeq++; this.rows=[]; this.active=null; this.pending=null; this.receipt=null; this.command=null; this.confirmVisible=false; this.busy=false; this.checking=false; this.loading=false; this.error=''; this.pagination={page:1,pageSize:20,total:0}; this.form={action:'UPHOLD',newScore:'',note:''} },
    restoreWithRecovery() {
      const found=findGradeCommandReference(this.recoveryIdentity,'RECHECK_REVIEW')
      if(!found.ok){this.pending={...this.capture(),recoveryUnavailable:true};this.receipt={verified:false};this.error=`恢复引用暂不可读，写入已锁定：${found.error}`;return}
      if(!found.entry){this.restoreRoute();return}
      const entry=found.entry;this.status=entry.status||'';this.pagination.page=entry.page
      this.pending={...this.capture(entry.objectId),commandKey:entry.commandKey,operation:entry.operation,page:entry.page,status:entry.status,recovered:true}
      const pending=this.pending;this.receipt={verified:false};this.error='检测到原身份的复查命令引用，正在只读核对持久回执。'
      if(!pending.id){this.error='恢复引用缺少复查申请编号，写入保持锁定且不会自动重放。';return}
      this.verifyReceipt()
    },
    exactId(value) { if(!['string','number'].includes(typeof value))return ''; const id=String(value ?? '').trim(); return /^[1-9]\d*$/.test(id) ? id : '' },
    resetForRoute() {
      const pending=this.pending,receipt=this.receipt,active=this.active,form={...this.form}
      this.invalidate()
      if(pending?.identity===this.identityKey){
        this.pending={...pending,route:this.routeKey,seq:this.objectSeq};this.active=active;this.form=form
        this.receipt=receipt;this.pagination.page=pending.page;this.status=pending.status
        this.error='原复查请求仍待核实；当前保留原申请，请只读核对其结果。'
        return
      }
      this.restoreRoute()
    },
    capture(id) { return {identity:this.identityKey,route:this.routeKey,seq:this.objectSeq,id:this.exactId(id)} },
    valid(c) { return this.alive && c.identity===this.identityKey && c.route===this.routeKey && c.seq===this.objectSeq },
    commandCurrent(c) { return this.valid(c) && c.id && this.pending===c },
    current(c) { return this.valid(c) && c.id && String(c.id)===String(this.active?.recheckId) },
    denied(err) { if (/403|NO_DATA_SCOPE|NO_PERMISSION|FORBIDDEN/.test([err?.status,err?.statusCode,err?.bizCode,err?.code].join(' '))) { const message=gradeError(err); this.invalidate(); this.error=message; return true } return false },
    conflict(err) { return /409|CONFLICT|VERSION/.test([err?.bizCode,err?.code].join(' ')) },
    explicitFailure(err) { return /400|403|409|422|NO_DATA_SCOPE|FORBIDDEN|NO_PERMISSION|CONFLICT|VALIDATION|TERM_ARCHIVED/.test([err?.httpStatus,err?.status,err?.statusCode,err?.bizCode,err?.code].join(' ')) },
    async navigate(patch) {
      const query={...this.$route.query,...patch}
      Object.keys(query).forEach(key=>{if(query[key]==null || query[key]==='')delete query[key]})
      const before=this.routeKey
      try{await this.$router.replace({path:this.$route.path,query})}catch{/* duplicate navigation */}
      if(before===this.routeKey)this.restoreRoute()
    },
    changePage(page) { if(this.busy || this.pending)return; this.navigate({page:String(page),status:this.status||undefined,recheckId:undefined}) },
    search() { if(this.busy || this.pending)return; this.navigate({page:'1',status:this.status||undefined,recheckId:undefined}) },
    closeReview() { if(this.busy || this.pending)return; this.navigate({page:String(this.pagination.page),status:this.status||undefined,recheckId:undefined}) },
    restoreRoute() {
      if(this.busy || this.pending)return
      const allowed=new Set(this.statusOptions.map(item=>item.value)),query=this.$route?.query||{}
      this.status=allowed.has(String(query.status||''))?String(query.status||''):''
      const page=Number(query.page);this.pagination.page=Number.isInteger(page)&&page>0?page:1
      if(query.recheckId!=null&&!this.exactId(query.recheckId)){this.error='复查申请编号无效，请从队列重新进入';return}
      this.load(this.exactId(query.recheckId))
    },
    async readExact(id) {
      const exact=this.exactId(id);if(!exact)throw {code:404,bizCode:'INVALID_OBJECT_ID'}
      const res=await academicAffairsApi.getGradeRecheck(exact);if(res?.code!==0)throw res
      if(!res.data || String(res.data.recheckId)!==exact)throw {code:409,bizCode:'OBJECT_ID_MISMATCH',message:'正式复查记录与请求对象不一致'}
      return res.data
    },
    sameSource(a,b,versions=true) { return ['recheckId','studentId','studentNo','acadGradeId','courseName','term','originalScore','reason','createdAt',...(versions?['version','recordVersion','gradeVersion']:[])].every(k=>String(a?.[k] ?? '')===String(b?.[k] ?? '')) },
    replaceFormal(formal) { this.active={...formal}; const row=this.rows.find(item=>String(item.recheckId)===String(formal.recheckId)); if(row)Object.assign(row,formal) },
    async load(detailId='') {
      if (this.busy || this.pending) return
      const seq=++this.readSeq,objectSeq=++this.objectSeq,c={identity:this.identityKey,route:this.routeKey,seq:objectSeq,id:detailId}
      const valid=()=>this.valid(c)&&seq===this.readSeq
      this.active=null;this.command=null;this.confirmVisible=false;this.form={action:'UPHOLD',newScore:'',note:''};this.loading=true;this.error='';this.rows=[];this.pagination.total=0
      try {
        if(detailId){const formal=await this.readExact(detailId);if(!valid())return;this.replaceFormal(formal);this.form={action:'UPHOLD',newScore:formal.originalScore ?? '',note:''}}
        const res=await academicAffairsApi.getGradeRechecks({status:this.status || undefined,page:this.pagination.page,pageSize:this.pagination.pageSize})
        if(!valid())return; if(res.code!==0)throw res
        this.rows=res.data?.list || []; this.pagination.total=res.data?.total ?? this.rows.length
        if(this.active){const row=this.rows.find(item=>String(item.recheckId)===String(this.active.recheckId));if(row)Object.assign(row,this.active)}
      } catch(err) { if(valid() && !this.denied(err))this.error=gradeError(err,'复查队列读取失败，请重试。') }
      finally { if(valid())this.loading=false }
    },
    openReview(row) { if(this.busy || this.pending)return; const id=this.exactId(row?.recheckId);if(id)this.navigate({page:String(this.pagination.page),status:this.status||undefined,recheckId:id}) },
    openConfirm() {
      if(this.busy || this.pending || !this.canReview || this.active?.status!=='SUBMITTED')return
      if(!['UPHOLD','ADJUST','REJECT'].includes(this.form.action))return
      const score=Number(this.form.newScore)
      if(this.form.action==='ADJUST' && (String(this.form.newScore ?? '').trim()==='' || !Number.isInteger(score) || score<0 || score>100)) { toast.error('调整后成绩须为0-100的整数，空值不是0'); return }
      if(this.form.action==='REJECT' && this.form.note.trim().length<5) { toast.error('不予受理原因至少5字'); return }
      if(this.form.action==='ADJUST' && this.form.note.trim().length<5) { toast.error('调整成绩的核验依据至少5字'); return }
      this.command={...this.capture(this.active.recheckId),row:{...this.active},studentName:this.active.studentName,courseName:this.active.courseName,action:this.form.action,newScore:this.form.action==='ADJUST'?score:undefined,note:this.form.note.trim(),page:this.pagination.page,status:this.status,ack:null}
      this.confirmVisible=true
    },
    async doReview() {
      const c=this.command
      if(!c || !this.confirmVisible || !this.current(c) || this.busy || this.pending || !this.canReview)return
      this.busy=true; this.error=''
      try {
        const before=await this.readExact(c.id)
        if(!this.current(c))return
        if(before.status!=='SUBMITTED' || !this.sameSource(before,c.row)) { this.replaceFormal(before);this.confirmVisible=false;this.command=null;this.error='申请、源成绩或版本已变化；已保留填写内容，请重新确认。'; return }
        const saved=createGradeCommandReference({identityRef:this.recoveryIdentity,operation:'RECHECK_REVIEW',objectId:c.id,page:c.page,status:c.status})
        if(!saved.ok){this.confirmVisible=false;this.error=`无法保存刷新恢复引用，本次未发送：${saved.error}`;return}
        this.pending={...c,commandKey:saved.entry.commandKey,operation:'RECHECK_REVIEW'};const pending=this.pending;this.receipt={...pending,verified:false}
        if(saved.existing){pending.recovered=true;this.confirmVisible=false;this.error='同一复查申请已有命令在途，本次未重复发送；正在只读核对。';await this.verifyReceipt();return}
        let res
        try { res=await academicAffairsApi.reviewGradeRecheck(c.id,{action:c.action,note:c.note || undefined,newScore:c.newScore},pending.commandKey) } catch(err) { res=err }
        if(!this.commandCurrent(pending))return
        this.confirmVisible=false
        pending.postFailure=res?.code===0?null:res
        await this.verifyReceipt()
      } catch(err) { if(this.current(c) && !this.denied(err)){if(this.conflict(err)){try{const formal=await this.readExact(c.id);if(this.current(c))this.replaceFormal(formal)}catch(readErr){if(this.current(c)&&this.denied(readErr))return}}this.confirmVisible=false;this.error=gradeError(err,'未能核对原申请，本次未提交；填写内容已保留。')} }
      finally { if(this.valid(c))this.busy=false }
    },
    async readPersistentReceipt(c) {
      const res=await academicAffairsApi.getGradeCommandReceipt(c.commandKey,c.operation);if(res?.code!==0)throw res
      const data=res.data
      if(!data || data.commandKey!==c.commandKey || data.operation!==c.operation || !['SUCCESS','UNRESOLVED'].includes(data.state) || (data.state==='SUCCESS'&&!data.result) || (data.state==='UNRESOLVED'&&data.result!=null))throw {code:'GRADE_COMMAND_RECEIPT_MISMATCH',message:'命令回执与当前恢复引用不一致'}
      return data
    },
    async clearRejectedCommand(c,failure) {
      if(this.denied(failure))return
      const removed=removeGradeCommandReference(c.commandKey,this.recoveryIdentity)
      if(!removed.ok){this.error=`服务器已明确拒绝本次操作，但本地恢复标记无法清除：${removed.error}`;return}
      this.pending=null;this.receipt=null
      if(this.conflict(failure)){try{const formal=await this.readExact(c.id);if(this.valid(c))this.replaceFormal(formal)}catch(readErr){if(this.valid(c)&&this.denied(readErr))return}}
      if(this.valid(c))this.error=gradeError(failure,'本次复审未受理；已保留填写内容，请重新读取后确认。')
    },
    async verifyReceipt() {
      if(this.pending?.recoveryUnavailable){this.pending=null;this.restoreWithRecovery();return}
      const c=this.pending
      if(!c || !this.commandCurrent(c) || this.checking)return
      this.checking=true
      try {
        const persisted=await this.readPersistentReceipt(c)
        if(!this.commandCurrent(c))return
        if(persisted.state==='UNRESOLVED'){
          if(c.postFailure&&this.explicitFailure(c.postFailure)){await this.clearRejectedCommand(c,c.postFailure);return}
          this.error='持久回执尚未确认原复查命令；不会自动重发，请稍后只读核对。';return
        }
        if(String(persisted.result?.recheckId)!==String(c.id))throw {code:'GRADE_COMMAND_RECEIPT_OBJECT_MISMATCH',message:'持久回执与原复查申请不一致'}
        if(!['UPHELD','ADJUSTED','REJECTED'].includes(persisted.result.status))throw {code:'GRADE_COMMAND_RECEIPT_MISMATCH',message:'持久回执未包含有效复审结果'}
        if(!c.recovered && (!this.sameSource(persisted.result,c.row,false) || persisted.result.status!==({UPHOLD:'UPHELD',ADJUST:'ADJUSTED',REJECT:'REJECTED'})[c.action] || String(persisted.result.reviewNote || '').trim()!==c.note || (c.action==='ADJUST' && (persisted.result.newScore==null || Number(persisted.result.newScore)!==c.newScore))))throw {code:'GRADE_COMMAND_RECEIPT_MISMATCH',message:'持久回执与已确认的复审内容不一致'}
        updateGradeCommandReference(c.commandKey,this.recoveryIdentity,{confirmedAt:Date.now()})
        const formal=await this.readExact(c.id)
        if(!this.commandCurrent(c))return
        this.replaceFormal(formal)
        this.receipt={studentName:formal.studentName,courseName:formal.courseName,commandStatus:persisted.result.status,status:formal.status,verified:true}
        const removed=removeGradeCommandReference(c.commandKey,this.recoveryIdentity)
        if(!removed.ok){this.error=`原命令和正式记录已确认，但本地恢复标记无法清除：${removed.error}`;return}
        this.pending=null;this.command=null;this.error=''
      } catch(err) {
        if(!this.commandCurrent(c))return
        if(!this.denied(err))this.error=gradeError(err,'原复查命令结果待核实，请稍后只读核对；不会自动重发。')
      } finally { if(this.valid(c) && (!this.pending || this.pending===c))this.checking=false }
    }
  }
}
</script>
<style scoped>
@import '@/styles/module-page.css';
.aa-filter,.aa-actions,.aa-pages{display:flex;gap:12px;align-items:center;flex-wrap:wrap}.aa-pages{justify-content:center;margin-top:16px}
.aa-recheck-workspace{display:grid;grid-template-columns:300px minmax(0,1fr);gap:18px;align-items:start}
.aa-recheck-queue{list-style:none;padding:0;margin:0}.aa-recheck-item{display:flex;flex-direction:column;align-items:flex-start;gap:8px;width:100%;text-align:left;border:0;border-bottom:1px solid var(--border-200);padding:16px;background:var(--bg-white);color:var(--text-900);cursor:pointer}.aa-recheck-item.is-active{background:var(--primary-50);border-left:3px solid var(--primary-600)}.aa-recheck-item span{font-size:12px;color:var(--text-500)}
.aa-facts{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}.aa-facts dt{font-size:12px;color:var(--text-500)}.aa-facts dd{margin:6px 0 0;overflow-wrap:anywhere}.aa-recheck-receipt{padding:16px;border:1px solid var(--border-200);border-radius:10px;background:var(--bg-white)}
@media(max-width:900px){.aa-recheck-workspace{grid-template-columns:1fr}}
</style>
