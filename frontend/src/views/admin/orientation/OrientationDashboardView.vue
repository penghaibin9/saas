<template>
  <ModulePageShell title="数字迎新管理看板" :subtitle="subtitle" :role-name="roleName" :data-scope-name="dataScopeName" watermark-purpose="迎新看板查阅">
    <LoadingState v-if="loading" text="正在加载迎新看板…" />
    <ErrorState v-else-if="error" :description="error" @retry="load" />
    <template v-else-if="board">
      <ModuleHero
        :title="board.batchName"
        :subtitle="`${board.batchPeriod} · 数据更新于 ${board.updateTime}`"
        :chips="heroChips"
        :stats="board.kpis"
        :flow="board.flow"
      />

      <div class="ori-grid">
        <div class="ori-col">
          <section class="ori-section">
            <div class="ori-section__head">
              <h3 class="ori-section__title">报到环节完成漏斗</h3>
              <button type="button" class="ori-section__more" @click="go('/admin/orientation/progress')">查看报到进度 →</button>
            </div>
            <div v-for="s in board.stepFunnel" :key="s.key" class="ori-rate">
              <div class="ori-rate__head">
                <span>{{ s.label }}</span>
                <span class="ori-rate__value">{{ s.done }}/{{ totalStudents }}</span>
              </div>
              <div class="ori-rate__track"><div class="ori-rate__bar" :style="{ width: funnelWidth(s) }" /></div>
            </div>
          </section>

          <section class="ori-section" style="margin-top: var(--space-4)">
            <div class="ori-section__head">
              <h3 class="ori-section__title">学院预报到完成率</h3>
              <button type="button" class="ori-section__more" @click="go('/admin/orientation/students')">查看新生列表 →</button>
            </div>
            <div v-for="c in board.collegeRates" :key="c.name" class="ori-rate">
              <div class="ori-rate__head">
                <span>{{ c.name }}</span>
                <span class="ori-rate__value">{{ c.prepared }}/{{ c.total }} · {{ c.rate }}%</span>
              </div>
              <div class="ori-rate__track"><div class="ori-rate__bar" :style="{ width: c.rate + '%' }" /></div>
            </div>
          </section>
        </div>

        <div class="ori-col">
          <section class="ori-section">
            <h3 class="ori-section__title">待办事项</h3>
            <div v-for="t in board.todos" :key="t.id" class="ori-todo" @click="goLink(t.link)">
              <span>{{ t.label }}</span>
              <span class="ori-todo__value">{{ t.value }}</span>
            </div>
          </section>

          <section class="ori-section" style="margin-top: var(--space-4)">
            <h3 class="ori-section__title">风险提醒</h3>
            <div v-for="r in board.riskAlerts" :key="r.id" class="ori-alert" @click="goLink(r.link)">
              <RiskTag :level="r.level" />
              <span class="ori-alert__title">{{ r.title }}</span>
              <span>→</span>
            </div>
          </section>
        </div>
      </div>
    </template>
  </ModulePageShell>
</template>

<script>
/** 页面 1：/admin/orientation 数字迎新首页 / 管理看板（数据全部来自 mock/api）。 */
import { ModulePageShell, ModuleHero, LoadingState, ErrorState, RiskTag } from '@/components/business'
import { getOrientationContext, getOrientationDashboard } from '@/modules/orientation/api/orientation.api'

const LINKS = {
  students: '/admin/orientation/students',
  progress: '/admin/orientation/progress',
  payment: '/admin/orientation/payment',
  materials: '/admin/orientation/materials',
  dorm: '/admin/orientation/dorm',
  exceptions: '/admin/orientation/exceptions'
}

export default {
  name: 'OrientationDashboardView',
  components: { ModulePageShell, ModuleHero, LoadingState, ErrorState, RiskTag },
  data() {
    return { loading: true, error: '', board: null, ctx: null }
  },
  computed: {
    roleName() {
      return this.ctx?.currentRole?.roleName || ''
    },
    dataScopeName() {
      return this.ctx?.dataScope?.name || ''
    },
    subtitle() {
      return this.ctx ? `${this.ctx.tenantBrandConfig.schoolName} · ${this.ctx.tenantBrandConfig.platformDisplayName}` : ''
    },
    heroChips() {
      if (!this.ctx) return []
      return [`角色：${this.roleName}`, `数据范围：${this.dataScopeName}`]
    },
    totalStudents() {
      const kpi = this.board?.kpis?.find((k) => k.key === 'total')
      return kpi ? Number(kpi.value) : 0
    }
  },
  created() {
    this.load()
  },
  methods: {
    go(path) {
      this.$router.push(path)
    },
    goLink(link) {
      if (LINKS[link]) this.go(LINKS[link])
    },
    funnelWidth(s) {
      if (!this.totalStudents) return '0%'
      return `${Math.round((s.done / this.totalStudents) * 100)}%`
    },
    async load() {
      this.loading = true
      this.error = ''
      try {
        const [ctxRes, boardRes] = await Promise.all([getOrientationContext(), getOrientationDashboard()])
        if (ctxRes.code === 0) this.ctx = ctxRes.data
        if (boardRes.code === 0) this.board = boardRes.data
        else this.error = boardRes.message
      } catch (e) {
        this.error = e.message || '加载失败'
      } finally {
        this.loading = false
      }
    }
  }
}
</script>

<style scoped>
@import './orientation-page.css';
</style>
