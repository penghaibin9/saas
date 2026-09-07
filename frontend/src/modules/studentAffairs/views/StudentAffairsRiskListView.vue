<template>
  <AppPageShell
    title="风险与重点学生"
    subtitle="按当前身份和数据范围汇总风险记录；先看结论，再分派、处置、跟进和闭环。"
    :role-name="roleName"
    :data-scope-name="scopeName"
    watermark-purpose="学工风险与重点学生查看"
  >
    <template #actions>
      <AppPermissionButton
        v-if="canScanTimeout"
        :allowed="canScanTimeout"
        code="studentAffairs.risk.handle"
        variant="secondary"
        :loading="actioning"
        @click="scanTimeout"
      >
        扫描超时
      </AppPermissionButton>
      <AppPermissionButton
        :allowed="canBtn('studentAffairs.risk.create')"
        code="studentAffairs.risk.create"
        :loading="actioning"
        @click="createRisk"
      >
        新建风险
      </AppPermissionButton>
    </template>

    <AppGlobalState
      :state="pageState"
      :title="stateTitle"
      :description="stateDescription"
      loading-text="正在加载风险与重点学生真实数据…"
      @retry="load"
      @back="$router.push('/admin/student-affairs/dashboard')"
    >
      <TaskContextBar
        :role-name="roleName"
        :scope-name="scopeName"
        :pending="pendingCount"
        :overdue="stats && stats.overdue"
        :filter-summary="taskFilterSummary"
        next-hint="优先分派或处置高危、危急和已超时记录。"
        :degraded="statsDegraded"
        @clear-filter="clearTaskFilters"
      />

      <template v-if="isRulePanel">
        <section class="risk-rule-hero">
          <span>RISK RULES · 规则真值</span>
          <h2>规则只解释服务端如何识别与流转风险，不在浏览器复制状态机。</h2>
          <p>创建、分派、处置、跟进、接管和关闭均继续由后端权限、数据范围、责任关系、状态和版本号共同裁定。</p>
        </section>
        <AppSectionCard title="风险规则摘要" subtitle="规则说明不扩大任何业务权限">
          <div class="sa-rules">
            <div v-for="rule in ruleItems" :key="rule.title" class="sa-rule">
              <strong>{{ rule.title }}</strong>
              <span>{{ rule.desc }}</span>
            </div>
          </div>
        </AppSectionCard>
      </template>

      <template v-else>
        <section class="risk-hero" aria-labelledby="risk-hero-title">
          <div class="risk-hero__copy">
            <span class="risk-hero__eyebrow">RISK · 当前运行结论</span>
            <h2 id="risk-hero-title">{{ riskConclusion }}</h2>
            <p>{{ riskConclusionHint }}</p>
          </div>
          <div class="risk-hero__metrics" aria-label="风险关键指标">
            <article v-for="item in heroMetrics" :key="item.key" class="risk-hero-metric">
              <span>{{ item.label }}</span>
              <strong :class="{ 'is-gap': item.isGap, 'is-alert': item.alert }">{{ item.value }}</strong>
              <small>{{ item.hint }}</small>
            </article>
          </div>
        </section>

        <div v-if="statsDegraded" class="risk-gap" role="status">
          <span aria-hidden="true">!</span>
          <div>
            <strong>风险记录可读取，但服务端聚合统计暂不可用</strong>
            <p>高危、未闭环、待分派和超时数字统一标记 DATA GAP；页面不会使用当前分页记录冒充全局统计。</p>
          </div>
          <button type="button" @click="load">重新加载</button>
        </div>

        <div class="risk-truthbar" role="note">
          <span class="risk-truthbar__mark" aria-hidden="true">真</span>
          <div>
            <strong>真实边界</strong>
            <p>队列数字来自服务端同谓词统计；行级按钮只认该行的 allowedActions，“我来处理”只认 canClaim，所有写操作继续提交 version。</p>
          </div>
          <AppStatusTag type="warning" label="全局重点学生聚合 · DATA GAP" />
        </div>

        <AppSectionCard
          class="risk-loop-card"
          title="学生问题黄金闭环"
          subtitle="风险中心负责识别、分派和处置；学生360、谈心家校与回访承担背景和持续跟踪"
        >
          <ol class="risk-loop" aria-label="学生问题闭环">
            <li v-for="(step, index) in studentLoopSteps" :key="step.title" :class="{ 'is-current': index === 2 }">
              <span>{{ index + 1 }}</span>
              <strong>{{ step.title }}</strong>
              <small>{{ step.subtitle }}</small>
            </li>
          </ol>
        </AppSectionCard>

        <section v-if="focusRisk" class="risk-focus" aria-labelledby="risk-focus-title">
          <div class="risk-focus__main">
            <span class="risk-focus__eyebrow">当前页优先焦点 · 非全局排名</span>
            <div class="risk-focus__title-row">
              <h3 id="risk-focus-title">{{ focusRisk.realName || '未命名学生' }}</h3>
              <AppRiskTag :level="focusRisk.riskLevel" />
              <AppStatusTag :type="statusKind(focusRisk.status)" :label="focusRisk.statusLabel || focusRisk.status" />
            </div>
            <p>{{ focusRisk.studentNo || focusRisk.studentId }} · {{ sourceLabel(focusRisk.source) }} · {{ focusRisk.title || '风险记录' }}</p>
            <small>{{ focusRisk.mentalMasked ? '心理来源明细已按角色脱敏；' : '' }}责任人：{{ ownerLabel(focusRisk) }}</small>
          </div>
          <div class="risk-focus__actions">
            <AppPermissionButton
              :allowed="canBtn('studentAffairs.student.view')"
              code="studentAffairs.student.view"
              variant="secondary"
              @click="goStudent360(focusRisk)"
            >
              学生360
            </AppPermissionButton>
            <AppPermissionButton
              v-if="focusRisk.canClaim"
              :allowed="canBtn('studentAffairs.risk.assign')"
              code="studentAffairs.risk.assign"
              variant="secondary"
              :loading="isRowActioning(focusRisk, 'CLAIM')"
              :disabled="isOtherRowActioning(focusRisk, 'CLAIM')"
              @click="claim(focusRisk)"
            >
              我来处理
            </AppPermissionButton>
            <AppPermissionButton
              v-if="primaryAction(focusRisk)"
              :allowed="canBtn(primaryAction(focusRisk).code)"
              :code="primaryAction(focusRisk).code"
              :loading="isRowActioning(focusRisk, primaryAction(focusRisk).key)"
              :disabled="isOtherRowActioning(focusRisk, primaryAction(focusRisk).key)"
              @click="primaryAction(focusRisk).run(focusRisk)"
            >
              {{ primaryAction(focusRisk).label }}
            </AppPermissionButton>
          </div>
        </section>

        <AppSectionCard title="风险学生与处置" subtitle="筛选和快捷队列均提交服务端，列表不是浏览器内的二次统计">
          <nav class="sa-queues" aria-label="风险快捷队列">
            <button
              v-for="q in quickQueues"
              :key="q.key"
              type="button"
              class="sa-queue"
              :class="[`is-${q.tone}`, { 'is-on': activeQueue === q.key, 'is-empty': q.count === 0 }]"
              :aria-pressed="activeQueue === q.key ? 'true' : 'false'"
              @click="selectQueue(q.key)"
            >
              <span class="sa-queue__dot" aria-hidden="true" />
              <span class="sa-queue__label">{{ q.label }}</span>
              <span v-if="q.count !== null" class="sa-queue__count">{{ q.count }}</span>
            </button>
          </nav>

          <div v-if="studentFilterLabel" class="sa-student-filter">
            <span>{{ studentFilterLabel }}</span>
            <button type="button" class="mp-link" @click="clearStudentFilter">清除筛选</button>
          </div>

          <div class="sa-toolbar">
            <AppSelect v-model="filters.source" class="sa-filter" :options="SOURCE_OPTIONS" placeholder="" @change="reload" />
            <AppSelect v-model="filters.riskLevel" class="sa-filter" :options="LEVEL_FILTER_OPTIONS" placeholder="" @change="reload" />
            <AppSelect v-model="filters.status" class="sa-filter" :options="STATUS_FILTER_OPTIONS" placeholder="" @change="onStatusSelect" />
            <span v-if="scanResult" class="sa-scan">{{ scanResult }}</span>
          </div>

          <DataTable
            v-if="risks.length || pagination.total > 0"
            :columns="riskColumns"
            :rows="risks"
            row-key="riskId"
            :pagination="pagination"
            @page-change="onPageChange"
          >
            <template #cell-student="{ row }">
              <button type="button" class="risk-student-link" @click="goStudent360(row)">
                <span>{{ row.realName || '未命名学生' }}</span>
                <small>{{ row.studentNo || row.studentId }}</small>
              </button>
            </template>
            <template #cell-source="{ row }">{{ sourceLabel(row.source) }}</template>
            <template #cell-riskLevel="{ row }"><AppRiskTag :level="row.riskLevel" /></template>
            <template #cell-status="{ row }"><AppStatusTag :type="statusKind(row.status)" :label="row.statusLabel || row.status" /></template>
            <template #cell-owner="{ row }">{{ ownerLabel(row) }}</template>
            <template #cell-summary="{ row }">
              <div class="mp-cell-main">{{ row.title || '风险记录' }}</div>
              <div v-if="row.mentalMasked" class="mp-cell-sub">心理来源明细已按角色脱敏</div>
            </template>
            <template #cell-actions="{ row }">
              <div class="sa-actions" :aria-label="`${row.realName || '该学生'}的可用操作`">
                <div v-if="primaryAction(row)" class="sa-actions__recommended">
                  <span class="sa-actions__hint">推荐下一步</span>
                  <AppPermissionButton
                    class="sa-actions__primary"
                    :allowed="canBtn(primaryAction(row).code)"
                    :code="primaryAction(row).code"
                    size="sm"
                    variant="primary"
                    :loading="isRowActioning(row, primaryAction(row).key)"
                    :disabled="isOtherRowActioning(row, primaryAction(row).key)"
                    :native-title="`推荐下一步：${primaryAction(row).label}`"
                    @click="primaryAction(row).run(row)"
                  >
                    <span>{{ primaryAction(row).label }}</span>
                    <span class="sa-actions__arrow" aria-hidden="true">→</span>
                  </AppPermissionButton>
                </div>

                <AppPermissionButton
                  v-if="row.canClaim"
                  class="sa-actions__claim"
                  :allowed="canBtn('studentAffairs.risk.assign')"
                  code="studentAffairs.risk.assign"
                  size="sm"
                  variant="secondary"
                  :loading="isRowActioning(row, 'CLAIM')"
                  :disabled="isOtherRowActioning(row, 'CLAIM')"
                  native-title="跳过责任人选择，直接分派给我"
                  @click="claim(row)"
                >
                  <span class="sa-actions__claim-dot" aria-hidden="true" />我来处理
                </AppPermissionButton>

                <div class="sa-actions__secondary">
                  <AppPermissionButton
                    v-for="a in secondaryActions(row)"
                    :key="a.key"
                    :allowed="canBtn(a.code)"
                    :code="a.code"
                    size="sm"
                    variant="secondary"
                    :loading="isRowActioning(row, a.key)"
                    :disabled="isOtherRowActioning(row, a.key)"
                    @click="a.run(row)"
                  >{{ a.label }}</AppPermissionButton>
                  <AppPermissionButton
                    class="sa-actions__detail"
                    :allowed="canBtn('studentAffairs.risk.view')"
                    code="studentAffairs.risk.view"
                    size="sm"
                    variant="ghost"
                    @click="$router.push(`/admin/student-affairs/risk/${row.riskId}`)"
                  >
                    查看详情
                  </AppPermissionButton>
                </div>
              </div>
            </template>
          </DataTable>

          <div v-else class="risk-empty">
            <span aria-hidden="true">✓</span>
            <strong>当前条件下暂无风险记录</strong>
            <p>这是当前服务端筛选结果，不代表其他数据范围或其他条件下没有风险。</p>
            <button v-if="taskFilterSummary" type="button" @click="clearTaskFilters">清除筛选</button>
          </div>
        </AppSectionCard>
      </template>
    </AppGlobalState>

    <AppDrawer :visible="createDlg.visible" title="新建风险记录" mode="modal" size="medium" @close="createDlg.visible = false">
      <div class="sa-form">
        <AppFormItem label="学生" required>
          <AppStudentPicker v-model="createDlg.studentId" placeholder="按姓名 / 学号搜索" :disabled="actioning" />
        </AppFormItem>
        <AppFormItem label="风险等级" required>
          <AppSelect v-model="createDlg.riskLevel" :options="RISK_LEVELS" :disabled="actioning" />
        </AppFormItem>
        <AppFormItem label="风险标题" required>
          <AppTextInput v-model="createDlg.title" placeholder="一句话概括风险事实" :disabled="actioning" />
        </AppFormItem>
        <AppFormItem label="风险详情" required hint="写清时间、表现和已了解情况，供责任人接手">
          <AppTextarea v-model="createDlg.detail" :rows="4" :disabled="actioning" />
        </AppFormItem>
        <AppInlineAlert v-if="createDlg.error" type="danger" :description="createDlg.error" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="actioning" @click="createDlg.visible = false">取消</AppButton>
        <AppButton variant="primary" :loading="actioning" @click="submitCreate">建单</AppButton>
      </template>
    </AppDrawer>

    <AppConfirmDialog
      v-model:visible="assignDlg.visible"
      title="分派责任人"
      type="primary"
      confirm-text="确认分派"
      :submitting="actioning"
      @confirm="submitAssign"
    >
      <AppFormItem label="责任人" required>
        <AppRiskOwnerPicker
          v-model="assignDlg.ownerId"
          placeholder="按姓名 / 工号搜索"
          data-scope-hint="仅可选持学工风险处置角色的在职账号"
        />
      </AppFormItem>
    </AppConfirmDialog>

    <AppConfirmDialog
      v-model:visible="processDlg.visible"
      :title="processDialog.title"
      type="primary"
      :confirm-text="processDialog.confirmText"
      require-reason
      :reason-label="processDialog.reasonLabel"
      phrase-scene-key="sa.risk.handle"
      :submitting="actioning"
      @confirm="submitProcess"
    />
  </AppPageShell>
</template>

<script>
import {
  AppConfirmDialog,
  AppFormItem,
  AppGlobalState,
  AppInlineAlert,
  AppPageShell,
  AppPermissionButton,
  AppRiskOwnerPicker,
  AppRiskTag,
  AppSectionCard,
  AppSelect,
  AppStatusTag,
  AppStudentPicker,
  AppTextInput,
  AppTextarea
} from '@/components/common'
import TaskContextBar from '@/modules/studentAffairs/components/TaskContextBar.vue'
import { AppButton, AppDrawer } from '@/components/ui'
import { DataTable } from '@/components/business'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairsB.api'
import { canCode } from '@/modules/studentAffairs/composables/permission'
import { resolveTodoStatus, readStudentFilter } from '@/modules/studentAffairs/utils/todoFilterSemantics'

const RISK_COLUMNS = [
  { key: 'student', title: '学生', width: '160px' },
  { key: 'source', title: '来源' },
  { key: 'riskLevel', title: '等级' },
  { key: 'status', title: '状态' },
  { key: 'owner', title: '责任人' },
  { key: 'summary', title: '摘要' },
  { key: 'actions', title: '操作', align: 'right', width: '270px' }
]

const RISK_LEVELS = [
  { value: 'LOW', label: '低风险' },
  { value: 'MEDIUM', label: '中风险' },
  { value: 'HIGH', label: '高风险' },
  { value: 'CRITICAL', label: '危急' }
]
const SOURCE_OPTIONS = [
  { value: '', label: '全部来源' },
  { value: 'ACADEMIC_WARNING', label: '学业预警' },
  { value: 'LEAVE_OVERDUE', label: '请假异常' },
  { value: 'DORM', label: '宿舍异常' },
  { value: 'MENTAL', label: '心理关注' }
]
const LEVEL_FILTER_OPTIONS = [
  { value: '', label: '全部等级' },
  { value: 'LOW', label: '低' },
  { value: 'MEDIUM', label: '中' },
  { value: 'HIGH', label: '高' },
  { value: 'CRITICAL', label: '重大' }
]
const STATUS_FILTER_OPTIONS = [
  { value: '', label: '全部状态' },
  { value: 'PENDING', label: '待处置' },
  { value: 'OPEN', label: '未关闭' },
  { value: 'NEW', label: '新建' },
  { value: 'ASSIGNED', label: '已分派' },
  { value: 'PROCESSING', label: '处置中' },
  { value: 'FOLLOWING', label: '持续跟进' },
  { value: 'ESCALATED', label: '已升级' },
  { value: 'CLOSED', label: '已关闭' }
]

const SCAN_ROLES = new Set([
  'SCHOOL_ADMIN', 'SCHOOL_LEADER', 'STUDENT_AFFAIRS_ADMIN', 'SA_ADMIN', 'PLATFORM_SUPER_ADMIN'
])

export default {
  name: 'StudentAffairsRiskListView',
  props: { ctx: { type: Object, default: null } },
  components: {
    AppButton,
    AppConfirmDialog,
    AppDrawer,
    AppFormItem,
    AppGlobalState,
    AppInlineAlert,
    AppPageShell,
    AppPermissionButton,
    AppRiskOwnerPicker,
    AppRiskTag,
    AppSectionCard,
    AppSelect,
    AppStatusTag,
    AppStudentPicker,
    AppTextInput,
    AppTextarea,
    DataTable,
    TaskContextBar
  },
  data() {
    return {
      riskColumns: RISK_COLUMNS,
      RISK_LEVELS,
      SOURCE_OPTIONS,
      LEVEL_FILTER_OPTIONS,
      STATUS_FILTER_OPTIONS,
      loading: true,
      actioning: false,
      rowActioning: { riskId: '', action: '' },
      errorMessage: '',
      risks: [],
      total: 0,
      stats: null,
      pagination: { page: 1, pageSize: 20, total: 0 },
      scanResult: '',
      createDlg: { visible: false, studentId: '', riskLevel: 'MEDIUM', title: '', detail: '', error: '' },
      assignDlg: { visible: false, riskId: '', ownerId: '', version: null },
      processDlg: { visible: false, riskId: '', version: null, action: 'PROCESS' },
      filters: { source: '', riskLevel: '', status: '', studentId: '' },
      studentFilter: { studentId: '', studentNo: '', studentName: '' },
      activeQueue: 'ALL',
      routeIntentConsumed: false
    }
  },
  computed: {
    roleName() {
      return (this.ctx && this.ctx.currentRole && this.ctx.currentRole.roleName) || '学工角色'
    },
    scopeName() {
      return (this.ctx && this.ctx.dataScope && (this.ctx.dataScope.scopeName || this.ctx.dataScope.name)) || '学工数据范围'
    },
    pendingCount() {
      return this.stats ? Number(this.stats.unassigned || 0) : null
    },
    taskFilterSummary() {
      if (this.studentFilterLabel) return this.studentFilterLabel
      const parts = []
      if (this.filters.source) parts.push(`来源：${this.sourceLabel(this.filters.source)}`)
      if (this.filters.riskLevel) parts.push(`等级：${this.filters.riskLevel}`)
      if (this.filters.status) parts.push(`状态：${this.filters.status}`)
      return parts.join('；')
    },
    isRulePanel() {
      return this.$route.name === 'student-affairs-risk-rules'
    },
    studentFilterLabel() {
      const f = this.studentFilter || {}
      if (!f.studentId && !f.studentNo) return ''
      let name = f.studentName || ''
      let no = f.studentNo || ''
      const id = f.studentId || ''
      if ((!name || !no) && id && this.risks.length) {
        const hit = this.risks.find((x) => String(x.studentId) === String(id))
        if (hit) {
          if (!name) name = hit.realName || ''
          if (!no) no = hit.studentNo || ''
        }
      }
      if (name || no) return `当前学生筛选：${name || '学生'}${no ? ` / ${no}` : ''}`
      return `当前学生筛选：#${id}`
    },
    pageState() {
      if (!this.canBtn('studentAffairs.risk.view')) return 'forbidden'
      if (this.loading) return 'loading'
      if (this.errorMessage) return 'error'
      return 'ready'
    },
    stateTitle() {
      if (this.pageState === 'forbidden') return '当前身份无权查看风险记录'
      if (this.pageState === 'error') return '风险与重点学生加载失败'
      return ''
    },
    stateDescription() {
      if (this.pageState === 'forbidden') return '请切换具备 studentAffairs.risk.view 的真实身份，或联系管理员核对角色与数据范围。'
      return this.errorMessage
    },
    statsDegraded() {
      return !this.loading && !this.errorMessage && !this.stats
    },
    canScanTimeout() {
      const role = (this.ctx?.currentRoleCode || this.ctx?.currentRole?.roleCode || '').toUpperCase()
      return SCAN_ROLES.has(role) && this.canBtn('studentAffairs.risk.handle')
    },
    riskConclusion() {
      if (!this.stats) return this.risks.length ? '风险记录已加载，聚合结论暂不可用。' : '当前条件下没有返回风险记录。'
      const high = Number(this.stats.highCritical || 0)
      const overdue = Number(this.stats.overdue || 0)
      const unassigned = Number(this.stats.unassigned || 0)
      const open = Number(this.stats.open || 0)
      if (!high && !overdue && !unassigned && !open) return '当前范围暂无未闭环风险，继续保持常态关注。'
      const fragments = []
      if (high) fragments.push(`${high} 条高危或危急`)
      if (overdue) fragments.push(`${overdue} 条已超时`)
      if (unassigned) fragments.push(`${unassigned} 条待分派`)
      return `当前有 ${open} 条未闭环风险${fragments.length ? `，其中${fragments.join('、')}` : ''}。`
    },
    riskConclusionHint() {
      if (!this.stats) return '当前分页记录不会被用来推算全局重点学生人数；统计恢复后再给出全局结论。'
      if (Number(this.stats.highCritical || 0) || Number(this.stats.overdue || 0)) return '先处置高危、危急与超时记录，再处理普通待分派和持续跟进。'
      if (Number(this.stats.unassigned || 0)) return '当前首要任务是明确责任人，随后进入处置与跟进。'
      return '按责任人持续推进未闭环记录，并在事实充分后由原状态机关闭。'
    },
    heroMetrics() {
      if (!this.stats) {
        return [
          { key: 'high', label: '高危 / 危急', value: 'DATA GAP', hint: '等待服务端聚合', isGap: true },
          { key: 'open', label: '未闭环', value: 'DATA GAP', hint: '不以当前页冒充', isGap: true },
          { key: 'unassigned', label: '待分派', value: 'DATA GAP', hint: '等待服务端聚合', isGap: true },
          { key: 'overdue', label: '已超时', value: 'DATA GAP', hint: '等待服务端聚合', isGap: true }
        ]
      }
      const high = Number(this.stats.highCritical || 0)
      const open = Number(this.stats.open || 0)
      const unassigned = Number(this.stats.unassigned || 0)
      const overdue = Number(this.stats.overdue || 0)
      return [
        { key: 'high', label: '高危 / 危急', value: high, hint: '服务端同口径', alert: high > 0 },
        { key: 'open', label: '未闭环', value: open, hint: '当前数据范围', alert: open > 0 },
        { key: 'unassigned', label: '待分派', value: unassigned, hint: '需明确责任人', alert: unassigned > 0 },
        { key: 'overdue', label: '已超时', value: overdue, hint: '需优先处置', alert: overdue > 0 }
      ]
    },
    focusRisk() {
      if (!this.risks.length) return null
      const levelRank = { CRITICAL: 4, HIGH: 3, MEDIUM: 2, LOW: 1 }
      const statusRank = { ESCALATED: 6, NEW: 5, ASSIGNED: 4, PROCESSING: 3, FOLLOWING: 2, CLOSED: 0 }
      return [...this.risks].sort((a, b) => {
        const level = (levelRank[b.riskLevel] || 0) - (levelRank[a.riskLevel] || 0)
        if (level) return level
        if (Boolean(a.overdue) !== Boolean(b.overdue)) return b.overdue ? 1 : -1
        return (statusRank[b.status] || 0) - (statusRank[a.status] || 0)
      })[0]
    },
    studentLoopSteps() {
      return [
        { title: '今日发现', subtitle: '统一待办与来源事实' },
        { title: '学生360', subtitle: '查看完整背景' },
        { title: '风险处置', subtitle: '分派并明确责任' },
        { title: '谈话家校', subtitle: '形成真实沟通' },
        { title: '回访', subtitle: '按约定时间跟进' },
        { title: '关闭沉淀', subtitle: '留痕并回到画像' }
      ]
    },
    processDialog() {
      return ({
        PROCESS: { title: '记录本次处置', confirmText: '确认记录', reasonLabel: '处置内容（≥5字）' },
        FOLLOW: { title: '转为持续跟进', confirmText: '开始跟进', reasonLabel: '本次跟进安排（≥5字）' },
        TAKEOVER: { title: '接管升级风险', confirmText: '确认接管', reasonLabel: '接管说明（≥5字）' }
      })[this.processDlg.action] || { title: '记录风险动作', confirmText: '确认', reasonLabel: '办理说明（≥5字）' }
    },
    quickQueues() {
      const s = this.stats || {}
      const list = [
        { key: 'ALL', label: '全部', tone: 'neutral', count: this.stats ? Number(s.total ?? this.total) : null },
        { key: 'HIGH', label: '高危 / 危急', tone: 'risk', count: this.stats ? Number(s.highCritical || 0) : null },
        { key: 'OVERDUE', label: '已超时', tone: 'risk', count: this.stats ? Number(s.overdue || 0) : null },
        { key: 'UNASSIGNED', label: '待分派', tone: 'warning', count: this.stats ? Number(s.unassigned || 0) : null },
        { key: 'FOLLOWING', label: '持续跟进', tone: 'neutral', count: null }
      ]
      list.splice(4, 0, { key: 'MINE', label: '我负责的', tone: 'primary', count: null })
      return list
    },
    ruleItems() {
      return [
        { title: '来源去重', desc: '同一学生、同一来源、同一来源单据重复建单由后端拦截。' },
        { title: '心理明细脱敏', desc: '心理来源明细只对授权角色展示，普通角色仅看到脱敏摘要。' },
        { title: '行级动作收口', desc: '页面只展示服务端 allowedActions 允许的动作，不以前端角色猜测。' },
        { title: '超时扫描', desc: '仅授权管理角色可触发，实际分派、升级、通知和审计均由服务端执行。' }
      ]
    }
  },
  watch: {
    '$route.fullPath'() {
      this.applyRouteFilters()
      this.load()
    }
  },
  mounted() {
    this.applyRouteFilters()
    this.load()
    this.consumeRouteIntent()
  },
  methods: {
    clearTaskFilters() {
      this.filters.source = ''
      this.filters.riskLevel = ''
      this.filters.status = ''
      this.clearStudentFilter()
      this.reload()
    },
    canBtn(code) { return canCode(this.ctx, code) },
    consumeRouteIntent() {
      if (this.routeIntentConsumed || this.$route.query?.intent !== 'create') return
      const sid = this.studentFilter?.studentId
      if (!sid || !this.canBtn('studentAffairs.risk.create')) return
      this.routeIntentConsumed = true
      this.createRisk()
    },
    canAction(row, action) {
      return Array.isArray(row && row.allowedActions) && row.allowedActions.includes(action)
    },
    isRowActioning(row, action) {
      return String(this.rowActioning.riskId) === String(row && row.riskId) && this.rowActioning.action === action
    },
    isOtherRowActioning(row, action) {
      return !!this.rowActioning.riskId && !this.isRowActioning(row, action)
    },
    actionCatalog() {
      return {
        ASSIGN: { key: 'ASSIGN', label: '分派', code: 'studentAffairs.risk.assign', run: (r) => this.assign(r) },
        PROCESS: { key: 'PROCESS', label: '记录处置', code: 'studentAffairs.risk.handle', run: (r) => this.process(r, 'PROCESS') },
        FOLLOW: { key: 'FOLLOW', label: '继续跟进', code: 'studentAffairs.risk.handle', run: (r) => this.process(r, 'FOLLOW') },
        TAKEOVER: { key: 'TAKEOVER', label: '上级接管', code: 'studentAffairs.risk.handle', run: (r) => this.process(r, 'TAKEOVER') }
      }
    },
    primaryAction(row) {
      const catalog = this.actionCatalog()
      for (const key of ['ASSIGN', 'PROCESS', 'FOLLOW', 'TAKEOVER']) {
        if (this.canAction(row, key)) return catalog[key]
      }
      return null
    },
    secondaryActions(row) {
      const primary = this.primaryAction(row)
      const catalog = this.actionCatalog()
      return ['ASSIGN', 'PROCESS', 'FOLLOW', 'TAKEOVER']
        .filter((key) => this.canAction(row, key) && (!primary || primary.key !== key))
        .map((key) => catalog[key])
    },
    async claim(row) {
      await this.runRowAction(row, 'CLAIM', () => studentAffairsApi.assignRisk(row.riskId, 'me', row.version))
    },
    applyRouteFilters() {
      const q = this.$route.query || {}
      this.studentFilter = readStudentFilter(q)
      this.filters.studentId = this.studentFilter.studentId || ''
      this.filters.source = q.source ? String(q.source) : this.filters.source
      this.filters.riskLevel = q.riskLevel ? String(q.riskLevel) : this.filters.riskLevel
      if (q.status != null && q.status !== '') {
        const resolved = resolveTodoStatus('risk', q.status)
        this.filters.status = resolved.activeKey === 'CLOSED' ? 'CLOSED'
          : (resolved.activeKey === 'ESCALATED' ? 'ESCALATED'
            : (['PENDING', 'OPEN'].includes(resolved.activeKey) ? resolved.activeKey
              : (resolved.matchStatuses && resolved.matchStatuses.length === 1 ? resolved.matchStatuses[0] : String(q.status))))
      }
    },
    clearStudentFilter() {
      this.studentFilter = { studentId: '', studentNo: '', studentName: '' }
      this.filters.studentId = ''
      const q = { ...this.$route.query }
      delete q.studentId
      delete q.studentNo
      delete q.studentName
      this.$router.replace({ query: q }).catch(() => {})
    },
    onStatusSelect() {
      const q = { ...this.$route.query }
      if (!this.filters.status) delete q.status
      else q.status = this.filters.status
      this.$router.replace({ query: q }).catch(() => {})
      this.reload()
    },
    selectQueue(key) {
      this.activeQueue = this.activeQueue === key && key !== 'ALL' ? 'ALL' : key
      this.scanResult = ''
      this.pagination.page = 1
      this.load()
    },
    queueParams() {
      switch (this.activeQueue) {
        case 'HIGH': return { priority: 'HIGH_CRITICAL' }
        case 'OVERDUE': return { overdueOnly: true }
        case 'UNASSIGNED': return { unassignedOnly: true }
        case 'MINE': return { ownerId: 'me' }
        case 'FOLLOWING': return { status: 'FOLLOWING' }
        default: return {}
      }
    },
    async load({ background = false } = {}) {
      if (!background) this.loading = true
      this.errorMessage = ''
      try {
        const res = await studentAffairsApi.listRiskRecords({
          ...this.filters,
          ...this.queueParams(),
          page: this.pagination.page,
          pageSize: this.pagination.pageSize
        })
        this.risks = res.data.items || []
        this.total = res.data.total || 0
        this.pagination.total = this.total
        this.stats = res.data.stats || null
      } catch (e) {
        this.errorMessage = e.message || '风险数据加载失败'
      } finally {
        if (!background) this.loading = false
      }
    },
    reload() {
      this.scanResult = ''
      this.pagination.page = 1
      this.load()
    },
    onPageChange(page) {
      this.pagination.page = page
      this.load()
    },
    ownerLabel(row) {
      if (!row.ownerId) return '待分派'
      if (row.ownerName) return row.ownerLoginName ? `${row.ownerName} / ${row.ownerLoginName}` : row.ownerName
      return '责任人账号异常'
    },
    goStudent360(row) {
      if (!row?.studentId) return
      this.$router.push({
        path: `/admin/student/${row.studentId}`,
        query: { from: 'risk', riskId: row.riskId || undefined, tab: 'risk' }
      })
    },
    createRisk() {
      const sid = this.studentFilter?.studentId
      this.createDlg = { visible: true, studentId: sid ? String(sid) : '', riskLevel: 'MEDIUM', title: '', detail: '', error: '' }
    },
    async submitCreate() {
      const d = this.createDlg
      if (!d.studentId) { d.error = '请选择学生'; return }
      if (!d.title.trim()) { d.error = '请填写风险标题'; return }
      if (d.detail.trim().length < 5) { d.error = '风险详情不少于 5 字'; return }
      d.error = ''
      const ok = await this.runAction(() => studentAffairsApi.createRiskRecord({
        studentId: d.studentId,
        source: 'MANUAL',
        sourceRefId: `manual-${Date.now()}`,
        riskLevel: d.riskLevel,
        title: d.title.trim(),
        detail: d.detail.trim()
      }))
      if (ok) d.visible = false
    },
    assign(risk) {
      this.assignDlg = { visible: true, riskId: risk.riskId, ownerId: risk.ownerId || '', version: risk.version }
    },
    async submitAssign() {
      const d = this.assignDlg
      if (!d.ownerId) { this.errorMessage = '请选择责任人'; return }
      const ok = await this.runAction(() => studentAffairsApi.assignRisk(d.riskId, d.ownerId, d.version))
      if (ok) d.visible = false
    },
    process(risk, action = 'PROCESS') {
      this.processDlg = { visible: true, riskId: risk.riskId, version: risk.version, action }
    },
    async submitProcess({ reason }) {
      const d = this.processDlg
      const request = {
        PROCESS: () => studentAffairsApi.processRisk(d.riskId, reason, d.version),
        FOLLOW: () => studentAffairsApi.followRisk(d.riskId, reason, d.version),
        TAKEOVER: () => studentAffairsApi.takeoverRisk(d.riskId, reason, d.version)
      }[d.action]
      const ok = await this.runAction(request)
      if (ok) this.processDlg.visible = false
    },
    async scanTimeout() {
      this.actioning = true
      try {
        const res = await studentAffairsApi.scanRiskTimeout()
        this.scanResult = `本次扫描自动分派 ${res.data.assigned || 0} 条，升级 ${res.data.escalated || 0} 条`
        await this.load()
      } catch (e) {
        this.errorMessage = e.message || '风险超时扫描失败'
      } finally {
        this.actioning = false
      }
    },
    async runAction(fn) {
      this.actioning = true
      this.errorMessage = ''
      try {
        await fn()
        await this.load()
        return true
      } catch (e) {
        if (e.bizCode === 'APPROVAL_VERSION_CONFLICT') {
          this.errorMessage = '该记录已被其他人处理，数据已刷新'
          await this.load()
          return false
        }
        this.errorMessage = e.message || '操作失败'
        return false
      } finally {
        this.actioning = false
      }
    },
    async runRowAction(row, action, fn) {
      if (this.rowActioning.riskId) return false
      this.rowActioning = { riskId: String(row.riskId), action }
      this.errorMessage = ''
      try {
        await fn()
        await this.load({ background: true })
        return true
      } catch (e) {
        if (e.bizCode === 'APPROVAL_VERSION_CONFLICT') {
          this.errorMessage = '该记录已被其他人处理，数据已刷新'
          await this.load({ background: true })
          return false
        }
        this.errorMessage = e.message || '操作失败'
        return false
      } finally {
        this.rowActioning = { riskId: '', action: '' }
      }
    },
    sourceLabel(source) {
      return ({
        ACADEMIC_WARNING: '学业预警',
        LEAVE_OVERDUE: '请假异常',
        DORM: '宿舍异常',
        MENTAL: '心理关注',
        MANUAL: '人工建单'
      })[source] || (source ? '来源待确认' : '未设置')
    },
    statusKind(status) {
      if (status === 'CLOSED') return 'success'
      if (status === 'ESCALATED') return 'danger'
      if (['PROCESSING', 'FOLLOWING'].includes(status)) return 'warning'
      return 'info'
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';

.sa-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
.risk-rule-hero,
.risk-hero {
  position: relative;
  overflow: hidden;
  border: 1px solid var(--hero-bd);
  border-radius: var(--radius-xl);
  background: var(--hero-grad);
  box-shadow: var(--hero-shadow);
  color: var(--hero-tx);
}
.risk-rule-hero {
  padding: var(--space-6);
}
.risk-rule-hero > span,
.risk-hero__eyebrow,
.risk-focus__eyebrow {
  color: var(--hero-dim);
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-bold);
  letter-spacing: .08em;
}
.risk-rule-hero h2 {
  margin: var(--space-2) 0;
  font-size: var(--font-size-xl);
}
.risk-rule-hero p {
  max-width: 920px;
  margin: 0;
  color: var(--hero-sub);
  line-height: 1.7;
}
.risk-hero {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(420px, .72fr);
  gap: var(--space-6);
  padding: var(--space-6);
}
.risk-hero::before {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(var(--hero-grid) 1px, transparent 1px),
    linear-gradient(90deg, var(--hero-grid) 1px, transparent 1px);
  background-size: 28px 28px;
  content: '';
  pointer-events: none;
}
.risk-hero__copy,
.risk-hero__metrics {
  position: relative;
  z-index: 1;
}
.risk-hero__copy {
  display: grid;
  align-content: center;
}
.risk-hero__copy h2 {
  max-width: 920px;
  margin: var(--space-2) 0;
  font-size: var(--font-size-2xl);
  line-height: 1.45;
}
.risk-hero__copy p {
  margin: 0;
  color: var(--hero-sub);
  line-height: 1.7;
}
.risk-hero__metrics {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-2);
}
.risk-hero-metric {
  display: grid;
  align-content: center;
  min-height: 92px;
  padding: var(--space-3);
  border: 1px solid var(--hero-chip-bd);
  border-radius: var(--radius-lg);
  background: var(--hero-chip-bg);
}
.risk-hero-metric span,
.risk-hero-metric small {
  color: var(--hero-sub);
  font-size: var(--font-size-xs);
}
.risk-hero-metric strong {
  margin: 2px 0;
  color: var(--hero-tx);
  font-size: var(--font-size-metric);
  font-variant-numeric: tabular-nums;
}
.risk-hero-metric strong.is-alert {
  color: var(--hero-warn);
}
.risk-hero-metric strong.is-gap {
  font-size: var(--font-size-sm);
  letter-spacing: .04em;
}
.risk-gap,
.risk-truthbar {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  border: 1px solid var(--primary-100);
  border-radius: var(--radius-lg);
  background: var(--bg-card);
}
.risk-gap > span,
.risk-truthbar__mark {
  display: grid;
  place-items: center;
  width: 28px;
  height: 28px;
  border-radius: var(--radius-base);
  background: var(--primary-50);
  color: var(--primary-700);
  font-weight: var(--font-weight-bold);
}
.risk-gap p,
.risk-truthbar p {
  margin: 2px 0 0;
  color: var(--text-secondary);
  font-size: var(--font-size-xs);
  line-height: 1.65;
}
.risk-gap button,
.risk-empty button {
  border: 0;
  background: transparent;
  color: var(--primary-700);
  font-weight: var(--font-weight-semibold);
  cursor: pointer;
}
.risk-loop {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: var(--space-2);
  margin: 0;
  padding: 0;
  list-style: none;
}
.risk-loop li {
  position: relative;
  display: grid;
  justify-items: center;
  gap: 3px;
  min-height: 86px;
  padding: var(--space-3);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-lg);
  background: var(--bg-section);
  text-align: center;
}
.risk-loop li > span {
  display: grid;
  place-items: center;
  width: 24px;
  height: 24px;
  border-radius: var(--radius-full);
  background: var(--primary-100);
  color: var(--primary-700);
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-bold);
}
.risk-loop li strong {
  color: var(--text-primary);
  font-size: var(--font-size-sm);
}
.risk-loop li small {
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
}
.risk-loop li.is-current {
  border-color: var(--primary-500);
  background: var(--primary-50);
}
.risk-loop li.is-current > span {
  background: var(--primary-600);
  color: var(--text-inverse);
}
.risk-focus {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: var(--space-5);
  padding: var(--space-5);
  border: 1px solid var(--danger-100);
  border-radius: var(--radius-xl);
  background: var(--bg-card);
  box-shadow: var(--shadow-card);
}
.risk-focus__eyebrow {
  color: var(--danger-600);
}
.risk-focus__title-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin: var(--space-1) 0;
}
.risk-focus h3,
.risk-focus p,
.risk-focus small {
  margin: 0;
}
.risk-focus h3 {
  color: var(--text-primary);
  font-size: var(--font-size-xl);
}
.risk-focus p {
  color: var(--text-secondary);
  line-height: 1.65;
}
.risk-focus small {
  color: var(--text-tertiary);
}
.risk-focus__actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: var(--space-2);
}
.sa-toolbar,
.sa-queues {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}
.sa-queues {
  margin-bottom: var(--space-4);
  padding-bottom: var(--space-3);
  border-bottom: 1px solid var(--border-light);
}
.sa-toolbar {
  margin-bottom: var(--space-4);
}
.sa-queue {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  min-height: 34px;
  padding: 0 var(--space-3);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-full);
  background: var(--bg-card);
  color: var(--text-secondary);
  font: inherit;
  font-size: var(--font-size-sm);
  cursor: pointer;
}
.sa-queue:hover,
.sa-queue.is-on {
  border-color: var(--queue-accent, var(--primary-500));
  background: var(--queue-soft, var(--primary-50));
  color: var(--queue-strong, var(--primary-700));
}
.sa-queue.is-on {
  font-weight: var(--font-weight-semibold);
}
.sa-queue__dot {
  width: 7px;
  height: 7px;
  border-radius: var(--radius-full);
  background: var(--queue-accent, var(--text-tertiary));
}
.sa-queue__count {
  min-width: 20px;
  padding: 1px 6px;
  border-radius: var(--radius-full);
  background: var(--bg-section);
  font-size: var(--font-size-xs);
  font-variant-numeric: tabular-nums;
  text-align: center;
}
.sa-queue.is-on .sa-queue__count {
  background: var(--queue-accent, var(--primary-600));
  color: var(--text-inverse);
}
.sa-queue.is-risk {
  --queue-accent: var(--danger-600);
  --queue-soft: var(--danger-50);
  --queue-strong: var(--danger-700);
}
.sa-queue.is-warning {
  --queue-accent: var(--warning-600);
  --queue-soft: var(--warning-50);
  --queue-strong: var(--warning-700);
}
.sa-queue.is-primary {
  --queue-accent: var(--primary-600);
  --queue-soft: var(--primary-50);
  --queue-strong: var(--primary-700);
}
.sa-queue.is-neutral {
  --queue-accent: var(--text-tertiary);
  --queue-soft: var(--bg-section);
  --queue-strong: var(--text-primary);
}
.sa-queue.is-empty:not(.is-on) {
  opacity: .58;
}
.sa-student-filter {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  margin-bottom: var(--space-3);
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--warning-100);
  border-radius: var(--radius-md);
  background: var(--warning-50);
  color: var(--text-primary);
  font-size: var(--font-size-sm);
}
.sa-filter {
  width: 154px;
}
.sa-scan {
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--warning-100);
  border-radius: var(--radius-base);
  background: var(--warning-50);
  color: var(--warning-700);
}
.risk-student-link {
  display: grid;
  gap: 2px;
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--text-primary);
  text-align: left;
  cursor: pointer;
}
.risk-student-link span {
  font-weight: var(--font-weight-semibold);
}
.risk-student-link small {
  color: var(--text-tertiary);
}
.sa-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 7px;
  min-width: 240px;
}
.sa-actions__recommended {
  position: relative;
  display: inline-flex;
  padding-top: 12px;
}
.sa-actions__hint {
  position: absolute;
  top: -2px;
  left: 9px;
  z-index: 1;
  padding: 0 5px;
  border-radius: var(--radius-full);
  background: var(--primary-50);
  color: var(--primary-700);
  font-size: 9px;
  font-weight: var(--font-weight-bold);
  line-height: 15px;
  letter-spacing: .08em;
  white-space: nowrap;
}
.sa-actions__primary :deep(.app-button) {
  min-width: 96px;
  border-radius: var(--radius-lg);
  box-shadow: var(--btn-p-shadow);
}
.sa-actions__arrow {
  margin-left: 2px;
  transition: transform .16s ease;
}
.sa-actions__primary:hover .sa-actions__arrow {
  transform: translateX(2px);
}
.sa-actions__claim :deep(.app-button) {
  border-color: var(--primary-100);
  background: var(--primary-50);
  color: var(--primary-700);
  font-weight: var(--font-weight-semibold);
}
.sa-actions__claim-dot {
  width: 6px;
  height: 6px;
  border-radius: var(--radius-full);
  background: var(--primary-500);
}
.sa-actions__secondary {
  display: inline-flex;
  align-items: center;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 3px;
}
.sa-actions__detail :deep(.app-button) {
  color: var(--text-tertiary);
}
.risk-empty {
  display: grid;
  justify-items: center;
  gap: var(--space-2);
  padding: var(--space-8);
  text-align: center;
}
.risk-empty > span {
  display: grid;
  place-items: center;
  width: 42px;
  height: 42px;
  border-radius: var(--radius-full);
  background: var(--success-50);
  color: var(--success-700);
  font-size: var(--font-size-xl);
}
.risk-empty strong {
  color: var(--text-primary);
}
.risk-empty p {
  max-width: 560px;
  margin: 0;
  color: var(--text-tertiary);
  line-height: 1.65;
}
.sa-rules {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-3);
}
.sa-rule {
  padding: var(--space-4);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-lg);
  background: var(--bg-section);
}
.sa-rule span {
  display: block;
  margin-top: 2px;
  color: var(--text-tertiary);
  line-height: 1.65;
}
@media (max-width: 1180px) {
  .risk-hero {
    grid-template-columns: 1fr;
  }
  .risk-loop {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}
@media (max-width: 820px) {
  .risk-hero__metrics,
  .sa-rules {
    grid-template-columns: 1fr 1fr;
  }
  .risk-focus,
  .risk-gap,
  .risk-truthbar {
    grid-template-columns: 1fr;
  }
  .risk-focus__actions {
    justify-content: flex-start;
  }
}
@media (max-width: 620px) {
  .risk-hero__metrics,
  .risk-loop,
  .sa-rules {
    grid-template-columns: 1fr;
  }
  .sa-filter {
    width: 100%;
  }
}
</style>
