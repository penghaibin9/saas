<template>
  <ModulePageShell
    title="毕设学生"
    :subtitle="pageSubtitle"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <ModuleToolbar :actions="toolbarActions" @action="onToolbar" />
    </template>

    <div class="mp-stack">
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
          <div class="mp-cell-sub">{{ maskNo(row.studentNo) }} · {{ row.className }}</div>
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

    <!-- 建档 -->
    <AppDrawer v-model:visible="createVisible" title="毕设学生建档">
      <form class="ie-form" @submit.prevent="submitCreate">
        <label class="ie-fld ie-fld--full"><span class="ie-lbl">学生 <i>*</i></span>
          <select v-model="cform.studentId" class="ie-in">
            <option value="">请选择学生</option>
            <option v-for="s in studentOpts" :key="s.id" :value="s.id">{{ s.name }}（{{ s.studentNo }}）</option>
          </select>
        </label>
        <label class="ie-fld ie-fld--full"><span class="ie-lbl">毕设批次</span>
          <select v-model="cform.batchId" class="ie-in">
            <option value="">不关联批次</option>
            <option v-for="b in batchOpts" :key="b.id" :value="b.id">{{ b.batchName }}（{{ b.batchNo }}）</option>
          </select>
        </label>
        <label class="ie-fld"><span class="ie-lbl">指导教师</span><input v-model.trim="cform.advisorName" class="ie-in" /></label>
        <p v-if="cError" class="ie-err">{{ cError }}</p>
        <div class="ie-actions">
          <button type="button" class="mp-btn" @click="createVisible = false">取消</button>
          <button type="submit" class="mp-btn mp-btn--primary" :disabled="submitting">建档</button>
        </div>
      </form>
    </AppDrawer>

    <!-- 分配选题 -->
    <AppDrawer v-model:visible="assignVisible" :title="assignRow ? `分配选题 · ${assignRow.name}` : '分配选题'">
      <div class="ie-form">
        <p class="ie-hint">仅「已确认」且未满员的选题可选（来自选题库真实数据）。</p>
        <label class="ie-fld ie-fld--full"><span class="ie-lbl">选题 <i>*</i></span>
          <select v-model="assignTopicId" class="ie-in">
            <option value="">请选择选题</option>
            <option v-for="t in topicOpts" :key="t.id" :value="t.id" :disabled="t.remaining <= 0">
              {{ t.title }} · {{ t.advisorName }}（余 {{ t.remaining }}）
            </option>
          </select>
        </label>
        <p v-if="assignError" class="ie-err">{{ assignError }}</p>
        <div class="ie-actions">
          <button type="button" class="mp-btn" @click="assignVisible = false">取消</button>
          <button type="button" class="mp-btn mp-btn--primary" :disabled="submitting || !assignTopicId" @click="submitAssign">确认分配</button>
        </div>
      </div>
    </AppDrawer>

    <!-- 设置分组 -->
    <AppDrawer v-model:visible="groupVisible" :title="groupRow ? `过程分组 · ${groupRow.name}` : '批量设置分组'">
      <div class="ie-form">
        <p v-if="!groupRow" class="ie-hint">已选 {{ selectedIds.length }} 人，将统一写入过程分组名称。</p>
        <label class="ie-fld ie-fld--full"><span class="ie-lbl">分组名称 <i>*</i></span>
          <input v-model.trim="groupName" class="ie-in" list="gd-group-suggest" placeholder="如：第1组 / A组答辩预备" />
          <datalist id="gd-group-suggest">
            <option v-for="g in groupOpts" :key="g" :value="g" />
          </datalist>
        </label>
        <p v-if="groupError" class="ie-err">{{ groupError }}</p>
        <div class="ie-actions">
          <button type="button" class="mp-btn" @click="groupVisible = false">取消</button>
          <button type="button" class="mp-btn mp-btn--primary" :disabled="submitting || !groupName" @click="submitGroup">确认</button>
        </div>
      </div>
    </AppDrawer>

    <!-- 分配答辩组 -->
    <AppDrawer v-model:visible="defenseVisible" :title="defenseRow ? `答辩组 · ${defenseRow.name}` : '分配答辩组'">
      <div class="ie-form">
        <p class="ie-hint">答辩组来自「答辩安排」模块真实数据；分配后自动更新组内人数。</p>
        <label class="ie-fld ie-fld--full"><span class="ie-lbl">答辩组 <i>*</i></span>
          <select v-model="defenseGroupId" class="ie-in">
            <option value="">请选择答辩组</option>
            <option v-for="g in defenseOpts" :key="g.id" :value="g.id">
              {{ g.groupName }} · {{ g.defenseDate || '日期待定' }} · {{ g.location || '地点待定' }}（{{ g.studentCount }}人）
            </option>
          </select>
        </label>
        <p v-if="defenseError" class="ie-err">{{ defenseError }}</p>
        <div class="ie-actions">
          <button type="button" class="mp-btn" @click="defenseVisible = false">取消</button>
          <button type="button" class="mp-btn mp-btn--primary" :disabled="submitting || !defenseGroupId" @click="submitDefense">确认分配</button>
        </div>
      </div>
    </AppDrawer>

    <AppExcelImportDrawer
      v-model:visible="importVisible"
      title="导入毕设学生"
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
import { AppDrawer } from '@/components/ui'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
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
  MIDTERM: 'warning', FINAL_CHECK: 'processing', DEFENSE: 'warning', ARCHIVED: 'success'
}

export default {
  name: 'GraduationStudentListView',
  components: { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag, RiskTag, LoadingState, ErrorState, EmptyState, AppDrawer, AppConfirmDialog, AppExcelImportDrawer },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true, error: '', submitting: false, activePanel: 'roster',
      rows: [], total: 0, page: 1, pageSize: 10, filters: EMPTY_FILTERS(),
      selectedIds: [],
      createVisible: false, cform: { studentId: '', batchId: '', advisorName: '' }, cError: '',
      studentOpts: [], batchOpts: [], groupOpts: [], defenseOpts: [],
      assignVisible: false, assignRow: null, assignTopicId: '', assignError: '', topicOpts: [],
      groupVisible: false, groupRow: null, groupName: '', groupError: '',
      defenseVisible: false, defenseRow: null, defenseGroupId: '', defenseError: '',
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
        base.push({ key: 'create', label: '＋ 建档', variant: 'primary' }, { key: 'import', label: '导入 Excel' }, { key: 'export', label: '导出 Excel' })
      }
      if (this.activePanel === 'grouping') {
        base.push({ key: 'batchGroup', label: '批量分组', variant: 'primary', disabled: !this.selectedIds.length })
      }
      if (this.activePanel === 'archive' && this.filters.archiveView !== 'archived') {
        base.push({ key: 'batchArchive', label: '批量归档', variant: 'primary', disabled: !this.selectedIds.length })
      }
      if (!base.length) base.push({ key: 'export', label: '导出 Excel' })
      return base
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
    applyPanel(panel) {
      const key = PANEL_PRESETS[panel] ? panel : 'roster'
      this.activePanel = key
      this.filters = (PANEL_PRESETS[key] || PANEL_PRESETS.roster)()
      this.selectedIds = []
      this.page = 1
      this.load()
    },
    stageTone(stage) { return STAGE_TONE[stage] || 'default' },
    eligTone(s) { return s === 'QUALIFIED' ? 'success' : (s === 'UNQUALIFIED' ? 'danger' : 'warning') },
    gradQualTone(s) { return s === 'PASS' ? 'success' : (s === 'FAIL' ? 'danger' : (s === 'PENDING' ? 'warning' : 'default')) },
    maskNo(v) { return v ? v.slice(0, -4) + '**' + v.slice(-2) : '' },
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
      if (p.archiveView) {
        p.archiveView = p.archiveView
      } else {
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
    async onToolbar(key) {
      if (key === 'create') {
        this.cform = { studentId: '', batchId: '', advisorName: '' }; this.cError = ''
        const [s, b] = await Promise.all([gdStudentApi.getStudentOptions(), gdStudentApi.getBatchOptions()])
        if (s.code === 0) this.studentOpts = s.data
        if (b.code === 0) this.batchOpts = b.data
        this.createVisible = true
      }
      if (key === 'import') { this.importVisible = true }
      if (key === 'export') this.doExport()
      if (key === 'batchGroup') { this.groupRow = null; this.groupName = ''; this.groupError = ''; this.groupVisible = true }
      if (key === 'batchArchive') this.askBatchArchive()
    },
    async submitCreate() {
      this.cError = ''
      if (!this.cform.studentId) { this.cError = '请选择学生'; return }
      this.submitting = true
      try {
        const body = { studentId: this.cform.studentId, advisorName: this.cform.advisorName || undefined }
        if (this.cform.batchId) body.batchId = this.cform.batchId
        const res = await gdStudentApi.createStudent(body)
        if (res.code === 0) { toast.success('已建档'); this.createVisible = false; this.load() } else this.cError = res.message
      } finally { this.submitting = false }
    },
    async openAssignTopic(row) {
      this.assignRow = row; this.assignTopicId = row.topicId || ''; this.assignError = ''
      const t = await gdStudentApi.getConfirmedTopics()
      if (t.code === 0) this.topicOpts = t.data
      else { this.topicOpts = []; toast.error(t.message) }
      this.assignVisible = true
    },
    async submitAssign() {
      this.assignError = ''
      this.submitting = true
      try {
        const res = await gdStudentApi.assignTopic(this.assignRow.id, { topicId: this.assignTopicId })
        if (res.code === 0) { toast.success('已分配选题'); this.assignVisible = false; this.load() } else this.assignError = res.message
      } finally { this.submitting = false }
    },
    openAdvisor(row) {
      this.confirm = {
        visible: true, title: '分配指导教师', message: `为「${row.name}」指定指导教师`,
        type: 'primary', confirmText: '确认分配', requireReason: true, reasonLabel: '指导教师姓名',
        action: 'ADVISOR', row
      }
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
      this.groupRow = row; this.groupName = row.studentGroup || ''; this.groupError = ''; this.groupVisible = true
    },
    async submitGroup() {
      this.groupError = ''
      if (!this.groupName) { this.groupError = '请填写分组名称'; return }
      this.submitting = true
      try {
        let res
        if (this.groupRow) {
          res = await gdStudentApi.setStudentGroup(this.groupRow.id, { groupName: this.groupName, reason: '' })
        } else {
          res = await gdStudentApi.batchSetStudentGroup({ recordIds: this.selectedIds, groupName: this.groupName, reason: '批量分组' })
        }
        if (res.code === 0) {
          toast.success(this.groupRow ? '已更新分组' : `已更新 ${res.data.updated} 人`)
          this.groupVisible = false
          this.selectedIds = []
          this.loadGroupOpts()
          this.load()
        } else this.groupError = res.message
      } finally { this.submitting = false }
    },
    async openDefense(row) {
      this.defenseRow = row; this.defenseGroupId = row.defenseGroupId || ''; this.defenseError = ''
      const d = await gdStudentApi.getDefenseGroups()
      if (d.code === 0) this.defenseOpts = d.data
      else { this.defenseOpts = []; toast.error(d.message) }
      this.defenseVisible = true
    },
    async submitDefense() {
      this.defenseError = ''
      this.submitting = true
      try {
        const res = await gdStudentApi.assignDefenseGroup(this.defenseRow.id, { defenseGroupId: this.defenseGroupId, reason: '' })
        if (res.code === 0) { toast.success('已分配答辩组'); this.defenseVisible = false; this.load() } else this.defenseError = res.message
      } finally { this.submitting = false }
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
        if (action === 'ADVISOR') {
          const name = (reason || '').trim()
          if (!name) { toast.error('请填写指导教师姓名'); return }
          res = await gdStudentApi.assignAdvisor(row.id, { advisorName: name })
        }
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
    async doExport() {
      const p = { ...this.filters }
      ;['batchId', 'stage', 'riskLevel', 'eligibility', 'studentGroup', 'gradQualStatus'].forEach((k) => {
        if (!p[k]) delete p[k]
      })
      const res = await gdStudentApi.downloadExport(p)
      if (res.code === 0) toast.success(`已导出 ${res.data.rowCount} 条`)
      else toast.error(res.message)
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.ie-form { display: flex; flex-direction: column; gap: var(--space-3); padding: var(--space-4); }
.ie-fld { display: flex; flex-direction: column; gap: var(--space-1); }
.ie-fld--full { grid-column: 1 / -1; }
.ie-lbl { font-size: var(--font-size-sm); color: var(--text-secondary); }
.ie-lbl i { color: var(--danger-600); font-style: normal; }
.ie-in { padding: var(--space-2); border: 1px solid var(--border-default); border-radius: var(--radius-sm); font-size: var(--font-size-sm); }
.ie-hint { font-size: var(--font-size-sm); color: var(--text-secondary); margin: 0; }
.ie-err { color: var(--danger-600); font-size: var(--font-size-sm); margin: 0; }
.ie-actions { display: flex; gap: var(--space-2); justify-content: flex-end; margin-top: var(--space-2); }
</style>
