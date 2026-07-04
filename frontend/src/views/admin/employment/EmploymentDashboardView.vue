<template>
  <ModulePageShell title="就业服务管理看板" :subtitle="subtitle" :role-name="roleName" :data-scope-name="dataScopeName" watermark-purpose="就业看板查阅">
    <LoadingState v-if="loading" text="正在加载就业看板…" />
    <ErrorState v-else-if="error" :description="error" @retry="load" />
    <template v-else-if="board">
      <ModuleHero
        :title="board.batchName"
        :subtitle="`批次周期 ${board.batchPeriod} · 数据更新于 ${board.updateTime}`"
        :chips="heroChips"
        :stats="board.kpis"
        :flow="board.flow"
      />

      <div class="emp-grid">
        <div class="emp-col">
          <section class="emp-section">
            <div class="emp-section__head">
              <h3 class="emp-section__title">学院去向落实率</h3>
              <button type="button" class="emp-section__more" @click="go('/admin/employment/students')">查看就业学生列表 →</button>
            </div>
            <div v-for="c in board.collegeRates" :key="c.name" class="emp-rate">
              <div class="emp-rate__head">
                <span>{{ c.name }}</span>
                <span class="emp-rate__value">{{ c.implemented }}/{{ c.total }} · {{ c.rate }}%</span>
              </div>
              <div class="emp-rate__track"><div class="emp-rate__bar" :style="{ width: c.rate + '%' }" /></div>
            </div>
          </section>

          <section class="emp-section" style="margin-top: var(--space-4)">
            <h3 class="emp-section__title">去向分布</h3>
            <div class="emp-dist">
              <span v-for="d in board.destinationDist" :key="d.label" class="emp-dist__item">
                {{ d.label }}<b class="emp-dist__value">{{ d.value }}</b>
              </span>
            </div>
          </section>
        </div>

        <div class="emp-col">
          <section class="emp-section">
            <h3 class="emp-section__title">待办事项</h3>
            <div v-for="t in board.todos" :key="t.id" class="emp-todo" @click="goLink(t.link)">
              <span>{{ t.label }}</span>
              <span class="emp-todo__value">{{ t.value }}</span>
            </div>
          </section>

          <section class="emp-section" style="margin-top: var(--space-4)">
            <h3 class="emp-section__title">风险提醒</h3>
            <div v-for="r in board.riskAlerts" :key="r.id" class="emp-alert" @click="goLink(r.link)">
              <RiskTag :level="r.level" />
              <span class="emp-alert__title">{{ r.title }}</span>
              <span>→</span>
            </div>
          </section>
        </div>
      </div>
    </template>
  </ModulePageShell>
</template>

<script>
/** 页面 1：/admin/employment 就业服务首页 / 管理看板（数据全部来自 mock/api）。 */
import { ModulePageShell, ModuleHero, LoadingState, ErrorState, RiskTag } from '@/components/business'
import { getEmploymentContext, getEmploymentDashboard } from '@/modules/employment/api/employment.api'

const LINKS = {
  students: '/admin/employment/students',
  materials: '/admin/employment/materials',
  unemployed: '/admin/employment/unemployed',
  companies: '/admin/employment/companies'
}

export default {
  name: 'EmploymentDashboardView',
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
    async load() {
      this.loading = true
      this.error = ''
      try {
        const [ctxRes, boardRes] = await Promise.all([getEmploymentContext(), getEmploymentDashboard()])
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
@import './employment-page.css';
</style>
