<template>
  <ModulePageShell
    title="今日工作"
    subtitle="集中处理当前批次的待办，跟进异常与关键进度"
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
          <AppButton v-if="canOpen('internship.batch.view')" variant="primary" @click="$router.push('/admin/internship/batches')">前往批次管理</AppButton>
          <AppButton variant="ghost" @click="load">重新检查</AppButton>
        </template>
      </EmptyState>
    </div>
    <div v-else class="mp-stack">
      <section class="idb-journey" aria-label="按实习流程办理">
        <div class="idb-journey__intro"><strong>按实习流程办理</strong><span>准备 → 岗位 → 落岗 → 过程 → 评价 → 归档 · 风险贯穿全程</span></div>
        <div class="idb-journey__steps">
          <RouterLink v-for="(stage, index) in workflowStages" :key="stage.key" :to="withInternshipBatch(stage.path, batchStore.selectedBatchId)" :title="stage.hint" class="idb-journey__step">
            <span class="idb-journey__number">{{ String(index + 1).padStart(2, '0') }}</span><strong>{{ stage.label }}</strong><small>{{ stage.hint }}</small>
          </RouterLink>
        </div>
      </section>
      <section id="idb-todos" class="mp-card idb-today">
        <div class="mp-card__head idb-today__head">
          <div>
            <span class="mp-card__title">优先待办 · {{ workItemTotal }} 项</span>
            <p>汇集风险、考勤异常与周报，最多显示 {{ hero.workItemLimit || 8 }} 项；其他事项从上方流程入口办理。</p>
          </div>
          <button type="button" class="mp-link" :disabled="loading" @click="load">刷新待办</button>
        </div>
        <nav class="idb-queues" aria-label="待办类型">
          <button v-for="kind in workKinds" :key="kind.value" type="button" :aria-pressed="workFilter === kind.value" @click="workFilter = kind.value">{{ kind.label }} <span>{{ kind.count }}</span></button>
          <RouterLink v-if="activeQueue" :to="withInternshipBatch(activeQueue.path, batchStore.selectedBatchId)">查看{{ activeQueue.label }}全部记录 →</RouterLink>
        </nav>
        <div class="mp-card__body idb-work-list">
          <div v-if="!workItems.length" class="idb-empty" role="status"><h3>{{ workFilter ? '优先事项中没有此类待办' : '暂无风险、考勤异常或周报待办' }}</h3><p>可切换待办类型；名单资格、协议与上岗核验等事项，请从上方对应流程进入。</p></div>
          <article v-for="item in workItems" :key="item.id" class="idb-work" :class="`is-${item.tone || 'warning'}`">
            <header class="idb-work__header">
              <div>
                <span class="idb-work__kind">{{ workKindLabel(item.kind) }}</span>
                <h3>{{ item.title }}</h3>
                <p>{{ item.summary }}</p>
              </div>
              <AppStatusTag :type="item.tone === 'danger' ? 'danger' : 'warning'" dot>{{ item.waitingOn }}</AppStatusTag>
            </header>
            <details class="idb-work__details"><summary>查看办理依据与交接</summary><dl class="idb-work__facts">
              <div><dt>为什么到我这里</dt><dd>{{ item.whyHere }}</dd></div>
              <div><dt>最近发生了什么</dt><dd>{{ item.recentChange }}</dd></div>
              <div><dt>办完交给谁</dt><dd>{{ item.nextActor }}</dd></div>
            </dl></details>
            <footer class="idb-work__footer">
              <span><b>办理回执：</b>{{ item.receipt }}</span>
              <AppButton variant="primary" size="sm" @click="openWorkItem(item)">{{ item.primaryActionLabel || '继续办理' }} →</AppButton>
            </footer>
          </article>
        </div>
      </section>

      <div class="mp-grid-2 idb-afterwork">
        <section class="mp-card">
          <div class="mp-card__head">
            <span class="mp-card__title">开放风险摘要</span>
            <button v-if="canOpen('internship.risk.handle')" type="button" class="mp-link" @click="goWithBatch('/admin/internship/risk-disposal')">风险处置 →</button>
          </div>
          <div class="mp-card__body">
            <div v-if="!hero.riskAlerts.length" class="idb-empty" role="status"><h3>暂无开放风险</h3><p>系统预警与人工创建的风险单将在此展示。</p></div>
            <ul v-else class="mp-timeline idb-risk-list">
              <li v-for="r in hero.riskAlerts" :key="r.id" class="mp-timeline__item" :class="r.level === 'HIGH' ? 'is-danger' : 'is-warning'">
                <div class="mp-timeline__title">
                  {{ r.studentName }} · {{ r.title }}
                  <AppRiskTag :level="r.level" />
                </div>
                <button v-if="canOpen('internship.risk.handle')" type="button" class="mp-link" @click="goWithBatch(r.route || goRiskRoute(r))">去处置</button>
              </li>
            </ul>
          </div>
        </section>
        <section class="mp-card idb-queue-note">
          <div class="mp-card__head"><span class="mp-card__title">办理提示</span></div>
          <div class="mp-card__body">
            <p><strong>一个对象，一次判断。</strong>进入周报或考勤详情后，队列会保留同类对象顺序。</p>
            <p>处理成功自动给出下一条；版本冲突会停在当前对象，保留输入并要求刷新事实。</p>
            <p>调岗、退岗或事故发生后，从“风险与变更”跟进；符合条件后，再回到实习过程继续办理。</p>
          </div>
        </section>
      </div>

    </div>
  </ModulePageShell>
</template>

<script>
/** 岗位实习中心 · 管理看板（/admin/internship）。数据全部来自 internshipApi。 */
import { ModulePageShell, ModuleToolbar, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppStatusTag, AppRiskTag } from '@/components/common'
import { AppButton } from '@/components/ui'
import { internshipApi } from '@/modules/internship/api/internship.api'
import { useInternshipBatchStore } from '@/stores/internshipBatch'
import { saveReviewQueue } from '@/modules/internship/composables/reviewQueue'
import { internshipWorkspaces, withInternshipBatch } from '../navigation.js'
import { matchPermission } from '@/config/navPlan'

const PANEL_ANCHORS = {
  todos: 'idb-todos'
}

const emptyHero = () => ({ workItems: [], workItemTotal: 0, workItemLimit: 8, riskAlerts: [] })

export default {
  name: 'InternshipDashboardView',
  components: { ModulePageShell, ModuleToolbar, AppStatusTag, AppRiskTag, AppButton, LoadingState, ErrorState, EmptyState },
  props: { ctx: { type: Object, required: true } },
  data() {
    return { loading: true, error: '', needsBatch: false, workFilter: '', loadTicket: 0, hero: emptyHero() }
  },
  computed: {
    batchStore() { return useInternshipBatchStore() },
    workflowStages() {
      return internshipWorkspaces(this.ctx).filter((item) => !['in-command-screen', 'in-workbench'].includes(item.key))
    },
    allWorkItems() {
      return Array.isArray(this.hero.workItems) ? this.hero.workItems : []
    },
    workItemTotal() {
      return Number.isFinite(Number(this.hero.workItemTotal)) ? Number(this.hero.workItemTotal) : this.allWorkItems.length
    },
    workItems() { return this.allWorkItems.filter((item) => !this.workFilter || item.kind === this.workFilter) },
    workKinds() {
      return [{ value: '', label: '全部' }, { value: 'RISK', label: '风险处置' }, { value: 'ATTENDANCE_EXCEPTION', label: '考勤异常' }, { value: 'WEEKLY_REPORT', label: '报告批阅' }].map((item) => ({ ...item, count: this.allWorkItems.filter((row) => !item.value || row.kind === item.value).length }))
    },
    activeQueue() {
      const map = {
        RISK: { label: '风险', path: '/admin/internship/risk-disposal?stage=pending', permission: 'internship.risk.handle' },
        ATTENDANCE_EXCEPTION: { label: '考勤异常', path: '/admin/internship/exceptions?status=PENDING_HANDLE', permission: 'internship.attendance.view' },
        WEEKLY_REPORT: { label: '报告', path: '/admin/internship/reports?panel=review', permission: 'internship.report.view' }
      }
      const queue = map[this.workFilter]
      return queue && this.canOpen(queue.permission) ? queue : null
    },
    toolbarActions() {
      const pa = this.ctx.permissionActions || {}
      const def = [
        { key: 'createBatch', label: '＋ 新增实习批次', variant: 'primary' },
        { key: 'importStudents', label: '管理学生名单' },
        { key: 'exportGroup', label: '统计报表' },
        { key: 'viewAuditLog', label: '分配记录', variant: 'ghost' }
      ]
      return def
        .filter((a) => pa[a.key] && pa[a.key].visible)
        .map((a) => ({ ...a, disabled: !pa[a.key].allowed, disabledReason: pa[a.key].reason }))
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
      this.workFilter = ''
      this.load()
    },
    'ctx.ctxKey'() { this.workFilter = ''; this.load() }
  },
  created() {
    this.load()
  },
  beforeUnmount() { this.loadTicket++ },
  methods: {
    withInternshipBatch,
    canOpen(code) { return matchPermission(this.ctx.permissionPatterns, code) },
    workKindLabel(kind) {
      return ({ RISK: '开放风险', ATTENDANCE_EXCEPTION: '考勤异常', WEEKLY_REPORT: '过程报告' })[kind] || '待办对象'
    },
    openWorkItem(item) {
      if (this.loading || this.error || this.needsBatch || !this.allWorkItems.includes(item)) return
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
      this.goWithBatch(item.route)
    },
    goWithBatch(path) {
      if (path) this.$router.push(withInternshipBatch(path, this.batchStore.selectedBatchId))
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
      const ticket = ++this.loadTicket, batchId = this.batchStore.selectedBatchId, ctxKey = this.ctx.ctxKey
      this.hero = emptyHero()
      if (!this.batchStore.selectedBatchId) {
        this.loading = false
        this.error = ''
        this.needsBatch = true
        return
      }
      this.loading = true
      this.error = ''
      this.needsBatch = false
      let res
      try { res = await internshipApi.getDashboardSummary({ batchId: this.batchStore.selectedBatchId }) }
      catch (error) { res = { code: -1, message: error.message || '工作台读取失败，请重试' } }
      if (ticket !== this.loadTicket || batchId !== this.batchStore.selectedBatchId || ctxKey !== this.ctx.ctxKey) return
      if (res.code === 0 && res.data) this.hero = { ...emptyHero(), ...res.data }
      else this.error = res.message || '工作台读取失败，请重试'
      this.loading = false
      this.$nextTick(() => this.scrollToPanel(this.$route.query.panel))
    },
    onToolbar(key) {
      if (!this.ctx.permissionActions?.[key]?.allowed) return
      const routes = {
        createBatch: '/admin/internship/batches/new',
        importStudents: '/admin/internship/students',
        exportGroup: '/admin/internship/stats',
        viewAuditLog: '/admin/internship/assignment-logs'
      }
      const path = routes[key]
      if (path) this.goWithBatch(path)
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.idb-journey{border:1px solid var(--card-b);border-radius:8px;background:var(--card);overflow:hidden}
.idb-journey__intro{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:10px 18px;border-bottom:1px solid var(--card-b);font-size:13px;color:var(--t1)}
.idb-journey__intro>span{font-size:11px;color:var(--t3)}
.idb-journey__steps{display:grid;grid-template-columns:repeat(auto-fit,minmax(135px,1fr))}
.idb-journey__step{display:flex;flex-direction:column;gap:7px;padding:16px;border-right:1px solid var(--card-b);color:var(--t1);text-decoration:none;font-size:13px}
.idb-journey__step:last-child{border-right:0}.idb-journey__step:hover{background:var(--pri-bg)}
.idb-journey__number{font-size:11px;color:var(--pri);font-variant-numeric:tabular-nums}.idb-journey__step small{font-size:11px;line-height:1.6;color:var(--t3)}
@media(max-height:850px){.idb-journey__step{flex-direction:row;align-items:center;gap:8px;padding:12px}.idb-journey__step small{display:none}}
.idb-queues{display:flex;align-items:center;gap:5px;flex-wrap:wrap;padding:10px 16px;border-bottom:1px solid var(--card-b)}
.idb-queues button{padding:6px 10px;border:1px solid transparent;background:transparent;color:var(--t2);border-radius:5px;font:inherit;font-size:12px;cursor:pointer}.idb-queues button[aria-pressed=true]{color:var(--pri);background:var(--pri-bg);border-color:var(--pri-100)}
.idb-queues button span{margin-left:5px;font-variant-numeric:tabular-nums}.idb-queues a{margin-left:auto;font-size:12px;color:var(--pri);text-decoration:none}
.idb-work__details summary{padding:0 16px 10px;cursor:pointer;color:var(--t3);font-size:12px}.idb-work__details[open] summary{color:var(--pri)}
.idb-journey a:focus-visible,.idb-queues button:focus-visible,.idb-queues a:focus-visible{outline:2px solid var(--pri);outline-offset:-2px}
.idb-setup { padding: clamp(24px, 5vw, 64px); }
.idb-today { overflow: hidden; border-color: color-mix(in srgb, var(--pri, #2563eb) 24%, var(--card-b, #e5e7eb)); box-shadow: 0 14px 40px rgba(30, 64, 175, .08); }
.idb-today__head { align-items: flex-end; padding: 18px 20px; background: linear-gradient(120deg, color-mix(in srgb, var(--pri, #2563eb) 8%, white), white 68%); }
.idb-today__head > div { display: grid; gap: 3px; }
.idb-today__head .mp-card__title { font-size: 18px; }
.idb-today__head p { margin: 0; color: var(--text-secondary); font-size: 12px; }
.idb-work-list { display: grid; gap: 12px; }
.idb-empty { padding: 28px 20px; text-align: center; color: var(--text-secondary); }
.idb-empty h3 { margin: 0 0 8px; font-size: 14px; font-weight: 500; color: var(--text-primary); }
.idb-empty p { margin: 0; font-size: 13px; line-height: 1.8; }
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
.idb-risk-list :deep(.mp-timeline__item) { border-radius: 10px; transition: background .18s ease; }
.idb-risk-list :deep(.mp-timeline__item:hover) { background: var(--fill-2, #f8fafc); }
@media (max-width: 940px) { .idb-work__facts { grid-template-columns: 1fr; } }
@media (max-width: 640px) { .idb-work__header, .idb-work__footer { align-items: stretch; flex-direction: column; } }
</style>
