<template>
  <ModulePageShell flat title="新生住宿核对" :role-name="roleName" :data-scope-name="dataScopeName" watermark-purpose="宿舍入住管理">
    <template #actions>
      <AppButton variant="secondary" @click="$router.push({ path: '/admin/student-affairs/dorm/allocation', query: { source: 'orientation' } })">分配计划</AppButton>
      <AppButton @click="openBatchCheckin">按名单批量入住</AppButton>
      <AppButton variant="secondary" @click="$router.push('/admin/student-affairs/dorm/resource')">选床办理入住</AppButton>
    </template>
    <div v-if="batchId" class="ori-inline-note">当前迎新批次 · {{ batchId }}</div>
    <NoPermissionState v-if="noPermission" @back="$router.back()" />
    <template v-else>
      <ModuleToolbar :actions="toolbarActions" :hint="`共 ${total} 名新生 · 预留与实际入住分别核对`" @action="onToolbar">
        <template #right>
          <ColumnSettings v-model:selected-keys="visibleColumnKeys" :columns="allColumns" />
        </template>
      </ModuleToolbar>

      <AdvancedFilter v-model="filters" :fields="filterFields" @search="search" @reset="reset" />

      <LoadingState v-if="loading" />
      <ErrorState v-else-if="error" :description="error" @retry="load" />
      <EmptyState v-else-if="!rows.length" title="暂无住宿数据" />
      <DataTable
        v-else
        :columns="tableColumns"
        :rows="rows"
        row-key="id"
        selectable
        v-model:selected="selected"
        :pagination="{ page, pageSize, total }"
        @page-change="turnPage"
      >
        <template #batch-actions>
          <BatchActionBar :actions="batchBarActions" @action="onBatch" />
        </template>
        <template #cell-room="{ row }">{{ row.room || '未分配' }}</template>
        <template #cell-building="{ row }">{{ row.building || '未分配' }}</template>
        <template #cell-dormStatus="{ row }">
          <StatusTag :type="dormTagType[row.dormStatus] || 'default'" :label="row.dormStatusLabel" dot />
        </template>
        <template #cell-checkinTime="{ row }">{{ row.checkinTime || '—' }}</template>
        <template #cell-exceptionNote="{ row }">
          <span class="ori-inline-note">{{ row.exceptionNote || '—' }}</span>
        </template>
        <template #cell-actions="{ row }">
          <TableActionColumn :actions="rowActions(row)" @action="(key) => onRowAction(key, row)" />
        </template>
      </DataTable>

      <!-- 异常标记 -->
      <AppConfirmDialog
        v-model:visible="exceptionVisible"
        title="标记入住异常"
        :message="exceptionTarget ? `将「${exceptionTarget.name}」登记住宿异常，不改变实际入住状态。` : ''"
        type="danger"
        confirm-text="确认标记"
        require-reason
        reason-label="异常说明"
        reason-placeholder="如床位冲突 / 特殊住宿需求 / 未按时入住等（不少于 5 个字）"
        :submitting="submitting"
        @confirm="onExceptionConfirm"
      />

      <ExportDialog
        v-model:visible="exportVisible"
        title="导出住宿名单"
        :options="exportOpts"
        :selected-count="selected.length"
        :data-scope-name="dataScopeName"
        :export-fn="exportFn"
      />

      <AppDrawer v-model:visible="auditVisible" title="操作留痕 · 宿舍入住" mode="modal" size="xlarge">
        <AuditTrailPanel :logs="auditLogs" />
      </AppDrawer>
    </template>
  </ModulePageShell>
</template>

<script>
/** 页面 7：/admin/orientation/dorm 宿舍入住确认（查看 / 编辑宿舍 / 批量确认 / 异常标记 / 导出 / 留痕）。 */
import { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag, EmptyState, LoadingState, ErrorState } from '@/components/business'
import { AppConfirmDialog } from '@/components/common'
import { AppDrawer, AppButton } from '@/components/ui'
import { TableActionColumn, BatchActionBar, ExportDialog, AuditTrailPanel, ColumnSettings, NoPermissionState } from '@/modules/orientation/components'
import * as api from '@/modules/orientation/api/orientation.api'
import { DORM_TAG_TYPE, toLabelMap } from '@/modules/orientation/constants/orientation.constants'
import { toast } from '@/utils/toast'

const EMPTY_FILTERS = () => ({ keyword: '', dormStatus: '', building: '' })

export default {
  name: 'DormCheckinView',
  components: {
    ModulePageShell,
    ModuleToolbar,
    AdvancedFilter,
    DataTable,
    StatusTag,
    EmptyState,
    LoadingState,
    ErrorState,
    AppConfirmDialog,
    AppDrawer,
    TableActionColumn,
    BatchActionBar,
    AppButton,
    ExportDialog,
    AuditTrailPanel,
    ColumnSettings,
    NoPermissionState
  },
  data() {
    return {
      ctx: null,
      loading: true, requestSequence: 0,
      error: '',
      submitting: false,
      rows: [],
      total: 0,
      page: 1,
      pageSize: 10,
      selected: [],
      filters: EMPTY_FILTERS(),
      statusOptions: {},
      filterOptions: {},
      allColumns: [],
      visibleColumnKeys: [],
      batchDefs: [],
      exportOpts: {},
      editVisible: false,
      editing: null,
      confirmVisible: false,
      exceptionVisible: false,
      exceptionTarget: null,
      exportVisible: false,
      auditVisible: false,
      auditLogs: [],
      dormTagType: DORM_TAG_TYPE
    }
  },
  computed: {
    batchId() { return String(this.$route.query.batchId || '') },
    roleName() {
      return this.ctx?.currentRole?.roleName || ''
    },
    dataScopeName() {
      return this.ctx?.dataScope?.name || ''
    },
    perms() {
      return this.ctx?.permissionActions || {}
    },
    noPermission() {
      const p = this.perms['orientation.student.view']
      return p ? !p.allowed : false
    },
    labelMaps() {
      return Object.fromEntries(Object.entries(this.statusOptions).map(([k, v]) => [k, toLabelMap(v)]))
    },
    filterFields() {
      return [
        { key: 'keyword', label: '关键词', type: 'text', placeholder: '姓名 / 房间号' },
        { key: 'dormStatus', label: '入住状态', type: 'select', options: [{ value: 'UNASSIGNED', label: '未分配' }, { value: 'ASSIGNED', label: '已预留 · 待入住' }, { value: 'CHECKED_IN', label: '已入住' }, { value: 'EXCEPTION', label: '住宿待核查' }] },
        { key: 'building', label: '楼栋', type: 'select', options: this.filterOptions.buildings || [] }
      ]
    },
    tableColumns() {
      return this.allColumns.filter((c) => this.visibleColumnKeys.includes(c.key)).map((c) => ({ key: c.key, title: c.title }))
    },
    toolbarActions() {
      const exp = this.perms['orientation.dorm.export']
      return [
        exp && !exp.visible ? null : { key: 'export', label: '导出住宿名单', disabled: exp ? !exp.allowed : false, disabledReason: exp?.reason },
        { key: 'audit', label: '操作留痕' }
      ].filter(Boolean)
    },
    batchBarActions() {
      return this.batchDefs.filter(b => b.key !== 'batchConfirm')
        .map((b) => {
          const p = this.perms[b.permission]
          if (p && !p.visible) return null
          return { ...b, disabled: p ? !p.allowed : false, disabledReason: p?.reason }
        })
        .filter(Boolean)
    },

  },
  async created() {
    await this.init()
  },
  watch: { batchId() { this.page = 1; this.load() } },
  methods: {
    openBatchCheckin() { return this.$router.push({path:'/admin/student-affairs/dorm/checkin',query:{workspace:'batch',...(this.batchId ? {orientationBatchId:this.batchId} : {})}}) },
    labelOf(dict, value) {
      return this.labelMaps[dict]?.[value] || (value ? '待确认' : '—')
    },
    async init() {
      const [ctx, status, filter, cols, batch, exp] = await Promise.all([
        api.getOrientationContext(),
        api.getStatusOptions(),
        api.getFilterOptions(),
        api.getFieldColumns('dormList'),
        api.getBatchActions('dormList'),
        api.getExportOptions('dormList')
      ])
      if (ctx.code === 0) this.ctx = ctx.data
      if (status.code === 0) this.statusOptions = status.data
      if (filter.code === 0) this.filterOptions = filter.data
      if (cols.code === 0) {
        this.allColumns = cols.data
        this.visibleColumnKeys = cols.data.filter((c) => c.default || c.locked).map((c) => c.key)
      }
      if (batch.code === 0) this.batchDefs = batch.data
      if (exp.code === 0) this.exportOpts = exp.data
      await this.load()
    },
    async load() {
      const sequence = ++this.requestSequence
      this.loading = true
      this.error = ''
      this.selected = []
      try {
        const res = await api.getDormitoryCheckinList({ ...this.filters, ...(this.batchId ? {batchId:this.batchId} : {}), page: this.page, pageSize: this.pageSize })
        if (sequence !== this.requestSequence) return
        if (res.code === 0) {
          this.rows = res.data.list
          this.total = res.data.total
        } else this.error = res.message
      } catch (e) {
        if (sequence === this.requestSequence) this.error = e.message || '加载失败'
      } finally {
        if (sequence === this.requestSequence) this.loading = false
      }
    },
    search() {
      this.page = 1
      this.load()
    },
    reset() {
      this.filters = EMPTY_FILTERS()
      this.page = 1
      this.load()
    },
    turnPage(p) {
      this.page = p
      this.load()
    },
    rowActions(row) {
      const mark = this.perms['orientation.dorm.markException']
      return [
        { key: 'view', label: '入住信息' },
        { key: 'housing', label: '选床入住', disabled: row.dormStatus === 'CHECKED_IN', disabledReason: '已入住，如需更换床位请办理调宿' },
        {
          key: 'exception',
          label: '异常标记',
          danger: true,
          disabled: (mark ? !mark.allowed : false) || row.dormStatus === 'EXCEPTION',
          disabledReason: row.dormStatus === 'EXCEPTION' ? '该生已标记异常' : mark?.reason
        }
      ]
    },
    onRowAction(key, row) {
      if (key === 'view') this.$router.push(`/admin/orientation/students/${row.id}`)
      if (key === 'housing') this.$router.push({ path: '/admin/student-affairs/dorm/resource', query: row.bedId ? { buildingId: row.buildingId, roomId: row.roomId, bedId: row.bedId } : {} })
      if (key === 'exception') {
        this.exceptionTarget = row
        this.exceptionVisible = true
      }
    },
    onToolbar(key) {
      if (key === 'export') this.exportVisible = true
      if (key === 'audit') this.openAudit()
    },
    async openAudit() {
      const res = await api.getAuditLogs({ bizType: 'DORM' })
      if (res.code === 0) this.auditLogs = res.data.list
      this.auditVisible = true
    },
    onBatch(key) {
      if (!this.selected.length) return
      if (key === 'batchExport') this.exportVisible = true
    },
    async onExceptionConfirm({ reason }) {
      if (!this.exceptionTarget) return
      this.submitting = true
      try {
        const res = await api.markDormException(this.exceptionTarget.id, { note: reason })
        if (res.code === 0) {
          toast.success('已标记入住异常，说明已留痕')
          this.exceptionVisible = false
          this.load()
        } else toast.error(res.message)
      } finally {
        this.submitting = false
      }
    },
    exportFn(payload) {
      return api.createExport('dormList', payload)
    }
  }
}
</script>

<style scoped>
@import './orientation-page.css';
</style>
