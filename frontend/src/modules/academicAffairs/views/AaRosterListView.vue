<template>
  <ModulePageShell
    :title="pageTitle"
    subtitle="在籍学生主档（只读脱敏）· 可从这里对某个学生发起学籍异动"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="mp-stack">
      <AdvancedFilter v-model="filters" :fields="filterFields" @search="search" @reset="reset" />

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" title="无在籍学生" description="当前数据范围内没有匹配的学生主档" />
      <DataTable
        v-else
        :columns="columns"
        :rows="rows"
        row-key="studentId"
        :pagination="pagination"
        @page-change="onPageChange"
      >
        <template #cell-student="{ row }">
          <div class="mp-cell-main">{{ row.realName }}</div>
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
          <button class="mp-link" :disabled="!row.enrolled" @click="goChange(row)">发起异动</button>
        </template>
      </DataTable>
      <p class="mp-note">身份证等敏感字段出口一律脱敏，页面不反解。学籍详情/导入导出为后续波次交付。</p>
    </div>
  </ModulePageShell>
</template>

<script>
/** 学籍名册（/admin/academic-affairs/roster）：GET /academic-affairs/roster（只读脱敏，无独立详情端点）。 */
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AdvancedFilter } from '@/components/business'
import { AppStatusTag } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'

const STATUS_LABEL = {
  REGISTERED: '在籍注册', PENDING_REGISTER: '待注册', SUSPENDED: '休学',
  WITHDRAWN: '退学', RETAINED: '留级', GRADUATED: '毕业'
}

/** 学籍管理分类视图叶子（休学学生/退学学生/保留学籍，见 navPlan aa-student-status）深链标题；
 *  「保留学籍」用词对齐三级菜单命名，与 STATUS_LABEL 的「留级」标签展示各自独立、互不影响。 */
const CATEGORY_TITLE = { SUSPENDED: '休学学生', WITHDRAWN: '退学学生', RETAINED: '保留学籍' }

export default {
  name: 'AaRosterListView',
  components: { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppStatusTag, AdvancedFilter },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      STATUS_LABEL,
      loading: true,
      error: '',
      rows: [],
      // keyword/status 支持从 query 预填（供「异动生效」等页按学号/姓名带入检索；
      // 供「休学学生/退学学生/保留学籍」等学籍管理分类视图叶子按状态预筛，见 navPlan aa-student-status）
      filters: { keyword: this.$route.query.keyword || '', status: this.$route.query.status || '' },
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
    // 「休学学生/退学学生/保留学籍」等分类视图叶子按 ?status= 深链进入时，标题随之切换，
    // 避免用户误以为落在通用「学籍名册」（navPlan aa-student-status 分类视图口径）。
    pageTitle() {
      const q = this.$route.query.status
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
  methods: {
    statusLabel(s) {
      return STATUS_LABEL[s] || s || ''
    },
    goChange(row) {
      this.$router.push({
        path: '/admin/academic-affairs/status-changes/new',
        query: { studentId: row.studentId, name: row.realName }
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
      this.filters = { keyword: '', status: '' }
      this.pagination.page = 1
      this.load()
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await academicAffairsApi.getRoster({
        keyword: this.filters.keyword || undefined,
        status: this.filters.status || undefined,
        page: this.pagination.page,
        pageSize: this.pagination.pageSize
      })
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
.aa-filter { display: flex; gap: 16px; align-items: center; flex-wrap: wrap; }
.aa-filter__item { display: inline-flex; align-items: center; gap: 8px; font-size: 13px; color: var(--text-700, #4e5969); }
.aa-input, .aa-select {
  height: 32px; padding: 0 10px;
  border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px;
  background: var(--bg-white, #fff); color: var(--text-900, #1f2329); font-size: 13px;
}
.aa-mask { font-family: var(--font-mono, monospace); color: var(--text-500, #646a73); }
</style>
