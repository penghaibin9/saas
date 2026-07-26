<template>
  <ModulePageShell
    :title="workbench.batchName || '教学任务工作台'"
    :subtitle="workbench.termLabel || '查看分配、教师确认、学院核对和教务终审进度'"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton @click="$router.push('/admin/academic-affairs/teaching-tasks')">返回批次</AppButton>
      <AppButton :disabled="loading" @click="load">刷新</AppButton>
      <AppButton
        v-if="workbench.actions?.canAssign"
        @click="$router.push('/admin/academic-affairs/teaching-tasks/assign')"
      >进入分配工作区</AppButton>
      <AppButton
        v-if="workbench.actions?.canCollegeConfirm"
        variant="primary"
        :loading="acting"
        @click="collegeConfirm"
      >学院确认</AppButton>
      <AppButton
        v-if="workbench.actions?.canAcademicReview"
        variant="primary"
        :loading="acting"
        @click="openApprove"
      >教务终审通过</AppButton>
      <button
        v-if="workbench.actions?.canAcademicReview"
        class="mp-btn mp-btn--danger"
        :disabled="acting"
        @click="openReturn"
      >退回学院</button>
    </template>

    <div class="task-workbench mp-stack">
      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <template v-else>
        <section class="task-workbench__hero">
          <div>
            <div class="task-workbench__eyebrow">批次 #{{ workbench.batchId }}</div>
            <div class="task-workbench__headline">
              <AppStatusTag :status="workbench.status" dot />
              <strong>{{ workbench.nextAction?.label || '请核对当前任务状态' }}</strong>
            </div>
            <p>教师确认必须由任课教师本人完成；管理端只负责分配、催办、学院确认和教务终审。</p>
          </div>
          <div class="task-workbench__scope-note">
            <span>当前范围</span>
            <strong>{{ ctx.dataScope.scopeName }}</strong>
          </div>
        </section>

        <section class="task-workbench__metrics">
          <article v-for="metric in metrics" :key="metric.label" class="task-metric">
            <span>{{ metric.label }}</span>
            <strong>{{ metric.value }}</strong>
            <small>{{ metric.note }}</small>
          </article>
        </section>

        <section v-if="workbench.blockers?.length" class="task-workbench__blockers">
          <header>
            <strong>当前有 {{ workbench.blockerCount }} 项阻断</strong>
            <p>处理完以下问题后，批次才能进入下一审核节点。</p>
          </header>
          <button
            v-for="item in workbench.blockers"
            :key="item.code"
            class="task-blocker"
            type="button"
            @click="goBlocker(item)"
          >
            <span class="task-blocker__count">{{ item.count }}</span>
            <span class="task-blocker__main">
              <strong>{{ item.message }}</strong>
              <small>{{ blockerHint(item.code) }}</small>
            </span>
            <span class="task-blocker__go">处理 ›</span>
          </button>
        </section>

        <section v-else class="task-workbench__ready">
          <strong>当前批次没有阻断项</strong>
          <span>{{ workbench.nextAction?.label || '可以进入下一处理节点' }}</span>
        </section>

        <section class="task-workbench__filters">
          <input v-model.trim="keyword" class="mp-input" placeholder="搜索课程、教学班、教师或工号" />
          <select v-model="statusFilter" class="mp-input task-workbench__select">
            <option value="">全部状态</option>
            <option v-for="(label, key) in taskStatuses" :key="key" :value="key">{{ label }}</option>
          </select>
          <span class="task-workbench__result">当前显示 {{ filteredRows.length }} / {{ rows.length }} 条</span>
        </section>

        <EmptyState
          v-if="!filteredRows.length"
          title="没有符合条件的教学任务"
          description="调整搜索条件，或返回批次列表确认是否已生成任务"
        />
        <DataTable v-else :columns="columns" :rows="filteredRows" row-key="taskId">
          <template #cell-course="{ row }">
            <div class="mp-cell-main">{{ row.courseName || '未命名课程' }}</div>
            <div class="mp-cell-sub">{{ row.courseCode || '无课程代码' }}</div>
          </template>
          <template #cell-class="{ row }">
            <div class="mp-cell-main">{{ row.teachingClassName || '未生成教学班名称' }}</div>
            <div class="mp-cell-sub">{{ row.teachingClassCode || '无教学班代码' }}{{ row.isMerged ? ' · 合班' : '' }}</div>
          </template>
          <template #cell-teacher="{ row }">
            <div class="mp-cell-main">{{ row.teacherName || '待分配' }}</div>
            <div class="mp-cell-sub">{{ row.teacherKey || '尚未绑定稳定工号' }}</div>
          </template>
          <template #cell-hours="{ row }">
            <div>{{ row.weeklyHours ?? '—' }} 学时/周</div>
            <div class="mp-cell-sub">第 {{ row.startWeek ?? '—' }}—{{ row.endWeek ?? '—' }} 周 · {{ row.expectedStudents ?? '—' }} 人</div>
          </template>
          <template #cell-status="{ row }">
            <AppStatusTag :status="row.status" :type="taskColor(row.status)" dot />
            <div v-if="row.rejectReason" class="mp-cell-sub is-danger">{{ row.rejectReason }}</div>
          </template>
          <template #cell-actions="{ row }">
            <button
              v-if="canAssignRow(row)"
              class="mp-link"
              :disabled="acting"
              @click="openAssign(row)"
            >{{ row.teacherKey ? '重新分配' : '分配教师' }}</button>
            <span v-else-if="row.status === 'ASSIGNED'" class="mp-cell-sub">等待教师本人确认</span>
            <span v-else class="mp-cell-sub">—</span>
          </template>
        </DataTable>
      </template>
    </div>

    <AppConfirmDialog
      v-model:visible="assign.visible"
      title="分配任课教师"
      type="primary"
      confirm-text="确认分配"
      :submitting="assign.submitting"
      @confirm="doAssign"
    >
      <div class="aa-assign-form">
        <label>任课教师
          <AppTeacherPicker v-model="assign.teacherKey" placeholder="选择任课教师" @change="onTeacherPicked" />
        </label>
        <label>周学时<input v-model.number="assign.weeklyHours" type="number" min="0" class="aa-input" /></label>
        <label>预计人数<input v-model.number="assign.expectedStudents" type="number" min="0" class="aa-input" /></label>
      </div>
      <p class="task-dialog-note">教师工号是权限归属依据；教师姓名只用于展示。分配后必须由教师本人确认。</p>
    </AppConfirmDialog>

    <AppConfirmDialog
      v-model:visible="review.visible"
      :title="review.action === 'APPROVE' ? '确认教务终审通过' : '退回学院重新处理'"
      :type="review.action === 'APPROVE' ? 'primary' : 'danger'"
      :confirm-text="review.action === 'APPROVE' ? '确认通过' : '确认退回'"
      :submitting="acting"
      @confirm="doReview"
    >
      <p v-if="review.action === 'APPROVE'">终审通过后，教师已确认的任务将进入“已就绪”，可进入排课。</p>
      <label v-else class="task-review-reason">退回原因（必填，至少5字）
        <textarea v-model.trim="review.reason" rows="4" placeholder="说明需要学院重新处理的具体问题" />
      </label>
    </AppConfirmDialog>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppStatusTag, AppConfirmDialog, AppTeacherPicker } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { teachingTaskWorkbenchApi } from '@/modules/academicAffairs/api/teaching-task-workbench.api'
import { TASK_STATUS, taskColor } from '@/modules/academicAffairs/constants/teaching'
import { toast } from '@/utils/toast'

export default {
  name: 'AaTaskDetailView',
  components: { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppButton, AppStatusTag, AppConfirmDialog, AppTeacherPicker },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      acting: false,
      error: '',
      workbench: {},
      rows: [],
      keyword: '',
      statusFilter: '',
      taskStatuses: TASK_STATUS,
      assign: { visible: false, submitting: false, taskId: '', teacherName: '', teacherKey: '', weeklyHours: null, expectedStudents: null },
      review: { visible: false, action: '', reason: '' },
      columns: [
        { key: 'course', title: '课程' },
        { key: 'class', title: '教学班' },
        { key: 'teacher', title: '任课教师' },
        { key: 'hours', title: '周次 / 人数' },
        { key: 'status', title: '状态' },
        { key: 'actions', title: '管理动作', width: '150px' }
      ]
    }
  },
  computed: {
    batchId() { return this.$route.params.batchId },
    metrics() {
      return [
        { label: '任务总数', value: this.workbench.taskTotal ?? 0, note: '不含已并入合班任务' },
        { label: '分配完成率', value: `${this.workbench.assignedRate ?? 0}%`, note: `未分配 ${this.workbench.unassignedCount ?? 0} 条` },
        { label: '教师确认率', value: `${this.workbench.teacherConfirmRate ?? 0}%`, note: `待本人确认 ${this.workbench.waitingTeacherCount ?? 0} 条` },
        { label: '教师退回', value: this.workbench.teacherRejectedCount ?? 0, note: '需学院重新分配' },
        { label: '可排课任务', value: this.workbench.readyCount ?? 0, note: '教务终审后进入就绪' }
      ]
    },
    filteredRows() {
      const keyword = this.keyword.toLowerCase()
      return this.rows.filter((row) => {
        if (this.statusFilter && row.status !== this.statusFilter) return false
        if (!keyword) return true
        return [row.courseName, row.courseCode, row.teachingClassName, row.teachingClassCode, row.teacherName, row.teacherKey]
          .some((value) => String(value || '').toLowerCase().includes(keyword))
      })
    }
  },
  created() { this.load() },
  methods: {
    taskColor,
    onTeacherPicked(value, items) {
      this.assign.teacherKey = value || ''
      this.assign.teacherName = items?.[0]?.raw?.teacherName || items?.[0]?.label || ''
    },
    blockerHint(code) {
      const hints = {
        UNASSIGNED: '为每条课程任务绑定稳定教师工号',
        WAIT_TEACHER: '教师须在“教师任务确认”页面本人确认',
        TEACHER_REJECTED: '查看退回原因并重新分配',
        TEACHER_KEY_MISSING: '修复历史任务的稳定教师身份'
      }
      return hints[code] || '进入对应工作区处理'
    },
    goBlocker(item) {
      if (item.route) this.$router.push(item.route)
    },
    canAssignRow(row) {
      return Boolean(this.workbench.actions?.canAssign) && ['PENDING_ASSIGN', 'ASSIGNED', 'REJECTED_BY_TEACHER'].includes(row.status)
    },
    openAssign(row) {
      this.assign = {
        visible: true,
        submitting: false,
        taskId: row.taskId,
        teacherName: row.teacherName || '',
        teacherKey: row.teacherKey || '',
        weeklyHours: row.weeklyHours,
        expectedStudents: row.expectedStudents
      }
    },
    async doAssign() {
      if (!this.assign.teacherKey || !this.assign.teacherName) {
        toast.error('请选择带稳定工号的任课教师')
        return
      }
      this.assign.submitting = true
      const res = await academicAffairsApi.assignTeacher(this.assign.taskId, {
        teacherName: this.assign.teacherName,
        teacherKey: this.assign.teacherKey,
        weeklyHours: this.assign.weeklyHours ?? undefined,
        expectedStudents: this.assign.expectedStudents ?? undefined
      })
      this.assign.submitting = false
      if (res.code === 0) {
        this.assign.visible = false
        toast.success('已分配，等待教师本人确认')
        this.load()
      } else toast.error(res.message || '分配失败')
    },
    async collegeConfirm() {
      this.acting = true
      const res = await academicAffairsApi.collegeConfirmTaskBatch(this.batchId)
      this.acting = false
      if (res.code === 0) {
        toast.success('学院已确认，批次已进入教务终审')
        this.load()
      } else toast.error(res.message || '学院确认失败')
    },
    openApprove() { this.review = { visible: true, action: 'APPROVE', reason: '' } },
    openReturn() { this.review = { visible: true, action: 'RETURN', reason: '' } },
    async doReview() {
      if (this.review.action === 'RETURN' && this.review.reason.length < 5) {
        toast.error('退回原因必填且不少于5字')
        return
      }
      this.acting = true
      const action = this.review.action
      const res = await academicAffairsApi.reviewTaskBatch(this.batchId, action, this.review.reason)
      this.acting = false
      if (res.code === 0) {
        this.review.visible = false
        toast.success(action === 'APPROVE' ? '教务终审已通过' : '批次已退回学院')
        this.load()
      } else toast.error(res.message || '处理失败')
    },
    async load() {
      this.loading = true
      this.error = ''
      const [workbenchRes, taskRes] = await Promise.all([
        teachingTaskWorkbenchApi.getBatch(this.batchId),
        academicAffairsApi.getBatchTasks(this.batchId, { page: 1, pageSize: 500 })
      ])
      if (workbenchRes.code !== 0) this.error = workbenchRes.message || '工作台加载失败'
      else if (taskRes.code !== 0) this.error = taskRes.message || '任务明细加载失败'
      else {
        this.workbench = workbenchRes.data || {}
        this.rows = taskRes.data?.list || []
      }
      this.loading = false
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.task-workbench__hero { display: flex; justify-content: space-between; gap: 24px; padding: 22px 24px; border: 1px solid var(--primary-100); border-radius: 14px; background: linear-gradient(135deg, var(--primary-50), #fff); }
.task-workbench__eyebrow { margin-bottom: 8px; color: var(--primary-700); font-size: 12px; font-weight: 600; }
.task-workbench__headline { display: flex; align-items: center; gap: 12px; font-size: 17px; }
.task-workbench__hero p { margin: 9px 0 0; color: var(--gray-600); font-size: 13px; line-height: 1.6; }
.task-workbench__scope-note { min-width: 190px; padding: 12px 14px; border-radius: 10px; background: rgba(255,255,255,.78); }
.task-workbench__scope-note span, .task-workbench__scope-note strong { display: block; }
.task-workbench__scope-note span { color: var(--gray-500); font-size: 12px; }
.task-workbench__scope-note strong { margin-top: 5px; color: var(--gray-800); font-size: 13px; }
.task-workbench__metrics { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 12px; }
.task-metric { padding: 16px; border: 1px solid var(--gray-200); border-radius: 12px; background: #fff; }
.task-metric span, .task-metric small { display: block; color: var(--gray-500); font-size: 12px; }
.task-metric strong { display: block; margin: 8px 0 5px; color: var(--gray-900); font-size: 24px; }
.task-workbench__blockers { padding: 18px; border: 1px solid var(--warning-100); border-radius: 12px; background: var(--warning-50); }
.task-workbench__blockers header p { margin: 4px 0 12px; color: var(--gray-600); font-size: 12px; }
.task-blocker { width: 100%; display: flex; align-items: center; gap: 12px; padding: 12px 0; border: 0; border-top: 1px solid rgba(180,120,0,.16); background: transparent; text-align: left; cursor: pointer; }
.task-blocker__count { display: inline-flex; align-items: center; justify-content: center; min-width: 34px; height: 28px; border-radius: 14px; background: #fff; color: var(--warning-700); font-weight: 700; }
.task-blocker__main { flex: 1; }
.task-blocker__main strong, .task-blocker__main small { display: block; }
.task-blocker__main small { margin-top: 3px; color: var(--gray-600); }
.task-blocker__go { color: var(--primary-700); }
.task-workbench__ready { display: flex; justify-content: space-between; padding: 15px 18px; border: 1px solid var(--success-100); border-radius: 12px; background: var(--success-50); color: var(--success-700); }
.task-workbench__filters { display: flex; align-items: center; gap: 10px; padding: 14px; border: 1px solid var(--gray-200); border-radius: 12px; background: #fff; }
.task-workbench__filters .mp-input { max-width: 360px; }
.task-workbench__select { max-width: 190px !important; }
.task-workbench__result { margin-left: auto; color: var(--gray-500); font-size: 12px; }
.aa-assign-form { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.aa-assign-form label { display: flex; flex-direction: column; gap: 6px; font-size: 13px; color: var(--gray-700); }
.aa-input { height: 34px; padding: 0 12px; border: 1px solid var(--gray-300); border-radius: 6px; background: #fff; color: var(--gray-900); font-size: 14px; box-sizing: border-box; }
.task-dialog-note { margin: 12px 0 0; color: var(--warning-700); font-size: 12px; }
.task-review-reason { display: flex; flex-direction: column; gap: 7px; color: var(--gray-700); font-size: 13px; }
.task-review-reason textarea { width: 100%; box-sizing: border-box; padding: 10px 12px; border: 1px solid var(--gray-300); border-radius: 8px; resize: vertical; }
.mp-cell-sub.is-danger { color: var(--danger-600); }
.mp-btn--danger { border: 0; border-radius: 8px; padding: 0 14px; min-height: 36px; background: var(--danger-600); color: #fff; cursor: pointer; }
@media (max-width: 1180px) { .task-workbench__metrics { grid-template-columns: repeat(3, 1fr); } }
@media (max-width: 760px) { .task-workbench__hero { flex-direction: column; } .task-workbench__metrics { grid-template-columns: 1fr 1fr; } .aa-assign-form { grid-template-columns: 1fr; } }
</style>
