<template>
  <ModulePageShell
    title="实习批次"
    :subtitle="pageSubtitle"
    :role-name="roleName"
    :data-scope-name="dataScopeName"
    watermark-purpose="实习批次管理"
  >
    <NoPermissionState v-if="noPermission" @back="$router.back()" />
    <template v-else>
      <ModuleToolbar :actions="toolbarActions" :hint="`共 ${total} 个批次 · 状态流转全程留痕`" @action="onToolbar" />

      <AdvancedFilter v-model="filters" :fields="filterFields" @search="search" @reset="reset" />

      <LoadingState v-if="loading" />
      <ErrorState v-else-if="error" :description="error" @retry="load" />
      <EmptyState v-else-if="!rows.length" title="暂无实习批次" description="点击右上角「新建批次」创建本轮岗位实习" />
      <DataTable
        v-else
        :columns="tableColumns"
        :rows="rows"
        row-key="id"
        row-clickable
        :pagination="{ page, pageSize, total }"
        @page-change="turnPage"
        @row-click="openDetail"
      >
        <template #cell-status="{ row }">
          <StatusTag :type="statusTagType[row.status] || 'default'" :label="row.statusLabel" dot />
        </template>
        <template #cell-term="{ row }">
          <span>{{ row.academicYear || '—' }}{{ row.term ? ' · ' + row.term : '' }}</span>
        </template>
        <template #cell-range="{ row }">
          <span>{{ dateShort(row.startDate) || '—' }} ~ {{ dateShort(row.endDate) || '—' }}</span>
        </template>
        <template #cell-count="{ row }">
          <span>{{ row.actualCount }} / {{ row.plannedCount }}</span>
        </template>
        <template #cell-actions="{ row }">
          <TableActionColumn :actions="rowActions(row)" @action="(key) => onRowAction(key, row)" />
        </template>
      </DataTable>

      <!-- 新建 / 编辑 -->
      <EditDrawer
        v-model:visible="editVisible"
        :title="editing ? '编辑实习批次' : '新建实习批次'"
        :fields="editFields"
        :model="editingModel"
        :submitting="submitting"
        @submit="onEditSubmit"
      />

      <!-- 详情：阶段时间轴 + 规则配置 + 审计留痕 -->
      <AppDrawer v-model:visible="detailVisible" :title="detailRow ? `${detailRow.batchName} · 详情` : '批次详情'">
        <div v-if="detailRow" class="bd">
          <section class="bd__section">
            <h4>基本信息</h4>
            <dl class="bd__grid">
              <div><dt>批次编号</dt><dd>{{ detailRow.batchNo }}</dd></div>
              <div><dt>状态</dt><dd><StatusTag :type="statusTagType[detailRow.status] || 'default'" :label="detailRow.statusLabel" dot /></dd></div>
              <div><dt>计划 / 实际人数</dt><dd>{{ detailRow.plannedCount }} / {{ detailRow.actualCount }}</dd></div>
              <div><dt>报名窗口</dt><dd>{{ dateShort(detailRow.signupStartDate) || '—' }} ~ {{ dateShort(detailRow.signupEndDate) || '—' }}</dd></div>
              <div v-if="detailRow.transitionReason"><dt>作废原因</dt><dd>{{ detailRow.transitionReason }}</dd></div>
              <div v-if="detailRow.archiveBatchNo"><dt>归档批次号</dt><dd>{{ detailRow.archiveBatchNo }}（{{ detailRow.archivedBy }} · {{ detailRow.archivedAt }}）</dd></div>
            </dl>
          </section>

          <section class="bd__section">
            <h4>阶段时间轴</h4>
            <AppTimeline :items="stageTimelineItems" />
          </section>

          <section class="bd__section">
            <h4>规则配置</h4>
            <ul class="bd__rules">
              <li>打卡：{{ detailRow.rules.checkin.requireDaily ? '每日必打卡' : '不强制每日' }}，电子围栏 {{ detailRow.rules.checkin.geofenceRadiusM }} 米</li>
              <li>周报：{{ detailRow.rules.weeklyReport.frequency === 'WEEKLY' ? '每周 1 次' : '每两周 1 次' }}，正文 ≥ {{ detailRow.rules.weeklyReport.minWordCount }} 字，周{{ detailRow.rules.weeklyReport.deadlineWeekday }}前提交</li>
              <li>指导：每学期现场巡访 ≥ {{ detailRow.rules.guidance.minVisitsPerTerm }} 次，每月沟通 ≥ {{ detailRow.rules.guidance.minCommunicationsPerMonth }} 次</li>
              <li>评价权重：企业 {{ pct(detailRow.rules.evaluation.enterpriseWeight) }} / 教师 {{ pct(detailRow.rules.evaluation.teacherWeight) }} / 自评 {{ pct(detailRow.rules.evaluation.selfWeight) }}</li>
              <li>成绩：及格线 {{ detailRow.rules.score.passThreshold }} 分，构成 {{ scoreComponentsText }}</li>
            </ul>
          </section>

          <section class="bd__section">
            <h4>操作留痕</h4>
            <AuditTrailPanel :logs="auditLogRows" />
          </section>
        </div>
      </AppDrawer>

      <!-- 启用 / 结束 / 归档 / 作废 二次确认 -->
      <AppConfirmDialog
        v-model:visible="confirmVisible"
        :title="confirmConf.title"
        :message="confirmConf.message"
        :type="confirmConf.type"
        :confirm-text="confirmConf.confirmText"
        :require-reason="confirmConf.requireReason"
        reason-label="作废原因（≥5 字）"
        @confirm="onConfirm"
      />
    </template>
  </ModulePageShell>
</template>

<script>
/** /admin/internship/batches 实习批次（列表 / 新建 / 编辑 / 启用 / 结束 / 归档 / 作废；真实走后端 /internship/batches）。 */
import { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag, EmptyState, LoadingState, ErrorState } from '@/components/business'
import { AppConfirmDialog, AppTimeline } from '@/components/common'
import { AppDrawer } from '@/components/ui'
import { EditDrawer, TableActionColumn, AuditTrailPanel, NoPermissionState } from '@/modules/internship/components'
import { internshipApi } from '@/modules/internship/api/internship.api'
import { toast } from '@/utils/toast'

const EMPTY_FILTERS = () => ({ keyword: '', status: '' })
const BATCH_PANEL_PRESETS = {
  list: () => EMPTY_FILTERS(),
  timeline: () => ({ ...EMPTY_FILTERS(), status: 'RUNNING' }),
  rules: () => ({ ...EMPTY_FILTERS(), status: 'DRAFT' }),
  export: () => ({ ...EMPTY_FILTERS(), status: 'ARCHIVED' })
}
const BATCH_PANEL_HINTS = {
  list: '组织岗位实习的时间轴与规则骨架（草稿 → 进行中 → 已结束 → 已归档）',
  timeline: '进行中批次 · 点击行「详情」查看阶段时间轴，新建/编辑可配 stagesJson',
  rules: '草稿批次 · 新建/编辑时可编辑 rulesJson（打卡/周报/指导/评价/成绩）',
  export: '已归档批次台账 · 可用右上角「导出 Excel 台账」'
}
const STATUS_OPTIONS = [
  { value: 'DRAFT', label: '草稿' },
  { value: 'RUNNING', label: '进行中' },
  { value: 'CLOSED', label: '已结束' },
  { value: 'ARCHIVED', label: '已归档' },
  { value: 'VOIDED', label: '已作废' }
]

export default {
  name: 'InternshipBatchListView',
  components: {
    ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag, EmptyState, LoadingState, ErrorState,
    AppConfirmDialog, AppTimeline, AppDrawer, EditDrawer, TableActionColumn, AuditTrailPanel, NoPermissionState
  },
  data() {
    return {
      ctx: null,
      loading: true,
      error: '',
      submitting: false,
      activePanel: 'list',
      rows: [],
      total: 0,
      page: 1,
      pageSize: 10,
      filters: EMPTY_FILTERS(),
      editVisible: false,
      editing: null,
      editingModel: null,
      detailVisible: false,
      detailRow: null,
      confirmVisible: false,
      confirmMode: '',
      confirmRow: null,
      statusTagType: { DRAFT: 'default', RUNNING: 'success', CLOSED: 'info', ARCHIVED: 'default', VOIDED: 'danger' }
    }
  },
  computed: {
    roleName() {
      return this.ctx?.currentRole?.roleName || ''
    },
    dataScopeName() {
      return this.ctx?.dataScope?.name || ''
    },
    perms() {
      return this.ctx?.permissionActions || {}
    },
    noPermission() {
      // 批次列表查看本身对已授权进入本页的角色开放；创建/归档等动作按钮各自受权限控制（见 rowActions/toolbarActions）
      return false
    },
    toolbarActions() {
      const p = this.perms.createBatch
      return [
        { key: 'create', label: '新建批次', disabled: p ? !p.allowed : false, disabledReason: p && !p.allowed ? p.reason : '' },
        { key: 'export', label: '导出 Excel 台账' }
      ]
    },
    filterFields() {
      return [
        { key: 'keyword', label: '关键词', type: 'text', placeholder: '批次名称 / 编号' },
        { key: 'status', label: '状态', type: 'select', options: STATUS_OPTIONS }
      ]
    },
    tableColumns() {
      return [
        { key: 'batchName', title: '批次名称' },
        { key: 'batchNo', title: '批次编号' },
        { key: 'term', title: '学年学期' },
        { key: 'range', title: '实习起止' },
        { key: 'count', title: '实际/计划人数' },
        { key: 'status', title: '状态' },
        { key: 'updateTime', title: '更新时间' },
        { key: 'actions', title: '操作' }
      ]
    },
    editFields() {
      return [
        { key: 'batchName', label: '批次名称', type: 'text', required: true, placeholder: '如：2026 届春季岗位实习' },
        { key: 'batchNo', label: '批次编号', type: 'text', required: true, placeholder: '如：INT-2026S', disabled: !!this.editing },
        { key: 'academicYear', label: '学年', type: 'text', placeholder: '如：2025-2026' },
        { key: 'term', label: '学期', type: 'text', placeholder: '如：第二学期' },
        { key: 'startDate', label: '实习开始', type: 'date' },
        { key: 'endDate', label: '实习结束', type: 'date' },
        { key: 'signupStartDate', label: '报名开始', type: 'date' },
        { key: 'signupEndDate', label: '报名结束', type: 'date' },
        { key: 'plannedCount', label: '计划人数', type: 'number' },
        { key: 'remark', label: '备注', type: 'textarea', placeholder: '批次说明（可选）' },
        {
          key: 'stagesJson', label: '阶段时间轴（JSON，可选）', type: 'textarea', rows: 4,
          placeholder: '[{"code":"PREP","name":"岗前准备","startDate":"","endDate":""}]',
          hint: '留空则使用默认三阶段：岗前准备 / 在岗实习 / 总结考核'
        },
        {
          key: 'rulesJson', label: '规则配置（JSON，可选）', type: 'textarea', rows: 4,
          placeholder: '{"checkin":{"geofenceRadiusM":500}, ...}',
          hint: '留空则使用默认规则；仅需覆盖的字段可局部提交'
        }
      ]
    },
    stageTimelineItems() {
      const stages = (this.detailRow && this.detailRow.stages) || []
      return stages.map((s) => ({
        id: s.code, title: s.name, type: 'primary',
        time: (s.startDate || s.endDate) ? `${this.dateShort(s.startDate) || '—'} ~ ${this.dateShort(s.endDate) || '—'}` : '未设置具体日期'
      }))
    },
    scoreComponentsText() {
      const comps = (this.detailRow && this.detailRow.rules.score.components) || []
      return comps.map((c) => `${c.name} ${this.pct(c.weight)}`).join(' + ')
    },
    auditLogRows() {
      const trail = (this.detailRow && this.detailRow.auditTrail) || []
      const ACTION_LABEL = { CREATE: '新建批次', UPDATE: '编辑批次', ACTIVATE: '启用批次', CLOSE: '结束批次', ARCHIVE: '归档批次', VOID: '作废批次' }
      return trail.map((t) => ({ id: t.id, time: t.time, operator: t.operator, action: ACTION_LABEL[t.action] || t.action, detail: t.detail }))
    },
    confirmConf() {
      const r = this.confirmRow
      if (this.confirmMode === 'activate') {
        return { title: '启用批次', message: r ? `将「${r.batchName}」置为「进行中」，实习流程正式开放。` : '', type: 'primary', confirmText: '确认启用', requireReason: false }
      }
      if (this.confirmMode === 'close') {
        return { title: '结束批次', message: r ? `将「${r.batchName}」置为「已结束」，结束后才可归档。` : '', type: 'danger', confirmText: '确认结束', requireReason: false }
      }
      if (this.confirmMode === 'archive') {
        return { title: '归档批次', message: r ? `归档「${r.batchName}」后进入只读台账，不可再变更。` : '', type: 'danger', confirmText: '确认归档', requireReason: false }
      }
      if (this.confirmMode === 'void') {
        return { title: '作废批次', message: r ? `作废「${r.batchName}」（仅草稿态可作废，可审计）。` : '', type: 'danger', confirmText: '确认作废', requireReason: true }
      }
      return { title: '', message: '', type: 'primary', confirmText: '确认', requireReason: false }
    },
    pageSubtitle() {
      const hint = BATCH_PANEL_HINTS[this.activePanel] || BATCH_PANEL_HINTS.list
      return `共 ${this.total} 个批次 · ${hint}`
    }
  },
  watch: {
    '$route.query.panel': {
      immediate: true,
      handler(panel) {
        this.applyPanel((panel || 'list').toString())
      }
    }
  },
  async created() {
    const ctx = await internshipApi.getContext()
    if (ctx.code === 0) this.ctx = ctx.data
  },
  methods: {
    applyPanel(panel) {
      const key = BATCH_PANEL_PRESETS[panel] ? panel : 'list'
      this.activePanel = key
      this.filters = (BATCH_PANEL_PRESETS[key] || BATCH_PANEL_PRESETS.list)()
      this.page = 1
      this.load()
    },
    pct(v) {
      return `${Math.round((v || 0) * 100)}%`
    },
    async load() {
      this.loading = true
      this.error = ''
      try {
        const res = await internshipApi.getBatches({ ...this.filters, page: this.page, pageSize: this.pageSize })
        if (res.code === 0) {
          this.rows = res.data.list
          this.total = res.data.total
        } else this.error = res.message
      } catch (e) {
        this.error = e.message || '加载失败'
      } finally {
        this.loading = false
      }
    },
    search() {
      this.page = 1
      this.load()
    },
    reset() {
      this.filters = EMPTY_FILTERS()
      this.page = 1
      this.load()
    },
    turnPage(p) {
      this.page = p
      this.load()
    },
    dateShort(v) {
      return v ? String(v).slice(0, 10) : ''
    },
    onToolbar(key) {
      if (key === 'create') this.openCreate()
      else if (key === 'export') this.doExport()
    },
    async doExport() {
      const res = await internshipApi.downloadBatchExport({ ...this.filters })
      if (res.code === 0) toast.success(`已导出 Excel 台账 ${res.data.rowCount} 个批次（已写审计）`)
      else toast.error(res.message)
    },
    openCreate() {
      this.editing = null
      this.editingModel = { plannedCount: 0 }
      this.editVisible = true
    },
    openEdit(row) {
      this.editing = row
      this.editingModel = {
        batchName: row.batchName, batchNo: row.batchNo, academicYear: row.academicYear, term: row.term,
        startDate: this.dateShort(row.startDate), endDate: this.dateShort(row.endDate),
        signupStartDate: this.dateShort(row.signupStartDate), signupEndDate: this.dateShort(row.signupEndDate),
        plannedCount: row.plannedCount, remark: row.remark, stagesJson: '', rulesJson: ''
      }
      this.editVisible = true
    },
    async openDetail(row) {
      const res = await internshipApi.getBatchDetail(row.id)
      if (res.code === 0) {
        this.detailRow = res.data
        this.detailVisible = true
      } else toast.error(res.message || '加载详情失败')
    },
    async onEditSubmit(form) {
      const body = { ...form }
      delete body.stagesJson
      delete body.rulesJson
      if (form.stagesJson && form.stagesJson.trim()) {
        try {
          body.stages = JSON.parse(form.stagesJson)
        } catch {
          return toast.error('阶段时间轴 JSON 格式错误，请检查后重试')
        }
      }
      if (form.rulesJson && form.rulesJson.trim()) {
        try {
          body.rules = JSON.parse(form.rulesJson)
        } catch {
          return toast.error('规则配置 JSON 格式错误，请检查后重试')
        }
      }
      this.submitting = true
      try {
        const res = this.editing
          ? await internshipApi.updateBatch(this.editing.id, body)
          : await internshipApi.createBatch(body)
        if (res.code === 0) {
          toast.success(this.editing ? '已保存' : '已新建批次')
          this.editVisible = false
          await this.load()
        } else {
          toast.error(res.message || '保存失败')
        }
      } finally {
        this.submitting = false
      }
    },
    rowActions(row) {
      return [
        { key: 'detail', label: '详情' },
        { key: 'edit', label: '编辑', disabled: !['DRAFT', 'RUNNING'].includes(row.status), disabledReason: '仅草稿/进行中批次可编辑' },
        { key: 'activate', label: '启用', disabled: row.status !== 'DRAFT', disabledReason: '仅草稿可启用' },
        { key: 'close', label: '结束', disabled: row.status !== 'RUNNING', disabledReason: '仅进行中可结束' },
        { key: 'archive', label: '归档', disabled: row.status !== 'CLOSED', disabledReason: '仅已结束可归档' },
        { key: 'void', label: '作废', danger: true, disabled: row.status !== 'DRAFT', disabledReason: '仅草稿可作废' }
      ]
    },
    onRowAction(key, row) {
      if (key === 'detail') return this.openDetail(row)
      if (key === 'edit') return this.openEdit(row)
      this.confirmMode = key
      this.confirmRow = row
      this.confirmVisible = true
    },
    async onConfirm(payload) {
      const row = this.confirmRow
      if (!row) return
      const reason = (payload && payload.reason) || ''
      let res
      if (this.confirmMode === 'activate') res = await internshipApi.activateBatch(row.id)
      else if (this.confirmMode === 'close') res = await internshipApi.closeBatch(row.id)
      else if (this.confirmMode === 'archive') res = await internshipApi.archiveBatch(row.id)
      else if (this.confirmMode === 'void') res = await internshipApi.voidBatch(row.id, reason)
      if (res && res.code === 0) {
        toast.success('操作成功')
        this.confirmVisible = false
        await this.load()
      } else {
        toast.error((res && res.message) || '操作失败')
      }
    }
  }
}
</script>

<style scoped>
.bd {
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
}
.bd__section h4 {
  margin: 0 0 var(--space-2);
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
  color: var(--text-secondary);
}
.bd__grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-2) var(--space-4);
  margin: 0;
}
.bd__grid dt {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}
.bd__grid dd {
  margin: 0;
  font-size: var(--font-size-sm);
  color: var(--text-primary);
}
.bd__rules {
  margin: 0;
  padding-left: var(--space-5);
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}
</style>
