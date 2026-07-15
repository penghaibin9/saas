<template>
  <ModulePageShell
    title="教师任务确认"
    subtitle="我的教学任务：确认接受授课安排，或在有异议时退回学院重新分配"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="mp-stack">
      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" title="暂无分配给您的教学任务"
                 description="学院分配授课教师后，任务会出现在这里" />
      <DataTable v-else :columns="columns" :rows="rows" row-key="taskId">
        <template #cell-course="{ row }">
          <div class="mp-cell-main">{{ row.courseName }}</div>
          <div class="mp-cell-sub">{{ row.teachingClassName }}{{ row.isMerged ? ' · 合班' : '' }}</div>
        </template>
        <template #cell-batch="{ row }">批次 #{{ row.batchId }}</template>
        <template #cell-hours="{ row }">周 {{ row.weeklyHours ?? '—' }} 学时 · 第 {{ row.startWeek ?? '—' }}-{{ row.endWeek ?? '—' }} 周 · 计 {{ row.expectedStudents ?? '—' }} 人</template>
        <template #cell-status="{ row }">
          <AppStatusTag :type="taskColor(row.status)" dot>{{ statusLabel(row.status) }}</AppStatusTag>
          <div v-if="row.rejectReason" class="mp-cell-sub is-danger">此前退回原因：{{ row.rejectReason }}</div>
        </template>
        <template #cell-actions="{ row }">
          <template v-if="row.status === 'ASSIGNED'">
            <button class="mp-link" :disabled="acting === row.taskId" @click="doConfirm(row)">确认接受</button>
            <button class="mp-link is-danger" :disabled="acting === row.taskId" @click="openReject(row)">提出异议</button>
          </template>
          <span v-else class="mp-cell-sub">—</span>
        </template>
      </DataTable>
    </div>

    <AppConfirmDialog
      v-model:visible="rejectDialog.visible" title="提出异议（退回学院重新分配）" type="danger"
      confirm-text="确认退回" :submitting="acting === rejectDialog.taskId" @confirm="doReject"
    >
      <label class="aa-note-label">退回原因（必填，≥5 字）
        <textarea v-model.trim="rejectDialog.reason" class="aa-textarea" rows="3" placeholder="如：与本人其他课表时间冲突" />
      </label>
    </AppConfirmDialog>
  </ModulePageShell>
</template>

<script>
/**
 * 教师任务确认（/admin/academic-affairs/teaching-tasks/teacher-confirm）：本人授课任务确认/异议。
 * GET /academic-affairs/teaching-tasks?mine=true（后端按 teacherKey 命中本人身份收敛）+
 * POST /teaching-tasks/{taskId}/teacher-act。
 */
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppStatusTag, AppConfirmDialog } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { TASK_STATUS, taskColor } from '@/modules/academicAffairs/constants/teaching'
import { toast } from '@/utils/toast'

export default {
  name: 'AaTeacherTaskConfirmView',
  components: { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppStatusTag, AppConfirmDialog },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true, error: '', rows: [], acting: '',
      rejectDialog: { visible: false, taskId: '', reason: '' },
      columns: [
        { key: 'course', title: '课程 / 教学班' }, { key: 'batch', title: '批次' },
        { key: 'hours', title: '学时 / 周次 / 人数' }, { key: 'status', title: '状态' },
        { key: 'actions', title: '操作', width: '160px' }
      ]
    }
  },
  created() { this.load() },
  methods: {
    taskColor,
    statusLabel(s) { return TASK_STATUS[s] || s || '' },
    async load() {
      this.loading = true
      this.error = ''
      const res = await academicAffairsApi.listAllTasks({ mine: true, page: 1, pageSize: 100 })
      if (res.code === 0) { this.rows = res.data.list }
      else { this.error = res.message }
      this.loading = false
    },
    async doConfirm(row) {
      this.acting = row.taskId
      const res = await academicAffairsApi.teacherActTask(row.taskId, 'CONFIRM', '')
      this.acting = ''
      if (res.code === 0) { toast.success('已确认接受本次授课安排'); this.load() }
      else { toast.error(res.message || '确认失败') }
    },
    openReject(row) { this.rejectDialog = { visible: true, taskId: row.taskId, reason: '' } },
    async doReject() {
      if (!this.rejectDialog.reason || this.rejectDialog.reason.length < 5) { toast.error('退回原因必填且不少于 5 字'); return }
      this.acting = this.rejectDialog.taskId
      const res = await academicAffairsApi.teacherActTask(this.rejectDialog.taskId, 'REJECT', this.rejectDialog.reason)
      this.acting = ''
      if (res.code === 0) { this.rejectDialog.visible = false; toast.success('已退回学院重新分配'); this.load() }
      else { toast.error(res.message || '退回失败') }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-note-label { display: flex; flex-direction: column; gap: 6px; font-size: 13px; color: var(--text-700, #4e5969); }
.aa-textarea { padding: 10px 12px; border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px; background: var(--bg-white, #fff); color: var(--text-900, #1f2329); font-size: 14px; box-sizing: border-box; width: 100%; resize: vertical; font-family: inherit; }
.mp-cell-sub.is-danger { color: var(--danger-600, #d54941); }
</style>
