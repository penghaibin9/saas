<template>
  <ModulePageShell
    title="毕业设计中心"
    :subtitle="hero.batchName + ' · ' + hero.batchStatus"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <ModuleToolbar :actions="toolbarActions" @action="onToolbar" />
    </template>

    <ErrorState v-if="error" :description="error" @retry="load" />
    <LoadingState v-else-if="loading" />
    <div v-else class="mp-stack">
      <ModuleHero
        :title="ctx.tenantBrandConfig.schoolName + ' · 毕业设计总览'"
        :subtitle="hero.batchName + '（' + hero.batchRange + '）'"
        :chips="heroChips"
        :stats="hero.stats"
        :flow="hero.flow"
      />

      <section v-if="hero.moduleStats && hero.moduleStats.length" class="mp-card">
        <div class="mp-card__head">
          <span class="mp-card__title">跨模块统计</span>
          <button class="mp-link" @click="$router.push('/admin/graduation/risk-archive?panel=stats')">完整统计 →</button>
        </div>
        <div class="mp-card__body gdb-modstats">
          <div v-for="s in hero.moduleStats" :key="s.label" class="gdb-modstat">
            <div class="gdb-modstat__val">{{ s.value }}</div>
            <div class="gdb-modstat__label">{{ s.label }}</div>
            <div class="gdb-modstat__hint">{{ s.hint }}</div>
          </div>
        </div>
      </section>

      <div class="mp-grid-2">
        <section class="mp-card">
          <div class="mp-card__head">
            <span class="mp-card__title">今日待办</span>
            <button class="mp-link" @click="$router.push('/admin/graduation/students')">毕设学生 →</button>
          </div>
          <div class="mp-card__body mp-stack">
            <div v-for="t in hero.todos" :key="t.id" class="mp-kv">
              <span class="mp-kv__k">
                <StatusTag :type="t.tone === 'danger' ? 'danger' : 'warning'" :label="String(t.count)" dot />
                <span class="gdb-todo-label">{{ t.label }}</span>
                <span class="mp-note">（{{ t.hint }}）</span>
              </span>
              <button class="mp-link" @click="$router.push(t.route)">去处理</button>
            </div>
          </div>
        </section>

        <section class="mp-card">
          <div class="mp-card__head">
            <span class="mp-card__title">滞后与风险提醒</span>
            <button class="mp-link" @click="$router.push('/admin/graduation/students')">滞后学生 →</button>
          </div>
          <div class="mp-card__body">
            <ul class="mp-timeline">
              <li v-for="r in hero.riskAlerts" :key="r.id" class="mp-timeline__item" :class="r.level === 'HIGH' ? 'is-danger' : 'is-warning'">
                <div class="mp-timeline__title">
                  {{ r.code }} · {{ r.title }}
                  <RiskTag :level="r.level" />
                </div>
                <div class="mp-timeline__desc">{{ r.detail }}</div>
                <div class="mp-timeline__time">{{ r.time }}</div>
              </li>
            </ul>
          </div>
        </section>
      </div>

      <p class="mp-note">进度洞察可下钻：滞后学生 → 毕设学生列表（按风险筛选）；批量提醒 / 导出均写入审计日志。</p>
    </div>
    <!-- 首次进入本模块时的 4 步说明；「已看过」存后端偏好，顶栏「?」可重看 -->
    <AppPageGuide guide-key="graduation.gd-dashboard" />
  </ModulePageShell>
</template>

<script>
/** 毕业设计中心 · 管理看板（/admin/graduation）。 */
import { AppPageGuide } from '@/components/common'
import { ModulePageShell, ModuleHero, ModuleToolbar, StatusTag, RiskTag, LoadingState, ErrorState } from '@/components/business'
import { graduationApi } from '@/modules/graduation/api/graduation.api'

export default {
  name: 'GraduationDashboardView',
  components: { AppPageGuide, ModulePageShell, ModuleHero, ModuleToolbar, StatusTag, RiskTag, LoadingState, ErrorState },
  props: { ctx: { type: Object, required: true } },
  data() {
    return { loading: true, error: '', hero: { stats: [], flow: [], todos: [], riskAlerts: [], moduleStats: [], batchName: '', batchRange: '', batchStatus: '' } }
  },
  computed: {
    toolbarActions() {
      const pa = this.ctx.permissionActions
      return [
        { key: 'createBatch', label: '＋ 新增毕设批次', variant: 'primary' },
        { key: 'importStudents', label: '导入学生名单' },
        { key: 'exportStats', label: '导出进度统计' },
        { key: 'viewAuditLog', label: '操作日志', variant: 'ghost' }
      ]
        .filter((a) => pa[a.key] && pa[a.key].visible)
        .map((a) => ({ ...a, disabled: !pa[a.key].allowed, disabledReason: pa[a.key].reason }))
    },
    heroChips() {
      return ['当前角色：' + this.ctx.currentRole.roleName, '数据范围：' + this.ctx.dataScope.scopeName]
    }
  },
  created() {
    this.load()
  },
  methods: {
    async load() {
      this.loading = true
      this.error = ''
      const res = await graduationApi.getDashboardSummary()
      if (res.code === 0) this.hero = res.data
      else this.error = res.message
      this.loading = false
    },
    onToolbar(key) {
      // 看板工具栏跳转到对应真实业务页，不做假动作
      const map = {
        createBatch: '/admin/graduation/batches?panel=create',
        importStudents: '/admin/graduation/students?panel=roster',
        exportStats: '/admin/graduation/risk-archive?panel=stats',
        viewAuditLog: '/admin/graduation/risk-archive?panel=risk'
      }
      if (map[key]) this.$router.push(map[key])
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.gdb-todo-label {
  color: var(--text-primary);
  font-weight: var(--font-weight-medium);
  margin: 0 var(--space-1);
}
.gdb-modstats { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: var(--space-3); }
.gdb-modstat { padding: var(--space-3); background: var(--gray-50); border: 1px solid var(--border-light); border-radius: var(--radius-md); }
.gdb-modstat__val { font-size: var(--font-size-xl); font-weight: var(--font-weight-semibold); color: var(--text-primary); }
.gdb-modstat__label { font-size: var(--font-size-sm); color: var(--text-secondary); margin-top: 2px; }
.gdb-modstat__hint { font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 4px; }
</style>
