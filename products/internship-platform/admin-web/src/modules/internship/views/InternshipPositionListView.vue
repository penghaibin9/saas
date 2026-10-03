<template>
  <ModulePageShell
    class="position-list"
    :title="activePanel === 'stats' ? '全校岗位概况' : '岗位库'"
    :subtitle="pageSubtitle"
  >
    <template #actions>
      <AppExportButton v-if="activePanel !== 'stats' && canExport" :export-fn="exportFn">{{ appliedFilters.risk ? '导出台账（不限风险）' : '导出岗位台账' }}</AppExportButton>
      <ModuleToolbar :actions="toolbarActions" @action="onToolbar" />
    </template>

    <dl v-if="activePanel === 'stats' && !loading && !error && posStats" class="ip-metrics">
      <div><dt>岗位总数</dt><dd>{{ posStats.total ?? '—' }}</dd></div>
      <div><dt>有风险标记</dt><dd>{{ posStats.riskCount ?? '—' }}</dd></div>
      <div><dt>已上架容量</dt><dd>{{ posStats.publishedCapacity ?? '—' }}</dd></div>
      <div><dt>已上架已分配</dt><dd>{{ posStats.publishedAllocated ?? '—' }}</dd></div>
      <div><dt>容量利用率</dt><dd>{{ posStats.publishedCapacity > 0 ? `${posStats.capacityUtilization ?? '—'}%` : '无上架容量' }}</dd></div>
      <div><dt>不限专业（已上架）</dt><dd>{{ posStats.unlimitedMajorCount ?? '—' }}</dd></div>
    </dl>

    <div class="mp-stack">
      <p v-if="receipt" class="ip-receipt" role="status">{{ receipt }}</p>
      <form v-if="activePanel !== 'stats'" class="ip-filters" @submit.prevent="search">
        <label class="ip-keyword">岗位 / 企业 / 专业<input v-model="filters.keyword" type="search" placeholder="输入名称或专业关键词" /></label>
        <label>岗位状态<select v-model="filters.status"><option value="">全部状态</option><option v-for="s in statusOpts" :key="s.value" :value="s.value">{{ s.label }}</option></select></label>
        <div class="ip-enterprise"><span id="position-company-label">所属企业</span><AppInternshipEnterprisePicker :key="scopeEpoch" v-model="filters.companyId" aria-labelledby="position-company-label" :options="enterpriseFallbackOptions" :disabled="!canEnterprise" placeholder="全部企业" search-placeholder="输入企业名称搜索" :clearable="true" /><small v-if="!canEnterprise">无企业库查询权限，可使用企业关键词查询岗位。<button v-if="filters.companyId" type="button" class="mp-link" @click="filters.companyId = ''">清除企业筛选</button></small></div>
        <label>风险标记<select v-model="filters.risk"><option value="">全部</option><option value="true">仅风险岗位</option><option value="false">排除风险岗位</option></select></label>
        <div class="ip-filter-actions"><button type="submit" class="ip-search">查询</button><AppButton variant="ghost" @click="reset">重置</AppButton></div>
      </form>
      <div v-if="activePanel !== 'stats'" class="ip-list-head"><span>{{ loading ? '正在查询岗位…' : error ? '岗位列表暂不可用' : `当前筛选 ${total} 个岗位` }}</span><div><AppButton variant="ghost" size="sm" :disabled="loading" @click="load">刷新列表</AppButton><AppButton variant="ghost" size="sm" @click="showPanel('stats')">全校概况</AppButton></div></div>
      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <template v-else-if="activePanel === 'stats' && posStats">
        <div class="ip-block">
          <h3 class="ip-h">按状态</h3>
          <DataTable :columns="statStatusCols" :rows="posStats.byStatus || []" row-key="status" :pagination="null" />
        </div>
        <div class="ip-block">
          <h3 class="ip-h">按专业要求（已上架）</h3>
          <EmptyState v-if="!(posStats.byMajor || []).length" title="暂无已上架岗位" description="上架岗位后可按专业要求聚合统计" />
          <DataTable v-else :columns="statMajorCols" :rows="posStats.byMajor || []" row-key="major" :pagination="null" />
        </div>
      </template>
      <EmptyState v-else-if="!rows.length" title="暂无符合条件的岗位" :description="canManage ? '可调整筛选，或为当前批次新增、导入岗位。' : '可调整筛选，或等待负责人准备当前批次岗位。'" />
      <DataTable v-else class="ip-position-table" :columns="columns" :rows="rows" row-key="id" :pagination="{ page, pageSize, total }" @page-change="turnPage">
        <template #cell-position="{ row }">
          <RouterLink class="ip-title" :to="positionLink(row.id)">{{ row.title }}</RouterLink><span v-if="row.riskFlag" class="ip-risk">风险岗位</span>
          <div class="mp-cell-sub">{{ row.companyName }}</div>
        </template>
        <template #cell-require="{ row }">
          <div class="mp-cell-sub">{{ row.majorRequirement || '不限专业' }}</div>
          <div class="mp-cell-sub">{{ row.gradeRequirement || '不限年级' }}</div>
        </template>
        <template #cell-capacity="{ row }"><strong>{{ row.allocatedCount ?? '—' }}</strong> / {{ row.headcount ?? '—' }}<div class="mp-cell-sub">{{ row.remaining == null ? '剩余名额待核对' : `剩余 ${row.remaining} 人` }}</div></template>
        <template #cell-status="{ row }">
          <AppStatusTag :type="row.statusTone" dot>{{ row.statusLabel }}</AppStatusTag>
        </template>
        <template #cell-actions="{ row }">
          <div class="ip-row-actions"><RouterLink class="mp-link" :to="positionLink(row.id, '', 'publish')">{{ canPublish || canManage ? '核验与发布' : '查看发布条件' }}</RouterLink><RouterLink v-if="canManage && row.status !== 'ARCHIVED'" class="mp-link" :to="positionLink(row.id, '/edit')">编辑资料</RouterLink></div>
        </template>
      </DataTable>
    </div>

    <!-- 新增 / 编辑：独立表单页 /admin/internship/positions/new 与 /:id/edit（PositionFormView） -->

    <AppExcelImportDrawer v-if="canManage"
      :key="scopeEpoch"
      v-model:visible="importVisible"
      title="导入岗位"
      template-name="岗位导入模板.xlsx"
      :required-fields="['岗位名称', '关联企业']"
      :preview-fields="['title', 'company', 'major', 'location', 'headcount']"
      :download-template-fn="() => positionApi.downloadPositionTemplate()"
      :upload-fn="(file) => positionApi.importPositionsXlsx(file)"
      :confirm-fn="({ rows }) => positionApi.importPositionsConfirm(rows)"
      :download-errors-fn="({ rows, errors }) => positionApi.downloadPositionImportErrors(rows, errors)"
      @imported="onImported"
    />


  </ModulePageShell>
</template>

<script>
/** 岗位库列表（/admin/internship/positions）：筛选 + 状态机 + 风险标记 + 真导入导出；新增/编辑走独立表单页 PositionFormView。 */
import { ModulePageShell, ModuleToolbar, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppExportButton, AppStatusTag, AppInternshipEnterprisePicker } from '@/components/common'
import { AppButton } from '@/components/ui'
import { AppExcelImportDrawer } from '@/components/common/excel'
import { canCode } from '@/modules/internship/composables/permission'
import { positionApi } from '@/modules/internship/api/position.api'
import { POSITION_STATUS } from '@/modules/internship/constants/position.constants'

const EMPTY_FILTERS = () => ({ keyword: '', status: '', companyId: '', risk: '' })
const POSITION_PANEL_PRESETS = {
  list: () => EMPTY_FILTERS(),
  detail: () => EMPTY_FILTERS(),
  requirement: () => EMPTY_FILTERS(),
  capacity: () => ({ ...EMPTY_FILTERS(), status: 'PUBLISHED' }),
  publish: () => ({ ...EMPTY_FILTERS(), status: 'PENDING' }),
  offline: () => ({ ...EMPTY_FILTERS(), status: 'PUBLISHED' }),
  risk: () => ({ ...EMPTY_FILTERS(), risk: 'true' }),
  archive: () => ({ ...EMPTY_FILTERS(), status: 'ARCHIVED' }),
  stats: () => EMPTY_FILTERS()
}
const POSITION_PANEL_HINTS = {
  list: '岗位关联企业 · 黑名单/停用企业不可上架',
  detail: '点击行「详情」进入岗位详情页',
  requirement: '关注「专业/年级」列 · 新建/编辑可维护要求',
  capacity: '已上架岗位 · 关注「已分配/容量」列',
  publish: '待审核岗位 · 进入「发布管理」核对并上架',
  offline: '已上架岗位 · 进入「发布管理」下架',
  risk: '仅风险岗位 · 进入「发布管理」核对风险',
  archive: '已归档岗位台账',
  stats: '岗位库真实统计 · 状态分布 / 专业分布 / 容量利用率'
}

export default {
  name: 'InternshipPositionListView',
  components: { ModulePageShell, ModuleToolbar, DataTable, AppButton, AppStatusTag, AppInternshipEnterprisePicker, AppExportButton, AppExcelImportDrawer, LoadingState, ErrorState, EmptyState },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      positionApi,
      loading: true, error: '', activePanel: 'list', loadSequence: 0, scopeEpoch: 0, receipt: '',
      rows: [], total: 0, page: 1, pageSize: 20, filters: EMPTY_FILTERS(), appliedFilters: EMPTY_FILTERS(),
      posStats: null,
      importVisible: false,
      columns: [
        { key: 'position', title: '岗位 / 企业' },
        { key: 'require', title: '专业 / 年级' },
        { key: 'workLocation', title: '工作地点' },
        { key: 'salaryRange', title: '薪资' },
        { key: 'capacity', title: '已分配/容量' },
        { key: 'status', title: '状态' },
        { key: 'actions', title: '操作', width: '180px' }
      ],
      statStatusCols: [{ key: 'label', title: '状态' }, { key: 'count', title: '数量' }],
      statMajorCols: [
        { key: 'major', title: '专业要求' },
        { key: 'count', title: '岗位数' },
        { key: 'capacity', title: '容量' },
        { key: 'allocated', title: '已分配' }
      ]
    }
  },
  computed: {
    canManage() { return Array.isArray(this.ctx.permissionPatterns) && canCode(this.ctx, 'internship.position.manage') },
    canPublish() { return Array.isArray(this.ctx.permissionPatterns) && canCode(this.ctx, 'internship.position.publish') },
    canView() { return Array.isArray(this.ctx.permissionPatterns) && canCode(this.ctx, 'internship.position.view') },
    canEnterprise() { return Array.isArray(this.ctx.permissionPatterns) && canCode(this.ctx, 'internship.enterprise.view') },
    canExport() { return Array.isArray(this.ctx.permissionPatterns) && canCode(this.ctx, 'internship.position.export') },
    enterpriseFallbackOptions() {
      return !this.canEnterprise && this.filters.companyId
        ? [{ value: String(this.filters.companyId), label: '已按企业筛选' }]
        : []
    },
    statusOpts() { return POSITION_STATUS },
    toolbarActions() {
      if (this.activePanel === 'stats') {
        return [{ key: 'back', label: '返回岗位库' }, { key: 'refreshStats', label: '刷新概况', variant: 'primary' }]
      }
      if (!this.canManage) return []
      return [{ key: 'create', label: '新增岗位', variant: 'primary' }, { key: 'import', label: '导入岗位' }]
    },
    pageSubtitle() {
      const hint = POSITION_PANEL_HINTS[this.activePanel] || POSITION_PANEL_HINTS.list
      return this.activePanel === 'stats' ? '本校全部批次的岗位统计，不随当前批次和列表筛选变化。' : hint
    },
    listQuery() {
      const query = { ...this.$route.query, ...this.appliedFilters, page: String(this.page) }
      delete query.section
      return query
    }
  },
  watch: {
    activePanel() { this.focusHeading() },
    '$route.query': {
      immediate: true,
      handler(query) {
        this.applyPanel((query.panel || 'list').toString())
      }
    },
    ctx: { deep: true, handler() {
      this.scopeEpoch++; this.loadSequence++; this.importVisible = false; this.receipt = ''
      this.rows = []; this.total = 0; this.posStats = null
      this.filters = POSITION_PANEL_PRESETS[this.activePanel](); this.appliedFilters = { ...this.filters }; this.page = 1
      this.syncQuery()
    } }
  },
  beforeUnmount() { this.scopeEpoch++; this.loadSequence++ },
  methods: {
    focusHeading() {
      this.$nextTick(() => {
        const heading = this.$el?.querySelector('h1')
        if (!heading) return
        heading.setAttribute('tabindex', '-1')
        heading.style.scrollMarginTop = '170px'
        heading.focus({ preventScroll: true })
        heading.scrollIntoView({ block: 'start', behavior: 'instant' })
      })
    },
    applyPanel(panel) {
      const key = Object.hasOwn(POSITION_PANEL_PRESETS, panel) ? panel : 'list'
      this.activePanel = key
      this.filters = (POSITION_PANEL_PRESETS[key] || POSITION_PANEL_PRESETS.list)()
      for (const key of Object.keys(this.filters)) {
        if (typeof this.$route.query[key] === 'string') this.filters[key] = this.$route.query[key]
      }
      if (!['true', 'false'].includes(this.filters.risk)) this.filters.risk = ''
      this.appliedFilters = { ...this.filters }
      this.page = Math.min(1000000, Math.max(1, Number.parseInt(this.$route.query.page, 10) || 1))
      this.load()
    },
    async load() {
      const sequence = ++this.loadSequence, scope = this.scopeEpoch
      this.loading = true; this.error = ''
      this.rows = []; this.total = 0; this.posStats = null
      if (!this.canView) { this.loading = false; this.error = '当前账号没有查看岗位库的权限'; return }
      const stats = this.activePanel === 'stats'
      const batchId = typeof this.$route.query.batchId === 'string' ? this.$route.query.batchId : ''
      if (!stats && !batchId) { this.loading = false; this.error = '请先选择实习批次'; return }
      const p = { ...this.appliedFilters, batchId, page: this.page, pageSize: this.pageSize }
      if (!p.risk) delete p.risk
      else p.risk = p.risk === 'true'
      try {
        const res = stats ? await positionApi.getPositionStats() : await positionApi.getPositions(p)
        if (sequence !== this.loadSequence || scope !== this.scopeEpoch) return
        if (res.code === 0) {
          if (stats) this.posStats = res.data
          else { this.rows = res.data.list; this.total = res.data.total }
        } else this.error = res.message || (stats ? '岗位概况读取失败' : '岗位列表读取失败')
      } catch { if (sequence === this.loadSequence && scope === this.scopeEpoch) this.error = '岗位信息读取失败，请重试' }
      finally { if (sequence === this.loadSequence && scope === this.scopeEpoch) this.loading = false }
    },
    search() { this.appliedFilters = { ...this.filters }; this.page = 1; this.syncQuery() },
    reset() { this.filters = POSITION_PANEL_PRESETS[this.activePanel](); this.search() },
    turnPage(p) { this.page = p; this.syncQuery() },
    syncQuery() {
      const query = this.listQuery
      if (Object.keys(query).every((key) => query[key] === this.$route.query[key])) this.load()
      else this.$router.push({ path: this.$route.path, query })
    },
    positionLink(id, suffix = '', section) {
      const query = { ...this.listQuery }
      if (section) query.section = section
      return { path: '/admin/internship/positions/' + id + suffix, query }
    },
    onToolbar(key) {
      if (['create', 'import'].includes(key) && !this.canManage) return
      if (key === 'create') { this.$router.push({ path: '/admin/internship/positions/new', query: this.listQuery }) }
      if (key === 'import') { this.importVisible = true }
      if (key === 'refreshStats') this.load()
      if (key === 'back') this.showPanel('list')
    },
    showPanel(panel) { this.$router.push({ path: '/admin/internship/positions', query: { ...this.listQuery, panel } }) },
    async exportFn() {
      if (!this.canExport || !this.$route.query.batchId) return { code: 1, message: '请确认导出权限并选择批次' }
      const scope = this.scopeEpoch, batchId = this.$route.query.batchId
      const { keyword, status, companyId } = this.appliedFilters
      const res = await positionApi.exportPositions({ keyword, status, companyId, batchId })
      return scope === this.scopeEpoch && batchId === this.$route.query.batchId ? res : { code: 1, message: '办理范围已切换，请重新导出' }
    },
    onImported(data) {
      this.receipt = `已导入 ${data.created ?? 0} 个岗位，初始为草稿；核对资料后提交审核。`
      this.load()
    },

  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.ip-position-table :deep(.dt__table) { min-width: 1040px; }
.ip-filters { display: flex; align-items: flex-end; flex-wrap: wrap; gap: 14px; padding: 16px; border: 1px solid var(--border-base); border-radius: 10px; background: var(--bg-card); }
.ip-filters label, .ip-enterprise { display: flex; flex-direction: column; gap: 7px; font-size: 12px; color: var(--text-secondary); }
.ip-filters input, .ip-filters select { min-height: 36px; padding: 7px 10px; border: 1px solid var(--border-base); border-radius: 6px; color: var(--text-primary); background: var(--field-bg); font: inherit; }
.ip-filters input:focus-visible, .ip-filters select:focus-visible { outline: 2px solid var(--primary-500); outline-offset: 2px; }
.ip-keyword { flex: 1 1 220px; }
.ip-enterprise { flex: 1 1 220px; min-width: 180px; }
.ip-filter-actions, .ip-row-actions { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; }
.ip-search { min-height: 36px; padding: 8px 18px; background: var(--primary-500); border: 0; border-radius: 6px; color: var(--text-inverse); cursor: pointer; font: inherit; font-size: 13px; }
.ip-title { font-weight: 600; line-height: 1.5; color: var(--text-primary); text-decoration: none; }
.ip-title:hover { color: var(--primary-500); text-decoration: underline; }
.ip-list-head { display: flex; align-items: center; justify-content: space-between; gap: 14px; font-size: 13px; color: var(--text-secondary); }
.ip-metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(125px, 1fr)); gap: 20px; padding: 18px 0; border-block: 1px solid var(--border-base); margin: 0; }
.ip-metrics dt { font-size: 12px; color: var(--text-secondary); }
.ip-metrics dd { margin: 8px 0 0; font-weight: 600; font-size: 22px; }
.ip-receipt { margin: 0; padding: 12px 16px; background: var(--bg-section); border-radius: 8px; }
.ip-risk { margin-left: var(--space-2); font-size: 11px; color: var(--danger, #dc2626); }
.mp-link--danger { color: var(--danger, #dc2626); }
.ip-block { margin-bottom: var(--space-4); }
.ip-h { margin: 0 0 var(--space-2); font-size: 14px; }
</style>
