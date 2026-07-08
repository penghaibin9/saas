<template>
  <ModulePageShell
    title="毕设批次"
    :subtitle="'共 ' + total + ' 个批次 · 一届毕业设计的组织与规则容器'"
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
      <EmptyState v-else-if="!rows.length" title="暂无毕设批次" description="点「＋ 新建批次」创建一届毕业设计批次" />
      <DataTable v-else :columns="columns" :rows="rows" row-key="id" :pagination="{ page, pageSize, total }" @page-change="turnPage">
        <template #cell-batch="{ row }">
          <div class="mp-cell-main">{{ row.batchName }}</div>
          <div class="mp-cell-sub">{{ row.batchNo }} · {{ row.gradeYear || '—' }} · {{ row.academicYear || '—' }}</div>
        </template>
        <template #cell-range="{ row }">
          <AppDateDisplay :value="row.startDate" /> ~ <AppDateDisplay :value="row.endDate" />
        </template>
        <template #cell-status="{ row }"><StatusTag :type="row.statusTone" :label="row.statusLabel" dot /></template>
        <template #cell-actions="{ row }">
          <button class="mp-link" @click="openDetail(row)">详情/配置</button>
          <button v-if="editable(row)" class="mp-link" style="margin-left: var(--space-2)" @click="openEdit(row)">编辑</button>
          <button v-if="row.status === 'DRAFT'" class="mp-link" style="margin-left: var(--space-2)" @click="askState(row, 'activate')">启用</button>
          <button v-else-if="row.status === 'RUNNING'" class="mp-link" style="margin-left: var(--space-2)" @click="askState(row, 'close')">结束</button>
          <button v-else-if="row.status === 'CLOSED'" class="mp-link" style="margin-left: var(--space-2)" @click="askState(row, 'archive')">归档</button>
          <button v-if="row.status === 'DRAFT'" class="mp-link mp-link--danger" style="margin-left: var(--space-2)" @click="askVoid(row)">作废</button>
        </template>
      </DataTable>
    </div>

    <!-- 新建 / 编辑 -->
    <AppDrawer v-model:visible="editVisible" :title="editing ? '编辑批次' : '新建毕设批次'">
      <form class="ie-form" @submit.prevent="submitEdit">
        <label class="ie-fld ie-fld--full"><span class="ie-lbl">批次名称 <i>*</i></span><input v-model.trim="form.batchName" class="ie-in" placeholder="如 2026届毕业设计" /></label>
        <label class="ie-fld"><span class="ie-lbl">批次编号 <i>*</i></span><input v-model.trim="form.batchNo" class="ie-in" :disabled="!!editing" placeholder="租户内唯一" /></label>
        <label class="ie-fld"><span class="ie-lbl">届</span><input v-model.trim="form.gradeYear" class="ie-in" placeholder="如 2026届" /></label>
        <label class="ie-fld"><span class="ie-lbl">学年</span><input v-model.trim="form.academicYear" class="ie-in" placeholder="如 2025-2026" /></label>
        <label class="ie-fld"><span class="ie-lbl">计划人数</span><input v-model.number="form.plannedCount" type="number" min="0" class="ie-in" /></label>
        <AppDatePicker v-model="form.startDate" class="ie-fld" label="开始日期" role="start" :end-value="form.endDate" hint="批次启动日" />
        <AppDatePicker v-model="form.endDate" class="ie-fld" label="结束日期" role="end" :start-value="form.startDate" hint="批次收口日" />
        <label class="ie-fld ie-fld--full"><span class="ie-lbl">适用范围</span><input v-model.trim="form.collegeScope" class="ie-in" placeholder="学院/专业范围，留空=全校" /></label>
        <label class="ie-fld ie-fld--full"><span class="ie-lbl">备注</span><textarea v-model.trim="form.remark" class="ie-in" rows="2" /></label>
        <p v-if="formError" class="ie-err">{{ formError }}</p>
        <div class="ie-actions">
          <button type="button" class="mp-btn" @click="editVisible = false">取消</button>
          <button type="submit" class="mp-btn mp-btn--primary" :disabled="submitting">保存</button>
        </div>
      </form>
    </AppDrawer>

    <!-- 详情 / 阶段+规则配置 -->
    <AppDrawer v-model:visible="detailVisible" :title="detail ? detail.batchName : '批次详情'">
      <template v-if="detail">
        <div class="gb-tabs">
          <button v-for="t in detailTabs" :key="t.key" class="gb-tabs__item" :class="{ 'is-active': dtab === t.key }" @click="dtab = t.key">{{ t.label }}</button>
        </div>

        <div v-show="dtab === 'stages'" class="gb-sec">
          <p class="ie-hint">阶段时间轴（编辑后点「保存阶段」）。{{ configLocked ? '已结束/归档/作废批次不可改。' : '' }}</p>
          <table class="gb-tbl">
            <thead><tr><th>阶段</th><th>开始</th><th>结束</th></tr></thead>
            <tbody>
              <tr v-for="(s, i) in stages" :key="i">
                <td>{{ s.name }}</td>
                <td><AppDatePicker v-model="s.startDate" role="start" :end-value="s.endDate" :disabled="configLocked" /></td>
                <td><AppDatePicker v-model="s.endDate" role="end" :start-value="s.startDate" :disabled="configLocked" /></td>
              </tr>
            </tbody>
          </table>
          <div class="ie-actions"><button class="mp-btn mp-btn--primary" :disabled="configLocked || submitting" @click="saveStages">保存阶段</button></div>
        </div>

        <div v-show="dtab === 'rules'" class="gb-sec">
          <p class="ie-hint">规则配置（查重/答辩/成绩权重）。</p>
          <label class="gb-kv"><span>查重阈值(%)</span><input v-model.number="rules.plagiarism.thresholdPercent" type="number" min="0" max="100" class="ie-in ie-in--sm" :disabled="configLocked" /></label>
          <label class="gb-kv"><span>查重通过才可答辩</span><input v-model="rules.plagiarism.mustPassToDefense" type="checkbox" :disabled="configLocked" /></label>
          <label class="gb-kv"><span>答辩组人数</span><input v-model.number="rules.defense.groupSize" type="number" min="1" class="ie-in ie-in--sm" :disabled="configLocked" /></label>
          <label class="gb-kv"><span>答辩及格分</span><input v-model.number="rules.defense.passScore" type="number" min="0" max="100" class="ie-in ie-in--sm" :disabled="configLocked" /></label>
          <label class="gb-kv"><span>导师权重</span><input v-model.number="rules.score.advisorWeight" type="number" step="0.1" min="0" max="1" class="ie-in ie-in--sm" :disabled="configLocked" /></label>
          <label class="gb-kv"><span>评阅权重</span><input v-model.number="rules.score.reviewerWeight" type="number" step="0.1" min="0" max="1" class="ie-in ie-in--sm" :disabled="configLocked" /></label>
          <label class="gb-kv"><span>答辩权重</span><input v-model.number="rules.score.defenseWeight" type="number" step="0.1" min="0" max="1" class="ie-in ie-in--sm" :disabled="configLocked" /></label>
          <div class="ie-actions"><button class="mp-btn mp-btn--primary" :disabled="configLocked || submitting" @click="saveRules">保存规则</button></div>
        </div>

        <div v-show="dtab === 'audit'" class="gb-sec">
          <EmptyState v-if="!detail.auditTrail.length" title="暂无操作记录" />
          <ul v-else class="gb-trail">
            <li v-for="(a, i) in detail.auditTrail" :key="i" class="gb-trail__item"><span>{{ a.action }}</span><span class="gb-trail__meta">{{ a.operator }} · {{ a.occurredAt }}</span></li>
          </ul>
        </div>
      </template>
    </AppDrawer>

    <AppConfirmDialog
      v-model:visible="confirm.visible" :title="confirm.title" :message="confirm.message"
      :type="confirm.type" :confirm-text="confirm.confirmText" :require-reason="confirm.requireReason"
      :reason-label="confirm.reasonLabel" :submitting="submitting" @confirm="onConfirm"
    />
  </ModulePageShell>
</template>

<script>
/** 毕设批次列表（/admin/graduation/batches）：生产级只走真实后端；建/改/阶段+规则配置/状态机/作废/Excel台账导出。 */
import { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppDrawer } from '@/components/ui'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import { AppDatePicker, AppDateDisplay } from '@/components/common/date'
import { graduationBatchApi } from '@/modules/graduation/api/graduation-batch.api'
import { BATCH_STATUS } from '@/modules/graduation/constants/graduation-batch.constants'
import { toast } from '@/utils/toast'
import { todayDate, formatDate, addDays, validateRange } from '@/utils/dateUtils'

const EMPTY_FILTERS = () => ({ keyword: '', status: '', dateStart: '', dateEnd: '' })
const EMPTY_FORM = () => ({
  batchName: '', batchNo: '', gradeYear: '', academicYear: '', plannedCount: 0,
  startDate: todayDate(),
  endDate: formatDate(addDays(new Date(), 180)),
  collegeScope: '', remark: ''
})
const DEFAULT_RULES = () => ({ plagiarism: { thresholdPercent: 30, mustPassToDefense: true }, defense: { groupSize: 5, passScore: 60 }, score: { advisorWeight: 0.4, reviewerWeight: 0.3, defenseWeight: 0.3 } })

export default {
  name: 'GraduationBatchListView',
  components: {
    ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag, LoadingState, ErrorState, EmptyState,
    AppDrawer, AppConfirmDialog, AppDatePicker, AppDateDisplay
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true, error: '', submitting: false,
      rows: [], total: 0, page: 1, pageSize: 10, filters: EMPTY_FILTERS(),
      editVisible: false, editing: null, form: EMPTY_FORM(), formError: '',
      detailVisible: false, detail: null, dtab: 'stages', preferredTab: 'stages', stages: [], rules: DEFAULT_RULES(),
      detailTabs: [{ key: 'stages', label: '阶段时间轴' }, { key: 'rules', label: '规则配置' }, { key: 'audit', label: '审计' }],
      confirm: { visible: false, title: '', message: '', type: 'primary', confirmText: '确认', requireReason: false, reasonLabel: '原因', action: null, row: null },
      columns: [
        { key: 'batch', title: '批次 / 编号' },
        { key: 'range', title: '起止' },
        { key: 'plannedCount', title: '计划人数' },
        { key: 'status', title: '状态' },
        { key: 'actions', title: '操作', width: '250px' }
      ]
    }
  },
  computed: {
    filterFields() {
      return [
        { key: 'keyword', label: '关键词', type: 'text', placeholder: '批次名称 / 编号 / 届' },
        { key: 'status', label: '状态', type: 'select', options: BATCH_STATUS },
        {
          key: 'date', label: '起止时间', type: 'daterange',
          startKey: 'dateStart', endKey: 'dateEnd',
          memoryKey: 'graduation.batches.dateRange', emptyLabel: '全部时间'
        }
      ]
    },
    toolbarActions() { return [{ key: 'create', label: '＋ 新建批次', variant: 'primary' }, { key: 'export', label: '导出台账' }] },
    configLocked() { return this.detail && ['ARCHIVED', 'VOIDED', 'CLOSED'].includes(this.detail.status) }
  },
  created() { this.applyPanel(this.$route.query.panel, true) },
  watch: {
    '$route.query.panel'(p) { this.applyPanel(p, false) }
  },
  methods: {
    editable(row) { return !['CLOSED', 'ARCHIVED', 'VOIDED'].includes(row.status) },
    /** 按左侧三级菜单的 ?panel= 切换到对应视图/动作（每个 panel 是独立 ref，点击都能导航） */
    applyPanel(panel, initial) {
      panel = panel || 'list'
      if (panel !== 'create') this.editVisible = false
      if (panel === 'create') {
        this.filters.status = ''; this.page = 1; this.load()
        this.editing = null; this.form = EMPTY_FORM(); this.formError = ''; this.editVisible = true
        return
      }
      if (panel === 'export') { this.filters.status = ''; this.page = 1; this.load(); this.doExport(); return }
      if (panel === 'running' || panel === 'archived') {
        this.filters.status = panel === 'running' ? 'RUNNING' : 'ARCHIVED'; this.page = 1; this.load(); return
      }
      if (panel === 'stages' || panel === 'rules') {
        this.preferredTab = panel; this.filters.status = ''; this.page = 1; this.load()
        if (!initial) toast.info(panel === 'stages' ? '点某个批次「详情/配置」即可编辑阶段时间轴' : '点某个批次「详情/配置」即可编辑规则')
        return
      }
      // list（默认）
      this.preferredTab = 'stages'; this.filters.status = ''; this.page = 1; this.load()
    },
    async load() {
      this.loading = true; this.error = ''
      const res = await graduationBatchApi.getBatches({ ...this.filters, page: this.page, pageSize: this.pageSize })
      if (res.code === 0) { this.rows = res.data.list; this.total = res.data.total } else this.error = res.message
      this.loading = false
    },
    search() { this.page = 1; this.load() },
    reset() { this.filters = EMPTY_FILTERS(); this.page = 1; this.load() },
    turnPage(p) { this.page = p; this.load() },
    onToolbar(key) {
      if (key === 'create') { this.editing = null; this.form = EMPTY_FORM(); this.formError = ''; this.editVisible = true }
      if (key === 'export') this.doExport()
    },
    openEdit(row) {
      this.editing = row
      this.form = { batchName: row.batchName, batchNo: row.batchNo, gradeYear: row.gradeYear, academicYear: row.academicYear, plannedCount: row.plannedCount, startDate: (row.startDate || '').slice(0, 10), endDate: (row.endDate || '').slice(0, 10), collegeScope: row.collegeScope, remark: row.remark }
      this.formError = ''; this.editVisible = true
    },
    async submitEdit() {
      this.formError = ''
      if (!this.form.batchName || !this.form.batchNo) { this.formError = '批次名称与编号必填'; return }
      const range = validateRange(this.form.startDate, this.form.endDate)
      if (!range.ok) { this.formError = range.message; return }
      this.submitting = true
      try {
        const res = this.editing ? await graduationBatchApi.updateBatch(this.editing.id, this.form) : await graduationBatchApi.createBatch(this.form)
        if (res.code === 0) { toast.success('已保存'); this.editVisible = false; this.load() } else this.formError = res.message
      } finally { this.submitting = false }
    },
    async openDetail(row) {
      const res = await graduationBatchApi.getBatchDetail(row.id)
      if (res.code !== 0) return toast.error(res.message)
      this.detail = res.data
      this.stages = JSON.parse(JSON.stringify(res.data.stages || []))
      this.rules = { ...DEFAULT_RULES(), ...(res.data.rules || {}), plagiarism: { ...DEFAULT_RULES().plagiarism, ...(res.data.rules?.plagiarism || {}) }, defense: { ...DEFAULT_RULES().defense, ...(res.data.rules?.defense || {}) }, score: { ...DEFAULT_RULES().score, ...(res.data.rules?.score || {}) } }
      this.dtab = this.preferredTab || 'stages'; this.detailVisible = true
    },
    async saveStages() {
      this.submitting = true
      try {
        const res = await graduationBatchApi.setStages(this.detail.id, this.stages)
        if (res.code === 0) { toast.success('阶段已保存'); this.detail = res.data } else toast.error(res.message)
      } finally { this.submitting = false }
    },
    async saveRules() {
      this.submitting = true
      try {
        const res = await graduationBatchApi.setRules(this.detail.id, this.rules)
        if (res.code === 0) { toast.success('规则已保存'); this.detail = res.data } else toast.error(res.message)
      } finally { this.submitting = false }
    },
    askState(row, action) {
      const m = { activate: { t: '启用批次', c: '确认启用', type: 'primary' }, close: { t: '结束批次', c: '确认结束', type: 'warning' }, archive: { t: '归档批次', c: '确认归档', type: 'primary' } }[action]
      this.confirm = { visible: true, title: m.t, message: `确认对「${row.batchName}」执行「${m.t}」？`, type: m.type, confirmText: m.c, requireReason: false, action, row }
    },
    askVoid(row) {
      this.confirm = { visible: true, title: '作废批次', message: `确认作废「${row.batchName}」？（仅草稿可作废，不可恢复）`, type: 'danger', confirmText: '确认作废', requireReason: true, reasonLabel: '作废原因', action: 'void', row }
    },
    async onConfirm({ reason } = {}) {
      const { action, row } = this.confirm
      this.submitting = true
      try {
        let res
        if (action === 'activate') res = await graduationBatchApi.activateBatch(row.id)
        else if (action === 'close') res = await graduationBatchApi.closeBatch(row.id)
        else if (action === 'archive') res = await graduationBatchApi.archiveBatch(row.id)
        else if (action === 'void') res = await graduationBatchApi.voidBatch(row.id, reason || '')
        if (res && res.code === 0) { toast.success('已更新'); this.confirm.visible = false; this.load() } else if (res) toast.error(res.message)
      } finally { this.submitting = false }
    },
    async doExport() {
      const res = await graduationBatchApi.downloadBatchExport({ ...this.filters })
      if (res.code === 0) toast.success(`已导出 ${res.data.rowCount} 个批次台账`)
      else toast.error(res.message)
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.mp-link--danger { color: var(--danger, #dc2626); }
.ie-form { display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-3); padding: var(--space-1) 0; }
.ie-fld { display: flex; flex-direction: column; gap: 4px; }
.ie-fld--full { grid-column: 1 / -1; }
.ie-lbl { font-size: 12px; color: var(--t2, #475569); }
.ie-lbl i { color: var(--danger, #dc2626); font-style: normal; }
.ie-in { width: 100%; padding: 7px 10px; border: 1px solid var(--line, #d9dee8); border-radius: 8px; font-size: 13px; box-sizing: border-box; }
.ie-in--sm { padding: 5px 8px; }
.ie-err { grid-column: 1 / -1; color: var(--danger, #dc2626); font-size: 12px; margin: 0; }
.ie-hint { font-size: 12px; color: var(--t3, #64748b); margin: 0 0 8px; }
.ie-actions { display: flex; justify-content: flex-end; gap: var(--space-2); margin-top: var(--space-3); }
.mp-btn { padding: 7px 16px; border: 1px solid var(--line, #d9dee8); border-radius: 8px; background: #fff; cursor: pointer; font-size: 13px; }
.mp-btn--primary { background: var(--pri, #2563eb); color: #fff; border-color: var(--pri, #2563eb); }
.mp-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.gb-tabs { display: flex; gap: var(--space-1); border-bottom: 1px solid var(--line, #e2e8f0); margin-bottom: var(--space-3); }
.gb-tabs__item { padding: 8px 12px; border: none; background: none; cursor: pointer; font-size: 13px; color: var(--t2, #475569); border-bottom: 2px solid transparent; }
.gb-tabs__item.is-active { color: var(--pri, #2563eb); border-bottom-color: var(--pri, #2563eb); font-weight: 600; }
.gb-sec { font-size: 13px; }
.gb-tbl { width: 100%; border-collapse: collapse; font-size: 13px; }
.gb-tbl th, .gb-tbl td { text-align: left; padding: 6px 8px; border-bottom: 1px solid var(--line, #eef1f6); }
.gb-tbl th { color: var(--t3, #64748b); font-weight: 500; font-size: 12px; }
.gb-kv { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); padding: 6px 0; border-bottom: 1px dashed var(--line, #eef1f6); }
.gb-kv > span { color: var(--t2, #475569); }
.gb-kv .ie-in--sm { width: 120px; flex: none; }
.gb-trail__item { display: flex; justify-content: space-between; padding: 7px 0; border-bottom: 1px dashed var(--line, #eef1f6); }
.gb-trail__meta { color: var(--t3, #64748b); font-size: 12px; }
</style>
