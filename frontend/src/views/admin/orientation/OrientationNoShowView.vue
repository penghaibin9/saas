<template>
  <ModulePageShell
    title="未报到学生"
    subtitle="未报到 / 延迟报到 / 未到校名单，跟进提醒（提醒经通知渠道下发，全程留痕）"
    :role-name="roleName"
    :data-scope-name="dataScopeName"
    watermark-purpose="未报到跟进"
  >
    <NoPermissionState v-if="noPermission" @back="$router.back()" />
    <template v-else>
      <ModuleToolbar :actions="toolbarActions" :hint="`共 ${total} 名待跟进新生`" @action="onToolbar" />

      <AdvancedFilter v-model="filters" :fields="filterFields" @search="search" @reset="reset" />

      <LoadingState v-if="loading" />
      <ErrorState v-else-if="error" :description="error" @retry="load" />
      <EmptyState v-else-if="!rows.length" title="没有未报到学生" description="当前数据范围内新生均已报到" />
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
/** /admin/orientation/no-show 未报到学生跟进（提醒 / 批量提醒 / 进学生详情；真实走 /orientation/students）。 */
import { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag, EmptyState, LoadingState, ErrorState } from '@/components/business'
import { TableActionColumn, NoPermissionState } from '@/modules/orientation/components'
import * as api from '@/modules/orientation/api/orientation.api'
import { toast } from '@/utils/toast'

const EMPTY_FILTERS = () => ({ keyword: '', reportStatus: 'NOT_REPORTED' })
const REPORT_OPTIONS = [
  { value: 'NOT_REPORTED', label: '未报到' },
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
      ctx: null, loading: true, error: '', rows: [], total: 0, page: 1, pageSize: 10,
      filters: EMPTY_FILTERS(),
      statusTagType: { NOT_REPORTED: 'warning', DELAYED: 'primary', NO_SHOW: 'danger', ABNORMAL: 'danger' }
    }
  },
  computed: {
    roleName() { return this.ctx?.currentRole?.roleName || '' },
    dataScopeName() { return this.ctx?.dataScope?.name || '' },
    perms() { return this.ctx?.permissionActions || {} },
    noPermission() { const p = this.perms['orientation.student.view']; return p ? !p.allowed : false },
    toolbarActions() { return [{ key: 'remindAll', label: '批量提醒本页' }] },
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
  methods: {
    async load() {
      this.loading = true; this.error = ''
      try {
        const res = await api.getOrientationStudents({ ...this.filters, page: this.page, pageSize: this.pageSize })
        if (res.code === 0) { this.rows = res.data.list; this.total = res.data.total } else this.error = res.message
      } catch (e) { this.error = e.message || '加载失败' } finally { this.loading = false }
    },
    search() { this.page = 1; this.load() },
    reset() { this.filters = EMPTY_FILTERS(); this.page = 1; this.load() },
    turnPage(p) { this.page = p; this.load() },
    rowActions() {
      return [
        { key: 'remind', label: '提醒' },
        { key: 'detail', label: '学生详情' }
      ]
    },
    async onRowAction(key, row) {
      if (key === 'detail') return this.$router.push(`/admin/orientation/students/${row.id}`)
      if (key === 'remind') {
        const res = await api.batchRemindStudents([row.id], '报到提醒')
        if (res.code === 0) toast.success(`已向「${row.name}」发送报到提醒`)
        else toast.error(res.message || '提醒失败')
      }
    },
    async onToolbar(key) {
      if (key !== 'remindAll') return
      if (!this.rows.length) return
      const res = await api.batchRemindStudents(this.rows.map((r) => r.id), '报到提醒')
      if (res.code === 0) toast.success(`已向本页 ${this.rows.length} 名新生发送报到提醒`)
      else toast.error(res.message || '批量提醒失败')
    }
  }
}
</script>
