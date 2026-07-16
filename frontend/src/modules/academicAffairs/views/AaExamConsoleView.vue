<template>
  <ModulePageShell
    title="考务管理 · 教务处控制台"
    :subtitle="'批次：草稿→圈课→学院确认→编排→发布→结束→归档 · 共 ' + pagination.total + ' 个批次'"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton v-if="tab === 'console'" variant="primary" @click="openCreate">新建考试批次</AppButton>
    </template>

    <div class="aaexam-tabs">
      <button v-for="t in tabs" :key="t.key" :class="['aaexam-tab', { 'is-active': tab === t.key }]" @click="switchTab(t.key)">{{ t.label }}</button>
    </div>

    <div v-if="tab === 'console'" class="aaexam-layout">
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
              <AppButton v-if="['COURSE_CONFIRMED','PUBLISHED'].includes(current.status)" size="small" variant="ghost" @click="openPatrol">巡考安排</AppButton>
              <AppButton v-if="current.status === 'COURSE_CONFIRMED'" size="small" variant="primary" @click="lc('publishBatch', '发布')">发布</AppButton>
              <AppButton v-if="current.status === 'PUBLISHED'" size="small" variant="warning" @click="lc('finishBatch', '结束考试')">结束</AppButton>
              <AppButton v-if="current.status === 'FINISHED'" size="small" variant="ghost" @click="lc('archiveBatch', '归档')">归档</AppButton>
            </div>
          </div>

          <div v-if="current.status === 'ARCHIVED'" class="aaexam-archived-hint">已归档：仅可查看，全部写操作已关闭</div>

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
              <template v-if="current.status !== 'ARCHIVED'">
                <button v-if="row.status === 'PENDING_CONFIRM'" class="mp-link" @click="confirm(row, 'CONFIRM')">确认</button>
                <button class="mp-link" @click="openSchedule(row)">设时间</button>
                <button class="mp-link" @click="openArrange(row)">考场</button>
              </template>
              <span v-else class="mp-cell-sub">只读</span>
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

    <!-- 缓考审批（P4：辅导员→任课教师→学院→教务处四级审批） -->
    <div v-else-if="tab === 'defer'" class="mp-stack">
      <div class="aaexam-bar">
        <AppSelect v-model="deferStatus" :options="deferStatusOptions" placeholder="全部状态" @change="loadDefer" />
      </div>
      <ErrorState v-if="deferError" :description="deferError" @retry="loadDefer" />
      <LoadingState v-else-if="deferLoading" />
      <EmptyState v-else-if="!deferRows.length" title="暂无缓考申请" description="学生小程序提交后在此审批" />
      <DataTable v-else :columns="deferColumns" :rows="deferRows" row-key="deferId">
        <template #cell-student="{ row }">
          <div class="mp-cell-main">{{ row.studentName }}</div>
          <div class="mp-cell-sub">{{ row.courseName }}</div>
        </template>
        <template #cell-reason="{ row }">{{ deferReasonLabel(row.reasonType) }}：{{ row.reason || '—' }}</template>
        <template #cell-status="{ row }"><StatusTag :type="deferStatusType(row.status)" :label="deferStatusLabel(row.status)" dot /></template>
        <template #cell-ops="{ row }">
          <template v-if="deferReviewable(row.status)">
            <button class="mp-link" @click="deferAct(row, 'APPROVE')">通过</button>
            <button class="mp-link" @click="deferAct(row, 'RETURN')">退回</button>
            <button class="mp-link is-danger" @click="deferAct(row, 'REJECT')">驳回</button>
          </template>
          <span v-else class="mp-cell-sub">{{ row.status === 'RETURNED' ? '待学生补材料重提' : '已终态' }}</span>
        </template>
      </DataTable>
    </div>

    <!-- 考务归档（12号卡：只读列表，点击进入控制台只读详情） -->
    <div v-else class="mp-stack">
      <ErrorState v-if="archiveError" :description="archiveError" @retry="loadArchive" />
      <LoadingState v-else-if="archiveLoading" />
      <EmptyState v-else-if="!archiveRows.length" title="暂无已归档批次" description="批次结束考试后可在考务控制台执行归档" />
      <DataTable v-else :columns="archiveColumns" :rows="archiveRows" row-key="batchId">
        <template #cell-batch="{ row }">{{ row.batchName }}</template>
        <template #cell-archivedAt="{ row }">{{ (row.archivedAt || '').replace('T', ' ').slice(0, 19) || '—' }}</template>
        <template #cell-summary="{ row }">
          课程{{ row.completenessSummary.courseCount }} · 缺考{{ row.completenessSummary.absentCount }} · 违纪{{ row.completenessSummary.violationCount }}
        </template>
        <template #cell-ops="{ row }"><button class="mp-link" @click="viewArchived(row)">查看只读详情</button></template>
      </DataTable>
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
            <button class="mp-link" @click="printSeating(r.examRoomId)">座位表/准考证/门贴</button>
          </li>
        </ul>
        <AppFormItem label="新增考场"><AppTextInput v-model="roomForm.classroomText" placeholder="考场名 如 A101" :disabled="saving" /></AppFormItem>
        <AppFormItem label="容量"><AppNumberInput v-model="roomForm.capacity" :min="1" :max="500" :disabled="saving" /></AppFormItem>
        <AppButton size="small" variant="ghost" :loading="saving" @click="submitRoom">添加考场</AppButton>
      </div>
    </AppDrawer>

    <AppDrawer :visible="patrolVisible" title="巡考安排" @close="patrolVisible = false">
      <div class="aaexam-form">
        <div class="aaexam-section-title">已排巡考</div>
        <EmptyState v-if="!patrols.length" title="暂无巡考" description="填写下方表单排巡考（同一人同时段/与监考冲突会拦截）" />
        <ul v-else class="aaexam-rooms">
          <li v-for="p in patrols" :key="p.patrolId">
            <span>{{ p.teacherName || p.teacherKey }} · {{ p.patrolDate || '—' }} {{ p.startTime || '' }}-{{ p.endTime || '' }} · {{ p.areaScope || '全场' }}</span>
          </li>
        </ul>
        <AppFormItem label="巡考教师工号" required><AppTextInput v-model="patrolForm.teacherKey" placeholder="教师 key/工号" :disabled="saving" /></AppFormItem>
        <AppFormItem label="教师姓名"><AppTextInput v-model="patrolForm.teacherName" :disabled="saving" /></AppFormItem>
        <AppFormItem label="巡考日期"><AppTextInput v-model="patrolForm.patrolDate" placeholder="YYYY-MM-DD" :disabled="saving" /></AppFormItem>
        <AppFormItem label="开始时间"><AppTextInput v-model="patrolForm.startTime" placeholder="HH:MM" :disabled="saving" /></AppFormItem>
        <AppFormItem label="结束时间"><AppTextInput v-model="patrolForm.endTime" placeholder="HH:MM" :disabled="saving" /></AppFormItem>
        <AppFormItem label="巡考区域"><AppTextInput v-model="patrolForm.areaScope" placeholder="如 教学楼A/全场" :disabled="saving" /></AppFormItem>
        <AppInlineAlert v-if="patrolError" type="danger" :description="patrolError" />
        <AppButton size="small" variant="primary" :loading="saving" @click="submitPatrol">排巡考</AppButton>
      </div>
    </AppDrawer>

    <AppConfirmDialog v-model:visible="confirmVisible" :title="confirmTitle" :message="confirmMessage" @confirm="onConfirm" />
    <AppConfirmDialog
      v-model:visible="reasonDialog.visible" :title="reasonDialog.title" type="danger"
      require-reason :phrase-scene-key="reasonDialog.sceneKey" reason-label="原因（≥5字）"
      :submitting="reasonDialog.submitting" @confirm="onReasonConfirm"
    />
  </ModulePageShell>
</template>

<script>
/** 考务管理 · 教务处控制台（/admin/academic-affairs/exam）：批次生命周期+考试课程+考场编排+异常+统计。 */
import { ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton, AppDrawer } from '@/components/ui'
import { AppTextInput, AppNumberInput, AppSelect, AppFormItem, AppConfirmDialog, AppInlineAlert } from '@/components/common'
import { academicAffairsApi, academicAffairsExamApi as api } from '@/modules/academicAffairs/api/academic-affairs.api'
import { toast } from '@/utils/toast'

const _L = { DRAFT: '草稿', COURSE_CONFIRMED: '课程已确认', ARRANGED: '已编排', PUBLISHED: '已发布', FINISHED: '已结束', ARCHIVED: '已归档' }
const _DL = { COUNSELOR_REVIEW: '辅导员审批', TEACHER_CONFIRM: '任课教师确认', COLLEGE_REVIEW: '学院审批',
  ACADEMIC_FINAL: '教务处终审', APPROVED: '已批准', RETURNED: '已退回补材料', REJECTED: '已驳回' }
const _DR = { SICK: '病假', EMERGENCY: '突发事件', OTHER: '其他' }
const _REVIEWABLE = ['COUNSELOR_REVIEW', 'TEACHER_CONFIRM', 'COLLEGE_REVIEW', 'ACADEMIC_FINAL']

export default {
  name: 'AaExamConsoleView',
  components: {
    ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState,
    AppButton, AppDrawer, AppTextInput, AppNumberInput, AppSelect, AppFormItem, AppConfirmDialog, AppInlineAlert
  },
  data() {
    return {
      ctx: { currentRole: { roleName: '' }, dataScope: { scopeName: '' } },
      tab: 'console',
      tabs: [
        { key: 'console', label: '考务控制台' },
        { key: 'defer', label: '缓考审批' },
        { key: 'archive', label: '考务归档' }
      ],
      loading: true, error: '', rows: [], pagination: { page: 1, pageSize: 50, total: 0 },
      current: null, courses: [], stats: null, incidents: [],
      createVisible: false, form: { batchName: '' }, formError: '',
      courseVisible: false, courseTaskId: '', courseError: '',
      schedVisible: false, schedCourse: null, sched: { examDate: '', startTime: '', endTime: '' },
      arrangeVisible: false, arrangeCourse: null, arrangeRooms: [], roomForm: { classroomText: '', capacity: 50 },
      patrolVisible: false, patrols: [], patrolForm: { teacherKey: '', teacherName: '', patrolDate: '', startTime: '', endTime: '', areaScope: '' }, patrolError: '',
      saving: false, confirmVisible: false, confirmTitle: '', confirmMessage: '', pendingAction: null,
      reasonDialog: { visible: false, title: '', sceneKey: '', submitting: false, action: null },
      courseColumns: [
        { key: 'course', title: '课程/班级' }, { key: 'schedule', title: '考试时间' },
        { key: 'status', title: '状态' }, { key: 'ops', title: '操作' }
      ],
      // 缓考审批
      deferStatus: '', deferLoading: true, deferError: '', deferRows: [],
      deferStatusOptions: [
        { label: '全部状态', value: '' }, { label: '辅导员审批', value: 'COUNSELOR_REVIEW' },
        { label: '任课教师确认', value: 'TEACHER_CONFIRM' }, { label: '学院审批', value: 'COLLEGE_REVIEW' },
        { label: '教务处终审', value: 'ACADEMIC_FINAL' }, { label: '已批准', value: 'APPROVED' },
        { label: '已退回', value: 'RETURNED' }, { label: '已驳回', value: 'REJECTED' }
      ],
      deferColumns: [
        { key: 'student', title: '学生/课程' }, { key: 'reason', title: '缓考原因' },
        { key: 'status', title: '当前节点' }, { key: 'ops', title: '操作' }
      ],
      // 考务归档
      archiveLoading: true, archiveError: '', archiveRows: [],
      archiveColumns: [
        { key: 'batch', title: '批次' }, { key: 'archivedAt', title: '归档时间' },
        { key: 'summary', title: '完整性摘要' }, { key: 'ops', title: '操作' }
      ]
    }
  },
  async created() {
    const c = await academicAffairsApi.getContext()
    if (c.code === 0) this.ctx = c.data
    const q = this.$route && this.$route.query && this.$route.query.tab
    if (q && this.tabs.some((t) => t.key === q)) this.tab = q
    if (this.tab === 'defer') this.loadDefer()
    else if (this.tab === 'archive') this.loadArchive()
    else this.load()
  },
  methods: {
    statusLabel(s) { return _L[s] || s },
    statusType(s) {
      if (s === 'PUBLISHED') return 'success'
      if (s === 'FINISHED') return 'warning'
      if (s === 'ARCHIVED') return 'default'
      return 'primary'
    },
    switchTab(k) {
      this.tab = k
      if (k === 'defer' && !this.deferRows.length) this.loadDefer()
      else if (k === 'archive' && !this.archiveRows.length) this.loadArchive()
      else if (k === 'console' && !this.rows.length) this.load()
    },
    deferStatusLabel(s) { return _DL[s] || s },
    deferReasonLabel(t) { return _DR[t] || t || '—' },
    deferStatusType(s) {
      if (s === 'APPROVED') return 'success'
      if (s === 'REJECTED') return 'danger'
      if (s === 'RETURNED') return 'warning'
      return 'primary'
    },
    deferReviewable(s) { return _REVIEWABLE.includes(s) },
    async loadDefer() {
      this.deferLoading = true; this.deferError = ''
      const params = { pageSize: 100 }
      if (this.deferStatus) params.status = this.deferStatus
      const res = await api.deferList(params)
      if (res.code === 0) this.deferRows = res.data.list
      else this.deferError = res.message
      this.deferLoading = false
    },
    async deferAct(row, action) {
      const submit = async (reason) => {
        const fn = row.status === 'COUNSELOR_REVIEW' ? 'deferCounselorReview' : 'deferReview'
        const res = await api[fn](row.deferId, action, reason)
        if (res.code !== 0) { toast.error(res.message); return false }
        toast.success(action === 'APPROVE' ? '已通过' : action === 'RETURN' ? '已退回' : '已驳回')
        await this.loadDefer()
        return true
      }
      if (action === 'APPROVE') { await submit(''); return }
      // 缓考驳回/退回补材料：走真实对话框（原生 prompt 无法多行、样式不可控、放不下快捷用语）
      this.reasonDialog = {
        visible: true,
        title: action === 'RETURN' ? '退回补材料' : '驳回缓考申请',
        sceneKey: action === 'RETURN' ? 'aa.makeup.supplement' : 'aa.makeup.reject',
        submitting: false,
        action: submit
      }
    },
    /** 失败时保留弹窗与已填内容，仅成功才关闭 */
    async onReasonConfirm({ reason }) {
      const action = this.reasonDialog.action
      if (!action) return
      this.reasonDialog.submitting = true
      const ok = await action(reason)
      this.reasonDialog.submitting = false
      if (ok) this.reasonDialog.visible = false
    },
    async loadArchive() {
      this.archiveLoading = true; this.archiveError = ''
      const res = await api.listArchived({ pageSize: 100 })
      if (res.code === 0) this.archiveRows = res.data.list
      else this.archiveError = res.message
      this.archiveLoading = false
    },
    async viewArchived(row) {
      this.tab = 'console'
      if (!this.rows.some((b) => b.batchId === row.batchId)) await this.load()
      await this.select(row)
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
    printSeating(roomId) {
      const url = this.$router.resolve({ path: '/admin/academic-affairs/exam/print/seating', query: { roomId } }).href
      window.open(url, '_blank')
    },
    async openPatrol() {
      this.patrolForm = { teacherKey: '', teacherName: '', patrolDate: '', startTime: '', endTime: '', areaScope: '' }
      this.patrolError = ''; this.patrolVisible = true
      const res = await api.listPatrols(this.current.batchId)
      this.patrols = res.code === 0 ? (res.data.items || []) : []
    },
    async submitPatrol() {
      if (!this.patrolForm.teacherKey) { this.patrolError = '巡考教师工号必填'; return }
      this.saving = true
      const res = await api.addPatrol(this.current.batchId, this.patrolForm)
      this.saving = false
      if (res.code === 0) {
        toast.success('已排巡考')
        this.patrolForm = { teacherKey: '', teacherName: '', patrolDate: '', startTime: '', endTime: '', areaScope: '' }
        const r = await api.listPatrols(this.current.batchId)
        this.patrols = r.code === 0 ? (r.data.items || []) : []
      } else this.patrolError = res.message
    },
    onConfirm() { const a = this.pendingAction; this.pendingAction = null; if (a) a() }
  }
}
</script>

<style scoped>
.aaexam-tabs { display: flex; gap: 4px; border-bottom: 1px solid var(--border-color, #e5e7eb); margin-bottom: 16px; }
.aaexam-tab { padding: 8px 16px; border: none; background: none; cursor: pointer; font-size: 14px; color: var(--text-secondary, #64748b); border-bottom: 2px solid transparent; }
.aaexam-tab.is-active { color: var(--primary-color, #2563eb); border-bottom-color: var(--primary-color, #2563eb); font-weight: 600; }
.aaexam-bar { margin-bottom: 8px; max-width: 220px; }
.aaexam-archived-hint { padding: 8px 12px; background: var(--warning-bg, #fffbeb); color: var(--warning-color, #d97706); border-radius: 6px; font-size: 13px; margin-bottom: 12px; }
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
