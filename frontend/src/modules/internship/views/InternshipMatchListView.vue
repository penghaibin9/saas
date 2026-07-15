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

    <nav class="im-stages" aria-label="岗位匹配流程">
      <span class="im-stages__title">匹配流程</span>
      <button
        v-for="(stage, index) in panelStages"
        :key="stage.key"
        type="button"
        class="im-stages__item"
        :class="{ 'is-active': activePanel === stage.key }"
        @click="goPanel(stage.key)"
      >
        <span class="im-stages__index">0{{ index + 1 }}</span>
        <span>{{ stage.label }}</span>
      </button>
    </nav>

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
            <button v-if="row.status === 'DRAFT' || row.status === 'WITHDRAWN'" class="mp-link" :disabled="!canIntentionManage" @click="doSubmitIntention(row)">提交</button>
            <button v-if="row.status === 'SUBMITTED'" class="mp-link" style="margin-left: var(--space-2)" :disabled="!canIntentionManage" @click="doWithdrawIntention(row)">撤回</button>
          </template>
          <template v-else>
            <button
              v-if="['RECOMMENDED', 'PENDING_CONFIRM', 'CONFLICT'].includes(row.status)"
              class="mp-link"
              :disabled="!canMatchManual"
              :title="canMatchManual ? '' : '无匹配落岗权限'"
              @click="askConfirm(row)"
            >确认落岗</button>
            <button
              v-if="['RECOMMENDED', 'PENDING_CONFIRM', 'CONFLICT'].includes(row.status)"
              class="mp-link mp-link--danger"
              style="margin-left: var(--space-2)"
              :disabled="!canMatchManual"
              :title="canMatchManual ? '' : '无匹配落岗权限'"
              @click="askReject(row)"
            >驳回</button>
          </template>
        </template>
      </DataTable>
    </div>

    <AppDrawer v-model:visible="intentionVisible" title="登记学生意向">
      <form class="ie-form" @submit.prevent="submitIntentionForm">
        <!-- Picker 不能包在 <label> 里：label 激活会把点击转发给选择器内部按钮 -->
        <div class="ie-fld ie-fld--full"><span class="ie-lbl">实习学生 <i>*</i></span>
          <AppStudentPicker
            v-model="intentionForm.recordId"
            :remote-search="searchUnassignedInternStudents"
            placeholder="输入姓名或学号搜索学生"
            search-placeholder="按姓名 / 学号搜索"
            data-scope-hint="仅显示你数据范围内未落实岗位的实习学生"
          />
        </div>
        <label class="ie-fld"><span class="ie-lbl">意向城市</span><input v-model.trim="intentionForm.preferredCity" class="ie-in" /></label>
        <label class="ie-fld"><span class="ie-lbl">意向行业</span><input v-model.trim="intentionForm.preferredIndustry" class="ie-in" /></label>
        <div class="ie-fld ie-fld--full"><span class="ie-lbl">意向企业</span>
          <AppCompanyPicker
            v-model="intentionForm.preferredCompanyId"
            :remote-search="searchEnterprises"
            placeholder="输入企业名称搜索（可不指定）"
            search-placeholder="按企业名称搜索"
          />
        </div>
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
        <div class="ie-fld ie-fld--full"><span class="ie-lbl">实习学生 <i>*</i></span>
          <AppStudentPicker
            v-model="manualForm.recordId"
            :remote-search="searchUnassignedInternStudents"
            placeholder="输入姓名或学号搜索学生"
            search-placeholder="按姓名 / 学号搜索"
            data-scope-hint="仅显示你数据范围内未落实岗位的实习学生"
          />
        </div>
        <div class="ie-fld ie-fld--full"><span class="ie-lbl">上架岗位 <i>*</i></span>
          <AppPositionPicker
            v-model="manualForm.positionId"
            :remote-search="searchPublishedPositions"
            placeholder="输入岗位或企业名称搜索"
            search-placeholder="按岗位名称 / 企业搜索"
            data-scope-hint="仅已上架岗位可选 · 满员（余 0）岗位不可选"
          />
        </div>
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
      show-account-boundary
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
import { AppExportButton, AppStatusTag, AppStudentPicker, AppPositionPicker, AppCompanyPicker } from '@/components/common'
import { AppExcelImportDrawer } from '@/components/common/excel'
import { AppDrawer } from '@/components/ui'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import ModuleSummaryStrip from './components/ModuleSummaryStrip.vue'
import { searchUnassignedInternStudents, searchPublishedPositions, searchEnterprises } from './components/entityPickerAdapters'
import { matchApi } from '@/modules/internship/api/match.api'
import { canCode } from '@/modules/internship/composables/permission'
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
  components: { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, AppStatusTag, AppExportButton, AppExcelImportDrawer, LoadingState, ErrorState, EmptyState, AppDrawer, AppConfirmDialog, ModuleSummaryStrip, AppStudentPicker, AppPositionPicker, AppCompanyPicker },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      matchApi,
      loading: true, error: '', submitting: false, activePanel: 'intention',
      rows: [], total: 0, page: 1, pageSize: 10, filters: EMPTY_FILTERS(),
      matchStats: null,
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
    canMatchManual() { return canCode(this.ctx, 'internship.match.manual') },
    canMatchBatch() { return canCode(this.ctx, 'internship.match.batch') },
    canIntentionManage() { return canCode(this.ctx, 'internship.match.intention.manage') },
    panelStages() {
      return [
        { key: 'intention', label: '意向登记' },
        { key: 'recommend', label: '推荐结果' },
        { key: 'confirm', label: '确认落岗' },
        { key: 'conflict', label: '冲突处置' },
        { key: 'results', label: '结果台账' }
      ]
    },
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
      const denyIntention = !this.canIntentionManage
      const denyManual = !this.canMatchManual
      const denyBatch = !this.canMatchBatch
      if (this.isIntentionPanel) {
        return [
          { key: 'createIntention', label: '＋ 登记意向', variant: 'primary', disabled: denyIntention, disabledReason: '无意向管理权限' },
          { key: 'import', label: '导入 Excel', disabled: denyIntention, disabledReason: '无意向管理权限' }
        ]
      }
      if (this.activePanel === 'major') {
        return [
          { key: 'runMajor', label: '跑专业匹配', variant: 'primary', disabled: denyManual, disabledReason: '无匹配操作权限' }
        ]
      }
      if (this.activePanel === 'enterprise') {
        return [
          { key: 'runEnterprise', label: '跑企业匹配', variant: 'primary', disabled: denyManual, disabledReason: '无匹配操作权限' }
        ]
      }
      if (this.activePanel === 'manual') {
        return [
          { key: 'manual', label: '＋ 手动匹配', variant: 'primary', disabled: denyManual, disabledReason: '无手动匹配权限' }
        ]
      }
      if (this.activePanel === 'batch') {
        return [
          { key: 'batch', label: '批量匹配', variant: 'primary', disabled: denyBatch, disabledReason: '无批量匹配权限' }
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
    // 学生/岗位/企业候选已改为选择器内按关键字远程搜索（后端裁定数据范围），不再一次性预载
    const st = await matchApi.getStats()
    if (st.code === 0 && !this.matchStats) this.matchStats = st.data
  },
  methods: {
    // 选择器远程搜索（岗位实习模块适配层，后端裁定关键字与数据范围）
    searchUnassignedInternStudents,
    searchPublishedPositions,
    searchEnterprises,
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
    goPanel(panel) {
      if (this.activePanel === panel) return
      this.$router.replace({ path: this.$route.path, query: { ...this.$route.query, panel } })
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
      // 前端二次拦截（后端 require_permission 仍是最终边界）
      const perm = {
        createIntention: this.canIntentionManage, import: this.canIntentionManage,
        runMajor: this.canMatchManual, runEnterprise: this.canMatchManual,
        manual: this.canMatchManual, batch: this.canMatchBatch
      }
      if (key in perm && !perm[key]) return toast.error('当前角色无此匹配操作权限')
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
      if (!this.canIntentionManage) return toast.error('无意向管理权限')
      const res = await matchApi.submitIntention(row.id)
      if (res.code === 0) { toast.success('已提交'); this.load() } else toast.error(res.message)
    },
    async doWithdrawIntention(row) {
      if (!this.canIntentionManage) return toast.error('无意向管理权限')
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
      if (!this.canMatchManual) return toast.error('无匹配落岗权限')
      this.confirm = {
        visible: true, title: '确认匹配并落岗',
        message: `确认将「${row.studentName}」分配到「${row.positionTitle}」？将占用岗位名额。`,
        type: 'primary', confirmText: '确认落岗', requireReason: false, action: 'CONFIRM', row
      }
    },
    askReject(row) {
      if (!this.canMatchManual) return toast.error('无匹配落岗权限')
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
.im-stages { display: flex; align-items: center; gap: 6px; padding: 8px 10px; border: 1px solid var(--card-b, #e5e7eb); border-radius: 12px; background: var(--card, #fff); box-shadow: var(--s1); overflow-x: auto; }
.im-stages__title { flex: 0 0 auto; padding: 0 8px 0 2px; color: var(--t2, #475569); font-size: 12px; font-weight: var(--font-weight-semibold); }
.im-stages__item { display: inline-flex; align-items: center; gap: 6px; flex: 0 0 auto; padding: 6px 10px; border: 1px solid transparent; border-radius: 8px; background: transparent; color: var(--t2, #475569); cursor: pointer; font-size: 12px; transition: .16s ease; }
.im-stages__item:hover { color: var(--pri, #2563eb); background: var(--pri-bg, #eff6ff); }
.im-stages__item.is-active { border-color: var(--pri-100, #dbeafe); background: var(--pri-bg, #eff6ff); color: var(--pri, #2563eb); font-weight: var(--font-weight-semibold); }
.im-stages__index { color: var(--t3, #94a3b8); font-size: 10px; font-weight: 800; }
.im-stages__item.is-active .im-stages__index { color: var(--pri, #2563eb); }
.mp-stats { display: grid; grid-template-columns: repeat(4, minmax(120px, 1fr)); gap: var(--space-3); margin-bottom: var(--space-4); }
.mp-stat { min-width: 0; padding: 14px var(--space-4); background: linear-gradient(145deg, var(--card, #fff), var(--pri-bg, #f8fbff)); border: 1px solid var(--card-b, #eee); border-radius: 12px; box-shadow: var(--s1); cursor: default; }
.mp-stat__val { color: var(--t1, #111827); font-size: 24px; line-height: 1; font-weight: var(--font-weight-bold); font-variant-numeric: tabular-nums; }
.mp-stat__lbl { color: var(--t3, #64748b); font-size: 12px; margin-top: 7px; }
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
@media (max-width: 760px) { .mp-stats { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
</style>
