<template>
  <AppPageShell
    class="sa-v6-page-shell"
    title="今日工作"
    subtitle="聚合当前身份可见的待办、请假返校、风险、困难资助与处分事项，直接进入现有真实业务工作页。"
    :role-name="dashboard.viewLabel"
    :data-scope-name="scopeLabel"
    watermark-purpose="学工今日工作查看"
  >
    <template #actions>
      <span class="sa-updated-hint">
        数据更新于 <AppDateDisplay :value="dashboard.updatedAt" mode="datetime" empty-text="—" />
      </span>
      <AppPermissionButton
        :allowed="canBtn('studentAffairs.dashboard.view')"
        code="studentAffairs.dashboard.view"
        variant="secondary"
        @click="load"
      >
        刷新
      </AppPermissionButton>
      <AppExportButton :export-fn="exportLedger" :has-permission="true" />
    </template>

    <AppGlobalState
      :state="pageState"
      :title="stateTitle"
      :description="stateDescription"
      loading-text="正在加载学工今日工作真实数据…"
      @retry="load"
      @back="$router.push('/workbench')"
    >
      <div class="sa-v6-dashboard">
        <section class="sa-v6-hero" aria-labelledby="sa-v6-hero-title">
          <div class="sa-v6-hero__copy">
            <span class="sa-v6-hero__eyebrow">TODAY · 当前运行结论</span>
            <h2 id="sa-v6-hero-title">{{ heroConclusion }}</h2>
            <p>{{ heroGuidance }}</p>
          </div>
          <dl class="sa-v6-hero__metrics" aria-label="今日工作关键指标">
            <div v-for="item in heroMetrics" :key="item.key" class="sa-v6-hero__metric">
              <dt>{{ item.label }}</dt>
              <dd>{{ formatCount(item.value) }}</dd>
            </div>
          </dl>
        </section>

        <ol class="sa-v6-flow" aria-label="今日工作闭环">
          <li v-for="(step, index) in workflowSteps" :key="step" :class="{ 'is-active': index === 0 }">
            <span class="sa-v6-flow__index">{{ index + 1 }}</span>
            <span>{{ step }}</span>
          </li>
        </ol>

        <div class="sa-v6-workspace">
          <AppSectionCard
            class="sa-v6-panel sa-v6-queue-card"
            title="现在先处理"
            subtitle="按风险、逾期与当前节点排序；每条进入已有业务工作页"
            compact
            no-padding
          >
            <template #header-extra>
              <span class="sa-v6-scope-note">{{ scopeLabel }}</span>
            </template>

            <div class="sa-v6-queue" aria-label="当前业务队列">
              <button
                v-for="item in businessQueues"
                :key="item.key"
                type="button"
                class="sa-v6-queue-row"
                :class="[`is-${item.tone}`, { 'is-zero': item.count === 0 }]"
                :disabled="!item.path"
                :title="item.path ? `进入${item.label}` : '当前身份无权进入或未配置可用入口'"
                @click="go(item.path)"
              >
                <span class="sa-v6-queue-row__icon" aria-hidden="true">{{ item.icon }}</span>
                <span class="sa-v6-queue-row__copy">
                  <span class="sa-v6-queue-row__title">
                    <strong>{{ item.label }}</strong>
                    <AppStatusTag :type="item.statusType" :label="item.statusLabel" />
                  </span>
                  <span class="sa-v6-queue-row__description">{{ item.description }}</span>
                  <span class="sa-v6-queue-row__meta">按当前数据范围 · 原业务流程</span>
                </span>
                <span class="sa-v6-queue-row__count">
                  <strong>{{ formatCount(item.count) }}</strong>
                  <small>{{ item.unit }}</small>
                </span>
                <span class="sa-v6-queue-row__action">
                  {{ item.path ? item.action : '无可用入口' }}
                  <span v-if="item.path" aria-hidden="true">→</span>
                </span>
              </button>
            </div>
          </AppSectionCard>

          <aside class="sa-v6-side" aria-label="今日工作辅助信息">
            <AppSectionCard
              class="sa-v6-panel sa-v6-scope-card"
              title="当前工作范围"
              subtitle="身份、数据范围和业务动作仍按系统规则校验"
              compact
            >
              <div class="sa-v6-scope-grid">
                <div>
                  <span>当前身份</span>
                  <strong>{{ dashboard.viewLabel || '按当前身份' }}</strong>
                </div>
                <div>
                  <span>范围口径</span>
                  <strong>{{ scopeLabel }}</strong>
                </div>
                <div>
                  <span>范围学生</span>
                  <strong>{{ formatCount(cardValue('studentTotal')) }}</strong>
                </div>
                <div>
                  <span>范围班级</span>
                  <strong>{{ formatCount(cardValue('classTotal')) }}</strong>
                </div>
              </div>
              <p class="sa-v6-card-note">权限、数据范围和业务动作会在目标工作页再次校验。</p>
            </AppSectionCard>

            <AppSectionCard
              class="sa-v6-panel sa-v6-risk-card"
              title="风险摘要"
              subtitle="只展示当前范围的真实聚合"
              compact
            >
              <template #header-extra>
                <AppRiskTag v-if="cardValue('riskStudents')" :level="riskLevel" />
                <AppStatusTag v-else type="success" label="暂无风险" />
              </template>
              <div class="sa-v6-risk-numbers">
                <div>
                  <span>危急风险</span>
                  <strong>{{ formatCount(criticalRiskCount) }}</strong>
                </div>
                <div>
                  <span>高风险</span>
                  <strong>{{ formatCount(highRiskCount) }}</strong>
                </div>
                <div>
                  <span>未关闭风险</span>
                  <strong>{{ formatCount(cardValue('riskStudents')) }}</strong>
                </div>
              </div>
              <p class="sa-v6-card-note">各等级按服务端口径分别展示，不在浏览器合并去重。</p>
              <AppPermissionButton
                :allowed="canBtn('studentAffairs.risk.view')"
                code="studentAffairs.risk.view"
                variant="secondary"
                @click="go(cardPath('riskStudents'))"
              >
                进入风险工作台
              </AppPermissionButton>
            </AppSectionCard>

            <AppSectionCard
              class="sa-v6-panel sa-v6-entry-card"
              title="高频入口"
              subtitle="找学生与进入专项工作区"
              compact
            >
              <div v-if="highFrequencyEntries.length" class="sa-v6-entry-grid">
                <button
                  v-for="entry in highFrequencyEntries"
                  :key="entry.path"
                  type="button"
                  class="sa-v6-entry"
                  @click="go(entry.path)"
                >
                  <span class="sa-v6-entry__icon" aria-hidden="true">{{ entry.icon }}</span>
                  <span>
                    <strong>{{ entry.label }}</strong>
                    <small>{{ entry.hint }}</small>
                  </span>
                </button>
              </div>
              <p v-else class="sa-v6-card-note">当前身份暂无可用的高频入口。</p>
            </AppSectionCard>
          </aside>
        </div>

        <div class="sa-v6-support-grid">
          <AppSectionCard
            class="sa-v6-panel sa-dashboard-panel--audit"
            title="最近处理与审计"
            subtitle="当前权限范围内的真实操作留痕"
            compact
          >
            <div v-if="auditUnavailable" class="sa-v6-inline-warning" role="status">
              审计列表暂不可用；今日工作真实聚合仍可使用，稍后刷新重试。
            </div>
            <AppAuditTrail :records="auditLogs" compact empty-text="暂无可展示审计记录" />
          </AppSectionCard>

          <AppSectionCard
            class="sa-v6-panel sa-v6-bridge-card"
            title="跨中心协同"
            subtitle="风险仍回到各中心正式工作页处理"
            compact
          >
            <div class="sa-v6-bridge-actions">
              <AppPermissionButton
                :allowed="canBtn('studentAffairs.orientation.view')"
                code="studentAffairs.orientation.view"
                variant="secondary"
                @click="go('/admin/orientation')"
              >
                数字迎新
              </AppPermissionButton>
              <AppPermissionButton
                :allowed="canBtn('internship.risk.view')"
                code="internship.risk.view"
                variant="secondary"
                @click="go('/admin/internship/risks')"
              >
                岗位实习风险
              </AppPermissionButton>
              <AppPermissionButton
                :allowed="canBtn('graduation.risk.view')"
                code="graduation.risk.view"
                variant="secondary"
                @click="go('/admin/graduation/risk-archive?panel=risk')"
              >
                毕业设计风险
              </AppPermissionButton>
            </div>
          </AppSectionCard>
        </div>
      </div>
    </AppGlobalState>
  </AppPageShell>
</template>

<script>
import {
  AppAuditTrail,
  AppDateDisplay,
  AppExportButton,
  AppGlobalState,
  AppPageShell,
  AppPermissionButton,
  AppRiskTag,
  AppSectionCard,
  AppStatusTag
} from '@/components/common'
import studentAffairsApi from '@/modules/studentAffairs/api/studentAffairsB.api'
import { canCode } from '@/modules/studentAffairs/composables/permission'

/** 指标 key → 页面权限；无权限时不生成可点击下钻。 */
const CARD_PERM = {
  studentTotal: 'studentAffairs.student.view',
  classTotal: 'studentAffairs.class.view',
  pendingTodo: 'approval.todo.view',
  pendingLeave: 'studentAffairs.leave.view',
  overdueLeave: 'studentAffairs.leave.view',
  pendingAid: 'studentAffairs.aid.view',
  pendingFunding: 'studentAffairs.funding.view',
  pendingDiscipline: 'studentAffairs.discipline.view',
  riskStudents: 'studentAffairs.risk.view'
}

const FALLBACK_DRILL = {
  studentTotal: '/admin/student/list',
  classTotal: '/admin/campus-service/classes',
  pendingTodo: '/admin/approval/todos',
  pendingLeave: '/admin/student-affairs/leave',
  overdueLeave: '/admin/student-affairs/leave/ledger?status=OVERDUE',
  pendingAid: '/admin/student-affairs/aid?status=REVIEW',
  pendingFunding: '/admin/student-affairs/funding?status=REVIEW',
  pendingDiscipline: '/admin/student-affairs/discipline?status=REVIEW',
  riskStudents: '/admin/student-affairs/risk?status=OPEN'
}

const WORKFLOW_STEPS = ['发现事项', '确认优先级', '进入业务办理', '返回今日队列', '审计沉淀']
const NUMBER_FORMATTER = new Intl.NumberFormat('zh-CN')

export default {
  name: 'StudentAffairsDashboardView',
  props: { ctx: { type: Object, default: null } },
  components: {
    AppAuditTrail,
    AppDateDisplay,
    AppExportButton,
    AppGlobalState,
    AppPageShell,
    AppPermissionButton,
    AppRiskTag,
    AppSectionCard,
    AppStatusTag
  },
  data() {
    return {
      loading: true,
      errorMessage: '',
      dashboard: {
        summaryCards: [],
        moduleCards: [],
        riskSummary: {},
        view: '',
        viewLabel: '',
        scopeMode: '',
        scopeType: '',
        scopeLabel: ''
      },
      auditLogs: [],
      auditUnavailable: false,
      workflowSteps: WORKFLOW_STEPS
    }
  },
  computed: {
    hasNoScope() {
      return this.dashboard.scopeMode === 'NONE' ||
        this.dashboard.scopeType === 'NONE' ||
        this.dashboard.scopeLabel === '无数据范围'
    },
    pageState() {
      if (this.loading) return 'loading'
      if (this.errorMessage) return 'error'
      if (this.hasNoScope) return 'empty'
      return this.metricCards.length ? 'ready' : 'empty'
    },
    stateTitle() {
      if (this.hasNoScope) return '当前账号未配置学工数据范围'
      if (!this.loading && !this.errorMessage && !this.metricCards.length) {
        return '当前范围暂无可展示的学工数据'
      }
      return ''
    },
    stateDescription() {
      if (this.errorMessage) return this.errorMessage
      if (this.hasNoScope) {
        return '系统已按最小权限关闭业务数据展示，请联系学校管理员配置负责学院、班级或学生范围。'
      }
      if (!this.loading && !this.metricCards.length) {
        return '当前接口没有返回可用指标，请刷新后重试；系统不会用示例数字替代真实结果。'
      }
      return ''
    },
    metricCards() {
      return (this.dashboard.summaryCards || []).map((card) => {
        const permission = CARD_PERM[card.key]
        const allowed = !permission || this.canBtn(permission)
        return {
          ...card,
          drillPath: allowed ? (card.drillPath || FALLBACK_DRILL[card.key] || '') : ''
        }
      })
    },
    cardMap() {
      return this.metricCards.reduce((map, card) => {
        map[card.key] = card
        return map
      }, {})
    },
    scopeLabel() {
      if (this.dashboard.scopeLabel) return this.dashboard.scopeLabel
      const map = {
        ADMIN_TENANT: '全校',
        SCOPED: '本人负责范围',
        NONE: '无数据范围',
        SELF: '本人负责范围'
      }
      return map[this.dashboard.scopeMode] || '按当前身份'
    },
    heroMetrics() {
      return [
        { key: 'pendingTodo', label: '统一待办', value: this.cardValue('pendingTodo') },
        { key: 'pendingLeave', label: '待审请假', value: this.cardValue('pendingLeave') },
        { key: 'overdueLeave', label: '逾期未销假', value: this.cardValue('overdueLeave') },
        { key: 'riskStudents', label: '未关闭风险', value: this.cardValue('riskStudents') }
      ]
    },
    highRiskCount() {
      return this.toCount(this.dashboard.riskSummary?.highCount)
    },
    criticalRiskCount() {
      return this.toCount(this.dashboard.riskSummary?.criticalCount)
    },
    heroConclusion() {
      const overdue = this.cardValue('overdueLeave')
      const pendingTodo = this.cardValue('pendingTodo')
      const clauses = []
      if (overdue) clauses.push(`先核查 ${this.formatCount(overdue)} 条逾期未销假`)
      if (this.criticalRiskCount) {
        clauses.push(`优先关注 ${this.formatCount(this.criticalRiskCount)} 名危急风险学生`)
      }
      if (this.highRiskCount) {
        clauses.push(`关注 ${this.formatCount(this.highRiskCount)} 名高风险学生`)
      }
      if (pendingTodo) clauses.push(`再处理 ${this.formatCount(pendingTodo)} 项统一待办`)
      if (!clauses.length && this.cardValue('riskStudents')) {
        return `当前范围有 ${this.formatCount(this.cardValue('riskStudents'))} 名未关闭风险学生，继续按队列跟进。`
      }
      if (!clauses.length) return '当前范围暂无高危风险与逾期未销假，继续检查各业务待审队列。'
      return `今天${clauses.join('，')}。`
    },
    heroGuidance() {
      const map = {
        COUNSELOR: '按风险、逾期和审批节点查看本人负责学生；每项都进入现有真实业务工作页。',
        COLLEGE_SA: '先核查本院班级与责任范围内的积压，再下钻到原业务工作页处理。',
        SA_ADMIN: '先看全校风险和业务域积压；普通个案仍由对应责任人按权限办理。'
      }
      return map[this.dashboard.view] || '当前页面只重新编排真实汇总与原业务入口，不改变原业务流程。'
    },
    businessQueues() {
      const card = (key) => this.cardMap[key] || {}
      const riskCount = this.cardValue('riskStudents')
      const overdueCount = this.cardValue('overdueLeave')
      const todoCount = this.cardValue('pendingTodo')
      const leaveCount = this.cardValue('pendingLeave')
      const aidCount = this.cardValue('pendingAid')
      const fundingCount = this.cardValue('pendingFunding')
      const disciplineCount = this.cardValue('pendingDiscipline')
      return [
        {
          key: 'riskStudents',
          label: '风险与重点学生',
          description: '当前范围未关闭风险学生，进入后按状态、责任人和最新记录继续处理。',
          icon: '险',
          count: riskCount,
          unit: card('riskStudents').unit || '人',
          path: card('riskStudents').drillPath,
          action: '进入风险',
          tone: riskCount ? 'danger' : 'success',
          statusType: riskCount ? 'danger' : 'success',
          statusLabel: this.criticalRiskCount
            ? '危急优先'
            : (this.highRiskCount ? '高风险' : (riskCount ? '当前队列' : '暂无风险'))
        },
        {
          key: 'overdueLeave',
          label: '逾期未销假',
          description: '已超过应返校时间，先核实返校事实，再由原业务页判断后续动作。',
          icon: '返',
          count: overdueCount,
          unit: card('overdueLeave').unit || '件',
          path: card('overdueLeave').drillPath,
          action: '核实返校',
          tone: overdueCount ? 'warning' : 'success',
          statusType: overdueCount ? 'warning' : 'success',
          statusLabel: overdueCount ? '已超期' : '无超期'
        },
        {
          key: 'pendingTodo',
          label: '统一待办',
          description: '当前身份可见的统一待办，进入待办中心继续按原流程处理。',
          icon: '办',
          count: todoCount,
          unit: card('pendingTodo').unit || '件',
          path: card('pendingTodo').drillPath,
          action: '查看待办',
          tone: todoCount ? 'primary' : 'success',
          statusType: todoCount ? 'info' : 'success',
          statusLabel: todoCount ? '当前节点' : '已清零'
        },
        {
          key: 'pendingLeave',
          label: '请假待审批',
          description: '按辅导员、学院或学工处当前审批节点显示，完成后读取最新业务状态。',
          icon: '假',
          count: leaveCount,
          unit: card('pendingLeave').unit || '件',
          path: card('pendingLeave').drillPath,
          action: '开始审批',
          tone: leaveCount ? 'primary' : 'success',
          statusType: leaveCount ? 'info' : 'success',
          statusLabel: leaveCount ? '待当前节点' : '已清零'
        },
        {
          key: 'pendingAid',
          label: '困难认定待处理',
          description: '进入认定工作台核验申请、资格、材料和当前审核节点。',
          icon: '困',
          count: aidCount,
          unit: card('pendingAid').unit || '件',
          path: card('pendingAid').drillPath,
          action: '进入认定',
          tone: aidCount ? 'warning' : 'success',
          statusType: aidCount ? 'warning' : 'success',
          statusLabel: aidCount ? '待处理' : '已清零'
        },
        {
          key: 'pendingFunding',
          label: '奖助申请待评审',
          description: '进入资助工作台核对资格、项目规则和当前评审节点。',
          icon: '助',
          count: fundingCount,
          unit: card('pendingFunding').unit || '件',
          path: card('pendingFunding').drillPath,
          action: '进入评审',
          tone: fundingCount ? 'warning' : 'success',
          statusType: fundingCount ? 'warning' : 'success',
          statusLabel: fundingCount ? '待评审' : '已清零'
        },
        {
          key: 'pendingDiscipline',
          label: '处分事项待处理',
          description: '进入处分工作台处理审批或解除节点，生效后再衔接教育跟进。',
          icon: '纪',
          count: disciplineCount,
          unit: card('pendingDiscipline').unit || '件',
          path: card('pendingDiscipline').drillPath,
          action: '进入处分',
          tone: disciplineCount ? 'neutral' : 'success',
          statusType: disciplineCount ? 'warning' : 'success',
          statusLabel: disciplineCount ? '待处理' : '已清零'
        }
      ]
    },
    riskLevel() {
      const card = this.cardMap.riskStudents || {}
      const summary = this.dashboard.riskSummary || {}
      const level = String(card.topRiskLevel || summary.topRiskLevel || 'NONE').toUpperCase()
      if (['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].includes(level)) return level
      return 'LOW'
    },
    highFrequencyEntries() {
      return [
        {
          label: '学生主档',
          hint: '唯一找学生入口',
          icon: '生',
          path: '/admin/student/list',
          allowed: this.canAny(['student.profile.view', 'studentAffairs.student.view'])
        },
        {
          label: '数字迎新',
          hint: '报到与异常',
          icon: '新',
          path: '/admin/orientation',
          allowed: this.canBtn('studentAffairs.orientation.view')
        },
        {
          label: '宿舍异常',
          hint: '真实宿舍队列',
          icon: '宿',
          path: '/admin/student-affairs/dorm/exception',
          allowed: this.canBtn('studentAffairs.dorm.view')
        }
      ].filter((entry) => entry.allowed)
    }
  },
  created() {
    this.load()
  },
  methods: {
    canBtn(code) {
      return canCode(this.ctx, code)
    },
    canAny(codes) {
      return codes.some((code) => this.canBtn(code))
    },
    toCount(value) {
      const count = Number(value)
      return Number.isFinite(count) && count > 0 ? count : 0
    },
    formatCount(value) {
      return NUMBER_FORMATTER.format(this.toCount(value))
    },
    cardValue(key) {
      return this.toCount(this.cardMap[key]?.value)
    },
    cardPath(key) {
      return this.cardMap[key]?.drillPath || ''
    },
    async load() {
      this.loading = true
      this.errorMessage = ''
      this.auditUnavailable = false
      try {
        const [dashboardRes, auditResult] = await Promise.all([
          studentAffairsApi.getDashboard(),
          studentAffairsApi.getAuditLogs()
            .then((res) => ({ ok: true, res }))
            .catch(() => ({ ok: false, res: { data: [] } }))
        ])
        this.dashboard = dashboardRes.data || this.dashboard
        this.auditLogs = auditResult.res?.data || []
        this.auditUnavailable = !auditResult.ok
      } catch (error) {
        this.errorMessage = error?.message || '学工今日工作加载失败'
      } finally {
        this.loading = false
      }
    },
    go(path) {
      if (!path) return
      this.$router.push(path)
    },
    exportLedger() {
      return studentAffairsApi.exportProfileLedger({ purpose: '学工今日工作范围学生台账导出' })
    }
  }
}
</script>

<style scoped>
.sa-v6-page-shell {
  gap: var(--space-2);
}
.sa-v6-page-shell :deep(.mps__head) {
  align-items: center;
  gap: var(--space-3);
}
.sa-v6-page-shell :deep(.mps__title) {
  font-size: var(--font-size-2xl);
  line-height: 1.25;
}
.sa-v6-page-shell :deep(.mps__subtitle) {
  max-width: 720px;
  margin-top: 0;
  overflow: hidden;
  font-size: var(--font-size-xs);
  line-height: 1.4;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.sa-v6-dashboard {
  display: grid;
  gap: var(--space-2);
  min-width: 0;
}
.sa-v6-hero {
  position: relative;
  isolation: isolate;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  min-height: 72px;
  overflow: hidden;
  padding: var(--space-2) var(--space-4);
  border: 1px solid color-mix(in srgb, var(--pri) 22%, var(--card-b));
  border-radius: var(--radius-xl);
  background: linear-gradient(
    112deg,
    color-mix(in srgb, var(--pri-bg) 72%, var(--bg-card)),
    var(--bg-card) 72%
  );
  box-shadow: var(--shadow-card);
}
.sa-v6-hero::before {
  position: absolute;
  inset: 0 auto 0 0;
  width: var(--space-1);
  background: var(--btn-p-bg);
  content: '';
}
.sa-v6-hero__copy {
  min-width: 0;
}
.sa-v6-hero__eyebrow {
  color: var(--primary-600);
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-bold);
  letter-spacing: 0.04em;
}
.sa-v6-hero h2 {
  margin: 0;
  overflow: hidden;
  color: var(--text-primary);
  font-size: var(--font-size-xl);
  font-weight: var(--font-weight-semibold);
  line-height: 1.35;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.sa-v6-hero p {
  margin: 0;
  overflow: hidden;
  color: var(--text-secondary);
  font-size: var(--font-size-xs);
  line-height: 1.4;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.sa-v6-hero__metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(74px, 90px));
  margin: 0;
}
.sa-v6-hero__metric {
  min-width: 0;
  padding: 0 var(--space-3);
  border-left: 1px solid var(--border-light);
}
.sa-v6-hero__metric dt {
  overflow: hidden;
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
  line-height: 1.4;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.sa-v6-hero__metric dd {
  margin: 0;
  color: var(--text-primary);
  font-size: var(--font-size-metric-sm);
  font-weight: var(--font-weight-semibold);
  font-variant-numeric: tabular-nums;
  line-height: 1.2;
}
.sa-v6-flow {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  min-height: 32px;
  margin: 0;
  padding: var(--space-1) var(--space-2);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-lg);
  background: var(--bg-card);
  box-shadow: var(--shadow-card);
  list-style: none;
}
.sa-v6-flow li {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-1);
  min-width: 0;
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-medium);
  white-space: nowrap;
}
.sa-v6-flow li:not(:last-child)::after {
  position: absolute;
  right: calc(var(--space-1) * -1);
  color: var(--text-disabled);
  content: '—';
}
.sa-v6-flow li.is-active {
  color: var(--primary-700);
  font-weight: var(--font-weight-semibold);
}
.sa-v6-flow__index {
  display: grid;
  place-items: center;
  width: var(--space-5);
  height: var(--space-5);
  border: 1px solid var(--primary-100);
  border-radius: var(--radius-full);
  background: var(--primary-50);
  color: var(--primary-600);
  font-size: 11px;
  font-variant-numeric: tabular-nums;
}
.sa-v6-flow li.is-active .sa-v6-flow__index {
  border-color: var(--primary-600);
  background: var(--primary-600);
  color: var(--text-inverse);
}
.sa-v6-workspace {
  display: grid;
  grid-template-columns: minmax(0, 1.62fr) minmax(300px, 0.72fr);
  align-items: start;
  gap: var(--space-3);
  min-width: 0;
}
.sa-v6-panel {
  overflow: hidden;
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-card);
}
.sa-v6-panel :deep(.app-section-card__head) {
  padding: var(--space-2) var(--space-3);
}
.sa-v6-panel :deep(.app-section-card__title) {
  font-size: var(--font-size-md);
  line-height: 1.35;
}
.sa-v6-panel :deep(.app-section-card__subtitle) {
  margin-top: 0;
  font-size: var(--font-size-xs);
  line-height: 1.35;
}
.sa-v6-panel :deep(.app-section-card__body) {
  padding: var(--space-3);
}
.sa-v6-queue-card :deep(.app-section-card__body) {
  padding: var(--space-1) var(--space-2) var(--space-2);
}
.sa-v6-scope-note {
  display: inline-flex;
  align-items: center;
  min-height: 26px;
  padding: 0 var(--space-2);
  border: 1px solid var(--primary-100);
  border-radius: var(--radius-full);
  background: var(--primary-50);
  color: var(--primary-700);
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-medium);
}
.sa-v6-queue {
  display: grid;
  gap: var(--space-1);
}
.sa-v6-queue-row {
  --sa-v6-tone: var(--primary-600);
  --sa-v6-soft: var(--primary-50);
  display: grid;
  grid-template-columns: 38px minmax(0, 1fr) 64px 92px;
  align-items: center;
  gap: var(--space-2);
  min-height: 64px;
  padding: var(--space-2);
  border: 1px solid var(--border-base);
  border-left: 3px solid var(--sa-v6-tone);
  border-radius: var(--radius-lg);
  background: var(--bg-card);
  color: var(--text-primary);
  text-align: left;
  transition: border-color 150ms ease, background 150ms ease, transform 150ms ease;
}
.sa-v6-queue-row:hover:not(:disabled) {
  border-color: color-mix(in srgb, var(--sa-v6-tone) 42%, var(--border-base));
  background: color-mix(in srgb, var(--sa-v6-soft) 58%, var(--bg-card));
  transform: translateX(1px);
}
.sa-v6-queue-row:focus-visible {
  outline: 2px solid color-mix(in srgb, var(--sa-v6-tone) 55%, var(--bg-card));
  outline-offset: 2px;
}
.sa-v6-queue-row:disabled {
  cursor: not-allowed;
  opacity: 0.65;
}
.sa-v6-queue-row.is-zero {
  border-left-color: var(--success-600);
}
.sa-v6-queue-row.is-danger {
  --sa-v6-tone: var(--danger-600);
  --sa-v6-soft: var(--danger-50);
}
.sa-v6-queue-row.is-warning {
  --sa-v6-tone: var(--warning-600);
  --sa-v6-soft: var(--warning-50);
}
.sa-v6-queue-row.is-success {
  --sa-v6-tone: var(--success-600);
  --sa-v6-soft: var(--success-50);
}
.sa-v6-queue-row.is-neutral {
  --sa-v6-tone: var(--text-secondary);
  --sa-v6-soft: var(--bg-section);
}
.sa-v6-queue-row__icon {
  display: grid;
  place-items: center;
  width: 36px;
  height: 36px;
  border-radius: var(--radius-lg);
  background: var(--sa-v6-soft);
  color: var(--sa-v6-tone);
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-bold);
}
.sa-v6-queue-row__copy {
  min-width: 0;
}
.sa-v6-queue-row__title {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  min-width: 0;
}
.sa-v6-queue-row__title strong {
  overflow: hidden;
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
  line-height: 1.35;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.sa-v6-queue-row__description,
.sa-v6-queue-row__meta {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.sa-v6-queue-row__description {
  color: var(--text-secondary);
  font-size: var(--font-size-xs);
  line-height: 1.35;
}
.sa-v6-queue-row__meta {
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
  line-height: 1.3;
}
.sa-v6-queue-row__count {
  display: flex;
  align-items: baseline;
  justify-content: flex-end;
  gap: var(--space-1);
  color: var(--text-secondary);
  font-variant-numeric: tabular-nums;
}
.sa-v6-queue-row__count strong {
  color: var(--text-primary);
  font-size: var(--font-size-metric-sm);
  font-weight: var(--font-weight-semibold);
  line-height: 1.15;
}
.sa-v6-queue-row__count small {
  font-size: var(--font-size-xs);
}
.sa-v6-queue-row__action {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-1);
  min-height: 36px;
  padding: 0 var(--space-2);
  border: 1px solid color-mix(in srgb, var(--sa-v6-tone) 26%, var(--border-base));
  border-radius: var(--radius-md);
  background: var(--sa-v6-soft);
  color: var(--sa-v6-tone);
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-semibold);
  white-space: nowrap;
}
.sa-v6-side {
  display: grid;
  gap: var(--space-3);
  min-width: 0;
}
.sa-v6-scope-grid,
.sa-v6-risk-numbers {
  display: grid;
  gap: var(--space-2);
}
.sa-v6-scope-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}
.sa-v6-risk-numbers {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}
.sa-v6-scope-grid > div,
.sa-v6-risk-numbers > div {
  min-width: 0;
  padding: var(--space-2);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-lg);
  background: var(--bg-section);
}
.sa-v6-scope-grid span,
.sa-v6-risk-numbers span {
  display: block;
  overflow: hidden;
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
  line-height: 1.35;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.sa-v6-scope-grid strong,
.sa-v6-risk-numbers strong {
  display: block;
  overflow: hidden;
  color: var(--text-primary);
  font-weight: var(--font-weight-semibold);
  font-variant-numeric: tabular-nums;
  line-height: 1.3;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.sa-v6-scope-grid strong {
  font-size: var(--font-size-lg);
}
.sa-v6-risk-numbers strong {
  color: var(--danger-600);
  font-size: var(--font-size-xl);
}
.sa-v6-card-note {
  margin: var(--space-2) 0 0;
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
  line-height: 1.5;
}
.sa-v6-risk-card :deep(.app-perm-btn),
.sa-v6-risk-card :deep(.app-button) {
  width: 100%;
  margin-top: var(--space-2);
}
.sa-v6-entry-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-2);
}
.sa-v6-entry {
  display: grid;
  grid-template-columns: 30px minmax(0, 1fr);
  align-items: center;
  gap: var(--space-2);
  min-width: 0;
  min-height: 48px;
  padding: var(--space-2);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-lg);
  background: var(--bg-section);
  color: var(--text-primary);
  text-align: left;
}
.sa-v6-entry:hover {
  border-color: var(--primary-100);
  background: var(--primary-50);
}
.sa-v6-entry:focus-visible {
  outline: 2px solid var(--primary-500);
  outline-offset: 2px;
}
.sa-v6-entry__icon {
  display: grid;
  place-items: center;
  width: 30px;
  height: 30px;
  border-radius: var(--radius-md);
  background: var(--primary-50);
  color: var(--primary-600);
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-bold);
}
.sa-v6-entry strong,
.sa-v6-entry small {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.sa-v6-entry strong {
  font-size: var(--font-size-xs);
  line-height: 1.35;
}
.sa-v6-entry small {
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
  line-height: 1.3;
}
.sa-v6-support-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.45fr) minmax(300px, 0.55fr);
  gap: var(--space-3);
}
.sa-dashboard-panel--audit :deep(.app-section-card__body) {
  max-height: 218px;
  overflow-y: auto;
  scrollbar-gutter: stable;
}
.sa-v6-inline-warning {
  margin-bottom: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--warning-100);
  border-radius: var(--radius-md);
  background: var(--warning-50);
  color: var(--warning-700);
  font-size: var(--font-size-xs);
  line-height: 1.5;
}
.sa-v6-bridge-actions {
  display: grid;
  gap: var(--space-2);
}
.sa-v6-bridge-actions :deep(.app-perm-btn),
.sa-v6-bridge-actions :deep(.app-button) {
  width: 100%;
}
.sa-updated-hint {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
}
@media (max-width: 1450px) {
  .sa-v6-page-shell :deep(.mps__subtitle) {
    max-width: 560px;
  }
  .sa-v6-hero__metrics {
    grid-template-columns: repeat(4, minmax(68px, 78px));
  }
  .sa-v6-workspace {
    grid-template-columns: minmax(0, 1.7fr) minmax(280px, 0.62fr);
  }
  .sa-v6-queue-row {
    grid-template-columns: 36px minmax(0, 1fr) 56px 86px;
  }
  .sa-v6-risk-numbers {
    grid-template-columns: repeat(3, minmax(72px, 1fr));
  }
}
@media (max-width: 1180px) {
  .sa-v6-hero__metrics {
    grid-template-columns: repeat(2, minmax(78px, 1fr));
  }
  .sa-v6-workspace,
  .sa-v6-support-grid {
    grid-template-columns: 1fr;
  }
  .sa-v6-side {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
  .sa-v6-entry-grid {
    grid-template-columns: 1fr;
  }
}
@media (max-width: 960px) {
  .sa-v6-page-shell :deep(.mps__subtitle) {
    max-width: 100%;
    white-space: normal;
  }
  .sa-v6-hero {
    grid-template-columns: 1fr;
    gap: var(--space-2);
  }
  .sa-v6-hero h2,
  .sa-v6-hero p {
    white-space: normal;
  }
  .sa-v6-hero__metrics {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }
  .sa-v6-side {
    grid-template-columns: 1fr;
  }
  .sa-v6-entry-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}
@media (max-width: 720px) {
  .sa-v6-flow {
    grid-template-columns: 1fr;
    gap: var(--space-1);
  }
  .sa-v6-flow li {
    justify-content: flex-start;
  }
  .sa-v6-flow li::after {
    display: none;
  }
  .sa-v6-queue-row {
    grid-template-columns: 36px minmax(0, 1fr) auto;
  }
  .sa-v6-queue-row__count {
    grid-column: 3;
    grid-row: 1;
  }
  .sa-v6-queue-row__action {
    grid-column: 2 / 4;
    width: max-content;
  }
  .sa-v6-entry-grid,
  .sa-v6-scope-grid,
  .sa-v6-risk-numbers,
  .sa-v6-hero__metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
@media (prefers-reduced-motion: reduce) {
  .sa-v6-queue-row {
    transition: none;
  }
}
</style>
