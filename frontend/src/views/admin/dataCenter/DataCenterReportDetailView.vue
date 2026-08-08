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
          <div class="mp-card__body">
            <div v-if="detail.meta" class="dcrd-meta">
              <div class="mp-kv"><span class="mp-kv__k">数据截至</span><span class="mp-kv__v">{{ detail.meta.asOf || '尚未发布' }}</span></div>
              <div class="mp-kv"><span class="mp-kv__k">统计口径</span><span class="mp-kv__v">{{ detail.meta.caliberLabel || detail.meta.caliber }}</span></div>
              <div class="mp-kv"><span class="mp-kv__k">数据范围</span><span class="mp-kv__v">{{ metaScopeName }}</span></div>
              <div class="mp-kv"><span class="mp-kv__k">数据来源</span><span class="mp-kv__v">{{ metaSources }}</span></div>
              <div v-if="detail.meta.qualityFlags && detail.meta.qualityFlags.length" class="dcrd-quality">
                <div v-for="flag in detail.meta.qualityFlags" :key="flag.code" class="dcrd-quality__item">
                  <strong>{{ flag.code }}</strong>：{{ flag.message }}
                </div>
              </div>
            </div>
            <EmptyState
              v-if="!detail.metrics.length"
              title="当前没有已发布指标快照"
              description="草稿或已撤回报表不会伪造指标；点击“发布报表”后由服务端读取真实统计并冻结一个可追溯版本。"
            />
            <DataTable v-else :columns="metricColumns" :rows="detail.metrics" row-key="id">
              <template #cell-metric="{ row }">
                <div class="mp-cell-main">{{ row.name }}</div>
                <div class="mp-cell-sub">{{ row.caliberLabel }} · {{ row.source }}</div>
              </template>
              <template #cell-value="{ row }">
                <span class="dcrd-value">{{ row.value }}</span>
                <span class="dcrd-unit">{{ row.unit }}</span>
              </template>
              <template #cell-mom="{ row }">
                <span class="dcrd-delta" :class="'is-' + (row.momQuality || 'neutral')">{{ row.mom }}</span>
              </template>
              <template #cell-yoy="{ row }">
                <span class="dcrd-delta" :class="'is-' + (row.yoyQuality || 'neutral')">{{ row.yoy }}</span>
              </template>
            </DataTable>
          </div>
        </section>

        <section class="mp-card">
          <div class="mp-card__head"><span class="mp-card__title">趋势曲线</span></div>
          <div class="mp-card__body">
            <template v-if="detail.trend">
              <p class="mp-note" style="margin: 0 0 var(--space-2)">
                {{ detail.trend.label }}（单位：{{ detail.trend.unit }}）
              </p>
              <svg :viewBox="'0 0 ' + chart.width + ' ' + chart.height" class="dcrd-chart" role="img" aria-label="报表指标趋势折线图">
                <line
                  v-for="t in yTicks"
                  :key="'grid-' + t.value"
                  class="dcrd-chart__grid"
                  :x1="chart.left"
                  :x2="chart.width - chart.right"
                  :y1="t.y"
                  :y2="t.y"
                />
                <text v-for="t in yTicks" :key="'ylab-' + t.value" class="dcrd-chart__label" :x="chart.left - 8" :y="t.y + 4" text-anchor="end">
                  {{ t.value }}
                </text>
                <polyline class="dcrd-chart__line" :points="linePoints(detail.trend.values)" />
                <circle
                  v-for="(v, i) in detail.trend.values"
                  :key="'pt-' + i"
                  class="dcrd-chart__dot"
                  :cx="pointX(i)"
                  :cy="pointY(v)"
                  r="3.5"
                />
                <text
                  v-for="(m, i) in detail.trend.months"
                  :key="'x-' + m"
                  class="dcrd-chart__label"
                  :x="pointX(i)"
                  :y="chart.height - 8"
                  text-anchor="middle"
                >
                  {{ axisLabel(m) }}
                </text>
              </svg>
            </template>
            <p v-else class="mp-note">当前没有权威历史趋势序列；系统不会用 0 或演示曲线补齐。</p>
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
            <div class="mp-kv"><span class="mp-kv__k">共享范围</span><span class="mp-kv__v">{{ detail.config.shareScope }}</span></div>
            <p class="mp-note" style="margin-top: var(--space-3)">{{ detail.description }}</p>
            <div v-if="detail.voidInfo" class="dcrd-void">
              <div class="dcrd-void__title">该报表已作废（逻辑作废，永久留痕）</div>
              <div class="dcrd-void__desc">作废原因：{{ detail.voidInfo.reason }}</div>
              <div class="dcrd-void__desc">操作：{{ detail.voidInfo.by }} · {{ detail.voidInfo.time }}</div>
            </div>
          </div>
        </section>

        <section class="mp-card">
          <div class="mp-card__head">
            <span class="mp-card__title">发布版本历史</span>
            <span class="mp-note">共 {{ versions.length }} 个冻结版本</span>
          </div>
          <div class="mp-card__body">
            <table class="mp-audit">
              <thead><tr><th>版本</th><th>发布时间</th><th>发布人</th><th>口径</th></tr></thead>
              <tbody>
                <tr v-for="v in versions" :key="v.id">
                  <td>v{{ v.versionNo }}</td>
                  <td>{{ v.publishedAt }}</td>
                  <td>{{ v.publishedBy }}</td>
                  <td>{{ v.caliberLabel }}</td>
                </tr>
                <tr v-if="!versions.length"><td colspan="4" class="mp-note">尚无发布版本</td></tr>
              </tbody>
            </table>
          </div>
        </section>

        <section class="mp-card">
          <div class="mp-card__head">
            <span class="mp-card__title">该报表的审计记录</span>
            <span class="mp-note">共 {{ audits.length }} 条</span>
          </div>
          <div class="mp-card__body">
            <table class="mp-audit">
              <thead>
                <tr><th>操作人</th><th>时间</th><th>动作</th><th>说明</th></tr>
              </thead>
              <tbody>
                <tr v-for="a in audits" :key="a.id">
                  <td class="is-who">{{ a.userName }} · {{ a.roleName }}</td>
                  <td>{{ a.time }}</td>
                  <td>{{ a.action }}</td>
                  <td>{{ a.detail }}</td>
                </tr>
                <tr v-if="!audits.length">
                  <td colspan="4" class="mp-note">暂无与该报表相关的审计记录</td>
                </tr>
              </tbody>
            </table>
            <p class="mp-note" style="margin-top: var(--space-3)">{{ ctx.exportOptions.policyNote }}</p>
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
    ModulePageShell,
    ModuleToolbar,
    DataTable,
    StatusTag,
    LoadingState,
    ErrorState,
    EmptyState,
    AppGlobalState,
    AppConfirmDialog
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      detail: null,
      audits: [],
      versions: [],
      chart: { width: 560, height: 220, left: 52, right: 20, top: 16, bottom: 30 },
      metricColumns: [
        { key: 'metric', title: '指标' },
        { key: 'value', title: '当前值', width: '110px' },
        { key: 'mom', title: '环比', width: '90px' },
        { key: 'yoy', title: '同比', width: '90px' }
      ],
      stateAction: { visible: false, key: '', submitting: false }
    }
  },
  computed: {
    reportId() {
      return this.$route.params.reportId
    },
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
      actions.push({ key: 'exportReport', label: '导出报表数据' })
      return actions
        .filter((a) => pa[a.key] && pa[a.key].visible)
        .map((a) => ({ ...a, disabled: !pa[a.key].allowed, disabledReason: pa[a.key].reason }))
    },
    stateActionMessage() {
      if (!this.detail) return ''
      return this.stateAction.key === 'withdrawReport'
        ? `撤回「${this.detail.name}」后，已发布版本仍永久保留，但当前领导入口不再展示该版本；撤回后可继续编辑工作副本。`
        : `发布「${this.detail.name}」将由服务端按当前统计口径读取真实数据并冻结一个新版本。发布失败时不会生成半真半假的版本。`
    },
    maxY() {
      if (!this.detail || !this.detail.trend) return 10
      const max = Math.max(...this.detail.trend.values)
      return Math.max(10, Math.ceil((max * 1.15) / 10) * 10)
    },
    yTicks() {
      const ticks = []
      const steps = 4
      for (let i = 0; i <= steps; i++) {
        const value = Math.round((this.maxY / steps) * i)
        ticks.push({ value, y: this.pointY(value) })
      }
      return ticks
    }
  },
  watch: {
    reportId() {
      this.load()
    }
  },
  created() {
    if (this.viewAllowed) this.load()
  },
  methods: {
    axisLabel(m) {
      return typeof m === 'string' && m.includes('-') ? Number(m.split('-')[1]) + '月' : m
    },
    pointX(i) {
      const n = this.detail && this.detail.trend ? this.detail.trend.months.length : 1
      const plotWidth = this.chart.width - this.chart.left - this.chart.right
      if (n <= 1) return this.chart.left
      return this.chart.left + (plotWidth / (n - 1)) * i
    },
    pointY(value) {
      const plotHeight = this.chart.height - this.chart.top - this.chart.bottom
      return this.chart.height - this.chart.bottom - (value / this.maxY) * plotHeight
    },
    linePoints(values) {
      return values.map((v, i) => this.pointX(i) + ',' + this.pointY(v)).join(' ')
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await dataCenterApi.getReportDetail(this.reportId)
      if (res.code === 0) {
        this.detail = res.data
        await Promise.all([this.loadAudits(), this.loadVersions()])
      } else {
        this.detail = null
        this.error = res.message
      }
      this.loading = false
    },
    async loadAudits() {
      const res = await dataCenterApi.getAuditLogs({ targetId: this.reportId })
      this.audits = res.code === 0 ? res.data : []
    },
    async loadVersions() {
      const res = await dataCenterApi.getReportVersions(this.reportId)
      this.versions = res.code === 0 ? (res.data.items || []) : []
    },
    onToolbar(key) {
      if (key === 'publishReport' || key === 'withdrawReport') {
        this.stateAction.key = key
        this.stateAction.visible = true
      }
    },
    async confirmStateAction() {
      if (!this.detail) return
      this.stateAction.submitting = true
      const res = this.stateAction.key === 'withdrawReport'
        ? await dataCenterApi.withdrawReport(this.detail.id, this.detail.version)
        : await dataCenterApi.publishReport(this.detail.id, this.detail.version)
      this.stateAction.submitting = false
      if (res.code === 0) {
        this.stateAction.visible = false
        toast.success(this.stateAction.key === 'withdrawReport' ? '报表已撤回，发布版本仍保留可追溯' : '报表已发布并冻结服务端指标版本')
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
.dcrd-value {
  font-weight: var(--font-weight-semibold);
  font-variant-numeric: var(--font-numeric);
}
.dcrd-unit {
  margin-left: 2px;
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}
.dcrd-delta {
  font-size: var(--font-size-xs);
  font-variant-numeric: var(--font-numeric);
}
.dcrd-delta.is-good { color: var(--trend-good); }
.dcrd-delta.is-bad { color: var(--trend-bad); }
.dcrd-delta.is-neutral { color: var(--trend-neutral); }
.dcrd-chart {
  width: 100%;
  height: auto;
  display: block;
}
.dcrd-chart__grid {
  stroke: var(--border-light);
  stroke-width: 1;
}
.dcrd-chart__label {
  fill: var(--text-tertiary);
  font-size: 11px;
}
.dcrd-chart__line {
  fill: none;
  stroke: var(--primary-500);
  stroke-width: 2.5;
  stroke-linecap: round;
  stroke-linejoin: round;
}
.dcrd-chart__dot { fill: var(--primary-500); }
.dcrd-meta {
  margin-bottom: var(--space-4);
  padding: var(--space-3);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  background: var(--bg-soft);
}
.dcrd-quality {
  margin-top: var(--space-2);
  display: grid;
  gap: var(--space-1);
}
.dcrd-quality__item {
  font-size: var(--font-size-xs);
  color: var(--text-secondary);
}
.dcrd-void {
  margin-top: var(--space-3);
  border: 1px solid var(--danger-100);
  background: var(--danger-50);
  border-radius: var(--radius-md);
  padding: var(--space-3);
}
.dcrd-void__title {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
  color: var(--danger-600);
}
.dcrd-void__desc {
  margin-top: var(--space-1);
  font-size: var(--font-size-xs);
  color: var(--text-secondary);
}
</style>
