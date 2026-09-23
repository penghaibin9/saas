<template>
  <ModulePageShell
:title="isAcademicTeacher ? '课程库' : '课程列表'"
    :subtitle="isAcademicTeacher ? '仅查看已经正式启用的课程版本、学分与学时信息' : '课程身份按代码与版本确定，不按名称猜'"
    show-subtitle-in-concise
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton v-if="!isAcademicTeacher" @click="downloadCourseTemplate">下载导入模板</AppButton>
      <AppButton v-if="hasPermission('academicAffairs.course.manage')" @click="importVisible = true">批量导入</AppButton>
      <AppButton v-if="hasPermission('academicAffairs.course.manage')" variant="primary" @click="$router.push('/admin/academic-affairs/courses/new')">＋ 新建课程</AppButton>
    </template>

    <div class="mp-stack">
      <div class="aac-list-card">
        <div class="aac-list-card__head">
          <strong>课程库 · 稳定课程身份</strong>
          <span>共 {{ pagination.total }} 个课程版本</span>
        </div>
        <form class="aac-filter" role="search" @submit.prevent="search">
          <input v-model.trim="filters.keyword" class="aac-input" aria-label="搜索稳定课程版本" placeholder="搜索稳定课程版本" />
          <AppButton type="submit">查询</AppButton>
          <AppButton variant="ghost" @click="reset">清空</AppButton>
        </form>
        <ErrorState v-if="error" :description="error" @retry="load" />
        <LoadingState v-else-if="loading" />
        <EmptyState v-else-if="!rows.length" title="课程库为空" :description="isAcademicTeacher ? '当前没有已正式启用的课程，请联系教务管理人员。' : '点击「新建课程」录入第一门课程，提交两级审核后启用'" />
        <DataTable v-else :columns="columns" :rows="rows" row-key="courseId" :pagination="pagination" @page-change="onPageChange">
        <template #cell-code="{ row }">
          <div class="mp-cell-main">{{ row.courseCode }}</div>
          <div class="mp-cell-sub">v{{ row.version }}</div>
        </template>
        <template #cell-name="{ row }">
          <div class="mp-cell-main">{{ row.courseName }}</div>
          <div class="mp-cell-sub">正式课程 #{{ row.courseId }}</div>
        </template>
        <template #cell-nature="{ row }">
          <span>{{ row.natureLabel || '性质待核验' }}</span>
          <div class="mp-cell-sub">{{ row.categoryLabel || '类别待核验' }}</div>
        </template>
        <template #cell-creditHours="{ row }">
          <div class="mp-cell-main">{{ row.credit ?? '—' }} 学分</div>
          <div class="mp-cell-sub">{{ row.hoursTotal ?? '—' }} 学时</div>
        </template>
        <template #cell-status="{ row }">
          <AppStatusTag :type="reviewStatusColor(row.status)" dot>{{ statusLabel(row.status) }}</AppStatusTag>
        </template>
        <template #cell-actions="{ row }">
          <button class="mp-link" @click="$router.push(`/admin/academic-affairs/courses/${row.courseId}`)">课程档案</button>
        </template>
      </DataTable>
      </div>
    </div>

    <AaAuthoritativeImportDrawer
      v-model:visible="importVisible"
      title="课程库权威 XLSX 导入"
      template-name="课程库权威导入模板.xlsx"
      :preview-fields="['courseCode', 'courseName', 'version', 'credit', 'category', 'nature']"
      :download-template-fn="academicFileExchangeApi.downloadCourseCatalogTemplate"
      :upload-fn="academicFileExchangeApi.uploadCourseCatalogImport"
      @imported="onCourseImported"
    />
  </ModulePageShell>
</template>

<script>
/** 课程库列表（/admin/academic-affairs/courses）：GET /academic-affairs/courses。 */
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppStatusTag } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { academicFileExchangeApi } from '@/modules/academicAffairs/api/academic-file-exchange.api'
import AaAuthoritativeImportDrawer from '@/modules/academicAffairs/components/AaAuthoritativeImportDrawer.vue'
import { matchPermission } from '@/config/navPlan'
import { toast } from '@/utils/toast'
import { COURSE_CATEGORY, COURSE_NATURE, REVIEW_STATUS, reviewStatusColor } from '@/modules/academicAffairs/constants/course-program'

export default {
  name: 'AaCourseListView',
  components: { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppButton, AppStatusTag, AaAuthoritativeImportDrawer },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      COURSE_CATEGORY, COURSE_NATURE, REVIEW_STATUS, academicFileExchangeApi,
      loading: true, error: '', rows: [], importVisible: false, requestRevision: 0,
      filters: { keyword: '', category: '', nature: '', status: '' },
      pagination: { page: 1, pageSize: 20, total: 0 },
      columns: [
        { key: 'code', title: '课程代码', width: '155px' },
        { key: 'name', title: '课程名称' },
        { key: 'nature', title: '性质', width: '155px' },
        { key: 'creditHours', title: '学分学时', width: '145px' },
        { key: 'status', title: '启用状态', width: '130px' },
        { key: 'actions', title: '办理入口', width: '100px' }
      ]
    }
  },
  computed: {
    isAcademicTeacher() {
      return String(this.ctx?.currentRole?.roleCode || this.ctx?.currentRole?.roleType || '').toUpperCase() === 'ACADEMIC_TEACHER'
    }
  },
  beforeUnmount() { this.requestRevision++ },
  created() { this.load() },
  methods: {
    hasPermission(key) { return matchPermission(this.ctx.permissionPatterns || [], key) },
    reviewStatusColor,
    statusLabel(s) { return REVIEW_STATUS[s] || (s ? '状态待确认' : '') },
    onPageChange(p) { this.pagination.page = p; this.load() },
    search() { this.pagination.page = 1; this.load() },
    reset() { this.filters = { keyword: '', category: '', nature: '', status: '' }; this.search() },
    async downloadCourseTemplate() {
      const res = await academicFileExchangeApi.downloadCourseCatalogTemplate()
      if (res.code !== 0) { toast.error(res.message || '课程导入模板下载失败'); return }
      const url = URL.createObjectURL(res.data)
      const a = document.createElement('a'); a.href = url; a.download = '课程库权威导入模板.xlsx'; a.click(); URL.revokeObjectURL(url)
    },
    async onCourseImported() { toast.success('课程库权威导入已完成'); this.importVisible = false; await this.load() },
    async load() {
      const revision = ++this.requestRevision
      this.loading = true
      this.error = ''
      this.rows = []
      try {
        const res = await academicAffairsApi.getCourses({
          keyword: this.filters.keyword || undefined,
          category: this.filters.category || undefined,
          nature: this.filters.nature || undefined,
          status: this.filters.status || undefined,
          page: this.pagination.page, pageSize: this.pagination.pageSize
        })
        if (revision !== this.requestRevision) return
        if (res.code === 0) { this.rows = res.data.list; this.pagination.total = res.data.total }
        else { this.error = res.message || '课程列表读取失败，请重试' }
      } catch (error) {
        if (revision === this.requestRevision) this.error = error?.message || '课程列表读取失败，请重试'
      } finally {
        if (revision === this.requestRevision) this.loading = false
      }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aac-list-card { overflow: hidden; border: 1px solid var(--border-200, #e5e7eb); border-radius: 10px; background: var(--bg-white, #fff); }
.aac-list-card__head { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 15px 16px; border-bottom: 1px solid var(--border-200, #e5e7eb); }
.aac-list-card__head strong { color: var(--text-900, #1f2937); }
.aac-list-card__head span { font-size: 12px; color: var(--text-500, #64748b); }
.aac-filter { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; padding: 12px 16px; }
.aac-input { width: 280px; max-width: 100%; height: 34px; padding: 0 10px; border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px; background: var(--bg-white, #fff); color: var(--text-900, #1f2329); font-size: 13px; }
.aac-list-card :deep(.data-table) { border: 0; border-radius: 0; }
</style>
