<template>
  <AppPageShell
    title="调宿与退宿"
    subtitle="调宿走「辅导员 → 宿管」两级审批，终审通过自动执行（原床释放 / 新床占用 / 回写我的宿舍）。"
    role-name="辅导员 / 宿管 / 学工处"
    data-scope-name="宿管限负责楼栋"
    watermark-purpose="宿舍调宿审批"
  >
    <template #actions>
      <AppPermissionButton code="studentAffairs.dorm.transfer.create" :loading="actioning" @click="openSubmitTransfer">
        发起调宿
      </AppPermissionButton>
    </template>

    <AppGlobalState :state="pageState" :description="errorMessage" loading-text="正在加载调宿申请..." @retry="load"
                    @back="$router.push('/admin/student-affairs/dashboard')">
      <div class="sa-grid sa-grid--metrics">
        <AppMetricCard v-for="c in metricCards" :key="c.key" :title="c.label" :value="c.value" :accent="c.accent" />
      </div>
      <AppSectionCard title="调宿申请">
        <table class="sa-table">
          <thead><tr><th>学生</th><th>目标床</th><th>事由</th><th>当前节点</th><th>状态</th><th>操作</th></tr></thead>
          <tbody>
            <tr v-for="t in items" :key="t.transferId">
              <td><strong>{{ t.realName || t.studentId }}</strong><small>{{ t.studentNo }}</small></td>
              <td>床 #{{ t.toBedId }}</td>
              <td>{{ t.reason || '—' }}</td>
              <td>{{ nodeLabel(t.currentNode) }}</td>
              <td><AppStatusTag :type="statusKind(t.status)" :label="statusLabel(t.status)" /></td>
              <td class="sa-actions">
                <template v-if="isPending(t.status)">
                  <AppPermissionButton code="studentAffairs.dorm.transfer.approve" size="sm" :loading="actioning" @click="openReview(t, 'APPROVE')">通过</AppPermissionButton>
                  <AppPermissionButton code="studentAffairs.dorm.transfer.approve" size="sm" variant="secondary" :loading="actioning" @click="openReview(t, 'REJECT')">驳回</AppPermissionButton>
                </template>
                <span v-else class="sa-muted">—</span>
              </td>
            </tr>
            <tr v-if="!items.length"><td colspan="6" class="sa-empty">暂无调宿申请</td></tr>
          </tbody>
        </table>
        <AppPagination v-model:page="pagination.page" v-model:pageSize="pagination.pageSize" :total="pagination.total" @change="load" />
      </AppSectionCard>
    </AppGlobalState>

    <!-- 发起调宿 -->
    <AppDrawer v-model:visible="transferDrawer.visible" title="发起调宿">
      <div class="sa-form">
        <AppFormItem label="调宿学生 ID" required :error="transferDrawer.errors.studentId">
          <AppTextInput v-model="transferDrawer.form.studentId" placeholder="请输入学生 ID" :disabled="actioning" />
        </AppFormItem>
        <AppFormItem label="目标床位 ID" required :error="transferDrawer.errors.toBedId">
          <AppTextInput v-model="transferDrawer.form.toBedId" placeholder="请输入空床床位 ID" :disabled="actioning" />
        </AppFormItem>
        <AppFormItem label="调宿事由">
          <AppTextarea v-model="transferDrawer.form.reason" placeholder="调宿事由（选填）" :disabled="actioning" />
        </AppFormItem>
        <AppInlineAlert v-if="transferDrawer.errorMessage" type="danger" :description="transferDrawer.errorMessage" />
      </div>
      <template #footer>
        <button type="button" class="sa-btn" :disabled="actioning" @click="transferDrawer.visible = false">取消</button>
        <AppPermissionButton code="studentAffairs.dorm.transfer.create" :loading="actioning" @click="submitTransferForm">
          提交
        </AppPermissionButton>
      </template>
    </AppDrawer>

    <!-- 审批二次确认 -->
    <AppConfirmDialog
      v-model:visible="reviewDialog.visible"
      :title="reviewDialogTitle"
      :message="reviewDialogMessage"
      :type="reviewDialog.action === 'REJECT' ? 'danger' : 'warning'"
      :confirm-text="reviewDialog.action === 'REJECT' ? '确认驳回' : '确认通过'"
      :require-reason="reviewDialog.action === 'REJECT'"
      reason-label="驳回原因"
      :reason-min-length="5"
      phrase-scene-key="sa.dorm.reject"
      :submitting="actioning"
      @confirm="submitReview"
    >
      <AppInlineAlert v-if="reviewDialog.errorMessage" type="danger" :description="reviewDialog.errorMessage" />
    </AppConfirmDialog>
  </AppPageShell>
</template>

<script>
import { AppConfirmDialog, AppFormItem, AppGlobalState, AppInlineAlert, AppMetricCard, AppPageShell,
        AppPagination, AppPermissionButton, AppSectionCard, AppStatusTag, AppTextarea, AppTextInput } from '@/components/common'
import AppDrawer from '@/components/ui/AppDrawer.vue'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairsB.api'

function freshTransferForm() {
  return { studentId: '', toBedId: '', reason: '' }
}

export default {
  name: 'DormTransferView',
  components: { AppConfirmDialog, AppDrawer, AppFormItem, AppGlobalState, AppInlineAlert, AppMetricCard, AppPageShell,
               AppPagination, AppPermissionButton, AppSectionCard, AppStatusTag, AppTextarea, AppTextInput },
  data() {
    return {
      loading: true, actioning: false, errorMessage: '', items: [],
      pagination: { page: 1, pageSize: 20, total: 0 },
      transferDrawer: { visible: false, form: freshTransferForm(), errors: {}, errorMessage: '' },
      reviewDialog: { visible: false, target: null, action: '', errorMessage: '' }
    }
  },
  computed: {
    pageState() { return this.loading ? 'loading' : (this.errorMessage ? 'error' : 'ready') },
    metricCards() {
      const pending = this.items.filter((t) => this.isPending(t.status)).length
      const executed = this.items.filter((t) => t.status === 'EXECUTED').length
      const rejected = this.items.filter((t) => t.status === 'REJECTED').length
      return [
        { key: 'p', label: '待审批', value: pending, accent: pending ? 'warning' : 'success' },
        { key: 'e', label: '已执行', value: executed, accent: 'primary' },
        { key: 'r', label: '已驳回', value: rejected, accent: 'info' },
        { key: 't', label: '合计', value: this.items.length, accent: 'info' }
      ]
    },
    reviewDialogTitle() { return this.reviewDialog.action === 'REJECT' ? '驳回调宿申请' : '通过调宿申请' },
    reviewDialogMessage() {
      const t = this.reviewDialog.target
      const who = t ? (t.realName || t.studentId) : ''
      return this.reviewDialog.action === 'REJECT'
        ? `确认驳回 ${who} 的调宿申请？请填写驳回原因。`
        : `确认通过 ${who} 的调宿申请？`
    }
  },
  mounted() { this.load() },
  methods: {
    async load() {
      this.loading = true; this.errorMessage = ''
      try {
        const res = await studentAffairsApi.listDormTransfers({
          page: this.pagination.page, pageSize: this.pagination.pageSize
        })
        this.items = res.data.items || []
        this.pagination.total = res.data.total || 0
      } catch (e) { this.errorMessage = e.message || '调宿加载失败' } finally { this.loading = false }
    },
    openSubmitTransfer() {
      this.transferDrawer.form = freshTransferForm()
      this.transferDrawer.errors = {}
      this.transferDrawer.errorMessage = ''
      this.transferDrawer.visible = true
    },
    async submitTransferForm() {
      const { form, errors } = this.transferDrawer
      errors.studentId = form.studentId.trim() ? '' : '调宿学生 ID 必填'
      errors.toBedId = form.toBedId.trim() ? '' : '目标床位 ID 必填'
      if (errors.studentId || errors.toBedId) return
      this.actioning = true; this.transferDrawer.errorMessage = ''
      try {
        await studentAffairsApi.submitDormTransfer({
          studentId: form.studentId.trim(), toBedId: form.toBedId.trim(), reason: form.reason.trim()
        })
        this.transferDrawer.visible = false
        await this.load()
      } catch (e) { this.transferDrawer.errorMessage = e.message || '提交失败' }
      finally { this.actioning = false }
    },
    openReview(t, action) {
      this.reviewDialog.target = t
      this.reviewDialog.action = action
      this.reviewDialog.errorMessage = ''
      this.reviewDialog.visible = true
    },
    async submitReview({ reason }) {
      const { target, action } = this.reviewDialog
      if (!target) return
      this.actioning = true; this.reviewDialog.errorMessage = ''
      try {
        await studentAffairsApi.reviewDormTransfer(target.transferId, action, (reason || '').trim())
        this.reviewDialog.visible = false
        await this.load()
      } catch (e) { this.reviewDialog.errorMessage = e.message || '操作失败' }
      finally { this.actioning = false }
    },
    isPending(s) { return s === 'COUNSELOR_REVIEW' || s === 'DORM_MANAGER_REVIEW' || s === 'SUBMITTED' },
    nodeLabel(n) { return ({ COUNSELOR_REVIEW: '辅导员审核', DORM_MANAGER_REVIEW: '宿管审核' })[n] || (n || '—') },
    statusLabel(s) { return ({ SUBMITTED: '已提交', COUNSELOR_REVIEW: '辅导员审核', DORM_MANAGER_REVIEW: '宿管审核', EXECUTED: '已执行', REJECTED: '已驳回', CANCELLED: '已取消' })[s] || s },
    statusKind(s) { if (s === 'EXECUTED') return 'success'; if (s === 'REJECTED') return 'danger'; if (this.isPending(s)) return 'warning'; return 'info' }
  }
}
</script>

<style scoped>
.sa-grid--metrics { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: var(--space-4); margin-bottom: var(--space-4); }
.sa-table { width: 100%; border-collapse: collapse; }
.sa-table th, .sa-table td { border-bottom: 1px solid var(--border-light); padding: var(--space-3); text-align: left; vertical-align: top; }
.sa-table small { display: block; color: var(--text-tertiary); }
.sa-actions { display: flex; flex-wrap: wrap; gap: var(--space-2); }
.sa-muted { color: var(--text-tertiary); }
.sa-empty { color: var(--text-tertiary); padding: var(--space-4); text-align: center; }
@media (max-width: 960px) { .sa-grid--metrics { grid-template-columns: 1fr 1fr; } }
.sa-form { display: flex; flex-direction: column; gap: var(--space-4); }
.sa-btn { height: 34px; padding: 0 var(--space-4); border-radius: var(--radius-base); border: 1px solid var(--border-base); background: var(--bg-card); color: var(--text-secondary); font-size: var(--font-size-base); cursor: pointer; }
.sa-btn:hover { border-color: var(--border-dark); }
.sa-btn:disabled { opacity: 0.6; cursor: not-allowed; }
</style>
