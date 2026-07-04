<template>
  <ModulePageShell
    title="数据驾驶舱"
    :subtitle="'全生命周期指标同源汇聚 · 数据更新于 ' + (overview ? overview.updatedAt : '—')"
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
    <EmptyState
      v-else-if="!overview"
      title="暂无概览数据"
      description="当前口径下暂未生成概览快照，可切换统计口径或稍后重试"
    />
    <div v-else class="mp-stack">
      <ModuleHero
        :title="ctx.tenantBrandConfig.schoolName + ' · 全景数据驾驶舱'"
        :subtitle="overview.caliberLabel + '快照 · 覆盖迎新报到至就业去向全流程'"
        :chips="heroChips"
        :stats="heroStats"
        :flow="overview.stageFlow"
      />

      <section class="mp-card">
        <div class="mp-card__body dcd-caliber">
          <span class="mp-note">统计口径：</span>
          <div class="dcd-caliber__seg">
            <button
              v-for="c in ctx.filterOptions.calibers"
              :key="c.value"
              type="button"
              class="dcd-caliber__btn"
              :class="{ 'is-active': caliber === c.value }"
              @click="setCaliber(c.value)"
            >
              {{ c.label }}
            </button>
          </div>
          <span class="mp-note dcd-caliber__note">{{ overview.caliberNote }}</span>
        </div>
      </section>

      <div class="mp-grid-cards">
        <button
          v-for="m in visibleMetrics"
          :key="m.key"
          type="button"
          class="dcd-metric"
          :title="'下钻查看：' + m.drillLabel"
          @click="drill(m)"
        >
          <div class="dcd-metric__head">
            <span class="dcd-metric__label">{{ m.label }}</span>
            <StatusTag type="info" :label="m.sourceModule" />
          </div>
          <div class="dcd-metric__value">
            {{ m.value }}<span class="dcd-metric__unit">{{ m.unit }}</span>
          </div>
          <div class="dcd-metric__trend" :class="'is-' + (m.trendQuality || 'neutral')">{{ m.trend }}</div>
          <div class="dcd-metric__desc">{{ m.description }}</div>
          <div class="dcd-metric__drill">下钻：{{ m.drillLabel }} →</div>
        </button>
      </div>

      <p class="mp-note">
        指标口径与各业务模块同源，页面不做二次计算；概览导出默认脱敏并附追踪水印，导出用途写入审计日志。
      </p>
    </div>

    <AppDrawer v-model:visible="guideVisible" title="指标口径说明">
      <div class="mp-stack">
        <p class="mp-note">
          以下为当前角色可见指标的统计口径，口径调整需经数据治理流程评审后统一发布。
        </p>
        <section v-for="m in visibleMetrics" :key="m.key" class="dcd-guide">
          <div class="dcd-guide__title">
            {{ m.label }}
            <StatusTag type="info" :label="'来源：' + m.sourceModule" />
          </div>
          <div class="dcd-guide__desc">{{ m.description }}</div>
        </section>
        <p v-if="overview" class="mp-note">{{ overview.caliberNote }}</p>
        <p class="mp-note">{{ ctx.exportOptions.policyNote }}</p>
      </div>
    </AppDrawer>

    <AppConfirmDialog
      v-model:visible="exportVisible"
      type="primary"
      title="导出全校概览数据"
      :message="ctx.exportOptions.policyNote"
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
 * 数据驾驶舱（/admin/data-center）。
 * 指标卡按角色 visibleMetricKeys 过滤；统计口径可切换；点击指标卡下钻到对应分析页；
 * 概览导出受 permissionActions.exportOverview 控制，导出前确认用途并留痕。
 */
import {
  ModulePageShell,
  ModuleHero,
  ModuleToolbar,
  StatusTag,
  LoadingState,
  ErrorState,
  EmptyState
} from '@/components/business'
import { AppGlobalState, AppConfirmDialog } from '@/components/common'
import { AppDrawer } from '@/components/ui'
import { dataCenterApi } from '@/modules/dataCenter/api/dataCenter.api'
import { toast } from '@/utils/toast'

export default {
  name: 'DataCenterDashboardView',
  components: {
    ModulePageShell,
    ModuleHero,
    ModuleToolbar,
    StatusTag,
    LoadingState,
    ErrorState,
    EmptyState,
    AppGlobalState,
    AppConfirmDialog,
    AppDrawer
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      overview: null,
      caliber: 'REGISTERED',
      guideVisible: false,
      exportVisible: false,
      exportPurpose: 'REPORT_TO_LEADER',
      exporting: false
    }
  },
  computed: {
    viewAllowed() {
      const pa = this.ctx.permissionActions.viewDashboard
      return !!(pa && pa.visible && pa.allowed)
    },
    viewReason() {
      const pa = this.ctx.permissionActions.viewDashboard
      return (pa && pa.reason) || '当前角色未开通数据驾驶舱查看权限'
    },
    visibleMetrics() {
      if (!this.overview) return []
      return this.overview.metrics.filter((m) => this.ctx.visibleMetricKeys.includes(m.key))
    },
    heroStats() {
      return this.visibleMetrics.slice(0, 5).map((m) => ({
        label: m.label,
        value: m.unit === '%' ? m.value + '%' : m.value + ' ' + m.unit,
        trend: m.trend,
        trendQuality: m.trendQuality
      }))
    },
    heroChips() {
      const chips = [
        '当前角色：' + this.ctx.currentRole.roleName,
        '数据范围：' + this.ctx.dataScope.scopeName
      ]
      if (this.overview) chips.push('统计口径：' + this.overview.caliberLabel)
      return chips
    },
    toolbarActions() {
      const pa = this.ctx.permissionActions
      const list = []
      if (pa.exportOverview && pa.exportOverview.visible) {
        list.push({
          key: 'exportOverview',
          label: '导出全校概览',
          variant: 'primary',
          disabled: !pa.exportOverview.allowed,
          disabledReason: pa.exportOverview.reason
        })
      }
      list.push({ key: 'metricGuide', label: '指标口径说明', variant: 'ghost' })
      return list
    }
  },
  created() {
    this.load()
  },
  methods: {
    async load() {
      this.loading = true
      this.error = ''
      const res = await dataCenterApi.getOverview({ caliber: this.caliber })
      if (res.code === 0) this.overview = res.data
      else this.error = res.message
      this.loading = false
    },
    setCaliber(value) {
      if (value === this.caliber) return
      this.caliber = value
      this.load()
    },
    drill(metric) {
      if (metric.drillRoute) this.$router.push(metric.drillRoute)
    },
    onToolbar(key) {
      if (key === 'metricGuide') this.guideVisible = true
      if (key === 'exportOverview') {
        this.exportPurpose = 'REPORT_TO_LEADER'
        this.exportVisible = true
      }
    },
    async onExportConfirm() {
      this.exporting = true
      const res = await dataCenterApi.exportData({ scope: 'OVERVIEW', purpose: this.exportPurpose })
      this.exporting = false
      if (res.code === 0) {
        this.exportVisible = false
        toast.success('导出任务 ' + res.data.taskId + ' 已创建：数据已脱敏、附追踪水印，并已写入审计日志')
      } else {
        toast.error(res.message)
      }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.dcd-caliber {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-wrap: wrap;
}
.dcd-caliber__seg {
  display: inline-flex;
  border: 1px solid var(--border-base);
  border-radius: var(--radius-full);
  overflow: hidden;
}
.dcd-caliber__btn {
  border: none;
  background: var(--bg-card);
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
  padding: var(--space-1) var(--space-4);
  cursor: pointer;
}
.dcd-caliber__btn.is-active {
  background: var(--primary-600);
  color: var(--text-inverse);
  font-weight: var(--font-weight-medium);
}
.dcd-caliber__note {
  flex: 1;
  min-width: 200px;
}
.dcd-metric {
  text-align: left;
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-card);
  padding: var(--space-4);
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  transition: box-shadow var(--motion-fast) var(--ease-standard), border-color var(--motion-fast) var(--ease-standard);
}
.dcd-metric:hover {
  border-color: var(--primary-500);
  box-shadow: var(--shadow-card-hover);
}
.dcd-metric__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
}
.dcd-metric__label {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  font-weight: var(--font-weight-medium);
}
.dcd-metric__value {
  font-size: var(--font-size-metric-sm);
  font-weight: var(--font-weight-bold);
  font-variant-numeric: var(--font-numeric);
  color: var(--text-primary);
  line-height: 1.2;
}
.dcd-metric__unit {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-normal);
  color: var(--text-tertiary);
  margin-left: var(--space-1);
}
.dcd-metric__trend {
  font-size: var(--font-size-xs);
}
.dcd-metric__trend.is-good { color: var(--trend-good); }
.dcd-metric__trend.is-bad { color: var(--trend-bad); }
.dcd-metric__trend.is-neutral { color: var(--trend-neutral); }
.dcd-metric__desc {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
  line-height: var(--line-height-base);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.dcd-metric__drill {
  margin-top: auto;
  padding-top: var(--space-2);
  font-size: var(--font-size-xs);
  color: var(--text-link);
  font-weight: var(--font-weight-medium);
}
.dcd-guide {
  border-bottom: 1px dashed var(--border-light);
  padding-bottom: var(--space-3);
}
.dcd-guide:last-of-type {
  border-bottom: none;
}
.dcd-guide__title {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
  flex-wrap: wrap;
}
.dcd-guide__desc {
  margin-top: var(--space-1);
  font-size: var(--font-size-xs);
  color: var(--text-secondary);
  line-height: var(--line-height-base);
}
</style>
