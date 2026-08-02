<template>
  <AppPageShell
    title="风险预警"
    subtitle="聚合学业、请假、宿舍、心理等来源的风险记录，PC 端负责分派、处置、升级和闭环入口。"
    role-name="学工角色"
    data-scope-name="学工数据范围"
    watermark-purpose="学工风险预警查看"
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
      <AppPermissionButton :allowed="canBtn('studentAffairs.risk.create')" code="studentAffairs.risk.create" :loading="actioning" @click="createRisk">
        新建风险
      </AppPermissionButton>
    </template>

    <AppGlobalState
      :state="pageState"
      :description="errorMessage"
      loading-text="正在加载学工风险预警数据..."
      @retry="load"
      @back="$router.push('/admin/student-affairs/dashboard')"
    >
      <TaskContextBar
        :role-name="roleName"
        :scope-name="scopeName"
        :pending="pendingCount"
        :overdue="stats && stats.overdue"
        :filter-summary="taskFilterSummary"
        next-hint="优先分派或处置超时、高危风险记录。"
        :degraded="!!errorMessage"
        @clear-filter="clearTaskFilters"
      />
      <div class="sa-grid sa-grid--metrics">
        <AppMetricCard v-for="card in metricCards" :key="card.key" :title="card.label" :value="card.value" :accent="card.accent" />
      </div>

      <AppSectionCard v-if="isRulePanel" title="风险规则摘要">
        <div class="sa-rules">
          <div v-for="rule in ruleItems" :key="rule.title" class="sa-rule">
            <strong>{{ rule.title }}</strong>
            <span>{{ rule.desc }}</span>
          </div>
        </div>
      </AppSectionCard>

      <AppSectionCard v-else title="风险学生与处置">
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
            <div class="mp-cell-main">{{ row.realName || '未命名学生' }}</div>
            <div class="mp-cell-sub">{{ row.studentNo || row.studentId }}</div>
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
            <div class="sa-actions">
              <AppPermissionButton :allowed="canBtn('studentAffairs.risk.view')" code="studentAffairs.risk.view" size="sm" variant="secondary" @click="$router.push(`/admin/student-affairs/risk/${row.riskId}`)">
                详情
              </AppPermissionButton>
              <AppPermissionButton :allowed="canBtn('studentAffairs.risk.assign')" code="studentAffairs.risk.assign" size="sm" variant="secondary" :loading="actioning" @click="assign(row)">
                分派
              </AppPermissionButton>
              <AppPermissionButton :allowed="canBtn('studentAffairs.risk.handle')" code="studentAffairs.risk.handle" size="sm" :loading="actioning" @click="process(row)">
                处置
              </AppPermissionButton>
            </div>
          </template>
        </DataTable>
        <p v-else class="sa-empty">当前范围内暂无风险记录</p>
      </AppSectionCard>
    </AppGlobalState>

    <AppDrawer :visible="createDlg.visible" title="新建风险记录" mode="modal" size="medium" @close="createDlg.visible = false">
      <div class="sa-form">
        <AppFormItem label="学生" required>
          <AppStudentPicker v-model="createDlg.studentId"
                            placeholder="按姓名 / 学号搜索" :disabled="actioning" />
        </AppFormItem>
        <AppFormItem label="风险等级" required>
          <AppSelect v-model="createDlg.riskLevel" :options="RISK_LEVELS" :disabled="actioning" />
        </AppFormItem>
        <AppFormItem label="风险标题" required>
          <AppTextInput v-model="createDlg.title" placeholder="一句话概括，如：连续两周未到课" :disabled="actioning" />
        </AppFormItem>
        <AppFormItem label="风险详情" required hint="写清时间、表现、已了解到的情况，供责任人接手">
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
      v-model:visible="assignDlg.visible" title="分派责任人" type="primary" confirm-text="确认分派"
      :submitting="actioning" @confirm="submitAssign"
    >
      <AppFormItem label="责任人" required>
        <AppRiskOwnerPicker v-model="assignDlg.ownerId"
                          placeholder="按姓名 / 工号搜索"
                          data-scope-hint="仅可选持学工风险处置角色的在职账号" />
      </AppFormItem>
    </AppConfirmDialog>

    <AppConfirmDialog
      v-model:visible="processDlg.visible" title="记录处置" type="primary" confirm-text="确认处置"
      require-reason reason-label="处置内容（≥5字）" phrase-scene-key="sa.risk.handle"
      :submitting="actioning" @confirm="submitProcess"
    />
  </AppPageShell>
</template>

<script>
import {
  AppConfirmDialog,
  AppFormItem,
  AppGlobalState,
  AppInlineAlert,
  AppMetricCard,
  AppPageShell,
  AppPermissionButton,
  AppRiskTag,
  AppSectionCard,
  AppSelect,
  AppStatusTag,
  AppStudentPicker,
  AppRiskOwnerPicker,
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
  { key: 'actions', title: '操作', align: 'right', width: '220px' }
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
    AppMetricCard,
    AppPageShell,
    AppPermissionButton,
    AppRiskTag,
    AppSelect,
    AppStudentPicker,
    AppRiskOwnerPicker,
    AppTextInput,
    AppTextarea,
    AppSectionCard,
    AppStatusTag,
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
      errorMessage: '',
      risks: [],
      total: 0,
      stats: null,
      pagination: { page: 1, pageSize: 20, total: 0 },
      scanResult: '',
      createDlg: { visible: false, studentId: '', riskLevel: 'MEDIUM', title: '', detail: '', error: '' },
      assignDlg: { visible: false, riskId: '', ownerId: '', version: null },
      processDlg: { visible: false, riskId: '', version: null },
      filters: {
        source: '',
        riskLevel: '',
        status: '',
        studentId: ''
      },
      studentFilter: { studentId: '', studentNo: '', studentName: '' }
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
      if (this.filters.source) parts.push(`来源：${this.filters.source}`)
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
      if ((!name || !no) && id && this.risks && this.risks.length) {
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
      if (this.loading) return 'loading'
      if (this.errorMessage) return 'error'
      return 'ready'
    },
    canScanTimeout() {
      const role = (this.ctx?.currentRoleCode || this.ctx?.currentRole?.roleCode || '').toUpperCase()
      return SCAN_ROLES.has(role) && this.canBtn('studentAffairs.risk.handle')
    },
    metricCards() {
      const s = this.stats || {}
      const high = Number(s.highCritical || 0)
      const open = Number(s.open || 0)
      const unassigned = Number(s.unassigned || 0)
      const overdue = Number(s.overdue || 0)
      return [
        { key: 'total', label: '风险记录', value: Number(s.total ?? this.total), accent: 'primary' },
        { key: 'high', label: '高危/危急', value: high, accent: high ? 'risk' : 'success' },
        { key: 'open', label: '未闭环', value: open, accent: open ? 'warning' : 'success' },
        { key: 'unassigned', label: '待分派', value: unassigned, accent: unassigned ? 'warning' : 'success' },
        { key: 'overdue', label: '超时', value: overdue, accent: overdue ? 'risk' : 'success' }
      ]
    },
    ruleItems() {
      return [
        { title: '来源去重', desc: '同一学生、同一来源、同一来源单据重复建单由后端拦截。' },
        { title: '心理明细脱敏', desc: '心理来源明细只对授权角色展示，普通辅导员只看到脱敏摘要。' },
        { title: '处置后关闭', desc: '风险关闭前必须存在处置记录，关闭后写入学生成长时间线。' },
        { title: '超时扫描', desc: '可由学工管理员手动触发自动分派与升级；接口幂等。' }
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
    applyRouteFilters() {
      const q = this.$route.query || {}
      this.studentFilter = readStudentFilter(q)
      this.filters.studentId = this.studentFilter.studentId || ''
      this.filters.source = q.source ? String(q.source) : this.filters.source
      this.filters.riskLevel = q.riskLevel ? String(q.riskLevel) : this.filters.riskLevel
      if (q.status != null && q.status !== '') {
        const resolved = resolveTodoStatus('risk', q.status)
        // PENDING/OPEN/DONE/OVERDUE 等公共语义：下拉用 activeKey；后端 OPEN/PENDING 已识别
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
    async load() {
      this.loading = true
      this.errorMessage = ''
      try {
        const res = await studentAffairsApi.listRiskRecords({
          ...this.filters,
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
        this.loading = false
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
      if (row.ownerName) {
        return row.ownerLoginName
          ? `${row.ownerName} / ${row.ownerLoginName}`
          : row.ownerName
      }
      return '责任人账号异常'
    },
    createRisk() {
      this.createDlg = { visible: true, studentId: '', riskLevel: 'MEDIUM', title: '', detail: '', error: '' }
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
      this.assignDlg = {
        visible: true,
        riskId: risk.riskId,
        ownerId: risk.ownerId || '',
        version: risk.version
      }
    },
    async submitAssign() {
      const d = this.assignDlg
      if (!d.ownerId) { this.errorMessage = '请选择责任人'; return }
      const ok = await this.runAction(() => studentAffairsApi.assignRisk(d.riskId, d.ownerId, d.version))
      if (ok) d.visible = false
    },
    process(risk) {
      this.processDlg = { visible: true, riskId: risk.riskId, version: risk.version }
    },
    async submitProcess({ reason }) {
      const ok = await this.runAction(() => studentAffairsApi.processRisk(
        this.processDlg.riskId, reason, this.processDlg.version))
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
    sourceLabel(source) {
      return ({
        ACADEMIC_WARNING: '学业预警',
        LEAVE_OVERDUE: '请假异常',
        DORM: '宿舍异常',
        MENTAL: '心理关注',
        MANUAL: '人工建单'
      })[source] || source || '未设置'
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
.sa-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
.sa-grid--metrics {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: var(--space-4);
  margin-bottom: var(--space-4);
}
.sa-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3);
  margin-bottom: var(--space-4);
}
.sa-student-filter {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  margin-bottom: var(--space-3);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-md);
  background: var(--warning-50, #fffbeb);
  border: 1px solid var(--warning-200, #fde68a);
  font-size: var(--font-size-sm);
  color: var(--text-primary);
}
.sa-filter {
  width: 150px;
}
.sa-scan {
  color: var(--warning-700);
  background: var(--warning-50);
  border: 1px solid var(--warning-200);
  border-radius: var(--radius-base);
  padding: var(--space-2) var(--space-3);
}
.sa-rule span {
  display: block;
  color: var(--text-tertiary);
  margin-top: 2px;
}
.sa-actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}
.sa-empty {
  color: var(--text-tertiary);
  padding: var(--space-4);
  text-align: center;
}
.sa-rules {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-3);
}
.sa-rule {
  border: 1px solid var(--border-light);
  border-radius: var(--radius-base);
  padding: var(--space-4);
}
@media (max-width: 960px) {
  .sa-grid--metrics,
  .sa-rules {
    grid-template-columns: 1fr;
  }
}
@import '@/styles/module-page.css';
</style>
