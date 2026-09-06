<template>
  <ModulePageShell
    :title="pageTitle"
    :subtitle="pageSubtitle"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <div class="gd-actions">
        <ModuleToolbar :actions="toolbarActions" @action="onToolbar" />
        <AppExportButton v-if="exportVisible" :export-fn="exportStudentsFn">导出 Excel</AppExportButton>
      </div>
    </template>

    <div class="mp-stack gd-student-page">
      <section v-if="hasBatch" class="gd-student-hero" aria-label="毕设学生工作结论">
        <div class="gd-student-hero__copy">
          <span>当前视图结论</span>
          <strong>{{ workConclusion }}</strong>
          <p>{{ workHint }}</p>
        </div>
        <div class="gd-student-hero__metrics" aria-label="当前批次学生统计">
          <div v-for="metric in heroMetrics" :key="metric.label">
            <b>{{ metric.value }}</b><span>{{ metric.label }}</span>
          </div>
        </div>
      </section>

      <section v-if="hasBatch && activePanel === 'roster'" class="gd-import-contract" aria-label="学生导入四步闭环">
        <span>名单导入</span>
        <ol><li>下载模板</li><li>上传并预览</li><li>下载错误行</li><li>确认导入并留痕</li></ol>
      </section>

      <section v-if="hasBatch && activePanel === 'grad-qual'" class="gd-readonly-banner" role="status">
        <div><strong>毕业资格是教务只读镜像</strong><span>毕设中心只展示教务侧最新预审结果与说明，不提供“通过/不通过”写入，避免形成第二套毕业资格主档。</span></div>
        <small>需要更正时请在教务毕业资格流程处理，回到本页刷新结果。</small>
      </section>

      <div class="mp-tabs gd-primary-tabs" aria-label="学生主视图">
        <button
          v-for="group in primaryGroups"
          :key="group.key"
          class="mp-tab"
          :class="{ 'is-active': activeGroupKey === group.key }"
          @click="switchGroup(group)"
        >{{ group.label }}</button>
      </div>
      <div v-if="activeGroupPanels.length > 1" class="gd-local-views" aria-label="当前主视图的细分任务">
        <span>当前视图</span>
        <button
          v-for="panel in activeGroupPanels"
          :key="panel.key"
          type="button"
          :class="{ 'is-active': activePanel === panel.key }"
          @click="switchPanel(panel.key)"
        >{{ panel.label }}</button>
      </div>

      <AdvancedFilter v-if="hasBatch" v-model="filters" :fields="filterFields" @search="search" @reset="reset" />
      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" :title="emptyTitle" :description="emptyDesc">
        <template v-if="showRosterEmptyActions" #actions>
          <button class="mp-btn mp-btn--primary" :disabled="!writeEnabled" @click="onToolbar('create')">＋ 建档</button>
          <button class="mp-btn" :disabled="!writeEnabled" @click="onToolbar('import')">导入 Excel</button>
          <button class="mp-btn" @click="$router.push('/admin/help?topic=gd-card-students')">怎么导入名单？</button>
        </template>
      </EmptyState>
      <DataTable
        v-else
        :columns="columns"
        :rows="rows"
        row-key="id"
        :selectable="selectablePanel"
        v-model:selected="selectedIds"
        :pagination="{ page, pageSize, total }"
        @page-change="turnPage"
      >
        <template #cell-student="{ row }">
          <div class="mp-cell-main">{{ row.name }}</div>
          <div class="mp-cell-sub"><AppSensitiveText :value="row.studentNo" type="generic" /> · {{ row.className }}</div>
        </template>
        <template #cell-batch="{ row }">
          <span v-if="row.batchName">{{ row.batchName }}</span><span v-else class="mp-note">未关联批次</span>
        </template>
        <template #cell-topic="{ row }">
          <template v-if="row.topicId">
            <div class="mp-cell-main gd-topic-title">{{ row.topicTitle }}</div>
            <div class="mp-cell-sub">指导教师：{{ row.advisorName || '—' }}</div>
          </template>
          <span v-else class="mp-note">未选题</span>
        </template>
        <template #cell-stage="{ row }"><StatusTag :type="row.stageTone || stageTone(row.stage)" :label="row.stageLabel" dot /></template>
        <template #cell-risk="{ row }"><RiskTag v-if="row.riskLevel !== 'NONE'" :level="row.riskLevel" /><span v-else class="mp-note">无</span></template>
        <template #cell-eligibility="{ row }"><StatusTag :type="row.eligibilityTone || eligTone(row.eligibilityStatus)" :label="row.eligibilityLabel" /></template>
        <template #cell-group="{ row }"><span v-if="row.studentGroup">{{ row.studentGroup }}</span><span v-else class="mp-note">未分组</span></template>
        <template #cell-materials="{ row }">
          <div class="mp-cell-main">开题：{{ row.proposalStatusLabel }}</div>
          <div class="mp-cell-sub">成果：{{ row.finalStatusLabel }} · 缺口：{{ row.materialGap }}</div>
        </template>
        <template #cell-defense="{ row }"><span v-if="row.defenseGroupId">{{ row.defenseGroup }}</span><span v-else class="mp-note">未分配答辩组</span></template>
        <template #cell-gradQual="{ row }">
          <StatusTag :type="row.gradQualTone || gradQualTone(row.gradQualStatus)" :label="row.gradQualLabel" />
          <div class="mp-cell-sub">教务只读镜像<template v-if="row.gradQualNote"> · {{ row.gradQualNote }}</template></div>
        </template>
        <template #cell-actions="{ row }">
          <button class="mp-link" @click="openDetail(row)">详情</button>
          <template v-if="activePanel === 'roster' || activePanel === 'topic' || activePanel === 'mentor'">
            <button v-if="row.stage !== 'ARCHIVED'" class="mp-link gd-row-action" @click="openAssignTopic(row)">{{ row.topicId ? '调题' : '分配选题' }}</button>
            <button v-if="row.stage !== 'ARCHIVED' && !row.advisorName" class="mp-link gd-row-action" @click="openAdvisor(row)">分配导师</button>
          </template>
          <template v-if="activePanel === 'eligibility' && row.stage !== 'ARCHIVED'">
            <button v-if="row.eligibilityStatus !== 'QUALIFIED'" class="mp-link gd-row-action" @click="askEligibility(row, 'QUALIFIED')">认定合格</button>
            <button v-if="row.eligibilityStatus !== 'UNQUALIFIED'" class="mp-link gd-row-action" @click="askEligibility(row, 'UNQUALIFIED')">认定不合格</button>
          </template>
          <button v-if="activePanel === 'grouping' && row.stage !== 'ARCHIVED'" class="mp-link gd-row-action" @click="openGroup(row)">设置分组</button>
          <button v-if="activePanel === 'defense' && row.stage !== 'ARCHIVED'" class="mp-link gd-row-action" @click="openDefense(row)">分配答辩组</button>
          <span v-if="activePanel === 'grad-qual'" class="gd-readonly-action">教务只读</span>
          <button v-if="activePanel === 'archive' && row.stage !== 'ARCHIVED'" class="mp-link gd-row-action" @click="askArchiveOne(row)">归档</button>
        </template>
      </DataTable>
      <p v-if="hasBatch" class="mp-note">列表、统计、导出均绑定当前批次与当前数据范围；页码和关键词写入 URL，返回时恢复原工作位置。</p>
    </div>

    <AppExcelImportDrawer
      v-model:visible="importVisible"
      title="导入毕设学生"
      show-account-boundary
      template-name="毕设学生导入模板.xlsx"
      :required-fields="['学号']"
      :preview-fields="['studentNo', 'batchNo', 'advisorName']"
      :download-template-fn="() => gdStudentApi.downloadImportTemplate()"
      :upload-fn="(file) => gdStudentApi.uploadImportXlsx(file)"
      :confirm-fn="({ rows, previewToken }) => gdStudentApi.importConfirm(rows, previewToken)"
      :download-errors-fn="({ rows, errors }) => gdStudentApi.downloadImportErrors(rows, errors)"
      @imported="onImported"
    />

    <AppConfirmDialog
      v-model:visible="confirm.visible" :title="confirm.title" :message="confirm.message"
      :type="confirm.type" :confirm-text="confirm.confirmText" :require-reason="confirm.requireReason"
      :reason-label="confirm.reasonLabel" :submitting="submitting" @confirm="onConfirm"
    />
    <AppPageGuide guide-key="graduation.gd-students" />
  </ModulePageShell>
</template>

<script>
/** 毕设学生列表：真实学生主档投影；毕业资格为教务只读镜像。 */
import {
  ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable,
  StatusTag, RiskTag, LoadingState, ErrorState, EmptyState
} from '@/components/business'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import { AppSensitiveText, AppExportButton, AppPageGuide } from '@/components/common'
import { AppExcelImportDrawer } from '@/components/common/excel'
import { gdStudentApi } from '@/modules/graduation/api/graduation-student.api'
import {
  GD_STAGE, GD_RISK_LEVEL, HAS_TOPIC, GD_ELIGIBILITY, GD_GRAD_QUAL,
  HAS_DEFENSE_GROUP, MATERIAL_COMPLETE, ARCHIVE_VIEW
} from '@/modules/graduation/constants/graduation-student.constants'
import { buildStudentQuery, exportFilenameHint } from '@/modules/graduation/utils/queryParams'
import { useGraduationBatchStore } from '@/stores/graduationBatch'
import { toast } from '@/utils/toast'

const EMPTY_FILTERS = () => ({
  keyword: '', stage: '', riskLevel: '', hasTopic: '',
  eligibility: '', studentGroup: '', hasDefenseGroup: '', gradQualStatus: '',
  materialComplete: '', archiveView: '', dateStart: '', dateEnd: ''
})
const PANEL_PRESETS = {
  roster: () => EMPTY_FILTERS(),
  progress: () => ({ ...EMPTY_FILTERS(), stage: 'GUIDING' }),
  risk: () => ({ ...EMPTY_FILTERS(), riskLevel: 'HIGH' }),
  mentor: () => ({ ...EMPTY_FILTERS(), hasTopic: 'true' }),
  topic: () => ({ ...EMPTY_FILTERS(), hasTopic: 'false' }),
  eligibility: () => ({ ...EMPTY_FILTERS(), eligibility: 'PENDING' }),
  grouping: () => EMPTY_FILTERS(),
  materials: () => ({ ...EMPTY_FILTERS(), materialComplete: 'false' }),
  defense: () => ({ ...EMPTY_FILTERS(), hasDefenseGroup: 'false' }),
  'grad-qual': () => ({ ...EMPTY_FILTERS(), gradQualStatus: 'UNKNOWN' }),
  archive: () => ({ ...EMPTY_FILTERS(), archiveView: 'candidates' })
}
const PANEL_TABS = [
  { key: 'roster', label: '学生名单' }, { key: 'progress', label: '学生进度' },
  { key: 'topic', label: '未选题' }, { key: 'eligibility', label: '资格认定' },
  { key: 'grouping', label: '过程分组' }, { key: 'materials', label: '材料缺口' },
  { key: 'defense', label: '答辩组' }, { key: 'grad-qual', label: '毕业资格联动' },
  { key: 'archive', label: '归档' }, { key: 'risk', label: '风险学生' },
  { key: 'mentor', label: '已选题导师' }
]
const PRIMARY_GROUPS = [
  { key: 'roster', label: '名单', defaultPanel: 'roster', panels: ['roster'] },
  { key: 'progress', label: '进度与风险', defaultPanel: 'progress', panels: ['progress', 'risk'] },
  { key: 'relations', label: '关系与资格', defaultPanel: 'topic', panels: ['topic', 'mentor', 'eligibility', 'grouping'] },
  { key: 'materials', label: '材料与答辩', defaultPanel: 'materials', panels: ['materials', 'defense'] },
  { key: 'closure', label: '收口与归档', defaultPanel: 'grad-qual', panels: ['grad-qual', 'archive'] }
]
const PANEL_HINTS = {
  roster: '建档、导入、导出全量名单', progress: '按真实节点查看推进情况', risk: '处理高风险学生',
  mentor: '查看已选题学生与导师关系', topic: '处理未选题学生', eligibility: '进行毕设资格认定',
  grouping: '维护过程分组', materials: '核对开题与成果缺口', defense: '处理未分配答辩组学生',
  'grad-qual': '只读查看教务毕业资格预审', archive: '处理待归档与已归档学生'
}
const COLUMN_PRESETS = {
  default: [
    { key: 'student', title: '学生' }, { key: 'batch', title: '批次' },
    { key: 'topic', title: '课题 / 导师' }, { key: 'stage', title: '节点状态' },
    { key: 'risk', title: '风险' }, { key: 'actions', title: '操作', width: '220px' }
  ],
  eligibility: [
    { key: 'student', title: '学生' }, { key: 'batch', title: '批次' },
    { key: 'eligibility', title: '毕设资格' }, { key: 'stage', title: '节点状态' },
    { key: 'actions', title: '操作', width: '240px' }
  ],
  grouping: [
    { key: 'student', title: '学生' }, { key: 'group', title: '过程分组' },
    { key: 'batch', title: '批次' }, { key: 'topic', title: '课题' },
    { key: 'actions', title: '操作', width: '160px' }
  ],
  materials: [
    { key: 'student', title: '学生' }, { key: 'materials', title: '材料状态' },
    { key: 'stage', title: '节点' }, { key: 'batch', title: '批次' },
    { key: 'actions', title: '操作', width: '100px' }
  ],
  defense: [
    { key: 'student', title: '学生' }, { key: 'defense', title: '答辩组' },
    { key: 'stage', title: '节点' }, { key: 'batch', title: '批次' },
    { key: 'actions', title: '操作', width: '160px' }
  ],
  'grad-qual': [
    { key: 'student', title: '学生' }, { key: 'gradQual', title: '教务毕业资格镜像' },
    { key: 'eligibility', title: '毕设资格' }, { key: 'stage', title: '节点' },
    { key: 'actions', title: '操作', width: '120px' }
  ],
  archive: [
    { key: 'student', title: '学生' }, { key: 'stage', title: '节点' },
    { key: 'materials', title: '材料' }, { key: 'gradQual', title: '毕业资格' },
    { key: 'actions', title: '操作', width: '120px' }
  ]
}
const STAGE_TONE = {
  TOPIC_SELECTING: 'default', TASKBOOK_CONFIRM: 'info', GUIDING: 'processing', MIDTERM: 'warning',
  FINAL_CHECK: 'processing', DEFENSE: 'warning', COMPLETED: 'info', ARCHIVED: 'success'
}

function errorText(error, fallback) { return error?.message || fallback }

export default {
  name: 'GraduationStudentListView',
  components: { AppPageGuide, ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag, RiskTag, LoadingState, ErrorState, EmptyState, AppConfirmDialog, AppExcelImportDrawer, AppSensitiveText, AppExportButton },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      batchStore: useGraduationBatchStore(),
      loading: true, error: '', submitting: false, activePanel: 'roster', routeReady: false,
      primaryGroups: PRIMARY_GROUPS, panelTabs: PANEL_TABS,
      rows: [], total: 0, page: 1, pageSize: 10, filters: EMPTY_FILTERS(),
      stats: null, statsError: '', loadToken: 0, statsToken: 0,
      selectedIds: [], groupOpts: [], importVisible: false, gdStudentApi,
      confirm: { visible: false, title: '', message: '', type: 'primary', confirmText: '确认', requireReason: false, reasonLabel: '原因', action: null, row: null, payload: null }
    }
  },
  computed: {
    activeGroupKey() { return PRIMARY_GROUPS.find((group) => group.panels.includes(this.activePanel))?.key || 'roster' },
    activeGroupPanels() {
      const group = PRIMARY_GROUPS.find((item) => item.key === this.activeGroupKey) || PRIMARY_GROUPS[0]
      return group.panels.map((key) => PANEL_TABS.find((panel) => panel.key === key)).filter(Boolean)
    },
    activePanelLabel() { return PANEL_TABS.find((panel) => panel.key === this.activePanel)?.label || '学生名单' },
    hasBatch() { return !!this.batchStore.selectedBatchId },
    writeEnabled() { return this.ctx.writeEnabled !== false },
    filtered() { return Object.keys(this.filters).some((key) => key !== 'archiveView' && this.filters[key]) },
    showRosterEmptyActions() { return this.hasBatch && this.activePanel === 'roster' && !this.filtered },
    columns() { return COLUMN_PRESETS[this.activePanel] || COLUMN_PRESETS.default },
    selectablePanel() { return this.activePanel === 'grouping' || this.activePanel === 'archive' },
    filterFields() {
      const groupOpts = this.groupOpts.map((group) => ({ value: group, label: group }))
      const base = [{ key: 'keyword', label: '关键词', type: 'text', placeholder: '姓名 / 学号 / 课题' }]
      const panelFields = {
        roster: [{ key: 'stage', label: '节点状态', type: 'select', options: GD_STAGE }, { key: 'riskLevel', label: '风险等级', type: 'select', options: GD_RISK_LEVEL }, { key: 'hasTopic', label: '选题', type: 'select', options: HAS_TOPIC }],
        progress: [{ key: 'stage', label: '节点状态', type: 'select', options: GD_STAGE }],
        risk: [{ key: 'riskLevel', label: '风险等级', type: 'select', options: GD_RISK_LEVEL }],
        mentor: [{ key: 'hasTopic', label: '选题', type: 'select', options: HAS_TOPIC }],
        topic: [{ key: 'hasTopic', label: '选题', type: 'select', options: HAS_TOPIC }],
        eligibility: [{ key: 'eligibility', label: '毕设资格', type: 'select', options: GD_ELIGIBILITY }],
        grouping: [{ key: 'studentGroup', label: '过程分组', type: 'select', options: groupOpts }],
        materials: [{ key: 'materialComplete', label: '材料', type: 'select', options: MATERIAL_COMPLETE }],
        defense: [{ key: 'hasDefenseGroup', label: '答辩组', type: 'select', options: HAS_DEFENSE_GROUP }],
        'grad-qual': [{ key: 'gradQualStatus', label: '毕业资格', type: 'select', options: GD_GRAD_QUAL }],
        archive: [{ key: 'archiveView', label: '归档视图', type: 'select', options: ARCHIVE_VIEW }]
      }
      return [...base, ...(panelFields[this.activePanel] || panelFields.roster)]
    },
    toolbarActions() {
      const writeOff = !this.writeEnabled
      const actions = []
      if (this.activePanel === 'roster') actions.push({ key: 'create', label: '＋ 建档', variant: 'primary', disabled: writeOff }, { key: 'import', label: '导入 Excel', disabled: writeOff })
      if (this.activePanel === 'grouping') actions.push({ key: 'batchGroup', label: '批量分组', variant: 'primary', disabled: writeOff || !this.selectedIds.length })
      if (this.activePanel === 'archive' && this.filters.archiveView !== 'archived') actions.push({ key: 'batchArchive', label: '批量归档', variant: 'primary', disabled: writeOff || !this.selectedIds.length })
      return actions
    },
    exportVisible() { return this.hasBatch && this.activePanel !== 'grouping' && this.activePanel !== 'archive' },
    pageTitle() { return this.batchStore.selectedBatchName ? `毕设学生 · ${this.batchStore.selectedBatchName}` : '毕设学生' },
    pageSubtitle() {
      if (!this.hasBatch) return '请先在顶部选择或创建毕设批次'
      const selected = this.selectablePanel && this.selectedIds.length ? ` · 已选 ${this.selectedIds.length}` : ''
      return `${this.batchStore.selectedBatchName || '当前批次'} · ${this.activePanelLabel} ${this.total} 人${selected} · 学号默认脱敏`
    },
    heroMetrics() {
      const stats = this.stats || {}
      return [
        { label: '批次学生', value: stats.total ?? '—' },
        { label: '未选题', value: stats.withoutTopic ?? '—' },
        { label: '高风险', value: stats.highRisk ?? '—' },
        { label: '待认定', value: stats.pendingEligibility ?? '—' },
        { label: '未分答辩组', value: stats.withoutDefenseGroup ?? '—' },
        { label: '已归档', value: stats.archived ?? '—' }
      ]
    },
    workConclusion() {
      const stats = this.stats || {}
      if (this.statsError) return `当前查看「${this.activePanelLabel}」${this.total} 人；全量统计暂未读取。`
      const map = {
        roster: `当前批次共 ${stats.total ?? this.total} 名学生，名单是后续选题、导师、材料和答辩的唯一入口。`,
        progress: `当前进度视图 ${this.total} 人；按服务端节点筛选处理，不用当前页推导全量。`,
        risk: `当前批次高风险 ${stats.highRisk ?? this.total} 人，优先进入真实风险处置。`,
        topic: `当前批次未选题 ${stats.withoutTopic ?? this.total} 人，应先建立真实选题关系。`,
        mentor: `当前查看已选题学生与导师关系 ${this.total} 人。`,
        eligibility: `当前批次待毕设资格认定 ${stats.pendingEligibility ?? this.total} 人。`,
        grouping: `当前查看过程分组 ${this.total} 人，可选择后批量分组。`,
        materials: `当前材料缺口队列 ${this.total} 人，逐人进入详情核验。`,
        defense: `当前批次未分答辩组 ${stats.withoutDefenseGroup ?? this.total} 人。`,
        'grad-qual': '毕业资格只读展示教务预审真值，本页不写入、不维护第二套主档。',
        archive: `当前查看归档队列 ${this.total} 人；归档仍受材料备案和未关闭风险校验。`
      }
      return map[this.activePanel] || `当前查看 ${this.total} 人。`
    },
    workHint() {
      if (this.activePanel === 'grad-qual') return '刷新只会重新读取教务镜像；结果更正必须回到教务资格流程。'
      return `${PANEL_HINTS[this.activePanel] || '处理当前学生队列'}；列表数据来自服务端分页。`
    },
    emptyTitle() {
      if (!this.hasBatch) return '请先选择或创建毕设批次'
      const labels = { eligibility: '暂无待认定学生', materials: '暂无材料缺口学生', defense: '暂无待分配答辩组学生', archive: '暂无归档记录', risk: '暂无高风险学生', topic: '暂无未选题学生' }
      return labels[this.activePanel] || '暂无毕设学生'
    },
    emptyDesc() {
      if (!this.hasBatch) return '顶部批次条选择当前工作批次后，再查看本页名单与进度。'
      if (this.activePanel === 'roster') return this.filtered ? '当前筛选条件下没有学生，可放宽条件或清空筛选。' : '名单是毕设起点；人多时使用 Excel 模板、预览、错误行和确认导入闭环。'
      return '当前队列为空，可调整筛选条件或切换其他工作视图。'
    }
  },
  watch: {
    '$route.query': {
      deep: true,
      handler(query) {
        if (!this.routeReady) return
        this.applyRouteState(query)
      }
    },
    'batchStore.selectedBatchId'(batchId) {
      this.page = 1
      this.selectedIds = []
      void this.replaceListQuery({ batchId: batchId ? String(batchId) : undefined, page: '1' })
      this.loadStats()
      this.load()
    }
  },
  created() {
    this.applyInitialRouteState(this.$route.query)
    this.routeReady = true
    this.loadGroupOpts()
    this.loadStats()
    this.load()
  },
  beforeUnmount() {
    ++this.loadToken
    ++this.statsToken
  },
  methods: {
    routeText(value) { return Array.isArray(value) ? String(value[0] || '') : String(value || '') },
    normalizePanel(value) { const panel = this.routeText(value); return PANEL_PRESETS[panel] ? panel : 'roster' },
    normalizePage(value) { const page = Number.parseInt(this.routeText(value), 10); return Number.isFinite(page) && page > 0 ? page : 1 },
    applyInitialRouteState(query) {
      const rawPanel = this.routeText(query.panel)
      if (rawPanel === 'create') {
        this.$router.replace({ path: '/admin/graduation/students/create', query: this.studentReturnQuery('roster') }).catch(() => {})
      }
      this.activePanel = this.normalizePanel(rawPanel)
      this.filters = { ...(PANEL_PRESETS[this.activePanel] || PANEL_PRESETS.roster)(), keyword: this.routeText(query.keyword) }
      this.page = this.normalizePage(query.page)
    },
    applyRouteState(query) {
      const rawPanel = this.routeText(query.panel)
      if (rawPanel === 'create') {
        this.$router.replace({ path: '/admin/graduation/students/create', query: this.studentReturnQuery('roster') }).catch(() => {})
        return
      }
      const panel = this.normalizePanel(rawPanel)
      const page = this.normalizePage(query.page)
      const keyword = this.routeText(query.keyword)
      if (panel === this.activePanel && page === this.page && keyword === String(this.filters.keyword || '')) return
      this.activePanel = panel
      this.filters = { ...(PANEL_PRESETS[panel] || PANEL_PRESETS.roster)(), keyword }
      this.page = page
      this.selectedIds = []
      this.load()
    },
    buildListQuery(overrides = {}) {
      const keyword = String(this.filters.keyword || '').trim()
      const query = {
        ...this.$route.query,
        batchId: this.batchStore.selectedBatchId ? String(this.batchStore.selectedBatchId) : undefined,
        panel: this.activePanel,
        page: String(this.page),
        keyword: keyword || undefined,
        ...overrides
      }
      Object.keys(query).forEach((key) => { if (query[key] == null || query[key] === '') delete query[key] })
      return query
    },
    replaceListQuery(overrides = {}) { return this.$router.replace({ query: this.buildListQuery(overrides) }).catch(() => {}) },
    currentListPath(panel = this.activePanel) {
      return this.$router.resolve({ path: '/admin/graduation/students', query: this.buildListQuery({ panel }) }).fullPath
    },
    studentReturnQuery(panel = this.activePanel) {
      return { returnPanel: panel, batchId: this.batchStore.selectedBatchId ? String(this.batchStore.selectedBatchId) : undefined, returnTo: this.currentListPath(panel) }
    },
    switchGroup(group) { if (group && group.key !== this.activeGroupKey) this.switchPanel(group.defaultPanel) },
    switchPanel(panel) {
      if (!PANEL_PRESETS[panel] || panel === this.activePanel) return
      const keyword = String(this.filters.keyword || '')
      this.activePanel = panel
      this.filters = { ...(PANEL_PRESETS[panel] || PANEL_PRESETS.roster)(), keyword }
      this.page = 1
      this.selectedIds = []
      void this.replaceListQuery({ panel, page: '1', keyword: keyword || undefined })
      this.load()
    },
    stageTone(stage) { return STAGE_TONE[stage] || 'default' },
    eligTone(status) { return status === 'QUALIFIED' ? 'success' : (status === 'UNQUALIFIED' ? 'danger' : 'warning') },
    gradQualTone(status) { return status === 'PASS' ? 'success' : (status === 'FAIL' ? 'danger' : (status === 'PENDING' ? 'warning' : 'default')) },
    async loadGroupOpts() {
      try { const result = await gdStudentApi.getStudentGroups(); if (result.code === 0) this.groupOpts = result.data || [] } catch { this.groupOpts = [] }
    },
    async loadStats() {
      const batchId = this.batchStore.selectedBatchId
      const token = ++this.statsToken
      if (!batchId) { this.stats = null; this.statsError = ''; return false }
      this.statsError = ''
      try {
        const result = await gdStudentApi.getStats({ batchId })
        if (token !== this.statsToken || String(batchId) !== String(this.batchStore.selectedBatchId)) return false
        if (result.code === 0) { this.stats = result.data || {}; return true }
        this.stats = null; this.statsError = result.message || '学生统计加载失败'; return false
      } catch (error) {
        if (token === this.statsToken) { this.stats = null; this.statsError = errorText(error, '学生统计加载失败') }
        return false
      }
    },
    buildQueryParams() { return buildStudentQuery(this.filters, { page: this.page, pageSize: this.pageSize, batchId: this.batchStore.selectedBatchId }) },
    async load() {
      const batchId = this.batchStore.selectedBatchId
      const token = ++this.loadToken
      if (!batchId) {
        this.loading = false; this.error = ''; this.rows = []; this.total = 0
        return false
      }
      this.loading = true; this.error = ''
      try {
        const result = await gdStudentApi.getStudents(this.buildQueryParams())
        if (token !== this.loadToken || String(batchId) !== String(this.batchStore.selectedBatchId)) return false
        if (result.code === 0) {
          this.rows = Array.isArray(result.data?.list) ? result.data.list : []
          this.total = Number(result.data?.total) || 0
          return true
        }
        this.rows = []; this.total = 0; this.error = result.message || '学生列表加载失败'
        return false
      } catch (error) {
        if (token === this.loadToken) { this.rows = []; this.total = 0; this.error = errorText(error, '学生列表加载失败') }
        return false
      } finally { if (token === this.loadToken) this.loading = false }
    },
    search() { this.page = 1; void this.replaceListQuery({ page: '1', keyword: String(this.filters.keyword || '').trim() || undefined }); this.load() },
    reset() {
      this.filters = (PANEL_PRESETS[this.activePanel] || PANEL_PRESETS.roster)()
      this.page = 1
      void this.replaceListQuery({ page: '1', keyword: undefined })
      this.load()
    },
    turnPage(page) { this.page = page; void this.replaceListQuery({ page: String(page) }); this.load() },
    onToolbar(key) {
      if (!this.writeEnabled && ['create', 'import', 'batchGroup', 'batchArchive'].includes(key)) return
      if (key === 'create') this.$router.push({ path: '/admin/graduation/students/create', query: this.studentReturnQuery() })
      if (key === 'import') this.importVisible = true
      if (key === 'batchGroup') this.$router.push({ path: '/admin/graduation/students/_batch/group', query: { ids: this.selectedIds.join(','), ...this.studentReturnQuery() } })
      if (key === 'batchArchive') this.askBatchArchive()
    },
    openDetail(row) { this.$router.push({ path: `/admin/graduation/students/${row.id}`, query: this.studentReturnQuery() }) },
    openAssignTopic(row) { this.$router.push({ path: `/admin/graduation/students/${row.id}/assign-topic`, query: this.studentReturnQuery() }) },
    openAdvisor(row) { this.$router.push({ path: `/admin/graduation/mentors/assign/${row.id}`, query: this.studentReturnQuery() }) },
    openGroup(row) { this.$router.push({ path: `/admin/graduation/students/${row.id}/group`, query: this.studentReturnQuery() }) },
    openDefense(row) { this.$router.push({ path: `/admin/graduation/students/${row.id}/defense-group`, query: this.studentReturnQuery() }) },
    askEligibility(row, status) {
      const label = status === 'QUALIFIED' ? '资格合格' : '资格不合格'
      this.confirm = { visible: true, title: '毕设资格认定', message: `确认将「${row.name}」认定为「${label}」？`, type: status === 'QUALIFIED' ? 'primary' : 'danger', confirmText: label, requireReason: true, reasonLabel: '认定意见', action: 'ELIGIBILITY', row, payload: { status } }
    },
    askArchiveOne(row) {
      this.confirm = { visible: true, title: '毕设归档', message: `确认归档「${row.name}」？归档后不可再编辑业务数据。`, type: 'warning', confirmText: '确认归档', requireReason: true, reasonLabel: '归档说明', action: 'ARCHIVE_ONE', row, payload: null }
    },
    askBatchArchive() {
      this.confirm = { visible: true, title: '批量归档', message: `确认归档已选 ${this.selectedIds.length} 名学生？仅材料已备案且无未关闭风险的学生会归档，其余将跳过。`, type: 'warning', confirmText: '批量归档', requireReason: true, reasonLabel: '归档说明', action: 'ARCHIVE_BATCH', row: null, payload: null }
    },
    async onConfirm({ reason } = {}) {
      if (this.submitting) return
      const { action, row, payload } = this.confirm
      this.submitting = true
      try {
        let result
        if (action === 'ELIGIBILITY') result = await gdStudentApi.setEligibility(row.id, { status: payload.status, reason: reason || '' })
        else if (action === 'ARCHIVE_ONE') result = await gdStudentApi.setStage(row.id, { action: 'ARCHIVE', reason: reason || '' })
        else if (action === 'ARCHIVE_BATCH') result = await gdStudentApi.batchArchive({ recordIds: this.selectedIds, reason: reason || '' })
        else return
        if (result?.code === 0) {
          toast.success(action === 'ARCHIVE_BATCH' ? `已归档 ${result.data.archived ?? 0} 人，跳过 ${result.data.skipped ?? 0} 人` : '已更新')
          this.confirm.visible = false
          this.selectedIds = []
          await Promise.all([this.load(), this.loadStats()])
        } else if (result) toast.error(result.message || '操作失败')
      } catch (error) { toast.error(errorText(error, '操作失败')) }
      finally { this.submitting = false }
    },
    onImported(data) {
      toast.success(`已导入 ${data?.created ?? 0} 人`)
      Promise.all([this.load(), this.loadStats()])
    },
    exportStudentsFn() {
      const tab = PANEL_TABS.find((panel) => panel.key === this.activePanel)
      const hint = exportFilenameHint(this.batchStore.selectedBatchName, tab?.label || '毕设学生')
      const params = { ...buildStudentQuery(this.filters, { batchId: this.batchStore.selectedBatchId }), filenameHint: hint }
      return gdStudentApi.exportStudents(params).then((result) => {
        if (result.code === 0 && result.data) result.data = { ...result.data, filename: result.data.filename || `${hint}.xlsx` }
        return result
      })
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.gd-student-page{gap:var(--space-3)}.gd-actions{display:flex;align-items:center;gap:var(--space-2);flex-wrap:wrap}.gd-student-hero{display:grid;grid-template-columns:minmax(280px,.9fr) minmax(0,1.45fr);align-items:center;gap:14px;padding:14px 16px;border:1px solid var(--primary-100,#dbeafe);border-radius:12px;background:linear-gradient(120deg,var(--primary-50,#eff6ff),#fff 72%);box-shadow:0 14px 30px -28px rgba(37,99,235,.7)}.gd-student-hero__copy{display:grid;min-width:0;gap:3px}.gd-student-hero__copy>span{color:var(--primary-600,#2563eb);font-size:10px;font-weight:700;letter-spacing:.08em}.gd-student-hero__copy strong{color:var(--text-primary);font-size:15px;line-height:1.45}.gd-student-hero__copy p{margin:0;color:var(--text-secondary);font-size:11px}.gd-student-hero__metrics{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:6px}.gd-student-hero__metrics div{display:grid;justify-items:center;gap:1px;padding:7px 5px;border:1px solid var(--border-light);border-radius:8px;background:rgba(255,255,255,.82)}.gd-student-hero__metrics b{color:var(--primary-700,#1d4ed8);font-size:18px}.gd-student-hero__metrics span{overflow:hidden;max-width:100%;color:var(--text-tertiary);font-size:9px;text-overflow:ellipsis;white-space:nowrap}.gd-import-contract{display:flex;align-items:center;gap:12px;padding:8px 10px;border:1px solid var(--border-light);border-radius:9px;background:var(--gray-50,#f8fafc)}.gd-import-contract>span{flex:none;color:var(--text-primary);font-size:11px;font-weight:700}.gd-import-contract ol{display:flex;align-items:center;flex-wrap:wrap;gap:5px 18px;margin:0;padding:0;counter-reset:step;list-style:none}.gd-import-contract li{position:relative;color:var(--text-secondary);font-size:10px}.gd-import-contract li::before{counter-increment:step;content:counter(step);display:inline-grid;place-items:center;width:17px;height:17px;margin-right:5px;border-radius:50%;background:var(--primary-100,#dbeafe);color:var(--primary-700,#1d4ed8);font-weight:700}.gd-import-contract li:not(:last-child)::after{content:'→';position:absolute;right:-13px;color:var(--text-tertiary)}.gd-readonly-banner{display:flex;justify-content:space-between;gap:12px;align-items:center;padding:10px 12px;border:1px solid var(--info-100,#dbeafe);border-radius:9px;background:#f8fbff}.gd-readonly-banner>div{display:grid;gap:2px}.gd-readonly-banner strong{color:var(--text-primary);font-size:12px}.gd-readonly-banner span,.gd-readonly-banner small{color:var(--text-secondary);font-size:10px;line-height:1.5}.gd-readonly-banner small{max-width:260px;text-align:right}.mp-tabs{overflow-x:auto;scrollbar-width:thin;flex-wrap:nowrap;padding-bottom:1px}.mp-tab{flex:0 0 auto;white-space:nowrap}.mp-tab:hover:not(.is-active){color:var(--text-primary);background:var(--gray-50,#f8fafc);border-radius:var(--radius-sm)}.gd-primary-tabs{overflow:visible}.gd-local-views{display:flex;align-items:center;gap:6px;flex-wrap:wrap;padding:8px 10px;border:1px solid var(--border-light);border-radius:var(--radius-md);background:var(--gray-50,#f8fafc)}.gd-local-views>span{margin-right:4px;color:var(--text-tertiary);font-size:var(--font-size-xs)}.gd-local-views button{padding:5px 10px;border:1px solid transparent;border-radius:var(--radius-full);background:transparent;color:var(--text-secondary);cursor:pointer}.gd-local-views button.is-active{border-color:var(--primary-200,#bfdbfe);background:var(--primary-50,#eff6ff);color:var(--primary-700,#1d4ed8);font-weight:600}.gd-topic-title{font-size:var(--font-size-sm)}.gd-row-action{margin-left:var(--space-2)}.gd-readonly-action{margin-left:var(--space-2);padding:2px 6px;border-radius:999px;background:var(--gray-100,#f1f5f9);color:var(--text-tertiary);font-size:10px}
@media(max-width:1180px){.gd-student-hero{grid-template-columns:1fr}.gd-student-hero__metrics{grid-template-columns:repeat(3,minmax(0,1fr))}}@media(max-width:700px){.gd-actions{width:100%;justify-content:space-between}.gd-readonly-banner{align-items:flex-start;flex-direction:column}.gd-readonly-banner small{max-width:none;text-align:left}.gd-student-hero__metrics{grid-template-columns:repeat(2,minmax(0,1fr))}}
</style>
