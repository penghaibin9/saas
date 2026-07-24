<template>
  <ModulePageShell
    title="选题轮次"
    :subtitle="pageSubtitle"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <div class="gd-actions">
        <ModuleToolbar :actions="toolbarActions" @action="onToolbar" />
        <AppExportButton v-if="exportVisible" :export-fn="exportRoundsFn">导出 Excel</AppExportButton>
      </div>
    </template>

    <div v-if="activePanel !== 'conflicts'" class="mp-stack">
      <AdvancedFilter v-if="activePanel === 'rounds' && hasBatch" v-model="filters" :fields="filterFields" @search="search" @reset="reset" />
      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" :title="emptyTitle" :description="emptyDesc" />

      <!-- 轮次列表 -->
      <DataTable
        v-else-if="activePanel === 'rounds'"
        :columns="roundColumns"
        :rows="rows"
        row-key="id"
        :pagination="{ page, pageSize, total }"
        @page-change="turnPage"
      >
        <template #cell-name="{ row }">
          <div class="mp-cell-main">{{ row.roundName }}</div>
          <div class="mp-cell-sub">第 {{ row.roundNo }} 轮 · 最多 {{ row.maxChoices }} 志愿</div>
        </template>
        <template #cell-batch="{ row }">{{ row.batchName || '—' }}</template>
        <template #cell-range="{ row }">
          <AppDateDisplay :value="row.startAt" mode="datetime" /> ~ <AppDateDisplay :value="row.endAt" mode="datetime" />
        </template>
        <template #cell-status="{ row }">
          <StatusTag :type="row.statusTone" :label="row.statusLabel" dot />
        </template>
        <template #cell-actions="{ row }">
          <button class="mp-link" @click="viewChoices(row)">志愿</button>
          <button v-if="row.status === 'DRAFT' || row.status === 'CLOSED'" class="mp-link" style="margin-left: var(--space-2)" @click="askOpen(row)">开启</button>
          <button v-if="row.status === 'OPEN'" class="mp-link" style="margin-left: var(--space-2)" @click="askClose(row)">关闭</button>
          <button v-if="row.status === 'OPEN' || row.status === 'CLOSED'" class="mp-link" style="margin-left: var(--space-2)" @click="askMatch(row)">匹配</button>
          <button v-if="row.status === 'CLOSED' || row.status === 'MATCHED'" class="mp-link" style="margin-left: var(--space-2)" @click="askArchive(row)">归档</button>
        </template>
      </DataTable>

      <!-- 志愿/匹配结果 -->
      <DataTable
        v-else
        :columns="choiceColumns"
        :rows="rows"
        row-key="id"
        :pagination="{ page: 1, pageSize: 100, total: rows.length }"
      >
        <template #cell-student="{ row }">
          <div class="mp-cell-main">{{ row.studentName }}</div>
          <div class="mp-cell-sub">{{ row.studentNo }}</div>
        </template>
        <template #cell-topic="{ row }">
          <div class="mp-cell-main">{{ row.topicTitle }}</div>
          <div class="mp-cell-sub">{{ row.advisorName || '—' }}</div>
        </template>
        <template #cell-order="{ row }">第 {{ row.choiceOrder }} 志愿</template>
        <template #cell-status="{ row }">
          <StatusTag :type="choiceTone(row.status)" :label="row.statusLabel" />
        </template>
        <template #cell-actions="{ row }">
          <template v-if="row.status === 'PENDING'">
            <button class="mp-link" @click="askConfirmChoice(row)">确认</button>
            <button class="mp-link mp-link--danger" style="margin-left: var(--space-2)" @click="askRejectChoice(row)">驳回</button>
            <button class="mp-link" style="margin-left: var(--space-2)" @click="askWithdraw(row)">退选</button>
          </template>
          <span v-else class="mp-cell-sub">—</span>
        </template>
      </DataTable>
    </div>

    <!-- 容量冲突人工复核 + 选题统计（Batch 3） -->
    <div v-if="activePanel === 'conflicts'" class="mp-stack">
      <section v-if="stats" class="mp-card">
        <div class="mp-card__head"><span class="mp-card__title">{{ selectedRoundName || '当前轮次' }} · 选题统计</span></div>
        <div class="mp-card__body trc-stats">
          <div class="trc-stat"><b>{{ stats.totalChoices }}</b><span>志愿总数</span></div>
          <div class="trc-stat"><b>{{ stats.studentCount }}</b><span>参与学生</span></div>
          <div class="trc-stat"><b>{{ stats.confirmedCount }}</b><span>已确认/匹配</span></div>
          <div class="trc-stat"><b :style="stats.conflictTopicCount ? 'color:var(--danger-600)' : ''">{{ stats.conflictTopicCount }}</b><span>过热题目</span></div>
          <div v-for="s in stats.byStatus" :key="s.status" class="trc-stat trc-stat--sm"><b>{{ s.count }}</b><span>{{ s.label }}</span></div>
        </div>
      </section>

      <LoadingState v-if="loading" />
      <EmptyState v-else-if="!conflicts.length" title="暂无容量冲突" description="没有志愿数超过剩余容量的题目，无需人工复核" />
      <section v-else v-for="c in conflicts" :key="c.topicId" class="mp-card">
        <div class="mp-card__head">
          <span class="mp-card__title">{{ c.title }}</span>
          <StatusTag type="danger" :label="`报 ${c.pendingCount} / 余 ${c.remaining}（超 ${c.overBy}）`" />
        </div>
        <div class="mp-card__body">
          <div v-for="s in c.students" :key="s.choiceId" class="trc-row">
            <div>
              <div class="mp-cell-main">第{{ s.choiceOrder }}志愿 · {{ s.studentName }}</div>
              <div class="mp-cell-sub">{{ s.className }} · 导师 {{ s.advisorName || '—' }}</div>
            </div>
            <div>
              <button class="mp-link" @click="askConfirmChoice({ id: s.choiceId, studentName: s.studentName, topicTitle: c.title })">确认</button>
              <button class="mp-link mp-link--danger" style="margin-left: var(--space-2)" @click="askRejectChoice({ id: s.choiceId, studentName: s.studentName, topicTitle: c.title })">驳回</button>
            </div>
          </div>
        </div>
      </section>
    </div>

    <AppConfirmDialog
      v-model:visible="confirm.visible"
      :title="confirm.title"
      :message="confirm.message"
      :type="confirm.type"
      :confirm-text="confirm.confirmText"
      :require-reason="confirm.requireReason"
      :reason-label="confirm.reasonLabel"
      :reason-chips="confirm.reasonChips || []"
      :submitting="submitting"
      @confirm="onConfirm"
    />

    <AppExcelImportDrawer
      v-model:visible="importVisible"
      title="导入选题志愿"
      template-name="选题志愿导入模板.xlsx"
      :required-fields="['studentNo', 'choiceOrder']"
      :preview-fields="['studentNo', 'topicNo', 'topicTitle', 'choiceOrder']"
      :download-template-fn="() => gdTopicRoundApi.downloadChoiceImportTemplate(selectedRoundId)"
      :upload-fn="(file) => gdTopicRoundApi.uploadChoiceImportXlsx(selectedRoundId, file)"
      :confirm-fn="({ rows }) => gdTopicRoundApi.importChoiceConfirm(selectedRoundId, rows)"
      :download-errors-fn="({ rows, errors }) => gdTopicRoundApi.downloadChoiceImportErrors(selectedRoundId, rows, errors)"
      @imported="onImported"
    />
  </ModulePageShell>
</template>

<script>
/** 选题轮次（/admin/graduation/topic-rounds）：轮次管理 + 志愿查看 + 贪心匹配 */
import { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import { AppExportButton } from '@/components/common'
import { AppExcelImportDrawer } from '@/components/common/excel'
import { AppDateDisplay } from '@/components/common/date'
import { gdTopicRoundApi } from '@/modules/graduation/api/graduation-topic-round.api'
import { GD_ROUND_STATUS } from '@/modules/graduation/constants/graduation-topic-round.constants'
import { useGraduationBatchStore } from '@/stores/graduationBatch'
import { toast } from '@/utils/toast'

const EMPTY_FILTERS = () => ({ status: '', dateStart: '', dateEnd: '' })

const REJECT_CHOICE_REASON_CHIPS = [
  '题目范围过大，请缩小研究范围',
  '题目已有学生选定，请更换题目',
  '研究方向与本专业培养目标不符',
  '题目缺乏研究价值或创新性，请与教师协商重选',
  '与企业合作课题相关，需先获得企业授权'
]

const PANEL_PRESETS = {
  rounds: () => EMPTY_FILTERS(),
  choices: () => ({}),
  match: () => ({ status: 'MATCHED' }),
  conflicts: () => ({})
}


export default {
  name: 'TopicRoundListView',
  components: { 
    ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag, LoadingState, ErrorState, EmptyState,
    AppConfirmDialog, AppExcelImportDrawer, AppDateDisplay, AppExportButton
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      batchStore: useGraduationBatchStore(),
      loading: true, error: '', submitting: false, activePanel: 'rounds',
      rows: [], total: 0, page: 1, pageSize: 10, filters: EMPTY_FILTERS(),
      selectedRoundId: '', selectedRoundName: '',
      importVisible: false, conflicts: [], stats: null,
      confirm: { visible: false, title: '', message: '', type: 'primary', confirmText: '确认', action: null, row: null }
    }
  },
  computed: {
    hasBatch() {
      return !!this.batchStore.selectedBatchId
    },
    roundColumns() {
      return [
        { key: 'name', title: '轮次' },
        { key: 'batch', title: '批次' },
        { key: 'range', title: '时间' },
        { key: 'status', title: '状态' },
        { key: 'actions', title: '操作', width: '220px' }
      ]
    },
    choiceColumns() {
      const cols = [
        { key: 'student', title: '学生' },
        { key: 'topic', title: '志愿课题' },
        { key: 'order', title: '志愿序' },
        { key: 'status', title: '状态' }
      ]
      if (this.activePanel === 'choices') cols.push({ key: 'actions', title: '操作', width: '140px' })
      return cols
    },
    filterFields() {
      return [
        { key: 'status', label: '状态', type: 'select', options: GD_ROUND_STATUS }
      ]
    },
    toolbarActions() {
      if (this.activePanel === 'rounds') {
        return [{ key: 'create', label: '＋ 新建轮次', variant: 'primary', disabled: !this.hasBatch || this.ctx.writeEnabled === false }]
      }
      const actions = [{ key: 'back', label: '返回轮次列表' }]
      if (this.activePanel === 'conflicts') return actions
      if (this.selectedRoundId) {
        actions.push({ key: 'conflicts', label: '容量冲突复核' }, { key: 'import', label: '导入 Excel', disabled: this.ctx.writeEnabled === false })
      }
      return actions
    },
    exportVisible() {
      return this.hasBatch && (this.activePanel === 'rounds' || !!this.selectedRoundId)
    },
    pageSubtitle() {
      const batch = this.batchStore.selectedBatchName ? `${this.batchStore.selectedBatchName} · ` : ''
      if (!this.hasBatch) return '请先在顶部选择或创建毕设批次'
      if (this.activePanel === 'rounds') return `${batch}共 ${this.total} 个轮次 · 开启后学生可填志愿，关闭后执行匹配`
      if (this.activePanel === 'conflicts') return `${batch}${this.selectedRoundName || '轮次'} · 容量冲突人工复核 + 选题统计`
      return `${batch}${this.selectedRoundName || '轮次'} · ${this.rows.length} 条志愿记录`
    },
    emptyTitle() {
      if (!this.hasBatch) return '请先选择或创建毕设批次'
      return this.activePanel === 'rounds' ? '暂无选题轮次' : '暂无志愿记录'
    },
    emptyDesc() {
      if (!this.hasBatch) return '顶部批次条选择当前工作批次后，再管理选题轮次。'
      return this.activePanel === 'rounds' ? '点「新建轮次」创建一轮选题互选' : '学生提交志愿后将在此展示'
    }
  },
  watch: {
    '$route.query.panel': {
      immediate: true,
      handler(panel) {
        const key = PANEL_PRESETS[panel] ? panel : 'rounds'
        this.activePanel = key
        if (key === 'rounds') this.filters = PANEL_PRESETS.rounds()
        this.page = 1
        this.load()
      }
    },
    'batchStore.selectedBatchId'() {
      this.page = 1
      this.selectedRoundId = ''
      this.load()
    }
  },
  methods: {
    choiceTone(s) {
      return s === 'MATCHED' ? 'success' : (s === 'UNMATCHED' ? 'danger' : 'warning')
    },
    async load() {
      if (!this.batchStore.selectedBatchId) {
        this.loading = false
        this.error = ''
        this.rows = []
        this.total = 0
        this.conflicts = []
        this.stats = null
        return
      }
      this.loading = true
      this.error = ''
      if (this.activePanel === 'rounds') {
        const r = await gdTopicRoundApi.getRounds({
          page: this.page, pageSize: this.pageSize,
          batchId: this.batchStore.selectedBatchId || undefined,
          status: this.filters.status || undefined
        })
        this.loading = false
        if (r.code !== 0) { this.error = r.message; return }
        this.rows = r.data.list
        this.total = r.data.total
        return
      }
      if (this.activePanel === 'conflicts') {
        if (!this.selectedRoundId) {
          const rr = await gdTopicRoundApi.getRounds({ page: 1, pageSize: 1, batchId: this.batchStore.selectedBatchId })
          if (rr.code === 0 && rr.data.list.length) {
            this.selectedRoundId = rr.data.list[0].id
            this.selectedRoundName = rr.data.list[0].roundName
          } else { this.loading = false; this.conflicts = []; this.stats = null; return }
        }
        const [cf, st] = await Promise.all([
          gdTopicRoundApi.getCapacityConflicts(this.selectedRoundId),
          gdTopicRoundApi.getRoundStats(this.selectedRoundId)
        ])
        this.loading = false
        this.conflicts = cf.code === 0 ? cf.data.list : []
        this.stats = st.code === 0 ? st.data : null
        return
      }
      if ((this.activePanel === 'match' || this.activePanel === 'choices') && !this.selectedRoundId) {
        const status = this.activePanel === 'match' ? 'MATCHED' : undefined
        const rr = await gdTopicRoundApi.getRounds({ status, page: 1, pageSize: 1, batchId: this.batchStore.selectedBatchId })
        if (rr.code === 0 && rr.data.list.length) {
          this.selectedRoundId = rr.data.list[0].id
          this.selectedRoundName = rr.data.list[0].roundName
        } else {
          this.loading = false
          this.rows = []
          return
        }
      }
      if (!this.selectedRoundId) {
        this.loading = false
        this.rows = []
        return
      }
      const r = await gdTopicRoundApi.getChoices(this.selectedRoundId)
      this.loading = false
      if (r.code !== 0) { this.error = r.message; return }
      let list = r.data || []
      if (this.activePanel === 'match') {
        list = list.filter((x) => x.status === 'MATCHED' || x.status === 'UNMATCHED')
      }
      this.rows = list
      this.total = list.length
    },
    search() { this.page = 1; this.load() },
    reset() { this.filters = EMPTY_FILTERS(); this.page = 1; this.load() },
    turnPage({ page }) { this.page = page; this.load() },
    onToolbar(key) {
      if (key === 'create') this.$router.push('/admin/graduation/topic-rounds/create')
      if (key === 'import') {
        if (!this.selectedRoundId) { toast.error('请先选择轮次'); return }
        this.importVisible = true
      }
      if (key === 'conflicts') {
        this.activePanel = 'conflicts'
        this.$router.replace('/admin/graduation/topic-rounds?panel=conflicts')
        this.load()
      }
      if (key === 'back') {
        this.activePanel = 'rounds'
        this.selectedRoundId = ''
        this.$router.replace('/admin/graduation/topic-rounds?panel=rounds')
        this.load()
      }
    },
    askArchive(row) {
      this.confirm = { visible: true, title: '归档轮次', message: `归档「${row.roundName}」？归档后不再出现在进行中列表。`, type: 'warning', confirmText: '归档', action: 'archive', row }
    },
    askWithdraw(row) {
      this.confirm = { visible: true, title: '退选', message: `撤回「${row.studentName}」在本轮的全部待处理志愿？之后该生可重新填报。`, type: 'danger', confirmText: '退选', action: 'withdraw', row }
    },
    viewChoices(row) {
      this.selectedRoundId = row.id
      this.selectedRoundName = row.roundName
      this.activePanel = 'choices'
      this.$router.replace('/admin/graduation/topic-rounds?panel=choices')
      this.load()
    },
    askOpen(row) {
      this.confirm = { visible: true, title: '开启轮次', message: `确认开启「${row.roundName}」？开启后学生可提交志愿。`, type: 'primary', confirmText: '开启', action: 'open', row }
    },
    askClose(row) {
      this.confirm = { visible: true, title: '关闭轮次', message: `关闭后不再接受新志愿，可执行匹配。`, type: 'warning', confirmText: '关闭', action: 'close', row }
    },
    askMatch(row) {
      this.confirm = { visible: true, title: '执行匹配', message: `按志愿序贪心匹配并写入毕设学生选题，不可撤销。`, type: 'primary', confirmText: '匹配', action: 'match', row }
    },
    askConfirmChoice(row) {
      this.confirm = { visible: true, title: '确认志愿', message: `确认「${row.studentName}」录入「${row.topicTitle}」？将自动关闭该生本轮其余待处理志愿。`, type: 'primary', confirmText: '确认', requireReason: false, action: 'confirmChoice', row }
    },
    askRejectChoice(row) {
      this.confirm = {
        visible: true, title: '驳回志愿', message: `驳回「${row.studentName}」对「${row.topicTitle}」的志愿？`,
        type: 'danger', confirmText: '驳回', requireReason: true, reasonLabel: '驳回理由',
        reasonChips: REJECT_CHOICE_REASON_CHIPS, action: 'rejectChoice', row
      }
    },
    async onConfirm({ reason } = {}) {
      const row = this.confirm.row
      this.submitting = true
      let r = { code: 1 }
      if (this.confirm.action === 'open') r = await gdTopicRoundApi.openRound(row.id)
      if (this.confirm.action === 'close') r = await gdTopicRoundApi.closeRound(row.id)
      if (this.confirm.action === 'match') r = await gdTopicRoundApi.matchRound(row.id)
      if (this.confirm.action === 'confirmChoice') r = await gdTopicRoundApi.confirmChoice(row.id)
      if (this.confirm.action === 'rejectChoice') r = await gdTopicRoundApi.rejectChoice(row.id, reason || '')
      if (this.confirm.action === 'archive') r = await gdTopicRoundApi.archiveRound(row.id)
      if (this.confirm.action === 'withdraw') r = await gdTopicRoundApi.withdrawChoices(this.selectedRoundId, row.gdStudentId)
      this.submitting = false
      if (r.code !== 0) { toast.error(r.message); return }
      toast.success(this.confirm.action === 'match' ? `已匹配 ${r.data?.matched ?? 0} 人` : '操作成功')
      this.confirm.visible = false
      this.load()
    },
    onImported() {
      this.importVisible = false
      toast.success('志愿导入完成')
      this.load()
    },
    exportRoundsFn() {
      if (this.activePanel === 'rounds') {
        return gdTopicRoundApi.exportRounds({
          batchId: this.batchStore.selectedBatchId || undefined,
          status: this.filters.status || undefined
        })
      }
      if (!this.selectedRoundId) {
        return Promise.resolve({ code: 1, message: '请先选择轮次' })
      }
      return gdTopicRoundApi.exportChoices(this.selectedRoundId, {
        matchedOnly: this.activePanel === 'match'
      })
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.gd-actions { display: flex; align-items: center; gap: var(--space-2); flex-wrap: wrap; }
.trc-stats { display: flex; flex-wrap: wrap; gap: var(--space-4); }
.trc-stat { display: flex; flex-direction: column; min-width: 84px; }
.trc-stat b { font-size: var(--font-size-xl); font-weight: var(--font-weight-semibold); color: var(--text-primary); }
.trc-stat span { font-size: var(--font-size-xs); color: var(--text-tertiary); }
.trc-stat--sm b { font-size: var(--font-size-lg); color: var(--text-secondary); }
.trc-row { display: flex; align-items: center; justify-content: space-between; padding: var(--space-2) 0; border-bottom: 1px solid var(--border-light); }
.trc-row:last-child { border-bottom: none; }
</style>
