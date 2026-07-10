<template>
  <ModulePageShell title="申请与协议办理" subtitle="审核学生实习申请，并完成协议发起、确认、变更和归档 · 三方协议 · 协议生成 · 学生/企业/学校确认 · 签署扫描件留痕"
    role-name="指导教师 / 管理员" :data-scope-name="scopeHint" :watermark="false">
    <template #actions>
      <AppPermissionButton code="internship.agreement.create" variant="primary" @click="openGenerate">＋ 生成协议</AppPermissionButton>
      <AppButton variant="ghost" @click="$router.push('/admin/internship/agreement-templates')">协议模板</AppButton>
      <AppExportButton :export-fn="exportFn" @exported="onExported">⬇ 导出 Excel 台账</AppExportButton>
    </template>

    <ModuleSummaryStrip :metrics="summaryMetrics" :note="summaryMetrics.length ? '' : '暂无统计口径'" />

    <div class="bar">
      <AppSearchBox v-model="keyword" placeholder="按学生姓名搜索" @search="reload" />
      <AppSelect v-model="statusFilter" :options="statusSelectOptions" placeholder="全部状态" @change="reload" />
    </div>

    <div v-if="error" class="state is-err">{{ error }} <button @click="load">重试</button></div>
    <DataTable v-else :columns="columns" :rows="rows" row-key="id" :loading="loading"
      :pagination="pagination" @page-change="onPageChange">
      <template #cell-studentConfirm="{ row }"><AppStatusTag :type="confirmTone(row.studentConfirm)">{{ row.studentConfirmLabel }}</AppStatusTag></template>
      <template #cell-enterpriseConfirm="{ row }"><AppStatusTag :type="confirmTone(row.enterpriseConfirm)">{{ row.enterpriseConfirmLabel }}</AppStatusTag></template>
      <template #cell-schoolConfirm="{ row }"><AppStatusTag :type="confirmTone(row.schoolConfirm)">{{ row.schoolConfirmLabel }}</AppStatusTag></template>
      <template #cell-status="{ row }"><AppStatusTag :status="row.status">{{ row.statusLabel }}</AppStatusTag></template>
      <template #cell-esignStatus="{ row }">
        <AppStatusTag :type="row.esignStatus === 'SIGNED' ? 'success' : row.esignStatus === 'PENDING' ? 'warning' : 'default'">
          {{ row.esignStatus === 'SIGNED' ? '已签' : row.esignStatus === 'PENDING' ? '签署中' : '未发起' }}
        </AppStatusTag>
      </template>
      <template #cell-actions="{ row }">
        <div class="ops">
          <AppButton variant="ghost" size="sm" @click="openDetail(row)">详情</AppButton>
          <AppPermissionButton v-if="row.status === 'DRAFT'" code="internship.agreement.issue" variant="secondary" size="sm" @click="confirmAct(row, 'issue')">下发</AppPermissionButton>
          <AppPermissionButton v-if="row.esignStatus === 'NONE' && canVoid(row.status)" code="internship.agreement.issue" variant="ghost" size="sm" @click="startEsign(row)">发起电子签</AppPermissionButton>
          <AppPermissionButton v-if="row.esignStatus === 'PENDING' && row.status === 'PENDING_ENTERPRISE'" code="internship.agreement.confirm" variant="ghost" size="sm" @click="esignParty(row, 'ENTERPRISE')">企业电子签</AppPermissionButton>
          <AppPermissionButton v-if="row.esignStatus === 'PENDING' && row.status === 'PENDING_SCHOOL'" code="internship.agreement.confirm" variant="ghost" size="sm" @click="esignParty(row, 'SCHOOL')">学校电子签</AppPermissionButton>
          <AppPermissionButton v-if="row.status === 'PENDING_ENTERPRISE'" code="internship.agreement.confirm" variant="secondary" size="sm" @click="openEnterprise(row)">记录企业签署</AppPermissionButton>
          <AppPermissionButton v-if="row.status === 'PENDING_SCHOOL'" code="internship.agreement.confirm" variant="secondary" size="sm" @click="confirmAct(row, 'school')">学校确认</AppPermissionButton>
          <AppPermissionButton v-if="row.status === 'EFFECTIVE'" code="internship.agreement.archive" variant="ghost" size="sm" @click="confirmAct(row, 'archive')">归档</AppPermissionButton>
          <AppPermissionButton v-if="canReject(row.status)" code="internship.agreement.reject" variant="ghost" size="sm" :danger="true" @click="confirmAct(row, 'reject')">驳回</AppPermissionButton>
          <AppPermissionButton v-if="canVoid(row.status)" code="internship.agreement.void" variant="ghost" size="sm" :danger="true" @click="confirmAct(row, 'void')">作废</AppPermissionButton>
        </div>
      </template>
    </DataTable>

    <!-- 生成 -->
    <div v-if="genDlg.visible" class="modal" @click.self="genDlg.visible = false">
      <div class="modal__card">
        <div class="modal__head">生成三方协议</div>
        <div class="modal__body">
          <AppFormItem label="实习学生" required>
            <AppStudentPicker
              v-model="genForm.internshipId"
              :remote-search="searchInternStudents"
              placeholder="输入姓名或学号搜索实习学生"
              search-placeholder="按姓名 / 学号搜索"
              data-scope-hint="指导教师仅本人指导学生；管理员全校"
            />
          </AppFormItem>
          <AppFormItem label="协议模板">
            <AppSelect v-model="genForm.templateId" :options="templateSelectOptions" placeholder="不选则自动使用默认启用模板" />
          </AppFormItem>
          <p v-if="previewText" class="preview">{{ previewText }}</p>
          <p class="hint">生成后为草稿，需依次「下发→学生确认→企业签署(上传扫描件)→学校确认」方可生效。仅可对本人指导学生生成。</p>
        </div>
        <div class="modal__foot">
          <AppButton variant="ghost" @click="genDlg.visible = false">取消</AppButton>
          <AppButton variant="primary" :loading="genDlg.submitting" @click="submitGenerate">生成</AppButton>
        </div>
      </div>
    </div>

    <!-- 记录企业签署 -->
    <div v-if="entDlg.visible" class="modal" @click.self="entDlg.visible = false">
      <div class="modal__card">
        <div class="modal__head">记录企业签署</div>
        <div class="modal__body">
          <AppFormItem label="企业经办人"><AppTextInput v-model="entForm.confirmBy" placeholder="如：企业 HR 张三" /></AppFormItem>
          <AppFormItem label="签署扫描件（企业已签的纸质三方协议）" required>
            <input type="file" class="file" @change="onEntFile" />
            <span v-if="entForm.fileId" class="att">已上传：{{ entAttachName }}</span>
            <span v-else-if="uploadingFile" class="att">上传中…</span>
          </AppFormItem>
          <p class="hint">无电子签章时，以上传企业已签署的纸质三方协议扫描件为准（电子签章能力预留）。</p>
        </div>
        <div class="modal__foot">
          <AppButton variant="ghost" @click="entDlg.visible = false">取消</AppButton>
          <AppButton variant="primary" :loading="entDlg.submitting" :disabled="!entForm.fileId" @click="submitEnterprise">确认企业已签署</AppButton>
        </div>
      </div>
    </div>

    <!-- 详情 -->
    <div v-if="detailDlg.visible" class="modal" @click.self="detailDlg.visible = false">
      <div class="modal__card">
        <div class="modal__head">协议详情</div>
        <div class="modal__body">
          <div v-if="detailDlg.loading" class="state">加载中…</div>
          <template v-else-if="detailDlg.data">
            <AppDescriptionList :items="detailItems" :columns="2" />
            <template v-if="detailDlg.data.renderedBody">
              <div class="sec-t">协议正文（模板渲染快照）</div>
              <pre id="agreement-print-body" class="ag-body">{{ detailDlg.data.renderedBody }}</pre>
            </template>
            <template v-if="detailDlg.data.attachment">
              <div class="sec-t">签署扫描件</div>
              <AppFilePreview :files="attachmentFiles" @download="downloadAtt" />
            </template>
            <div class="sec-t">三方确认留痕</div>
            <AppAuditTrail :records="auditRecords" :show-ip="false" compact empty-text="暂无确认记录" />
          </template>
        </div>
        <div class="modal__foot">
          <AppPrintButton v-if="detailDlg.data?.renderedBody" print-selector="#agreement-print-body" label="打印正文" />
          <AppPermissionButton v-if="detailDlg.data?.renderedBody" code="internship.agreement.view"
            variant="secondary" :loading="pdfLoading" @click="downloadPdf">下载 PDF 套打</AppPermissionButton>
          <AppButton variant="secondary" @click="detailDlg.visible = false">关闭</AppButton>
        </div>
      </div>
    </div>

    <AppConfirmDialog v-model:visible="cd.visible" :title="cd.title" :content="cd.content"
      :danger="cd.danger" :confirm-text="cd.confirmText" :require-reason="cd.requireReason"
      reason-label="原因" :submitting="cd.submitting" @confirm="onConfirm" />
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, DataTable } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppStatusTag, AppConfirmDialog, AppExportButton, AppPermissionButton, AppDescriptionList,
  AppAuditTrail, AppSearchBox, AppSelect, AppTextInput, AppFormItem, AppFilePreview, AppPrintButton,
  AppStudentPicker } from '@/components/common'
import { searchInternStudents } from './components/entityPickerAdapters'
import ModuleSummaryStrip from './components/ModuleSummaryStrip.vue'
import { agreementApi } from '@/modules/internship/api/agreement.api'
import { agreementTemplateApi } from '@/modules/internship/api/agreement-template.api'
import { downloadXlsxFromApi } from '@/utils/xlsxDownload'
import { toast } from '@/utils/toast'

const STATUS_MAP = {
  DRAFT: '草稿', PENDING_STUDENT: '待学生确认', PENDING_ENTERPRISE: '待企业确认',
  PENDING_SCHOOL: '待学校确认', EFFECTIVE: '已生效', REJECTED: '已驳回', VOIDED: '已作废', ARCHIVED: '已归档'
}
const COLUMNS = [
  { key: 'studentNo', title: '学号', width: '100px' }, { key: 'studentName', title: '姓名' },
  { key: 'enterpriseName', title: '企业' }, { key: 'positionName', title: '岗位' },
  { key: 'studentConfirm', title: '学生' }, { key: 'enterpriseConfirm', title: '企业' },
  { key: 'schoolConfirm', title: '学校' }, { key: 'esignStatus', title: '电子签' },
  { key: 'status', title: '协议状态' },
  { key: 'actions', title: '操作', width: '280px' }
]
const DETAIL = [
  { key: 'studentName', label: '学生' }, { key: 'advisorName', label: '指导教师' },
  { key: 'enterpriseName', label: '企业' }, { key: 'positionName', label: '岗位' },
  { key: 'templateName', label: '协议模板' },
  { key: 'studentConfirmLabel', label: '学生确认' }, { key: 'enterpriseConfirmLabel', label: '企业确认' },
  { key: 'schoolConfirmLabel', label: '学校确认' }, { key: 'statusLabel', label: '协议状态' },
  { key: 'rejectReason', label: '驳回/作废原因' }
]
const PANEL_PRESETS = {
  issue: () => ({ statusFilter: 'DRAFT' }),
  confirm: () => ({ statusFilter: 'PENDING_ENTERPRISE' }),
  change: () => ({ statusFilter: '' }),
  archive: () => ({ statusFilter: 'ARCHIVED' }),
  'student-apply': () => ({ statusFilter: 'PENDING_STUDENT' }),
  'self-apply': () => ({ statusFilter: 'PENDING_STUDENT' }),
  'position-apply': () => ({ statusFilter: 'PENDING_ENTERPRISE' }),
  'audit-ledger': () => ({ statusFilter: '' })
}

export default {
  name: 'AgreementView',
  components: { ModulePageShell, DataTable, AppButton, AppStatusTag, AppConfirmDialog, AppExportButton,
    AppPermissionButton, AppDescriptionList, AppAuditTrail, AppSearchBox, AppSelect, AppTextInput, AppFormItem,
    AppFilePreview, AppPrintButton, AppStudentPicker, ModuleSummaryStrip },
  data() {
    return {
      rows: [], total: 0, page: 1, pageSize: 20, loading: false, error: '',
      keyword: '', statusFilter: '', columns: COLUMNS,
      templateOptions: [],
      previewText: '',
      genForm: { internshipId: '', templateId: '' }, genDlg: { visible: false, submitting: false },
      entForm: { confirmBy: '', fileId: '' }, entDlg: { visible: false, submitting: false }, entRow: null,
      entAttachName: '', uploadingFile: false,
      detailDlg: { visible: false, loading: false, data: null },
      cd: { visible: false, title: '', content: '', danger: false, confirmText: '确认', requireReason: false, submitting: false },
      pending: null,
      pdfLoading: false,
      scopeHint: '指导教师仅本人指导学生；管理员全校'
    }
  },
  computed: {
    pagination() { return { page: this.page, pageSize: this.pageSize, total: this.total } },
    summaryMetrics() {
      if (this.loading || this.error) return []
      return [{ label: '协议/申请总数', value: this.total }]
    },
    statusSelectOptions() { return Object.entries(STATUS_MAP).map(([value, label]) => ({ value, label })) },
    templateSelectOptions() {
      return [{ value: '', label: '自动使用默认启用模板' }].concat(
        this.templateOptions.map((t) => ({ value: t.id, label: t.label || t.name }))
      )
    },
    detailItems() { const d = this.detailDlg.data || {}; return DETAIL.map((f) => ({ label: f.label, value: d[f.key] })) },
    attachmentFiles() { const a = this.detailDlg.data?.attachment; return a ? [{ id: a.fileId, name: a.fileName, sensitive: true }] : [] },
    auditRecords() {
      return (this.detailDlg.data?.auditTrail || []).map((t, i) => ({
        id: i, action: t.action, actor: t.operator, reason: t.detail && (t.detail.reason || t.detail.confirmBy || ''), at: t.occurredAt
      }))
    }
  },
  watch: {
    '$route.query.panel': {
      immediate: true,
      handler(panel) {
        this.applyPanel((panel || 'issue').toString())
      }
    },
    'genForm.internshipId'() { this.loadPreview() },
    'genForm.templateId'() { this.loadPreview() }
  },
  methods: {
    applyPanel(panel) {
      const preset = PANEL_PRESETS[panel] || PANEL_PRESETS.issue
      this.statusFilter = preset().statusFilter
      this.keyword = ''
      this.page = 1
      this.load()
    },
    confirmTone(s) { return s === 'CONFIRMED' ? 'success' : s === 'REJECTED' ? 'danger' : 'warning' },
    canReject(s) { return ['PENDING_STUDENT', 'PENDING_ENTERPRISE', 'PENDING_SCHOOL'].includes(s) },
    canVoid(s) { return ['DRAFT', 'PENDING_STUDENT', 'PENDING_ENTERPRISE', 'PENDING_SCHOOL'].includes(s) },
    exportFn() { return agreementApi.exportAgreements({ keyword: this.keyword, status: this.statusFilter }) },
    onExported(data) { toast.success(`已导出 ${data.rowCount} 条（水印 + 导出留痕）`) },
    reload() { this.page = 1; this.load() },
    onPageChange(p) { this.page = p; this.load() },
    async load() {
      this.loading = true; this.error = ''
      const params = { page: this.page, pageSize: this.pageSize, keyword: this.keyword }
      if (this.statusFilter) params.status = this.statusFilter
      const res = await agreementApi.getAgreements(params)
      this.loading = false
      if (res.code !== 0) { this.error = res.message || '加载失败'; this.rows = []; this.total = 0; return }
      this.rows = res.data.list; this.total = res.data.total
    },
    // 选择器远程搜索（岗位实习模块适配层，后端裁定关键字与数据范围）
    searchInternStudents,
    async openGenerate() {
      // 学生候选改为选择器内按关键字远程搜索，不再一次性预载 200 条
      this.genForm = { internshipId: '', templateId: '' }
      this.previewText = ''
      this.genDlg.visible = true
      if (!this.templateOptions.length) {
        const res = await agreementTemplateApi.getEnabledOptions()
        if (res.code === 0) this.templateOptions = res.data || []
      }
    },
    async loadPreview() {
      this.previewText = ''
      if (!this.genForm.internshipId) return
      const tplId = this.genForm.templateId || (this.templateOptions.find((t) => t.isDefault) || this.templateOptions[0])?.id
      if (!tplId) return
      const res = await agreementTemplateApi.previewTemplate(tplId, { internshipId: this.genForm.internshipId })
      if (res.code === 0 && res.data?.renderedBody) {
        const body = res.data.renderedBody
        this.previewText = body.length > 120 ? body.slice(0, 120) + '…' : body
      }
    },
    async submitGenerate() {
      if (!this.genForm.internshipId) return toast.error('请选择实习学生')
      this.genDlg.submitting = true
      const payload = { internshipId: this.genForm.internshipId }
      if (this.genForm.templateId) payload.templateId = this.genForm.templateId
      const res = await agreementApi.generate(payload)
      this.genDlg.submitting = false
      if (res.code !== 0) return toast.error(res.message || '生成失败')
      this.genDlg.visible = false; toast.success('已生成协议草稿'); this.load()
    },
    openEnterprise(r) { this.entRow = r; this.entForm = { confirmBy: '', fileId: '' }; this.entAttachName = ''; this.entDlg.visible = true },
    async onEntFile(e) {
      const file = e.target.files && e.target.files[0]
      if (!file) return
      this.uploadingFile = true
      const res = await agreementApi.uploadAttachment(file)
      this.uploadingFile = false
      if (res.code !== 0) return toast.error(res.message || '上传失败')
      this.entForm.fileId = res.data.fileId; this.entAttachName = res.data.fileName || file.name
      toast.success('扫描件已上传')
    },
    async submitEnterprise() {
      this.entDlg.submitting = true
      const res = await agreementApi.enterpriseConfirm(this.entRow.id, { confirmBy: this.entForm.confirmBy, fileId: this.entForm.fileId })
      this.entDlg.submitting = false
      if (res.code !== 0) return toast.error(res.message || '提交失败')
      this.entDlg.visible = false; toast.success('已记录企业签署'); this.load()
    },
    async openDetail(r) {
      this.detailDlg = { visible: true, loading: true, data: null }
      const res = await agreementApi.getDetail(r.id)
      this.detailDlg.loading = false
      if (res.code !== 0) { toast.error(res.message); this.detailDlg.visible = false; return }
      this.detailDlg.data = res.data
    },
    async downloadAtt() {
      const a = this.detailDlg.data?.attachment
      if (!a) return
      try { await agreementApi.downloadAttachment(a.fileId, a.fileName) } catch (e) { toast.error('下载失败：' + (e.message || '')) }
    },
    async downloadPdf() {
      const id = this.detailDlg.data?.id
      if (!id || this.pdfLoading) return
      this.pdfLoading = true
      const res = await agreementApi.exportAgreementPdf(id)
      this.pdfLoading = false
      if (res.code !== 0) return toast.error(res.message || 'PDF 生成失败')
      downloadXlsxFromApi(res.data)
      toast.success('PDF 套打已下载（含水印与导出留痕）')
    },
    confirmAct(r, kind) {
      const map = {
        issue: { title: '下发协议', content: `将「${r.studentName}」的协议下发给学生确认？`, danger: false, confirmText: '下发', requireReason: false },
        school: { title: '学校确认', content: `确认「${r.studentName}」三方协议生效？`, danger: false, confirmText: '确认生效', requireReason: false },
        archive: { title: '归档协议', content: `归档「${r.studentName}」的已生效协议？`, danger: false, confirmText: '归档', requireReason: false },
        reject: { title: '驳回协议', content: `驳回「${r.studentName}」的协议，原因将写入审计。`, danger: true, confirmText: '驳回', requireReason: true },
        void: { title: '作废协议', content: `作废「${r.studentName}」的协议，原因将写入审计。`, danger: true, confirmText: '作废', requireReason: true }
      }[kind]
      this.pending = { id: r.id, kind }
      this.cd = { visible: true, ...map, submitting: false }
    },
    async onConfirm({ reason }) {
      const p = this.pending
      this.cd.submitting = true
      let res
      if (p.kind === 'issue') res = await agreementApi.issue(p.id)
      else if (p.kind === 'school') res = await agreementApi.schoolConfirm(p.id)
      else if (p.kind === 'archive') res = await agreementApi.archive(p.id)
      else if (p.kind === 'reject') res = await agreementApi.reject(p.id, { reason })
      else res = await agreementApi.voidAgreement(p.id, { reason })
      this.cd.submitting = false
      if (res.code !== 0) return toast.error(res.message || '操作失败')
      this.cd.visible = false; toast.success('操作成功，已写审计'); this.load()
    },
    async startEsign(row) {
      const res = await agreementApi.startEsign(row.id)
      if (res.code !== 0) return toast.error(res.message)
      toast.success(res.data.message || '已发起电子签')
      this.load()
    },
    async esignParty(row, party) {
      const res = await agreementApi.esignSign(row.id, { party })
      if (res.code !== 0) return toast.error(res.message)
      toast.success(`${party === 'SCHOOL' ? '学校' : '企业'}电子签完成`)
      this.load()
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
.preview { margin: var(--space-2) 0 0; padding: var(--space-2); background: var(--bg-subtle, #f8fafc); border-radius: 6px; font-size: var(--font-size-xs); color: var(--text-secondary); white-space: pre-wrap; }
.ag-body { white-space: pre-wrap; word-break: break-word; background: var(--bg-subtle, #f8fafc); border: 1px solid var(--border-light); border-radius: 8px; padding: 10px; font-size: 12px; max-height: 240px; overflow: auto; margin: 0; }
.file { font-size: var(--font-size-xs); }
.att { font-size: var(--font-size-xs); color: var(--success-700); margin-left: var(--space-2); }
.modal { position: fixed; inset: 0; background: rgba(15, 23, 42, 0.45); display: flex; align-items: center; justify-content: center; z-index: var(--z-modal, 1000); padding: var(--space-4); }
.modal__card { background: var(--bg-card); border-radius: var(--radius-lg); width: min(560px, 100%); max-height: 88vh; display: flex; flex-direction: column; box-shadow: var(--shadow-lg); }
.modal__head { padding: var(--space-4); font-weight: var(--font-weight-semibold); border-bottom: 1px solid var(--border-light); }
.modal__body { padding: var(--space-4); overflow-y: auto; }
.modal__foot { padding: var(--space-3) var(--space-4); border-top: 1px solid var(--border-light); display: flex; justify-content: flex-end; gap: var(--space-2); }
</style>
