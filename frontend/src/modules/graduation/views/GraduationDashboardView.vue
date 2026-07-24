<template>
  <ModulePageShell
    title="毕业设计中心"
    :subtitle="pageSubtitle"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <ModuleToolbar :actions="toolbarActions" @action="onToolbar" />
    </template>

    <ErrorState v-if="error" :description="error" @retry="load" />
    <LoadingState v-else-if="loading" />
    <EmptyState
      v-else-if="!hasBatch"
      title="请先选择或创建毕设批次"
      description="顶部批次条选择当前工作批次后，再查看本批次运营总览。"
    >
      <template #actions>
        <button class="mp-btn mp-btn--primary" @click="$router.push('/admin/graduation/batches?panel=create')">＋ 新增毕设批次</button>
        <button class="mp-btn" @click="$router.push('/admin/graduation/batches?panel=list')">去批次列表</button>
      </template>
    </EmptyState>
    <div v-else class="mp-stack gdb-page">
      <section class="gdb-command-bar" aria-label="当前毕设批次">
        <div class="gdb-command-bar__primary">
          <span class="gdb-command-bar__eyebrow">毕业设计运营驾驶舱</span>
          <strong>{{ hero.batchName || batchStore.selectedBatchName || '尚未创建毕业设计批次' }}</strong>
          <span v-if="hero.batchRange" class="gdb-command-bar__range">{{ hero.batchRange }}</span>
        </div>
        <div class="gdb-command-bar__scope">
          <span>{{ ctx.currentRole.roleName }}</span>
          <i></i>
          <span>{{ ctx.dataScope.scopeName }}</span>
        </div>
      </section>

      <ModuleHero
        :title="ctx.tenantBrandConfig.schoolName + ' · 毕业设计总览'"
        :subtitle="(hero.batchName || batchStore.selectedBatchName) + '（' + (hero.batchRange || '—') + '）'"
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
          <button
            v-for="s in hero.moduleStats"
            :key="s.label"
            class="gdb-modstat"
            type="button"
            @click="$router.push('/admin/graduation/risk-archive?panel=stats')"
          >
            <div class="gdb-modstat__val">{{ s.value }}</div>
            <div class="gdb-modstat__label">{{ s.label }}</div>
            <div class="gdb-modstat__hint">{{ s.hint }}</div>
          </button>
        </div>
      </section>

      <div class="mp-grid-2">
        <section class="mp-card">
          <div class="mp-card__head">
            <span class="mp-card__title">今日待办</span>
            <button class="mp-link" @click="$router.push('/admin/graduation/students')">毕设学生 →</button>
          </div>
          <div class="mp-card__body gdb-todos">
            <button
              v-for="t in hero.todos"
              :key="t.id"
              class="gdb-todo"
              :class="'is-' + t.tone"
              type="button"
              @click="$router.push(t.route)"
            >
              <span class="gdb-todo__count">{{ t.count }}</span>
              <span class="gdb-todo__copy">
                <span class="gdb-todo__label">{{ t.label }}</span>
                <span class="gdb-todo__hint">{{ t.hint }}</span>
              </span>
              <span class="gdb-todo__action">去处理 <b>→</b></span>
            </button>
          </div>
        </section>

        <section class="mp-card">
          <div class="mp-card__head">
            <span class="mp-card__title">滞后与风险提醒</span>
            <button class="mp-link" @click="$router.push('/admin/graduation/students')">滞后学生 →</button>
          </div>
          <div class="mp-card__body">
            <div v-if="!hero.riskAlerts.length" class="gdb-risk-empty">
              <span class="gdb-risk-empty__icon">✓</span>
              <div>
                <strong>暂未发现待处理风险</strong>
                <p>风险扫描结果会在这里集中展示。</p>
              </div>
            </div>
            <ul v-else class="mp-timeline">
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
  </ModulePageShell>
</template>

<script>
/** 毕业设计中心 · 管理看板（/admin/graduation）。 */
import { ModulePageShell, ModuleHero, ModuleToolbar, RiskTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { graduationApi } from '@/modules/graduation/api/graduation.api'
import { useGraduationBatchStore } from '@/stores/graduationBatch'

export default {
  name: 'GraduationDashboardView',
  components: { ModulePageShell, ModuleHero, ModuleToolbar, RiskTag, LoadingState, ErrorState, EmptyState },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      batchStore: useGraduationBatchStore(),
      loading: true,
      error: '',
      hero: { stats: [], flow: [], todos: [], riskAlerts: [], moduleStats: [], batchName: '', batchRange: '', batchStatus: '' }
    }
  },
  computed: {
    hasBatch() {
      return !!this.batchStore.selectedBatchId
    },
    pageSubtitle() {
      if (!this.hasBatch) return '请先在顶部选择或创建毕设批次'
      const name = this.hero.batchName || this.batchStore.selectedBatchName || '当前批次'
      const status = this.hero.batchStatus || this.batchStore.batchStatus || ''
      return status ? `${name} · ${status}` : name
    },
    toolbarActions() {
      const pa = this.ctx.permissionActions
      return [
        { key: 'createBatch', label: '＋ 新增毕设批次', variant: 'primary' },
        { key: 'importStudents', label: '导入学生名单' },
        { key: 'exportStats', label: '导出进度统计' },
        { key: 'viewAuditLog', label: '操作日志', variant: 'ghost' }
      ]
        .filter((a) => pa[a.key] && pa[a.key].visible)
        .map((a) => ({
          ...a,
          disabled: !pa[a.key].allowed || (a.key !== 'createBatch' && a.key !== 'viewAuditLog' && !this.hasBatch),
          disabledReason: pa[a.key].reason
        }))
    },
    heroChips() {
      return ['当前角色：' + this.ctx.currentRole.roleName, '数据范围：' + this.ctx.dataScope.scopeName]
    }
  },
  created() {
    this.load()
  },
  watch: {
    'batchStore.selectedBatchId'() {
      this.load()
    }
  },
  methods: {
    async load() {
      if (!this.batchStore.selectedBatchId) {
        this.loading = false
        this.error = ''
        this.hero = { stats: [], flow: [], todos: [], riskAlerts: [], moduleStats: [], batchName: '', batchRange: '', batchStatus: '' }
        return
      }
      this.loading = true
      this.error = ''
      const res = await graduationApi.getDashboardSummary({ batchId: this.batchStore.selectedBatchId })
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
        viewAuditLog: '/admin/graduation/audit-logs'
      }
      if (map[key]) this.$router.push(map[key])
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.gdb-page { gap: var(--space-4); }
.gdb-command-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  padding: var(--space-3) var(--space-4);
  border: 1px solid var(--primary-100, #dbeafe);
  border-radius: var(--radius-md);
  background: linear-gradient(100deg, var(--primary-50, #eff6ff), var(--card, #fff) 68%);
}
.gdb-command-bar__primary { display: flex; align-items: baseline; flex-wrap: wrap; gap: 0 var(--space-2); min-width: 0; }
.gdb-command-bar__eyebrow { width: 100%; color: var(--primary-700, #1d4ed8); font-size: var(--font-size-xs); font-weight: var(--font-weight-semibold); letter-spacing: .06em; }
.gdb-command-bar strong { color: var(--text-primary); font-size: var(--font-size-lg); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.gdb-command-bar__range { color: var(--text-secondary); font-size: var(--font-size-sm); }
.gdb-command-bar__scope { display: inline-flex; align-items: center; gap: var(--space-2); color: var(--text-secondary); font-size: var(--font-size-xs); white-space: nowrap; }
.gdb-command-bar__scope i { width: 3px; height: 3px; border-radius: 50%; background: var(--text-tertiary); }
.gdb-modstats { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: var(--space-3); }
.gdb-modstat { appearance: none; text-align: left; padding: var(--space-3); background: var(--gray-50); border: 1px solid var(--border-light); border-radius: var(--radius-md); cursor: pointer; transition: transform .15s ease, border-color .15s ease, box-shadow .15s ease; }
.gdb-modstat:hover { transform: translateY(-2px); border-color: var(--primary-200, #bfdbfe); box-shadow: var(--s1); }
.gdb-modstat:focus-visible, .gdb-todo:focus-visible { outline: 2px solid var(--primary-400, #60a5fa); outline-offset: 2px; }
.gdb-modstat__val { font-size: var(--font-size-xl); font-weight: var(--font-weight-semibold); color: var(--text-primary); }
.gdb-modstat__label { font-size: var(--font-size-sm); color: var(--text-secondary); margin-top: 2px; }
.gdb-modstat__hint { font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 4px; line-height: 1.45; }
.gdb-todos { display: grid; gap: var(--space-2); }
.gdb-todo { display: grid; grid-template-columns: 34px minmax(0, 1fr) auto; align-items: center; gap: var(--space-3); width: 100%; padding: var(--space-2) var(--space-3); border: 1px solid transparent; border-radius: var(--radius-md); background: transparent; color: inherit; text-align: left; cursor: pointer; transition: background .15s ease, border-color .15s ease; }
.gdb-todo:hover { background: var(--gray-50); border-color: var(--border-light); }
.gdb-todo__count { display: grid; place-items: center; width: 32px; height: 32px; border-radius: var(--radius-full); color: var(--primary-700, #1d4ed8); background: var(--primary-50, #eff6ff); font-weight: var(--font-weight-bold); }
.gdb-todo.is-danger .gdb-todo__count { color: var(--danger-700, #b91c1c); background: var(--danger-50, #fef2f2); }
.gdb-todo__copy { display: grid; gap: 2px; min-width: 0; }
.gdb-todo__label { color: var(--text-primary); font-size: var(--font-size-sm); font-weight: var(--font-weight-medium); }
.gdb-todo__hint { overflow: hidden; color: var(--text-tertiary); font-size: var(--font-size-xs); text-overflow: ellipsis; white-space: nowrap; }
.gdb-todo__action { color: var(--text-link, var(--pri, #2563eb)); font-size: var(--font-size-sm); font-weight: var(--font-weight-medium); white-space: nowrap; }
.gdb-todo__action b { font-size: 16px; font-weight: 400; }
.gdb-risk-empty { display: flex; align-items: center; gap: var(--space-3); min-height: 142px; color: var(--text-secondary); }
.gdb-risk-empty__icon { display: grid; place-items: center; flex: 0 0 auto; width: 34px; height: 34px; border-radius: var(--radius-full); background: var(--success-50, #ecfdf5); color: var(--success-700, #047857); font-weight: var(--font-weight-bold); }
.gdb-risk-empty strong { color: var(--text-primary); font-size: var(--font-size-sm); }
.gdb-risk-empty p { margin: 4px 0 0; color: var(--text-tertiary); font-size: var(--font-size-xs); }
@media (max-width: 700px) {
  .gdb-command-bar { align-items: flex-start; flex-direction: column; }
  .gdb-command-bar__scope { white-space: normal; }
  .gdb-todo { grid-template-columns: 32px minmax(0, 1fr); }
  .gdb-todo__action { grid-column: 2; }
}
</style>
