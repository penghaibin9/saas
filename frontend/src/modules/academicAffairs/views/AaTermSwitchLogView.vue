<template>
  <ModulePageShell
    class="aa-foundation-workspace"
    title="学期切换记录"
    subtitle="按时间查看教务操作与全校学期激活记录。"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="mp-stack">
      <AppSectionCard title="当前学期切换记录 · 可回查证据">
      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState
        v-else-if="!rows.length"
        title="还没有切换记录"
        description="在「学年学期」发布学期或在「当前学期设置」切换当前学期后，这里会自动生成记录"
      />
      <ol v-else class="aa-switch-timeline">
        <li v-for="row in rows" :key="row.id">
          <small>{{ formatTime(row.occurredAt) }} · 记录 {{ row.id }}</small>
          <h2>{{ actionLabel(row.action) }} <AppStatusTag :type="actionType(row.action)">{{ row.sourceLabel || '教务操作记录' }}</AppStatusTag></h2>
          <p>{{ row.fromTermLabel || '无前序记录' }} → <strong>{{ row.toTermLabel || '目标学期待核对' }}</strong></p>
          <p>操作人：{{ row.operator || '未记录' }}<span v-if="row.roleName"> · {{ roleLabel(row.roleName) }}</span></p>
          <button v-if="row.toTermId" class="mp-link" @click="openTerm(row)">查看目标学期与状态记录</button>
        </li>
      </ol>
      <AppPagination v-if="!loading && !error && pagination.total" :total="pagination.total" :page="pagination.page" :page-size="pagination.pageSize" :show-size-changer="false" @change="onPageChange($event.page)" />
      </AppSectionCard>
      <p class="mp-note">学期前后关系按已有记录顺序还原。历史发布记录未保存切换快照，可结合学校的学期启用记录核对。</p>
    </div>
  </ModulePageShell>
</template>

<script>
/** 学期切换记录（/admin/academic-affairs/terms/switch-log）：GET /academic-affairs/terms/switch-log。
 * 设计来源：existing_code——读取既有 t_affairs_audit_trail(biz_type=AA_TERM) 审计流水，
 * 覆盖 publish_term/set_current_term 两个写入口已落的 PUBLISH/SET_CURRENT 事件，
 * 按时间顺序推导每次「当前学期」切出/切入学期，不新建表、不新增写入口。 */
import { ModulePageShell, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppSectionCard, AppPagination, AppStatusTag } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { formatDateTime } from '@/utils/dateUtils'
import { presentAuditRecord } from '@/utils/presentationSafety'
import { academicRouteState } from '@/modules/academicAffairs/academicFlowContext'

const ACTION_LABEL = { PUBLISH: '发布记录', SET_CURRENT: '切换当前学期', ACTIVATE: '统一启用学期' }
const ACTION_TYPE = { PUBLISH: 'success', SET_CURRENT: 'processing', ACTIVATE: 'success' }

export default {
  name: 'AaTermSwitchLogView',
  components: { ModulePageShell, LoadingState, ErrorState, EmptyState, AppSectionCard, AppPagination, AppStatusTag },
  props: { ctx: { type: Object, required: true } },
  inject: { academicFlow: { default: null } },
  data() {
    return {
      loading: true, requestVersion: 0, disposed: false,
      error: '',
      rows: [],
      pagination: { page: 1, pageSize: 20, total: 0 }
    }
  },
  created() {
    this.pagination.page = academicRouteState(this.$route).page
    this.load()
  },
  watch: { '$route.query.page'() { const page = academicRouteState(this.$route).page; if (page !== this.pagination.page) { this.pagination.page = page; this.load() } } },
  beforeUnmount() { this.disposed = true; this.requestVersion++ },
  methods: {
    openTerm(row) { const returnToken = this.academicFlow?.captureReturn(); this.$router.push({ name: 'aa-term-detail', params: { termId: row.toTermId }, query: returnToken ? { returnToken } : {} }) },
    actionLabel(a) { return ACTION_LABEL[a] || '学期操作' },
    roleLabel(actorRole) { return presentAuditRecord({ actorRole }).displayRole },
    actionType(a) { return ACTION_TYPE[a] || 'default' },
    formatTime(t) {
      return formatDateTime(t, '—')
    },
    onPageChange(page) {
      this.pagination.page = page
      this.$router.replace({ query: { ...this.$route.query, page: String(page) } })
      this.load()
    },
    async load() {
      const version = ++this.requestVersion, scope = JSON.stringify(this.ctx)
      this.loading = true
      this.error = ''
      const res = await academicAffairsApi.getTermSwitchLog({
        page: this.pagination.page,
        pageSize: this.pagination.pageSize
      })
      if (version !== this.requestVersion || this.disposed || scope !== JSON.stringify(this.ctx)) return
      if (res.code === 0) {
        this.rows = res.data.list
        this.pagination.total = res.data.total
      } else {
        this.error = res.message
      }
      this.loading = false
      this.academicFlow?.restorePosition?.()
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
.aa-switch-timeline { list-style: none; margin: 0 0 16px; padding: 0 0 0 12px; }
.aa-switch-timeline li { position: relative; border-left: 1px solid var(--border-base); padding: 0 16px 28px; }
.aa-switch-timeline li::before { content: ''; position: absolute; top: 5px; left: -4px; width: 7px; height: 7px; border-radius: 50%; background: var(--pri); }
.aa-switch-timeline small { color: var(--text-secondary); font-size: 12px; }
.aa-switch-timeline h2 { display: flex; align-items: center; gap: 12px; margin: 10px 0; font-size: 14px; }
.aa-switch-timeline p { font-size: 13px; color: var(--text-secondary); }
.mp-link { border: 0; background: transparent; color: var(--pri); font: inherit; cursor: pointer; padding: 0; }
</style>
