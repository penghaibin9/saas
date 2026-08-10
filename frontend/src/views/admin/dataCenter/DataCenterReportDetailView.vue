<template>
  <ModulePageShell
    :title="detail ? detail.name : '报表详情'"
    :subtitle="detail ? detail.config.reportNo + ' · ' + detail.config.cycleLabel : '专题报表配置与指标数据'"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <ModuleToolbar :actions="toolbarActions" @action="onToolbar" />
    </template>

    <AppGlobalState
      v-if="!viewAllowed"
      state="forbidden"
      :description="viewReason"
      @back="$router.push('/admin/data-center')"
    />
    <ErrorState
      v-else-if="error"
      :description="error"
      @retry="load"
      @back="$router.push('/admin/data-center/reports')"
    />
    <LoadingState v-else-if="loading" />

    <div v-else-if="detail" class="mp-grid-2">
      <div class="mp-stack">
        <section class="mp-card">
          <div class="mp-card__head">
            <span class="mp-card__title">指标数据（{{ detail.metrics.length }} 项）</span>
            <StatusTag :type="detail.statusTone" :label="detail.statusLabel" dot />
          </div>
          <div class="mp-card__body mp-stack">
            <div v-if="detail.meta" class="dcrd-meta">
              <div class="mp-kv"><span class="mp-kv__k">数据截至</span><span class="mp-kv__v">{{ detail.meta.asOf || '尚未发布' }}</span></div>
              <div class="mp-kv"><span class="mp-kv__k">统计口径</span><span class="mp-kv__v">{{ detail.meta.caliberLabel || detail.meta.caliber }}</span></div>
              <div class="mp-kv"><span class="mp-kv__k">数据范围</span><span class="mp-kv__v">{{ metaScopeName }}</span></div>
              <div class="mp-kv"><span class="mp-kv__k">数据来源</span><span class="mp-kv__v">{{ metaSources }}</span></div>
            </div>

            <div v-if="qualityFlags.length" class="mp-stack">
              <div v-for="flag in qualityFlags" :key="flag.code" class="dcrd-quality">
                <StatusTag :type="flag.severity === 'ERROR' ? 'danger' : 'info'" :label="flag.code" />
                <span>{{ flag.message }}</span>
              </div>
            </div>

            <EmptyState
              v-if="!detail.metrics.length"
              title="当前没有已发布指标快照"
              description="草稿或已撤回报表不会伪造指标；发布时才由服务端读取真实统计并冻结可追溯版本。"
            />
            <DataTable v-else :columns="metricColumns" :rows="detail.metrics" row-key="id">
              <template #cell-metric="{ row }">
                <div class="mp-cell-main">{{ row.name }}</div>
                <div class="mp-cell-sub">{{ row.caliberLabel }} · {{ row.source }}</div>
              </template>
              <template #cell-value="{ row }"><strong>{{ row.value }}</strong> {{ row.unit }}</template>
              <template #cell-mom="{ row }">{{ row.mom }}</template>
              <template #cell-yoy="{ row }">{{ row.yoy }}</template>
            </DataTable>
          </div>
        </section>

        <section class="mp-card">
          <div class="mp-card__head"><span class="mp-card__title">历史趋势</span></div>
          <div class="mp-card__body">
            <div v-if="hasTrend" class="mp-stack">
              <div v-for="(m, i) in detail.trend.months" :key="m" class="mp-kv">
                <span class="mp-kv__k">{{ m }}</span>
                <span class="mp-kv__v">{{ detail.trend.values[i] }} {{ detail.trend.unit || '' }}</span>
              </div>
            </div>
            <EmptyState
              v-else
              title="尚无权威历史趋势序列"
              description="统计快照序列尚未配置；系统不会用 0 或演示曲线补齐。"
            />
          </div>
        </section>
      </div>

      <div class="mp-stack">
        <section class="mp-card">
          <div class="mp-card__head"><span class="mp-card__title">报表配置</span></div>
          <div class="mp-card__body">
            <div class="mp-kv"><span class="mp-kv__k">报表编号</span><span class="mp-kv__v">{{ detail.config.reportNo }}</span></div>
            <div class="mp-kv"><span class="mp-kv__k">统计周期</span><span class="mp-kv__v">{{ detail.config.cycleLabel }}</span></div>
            <div class="mp-kv"><span class="mp-kv__k">统计口径</span><span class="mp-kv__v">{{ detail.config.caliberLabel }}</span></div>
            <div class="mp-kv"><span class="mp-kv__k">数据范围</span><span class="mp-kv__v">{{ detail.config.scopeName }}</span></div>
            <div class="mp-kv"><span class="mp-kv__k">负责人</span><span class="mp-kv__v">{{ detail.config.ownerName }}</span></div>
            <div class="mp-kv"><span class="mp-kv__k">当前配置版本</span><span class="mp-kv__v">v{{ detail.version }}</span></div>
            <div class="mp-kv"><span class="mp-kv__k">已发布版本</span><span class="mp-kv__v">{{ detail.publishedVersion ? 'v' + detail.publishedVersion : '未发布' }}</span></div>
            <div class="mp-kv"><span class="mp-kv__k">创建时间</span><span class="mp-kv__v">{{ detail.config.createdAt }}</span></div>
            <div class="mp-kv"><span class="mp-kv__k">最近更新</span><span class="mp-kv__v">{{ detail.config.updatedAt }}</span></div>
            <p class="mp-note" style="margin-top: var(--space-3)">{{ detail.description }}</p>
            <div v-if="detail.voidInfo" class="dcrd-void">
              <strong>该报表已作废</strong>
              <div>原因：{{ detail.voidInfo.reason }}</div>
              <div>{{ detail.voidInfo.by }} · {{ detail.voidInfo.time }}</div>
            </div>
          </div>
        </section>

        <section class="mp-card">
          <div class="mp-card__head">
            <span class="mp-card__title">发布版本历史</span>
            <span class="mp-note">append-only 冻结版本</span>
          </div>
          <div class="mp-card__body">
            <ErrorState v-if="versionsError" :description="versionsError" @retry="loadVersions" />
            <LoadingState v-else-if="versionsLoading" text="正在读取发布版本…" />
            <EmptyState
              v-else-if="!versions.length"
              title="尚无发布版本"
              description="服务端查询成功，当前报表还没有冻结发布版本。"
            />
            <table v-else class="mp-audit">
              <thead><tr><th>版本</th><th>发布时间</th><th>发布人</th><th>口径</th></tr></thead>
              <tbody>
                <tr v-for="v in versions" :key="v.id">
                  <td>v{{ v.versionNo }}</td>
                  <td>{{ v.publishedAt }}</td>
                  <td>{{ v.publishedBy }}</td>
                  <td>{{ v.caliberLabel }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <section class="mp-card">
          <div class="mp-card__head">
            <span class="mp-card__title">该报表的审计记录</span>
            <span class="mp-note">真实 SecurityAuditLog</span>
          </div>
          <div class="mp-card__body">
            <ErrorState v-if="auditError" :description="auditError" @retry="loadAudits" />
            <LoadingState v-else-if="auditLoading" text="正在读取报表审计…" />
            <EmptyState
              v-else-if="!audits.length"
              title="暂无审计记录"
              description="服务端查询成功，但当前报表尚无审计事件。"
            />
            <table v-else class="mp-audit">
              <thead><tr><th>操作人</th><th>时间</th><th>动作</th><th>说明</th></tr></thead>
              <tbody>
                <tr v-for="a in audits" :key="a.id">
                  <td class="is-who">{{ a.userName }} · {{ a.roleName }}</td>
                  <td>{{ a.time }}</td>
                  <td>{{ a.action }}</td>
                  <td>{{ a.detail }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </div>

    <AppConfirmDialog
      v-model:visible="stateAction.visible"
      :type="stateAction.key === 'withdrawReport' ? 'warning' : 'primary'"
      :title="stateAction.key === 'withdrawReport' ? '撤回已发布报表' : '发布报表'"
      :message="stateActionMessage"
      :confirm-text="stateAction.key === 'withdrawReport' ? '确认撤回' : '确认发布'"
      :submitting="stateAction.submitting"
      @confirm="confirmStateAction"
    />
  </ModulePageShell>
</template>

<script>
import {
  ModulePageShell,
  ModuleToolbar,
  DataTable,
  StatusTag,
  LoadingState,
  ErrorState,
  EmptyState
} from '@/components/business'
import { AppGlobalState, AppConfirmDialog } from '@/components/common'
import { dataCenterApi } from '@/modules/dataCenter/api/dataCenter.api'
import { toast } from '@/utils/toast'

export default {
  name: 'DataCenterReportDetailView',
  components: {
    ModulePageShell, ModuleToolbar, DataTable, StatusTag,
    LoadingState, ErrorState, EmptyState, AppGlobalState, AppConfirmDialog
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      detail: null,
      audits: [],
      auditLoading: false,
      auditError: '',
      versions: [],
      versionsLoading: false,
      versionsError: '',
      metricColumns: [
        { key: 'metric', title: '指标' },
        { key: 'value', title: '冻结值', width: '120px' },
        { key: 'mom', title: '环比', width: '90px' },
        { key: 'yoy', title: '同比', width: '90px' }
      ],
      stateAction: { visible: false, key: '', submitting: false }
    }
  },
  computed: {
    reportId() { return this.$route.params.reportId },
    viewAllowed() {
      const pa = this.ctx.permissionActions.viewReports
      return !!(pa && pa.visible && pa.allowed)
    },
    viewReason() {
      const pa = this.ctx.permissionActions.viewReports
      return (pa && pa.reason) || '当前角色未开通专题报表模块权限'
    },
    metaScopeName() {
      return (this.detail && this.detail.meta && this.detail.meta.scope && this.detail.meta.scope.scopeName) || '—'
    },
    metaSources() {
      const rows = (this.detail && this.detail.meta && this.detail.meta.source) || []
      return rows.length ? rows.map((x) => x.module || x).join('、') : '尚未形成已发布来源快照'
    },
    qualityFlags() {
      const flags = this.detail && this.detail.meta && this.detail.meta.qualityFlags
      return Array.isArray(flags) ? flags : []
    },
    hasTrend() {
      return !!(
        this.detail && this.detail.trend &&
        Array.isArray(this.detail.trend.months) && this.detail.trend.months.length &&
        Array.isArray(this.detail.trend.values)
      )
    },
    toolbarActions() {
      if (!this.detail) return []
      const pa = this.ctx.permissionActions
      const actions = []
      if (['DRAFT', 'WITHDRAWN'].includes(this.detail.status)) {
        actions.push({ key: 'publishReport', label: '发布报表', variant: 'primary' })
      }
      if (this.detail.status === 'PUBLISHED') {
        actions.push({ key: 'withdrawReport', label: '撤回发布', variant: 'warning' })
      }
      return actions
        .filter((a) => pa[a.key] && pa[a.key].visible)
        .map((a) => ({ ...a, disabled: !pa[a.key].allowed, disabledReason: pa[a.key].reason }))
    },
    stateActionMessage() {
      if (!this.detail) return ''
      return this.stateAction.key === 'withdrawReport'
        ? `撤回「${this.detail.name}」后，已发布版本仍永久保留；当前入口不再展示冻结指标，撤回后可继续编辑工作副本。`
        : `发布「${this.detail.name}」将由服务端读取当前真实统计并冻结一个 append-only 版本。任一上游失败则整次发布失败。`
    }
  },
  watch: {
    reportId() { this.load() }
  },
  created() {
    if (this.viewAllowed) this.load()
  },
  methods: {
    async load() {
      this.loading = true
      this.error = ''
      const res = await dataCenterApi.getReportDetail(this.reportId)
      if (res.code === 0) {
        this.detail = res.data
        this.loading = false
        await Promise.all([this.loadVersions(), this.loadAudits()])
      } else {
        this.detail = null
        this.loading = false
        this.error = res.message
      }
    },
    async loadVersions() {
      this.versionsLoading = true
      this.versionsError = ''
      const res = await dataCenterApi.getReportVersions(this.reportId)
      if (res.code === 0) {
        this.versions = (res.data && res.data.items) || []
      } else {
        this.versions = []
        this.versionsError = res.message || '发布版本历史加载失败'
      }
      this.versionsLoading = false
    },
    async loadAudits() {
      this.auditLoading = true
      this.auditError = ''
      const res = await dataCenterApi.getAuditLogs({ targetId: this.reportId, limit: 50 })
      if (res.code === 0) {
        this.audits = res.data || []
      } else {
        this.audits = []
        this.auditError = res.message || '报表审计记录加载失败'
      }
      this.auditLoading = false
    },
    onToolbar(key) {
      if (!['publishReport', 'withdrawReport'].includes(key)) return
      this.stateAction.key = key
      this.stateAction.visible = true
    },
    async confirmStateAction() {
      if (!this.detail || !this.stateAction.key) return
      this.stateAction.submitting = true
      const res = this.stateAction.key === 'withdrawReport'
        ? await dataCenterApi.withdrawReport(this.detail.id, this.detail.version)
        : await dataCenterApi.publishReport(this.detail.id, this.detail.version)
      this.stateAction.submitting = false
      if (res.code === 0) {
        this.stateAction.visible = false
        toast.success(this.stateAction.key === 'withdrawReport' ? '报表已撤回，冻结历史版本继续保留' : '报表已发布并冻结服务端指标版本')
        await this.load()
      } else {
        toast.error(res.message)
        if (res.bizCode === 'DATA_VERSION_CONFLICT') await this.load()
      }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.dcrd-meta {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-2) var(--space-4);
  padding: var(--space-3);
  background: var(--bg-subtle);
  border-radius: var(--radius-md);
}
.dcrd-quality {
  display: flex;
  align-items: flex-start;
  gap: var(--space-2);
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
}
.dcrd-void {
  margin-top: var(--space-3);
  padding: var(--space-3);
  border: 1px solid var(--danger-100);
  border-radius: var(--radius-md);
  background: var(--danger-50);
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
  line-height: var(--line-height-base);
}
</style>
