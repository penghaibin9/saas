<template>
  <ModulePageShell
    title="报到资格"
    subtitle="服务端综合身份、必交材料、缴费/绿通、住宿、异常与冻结流程，返回可解释资格结论"
    :role-name="roleName"
    :data-scope-name="dataScopeName"
    watermark-purpose="报到资格判定"
  >
    <NoPermissionState v-if="noPermission" @back="$router.back()" />
    <template v-else>
      <ModuleToolbar :actions="[]" :hint="`共 ${total} 名新生 · 当前页面只展示服务端资格真值`" />

      <AdvancedFilter v-model="filters" :fields="filterFields" @search="search" @reset="reset" />

      <LoadingState v-if="loading" />
      <ErrorState v-else-if="error" :description="error" @retry="load" />
      <EmptyState v-else-if="!rows.length" title="暂无新生" description="当前数据范围内没有匹配的新生" />
      <DataTable
        v-else
        :columns="tableColumns"
        :rows="rows"
        row-key="id"
        :pagination="{ page, pageSize, total }"
        @page-change="turnPage"
      >
        <template #cell-qualification="{ row }">
          <StatusTag :type="qualificationType(row.verdict)" :label="row.verdictLabel" dot />
        </template>
        <template #cell-blockedReason="{ row }">
          <span :class="{ 'oq-muted': !row.blockers?.length }">{{ blockerText(row) }}</span>
        </template>
        <template #cell-actions="{ row }">
          <TableActionColumn :actions="rowActions(row)" @action="(key) => onRowAction(key, row)" />
        </template>
      </DataTable>

      <AppConfirmDialog
        v-model:visible="confirmVisible"
        title="重新计算报到资格"
        :message="confirmRow ? `将按当前服务器真实材料、缴费、绿色通道、住宿和异常事实重算「${confirmRow.name}」的报到资格。` : ''"
        type="primary"
        confirm-text="确认重算"
        @confirm="onConfirm"
      />
    </template>
  </ModulePageShell>
</template>

<script>
/** /admin/orientation/qualification：只展示服务端 OrientationQualificationService 裁决。 */
import { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag, EmptyState, LoadingState, ErrorState } from '@/components/business'
import { AppConfirmDialog } from '@/components/common'
import { TableActionColumn, NoPermissionState } from '@/modules/orientation/components'
import * as api from '@/modules/orientation/api/orientation.api'
import { toast } from '@/utils/toast'

const EMPTY_FILTERS = () => ({ keyword: '', verdict: '' })

export default {
  name: 'OrientationQualificationView',
  components: {
    ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag,
    EmptyState, LoadingState, ErrorState, AppConfirmDialog, TableActionColumn, NoPermissionState
  },
  data() {
    return {
      ctx: null, loading: true, error: '', rows: [], total: 0, page: 1, pageSize: 10,
      filters: EMPTY_FILTERS(), confirmVisible: false, confirmRow: null
    }
  },
  computed: {
    roleName() { return this.ctx?.currentRole?.roleName || '' },
    dataScopeName() { return this.ctx?.dataScope?.name || '' },
    perms() { return this.ctx?.permissionActions || {} },
    noPermission() { const p = this.perms['orientation.student.view']; return p ? !p.allowed : false },
    filterFields() {
      return [
        { key: 'keyword', label: '关键词', type: 'text', placeholder: '姓名 / 录取编号' },
        { key: 'verdict', label: '资格结论', type: 'select', options: [
          { value: 'QUALIFIED', label: '具备报到资格' },
          { value: 'NOT_QUALIFIED', label: '暂不具备报到资格' },
          { value: 'MANUAL_REVIEW', label: '需人工核查' }
        ] }
      ]
    },
    tableColumns() {
      return [
        { key: 'name', title: '姓名' },
        { key: 'className', title: '班级' },
        { key: 'qualification', title: '报到资格' },
        { key: 'blockedReason', title: '受阻原因' },
        { key: 'ruleVersion', title: '规则版本' },
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
        const res = await api.getOrientationQualifications({ ...this.filters, page: this.page, pageSize: this.pageSize })
        if (res.code === 0) { this.rows = res.data.list; this.total = res.data.total } else this.error = res.message
      } catch (e) { this.error = e.message || '加载失败' } finally { this.loading = false }
    },
    search() { this.page = 1; this.load() },
    reset() { this.filters = EMPTY_FILTERS(); this.page = 1; this.load() },
    turnPage(p) { this.page = p; this.load() },
    qualificationType(verdict) {
      return ({ QUALIFIED: 'success', NOT_QUALIFIED: 'danger', MANUAL_REVIEW: 'warning' })[verdict] || 'default'
    },
    blockerText(row) {
      return row.blockers?.length ? row.blockers.map((item) => item.message).join('；') : '—'
    },
    rowActions(row) {
      return [
        { key: 'student', label: '学生详情' },
        { key: 'recalculate', label: '按当前事实重算' }
      ]
    },
    onRowAction(key, row) {
      if (key === 'student') this.$router.push(`/admin/orientation/students/${row.id}`)
      if (key === 'recalculate') { this.confirmRow = row; this.confirmVisible = true }
    },
    async onConfirm() {
      const row = this.confirmRow; if (!row) return
      const res = await api.recalculateOrientationQualification(row.id)
      if (res && res.code === 0) { toast.success(`资格已重算：${res.data.verdictLabel}`); this.confirmVisible = false; await this.load() }
      else toast.error((res && res.message) || '资格重算失败')
    }
  }
}
</script>

<style scoped>
.oq-muted {
  color: var(--t3);
}
</style>
