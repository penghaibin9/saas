<template>
  <ModulePageShell title="报到流程配置" subtitle="配置迎新各环节是否启用、是否必办（影响新生报到流程判定）" :role-name="roleName" :data-scope-name="dataScopeName" watermark-purpose="报到流程配置">
    <NoPermissionState v-if="noPermission" @back="$router.back()" />
    <template v-else>
      <ModuleToolbar :actions="[]" :hint="`共 ${rows.length} 个报到环节 · 调整全程留痕`" />
      <LoadingState v-if="loading" />
      <ErrorState v-else-if="error" :description="error" @retry="load" />
      <DataTable v-else :columns="tableColumns" :rows="rows" row-key="id">
        <template #cell-sortOrder="{ row }">
          <span>第 {{ row.sortOrder + 1 }} 步</span>
        </template>
        <template #cell-enabled="{ row }">
          <StatusTag :type="row.enabled ? 'success' : 'default'" :label="row.enabled ? '已启用' : '已停用'" dot />
        </template>
        <template #cell-required="{ row }">
          <StatusTag :type="row.required ? 'primary' : 'default'" :label="row.required ? '必办' : '选办'" />
        </template>
        <template #cell-actions="{ row }">
          <TableActionColumn :actions="rowActions(row)" @action="(key) => onRowAction(key, row)" />
        </template>
      </DataTable>
    </template>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, ModuleToolbar, DataTable, StatusTag, LoadingState, ErrorState } from '@/components/business'
import { TableActionColumn, NoPermissionState } from '@/modules/orientation/components'
import * as api from '@/modules/orientation/api/orientation.api'
import { toast } from '@/utils/toast'

export default {
  name: 'OrientationFlowConfigView',
  components: { ModulePageShell, ModuleToolbar, DataTable, StatusTag, LoadingState, ErrorState, TableActionColumn, NoPermissionState },
  data() { return { ctx: null, loading: true, error: '', rows: [] } },
  computed: {
    roleName() { return this.ctx?.currentRole?.roleName || '' },
    dataScopeName() { return this.ctx?.dataScope?.name || '' },
    perms() { return this.ctx?.permissionActions || {} },
    noPermission() { const p = this.perms['orientation.student.view']; return p ? !p.allowed : false },
    tableColumns() { return [{ key: 'sortOrder', title: '顺序' }, { key: 'stepName', title: '环节' }, { key: 'enabled', title: '启用' }, { key: 'required', title: '必办' }, { key: 'actions', title: '操作' }] }
  },
  async created() { const c = await api.getOrientationContext(); if (c.code === 0) this.ctx = c.data; await this.load() },
  methods: {
    async load() {
      this.loading = true; this.error = ''
      try { const res = await api.getFlowConfig(); if (res.code === 0) this.rows = res.data; else this.error = res.message } catch (e) { this.error = e.message || '加载失败' } finally { this.loading = false }
    },
    rowActions(row) { return [{ key: 'toggleEnabled', label: row.enabled ? '停用' : '启用' }, { key: 'toggleRequired', label: row.required ? '设为选办' : '设为必办' }] },
    async onRowAction(k, row) {
      const payload = k === 'toggleEnabled' ? { enabled: !row.enabled } : { required: !row.required }
      const res = await api.updateFlowConfig(row.id, payload)
      if (res.code === 0) { toast.success('已更新'); this.load() } else toast.error(res.message || '更新失败')
    }
  }
}
</script>
