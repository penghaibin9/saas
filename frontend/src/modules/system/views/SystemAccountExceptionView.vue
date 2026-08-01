<template>
  <ModulePageShell
    title="账号异常排查"
    subtitle="锁定 / 停用 / 长期未登录 / 强制改密 · 只读排查台账"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="mp-stack">
      <div class="ae-tabs" role="tablist" aria-label="账号类型">
        <button class="mp-link" :class="{ 'is-active': accountType === 'STAFF' }" @click="switchType('STAFF')">教职工异常</button>
        <button class="mp-link" :class="{ 'is-active': accountType === 'STUDENT' }" @click="switchType('STUDENT')">学生异常</button>
      </div>
      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" title="暂无异常账号" description="当前范围内没有需要处理的账号异常" />
      <DataTable
        v-else
        :columns="columns"
        :rows="rows"
        row-key="id"
        :pagination="pagination"
        @page-change="onPageChange"
      >
        <template #cell-user="{ row }">
          <div class="mp-cell-main">{{ row.name }}</div>
          <div class="mp-cell-sub">{{ row.userNo }}</div>
        </template>
        <template #cell-status="{ row }">
          <StatusTag :type="statusTone(row.status)" :label="row.statusLabel || row.status" dot />
        </template>
        <template #cell-reasons="{ row }">
          <span v-for="r in (row.exceptionReasons || [])" :key="r" class="ae-tag">{{ r }}</span>
        </template>
      </DataTable>
    </div>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { systemApi } from '@/modules/system/api/system.api'

export default {
  name: 'SystemAccountExceptionView',
  components: { ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      accountType: 'STAFF',
      rows: [],
      pagination: { page: 1, pageSize: 20, total: 0 },
      columns: [
        { key: 'user', title: '账号' },
        { key: 'orgName', title: '组织' },
        { key: 'status', title: '状态' },
        { key: 'reasons', title: '异常原因' },
        { key: 'lastLoginAt', title: '最近登录' }
      ]
    }
  },
  created() { this.load() },
  methods: {
    statusTone(s) {
      return { ACTIVE: 'success', DISABLED: 'default', LOCKED: 'danger', PENDING: 'warning' }[s] || 'warning'
    },
    onPageChange(page) {
      this.pagination.page = page
      this.load()
    },
    switchType(type) {
      if (this.accountType === type) return
      this.accountType = type
      this.pagination.page = 1
      this.load()
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await systemApi.listAccountExceptions({
        accountType: this.accountType,
        page: this.pagination.page,
        pageSize: this.pagination.pageSize
      })
      if (res.code === 0) {
        this.rows = res.data.list || []
        this.pagination.total = res.data.total || 0
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
.ae-tag {
  display: inline-block;
  margin: 0 4px 4px 0;
  padding: 2px 8px;
  border-radius: var(--radius-full);
  background: var(--warning-50);
  color: var(--warning-700);
  font-size: var(--font-size-xs);
}
.ae-tabs {
  display: flex;
  gap: var(--space-3);
  border-bottom: 1px solid var(--border-light);
  padding-bottom: var(--space-2);
}
.ae-tabs .is-active {
  color: var(--primary-600);
  font-weight: var(--font-weight-semibold);
}
</style>
