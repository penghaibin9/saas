<template>
  <ModulePageShell
    title="题目库"
    :subtitle="pageSubtitle"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <div class="gd-actions">
        <ModuleToolbar :actions="toolbarActions" @action="onToolbar" />
        <AppExportButton
          v-if="exportVisible"
          :export-fn="exportTopicsLibFn"
        >导出 Excel</AppExportButton>
      </div>
    </template>

    <!-- 分类 / 容量概览 -->
    <div v-if="activePanel === 'category' && categoryStats.length" class="mp-stats">
      <button v-for="c in categoryStats.slice(0, 6)" :key="c.category" type="button" class="mp-stat" @click="drillCategory(c.category)">
        <div class="mp-stat__val">{{ c.count }}</div>
        <div class="mp-stat__lbl">{{ c.category }}</div>
        <div class="mp-stat__sub">入池 {{ c.inPool }} · 满员 {{ c.full }}</div>
      </button>
    </div>
    <div v-if="activePanel === 'capacity' && libStats" class="mp-stats">
      <div class="mp-stat"><div class="mp-stat__val">{{ libStats.inPool }}</div><div class="mp-stat__lbl">在池题目</div></div>
      <div class="mp-stat"><div class="mp-stat__val">{{ libStats.availableCount }}</div><div class="mp-stat__lbl">可选余量</div></div>
      <div class="mp-stat"><div class="mp-stat__val">{{ libStats.fullCount }}</div><div class="mp-stat__lbl">已满员</div></div>
      <div class="mp-stat"><div class="mp-stat__val">{{ libStats.uncategorized }}</div><div class="mp-stat__lbl">未分类</div></div>
    </div>

    <div class="mp-stack">
      <GraduationBatchStrip />
      <!-- 页内视图页签：同一题目库的来源/审核/维护视图（原三级菜单入口收口至此，?panel= 深链不变） -->
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

      <!-- 内嵌表单/详情：固定在筛选栏下方，替换表格区域 -->
      <router-view v-if="inlineOpen" :ctx="ctx" />

      <template v-else>
      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" :title="emptyTitle" :description="emptyDesc" />
      <DataTable
        v-else
        :columns="columns"
        :rows="rows"
        row-key="id"
        :virtual-scroll="rows.length > 15"
        :virtual-height="560"
        :pagination="{ page, pageSize, total }"
        @page-change="turnPage"
      >
        <template #cell-title="{ row }">
          <div class="mp-cell-main">{{ row.title }}</div>
          <div class="mp-cell-sub">{{ row.topicNo || '无编号' }} · {{ row.majorName || '—' }}</div>
        </template>
        <template #cell-category="{ row }">
          <StatusTag v-if="row.category" type="info" :label="row.category" />
          <span v-else class="mp-note">未分类</span>
        </template>
        <template #cell-source="{ row }">
          <StatusTag :type="sourceTone(row.sourceType)" :label="row.sourceLabel" />
          <div v-if="row.enterpriseName" class="mp-cell-sub">{{ row.enterpriseName }}</div>
        </template>
        <template #cell-advisor="{ row }">{{ row.advisorName || '—' }}</template>
        <template #cell-capacity="{ row }">
          <span :class="{ 'mp-note': row.isFull }">{{ row.selected }}/{{ row.capacity }}</span>
          <span v-if="row.isFull" class="mp-cell-sub">已满员</span>
          <span v-else class="mp-cell-sub">余 {{ row.remaining }}</span>
        </template>
        <template #cell-requirements="{ row }">
          <span v-if="row.hasRequirements" class="mp-cell-sub">{{ truncate(row.requirements, 48) }}</span>
          <StatusTag v-else type="warning" label="待补全" />
        </template>
        <template #cell-attachments="{ row }">
          <span v-if="row.attachmentCount">{{ row.attachmentCount }} 个附件</span>
          <StatusTag v-else type="warning" label="无附件" />
        </template>
        <template #cell-review="{ row }">
          <StatusTag :type="row.reviewTone" :label="row.reviewLabel" dot />
          <div v-if="row.reviewComment" class="mp-cell-sub">{{ row.reviewComment }}</div>
        </template>
        <template #cell-status="{ row }">
          <StatusTag :type="row.statusTone" :label="row.statusLabel" />
        </template>
        <template #cell-historyTopic="{ row }">
          <div class="mp-cell-main">{{ row.topicTitle || '—' }}</div>
          <div class="mp-cell-sub">ID {{ row.topicId || '—' }}</div>
        </template>
        <template #cell-historyAction="{ row }">
          <StatusTag type="info" :label="row.action" />
        </template>
        <template #cell-historyOperator="{ row }">
          <div>{{ row.operator }}</div>
          <div v-if="row.roleName" class="mp-cell-sub">{{ row.roleName }}</div>
        </template>
        <template #cell-historyDetail="{ row }">
          <div class="mp-cell-sub">{{ row.detail || '—' }}</div>
          <div v-if="row.beforeVal || row.afterVal" class="mp-cell-sub">{{ row.beforeVal }} → {{ row.afterVal }}</div>
        </template>
        <template #cell-historyTime="{ row }">{{ row.occurredAt || '—' }}</template>
        <template #cell-actions="{ row }">
          <template v-if="isHistoryPanel">
            <button v-if="row.topicId" class="mp-link" @click="openDetailById(row.topicId)">查看题目</button>
          </template>
          <template v-else>
            <button class="mp-link" @click="openDetail(row)">详情</button>
            <button
              v-if="canEdit(row)"
              class="mp-link"
              style="margin-left: var(--space-2)"
              @click="openEdit(row)"
            >编辑</button>
            <button
              v-if="activePanel === 'capacity' && row.status !== 'ARCHIVED'"
              class="mp-link"
              style="margin-left: var(--space-2)"
              @click="openCapacity(row)"
            >调容量</button>
            <button
              v-if="activePanel === 'requirements' && row.status !== 'ARCHIVED'"
              class="mp-link"
              style="margin-left: var(--space-2)"
              @click="openRequirements(row)"
            >补要求</button>
            <button
              v-if="activePanel === 'attachments' && row.status !== 'ARCHIVED'"
              class="mp-link"
              style="margin-left: var(--space-2)"
              @click="openAttachments(row)"
            >管附件</button>
            <button
              v-if="activePanel === 'category' && row.status !== 'ARCHIVED'"
              class="mp-link"
              style="margin-left: var(--space-2)"
              @click="openCategoryEdit(row)"
            >改分类</button>
            <button
              v-if="row.reviewStatus === 'DRAFT' || row.reviewStatus === 'REJECTED'"
              class="mp-link"
              style="margin-left: var(--space-2)"
              @click="askSubmitReview(row)"
            >提交审核</button>
            <template v-if="activePanel === 'pending' && row.reviewStatus === 'PENDING_REVIEW'">
              <button class="mp-link" style="margin-left: var(--space-2)" @click="askReview(row, 'APPROVE')">通过</button>
              <button class="mp-link" style="margin-left: var(--space-2)" @click="askReview(row, 'REJECT')">驳回</button>
            </template>
            <button
              v-if="row.status === 'CONFIRMED' && row.reviewStatus === 'APPROVED' && !panelOnlyOps"
              class="mp-link"
              style="margin-left: var(--space-2)"
              @click="askDisable(row)"
            >停用</button>
            <button
              v-if="row.status === 'DISABLED' && !panelOnlyOps"
              class="mp-link"
              style="margin-left: var(--space-2)"
              @click="askEnable(row)"
            >启用</button>
            <button
              v-if="row.status !== 'ARCHIVED' && !panelOnlyOps"
              class="mp-link"
              style="margin-left: var(--space-2)"
              @click="askArchive(row)"
            >归档</button>
          </template>
        </template>
      </DataTable>
      </template>
    </div>

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

    <AppExcelImportDrawer
      v-model:visible="importVisible"
      title="导入题目库"
      template-name="题目库导入模板.xlsx"
      :required-fields="['题目名称']"
      :preview-fields="['title', 'batchNo', 'topicNo', 'sourceType', 'advisorName', 'capacity', 'submitReview']"
      :download-template-fn="() => gdTopicApi.downloadImportTemplate()"
      :upload-fn="(file) => gdTopicApi.uploadImportXlsx(file)"
      :confirm-fn="({ rows }) => gdTopicApi.importConfirm(rows)"
      :download-errors-fn="({ rows, errors }) => gdTopicApi.downloadImportErrors(rows, errors)"
      @imported="onImported"
    />
  </ModulePageShell>
</template>

<script>
/** 题目库（/admin/graduation/topic-lib）：申报/审核/分类/容量/要求/附件/历史/归档 */
import { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import { AppExportButton } from '@/components/common'
import { AppExcelImportDrawer } from '@/components/common/excel'
import { gdTopicApi } from '@/modules/graduation/api/graduation-topic.api'
import {
  GD_TOPIC_SOURCE, GD_TOPIC_REVIEW, GD_TOPIC_STATUS, GD_TOPIC_CATEGORY,
  GD_TOPIC_DIFFICULTY, IS_FULL
} from '@/modules/graduation/constants/graduation-topic.constants'
import { toast } from '@/utils/toast'

const EMPTY_FILTERS = () => ({
  keyword: '', batchId: '', sourceType: '', category: '', reviewStatus: '',
  status: '', isFull: '', archiveView: 'active',
  hasRequirements: '', hasAttachments: '', missingCategory: '',
  topicId: '', action: ''
})

const PANEL_PRESETS = {
  list: () => ({ ...EMPTY_FILTERS(), archiveView: 'active' }),
  'teacher-apply': () => ({ ...EMPTY_FILTERS(), sourceType: 'TEACHER', archiveView: 'active' }),
  enterprise: () => ({ ...EMPTY_FILTERS(), sourceType: 'ENTERPRISE', archiveView: 'active' }),
  'student-proposed': () => ({ ...EMPTY_FILTERS(), sourceType: 'STUDENT', archiveView: 'active' }),
  pending: () => ({ ...EMPTY_FILTERS(), reviewStatus: 'PENDING_REVIEW', archiveView: 'active' }),
  category: () => ({ ...EMPTY_FILTERS(), archiveView: 'active' }),
  capacity: () => ({ ...EMPTY_FILTERS(), archiveView: 'active', reviewStatus: 'APPROVED', status: 'CONFIRMED' }),
  requirements: () => ({ ...EMPTY_FILTERS(), archiveView: 'active', hasRequirements: 'false' }),
  attachments: () => ({ ...EMPTY_FILTERS(), archiveView: 'active', hasAttachments: 'false' }),
  history: () => ({ ...EMPTY_FILTERS(), keyword: '', topicId: '', action: '', archiveView: '' }),
  archive: () => ({ ...EMPTY_FILTERS(), archiveView: 'archived' })
}

/** 页内视图页签（与 PANEL_PRESETS 一一对应） */
const PANEL_TABS = [
  { key: 'list', label: '全部题目' },
  { key: 'pending', label: '待审核' },
  { key: 'teacher-apply', label: '教师申报' },
  { key: 'enterprise', label: '企业题目' },
  { key: 'student-proposed', label: '学生自拟' },
  { key: 'category', label: '分类维护' },
  { key: 'capacity', label: '容量余量' },
  { key: 'requirements', label: '待补要求' },
  { key: 'attachments', label: '待挂附件' },
  { key: 'history', label: '操作历史' },
  { key: 'archive', label: '已归档' }
]

const PANEL_HINTS = {
  list: '全部在库题目',
  'teacher-apply': '教师申报题目',
  enterprise: '企业合作题目',
  'student-proposed': '学生自拟题目',
  pending: '待审核题目',
  category: '按分类统计与维护',
  capacity: '在池题目容量与余量',
  requirements: '待补全题目要求',
  attachments: '待挂附件题目',
  history: '题目操作审计链',
  archive: '已归档题目'
}

const SOURCE_TONE = { TEACHER: 'info', ENTERPRISE: 'processing', STUDENT: 'warning', ADMIN: 'default' }

const BASE_COLUMNS = [
  { key: 'title', title: '题目' },
  { key: 'source', title: '来源' },
  { key: 'advisor', title: '指导教师' },
  { key: 'capacity', title: '容量' },
  { key: 'review', title: '审核' },
  { key: 'status', title: '状态' },
  { key: 'actions', title: '操作', width: '280px' }
]

const HISTORY_COLUMNS = [
  { key: 'historyTime', title: '时间', width: '160px' },
  { key: 'historyAction', title: '操作' },
  { key: 'historyTopic', title: '题目' },
  { key: 'historyOperator', title: '操作人' },
  { key: 'historyDetail', title: '详情' },
  { key: 'actions', title: '操作', width: '100px' }
]

const HISTORY_ACTIONS = [
  { value: '', label: '全部' },
  { value: 'CREATE', label: '创建' },
  { value: 'SUBMIT_REVIEW', label: '提交审核' },
  { value: 'REVIEW', label: '审核' },
  { value: 'UPDATE', label: '编辑' },
  { value: 'UPDATE_ATTACHMENTS', label: '附件' },
  { value: 'DISABLE', label: '停用' },
  { value: 'ENABLE', label: '启用' },
  { value: 'ARCHIVE', label: '归档' }
]

const TOPIC_LIB_INLINE_ROUTES = new Set([
  'graduation-topic-lib-create',
  'graduation-topic-lib-edit',
  'graduation-topic-lib-capacity',
  'graduation-topic-lib-requirements',
  'graduation-topic-lib-attachments',
  'graduation-topic-lib-category',
  'graduation-topic-lib-detail'
])

import GraduationBatchStrip from './_shared/GraduationBatchStrip.vue'

export default {
  name: 'TopicLibListView',
  components: { GraduationBatchStrip, ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag, LoadingState, ErrorState, EmptyState, AppConfirmDialog, AppExcelImportDrawer, AppExportButton },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      GD_TOPIC_CATEGORY, GD_TOPIC_DIFFICULTY,
      loading: true, error: '', submitting: false, activePanel: 'list',
      panelTabs: PANEL_TABS,
      rows: [], total: 0, page: 1, pageSize: 10, filters: EMPTY_FILTERS(),
      batchOpts: [], categoryStats: [], libStats: null,
      importVisible: false,
      confirm: { visible: false, title: '', message: '', type: 'primary', confirmText: '确认', requireReason: false, reasonLabel: '原因', action: null, row: null, payload: null }
    }
  },
  computed: {
    inlineOpen() {
      return TOPIC_LIB_INLINE_ROUTES.has(this.$route.name)
    },
    isHistoryPanel() { return this.activePanel === 'history' },
    panelOnlyOps() { return ['category', 'capacity', 'requirements', 'attachments'].includes(this.activePanel) },
    columns() {
      if (this.isHistoryPanel) return HISTORY_COLUMNS
      if (this.activePanel === 'category') {
        return [
          { key: 'title', title: '题目' },
          { key: 'category', title: '分类' },
          { key: 'advisor', title: '指导教师' },
          { key: 'capacity', title: '容量' },
          { key: 'status', title: '状态' },
          { key: 'actions', title: '操作', width: '180px' }
        ]
      }
      if (this.activePanel === 'capacity') {
        return [
          { key: 'title', title: '题目' },
          { key: 'advisor', title: '指导教师' },
          { key: 'capacity', title: '容量/余量' },
          { key: 'status', title: '状态' },
          { key: 'actions', title: '操作', width: '140px' }
        ]
      }
      if (this.activePanel === 'requirements') {
        return [
          { key: 'title', title: '题目' },
          { key: 'requirements', title: '题目要求' },
          { key: 'advisor', title: '指导教师' },
          { key: 'review', title: '审核' },
          { key: 'actions', title: '操作', width: '140px' }
        ]
      }
      if (this.activePanel === 'attachments') {
        return [
          { key: 'title', title: '题目' },
          { key: 'attachments', title: '附件' },
          { key: 'advisor', title: '指导教师' },
          { key: 'status', title: '状态' },
          { key: 'actions', title: '操作', width: '140px' }
        ]
      }
      return BASE_COLUMNS
    },
    filterFields() {
      if (this.isHistoryPanel) {
        return [
          { key: 'keyword', label: '关键词', type: 'text', placeholder: '题目 / 操作 / 详情' },
          { key: 'topicId', label: '题目编号', type: 'text', placeholder: '按题目编号精确筛选' },
          { key: 'action', label: '操作类型', type: 'select', options: HISTORY_ACTIONS }
        ]
      }
      const batchOpts = this.batchOpts.map((b) => ({ value: b.id, label: b.batchName }))
      const catOpts = [{ value: '', label: '全部' }, ...GD_TOPIC_CATEGORY.map((c) => ({ value: c, label: c })), { value: '__uncat__', label: '未分类' }]
      const base = [
        { key: 'keyword', label: '关键词', type: 'text', placeholder: '题目 / 教师 / 企业' },
        { key: 'batchId', label: '批次', type: 'select', options: batchOpts }
      ]
      if (this.activePanel === 'category') {
        return [...base, { key: 'category', label: '分类', type: 'select', options: catOpts }]
      }
      if (this.activePanel === 'capacity') {
        return [
          ...base,
          { key: 'isFull', label: '满员', type: 'select', options: IS_FULL }
        ]
      }
      if (this.activePanel === 'requirements') {
        return [
          ...base,
          { key: 'hasRequirements', label: '要求状态', type: 'select', options: [
            { value: 'false', label: '待补全' }, { value: 'true', label: '已填写' }, { value: '', label: '全部' }
          ] }
        ]
      }
      if (this.activePanel === 'attachments') {
        return [
          ...base,
          { key: 'hasAttachments', label: '附件状态', type: 'select', options: [
            { value: 'false', label: '无附件' }, { value: 'true', label: '已有附件' }, { value: '', label: '全部' }
          ] }
        ]
      }
      if (this.activePanel === 'list') {
        return [
          ...base,
          { key: 'sourceType', label: '来源', type: 'select', options: GD_TOPIC_SOURCE },
          { key: 'reviewStatus', label: '审核', type: 'select', options: GD_TOPIC_REVIEW },
          { key: 'status', label: '状态', type: 'select', options: GD_TOPIC_STATUS },
          { key: 'isFull', label: '满员', type: 'select', options: IS_FULL }
        ]
      }
      if (this.activePanel === 'archive') {
        return [{ key: 'keyword', label: '关键词', type: 'text', placeholder: '题目名称' }]
      }
      return base
    },
    toolbarActions() {
      const createPanels = ['list', 'teacher-apply', 'enterprise', 'student-proposed']
      const base = []
      if (createPanels.includes(this.activePanel)) {
        const labels = { list: '＋ 申报题目', 'teacher-apply': '＋ 教师申报', enterprise: '＋ 企业题目', 'student-proposed': '＋ 学生自拟' }
        base.push({ key: 'create', label: labels[this.activePanel], variant: 'primary' })
      }
      if (['list', 'teacher-apply', 'enterprise', 'student-proposed', 'pending', 'archive', 'category', 'capacity', 'requirements', 'attachments', 'history'].includes(this.activePanel)) {
        if (this.activePanel !== 'history') {
          base.push({ key: 'import', label: '导入 Excel' })
        }
      }
      if (this.activePanel === 'category') {
        base.unshift({ key: 'refreshStats', label: '刷新统计' })
      }
      return base
    },
    exportVisible() {
      return ['list', 'teacher-apply', 'enterprise', 'student-proposed', 'pending', 'archive', 'category', 'capacity', 'requirements', 'attachments', 'history'].includes(this.activePanel)
    },
    pageSubtitle() {
      const gap = this.libStats && this.activePanel === 'requirements'
        ? ` · 待补 ${this.libStats.requirementsGap} 题`
        : this.libStats && this.activePanel === 'attachments'
          ? ` · 缺附件 ${this.libStats.attachmentsGap} 题`
          : ''
      return `共 ${this.total} 条 · ${PANEL_HINTS[this.activePanel] || ''}${gap}`
    },
    emptyTitle() {
      const m = {
        pending: '暂无待审核题目', archive: '暂无归档题目',
        requirements: '题目要求均已补全', attachments: '附件均已挂接', history: '暂无操作记录'
      }
      return m[this.activePanel] || '暂无题目'
    },
    emptyDesc() {
      if (['teacher-apply', 'enterprise', 'student-proposed', 'list'].includes(this.activePanel)) {
        return '点「申报」创建题目，保存后可提交审核'
      }
      if (this.activePanel === 'requirements') return '可在题目申报时填写要求，或通过导入 Excel 批量维护'
      if (this.activePanel === 'attachments') return '为题目挂接任务书、参考资料等附件元数据'
      if (this.activePanel === 'history') return '题目创建、审核、容量调整等操作均会留痕'
      return '可调整筛选条件'
    },
    defaultSourceType() {
      const m = { 'teacher-apply': 'TEACHER', enterprise: 'ENTERPRISE', 'student-proposed': 'STUDENT' }
      return m[this.activePanel] || 'TEACHER'
    }
  },
  watch: {
    '$route.query.panel': {
      immediate: true,
      handler(panel) {
        this.applyPanel((panel || 'list').toString())
      }
    },
    inlineOpen(val, oldVal) {
      if (oldVal && !val) {
        this.loadPanelExtras()
        this.load()
      }
    }
  },
  created() {
    this.loadBatchOpts()
  },
  methods: {
    truncate(s, n) {
      if (!s) return ''
      return s.length <= n ? s : `${s.slice(0, n)}…`
    },
    sourceTone(t) { return SOURCE_TONE[t] || 'default' },
    canEdit(row) {
      return row.status !== 'ARCHIVED' && row.reviewStatus !== 'PENDING_REVIEW' && !(row.selected > 0 && row.reviewStatus === 'APPROVED')
    },
    /** 页内页签切换：统一回到列表路由并改 query，由 watcher 应用视图（内嵌子路由打开时也能返回） */
    switchPanel(p) {
      if (p === this.activePanel && !this.inlineOpen) return
      this.$router.push({ path: '/admin/graduation/topic-lib', query: { panel: p } })
    },
    applyPanel(panel) {
      const key = PANEL_PRESETS[panel] ? panel : 'list'
      this.activePanel = key
      this.filters = (PANEL_PRESETS[key] || PANEL_PRESETS.list)()
      this.page = 1
      this.loadPanelExtras()
      this.load()
    },
    async loadPanelExtras() {
      if (this.activePanel === 'category' || this.activePanel === 'capacity' || this.activePanel === 'requirements' || this.activePanel === 'attachments') {
        const s = await gdTopicApi.getStats()
        if (s.code === 0) {
          this.libStats = s.data
          this.categoryStats = s.data.categoryStats || []
        }
      } else {
        this.categoryStats = []
        this.libStats = null
      }
    },
    drillCategory(cat) {
      if (cat === '未分类') {
        this.filters.category = ''
        this.filters.missingCategory = 'true'
      } else {
        this.filters.category = cat
        this.filters.missingCategory = ''
      }
      this.page = 1
      this.load()
    },
    async loadBatchOpts() {
      const b = await gdTopicApi.getBatchOptions()
      if (b.code === 0) this.batchOpts = b.data
    },
    buildParams() {
      if (this.isHistoryPanel) {
        return {
          page: this.page, pageSize: this.pageSize,
          keyword: this.filters.keyword || undefined,
          topicId: this.filters.topicId || undefined,
          action: this.filters.action || undefined
        }
      }
      const p = { page: this.page, pageSize: this.pageSize, keyword: this.filters.keyword || undefined, batchId: this.filters.batchId || undefined }
      if (this.filters.sourceType) p.sourceType = this.filters.sourceType
      if (this.filters.category && this.filters.category !== '__uncat__') p.category = this.filters.category
      if (this.filters.category === '__uncat__' || this.filters.missingCategory === 'true') p.missingCategory = true
      if (this.filters.reviewStatus) p.reviewStatus = this.filters.reviewStatus
      if (this.filters.status) p.status = this.filters.status
      if (this.filters.isFull === 'true') p.isFull = true
      if (this.filters.isFull === 'false') p.isFull = false
      if (this.filters.archiveView) p.archiveView = this.filters.archiveView
      if (this.filters.hasRequirements === 'true') p.hasRequirements = true
      if (this.filters.hasRequirements === 'false') p.hasRequirements = false
      if (this.filters.hasAttachments === 'true') p.hasAttachments = true
      if (this.filters.hasAttachments === 'false') p.hasAttachments = false
      return p
    },
    async load() {
      this.loading = true
      this.error = ''
      const r = this.isHistoryPanel
        ? await gdTopicApi.getTopicHistory(this.buildParams())
        : await gdTopicApi.getTopics(this.buildParams())
      this.loading = false
      if (r.code !== 0) { this.error = r.message || '加载失败'; this.rows = []; this.total = 0; return }
      this.rows = r.data.list
      this.total = r.data.total
    },
    search() { this.page = 1; this.load() },
    reset() {
      this.filters = (PANEL_PRESETS[this.activePanel] || PANEL_PRESETS.list)()
      this.page = 1
      this.load()
    },
    turnPage(p) {
      const page = typeof p === 'number' ? p : p?.page
      const pageSize = typeof p === 'object' && p ? p.pageSize : this.pageSize
      if (page) this.page = page
      if (pageSize) this.pageSize = pageSize
      this.load()
    },
    onToolbar(key) {
      if (key === 'create') this.openCreate()
      if (key === 'import') { this.importVisible = true }
      if (key === 'refreshStats') this.loadPanelExtras()
    },
    topicReturnQuery() {
      return { returnPanel: this.activePanel }
    },
    openCreate() {
      this.$router.push({
        path: '/admin/graduation/topic-lib/create',
        query: { sourceType: this.defaultSourceType, ...this.topicReturnQuery() }
      })
    },
    openEdit(row) {
      this.$router.push({
        path: `/admin/graduation/topic-lib/${row.id}/edit`,
        query: this.topicReturnQuery()
      })
    },
    openCapacity(row) {
      this.$router.push({
        path: `/admin/graduation/topic-lib/${row.id}/capacity`,
        query: this.topicReturnQuery()
      })
    },
    openRequirements(row) {
      this.$router.push({
        path: `/admin/graduation/topic-lib/${row.id}/requirements`,
        query: this.topicReturnQuery()
      })
    },
    openAttachments(row) {
      this.$router.push({
        path: `/admin/graduation/topic-lib/${row.id}/attachments`,
        query: this.topicReturnQuery()
      })
    },
    openCategoryEdit(row) {
      this.$router.push({
        path: `/admin/graduation/topic-lib/${row.id}/category`,
        query: this.topicReturnQuery()
      })
    },
    openDetail(row) {
      this.$router.push({
        path: `/admin/graduation/topic-lib/${row.id}`,
        query: this.topicReturnQuery()
      })
    },
    openDetailById(topicId) {
      this.$router.push({
        path: `/admin/graduation/topic-lib/${topicId}`,
        query: this.topicReturnQuery()
      })
    },
    askSubmitReview(row) {
      this.confirm = { visible: true, title: '提交审核', message: `确认提交「${row.title}」进入审核？`, type: 'primary', confirmText: '提交', requireReason: false, action: 'submitReview', row }
    },
    askReview(row, action) {
      this.confirm = {
        visible: true, title: action === 'APPROVE' ? '审核通过' : '驳回题目',
        message: action === 'APPROVE' ? `通过后题目入池，可分配给学生。` : `驳回须填写原因（≥5字）。`,
        type: action === 'APPROVE' ? 'primary' : 'danger', confirmText: action === 'APPROVE' ? '通过' : '驳回',
        requireReason: action === 'REJECT', reasonLabel: '驳回原因', action: 'review', row, payload: { action }
      }
    },
    askDisable(row) {
      this.confirm = { visible: true, title: '停用题目', message: '停用后不可再分配新学生，已选学生不受影响。', type: 'warning', confirmText: '停用', requireReason: true, reasonLabel: '停用原因', action: 'disable', row }
    },
    askEnable(row) {
      this.confirm = { visible: true, title: '启用题目', message: `确认重新启用「${row.title}」？`, type: 'primary', confirmText: '启用', requireReason: false, action: 'enable', row }
    },
    askArchive(row) {
      this.confirm = { visible: true, title: '归档题目', message: '归档后题目移出在库列表。', type: 'warning', confirmText: '归档', requireReason: false, reasonLabel: '归档原因', action: 'archive', row }
    },
    async onConfirm({ reason }) {
      const row = this.confirm.row
      const action = this.confirm.action
      this.submitting = true
      let r = { code: 1 }
      if (action === 'submitReview') r = await gdTopicApi.submitReview(row.id)
      else if (action === 'review') r = await gdTopicApi.reviewTopic(row.id, { action: this.confirm.payload.action, comment: reason || '' })
      else if (action === 'disable') r = await gdTopicApi.disableTopic(row.id, { reason })
      else if (action === 'enable') r = await gdTopicApi.enableTopic(row.id)
      else if (action === 'archive') r = await gdTopicApi.archiveTopic(row.id, { reason: reason || '' })
      this.submitting = false
      if (r.code !== 0) { toast.error(r.message); return }
      toast.success('操作成功')
      this.confirm.visible = false
      this.loadPanelExtras()
      this.load()
    },
    onImported() {
      this.importVisible = false
      toast.success('题目导入完成')
      this.loadPanelExtras()
      this.load()
    },
    exportTopicsLibFn() {
      const p = this.buildParams()
      delete p.page
      delete p.pageSize
      return this.isHistoryPanel ? gdTopicApi.exportTopicHistory(p) : gdTopicApi.exportTopics(p)
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.gd-actions { display: flex; align-items: center; gap: var(--space-2); flex-wrap: wrap; }
.mp-stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: var(--space-3); margin-bottom: var(--space-4); }
.mp-stat { width: 100%; min-width: 0; padding: var(--space-3); border: 1px solid var(--border-light); border-radius: var(--radius-md); background: linear-gradient(145deg, var(--color-bg-subtle), var(--card)); box-shadow: 0 1px 1px rgba(15, 23, 42, .02); color: inherit; font: inherit; text-align: left; transition: border-color .15s ease, box-shadow .15s ease, transform .15s ease; }
.mp-stat[type='button'] { cursor: pointer; }
.mp-stat:hover { border-color: var(--primary-200, #bfdbfe); box-shadow: var(--s1); }
.mp-stat[type='button']:hover { transform: translateY(-2px); }
.mp-stat[type='button']:focus-visible { outline: 2px solid var(--primary-400, #60a5fa); outline-offset: 2px; }
.mp-stat__val { font-size: calc(var(--font-size-xl) + 2px); font-weight: var(--font-weight-semibold); color: var(--text-primary); font-variant-numeric: tabular-nums; }
.mp-stat__lbl { color: var(--color-text-secondary); font-size: var(--font-size-sm); font-weight: var(--font-weight-medium); margin-top: var(--space-1); }
.mp-stat__sub { color: var(--color-text-tertiary); font-size: var(--font-size-xs); margin-top: var(--space-1); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
</style>
