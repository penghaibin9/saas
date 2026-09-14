<template>
  <ModulePageShell
    title="排课 · 课表维护"
    subtitle="从排课任务队列进入班级网格，点击候选课位后先校验教师、班级、教室冲突，再确认写入"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton @click="returnToQueue">返回原队列</AppButton>
      <button class="mp-btn" :disabled="!canEditBatch" @click="importVisible = true">批量导入 XLSX</button>
    </template>

    <div class="mp-stack">
      <AaScheduleStageRail mode="scheduling" :active-index="scheduleBatch?.status === 'DRAFT' ? 2 : 3" />
      <AppSectionCard v-if="scheduleBatch" compact title="课表批次与当前正式版本">
        <div class="aa-batch-truth">
          <div class="aa-batch-truth__head">
            <div>
              <strong>{{ scheduleBatch.batchName || `课表批次 ${scheduleBatch.batchId}` }}</strong>
              <p>批次 ID {{ scheduleBatch.batchId }} · {{ batchStatusLabel }}</p>
            </div>
            <AppStatusTag :type="batchHead.type" dot>{{ batchHead.label }}</AppStatusTag>
          </div>
          <div class="aa-batch-truth__grid">
            <div><span>正式范围</span><strong>{{ formalScopeText }}</strong></div>
            <div><span>当前正式批次</span><strong>{{ activeBatchText }}</strong></div>
            <div><span>正式头版本</span><strong>{{ headVersionText }}</strong></div>
            <div><span>正式头发布时间</span><strong>{{ headPublishedAtText }}</strong></div>
          </div>
          <p class="mp-note">{{ batchHead.detail }}</p>
        </div>
      </AppSectionCard>
      <div class="aa-filter">
        <label class="aa-filter__item">班级<AppClassPicker v-model="classId" placeholder="选择班级" @change="onClassPicked" /></label>
        <AppButton @click="loadClass">载入课表</AppButton>
        <span class="mp-note">{{ scheduleBatch?.status === 'DRAFT' ? '排课新增只接受同学期“已就绪”教学任务；班级选择只决定当前课表视图与可选任务范围。' : '正式或历史批次按班级直接只读，不依赖教学任务准备链，也不会开放排课写入。' }}</span>
      </div>

      <AppInlineAlert v-if="lastConflict" type="error" :message="lastConflict" />
      <AaOperationReceipt :receipt="receipt" />
      <AppButton v-if="pendingWrite" @click="retryPendingRead">只读核对原排课结果</AppButton>
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
      <AppInlineAlert
        v-if="focusItemError"
        type="error"
        title="指定课位无法精确定位"
        :description="focusItemError"
      />
      <section v-else-if="focusedItem" class="aa-focused-item" aria-live="polite">
        <div class="aa-focused-item__head">
          <div>
            <span>资源占用 / 冲突来源课位</span>
            <strong>{{ focusedItem.courseName || '课程待确认' }}</strong>
          </div>
          <AppStatusTag type="success" dot>已精确定位</AppStatusTag>
        </div>
        <div class="aa-focused-item__grid">
          <div><span>课位 / 批次</span><strong>#{{ focusedItem.itemId }} / #{{ focusedItem.batchId }}</strong></div>
          <div><span>班级 / 任务</span><strong>#{{ focusedItem.classId }} / #{{ focusedItem.taskId }}</strong></div>
          <div><span>原课位</span><strong>周{{ focusedItem.weekday }} · 第{{ focusedItem.slotNo }}节</strong></div>
          <div><span>周次 / 教室</span><strong>{{ focusedItem.startWeek }}-{{ focusedItem.endWeek }}周 · {{ focusedItem.classroom || '教室待确认' }}</strong></div>
        </div>
        <p class="mp-note">当前只展示服务端按批次、班级、任务和课位 ID 共同确认的原课位；任一 ID 不一致都不会用名称近似匹配。</p>
      </section>

      <LoadingState v-if="loading" />
      <AppSectionCard v-else :title="classId ? ('班级 ' + (className || '已选择班级') + ' 课表') : preferredTask ? (preferredTask.teachingClassName + ' · ' + preferredTask.courseName) : '请先载入班级课表'">
        <AaScheduleGrid
          :items="items"
          :slots="slots"
          :editable="!!(classId || preferredTask) && canEditBatch && !taskLoading && !taskLoadError"
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
        <label>教室<AppClassroomPicker v-model="add.classroomId" :query="{ purpose: 'SCHEDULE' }" @change="onClassroomPicked" /></label>
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
      v-if="importVisible && canEditBatch"
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
/** AA-144 · 课表维护：班级视图保持不变；新增写入改为 READY TeachingTask-first，批量导入由统一权威 ImportJob Drawer 接管。 */
import { ModulePageShell, LoadingState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppSectionCard, AppConfirmDialog, AppInlineAlert, AppSelect, AppClassPicker, AppClassroomPicker, AppStatusTag } from '@/components/common'
import AaAuthoritativeImportDrawer from '@/modules/academicAffairs/components/AaAuthoritativeImportDrawer.vue'
import AaScheduleGrid from '@/modules/academicAffairs/components/AaScheduleGrid.vue'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { SCHEDULE_BATCH_STATUS } from '@/modules/academicAffairs/constants/teaching'
import { academicFileExchangeApi } from '@/modules/academicAffairs/api/academic-file-exchange.api'
import { toast } from '@/utils/toast'
import { academicRouteState, createAcademicRequestGate, routeScalar } from '../academicFlowContext'
import { isDeniedResult, isConflictResult } from '../components/parallel-a/resultState'
import AaOperationReceipt from '../components/parallel-a/AaOperationReceipt.vue'
import { scheduleTruthPresentation } from '../components/parallel-a/scheduleTruthPresentation'
import { readAllPages } from '../components/parallel-a/pagedRead'
import AaScheduleStageRail from '../components/AaScheduleStageRail.vue'

export default {
  name: 'AaScheduleMaintainView',
  components: {
    ModulePageShell, LoadingState, AppButton, AppSectionCard, AppConfirmDialog, AppInlineAlert,
    AppSelect, AppClassPicker, AppClassroomPicker, AppStatusTag, AaAuthoritativeImportDrawer, AaScheduleGrid, AaOperationReceipt, AaScheduleStageRail
  },
  props: { ctx: { type: Object, required: true } },
  inject: { academicFlow: { default: null } },
  data() {
    return {
      academicAffairsApi, academicFileExchangeApi,
      loading: false, disposed: false, routeSyncing: false, slotsSeq: 0,
      routeBatchId: '',
      slots: [], items: [], classId: '', className: '',
      conflictCell: null, lastConflict: '',
      moveConflict: { item: null, alternatives: [] }, moving: false,
      preflight: { loading: false, result: null, requestSeq: 0, timer: null },
      readyTasks: [], taskBatchIds: new Set(), taskLoading: false, taskLoadError: '',
      preferredTaskId: '',
      focusItemId: '', focusTaskId: '', focusTermId: '', focusedItem: null, focusItemError: '',
      scheduleBatch: null,
      receipt: null, pendingWrite: null,
      importVisible: false,
      add: {
        visible: false, submitting: false, weekday: 1, slotNo: 1,
        taskId: '', classroomId: '', classroom: '',
        startWeek: null, endWeek: null, weekParity: 'ALL'
      }
    }
  },
  computed: {
    batchId() { return this.routeBatchId },
    identityKey() { return JSON.stringify([this.academicFlow?.identity?.(), this.ctx?.currentRole, this.ctx?.dataScope, this.ctx?.ctxKey, this.ctx?.permissionVersion]) },
    canEditBatch() {
      return this.scheduleBatch?.status === 'DRAFT' && !this.taskLoadError &&
        String(this.$route.query.classId || '') === String(this.classId || '') &&
        (!this.focusItemId || !!this.focusedItem) && !this.pendingWrite && !this.moving
    },
    batchStatusLabel() { return SCHEDULE_BATCH_STATUS[this.scheduleBatch?.status] || (this.scheduleBatch?.status ? '状态待确认' : '') },
    formalScopeText() {
      const truth = this.scheduleBatch?.activeTruth || {}
      if (!truth.scopeType && !truth.scopeId) return '待服务端确认'
      return `${({ SCHOOL: '全校', COLLEGE: '学院' })[truth.scopeType] || '范围待确认'}${truth.scopeId ? ` · ${truth.scopeId}` : ''}`
    },
    activeBatchText() {
      const truth = this.scheduleBatch?.activeTruth
      if (truth?.truthStatus === 'VERIFIED') return truth.activeBatchId || '待服务端确认'
      if (truth?.truthStatus === 'NOT_PUBLISHED') return '尚无正式头'
      return '待服务端确认'
    },
    headVersionText() {
      const truth = this.scheduleBatch?.activeTruth
      if (truth?.truthStatus === 'NOT_PUBLISHED') return '—'
      return truth?.truthStatus === 'VERIFIED' && truth.headVersion != null ? truth.headVersion : '待服务端确认'
    },
    headPublishedAtText() {
      const truth = this.scheduleBatch?.activeTruth
      if (truth?.truthStatus === 'NOT_PUBLISHED') return '—'
      return truth?.truthStatus === 'VERIFIED' ? (truth.publishedAt || '—') : '待服务端确认'
    },
    batchHead() { return scheduleTruthPresentation(this.scheduleBatch) },
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
    '$route.fullPath'() { this.syncRoute() },
    identityKey() { this.clearSensitive('身份或数据范围已变化'); this.loadSlots(); this.syncRoute() },
    classId() { if (!this.routeSyncing) this.invalidateClass() },
    'add.taskId'() { this.queuePreflight() },
    'add.classroom'() { this.queuePreflight() },
    'add.weekParity'() { this.queuePreflight() },
    'add.startWeek'() { this.queuePreflight() },
    'add.endWeek'() { this.queuePreflight() },
    'add.weekday'() { this.queuePreflight() },
    'add.slotNo'() { this.queuePreflight() }
  },
  created() {
    this.taskGate = createAcademicRequestGate(() => this.contextKey())
    this.classGate = createAcademicRequestGate(() => this.contextKey())
    this.moveGate = createAcademicRequestGate(() => this.contextKey())
    this.loadSlots()
    this.syncRoute()
  },
  beforeUnmount() {
    this.disposed = true; this.slotsSeq += 1
    this.taskGate.invalidate(); this.invalidateClass()
  },
  methods: {
    contextKey() {
      return JSON.stringify([
        this.identityKey,
        this.$route?.fullPath, this.batchId, this.classId, this.focusTermId, this.focusTaskId, this.focusItemId
      ])
    },
    clearSensitive(message) {
      this.taskGate.invalidate(); this.invalidateClass(); this.slotsSeq += 1
      this.slots = []; this.readyTasks = []; this.scheduleBatch = null; this.taskBatchIds = new Set()
      this.pendingWrite = null; this.receipt = null; this.className = ''; this.preferredTaskId = ''
      this.focusItemId = ''; this.focusTaskId = ''; this.focusTermId = ''; this.focusedItem = null; this.focusItemError = ''
      this.taskLoading = false; this.taskLoadError = message || '权限或数据范围已变化，请重新进入'
    },
    async requestResult(request) {
      try { return await request() }
      catch (error) { return { code: 'REQUEST_ERROR', status: error?.response?.status, message: error?.message || '网络连接中断，请只读核对结果' } }
    },
    invalidateClass() {
      this.classGate.invalidate(); this.moveGate.invalidate()
      this.items = []; this.loading = false; this.lastConflict = ''; this.conflictCell = null
      this.focusedItem = null
      if (!this.focusItemId) this.focusItemError = ''
      this.moveConflict = { item: null, alternatives: [] }
      this.moving = false
      this.add = { ...this.add, visible: false, submitting: false }
      this.importVisible = false
      clearTimeout(this.preflight.timer)
      this.preflight.requestSeq++; this.preflight.result = null; this.preflight.loading = false
    },
    async syncRoute() {
      if (this.disposed) return
      this.taskGate.invalidate(); this.invalidateClass()
      this.receipt = null
      this.readyTasks = []; this.scheduleBatch = null; this.taskBatchIds = new Set(); this.taskLoadError = ''; this.taskLoading = false
      const state = academicRouteState(this.$route)
      const rawItemId = this.$route.query.itemId
      const rawDate = this.$route.query.date
      const rawReturnToken = this.$route.query.returnToken
      const itemId = routeScalar(rawItemId)
      const invalidItemId = rawItemId != null && (typeof rawItemId !== 'string' || !/^[A-Za-z0-9_-]{1,128}$/.test(itemId))
      const invalidDate = rawDate != null && (typeof rawDate !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(routeScalar(rawDate)))
      const invalidReturnToken = rawReturnToken != null && typeof rawReturnToken !== 'string'
      this.routeBatchId = state.error ? '' : state.batchId
      this.routeSyncing = true
      this.preferredTaskId = state.taskId
      this.focusTaskId = state.taskId
      this.focusTermId = state.termId
      this.focusItemId = invalidItemId ? '' : itemId
      this.classId = state.classId
      this.className = ''
      this.focusedItem = null
      this.focusItemError = this.focusItemId && (!this.classId || !this.focusTaskId)
        ? `课位 #${this.focusItemId} 缺少正式班级 ID 或任务 ID，无法定位原课位。`
        : ''
      const context = this.contextKey()
      await this.$nextTick()
      this.routeSyncing = false
      if (this.disposed || context !== this.contextKey()) return
      if (state.error || invalidItemId || invalidDate || invalidReturnToken) {
        this.taskLoadError = state.error || (invalidItemId ? '课位 ID 参数无效，请从资源占用或冲突台账重新进入。' : invalidDate
          ? '来源日期参数无效，请从资源占用或冲突台账重新进入。' : '返回位置参数无效，请从原业务入口重新进入。')
        return
      }
      await this.loadReadyTasks()
      if (!this.disposed && context === this.contextKey() && (this.classId || this.preferredTask) && !this.taskLoadError) await this.loadClass()
    },
    returnToQueue() {
      return this.academicFlow?.back(this.$route.query.returnToken, '/admin/academic-affairs/scheduling')
        || this.$router.push('/admin/academic-affairs/scheduling')
    },
    async loadReadyTasks() {
      const current = this.taskGate.begin()
      const batchId = this.batchId
      this.taskLoading = true
      this.taskLoadError = ''
      try {
        if (!batchId) throw new Error('课表批次参数缺失，请返回原队列重新进入。')
        const batches = await academicAffairsApi.getScheduleBatch(batchId)
        if (!current()) return
        if (isDeniedResult(batches)) return this.clearSensitive(batches.message)
        if (batches.code !== 0) throw new Error(batches.message || '课表批次读取失败')
        const scheduleBatch = batches.data
        if (String(scheduleBatch?.batchId || '') !== String(batchId)) throw new Error('服务端返回了不同的课表批次，已拒绝更新当前页面。')
        if (!scheduleBatch.termId) throw new Error('当前课表批次未绑定正式学期')
        this.scheduleBatch = scheduleBatch

        if (scheduleBatch.status !== 'DRAFT') {
          this.readyTasks = []
          this.taskBatchIds = new Set()
          return
        }

        const taskBatches = await readAllPages(
          (page, pageSize) => academicAffairsApi.getTaskBatches({ termId: scheduleBatch.termId, status: 'APPROVED', page, pageSize }),
          { identity: row => row.batchId }
        )
        if (!current()) return
        if (isDeniedResult(taskBatches)) return this.clearSensitive(taskBatches.message)
        if (taskBatches.code !== 0) throw new Error(taskBatches.message || '教学任务批次读取失败')
        const allowedBatches = new Set(
          (taskBatches.data?.list || [])
            .filter((row) => !scheduleBatch.collegeId || !row.collegeId || String(row.collegeId) === String(scheduleBatch.collegeId))
            .map((row) => String(row.batchId))
        )
        this.taskBatchIds = allowedBatches

        const readyTasks = []
        for (const taskBatchId of allowedBatches) {
          const tasks = await readAllPages(
            (page, pageSize) => academicAffairsApi.getBatchTasks(taskBatchId, { status: 'READY', page, pageSize }),
            { identity: row => row.taskId }
          )
          if (!current()) return
          if (isDeniedResult(tasks)) return this.clearSensitive(tasks.message)
          if (tasks.code !== 0) throw new Error(tasks.message || `教学任务批次 ${taskBatchId} 读取失败`)
          readyTasks.push(...(tasks.data?.list || []))
        }
        this.readyTasks = readyTasks
      } catch (error) {
        if (!current()) return
        if (Number(error?.response?.status) === 403) return this.clearSensitive(error?.message)
        this.readyTasks = []; this.scheduleBatch = null; this.taskBatchIds = new Set(); this.invalidateClass()
        this.taskLoadError = error?.message || '已就绪教学任务读取失败'
      } finally {
        if (current()) this.taskLoading = false
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
      const identity = this.identityKey, seq = ++this.slotsSeq
      const res = await this.requestResult(() => academicAffairsApi.getTimeSlots())
      if (this.disposed || identity !== this.identityKey || seq !== this.slotsSeq) return
      if (isDeniedResult(res)) return this.clearSensitive(res.message)
      this.slots = res.code === 0 && Array.isArray(res.data) ? res.data : []
    },
    async loadClass() {
      if (!this.classId && !this.preferredTask?.teacherKey) { toast.error('请先选择班级或从教学任务进入'); return }
      if (this.classId && this.$route.query.classId !== this.classId) {
        await this.$router.replace({ path: this.$route.path, query: { ...this.$route.query, classId: this.classId, taskId: undefined, itemId: undefined, className: undefined } })
        return
      }
      const current = this.classGate.begin()
      this.items = []
      this.focusedItem = null
      if (this.focusItemId) this.focusItemError = ''
      this.loading = true
      try {
        const taskId = String(this.preferredTaskId || '')
        const res = this.classId
          ? await academicAffairsApi.getScheduleClassView(this.batchId, this.classId)
          : await academicAffairsApi.getScheduleTeacherView(this.batchId, this.preferredTask.teacherKey)
        if (!current()) return
        if (isDeniedResult(res)) return this.clearSensitive(res.message)
        if (res.code !== 0) throw new Error(res.message || '载入失败')
        if (!Array.isArray(res.data?.items)) throw new Error('班级课表未完整返回，请重新读取。')
        this.items = this.classId ? res.data.items : res.data.items.filter(item => String(item.taskId) === taskId)
        this.className = res.data?.className || ''
        this.locateFocusedItem()
        this.reconcilePendingWrite()
      } catch (error) {
        if (current() && Number(error?.response?.status) === 403) return this.clearSensitive(error?.message)
        if (current()) this.lastConflict = error?.message || '课表读取失败，请重试'
      } finally {
        if (current()) { this.loading = false; this.academicFlow?.restorePosition() }
      }
    },
    locateFocusedItem() {
      this.focusedItem = null
      if (!this.focusItemId) { this.focusItemError = ''; return }
      if (!this.classId || !this.focusTaskId) {
        this.focusItemError = `课位 #${this.focusItemId} 缺少正式班级 ID 或任务 ID，无法定位原课位。`
        return
      }
      const matches = this.items.filter((item) => String(item.itemId || '') === String(this.focusItemId))
      if (matches.length !== 1) {
        this.focusItemError = matches.length
          ? `班级 #${this.classId} 的课表返回了重复的课位 #${this.focusItemId}，已拒绝近似定位。`
          : `班级 #${this.classId} 的当前批次未找到课位 #${this.focusItemId}；课表事实可能已变化，请返回来源页重新查询。`
        return
      }
      const item = matches[0]
      if ((this.focusTermId && String(this.scheduleBatch?.termId || '') !== String(this.focusTermId)) ||
        String(item.batchId || '') !== String(this.batchId) || String(item.classId || '') !== String(this.classId) || String(item.taskId || '') !== String(this.focusTaskId)) {
        this.focusItemError = `课位 #${this.focusItemId} 与入口携带的学期、批次、班级或任务 ID 不一致，已拒绝用课程名或班级名替代定位。`
        return
      }
      this.focusedItem = item
      this.focusItemError = ''
    },
    reconcilePendingWrite() {
      const frozen = this.pendingWrite
      if (!frozen || frozen.identity !== this.identityKey || String(frozen.batchId) !== String(this.batchId) || String(frozen.classId) !== String(this.classId)) return null
      const formal = frozen.acknowledged && frozen.itemId
        ? this.items.find(item => String(item.itemId) === String(frozen.itemId)
          && String(item.taskId) === String(frozen.taskId) && Number(item.weekday) === frozen.weekday && Number(item.slotNo) === frozen.slotNo)
        : null
      this.receipt = formal ? {
        title: '排课草稿已更新并核对', object: frozen.courseName,
        status: '周' + formal.weekday + '第' + formal.slotNo + '节', time: formal.updatedAt || formal.createdAt || '',
        next: '继续补齐剩余课位；正式发布前还需通过冲突与漏排门禁。', pending: false
      } : {
        title: '排课结果待确认', object: frozen.courseName,
        status: frozen.acknowledged ? '命令已受理，尚未读到匹配课位' : '尚未取得可归属本次请求的回执', time: '',
        next: '仅刷新原批次和班级课表核对，不会自动重复排课。', pending: true
      }
      if (formal) this.pendingWrite = null
      return formal
    },
    async retryPendingRead() {
      const pending = this.pendingWrite
      if (!pending || pending.identity !== this.identityKey) return
      if (String(pending.batchId) !== String(this.batchId) || String(pending.classId) !== String(this.classId)) {
        return this.$router.push({ path: '/admin/academic-affairs/schedule/' + pending.batchId + '/edit', query: { classId: String(pending.classId), returnToken: this.$route.query.returnToken } })
      }
      await this.loadClass()
    },
    onCellClick({ weekday, slotNo }) {
      if (!this.canEditBatch || this.taskLoadError || this.taskLoading) return
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
      if (!this.canEditBatch) return
      const current = this.moveGate.begin()
      const context = this.contextKey()
      this.moving = true
      this.lastConflict = ''
      this.moveConflict = { item: null, alternatives: [] }
      const checked = await this.requestResult(() => academicAffairsApi.preflightScheduleMove(item.itemId, weekday, slotNo))
      if (!current()) return
      if (isDeniedResult(checked)) return this.clearSensitive(checked.message)
      if (checked.code !== 0 || !checked.data?.allowed) {
        this.moving = false
        this.conflictCell = { weekday, slotNo }
        this.lastConflict = checked.data?.conflict?.detail || checked.data?.blockers?.[0] || checked.message || '目标课位存在硬冲突'
        this.moveConflict = { item, alternatives: checked.data?.alternatives || [] }
        toast.error(this.lastConflict)
        return
      }
      this.pendingWrite = { itemId: item.itemId, taskId: item.taskId, batchId: this.batchId, classId: this.classId,
        identity: this.identityKey, weekday: Number(weekday), slotNo: Number(slotNo),
        courseName: item.courseName, acknowledged: false }
      const frozen = this.pendingWrite
      const res = await this.requestResult(() => academicAffairsApi.moveScheduleItem(frozen.itemId, weekday, slotNo))
      if (this.disposed || frozen.identity !== this.identityKey || this.pendingWrite !== frozen) return
      frozen.acknowledged = res.code === 0 && String(res.data?.itemId) === String(frozen.itemId)
        && String(res.data?.batchId) === String(frozen.batchId) && String(res.data?.taskId) === String(frozen.taskId)
        && Number(res.data?.weekday) === frozen.weekday && Number(res.data?.slotNo) === frozen.slotNo
      if (isDeniedResult(res)) return this.clearSensitive(res.message)
      if (isConflictResult(res)) this.pendingWrite = null
      if (!current()) return
      this.moving = false
      if (isConflictResult(res)) { this.lastConflict = res.message || '课位已变化，请重新预检'; return }
      await this.loadClass()
      if (!this.disposed && context === this.contextKey()) this.reconcilePendingWrite()
    },
    applyMoveAlternative(slot) {
      const item = this.moveConflict.item
      if (!item) return
      this.onItemMove({ item, weekday: Number(slot.weekday), slotNo: Number(slot.slotNo) })
    },
    async doAdd() {
      if (!this.canEditBatch || !this.add.visible || this.add.submitting || this.pendingWrite) return
      if (!this.add.taskId) { toast.error('请先选择已就绪教学任务'); return }
      const task = this.selectedTask
      if (!task) { toast.error('教学任务已失效，请刷新后重新选择'); return }
      if (this.classId && String(task.classId || '') !== String(this.classId)) {
        toast.error('所选教学任务不属于当前班级，请重新选择')
        return
      }
      if (this.preflight.loading || !this.preflight.result?.allowed) {
        toast.error(this.preflightMessage || '请先通过排课前置校验')
        return
      }
      this.add.submitting = true
      const command = this.add, context = this.contextKey()
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
      this.pendingWrite = { ...body, batchId: this.batchId, classId: this.classId, identity: this.identityKey, itemId: '', acknowledged: false, courseName: task.courseName || task.courseCode || '教学任务' }
      const frozen = this.pendingWrite
      const res = await this.requestResult(() => academicAffairsApi.addScheduleItem(frozen.batchId, body))
      if (this.disposed || frozen.identity !== this.identityKey || this.pendingWrite !== frozen) return
      frozen.itemId = res.data?.itemId || ''
      frozen.acknowledged = res.code === 0 && !!frozen.itemId && String(res.data?.taskId) === String(frozen.taskId)
        && String(res.data?.batchId) === String(frozen.batchId)
        && Number(res.data?.weekday) === frozen.weekday && Number(res.data?.slotNo) === frozen.slotNo
      if (isDeniedResult(res)) return this.clearSensitive(res.message)
      if (isConflictResult(res)) this.pendingWrite = null
      if (command !== this.add || context !== this.contextKey()) return
      this.add.submitting = false
      if (isConflictResult(res)) {
        this.conflictCell = { weekday: this.add.weekday, slotNo: this.add.slotNo }
        this.lastConflict = res.message || '排课事实已变化，请保留当前输入并重新预检。'
        this.preflight.result = null
        return
      }
      this.add.visible = false
      await this.loadClass()
      if (!this.disposed && context === this.contextKey()) this.reconcilePendingWrite()
    },
    queuePreflight() {
      if (this.preflight.timer) clearTimeout(this.preflight.timer)
      this.preflight.requestSeq++
      this.preflight.result = null
      this.preflight.loading = false
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
      const context = this.contextKey()
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
      const response = await this.requestResult(() => academicAffairsApi.preflightScheduleItem(this.batchId, body))
      if (this.disposed || seq !== this.preflight.requestSeq || context !== this.contextKey()) return
      if (isDeniedResult(response)) return this.clearSensitive(response.message)
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
.aa-batch-truth { display: flex; flex-direction: column; gap: 14px; }
.aa-batch-truth__head { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; }
.aa-batch-truth__head p { margin: 5px 0 0; color: var(--text-500, #86909c); font-size: 12px; }
.aa-batch-truth__grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; }
.aa-batch-truth__grid > div { display: flex; min-width: 0; flex-direction: column; gap: 5px; padding: 10px 12px; border: 1px solid var(--border-200, #e5e6eb); border-radius: 8px; background: var(--bg-100, #f7f8fa); }
.aa-batch-truth__grid span { color: var(--text-500, #86909c); font-size: 12px; }
.aa-batch-truth__grid strong { color: var(--text-900, #1f2329); font-size: 13px; overflow-wrap: anywhere; }
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
.aa-focused-item { padding: 14px; border: 1px solid var(--success-200, #bbf7d0); border-radius: 10px; background: var(--success-50, #f0fdf4); }
.aa-focused-item__head { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; }
.aa-focused-item__head span, .aa-focused-item__head strong { display: block; }
.aa-focused-item__head span { color: var(--text-500, #86909c); font-size: 12px; }
.aa-focused-item__head strong { margin-top: 4px; color: var(--text-900, #1f2329); font-size: 15px; }
.aa-focused-item__grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; margin-top: 12px; }
.aa-focused-item__grid > div { min-width: 0; padding: 9px 10px; border: 1px solid var(--success-200, #bbf7d0); border-radius: 7px; background: var(--bg-white, #fff); }
.aa-focused-item__grid span, .aa-focused-item__grid strong { display: block; }
.aa-focused-item__grid span { color: var(--text-500, #86909c); font-size: 12px; }
.aa-focused-item__grid strong { margin-top: 4px; color: var(--text-900, #1f2329); font-size: 13px; overflow-wrap: anywhere; }
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
  .aa-batch-truth__head { flex-direction: column; }
  .aa-batch-truth__grid, .aa-focused-item__grid { grid-template-columns: 1fr; }
  .aa-focused-item__head { flex-direction: column; }
  .aa-assign-form { grid-template-columns: 1fr; }
  .aa-assign-form__wide, .aa-task-echo { grid-column: 1; }
  .aa-task-echo { grid-template-columns: 1fr; }
}
@media (min-width: 761px) and (max-width: 980px) { .aa-batch-truth__grid, .aa-focused-item__grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
</style>
