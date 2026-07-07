<template>
  <ModulePageShell
    title="新生信息核验"
    subtitle="核对新生填报信息与录取数据（姓名 / 身份证 / 录取编号），通过后进入预报到已核验"
    :role-name="roleName"
    :data-scope-name="dataScopeName"
    watermark-purpose="新生信息核验"
  >
    <NoPermissionState v-if="noPermission" @back="$router.back()" />
    <template v-else>
      <ModuleToolbar :actions="[]" :hint="`共 ${total} 名新生 · 核验动作全程留痕`" />

      <AdvancedFilter v-model="filters" :fields="filterFields" @search="search" @reset="reset" />

      <LoadingState v-if="loading" />
      <ErrorState v-else-if="error" :description="error" @retry="load" />
      <EmptyState v-else-if="!rows.length" title="暂无待核验新生" description="当前数据范围内没有匹配的新生" />
      <DataTable
        v-else
        :columns="tableColumns"
        :rows="rows"
        row-key="id"
        :pagination="{ page, pageSize, total }"
        @page-change="turnPage"
      >
        <template #cell-stage="{ row }">
          <StatusTag :type="row.stage === 'PRE_STUDENT_VERIFIED' ? 'success' : 'warning'" :label="row.stageLabel" dot />
        </template>
        <template #cell-actions="{ row }">
          <TableActionColumn :actions="rowActions(row)" @action="(key) => onRowAction(key, row)" />
        </template>
      </DataTable>

      <AppConfirmDialog
        v-model:visible="confirmVisible"
        :title="confirmConf.title"
        :message="confirmConf.message"
        :type="confirmConf.type"
        :confirm-text="confirmConf.confirmText"
        :require-reason="confirmConf.requireReason"
        reason-label="不通过原因（≥5 字）"
        @confirm="onConfirm"
      />
    </template>
  </ModulePageShell>
</template>

<script>
/** /admin/orientation/verify 新生信息核验（通过 / 不通过；真实走 /orientation/students/:id/verify）。 */
import { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag, EmptyState, LoadingState, ErrorState } from '@/components/business'
import { AppConfirmDialog } from '@/components/common'
import { TableActionColumn, NoPermissionState } from '@/modules/orientation/components'
import * as api from '@/modules/orientation/api/orientation.api'
import { toast } from '@/utils/toast'

const EMPTY_FILTERS = () => ({ keyword: '', stage: 'ADMITTED' })
const STAGE_OPTIONS = [
  { value: 'ADMITTED', label: '待核验（已录取）' },
  { value: 'PRE_STUDENT_VERIFIED', label: '已核验' }
]

export default {
  name: 'OrientationVerifyView',
  components: {
    ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag,
    EmptyState, LoadingState, ErrorState, AppConfirmDialog, TableActionColumn, NoPermissionState
  },
  data() {
    return {
      ctx: null, loading: true, error: '', rows: [], total: 0, page: 1, pageSize: 10,
      filters: EMPTY_FILTERS(), confirmVisible: false, confirmMode: '', confirmRow: null
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
        { key: 'stage', label: '核验状态', type: 'select', options: STAGE_OPTIONS }
      ]
    },
    tableColumns() {
      return [
        { key: 'name', title: '姓名' },
        { key: 'admissionNo', title: '录取编号' },
        { key: 'idCard', title: '身份证（脱敏）' },
        { key: 'className', title: '班级' },
        { key: 'stage', title: '核验状态' },
        { key: 'actions', title: '操作' }
      ]
    },
    confirmConf() {
      const r = this.confirmRow
      const who = r ? `「${r.name}」` : ''
      if (this.confirmMode === 'pass') return { title: '信息核验通过', message: `确认${who}的填报信息与录取数据一致？通过后进入「预报到已核验」。`, type: 'primary', confirmText: '确认通过', requireReason: false }
      if (this.confirmMode === 'fail') return { title: '信息核验不通过', message: `标记${who}信息核验不通过，请说明问题（如身份证/录取编号不一致）。`, type: 'danger', confirmText: '确认不通过', requireReason: true }
      return { title: '', message: '', type: 'primary', confirmText: '确认', requireReason: false }
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
    rowActions(row) {
      const verified = row.stage === 'PRE_STUDENT_VERIFIED'
      return [
        { key: 'pass', label: '核验通过', disabled: verified, disabledReason: verified ? '该生已核验' : '' },
        { key: 'fail', label: '不通过' }
      ]
    },
    onRowAction(key, row) { this.confirmMode = key; this.confirmRow = row; this.confirmVisible = true },
    async onConfirm(reason) {
      const row = this.confirmRow; if (!row) return
      const res = await api.verifyOrientationStudent(row.id, { passed: this.confirmMode === 'pass', reason })
      if (res && res.code === 0) { toast.success('已核验'); this.confirmVisible = false; await this.load() }
      else toast.error((res && res.message) || '操作失败')
    }
  }
}
</script>
