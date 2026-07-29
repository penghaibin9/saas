<template>
  <ModulePageShell
    title="开课差异"
    subtitle="对照生效培养方案应开课程与本学期教学任务，先处理漏开、重复、多开、学分和学时异常"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton @click="$router.push('/admin/academic-affairs/programs')">培养方案</AppButton>
      <AppButton variant="primary" @click="$router.push('/admin/academic-affairs/teaching-tasks')">教学任务</AppButton>
    </template>

    <div class="mp-stack">
      <AppInlineAlert
        type="info"
        title="本页不建立第二套教学计划"
        description="差异由已发布/已启用/已冻结的生效培养方案、专业年级/班级绑定和本学期教学任务实时计算；修复动作回到培养方案或教学任务正式页面完成。"
      />

      <AppSectionCard title="检查范围">
        <div class="aa-filter-row">
          <label>
            学期
            <select v-model="filters.termId" class="aa-select" @change="load">
              <option value="">请选择学期</option>
              <option v-for="term in terms" :key="term.termId" :value="term.termId">
                {{ term.termName || `${term.yearCode}-${term.termNo}` }}
              </option>
            </select>
          </label>
          <label>
            专业
            <AppMajorPicker v-model="filters.majorId" placeholder="全部专业" />
          </label>
          <label>
            年级
            <input v-model.trim="filters.gradeYear" class="aa-input" placeholder="全部年级" maxlength="4" />
          </label>
          <label>
            差异类型
            <select v-model="filters.status" class="aa-select">
              <option value="">全部</option>
              <option v-for="item in statusOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
            </select>
          </label>
          <AppButton variant="primary" :disabled="!filters.termId" :loading="loading" @click="load">重新检查</AppButton>
        </div>
      </AppSectionCard>

      <AppInlineAlert
        v-if="summary"
        :type="summary.canGenerateOrConfirm ? 'success' : 'warning'"
        :title="summary.conclusion"
        :description="summary.canGenerateOrConfirm ? '当前开课基础数据可继续生成或确认教学任务。' : '先处理阻断差异，再生成、确认或冻结本学期教学任务。'"
      />

      <div v-if="summary" class="aa-summary-grid">
        <button class="aa-summary-card" @click="setStatus('')"><strong>{{ summary.total }}</strong><span>全部应开/实开项</span></button>
        <button class="aa-summary-card is-ok" @click="setStatus('READY')"><strong>{{ summary.ready }}</strong><span>一致</span></button>
        <button class="aa-summary-card is-danger" @click="setStatus('MISSING_TASK')"><strong>{{ summary.missingTask }}</strong><span>漏开</span></button>
        <button class="aa-summary-card is-danger" @click="setStatus('DUPLICATE_TASK')"><strong>{{ summary.duplicateTask }}</strong><span>重复任务</span></button>
        <button class="aa-summary-card is-warning" @click="setStatus('OVER_OPENED')"><strong>{{ summary.overOpened || 0 }}</strong><span>多开</span></button>
        <button class="aa-summary-card is-warning" @click="setStatus('NO_TEACHER')"><strong>{{ summary.noTeacher }}</strong><span>缺教师</span></button>
        <button class="aa-summary-card is-warning" @click="setStatus('CREDIT_MISMATCH')"><strong>{{ summary.creditMismatch }}</strong><span>学分不一致</span></button>
        <button class="aa-summary-card is-warning" @click="setStatus('HOURS_MISMATCH')"><strong>{{ summary.hoursMismatch || 0 }}</strong><span>学时不一致</span></button>
        <button class="aa-summary-card is-danger" @click="setStatus('TERM_UNRESOLVED')"><strong>{{ summary.unresolved }}</strong><span>数据未解析</span></button>
      </div>

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState
        v-else-if="!rows.length"
        title="当前筛选下没有差异记录"
        :description="filters.status ? '切换差异类型查看其它结果' : '尚无方案应开记录，或当前学期没有匹配到有效方案绑定'"
      />
      <DataTable v-else :columns="columns" :rows="rows" row-key="key">
        <template #cell-program="{ row }">
          <div class="mp-cell-main">{{ row.programName || '非方案应开任务' }}</div>
          <div class="mp-cell-sub">{{ row.gradeYear ? `${row.gradeYear}级` : '—' }} · 第{{ row.planTermNo || '—' }}学期</div>
        </template>
        <template #cell-class="{ row }">
          <div class="mp-cell-main">{{ row.className || '—' }}</div>
          <div class="mp-cell-sub">ID {{ row.classId || '—' }}</div>
        </template>
        <template #cell-course="{ row }">
          <div class="mp-cell-main">{{ row.courseName || '—' }}</div>
          <div class="mp-cell-sub">{{ row.courseCode || row.courseId || '—' }}</div>
        </template>
        <template #cell-status="{ row }">
          <AppStatusTag :type="statusType(row.status)" :label="statusLabel(row.status)" dot />
        </template>
        <template #cell-conclusion="{ row }">
          <div class="mp-cell-main">{{ row.message }}</div>
          <div v-if="row.teacherName" class="mp-cell-sub">教师：{{ row.teacherName }}</div>
          <div v-if="row.responsibility" class="mp-cell-sub">责任对象：{{ responsibilityLabel(row.responsibility) }}</div>
        </template>
        <template #cell-actions="{ row }">
          <button v-if="row.fixRoute" class="mp-link" @click="$router.push(row.fixRoute)">去处理</button>
          <button v-else-if="row.programId" class="mp-link" @click="openProgram(row)">处理方案</button>
          <button v-else-if="row.taskIds?.length" class="mp-link" @click="$router.push('/admin/academic-affairs/teaching-tasks')">处理任务</button>
        </template>
      </DataTable>
    </div>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppInlineAlert, AppMajorPicker, AppSectionCard, AppStatusTag } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { programQualityApi } from '@/modules/academicAffairs/api/program-quality.api'

const LABELS = {
  READY: '一致', MISSING_TASK: '漏开', DUPLICATE_TASK: '重复任务', OVER_OPENED: '多开',
  NO_TEACHER: '缺教师', CREDIT_MISMATCH: '学分不一致', HOURS_MISMATCH: '学时不一致',
  COURSE_UNRESOLVED: '课程未解析', TERM_UNRESOLVED: '学期未解析', NO_CLASS: '未匹配班级'
}
const RESPONSIBILITY = { PROGRAM_BINDING: '方案绑定', PROGRAM_COURSE: '方案课程', TEACHING_TASK: '教学任务' }

export default {
  name: 'AaOpeningPlanDiffView',
  components: { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppButton, AppInlineAlert, AppMajorPicker, AppSectionCard, AppStatusTag },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: false,
      error: '',
      terms: [],
      rows: [],
      summary: null,
      filters: { termId: '', majorId: '', gradeYear: '', status: '' },
      statusOptions: Object.entries(LABELS).map(([value, label]) => ({ value, label })),
      columns: [
        { key: 'program', title: '方案' },
        { key: 'class', title: '行政班' },
        { key: 'course', title: '课程' },
        { key: 'status', title: '结论', width: '130px' },
        { key: 'conclusion', title: '原因与责任' },
        { key: 'actions', title: '处理', width: '100px' }
      ]
    }
  },
  async created() {
    await this.loadTerms()
    if (this.filters.termId) await this.load()
  },
  methods: {
    statusLabel(value) { return LABELS[value] || value || '—' },
    responsibilityLabel(value) { return RESPONSIBILITY[value] || value || '—' },
    statusType(value) {
      if (value === 'READY') return 'success'
      if (['MISSING_TASK', 'DUPLICATE_TASK', 'COURSE_UNRESOLVED', 'TERM_UNRESOLVED', 'NO_CLASS', 'OVER_OPENED'].includes(value)) return 'danger'
      return 'warning'
    },
    async loadTerms() {
      const [termsRes, currentRes] = await Promise.all([
        academicAffairsApi.getTerms({ page: 1, pageSize: 50 }),
        academicAffairsApi.getCurrentTerm()
      ])
      if (termsRes.code === 0) this.terms = termsRes.data.list || []
      if (currentRes.code === 0 && currentRes.data?.termId) this.filters.termId = String(currentRes.data.termId)
      else if (this.terms[0]?.termId) this.filters.termId = String(this.terms[0].termId)
    },
    setStatus(value) {
      this.filters.status = value
      this.load()
    },
    openProgram(row) {
      this.$router.push(`/admin/academic-affairs/programs/${row.programId}`)
    },
    async load() {
      if (!this.filters.termId || this.loading) return
      this.loading = true
      this.error = ''
      const res = await programQualityApi.openingDifferences({
        termId: this.filters.termId,
        majorId: this.filters.majorId || undefined,
        gradeYear: this.filters.gradeYear || undefined,
        status: this.filters.status || undefined
      })
      if (res.code === 0) {
        this.rows = res.data.items || []
        this.summary = res.data.summary || null
      } else {
        this.rows = []
        this.summary = null
        this.error = res.message || '开课差异检查失败'
      }
      this.loading = false
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-filter-row { display: flex; flex-wrap: wrap; align-items: flex-end; gap: 12px; }
.aa-filter-row label { display: flex; min-width: 150px; flex-direction: column; gap: 6px; font-size: 13px; color: var(--text-700, #4e5969); }
.aa-input, .aa-select { height: 34px; padding: 0 10px; border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px; background: var(--bg-white, #fff); color: var(--text-900, #1f2329); }
.aa-summary-grid { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 12px; }
.aa-summary-card { padding: 14px 16px; border: 1px solid var(--border-200, #e5e7eb); border-radius: 8px; background: var(--bg-white, #fff); text-align: left; cursor: pointer; }
.aa-summary-card strong, .aa-summary-card span { display: block; }
.aa-summary-card strong { font-size: 24px; color: var(--text-900, #1f2937); }
.aa-summary-card span { margin-top: 4px; color: var(--text-500, #64748b); font-size: 12px; }
.aa-summary-card.is-ok { border-color: var(--success-200, #a7f3d0); }
.aa-summary-card.is-warning { border-color: var(--warning-200, #fde68a); }
.aa-summary-card.is-danger { border-color: var(--danger-200, #fecaca); }
@media (max-width: 1200px) { .aa-summary-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
@media (max-width: 760px) { .aa-summary-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
</style>
