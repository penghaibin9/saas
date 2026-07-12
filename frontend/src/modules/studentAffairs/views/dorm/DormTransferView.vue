<template>
  <AppPageShell
    title="调宿与退宿"
    subtitle="调宿走「辅导员 → 宿管」两级审批，终审通过自动执行（原床释放 / 新床占用 / 回写我的宿舍）。"
    role-name="辅导员 / 宿管 / 学工处"
    data-scope-name="宿管限负责楼栋"
    watermark-purpose="宿舍调宿审批"
  >
    <template #actions>
      <AppPermissionButton code="studentAffairs.dorm.transfer.create" :loading="actioning" @click="submitTransfer">
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
                  <AppPermissionButton code="studentAffairs.dorm.transfer.approve" size="sm" :loading="actioning" @click="review(t, 'APPROVE')">通过</AppPermissionButton>
                  <AppPermissionButton code="studentAffairs.dorm.transfer.approve" size="sm" variant="secondary" :loading="actioning" @click="review(t, 'REJECT')">驳回</AppPermissionButton>
                </template>
                <span v-else class="sa-muted">—</span>
              </td>
            </tr>
            <tr v-if="!items.length"><td colspan="6" class="sa-empty">暂无调宿申请</td></tr>
          </tbody>
        </table>
      </AppSectionCard>
    </AppGlobalState>
  </AppPageShell>
</template>

<script>
import { AppGlobalState, AppMetricCard, AppPageShell, AppPermissionButton, AppSectionCard, AppStatusTag } from '@/components/common'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairsB.api'

export default {
  name: 'DormTransferView',
  components: { AppGlobalState, AppMetricCard, AppPageShell, AppPermissionButton, AppSectionCard, AppStatusTag },
  data() { return { loading: true, actioning: false, errorMessage: '', items: [] } },
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
    }
  },
  mounted() { this.load() },
  methods: {
    async load() {
      this.loading = true; this.errorMessage = ''
      try { this.items = (await studentAffairsApi.listDormTransfers({ pageSize: 100 })).data.items || [] }
      catch (e) { this.errorMessage = e.message || '调宿加载失败' } finally { this.loading = false }
    },
    async submitTransfer() {
      const sid = window.prompt('调宿学生 ID', '')
      if (!sid) return
      const toBedId = window.prompt('目标床位 ID（空床）', '')
      if (!toBedId) return
      const reason = window.prompt('调宿事由', '') || ''
      await this.runAction(() => studentAffairsApi.submitDormTransfer({ studentId: sid.trim(), toBedId: toBedId.trim(), reason }))
    },
    async review(t, action) {
      let reason = ''
      if (action === 'REJECT') {
        reason = window.prompt('驳回原因（不少于 5 字）', '')
        if (!reason || reason.trim().length < 5) { if (reason !== null) window.alert('原因不少于 5 字'); return }
      }
      await this.runAction(() => studentAffairsApi.reviewDormTransfer(t.transferId, action, (reason || '').trim()))
    },
    async runAction(fn) {
      this.actioning = true
      try { await fn(); await this.load() } catch (e) { this.errorMessage = e.message || '操作失败' } finally { this.actioning = false }
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
</style>
