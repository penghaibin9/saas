<template>
  <ModulePageShell title="申请与协议办理" subtitle="审核学生实习申请，并完成协议发起、确认、变更和归档 · 三方协议 · 协议生成 · 学生/企业/学校确认 · 签署扫描件留痕"
    role-name="指导教师 / 管理员" :data-scope-name="scopeHint" :watermark="false">
    <template #actions>
      <AppPermissionButton code="internship.agreement.manage" :allowed="canBtn('internship.agreement.manage')" variant="primary" @click="openGenerate">＋ 生成协议</AppPermissionButton>
      <AppButton variant="ghost" @click="goTemplates">协议模板</AppButton>
      <AppExportButton :export-fn="exportFn" @exported="onExported">⬇ 导出 Excel 台账</AppExportButton>
    </template>

    <section v-if="!error" class="ag-now" aria-label="当前协议办理对象">
      <header class="ag-now__head">
        <div>
          <span class="ag-now__eyebrow">AGREEMENT NOW</span>
          <h2>当前阶段先办这 {{ priorityRows.length }} 份协议</h2>
          <p>按服务端当前页顺序展示；实际下发、确认、驳回与归档仍在协议档案页完成。</p>
        </div>
        <span>{{ activeStepLabel }}</span>
      </header>
      <div v-if="loading" class="ag-now__state">正在读取当前协议对象…</div>
      <div v-else-if="priorityRows.length" class="ag-now__list">
        <article v-for="row in priorityRows" :key="row.id" class="ag-now__item">
          <div class="ag-now__identity">
            <small>{{ row.studentNo }} · {{ row.statusLabel }}</small>
            <strong>{{ row.studentName }} · {{ row.enterpriseName || '企业待确认' }}</strong>
            <span>{{ row.positionName || '岗位待确认' }}</span>
          </div>
          <dl>
            <div><dt>为什么到这里</dt><dd>{{ agreementWhy(row) }}</dd></div>
            <div><dt>最近状态</dt><dd>{{ agreementRecent(row) }}</dd></div>
            <div><dt>下一责任人</dt><dd>{{ agreementNextActor(row) }}</dd></div>
          </dl>
          <AppButton variant="primary" size="sm" @click="openDossier(row)">{{ agreementActionLabel(row) }} →</AppButton>
        </article>
      </div>
      <div v-else class="ag-now__state">当前阶段没有待办理协议，可切换流程步骤查看其他状态。</div>
    </section>

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
        <AppStatusTag :type="row.esignStatus === 'INTERNAL_CONFIRMED' ? 'success' : row.esignStatus === 'PENDING' ? 'warning' : 'default'">
          {{ row.esignStatus === 'INTERNAL_CONFIRMED' ? '内部确认完成' : row.esignStatus === 'PENDING' ? '确认中' : '未发起' }}
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
    <AppDrawer :visible="genDlg.visible" title="生成三方协议" mode="modal" size="medium" @update:visible="genDlg.visible = $event">
      <AppFormItem label="实习学生" required>
        <AppInternshipStudentPicker
          v-model="genForm.internshipId"
          :query="{ batchId: batchStore.selectedBatchId }"
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
  { key: 'schoolConfirm', title: '学校' }, { key: 'esignStatus', title: '内部确认' },
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
    priorityRows() { return this.rows.slice(0, 3) },
    activeStepLabel() { return this.flowSteps.find((step) => step.panel === this.activePanel)?.label || '协议办理' },
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
      this.templateOptions = []
      this.load()
    },
    'genForm.internshipId'() { this.refreshTemplateOptions() },
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
    agreementWhy(row) {
      return ({
        DRAFT: '协议草稿已生成，等待学校下发', PENDING_STUDENT: '协议已下发，等待学生确认',
        PENDING_ENTERPRISE: '学生已确认，等待企业确认与签署材料', PENDING_SCHOOL: '企业已确认，等待学校复核',
        EFFECTIVE: '三方确认已完成，等待归档留存', REJECTED: '上一确认方已驳回，需要查看原因后修正',
        VOIDED: '协议已作废，仅保留审计档案', ARCHIVED: '协议已归档，可查看完整证据链'
      })[row.status] || '协议状态已变化，需要进入档案核对服务端事实'
    },
    agreementRecent(row) {
      const when = row.updatedAt ? String(row.updatedAt).replace('T', ' ').replace('Z', '').slice(0, 16) : '当前版本'
      return `${when} · ${row.statusLabel || STATUS_MAP[row.status] || '状态待确认'} · v${row.version ?? '-'}`
    },
    agreementNextActor(row) {
      return ({
        DRAFT: '学校协议经办人', PENDING_STUDENT: '学生本人', PENDING_ENTERPRISE: '企业联系人',
        PENDING_SCHOOL: '学校协议经办人', EFFECTIVE: '档案经办人', REJECTED: '协议发起人',
        VOIDED: '无需继续办理', ARCHIVED: '无需继续办理'
      })[row.status] || '协议经办人'
    },
    agreementActionLabel(row) {
      return ({ DRAFT: '继续下发', PENDING_STUDENT: '跟进学生', PENDING_ENTERPRISE: '跟进企业', PENDING_SCHOOL: '学校确认', EFFECTIVE: '办理归档' })[row.status] || '查看档案'
    },
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
      // 先选真实实习学生，再按该学生的学院/专业/年级/批次加载可用模板。
      this.genForm = { internshipId: '', templateId: '' }
      this.templateOptions = []
      this.previewText = ''
      this.genDlg.visible = true
    },
    async refreshTemplateOptions() {
      this.previewText = ''
      this.genForm.templateId = ''
      this.templateOptions = []
      if (!this.genForm.internshipId) return
      const res = await agreementTemplateApi.getEnabledOptions({
        batchId: this.batchStore.selectedBatchId,
        internshipId: this.genForm.internshipId
      })
      if (res.code !== 0) {
        toast.error(res.message || '加载适用协议模板失败')
        return
      }
      this.templateOptions = res.data || []
      await this.loadPreview()
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
      const effectiveTemplateId = this.genForm.templateId ||
        (this.templateOptions.find((t) => t.isDefault) || this.templateOptions[0])?.id
      if (effectiveTemplateId) payload.templateId = effectiveTemplateId
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
.ag-now { overflow: hidden; margin-bottom: var(--space-3); border: 1px solid color-mix(in srgb, var(--pri) 24%, var(--card-b)); border-radius: 14px; background: var(--card); box-shadow: 0 14px 38px rgba(30,64,175,.08); }
.ag-now__head { display: flex; align-items: flex-end; justify-content: space-between; gap: 18px; padding: 16px 18px; background: linear-gradient(120deg, var(--pri-bg), #fff 72%); }
.ag-now__head > div { display: grid; gap: 3px; }.ag-now__head h2 { margin: 0; color: var(--t1); font-size: 17px; }.ag-now__head p { margin: 0; color: var(--t3); font-size: 12px; }
.ag-now__head > span { padding: 4px 9px; border-radius: 999px; background: #fff; color: var(--pri); font-size: 12px; font-weight: 700; }.ag-now__eyebrow { color: var(--pri); font-size: 10px; font-weight: 800; letter-spacing: .12em; }
.ag-now__list { display: grid; gap: 10px; padding: 14px; }.ag-now__item { display: grid; grid-template-columns: minmax(170px,.9fr) minmax(0,2fr) auto; align-items: center; gap: 14px; padding: 12px 14px; border: 1px solid var(--card-b); border-left: 4px solid var(--warning-500,#f59e0b); border-radius: 10px; }
.ag-now__identity { display: grid; gap: 3px; min-width: 0; }.ag-now__identity small { color: var(--pri); font-weight: 700; }.ag-now__identity strong,.ag-now__identity span { overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }.ag-now__identity span { color: var(--t3); font-size: 12px; }
.ag-now__item dl { display: grid; grid-template-columns: 1.25fr 1fr .8fr; gap: 8px; margin: 0; }.ag-now__item dl div { min-width: 0; padding: 8px 10px; border-radius: 8px; background: var(--fill-2,#f8fafc); }.ag-now__item dt { margin-bottom: 3px; color: var(--t3); font-size: 10px; font-weight: 700; }.ag-now__item dd { margin: 0; color: var(--t2); font-size: 12px; line-height: 1.45; }.ag-now__state { padding: 24px; color: var(--t3); font-size: 13px; text-align: center; }
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
@media (max-width: 900px) { .ag-now__item { grid-template-columns: 1fr; } .ag-now__item dl { grid-template-columns: 1fr; } .ag-now__head { align-items: flex-start; flex-direction: column; } }
</style>
