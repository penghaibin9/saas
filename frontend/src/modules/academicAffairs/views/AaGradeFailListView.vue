<template>
  <ModulePageShell
    title="挂科清单"
    subtitle="正式生效的不及格记录，不累加已被替代的历史成绩"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="mp-stack">
      <AdvancedFilter v-model="filters" :fields="filterFields" @search="search" @reset="reset" />

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" title="无挂科记录" description="当前范围内没有不及格成绩" />
      <DataTable v-else :columns="columns" :rows="rows" row-key="rowKey" :pagination="pagination" @page-change="onPageChange">
        <template #cell-score="{ row }"><span class="aa-fail-score">{{ row.score ?? '待核对' }}</span></template>
        <template #cell-remedy="{ row }">{{ row.attemptNo == null ? '修读次数待核对' : `第 ${row.attemptNo} 次修读` }} · 补救办理情况待核对</template>
        <template #cell-actions="{ row }">
          <button class="mp-link" :disabled="!row.studentId" @click="goTranscript(row)">成绩单</button>
        </template>
      </DataTable>
    </div>
  </ModulePageShell>
</template>

<script>
/** 挂科清单（/admin/academic-affairs/grade-fail）：GET /grade-views/fail-list。 */
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AdvancedFilter } from '@/components/business'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { currentUserFromToken } from '@/services/http/client'
import { gradeError } from './parallel-c/grade-review'

export default {
  name: 'AaGradeFailListView',
  components: { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AdvancedFilter },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      alive: true, readSeq: 0, loading: true, error: '', rows: [], filters: { term: '' },
      pagination: { page: 1, pageSize: 50, total: 0 },
      columns: [
        { key: 'studentName', title: '学生' },
        { key: 'courseName', title: '课程' },
        { key: 'term', title: '学期' },
        { key: 'score', title: '正式成绩' },
        { key: 'remedy', title: '补救情况' },
        { key: 'actions', title: '操作', width: '80px' }
      ]
    }
  },
  computed: {
    identityKey() { const u = currentUserFromToken() || {}; return JSON.stringify([u.tenantId, u.userId, u.activeContextId, u.currentRoleCode, this.ctx.currentRole, this.ctx.dataScope]) },

    filterFields() {
      return [
        { key: 'term', label: '学期', type: 'text', placeholder: '学期码（空=全部）' }
      ]
    }
  },
  created() { this.load() },
  watch: { identityKey() { this.readSeq++; this.rows = []; this.pagination.page = 1; this.pagination.total = 0; this.load() } },
  beforeUnmount() { this.alive = false; this.readSeq++ },
  methods: {
    goTranscript(row) {
      this.$router.push({ path: '/admin/academic-affairs/transcript', query: { studentId: row.studentId, name: row.studentName } })
    },
    onPageChange(p) { this.pagination.page = p; this.load() },
    search() { this.pagination.page = 1; this.load() },
    reset() { this.filters.term = ''; this.search() },
    async load() {
      const seq = ++this.readSeq, identity = this.identityKey
      const valid = () => this.alive && seq === this.readSeq && identity === this.identityKey
      this.loading = true; this.error = ''; this.rows = []; this.pagination.total = 0
      try {
        const res = await academicAffairsApi.getFailList({ term: this.filters.term || undefined, page: this.pagination.page, pageSize: this.pagination.pageSize })
        if (!valid()) return
        if (res.code !== 0) throw res
        this.rows = (Array.isArray(res.data?.list) ? res.data.list : []).map((r, i) => ({ ...r, rowKey: r.gradeId || `${r.studentId}-${r.courseId || r.courseName}-${i}` }))
        this.pagination.total = res.data?.total ?? this.rows.length
      } catch (err) { if (valid()) this.error = gradeError(err, '记录读取失败，请重试。') }
      finally { if (valid()) this.loading = false }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-filter { display: flex; gap: 16px; align-items: center; }
.aa-filter__item { display: inline-flex; align-items: center; gap: 8px; font-size: 13px; color: var(--text-700, #4e5969); }
.aa-input { height: 32px; padding: 0 10px; border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px; background: var(--bg-white, #fff); color: var(--text-900, #1f2329); font-size: 13px; }
.aa-input--sm { width: 200px; }
.aa-fail-score { color: var(--danger-600, #f53f3f); font-weight: 600; }
</style>
