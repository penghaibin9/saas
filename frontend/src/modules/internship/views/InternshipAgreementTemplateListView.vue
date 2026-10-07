<template>
  <ModulePageShell
    class="atl" title="协议模板库"
    :subtitle="pageSubtitle"
  >
    <template #actions>
      <ModuleToolbar :actions="toolbarActions" @action="onToolbar" />
      <AppExportButton :export-fn="exportFn" @exported="onExported">导出台账</AppExportButton>
      <AppButton variant="ghost" @click="backToAgreements">返回三方协议</AppButton>
    </template>

    <section class="atl-list" aria-label="协议模板列表">
      <AdvancedFilter v-model="filters" :fields="filterFields" @search="search" @reset="reset" />
      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" title="暂无协议模板" description="调整筛选条件，或新建适用的协议模板。"><template #actions><AppButton variant="primary" @click="openCreate">新建模板</AppButton></template></EmptyState>
      <DataTable v-else :columns="columns" :rows="rows" row-key="id" :pagination="{ page, pageSize, total }" @page-change="turnPage">
        <template #cell-name="{ row }">
          <div class="mp-cell-main"><RouterLink class="atl-name" :to="detailLocation(row)">{{ row.name }}</RouterLink><span v-if="row.isDefault" class="at-default">默认</span></div>
          <div class="mp-cell-sub">{{ row.category || '未分类' }} · {{ row.version }}</div>
        </template>
        <template #cell-scope="{ row }">
          <span class="mp-cell-sub">{{ row.scopeSummary }}</span>
        </template>
        <template #cell-status="{ row }">
          <AppStatusTag :type="row.statusTone" dot>{{ row.statusLabel }}</AppStatusTag>
        </template>
        <template #cell-actions="{ row }">
          <button class="mp-link" @click="openDetail(row)">查看与配置</button>
          <button v-if="row.status !== 'ARCHIVED'" class="mp-link" style="margin-left: var(--space-2)" @click="openEdit(row)">编辑</button>
        </template>
      </DataTable>
    </section>
  </ModulePageShell>
</template>

<script>
/**
 * 实习协议模板库（/admin/internship/agreement-templates）：筛选 / 台账导出 / 启用 / 停用 / 归档 / 设默认。
 * 新建/编辑入口跳独立页 AgreementTemplateFormView（/agreement-templates/new、/agreement-templates/:id/edit）；
 * 详情跳 AgreementTemplateDetailView（/agreement-templates/:id）。
 */
import { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppStatusTag, AppExportButton } from '@/components/common'
import { agreementTemplateApi } from '@/modules/internship/api/agreement-template.api'
import { toast } from '@/utils/toast'
import { AppButton } from '@/components/ui'

const STATUS_OPTS = [
  { value: 'DRAFT', label: '草稿' },
  { value: 'ENABLED', label: '启用中' },
  { value: 'DISABLED', label: '已停用' },
  { value: 'ARCHIVED', label: '已归档' }
]
const CATEGORY_OPTS = ['三方协议', '顶岗实习协议', '安全责任书', '实习承诺书', '保密协议']
const EMPTY_FILTERS = () => ({ keyword: '', status: '', category: '' })

export default {
  name: 'InternshipAgreementTemplateListView',
  components: { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, AppStatusTag, AppExportButton, LoadingState, ErrorState, EmptyState, AppButton },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true, error: '', loadTicket: 0, appliedFilters: EMPTY_FILTERS(),
      rows: [], total: 0, page: 1, pageSize: 10, filters: EMPTY_FILTERS(),
      columns: [
        { key: 'name', title: '模板 / 类型·版本' },
        { key: 'scope', title: '适用范围' },
        { key: 'status', title: '状态' },
        { key: 'actions', title: '操作', width: '150px' }
      ]
    }
  },
  computed: {
    filterFields() {
      return [
        { key: 'keyword', label: '关键词', type: 'text', placeholder: '模板名称 / 类型' },
        { key: 'status', label: '状态', type: 'select', options: STATUS_OPTS },
        { key: 'category', label: '类型', type: 'select', options: CATEGORY_OPTS.map((c) => ({ value: c, label: c })) }
      ]
    },
    toolbarActions() {
      return [{ key: 'create', label: '新建模板', variant: 'primary' }]
    },
    pageSubtitle() {
      return '管理协议正文与适用范围，启用后供生成协议时选用。'
    }
  },
  watch: { '$route.fullPath': { immediate: true, handler() {
    const q = this.$route.query
    this.filters = { keyword: String(q.templateKeyword || ''), status: String(q.templateStatus || ''), category: String(q.templateCategory || '') }
    this.appliedFilters = { ...this.filters }
    const page = Number(q.templatePage); this.page = Number.isSafeInteger(page) && page > 0 ? page : 1
    this.load()
  } } },
  beforeUnmount() { this.loadTicket++ },
  methods: {
    templateQuery(filters = this.appliedFilters) { return { ...this.$route.query, templateKeyword: filters.keyword || undefined, templateStatus: filters.status || undefined, templateCategory: filters.category || undefined, templatePage: this.page > 1 ? this.page : undefined } },
    backToAgreements() { const query = { ...this.$route.query }; for (const key of Object.keys(query)) if (key.startsWith('template')) delete query[key]; this.$router.push({ path: '/admin/internship/agreements', query }) },
    updateLocation(filters = this.appliedFilters) { const to = { path: this.$route.path, query: this.templateQuery(filters) }; if (this.$router.resolve(to).fullPath === this.$route.fullPath) this.load(); else this.$router.replace(to) },
    async load() {
      const ticket = ++this.loadTicket
      this.loading = true; this.error = ''
      try {
        const res = await agreementTemplateApi.getTemplates({ ...this.appliedFilters, page: this.page, pageSize: this.pageSize })
        if (ticket !== this.loadTicket) return
        if (res.code !== 0) throw new Error(res.message || '模板加载失败，请重试')
        this.rows = res.data.list; this.total = res.data.total
      } catch (error) {
        if (ticket === this.loadTicket) { this.error = error.message || '模板加载失败，请重试'; this.rows = []; this.total = 0 }
      } finally { if (ticket === this.loadTicket) this.loading = false }
    },
    search() { this.page = 1; this.updateLocation({ ...this.filters, keyword: this.filters.keyword.trim() }) },
    reset() { this.filters = EMPTY_FILTERS(); this.page = 1; this.updateLocation(this.filters) },
    turnPage(p) { this.page = p; this.updateLocation() },
    exportFn() { return agreementTemplateApi.exportTemplates({ ...this.appliedFilters }) },
    onExported(data) { toast.success(`已导出 ${data.rowCount} 个模板（已写审计）`) },
    onToolbar(key) {
      if (key === 'create') this.openCreate()
    },
    openCreate() {
      this.$router.push({ path: '/admin/internship/agreement-templates/new', query: this.templateQuery() })
    },
    openEdit(row) {
      this.$router.push({ path: `/admin/internship/agreement-templates/${row.id}/edit`, query: this.templateQuery() })
    },
    openDetail(row) {
      this.$router.push(this.detailLocation(row))
    },
    detailLocation(row) { return { path: `/admin/internship/agreement-templates/${row.id}`, query: this.templateQuery() } }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.at-default { margin-left: var(--space-2); font-size: 11px; padding: 1px 6px; border-radius: 6px; background: var(--success-50, #ecfdf5); color: var(--success, #16a34a); }
.mp-link--danger { color: var(--danger, #dc2626); }
.atl-list { min-width: 0; background: var(--card); border: 1px solid var(--card-b); border-radius: 8px; overflow: hidden; }
.atl-list :deep(.af), .atl-list :deep(.dt) { border: 0; box-shadow: none; border-radius: 0; margin: 0; }
.atl-list :deep(.dt__table) { min-width: 720px; }
.atl-name { color: var(--t1); text-decoration: none; }
.atl-name:hover { color: var(--pri); text-decoration: underline; }
.atl :deep(.dt__td) { padding-top: 16px; padding-bottom: 16px; }.atl :deep(.dt__td:last-child) { line-height: 2.4; }.atl :deep(.mp-cell-main) { font-weight: 600; }.atl :deep(.mp-cell-sub) { margin-top: 5px; line-height: 1.6; }
</style>
