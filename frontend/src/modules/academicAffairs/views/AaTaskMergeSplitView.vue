<template>
  <ModulePageShell
    title="合班拆班"
    subtitle="同批次、同课程的教学任务可合并为一个教学班授课；教师确认前可再拆回独立任务"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="mp-stack">
      <AppSectionCard title="待合班任务（教师确认前，勾选同批次+同课程的 2 条及以上）">
        <ErrorState v-if="error" :description="error" @retry="load" />
        <LoadingState v-else-if="loading" />
        <EmptyState v-else-if="!candidates.length" title="暂无可合班的教学任务"
                   description="任务须在待分配/已分配（教师尚未确认）阶段才可合班" />
        <DataTable
          v-else :columns="candidateColumns" :rows="candidates" row-key="taskId"
          selectable :selected="selected" @update:selected="selected = $event"
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
          :actions="[{ key: 'merge', label: '合班', disabled: !canMerge, disabledReason: mergeDisabledReason }]"
          :loading-key="merging ? 'merge' : ''"
          @action="openMerge" @clear="selected = []"
        />
      </AppSectionCard>

      <AppSectionCard title="已合班教学任务（教师确认前可拆班还原）">
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
            <button v-if="canSplit(row)" class="mp-link" @click="doSplit(row)">拆班</button>
            <span v-else class="mp-cell-sub">教师已确认，需先退回</span>
          </template>
        </DataTable>
      </AppSectionCard>
    </div>

    <AppConfirmDialog
      v-model:visible="mergeDialog.visible" title="确认合班" type="primary"
      confirm-text="确认合班" :submitting="merging" @confirm="doMerge"
    >
      <p class="mp-note">将把选中的 {{ selected.length }} 条教学任务合并为一个教学班（人数相加），
        以最早一条为主任务；如需还原请在合班后使用「拆班」。</p>
      <label class="aa-note-label">合班备注（选填）
        <input v-model.trim="mergeDialog.note" class="aa-input" placeholder="如：小班合并授课" maxlength="200" />
      </label>
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
import { AppSectionCard, AppStatusTag, AppConfirmDialog, AppBatchActionBar } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { TASK_STATUS, taskColor } from '@/modules/academicAffairs/constants/teaching'
import { toast } from '@/utils/toast'

const PRE_CONFIRM = ['PENDING_ASSIGN', 'ASSIGNED']

export default {
  name: 'AaTaskMergeSplitView',
  components: { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppSectionCard, AppStatusTag, AppConfirmDialog, AppBatchActionBar },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true, error: '', all: [], selected: [], merging: false,
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
    canMerge() {
      if (this.selectedRows.length < 2) return false
      const first = this.selectedRows[0]
      return this.selectedRows.every((r) => r.batchId === first.batchId && r.courseId === first.courseId)
    },
    mergeDisabledReason() {
      if (this.selectedRows.length < 2) return '至少选择 2 条教学任务'
      if (!this.canMerge) return '仅可合并同批次、同课程的教学任务'
      return ''
    }
  },
  created() { this.load() },
  methods: {
    taskColor,
    statusLabel(s) { return TASK_STATUS[s] || s || '' },
    canSplit(row) { return PRE_CONFIRM.includes(row.status) },
    async load() {
      this.loading = true
      this.error = ''
      const res = await academicAffairsApi.listAllTasks({ page: 1, pageSize: 200 })
      if (res.code === 0) { this.all = res.data.list }
      else { this.error = res.message }
      this.loading = false
    },
    openMerge(action) {
      if (action.key !== 'merge' || !this.canMerge) return
      this.mergeDialog = { visible: true, note: '' }
    },
    async doMerge() {
      this.merging = true
      const res = await academicAffairsApi.mergeTasks(this.selected, this.mergeDialog.note || undefined)
      this.merging = false
      if (res.code === 0) {
        this.mergeDialog.visible = false
        this.selected = []
        toast.success('已合班')
        this.load()
      } else {
        toast.error(res.message || '合班失败')
      }
    },
    async doSplit(row) {
      const res = await academicAffairsApi.splitTask(row.taskId)
      if (res.code === 0) { toast.success('已拆班'); this.load() }
      else { toast.error(res.message || '拆班失败') }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-note-label { display: flex; flex-direction: column; gap: 6px; font-size: 13px; color: var(--text-700, #4e5969); margin-top: 10px; }
.aa-input { height: 34px; padding: 0 12px; border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px; background: var(--bg-white, #fff); color: var(--text-900, #1f2329); font-size: 14px; box-sizing: border-box; width: 100%; }
</style>
