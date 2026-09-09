<template>
  <ModulePageShell
    class="aa-foundation-workspace"
    title="学期切换记录"
    subtitle="按时间查看教务操作与全校学期激活记录。"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="mp-stack">
      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState
        v-else-if="!rows.length"
        title="还没有切换记录"
        description="在「学年学期」发布学期或在「当前学期设置」切换当前学期后，这里会自动生成记录"
      />
      <DataTable
        v-else
        :columns="columns"
        :rows="rows"
        row-key="id"
        :pagination="pagination"
        @page-change="onPageChange"
      >
        <template #cell-occurredAt="{ row }">{{ formatTime(row.occurredAt) }}</template>
        <template #cell-switch="{ row }">
          <div class="aa-switch-cell">
            <span v-if="row.fromTermLabel" class="aa-switch-from">{{ row.fromTermLabel }}</span>
            <span v-else class="aa-switch-from aa-switch-from--empty">无前序记录</span>
            <span class="aa-switch-arrow">→</span>
            <span class="aa-switch-to">{{ row.toTermLabel || '—' }}</span>
          </div>
        </template>
        <template #cell-action="{ row }">
          <AppStatusTag :type="actionType(row.action)" dot>{{ actionLabel(row.action) }}</AppStatusTag>
          <div class="mp-cell-sub">{{ row.sourceLabel || '教务操作记录' }}</div>
        </template>
        <template #cell-operator="{ row }">
          <div class="mp-cell-main">{{ row.operator || '—' }}</div>
          <div class="mp-cell-sub" v-if="row.roleName">{{ roleLabel(row.roleName) }}</div>
        </template>
      </DataTable>
      <p class="mp-note">学期前后关系按已有记录顺序还原。历史发布记录未保存切换快照，可结合学校的学期启用记录核对。</p>
    </div>
  </ModulePageShell>
</template>

<script>
/** 学期切换记录（/admin/academic-affairs/terms/switch-log）：GET /academic-affairs/terms/switch-log。
 * 设计来源：existing_code——读取既有 t_affairs_audit_trail(biz_type=AA_TERM) 审计流水，
 * 覆盖 publish_term/set_current_term 两个写入口已落的 PUBLISH/SET_CURRENT 事件，
 * 按时间顺序推导每次「当前学期」切出/切入学期，不新建表、不新增写入口。 */
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppStatusTag } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { formatDateTime } from '@/utils/dateUtils'
import { presentAuditRecord } from '@/utils/presentationSafety'

const ACTION_LABEL = { PUBLISH: '发布记录', SET_CURRENT: '切换当前学期', ACTIVATE: '统一启用学期' }
const ACTION_TYPE = { PUBLISH: 'success', SET_CURRENT: 'processing', ACTIVATE: 'success' }

export default {
  name: 'AaTermSwitchLogView',
  components: { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppStatusTag },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      rows: [],
      pagination: { page: 1, pageSize: 20, total: 0 },
      columns: [
        { key: 'occurredAt', title: '切换时间' },
        { key: 'switch', title: '切换详情' },
        { key: 'action', title: '触发动作' },
        { key: 'operator', title: '操作人' }
      ]
    }
  },
  created() {
    this.load()
  },
  methods: {
    actionLabel(a) { return ACTION_LABEL[a] || '学期操作' },
    roleLabel(actorRole) { return presentAuditRecord({ actorRole }).displayRole },
    actionType(a) { return ACTION_TYPE[a] || 'default' },
    formatTime(t) {
      return formatDateTime(t, '—')
    },
    onPageChange(page) {
      this.pagination.page = page
      this.load()
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await academicAffairsApi.getTermSwitchLog({
        page: this.pagination.page,
        pageSize: this.pagination.pageSize
      })
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
@import '../styles/foundation-workspace.css';
.aa-switch-cell {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}
.aa-switch-from {
  color: var(--text-700, #4e5969);
}
.aa-switch-from--empty {
  color: var(--text-400, #86909c);
  font-style: italic;
}
.aa-switch-arrow {
  color: var(--text-400, #86909c);
}
.aa-switch-to {
  color: var(--text-900, #1f2329);
  font-weight: 600;
}
</style>
