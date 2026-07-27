<template>
  <ModulePageShell
    title="成绩录入"
    subtitle="建录入任务 → 选择固定三段或动态成绩项 → 按正式名单录入 → 提交学院审核"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton @click="$router.push('/admin/academic-affairs/grade-overview')">成绩总览</AppButton>
      <AppButton @click="loadTasks">我的录入任务</AppButton>
    </template>

    <div class="mp-stack">
      <AppSectionCard v-if="!task" title="新建成绩录入任务">
        <AppInlineAlert
          v-if="isAdminRole && !form.teachingTaskId"
          type="warning"
          title="管理员特殊补录"
          description="必须选择正式学期和课程库具体版本并填写原因；课程名、学分和课程版本均由课程库带出。"
        />
        <div class="aa-grid2">
          <label class="aa-field">
            <span :class="{ req: !isAdminRole }">教学任务</span>
            <AppTeachingTaskPicker v-model="form.teachingTaskId" clearable @change="onTeachingTaskChange" placeholder="普通教师必选；管理员可留空做特殊补录" />
          </label>
          <label v-if="isAdminRole && !form.teachingTaskId" class="aa-field">
            <span class="req">课程具体版本</span>
            <AppCoursePicker v-model="form.courseId" @change="onCourseChange" placeholder="按课程代码/名称选择" />
          </label>
          <label class="aa-field"><span>课程</span><input :value="form.courseName" type="text" class="aa-input" disabled placeholder="由教学任务或课程版本带出" /></label>
          <label v-if="isAdminRole && !form.teachingTaskId" class="aa-field">
            <span class="req">正式学期</span>
            <AppTermEntityPicker v-model="form.termId" placeholder="选择正式学期" />
          </label>
          <label v-else class="aa-field"><span>学期</span><input :value="form.termCode" type="text" class="aa-input" disabled placeholder="由教学任务所属批次带出" /></label>
          <label class="aa-field"><span>学分</span><input v-model.number="form.credit" type="number" min="0" step="0.5" class="aa-input" disabled /></label>
          <label class="aa-field"><span>班级</span><AppClassPicker v-model="form.classId" placeholder="由教学任务带出；特殊补录可选" :disabled="!!form.teachingTaskId" /></label>
          <label class="aa-field"><span>平时占比%</span><input v-model.number="form.usualRatio" type="number" min="0" max="100" class="aa-input" /></label>
          <label class="aa-field"><span>期中占比%</span><input v-model.number="form.midtermRatio" type="number" min="0" max="100" class="aa-input" placeholder="0=不启用期中" /></label>
          <label class="aa-field"><span>期末占比%</span><input v-model.number="form.finalRatio" type="number" min="0" max="100" class="aa-input" /></label>
          <label class="aa-field"><span>及格线</span><input v-model.number="form.passLine" type="number" min="0" max="100" class="aa-input" /></label>
          <label v-if="isAdminRole && !form.teachingTaskId" class="aa-field"><span class="req">补录原因</span><input v-model="form.adminSupplementReason" type="text" class="aa-input" placeholder="不少于5字" /></label>
        </div>
        <p class="mp-note">创建后可继续使用固定三段录入，也可在任务内切换为1—12项动态成绩方案；动态方案首次录分后锁定。</p>
        <div class="aa-actions"><AppButton variant="primary" :loading="creating" @click="createTask">创建任务</AppButton></div>

        <div v-if="myTasks.length" class="aa-my-tasks">
          <h4>我的录入任务</h4>
          <ul>
            <li v-for="t in myTasks" :key="t.gradeTaskId" class="aa-my-task-item">
              <span>{{ t.courseName }}<small v-if="t.courseId"> · 课程ID {{ t.courseId }}</small></span>
              <AppStatusTag :type="statusColor(t.status)" dot>{{ statusLabel(t.status) }}</AppStatusTag>
              <button class="mp-link" @click="openTask(t)">进入</button>
            </li>
          </ul>
        </div>
      </AppSectionCard>

      <template v-else>
        <AppSectionCard :title="`录入任务：${task.courseName}`">
          <template #header-extra><button class="mp-link" @click="closeTask">返回</button></template>
          <div class="aa-task-head">
            <span>课程ID {{ task.courseId || '待治理' }} · 及格线 {{ task.passLine }}</span>
            <AppStatusTag :type="statusColor(task.status)" dot>{{ statusLabel(task.status) }}</AppStatusTag>
          </div>
          <div class="aa-mode-switch">
            <button :class="['aa-mode', { 'is-active': !dynamicMode }]" @click="switchMode(false)">固定三段</button>
            <button :class="['aa-mode', { 'is-active': dynamicMode }]" @click="switchMode(true)">动态成绩项</button>
          </div>
          <AppInlineAlert v-if="!task.courseId" type="warning" title="课程身份欠账" description="该历史任务尚未绑定课程库具体版本，不能发布正式成绩。" />
          <AppInlineAlert v-if="task.status === 'RETURNED' && task.returnReason" type="warning" :message="`已被退回：${task.returnReason}，请核对后重新提交`" />
        </AppSectionCard>

        <template v-if="!dynamicMode">
          <AppSectionCard v-if="editable" title="添加学生">
            <div class="aa-reg-search">
              <AppStudentPicker v-model="candidateStudentId" class="aa-input--grow" placeholder="按姓名/学号检索并添加学生" @change="onStudentPicked" />
              <AppButton :loading="loadingRoster" @click="loadRoster">按正式名单圈定</AppButton>
              <AppButton @click="importVisible = true">导入成绩（Excel）</AppButton>
            </div>
          </AppSectionCard>

          <AppExcelImportDrawer
            v-if="task"
            v-model:visible="importVisible"
            title="导入成绩（学号/平时/期中/期末/异常标记）"
            template-name="成绩导入模板.xlsx"
            :required-fields="['学号']"
            :preview-fields="['studentNo', 'studentName', 'usualScore', 'midtermScore', 'finalScore', 'exceptionFlag']"
            :download-template-fn="() => academicAffairsApi.downloadGradeImportTemplate(task.gradeTaskId)"
            :upload-fn="(file) => academicAffairsApi.uploadGradeImportXlsx(task.gradeTaskId, file)"
            :confirm-fn="({ rows }) => academicAffairsApi.confirmGradeImport(task.gradeTaskId, rows)"
            :download-errors-fn="({ rows, errors }) => academicAffairsApi.downloadGradeImportErrors(task.gradeTaskId, rows, errors)"
            @imported="onImported"
          />

          <AppSectionCard title="固定三段成绩录入表">
            <p class="mp-note">平时 {{ task.usualRatio }}%<template v-if="hasMidterm"> · 期中 {{ task.midtermRatio }}%</template> · 期末 {{ task.finalRatio }}%</p>
            <EmptyState v-if="!rows.length" title="录入表为空" description="从上方检索学生加入，或按正式教学班名单圈定" />
            <table v-else class="aa-course-table">
              <thead><tr><th>学生</th><th>异常标记</th><th>平时分</th><th v-if="hasMidterm">期中分</th><th>期末分</th><th>总评</th><th>结果</th><th></th></tr></thead>
              <tbody>
                <tr v-for="r in rows" :key="r.studentId">
                  <td>{{ r.realName }}</td>
                  <td><AppSelect v-model="r.exceptionFlag" :options="exceptionOptions" :disabled="!editable" placeholder="" size="compact" /></td>
                  <td><input v-model.number="r.usual" type="number" min="0" max="100" class="aa-input aa-input--xs" :disabled="!editable || r.exceptionFlag !== 'NORMAL'" /></td>
                  <td v-if="hasMidterm"><input v-model.number="r.midterm" type="number" min="0" max="100" class="aa-input aa-input--xs" :disabled="!editable || r.exceptionFlag !== 'NORMAL'" /></td>
                  <td><input v-model.number="r.final" type="number" min="0" max="100" class="aa-input aa-input--xs" :disabled="!editable || r.exceptionFlag !== 'NORMAL'" /></td>
                  <td>{{ r.total ?? '—' }}</td>
                  <td><AppStatusTag v-if="r.passStatus" :type="r.passStatus === 'PASSED' ? 'success' : 'danger'">{{ r.passStatus === 'PASSED' ? '及格' : '不及格' }}</AppStatusTag></td>
                  <td><button v-if="editable" class="mp-link" @click="saveRow(r)">录入</button></td>
                </tr>
              </tbody>
            </table>
          </AppSectionCard>
        </template>

        <template v-else>
          <AppSectionCard title="动态成绩项方案">
            <AppInlineAlert
              type="info"
              title="兼容现有成绩主账"
              description="分项成绩单独留痕，系统按权重生成总评后仍进入原学院审核、教务发布、预警和成绩单流程。首次录分后方案自动锁定。"
            />
            <LoadingState v-if="dynamicLoading" />
            <template v-else-if="dynamicData">
              <div class="aa-scheme-head">
                <span>名单版本：{{ dynamicData.rosterIdentity?.rosterVersionNo || '—' }} · {{ dynamicData.rosterIdentity?.memberCount || 0 }}人</span>
                <span>权重合计 {{ schemeTotal }}%</span>
              </div>
              <div class="aa-scheme-list">
                <div v-for="(component, index) in schemeDraft" :key="component.code + index" class="aa-scheme-row">
                  <input v-model.trim="component.code" class="aa-input aa-code" maxlength="40" :disabled="!schemeEditable" placeholder="代码" />
                  <input v-model.trim="component.name" class="aa-input aa-name" maxlength="80" :disabled="!schemeEditable" placeholder="名称" />
                  <input v-model.number="component.weight" type="number" min="0.01" max="100" step="0.01" class="aa-input aa-weight" :disabled="!schemeEditable" />
                  <label class="aa-required"><input v-model="component.required" type="checkbox" :disabled="!schemeEditable" /> 必填</label>
                  <button v-if="schemeEditable && schemeDraft.length > 1" class="mp-link is-danger" @click="removeComponent(index)">删除</button>
                </div>
              </div>
              <div v-if="schemeEditable" class="aa-actions">
                <AppButton :disabled="schemeDraft.length >= 12" @click="addComponent">新增成绩项</AppButton>
                <AppButton variant="primary" :loading="schemeSaving" @click="saveScheme">保存方案</AppButton>
              </div>
              <p v-else class="mp-note">方案状态：{{ dynamicData.scheme?.status }}。已开始录分或任务状态已变化，当前只读。</p>
            </template>
          </AppSectionCard>

          <AppSectionCard title="动态分项录入表">
            <ErrorState v-if="dynamicError" :description="dynamicError" @retry="loadDynamic" />
            <LoadingState v-else-if="dynamicLoading" />
            <EmptyState v-else-if="!dynamicRows.length" title="正式名单为空" description="请先完成教学班和名单版本治理" />
            <div v-else class="aa-table-scroll">
              <table class="aa-course-table aa-dynamic-table">
                <thead>
                  <tr>
                    <th>学生</th><th>异常标记</th>
                    <th v-for="component in dynamicComponents" :key="component.code">{{ component.name }}<small>{{ component.weight }}%</small></th>
                    <th>总评</th><th>结果</th><th></th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="row in dynamicRows" :key="row.studentId">
                    <td><strong>{{ row.realName }}</strong><small>{{ row.studentNo }}</small></td>
                    <td><AppSelect v-model="row.exceptionFlag" :options="exceptionOptions" :disabled="!editable" placeholder="" size="compact" /></td>
                    <td v-for="component in dynamicComponents" :key="component.code">
                      <input v-model.number="row.scores[component.code]" type="number" min="0" max="100" step="0.01" class="aa-input aa-input--xs" :disabled="!editable || row.exceptionFlag !== 'NORMAL'" />
                    </td>
                    <td>{{ row.totalScore ?? '—' }}</td>
                    <td><AppStatusTag v-if="row.passStatus" :type="row.passStatus === 'PASSED' ? 'success' : 'danger'">{{ row.passStatus === 'PASSED' ? '及格' : '不及格' }}</AppStatusTag></td>
                    <td><button v-if="editable" class="mp-link" :disabled="dynamicSavingId === row.studentId" @click="saveDynamicRow(row)">{{ dynamicSavingId === row.studentId ? '保存中' : '保存' }}</button></td>
                  </tr>
                </tbody>
              </table>
            </div>
          </AppSectionCard>
        </template>

        <AppSectionCard v-if="editable" title="提交审核">
          <div class="aa-actions">
            <AppButton variant="primary" :loading="submitting" @click="submit">提交进入学院审核</AppButton>
            <span class="mp-note">提交时冻结正式名单版本；名单换版后必须退回重建，禁止静默替换。</span>
          </div>
        </AppSectionCard>
      </template>
    </div>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, EmptyState, LoadingState, ErrorState } from '@/components/business'
import { AppButton } from '@/components/ui'
import {
  AppSectionCard, AppStatusTag, AppInlineAlert, AppSelect,
  AppClassPicker, AppStudentPicker, AppTeachingTaskPicker,
  AppCoursePicker, AppTermEntityPicker
} from '@/components/common'
import { AppExcelImportDrawer } from '@/components/common/excel'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { academicAffairsR10Api } from '@/modules/academicAffairs/api/academic-affairs-r10.api'
import { toast } from '@/utils/toast'

const TASK_STATUS = {
  NOT_STARTED: '未开始', INPUTTING: '录入中', SUBMITTED: '已提交',
  COLLEGE_REVIEW: '学院审核中', ACADEMIC_REVIEW: '教务终审中', PUBLISHED: '已发布',
  RETURNED: '已退回', ARCHIVED: '已归档'
}
const EDITABLE_STATUS = new Set(['NOT_STARTED', 'INPUTTING', 'RETURNED'])
const ADMIN_ROLES = new Set(['SCHOOL_ADMIN', 'ACADEMIC_ADMIN', 'JWC_ADMIN', 'PLATFORM_SUPER_ADMIN'])

export default {
  name: 'AaGradeEntryView',
  components: {
    ModulePageShell, EmptyState, LoadingState, ErrorState, AppButton, AppSectionCard,
    AppStatusTag, AppInlineAlert, AppSelect, AppExcelImportDrawer, AppClassPicker,
    AppStudentPicker, AppTeachingTaskPicker, AppCoursePicker, AppTermEntityPicker
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      form: {
        teachingTaskId: '', courseId: '', courseName: '', termId: '', termCode: '',
        credit: null, classId: '', usualRatio: 30, midtermRatio: 0, finalRatio: 70,
        passLine: 60, adminSupplementReason: ''
      },
      creating: false, task: null, myTasks: [],
      candidateStudentId: '', loadingRoster: false, rows: [], submitting: false,
      importVisible: false,
      dynamicMode: false, dynamicLoading: false, dynamicError: '', dynamicData: null,
      schemeDraft: [], schemeSaving: false, dynamicSavingId: ''
    }
  },
  computed: {
    editable() { return this.task && EDITABLE_STATUS.has(this.task.status) },
    hasMidterm() { return this.task && Number(this.task.midtermRatio) > 0 },
    isAdminRole() {
      const code = (this.ctx?.currentRole?.roleCode || this.ctx?.currentRoleCode || '').toUpperCase()
      return ADMIN_ROLES.has(code) || this.ctx?.userType === 'PLATFORM_SUPER_ADMIN'
    },
    exceptionOptions() {
      return [
        { value: 'NORMAL', label: '正常' }, { value: 'ABSENT', label: '缺考' },
        { value: 'DEFERRED', label: '缓考' }, { value: 'EXEMPT', label: '免修' },
        { value: 'CHEAT', label: '作弊' }
      ]
    },
    dynamicRows() { return this.dynamicData?.items || [] },
    dynamicComponents() { return this.dynamicData?.scheme?.components || [] },
    schemeEditable() { return !!this.dynamicData?.scheme?.editable },
    schemeTotal() { return Number(this.schemeDraft.reduce((sum, item) => sum + Number(item.weight || 0), 0).toFixed(4)) }
  },
  created() { this.loadTasks() },
  methods: {
    statusLabel(status) { return TASK_STATUS[status] || status || '未知' },
    statusColor(status) {
      if (['PUBLISHED', 'ARCHIVED'].includes(status)) return 'success'
      if (['RETURNED'].includes(status)) return 'warning'
      if (['SUBMITTED', 'COLLEGE_REVIEW', 'ACADEMIC_REVIEW'].includes(status)) return 'primary'
      return 'default'
    },
    closeTask() {
      this.task = null; this.rows = []; this.dynamicData = null; this.dynamicMode = false
    },
    switchMode(value) {
      this.dynamicMode = value
      if (value) this.loadDynamic()
    },
    onTeachingTaskChange(value, items) {
      if (!value) {
        this.form.courseId = ''; this.form.courseName = ''; this.form.termCode = ''
        this.form.credit = null; this.form.classId = ''
        return
      }
      const item = items?.[0]
      const task = item?.raw || item || {}
      this.form.courseId = task.courseId || ''
      this.form.courseName = task.courseName || task.name || item?.label || ''
      if (task.credit != null) this.form.credit = task.credit
      if (task.classId != null) this.form.classId = String(task.classId)
      this.form.termCode = task.termCode || ''
    },
    onCourseChange(value, items) {
      const item = items?.[0]
      const course = item?.raw || item || {}
      this.form.courseId = value || course.courseId || course.id || ''
      this.form.courseName = course.courseName || course.name || item?.label || ''
      if (course.credit != null) this.form.credit = course.credit
    },
    onStudentPicked(value, items) {
      const item = items?.[0]
      if (!item) return
      this.addRow(item.raw || item)
      this.candidateStudentId = ''
    },
    async loadTasks() {
      const res = await academicAffairsApi.getGradeTasks({ page: 1, pageSize: 50 })
      if (res.code !== 0) return
      let list = res.data?.list || res.data?.items || []
      const filter = String(this.$route.query.filter || '').toLowerCase()
      const todoType = String(this.$route.query.todoType || '')
      if (filter === 'pending' || todoType === 'AA_GRADE_ENTRY') list = list.filter((row) => EDITABLE_STATUS.has(row.status))
      this.myTasks = list
      const taskId = this.$route.query.taskId
      if (taskId) {
        const hit = list.find((row) => String(row.gradeTaskId) === String(taskId))
        if (hit) await this.openTask(hit)
      } else if ((filter === 'pending' || todoType === 'AA_GRADE_ENTRY') && list.length === 1) await this.openTask(list[0])
    },
    async openTask(row) {
      this.task = { ...row }; this.rows = []; this.dynamicData = null
      this.dynamicMode = String(this.$route.query.mode || '') === 'dynamic'
      await this.refreshRecords()
      if (this.dynamicMode) await this.loadDynamic()
      if (this.$route.query.action === 'import') this.importVisible = true
    },
    async refreshRecords() {
      if (!this.task) return
      const res = await academicAffairsApi.getGradeRecords(this.task.gradeTaskId)
      if (res.code === 0) {
        this.rows = (res.data.items || []).map((item) => ({
          studentId: item.studentId, realName: item.realName, usual: item.usualScore,
          midterm: item.midtermScore, final: item.finalScore, total: item.totalScore,
          passStatus: item.passStatus, exceptionFlag: item.exceptionFlag || 'NORMAL'
        }))
      }
    },
    async loadDynamic() {
      if (!this.task || this.dynamicLoading) return
      this.dynamicLoading = true; this.dynamicError = ''
      const res = await academicAffairsR10Api.getDynamicGradeRoster(this.task.gradeTaskId)
      this.dynamicLoading = false
      if (res.code !== 0) { this.dynamicError = res.message || '动态成绩工作区加载失败'; return }
      this.dynamicData = res.data
      this.schemeDraft = (res.data.scheme?.components || []).map((item, index) => ({
        code: item.code, name: item.name, weight: Number(item.weight),
        required: item.required !== false, order: item.order || index + 1
      }))
      this.dynamicData.items = (res.data.items || []).map((row) => ({
        ...row, scores: { ...(row.scores || {}) }, exceptionFlag: row.exceptionFlag || 'NORMAL'
      }))
      if (this.task.status !== res.data.status) this.task.status = res.data.status
    },
    addComponent() {
      const index = this.schemeDraft.length + 1
      this.schemeDraft.push({ code: `ITEM_${index}`, name: `成绩项${index}`, weight: 0, required: true, order: index })
    },
    removeComponent(index) { this.schemeDraft.splice(index, 1) },
    async saveScheme() {
      if (this.schemeSaving) return
      if (Math.abs(this.schemeTotal - 100) > 0.0001) { toast.error(`权重合计须为100%，当前为${this.schemeTotal}%`); return }
      this.schemeSaving = true
      const res = await academicAffairsR10Api.updateGradeScheme(this.task.gradeTaskId, this.schemeDraft.map((item, index) => ({ ...item, code: String(item.code || '').toUpperCase(), order: index + 1 })))
      this.schemeSaving = false
      if (res.code === 0) { toast.success('动态成绩项方案已保存'); await this.loadDynamic() }
      else toast.error(res.message || '方案保存失败')
    },
    async saveDynamicRow(row) {
      if (this.dynamicSavingId) return
      this.dynamicSavingId = row.studentId
      const scores = {}
      if (row.exceptionFlag === 'NORMAL') {
        this.dynamicComponents.forEach((component) => {
          if (row.scores[component.code] !== '' && row.scores[component.code] != null) scores[component.code] = row.scores[component.code]
        })
      }
      const res = await academicAffairsR10Api.saveDynamicGrade(this.task.gradeTaskId, {
        studentId: Number(row.studentId), scores, exceptionFlag: row.exceptionFlag
      })
      this.dynamicSavingId = ''
      if (res.code === 0) {
        row.totalScore = res.data.totalScore; row.passStatus = res.data.passStatus
        row.exceptionFlag = res.data.exceptionFlag || row.exceptionFlag
        if (this.task.status === 'NOT_STARTED') this.task.status = 'INPUTTING'
        toast.success(`${row.realName} 分项成绩已保存`)
        await this.loadDynamic()
      } else toast.error(res.message || '分项成绩保存失败')
    },
    async onImported(result) {
      toast.success(`已导入 ${result?.imported ?? result?.created ?? 0} 条成绩`)
      if (this.task && this.task.status === 'NOT_STARTED' && (result?.imported || result?.created)) this.task.status = 'INPUTTING'
      await this.refreshRecords()
    },
    async createTask() {
      if (this.creating) return
      if (!this.form.teachingTaskId && !this.isAdminRole) { toast.error('请选择教学任务'); return }
      if (!this.form.teachingTaskId) {
        if (!this.form.courseId) { toast.error('请选择课程库具体版本'); return }
        if (!this.form.termId) { toast.error('请选择正式学期'); return }
        if ((this.form.adminSupplementReason || '').trim().length < 5) { toast.error('管理员特殊补录原因不少于5字'); return }
      }
      if (Number(this.form.usualRatio) + Number(this.form.midtermRatio) + Number(this.form.finalRatio) !== 100) {
        toast.error('平时+期中+期末占比之和须=100'); return
      }
      this.creating = true
      const res = await academicAffairsApi.createGradeTask({
        teachingTaskId: this.form.teachingTaskId || undefined,
        courseId: this.form.teachingTaskId ? undefined : Number(this.form.courseId),
        courseName: this.form.teachingTaskId ? undefined : this.form.courseName,
        termId: this.form.teachingTaskId ? undefined : Number(this.form.termId),
        classId: this.form.teachingTaskId || !this.form.classId ? undefined : Number(this.form.classId),
        credit: this.form.teachingTaskId ? undefined : this.form.credit,
        usualRatio: Number(this.form.usualRatio), midtermRatio: Number(this.form.midtermRatio),
        finalRatio: Number(this.form.finalRatio), passLine: Number(this.form.passLine),
        adminSupplementReason: this.form.teachingTaskId ? undefined : this.form.adminSupplementReason.trim()
      })
      this.creating = false
      if (res.code === 0) { this.task = res.data; toast.success('任务已创建，开始录入'); this.loadTasks() }
      else toast.error(res.message || '创建失败')
    },
    async loadRoster() {
      if (this.loadingRoster) return
      this.loadingRoster = true
      const res = await academicAffairsApi.getGradeRoster(this.task.gradeTaskId)
      this.loadingRoster = false
      if (res.code === 0) {
        const items = res.data.items || []
        if (!items.length) { toast.error(res.data.note || '未圈定到正式名单'); return }
        items.forEach((student) => this.addRow(student))
        toast.success(`已加入 ${items.length} 人`)
      } else toast.error(res.message || '加载名单失败')
    },
    addRow(student) {
      if (this.rows.some((row) => row.studentId === student.studentId)) return
      this.rows.push({ studentId: student.studentId, realName: student.realName, usual: null, midterm: null, final: null, total: null, passStatus: null, exceptionFlag: 'NORMAL' })
    },
    async saveRow(row) {
      const res = await academicAffairsApi.enterScore(this.task.gradeTaskId, {
        studentId: row.studentId,
        usualScore: row.exceptionFlag === 'NORMAL' && row.usual != null ? row.usual : undefined,
        midtermScore: row.exceptionFlag === 'NORMAL' && row.midterm != null ? row.midterm : undefined,
        finalScore: row.exceptionFlag === 'NORMAL' && row.final != null ? row.final : undefined,
        exceptionFlag: row.exceptionFlag
      })
      if (res.code === 0) {
        row.total = res.data.totalScore; row.passStatus = res.data.passStatus
        toast.success(`${row.realName} 已录入`)
        if (this.task.status === 'NOT_STARTED') this.task.status = 'INPUTTING'
      } else toast.error(res.message || '录入失败')
    },
    async submit() {
      if (this.submitting) return
      this.submitting = true
      const res = await academicAffairsApi.submitGradeTask(this.task.gradeTaskId)
      this.submitting = false
      if (res.code === 0) { this.task.status = res.data.status; toast.success('已提交，进入学院审核'); this.loadTasks() }
      else toast.error(res.message || '提交失败')
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-grid2 { display: grid; grid-template-columns: repeat(2, minmax(220px, 1fr)); gap: 14px 24px; }
.aa-field { display: flex; flex-direction: column; gap: 6px; font-size: 13px; color: var(--text-700, #4e5969); }
.aa-field .req::before, .aa-field span.req::before { content: '*'; color: var(--danger-600, #f53f3f); margin-right: 4px; }
.aa-input { height: 34px; padding: 0 12px; border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px; background: var(--bg-white, #fff); color: var(--text-900, #1f2329); font-size: 14px; box-sizing: border-box; }
.aa-input--grow { flex: 1; }.aa-input--xs { width: 82px; height: 30px; padding: 0 8px; }
.aa-actions { margin-top: 16px; display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }.aa-reg-search { display: flex; gap: 12px; }
.aa-task-head { display: flex; align-items: center; gap: 16px; font-size: 14px; color: var(--text-700, #4e5969); margin-bottom: 8px; }
.aa-mode-switch { display: inline-flex; gap: 4px; margin: 8px 0 12px; padding: 4px; border-radius: 8px; background: var(--fill-100, #f2f3f5); }
.aa-mode { padding: 7px 14px; border: 0; border-radius: 6px; background: transparent; color: var(--text-600, #64748b); cursor: pointer; }
.aa-mode.is-active { background: #fff; color: var(--primary-600, #2563eb); box-shadow: 0 1px 3px rgba(15,23,42,.12); }
.aa-course-table { width: 100%; border-collapse: collapse; }.aa-course-table th, .aa-course-table td { text-align: left; padding: 8px 12px; border-bottom: 1px solid var(--border-100, #f0f1f2); font-size: 14px; }
.aa-course-table th { color: var(--text-500, #646a73); font-weight: 500; font-size: 13px; white-space: nowrap; }.aa-course-table th small, .aa-course-table td small { display: block; margin-top: 3px; color: var(--text-400, #8a9099); font-size: 11px; }
.aa-table-scroll { overflow-x: auto; }.aa-dynamic-table { min-width: 860px; }
.aa-scheme-head { display: flex; justify-content: space-between; margin: 14px 0 10px; color: var(--text-600, #64748b); font-size: 13px; }
.aa-scheme-list { display: flex; flex-direction: column; gap: 8px; }.aa-scheme-row { display: flex; align-items: center; gap: 10px; }.aa-code { width: 150px; }.aa-name { flex: 1; }.aa-weight { width: 110px; }.aa-required { display: flex; align-items: center; gap: 5px; font-size: 13px; white-space: nowrap; }.is-danger { color: var(--danger-600, #dc2626); }
.aa-my-tasks { margin-top: 20px; border-top: 1px solid var(--border-100, #f0f1f2); padding-top: 16px; }.aa-my-tasks h4 { margin: 0 0 10px; font-size: 14px; }
.aa-my-tasks ul { list-style: none; margin: 0; padding: 0; }.aa-my-task-item { display: flex; align-items: center; gap: 12px; padding: 8px 0; border-bottom: 1px solid var(--border-100, #f0f1f2); font-size: 14px; }.aa-my-task-item small { color: var(--text-500, #64748b); }
@media (max-width: 760px) { .aa-grid2 { grid-template-columns: 1fr; }.aa-scheme-row { align-items: stretch; flex-direction: column; }.aa-code, .aa-weight { width: 100%; } }
</style>
