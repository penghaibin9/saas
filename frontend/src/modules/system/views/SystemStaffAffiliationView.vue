<template>
  <ModulePageShell
    title="教职工任职归属查询"
    subtitle="班级辅导员 / 班主任 / 教学秘书 / 教师范围 · 当前为只读归属视图"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="mp-stack">
      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" title="暂无任职归属" description="可在组织与班级主数据中维护辅导员、班主任等岗位" />
      <DataTable v-else :columns="columns" :rows="rows" row-key="id">
        <template #cell-status="{ row }">
          <StatusTag :type="row.status === 'ACTIVE' ? 'success' : 'default'" :label="row.status || 'ACTIVE'" dot />
        </template>
      </DataTable>
    </div>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { systemApi } from '@/modules/system/api/system.api'

export default {
  name: 'SystemStaffAffiliationView',
  components: { ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      rows: [],
      columns: [
        { key: 'roleLabel', title: '岗位' },
        { key: 'orgName', title: '组织' },
        { key: 'orgType', title: '组织类型' },
        { key: 'staffName', title: '人员' },
        { key: 'staffKey', title: '人员标识' },
        { key: 'status', title: '状态' }
      ]
    }
  },
  created() { this.load() },
  methods: {
    async load() {
      this.loading = true
      this.error = ''
      const res = await systemApi.listStaffAffiliations()
      if (res.code === 0) this.rows = res.data.list || []
      else this.error = res.message
      this.loading = false
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
</style>
