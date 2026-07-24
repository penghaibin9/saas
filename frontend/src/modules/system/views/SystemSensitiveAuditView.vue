<template>
  <ModulePageShell
    title="敏感与导入导出审计"
    subtitle="敏感查看 / 导入导出动作只读追溯 · 不提供删除"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="mp-stack">
      <AdvancedFilter v-model="filters" :fields="filterFields" @search="search" @reset="reset" />
      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" title="没有符合条件的敏感审计" description="可调整关键词或时间范围" />
      <DataTable
        v-else
        :columns="columns"
        :rows="rows"
        row-key="id"
        :pagination="pagination"
        @page-change="onPageChange"
      >
        <template #cell-result="{ row }">
          <StatusTag :type="row.result === 'SUCCESS' ? 'success' : 'warning'" :label="row.resultLabel || row.result" dot />
        </template>
      </DataTable>
    </div>
  </ModulePageShell>
</template>

<script>
import {
  ModulePageShell, AdvancedFilter, DataTable, StatusTag,
  LoadingState, ErrorState, EmptyState
} from '@/components/business'
import { systemApi } from '@/modules/system/api/system.api'

const EMPTY_FILTERS = () => ({ keyword: '', result: '', dateFrom: '', dateTo: '' })

export default {
  name: 'SystemSensitiveAuditView',
  components: {
    ModulePageShell, AdvancedFilter, DataTable, StatusTag, LoadingState, ErrorState, EmptyState
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      rows: [],
      filters: EMPTY_FILTERS(),
      pagination: { page: 1, pageSize: 20, total: 0 },
      columns: [
        { key: 'time', title: '时间', width: '150px' },
        { key: 'who', title: '操作人' },
        { key: 'actionLabel', title: '动作' },
        { key: 'target', title: '对象' },
        { key: 'result', title: '结果' },
        { key: 'moduleLabel', title: '模块' }
      ],
      filterFields: [
        { key: 'keyword', label: '关键词', type: 'text', placeholder: '操作人 / 对象' },
        { key: 'dateFrom', label: '开始日期', type: 'date' },
        { key: 'dateTo', label: '结束日期', type: 'date' },
        { key: 'result', label: '结果', type: 'select', options: [
          { value: 'SUCCESS', label: '成功' },
          { value: 'DENIED', label: '拒绝' },
          { value: 'FAILED', label: '失败' }
        ] }
      ]
    }
  },
  created() { this.load() },
  methods: {
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
      this.search()
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await systemApi.listSensitiveLogs({
        ...this.filters,
        page: this.pagination.page,
        pageSize: this.pagination.pageSize
      })
      if (res.code === 0) {
        this.rows = res.data.list || []
        this.pagination.total = res.data.total || 0
      } else {
        this.error = res.message
      }
      this.loading = false
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
</style>
