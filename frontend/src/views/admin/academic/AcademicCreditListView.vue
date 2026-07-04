<template>
  <ModulePageShell
    title="学分修读"
    :subtitle="'共 ' + pagination.total + ' 人 · 学分口径同步自教务系统'"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.name"
  >
    <template #actions>
      <ModuleToolbar :actions="toolbarActions" @action="onToolbar" />
    </template>

    <div class="mp-stack">
      <AdvancedFilter v-model="filters" :fields="filterFields" @search="search" @reset="reset" />

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" title="没有符合条件的学分记录" description="可调整筛选条件后重新查询" />
      <DataTable v-else :columns="columns" :rows="rows" row-key="id" :pagination="pagination" @page-change="onPageChange">
        <template #cell-name="{ row }">
          <div class="mp-cell-main">{{ row.name }}</div>
          <div class="mp-cell-sub">{{ row.className }}</div>
        </template>
        <template #cell-progress="{ row }">
          <div class="acl-bar">
            <div class="acl-bar__fill" :class="{ 'is-low': row.status !== 'ON_TRACK' }" :style="{ width: Math.min(100, (row.obtained / row.midRequired) * 100) + '%' }" />
          </div>
          <div class="mp-cell-sub">中期进度 {{ Math.round((row.obtained / row.midRequired) * 100) }}%</div>
        </template>
        <template #cell-categories="{ row }">
          <span v-for="c in row.categories" :key="c.key" class="acl-cat">{{ c.label }} {{ c.obtained }}/{{ c.required }}</span>
        </template>
        <template #cell-gap="{ row }">
          <StatusTag v-if="row.gap > 0" type="danger" :label="'缺 ' + row.gap" />
          <span v-else class="mp-note">无缺口</span>
        </template>
        <template #cell-status="{ row }">
          <StatusTag :type="row.status === 'ON_TRACK' ? 'success' : row.status === 'BEHIND' ? 'warning' : 'danger'" :label="statusLabel(row.status)" dot />
        </template>
        <template #cell-actions="{ row }">
          <button class="mp-link" @click="$router.push('/admin/academic/students/' + row.studentId)">下钻学生</button>
          <button
            v-if="row.status !== 'ON_TRACK' && visible('academic.warning.create')"
            class="mp-link"
            :class="{ 'is-disabled': !can('academic.warning.create') }"
            :title="reason('academic.warning.create')"
            @click="$router.push('/admin/academic/warnings?create=' + row.studentId)"
          >
            发起预警
          </button>
        </template>
      </DataTable>

      <p class="mp-note">
        学分完成情况用于学业预警（规则 ACAD-R05）与毕业资格前置判断；本页只读展示，学分变动以教务同步批次为准。导出默认脱敏并含水印。
      </p>
    </div>

    <ExportDrawer v-model:visible="exportVisible" :options="exportOpts" :selected-count="0" :data-scope-name="ctx.dataScope.name" :export-fn="exportFn" />
  </ModulePageShell>
</template>

<script>
/** 学分修读管理（/admin/academic/credits）：学分完成情况 → 下钻学生 / 对滞后学生发起预警 / 导出台账。 */
import { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { ExportDrawer } from '@/modules/academic/components'
import { getCreditRecords, getFieldColumns, getExportOptions, createExport } from '@/modules/academic/api/academic.api'

const EMPTY_FILTERS = () => ({ keyword: '', classId: '', status: '' })

export default {
  name: 'AcademicCreditListView',
  components: { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag, LoadingState, ErrorState, EmptyState, ExportDrawer },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      rows: [],
      filters: EMPTY_FILTERS(),
      pagination: { page: 1, pageSize: 10, total: 0 },
      columns: [],
      exportVisible: false,
      exportOpts: null
    }
  },
  computed: {
    filterFields() {
      return [
        { key: 'keyword', label: '关键词', type: 'text', placeholder: '学生姓名' },
        { key: 'classId', label: '班级', type: 'select', options: this.ctx.filterOptions.classes },
        { key: 'status', label: '学分状态', type: 'select', options: this.ctx.statusOptions.creditStatus }
      ]
    },
    toolbarActions() {
      const pa = this.ctx.permissionActions
      return [{ key: 'export', permission: 'academic.credit.export', label: '导出学分台账' }]
        .filter((a) => pa[a.permission] && pa[a.permission].visible)
        .map((a) => ({ ...a, disabled: !pa[a.permission].allowed, disabledReason: pa[a.permission].reason }))
    }
  },
  async created() {
    const cols = await getFieldColumns('creditList')
    if (cols.code === 0) this.columns = cols.data.filter((c) => c.locked || c.default).map((c) => ({ key: c.key, title: c.title }))
    this.load()
  },
  methods: {
    can(key) {
      const pa = this.ctx.permissionActions[key]
      return !!(pa && pa.visible && pa.allowed)
    },
    visible(key) {
      const pa = this.ctx.permissionActions[key]
      return !!(pa && pa.visible)
    },
    reason(key) {
      const pa = this.ctx.permissionActions[key]
      return pa && !pa.allowed ? pa.reason : ''
    },
    statusLabel(v) {
      return (this.ctx.statusOptions.creditStatus.find((o) => o.value === v) || {}).label || v
    },
    onPageChange(page) {
      this.pagination.page = page
      this.load()
    },
    search() {
      this.pagination.page = 1
      this.load()
    },
    reset() {
      this.filters = EMPTY_FILTERS()
      this.pagination.page = 1
      this.load()
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await getCreditRecords({ ...this.filters, page: this.pagination.page, pageSize: this.pagination.pageSize })
      if (res.code === 0) {
        this.rows = res.data.list
        this.pagination.total = res.data.total
      } else {
        this.error = res.message
      }
      this.loading = false
    },
    async onToolbar(key) {
      if (key === 'export') {
        if (!this.exportOpts) {
          const res = await getExportOptions('creditList')
          if (res.code === 0) this.exportOpts = res.data
        }
        this.exportVisible = true
      }
    },
    exportFn(payload) {
      return createExport('creditList', payload)
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.acl-bar {
  width: 120px;
  height: 8px;
  border-radius: var(--radius-full);
  background: var(--gray-100);
  overflow: hidden;
}
.acl-bar__fill {
  height: 100%;
  border-radius: var(--radius-full);
  background: var(--primary-500);
}
.acl-bar__fill.is-low {
  background: var(--danger-500);
}
.acl-cat {
  display: inline-block;
  font-size: var(--font-size-xs);
  color: var(--text-secondary);
  background: var(--bg-section-blue);
  border-radius: var(--radius-full);
  padding: 0 var(--space-2);
  margin: 0 var(--space-1) var(--space-1) 0;
  white-space: nowrap;
}
.mp-link + .mp-link {
  margin-left: var(--space-2);
}
</style>
