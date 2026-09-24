<template>
  <ModulePageShell
    class="isl"
    :title="pageTitle"
    :subtitle="pageSubtitle"
  >
    <template #actions>
      <AppExportButton v-if="canExport" :export-fn="exportFn" @exported="onExported">导出名单</AppExportButton>
      <ModuleToolbar :actions="toolbarActions" @action="onToolbar" />
    </template>

    <section class="mp-card isl-list">
      <nav class="isl-viewnav" aria-label="实习学生视图">
        <span class="isl-viewnav__title">{{ loading || error ? '学生台账' : total + ' 名学生' }}</span>
        <button
          v-for="view in viewModes"
          :key="view.key"
          type="button"
          class="isl-viewnav__item"
          :class="{ 'is-active': activePanel === view.key }"
          :aria-pressed="activePanel === view.key"
          @click="goPanel(view.key)"
        >{{ view.label }}</button>
      </nav>
      <form class="isl-filters" @submit.prevent="search">
        <label class="isl-keyword">学生姓名 / 学号<input v-model="filters.keyword" type="search" placeholder="输入姓名或学号" /></label>
        <label v-for="field in filterFields.slice(1, 3)" :key="field.key">{{ field.label }}<select v-model="filters[field.key]"><option value="">全部</option><option v-for="option in field.options" :key="option.value" :value="option.value">{{ option.label }}</option></select></label>
        <div class="isl-filter-actions"><button class="mp-btn mp-btn--primary" type="submit">查询</button><button class="mp-btn" type="button" @click="reset">重置</button></div>
        <details class="isl-more" :open="!!(appliedFilters.destination || appliedFilters.hasPosition)"><summary>更多筛选{{ filters.destination || filters.hasPosition ? ' · 已选择' : '' }}</summary><div><label v-for="field in filterFields.slice(3)" :key="field.key">{{ field.label }}<select v-model="filters[field.key]"><option value="">全部</option><option v-for="option in field.options" :key="option.value" :value="option.value">{{ option.label }}</option></select></label></div></details>
      </form>
      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" title="暂无符合条件的学生" :description="canStudentManage ? '可调整筛选，或为当前批次建档、导入学生。' : '可调整筛选，或等待负责人准备本批次学生名单。'" />
      <DataTable v-else :columns="columns" :rows="rows" row-key="id" :pagination="{ page, pageSize, total }" @page-change="turnPage">
        <template #cell-student="{ row }">
          <RouterLink class="mp-cell-main mp-link" :to="studentLocation(row)">{{ row.name }}</RouterLink>
          <div class="mp-cell-sub"><AppSensitiveText :value="row.studentNo" /> · {{ row.className }}</div>
        </template>
        <template #cell-placement="{ row }">
          <template v-if="row.positionId">
            <div class="mp-cell-main">{{ row.enterpriseName }}</div>
            <div class="mp-cell-sub">{{ row.positionName }}</div>
          </template>
          <span v-else class="mp-note">{{ row.destinationLabel || '岗位待落实' }}</span>
        </template>
        <template #cell-eligibility="{ row }">
          <AppStatusTag :type="eligTone(row.eligibilityStatus)">{{ row.eligibilityLabel }}</AppStatusTag>
        </template>
        <template #cell-destination="{ row }">{{ row.destinationLabel }}</template>
        <template #cell-advisor="{ row }">{{ row.advisorName || '待分配' }}</template>
        <template #cell-status="{ row }">
          <AppStatusTag :type="row.statusTone" dot>{{ row.statusLabel }}</AppStatusTag>
        </template>
        <template #cell-actions="{ row }">
          <TableActionColumn :actions="rowActions(row)" @action="(key) => onRowAction(key, row)" />
        </template>
      </DataTable>
    </section>

    <!-- 建档 -->
    <AppDrawer :visible="createVisible" title="实习学生建档" mode="modal" size="large" @update:visible="!submitting && (createVisible = $event)">
      <form class="ie-form" @submit.prevent="submitCreate">
        <!-- 注意：Picker 不能包在 <label> 里，label 激活会把点击转发给选择器内部按钮（清空/搜索） -->
        <div class="ie-fld ie-fld--full"><span class="ie-lbl">学生 <i>*</i></span>
          <AppInternshipCandidateStudentPicker
            v-model="cform.studentId"
            :disabled="submitting"
            placeholder="输入姓名或学号搜索学生"
            search-placeholder="按姓名 / 学号搜索"
            data-scope-hint="仅显示你数据范围内的学生 · 已建档学生提交时由后端拦截重复"
          />
        </div>
        <div class="ie-fld"><span class="ie-lbl">校内指导教师</span><AppInternshipAdvisorPicker v-model="cform.advisorUserId" :disabled="submitting" clearable placeholder="暂不分配" /></div>
        <label class="ie-fld ie-fld--full"><span class="ie-lbl">备注</span><AppTextarea v-model="cform.remark" :disabled="submitting" :rows="2" /></label>
        <p v-if="cError" class="ie-err">{{ cError }}</p>
        <div class="ie-actions">
          <button type="button" class="mp-btn" :disabled="submitting" @click="createVisible = false">取消</button>
          <button type="submit" class="mp-btn mp-btn--primary" :disabled="submitting">建档</button>
        </div>
      </form>
    </AppDrawer>

    <AppDrawer :visible="advisorVisible" :title="advisorRow ? `分配指导教师 · ${advisorRow.name}` : '分配指导教师'" mode="modal" size="medium" @update:visible="!$event && closeAdvisor()">
      <LoadingState v-if="advisorLoading" />
      <ErrorState v-else-if="advisorLoadError" :description="advisorLoadError" @retry="restoreAdvisor" />
      <div v-else-if="advisorRow" class="ie-form">
        <div ref="advisorContext" class="isl-advisor-context" tabindex="-1"><strong>{{ advisorRow.name }}</strong><span>{{ advisorRow.className || '班级待补充' }} · {{ advisorRow.batchName || '当前批次' }}</span><span>{{ advisorRow.positionName || advisorRow.destinationLabel || '岗位待落实' }}</span></div>
        <p class="ie-hint">当前指导教师：{{ advisorRow?.advisorName || '待分配' }}。选择接手指导的教师，并填写必要的交接说明。</p>
        <div class="ie-fld ie-fld--full"><span class="ie-lbl">校内指导教师 <i>*</i></span><AppInternshipAdvisorPicker v-model="advisorAssignmentUserId" :disabled="submitting || advisorConflict" /></div>
        <label class="ie-fld ie-fld--full"><span class="ie-lbl">分配说明</span><AppTextarea v-model="advisorAssignmentReason" :disabled="submitting || advisorConflict" :rows="2" placeholder="例如：按专业方向调整指导关系" /></label>
        <p v-if="advisorError" class="ie-err">{{ advisorError }}</p>
        <p v-else-if="advisorUnchanged" class="ie-hint">已选择当前指导教师；如需调整，请选择接手教师。</p>
        <div class="ie-actions">
          <button type="button" class="mp-btn" :disabled="submitting" @click="closeAdvisor">返回名单</button>
          <button type="button" class="mp-btn mp-btn--primary" :disabled="submitting || advisorConflict || advisorUnchanged || !advisorAssignmentUserId" @click="submitAssignAdvisor">确认分配</button>
        </div>
      </div>
    </AppDrawer>

    <!-- Excel 导入（P0-E 正式 xlsx） -->
    <AppExcelImportDrawer
      :key="scopeEpoch"
      v-model:visible="importVisible"
      title="导入实习学生"
      show-account-boundary
      template-name="实习学生导入模板.xlsx"
      :required-fields="['学号']"
      :preview-fields="['studentNo', 'advisorName', 'enterpriseName', 'batchName']"
      :download-template-fn="() => internStudentApi.downloadImportTemplate()"
      :upload-fn="(file) => internStudentApi.uploadImportXlsx(file, this.batchStore.selectedBatchId)"
      :confirm-fn="({ rows }) => internStudentApi.importConfirmRows(rows, this.batchStore.selectedBatchId)"
      :download-errors-fn="({ rows, errors }) => internStudentApi.downloadImportErrors(rows, errors)"
      @imported="onImported"
    />

  </ModulePageShell>
</template>

<script>
/** 实习学生列表（/admin/internship/students）：生产级只走真实后端；建档/分配岗位(岗位库)/资格/状态/导入导出。 */
import { ModulePageShell, ModuleToolbar, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppDrawer } from '@/components/ui'
import { AppSensitiveText, AppStatusTag, AppExportButton, AppTextarea, AppInternshipCandidateStudentPicker, AppInternshipAdvisorPicker } from '@/components/common'
import { AppExcelImportDrawer } from '@/components/common/excel'
import { TableActionColumn } from '@/modules/internship/components'
import { internStudentApi } from '@/modules/internship/api/internship-student.api'
import { STUDENT_STATUS, ELIGIBILITY_STATUS, DESTINATION_TYPE } from '@/modules/internship/constants/internship-student.constants'
import { canCode } from '@/modules/internship/composables/permission'
import { useInternshipBatchStore } from '@/stores/internshipBatch'
import { toast } from '@/utils/toast'

const EMPTY_FILTERS = () => ({ keyword: '', status: '', eligibility: '', destination: '', hasPosition: '' })

const PANEL_PRESETS = {
  roster: () => EMPTY_FILTERS(),
  eligibility: () => ({ ...EMPTY_FILTERS(), eligibility: 'PENDING' }),
  status: () => ({ ...EMPTY_FILTERS(), status: 'ONBOARD' }),
  destination: () => ({ ...EMPTY_FILTERS(), destination: 'NONE' }),
  position: () => ({ ...EMPTY_FILTERS(), hasPosition: 'false' }),
  enterprise: () => ({ ...EMPTY_FILTERS(), hasPosition: 'true' }),
  mentor: () => EMPTY_FILTERS()
}

export default {
  name: 'InternshipStudentListView',
  components: { ModulePageShell, ModuleToolbar, DataTable, LoadingState, ErrorState, EmptyState,
    AppDrawer, AppSensitiveText, AppStatusTag, AppExportButton, AppTextarea, AppExcelImportDrawer, TableActionColumn,
    AppInternshipCandidateStudentPicker, AppInternshipAdvisorPicker },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loadSequence: 0, scopeEpoch: 0, loading: true, error: '', submitting: false, activePanel: 'roster',
      rows: [], total: 0, page: 1, pageSize: 10, filters: EMPTY_FILTERS(), appliedFilters: EMPTY_FILTERS(), advisorConflict: false,
      createVisible: false, cform: { studentId: '', advisorUserId: '', remark: '' }, cError: '',
      advisorVisible: false, advisorRow: null, advisorAssignmentUserId: '', advisorAssignmentReason: '', advisorError: '',
      advisorLoading: false, advisorLoadError: '', advisorSequence: 0,
      importVisible: false,
      columns: [
        { key: 'student', title: '学生' },
        { key: 'eligibility', title: '实习资格' },
        { key: 'placement', title: '岗位与去向' },
        { key: 'status', title: '实习状态' },
        { key: 'advisor', title: '指导教师' },
        { key: 'actions', title: '操作', width: '170px' }
      ]
    }
  },
  computed: {
    advisorUnchanged() { return !!this.advisorAssignmentUserId && String(this.advisorAssignmentUserId) === String(this.advisorRow?.advisorUserId || '') },
    pageTitle() { return ({ roster: '实习学生名单', eligibility: '实习资格审核', mentor: '导师分配', status: '在岗学生', position: '待分配岗位', destination: '去向待落实', enterprise: '已落岗学生' })[this.activePanel] },
    statusOpts() { return STUDENT_STATUS },
    viewModes() {
      return [
        { key: 'roster', label: '全部学生' },
        { key: 'eligibility', label: '待资格认定' },
        { key: 'position', label: '待分配岗位' },
        { key: 'status', label: '在岗学生' },
        { key: 'destination', label: '去向待落实' },
        { key: 'mentor', label: '导师分配' }
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
    canView() { return this.allowed('internship.student.view') },
    canExport() { return this.allowed('internship.student.export') },
    canStudentManage() { return this.allowed('internship.student.manage') },
    canEligibility() { return this.allowed('internship.student.eligibility.review') },
    canInsuranceView() { return this.allowed('internship.insurance.view') },
    batchStore() { return useInternshipBatchStore() },
    canWriteBatch() { return this.batchStore.canWriteStudents },
    toolbarActions() {
      if (this.activePanel === 'mentor') return [{ key: 'roster', label: '管理学生名单', variant: 'ghost' }]
      const denyManage = !this.canStudentManage
      const denyBatch = !this.canWriteBatch
      const batchReason = !this.batchStore.selectedBatchId
        ? '请先选择实习批次'
        : '当前批次已结束/归档/作废，禁止新增'
      return [
        { key: 'create', label: '学生建档', variant: 'primary',
          disabled: denyManage || denyBatch,
          disabledReason: denyManage ? '无学生建档权限' : batchReason },
        { key: 'import', label: '导入 Excel',
          disabled: denyManage || denyBatch,
          disabledReason: denyManage ? '无学生导入权限' : batchReason },
        { key: 'insurance', label: '保险核验', variant: 'ghost', disabled: !this.canInsuranceView, disabledReason: '无保险查看权限' }
      ]
    },
    pageSubtitle() {
      return this.activePanel === 'mentor' ? '核对本批次指导关系，按实际安排分配或调整校内指导教师。' : this.activePanel === 'eligibility' ? '按批次核对资格，记录认定结果和学生后续安排。' : '查找本批次学生，进入档案核对资格、指导关系与实习安排。'
    },
  },
  watch: {
    '$route.fullPath': { immediate: true, handler() {
      if (this.$route.path === '/admin/internship/students') this.applyRouteFilters()
    } },
    'batchStore.selectedBatchId'() { this.resetScope(); this.applyRouteFilters() },
    ctx: { deep: true, handler() { this.resetScope(); this.load() } }
  },
  beforeUnmount() { this.loadSequence++; this.scopeEpoch++; this.advisorSequence++ },
  methods: {
    allowed(code) { return Array.isArray(this.ctx?.permissionPatterns) && canCode(this.ctx, code) },
    resetScope() {
      this.scopeEpoch++; this.loadSequence++; this.submitting = false
      this.advisorSequence++; this.advisorLoading = false; this.advisorLoadError = ''
      this.createVisible = false; this.advisorVisible = false; this.importVisible = false
      this.cform = { studentId: '', advisorUserId: '', remark: '' }; this.cError = ''
      this.advisorRow = null; this.advisorAssignmentUserId = ''; this.advisorAssignmentReason = ''; this.advisorError = ''; this.advisorConflict = false
      this.rows = []; this.total = 0
    },
    applyRouteFilters() {
      const q = this.$route.query
      const panel = String(q.panel || 'roster')
      this.activePanel = PANEL_PRESETS[panel] ? panel : 'roster'
      this.filters = PANEL_PRESETS[this.activePanel]()
      for (const key of Object.keys(EMPTY_FILTERS())) {
        if (Object.hasOwn(q, key)) this.filters[key] = String(q[key] || '')
      }
      if (!['true', 'false'].includes(this.filters.hasPosition)) this.filters.hasPosition = ''
      this.appliedFilters = { ...this.filters }
      this.page = Math.max(1, Math.floor(Number(q.page) || 1))
      this.load()
      this.restoreAdvisor()
    },
    updateQuery() {
      const query = this.batchStore.withBatchQuery({ panel: this.activePanel, ...this.appliedFilters, page: String(this.page) })
      const location = { path: '/admin/internship/students', query }
      if (this.$router.resolve(location).fullPath === this.$route.fullPath) this.load()
      else this.$router.replace(location)
    },
    goPanel(panel) {
      this.activePanel = panel; this.filters = PANEL_PRESETS[panel](); this.appliedFilters = { ...this.filters }; this.page = 1
      this.updateQuery()
    },
    studentLocation(row, section = 'profile') {
      return { path: '/admin/internship/students/' + row.id, query: { batchId: row.batchId || this.batchStore.selectedBatchId, section, returnTo: this.$route.fullPath } }
    },
    eligTone(s) { return s === 'QUALIFIED' ? 'success' : (s === 'UNQUALIFIED' ? 'danger' : 'warning') },
    queryParams() {
      const params = { ...this.appliedFilters, batchId: this.batchStore.selectedBatchId }
      if (!params.hasPosition) delete params.hasPosition
      else params.hasPosition = params.hasPosition === 'true'
      return params
    },
    async exportFn() {
      if (!this.canExport || !this.batchStore.selectedBatchId) return { code: 1, message: '请确认导出权限并选择批次' }
      const scope = this.scopeEpoch, batchId = this.batchStore.selectedBatchId
      const result = await internStudentApi.exportStudents(this.queryParams())
      return scope === this.scopeEpoch && batchId === this.batchStore.selectedBatchId ? result : { code: 1, message: '办理范围已切换，请重新导出' }
    },
    onExported(data) { toast.success(`已导出 ${data.rowCount} 人（脱敏 + 水印，已写审计）`) },
    onImported(data) { toast.success(`已导入 ${data.created || 0} 人`); this.load() },
    async load() {
      const seq = ++this.loadSequence
      this.rows = []; this.total = 0
      if (!this.canView) { this.loading = false; this.error = '当前身份没有查看学生名单的权限'; return }
      if (!this.batchStore.selectedBatchId) {
        this.loading = false
        this.rows = []
        this.total = 0
        this.error = this.batchStore.needsExplicitSelect
          ? '存在多个进行中批次，请先选择当前工作批次'
          : '请先选择实习批次'
        return
      }
      this.loading = true; this.error = ''
      const p = { ...this.queryParams(), page: this.page, pageSize: this.pageSize }
      try {
        const res = await internStudentApi.getStudents(p)
        if (seq !== this.loadSequence) return
        if (res.code === 0) { this.rows = res.data.list; this.total = res.data.total } else this.error = res.message || '学生名单读取失败，请重试'
      } catch (e) { if (seq === this.loadSequence) this.error = e.message || '学生名单读取失败，请重试' }
      finally { if (seq === this.loadSequence) this.loading = false }
    },
    search() { this.appliedFilters = { ...this.filters }; this.page = 1; this.updateQuery() },
    reset() { this.filters = EMPTY_FILTERS(); this.search() },
    turnPage(p) { this.page = p; this.updateQuery() },
    async onToolbar(key) {
      if (this.submitting) return
      if (key === 'roster') return this.goPanel('roster')
      if (key === 'insurance') {
        if (!this.canInsuranceView) return toast.error('无保险查看权限')
        this.$router.push({ path: '/admin/internship/insurance', query: this.batchStore.withBatchQuery({}) })
        return
      }
      if ((key === 'create' || key === 'import') && !this.canStudentManage) return toast.error('无学生管理权限')
      if ((key === 'create' || key === 'import') && !this.canWriteBatch) {
        return toast.error(!this.batchStore.selectedBatchId ? '请先选择实习批次' : '当前批次不可新增学生')
      }
      if (key === 'create') {
        this.cform = { studentId: '', advisorUserId: '', remark: '' }; this.cError = ''
        this.createVisible = true
      }
      if (key === 'import') { this.importVisible = true }
    },
    async submitCreate() {
      if (this.submitting || !this.canStudentManage || !this.canWriteBatch) return
      const scope = this.scopeEpoch, batchId = this.batchStore.selectedBatchId
      this.cError = ''
      if (!this.cform.studentId) { this.cError = '请选择学生'; return }
      if (!this.batchStore.selectedBatchId) { this.cError = '请先选择实习批次'; return }
      this.submitting = true
      try {
        const res = await internStudentApi.createStudent({
          studentId: this.cform.studentId,
          batchId,
          advisorUserId: this.cform.advisorUserId || null,
          remark: this.cform.remark
        })
        if (scope !== this.scopeEpoch || batchId !== this.batchStore.selectedBatchId) return
        if (res.code === 0) { toast.success('已建档，下一步核对实习资格'); this.createVisible = false; this.$router.push(this.studentLocation(res.data, 'eligibility')) } else this.cError = res.message
      } catch (e) { if (scope === this.scopeEpoch) this.cError = e.message || '建档失败，填写内容已保留' }
      finally { if (scope === this.scopeEpoch) this.submitting = false }
    },
    async openAssignAdvisor(row) {
      if (!this.canStudentManage) return toast.error('无学生管理权限')
      if (this.submitting || row.status === 'ARCHIVED') return
      this.advisorRow = { ...row }
      this.advisorAssignmentUserId = row.advisorUserId || ''
      this.advisorAssignmentReason = ''
      this.advisorError = ''
      this.advisorConflict = false
      this.advisorVisible = true
      this.$nextTick?.(() => this.$refs?.advisorContext?.focus({ preventScroll: true }))
    },
    advisorLocation(row) {
      return { path: '/admin/internship/students', query: { ...this.$route.query, batchId: this.batchStore.selectedBatchId, advisorId: String(row.id) } }
    },
    closeAdvisor() {
      if (this.submitting) return
      this.advisorSequence++; this.advisorLoading = false; this.advisorVisible = false
      if (this.$route.query.advisorId) {
        const query = { ...this.$route.query }; delete query.advisorId
        this.$router.replace({ path: '/admin/internship/students', query })
      }
    },
    async restoreAdvisor() {
      if (this.advisorVisible) this.submitting = false
      const seq = ++this.advisorSequence, id = this.$route.query.advisorId, batchId = this.batchStore.selectedBatchId
      this.advisorVisible = !!id; this.advisorRow = null; this.advisorLoadError = ''; this.advisorLoading = false
      if (!id) return
      if (typeof id !== 'string' || !/^\d+$/.test(id) || !batchId) { this.advisorLoadError = '分配入口缺少有效学生或批次，请返回名单重新进入'; return }
      if (!this.canStudentManage || !this.canView) { this.advisorLoadError = '当前身份无权办理导师分配'; return }
      this.advisorLoading = true
      try {
        const res = await internStudentApi.getStudentDetail(id)
        if (seq !== this.advisorSequence || batchId !== this.batchStore.selectedBatchId || id !== this.$route.query.advisorId) return
        if (res.code !== 0 || !res.data) throw new Error(res.message || '学生记录读取失败，请重试')
        if (String(res.data.batchId) !== String(batchId)) throw new Error('此学生记录不属于当前批次，请返回名单重新进入')
        if (res.data.status === 'ARCHIVED') throw new Error('该学生实习已归档，不能变更指导教师')
        await this.openAssignAdvisor(res.data)
      } catch (e) { if (seq === this.advisorSequence) this.advisorLoadError = e.message || '学生记录读取失败，请重试' }
      finally {
        if (seq === this.advisorSequence) {
          this.advisorLoading = false
          this.$nextTick?.(() => this.$refs?.advisorContext?.focus({ preventScroll: true }))
        }
      }
    },
    async submitAssignAdvisor() {
      if (this.submitting || this.advisorConflict || this.advisorUnchanged || !this.canStudentManage || !this.advisorRow || this.advisorRow.status === 'ARCHIVED' || !this.advisorAssignmentUserId) return
      const scope = this.scopeEpoch, batchId = this.batchStore.selectedBatchId
      const workspace = this.advisorSequence
      this.advisorError = ''
      this.submitting = true
      try {
        const res = await internStudentApi.assignAdvisor(this.advisorRow.id, {
          advisorUserId: this.advisorAssignmentUserId,
          reason: this.advisorAssignmentReason,
          expectedVersion: this.advisorRow.version
        })
        if (scope !== this.scopeEpoch || batchId !== this.batchStore.selectedBatchId || workspace !== this.advisorSequence) return
        if (res.code === 0) {
          toast.success('指导教师已分配，变更已写入审计留痕')
          this.submitting = false; this.closeAdvisor()
          this.load()
        } else {
          this.advisorConflict = /CONFLICT|409/.test(String(res.code)) || /版本|已被修改/.test(res.message || '')
          this.advisorError = (res.message || '分配失败，请重试') + (this.advisorConflict ? '。填写内容已保留，请取消后刷新名单、核对最新记录再办理。' : '')
        }
      } catch (e) { if (scope === this.scopeEpoch && workspace === this.advisorSequence) this.advisorError = e.message || '分配失败，填写内容已保留' }
      finally { if (scope === this.scopeEpoch && workspace === this.advisorSequence) this.submitting = false }
    },
    rowActions(row) {
      const actions = [{ key: 'detail', label: '档案' }]
      if (this.activePanel !== 'mentor' && row.status !== 'ARCHIVED' && this.canWriteBatch && this.canEligibility) actions.push({ key: 'eligibility', label: '审核资格' })
      if (row.status !== 'ARCHIVED' && this.canStudentManage) {
        const assign = { key: 'assignAdvisor', label: row.advisorUserId ? '调整导师' : '分配导师' }
        if (this.activePanel === 'mentor') actions.unshift(assign)
        else actions.push(assign)
      }
      return actions
    },
    onRowAction(key, row) {
      if (key === 'assignAdvisor') {
        if (!this.canStudentManage || row.status === 'ARCHIVED' || this.submitting) return
        return this.$router.push(this.advisorLocation(row))
      }
      return this.$router.push(this.studentLocation(row, key === 'eligibility' ? 'eligibility' : 'profile'))
    },

  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.isl-filters { display:flex; flex-wrap:wrap; align-items:flex-end; gap:12px; padding:16px 18px; }
.isl-filters label { display:flex; flex-direction:column; gap:7px; color:var(--text-secondary); font-size:12px; }
.isl-keyword { flex:1 1 210px; }
.isl-filters input,.isl-filters select { min-height:36px; padding:7px 10px; border:1px solid var(--border-base); border-radius:6px; background:var(--field-bg); color:var(--text-primary); font:inherit; }
.isl-filters input:focus-visible,.isl-filters select:focus-visible,.isl-more summary:focus-visible { outline:2px solid var(--primary-500); outline-offset:2px; }
.isl-filter-actions { display:flex; gap:8px; }
.isl-advisor-context { display:flex;flex-direction:column;gap:6px;padding:12px 14px;border:1px solid var(--border-base);border-radius:8px;background:var(--field-bg);font-size:13px;line-height:1.6;overflow-wrap:anywhere;grid-column:1/-1; }
.isl-advisor-context strong { color:var(--text-primary);font-size:15px; }
.isl-advisor-context span { color:var(--text-secondary); }
.isl-more { flex-basis:100%; color:var(--text-secondary); font-size:12px; }
.isl-more summary { cursor:pointer; padding:4px 0; }
.isl-more > div { display:flex; flex-wrap:wrap; gap:12px; padding-top:10px; }
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

.isl-list{padding:0;overflow:hidden}.isl-list .isl-viewnav{border:0;border-radius:0;box-shadow:none;padding:14px 18px;background:transparent;border-bottom:1px solid var(--line);flex-wrap:wrap}
.isl-list :deep(.tac){display:flex;flex-wrap:nowrap;gap:12px}
.isl-list :deep(.tac__btn){padding:2px 0}
.isl-list :deep(.dt){border:0;box-shadow:none;border-radius:0}.isl-list :deep(table){min-width:900px}
.isl .mp-cell-sub{line-height:1.6}.isl .mp-cell-main.mp-link{display:block;text-decoration:none;font-weight:500}
@media(max-width:800px){.isl-list{overflow:auto}}
</style>
