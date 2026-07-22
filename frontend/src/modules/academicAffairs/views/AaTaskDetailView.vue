<template>
  <ModulePageShell
    title="教学任务明细"
    subtitle="为每门任务分配授课教师 → 教师确认 → 全部分配后提交批次审核"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton @click="$router.push('/admin/academic-affairs/teaching-tasks')">返回批次</AppButton>
      <AppButton variant="primary" :loading="submitting" @click="submitBatch">提交批次审核</AppButton>
    </template>

    <div class="mp-stack">
      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" title="本批次暂无教学任务" description="返回批次列表重新生成，或确认方案已绑定年级" />
      <DataTable v-else :columns="columns" :rows="rows" row-key="taskId" :pagination="pagination" @page-change="onPageChange">
        <template #cell-course="{ row }">
          <div class="mp-cell-main">{{ row.courseName }}</div>
          <div class="mp-cell-sub">{{ row.teachingClassName || row.courseCode }}{{ row.isMerged ? ' · 合班' : '' }}</div>
        </template>
        <template #cell-teacher="{ row }">
          <span v-if="row.teacherName">{{ row.teacherName }}</span>
          <span v-else class="mp-cell-sub">未分配</span>
        </template>
        <template #cell-hours="{ row }">周 {{ row.weeklyHours ?? '—' }} · 计 {{ row.expectedStudents ?? '—' }} 人</template>
        <template #cell-status="{ row }">
          <AppStatusTag :type="taskColor(row.status)" dot>{{ statusLabel(row.status) }}</AppStatusTag>
        </template>
        <template #cell-actions="{ row }">
          <button class="mp-link" @click="openAssign(row)">分配</button>
          <button v-if="row.status === 'ASSIGNED'" class="mp-link" @click="teacherAct(row, 'CONFIRM')">教师确认</button>
        </template>
      </DataTable>
    </div>

    <AppConfirmDialog
      v-model:visible="assign.visible"
      title="分配授课教师"
      type="primary"
      confirm-text="确认分配"
      :submitting="assign.submitting"
      @confirm="doAssign"
    >
      <div class="aa-assign-form">
        <label>任课教师<AppTeacherPicker v-model="assign.teacherKey" placeholder="选择任课教师" @change="onTeacherPicked" /></label>
        <label>周学时<input v-model.number="assign.weeklyHours" type="number" min="0" class="aa-input" /></label>
        <label>预计人数<input v-model.number="assign.expectedStudents" type="number" min="0" class="aa-input" /></label>
      </div>
    </AppConfirmDialog>
  </ModulePageShell>
</template>

<script>
/** 教学任务明细（/admin/academic-affairs/teaching-tasks/:batchId）：分配教师 + 教师确认 + 提交批次。 */
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppStatusTag, AppConfirmDialog, AppTeacherPicker } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { TASK_STATUS, taskColor } from '@/modules/academicAffairs/constants/teaching'
import { toast } from '@/utils/toast'

export default {
  name: 'AaTaskDetailView',
  components: { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppButton, AppStatusTag, AppConfirmDialog, AppTeacherPicker },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true, error: '', rows: [], submitting: false,
      pagination: { page: 1, pageSize: 50, total: 0 },
      assign: { visible: false, submitting: false, taskId: '', teacherName: '', teacherKey: '', weeklyHours: null, expectedStudents: null },
      columns: [
        { key: 'course', title: '课程 / 教学班' },
        { key: 'teacher', title: '授课教师' },
        { key: 'hours', title: '学时 / 人数' },
        { key: 'status', title: '状态' },
        { key: 'actions', title: '操作', width: '150px' }
      ]
    }
  },
  computed: {
    batchId() { return this.$route.params.batchId }
  },
  created() { this.load() },
  methods: {
    onTeacherPicked(value, items) {
      this.assign.teacherKey = value || ''
      this.assign.teacherName = items?.[0]?.raw?.teacherName || items?.[0]?.label || ''
    },
    taskColor,
    statusLabel(s) { return TASK_STATUS[s] || s || '' },
    onPageChange(p) { this.pagination.page = p; this.load() },
    openAssign(row) {
      this.assign = { visible: true, submitting: false, taskId: row.taskId, teacherName: row.teacherName || '', teacherKey: '', weeklyHours: row.weeklyHours, expectedStudents: row.expectedStudents }
    },
    async doAssign() {
      if (!this.assign.teacherName) { toast.error('请填写教师姓名'); return }
      this.assign.submitting = true
      const res = await academicAffairsApi.assignTeacher(this.assign.taskId, {
        teacherName: this.assign.teacherName,
        teacherKey: this.assign.teacherKey || undefined,
        weeklyHours: this.assign.weeklyHours || undefined,
        expectedStudents: this.assign.expectedStudents || undefined
      })
      this.assign.submitting = false
      if (res.code === 0) { this.assign.visible = false; toast.success('已分配'); this.load() }
      else { toast.error(res.message || '分配失败') }
    },
    async teacherAct(row, action) {
      const res = await academicAffairsApi.teacherActTask(row.taskId, action, '')
      if (res.code === 0) { toast.success('教师已确认'); this.load() }
      else { toast.error(res.message || '操作失败') }
    },
    async submitBatch() {
      if (this.submitting) return
      this.submitting = true
      const res = await academicAffairsApi.submitTaskBatch(this.batchId)
      this.submitting = false
      if (res.code === 0) { toast.success('批次已提交审核'); this.load() }
      else { toast.error(res.message || '提交失败（需全部任务已分配）') }
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await academicAffairsApi.getBatchTasks(this.batchId, { page: this.pagination.page, pageSize: this.pagination.pageSize })
      if (res.code === 0) { this.rows = res.data.list; this.pagination.total = res.data.total }
      else { this.error = res.message }
      this.loading = false
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-assign-form { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.aa-assign-form label { display: flex; flex-direction: column; gap: 6px; font-size: 13px; color: var(--text-700, #4e5969); }
.aa-input { height: 34px; padding: 0 12px; border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px; background: var(--bg-white, #fff); color: var(--text-900, #1f2329); font-size: 14px; box-sizing: border-box; }
</style>
