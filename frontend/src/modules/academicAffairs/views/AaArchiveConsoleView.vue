<template>
  <ModulePageShell
    :title="pageTitle"
    :subtitle="pageSubtitle"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton v-if="canManageArchive" variant="primary" :disabled="actionBusy || !!pendingCommand" @click="openCreate">新建归档批次</AppButton>
    </template>

    <AppInlineAlert v-if="actionNotice" :type="pendingCommand ? 'warning' : 'success'" :description="actionNotice" />
    <AppInlineAlert v-if="confirmError" type="danger" :description="confirmError" />
    <AppButton v-if="pendingCommand?.termId" @click="readPendingOriginal">刷新查看原学期{{ pendingCommand.batchId ? `归档批次 ${pendingCommand.batchId}` : '归档批次列表' }}</AppButton>
    <div class="aaar-context">
      <AppFormItem label="学期"><AppTermEntityPicker :model-value="routeTermId()" placeholder="全部学期" :disabled="actionBusy || !!pendingCommand" @update:model-value="changeTerm" /></AppFormItem>
      <span v-if="current">当前批次：{{ current.batchName }}</span>
    </div>
    <div class="aaar-layout">
      <section class="aaar-list">
        <header class="aaar-list-head"><div><h2>学期归档批次</h2><p>{{ isCollegeScope ? '查看学校归档进度；本院缺项请进入实时预检' : '选择批次查看十三域正式结论' }}</p></div><span>{{ rows.length }} 个批次</span></header>
        <LoadingState v-if="loading" />
        <ErrorState v-else-if="listError" :description="listError" @retry="load" />
        <EmptyState v-else-if="!rows.length" title="暂无归档批次" :description="canManageArchive ? '按学期新建归档批次' : '学校归档批次由校教务统筹建立'" />
        <ul v-else class="aaar-items">
          <li
            v-for="b in rows"
            :key="b.batchId"
            :class="['aaar-item', { 'is-active': current && current.batchId === b.batchId }]"
            role="button"
            tabindex="0"
            :aria-current="current && current.batchId === b.batchId ? 'true' : undefined"
            @click="select(b)"
            @keydown.enter.prevent="select(b)"
            @keydown.space.prevent="select(b)"
          >
            <span class="aaar-item__name"><strong>{{ b.batchName }}</strong><small>{{ b.termCode || '学期待核对' }}</small></span>
            <span class="aaar-item__facts"><small>{{ batchMissingLabel(b) }}</small><StatusTag :type="sType(b.status)" :label="sLabel(b.status)" dot /></span>
          </li>
        </ul>
      </section>

      <div class="aaar-detail">
        <EmptyState v-if="!current" :title="!rows.length && !canManageArchive ? '等待校教务建立归档批次' : '选择批次'" :description="isCollegeScope ? '从左侧选择批次查看学校归档进度，并进入本院实时预检' : canManageArchive ? '从左侧选择归档批次执行完整性检查与归档' : rows.length ? '从左侧选择批次查看学校归档进度；正式检查与封存由校教务负责' : '批次建立后，可在此查阅学校归档进度'" />
        <template v-else>
          <section class="aaar-object-card">
            <div class="aaar-object-main">
              <div class="aaar-title">{{ current.batchName }}</div>
              <p v-if="isCollegeScope">本院缺项以实时检查结果为准</p>
            </div>
            <div class="aaar-current-state"><StatusTag :type="sType(current.status)" :label="sLabel(current.status)" dot /><span>当前责任：{{ archiveOwner }}</span></div>
            <details class="aaar-responsibility"><summary>查看办理责任与下一步</summary>
              <p>当前阻断：{{ blockerText }}</p><p>下一责任岗位：{{ nextRole }}</p>
            </details>
          </section>
          <AppInlineAlert v-if="isCollegeScope" type="info" :description="archiveScopeNote" />
          <div v-if="isCollegeScope" class="aaar-head">
            <div><strong>本院归档准备</strong><small>进入该学期的本院实时预检，核对本院缺项与责任岗位</small></div>
            <AppButton variant="primary" :disabled="!current.termId" @click="goCollegePrecheck">查看本院实时预检</AppButton>
          </div>
          <ol v-else class="aaar-stage-rail" aria-label="归档办理阶段">
            <li class="is-done"><b>✓</b><span><strong>建立批次</strong><small>学期对象已锁定</small></span></li>
            <li :class="{ 'is-done': items.length === 13, 'is-current': !items.length }"><b>{{ items.length === 13 ? '✓' : '2' }}</b><span><strong>十三域检查</strong><small>{{ items.length === 13 ? '已读取正式结论' : '等待检查' }}</small></span></li>
            <li :class="{ 'is-done': current.status === 'READY' || current.status === 'ARCHIVED', 'is-current': current.status === 'MISSING_ITEMS' }"><b>{{ current.status === 'READY' || current.status === 'ARCHIVED' ? '✓' : '3' }}</b><span><strong>缺失处理</strong><small>{{ current.status === 'MISSING_ITEMS' ? '当前责任阶段' : '按结果解锁' }}</small></span></li>
            <li :class="{ 'is-done': current.status === 'ARCHIVED', 'is-current': current.status === 'READY' }"><b>{{ current.status === 'ARCHIVED' ? '✓' : '4' }}</b><span><strong>正式封存</strong><small>{{ current.status === 'READY' ? '等待确认' : '按状态解锁' }}</small></span></li>
            <li :class="{ 'is-done': current.status === 'ARCHIVED' }"><b>{{ current.status === 'ARCHIVED' ? '✓' : '5' }}</b><span><strong>受控纠错</strong><small>{{ current.status === 'ARCHIVED' ? '普通解冻关闭' : '封存后启用' }}</small></span></li>
          </ol>
          <AppInlineAlert v-if="!isCollegeScope && current.status === 'READY' && !canConfirmArchive" type="warning" :description="confirmReason" />
          <AppButton v-if="!isCollegeScope && current.status === 'READY' && !canConfirmArchive" size="small" :disabled="actionBusy || !!pendingCommand" @click="refreshCurrentFromServer">重新核对归档权限</AppButton>
          <div v-if="!isCollegeScope || current.archivedAt" class="aaar-summary">
            <span v-if="!isCollegeScope" :class="{ 'is-bad': Number(current.missingCount) > 0 }">{{ batchMissingLabel(current) }}</span>
            <span v-if="current.archivedAt">归档于 {{ fmt(current.archivedAt) }}（历史记录已封存）</span>
          </div>
          <AppInlineAlert
            v-if="!isCollegeScope && current.status === 'MISSING_ITEMS'"
            type="warning"
            description="当前仍有已阻断或待处理的数据域，整体强制归档已停用。请处理阻断或待处理的数据域后重新执行完整性检查。"
          />
          <AppInlineAlert
            v-if="current.status === 'ARCHIVED'"
            type="info"
            :description="isCollegeScope ? '学校已完成该学期正式封存；封存材料由校教务统筹，如本院发现错误请按责任岗位反馈。' : '该学期已经形成正式归档，普通解冻入口已关闭。后续发现错误时必须走归档后纠错，保留原归档版本、纠错原因和新版本审计记录。'"
          />

          <AaArchiveCorrectionWorkspace
            v-if="canManageArchive && current.status === 'ARCHIVED'"
            :batch="current"
            :items="items"
            @refresh-batch="refreshCurrentFromServer"
          />
          <template v-else-if="!isCollegeScope">
            <div class="aaar-section-title"><strong>归档资料检查</strong>
              <AppButton v-if="current.termId" size="small" variant="ghost" @click="goCollegePrecheck">查看缺失提醒</AppButton>
            </div>
            <div v-if="items.length" class="aaar-counts">
              <span>已通过 {{ items.filter(row => itemState(row) === 'PASS').length }} 类</span>
              <span>不适用 {{ items.filter(row => itemState(row) === 'NOT_APPLICABLE').length }} 类</span>
              <span>阻断 {{ items.filter(row => itemState(row) === 'BLOCKED').length }} 类</span>
              <span>待核验 {{ items.filter(row => itemState(row) === 'UNKNOWN').length }} 类</span>
            </div>
            <EmptyState v-if="!items.length" title="未检查" description="点击「完整性检查」聚合各数据域" />
            <DataTable v-else :columns="itemColumns" :rows="items" row-key="domain">
              <template #cell-domain="{ row }">{{ row.domainLabel }}</template>
              <template #cell-result="{ row }"><StatusTag :type="itemType(row)" :label="itemLabel(row)" dot /></template>
            </DataTable>
          </template>
          <div v-if="canManageArchive" class="aaar-head">
            <div><strong>当前主动作</strong><small>{{ archiveActionHint }}</small></div>
            <div class="aaar-actions">
              <AppButton v-if="['DRAFT','MISSING_ITEMS','READY'].includes(current.status)" size="small" variant="ghost" :disabled="!!pendingCommand" :loading="actionBusy" @click="doCheck">完整性检查</AppButton>
              <AppButton v-if="current.status === 'READY'" size="small" variant="primary" :disabled="actionBusy || !!pendingCommand || !canConfirmArchive" @click="doConfirm">确认归档</AppButton>
              <AppButton v-if="!['ARCHIVED','CANCELLED'].includes(current.status)" size="small" variant="ghost" :disabled="actionBusy || !!pendingCommand" @click="doCancel">取消</AppButton>
            </div>
          </div>
        </template>
      </div>
    </div>

    <AppDrawer :visible="createVisible && canManageArchive" title="新建归档批次" mode="modal" size="small" @close="createVisible = false">
      <div class="aaar-form">
        <AppFormItem label="学期" required><AppTermEntityPicker v-model="form.termId" placeholder="选择要归档的学期（一学期一批次）" :disabled="saving" /></AppFormItem>
        <AppInlineAlert type="warning" description="确认归档后该学期将成为不可普通回退的历史记录，教务写操作会被拦截；如后续发现错误，必须走归档后纠错并保留原版本。" />
        <AppInlineAlert v-if="formError" type="danger" :description="formError" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="saving" @click="createVisible = false">取消</AppButton>
        <AppButton variant="primary" :loading="saving" :disabled="!canManageArchive || !!pendingCommand" @click="submitCreate">创建</AppButton>
      </template>
    </AppDrawer>

    <AppConfirmDialog
      v-model:visible="confirmVisible"
      :title="confirmTitle"
      :message="confirmMessage"
      :submitting="actionBusy"
      :confirm-disabled="!canManageArchive || (confirmKind === 'confirm' && !canConfirmArchive)"
      @confirm="onConfirm"
    ><AppInlineAlert v-if="confirmKind === 'confirm' && (confirmError || !canConfirmArchive)" type="warning" :description="confirmError || confirmReason" /></AppConfirmDialog>
  </ModulePageShell>
</template>

<script>
import { academicFlowOwner, academicFlowNextOwner, academicFlowText } from '../config/academicFlowRegistry.js'

/** 教务归档 · 控制台（/admin/academic-affairs/archive）：批次+数据域四态检查+不可逆归档封存。 */
import { ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton, AppDrawer } from '@/components/ui'
import { AppFormItem, AppConfirmDialog, AppInlineAlert, AppTermEntityPicker } from '@/components/common'
import { academicAffairsArchiveApi as api } from '@/modules/academicAffairs/api/academic-affairs.api'
import AaArchiveCorrectionWorkspace from '@/modules/academicAffairs/components/AaArchiveCorrectionWorkspace.vue'
import { toast } from '@/utils/toast'
import { matchPermission } from '@/config/navPlan'
import { currentUserFromToken } from '@/services/http/client'
import { gradeError } from './parallel-c/grade-review'
import { readAllPages } from '../components/parallel-a/pagedRead'

const _SL = { DRAFT: '草稿', CHECKING: '检查中', READY: '完整可归档', MISSING_ITEMS: '有阻断', ARCHIVED: '已归档', CANCELLED: '已取消' }
const _IL = { PASS: '通过', BLOCKED: '阻断', UNKNOWN: '待处理', NOT_APPLICABLE: '不适用' }
const _IT = { PASS: 'success', BLOCKED: 'danger', UNKNOWN: 'warning', NOT_APPLICABLE: 'info' }
const ARCHIVE_DOMAINS=['STUDENT_STATUS','REGISTRATION','STATUS_CHANGE','PROGRAM','TEACHING_TASK','SCHEDULE','SELECTION','EXAM','GRADE','MAKEUP','EVALUATION','TEXTBOOK','GRADUATION']

export default {
  name: 'AaArchiveConsoleView',
 components: { ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState, AppButton, AppDrawer, AppFormItem, AppConfirmDialog, AppInlineAlert, AppTermEntityPicker, AaArchiveCorrectionWorkspace },
  props:{ctx:{type:Object,required:true}},
 data() {
    return {
      alive:true,scope:0,seq:0,detailSeq:0,pendingCommand:null,actionNotice:'',
      listError: '', loading: true, rows: [], current: null, items: [],
      itemColumns: [{ key: 'domain', title: '归档资料' }, { key: 'recordCount', title: '正式记录数' }, { key: 'result', title: '检查结论' }, { key: 'remark', title: '说明' }],
      createVisible: false, form: { termId: '' }, formError: '', saving: false,
      confirmVisible: false, confirmTitle: '', confirmMessage: '', confirmKind: '', confirmError: '', pendingAction: null,
      actionBusy: false
    }
  },
  computed:{
    // 说明随归档批次的真实状态变化，不再固定写“先检查”
    archiveActionHint(){const status=this.current?.status;if(status==='READY')return '检查已通过，可以确认归档';if(status==='ARCHIVED')return '已归档，可查阅历史；如需更正请走纠错流程';if(status==='CANCELLED')return '已取消，仅可查看历史';return '先做完整性检查，处理完缺项后再确认归档'},
    identity(){const u=currentUserFromToken()||{};return JSON.stringify([u.tenantId,u.userId,u.activeContextId,u.currentRoleCode,u.permissionVersion,this.ctx.currentRole,this.ctx.dataScope,this.ctx.permissionVersion,this.ctx.permissionPatterns])},
    pageTitle(){return this.$route.query?.entry==='batch'?'批量归档':'归档与封存'},
    pageSubtitle(){return this.isCollegeScope?'查看学校归档进度，按本院实时预检处理本院缺项':!this.canManageArchive?'查阅学校归档进度；建立批次、处理缺项和正式封存由校教务负责':this.$route.query?.entry==='batch'?'复用正式学期归档批次；不另建旁路归档引擎':'十三个教务数据域先检查、处理缺失，再形成不可普通回退的学期归档'},
    isCollegeScope(){return this.current?.scopeType==='COLLEGE'||(this.ctx.dataScope?.scopeType||this.ctx.dataScope?.scope)==='COLLEGE'||this.rows.some(row=>row.scopeType==='COLLEGE')},
    archiveScopeNote(){return academicFlowText(this.current?.scopeNote,'学校封存材料由校教务统筹，本院缺项请查看本院实时预检。')},
    archiveOwner(){
      if(!this.current?.responsibility){
        if(this.current?.status==='ARCHIVED')return '学校已完成封存'
        if(this.current?.status==='CANCELLED')return '批次已取消'
      }
      return academicFlowOwner(this.current?.responsibility)
    },
    canManageArchive(){return !this.isCollegeScope&&matchPermission(this.ctx.permissionPatterns||[],'academicAffairs.archive.manage')},
    canConfirmArchive(){return this.canManageArchive&&this.current?.confirmAction?.allowed===true},
    confirmReason(){return this.confirmActionReason(this.current)},
    blockerText(){if(this.isCollegeScope)return '本院缺项请查看实时预检';const raw=this.current?.missingCount;if(raw==null||raw==='')return '阻断数量待核对';const count=Number(raw);if(!Number.isInteger(count)||count<0)return '阻断数量待核对';if(count>0)return `${count} 个数据域阻断`;if(this.current?.status==='ARCHIVED')return '无当前办理阻断';if(!this.items.length)return '尚未执行十三域检查';return '无阻断，可按状态继续'},
    nextRole(){
      if(!this.current?.nextStep){
        if(this.current?.status==='ARCHIVED')return '后续查阅或纠错由校教务统筹'
        if(this.current?.status==='CANCELLED')return '无需继续办理此批次'
      }
      return academicFlowNextOwner(this.current?.nextStep)
    }
  },
  watch:{identity(){this.clearPrivate();this.syncRoute()},'$route.fullPath'(){this.syncRoute()}},
  created(){this.syncRoute()},
  beforeUnmount(){this.alive=false;this.clearPrivate()},
 methods: {
    capture(){return {scope:this.scope,identity:this.identity,route:this.$route.fullPath}},isCurrent(c){return this.alive&&c.scope===this.scope&&c.identity===this.identity&&c.route===this.$route.fullPath},
    changeTerm(value) {
      if (this.actionBusy || this.pendingCommand) return
      const query = { ...this.$route.query }
      delete query.batchId
      if (value) query.termId = String(value)
      else delete query.termId
      return this.$router.push({ name: 'aa-archive', query })
    },
    routeTermId(){const value=this.$route.query?.termId;return typeof value==='string'&&/^[1-9][0-9]*$/.test(value)?value:''},
    invalidRouteTerm(){return this.$route.query?.termId!==undefined&&!this.routeTermId()},
    matchesRouteTerm(batch){const termId=this.routeTermId();return !termId||String(batch?.termId)===termId},
    denied(err){return /403|NO_DATA_SCOPE|NO_PERMISSION|FORBIDDEN/.test([err?.code,err?.bizCode].join(' '))},
    clearPrivate(){this.scope++;this.seq++;this.detailSeq++;this.rows=[];this.current=null;this.items=[];this.createVisible=false;this.confirmVisible=false;this.confirmKind='';this.confirmError='';this.pendingAction=null;this.pendingCommand=null;this.actionNotice='';this.form={termId:''};this.formError='';this.loading=false;this.saving=false;this.actionBusy=false},
    fail(err,fallback){if(this.denied(err))this.clearPrivate();return gradeError(err,fallback)},
    syncRoute(){
      if(!this.alive)return
      this.scope++;this.seq++;this.detailSeq++
      this.rows=[];this.current=null;this.items=[];this.confirmVisible=false;this.confirmKind='';this.confirmError='';this.pendingAction=null
      this.createVisible=false;this.formError='';this.listError='';this.loading=false;this.saving=false;this.actionBusy=false
      if(this.pendingCommand&&!this.pendingCommand.sent){this.pendingCommand=null;this.actionNotice=''}
      if(this.invalidRouteTerm()){this.listError='学期参数无效，请从正式学期入口重新进入归档批次。';return}
      this.load()
      const batchId=this.$route.params?.batchId??this.$route.query?.batchId
      if(batchId==null||batchId==='')return
      if(typeof batchId!=='string'||!/^\d+$/.test(batchId)){this.listError='归档批次参数无效，请返回原队列重新进入';return}
      this.selectAfterAction({batchId})
    },
    readPendingOriginal(){
      const {termId,batchId}=this.pendingCommand||{}
      if(!termId)return
      if(this.routeTermId()!==termId||String(this.$route.query.batchId||'')!==String(batchId||'')){
        const query={...this.$route.query,termId}
        if(batchId)query.batchId=batchId
        else delete query.batchId
        return this.$router.push({name:'aa-archive',query})
      }
      return batchId?this.selectAfterAction({batchId}):this.load()
    },
    sLabel(s) { return _SL[s] || '状态待确认' },
    batchMissingLabel(batch){return batch?.scopeType==='COLLEGE'?'学校材料由校教务统筹':batch?.missingCount==null?'阻断数量待核对':`阻断数据域 ${batch.missingCount}`},
    goCollegePrecheck(){if(!this.current?.termId)return;return this.$router.push({name:'aa-archive-precheck',query:{termId:String(this.current.termId)}})},
    sType(s) { return s === 'ARCHIVED' ? 'success' : s === 'MISSING_ITEMS' ? 'danger' : s === 'READY' ? 'primary' : 'default' },
   itemState(row) { const state=String(row?.result||'UNKNOWN').toUpperCase();return Object.hasOwn(_IL,state)?state:'UNKNOWN' },
    validItems(items){return Array.isArray(items)&&items.length===ARCHIVE_DOMAINS.length&&ARCHIVE_DOMAINS.every(domain=>items.some(item=>item.domain===domain))},
    itemLabel(row) { const state = this.itemState(row); return _IL[state] || '待确认' },
    itemType(row) { const state = this.itemState(row); return _IT[state] || 'warning' },
    fmt(s) { return s ? s.replace('T', ' ').slice(0, 16) : '' },
   async load() {
      const c=this.capture(),seq=++this.seq,termId=this.routeTermId();this.loading = true;this.listError=''
     try {
        if(this.invalidRouteTerm()){
          this.rows=[];this.current=null;this.items=[];this.confirmVisible=false;this.createVisible=false
          this.listError='学期参数无效，请从正式学期入口重新进入归档批次。';return
        }
        const res=await readAllPages((page,pageSize)=>api.listBatches({page,pageSize,...(termId?{termId}:{})}),{identity:row=>row.batchId,pageSize:100})
        if(!this.isCurrent(c)||seq!==this.seq)return
        if(res.code!==0)throw res
        if(termId&&res.data.list.some(row=>!this.matchesRouteTerm(row)))throw {code:'TERM_SCOPE_MISMATCH',message:'返回的归档批次与当前学期不一致，请刷新后核对。'}
        this.rows=res.data.list
        if(!this.current&&!this.$route.query?.batchId&&this.rows.length)await this.select(this.rows[0])
     } catch (e) {
        if(this.isCurrent(c)&&seq===this.seq)this.listError=this.fail(e,'归档批次加载失败')
     } finally {
        if(this.isCurrent(c)&&seq===this.seq)this.loading=false
     }
   },
   async select(b) {
      if(this.actionBusy||this.pendingCommand)return
      this.confirmVisible=false;this.confirmKind='';this.confirmError='';this.pendingAction=null
      const batchId=String(b.batchId),c=this.capture(),seq=++this.detailSeq
      try{const res=await api.getBatch(batchId);if(!this.isCurrent(c)||seq!==this.detailSeq)return;if(res.code!==0)throw res;if(String(res.data?.batchId)!==batchId||!Array.isArray(res.data?.items))throw {code:503};if(!this.matchesRouteTerm(res.data)){this.current=null;this.items=[];this.listError='所选归档批次不属于当前学期，请返回本学期列表。';return}this.current=res.data;this.items=res.data.items}
      catch(err){if(this.isCurrent(c)&&seq===this.detailSeq)toast.error(this.fail(err,'归档批次加载失败'))}
   },
    async refreshCurrentFromServer() {
      if (!this.current?.batchId || this.actionBusy) return
      const batchId = String(this.current.batchId),c=this.capture(),seq=++this.detailSeq
      try {
      const res = await api.getBatch(batchId)
      if(!this.isCurrent(c)||seq!==this.detailSeq)return
      if (res.code === 0&&String(res.data?.batchId)===batchId&&Array.isArray(res.data?.items)) {
        this.current = res.data
        this.items = res.data.items || []
        this.confirmError = ''
        await this.load()
      } else toast.error(this.fail(res,'归档批次刷新失败'))
      } catch (err) { if(this.isCurrent(c)&&seq===this.detailSeq)toast.error(this.fail(err,'归档批次刷新失败')) }
    },
   openCreate() { if (this.canManageArchive && !this.actionBusy && !this.pendingCommand && !this.invalidRouteTerm()) { this.form = { termId: this.routeTermId() }; this.formError = ''; this.createVisible = true } },
    async runBatchWrite(kind,batchId,validate,send,verify,success){
      if(!this.canManageArchive||this.pendingCommand)return false
      const c=this.capture(),id=String(batchId);this.actionBusy=true;this.pendingCommand={kind,batchId:id,termId:String(this.current?.termId||this.routeTermId()),sent:false};this.actionNotice='结果待核实，请勿重复操作。'
      let res, sent=false
      try {
        const before=await api.getBatch(id)
        if(!this.canManageArchive){this.pendingCommand=null;this.actionNotice='';this.confirmError='当前账号没有教务归档办理权限，请联系校教务处。';return false}
        if(!this.isCurrent(c))return false
        if(before?.code!==0||String(before.data?.batchId)!==id||!Array.isArray(before.data?.items))throw before
        this.pendingCommand.termId=String(before.data.termId)
        if(kind==='confirm'&&before.data.confirmAction?.allowed!==true){this.current=before.data;this.items=before.data.items;this.confirmError=this.confirmActionReason(before.data);this.pendingCommand=null;this.actionNotice='';return false}
        if(before.data.scopeType==='COLLEGE'||!validate(before.data)){this.pendingCommand=null;this.actionNotice='';throw {code:409}}
        sent=true;this.pendingCommand.sent=true
        try{res=await send(before.data)}catch(err){res=err}
        if(!this.isCurrent(c))return false
        if(res?.code!==0&&/403|404|409|422|NO_DATA_SCOPE|NO_PERMISSION|FORBIDDEN|CONFLICT|VALIDATION/.test([res?.code,res?.bizCode].join(' '))){this.pendingCommand=null;this.actionNotice='';throw res}
        const fresh=await api.getBatch(id)
        if(!this.isCurrent(c))return false
        if(fresh?.code!==0)throw fresh
        if(res?.code===0&&String(res.data?.batchId)===id&&fresh?.code===0&&String(fresh.data?.batchId)===id&&Array.isArray(fresh.data?.items)&&verify(fresh.data,res,before.data)){this.current=fresh.data;this.items=fresh.data.items;this.pendingCommand=null;this.actionNotice=success;return true}
        this.actionNotice='结果待核实：已读取当前归档批次，但不能确认本次操作完成，请勿重复操作。';return false
      }catch(err){if(this.isCurrent(c)){if(!sent){this.pendingCommand=null;this.actionNotice='';if(kind==='confirm'&&this.current)this.current={...this.current,confirmAction:null}}const message=this.fail(err,sent?'操作结果待核实，请勿重复操作。':'操作前核对未完成，请重试。');if(kind==='confirm')this.confirmError=message;toast.error(message)}return false}finally{if(this.isCurrent(c))this.actionBusy=false}
    },
   async submitCreate() {
     if(!this.canManageArchive)return
     if (!this.form.termId) { this.formError = '请选择学期'; return }
     if(this.invalidRouteTerm()||(this.routeTermId()&&String(this.form.termId)!==this.routeTermId())){this.formError='当前归档学期与页面学期不一致，请返回本学期重新选择。';return}
      if(this.saving||this.pendingCommand)return
      const termId=String(this.form.termId),c=this.capture();this.saving=true;this.pendingCommand={kind:'create',termId,sent:true};this.actionNotice='创建结果待核实，请勿重复创建。'
      try{let res;try{res=await api.createBatch({termId})}catch(err){res=err}if(!this.isCurrent(c))return;if(res?.code!==0&&/403|409|422|NO_DATA_SCOPE|NO_PERMISSION|FORBIDDEN|CONFLICT|VALIDATION/.test([res?.code,res?.bizCode].join(' '))){this.pendingCommand=null;this.actionNotice='';throw res}const id=String(res?.data?.batchId||'');if(res?.code===0&&id){const fresh=await api.getBatch(id);if(!this.isCurrent(c))return;if(fresh?.code!==0)throw fresh;if(fresh?.code===0&&String(fresh.data?.batchId)===id&&String(fresh.data?.termId)===termId&&Array.isArray(fresh.data?.items)){this.pendingCommand=null;this.actionNotice='已核对正式归档批次。';this.createVisible=false;this.current=fresh.data;this.items=fresh.data.items;await this.load();return}}this.formError='创建结果待核实，请勿重复创建。'
      }catch(e){if(this.isCurrent(c))this.formError=this.fail(e,'创建失败')}finally{if(this.isCurrent(c))this.saving=false}
   },
    async doCheck() {
      if (!this.canManageArchive || !this.current || this.actionBusy || this.pendingCommand) return
      const batchId=String(this.current.batchId)
      const ok=await this.runBatchWrite('check',batchId,before=>['DRAFT','MISSING_ITEMS','READY'].includes(before.status),()=>api.check(batchId),fresh=>this.validItems(fresh.items)&&['READY','MISSING_ITEMS'].includes(fresh.status),'已核对十三域完整性检查结果。')
      if(ok){toast.success(this.actionNotice);await this.load()}
    },
    confirmActionReason(batch){return academicFlowText(batch?.confirmAction?.reason,batch?.confirmAction?.allowed===false?'当前账号暂不可确认归档，请核对学校归档责任任职及办理权限。':'尚未取得当前账号的归档确认权限，请重新读取批次后核对。')},
    async doConfirm() {
      if (!this.canManageArchive || !this.current || this.actionBusy || this.pendingCommand || this.current.status !== 'READY') return
      if(!this.canConfirmArchive){this.confirmError=this.confirmReason;return}
      const batchId = String(this.current.batchId),c=this.capture(),seq=++this.detailSeq
      this.actionBusy=true;this.confirmError='';this.confirmVisible=false;this.pendingAction=null
      try {
      const response=await api.getBatch(batchId)
      if(!this.isCurrent(c)||seq!==this.detailSeq||String(this.current?.batchId)!==batchId)return
      if(response?.code!==0||String(response.data?.batchId)!==batchId||!Array.isArray(response.data?.items))throw response
      this.current=response.data;this.items=response.data.items
      if(!this.canConfirmArchive){this.confirmError=this.confirmReason;return}
      const batchName = this.current.batchName
      this.confirmKind = 'confirm'
      this.confirmTitle = '确认归档'
      this.confirmMessage = `确认归档「${batchName}」？归档后该学期将形成不可普通回退的历史记录，教务写操作受限。`
      this.pendingAction = async () => {
        if(!this.canManageArchive)return
        const ok=await this.runBatchWrite('confirm',batchId,before=>before.confirmAction?.allowed===true&&before.status==='READY'&&this.validItems(before.items)&&!before.items.some(item=>['BLOCKED','UNKNOWN'].includes(this.itemState(item))),()=>api.confirm(batchId, false),fresh=>fresh.status==='ARCHIVED'&&this.validItems(fresh.items),'已核对正式十三域归档状态。')
        if(ok){toast.success(this.actionNotice);this.confirmVisible=false;await this.load();const b=this.rows.find(row=>String(row.batchId)===String(batchId));if(b)await this.selectAfterAction(b)}
      }
      this.confirmVisible = true
      }catch(err){if(this.isCurrent(c)&&seq===this.detailSeq){if(this.current)this.current={...this.current,confirmAction:null};this.confirmError=this.fail(err,'归档确认权限读取失败，请重新读取批次后核对。')}}
      finally{if(this.isCurrent(c)&&seq===this.detailSeq)this.actionBusy=false}
    },
    doCancel() {
      if (!this.canManageArchive || !this.current || this.actionBusy || ['ARCHIVED', 'CANCELLED'].includes(this.current.status)) return
      const batchId = this.current.batchId
      const batchName = this.current.batchName
      this.confirmKind = 'cancel';this.confirmError=''
      this.confirmTitle = '取消批次'
      this.confirmMessage = `确认取消归档批次「${batchName}」？`
      this.pendingAction = async () => {
        if(!this.canManageArchive)return
        const ok=await this.runBatchWrite('cancel',batchId,before=>!['ARCHIVED','CANCELLED'].includes(before.status),()=>api.cancel(batchId),fresh=>fresh.status==='CANCELLED','已核对正式取消状态。')
        if(ok){toast.success(this.actionNotice);this.confirmVisible=false;await this.load();const b=this.rows.find(row=>String(row.batchId)===String(batchId));if(b)await this.selectAfterAction(b)}
      }
      this.confirmVisible = true
    },
    async onConfirm() {
      if (!this.canManageArchive || this.actionBusy || !this.pendingAction) return
      if (this.pendingCommand) return
      if(this.confirmKind==='confirm'&&!this.canConfirmArchive){this.confirmError=this.confirmReason;return}
      const action = this.pendingAction
      try {
        await action()
      } catch (e) {
        toast.error(this.fail(e,'操作失败'))
      }
    },
    async selectAfterAction(b) {
      const batchId=String(b?.batchId||''),c=this.capture(),seq=++this.detailSeq
      if(!batchId)return
      try {
        const res=await api.getBatch(batchId)
        if(!this.isCurrent(c)||seq!==this.detailSeq)return
        if(res?.code!==0)throw res
        if(String(res.data?.batchId)!==batchId||!Array.isArray(res.data?.items))throw {code:503}
        if(!this.matchesRouteTerm(res.data)){this.current=null;this.items=[];this.listError='所选归档批次不属于当前学期，请返回本学期列表。';return}
        this.current=res.data;this.items=res.data.items
      } catch(err) { if(this.isCurrent(c)&&seq===this.detailSeq)toast.error(this.fail(err,'归档结果复读失败')) }
    }
  }
}
</script>

<style scoped>
.aaar-context { display:flex;align-items:center;flex-wrap:wrap;gap:20px;margin-bottom:16px; }
.aaar-context .app-form-item { width:350px;max-width:100%;margin:0; }
.aaar-context > span { font-size:13px;color:var(--text-secondary,#64748b); }
.aaar-layout { display:grid;grid-template-columns:270px minmax(0,1fr);border:1px solid var(--border-color,#dbe3ee);border-radius:8px;background:var(--bg-card,#fff); }
.aaar-list,.aaar-detail { min-width:0; }
.aaar-list { border-right:1px solid var(--border-color,#dbe3ee); }
.aaar-list-head { display:flex;align-items:center;justify-content:space-between;gap:8px;padding:18px 14px; }
.aaar-list-head h2 { margin:0;font-size:16px; }
.aaar-list-head p,.aaar-list-head > span { margin:6px 0 0;color:var(--text-secondary,#64748b);font-size:12px;line-height:1.5; }
.aaar-items { list-style:none;margin:0;padding:0 10px 14px;display:grid;gap:8px;max-height:580px;overflow:auto; }
.aaar-item { display:flex;flex-direction:column;gap:12px;padding:14px 12px;border:1px solid var(--border-color,#dbe3ee);border-radius:6px;cursor:pointer;overflow-wrap:anywhere; }
.aaar-item.is-active { border-color:var(--primary-color,#285cba);background:var(--primary-bg,#eff6ff); }
.aaar-item:focus-visible { outline:2px solid var(--primary-color,#285cba);outline-offset:2px; }
.aaar-item__name { display:grid;gap:6px; }
.aaar-item__name strong { font-size:14px;line-height:1.6; }
.aaar-item__name small,.aaar-item__facts small { font-size:12px;color:var(--text-secondary,#64748b); }
.aaar-item__facts { display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px; }
.aaar-detail { padding:20px; }
.aaar-object-card { margin-bottom:16px; }
.aaar-title { font-size:20px;font-weight:650;line-height:1.5;overflow-wrap:anywhere; }
.aaar-object-main p { font-size:13px;color:var(--text-secondary,#64748b); }
.aaar-current-state { display:flex;gap:18px;align-items:center;flex-wrap:wrap;margin:10px 0; }
.aaar-current-state > span,.aaar-responsibility { font-size:13px;line-height:1.6;color:var(--text-secondary,#64748b); }
.aaar-responsibility summary { cursor:pointer; }
.aaar-responsibility p { margin:6px 0; }
.aaar-stage-rail { display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:14px;list-style:none;padding:16px 0;margin:0 0 14px;border-top:1px solid var(--border-color,#dbe3ee);border-bottom:1px solid var(--border-color,#dbe3ee); }
.aaar-stage-rail li { display:flex;align-items:flex-start;gap:8px; }
.aaar-stage-rail b { color:var(--text-secondary,#64748b);font-size:14px; }
.aaar-stage-rail span { display:grid;gap:4px; }
.aaar-stage-rail strong { font-size:13px; }
.aaar-stage-rail small { font-size:12px;color:var(--text-secondary,#64748b);line-height:1.5; }
.aaar-stage-rail .is-done b { color:var(--success-color,#23834f); }
.aaar-stage-rail .is-current strong,.aaar-stage-rail .is-current b { color:var(--primary-color,#285cba); }
.aaar-head { display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:14px;padding:16px 0 0;margin-top:16px;border-top:1px solid var(--border-color,#dbe3ee); }
.aaar-head > div:first-child { display:grid;gap:6px; }
.aaar-head small { font-size:13px;line-height:1.5;color:var(--text-secondary,#64748b); }
.aaar-actions { display:flex;flex-wrap:wrap;gap:8px; }
.aaar-summary,.aaar-counts { display:flex;flex-wrap:wrap;gap:12px 20px;font-size:13px;line-height:1.6;margin:12px 0; }
.aaar-summary .is-bad { color:var(--danger-color,#c53636); }
.aaar-section-title { display:flex;align-items:center;justify-content:space-between;gap:12px;margin:16px 0 8px; }
.aaar-detail :deep(.dt__scroll) { max-height:420px;overflow:auto; }
.aaar-detail :deep(.dt__th) { position:sticky;top:0;z-index:1;background:var(--fill-light,#f4f7fc); }
.aaar-detail :deep(.dt__td) { white-space:normal;overflow-wrap:anywhere; }
.aaar-form { display:flex;flex-direction:column;gap:12px; }
@media(max-width:1100px) { .aaar-layout { grid-template-columns:minmax(0,1fr); }.aaar-list { border-right:0;border-bottom:1px solid var(--border-color,#dbe3ee); }.aaar-items { grid-template-columns:repeat(auto-fit,minmax(220px,1fr));max-height:210px; }.aaar-stage-rail { grid-template-columns:repeat(auto-fit,minmax(120px,1fr)); } }
@media(max-width:600px) { .aaar-context { align-items:stretch;flex-direction:column; }.aaar-context .app-form-item { width:100%; }.aaar-detail { padding:12px; }.aaar-detail :deep(.dt__table) { min-width:560px; }.aaar-stage-rail { grid-template-columns:1fr 1fr; }.aaar-title { font-size:18px; } }
</style>
