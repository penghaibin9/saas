<template>
  <ModulePageShell
    title="报到资格"
    subtitle="综合核验 / 材料 / 缴费 / 卡点判定新生是否具备报到资格；受阻可人工放行（留痕）"
    :role-name="roleName"
    :data-scope-name="dataScopeName"
    watermark-purpose="报到资格判定"
  >
    <NoPermissionState v-if="noPermission" @back="$router.back()" />
    <template v-else>
      <ModuleToolbar :actions="[]" :hint="`共 ${total} 名新生 · 资格由核验/材料/缴费/卡点综合判定`" />

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
          <StatusTag :type="verdict(row).type" :label="verdict(row).label" dot />
        </template>
        <template #cell-blockedReason="{ row }">
          <span :class="{ 'oq-muted': !row.blockedReason }">{{ row.blockedReason || '—' }}</span>
        </template>
        <template #cell-actions="{ row }">
          <TableActionColumn :actions="rowActions(row)" @action="(key) => onRowAction(key, row)" />
        </template>
      </DataTable>

      <AppConfirmDialog
        v-model:visible="confirmVisible"
        title="人工放行"
        :message="confirmRow ? `对「${confirmRow.name}」人工放行，解除当前卡点、准予报到（需说明理由）。` : ''"
        type="danger"
        confirm-text="确认放行"
        require-reason
        reason-label="放行理由（≥5 字）"
        @confirm="onConfirm"
      />
    </template>
  </ModulePageShell>
</template>

<script>
/** /admin/orientation/qualification 报到资格判定 + 人工放行（真实走 /orientation/students 与 /orientation/progress/:id/resolve）。 */
import { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag, EmptyState, LoadingState, ErrorState } from '@/components/business'
import { AppConfirmDialog } from '@/components/common'
import { TableActionColumn, NoPermissionState } from '@/modules/orientation/components'
import * as api from '@/modules/orientation/api/orientation.api'
import { toast } from '@/utils/toast'

const EMPTY_FILTERS = () => ({ keyword: '' })

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
      return [{ key: 'keyword', label: '关键词', type: 'text', placeholder: '姓名 / 录取编号' }]
    },
    tableColumns() {
      return [
        { key: 'name', title: '姓名' },
        { key: 'className', title: '班级' },
        { key: 'qualification', title: '报到资格' },
        { key: 'blockedReason', title: '受阻原因' },
        { key: 'materialStatusLabel', title: '材料' },
        { key: 'paymentStatusLabel', title: '缴费' },
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
    verdict(row) {
      if (row.blockedStep) return { type: 'danger', label: '受阻', code: 'BLOCKED' }
      if (row.stage !== 'PRE_STUDENT_VERIFIED') return { type: 'warning', label: '待核验', code: 'PENDING' }
      return { type: 'success', label: '合格', code: 'QUALIFIED' }
    },
    rowActions(row) {
      const blocked = !!row.blockedStep
      return [
        { key: 'release', label: '人工放行', disabled: !blocked, disabledReason: blocked ? '' : '该生无卡点，无需放行' }
      ]
    },
    onRowAction(key, row) {
      if (key === 'release') { this.confirmRow = row; this.confirmVisible = true }
    },
    async onConfirm(reason) {
      const row = this.confirmRow; if (!row) return
      const res = await api.resolveBlockedIssue(row.id, { note: reason })
      if (res && res.code === 0) { toast.success('已人工放行'); this.confirmVisible = false; await this.load() }
      else toast.error((res && res.message) || '放行失败')
    }
  }
}
</script>

<style scoped>
.oq-muted {
  color: var(--t3);
}
</style>
