<template>
  <ModulePageShell
    title="学籍名册"
    subtitle="在籍学生主档（只读脱敏）· 可从这里对某个学生发起学籍异动"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="mp-stack">
      <div class="aa-filter">
        <label class="aa-filter__item">
          关键字
          <input v-model.trim="filters.keyword" class="aa-input" placeholder="姓名 / 学号" @keyup.enter="search" />
        </label>
        <label class="aa-filter__item">
          学籍状态
          <select v-model="filters.status" class="aa-select">
            <option value="">全部</option>
            <option v-for="(label, val) in STATUS_LABEL" :key="val" :value="val">{{ label }}</option>
          </select>
        </label>
        <button class="mp-btn" @click="search">查询</button>
        <button class="mp-btn" @click="reset">重置</button>
      </div>

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
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppStatusTag } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'

const STATUS_LABEL = {
  REGISTERED: '在籍注册', PENDING_REGISTER: '待注册', SUSPENDED: '休学',
  WITHDRAWN: '退学', RETAINED: '留级', GRADUATED: '毕业'
}

export default {
  name: 'AaRosterListView',
  components: { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppStatusTag },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      STATUS_LABEL,
      loading: true,
      error: '',
      rows: [],
      filters: { keyword: '', status: '' },
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
