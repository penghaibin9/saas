<template>
  <ModulePageShell
    title="学院成绩审核"
    subtitle="逐项核对当前任务，再通过或退回教师"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="mp-stack">
      <div v-if="focusTaskId" class="aa-focus-note">已从教务待办精确定位成绩任务 {{ focusTaskId }} <button class="mp-btn" :disabled="busy" @click="returnQueue">返回责任队列</button></div>
      <section v-if="receipt && (!selectedId || String(receipt.taskId) === selectedId)" class="aa-review-receipt" role="status">
        <div><strong>{{ receipt.verified ? '已回读正式任务' : '结果待核实' }}</strong><span>{{ receipt.courseName }} · 任务 {{ receipt.taskId }}</span></div>
        <div><small>当前结果</small><b>{{ statusLabel(receipt.status) }}</b></div>
        <div><small>下一步</small><b>{{ receipt.next }}</b></div>
        <button v-if="!receipt.verified" class="mp-btn" :disabled="checking" @click="verifyReceipt">核对正式状态</button>
      </section>
      <template v-if="current">
        <section class="aa-review-context" aria-label="当前学院审核任务">
          <div><span>当前正式成绩任务</span><h2>{{ current.courseName }}</h2><p>{{ current.termCode || '学期待核对' }} · 任务 {{ current.gradeTaskId }} · 教学班 {{ current.teachingClassId || '待核对' }}</p></div>
          <div class="aa-review-context__roles"><div><small>当前责任</small><strong>{{ reviewResponsibility }}</strong></div><div><small>当前责任人</small><strong>{{ evidence?.workflow?.assigneeId ? `办理人 ${evidence.workflow.assigneeId}` : '按正式审核分派' }}</strong></div></div>
          <AppStatusTag type="primary">{{ statusLabel(current.status) }}</AppStatusTag>
        </section>
        <ol class="aa-review-steps" aria-label="成绩审核阶段">
          <li v-for="(step, index) in reviewSteps" :key="step" :class="{ 'is-done': index < reviewStage, 'is-current': index === reviewStage && index < 3 }" :aria-current="index === reviewStage && index < 3 ? 'step' : undefined"><span>{{ index < reviewStage ? '✓' : index + 1 }}</span><div><strong>{{ step }}</strong><small>{{ index > 2 ? '结果单独核对' : index === reviewStage ? '当前正式节点' : index < reviewStage ? '前序已完成' : '等待前序完成' }}</small></div></li>
        </ol>
      </template>
      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <div v-else class="aa-review-workspace">
        <aside class="aa-review-queue" aria-label="学院审核责任队列">
          <h3>责任队列 <small>{{ pagination.total }} 项</small></h3>
          <EmptyState v-if="!rows.length" title="暂无待审核任务" description="任课教师提交后进入本队列" />
          <button v-for="row in rows" :key="row.gradeTaskId" :class="['aa-review-queue-item', { 'is-active': String(current?.gradeTaskId) === String(row.gradeTaskId) }]" :disabled="busy" @click="selectTask(row.gradeTaskId)">
            <strong>{{ row.courseName }}</strong><span>{{ row.termCode }} · 任务 {{ row.gradeTaskId }}</span><AppStatusTag type="primary">{{ statusLabel(row.status) }}</AppStatusTag>
          </button>
          <div class="aa-review-pages"><button class="mp-btn" :disabled="pagination.page <= 1" @click="onPageChange(pagination.page - 1)">上一页</button><span>{{ pagination.page }}</span><button class="mp-btn" :disabled="pagination.page * pagination.pageSize >= pagination.total" @click="onPageChange(pagination.page + 1)">下一页</button></div>
        </aside>
        <div class="aa-review-detail">
          <section v-if="current" class="aa-review-metrics" aria-label="正式成绩审核摘要">
            <article><small>应录 / 已录</small><strong>{{ fact(evidence?.counts?.expected) }} / {{ fact(evidence?.counts?.entered) }}</strong><span>提交冻结名单口径</span></article>
            <article><small>名单外</small><strong>{{ fact(evidence?.counts?.outside) }}</strong><span>按正式名单逐人核对</span></article>
            <article><small>异常标记</small><strong>{{ exceptionTotal }}</strong><span>不含正常成绩记录</span></article>
            <article><small>审核阻断</small><strong>{{ blockerCount }}</strong><span>{{ evidence?.evidenceHash ? '已取得正式证据' : '证据待读取' }}</span></article>
          </section>
          <LoadingState v-if="detailLoading" />
          <ErrorState v-else-if="detailError" :description="detailError" @retry="selectTask(selectedId)" />
          <GradeReviewEvidence v-else-if="current" :task="current" :evidence="evidence" :loading="evidenceLoading" :error="evidenceError" compact>
            <button class="mp-btn" :disabled="busy" @click="selectTask(current.gradeTaskId)">重新读取证据</button>
            <button v-if="canReturn" class="mp-btn" :disabled="busy || !!pending" @click="openReview('RETURN')">退回教师修改</button>
            <button v-if="canReview" class="mp-btn mp-btn--primary" :disabled="busy || !!pending || !canApprove" :title="canApprove ? '' : '需取得无阻断项的正式审核证据'" @click="openReview('APPROVE')">通过并交教务</button>
            <span v-if="canReview && !canApprove">正式证据缺失、已变化或仍有阻断项，暂不能通过</span>
            <span v-if="!canReview">当前状态或身份不允许学院审核</span>
          </GradeReviewEvidence>
          <EmptyState v-else title="选择需要办理的任务" description="指定任务无法读取时，不会改选其他对象" />
        </div>
      </div>
    </div>

    <AppConfirmDialog
      v-model:visible="dlg.visible"
      :title="dlg.title"
      :type="dlg.type"
      :confirm-text="dlg.confirmText"
      :confirm-disabled="confirmDisabled"
      :submitting="busy"
      @confirm="doReview"
    >
      <p>{{ dlg.courseName }} · 任务 {{ dlg.taskId }}</p>
      <p>正在办理上述成绩任务；提交前将再次核对正式名单和成绩是否变化。</p>
      <details v-if="dlg.action === 'APPROVE'" class="aa-review-hash"><summary>实施人员使用：证据校验摘要</summary>{{ dlg.evidenceHash || '未提供' }}</details>
      <label class="aa-review-reason">审核意见{{ dlg.action === 'RETURN' ? '（至少 5 字）' : '（可选）' }}<textarea v-model="reviewReason" :disabled="busy" rows="4" :placeholder="dlg.action === 'RETURN' ? '请填写需修改的具体事项' : '可填写审核说明'" /></label>
      <p v-if="reviewMessage" role="alert">{{ reviewMessage }}</p>
      <button v-if="reviewConflict" class="mp-btn" :disabled="busy || checking" @click="refreshReview">重新核对当前任务</button>
    </AppConfirmDialog>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppStatusTag, AppConfirmDialog } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { currentUserFromToken } from '@/services/http/client'
import GradeReviewEvidence from './parallel-c/GradeReviewEvidence.vue'
import { gradeStatusLabel, gradeError } from './parallel-c/grade-review.js'

export default {
  name: 'AaGradeCollegeReviewView',
  components: { ModulePageShell, LoadingState, ErrorState, EmptyState, AppStatusTag, AppConfirmDialog, GradeReviewEvidence },
  props: { ctx: { type: Object, required: true } },
  inject: { academicFlow: { default: null } },
  data() {
    return { loading: true, error: '', rows: [], focusTaskId: '', current: null, evidence: null, evidenceLoading: false, evidenceError: '', selectedId: '', detailLoading: false, detailError: '',
      listSeq: 0, detailSeq: 0, alive: true, busy: false, checking: false, pending: null, receipt: null, reviewReason: '', reviewDraftTaskId: '', reviewConflict: false, reviewMessage: '',
      pagination: { page: 1, pageSize: 20, total: 0 }, dlg: { visible: false, action: '', taskId: '', courseName: '', title: '', type: 'primary', confirmText: '确认', requireReason: false } }
  },
  computed: {
    identityKey() { const u = currentUserFromToken() || {}; return JSON.stringify([u.tenantId, u.userId, u.activeContextId, u.currentRoleCode, this.ctx.currentRole, this.ctx.dataScope]) },
    routeKey() { return String(this.$route?.fullPath || '') },
    canReview() { return this.current?.status === 'SUBMITTED' && this.current.allowedActions?.includes('COLLEGE_REVIEW') },
    canReturn() { return this.canReview },
    reviewSteps() { return [this.current?.status === 'RETURNED' ? '教师修改重提' : '提交冻结名单', '学院审核', '教务发布', '后置扫描', '更正留痕'] },
    reviewStage() {
      const status = this.current?.status
      if (['NOT_STARTED', 'INPUTTING', 'RETURNED'].includes(status)) return 0
      if (['SUBMITTED', 'COLLEGE_REVIEW'].includes(status)) return 1
      if (status === 'ACADEMIC_REVIEW') return 2
      // 发布不证明后置扫描成功，更正也不是每个任务的必经环节。
      if (['PUBLISHED', 'ARCHIVED'].includes(status)) return 3
      return -1
    },
    reviewResponsibility() {
      return ({ NOT_STARTED: '任课教师', INPUTTING: '任课教师', RETURNED: '任课教师修改重提', SUBMITTED: '学院成绩审核岗', COLLEGE_REVIEW: '学院成绩审核岗', ACADEMIC_REVIEW: '教务成绩发布岗', PUBLISHED: '已发布，后置结果待核对', ARCHIVED: '已归档，只读核对' })[this.current?.status] || '责任节点待核对'
    },
    exceptionTotal() {
      const values = this.evidence?.exceptions
      if (!values || Array.isArray(values) || typeof values !== 'object') return '待核对'
      const entries = Object.entries(values).filter(([flag]) => flag !== 'NORMAL')
      if (!entries.length || entries.some(([, value]) => !Number.isInteger(value) || value < 0)) return '待核对'
      return entries.reduce((sum, [, value]) => sum + value, 0)
    },
    blockerCount() { return Array.isArray(this.evidence?.blockers) ? this.evidence.blockers.length : '待核对' },
    canApprove() {
      return this.canReview && !this.evidenceLoading && !this.evidenceError &&
        String(this.evidence?.gradeTaskId || '') === String(this.current?.gradeTaskId || '') &&
        this.evidence?.status === 'SUBMITTED' && !!this.evidence?.evidenceHash &&
        Array.isArray(this.evidence?.blockers) && this.evidence.blockers.length === 0 &&
        this.evidence?.allowedActions?.includes('APPROVE')
    },
    confirmDisabled() {
      if (this.reviewConflict || this.busy || this.checking) return true
      if (this.dlg.action === 'RETURN') return this.reviewReason.trim().length < 5
      return this.dlg.action !== 'APPROVE' || !this.canApprove ||
        String(this.dlg.taskId || '') !== String(this.current?.gradeTaskId || '') ||
        this.dlg.evidenceHash !== this.evidence?.evidenceHash ||
        this.dlg.identity !== this.identityKey || this.dlg.route !== this.routeKey
    }
  },
  watch: {
    identityKey() { this.invalidate(); this.pending = null; this.receipt = null; this.pagination.page = 1; this.load() },
    '$route.fullPath'() { this.invalidate(); this.load() }
  },
  created() { this.load() },
  beforeUnmount() { this.alive = false; this.invalidate() },
  methods: {
    statusLabel: gradeStatusLabel,
    fact(value) { return value === null || value === undefined || value === '' ? '待核对' : value },
    returnQueue() {
      if (this.busy) return
      if (this.$route.query.returnToken && this.academicFlow) return this.academicFlow.back(this.$route.query.returnToken, '/admin/academic-affairs/grade-overview')
      const query = { ...this.$route.query }; delete query.taskId; this.$router.replace({ path: this.$route.path, query })
    },
    invalidate() { this.listSeq++; this.detailSeq++; this.current = null; this.evidence = null; this.evidenceLoading = false; this.evidenceError = ''; this.rows = []; this.selectedId = ''; this.dlg.visible = false; this.busy = false; this.detailLoading = false; this.detailError = ''; this.checking = false; this.reviewReason = ''; this.reviewDraftTaskId = ''; this.reviewConflict = false; this.reviewMessage = '' },
    isDenied(result) { return /403|NO_DATA_SCOPE|NO_PERMISSION|FORBIDDEN/.test([result?.status, result?.statusCode, result?.bizCode, result?.code].join(' ')) },
    clearDenied(result) {
      this.invalidate(); this.pending = null; this.receipt = null; this.focusTaskId = ''; this.pagination.total = 0; this.loading = false
      this.dlg = { visible: false, action: '', taskId: '', courseName: '', title: '', type: 'primary', confirmText: '确认', requireReason: false }
      this.error = gradeError(result)
    },
    async refreshReview() {
      if (!this.reviewConflict || this.busy || this.checking || !this.dlg.visible) return
      const command = { ...this.dlg }
      const valid = () => this.alive && command.identity === this.identityKey && command.route === this.routeKey && command.seq === this.detailSeq
      this.checking = true
      try {
        const task = await this.readTask(command.taskId)
        if (!valid()) return
        this.current = task
        let evidence = null
        if (command.action === 'APPROVE') {
          evidence = await this.readEvidence(command.taskId)
          if (!valid()) return
          this.evidence = evidence; this.evidenceError = ''
        }
        const actionAllowed = command.action === 'RETURN'
          ? task.status === 'SUBMITTED' && task.allowedActions?.includes('COLLEGE_REVIEW')
          : task.status === 'SUBMITTED' && evidence?.status === 'SUBMITTED' && !!evidence?.evidenceHash &&
            Array.isArray(evidence?.blockers) && evidence.blockers.length === 0 && evidence?.allowedActions?.includes('APPROVE')
        if (actionAllowed) {
          this.dlg = { ...this.dlg, evidenceHash: command.action === 'APPROVE' ? evidence.evidenceHash : null }
          this.reviewConflict = false
          this.reviewMessage = '正式事实已重新读取，审核意见已保留；请核对新证据后再次点击确认。'
        } else this.reviewMessage = '当前正式事实已不允许该动作，意见已保留，请取消确认并查看任务。'
      } catch (err) { if (valid()) { if (this.isDenied(err)) this.clearDenied(err); else this.reviewMessage = gradeError(err) } }
      finally { if (valid()) this.checking = false }
    },
    onPageChange(page) { this.pagination.page = page; this.load() },
    async readTask(taskId) {
      const res = await academicAffairsApi.getGradeTasks({ taskId, page: 1, pageSize: 1 })
      if (res?.code !== 0) throw res
      const row = res.data?.list?.find(item => String(item.gradeTaskId) === String(taskId))
      if (!row) throw { code: 404 }
      return row
    },
    async readEvidence(taskId) {
      const res = await academicAffairsApi.getGradeReviewEvidence(taskId)
      if (res?.code !== 0) throw res
      const evidence = res.data
      if (!evidence || String(evidence.gradeTaskId || '') !== String(taskId)) throw { code: 'GRADE_REVIEW_EVIDENCE_MISMATCH', message: '审核证据与当前任务不一致' }
      return evidence
    },
    async load() {
      const seq = ++this.listSeq, identity = this.identityKey
      const valid = () => this.alive && seq === this.listSeq && identity === this.identityKey
      this.loading = true; this.error = ''; this.focusTaskId = String(this.$route?.query?.taskId || '')
      try {
        const res = await academicAffairsApi.getGradeTasks({ status: 'SUBMITTED', taskId: this.focusTaskId || undefined, page: this.pagination.page, pageSize: this.pagination.pageSize })
        if (!valid()) return
        if (res?.code !== 0) throw res
        this.rows = res.data?.list || []; this.pagination.total = res.data?.total || 0
        const id = this.focusTaskId || this.selectedId
        if (id) await this.selectTask(id)
      } catch (err) { if (valid()) { if (this.isDenied(err)) this.clearDenied(err); else this.error = gradeError(err) } }
      finally { if (valid()) this.loading = false }
    },
    async selectTask(taskId) {
      if (this.busy) return
      const seq = ++this.detailSeq, identity = this.identityKey
      const valid = () => this.alive && seq === this.detailSeq && identity === this.identityKey
      this.selectedId = String(taskId); this.current = null; this.evidence = null; this.evidenceError = ''; this.detailError = ''; this.detailLoading = true; this.evidenceLoading = false; this.dlg.visible = false; this.reviewConflict = false; this.reviewMessage = ''
      try {
        const row = await this.readTask(taskId)
        if (!valid()) return
        this.current = row; this.detailLoading = false; this.evidenceLoading = true
        try {
          const evidence = await this.readEvidence(taskId)
          if (valid()) this.evidence = evidence
        } catch (err) {
          if (valid()) {
            if (this.isDenied(err)) { this.clearDenied(err); return }
            this.evidenceError = gradeError(err, '正式审核证据读取失败，暂不能通过。')
          }
        } finally { if (valid()) this.evidenceLoading = false }
      }
      catch (err) { if (valid()) { if (this.isDenied(err)) this.clearDenied(err); else this.detailError = gradeError(err) } }
      finally { if (valid()) this.detailLoading = false }
    },
    openReview(action) {
      if (!['RETURN', 'APPROVE'].includes(action) || this.busy || this.pending) return
      if ((action === 'RETURN' && !this.canReturn) || (action === 'APPROVE' && !this.canApprove)) return
      if (String(this.reviewDraftTaskId) !== String(this.current.gradeTaskId)) { this.reviewReason = ''; this.reviewConflict = false; this.reviewMessage = '' }
      this.reviewDraftTaskId = String(this.current.gradeTaskId)
      this.dlg = { visible: true, action, taskId: this.current.gradeTaskId, courseName: this.current.courseName, evidenceHash: action === 'APPROVE' ? this.evidence.evidenceHash : null,
        identity: this.identityKey, route: this.routeKey, seq: this.detailSeq,
        title: action === 'RETURN' ? '退回教师修改' : '通过并交教务', type: action === 'RETURN' ? 'warning' : 'primary', confirmText: action === 'RETURN' ? '确认退回' : '确认通过并交教务', requireReason: action === 'RETURN' }
    },
    async doReview(payload) {
      const command = { ...this.dlg, reason: String(payload?.reason || this.reviewReason).trim() }
      if (!['RETURN', 'APPROVE'].includes(command.action) || this.reviewConflict || this.busy || this.pending || !command.visible || command.identity !== this.identityKey || command.route !== this.routeKey || command.seq !== this.detailSeq) return
      if (command.action === 'RETURN' && command.reason.length < 5) return
      if (command.action === 'APPROVE' && (!command.evidenceHash || command.evidenceHash !== this.evidence?.evidenceHash || !this.canApprove)) return
      const valid = () => this.alive && command.identity === this.identityKey && command.route === this.routeKey && command.seq === this.detailSeq
      this.reviewReason = command.reason
      this.busy = true
      try {
        const before = await this.readTask(command.taskId)
        if (!valid()) return
        this.current = before
        if (before.status !== 'SUBMITTED' || !before.allowedActions?.includes('COLLEGE_REVIEW')) {
          this.reviewConflict = true; this.reviewMessage = '当前任务状态或责任已变化，审核意见已保留，请重新核对。'; return
        }
        if (command.action === 'APPROVE') {
          const freshEvidence = await this.readEvidence(command.taskId)
          if (!valid()) return
          this.evidence = freshEvidence; this.evidenceError = ''
          const evidenceAllowed = freshEvidence.status === 'SUBMITTED' && !!freshEvidence.evidenceHash &&
            Array.isArray(freshEvidence.blockers) && freshEvidence.blockers.length === 0 && freshEvidence.allowedActions?.includes('APPROVE')
          if (!evidenceAllowed || freshEvidence.evidenceHash !== command.evidenceHash) {
            this.reviewConflict = true
            this.reviewMessage = '正式审核证据已变化或出现阻断项，本次未提交。审核意见已保留，请重新核对证据后再次确认。'
            return
          }
        }
        this.pending = { ...command, responseAccepted: false, unknownResponse: false }
        this.receipt = { taskId: command.taskId, courseName: command.courseName, status: null, verified: false, next: '正在办理，随后核对正式状态' }
        let res
        try { res = await academicAffairsApi.collegeReviewGrade(command.taskId, command.action, command.reason, command.action === 'APPROVE' ? command.evidenceHash : null) }
        catch (err) { res = err }
        if (!valid()) return
        if (res && res.code !== 0 && this.isDenied(res)) { this.clearDenied(res); return }
        const resultCode = [res?.status, res?.statusCode, res?.bizCode, res?.code].join(' ')
        if (res && res.code !== 0 && /409|CONFLICT|STALE/.test(resultCode)) {
          this.pending = null; this.receipt = null; this.reviewConflict = true; this.reviewMessage = '任务或审核证据已变化，本次未受理。意见已保留，请先重新核对正式事实。'; return
        }
        this.dlg.visible = false
        if (res && res.code !== 0 && /403|404|409|422|NO_PERMISSION|FORBIDDEN|NOT_FOUND|CONFLICT|VALIDATION/.test(resultCode)) {
          this.pending = null; this.receipt = null; this.detailError = gradeError(res, '本次审核未受理，请重新核对任务。'); return
        }
        const responseAccepted = res?.code === 0 && String(res.data?.gradeTaskId) === String(command.taskId) && res.data?.status === (command.action === 'APPROVE' ? 'ACADEMIC_REVIEW' : 'RETURNED')
        this.pending = { ...this.pending, responseAccepted, unknownResponse: !responseAccepted }
        await this.verifyReceipt()
      } catch (err) { if (valid()) { if (this.isDenied(err)) this.clearDenied(err); else this.detailError = gradeError(err, '未能读取当前任务，本次未提交审核。') } }
      finally { if (valid()) this.busy = false }
    },
    async verifyReceipt() {
      if (!this.pending || this.checking) return
      const command = this.pending, identity = this.identityKey, route = this.routeKey
      const valid = () => this.alive && identity === this.identityKey && route === this.routeKey && this.pending === command
      this.checking = true
      this.receipt = { taskId: command.taskId, courseName: command.courseName, status: null, verified: false, next: '仅核对正式状态，请勿重复提交审核' }
      try {
        const row = await this.readTask(command.taskId)
        if (!valid()) return
        const targetReached = command.action === 'RETURN' ? row.status === 'RETURNED' : ['ACADEMIC_REVIEW', 'PUBLISHED', 'ARCHIVED'].includes(row.status)
        const verified = command.responseAccepted === true && targetReached
        const next = command.unknownResponse
          ? `已读取当前正式状态“${this.statusLabel(row.status)}”，但无法证明由本次命令产生；请勿重复提交`
          : verified
            ? (row.status === 'RETURNED' ? '任课教师修改后重新提交' : row.status === 'ACADEMIC_REVIEW' ? '教务处终审发布' : '查看正式任务后续状态')
            : '命令已有响应，正式状态仍待核实；请勿重复提交审核'
        this.receipt = { taskId: command.taskId, courseName: command.courseName, status: row.status, verified, next }
        if (String(this.selectedId) === String(command.taskId)) this.current = row
        if (row.status === 'SUBMITTED') {
          try { const evidence = await this.readEvidence(command.taskId); if (valid()) { this.evidence = evidence; this.evidenceError = '' } }
          catch (err) { if (valid()) { if (this.isDenied(err)) { this.clearDenied(err); return } this.evidenceError = gradeError(err, '正式审核证据读取失败。') } }
        } else { this.evidence = null; this.evidenceError = '' }
        if (verified) { this.reviewReason = ''; this.reviewDraftTaskId = ''; this.pending = null; const listed = this.rows.some(item => String(item.gradeTaskId) === String(command.taskId)); this.rows = this.rows.filter(item => String(item.gradeTaskId) !== String(command.taskId)); if (listed) this.pagination.total = Math.max(0, this.pagination.total - 1) }
      } catch (err) { if (valid() && this.isDenied(err)) this.clearDenied(err) }
      finally { if (this.alive && identity === this.identityKey && route === this.routeKey) this.checking = false }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-review-detail { display: grid; gap: 16px; min-width: 0; }
.aa-review-detail .aa-review-metrics strong { color: var(--text-primary); font-size: 24px; }
.aa-review-detail .aa-review-metrics article { min-width: 0; padding: 14px; }
.aa-focus-note { padding: 9px 12px; border: 1px solid #bfdbfe; border-radius: 8px; background: var(--pri-bg); color: var(--pri); font-size: 12px; }
.aa-review-receipt { display: grid; grid-template-columns: minmax(0,1fr) auto auto; gap: 18px; padding: 12px 14px; border: 1px solid var(--border-base); border-radius: 9px; background: var(--bg-card); }
.aa-review-receipt strong, .aa-review-receipt span, .aa-review-receipt small, .aa-review-receipt b { display: block; }.aa-review-receipt strong { color: var(--text-primary); }.aa-review-receipt span, .aa-review-receipt small { margin-top: 3px; color: var(--text-secondary); font-size: 12px; }.aa-review-receipt b { margin-top: 3px; font-size: 12px; }
.aa-review-workspace { display: grid; grid-template-columns: 250px minmax(0,1fr); gap: 16px; align-items: start; }
.aa-review-queue { border: 1px solid var(--border-base); background: var(--bg-card); border-radius: 10px; overflow: hidden; }.aa-review-queue h3 { margin: 0; padding: 16px; font-size: 15px; }.aa-review-queue small { font-weight: 400; color: var(--text-secondary); }
.aa-review-queue-item { display: grid; width: 100%; gap: 8px; padding: 14px; text-align: left; color: var(--text-primary); background: transparent; border: 0; border-top: 1px solid var(--border-base); cursor: pointer; }.aa-review-queue-item span { color: var(--text-secondary); font-size: 12px; }.aa-review-queue-item.is-active { background: var(--pri-bg); box-shadow: inset 3px 0 var(--pri); }
.aa-review-reason { display: grid; gap: 8px; font-size: 13px; }.aa-review-reason textarea { width: 100%; box-sizing: border-box; padding: 10px; color: var(--text-primary); background: var(--bg-card); border: 1px solid var(--border-base); border-radius: 6px; }
.aa-review-pages { display: flex; align-items: center; justify-content: space-between; padding: 12px; gap: 6px; }
.aa-review-context { display: grid; grid-template-columns: minmax(0, 1fr) auto auto; align-items: center; gap: 24px; padding: 15px 16px; border: 1px solid #dbe5f2; border-left: 3px solid var(--pri); border-radius: 11px; background: var(--bg-card); }
.aa-review-context > div:first-child > span, .aa-review-context p, .aa-review-context__roles small { color: var(--text-secondary); font-size: 12px; }
.aa-review-context h2 { margin: 4px 0; color: var(--text-primary); font-size: 17px; }.aa-review-context p { margin: 0; }
.aa-review-context__roles { display: grid; grid-template-columns: repeat(2, minmax(130px, 1fr)); gap: 22px; }.aa-review-context__roles small, .aa-review-context__roles strong { display: block; }.aa-review-context__roles strong { margin-top: 4px; font-size: 12px; }
.aa-review-steps { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 0; margin: 0; padding: 15px 16px; list-style: none; border: 1px solid #e4eaf2; border-radius: 11px; background: var(--bg-card); }
.aa-review-steps li { display: flex; gap: 9px; align-items: flex-start; min-width: 0; color: var(--text-tertiary); }.aa-review-steps li > span { display: grid; place-items: center; flex: 0 0 24px; height: 24px; border: 1px solid #dce3ec; border-radius: 50%; font-size: 11px; }.aa-review-steps strong, .aa-review-steps small { display: block; white-space: nowrap; }.aa-review-steps strong { color: var(--text-secondary); font-size: 12px; }.aa-review-steps small { margin-top: 3px; font-size: 10px; }.aa-review-steps .is-done > span { color: #267a4b; border-color: #b9dfc8; background: #f0faf4; }.aa-review-steps .is-current > span { color: #fff; border-color: var(--pri); background: var(--pri); }.aa-review-steps .is-current strong { color: var(--pri); }
.aa-review-metrics { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }.aa-review-metrics article { padding: 14px 16px; border: 1px solid #e2e8f0; border-radius: 11px; background: var(--bg-card); }.aa-review-metrics small, .aa-review-metrics strong, .aa-review-metrics span { display: block; }.aa-review-metrics small, .aa-review-metrics span { color: var(--text-secondary); font-size: 11px; }.aa-review-metrics strong { margin: 6px 0 4px; color: #24364f; font-size: 20px; }
@media (max-width: 980px) { .aa-review-context { grid-template-columns: 1fr; }.aa-review-steps { overflow-x: auto; grid-template-columns: repeat(5, minmax(150px, 1fr)); }.aa-review-metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 760px) { .aa-review-workspace, .aa-review-metrics { grid-template-columns: 1fr; }.aa-review-receipt { grid-template-columns: 1fr; gap: 10px; }.aa-review-context__roles { grid-template-columns: 1fr; gap: 10px; } }
</style>
