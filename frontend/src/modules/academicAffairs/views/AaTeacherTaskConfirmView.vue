<template>
  <ModulePageShell
    title="教师任务确认"
    subtitle="本人确认不授予修改全校任务权限"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
    show-subtitle-in-concise
  >
    <template #actions>
      <button class="mp-btn mp-btn--ghost" @click="$router.push('/admin/academic-affairs/teacher/today')">返回今日教学</button>
      <button class="mp-btn mp-btn--ghost" :disabled="loading || Boolean(focusTaskId)" @click="toggleHistory">{{ showHistory ? '返回当前学期' : '历史任务' }}</button>
      <button class="mp-btn mp-btn--ghost" :disabled="loading" @click="load">刷新</button>
    </template>

    <div class="teacher-task mp-stack">
      <AaOperationReceipt :receipt="receipt" />
      <div v-if="receipt && receipt.pending === false" class="teacher-task__next">
        <span>本次办理已形成正式状态；后续进度会回到“今日教学”的办理中。</span>
        <button class="mp-btn mp-btn--ghost" @click="$router.push('/admin/academic-affairs/teacher/today?work=waiting')">返回今日教学</button>
        <button v-if="primaryRow?.status === 'READY'" class="mp-btn mp-btn--ghost" @click="$router.push('/admin/academic-affairs/schedule/teacher')">查看个人课表</button>
      </div>
      <button v-if="pendingCommand" class="mp-btn mp-btn--ghost" :disabled="loading || Boolean(acting)" @click="queryPending">查询原办理结果（不会重提）</button>
      <AaTeachingTaskObjectBar
        v-if="primaryRow"
        :name="`${primaryRow.courseName || '课程'} · ${primaryRow.teachingClassName || '教学班'}`"
        :identity="`本人教学任务 #${primaryRow.taskId} · ${primaryRow.courseCode || '课程代码待提供'}`"
        source="来源：学院已分配至当前登录教师的稳定工号；本入口不能代办他人任务。"
        :status="statusLabel(primaryRow.status)"
        owner="当前正式任课教师"
        next-owner="学院任务核对岗"
      />
      <AaTeachingTaskStageRail :current="3" current-note="当前教师本人确认" />
      <section v-if="!loading && !error" class="teacher-task__summary">
        <article>
          <span>等待本人确认</span>
          <strong>{{ counts.assigned }}</strong>
          <small>请优先处理，避免阻塞学院确认</small>
        </article>
        <article>
          <span>已确认</span>
          <strong>{{ counts.confirmed }}</strong>
          <small>等待学院核对或教务终审</small>
        </article>
        <article>
          <span>已退回学院</span>
          <strong>{{ counts.rejected }}</strong>
          <small>学院重新分配后会再次出现</small>
        </article>
        <article>
          <span>已就绪</span>
          <strong>{{ counts.ready }}</strong>
          <small>可进入排课和后续教学运行</small>
        </article>
      </section>

      <section class="teacher-task__notice">
        <strong>{{ showHistory ? '历史教学任务' : '当前学期教学任务' }}</strong>
        <span>{{ showHistory ? '历史任务仅供查询；默认工作队列只显示当前学期。' : `当前学期：${currentTermName || currentTermId || '待确认'}。确认前请核对课程、教学班、周学时、授课周次和预计人数。` }}</span>
      </section>

      <section class="teacher-task__filters">
        <button
          v-for="item in filters"
          :key="item.value"
          type="button"
          :class="{ active: statusFilter === item.value }"
          @click="statusFilter = item.value"
        >{{ item.label }} <span>{{ item.count }}</span></button>
        <input v-model.trim="keyword" class="teacher-task__search" placeholder="搜索课程或教学班" />
      </section>

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState
        v-else-if="!filteredRows.length"
        :title="statusFilter === 'ASSIGNED' ? '当前没有待确认任务' : '没有符合条件的教学任务'"
        description="学院分配并绑定您的稳定教师工号后，任务会出现在这里"
      />
      <DataTable v-else :columns="columns" :rows="filteredRows" row-key="taskId">
        <template #cell-course="{ row }">
          <div class="mp-cell-main">{{ row.courseName || '未命名课程' }}</div>
          <div class="mp-cell-sub">{{ row.courseCode || '无课程代码' }}</div>
        </template>
        <template #cell-class="{ row }">
          <div class="mp-cell-main">{{ row.teachingClassName || '未命名教学班' }}</div>
          <div class="mp-cell-sub">{{ row.teachingClassCode || '无教学班代码' }}{{ row.isMerged ? ' · 合班' : '' }}</div>
        </template>
        <template #cell-hours="{ row }">
          <div>周 {{ row.weeklyHours ?? '—' }} 学时</div>
          <div class="mp-cell-sub">第 {{ row.startWeek ?? '—' }}—{{ row.endWeek ?? '—' }} 周 · {{ row.expectedStudents ?? '—' }} 人</div>
        </template>
        <template #cell-status="{ row }">
          <AppStatusTag :status="row.status" :type="taskColor(row.status)" dot />
          <div v-if="row.rejectReason" class="mp-cell-sub is-danger">此前退回：{{ row.rejectReason }}</div>
        </template>
        <template #cell-actions="{ row }">
          <template v-if="row.status === 'ASSIGNED'">
            <button class="mp-link" :disabled="Boolean(acting || pendingCommand)" @click="openConfirm(row)">确认接受</button>
            <button class="mp-link is-danger" :disabled="Boolean(acting || pendingCommand)" @click="openReject(row)">提出异议</button>
          </template>
          <span v-else class="mp-cell-sub">已处理</span>
        </template>
      </DataTable>
    </div>

    <AppConfirmDialog
      v-model:visible="confirmDialog.visible"
      title="确认接受授课安排"
      type="primary"
      confirm-text="确认接受"
      :submitting="acting === confirmDialog.taskId"
      :confirm-disabled="Boolean(confirmDialog.invalid || pendingCommand)"
      @confirm="doConfirm"
    >
      <div class="teacher-task__confirm-card">
        <strong>{{ confirmDialog.row?.courseName || '课程' }}</strong>
        <span>{{ confirmDialog.row?.teachingClassName || '教学班待确认' }}</span>
        <span>周 {{ confirmDialog.row?.weeklyHours ?? '—' }} 学时 · 第 {{ confirmDialog.row?.startWeek ?? '—' }}—{{ confirmDialog.row?.endWeek ?? '—' }} 周</span>
        <span>预计 {{ confirmDialog.row?.expectedStudents ?? '—' }} 人</span>
      </div>
      <p class="teacher-task__confirm-note">确认后不能在本页直接修改；如后续确需调整，须由学院发起教学任务调整并保留原因。</p>
      <p v-if="confirmDialog.invalid" class="mp-cell-sub is-danger">原确认已失效。请关闭后从最新任务重新打开核对；结果待确认时只能查询。</p>
    </AppConfirmDialog>

    <AppConfirmDialog
      v-model:visible="rejectDialog.visible"
      title="提出异议（退回学院重新分配）"
      type="danger"
      confirm-text="确认退回"
      :submitting="acting === rejectDialog.taskId"
      :confirm-disabled="Boolean(rejectDialog.invalid || pendingCommand)"
      @confirm="doReject"
    >
      <p v-if="rejectDialog.invalid" class="mp-cell-sub is-danger">已保留异议原因，原确认已失效。请读取最新任务并重新打开；未知结果不会再次发送。</p>
      <label class="aa-note-label">退回原因（必填，≥5 字）
        <textarea ref="rejectReasonInput" v-model.trim="rejectDialog.reason" class="aa-textarea" rows="3" placeholder="如：与本人其他课表时间冲突" />
      </label>
      <AppQuickPhrases scene-key="aa.task.reject" @pick="onPickRejectReason" />
    </AppConfirmDialog>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppStatusTag, AppConfirmDialog, AppQuickPhrases } from '@/components/common'
import { insertAtCursor, applyInsertion } from '@/utils/insertAtCursor'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { TASK_STATUS, taskColor } from '@/modules/academicAffairs/constants/teaching'
import AaOperationReceipt from '../components/parallel-a/AaOperationReceipt.vue'
import { readTaskPages, taskConfirmationEvidence } from '../components/parallel-a/taskFacts'
import { isDeniedResult, isConflictResult } from '../components/parallel-a/resultState'
import { toast } from '@/utils/toast'
import AaTeachingTaskStageRail from '../components/teaching-tasks/AaTeachingTaskStageRail.vue'
import AaTeachingTaskObjectBar from '../components/teaching-tasks/AaTeachingTaskObjectBar.vue'

export default {
  name: 'AaTeacherTaskConfirmView',
  components: { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppStatusTag, AppConfirmDialog, AppQuickPhrases, AaOperationReceipt, AaTeachingTaskStageRail, AaTeachingTaskObjectBar },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      rows: [],
      revision: 0, receipt: null, pendingCommand: null,
      acting: '',
      statusFilter: 'ASSIGNED',
      keyword: '',
      currentTermId: '', currentTermName: '', showHistory: false,
      confirmDialog: { visible: false, taskId: '', row: null },
      rejectDialog: { visible: false, taskId: '', reason: '' },
      columns: [
        { key: 'course', title: '课程' },
        { key: 'class', title: '教学班' },
        { key: 'hours', title: '学时 / 周次 / 人数' },
        { key: 'status', title: '状态' },
        { key: 'actions', title: '本人操作', width: '170px' }
      ]
    }
  },
  computed: {
    focusTaskId() { return String(this.$route?.query?.taskId || '') },
    primaryRow() { return this.filteredRows[0] || this.rows[0] || null },
    counts() {
      const count = (status) => this.rows.filter((row) => row.status === status).length
      return {
        assigned: count('ASSIGNED'),
        confirmed: count('TEACHER_CONFIRMED'),
        rejected: count('REJECTED_BY_TEACHER'),
        ready: count('READY')
      }
    },
    filters() {
      return [
        { value: 'ASSIGNED', label: '待我确认', count: this.counts.assigned },
        { value: 'TEACHER_CONFIRMED', label: '已确认', count: this.counts.confirmed },
        { value: 'REJECTED_BY_TEACHER', label: '已退回', count: this.counts.rejected },
        { value: 'READY', label: '已就绪', count: this.counts.ready },
        { value: '', label: '全部', count: this.rows.length }
      ]
    },
    filteredRows() {
      if (this.focusTaskId) return this.rows.filter(row => String(row.taskId) === this.focusTaskId)
      const keyword = this.keyword.toLowerCase()
      return this.rows.filter((row) => {
        if (this.statusFilter && row.status !== this.statusFilter) return false
        if (!keyword) return true
        return [row.courseName, row.courseCode, row.teachingClassName, row.teachingClassCode]
          .some((value) => String(value || '').toLowerCase().includes(keyword))
      })
    }
  },
  created() { this.load() },
  watch: {
    ctx() { this.confirmDialog = { visible: false, taskId: '', row: null }; this.rejectDialog = { visible: false, taskId: '', reason: '' }; this.receipt = null; this.pendingCommand = null; this.acting = ''; this.keyword = ''; this.currentTermId = ''; this.currentTermName = ''; this.showHistory = false; this.load() },
    '$route.query.taskId'() { this.keyword = ''; this.load() }
  },
  beforeUnmount() { this.revision++; this.disposed = true },
  methods: {
    taskColor,
    async ensureCurrentTerm() {
      if (this.showHistory || this.currentTermId) return true
      const res = await academicAffairsApi.getCurrentTerm()
      if (res?.code !== 0 || !res.data?.termId) {
        this.error = res?.message || '当前学期尚未设置，无法建立教师当前任务队列'
        return false
      }
      this.currentTermId = String(res.data.termId)
      this.currentTermName = res.data.termName || res.data.name || res.data.termCode || this.currentTermId
      return true
    },
    async toggleHistory() {
      if (this.loading || this.focusTaskId) return
      this.showHistory = !this.showHistory
      this.statusFilter = this.showHistory ? '' : 'ASSIGNED'
      this.keyword = ''
      await this.load()
    },
    async load() {
      const revision = ++this.revision, context = this.ctx
      this.loading = true
      this.error = ''
      this.rows = []
      try {
        if (this.focusTaskId) {
          const exact = await academicAffairsApi.listAllTasks({
            mine: true, taskId: this.focusTaskId, page: 1, pageSize: 1
          })
          if (revision !== this.revision || context !== this.ctx || this.disposed) return false
          if (exact?.code === 0) {
            this.rows = exact.data?.list || []
            if (!this.rows.length) this.error = '该教学任务不存在或已不在本人数据范围内'
            return !this.error
          }
          this.handleFailure(exact, '教学任务读取失败')
          return false
        }
        if (!(await this.ensureCurrentTerm())) return false
        const res = await readTaskPages(
          page => academicAffairsApi.listAllTasks({
            mine: true,
            ...(this.showHistory ? {} : { termId: this.currentTermId }),
            ...page
          }),
          () => revision === this.revision && context === this.ctx && !this.disposed
        )
        if (revision !== this.revision || context !== this.ctx || this.disposed) return false
        if (res?.code === 0) { this.rows = res.data.list; return true }
        this.handleFailure(res, '我的教学任务加载失败')
        if (!this.error) this.error = res?.message || '任务未完整读取，请重试。'
        return false
      } catch (error) {
        if (revision === this.revision && context === this.ctx && !this.disposed) this.handleFailure(error, '网络连接失败，请重新读取本人任务。')
        return false
      } finally { if (revision === this.revision && context === this.ctx && !this.disposed) this.loading = false }
    },
    openConfirm(row) {
      if (this.acting || this.loading || this.pendingCommand || row.status !== 'ASSIGNED' || !this.rows.some(item => item.taskId === row.taskId && taskConfirmationEvidence(item) === taskConfirmationEvidence(row))) return
      this.confirmDialog = { visible: true, taskId: row.taskId, row: Object.freeze({ ...row }), evidence: taskConfirmationEvidence(row), invalid: false }
    },
    async doConfirm() {
      await this.submitAction(this.confirmDialog, 'CONFIRM', '')
    },
    openReject(row) {
      if (this.acting || this.loading || this.pendingCommand || row.status !== 'ASSIGNED' || !this.rows.some(item => item.taskId === row.taskId && taskConfirmationEvidence(item) === taskConfirmationEvidence(row))) return
      const reason = this.rejectDialog.taskId === row.taskId ? this.rejectDialog.reason : ''
      this.rejectDialog = { visible: true, taskId: row.taskId, row: Object.freeze({ ...row }), evidence: taskConfirmationEvidence(row), invalid: false, reason }
    },
    onPickRejectReason(text) {
      const el = this.$refs.rejectReasonInput
      const { value, selStart, selEnd } = insertAtCursor(el, this.rejectDialog.reason, text)
      this.rejectDialog.reason = value
      this.$nextTick(() => applyInsertion(el, selStart, selEnd))
    },
    async doReject() {
      if (!this.rejectDialog.reason || this.rejectDialog.reason.length < 5) {
        toast.error('退回原因必填且不少于 5 字')
        return
      }
      await this.submitAction(this.rejectDialog, 'REJECT', this.rejectDialog.reason.trim())
    },
    handleFailure(result, fallback) {
      const message = result?.message || fallback
      if (isDeniedResult(result)) {
        this.revision++; this.loading = false; this.rows = []; this.receipt = null; this.pendingCommand = null
        this.confirmDialog = { visible: false, taskId: '', row: null }
        this.rejectDialog = { visible: false, taskId: '', reason: '' }
        this.error = `${message}；已清除先前任务内容。`
      } else if (isConflictResult(result)) {
        this.confirmDialog.invalid = true; this.rejectDialog.invalid = true
        this.receipt = { title: '请重新核对任务', status: '事实已变化，保留输入', pending: true, next: `${message} 刷新后重新核对；不会自动重提。` }
      } else { this.error = message }
    },
    async submitAction(dialog, action, reason) {
      if (this.pendingCommand) return this.queryPending()
      if (this.acting || this.loading || dialog.invalid || !dialog.taskId || !dialog.evidence) return
      const taskId = dialog.taskId, context = this.ctx, sameContext = () => !this.disposed && context === this.ctx
      this.acting = taskId
      try {
        const loaded = await this.load()
        if (!sameContext() || !loaded) { dialog.invalid = true; return }
        const task = this.rows.find(row => String(row.taskId) === String(taskId))
        const unchanged = task?.status === 'ASSIGNED' && taskConfirmationEvidence(task) === dialog.evidence && String(task?.version ?? '') === String(dialog.row?.version ?? '')
        if (!unchanged) { dialog.invalid = true; this.handleFailure({ code: 409001, message: '所见课程、教师、教学班或授课安排已变化，请重新打开最新任务核对。' }); return }
        const object = `${task.courseName || '教学任务'} · ${task.teachingClassName || ''} · #${taskId}`
        this.pendingCommand = { taskId, action, reason, evidence: dialog.evidence, object }
        dialog.invalid = true
        this.receipt = { object, title: '办理回执', status: '结果待确认', pending: true, next: '正在查询原命令结果，请勿重复提交。' }
        const result = await academicAffairsApi.teacherActTask(taskId, action, reason)
        if (!sameContext()) return
        if (result.code !== 0) {
          if (isDeniedResult(result)) { this.handleFailure(result, '无权办理'); return }
          if (isConflictResult(result) || String(result.code || '').startsWith('400') || result.bizCode === 'VALIDATION_ERROR') {
            this.pendingCommand = null; this.handleFailure(result, '办理未完成，原确认已失效。'); await this.load(); return
          }
          this.handleFailure(result, '连接中断，原办理结果待确认。')
        } else dialog.visible = false
        await this.readPendingResult(sameContext)
      } catch (error) {
        if (sameContext()) {
          dialog.invalid = true; this.handleFailure(error, '连接中断，办理结果待确认。')
          if (this.pendingCommand && !isDeniedResult(error)) await this.readPendingResult(sameContext)
        }
      } finally { if (sameContext()) this.acting = '' }
    },
    async readPendingResult(current) {
      const pending = this.pendingCommand
      if (!pending) return
      const loaded = await this.load()
      if (!current() || !loaded || this.pendingCommand !== pending) return
      const row = this.rows.find(item => String(item.taskId) === String(pending.taskId))
      const evidenceMatches = row && taskConfirmationEvidence(row) === pending.evidence
      const confirmed = evidenceMatches && (pending.action === 'CONFIRM' ? ['TEACHER_CONFIRMED', 'READY'].includes(row.status) : row.status === 'REJECTED_BY_TEACHER' && String(row.rejectReason || '') === pending.reason)
      this.receipt = { object: pending.object, title: '办理回执', status: confirmed ? TASK_STATUS[row.status] : '结果待确认', pending: !confirmed, next: confirmed ? pending.action === 'CONFIRM' ? '由学院和教务继续核对；正式就绪后进入排课。' : '学院将查看异议并重新分配。' : '尚未读到与原办理一致的正式状态。只查询原命令，不会再次发送；请联系学院核对。' }
      if (confirmed) this.pendingCommand = null
    },
    async queryPending() {
      if (!this.pendingCommand || this.acting || this.loading) return
      const context = this.ctx, current = () => !this.disposed && context === this.ctx
      this.acting = this.pendingCommand.taskId
      try { await this.readPendingResult(current) } finally { if (current()) this.acting = '' }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.teacher-task__next { display:flex; align-items:center; gap:10px; flex-wrap:wrap; padding:12px 14px; border:1px solid var(--primary-100); border-radius:10px; background:var(--primary-50); color:var(--gray-600); font-size:12px; }
.teacher-task__next span { flex:1 1 280px; }
.teacher-task__summary { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }
.teacher-task__summary article { padding: 16px; border: 1px solid var(--gray-200); border-radius: 12px; background: #fff; }
.teacher-task__summary span, .teacher-task__summary small { display: block; color: var(--gray-500); font-size: 12px; }
.teacher-task__summary strong { display: block; margin: 8px 0 5px; color: var(--gray-900); font-size: 24px; }
.teacher-task__notice { display: flex; align-items: center; gap: 14px; padding: 14px 16px; border: 1px solid var(--primary-100); border-radius: 12px; background: var(--primary-50); }
.teacher-task__notice strong { color: var(--primary-700); }
.teacher-task__notice span { color: var(--gray-600); font-size: 13px; }
.teacher-task__filters { display: flex; align-items: center; gap: 8px; padding: 12px; border: 1px solid var(--gray-200); border-radius: 12px; background: #fff; }
.teacher-task__filters button { border: 1px solid var(--gray-200); border-radius: 18px; padding: 6px 11px; background: #fff; color: var(--gray-600); cursor: pointer; }
.teacher-task__filters button.active { border-color: var(--primary-300); background: var(--primary-50); color: var(--primary-700); font-weight: 600; }
.teacher-task__filters button span { margin-left: 4px; }
.teacher-task__search { margin-left: auto; width: 260px; height: 34px; padding: 0 11px; border: 1px solid var(--gray-300); border-radius: 8px; }
.teacher-task__confirm-card { display: flex; flex-direction: column; gap: 5px; padding: 14px; border-radius: 10px; background: var(--gray-50); }
.teacher-task__confirm-card strong { color: var(--gray-900); }
.teacher-task__confirm-card span { color: var(--gray-600); font-size: 13px; }
.teacher-task__confirm-note { margin: 12px 0 0; color: var(--warning-700); font-size: 12px; line-height: 1.6; }
.aa-note-label { display: flex; flex-direction: column; gap: 6px; font-size: 13px; color: var(--gray-700); }
.aa-textarea { padding: 10px 12px; border: 1px solid var(--gray-300); border-radius: 6px; background: #fff; color: var(--gray-900); font-size: 14px; box-sizing: border-box; width: 100%; resize: vertical; font-family: inherit; }
.mp-cell-sub.is-danger, .mp-link.is-danger { color: var(--danger-600); }
.mp-btn--ghost { border: 1px solid var(--gray-300); border-radius: 8px; padding: 0 14px; min-height: 36px; background: #fff; color: var(--gray-700); cursor: pointer; }
@media (max-width: 980px) { .teacher-task__summary { grid-template-columns: 1fr 1fr; } .teacher-task__filters { flex-wrap: wrap; } .teacher-task__search { margin-left: 0; width: 100%; } }
</style>
