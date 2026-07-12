<template>
  <ModulePageShell
    title="订单 / 续费 / 授权"
    :subtitle="'共 ' + pagination.total + ' 笔订单 · 金额默认脱敏为区间'"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <ModuleToolbar :actions="toolbarActions" @action="onToolbar" />
    </template>

    <div class="mp-stack">
      <div v-if="expiringCount" class="od-notice">
        ⏰ {{ expiringCount }} 个租户 30 天内到期，请及时跟进续费。
        <button class="mp-link" @click="$router.push('/admin/platform/tenants?status=EXPIRING')">查看到期租户 →</button>
      </div>

      <div class="mp-tabs">
        <button class="mp-tab" :class="{ 'is-active': tab === 'orders' }" @click="tab = 'orders'">订单列表</button>
        <button class="mp-tab" :class="{ 'is-active': tab === 'auth' }" @click="switchAuth">授权记录</button>
      </div>

      <template v-if="tab === 'orders'">
        <AdvancedFilter v-model="filters" :fields="filterFields" @search="search" @reset="reset" />

        <ErrorState v-if="error" :description="error" @retry="load" />
        <LoadingState v-else-if="loading" />
        <EmptyState v-else-if="!rows.length" title="没有符合条件的订单" description="可调整筛选条件或新增订单记录" />
        <DataTable v-else :columns="columns" :rows="rows" row-key="id" :pagination="pagination" @page-change="onPageChange">
          <template #cell-order="{ row }">
            <div class="mp-cell-main">{{ row.orderNo }}</div>
            <div class="mp-cell-sub">{{ row.createdAt }} · {{ row.createdBy }}</div>
          </template>
          <template #cell-typeLabel="{ row }">
            <StatusTag :type="row.type === 'RENEW' ? 'processing' : row.type === 'UPGRADE' ? 'info' : 'default'" :label="row.typeLabel" />
          </template>
          <template #cell-status="{ row }">
            <StatusTag :type="row.status === 'ACTIVE' ? 'success' : row.status === 'VOID' ? 'default' : 'warning'" :label="row.statusLabel" dot />
          </template>
          <template #cell-actions="{ row }">
            <button class="mp-link" @click="openDetail(row)">查看</button>
            <button
              v-if="row.status === 'PENDING_ACTIVATE'"
              class="mp-link"
              :class="{ 'is-disabled': !can('activateOrder') }"
              :title="reason('activateOrder')"
              @click="askActivate(row)"
            >授权开通</button>
            <button
              v-if="row.status === 'ACTIVE'"
              class="mp-link"
              :class="{ 'is-disabled': !can('renewOrder') }"
              :title="reason('renewOrder')"
              @click="openCreate(row)"
            >续费</button>
            <button class="mp-link" :class="{ 'is-disabled': !can('editOrderRemark') }" :title="reason('editOrderRemark')" @click="openRemark(row)">备注</button>
            <button
              v-if="row.status === 'PENDING_ACTIVATE'"
              class="mp-link od-danger"
              :class="{ 'is-disabled': !can('voidOrder') }"
              :title="reason('voidOrder')"
              @click="askVoid(row)"
            >作废</button>
          </template>
        </DataTable>
      </template>

      <template v-else>
        <LoadingState v-if="authLoading" />
        <EmptyState v-else-if="!authRows.length" title="暂无授权记录" description="订单开通 / 模块开关 / 到期锁写都会生成授权流水" />
        <DataTable v-else :columns="authColumns" :rows="authRows" row-key="id" />
      </template>
    </div>

    <!-- 新增订单 -->
    <AppDrawer v-model:visible="form.open" title="新增订单记录">
      <FormFields v-model="form.value" :fields="formFields" :errors="form.errors" />
      <p class="mp-note" style="margin-top: var(--space-3)">合同金额录入后仅财务角色可见明文，本页展示脱敏区间；开通动作需在订单创建后单独执行并留痕。</p>
      <template #footer>
        <AppButton variant="ghost" @click="form.open = false">取消</AppButton>
        <AppButton variant="primary" :loading="form.submitting" @click="submitForm">创建订单（待开通）</AppButton>
      </template>
    </AppDrawer>

    <!-- 订单详情 -->
    <AppDrawer v-model:visible="detail.open" :title="'订单详情 · ' + (detail.data ? detail.data.orderNo : '')">
      <LoadingState v-if="detail.loading" />
      <template v-else-if="detail.data">
        <div class="mp-kv"><span class="mp-kv__k">租户</span><span class="mp-kv__v">{{ detail.data.tenantName }}</span></div>
        <div class="mp-kv"><span class="mp-kv__k">类型 / 套餐</span><span class="mp-kv__v">{{ detail.data.typeLabel }} · {{ detail.data.packageName }}</span></div>
        <div class="mp-kv"><span class="mp-kv__k">金额</span><span class="mp-kv__v">{{ detail.data.amountMasked }}</span></div>
        <div class="mp-kv"><span class="mp-kv__k">服务期</span><span class="mp-kv__v">{{ detail.data.period }}</span></div>
        <div class="mp-kv"><span class="mp-kv__k">状态</span><span class="mp-kv__v">{{ detail.data.statusLabel }}</span></div>
        <div class="mp-kv"><span class="mp-kv__k">备注</span><span class="mp-kv__v">{{ detail.data.remark || '—' }}</span></div>
        <h4 class="od-sec">操作留痕</h4>
        <table class="mp-audit">
          <thead><tr><th>操作人</th><th>动作</th><th>影响</th><th>时间</th></tr></thead>
          <tbody>
            <tr v-for="(a, i) in detail.data.auditTrail" :key="i">
              <td class="is-who">{{ a.who }}</td><td>{{ a.action }}</td><td>{{ a.affected }}</td><td>{{ a.time }}</td>
            </tr>
          </tbody>
        </table>
      </template>
    </AppDrawer>

    <!-- 备注编辑 -->
    <AppDrawer v-model:visible="remark.open" :title="'编辑备注 · ' + remark.orderNo">
      <textarea v-model="remark.value" class="mp-textarea" rows="4" placeholder="如：合同走款中 / 学校预算周期说明" />
      <template #footer>
        <AppButton variant="ghost" @click="remark.open = false">取消</AppButton>
        <AppButton variant="primary" :loading="remark.submitting" @click="submitRemark">保存备注并留痕</AppButton>
      </template>
    </AppDrawer>

    <AppConfirmDialog
      v-model:visible="confirmActivate"
      type="primary"
      :title="'授权开通订单 ' + (actionRow ? actionRow.orderNo : '') + '？'"
      :message="actionRow ? '开通后租户「' + actionRow.tenantName + '」有效期同步至 ' + (actionRow.period.split('~')[1] || '').trim() + '，模块授权即时生效。' : ''"
      confirm-text="确认开通并留痕"
      :submitting="confirmSubmitting"
      @confirm="doActivate"
    />
    <AppConfirmDialog
      v-model:visible="confirmVoid"
      type="danger"
      :title="'作废订单 ' + (actionRow ? actionRow.orderNo : '') + '？'"
      message="作废为逻辑删除：订单流水保留可追溯，不影响租户现有授权。"
      confirm-text="确认作废并留痕"
      require-reason
      reason-label="作废原因"
      :submitting="confirmSubmitting"
      @confirm="doVoid"
    />

    <ExportDialog
      v-model:visible="exportOpen"
      title="导出订单"
      :options="ctx.exportOptions.orders"
      :data-scope-name="ctx.dataScope.scopeName"
      :run-export="api.exportOrders"
    />
  </ModulePageShell>
</template>

<script>
/**
 * 订单 / 续费 / 授权（/admin/platform/orders）：
 * 新增订单 / 查看 / 备注编辑 / 授权开通（同步租户有效期）/ 续费 / 作废留痕 / 到期提醒 / 授权流水 / 导出。
 */
import {
  ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable,
  StatusTag, LoadingState, ErrorState, EmptyState
} from '@/components/business'
import { AppButton } from '@/components/ui'
import AppDrawer from '@/components/ui/AppDrawer.vue'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import FormFields from '@/modules/platform/components/FormFields.vue'
import ExportDialog from '@/modules/platform/components/ExportDialog.vue'
import { platformApi } from '@/modules/platform/api/platform.api'
import { toast } from '@/utils/toast'

const EMPTY_FILTERS = () => ({ keyword: '', type: '', status: '' })

export default {
  name: 'PlatformOrderView',
  components: {
    ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag,
    LoadingState, ErrorState, EmptyState, AppButton, AppDrawer, AppConfirmDialog, FormFields, ExportDialog
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      api: platformApi,
      tab: 'orders',
      loading: true,
      error: '',
      rows: [],
      tenantOptions: [],
      authRows: [],
      authLoading: false,
      expiringCount: 1,
      filters: EMPTY_FILTERS(),
      pagination: { page: 1, pageSize: 10, total: 0 },
      columns: [
        { key: 'order', title: '订单' },
        { key: 'tenantName', title: '租户' },
        { key: 'typeLabel', title: '类型' },
        { key: 'packageName', title: '套餐' },
        { key: 'amountMasked', title: '金额（脱敏）' },
        { key: 'period', title: '服务期' },
        { key: 'status', title: '状态' },
        { key: 'actions', title: '操作', width: '210px' }
      ],
      authColumns: [
        { key: 'time', title: '时间', width: '150px' },
        { key: 'tenantName', title: '租户' },
        { key: 'moduleName', title: '模块 / 套餐' },
        { key: 'actionLabel', title: '动作' },
        { key: 'validUntil', title: '有效期至' },
        { key: 'operator', title: '操作人' }
      ],
      form: { open: false, value: {}, errors: {}, submitting: false },
      detail: { open: false, loading: false, data: null },
      remark: { open: false, id: '', orderNo: '', value: '', submitting: false },
      confirmActivate: false,
      confirmVoid: false,
      actionRow: null,
      confirmSubmitting: false,
      exportOpen: false
    }
  },
  computed: {
    filterFields() {
      return [
        { key: 'keyword', label: '关键词', type: 'text', placeholder: '订单号 / 租户' },
        { key: 'type', label: '订单类型', type: 'select', options: this.ctx.statusOptions.orderTypes },
        { key: 'status', label: '状态', type: 'select', options: this.ctx.statusOptions.orderStatus }
      ]
    },
    toolbarActions() {
      const pa = this.ctx.permissionActions
      return [
        { key: 'createOrder', label: '＋ 新增订单', variant: 'primary' },
        { key: 'exportOrders', label: '⇩ 导出订单' }
      ]
        .filter((a) => pa[a.key] && pa[a.key].visible)
        .map((a) => ({ ...a, disabled: !pa[a.key].allowed, disabledReason: pa[a.key].reason }))
    },
    formFields() {
      return [
        { key: 'tenantId', label: '租户', type: 'select', required: true, options: this.tenantOptions },
        { key: 'type', label: '订单类型', type: 'select', required: true, options: this.ctx.statusOptions.orderTypes },
        { key: 'packageName', label: '套餐', type: 'select', options: this.ctx.filterOptions.packages.map((p) => ({ value: p.label, label: p.label })) },
        { key: 'period', label: '服务期', placeholder: '2026-08-01 ~ 2027-08-01' },
        { key: 'remark', label: '备注', type: 'textarea', full: true }
      ]
    }
  },
  async created() {
    this.load()
    const res = await platformApi.getTenantOptions()
    if (res.code === 0) this.tenantOptions = res.data
    if (this.$route.query.action === 'create') this.openCreate(null)
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
      this.load()
    },
    onToolbar(key) {
      if (key === 'createOrder') this.openCreate(null)
      if (key === 'exportOrders') this.exportOpen = true
    },
    async switchAuth() {
      this.tab = 'auth'
      this.authLoading = true
      const res = await platformApi.getAuthorizations()
      this.authLoading = false
      if (res.code === 0) this.authRows = res.data
    },
    openCreate(fromOrder) {
      if (!this.can('createOrder')) return
      this.form = {
        open: true,
        value: fromOrder
          ? { tenantId: fromOrder.tenantId, type: 'RENEW', packageName: fromOrder.packageName, period: '', remark: '续费自 ' + fromOrder.orderNo }
          : { tenantId: '', type: '', packageName: '', period: '', remark: '' },
        errors: {},
        submitting: false
      }
    },
    async submitForm() {
      const errors = FormFields.validateRequired(this.formFields, this.form.value)
      this.form.errors = errors
      if (Object.keys(errors).length) return
      this.form.submitting = true
      const res = await platformApi.createOrder(this.form.value)
      this.form.submitting = false
      if (res.code === 0) {
        toast.success('订单已创建（待开通），已写入审计日志')
        this.form.open = false
        this.load()
      } else {
        toast.error(res.message)
      }
    },
    async openDetail(row) {
      this.detail = { open: true, loading: true, data: null }
      const res = await platformApi.getOrderDetail(row.id)
      this.detail.loading = false
      if (res.code === 0) this.detail.data = res.data
    },
    openRemark(row) {
      if (!this.can('editOrderRemark')) return
      this.remark = { open: true, id: row.id, orderNo: row.orderNo, value: row.remark, submitting: false }
    },
    async submitRemark() {
      this.remark.submitting = true
      const res = await platformApi.updateOrderRemark(this.remark.id, this.remark.value)
      this.remark.submitting = false
      if (res.code === 0) {
        toast.success('备注已保存（前后值已留痕）')
        this.remark.open = false
        this.load()
      } else {
        toast.error(res.message)
      }
    },
    askActivate(row) {
      if (!this.can('activateOrder')) return
      this.actionRow = row
      this.confirmActivate = true
    },
    askVoid(row) {
      if (!this.can('voidOrder')) return
      this.actionRow = row
      this.confirmVoid = true
    },
    async doActivate() {
      this.confirmSubmitting = true
      const res = await platformApi.activateOrder(this.actionRow.id)
      this.confirmSubmitting = false
      if (res.code === 0) {
        toast.success('订单已开通：租户有效期与模块授权已同步，已留痕')
        this.confirmActivate = false
        this.load()
      } else {
        toast.error(res.message)
      }
    },
    async doVoid({ reason }) {
      this.confirmSubmitting = true
      const res = await platformApi.voidOrder(this.actionRow.id, { reason })
      this.confirmSubmitting = false
      if (res.code === 0) {
        toast.success('订单已作废（流水保留），原因已留痕')
        this.confirmVoid = false
        this.load()
      } else {
        toast.error(res.message)
      }
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await platformApi.getOrders({ ...this.filters, page: this.pagination.page, pageSize: this.pagination.pageSize })
      if (res.code === 0) {
        this.rows = res.data.list
        this.pagination.total = res.data.total
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
.od-notice {
  font-size: var(--font-size-sm);
  color: var(--warning-700);
  background: var(--warning-50);
  border: 1px solid var(--warning-100);
  border-radius: var(--radius-base);
  padding: var(--space-2) var(--space-3);
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-wrap: wrap;
}
.od-danger {
  color: var(--danger-600);
}
.od-sec {
  margin: var(--space-4) 0 var(--space-2);
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
}
.mp-link + .mp-link {
  margin-left: var(--space-2);
}
</style>
