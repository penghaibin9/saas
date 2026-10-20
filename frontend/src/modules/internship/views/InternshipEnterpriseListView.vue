<template>
  <ModulePageShell
    class="enterprise-list"
    :title="activePanel === 'qualification' ? '企业准入' : '企业库'"
    :subtitle="pageSubtitle"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppExportButton :export-fn="exportFn" :has-permission="can('exportEnterprises')">{{ appliedFilters.blacklist ? '导出台账（不限黑名单）' : '导出企业台账' }}</AppExportButton>
      <ModuleToolbar :actions="toolbarActions" @action="onToolbar" />
    </template>

    <div class="mp-stack">
      <p v-if="receipt" class="ie-receipt" role="status">{{ receipt }}</p>
      <AdvancedFilter v-model="filters" :fields="filterFields" @search="search" @reset="reset" />
      <div class="ie-list-head">
        <span>{{ loading ? '正在查询企业…' : error ? '企业列表暂不可用' : `筛选结果 ${total} 家` }}</span>
        <AppButton variant="ghost" size="sm" :disabled="loading" @click="load">刷新列表</AppButton>
      </div>
      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" title="当前筛选下没有企业" :description="activePanel === 'qualification' ? '可切换合作状态查看已审核企业，或重置筛选。' : '可调整筛选；有维护权限时，也可新增或导入企业。'" />
      <DataTable v-else :columns="columns" :rows="rows" row-key="id" :pagination="{ page, pageSize, total }" @page-change="turnPage">
        <template #cell-company="{ row }">
          <RouterLink class="ie-company" :to="detailLink(row)">{{ row.name }}</RouterLink>
          <div class="mp-cell-sub">{{ row.creditCode || '信用代码未登记' }}</div>
          <div class="mp-cell-sub">{{ row.industry || '行业未登记' }} · {{ row.region || '地区未登记' }}</div>
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
          <div class="ie-actions">
            <RouterLink class="mp-link" :to="detailLink(row, 'coop')">{{ row.coopStatus === 'PENDING' ? '核验准入' : '合作与资质' }}</RouterLink>
            <RouterLink v-if="can('editEnterprise') && row.coopStatus !== 'ARCHIVED'" class="mp-link" :to="editLink(row)">编辑资料</RouterLink>
          </div>
        </template>
      </DataTable>
      <details class="ie-stats" :open="statsOpen" @toggle="toggleStats">
        <summary>本校企业概况 <span>全校企业库，非当前批次或筛选结果</span></summary>
        <div v-if="statsLoading" class="mp-note">正在读取概况…</div>
        <div v-else-if="statsError" role="alert" class="ie-stats-error">{{ statsError }} <AppButton variant="ghost" size="sm" @click="loadStats">重试</AppButton></div>
        <template v-else-if="entStats">
          <dl class="ie-stats__grid"><div><dt>企业总数</dt><dd>{{ entStats.total ?? '—' }}</dd></div><div><dt>已标记黑名单</dt><dd>{{ entStats.blacklistCount ?? '—' }}</dd></div><div v-for="s in entStats.byCoopStatus || []" :key="s.status"><dt>{{ s.status === 'BLACKLIST' ? '黑名单状态' : s.label }}</dt><dd>{{ s.count ?? '—' }}</dd></div></dl>
          <p v-if="entStats.byIndustry?.length" class="mp-note">行业分布：<span v-for="(item, index) in entStats.byIndustry" :key="item.industry">{{ index ? ' · ' : '' }}{{ item.industry }} {{ item.count }}</span></p>
        </template>
      </details>
    </div>

    <!-- 新增 / 编辑：独立表单页 /admin/internship/enterprises/new 与 /:id/edit（EnterpriseFormView） -->

    <!-- Excel 导入（正式 xlsx · 公共底座） -->
    <AppExcelImportDrawer
      v-if="can('importEnterprises')"
      :key="scopeEpoch"
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

  </ModulePageShell>
</template>

<script>
/** 企业库负责检索与导入导出；准入审核和合作变更统一在企业详情中办理。 */
import { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppExportButton, AppStatusTag } from '@/components/common'
import { AppButton } from '@/components/ui'
import { AppExcelImportDrawer } from '@/components/common/excel'
import { internshipApi } from '@/modules/internship/api/internship.api'
import { toast } from '@/utils/toast'
import { canCode } from '@/modules/internship/composables/permission'

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

export default {
  name: 'InternshipEnterpriseListView',
  components: { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, AppButton, AppStatusTag, AppExportButton, AppExcelImportDrawer, LoadingState, ErrorState, EmptyState },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      internshipApi,
      loading: true, error: '', activePanel: 'list',
      rows: [], total: 0, page: 1, pageSize: 20,
      listSequence: 0, statsSequence: 0, scopeEpoch: 0, receipt: '',
      statsOpen: false, statsLoading: false, statsError: '',
      filters: EMPTY_FILTERS(),
      appliedFilters: EMPTY_FILTERS(),
      importVisible: false,
      entStats: null,
      columns: [
        { key: 'company', title: '企业信息', width: '300px' },
        { key: 'contact', title: '联系人 / 电话' },
        { key: 'coopStatus', title: '合作状态' },
        { key: 'qualification', title: '资质' },
        { key: 'internCount', title: '实习生', width: '80px' },
        { key: 'actions', title: '操作', width: '160px' }
      ]
    }
  },
  computed: {
    perms() { return this.ctx.permissionActions || {} },
    coopStatusOptions() { return this.ctx.statusOptions?.coopStatus || [] },
    industryOptions() { return this.ctx.statusOptions?.enterpriseIndustry || [] },
    filterFields() {
      return [
        { key: 'keyword', label: '关键词', type: 'text', placeholder: '企业名称 / 信用代码 / 联系人' },
        { key: 'coopStatus', label: '合作状态', type: 'select', options: this.coopStatusOptions },
        { key: 'industry', label: '行业', type: 'select', options: this.industryOptions },
        { key: 'region', label: '地区', type: 'text', placeholder: '省/市' },
        { key: 'blacklist', label: '黑名单', type: 'select', options: [{ value: 'true', label: '仅黑名单' }, { value: 'false', label: '排除黑名单' }] }
      ]
    },
    toolbarActions() {
      return [
        { key: 'create', label: '新增企业', variant: 'primary', permission: 'createEnterprise' },
        { key: 'import', label: '导入企业', permission: 'importEnterprises' }
      ].filter(a => this.perms[a.permission]?.visible !== false && this.perms[a.permission])
        .map(a => ({ ...a, disabled: !this.can(a.permission), disabledReason: this.reason(a.permission) }))
    },
    pageSubtitle() {
      return this.activePanel === 'qualification' ? '进入企业核验资料与考察记录，再完成准入审核。' : '本校共享企业库，核对合作状态与资质，继续企业对接。'
    },
    listQuery() {
      const query = { panel: this.activePanel, page: String(this.page) }
      if (typeof this.$route.query.batchId === 'string') query.batchId = this.$route.query.batchId
      for (const [key, value] of Object.entries(this.appliedFilters)) query[key] = value
      return query
    }
  },
  watch: {
    '$route.query': {
      immediate: true,
      deep: true,
      handler() { this.restoreQuery(); this.load() }
    },
    ctx: { deep: true, handler() {
      this.scopeEpoch++; this.listSequence++; this.statsSequence++
      this.entStats = null; this.statsError = ''; this.statsLoading = false
      this.importVisible = false; this.receipt = ''; this.rows = []; this.total = 0
      this.restoreQuery(); this.load()
      if (this.statsOpen) this.loadStats()
    } }
  },
  beforeUnmount() { this.scopeEpoch++; this.listSequence++; this.statsSequence++ },
  methods: {
    restoreQuery() {
      const q = this.$route.query
      this.activePanel = Object.hasOwn(ENTERPRISE_PANEL_PRESETS, q.panel) ? q.panel : 'list'
      const filters = ENTERPRISE_PANEL_PRESETS[this.activePanel]()
      for (const key of Object.keys(filters)) if (typeof q[key] === 'string') filters[key] = q[key]
      if (!['true', 'false'].includes(filters.blacklist)) filters.blacklist = ''
      this.filters = filters; this.appliedFilters = { ...filters }
      this.page = Math.min(1000000, Math.max(1, Number.parseInt(q.page, 10) || 1))
      if (this.activePanel === 'stats') { this.statsOpen = true; if (!this.entStats && !this.statsLoading) this.loadStats() }
    },
    navigate() {
      const query = this.listQuery
      if (JSON.stringify(query) === JSON.stringify(this.$route.query)) return this.load()
      return this.$router.replace({ path: '/admin/internship/enterprises', query })
    },
    toggleStats(event) {
      this.statsOpen = event.target.open
      if (this.statsOpen && !this.entStats && !this.statsLoading && !this.statsError) this.loadStats()
    },
    async loadStats() {
      const sequence = ++this.statsSequence, scope = this.scopeEpoch
      this.entStats = null; this.statsError = ''
      if (!canCode(this.ctx, 'internship.enterprise.view')) { this.statsError = '当前账号没有查看企业库的权限'; this.statsLoading = false; return }
      this.statsLoading = true
      try {
        const res = await internshipApi.getEnterpriseStats()
        if (sequence !== this.statsSequence || scope !== this.scopeEpoch) return
        if (res.code === 0) this.entStats = res.data
        else this.statsError = res.message || '企业概况读取失败'
      } catch { if (sequence === this.statsSequence && scope === this.scopeEpoch) this.statsError = '企业概况读取失败，请重试' }
      finally { if (sequence === this.statsSequence && scope === this.scopeEpoch) this.statsLoading = false }
    },
    can(key) { const p = this.perms[key]; return !!(p && p.allowed) },
    reason(key) { const p = this.perms[key]; return p && !p.allowed ? p.reason : '' },
    async load() {
      const sequence = ++this.listSequence, scope = this.scopeEpoch
      this.loading = true; this.error = ''
      this.rows = []; this.total = 0
      if (!canCode(this.ctx, 'internship.enterprise.view')) { this.error = '当前账号没有查看企业库的权限'; this.loading = false; return }
      const p = { ...this.appliedFilters, page: this.page, pageSize: this.pageSize }
      if (p.blacklist === '') delete p.blacklist
      else p.blacklist = p.blacklist === 'true'
      try {
        const res = await internshipApi.getEnterprises(p)
        if (sequence !== this.listSequence || scope !== this.scopeEpoch) return
        if (res.code === 0) { this.rows = res.data.list; this.total = res.data.total }
        else this.error = res.message || '企业列表读取失败'
      } catch { if (sequence === this.listSequence && scope === this.scopeEpoch) this.error = '企业列表读取失败，请重试' }
      finally { if (sequence === this.listSequence && scope === this.scopeEpoch) this.loading = false }
    },
    search() { this.page = 1; this.appliedFilters = { ...this.filters }; return this.navigate() },
    reset() { this.filters = ENTERPRISE_PANEL_PRESETS[this.activePanel](); return this.search() },
    turnPage(p) { this.page = p; return this.navigate() },
    onToolbar(key) {
      if (key === 'create') { if (!this.can('createEnterprise')) return toast.error(this.reason('createEnterprise')); this.$router.push({ path: '/admin/internship/enterprises/new', query: this.listQuery }) }
      if (key === 'import') { if (!this.can('importEnterprises')) return toast.error(this.reason('importEnterprises')); this.importVisible = true }
    },
    detailLink(row, section = 'basic') { return { path: `/admin/internship/enterprises/${String(row.id)}`, query: { ...this.listQuery, section } } },
    editLink(row) { return { path: `/admin/internship/enterprises/${String(row.id)}/edit`, query: this.listQuery } },
    async exportFn() {
      if (!this.can('exportEnterprises')) return { code: 1, message: this.reason('exportEnterprises') || '当前账号没有导出权限' }
      const scope = this.scopeEpoch
      const { keyword, coopStatus, industry, region } = this.appliedFilters
      const res = await internshipApi.exportEnterprises({ keyword, coopStatus, industry, region })
      return scope === this.scopeEpoch ? res : { code: 1, message: '身份已切换，请重新导出' }
    },
    onImported(data) {
      this.receipt = `已导入 ${data.created ?? 0} 家企业；新企业为待审核状态，可进入企业准入继续核验。`
      this.load(); this.entStats = null
      if (this.statsOpen) this.loadStats()
    },

  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';

.ie-bl { margin-left: var(--space-2); font-size: 11px; color: var(--danger, #dc2626); }
.enterprise-list :deep(.mps__head) { padding: 0; border: 0; border-radius: 0; background: none; box-shadow: none; }
.enterprise-list :deep(.mps__head::before) { display: none; }
.enterprise-list :deep(.dt__table) { min-width: 930px; }
.ie-list-head { display: flex; align-items: center; justify-content: space-between; gap: 16px; font-size: 13px; color: var(--text-secondary); }
.ie-company { color: var(--text-primary); text-decoration: none; font-weight: 600; line-height: 1.5; }
.ie-company:hover { color: var(--primary-500); text-decoration: underline; }
.ie-company:focus-visible, .ie-actions a:focus-visible { outline: 2px solid var(--primary-500); outline-offset: 3px; border-radius: 3px; }
.ie-actions { display: flex; flex-wrap: wrap; gap: 8px 14px; }
.ie-stats { border-top: 1px solid var(--border-base); padding: 14px 0; }
.ie-stats summary { cursor: pointer; font-size: 13px; font-weight: 600; }
.ie-stats summary span { display: inline-block; margin-left: 12px; color: var(--text-secondary); font-size: 12px; font-weight: 400; }
.ie-stats__grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(100px, 1fr)); gap: 16px; margin: 20px 0; }
.ie-stats__grid dt { color: var(--text-secondary); font-size: 12px; }
.ie-stats__grid dd { margin: 6px 0 0; font-size: 22px; font-weight: 600; }
.ie-stats-error { margin-top: 12px; color: var(--danger); }
.ie-receipt { padding: 12px 16px; margin: 0; border: 1px solid var(--border-base); border-radius: 8px; background: var(--bg-section); }
</style>
