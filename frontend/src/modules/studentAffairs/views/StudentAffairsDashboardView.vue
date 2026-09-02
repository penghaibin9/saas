<template>
  <AppPageShell
    title="今日工作"
    subtitle="按当前角色和数据范围汇总真实学工事项；先看运行结论，再进入原业务工作区。"
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
      <AppExportButton :export-fn="exportLedger" :has-permission="canBtn('studentAffairs.dashboard.view')" />
    </template>

    <AppGlobalState
      :state="pageState"
      :title="stateTitle"
      :description="stateDescription"
      loading-text="正在加载学工今日工作真实数据…"
      @retry="load"
      @back="$router.push('/workbench')"
    >
      <template #actions>
        <div class="sa-state-actions">
          <button
            v-if="pageState === 'error' || pageState === 'empty'"
            type="button"
            class="sa-state-button sa-state-button--primary"
            @click="load"
          >
            重新加载
          </button>
          <button type="button" class="sa-state-button" @click="$router.push('/workbench')">
            返回工作台
          </button>
        </div>
      </template>

      <div v-if="isDegraded" class="sa-degraded" role="status" aria-live="polite">
        <span class="sa-degraded__icon" aria-hidden="true">!</span>
        <div>
          <strong>部分辅助信息暂不可用</strong>
          <p>{{ auditError }}。Dashboard 主数据仍按真实返回展示，不把审计加载失败解释为 0。</p>
        </div>
      </div>

      <section class="sa-hero" aria-labelledby="sa-today-conclusion">
        <div class="sa-hero__copy">
          <span class="sa-hero__eyebrow">TODAY · {{ roleProjection.eyebrow }}</span>
          <h2 id="sa-today-conclusion">{{ currentConclusion }}</h2>
          <p>{{ roleProjection.description }}</p>
        </div>
        <div class="sa-hero__stats" aria-label="今日工作关键真值">
          <article v-for="card in headlineCards" :key="card.key" class="sa-hero-stat">
            <span>{{ card.label }}</span>
            <strong>{{ displayMetricValue(card) }}<small v-if="card.unit"> {{ card.unit }}</small></strong>
          </article>
        </div>
      </section>

      <div class="sa-truthbar" role="note">
        <span class="sa-truthbar__icon" aria-hidden="true">真</span>
        <div class="sa-truthbar__copy">
          <strong>数据真值边界</strong>
          <p>
            本页只使用现有 Dashboard 返回的学生、班级、统一待办、请假、困难、奖助、处分和风险聚合；
            当前接口没有学生级优先名单、统一跟进时间和推荐动作时，页面不生成示例学生。
          </p>
          <div class="sa-truthbar__gaps" aria-label="当前数据缺口">
            <AppStatusTag type="warning" label="DATA GAP" />
            <span v-for="gap in dataGapLabels" :key="gap">{{ gap }}</span>
          </div>
        </div>
      </div>

      <div class="sa-dashboard-metrics" aria-label="当前范围真实指标">
        <AppMetricCard
          v-for="card in metricCards"
          :key="card.key"
          :title="card.label"
          :value="card.value"
          :unit="card.unit"
          :accent="metricAccent(card.key)"
          :drillable="!!card.drillPath"
          :drill-target="card.drillPath"
          @drill="go"
        />
      </div>

      <AppSectionCard
        class="sa-flow-card"
        title="学生问题黄金闭环"
        subtitle="这是页面导航主链，不新增或替代任何后端状态机"
      >
        <ol class="sa-flow" aria-label="学生问题处理闭环">
          <li
            v-for="(step, index) in studentLoopSteps"
            :key="step.title"
            class="sa-flow__item"
            :class="{ 'is-current': index === 0 }"
          >
            <span class="sa-flow__index">{{ index + 1 }}</span>
            <strong>{{ step.title }}</strong>
            <small>{{ step.subtitle }}</small>
          </li>
        </ol>
      </AppSectionCard>

      <div class="sa-main-grid">
        <AppSectionCard
          class="sa-panel"
          title="当前业务队列"
          subtitle="按现有真实聚合字段组织；这里只提供业务深链，不替服务端推荐处置动作"
        >
          <div class="sa-queue">
            <article v-for="item in businessQueues" :key="item.key" class="sa-queue-row">
              <span class="sa-queue-row__marker" :class="`is-${item.accent}`" aria-hidden="true">
                {{ item.shortLabel }}
              </span>
              <div class="sa-queue-row__content">
                <div class="sa-queue-row__title">
                  <strong>{{ item.label }}</strong>
                  <AppStatusTag
                    :type="item.tagType"
                    :label="`${displayMetricValue(item)} ${item.unit || ''}`.trim()"
                  />
                </div>
                <p>{{ item.hint }}</p>
              </div>
              <AppPermissionButton
                :allowed="item.allowed"
                :code="item.permissionCode"
                :disabled="!item.path"
                variant="secondary"
                size="sm"
                reason="当前身份无权进入此业务"
                @click="go(item.path)"
              >
                进入业务
              </AppPermissionButton>
            </article>
          </div>
        </AppSectionCard>

        <div class="sa-side-stack">
          <AppSectionCard class="sa-panel" title="当前角色工作视角" subtitle="同一母版按真实角色和数据范围投影">
            <div class="sa-role-lens">
              <span class="sa-role-lens__avatar" aria-hidden="true">{{ roleProjection.avatar }}</span>
              <div>
                <strong>{{ dashboard.viewLabel || roleProjection.label }}</strong>
                <p>{{ roleProjection.focus }}</p>
              </div>
            </div>
            <dl class="sa-role-facts">
              <div><dt>数据范围</dt><dd>{{ scopeLabel }}</dd></div>
              <div><dt>页面对象</dt><dd>{{ roleProjection.object }}</dd></div>
              <div>
                <dt>最高风险</dt>
                <dd>
                  <AppRiskTag v-if="riskCount > 0" :level="riskLevel" />
                  <AppStatusTag v-else type="success" label="暂无未关闭风险" />
                </dd>
              </div>
            </dl>
          </AppSectionCard>

          <AppSectionCard class="sa-panel" title="下一步如何判断" subtitle="本页不猜服务端动作">
            <div class="sa-next-rule">
              <span aria-hidden="true">→</span>
              <div>
                <strong>进入原业务工作区继续判断</strong>
                <p>风险动作继续服从服务端 allowedActions；其他业务继续服从各自状态、权限和数据范围。</p>
              </div>
            </div>
          </AppSectionCard>
        </div>
      </div>

      <div class="sa-support-grid">
        <AppSectionCard class="sa-panel" title="真实业务入口" subtitle="保留数字迎新、宿舍以及跨中心风险的现有深链">
          <div class="sa-service-grid">
            <article v-for="link in serviceLinks" :key="link.key" class="sa-service-link">
              <div>
                <strong>{{ link.label }}</strong>
                <p>{{ link.description }}</p>
              </div>
              <AppPermissionButton
                :allowed="link.allowed"
                :code="link.permissionCode"
                variant="secondary"
                size="sm"
                reason="当前身份无权进入此业务"
                @click="go(link.path)"
              >
                打开
              </AppPermissionButton>
            </article>
          </div>
        </AppSectionCard>

        <AppSectionCard class="sa-panel sa-panel--audit" title="最近操作记录" subtitle="当前权限与数据范围内的真实操作留痕">
          <div v-if="auditError" class="sa-audit-warning" role="status">
            <AppStatusTag type="warning" label="审计加载降级" />
            <span>最近操作记录暂不可用，主数据不受影响。</span>
          </div>
          <AppAuditTrail :records="auditLogs" compact empty-text="暂无可展示审计记录" />
        </AppSectionCard>
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
  AppMetricCard,
  AppPageShell,
  AppPermissionButton,
  AppRiskTag,
  AppSectionCard,
  AppStatusTag
} from '@/components/common'
import studentAffairsApi from '@/modules/studentAffairs/api/studentAffairsB.api'
import { canCode } from '@/modules/studentAffairs/composables/permission'

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

const ROLE_PROJECTION = {
  COUNSELOR: {
    label: '辅导员', avatar: '辅', eyebrow: '辅导员工作视角', object: '本人负责学生',
    focus: '先看本人负责范围内的风险、待办和请假，再进入具体学生与业务。',
    description: '辅导员先处理当前负责范围内的学生事项；优先级只依据现有聚合，不生成假学生名单。'
  },
  COLLEGE_SA: {
    label: '学院学工', avatar: '院', eyebrow: '学院工作视角', object: '本院班级与学生',
    focus: '先看本院真实积压，再通过原台账下钻班级、学生和责任人。',
    description: '学院角色按本院数据范围观察业务积压；当前没有班级和责任人级正式聚合时不造排名。'
  },
  SA_ADMIN: {
    label: '学工处', avatar: '校', eyebrow: '全校管理视角', object: '全校业务域',
    focus: '先看全校真实业务聚合，再进入对应业务台账核查。',
    description: '管理角色观察全校业务域；当前没有学院健康排名时，只展示现有可信指标。'
  }
}

export default {
  name: 'StudentAffairsDashboardView',
  props: { ctx: { type: Object, default: null } },
  components: {
    AppAuditTrail,
    AppDateDisplay,
    AppExportButton,
    AppGlobalState,
    AppMetricCard,
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
      auditError: '',
      dashboard: {
        summaryCards: [], moduleCards: [], view: '', viewLabel: '', scopeMode: '', scopeLabel: '', riskSummary: {}
      },
      auditLogs: []
    }
  },
  computed: {
    pageState() {
      if (this.loading) return 'loading'
      if (!this.canBtn('studentAffairs.dashboard.view')) return 'forbidden'
      if (this.errorMessage) return 'error'
      if (this.dashboard.scopeMode === 'NONE') return 'empty'
      return this.metricCards.length ? 'ready' : 'empty'
    },
    stateTitle() {
      if (this.pageState === 'empty' && this.dashboard.scopeMode === 'NONE') return '当前身份尚未配置数据范围'
      if (this.pageState === 'empty') return '当前范围暂无可展示数据'
      return ''
    },
    stateDescription() {
      if (this.errorMessage) return this.errorMessage
      if (this.dashboard.scopeMode === 'NONE') return '系统已按 fail-closed 返回空范围，请联系学校管理员配置组织或班级责任范围。'
      if (this.pageState === 'empty') return '当前真实接口没有返回可展示的 Dashboard 指标，可刷新或返回工作台。'
      return ''
    },
    isDegraded() {
      return this.pageState === 'ready' && !!this.auditError
    },
    metricCards() {
      return (this.dashboard.summaryCards || []).map((card) => {
        const permissionCode = CARD_PERM[card.key] || ''
        const allowed = !permissionCode || this.canBtn(permissionCode)
        return {
          ...card,
          permissionCode,
          allowed,
          drillPath: allowed ? (card.drillPath || FALLBACK_DRILL[card.key] || '') : ''
        }
      })
    },
    metricMap() {
      return Object.fromEntries(this.metricCards.map((card) => [card.key, card]))
    },
    headlineCards() {
      const keys = ['pendingTodo', 'riskStudents', 'pendingLeave', 'overdueLeave']
      return keys.map((key) => this.metricMap[key]).filter(Boolean).slice(0, 4)
    },
    scopeLabel() {
      if (this.dashboard.scopeLabel) return this.dashboard.scopeLabel
      return ({ ADMIN_TENANT: '全校', SCOPED: '本人负责范围', SELF: '本人负责范围', NONE: '无数据范围' })[this.dashboard.scopeMode] || '按当前身份'
    },
    roleProjection() {
      return ROLE_PROJECTION[this.dashboard.view] || ROLE_PROJECTION.COUNSELOR
    },
    riskCount() {
      const summary = this.dashboard.riskSummary || {}
      const card = this.metricMap.riskStudents || {}
      return Number(summary.openStudentCount != null ? summary.openStudentCount : (card.value || 0))
    },
    riskLevel() {
      const summary = this.dashboard.riskSummary || {}
      const card = this.metricMap.riskStudents || {}
      const value = String(summary.topRiskLevel || card.topRiskLevel || 'LOW').toUpperCase()
      return ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].includes(value) ? value : 'LOW'
    },
    currentConclusion() {
      const todo = Number(this.metricMap.pendingTodo?.value || 0)
      const leave = Number(this.metricMap.pendingLeave?.value || 0)
      const overdue = Number(this.metricMap.overdueLeave?.value || 0)
      const risk = this.riskCount
      if (!todo && !leave && !overdue && !risk) return `当前${this.scopeLabel}暂无待办、待审请假、逾期销假或未关闭风险。`
      return `当前${this.scopeLabel}有 ${todo} 件统一待办、${risk} 名未关闭风险学生、${leave} 件待审请假，其中 ${overdue} 件逾期未销假。`
    },
    businessQueues() {
      const definitions = [
        ['pendingTodo', '统一待办', '办', '按当前身份可见的统一待办。', 'warning'],
        ['riskStudents', '风险与重点学生', '险', '未关闭风险学生去重计数；进入风险中心后继续服从 allowedActions。', 'risk'],
        ['pendingLeave', '请假与返校', '假', '待辅导员、学院或学工处处理的请假。', 'warning'],
        ['overdueLeave', '逾期未销假', '返', 'affairs_status=OVERDUE 的真实记录。', 'risk'],
        ['pendingAid', '困难认定', '困', '当前学生范围内的待审困难认定。', 'warning'],
        ['pendingFunding', '奖助评审', '助', '当前学生范围内的待审奖助申请。', 'warning'],
        ['pendingDiscipline', '处分审核', '纪', '处分或解除流程中的待审事项。', 'warning']
      ]
      return definitions.map(([key, label, shortLabel, hint, accent]) => {
        const card = this.metricMap[key] || {}
        return {
          key, label, shortLabel, hint, accent,
          value: card.value == null ? 0 : card.value,
          unit: card.unit || (key === 'riskStudents' ? '人' : '件'),
          path: card.drillPath || '',
          permissionCode: card.permissionCode || CARD_PERM[key] || '',
          allowed: card.allowed !== false,
          tagType: Number(card.value || 0) > 0 ? (accent === 'risk' ? 'danger' : 'warning') : 'success'
        }
      })
    },
    studentLoopSteps() {
      return [
        { title: '今日发现', subtitle: '统一待办' },
        { title: '学生360', subtitle: '完整背景' },
        { title: '风险处置', subtitle: '明确责任' },
        { title: '谈话/家校', subtitle: '真实沟通' },
        { title: '回访', subtitle: '约定时间' },
        { title: '关闭沉淀', subtitle: '留时间线' }
      ]
    },
    dataGapLabels() {
      return ['优先学生名单', '统一最近跟进', '统一下次回访', '推荐动作', '宿舍异常同口径统计']
    },
    serviceLinks() {
      return [
        {
          key: 'students', label: '公共学生主档', description: '从真实学生列表下钻唯一学生360。',
          permissionCode: 'studentAffairs.student.view', allowed: this.canBtn('studentAffairs.student.view'), path: '/admin/student/list'
        },
        {
          key: 'orientation', label: '数字迎新', description: '查看迎新批次、报到进度和异常学生。',
          permissionCode: 'studentAffairs.orientation.view',
          allowed: this.canBtn('orientation.dashboard.view') || this.canBtn('studentAffairs.orientation.view'), path: '/admin/orientation'
        },
        {
          key: 'dorm', label: '宿舍与公寓', description: '进入现有宿舍工作区查看真实房态与业务队列。',
          permissionCode: 'studentAffairs.dorm.view', allowed: this.canBtn('studentAffairs.dorm.view'), path: '/admin/student-affairs/dorm'
        },
        {
          key: 'internship', label: '岗位实习风险', description: '查看岗位实习中心的真实风险记录。',
          permissionCode: 'internship.risk.view', allowed: this.canBtn('internship.risk.view'), path: '/admin/internship/risks'
        },
        {
          key: 'graduation', label: '毕业设计风险', description: '查看毕业设计中心的真实风险归档。',
          permissionCode: 'graduation.risk.view', allowed: this.canBtn('graduation.risk.view'), path: '/admin/graduation/risk-archive?panel=risk'
        }
      ]
    }
  },
  created() {
    this.load()
  },
  methods: {
    canBtn(code) {
      return canCode(this.ctx, code)
    },
    displayMetricValue(card) {
      return card && card.value != null ? card.value : '—'
    },
    metricAccent(key) {
      if (['riskStudents', 'overdueLeave'].includes(key)) return 'risk'
      if (['pendingTodo', 'pendingLeave', 'pendingAid', 'pendingFunding', 'pendingDiscipline'].includes(key)) return 'warning'
      return 'primary'
    },
    async load() {
      this.loading = true
      this.errorMessage = ''
      this.auditError = ''
      try {
        const dashboardRes = await studentAffairsApi.getDashboard()
        this.dashboard = dashboardRes.data || { summaryCards: [], moduleCards: [], riskSummary: {} }
      } catch (error) {
        this.errorMessage = error?.message || '学工今日工作加载失败'
      }
      if (!this.errorMessage) {
        try {
          const auditRes = await studentAffairsApi.getAuditLogs()
          this.auditLogs = auditRes.data || []
        } catch (error) {
          this.auditLogs = []
          this.auditError = error?.message || '最近操作记录加载失败'
        }
      }
      this.loading = false
    },
    go(path) {
      if (path) this.$router.push(path)
    },
    exportLedger() {
      return studentAffairsApi.exportProfileLedger({ purpose: '学工今日工作范围学生台账导出' })
    }
  }
}
</script>

<style scoped>
.sa-updated-hint {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
}
.sa-state-actions { display: flex; justify-content: center; gap: var(--space-3); flex-wrap: wrap; }
.sa-state-button {
  min-height: 36px;
  padding: 0 var(--space-4);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-md);
  background: var(--bg-card);
  color: var(--text-secondary);
  cursor: pointer;
}
.sa-state-button--primary { border-color: var(--pri); background: var(--pri); color: var(--text-inverse); }
.sa-degraded {
  display: flex;
  align-items: flex-start;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  border: 1px solid var(--warning-100);
  border-radius: var(--radius-card-sm);
  background: var(--warning-50);
}
.sa-degraded__icon {
  display: grid;
  place-items: center;
  flex: 0 0 auto;
  width: 28px;
  height: 28px;
  border-radius: var(--radius-md);
  background: var(--warning-100);
  color: var(--warning-700);
  font-weight: var(--font-weight-bold);
}
.sa-degraded strong { color: var(--text-primary); font-size: var(--font-size-sm); }
.sa-degraded p { margin: var(--space-1) 0 0; color: var(--text-secondary); font-size: var(--font-size-xs); line-height: var(--line-height-base); }
.sa-hero {
  position: relative;
  isolation: isolate;
  overflow: hidden;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: var(--space-6);
  min-height: 148px;
  padding: var(--space-6);
  border: 1px solid var(--hero-bd);
  border-radius: var(--radius-xl);
  background: var(--hero-grad);
  box-shadow: var(--hero-shadow);
  color: var(--hero-tx);
}
.sa-hero::before {
  position: absolute;
  inset: 0;
  z-index: -1;
  content: '';
  background-image: linear-gradient(var(--hero-grid) 1px, transparent 1px), linear-gradient(90deg, var(--hero-grid) 1px, transparent 1px);
  background-size: 30px 30px;
}
.sa-hero__eyebrow { color: var(--hero-sub); font-size: var(--font-size-xs); font-weight: var(--font-weight-bold); letter-spacing: .06em; }
.sa-hero h2 { max-width: 900px; margin: var(--space-1) 0; color: var(--hero-tx); font-size: var(--font-size-xl); line-height: 1.45; }
.sa-hero p { max-width: 920px; margin: 0; color: var(--hero-sub); font-size: var(--font-size-sm); line-height: var(--line-height-base); }
.sa-hero__stats { display: grid; grid-template-columns: repeat(2, minmax(112px, 1fr)); gap: var(--space-2); }
.sa-hero-stat { min-width: 112px; padding: var(--space-3); border: 1px solid var(--hero-chip-bd); border-radius: var(--radius-card-sm); background: var(--hero-chip-bg); }
.sa-hero-stat span { display: block; color: var(--hero-sub); font-size: var(--font-size-xs); }
.sa-hero-stat strong { display: block; margin-top: var(--space-1); color: var(--hero-tx); font-size: var(--font-size-metric-sm); font-variant-numeric: tabular-nums; }
.sa-hero-stat small { color: var(--hero-sub); font-size: var(--font-size-xs); }
.sa-truthbar { display: flex; align-items: flex-start; gap: var(--space-3); padding: var(--space-3) var(--space-4); border: 1px solid var(--primary-100); border-radius: var(--radius-card-sm); background: var(--info-50); }
.sa-truthbar__icon { display: grid; place-items: center; flex: 0 0 auto; width: 28px; height: 28px; border-radius: var(--radius-md); background: var(--primary-100); color: var(--primary-700); font-weight: var(--font-weight-bold); }
.sa-truthbar__copy { min-width: 0; }
.sa-truthbar__copy > strong { color: var(--text-primary); font-size: var(--font-size-sm); }
.sa-truthbar__copy > p { margin: var(--space-1) 0 0; color: var(--text-secondary); font-size: var(--font-size-sm); line-height: var(--line-height-base); }
.sa-truthbar__gaps { display: flex; align-items: center; gap: var(--space-2); flex-wrap: wrap; margin-top: var(--space-2); }
.sa-truthbar__gaps > span:not(.app-status-tag) { color: var(--warning-700); font-size: var(--font-size-xs); }
.sa-dashboard-metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(152px, 1fr)); gap: var(--space-3); }
.sa-dashboard-metrics > :deep(.app-metric-card) { min-height: 108px; padding: var(--space-4); border-radius: var(--radius-card-sm); box-shadow: var(--shadow-card); }
.sa-dashboard-metrics :deep(.app-metric-card__title) { font-size: var(--font-size-xs); }
.sa-dashboard-metrics :deep(.app-metric-card__value) { font-size: var(--font-size-metric-lg); font-variant-numeric: tabular-nums; }
.sa-flow-card { overflow: hidden; }
.sa-flow-card :deep(.app-section-card__body) { padding-top: 0; }
.sa-flow { display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: var(--space-2); margin: 0; padding: 0; list-style: none; }
.sa-flow__item { display: grid; justify-items: center; align-content: center; min-height: 76px; padding: var(--space-2); border: 1px solid var(--border-base); border-radius: var(--radius-card-sm); background: var(--bg-section); text-align: center; }
.sa-flow__item.is-current { border-color: var(--primary-500); background: var(--primary-50); }
.sa-flow__index { display: grid; place-items: center; width: 28px; height: 28px; border-radius: var(--radius-full); background: var(--primary-100); color: var(--primary-700); font-size: var(--font-size-xs); font-weight: var(--font-weight-bold); }
.sa-flow__item.is-current .sa-flow__index { background: var(--pri); color: var(--text-inverse); }
.sa-flow__item strong { margin-top: var(--space-1); color: var(--text-primary); font-size: var(--font-size-xs); }
.sa-flow__item small { color: var(--text-tertiary); font-size: var(--font-size-xs); }
.sa-main-grid { display: grid; grid-template-columns: minmax(0, 1.45fr) minmax(300px, .62fr); align-items: start; gap: var(--space-4); }
.sa-side-stack { display: grid; gap: var(--space-4); }
.sa-panel { overflow: hidden; border-radius: var(--radius-card-sm); box-shadow: var(--shadow-card); }
.sa-panel :deep(.app-section-card__head) { padding: var(--space-4) var(--space-4) var(--space-3); }
.sa-panel :deep(.app-section-card__title) { font-size: var(--font-size-md); }
.sa-panel :deep(.app-section-card__body) { padding: var(--space-4); }
.sa-queue { display: grid; gap: var(--space-2); }
.sa-queue-row { display: grid; grid-template-columns: 42px minmax(0, 1fr) auto; align-items: center; gap: var(--space-3); min-height: 76px; padding: var(--space-3); border: 1px solid var(--border-base); border-radius: var(--radius-card-sm); background: var(--bg-card); }
.sa-queue-row:hover { border-color: var(--primary-100); background: var(--primary-25); }
.sa-queue-row__marker { display: grid; place-items: center; width: 42px; height: 42px; border-radius: var(--radius-full); background: var(--primary-50); color: var(--primary-700); font-size: var(--font-size-sm); font-weight: var(--font-weight-bold); }
.sa-queue-row__marker.is-warning { background: var(--warning-50); color: var(--warning-700); }
.sa-queue-row__marker.is-risk { background: var(--danger-50); color: var(--danger-600); }
.sa-queue-row__content { min-width: 0; }
.sa-queue-row__title { display: flex; align-items: center; gap: var(--space-2); flex-wrap: wrap; }
.sa-queue-row__title strong { color: var(--text-primary); font-size: var(--font-size-sm); }
.sa-queue-row__content p { margin: var(--space-1) 0 0; color: var(--text-secondary); font-size: var(--font-size-xs); line-height: var(--line-height-base); }
.sa-role-lens { display: flex; align-items: center; gap: var(--space-3); padding: var(--space-3); border: 1px solid var(--primary-100); border-radius: var(--radius-card-sm); background: var(--primary-50); }
.sa-role-lens__avatar { display: grid; place-items: center; flex: 0 0 auto; width: 42px; height: 42px; border-radius: var(--radius-full); background: var(--primary-100); color: var(--primary-700); font-size: var(--font-size-sm); font-weight: var(--font-weight-bold); }
.sa-role-lens strong { color: var(--text-primary); font-size: var(--font-size-sm); }
.sa-role-lens p { margin: var(--space-1) 0 0; color: var(--text-secondary); font-size: var(--font-size-xs); line-height: var(--line-height-base); }
.sa-role-facts { display: grid; gap: var(--space-2); margin: var(--space-3) 0 0; }
.sa-role-facts > div { display: grid; grid-template-columns: 84px minmax(0, 1fr); align-items: center; gap: var(--space-2); padding-top: var(--space-2); border-top: 1px solid var(--border-light); }
.sa-role-facts dt, .sa-role-facts dd { margin: 0; font-size: var(--font-size-xs); }
.sa-role-facts dt { color: var(--text-tertiary); }
.sa-role-facts dd { color: var(--text-primary); font-weight: var(--font-weight-medium); }
.sa-next-rule { display: flex; align-items: flex-start; gap: var(--space-3); padding: var(--space-3); border: 1px solid var(--primary-100); border-radius: var(--radius-card-sm); background: var(--primary-50); }
.sa-next-rule > span { display: grid; place-items: center; flex: 0 0 auto; width: 32px; height: 32px; border-radius: var(--radius-md); background: var(--primary-100); color: var(--primary-700); font-weight: var(--font-weight-bold); }
.sa-next-rule strong { color: var(--text-primary); font-size: var(--font-size-sm); }
.sa-next-rule p { margin: var(--space-1) 0 0; color: var(--text-secondary); font-size: var(--font-size-xs); line-height: var(--line-height-base); }
.sa-support-grid { display: grid; grid-template-columns: minmax(0, 1.2fr) minmax(340px, .8fr); align-items: stretch; gap: var(--space-4); }
.sa-service-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--space-2); }
.sa-service-link { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); min-height: 92px; padding: var(--space-3); border: 1px solid var(--border-base); border-radius: var(--radius-card-sm); background: var(--bg-card); }
.sa-service-link > div { min-width: 0; }
.sa-service-link strong { color: var(--text-primary); font-size: var(--font-size-sm); }
.sa-service-link p { margin: var(--space-1) 0 0; color: var(--text-secondary); font-size: var(--font-size-xs); line-height: var(--line-height-base); }
.sa-panel--audit :deep(.app-section-card__body) { max-height: 360px; overflow-y: auto; scrollbar-gutter: stable; }
.sa-audit-warning { display: flex; align-items: center; gap: var(--space-2); flex-wrap: wrap; margin-bottom: var(--space-3); color: var(--text-secondary); font-size: var(--font-size-xs); }
@media (max-width: 1500px) {
  .sa-main-grid, .sa-support-grid { grid-template-columns: 1fr; }
  .sa-side-stack { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 1120px) {
  .sa-hero { grid-template-columns: 1fr; }
  .sa-hero__stats { grid-template-columns: repeat(4, minmax(0, 1fr)); }
  .sa-flow { grid-template-columns: repeat(3, minmax(0, 1fr)); }
}
@media (max-width: 960px) {
  .sa-side-stack, .sa-service-grid { grid-template-columns: 1fr; }
}
@media (max-width: 720px) {
  .sa-dashboard-metrics, .sa-hero__stats { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .sa-flow { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .sa-queue-row { grid-template-columns: 42px minmax(0, 1fr); }
  .sa-queue-row :deep(.app-perm-btn) { grid-column: 2; justify-self: start; }
}
@media (max-width: 460px) {
  .sa-dashboard-metrics, .sa-hero__stats, .sa-flow { grid-template-columns: 1fr; }
}
</style>
