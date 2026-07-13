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

      <section class="idb-path" aria-label="实习业务路径">
        <div class="idb-path__intro">
          <span class="idb-eyebrow">WORKFLOW</span>
          <strong>实习业务路径</strong>
          <span>按批次推进，优先处理阻塞项</span>
        </div>
        <div class="idb-path__steps">
          <button
            v-for="(stage, index) in workflowStages"
            :key="stage.to"
            type="button"
            class="idb-path__step"
            @click="$router.push(stage.to)"
          >
            <span class="idb-path__index">0{{ index + 1 }}</span>
            <span class="idb-path__copy">
              <strong>{{ stage.label }}</strong>
              <small>{{ stage.hint }}</small>
            </span>
            <span class="idb-path__arrow" aria-hidden="true">→</span>
          </button>
        </div>
      </section>

      <section id="idb-batch-progress" class="mp-card">
        <div class="mp-card__head">
          <span class="mp-card__title">当前批次进度</span>
          <button class="mp-link" @click="$router.push('/admin/internship/batches')">批次管理 →</button>
        </div>
        <div class="mp-card__body">
          <div class="idb-progress-wrap">
            <div class="idb-progress">
              <div class="idb-progress__bar">
                <span class="idb-progress__fill" :style="{ width: batchProgress + '%' }"></span>
              </div>
              <span class="idb-progress__text">在岗 {{ hero.flow.find(f => f.active)?.value || 0 }} 人 · 在岗率 {{ batchProgress }}%</span>
            </div>
            <div class="idb-progress__rate" aria-label="当前在岗率">
              <strong>{{ batchProgress }}<small>%</small></strong>
              <span>当前在岗率</span>
            </div>
          </div>
          <div class="idb-flow">
            <div v-for="(f, index) in hero.flow" :key="f.label" class="idb-flow__item" :class="{ 'is-active': f.active }">
              <span class="idb-flow__index">0{{ index + 1 }}</span>
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
            <div v-for="t in hero.todos" :key="t.id" class="mp-kv idb-todo" :class="{ 'is-danger': t.tone === 'danger' }">
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
            <ul v-else class="mp-timeline idb-risk-list">
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
    workflowStages() {
      return [
        { label: '批次建档', hint: '范围与名单', to: '/admin/internship/batches' },
        { label: '岗位匹配', hint: '意向与落岗', to: '/admin/internship/match-assign' },
        { label: '协议到岗', hint: '协议与签到', to: '/admin/internship/agreements' },
        { label: '过程指导', hint: '周报与走访', to: '/admin/internship/reports' },
        { label: '风险处置', hint: '预警与闭环', to: '/admin/internship/risks' },
        { label: '评价归档', hint: '成绩与留档', to: '/admin/internship/scores' }
      ]
    },
    batchProgress() {
      return this.hero.batchProgress ?? 0
    },
    toolbarActions() {
      const pa = this.ctx.permissionActions
      const def = [
        { key: 'createBatch', label: '＋ 新增实习批次', variant: 'primary' },
        { key: 'importStudents', label: '导入实习学生' },
        { key: 'exportGroup', label: '统计报表' },
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
.idb-path {
  display: flex;
  align-items: stretch;
  gap: var(--space-5);
  padding: 16px 18px;
  border: 1px solid var(--pri-100, #dbeafe);
  border-radius: 16px;
  background: linear-gradient(112deg, var(--pri-bg, #eff6ff), rgba(255, 255, 255, .9) 62%);
}
.idb-path__intro { display: flex; flex: 0 0 158px; flex-direction: column; justify-content: center; gap: 3px; color: var(--t2, #4b5563); font-size: 12px; }
.idb-path__intro strong { color: var(--t1, #111827); font-size: 15px; }
.idb-eyebrow { color: var(--pri, #2563eb); font-size: 10px; font-weight: 800; letter-spacing: .12em; }
.idb-path__steps { display: grid; flex: 1; grid-template-columns: repeat(6, minmax(104px, 1fr)); gap: 8px; min-width: 0; }
.idb-path__step { display: flex; align-items: center; gap: 8px; min-width: 0; padding: 8px; border: 1px solid transparent; border-radius: 10px; background: transparent; color: inherit; text-align: left; cursor: pointer; transition: .18s ease; }
.idb-path__step:hover { border-color: var(--pri-100, #dbeafe); background: rgba(255, 255, 255, .9); box-shadow: 0 6px 14px rgba(30, 64, 175, .08); transform: translateY(-1px); }
.idb-path__index { color: var(--pri, #2563eb); font-size: 10px; font-weight: 800; font-variant-numeric: tabular-nums; }
.idb-path__copy { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.idb-path__copy strong { overflow: hidden; color: var(--t1, #111827); font-size: 12px; white-space: nowrap; text-overflow: ellipsis; }
.idb-path__copy small { overflow: hidden; color: var(--t3, #6b7280); font-size: 11px; white-space: nowrap; text-overflow: ellipsis; }
.idb-path__arrow { margin-left: auto; color: var(--t3, #9ca3af); }
.idb-progress-wrap { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: var(--space-5); align-items: center; margin-bottom: var(--space-4); }
.idb-progress { display: flex; flex-direction: column; gap: var(--space-2); }
.idb-progress__bar { height: 10px; background: var(--fill-2, #edf0f5); border-radius: 999px; overflow: hidden; box-shadow: inset 0 1px 2px rgba(15, 23, 42, .08); }
.idb-progress__fill { display: block; height: 100%; border-radius: inherit; background: linear-gradient(90deg, var(--pri, #2563eb), #54a4ff); transition: width .3s; }
.idb-progress__text { font-size: var(--font-size-sm); color: var(--text-secondary); }
.idb-progress__rate { display: flex; flex-direction: column; align-items: flex-end; padding-left: var(--space-5); border-left: 1px solid var(--card-b, #e5e7eb); }
.idb-progress__rate strong { color: var(--pri, #2563eb); font-size: 26px; line-height: 1; font-variant-numeric: tabular-nums; }
.idb-progress__rate small { font-size: 13px; }
.idb-progress__rate span { margin-top: 4px; color: var(--t3, #6b7280); font-size: 11px; }
.idb-flow { display: grid; grid-template-columns: repeat(auto-fit, minmax(90px, 1fr)); gap: 10px; }
.idb-flow__item { position: relative; min-width: 72px; padding: 10px 8px; border: 1px solid var(--border-subtle, #e5e7eb); border-radius: 10px; background: var(--card-bg, #fff); text-align: center; }
.idb-flow__item.is-active { border-color: var(--pri, #2563eb); background: var(--pri-bg, #eff6ff); box-shadow: 0 6px 14px rgba(37, 99, 235, .1); }
.idb-flow__index { position: absolute; top: 6px; left: 7px; color: var(--t3, #9ca3af); font-size: 9px; font-weight: 700; }
.idb-flow__val { display: block; font-size: var(--font-size-lg); font-weight: var(--font-weight-semibold); }
.idb-flow__lbl { font-size: var(--font-size-xs); color: var(--text-secondary); }
.idb-todo { padding: 8px 0; border-bottom: 1px solid var(--card-b, #eef0f3); }
.idb-todo:last-child { border-bottom: 0; }
.idb-todo.is-danger { margin: 0 -8px; padding: 8px; border-radius: 8px; border-bottom-color: transparent; background: rgba(254, 242, 242, .7); }
.idb-risk-list :deep(.mp-timeline__item) { border-radius: 10px; transition: background .18s ease; }
.idb-risk-list :deep(.mp-timeline__item:hover) { background: var(--fill-2, #f8fafc); }
@media (max-width: 1280px) { .idb-path { align-items: flex-start; flex-direction: column; gap: 10px; } .idb-path__intro { flex-basis: auto; } .idb-path__steps { width: 100%; } }
@media (max-width: 940px) { .idb-path__steps { grid-template-columns: repeat(3, 1fr); } }
@media (max-width: 640px) { .idb-path__steps { grid-template-columns: repeat(2, 1fr); } .idb-progress-wrap { grid-template-columns: 1fr; } .idb-progress__rate { align-items: flex-start; padding: 10px 0 0; border-top: 1px solid var(--card-b, #e5e7eb); border-left: 0; } }
</style>
