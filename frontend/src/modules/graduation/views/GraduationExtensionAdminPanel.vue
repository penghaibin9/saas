<template>
  <ModulePageShell
    :title="activePanel === 'excellent' ? '优秀成果认定' : '延期答辩管理'"
    :subtitle="subtitle"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="mp-stack">
      <section class="ext-hero">
        <div class="ext-hero__main">
          <span class="ext-eyebrow">当前批次</span>
          <strong>{{ batchStore.selectedBatchName || '请先选择毕业设计批次' }}</strong>
          <p>{{ nextStepText }}</p>
        </div>
        <div class="ext-kpis">
          <div><span>台账总数</span><b>{{ total }}</b></div>
          <div><span>当前页待处理</span><b>{{ actionableCount }}</b></div>
          <div><span>{{ activePanel === 'excellent' ? '本人可提名' : '可用答辩组' }}</span><b>{{ activePanel === 'excellent' ? nominatableCount : groups.length }}</b></div>
        </div>
      </section>

      <div class="mp-tabs ext-main-tabs">
        <button class="mp-tab" :class="{ 'is-active': activePanel === 'excellent' }" @click="switchPanel('excellent')">优秀成果认定</button>
        <button class="mp-tab" :class="{ 'is-active': activePanel === 'delay' }" @click="switchPanel('delay')">延期答辩</button>
      </div>

      <div class="ext-filter-bar">
        <button
          v-for="item in statusOptions"
          :key="item.value"
          class="ext-filter"
          :class="{ 'is-active': statusFilter === item.value }"
          @click="changeStatus(item.value)"
        >{{ item.label }}</button>
      </div>

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />

      <template v-else-if="activePanel === 'excellent'">
        <section class="mp-card">
          <div class="mp-card__head">
            <div>
              <span class="mp-card__title">可提名候选</span>
              <p class="mp-note">成绩“优秀”只是候选条件；只有该生稳定绑定导师可提名，之后仍须专业复核、学院终审。</p>
            </div>
          </div>
          <div v-if="supportError" class="ext-inline-error">候选加载失败：{{ supportError }}</div>
          <EmptyState v-else-if="!candidates.length" title="当前没有可提名候选" description="需满足成绩已发布且等级优秀、正式定稿已通过，并且没有进行中的优秀成果记录。" />
          <div v-else class="ext-grid">
            <article v-for="row in candidates" :key="row.gdStudentId" class="ext-card">
              <div class="ext-card__head"><strong>{{ row.studentName }}</strong><span>{{ row.studentNo }} · {{ row.className }}</span></div>
              <p>{{ row.topicTitle || '未填写课题' }}</p>
              <div class="ext-meta"><span>导师 {{ row.advisorName || '—' }}</span><b>{{ row.totalScore }} 分 · 优秀</b></div>
              <button v-if="row.canNominate" class="mp-btn mp-btn--primary" @click="askNominate(row)">导师提名</button>
              <span v-else class="ext-muted">仅该生当前指导教师可提名</span>
            </article>
          </div>
        </section>

        <section class="mp-card">
          <div class="mp-card__head"><span class="mp-card__title">认定台账 · {{ total }} 条</span></div>
          <EmptyState v-if="!rows.length" title="当前筛选下暂无认定记录" description="导师完成提名后会进入专业、学院两级审核。" />
          <div v-else class="ext-table-wrap">
            <table class="ext-table">
              <thead><tr><th>学生 / 课题</th><th>提名理由</th><th>成绩快照</th><th>状态</th><th>审核留痕</th><th>下一步操作</th></tr></thead>
              <tbody>
                <tr v-for="row in rows" :key="row.id">
                  <td data-label="学生 / 课题"><strong>{{ row.studentName }}</strong><small>{{ row.studentNo }} · {{ row.topicTitle || '未填写课题' }}</small></td>
                  <td data-label="提名理由">{{ row.nominationReason }}</td>
                  <td data-label="成绩快照">{{ row.gradeSnapshot.totalScore == null ? '—' : row.gradeSnapshot.totalScore }} · {{ row.gradeSnapshot.gradeLevel || '—' }}</td>
                  <td data-label="状态"><StatusTag :type="statusTone(row.status)" :label="row.statusLabel" dot /></td>
                  <td data-label="审核留痕"><small>提名：{{ row.nominatedBy || '—' }}</small><small>专业：{{ row.majorReviewedBy || '待处理' }}</small><small>学院：{{ row.collegeReviewedBy || '待处理' }}</small></td>
                  <td data-label="下一步操作" class="ext-actions">
                    <template v-if="can(row, 'majorReview')">
                      <button class="mp-link" @click="askReview('excellent-major', row, 'APPROVE')">专业通过</button>
                      <button class="mp-link ext-danger" @click="askReview('excellent-major', row, 'REJECT')">驳回</button>
                    </template>
                    <template v-else-if="can(row, 'collegeReview')">
                      <button class="mp-link" @click="askReview('excellent-college', row, 'APPROVE')">学院发布</button>
                      <button class="mp-link ext-danger" @click="askReview('excellent-college', row, 'REJECT')">驳回</button>
                    </template>
                    <span v-else class="ext-muted">{{ excellentNextStep(row) }}</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      </template>

      <template v-else>
        <section class="mp-card">
          <div class="mp-card__head">
            <div>
              <span class="mp-card__title">延期答辩审批与排期 · {{ total }} 条</span>
              <p class="mp-note">学生申请 → 导师审核 → 专业复核 → 学院审批 → 重新排期。每行只显示当前角色真正可执行的动作。</p>
            </div>
          </div>
          <div v-if="supportError" class="ext-inline-error">答辩组加载失败：{{ supportError }}。审批仍可查看，但暂不能排期。</div>
          <EmptyState v-if="!rows.length" title="当前筛选下没有延期答辩申请" description="学生进入成果检查或答辩阶段后，可从学生 PC / 小程序提交申请。" />
          <div v-else class="ext-table-wrap">
            <table class="ext-table">
              <thead><tr><th>学生 / 课题</th><th>申请理由</th><th>状态</th><th>审核留痕</th><th>排期</th><th>下一步操作</th></tr></thead>
              <tbody>
                <tr v-for="row in rows" :key="row.id">
                  <td data-label="学生 / 课题"><strong>{{ row.studentName }}</strong><small>{{ row.studentNo }} · {{ row.topicTitle || '未填写课题' }}</small></td>
                  <td data-label="申请理由">{{ row.reason }}</td>
                  <td data-label="状态"><StatusTag :type="statusTone(row.status)" :label="row.statusLabel" dot /></td>
                  <td data-label="审核留痕"><small>导师：{{ row.advisorReviewedBy || '待处理' }}</small><small>专业：{{ row.majorReviewedBy || '待处理' }}</small><small>学院：{{ row.collegeReviewedBy || '待处理' }}</small></td>
                  <td data-label="排期">
                    <template v-if="can(row, 'schedule')">
                      <select v-model="scheduleDraft(row).groupId" class="ext-input" @change="onGroupChange(row)">
                        <option value="">选择延期答辩组</option>
                        <option v-for="g in groups" :key="g.id" :value="g.id">
                          {{ g.groupName }} · {{ g.date || '日期待定' }} · {{ g.studentCount || 0 }}人{{ g.published ? ' · 已发布' : '' }}
                        </option>
                      </select>
                      <input v-model="scheduleDraft(row).date" class="ext-input" type="date" />
                    </template>
                    <template v-else>{{ row.plannedDefenseDate || '—' }}<small>{{ row.defenseGroupName || '' }}</small></template>
                  </td>
                  <td data-label="下一步操作" class="ext-actions">
                    <template v-if="can(row, 'advisorReview')">
                      <button class="mp-link" @click="askReview('delay-advisor', row, 'APPROVE')">导师通过</button>
                      <button class="mp-link ext-danger" @click="askReview('delay-advisor', row, 'REJECT')">驳回</button>
                    </template>
                    <template v-else-if="can(row, 'majorReview')">
                      <button class="mp-link" @click="askReview('delay-major', row, 'APPROVE')">专业通过</button>
                      <button class="mp-link ext-danger" @click="askReview('delay-major', row, 'REJECT')">驳回</button>
                    </template>
                    <template v-else-if="can(row, 'collegeReview')">
                      <button class="mp-link" @click="askReview('delay-college', row, 'APPROVE')">学院批准</button>
                      <button class="mp-link ext-danger" @click="askReview('delay-college', row, 'REJECT')">驳回</button>
                    </template>
                    <button
                      v-else-if="can(row, 'schedule')"
                      class="mp-btn mp-btn--primary"
                      :disabled="!scheduleDraft(row).date || !scheduleDraft(row).groupId || !!supportError"
                      @click="askSchedule(row)"
                    >确认排期</button>
                    <span v-else class="ext-muted">{{ delayNextStep(row) }}</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      </template>

      <AppPagination v-if="total > pageSize" :total="total" :page="page" :page-size="pageSize" :show-size-changer="false" @update:page="turnPage" />
    </div>

    <AppConfirmDialog
      v-model:visible="confirm.visible"
      :title="confirm.title"
      :message="confirm.message"
      :type="confirm.type"
      :confirm-text="confirm.confirmText"
      :require-reason="confirm.requireReason"
      :reason-label="confirm.reasonLabel"
      :submitting="submitting"
      @confirm="onConfirm"
    />
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppPagination } from '@/components/common'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import { graduationMoreApi } from '@/modules/graduation/api/graduation-more.api'
import { useGraduationBatchStore } from '@/stores/graduationBatch'
import { toast } from '@/utils/toast'

const EXCELLENT_STATUS = [
  { value: '', label: '全部' }, { value: 'PENDING_MAJOR', label: '待专业复核' },
  { value: 'PENDING_COLLEGE', label: '待学院终审' }, { value: 'PUBLISHED', label: '已发布' },
  { value: 'REJECTED', label: '已驳回' }
]
const DELAY_STATUS = [
  { value: '', label: '全部' }, { value: 'PENDING_ADVISOR', label: '待导师审核' },
  { value: 'PENDING_MAJOR', label: '待专业复核' }, { value: 'PENDING_COLLEGE', label: '待学院审批' },
  { value: 'APPROVED', label: '待排期' }, { value: 'SCHEDULED', label: '已排期' },
  { value: 'REJECTED', label: '已驳回' }
]

export default {
  name: 'GraduationExtensionAdminPanel',
  components: { ModulePageShell, StatusTag, LoadingState, ErrorState, EmptyState, AppPagination, AppConfirmDialog },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      batchStore: useGraduationBatchStore(), loading: false, error: '', supportError: '', rows: [], candidates: [], groups: [],
      total: 0, page: 1, pageSize: 20, statusFilter: '', submitting: false, schedules: {},
      confirm: { visible: false, title: '', message: '', type: 'primary', confirmText: '确认', requireReason: true, reasonLabel: '说明', action: '', row: null, decision: '' }
    }
  },
  computed: {
    activePanel() { return this.$route.query.extension === 'delay' ? 'delay' : 'excellent' },
    statusOptions() { return this.activePanel === 'excellent' ? EXCELLENT_STATUS : DELAY_STATUS },
    nominatableCount() { return this.candidates.filter((row) => row.canNominate).length },
    actionableCount() {
      const rowActions = this.rows.filter((row) => Object.values(row.allowedActions || {}).some(Boolean)).length
      return this.activePanel === 'excellent' ? rowActions + this.nominatableCount : rowActions
    },
    nextStepText() {
      if (!this.batchStore.selectedBatchId) return '先选择批次，系统才会加载对应届别的候选、审批台账和答辩组。'
      if (this.loading) return '正在读取当前批次真实台账。'
      if (this.error) return '主台账加载失败，请先重试，不要把故障当成暂无业务。'
      if (this.actionableCount > 0) return `当前页有 ${this.actionableCount} 项需要你处理，完成后会自动进入下一角色队列。`
      return this.activePanel === 'excellent' ? '当前没有需要你处理的认定，继续关注候选和后续审核。' : '当前没有需要你处理的延期申请，继续关注学生申请或答辩组重新发布。'
    },
    subtitle() {
      const batch = this.batchStore.selectedBatchName || '当前批次'
      return this.activePanel === 'excellent'
        ? `${batch} · 导师提名、专业复核、学院终审形成独立证据链`
        : `${batch} · 延期申请与二次答辩分开管理，排期会撤回相关答辩组发布状态`
    }
  },
  watch: {
    '$route.query.extension'() { this.page = 1; this.statusFilter = ''; this.schedules = {}; this.load() },
    'batchStore.selectedBatchId'() { this.page = 1; this.statusFilter = ''; this.schedules = {}; this.load() }
  },
  created() { this.load() },
  methods: {
    can(row, action) { return !!(row && row.allowedActions && row.allowedActions[action]) },
    statusTone(status) {
      if (['PUBLISHED', 'SCHEDULED'].includes(status)) return 'success'
      if (status === 'REJECTED') return 'danger'
      return 'warning'
    },
    switchPanel(panel) { this.$router.replace({ query: { ...this.$route.query, extension: panel } }) },
    changeStatus(status) { this.statusFilter = status; this.page = 1; this.load() },
    turnPage(page) { this.page = page; this.load() },
    scheduleDraft(row) {
      if (!this.schedules[row.id]) this.schedules[row.id] = { date: row.plannedDefenseDate || '', groupId: row.defenseGroupId || '' }
      return this.schedules[row.id]
    },
    primeSchedules(rows) {
      const next = {}
      rows.forEach((row) => { next[row.id] = { date: row.plannedDefenseDate || '', groupId: row.defenseGroupId || '' } })
      this.schedules = next
    },
    onGroupChange(row) {
      const draft = this.scheduleDraft(row)
      const group = this.groups.find((item) => String(item.id) === String(draft.groupId))
      if (group && group.date && group.date !== '待定') draft.date = String(group.date).slice(0, 10)
    },
    async load() {
      if (!this.batchStore.selectedBatchId) { this.rows = []; this.candidates = []; this.groups = []; this.total = 0; this.error = ''; return }
      this.loading = true; this.error = ''; this.supportError = ''
      const params = { page: this.page, pageSize: this.pageSize, ...(this.statusFilter ? { status: this.statusFilter } : {}) }
      if (this.activePanel === 'excellent') {
        const [records, candidates] = await Promise.all([
          graduationMoreApi.getExcellentOutcomes(params),
          graduationMoreApi.getExcellentCandidates({ page: 1, pageSize: 100 })
        ])
        if (records.code === 0) { this.rows = records.data.list; this.total = records.data.total } else { this.rows = []; this.total = 0; this.error = records.message }
        if (candidates.code === 0) this.candidates = candidates.data.list
        else { this.candidates = []; this.supportError = candidates.message || '候选接口不可用' }
      } else {
        const [records, groups] = await Promise.all([
          graduationMoreApi.getDefenseDelays(params),
          graduationMoreApi.getDefenseGroups()
        ])
        if (records.code === 0) { this.rows = records.data.list; this.total = records.data.total; this.primeSchedules(this.rows) } else { this.rows = []; this.total = 0; this.error = records.message }
        if (groups.code === 0) this.groups = groups.data.list
        else { this.groups = []; this.supportError = groups.message || '答辩组接口不可用' }
      }
      this.loading = false
    },
    excellentNextStep(row) {
      const map = { PENDING_MAJOR: '等待专业负责人', PENDING_COLLEGE: '等待学院管理员', PUBLISHED: '已完成', REJECTED: '已结束，可重新提名' }
      return map[row.status] || '查看记录'
    },
    delayNextStep(row) {
      const map = { PENDING_ADVISOR: '等待指导教师', PENDING_MAJOR: '等待专业负责人', PENDING_COLLEGE: '等待学院管理员', APPROVED: '等待学院排期', SCHEDULED: '答辩组待重新发布', REJECTED: '已结束，学生可按条件重申' }
      return map[row.status] || '查看记录'
    },
    askNominate(row) {
      this.confirm = { visible: true, title: '提名优秀成果', message: `确认提名「${row.studentName}」的毕业设计为优秀成果候选？`, type: 'primary', confirmText: '提交提名', requireReason: true, reasonLabel: '提名理由（10—1000字）', action: 'NOMINATE', row, decision: '' }
    },
    askReview(action, row, decision) {
      const reject = decision === 'REJECT'
      this.confirm = { visible: true, title: reject ? '驳回申请' : '审核通过', message: `处理「${row.studentName}」：${row.statusLabel}`, type: reject ? 'danger' : 'primary', confirmText: reject ? '确认驳回' : '确认通过', requireReason: true, reasonLabel: reject ? '驳回理由（5—1000字）' : '审核意见（最多1000字）', action, row, decision }
    },
    askSchedule(row) {
      const draft = this.scheduleDraft(row)
      const group = this.groups.find((item) => String(item.id) === String(draft.groupId))
      const groupName = group ? group.groupName : '所选答辩组'
      this.confirm = { visible: true, title: '确认延期答辩排期', message: `将「${row.studentName}」安排到「${groupName}」并设置日期 ${draft.date}。原组和新组发布状态都会撤回，需重新核对评委回避后发布。`, type: 'primary', confirmText: '确认排期', requireReason: false, reasonLabel: '', action: 'SCHEDULE', row, decision: '' }
    },
    async onConfirm({ reason } = {}) {
      const c = this.confirm; const text = (reason || '').trim()
      if (text.length > 1000) return toast.error('填写内容不能超过 1000 字')
      if (c.action === 'NOMINATE' && text.length < 10) return toast.error('提名理由不少于 10 字')
      if (c.decision === 'REJECT' && text.length < 5) return toast.error('驳回理由不少于 5 字')
      this.submitting = true
      let res
      if (c.action === 'NOMINATE') res = await graduationMoreApi.nominateExcellent(c.row.gdStudentId, text)
      if (c.action === 'excellent-major') res = await graduationMoreApi.reviewExcellent(c.row.id, 'major', c.decision, text)
      if (c.action === 'excellent-college') res = await graduationMoreApi.reviewExcellent(c.row.id, 'college', c.decision, text)
      if (c.action === 'delay-advisor') res = await graduationMoreApi.reviewDefenseDelay(c.row.id, 'advisor', c.decision, text)
      if (c.action === 'delay-major') res = await graduationMoreApi.reviewDefenseDelay(c.row.id, 'major', c.decision, text)
      if (c.action === 'delay-college') res = await graduationMoreApi.reviewDefenseDelay(c.row.id, 'college', c.decision, text)
      if (c.action === 'SCHEDULE') {
        const draft = this.scheduleDraft(c.row)
        res = await graduationMoreApi.scheduleDefenseDelay(c.row.id, draft.groupId, draft.date)
      }
      this.submitting = false
      if (res && res.code === 0) { toast.success(c.action === 'SCHEDULE' ? '延期答辩已排期，相关答辩组待重新发布' : '处理完成并写入审核留痕'); this.confirm.visible = false; this.load() }
      else toast.error(res && res.message ? res.message : '处理失败')
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.ext-hero { display:flex; align-items:stretch; justify-content:space-between; gap:var(--space-4); padding:18px; border:1px solid #d9e8ff; border-radius:14px; background:linear-gradient(135deg,#f5f9ff 0%,#fff 70%); }
.ext-hero__main { flex:1; min-width:0; }.ext-eyebrow { display:block; color:var(--primary-600); font-size:var(--font-size-xs); }.ext-hero__main strong { display:block; margin-top:4px; color:var(--text-primary); font-size:20px; }.ext-hero__main p { margin:7px 0 0; color:var(--text-secondary); font-size:var(--font-size-sm); line-height:1.6; }
.ext-kpis { display:grid; grid-template-columns:repeat(3,minmax(100px,1fr)); gap:10px; }.ext-kpis div { padding:11px 14px; border:1px solid var(--border-light); border-radius:10px; background:#fff; }.ext-kpis span,.ext-kpis b { display:block; }.ext-kpis span { color:var(--text-tertiary); font-size:var(--font-size-xs); }.ext-kpis b { margin-top:4px; color:var(--text-primary); font-size:20px; }
.ext-main-tabs { margin-bottom:0; }.ext-filter-bar { display:flex; gap:8px; overflow:auto; padding-bottom:2px; }.ext-filter { flex:none; min-height:34px; padding:0 12px; border:1px solid var(--border-base); border-radius:999px; background:#fff; color:var(--text-secondary); cursor:pointer; }.ext-filter.is-active { border-color:var(--primary-500); background:var(--primary-50); color:var(--primary-700); }
.ext-inline-error { margin-bottom:12px; padding:10px 12px; border:1px solid #ffccc7; border-radius:8px; background:#fff2f0; color:#cf1322; font-size:var(--font-size-sm); }
.ext-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(260px,1fr)); gap:var(--space-3); }.ext-card { padding:var(--space-3); border:1px solid var(--border-light); border-radius:var(--radius-md); background:var(--card,#fff); }.ext-card__head { display:flex; justify-content:space-between; gap:var(--space-2); }.ext-card__head span,.ext-card p,.ext-card small { color:var(--text-secondary); font-size:var(--font-size-sm); }.ext-meta { display:flex; justify-content:space-between; gap:var(--space-2); margin:var(--space-2) 0; }.ext-meta b { color:var(--success-600); }
.ext-table-wrap { overflow:auto; border:1px solid var(--border-light); border-radius:10px; }.ext-table { width:100%; border-collapse:separate; border-spacing:0; min-width:980px; }.ext-table th,.ext-table td { padding:11px 12px; border-bottom:1px solid var(--border-light); text-align:left; vertical-align:top; font-size:var(--font-size-sm); line-height:1.55; }.ext-table th { position:sticky; top:0; z-index:1; color:var(--text-secondary); background:var(--gray-50); }.ext-table tbody tr:hover { background:#fafcff; }.ext-table strong,.ext-table small { display:block; }.ext-table small { margin-top:3px; color:var(--text-tertiary); }.ext-table td:first-child { position:sticky; left:0; z-index:1; min-width:170px; background:inherit; }
.ext-actions { white-space:nowrap; }.ext-actions button + button { margin-left:var(--space-2); }.ext-danger { color:var(--danger-600); }.ext-muted { color:var(--text-tertiary); font-size:var(--font-size-xs); }.ext-input { display:block; width:190px; margin-bottom:6px; padding:7px 8px; border:1px solid var(--border-base); border-radius:var(--radius-sm); background:var(--card,#fff); }
@media (max-width: 980px) {
  .ext-hero { flex-direction:column; }.ext-kpis { grid-template-columns:repeat(3,minmax(0,1fr)); }
  .ext-table,.ext-table tbody,.ext-table tr,.ext-table td { display:block; min-width:0; width:100%; }.ext-table thead { display:none; }.ext-table-wrap { overflow:visible; border:0; }.ext-table tr { margin-bottom:12px; padding:12px; border:1px solid var(--border-light); border-radius:10px; background:#fff; }.ext-table td { display:grid; grid-template-columns:110px minmax(0,1fr); gap:12px; padding:7px 0; border:0; }.ext-table td::before { content:attr(data-label); color:var(--text-tertiary); font-size:var(--font-size-xs); }.ext-table td:first-child { position:static; min-width:0; }.ext-actions { white-space:normal; }.ext-input { width:100%; }
}
@media (max-width: 620px) { .ext-kpis { grid-template-columns:1fr; }.ext-table td { grid-template-columns:1fr; gap:3px; } }
</style>
