<template>
  <ModulePageShell
    title="数据同步任务 / 平台日志"
    subtitle="同步链路：外部系统 → 映射 → 暂存 → 校验 → 身份匹配 → 业务表 · 失败可重试（幂等）"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <ModuleToolbar :actions="toolbarActions" @action="onToolbar" />
    </template>

    <div class="mp-stack">
      <div class="mp-tabs">
        <button class="mp-tab" :class="{ 'is-active': tab === 'tasks' }" @click="switchTab('tasks')">同步任务</button>
        <button class="mp-tab" :class="{ 'is-active': tab === 'logs' }" @click="switchTab('logs')">平台操作日志</button>
      </div>

      <AdvancedFilter v-model="filters" :fields="filterFields" @search="search" @reset="reset" />

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" :title="tab === 'tasks' ? '没有符合条件的同步任务' : '没有符合条件的日志'" description="可调整筛选条件" />

      <!-- 同步任务 -->
      <DataTable v-else-if="tab === 'tasks'" :columns="taskColumns" :rows="rows" row-key="id" :pagination="pagination" @page-change="onPageChange">
        <template #cell-task="{ row }">
          <div class="mp-cell-main">{{ row.name }}</div>
          <div class="mp-cell-sub">{{ row.tenantName }} · {{ row.source }}</div>
        </template>
        <template #cell-objectLabel="{ row }">
          <StatusTag type="info" :label="row.objectLabel" />
        </template>
        <template #cell-lastResult="{ row }">
          <span :class="{ 'st-fail': row.failRows > 0 }">{{ row.lastResult }}</span>
        </template>
        <template #cell-status="{ row }">
          <StatusTag :type="row.status === 'ENABLED' ? 'success' : row.status === 'FAILED' ? 'danger' : 'default'" :label="row.statusLabel" dot />
        </template>
        <template #cell-actions="{ row }">
          <button class="mp-link" @click="openDetail(row)">详情</button>
          <button
            v-if="row.failRows > 0"
            class="mp-link"
            :class="{ 'is-disabled': !can('retrySyncTask') }"
            :title="reason('retrySyncTask')"
            @click="doRetry(row)"
          >重试失败行</button>
          <button
            v-if="row.status !== 'PAUSED'"
            class="mp-link st-danger"
            :class="{ 'is-disabled': !can('disableSyncTask') }"
            :title="reason('disableSyncTask')"
            @click="askPause(row)"
          >停用</button>
          <button v-else class="mp-link" :class="{ 'is-disabled': !can('disableSyncTask') }" @click="doResume(row)">恢复</button>
        </template>
      </DataTable>

      <!-- 平台日志 -->
      <DataTable v-else :columns="logColumns" :rows="rows" row-key="id" :pagination="pagination" @page-change="onPageChange">
        <template #cell-who="{ row }">
          <div class="mp-cell-main">{{ row.who }}</div>
          <div class="mp-cell-sub">{{ row.roleName }}</div>
        </template>
        <template #cell-action="{ row }">
          <StatusTag :type="row.action === 'DISABLE' ? 'warning' : row.action === 'GRANT' ? 'danger' : 'info'" :label="row.actionLabel" />
        </template>
        <template #cell-result="{ row }">
          <StatusTag :type="row.result === 'SUCCESS' ? 'success' : 'danger'" :label="row.resultLabel" dot />
        </template>
        <template #cell-actions="{ row }">
          <button class="mp-link" @click="logDetail = { open: true, row }">详情</button>
        </template>
      </DataTable>

      <p v-if="tab === 'logs'" class="mp-note">平台审计日志只增不删（含平台管理员）；IP 已固定脱敏，导出动作本身写入审计日志。</p>
    </div>

    <!-- 同步任务详情 -->
    <AppDrawer v-model:visible="detail.open" :title="'同步任务 · ' + (detail.data ? detail.data.name : '')" mode="modal" size="xlarge">
      <LoadingState v-if="detail.loading" />
      <template v-else-if="detail.data">
        <div class="mp-kv"><span class="mp-kv__k">租户 / 数据源</span><span class="mp-kv__v">{{ detail.data.tenantName }} · {{ detail.data.source }}</span></div>
        <div class="mp-kv"><span class="mp-kv__k">同步对象 / 调度</span><span class="mp-kv__v">{{ detail.data.objectLabel }} · {{ detail.data.schedule }}</span></div>
        <div class="mp-kv"><span class="mp-kv__k">最近批次</span><span class="mp-kv__v">{{ detail.data.batchNo }}</span></div>
        <div class="mp-kv"><span class="mp-kv__k">数据链路</span><span class="mp-kv__v">{{ detail.data.flow }}</span></div>

        <h4 class="st-sec">执行记录</h4>
        <ul class="mp-timeline">
          <li v-for="(r, i) in detail.data.runs" :key="i" class="mp-timeline__item" :class="'is-' + r.tone">
            <div class="mp-timeline__title">{{ r.resultLabel }}</div>
            <div class="mp-timeline__desc">{{ r.detail }}</div>
            <div class="mp-timeline__time">{{ r.time }}</div>
          </li>
        </ul>

        <template v-if="detail.data.failedRows.length">
          <h4 class="st-sec">失败明细（学号脱敏）</h4>
          <table class="mp-audit">
            <thead><tr><th>数据行</th><th>字段</th><th>错误原因</th></tr></thead>
            <tbody>
              <tr v-for="(f, i) in detail.data.failedRows" :key="i">
                <td class="is-who">{{ f.row }}</td><td>{{ f.field }}</td><td>{{ f.message }}</td>
              </tr>
            </tbody>
          </table>
          <p class="mp-note" style="margin-top: var(--space-2)">修复建议：{{ detail.data.suggestion }}</p>
        </template>

        <template v-if="detail.data.auditTrail.length">
          <h4 class="st-sec">处理留痕</h4>
          <table class="mp-audit">
            <thead><tr><th>操作人</th><th>动作</th><th>影响</th><th>时间</th></tr></thead>
            <tbody>
              <tr v-for="(a, i) in detail.data.auditTrail" :key="i">
                <td class="is-who">{{ a.who }}</td><td>{{ a.action }}</td><td>{{ a.affected }}</td><td>{{ a.time }}</td>
              </tr>
            </tbody>
          </table>
        </template>
      </template>
    </AppDrawer>

    <!-- 平台日志详情 -->
    <AppDrawer v-model:visible="logDetail.open" title="平台操作日志详情" mode="modal" size="large">
      <template v-if="logDetail.row">
        <div class="mp-kv"><span class="mp-kv__k">时间</span><span class="mp-kv__v">{{ logDetail.row.time }}</span></div>
        <div class="mp-kv"><span class="mp-kv__k">操作人</span><span class="mp-kv__v">{{ logDetail.row.who }} · {{ logDetail.row.roleName }}</span></div>
        <div class="mp-kv"><span class="mp-kv__k">模块 / 动作</span><span class="mp-kv__v">{{ logDetail.row.moduleLabel }} · {{ logDetail.row.actionLabel }}</span></div>
        <div class="mp-kv"><span class="mp-kv__k">对象</span><span class="mp-kv__v">{{ logDetail.row.target }}</span></div>
        <div class="mp-kv"><span class="mp-kv__k">IP（脱敏）</span><span class="mp-kv__v">{{ logDetail.row.ip }}</span></div>
        <div class="mp-kv"><span class="mp-kv__k">摘要</span><span class="mp-kv__v">{{ logDetail.row.detail.summary }}</span></div>
        <div v-if="logDetail.row.detail.before || logDetail.row.detail.after" class="st-diff">
          <div class="st-diff__col st-diff__col--before"><b>变更前</b>{{ logDetail.row.detail.before || '（空）' }}</div>
          <div class="st-diff__col st-diff__col--after"><b>变更后</b>{{ logDetail.row.detail.after || '（空）' }}</div>
        </div>
        <div v-if="logDetail.row.detail.reason" class="mp-kv"><span class="mp-kv__k">原因</span><span class="mp-kv__v">{{ logDetail.row.detail.reason }}</span></div>
      </template>
    </AppDrawer>

    <AppConfirmDialog
      v-model:visible="confirmPause"
      type="danger"
      :title="'停用同步任务「' + (actionRow ? actionRow.name : '') + '」？'"
      message="停用后调度暂停，不再拉取外部数据；历史执行记录与暂存数据保留。"
      confirm-text="确认停用并留痕"
      require-reason
      reason-label="停用原因"
      :submitting="confirmSubmitting"
      @confirm="doPause"
    />

    <ExportDialog
      v-model:visible="exportOpen"
      title="导出平台操作日志"
      :options="ctx.exportOptions.logs"
      :data-scope-name="ctx.dataScope.scopeName"
      :run-export="api.exportPlatformLogs"
    />
  </ModulePageShell>
</template>

<script>
/**
 * 数据同步任务 / 平台日志（/admin/platform/sync）：
 * 任务列表 / 详情（执行记录 + 失败明细 + 修复建议）/ 重试失败行（幂等）/ 停用恢复留痕 / 导出任务日志；
 * 平台操作日志（只读 + 前后值对照 + 受控导出，禁止删除）。
 */
import {
  ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable,
  StatusTag, LoadingState, ErrorState, EmptyState
} from '@/components/business'
import AppDrawer from '@/components/ui/AppDrawer.vue'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import ExportDialog from '@/modules/platform/components/ExportDialog.vue'
import { platformApi } from '@/modules/platform/api/platform.api'
import { toast } from '@/utils/toast'

const EMPTY_FILTERS = () => ({ keyword: '', object: '', status: '' })

export default {
  name: 'PlatformSyncTaskView',
  components: {
    ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag,
    LoadingState, ErrorState, EmptyState, AppDrawer, AppConfirmDialog, ExportDialog
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      api: platformApi,
      tab: 'tasks',
      loading: true,
      error: '',
      rows: [],
      filters: EMPTY_FILTERS(),
      pagination: { page: 1, pageSize: 10, total: 0 },
      taskColumns: [
        { key: 'task', title: '任务' },
        { key: 'objectLabel', title: '对象' },
        { key: 'schedule', title: '调度' },
        { key: 'lastRunAt', title: '最近执行' },
        { key: 'lastResult', title: '最近结果' },
        { key: 'status', title: '状态' },
        { key: 'actions', title: '操作', width: '190px' }
      ],
      logColumns: [
        { key: 'time', title: '时间', width: '150px' },
        { key: 'who', title: '操作人' },
        { key: 'moduleLabel', title: '模块' },
        { key: 'action', title: '动作' },
        { key: 'target', title: '对象' },
        { key: 'result', title: '结果' },
        { key: 'actions', title: '操作', width: '70px' }
      ],
      detail: { open: false, loading: false, data: null },
      logDetail: { open: false, row: null },
      confirmPause: false,
      actionRow: null,
      confirmSubmitting: false,
      exportOpen: false
    }
  },
  computed: {
    filterFields() {
      if (this.tab === 'tasks') {
        return [
          { key: 'keyword', label: '关键词', type: 'text', placeholder: '任务 / 租户' },
          { key: 'object', label: '同步对象', type: 'select', options: this.ctx.filterOptions.syncObjects },
          { key: 'status', label: '任务状态', type: 'select', options: this.ctx.statusOptions.syncStatus }
        ]
      }
      return [{ key: 'keyword', label: '关键词', type: 'text', placeholder: '操作人 / 对象' }]
    },
    toolbarActions() {
      const pa = this.ctx.permissionActions
      const list = this.tab === 'tasks'
        ? [{ key: 'exportSyncLogs', label: '⇩ 导出任务日志' }]
        : [{ key: 'exportPlatformLogs', label: '⇩ 导出平台日志' }]
      return list
        .filter((a) => pa[a.key] && pa[a.key].visible)
        .map((a) => ({ ...a, disabled: !pa[a.key].allowed, disabledReason: pa[a.key].reason }))
    }
  },
  created() {
    if (this.$route.query.tab === 'logs') this.tab = 'logs'
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
    switchTab(tab) {
      this.tab = tab
      this.filters = EMPTY_FILTERS()
      this.pagination.page = 1
      this.load()
    },
    async onToolbar(key) {
      if (key === 'exportSyncLogs') {
        const res = await platformApi.exportSyncLogs()
        if (res.code === 0) toast.success('导出任务已创建：' + res.data.fileName + '（学号脱敏 + 水印），已留痕')
      }
      if (key === 'exportPlatformLogs') this.exportOpen = true
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
    async openDetail(row) {
      this.detail = { open: true, loading: true, data: null }
      const res = await platformApi.getSyncTaskDetail(row.id)
      this.detail.loading = false
      if (res.code === 0) this.detail.data = res.data
    },
    async doRetry(row) {
      if (!this.can('retrySyncTask')) return
      const res = await platformApi.retrySyncTask(row.id)
      if (res.code === 0) {
        toast.success('已重试失败行 ' + res.data.retried + ' 行（幂等），全部成功并留痕')
        this.load()
      } else {
        toast.error(res.message)
      }
    },
    askPause(row) {
      if (!this.can('disableSyncTask')) return
      this.actionRow = row
      this.confirmPause = true
    },
    async doPause({ reason }) {
      this.confirmSubmitting = true
      const res = await platformApi.setSyncTaskStatus(this.actionRow.id, { action: 'DISABLE', reason })
      this.confirmSubmitting = false
      if (res.code === 0) {
        toast.success('任务已停用（记录保留），原因已留痕')
        this.confirmPause = false
        this.load()
      } else {
        toast.error(res.message)
      }
    },
    async doResume(row) {
      if (!this.can('disableSyncTask')) return
      const res = await platformApi.setSyncTaskStatus(row.id, { action: 'ENABLE' })
      if (res.code === 0) {
        toast.success('任务已恢复调度，已留痕')
        this.load()
      }
    },
    async load() {
      this.loading = true
      this.error = ''
      const params = { ...this.filters, page: this.pagination.page, pageSize: this.pagination.pageSize }
      const res = this.tab === 'tasks' ? await platformApi.getSyncTasks(params) : await platformApi.getPlatformLogs(params)
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
.st-fail {
  color: var(--danger-600);
}
.st-danger {
  color: var(--danger-600);
}
.st-sec {
  margin: var(--space-4) 0 var(--space-2);
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
}
.st-diff {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-2);
  margin: var(--space-2) 0;
}
.st-diff__col {
  border-radius: var(--radius-base);
  padding: var(--space-2) var(--space-3);
  font-size: var(--font-size-sm);
  line-height: 1.6;
}
.st-diff__col b {
  display: block;
  font-size: var(--font-size-xs);
  margin-bottom: var(--space-1);
}
.st-diff__col--before {
  background: var(--danger-50);
  border: 1px solid var(--danger-100);
  color: var(--danger-700);
}
.st-diff__col--after {
  background: var(--success-50);
  border: 1px solid var(--success-100);
  color: var(--success-700);
}
.mp-link + .mp-link {
  margin-left: var(--space-2);
}
</style>
