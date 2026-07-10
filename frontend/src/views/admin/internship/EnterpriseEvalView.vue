<template>
  <ModulePageShell title="评价管理" subtitle="完成学生、企业和教师评价，并进行成绩核算、审核、发布和复核 · 企业评价 · 企业导师五维评价 · 学校审核 · 来源可追溯"
    role-name="指导教师 / 管理员" :data-scope-name="scopeHint" :watermark="false">
    <template #actions>
      <AppButton variant="ghost" @click="$router.push('/admin/internship/student-evals')">学生自评与教师评价</AppButton>
      <AppButton variant="ghost" @click="$router.push('/admin/internship/scores')">综合成绩</AppButton>
      <AppPermissionButton code="internship.enterpriseEval.create" variant="primary" @click="openCreate">＋ 录入企业评价</AppPermissionButton>
      <AppExportButton :export-fn="exportFn" @exported="onExported">⬇ 导出 Excel 台账</AppExportButton>
    </template>

    <ModuleSummaryStrip :metrics="summaryMetrics" :note="summaryMetrics.length ? '' : '暂无统计口径'" />

    <div class="bar">
      <AppSearchBox v-model="keyword" placeholder="按学生姓名搜索" @search="reload" />
      <AppQuickFilterChips v-model="statusFilter" :options="statusOptions" allow-clear @change="reload" />
    </div>

    <div v-if="error" class="state is-err">{{ error }} <button @click="load">重试</button></div>
    <DataTable v-else :columns="columns" :rows="rows" row-key="id" :loading="loading"
      :pagination="pagination" @page-change="onPageChange">
      <template #cell-avgScore="{ row }"><b>{{ row.avgScore }}</b></template>
      <template #cell-recommendHire="{ row }">{{ row.recommendHire ? '是' : '否' }}</template>
      <template #cell-source="{ row }"><AppStatusTag :type="row.source === 'ENTERPRISE' ? 'success' : 'default'">{{ row.sourceLabel }}</AppStatusTag></template>
      <template #cell-reviewStatus="{ row }"><AppStatusTag :type="reviewTone(row.reviewStatus)">{{ row.reviewStatusLabel }}</AppStatusTag></template>
      <template #cell-actions="{ row }">
        <div class="ops">
          <AppButton variant="ghost" size="sm" @click="openDetail(row)">详情</AppButton>
          <template v-if="row.reviewStatus === 'PENDING'">
            <AppPermissionButton code="internship.enterpriseEval.review" variant="secondary" size="sm" @click="openReview(row, 'APPROVE')">通过</AppPermissionButton>
            <AppPermissionButton code="internship.enterpriseEval.review" variant="ghost" size="sm" :danger="true" @click="openReview(row, 'RETURN')">退回</AppPermissionButton>
          </template>
        </div>
      </template>
    </DataTable>

    <!-- 录入 -->
    <div v-if="createDlg.visible" class="modal" @click.self="createDlg.visible = false">
      <div class="modal__card">
        <div class="modal__head">录入企业评价</div>
        <div class="modal__body">
          <AppFormItem label="实习学生" required>
            <AppStudentPicker
              v-model="form.internshipId"
              :remote-search="searchInternStudents"
              placeholder="输入姓名或学号搜索实习学生"
              search-placeholder="按姓名 / 学号搜索"
              data-scope-hint="指导教师仅本人指导学生；管理员全校"
            />
          </AppFormItem>
          <AppFormItem label="企业导师姓名（来源可追溯）" required>
            <AppTextInput v-model="form.mentorName" placeholder="填写企业导师真实姓名" />
          </AppFormItem>
          <div class="scores">
            <AppFormItem v-for="s in scoreDefs" :key="s.key" :label="s.label" class="score">
              <AppNumberInput v-model="form[s.key]" :min="0" :max="100" />
            </AppFormItem>
          </div>
          <AppFormItem label="综合评语"><AppTextarea v-model="form.overallComment" :rows="2" placeholder="企业对学生的综合评语" /></AppFormItem>
          <label class="chk"><input v-model="form.recommendHire" type="checkbox" />建议录用</label>
          <AppFormItem label="评价扫描件（可选，企业签署）">
            <input type="file" class="file" @change="onFile" />
            <span v-if="form.fileId" class="att">已上传：{{ attachName }}</span>
            <span v-else-if="uploadingFile" class="att">上传中…</span>
          </AppFormItem>
          <p class="hint">五维评分均 0-100。学校录入的企业纸质评价来源标记为「学校录入」，请如实转录企业导师评价，勿代填虚构。</p>
        </div>
        <div class="modal__foot">
          <AppButton variant="ghost" @click="createDlg.visible = false">取消</AppButton>
          <AppButton variant="primary" :loading="createDlg.submitting" @click="submitCreate">提交</AppButton>
        </div>
      </div>
    </div>

    <!-- 详情 -->
    <div v-if="detailDlg.visible" class="modal" @click.self="detailDlg.visible = false">
      <div class="modal__card">
        <div class="modal__head">企业评价详情</div>
        <div class="modal__body">
          <div v-if="detailDlg.loading" class="state">加载中…</div>
          <template v-else-if="detailDlg.data">
            <AppDescriptionList :items="detailItems" :columns="2" />
            <template v-if="detailDlg.data.attachment">
              <div class="sec-t">评价扫描件</div>
              <AppFilePreview :files="attachmentFiles" @download="downloadAtt" />
            </template>
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
  AppAuditTrail, AppSearchBox, AppQuickFilterChips, AppTextInput, AppNumberInput,
  AppTextarea, AppFormItem, AppFilePreview, AppStudentPicker } from '@/components/common'
import { searchInternStudents } from './components/entityPickerAdapters'
import ModuleSummaryStrip from './components/ModuleSummaryStrip.vue'
import { enterpriseEvalApi } from '@/modules/internship/api/enterprise-eval.api'
import { toast } from '@/utils/toast'

const SCORES = [
  { key: 'attendanceScore', label: '出勤' }, { key: 'skillScore', label: '技能' },
  { key: 'attitudeScore', label: '态度' }, { key: 'collaborationScore', label: '协作' }, { key: 'safetyScore', label: '安全纪律' }
]
const COLUMNS = [
  { key: 'studentNo', title: '学号', width: '100px' }, { key: 'studentName', title: '姓名' },
  { key: 'mentorName', title: '企业导师' }, { key: 'attendanceScore', title: '出勤' },
  { key: 'skillScore', title: '技能' }, { key: 'attitudeScore', title: '态度' },
  { key: 'collaborationScore', title: '协作' }, { key: 'safetyScore', title: '安全' },
  { key: 'avgScore', title: '均分' }, { key: 'recommendHire', title: '建议录用' },
  { key: 'source', title: '来源' }, { key: 'reviewStatus', title: '审核' }, { key: 'actions', title: '操作', width: '170px' }
]
const STATUS_OPTIONS = [{ label: '待审核', value: 'PENDING' }, { label: '已通过', value: 'APPROVED' }, { label: '已退回', value: 'RETURNED' }]
const DETAIL = [
  { key: 'studentName', label: '学生' }, { key: 'mentorName', label: '企业导师' },
  { key: 'positionName', label: '岗位' }, { key: 'attendanceScore', label: '出勤' },
  { key: 'skillScore', label: '技能' }, { key: 'attitudeScore', label: '态度' },
  { key: 'collaborationScore', label: '协作' }, { key: 'safetyScore', label: '安全纪律' },
  { key: 'avgScore', label: '均分' }, { key: 'recommendHire', label: '建议录用', bool: true },
  { key: 'overallComment', label: '综合评语' }, { key: 'sourceLabel', label: '来源' },
  { key: 'reviewStatusLabel', label: '审核状态' }, { key: 'reviewComment', label: '审核意见' }
]

function emptyForm() {
  return { internshipId: '', mentorName: '', attendanceScore: null, skillScore: null,
    attitudeScore: null, collaborationScore: null, safetyScore: null, overallComment: '', recommendHire: false, fileId: '' }
}

export default {
  name: 'EnterpriseEvalView',
  components: { ModulePageShell, DataTable, AppButton, AppStatusTag, AppConfirmDialog, AppExportButton,
    AppPermissionButton, AppDescriptionList, AppAuditTrail, AppSearchBox, AppQuickFilterChips,
    AppTextInput, AppNumberInput, AppTextarea, AppFormItem, AppFilePreview, AppStudentPicker, ModuleSummaryStrip },
  data() {
    return {
      rows: [], total: 0, page: 1, pageSize: 20, loading: false, error: '',
      keyword: '', statusFilter: '', columns: COLUMNS, statusOptions: STATUS_OPTIONS, scoreDefs: SCORES,
      form: emptyForm(), attachName: '', uploadingFile: false,
      createDlg: { visible: false, submitting: false },
      detailDlg: { visible: false, loading: false, data: null },
      cd: { visible: false, title: '', content: '', danger: false, confirmText: '确认', requireReason: false, submitting: false },
      pending: null,
      scopeHint: '指导教师仅本人指导学生；管理员全校'
    }
  },
  computed: {
    pagination() { return { page: this.page, pageSize: this.pageSize, total: this.total } },
    detailItems() { const d = this.detailDlg.data || {}; return DETAIL.map((f) => ({ label: f.label, value: f.bool ? (d[f.key] ? '是' : '否') : d[f.key] })) },
    attachmentFiles() { const a = this.detailDlg.data?.attachment; return a ? [{ id: a.fileId, name: a.fileName, sensitive: true }] : [] },
    auditRecords() {
      return (this.detailDlg.data?.auditTrail || []).map((t, i) => ({
        id: i, action: t.action, actor: t.operator, reason: t.detail && (t.detail.comment || ''), at: t.occurredAt
      }))
    },
    summaryMetrics() {
      // 仅在列表真实加载成功后展示服务端 total；loading / error 一律不展示
      if (this.loading || this.error) return []
      return [{ label: '企业评价记录', value: this.total }]
    }
  },
  created() { this.load() },
  methods: {
    reviewTone(s) { return s === 'APPROVED' ? 'success' : s === 'RETURNED' ? 'danger' : 'warning' },
    exportFn() { return enterpriseEvalApi.exportEvals({ keyword: this.keyword, reviewStatus: this.statusFilter }) },
    onExported(data) { toast.success(`已导出 ${data.rowCount} 条（水印 + 导出留痕）`) },
    reload() { this.page = 1; this.load() },
    onPageChange(p) { this.page = p; this.load() },
    async load() {
      this.loading = true; this.error = ''
      const params = { page: this.page, pageSize: this.pageSize, keyword: this.keyword }
      if (this.statusFilter) params.reviewStatus = this.statusFilter
      const res = await enterpriseEvalApi.getEvals(params)
      this.loading = false
      if (res.code !== 0) { this.error = res.message || '加载失败'; this.rows = []; this.total = 0; return }
      this.rows = res.data.list; this.total = res.data.total
    },
    // 选择器远程搜索（岗位实习模块适配层，后端裁定关键字与数据范围）
    searchInternStudents,
    openCreate() {
      // 学生候选改为选择器内按关键字远程搜索，不再一次性预载 200 条
      this.form = emptyForm(); this.attachName = ''; this.createDlg.visible = true
    },
    async onFile(e) {
      const file = e.target.files && e.target.files[0]
      if (!file) return
      this.uploadingFile = true
      const res = await enterpriseEvalApi.uploadAttachment(file)
      this.uploadingFile = false
      if (res.code !== 0) return toast.error(res.message || '上传失败')
      this.form.fileId = res.data.fileId; this.attachName = res.data.fileName || file.name
    },
    async submitCreate() {
      if (!this.form.internshipId) return toast.error('请选择实习学生')
      if (!this.form.mentorName.trim()) return toast.error('请填写企业导师姓名')
      for (const s of SCORES) {
        const v = this.form[s.key]
        if (v === null || v === '' || v < 0 || v > 100) return toast.error(`${s.label}评分须为 0-100`)
      }
      this.createDlg.submitting = true
      const res = await enterpriseEvalApi.create(this.form)
      this.createDlg.submitting = false
      if (res.code !== 0) return toast.error(res.message || '提交失败')
      this.createDlg.visible = false; toast.success('已录入并写审计'); this.load()
    },
    async openDetail(r) {
      this.detailDlg = { visible: true, loading: true, data: null }
      const res = await enterpriseEvalApi.getDetail(r.id)
      this.detailDlg.loading = false
      if (res.code !== 0) { toast.error(res.message); this.detailDlg.visible = false; return }
      this.detailDlg.data = res.data
    },
    async downloadAtt() {
      const a = this.detailDlg.data?.attachment
      if (!a) return
      try { await enterpriseEvalApi.downloadAttachment(a.fileId, a.fileName) } catch (e) { toast.error('下载失败：' + (e.message || '')) }
    },
    openReview(r, action) {
      const ap = action === 'APPROVE'
      this.pending = { id: r.id, action }
      this.cd = { visible: true, title: ap ? '企业评价 · 通过' : '企业评价 · 退回',
        content: `${ap ? '通过' : '退回'}「${r.studentName}」的企业评价，意见将写入审计。`,
        danger: !ap, confirmText: ap ? '通过' : '退回', requireReason: !ap, submitting: false }
    },
    async onConfirm({ reason }) {
      this.cd.submitting = true
      const res = await enterpriseEvalApi.review(this.pending.id, { action: this.pending.action, comment: reason || '' })
      this.cd.submitting = false
      if (res.code !== 0) return toast.error(res.message || '操作失败')
      this.cd.visible = false; toast.success('审核完成，已写审计'); this.load()
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
.hint { margin: var(--space-2) 0 0; font-size: var(--font-size-xs); color: var(--text-tertiary); }
.scores { display: flex; flex-wrap: wrap; gap: var(--space-2); }
.score { width: calc(20% - var(--space-2)); min-width: 90px; }
.chk { display: flex; align-items: center; gap: var(--space-1); font-size: var(--font-size-sm); color: var(--text-secondary); margin-bottom: var(--space-3); }
.file { font-size: var(--font-size-xs); }
.att { font-size: var(--font-size-xs); color: var(--success-700); margin-left: var(--space-2); }
.modal { position: fixed; inset: 0; background: rgba(15, 23, 42, 0.45); display: flex; align-items: center; justify-content: center; z-index: var(--z-modal, 1000); padding: var(--space-4); }
.modal__card { background: var(--bg-card); border-radius: var(--radius-lg); width: min(600px, 100%); max-height: 88vh; display: flex; flex-direction: column; box-shadow: var(--shadow-lg); }
.modal__head { padding: var(--space-4); font-weight: var(--font-weight-semibold); border-bottom: 1px solid var(--border-light); }
.modal__body { padding: var(--space-4); overflow-y: auto; }
.modal__foot { padding: var(--space-3) var(--space-4); border-top: 1px solid var(--border-light); display: flex; justify-content: flex-end; gap: var(--space-2); }
</style>
