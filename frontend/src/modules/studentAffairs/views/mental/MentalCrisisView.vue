<template>
  <AppPageShell
    title="心理危机升级"
    subtitle="危机升级复用风险中枢：升级后自动生成 source=MENTAL 的风险记录并接入处置闭环；升级幂等，不重复建单。"
    role-name="心理老师 / 授权辅导员 / 学工处(专项授权)"
    data-scope-name="PSY_STUDENT 逐生授权范围"
    watermark-purpose="心理危机升级处理"
  >
    <AppGlobalState :state="pageState" :description="errorMessage" loading-text="正在加载心理危机记录..." @retry="load" @back="$router.push('/admin/student-affairs/dashboard')">
      <div class="sa-grid sa-grid--metrics"><AppMetricCard v-for="card in metricCards" :key="card.key" :title="card.label" :value="card.value" :accent="card.accent" /></div>

      <AppSectionCard title="危机与可升级记录">
        <AppInlineAlert type="warning" description="升级危机会生成正式风险单并通知相关责任人。必须填写客观危机信号和已采取措施，禁止空说明或诊断性结论。" />
        <DataTable
          v-if="items.length || pagination.total > 0"
          :columns="crisisColumns"
          :rows="items"
          row-key="referralId"
          :pagination="pagination"
          :row-class="(row) => (row.level === 'CRISIS' ? 'sa-crisis' : '')"
          @page-change="onPageChange"
        >
          <template #cell-student="{ row }"><div class="mp-cell-main">{{ row.realName || '未命名学生' }}</div><div class="mp-cell-sub">{{ row.studentNo || row.studentId }}</div></template>
          <template #cell-level="{ row }"><AppStatusTag :type="levelKind(row.level)" :label="row.levelLabel || row.level" /></template>
          <template #cell-status="{ row }"><AppStatusTag :type="statusKind(row.status)" :label="row.statusLabel || row.status" /></template>
          <template #cell-reason="{ row }">{{ row.reasonSummary || '—' }}</template>
          <template #cell-risk="{ row }"><a v-if="row.riskId" class="sa-link" @click="gotoRisk(row.riskId)">风险 #{{ row.riskId }} →</a><span v-else class="sa-muted">未升级</span></template>
          <template #cell-actions="{ row }">
            <div class="sa-actions">
              <AppPermissionButton
                v-if="canEscalate(row)"
                :allowed="canBtn('studentAffairs.mental.manage')"
                code="studentAffairs.mental.manage"
                size="sm"
                danger
                :loading="actioning"
                :disabled="!hasVersion(row)"
                @click="escalate(row)"
              >填写依据并升级</AppPermissionButton>
              <AppPermissionButton v-if="row.riskId" :allowed="canBtn('studentAffairs.risk.view')" code="studentAffairs.risk.view" size="sm" variant="secondary" @click="gotoRisk(row.riskId)">查看风险</AppPermissionButton>
              <span v-if="!canEscalate(row) && !row.riskId" class="sa-muted">当前状态不可升级</span>
            </div>
          </template>
        </DataTable>
        <p v-else class="sa-empty">当前授权范围内暂无心理关注记录</p>
      </AppSectionCard>
    </AppGlobalState>

    <AppConfirmDialog
      v-model:visible="dlg.visible"
      :title="`升级为心理危机 · ${dlg.who}`"
      type="danger"
      message="升级后将生成正式风险中枢记录并通知相关责任人。请先核对学生身份、危机信号和当前处置情况；该动作全程审计。"
      confirm-text="确认升级"
      :submitting="actioning"
      @confirm="submitEscalate"
    >
      <AppFormItem label="升级依据（5-300字）" required>
        <AppTextarea ref="contentInput" v-model="dlg.content" :rows="4" :maxlength="300" :disabled="actioning" placeholder="客观写明危机信号、核实来源、已采取措施与升级必要性" />
        <AppQuickPhrases scene-key="sa.mental.escalate" @pick="onPickContent" />
        <p class="char-count">{{ (dlg.content || '').trim().length }}/300</p>
        <p v-if="dlg.error" class="field-error">{{ dlg.error }}</p>
      </AppFormItem>
    </AppConfirmDialog>
  </AppPageShell>
</template>

<script>
import {
  AppConfirmDialog, AppFormItem, AppGlobalState, AppInlineAlert, AppMetricCard, AppPageShell,
  AppPermissionButton, AppQuickPhrases, AppSectionCard, AppStatusTag, AppTextarea
} from '@/components/common'
import { DataTable } from '@/components/business'
import { insertAtCursor, applyInsertion } from '@/utils/insertAtCursor'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairsB.api'
import { canCode } from '@/modules/studentAffairs/composables/permission'

const CRISIS_COLUMNS = [
  { key: 'student', title: '学生' }, { key: 'level', title: '关注等级' },
  { key: 'status', title: '状态' }, { key: 'reason', title: '事由摘要' },
  { key: 'risk', title: '关联风险' }, { key: 'actions', title: '操作', align: 'right', width: '220px' }
]

export default {
  name: 'MentalCrisisView',
  props: { ctx: { type: Object, default: null } },
  components: {
    AppConfirmDialog, AppFormItem, AppGlobalState, AppInlineAlert, AppMetricCard, AppPageShell,
    AppPermissionButton, AppQuickPhrases, AppSectionCard, AppStatusTag, AppTextarea, DataTable
  },
  data() {
    return {
      crisisColumns: CRISIS_COLUMNS,
      loading: true, actioning: false, errorMessage: '', items: [], statusCounts: null,
      pagination: { page: 1, pageSize: 50, total: 0 },
      dlg: { visible: false, row: null, who: '', content: '', error: '' }
    }
  },
  computed: {
    pageState() { return this.loading ? 'loading' : (this.errorMessage ? 'error' : 'ready') },
    metricCards() {
      const count = (status) => this.statusCounts === null ? '—' : Number(this.statusCounts[status] || 0)
      return [
        { key: 'crisis', label: '危机记录', value: '—', accent: 'risk' },
        { key: 'open', label: '在办危机', value: '—', accent: 'risk' },
        { key: 'escalated', label: '已接风险中枢', value: count('ESCALATED'), accent: 'primary' },
        { key: 'total', label: '关注在册', value: this.statusCounts === null ? '—' : Number(this.statusCounts.ALL || 0), accent: 'info' }
      ]
    }
  },
  mounted() { this.load() },
  methods: {
    canBtn(code) { return canCode(this.ctx, code) },
    hasVersion(row) { return row && row.version !== undefined && row.version !== null && row.version !== '' },
    canEscalate(row) {
      if (!row || row.status === 'CLOSED' || row.riskId) return false
      if (Array.isArray(row.allowedActions)) return row.allowedActions.includes('ESCALATE')
      return ['REFERRED', 'FOLLOWING'].includes(row.status)
    },
    async load() {
      this.loading = true; this.errorMessage = ''
      try {
        const res = await studentAffairsApi.listMentalAttention({ page: this.pagination.page, pageSize: this.pagination.pageSize })
        this.items = res.data.items || []
        this.pagination.total = res.data.total != null ? res.data.total : this.items.length
        this.statusCounts = res.data.statusCounts || null
      } catch (e) { this.errorMessage = e.message || '心理危机记录加载失败' }
      finally { this.loading = false }
    },
    onPageChange(page) { this.pagination.page = page; this.load() },
    escalate(row) {
      if (!this.canEscalate(row) || !this.hasVersion(row)) return
      this.dlg = { visible: true, row, who: row.realName || row.studentNo || row.studentId, content: '', error: '' }
    },
    onPickContent(text) {
      const el = this.$refs.contentInput && this.$refs.contentInput.$refs.el
      if (!el) { this.dlg.content += text; return }
      const r = insertAtCursor(el, this.dlg.content, text)
      this.dlg.content = r.value
      this.$nextTick(() => applyInsertion(el, r.selStart, r.selEnd))
    },
    async submitEscalate() {
      const content = (this.dlg.content || '').trim()
      if (content.length < 5 || content.length > 300) { this.dlg.error = '升级依据需5-300字'; return }
      if (!this.canEscalate(this.dlg.row) || !this.hasVersion(this.dlg.row)) { this.dlg.error = '记录状态或版本已变化，请刷新后重试'; return }
      this.dlg.error = ''
      const ok = await this.runAction(() => studentAffairsApi.escalateMentalReferral(this.dlg.row.referralId, content, this.dlg.row.version))
      if (ok) this.dlg.visible = false
      else this.dlg.error = this.errorMessage
    },
    gotoRisk(riskId) { this.$router.push(`/admin/student-affairs/risk/${riskId}`) },
    async runAction(fn) {
      this.actioning = true; this.errorMessage = ''
      try { await fn(); await this.load(); return true }
      catch (e) {
        if (e.bizCode === 'APPROVAL_VERSION_CONFLICT') { this.errorMessage = '该记录已被其他人处理，数据已刷新'; await this.load(); return false }
        this.errorMessage = e.message || '操作失败'; return false
      } finally { this.actioning = false }
    },
    levelKind(level) { if (level === 'CRISIS') return 'danger'; if (level === 'FOCUS') return 'warning'; return 'info' },
    statusKind(status) { if (status === 'CLOSED') return 'success'; if (status === 'ESCALATED') return 'danger'; if (status === 'FOLLOWING') return 'warning'; return 'info' }
  }
}
</script>

<style scoped>
.sa-grid--metrics { display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:var(--space-4);margin-bottom:var(--space-4) }
:deep(.dt__tr.sa-crisis) .dt__td { background:var(--danger-50,var(--warning-50)) }
.sa-actions { display:flex;flex-wrap:wrap;gap:var(--space-2) }.sa-link { color:var(--primary-600);cursor:pointer }.sa-muted { color:var(--text-tertiary) }.sa-empty { color:var(--text-tertiary);padding:var(--space-4);text-align:center }.char-count { margin:4px 0 0;text-align:right;color:var(--text-tertiary);font-size:12px }.field-error { margin:4px 0 0;color:var(--danger-600);font-size:12px }
@media(max-width:960px){.sa-grid--metrics{grid-template-columns:1fr 1fr}}
@import '@/styles/module-page.css';
</style>
