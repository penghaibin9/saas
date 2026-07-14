<template>
  <ModulePageShell
    title="课程库"
    subtitle="全校课程主数据 · 两级审核（学院→教务）通过后启用，方可被培养方案引用"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <button class="mp-btn mp-btn--primary" @click="$router.push('/admin/academic-affairs/courses/new')">＋ 新建课程</button>
    </template>

    <div class="mp-stack">
      <div class="aa-filter">
        <input v-model.trim="filters.keyword" class="aa-input" placeholder="课程名/编码" @keyup.enter="search" />
        <select v-model="filters.category" class="aa-select" @change="search">
          <option value="">全部类别</option>
          <option v-for="(l, v) in COURSE_CATEGORY" :key="v" :value="v">{{ l }}</option>
        </select>
        <select v-model="filters.nature" class="aa-select" @change="search">
          <option value="">全部性质</option>
          <option v-for="(l, v) in COURSE_NATURE" :key="v" :value="v">{{ l }}</option>
        </select>
        <select v-model="filters.status" class="aa-select" @change="search">
          <option value="">全部状态</option>
          <option v-for="(l, v) in REVIEW_STATUS" :key="v" :value="v">{{ l }}</option>
        </select>
        <button class="mp-btn" @click="search">查询</button>
      </div>

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
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppStatusTag } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { COURSE_CATEGORY, COURSE_NATURE, REVIEW_STATUS, reviewStatusColor } from '@/modules/academicAffairs/constants/course-program'

export default {
  name: 'AaCourseListView',
  components: { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppStatusTag },
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
  created() { this.load() },
  methods: {
    reviewStatusColor,
    statusLabel(s) { return REVIEW_STATUS[s] || s || '' },
    onPageChange(p) { this.pagination.page = p; this.load() },
    search() { this.pagination.page = 1; this.load() },
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
