<template>
  <ModulePageShell
    title="教学任务调整"
    subtitle="教务管理员更正教师/学时/周次/预计人数，理由必填并写入审计；已生成课表项的任务须先在排课模块处理"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="mp-stack">
      <AppInlineAlert
        type="info"
        description="与「任课教师分配」不同：本页面向已过初始分配阶段（含教师已确认/已就绪）仍需更正的场景；仅调整学时/周次/人数不影响确认状态，变更教师身份会退回「已分配」要求新教师重新确认。已合班并入其他教学班或已生成课表项的任务需先在「合班拆班」/排课模块处理。"
      />

      <div class="aa-filter">
        <label class="aa-filter__item">状态
          <AppSelect v-model="filterStatus" :options="statusOptions" :placeholder="''" @change="load" />
        </label>
        <button class="mp-btn" :disabled="loading" @click="load">刷新</button>
      </div>

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" title="暂无可调整的教学任务"
                 description="请先在「教学任务生成」按学期生成应开课程，或调整已合班/已排课的任务需先在对应模块处理" />
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
        <template #cell-hours="{ row }">
          周 {{ row.weeklyHours ?? '—' }} · 共 {{ row.totalHours ?? '—' }} 学时 · 第 {{ row.startWeek ?? '—' }}-{{ row.endWeek ?? '—' }} 周 · 计 {{ row.expectedStudents ?? '—' }} 人
        </template>
        <template #cell-status="{ row }">
          <AppStatusTag :type="taskColor(row.status)" dot>{{ statusLabel(row.status) }}</AppStatusTag>
        </template>
        <template #cell-actions="{ row }">
          <button class="mp-link" @click="openAdjust(row)">调整</button>
        </template>
      </DataTable>
    </div>

    <AppConfirmDialog
      v-model:visible="adjust.visible"
      title="调整教学任务"
      type="primary"
      confirm-text="确认调整"
      :submitting="adjust.submitting"
      @confirm="doAdjust"
    >
      <div class="aa-adjust-form">
        <label>教师姓名<input v-model.trim="adjust.teacherName" class="aa-input" placeholder="不变可留空" /></label>
        <label>教师工号/账号<input v-model.trim="adjust.teacherKey" class="aa-input" placeholder="不变可留空" /></label>
        <label>周学时<input v-model.number="adjust.weeklyHours" type="number" min="0" class="aa-input" /></label>
        <label>总学时<input v-model.number="adjust.totalHours" type="number" min="0" class="aa-input" /></label>
        <label>起始周<input v-model.number="adjust.startWeek" type="number" min="1" class="aa-input" /></label>
        <label>结束周<input v-model.number="adjust.endWeek" type="number" min="1" class="aa-input" /></label>
        <label>预计人数<input v-model.number="adjust.expectedStudents" type="number" min="0" class="aa-input" /></label>
      </div>
      <label class="aa-note-label">调整原因<i class="aa-req">*</i>（必填，至少 5 字，写入审计）
        <input v-model.trim="adjust.reason" class="aa-input" placeholder="如：原教师休产假换人代课" maxlength="500" />
      </label>
      <AppInlineAlert v-if="teacherChangedInDialog" type="warning"
                      description="教师姓名/工号有变更：确认后任务将退回「已分配」，需新教师重新确认。" />
    </AppConfirmDialog>
  </ModulePageShell>
</template>

<script>
/**
 * 教学任务调整（/admin/academic-affairs/teaching-tasks/adjust，续工新增）。
 * GET /academic-affairs/teaching-tasks（跨批次，排除 MERGED）+ POST /teaching-tasks/{taskId}/adjust。
 */
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppStatusTag, AppConfirmDialog, AppInlineAlert, AppSelect } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { TASK_STATUS, taskColor } from '@/modules/academicAffairs/constants/teaching'
import { toast } from '@/utils/toast'

export default {
  name: 'AaTaskAdjustView',
  components: { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppStatusTag, AppConfirmDialog, AppInlineAlert, AppSelect },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true, error: '', all: [], filterStatus: '',
      pagination: { page: 1, pageSize: 20, total: 0 },
      adjust: { visible: false, submitting: false, taskId: '', origTeacherName: '', origTeacherKey: '',
               teacherName: '', teacherKey: '', weeklyHours: null, totalHours: null,
               startWeek: null, endWeek: null, expectedStudents: null, reason: '' },
      columns: [
        { key: 'course', title: '课程 / 教学班' },
        { key: 'batch', title: '批次' },
        { key: 'teacher', title: '授课教师' },
        { key: 'hours', title: '学时 / 周次 / 人数' },
        { key: 'status', title: '状态' },
        { key: 'actions', title: '操作', width: '90px' }
      ]
    }
  },
  computed: {
    statusOptions() {
      return [
        { value: '', label: '全部（不含已并入合班）' },
        { value: 'PENDING_ASSIGN', label: '待分配' },
        { value: 'ASSIGNED', label: '已分配(待教师确认)' },
        { value: 'REJECTED_BY_TEACHER', label: '教师退回' },
        { value: 'TEACHER_CONFIRMED', label: '教师已确认' },
        { value: 'READY', label: '已就绪(可排课)' }
      ]
    },
    rows() {
      // MERGED 成员任务不可调整（须先拆班），列表侧直接排除，避免用户点进死路
      return this.all.filter((r) => r.status !== 'MERGED')
    },
    teacherChangedInDialog() {
      const a = this.adjust
      return (a.teacherName || '') !== (a.origTeacherName || '') || (a.teacherKey || '') !== (a.origTeacherKey || '')
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
      if (res.code === 0) { this.all = res.data.list; this.pagination.total = res.data.total }
      else { this.error = res.message }
      this.loading = false
    },
    openAdjust(row) {
      this.adjust = {
        visible: true, submitting: false, taskId: row.taskId,
        origTeacherName: row.teacherName || '', origTeacherKey: row.teacherKey || '',
        teacherName: row.teacherName || '', teacherKey: row.teacherKey || '',
        weeklyHours: row.weeklyHours, totalHours: row.totalHours,
        startWeek: row.startWeek, endWeek: row.endWeek, expectedStudents: row.expectedStudents,
        reason: ''
      }
    },
    async doAdjust() {
      if (!this.adjust.reason || this.adjust.reason.length < 5) { toast.error('调整原因必填且不少于 5 字'); return }
      this.adjust.submitting = true
      const res = await academicAffairsApi.adjustTask(this.adjust.taskId, {
        teacherName: this.adjust.teacherName || undefined,
        teacherKey: this.adjust.teacherKey || undefined,
        weeklyHours: this.adjust.weeklyHours ?? undefined,
        totalHours: this.adjust.totalHours ?? undefined,
        startWeek: this.adjust.startWeek ?? undefined,
        endWeek: this.adjust.endWeek ?? undefined,
        expectedStudents: this.adjust.expectedStudents ?? undefined,
        reason: this.adjust.reason
      })
      this.adjust.submitting = false
      if (res.code === 0) { this.adjust.visible = false; toast.success('已调整'); this.load() }
      else { toast.error(res.message || '调整失败') }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-filter { display: flex; gap: 16px; align-items: center; flex-wrap: wrap; }
.aa-select { height: 32px; padding: 0 10px; border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px; background: var(--bg-white, #fff); color: var(--text-900, #1f2329); font-size: 13px; min-width: 220px; }
.aa-adjust-form { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.aa-adjust-form label { display: flex; flex-direction: column; gap: 6px; font-size: 13px; color: var(--text-700, #4e5969); }
.aa-note-label { display: flex; flex-direction: column; gap: 6px; font-size: 13px; color: var(--text-700, #4e5969); margin-top: 10px; }
.aa-req { color: var(--danger-600, #d54941); margin-left: 2px; }
.aa-input { height: 34px; padding: 0 12px; border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px; background: var(--bg-white, #fff); color: var(--text-900, #1f2329); font-size: 14px; box-sizing: border-box; width: 100%; }
</style>
