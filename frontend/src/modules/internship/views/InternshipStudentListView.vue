<template>
  <ModulePageShell
    title="学生实习管理"
    :subtitle="pageSubtitle"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppExportButton :export-fn="exportFn" @exported="onExported">⬇ 导出 Excel</AppExportButton>
      <ModuleToolbar :actions="toolbarActions" @action="onToolbar" />
    </template>

    <div class="mp-stack">
      <ModuleSummaryStrip :metrics="summaryMetrics" :note="summaryMetrics.length ? '' : '暂无统计口径'" />
      <nav class="isl-viewnav" aria-label="实习学生视图">
        <span class="isl-viewnav__title">学生台账</span>
        <button
          v-for="view in viewModes"
          :key="view.key"
          type="button"
          class="isl-viewnav__item"
          :class="{ 'is-active': activePanel === view.key }"
          @click="goPanel(view.key)"
        >{{ view.label }}</button>
      </nav>
      <AdvancedFilter v-model="filters" :fields="filterFields" @search="search" @reset="reset" />
      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" title="暂无实习学生" description="可「＋ 建档」或「导入」录入实习学生（岗位在详情里从岗位库分配）" />
      <DataTable v-else :columns="columns" :rows="rows" row-key="id" :pagination="{ page, pageSize, total }" @page-change="turnPage">
        <template #cell-student="{ row }">
          <div class="mp-cell-main">{{ row.name }}</div>
          <div class="mp-cell-sub"><AppSensitiveText :value="row.studentNo" /> · {{ row.className }}</div>
        </template>
        <template #cell-placement="{ row }">
          <template v-if="row.positionId">
            <div class="mp-cell-main">{{ row.enterpriseName }}</div>
            <div class="mp-cell-sub">{{ row.positionName }}<span v-if="row.mentorName"> · 导师 {{ row.mentorName }}</span></div>
          </template>
          <span v-else class="mp-note">未分配岗位</span>
        </template>
        <template #cell-eligibility="{ row }">
          <AppStatusTag :type="eligTone(row.eligibilityStatus)">{{ row.eligibilityLabel }}</AppStatusTag>
        </template>
        <template #cell-destination="{ row }">{{ row.destinationLabel }}</template>
        <template #cell-status="{ row }">
          <AppStatusTag :type="row.statusTone" dot>{{ row.statusLabel }}</AppStatusTag>
        </template>
        <template #cell-actions="{ row }">
          <TableActionColumn :actions="rowActions(row)" @action="(key) => onRowAction(key, row)" />
        </template>
      </DataTable>
    </div>

    <!-- 建档 -->
    <AppDrawer v-model:visible="createVisible" title="实习学生建档">
      <form class="ie-form" @submit.prevent="submitCreate">
        <!-- 注意：Picker 不能包在 <label> 里，label 激活会把点击转发给选择器内部按钮（清空/搜索） -->
        <div class="ie-fld ie-fld--full"><span class="ie-lbl">学生 <i>*</i></span>
          <AppInternshipCandidateStudentPicker
            v-model="cform.studentId"
            placeholder="输入姓名或学号搜索学生"
            search-placeholder="按姓名 / 学号搜索"
            data-scope-hint="仅显示你数据范围内的学生 · 已建档学生提交时由后端拦截重复"
          />
        </div>
        <div class="ie-fld"><span class="ie-lbl">校内指导教师</span><AppInternshipAdvisorPicker v-model="cform.advisorUserId" clearable placeholder="暂不分配" /></div>
        <label class="ie-fld ie-fld--full"><span class="ie-lbl">备注</span><textarea v-model.trim="cform.remark" class="ie-in" rows="2" /></label>
        <p v-if="cError" class="ie-err">{{ cError }}</p>
        <div class="ie-actions">
          <button type="button" class="mp-btn" @click="createVisible = false">取消</button>
          <button type="submit" class="mp-btn mp-btn--primary" :disabled="submitting">建档</button>
        </div>
      </form>
    </AppDrawer>

    <!-- 分配岗位（从岗位库选已上架岗位） -->
    <AppDrawer v-model:visible="assignVisible" :title="assignRow ? `分配岗位 · ${assignRow.name}` : '分配岗位'">
      <div class="ie-form">
        <p class="ie-hint">仅「已上架」且企业非黑名单、未满员的岗位可选（来自岗位库真实数据）。</p>
        <div class="ie-fld ie-fld--full"><span class="ie-lbl">岗位 <i>*</i></span>
          <AppInternshipPositionPicker
            v-model="assignPositionId"
            placeholder="输入岗位或企业名称搜索"
            search-placeholder="按岗位名称 / 企业搜索"
            data-scope-hint="仅已上架、未满员岗位可选"
          />
        </div>
        <p v-if="assignError" class="ie-err">{{ assignError }}</p>
        <div class="ie-actions">
          <button type="button" class="mp-btn" @click="assignVisible = false">取消</button>
          <button type="button" class="mp-btn mp-btn--primary" :disabled="submitting || !assignPositionId" @click="submitAssign">确认分配</button>
        </div>
      </div>
    </AppDrawer>

    <AppDrawer v-model:visible="advisorVisible" :title="advisorRow ? `分配指导老师 · ${advisorRow.name}` : '分配指导老师'">
      <div class="ie-form">
        <p class="ie-hint">选择当前租户内启用的教职工账号。变更会写入学生实习档案和审计留痕。</p>
        <div class="ie-fld ie-fld--full"><span class="ie-lbl">校内指导教师 <i>*</i></span><AppInternshipAdvisorPicker v-model="advisorAssignmentUserId" /></div>
        <label class="ie-fld ie-fld--full"><span class="ie-lbl">分配说明</span><textarea v-model.trim="advisorAssignmentReason" class="ie-in" rows="2" placeholder="例如：按专业方向调整指导关系" /></label>
        <p v-if="advisorError" class="ie-err">{{ advisorError }}</p>
        <div class="ie-actions">
          <button type="button" class="mp-btn" @click="advisorVisible = false">取消</button>
          <button type="button" class="mp-btn mp-btn--primary" :disabled="submitting || !advisorAssignmentUserId" @click="submitAssignAdvisor">确认分配</button>
        </div>
      </div>
    </AppDrawer>

    <!-- Excel 导入（P0-E 正式 xlsx） -->
    <AppExcelImportDrawer
      v-model:visible="importVisible"
      title="导入实习学生"
      show-account-boundary
      template-name="实习学生导入模板.xlsx"
      :required-fields="['学号']"
      :preview-fields="['studentNo', 'advisorName', 'enterpriseName', 'batchName']"
      :download-template-fn="() => internStudentApi.downloadImportTemplate()"
      :upload-fn="(file) => internStudentApi.uploadImportXlsx(file)"
      :confirm-fn="({ rows }) => internStudentApi.importConfirmRows(rows)"
      :download-errors-fn="({ rows, errors }) => internStudentApi.downloadImportErrors(rows, errors)"
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
/** 实习学生列表（/admin/internship/students）：生产级只走真实后端；建档/分配岗位(岗位库)/资格/状态/导入导出。 */
import { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppDrawer } from '@/components/ui'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import { AppSensitiveText, AppStatusTag, AppExportButton, AppInternshipCandidateStudentPicker, AppInternshipPositionPicker, AppInternshipAdvisorPicker } from '@/components/common'
import { AppExcelImportDrawer } from '@/components/common/excel'
import { TableActionColumn } from '@/modules/internship/components'
import ModuleSummaryStrip from './components/ModuleSummaryStrip.vue'
import { internStudentApi } from '@/modules/internship/api/internship-student.api'
import { STUDENT_STATUS, ELIGIBILITY_STATUS, DESTINATION_TYPE } from '@/modules/internship/constants/internship-student.constants'
import { canCode } from '@/modules/internship/composables/permission'
import { toast } from '@/utils/toast'

const EMPTY_FILTERS = () => ({ keyword: '', status: '', eligibility: '', destination: '', hasPosition: '' })

const PANEL_PRESETS = {
  roster: () => EMPTY_FILTERS(),
  eligibility: () => ({ ...EMPTY_FILTERS(), eligibility: 'PENDING' }),
  status: () => ({ ...EMPTY_FILTERS(), status: 'ONBOARD' }),
  destination: () => ({ ...EMPTY_FILTERS(), destination: 'NONE' }),
  position: () => ({ ...EMPTY_FILTERS(), hasPosition: 'false' }),
  enterprise: () => ({ ...EMPTY_FILTERS(), hasPosition: 'true' }),
  mentor: () => ({ ...EMPTY_FILTERS(), hasPosition: 'true' })
}

const PANEL_HINTS = {
  roster: '建档、导入、导出全量名单',
  eligibility: '筛选待认定资格学生，可在行内「认定资格」',
  status: '按实习状态筛选（默认在岗中，可改筛选条件）',
  destination: '筛选未落实去向学生',
  position: '筛选未分配岗位学生，可「分配岗位 / 调岗」',
  enterprise: '筛选已分配企业/岗位学生',
  mentor: '筛选已分配岗位（含企业导师）学生'
}

export default {
  name: 'InternshipStudentListView',
  components: { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, LoadingState, ErrorState, EmptyState,
    AppDrawer, AppConfirmDialog, AppSensitiveText, AppStatusTag, AppExportButton, AppExcelImportDrawer, TableActionColumn, ModuleSummaryStrip,
    AppInternshipCandidateStudentPicker, AppInternshipPositionPicker, AppInternshipAdvisorPicker },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true, error: '', submitting: false, activePanel: 'roster',
      rows: [], total: 0, page: 1, pageSize: 10, filters: EMPTY_FILTERS(),
      createVisible: false, cform: { studentId: '', advisorUserId: '', remark: '' }, cError: '',
      assignVisible: false, assignRow: null, assignPositionId: '', assignError: '',
      advisorVisible: false, advisorRow: null, advisorAssignmentUserId: '', advisorAssignmentReason: '', advisorError: '',
      importVisible: false,
      confirm: { visible: false, title: '', message: '', type: 'primary', confirmText: '确认', requireReason: false, reasonLabel: '原因', action: null, row: null },
      columns: [
        { key: 'student', title: '学生' },
        { key: 'eligibility', title: '实习资格' },
        { key: 'destination', title: '去向' },
        { key: 'placement', title: '企业 / 岗位' },
        { key: 'status', title: '实习状态' },
        { key: 'actions', title: '操作', width: '300px' }
      ]
    }
  },
  computed: {
    statusOpts() { return STUDENT_STATUS },
    viewModes() {
      return [
        { key: 'roster', label: '全部学生' },
        { key: 'eligibility', label: '待资格认定' },
        { key: 'position', label: '待分配岗位' },
        { key: 'status', label: '在岗学生' },
        { key: 'destination', label: '去向待落实' }
      ]
    },
    filterFields() {
      return [
        { key: 'keyword', label: '关键词', type: 'text', placeholder: '姓名 / 学号' },
        { key: 'status', label: '实习状态', type: 'select', options: STUDENT_STATUS },
        { key: 'eligibility', label: '实习资格', type: 'select', options: ELIGIBILITY_STATUS },
        { key: 'destination', label: '去向', type: 'select', options: DESTINATION_TYPE },
        { key: 'hasPosition', label: '岗位', type: 'select', options: [{ value: 'true', label: '已分配' }, { value: 'false', label: '未分配' }] }
      ]
    },
    canStudentManage() { return canCode(this.ctx, 'internship.student.manage') },
    canEligibility() { return canCode(this.ctx, 'internship.student.eligibility.review') },
    canInsuranceView() { return canCode(this.ctx, 'internship.insurance.view') },
    toolbarActions() {
      const denyManage = !this.canStudentManage
      return [
        { key: 'create', label: '＋ 建档', variant: 'primary', disabled: denyManage, disabledReason: '无学生建档权限' },
        { key: 'import', label: '导入 Excel', disabled: denyManage, disabledReason: '无学生导入权限' },
        { key: 'insurance', label: '保险核验', variant: 'ghost', disabled: !this.canInsuranceView, disabledReason: '无保险查看权限' }
      ]
    },
    pageSubtitle() {
      const hint = PANEL_HINTS[this.activePanel] || ''
      return `查看和管理本批次学生的实习落实、在岗状态和材料情况 · 共 ${this.total} 人 · ${hint} · 学号默认脱敏`
    },
    summaryMetrics() {
      if (this.loading || this.error) return []
      return [{ label: '实习学生', value: this.total }]
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
  methods: {
    applyPanel(panel) {
      const key = PANEL_PRESETS[panel] ? panel : 'roster'
      this.activePanel = key
      this.filters = (PANEL_PRESETS[key] || PANEL_PRESETS.roster)()
      this.page = 1
      this.load()
    },
    goPanel(panel) {
      if (this.activePanel === panel) return
      this.$router.replace({ path: this.$route.path, query: { ...this.$route.query, panel } })
    },
    eligTone(s) { return s === 'QUALIFIED' ? 'success' : (s === 'UNQUALIFIED' ? 'danger' : 'warning') },
    exportFn() { return internStudentApi.exportStudents({ ...this.filters }) },
    onExported(data) { toast.success(`已导出 ${data.rowCount} 人（脱敏 + 水印，已写审计）`) },
    onImported(data) { toast.success(`已导入 ${data.created || 0} 人`); this.load() },
    async load() {
      this.loading = true; this.error = ''
      const p = { ...this.filters, page: this.page, pageSize: this.pageSize }
      if (p.hasPosition === '') delete p.hasPosition
      const res = await internStudentApi.getStudents(p)
      if (res.code === 0) { this.rows = res.data.list; this.total = res.data.total } else this.error = res.message
      this.loading = false
    },
    search() { this.page = 1; this.load() },
    reset() { this.filters = EMPTY_FILTERS(); this.page = 1; this.load() },
    turnPage(p) { this.page = p; this.load() },
    async onToolbar(key) {
      if (key === 'insurance') {
        if (!this.canInsuranceView) return toast.error('无保险查看权限')
        this.$router.push('/admin/internship/insurance')
        return
      }
      if ((key === 'create' || key === 'import') && !this.canStudentManage) return toast.error('无学生管理权限')
      if (key === 'create') {
        // 学生候选改为选择器内按关键字远程搜索（后端裁定数据范围），不再一次性预载
        this.cform = { studentId: '', advisorUserId: '', remark: '' }; this.cError = ''
        this.createVisible = true
      }
      if (key === 'import') { this.importVisible = true }
    },
    async submitCreate() {
      this.cError = ''
      if (!this.cform.studentId) { this.cError = '请选择学生'; return }
      this.submitting = true
      try {
        const res = await internStudentApi.createStudent({ studentId: this.cform.studentId, advisorUserId: this.cform.advisorUserId || null, remark: this.cform.remark })
        if (res.code === 0) { toast.success('已建档'); this.createVisible = false; this.load() } else this.cError = res.message
      } finally { this.submitting = false }
    },
    openAssign(row) {
      if (!this.canStudentManage) return toast.error('无学生管理权限')
      // 岗位候选改为选择器内按关键字远程搜索，不再一次性预载
      this.assignRow = row; this.assignPositionId = ''; this.assignError = ''
      this.assignVisible = true
    },
    async submitAssign() {
      this.assignError = ''
      this.submitting = true
      try {
        const res = await internStudentApi.assignPosition(this.assignRow.id, { positionId: this.assignPositionId })
        if (res.code === 0) { toast.success('已分配岗位（岗位库名额已回填）'); this.assignVisible = false; this.load() } else this.assignError = res.message
      } finally { this.submitting = false }
    },
    async openAssignAdvisor(row) {
      if (!this.canStudentManage) return toast.error('无学生管理权限')
      this.advisorRow = row
      this.advisorAssignmentUserId = row.advisorUserId || ''
      this.advisorAssignmentReason = ''
      this.advisorError = ''
      this.advisorVisible = true
    },
    async submitAssignAdvisor() {
      if (!this.advisorRow || !this.advisorAssignmentUserId) return
      this.advisorError = ''
      this.submitting = true
      try {
        const res = await internStudentApi.assignAdvisor(this.advisorRow.id, {
          advisorUserId: this.advisorAssignmentUserId,
          reason: this.advisorAssignmentReason
        })
        if (res.code === 0) {
          toast.success('指导教师已分配，变更已写入审计留痕')
          this.advisorVisible = false
          this.load()
        } else this.advisorError = res.message
      } finally { this.submitting = false }
    },
    askEligibility(row) {
      if (!this.canEligibility) return toast.error('无资格认定权限')
      this.confirm = { visible: true, title: '实习资格认定', message: `确认「${row.name}」实习资格合格？（合格后方可待上岗）`, type: 'primary', confirmText: '认定合格', requireReason: false, reasonLabel: '认定意见', action: 'ELIG_QUALIFIED', row }
    },
    rowActions(row) {
      const actions = [{ key: 'detail', label: '详情' }]
      if (row.status !== 'ARCHIVED') {
        actions.push({ key: 'assign', label: row.positionId ? '调岗' : '分配岗位', disabled: !this.canStudentManage, disabledReason: this.canStudentManage ? '' : '无学生管理权限' })
        actions.push({ key: 'assignAdvisor', label: row.advisorName ? '变更指导老师' : '分配指导老师', disabled: !this.canStudentManage, disabledReason: this.canStudentManage ? '' : '无学生管理权限' })
      }
      if (row.eligibilityStatus !== 'QUALIFIED' && row.status !== 'ARCHIVED') {
        actions.push({ key: 'eligibility', label: '认定资格', disabled: !this.canEligibility, disabledReason: this.canEligibility ? '' : '无资格认定权限' })
      }
      return actions
    },
    onRowAction(key, row) {
      if (key === 'detail') return this.$router.push('/admin/internship/students/' + row.id)
      if (key === 'assign') return this.openAssign(row)
      if (key === 'assignAdvisor') return this.openAssignAdvisor(row)
      if (key === 'eligibility') return this.askEligibility(row)
    },
    async onConfirm({ reason } = {}) {
      const { action, row } = this.confirm
      this.submitting = true
      try {
        let res
        if (action === 'ELIG_QUALIFIED') res = await internStudentApi.setEligibility(row.id, { status: 'QUALIFIED', reason: reason || '' })
        if (res && res.code === 0) { toast.success('已更新'); this.confirm.visible = false; this.load() } else if (res) toast.error(res.message)
      } finally { this.submitting = false }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.isl-viewnav { display: flex; align-items: center; gap: 6px; padding: 8px 10px; border: 1px solid var(--card-b); border-radius: 12px; background: var(--card); box-shadow: var(--s1); overflow-x: auto; }
.isl-viewnav__title { flex: 0 0 auto; padding: 0 8px 0 2px; color: var(--t2); font-size: 12px; font-weight: var(--font-weight-semibold); }
.isl-viewnav__item { flex: 0 0 auto; padding: 6px 11px; border: 1px solid transparent; border-radius: 8px; background: transparent; color: var(--t2); cursor: pointer; font-size: 12px; transition: .16s ease; }
.isl-viewnav__item:hover { color: var(--pri); background: var(--pri-bg); }
.isl-viewnav__item.is-active { border-color: var(--pri-100); background: var(--pri-bg); color: var(--pri); font-weight: var(--font-weight-semibold); }
.ie-form { display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-3); padding: var(--space-1) 0; }
.ie-fld { display: flex; flex-direction: column; gap: 4px; }
.ie-fld--full { grid-column: 1 / -1; }
.ie-lbl { font-size: 12px; color: var(--t2, #475569); }
.ie-lbl i { color: var(--danger, #dc2626); font-style: normal; }
.ie-in { width: 100%; padding: 7px 10px; border: 1px solid var(--line, #d9dee8); border-radius: 8px; font-size: 13px; box-sizing: border-box; }
.ie-err { grid-column: 1 / -1; color: var(--danger, #dc2626); font-size: 12px; margin: 0; }
.ie-hint { grid-column: 1 / -1; font-size: 12px; color: var(--t3, #64748b); margin: 0; }
.ie-actions { grid-column: 1 / -1; display: flex; justify-content: flex-end; gap: var(--space-2); margin-top: var(--space-2); }
.mp-btn { padding: 7px 16px; border: 1px solid var(--line, #d9dee8); border-radius: 8px; background: #fff; cursor: pointer; font-size: 13px; }
.mp-btn--primary { background: var(--pri, #2563eb); color: #fff; border-color: var(--pri, #2563eb); }
.mp-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.ie-imp { grid-column: 1 / -1; font-size: 12px; }
.ie-imp__errs { margin: 4px 0 0; padding-left: 18px; color: var(--danger, #dc2626); }
.ie-ok { color: var(--success, #16a34a); } .ie-bad { color: var(--danger, #dc2626); }
</style>
