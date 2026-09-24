<template>
  <ModulePageShell
:title="isAcademicTeacher ? '培养方案' : '方案列表'"
    :subtitle="isAcademicTeacher ? '仅查看学校已经正式发布、生效或冻结留存的培养方案' : '一行是一份专业年级方案，不是一门课程'"
    show-subtitle-in-concise
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton v-if="hasPermission('academicAffairs.program.manage')" @click="importChooserVisible = !importChooserVisible">Excel导入</AppButton>
      <AppButton v-if="!isAcademicTeacher" @click="$router.push('/admin/academic-affairs/programs/opening-plan')">开课差异</AppButton>
      <AppButton v-if="hasPermission('academicAffairs.program.manage')" variant="primary" @click="showCreate = !showCreate">＋ 新建方案</AppButton>
    </template>

    <div class="mp-stack">
      <AppSectionCard v-if="importChooserVisible" title="培养方案 Excel 导入阶段" subtitle="同一六工作表模板，阶段由操作者明确选择；浏览器不推断写入顺序">
        <AppInlineAlert type="info" description="先导入方案定义并确认，再按实施进度导入适用范围绑定；两个阶段分别形成独立 ImportJob 与审计证据。" />
        <div class="aa-actions">
          <AppButton variant="primary" @click="openProgramImport('DEFINITION')">1. 方案定义</AppButton>
          <AppButton @click="openProgramImport('BINDING')">2. 适用范围绑定</AppButton>
          <AppButton variant="ghost" @click="downloadProgramTemplate">下载六工作表模板</AppButton>
        </div>
      </AppSectionCard>
      <div v-if="summary && !isAcademicTeacher" class="aa-summary-grid">
        <div class="aa-summary-card"><span>本次范围</span><strong>{{ stageSummary.total }}</strong><small>专业年级方案</small></div>
        <div class="aa-summary-card"><span>编制中</span><strong>{{ stageSummary.authoring }}</strong><small>可继续完善</small></div>
        <div class="aa-summary-card is-warning"><span>待审核</span><strong>{{ stageSummary.review }}</strong><small>不提前生成正式任务</small></div>
        <div class="aa-summary-card is-ok"><span>已发布</span><strong>{{ stageSummary.published }}</strong><small>修改须建立新版本</small></div>
      </div>

      <AppInlineAlert
        v-if="!isAcademicTeacher && summary?.blockedPrograms"
        type="warning"
        title="先处理方案阻断，再生成教学任务"
        :description="`当前有 ${summary.blockedPrograms} 个方案不能提交审核。进入方案详情可查看具体规则、定位字段和处理建议。`"
      />

      <AppSectionCard v-if="showCreate" title="新建培养方案">
        <div class="aa-cal-form">
          <label class="aa-cal-form__item aa-cal-form__item--grow">
            方案名称<input v-model.trim="draft.programName" class="aa-input" placeholder="如 软件技术2026级培养方案" maxlength="60" />
          </label>
          <label class="aa-cal-form__item">专业<AppMajorPicker v-model="draft.majorId" placeholder="选择专业" /></label>
          <label class="aa-cal-form__item">年级<input v-model.trim="draft.gradeYear" class="aa-input aa-input--sm" placeholder="如 2026" maxlength="4" /></label>
          <label class="aa-cal-form__item">毕业总学分<input v-model.number="draft.totalCredits" type="number" min="0.5" step="0.5" class="aa-input aa-input--sm" /></label>
          <AppButton variant="primary" :disabled="!canCreate" :loading="creating" @click="createProgram">创建</AppButton>
        </div>
      </AppSectionCard>

      <div class="aa-list-card">
        <div class="aa-list-card__head">
          <strong>方案与适用年级</strong>
          <span>共 {{ pagination.total }} 份正式来源记录</span>
        </div>
        <form class="aa-actions aa-list-card__filters" role="search" @submit.prevent="pagination.page = 1; applyPage()"><input v-model="keyword" class="aa-input" aria-label="搜索人才培养方案" placeholder="搜索人才培养方案" /><AppButton type="submit">查询</AppButton><AppButton variant="ghost" @click="keyword = ''; pagination.page = 1; applyPage()">清空</AppButton></form>
      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" :title="isAcademicTeacher ? '暂无正式培养方案' : '还没有培养方案'" :description="isAcademicTeacher ? '当前没有已正式发布或生效的培养方案，请联系教务管理人员。' : '点击「新建方案」开始编制课程、学分结构、毕业要求和实践环节'" />
      <DataTable v-else :columns="columns" :rows="rows" row-key="programId" :pagination="pagination" @page-change="onPageChange">
        <template #cell-name="{ row }">
          <div class="mp-cell-main">{{ row.programName }}</div>
          <div class="mp-cell-sub">{{ row.courseCount ?? '—' }} 门课程 · 正式方案 #{{ row.programId }}</div>
        </template>
        <template #cell-majorGrade="{ row }">
          <div class="mp-cell-main">{{ row.majorName || '专业待核验' }}</div>
          <div class="mp-cell-sub">{{ row.gradeYear ? `${row.gradeYear}级` : '年级待核验' }}</div>
        </template>
        <template #cell-version="{ row }">v{{ row.version }}</template>
        <template #cell-credits="{ row }">
          <div class="mp-cell-main">{{ row.totalCredits ?? '—' }} 学分</div>
          <div class="mp-cell-sub">已编 {{ row.creditSum ?? '—' }}</div>
        </template>
        <template #cell-status="{ row }">
          <AppStatusTag :type="reviewStatusColor(row.status)" :label="statusLabel(row.status)" dot />
          <div v-if="row.blockerCount" class="mp-cell-sub is-danger-text">{{ row.blockerCount }} 项阻断</div>
        </template>
        <template #cell-actions="{ row }">
          <button class="mp-link" @click="$router.push(`/admin/academic-affairs/programs/${row.programId}`)">打开方案</button>
        </template>
      </DataTable>
      </div>
    </div>

    <AaAuthoritativeImportDrawer
      v-model:visible="importVisible"
      title="培养方案六工作表权威导入"
      template-name="培养方案六工作表权威导入模板.xlsx"
      :phase-label="programImportPhase === 'DEFINITION' ? '1. 方案定义（DEFINITION）' : '2. 适用范围绑定（BINDING）'"
      :preview-fields="['sheetName', 'rowNo', 'programCode', 'programName', 'majorCode', 'gradeYear', 'courseCode']"
      :download-template-fn="academicFileExchangeApi.downloadProgramTemplate"
      :upload-fn="uploadProgramFile"
      @imported="onProgramImported"
    />
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppInlineAlert, AppSectionCard, AppStatusTag, AppMajorPicker } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { programQualityApi } from '@/modules/academicAffairs/api/program-quality.api'
import { academicFileExchangeApi } from '@/modules/academicAffairs/api/academic-file-exchange.api'
import AaAuthoritativeImportDrawer from '@/modules/academicAffairs/components/AaAuthoritativeImportDrawer.vue'
import { REVIEW_STATUS, reviewStatusColor } from '@/modules/academicAffairs/constants/course-program'
import { matchPermission } from '@/config/navPlan'
import { toast } from '@/utils/toast'

export default {
  name: 'AaProgramListView',
  components: { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppButton, AppInlineAlert, AppSectionCard, AppStatusTag, AppMajorPicker, AaAuthoritativeImportDrawer },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      keyword: '', requestRevision: 0, loading: true,
      error: '',
      rows: [],
      allRows: [],
      summary: null,
      academicFileExchangeApi,
      importChooserVisible: false, importVisible: false, programImportPhase: 'DEFINITION',
      showCreate: false,
      creating: false,
      draft: { programName: '', majorId: '', gradeYear: '', totalCredits: null },
      pagination: { page: 1, pageSize: 20, total: 0 },
      columns: [
        { key: 'name', title: '方案名称' },
        { key: 'majorGrade', title: '专业年级', width: '190px' },
        { key: 'version', title: '版本', width: '88px' },
        { key: 'credits', title: '毕业学分', width: '140px' },
        { key: 'status', title: '当前阶段', width: '160px' },
        { key: 'actions', title: '办理入口', width: '110px' }
      ]
    }
  },
  computed: {
    isAcademicTeacher() {
      return String(this.ctx?.currentRole?.roleCode || this.ctx?.currentRole?.roleType || '').toUpperCase() === 'ACADEMIC_TEACHER'
    },
    stageSummary() {
      const statuses = this.allRows.map((row) => row.status)
      return {
        total: this.allRows.length,
        authoring: statuses.filter((status) => ['DRAFT', 'RETURNED'].includes(status)).length,
        review: statuses.filter((status) => ['COLLEGE_REVIEW', 'ACADEMIC_REVIEW'].includes(status)).length,
        published: statuses.filter((status) => ['PUBLISHED', 'ENABLED'].includes(status)).length
      }
    },
    canCreate() {
      return Boolean(
        this.hasPermission('academicAffairs.program.manage') && this.draft.programName && this.draft.majorId && /^\d{4}$/.test(this.draft.gradeYear) && Number(this.draft.totalCredits) > 0
      )
    }
  },
  beforeUnmount() { this.requestRevision++ },
  created() { this.load() },
  methods: {
    hasPermission(key) { return matchPermission(this.ctx.permissionPatterns || [], key) },
    reviewStatusColor,
    statusLabel(value) { return REVIEW_STATUS[value] || (value ? '待确认' : '') },
    openProgramImport(phase) {
      this.programImportPhase = phase === 'BINDING' ? 'BINDING' : 'DEFINITION'
      this.importChooserVisible = false
      this.importVisible = true
    },
    uploadProgramFile(file) {
      return this.programImportPhase === 'BINDING'
        ? academicFileExchangeApi.uploadProgramBindingImport(file)
        : academicFileExchangeApi.uploadProgramDefinitionImport(file)
    },
    async downloadProgramTemplate() {
      const res = await academicFileExchangeApi.downloadProgramTemplate()
      if (res.code !== 0) { toast.error(res.message || '培养方案模板下载失败'); return }
      const url = URL.createObjectURL(res.data)
      const a = document.createElement('a'); a.href = url; a.download = '培养方案六工作表权威导入模板.xlsx'; a.click(); URL.revokeObjectURL(url)
    },
    async onProgramImported() { toast.success('培养方案权威导入已完成'); this.importVisible = false; await this.load() },
    applyPage() {
      const start = (this.pagination.page - 1) * this.pagination.pageSize
      const keyword = this.keyword.trim().toLowerCase()
      const visible = this.allRows.filter(row => !keyword || [row.programName,row.gradeYear,row.majorName].some(value => String(value || '').toLowerCase().includes(keyword)))
      this.rows = visible.slice(start, start + this.pagination.pageSize)
      this.pagination.total = visible.length
    },
    onPageChange(page) { this.pagination.page = page; this.applyPage() },
    async createProgram() {
      if (this.creating || !this.canCreate) return
      this.creating = true
      const res = await academicAffairsApi.createProgram({
        programName: this.draft.programName,
        majorId: this.draft.majorId,
        gradeYear: this.draft.gradeYear,
        totalCredits: this.draft.totalCredits,
        requirement: {}
      })
      this.creating = false
      if (res.code === 0) {
        toast.success('方案已创建，请继续配置课程、学分结构、毕业要求和实践环节')
        this.$router.push(`/admin/academic-affairs/programs/${res.data.programId}`)
      } else toast.error(res.message || '创建失败')
    },
    async load() {
      const revision = ++this.requestRevision
      this.loading = true; this.error = ''; this.rows = []; this.allRows = []; this.summary = null
      try {
        const res = this.isAcademicTeacher
          ? await academicAffairsApi.getPrograms({ page: 1, pageSize: 500 })
          : await programQualityApi.governanceSummary()
        if (revision !== this.requestRevision) return
        if (res.code === 0) {
          if (this.isAcademicTeacher) {
            this.summary = null
            this.allRows = res.data?.list || []
          } else {
            this.summary = res.data
            this.allRows = res.data.items || []
          }
          this.applyPage()
        } else this.error = res.message || (this.isAcademicTeacher ? '正式培养方案读取失败，请重试' : '方案及质量数据读取失败，请重试')
      } catch(error) { if (revision === this.requestRevision) this.error = error?.message || '方案读取失败，请重试' }
      finally { if (revision === this.requestRevision) this.loading = false }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-summary-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }
.aa-summary-card { padding: 14px 16px; border: 1px solid var(--border-200, #e5e7eb); border-radius: 8px; background: var(--bg-white, #fff); }
.aa-summary-card strong, .aa-summary-card span, .aa-summary-card small { display: block; }
.aa-summary-card strong { font-size: 24px; color: var(--text-900, #1f2937); }
.aa-summary-card span { margin-bottom: 6px; font-size: 13px; color: var(--text-500, #64748b); }
.aa-summary-card small { margin-top: 6px; font-size: 12px; color: var(--text-500, #64748b); }
.aa-summary-card.is-ok { border-color: var(--success-200, #a7f3d0); }
.aa-summary-card.is-warning { border-color: var(--warning-200, #fde68a); }
.aa-summary-card.is-danger { border-color: var(--danger-200, #fecaca); }
.aa-actions { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-top: 10px; }
.aa-cal-form { display: flex; flex-wrap: wrap; gap: 14px; align-items: flex-end; }
.aa-cal-form__item { display: inline-flex; flex-direction: column; gap: 6px; font-size: 13px; color: var(--text-700, #4e5969); }
.aa-cal-form__item--grow { flex: 1; min-width: 240px; }
.aa-input { height: 34px; padding: 0 10px; border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px; background: var(--bg-white, #fff); color: var(--text-900, #1f2329); font-size: 13px; box-sizing: border-box; }
.aa-input--sm { width: 120px; }
.aa-list-card { overflow: hidden; border: 1px solid var(--border-200, #e5e7eb); border-radius: 10px; background: var(--bg-white, #fff); }
.aa-list-card__head { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 15px 16px; border-bottom: 1px solid var(--border-200, #e5e7eb); }
.aa-list-card__head strong { color: var(--text-900, #1f2937); }
.aa-list-card__head span { font-size: 12px; color: var(--text-500, #64748b); }
.aa-list-card__filters { margin: 0; padding: 12px 16px; }
.aa-list-card :deep(.data-table) { border: 0; border-radius: 0; }
.is-danger-text { color: var(--danger-600, #dc2626); }
@media (max-width: 900px) { .aa-summary-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
</style>
