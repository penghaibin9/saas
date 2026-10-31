<template>
  <ModulePageShell
    title="教师任务确认"
    subtitle="核对课程、教学班、学时和人数后确认"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
    show-subtitle-in-concise
  >
    <template #actions>
      <button class="mp-btn mp-btn--ghost" @click="$router.push('/admin/academic-affairs/teacher/today')">返回今日教学</button>
      <button class="mp-btn mp-btn--ghost" :disabled="loading || Boolean(focusTaskId)" @click="toggleHistory">{{ showHistory ? '返回当前学期' : '历史任务' }}</button>
      <button class="mp-btn mp-btn--ghost" :disabled="loading" @click="load">刷新</button>
    </template>

    <div class="teacher-task mp-stack task-workspace">
      <AaOperationReceipt :receipt="receipt" />
      <div v-if="receipt && receipt.pending === false" class="teacher-task__next">
        <span>本次办理已形成正式状态；后续进度会回到“今日教学”的办理中。</span>
        <button class="mp-btn mp-btn--ghost" @click="$router.push('/admin/academic-affairs/teacher/today?work=waiting')">返回今日教学</button>
        <button v-if="primaryRow?.status === 'READY'" class="mp-btn mp-btn--ghost" @click="$router.push('/admin/academic-affairs/schedule/teacher')">查看个人课表</button>
      </div>
      <button v-if="pendingCommand" class="mp-btn mp-btn--ghost" :disabled="loading || Boolean(acting)" @click="queryPending">查询原办理结果（不会重复提交）</button>
      <section class="teacher-task__notice">
        <strong>{{ showHistory ? '历史教学任务' : '当前学期教学任务' }}</strong>
        <span>{{ showHistory ? '历史任务仅供查询；默认工作队列只显示当前学期。' : `当前学期：${currentTermName || '待确认'}` }}</span>
      </section>

      <section class="teacher-task__filters">
        <button
          v-for="item in filters"
          :key="item.value"
          type="button"
          :class="{ active: statusFilter === item.value }"
          @click="changeStatus(item.value)"
        >{{ item.label }}</button>
        <input v-model.trim="keyword" class="teacher-task__search" placeholder="搜索课程或教学班" aria-label="搜索课程或教学班" @keyup.enter="changePage(1)" /><button type="button" @click="changePage(1)">查询</button>
      </section>

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState
        v-else-if="!filteredRows.length"
        :title="statusFilter === 'ASSIGNED' ? '当前没有待确认任务' : '没有符合条件的教学任务'"
        description="学院分配并绑定您的稳定教师工号后，任务会出现在这里"
      />
      <div v-else class="task-workspace__split">
      <DataTable :columns="columns" :rows="filteredRows" row-key="taskId" :row-class="row => String(row.taskId) === String(primaryRow?.taskId) ? 'task-workspace__selected' : ''" :pagination="pagination" @page-change="changePage">
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
        <template #cell-actions="{ row }"><button class="mp-link" :disabled="Boolean(acting || pendingCommand)" @click="selectTask(row)">{{ String(row.taskId) === String(primaryRow?.taskId) ? '正在核对' : '核对安排' }}</button></template>
      </DataTable>
      <aside v-if="primaryRow" class="task-workspace__panel" aria-label="核对本次教学安排">
        <h3>核对本次教学安排</h3>
        <AaTeachingTaskObjectBar
          :name="primaryRow.courseName || '当前教学任务'"
          :owner="currentOwner(primaryRow)"
          :next-owner="nextOwner(primaryRow)"
        />
        <dl class="task-workspace__facts"><div><dt>课程</dt><dd>{{ primaryRow.courseName }}</dd></div><div><dt>任课教师</dt><dd>{{ primaryRow.teacherName || '本人' }}</dd></div><div><dt>教学班</dt><dd>{{ primaryRow.teachingClassName || primaryRow.className || '教学班待核对' }}</dd></div><div><dt>周学时</dt><dd>{{ primaryRow.weeklyHours ?? '—' }}学时</dd></div><div><dt>总学时</dt><dd>{{ primaryRow.totalHours ?? '—' }}学时</dd></div><div><dt>教学周次</dt><dd>第{{ primaryRow.startWeek ?? '—' }}—{{ primaryRow.endWeek ?? '—' }}周</dd></div><div><dt>预计人数</dt><dd>{{ primaryRow.expectedStudents ?? '—' }}人</dd></div></dl>
        <p class="task-workspace__notice">确认的是教学任务安排，具体上课时间以发布课表为准。</p>
        <AppButton v-if="primaryRow.teachingClassCode && primaryRow.termId" :disabled="Boolean(acting || pendingCommand)" @click="openTeachingClass(primaryRow)">查看教学班名单</AppButton>
        <p v-if="primaryRow.rejectReason" class="task-workspace__notice task-workspace__notice--warning">退回原因：{{ primaryRow.rejectReason }}</p>
        <div v-if="primaryRow.status === 'ASSIGNED' && !showHistory" class="task-workspace__actions"><AppButton variant="primary" :disabled="Boolean(acting || pendingCommand)" @click="openConfirm(primaryRow)">确认本人任务</AppButton><AppButton :disabled="Boolean(acting || pendingCommand)" @click="openReject(primaryRow)">退回学院</AppButton></div>
        <p>{{ stageNote(primaryRow) }}</p><p class="mp-cell-sub">本人确认后，由学院核对，再交校教务终审。</p>
      </aside></div>
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
import { AppButton } from '@/components/ui'
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppStatusTag, AppConfirmDialog, AppQuickPhrases } from '@/components/common'
import { insertAtCursor, applyInsertion } from '@/utils/insertAtCursor'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { TASK_STATUS, taskColor } from '@/modules/academicAffairs/constants/teaching'
import AaOperationReceipt from '../components/parallel-a/AaOperationReceipt.vue'
import AaTeachingTaskObjectBar from '../components/teaching-tasks/AaTeachingTaskObjectBar.vue'
import { taskConfirmationEvidence } from '../components/parallel-a/taskFacts'
import { isDeniedResult, isConflictResult } from '../components/parallel-a/resultState'
import { toast } from '@/utils/toast'

export default {
  name: 'AaTeacherTaskConfirmView',
  components: { AppButton, ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppStatusTag, AppConfirmDialog, AppQuickPhrases, AaOperationReceipt, AaTeachingTaskObjectBar },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      selectedId: '', pagination: { page: 1, pageSize: 20, total: 0 },
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
        { key: 'status', title: '状态' },
        { key: 'actions', title: '本人操作', width: '170px' }
      ]
    }
  },
  computed: {
    focusTaskId() { return String(this.$route?.query?.taskId || '') },
    primaryRow() { return this.filteredRows.find(row => String(row.taskId) === this.selectedId) || this.filteredRows[0] || null },
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
    filteredRows() { return this.rows }
  },
  created() { this.restoreQuery(); this.load() },
  watch: {
    ctx() { this.confirmDialog = { visible: false, taskId: '', row: null }; this.rejectDialog = { visible: false, taskId: '', reason: '' }; this.receipt = null; this.pendingCommand = null; this.acting = ''; this.keyword = ''; this.currentTermId = ''; this.currentTermName = ''; this.showHistory = false; this.load() },
    '$route.fullPath'() { this.restoreQuery(); this.load() }
  },
  beforeUnmount() { this.revision++; this.disposed = true },
  methods: {
    openTeachingClass(row) {
      if (!row?.teachingClassCode || !row.termId || this.acting || this.pendingCommand) return
      return this.$router.push({ path: '/admin/academic-affairs/teaching-tasks', query: { view: 'classes', termId: String(row.termId), keyword: String(row.teachingClassCode), returnTo: this.$route.fullPath } })
    },
    restoreQuery() { const q = this.$route.query; this.keyword = String(q.keyword || ''); this.statusFilter = typeof q.status === 'string' ? q.status : 'ASSIGNED'; this.showHistory = q.history === '1'; this.selectedId = String(q.selected || ''); this.pagination.page = Math.max(1, Number(q.page) || 1) },
    selectTask(row) { if (this.acting || this.pendingCommand) return; this.selectedId = String(row.taskId); return this.$router.replace({ path: this.$route.path, query: { ...this.$route.query, selected: this.selectedId } }) },
    changeStatus(status) { if (this.acting || this.pendingCommand) return; this.statusFilter = status; return this.changePage(1) },
    async changePage(page) { if (this.acting || this.pendingCommand) return; this.pagination.page = page; const before = this.$route.fullPath; await this.$router.replace({ path: this.$route.path, query: { ...this.$route.query, taskId: undefined, selected: undefined, keyword: this.keyword || undefined, status: this.statusFilter, page: String(page), history: this.showHistory ? '1' : undefined } }); if (before === this.$route.fullPath) await this.load() },
    taskColor,
    statusLabel(status) { return TASK_STATUS[status] || '状态待核对' },
    currentOwner(row) {
      const status = String(row?.status || '').toUpperCase()
      const batch = String(row?.batchStatus || '').toUpperCase()
      if (status === 'ASSIGNED') return '当前正式任课教师'
      if (status === 'TEACHER_CONFIRMED' && batch === 'COLLEGE_CONFIRMED') return '学校教务终审岗'
      if (status === 'TEACHER_CONFIRMED') return '学院教学任务核对岗'
      if (status === 'READY') return '教学任务确认链已完成'
      if (status === 'REJECTED_BY_TEACHER') return '学院重新分配岗'
      return '状态待核对'
    },
    nextOwner(row) {
      const status = String(row?.status || '').toUpperCase()
      const batch = String(row?.batchStatus || '').toUpperCase()
      if (status === 'ASSIGNED') return '学院教学任务核对岗'
      if (status === 'TEACHER_CONFIRMED' && batch === 'COLLEGE_CONFIRMED') return '终审通过后可进入排课'
      if (status === 'TEACHER_CONFIRMED') return '学院确认后转学校教务终审'
      if (status === 'READY') return '进入个人课表与后续教学执行'
      if (status === 'REJECTED_BY_TEACHER') return '学院调整后重新分配教师'
      return '请核对最新状态'
    },
    taskStage(row) {
      const status = String(row?.status || '').toUpperCase()
      const batch = String(row?.batchStatus || '').toUpperCase()
      if (status === 'READY') return 5
      if (status === 'TEACHER_CONFIRMED' && batch === 'COLLEGE_CONFIRMED') return 4
      if (status === 'TEACHER_CONFIRMED') return 3
      return 3
    },
    stageNote(row) {
      const status = String(row?.status || '').toUpperCase()
      const batch = String(row?.batchStatus || '').toUpperCase()
      if (status === 'ASSIGNED') return '等待教师本人确认'
      if (status === 'TEACHER_CONFIRMED' && batch === 'COLLEGE_CONFIRMED') return '学院已核对，等待教务终审'
      if (status === 'TEACHER_CONFIRMED') return '本人已确认，等待学院核对'
      if (status === 'READY') return '教务终审通过，教学任务已就绪'
      if (status === 'REJECTED_BY_TEACHER') return '本人已提出异议，等待学院处理'
      return '当前任务状态待核对'
    },
    rowProgress(row) {
      const status = String(row?.status || '').toUpperCase()
      const batch = String(row?.batchStatus || '').toUpperCase()
      if (status === 'TEACHER_CONFIRMED' && batch === 'COLLEGE_CONFIRMED') return '等待教务终审'
      if (status === 'TEACHER_CONFIRMED') return '等待学院核对'
      if (status === 'READY') return '已就绪'
      if (status === 'REJECTED_BY_TEACHER') return '等待学院调整'
      return '已处理'
    },
    async ensureCurrentTerm(revision = this.revision, context = this.ctx) {
      if (this.showHistory || this.currentTermId) return true
      const res = await academicAffairsApi.getCurrentTerm()
      if (revision !== this.revision || context !== this.ctx || this.disposed) return false
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
      await this.changePage(1)
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
            this.rows = exact.data?.list || []; this.pagination.total = Number(exact.data?.total || 0)
            if (!this.rows.length) this.error = '该教学任务不存在或已不在本人数据范围内'
            return !this.error
          }
          this.handleFailure(exact, '教学任务读取失败')
          return false
        }
        if (!this.showHistory && !this.currentTermId) {
          if (!(await this.ensureCurrentTerm(revision, context))) return false
        }
        if (revision !== this.revision || context !== this.ctx || this.disposed) return false
        const res = await academicAffairsApi.listAllTasks({ mine: true, ...(this.showHistory ? {} : { termId: this.currentTermId }), status: this.statusFilter || undefined, keyword: this.keyword || undefined, page: this.pagination.page, pageSize: this.pagination.pageSize })
        if (revision !== this.revision || context !== this.ctx || this.disposed) return false
        if (res?.code === 0) { this.rows = res.data.list; this.pagination.total = Number(res.data.total || 0); return true }
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
        this.receipt = { title: '请重新核对任务', status: '数据已变化，保留输入', pending: true, next: `${message} 刷新后重新核对；不会自动重提。` }
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
        this.receipt = { object, title: '办理回执', status: '结果待确认', pending: true, next: '正在查询原操作的结果，请勿重复提交。' }
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
      const exact = await academicAffairsApi.listAllTasks({ mine: true, taskId: pending.taskId, page: 1, pageSize: 1 })
      if (!current() || this.pendingCommand !== pending) return
      if (exact.code !== 0) { this.handleFailure(exact, '原办理结果查询失败'); return }
      const row = exact.data?.list?.find(item => String(item.taskId) === String(pending.taskId))
      const evidenceMatches = row && taskConfirmationEvidence(row) === pending.evidence
      const confirmed = evidenceMatches && (pending.action === 'CONFIRM' ? ['TEACHER_CONFIRMED', 'READY'].includes(row.status) : row.status === 'REJECTED_BY_TEACHER' && String(row.rejectReason || '') === pending.reason)
      this.receipt = { object: pending.object, title: '办理回执', status: confirmed ? TASK_STATUS[row.status] : '结果待确认', pending: !confirmed, next: confirmed ? pending.action === 'CONFIRM' ? '由学院和教务继续核对；正式就绪后进入排课。' : '学院将查看异议并重新分配。' : '尚未读到与原办理一致的正式状态。只查询原操作，不会再次提交；请联系学院核对。' }
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
@import '../styles/teaching-task-workspace.css';
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
