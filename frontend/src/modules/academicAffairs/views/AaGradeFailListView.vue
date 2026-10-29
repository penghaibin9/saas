<template>
  <ModulePageShell
    title="挂科清单"
    subtitle="正式生效的不及格记录，不累加已被替代的历史成绩"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="mp-stack">
      <form class="aa-filter" @submit.prevent="search">
        <label class="aa-filter__item">学期<AppTermCodePicker v-model="filters.term" placeholder="全部学期" /></label>
        <AppButton type="submit" :loading="loading">查询</AppButton><AppButton variant="ghost" @click="reset">重置</AppButton>
      </form>

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" title="无挂科记录" description="当前范围内没有不及格成绩" />
      <DataTable v-else :columns="columns" :rows="rows" row-key="rowKey" :pagination="pagination" @page-change="onPageChange">
        <template #cell-score="{ row }"><span class="aa-fail-score">{{ row.score ?? '待核对' }}</span></template>
        <template #cell-remedy="{ row }">
          <div>{{ row.attemptNo == null ? '修读次数待核对' : `第 ${row.attemptNo} 次修读` }}</div>
          <div v-for="item in row.remedies || []" :key="`${item.kind}-${item.id}`">
            <button v-if="canViewRemedy && (item.kind === 'RETAKE' || (item.kind === 'MAKEUP' && item.batchId))" class="mp-link" @click="goRemedy(item, row)">{{ remedyLabel(item) }} · {{ item.kind === 'RETAKE' ? '查看申请' : '查看补考名单' }}</button>
            <span v-else>{{ remedyLabel(item) }}</span>
          </div>
          <span v-if="!row.remedies?.length">未查到与本条成绩关联的补救记录，请由补重修责任岗核对</span>
        </template>
        <template #cell-actions="{ row }">
          <button class="mp-link" :disabled="!row.studentId" @click="goTranscript(row)">成绩单</button>
        </template>
      </DataTable>
    </div>
  </ModulePageShell>
</template>

<script>
/** 挂科清单（/admin/academic-affairs/grade-fail）：GET /grade-views/fail-list。 */
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppTermCodePicker } from '@/components/common'
import { AppButton } from '@/components/ui'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { currentUserFromToken } from '@/services/http/client'
import { matchPermission } from '@/config/navPlan'
import { gradeError } from './parallel-c/grade-review'

export default {
  name: 'AaGradeFailListView',
  components: { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppTermCodePicker, AppButton },
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
    canViewRemedy() { return matchPermission(this.ctx.permissionPatterns || [], 'academicAffairs.makeup.view') },
    identityKey() { const u = currentUserFromToken() || {}; return JSON.stringify([u.tenantId, u.userId, u.activeContextId, u.currentRoleCode, this.ctx.currentRole, this.ctx.dataScope]) },

  },
  created() { this.restoreQuery(); this.load() },
  watch: {
    identityKey() { this.readSeq++; this.rows = []; this.pagination.page = 1; this.pagination.total = 0; this.load() },
    '$route.fullPath'() { if (this.$route.path === '/admin/academic-affairs/grade-fail') { this.restoreQuery(); this.load() } }
  },
  beforeUnmount() { this.alive = false; this.readSeq++ },
  methods: {
    remedyLabel(item) {
      const kind = { MAKEUP: '补考', CLEARANCE: '清考', RETAKE: '重修' }[item.kind] || '补救记录'
      const status = { PENDING_EXAM: '待考试', ARRANGED: '已安排', SCORED: '已录分，待审核发布', FINISHED: '办理已结束，当前正式成绩仍未通过', SUBMITTED: '待审核', ACADEMIC_REVIEW: '教务审核中', APPROVED: '已批准，待编班', REJECTED: '已驳回', ENROLLED: '已编班', CANCELLED: '已撤销' }[item.status] || '办理状态待核对'
      return `${kind}：${status}`
    },
    goRemedy(item, row) {
      if (!this.canViewRemedy || !/^[1-9]\d*$/.test(String(item.id))) return
      if (item.kind === 'RETAKE') return this.$router.push({ path: '/admin/academic-affairs/makeup', query: { tab: 'retake', applyId: String(item.id) } })
      if (item.kind === 'MAKEUP' && /^[1-9]\d*$/.test(String(item.batchId)) && /^[1-9]\d*$/.test(String(row?.gradeId))) {
        this.$router.push({ path: '/admin/academic-affairs/makeup', query: { tab: 'makeup', batchId: String(item.batchId), originGradeId: String(row.gradeId) } })
      }
    },
    goTranscript(row) {
      this.$router.push({ path: '/admin/academic-affairs/transcript', query: { studentId: row.studentId, name: row.studentName } })
    },
    restoreQuery() {
      this.filters.term = typeof this.$route.query.term === 'string' ? this.$route.query.term : ''
      const page = Number(this.$route.query.page || 1)
      this.pagination.page = Number.isSafeInteger(page) && page > 0 ? page : 1
    },
    updateQuery(page) {
      if (!Number.isSafeInteger(page) || page < 1) return
      this.pagination.page = page
      if (String(this.$route.query.term || '') === this.filters.term && Number(this.$route.query.page || 1) === page) return this.load()
      return this.$router.replace({ query: { ...this.$route.query, term: this.filters.term || undefined, page: String(page) } })
    },
    onPageChange(p) { return this.updateQuery(p) },
    search() { return this.updateQuery(1) },
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
.aa-filter { display: flex; flex-wrap: wrap; gap: 16px; align-items: center; }
.aa-filter__item { display: inline-flex; flex: 0 1 320px; min-width: 0; white-space: nowrap; align-items: center; gap: 8px; font-size: 13px; color: var(--text-700, #4e5969); }
.aa-input { height: 32px; padding: 0 10px; border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px; background: var(--bg-white, #fff); color: var(--text-900, #1f2329); font-size: 13px; }
.aa-input--sm { width: 200px; }
.aa-fail-score { color: var(--danger-600, #f53f3f); font-weight: 600; }
</style>
