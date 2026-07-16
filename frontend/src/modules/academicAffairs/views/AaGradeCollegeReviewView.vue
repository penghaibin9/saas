<template>
  <ModulePageShell
    title="学院审核"
    subtitle="审核本学院教学班已提交的成绩录入任务：完整性/合理性把关，通过进教务终审，退回教师重录"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="mp-stack">
      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" title="暂无待审核任务" description="任课教师提交成绩后会出现在这里" />
      <DataTable v-else :columns="columns" :rows="rows" row-key="gradeTaskId" :pagination="pagination" @page-change="onPageChange">
        <template #cell-status="{ row }"><AppStatusTag type="primary" dot>{{ statusLabel(row.status) }}</AppStatusTag></template>
        <template #cell-actions="{ row }">
          <button class="mp-btn mp-btn--primary mp-btn--sm" @click="openApprove(row)">通过</button>
          <button class="mp-btn mp-btn--sm" @click="openReturn(row)">退回</button>
        </template>
      </DataTable>
    </div>

    <AppConfirmDialog
      v-model:visible="dlg.visible"
      :title="dlg.title"
      :type="dlg.type"
      :confirm-text="dlg.confirmText"
      :require-reason="dlg.requireReason"
      phrase-scene-key="aa.grade.taskReview"
      reason-label="审核意见"
      :submitting="dlg.submitting"
      @confirm="doReview"
    />
  </ModulePageShell>
</template>

<script>
/** 学院审核（/admin/academic-affairs/grade-college-review）：GET /grade-tasks?status=SUBMITTED + POST /college-review。 */
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppStatusTag, AppConfirmDialog } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { toast } from '@/utils/toast'

export default {
  name: 'AaGradeCollegeReviewView',
  components: { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppStatusTag, AppConfirmDialog },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true, error: '', rows: [],
      pagination: { page: 1, pageSize: 20, total: 0 },
      dlg: { visible: false, title: '', type: 'primary', confirmText: '确认', requireReason: false, submitting: false, taskId: '', action: '' },
      columns: [
        { key: 'courseName', title: '课程' },
        { key: 'termCode', title: '学期' },
        { key: 'status', title: '状态' },
        { key: 'actions', title: '操作', width: '160px' }
      ]
    }
  },
  created() { this.load() },
  methods: {
    statusLabel(s) { return s === 'SUBMITTED' ? '待学院审核' : s },
    onPageChange(p) { this.pagination.page = p; this.load() },
    openApprove(row) {
      this.dlg = { visible: true, taskId: row.gradeTaskId, action: 'APPROVE', title: `通过「${row.courseName}」`, type: 'primary', confirmText: '确认通过', requireReason: false, submitting: false }
    },
    openReturn(row) {
      this.dlg = { visible: true, taskId: row.gradeTaskId, action: 'RETURN', title: `退回「${row.courseName}」`, type: 'warning', confirmText: '确认退回', requireReason: true, submitting: false }
    },
    async doReview(payload) {
      const reason = (payload && payload.reason) || ''
      this.dlg.submitting = true
      const res = await academicAffairsApi.collegeReviewGrade(this.dlg.taskId, this.dlg.action, reason)
      this.dlg.submitting = false
      if (res.code === 0) { this.dlg.visible = false; toast.success('已处理'); this.load() }
      else toast.error(res.message || '处理失败')
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await academicAffairsApi.getGradeTasks({ status: 'SUBMITTED', page: this.pagination.page, pageSize: this.pagination.pageSize })
      if (res.code === 0) { this.rows = res.data.list; this.pagination.total = res.data.total }
      else this.error = res.message
      this.loading = false
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
</style>
