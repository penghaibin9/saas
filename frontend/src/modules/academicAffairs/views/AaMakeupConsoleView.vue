<template>
  <ModulePageShell
    title="补考重修缓考免修 · 教务处控制台"
    :subtitle="'四条线：补考批次 · 重修审批 · 免修三级审批 · 缓考合流'"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="aamk-tabs">
      <button v-for="t in tabs" :key="t.key" :class="['aamk-tab', { 'is-active': tab === t.key }]" @click="switchTab(t.key)">{{ t.label }}</button>
    </div>

    <ErrorState v-if="error" :description="error" @retry="reload" />
    <LoadingState v-else-if="loading" />
    <template v-else>
      <!-- 补考批次 -->
      <div v-if="tab === 'makeup'" class="mp-stack">
        <div class="aamk-bar">
          <AppButton variant="primary" size="small" @click="openCreateBatch">新建补考批次</AppButton>
        </div>
        <EmptyState v-if="!rows.length" title="暂无补考批次" description="从不及格名单建批次" />
        <DataTable v-else :columns="batchColumns" :rows="rows" row-key="batchId">
          <template #cell-status="{ row }"><StatusTag :type="mbType(row.status)" :label="mbLabel(row.status)" dot /></template>
          <template #cell-ops="{ row }">
            <button v-if="row.status === 'ARRANGED'" class="mp-link" @click="act('publishBatch', row.batchId, '发布')">发布</button>
            <button v-if="row.status === 'SCORING'" class="mp-link" @click="act('collegeReview', row.batchId, '学院审核')">学院审核</button>
            <button v-if="row.status === 'REVIEWED'" class="mp-link" @click="act('finishBatch', row.batchId, '教务发布回写')">教务发布回写</button>
            <button v-if="row.status !== 'DRAFT' && row.status !== 'ARRANGED'" class="mp-link" @click="printBatch(row.batchId)">打印安排表</button>
          </template>
        </DataTable>
      </div>

      <!-- 重修审批 -->
      <div v-else-if="tab === 'retake'" class="mp-stack">
        <EmptyState v-if="!rows.length" title="暂无重修申请" description="学生报名后在此审批" />
        <DataTable v-else :columns="retakeColumns" :rows="rows" row-key="applyId">
          <template #cell-student="{ row }">{{ row.studentName }}（{{ row.courseName }}·第{{ row.retakeCount }}次）</template>
          <template #cell-status="{ row }"><StatusTag :type="rtType(row.status)" :label="row.status" dot /></template>
          <template #cell-ops="{ row }">
            <button v-if="row.status === 'SUBMITTED'" class="mp-link" @click="review('retakeReview', row.applyId, 'APPROVE')">通过</button>
            <button v-if="row.status === 'SUBMITTED'" class="mp-link is-danger" @click="reject('retakeReview', row.applyId)">驳回</button>
            <button v-if="row.status === 'APPROVED'" class="mp-link" @click="enrollRetake(row.applyId)">编入跟班</button>
          </template>
        </DataTable>
      </div>

      <!-- 免修审批 -->
      <div v-else-if="tab === 'exemption'" class="mp-stack">
        <EmptyState v-if="!rows.length" title="暂无免修申请" description="学生申请后三级审批" />
        <DataTable v-else :columns="exemptionColumns" :rows="rows" row-key="exemptionId">
          <template #cell-student="{ row }">{{ row.studentName }}（{{ row.courseName }}）</template>
          <template #cell-status="{ row }"><StatusTag :type="exType(row.status)" :label="row.status" dot /></template>
          <template #cell-ops="{ row }">
            <button v-if="canReviewEx(row.status)" class="mp-link" @click="review('exemptionReview', row.exemptionId, 'APPROVE')">通过</button>
            <button v-if="canReviewEx(row.status)" class="mp-link" @click="returnEx(row.exemptionId)">退回</button>
            <button v-if="canReviewEx(row.status)" class="mp-link is-danger" @click="reject('exemptionReview', row.exemptionId)">驳回</button>
          </template>
        </DataTable>
      </div>

      <!-- 毕业清考 -->
      <div v-else-if="tab === 'clearance'" class="mp-stack">
        <div class="aamk-bar">
          <AppButton variant="primary" size="small" @click="openCreateClearance">新建清考批次</AppButton>
        </div>
        <AppInlineAlert type="info" description="毕业清考=应届生对「补考/重修后最优成绩仍不及格」课程的最后考核机会；名单自动圈定，通过按 60 分记（CAP60），回写成绩后可重跑毕业预审。" />
        <EmptyState v-if="!rows.length" title="暂无清考批次" description="为毕业年级新建清考批次并自动圈定名单" />
        <DataTable v-else :columns="clearanceColumns" :rows="rows" row-key="batchId">
          <template #cell-grades="{ row }">{{ (row.targetGrades || []).join('、') || '—' }}</template>
          <template #cell-status="{ row }"><StatusTag :type="mbType(row.status)" :label="mbLabel(row.status)" dot /></template>
          <template #cell-ops="{ row }">
            <button v-if="['DRAFT','ARRANGED'].includes(row.status)" class="mp-link" @click="scanClearance(row, true)">预览名单</button>
            <button v-if="['DRAFT','ARRANGED'].includes(row.status)" class="mp-link" @click="scanClearance(row, false)">圈定名单</button>
            <button class="mp-link" @click="openClearanceRecords(row)">名单/录分</button>
            <button v-if="row.status === 'ARRANGED'" class="mp-link" @click="act('publishBatch', row.batchId, '发布清考')">发布</button>
            <button v-if="row.status === 'SCORING'" class="mp-link" @click="act('collegeReview', row.batchId, '学院审核')">学院审核</button>
            <button v-if="row.status === 'REVIEWED'" class="mp-link" @click="act('finishBatch', row.batchId, '教务发布回写(source=CLEARANCE)')">教务发布回写</button>
          </template>
        </DataTable>
      </div>

      <!-- 缓考合流 -->
      <div v-else class="mp-stack">
        <EmptyState v-if="!rows.length" title="暂无缓考 APPROVED 学生" description="考务包审批通过的缓考学生在此并入补考批次" />
        <DataTable v-else :columns="poolColumns" :rows="rows" row-key="deferId">
          <template #cell-student="{ row }">{{ row.studentName }}（{{ row.courseName }}）</template>
          <template #cell-ops="{ row }"><button class="mp-link" @click="openMerge(row)">并入补考批次</button></template>
        </DataTable>
      </div>
    </template>

    <AppDrawer :visible="batchVisible" title="新建补考批次" mode="modal" size="medium" @close="batchVisible = false">
      <div class="aamk-form">
        <AppFormItem label="批次名称" required><AppTextInput v-model="batchForm.batchName" placeholder="如 2024秋补考" :disabled="saving" /></AppFormItem>
        <AppFormItem label="学期"><AppTermCodePicker v-model="batchForm.termCode" :disabled="saving" /></AppFormItem>
        <AppInlineAlert v-if="formError" type="danger" :description="formError" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="saving" @click="batchVisible = false">取消</AppButton>
        <AppButton variant="primary" :loading="saving" @click="submitBatch">创建</AppButton>
      </template>
    </AppDrawer>

    <AppDrawer :visible="mergeVisible" title="并入补考批次" mode="modal" size="small" @close="mergeVisible = false">
      <div class="aamk-form">
        <AppFormItem label="目标补考批次" required><AppMakeupBatchPicker v-model="mergeBatchId" :disabled="saving" /></AppFormItem>
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="saving" @click="mergeVisible = false">取消</AppButton>
        <AppButton variant="primary" :loading="saving" @click="submitMerge">并入</AppButton>
      </template>
    </AppDrawer>

    <!-- 建清考批次 -->
    <AppDrawer :visible="clearanceVisible" title="新建毕业清考批次" mode="modal" size="medium" @close="clearanceVisible = false">
      <div class="aamk-form">
        <AppFormItem label="批次名称" required><AppTextInput v-model="clearanceForm.batchName" placeholder="如 2022届毕业清考" :disabled="saving" /></AppFormItem>
        <AppFormItem label="限定毕业年级" required><AppTextInput v-model="clearanceForm.grades" placeholder="逗号分隔，如 2022 或 2021,2022" :disabled="saving" /></AppFormItem>
        <AppFormItem label="学期"><AppTermCodePicker v-model="clearanceForm.termCode" :disabled="saving" /></AppFormItem>
        <AppInlineAlert v-if="clearanceError" type="danger" :description="clearanceError" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="saving" @click="clearanceVisible = false">取消</AppButton>
        <AppButton variant="primary" :loading="saving" @click="submitClearance">创建</AppButton>
      </template>
    </AppDrawer>

    <!-- 清考名单/录分 -->
    <AppDrawer :visible="crVisible" :title="'清考名单 · ' + (crBatch ? crBatch.batchName : '')" mode="modal" size="xlarge" @close="crVisible = false">
      <EmptyState v-if="!crRows.length" title="暂无名单" description="先执行「圈定名单」自动捞取未通过课程" />
      <DataTable v-else :columns="crColumns" :rows="crRows" row-key="makeupId">
        <template #cell-student="{ row }">{{ row.studentName }}（{{ row.studentNo }}）</template>
        <template #cell-course="{ row }">{{ row.courseName }}<span class="mp-cell-sub">（原 {{ row.originScore != null ? row.originScore : '—' }} 分）</span></template>
        <template #cell-score="{ row }">
          <span v-if="row.status === 'SCORED'">{{ row.finalScore }}</span>
          <AppNumberInput
            v-else-if="crBatch && ['PUBLISHED','SCORING'].includes(crBatch.status)"
            v-model="crScores[row.makeupId]"
            class="aamk-score-input"
            :min="0"
            :max="100"
            :controls="false"
            size="compact"
            placeholder="0-100"
          />
          <span v-else>—</span>
        </template>
        <template #cell-ops="{ row }">
          <button v-if="row.status !== 'SCORED' && crBatch && ['PUBLISHED','SCORING'].includes(crBatch.status)"
                  class="mp-link" @click="submitClearanceScore(row)">录分</button>
        </template>
      </DataTable>
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
/** 补考重修缓考免修 · 教务处控制台（/admin/academic-affairs/makeup）：四条线 tab 管理。 */
import { ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton, AppDrawer } from '@/components/ui'
import { AppTextInput, AppNumberInput, AppFormItem, AppConfirmDialog, AppInlineAlert, AppTermCodePicker, AppMakeupBatchPicker } from '@/components/common'
import { academicAffairsApi, academicAffairsMakeupApi as api } from '@/modules/academicAffairs/api/academic-affairs.api'
import { toast } from '@/utils/toast'

const _MBL = { DRAFT: '草稿', ARRANGED: '已编排', PUBLISHED: '已发布', SCORING: '录入中', REVIEWED: '学院已审', FINISHED: '已结束' }

export default {
  name: 'AaMakeupConsoleView',
  components: {
    ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState,
      AppButton, AppDrawer, AppTextInput, AppNumberInput, AppFormItem, AppConfirmDialog, AppInlineAlert, AppTermCodePicker, AppMakeupBatchPicker
  },
  data() {
    return {
      ctx: { currentRole: { roleName: '' }, dataScope: { scopeName: '' } },
      tab: 'makeup', loading: true, error: '', rows: [],
      tabs: [
        { key: 'makeup', label: '补考批次' }, { key: 'retake', label: '重修审批' },
        { key: 'exemption', label: '免修审批' }, { key: 'clearance', label: '毕业清考' },
        { key: 'deferred', label: '缓考合流' }
      ],
      batchColumns: [{ key: 'batchName', title: '批次' }, { key: 'termCode', title: '学期' }, { key: 'status', title: '状态' }, { key: 'ops', title: '操作' }],
      clearanceColumns: [{ key: 'batchName', title: '批次' }, { key: 'grades', title: '毕业年级' }, { key: 'status', title: '状态' }, { key: 'ops', title: '操作' }],
      crColumns: [{ key: 'student', title: '学生' }, { key: 'course', title: '课程' }, { key: 'score', title: '清考成绩' }, { key: 'ops', title: '操作' }],
      clearanceVisible: false, clearanceForm: { batchName: '', grades: '', termCode: '' }, clearanceError: '',
      crVisible: false, crBatch: null, crRows: [], crScores: {},
      retakeColumns: [{ key: 'student', title: '申请' }, { key: 'status', title: '状态' }, { key: 'ops', title: '操作' }],
      exemptionColumns: [{ key: 'student', title: '申请' }, { key: 'currentNode', title: '当前节点' }, { key: 'status', title: '状态' }, { key: 'ops', title: '操作' }],
      poolColumns: [{ key: 'student', title: '缓考学生' }, { key: 'ops', title: '操作' }],
      batchVisible: false, batchForm: { batchName: '', termCode: '' }, formError: '',
      mergeVisible: false, mergeRow: null, mergeBatchId: '',
      saving: false, confirmVisible: false, confirmTitle: '', confirmMessage: '', pendingAction: null,
      reasonDialog: { visible: false, title: '', sceneKey: '', submitting: false, action: null }
    }
  },
  async created() {
    const c = await academicAffairsApi.getContext()
    if (c.code === 0) this.ctx = c.data
    const q = this.$route && this.$route.query && this.$route.query.tab
    if (q && this.tabs.some((t) => t.key === q)) this.tab = q
    this.reload()
  },
  methods: {
    mbLabel(s) { return _MBL[s] || s },
    mbType(s) { return s === 'PUBLISHED' ? 'success' : s === 'FINISHED' ? 'default' : 'primary' },
    rtType(s) { return ['APPROVED', 'ENROLLED', 'FINISHED'].includes(s) ? 'success' : s === 'REJECTED' ? 'danger' : 'primary' },
    exType(s) { return s === 'APPROVED' ? 'success' : s === 'REJECTED' ? 'danger' : 'primary' },
    canReviewEx(s) { return ['SUBMITTED', 'TEACHER_REVIEW', 'COLLEGE_REVIEW', 'ACADEMIC_REVIEW'].includes(s) },
    switchTab(k) { this.tab = k; this.reload() },
    async reload() {
      this.loading = true; this.error = ''
      let res
      if (this.tab === 'makeup') res = await api.listBatches({ pageSize: 100, kind: 'MAKEUP' })
      else if (this.tab === 'clearance') res = await api.listBatches({ pageSize: 100, kind: 'CLEARANCE' })
      else if (this.tab === 'retake') res = await api.retakeApplies({ pageSize: 100 })
      else if (this.tab === 'exemption') res = await api.exemptionApplies({ pageSize: 100 })
      else res = await api.deferredPool({ pageSize: 100 })
      if (res.code === 0) this.rows = res.data.list
      else this.error = res.message
      this.loading = false
    },
    openCreateBatch() { this.batchForm = { batchName: '', termCode: '' }; this.formError = ''; this.batchVisible = true },
    async submitBatch() {
      if (!this.batchForm.batchName) { this.formError = '批次名称必填'; return }
      this.saving = true
      const res = await api.createBatch(this.batchForm)
      this.saving = false
      if (res.code === 0) { toast.success('已创建'); this.batchVisible = false; this.reload() } else this.formError = res.message
    },
    act(fn, id, label) {
      this.confirmTitle = label; this.confirmMessage = `确认执行「${label}」？`
      this.pendingAction = async () => {
        const res = await api[fn](id)
        if (res.code === 0) { toast.success(label + '成功'); this.reload() } else toast.error(res.message)
      }
      this.confirmVisible = true
    },
    printBatch(batchId) {
      window.open(`/admin/academic-affairs/makeup/batches/${batchId}/print`, '_blank')
    },
    async review(fn, id, action) {
      const res = await api[fn](id, action)
      if (res.code === 0) { toast.success('已通过'); this.reload() } else toast.error(res.message)
    },
    reject(fn, id) {
      this.reasonDialog = {
        visible: true, title: '驳回', sceneKey: 'aa.makeup.reject', submitting: false,
        action: async (reason) => {
          const res = await api[fn](id, 'REJECT', reason)
          if (res.code !== 0) { toast.error(res.message); return false }
          toast.success('已驳回'); this.reload(); return true
        }
      }
    },
    returnEx(id) {
      this.reasonDialog = {
        visible: true, title: '退回补材料', sceneKey: 'aa.makeup.supplement', submitting: false,
        action: async (reason) => {
          const res = await api.exemptionReview(id, 'RETURN', reason)
          if (res.code !== 0) { toast.error(res.message); return false }
          toast.success('已退回'); this.reload(); return true
        }
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
    async enrollRetake(id) {
      const res = await api.retakeEnroll(id, '')
      if (res.code === 0) { toast.success('已编入跟班'); this.reload() } else toast.error(res.message)
    },
    openMerge(row) { this.mergeRow = row; this.mergeBatchId = ''; this.mergeVisible = true },
    async submitMerge() {
      if (!this.mergeBatchId) { toast.error('批次 ID 必填'); return }
      this.saving = true
      const res = await api.mergeDeferred(this.mergeRow.deferId, this.mergeBatchId)
      this.saving = false
      if (res.code === 0) { toast.success('已并入'); this.mergeVisible = false; this.reload() } else toast.error(res.message)
    },
    openCreateClearance() { this.clearanceForm = { batchName: '', grades: '', termCode: '' }; this.clearanceError = ''; this.clearanceVisible = true },
    async submitClearance() {
      const grades = this.clearanceForm.grades.split(/[,，、\s]+/).filter(Boolean)
      if (!this.clearanceForm.batchName) { this.clearanceError = '批次名称必填'; return }
      if (!grades.length) { this.clearanceError = '必须限定毕业年级'; return }
      this.saving = true
      const res = await api.createClearanceBatch({
        batchName: this.clearanceForm.batchName, targetGrades: grades,
        termCode: this.clearanceForm.termCode || undefined
      })
      this.saving = false
      if (res.code === 0) { toast.success('清考批次已创建'); this.clearanceVisible = false; this.reload() }
      else this.clearanceError = res.message
    },
    async scanClearance(row, dryRun) {
      const res = await api.clearanceScan(row.batchId, dryRun)
      if (res.code !== 0) { toast.error(res.message); return }
      const d = res.data
      if (dryRun) toast.info(`预览：可圈定 ${d.candidates} 条（未落库）`)
      else { toast.success(`已圈定 ${d.added} 条（跳过已存在 ${d.skipped}）`); this.reload() }
    },
    async openClearanceRecords(row) {
      this.crBatch = row; this.crScores = {}
      const res = await api.clearanceRecords(row.batchId)
      this.crRows = res.code === 0 ? res.data.list : []
      this.crVisible = true
    },
    async submitClearanceScore(row) {
      const v = Number(this.crScores[row.makeupId])
      if (!(v >= 0 && v <= 100)) { toast.error('成绩须为 0-100'); return }
      const res = await api.score(row.makeupId, v)
      if (res.code === 0) { toast.success('已录入'); await this.openClearanceRecords(this.crBatch); this.reload() }
      else toast.error(res.message)
    },
    onConfirm() { const a = this.pendingAction; this.pendingAction = null; if (a) a() }
  }
}
</script>

<style scoped>
.aamk-tabs { display: flex; gap: 4px; border-bottom: 1px solid var(--border-color, #e5e7eb); margin-bottom: 16px; }
.aamk-tab { padding: 8px 16px; border: none; background: none; cursor: pointer; font-size: 14px; color: var(--text-secondary, #64748b); border-bottom: 2px solid transparent; }
.aamk-tab.is-active { color: var(--primary-color, #2563eb); border-bottom-color: var(--primary-color, #2563eb); font-weight: 600; }
.aamk-bar { margin-bottom: 8px; }
.aamk-form { display: flex; flex-direction: column; gap: 12px; }
.aamk-score-input { width: 82px; padding: 4px 8px; border: 1px solid var(--border-color, #e5e7eb); border-radius: 6px; font-size: 13px; }
</style>
