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
        </template>
        <template #cell-endAt="{ row }">{{ (row.endAt || '').slice(0, 10) || '—' }}</template>
        <template #cell-actions="{ row }">
          <div class="pcod__ops">
            <AppButton v-if="row.status === 'unpaid'" variant="primary" @click="act(row, 'mark-paid')">标记已支付</AppButton>
            <AppButton v-if="row.status === 'unpaid'" variant="danger" @click="act(row, 'cancel')">取消</AppButton>
          </div>
        </template>
      </DataTable>
      <EmptyState v-if="!rows.length" text="暂无订单" />
    </template>

    <AppDrawer :visible="createVisible" title="人工录入订单" @update:visible="createVisible = $event">
      <div class="pcod__form">
        <label class="pcod__field"><span>租户</span>
          <select v-model="form.tenantId" class="pcod__input">
            <option v-for="t in tenants" :key="t.tenantId" :value="t.tenantId">{{ t.tenantName }}</option>
          </select>
        </label>
        <label class="pcod__field"><span>套餐</span>
          <select v-model="form.packageCode" class="pcod__input">
            <option value="basic">基础版</option>
            <option value="standard">标准版</option>
            <option value="professional">专业版</option>
            <option value="private">私有化版</option>
          </select>
        </label>
        <label class="pcod__field"><span>金额（元）</span><input v-model.number="form.amount" type="number" class="pcod__input" /></label>
        <label class="pcod__field"><span>备注</span><input v-model.trim="form.remark" class="pcod__input" /></label>
        <div class="pcod__form-ops">
          <AppButton variant="primary" :loading="saving" @click="submit">创建（未支付）</AppButton>
          <AppButton @click="createVisible = false">取消</AppButton>
        </div>
      </div>
    </AppDrawer>
  </ModulePageShell>
</template>

<script>
import { AppButton, AppDrawer } from '@/components/ui'
import { DataTable, EmptyState, LoadingState, ModulePageShell, StatusTag } from '@/components/business'
import { platformControlApi } from '@/modules/platform/api/platformControl.api'
import { toast } from '@/utils/toast'

const STATUS = { unpaid: ['warning', '未支付'], paid: ['success', '已支付'], refunded: ['default', '已退款'], cancelled: ['default', '已取消'] }

export default {
  name: 'PlatformControlOrders',
  components: { AppButton, AppDrawer, DataTable, EmptyState, LoadingState, ModulePageShell, StatusTag },
  data() {
    return {
      loading: true,
      saving: false,
      rows: [],
      tenants: [],
      createVisible: false,
      form: { tenantId: '', packageCode: 'standard', amount: 49800, remark: '' },
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
        if (!this.form.tenantId && this.tenants.length) this.form.tenantId = this.tenants[0].tenantId
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
    async act(row, action) {
      const res = await platformControlApi.orderAction(row.orderNo, action)
      if (res.code === 0) {
        toast.success(action === 'mark-paid' ? '已入账并自动开通/续期' : '已取消')
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
</style>
