<template>
  <ModulePageShell
    title="风险预警数据"
    :subtitle="risk ? '当前实时风险 ' + risk.total + ' 条 · 数据截至 ' + asOfLabel : '来源分布 · 等级分布 · 数据质量说明'"
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
      v-else-if="!risk"
      title="暂无可证明的风险统计数据"
      description="本页不会用演示记录或浏览器估算补齐风险数字。"
    />

    <div v-else class="mp-stack">
      <section class="mp-card dcrk-contract">
        <div class="mp-card__body dcrk-contract__body">
          <div>
            <div class="dcrk-contract__label">数据范围</div>
            <div class="dcrk-contract__value">{{ scopeLabel }}</div>
          </div>
          <div>
            <div class="dcrk-contract__label">统计口径</div>
            <div class="dcrk-contract__value">{{ caliberLabel }}</div>
          </div>
          <div>
            <div class="dcrk-contract__label">数据来源</div>
            <div class="dcrk-contract__value">{{ sourceNames || '服务端真实聚合' }}</div>
          </div>
          <div>
            <div class="dcrk-contract__label">质量提示</div>
            <div class="dcrk-contract__value">{{ qualityFlags.length ? qualityFlags.length + ' 项' : '无阻断项' }}</div>
          </div>
        </div>
      </section>

      <div class="mp-grid-2">
        <section class="mp-card">
          <div class="mp-card__head">
            <span class="mp-card__title">风险来源分布</span>
            <span class="mp-note">合计 {{ risk.total }} 条</span>
          </div>
          <div class="mp-card__body mp-stack">
            <EmptyState
              v-if="!risk.bySource || !risk.bySource.length"
              title="暂无风险来源数据"
              description="当前真实聚合未命中风险记录。"
            />
            <div v-for="s in risk.bySource || []" v-else :key="s.moduleCode" class="dcrk-bar">
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
          <div class="mp-card__head"><span class="mp-card__title">风险等级分布</span></div>
          <div class="mp-card__body mp-stack">
            <div v-for="l in risk.byLevel || []" :key="l.level" class="dcrk-bar">
              <span class="dcrk-bar__label"><RiskTag :level="l.level" /></span>
              <div class="dcrk-bar__track">
                <div class="dcrk-bar__fill" :class="'is-' + l.level" :style="{ width: levelWidth(l) }" />
              </div>
              <span class="dcrk-bar__value">{{ l.count }} 条</span>
            </div>
          </div>
        </section>
      </div>

      <div class="mp-grid-2">
        <section class="mp-card">
          <div class="mp-card__head"><span class="mp-card__title">处理进度</span></div>
          <div class="mp-card__body">
            <div v-if="risk.byStatus && risk.byStatus.length" class="mp-stack">
              <div v-for="st in risk.byStatus" :key="st.key" class="mp-kv">
                <span class="mp-kv__k">{{ st.label }}</span>
                <span class="mp-kv__v">{{ st.count }} 条</span>
              </div>
            </div>
            <EmptyState
              v-else
              title="处理进度口径尚未统一"
              description="跨业务域的待处理/跟进中/已关闭状态还没有统一服务端合同；空白代表未配置，不代表 0。"
            />
          </div>
        </section>

        <section class="mp-card">
          <div class="mp-card__head"><span class="mp-card__title">历史趋势</span></div>
          <div class="mp-card__body">
            <div v-if="hasTrend" class="dcrk-trend-list">
              <div v-for="(m, i) in risk.trend.months" :key="m" class="mp-kv">
                <span class="mp-kv__k">{{ m }}</span>
                <span class="mp-kv__v">总量 {{ risk.trend.total[i] }} · 高风险 {{ risk.trend.high[i] }}</span>
              </div>
            </div>
            <EmptyState
              v-else
              title="历史趋势尚未配置"
              description="统计快照表尚未形成统一历史序列；系统不会用 0 或演示曲线填充。"
            />
          </div>
        </section>
      </div>

      <section class="mp-card">
        <div class="mp-card__head"><span class="mp-card__title">明细能力边界</span></div>
        <div class="mp-card__body">
          <p class="dcrk-boundary">
            跨域“风险学生名单”尚未形成统一服务端命中口径，批量提醒和风险导出也尚未接入正式任务链，因此本页不提供这些入口。风险处置请进入对应业务模块，以各域权威记录和权限规则为准。
          </p>
        </div>
      </section>

      <section v-if="qualityFlags.length" class="mp-card">
        <div class="mp-card__head"><span class="mp-card__title">数据质量提示</span></div>
        <div class="mp-card__body mp-stack">
          <div v-for="flag in qualityFlags" :key="flag.code" class="dcrk-quality">
            <StatusTag :type="flag.severity === 'ERROR' ? 'danger' : 'info'" :label="flag.code" />
            <span>{{ flag.message }}</span>
          </div>
        </div>
      </section>
    </div>

    <AppDrawer v-model:visible="guideVisible" title="风险数据口径">
      <div class="mp-stack">
        <div class="mp-kv"><span class="mp-kv__k">数据截至</span><span class="mp-kv__v">{{ asOfLabel }}</span></div>
        <div class="mp-kv"><span class="mp-kv__k">统计口径</span><span class="mp-kv__v">{{ caliberLabel }}</span></div>
        <div class="mp-kv"><span class="mp-kv__k">数据范围</span><span class="mp-kv__v">{{ scopeLabel }}</span></div>
        <div class="mp-kv"><span class="mp-kv__k">来源</span><span class="mp-kv__v">{{ sourceNames || '服务端真实聚合' }}</span></div>
        <p class="mp-note">空数组表示服务端尚未形成对应统一口径，而不是业务事实为 0。</p>
        <div v-for="flag in qualityFlags" :key="'drawer-' + flag.code" class="dcrk-quality">
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
  ModuleToolbar,
  StatusTag,
  RiskTag,
  LoadingState,
  ErrorState,
  EmptyState
} from '@/components/business'
import { AppGlobalState } from '@/components/common'
import { AppDrawer } from '@/components/ui'
import { dataCenterApi } from '@/modules/dataCenter/api/dataCenter.api'

export default {
  name: 'DataCenterRiskView',
  components: {
    ModulePageShell,
    ModuleToolbar,
    StatusTag,
    RiskTag,
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
      risk: null,
      guideVisible: false
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
    toolbarActions() {
      return [{ key: 'metricGuide', label: '数据口径与质量', variant: 'ghost' }]
    },
    meta() {
      return (this.risk && this.risk.meta) || {}
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
      return this.meta.caliberLabel || '服务端实时风险口径'
    },
    asOfLabel() {
      return this.meta.asOf || (this.risk && this.risk.updatedAt) || '—'
    },
    hasTrend() {
      return !!(
        this.risk && this.risk.trend &&
        Array.isArray(this.risk.trend.months) && this.risk.trend.months.length &&
        Array.isArray(this.risk.trend.total) && Array.isArray(this.risk.trend.high)
      )
    }
  },
  created() {
    if (this.viewAllowed) this.load()
  },
  methods: {
    sourceWidth(s) {
      const rows = (this.risk && this.risk.bySource) || []
      const max = Math.max(0, ...rows.map((x) => Number(x.count) || 0))
      if (!max) return '0%'
      return Math.round(((Number(s.count) || 0) / max) * 100) + '%'
    },
    levelWidth(l) {
      if (!this.risk || !this.risk.total) return '0%'
      return Math.round(((Number(l.count) || 0) / this.risk.total) * 100) + '%'
    },
    onToolbar(key) {
      if (key === 'metricGuide') this.guideVisible = true
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await dataCenterApi.getRiskStats()
      if (res.code === 0) {
        this.risk = res.data
      } else {
        this.risk = null
        this.error = res.message
      }
      this.loading = false
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.dcrk-contract__body {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--space-4);
}
.dcrk-contract__label {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}
.dcrk-contract__value {
  margin-top: var(--space-1);
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  overflow-wrap: anywhere;
}
.dcrk-bar {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}
.dcrk-bar__label {
  width: 96px;
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
}
.dcrk-bar__fill.is-HIGH { background: var(--danger-500); }
.dcrk-bar__fill.is-MEDIUM { background: var(--warning-500); }
.dcrk-bar__fill.is-LOW { background: var(--info-500); }
.dcrk-bar__value {
  width: 64px;
  flex-shrink: 0;
  text-align: right;
  font-size: var(--font-size-xs);
  color: var(--text-secondary);
  font-variant-numeric: var(--font-numeric);
}
.dcrk-boundary {
  margin: 0;
  padding: var(--space-3);
  border: 1px solid var(--info-100);
  border-radius: var(--radius-md);
  background: var(--info-50);
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
  line-height: var(--line-height-base);
}
.dcrk-quality {
  display: flex;
  align-items: flex-start;
  gap: var(--space-2);
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
}
@media (max-width: 960px) {
  .dcrk-contract__body { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
</style>
