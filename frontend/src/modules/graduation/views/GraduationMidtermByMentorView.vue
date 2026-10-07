<template>
  <ModulePageShell
    class="gm-shell"
    title="中期检查（按导师看）"
    :subtitle="subtitle"
    :role-name="ctx.currentRole?.roleName"
    :data-scope-name="ctx.dataScope?.scopeName"
  >
    <template #summary>
      <div class="gm-kpis">
        <span class="gm-kpi"><b>{{ s.total || 0 }}</b>名学生</span>
        <span class="gm-kpi"><b>{{ s.checked || 0 }}</b>已检查</span>
        <span class="gm-kpi" :class="{ 'is-warn': s.pendingCheck }"><b>{{ s.pendingCheck || 0 }}</b>待检查</span>
        <span class="gm-kpi" :class="{ 'is-warn': s.pendingReview }"><b>{{ s.pendingReview || 0 }}</b>整改待复核</span>
        <span class="gm-kpi"><b>{{ s.rectifying || 0 }}</b>学生整改中</span>
        <span class="gm-kpi"><b>{{ s.notReady || 0 }}</b>还没到中期</span>
      </div>
    </template>
    <template #actions>
      <AppButton :disabled="loading" @click="load">刷新</AppButton>
    </template>

    <ErrorState v-if="error" :description="error" @retry="load" />
    <LoadingState v-else-if="loading" />
    <EmptyState v-else-if="!hasBatch" title="请先选择毕设批次" description="选择批次后按导师查看中期检查进度。" />
    <EmptyState v-else-if="!rows.length" title="这个批次还没有学生" description="导入学生并分配导师后，这里会按导师列出中期检查进度。" />

    <section v-else class="mp-card">
      <div class="mp-card__head">
        <span class="mp-card__title">导师进度</span>
        <small>开题通过的学生自动进入导师的「中期检查」待办，不需要逐个推进阶段。待处理多的导师排在前面。</small>
      </div>
      <div class="mp-card__body gm-wrap">
        <table class="gm-table">
          <thead>
            <tr><th>指导教师</th><th>学生数</th><th>已检查</th><th>待检查</th><th>整改待复核</th><th>学生整改中</th><th>最近一次检查</th><th aria-label="操作" /></tr>
          </thead>
          <tbody>
            <template v-for="row in rows" :key="row.mentorId || 'none'">
              <tr :class="{ 'is-open': open[rowKey(row)] }">
                <td><strong>{{ row.mentorName }}</strong><small v-if="row.teacherNo">工号 {{ row.teacherNo }}</small></td>
                <td class="num">{{ row.total }}</td>
                <td class="num">{{ row.checked }}</td>
                <td class="num" :class="{ 'is-warn': row.pendingCheck }">{{ row.pendingCheck }}</td>
                <td class="num" :class="{ 'is-warn': row.pendingReview }">{{ row.pendingReview }}</td>
                <td class="num">{{ row.rectifying }}</td>
                <td>{{ row.lastCheckedAt ? shortTime(row.lastCheckedAt) : '还没检查过' }}</td>
                <td class="ops">
                  <button v-if="row.pendingStudents.length" type="button" class="mp-link" @click="toggle(row)">
                    {{ open[rowKey(row)] ? '收起' : `看待处理学生（${row.pendingCheck + row.pendingReview}）` }}
                  </button>
                </td>
              </tr>
              <tr v-if="open[rowKey(row)]" class="gm-sub">
                <td colspan="8">
                  <div class="gm-students">
                    <button v-for="st in row.pendingStudents" :key="st.gdStudentId" type="button" class="gm-student" @click="openStudent(st)">
                      <strong>{{ st.studentName }}</strong>
                      <small>{{ [st.className, st.studentNo].filter(Boolean).join(' · ') }}</small>
                      <em>{{ st.statusLabel }}</em>
                    </button>
                  </div>
                  <p v-if="row.pendingCheck + row.pendingReview > row.pendingStudents.length" class="mp-note">只列出前 {{ row.pendingStudents.length }} 名。</p>
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>
    </section>
  </ModulePageShell>
</template>

<script>
import { AppButton } from '@/components/ui'
import { ModulePageShell, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { graduationApi } from '@/modules/graduation/api/graduation.api'
import { useGraduationBatchStore } from '@/stores/graduationBatch'

export default {
  name: 'GraduationMidtermByMentorView',
  components: { AppButton, ModulePageShell, LoadingState, ErrorState, EmptyState },
  props: { ctx: { type: Object, required: true } },
  data() {
    return { batchStore: useGraduationBatchStore(), loading: true, error: '', rows: [], s: {}, open: {}, token: 0 }
  },
  computed: {
    hasBatch() { return !!this.batchStore.selectedBatchId },
    subtitle() {
      const name = this.batchStore.selectedBatchName || '当前批次'
      return this.s.mentorsWithPending ? `${name} · ${this.s.mentorsWithPending} 位导师还有待处理` : name
    }
  },
  watch: { 'batchStore.selectedBatchId'() { this.load() } },
  created() { this.load() },
  methods: {
    rowKey(row) { return row.mentorId || 'none' },
    toggle(row) { this.open = { ...this.open, [this.rowKey(row)]: !this.open[this.rowKey(row)] } },
    shortTime(value) { const t = String(value || '').replace('T', ' '); return t.length > 16 ? t.slice(0, 16) : t },
    async load() {
      const token = ++this.token
      this.error = ''
      if (!this.hasBatch) { this.loading = false; this.rows = []; this.s = {}; return }
      this.loading = true
      try {
        const res = await graduationApi.getMidtermByMentor({ batchId: this.batchStore.selectedBatchId })
        if (token !== this.token) return
        if (res.code === 0) { this.rows = res.data?.rows || []; this.s = res.data?.summary || {} }
        else this.error = res.message || '中期检查进度加载失败，请稍后重试。'
      } catch (error) {
        if (token === this.token) this.error = error?.message || '中期检查进度加载失败，请检查网络后重试。'
      } finally {
        if (token === this.token) this.loading = false
      }
    },
    openStudent(st) {
      const batchId = this.batchStore.selectedBatchId ? String(this.batchStore.selectedBatchId) : undefined
      this.$router.push({ path: '/admin/graduation/process', query: { panel: 'midterm', studentId: st.gdStudentId, batchId, source: 'midterm-by-mentor' } }).catch(() => {})
    }
  }
}
</script>

<style scoped>
.gm-kpis { display: flex; flex-wrap: wrap; gap: 6px; }
.gm-kpi { display: inline-flex; align-items: baseline; gap: 4px; padding: 4px 10px; border: 1px solid var(--border-light, #e2e8f0); border-radius: 8px; background: var(--card, #fff); color: var(--text-tertiary, #64748b); font-size: 12px; }
.gm-kpi b { color: var(--text-primary, #0f172a); font-size: 16px; font-variant-numeric: tabular-nums; }
.gm-kpi.is-warn b { color: var(--warning-600, #d97706); }
.mp-card__head small { color: var(--text-tertiary, #64748b); }
.gm-wrap { overflow-x: auto; }
.gm-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.gm-table th, .gm-table td { padding: 9px 10px; border-bottom: 1px solid var(--border-light, #e2e8f0); text-align: left; vertical-align: middle; }
.gm-table th { color: var(--text-tertiary, #64748b); font-weight: 600; background: var(--gray-50, #f8fafc); white-space: nowrap; }
.gm-table td small { display: block; color: var(--text-tertiary, #64748b); font-size: 12px; }
.gm-table .num { font-variant-numeric: tabular-nums; }
.gm-table .is-warn { color: var(--warning-700, #b45309); font-weight: 700; }
.gm-table .ops { text-align: right; white-space: nowrap; }
.gm-sub td { background: var(--gray-50, #f8fafc); }
.gm-students { display: flex; flex-wrap: wrap; gap: 8px; }
.gm-student { display: grid; gap: 2px; padding: 8px 12px; border: 1px solid var(--border-light, #e2e8f0); border-radius: 8px; background: var(--card, #fff); text-align: left; cursor: pointer; }
.gm-student small { color: var(--text-tertiary, #64748b); font-size: 12px; }
.gm-student em { font-style: normal; color: var(--warning-700, #b45309); font-size: 12px; }
.gm-student:hover { border-color: var(--primary-300, #93c5fd); }
</style>
