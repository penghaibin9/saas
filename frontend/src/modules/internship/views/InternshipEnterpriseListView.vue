<template>
  <ModulePageShell
    title="企业岗位库"
    :subtitle="pageSubtitle"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppExportButton :export-fn="exportFn" :has-permission="can('exportEnterprises')">⬇ 导出 Excel 台账</AppExportButton>
      <ModuleToolbar :actions="toolbarActions" @action="onToolbar" />
    </template>

    <div class="mp-stack">
      <ModuleSummaryStrip :metrics="summaryMetrics" :note="summaryMetrics.length ? '' : '暂无统计口径'" />
      <section v-if="activePanel === 'stats' && entStats" class="mp-card ie-stats">
        <div class="mp-card__head"><span class="mp-card__title">企业库统计</span></div>
        <div class="mp-card__body">
          <div class="ie-stats__grid">
            <AppMetricCard title="企业总数" :value="entStats.total" />
            <AppMetricCard title="黑名单" :value="entStats.blacklistCount" :accent="entStats.blacklistCount ? 'risk' : 'primary'" />
            <AppMetricCard v-for="s in entStats.byCoopStatus" :key="s.status" :title="s.label" :value="s.count" />
          </div>
          <div v-if="entStats.byIndustry?.length" class="ie-stats__ind">
            <span class="mp-note">行业分布：</span>
            <span v-for="(ind, i) in entStats.byIndustry" :key="ind.industry">{{ ind.industry }} {{ ind.count }}<template v-if="i < entStats.byIndustry.length - 1"> · </template></span>
          </div>
        </div>
      </section>

      <AdvancedFilter v-model="filters" :fields="filterFields" @search="search" @reset="reset" />

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" title="暂无企业" description="可通过「＋ 新增企业」或「导入」补充企业库" />
      <DataTable v-else :columns="columns" :rows="rows" row-key="id" :pagination="{ page, pageSize, total }" @page-change="turnPage">
        <template #cell-company="{ row }">
          <div class="mp-cell-main">{{ row.name }}</div>
          <div class="mp-cell-sub">{{ row.creditCode || '无信用代码' }} · {{ row.sourceLabel }}</div>
        </template>
        <template #cell-contact="{ row }">
          <template v-if="row.contactPerson">
            <div class="mp-cell-main">{{ row.contactPerson }}</div>
            <div class="mp-cell-sub">{{ row.contactPhoneMasked || '未登记' }}</div>
          </template>
          <span v-else class="mp-note">未登记</span>
        </template>
        <template #cell-coopStatus="{ row }">
          <AppStatusTag :type="row.coopStatusTone" dot>{{ row.coopStatusLabel }}</AppStatusTag>
          <span v-if="row.blacklist" class="ie-bl">黑名单</span>
        </template>
        <template #cell-qualification="{ row }">
          <AppStatusTag :type="row.qualificationStatus === 'PASSED' ? 'success' : (row.qualificationStatus === 'FAILED' ? 'danger' : 'default')">{{ row.qualificationLabel }}</AppStatusTag>
        </template>
        <template #cell-actions="{ row }">
          <TableActionColumn :actions="rowActions(row)" @action="(key) => onRowAction(key, row)" />
        </template>
      </DataTable>
    </div>

    <!-- 新增 / 编辑：独立表单页 /admin/internship/enterprises/new 与 /:id/edit（EnterpriseFormView） -->

    <!-- Excel 导入（正式 xlsx · 公共底座） -->
    <AppExcelImportDrawer
      v-model:visible="importVisible"
      title="导入企业"
      template-name="企业导入模板.xlsx"
      :required-fields="['企业名称', '统一社会信用代码', '行业', '地区']"
      :preview-fields="['name', 'creditCode', 'industry', 'region', 'contactPerson']"
      :download-template-fn="() => internshipApi.downloadEnterpriseTemplate()"
      :upload-fn="(file) => internshipApi.importEnterprisesXlsx(file)"
      :confirm-fn="({ rows }) => internshipApi.importEnterprisesConfirm(rows)"
      :download-errors-fn="({ rows, errors }) => internshipApi.downloadEnterpriseImportErrors(rows, errors)"
      @imported="onImported"
    />

    <AppConfirmDialog
      v-model:visible="confirm.visible"
      :title="confirm.title"
      :message="confirm.message"
      :type="confirm.type"
      :confirm-text="confirm.confirmText"
      :require-reason="confirm.requireReason"
      :reason-label="confirm.reasonLabel"
      :submitting="submitting"
      @confirm="onConfirm"
    />
  </ModulePageShell>
</template>

<script>
/** 企业库列表（/admin/internship/enterprises）：筛选 + 审核/暂停/黑名单状态机 + 真导入导出 + 脱敏；新增/编辑走独立表单页 EnterpriseFormView。 */
import { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppExportButton, AppStatusTag, AppMetricCard } from '@/components/common'
import { AppExcelImportDrawer } from '@/components/common/excel'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import { TableActionColumn } from '@/modules/internship/components'
import ModuleSummaryStrip from './components/ModuleSummaryStrip.vue'
import { internshipApi } from '@/modules/internship/api/internship.api'
import { toast } from '@/utils/toast'

const EMPTY_FILTERS = () => ({ keyword: '', coopStatus: '', industry: '', region: '', blacklist: '' })
const ENTERPRISE_PANEL_PRESETS = {
  list: () => EMPTY_FILTERS(),
  detail: () => EMPTY_FILTERS(),
  contacts: () => EMPTY_FILTERS(),
  mentor: () => EMPTY_FILTERS(),
  qualification: () => ({ ...EMPTY_FILTERS(), coopStatus: 'PENDING' }),
  blacklist: () => ({ ...EMPTY_FILTERS(), blacklist: 'true' }),
  archive: () => ({ ...EMPTY_FILTERS(), coopStatus: 'ARCHIVED' }),
  stats: () => EMPTY_FILTERS(),
  cooperation: () => ({ ...EMPTY_FILTERS(), coopStatus: 'ACTIVE' }),
  positions: () => EMPTY_FILTERS()
}
const ENTERPRISE_PANEL_HINTS = {
  list: '合作企业主档 · 联系电话默认脱敏',
  detail: '点击行「详情」进入企业详情页',
  contacts: '联系人在企业详情页维护',
  mentor: '企业导师在企业详情页维护',
  qualification: '待审核企业 · 行内可「审核」资质',
  blacklist: '黑名单企业 · 可「移出黑名单」',
  archive: '已归档企业台账',
  stats: '企业库统计 · 合作状态/行业/黑名单汇总',
  cooperation: '合作中企业',
  positions: '关联岗位请前往岗位库筛选企业'
}

export default {
  name: 'InternshipEnterpriseListView',
  components: { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, AppStatusTag, AppMetricCard, AppExportButton, AppExcelImportDrawer, LoadingState, ErrorState, EmptyState, AppConfirmDialog, TableActionColumn, ModuleSummaryStrip },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      internshipApi,
      loading: true, error: '', submitting: false, activePanel: 'list',
      rows: [], total: 0, page: 1, pageSize: 10,
      filters: EMPTY_FILTERS(),
      importVisible: false,
      confirm: { visible: false, title: '', message: '', type: 'primary', confirmText: '确认', requireReason: false, reasonLabel: '原因', action: null, row: null, extra: null },
      entStats: null,
      columns: [
        { key: 'company', title: '企业 / 信用代码' },
        { key: 'industry', title: '行业' },
        { key: 'region', title: '地区' },
        { key: 'contact', title: '联系人 / 电话' },
        { key: 'coopStatus', title: '合作状态' },
        { key: 'qualification', title: '资质' },
        { key: 'internCount', title: '实习生' },
        { key: 'actions', title: '操作', width: '260px' }
      ]
    }
  },
  computed: {
    perms() { return this.ctx.permissionActions || {} },
    coopStatusOptions() { return this.ctx.statusOptions.coopStatus || [] },
    industryOptions() { return this.ctx.statusOptions.enterpriseIndustry || [] },
    filterFields() {
      return [
        { key: 'keyword', label: '关键词', type: 'text', placeholder: '企业名称 / 信用代码 / 联系人' },
        { key: 'coopStatus', label: '合作状态', type: 'select', options: this.coopStatusOptions },
        { key: 'industry', label: '行业', type: 'select', options: this.industryOptions },
        { key: 'region', label: '地区', type: 'text', placeholder: '省/市' }
      ]
    },
    toolbarActions() {
      const pa = this.perms
      return [
        { key: 'create', label: '＋ 新增企业', variant: 'primary' },
        { key: 'import', label: '导入' }
      ].filter((a) => !pa[a.key + 'Enterprise'] || pa[a.key + 'Enterprise'].visible !== false)
        .map((a) => {
          const p = pa[({ create: 'createEnterprise', import: 'importEnterprises' })[a.key]]
          return p ? { ...a, disabled: !p.allowed, disabledReason: p.reason } : a
        })
    },
    pageSubtitle() {
      const hint = ENTERPRISE_PANEL_HINTS[this.activePanel] || ENTERPRISE_PANEL_HINTS.list
      return `维护合作企业和实习岗位，检查企业资质、岗位容量和专业匹配情况 · 共 ${this.total} 家 · ${hint}`
    },
    summaryMetrics() {
      const s = this.entStats
      if (!s) return []
      const m = [{ label: '合作企业', value: s.total }]
      if (s.blacklistCount != null) m.push({ label: '黑名单', value: s.blacklistCount, tone: s.blacklistCount ? 'warn' : undefined })
      const pending = (s.byCoopStatus || []).find((x) => x.status === 'PENDING')
      if (pending) m.push({ label: '待审核企业', value: pending.count, tone: pending.count ? 'warn' : undefined })
      return m
    }
  },
  watch: {
    '$route.query.panel': {
      immediate: true,
      handler(panel) {
        this.applyPanel((panel || 'list').toString())
      }
    }
  },
  methods: {
    applyPanel(panel) {
      const key = ENTERPRISE_PANEL_PRESETS[panel] ? panel : 'list'
      this.activePanel = key
      this.filters = (ENTERPRISE_PANEL_PRESETS[key] || ENTERPRISE_PANEL_PRESETS.list)()
      this.page = 1
      // 摘要条常驻使用企业统计，进入统计面板时强制刷新，其余面板复用已加载数据
      if (key === 'stats' || !this.entStats) this.loadStats()
      this.load()
    },
    async loadStats() {
      const res = await internshipApi.getEnterpriseStats()
      if (res.code === 0) this.entStats = res.data
    },
    can(key) { const p = this.perms[key]; return !!(p && p.allowed) },
    reason(key) { const p = this.perms[key]; return p && !p.allowed ? p.reason : '' },
    async load() {
      this.loading = true; this.error = ''
      const p = { ...this.filters, page: this.page, pageSize: this.pageSize }
      if (p.blacklist === '') delete p.blacklist
      else if (p.blacklist === 'true') p.blacklist = true
      const res = await internshipApi.getEnterprises(p)
      if (res.code === 0) { this.rows = res.data.list; this.total = res.data.total } else this.error = res.message
      this.loading = false
    },
    search() { this.page = 1; this.load() },
    reset() { this.filters = EMPTY_FILTERS(); this.page = 1; this.load() },
    turnPage(p) { this.page = p; this.load() },
    onToolbar(key) {
      if (key === 'create') { if (!this.can('createEnterprise')) return toast.error(this.reason('createEnterprise')); this.$router.push('/admin/internship/enterprises/new') }
      if (key === 'import') { if (!this.can('importEnterprises')) return toast.error(this.reason('importEnterprises')); this.importVisible = true }
    },
    goEdit(row) {
      if (!this.can('editEnterprise')) return toast.error(this.reason('editEnterprise'))
      this.$router.push(`/admin/internship/enterprises/${row.id}/edit`)
    },
    rowActions(row) {
      const actions = [
        { key: 'detail', label: '详情' },
        { key: 'edit', label: '编辑', disabled: !this.can('editEnterprise'), disabledReason: this.reason('editEnterprise') }
      ]
      if (row.coopStatus === 'PENDING') {
        actions.push({ key: 'review', label: '审核', disabled: !this.can('reviewEnterprise'), disabledReason: this.reason('reviewEnterprise') })
      } else if (row.coopStatus === 'ACTIVE') {
        actions.push({ key: 'coopSuspend', label: '暂停' })
      } else if (row.coopStatus === 'SUSPENDED') {
        actions.push({ key: 'coopResume', label: '恢复' })
      }
      if (!row.blacklist && row.coopStatus !== 'ARCHIVED') {
        actions.push({ key: 'blacklistOn', label: '拉黑', danger: true, disabled: !this.can('blacklistEnterprise'), disabledReason: this.reason('blacklistEnterprise') })
      }
      if (row.blacklist) {
        actions.push({ key: 'blacklistOff', label: '移出黑名单', disabled: !this.can('blacklistEnterprise'), disabledReason: this.reason('blacklistEnterprise') })
      }
      return actions
    },
    onRowAction(key, row) {
      if (key === 'detail') return this.$router.push('/admin/internship/enterprises/' + row.id)
      if (key === 'edit') return this.goEdit(row)
      if (key === 'review') return this.askReview(row)
      if (key === 'coopSuspend') return this.askCoop(row, 'SUSPEND')
      if (key === 'coopResume') return this.askCoop(row, 'RESUME')
      if (key === 'blacklistOn') return this.askBlacklist(row, true)
      if (key === 'blacklistOff') return this.askBlacklist(row, false)
    },
    exportFn() {
      return internshipApi.exportEnterprises({ ...this.filters })
    },
    onImported(data) {
      toast.success(`已导入 ${data.created || 0} 家（初始待审核）`)
      this.load()
    },
    askReview(row) {
      if (!this.can('reviewEnterprise')) return toast.error(this.reason('reviewEnterprise'))
      this.confirm = { visible: true, title: '企业资质审核', message: `确认「${row.name}」资质核验结果？通过→合作中，驳回→已驳回。`, type: 'primary', confirmText: '通过（资质合格）', requireReason: false, reasonLabel: '审核意见', action: 'REVIEW_APPROVE', row, extra: null }
    },
    askCoop(row, action) {
      const map = { SUSPEND: { t: '暂停合作', c: '确认暂停', type: 'warning' }, RESUME: { t: '恢复合作', c: '确认恢复', type: 'primary' } }
      const m = map[action]
      this.confirm = { visible: true, title: m.t, message: `确认对「${row.name}」执行「${m.t}」？`, type: m.type, confirmText: m.c, requireReason: false, action: 'COOP_' + action, row, extra: null }
    },
    askBlacklist(row, on) {
      if (!this.can('blacklistEnterprise')) return toast.error(this.reason('blacklistEnterprise'))
      this.confirm = { visible: true, title: on ? '加入黑名单' : '移出黑名单', message: on ? `确认将「${row.name}」拉黑？拉黑后不再向学生推荐。` : `确认将「${row.name}」移出黑名单？恢复为合作中。`, type: on ? 'danger' : 'primary', confirmText: on ? '确认拉黑' : '确认移出', requireReason: on, reasonLabel: '拉黑原因', action: on ? 'BLACKLIST_ON' : 'BLACKLIST_OFF', row, extra: null }
    },
    async onConfirm({ reason } = {}) {
      const { action, row } = this.confirm
      this.submitting = true
      try {
        let res
        if (action === 'REVIEW_APPROVE') res = await internshipApi.reviewEnterprise(row.id, { action: 'APPROVE', comment: reason || '' })
        else if (action.startsWith('COOP_')) res = await internshipApi.setEnterpriseCooperation(row.id, { action: action.slice(5), reason: reason || '' })
        else if (action === 'BLACKLIST_ON') res = await internshipApi.setEnterpriseBlacklist(row.id, { on: true, reason: reason || '' })
        else if (action === 'BLACKLIST_OFF') res = await internshipApi.setEnterpriseBlacklist(row.id, { on: false })
        if (res && res.code === 0) { toast.success('已更新并写入留痕'); this.confirm.visible = false; this.load() }
        else if (res) toast.error(res.message)
      } finally { this.submitting = false }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';

.ie-bl { margin-left: var(--space-2); font-size: 11px; color: var(--danger, #dc2626); }
.ie-stats__grid { display: flex; flex-wrap: wrap; gap: var(--space-3); }
.ie-stats__grid > * { flex: 1 1 160px; }
.ie-stats__ind { margin-top: var(--space-3); font-size: 13px; }
</style>
