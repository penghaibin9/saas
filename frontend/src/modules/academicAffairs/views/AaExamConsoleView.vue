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
              <AppButton v-if="current.status === 'DRAFT'" size="small" variant="ghost" @click="openAddCourse">+ 批量圈课</AppButton>
              <AppButton v-if="current.status === 'DRAFT'" size="small" variant="primary" @click="lc('confirmBatchCourses', '推进(课程确认完成)')">推进</AppButton>
              <AppButton v-if="['COURSE_CONFIRMED','PUBLISHED'].includes(current.status)" size="small" variant="ghost" @click="openPatrol">巡考安排</AppButton>
              <AppButton v-if="current.status === 'COURSE_CONFIRMED'" size="small" variant="ghost" :loading="autoArranging" @click="openAutoPlan">自动排考</AppButton>
              <AppButton
                v-if="current.status === 'COURSE_CONFIRMED'"
                size="small"
                variant="primary"
                :disabled="!readiness || !readiness.canPublish"
                @click="lc('publishBatch', '发布')"
              >发布</AppButton>
              <AppButton v-if="current.status === 'PUBLISHED'" size="small" variant="warning" @click="lc('finishBatch', '结束考试')">结束</AppButton>
              <AppButton v-if="current.status === 'FINISHED'" size="small" variant="ghost" @click="lc('archiveBatch', '归档')">归档</AppButton>
            </div>
          </div>

          <AppInlineAlert v-if="readinessError" type="danger" :description="'发布就绪检查失败：' + readinessError" />
          <div v-if="readiness" class="aaexam-readiness" aria-label="考务发布就绪摘要">
            <div class="aaexam-readiness__item">
              <span>应考课程</span>
              <strong>{{ readiness.eligibleCourseCount }}</strong>
              <small>已圈 {{ readiness.circledCourseCount }} · 待圈 {{ readiness.pendingCandidateCount }}</small>
            </div>
            <div class="aaexam-readiness__item">
              <span>已排</span>
              <strong>{{ readiness.arrangedCourseCount }}</strong>
              <small>已确认 {{ readiness.confirmedCourseCount }}</small>
            </div>
            <div class="aaexam-readiness__item" :class="{ 'is-risk': readiness.missedCourseCount }">
              <span>漏排</span>
              <strong>{{ readiness.missedCourseCount }}</strong>
              <small>只需继续处理异常课程</small>
            </div>
            <div class="aaexam-readiness__item" :class="{ 'is-risk': readiness.invigilatorGapCount }">
              <span>监考缺口</span>
              <strong>{{ readiness.invigilatorGapCount }}</strong>
              <small>缺口考场数</small>
            </div>
            <div class="aaexam-readiness__item" :class="{ 'is-risk': readiness.roomShortageCount }">
              <span>教室不足</span>
              <strong>{{ readiness.roomShortageCount }}</strong>
              <small>容量不足或尚无考场</small>
            </div>
            <div class="aaexam-readiness__item is-conclusion" :class="readiness.canPublish ? 'is-ready' : 'is-risk'">
              <span>发布结论</span>
              <strong>{{ readiness.canPublish ? '可以发布' : '暂不可发布' }}</strong>
              <small>{{ readiness.canPublish ? '正式发布门禁已满足' : '先处理下方阻断项' }}</small>
            </div>
          </div>

          <AppInlineAlert
            v-if="readiness && !readiness.canPublish && readiness.blockingReasons && readiness.blockingReasons.length"
            type="warning"
            :description="'发布前还需处理：' + readiness.blockingReasons.join('；')"
          />

          <div v-if="stats" class="aaexam-stats">
            <span>已圈课程 {{ stats.courseCount }}</span>
            <span>已确认 {{ stats.confirmedCount }}</span>
            <span :class="{ 'is-warn': stats.absentCount }">缺考 {{ stats.absentCount }}</span>
            <span :class="{ 'is-warn': stats.violationCount }">违纪 {{ stats.violationCount }}</span>
          </div>

          <template v-if="autoResult && autoResult.batchId === String(current.batchId)">
            <AppInlineAlert
              v-if="autoResult.timePlan && autoResult.timePlan.misses && autoResult.timePlan.misses.length"
              type="warning"
              :description="'自动定时未放下 ' + autoResult.timePlan.misses.length + ' 门：' + autoResult.timePlan.misses.map(m => `${m.courseName}（${m.reasonLabel}）`).join('；')"
            />
            <AppInlineAlert
              v-if="autoResult.misses && autoResult.misses.length"
              type="warning"
              :description="'自动排考漏排 ' + autoResult.misses.length + ' 门：' + autoResult.misses.map(m => `${m.courseName}（${m.reasonLabel}——${m.detail}）`).join('；')"
            />
            <AppInlineAlert
              v-if="autoResult.invigilatorGaps && autoResult.invigilatorGaps.length"
              type="warning"
              :description="'监考缺口 ' + autoResult.invigilatorGaps.length + ' 处：' + autoResult.invigilatorGaps.map(g => `${g.courseName} 考场${g.roomSeq}（需 ${g.needed} 实配 ${g.assigned}）`).join('；') + '，请在考场编排中手工补指'"
            />
            <AppInlineAlert
              v-if="(!autoResult.misses || !autoResult.misses.length) && (!autoResult.invigilatorGaps || !autoResult.invigilatorGaps.length) && (!autoResult.timePlan || !autoResult.timePlan.misses || !autoResult.timePlan.misses.length)"
              type="success"
              :description="'自动排考完成：自动定时 ' + (autoResult.timePlan ? autoResult.timePlan.assigned : 0) + ' 门，编排 ' + autoResult.arrangedCourses + ' 门，无漏排、无监考缺口'"
            />
          </template>

          <div class="aaexam-section-title">考试课程</div>
          <EmptyState v-if="!courses.length" title="未圈定课程" description="从已终审教学任务批量圈定应考课程" />
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

    <AppDrawer :visible="createVisible" title="新建考试批次" mode="modal" size="small" @close="createVisible = false">
      <div class="aaexam-form">
        <AppFormItem label="学期" required><AppTermEntityPicker v-model="form.termId" placeholder="请选择正式学期" :disabled="saving" /></AppFormItem>
        <AppFormItem label="批次名称" required><AppTextInput v-model="form.batchName" placeholder="如 2024秋期末考试" :disabled="saving" /></AppFormItem>
        <AppInlineAlert v-if="formError" type="danger" :description="formError" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="saving" @click="createVisible = false">取消</AppButton>
        <AppButton variant="primary" :loading="saving" @click="submitCreate">创建</AppButton>
      </template>
    </AppDrawer>

    <AppDrawer :visible="courseVisible" title="批量圈定应考课程" mode="modal" size="large" @close="closeCourseDrawer">
      <div class="aaexam-form">
        <div class="aaexam-candidate-toolbar">
          <AppTextInput v-model="candidateKeyword" placeholder="搜索课程、教学班或教师" :disabled="candidateLoading || saving" />
          <AppButton size="small" variant="ghost" :loading="candidateLoading" @click="loadCourseCandidates">搜索</AppButton>
        </div>
        <AppInlineAlert
          type="info"
          :description="'系统只列出当前考试批次同学期、已终审且尚未圈定的教学任务；单次最多 100 门。已选 ' + selectedTaskIds.length + ' 门。'"
        />
        <LoadingState v-if="candidateLoading" />
        <EmptyState v-else-if="!courseCandidates.length" title="暂无可圈定课程" description="当前批次没有尚未圈定的已终审教学任务" />
        <div v-else class="aaexam-candidate-list">
          <AppCheckboxGroup v-model="selectedTaskIds" :options="candidateOptions" :max="100" block :disabled="saving" />
        </div>
        <div v-if="coursePreview" class="aaexam-preview">
          <div class="aaexam-preview__summary">
            <strong>预览结果：可圈 {{ coursePreview.ready }} 门</strong>
            <span v-if="coursePreview.blocked">· 阻断 {{ coursePreview.blocked }} 门</span>
          </div>
          <ul v-if="previewBlockedItems.length" class="aaexam-preview__blocked">
            <li v-for="item in previewBlockedItems" :key="item.teachingTaskId">
              {{ item.courseName || ('教学任务 ' + item.teachingTaskId) }}：{{ item.message }}
            </li>
          </ul>
          <AppInlineAlert
            v-if="coursePreview.previewToken"
            type="success"
            description="预览为零写入；确认时系统会重新校验名单与任务状态，再逐门进入正式圈课写链。"
          />
        </div>
        <AppInlineAlert v-if="courseError" type="danger" :description="courseError" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="saving" @click="closeCourseDrawer">取消</AppButton>
        <AppButton variant="ghost" :loading="saving" :disabled="!selectedTaskIds.length" @click="previewCourses">预览圈课</AppButton>
        <AppButton
          variant="primary"
          :loading="saving"
          :disabled="!coursePreview || !coursePreview.previewToken || !coursePreview.ready"
          @click="confirmCourses"
        >确认圈定 {{ coursePreview ? coursePreview.ready : 0 }} 门</AppButton>
      </template>
    </AppDrawer>

    <AppDrawer :visible="autoPlanVisible" title="自动排考 · 日期与场次" mode="modal" size="large" @close="closeAutoPlan">
      <div class="aaexam-form">
        <AppInlineAlert type="info" description="系统先用所选日期×场次自动安排考试时间，再增量切考场、铺座位、配监考；已定时间和已有考场不会被覆盖。" />

        <div class="aaexam-auto-block">
          <div class="aaexam-auto-head">
            <strong>考试日期</strong>
            <AppButton size="small" variant="ghost" :disabled="autoArranging" @click="addAutoDate">+ 添加日期</AppButton>
          </div>
          <div v-for="(date, index) in autoPlan.dates" :key="'date-' + index" class="aaexam-auto-row">
            <AppDatePicker v-model="autoPlan.dates[index]" :disabled="autoArranging" />
            <AppButton v-if="autoPlan.dates.length > 1" size="small" variant="ghost" :disabled="autoArranging" @click="removeAutoDate(index)">移除</AppButton>
          </div>
        </div>

        <div class="aaexam-auto-block">
          <div class="aaexam-auto-head">
            <strong>每日场次</strong>
            <AppButton size="small" variant="ghost" :disabled="autoArranging" @click="addAutoSession">+ 添加场次</AppButton>
          </div>
          <div v-for="(session, index) in autoPlan.sessions" :key="'session-' + index" class="aaexam-auto-row is-session">
            <AppTimePicker v-model="session.start" :disabled="autoArranging" />
            <span class="aaexam-auto-sep">至</span>
            <AppTimePicker v-model="session.end" :disabled="autoArranging" />
            <AppButton v-if="autoPlan.sessions.length > 1" size="small" variant="ghost" :disabled="autoArranging" @click="removeAutoSession(index)">移除</AppButton>
          </div>
        </div>

        <AppFormItem label="同班每日最多考试场次">
          <AppNumberInput v-model="autoPlan.maxPerDayPerClass" :min="1" :max="4" :disabled="autoArranging" />
        </AppFormItem>
        <AppInlineAlert v-if="autoPlanError" type="danger" :description="autoPlanError" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="autoArranging" @click="closeAutoPlan">取消</AppButton>
        <AppButton variant="primary" :loading="autoArranging" @click="runAutoArrange">开始自动排考</AppButton>
      </template>
    </AppDrawer>

    <AppDrawer :visible="schedVisible" title="设置考试时间" mode="modal" size="medium" @close="schedVisible = false">
      <div class="aaexam-form">
        <AppFormItem label="考试日期"><AppDatePicker v-model="sched.examDate" :disabled="saving" /></AppFormItem>
        <AppFormItem label="开始时间"><AppTimePicker v-model="sched.startTime" :disabled="saving" /></AppFormItem>
        <AppFormItem label="结束时间"><AppTimePicker v-model="sched.endTime" :disabled="saving" /></AppFormItem>
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="saving" @click="schedVisible = false">取消</AppButton>
        <AppButton variant="primary" :loading="saving" @click="submitSchedule">保存</AppButton>
      </template>
    </AppDrawer>

    <AppDrawer :visible="arrangeVisible" :title="'考场编排 · ' + (arrangeCourse ? arrangeCourse.courseName : '')" mode="modal" size="large" @close="arrangeVisible = false">
      <div class="aaexam-form">
        <div class="aaexam-section-title">已有考场</div>
        <EmptyState v-if="!arrangeRooms.length" title="暂无考场" description="添加考场后可指定监考" />
        <ul v-else class="aaexam-rooms">
          <li v-for="r in arrangeRooms" :key="r.examRoomId">
            <span>考场{{ r.roomSeq }} · {{ r.classroomText }}（{{ r.plannedCount }}/{{ r.capacity }}）</span>
            <button class="mp-link" @click="printSeating(r.examRoomId)">座位表/准考证/门贴</button>
          </li>
        </ul>
        <AppFormItem label="新增考场"><AppClassroomPicker v-model="roomForm.classroomId" :disabled="saving" @change="onExamRoomPicked" /></AppFormItem>
        <AppFormItem label="容量"><AppNumberInput v-model="roomForm.capacity" :min="1" :max="500" :disabled="saving" /></AppFormItem>
        <AppButton size="small" variant="ghost" :loading="saving" @click="submitRoom">添加考场</AppButton>
      </div>
    </AppDrawer>

    <AppDrawer :visible="patrolVisible" title="巡考安排" mode="modal" size="large" @close="patrolVisible = false">
      <div class="aaexam-form">
        <div class="aaexam-section-title">已排巡考</div>
        <EmptyState v-if="!patrols.length" title="暂无巡考" description="填写下方表单排巡考（同一人同时段/与监考冲突会拦截）" />
        <ul v-else class="aaexam-rooms">
          <li v-for="p in patrols" :key="p.patrolId">
            <span>{{ p.teacherName || p.teacherKey }} · {{ p.patrolDate || '—' }} {{ p.startTime || '' }}-{{ p.endTime || '' }} · {{ p.areaScope || '全场' }}</span>
          </li>
        </ul>
        <AppFormItem label="巡考教师" required><AppTeacherPicker v-model="patrolForm.teacherKey" :disabled="saving" @change="onPatrolTeacherPicked" /></AppFormItem>
        <AppFormItem label="巡考日期"><AppDatePicker v-model="patrolForm.patrolDate" :disabled="saving" /></AppFormItem>
        <AppFormItem label="开始时间"><AppTimePicker v-model="patrolForm.startTime" :disabled="saving" /></AppFormItem>
        <AppFormItem label="结束时间"><AppTimePicker v-model="patrolForm.endTime" :disabled="saving" /></AppFormItem>
        <AppFormItem label="巡考区域"><AppTextInput v-model="patrolForm.areaScope" placeholder="如 教学楼A/全场" :disabled="saving" /></AppFormItem>
        <AppInlineAlert v-if="patrolError" type="danger" :description="patrolError" />
        <AppButton size="small" variant="primary" :loading="saving" @click="submitPatrol">排巡考</AppButton>
      </div>
    </AppDrawer>

    <AppConfirmDialog v-model:visible="confirmVisible" :title="confirmTitle" :message="confirmMessage" @confirm="onConfirm" />
  </ModulePageShell>
</template>

<script>
/** 考务管理 · 教务处控制台：批次生命周期 + 批量圈课 + 两段式自动排考 + 发布就绪。 */
import { ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton, AppDrawer } from '@/components/ui'
import { AppTextInput, AppNumberInput, AppFormItem, AppConfirmDialog, AppInlineAlert, AppCheckboxGroup, AppTermEntityPicker, AppClassroomPicker, AppTeacherPicker, AppDatePicker, AppTimePicker } from '@/components/common'
import { academicAffairsApi, academicAffairsExamApi as api } from '@/modules/academicAffairs/api/academic-affairs.api'
import { academicAffairsExamConvenienceApi as convenienceApi } from '@/modules/academicAffairs/api/exam-convenience.api'
import { toast } from '@/utils/toast'

const _L = { DRAFT: '草稿', COURSE_CONFIRMED: '课程已确认', ARRANGED: '已编排', PUBLISHED: '已发布', FINISHED: '已结束', ARCHIVED: '已归档' }

export default {
  name: 'AaExamConsoleView',
  components: {
    ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState,
    AppButton, AppDrawer, AppTextInput, AppNumberInput, AppFormItem, AppConfirmDialog, AppInlineAlert,
    AppCheckboxGroup, AppTermEntityPicker, AppClassroomPicker, AppTeacherPicker, AppDatePicker, AppTimePicker
  },
  data() {
    return {
      ctx: { currentRole: { roleName: '' }, dataScope: { scopeName: '' } },
      loading: true, error: '', rows: [], pagination: { page: 1, pageSize: 50, total: 0 },
      current: null, courses: [], stats: null, incidents: [], readiness: null, readinessError: '',
      createVisible: false, form: { batchName: '', termId: '' }, formError: '',
      courseVisible: false, candidateLoading: false, candidateKeyword: '', courseCandidates: [], selectedTaskIds: [], coursePreview: null, courseError: '',
      autoPlanVisible: false, autoPlanError: '', autoPlan: { dates: [''], sessions: [{ start: '', end: '' }], maxPerDayPerClass: 1 },
      schedVisible: false, schedCourse: null, sched: { examDate: '', startTime: '', endTime: '' },
      arrangeVisible: false, arrangeCourse: null, arrangeRooms: [], roomForm: { classroomId: '', classroomText: '', capacity: 50 },
      patrolVisible: false, patrols: [], patrolForm: { teacherKey: '', teacherName: '', patrolDate: '', startTime: '', endTime: '', areaScope: '' }, patrolError: '',
      saving: false, confirmVisible: false, confirmTitle: '', confirmMessage: '', pendingAction: null,
      autoArranging: false, autoResult: null,
      courseColumns: [
        { key: 'course', title: '课程/班级' }, { key: 'schedule', title: '考试时间' },
        { key: 'status', title: '状态' }, { key: 'ops', title: '操作' }
      ]
    }
  },
  computed: {
    candidateOptions() {
      return this.courseCandidates.map((row) => ({
        value: String(row.teachingTaskId),
        label: `${row.courseName || '未命名课程'} · ${row.teachingClassName || '未分教学班'} · ${row.teacherName || '未派课'}`
      }))
    },
    previewBlockedItems() {
      return (this.coursePreview?.items || []).filter((item) => item.status !== 'READY')
    }
  },
  async created() {
    const c = await academicAffairsApi.getContext()
    if (c.code === 0) this.ctx = c.data
    this.load()
  },
  methods: {
    onExamRoomPicked(value, items) {
      this.roomForm.classroomId = value || ''
      this.roomForm.classroomText = items?.[0]?.label || ''
      const capacity = items?.[0]?.raw?.capacity
      if (capacity) this.roomForm.capacity = capacity
    },
    onPatrolTeacherPicked(value, items) {
      this.patrolForm.teacherKey = value || ''
      this.patrolForm.teacherName = items?.[0]?.raw?.teacherName || items?.[0]?.label || ''
    },
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
    async select(b) { this.current = b; this.autoResult = null; await this.refresh() },
    async refresh() {
      if (!this.current) return
      const [cs, st, inc, ready] = await Promise.all([
        api.listCourses(this.current.batchId, { pageSize: 200 }),
        api.batchStats(this.current.batchId),
        api.listIncidents({ batchId: this.current.batchId, pageSize: 100 }),
        convenienceApi.getReadiness(this.current.batchId)
      ])
      this.courses = cs.code === 0 ? cs.data.list : []
      this.stats = st.code === 0 ? st.data : null
      this.incidents = inc.code === 0 ? inc.data.list : []
      this.readiness = ready.code === 0 ? ready.data : null
      this.readinessError = ready.code === 0 ? '' : ready.message
    },
    openCreate() { this.form = { batchName: '', termId: '' }; this.formError = ''; this.createVisible = true },
    async submitCreate() {
      if (!this.form.termId) { this.formError = '请选择正式学期'; return }
      if (!this.form.batchName) { this.formError = '批次名称必填'; return }
      this.saving = true
      const res = await api.createBatch({ batchName: this.form.batchName, termId: this.form.termId })
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
    async openAddCourse() {
      this.courseVisible = true
      this.candidateKeyword = ''
      this.courseCandidates = []
      this.selectedTaskIds = []
      this.coursePreview = null
      this.courseError = ''
      await this.loadCourseCandidates()
    },
    closeCourseDrawer() {
      if (this.saving) return
      this.courseVisible = false
      this.coursePreview = null
      this.courseError = ''
    },
    async loadCourseCandidates() {
      if (!this.current) return
      this.candidateLoading = true
      this.courseError = ''
      const res = await convenienceApi.listCourseCandidates(this.current.batchId, {
        keyword: this.candidateKeyword || undefined,
        page: 1,
        pageSize: 100
      })
      this.candidateLoading = false
      if (res.code === 0) {
        this.courseCandidates = res.data.list || []
        this.selectedTaskIds = []
        this.coursePreview = null
      } else {
        this.courseCandidates = []
        this.courseError = res.message
      }
    },
    async previewCourses() {
      if (!this.selectedTaskIds.length) { this.courseError = '请至少选择 1 门应考课程'; return }
      this.saving = true; this.courseError = ''
      const res = await convenienceApi.previewCourses(this.current.batchId, this.selectedTaskIds)
      this.saving = false
      if (res.code === 0) this.coursePreview = res.data
      else { this.coursePreview = null; this.courseError = res.message }
    },
    async confirmCourses() {
      const previewToken = this.coursePreview?.previewToken
      if (!previewToken) { this.courseError = '预览已失效，请重新预览'; return }
      this.saving = true; this.courseError = ''
      const res = await convenienceApi.confirmCourses(this.current.batchId, previewToken)
      this.saving = false
      if (res.code !== 0) { this.courseError = res.message; return }
      const { succeeded = 0, failed = 0, items = [] } = res.data || {}
      await this.refresh()
      if (failed) {
        const message = `已圈定 ${succeeded} 门，另有 ${failed} 门状态已变化：${items.filter(item => !item.ok).map(item => item.message).join('；')}`
        await this.loadCourseCandidates()
        this.courseError = message
        return
      }
      toast.success(`已批量圈定 ${succeeded} 门课程`)
      this.courseVisible = false
      this.coursePreview = null
    },
    openAutoPlan() {
      this.autoPlan = { dates: [''], sessions: [{ start: '', end: '' }], maxPerDayPerClass: 1 }
      this.autoPlanError = ''
      this.autoPlanVisible = true
    },
    closeAutoPlan() {
      if (this.autoArranging) return
      this.autoPlanVisible = false
      this.autoPlanError = ''
    },
    addAutoDate() { this.autoPlan.dates.push('') },
    removeAutoDate(index) { if (this.autoPlan.dates.length > 1) this.autoPlan.dates.splice(index, 1) },
    addAutoSession() { this.autoPlan.sessions.push({ start: '', end: '' }) },
    removeAutoSession(index) { if (this.autoPlan.sessions.length > 1) this.autoPlan.sessions.splice(index, 1) },
    async runAutoArrange() {
      if (!this.current) return
      const dates = [...new Set(this.autoPlan.dates.map((value) => String(value || '').trim()).filter(Boolean))]
      const sessions = []
      const seenSessions = new Set()
      for (const row of this.autoPlan.sessions) {
        const start = String(row.start || '').trim()
        const end = String(row.end || '').trim()
        if (!start && !end) continue
        if (!start || !end) { this.autoPlanError = '每个考试场次都必须同时填写开始与结束时间'; return }
        if (start >= end) { this.autoPlanError = `场次 ${start}-${end} 的结束时间必须晚于开始时间`; return }
        const key = `${start}-${end}`
        if (!seenSessions.has(key)) {
          seenSessions.add(key)
          sessions.push({ start, end })
        }
      }
      if (!dates.length) { this.autoPlanError = '请至少选择 1 个考试日期'; return }
      if (!sessions.length) { this.autoPlanError = '请至少配置 1 个每日考试场次'; return }

      this.autoPlanError = ''
      this.autoArranging = true
      const timeRes = await convenienceApi.autoTimes(this.current.batchId, {
        dates,
        sessions,
        maxPerDayPerClass: Number(this.autoPlan.maxPerDayPerClass || 1)
      })
      if (timeRes.code !== 0) {
        this.autoArranging = false
        this.autoPlanError = timeRes.message
        return
      }

      const arrangeRes = await api.autoArrange(this.current.batchId)
      this.autoArranging = false
      if (arrangeRes.code !== 0) {
        this.autoPlanError = arrangeRes.message
        await this.refresh()
        return
      }

      this.autoResult = { ...arrangeRes.data, timePlan: timeRes.data }
      this.autoPlanVisible = false
      toast.success(`自动定时 ${timeRes.data.assigned} 门，编排 ${arrangeRes.data.arrangedCourses} 门，漏排 ${arrangeRes.data.missedCourses} 门`)
      await this.refresh()
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
      this.arrangeCourse = row; this.roomForm = { classroomId: '', classroomText: '', capacity: 50 }; this.arrangeVisible = true
      const res = await api.listRooms(row.examCourseId)
      this.arrangeRooms = res.code === 0 ? (res.data.items || []) : []
    },
    async submitRoom() {
      if (!this.roomForm.classroomText) { toast.error('考场名必填'); return }
      this.saving = true
      const res = await api.addRoom(this.arrangeCourse.examCourseId, this.roomForm)
      this.saving = false
      if (res.code === 0) { toast.success('已添加考场'); const r = await api.listRooms(this.arrangeCourse.examCourseId); this.arrangeRooms = r.code === 0 ? r.data.items : []; await this.refresh() }
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
        await this.refresh()
      } else this.patrolError = res.message
    },
    onConfirm() { const a = this.pendingAction; this.pendingAction = null; if (a) a() }
  }
}
</script>

<style scoped>
.aaexam-layout { display: grid; grid-template-columns: 300px minmax(0, 1fr); gap: 16px; }
.aaexam-detail { min-width: 0; }
.aaexam-batches { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 6px; }
.aaexam-batch { display: flex; justify-content: space-between; align-items: center; gap: 8px; padding: 10px 12px; border: 1px solid var(--border-color, #e5e7eb); border-radius: 8px; cursor: pointer; }
.aaexam-batch.is-active { border-color: var(--primary-color, #2563eb); background: var(--primary-bg, #eff6ff); }
.aaexam-batch-name { min-width: 0; font-weight: 500; overflow-wrap: anywhere; }
.aaexam-head { display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; margin-bottom: 12px; }
.aaexam-title { font-size: 16px; font-weight: 600; margin-bottom: 4px; }
.aaexam-actions { display: flex; justify-content: flex-end; gap: 8px; flex-wrap: wrap; }
.aaexam-readiness { display: grid; grid-template-columns: repeat(6, minmax(110px, 1fr)); gap: 10px; margin-bottom: 12px; }
.aaexam-readiness__item { min-width: 0; padding: 12px; border: 1px solid var(--border-color, #e5e7eb); border-radius: 10px; background: var(--fill-light, #f8fafc); display: flex; flex-direction: column; gap: 3px; }
.aaexam-readiness__item span { font-size: 12px; color: var(--text-secondary, #64748b); }
.aaexam-readiness__item strong { font-size: 20px; line-height: 1.2; }
.aaexam-readiness__item small { color: var(--text-secondary, #64748b); overflow-wrap: anywhere; }
.aaexam-readiness__item.is-risk { border-color: var(--warning-color, #d97706); background: #fffbeb; }
.aaexam-readiness__item.is-ready { border-color: var(--success-color, #16a34a); background: #f0fdf4; }
.aaexam-readiness__item.is-conclusion strong { font-size: 16px; }
.aaexam-stats { display: flex; gap: 16px; flex-wrap: wrap; padding: 10px 12px; background: var(--fill-light, #f8fafc); border-radius: 8px; margin: 12px 0; font-size: 13px; }
.aaexam-stats .is-warn { color: var(--warning-color, #d97706); font-weight: 600; }
.aaexam-section-title { font-weight: 500; margin: 14px 0 8px; }
.aaexam-form { display: flex; flex-direction: column; gap: 12px; }
.aaexam-candidate-toolbar { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 8px; align-items: center; }
.aaexam-candidate-list { max-height: 420px; overflow: auto; padding: 10px 12px; border: 1px solid var(--border-color, #e5e7eb); border-radius: 8px; }
.aaexam-preview { display: flex; flex-direction: column; gap: 8px; padding: 10px 12px; border-radius: 8px; background: var(--fill-light, #f8fafc); }
.aaexam-preview__summary { display: flex; gap: 6px; flex-wrap: wrap; }
.aaexam-preview__blocked { margin: 0; padding-left: 20px; color: var(--warning-color, #d97706); }
.aaexam-auto-block { display: flex; flex-direction: column; gap: 8px; padding: 10px 12px; border: 1px solid var(--border-color, #e5e7eb); border-radius: 8px; }
.aaexam-auto-head { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
.aaexam-auto-row { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 8px; align-items: center; }
.aaexam-auto-row.is-session { grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr) auto; }
.aaexam-auto-sep { color: var(--text-secondary, #64748b); }
.aaexam-rooms, .aaexam-incidents { list-style: none; margin: 0 0 8px; padding: 0; display: flex; flex-direction: column; gap: 6px; }
.aaexam-rooms li, .aaexam-incidents li { display: flex; justify-content: space-between; gap: 12px; padding: 8px 12px; background: var(--fill-light, #f8fafc); border-radius: 6px; }

@media (max-width: 1080px) {
  .aaexam-layout { grid-template-columns: 240px minmax(0, 1fr); }
  .aaexam-readiness { grid-template-columns: repeat(3, minmax(120px, 1fr)); }
}

@media (max-width: 760px) {
  .aaexam-layout { grid-template-columns: 1fr; }
  .aaexam-list { max-height: 220px; overflow: auto; }
  .aaexam-head { flex-direction: column; }
  .aaexam-actions { justify-content: flex-start; width: 100%; }
  .aaexam-readiness { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .aaexam-candidate-toolbar, .aaexam-auto-row, .aaexam-auto-row.is-session { grid-template-columns: 1fr; }
  .aaexam-auto-sep { display: none; }
  .aaexam-rooms li, .aaexam-incidents li { flex-direction: column; }
}
</style>
