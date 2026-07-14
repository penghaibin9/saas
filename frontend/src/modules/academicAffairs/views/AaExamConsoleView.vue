<template>
  <ModulePageShell
    title="考务管理 · 教务处控制台"
    :subtitle="'批次：草稿→圈课→学院确认→编排→发布→结束→归档 · 共 ' + pagination.total + ' 个批次'"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton variant="primary" @click="openCreate">新建考试批次</AppButton>
    </template>

    <div class="aaexam-layout">
      <div class="aaexam-list">
        <ErrorState v-if="error" :description="error" @retry="load" />
        <LoadingState v-else-if="loading" />
        <EmptyState v-else-if="!rows.length" title="暂无考试批次" description="点击右上角新建" />
        <ul v-else class="aaexam-batches">
          <li v-for="b in rows" :key="b.batchId"
              :class="['aaexam-batch', { 'is-active': current && current.batchId === b.batchId }]"
              @click="select(b)">
            <div class="aaexam-batch-name">{{ b.batchName }}</div>
            <StatusTag :type="statusType(b.status)" :label="statusLabel(b.status)" dot />
          </li>
        </ul>
      </div>

      <div class="aaexam-detail">
        <EmptyState v-if="!current" title="选择一个批次" description="从左侧选择批次以圈定课程、编排考场与监考" />
        <template v-else>
          <div class="aaexam-head">
            <div>
              <div class="aaexam-title">{{ current.batchName }}</div>
              <StatusTag :type="statusType(current.status)" :label="statusLabel(current.status)" dot />
            </div>
            <div class="aaexam-actions">
              <AppButton v-if="current.status === 'DRAFT'" size="small" variant="ghost" @click="openAddCourse">+ 圈课</AppButton>
              <AppButton v-if="current.status === 'DRAFT'" size="small" variant="primary" @click="lc('confirmBatchCourses', '推进(课程确认完成)')">推进</AppButton>
              <AppButton v-if="current.status === 'COURSE_CONFIRMED'" size="small" variant="primary" @click="lc('publishBatch', '发布')">发布</AppButton>
              <AppButton v-if="current.status === 'PUBLISHED'" size="small" variant="warning" @click="lc('finishBatch', '结束考试')">结束</AppButton>
              <AppButton v-if="current.status === 'FINISHED'" size="small" variant="ghost" @click="lc('archiveBatch', '归档')">归档</AppButton>
            </div>
          </div>

          <div v-if="stats" class="aaexam-stats">
            <span>课程 {{ stats.courseCount }}</span>
            <span>已确认 {{ stats.confirmedCount }}</span>
            <span :class="{ 'is-warn': stats.absentCount }">缺考 {{ stats.absentCount }}</span>
            <span :class="{ 'is-warn': stats.violationCount }">违纪 {{ stats.violationCount }}</span>
          </div>

          <div class="aaexam-section-title">考试课程</div>
          <EmptyState v-if="!courses.length" title="未圈定课程" description="从教学任务圈定考试课程" />
          <DataTable v-else :columns="courseColumns" :rows="courses" row-key="examCourseId">
            <template #cell-course="{ row }">
              <div class="mp-cell-main">{{ row.courseName }}</div>
              <div class="mp-cell-sub">{{ row.className }} · {{ row.teacherName || '未派课' }}</div>
            </template>
            <template #cell-schedule="{ row }">{{ row.examDate || '—' }} {{ row.startTime || '' }}</template>
            <template #cell-status="{ row }">
              <StatusTag :type="row.status === 'CONFIRMED' ? 'success' : 'primary'"
                         :label="row.status === 'CONFIRMED' ? '已确认' : '待确认'" dot />
            </template>
            <template #cell-ops="{ row }">
              <button v-if="row.status === 'PENDING_CONFIRM'" class="mp-link" @click="confirm(row, 'CONFIRM')">确认</button>
              <button class="mp-link" @click="openSchedule(row)">设时间</button>
              <button class="mp-link" @click="openArrange(row)">考场</button>
            </template>
          </DataTable>

          <div class="aaexam-section-title">考场异常记录</div>
          <EmptyState v-if="!incidents.length" title="暂无异常" description="发布后监考教师可登记缺考/违纪" />
          <ul v-else class="aaexam-incidents">
            <li v-for="i in incidents" :key="i.incidentId">
              <span>{{ i.studentName }} · {{ i.incidentType === 'ABSENT' ? '缺考' : i.incidentType === 'DISCIPLINE_VIOLATION' ? '违纪' : '其他' }}</span>
              <span class="mp-cell-sub">{{ i.description || '' }}</span>
            </li>
          </ul>
        </template>
      </div>
    </div>

    <AppDrawer :visible="createVisible" title="新建考试批次" @close="createVisible = false">
      <div class="aaexam-form">
        <AppFormItem label="批次名称" required><AppTextInput v-model="form.batchName" placeholder="如 2024秋期末考试" :disabled="saving" /></AppFormItem>
        <AppInlineAlert v-if="formError" type="danger" :description="formError" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="saving" @click="createVisible = false">取消</AppButton>
        <AppButton variant="primary" :loading="saving" @click="submitCreate">创建</AppButton>
      </template>
    </AppDrawer>

    <AppDrawer :visible="courseVisible" title="从教学任务圈定考试课程" @close="courseVisible = false">
      <div class="aaexam-form">
        <AppFormItem label="教学任务 ID" required><AppTextInput v-model="courseTaskId" placeholder="教学任务 ID" :disabled="saving" /></AppFormItem>
        <AppInlineAlert v-if="courseError" type="danger" :description="courseError" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="saving" @click="courseVisible = false">取消</AppButton>
        <AppButton variant="primary" :loading="saving" @click="submitCourse">圈定</AppButton>
      </template>
    </AppDrawer>

    <AppDrawer :visible="schedVisible" title="设置考试时间" @close="schedVisible = false">
      <div class="aaexam-form">
        <AppFormItem label="考试日期"><AppTextInput v-model="sched.examDate" placeholder="YYYY-MM-DD" :disabled="saving" /></AppFormItem>
        <AppFormItem label="开始时间"><AppTextInput v-model="sched.startTime" placeholder="HH:MM" :disabled="saving" /></AppFormItem>
        <AppFormItem label="结束时间"><AppTextInput v-model="sched.endTime" placeholder="HH:MM" :disabled="saving" /></AppFormItem>
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="saving" @click="schedVisible = false">取消</AppButton>
        <AppButton variant="primary" :loading="saving" @click="submitSchedule">保存</AppButton>
      </template>
    </AppDrawer>

    <AppDrawer :visible="arrangeVisible" :title="'考场编排 · ' + (arrangeCourse ? arrangeCourse.courseName : '')" @close="arrangeVisible = false">
      <div class="aaexam-form">
        <div class="aaexam-section-title">已有考场</div>
        <EmptyState v-if="!arrangeRooms.length" title="暂无考场" description="添加考场后可指定监考" />
        <ul v-else class="aaexam-rooms">
          <li v-for="r in arrangeRooms" :key="r.examRoomId">
            <span>考场{{ r.roomSeq }} · {{ r.classroomText }}（{{ r.plannedCount }}/{{ r.capacity }}）</span>
          </li>
        </ul>
        <AppFormItem label="新增考场"><AppTextInput v-model="roomForm.classroomText" placeholder="考场名 如 A101" :disabled="saving" /></AppFormItem>
        <AppFormItem label="容量"><AppNumberInput v-model="roomForm.capacity" :min="1" :max="500" :disabled="saving" /></AppFormItem>
        <AppButton size="small" variant="ghost" :loading="saving" @click="submitRoom">添加考场</AppButton>
      </div>
    </AppDrawer>

    <AppConfirmDialog v-model:visible="confirmVisible" :title="confirmTitle" :message="confirmMessage" @confirm="onConfirm" />
  </ModulePageShell>
</template>

<script>
/** 考务管理 · 教务处控制台（/admin/academic-affairs/exam）：批次生命周期+考试课程+考场编排+异常+统计。 */
import { ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton, AppDrawer } from '@/components/ui'
import { AppTextInput, AppNumberInput, AppFormItem, AppConfirmDialog, AppInlineAlert } from '@/components/common'
import { academicAffairsApi, academicAffairsExamApi as api } from '@/modules/academicAffairs/api/academic-affairs.api'
import { toast } from '@/utils/toast'

const _L = { DRAFT: '草稿', COURSE_CONFIRMED: '课程已确认', ARRANGED: '已编排', PUBLISHED: '已发布', FINISHED: '已结束', ARCHIVED: '已归档' }

export default {
  name: 'AaExamConsoleView',
  components: {
    ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState,
    AppButton, AppDrawer, AppTextInput, AppNumberInput, AppFormItem, AppConfirmDialog, AppInlineAlert
  },
  data() {
    return {
      ctx: { currentRole: { roleName: '' }, dataScope: { scopeName: '' } },
      loading: true, error: '', rows: [], pagination: { page: 1, pageSize: 50, total: 0 },
      current: null, courses: [], stats: null, incidents: [],
      createVisible: false, form: { batchName: '' }, formError: '',
      courseVisible: false, courseTaskId: '', courseError: '',
      schedVisible: false, schedCourse: null, sched: { examDate: '', startTime: '', endTime: '' },
      arrangeVisible: false, arrangeCourse: null, arrangeRooms: [], roomForm: { classroomText: '', capacity: 50 },
      saving: false, confirmVisible: false, confirmTitle: '', confirmMessage: '', pendingAction: null,
      courseColumns: [
        { key: 'course', title: '课程/班级' }, { key: 'schedule', title: '考试时间' },
        { key: 'status', title: '状态' }, { key: 'ops', title: '操作' }
      ]
    }
  },
  async created() {
    const c = await academicAffairsApi.getContext()
    if (c.code === 0) this.ctx = c.data
    this.load()
  },
  methods: {
    statusLabel(s) { return _L[s] || s },
    statusType(s) {
      if (s === 'PUBLISHED') return 'success'
      if (s === 'FINISHED') return 'warning'
      if (s === 'ARCHIVED') return 'default'
      return 'primary'
    },
    async load() {
      this.loading = true; this.error = ''
      const res = await api.listBatches({ page: 1, pageSize: 50 })
      if (res.code === 0) { this.rows = res.data.list; this.pagination.total = res.data.total } else this.error = res.message
      this.loading = false
    },
    async select(b) { this.current = b; await this.refresh() },
    async refresh() {
      if (!this.current) return
      const [cs, st, inc] = await Promise.all([
        api.listCourses(this.current.batchId, { pageSize: 200 }),
        api.batchStats(this.current.batchId),
        api.listIncidents({ batchId: this.current.batchId, pageSize: 100 })
      ])
      this.courses = cs.code === 0 ? cs.data.list : []
      this.stats = st.code === 0 ? st.data : null
      this.incidents = inc.code === 0 ? inc.data.list : []
    },
    openCreate() { this.form = { batchName: '' }; this.formError = ''; this.createVisible = true },
    async submitCreate() {
      if (!this.form.batchName) { this.formError = '批次名称必填'; return }
      this.saving = true
      const res = await api.createBatch({ batchName: this.form.batchName })
      this.saving = false
      if (res.code === 0) { toast.success('已创建'); this.createVisible = false; await this.load() } else this.formError = res.message
    },
    lc(fn, label) {
      this.confirmTitle = label
      this.confirmMessage = `确认对批次「${this.current.batchName}」执行「${label}」？`
      this.pendingAction = async () => {
        const res = await api[fn](this.current.batchId)
        if (res.code === 0) { toast.success(label + '成功'); this.current = res.data; await this.load(); await this.refresh() }
        else toast.error(res.message)
      }
      this.confirmVisible = true
    },
    openAddCourse() { this.courseTaskId = ''; this.courseError = ''; this.courseVisible = true },
    async submitCourse() {
      if (!this.courseTaskId) { this.courseError = '教学任务 ID 必填'; return }
      this.saving = true
      const res = await api.addCourse(this.current.batchId, this.courseTaskId)
      this.saving = false
      if (res.code === 0) { toast.success('已圈定'); this.courseVisible = false; await this.refresh() } else this.courseError = res.message
    },
    async confirm(row, action) {
      const res = await api.confirmCourse(row.examCourseId, action)
      if (res.code === 0) { toast.success('已处理'); await this.refresh() } else toast.error(res.message)
    },
    openSchedule(row) { this.schedCourse = row; this.sched = { examDate: row.examDate || '', startTime: row.startTime || '', endTime: row.endTime || '' }; this.schedVisible = true },
    async submitSchedule() {
      this.saving = true
      const res = await api.setSchedule(this.schedCourse.examCourseId, this.sched)
      this.saving = false
      if (res.code === 0) { toast.success('已保存'); this.schedVisible = false; await this.refresh() } else toast.error(res.message)
    },
    async openArrange(row) {
      this.arrangeCourse = row; this.roomForm = { classroomText: '', capacity: 50 }; this.arrangeVisible = true
      const res = await api.listRooms(row.examCourseId)
      this.arrangeRooms = res.code === 0 ? (res.data.items || []) : []
    },
    async submitRoom() {
      if (!this.roomForm.classroomText) { toast.error('考场名必填'); return }
      this.saving = true
      const res = await api.addRoom(this.arrangeCourse.examCourseId, this.roomForm)
      this.saving = false
      if (res.code === 0) { toast.success('已添加考场'); const r = await api.listRooms(this.arrangeCourse.examCourseId); this.arrangeRooms = r.code === 0 ? r.data.items : [] }
      else toast.error(res.message)
    },
    onConfirm() { const a = this.pendingAction; this.pendingAction = null; if (a) a() }
  }
}
</script>

<style scoped>
.aaexam-layout { display: grid; grid-template-columns: 300px 1fr; gap: 16px; }
.aaexam-batches { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 6px; }
.aaexam-batch { display: flex; justify-content: space-between; align-items: center; padding: 10px 12px; border: 1px solid var(--border-color, #e5e7eb); border-radius: 8px; cursor: pointer; }
.aaexam-batch.is-active { border-color: var(--primary-color, #2563eb); background: var(--primary-bg, #eff6ff); }
.aaexam-batch-name { font-weight: 500; }
.aaexam-head { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px; }
.aaexam-title { font-size: 16px; font-weight: 600; margin-bottom: 4px; }
.aaexam-actions { display: flex; gap: 8px; flex-wrap: wrap; }
.aaexam-stats { display: flex; gap: 16px; padding: 10px 12px; background: var(--fill-light, #f8fafc); border-radius: 8px; margin-bottom: 12px; font-size: 13px; }
.aaexam-stats .is-warn { color: var(--warning-color, #d97706); font-weight: 600; }
.aaexam-section-title { font-weight: 500; margin: 14px 0 8px; }
.aaexam-form { display: flex; flex-direction: column; gap: 12px; }
.aaexam-rooms, .aaexam-incidents { list-style: none; margin: 0 0 8px; padding: 0; display: flex; flex-direction: column; gap: 6px; }
.aaexam-incidents li { display: flex; justify-content: space-between; padding: 8px 12px; background: var(--fill-light, #f8fafc); border-radius: 6px; }
</style>
