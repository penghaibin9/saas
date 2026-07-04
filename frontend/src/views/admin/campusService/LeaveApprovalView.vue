<template>
  <ModulePageShell
    title="请假审批"
    :subtitle="'共 ' + pagination.total + ' 条 · 时长校验 / 冲突检测 / 频繁请假预警已启用'"
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
      <EmptyState v-else-if="!rows.length" title="没有符合条件的请假申请" description="学生可通过小程序发起请假申请，审批结果实时同步学生端" />
      <DataTable
        v-else
        :columns="columns"
        :rows="rows"
        row-key="id"
        selectable
        v-model:selected="selected"
        :pagination="pagination"
        @page-change="onPageChange"
      >
        <template #batch-actions>
          <button class="mp-link" :class="{ 'is-disabled': !can('campus.leave.batchApprove') }" :title="reason('campus.leave.batchApprove')" @click="batchApprove">批量通过</button>
          <button class="mp-link" :class="{ 'is-disabled': !can('campus.leave.export') }" :title="reason('campus.leave.export')" @click="openExport">导出选中</button>
        </template>
        <template #cell-code="{ row }">
          <div class="mp-cell-main">{{ row.code }}</div>
          <div class="mp-cell-sub">{{ row.applyTime }}</div>
        </template>
        <template #cell-name="{ row }">
          <div class="mp-cell-main">{{ row.name }}</div>
          <div class="mp-cell-sub">{{ row.className }}</div>
        </template>
        <template #cell-type="{ row }">{{ typeLabel(row.type) }}</template>
        <template #cell-range="{ row }">
          <div class="mp-cell-main">{{ row.startTime }}</div>
          <div class="mp-cell-sub">至 {{ row.endTime }}</div>
        </template>
        <template #cell-status="{ row }">
          <StatusTag :status="row.status" :label="statusLabel(row.status)" dot />
        </template>
        <template #cell-cancelStatus="{ row }">
          <span :class="{ 'mp-note': row.cancelStatus === '—' }">{{ row.cancelStatus }}</span>
        </template>
        <template #cell-actions="{ row }">
          <button class="mp-link" @click="openDetail(row)">查看</button>
          <button
            v-if="row.status === 'PENDING_REVIEW'"
            class="mp-link"
            :class="{ 'is-disabled': !can('campus.leave.approve') }"
            :title="reason('campus.leave.approve')"
            @click="quickApprove(row)"
          >
            通过
          </button>
          <button
            v-if="row.status === 'PENDING_REVIEW'"
            class="mp-link lav-danger"
            :class="{ 'is-disabled': !can('campus.leave.return') }"
            :title="reason('campus.leave.return')"
            @click="openReturn(row)"
          >
            退回
          </button>
        </template>
      </DataTable>

      <p class="mp-note">退回必须填写原因（同步学生端）；通过/退回/批量审批/导出均写入审计日志。请假记录自动进入学生360时间线。</p>
    </div>

    <AppDrawer v-model:visible="detailVisible" :title="detail ? '请假详情 · ' + detail.leave.code : '请假详情'">
      <template v-if="detail">
        <div class="lav-sec">
          <div class="mp-kv"><span class="mp-kv__k">学生</span><span class="mp-kv__v">{{ detail.leave.name }}（{{ detail.leave.className }}）</span></div>
          <div class="mp-kv"><span class="mp-kv__k">类型 / 时长</span><span class="mp-kv__v">{{ typeLabel(detail.leave.type) }} · {{ detail.leave.duration }}</span></div>
          <div class="mp-kv"><span class="mp-kv__k">起止时间</span><span class="mp-kv__v">{{ detail.leave.startTime }} ~ {{ detail.leave.endTime }}</span></div>
          <div class="mp-kv"><span class="mp-kv__k">事由</span><span class="mp-kv__v">{{ detail.leave.reason }}</span></div>
          <div class="mp-kv"><span class="mp-kv__k">附件</span><span class="mp-kv__v">{{ detail.leave.attachments.length ? detail.leave.attachments.join('、') : '无' }}</span></div>
          <div class="mp-kv"><span class="mp-kv__k">审批状态</span><span class="mp-kv__v"><StatusTag :status="detail.leave.status" :label="statusLabel(detail.leave.status)" dot /></span></div>
          <div v-if="detail.leave.returnReason" class="mp-kv"><span class="mp-kv__k">退回原因</span><span class="mp-kv__v">{{ detail.leave.returnReason }}</span></div>
        </div>
        <div v-if="detail.leave.conflictHint" class="lav-warn">⚠ {{ detail.leave.conflictHint }}</div>
        <div class="lav-sec">
          <div class="lav-sec__title">该生历史请假</div>
          <ul class="lav-list">
            <li v-for="h in detail.history" :key="h">{{ h }}</li>
            <li v-if="!detail.history.length" class="mp-note">无历史请假</li>
          </ul>
        </div>
        <div class="lav-sec">
          <div class="lav-sec__title">审批留痕</div>
          <table class="mp-audit">
            <thead><tr><th>时间</th><th>操作人</th><th>动作</th></tr></thead>
            <tbody>
              <tr v-for="a in detail.auditLogs" :key="a.id">
                <td>{{ a.time }}</td>
                <td class="is-who">{{ a.operator }}</td>
                <td>{{ a.detail }}</td>
              </tr>
              <tr v-if="!detail.auditLogs.length"><td colspan="3" class="mp-note">暂无审批记录</td></tr>
            </tbody>
          </table>
        </div>
      </template>
      <template #footer>
        <template v-if="detail && detail.leave.status === 'PENDING_REVIEW'">
          <AppButton variant="danger" :disabled="!can('campus.leave.return')" :title="reason('campus.leave.return')" @click="openReturn(detail.leave)">退回修改</AppButton>
          <AppButton variant="primary" :disabled="!can('campus.leave.approve')" :title="reason('campus.leave.approve')" @click="quickApprove(detail.leave)">审批通过</AppButton>
        </template>
        <AppButton v-else variant="ghost" @click="detailVisible = false">关闭</AppButton>
      </template>
    </AppDrawer>

    <AppConfirmDialog
      v-model:visible="approveDialog.visible"
      type="primary"
      title="审批通过"
      :message="'确认通过「' + (approveDialog.row ? approveDialog.row.name + ' · ' + approveDialog.row.duration : '') + '」的请假申请？结果将同步学生端并进入学生360。'"
      confirm-text="确认通过"
      :submitting="approveDialog.submitting"
      @confirm="submitApprove"
    />

    <AppConfirmDialog
      v-model:visible="returnDialog.visible"
      type="danger"
      title="退回修改"
      :message="'退回「' + (returnDialog.row ? returnDialog.row.code : '') + '」请假申请，退回原因将原文同步学生端。'"
      confirm-text="确认退回"
      require-reason
      reason-label="退回原因"
      reason-placeholder="请说明退回原因（如材料不全、时间冲突），不少于 5 个字"
      :submitting="returnDialog.submitting"
      @confirm="submitReturn"
    />

    <ExportDrawer v-model:visible="exportVisible" :options="exportOpts" :selected-count="selected.length" :data-scope-name="ctx.dataScope.name" :export-fn="exportFn" />
  </ModulePageShell>
</template>

<script>
/**
 * 请假审批管理（/admin/campus-service/leave）。
 * 闭环：请假列表 → 详情（历史/冲突提示/留痕）→ 通过 / 退回（原因必填同步学生端）→ 批量审批 → 导出（审计）。
 */
import { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import AppDrawer from '@/components/ui/AppDrawer.vue'
import { AppButton } from '@/components/ui'
import { ExportDrawer } from '@/modules/campusService/components'
import {
  getLeaveApplications, getLeaveApplicationDetail, approveLeave, returnLeave, batchApproveLeaves,
  getFieldColumns, getExportOptions, createExport
} from '@/modules/campusService/api/campusService.api'
import { toast } from '@/utils/toast'

const EMPTY_FILTERS = () => ({ keyword: '', type: '', status: '', classId: '' })

export default {
  name: 'LeaveApprovalView',
  components: {
    ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag, LoadingState, ErrorState, EmptyState,
    AppConfirmDialog, AppDrawer, AppButton, ExportDrawer
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      rows: [],
      selected: [],
      filters: EMPTY_FILTERS(),
      pagination: { page: 1, pageSize: 10, total: 0 },
      columns: [],
      detailVisible: false,
      detail: null,
      approveDialog: { visible: false, submitting: false, row: null },
      returnDialog: { visible: false, submitting: false, row: null },
      exportVisible: false,
      exportOpts: null
    }
  },
  computed: {
    filterFields() {
      const o = this.ctx.statusOptions
      const f = this.ctx.filterOptions
      return [
        { key: 'keyword', label: '关键词', type: 'text', placeholder: '学生 / 请假编号' },
        { key: 'type', label: '请假类型', type: 'select', options: o.leaveType },
        { key: 'status', label: '审批状态', type: 'select', options: o.leaveStatus },
        { key: 'classId', label: '班级', type: 'select', options: f.classes }
      ]
    },
    toolbarActions() {
      const pa = this.ctx.permissionActions
      return [{ key: 'export', permission: 'campus.leave.export', label: '导出请假记录' }]
        .filter((a) => pa[a.permission] && pa[a.permission].visible)
        .map((a) => ({ ...a, disabled: !pa[a.permission].allowed, disabledReason: pa[a.permission].reason }))
    }
  },
  async created() {
    const cols = await getFieldColumns('leaveList')
    if (cols.code === 0) this.columns = cols.data.filter((c) => c.locked || c.default).map((c) => ({ key: c.key, title: c.title }))
    if (this.$route.query.keyword) this.filters.keyword = String(this.$route.query.keyword)
    this.load()
  },
  methods: {
    can(key) {
      const pa = this.ctx.permissionActions[key]
      return !!(pa && pa.visible && pa.allowed)
    },
    reason(key) {
      const pa = this.ctx.permissionActions[key]
      return pa && !pa.allowed ? pa.reason : ''
    },
    typeLabel(v) {
      return (this.ctx.statusOptions.leaveType.find((o) => o.value === v) || {}).label || v
    },
    statusLabel(v) {
      return (this.ctx.statusOptions.leaveStatus.find((o) => o.value === v) || {}).label || v
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
      const res = await getLeaveApplications({ ...this.filters, page: this.pagination.page, pageSize: this.pagination.pageSize })
      if (res.code === 0) {
        this.rows = res.data.list
        this.pagination.total = res.data.total
      } else {
        this.error = res.message
      }
      this.loading = false
    },
    async onToolbar(key) {
      if (key === 'export') this.openExport()
    },
    async openDetail(row) {
      const res = await getLeaveApplicationDetail(row.id)
      if (res.code === 0) {
        this.detail = res.data
        this.detailVisible = true
      } else {
        toast.error(res.message)
      }
    },
    quickApprove(row) {
      if (!this.can('campus.leave.approve')) return
      this.approveDialog = { visible: true, submitting: false, row }
    },
    async submitApprove() {
      this.approveDialog.submitting = true
      const res = await approveLeave(this.approveDialog.row.id)
      this.approveDialog.submitting = false
      if (res.code === 0) {
        toast.success('已审批通过，结果已同步学生端并留痕')
        this.approveDialog.visible = false
        this.detailVisible = false
        this.load()
      } else {
        toast.error(res.message)
      }
    },
    openReturn(row) {
      if (!this.can('campus.leave.return')) return
      this.returnDialog = { visible: true, submitting: false, row }
    },
    async submitReturn({ reason }) {
      this.returnDialog.submitting = true
      const res = await returnLeave(this.returnDialog.row.id, { reason })
      this.returnDialog.submitting = false
      if (res.code === 0) {
        toast.success('已退回修改，原因已原文同步学生端并留痕')
        this.returnDialog.visible = false
        this.detailVisible = false
        this.load()
      } else {
        toast.error(res.message)
      }
    },
    async batchApprove() {
      if (!this.can('campus.leave.batchApprove')) return
      const res = await batchApproveLeaves(this.selected)
      if (res.code === 0) toast.success(`批量通过 ${res.data.count} 条待审批请假（跳过非待审批状态），已留痕`)
      else toast.error(res.message)
      this.selected = []
      this.load()
    },
    async openExport() {
      if (!this.can('campus.leave.export')) return
      if (!this.exportOpts) {
        const res = await getExportOptions('leaveList')
        if (res.code === 0) this.exportOpts = res.data
      }
      this.exportVisible = true
    },
    exportFn(payload) {
      return createExport('leaveList', payload)
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.lav-danger {
  color: var(--danger-600);
}
.mp-link + .mp-link {
  margin-left: var(--space-2);
}
.lav-sec {
  margin-bottom: var(--space-4);
}
.lav-sec__title {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
  margin-bottom: var(--space-2);
}
.lav-list {
  margin: 0;
  padding-left: var(--space-5);
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}
.lav-warn {
  font-size: var(--font-size-sm);
  color: var(--warning-700);
  background: var(--warning-50);
  border: 1px solid var(--warning-100);
  border-radius: var(--radius-base);
  padding: var(--space-2) var(--space-3);
  margin-bottom: var(--space-4);
}
</style>
