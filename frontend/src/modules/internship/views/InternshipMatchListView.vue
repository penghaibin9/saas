<template>
  <ModulePageShell
    :title="formTitle || '岗位匹配'"
    :subtitle="pageSubtitle"
  >
    <template #actions>
      <AppButton v-if="formTitle" variant="ghost" @click="closeForm">返回匹配列表</AppButton>
      <AppExportButton v-else-if="!isStatsPanel && !isConflictPanel && canExport" :export-fn="exportFn">导出 Excel</AppExportButton>
      <ModuleToolbar v-if="!formTitle" :actions="toolbarActions" @action="onToolbar" />
    </template>

    <nav v-if="!formTitle" class="im-stages" aria-label="岗位匹配流程">
      <span class="im-stages__title">匹配流程</span>
      <button
        v-for="(stage, index) in panelStages"
        :key="stage.key"
        type="button"
        class="im-stages__item"
        :class="{ 'is-active': stage.key === (isRecommendationPanel ? 'recommend' : activePanel) }"
        :aria-pressed="stage.key === (isRecommendationPanel ? 'recommend' : activePanel)"
        @click="goPanel(stage.key)"
      >
        <span class="im-stages__index">0{{ index + 1 }}</span>
        <span>{{ stage.label }}</span>
      </button>
    </nav>

    <nav v-if="isRecommendationPanel && !formTitle" class="im-methods" aria-label="匹配方式">
      <button v-for="method in matchMethods" :key="method.key" type="button" :class="{ 'is-active': activePanel === method.key }" :aria-pressed="activePanel === method.key" @click="goPanel(method.key)">{{ method.label }}</button>
    </nav>
    <div v-if="isStatsPanel && !loading && !error && !formTitle" class="im-metrics"><div v-for="metric in summaryMetrics" :key="metric.label"><strong>{{ metric.value }}</strong><span>{{ metric.label }}</span></div></div>
    <div v-if="!formTitle" class="mp-stack im-workspace">
      <AdvancedFilter v-if="!isStatsPanel" v-model="filters" :fields="filterFields" @search="search" @reset="reset" />
      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <template v-else-if="isStatsPanel && matchStats">
        <div class="im-stat-breakdown">
        <div class="im-block">
          <h3 class="im-h">按状态</h3>
          <DataTable :columns="statStatusCols" :rows="matchStats.byStatus || []" row-key="status" :pagination="null" />
        </div>
        <div class="im-block">
          <h3 class="im-h">按匹配方式</h3>
          <DataTable :columns="statTypeCols" :rows="matchStats.byType || []" row-key="matchType" :pagination="null" />
        </div>
        </div>
      </template>
      <EmptyState v-else-if="!rows.length" :title="emptyTitle" :description="emptyDesc"><template #actions><AppButton variant="ghost" @click="load">刷新列表</AppButton></template></EmptyState>
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
          <TableActionColumn :actions="rowActions(row)" @action="(key) => onRowAction(key, row)" />
        </template>
      </DataTable>
    </div>

    <p v-if="formTitle && !canEditForm" class="im-readonly" role="status">当前身份可查看此表单，但没有{{ formTitle }}权限。请返回列表或由具备对应权限的经办人办理。</p>
    <section v-if="intentionVisible" class="im-editor" aria-label="登记学生意向">
      <h2>学生与意向信息</h2>
      <form class="ie-form" @submit.prevent="submitIntentionForm">
        <!-- Picker 不能包在 <label> 里：label 激活会把点击转发给选择器内部按钮 -->
        <div class="ie-fld ie-fld--full"><span class="ie-lbl">实习学生 <i>*</i></span>
          <AppUnassignedInternshipStudentPicker
            v-model="intentionForm.recordId"
            :query="{ batchId: batchStore.selectedBatchId }"
            placeholder="输入姓名或学号搜索学生"
            search-placeholder="按姓名 / 学号搜索"
            data-scope-hint="仅显示你数据范围内未落实岗位的实习学生"
          />
        </div>
        <label class="ie-fld"><span class="ie-lbl">意向城市</span><AppTextInput v-model="intentionForm.preferredCity" /></label>
        <label class="ie-fld"><span class="ie-lbl">意向行业</span><AppTextInput v-model="intentionForm.preferredIndustry" /></label>
        <div class="ie-fld ie-fld--full"><span class="ie-lbl">意向企业</span>
          <AppInternshipEnterprisePicker
            v-model="intentionForm.preferredCompanyId"
            placeholder="输入企业名称搜索（可不指定）"
            search-placeholder="按企业名称搜索"
          />
        </div>
        <label class="ie-fld ie-fld--full"><span class="ie-lbl">备注</span><AppTextarea v-model="intentionForm.intentionNote" :rows="2" /></label>
        <p v-if="formError" class="ie-err">{{ formError }}</p>
        <div class="ie-actions">
          <AppButton type="button" variant="secondary" @click="intentionVisible = false">取消</AppButton>
          <AppButton type="submit" variant="primary" :disabled="submitting || !canIntentionManage">{{ submitting ? '提交中…' : '保存草稿' }}</AppButton>
        </div>
      </form>
    </section>

    <section v-if="manualVisible" class="im-editor" aria-label="手动匹配">
      <h2>学生与岗位</h2>
      <form class="ie-form" @submit.prevent="submitManual">
        <div class="ie-fld ie-fld--full"><span class="ie-lbl">实习学生 <i>*</i></span>
          <AppUnassignedInternshipStudentPicker
            v-model="manualForm.recordId"
            :query="{ batchId: batchStore.selectedBatchId }"
            placeholder="输入姓名或学号搜索学生"
            search-placeholder="按姓名 / 学号搜索"
            data-scope-hint="仅显示你数据范围内未落实岗位的实习学生"
          />
        </div>
        <div class="ie-fld ie-fld--full"><span class="ie-lbl">上架岗位 <i>*</i></span>
          <AppInternshipPositionPicker
            v-model="manualForm.positionId"
            placeholder="输入岗位或企业名称搜索"
            search-placeholder="按岗位名称 / 企业搜索"
            data-scope-hint="仅已上架岗位可选 · 满员（余 0）岗位不可选"
          />
        </div>
        <label class="ie-fld ie-fld--full"><span class="ie-lbl">备注</span><AppTextarea v-model="manualForm.remark" :rows="2" /></label>
        <p v-if="formError" class="ie-err">{{ formError }}</p>
        <div class="ie-actions">
          <AppButton type="button" variant="secondary" @click="manualVisible = false">取消</AppButton>
          <AppButton type="submit" variant="primary" :disabled="submitting || !canMatchManual">创建待确认匹配</AppButton>
        </div>
      </form>
    </section>

    <section v-if="batchVisible" class="im-editor" aria-label="批量匹配">
      <h2>匹配清单</h2>
      <div class="ie-form">
        <p class="ie-hint">逐行选择「学生 → 岗位」，可一次提交多条；数据范围与单条匹配一致。</p>
        <div v-for="(row, i) in batchRows" :key="i" class="ie-batch-row ie-fld--full">
          <AppUnassignedInternshipStudentPicker v-model="row.recordId" :query="{ batchId: batchStore.selectedBatchId }" placeholder="选择实习学生"
            search-placeholder="按姓名 / 学号搜索" data-scope-hint="仅显示你数据范围内未落实岗位的实习学生" />
          <AppInternshipPositionPicker v-model="row.positionId" placeholder="选择岗位"
            search-placeholder="按岗位名称 / 企业搜索" data-scope-hint="仅已上架岗位可选" />
          <button type="button" class="mp-link danger ie-batch-del" :disabled="batchRows.length <= 1"
            @click="removeBatchRow(i)">删除</button>
        </div>
        <AppButton type="button" class="mp-btn ie-batch-add" @click="addBatchRow">＋ 再加一行</AppButton>
        <p v-if="formError" class="ie-err">{{ formError }}</p>
        <div class="ie-actions">
          <AppButton type="button" variant="secondary" @click="batchVisible = false">取消</AppButton>
          <AppButton type="button" variant="primary" :disabled="submitting || !canMatchBatch" @click="submitBatch">执行批量匹配</AppButton>
        </div>
      </div>
    </section>

    <AppExcelImportDrawer
      v-model:visible="importVisible"
      title="导入学生意向"
      show-account-boundary
      template-name="意向导入模板.xlsx"
      :required-fields="['学号']"
      :preview-fields="['studentNo', 'city', 'industry', 'company', 'note']"
      :download-template-fn="() => matchApi.downloadIntentionTemplate()"
      :upload-fn="(file) => matchApi.importIntentionsXlsx(file, batchStore.selectedBatchId)"
      :confirm-fn="({ rows }) => matchApi.importIntentionsConfirm(rows, batchStore.selectedBatchId)"
      :download-errors-fn="({ rows, errors }) => matchApi.downloadIntentionImportErrors(rows, errors)"
      @imported="onImported"
    />

    <AppConfirmDialog
      v-model:visible="confirm.visible"
      :title="confirm.title"
      :content="confirm.message"
      :danger="confirm.type === 'danger'"
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
import { AppExportButton, AppStatusTag, AppTextInput, AppTextarea, AppUnassignedInternshipStudentPicker, AppInternshipPositionPicker, AppInternshipEnterprisePicker } from '@/components/common'
import { AppExcelImportDrawer } from '@/components/common/excel'
import { AppButton } from '@/components/ui'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import { TableActionColumn } from '@/modules/internship/components'
import { matchApi } from '@/modules/internship/api/match.api'
import { canCode } from '@/modules/internship/composables/permission'
import { useInternshipBatchStore } from '@/stores/internshipBatch'
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
  components: { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, AppButton, AppStatusTag, AppExportButton, AppTextInput, AppTextarea, AppExcelImportDrawer, LoadingState, ErrorState, EmptyState, AppConfirmDialog, TableActionColumn, AppUnassignedInternshipStudentPicker, AppInternshipPositionPicker, AppInternshipEnterprisePicker },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      matchApi,
      loading: true, error: '', submitting: false, activePanel: 'intention',
      rows: [], total: 0, page: 1, pageSize: 10, filters: EMPTY_FILTERS(), appliedFilters: EMPTY_FILTERS(),
      matchStats: null, loadTicket: 0,
      intentionForm: { recordId: '', preferredCity: '', preferredIndustry: '', preferredCompanyId: '', intentionNote: '' },
      manualForm: { recordId: '', positionId: '', remark: '' },
      batchRows: [{ recordId: '', positionId: '' }],
      importVisible: false,
      formError: '',
      confirm: { visible: false, title: '', message: '', type: 'primary', confirmText: '确认', requireReason: false, reasonLabel: '原因', action: null, row: null },
      statStatusCols: [{ key: 'label', title: '状态' }, { key: 'count', title: '数量' }],
      statTypeCols: [{ key: 'label', title: '匹配方式' }, { key: 'count', title: '数量' }]
    }
  },
  computed: {
    formTitle() { return { intention: '登记学生意向', manual: '手动匹配', batch: '批量匹配' }[this.$route.query.form] || '' },
    intentionVisible: { get() { return this.$route.query.form === 'intention' }, set(value) { value ? this.openForm('intention') : this.closeForm() } },
    manualVisible: { get() { return this.$route.query.form === 'manual' }, set(value) { value ? this.openForm('manual') : this.closeForm() } },
    batchVisible: { get() { return this.$route.query.form === 'batch' }, set(value) { value ? this.openForm('batch') : this.closeForm() } },
    isRecommendationPanel() { return ['recommend', 'major', 'enterprise', 'manual', 'batch'].includes(this.activePanel) },
    matchMethods() { return [{ key: 'recommend', label: '全部推荐' }, { key: 'major', label: '专业匹配' }, { key: 'enterprise', label: '企业匹配' }, { key: 'manual', label: '手动匹配' }, { key: 'batch', label: '批量匹配' }] },
    batchStore() { return useInternshipBatchStore() },
    canMatchManual() { return canCode(this.ctx, 'internship.match.manual') },
    canMatchBatch() { return canCode(this.ctx, 'internship.match.batch') },
    canIntentionManage() { return canCode(this.ctx, 'internship.match.intention.manage') },
    canEditForm() { return this.intentionVisible ? this.canIntentionManage : this.manualVisible ? this.canMatchManual : this.batchVisible ? this.canMatchBatch : false },
    canExport() { return canCode(this.ctx, 'internship.match.export') },
    canRead() { return canCode(this.ctx, this.isIntentionPanel ? 'internship.match.intention.view' : this.isConflictPanel ? 'internship.match.conflict.view' : 'internship.match.result.view') },
    panelStages() {
      return [
        { key: 'intention', label: '意向登记' },
        { key: 'recommend', label: '推荐结果' },
        { key: 'confirm', label: '确认落岗' },
        { key: 'conflict', label: '冲突处置' },
        { key: 'results', label: '结果台账' },
        { key: 'stats', label: '匹配统计' }
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
      if (this.isConflictPanel) return [{ key: 'keyword', label: '关键词', type: 'text', placeholder: '学生 / 岗位 / 企业' }]
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
          { key: 'runMajor', label: '生成专业推荐', variant: 'primary', disabled: denyManual, disabledReason: '无匹配操作权限' }
        ]
      }
      if (this.activePanel === 'enterprise') {
        return [
          { key: 'runEnterprise', label: '生成企业推荐', variant: 'primary', disabled: denyManual, disabledReason: '无匹配操作权限' }
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
      if (this.formTitle) return this.intentionVisible ? '保存意向草稿后，可回到列表提交。' : '选择学生与岗位，创建后进入待确认列表办理落岗。'
      return '登记意向、生成推荐，核对岗位后确认落岗。'
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
      if (this.isConflictPanel) return '暂无待处置冲突'
      return this.isIntentionPanel ? '暂无学生意向' : '暂无匹配记录'
    },
    emptyDesc() {
      if (this.isConflictPanel) return '当前筛选下没有冲突记录，可在结果台账查看其他匹配。'
      return this.isIntentionPanel ? '可登记意向或导入 Excel' : '可在推荐结果中选择专业、企业、手动或批量匹配'
    }
  },
  watch: {
    '$route.fullPath': {
      immediate: true,
      handler() {
        this.applyPanel(String(this.$route.query.panel || 'intention'))
      }
    }
  },
  beforeUnmount() { this.loadTicket++ },
  methods: {
    openForm(form) { this.$router.push({ path: this.$route.path, query: { ...this.$route.query, form } }) },
    closeForm() { const query = { ...this.$route.query }; delete query.form; this.$router.push({ path: this.$route.path, query }) },
    applyPanel(panel) {
      const known = Object.keys(PANEL_HINTS)
      this.activePanel = known.includes(panel) ? panel : 'intention'
      this.filters = EMPTY_FILTERS()
      if (this.activePanel === 'confirm') this.filters.status = 'PENDING_CONFIRM'
      if (this.activePanel === 'major') this.filters.matchType = 'AUTO_MAJOR'
      if (this.activePanel === 'enterprise') this.filters.matchType = 'AUTO_ENTERPRISE'
      if (this.activePanel === 'manual') this.filters.matchType = 'MANUAL'
      if (this.activePanel === 'batch') this.filters.matchType = 'BATCH'
      if (this.activePanel === 'recommend') this.filters.status = 'RECOMMENDED'
      for (const key of Object.keys(this.filters)) {
        if (typeof this.$route.query[key] === 'string') this.filters[key] = this.$route.query[key]
      }
      const page = Number(this.$route.query.page)
      this.appliedFilters = { ...this.filters }
      this.page = Number.isSafeInteger(page) && page > 0 ? page : 1
      this.load()
    },
    goPanel(panel) {
      if (this.activePanel === panel) return
      this.$router.push({ path: this.$route.path, query: this.batchStore.withBatchQuery({ panel }) })
    },
    async load() {
      const ticket = ++this.loadTicket
      const batchId = this.batchStore.selectedBatchId
      const current = () => ticket === this.loadTicket && batchId === this.batchStore.selectedBatchId
      this.rows = []; this.total = 0; this.matchStats = null
      this.loading = true
      this.error = ''
      if (!batchId || !this.canRead) {
        this.loading = false; this.error = !batchId ? '请先选择实习批次' : '当前身份无权查看此匹配分区'
        return
      }
      try {
        if (this.isStatsPanel) {
          const res = await matchApi.getStats({ batchId: this.batchStore.selectedBatchId })
          if (!current()) return
          if (res.code === 0) this.matchStats = res.data
          else this.error = res.message
          this.rows = []
          this.total = 0
        } else if (this.isIntentionPanel) {
          const res = await matchApi.getIntentions({ ...this.appliedFilters, page: this.page, pageSize: this.pageSize, batchId })
          if (!current()) return
          if (res.code === 0) { this.rows = res.data.list; this.total = res.data.total }
          else this.error = res.message
        } else if (this.isConflictPanel) {
          const res = await matchApi.getConflicts({ keyword: this.appliedFilters.keyword, page: this.page, pageSize: this.pageSize, batchId })
          if (!current()) return
          if (res.code === 0) { this.rows = res.data.list; this.total = res.data.total }
          else this.error = res.message
        } else {
          const params = { ...this.appliedFilters, page: this.page, pageSize: this.pageSize, batchId }
          const res = await matchApi.getResults(params)
          if (!current()) return
          if (res.code === 0) { this.rows = res.data.list; this.total = res.data.total }
          else this.error = res.message
        }
      } catch (err) {
        if (current()) this.error = err.message || '匹配数据加载失败，请重试'
      } finally {
        if (ticket === this.loadTicket) this.loading = false
      }
    },
    syncFilters() {
      const location = { path: this.$route.path, query: { ...this.$route.query, ...this.appliedFilters, page: this.page } }
      if (this.$router.resolve(location).fullPath === this.$route.fullPath) this.load()
      else this.$router.replace(location)
    },
    search() { this.appliedFilters = { ...this.filters }; this.page = 1; this.syncFilters() },
    reset() { this.filters = EMPTY_FILTERS(); this.search() },
    turnPage(p) { this.page = p; this.syncFilters() },
    async exportFn() {
      const batchId = this.batchStore.selectedBatchId, panel = this.activePanel, scope = JSON.stringify(this.ctx)
      if (this.isConflictPanel) return { code: 1, message: '请到结果台账导出匹配记录' }
      if (!this.canExport || !batchId) return { code: 1, message: '请确认导出权限并选择实习批次' }
      const params = { ...this.appliedFilters, batchId }
      const res = await (this.isIntentionPanel ? matchApi.exportIntentions(params) : matchApi.exportMatches(params))
      return batchId === this.batchStore.selectedBatchId && panel === this.activePanel && scope === JSON.stringify(this.ctx) && this.canExport ? res : { code: 1, message: '办理范围已切换，请重新导出' }
    },
    async onToolbar(key) {
      if (this.submitting) return
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
          const res = await matchApi.runMajor({ batchId: this.batchStore.selectedBatchId })
          if (res.code === 0) { toast.success(`专业匹配完成 · ${res.data.created} 条`); this.load() }
          else toast.error(res.message)
        } finally { this.submitting = false }
      }
      if (key === 'runEnterprise') {
        this.submitting = true
        try {
          const res = await matchApi.runEnterprise({ batchId: this.batchStore.selectedBatchId })
          if (res.code === 0) { toast.success(`企业匹配完成 · ${res.data.created} 条`); this.load() }
          else toast.error(res.message)
        } finally { this.submitting = false }
      }
      if (key === 'manual') {
        this.manualForm = { recordId: '', positionId: '', remark: '' }
        this.manualVisible = true
      }
      if (key === 'batch') { this.batchRows = [{ recordId: '', positionId: '' }]; this.formError = ''; this.batchVisible = true }
      if (key === 'refreshStats') this.load()
    },
    async submitIntentionForm() {
      if (this.submitting || !this.canIntentionManage) return
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
      if (this.submitting || !this.canMatchManual) return
      this.formError = ''
      if (!this.manualForm.recordId || !this.manualForm.positionId) { this.formError = '学生与岗位必选'; return }
      this.submitting = true
      try {
        const res = await matchApi.manualMatch(this.manualForm)
        if (res.code === 0) { toast.success('已创建待确认匹配'); this.manualVisible = false; this.load() }
        else this.formError = res.message
      } finally { this.submitting = false }
    },
    addBatchRow() { this.batchRows.push({ recordId: '', positionId: '' }) },
    removeBatchRow(i) { if (this.batchRows.length > 1) this.batchRows.splice(i, 1) },
    async submitBatch() {
      if (this.submitting || !this.canMatchBatch) return
      this.formError = ''
      const pairs = this.batchRows
        .map((r) => ({ recordId: String(r.recordId || ''), positionId: String(r.positionId || '') }))
        .filter((p) => p.recordId && p.positionId)
      if (!pairs.length) { this.formError = '请至少完整选择一行「学生 + 岗位」'; return }
      const dup = pairs.map((p) => p.recordId).filter((v, i, a) => a.indexOf(v) !== i)
      if (dup.length) { this.formError = '同一名学生在本次提交里出现多次，请先删掉重复行'; return }
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
          const res = await matchApi.confirmMatch(row.id, {
            expectedVersion: row.version,
            recordExpectedVersion: row.recordVersion
          })
          if (res.code === 0) { toast.success('已确认并分配岗位'); this.confirm.visible = false; this.load() }
          else toast.error(res.message)
        }
        if (action === 'REJECT') {
          const res = await matchApi.rejectMatch(row.id, reason || '')
          if (res.code === 0) { toast.success('已驳回'); this.confirm.visible = false; this.load() }
          else toast.error(res.message)
        }
      } finally { this.submitting = false }
    },
    rowActions(row) {
      if (this.isIntentionPanel) {
        const actions = []
        if (row.status === 'DRAFT' || row.status === 'WITHDRAWN') {
          actions.push({ key: 'submitIntention', label: '提交', disabled: !this.canIntentionManage })
        }
        if (row.status === 'SUBMITTED') {
          actions.push({ key: 'withdrawIntention', label: '撤回', disabled: !this.canIntentionManage })
        }
        return actions
      }
      const actions = []
      if (['RECOMMENDED', 'PENDING_CONFIRM', 'CONFLICT'].includes(row.status)) {
        actions.push({ key: 'confirm', label: '确认落岗', disabled: !this.canMatchManual, disabledReason: this.canMatchManual ? '' : '无匹配落岗权限' })
        actions.push({ key: 'reject', label: '驳回', danger: true, disabled: !this.canMatchManual, disabledReason: this.canMatchManual ? '' : '无匹配落岗权限' })
      }
      return actions
    },
    onRowAction(key, row) {
      if (key === 'submitIntention') return this.doSubmitIntention(row)
      if (key === 'withdrawIntention') return this.doWithdrawIntention(row)
      if (key === 'confirm') return this.askConfirm(row)
      if (key === 'reject') return this.askReject(row)
    }
  }
}
</script>

<style scoped>
.im-workspace { background: var(--card, #fff); border: 1px solid var(--card-b, #e5e7eb); border-radius: 12px; overflow: hidden; }
.im-methods { display: flex; gap: 8px; padding: 0 4px; flex-wrap: wrap; }
.im-methods button { border: 0; background: transparent; padding: 8px 12px; color: var(--t2, #475569); cursor: pointer; border-radius: 6px; }
.im-methods button.is-active { background: var(--pri-bg, #eff6ff); color: var(--pri, #2563eb); font-weight: 600; }
.im-methods button:focus-visible,.im-stages__item:focus-visible { outline:2px solid var(--pri,#2563eb);outline-offset:2px; }
.im-readonly { padding:12px 16px;border-left:3px solid var(--pri,#2563eb);background:var(--pri-bg,#eff6ff);font-size:13px;line-height:1.7;color:var(--t2,#475569); }
.im-editor { width: 100%; max-width: 960px; padding: 24px; border: 1px solid var(--card-b, #e5e7eb); border-radius: 12px; background: var(--card, #fff); box-sizing: border-box; }
.im-editor h2 { margin: 0 0 24px; font-size: 16px; }
.im-editor .ie-actions { border-top: 1px solid var(--card-b, #e5e7eb); padding-top: 20px; }
.im-metrics { display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:16px;padding:16px 20px;background:var(--card,#fff);border:1px solid var(--card-b,#e5e7eb);border-radius:8px; }
.im-stat-breakdown { display:grid;grid-template-columns:1fr 1fr;gap:20px;padding:16px;min-width:0; }
.im-stat-breakdown .im-block { min-width:0;margin:0; }
.im-stat-breakdown .im-h { margin:0 0 12px;font-size:14px; }
@media(max-width:700px){.im-stat-breakdown{grid-template-columns:1fr}.im-metrics{grid-template-columns:repeat(2,minmax(0,1fr))}}
.im-metrics > div { display: grid; gap: 4px; }
.im-metrics strong { font-size: 24px; }
.im-metrics span { color: var(--t2, #475569); font-size: 13px; }

.ie-batch-row { display:flex; gap:var(--space-2); align-items:center; margin-bottom:var(--space-2); }
.ie-batch-row > *:first-child, .ie-batch-row > *:nth-child(2) { flex:1; min-width:0; }
.ie-batch-del { white-space:nowrap; }
.ie-batch-add { margin-bottom:var(--space-2); }
.im-stages { display: flex; align-items: center; gap: 6px; padding: 8px 10px; border: 1px solid var(--card-b, #e5e7eb); border-radius: 12px; background: var(--card, #fff); box-shadow: var(--s1); overflow-x: auto; }
.im-stages__title { flex: 0 0 auto; padding: 0 8px 0 2px; color: var(--t2, #475569); font-size: 12px; font-weight: var(--font-weight-semibold); }
.im-stages__item { display: inline-flex; align-items: center; gap: 6px; flex: 0 0 auto; padding: 6px 10px; border: 1px solid transparent; border-radius: 8px; background: transparent; color: var(--t2, #475569); cursor: pointer; font-size: 12px; transition: .16s ease; }
.im-stages__item:hover { color: var(--pri, #2563eb); background: var(--pri-bg, #eff6ff); }
.im-stages__item.is-active { border-color: var(--pri-100, #dbeafe); background: var(--pri-bg, #eff6ff); color: var(--pri, #2563eb); font-weight: var(--font-weight-semibold); }
.im-stages__index { color: var(--t3, #94a3b8); font-size: 10px; font-weight: 800; }
.im-stages__item.is-active .im-stages__index { color: var(--pri, #2563eb); }
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
