<template>
  <ModulePageShell
    title="合班拆班"
    subtitle="先校验课程学期与名单，再调整"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
    show-subtitle-in-concise
  >
    <div class="mp-stack task-workspace">
      <AaOperationReceipt :receipt="receipt" />
      <AppButton v-if="pendingComposition" :disabled="merging || loading" @click="queryPendingComposition">查询原合拆班结果（不会重复提交）</AppButton>
      <AppInlineAlert v-if="scopeReadOnlyReason" type="info" :description="scopeReadOnlyReason" />
      <AppInlineAlert v-if="actionError" type="warning" :description="actionError" />
      <div class="task-workspace__filters"><label>学期<AppTermEntityPicker v-model="termId" clearable @change="search" /></label><label>课程或教学班<input v-model.trim="keyword" placeholder="输入课程或教学班" @keyup.enter="search" /></label><AppButton :disabled="merging" @click="search">查询</AppButton><AppButton v-if="$route.query.batchId" @click="$router.push({ path: `/admin/academic-affairs/teaching-tasks/${$route.query.batchId}`, query: { returnTo: $route.fullPath } })">返回批次</AppButton></div>
      <div class="task-workspace__tabs"><button :aria-pressed="panel === 'candidates'" :disabled="merging" @click="switchPanel('candidates')">待合班任务</button><button :aria-pressed="panel === 'merged'" :disabled="merging" @click="switchPanel('merged')">已合班任务</button></div>
      <div v-if="panel === 'candidates'" class="task-workspace__split">
      <section aria-label="待合班任务">
        <ErrorState v-if="error" :description="error" @retry="load" />
        <LoadingState v-else-if="loading" />
        <EmptyState v-else-if="!candidates.length" title="暂无可合班的教学任务"
                   description="任务须在待分配/已分配（教师尚未确认）阶段才可合班" />
        <DataTable
          v-else :columns="candidateColumns" :rows="candidates" row-key="taskId"
          :pagination="pagination" @page-change="changePage" :selectable="canManageMerge && !merging && !actionLoading && !pendingComposition" :selected="selected" @update:selected="selected = $event"
        >
          <template #cell-course="{ row }">
            <div class="mp-cell-main">{{ row.courseName }}</div>
            <div class="mp-cell-sub">{{ row.teachingClassName }}</div>
          </template>
          <template #cell-batch="{ row }">{{ row.termName || row.termCode || '—' }}</template>
          <template #cell-teacher="{ row }">{{ row.teacherName || '未分配' }}</template>
          <template #cell-students="{ row }">{{ row.expectedStudents ?? '—' }} 人</template>
          <template #cell-status="{ row }"><AppStatusTag :type="taskColor(row.status)" dot>{{ statusLabel(row.status) }}</AppStatusTag></template>
        </DataTable>
      </section>
      <aside class="task-workspace__panel"><h3>本次合班内容</h3><dl class="task-workspace__facts"><div><dt>选择任务</dt><dd>{{ selectedRows.length }}条</dd></div><div><dt>来源教学班</dt><dd>{{ selectedRows.map(row => row.teachingClassName || row.className || '班级待核对').join('、') || '请从左侧选择任务' }}</dd></div><div><dt>预计人数</dt><dd>{{ selectedRows.length && selectedRows.every(row => row.expectedStudents != null) ? selectedRows.reduce((sum, row) => sum + Number(row.expectedStudents), 0) + '人' : '待核对' }}</dd></div></dl><p class="task-workspace__notice">仅同批次、同课程且教师确认前的任务可合班。提交时重新核对最新状态和名单关系。</p><div class="task-workspace__actions"><AppButton variant="primary" :disabled="!eligibleSelection || !canManageMerge || merging || actionLoading || Boolean(pendingComposition)" @click="openMerge({ key: 'merge' })">核对合班条件</AppButton><AppButton :disabled="merging" @click="selected = []">清空选择</AppButton></div><p class="mp-cell-sub">{{ mergeDisabledReason }}</p></aside></div>

      <ErrorState v-if="panel === 'merged' && error" :description="error" @retry="load" />
      <LoadingState v-else-if="panel === 'merged' && loading" />
      <AppSectionCard v-else-if="panel === 'merged'" title="已合班教学任务（教师确认前可拆班还原）">
        <EmptyState v-if="!merged.length" title="暂无已合班的教学任务" />
        <DataTable v-else :columns="mergedColumns" :rows="merged" row-key="taskId" :pagination="pagination" @page-change="changePage">
          <template #cell-course="{ row }">
            <div class="mp-cell-main">{{ row.courseName }}</div>
            <div class="mp-cell-sub">{{ row.teachingClassName }}</div>
          </template>
          <template #cell-batch="{ row }">{{ row.termName || row.termCode || '—' }}</template>
          <template #cell-students="{ row }">{{ row.expectedStudents ?? '—' }} 人</template>
          <template #cell-status="{ row }"><AppStatusTag :type="taskColor(row.status)" dot>{{ statusLabel(row.status) }}</AppStatusTag></template>
          <template #cell-actions="{ row }">
            <button v-if="canInspectSplit(row)" class="mp-link" :disabled="merging || actionLoading" @click="openSplit(row)">核对拆班条件</button>
            <span v-else class="mp-cell-sub">{{ canManageMerge ? '教师已确认，需先退回' : '当前只读' }}</span>
          </template>
        </DataTable>
      </AppSectionCard>
      <p class="task-workspace__notice">拆班按原合班记录恢复任务，不是任意拆分学生；教师确认后不可直接办理。</p>
    </div>

    <AppConfirmDialog
      v-model:visible="mergeDialog.visible" title="确认合班" type="primary"
      confirm-text="确认合班" :submitting="merging" :confirm-disabled="!canMerge || actionLoading" @confirm="doMerge"
    >
      <AppInlineAlert v-if="actionError" type="warning" :description="actionError" />
      <p class="mp-note">将把选中的 {{ selected.length }} 条教学任务合并为一个教学班（人数相加），
        以最早一条为主任务；如需还原请在合班后使用「拆班」。</p>
      <ul><li v-for="row in selectedRows" :key="row.taskId">{{ row.courseName }} · {{ row.teachingClassName }}</li></ul>
      <p class="mp-note">提交前重新读取候选。正式名单与下游影响由系统核对；当前没有独立的合班拆班影响预览。</p>
      <label class="aa-note-label">合班备注（选填）
        <input ref="noteInput" v-model.trim="mergeDialog.note" class="aa-input" placeholder="如：小班合并授课" maxlength="200" />
      </label>
      <AppQuickPhrases scene-key="aa.remark" @pick="onPickNote" />
    </AppConfirmDialog>
    <AppConfirmDialog :visible="Boolean(splitRow)" title="确认拆回原任务" confirm-text="确认拆班" :submitting="merging" :confirm-disabled="!canSplit(splitRow) || actionLoading" @update:visible="value => { if (!value) splitRow = null }" @confirm="doSplit(splitRow)">
      <AppInlineAlert v-if="actionError" type="warning" :description="actionError" />
      <p>{{ splitRow?.courseName }} · {{ splitRow?.teachingClassName }}</p>
      <p>按系统保留的合班快照恢复；已确认任务和下游引用的限制以系统核对结果为准。</p>
    </AppConfirmDialog>
  </ModulePageShell>
</template>

<script>
/**
 * 合班拆班（/admin/academic-affairs/teaching-tasks/merge-split）。
 * GET /academic-affairs/teaching-tasks（mergeable=true 取候选，另拉全量算已合班）+
 * POST /teaching-tasks/merge + POST /teaching-tasks/{taskId}/split。
 */
import { AppButton } from '@/components/ui'
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppSectionCard, AppStatusTag, AppConfirmDialog, AppTermEntityPicker, AppQuickPhrases, AppInlineAlert } from '@/components/common'
import { insertAtCursor, applyInsertion } from '@/utils/insertAtCursor'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { teachingTaskWorkbenchApi } from '@/modules/academicAffairs/api/teaching-task-workbench.api'
import { TASK_STATUS, taskColor } from '@/modules/academicAffairs/constants/teaching'
import { matchPermission } from '@/config/navPlan'
import AaOperationReceipt from '../components/parallel-a/AaOperationReceipt.vue'
import { isDeniedResult, isConflictResult } from '../components/parallel-a/resultState'

const PRE_CONFIRM = ['PENDING_ASSIGN', 'ASSIGNED']

export default {
  name: 'AaTaskMergeSplitView',
  components: { AppButton, ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppSectionCard, AppStatusTag, AppConfirmDialog, AppTermEntityPicker, AppQuickPhrases, AppInlineAlert, AaOperationReceipt },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      panel: 'candidates', termId: '', keyword: '', pagination: { page: 1, pageSize: 20, total: 0 },
      loading: true, error: '', all: [], selected: [], merging: false,
      revision: 0, receipt: null, pendingComposition: null, splitRow: null, actionSeq: 0, operationSeq: 0, actionLoading: false, actionError: '', batchWorkbench: {},
      mergeDialog: { visible: false, note: '' },
      candidateColumns: [
        { key: 'course', title: '课程 / 教学班' }, { key: 'batch', title: '批次' },
        { key: 'teacher', title: '授课教师' }, { key: 'students', title: '预计人数' }, { key: 'status', title: '状态' }
      ],
      mergedColumns: [
        { key: 'course', title: '课程 / 合班教学班' }, { key: 'batch', title: '批次' },
        { key: 'students', title: '合班总人数' }, { key: 'status', title: '状态' }, { key: 'actions', title: '操作', width: '140px' }
      ]
    }
  },
  computed: {
    mutationContext() { return JSON.stringify([this.ctx.currentRole, this.ctx.dataScope, this.ctx.permissionPatterns, this.ctx.permissionVersion, this.ctx.dataScopeVersion]) },
    scopeReadOnlyReason() { return (this.ctx.dataScope?.scopeType || this.ctx.dataScope?.scope) === 'COLLEGE' ? '' : '学校仅查看，合班拆班由开课责任学院办理。' },
    canManageMerge() { return !this.scopeReadOnlyReason && matchPermission(this.ctx.permissionPatterns || [], 'academicAffairs.teachingTask.merge') },
    candidates() {
      return this.all.filter((r) => PRE_CONFIRM.includes(r.status) && !r.isMerged && !Number(r.mergedIntoId))
    },
    merged() {
      return this.all.filter((r) => r.isMerged)
    },
    selectedRows() {
      const set = new Set(this.selected)
      return this.candidates.filter((r) => set.has(r.taskId))
    },
    selectionKey() { return JSON.stringify(this.selected.map(String)) },
    eligibleSelection() {
      if (this.loading || this.selectedRows.length < 2 || this.selectedRows.length !== this.selected.length) return false
      const first = this.selectedRows[0]
      return Boolean(first.batchId && first.courseId) && this.selectedRows.every((r) => String(r.batchId) === String(first.batchId) && String(r.courseId) === String(first.courseId))
    },
    canMerge() { return !this.pendingComposition && this.canManageMerge && this.eligibleSelection && this.batchWorkbench.actions?.canEditComposition === true && String(this.batchWorkbench.batchId || '') === String(this.selectedRows[0]?.batchId || '') },
    mergeDisabledReason() {
      if (!this.canManageMerge) return this.scopeReadOnlyReason || '当前没有合拆班办理权限'
      if (this.actionLoading) return '正在核对批次办理条件'
      if (this.selectedRows.length < 2) return '至少选择 2 条教学任务'
      if (!this.eligibleSelection) return '仅可合并同批次、同课程的教学任务'
      return ''
    }
  },
  created() { this.restoreQuery(); this.load() },
  watch: {
    '$route.fullPath'() { this.selected = []; this.restoreQuery(); this.load() },
    ctx: { deep: true, handler() { this.revision++; this.actionSeq++; this.operationSeq++; this.all = []; this.selected = []; this.receipt = null; this.pendingComposition = null; this.batchWorkbench = {}; this.actionError = ''; this.actionLoading = false; this.merging = false; this.mergeDialog = { visible: false, note: '' }; this.splitRow = null; this.load() } },
    selectionKey() { this.actionSeq++; this.batchWorkbench = {}; this.actionLoading = false; this.mergeDialog.visible = false }
  },
  beforeUnmount() { this.revision++; this.actionSeq++; this.disposed = true },
  methods: {
    restoreQuery() { const q = this.$route.query; this.termId = String(q.termId || ''); this.keyword = String(q.keyword || ''); this.panel = q.panel === 'merged' ? 'merged' : 'candidates'; this.pagination.page = Math.max(1, Number(q.page) || 1) },
    search() { return this.changePage(1) },
    switchPanel(panel) { this.panel = panel; return this.changePage(1) },
    async changePage(page) { if (this.merging || this.actionLoading) return; this.selected = []; this.pagination.page = page; const before = this.$route.fullPath; await this.$router.replace({ path: this.$route.path, query: { ...this.$route.query, termId: this.termId || undefined, keyword: this.keyword || undefined, panel: this.panel, page: String(page) } }); if (before === this.$route.fullPath) await this.load() },
    async readExact(taskId) { const res = await academicAffairsApi.listAllTasks({ taskId, page: 1, pageSize: 1 }); if (res.code !== 0) throw res; return res.data?.list?.find(row => String(row.taskId) === String(taskId)) },
    onPickNote(text) {
      const el = this.$refs.noteInput
      const { value, selStart, selEnd } = insertAtCursor(el, this.mergeDialog.note, text)
      this.mergeDialog.note = value
      this.$nextTick(() => applyInsertion(el, selStart, selEnd))
    },
    taskColor,
    statusLabel(s) { return TASK_STATUS[s] || (s ? '状态待确认' : '') },
    canInspectSplit(row) { return !this.pendingComposition && this.canManageMerge && Boolean(row?.isMerged) && PRE_CONFIRM.includes(row.status) },
    canSplit(row) { return this.canInspectSplit(row) && this.batchWorkbench.actions?.canEditComposition === true && String(this.batchWorkbench.batchId || '') === String(row?.batchId || '') },
    async readCompositionActions(batchId) {
      const seq = ++this.actionSeq, context = this.mutationContext, ctx = this.ctx, selected = this.selectionKey
      const valid = () => !this.disposed && seq === this.actionSeq && context === this.mutationContext && ctx === this.ctx && selected === this.selectionKey
      this.batchWorkbench = {}; this.actionLoading = true; this.actionError = ''
      try {
        const res = await teachingTaskWorkbenchApi.getBatch(String(batchId))
        if (!valid()) return false
        if (res.code !== 0) throw res
        if (String(res.data?.batchId || '') !== String(batchId)) throw { message: '批次读取返回了不同对象，请重新核对。' }
        this.batchWorkbench = res.data
        if (!this.canManageMerge || res.data.actions?.canEditComposition !== true) { this.actionError = '本批次当前不允许合拆班，请由开课责任学院的有效办理人核对任职、权限及批次状态。'; return false }
        return true
      } catch (error) {
        if (valid()) { this.actionError = error?.message || '批次办理条件读取失败，请重试。'; if (isDeniedResult(error)) { this.all = []; this.selected = []; this.receipt = null; this.mergeDialog.visible = false; this.splitRow = null; this.actionLoading = false } }
        return false
      } finally { if (valid()) this.actionLoading = false }
    },
    async load() {
      const revision = ++this.revision, context = this.mutationContext, ctx = this.ctx
      const valid = () => !this.disposed && revision === this.revision && context === this.mutationContext && ctx === this.ctx
      this.loading = true
      this.error = ''
      this.all = []
      try {
        const res = await academicAffairsApi.listAllTasks({ batchId: this.$route.query.batchId || undefined, termId: this.termId || undefined, keyword: this.keyword || undefined, ...(this.panel === 'merged' ? { merged: true } : { mergeable: true }), page: this.pagination.page, pageSize: this.pagination.pageSize })
        if (!valid()) return false
        if (res?.code !== 0) { this.handleFailure(res, '任务读取失败'); return false }
        this.all = res.data.list; this.pagination.total = Number(res.data.total || 0); return true
      } catch (error) { if (valid()) this.handleFailure(error, '网络连接失败，请重试。'); return false }
      finally { if (valid()) this.loading = false }
    },
    async openMerge(action) {
      if (this.pendingComposition || action.key !== 'merge' || !this.canManageMerge || !this.eligibleSelection || this.actionLoading || this.merging) return
      if (await this.readCompositionActions(this.selectedRows[0].batchId) && this.canMerge) this.mergeDialog = { visible: true, note: '' }
    },
    async openSplit(row) {
      if (!this.canInspectSplit(row) || this.actionLoading || this.merging) return
      if (await this.readCompositionActions(row.batchId) && this.canSplit(row)) this.splitRow = row
    },
    async doMerge() {
      if (!this.canMerge || this.merging) return
      this.merging = true
      const ids = this.selected.map(String), note = this.mergeDialog.note, batchId = String(this.selectedRows[0].batchId), context = this.mutationContext, ctx = this.ctx, selected = this.selectionKey, operation = ++this.operationSeq
      const valid = () => !this.disposed && operation === this.operationSeq && context === this.mutationContext && ctx === this.ctx && selected === this.selectionKey
      let commandPhase = false
      try {
        if (!await this.load() || !valid()) return
        if (!this.eligibleSelection) { this.handleFailure({ code: 409001, message: '候选任务已变化，请核对后重新选择。' }); return }
        if (!await this.readCompositionActions(batchId) || !valid() || !this.canMerge) return
        this.pendingComposition = { action: 'merge', ids }
        commandPhase = true
        const res = await academicAffairsApi.mergeTasks(ids, note || undefined)
        commandPhase = false
        if (!valid()) return
        if (res.code !== 0) { if (isDeniedResult(res) || isConflictResult(res) || String(res.code).startsWith('400') || res.bizCode === 'VALIDATION_ERROR') this.pendingComposition = null; this.handleFailure(res, '合班失败'); return }
        if (!await this.load() || !valid()) return
        const rows = await Promise.all(ids.map(id => this.readExact(id)))
        if (!valid()) return
        const survivor = rows.find(row => row?.isMerged)
        const confirmed = survivor && rows.every(row => row && (row === survivor || (row.status === 'MERGED' && String(row.mergedIntoId) === String(survivor.taskId))))
        if (confirmed) this.pendingComposition = null
        this.receipt = { object: rows.map(row => row?.teachingClassName || row?.courseName).filter(Boolean).join('、') || `${ids.length} 个教学任务`, status: confirmed ? '已合班，已重新读取正式任务' : '结果待确认', pending: !confirmed, next: confirmed ? '核对合班教学班的正式名单及教师，再交教师本人确认。' : '请重新读取正式任务；不要重复合班。' }
        this.mergeDialog.visible = false
        if (confirmed) this.selected = []
      } catch (error) { if (valid()) { if (commandPhase && (isDeniedResult(error) || isConflictResult(error) || String(error?.code).startsWith('400') || error?.bizCode === 'VALIDATION_ERROR')) this.pendingComposition = null; this.handleFailure(error, '连接中断，请查询正式任务，勿重复合班。') } }
      finally { if (!this.disposed && operation === this.operationSeq && context === this.mutationContext && ctx === this.ctx) this.merging = false }
    },
    async doSplit(row) {
      if (!this.canSplit(row) || this.merging) return
      this.merging = true
      const id = String(row.taskId), batchId = String(row.batchId), context = this.mutationContext, ctx = this.ctx, operation = ++this.operationSeq
      const valid = () => !this.disposed && operation === this.operationSeq && context === this.mutationContext && ctx === this.ctx && this.splitRow === row
      let commandPhase = false
      try {
        if (!await this.load() || !valid()) return
        if (!await this.readCompositionActions(batchId) || !valid()) return
        if (!this.canSplit(this.all.find(item => String(item.taskId) === String(id)))) { this.handleFailure({ code: 409001, message: '当前任务已不允许拆班。' }); return }
        this.pendingComposition = { action: 'split', ids: [id] }
        commandPhase = true
        const res = await academicAffairsApi.splitTask(id)
        commandPhase = false
        if (!valid()) return
        if (res.code !== 0) { if (isDeniedResult(res) || isConflictResult(res) || String(res.code).startsWith('400') || res.bizCode === 'VALIDATION_ERROR') this.pendingComposition = null; this.handleFailure(res, '拆班失败'); return }
        if (!await this.load() || !valid()) return
        const current = await this.readExact(id)
        if (!valid()) return
        const confirmed = current && !current.isMerged
        if (confirmed) this.pendingComposition = null
        this.receipt = { object: [row.courseName, row.teachingClassName].filter(Boolean).join(' · ') || '教学任务', status: confirmed ? '已拆班，已重新读取正式任务' : '结果待确认', pending: !confirmed, next: '核对恢复的教学班及正式名单，再继续派师和确认。' }
        this.splitRow = null
      } catch (error) { if (valid()) { if (commandPhase && (isDeniedResult(error) || isConflictResult(error) || String(error?.code).startsWith('400') || error?.bizCode === 'VALIDATION_ERROR')) this.pendingComposition = null; this.handleFailure(error, '连接中断，请查询正式任务，勿重复拆班。') } }
      finally { if (!this.disposed && operation === this.operationSeq && context === this.mutationContext && ctx === this.ctx) this.merging = false }
    },
    async queryPendingComposition() {
      if (!this.pendingComposition || this.merging || this.loading) return
      const pending = this.pendingComposition, context = this.ctx
      this.merging = true
      try {
        const rows = await Promise.all(pending.ids.map(id => this.readExact(id)))
        if (this.disposed || context !== this.ctx || this.pendingComposition !== pending) return
        const survivor = rows.find(row => row?.isMerged)
        const confirmed = pending.action === 'merge' ? survivor && rows.every(row => row && (row === survivor || (row.status === 'MERGED' && String(row.mergedIntoId) === String(survivor.taskId)))) : rows[0] && !rows[0].isMerged
        this.receipt = { status: confirmed ? '已读取原合拆班正式结果' : '结果待确认', pending: !confirmed, next: confirmed ? '核对教学班名单，再继续分配和确认。' : '尚未读到一致的正式结果，请联系学院核对；不会重复提交。' }
        if (confirmed) { this.pendingComposition = null; this.selected = []; this.splitRow = null; this.mergeDialog.visible = false; await this.load() }
      } catch (error) { if (context === this.ctx) this.handleFailure(error, '原合拆班结果查询失败') }
      finally { if (context === this.ctx) this.merging = false }
    },
    handleFailure(result, fallback) {
      this.error = result?.message || fallback
      if (isDeniedResult(result)) { this.revision++; this.loading = false; this.all = []; this.selected = []; this.receipt = null; this.mergeDialog = { visible: false, note: '' }; this.splitRow = null }
      else this.receipt = { title: '合拆班办理回执', status: isConflictResult(result) ? '数据已变化，保留输入' : '办理结果需核对', pending: true, next: '重新核对来源任务及正式名单后继续。' }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
@import '../styles/teaching-task-workspace.css';
.aa-note-label { display: flex; flex-direction: column; gap: 6px; font-size: 13px; color: var(--text-700, #4e5969); margin-top: 10px; }
.aa-input { height: 34px; padding: 0 12px; border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px; background: var(--bg-white, #fff); color: var(--text-900, #1f2329); font-size: 14px; box-sizing: border-box; width: 100%; }
</style>
