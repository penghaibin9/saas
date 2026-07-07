<template>
  <ModulePageShell
    title="迎新统计"
    subtitle="全校迎新数据总览（数据按当前角色数据范围统计）"
    :role-name="roleName"
    :data-scope-name="dataScopeName"
    watermark-purpose="迎新统计"
  >
    <NoPermissionState v-if="noPermission" @back="$router.back()" />
    <template v-else>
      <LoadingState v-if="loading" />
      <ErrorState v-else-if="error" :description="error" @retry="load" />
      <template v-else>
        <div class="ost-head">
          <span class="ost-head__name">{{ data.batchName }}</span>
          <span class="ost-head__period">{{ data.batchPeriod }}</span>
          <span class="ost-head__time">更新于 {{ data.updateTime ? String(data.updateTime).slice(0, 16).replace('T', ' ') : '—' }}</span>
        </div>

        <!-- KPI 卡片 -->
        <div class="ost-kpis">
          <div v-for="k in data.kpis" :key="k.key" class="ost-kpi" :class="'ost-kpi--' + (k.trendQuality || 'neutral')">
            <div class="ost-kpi__label">{{ k.label }}</div>
            <div class="ost-kpi__value">{{ k.value }}</div>
            <div v-if="k.trend" class="ost-kpi__trend">{{ k.trend }}</div>
          </div>
        </div>

        <!-- 环节漏斗 -->
        <section class="ost-card">
          <div class="ost-card__title">报到环节完成漏斗</div>
          <div v-if="!data.stepFunnel.length" class="ost-empty">暂无环节数据</div>
          <div v-for="s in data.stepFunnel" v-else :key="s.key" class="ost-funnel">
            <span class="ost-funnel__label">{{ s.label }}</span>
            <div class="ost-funnel__bar">
              <div class="ost-funnel__fill" :style="{ width: barWidth(s.done) + '%' }" />
            </div>
            <span class="ost-funnel__num">{{ s.done }}</span>
          </div>
        </section>

        <!-- 待办 -->
        <section class="ost-card">
          <div class="ost-card__title">待办概览</div>
          <div class="ost-todos">
            <button v-for="t in data.todos" :key="t.id" type="button" class="ost-todo" @click="go(t.link)">
              <span class="ost-todo__label">{{ t.label }}</span>
              <span class="ost-todo__value">{{ t.value }}</span>
            </button>
          </div>
        </section>
      </template>
    </template>
  </ModulePageShell>
</template>

<script>
/** /admin/orientation/statistics 迎新统计（KPI + 环节漏斗 + 待办；真实走 /orientation/dashboard）。 */
import { ModulePageShell, LoadingState, ErrorState } from '@/components/business'
import { NoPermissionState } from '@/modules/orientation/components'
import * as api from '@/modules/orientation/api/orientation.api'

export default {
  name: 'OrientationStatsView',
  components: { ModulePageShell, LoadingState, ErrorState, NoPermissionState },
  data() {
    return {
      ctx: null,
      loading: true,
      error: '',
      data: { batchName: '', batchPeriod: '', updateTime: '', kpis: [], stepFunnel: [], todos: [] }
    }
  },
  computed: {
    roleName() { return this.ctx?.currentRole?.roleName || '' },
    dataScopeName() { return this.ctx?.dataScope?.name || '' },
    perms() { return this.ctx?.permissionActions || {} },
    noPermission() { const p = this.perms['orientation.student.view']; return p ? !p.allowed : false },
    maxDone() { return Math.max(1, ...this.data.stepFunnel.map((s) => s.done || 0)) }
  },
  async created() {
    const ctx = await api.getOrientationContext()
    if (ctx.code === 0) this.ctx = ctx.data
    await this.load()
  },
  methods: {
    async load() {
      this.loading = true; this.error = ''
      try {
        const res = await api.getOrientationDashboard()
        if (res.code === 0) {
          this.data = {
            batchName: res.data.batchName || '',
            batchPeriod: res.data.batchPeriod || '',
            updateTime: res.data.updateTime || '',
            kpis: res.data.kpis || [],
            stepFunnel: res.data.stepFunnel || [],
            todos: res.data.todos || []
          }
        } else this.error = res.message
      } catch (e) { this.error = e.message || '加载失败' } finally { this.loading = false }
    },
    barWidth(done) { return Math.round(((done || 0) / this.maxDone) * 100) },
    go(link) { if (link) this.$router.push(link) }
  }
}
</script>

<style scoped>
.ost-head {
  display: flex;
  align-items: baseline;
  gap: 14px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}
.ost-head__name {
  font-size: 16px;
  font-weight: var(--font-weight-bold);
  color: var(--t1);
}
.ost-head__period {
  font-size: 13px;
  color: var(--t2);
}
.ost-head__time {
  font-size: 12px;
  color: var(--t3);
  margin-left: auto;
}
.ost-kpis {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(170px, 1fr));
  gap: 12px;
  margin-bottom: 18px;
}
.ost-kpi {
  padding: 14px 16px;
  border: 1px solid var(--card-b);
  border-radius: 12px;
  background: var(--card);
}
.ost-kpi__label {
  font-size: 12.5px;
  color: var(--t3);
}
.ost-kpi__value {
  font-size: 26px;
  font-weight: var(--font-weight-bold);
  color: var(--t1);
  margin: 4px 0;
  font-variant-numeric: tabular-nums;
}
.ost-kpi__trend {
  font-size: 11.5px;
  color: var(--t2);
}
.ost-kpi--good .ost-kpi__value {
  color: #16a34a;
}
.ost-kpi--bad .ost-kpi__value {
  color: #dc2626;
}
.ost-card {
  border: 1px solid var(--card-b);
  border-radius: 12px;
  background: var(--card);
  padding: 16px;
  margin-bottom: 16px;
}
.ost-card__title {
  font-size: 14px;
  font-weight: var(--font-weight-semibold);
  color: var(--t1);
  margin-bottom: 12px;
}
.ost-funnel {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 9px;
}
.ost-funnel__label {
  width: 92px;
  flex-shrink: 0;
  font-size: 12.5px;
  color: var(--t2);
}
.ost-funnel__bar {
  flex: 1;
  height: 14px;
  border-radius: 7px;
  background: var(--pri-bg);
  overflow: hidden;
}
.ost-funnel__fill {
  height: 100%;
  border-radius: 7px;
  background: var(--btn-p-bg);
  transition: width 0.3s ease;
}
.ost-funnel__num {
  width: 44px;
  text-align: right;
  font-size: 12.5px;
  color: var(--t1);
  font-variant-numeric: tabular-nums;
}
.ost-todos {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}
.ost-todo {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  border: 1px solid var(--card-b);
  border-radius: 10px;
  background: var(--bg-card);
  cursor: pointer;
  font-family: inherit;
}
.ost-todo:hover {
  border-color: var(--glow);
}
.ost-todo__label {
  font-size: 13px;
  color: var(--t2);
}
.ost-todo__value {
  font-size: 15px;
  font-weight: var(--font-weight-bold);
  color: var(--pri);
}
.ost-empty {
  font-size: 12.5px;
  color: var(--t3);
}
</style>
