<template>
  <ModulePageShell title="申请与协议办理" subtitle="审核学生实习申请，并完成协议发起、确认、变更和归档 · 三方协议 · 协议生成 · 学生/企业/学校确认 · 签署扫描件留痕"
    role-name="指导教师 / 管理员" :data-scope-name="scopeHint" :watermark="false">
    <template #actions>
      <AppPermissionButton code="internship.agreement.manage" :allowed="canBtn('internship.agreement.manage')" variant="primary" @click="openGenerate">＋ 生成协议</AppPermissionButton>
      <AppButton variant="ghost" @click="goTemplates">协议模板</AppButton>
      <AppExportButton :export-fn="exportFn" @exported="onExported">⬇ 导出 Excel 台账</AppExportButton>
    </template>

    <ModuleSummaryStrip :metrics="summaryMetrics" :note="summaryMetrics.length ? '' : '暂无统计口径'" />

    <nav class="ag-flow" aria-label="三方协议办理流程">
      <span class="ag-flow__title">协议办理</span>
      <button
        v-for="(step, index) in flowSteps"
        :key="step.panel"
        type="button"
        class="ag-flow__step"
        :class="{ 'is-active': activePanel === step.panel }"
        @click="goPanel(step.panel)"
      >
        <span class="ag-flow__index">0{{ index + 1 }}</span>
        <span>{{ step.label }}</span>
      </button>
    </nav>

    <div class="bar">
      <AppSearchBox v-model="keyword" placeholder="按学生姓名搜索" @search="reload" />
      <AppSelect v-model="statusFilter" :options="statusSelectOptions" placeholder="全部状态" @change="reload" />
    </div>

    <ErrorState v-if="error" :description="error" @retry="load" />
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
        <!-- 全部办理动作收口至三方协议档案页（独立页），列表只保留主入口 -->
        <AppButton variant="secondary" size="sm" @click="openDossier(row)">
          {{ ['DRAFT', 'PENDING_ENTERPRISE', 'PENDING_SCHOOL', 'EFFECTIVE'].includes(row.status) ? '办理' : '查看档案' }}
        </AppButton>
      </template>
    </DataTable>

    <!-- 生成 -->
    <AppDrawer :visible="genDlg.visible" title="生成三方协议" @update:visible="genDlg.visible = $event">
      <AppFormItem label="实习学生" required>
        <AppInternshipStudentPicker
          v-model="genForm.internshipId"
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
      <template #footer>
        <AppButton variant="ghost" @click="genDlg.visible = false">取消</AppButton>
        <AppButton variant="primary" :loading="genDlg.submitting" @click="submitGenerate">生成</AppButton>
      </template>
    </AppDrawer>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, DataTable, ErrorState } from '@/components/business'
import { AppButton, AppDrawer } from '@/components/ui'
import { AppStatusTag, AppExportButton, AppPermissionButton, AppSearchBox, AppSelect, AppFormItem,
  AppInternshipStudentPicker } from '@/components/common'
import ModuleSummaryStrip from './components/ModuleSummaryStrip.vue'
import { agreementApi } from '@/modules/internship/api/agreement.api'
import { agreementTemplateApi } from '@/modules/internship/api/agreement-template.api'
import { canCode } from '@/modules/internship/composables/permission'
import { toast } from '@/utils/toast'
import { useInternshipBatchStore } from '@/stores/internshipBatch'

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
const PANEL_PRESETS = {
  issue: () => ({ statusFilter: 'DRAFT' }),
  confirm: () => ({ statusFilter: 'PENDING_ENTERPRISE' }),
  change: () => ({ statusFilter: '' }),
  archive: () => ({ statusFilter: 'ARCHIVED' }),
  'student-apply': () => ({ statusFilter: 'PENDING_STUDENT' }),
  'self-apply': () => ({ statusFilter: 'PENDING_STUDENT' }),
  'position-apply': () => ({ statusFilter: 'PENDING_ENTERPRISE' }),
  'school-confirm': () => ({ statusFilter: 'PENDING_SCHOOL' }),
  'audit-ledger': () => ({ statusFilter: '' })
}

export default {
  name: 'AgreementView',
  props: { ctx: { type: Object, default: () => ({}) } },
  components: { ModulePageShell, DataTable, ErrorState, AppButton, AppDrawer, AppStatusTag, AppExportButton,
    AppPermissionButton, AppSearchBox, AppSelect, AppFormItem, AppInternshipStudentPicker, ModuleSummaryStrip },
  data() {
    return {
      rows: [], total: 0, page: 1, pageSize: 20, loading: false, error: '',
      keyword: '', statusFilter: '', activePanel: 'issue', columns: COLUMNS,
      templateOptions: [],
      previewText: '',
      genForm: { internshipId: '', templateId: '' }, genDlg: { visible: false, submitting: false },
      scopeHint: '指导教师仅本人指导学生；管理员全校'
    }
  },
  computed: {
    batchStore() { return useInternshipBatchStore() },
    pagination() { return { page: this.page, pageSize: this.pageSize, total: this.total } },
    flowSteps() {
      return [
        { panel: 'issue', label: '发起协议' },
        { panel: 'student-apply', label: '学生确认' },
        { panel: 'position-apply', label: '企业确认' },
        { panel: 'school-confirm', label: '学校确认' },
        { panel: 'archive', label: '归档留存' }
      ]
    },
    summaryMetrics() {
      if (this.loading || this.error) return []
      return [{ label: '协议/申请总数', value: this.total }]
    },
    statusSelectOptions() { return Object.entries(STATUS_MAP).map(([value, label]) => ({ value, label })) },
    templateSelectOptions() {
      return [{ value: '', label: '自动使用默认启用模板' }].concat(
        this.templateOptions.map((t) => ({ value: t.id, label: t.label || t.name }))
      )
    }
  },
  watch: {
    '$route.query.panel': {
      immediate: true,
      handler(panel) {
        this.applyPanel((panel || 'issue').toString())
      }
    },
    'batchStore.selectedBatchId'() {
      this.page = 1
      this.load()
    },
    'genForm.internshipId'() { this.loadPreview() },
    'genForm.templateId'() { this.loadPreview() }
  },
  methods: {
    canBtn(code) { return canCode(this.ctx, code) },
    applyPanel(panel) {
      const preset = PANEL_PRESETS[panel] || PANEL_PRESETS.issue
      this.activePanel = PANEL_PRESETS[panel] ? panel : 'issue'
      this.statusFilter = preset().statusFilter
      this.keyword = ''
      this.page = 1
      this.load()
    },
    goPanel(panel) {
      if (this.activePanel === panel) return
      this.$router.replace({ path: this.$route.path, query: this.batchStore.withBatchQuery({ ...this.$route.query, panel }) })
    },
    confirmTone(s) { return s === 'CONFIRMED' ? 'success' : s === 'REJECTED' ? 'danger' : 'warning' },
    goTemplates() { this.$router.push({ path: '/admin/internship/agreement-templates', query: this.batchStore.withBatchQuery() }) },
    openDossier(row) { this.$router.push({ path: `/admin/internship/agreements/${row.id}`, query: this.batchStore.withBatchQuery() }) },
    exportFn() {
      if (!this.batchStore.selectedBatchId) return Promise.resolve({ code: 1, message: '请先选择批次' })
      return agreementApi.exportAgreements({ keyword: this.keyword, status: this.statusFilter, batchId: this.batchStore.selectedBatchId })
    },
    onExported(data) { toast.success(`已导出 ${data.rowCount} 条（水印 + 导出留痕）`) },
    reload() { this.page = 1; this.load() },
    onPageChange(p) { this.page = p; this.load() },
    async load() {
      if (!this.batchStore.selectedBatchId) {
        this.loading = false; this.error = '请先选择批次'; this.rows = []; this.total = 0
        return
      }
      this.loading = true; this.error = ''
      const params = { page: this.page, pageSize: this.pageSize, keyword: this.keyword, batchId: this.batchStore.selectedBatchId }
      if (this.statusFilter) params.status = this.statusFilter
      const res = await agreementApi.getAgreements(params)
      this.loading = false
      if (res.code !== 0) { this.error = res.message || '加载失败'; this.rows = []; this.total = 0; return }
      this.rows = res.data.list; this.total = res.data.total
    },
    // 选择器远程搜索（岗位实习模块适配层，后端裁定关键字与数据范围）
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
    // 详情、企业签署、下发/确认/归档/驳回/作废、电子签、PDF 套打：全部收口至三方协议档案页 AgreementDetailView
  }
}
</script>

<style scoped>
.ag-flow { display: flex; align-items: center; gap: 6px; padding: 8px 10px; border: 1px solid var(--card-b); border-radius: 12px; background: linear-gradient(100deg, var(--pri-bg), var(--card) 54%); box-shadow: var(--s1); overflow-x: auto; }
.ag-flow__title { flex: 0 0 auto; padding: 0 8px 0 2px; color: var(--t2); font-size: 12px; font-weight: var(--font-weight-semibold); }
.ag-flow__step { display: inline-flex; align-items: center; gap: 6px; flex: 0 0 auto; padding: 6px 10px; border: 1px solid transparent; border-radius: 8px; background: transparent; color: var(--t2); cursor: pointer; font-size: 12px; transition: .16s ease; }
.ag-flow__step:hover { color: var(--pri); background: var(--pri-bg); }
.ag-flow__step.is-active { color: var(--pri); border-color: var(--pri-100); background: var(--card); box-shadow: 0 2px 5px rgba(15, 40, 90, .07); font-weight: var(--font-weight-semibold); }
.ag-flow__index { color: var(--t3); font-size: 10px; font-weight: 800; }
.ag-flow__step.is-active .ag-flow__index { color: var(--pri); }
.bar { display: flex; align-items: center; gap: var(--space-3); margin-bottom: var(--space-3); padding: 10px 12px; border: 1px solid var(--card-b); border-radius: 12px; background: var(--card); box-shadow: var(--s1); flex-wrap: wrap; }
.ops { display: flex; gap: var(--space-1); flex-wrap: wrap; }
.sec-t { font-size: var(--font-size-sm); font-weight: var(--font-weight-medium); color: var(--text-secondary); margin: var(--space-3) 0 var(--space-2); }
.hint { margin: var(--space-2) 0 0; font-size: var(--font-size-xs); color: var(--text-tertiary); }
.preview { margin: var(--space-2) 0 0; padding: var(--space-2); background: var(--bg-subtle, #f8fafc); border-radius: 6px; font-size: var(--font-size-xs); color: var(--text-secondary); white-space: pre-wrap; }
.ag-body { white-space: pre-wrap; word-break: break-word; background: var(--bg-subtle, #f8fafc); border: 1px solid var(--border-light); border-radius: 8px; padding: 10px; font-size: 12px; max-height: 240px; overflow: auto; margin: 0; }
.file { font-size: var(--font-size-xs); }
.att { font-size: var(--font-size-xs); color: var(--success-700); margin-left: var(--space-2); }
</style>
