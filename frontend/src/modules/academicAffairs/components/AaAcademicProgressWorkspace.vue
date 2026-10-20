<template>
  <AaOverviewPageFrame title="学业过程" subtitle="先核对正式学业事实，再进入学生证据">
    <template #actions><AppButton @click="go('/admin/academic-affairs/roster')">查看学生名册</AppButton><AppButton variant="primary" :loading="loading" @click="load">更新学业记录</AppButton></template>
    <div class="m02-metrics">
      <article><span>当前对象</span><strong>{{ loading || error ? '—' : total }}</strong><small>当前查询范围内的学生</small></article>
      <article><span>学分已达标</span><strong>{{ loading || error ? '—' : completed }}</strong><small>本页 · 仍须核对毕业其他证据</small></article>
      <article class="is-alert"><span>学业风险</span><strong>{{ loading || error ? '—' : attention }}</strong><small>本页有正式学业风险的学生</small></article>
      <article class="is-alert"><span>来源未齐</span><strong>{{ loading || error ? '—' : unresolved }}</strong><small>本页 · 不得当成零异常</small></article>
    </div>
    <LoadingState v-if="loading" />
    <ErrorState v-else-if="error" :description="error" @retry="load" />
    <template v-else>
      <section class="m02-card">
        <header><h2>学生学业事实 · 进度与责任</h2><span class="m02-secondary">本页前 {{ progressRows.length }} 位学生</span></header>
        <div class="m02-progress-list">
          <EmptyState v-if="!rows.length" title="当前查询暂无学业记录" description="调整查询条件，或到学业台账核对学生来源。" />
          <article v-for="row in progressRows" :key="row.id" class="m02-progress-row">
            <div><strong>{{ row.name }} · {{ row.className || '班级待核对' }}</strong><span class="m02-secondary">{{ row.counselor || '责任老师待核对' }} · {{ row.studentNo }}</span></div>
            <div class="m02-progress-value"><progress v-if="ratio(row) !== null" :value="ratio(row)" max="100" :aria-label="row.name + '已获学分进度'" /><span v-else class="m02-progress-unknown">培养要求或学分来源待核对</span><small v-if="ratio(row) !== null">{{ row.obtainedCredits }} / {{ row.requiredCredits }} 学分</small></div>
            <AppButton size="small" :disabled="!canOpen(studentRoute(row))" @click="go(studentRoute(row))">查看学业记录</AppButton>
          </article>
        </div>
      </section>
      <section class="m02-card">
        <header><h2>办理队列</h2></header>
        <form class="m02-toolbar" @submit.prevent="search"><input v-model="keyword" placeholder="搜索学生姓名、学号" maxlength="100" aria-label="搜索学生学业事实" /><AppButton @click="search">查询</AppButton><AppButton variant="ghost" @click="clearSearch">清空</AppButton><small>共 {{ total }} 条 · 正式学业台账</small></form>
        <div class="m02-scroll"><table class="m02-table"><thead><tr><th>学生</th><th>专业年级</th><th>已获学分</th><th>有效 GPA</th><th>风险结论</th><th>办理入口</th></tr></thead><tbody>
          <tr v-for="row in rows" :key="row.id"><td><strong>{{ row.name }}</strong><span class="m02-secondary">{{ row.studentNo }} · {{ row.className || '班级待核对' }}</span></td><td>{{ row.majorName || '专业待核对' }} · {{ row.grade || '年级待核对' }}</td><td>{{ numeric(row.obtainedCredits) ? row.obtainedCredits : '待核对' }}</td><td>{{ numeric(row.gpa) ? Number(row.gpa).toFixed(2) : '待核对' }}</td><td><span class="m02-tag" :class="{ 'is-alert': hasRisk(row) }">{{ row.warningLabel || '待核对' }}</span><span class="m02-secondary">{{ row.academicStatusLabel || '' }}</span></td><td><button v-if="canOpen(studentRoute(row))" class="m02-link" @click="go(studentRoute(row))">打开</button><span v-else>无入口权限</span></td></tr>
          <tr v-if="!rows.length"><td colspan="6">暂无符合条件的学生</td></tr>
        </tbody></table></div>
        <footer class="m02-pager"><span>{{ total ? `第 ${(page - 1) * 5 + 1}–${(page - 1) * 5 + rows.length} 条 / 共 ${total} 条` : '共 0 条' }}</span><AppButton size="small" :disabled="page <= 1" @click="changePage(page - 1)">上一页</AppButton><span>{{ page }}</span><AppButton size="small" :disabled="page * 5 >= total" @click="changePage(page + 1)">下一页</AppButton></footer>
      </section>
      <p class="m02-note">学分、GPA 与风险结论来自正式学业台账。学分进度不代替毕业资格结论；打开同一学生的成绩单核对学分来源，预警处理仍在原业务工作区办理。</p>
    </template>
    <p v-if="message" class="m02-note" role="status">{{ message }}</p>
  </AaOverviewPageFrame>
</template>

<script>
import AaOverviewPageFrame from './AaOverviewPageFrame.vue'
import { AppButton } from '@/components/ui'
import { LoadingState, ErrorState, EmptyState } from '@/components/business'
import { request, currentUserFromToken } from '@/services/http/client'
import { academicIdentity } from '../academicFlowContext'
import { canEnterRoute } from '@/security/permissionGate'
import { safeBusinessMessage } from '@/utils/presentationSafety'
export default {
  name: 'AaAcademicProgressWorkspace', components: { AaOverviewPageFrame, AppButton, LoadingState, ErrorState, EmptyState },
  props: { ctx: { type: Object, required: true } }, inject: { academicFlow: { default: null } },
  data: () => ({ keyword: '', rows: [], total: 0, loading: false, error: '', message: '', generation: 0 }),
  computed: {
    page() { const n = Number(this.$route.query.page); return Number.isSafeInteger(n) && n > 0 && n <= 100000 ? n : 1 },
    identity() { return academicIdentity(currentUserFromToken(), this.ctx) },
    progressRows() { return this.rows.slice(0, 4) },
    completed() { return this.rows.filter(r => this.ratio(r) === 100).length },
    attention() { return this.rows.filter(this.hasRisk).length },
    unresolved() { return this.rows.filter(r => this.ratio(r) === null || !this.numeric(r.gpa) || !r.warningLabel).length }
  },
  created() { this.sync(); this.load() }, beforeUnmount() { this.generation++ },
  watch: { '$route.fullPath'() { this.sync(); this.load() }, identity() { this.load() } },
  methods: {
    numeric(v) { return typeof v === 'number' && Number.isFinite(v) && v >= 0 },
    ratio(row) { return this.numeric(row.requiredCredits) && row.requiredCredits > 0 && this.numeric(row.obtainedCredits) ? Math.min(100, row.obtainedCredits / row.requiredCredits * 100) : null },
    hasRisk(row) { return !!row.warningLevel && !['NONE', 'NORMAL'].includes(row.warningLevel) },
    sync() { this.keyword = typeof this.$route.query.keyword === 'string' ? this.$route.query.keyword : '' },
    async load() {
      const ticket = ++this.generation, identity = this.identity
      this.loading = true; this.error = ''; this.rows = []; this.total = 0
      try {
        const data = await request('/academic-affairs/dashboard/academic-progress', { params: { keyword: this.$route.query.keyword || '', page: this.page, pageSize: 5 } })
        if (ticket !== this.generation || identity !== this.identity) return
        if (!Array.isArray(data?.items) || !Number.isSafeInteger(data.total)) throw new Error('学业台账返回不完整，请重试')
        this.rows = data.items; this.total = data.total
      } catch (e) { if (ticket === this.generation && identity === this.identity) this.error = safeBusinessMessage(e?.message, '学业记录读取失败') }
      finally { if (ticket === this.generation && identity === this.identity) this.loading = false }
    },
    search() { const query = { ...this.$route.query, keyword: this.keyword.trim() || undefined, page: '1' }; if ((query.keyword || '') === (this.$route.query.keyword || '') && this.page === 1) this.load(); else this.$router.push({ path: this.$route.path, query }) },
    clearSearch() { this.keyword = ''; this.search() },
    changePage(page) { this.$router.push({ path: this.$route.path, query: { ...this.$route.query, page: String(page) } }) },
    studentRoute(row) { return row.studentId ? `/admin/academic-affairs/transcript?studentId=${encodeURIComponent(row.studentId)}&name=${encodeURIComponent(row.name)}` : '' },
    canOpen(target) { if (!target) return false; const route = this.$router.resolve(target); return !!route.matched.length && route.matched.every(r => canEnterRoute(r.meta)) },
    go(target) { if (!this.canOpen(target)) { this.message = '当前身份无该学业记录入口权限'; return } const route = this.$router.resolve(target), returnToken = this.academicFlow?.captureReturn(); this.$router.push({ path: route.path, query: { ...route.query, ...(returnToken ? { returnToken } : {}) } }) }
  }
}
</script>

<style scoped>
.m02-progress-list { padding:12px 16px 20px; }
.m02-progress-row { display:grid; grid-template-columns:220px minmax(0,1fr) 105px; gap:14px; align-items:center; min-height:56px; }
.m02-progress-row strong { font-size:13px; }.m02-progress-value { display:flex; align-items:center; gap:12px; }.m02-progress-value progress { width:100%; height:10px; border:0; border-radius:6px; overflow:hidden; appearance:none; }.m02-progress-value progress::-webkit-progress-bar { background:var(--bg-page); border-radius:6px; }.m02-progress-value progress::-webkit-progress-value { background:var(--pri); border-radius:6px; }.m02-progress-value progress::-moz-progress-bar { background:var(--pri); border-radius:6px; }.m02-progress-value small { min-width:88px; color:var(--text-secondary); font-size:11px; text-align:right; }.m02-progress-unknown { font-size:12px; color:var(--text-secondary); }
@container academic-body (max-width:760px) { .m02-progress-row { grid-template-columns:180px minmax(0,1fr) 90px; }.m02-progress-value small { display:none; } }
@container academic-body (max-width:520px) { .m02-progress-row { grid-template-columns:1fr 90px; padding:10px 0; }.m02-progress-value { grid-row:2; grid-column:1 / -1; } }
</style>
