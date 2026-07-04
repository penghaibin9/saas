<template>
  <ModulePageShell
    title="日志中心"
    subtitle="操作日志 / 登录日志 · 审计日志只增不删，IP 与账号固定脱敏"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <ModuleToolbar :actions="toolbarActions" @action="onToolbar">
        <template #right><span class="mp-note">导出动作本身也会写入审计日志</span></template>
      </ModuleToolbar>
    </template>

    <div class="mp-stack">
      <div class="mp-tabs">
        <button class="mp-tab" :class="{ 'is-active': tab === 'operation' }" @click="switchTab('operation')">操作日志</button>
        <button class="mp-tab" :class="{ 'is-active': tab === 'login' }" @click="switchTab('login')">登录日志</button>
      </div>

      <AdvancedFilter v-model="filters" :fields="filterFields" @search="search" @reset="reset" />

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" title="没有符合条件的日志" description="可调整筛选条件或扩大时间范围" />

      <!-- 操作日志 -->
      <DataTable
        v-else-if="tab === 'operation'"
        :columns="opColumns"
        :rows="rows"
        row-key="id"
        :pagination="pagination"
        @page-change="onPageChange"
      >
        <template #cell-who="{ row }">
          <div class="mp-cell-main">{{ row.who }}</div>
          <div class="mp-cell-sub">{{ row.roleName }}</div>
        </template>
        <template #cell-action="{ row }">
          <StatusTag :type="actionTone(row.action)" :label="row.actionLabel" />
        </template>
        <template #cell-result="{ row }">
          <StatusTag :type="row.result === 'SUCCESS' ? 'success' : row.result === 'DENIED' ? 'danger' : 'warning'" :label="row.resultLabel" dot />
        </template>
        <template #cell-actions="{ row }">
          <button class="mp-link" @click="openDetail(row)">详情</button>
        </template>
      </DataTable>

      <!-- 登录日志 -->
      <DataTable
        v-else
        :columns="loginColumns"
        :rows="rows"
        row-key="id"
        :pagination="pagination"
        @page-change="onPageChange"
      >
        <template #cell-user="{ row }">
          <div class="mp-cell-main">{{ row.userName }}</div>
          <div class="mp-cell-sub">{{ maskNo(row.userNo) }} · {{ row.roleName }}</div>
        </template>
        <template #cell-result="{ row }">
          <StatusTag :type="row.result === 'SUCCESS' ? 'success' : row.result === 'BLOCKED' ? 'danger' : 'warning'" :label="row.resultLabel" dot />
        </template>
        <template #cell-reason="{ row }">
          <span class="mp-cell-sub">{{ row.reason || '—' }}</span>
        </template>
      </DataTable>

      <p class="mp-note">
        合规说明：审计日志不提供删除 / 修改入口（含系统管理员）；日志中的 IP、账号已固定脱敏，明文仅存于安全存储并需专项审计流程调取。
      </p>
    </div>

    <!-- 操作日志详情：前后值对照 -->
    <AppDrawer v-model:visible="detail.open" title="操作日志详情">
      <template v-if="detail.row">
        <div class="mp-kv"><span class="mp-kv__k">时间</span><span class="mp-kv__v">{{ detail.row.time }}</span></div>
        <div class="mp-kv"><span class="mp-kv__k">操作人</span><span class="mp-kv__v">{{ detail.row.who }} · {{ detail.row.roleName }}</span></div>
        <div class="mp-kv"><span class="mp-kv__k">模块 / 动作</span><span class="mp-kv__v">{{ detail.row.moduleLabel }} · {{ detail.row.actionLabel }}</span></div>
        <div class="mp-kv"><span class="mp-kv__k">对象</span><span class="mp-kv__v">{{ detail.row.target }}</span></div>
        <div class="mp-kv"><span class="mp-kv__k">结果</span><span class="mp-kv__v">{{ detail.row.resultLabel }}</span></div>
        <div class="mp-kv"><span class="mp-kv__k">IP（脱敏）</span><span class="mp-kv__v">{{ detail.row.ip }}</span></div>
        <div class="mp-kv"><span class="mp-kv__k">摘要</span><span class="mp-kv__v">{{ detail.row.detail.summary }}</span></div>

        <template v-if="detail.row.detail.before || detail.row.detail.after">
          <h4 class="lg-sec">变更对照</h4>
          <div class="lg-diff">
            <div class="lg-diff__col lg-diff__col--before"><b>变更前</b>{{ detail.row.detail.before || '（空）' }}</div>
            <div class="lg-diff__col lg-diff__col--after"><b>变更后</b>{{ detail.row.detail.after || '（空）' }}</div>
          </div>
        </template>
        <div v-if="detail.row.detail.reason" class="mp-kv"><span class="mp-kv__k">操作原因</span><span class="mp-kv__v">{{ detail.row.detail.reason }}</span></div>
      </template>
    </AppDrawer>

    <ExportDialog
      v-model:visible="exportOpen"
      :title="tab === 'login' ? '导出登录日志' : '导出操作日志'"
      :options="ctx.exportOptions.logs"
      :data-scope-name="ctx.dataScope.scopeName"
      :run-export="(p) => api.exportLogs({ ...p, tab })"
    />
  </ModulePageShell>
</template>

<script>
/**
 * 日志中心（/admin/system/logs）：
 * 操作日志（详情含前后值对照）/ 登录日志 / 高级筛选 / 受控导出（脱敏+水印+留痕）/ 禁止删除。
 */
import {
  ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable,
  StatusTag, LoadingState, ErrorState, EmptyState
} from '@/components/business'
import AppDrawer from '@/components/ui/AppDrawer.vue'
import ExportDialog from '@/modules/system/components/ExportDialog.vue'
import { systemApi } from '@/modules/system/api/system.api'

const EMPTY_FILTERS = () => ({ keyword: '', module: '', action: '', result: '' })

export default {
  name: 'SystemLogView',
  components: {
    ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag,
    LoadingState, ErrorState, EmptyState, AppDrawer, ExportDialog
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      api: systemApi,
      tab: 'operation',
      loading: true,
      error: '',
      rows: [],
      filters: EMPTY_FILTERS(),
      pagination: { page: 1, pageSize: 10, total: 0 },
      opColumns: [
        { key: 'time', title: '时间', width: '150px' },
        { key: 'who', title: '操作人' },
        { key: 'moduleLabel', title: '模块' },
        { key: 'action', title: '动作' },
        { key: 'target', title: '对象' },
        { key: 'result', title: '结果' },
        { key: 'ip', title: 'IP（脱敏）' },
        { key: 'actions', title: '操作', width: '70px' }
      ],
      loginColumns: [
        { key: 'time', title: '时间', width: '150px' },
        { key: 'user', title: '账号' },
        { key: 'result', title: '结果' },
        { key: 'reason', title: '说明' },
        { key: 'ip', title: 'IP（脱敏）' },
        { key: 'location', title: '地点' },
        { key: 'device', title: '设备' }
      ],
      detail: { open: false, row: null },
      exportOpen: false
    }
  },
  computed: {
    filterFields() {
      const o = this.ctx
      const base = [{ key: 'keyword', label: '关键词', type: 'text', placeholder: this.tab === 'login' ? '姓名 / 工号' : '操作人 / 对象' }]
      if (this.tab === 'operation') {
        base.push(
          { key: 'module', label: '模块', type: 'select', options: o.filterOptions.logModules },
          { key: 'action', label: '动作', type: 'select', options: o.filterOptions.logActions },
          { key: 'result', label: '结果', type: 'select', options: o.statusOptions.opResult }
        )
      } else {
        base.push({ key: 'result', label: '结果', type: 'select', options: o.statusOptions.loginResult })
      }
      return base
    },
    toolbarActions() {
      const pa = this.ctx.permissionActions
      return [{ key: 'exportLogs', label: '⇩ 导出日志' }]
        .filter((a) => pa[a.key] && pa[a.key].visible)
        .map((a) => ({ ...a, disabled: !pa[a.key].allowed, disabledReason: pa[a.key].reason }))
    }
  },
  created() {
    if (this.$route.query.tab === 'login') this.tab = 'login'
    this.load()
  },
  methods: {
    maskNo(v) {
      return v && v.length > 4 ? v.slice(0, 4) + '****' + v.slice(-2) : v
    },
    actionTone(action) {
      return { CREATE: 'processing', UPDATE: 'info', DISABLE: 'warning', GRANT: 'danger', EXPORT: 'warning', IMPORT: 'processing', CONFIG: 'danger', LOGIN: 'default' }[action] || 'default'
    },
    switchTab(tab) {
      this.tab = tab
      this.filters = EMPTY_FILTERS()
      this.pagination.page = 1
      this.load()
    },
    onToolbar(key) {
      if (key === 'exportLogs') this.exportOpen = true
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
    openDetail(row) {
      this.detail = { open: true, row }
    },
    async load() {
      this.loading = true
      this.error = ''
      const params = { ...this.filters, page: this.pagination.page, pageSize: this.pagination.pageSize }
      const res = this.tab === 'operation' ? await systemApi.getOperationLogs(params) : await systemApi.getLoginLogs(params)
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
.lg-sec {
  margin: var(--space-4) 0 var(--space-2);
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
}
.lg-diff {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-2);
}
.lg-diff__col {
  border-radius: var(--radius-base);
  padding: var(--space-2) var(--space-3);
  font-size: var(--font-size-sm);
  line-height: 1.6;
}
.lg-diff__col b {
  display: block;
  font-size: var(--font-size-xs);
  margin-bottom: var(--space-1);
}
.lg-diff__col--before {
  background: var(--danger-50);
  border: 1px solid var(--danger-100);
  color: var(--danger-700);
}
.lg-diff__col--after {
  background: var(--success-50);
  border: 1px solid var(--success-100);
  color: var(--success-700);
}
</style>
