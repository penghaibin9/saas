<template>
  <ModulePageShell
    title="我的教学任务"
    subtitle="仅处理分配给本人工号的授课任务；确认后由学院和教务继续审核"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <button class="mp-btn mp-btn--ghost" :disabled="loading" @click="load">刷新</button>
    </template>

    <div class="teacher-task mp-stack">
      <section class="teacher-task__summary">
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
        <strong>确认前请核对</strong>
        <span>课程、教学班、周学时、授课周次和预计人数。管理端不能代替教师确认。</span>
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
            <button class="mp-link" :disabled="acting === row.taskId" @click="openConfirm(row)">确认接受</button>
            <button class="mp-link is-danger" :disabled="acting === row.taskId" @click="openReject(row)">提出异议</button>
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
      @confirm="doConfirm"
    >
      <div class="teacher-task__confirm-card">
        <strong>{{ confirmDialog.row?.courseName || '课程' }}</strong>
        <span>{{ confirmDialog.row?.teachingClassName || '教学班待确认' }}</span>
        <span>周 {{ confirmDialog.row?.weeklyHours ?? '—' }} 学时 · 第 {{ confirmDialog.row?.startWeek ?? '—' }}—{{ confirmDialog.row?.endWeek ?? '—' }} 周</span>
        <span>预计 {{ confirmDialog.row?.expectedStudents ?? '—' }} 人</span>
      </div>
      <p class="teacher-task__confirm-note">确认后不能在本页直接修改；如后续确需调整，须由学院发起教学任务调整并保留原因。</p>
    </AppConfirmDialog>

    <AppConfirmDialog
      v-model:visible="rejectDialog.visible"
      title="提出异议（退回学院重新分配）"
      type="danger"
      confirm-text="确认退回"
      :submitting="acting === rejectDialog.taskId"
      @confirm="doReject"
    >
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
import { taskColor } from '@/modules/academicAffairs/constants/teaching'
import { toast } from '@/utils/toast'

export default {
  name: 'AaTeacherTaskConfirmView',
  components: { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppStatusTag, AppConfirmDialog, AppQuickPhrases },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      rows: [],
      acting: '',
      statusFilter: 'ASSIGNED',
      keyword: '',
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
  methods: {
    taskColor,
    async load() {
      this.loading = true
      this.error = ''
      const res = await academicAffairsApi.listAllTasks({ mine: true, page: 1, pageSize: 500 })
      if (res.code === 0) this.rows = res.data?.list || []
      else this.error = res.message || '我的教学任务加载失败'
      this.loading = false
    },
    openConfirm(row) {
      this.confirmDialog = { visible: true, taskId: row.taskId, row }
    },
    async doConfirm() {
      const taskId = this.confirmDialog.taskId
      if (!taskId) return
      this.acting = taskId
      const res = await academicAffairsApi.teacherActTask(taskId, 'CONFIRM', '')
      this.acting = ''
      if (res.code === 0) {
        this.confirmDialog.visible = false
        toast.success('已确认接受本次授课安排')
        this.load()
      } else toast.error(res.message || '确认失败')
    },
    openReject(row) { this.rejectDialog = { visible: true, taskId: row.taskId, reason: '' } },
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
      this.acting = this.rejectDialog.taskId
      const res = await academicAffairsApi.teacherActTask(this.rejectDialog.taskId, 'REJECT', this.rejectDialog.reason)
      this.acting = ''
      if (res.code === 0) {
        this.rejectDialog.visible = false
        toast.success('已退回学院重新分配')
        this.load()
      } else toast.error(res.message || '退回失败')
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
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
