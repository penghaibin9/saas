<template>
  <ModulePageShell
    :title="pageTitle"
    :subtitle="pageSubtitle"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton variant="primary" :disabled="actionBusy || !!pendingCommand" @click="openCreate">新建归档批次</AppButton>
    </template>

    <AppInlineAlert v-if="actionNotice" :type="pendingCommand ? 'warning' : 'success'" :description="actionNotice" />
    <AppButton v-if="pendingCommand?.batchId" @click="readPendingOriginal">只读核对原归档批次 {{ pendingCommand.batchId }}</AppButton>
    <div class="aaar-layout">
      <section class="aaar-list">
        <header class="aaar-list-head"><div><h2>学期归档批次</h2><p>选择批次查看十三域正式结论</p></div><span>{{ rows.length }} 个批次</span></header>
        <LoadingState v-if="loading" />
        <ErrorState v-else-if="listError" :description="listError" @retry="load" />
        <EmptyState v-else-if="!rows.length" title="暂无归档批次" description="按学期新建归档批次" />
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
            <span class="aaar-item__name"><strong>{{ b.batchName }}</strong><small>#{{ b.batchId }} · {{ b.termCode || `学期 #${b.termId || '—'}` }}</small></span>
            <span class="aaar-item__facts"><small>阻断 {{ b.missingCount ?? '—' }}</small><StatusTag :type="sType(b.status)" :label="sLabel(b.status)" dot /></span>
          </li>
        </ul>
      </section>

      <div class="aaar-detail">
        <EmptyState v-if="!current" title="选择批次" description="从左侧选择归档批次执行完整性检查与归档" />
        <template v-else>
          <section class="aaar-object-card">
            <div class="aaar-object-main">
              <small>当前业务对象 · 学期归档批次 #{{ current.batchId }}</small>
              <div class="aaar-title">{{ current.batchName }}</div>
              <p>来源：学期正式事实与十三域聚合检查 · 为什么轮到我：当前岗位拥有教务归档查看或办理权限</p>
            </div>
            <dl>
              <div><dt>当前状态</dt><dd><StatusTag :type="sType(current.status)" :label="sLabel(current.status)" dot /></dd></div>
              <div><dt>当前责任</dt><dd>{{ archiveOwner }}</dd></div>
              <div><dt>当前阻断</dt><dd :class="{ 'is-bad': Number(current.missingCount) > 0 }">{{ blockerText }}</dd></div>
              <div><dt>下一责任岗位</dt><dd>{{ nextRole }}</dd></div>
            </dl>
          </section>
          <ol class="aaar-stage-rail" aria-label="归档办理阶段">
            <li class="is-done"><b>✓</b><span><strong>建立批次</strong><small>学期对象已锁定</small></span></li>
            <li :class="{ 'is-done': items.length === 13, 'is-current': !items.length }"><b>{{ items.length === 13 ? '✓' : '2' }}</b><span><strong>十三域检查</strong><small>{{ items.length === 13 ? '已读取正式结论' : '等待检查' }}</small></span></li>
            <li :class="{ 'is-done': current.status === 'READY' || current.status === 'ARCHIVED', 'is-current': current.status === 'MISSING_ITEMS' }"><b>{{ current.status === 'READY' || current.status === 'ARCHIVED' ? '✓' : '3' }}</b><span><strong>缺失处理</strong><small>{{ current.status === 'MISSING_ITEMS' ? '当前责任阶段' : '按结果解锁' }}</small></span></li>
            <li :class="{ 'is-done': current.status === 'ARCHIVED', 'is-current': current.status === 'READY' }"><b>{{ current.status === 'ARCHIVED' ? '✓' : '4' }}</b><span><strong>正式封存</strong><small>{{ current.status === 'READY' ? '等待确认' : '按状态解锁' }}</small></span></li>
            <li :class="{ 'is-done': current.status === 'ARCHIVED' }"><b>{{ current.status === 'ARCHIVED' ? '✓' : '5' }}</b><span><strong>受控纠错</strong><small>{{ current.status === 'ARCHIVED' ? '普通解冻关闭' : '封存后启用' }}</small></span></li>
          </ol>
          <div class="aaar-head">
            <div><strong>当前主动作</strong><small>先检查完整性；只有十三域无 BLOCKED / UNKNOWN 才可确认归档</small></div>
            <div class="aaar-actions">
              <AppButton v-if="['DRAFT','MISSING_ITEMS','READY'].includes(current.status)" size="small" variant="ghost" :disabled="!!pendingCommand" :loading="actionBusy" @click="doCheck">完整性检查</AppButton>
              <AppButton v-if="current.status === 'READY'" size="small" variant="primary" :disabled="actionBusy || !!pendingCommand" @click="doConfirm">确认归档</AppButton>
              <AppButton v-if="!['ARCHIVED','CANCELLED'].includes(current.status)" size="small" variant="ghost" :disabled="actionBusy || !!pendingCommand" @click="doCancel">取消</AppButton>
            </div>
          </div>
          <div v-if="current.missingCount != null" class="aaar-summary">
            <span :class="{ 'is-bad': current.missingCount }">阻断数据域 {{ current.missingCount }}</span>
            <span v-if="current.archivedAt">归档于 {{ fmt(current.archivedAt) }}（历史事实已封存）</span>
          </div>
          <AppInlineAlert
            v-if="current.status === 'MISSING_ITEMS'"
            type="warning"
            description="当前仍有已阻断或待治理的数据域，整体强制归档已停用。请处理阻断 / 待治理域后重新执行完整性检查。"
          />
          <AppInlineAlert
            v-if="current.status === 'ARCHIVED'"
            type="info"
            description="该学期已经形成正式归档事实，普通解冻入口已关闭。后续发现错误时必须走归档后纠错，保留原归档版本、纠错原因和新版本审计链。"
          />

          <AaArchiveCorrectionWorkspace
            v-if="current.status === 'ARCHIVED'"
            :batch="current"
            :items="items"
            @refresh-batch="refreshCurrentFromServer"
          />
          <template v-else>
            <div class="aaar-section-title">数据域完整性</div>
            <EmptyState v-if="!items.length" title="未检查" description="点击「完整性检查」聚合各数据域" />
            <DataTable v-else :columns="itemColumns" :rows="items" row-key="domain">
              <template #cell-domain="{ row }">{{ row.domainLabel }}</template>
              <template #cell-result="{ row }"><StatusTag :type="itemType(row)" :label="itemLabel(row)" dot /></template>
            </DataTable>
          </template>
        </template>
      </div>
    </div>

    <AppDrawer :visible="createVisible" title="新建归档批次" mode="modal" size="small" @close="createVisible = false">
      <div class="aaar-form">
        <AppFormItem label="学期" required><AppTermEntityPicker v-model="form.termId" placeholder="选择要归档的学期（一学期一批次）" :disabled="saving" /></AppFormItem>
        <AppInlineAlert type="warning" description="确认归档后该学期将成为不可普通回退的历史事实，教务写操作会被拦截；如后续发现错误，必须走归档后纠错并保留原版本。" />
        <AppInlineAlert v-if="formError" type="danger" :description="formError" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="saving" @click="createVisible = false">取消</AppButton>
        <AppButton variant="primary" :loading="saving" @click="submitCreate">创建</AppButton>
      </template>
    </AppDrawer>

    <AppConfirmDialog
      v-model:visible="confirmVisible"
      :title="confirmTitle"
      :message="confirmMessage"
      :submitting="actionBusy"
      @confirm="onConfirm"
    />
  </ModulePageShell>
</template>

<script>
/** 教务归档 · 控制台（/admin/academic-affairs/archive）：批次+数据域四态检查+不可逆归档封存。 */
import { ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton, AppDrawer } from '@/components/ui'
import { AppFormItem, AppConfirmDialog, AppInlineAlert, AppTermEntityPicker } from '@/components/common'
import { academicAffairsArchiveApi as api } from '@/modules/academicAffairs/api/academic-affairs.api'
import AaArchiveCorrectionWorkspace from '@/modules/academicAffairs/components/AaArchiveCorrectionWorkspace.vue'
import { toast } from '@/utils/toast'
import { currentUserFromToken } from '@/services/http/client'
import { gradeError } from './parallel-c/grade-review'
import { readAllPages } from '../components/parallel-a/pagedRead'

const _SL = { DRAFT: '草稿', CHECKING: '检查中', READY: '完整可归档', MISSING_ITEMS: '有阻断', ARCHIVED: '已归档', CANCELLED: '已取消' }
const _IL = { PASS: '通过', BLOCKED: '阻断', UNKNOWN: '待治理', NOT_APPLICABLE: '不适用' }
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
      itemColumns: [{ key: 'domain', title: '数据域' }, { key: 'recordCount', title: '记录数' }, { key: 'result', title: '归档状态' }, { key: 'remark', title: '备注' }],
      createVisible: false, form: { termId: '' }, formError: '', saving: false,
      confirmVisible: false, confirmTitle: '', confirmMessage: '', pendingAction: null,
      actionBusy: false
    }
  },
  computed:{
    identity(){const u=currentUserFromToken()||{};return JSON.stringify([u.tenantId,u.userId,u.activeContextId,u.currentRoleCode,this.ctx.currentRole,this.ctx.dataScope])},
    pageTitle(){return this.$route.query?.entry==='batch'?'批量归档':'归档与封存'},
    pageSubtitle(){return this.$route.query?.entry==='batch'?'复用正式学期归档批次；不另建旁路归档引擎':'十三个教务数据域先检查、处理缺失，再形成不可普通回退的学期归档事实'},
    archiveOwner(){return this.current?.status==='ARCHIVED'?'档案管理员 / 教务终审':this.current?.status==='READY'?'教务处归档岗':'各业务域责任岗位'},
    blockerText(){const count=Number(this.current?.missingCount||0);if(this.current?.status==='ARCHIVED')return '无当前办理阻断';if(count>0)return `${count} 个数据域阻断`;if(!this.items.length)return '尚未执行十三域检查';return '无阻断，可按状态继续'},
    nextRole(){if(this.current?.status==='ARCHIVED')return '受控纠错审批岗';if(this.current?.status==='READY')return '教务终审 / 归档确认岗';if(this.current?.status==='MISSING_ITEMS')return '命中缺失项的业务责任岗';return '教务归档检查岗'}
  },
  watch:{identity(){this.clearPrivate();this.syncRoute()},'$route.fullPath'(){this.syncRoute()}},
  created(){this.syncRoute()},
  beforeUnmount(){this.alive=false;this.clearPrivate()},
 methods: {
    capture(){return {scope:this.scope,identity:this.identity,route:this.$route.fullPath}},isCurrent(c){return this.alive&&c.scope===this.scope&&c.identity===this.identity&&c.route===this.$route.fullPath},
    denied(err){return /403|NO_DATA_SCOPE|NO_PERMISSION|FORBIDDEN/.test([err?.code,err?.bizCode].join(' '))},
    clearPrivate(){this.scope++;this.seq++;this.detailSeq++;this.rows=[];this.current=null;this.items=[];this.createVisible=false;this.confirmVisible=false;this.pendingAction=null;this.pendingCommand=null;this.actionNotice='';this.form={termId:''};this.formError='';this.loading=false;this.saving=false;this.actionBusy=false},
    fail(err,fallback){if(this.denied(err))this.clearPrivate();return gradeError(err,fallback)},
    syncRoute(){
      if(!this.alive)return
      this.scope++;this.seq++;this.detailSeq++
      this.rows=[];this.current=null;this.items=[];this.confirmVisible=false;this.pendingAction=null
      this.createVisible=false;this.formError='';this.listError='';this.loading=false;this.saving=false;this.actionBusy=false
      if(this.pendingCommand&&!this.pendingCommand.sent){this.pendingCommand=null;this.actionNotice=''}
      this.load()
      const batchId=this.$route.params?.batchId??this.$route.query?.batchId
      if(batchId==null||batchId==='')return
      if(typeof batchId!=='string'||!/^\d+$/.test(batchId)){this.listError='归档批次参数无效，请返回原队列重新进入';return}
      this.selectAfterAction({batchId})
    },
    readPendingOriginal(){
      const batchId=this.pendingCommand?.batchId
      if(!batchId)return
      if(String(this.$route.query.batchId)!==String(batchId))return this.$router.push({path:this.$route.path,query:{...this.$route.query,batchId:String(batchId)}})
      return this.selectAfterAction({batchId})
    },
    sLabel(s) { return _SL[s] || '状态待确认' },
    sType(s) { return s === 'ARCHIVED' ? 'success' : s === 'MISSING_ITEMS' ? 'danger' : s === 'READY' ? 'primary' : 'default' },
   itemState(row) { const state=String(row?.result||'UNKNOWN').toUpperCase();return Object.hasOwn(_IL,state)?state:'UNKNOWN' },
    validItems(items){return Array.isArray(items)&&items.length===ARCHIVE_DOMAINS.length&&ARCHIVE_DOMAINS.every(domain=>items.some(item=>item.domain===domain))},
    itemLabel(row) { const state = this.itemState(row); return _IL[state] || '待确认' },
    itemType(row) { const state = this.itemState(row); return _IT[state] || 'warning' },
    fmt(s) { return s ? s.replace('T', ' ').slice(0, 16) : '' },
   async load() {
      const c=this.capture(),seq=++this.seq;this.loading = true;this.listError=''
     try {
        const res=await readAllPages((page,pageSize)=>api.listBatches({page,pageSize}),{identity:row=>row.batchId,pageSize:100})
        if(!this.isCurrent(c)||seq!==this.seq)return
        if(res.code!==0)throw res
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
      this.confirmVisible=false;this.pendingAction=null
      const batchId=String(b.batchId),c=this.capture(),seq=++this.detailSeq
      try{const res=await api.getBatch(batchId);if(!this.isCurrent(c)||seq!==this.detailSeq)return;if(res.code!==0)throw res;if(String(res.data?.batchId)!==batchId||!Array.isArray(res.data?.items))throw {code:503};this.current=res.data;this.items=res.data.items}
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
        await this.load()
      } else toast.error(this.fail(res,'归档批次刷新失败'))
      } catch (err) { if(this.isCurrent(c)&&seq===this.detailSeq)toast.error(this.fail(err,'归档批次刷新失败')) }
    },
   openCreate() { if (!this.actionBusy) { this.form = { termId: '' }; this.formError = ''; this.createVisible = true } },
    async runBatchWrite(kind,batchId,validate,send,verify,success){
      if(this.pendingCommand)return false
      const c=this.capture(),id=String(batchId);this.actionBusy=true;this.pendingCommand={kind,batchId:id,sent:false};this.actionNotice='结果待核实，请勿重复操作。'
      let res, sent=false
      try {
        const before=await api.getBatch(id)
        if(!this.isCurrent(c))return false
        if(before?.code!==0||String(before.data?.batchId)!==id||!Array.isArray(before.data?.items))throw before
        if(!validate(before.data)){this.pendingCommand=null;this.actionNotice='';throw {code:409}}
        sent=true;this.pendingCommand.sent=true
        try{res=await send(before.data)}catch(err){res=err}
        if(!this.isCurrent(c))return false
        if(res?.code!==0&&/403|404|409|422|NO_DATA_SCOPE|NO_PERMISSION|FORBIDDEN|CONFLICT|VALIDATION/.test([res?.code,res?.bizCode].join(' '))){this.pendingCommand=null;this.actionNotice='';throw res}
        const fresh=await api.getBatch(id)
        if(!this.isCurrent(c))return false
        if(fresh?.code!==0)throw fresh
        if(res?.code===0&&String(res.data?.batchId)===id&&fresh?.code===0&&String(fresh.data?.batchId)===id&&Array.isArray(fresh.data?.items)&&verify(fresh.data,res,before.data)){this.current=fresh.data;this.items=fresh.data.items;this.pendingCommand=null;this.actionNotice=success;return true}
        this.actionNotice='结果待核实：已读取当前归档批次，但不能确认本次操作完成，请勿重复操作。';return false
      }catch(err){if(this.isCurrent(c)){if(!sent){this.pendingCommand=null;this.actionNotice=''}toast.error(this.fail(err,sent?'操作结果待核实，请勿重复操作。':'操作前核对未完成，请重试。'))}return false}finally{if(this.isCurrent(c))this.actionBusy=false}
    },
   async submitCreate() {
     if (!this.form.termId) { this.formError = '请选择学期'; return }
      if(this.saving||this.pendingCommand)return
      const termId=String(this.form.termId),c=this.capture();this.saving=true;this.pendingCommand={kind:'create',termId,sent:true};this.actionNotice='创建结果待核实，请勿重复创建。'
      try{let res;try{res=await api.createBatch({termId})}catch(err){res=err}if(!this.isCurrent(c))return;if(res?.code!==0&&/403|409|422|NO_DATA_SCOPE|NO_PERMISSION|FORBIDDEN|CONFLICT|VALIDATION/.test([res?.code,res?.bizCode].join(' '))){this.pendingCommand=null;this.actionNotice='';throw res}const id=String(res?.data?.batchId||'');if(res?.code===0&&id){const fresh=await api.getBatch(id);if(!this.isCurrent(c))return;if(fresh?.code!==0)throw fresh;if(fresh?.code===0&&String(fresh.data?.batchId)===id&&String(fresh.data?.termId)===termId&&Array.isArray(fresh.data?.items)){this.pendingCommand=null;this.actionNotice='已核对正式归档批次。';this.createVisible=false;this.current=fresh.data;this.items=fresh.data.items;await this.load();return}}this.formError='创建结果待核实，请勿重复创建。'
      }catch(e){if(this.isCurrent(c))this.formError=this.fail(e,'创建失败')}finally{if(this.isCurrent(c))this.saving=false}
   },
    async doCheck() {
      if (!this.current || this.actionBusy || this.pendingCommand) return
      const batchId=String(this.current.batchId)
      const ok=await this.runBatchWrite('check',batchId,before=>['DRAFT','MISSING_ITEMS','READY'].includes(before.status),()=>api.check(batchId),fresh=>this.validItems(fresh.items)&&['READY','MISSING_ITEMS'].includes(fresh.status),'已核对十三域完整性检查结果。')
      if(ok){toast.success(this.actionNotice);await this.load()}
    },
    doConfirm() {
      if (!this.current || this.actionBusy || this.current.status !== 'READY') return
      const batchId = this.current.batchId
      const batchName = this.current.batchName
      this.confirmTitle = '确认归档'
      this.confirmMessage = `确认归档「${batchName}」？归档后该学期将形成不可普通回退的历史事实，教务写操作受限。`
      this.pendingAction = async () => {
        const ok=await this.runBatchWrite('confirm',batchId,before=>before.status==='READY'&&this.validItems(before.items)&&!before.items.some(item=>['BLOCKED','UNKNOWN'].includes(this.itemState(item))),()=>api.confirm(batchId, false),fresh=>fresh.status==='ARCHIVED'&&this.validItems(fresh.items),'已核对正式十三域归档状态。')
        if(ok){toast.success(this.actionNotice);this.confirmVisible=false;await this.load();const b=this.rows.find(row=>String(row.batchId)===String(batchId));if(b)await this.selectAfterAction(b)}
      }
      this.confirmVisible = true
    },
    doCancel() {
      if (!this.current || this.actionBusy || ['ARCHIVED', 'CANCELLED'].includes(this.current.status)) return
      const batchId = this.current.batchId
      const batchName = this.current.batchName
      this.confirmTitle = '取消批次'
      this.confirmMessage = `确认取消归档批次「${batchName}」？`
      this.pendingAction = async () => {
        const ok=await this.runBatchWrite('cancel',batchId,before=>!['ARCHIVED','CANCELLED'].includes(before.status),()=>api.cancel(batchId),fresh=>fresh.status==='CANCELLED','已核对正式取消状态。')
        if(ok){toast.success(this.actionNotice);this.confirmVisible=false;await this.load();const b=this.rows.find(row=>String(row.batchId)===String(batchId));if(b)await this.selectAfterAction(b)}
      }
      this.confirmVisible = true
    },
    async onConfirm() {
      if (this.actionBusy || !this.pendingAction) return
      if (this.pendingCommand) return
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
        this.current=res.data;this.items=res.data.items
      } catch(err) { if(this.isCurrent(c)&&seq===this.detailSeq)toast.error(this.fail(err,'归档结果复读失败')) }
    }
  }
}
</script>

<style scoped>
.aaar-layout { display: grid; grid-template-columns: minmax(0, 1fr); gap: 16px; }
.aaar-list, .aaar-detail { min-width: 0; }
.aaar-list { order: 2; overflow: hidden; border: 1px solid var(--border-color, #e5e7eb); border-radius: 12px; background: var(--bg-card, #fff); }
.aaar-detail { order: 1; }
.aaar-list-head { display: flex; align-items: center; justify-content: space-between; gap: 14px; padding: 14px 18px; border-bottom: 1px solid var(--border-color, #e5e7eb); }
.aaar-list-head h2 { margin: 0; font-size: 16px; }
.aaar-list-head p, .aaar-list-head > span { margin: 4px 0 0; color: var(--text-secondary, #64748b); font-size: 12px; }
.aaar-items { list-style: none; margin: 0; padding: 0; display: grid; }
.aaar-item { display: grid; grid-template-columns: minmax(0, 1fr) auto; align-items: center; gap: 16px; padding: 13px 18px; border-bottom: 1px solid var(--border-color, #e5e7eb); cursor: pointer; }
.aaar-item:last-child { border-bottom: 0; }
.aaar-item.is-active { border-color: var(--primary-color, #2563eb); background: var(--primary-bg, #eff6ff); }
.aaar-item:focus-visible { outline: 2px solid var(--primary-color, #2563eb); outline-offset: 2px; }
.aaar-item__name, .aaar-item__facts { display: flex; min-width: 0; align-items: center; gap: 12px; }
.aaar-item__name { flex-wrap: wrap; }
.aaar-item__name strong { color: var(--primary-color, #2563eb); font-size: 13px; }
.aaar-item__name small, .aaar-item__facts small { color: var(--text-secondary, #64748b); font-size: 11px; }
.aaar-object-card { display: grid; grid-template-columns: minmax(0, 1.55fr) minmax(420px, 1fr); gap: 18px; padding: 16px 18px; margin-bottom: 14px; border: 1px solid var(--border-color, #e5e7eb); border-radius: 12px; background: var(--bg-card, #fff); }
.aaar-object-main > small { color: var(--text-secondary, #64748b); font-size: 11px; }
.aaar-title { margin: 5px 0 4px; overflow-wrap: anywhere; color: var(--text-primary, #172033); font-size: 18px; font-weight: 650; }
.aaar-object-main p { margin: 0; color: var(--text-secondary, #64748b); font-size: 12px; line-height: 1.6; }
.aaar-object-card dl { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; margin: 0; }
.aaar-object-card dl > div { min-width: 0; padding: 9px 11px; border-radius: 8px; background: var(--fill-light, #f6f8fb); }
.aaar-object-card dt { margin-bottom: 5px; color: var(--text-secondary, #64748b); font-size: 10px; }
.aaar-object-card dd { margin: 0; color: var(--text-primary, #172033); font-size: 12px; font-weight: 600; line-height: 1.4; }
.aaar-object-card dd.is-bad { color: var(--danger-color, #dc2626); }
.aaar-stage-rail { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); margin: 0 0 14px; padding: 14px 18px; border: 1px solid var(--border-color, #e5e7eb); border-radius: 12px; background: var(--bg-card, #fff); list-style: none; }
.aaar-stage-rail li { position: relative; display: flex; align-items: center; gap: 9px; min-width: 0; }
.aaar-stage-rail li:not(:last-child)::after { position: absolute; top: 14px; right: 9px; width: calc(100% - 42px); height: 1px; background: var(--border-color, #e5e7eb); content: ''; transform: translateX(100%); }
.aaar-stage-rail b { z-index: 1; display: grid; width: 28px; height: 28px; flex: 0 0 28px; place-items: center; border: 1px solid var(--border-color, #e5e7eb); border-radius: 50%; background: var(--bg-card, #fff); color: var(--text-secondary, #64748b); font-size: 11px; }
.aaar-stage-rail span { display: grid; gap: 2px; }
.aaar-stage-rail strong { color: var(--text-primary, #172033); font-size: 11px; }
.aaar-stage-rail small { color: var(--text-secondary, #64748b); font-size: 9px; }
.aaar-stage-rail .is-done b { border-color: #b7dfc5; background: #eef9f2; color: #23834f; }
.aaar-stage-rail .is-current b { border-color: var(--primary-color, #2563eb); background: var(--primary-color, #2563eb); color: #fff; }
.aaar-head { display: flex; justify-content: space-between; align-items: center; gap: 12px; padding: 12px 16px; margin-bottom: 12px; border: 1px solid #cdddf7; border-radius: 10px; background: #f1f6ff; }
.aaar-head > div:first-child { display: grid; gap: 3px; }
.aaar-head > div:first-child small { color: var(--text-secondary, #64748b); font-size: 11px; }
.aaar-actions { display: flex; gap: 8px; flex-wrap: wrap; }
.aaar-summary { display: flex; flex-wrap: wrap; gap: 8px 16px; padding: 10px 12px; background: var(--fill-light, #f8fafc); border-radius: 8px; margin-bottom: 12px; font-size: 13px; }
.aaar-summary .is-bad { color: var(--danger-color, #dc2626); font-weight: 600; }
.aaar-section-title { font-weight: 500; margin: 12px 0 8px; }
.aaar-form { display: flex; flex-direction: column; gap: 12px; }
@media (max-width: 900px) {
  .aaar-object-card { grid-template-columns: minmax(0, 1fr); }
  .aaar-list { max-height: 300px; overflow: auto; }
}
@media (max-width: 600px) {
  .aaar-head { flex-direction: column; }
  .aaar-actions { width: 100%; }
  .aaar-summary { flex-direction: column; gap: 6px; }
  .aaar-object-card dl { grid-template-columns: minmax(0, 1fr); }
  .aaar-stage-rail { grid-template-columns: minmax(0, 1fr); gap: 9px; }
  .aaar-stage-rail li::after { display: none; }
}
</style>
