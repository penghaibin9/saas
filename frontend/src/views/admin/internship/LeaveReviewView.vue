<template>
  <ModulePageShell title="打卡与请假" subtitle="学生实习期请假 · 指导教师审批 · 证明附件留痕"
    role-name="指导教师 / 管理员" :data-scope-name="scopeHint" :watermark="false">
    <template #actions>
      <AppExportButton :export-fn="exportFn" @exported="onExported">⬇ 导出 Excel 台账</AppExportButton>
    </template>

    <div class="bar">
      <AppSearchBox v-model="keyword" placeholder="按学生姓名搜索" @search="reload" />
      <AppQuickFilterChips v-model="statusFilter" :options="statusOptions" allow-clear @change="reload" />
    </div>

    <div v-if="error" class="state is-err">{{ error }} <button @click="load">重试</button></div>
    <DataTable v-else :columns="columns" :rows="rows" row-key="id" :loading="loading"
      :pagination="pagination" @page-change="onPageChange">
      <template #cell-range="{ row }">{{ row.startDate }} ~ {{ row.endDate }}</template>
      <template #cell-status="{ row }"><AppStatusTag :status="row.status" /></template>
      <template #cell-actions="{ row }">
        <div class="ops">
          <AppButton variant="ghost" size="sm" @click="openDetail(row)">详情</AppButton>
          <template v-if="row.status === 'PENDING'">
            <AppPermissionButton code="internship.leave.review" variant="secondary" size="sm" @click="openReview(row, 'APPROVE')">通过</AppPermissionButton>
            <AppPermissionButton code="internship.leave.review" variant="ghost" size="sm" :danger="true" @click="openReview(row, 'REJECT')">驳回</AppPermissionButton>
          </template>
        </div>
      </template>
    </DataTable>

    <div v-if="detailDlg.visible" class="modal" @click.self="detailDlg.visible = false">
      <div class="modal__card">
        <div class="modal__head">请假详情</div>
        <div class="modal__body">
          <div v-if="detailDlg.loading" class="state">加载中…</div>
          <template v-else-if="detailDlg.data">
            <AppDescriptionList :items="detailItems" :columns="2" />
            <template v-if="detailDlg.data.attachment">
              <div class="sec-t">证明附件</div>
              <AppFilePreview :files="attachmentFiles" @download="downloadAtt" />
            </template>
            <div class="sec-t">审批留痕</div>
            <AppAuditTrail :records="auditRecords" :show-ip="false" compact empty-text="暂无审批记录" />
          </template>
        </div>
        <div class="modal__foot"><AppButton variant="secondary" @click="detailDlg.visible = false">关闭</AppButton></div>
      </div>
    </div>

    <AppConfirmDialog v-model:visible="cd.visible" :title="cd.title" :content="cd.content"
      :danger="cd.danger" :confirm-text="cd.confirmText" :require-reason="cd.requireReason"
      reason-label="审批意见" :submitting="cd.submitting" @confirm="onConfirm" />
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, DataTable } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppStatusTag, AppConfirmDialog, AppExportButton, AppPermissionButton, AppDescriptionList,
  AppAuditTrail, AppSearchBox, AppQuickFilterChips, AppFilePreview } from '@/components/common'
import { leaveApi } from '@/modules/internship/api/leave-risk.api'
import { guidanceVisitApi } from '@/modules/internship/api/guidance-visit.api'
import { toast } from '@/utils/toast'

const COLUMNS = [
  { key: 'studentNo', title: '学号', width: '110px' }, { key: 'studentName', title: '姓名' },
  { key: 'advisorName', title: '指导教师' }, { key: 'leaveTypeLabel', title: '类型' },
  { key: 'range', title: '起止' }, { key: 'days', title: '天数', width: '70px' },
  { key: 'status', title: '状态' }, { key: 'actions', title: '操作', width: '180px' }
]
const STATUS_OPTIONS = [
  { label: '待审批', value: 'PENDING' }, { label: '已通过', value: 'APPROVED' },
  { label: '已驳回', value: 'REJECTED' }, { label: '已撤回', value: 'WITHDRAWN' }
]
const DETAIL = [
  { key: 'studentName', label: '学生' }, { key: 'advisorName', label: '指导教师' },
  { key: 'leaveTypeLabel', label: '类型' }, { key: 'startDate', label: '开始' },
  { key: 'endDate', label: '结束' }, { key: 'days', label: '天数' }, { key: 'reason', label: '事由' },
  { key: 'statusLabel', label: '状态' }, { key: 'reviewBy', label: '审批人' }, { key: 'reviewComment', label: '审批意见' }
]
const PANEL_PRESETS = {
  all: () => ({ statusFilter: '' }),
  pending: () => ({ statusFilter: 'PENDING' }),
  approved: () => ({ statusFilter: 'APPROVED' })
}

export default {
  name: 'LeaveReviewView',
  components: { ModulePageShell, DataTable, AppButton, AppStatusTag, AppConfirmDialog, AppExportButton,
    AppPermissionButton, AppDescriptionList, AppAuditTrail, AppSearchBox, AppQuickFilterChips, AppFilePreview },
  data() {
    return {
      rows: [], total: 0, page: 1, pageSize: 20, loading: false, error: '',
      keyword: '', statusFilter: '', columns: COLUMNS, statusOptions: STATUS_OPTIONS,
      detailDlg: { visible: false, loading: false, data: null },
      cd: { visible: false, title: '', content: '', danger: false, confirmText: '确认', requireReason: false, submitting: false },
      pending: null,
      scopeHint: '指导教师仅本人指导学生；管理员全校'
    }
  },
  computed: {
    pagination() { return { page: this.page, pageSize: this.pageSize, total: this.total } },
    detailItems() { const d = this.detailDlg.data || {}; return DETAIL.map((f) => ({ label: f.label, value: d[f.key] })) },
    attachmentFiles() { const a = this.detailDlg.data?.attachment; return a ? [{ id: a.fileId, name: a.fileName, sensitive: true }] : [] },
    auditRecords() {
      return (this.detailDlg.data?.auditTrail || []).map((t, i) => ({
        id: i, action: t.action, actor: t.operator, reason: t.detail && (t.detail.comment || ''), at: t.occurredAt
      }))
    }
  },
  watch: {
    '$route.query.panel': {
      immediate: true,
      handler(panel) {
        this.applyPanel((panel || 'pending').toString())
      }
    }
  },
  methods: {
    applyPanel(panel) {
      const preset = PANEL_PRESETS[panel] || PANEL_PRESETS.pending
      this.statusFilter = preset().statusFilter
      this.keyword = ''
      this.page = 1
      this.load()
    },
    exportFn() { return leaveApi.exportLeaves({ keyword: this.keyword, status: this.statusFilter }) },
    onExported(data) { toast.success(`已导出 ${data.rowCount} 条（水印 + 导出留痕）`) },
    reload() { this.page = 1; this.load() },
    onPageChange(p) { this.page = p; this.load() },
    async load() {
      this.loading = true; this.error = ''
      const params = { page: this.page, pageSize: this.pageSize, keyword: this.keyword }
      if (this.statusFilter) params.status = this.statusFilter
      const res = await leaveApi.getLeaves(params)
      this.loading = false
      if (res.code !== 0) { this.error = res.message || '加载失败'; this.rows = []; this.total = 0; return }
      this.rows = res.data.list; this.total = res.data.total
    },
    async openDetail(r) {
      this.detailDlg = { visible: true, loading: true, data: null }
      const res = await leaveApi.getLeaveDetail(r.id)
      this.detailDlg.loading = false
      if (res.code !== 0) { toast.error(res.message); this.detailDlg.visible = false; return }
      this.detailDlg.data = res.data
    },
    async downloadAtt() {
      const a = this.detailDlg.data?.attachment
      if (!a) return
      try { await guidanceVisitApi.downloadAttachment(a.fileId, a.fileName) } catch (e) { toast.error('下载失败：' + (e.message || '')) }
    },
    openReview(r, action) {
      this.pending = { id: r.id, action }
      const ap = action === 'APPROVE'
      this.cd = { visible: true, title: ap ? '请假 · 通过' : '请假 · 驳回',
        content: `${ap ? '通过' : '驳回'}「${r.studentName}」${r.startDate}~${r.endDate} 的请假，意见将写入审计。`,
        danger: !ap, confirmText: ap ? '通过' : '驳回', requireReason: !ap, submitting: false }
    },
    async onConfirm({ reason }) {
      this.cd.submitting = true
      const res = await leaveApi.review(this.pending.id, { action: this.pending.action, comment: reason || '' })
      this.cd.submitting = false
      if (res.code !== 0) return toast.error(res.message || '操作失败')
      this.cd.visible = false; toast.success('审批完成，已写审计'); this.load()
    }
  }
}
</script>

<style scoped>
.bar { display: flex; align-items: center; gap: var(--space-3); margin-bottom: var(--space-3); flex-wrap: wrap; }
.state { padding: var(--space-6); text-align: center; color: var(--text-tertiary); font-size: var(--font-size-sm); border: 1px dashed var(--border-base); border-radius: var(--radius-base); }
.state.is-err { color: var(--danger-600); }
.ops { display: flex; gap: var(--space-1); flex-wrap: wrap; }
.sec-t { font-size: var(--font-size-sm); font-weight: var(--font-weight-medium); color: var(--text-secondary); margin: var(--space-3) 0 var(--space-2); }
.modal { position: fixed; inset: 0; background: rgba(15, 23, 42, 0.45); display: flex; align-items: center; justify-content: center; z-index: var(--z-modal, 1000); padding: var(--space-4); }
.modal__card { background: var(--bg-card); border-radius: var(--radius-lg); width: min(520px, 100%); max-height: 88vh; display: flex; flex-direction: column; box-shadow: var(--shadow-lg); }
.modal__head { padding: var(--space-4); font-weight: var(--font-weight-semibold); border-bottom: 1px solid var(--border-light); }
.modal__body { padding: var(--space-4); overflow-y: auto; }
.modal__foot { padding: var(--space-3) var(--space-4); border-top: 1px solid var(--border-light); display: flex; justify-content: flex-end; gap: var(--space-2); }
</style>
