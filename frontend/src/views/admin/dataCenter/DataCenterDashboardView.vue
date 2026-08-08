<template>
  <ModulePageShell
    title="数据驾驶舱"
    :subtitle="'全生命周期指标同源汇聚 · 数据截至 ' + asOfLabel"
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
      @back="$router.push('/admin')"
    />
    <ErrorState v-else-if="error" :description="error" @retry="load" />
    <LoadingState v-else-if="loading" />
    <EmptyState
      v-else-if="!overview"
      title="暂无可证明的概览数据"
      description="当前服务端没有返回正式概览；页面不会用浏览器演示数据补齐。"
    />

    <div v-else class="mp-stack">
      <ModuleHero
        :title="ctx.tenantBrandConfig.schoolName + ' · 全景数据驾驶舱'"
        :subtitle="caliberLabel + ' · ' + scopeLabel + ' · 服务端实时聚合'"
        :chips="heroChips"
        :stats="heroStats"
        :flow="overview.stageFlow"
      />

      <section class="mp-card dcd-contract">
        <div class="mp-card__body dcd-contract__body">
          <div>
            <div class="dcd-contract__label">数据截至</div>
            <div class="dcd-contract__value">{{ asOfLabel }}</div>
          </div>
          <div>
            <div class="dcd-contract__label">统计口径</div>
            <div class="dcd-contract__value">{{ caliberLabel }}</div>
          </div>
          <div>
            <div class="dcd-contract__label">数据范围</div>
            <div class="dcd-contract__value">{{ scopeLabel }}</div>
          </div>
          <div>
            <div class="dcd-contract__label">质量提示</div>
            <div class="dcd-contract__value">{{ qualityFlags.length ? qualityFlags.length + ' 项' : '无阻断项' }}</div>
          </div>
        </div>
      </section>

      <div class="mp-grid-cards">
        <button
          v-for="m in visibleMetrics"
          :key="m.key"
          type="button"
          class="dcd-metric"
          :title="m.drillRoute ? '进入权威业务页：' + m.drillLabel : m.description"
          @click="drill(m)"
        >
          <div class="dcd-metric__head">
            <span class="dcd-metric__label">{{ m.label }}</span>
            <StatusTag type="info" :label="m.sourceModule" />
          </div>
          <div class="dcd-metric__value">
            {{ m.value }}<span class="dcd-metric__unit">{{ m.unit }}</span>
          </div>
          <div v-if="m.trend" class="dcd-metric__trend" :class="'is-' + (m.trendQuality || 'neutral')">{{ m.trend }}</div>
          <div class="dcd-metric__desc">{{ m.description }}</div>
          <div v-if="m.drillRoute" class="dcd-metric__drill">进入：{{ m.drillLabel }} →</div>
        </button>
      </div>

      <section v-if="qualityFlags.length" class="mp-card">
        <div class="mp-card__head"><span class="mp-card__title">数据质量提示</span></div>
        <div class="mp-card__body mp-stack">
          <div v-for="flag in qualityFlags" :key="flag.code" class="dcd-quality">
            <StatusTag :type="flag.severity === 'ERROR' ? 'danger' : 'info'" :label="flag.code" />
            <span>{{ flag.message }}</span>
          </div>
        </div>
      </section>

      <p class="mp-note">
        当前 A4 仅开放已由服务端真实查询实现的在册口径。未实现的自然口径、导出任务等能力不会以切换标签、假 taskId 或演示数据冒充成功。
      </p>
    </div>

    <AppDrawer v-model:visible="guideVisible" title="指标口径与数据来源">
      <div class="mp-stack">
        <div class="mp-kv"><span class="mp-kv__k">数据截至</span><span class="mp-kv__v">{{ asOfLabel }}</span></div>
        <div class="mp-kv"><span class="mp-kv__k">统计口径</span><span class="mp-kv__v">{{ caliberLabel }}</span></div>
        <div class="mp-kv"><span class="mp-kv__k">数据范围</span><span class="mp-kv__v">{{ scopeLabel }}</span></div>
        <div class="mp-kv"><span class="mp-kv__k">服务端来源</span><span class="mp-kv__v">{{ sourceNames || '跨域真实 MySQL 聚合' }}</span></div>
        <section v-for="m in visibleMetrics" :key="m.key" class="dcd-guide">
          <div class="dcd-guide__title">
            {{ m.label }}
            <StatusTag type="info" :label="'来源：' + m.sourceModule" />
          </div>
          <div class="dcd-guide__desc">{{ m.description }}</div>
        </section>
        <div v-for="flag in qualityFlags" :key="'guide-' + flag.code" class="dcd-quality">
          <StatusTag :type="flag.severity === 'ERROR' ? 'danger' : 'info'" :label="flag.code" />
          <span>{{ flag.message }}</span>
        </div>
      </div>
    </AppDrawer>
  </ModulePageShell>
</template>

<script>
import {
  ModulePageShell,
  ModuleHero,
  ModuleToolbar,
  StatusTag,
  LoadingState,
  ErrorState,
  EmptyState
} from '@/components/business'
import { AppGlobalState } from '@/components/common'
import { AppDrawer } from '@/components/ui'
import { dataCenterApi } from '@/modules/dataCenter/api/dataCenter.api'

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
    AppDrawer
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      overview: null,
      guideVisible: false
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
      const allowed = new Set(this.ctx.visibleMetricKeys || [])
      return (this.overview.metrics || []).filter((m) => allowed.has(m.key))
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
      return [
        '当前角色：' + this.ctx.currentRole.roleName,
        '数据范围：' + this.scopeLabel,
        '统计口径：' + this.caliberLabel
      ]
    },
    toolbarActions() {
      return [{ key: 'metricGuide', label: '指标口径与来源', variant: 'ghost' }]
    },
    meta() {
      return (this.overview && this.overview.meta) || {}
    },
    qualityFlags() {
      return Array.isArray(this.meta.qualityFlags) ? this.meta.qualityFlags : []
    },
    sourceNames() {
      const rows = Array.isArray(this.meta.source) ? this.meta.source : []
      return rows.map((x) => x.module).filter(Boolean).join('、')
    },
    scopeLabel() {
      return (this.meta.scope && this.meta.scope.scopeName) || this.ctx.dataScope.scopeName || '—'
    },
    caliberLabel() {
      return this.meta.caliberLabel || (this.overview && this.overview.caliberLabel) || '在册口径'
    },
    asOfLabel() {
      return this.meta.asOf || (this.overview && this.overview.updatedAt) || '—'
    }
  },
  created() {
    if (this.viewAllowed) this.load()
  },
  methods: {
    async load() {
      this.loading = true
      this.error = ''
      const res = await dataCenterApi.getOverview({ caliber: 'REGISTERED' })
      if (res.code === 0) {
        this.overview = res.data
      } else {
        this.overview = null
        this.error = res.message
      }
      this.loading = false
    },
    drill(metric) {
      if (metric.drillRoute) this.$router.push(metric.drillRoute)
    },
    onToolbar(key) {
      if (key === 'metricGuide') this.guideVisible = true
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.dcd-contract__body {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--space-4);
}
.dcd-contract__label { font-size: var(--font-size-xs); color: var(--text-tertiary); }
.dcd-contract__value {
  margin-top: var(--space-1);
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
  overflow-wrap: anywhere;
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
.dcd-metric:hover { border-color: var(--primary-500); box-shadow: var(--shadow-card-hover); }
.dcd-metric__head { display: flex; align-items: center; justify-content: space-between; gap: var(--space-2); }
.dcd-metric__label { font-size: var(--font-size-sm); color: var(--text-secondary); font-weight: var(--font-weight-medium); }
.dcd-metric__value {
  font-size: var(--font-size-metric-sm);
  font-weight: var(--font-weight-bold);
  font-variant-numeric: var(--font-numeric);
  color: var(--text-primary);
  line-height: 1.2;
}
.dcd-metric__unit { font-size: var(--font-size-sm); font-weight: var(--font-weight-normal); color: var(--text-tertiary); margin-left: var(--space-1); }
.dcd-metric__trend { font-size: var(--font-size-xs); }
.dcd-metric__trend.is-good { color: var(--trend-good); }
.dcd-metric__trend.is-bad { color: var(--trend-bad); }
.dcd-metric__trend.is-neutral { color: var(--trend-neutral); }
.dcd-metric__desc { font-size: var(--font-size-xs); color: var(--text-tertiary); line-height: var(--line-height-base); }
.dcd-metric__drill { margin-top: auto; padding-top: var(--space-2); font-size: var(--font-size-xs); color: var(--text-link); font-weight: var(--font-weight-medium); }
.dcd-guide { border-bottom: 1px dashed var(--border-light); padding-bottom: var(--space-3); }
.dcd-guide:last-of-type { border-bottom: none; }
.dcd-guide__title { display: flex; align-items: center; justify-content: space-between; gap: var(--space-2); font-weight: var(--font-weight-semibold); }
.dcd-guide__desc { margin-top: var(--space-1); color: var(--text-secondary); font-size: var(--font-size-sm); line-height: var(--line-height-base); }
.dcd-quality { display: flex; align-items: flex-start; gap: var(--space-2); color: var(--text-secondary); font-size: var(--font-size-sm); }
@media (max-width: 960px) {
  .dcd-contract__body { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
</style>
