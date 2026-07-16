<template>
  <AppPageShell
    title="宿舍检查"
    subtitle="卫生/安全/违禁/夜不归宿检查任务与记录；异常须绑真实涉事学生（夜不归宿必填），自动进入风险处置。"
    role-name="宿管 / 辅导员 / 学工处"
    data-scope-name="宿管限负责楼栋"
    watermark-purpose="宿舍检查登记"
  >
    <template #actions>
      <AppPermissionButton code="studentAffairs.dorm.inspection.manage" :loading="actioning" @click="openCreateTask">
        新建检查任务
      </AppPermissionButton>
    </template>

    <AppGlobalState :state="pageState" :description="errorMessage" loading-text="正在加载检查任务..." @retry="load"
                    @back="$router.push('/admin/student-affairs/dashboard')">
      <AppSectionCard title="检查任务">
        <table class="sa-table">
          <thead><tr><th>任务</th><th>类型</th><th>楼栋</th><th>状态</th><th>操作</th></tr></thead>
          <tbody>
            <tr v-for="t in tasks" :key="t.taskId" :class="{ 'sa-sel': t.taskId === curTask }">
              <td><strong>{{ t.taskName }}</strong></td>
              <td>{{ typeLabel(t.checkType) }}</td>
              <td>{{ t.buildingName || '—' }}</td>
              <td>{{ t.status }}</td>
              <td class="sa-actions">
                <AppPermissionButton code="studentAffairs.dorm.view" size="sm" variant="secondary" @click="openTask(t)">记录</AppPermissionButton>
                <AppPermissionButton code="studentAffairs.dorm.inspection.manage" size="sm" :loading="actioning" @click="openAddRecord(t)">录结果</AppPermissionButton>
              </td>
            </tr>
            <tr v-if="!tasks.length"><td colspan="5" class="sa-empty">暂无检查任务</td></tr>
          </tbody>
        </table>
        <AppPagination v-model:page="tasksPagination.page" v-model:pageSize="tasksPagination.pageSize" :total="tasksPagination.total" @change="load" />
      </AppSectionCard>

      <AppSectionCard v-if="curTask" :title="`检查记录 · ${curTaskName}`">
        <table class="sa-table">
          <thead><tr><th>房间</th><th>结果</th><th>问题</th><th>说明</th><th>关联风险</th></tr></thead>
          <tbody>
            <tr v-for="r in records" :key="r.recordId">
              <td>{{ r.roomNo || r.roomId || '—' }}</td>
              <td><AppStatusTag :type="r.result === 'ABNORMAL' ? 'danger' : 'success'" :label="r.result === 'ABNORMAL' ? '异常' : '正常'" /></td>
              <td>{{ r.issueType || '—' }}</td>
              <td>{{ r.detail || '—' }}</td>
              <td><a v-if="r.relatedRiskId" class="sa-link" @click="$router.push(`/admin/student-affairs/risk/${r.relatedRiskId}`)">风险 #{{ r.relatedRiskId }} →</a><span v-else class="sa-muted">—</span></td>
            </tr>
            <tr v-if="!records.length"><td colspan="5" class="sa-empty">暂无检查记录</td></tr>
          </tbody>
        </table>
        <AppPagination v-model:page="recordsPagination.page" v-model:pageSize="recordsPagination.pageSize" :total="recordsPagination.total" @change="reloadRecords" />
      </AppSectionCard>
    </AppGlobalState>

    <!-- 新建检查任务 -->
    <AppDrawer v-model:visible="createTaskDrawer.visible" title="新建检查任务">
      <div class="sa-form">
        <AppFormItem label="任务名称" required :error="createTaskDrawer.errors.taskName">
          <AppTextInput v-model="createTaskDrawer.form.taskName" placeholder="如 月度卫生检查" :disabled="actioning" />
        </AppFormItem>
        <AppFormItem label="检查类型">
          <AppSelect v-model="createTaskDrawer.form.checkType" :options="checkTypeOptions" :disabled="actioning" />
        </AppFormItem>
        <AppFormItem label="楼栋 ID">
          <AppTextInput v-model="createTaskDrawer.form.buildingId" placeholder="限定楼栋（选填）" :disabled="actioning" />
        </AppFormItem>
        <AppInlineAlert v-if="createTaskDrawer.errorMessage" type="danger" :description="createTaskDrawer.errorMessage" />
      </div>
      <template #footer>
        <button type="button" class="sa-btn" :disabled="actioning" @click="createTaskDrawer.visible = false">取消</button>
        <AppPermissionButton code="studentAffairs.dorm.inspection.manage" :loading="actioning" @click="submitCreateTask">
          新建
        </AppPermissionButton>
      </template>
    </AppDrawer>

    <!-- 录检查结果 -->
    <AppDrawer v-model:visible="addRecordDrawer.visible" :title="`录结果 · ${addRecordDrawer.task ? addRecordDrawer.task.taskName : ''}`">
      <div class="sa-form">
        <AppFormItem label="房间 ID">
          <AppTextInput v-model="addRecordDrawer.form.roomId" placeholder="限定房间（选填）" :disabled="actioning" />
        </AppFormItem>
        <AppFormItem label="检查结果">
          <AppSelect v-model="addRecordDrawer.form.result" :options="resultOptions" :disabled="actioning" />
        </AppFormItem>
        <template v-if="addRecordDrawer.form.result === 'ABNORMAL'">
          <AppFormItem label="异常说明" required :error="addRecordDrawer.errors.detail">
            <AppQuickPhrases scene-key="sa.dorm.exception" :group="addRecordDrawer.task ? addRecordDrawer.task.checkType : ''" @pick="onPickDetail" />
            <AppTextarea ref="detailTa" v-model="addRecordDrawer.form.detail" placeholder="异常说明（不少于 5 字）" :disabled="actioning" />
          </AppFormItem>
          <AppFormItem
            label="涉事学生 ID"
            :required="needStudentId"
            :error="addRecordDrawer.errors.studentId"
            :hint="needStudentId ? '夜不归宿检查必须指定涉事学生' : '填写后将绑定风险处置'"
          >
            <AppTextInput v-model="addRecordDrawer.form.studentId" placeholder="学生 ID" :disabled="actioning" />
          </AppFormItem>
        </template>
        <AppInlineAlert v-if="addRecordDrawer.errorMessage" type="danger" :description="addRecordDrawer.errorMessage" />
      </div>
      <template #footer>
        <button type="button" class="sa-btn" :disabled="actioning" @click="addRecordDrawer.visible = false">取消</button>
        <AppPermissionButton code="studentAffairs.dorm.inspection.manage" :loading="actioning" @click="submitAddRecord">
          提交
        </AppPermissionButton>
      </template>
    </AppDrawer>
  </AppPageShell>
</template>

<script>
import { AppFormItem, AppGlobalState, AppInlineAlert, AppPageShell, AppPagination, AppPermissionButton,
        AppQuickPhrases, AppSectionCard, AppSelect, AppStatusTag, AppTextarea, AppTextInput } from '@/components/common'
import AppDrawer from '@/components/ui/AppDrawer.vue'
import { insertAtCursor, applyInsertion } from '@/utils/insertAtCursor'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairsB.api'

const CHECK_TYPE_OPTIONS = [
  { label: '卫生', value: 'HYGIENE' },
  { label: '安全', value: 'SAFETY' },
  { label: '违禁品', value: 'CONTRABAND' },
  { label: '夜不归宿', value: 'NIGHT_ABSENCE' }
]

const RESULT_OPTIONS = [
  { label: '正常', value: 'NORMAL' },
  { label: '异常', value: 'ABNORMAL' }
]

function freshCreateTaskForm() {
  return { taskName: '', checkType: 'HYGIENE', buildingId: '' }
}

function freshAddRecordForm() {
  return { roomId: '', result: 'ABNORMAL', detail: '', studentId: '' }
}

export default {
  name: 'DormCheckView',
  components: { AppDrawer, AppFormItem, AppGlobalState, AppInlineAlert, AppPageShell, AppPagination,
               AppPermissionButton, AppQuickPhrases, AppSectionCard, AppSelect, AppStatusTag, AppTextarea, AppTextInput },
  data() {
    return {
      loading: true, actioning: false, errorMessage: '', tasks: [], curTask: '', curTaskName: '', curTaskType: '', records: [],
      tasksPagination: { page: 1, pageSize: 20, total: 0 },
      recordsPagination: { page: 1, pageSize: 20, total: 0 },
      checkTypeOptions: CHECK_TYPE_OPTIONS,
      resultOptions: RESULT_OPTIONS,
      createTaskDrawer: { visible: false, form: freshCreateTaskForm(), errors: {}, errorMessage: '' },
      addRecordDrawer: { visible: false, task: null, form: freshAddRecordForm(), errors: {}, errorMessage: '' }
    }
  },
  computed: {
    pageState() { return this.loading ? 'loading' : (this.errorMessage ? 'error' : 'ready') },
    needStudentId() {
      return !!this.addRecordDrawer.task && this.addRecordDrawer.task.checkType === 'NIGHT_ABSENCE'
    }
  },
  mounted() { this.load() },
  methods: {
    async load() {
      this.loading = true; this.errorMessage = ''
      try {
        const res = await studentAffairsApi.listDormCheckTasks({
          page: this.tasksPagination.page, pageSize: this.tasksPagination.pageSize
        })
        this.tasks = res.data.items || []
        this.tasksPagination.total = res.data.total || 0
      } catch (e) { this.errorMessage = e.message || '检查任务加载失败' } finally { this.loading = false }
    },
    async openTask(t) {
      this.curTask = t.taskId; this.curTaskName = t.taskName; this.curTaskType = t.checkType
      this.recordsPagination.page = 1
      await this.reloadRecords()
    },
    async reloadRecords() {
      if (!this.curTask) return
      try {
        const res = await studentAffairsApi.listDormCheckRecords(this.curTask, {
          page: this.recordsPagination.page, pageSize: this.recordsPagination.pageSize
        })
        this.records = res.data.items || []
        this.recordsPagination.total = res.data.total || 0
      } catch (e) { this.errorMessage = e.message }
    },
    openCreateTask() {
      this.createTaskDrawer.form = freshCreateTaskForm()
      this.createTaskDrawer.errors = {}
      this.createTaskDrawer.errorMessage = ''
      this.createTaskDrawer.visible = true
    },
    async submitCreateTask() {
      const { form, errors } = this.createTaskDrawer
      errors.taskName = form.taskName.trim() ? '' : '任务名称必填'
      if (errors.taskName) return
      this.actioning = true; this.createTaskDrawer.errorMessage = ''
      try {
        await studentAffairsApi.createDormCheckTask({
          taskName: form.taskName.trim(), checkType: form.checkType, buildingId: form.buildingId.trim() || null
        })
        this.createTaskDrawer.visible = false
        await this.load()
      } catch (e) { this.createTaskDrawer.errorMessage = e.message || '新建失败' }
      finally { this.actioning = false }
    },
    openAddRecord(t) {
      this.addRecordDrawer.task = t
      this.addRecordDrawer.form = freshAddRecordForm()
      this.addRecordDrawer.errors = {}
      this.addRecordDrawer.errorMessage = ''
      this.addRecordDrawer.visible = true
    },
    async submitAddRecord() {
      const { form, errors, task } = this.addRecordDrawer
      if (!task) return
      errors.detail = ''; errors.studentId = ''
      const body = { roomId: form.roomId.trim() || null, result: form.result, issueType: task.checkType }
      if (form.result === 'ABNORMAL') {
        if (!form.detail.trim() || form.detail.trim().length < 5) { errors.detail = '异常说明不少于 5 字'; }
        if (this.needStudentId && !form.studentId.trim()) { errors.studentId = '夜不归宿须指定涉事学生' }
        if (errors.detail || errors.studentId) return
        body.detail = form.detail.trim()
        if (form.studentId.trim()) body.studentId = form.studentId.trim()
      }
      this.actioning = true; this.addRecordDrawer.errorMessage = ''
      try {
        await studentAffairsApi.submitDormCheckRecord(task.taskId, body)
        this.addRecordDrawer.visible = false
        await this.load()
        if (this.curTask === task.taskId) await this.reloadRecords()
      } catch (e) { this.addRecordDrawer.errorMessage = e.message || '提交失败' }
      finally { this.actioning = false }
    },
    typeLabel(t) { return ({ HYGIENE: '卫生', SAFETY: '安全', CONTRABAND: '违禁品', NIGHT_ABSENCE: '夜不归宿' })[t] || t },
    onPickDetail(text) {
      const el = this.$refs.detailTa?.$refs?.el
      const { value, selStart, selEnd } = insertAtCursor(el, this.addRecordDrawer.form.detail, text)
      this.addRecordDrawer.form.detail = value
      this.$nextTick(() => applyInsertion(el, selStart, selEnd))
    }
  }
}
</script>

<style scoped>
.sa-table { width: 100%; border-collapse: collapse; }
.sa-table th, .sa-table td { border-bottom: 1px solid var(--border-light); padding: var(--space-3); text-align: left; }
.sa-actions { display: flex; flex-wrap: wrap; gap: var(--space-2); }
.sa-sel { background: var(--primary-50, var(--bg-subtle)); }
.sa-link { color: var(--primary-600); cursor: pointer; }
.sa-muted { color: var(--text-tertiary); }
.sa-empty { color: var(--text-tertiary); padding: var(--space-4); text-align: center; }
.sa-form { display: flex; flex-direction: column; gap: var(--space-4); }
.sa-btn { height: 34px; padding: 0 var(--space-4); border-radius: var(--radius-base); border: 1px solid var(--border-base); background: var(--bg-card); color: var(--text-secondary); font-size: var(--font-size-base); cursor: pointer; }
.sa-btn:hover { border-color: var(--border-dark); }
.sa-btn:disabled { opacity: 0.6; cursor: not-allowed; }
</style>
