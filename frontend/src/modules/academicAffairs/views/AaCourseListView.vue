<template>
  <ModulePageShell
    title="课程库"
    subtitle="全校课程主数据 · 两级审核（学院→教务）通过后启用，方可被培养方案引用"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton variant="primary" @click="$router.push('/admin/academic-affairs/courses/new')">＋ 新建课程</AppButton>
    </template>

    <div class="mp-stack">
      <AdvancedFilter v-model="filters" :fields="filterFields" @search="search" @reset="reset" />

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" title="课程库为空" description="点击「新建课程」录入第一门课程，提交两级审核后启用" />
      <DataTable v-else :columns="columns" :rows="rows" row-key="courseId" :pagination="pagination" @page-change="onPageChange">
        <template #cell-course="{ row }">
          <div class="mp-cell-main">{{ row.courseName }}</div>
          <div class="mp-cell-sub">{{ row.courseCode }} · {{ row.credit }} 学分</div>
        </template>
        <template #cell-type="{ row }">
          <span>{{ row.categoryLabel }} · {{ row.natureLabel }}</span>
        </template>
        <template #cell-status="{ row }">
          <AppStatusTag :type="reviewStatusColor(row.status)" dot>{{ statusLabel(row.status) }}</AppStatusTag>
        </template>
        <template #cell-actions="{ row }">
          <button class="mp-link" @click="$router.push(`/admin/academic-affairs/courses/${row.courseId}`)">详情</button>
        </template>
      </DataTable>
    </div>
  </ModulePageShell>
</template>

<script>
/** 课程库列表（/admin/academic-affairs/courses）：GET /academic-affairs/courses。 */
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AdvancedFilter } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppStatusTag } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { COURSE_CATEGORY, COURSE_NATURE, REVIEW_STATUS, reviewStatusColor } from '@/modules/academicAffairs/constants/course-program'

export default {
  name: 'AaCourseListView',
  components: { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppButton, AppStatusTag, AdvancedFilter },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      COURSE_CATEGORY, COURSE_NATURE, REVIEW_STATUS,
      loading: true, error: '', rows: [],
      filters: { keyword: '', category: '', nature: '', status: '' },
      pagination: { page: 1, pageSize: 20, total: 0 },
      columns: [
        { key: 'course', title: '课程' },
        { key: 'type', title: '类别 / 性质' },
        { key: 'status', title: '状态' },
        { key: 'actions', title: '操作', width: '80px' }
      ]
    }
  },
  computed: {
    filterFields() {
      const toOptions = (dict) => Object.entries(dict).map(([value, label]) => ({ value, label }))
      return [
        { key: 'keyword', label: '关键词', type: 'text', placeholder: '课程名/编码' },
        { key: 'category', label: '类别', type: 'select', options: toOptions(COURSE_CATEGORY) },
        { key: 'nature', label: '性质', type: 'select', options: toOptions(COURSE_NATURE) },
        { key: 'status', label: '状态', type: 'select', options: toOptions(REVIEW_STATUS) }
      ]
    }
  },
  created() { this.load() },
  methods: {
    reviewStatusColor,
    statusLabel(s) { return REVIEW_STATUS[s] || s || '' },
    onPageChange(p) { this.pagination.page = p; this.load() },
    search() { this.pagination.page = 1; this.load() },
    reset() { this.filters = { keyword: '', category: '', nature: '', status: '' }; this.search() },
    async load() {
      this.loading = true
      this.error = ''
      const res = await academicAffairsApi.getCourses({
        keyword: this.filters.keyword || undefined,
        category: this.filters.category || undefined,
        nature: this.filters.nature || undefined,
        status: this.filters.status || undefined,
        page: this.pagination.page, pageSize: this.pagination.pageSize
      })
      if (res.code === 0) { this.rows = res.data.list; this.pagination.total = res.data.total }
      else { this.error = res.message }
      this.loading = false
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-filter { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
.aa-input, .aa-select { height: 32px; padding: 0 10px; border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px; background: var(--bg-white, #fff); color: var(--text-900, #1f2329); font-size: 13px; }
</style>
