<template>
  <ModulePageShell
    title="今日工作"
    :subtitle="'集中查看当前实习批次的待办、异常、风险和关键进度' + (hero.batchName ? ' · ' + hero.batchName + '（' + hero.batchStatus + '）' : '')"
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
        id="idb-trends"
        :title="ctx.tenantBrandConfig.schoolName + ' · 实习总览'"
        :subtitle="hero.batchName + '（' + hero.batchRange + '）'"
        :chips="heroChips"
        :stats="hero.stats"
        :flow="hero.flow"
      />

      <section id="idb-batch-progress" class="mp-card">
        <div class="mp-card__head">
          <span class="mp-card__title">当前批次进度</span>
          <button class="mp-link" @click="$router.push('/admin/internship/batches')">批次管理 →</button>
        </div>
        <div class="mp-card__body">
          <div class="idb-progress">
            <div class="idb-progress__bar">
              <span class="idb-progress__fill" :style="{ width: batchProgress + '%' }"></span>
            </div>
            <span class="idb-progress__text">在岗 {{ hero.flow.find(f => f.active)?.value || 0 }} 人 · 在岗率 {{ batchProgress }}%</span>
          </div>
          <div class="idb-flow">
            <div v-for="f in hero.flow" :key="f.label" class="idb-flow__item" :class="{ 'is-active': f.active }">
              <span class="idb-flow__val">{{ f.value }}</span>
              <span class="idb-flow__lbl">{{ f.label }}</span>
            </div>
          </div>
        </div>
      </section>

      <div class="mp-grid-2">
        <section id="idb-todos" class="mp-card">
          <div class="mp-card__head">
            <span class="mp-card__title">我的待办</span>
            <button class="mp-link" @click="$router.push('/admin/internship/students')">实习学生 →</button>
          </div>
          <div class="mp-card__body mp-stack">
            <EmptyState v-if="!hero.todos.length" title="暂无待办" description="当前数据范围内没有待处理事项" />
            <div v-for="t in hero.todos" :key="t.id" class="mp-kv">
              <span class="mp-kv__k">
                <AppStatusTag :type="t.tone === 'danger' ? 'danger' : 'warning'" dot>{{ t.count }}</AppStatusTag>
                <span class="idb-todo-label">{{ t.label }}</span>
                <span class="mp-note">（{{ t.hint }}）</span>
              </span>
              <button class="mp-link" @click="$router.push(t.route)">去处理</button>
            </div>
          </div>
        </section>

        <section class="mp-card">
          <div class="mp-card__head">
            <span class="mp-card__title">风险提醒</span>
            <button class="mp-link" @click="$router.push('/admin/internship/risks')">风险学生 →</button>
          </div>
          <div class="mp-card__body">
            <EmptyState v-if="!hero.riskAlerts.length" title="暂无开放风险" description="系统预警与人工创建的风险单将在此展示" />
            <ul v-else class="mp-timeline">
              <li v-for="r in hero.riskAlerts" :key="r.id" class="mp-timeline__item" :class="r.level === 'HIGH' ? 'is-danger' : 'is-warning'">
                <div class="mp-timeline__title">
                  {{ r.code }} · {{ r.title }}
                  <AppRiskTag :level="r.level" />
                </div>
                <div class="mp-timeline__desc">{{ r.detail }}</div>
                <div class="mp-timeline__time">{{ r.time }}</div>
              </li>
            </ul>
          </div>
        </section>
      </div>

      <p class="mp-note">本页所有操作（含导出）均写入审计日志；指标口径与数据驾驶舱同源，页面不自行计算。</p>
    </div>
  </ModulePageShell>
</template>

<script>
/** 岗位实习中心 · 管理看板（/admin/internship）。数据全部来自 internshipApi。 */
import { ModulePageShell, ModuleHero, ModuleToolbar, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppStatusTag, AppRiskTag } from '@/components/common'
import { internshipApi } from '@/modules/internship/api/internship.api'

const PANEL_ANCHORS = {
  'batch-progress': 'idb-batch-progress',
  todos: 'idb-todos',
  trends: 'idb-trends'
}

export default {
  name: 'InternshipDashboardView',
  components: { ModulePageShell, ModuleHero, ModuleToolbar, AppStatusTag, AppRiskTag, LoadingState, ErrorState, EmptyState },
  props: { ctx: { type: Object, required: true } },
  data() {
    return { loading: true, error: '', hero: { stats: [], flow: [], todos: [], riskAlerts: [], batchName: '', batchRange: '', batchStatus: '', batchProgress: 0 } }
  },
  computed: {
    batchProgress() {
      return this.hero.batchProgress ?? 0
    },
    toolbarActions() {
      const pa = this.ctx.permissionActions
      const def = [
        { key: 'createBatch', label: '＋ 新增实习批次', variant: 'primary' },
        { key: 'importStudents', label: '导入实习学生' },
        { key: 'exportGroup', label: '导出统计数据' },
        { key: 'viewAuditLog', label: '操作日志', variant: 'ghost' }
      ]
      return def
        .filter((a) => pa[a.key] && pa[a.key].visible)
        .map((a) => ({ ...a, disabled: !pa[a.key].allowed, disabledReason: pa[a.key].reason }))
    },
    heroChips() {
      return ['当前角色：' + this.ctx.currentRole.roleName, '数据范围：' + this.ctx.dataScope.scopeName]
    }
  },
  watch: {
    '$route.query.panel': {
      immediate: true,
      handler(panel) {
        this.$nextTick(() => this.scrollToPanel(panel))
      }
    }
  },
  created() {
    this.load()
  },
  methods: {
    scrollToPanel(panel) {
      const id = PANEL_ANCHORS[(panel || '').toString()]
      if (!id) return
      const el = document.getElementById(id)
      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await internshipApi.getDashboardSummary()
      if (res.code === 0) this.hero = res.data
      else this.error = res.message
      this.loading = false
      this.$nextTick(() => this.scrollToPanel(this.$route.query.panel))
    },
    onToolbar(key) {
      const routes = {
        createBatch: '/admin/internship/batches',
        importStudents: '/admin/internship/students',
        exportGroup: '/admin/internship/stats',
        viewAuditLog: '/admin/system/logs'
      }
      const path = routes[key]
      if (path) this.$router.push(path)
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.idb-todo-label {
  color: var(--text-primary);
  font-weight: var(--font-weight-medium);
  margin: 0 var(--space-1);
}
.idb-progress { display: flex; flex-direction: column; gap: var(--space-2); margin-bottom: var(--space-4); }
.idb-progress__bar { height: 8px; background: var(--surface-muted); border-radius: 4px; overflow: hidden; }
.idb-progress__fill { display: block; height: 100%; background: var(--color-primary); transition: width .3s; }
.idb-progress__text { font-size: var(--font-size-sm); color: var(--text-secondary); }
.idb-flow { display: flex; flex-wrap: wrap; gap: var(--space-3); }
.idb-flow__item { min-width: 72px; padding: var(--space-2) var(--space-3); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); text-align: center; }
.idb-flow__item.is-active { border-color: var(--color-primary); background: var(--surface-accent); }
.idb-flow__val { display: block; font-size: var(--font-size-lg); font-weight: var(--font-weight-semibold); }
.idb-flow__lbl { font-size: var(--font-size-xs); color: var(--text-secondary); }
</style>
