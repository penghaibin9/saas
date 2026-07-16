<template>
  <ModulePageShell
    title="教务发布"
    subtitle="教务处终审：发布后原子回写成绩台账、刷新学生 GPA/学分/挂科数、触发预警扫描——超高危动作，二次确认"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="mp-stack">
      <div class="aa-tabs">
        <button class="aa-tab" :class="{ 'is-active': tab === 'ACADEMIC_REVIEW' }" @click="switchTab('ACADEMIC_REVIEW')">待终审</button>
        <button class="aa-tab" :class="{ 'is-active': tab === 'PUBLISHED' }" @click="switchTab('PUBLISHED')">已发布（可归档）</button>
      </div>

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" :title="tab === 'ACADEMIC_REVIEW' ? '暂无待终审任务' : '暂无已发布任务'" description="" />
      <DataTable v-else :columns="columns" :rows="rows" row-key="gradeTaskId" :pagination="pagination" @page-change="onPageChange">
        <template #cell-status="{ row }"><AppStatusTag :type="tab === 'PUBLISHED' ? 'success' : 'primary'" dot>{{ statusLabel(row.status) }}</AppStatusTag></template>
        <template #cell-actions="{ row }">
          <template v-if="tab === 'ACADEMIC_REVIEW'">
            <button class="mp-btn mp-btn--primary mp-btn--sm" @click="openPublish(row)">发布</button>
            <button class="mp-btn mp-btn--sm" @click="openReturn(row)">退回</button>
          </template>
          <button v-else class="mp-btn mp-btn--sm" @click="openArchive(row)">归档</button>
        </template>
      </DataTable>
    </div>

    <AppConfirmDialog
      v-model:visible="dlg.visible"
      :title="dlg.title"
      :type="dlg.type"
      :confirm-text="dlg.confirmText"
      :require-reason="dlg.requireReason"
      phrase-scene-key="aa.grade.return"
      reason-label="退回原因"
      :submitting="dlg.submitting"
      @confirm="doAction"
    >
      <p v-if="dlg.action === 'publish'">发布后即刻原子完成：回写成绩台账 + 刷新学生 GPA/学分/挂科数 + 触发预警扫描 + 不及格生成风险记录，不可撤销。</p>
    </AppConfirmDialog>
  </ModulePageShell>
</template>

<script>
/** 教务发布（/admin/academic-affairs/grade-publish）：终审发布/退回/归档。仅 ACADEMIC_ADMIN/SCHOOL_ADMIN 可执行。 */
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppStatusTag, AppConfirmDialog } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { toast } from '@/utils/toast'

export default {
  name: 'AaGradePublishView',
  components: { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppStatusTag, AppConfirmDialog },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      tab: 'ACADEMIC_REVIEW', loading: true, error: '', rows: [],
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
    statusLabel(s) { return s === 'ACADEMIC_REVIEW' ? '待教务终审' : (s === 'PUBLISHED' ? '已发布' : s) },
    switchTab(t) { this.tab = t; this.pagination.page = 1; this.load() },
    onPageChange(p) { this.pagination.page = p; this.load() },
    openPublish(row) {
      this.dlg = { visible: true, taskId: row.gradeTaskId, action: 'publish', title: `发布「${row.courseName}」成绩`, type: 'danger', confirmText: '确认发布（不可撤销）', requireReason: false, submitting: false }
    },
    openReturn(row) {
      this.dlg = { visible: true, taskId: row.gradeTaskId, action: 'return', title: `退回「${row.courseName}」`, type: 'warning', confirmText: '确认退回', requireReason: true, submitting: false }
    },
    openArchive(row) {
      this.dlg = { visible: true, taskId: row.gradeTaskId, action: 'archive', title: `归档「${row.courseName}」`, type: 'warning', confirmText: '确认归档', requireReason: false, submitting: false }
    },
    async doAction(payload) {
      const reason = (payload && payload.reason) || ''
      this.dlg.submitting = true
      let res
      if (this.dlg.action === 'publish') res = await academicAffairsApi.publishGrades(this.dlg.taskId)
      else if (this.dlg.action === 'return') res = await academicAffairsApi.returnGradeTask(this.dlg.taskId, reason)
      else res = await academicAffairsApi.archiveGradeTask(this.dlg.taskId)
      this.dlg.submitting = false
      if (res.code === 0) {
        this.dlg.visible = false
        if (this.dlg.action === 'publish') toast.success(`已发布，回写 ${res.data.projected} 条成绩，${res.data.failCount} 条触发预警`)
        else toast.success('已处理')
        this.load()
      } else toast.error(res.message || '操作失败')
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await academicAffairsApi.getGradeTasks({ status: this.tab, page: this.pagination.page, pageSize: this.pagination.pageSize })
      if (res.code === 0) { this.rows = res.data.list; this.pagination.total = res.data.total }
      else this.error = res.message
      this.loading = false
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-tabs { display: flex; gap: 4px; border-bottom: 1px solid var(--border-200, #e5e6eb); }
.aa-tab { padding: 8px 16px; border: none; background: none; cursor: pointer; font-size: 14px; color: var(--text-500, #646a73); border-bottom: 2px solid transparent; }
.aa-tab.is-active { color: var(--primary-600, #2563eb); border-bottom-color: var(--primary-500, #3b82f6); font-weight: 500; }
</style>
