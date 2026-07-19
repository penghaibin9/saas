<template>
  <ModulePageShell title="班级管理" subtitle="班级与辅导员 · 数据范围载体 · 人数/请假/风险实时指标"
    :role-name="roleName" :data-scope-name="scopeHint">
    <div class="mp-stack">
      <div class="flt">
        <AppSearchBox v-model="filters.keyword" placeholder="按班级名称搜索" @search="search" />
        <AppTextInput class="flt-input" v-model="filters.grade" placeholder="年级，如 2024" @keyup.enter="search" />
        <button type="button" class="mp-link" @click="search">查询</button>
        <button type="button" class="mp-link" @click="reset">重置</button>
      </div>

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" title="没有符合条件的班级" description="调整筛选条件，或联系管理员维护班级与辅导员绑定" />
      <DataTable v-else :columns="columns" :rows="rows" row-key="classId" :pagination="pagination" @page-change="onPageChange">
        <template #cell-className="{ row }">
          <div class="mp-cell-main">{{ row.className }}</div>
          <div class="mp-cell-sub">{{ row.collegeName }} · {{ row.majorName }}</div>
        </template>
        <template #cell-teacher="{ row }">
          <div class="mp-cell-main">{{ row.counselorName || '—' }}</div>
          <div class="mp-cell-sub">班主任：{{ row.headTeacherName || '—' }}</div>
        </template>
        <template #cell-riskOpen="{ row }">
          <span :class="{ 'is-warn': row.riskOpen > 0 }">{{ row.riskOpen }}</span>
        </template>
        <template #cell-actions="{ row }">
          <button type="button" class="mp-link" @click="openProfile(row)">班级画像</button>
        </template>
      </DataTable>
      <p class="mp-note">班级是全学工数据范围载体：辅导员看本人绑定班级、学院看本院、学工处看全校。点击「班级画像」查看学生名单、材料与班干部。</p>
    </div>
  </ModulePageShell>
</template>

<script>
/**
 * 班级列表（/admin/campus-service/classes）。名称+专业/学院+辅导员+实时指标（人数/在假/在办风险），
 * 数据范围裁剪；点击进入班级画像独立页。真实对接 /student-affairs/classes。
 */
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppSearchBox, AppTextInput } from '@/components/common'
import { classApi } from '@/modules/studentAffairs/api/class.api'

const COLUMNS = [
  { key: 'className', title: '班级' }, { key: 'grade', title: '年级' },
  { key: 'teacher', title: '辅导员 / 班主任' }, { key: 'studentCount', title: '人数' },
  { key: 'currentLeave', title: '当前请假' }, { key: 'riskOpen', title: '在办风险' },
  { key: 'actions', title: '操作' }
]
const EMPTY_FILTERS = () => ({ keyword: '', grade: '' })

export default {
  name: 'ClassListView',
  components: { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppSearchBox, AppTextInput },
  props: { ctx: { type: Object, default: null } },
  data() {
    return {
      loading: true, error: '', rows: [], columns: COLUMNS, filters: EMPTY_FILTERS(),
      pagination: { page: 1, pageSize: 10, total: 0 }
    }
  },
  computed: {
    roleName() { return (this.ctx && this.ctx.currentRole && this.ctx.currentRole.roleName) || '辅导员 / 学院学工 / 学工处' },
    scopeHint() { return (this.ctx && this.ctx.dataScope && this.ctx.dataScope.name) || '按数据范围裁剪' }
  },
  created() { this.load() },
  methods: {
    buildParams() {
      const p = { page: this.pagination.page, pageSize: this.pagination.pageSize }
      if (this.filters.keyword) p.keyword = this.filters.keyword
      if (this.filters.grade) p.grade = this.filters.grade
      return p
    },
    search() { this.pagination.page = 1; this.load() },
    reset() { this.filters = EMPTY_FILTERS(); this.pagination.page = 1; this.load() },
    onPageChange(page) { this.pagination.page = page; this.load() },
    async load() {
      this.loading = true; this.error = ''
      const res = await classApi.list(this.buildParams())
      this.loading = false
      if (res.code !== 0) { this.error = res.message || '加载失败'; this.rows = []; return }
      this.rows = res.data.list
      this.pagination.total = res.data.total
    },
    openProfile(row) {
      this.$router.push(`/admin/campus-service/classes/${row.classId}`)
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.flt { display: flex; align-items: center; gap: var(--space-3); flex-wrap: wrap; }
.flt-input { width: 160px; }
.is-warn { color: var(--danger-600); font-weight: var(--font-weight-semibold); }
</style>
