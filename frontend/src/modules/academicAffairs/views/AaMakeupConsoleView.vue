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

      <!-- 缓考合流 -->
      <div v-else class="mp-stack">
        <EmptyState v-if="!rows.length" title="暂无缓考 APPROVED 学生" description="考务包审批通过的缓考学生在此并入补考批次" />
        <DataTable v-else :columns="poolColumns" :rows="rows" row-key="deferId">
          <template #cell-student="{ row }">{{ row.studentName }}（{{ row.courseName }}）</template>
          <template #cell-ops="{ row }"><button class="mp-link" @click="openMerge(row)">并入补考批次</button></template>
        </DataTable>
      </div>
    </template>

    <AppDrawer :visible="batchVisible" title="新建补考批次" @close="batchVisible = false">
      <div class="aamk-form">
        <AppFormItem label="批次名称" required><AppTextInput v-model="batchForm.batchName" placeholder="如 2024秋补考" :disabled="saving" /></AppFormItem>
        <AppFormItem label="学期"><AppTextInput v-model="batchForm.termCode" placeholder="如 2024-1" :disabled="saving" /></AppFormItem>
        <AppInlineAlert v-if="formError" type="danger" :description="formError" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="saving" @click="batchVisible = false">取消</AppButton>
        <AppButton variant="primary" :loading="saving" @click="submitBatch">创建</AppButton>
      </template>
    </AppDrawer>

    <AppDrawer :visible="mergeVisible" title="并入补考批次" @close="mergeVisible = false">
      <div class="aamk-form">
        <AppFormItem label="目标补考批次 ID" required><AppTextInput v-model="mergeBatchId" placeholder="补考批次 ID" :disabled="saving" /></AppFormItem>
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="saving" @click="mergeVisible = false">取消</AppButton>
        <AppButton variant="primary" :loading="saving" @click="submitMerge">并入</AppButton>
      </template>
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
import { AppTextInput, AppFormItem, AppConfirmDialog, AppInlineAlert } from '@/components/common'
import { academicAffairsApi, academicAffairsMakeupApi as api } from '@/modules/academicAffairs/api/academic-affairs.api'
import { toast } from '@/utils/toast'

const _MBL = { DRAFT: '草稿', ARRANGED: '已编排', PUBLISHED: '已发布', SCORING: '录入中', REVIEWED: '学院已审', FINISHED: '已结束' }

export default {
  name: 'AaMakeupConsoleView',
  components: {
    ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState,
    AppButton, AppDrawer, AppTextInput, AppFormItem, AppConfirmDialog, AppInlineAlert
  },
  data() {
    return {
      ctx: { currentRole: { roleName: '' }, dataScope: { scopeName: '' } },
      tab: 'makeup', loading: true, error: '', rows: [],
      tabs: [
        { key: 'makeup', label: '补考批次' }, { key: 'retake', label: '重修审批' },
        { key: 'exemption', label: '免修审批' }, { key: 'deferred', label: '缓考合流' }
      ],
      batchColumns: [{ key: 'batchName', title: '批次' }, { key: 'termCode', title: '学期' }, { key: 'status', title: '状态' }, { key: 'ops', title: '操作' }],
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
      if (this.tab === 'makeup') res = await api.listBatches({ pageSize: 100 })
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
          if (res.code === 0) { toast.success('已驳回'); this.reload() } else toast.error(res.message)
        }
      }
    },
    returnEx(id) {
      this.reasonDialog = {
        visible: true, title: '退回补材料', sceneKey: 'aa.makeup.supplement', submitting: false,
        action: async (reason) => {
          const res = await api.exemptionReview(id, 'RETURN', reason)
          if (res.code === 0) { toast.success('已退回'); this.reload() } else toast.error(res.message)
        }
      }
    },
    async onReasonConfirm({ reason }) {
      const action = this.reasonDialog.action
      this.reasonDialog.submitting = true
      if (action) await action(reason)
      this.reasonDialog.submitting = false
      this.reasonDialog.visible = false
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
</style>
