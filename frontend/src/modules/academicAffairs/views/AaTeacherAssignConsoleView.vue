<template>
  <ModulePageShell
    title="任课教师分配"
    subtitle="跨批次待分配 / 被教师退回的教学任务工作队列，行内直接分配授课教师"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="mp-stack">
      <div class="aa-filter">
        <label class="aa-filter__item">状态
          <AppSelect v-model="filterStatus" :options="statusOptions" placeholder="" class="aa-select" @change="load" />
        </label>
        <button class="mp-btn" :disabled="loading" @click="load">刷新</button>
      </div>

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" title="暂无待处理的教学任务"
                 description="请先在「教学任务生成」按学期生成应开课程" />
      <DataTable v-else :columns="columns" :rows="rows" row-key="taskId" :pagination="pagination" @page-change="onPageChange">
        <template #cell-course="{ row }">
          <div class="mp-cell-main">{{ row.courseName }}</div>
          <div class="mp-cell-sub">{{ row.teachingClassName || row.courseCode }}{{ row.isMerged ? ' · 合班' : '' }}</div>
        </template>
        <template #cell-batch="{ row }">批次 #{{ row.batchId }}</template>
        <template #cell-teacher="{ row }">
          <span v-if="row.teacherName">{{ row.teacherName }}</span>
          <span v-else class="mp-cell-sub">未分配</span>
        </template>
        <template #cell-hours="{ row }">周 {{ row.weeklyHours ?? '—' }} · 计 {{ row.expectedStudents ?? '—' }} 人</template>
        <template #cell-status="{ row }">
          <AppStatusTag :type="taskColor(row.status)" dot>{{ statusLabel(row.status) }}</AppStatusTag>
          <div v-if="row.rejectReason" class="mp-cell-sub is-danger">退回：{{ row.rejectReason }}</div>
        </template>
        <template #cell-actions="{ row }">
          <button class="mp-link" @click="openAssign(row)">{{ row.teacherName ? '改派' : '分配' }}</button>
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
        <label>教师姓名<input v-model.trim="assign.teacherName" class="aa-input" placeholder="必填" /></label>
        <label>教师工号/账号<input v-model.trim="assign.teacherKey" class="aa-input" placeholder="选填，用于教师本人在移动端确认" /></label>
        <label>周学时<input v-model.number="assign.weeklyHours" type="number" min="0" class="aa-input" /></label>
        <label>预计人数<input v-model.number="assign.expectedStudents" type="number" min="0" class="aa-input" /></label>
      </div>
    </AppConfirmDialog>
  </ModulePageShell>
</template>

<script>
/**
 * 任课教师分配（/admin/academic-affairs/teaching-tasks/assign）：跨批次工作队列。
 * GET /academic-affairs/teaching-tasks（跨批次）+ POST /teaching-tasks/{taskId}/assign。
 */
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppStatusTag, AppConfirmDialog, AppSelect } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { TASK_STATUS, taskColor } from '@/modules/academicAffairs/constants/teaching'
import { toast } from '@/utils/toast'

export default {
  name: 'AaTeacherAssignConsoleView',
  components: { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppStatusTag, AppConfirmDialog, AppSelect },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true, error: '', rows: [], filterStatus: '',
      statusOptions: [
        { value: '', label: '全部（默认按未完成分配优先）' },
        { value: 'PENDING_ASSIGN', label: '待分配' },
        { value: 'REJECTED_BY_TEACHER', label: '教师退回' },
        { value: 'ASSIGNED', label: '已分配（待教师确认）' },
        { value: 'TEACHER_CONFIRMED', label: '教师已确认' }
      ],
      pagination: { page: 1, pageSize: 20, total: 0 },
      assign: { visible: false, submitting: false, taskId: '', teacherName: '', teacherKey: '', weeklyHours: null, expectedStudents: null },
      columns: [
        { key: 'course', title: '课程 / 教学班' },
        { key: 'batch', title: '批次' },
        { key: 'teacher', title: '授课教师' },
        { key: 'hours', title: '学时 / 人数' },
        { key: 'status', title: '状态' },
        { key: 'actions', title: '操作', width: '110px' }
      ]
    }
  },
  created() { this.load() },
  methods: {
    taskColor,
    statusLabel(s) { return TASK_STATUS[s] || s || '' },
    onPageChange(p) { this.pagination.page = p; this.load() },
    async load() {
      this.loading = true
      this.error = ''
      const res = await academicAffairsApi.listAllTasks({
        status: this.filterStatus || undefined,
        page: this.pagination.page, pageSize: this.pagination.pageSize
      })
      if (res.code === 0) { this.rows = res.data.list; this.pagination.total = res.data.total }
      else { this.error = res.message }
      this.loading = false
    },
    openAssign(row) {
      this.assign = { visible: true, submitting: false, taskId: row.taskId, teacherName: row.teacherName || '',
                      teacherKey: row.teacherKey || '', weeklyHours: row.weeklyHours, expectedStudents: row.expectedStudents }
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
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-filter { display: flex; gap: 16px; align-items: center; flex-wrap: wrap; }
.aa-select { min-width: 220px; }
.aa-assign-form { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.aa-assign-form label { display: flex; flex-direction: column; gap: 6px; font-size: 13px; color: var(--text-700, #4e5969); }
.aa-input { height: 34px; padding: 0 12px; border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px; background: var(--bg-white, #fff); color: var(--text-900, #1f2329); font-size: 14px; box-sizing: border-box; }
.mp-cell-sub.is-danger { color: var(--danger-600, #d54941); }
</style>
