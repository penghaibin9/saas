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
              <td>{{ (c.occurredAt||'').slice(0,10) || '—' }}</td>
              <td><StatusTag :type="c.receiptStatus==='RECEIVED'?'success':'warning'" :label="c.receiptStatusLabel || c.receiptStatus" dot />
                <em v-if="c.receiptNote" class="fr-note">{{ c.receiptNote }}</em></td>
              <td>
                <AppPermissionButton v-if="c.receiptStatus!=='RECEIVED'" code="studentAffairs.homeSchool.record.create" size="sm" :loading="acting===c.contactId" @click="markReceipt(c)">登记回执</AppPermissionButton>
                <span v-else class="fr-muted">—</span>
              </td>
            </tr>
            <tr v-if="!items.length"><td colspan="6" class="sa-empty">暂无家校联系记录</td></tr>
          </tbody>
        </table>
      </AppSectionCard>
    </AppGlobalState>

    <!-- 家长回执：挂 sa.family.result——该词库正是家长反馈口径
         （家长已知晓将督促/约定每周沟通/在家表现正常/将来校面谈/未接通改短信），与本字段同义。 -->
    <AppConfirmDialog
      v-model:visible="recDlg.visible" :title="`登记家长回执 · ${recDlg.who}`" type="primary"
      confirm-text="登记回执" :submitting="acting === recDlg.contactId" @confirm="submitReceipt"
    >
      <AppFormItem label="家长回执内容（可空）">
        <AppTextarea ref="noteInput" v-model="recDlg.note" :rows="3" :maxlength="500"
                     placeholder="记录家长的反馈与后续约定" />
        <AppQuickPhrases scene-key="sa.family.result" @pick="onPickNote" />
      </AppFormItem>
    </AppConfirmDialog>
  </AppPageShell>
</template>

<script>
import {
  AppConfirmDialog, AppFormItem, AppGlobalState, AppMetricCard, AppPageShell, AppPermissionButton,
  AppQuickPhrases, AppSectionCard, AppStatusTag, AppTextarea
} from '@/components/common'
import { insertAtCursor, applyInsertion } from '@/utils/insertAtCursor'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'
import { toast } from '@/utils/toast'

const TYPE = { PHONE: '电话', WECHAT: '微信', VISIT: '家访', MESSAGE: '短信' }
const STATUS_FILTERS = [{ key: '', label: '全部' }, { key: 'PENDING', label: '待回执' }, { key: 'RECEIVED', label: '已回执' }]

export default {
  name: 'FamilyReceiptView',
  components: {
    AppConfirmDialog, AppFormItem, AppGlobalState, AppMetricCard, AppPageShell, AppPermissionButton,
    AppQuickPhrases, AppSectionCard, AppTextarea, StatusTag: AppStatusTag
  },
  data() {
    return {
      loading: true, acting: '', errorMessage: '', all: [], items: [], activeStatus: '', statusFilters: STATUS_FILTERS,
      recDlg: { visible: false, contactId: '', who: '', note: '' }
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
      const res = await studentAffairsApi.getFamilyContactsAll({ receiptStatus: this.activeStatus })
      if (res.code === 0 && res.data) {
        this.items = res.data.items || []
        if (!this.activeStatus) this.all = this.items
      } else { this.errorMessage = res.message || '加载失败' }
      // 指标始终基于全量
      if (this.activeStatus) {
        const full = await studentAffairsApi.getFamilyContactsAll({})
        this.all = (full.code === 0 && full.data) ? (full.data.items || []) : this.all
      }
      this.loading = false
    },
    setStatus(k) { if (this.activeStatus === k) return; this.activeStatus = k; this.load() },
    markReceipt(c) {
      this.recDlg = { visible: true, contactId: c.contactId, who: c.realName || c.studentNo || '该生', note: '' }
    },
    onPickNote(text) {
      const el = this.$refs.noteInput && this.$refs.noteInput.$refs.el
      if (!el) { this.recDlg.note += text; return }
      const r = insertAtCursor(el, this.recDlg.note, text)
      this.recDlg.note = r.value
      this.$nextTick(() => applyInsertion(el, r.selStart, r.selEnd))
    },
    async submitReceipt() {
      const d = this.recDlg
      this.acting = d.contactId
      const res = await studentAffairsApi.markFamilyReceipt(d.contactId, d.note.trim())
      this.acting = ''
      if (res.code === 0) { d.visible = false; toast.success('回执已登记'); this.load() } else toast.error(res.message || '登记失败')
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
@media (max-width: 960px) { .sa-grid--metrics { grid-template-columns: 1fr; } }
</style>
