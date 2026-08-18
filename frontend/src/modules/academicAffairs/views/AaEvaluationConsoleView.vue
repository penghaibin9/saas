<template>
  <ModulePageShell
    title="教学评价 · 教务处控制台"
    :subtitle="'评教批次生命周期 · 学生匿名评教 · 结果分级 · 申诉两级审核'"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="aaev-tabs">
      <button v-for="t in tabs" :key="t.key" :class="['aaev-tab', { 'is-active': tab === t.key }]" @click="switchTab(t.key)">{{ t.label }}</button>
    </div>

    <div v-if="viewMode === 'byType'" class="mp-stack">
      <AppInlineAlert type="info" :description="'当前视图：' + typeViewLabel + '。按评价类型过滤应评任务；可在「评教批次」生成对应来源任务。'" />
      <div class="aaev-layout">
        <div class="aaev-list-pane">
          <ul class="aaev-list">
            <li
              v-for="b in rows"
              :key="b.batchId"
              :class="['aaev-item', { 'is-active': current && current.batchId === b.batchId }]"
              role="button"
              tabindex="0"
              :aria-current="current && current.batchId === b.batchId ? 'true' : undefined"
              @click="selectTyped(b)"
              @keydown.enter.prevent="selectTyped(b)"
              @keydown.space.prevent="selectTyped(b)"
            >
              <span>{{ b.batchName }}</span>
              <StatusTag :type="bType(b.status)" :label="bLabel(b.status)" dot />
            </li>
          </ul>
          <AppPagination
            :total="batchPagination.total"
            :page="batchPagination.page"
            :page-size="batchPagination.pageSize"
            :show-size-changer="false"
            @change="onBatchPaginationChange"
          />
        </div>
        <div class="aaev-detail">
          <EmptyState v-if="!current" title="选择批次" :description="'查看' + typeViewLabel + '应评任务'" />
          <template v-else>
            <div class="aaev-head">
              <div><div class="aaev-title">{{ current.batchName }} · {{ typeViewLabel }}</div>
                <StatusTag :type="bType(current.status)" :label="bLabel(current.status)" dot /></div>
            </div>
            <EmptyState v-if="!tasks.length" :title="'暂无' + typeViewLabel + '任务'" description="请在「评教批次」生成对应来源的应评任务" />
            <DataTable v-else :columns="taskColumns" :rows="tasks" row-key="taskId">
              <template #cell-status="{ row }"><StatusTag :type="row.status === 'SUBMITTED' ? 'success' : 'primary'" :label="row.status" dot /></template>
            </DataTable>
          </template>
        </div>
      </div>
    </div>

    <div v-else-if="viewMode === 'stats'" class="mp-stack">
      <AppInlineAlert type="info" description="评价统计：选择批次查看等级分布与各来源参评率。" />
      <div class="aaev-layout">
        <div class="aaev-list-pane">
          <ul class="aaev-list">
            <li
              v-for="b in rows"
              :key="b.batchId"
              :class="['aaev-item', { 'is-active': current && current.batchId === b.batchId }]"
              role="button"
              tabindex="0"
              :aria-current="current && current.batchId === b.batchId ? 'true' : undefined"
              @click="selectStats(b)"
              @keydown.enter.prevent="selectStats(b)"
              @keydown.space.prevent="selectStats(b)"
            >
              <span>{{ b.batchName }}</span>
              <StatusTag :type="bType(b.status)" :label="bLabel(b.status)" dot />
            </li>
          </ul>
          <AppPagination
            :total="batchPagination.total"
            :page="batchPagination.page"
            :page-size="batchPagination.pageSize"
            :show-size-changer="false"
            @change="onBatchPaginationChange"
          />
        </div>
        <div class="aaev-detail">
          <EmptyState v-if="!current" title="选择批次" description="查看评价统计" />
          <template v-else-if="stats">
            <div class="aaev-section-title">{{ current.batchName }} · 统计</div>
            <p>结果数 {{ stats.resultCount ?? 0 }} · 学生均分均值 {{ stats.overallAvg ?? '—' }}</p>
            <div class="aaev-section-title">等级分布</div>
            <DataTable :columns="statsLevelColumns" :rows="statsLevelRows" row-key="level" />
            <div class="aaev-section-title">参评率</div>
            <DataTable :columns="statsPartColumns" :rows="statsPartRows" row-key="type" />
          </template>
        </div>
      </div>
    </div>

    <div v-else-if="viewMode === 'archive'" class="mp-stack">
      <AppInlineAlert type="info" description="评价归档：仅展示已归档批次及其结果，只读。" />
      <EmptyState v-if="!archivedRows.length" title="暂无已归档批次" description="在「评教批次」对结果就绪批次执行归档后会出现在此" />
      <div v-else class="aaev-layout">
        <div class="aaev-list-pane">
          <ul class="aaev-list">
            <li
              v-for="b in archivedRows"
              :key="b.batchId"
              :class="['aaev-item', { 'is-active': current && current.batchId === b.batchId }]"
              role="button"
              tabindex="0"
              :aria-current="current && current.batchId === b.batchId ? 'true' : undefined"
              @click="select(b)"
              @keydown.enter.prevent="select(b)"
              @keydown.space.prevent="select(b)"
            >
              <span>{{ b.batchName }}</span>
              <StatusTag type="default" label="已归档" dot />
            </li>
          </ul>
          <AppPagination
            :total="archivePagination.total"
            :page="archivePagination.page"
            :page-size="archivePagination.pageSize"
            :show-size-changer="false"
            @change="onArchivePaginationChange"
          />
        </div>
        <div class="aaev-detail">
          <EmptyState v-if="!current" title="选择归档批次" description="查看归档结果" />
          <template v-else>
            <div class="aaev-title">{{ current.batchName }}</div>
            <EmptyState v-if="!results.length" title="无结果" description="该归档批次暂无评价结果" />
            <DataTable
              v-else
              :columns="resultColumns"
              :rows="results"
              row-key="resultId"
              :pagination="resultPagination"
              @page-change="onResultPageChange"
            >
              <template #cell-level="{ row }"><StatusTag :type="lvType(row.level)" :label="lvLabel(row.level)" dot /></template>
            </DataTable>
          </template>
        </div>
      </div>
    </div>

    <div v-else-if="tab === 'batches'" class="mp-stack">
      <div class="aaev-bar"><AppButton variant="primary" size="small" @click="openCreate">新建评教批次</AppButton></div>
      <div class="aaev-layout">
        <div class="aaev-list-pane">
          <ul class="aaev-list">
            <li
              v-for="b in rows"
              :key="b.batchId"
              :class="['aaev-item', { 'is-active': current && current.batchId === b.batchId }]"
              role="button"
              tabindex="0"
              :aria-current="current && current.batchId === b.batchId ? 'true' : undefined"
              @click="select(b)"
              @keydown.enter.prevent="select(b)"
              @keydown.space.prevent="select(b)"
            >
              <span>{{ b.batchName }}</span>
              <StatusTag :type="bType(b.status)" :label="bLabel(b.status)" dot />
            </li>
          </ul>
          <AppPagination
            :total="batchPagination.total"
            :page="batchPagination.page"
            :page-size="batchPagination.pageSize"
            :show-size-changer="false"
            @change="onBatchPaginationChange"
          />
        </div>
        <div class="aaev-detail">
          <EmptyState v-if="!current" title="选择批次" description="从左侧选择评教批次管理生命周期" />
          <template v-else>
            <div class="aaev-head">
              <div><div class="aaev-title">{{ current.batchName }}</div><StatusTag :type="bType(current.status)" :label="bLabel(current.status)" dot /></div>
              <div class="aaev-actions">
                <AppButton v-if="current.status === 'DRAFT'" size="small" variant="ghost" @click="openGenTasks">生成应评任务</AppButton>
                <AppButton v-if="current.status === 'DRAFT'" size="small" variant="primary" @click="lc('publish', '发布')">发布</AppButton>
                <AppButton v-if="current.status === 'PUBLISHED'" size="small" variant="primary" @click="lc('open', '开放评教')">开放</AppButton>
                <AppButton v-if="current.status === 'OPEN'" size="small" variant="warning" @click="lc('closeScore', '关闭核算')">关闭核算</AppButton>
                <AppButton v-if="current.status === 'RESULT_READY'" size="small" variant="primary" @click="lc('publishResults', '发布结果')">发布结果</AppButton>
                <AppButton v-if="current.status === 'RESULT_READY'" size="small" variant="ghost" @click="lc('archive', '归档')">归档</AppButton>
              </div>
            </div>
            <div class="aaev-section-title">应评任务</div>
            <EmptyState v-if="!tasks.length" title="未生成应评任务" description="DRAFT 阶段从教学任务生成" />
            <DataTable v-else :columns="taskColumns" :rows="tasks" row-key="taskId">
              <template #cell-status="{ row }"><StatusTag :type="row.status === 'SUBMITTED' ? 'success' : 'primary'" :label="row.status" dot /></template>
            </DataTable>
            <template v-if="results.length">
              <div class="aaev-section-title">评价结果</div>
              <DataTable
                :columns="resultColumns"
                :rows="results"
                row-key="resultId"
                :pagination="resultPagination"
                @page-change="onResultPageChange"
              >
                <template #cell-level="{ row }"><StatusTag :type="lvType(row.level)" :label="lvLabel(row.level)" dot /></template>
              </DataTable>
            </template>
          </template>
        </div>
      </div>
    </div>

    <div v-else class="mp-stack">
      <EmptyState v-if="!appeals.length" title="暂无申诉" description="教师对评价结果申诉后在此审核" />
      <DataTable
        v-else
        :columns="appealColumns"
        :rows="appeals"
        row-key="appealId"
        :pagination="appealPagination"
        @page-change="onAppealPageChange"
      >
        <template #cell-status="{ row }"><StatusTag :type="row.status === 'RESOLVED' ? 'success' : row.status === 'REJECTED' ? 'danger' : 'primary'" :label="row.status" dot /></template>
        <template #cell-ops="{ row }">
          <button v-if="['SUBMITTED','COLLEGE_REVIEW'].includes(row.status)" class="mp-link" :disabled="confirmSubmitting" @click="approveAppeal(row)">{{ row.status === 'SUBMITTED' ? '学院初审通过' : '教务终审通过' }}</button>
          <button v-if="['SUBMITTED','COLLEGE_REVIEW'].includes(row.status)" class="mp-link is-danger" :disabled="confirmSubmitting" @click="rejectAppeal(row.appealId)">驳回</button>
        </template>
      </DataTable>
    </div>

    <AppDrawer :visible="createVisible" title="新建评教批次" mode="modal" size="medium" @close="createVisible = false">
      <div class="aaev-form">
        <AppFormItem label="批次名称" required><AppTextInput v-model="form.batchName" placeholder="如 2024秋学生评教" :disabled="saving" /></AppFormItem>
        <AppFormItem label="学期"><AppTermEntityPicker v-model="form.termId" placeholder="选择学期（可空）" :disabled="saving" /></AppFormItem>
        <AppInlineAlert type="info" description="问卷模板本期用默认客观5级量表；匿名默认开启（学生评教架构级不留身份）。" />
        <AppInlineAlert v-if="formError" type="danger" :description="formError" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="saving" @click="createVisible = false">取消</AppButton>
        <AppButton variant="primary" :loading="saving" @click="submitCreate">创建</AppButton>
      </template>
    </AppDrawer>

    <AppDrawer :visible="genVisible" title="生成应评任务" mode="modal" size="medium" @close="genVisible = false">
      <div class="aaev-form">
        <AppFormItem label="评价来源">
          <AppSelect v-model="genType" :options="genTypeOptions" :disabled="saving" />
        </AppFormItem>
        <AppFormItem label="教学任务" required><AppTeachingTaskPicker v-model="genTaskIds" multiple :query="{ termId: current && current.termId || undefined }" :disabled="saving" /></AppFormItem>
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="saving" @click="genVisible = false">取消</AppButton>
        <AppButton variant="primary" :loading="saving" @click="submitGen">生成</AppButton>
      </template>
    </AppDrawer>

    <AppConfirmDialog
      v-model:visible="confirmVisible"
      :title="confirmTitle"
      :message="confirmMessage"
      :confirm-text="confirmText"
      :require-reason="confirmRequireReason"
      :reason-label="confirmReasonLabel"
      :submitting="confirmSubmitting"
      @confirm="onConfirm"
    />
  </ModulePageShell>
</template>

<script>
/** 教学评价 · 教务处控制台（/admin/academic-affairs/evaluation）：批次生命周期 + 结果分级 + 申诉。 */
import { ModulePageShell, DataTable, StatusTag, EmptyState } from '@/components/business'
import { AppButton, AppDrawer } from '@/components/ui'
import { AppTextInput, AppFormItem, AppSelect, AppConfirmDialog, AppInlineAlert, AppTermEntityPicker, AppTeachingTaskPicker, AppPagination } from '@/components/common'
import { academicAffairsApi, academicAffairsEvaluationApi as api } from '@/modules/academicAffairs/api/academic-affairs.api'
import { toast } from '@/utils/toast'

const _BL = { DRAFT: '草稿', PUBLISHED: '已发布', OPEN: '评教中', CLOSED: '已关闭', RESULT_READY: '结果就绪', ARCHIVED: '已归档' }
const _LV = { EXCELLENT: '优秀', GOOD: '良好', PASS: '合格', NEED_IMPROVE: '需整改' }
const freshPagination = (pageSize) => ({ page: 1, pageSize, total: 0 })

export default {
  name: 'AaEvaluationConsoleView',
  components: { ModulePageShell, DataTable, StatusTag, EmptyState, AppButton, AppDrawer, AppTextInput, AppFormItem, AppSelect, AppConfirmDialog, AppInlineAlert, AppTermEntityPicker, AppTeachingTaskPicker, AppPagination },
  data() {
    return {
      ctx: { currentRole: { roleName: '' }, dataScope: { scopeName: '' } },
      tab: 'batches', tabs: [{ key: 'batches', label: '评教批次' }, { key: 'appeals', label: '申诉审核' }],
      typeViewMap: {
        studentEval: { type: 'STUDENT', label: '学生评教' },
        selfEval: { type: 'SELF', label: '教师自评' },
        peerEval: { type: 'PEER', label: '同行评价' },
        supervisorEval: { type: 'SUPERVISOR', label: '督导评价' }
      },
      rows: [], archivedRows: [], current: null, tasks: [], results: [], appeals: [], stats: null,
      batchPagination: freshPagination(30),
      archivePagination: freshPagination(30),
      resultPagination: freshPagination(50),
      appealPagination: freshPagination(50),
      taskColumns: [{ key: 'courseName', title: '课程' }, { key: 'teacherName', title: '教师' }, { key: 'submittedCount', title: '已评' }, { key: 'status', title: '状态' }],
      resultColumns: [{ key: 'teacherName', title: '教师' }, { key: 'courseName', title: '课程' }, { key: 'studentAvg', title: '学生均分' }, { key: 'supervisorAvg', title: '督导' }, { key: 'peerAvg', title: '同行' }, { key: 'selfScore', title: '自评' }, { key: 'compositeScore', title: '综合分' }, { key: 'level', title: '等级' }],
      appealColumns: [{ key: 'teacherKey', title: '教师' }, { key: 'reason', title: '申诉理由' }, { key: 'status', title: '状态' }, { key: 'ops', title: '操作' }],
      statsLevelColumns: [{ key: 'level', title: '等级' }, { key: 'count', title: '人数' }],
      statsPartColumns: [{ key: 'type', title: '来源' }, { key: 'total', title: '应评' }, { key: 'submitted', title: '已评' }, { key: 'rate', title: '参评率%' }],
      createVisible: false, form: { batchName: '', termId: '' }, formError: '',
      genVisible: false, genTaskIds: [], genType: 'STUDENT',
      genTypeOptions: [
        { label: '学生评教', value: 'STUDENT' }, { label: '教师自评', value: 'SELF' },
        { label: '同行评价', value: 'PEER' }, { label: '督导评价', value: 'SUPERVISOR' }
      ],
      saving: false,
      confirmVisible: false, confirmTitle: '', confirmMessage: '', confirmText: '确认操作', pendingAction: null,
      confirmRequireReason: false, confirmReasonLabel: '', confirmSubmitting: false, queryTab: ''
    }
  },
  computed: {
    viewMode() {
      if (this.typeViewMap[this.queryTab]) return 'byType'
      if (this.queryTab === 'evalStats') return 'stats'
      if (this.queryTab === 'archive') return 'archive'
      return 'main'
    },
    typeViewLabel() { return (this.typeViewMap[this.queryTab] || {}).label || '' },
    typeFilter() { return (this.typeViewMap[this.queryTab] || {}).type || '' },
    statsLevelRows() {
      const by = (this.stats && this.stats.byLevel) || {}
      return Object.keys(by).map((k) => ({ level: this.lvLabel(k), count: by[k] }))
    },
    statsPartRows() {
      const p = (this.stats && this.stats.participation) || {}
      return Object.keys(p).map((k) => ({ type: k, total: p[k].total, submitted: p[k].submitted, rate: p[k].rate }))
    }
  },
  async created() {
    const c = await academicAffairsApi.getContext()
    if (c.code === 0) this.ctx = c.data
    const q = this.$route && this.$route.query && this.$route.query.tab
    this.queryTab = q || ''
    if (q && this.tabs.some((t) => t.key === q)) this.tab = q
    if (this.viewMode === 'archive') await this.loadArchived()
    else await this.loadBatches()
    if (this.tab === 'appeals') await this.loadAppeals()
  },
  methods: {
    bLabel(s) { return _BL[s] || s },
    bType(s) { return s === 'OPEN' ? 'success' : ['ARCHIVED', 'CLOSED'].includes(s) ? 'default' : s === 'RESULT_READY' ? 'warning' : 'primary' },
    lvLabel(l) { return _LV[l] || l || '—' },
    lvType(l) { return l === 'EXCELLENT' ? 'success' : l === 'NEED_IMPROVE' ? 'danger' : 'primary' },
    switchTab(k) {
      if (this.confirmSubmitting) return
      this.tab = k
      this.queryTab = ''
      if (k === 'appeals') {
        this.appealPagination.page = 1
        this.loadAppeals()
      }
    },
    async loadBatches() {
      try {
        const res = await api.listBatches({ page: this.batchPagination.page, pageSize: this.batchPagination.pageSize })
        if (res.code === 0) {
          this.rows = res.data.list
          this.batchPagination.total = res.data.total
        } else toast.error(res.message || '评教批次加载失败')
      } catch (e) {
        toast.error((e && e.message) || '评教批次加载失败')
      }
    },
    async loadArchived() {
      try {
        const res = await api.archivedBatches({ page: this.archivePagination.page, pageSize: this.archivePagination.pageSize })
        if (res.code === 0) {
          this.archivedRows = res.data.list
          this.archivePagination.total = res.data.total
        } else toast.error(res.message || '评教归档批次加载失败')
      } catch (e) {
        toast.error((e && e.message) || '评教归档批次加载失败')
      }
    },
    onBatchPaginationChange({ page }) {
      if (!page || page === this.batchPagination.page) return
      this.batchPagination.page = page
      this.current = null
      this.tasks = []
      this.results = []
      this.stats = null
      this.loadBatches()
    },
    onArchivePaginationChange({ page }) {
      if (!page || page === this.archivePagination.page) return
      this.archivePagination.page = page
      this.current = null
      this.tasks = []
      this.results = []
      this.loadArchived()
    },
    async loadCurrentResults() {
      if (!this.current) { this.results = []; this.resultPagination.total = 0; return }
      try {
        const res = await api.results(this.current.batchId, {
          page: this.resultPagination.page,
          pageSize: this.resultPagination.pageSize
        })
        if (res.code === 0) {
          this.results = res.data.list
          this.resultPagination.total = res.data.total
        } else toast.error(res.message || '评价结果加载失败')
      } catch (e) {
        toast.error((e && e.message) || '评价结果加载失败')
      }
    },
    async select(b) {
      if (this.confirmSubmitting) return
      this.current = b
      this.resultPagination.page = 1
      try {
        const t = await api.listTasks(b.batchId)
        this.tasks = t.code === 0 ? (t.data.items || []) : []
        if (t.code !== 0) toast.error(t.message || '应评任务加载失败')
      } catch (e) {
        this.tasks = []
        toast.error((e && e.message) || '应评任务加载失败')
      }
      await this.loadCurrentResults()
    },
    async selectTyped(b) {
      if (this.confirmSubmitting) return
      this.current = b
      this.results = []
      this.resultPagination.total = 0
      try {
        const t = await api.listTasks(b.batchId, { evaluatorType: this.typeFilter })
        this.tasks = t.code === 0 ? (t.data.items || t.data.list || []) : []
        if (t.code !== 0) toast.error(t.message || '应评任务加载失败')
      } catch (e) {
        this.tasks = []
        toast.error((e && e.message) || '应评任务加载失败')
      }
    },
    async selectStats(b) {
      if (this.confirmSubmitting) return
      this.current = b
      try {
        const res = await api.stats(b.batchId)
        this.stats = res.code === 0 ? res.data : null
        if (res.code !== 0) toast.error(res.message || '评价统计加载失败')
      } catch (e) {
        this.stats = null
        toast.error((e && e.message) || '评价统计加载失败')
      }
    },
    onResultPageChange(page) {
      if (!page || page === this.resultPagination.page) return
      this.resultPagination.page = page
      this.loadCurrentResults()
    },
    async loadAppeals() {
      try {
        const res = await api.listAppeals({ page: this.appealPagination.page, pageSize: this.appealPagination.pageSize })
        if (res.code === 0) {
          this.appeals = res.data.list
          this.appealPagination.total = res.data.total
        } else toast.error(res.message || '申诉列表加载失败')
      } catch (e) {
        toast.error((e && e.message) || '申诉列表加载失败')
      }
    },
    onAppealPageChange(page) {
      if (!page || page === this.appealPagination.page) return
      this.appealPagination.page = page
      this.loadAppeals()
    },
    openCreate() { this.form = { batchName: '', termId: '' }; this.formError = ''; this.createVisible = true },
    async submitCreate() {
      if (!this.form.batchName) { this.formError = '批次名称必填'; return }
      if (this.saving) return
      this.saving = true
      try {
        const res = await api.createBatch({ batchName: this.form.batchName, termId: this.form.termId || undefined,
          template: { items: [{ q: '教学态度', type: 'scale5' }, { q: '教学效果', type: 'scale5' }] } })
        if (res.code === 0) {
          toast.success('已创建')
          this.createVisible = false
          this.batchPagination.page = 1
          await this.loadBatches()
        } else this.formError = res.message || '创建失败'
      } catch (e) {
        this.formError = (e && e.message) || '创建失败'
      } finally {
        this.saving = false
      }
    },
    openGenTasks() { this.genTaskIds = []; this.genType = this.typeFilter || 'STUDENT'; this.genVisible = true },
    async submitGen() {
      const ids = this.genTaskIds
      if (!ids.length) { toast.error('请选择教学任务'); return }
      if (this.saving || !this.current) return
      this.saving = true
      try {
        const res = await api.genTasks(this.current.batchId, ids, this.genType)
        if (res.code === 0) {
          toast.success(`已生成 ${res.data.taskCount} 条`)
          this.genVisible = false
          if (this.viewMode === 'byType') await this.selectTyped(this.current)
          else await this.select(this.current)
        } else toast.error(res.message || '生成应评任务失败')
      } catch (e) {
        toast.error((e && e.message) || '生成应评任务失败')
      } finally {
        this.saving = false
      }
    },
    lc(fn, label) {
      if (!this.current || this.confirmSubmitting) return
      const batchId = this.current.batchId
      this.confirmRequireReason = false
      this.confirmReasonLabel = ''
      this.confirmTitle = label
      this.confirmText = `确认${label}`
      this.confirmMessage = `确认对批次「${this.current.batchName}」执行「${label}」？`
      this.pendingAction = async () => {
        const res = await api[fn](batchId)
        if (res.code !== 0) { toast.error(res.message); return false }
        toast.success(label + '成功')
        await this.loadBatches()
        const b = this.rows.find((x) => x.batchId === batchId)
        if (b) await this.select(b)
        else {
          const fresh = await api.getBatch(batchId)
          if (fresh.code === 0) await this.select(fresh.data)
        }
        return true
      }
      this.confirmVisible = true
    },
    approveAppeal(row) {
      if (this.confirmSubmitting) return
      const isCollegeStage = row.status === 'SUBMITTED'
      const stageLabel = isCollegeStage ? '学院初审' : '教务终审'
      this.confirmRequireReason = true
      this.confirmReasonLabel = `${stageLabel}意见（≥5 字）`
      this.confirmTitle = `${stageLabel}通过`
      this.confirmText = `确认${stageLabel}通过`
      this.confirmMessage = `请填写${stageLabel}意见。审核意见将记入审计，后端仍按当前账号数据范围校验本级审核权限。`
      this.pendingAction = async (reason) => {
        const note = String(reason || '').trim()
        const res = await api.reviewAppeal(row.appealId, 'RESOLVE', note)
        if (res.code !== 0) { toast.error(res.message); return false }
        toast.success(`${stageLabel}已通过`)
        await this.loadAppeals()
        return true
      }
      this.confirmVisible = true
    },
    rejectAppeal(id) {
      if (this.confirmSubmitting) return
      this.confirmRequireReason = true
      this.confirmReasonLabel = '驳回原因（≥5 字）'
      this.confirmTitle = '驳回申诉'
      this.confirmText = '确认驳回申诉'
      this.confirmMessage = '请填写驳回原因，将记入审计并通知申诉人。'
      this.pendingAction = async (reason) => {
        const res = await api.reviewAppeal(id, 'REJECT', String(reason || '').trim())
        if (res.code !== 0) { toast.error(res.message); return false }
        toast.success('已驳回')
        await this.loadAppeals()
        return true
      }
      this.confirmVisible = true
    },
    async onConfirm(payload = {}) {
      if (this.confirmSubmitting || !this.pendingAction) return
      const action = this.pendingAction
      this.confirmSubmitting = true
      try {
        const ok = await action(payload && payload.reason)
        if (ok) {
          this.confirmVisible = false
          this.pendingAction = null
          this.confirmRequireReason = false
          this.confirmReasonLabel = ''
        }
      } catch (e) {
        toast.error((e && e.message) || '操作失败')
      } finally {
        this.confirmSubmitting = false
      }
    }
  }
}
</script>

<style scoped>
.aaev-tabs { display: flex; gap: 4px; border-bottom: 1px solid var(--border-color, #e5e7eb); margin-bottom: 16px; }
.aaev-tab { padding: 8px 16px; border: none; background: none; cursor: pointer; font-size: 14px; color: var(--text-secondary, #64748b); border-bottom: 2px solid transparent; }
.aaev-tab.is-active { color: var(--primary-color, #2563eb); border-bottom-color: var(--primary-color, #2563eb); font-weight: 600; }
.aaev-bar { margin-bottom: 12px; }
.aaev-layout { display: grid; grid-template-columns: 280px minmax(0, 1fr); gap: 16px; }
.aaev-list-pane, .aaev-detail { min-width: 0; }
.aaev-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 6px; }
.aaev-list-pane :deep(.app-pagination) { margin-top: 10px; }
.aaev-item { display: flex; justify-content: space-between; align-items: center; gap: 10px; padding: 10px 12px; border: 1px solid var(--border-color, #e5e7eb); border-radius: 8px; cursor: pointer; }
.aaev-item.is-active { border-color: var(--primary-color, #2563eb); background: var(--primary-bg, #eff6ff); }
.aaev-item:focus-visible { outline: 2px solid var(--primary-color, #2563eb); outline-offset: 2px; }
.aaev-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; margin-bottom: 12px; }
.aaev-title { font-size: 16px; font-weight: 600; margin-bottom: 4px; overflow-wrap: anywhere; }
.aaev-actions { display: flex; gap: 8px; flex-wrap: wrap; }
.aaev-section-title { font-weight: 500; margin: 14px 0 8px; }
.aaev-form { display: flex; flex-direction: column; gap: 12px; }
@media (max-width: 900px) {
  .aaev-layout { grid-template-columns: 1fr; }
  .aaev-list-pane { max-height: 300px; overflow: auto; padding: 2px; }
}
@media (max-width: 640px) {
  .aaev-tabs { overflow-x: auto; }
  .aaev-tab { flex: 0 0 auto; white-space: nowrap; }
  .aaev-head { flex-direction: column; }
  .aaev-actions { width: 100%; }
}
</style>
