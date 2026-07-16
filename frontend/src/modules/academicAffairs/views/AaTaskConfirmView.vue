<template>
  <ModulePageShell
    title="教学任务确认"
    subtitle="学院核对确认（要求批内任务均已分配教师）→ 教务终审通过（进入排课资源池）或退回"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="mp-stack">
      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" title="暂无教学任务批次" description="请先在「教学任务生成」按学期生成" />
      <DataTable v-else :columns="columns" :rows="rows" row-key="batchId" :pagination="pagination" @page-change="onPageChange">
        <template #cell-status="{ row }"><AppStatusTag :type="taskBatchColor(row.status)" dot>{{ statusLabel(row.status) }}</AppStatusTag></template>
        <template #cell-actions="{ row }">
          <button v-if="row.status === 'DRAFT' || row.status === 'RETURNED'" class="mp-link"
                 :disabled="acting === row.batchId" @click="doCollegeConfirm(row)">学院核对确认</button>
          <template v-if="row.status === 'COLLEGE_CONFIRMED'">
            <button class="mp-link" :disabled="acting === row.batchId" @click="doReview(row, 'APPROVE')">教务终审通过</button>
            <button class="mp-link is-danger" :disabled="acting === row.batchId" @click="openReturn(row)">退回</button>
          </template>
          <button class="mp-link" @click="$router.push(`/admin/academic-affairs/teaching-tasks/${row.batchId}`)">查看明细</button>
        </template>
      </DataTable>
    </div>

    <AppConfirmDialog
      v-model:visible="returnDialog.visible" title="退回学院重新核对" type="danger"
      confirm-text="确认退回" :submitting="acting === returnDialog.batchId" @confirm="doReturn"
    >
      <label class="aa-note-label">退回原因（必填，≥5 字）
        <textarea ref="returnReasonInput" v-model.trim="returnDialog.reason" class="aa-textarea" rows="3" placeholder="如：教师工作量超限需重新安排" />
      </label>
      <AppQuickPhrases scene-key="aa.task.return" @pick="onPickReturnReason" />
    </AppConfirmDialog>
  </ModulePageShell>
</template>

<script>
/**
 * 教学任务确认（/admin/academic-affairs/teaching-tasks/confirm）：教务两级确认链。
 * POST .../college-confirm（学院核对确认）+ POST .../review（教务终审 APPROVE/RETURN）。
 * 与既有 /submit（单步直提）并存，本页只展示两级链路的操作入口。
 */
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppStatusTag, AppConfirmDialog, AppQuickPhrases } from '@/components/common'
import { insertAtCursor, applyInsertion } from '@/utils/insertAtCursor'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { TASK_BATCH_STATUS, taskBatchColor } from '@/modules/academicAffairs/constants/teaching'
import { toast } from '@/utils/toast'

export default {
  name: 'AaTaskConfirmView',
  components: { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppStatusTag, AppConfirmDialog, AppQuickPhrases },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true, error: '', rows: [], acting: '',
      pagination: { page: 1, pageSize: 20, total: 0 },
      returnDialog: { visible: false, batchId: '', reason: '' },
      columns: [
        { key: 'batchName', title: '批次名称' }, { key: 'termId', title: '学期 ID' },
        { key: 'status', title: '状态' }, { key: 'actions', title: '操作', width: '260px' }
      ]
    }
  },
  created() { this.load() },
  methods: {
    taskBatchColor,
    statusLabel(s) { return TASK_BATCH_STATUS[s] || s || '' },
    onPageChange(p) { this.pagination.page = p; this.load() },
    async load() {
      this.loading = true
      this.error = ''
      const res = await academicAffairsApi.getTaskBatches({ page: this.pagination.page, pageSize: this.pagination.pageSize })
      if (res.code === 0) { this.rows = res.data.list; this.pagination.total = res.data.total }
      else { this.error = res.message }
      this.loading = false
    },
    async doCollegeConfirm(row) {
      this.acting = row.batchId
      const res = await academicAffairsApi.collegeConfirmTaskBatch(row.batchId)
      this.acting = ''
      if (res.code === 0) { toast.success('已核对确认，待教务终审'); this.load() }
      else { toast.error(res.message || '确认失败（需批内任务均已分配教师）') }
    },
    async doReview(row, action) {
      this.acting = row.batchId
      const res = await academicAffairsApi.reviewTaskBatch(row.batchId, action, '')
      this.acting = ''
      if (res.code === 0) { toast.success('教务终审通过，任务进入排课资源池'); this.load() }
      else { toast.error(res.message || '操作失败') }
    },
    openReturn(row) { this.returnDialog = { visible: true, batchId: row.batchId, reason: '' } },
    onPickReturnReason(text) {
      const el = this.$refs.returnReasonInput
      const { value, selStart, selEnd } = insertAtCursor(el, this.returnDialog.reason, text)
      this.returnDialog.reason = value
      this.$nextTick(() => applyInsertion(el, selStart, selEnd))
    },
    async doReturn() {
      if (!this.returnDialog.reason || this.returnDialog.reason.length < 5) { toast.error('退回原因必填且不少于 5 字'); return }
      this.acting = this.returnDialog.batchId
      const res = await academicAffairsApi.reviewTaskBatch(this.returnDialog.batchId, 'RETURN', this.returnDialog.reason)
      this.acting = ''
      if (res.code === 0) { this.returnDialog.visible = false; toast.success('已退回学院'); this.load() }
      else { toast.error(res.message || '退回失败') }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-note-label { display: flex; flex-direction: column; gap: 6px; font-size: 13px; color: var(--text-700, #4e5969); }
.aa-textarea { padding: 10px 12px; border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px; background: var(--bg-white, #fff); color: var(--text-900, #1f2329); font-size: 14px; box-sizing: border-box; width: 100%; resize: vertical; font-family: inherit; }
</style>
