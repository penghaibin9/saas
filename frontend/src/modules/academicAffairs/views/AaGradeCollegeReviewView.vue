<template>
  <ModulePageShell
    title="学院审核"
    subtitle="审核本学院教学班已提交的成绩录入任务：完整性/合理性把关，通过进教务终审，退回教师重录"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="mp-stack">
      <div v-if="focusTaskId" class="aa-focus-note">已从教务待办精确定位成绩任务 {{ focusTaskId }}</div>
      <section v-if="receipt" class="aa-review-receipt" role="status">
        <div><strong>✓ 学院审核已完成</strong><span>{{ receipt.courseName }} · 任务 {{ receipt.taskId }}</span></div>
        <div><small>当前结果</small><b>{{ statusLabel(receipt.status) }}</b></div>
        <div><small>下一步</small><b>{{ receipt.next }}</b></div>
      </section>
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
      loading: true, error: '', rows: [], focusTaskId: '', receipt: null,
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
  created() {
    this.focusTaskId = String(this.$route?.query?.taskId || '')
    this.load()
  },
  methods: {
    statusLabel(s) { return s === 'SUBMITTED' ? '待学院审核' : s },
    onPageChange(p) { this.pagination.page = p; this.load() },
    openApprove(row) {
      this.dlg = { visible: true, taskId: row.gradeTaskId, courseName: row.courseName, action: 'APPROVE', title: `通过「${row.courseName}」`, type: 'primary', confirmText: '确认通过', requireReason: false, submitting: false }
    },
    openReturn(row) {
      this.dlg = { visible: true, taskId: row.gradeTaskId, courseName: row.courseName, action: 'RETURN', title: `退回「${row.courseName}」`, type: 'warning', confirmText: '确认退回', requireReason: true, submitting: false }
    },
    async doReview(payload) {
      const reason = (payload && payload.reason) || ''
      this.dlg.submitting = true
      const res = await academicAffairsApi.collegeReviewGrade(this.dlg.taskId, this.dlg.action, reason)
      this.dlg.submitting = false
      if (res.code === 0) {
        this.receipt = { taskId: this.dlg.taskId, courseName: this.dlg.courseName, status: res.data.status,
          next: this.dlg.action === 'APPROVE' ? '教务处终审发布' : '任课教师修改后重新提交' }
        this.dlg.visible = false; toast.success('已处理'); this.load()
      }
      else toast.error(res.message || '处理失败')
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await academicAffairsApi.getGradeTasks({
        status: 'SUBMITTED', taskId: this.focusTaskId || undefined,
        page: this.pagination.page, pageSize: this.pagination.pageSize
      })
      if (res.code === 0) { this.rows = res.data.list; this.pagination.total = res.data.total }
      else this.error = res.message
      this.loading = false
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-focus-note { padding: 9px 12px; border: 1px solid #bfdbfe; border-radius: 8px; background: #eff6ff; color: #1d4ed8; font-size: 12px; }
.aa-review-receipt { display: grid; grid-template-columns: minmax(0,1fr) auto auto; gap: 18px; padding: 12px 14px; border: 1px solid #a7d7b4; border-radius: 9px; background: #f3fbf5; }
.aa-review-receipt strong, .aa-review-receipt span, .aa-review-receipt small, .aa-review-receipt b { display: block; }.aa-review-receipt strong { color: #15803d; }.aa-review-receipt span, .aa-review-receipt small { margin-top: 3px; color: #64748b; font-size: 11px; }.aa-review-receipt b { margin-top: 3px; font-size: 12px; }
@media (max-width: 760px) { .aa-review-receipt { grid-template-columns: 1fr; gap: 10px; } }
</style>
