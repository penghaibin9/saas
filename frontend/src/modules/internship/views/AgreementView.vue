<template>
  <ModulePageShell :watermark="false" :title="isGenerating ? '生成三方协议' : '三方协议'" :subtitle="isGenerating ? '选择实习学生与适用模板，核对正文后生成草稿。' : '跟进三方确认，完成协议签署与归档。'">
    <template #actions>
      <AppButton v-if="isGenerating" variant="ghost" :disabled="genDlg.submitting" @click="backToList">返回协议列表</AppButton>
      <template v-else>
        <AppButton v-if="workspaceReturnTo" variant="ghost" @click="$router.push(workspaceReturnTo)">{{ workspaceReturnTo.startsWith('/admin/internship/students/') ? '返回学生上岗核验' : '返回归档核验' }}</AppButton>
        <AppPermissionButton code="internship.agreement.manage" :allowed="canBtn('internship.agreement.manage')" variant="primary" @click="openGenerate">生成协议</AppPermissionButton>
        <AppButton v-if="canBtn('internship.agreement.template.manage')" variant="ghost" @click="goTemplates">协议模板</AppButton>
        <AppExportButton v-if="canBtn('internship.agreement.export')" :export-fn="exportFn" @exported="onExported">导出台账</AppExportButton>
      </template>
    </template>
    <div v-if="isGenerating" class="ag-generate">
      <section class="ag-card ag-form">
        <h2>协议对象与模板</h2>
        <fieldset class="ag-fields" :disabled="genDlg.submitting">
        <AppFormItem label="实习学生" required>
          <AppInternshipStudentPicker v-model="genForm.internshipId" :disabled="genDlg.submitting || !batchStore.selectedBatchId" :query="{ batchId: batchStore.selectedBatchId }" placeholder="输入姓名或学号搜索" search-placeholder="按姓名 / 学号搜索" />
        </AppFormItem>
        <AppFormItem label="协议模板">
          <AppSelect v-model="genForm.templateId" :options="templateSelectOptions" :placeholder="templatesReady && !templateOptions.length ? '系统基础正文' : '自动选择适用模板'" :disabled="!genForm.internshipId || templateLoading || genDlg.submitting" />
        </AppFormItem>
        </fieldset>
        <p v-if="generationError" class="ag-error" role="alert">{{ generationError }}</p>
        <p class="ag-note">生成后为草稿，依次完成学生、企业和学校确认后生效。</p>
        <div class="ag-form-actions">
          <AppPermissionButton code="internship.agreement.manage" :allowed="canBtn('internship.agreement.manage')" variant="primary" :disabled="!generationReady" :loading="genDlg.submitting" @click="submitGenerate">生成草稿</AppPermissionButton>
          <AppButton variant="ghost" :disabled="genDlg.submitting" @click="backToList">取消</AppButton>
        </div>
      </section>
      <section class="ag-card ag-document" aria-live="polite">
        <h2>正文预览</h2>
        <LoadingState v-if="templateLoading || previewLoading" />
        <ErrorState v-else-if="templateError || previewError" :description="templateError || previewError" @retry="retryPreview" />
        <pre v-else-if="previewText">{{ previewText }}</pre>
        <p v-else-if="templatesReady && genForm.internshipId" class="ag-empty">当前没有适用的启用模板。生成时会使用系统基础正文，生成后请在协议档案核对，再下发给学生。</p>
        <p v-else class="ag-empty">先选择实习学生，再核对适用模板与正文。</p>
      </section>
    </div>
    <section v-else class="ag-card ag-list">
      <nav class="ag-tabs" aria-label="三方协议办理流程">
        <button v-for="step in flowSteps" :key="step.panel" type="button" :class="{ 'is-active': currentPanel === step.panel }" :aria-current="currentPanel === step.panel ? 'page' : undefined" @click="goPanel(step.panel)">{{ step.label }}</button>
      </nav>
      <form class="ag-toolbar" @submit.prevent="reload">
        <label class="ag-filter">搜索学生<input v-model="keyword" type="search" placeholder="学生姓名" /></label>
        <label class="ag-filter ag-status-filter">协议状态<select v-model="statusFilter"><option v-for="option in statusSelectOptions" :key="option.value" :value="option.value">{{ option.label }}</option></select></label>
        <div class="ag-filter-actions"><button class="ag-search" type="submit">查询</button><AppButton variant="ghost" @click="resetFilters">重置</AppButton></div>
        <span v-if="!loading && !error" class="ag-count">{{ total }} 份协议</span>
      </form>
      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <DataTable v-else-if="rows.length" :columns="columns" :rows="rows" row-key="id" :pagination="pagination" @page-change="onPageChange">
        <template #cell-student="{ row }"><div class="ag-cell"><RouterLink class="ag-name" :to="dossierLocation(row)">{{ row.studentName }}</RouterLink><span>{{ row.studentNo }}</span></div></template>
        <template #cell-placement="{ row }"><div class="ag-cell"><strong>{{ row.enterpriseName || '企业待确认' }}</strong><span>{{ row.positionName || '岗位待确认' }}</span></div></template>
        <template #cell-confirmation="{ row }"><div class="ag-confirm"><span v-for="party in ['student', 'enterprise', 'school']" :key="party"><small>{{ { student: '学生', enterprise: '企业', school: '学校' }[party] }}</small><AppStatusTag :type="confirmTone(row[party + 'Confirm'])">{{ row[party + 'ConfirmLabel'] || '待确认' }}</AppStatusTag></span></div></template>
        <template #cell-status="{ row }"><AppStatusTag :status="row.status">{{ row.statusLabel }}</AppStatusTag></template>
        <template #cell-actions="{ row }"><AppButton variant="ghost" size="sm" @click="openDossier(row)">{{ agreementActionLabel(row) }}</AppButton></template>
      </DataTable>
      <p v-if="!error && !loading && !rows.length" class="ag-empty">{{ currentPanel === 'archive' && appliedFilters.status === 'EFFECTIVE' ? '暂无待归档的已生效协议。查看历史归档时，请将协议状态切换为“已归档”。' : '当前条件下暂无协议，可切换办理阶段或调整筛选。' }}</p>
    </section>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, DataTable, ErrorState, LoadingState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppStatusTag, AppExportButton, AppPermissionButton, AppSelect, AppFormItem,
  AppInternshipStudentPicker } from '@/components/common'
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
  { key: 'student', title: '学生', width: '155px' },
  { key: 'placement', title: '实习企业 / 岗位' },
  { key: 'confirmation', title: '三方确认', width: '245px' },
  { key: 'status', title: '协议状态', width: '135px' },
  { key: 'actions', title: '办理', width: '110px' }
]
const PANEL_PRESETS = {
  issue: () => ({ statusFilter: 'DRAFT' }),
  confirm: () => ({ statusFilter: 'PENDING_ENTERPRISE' }),
  change: () => ({ statusFilter: '' }),
  archive: () => ({ statusFilter: 'EFFECTIVE' }),
  'student-apply': () => ({ statusFilter: 'PENDING_STUDENT' }),
  'self-apply': () => ({ statusFilter: 'PENDING_STUDENT' }),
  'position-apply': () => ({ statusFilter: 'PENDING_ENTERPRISE' }),
  'school-confirm': () => ({ statusFilter: 'PENDING_SCHOOL' }),
  'audit-ledger': () => ({ statusFilter: '' })
}

export default {
  name: 'AgreementView',
  props: { ctx: { type: Object, default: () => ({}) } },
  components: { ModulePageShell, DataTable, ErrorState, LoadingState, AppButton, AppStatusTag, AppExportButton,
    AppPermissionButton, AppSelect, AppFormItem, AppInternshipStudentPicker },
  data() {
    return {
      rows: [], total: 0, page: 1, pageSize: 20, loading: false, error: '',
      keyword: '', statusFilter: '', activePanel: 'issue', columns: COLUMNS,
      templateOptions: [],
      previewText: '',
      genForm: { internshipId: '', templateId: '' }, genDlg: { submitting: false },
      loadTicket: 0, appliedFilters: { keyword: '', status: '' },
      templateTicket: 0, previewTicket: 0, generationTicket: 0, templateLoading: false, previewLoading: false,
      templateError: '', previewError: '', generationError: '', templatesReady: false
    }
  },
  computed: {
    batchStore() { return useInternshipBatchStore() },
    workspaceReturnTo() {
      const ref = this.$route.query.returnTo
      if (typeof ref !== 'string' || !/^\/admin\/internship\/(?:archive|students\/\d+)(?:\?|$)/.test(ref)) return ''
      const target = new URL(ref, 'https://local.invalid')
      return this.batchStore.selectedBatchId && target.searchParams.get('batchId') === String(this.batchStore.selectedBatchId) ? ref : ''
    },
    scopeKey() { return `${this.ctx?.ctxKey || ''}:${this.batchStore.selectedBatchId || ''}` },
    effectiveTemplateId() { return this.genForm.templateId || (this.templateOptions.find(t => t.isDefault) || this.templateOptions[0])?.id || '' },
    generationReady() { return Boolean(this.batchStore.selectedBatchId && this.genForm.internshipId && this.templatesReady && !this.templateLoading && !this.previewLoading && !this.templateError && !this.previewError && (!this.effectiveTemplateId || this.previewText)) },
    pagination() { return { page: this.page, pageSize: this.pageSize, total: this.total } },
    flowSteps() {
      return [
        { panel: 'issue', label: '发起协议' },
        { panel: 'student-apply', label: '学生确认' },
        { panel: 'position-apply', label: '企业确认' },
        { panel: 'school-confirm', label: '学校确认' },
        { panel: 'archive', label: '归档留存' },
        { panel: 'audit-ledger', label: '全部协议' }
      ]
    },
    isGenerating() { return this.$route.name === 'internship-agreement-new' },
    currentPanel() { return ({ confirm: 'position-apply', 'self-apply': 'student-apply', change: 'audit-ledger' })[this.activePanel] || this.activePanel },
    statusSelectOptions() { return [{ value: '', label: '全部状态' }, ...Object.entries(STATUS_MAP).map(([value, label]) => ({ value, label }))] },
    templateSelectOptions() {
      return [{ value: '', label: this.templateOptions.length ? '自动选择适用模板' : '系统基础正文' }].concat(
        this.templateOptions.map((t) => ({ value: t.id, label: t.label || t.name }))
      )
    }
  },
  watch: {
    '$route.fullPath': {
      immediate: true,
      handler() {
        this.applyPanel((this.$route.query.panel || 'issue').toString())
      }
    },
    scopeKey() {
      this.page = 1
      this.resetGeneration()
      if (!this.isGenerating) this.load()
    },
    'genForm.internshipId'(id) { if (id && this.isGenerating) window.__SAAS_DIRTY_FORM_GUARD__?.markDirty(); this.refreshTemplateOptions() },
    'genForm.templateId'() { this.loadPreview() }
  },
  beforeUnmount() { this.loadTicket++; this.templateTicket++; this.previewTicket++; this.generationTicket++ },
  methods: {
    canBtn(code) { return Array.isArray(this.ctx?.permissionPatterns) && canCode(this.ctx, code) },
    applyPanel(panel) {
      const preset = PANEL_PRESETS[panel] || PANEL_PRESETS.issue
      this.activePanel = PANEL_PRESETS[panel] ? panel : 'issue'
      this.statusFilter = preset().statusFilter
      if (Object.hasOwn(this.$route.query, 'status')) this.statusFilter = STATUS_MAP[this.$route.query.status] ? this.$route.query.status : ''
      this.keyword = String(this.$route.query.keyword || '')
      this.appliedFilters = { keyword: this.keyword, status: this.statusFilter }
      const page = Number(this.$route.query.page)
      this.page = Number.isSafeInteger(page) && page > 0 ? page : 1
      if (!this.isGenerating) this.load()
    },
    goPanel(panel) {
      if (this.activePanel === panel) return
      this.$router.replace({ path: this.$route.path, query: this.batchStore.withBatchQuery({ ...this.$route.query, panel, status: undefined, page: undefined }) })
    },
    confirmTone(s) { return s === 'CONFIRMED' ? 'success' : s === 'REJECTED' ? 'danger' : 'warning' },
    agreementActionLabel(row) {
      return ({ DRAFT: '继续下发', PENDING_STUDENT: '跟进学生', PENDING_ENTERPRISE: '跟进企业', PENDING_SCHOOL: '学校确认', EFFECTIVE: '办理归档' })[row.status] || '查看档案'
    },
    goTemplates() { this.$router.push({ path: '/admin/internship/agreement-templates', query: this.listQuery() }) },
    dossierLocation(row) { return { path: `/admin/internship/agreements/${row.id}`, query: this.listQuery() } },
    openDossier(row) { this.$router.push(this.dossierLocation(row)) },
    listQuery(filters = this.appliedFilters) { const query = { panel: this.activePanel, status: filters.status, keyword: filters.keyword || undefined, page: this.page > 1 ? this.page : undefined }; if (this.workspaceReturnTo) query.returnTo = this.workspaceReturnTo; return this.batchStore.withBatchQuery(query) },
    backToList() { return this.$router.push({ path: '/admin/internship/agreements', query: this.listQuery() }) },
    exportFn() {
      if (!this.batchStore.selectedBatchId) return Promise.resolve({ code: 1, message: '请先选择批次' })
      return agreementApi.exportAgreements({ ...this.appliedFilters, batchId: this.batchStore.selectedBatchId })
    },
    onExported(data) { toast.success(`已导出 ${data.rowCount} 条（水印 + 导出留痕）`) },
    reload() { this.page = 1; this.updateListLocation({ keyword: this.keyword.trim(), status: this.statusFilter }) },
    resetFilters() { this.keyword = ''; this.statusFilter = (PANEL_PRESETS[this.activePanel] || PANEL_PRESETS.issue)().statusFilter; this.reload() },
    onPageChange(p) { this.page = p; this.updateListLocation() },
    updateListLocation(filters = this.appliedFilters) { const to = { path: '/admin/internship/agreements', query: this.listQuery(filters) }; if (this.$router.resolve(to).fullPath === this.$route.fullPath) this.load(); else this.$router.replace(to) },
    async load() {
      const ticket = ++this.loadTicket
      if (!this.batchStore.selectedBatchId) {
        this.loading = false; this.error = '请先选择批次'; this.rows = []; this.total = 0
        return
      }
      this.loading = true; this.error = ''
      const params = { page: this.page, pageSize: this.pageSize, ...this.appliedFilters, batchId: this.batchStore.selectedBatchId }
      try {
        const res = await agreementApi.getAgreements(params)
        if (ticket !== this.loadTicket) return
        if (res.code !== 0) throw new Error(res.message || '协议加载失败，请重试')
        this.rows = res.data.list; this.total = res.data.total
      } catch (error) {
        if (ticket === this.loadTicket) { this.error = error.message || '协议加载失败，请重试'; this.rows = []; this.total = 0 }
      } finally { if (ticket === this.loadTicket) this.loading = false }
    },
    // 选择器远程搜索（岗位实习模块适配层，后端裁定关键字与数据范围）
    async openGenerate() {
      // 先选真实实习学生，再按该学生的学院/专业/年级/批次加载可用模板。
      this.resetGeneration()
      this.$router.push({ path: '/admin/internship/agreements/new', query: this.listQuery() })
    },
    resetGeneration() {
      this.templateTicket++; this.previewTicket++; this.generationTicket++
      this.genForm = { internshipId: '', templateId: '' }; this.genDlg.submitting = false
      this.templateOptions = []; this.previewText = ''; this.templatesReady = false
      this.templateLoading = false; this.previewLoading = false
      this.templateError = ''; this.previewError = ''; this.generationError = ''
    },
    retryPreview() { return this.templateError ? this.refreshTemplateOptions() : this.loadPreview() },
    async refreshTemplateOptions() {
      const ticket = ++this.templateTicket, scope = this.scopeKey, id = this.genForm.internshipId
      this.previewTicket++
      this.previewText = ''; this.previewError = ''; this.previewLoading = false
      this.genForm.templateId = ''
      this.templateOptions = []; this.templatesReady = false; this.templateError = ''; this.generationError = ''
      this.templateLoading = false
      if (!id || !this.batchStore.selectedBatchId) return
      this.templateLoading = true
      try {
        const res = await agreementTemplateApi.getEnabledOptions({ batchId: this.batchStore.selectedBatchId, internshipId: id })
        if (ticket !== this.templateTicket || scope !== this.scopeKey || id !== this.genForm.internshipId) return
        if (res.code !== 0) throw new Error(res.message || '加载适用协议模板失败，请重试')
        this.templateOptions = res.data || []; this.templatesReady = true
        await this.loadPreview()
      } catch (error) {
        if (ticket === this.templateTicket && scope === this.scopeKey) this.templateError = error.message || '适用模板加载失败，请重试'
      } finally {
        if (ticket === this.templateTicket) this.templateLoading = false
      }
    },
    async loadPreview() {
      const ticket = ++this.previewTicket, scope = this.scopeKey, id = this.genForm.internshipId, tplId = this.effectiveTemplateId
      this.previewText = ''; this.previewError = ''; this.previewLoading = false
      if (!id || !this.templatesReady || !tplId) return
      this.previewLoading = true
      try {
        const res = await agreementTemplateApi.previewTemplate(tplId, { internshipId: id })
        if (ticket !== this.previewTicket || scope !== this.scopeKey || id !== this.genForm.internshipId || tplId !== this.effectiveTemplateId) return
        if (res.code !== 0 || !res.data?.renderedBody) throw new Error(res.message || '正文预览暂时不可用，请重试')
        this.previewText = res.data.renderedBody
      } catch (error) {
        if (ticket === this.previewTicket && scope === this.scopeKey) this.previewError = error.message || '正文预览加载失败，请重试'
      } finally {
        if (ticket === this.previewTicket) this.previewLoading = false
      }
    },
    async submitGenerate() {
      if (this.genDlg.submitting || !this.generationReady || !this.canBtn('internship.agreement.manage')) return
      const ticket = ++this.generationTicket, scope = this.scopeKey
      this.genDlg.submitting = true
      this.generationError = ''
      const payload = { internshipId: this.genForm.internshipId }
      if (this.effectiveTemplateId) payload.templateId = this.effectiveTemplateId
      try {
        const res = await agreementApi.generate(payload)
        if (ticket !== this.generationTicket || scope !== this.scopeKey) return
        if (res.code !== 0 || !res.data?.id) throw new Error(res.message || '未能确认生成结果，请到协议列表核对后重试')
        window.__SAAS_DIRTY_FORM_GUARD__?.markSaved()
        toast.success('已生成协议草稿，核对后可下发给学生确认')
        this.$router.push(this.dossierLocation(res.data))
      } catch (error) {
        if (ticket === this.generationTicket && scope === this.scopeKey) this.generationError = error.message || '生成失败，请重试'
      } finally {
        if (ticket === this.generationTicket) this.genDlg.submitting = false
      }
    },
    // 详情、企业签署、下发/确认/归档/驳回/作废、电子签、PDF 套打：全部收口至三方协议档案页 AgreementDetailView
  }
}
</script>

<style scoped>
.ag-card { border: 1px solid var(--card-b, #e2e8f0); border-radius: 12px; background: var(--card, #fff); min-width: 0; }
.ag-list { overflow: hidden; }
.ag-tabs { display: flex; gap: 22px; overflow-x: auto; padding: 0 20px; border-bottom: 1px solid var(--card-b, #e2e8f0); }
.ag-tabs button { flex: none; padding: 17px 0 14px; border: 0; border-bottom: 3px solid transparent; background: transparent; font: inherit; font-size: 14px; color: var(--t2, #536178); cursor: pointer; }
.ag-tabs button:hover, .ag-tabs button.is-active { color: var(--pri, #315fba); }
.ag-tabs button.is-active { border-bottom-color: var(--pri, #315fba); font-weight: 600; }
.ag-tabs button:focus-visible { outline: 2px solid var(--pri, #315fba); outline-offset: -4px; }
.ag-toolbar { display: flex; align-items: end; flex-wrap: wrap; gap: 12px; padding: 16px 20px; }
.ag-filter { display: grid; gap: 7px; color: var(--t3); font-size: 12px; flex: 1 1 180px; }
.ag-filter input, .ag-filter select { box-sizing: border-box; width: 100%; min-width: 0; height: 36px; border: 1px solid var(--card-b); border-radius: 6px; background: var(--card); color: var(--t1); padding: 0 10px; font: inherit; font-size: 13px; }
.ag-filter input:focus-visible, .ag-filter select:focus-visible { outline: 2px solid var(--pri); outline-offset: 2px; }
.ag-status-filter { flex: 0 1 160px; }
.ag-filter-actions { display: flex; gap: 6px; }
.ag-search { height: 36px; padding: 0 18px; border: 0; border-radius: 6px; background: var(--pri); color: white; font: inherit; font-size: 13px; cursor: pointer; }
.ag-name { font-size: 13px; font-weight: 600; color: var(--t1); text-decoration: none; }
.ag-name:hover { color: var(--pri); text-decoration: underline; }
.ag-list :deep(.dt) { border: 0; border-radius: 0; box-shadow: none; }
.ag-list :deep(.dt__table) { min-width: 900px; }
.ag-fields { border: 0; margin: 0; padding: 0; min-width: 0; }
.ag-error { font-size: 13px; line-height: 1.7; color: var(--danger-700, #b91c1c); background: var(--danger-50, #fef2f2); padding: 12px; border-radius: 6px; }
.ag-count { margin-left: auto; color: var(--t3, #758297); font-size: 13px; }
.ag-cell { display: grid; gap: 5px; line-height: 1.5; overflow-wrap: anywhere; }
.ag-cell strong { font-size: 13px; font-weight: 500; color: var(--t1, #27364b); }.ag-cell > span { font-size: 12px; color: var(--t3, #758297); }
.ag-confirm { display: flex; gap: 10px; }.ag-confirm > span { display: grid; justify-items: start; gap: 5px; }.ag-confirm small { color: var(--t3, #758297); }
.ag-empty { margin: 0; padding: 48px 24px; text-align: center; color: var(--t3, #758297); font-size: 13px; line-height: 1.8; }
.ag-generate { display: grid; grid-template-columns: minmax(290px, .8fr) minmax(0, 1.4fr); align-items: start; gap: 20px; }
.ag-form, .ag-document { padding: 24px; }.ag-card h2 { margin: 0 0 22px; font-size: 16px; color: var(--t1, #27364b); }
.ag-note { font-size: 13px; line-height: 1.8; color: var(--t3, #758297); }.ag-form-actions { display: flex; gap: 12px; margin-top: 24px; padding-top: 20px; border-top: 1px solid var(--card-b, #e2e8f0); }
.ag-document pre { white-space: pre-wrap; overflow-wrap: anywhere; font-family: inherit; font-size: 14px; line-height: 1.9; margin: 0; }
@media (max-width: 1100px) { .ag-generate { grid-template-columns: 1fr; }.ag-tabs { gap: 16px; } }
</style>
