<template>
  <ModulePageShell
    title="风险预警数据"
    :subtitle="risk ? '预警总量 ' + risk.total + ' 条 · ' + risk.timeRangeLabel + ' · 更新于 ' + risk.updatedAt : '来源分布 · 等级分布 · 趋势与下钻'"
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
    <ErrorState v-else-if="error" :description="error" @retry="load" />
    <LoadingState v-else-if="loading" />
    <EmptyState v-else-if="!risk" title="暂无风险统计数据" description="预警规则命中后将自动生成统计" />
    <div v-else class="mp-stack">
      <div class="mp-grid-2">
        <section class="mp-card">
          <div class="mp-card__head">
            <span class="mp-card__title">风险来源分布（按业务模块）</span>
            <span class="mp-note">合计 {{ risk.total }} 条</span>
          </div>
          <div class="mp-card__body mp-stack">
            <div v-for="s in risk.bySource" :key="s.moduleCode" class="dcrk-bar">
              <span class="dcrk-bar__label">{{ s.moduleName }}</span>
              <div class="dcrk-bar__track">
                <div class="dcrk-bar__fill" :style="{ width: sourceWidth(s) }" />
              </div>
              <span class="dcrk-bar__value">{{ s.count }} 条</span>
            </div>
            <p class="mp-note">{{ risk.suggestion }}</p>
          </div>
        </section>

        <section class="mp-card">
          <div class="mp-card__head"><span class="mp-card__title">等级分布与处理进度</span></div>
          <div class="mp-card__body mp-stack">
            <div v-for="l in risk.byLevel" :key="l.level" class="dcrk-bar">
              <span class="dcrk-bar__label"><RiskTag :level="l.level" /></span>
              <div class="dcrk-bar__track">
                <div class="dcrk-bar__fill" :class="'is-' + l.level" :style="{ width: levelWidth(l) }" />
              </div>
              <span class="dcrk-bar__value">{{ l.count }} 条</span>
            </div>
            <div class="dcrk-status">
              <div v-for="st in risk.byStatus" :key="st.key" class="mp-kv">
                <span class="mp-kv__k">
                  <StatusTag :type="st.key === 'PENDING' ? 'warning' : st.key === 'PROCESSING' ? 'processing' : 'success'" :label="st.label" dot />
                </span>
                <span class="mp-kv__v">{{ st.count }} 条</span>
              </div>
            </div>
          </div>
        </section>
      </div>

      <section class="mp-card">
        <div class="mp-card__head">
          <span class="mp-card__title">近 6 个月风险趋势</span>
          <span class="dcrk-legend">
            <span class="dcrk-legend__item"><span class="dcrk-legend__dot is-total" />预警总量</span>
            <span class="dcrk-legend__item"><span class="dcrk-legend__dot is-high" />高风险</span>
          </span>
        </div>
        <div class="mp-card__body">
          <svg :viewBox="'0 0 ' + chart.width + ' ' + chart.height" class="dcrk-chart" role="img" aria-label="近六个月风险趋势折线图">
            <line
              v-for="t in yTicks"
              :key="'grid-' + t.value"
              class="dcrk-chart__grid"
              :x1="chart.left"
              :x2="chart.width - chart.right"
              :y1="t.y"
              :y2="t.y"
            />
            <text v-for="t in yTicks" :key="'ylab-' + t.value" class="dcrk-chart__label" :x="chart.left - 8" :y="t.y + 4" text-anchor="end">
              {{ t.value }}
            </text>
            <polyline class="dcrk-chart__line is-total" :points="linePoints(risk.trend.total)" />
            <polyline class="dcrk-chart__line is-high" :points="linePoints(risk.trend.high)" />
            <circle
              v-for="(v, i) in risk.trend.total"
              :key="'pt-' + i"
              class="dcrk-chart__dot is-total"
              :cx="pointX(i)"
              :cy="pointY(v)"
              r="3.5"
            />
            <circle
              v-for="(v, i) in risk.trend.high"
              :key="'ph-' + i"
              class="dcrk-chart__dot is-high"
              :cx="pointX(i)"
              :cy="pointY(v)"
              r="3"
            />
            <text
              v-for="(m, i) in risk.trend.months"
              :key="'x-' + m"
              class="dcrk-chart__label"
              :x="pointX(i)"
              :y="chart.height - 8"
              text-anchor="middle"
            >
              {{ monthLabel(m) }}
            </text>
          </svg>
        </div>
      </section>

      <p class="mp-note">
        风险数据由各业务模块预警规则实时汇入，本页仅作统计分析；处置动作请在对应业务模块完成，全程留痕。
      </p>
    </div>

    <AppDrawer v-model:visible="drill.visible" title="风险学生名单">
      <div class="mp-stack">
        <p class="mp-note">名单来自各模块风险记录（脱敏展示）；勾选学生后可生成提醒建议，操作将写入审计日志。</p>
        <ErrorState v-if="drill.error" :description="drill.error" @retry="loadDrill" />
        <LoadingState v-else-if="drill.loading" text="正在加载风险学生名单…" />
        <EmptyState v-else-if="!drill.rows.length" title="暂无风险学生" description="当前范围内没有未闭环的风险记录" />
        <DataTable
          v-else
          :columns="drillColumns"
          :rows="drill.rows"
          row-key="id"
          selectable
          v-model:selected="drill.selected"
          :pagination="drill.pagination"
          @page-change="onDrillPage"
        >
          <template #cell-student="{ row }">
            <div class="mp-cell-main">{{ row.name }}</div>
            <div class="mp-cell-sub">{{ maskNo(row.studentNo) }} · {{ maskPhone(row.phone) }} · {{ row.className }}</div>
          </template>
          <template #cell-risk="{ row }">
            <RiskTag :level="row.riskLevel" />
          </template>
          <template #cell-status="{ row }">
            <StatusTag :type="row.tone" :label="row.statusLabel" />
          </template>
        </DataTable>
      </div>
      <template #footer>
        <AppButton
          variant="primary"
          :disabled="!canRemind || !drill.selected.length"
          :loading="reminding"
          :title="!canRemind ? remindReason : !drill.selected.length ? '请先勾选学生' : ''"
          @click="sendReminder"
        >
          生成提醒建议（{{ drill.selected.length }}）
        </AppButton>
        <span class="mp-note">建议将下发至责任教师工作台，并写入审计日志</span>
      </template>
    </AppDrawer>

    <AppConfirmDialog
      v-model:visible="exportVisible"
      type="warning"
      title="导出风险预警报表"
      :message="'风险报表含学生敏感信息摘要。' + ctx.exportOptions.policyNote"
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
 * 风险预警数据（/admin/data-center/risk）。
 * 来源 / 等级 / 处理进度三视角统计（合计一致），近 6 月趋势为内联 SVG polyline（禁图表库）；
 * 风险学生名单下钻（drawer + 脱敏），批量提醒建议与导出均留痕。
 */
import {
  ModulePageShell,
  ModuleToolbar,
  DataTable,
  StatusTag,
  RiskTag,
  LoadingState,
  ErrorState,
  EmptyState
} from '@/components/business'
import { AppGlobalState, AppConfirmDialog } from '@/components/common'
import { AppDrawer, AppButton } from '@/components/ui'
import { dataCenterApi } from '@/modules/dataCenter/api/dataCenter.api'
import { toast } from '@/utils/toast'

export default {
  name: 'DataCenterRiskView',
  components: {
    ModulePageShell,
    ModuleToolbar,
    DataTable,
    StatusTag,
    RiskTag,
    LoadingState,
    ErrorState,
    EmptyState,
    AppGlobalState,
    AppConfirmDialog,
    AppDrawer,
    AppButton
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      risk: null,
      chart: { width: 640, height: 240, left: 48, right: 24, top: 20, bottom: 32 },
      drill: {
        visible: false,
        loading: false,
        error: '',
        rows: [],
        selected: [],
        pagination: { page: 1, pageSize: 5, total: 0 }
      },
      drillColumns: [
        { key: 'student', title: '学生' },
        { key: 'risk', title: '等级', width: '86px' },
        { key: 'status', title: '状态' },
        { key: 'lastEvent', title: '最近动态' }
      ],
      reminding: false,
      exportVisible: false,
      exportPurpose: 'INTERNAL_ANALYSIS',
      exporting: false
    }
  },
  computed: {
    viewAllowed() {
      const pa = this.ctx.permissionActions.viewRisk
      return !!(pa && pa.visible && pa.allowed)
    },
    viewReason() {
      const pa = this.ctx.permissionActions.viewRisk
      return (pa && pa.reason) || '当前角色未开通风险预警数据查看权限'
    },
    canDrill() {
      const pa = this.ctx.permissionActions.drilldownStudents
      return !!(pa && pa.visible && pa.allowed)
    },
    drillReason() {
      const pa = this.ctx.permissionActions.drilldownStudents
      return pa && !pa.allowed ? pa.reason : ''
    },
    canRemind() {
      const pa = this.ctx.permissionActions.batchRemind
      return !!(pa && pa.visible && pa.allowed)
    },
    remindReason() {
      const pa = this.ctx.permissionActions.batchRemind
      return pa && !pa.allowed ? pa.reason : ''
    },
    toolbarActions() {
      const pa = this.ctx.permissionActions
      const list = []
      if (pa.exportRisk && pa.exportRisk.visible) {
        list.push({
          key: 'exportRisk',
          label: '导出风险报表',
          variant: 'primary',
          disabled: !pa.exportRisk.allowed,
          disabledReason: pa.exportRisk.reason
        })
      }
      if (pa.drilldownStudents && pa.drilldownStudents.visible) {
        list.push({
          key: 'openStudents',
          label: '风险学生名单',
          disabled: !pa.drilldownStudents.allowed,
          disabledReason: pa.drilldownStudents.reason
        })
      }
      return list
    },
    maxY() {
      if (!this.risk) return 10
      const max = Math.max(...this.risk.trend.total, ...this.risk.trend.high)
      return Math.max(10, Math.ceil((max * 1.15) / 20) * 20)
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
  created() {
    this.load()
  },
  methods: {
    maskPhone(v) {
      return v ? v.slice(0, 3) + '****' + v.slice(-4) : '未登记'
    },
    maskNo(v) {
      return v ? v.slice(0, -4) + '**' + v.slice(-2) : ''
    },
    sourceWidth(s) {
      if (!this.risk) return '0%'
      const max = Math.max(...this.risk.bySource.map((x) => x.count))
      return Math.round((s.count / max) * 100) + '%'
    },
    levelWidth(l) {
      if (!this.risk || !this.risk.total) return '0%'
      return Math.round((l.count / this.risk.total) * 100) + '%'
    },
    monthLabel(m) {
      return m.includes('-') ? Number(m.split('-')[1]) + '月' : m
    },
    pointX(i) {
      const n = this.risk ? this.risk.trend.months.length : 1
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
      const res = await dataCenterApi.getRiskStats({ timeRange: 'LAST_6M' })
      if (res.code === 0) this.risk = res.data
      else this.error = res.message
      this.loading = false
    },
    onToolbar(key) {
      if (key === 'exportRisk') {
        this.exportPurpose = 'INTERNAL_ANALYSIS'
        this.exportVisible = true
      }
      if (key === 'openStudents') this.openDrill()
    },
    openDrill() {
      if (!this.canDrill) {
        toast.info(this.drillReason || '当前角色不可查看学生明细')
        return
      }
      this.drill.visible = true
      this.drill.selected = []
      this.drill.pagination.page = 1
      this.loadDrill()
    },
    onDrillPage(page) {
      this.drill.pagination.page = page
      this.loadDrill()
    },
    async loadDrill() {
      this.drill.loading = true
      this.drill.error = ''
      const res = await dataCenterApi.getDrilldownStudents({
        metricKey: 'RISK',
        page: this.drill.pagination.page,
        pageSize: this.drill.pagination.pageSize
      })
      if (res.code === 0) {
        this.drill.rows = res.data.list
        this.drill.pagination.total = res.data.total
      } else {
        this.drill.error = res.message
      }
      this.drill.loading = false
    },
    async sendReminder() {
      if (!this.canRemind || !this.drill.selected.length) return
      this.reminding = true
      const res = await dataCenterApi.sendRiskReminder({ studentIds: [...this.drill.selected] })
      this.reminding = false
      if (res.code === 0) {
        toast.success('已为 ' + res.data.count + ' 名学生生成提醒建议并下发责任教师工作台，操作已留痕')
        this.drill.selected = []
      } else {
        toast.error(res.message)
      }
    },
    async onExportConfirm() {
      this.exporting = true
      const res = await dataCenterApi.exportData({ scope: 'RISK', purpose: this.exportPurpose })
      this.exporting = false
      if (res.code === 0) {
        this.exportVisible = false
        toast.success('导出任务 ' + res.data.taskId + ' 已登记并写入审计日志（演示态，暂未生成实际文件）')
      } else {
        toast.error(res.message)
      }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.dcrk-bar {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}
.dcrk-bar__label {
  width: 84px;
  flex-shrink: 0;
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}
.dcrk-bar__track {
  flex: 1;
  height: 12px;
  background: var(--gray-100);
  border-radius: var(--radius-full);
  overflow: hidden;
}
.dcrk-bar__fill {
  height: 100%;
  border-radius: var(--radius-full);
  background: linear-gradient(90deg, var(--primary-500), var(--primary-600));
  transition: width var(--motion-normal) var(--ease-standard);
}
.dcrk-bar__fill.is-HIGH { background: var(--danger-500); }
.dcrk-bar__fill.is-MEDIUM { background: var(--warning-500); }
.dcrk-bar__fill.is-LOW { background: var(--info-500); }
.dcrk-bar__value {
  width: 56px;
  flex-shrink: 0;
  text-align: right;
  font-size: var(--font-size-xs);
  color: var(--text-secondary);
  font-variant-numeric: var(--font-numeric);
}
.dcrk-status {
  border-top: 1px dashed var(--border-light);
  padding-top: var(--space-2);
}
.dcrk-legend {
  display: inline-flex;
  gap: var(--space-4);
  font-size: var(--font-size-xs);
  color: var(--text-secondary);
}
.dcrk-legend__item {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
}
.dcrk-legend__dot {
  width: 8px;
  height: 8px;
  border-radius: var(--radius-full);
}
.dcrk-legend__dot.is-total { background: var(--primary-500); }
.dcrk-legend__dot.is-high { background: var(--danger-500); }
.dcrk-chart {
  width: 100%;
  height: auto;
  display: block;
}
.dcrk-chart__grid {
  stroke: var(--border-light);
  stroke-width: 1;
}
.dcrk-chart__label {
  fill: var(--text-tertiary);
  font-size: 11px;
}
.dcrk-chart__line {
  fill: none;
  stroke-width: 2.5;
  stroke-linecap: round;
  stroke-linejoin: round;
}
.dcrk-chart__line.is-total { stroke: var(--primary-500); }
.dcrk-chart__line.is-high { stroke: var(--danger-500); }
.dcrk-chart__dot.is-total { fill: var(--primary-500); }
.dcrk-chart__dot.is-high { fill: var(--danger-500); }
</style>
