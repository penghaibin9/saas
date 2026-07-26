<template>
  <AppPageShell
    title="谈话转介与回访"
    subtitle="统一展示转介、回访、危机升级与关闭记录；动作由后端状态机返回，明细仍按专项授权和审计控制。"
    role-name="心理老师 / 授权辅导员"
    data-scope-name="PSY_STUDENT 逐生授权范围"
    watermark-purpose="心理转介回访处理"
  >
    <template #actions>
      <AppPermissionButton :allowed="canBtn('studentAffairs.mental.manage')" code="studentAffairs.mental.manage" :loading="actioning" @click="createReferral">登记转介</AppPermissionButton>
    </template>

    <AppGlobalState :state="pageState" :description="errorMessage" loading-text="正在加载转介回访工作台..." @retry="load" @back="$router.push('/admin/student-affairs/dashboard')">
      <div class="sa-grid sa-grid--metrics">
        <AppMetricCard v-for="card in metricCards" :key="card.key" :title="card.label" :value="card.value" :accent="card.accent" />
      </div>

      <AppSectionCard title="心理转介与回访记录">
        <AppInlineAlert type="info" description="列表只展示业务摘要；敏感明细必须进入详情并填写查看原因。已升级危机由风险中枢继续处置，转介记录不再提供普通回访动作。" />
        <DataTable v-if="items.length || pagination.total > 0" :columns="followColumns" :rows="items" row-key="referralId" :pagination="pagination" @page-change="onPageChange">
          <template #cell-student="{ row }"><div class="mp-cell-main">{{ row.realName || '未命名学生' }}</div><div class="mp-cell-sub">{{ row.studentNo || row.studentId }}</div></template>
          <template #cell-level="{ row }"><AppStatusTag :type="levelKind(row.level)" :label="row.levelLabel || row.level" /></template>
          <template #cell-status="{ row }"><AppStatusTag :type="statusKind(row.status)" :label="row.statusLabel || row.status" /></template>
          <template #cell-reason="{ row }">{{ row.reasonSummary || '—' }}</template>
          <template #cell-channel="{ row }">{{ row.channel || '—' }}</template>
          <template #cell-lastFollow="{ row }">{{ (row.lastFollowTime || '').slice(0, 16) || '尚未回访' }}</template>
          <template #cell-actions="{ row }">
            <div class="sa-actions" v-if="allowed(row).length">
              <AppPermissionButton v-if="allowed(row).includes('FOLLOW')" :allowed="canBtn('studentAffairs.mental.manage')" code="studentAffairs.mental.manage" size="sm" :disabled="!hasVersion(row)" @click="follow(row)">回访</AppPermissionButton>
              <AppPermissionButton v-if="allowed(row).includes('ESCALATE')" :allowed="canBtn('studentAffairs.mental.manage')" code="studentAffairs.mental.manage" size="sm" variant="secondary" danger :disabled="!hasVersion(row)" @click="gotoCrisis(row)">填写依据并升级</AppPermissionButton>
              <AppPermissionButton v-if="allowed(row).includes('CLOSE')" :allowed="canBtn('studentAffairs.mental.manage')" code="studentAffairs.mental.manage" size="sm" variant="secondary" :disabled="!hasVersion(row)" @click="close(row)">关闭</AppPermissionButton>
            </div>
            <span v-else class="sa-muted">当前状态无操作</span>
          </template>
        </DataTable>
        <p v-else class="sa-empty">暂无心理转介记录</p>
      </AppSectionCard>
    </AppGlobalState>

    <AppDrawer :visible="refDlg.visible" title="登记心理转介" @close="closeReferral">
      <div class="dr-form">
        <AppFormItem label="学生" required><AppStudentPicker v-model="refDlg.studentId" placeholder="按姓名 / 学号搜索" :disabled="actioning" /></AppFormItem>
        <AppFormItem label="转介去向"><AppSelect v-model="refDlg.channel" :options="CHANNELS" placeholder="可空" clearable :disabled="actioning" /></AppFormItem>
        <AppFormItem label="转介事由摘要（5-500字）" required>
          <AppTextarea ref="refInput" v-model="refDlg.reasonSummary" :rows="4" :maxlength="500" :disabled="actioning" placeholder="客观描述观察到的表现与转介必要性，不作诊断结论" />
          <AppQuickPhrases scene-key="sa.mental.referral" @pick="onPickReferral" />
          <p class="char-count">{{ refDlg.reasonSummary.trim().length }}/500</p>
        </AppFormItem>
        <AppInlineAlert v-if="refDlg.error" type="danger" :description="refDlg.error" />
      </div>
      <template #footer><AppButton variant="ghost" :disabled="actioning" @click="closeReferral">取消</AppButton><AppButton variant="primary" :loading="actioning" :disabled="!referralValid" @click="submitReferral">登记</AppButton></template>
    </AppDrawer>

    <AppConfirmDialog
      v-model:visible="txtDlg.visible"
      :title="txtDlg.title"
      :type="txtDlg.type"
      :message="txtDlg.message"
      :confirm-text="txtDlg.confirmText"
      require-reason
      :reason-min-length="5"
      :reason-label="txtDlg.reasonLabel"
      :phrase-scene-key="txtDlg.sceneKey"
      :submitting="actioning"
      @confirm="submitText"
    />
  </AppPageShell>
</template>

<script>
import {
  AppConfirmDialog, AppFormItem, AppGlobalState, AppInlineAlert, AppMetricCard, AppPageShell,
  AppPermissionButton, AppQuickPhrases, AppSectionCard, AppSelect, AppStatusTag,
  AppStudentPicker, AppTextarea
} from '@/components/common'
import { AppButton, AppDrawer } from '@/components/ui'
import { DataTable } from '@/components/business'
import { insertAtCursor, applyInsertion } from '@/utils/insertAtCursor'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairsB.api'
import { canCode } from '@/modules/studentAffairs/composables/permission'

const FOLLOW_COLUMNS = [
  { key: 'student', title: '学生' }, { key: 'level', title: '关注等级' },
  { key: 'status', title: '状态' }, { key: 'reason', title: '事由摘要' },
  { key: 'channel', title: '转介去向' }, { key: 'lastFollow', title: '最近回访' },
  { key: 'actions', title: '操作', align: 'right', width: '250px' }
]
const CHANNELS = ['校内咨询', '校医院', '专业机构', '家长'].map((value) => ({ value, label: value }))
const FALLBACK_ACTIONS = {
  REFERRED: ['FOLLOW', 'ESCALATE', 'CLOSE'],
  FOLLOWING: ['FOLLOW', 'ESCALATE', 'CLOSE'],
  ESCALATED: ['CLOSE'],
  CLOSED: []
}

export default {
  name: 'MentalReferralFollowView',
  props: { ctx: { type: Object, default: null } },
  components: {
    AppButton, AppConfirmDialog, AppDrawer, AppFormItem, AppGlobalState, AppInlineAlert,
    AppMetricCard, AppPageShell, AppPermissionButton, AppQuickPhrases, AppSectionCard,
    AppSelect, AppStatusTag, AppStudentPicker, AppTextarea, DataTable
  },
  data() {
    return {
      followColumns: FOLLOW_COLUMNS,
      loading: true, actioning: false, errorMessage: '', items: [],
      pagination: { page: 1, pageSize: 50, total: 0 },
      refDlg: { visible: false, studentId: '', channel: '校内咨询', reasonSummary: '', error: '' },
      txtDlg: { visible: false, kind: '', row: null, title: '', type: 'primary', confirmText: '确认', reasonLabel: '', sceneKey: '', message: '' }
    }
  },
  computed: {
    CHANNELS: () => CHANNELS,
    pageState() { return this.loading ? 'loading' : (this.errorMessage ? 'error' : 'ready') },
    referralValid() { const n = this.refDlg.reasonSummary.trim().length; return !!this.refDlg.studentId && n >= 5 && n <= 500 },
    metricCards() {
      return [
        { key: 'total', label: '全部记录', value: this.pagination.total, accent: 'info' },
        { key: 'page', label: '本页记录', value: this.items.length, accent: 'primary' },
        { key: 'open', label: '全量待回访', value: '—', accent: 'warning' },
        { key: 'crisis', label: '全量危机升级', value: '—', accent: 'risk' }
      ]
    }
  },
  mounted() { this.load() },
  methods: {
    canBtn(code) { return canCode(this.ctx, code) },
    hasVersion(row) { return row && row.version !== undefined && row.version !== null && row.version !== '' },
    allowed(row) { return Array.isArray(row.allowedActions) ? row.allowedActions : (FALLBACK_ACTIONS[row.status] || []) },
    async load() {
      this.loading = true; this.errorMessage = ''
      try {
        const res = await studentAffairsApi.listMentalAttention({ page: this.pagination.page, pageSize: this.pagination.pageSize })
        this.items = res.data.items || []
        this.pagination.total = res.data.total != null ? res.data.total : this.items.length
      } catch (e) { this.errorMessage = e.message || '转介回访工作台加载失败' }
      finally { this.loading = false }
    },
    onPageChange(page) { this.pagination.page = page; this.load() },
    createReferral() { this.refDlg = { visible: true, studentId: '', channel: '校内咨询', reasonSummary: '', error: '' } },
    closeReferral() { if (!this.actioning) this.refDlg.visible = false },
    onPickReferral(text) {
      const el = this.$refs.refInput && this.$refs.refInput.$refs.el
      if (!el) { this.refDlg.reasonSummary += text; return }
      const result = insertAtCursor(el, this.refDlg.reasonSummary, text)
      this.refDlg.reasonSummary = result.value
      this.$nextTick(() => applyInsertion(el, result.selStart, result.selEnd))
    },
    async submitReferral() {
      const dlg = this.refDlg
      const reason = dlg.reasonSummary.trim()
      if (!dlg.studentId) { dlg.error = '请选择学生'; return }
      if (reason.length < 5 || reason.length > 500) { dlg.error = '转介事由摘要需5-500字'; return }
      dlg.error = ''
      const ok = await this.runAction(() => studentAffairsApi.createMentalReferral({ studentId: dlg.studentId, level: 'FOCUS', channel: dlg.channel || '', reasonSummary: reason }))
      if (ok) { dlg.visible = false; this.pagination.page = 1 }
      else dlg.error = this.errorMessage
    },
    follow(row) {
      if (!this.allowed(row).includes('FOLLOW') || !this.hasVersion(row)) return
      this.txtDlg = {
        visible: true, kind: 'follow', row, title: `登记回访 · ${row.realName || '该生'}`,
        type: 'primary', confirmText: '确认登记', reasonLabel: '本次回访记录（5-300字）',
        sceneKey: 'sa.mental.followup', message: '记录应客观说明回访方式、学生当前情况和后续安排。'
      }
    },
    close(row) {
      if (!this.allowed(row).includes('CLOSE') || !this.hasVersion(row)) return
      this.txtDlg = {
        visible: true, kind: 'close', row, title: `关闭心理关注 · ${row.realName || '该生'}`,
        type: 'warning', confirmText: '确认关闭', reasonLabel: '关闭结论（5-300字）',
        sceneKey: 'sa.mental.close', message: '关闭后记录转为只读。请确认必要回访、转介或风险处置已经完成。'
      }
    },
    gotoCrisis(row) {
      if (!this.allowed(row).includes('ESCALATE') || !this.hasVersion(row)) return
      this.$router.push('/admin/student-affairs/mental/crisis')
    },
    async submitText({ reason }) {
      const dlg = this.txtDlg
      const text = (reason || '').trim()
      if (text.length < 5 || text.length > 300) { this.errorMessage = '处理说明需5-300字'; return }
      if (!dlg.row || !this.allowed(dlg.row).includes(dlg.kind === 'follow' ? 'FOLLOW' : 'CLOSE') || !this.hasVersion(dlg.row)) { this.errorMessage = '记录状态或版本已变化，请刷新后重试'; return }
      const task = dlg.kind === 'follow'
        ? () => studentAffairsApi.followMentalReferral(dlg.row.referralId, text, dlg.row.version)
        : () => studentAffairsApi.closeMentalReferral(dlg.row.referralId, text, dlg.row.version)
      const ok = await this.runAction(task)
      if (ok) dlg.visible = false
    },
    async runAction(task) {
      this.actioning = true; this.errorMessage = ''
      try { await task(); await this.load(); return true }
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
.sa-grid--metrics { display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:var(--space-4);margin-bottom:var(--space-4) }.sa-actions { display:flex;flex-wrap:wrap;gap:var(--space-2) }.sa-muted { color:var(--text-tertiary);font-size:12px }.sa-empty { color:var(--text-tertiary);padding:var(--space-4);text-align:center }.dr-form { display:flex;flex-direction:column;gap:var(--space-4) }.char-count { margin:4px 0 0;text-align:right;color:var(--text-tertiary);font-size:12px }
@media(max-width:960px){.sa-grid--metrics{grid-template-columns:1fr 1fr}}
@import '@/styles/module-page.css';
</style>
