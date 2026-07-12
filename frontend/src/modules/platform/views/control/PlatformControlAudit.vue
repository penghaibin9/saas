<template>
  <ModulePageShell title="全平台审计" subtitle="跨租户操作留痕：登录 / 导入导出 / 平台操作 / 权限拒绝，只增不删" role-name="平台超级管理员" data-scope-name="全平台（跨租户）">
    <ModuleToolbar :actions="[]" :hint="`共 ${total} 条`">
      <template #left>
        <select v-model="filters.tenantId" class="pca__input" @change="load(1)">
          <option value="">全部租户</option>
          <option v-for="t in tenants" :key="t.tenantId" :value="t.tenantId">{{ t.tenantName }}</option>
        </select>
        <input v-model.trim="filters.action" class="pca__input" placeholder="动作，如 LOGIN / PERMISSION_DENIED" @keyup.enter="load(1)" />
        <input v-model="filters.dateFrom" type="date" class="pca__input" @change="load(1)" />
        <input v-model="filters.dateTo" type="date" class="pca__input" @change="load(1)" />
        <AppButton @click="load(1)">查询</AppButton>
      </template>
    </ModuleToolbar>
    <LoadingState v-if="loading" text="正在加载审计…" />
    <template v-else>
      <DataTable :columns="columns" :rows="rows" row-key="auditId" :pagination="{ page, pageSize, total }" @page-change="load">
        <template #cell-result="{ row }">
          <StatusTag :type="row.result === 'SUCCESS' ? 'success' : row.result === 'DENIED' ? 'danger' : 'warning'" :label="row.result" />
        </template>
        <template #cell-occurredAt="{ row }">{{ (row.occurredAt || '').replace('T', ' ') }}</template>
      </DataTable>
      <EmptyState v-if="!rows.length" text="没有符合条件的审计记录" />
    </template>
  </ModulePageShell>
</template>

<script>
import { AppButton } from '@/components/ui'
import { DataTable, EmptyState, LoadingState, ModulePageShell, ModuleToolbar, StatusTag } from '@/components/business'
import { platformControlApi } from '@/modules/platform/api/platformControl.api'
import { toast } from '@/utils/toast'

export default {
  name: 'PlatformControlAudit',
  components: { AppButton, DataTable, EmptyState, LoadingState, ModulePageShell, ModuleToolbar, StatusTag },
  data() {
    return {
      loading: true,
      rows: [],
      tenants: [],
      total: 0,
      page: 1,
      pageSize: 20,
      filters: { tenantId: '', action: '', dateFrom: '', dateTo: '' },
      columns: [
        { key: 'occurredAt', title: '时间', width: '160px' },
        { key: 'tenantName', title: '租户', width: '160px' },
        { key: 'action', title: '动作', width: '160px' },
        { key: 'resource', title: '对象', width: '190px' },
        { key: 'operatorName', title: '操作人', width: '110px' },
        { key: 'ip', title: 'IP', width: '120px' },
        { key: 'result', title: '结果', width: '90px' }
      ]
    }
  },
  created() {
    this.init()
  },
  methods: {
    async init() {
      const t = await platformControlApi.listTenants()
      if (t.code === 0) this.tenants = t.data.list || []
      this.load(1)
    },
    async load(page) {
      this.loading = true
      this.page = page || this.page
      const params = { page: this.page, pageSize: this.pageSize }
      Object.entries(this.filters).forEach(([k, v]) => {
        if (v) params[k] = v
      })
      const res = await platformControlApi.listAuditLogs(params)
      this.loading = false
      if (res.code === 0) {
        this.rows = res.data.items || []
        this.total = res.data.total || 0
      } else {
        toast.error(res.message)
      }
    }
  }
}
</script>

<style scoped>
.pca__input {
  height: 34px;
  padding: 0 10px;
  border: 1px solid var(--card-b);
  border-radius: 9px;
  background: rgba(255, 255, 255, 0.85);
  color: var(--t1);
  font-size: 13px;
  font-family: inherit;
}
.pca__input:focus {
  outline: none;
  border-color: var(--glow);
}
</style>
