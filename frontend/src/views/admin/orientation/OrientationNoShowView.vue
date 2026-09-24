<template>
  <ModulePageShell
    flat title="未报到跟进"
    watermark-purpose="未报到跟进"
  >
    <NoPermissionState v-if="noPermission" @back="$router.back()" />
    <template v-else>
      <ModuleToolbar :hint="`共 ${total} 名待跟进新生 · 点击学生详情继续核对，报到安排处理延期与未到校`" />

      <AdvancedFilter v-model="filters" :fields="filterFields" @search="search" @reset="reset" />

      <LoadingState v-if="loading" />
      <ErrorState v-else-if="error" :description="error" @retry="load" />
      <EmptyState v-else-if="!rows.length" title="没有未报到学生" description="当前筛选下没有待跟进记录" />
      <DataTable
        v-else
        :columns="tableColumns"
        :rows="rows"
        row-key="id"
        :pagination="{ page, pageSize, total }"
        @page-change="turnPage"
      >
        <template #cell-reportStatus="{ row }">
          <StatusTag :type="statusTagType[row.reportStatus] || 'default'" :label="row.reportStatusLabel" dot />
        </template>
        <template #cell-actions="{ row }">
          <TableActionColumn :actions="rowActions()" @action="(key) => onRowAction(key, row)" />
        </template>
      </DataTable>
    </template>
  </ModulePageShell>
</template>

<script>
/** 未报到学生跟进，接续同一批次、同一学生的正式办理入口。 */
import { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag, EmptyState, LoadingState, ErrorState } from '@/components/business'
import { TableActionColumn, NoPermissionState } from '@/modules/orientation/components'
import * as api from '@/modules/orientation/api/orientation.api'

const EMPTY_FILTERS = () => ({ keyword: '', reportStatus: '' })
const REPORT_OPTIONS = [
  { value: 'NOT_REPORTED', label: '未预报到' },
  { value: 'PREPARED', label: '已预报到，待到校' },
  { value: 'DELAYED', label: '延迟报到' },
  { value: 'NO_SHOW', label: '未到校' },
  { value: 'ABNORMAL', label: '报到异常' }
]

export default {
  name: 'OrientationNoShowView',
  components: {
    ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag,
    EmptyState, LoadingState, ErrorState, TableActionColumn, NoPermissionState
  },
  data() {
    return {
      requestSerial: 0, ctx: null, loading: true, error: '', rows: [], total: 0, page: 1, pageSize: 10,
      filters: EMPTY_FILTERS(),
      statusTagType: { NOT_REPORTED: 'warning', PREPARED: 'primary', DELAYED: 'primary', NO_SHOW: 'danger', ABNORMAL: 'danger' }
    }
  },
  computed: {
    roleName() { return this.ctx?.currentRole?.roleName || '' },
    dataScopeName() { return this.ctx?.dataScope?.name || '' },
    perms() { return this.ctx?.permissionActions || {} },
    noPermission() { const p = this.perms['orientation.student.view']; return p ? !p.allowed : false },
    canArrange() { return !!this.perms['orientation.enrollment.finalize']?.allowed },
    filterFields() {
      return [
        { key: 'keyword', label: '关键词', type: 'text', placeholder: '姓名 / 录取编号' },
        { key: 'reportStatus', label: '报到状态', type: 'select', options: REPORT_OPTIONS }
      ]
    },
    tableColumns() {
      return [
        { key: 'name', title: '姓名' },
        { key: 'admissionNo', title: '录取编号' },
        { key: 'collegeName', title: '学院' },
        { key: 'className', title: '班级' },
        { key: 'counselor', title: '辅导员' },
        { key: 'reportStatus', title: '报到状态' },
        { key: 'actions', title: '操作' }
      ]
    }
  },
  async created() {
    const ctx = await api.getOrientationContext()
    if (ctx.code === 0) this.ctx = ctx.data
    await this.load()
  },
  beforeUnmount() { this.requestSerial++ },
  methods: {
    async load() {
      const serial = ++this.requestSerial
      this.loading = true; this.error = ''; this.rows = []; this.total = 0
      try {
        const res = await api.getOrientationStudents({ ...this.filters, page: this.page, pageSize: this.pageSize, pendingArrival: true, batchId: this.$route?.query?.batchId || undefined })
        if (serial !== this.requestSerial) return
        if (res.code === 0) { this.rows = res.data.list; this.total = res.data.total } else this.error = res.message || '未报到名单读取失败，请重试'
      } catch (e) { if (serial === this.requestSerial) this.error = e.message || '加载失败' } finally { if (serial === this.requestSerial) this.loading = false }
    },
    search() { this.page = 1; this.load() },
    reset() { this.filters = EMPTY_FILTERS(); this.page = 1; this.load() },
    turnPage(p) { this.page = p; this.load() },
    rowActions() {
      return [
        ...(this.canArrange ? [{ key: 'disposition', label: '报到安排' }] : []),
        { key: 'detail', label: '学生详情' }
      ]
    },
    onRowAction(key, row) {
      if (this.loading || this.error) return
      const query = { batchId: row.batchId || this.$route.query.batchId }
      if (key === 'disposition' && this.canArrange) return this.$router.push({ path: '/admin/orientation/qualification', query: { ...query, orientationStudentId: String(row.id) } })
      if (key === 'detail') return this.$router.push({ path: `/admin/orientation/students/${row.id}`, query })
    }
  }
}
</script>
