<template>
  <ModulePageShell title="评价与成绩" subtitle="学生鉴定 · 学生自评 · 指导教师意见 · 学校审核"
    role-name="指导教师 / 管理员" :data-scope-name="scopeHint" :watermark="false">
    <template #actions>
      <AppButton variant="ghost" @click="$router.push('/admin/internship/enterprise-evals')">返回评价管理</AppButton>
      <AppExportButton :export-fn="exportFn" @exported="onExported">⬇ 导出 Excel 台账</AppExportButton>
    </template>

    <div class="bar">
      <AppSearchBox v-model="keyword" placeholder="按学生姓名搜索" @search="reload" />
      <AppQuickFilterChips v-model="statusFilter" :options="statusOptions" allow-clear @change="reload" />
      <span class="bar__hint">学生自评经移动端提交</span>
    </div>

    <div v-if="error" class="state is-err">{{ error }} <button @click="load">重试</button></div>
    <DataTable v-else :columns="columns" :rows="rows" row-key="id" :loading="loading"
      :pagination="pagination" @page-change="onPageChange">
      <template #cell-submitStatus="{ row }"><AppStatusTag :type="row.submitStatus === 'SUBMITTED' ? 'success' : 'default'">{{ row.submitStatusLabel }}</AppStatusTag></template>
      <template #cell-enterpriseRating="{ row }">{{ row.enterpriseRating ? row.enterpriseRating + ' 分' : '—' }}</template>
      <template #cell-positionRating="{ row }">{{ row.positionRating ? row.positionRating + ' 分' : '—' }}</template>
      <template #cell-advisor="{ row }">{{ row.hasAdvisorOpinion ? '已填' : '未填' }}</template>
      <template #cell-mentor="{ row }">{{ row.hasMentorOpinion ? '已填' : '未填' }}</template>
      <template #cell-reviewStatus="{ row }"><AppStatusTag :type="reviewTone(row.reviewStatus)">{{ row.reviewStatusLabel }}</AppStatusTag></template>
      <template #cell-actions="{ row }">
        <div class="ops">
          <AppButton variant="ghost" size="sm" @click="openDetail(row)">详情</AppButton>
          <AppPermissionButton v-if="row.submitStatus === 'SUBMITTED'" code="internship.studentEval.comment" variant="ghost" size="sm" @click="openComment(row)">填意见</AppPermissionButton>
          <template v-if="row.submitStatus === 'SUBMITTED' && row.reviewStatus === 'PENDING'">
            <AppPermissionButton code="internship.studentEval.review" variant="secondary" size="sm" @click="openReview(row, 'APPROVE')">通过</AppPermissionButton>
            <AppPermissionButton code="internship.studentEval.review" variant="ghost" size="sm" :danger="true" @click="openReview(row, 'RETURN')">退回</AppPermissionButton>
          </template>
        </div>
      </template>
    </DataTable>

    <!-- 填意见 -->
    <div v-if="cmtDlg.visible" class="modal" @click.self="cmtDlg.visible = false">
      <div class="modal__card">
        <div class="modal__head">指导教师意见</div>
        <div class="modal__body">
          <AppFormItem label="指导教师意见" required>
            <AppTextarea v-model="cmtForm.advisorOpinion" :rows="3" placeholder="对学生实习表现的鉴定意见" />
          </AppFormItem>
          <AppFormItem label="企业导师意见（可选，如实转录）">
            <AppTextarea v-model="cmtForm.mentorOpinion" :rows="3" placeholder="企业导师对学生的意见" />
          </AppFormItem>
        </div>
        <div class="modal__foot">
          <AppButton variant="ghost" @click="cmtDlg.visible = false">取消</AppButton>
          <AppButton variant="primary" :loading="cmtDlg.submitting" @click="submitComment">保存意见</AppButton>
        </div>
      </div>
    </div>

    <!-- 详情 -->
    <div v-if="detailDlg.visible" class="modal" @click.self="detailDlg.visible = false">
      <div class="modal__card">
        <div class="modal__head">学生鉴定详情</div>
        <div class="modal__body">
          <div v-if="detailDlg.loading" class="state">加载中…</div>
          <template v-else-if="detailDlg.data">
            <AppDescriptionList :items="detailItems" :columns="1" />
            <div class="sec-t">操作留痕</div>
            <AppAuditTrail :records="auditRecords" :show-ip="false" compact empty-text="暂无记录" />
          </template>
        </div>
        <div class="modal__foot"><AppButton variant="secondary" @click="detailDlg.visible = false">关闭</AppButton></div>
      </div>
    </div>

    <AppConfirmDialog v-model:visible="cd.visible" :title="cd.title" :content="cd.content"
      :danger="cd.danger" :confirm-text="cd.confirmText" :require-reason="cd.requireReason"
      reason-label="审核意见" :submitting="cd.submitting" @confirm="onConfirm" />
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, DataTable } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppStatusTag, AppConfirmDialog, AppExportButton, AppPermissionButton, AppDescriptionList,
  AppAuditTrail, AppSearchBox, AppQuickFilterChips, AppTextarea, AppFormItem } from '@/components/common'
import { studentEvalApi } from '@/modules/internship/api/student-eval.api'
import { toast } from '@/utils/toast'

const COLUMNS = [
  { key: 'studentNo', title: '学号', width: '110px' }, { key: 'studentName', title: '姓名' },
  { key: 'advisorName', title: '指导教师' }, { key: 'submitStatus', title: '自评' },
  { key: 'enterpriseRating', title: '企业评分' }, { key: 'positionRating', title: '岗位评分' },
  { key: 'advisor', title: '教师意见' }, { key: 'mentor', title: '企业意见' },
  { key: 'reviewStatus', title: '学校审核' }, { key: 'actions', title: '操作', width: '220px' }
]
const DETAIL = [
  { key: 'studentName', label: '学生' }, { key: 'advisorName', label: '指导教师' },
  { key: 'selfSummary', label: '实习总结' }, { key: 'selfHarvest', label: '学习收获' },
  { key: 'selfProblem', label: '存在问题' },
  { key: 'enterpriseRating', label: '对企业评分（1-5）' }, { key: 'enterpriseFeedback', label: '对企业评价' },
  { key: 'positionRating', label: '对岗位评分（1-5）' }, { key: 'positionFeedback', label: '对岗位评价' },
  { key: 'advisorOpinion', label: '指导教师意见' },
  { key: 'mentorOpinion', label: '企业导师意见' }, { key: 'reviewStatusLabel', label: '学校审核' },
  { key: 'reviewComment', label: '审核意见' }
]
const STATUS_OPTIONS = [{ label: '待审核', value: 'PENDING' }, { label: '已通过', value: 'APPROVED' }, { label: '已退回', value: 'RETURNED' }]

export default {
  name: 'StudentEvalView',
  components: { ModulePageShell, DataTable, AppButton, AppStatusTag, AppConfirmDialog, AppExportButton,
    AppPermissionButton, AppDescriptionList, AppAuditTrail, AppSearchBox, AppQuickFilterChips, AppTextarea, AppFormItem },
  data() {
    return {
      rows: [], total: 0, page: 1, pageSize: 20, loading: false, error: '',
      keyword: '', statusFilter: '', columns: COLUMNS, statusOptions: STATUS_OPTIONS,
      cmtForm: { advisorOpinion: '', mentorOpinion: '' }, cmtDlg: { visible: false, submitting: false }, cmtRow: null,
      detailDlg: { visible: false, loading: false, data: null },
      cd: { visible: false, title: '', content: '', danger: false, confirmText: '确认', requireReason: false, submitting: false },
      pending: null,
      scopeHint: '指导教师仅本人指导学生；管理员全校'
    }
  },
  computed: {
    pagination() { return { page: this.page, pageSize: this.pageSize, total: this.total } },
    detailItems() {
      const d = this.detailDlg.data || {}
      return DETAIL.map((f) => ({
        label: f.label,
        value: d[f.key] != null && d[f.key] !== '' ? d[f.key] : '—'
      }))
    },
    auditRecords() {
      return (this.detailDlg.data?.auditTrail || []).map((t, i) => ({
        id: i, action: t.action, actor: t.operator, reason: t.detail && (t.detail.comment || ''), at: t.occurredAt
      }))
    }
  },
  created() { this.load() },
  methods: {
    reviewTone(s) { return s === 'APPROVED' ? 'success' : s === 'RETURNED' ? 'danger' : 'warning' },
    exportFn() { return studentEvalApi.exportEvals({ keyword: this.keyword, reviewStatus: this.statusFilter }) },
    onExported(data) { toast.success(`已导出 ${data.rowCount} 条（水印 + 导出留痕）`) },
    reload() { this.page = 1; this.load() },
    onPageChange(p) { this.page = p; this.load() },
    async load() {
      this.loading = true; this.error = ''
      const params = { page: this.page, pageSize: this.pageSize, keyword: this.keyword }
      if (this.statusFilter) params.reviewStatus = this.statusFilter
      const res = await studentEvalApi.getEvals(params)
      this.loading = false
      if (res.code !== 0) { this.error = res.message || '加载失败'; this.rows = []; this.total = 0; return }
      this.rows = res.data.list; this.total = res.data.total
    },
    openComment(r) { this.cmtRow = r; this.cmtForm = { advisorOpinion: '', mentorOpinion: '' }; this.cmtDlg.visible = true },
    async submitComment() {
      if (!this.cmtForm.advisorOpinion.trim()) return toast.error('请填写指导教师意见')
      this.cmtDlg.submitting = true
      const res = await studentEvalApi.advisorComment(this.cmtRow.id, this.cmtForm)
      this.cmtDlg.submitting = false
      if (res.code !== 0) return toast.error(res.message || '保存失败')
      this.cmtDlg.visible = false; toast.success('已保存意见'); this.load()
    },
    async openDetail(r) {
      this.detailDlg = { visible: true, loading: true, data: null }
      const res = await studentEvalApi.getDetail(r.id)
      this.detailDlg.loading = false
      if (res.code !== 0) { toast.error(res.message); this.detailDlg.visible = false; return }
      this.detailDlg.data = res.data
    },
    openReview(r, action) {
      const ap = action === 'APPROVE'
      this.pending = { id: r.id, action }
      this.cd = { visible: true, title: ap ? '鉴定 · 通过' : '鉴定 · 退回',
        content: `${ap ? '通过' : '退回'}「${r.studentName}」的实习鉴定，意见将写入审计。`,
        danger: !ap, confirmText: ap ? '通过' : '退回', requireReason: !ap, submitting: false }
    },
    async onConfirm({ reason }) {
      this.cd.submitting = true
      const res = await studentEvalApi.review(this.pending.id, { action: this.pending.action, comment: reason || '' })
      this.cd.submitting = false
      if (res.code !== 0) return toast.error(res.message || '操作失败')
      this.cd.visible = false; toast.success('审核完成，已写审计'); this.load()
    }
  }
}
</script>

<style scoped>
.bar { display: flex; align-items: center; gap: var(--space-3); margin-bottom: var(--space-3); flex-wrap: wrap; }
.bar__hint { font-size: var(--font-size-xs); color: var(--text-tertiary); margin-left: auto; }
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
