<template>
  <ModulePageShell
    title="培养方案"
    subtitle="按专业年级编制课程结构 · 学分达标后两级审核发布，再绑定年级"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton variant="primary" @click="showCreate = !showCreate">＋ 新建方案</AppButton>
    </template>

    <div class="mp-stack">
      <AppSectionCard v-if="showCreate" title="新建培养方案">
        <div class="aa-cal-form">
          <label class="aa-cal-form__item aa-cal-form__item--grow">
            方案名称<input v-model.trim="draft.programName" class="aa-input" placeholder="如 软件技术2026级培养方案" maxlength="60" />
          </label>
          <label class="aa-cal-form__item">专业ID<input v-model.trim="draft.majorId" class="aa-input aa-input--sm" placeholder="选填" /></label>
          <label class="aa-cal-form__item">年级<input v-model.trim="draft.gradeYear" class="aa-input aa-input--sm" placeholder="如 2026" /></label>
          <label class="aa-cal-form__item">毕业总学分<input v-model.number="draft.totalCredits" type="number" min="0" class="aa-input aa-input--sm" /></label>
          <AppButton variant="primary" :disabled="!draft.programName" :loading="creating" @click="createProgram">创建</AppButton>
        </div>
      </AppSectionCard>

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" title="还没有培养方案" description="点击「新建方案」开始编制课程结构" />
      <DataTable v-else :columns="columns" :rows="rows" row-key="programId" :pagination="pagination" @page-change="onPageChange">
        <template #cell-program="{ row }">
          <div class="mp-cell-main">{{ row.programName }}</div>
          <div class="mp-cell-sub">年级 {{ row.gradeYear || '—' }} · v{{ row.version }}</div>
        </template>
        <template #cell-credits="{ row }">{{ row.totalCredits ?? '—' }}</template>
        <template #cell-status="{ row }">
          <AppStatusTag :type="reviewStatusColor(row.status)" dot>{{ statusLabel(row.status) }}</AppStatusTag>
        </template>
        <template #cell-actions="{ row }">
          <button class="mp-link" @click="$router.push(`/admin/academic-affairs/programs/${row.programId}`)">编制 / 详情</button>
        </template>
      </DataTable>
    </div>
  </ModulePageShell>
</template>

<script>
/** 培养方案列表（/admin/academic-affairs/programs）：GET/POST /academic-affairs/programs。 */
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppSectionCard, AppStatusTag } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { REVIEW_STATUS, reviewStatusColor } from '@/modules/academicAffairs/constants/course-program'
import { toast } from '@/utils/toast'

export default {
  name: 'AaProgramListView',
  components: { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppButton, AppSectionCard, AppStatusTag },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true, error: '', rows: [], showCreate: false, creating: false,
      draft: { programName: '', majorId: '', gradeYear: '', totalCredits: null },
      pagination: { page: 1, pageSize: 20, total: 0 },
      columns: [
        { key: 'program', title: '方案' },
        { key: 'credits', title: '毕业总学分' },
        { key: 'status', title: '状态' },
        { key: 'actions', title: '操作', width: '110px' }
      ]
    }
  },
  created() { this.load() },
  methods: {
    reviewStatusColor,
    statusLabel(s) { return REVIEW_STATUS[s] || s || '' },
    onPageChange(p) { this.pagination.page = p; this.load() },
    async createProgram() {
      if (this.creating || !this.draft.programName) return
      this.creating = true
      const res = await academicAffairsApi.createProgram({
        programName: this.draft.programName,
        majorId: this.draft.majorId || undefined,
        gradeYear: this.draft.gradeYear || undefined,
        totalCredits: this.draft.totalCredits || undefined,
        requirement: {}
      })
      this.creating = false
      if (res.code === 0) {
        toast.success('方案已创建')
        this.$router.push(`/admin/academic-affairs/programs/${res.data.programId}`)
      } else {
        toast.error(res.message || '创建失败')
      }
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await academicAffairsApi.getPrograms({ page: this.pagination.page, pageSize: this.pagination.pageSize })
      if (res.code === 0) { this.rows = res.data.list; this.pagination.total = res.data.total }
      else { this.error = res.message }
      this.loading = false
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-cal-form { display: flex; flex-wrap: wrap; gap: 14px; align-items: flex-end; }
.aa-cal-form__item { display: inline-flex; flex-direction: column; gap: 6px; font-size: 13px; color: var(--text-700, #4e5969); }
.aa-cal-form__item--grow { flex: 1; min-width: 240px; }
.aa-input { height: 34px; padding: 0 10px; border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px; background: var(--bg-white, #fff); color: var(--text-900, #1f2329); font-size: 13px; box-sizing: border-box; }
.aa-input--sm { width: 120px; }
</style>
