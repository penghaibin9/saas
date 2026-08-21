<template>
  <ModulePageShell
    title="排课 · 课表维护"
    subtitle="先载入班级课表，再从同学期 READY 教学任务排入时段；课程、教师、教学班身份由任务唯一带出"
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
        <span class="mp-note">排课新增只接受同学期 READY 教学任务；班级选择只决定当前课表视图与可选任务范围。</span>
      </div>

      <AppInlineAlert v-if="lastConflict" type="error" :message="lastConflict" />
      <AppInlineAlert
        v-if="taskLoadError"
        type="error"
        :message="taskLoadError"
      />

      <LoadingState v-if="loading" />
      <AppSectionCard v-else :title="classId ? ('班级 ' + (className || classId) + ' 课表') : '请先载入班级课表'">
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
      confirm-text="确认排课"
      :submitting="add.submitting"
      @confirm="doAdd"
    >
      <div class="aa-assign-form">
        <label class="aa-assign-form__wide">
          READY 教学任务
          <AppSelect
            v-model="add.taskId"
            :options="taskOptions"
            :disabled="taskLoading"
            :placeholder="taskLoading ? '正在读取 READY 教学任务…' : (taskOptions.length ? '选择教学任务' : '当前班级无 READY 教学任务')"
            @change="onTaskPicked"
          />
        </label>

        <div class="aa-task-echo aa-assign-form__wide" :class="{ 'is-empty': !selectedTask }">
          <div><span>课程</span><strong>{{ selectedTask?.courseName || '选择教学任务后自动带出' }}</strong><small>{{ selectedTask?.courseCode || '—' }}</small></div>
          <div><span>授课教师</span><strong>{{ selectedTask?.teacherName || '—' }}</strong><small>{{ selectedTask?.teacherKey || '—' }}</small></div>
          <div><span>教学班</span><strong>{{ selectedTask?.teachingClassName || '—' }}</strong><small>ID {{ selectedTask?.classId || '—' }}</small></div>
        </div>

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
      </div>
    </AppConfirmDialog>

    <AaAuthoritativeImportDrawer
      v-model:visible="importVisible"
      title="排课权威 XLSX 导入"
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
/** 课表维护：班级视图保持不变；新增写入改为 READY TeachingTask-first，批量导入改走 File Exchange。 */
import { ModulePageShell, LoadingState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppSectionCard, AppConfirmDialog, AppInlineAlert, AppSelect, AppClassPicker, AppClassroomPicker } from '@/components/common'
import AaAuthoritativeImportDrawer from '@/modules/academicAffairs/components/AaAuthoritativeImportDrawer.vue'
import AaScheduleGrid from '@/modules/academicAffairs/components/AaScheduleGrid.vue'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { academicFileExchangeApi } from '@/modules/academicAffairs/api/academic-file-exchange.api'
import { toast } from '@/utils/toast'

const IMPORT_TERMINAL = new Set(['VALIDATED', 'VALIDATION_FAILED', 'FAILED', 'EXPIRED', 'SUCCEEDED'])
const delay = (milliseconds) => new Promise((resolve) => window.setTimeout(resolve, milliseconds))

function previewResponse(item, message) {
  const preview = item.preview || {}
  const invalidRows = preview.invalidRows ?? item.invalidRows ?? 0
  const validated = item.status === 'VALIDATED'
  return {
    code: validated || item.status === 'VALIDATION_FAILED' ? 0 : 1,
    message: message || item.errorMessage || '导入任务尚未完成安全扫描与服务端预检',
    data: {
      total: preview.totalRows ?? item.totalRows ?? 0,
      validRows: preview.validRows ?? item.validRows ?? 0,
      invalidRows,
      passed: validated && invalidRows === 0,
      rows: preview.rows || [],
      errors: preview.errors || [],
      jobId: item.id,
      expectedVersion: item.version,
      status: item.status
    }
  }
}

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
      readyTasks: [], taskBatchIds: new Set(), taskLoading: false, taskLoadError: '',
      scheduleBatch: null,
      importVisible: false, currentImportJob: null,
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
    taskOptions() {
      return this.readyTasks
        .filter((task) => !this.classId || String(task.classId || '') === String(this.classId))
        .map((task) => ({
          value: String(task.taskId),
          label: `${task.courseName || task.courseCode || '课程'} · ${task.teachingClassName || `班级${task.classId || '—'}`} · ${task.teacherName || '教师待确认'}`
        }))
    },
    taskWeekText() {
      if (!this.selectedTask) return '选择任务后显示正式周次'
      const start = this.selectedTask.startWeek ?? '—'
      const end = this.selectedTask.endWeek ?? '—'
      return `${start}-${end} 周`
    },
    weekParityOptions() {
      return [
        { value: 'ALL', label: '全周' },
        { value: 'ODD', label: '单周' },
        { value: 'EVEN', label: '双周' }
      ]
    }
  },
  created() {
    this.loadSlots()
    this.loadReadyTasks()
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
        if (tasks.code !== 0) throw new Error(tasks.message || 'READY 教学任务读取失败')
        this.readyTasks = (tasks.data?.list || []).filter((task) => allowedBatches.has(String(task.batchId)))
      } catch (error) {
        this.readyTasks = []
        this.taskLoadError = error?.message || 'READY 教学任务读取失败'
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
        taskId: '', classroomId: '', classroom: '',
        startWeek: null, endWeek: null, weekParity: 'ALL'
      }
    },
    onItemClick(it) {
      toast.info(`${it.courseName} · ${it.teacherName || ''} · ${it.startWeek}-${it.endWeek}周`)
    },
    async onItemMove({ item, weekday, slotNo }) {
      const res = await academicAffairsApi.moveScheduleItem(item.itemId, weekday, slotNo)
      if (res.code === 0) { toast.success(`已调整到周${weekday}第${slotNo}节`); await this.loadClass() }
      else toast.error(res.message)
    },
    async doAdd() {
      if (!this.add.taskId) { toast.error('请先选择 READY 教学任务'); return }
      const task = this.selectedTask
      if (!task) { toast.error('教学任务已失效，请刷新后重新选择'); return }
      if (this.classId && String(task.classId || '') !== String(this.classId)) {
        toast.error('所选教学任务不属于当前班级，请重新选择')
        return
      }
      this.add.submitting = true
      this.lastConflict = ''
      const body = {
        taskId: String(task.taskId),
        weekday: this.add.weekday,
        slotNo: this.add.slotNo,
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
    async waitForImportJob(initial) {
      let item = initial
      for (let attempt = 0; attempt < 60 && !IMPORT_TERMINAL.has(item.status); attempt += 1) {
        await delay(1500)
        const detail = await academicFileExchangeApi.getImportJob(item.id)
        if (detail.code !== 0) return detail
        item = detail.data
        this.currentImportJob = { id: item.id, version: item.version, status: item.status }
      }
      if (!IMPORT_TERMINAL.has(item.status)) {
        return { code: 1, data: null, message: '文件仍在后台安全扫描；扫描完成前不会开放确认' }
      }
      return { code: 0, data: item, message: item.errorMessage || '服务端预检已完成' }
    },
    async uploadAuthoritative(file) {
      const res = await academicFileExchangeApi.uploadScheduleImport(this.batchId, file)
      if (res.code !== 0) return res
      this.currentImportJob = { id: res.data.id, version: res.data.version, status: res.data.status }
      const terminal = IMPORT_TERMINAL.has(res.data.status)
        ? { code: 0, data: res.data, message: res.message }
        : await this.waitForImportJob(res.data)
      if (terminal.code !== 0) return terminal
      this.currentImportJob = { id: terminal.data.id, version: terminal.data.version, status: terminal.data.status }
      return previewResponse(terminal.data, terminal.message)
    },
    async confirmAuthoritative() {
      if (!this.currentImportJob?.id) return { code: 1, message: '导入任务已丢失，请重新上传预检' }
      if (this.currentImportJob.status !== 'VALIDATED') {
        const detail = await academicFileExchangeApi.getImportJob(this.currentImportJob.id)
        if (detail.code !== 0) return detail
        this.currentImportJob = { id: detail.data.id, version: detail.data.version, status: detail.data.status }
        if (detail.data.status !== 'VALIDATED') {
          return { code: 1, message: '安全扫描或服务端预检尚未通过，禁止确认导入' }
        }
      }
      const res = await academicFileExchangeApi.confirmImport(this.currentImportJob.id, this.currentImportJob.version)
      if (res.code === 0) this.currentImportJob = null
      return res
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
@media (max-width: 760px) {
  .aa-assign-form { grid-template-columns: 1fr; }
  .aa-assign-form__wide, .aa-task-echo { grid-column: 1; }
  .aa-task-echo { grid-template-columns: 1fr; }
}
</style>
