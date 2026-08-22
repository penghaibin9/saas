<template>
  <section class="aeiw" aria-label="考场异常处置工作区">
    <div class="aeiw-head">
      <div>
        <div class="aeiw-title">异常处置</div>
        <div class="aeiw-subtitle">原始异常事实保留；HANDOFF / CLOSE / VOID 形成正式处置证据，成功后重新读取服务端。</div>
      </div>
      <AppButton size="small" variant="ghost" :loading="loading" @click="load">刷新服务端状态</AppButton>
    </div>

    <div class="aeiw-kpis">
      <button type="button" :class="['aeiw-kpi', { 'is-active': view === 'OPEN' }]" @click="setView('OPEN')">
        <span>待处置</span><strong>{{ summary.openCount }}</strong>
      </button>
      <button type="button" :class="['aeiw-kpi', { 'is-active': view === 'CLOSED' }]" @click="setView('CLOSED')">
        <span>已闭环</span><strong>{{ summary.closedCount }}</strong>
      </button>
      <button type="button" :class="['aeiw-kpi', { 'is-active': view === 'VOIDED' }]" @click="setView('VOIDED')">
        <span>已作废</span><strong>{{ summary.voidedCount }}</strong>
      </button>
      <button type="button" :class="['aeiw-kpi', { 'is-active': view === 'ALL' }]" @click="setView('ALL')">
        <span>全部</span><strong>{{ summary.openCount + summary.closedCount + summary.voidedCount }}</strong>
      </button>
    </div>

    <div class="aeiw-filters">
      <label class="aeiw-field compact">
        <span>异常类型</span>
        <select v-model="filters.incidentType" :disabled="loading">
          <option value="">全部类型</option>
          <option value="ABSENT">缺考</option>
          <option value="DISCIPLINE_VIOLATION">违纪</option>
          <option value="OTHER">其他</option>
        </select>
      </label>
      <label class="aeiw-field keyword">
        <span>学生 / 课程 / 考场</span>
        <input v-model.trim="filters.keyword" :disabled="loading" placeholder="学号、姓名、课程或考场" @keyup.enter="applyFilters" />
      </label>
      <label class="aeiw-field compact">
        <span>考试日期</span>
        <input v-model="filters.examDate" type="date" :disabled="loading" />
      </label>
      <div class="aeiw-filter-actions">
        <AppButton size="small" variant="primary" :disabled="loading" @click="applyFilters">查询</AppButton>
        <AppButton size="small" variant="ghost" :disabled="loading" @click="resetFilters">清空</AppButton>
      </div>
    </div>

    <AppInlineAlert
      v-if="!canResolve"
      type="info"
      description="当前身份仅可查看考务异常；处置按钮由 academicAffairs.exam.recordAbnormal 权限控制，后端仍会再次校验权限与数据范围。"
    />
    <AppInlineAlert
      v-else-if="batch.status === 'ARCHIVED'"
      type="info"
      description="该考试批次已归档，异常历史永久只读，不允许再 HANDOFF / CLOSE / VOID。"
    />

    <LoadingState v-if="loading && !loadedOnce" />
    <ErrorState v-else-if="error" title="异常工作台加载失败" :description="error" @retry="load" />
    <EmptyState v-else-if="!rows.length" title="当前筛选无异常" description="可切换状态或清空筛选条件" />
    <DataTable
      v-else
      :columns="columns"
      :rows="rows"
      row-key="incidentId"
      :pagination="pagination"
      @page-change="onPageChange"
    >
      <template #cell-student="{ row }">
        <div class="mp-cell-main">{{ row.studentName || '—' }}</div>
        <div class="mp-cell-sub">{{ row.studentNo || '无学号' }}</div>
      </template>
      <template #cell-exam="{ row }">
        <div class="mp-cell-main">{{ row.courseName || '—' }}</div>
        <div class="mp-cell-sub">{{ row.examDate || '—' }} {{ row.startTime || '' }} · {{ row.classroom || '未标考场' }}</div>
      </template>
      <template #cell-type="{ row }">
        <StatusTag :type="incidentTypeTag(row.incidentType)" :label="incidentTypeLabel(row.incidentType)" dot />
      </template>
      <template #cell-record="{ row }">
        <div>{{ row.recordedBy || '—' }}</div>
        <div class="mp-cell-sub">{{ formatTime(row.recordedAt) }}</div>
      </template>
      <template #cell-closure="{ row }">
        <StatusTag :type="closureType(row.closureStatus)" :label="closureLabel(row.closureStatus)" dot />
        <div v-if="row.resolutionAction" class="mp-cell-sub">{{ actionLabel(row.resolutionAction) }} · {{ formatTime(row.resolvedAt) }}</div>
      </template>
      <template #cell-case="{ row }">
        <span v-if="row.disciplineCaseRef" class="aeiw-mono">{{ row.disciplineCaseRef }}</span>
        <span v-else>—</span>
      </template>
      <template #cell-actions="{ row }">
        <AppButton size="small" variant="ghost" @click="openDetail(row)">详情 / 处置</AppButton>
      </template>
    </DataTable>

    <AppDrawer
      :visible="detailVisible"
      title="考场异常详情 / 正式处置"
      mode="modal"
      size="large"
      @close="closeDetail"
    >
      <template v-if="detail">
        <div class="aeiw-detail-head">
          <div>
            <strong>{{ detail.studentName || '—' }} · {{ detail.studentNo || '无学号' }}</strong>
            <div class="aeiw-muted">{{ detail.courseName || '—' }} · {{ detail.classroom || '未标考场' }} · {{ detail.examDate || '—' }} {{ detail.startTime || '' }}</div>
          </div>
          <StatusTag :type="closureType(detail.closureStatus)" :label="closureLabel(detail.closureStatus)" dot />
        </div>

        <div class="aeiw-detail-grid">
          <div><span>异常类型</span><strong>{{ incidentTypeLabel(detail.incidentType) }}</strong></div>
          <div><span>登记人</span><strong>{{ detail.recordedBy || '—' }}</strong></div>
          <div><span>登记时间</span><strong>{{ formatTime(detail.recordedAt) }}</strong></div>
          <div><span>风险联动</span><strong>{{ detail.riskAlertSent ? '已送达' : '未完成' }}</strong></div>
        </div>

        <div class="aeiw-block">
          <span>异常事实描述</span>
          <p>{{ detail.description || '未填写' }}</p>
        </div>

        <template v-if="detail.closureStatus !== 'OPEN'">
          <div class="aeiw-section-title">正式处置证据</div>
          <div class="aeiw-detail-grid">
            <div><span>动作</span><strong>{{ actionLabel(detail.resolutionAction) }}</strong></div>
            <div><span>处置人</span><strong>{{ detail.resolvedBy || '—' }}</strong></div>
            <div><span>处置时间</span><strong>{{ formatTime(detail.resolvedAt) }}</strong></div>
            <div><span>处分/后续线索</span><strong class="aeiw-mono">{{ detail.disciplineCaseRef || '—' }}</strong></div>
          </div>
          <div class="aeiw-block">
            <span>处置原因</span>
            <p>{{ detail.resolutionReason || '—' }}</p>
          </div>
          <AppInlineAlert
            :type="detail.closureEvidenceConsistent ? 'success' : 'danger'"
            :description="detail.closureEvidenceConsistent ? '处置审计与当前正式事实一致。' : '处置审计与当前事实不一致，禁止继续写入，请联系系统管理员核查。'"
          />
        </template>

        <template v-else>
          <AppInlineAlert
            v-if="detail.incidentType === 'ABSENT' && detail.riskAlertSent"
            type="info"
            description="风险通知已送达，但这不等于考务正式关闭；仍需有权限的第二步 CLOSE 形成处置事实。"
          />
          <label v-if="detail.incidentType !== 'ABSENT' && canWriteCurrent" class="aeiw-field handoff-ref">
            <span>处分 / 后续处理线索编号（HANDOFF 必填）</span>
            <input v-model.trim="disciplineCaseRef" :disabled="busy" maxlength="100" placeholder="如 DISC-2026-000123" />
          </label>
        </template>
      </template>

      <template #footer>
        <AppButton variant="ghost" :disabled="busy" @click="closeDetail">关闭</AppButton>
        <template v-if="detail?.closureStatus === 'OPEN' && canWriteCurrent">
          <AppButton
            v-if="detail.incidentType !== 'ABSENT'"
            variant="ghost"
            :disabled="busy || disciplineCaseRef.length < 3"
            @click="openDecision('HANDOFF')"
          >移交处理线索</AppButton>
          <AppButton
            v-if="detail.incidentType === 'ABSENT'"
            variant="primary"
            :disabled="busy || !detail.riskAlertSent"
            @click="openDecision('CLOSE')"
          >确认关闭</AppButton>
          <AppButton variant="danger" :disabled="busy" @click="openDecision('VOID')">作废误登记</AppButton>
        </template>
      </template>
    </AppDrawer>

    <AppConfirmDialog
      v-model:visible="decisionVisible"
      :title="decisionTitle"
      :message="decisionMessage"
      :type="pendingAction === 'VOID' ? 'danger' : 'warning'"
      :confirm-text="decisionConfirmText"
      :require-reason="true"
      reason-label="处置原因"
      reason-placeholder="至少 5 个字，说明处置依据；该原因将进入正式审计"
      :reason-min-length="5"
      :submitting="busy"
      @confirm="submitDecision"
      @cancel="pendingAction = ''"
    />
  </section>
</template>

<script>
import { DataTable, StatusTag, LoadingState, EmptyState, ErrorState } from '@/components/business'
import { AppButton, AppDrawer } from '@/components/ui'
import { AppConfirmDialog, AppInlineAlert } from '@/components/common'
import { matchPermission } from '@/config/navPlan.js'
import { academicExamIncidentApi } from '@/modules/academicAffairs/api/academic-exam-incident.api'
import { getPermissionPatterns } from '@/security/permissionGate.js'
import { toast } from '@/utils/toast'

const TYPE_LABEL = {
  ABSENT: '缺考',
  DISCIPLINE: '违纪',
  DISCIPLINE_VIOLATION: '违纪',
  CHEAT: '违纪',
  OTHER: '其他'
}
const CLOSURE_LABEL = {
  OPEN: '待处置',
  CASE_LINKED: '已移交',
  RISK_TRANSFERRED: '已关闭',
  VOIDED: '已作废'
}

export default {
  name: 'AaExamIncidentWorkbench',
  components: { DataTable, StatusTag, LoadingState, EmptyState, ErrorState, AppButton, AppDrawer, AppConfirmDialog, AppInlineAlert },
  props: {
    batch: { type: Object, required: true }
  },
  data() {
    return {
      loading: false,
      loadedOnce: false,
      error: '',
      rows: [],
      summary: { openCount: 0, closedCount: 0, voidedCount: 0 },
      view: 'ALL',
      filters: { incidentType: '', keyword: '', examDate: '' },
      appliedFilters: { incidentType: '', keyword: '', examDate: '' },
      pagination: { page: 1, pageSize: 20, total: 0 },
      detailVisible: false,
      detail: null,
      disciplineCaseRef: '',
      pendingAction: '',
      decisionVisible: false,
      busy: false,
      columns: [
        { key: 'student', title: '学生' },
        { key: 'exam', title: '考试 / 考场' },
        { key: 'type', title: '异常类型' },
        { key: 'record', title: '登记' },
        { key: 'closure', title: '闭环状态' },
        { key: 'case', title: '后续线索' },
        { key: 'actions', title: '操作' }
      ]
    }
  },
  computed: {
    batchId() { return this.batch?.batchId },
    canResolve() {
      const patterns = getPermissionPatterns()
      return Array.isArray(patterns) && matchPermission(patterns, 'academicAffairs.exam.recordAbnormal')
    },
    canWriteCurrent() {
      return this.canResolve && ['PUBLISHED', 'FINISHED'].includes(String(this.batch?.status || '').toUpperCase())
    },
    decisionTitle() {
      if (this.pendingAction === 'HANDOFF') return '确认移交异常线索'
      if (this.pendingAction === 'CLOSE') return '确认正式关闭缺考异常'
      return '确认作废异常登记'
    },
    decisionConfirmText() {
      if (this.pendingAction === 'HANDOFF') return '确认移交'
      if (this.pendingAction === 'CLOSE') return '确认关闭'
      return '确认作废'
    },
    decisionMessage() {
      if (this.pendingAction === 'HANDOFF') return `线索编号 ${this.disciplineCaseRef || '未填写'} 将与该异常正式关联；学工处分状态机仍由学工中心负责。`
      if (this.pendingAction === 'CLOSE') return '仅在缺考风险联动已经成功后关闭；关闭后不能改成 HANDOFF 或 VOID。'
      return '作废只追加 VOID 处置事实并保留原异常记录，不会物理删除历史。'
    }
  },
  watch: {
    batchId: {
      immediate: true,
      handler() {
        this.view = 'ALL'
        this.pagination.page = 1
        this.filters = { incidentType: '', keyword: '', examDate: '' }
        this.appliedFilters = { incidentType: '', keyword: '', examDate: '' }
        this.closeDetail()
        this.load()
      }
    }
  },
  methods: {
    incidentTypeLabel(value) { return TYPE_LABEL[String(value || '').toUpperCase()] || value || '其他' },
    incidentTypeTag(value) { return String(value || '').toUpperCase() === 'ABSENT' ? 'warning' : 'danger' },
    closureLabel(value) { return CLOSURE_LABEL[value] || value || '未知' },
    closureType(value) {
      if (value === 'OPEN') return 'warning'
      if (value === 'VOIDED') return 'default'
      return 'success'
    },
    actionLabel(value) {
      if (value === 'HANDOFF') return '移交'
      if (value === 'CLOSE') return '关闭'
      if (value === 'VOID') return '作废'
      return value || '—'
    },
    formatTime(value) {
      if (!value) return '—'
      const date = new Date(value)
      return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString('zh-CN', { hour12: false })
    },
    async load() {
      if (!this.batchId || this.loading) return
      this.loading = true
      this.error = ''
      try {
        const data = await academicExamIncidentApi.workbench({
          batchId: this.batchId,
          view: this.view,
          page: this.pagination.page,
          pageSize: this.pagination.pageSize,
          incidentType: this.appliedFilters.incidentType || undefined,
          keyword: this.appliedFilters.keyword || undefined,
          examDate: this.appliedFilters.examDate || undefined
        })
        this.rows = Array.isArray(data.items) ? data.items : []
        this.pagination.total = Number(data.total || 0)
        this.summary = {
          openCount: Number(data.openCount || 0),
          closedCount: Number(data.closedCount || 0),
          voidedCount: Number(data.voidedCount || 0)
        }
      } catch (error) {
        this.rows = []
        this.pagination.total = 0
        this.error = error?.message || '异常工作台加载失败'
      } finally {
        this.loading = false
        this.loadedOnce = true
      }
    },
    setView(value) {
      if (this.view === value) return
      this.view = value
      this.pagination.page = 1
      this.closeDetail()
      this.load()
    },
    applyFilters() {
      this.appliedFilters = { ...this.filters }
      this.pagination.page = 1
      this.closeDetail()
      this.load()
    },
    resetFilters() {
      this.filters = { incidentType: '', keyword: '', examDate: '' }
      this.appliedFilters = { ...this.filters }
      this.pagination.page = 1
      this.closeDetail()
      this.load()
    },
    onPageChange(page) {
      this.pagination.page = Number(page || 1)
      this.closeDetail()
      this.load()
    },
    openDetail(row) {
      this.detail = { ...row }
      this.disciplineCaseRef = row.disciplineCaseRef || ''
      this.detailVisible = true
    },
    closeDetail() {
      if (this.busy) return
      this.detailVisible = false
      this.detail = null
      this.disciplineCaseRef = ''
      this.pendingAction = ''
      this.decisionVisible = false
    },
    openDecision(action) {
      if (!this.detail || this.detail.closureStatus !== 'OPEN' || !this.canWriteCurrent) return
      if (action === 'HANDOFF' && this.disciplineCaseRef.length < 3) {
        toast.error('请先填写处分 / 后续处理线索编号')
        return
      }
      this.pendingAction = action
      this.decisionVisible = true
    },
    async submitDecision({ reason }) {
      if (!this.detail || !this.pendingAction || this.busy) return
      const incidentId = this.detail.incidentId
      const action = this.pendingAction
      this.busy = true
      try {
        await academicExamIncidentApi.resolve(incidentId, {
          action,
          reason,
          disciplineCaseRef: action === 'HANDOFF' ? this.disciplineCaseRef : undefined
        })
        this.decisionVisible = false
        this.pendingAction = ''
        this.detailVisible = false
        this.detail = null
        toast.success(action === 'HANDOFF' ? '异常已正式移交' : action === 'CLOSE' ? '缺考异常已正式关闭' : '误登记已正式作废')
        await this.load()
      } catch (error) {
        toast.error(error?.message || '异常处置失败，请刷新后重试')
        this.decisionVisible = false
        this.pendingAction = ''
        this.detailVisible = false
        this.detail = null
        await this.load()
      } finally {
        this.busy = false
      }
    }
  }
}
</script>

<style scoped>
.aeiw { margin-top: 18px; min-width: 0; }
.aeiw-head { display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; margin-bottom: 10px; }
.aeiw-title { font-size: 15px; font-weight: 650; }
.aeiw-subtitle, .aeiw-muted { color: var(--text-secondary, #64748b); font-size: 12px; margin-top: 3px; line-height: 1.55; }
.aeiw-kpis { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; margin: 10px 0; }
.aeiw-kpi { text-align: left; border: 1px solid var(--border-color, #e5e7eb); border-radius: 9px; padding: 10px 12px; background: var(--surface-color, #fff); cursor: pointer; color: inherit; }
.aeiw-kpi.is-active { border-color: var(--primary-color, #2563eb); background: var(--primary-bg, #eff6ff); }
.aeiw-kpi span { display: block; color: var(--text-secondary, #64748b); font-size: 12px; }
.aeiw-kpi strong { display: block; margin-top: 3px; font-size: 20px; }
.aeiw-filters { display: grid; grid-template-columns: 160px minmax(220px, 1fr) 180px auto; gap: 8px; align-items: end; margin: 10px 0; }
.aeiw-field { display: flex; flex-direction: column; gap: 5px; min-width: 0; }
.aeiw-field > span { font-size: 12px; color: var(--text-secondary, #64748b); }
.aeiw-field input, .aeiw-field select { width: 100%; box-sizing: border-box; border: 1px solid var(--border-color, #d1d5db); border-radius: 8px; min-height: 34px; padding: 7px 9px; background: var(--surface-color, #fff); color: inherit; font: inherit; }
.aeiw-filter-actions { display: flex; gap: 6px; padding-bottom: 1px; }
.aeiw-detail-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; margin-bottom: 12px; }
.aeiw-detail-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; }
.aeiw-detail-grid > div { min-width: 0; padding: 10px; border-radius: 8px; background: var(--fill-light, #f8fafc); }
.aeiw-detail-grid span { display: block; color: var(--text-secondary, #64748b); font-size: 12px; margin-bottom: 4px; }
.aeiw-detail-grid strong { overflow-wrap: anywhere; }
.aeiw-block { margin: 12px 0; }
.aeiw-block > span { color: var(--text-secondary, #64748b); font-size: 12px; }
.aeiw-block p { margin: 5px 0 0; white-space: pre-wrap; overflow-wrap: anywhere; }
.aeiw-section-title { font-weight: 600; margin: 16px 0 8px; }
.aeiw-mono { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; overflow-wrap: anywhere; }
.handoff-ref { margin-top: 12px; }
@media (max-width: 980px) {
  .aeiw-kpis { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .aeiw-filters { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .aeiw-detail-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 600px) {
  .aeiw-head { flex-direction: column; }
  .aeiw-kpis, .aeiw-filters, .aeiw-detail-grid { grid-template-columns: 1fr; }
  .aeiw-filter-actions { flex-wrap: wrap; }
}
</style>
