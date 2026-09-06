<template>
  <ModulePageShell
    title="排课 · 课表维护"
    subtitle="从排课任务队列进入班级网格，点击候选课位后先校验教师、班级、教室冲突，再确认写入"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton @click="$router.push('/admin/academic-affairs/schedule')">返回批次</AppButton>
      <button class="mp-btn" @click="importVisible = true">批量导入 XLSX</button>
    </template>

    <div class="mp-stack">
      <div class="aa-filter">
        <label class="aa-filter__item">班级<AppClassPicker v-model="classId" placeholder="选择班级" @change="onClassPicked" /></label>
        <AppButton @click="loadClass">载入课表</AppButton>
        <span class="mp-note">排课新增只接受同学期“已就绪”教学任务；班级选择只决定当前课表视图与可选任务范围。</span>
      </div>

      <AppInlineAlert v-if="lastConflict" type="error" :message="lastConflict" />
      <div v-if="moveConflict.alternatives.length" class="aa-move-alternatives">
        <strong>可改到无硬冲突时段</strong>
        <button
          v-for="slot in moveConflict.alternatives"
          :key="`${slot.weekday}-${slot.slotNo}`"
          type="button"
          @click="applyMoveAlternative(slot)"
        >{{ slot.label }}</button>
      </div>
      <AppInlineAlert
        v-if="taskLoadError"
        type="error"
        :message="taskLoadError"
      />
      <AppInlineAlert
        v-if="preferredTask"
        type="info"
        title="已从排课工作台定位任务"
        :description="`${preferredTask.courseName || preferredTask.courseCode || '教学任务'} · ${preferredTask.teacherName || '教师待确认'}；点击课表中的空白课位即可直接安排。`"
      />

      <LoadingState v-if="loading" />
      <AppSectionCard v-else :title="classId ? ('班级 ' + (className || '已选择班级') + ' 课表') : '请先载入班级课表'">
        <AaScheduleGrid
          :items="items"
          :slots="slots"
          :editable="!!classId"
          :conflict="conflictCell"
          @cell-click="onCellClick"
          @item-click="onItemClick"
          @item-move="onItemMove"
        />
      </AppSectionCard>
    </div>

    <AppConfirmDialog
      v-model:visible="add.visible"
      :title="`排课 · 周${add.weekday} 第${add.slotNo}节`"
      type="primary"
      size="wide"
      confirm-text="确认排课"
      :submitting="add.submitting"
      :confirm-disabled="preflight.loading || !preflight.result?.allowed"
      @confirm="doAdd"
    >
      <div class="aa-assign-form">
        <label class="aa-assign-form__wide">
          已就绪教学任务
          <AppSelect
            v-model="add.taskId"
            :options="taskOptions"
            :disabled="taskLoading"
            :placeholder="taskLoading ? '正在读取已就绪教学任务…' : (taskOptions.length ? '选择教学任务' : '当前班级无已就绪教学任务')"
            @change="onTaskPicked"
          />
        </label>

        <div class="aa-task-echo aa-assign-form__wide" :class="{ 'is-empty': !selectedTask }">
          <div><span>课程</span><strong>{{ selectedTask?.courseName || '选择教学任务后自动带出' }}</strong><small>{{ selectedTask?.courseCode || '—' }}</small></div>
          <div><span>授课教师</span><strong>{{ selectedTask?.teacherName || '—' }}</strong><small>{{ selectedTask?.teacherKey || '—' }}</small></div>
          <div><span>教学班</span><strong>{{ selectedTask?.teachingClassName || '—' }}</strong><small>{{ className ? `行政班：${className}` : '由教学任务自动带出' }}</small></div>
        </div>

        <label>星期
          <AppSelect v-model="add.weekday" :options="weekdayOptions" placeholder="选择星期" />
        </label>
        <label>节次
          <AppSelect v-model="add.slotNo" :options="slotOptions" placeholder="选择节次" />
        </label>
        <label>教室<AppClassroomPicker v-model="add.classroomId" @change="onClassroomPicked" /></label>
        <label>单双周
          <AppSelect v-model="add.weekParity" :options="weekParityOptions" placeholder="" />
        </label>
        <label>起始周
          <input v-model.number="add.startWeek" type="number" :min="selectedTask?.startWeek || 1" :max="selectedTask?.endWeek || undefined" class="aa-input" />
          <small class="mp-note">任务范围 {{ taskWeekText }}</small>
        </label>
        <label>结束周
          <input v-model.number="add.endWeek" type="number" :min="selectedTask?.startWeek || 1" :max="selectedTask?.endWeek || undefined" class="aa-input" />
          <small class="mp-note">不再使用固定 18 周</small>
        </label>

        <section class="aa-preflight aa-assign-form__wide" :class="preflightClass">
          <div class="aa-preflight__head">
            <strong>排课前置校验</strong>
            <span v-if="preflight.loading">正在校验候选课位…</span>
            <span v-else-if="preflight.result?.allowed">可以排入</span>
            <span v-else-if="preflight.result">存在硬冲突，最终提交已锁定</span>
            <span v-else>选择教学任务后自动校验</span>
          </div>
          <template v-if="preflight.result && !preflight.result.allowed">
            <p class="aa-preflight__detail">{{ preflightMessage }}</p>
            <div v-if="preflight.result.alternatives?.length" class="aa-preflight__alternatives">
              <span>可选无硬冲突时段</span>
              <button
                v-for="slot in preflight.result.alternatives"
                :key="`${slot.weekday}-${slot.slotNo}`"
                type="button"
                @click="applyAlternative(slot)"
              >{{ slot.label }}</button>
            </div>
          </template>
          <p v-else-if="preflight.result?.allowed" class="aa-preflight__detail">
            教师、班级、教室三类硬冲突均已通过；正式提交时服务端仍会再次校验。
          </p>
        </section>
      </div>
    </AppConfirmDialog>

    <AaAuthoritativeImportDrawer
      v-model:visible="importVisible"
      title="批量导入课表"
      template-name="排课结果导入模板.xlsx"
      show-import-mode
      :preview-fields="['taskId', 'courseName', 'teacherName', 'className', 'weekday', 'slotNo', 'startWeek', 'endWeek', 'weekParity', 'classroom']"
      :download-template-fn="() => academicAffairsApi.downloadScheduleImportTemplate()"
      :upload-fn="(file, mode) => academicFileExchangeApi.uploadScheduleImport(batchId, file, mode)"
      @imported="onImported"
    />
  </ModulePageShell>
</template>

<script>
/** 课表维护：班级视图保持不变；新增写入改为 READY TeachingTask-first，批量导入由统一权威 ImportJob Drawer 接管。 */
import { ModulePageShell, LoadingState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppSectionCard, AppConfirmDialog, AppInlineAlert, AppSelect, AppClassPicker, AppClassroomPicker } from '@/components/common'
import AaAuthoritativeImportDrawer from '@/modules/academicAffairs/components/AaAuthoritativeImportDrawer.vue'
import AaScheduleGrid from '@/modules/academicAffairs/components/AaScheduleGrid.vue'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { academicFileExchangeApi } from '@/modules/academicAffairs/api/academic-file-exchange.api'
import { toast } from '@/utils/toast'

export default {
  name: 'AaScheduleMaintainView',
  components: {
    ModulePageShell, LoadingState, AppButton, AppSectionCard, AppConfirmDialog, AppInlineAlert,
    AppSelect, AppClassPicker, AppClassroomPicker, AaAuthoritativeImportDrawer, AaScheduleGrid
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      academicAffairsApi, academicFileExchangeApi,
      loading: false,
      slots: [], items: [], classId: '', className: '',
      conflictCell: null, lastConflict: '',
      moveConflict: { item: null, alternatives: [] },
      preflight: { loading: false, result: null, requestSeq: 0, timer: null },
      readyTasks: [], taskBatchIds: new Set(), taskLoading: false, taskLoadError: '',
      preferredTaskId: '',
      scheduleBatch: null,
      importVisible: false,
      add: {
        visible: false, submitting: false, weekday: 1, slotNo: 1,
        taskId: '', classroomId: '', classroom: '',
        startWeek: null, endWeek: null, weekParity: 'ALL'
      }
    }
  },
  computed: {
    batchId() { return this.$route.params.batchId },
    selectedTask() {
      return this.readyTasks.find((task) => String(task.taskId) === String(this.add.taskId)) || null
    },
    preferredTask() {
      return this.readyTasks.find((task) => String(task.taskId) === String(this.preferredTaskId)) || null
    },
    taskOptions() {
      return this.readyTasks
        .filter((task) => !this.classId || String(task.classId || '') === String(this.classId))
        .map((task) => ({
          value: String(task.taskId),
          label: `${task.courseName || task.courseCode || '课程'} · ${task.teachingClassName || '教学班待确认'} · ${task.teacherName || '教师待确认'}`
        }))
    },
    taskWeekText() {
      if (!this.selectedTask) return '选择任务后显示正式周次'
      const start = this.selectedTask.startWeek ?? '—'
      const end = this.selectedTask.endWeek ?? '—'
      return `${start}-${end} 周`
    },
    preflightMessage() {
      const result = this.preflight.result
      return result?.conflict?.detail || result?.blockers?.[0] || '当前候选课位不可提交'
    },
    preflightClass() {
      if (this.preflight.loading) return 'is-loading'
      if (this.preflight.result?.allowed) return 'is-ok'
      if (this.preflight.result) return 'is-blocked'
      return ''
    },
    weekParityOptions() {
      return [
        { value: 'ALL', label: '全周' },
        { value: 'ODD', label: '单周' },
        { value: 'EVEN', label: '双周' }
      ]
    },
    weekdayOptions() {
      return [1, 2, 3, 4, 5, 6, 7].map((value) => ({ value, label: `周${value}` }))
    },
    slotOptions() {
      return this.slots.map((slot) => ({
        value: Number(slot.slotNo),
        label: `第 ${slot.slotNo} 节 · ${slot.startTime || ''}-${slot.endTime || ''}`
      }))
    }
  },
  watch: {
    'add.taskId'() { this.queuePreflight() },
    'add.classroom'() { this.queuePreflight() },
    'add.weekParity'() { this.queuePreflight() },
    'add.startWeek'() { this.queuePreflight() },
    'add.endWeek'() { this.queuePreflight() },
    'add.weekday'() { this.queuePreflight() },
    'add.slotNo'() { this.queuePreflight() }
  },
  async created() {
    this.preferredTaskId = String(this.$route?.query?.taskId || '')
    this.classId = String(this.$route?.query?.classId || '')
    this.className = String(this.$route?.query?.className || '')
    await Promise.all([this.loadSlots(), this.loadReadyTasks()])
    if (this.classId) await this.loadClass()
  },
  methods: {
    async loadReadyTasks() {
      this.taskLoading = true
      this.taskLoadError = ''
      try {
        const batches = await academicAffairsApi.getScheduleBatches({ page: 1, pageSize: 500 })
        if (batches.code !== 0) throw new Error(batches.message || '课表批次读取失败')
        const scheduleBatch = (batches.data?.list || []).find((row) => String(row.batchId) === String(this.batchId))
        if (!scheduleBatch?.termId) throw new Error('当前课表批次未绑定正式学期')
        this.scheduleBatch = scheduleBatch

        const taskBatches = await academicAffairsApi.getTaskBatches({
          termId: scheduleBatch.termId,
          status: 'APPROVED',
          page: 1,
          pageSize: 500
        })
        if (taskBatches.code !== 0) throw new Error(taskBatches.message || '教学任务批次读取失败')
        const allowedBatches = new Set(
          (taskBatches.data?.list || [])
            .filter((row) => !scheduleBatch.collegeId || !row.collegeId || String(row.collegeId) === String(scheduleBatch.collegeId))
            .map((row) => String(row.batchId))
        )
        this.taskBatchIds = allowedBatches

        const tasks = await academicAffairsApi.listAllTasks({ status: 'READY', page: 1, pageSize: 500 })
        if (tasks.code !== 0) throw new Error(tasks.message || '已就绪教学任务读取失败')
        this.readyTasks = (tasks.data?.list || []).filter((task) => allowedBatches.has(String(task.batchId)))
      } catch (error) {
        this.readyTasks = []
        this.taskLoadError = error?.message || '已就绪教学任务读取失败'
      } finally {
        this.taskLoading = false
      }
    },
    onClassPicked(value, items) {
      const item = items?.[0]
      const row = item?.raw || item || {}
      this.className = row.className || row.name || item?.label || ''
    },
    onTaskPicked() {
      const task = this.selectedTask
      this.add.startWeek = task?.startWeek ?? null
      this.add.endWeek = task?.endWeek ?? null
      this.lastConflict = ''
      this.queuePreflight()
    },
    onClassroomPicked(value, items) {
      const item = items?.[0]
      const row = item?.raw || item || {}
      this.add.classroom = row.label || row.roomName || `${row.buildingName || ''}${row.roomCode || ''}` || item?.label || ''
    },
    async loadSlots() {
      const res = await academicAffairsApi.getTimeSlots()
      if (res.code === 0) this.slots = res.data
    },
    async loadClass() {
      if (!this.classId) { toast.error('请先选择班级'); return }
      this.loading = true
      const res = await academicAffairsApi.getScheduleClassView(this.batchId, this.classId)
      if (res.code === 0) this.items = (res.data && res.data.items) || []
      else toast.error(res.message || '载入失败')
      this.loading = false
    },
    onCellClick({ weekday, slotNo }) {
      this.conflictCell = null
      this.add = {
        visible: true, submitting: false, weekday, slotNo,
        taskId: this.preferredTask?.taskId ? String(this.preferredTask.taskId) : '', classroomId: '', classroom: '',
        startWeek: null, endWeek: null, weekParity: 'ALL'
      }
      this.onTaskPicked()
    },
    onItemClick(it) {
      toast.info(`${it.courseName} · ${it.teacherName || ''} · ${it.startWeek}-${it.endWeek}周`)
    },
    async onItemMove({ item, weekday, slotNo }) {
      this.lastConflict = ''
      this.moveConflict = { item: null, alternatives: [] }
      const checked = await academicAffairsApi.preflightScheduleMove(item.itemId, weekday, slotNo)
      if (checked.code !== 0 || !checked.data?.allowed) {
        this.conflictCell = { weekday, slotNo }
        this.lastConflict = checked.data?.conflict?.detail || checked.data?.blockers?.[0] || checked.message || '目标课位存在硬冲突'
        this.moveConflict = { item, alternatives: checked.data?.alternatives || [] }
        toast.error(this.lastConflict)
        return
      }
      const res = await academicAffairsApi.moveScheduleItem(item.itemId, weekday, slotNo)
      if (res.code === 0) {
        this.conflictCell = null
        this.moveConflict = { item: null, alternatives: [] }
        toast.success(`已调整到周${weekday}第${slotNo}节`)
        await this.loadClass()
      }
      else toast.error(res.message)
    },
    applyMoveAlternative(slot) {
      const item = this.moveConflict.item
      if (!item) return
      this.onItemMove({ item, weekday: Number(slot.weekday), slotNo: Number(slot.slotNo) })
    },
    async doAdd() {
      if (!this.add.taskId) { toast.error('请先选择已就绪教学任务'); return }
      const task = this.selectedTask
      if (!task) { toast.error('教学任务已失效，请刷新后重新选择'); return }
      if (this.classId && String(task.classId || '') !== String(this.classId)) {
        toast.error('所选教学任务不属于当前班级，请重新选择')
        return
      }
      if (!this.preflight.result?.allowed) {
        toast.error(this.preflightMessage || '请先通过排课前置校验')
        return
      }
      this.add.submitting = true
      this.lastConflict = ''
      const body = {
        taskId: String(task.taskId),
        weekday: Number(this.add.weekday),
        slotNo: Number(this.add.slotNo),
        weekParity: this.add.weekParity,
        classroom: this.add.classroom || undefined
      }
      if (Number(this.add.startWeek) > 0) body.startWeek = Number(this.add.startWeek)
      if (Number(this.add.endWeek) > 0) body.endWeek = Number(this.add.endWeek)
      const res = await academicAffairsApi.addScheduleItem(this.batchId, body)
      this.add.submitting = false
      if (res.code === 0) {
        this.add.visible = false
        toast.success(`已排课 · ${task.courseName || task.courseCode || '教学任务'}`)
        await this.loadClass()
      } else {
        this.conflictCell = { weekday: this.add.weekday, slotNo: this.add.slotNo }
        this.lastConflict = res.message || '排课冲突'
        toast.error(res.message || '排课冲突')
      }
    },
    queuePreflight() {
      if (this.preflight.timer) clearTimeout(this.preflight.timer)
      if (!this.add.visible || !this.add.taskId) {
        this.preflight.result = null
        this.preflight.loading = false
        return
      }
      this.preflight.timer = setTimeout(() => this.runPreflight(), 220)
    },
    async runPreflight() {
      const task = this.selectedTask
      if (!this.add.visible || !task) return
      const seq = ++this.preflight.requestSeq
      this.preflight.loading = true
      const body = {
        taskId: String(task.taskId),
        weekday: Number(this.add.weekday),
        slotNo: Number(this.add.slotNo),
        weekParity: this.add.weekParity,
        classroom: this.add.classroom || undefined
      }
      if (Number(this.add.startWeek) > 0) body.startWeek = Number(this.add.startWeek)
      if (Number(this.add.endWeek) > 0) body.endWeek = Number(this.add.endWeek)
      const response = await academicAffairsApi.preflightScheduleItem(this.batchId, body)
      if (seq !== this.preflight.requestSeq) return
      this.preflight.loading = false
      this.preflight.result = response.code === 0
        ? response.data
        : { allowed: false, blockers: [response.message || '排课前置校验失败'], alternatives: [] }
      if (!this.preflight.result.allowed) {
        this.conflictCell = { weekday: this.add.weekday, slotNo: this.add.slotNo }
      } else {
        this.conflictCell = null
      }
    },
    applyAlternative(slot) {
      this.add.weekday = Number(slot.weekday)
      this.add.slotNo = Number(slot.slotNo)
      this.queuePreflight()
    },
    onImported(data) {
      const result = data?.result || data || {}
      toast.success(`排课导入完成${result.imported != null ? `：成功 ${result.imported} 条` : ''}`)
      this.loadClass()
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-filter { display: flex; gap: 16px; align-items: center; flex-wrap: wrap; }
.aa-filter__item { display: inline-flex; align-items: center; gap: 8px; font-size: 13px; color: var(--text-700, #4e5969); }
.aa-input { height: 32px; padding: 0 10px; border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px; background: var(--bg-white, #fff); color: var(--text-900, #1f2329); font-size: 13px; box-sizing: border-box; }
.aa-assign-form { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.aa-assign-form label { display: flex; flex-direction: column; gap: 6px; font-size: 13px; color: var(--text-700, #4e5969); }
.aa-assign-form__wide { grid-column: 1 / -1; }
.aa-task-echo { grid-column: 1 / -1; display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; padding: 10px; border: 1px solid var(--border-200, #e5e6eb); border-radius: 8px; background: var(--bg-100, #f7f8fa); }
.aa-task-echo > div { min-width: 0; display: flex; flex-direction: column; gap: 3px; }
.aa-task-echo span, .aa-task-echo small { color: var(--text-500, #86909c); font-size: 12px; }
.aa-task-echo strong { color: var(--text-900, #1f2329); font-size: 13px; overflow-wrap: anywhere; }
.aa-task-echo.is-empty { opacity: .72; }
.aa-preflight { padding: 12px; border: 1px solid var(--border-200, #e5e6eb); border-radius: 8px; background: var(--bg-100, #f7f8fa); }
.aa-preflight.is-loading { border-color: var(--primary-200, #bfdbfe); background: var(--primary-50, #eff6ff); }
.aa-preflight.is-ok { border-color: var(--success-200, #bbf7d0); background: var(--success-50, #f0fdf4); }
.aa-preflight.is-blocked { border-color: var(--danger-200, #fecaca); background: var(--danger-50, #fef2f2); }
.aa-preflight__head { display: flex; align-items: center; justify-content: space-between; gap: 12px; color: var(--text-900, #1f2329); font-size: 13px; }
.aa-preflight__head span { color: var(--text-600, #64748b); font-size: 12px; }
.aa-preflight.is-ok .aa-preflight__head span { color: var(--success-700, #15803d); }
.aa-preflight.is-blocked .aa-preflight__head span, .aa-preflight.is-blocked .aa-preflight__detail { color: var(--danger-700, #b91c1c); }
.aa-preflight__detail { margin: 8px 0 0; color: var(--text-600, #64748b); font-size: 12px; line-height: 1.6; }
.aa-preflight__alternatives { display: flex; align-items: center; flex-wrap: wrap; gap: 6px; margin-top: 10px; font-size: 12px; color: var(--text-600, #64748b); }
.aa-preflight__alternatives button { padding: 4px 8px; border: 1px solid var(--primary-200, #bfdbfe); border-radius: 6px; color: var(--primary-700, #1d4ed8); background: var(--bg-white, #fff); cursor: pointer; }
.aa-preflight__alternatives button:hover { border-color: var(--primary-500, #3b82f6); background: var(--primary-50, #eff6ff); }
.aa-move-alternatives { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; padding: 10px 12px; border: 1px solid var(--danger-200, #fecaca); border-radius: 8px; background: var(--danger-50, #fef2f2); color: var(--danger-700, #b91c1c); font-size: 12px; }
.aa-move-alternatives button { padding: 4px 8px; border: 1px solid var(--primary-200, #bfdbfe); border-radius: 6px; background: var(--bg-white, #fff); color: var(--primary-700, #1d4ed8); cursor: pointer; }
@media (max-width: 760px) {
  .aa-assign-form { grid-template-columns: 1fr; }
  .aa-assign-form__wide, .aa-task-echo { grid-column: 1; }
  .aa-task-echo { grid-template-columns: 1fr; }
}
</style>
