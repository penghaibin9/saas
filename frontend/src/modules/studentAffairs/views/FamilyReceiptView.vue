<template>
  <AppPageShell title="家校回执" subtitle="家校联系记录的家长回执跟踪：待回执 → 登记回执。号码本体不呈现。按数据范围裁剪。"
    role-name="辅导员 / 学院" data-scope-name="本人带班 / 授权范围" watermark-purpose="家校回执">
    <AppGlobalState :state="pageState" :description="errorMessage" loading-text="加载中..." @retry="load"
                    @back="$router.push('/admin/student-affairs/family')">
      <div class="sa-grid sa-grid--metrics">
        <AppMetricCard v-for="c in metricCards" :key="c.key" :title="c.label" :value="c.value" :accent="c.accent" />
      </div>
      <AppSectionCard title="家校联系记录">
        <div class="fr-filters">
          <button v-for="f in statusFilters" :key="f.key" type="button" class="fr-chip" :class="{ 'is-on': activeStatus===f.key }" @click="setStatus(f.key)">{{ f.label }}</button>
        </div>
        <table class="sa-table">
          <thead><tr><th>学生</th><th>方式</th><th>事由</th><th>时间</th><th>回执</th><th>操作</th></tr></thead>
          <tbody>
            <tr v-for="c in items" :key="c.contactId">
              <td><strong>{{ c.realName || ('#'+c.studentId) }}</strong></td>
              <td>{{ typeLabel(c.contactType) }}</td>
              <td class="fr-reason">{{ c.reason || '—' }}</td>
              <td><AppDateDisplay :value="c.occurredAt" mode="date" empty-text="—" /></td>
              <td><StatusTag :type="c.receiptStatus==='RECEIVED'?'success':'warning'" :label="c.receiptStatusLabel || c.receiptStatus" dot />
                <em v-if="c.receiptNote" class="fr-note">{{ c.receiptNote }}</em></td>
              <td>
                <AppPermissionButton v-if="c.receiptStatus!=='RECEIVED'" code="studentAffairs.homeSchool.record.create" size="sm" :loading="acting===c.contactId" @click="openReceiptDialog(c)">登记回执</AppPermissionButton>
                <span v-else class="fr-muted">—</span>
              </td>
            </tr>
            <tr v-if="!items.length"><td colspan="6" class="sa-empty">暂无家校联系记录</td></tr>
          </tbody>
        </table>
        <AppPagination v-if="total > pageSize" class="fr-pagination" v-model:page="page" v-model:pageSize="pageSize" :total="total" @change="load" />
      </AppSectionCard>
    </AppGlobalState>

    <!-- 登记家长回执确认 -->
    <AppConfirmDialog
      v-model:visible="receiptDialog.visible"
      title="登记家长回执"
      message="确认登记该条家校联系的家长回执。"
      type="primary"
      confirm-text="登记回执"
      :submitting="!!acting"
      @confirm="confirmReceipt"
    >
      <AppFormItem label="回执内容（可空）">
        <AppTextarea v-model="receiptDialog.note" :rows="3" placeholder="家长回执内容（可空）" />
      </AppFormItem>
    </AppConfirmDialog>
  </AppPageShell>
</template>

<script>
import {
  AppConfirmDialog, AppDateDisplay, AppFormItem, AppGlobalState, AppMetricCard, AppPageShell,
  AppPagination, AppPermissionButton, AppSectionCard, AppStatusTag, AppTextarea
} from '@/components/common'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'
import { toast } from '@/utils/toast'

const TYPE = { PHONE: '电话', WECHAT: '微信', VISIT: '家访', MESSAGE: '短信' }
const STATUS_FILTERS = [{ key: '', label: '全部' }, { key: 'PENDING', label: '待回执' }, { key: 'RECEIVED', label: '已回执' }]

export default {
  name: 'FamilyReceiptView',
  components: {
    AppConfirmDialog, AppDateDisplay, AppFormItem, AppGlobalState, AppMetricCard, AppPageShell,
    AppPagination, AppPermissionButton, AppSectionCard, StatusTag: AppStatusTag, AppTextarea
  },
  data() {
    return {
      loading: true, acting: '', errorMessage: '', all: [], items: [], activeStatus: '', statusFilters: STATUS_FILTERS,
      page: 1, pageSize: 20, total: 0,
      receiptDialog: { visible: false, contactId: '', note: '' }
    }
  },
  computed: {
    pageState() { return this.loading ? 'loading' : (this.errorMessage ? 'error' : 'ready') },
    metricCards() {
      const pend = this.all.filter((x) => x.receiptStatus === 'PENDING').length
      return [
        { key: 't', label: '联系记录', value: this.all.length, accent: 'primary' },
        { key: 'p', label: '待回执', value: pend, accent: pend ? 'warning' : 'success' },
        { key: 'r', label: '已回执', value: this.all.length - pend, accent: 'success' }
      ]
    }
  },
  mounted() { this.load() },
  methods: {
    async load() {
      this.loading = true; this.errorMessage = ''
      // 分页说明：/student-affairs/family-contacts 后端支持真分页（page/pageSize/total）；
      // 表格 items 按分页加载，顶部统计卡片始终基于全量单独取数，两者互不影响。
      const res = await studentAffairsApi.getFamilyContactsAll({ receiptStatus: this.activeStatus, page: this.page, pageSize: this.pageSize })
      if (res.code === 0 && res.data) {
        this.items = res.data.items || []
        this.total = res.data.total || 0
      } else { this.errorMessage = res.message || '加载失败' }
      // 指标始终基于全量
      const full = await studentAffairsApi.getFamilyContactsAll({})
      this.all = (full.code === 0 && full.data) ? (full.data.items || []) : this.all
      this.loading = false
    },
    setStatus(k) { if (this.activeStatus === k) return; this.activeStatus = k; this.page = 1; this.load() },
    openReceiptDialog(c) {
      this.receiptDialog = { visible: true, contactId: c.contactId, note: '' }
    },
    async confirmReceipt() {
      const { contactId, note } = this.receiptDialog
      this.acting = contactId
      const res = await studentAffairsApi.markFamilyReceipt(contactId, note || '')
      this.acting = ''
      this.receiptDialog.visible = false
      if (res.code === 0) { toast.success('回执已登记'); this.load() } else toast.error(res.message || '登记失败')
    },
    typeLabel(t) { return TYPE[t] || t }
  }
}
</script>

<style scoped>
.sa-grid--metrics { display: grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap: var(--space-4); margin-bottom: var(--space-4); }
.fr-filters { display: flex; gap: var(--space-2); margin-bottom: var(--space-3); }
.fr-chip { border: 1px solid var(--border-light); background: var(--bg-card); border-radius: var(--radius-full); padding: 4px 14px; font-size: var(--font-size-sm); cursor: pointer; }
.fr-chip.is-on { background: var(--color-primary); color: #fff; border-color: var(--color-primary); }
.sa-table { width: 100%; border-collapse: collapse; }
.sa-table th, .sa-table td { border-bottom: 1px solid var(--border-light); padding: var(--space-2) var(--space-3); text-align: left; }
.sa-empty { color: var(--text-tertiary); padding: var(--space-4); text-align: center; }
.fr-reason { color: var(--text-secondary); font-size: var(--font-size-sm); max-width: 220px; }
.fr-note { display: block; color: var(--text-tertiary); font-size: var(--font-size-xs); font-style: normal; }
.fr-muted { color: var(--text-tertiary); }
.fr-pagination { margin-top: var(--space-4); }
@media (max-width: 960px) { .sa-grid--metrics { grid-template-columns: 1fr; } }
</style>
