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

    <LoadingState v-if="loading" />
    <ErrorState v-else-if="error" :description="error" @retry="load" />
    <div v-else-if="needsBatch" class="mp-card idb-setup">
      <EmptyState
        title="先确定今天要处理的实习批次"
        :description="batchStore.needsExplicitSelect ? '当前有多个进行中批次，请从顶部批次条选择一个后继续。' : '当前没有可用工作批次，可先创建批次并配置学生范围。'"
      >
        <template #actions>
          <AppButton variant="primary" @click="$router.push('/admin/internship/batches')">前往批次管理</AppButton>
          <AppButton variant="ghost" @click="load">重新检查</AppButton>
        </template>
      </EmptyState>
    </div>
    <div v-else class="mp-stack">
      <section id="idb-todos" class="mp-card idb-today">
        <div class="mp-card__head idb-today__head">
          <div>
            <span class="idb-eyebrow">TODAY FIRST</span>
            <span class="mp-card__title">待我处理 · {{ hero.workItemTotal || workItems.length }} 项</span>
            <p>先展示最紧急的 {{ hero.workItemLimit || 8 }} 个真实对象；处理动作仍在原业务详情页完成。</p>
          </div>
          <button type="button" class="mp-link" @click="goWithBatch('/admin/internship/risk-disposal')">查看全部工作队列 →</button>
        </div>
        <div class="mp-card__body idb-work-list">
          <EmptyState v-if="!workItems.length" title="今天没有待处理对象" description="当前权限与数据范围内没有开放风险、待核实异常或待批阅周报。" />
          <article v-for="item in workItems" :key="item.id" class="idb-work" :class="`is-${item.tone || 'warning'}`">
            <header class="idb-work__header">
              <div>
                <span class="idb-work__kind">{{ workKindLabel(item.kind) }}</span>
                <h3>{{ item.title }}</h3>
                <p>{{ item.summary }}</p>
              </div>
              <AppStatusTag :type="item.tone === 'danger' ? 'danger' : 'warning'" dot>{{ item.waitingOn }}</AppStatusTag>
            </header>
            <dl class="idb-work__facts">
              <div><dt>为什么到我这里</dt><dd>{{ item.whyHere }}</dd></div>
              <div><dt>最近发生了什么</dt><dd>{{ item.recentChange }}</dd></div>
              <div><dt>办完交给谁</dt><dd>{{ item.nextActor }}</dd></div>
            </dl>
            <footer class="idb-work__footer">
              <span><b>办理回执：</b>{{ item.receipt }}</span>
              <AppButton variant="primary" size="sm" @click="openWorkItem(item)">{{ item.primaryActionLabel || '继续办理' }} →</AppButton>
            </footer>
          </article>
        </div>
      </section>

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
          <button type="button" class="mp-link" @click="$router.push('/admin/internship/batches')">批次管理 →</button>
        </div>
        <div class="mp-card__body">
          <div class="idb-progress-wrap">
            <div class="idb-progress">
              <div class="idb-progress__bar" role="progressbar" aria-label="当前在岗率" aria-valuemin="0" aria-valuemax="100" :aria-valuenow="batchProgress">
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
            <AppMetricCard v-for="f in hero.flow" :key="f.label" :title="f.label" :value="f.value" :accent="f.active ? 'primary' : ''" />
          </div>
        </div>
      </section>

      <div class="mp-grid-2 idb-afterwork">
        <section class="mp-card">
          <div class="mp-card__head">
            <span class="mp-card__title">开放风险摘要</span>
            <button type="button" class="mp-link" @click="goWithBatch('/admin/internship/risk-disposal')">风险处置 →</button>
          </div>
          <div class="mp-card__body">
            <EmptyState v-if="!hero.riskAlerts.length" title="暂无开放风险" description="系统预警与人工创建的风险单将在此展示" />
            <ul v-else class="mp-timeline idb-risk-list">
              <li v-for="r in hero.riskAlerts" :key="r.id" class="mp-timeline__item" :class="r.level === 'HIGH' ? 'is-danger' : 'is-warning'">
                <div class="mp-timeline__title">
                  {{ r.studentName }} · {{ r.title }}
                  <AppRiskTag :level="r.level" />
                </div>
                <button type="button" class="mp-link" @click="$router.push(r.route || goRiskRoute(r))">去处置</button>
              </li>
            </ul>
          </div>
        </section>
        <section class="mp-card idb-queue-note">
          <div class="mp-card__head"><span class="mp-card__title">连续办理规则</span></div>
          <div class="mp-card__body">
            <p><strong>一个对象，一次判断。</strong>进入周报或考勤详情后，队列会保留同类对象顺序。</p>
            <p>处理成功自动给出下一条；版本冲突会停在当前对象，保留输入并要求刷新事实。</p>
            <p>风险、周报、考勤分别沿用原状态机、原权限和原审计，不在工作台复制写操作。</p>
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
import { AppStatusTag, AppRiskTag, AppMetricCard } from '@/components/common'
import { AppButton } from '@/components/ui'
import { internshipApi } from '@/modules/internship/api/internship.api'
import { useInternshipBatchStore } from '@/stores/internshipBatch'
import { saveReviewQueue } from '@/modules/internship/composables/reviewQueue'

const PANEL_ANCHORS = {
  'batch-progress': 'idb-batch-progress',
  todos: 'idb-todos',
  trends: 'idb-trends'
}

export default {
  name: 'InternshipDashboardView',
  components: { ModulePageShell, ModuleHero, ModuleToolbar, AppStatusTag, AppRiskTag, AppMetricCard, AppButton, LoadingState, ErrorState, EmptyState },
  props: { ctx: { type: Object, required: true } },
  data() {
    return { loading: true, error: '', needsBatch: false, hero: { stats: [], flow: [], todos: [], workItems: [], workItemTotal: 0, workItemLimit: 8, riskAlerts: [], batchName: '', batchRange: '', batchStatus: '', batchProgress: 0 } }
  },
  computed: {
    batchStore() { return useInternshipBatchStore() },
    workflowStages() {
      const bid = this.batchStore.selectedBatchId
      const q = bid ? `?batchId=${bid}` : ''
      return [
        { label: '批次建档', hint: '范围与名单', to: '/admin/internship/batches' },
        { label: '岗位匹配', hint: '意向与落岗', to: `/admin/internship/match-assign${q}` },
        { label: '协议到岗', hint: '协议与签到', to: `/admin/internship/agreements${q}` },
        { label: '过程指导', hint: '周报与走访', to: `/admin/internship/reports${q}` },
        { label: '风险处置', hint: '预警与闭环', to: `/admin/internship/risk-disposal${q}` },
        { label: '评价归档', hint: '成绩与留档', to: `/admin/internship/scores${q}` }
      ]
    },
    batchProgress() {
      return this.hero.batchProgress ?? 0
    },
    workItems() {
      return Array.isArray(this.hero.workItems) ? this.hero.workItems : []
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
    },
    'batchStore.selectedBatchId'() {
      this.load()
    }
  },
  created() {
    this.load()
  },
  methods: {
    workKindLabel(kind) {
      return ({ RISK: '开放风险', ATTENDANCE_EXCEPTION: '考勤异常', WEEKLY_REPORT: '过程报告' })[kind] || '待办对象'
    },
    openWorkItem(item) {
      const queueKind = ({ WEEKLY_REPORT: 'weekly-report', ATTENDANCE_EXCEPTION: 'attendance-exception' })[item.kind]
      if (queueKind) {
        const peers = this.workItems.filter((row) => row.kind === item.kind).map((row) => row.objectId)
        saveReviewQueue({
          kind: queueKind,
          title: item.kind === 'WEEKLY_REPORT' ? '今日待批阅周报' : '今日待核实异常',
          listPath: '/admin/internship',
          listQuery: this.batchStore.withBatchQuery({ panel: 'todos' }),
          ids: peers
        })
      }
      this.$router.push(item.route)
    },
    goWithBatch(path) {
      const q = this.batchStore.withBatchQuery({})
      this.$router.push({ path, query: q })
    },
    goRiskRoute(r) {
      return `/admin/internship/risk-disposal?id=${r.id}&batchId=${this.batchStore.selectedBatchId || ''}`
    },
    scrollToPanel(panel) {
      const id = PANEL_ANCHORS[(panel || '').toString()]
      if (!id) return
      const el = document.getElementById(id)
      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
    },
    async load() {
      if (!this.batchStore.selectedBatchId) {
        this.loading = false
        this.error = ''
        this.needsBatch = true
        this.hero = { stats: [], flow: [], todos: [], workItems: [], workItemTotal: 0, workItemLimit: 8, riskAlerts: [], batchName: '', batchRange: '', batchStatus: '', batchProgress: 0 }
        return
      }
      this.loading = true
      this.error = ''
      this.needsBatch = false
      const res = await internshipApi.getDashboardSummary({ batchId: this.batchStore.selectedBatchId })
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
      if (path) this.goWithBatch(path)
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.idb-setup { padding: clamp(24px, 5vw, 64px); }
.idb-today { overflow: hidden; border-color: color-mix(in srgb, var(--pri, #2563eb) 24%, var(--card-b, #e5e7eb)); box-shadow: 0 14px 40px rgba(30, 64, 175, .08); }
.idb-today__head { align-items: flex-end; padding: 18px 20px; background: linear-gradient(120deg, color-mix(in srgb, var(--pri, #2563eb) 8%, white), white 68%); }
.idb-today__head > div { display: grid; gap: 3px; }
.idb-today__head .mp-card__title { font-size: 18px; }
.idb-today__head p { margin: 0; color: var(--text-secondary); font-size: 12px; }
.idb-work-list { display: grid; gap: 12px; }
.idb-work { overflow: hidden; border: 1px solid var(--card-b, #e5e7eb); border-left: 4px solid var(--warning-500, #f59e0b); border-radius: 12px; background: var(--card, #fff); }
.idb-work.is-danger { border-left-color: var(--danger-500, #ef4444); }
.idb-work__header { display: flex; align-items: flex-start; justify-content: space-between; gap: 18px; padding: 14px 16px 10px; }
.idb-work__header h3 { margin: 3px 0; color: var(--text-primary); font-size: 15px; }
.idb-work__header p { margin: 0; color: var(--text-secondary); font-size: 12px; }
.idb-work__kind { color: var(--pri, #2563eb); font-size: 10px; font-weight: 800; letter-spacing: .08em; }
.idb-work__facts { display: grid; grid-template-columns: 1.2fr 1fr 1fr; margin: 0; padding: 0 16px 12px; gap: 12px; }
.idb-work__facts div { min-width: 0; padding: 10px 12px; border-radius: 9px; background: var(--fill-2, #f8fafc); }
.idb-work__facts dt { margin-bottom: 4px; color: var(--text-tertiary); font-size: 10px; font-weight: 700; }
.idb-work__facts dd { margin: 0; color: var(--text-secondary); font-size: 12px; line-height: 1.5; }
.idb-work__footer { display: flex; align-items: center; justify-content: space-between; gap: 18px; padding: 10px 16px; border-top: 1px solid var(--card-b, #eef0f3); background: color-mix(in srgb, var(--fill-2, #f8fafc) 72%, white); }
.idb-work__footer > span { color: var(--text-tertiary); font-size: 11px; line-height: 1.5; }
.idb-work__footer b { color: var(--text-secondary); }
.idb-queue-note p { margin: 0 0 10px; color: var(--text-secondary); font-size: 13px; line-height: 1.65; }
.idb-queue-note p:last-child { margin-bottom: 0; }
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
.idb-flow { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 10px; }
.idb-todo { padding: 8px 0; border-bottom: 1px solid var(--card-b, #eef0f3); }
.idb-todo:last-child { border-bottom: 0; }
.idb-todo.is-danger { margin: 0 -8px; padding: 8px; border-radius: 8px; border-bottom-color: transparent; background: rgba(254, 242, 242, .7); }
.idb-risk-list :deep(.mp-timeline__item) { border-radius: 10px; transition: background .18s ease; }
.idb-risk-list :deep(.mp-timeline__item:hover) { background: var(--fill-2, #f8fafc); }
@media (max-width: 1280px) { .idb-path { align-items: flex-start; flex-direction: column; gap: 10px; } .idb-path__intro { flex-basis: auto; } .idb-path__steps { width: 100%; } }
@media (max-width: 940px) { .idb-path__steps { grid-template-columns: repeat(3, 1fr); } }
@media (max-width: 940px) { .idb-work__facts { grid-template-columns: 1fr; } }
@media (max-width: 640px) { .idb-path__steps { grid-template-columns: repeat(2, 1fr); } .idb-progress-wrap { grid-template-columns: 1fr; } .idb-progress__rate { align-items: flex-start; padding: 10px 0 0; border-top: 1px solid var(--card-b, #e5e7eb); border-left: 0; } .idb-work__header, .idb-work__footer { align-items: stretch; flex-direction: column; } }
</style>
