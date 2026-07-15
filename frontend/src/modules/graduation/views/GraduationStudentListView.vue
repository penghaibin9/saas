<template>
  <ModulePageShell
    title="毕设学生"
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

    <div class="mp-stack">
      <GraduationBatchStrip />
      <!-- 页内视图页签：同一名单的不同工作视图（原三级菜单入口收口至此，?panel= 深链不变） -->
      <div class="mp-tabs">
        <button
          v-for="p in panelTabs"
          :key="p.key"
          class="mp-tab"
          :class="{ 'is-active': activePanel === p.key }"
          @click="switchPanel(p.key)"
        >{{ p.label }}</button>
      </div>
      <AdvancedFilter v-model="filters" :fields="filterFields" @search="search" @reset="reset" />
      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" :title="emptyTitle" :description="emptyDesc" />
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
          <span v-if="row.batchName">{{ row.batchName }}</span>
          <span v-else class="mp-note">未关联批次</span>
        </template>
        <template #cell-topic="{ row }">
          <template v-if="row.topicId">
            <div class="mp-cell-main" style="font-size: var(--font-size-sm)">{{ row.topicTitle }}</div>
            <div class="mp-cell-sub">指导教师：{{ row.advisorName || '—' }}</div>
          </template>
          <span v-else class="mp-note">未选题</span>
        </template>
        <template #cell-stage="{ row }">
          <StatusTag :type="row.stageTone || stageTone(row.stage)" :label="row.stageLabel" dot />
        </template>
        <template #cell-risk="{ row }">
          <RiskTag v-if="row.riskLevel !== 'NONE'" :level="row.riskLevel" />
          <span v-else class="mp-note">无</span>
        </template>
        <template #cell-eligibility="{ row }">
          <StatusTag :type="row.eligibilityTone || eligTone(row.eligibilityStatus)" :label="row.eligibilityLabel" />
        </template>
        <template #cell-group="{ row }">
          <span v-if="row.studentGroup">{{ row.studentGroup }}</span>
          <span v-else class="mp-note">未分组</span>
        </template>
        <template #cell-materials="{ row }">
          <div class="mp-cell-main">开题：{{ row.proposalStatusLabel }}</div>
          <div class="mp-cell-sub">成果：{{ row.finalStatusLabel }} · 缺口：{{ row.materialGap }}</div>
        </template>
        <template #cell-defense="{ row }">
          <template v-if="row.defenseGroupId">
            <div class="mp-cell-main">{{ row.defenseGroup }}</div>
          </template>
          <span v-else class="mp-note">未分配答辩组</span>
        </template>
        <template #cell-gradQual="{ row }">
          <StatusTag :type="row.gradQualTone || gradQualTone(row.gradQualStatus)" :label="row.gradQualLabel" />
          <div v-if="row.gradQualNote" class="mp-cell-sub">{{ row.gradQualNote }}</div>
        </template>
        <template #cell-actions="{ row }">
          <button class="mp-link" @click="$router.push('/admin/graduation/students/' + row.id)">详情</button>
          <template v-if="activePanel === 'roster' || activePanel === 'topic' || activePanel === 'mentor'">
            <button
              v-if="row.stage !== 'ARCHIVED'"
              class="mp-link"
              style="margin-left: var(--space-2)"
              @click="openAssignTopic(row)"
            >{{ row.topicId ? '调题' : '分配选题' }}</button>
            <button
              v-if="row.stage !== 'ARCHIVED' && !row.advisorName"
              class="mp-link"
              style="margin-left: var(--space-2)"
              @click="openAdvisor(row)"
            >分配导师</button>
          </template>
          <template v-if="activePanel === 'eligibility' && row.stage !== 'ARCHIVED'">
            <button
              v-if="row.eligibilityStatus !== 'QUALIFIED'"
              class="mp-link"
              style="margin-left: var(--space-2)"
              @click="askEligibility(row, 'QUALIFIED')"
            >认定合格</button>
            <button
              v-if="row.eligibilityStatus !== 'UNQUALIFIED'"
              class="mp-link"
              style="margin-left: var(--space-2)"
              @click="askEligibility(row, 'UNQUALIFIED')"
            >认定不合格</button>
          </template>
          <button
            v-if="activePanel === 'grouping' && row.stage !== 'ARCHIVED'"
            class="mp-link"
            style="margin-left: var(--space-2)"
            @click="openGroup(row)"
          >设置分组</button>
          <button
            v-if="activePanel === 'defense' && row.stage !== 'ARCHIVED'"
            class="mp-link"
            style="margin-left: var(--space-2)"
            @click="openDefense(row)"
          >分配答辩组</button>
          <template v-if="activePanel === 'grad-qual' && row.stage !== 'ARCHIVED'">
            <button class="mp-link" style="margin-left: var(--space-2)" @click="askGradQual(row, 'PASS')">联动通过</button>
            <button class="mp-link" style="margin-left: var(--space-2)" @click="askGradQual(row, 'FAIL')">联动不通过</button>
          </template>
          <button
            v-if="activePanel === 'archive' && row.stage !== 'ARCHIVED'"
            class="mp-link"
            style="margin-left: var(--space-2)"
            @click="askArchiveOne(row)"
          >归档</button>
        </template>
      </DataTable>
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
      :confirm-fn="({ rows }) => gdStudentApi.importConfirm(rows)"
      :download-errors-fn="({ rows, errors }) => gdStudentApi.downloadImportErrors(rows, errors)"
      @imported="onImported"
    />

    <AppConfirmDialog
      v-model:visible="confirm.visible" :title="confirm.title" :message="confirm.message"
      :type="confirm.type" :confirm-text="confirm.confirmText" :require-reason="confirm.requireReason"
      :reason-label="confirm.reasonLabel" :submitting="submitting" @confirm="onConfirm"
    />
  </ModulePageShell>
</template>

<script>
/** 毕设学生列表：多 panel 生产级（名单/进度/风险/导师/选题/资格/分组/材料/答辩组/毕业资格/归档） */
import {
  ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable,
  StatusTag, RiskTag, LoadingState, ErrorState, EmptyState
} from '@/components/business'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import { AppSensitiveText, AppExportButton } from '@/components/common'
import { AppExcelImportDrawer } from '@/components/common/excel'
import { gdStudentApi } from '@/modules/graduation/api/graduation-student.api'
import {
  GD_STAGE, GD_RISK_LEVEL, HAS_TOPIC, GD_ELIGIBILITY, GD_GRAD_QUAL,
  HAS_DEFENSE_GROUP, MATERIAL_COMPLETE, ARCHIVE_VIEW
} from '@/modules/graduation/constants/graduation-student.constants'
import { toast } from '@/utils/toast'

const EMPTY_FILTERS = () => ({
  keyword: '', batchId: '', stage: '', riskLevel: '', hasTopic: '',
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

/** 页内视图页签（与 PANEL_PRESETS 一一对应；风险/导师视图保留在页内供跨模块联动） */
const PANEL_TABS = [
  { key: 'roster', label: '学生名单' },
  { key: 'progress', label: '学生进度' },
  { key: 'topic', label: '未选题' },
  { key: 'eligibility', label: '资格认定' },
  { key: 'grouping', label: '过程分组' },
  { key: 'materials', label: '材料缺口' },
  { key: 'defense', label: '答辩组' },
  { key: 'grad-qual', label: '毕业资格联动' },
  { key: 'archive', label: '归档' },
  { key: 'risk', label: '风险学生' },
  { key: 'mentor', label: '已选题导师' }
]

const PANEL_HINTS = {
  roster: '建档、导入、导出全量名单',
  progress: '按节点状态筛选（默认指导中）',
  risk: '筛选高风险学生',
  mentor: '筛选已选题学生（含导师）',
  topic: '筛选未选题学生，可「分配选题」',
  eligibility: '毕设资格认定（待认定默认可筛）',
  grouping: '过程分组维护，支持批量分组',
  materials: '开题/成果材料缺口一览',
  defense: '答辩组分配（未分配默认可筛）',
  'grad-qual': '与教务毕业资格预审联动状态',
  archive: '待归档/已归档学生管理'
}

const COLUMN_PRESETS = {
  default: [
    { key: 'student', title: '学生' },
    { key: 'batch', title: '批次' },
    { key: 'topic', title: '课题 / 导师' },
    { key: 'stage', title: '节点状态' },
    { key: 'risk', title: '风险' },
    { key: 'actions', title: '操作', width: '220px' }
  ],
  eligibility: [
    { key: 'student', title: '学生' },
    { key: 'batch', title: '批次' },
    { key: 'eligibility', title: '毕设资格' },
    { key: 'stage', title: '节点状态' },
    { key: 'actions', title: '操作', width: '240px' }
  ],
  grouping: [
    { key: 'student', title: '学生' },
    { key: 'group', title: '过程分组' },
    { key: 'batch', title: '批次' },
    { key: 'topic', title: '课题' },
    { key: 'actions', title: '操作', width: '160px' }
  ],
  materials: [
    { key: 'student', title: '学生' },
    { key: 'materials', title: '材料状态' },
    { key: 'stage', title: '节点' },
    { key: 'batch', title: '批次' },
    { key: 'actions', title: '操作', width: '100px' }
  ],
  defense: [
    { key: 'student', title: '学生' },
    { key: 'defense', title: '答辩组' },
    { key: 'stage', title: '节点' },
    { key: 'batch', title: '批次' },
    { key: 'actions', title: '操作', width: '160px' }
  ],
  'grad-qual': [
    { key: 'student', title: '学生' },
    { key: 'gradQual', title: '毕业资格联动' },
    { key: 'eligibility', title: '毕设资格' },
    { key: 'stage', title: '节点' },
    { key: 'actions', title: '操作', width: '240px' }
  ],
  archive: [
    { key: 'student', title: '学生' },
    { key: 'stage', title: '节点' },
    { key: 'materials', title: '材料' },
    { key: 'gradQual', title: '毕业资格' },
    { key: 'actions', title: '操作', width: '120px' }
  ]
}

const STAGE_TONE = {
  TOPIC_SELECTING: 'default', TASKBOOK_CONFIRM: 'info', GUIDING: 'processing',
  MIDTERM: 'warning', FINAL_CHECK: 'processing', DEFENSE: 'warning', COMPLETED: 'info', ARCHIVED: 'success'
}

import GraduationBatchStrip from './_shared/GraduationBatchStrip.vue'

export default {
  name: 'GraduationStudentListView',
  components: { GraduationBatchStrip, ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag, RiskTag, LoadingState, ErrorState, EmptyState, AppConfirmDialog, AppExcelImportDrawer, AppSensitiveText, AppExportButton },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true, error: '', submitting: false, activePanel: 'roster',
      panelTabs: PANEL_TABS,
      rows: [], total: 0, page: 1, pageSize: 10, filters: EMPTY_FILTERS(),
      selectedIds: [],
      batchOpts: [], groupOpts: [],
      importVisible: false,
      gdStudentApi,
      confirm: { visible: false, title: '', message: '', type: 'primary', confirmText: '确认', requireReason: false, reasonLabel: '原因', action: null, row: null, payload: null }
    }
  },
  computed: {
    columns() {
      return COLUMN_PRESETS[this.activePanel] || COLUMN_PRESETS.default
    },
    selectablePanel() {
      return this.activePanel === 'grouping' || this.activePanel === 'archive'
    },
    filterFields() {
      const batchOpts = this.batchOpts.map((b) => ({ value: b.id, label: b.batchName }))
      const groupOpts = this.groupOpts.map((g) => ({ value: g, label: g }))
      const base = [
        { key: 'keyword', label: '关键词', type: 'text', placeholder: '姓名 / 学号 / 课题' },
        { key: 'batchId', label: '批次', type: 'select', options: batchOpts },
        {
          key: 'date', label: '起始日期', type: 'daterange',
          startKey: 'dateStart', endKey: 'dateEnd',
          memoryKey: 'graduation.students.dateRange', emptyLabel: '全部时间'
        }
      ]
      const panelFields = {
        roster: [
          { key: 'stage', label: '节点状态', type: 'select', options: GD_STAGE },
          { key: 'riskLevel', label: '风险等级', type: 'select', options: GD_RISK_LEVEL },
          { key: 'hasTopic', label: '选题', type: 'select', options: HAS_TOPIC }
        ],
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
      const base = []
      if (this.activePanel === 'roster') {
        base.push({ key: 'create', label: '＋ 建档', variant: 'primary' }, { key: 'import', label: '导入 Excel' })
      }
      if (this.activePanel === 'grouping') {
        base.push({ key: 'batchGroup', label: '批量分组', variant: 'primary', disabled: !this.selectedIds.length })
      }
      if (this.activePanel === 'archive' && this.filters.archiveView !== 'archived') {
        base.push({ key: 'batchArchive', label: '批量归档', variant: 'primary', disabled: !this.selectedIds.length })
      }
      return base
    },
    exportVisible() {
      if (this.activePanel === 'grouping' || this.activePanel === 'archive') return false
      return true
    },
    pageSubtitle() {
      const hint = PANEL_HINTS[this.activePanel] || ''
      const sel = this.selectablePanel && this.selectedIds.length ? ` · 已选 ${this.selectedIds.length}` : ''
      return `共 ${this.total} 人 · ${hint}${sel} · 学号默认脱敏`
    },
    emptyTitle() {
      const m = { eligibility: '暂无待认定学生', materials: '暂无材料缺口学生', defense: '暂无待分配答辩组学生', archive: '暂无归档记录' }
      return m[this.activePanel] || '暂无毕设学生'
    },
    emptyDesc() {
      if (this.activePanel === 'roster') return '可「＋ 建档」或「导入 Excel」录入毕设学生'
      return '可调整筛选条件或从其他入口建档'
    }
  },
  watch: {
    '$route.query.panel': {
      immediate: true,
      handler(panel) {
        this.applyPanel((panel || 'roster').toString())
      }
    }
  },
  created() {
    this.loadBatchOpts()
    this.loadGroupOpts()
  },
  methods: {
    /** 页内页签切换：改路由 query，由 $route.query.panel watcher 统一应用视图 */
    switchPanel(p) {
      if (p === this.activePanel) return
      this.$router.replace({ query: { ...this.$route.query, panel: p } })
    },
    applyPanel(panel) {
      const key = PANEL_PRESETS[panel] ? panel : 'roster'
      this.activePanel = key
      this.filters = (PANEL_PRESETS[key] || PANEL_PRESETS.roster)()
      this.selectedIds = []
      this.page = 1
      if (panel === 'create') {
        this.$router.push({ path: '/admin/graduation/students/create', query: { returnPanel: key } })
        return
      }
      this.load()
    },
    studentReturnQuery() {
      return { returnPanel: this.activePanel }
    },
    stageTone(stage) { return STAGE_TONE[stage] || 'default' },
    eligTone(s) { return s === 'QUALIFIED' ? 'success' : (s === 'UNQUALIFIED' ? 'danger' : 'warning') },
    gradQualTone(s) { return s === 'PASS' ? 'success' : (s === 'FAIL' ? 'danger' : (s === 'PENDING' ? 'warning' : 'default')) },
    async loadBatchOpts() {
      const b = await gdStudentApi.getBatchOptions()
      if (b.code === 0) this.batchOpts = b.data
    },
    async loadGroupOpts() {
      const g = await gdStudentApi.getStudentGroups()
      if (g.code === 0) this.groupOpts = g.data || []
    },
    buildQueryParams() {
      const p = { ...this.filters, page: this.page, pageSize: this.pageSize }
      const boolKeys = ['hasTopic', 'hasDefenseGroup', 'materialComplete']
      boolKeys.forEach((k) => {
        if (p[k] === 'true') p[k] = true
        else if (p[k] === 'false') p[k] = false
        else delete p[k]
      })
      if (!p.archiveView) {
        delete p.archiveView
      }
      ;['batchId', 'stage', 'riskLevel', 'eligibility', 'studentGroup', 'gradQualStatus'].forEach((k) => {
        if (!p[k]) delete p[k]
      })
      return p
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await gdStudentApi.getStudents(this.buildQueryParams())
      if (res.code === 0) { this.rows = res.data.list; this.total = res.data.total } else this.error = res.message
      this.loading = false
    },
    search() { this.page = 1; this.load() },
    reset() {
      this.filters = (PANEL_PRESETS[this.activePanel] || PANEL_PRESETS.roster)()
      this.page = 1
      this.load()
    },
    turnPage(p) { this.page = p; this.load() },
    onToolbar(key) {
      if (key === 'create') {
        this.$router.push({ path: '/admin/graduation/students/create', query: this.studentReturnQuery() })
      }
      if (key === 'import') { this.importVisible = true }
      if (key === 'batchGroup') {
        this.$router.push({
          path: '/admin/graduation/students/_batch/group',
          query: { ids: this.selectedIds.join(','), ...this.studentReturnQuery() }
        })
      }
      if (key === 'batchArchive') this.askBatchArchive()
    },
    openAssignTopic(row) {
      this.$router.push({
        path: `/admin/graduation/students/${row.id}/assign-topic`,
        query: this.studentReturnQuery()
      })
    },
    openAdvisor(row) {
      this.$router.push(`/admin/graduation/mentors/assign/${row.id}`)
    },
    askEligibility(row, status) {
      const label = status === 'QUALIFIED' ? '资格合格' : '资格不合格'
      this.confirm = {
        visible: true, title: '毕设资格认定', message: `确认将「${row.name}」认定为「${label}」？`,
        type: status === 'QUALIFIED' ? 'primary' : 'danger', confirmText: label,
        requireReason: true, reasonLabel: '认定意见', action: 'ELIGIBILITY', row, payload: { status }
      }
    },
    openGroup(row) {
      this.$router.push({
        path: `/admin/graduation/students/${row.id}/group`,
        query: this.studentReturnQuery()
      })
    },
    openDefense(row) {
      this.$router.push({
        path: `/admin/graduation/students/${row.id}/defense-group`,
        query: this.studentReturnQuery()
      })
    },
    askGradQual(row, status) {
      const label = status === 'PASS' ? '毕业资格通过' : '毕业资格不通过'
      this.confirm = {
        visible: true, title: '毕业资格联动', message: `确认将「${row.name}」教务毕业资格联动为「${label}」？`,
        type: status === 'PASS' ? 'primary' : 'danger', confirmText: label,
        requireReason: true, reasonLabel: '联动说明', action: 'GRAD_QUAL', row, payload: { status }
      }
    },
    askArchiveOne(row) {
      this.confirm = {
        visible: true, title: '毕设归档', message: `确认归档「${row.name}」？归档后不可再编辑业务数据。`,
        type: 'warning', confirmText: '确认归档', requireReason: true, reasonLabel: '归档说明',
        action: 'ARCHIVE_ONE', row
      }
    },
    askBatchArchive() {
      this.confirm = {
        visible: true, title: '批量归档', message: `确认归档已选 ${this.selectedIds.length} 名学生？`,
        type: 'warning', confirmText: '批量归档', requireReason: true, reasonLabel: '归档说明',
        action: 'ARCHIVE_BATCH', row: null
      }
    },
    async onConfirm({ reason } = {}) {
      const { action, row, payload } = this.confirm
      this.submitting = true
      try {
        let res
        if (action === 'ELIGIBILITY') {
          res = await gdStudentApi.setEligibility(row.id, { status: payload.status, reason: reason || '' })
        }
        if (action === 'GRAD_QUAL') {
          res = await gdStudentApi.setGradQual(row.id, { status: payload.status, note: reason || '', reason: reason || '' })
        }
        if (action === 'ARCHIVE_ONE') {
          res = await gdStudentApi.setStage(row.id, { action: 'ARCHIVE', reason: reason || '' })
        }
        if (action === 'ARCHIVE_BATCH') {
          res = await gdStudentApi.batchArchive({ recordIds: this.selectedIds, reason: reason || '' })
        }
        if (res && res.code === 0) {
          toast.success(action === 'ARCHIVE_BATCH' ? `已归档 ${res.data.archived} 人` : '已更新')
          this.confirm.visible = false
          this.selectedIds = []
          this.load()
        } else if (res) toast.error(res.message)
      } finally { this.submitting = false }
    },
    onImported(data) {
      toast.success(`已导入 ${data?.created ?? 0} 人`)
      this.load()
    },
    exportStudentsFn() {
      const p = { ...this.filters }
      ;['batchId', 'stage', 'riskLevel', 'eligibility', 'studentGroup', 'gradQualStatus'].forEach((k) => {
        if (!p[k]) delete p[k]
      })
      return gdStudentApi.exportStudents(p)
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.gd-actions { display: flex; align-items: center; gap: var(--space-2); flex-wrap: wrap; }
</style>
