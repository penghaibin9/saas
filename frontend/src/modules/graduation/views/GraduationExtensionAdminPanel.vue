<template>
  <ModulePageShell
    :title="activePanel === 'excellent' ? '优秀成果认定' : '延期答辩管理'"
    :subtitle="subtitle"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="mp-stack">
      <div class="mp-tabs">
        <button class="mp-tab" :class="{ 'is-active': activePanel === 'excellent' }" @click="switchPanel('excellent')">优秀成果认定</button>
        <button class="mp-tab" :class="{ 'is-active': activePanel === 'delay' }" @click="switchPanel('delay')">延期答辩</button>
      </div>

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />

      <template v-else-if="activePanel === 'excellent'">
        <section class="mp-card">
          <div class="mp-card__head">
            <div>
              <span class="mp-card__title">可提名候选</span>
              <p class="mp-note">成绩“优秀”只是候选条件；仍须导师提名、专业复核、学院终审发布。</p>
            </div>
          </div>
          <EmptyState v-if="!candidates.length" title="当前没有可提名候选" description="需满足成绩已发布且等级优秀、正式定稿已通过，并且没有进行中的优秀成果记录。" />
          <div v-else class="ext-grid">
            <article v-for="row in candidates" :key="row.gdStudentId" class="ext-card">
              <div><strong>{{ row.studentName }}</strong><span>{{ row.studentNo }} · {{ row.className }}</span></div>
              <p>{{ row.topicTitle || '未填写课题' }}</p>
              <div class="ext-meta"><span>导师 {{ row.advisorName || '—' }}</span><b>{{ row.totalScore }} 分 · 优秀</b></div>
              <button v-if="canNominate" class="mp-btn mp-btn--primary" @click="askNominate(row)">导师提名</button>
            </article>
          </div>
        </section>

        <section class="mp-card">
          <div class="mp-card__head"><span class="mp-card__title">认定台账 · {{ total }} 条</span></div>
          <EmptyState v-if="!rows.length" title="暂无优秀成果认定记录" description="导师完成提名后会进入专业、学院两级审核。" />
          <div v-else class="ext-table-wrap">
            <table class="ext-table">
              <thead><tr><th>学生 / 课题</th><th>提名理由</th><th>成绩快照</th><th>状态</th><th>审核留痕</th><th>操作</th></tr></thead>
              <tbody>
                <tr v-for="row in rows" :key="row.id">
                  <td><strong>{{ row.studentName }}</strong><small>{{ row.studentNo }} · {{ row.topicTitle }}</small></td>
                  <td>{{ row.nominationReason }}</td>
                  <td>{{ row.gradeSnapshot.totalScore ?? '—' }} · {{ row.gradeSnapshot.gradeLevel || '—' }}</td>
                  <td><StatusTag :status="row.status" :label="row.statusLabel" /></td>
                  <td><small>提名：{{ row.nominatedBy || '—' }}</small><small>专业：{{ row.majorReviewedBy || '—' }}</small><small>学院：{{ row.collegeReviewedBy || '—' }}</small></td>
                  <td class="ext-actions">
                    <template v-if="row.status === 'PENDING_MAJOR' && canMajorReview">
                      <button class="mp-link" @click="askReview('excellent-major', row, 'APPROVE')">专业通过</button>
                      <button class="mp-link ext-danger" @click="askReview('excellent-major', row, 'REJECT')">驳回</button>
                    </template>
                    <template v-else-if="row.status === 'PENDING_COLLEGE' && canCollegeExcellent">
                      <button class="mp-link" @click="askReview('excellent-college', row, 'APPROVE')">学院发布</button>
                      <button class="mp-link ext-danger" @click="askReview('excellent-college', row, 'REJECT')">驳回</button>
                    </template>
                    <span v-else class="mp-note">—</span>
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
            <div><span class="mp-card__title">延期答辩审批与排期 · {{ total }} 条</span><p class="mp-note">学生申请 → 导师审核 → 专业复核 → 学院审批 → 重新排期；不与二次答辩混用。</p></div>
          </div>
          <EmptyState v-if="!rows.length" title="当前没有延期答辩申请" description="学生进入成果检查或答辩阶段后，可从学生 PC / 小程序提交申请。" />
          <div v-else class="ext-table-wrap">
            <table class="ext-table">
              <thead><tr><th>学生 / 课题</th><th>申请理由</th><th>状态</th><th>审核留痕</th><th>排期</th><th>操作</th></tr></thead>
              <tbody>
                <tr v-for="row in rows" :key="row.id">
                  <td><strong>{{ row.studentName }}</strong><small>{{ row.studentNo }} · {{ row.topicTitle }}</small></td>
                  <td>{{ row.reason }}</td>
                  <td><StatusTag :status="row.status" :label="row.statusLabel" /></td>
                  <td><small>导师：{{ row.advisorReviewedBy || '待处理' }}</small><small>专业：{{ row.majorReviewedBy || '待处理' }}</small><small>学院：{{ row.collegeReviewedBy || '待处理' }}</small></td>
                  <td>
                    <template v-if="row.status === 'APPROVED' && canCollegeDelay">
                      <input v-model="scheduleDraft(row).date" class="ext-input" type="date" />
                      <select v-model="scheduleDraft(row).groupId" class="ext-input">
                        <option value="">选择延期答辩组</option>
                        <option v-for="g in groups" :key="g.id" :value="g.id">{{ g.groupName }} · {{ g.defenseDate || '日期待定' }}</option>
                      </select>
                    </template>
                    <template v-else>{{ row.plannedDefenseDate || '—' }}<small>{{ row.defenseGroupName || '' }}</small></template>
                  </td>
                  <td class="ext-actions">
                    <template v-if="row.status === 'PENDING_ADVISOR' && canAdvisorReview">
                      <button class="mp-link" @click="askReview('delay-advisor', row, 'APPROVE')">导师通过</button>
                      <button class="mp-link ext-danger" @click="askReview('delay-advisor', row, 'REJECT')">驳回</button>
                    </template>
                    <template v-else-if="row.status === 'PENDING_MAJOR' && canMajorDelay">
                      <button class="mp-link" @click="askReview('delay-major', row, 'APPROVE')">专业通过</button>
                      <button class="mp-link ext-danger" @click="askReview('delay-major', row, 'REJECT')">驳回</button>
                    </template>
                    <template v-else-if="row.status === 'PENDING_COLLEGE' && canCollegeDelay">
                      <button class="mp-link" @click="askReview('delay-college', row, 'APPROVE')">学院批准</button>
                      <button class="mp-link ext-danger" @click="askReview('delay-college', row, 'REJECT')">驳回</button>
                    </template>
                    <button v-else-if="row.status === 'APPROVED' && canCollegeDelay" class="mp-btn mp-btn--primary" :disabled="!scheduleDraft(row).date || !scheduleDraft(row).groupId" @click="schedule(row)">确认排期</button>
                    <span v-else class="mp-note">—</span>
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
      require-reason
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
import { matchPermission } from '@/config/navPlan'
import { graduationMoreApi } from '@/modules/graduation/api/graduation-more.api'
import { useGraduationBatchStore } from '@/stores/graduationBatch'
import { toast } from '@/utils/toast'

export default {
  name: 'GraduationExtensionAdminPanel',
  components: { ModulePageShell, StatusTag, LoadingState, ErrorState, EmptyState, AppPagination, AppConfirmDialog },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      batchStore: useGraduationBatchStore(), loading: false, error: '', rows: [], candidates: [], groups: [],
      total: 0, page: 1, pageSize: 20, submitting: false, schedules: {},
      confirm: { visible: false, title: '', message: '', type: 'primary', confirmText: '确认', reasonLabel: '说明', action: '', row: null, decision: '' }
    }
  },
  computed: {
    activePanel() { return this.$route.query.extension === 'delay' ? 'delay' : 'excellent' },
    patterns() { return this.ctx.permissionPatterns || [] },
    canNominate() { return matchPermission(this.patterns, 'graduationDesign.grade.view') },
    canMajorReview() { return matchPermission(this.patterns, 'graduationDesign.grade.review') },
    canCollegeExcellent() { return matchPermission(this.patterns, 'graduationDesign.grade.publish') },
    canAdvisorReview() { return matchPermission(this.patterns, 'graduationDesign.defense.view') },
    canMajorDelay() { return matchPermission(this.patterns, 'graduationDesign.defense.groupManage') },
    canCollegeDelay() { return matchPermission(this.patterns, 'graduationDesign.defense.groupManage') },
    subtitle() {
      const batch = this.batchStore.selectedBatchName || '当前批次'
      return this.activePanel === 'excellent'
        ? `${batch} · 成绩优秀只是候选，须形成导师、专业、学院三级证据`
        : `${batch} · 延期申请与二次答辩分开管理，排期后答辩组必须重新发布`
    }
  },
  watch: {
    '$route.query.extension'() { this.page = 1; this.load() },
    'batchStore.selectedBatchId'() { this.page = 1; this.load() }
  },
  created() { this.load() },
  methods: {
    switchPanel(panel) { this.$router.replace({ query: { ...this.$route.query, extension: panel } }) },
    turnPage(page) { this.page = page; this.load() },
    scheduleDraft(row) {
      if (!this.schedules[row.id]) this.schedules[row.id] = { date: row.plannedDefenseDate || '', groupId: row.defenseGroupId || '' }
      return this.schedules[row.id]
    },
    async load() {
      if (!this.batchStore.selectedBatchId) { this.rows = []; this.candidates = []; this.total = 0; return }
      this.loading = true; this.error = ''
      if (this.activePanel === 'excellent') {
        const [records, candidates] = await Promise.all([
          graduationMoreApi.getExcellentOutcomes({ page: this.page, pageSize: this.pageSize }),
          graduationMoreApi.getExcellentCandidates({ page: 1, pageSize: 50 })
        ])
        if (records.code === 0) { this.rows = records.data.list; this.total = records.data.total } else this.error = records.message
        this.candidates = candidates.code === 0 ? candidates.data.list : []
      } else {
        const [records, groups] = await Promise.all([
          graduationMoreApi.getDefenseDelays({ page: this.page, pageSize: this.pageSize }),
          graduationMoreApi.getDefenseGroups()
        ])
        if (records.code === 0) { this.rows = records.data.list; this.total = records.data.total } else this.error = records.message
        this.groups = groups.code === 0 ? groups.data.list : []
      }
      this.loading = false
    },
    askNominate(row) {
      this.confirm = { visible: true, title: '提名优秀成果', message: `确认提名「${row.studentName}」的毕业设计为优秀成果候选？`, type: 'primary', confirmText: '提交提名', reasonLabel: '提名理由（不少于10字）', action: 'NOMINATE', row, decision: '' }
    },
    askReview(action, row, decision) {
      const reject = decision === 'REJECT'
      this.confirm = { visible: true, title: reject ? '驳回申请' : '审核通过', message: `处理「${row.studentName}」：${row.statusLabel}`, type: reject ? 'danger' : 'primary', confirmText: reject ? '确认驳回' : '确认通过', reasonLabel: reject ? '驳回理由（不少于5字）' : '审核意见', action, row, decision }
    },
    async onConfirm({ reason } = {}) {
      const c = this.confirm; const text = (reason || '').trim()
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
      this.submitting = false
      if (res && res.code === 0) { toast.success('处理完成并写入审核留痕'); this.confirm.visible = false; this.load() }
      else toast.error(res?.message || '处理失败')
    },
    async schedule(row) {
      const draft = this.scheduleDraft(row)
      const res = await graduationMoreApi.scheduleDefenseDelay(row.id, draft.groupId, draft.date)
      if (res.code === 0) { toast.success('延期答辩已排期，答辩组待重新发布'); this.load() }
      else toast.error(res.message)
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.ext-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(260px,1fr)); gap:var(--space-3); }
.ext-card { padding:var(--space-3); border:1px solid var(--border-light); border-radius:var(--radius-md); background:var(--card,#fff); }
.ext-card div:first-child { display:flex; justify-content:space-between; gap:var(--space-2); }.ext-card span,.ext-card p,.ext-card small { color:var(--text-secondary); font-size:var(--font-size-sm); }
.ext-meta { display:flex; justify-content:space-between; gap:var(--space-2); margin:var(--space-2) 0; }.ext-meta b { color:var(--success-600); }
.ext-table-wrap { overflow:auto; }.ext-table { width:100%; border-collapse:collapse; min-width:920px; }.ext-table th,.ext-table td { padding:10px 12px; border-bottom:1px solid var(--border-light); text-align:left; vertical-align:top; font-size:var(--font-size-sm); }
.ext-table th { color:var(--text-secondary); background:var(--gray-50); }.ext-table strong,.ext-table small { display:block; }.ext-table small { margin-top:3px; color:var(--text-tertiary); }
.ext-actions { white-space:nowrap; }.ext-actions button + button { margin-left:var(--space-2); }.ext-danger { color:var(--danger-600); }
.ext-input { display:block; width:170px; margin-bottom:6px; padding:7px 8px; border:1px solid var(--border-base); border-radius:var(--radius-sm); background:var(--card,#fff); }
</style>
