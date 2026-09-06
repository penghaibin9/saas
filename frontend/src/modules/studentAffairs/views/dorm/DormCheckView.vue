<template>
  <AppPageShell
    title="宿舍检查"
    subtitle="按生效模板逐房检查，照片进入公共文件证据链；异常形成整改，只有高风险问题进入风险处置。"
    role-name="宿管 / 辅导员 / 学工处"
    data-scope-name="宿管限负责楼栋"
    watermark-purpose="宿舍检查登记"
  >
    <template #actions>
      <AppPermissionButton :allowed="canBtn('studentAffairs.dorm.inspection.manage')" code="studentAffairs.dorm.inspection.manage" :loading="actioning" @click="createTask">
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
          <template #cell-type="{ row }"><strong>{{ row.templateName || typeLabel(row.checkType) }}</strong><small class="cell-sub">{{ typeLabel(row.checkType) }} · v{{ row.templateVersion }}</small></template>
          <template #cell-building="{ row }">{{ row.buildingName || '—' }}</template>
          <template #cell-status="{ row }"><AppStatusTag :type="row.pendingRectificationCount ? 'warning' : 'success'" :label="`${statusLabel(row.status)} · ${row.recordCount || 0} 间`" /></template>
          <template #cell-actions="{ row }">
            <div class="sa-actions">
              <AppPermissionButton :allowed="canBtn('studentAffairs.dorm.view')" code="studentAffairs.dorm.view" size="sm" variant="secondary" @click="openTask(row)">记录</AppPermissionButton>
              <AppPermissionButton :allowed="canBtn('studentAffairs.dorm.inspection.manage')" code="studentAffairs.dorm.inspection.manage" size="sm" :loading="actioning" @click="addRecord(row)">录结果</AppPermissionButton>
            </div>
          </template>
        </DataTable>
        <p v-else class="sa-empty">暂无检查任务</p>
      </AppSectionCard>

      <AppSectionCard v-if="curTask" :title="`检查记录 · ${curTaskName}`">
        <DataTable v-if="records.length" :columns="recordColumns" :rows="records" row-key="recordId">
          <template #cell-room="{ row }">{{ row.roomNo || row.roomId || '—' }}</template>
          <template #cell-result="{ row }"><AppStatusTag :type="row.result === 'ABNORMAL' ? 'danger' : 'success'" :label="row.result === 'ABNORMAL' ? '异常' : '正常'" /></template>
          <template #cell-issueType="{ row }"><strong>{{ severityLabel(row.severity) }}</strong><small class="cell-sub">{{ row.score == null ? '未评分' : `${row.score} 分` }}</small></template>
          <template #cell-detail="{ row }">{{ row.detail || '—' }}</template>
          <template #cell-risk="{ row }">
            <a v-if="row.relatedRiskId" class="sa-link" @click="$router.push(`/admin/student-affairs/risk/${row.relatedRiskId}`)">风险 #{{ row.relatedRiskId }} →</a>
            <span v-else class="sa-muted">—</span>
          </template>
        </DataTable>
        <p v-else class="sa-empty">暂无检查记录</p>
      </AppSectionCard>

      <AppSectionCard title="整改与复检">
        <DataTable v-if="rectifications.length" :columns="rectColumns" :rows="rectifications" row-key="rectificationId">
          <template #cell-room="{ row }"><strong>{{ row.buildingName }} · {{ row.roomNo }}室</strong><small class="cell-sub">{{ row.studentName || '房间级整改' }}</small></template>
          <template #cell-issue="{ row }"><AppStatusTag :type="['HIGH','CRITICAL'].includes(row.severity) ? 'danger' : 'warning'" :label="severityLabel(row.severity)" /><small class="cell-sub">{{ row.requirement }}</small></template>
          <template #cell-deadline="{ row }"><span :class="row.overdue ? 'danger-text' : ''">{{ fmt(row.deadlineAt) }}</span></template>
          <template #cell-status="{ row }"><AppStatusTag :type="rectStatusType(row.status)" :label="rectStatusLabel(row.status)" /></template>
          <template #cell-actions="{ row }"><div class="sa-actions"><AppPermissionButton v-if="row.allowedActions?.includes('START')" :allowed="canBtn('studentAffairs.dorm.inspection.manage')" code="studentAffairs.dorm.inspection.manage" size="sm" variant="secondary" :loading="actioning" @click="startRectification(row)">开始整改</AppPermissionButton><AppPermissionButton v-if="row.allowedActions?.includes('SUBMIT')" :allowed="canBtn('studentAffairs.dorm.inspection.manage')" code="studentAffairs.dorm.inspection.manage" size="sm" :loading="actioning" @click="openRectification(row, 'SUBMIT')">提交证据</AppPermissionButton><AppPermissionButton v-if="row.allowedActions?.includes('PASS')" :allowed="canBtn('studentAffairs.dorm.inspection.manage')" code="studentAffairs.dorm.inspection.manage" size="sm" :loading="actioning" @click="openRectification(row, 'PASS')">复检</AppPermissionButton></div></template>
        </DataTable>
        <p v-else class="sa-empty">暂无整改记录</p>
      </AppSectionCard>
    </AppGlobalState>

    <!-- 新建检查任务：原为「任务名→类型码→楼栋 ID」3 连原生弹窗，类型要手打 HYGIENE 之类 -->
    <AppDrawer :visible="taskDlg.visible" title="新建检查任务" mode="modal" size="medium" @close="taskDlg.visible = false">
      <div class="dr-form">
        <AppFormItem label="任务名称" required>
          <AppTextInput v-model="taskDlg.taskName" placeholder="如：11 月宿舍卫生检查" :disabled="actioning" />
        </AppFormItem>
        <AppFormItem label="检查模板" required>
          <AppSelect v-model="taskDlg.templateKey" :options="templateOptions" :disabled="actioning" />
        </AppFormItem>
        <AppFormItem label="检查楼栋" required>
          <AppDormBuildingPicker v-model="taskDlg.buildingId" :options="buildingOptions" placeholder="请选择具体楼栋" :disabled="actioning" @change="taskDlg.floorScope = []" />
        </AppFormItem>
        <AppFormItem label="检查楼层（不选表示整栋）"><div class="floor-grid"><label v-for="floor in taskFloorOptions" :key="floor"><input v-model="taskDlg.floorScope" type="checkbox" :value="floor" /> {{ floor }} 层</label></div></AppFormItem>
        <AppFormItem label="计划检查时间"><input v-model="taskDlg.plannedAt" type="datetime-local" class="sa-native-input" /></AppFormItem>
        <p class="dr-hint">发布时冻结模板版本、评分项、风险阈值与楼层范围，后续配置变化不会改写已发布任务。</p>
        <AppInlineAlert v-if="taskDlg.error" type="danger" :description="taskDlg.error" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="actioning" @click="taskDlg.visible = false">取消</AppButton>
        <AppButton variant="primary" :loading="actioning" @click="submitTask">新建</AppButton>
      </template>
    </AppDrawer>

    <!-- 录检查结果：原为「房间 ID→结果码→异常说明→涉事学生 ID」4 连弹窗，中途取消丢数据、ID 全靠手打 -->
    <AppDrawer :visible="recDlg.visible" :title="`录检查结果 · ${recDlg.taskName}`" mode="modal" size="large" @close="recDlg.visible = false">
      <div class="dr-form">
        <AppFormItem label="楼栋">
          <AppDormBuildingPicker v-model="recDlg.buildingId" :options="buildingOptions" placeholder="不限楼栋"
                     clearable :disabled="actioning || recDlg.buildingLocked" @change="onRecBuildingChange" />
          <p v-if="recDlg.buildingLocked" class="dr-hint">本任务已绑定该楼栋，不可更改。</p>
        </AppFormItem>
        <AppFormItem label="房间">
          <AppDormRoomPicker v-model="recDlg.roomId" :options="roomOptions" :query="{ buildingId: recDlg.buildingId }" clearable :disabled="actioning || !recDlg.buildingId"
                     :placeholder="recDlg.buildingId ? '选择房间（可空）' : '请先选楼栋'" />
        </AppFormItem>
        <AppFormItem label="逐项检查" required><div class="item-list"><div v-for="item in recDlg.itemResults" :key="item.itemCode" class="item-row"><div><strong>{{ item.itemName }}</strong><small>{{ severityLabel(item.severity) }} · 满分 {{ item.maxScore }}</small></div><AppSelect v-model="item.status" :options="ITEM_RESULTS" :disabled="actioning" @change="syncItemScore(item)" /><input v-model.number="item.score" type="number" min="0" :max="item.maxScore" step="0.5" class="score-input" /></div></div></AppFormItem>
        <template v-if="recordAbnormal">
          <AppFormItem :label="`异常说明（≥5 字，${typeLabel(recDlg.checkType)}）`" required>
            <AppTextarea ref="detailInput" v-model="recDlg.detail" :rows="3" :maxlength="500" :disabled="actioning"
                         placeholder="写清问题、处理动作与整改要求" />
            <AppQuickPhrases scene-key="sa.dorm.exception" :group="recDlg.checkType" @pick="onPickDetail" />
          </AppFormItem>
          <AppFormItem label="涉事学生（可空；填写后必须为该房当前住宿学生）">
            <AppStudentPicker v-model="recDlg.studentId"
                              placeholder="按姓名 / 学号搜索" :disabled="actioning" />
          </AppFormItem>
        </template>
        <AppFormItem label="现场照片证据"><FileUploader biz-type="TEMP_PRIVATE" accept="image/*" button-text="上传现场照片" :disabled="actioning" @uploaded="onRecordFileUploaded" @error="onUploadError" /><div v-if="recDlg.files.length" class="file-chips"><span v-for="file in recDlg.files" :key="file.fileId">{{ file.fileName || `文件 #${file.fileId}` }} <button type="button" @click="removeRecordFile(file.fileId)">×</button></span></div><p class="dr-hint">高风险/重大风险异常必须上传照片；文件只保存稳定 ID，不在检查记录存 URL。</p></AppFormItem>
        <AppInlineAlert v-if="recDlg.error" type="danger" :description="recDlg.error" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="actioning" @click="recDlg.visible = false">取消</AppButton>
        <AppButton variant="primary" :loading="actioning" @click="submitRecord">提交</AppButton>
      </template>
    </AppDrawer>

    <AppDrawer :visible="rectDlg.visible" :title="rectDlg.mode === 'SUBMIT' ? '提交整改证据' : '宿舍整改复检'" mode="modal" size="large" @close="rectDlg.visible = false">
      <div class="dr-form" v-if="rectDlg.row"><AppInlineAlert type="info" :title="`${rectDlg.row.buildingName} · ${rectDlg.row.roomNo}室 · ${severityLabel(rectDlg.row.severity)}`" :description="rectDlg.row.requirement" /><AppFormItem v-if="rectDlg.mode !== 'SUBMIT'" label="复检结论" required><AppSelect v-model="rectDlg.action" :options="RECHECK_ACTIONS" :disabled="actioning" /></AppFormItem><AppFormItem :label="rectDlg.mode === 'SUBMIT' ? '整改说明（5-1000字）' : '复检意见（5-1000字）'" required><AppTextarea v-model="rectDlg.note" :rows="4" :maxlength="1000" :disabled="actioning" /></AppFormItem><AppFormItem label="照片证据"><FileUploader biz-type="TEMP_PRIVATE" accept="image/*" button-text="上传照片" :disabled="actioning" @uploaded="onRectFileUploaded" @error="onUploadError" /><div v-if="rectDlg.files.length" class="file-chips"><span v-for="file in rectDlg.files" :key="file.fileId">{{ file.fileName || `文件 #${file.fileId}` }} <button type="button" @click="removeRectFile(file.fileId)">×</button></span></div></AppFormItem><AppInlineAlert v-if="rectDlg.error" type="danger" :description="rectDlg.error" /></div>
      <template #footer><AppButton variant="ghost" :disabled="actioning" @click="rectDlg.visible = false">取消</AppButton><AppButton variant="primary" :loading="actioning" @click="submitRectificationAction">{{ rectDlg.mode === 'SUBMIT' ? '提交复检' : '保存复检结论' }}</AppButton></template>
    </AppDrawer>
  </AppPageShell>
</template>

<script>
import {
  AppFormItem, AppGlobalState, AppInlineAlert, AppPageShell, AppPermissionButton,
  AppQuickPhrases, AppSectionCard, AppSelect, AppStatusTag, AppStudentPicker, AppDormBuildingPicker, AppDormRoomPicker, AppTextInput, AppTextarea
} from '@/components/common'
import { AppButton, AppDrawer } from '@/components/ui'
import { DataTable } from '@/components/business'
import FileUploader from '@/components/file/FileUploader.vue'
import { insertAtCursor, applyInsertion } from '@/utils/insertAtCursor'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairsB.api'
import { canCode } from '@/modules/studentAffairs/composables/permission'


const TASK_COLUMNS = [
  { key: 'name', title: '任务' },
  { key: 'type', title: '类型' },
  { key: 'building', title: '楼栋' },
  { key: 'status', title: '状态' },
  { key: 'actions', title: '操作', align: 'right', width: '180px' }
]
const RECT_COLUMNS = [
  { key: 'room', title: '楼栋 / 房间 / 责任人' },
  { key: 'issue', title: '整改要求' },
  { key: 'deadline', title: '期限' },
  { key: 'status', title: '状态' },
  { key: 'actions', title: '操作', align: 'right', width: '240px' }
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
  { value: 'NIGHT_ABSENCE', label: '夜不归宿' },
  { value: 'FIRE_SAFETY', label: '消防安全' },
  { value: 'FACILITY', label: '设施设备' },
  { value: 'OTHER', label: '其他' }
]
const ITEM_RESULTS = [
  { value: 'PASS', label: '正常' },
  { value: 'FAIL', label: '异常' },
  { value: 'NA', label: '不适用' }
]
const RECHECK_ACTIONS = [
  { value: 'PASS', label: '通过并关闭' },
  { value: 'RETURN', label: '退回继续整改' },
  { value: 'ESCALATE', label: '升级处置（仅高危）' }
]
let requestSequence = 0

function requestId(prefix) {
  const token = globalThis.crypto?.randomUUID?.() || `${Date.now()}-${++requestSequence}`
  return `${prefix}-${token}`.slice(0, 100)
}

export default {
  name: 'DormCheckView',
  props: { ctx: { type: Object, default: null } },
  components: {
    AppButton, AppDrawer, FileUploader, AppFormItem, AppGlobalState, AppInlineAlert, AppPageShell, AppPermissionButton,
    AppQuickPhrases, AppSectionCard, AppSelect, AppStatusTag, AppStudentPicker, AppDormBuildingPicker, AppDormRoomPicker, AppTextInput, AppTextarea, DataTable
  },
  data() {
    return {
      taskColumns: TASK_COLUMNS,
      recordColumns: RECORD_COLUMNS,
      rectColumns: RECT_COLUMNS,
      loading: true, actioning: false, errorMessage: '',
      tasks: [], curTask: '', curTaskName: '', curTaskType: '', records: [], rectifications: [], policy: { items: [], riskSeverities: [], evidenceRequiredSeverities: [] },
      buildings: [], rooms: [],
      taskDlg: { visible: false, taskName: '', templateKey: '', buildingId: '', floorScope: [], plannedAt: '', error: '' },
      recDlg: {
        visible: false, taskId: '', taskName: '', checkType: '', buildingId: '', buildingLocked: false,
        roomId: '', itemResults: [], detail: '', studentId: '', files: [], error: ''
      },
      rectDlg: { visible: false, row: null, mode: '', action: 'PASS', note: '', files: [], error: '' }
    }
  },
  computed: {
    pageState() { return this.loading ? 'loading' : (this.errorMessage ? 'error' : 'ready') },
    CHECK_TYPES: () => CHECK_TYPES,
    ITEM_RESULTS: () => ITEM_RESULTS,
    RECHECK_ACTIONS: () => RECHECK_ACTIONS,
    templateOptions() { return (this.policy.items || []).map((item) => ({ value: item.key, label: `${item.name} · ${this.typeLabel(item.checkType)} · v${item.version}` })) },
    taskFloorOptions() { const row = this.buildings.find((item) => String(item.buildingId) === String(this.taskDlg.buildingId)); return Array.from({ length: Number(row?.floorCount || 0) }, (_, i) => i + 1) },
    buildingOptions() {
      return this.buildings.map((b) => ({ value: String(b.buildingId), label: b.buildingName || `楼栋 #${b.buildingId}` }))
    },
    roomOptions() {
      return this.rooms.map((r) => ({ value: String(r.roomId), label: r.roomNo || `房间 #${r.roomId}` }))
    },
    recordAbnormal() { return this.recDlg.itemResults.some((item) => item.status === 'FAIL') }
  },
  mounted() { this.load(); this.loadBuildings() },
  methods: {
    canBtn(code) { return canCode(this.ctx, code) },
    async load() {
      this.loading = true; this.errorMessage = ''
      try {
        const [taskRes, policyRes, rectRes] = await Promise.all([
          studentAffairsApi.listDormCheckTasks({ pageSize: 100 }),
          studentAffairsApi.getDormInspectionTemplates(),
          studentAffairsApi.listDormRectifications({ pageSize: 200 })
        ])
        this.tasks = taskRes.data.items || []; this.policy = policyRes.data || this.policy; this.rectifications = rectRes.data.items || []
      }
      catch (e) { this.errorMessage = e.message || '检查任务加载失败' } finally { this.loading = false }
    },
    async loadBuildings() {
      // 楼栋列表只用于填下拉；失败不阻断主流程，退化为「不限楼栋」。
      try { this.buildings = (await studentAffairsApi.listDormBuildings({ pageSize: 200 })).data.items || [] }
      catch { this.buildings = [] }
    },
    async loadRooms(buildingId) {
      if (!buildingId) { this.rooms = []; return }
      // 待服务端全量统计：下拉列表仅加载 API 单页上限。
      try { this.rooms = (await studentAffairsApi.listDormRooms(buildingId, { pageSize: 200 })).data.items || [] }
      catch { this.rooms = [] }
    },
    async openTask(t) {
      this.curTask = t.taskId; this.curTaskName = t.taskName; this.curTaskType = t.checkType
      try { this.records = (await studentAffairsApi.listDormCheckRecords(t.taskId)).data.items || [] }
      catch (e) { this.errorMessage = e.message }
    },
    /* ── 新建任务 ── */
    createTask() {
      this.taskDlg = { visible: true, taskName: '', templateKey: this.policy.items?.[0]?.key || '', buildingId: '', floorScope: [], plannedAt: '', error: '' }
    },
    async submitTask() {
      const d = this.taskDlg
      if (d.taskName.trim().length < 2 || !d.templateKey || !d.buildingId) { d.error = '请填写至少2字任务名称，并选择检查模板和具体楼栋'; return }
      const template = this.policy.items.find((item) => item.key === d.templateKey)
      d.error = ''
      const ok = await this.runAction(() => studentAffairsApi.createDormCheckTask({
        taskName: d.taskName.trim(), checkType: template?.checkType, templateKey: d.templateKey,
        templateVersion: template?.version, buildingId: d.buildingId, floorScope: d.floorScope,
        plannedAt: d.plannedAt || null, clientRequestId: requestId('dorm-task')
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
        itemResults: (t.templateItems || []).map((item) => ({ itemCode: item.code, itemName: item.name, status: 'PASS', score: item.maxScore, maxScore: item.maxScore, severity: item.severity })),
        detail: '', studentId: '', files: [], error: ''
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
    syncItemScore(item) { item.score = item.status === 'PASS' ? item.maxScore : 0 },
    onRecordFileUploaded(file) { const fileId = String(file?.fileId || file?.id || ''); if (fileId && !this.recDlg.files.some((item) => item.fileId === fileId)) this.recDlg.files.push({ fileId, fileName: file.fileName || file.name || '' }) },
    removeRecordFile(fileId) { this.recDlg.files = this.recDlg.files.filter((item) => item.fileId !== fileId) },
    onRectFileUploaded(file) { const fileId = String(file?.fileId || file?.id || ''); if (fileId && !this.rectDlg.files.some((item) => item.fileId === fileId)) this.rectDlg.files.push({ fileId, fileName: file.fileName || file.name || '' }) },
    removeRectFile(fileId) { this.rectDlg.files = this.rectDlg.files.filter((item) => item.fileId !== fileId) },
    onUploadError(error) { this.errorMessage = error?.message || '照片上传失败' },
    async submitRecord() {
      const d = this.recDlg
      if (!d.roomId || !d.itemResults.length) { d.error = '请选择房间并完成逐项检查'; return }
      const body = { roomId: d.roomId, result: this.recordAbnormal ? 'ABNORMAL' : 'NORMAL', issueType: d.checkType, itemResults: d.itemResults.map(({ itemCode, status, score }) => ({ itemCode, status, score })), fileIds: d.files.map((file) => file.fileId), clientRequestId: requestId('dorm-record') }
      if (this.recordAbnormal) {
        if (d.detail.trim().length < 5) { d.error = '异常说明不少于 5 字'; return }
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
    async startRectification(row) { await this.runAction(() => studentAffairsApi.startDormRectification(row.rectificationId, row.version)) },
    openRectification(row, mode) { this.rectDlg = { visible: true, row, mode, action: mode === 'SUBMIT' ? '' : 'PASS', note: '', files: [], error: '' } },
    async submitRectificationAction() {
      const d = this.rectDlg
      if (d.note.trim().length < 5) { d.error = '说明不少于5字'; return }
      if (d.mode === 'SUBMIT' && !d.files.length) { d.error = '请上传整改照片证据'; return }
      if (d.mode !== 'SUBMIT' && d.action === 'PASS' && ['HIGH', 'CRITICAL'].includes(d.row.severity) && !d.files.length) { d.error = '高风险复检通过必须上传现场照片'; return }
      d.error = ''
      const body = { expectedVersion: d.row.version, note: d.note.trim(), fileIds: d.files.map((file) => file.fileId) }
      const task = d.mode === 'SUBMIT'
        ? () => studentAffairsApi.submitDormRectification(d.row.rectificationId, { ...body, clientRequestId: requestId('dorm-rectify') })
        : () => studentAffairsApi.recheckDormRectification(d.row.rectificationId, { ...body, action: d.action })
      const ok = await this.runAction(task)
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
    fmt(value) { return String(value || '').slice(0, 16).replace('T', ' ') || '—' },
    typeLabel(t) { return ({ HYGIENE: '卫生', SAFETY: '安全', CONTRABAND: '违禁品', NIGHT_ABSENCE: '夜不归宿', FIRE_SAFETY: '消防安全', FACILITY: '设施设备', OTHER: '其他' })[t] || (t ? '类型待确认' : '—') },
    severityLabel(value) { return ({ NONE: '正常', LOW: '低', MEDIUM: '中', HIGH: '高风险', CRITICAL: '重大风险' })[value] || (value ? '待确认' : '—') },
    rectStatusLabel(value) { return ({ OPEN: '待整改', RECTIFYING: '整改中', WAITING_RECHECK: '待复检', CLOSED: '已关闭', ESCALATED: '已升级' })[value] || (value ? '待确认' : '—') },
    rectStatusType(value) { return ({ OPEN: 'warning', RECTIFYING: 'processing', WAITING_RECHECK: 'warning', CLOSED: 'success', ESCALATED: 'danger' })[value] || 'default' },
    /** 检查任务状态：取值见 affairs_dorm_service.create（RUNNING）与模型默认值（DRAFT）；
     *  未收录的取值原样显示，避免把后端新增状态误显示成空白 */
    statusLabel(s) { return ({ DRAFT: '草稿', RUNNING: '进行中', DONE: '已完成', CLOSED: '已结束' })[s] || (s ? '状态待确认' : '—') }
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
.cell-sub { display:block;margin-top:3px;color:var(--text-tertiary);font-size:12px }.danger-text { color:#dc2626;font-weight:650 }.sa-native-input { width:100%;min-height:38px;box-sizing:border-box;border:1px solid var(--border-base);border-radius:8px;padding:7px 10px }.floor-grid { display:flex;gap:12px;flex-wrap:wrap }.floor-grid label { padding:7px 10px;border:1px solid var(--border-base);border-radius:8px }.item-list { display:grid;gap:8px }.item-row { display:grid;grid-template-columns:minmax(180px,1fr) 150px 90px;gap:10px;align-items:center;padding:10px;border:1px solid var(--border-base);border-radius:9px }.item-row small { display:block;margin-top:3px;color:var(--text-tertiary) }.score-input { width:100%;min-height:36px;box-sizing:border-box;border:1px solid var(--border-base);border-radius:8px;padding:6px }.file-chips { display:flex;gap:8px;flex-wrap:wrap;margin-top:8px }.file-chips span { padding:6px 8px;border-radius:8px;background:#eff6ff;color:#1d4ed8;font-size:12px }.file-chips button { border:0;background:transparent;color:#64748b;cursor:pointer }
@media(max-width:760px){.item-row{grid-template-columns:1fr}.score-input{width:100%}}
@import '@/styles/module-page.css';
</style>
