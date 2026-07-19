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
            <EmptyState
              v-if="!detail.metrics.length"
              title="尚未生成指标数据"
              description="草稿报表在发布后按统计周期自动汇聚指标数据"
            />
            <DataTable v-else :columns="metricColumns" :rows="detail.metrics" row-key="id">
              <template #cell-metric="{ row }">
                <div class="mp-cell-main">{{ row.name }}</div>
                <div class="mp-cell-sub">{{ row.caliberLabel }}</div>
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
            <p v-else class="mp-note">该报表暂无趋势序列（草稿或一次性冻结数据）。</p>
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
            <div class="mp-kv"><span class="mp-kv__k">创建时间</span><span class="mp-kv__v">{{ detail.config.createdAt }}</span></div>
            <div class="mp-kv"><span class="mp-kv__k">最近更新</span><span class="mp-kv__v">{{ detail.config.updatedAt }}</span></div>
            <div class="mp-kv"><span class="mp-kv__k">共享范围</span><span class="mp-kv__v">{{ detail.config.shareScope }}</span></div>
            <p class="mp-note" style="margin-top: var(--space-3)">{{ detail.description }}</p>
            <div v-if="detail.voidInfo" class="dcrd-void">
              <div class="dcrd-void__title">该报表已作废（逻辑删除，永久留痕）</div>
              <div class="dcrd-void__desc">作废原因：{{ detail.voidInfo.reason }}</div>
              <div class="dcrd-void__desc">操作：{{ detail.voidInfo.by }} · {{ detail.voidInfo.time }}</div>
            </div>
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
            <p class="mp-note" style="margin-top: var(--space-3)">
              {{ ctx.exportOptions.policyNote }}
            </p>
          </div>
        </section>
      </div>
    </div>

    <AppConfirmDialog
      v-model:visible="exportVisible"
      type="primary"
      title="导出报表数据"
      :message="'导出内容为本报表指标数据与趋势序列。' + ctx.exportOptions.policyNote"
      confirm-text="确认导出"
      :submitting="exporting"
      @confirm="onExportConfirm"
    >
      <div class="mp-note" style="margin-bottom: var(--space-2)">导出用途（必选，写入审计日志）</div>
      <div
        v-for="p in ctx.exportOptions.purposes"
        :key="p.value"
        class="mp-radio"
        :class="{ 'is-active': exportPurpose === p.value }"
        @click="exportPurpose = p.value"
      >
        <input type="radio" :checked="exportPurpose === p.value" style="margin-top: 3px" />
        <div>
          <div class="mp-radio__title">{{ p.label }}</div>
          <div class="mp-radio__desc">{{ p.desc }}</div>
        </div>
      </div>
    </AppConfirmDialog>
  </ModulePageShell>
</template>

<script>
/**
 * 报表详情（/admin/data-center/reports/:reportId）。
 * 展示报表配置（mp-kv）、指标数据表、趋势 SVG 与该报表的审计记录；
 * reportId 不存在时渲染 ErrorState；导出强调脱敏 / 水印 / 审计并留痕到本报表。
 */
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
      chart: { width: 560, height: 220, left: 52, right: 20, top: 16, bottom: 30 },
      metricColumns: [
        { key: 'metric', title: '指标' },
        { key: 'value', title: '当前值', width: '110px' },
        { key: 'mom', title: '环比', width: '90px' },
        { key: 'yoy', title: '同比', width: '90px' }
      ],
      exportVisible: false,
      exportPurpose: 'REPORT_TO_LEADER',
      exporting: false
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
    toolbarActions() {
      const pa = this.ctx.permissionActions
      return [{ key: 'exportReport', label: '导出报表数据', variant: 'primary' }]
        .filter((a) => pa[a.key] && pa[a.key].visible && !!this.detail)
        .map((a) => ({ ...a, disabled: !pa[a.key].allowed, disabledReason: pa[a.key].reason }))
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
        this.loadAudits()
      } else {
        this.detail = null
        this.error = res.message
      }
      this.loading = false
    },
    async loadAudits() {
      const res = await dataCenterApi.getAuditLogs({ targetId: this.reportId })
      if (res.code === 0) this.audits = res.data
    },
    onToolbar(key) {
      if (key === 'exportReport') {
        this.exportPurpose = 'REPORT_TO_LEADER'
        this.exportVisible = true
      }
    },
    async onExportConfirm() {
      if (!this.detail) return
      this.exporting = true
      const res = await dataCenterApi.exportData({
        scope: 'REPORT',
        purpose: this.exportPurpose,
        targetId: this.detail.id,
        targetName: this.detail.name
      })
      this.exporting = false
      if (res.code === 0) {
        this.exportVisible = false
        toast.success('导出任务 ' + res.data.taskId + ' 已登记并写入本报表审计记录（演示态，暂未生成实际文件）')
        this.loadAudits()
      } else {
        toast.error(res.message)
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
.dcrd-chart__dot {
  fill: var(--primary-500);
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
