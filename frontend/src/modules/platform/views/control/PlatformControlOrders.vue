<template>
  <ModulePageShell title="订单与开通" subtitle="人工录单 → 标记支付 → 自动开通/续期（试用转正式）" role-name="平台超级管理员" data-scope-name="全平台（跨租户）">
    <template #actions>
      <AppButton variant="primary" @click="createVisible = true">+ 录入订单</AppButton>
    </template>
    <LoadingState v-if="loading" text="正在加载订单…" />
    <template v-else>
      <DataTable :columns="columns" :rows="rows" row-key="orderNo">
        <template #cell-amount="{ row }">￥{{ (row.amount || 0).toLocaleString() }}</template>
        <template #cell-status="{ row }">
          <StatusTag :type="statusType(row.status)" :label="statusLabel(row.status)" />
          <div v-if="row.repairTaskRequired" class="pcod__repair">已支付 · 激活待修复</div>
        </template>
        <template #cell-endAt="{ row }">{{ (row.endAt || '').slice(0, 10) || '—' }}</template>
        <template #cell-actions="{ row }">
          <div class="pcod__ops">
            <AppButton v-if="row.status === 'unpaid'" variant="primary" @click="openAction(row, 'mark-paid')">标记已支付</AppButton>
            <AppButton v-if="row.status === 'unpaid'" variant="danger" @click="openAction(row, 'cancel')">取消</AppButton>
            <AppButton v-if="row.repairTaskRequired" variant="warning" @click="openAction(row, 'repair-activation')">修复激活</AppButton>
          </div>
        </template>
      </DataTable>
      <EmptyState v-if="!rows.length" text="暂无订单" />
    </template>

    <AppDrawer :visible="createVisible" title="人工录入订单" mode="modal" size="large" @update:visible="createVisible = $event">
      <div class="pcod__form">
        <label class="pcod__field"><span>租户</span>
          <AppSelect v-model="form.tenantId" :options="tenants" label-key="tenantName" value-key="tenantId" />
        </label>
        <label class="pcod__field"><span>套餐</span>
          <AppSelect v-model="form.packageCode" :options="packageOptions" />
        </label>
        <label class="pcod__field"><span>金额（元）</span><AppNumberInput v-model="form.amount" :min="0.01" :precision="2" /></label>
        <label class="pcod__field"><span>备注</span><AppTextInput v-model="form.remark" /></label>
        <div class="pcod__form-ops">
          <AppButton variant="primary" :loading="saving" @click="submit">创建（未支付）</AppButton>
          <AppButton @click="createVisible = false">取消</AppButton>
        </div>
      </div>
    </AppDrawer>

    <AppDrawer
      :visible="actionForm.visible"
      :title="actionTitle"
      mode="modal"
      size="medium"
      @update:visible="actionForm.visible = $event"
    >
      <div class="pcod__form">
        <p class="pcod__action-note">
          {{ actionNote }}
        </p>
        <label class="pcod__field"><span>订单号</span><strong>{{ actionForm.row?.orderNo || '—' }}</strong></label>
        <label class="pcod__field"><span>变更原因（至少 5 个字符）</span>
          <AppTextInput v-model="actionForm.reason" placeholder="请输入可审计的变更原因" />
        </label>
        <div class="pcod__form-ops">
          <AppButton
            :variant="actionForm.action === 'cancel' ? 'danger' : 'primary'"
            :loading="actionForm.saving"
            @click="submitAction"
          >
            {{ actionButtonText }}
          </AppButton>
          <AppButton :disabled="actionForm.saving" @click="actionForm.visible = false">返回</AppButton>
        </div>
      </div>
    </AppDrawer>
  </ModulePageShell>
</template>

<script>
import { AppButton, AppDrawer } from '@/components/ui'
import { DataTable, EmptyState, LoadingState, ModulePageShell, StatusTag } from '@/components/business'
import { AppNumberInput, AppSelect, AppTextInput } from '@/components/common'
import { platformControlApi } from '@/modules/platform/api/platformControl.api'
import { toast } from '@/utils/toast'

const STATUS = { unpaid: ['warning', '未支付'], paid: ['success', '已支付'], refunded: ['default', '已退款'], cancelled: ['default', '已取消'] }

export default {
  name: 'PlatformControlOrders',
  components: { AppButton, AppDrawer, DataTable, EmptyState, LoadingState, ModulePageShell, StatusTag, AppNumberInput, AppSelect, AppTextInput },
  data() {
    return {
      loading: true,
      saving: false,
      rows: [],
      tenants: [],
      packageOptions: [
        { value: 'basic', label: '基础版' },
        { value: 'standard', label: '标准版' },
        { value: 'professional', label: '专业版' },
        { value: 'private', label: '私有化版' }
      ],
      createVisible: false,
      queryTenantConsumed: false,
      form: { tenantId: '', packageCode: 'standard', amount: 49800, remark: '' },
      actionForm: { visible: false, row: null, action: '', reason: '', saving: false },
      columns: [
        { key: 'orderNo', title: '订单号', width: '170px' },
        { key: 'tenantName', title: '学校', width: '190px' },
        { key: 'packageCode', title: '套餐', width: '110px' },
        { key: 'amount', title: '金额', width: '110px' },
        { key: 'status', title: '状态', width: '90px' },
        { key: 'endAt', title: '服务期至', width: '110px' },
        { key: 'actions', title: '操作', width: '200px' }
      ]
    }
  },
  created() {
    this.load()
  },
  computed: {
    actionTitle() {
      return { 'mark-paid': '确认订单已支付', cancel: '取消订单', 'repair-activation': '修复订单授权激活' }[this.actionForm.action] || '订单操作'
    },
    actionNote() {
      return {
        'mark-paid': '确认后将以该订单为商业 Authority 自动生效套餐、有效期与授权。',
        cancel: '取消后保留订单与审计流水，不会授予正式权益。',
        'repair-activation': '支付事实已经入账；本次只重试该订单对应的套餐与有效期激活，并保留修复审计。'
      }[this.actionForm.action] || ''
    },
    actionButtonText() {
      return { 'mark-paid': '确认已支付并生效', cancel: '确认取消订单', 'repair-activation': '确认修复激活' }[this.actionForm.action] || '确认'
    }
  },
  methods: {
    async load() {
      this.loading = true
      const [orders, tenants] = await Promise.all([
        platformControlApi.listOrders(),
        platformControlApi.listTenants()
      ])
      this.loading = false
      if (orders.code === 0) this.rows = orders.data.list || []
      else toast.error(orders.message)
      if (tenants.code === 0) {
        this.tenants = tenants.data.list || []
        const requestedTenantId = String(this.$route.query.tenantId || '')
        if (!this.queryTenantConsumed && requestedTenantId && this.tenants.some((item) => String(item.tenantId) === requestedTenantId)) {
          this.form.tenantId = requestedTenantId
          this.createVisible = true
          this.queryTenantConsumed = true
        } else if (!this.form.tenantId && this.tenants.length) this.form.tenantId = this.tenants[0].tenantId
      }
    },
    statusType(s) {
      return (STATUS[s] || ['default', s])[0]
    },
    statusLabel(s) {
      return (STATUS[s] || ['default', s])[1]
    },
    async submit() {
      if (!this.form.tenantId) {
        toast.error('请选择租户')
        return
      }
      this.saving = true
      const res = await platformControlApi.createOrder({ ...this.form })
      this.saving = false
      if (res.code === 0) {
        toast.success('订单已创建：' + res.data.orderNo)
        this.createVisible = false
        this.load()
      } else {
        toast.error(res.message)
      }
    },
    openAction(row, action) {
      this.actionForm = { visible: true, row, action, reason: '', saving: false }
    },
    async submitAction() {
      const reason = this.actionForm.reason.trim()
      if (reason.length < 5) {
        toast.error('变更原因至少 5 个字符')
        return
      }
      const row = this.actionForm.row
      const action = this.actionForm.action
      this.actionForm.saving = true
      const res = await platformControlApi.orderAction(row.orderNo, action, { expectedVersion: Number(row.version || 1), reason })
      this.actionForm.saving = false
      if (res.code === 0) {
        if (res.data?.repairTaskRequired) toast.warning('支付事实已入账，但授权激活失败；交付验收已阻断，请按待修复项处理')
        else toast.success({ 'mark-paid': '已入账并自动开通/续期', cancel: '已取消', 'repair-activation': '订单授权激活已修复' }[action] || '操作成功')
        this.actionForm.visible = false
        this.load()
      } else {
        toast.error(res.message)
      }
    }
  }
}
</script>

<style scoped>
.pcod__ops {
  display: flex;
  gap: var(--space-1);
}
.pcod__repair { margin-top: 4px; color: var(--color-danger); font-size: var(--font-size-xs); font-weight: 700; }
.pcod__form {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
.pcod__field {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}
.pcod__input {
  height: 34px;
  padding: 0 10px;
  border: 1px solid var(--card-b);
  border-radius: 9px;
  background: rgba(255, 255, 255, 0.85);
  color: var(--t1);
  font-size: 13px;
  font-family: inherit;
}
.pcod__input:focus {
  outline: none;
  border-color: var(--glow);
}
.pcod__form-ops {
  display: flex;
  gap: var(--space-2);
  margin-top: var(--space-2);
}
.pcod__action-note {
  margin: 0;
  padding: var(--space-3);
  border-radius: 9px;
  background: var(--color-primary-soft);
  color: var(--text-secondary);
  line-height: 1.6;
}
</style>
