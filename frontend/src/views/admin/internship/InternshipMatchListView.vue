<template>
  <ModulePageShell
    title="岗位与导师分配"
    :subtitle="pageSubtitle"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppExportButton v-if="!isStatsPanel" :export-fn="exportFn">⬇ 导出 Excel 台账</AppExportButton>
      <ModuleToolbar :actions="toolbarActions" @action="onToolbar" />
    </template>

    <ModuleSummaryStrip :metrics="summaryMetrics" :note="summaryMetrics.length ? '' : '暂无统计口径'" />

    <div v-if="activePanel === 'stats' && matchStats" class="mp-stats">
      <div class="mp-stat"><div class="mp-stat__val">{{ matchStats.total }}</div><div class="mp-stat__lbl">匹配总数</div></div>
      <div class="mp-stat"><div class="mp-stat__val">{{ matchStats.confirmedCount }}</div><div class="mp-stat__lbl">已确认落岗</div></div>
      <div class="mp-stat"><div class="mp-stat__val">{{ matchStats.conflictCount }}</div><div class="mp-stat__lbl">冲突</div></div>
      <div class="mp-stat"><div class="mp-stat__val">{{ matchStats.intentionSubmitted }}</div><div class="mp-stat__lbl">已提交意向</div></div>
    </div>

    <div class="mp-stack">
      <AdvancedFilter v-if="!isStatsPanel" v-model="filters" :fields="filterFields" @search="search" @reset="reset" />
      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <template v-else-if="isStatsPanel && matchStats">
        <div class="im-block">
          <h3 class="im-h">按状态</h3>
          <DataTable :columns="statStatusCols" :rows="matchStats.byStatus || []" row-key="status" :pagination="null" />
        </div>
        <div class="im-block">
          <h3 class="im-h">按匹配方式</h3>
          <DataTable :columns="statTypeCols" :rows="matchStats.byType || []" row-key="matchType" :pagination="null" />
        </div>
      </template>
      <EmptyState v-else-if="!rows.length" :title="emptyTitle" :description="emptyDesc" />
      <DataTable
        v-else
        :columns="columns"
        :rows="rows"
        row-key="id"
        :pagination="{ page, pageSize, total }"
        @page-change="turnPage"
      >
        <template #cell-student="{ row }">
          <div class="mp-cell-main">{{ row.studentName }}</div>
          <div class="mp-cell-sub">{{ row.studentNo }} · {{ row.majorName || '未维护专业' }}</div>
        </template>
        <template #cell-prefer="{ row }">
          <div class="mp-cell-sub">{{ row.preferredCity || '-' }} / {{ row.preferredIndustry || '-' }}</div>
          <div class="mp-cell-sub">{{ row.preferredCompanyName || '未指定企业' }}</div>
        </template>
        <template #cell-position="{ row }">
          <div class="mp-cell-main">{{ row.positionTitle }}</div>
          <div class="mp-cell-sub">{{ row.companyName }} · 余量 {{ row.remaining }}</div>
        </template>
        <template #cell-score="{ row }">
          <span>{{ row.score }}</span>
          <span v-if="row.majorHit" class="im-tag">专业</span>
          <span v-if="row.enterpriseHit" class="im-tag im-tag--e">企业</span>
        </template>
        <template #cell-conflict="{ row }">
          <span v-if="row.conflictFlag" class="im-conflict">{{ row.conflictReason || '冲突' }}</span>
          <span v-else>-</span>
        </template>
        <template #cell-status="{ row }">
          <AppStatusTag :type="row.statusTone || 'default'" dot>{{ row.statusLabel }}</AppStatusTag>
        </template>
        <template #cell-actions="{ row }">
          <template v-if="isIntentionPanel">
            <button v-if="row.status === 'DRAFT' || row.status === 'WITHDRAWN'" class="mp-link" @click="doSubmitIntention(row)">提交</button>
            <button v-if="row.status === 'SUBMITTED'" class="mp-link" style="margin-left: var(--space-2)" @click="doWithdrawIntention(row)">撤回</button>
          </template>
          <template v-else>
            <button
              v-if="['RECOMMENDED', 'PENDING_CONFIRM', 'CONFLICT'].includes(row.status)"
              class="mp-link"
              @click="askConfirm(row)"
            >确认落岗</button>
            <button
              v-if="['RECOMMENDED', 'PENDING_CONFIRM', 'CONFLICT'].includes(row.status)"
              class="mp-link mp-link--danger"
              style="margin-left: var(--space-2)"
              @click="askReject(row)"
            >驳回</button>
          </template>
        </template>
      </DataTable>
    </div>

    <AppDrawer v-model:visible="intentionVisible" title="登记学生意向">
      <form class="ie-form" @submit.prevent="submitIntentionForm">
        <label class="ie-fld ie-fld--full"><span class="ie-lbl">实习学生 <i>*</i></span>
          <select v-model="intentionForm.recordId" class="ie-in">
            <option value="">请选择</option>
            <option v-for="s in studentOpts" :key="s.id" :value="s.id">{{ s.label }}</option>
          </select>
        </label>
        <label class="ie-fld"><span class="ie-lbl">意向城市</span><input v-model.trim="intentionForm.preferredCity" class="ie-in" /></label>
        <label class="ie-fld"><span class="ie-lbl">意向行业</span><input v-model.trim="intentionForm.preferredIndustry" class="ie-in" /></label>
        <label class="ie-fld ie-fld--full"><span class="ie-lbl">意向企业</span>
          <select v-model="intentionForm.preferredCompanyId" class="ie-in">
            <option value="">不指定</option>
            <option v-for="e in enterpriseOpts" :key="e.id" :value="e.id">{{ e.name }}</option>
          </select>
        </label>
        <label class="ie-fld ie-fld--full"><span class="ie-lbl">备注</span><textarea v-model.trim="intentionForm.intentionNote" class="ie-in" rows="2" /></label>
        <p v-if="formError" class="ie-err">{{ formError }}</p>
        <div class="ie-actions">
          <button type="button" class="mp-btn" @click="intentionVisible = false">取消</button>
          <button type="submit" class="mp-btn mp-btn--primary" :disabled="submitting">{{ submitting ? '提交中…' : '保存草稿' }}</button>
        </div>
      </form>
    </AppDrawer>

    <AppDrawer v-model:visible="manualVisible" title="手动匹配">
      <form class="ie-form" @submit.prevent="submitManual">
        <label class="ie-fld ie-fld--full"><span class="ie-lbl">实习学生 <i>*</i></span>
          <select v-model="manualForm.recordId" class="ie-in">
            <option value="">请选择</option>
            <option v-for="s in studentOpts" :key="s.id" :value="s.id">{{ s.label }}</option>
          </select>
        </label>
        <label class="ie-fld ie-fld--full"><span class="ie-lbl">上架岗位 <i>*</i></span>
          <select v-model="manualForm.positionId" class="ie-in">
            <option value="">请选择</option>
            <option v-for="p in positionOpts" :key="p.id" :value="p.id">{{ p.label }}（余 {{ p.remaining }}）</option>
          </select>
        </label>
        <label class="ie-fld ie-fld--full"><span class="ie-lbl">备注</span><textarea v-model.trim="manualForm.remark" class="ie-in" rows="2" /></label>
        <p v-if="formError" class="ie-err">{{ formError }}</p>
        <div class="ie-actions">
          <button type="button" class="mp-btn" @click="manualVisible = false">取消</button>
          <button type="submit" class="mp-btn mp-btn--primary" :disabled="submitting">确认</button>
        </div>
      </form>
    </AppDrawer>

    <AppDrawer v-model:visible="batchVisible" title="批量匹配">
      <div class="ie-form">
        <p class="ie-hint">每行：实习学生记录ID,岗位ID（可从实习学生/岗位库复制）</p>
        <textarea v-model="batchText" class="ie-in" rows="6" placeholder="recordId,positionId" />
        <p v-if="formError" class="ie-err">{{ formError }}</p>
        <div class="ie-actions">
          <button type="button" class="mp-btn" @click="batchVisible = false">取消</button>
          <button type="button" class="mp-btn mp-btn--primary" :disabled="submitting" @click="submitBatch">执行批量匹配</button>
        </div>
      </div>
    </AppDrawer>

    <AppExcelImportDrawer
      v-model:visible="importVisible"
      title="导入学生意向"
      template-name="意向导入模板.xlsx"
      :required-fields="['学号']"
      :preview-fields="['studentNo', 'city', 'industry', 'company', 'note']"
      :download-template-fn="() => matchApi.downloadIntentionTemplate()"
      :upload-fn="(file) => matchApi.importIntentionsXlsx(file)"
      :confirm-fn="({ rows }) => matchApi.importIntentionsConfirm(rows)"
      :download-errors-fn="({ rows, errors }) => matchApi.downloadIntentionImportErrors(rows, errors)"
      @imported="onImported"
    />

    <AppConfirmDialog
      v-model:visible="confirm.visible"
      :title="confirm.title"
      :message="confirm.message"
      :type="confirm.type"
      :confirm-text="confirm.confirmText"
      :require-reason="confirm.requireReason"
      :reason-label="confirm.reasonLabel"
      :submitting="submitting"
      @confirm="onConfirm"
    />
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppExportButton, AppStatusTag } from '@/components/common'
import { AppExcelImportDrawer } from '@/components/common/excel'
import { AppDrawer } from '@/components/ui'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import ModuleSummaryStrip from './components/ModuleSummaryStrip.vue'
import { matchApi } from '@/modules/internship/api/match.api'
import { toast } from '@/utils/toast'

const EMPTY_FILTERS = () => ({ keyword: '', status: '', matchType: '' })

const PANEL_HINTS = {
  intention: '学生意向登记 / 提交 / 导入导出',
  recommend: '岗位推荐结果（规则引擎产出）',
  major: '按学生专业 × 岗位专业要求匹配',
  enterprise: '按意向企业推荐上架岗位',
  manual: '管理员手工指定学生-岗位',
  batch: '批量写入待确认匹配',
  confirm: '待确认匹配 · 确认后复用分配落岗',
  conflict: '一人多岗 / 满员 / 已分配冲突',
  results: '全部匹配结果台账',
  stats: '匹配统计看板'
}

export default {
  name: 'InternshipMatchListView',
  components: { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, AppStatusTag, AppExportButton, AppExcelImportDrawer, LoadingState, ErrorState, EmptyState, AppDrawer, AppConfirmDialog, ModuleSummaryStrip },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      matchApi,
      loading: true, error: '', submitting: false, activePanel: 'intention',
      rows: [], total: 0, page: 1, pageSize: 10, filters: EMPTY_FILTERS(),
      matchStats: null, studentOpts: [], positionOpts: [], enterpriseOpts: [],
      intentionVisible: false, intentionForm: { recordId: '', preferredCity: '', preferredIndustry: '', preferredCompanyId: '', intentionNote: '' },
      manualVisible: false, manualForm: { recordId: '', positionId: '', remark: '' },
      batchVisible: false, batchText: '',
      importVisible: false,
      formError: '',
      confirm: { visible: false, title: '', message: '', type: 'primary', confirmText: '确认', requireReason: false, reasonLabel: '原因', action: null, row: null },
      statStatusCols: [{ key: 'label', title: '状态' }, { key: 'count', title: '数量' }],
      statTypeCols: [{ key: 'label', title: '匹配方式' }, { key: 'count', title: '数量' }]
    }
  },
  computed: {
    isIntentionPanel() { return this.activePanel === 'intention' },
    isStatsPanel() { return this.activePanel === 'stats' },
    isConflictPanel() { return this.activePanel === 'conflict' },
    columns() {
      if (this.isIntentionPanel) {
        return [
          { key: 'student', title: '学生' },
          { key: 'prefer', title: '意向' },
          { key: 'status', title: '状态' },
          { key: 'actions', title: '操作', width: '160px' }
        ]
      }
      return [
        { key: 'student', title: '学生' },
        { key: 'position', title: '岗位 / 企业' },
        { key: 'matchTypeLabel', title: '方式' },
        { key: 'score', title: '得分' },
        { key: 'conflict', title: '冲突' },
        { key: 'status', title: '状态' },
        { key: 'actions', title: '操作', width: '180px' }
      ]
    },
    filterFields() {
      if (this.isIntentionPanel) {
        return [
          { key: 'keyword', label: '关键词', type: 'text', placeholder: '姓名 / 学号 / 城市' },
          { key: 'status', label: '状态', type: 'select', options: [
            { value: 'DRAFT', label: '草稿' }, { value: 'SUBMITTED', label: '已提交' }, { value: 'WITHDRAWN', label: '已撤回' }
          ] }
        ]
      }
      return [
        { key: 'keyword', label: '关键词', type: 'text', placeholder: '学生 / 岗位 / 企业' },
        { key: 'status', label: '状态', type: 'select', options: [
          { value: 'RECOMMENDED', label: '已推荐' }, { value: 'PENDING_CONFIRM', label: '待确认' },
          { value: 'CONFIRMED', label: '已确认' }, { value: 'REJECTED', label: '已驳回' },
          { value: 'CONFLICT', label: '冲突' }, { value: 'CANCELLED', label: '已取消' }
        ] },
        { key: 'matchType', label: '方式', type: 'select', options: [
          { value: 'AUTO_MAJOR', label: '专业匹配' }, { value: 'AUTO_ENTERPRISE', label: '企业匹配' },
          { value: 'MANUAL', label: '手动' }, { value: 'BATCH', label: '批量' }
        ] }
      ]
    },
    toolbarActions() {
      if (this.isIntentionPanel) {
        return [
          { key: 'createIntention', label: '＋ 登记意向', variant: 'primary' },
          { key: 'import', label: '导入 Excel' }
        ]
      }
      if (this.activePanel === 'major') {
        return [
          { key: 'runMajor', label: '跑专业匹配', variant: 'primary' }
        ]
      }
      if (this.activePanel === 'enterprise') {
        return [
          { key: 'runEnterprise', label: '跑企业匹配', variant: 'primary' }
        ]
      }
      if (this.activePanel === 'manual') {
        return [
          { key: 'manual', label: '＋ 手动匹配', variant: 'primary' }
        ]
      }
      if (this.activePanel === 'batch') {
        return [
          { key: 'batch', label: '批量匹配', variant: 'primary' }
        ]
      }
      if (this.isStatsPanel) {
        return [{ key: 'refreshStats', label: '刷新统计', variant: 'primary' }]
      }
      return []
    },
    pageSubtitle() {
      const intro = '为学生安排实习岗位和指导老师，处理匹配冲突、调岗和退岗'
      const hint = PANEL_HINTS[this.activePanel] || ''
      if (this.isStatsPanel) return `${intro} · ${hint}`
      return `${intro} · 共 ${this.total} 条 · ${hint}`
    },
    summaryMetrics() {
      const s = this.matchStats
      if (!s) return []
      return [
        { label: '匹配总数', value: s.total },
        { label: '已确认落岗', value: s.confirmedCount },
        { label: '冲突', value: s.conflictCount },
        { label: '已提交意向', value: s.intentionSubmitted }
      ]
    },
    emptyTitle() {
      return this.isIntentionPanel ? '暂无学生意向' : '暂无匹配记录'
    },
    emptyDesc() {
      return this.isIntentionPanel ? '可登记意向或导入 Excel' : '可跑专业/企业匹配，或手动/批量创建'
    }
  },
  watch: {
    '$route.query.panel': {
      immediate: true,
      handler(panel) {
        this.applyPanel((panel || 'intention').toString())
      }
    }
  },
  async created() {
    const [s, p, e, st] = await Promise.all([
      matchApi.getStudentOptions(),
      matchApi.getPositionOptions(),
      matchApi.getEnterpriseOptions(),
      matchApi.getStats()
    ])
    if (s.code === 0) this.studentOpts = s.data
    if (p.code === 0) this.positionOpts = p.data
    if (e.code === 0) this.enterpriseOpts = e.data
    if (st.code === 0 && !this.matchStats) this.matchStats = st.data
  },
  methods: {
    applyPanel(panel) {
      const known = Object.keys(PANEL_HINTS)
      this.activePanel = known.includes(panel) ? panel : 'intention'
      this.filters = EMPTY_FILTERS()
      if (this.activePanel === 'confirm') this.filters.status = 'PENDING_CONFIRM'
      if (this.activePanel === 'major') this.filters.matchType = 'AUTO_MAJOR'
      if (this.activePanel === 'enterprise') this.filters.matchType = 'AUTO_ENTERPRISE'
      if (this.activePanel === 'recommend') this.filters.status = 'RECOMMENDED'
      this.page = 1
      this.load()
    },
    async load() {
      this.loading = true
      this.error = ''
      try {
        if (this.isStatsPanel) {
          const res = await matchApi.getStats()
          if (res.code === 0) this.matchStats = res.data
          else this.error = res.message
          this.rows = []
          this.total = 0
        } else if (this.isIntentionPanel) {
          const res = await matchApi.getIntentions({ ...this.filters, page: this.page, pageSize: this.pageSize })
          if (res.code === 0) { this.rows = res.data.list; this.total = res.data.total }
          else this.error = res.message
        } else if (this.isConflictPanel) {
          const res = await matchApi.getConflicts({ keyword: this.filters.keyword, page: this.page, pageSize: this.pageSize })
          if (res.code === 0) { this.rows = res.data.list; this.total = res.data.total }
          else this.error = res.message
        } else {
          const params = { ...this.filters, page: this.page, pageSize: this.pageSize }
          const res = await matchApi.getResults(params)
          if (res.code === 0) { this.rows = res.data.list; this.total = res.data.total }
          else this.error = res.message
        }
      } finally {
        this.loading = false
      }
    },
    search() { this.page = 1; this.load() },
    reset() { this.filters = EMPTY_FILTERS(); this.page = 1; this.load() },
    turnPage(p) { this.page = p; this.load() },
    exportFn() {
      if (this.isIntentionPanel) return matchApi.exportIntentions({ ...this.filters })
      return matchApi.exportMatches({ ...this.filters })
    },
    async onToolbar(key) {
      this.formError = ''
      if (key === 'createIntention') {
        this.intentionForm = { recordId: '', preferredCity: '', preferredIndustry: '', preferredCompanyId: '', intentionNote: '' }
        this.intentionVisible = true
      }
      if (key === 'import') { this.importVisible = true }
      if (key === 'runMajor') {
        this.submitting = true
        try {
          const res = await matchApi.runMajor()
          if (res.code === 0) { toast.success(`专业匹配完成 · ${res.data.created} 条`); this.load() }
          else toast.error(res.message)
        } finally { this.submitting = false }
      }
      if (key === 'runEnterprise') {
        this.submitting = true
        try {
          const res = await matchApi.runEnterprise()
          if (res.code === 0) { toast.success(`企业匹配完成 · ${res.data.created} 条`); this.load() }
          else toast.error(res.message)
        } finally { this.submitting = false }
      }
      if (key === 'manual') {
        this.manualForm = { recordId: '', positionId: '', remark: '' }
        this.manualVisible = true
      }
      if (key === 'batch') { this.batchText = ''; this.batchVisible = true }
      if (key === 'refreshStats') this.load()
    },
    async submitIntentionForm() {
      this.formError = ''
      if (!this.intentionForm.recordId) { this.formError = '请选择实习学生'; return }
      this.submitting = true
      try {
        const res = await matchApi.createIntention(this.intentionForm)
        if (res.code === 0) { toast.success('已保存草稿'); this.intentionVisible = false; this.load() }
        else this.formError = res.message
      } finally { this.submitting = false }
    },
    async doSubmitIntention(row) {
      const res = await matchApi.submitIntention(row.id)
      if (res.code === 0) { toast.success('已提交'); this.load() } else toast.error(res.message)
    },
    async doWithdrawIntention(row) {
      const res = await matchApi.withdrawIntention(row.id)
      if (res.code === 0) { toast.success('已撤回'); this.load() } else toast.error(res.message)
    },
    async submitManual() {
      this.formError = ''
      if (!this.manualForm.recordId || !this.manualForm.positionId) { this.formError = '学生与岗位必选'; return }
      this.submitting = true
      try {
        const res = await matchApi.manualMatch(this.manualForm)
        if (res.code === 0) { toast.success('已创建待确认匹配'); this.manualVisible = false; this.load() }
        else this.formError = res.message
      } finally { this.submitting = false }
    },
    async submitBatch() {
      this.formError = ''
      const pairs = (this.batchText || '').split(/\n/).map((line) => line.trim()).filter(Boolean).map((line) => {
        const [recordId, positionId] = line.split(/[,，\t]/).map((x) => x.trim())
        return { recordId, positionId }
      }).filter((p) => p.recordId && p.positionId)
      if (!pairs.length) { this.formError = '请填写至少一行 recordId,positionId'; return }
      this.submitting = true
      try {
        const res = await matchApi.batchMatch(pairs)
        if (res.code === 0) {
          toast.success(`成功 ${res.data.success} · 失败 ${res.data.failed}`)
          this.batchVisible = false
          this.load()
        } else this.formError = res.message
      } finally { this.submitting = false }
    },
    onImported() {
      toast.success('导入完成')
      this.importVisible = false
      this.load()
    },
    askConfirm(row) {
      this.confirm = {
        visible: true, title: '确认匹配并落岗',
        message: `确认将「${row.studentName}」分配到「${row.positionTitle}」？将占用岗位名额。`,
        type: 'primary', confirmText: '确认落岗', requireReason: false, action: 'CONFIRM', row
      }
    },
    askReject(row) {
      this.confirm = {
        visible: true, title: '驳回匹配', message: `确认驳回「${row.studentName} / ${row.positionTitle}」？`,
        type: 'danger', confirmText: '确认驳回', requireReason: true, reasonLabel: '驳回原因', action: 'REJECT', row
      }
    },
    async onConfirm({ reason } = {}) {
      const { action, row } = this.confirm
      this.submitting = true
      try {
        if (action === 'CONFIRM') {
          const res = await matchApi.confirmMatch(row.id)
          if (res.code === 0) { toast.success('已确认并分配岗位'); this.confirm.visible = false; this.load() }
          else toast.error(res.message)
        }
        if (action === 'REJECT') {
          const res = await matchApi.rejectMatch(row.id, reason || '')
          if (res.code === 0) { toast.success('已驳回'); this.confirm.visible = false; this.load() }
          else toast.error(res.message)
        }
      } finally { this.submitting = false }
    }
  }
}
</script>

<style scoped>
.mp-stats { display: flex; flex-wrap: wrap; gap: var(--space-3); margin-bottom: var(--space-4); }
.mp-stat { min-width: 120px; padding: var(--space-3) var(--space-4); background: var(--color-bg-elevated, #fff); border: 1px solid var(--color-border, #eee); border-radius: 8px; cursor: default; }
.mp-stat__val { font-size: var(--font-size-xl); font-weight: 600; }
.mp-stat__lbl { color: var(--color-text-secondary); font-size: var(--font-size-sm); margin-top: var(--space-1); }
.im-block { margin-bottom: var(--space-4); }
.im-h { margin: 0 0 var(--space-2); font-size: var(--font-size-md); }
.im-tag { display: inline-block; margin-left: 4px; padding: 0 6px; font-size: 12px; background: #e8f5e9; color: #2e7d32; border-radius: 4px; }
.im-tag--e { background: #e3f2fd; color: #1565c0; }
.im-conflict { color: var(--color-danger, #c62828); font-size: 12px; }
.ie-form { display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-3); }
.ie-fld { display: flex; flex-direction: column; gap: 4px; }
.ie-fld--full { grid-column: 1 / -1; }
.ie-lbl { font-size: 13px; color: var(--color-text-secondary); }
.ie-lbl i { color: var(--color-danger, #c62828); font-style: normal; }
.ie-in { width: 100%; padding: 8px 10px; border: 1px solid var(--color-border, #ddd); border-radius: 6px; }
.ie-actions { grid-column: 1 / -1; display: flex; gap: var(--space-2); justify-content: flex-end; margin-top: var(--space-2); }
.ie-err { grid-column: 1 / -1; color: var(--color-danger, #c62828); margin: 0; }
.ie-hint { grid-column: 1 / -1; color: var(--color-text-secondary); font-size: 13px; margin: 0; }
.ie-imp { grid-column: 1 / -1; }
.ie-ok { color: #2e7d32; }
.ie-bad { color: #c62828; }
.ie-imp__errs { margin: 8px 0; padding-left: 18px; color: #c62828; font-size: 13px; }
</style>
