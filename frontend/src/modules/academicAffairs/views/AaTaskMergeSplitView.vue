<template>
  <ModulePageShell
    title="合班拆班"
    subtitle="先校验课程学期与名单，再调整"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
    show-subtitle-in-concise
  >
    <div class="mp-stack">
      <AaOperationReceipt :receipt="receipt" />
      <AppInlineAlert v-if="scopeReadOnlyReason" type="info" :description="scopeReadOnlyReason" />
      <AppInlineAlert v-if="actionError" type="warning" :description="actionError" />
      <AaTeachingTaskObjectBar
        v-if="primaryRow"
        :name="`${primaryRow.courseName || '课程'} · ${primaryRow.teachingClassName || '教学班'}`"
        :identity="`教学任务 #${primaryRow.taskId} · 批次 #${primaryRow.batchId}`"
        source="来源：正式教学任务与当前教学班名单；合班只调整授课组织，不覆盖历史课程和名单身份。"
        :status="statusLabel(primaryRow.status)"
        owner="学院教务 / 任课教师"
        next-owner="教师确认岗 → 学院教务核对岗 → 排课岗"
      />
      <AaTeachingTaskStageRail :current="2" current-note="当前合拆班工作区" />
      <AppSectionCard title="待合班任务（教师确认前，勾选同批次+同课程的 2 条及以上）">
        <ErrorState v-if="error" :description="error" @retry="load" />
        <LoadingState v-else-if="loading" />
        <EmptyState v-else-if="!candidates.length" title="暂无可合班的教学任务"
                   description="任务须在待分配/已分配（教师尚未确认）阶段才可合班" />
        <DataTable
          v-else :columns="candidateColumns" :rows="candidates" row-key="taskId"
          :selectable="canManageMerge && !merging && !actionLoading" :selected="selected" @update:selected="selected = $event"
        >
          <template #cell-course="{ row }">
            <div class="mp-cell-main">{{ row.courseName }}</div>
            <div class="mp-cell-sub">{{ row.teachingClassName }}</div>
          </template>
          <template #cell-batch="{ row }">批次 #{{ row.batchId }}</template>
          <template #cell-teacher="{ row }">{{ row.teacherName || '未分配' }}</template>
          <template #cell-students="{ row }">{{ row.expectedStudents ?? '—' }} 人</template>
          <template #cell-status="{ row }"><AppStatusTag :type="taskColor(row.status)" dot>{{ statusLabel(row.status) }}</AppStatusTag></template>
        </DataTable>
        <AppBatchActionBar
          :count="selected.length" :total="candidates.length"
          :actions="[{ key: 'merge', label: '核对合班条件', disabled: !eligibleSelection || !canManageMerge || actionLoading, disabledReason: mergeDisabledReason }]"
          :loading-key="merging || actionLoading ? 'merge' : ''"
          @action="openMerge" @clear="selected = []"
        />
      </AppSectionCard>

      <AppSectionCard v-if="!loading && !error" title="已合班教学任务（教师确认前可拆班还原）">
        <EmptyState v-if="!merged.length" title="暂无已合班的教学任务" />
        <DataTable v-else :columns="mergedColumns" :rows="merged" row-key="taskId">
          <template #cell-course="{ row }">
            <div class="mp-cell-main">{{ row.courseName }}</div>
            <div class="mp-cell-sub">{{ row.teachingClassName }}</div>
          </template>
          <template #cell-batch="{ row }">批次 #{{ row.batchId }}</template>
          <template #cell-students="{ row }">{{ row.expectedStudents ?? '—' }} 人</template>
          <template #cell-status="{ row }"><AppStatusTag :type="taskColor(row.status)" dot>{{ statusLabel(row.status) }}</AppStatusTag></template>
          <template #cell-actions="{ row }">
            <button v-if="canInspectSplit(row)" class="mp-link" :disabled="merging || actionLoading" @click="openSplit(row)">核对拆班条件</button>
            <span v-else class="mp-cell-sub">{{ canManageMerge ? '教师已确认，需先退回' : '当前只读' }}</span>
          </template>
        </DataTable>
      </AppSectionCard>
    </div>

    <AppConfirmDialog
      v-model:visible="mergeDialog.visible" title="确认合班" type="primary"
      confirm-text="确认合班" :submitting="merging" :confirm-disabled="!canMerge || actionLoading" @confirm="doMerge"
    >
      <AppInlineAlert v-if="actionError" type="warning" :description="actionError" />
      <p class="mp-note">将把选中的 {{ selected.length }} 条教学任务合并为一个教学班（人数相加），
        以最早一条为主任务；如需还原请在合班后使用「拆班」。</p>
      <ul><li v-for="row in selectedRows" :key="row.taskId">{{ row.courseName }} · {{ row.teachingClassName }} · 任务 #{{ row.taskId }} · 课程版本身份 #{{ row.courseId }}</li></ul>
      <p class="mp-note">提交前重新读取候选。正式名单与下游影响由服务端核对；当前没有独立合拆班影响预览接口。</p>
      <label class="aa-note-label">合班备注（选填）
        <input ref="noteInput" v-model.trim="mergeDialog.note" class="aa-input" placeholder="如：小班合并授课" maxlength="200" />
      </label>
      <AppQuickPhrases scene-key="aa.remark" @pick="onPickNote" />
    </AppConfirmDialog>
    <AppConfirmDialog :visible="Boolean(splitRow)" title="确认拆回原任务" confirm-text="确认拆班" :submitting="merging" :confirm-disabled="!canSplit(splitRow) || actionLoading" @update:visible="value => { if (!value) splitRow = null }" @confirm="doSplit(splitRow)">
      <AppInlineAlert v-if="actionError" type="warning" :description="actionError" />
      <p>{{ splitRow?.courseName }} · {{ splitRow?.teachingClassName }} · 任务 #{{ splitRow?.taskId }}</p>
      <p>按服务端保留的合班快照恢复；已确认任务和下游引用限制以服务端核对结果为准。</p>
    </AppConfirmDialog>
  </ModulePageShell>
</template>

<script>
/**
 * 合班拆班（/admin/academic-affairs/teaching-tasks/merge-split）。
 * GET /academic-affairs/teaching-tasks（mergeable=true 取候选，另拉全量算已合班）+
 * POST /teaching-tasks/merge + POST /teaching-tasks/{taskId}/split。
 */
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppSectionCard, AppStatusTag, AppConfirmDialog, AppBatchActionBar, AppQuickPhrases, AppInlineAlert } from '@/components/common'
import { insertAtCursor, applyInsertion } from '@/utils/insertAtCursor'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { teachingTaskWorkbenchApi } from '@/modules/academicAffairs/api/teaching-task-workbench.api'
import { TASK_STATUS, taskColor } from '@/modules/academicAffairs/constants/teaching'
import { matchPermission } from '@/config/navPlan'
import AaOperationReceipt from '../components/parallel-a/AaOperationReceipt.vue'
import AaTeachingTaskStageRail from '../components/teaching-tasks/AaTeachingTaskStageRail.vue'
import AaTeachingTaskObjectBar from '../components/teaching-tasks/AaTeachingTaskObjectBar.vue'
import { readTaskPages } from '../components/parallel-a/taskFacts'
import { isDeniedResult, isConflictResult } from '../components/parallel-a/resultState'

const PRE_CONFIRM = ['PENDING_ASSIGN', 'ASSIGNED']

export default {
  name: 'AaTaskMergeSplitView',
  components: { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppSectionCard, AppStatusTag, AppConfirmDialog, AppBatchActionBar, AppQuickPhrases, AppInlineAlert, AaOperationReceipt, AaTeachingTaskStageRail, AaTeachingTaskObjectBar },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true, error: '', all: [], selected: [], merging: false,
      revision: 0, receipt: null, splitRow: null, actionSeq: 0, operationSeq: 0, actionLoading: false, actionError: '', batchWorkbench: {},
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
    primaryRow() { return this.selectedRows[0] || this.candidates[0] || this.merged[0] || null },
    mutationContext() { return JSON.stringify([this.ctx.currentRole, this.ctx.dataScope, this.ctx.permissionPatterns, this.ctx.permissionVersion, this.ctx.dataScopeVersion]) },
    scopeReadOnlyReason() { return (this.ctx.dataScope?.scopeType || this.ctx.dataScope?.scope) === 'COLLEGE' ? '' : '当前为只读范围。合班和拆班由开课责任学院的当前有效办理人处理，学校负责统筹与终审。' },
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
    canMerge() { return this.canManageMerge && this.eligibleSelection && this.batchWorkbench.actions?.canEditComposition === true && String(this.batchWorkbench.batchId || '') === String(this.selectedRows[0]?.batchId || '') },
    mergeDisabledReason() {
      if (!this.canManageMerge) return this.scopeReadOnlyReason || '当前没有合拆班办理权限'
      if (this.actionLoading) return '正在核对批次办理条件'
      if (this.selectedRows.length < 2) return '至少选择 2 条教学任务'
      if (!this.eligibleSelection) return '仅可合并同批次、同课程的教学任务'
      return ''
    }
  },
  created() { this.load() },
  watch: {
    ctx: { deep: true, handler() { this.revision++; this.actionSeq++; this.operationSeq++; this.all = []; this.selected = []; this.receipt = null; this.batchWorkbench = {}; this.actionError = ''; this.actionLoading = false; this.merging = false; this.mergeDialog = { visible: false, note: '' }; this.splitRow = null; this.load() } },
    selectionKey() { this.actionSeq++; this.batchWorkbench = {}; this.actionLoading = false; this.mergeDialog.visible = false }
  },
  beforeUnmount() { this.revision++; this.actionSeq++; this.disposed = true },
  methods: {
    onPickNote(text) {
      const el = this.$refs.noteInput
      const { value, selStart, selEnd } = insertAtCursor(el, this.mergeDialog.note, text)
      this.mergeDialog.note = value
      this.$nextTick(() => applyInsertion(el, selStart, selEnd))
    },
    taskColor,
    statusLabel(s) { return TASK_STATUS[s] || (s ? '状态待确认' : '') },
    canInspectSplit(row) { return this.canManageMerge && Boolean(row?.isMerged) && PRE_CONFIRM.includes(row.status) },
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
        const res = await readTaskPages(page => academicAffairsApi.listAllTasks(page), valid)
        if (!valid()) return false
        if (res?.code !== 0) { this.handleFailure(res, '任务读取失败'); return false }
        this.all = res.data.list; return true
      } catch (error) { if (valid()) this.handleFailure(error, '网络连接失败，请重试。'); return false }
      finally { if (valid()) this.loading = false }
    },
    async openMerge(action) {
      if (action.key !== 'merge' || !this.canManageMerge || !this.eligibleSelection || this.actionLoading || this.merging) return
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
      try {
        if (!await this.load() || !valid()) return
        if (!this.eligibleSelection) { this.handleFailure({ code: 409001, message: '候选任务已变化，请核对后重新选择。' }); return }
        if (!await this.readCompositionActions(batchId) || !valid() || !this.canMerge) return
        const res = await academicAffairsApi.mergeTasks(ids, note || undefined)
        if (!valid()) return
        if (res.code !== 0) { this.handleFailure(res, '合班失败'); return }
        if (!await this.load() || !valid()) return
        const rows = ids.map(id => this.all.find(row => String(row.taskId) === String(id)))
        const survivor = rows.find(row => row?.isMerged)
        const confirmed = survivor && rows.every(row => row && (row === survivor || (row.status === 'MERGED' && String(row.mergedIntoId) === String(survivor.taskId))))
        this.receipt = { object: `任务 ${ids.join('、')}`, status: confirmed ? '已合班，正式任务已回读' : '结果待确认', pending: !confirmed, next: confirmed ? '核对合班教学班的正式名单及教师，再交教师本人确认。' : '请重新读取正式任务；不要重复合班。' }
        this.mergeDialog.visible = false
        if (confirmed) this.selected = []
      } catch (error) { if (valid()) this.handleFailure(error, '连接中断，请查询正式任务，勿重复合班。') }
      finally { if (!this.disposed && operation === this.operationSeq && context === this.mutationContext && ctx === this.ctx) this.merging = false }
    },
    async doSplit(row) {
      if (!this.canSplit(row) || this.merging) return
      this.merging = true
      const id = String(row.taskId), batchId = String(row.batchId), context = this.mutationContext, ctx = this.ctx, operation = ++this.operationSeq
      const valid = () => !this.disposed && operation === this.operationSeq && context === this.mutationContext && ctx === this.ctx && this.splitRow === row
      try {
        if (!await this.load() || !valid()) return
        if (!await this.readCompositionActions(batchId) || !valid()) return
        if (!this.canSplit(this.all.find(item => String(item.taskId) === String(id)))) { this.handleFailure({ code: 409001, message: '当前任务已不允许拆班。' }); return }
        const res = await academicAffairsApi.splitTask(id)
        if (!valid()) return
        if (res.code !== 0) { this.handleFailure(res, '拆班失败'); return }
        if (!await this.load() || !valid()) return
        const current = this.all.find(item => String(item.taskId) === String(id))
        const confirmed = current && !current.isMerged && !this.all.some(item => String(item.mergedIntoId) === String(id))
        this.receipt = { object: `任务 #${id}`, status: confirmed ? '已拆班，正式任务已回读' : '结果待确认', pending: !confirmed, next: '核对恢复的教学班及正式名单，再继续派师和确认。' }
        this.splitRow = null
      } catch (error) { if (valid()) this.handleFailure(error, '连接中断，请查询正式任务，勿重复拆班。') }
      finally { if (!this.disposed && operation === this.operationSeq && context === this.mutationContext && ctx === this.ctx) this.merging = false }
    },
    handleFailure(result, fallback) {
      this.error = result?.message || fallback
      if (isDeniedResult(result)) { this.revision++; this.loading = false; this.all = []; this.selected = []; this.receipt = null; this.mergeDialog = { visible: false, note: '' }; this.splitRow = null }
      else this.receipt = { title: '合拆班办理回执', status: isConflictResult(result) ? '事实已变化，保留输入' : '办理结果需核对', pending: true, next: '重新核对来源任务及正式名单后继续。' }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-note-label { display: flex; flex-direction: column; gap: 6px; font-size: 13px; color: var(--text-700, #4e5969); margin-top: 10px; }
.aa-input { height: 34px; padding: 0 12px; border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px; background: var(--bg-white, #fff); color: var(--text-900, #1f2329); font-size: 14px; box-sizing: border-box; width: 100%; }
</style>
