<template>
  <ModulePageShell
    class="aa-foundation-workspace"
    :title="pageTitle"
    subtitle="按姓名、学号或学籍状态查找学生，进入档案查看详情与办理记录。"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="mp-stack">
      <AdvancedFilter v-model="filters" :fields="filterFields" @search="search" @reset="reset" />

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" title="没有符合条件的学生" description="可调整姓名、学号或学籍状态后重试。" />
      <DataTable
        v-else
        :columns="columns"
        :rows="rows"
        row-key="studentId"
        :pagination="pagination"
        @page-change="onPageChange"
      >
        <template #cell-student="{ row }">
          <button class="mp-link aa-student-name" type="button" @click="goDetail(row)">{{ row.realName || '查看学生档案' }}</button>
          <div class="mp-cell-sub">学号 {{ row.studentNo }}</div>
        </template>
        <template #cell-idCard="{ row }">
          <span class="aa-mask">{{ row.idCardMasked || '—' }}</span>
        </template>
        <template #cell-status="{ row }">
          <AppStatusTag :status="row.studentStatus" dot>{{ statusLabel(row.studentStatus) }}</AppStatusTag>
        </template>
        <template #cell-enrolled="{ row }">
          <span :style="row.enrolled ? 'color:var(--success-600,#16a34a)' : 'color:var(--text-400,#8a9099)'">
            {{ row.enrolled ? '在籍' : '非在籍' }}
          </span>
        </template>
        <template #cell-actions="{ row }">
          <button v-if="canApplyChange && (row.enrolled || canResume(row))" class="mp-link" type="button" @click="goChange(row)">{{ canResume(row) ? '办理复学' : '发起异动' }}</button>
          <button v-else class="mp-link" type="button" @click="goDetail(row)">查看档案</button>
        </template>
      </DataTable>
      <p class="mp-note">列表按当前数据范围展示，证件号默认脱敏。点击学生姓名可查看学籍档案。</p>
    </div>
  </ModulePageShell>
</template>

<script>
/** 名册和分类深链共用正式 roster 查询，档案读取独立详情端点。 */
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AdvancedFilter } from '@/components/business'
import { AppStatusTag } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { matchPermission } from '@/config/navPlan'
import { ACADEMIC_STUDENT_STATUS_LABELS as STATUS_LABEL } from '@/modules/academicAffairs/config/academicStudentLabels'

const CATEGORY_TITLE = { SUSPENDED: '休学学生', WITHDRAWN: '退学学生', PRESERVED: '保留学籍', RETAINED: '留级学生' }

export default {
  name: 'AaRosterListView',
  components: { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppStatusTag, AdvancedFilter },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      STATUS_LABEL,
      loading: true,
      requestVersion: 0,
      error: '',
      rows: [],
      // keyword/status 支持从 query 预填（供「异动生效」等页按学号/姓名带入检索；
      // 供「休学学生/退学学生/保留学籍」等学籍管理分类视图叶子按状态预筛，见 navPlan aa-student-status）
      filters: { keyword: this.$route.query.keyword || '', status: this.$route.query.status || '' },
      appliedStatus: this.$route.query.status || '',
      pagination: { page: 1, pageSize: 20, total: 0 },
      columns: [
        { key: 'student', title: '学生' },
        { key: 'className', title: '班级' },
        { key: 'idCard', title: '身份证（脱敏）' },
        { key: 'status', title: '学籍状态' },
        { key: 'enrolled', title: '是否在籍' },
        { key: 'actions', title: '操作', width: '90px' }
      ]
    }
  },
  computed: {
    canApplyChange() { return matchPermission(this.ctx.permissionPatterns || [], 'academicAffairs.statusChange.apply') },
    // 「休学学生/退学学生/保留学籍」等分类视图叶子按 ?status= 深链进入时，标题随之切换，
    // 避免用户误以为落在通用「学籍名册」（navPlan aa-student-status 分类视图口径）。
    pageTitle() {
      const q = this.appliedStatus
      return (q && CATEGORY_TITLE[q]) || '学籍名册'
    },
    filterFields() {
      return [
        { key: 'keyword', label: '关键字', type: 'text', placeholder: '姓名 / 学号' },
        {
          key: 'status',
          label: '学籍状态',
          type: 'select',
          placeholder: '全部',
          options: Object.entries(STATUS_LABEL).map(([value, label]) => ({ value, label }))
        }
      ]
    }
  },
  created() {
    this.load()
  },
  watch: {
    '$route.query': {
      handler(query) {
        this.filters = { keyword: query.keyword || '', status: query.status || '' }
        this.search()
      },
      deep: true
    }
  },
  methods: {
    goDetail(row) { this.$router.push({ name: 'aa-roster-detail', params: { studentId: row.studentId } }) },
    canResume(row) { return ['SUSPENDED', 'PRESERVED'].includes(row.studentStatus) },
    statusLabel(s) {
      return STATUS_LABEL[s] || (s ? '状态待确认' : '')
    },
    goChange(row) {
      if (!this.canApplyChange || (!row.enrolled && !this.canResume(row))) return
      this.$router.push({
        path: '/admin/academic-affairs/status-changes/new',
        query: { studentId: row.studentId, name: row.realName, ...(this.canResume(row) ? { type: 'RESUME' } : {}) }
      })
    },
    onPageChange(page) {
      this.pagination.page = page
      this.load()
    },
    search() {
      this.pagination.page = 1
      this.load()
    },
    reset() {
      this.filters = { keyword: '', status: this.$route.query.status || '' }
      this.pagination.page = 1
      this.load()
    },
    async load() {
      const version = ++this.requestVersion
      this.appliedStatus = this.filters.status
      this.loading = true
      this.error = ''
      const res = await academicAffairsApi.getRoster({
        keyword: this.filters.keyword || undefined,
        status: this.filters.status || undefined,
        page: this.pagination.page,
        pageSize: this.pagination.pageSize
      })
      if (version !== this.requestVersion) return
      if (res.code === 0) {
        this.rows = res.data.list
        this.pagination.total = res.data.total
      } else {
        this.error = res.message
      }
      this.loading = false
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
@import '../styles/foundation-workspace.css';
.aa-student-name { text-align: left; font-weight: 600; line-height: 1.7; }
.aa-filter { display: flex; gap: 16px; align-items: center; flex-wrap: wrap; }
.aa-filter__item { display: inline-flex; align-items: center; gap: 8px; font-size: 13px; color: var(--text-700, #4e5969); }
.aa-input, .aa-select {
  height: 32px; padding: 0 10px;
  border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px;
  background: var(--bg-white, #fff); color: var(--text-900, #1f2329); font-size: 13px;
}
.aa-mask { font-family: var(--font-mono, monospace); color: var(--text-500, #646a73); }
</style>
