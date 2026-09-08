<template>
  <ModulePageShell class="ix-batch-list" :title="pageTitle" :subtitle="pageSubtitle" watermark-purpose="实习批次管理">
    <template #actions>
      <AppExportButton v-if="canExport" :export-fn="exportFn">导出台账</AppExportButton>
      <AppButton v-if="canManage" variant="primary" @click="openCreate">新建批次</AppButton>
    </template>
    <section class="ibl-workspace" aria-label="实习批次列表">
      <div class="ibl-context">
        <span>授权范围内的实习批次</span>
        <span v-if="!loading && !error">共 {{ total }} 个批次</span>
      </div>
      <AdvancedFilter v-model="filters" :fields="filterFields" @search="search" @reset="reset" />
      <LoadingState v-if="loading" />
      <ErrorState v-else-if="error" :description="error" @retry="load" />
      <EmptyState v-else-if="!rows.length" title="没有找到实习批次" :description="emptyDescription" />
      <DataTable v-else :columns="tableColumns" :rows="rows" row-key="id"
        :pagination="{ page, pageSize, total }" @page-change="turnPage">
        <template #cell-batch="{ row }">
          <RouterLink class="ibl-name" :to="detailLocation(row)">{{ row.batchName }}</RouterLink>
          <div class="ibl-secondary">{{ row.batchNo }}<span v-if="row.academicYear"> · {{ row.academicYear }} {{ row.term }}</span></div>
        </template>
        <template #cell-range="{ row }">{{ dateShort(row.startDate) }} 至 {{ dateShort(row.endDate) }}</template>
        <template #cell-count="{ row }">
          <strong>{{ row.actualCount ?? '—' }}</strong><span class="ibl-secondary"> / {{ row.plannedCount ?? '—' }}</span>
        </template>
        <template #cell-status="{ row }">
          <AppStatusTag :type="statusTagType[row.status] || 'default'" dot>{{ row.statusLabel }}</AppStatusTag>
        </template>
        <template #cell-actions="{ row }">
          <TableActionColumn :actions="rowActions(row)" @action="(key) => onRowAction(key, row)" />
        </template>
      </DataTable>
    </section>
    <p class="ibl-note">草稿批次可配置范围与规则；预览并冻结参与名单后启用。批次启用不代表学生已具备上岗条件。</p>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, AdvancedFilter, DataTable, EmptyState, LoadingState, ErrorState } from '@/components/business'
import { AppStatusTag, AppExportButton } from '@/components/common'
import { AppButton } from '@/components/ui'
import { TableActionColumn } from '@/modules/internship/components'
import { internshipApi } from '@/modules/internship/api/internship.api'
import { formatDate } from '@/utils/dateUtils'
import { matchPermission } from '@/config/navPlan'
import { withInternshipBatch } from '../navigation.js'

const PANELS = {
  list: { title: '批次管理', hint: '建立实习周期，确定参与名单，再启用本轮实习。', status: '' },
  participants: { title: '参与学生配置', hint: '选择草稿批次，圈定范围并预览名单，确认后启用。', status: 'DRAFT' },
  configuration: { title: '阶段与规则配置', hint: '选择草稿批次，维护实习阶段与本轮业务规则。', status: 'DRAFT' },
  export: { title: '实习批次归档台账', hint: '检索已归档批次，查看记录或导出台账。', status: 'ARCHIVED' }
}
const STATUS_OPTIONS = [
  { value: 'DRAFT', label: '草稿' }, { value: 'RUNNING', label: '进行中' },
  { value: 'CLOSED', label: '已结束' }, { value: 'ARCHIVED', label: '已归档' },
  { value: 'VOIDED', label: '已作废' }
]

export default {
  name: 'InternshipBatchListView',
  components: { ModulePageShell, AdvancedFilter, DataTable, EmptyState, LoadingState, ErrorState,
    AppStatusTag, AppExportButton, AppButton, TableActionColumn },
  data() {
    return { ctx: null, loading: true, error: '', rows: [], total: 0, page: 1, pageSize: 10,
      filters: { keyword: '', status: '' }, appliedFilters: { keyword: '', status: '' }, loadSequence: 0,
      statusTagType: { DRAFT: 'default', RUNNING: 'success', CLOSED: 'info', ARCHIVED: 'default', VOIDED: 'danger' } }
  },
  computed: {
    activePanel() {
      const raw = String(this.$route.query.panel || 'list')
      return ['timeline', 'rules'].includes(raw) ? 'configuration' : (PANELS[raw] ? raw : 'list')
    },
    pageTitle() { return PANELS[this.activePanel].title },
    pageSubtitle() { return PANELS[this.activePanel].hint },
    canManage() { return this.ctx?.permissionActions?.createBatch?.allowed === true },
    canExport() { return Array.isArray(this.ctx?.permissionPatterns) && matchPermission(this.ctx.permissionPatterns, 'internship.batch.export') },
    emptyDescription() {
      if (this.appliedFilters.keyword || this.appliedFilters.status) return '可调整关键词或状态，重新查询。'
      return this.canManage ? '从“新建批次”开始，保存后继续配置参与名单。' : '当前授权范围内暂无批次，请联系实习管理员。'
    },
    filterFields() { return [
      { key: 'keyword', label: '搜索批次', type: 'text', placeholder: '批次名称或编号' },
      { key: 'status', label: '批次状态', type: 'select', options: STATUS_OPTIONS }
    ] },
    tableColumns() { return [
      { key: 'batch', title: '实习批次' }, { key: 'range', title: '实习周期' },
      { key: 'count', title: '实际 / 计划人数' }, { key: 'status', title: '状态' },
      { key: 'actions', title: '操作' }
    ] }
  },
  watch: {
    '$route.query': { immediate: true, handler(query) {
      if (this.$route.path !== '/admin/internship/batches') return
      this.filters = { keyword: String(query.keyword || ''), status: typeof query.status === 'string' ? query.status : PANELS[this.activePanel].status }
      this.appliedFilters = { ...this.filters }
      const page = Number(query.page)
      this.page = Number.isSafeInteger(page) && page > 0 ? page : 1
      this.load()
    } }
  },
  beforeUnmount() { this.loadSequence++ },
  methods: {
    async load() {
      const sequence = ++this.loadSequence
      this.loading = true
      this.error = ''
      try {
        const [res, context] = await Promise.all([
          internshipApi.getBatches({ ...this.appliedFilters, page: this.page, pageSize: this.pageSize }),
          this.ctx ? Promise.resolve({ code: 0, data: this.ctx }) : internshipApi.getContext()
        ])
        if (sequence !== this.loadSequence) return
        if (context.code !== 0) throw new Error(context.message || '无法获取当前身份，请重试')
        this.ctx = context.data
        if (res.code !== 0) throw new Error(res.message || '批次加载失败，请重试')
        this.rows = res.data?.list || []
        this.total = Number(res.data?.total || 0)
      } catch (e) {
        if (sequence === this.loadSequence) {
          this.error = e.message || '批次加载失败，请重试'
          this.rows = []; this.total = 0; this.ctx = null
        }
      } finally {
        if (sequence === this.loadSequence) this.loading = false
      }
    },
    updateQuery(page, filters = this.appliedFilters) {
      const query = { ...this.$route.query, keyword: filters.keyword.trim(), status: filters.status, page: String(page) }
      const location = { path: '/admin/internship/batches', query }
      if (this.$router.resolve(location).fullPath === this.$route.fullPath) return this.load()
      return this.$router.replace(location)
    },
    search() { this.updateQuery(1, this.filters) },
    reset() { this.filters = { keyword: '', status: '' }; this.updateQuery(1, this.filters) },
    turnPage(page) { this.updateQuery(page) },
    dateShort(value) { return formatDate(value, '—') },
    exportFn() { return internshipApi.exportBatches({ ...this.appliedFilters }) },
    openCreate() {
      this.$router.push({ path: '/admin/internship/batches/new', query: { returnTo: this.$route.fullPath } })
    },
    detailLocation(row) {
      const location = withInternshipBatch('/admin/internship/batches/' + row.id, row.id)
      location.query.returnTo = this.$route.fullPath
      if (this.activePanel === 'participants') location.query.setup = 'participants'
      if (this.activePanel === 'configuration') location.query.setup = 'rules'
      return location
    },
    rowActions(row) {
      const actions = [{ key: 'detail', label: '查看详情' }]
      if (row.status === 'DRAFT' && this.canManage) actions.push({ key: 'participants', label: '配置名单' })
      return actions
    },
    onRowAction(key, row) {
      if (key === 'participants' && this.canManage) {
        const location = this.detailLocation(row)
        location.query.setup = 'participants'
        this.$router.push(location)
      } else this.$router.push(this.detailLocation(row))
    }
  }
}
</script>

<style scoped>
.ibl-workspace { background: var(--card); border: 1px solid var(--card-b); border-radius: 8px; overflow: hidden; }
.ibl-context { display: flex; justify-content: space-between; gap: 12px; padding: 13px 16px 0; color: var(--t3); font-size: 12px; }
.ibl-workspace :deep(.af) { border: 0; border-radius: 0; box-shadow: none; background: transparent; margin: 0; }
.ibl-workspace :deep(.dt) { border: 0; border-radius: 0; box-shadow: none; }
.ibl-workspace :deep(.dt__table) { min-width: 680px; }
.ibl-name { color: var(--t1); font-weight: 600; text-decoration: none; display: inline-block; padding: 4px 0; }
.ibl-name:hover { color: var(--pri); text-decoration: underline; }
.ibl-secondary { color: var(--t3); font-size: 12px; margin-top: 3px; }
.ibl-note { margin: 0; color: var(--t3); font-size: 12px; line-height: 1.7; }
</style>
