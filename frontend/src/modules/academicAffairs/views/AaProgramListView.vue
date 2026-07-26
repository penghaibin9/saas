<template>
  <ModulePageShell
    title="培养方案治理"
    subtitle="按专业年级检查方案完整性、结构阻断与开课准备情况"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton @click="$router.push('/admin/academic-affairs/programs/opening-plan')">开课差异</AppButton>
      <AppButton variant="primary" @click="showCreate = !showCreate">＋ 新建方案</AppButton>
    </template>

    <div class="mp-stack">
      <div v-if="summary" class="aa-summary-grid">
        <div class="aa-summary-card"><strong>{{ summary.totalPrograms }}</strong><span>方案总数</span></div>
        <div class="aa-summary-card is-ok"><strong>{{ summary.readyPrograms }}</strong><span>校验可提交</span></div>
        <div class="aa-summary-card is-danger"><strong>{{ summary.blockedPrograms }}</strong><span>存在阻断</span></div>
        <div class="aa-summary-card is-warning"><strong>{{ summary.missingMajor + summary.missingGrade }}</strong><span>缺专业/年级</span></div>
      </div>

      <AppInlineAlert
        v-if="summary?.blockedPrograms"
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

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" title="还没有培养方案" description="点击「新建方案」开始编制课程、学分结构、毕业要求和实践环节" />
      <DataTable v-else :columns="columns" :rows="rows" row-key="programId" :pagination="pagination" @page-change="onPageChange">
        <template #cell-program="{ row }">
          <div class="mp-cell-main">{{ row.programName }}</div>
          <div class="mp-cell-sub">{{ row.gradeYear ? `${row.gradeYear}级` : '未设置年级' }} · v{{ row.version }} · {{ row.courseCount ?? '—' }}门课程</div>
        </template>
        <template #cell-credits="{ row }">
          <div class="mp-cell-main">{{ row.creditSum ?? '—' }} / {{ row.totalCredits ?? '—' }}</div>
          <div class="mp-cell-sub">已排 / 毕业要求</div>
        </template>
        <template #cell-quality="{ row }">
          <AppStatusTag
            :type="row.canSubmit ? 'success' : 'danger'"
            :label="row.canSubmit ? '校验通过' : `${row.blockerCount || 0}项阻断`"
            dot
          />
          <div v-if="row.warningCount" class="mp-cell-sub">{{ row.warningCount }}项提醒</div>
        </template>
        <template #cell-status="{ row }">
          <AppStatusTag :type="reviewStatusColor(row.status)" :label="statusLabel(row.status)" dot />
        </template>
        <template #cell-actions="{ row }">
          <button class="mp-link" @click="$router.push(`/admin/academic-affairs/programs/${row.programId}`)">编制 / 校验</button>
        </template>
      </DataTable>
    </div>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppInlineAlert, AppSectionCard, AppStatusTag, AppMajorPicker } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { programQualityApi } from '@/modules/academicAffairs/api/program-quality.api'
import { REVIEW_STATUS, reviewStatusColor } from '@/modules/academicAffairs/constants/course-program'
import { toast } from '@/utils/toast'

export default {
  name: 'AaProgramListView',
  components: { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppButton, AppInlineAlert, AppSectionCard, AppStatusTag, AppMajorPicker },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      rows: [],
      allRows: [],
      summary: null,
      showCreate: false,
      creating: false,
      draft: { programName: '', majorId: '', gradeYear: '', totalCredits: null },
      pagination: { page: 1, pageSize: 20, total: 0 },
      columns: [
        { key: 'program', title: '方案' },
        { key: 'credits', title: '学分结构', width: '150px' },
        { key: 'quality', title: '质量结论', width: '150px' },
        { key: 'status', title: '流程状态', width: '130px' },
        { key: 'actions', title: '操作', width: '120px' }
      ]
    }
  },
  computed: {
    canCreate() {
      return Boolean(
        this.draft.programName && this.draft.majorId && /^\d{4}$/.test(this.draft.gradeYear) && Number(this.draft.totalCredits) > 0
      )
    }
  },
  created() { this.load() },
  methods: {
    reviewStatusColor,
    statusLabel(value) { return REVIEW_STATUS[value] || value || '' },
    applyPage() {
      const start = (this.pagination.page - 1) * this.pagination.pageSize
      this.rows = this.allRows.slice(start, start + this.pagination.pageSize)
      this.pagination.total = this.allRows.length
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
      this.loading = true
      this.error = ''
      const qualityRes = await programQualityApi.governanceSummary()
      if (qualityRes.code === 0) {
        this.summary = qualityRes.data
        this.allRows = qualityRes.data.items || []
        this.applyPage()
      } else {
        const fallback = await academicAffairsApi.getPrograms({ page: 1, pageSize: 200 })
        if (fallback.code === 0) {
          this.summary = null
          this.allRows = fallback.data.list || []
          this.applyPage()
        } else this.error = qualityRes.message || fallback.message || '加载培养方案失败'
      }
      this.loading = false
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-summary-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }
.aa-summary-card { padding: 14px 16px; border: 1px solid var(--border-200, #e5e7eb); border-radius: 8px; background: var(--bg-white, #fff); }
.aa-summary-card strong, .aa-summary-card span { display: block; }
.aa-summary-card strong { font-size: 24px; color: var(--text-900, #1f2937); }
.aa-summary-card span { margin-top: 4px; font-size: 12px; color: var(--text-500, #64748b); }
.aa-summary-card.is-ok { border-color: var(--success-200, #a7f3d0); }
.aa-summary-card.is-warning { border-color: var(--warning-200, #fde68a); }
.aa-summary-card.is-danger { border-color: var(--danger-200, #fecaca); }
.aa-cal-form { display: flex; flex-wrap: wrap; gap: 14px; align-items: flex-end; }
.aa-cal-form__item { display: inline-flex; flex-direction: column; gap: 6px; font-size: 13px; color: var(--text-700, #4e5969); }
.aa-cal-form__item--grow { flex: 1; min-width: 240px; }
.aa-input { height: 34px; padding: 0 10px; border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px; background: var(--bg-white, #fff); color: var(--text-900, #1f2329); font-size: 13px; box-sizing: border-box; }
.aa-input--sm { width: 120px; }
@media (max-width: 900px) { .aa-summary-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
</style>
