<template>
  <ModulePageShell title="租户学校管控" subtitle="学校档案 / 停用 / 试用 / 到期 / 容量；新校统一由可恢复 Provisioning SAGA 开通" role-name="平台超级管理员" data-scope-name="全平台（跨租户）">
    <template #actions>
      <AppButton variant="primary" @click="goProvisioning">+ 开通新学校</AppButton>
    </template>
    <div v-if="pickerHint" class="pct__hint">{{ pickerHint }}（点击行进入该学校的配置页）</div>
    <ModuleToolbar :actions="[]" :hint="`共 ${rows.length} 所学校`">
      <template #left>
        <input v-model.trim="keyword" class="pct__input" placeholder="搜索学校名 / 编码" @keyup.enter="load" />
        <select v-model="status" class="pct__input pct__input--sel" @change="load">
          <option value="">全部状态</option>
          <option value="trial">试用</option>
          <option value="active">正式</option>
          <option value="expired">已到期</option>
          <option value="disabled">已停用</option>
        </select>
        <AppButton @click="load">查询</AppButton>
      </template>
    </ModuleToolbar>
    <LoadingState v-if="loading" text="正在加载租户列表…" />
    <template v-else>
      <DataTable :columns="columns" :rows="rows" row-key="tenantId" row-clickable @row-click="goDetail">
        <template #cell-tenantName="{ row }">
          <div class="pct__name">{{ row.tenantName }}</div>
          <div class="pct__code">{{ row.tenantCode }} · {{ row.environment === 'demo' ? '演示环境' : '生产环境' }}</div>
        </template>
        <template #cell-status="{ row }">
          <StatusTag :type="statusType(row.status)" :label="statusLabel(row.status)" />
        </template>
        <template #cell-usage="{ row }">
          <span class="pct__usage">{{ row.studentCount }}/{{ row.maxStudents }} 生 · {{ row.userCount }}/{{ row.maxUsers }} 号</span>
        </template>
        <template #cell-expireAt="{ row }">{{ fmt(row.expireAt) }}</template>
        <template #cell-actions="{ row }">
          <div class="pct__ops">
            <AppButton v-if="row.status === 'disabled'" variant="ghost" @click.stop="act(row, 'enable')">启用</AppButton>
            <AppButton v-else variant="danger" @click.stop="act(row, 'disable')">停用</AppButton>
            <AppButton v-if="row.status === 'trial'" variant="ghost" @click.stop="act(row, 'extend-trial', { days: 7 })">延试用7天</AppButton>
            <AppButton v-if="row.status === 'trial' || row.status === 'expired'" variant="ghost" @click.stop="goOrder(row)">录订单 / 续费</AppButton>
            <AppButton v-if="row.tenantCode === 'demo-school'" variant="warning" @click.stop="act(row, 'reset-demo-data')">重置演示</AppButton>
            <AppButton v-if="row.tenantCode === 'sandbox-school'" variant="warning" @click.stop="resetSandbox(row)">恢复演示数据</AppButton>
          </div>
        </template>
      </DataTable>
      <EmptyState v-if="!rows.length" text="没有符合条件的学校" />
    </template>

  </ModulePageShell>
</template>

<script>
import { AppButton } from '@/components/ui'
import { DataTable, EmptyState, LoadingState, ModulePageShell, ModuleToolbar, StatusTag } from '@/components/business'
import { platformControlApi } from '@/modules/platform/api/platformControl.api'
import { toast } from '@/utils/toast'

const STATUS = {
  trial: ['warning', '试用中'],
  active: ['success', '正式'],
  expired: ['danger', '已到期'],
  disabled: ['default', '已停用']
}

export default {
  name: 'PlatformControlTenants',
  components: { AppButton, DataTable, EmptyState, LoadingState, ModulePageShell, ModuleToolbar, StatusTag },
  props: {
    targetTab: { type: String, default: '' }
  },
  data() {
    return {
      loading: true,
      rows: [],
      keyword: '',
      status: '',
      columns: [
        { key: 'tenantName', title: '学校', width: '240px' },
        { key: 'status', title: '状态', width: '90px' },
        { key: 'packageName', title: '套餐', width: '90px' },
        { key: 'usage', title: '用量（学生/账号）', width: '170px' },
        { key: 'expireAt', title: '到期时间', width: '120px' },
        { key: 'actions', title: '操作', width: '300px' }
      ]
    }
  },
  computed: {
    pickerHint() {
      const map = {
        features: '功能开关按学校配置',
        rules: '规则中心按学校配置',
        workflows: '审批流按学校配置',
        brands: '品牌按学校配置',
        users: '账号按学校管理'
      }
      return map[this.targetTab] || ''
    }
  },
  created() {
    this.load()
  },
  methods: {
    async load() {
      this.loading = true
      const res = await platformControlApi.listTenants({ keyword: this.keyword, status: this.status })
      this.loading = false
      if (res.code === 0) {
        this.rows = res.data.list || []
      } else {
        toast.error(res.message)
      }
    },
    statusType(s) {
      return (STATUS[s] || ['default', s])[0]
    },
    statusLabel(s) {
      return (STATUS[s] || ['default', s])[1]
    },
    fmt(v) {
      return v ? String(v).replace('T', ' ').slice(0, 10) : '—'
    },
    goDetail(row) {
      const tab = this.targetTab || 'info'
      this.$router.push(`/admin/platform/tenants/${row.tenantId}?tab=${tab}`)
    },
    goProvisioning() {
      this.$router.push('/admin/platform/provisioning?create=1')
    },
    goOrder(row) {
      this.$router.push(`/admin/platform/orders?tenantId=${row.tenantId}`)
    },
    async act(row, action, body = {}) {
      if (action === 'reset-demo-data') {
        const res = await platformControlApi.tenantAction(row.tenantId, action, body)
        if (res.code === 0) { toast.success(res.message || '操作成功'); this.load() }
        else toast.error(res.message)
        return
      }
      const reason = window.prompt('请输入本次变更原因（至少 5 个字符）')
      if (!reason || reason.trim().length < 5) return
      const payload = { ...body, reason: reason.trim(), expectedVersion: Number(row.version || 0) }
      const preview = await platformControlApi.previewTenantTransition(row.tenantId, action, payload)
      if (preview.code !== 0) return toast.error(preview.message)
      const warnings = (preview.data.warnings || []).join('；')
      if (!window.confirm(`${preview.data.fromStatus} → ${preview.data.toStatus}${warnings ? `\n${warnings}` : ''}\n确认执行？`)) return
      const res = await platformControlApi.applyTenantTransition(row.tenantId, action, payload)
      if (res.code === 0) { toast.success('操作成功'); this.load() }
      else toast.error(res.message)
    },
    async resetSandbox(row) {
      const confirmed = window.confirm(`确认恢复「${row.tenantName}」的演示数据？\n\n现场新增数据会被清理，预置流程数据、账号和权限会恢复。其他学校不受影响。`)
      if (!confirmed) return
      const res = await platformControlApi.resetSandboxData(row.tenantId)
      if (res.code === 0) {
        toast.success(res.message || '演示数据已恢复')
        this.load()
      } else {
        toast.error(res.message)
      }
    }
  }
}
</script>

<style scoped>
.pct__hint {
  padding: var(--space-2) var(--space-3);
  border-radius: 9px;
  background: var(--pri-bg);
  color: var(--pri);
  font-size: var(--font-size-sm);
}
.pct__input {
  height: 34px;
  padding: 0 10px;
  border: 1px solid var(--card-b);
  border-radius: 9px;
  background: rgba(255, 255, 255, 0.85);
  color: var(--t1);
  font-size: 13px;
  font-family: inherit;
  min-width: 0;
}
.pct__input:focus {
  outline: none;
  border-color: var(--glow);
}
.pct__input--sel {
  width: 110px;
}
.pct__name {
  font-weight: var(--font-weight-medium);
  color: var(--t1);
}
.pct__code {
  font-size: 12px;
  color: var(--text-tertiary);
}
.pct__usage {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}
.pct__ops {
  display: flex;
  gap: var(--space-1);
  flex-wrap: wrap;
}
</style>
