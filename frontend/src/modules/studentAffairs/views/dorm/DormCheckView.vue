<template>
  <AppPageShell
    title="宿舍检查"
    subtitle="卫生/安全/违禁/夜不归宿检查任务与记录；异常须绑真实涉事学生（夜不归宿必填），自动进入风险处置。"
    role-name="宿管 / 辅导员 / 学工处"
    data-scope-name="宿管限负责楼栋"
    watermark-purpose="宿舍检查登记"
  >
    <template #actions>
      <AppPermissionButton code="studentAffairs.dorm.inspection.manage" :loading="actioning" @click="createTask">
        新建检查任务
      </AppPermissionButton>
    </template>

    <AppGlobalState :state="pageState" :description="errorMessage" loading-text="正在加载检查任务..." @retry="load"
                    @back="$router.push('/admin/student-affairs/dashboard')">
      <AppSectionCard title="检查任务">
        <DataTable
          v-if="tasks.length"
          :columns="taskColumns"
          :rows="tasks"
          row-key="taskId"
          :row-class="(row) => (row.taskId === curTask ? 'sa-sel' : '')"
        >
          <template #cell-name="{ row }"><span class="mp-cell-main">{{ row.taskName }}</span></template>
          <template #cell-type="{ row }">{{ typeLabel(row.checkType) }}</template>
          <template #cell-building="{ row }">{{ row.buildingName || '—' }}</template>
          <template #cell-status="{ row }">{{ row.status }}</template>
          <template #cell-actions="{ row }">
            <div class="sa-actions">
              <AppPermissionButton code="studentAffairs.dorm.view" size="sm" variant="secondary" @click="openTask(row)">记录</AppPermissionButton>
              <AppPermissionButton code="studentAffairs.dorm.inspection.manage" size="sm" :loading="actioning" @click="addRecord(row)">录结果</AppPermissionButton>
            </div>
          </template>
        </DataTable>
        <p v-else class="sa-empty">暂无检查任务</p>
      </AppSectionCard>

      <AppSectionCard v-if="curTask" :title="`检查记录 · ${curTaskName}`">
        <DataTable v-if="records.length" :columns="recordColumns" :rows="records" row-key="recordId">
          <template #cell-room="{ row }">{{ row.roomNo || row.roomId || '—' }}</template>
          <template #cell-result="{ row }"><AppStatusTag :type="row.result === 'ABNORMAL' ? 'danger' : 'success'" :label="row.result === 'ABNORMAL' ? '异常' : '正常'" /></template>
          <template #cell-issueType="{ row }">{{ row.issueType || '—' }}</template>
          <template #cell-detail="{ row }">{{ row.detail || '—' }}</template>
          <template #cell-risk="{ row }">
            <a v-if="row.relatedRiskId" class="sa-link" @click="$router.push(`/admin/student-affairs/risk/${row.relatedRiskId}`)">风险 #{{ row.relatedRiskId }} →</a>
            <span v-else class="sa-muted">—</span>
          </template>
        </DataTable>
        <p v-else class="sa-empty">暂无检查记录</p>
      </AppSectionCard>
    </AppGlobalState>

    <!-- 新建检查任务：原为「任务名→类型码→楼栋 ID」3 连原生弹窗，类型要手打 HYGIENE 之类 -->
    <AppDrawer :visible="taskDlg.visible" title="新建检查任务" @close="taskDlg.visible = false">
      <div class="dr-form">
        <AppFormItem label="任务名称" required>
          <AppTextInput v-model="taskDlg.taskName" placeholder="如：11 月宿舍卫生检查" :disabled="actioning" />
        </AppFormItem>
        <AppFormItem label="检查类型" required>
          <AppSelect v-model="taskDlg.checkType" :options="CHECK_TYPES" :disabled="actioning" />
        </AppFormItem>
        <AppFormItem label="检查楼栋">
          <AppSelect v-model="taskDlg.buildingId" :options="buildingOptions" placeholder="不限楼栋（全校）" clearable :disabled="actioning" />
        </AppFormItem>
        <p class="dr-hint">绑定楼栋后，录结果时可直接下拉选房间；不绑则录结果时再选楼栋。</p>
        <AppInlineAlert v-if="taskDlg.error" type="danger" :description="taskDlg.error" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="actioning" @click="taskDlg.visible = false">取消</AppButton>
        <AppButton variant="primary" :loading="actioning" @click="submitTask">新建</AppButton>
      </template>
    </AppDrawer>

    <!-- 录检查结果：原为「房间 ID→结果码→异常说明→涉事学生 ID」4 连弹窗，中途取消丢数据、ID 全靠手打 -->
    <AppDrawer :visible="recDlg.visible" :title="`录检查结果 · ${recDlg.taskName}`" @close="recDlg.visible = false">
      <div class="dr-form">
        <AppFormItem label="楼栋">
          <AppSelect v-model="recDlg.buildingId" :options="buildingOptions" placeholder="不限楼栋"
                     clearable :disabled="actioning || recDlg.buildingLocked" @change="onRecBuildingChange" />
          <p v-if="recDlg.buildingLocked" class="dr-hint">本任务已绑定该楼栋，不可更改。</p>
        </AppFormItem>
        <AppFormItem label="房间">
          <AppSelect v-model="recDlg.roomId" :options="roomOptions" clearable :disabled="actioning || !recDlg.buildingId"
                     :placeholder="recDlg.buildingId ? '选择房间（可空）' : '请先选楼栋'" />
        </AppFormItem>
        <AppFormItem label="检查结果" required>
          <AppSelect v-model="recDlg.result" :options="CHECK_RESULTS" :disabled="actioning" />
        </AppFormItem>
        <template v-if="recDlg.result === 'ABNORMAL'">
          <AppFormItem :label="`异常说明（≥5 字，${typeLabel(recDlg.checkType)}）`" required>
            <AppTextarea ref="detailInput" v-model="recDlg.detail" :rows="3" :maxlength="500" :disabled="actioning"
                         placeholder="写清问题、处理动作与整改要求" />
            <AppQuickPhrases scene-key="sa.dorm.exception" :group="recDlg.checkType" @pick="onPickDetail" />
          </AppFormItem>
          <AppFormItem :label="needStudent ? '涉事学生（夜不归宿必填）' : '涉事学生（可空；填则自动建风险单）'" :required="needStudent">
            <AppStudentPicker v-model="recDlg.studentId" :remote-search="searchStudents"
                              placeholder="按姓名 / 学号搜索" :disabled="actioning" />
          </AppFormItem>
        </template>
        <AppInlineAlert v-if="recDlg.error" type="danger" :description="recDlg.error" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="actioning" @click="recDlg.visible = false">取消</AppButton>
        <AppButton variant="primary" :loading="actioning" @click="submitRecord">提交</AppButton>
      </template>
    </AppDrawer>
  </AppPageShell>
</template>

<script>
import {
  AppFormItem, AppGlobalState, AppInlineAlert, AppPageShell, AppPermissionButton,
  AppQuickPhrases, AppSectionCard, AppSelect, AppStatusTag, AppStudentPicker, AppTextInput, AppTextarea
} from '@/components/common'
import { AppButton, AppDrawer } from '@/components/ui'
import { DataTable } from '@/components/business'
import { insertAtCursor, applyInsertion } from '@/utils/insertAtCursor'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairsB.api'

const TASK_COLUMNS = [
  { key: 'name', title: '任务' },
  { key: 'type', title: '类型' },
  { key: 'building', title: '楼栋' },
  { key: 'status', title: '状态' },
  { key: 'actions', title: '操作', align: 'right', width: '180px' }
]
const RECORD_COLUMNS = [
  { key: 'room', title: '房间' },
  { key: 'result', title: '结果' },
  { key: 'issueType', title: '问题' },
  { key: 'detail', title: '说明' },
  { key: 'risk', title: '关联风险' }
]

/** 与后端 checkType 取值一一对应；也是 sa.dorm.exception 词库的分组键。 */
const CHECK_TYPES = [
  { value: 'HYGIENE', label: '卫生' },
  { value: 'SAFETY', label: '安全' },
  { value: 'CONTRABAND', label: '违禁品' },
  { value: 'NIGHT_ABSENCE', label: '夜不归宿' }
]
const CHECK_RESULTS = [
  { value: 'NORMAL', label: '正常' },
  { value: 'ABNORMAL', label: '异常（进入风险处置）' }
]

export default {
  name: 'DormCheckView',
  components: {
    AppButton, AppDrawer, AppFormItem, AppGlobalState, AppInlineAlert, AppPageShell, AppPermissionButton,
    AppQuickPhrases, AppSectionCard, AppSelect, AppStatusTag, AppStudentPicker, AppTextInput, AppTextarea, DataTable
  },
  data() {
    return {
      taskColumns: TASK_COLUMNS,
      recordColumns: RECORD_COLUMNS,
      loading: true, actioning: false, errorMessage: '',
      tasks: [], curTask: '', curTaskName: '', curTaskType: '', records: [],
      buildings: [], rooms: [],
      taskDlg: { visible: false, taskName: '', checkType: 'HYGIENE', buildingId: '', error: '' },
      recDlg: {
        visible: false, taskId: '', taskName: '', checkType: '', buildingId: '', buildingLocked: false,
        roomId: '', result: 'ABNORMAL', detail: '', studentId: '', error: ''
      }
    }
  },
  computed: {
    pageState() { return this.loading ? 'loading' : (this.errorMessage ? 'error' : 'ready') },
    CHECK_TYPES: () => CHECK_TYPES,
    CHECK_RESULTS: () => CHECK_RESULTS,
    buildingOptions() {
      return this.buildings.map((b) => ({ value: String(b.buildingId), label: b.buildingName || `楼栋 #${b.buildingId}` }))
    },
    roomOptions() {
      return this.rooms.map((r) => ({ value: String(r.roomId), label: r.roomNo || `房间 #${r.roomId}` }))
    },
    needStudent() { return this.recDlg.checkType === 'NIGHT_ABSENCE' }
  },
  mounted() { this.load(); this.loadBuildings() },
  methods: {
    async load() {
      this.loading = true; this.errorMessage = ''
      try { this.tasks = (await studentAffairsApi.listDormCheckTasks({ pageSize: 100 })).data.items || [] }
      catch (e) { this.errorMessage = e.message || '检查任务加载失败' } finally { this.loading = false }
    },
    async loadBuildings() {
      // 楼栋列表只用于填下拉；失败不阻断主流程，退化为「不限楼栋」。
      try { this.buildings = (await studentAffairsApi.listDormBuildings({ pageSize: 200 })).data.items || [] }
      catch { this.buildings = [] }
    },
    async loadRooms(buildingId) {
      if (!buildingId) { this.rooms = []; return }
      try { this.rooms = (await studentAffairsApi.listDormRooms(buildingId, { pageSize: 500 })).data.items || [] }
      catch { this.rooms = [] }
    },
    async openTask(t) {
      this.curTask = t.taskId; this.curTaskName = t.taskName; this.curTaskType = t.checkType
      try { this.records = (await studentAffairsApi.listDormCheckRecords(t.taskId)).data.items || [] }
      catch (e) { this.errorMessage = e.message }
    },
    searchStudents(keyword) { return studentAffairsApi.searchStudents(keyword) },
    /* ── 新建任务 ── */
    createTask() {
      this.taskDlg = { visible: true, taskName: '', checkType: 'HYGIENE', buildingId: '', error: '' }
    },
    async submitTask() {
      const d = this.taskDlg
      if (!d.taskName.trim()) { d.error = '请填写任务名称'; return }
      d.error = ''
      const ok = await this.runAction(() => studentAffairsApi.createDormCheckTask({
        taskName: d.taskName.trim(), checkType: d.checkType, buildingId: d.buildingId || null
      }))
      if (ok) d.visible = false
      else d.error = this.errorMessage
    },
    /* ── 录结果 ── */
    addRecord(t) {
      const bound = t.buildingId ? String(t.buildingId) : ''
      this.recDlg = {
        visible: true, taskId: t.taskId, taskName: t.taskName, checkType: t.checkType,
        buildingId: bound, buildingLocked: !!bound, roomId: '', result: 'ABNORMAL',
        detail: '', studentId: '', error: ''
      }
      this.loadRooms(bound)
    },
    onRecBuildingChange() { this.recDlg.roomId = ''; this.loadRooms(this.recDlg.buildingId) },
    onPickDetail(text) {
      const el = this.$refs.detailInput && this.$refs.detailInput.$refs.el
      if (!el) { this.recDlg.detail += text; return }
      const r = insertAtCursor(el, this.recDlg.detail, text)
      this.recDlg.detail = r.value
      this.$nextTick(() => applyInsertion(el, r.selStart, r.selEnd))
    },
    async submitRecord() {
      const d = this.recDlg
      const body = { roomId: d.roomId || null, result: d.result, issueType: d.checkType }
      if (d.result === 'ABNORMAL') {
        if (d.detail.trim().length < 5) { d.error = '异常说明不少于 5 字'; return }
        if (this.needStudent && !d.studentId) { d.error = '夜不归宿须指定涉事学生'; return }
        body.detail = d.detail.trim()
        if (d.studentId) body.studentId = d.studentId
      }
      d.error = ''
      const task = this.tasks.find((t) => t.taskId === d.taskId)
      const ok = await this.runAction(async () => {
        await studentAffairsApi.submitDormCheckRecord(d.taskId, body)
        if (this.curTask && task) await this.openTask(task)
      })
      if (ok) d.visible = false
      else d.error = this.errorMessage
    },
    /** @returns {boolean} 是否成功；失败时保留弹窗与已填内容，不让人重录一遍。 */
    async runAction(fn) {
      this.actioning = true; this.errorMessage = ''
      try { await fn(); await this.load(); return true }
      catch (e) { this.errorMessage = e.message || '操作失败'; return false }
      finally { this.actioning = false }
    },
    typeLabel(t) { return ({ HYGIENE: '卫生', SAFETY: '安全', CONTRABAND: '违禁品', NIGHT_ABSENCE: '夜不归宿' })[t] || t }
  }
}
</script>

<style scoped>
.sa-actions { display: flex; flex-wrap: wrap; gap: var(--space-2); }
/* 选中任务高亮：类由 DataTable 的 row-class 挂在子组件内部 <tr> 上，父级 scoped 样式须 :deep() 穿透 */
:deep(.dt__tr.sa-sel) .dt__td { background: var(--primary-50, var(--bg-subtle)); }
.sa-link { color: var(--primary-600); cursor: pointer; }
.sa-muted { color: var(--text-tertiary); }
.sa-empty { color: var(--text-tertiary); padding: var(--space-4); text-align: center; }
.dr-form { display: flex; flex-direction: column; gap: var(--space-4); }
.dr-hint { margin: var(--space-1) 0 0; color: var(--text-tertiary); font-size: var(--font-size-sm); }
@import '@/styles/module-page.css';
</style>
