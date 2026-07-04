<template>
  <ModulePageShell
    title="奖助资助"
    :subtitle="'共 ' + pagination.total + ' 条 · 金额区间化展示，困难材料仅授权角色可见'"
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
      <EmptyState v-else-if="!rows.length" title="没有符合条件的资助申请" description="学生可通过小程序提交奖助/资助申请，审核结果实时同步学生端" />
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
          <button class="mp-link" :class="{ 'is-disabled': !can('campus.grant.batchReview') }" :title="reason('campus.grant.batchReview')" @click="batchApprove">批量审核通过</button>
          <button class="mp-link" :class="{ 'is-disabled': !can('campus.grant.export') }" :title="reason('campus.grant.export')" @click="openExport">导出选中</button>
        </template>
        <template #cell-code="{ row }">
          <div class="mp-cell-main">{{ row.code }}</div>
          <div class="mp-cell-sub">{{ row.currentNode }}</div>
        </template>
        <template #cell-name="{ row }">
          <div class="mp-cell-main">{{ row.name }}</div>
          <div class="mp-cell-sub">{{ row.className }}</div>
        </template>
        <template #cell-type="{ row }">{{ typeLabel(row.type) }}</template>
        <template #cell-amount="{ row }">{{ row.amountDisplay }}</template>
        <template #cell-materialStatus="{ row }">{{ row.materialStatus }}</template>
        <template #cell-status="{ row }">
          <StatusTag :status="row.status" :label="statusLabel(row.status)" dot />
        </template>
        <template #cell-actions="{ row }">
          <button class="mp-link" @click="openDetail(row)">查看</button>
          <button
            v-if="['PENDING_REVIEW', 'REVIEWING'].includes(row.status)"
            class="mp-link"
            :class="{ 'is-disabled': !can('campus.grant.review') }"
            :title="reason('campus.grant.review')"
            @click="quickApprove(row)"
          >
            通过
          </button>
          <button
            v-if="['PENDING_REVIEW', 'REVIEWING'].includes(row.status)"
            class="mp-link gav-danger"
            :class="{ 'is-disabled': !can('campus.grant.return') }"
            :title="reason('campus.grant.return')"
            @click="openReturn(row)"
          >
            退回
          </button>
        </template>
      </DataTable>

      <p class="mp-note">
        资助审核为资助老师专属权限；家庭经济困难材料默认不展示，仅授权角色可查看且查看写审计。退回原因必填并同步学生端；导出台账金额区间化、含水印并留痕。
      </p>
    </div>

    <AppDrawer v-model:visible="detailVisible" :title="detail ? '资助申请 · ' + detail.grant.code : '资助申请'">
      <template v-if="detail">
        <div class="gav-sec">
          <div class="mp-kv"><span class="mp-kv__k">学生</span><span class="mp-kv__v">{{ detail.grant.name }}（{{ detail.grant.className }}）</span></div>
          <div class="mp-kv"><span class="mp-kv__k">申请类型</span><span class="mp-kv__v">{{ typeLabel(detail.grant.type) }}</span></div>
          <div class="mp-kv"><span class="mp-kv__k">金额（区间）</span><span class="mp-kv__v">{{ detail.grant.amountDisplay }}</span></div>
          <div class="mp-kv"><span class="mp-kv__k">申请理由</span><span class="mp-kv__v">{{ detail.grant.applyReason }}</span></div>
          <div class="mp-kv"><span class="mp-kv__k">当前节点</span><span class="mp-kv__v">{{ detail.grant.currentNode }}</span></div>
          <div class="mp-kv"><span class="mp-kv__k">审核状态</span><span class="mp-kv__v"><StatusTag :status="detail.grant.status" :label="statusLabel(detail.grant.status)" dot /></span></div>
          <div v-if="detail.grant.returnReason" class="mp-kv"><span class="mp-kv__k">退回原因</span><span class="mp-kv__v">{{ detail.grant.returnReason }}</span></div>
        </div>
        <div class="gav-sec">
          <div class="gav-sec__title">申请材料（敏感收敛）</div>
          <template v-if="detail.materials.length">
            <ul class="gav-list">
              <li v-for="m in detail.materials" :key="m">{{ m }}</li>
            </ul>
            <p class="mp-note">本次查看已写入审计日志。</p>
          </template>
          <div v-else class="gav-warn">{{ detail.materialHint || '当前角色不可查看困难材料明细' }}</div>
        </div>
        <div class="gav-sec">
          <div class="gav-sec__title">审核留痕</div>
          <table class="mp-audit">
            <thead><tr><th>时间</th><th>操作人</th><th>动作</th></tr></thead>
            <tbody>
              <tr v-for="a in detail.auditLogs" :key="a.id">
                <td>{{ a.time }}</td>
                <td class="is-who">{{ a.operator }}</td>
                <td>{{ a.detail }}</td>
              </tr>
              <tr v-if="!detail.auditLogs.length"><td colspan="3" class="mp-note">暂无审核记录</td></tr>
            </tbody>
          </table>
        </div>
      </template>
      <template #footer>
        <template v-if="detail && ['PENDING_REVIEW', 'REVIEWING'].includes(detail.grant.status)">
          <AppButton variant="danger" :disabled="!can('campus.grant.return')" :title="reason('campus.grant.return')" @click="openReturn(detail.grant)">退回补充</AppButton>
          <AppButton variant="primary" :disabled="!can('campus.grant.review')" :title="reason('campus.grant.review')" @click="quickApprove(detail.grant)">审核通过</AppButton>
        </template>
        <AppButton v-else variant="ghost" @click="detailVisible = false">关闭</AppButton>
      </template>
    </AppDrawer>

    <AppConfirmDialog
      v-model:visible="approveDialog.visible"
      type="primary"
      title="审核通过"
      :message="'确认通过「' + (approveDialog.row ? approveDialog.row.name + ' · ' + typeLabel(approveDialog.row.type) : '') + '」？通过后进入发放流程，结果同步学生端。'"
      confirm-text="确认通过"
      :submitting="approveDialog.submitting"
      @confirm="submitApprove"
    />

    <AppConfirmDialog
      v-model:visible="returnDialog.visible"
      type="danger"
      title="退回补充"
      :message="'退回「' + (returnDialog.row ? returnDialog.row.code : '') + '」资助申请，退回原因将原文同步学生端。'"
      confirm-text="确认退回"
      require-reason
      reason-label="退回原因"
      reason-placeholder="请说明需补充的材料或不符合项，不少于 5 个字"
      :submitting="returnDialog.submitting"
      @confirm="submitReturn"
    />

    <ExportDrawer v-model:visible="exportVisible" :options="exportOpts" :selected-count="selected.length" :data-scope-name="ctx.dataScope.name" :export-fn="exportFn" />
  </ModulePageShell>
</template>

<script>
/**
 * 奖助 / 资助申请管理（/admin/campus-service/grants）。
 * 闭环：申请列表 → 详情（材料敏感收敛+查看留痕）→ 审核通过 / 退回（原因必填）→ 批量审核 → 导出资助台账（区间化+水印+审计）。
 */
import { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import AppDrawer from '@/components/ui/AppDrawer.vue'
import { AppButton } from '@/components/ui'
import { ExportDrawer } from '@/modules/campusService/components'
import {
  getGrantApplications, getGrantApplicationDetail, approveGrant, returnGrant, batchApproveGrants,
  getFieldColumns, getExportOptions, createExport
} from '@/modules/campusService/api/campusService.api'
import { toast } from '@/utils/toast'

const EMPTY_FILTERS = () => ({ keyword: '', type: '', status: '' })

export default {
  name: 'GrantApplicationView',
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
      return [
        { key: 'keyword', label: '关键词', type: 'text', placeholder: '学生 / 申请编号' },
        { key: 'type', label: '申请类型', type: 'select', options: o.grantType },
        { key: 'status', label: '审核状态', type: 'select', options: o.grantStatus }
      ]
    },
    toolbarActions() {
      const pa = this.ctx.permissionActions
      return [{ key: 'export', permission: 'campus.grant.export', label: '导出资助台账' }]
        .filter((a) => pa[a.permission] && pa[a.permission].visible)
        .map((a) => ({ ...a, disabled: !pa[a.permission].allowed, disabledReason: pa[a.permission].reason }))
    }
  },
  async created() {
    const cols = await getFieldColumns('grantList')
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
      return (this.ctx.statusOptions.grantType.find((o) => o.value === v) || {}).label || v
    },
    statusLabel(v) {
      return (this.ctx.statusOptions.grantStatus.find((o) => o.value === v) || {}).label || v
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
      const res = await getGrantApplications({ ...this.filters, page: this.pagination.page, pageSize: this.pagination.pageSize })
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
      const res = await getGrantApplicationDetail(row.id)
      if (res.code === 0) {
        this.detail = res.data
        this.detailVisible = true
      } else {
        toast.error(res.message)
      }
    },
    quickApprove(row) {
      if (!this.can('campus.grant.review')) return
      this.approveDialog = { visible: true, submitting: false, row }
    },
    async submitApprove() {
      this.approveDialog.submitting = true
      const res = await approveGrant(this.approveDialog.row.id)
      this.approveDialog.submitting = false
      if (res.code === 0) {
        toast.success('已审核通过，进入发放流程（已留痕并同步学生端）')
        this.approveDialog.visible = false
        this.detailVisible = false
        this.load()
      } else {
        toast.error(res.message)
      }
    },
    openReturn(row) {
      if (!this.can('campus.grant.return')) return
      this.returnDialog = { visible: true, submitting: false, row }
    },
    async submitReturn({ reason }) {
      this.returnDialog.submitting = true
      const res = await returnGrant(this.returnDialog.row.id, { reason })
      this.returnDialog.submitting = false
      if (res.code === 0) {
        toast.success('已退回补充，原因已原文同步学生端并留痕')
        this.returnDialog.visible = false
        this.detailVisible = false
        this.load()
      } else {
        toast.error(res.message)
      }
    },
    async batchApprove() {
      if (!this.can('campus.grant.batchReview')) return
      const res = await batchApproveGrants(this.selected)
      if (res.code === 0) toast.success(`批量通过 ${res.data.count} 条资助申请（跳过非待审核状态），已留痕`)
      else toast.error(res.message)
      this.selected = []
      this.load()
    },
    async openExport() {
      if (!this.can('campus.grant.export')) return
      if (!this.exportOpts) {
        const res = await getExportOptions('grantList')
        if (res.code === 0) this.exportOpts = res.data
      }
      this.exportVisible = true
    },
    exportFn(payload) {
      return createExport('grantList', payload)
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.gav-danger {
  color: var(--danger-600);
}
.mp-link + .mp-link {
  margin-left: var(--space-2);
}
.gav-sec {
  margin-bottom: var(--space-4);
}
.gav-sec__title {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
  margin-bottom: var(--space-2);
}
.gav-list {
  margin: 0;
  padding-left: var(--space-5);
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}
.gav-warn {
  font-size: var(--font-size-sm);
  color: var(--warning-700);
  background: var(--warning-50);
  border: 1px solid var(--warning-100);
  border-radius: var(--radius-base);
  padding: var(--space-2) var(--space-3);
}
</style>
