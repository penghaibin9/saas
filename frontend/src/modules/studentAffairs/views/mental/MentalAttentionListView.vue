<template>
  <AppPageShell
    title="心理关注名单"
    subtitle="强敏感红线：列表仅显示摘要与「需关注」标记；心理明细须授权角色 + 填写原因方可查看，且全程留痕。"
    role-name="心理老师 / 授权辅导员 / 学工处(专项授权)"
    data-scope-name="PSY_STUDENT 逐生授权范围"
    watermark-purpose="心理关注名单查看"
  >
    <template #actions>
      <AppPermissionButton :allowed="canBtn('studentAffairs.mental.manage')" code="studentAffairs.mental.manage" :loading="actioning" @click="createReferral">
        登记转介
      </AppPermissionButton>
    </template>

    <AppGlobalState
      :state="pageState"
      :description="errorMessage"
      loading-text="正在加载心理关注名单..."
      @retry="load"
      @back="$router.push('/admin/student-affairs/dashboard')"
    >
      <section class="sa-summary-strip mental-privacy-summary">
        <div class="sa-summary-strip__content">
          <span class="sa-summary-strip__eyebrow">心理信息保护红线</span>
          <h2 class="sa-summary-strip__title">名单只展示必要摘要；查看心理明文必须有逐生授权、填写业务原因并留下安全审计</h2>
          <p class="sa-summary-strip__text">当前授权范围共 {{ total }} 条关注记录。先看等级、状态、事由摘要和最近回访；只有业务确有必要时才点击“查看明细”。</p>
        </div>
        <div class="sa-summary-strip__actions">
          <AppPermissionButton :allowed="canBtn('studentAffairs.mental.manage')" code="studentAffairs.mental.manage" :loading="actioning" @click="createReferral">登记转介</AppPermissionButton>
        </div>
      </section>

      <div class="sa-workflow-strip" aria-label="心理关注处理流程">
        <div class="sa-workflow-step" data-step="1"><strong>登记转介</strong><br>客观记录关注等级与事由摘要</div>
        <div class="sa-workflow-step" data-step="2"><strong>查看摘要</strong><br>默认只读必要业务信息和脱敏内容</div>
        <div class="sa-workflow-step" data-step="3"><strong>授权查明细</strong><br>填写原因并记录敏感查看审计</div>
        <div class="sa-workflow-step" data-step="4"><strong>回访 / 关闭</strong><br>持续记录处置，满足条件后关闭</div>
      </div>

      <div class="sa-grid sa-grid--metrics">
        <AppMetricCard v-for="card in metricCards" :key="card.key" :title="card.label" :value="card.value" :accent="card.accent" />
      </div>

      <AppSectionCard title="关注名单（明细默认遮蔽）">
        <div class="mental-list-note">
          <strong>查看顺序：</strong>学生 → 关注等级 → 当前状态 → 事由摘要 → 最近回访。心理明细列保持脱敏，点击查看时必须说明业务必要性。
        </div>
        <div class="sa-toolbar sa-filter-bar">
          <AppSelect v-model="filters.level" :options="LEVEL_FILTERS" placeholder="全部等级" class="sa-pick" @change="onFilterChange" />
          <span class="sa-hint">共 {{ total }} 条 · 当前页 {{ items.length }} 条 · 明细默认脱敏</span>
        </div>

        <DataTable v-if="items.length || pagination.total > 0" :columns="attentionColumns" :rows="items" row-key="referralId"
                   :pagination="pagination" @page-change="onPageChange">
          <template #cell-student="{ row }">
            <div class="mp-cell-main">{{ row.realName || '未命名学生' }}</div>
            <div class="mp-cell-sub">{{ row.studentNo || row.studentId }}</div>
          </template>
          <template #cell-level="{ row }"><AppStatusTag :type="levelKind(row.level)" :label="row.levelLabel || row.level" /></template>
          <template #cell-status="{ row }"><AppStatusTag :type="statusKind(row.status)" :label="row.statusLabel || row.status" /></template>
          <template #cell-reason="{ row }"><span class="mental-reason sa-cell-wrap">{{ row.reasonSummary || '—' }}</span></template>
          <template #cell-channel="{ row }">{{ row.channel || '—' }}</template>
          <template #cell-lastFollow="{ row }"><span :class="row.lastFollowTime ? 'mental-followed' : 'mental-not-followed'">{{ (row.lastFollowTime || '').slice(0, 16) || '尚未回访' }}</span></template>
          <template #cell-note="{ row }"><span :class="row.noteMasked ? 'sa-mask' : 'mental-revealed'">{{ row.note }}</span></template>
          <template #cell-actions="{ row }">
            <div class="sa-actions">
              <AppPermissionButton :allowed="canBtn('studentAffairs.risk.psyDetail.view')" code="studentAffairs.risk.psyDetail.view" size="sm" variant="secondary" :loading="actioning" @click="reveal(row)">
                查看明细
              </AppPermissionButton>
              <AppPermissionButton :allowed="canBtn('studentAffairs.mental.manage')" v-if="row.status !== 'CLOSED'" code="studentAffairs.mental.manage" size="sm" variant="secondary" :loading="actioning" @click="follow(row)">
                回访
              </AppPermissionButton>
              <AppPermissionButton :allowed="canBtn('studentAffairs.mental.manage')" v-if="row.status !== 'CLOSED'" code="studentAffairs.mental.manage" size="sm" :loading="actioning" @click="close(row)">
                关闭
              </AppPermissionButton>
            </div>
          </template>
        </DataTable>
        <p v-else class="sa-empty">当前授权范围内暂无心理关注记录。需要建立转介时，可点击“登记转介”。</p>
      </AppSectionCard>
    </AppGlobalState>

    <AppConfirmDialog
      v-model:visible="revDlg.visible" :title="`查看心理明细 · ${revDlg.who}`" type="warning"
      confirm-text="确认查看" require-reason :reason-min-length="5"
      reason-label="查看原因（≥5 字，将写入安全审计）"
      description="查看心理明细属敏感操作。原因、查看人、时间将完整留痕，供事后追责。请如实填写本次查阅的业务必要性。"
      :submitting="actioning" @confirm="submitReveal"
    >
      <AppInlineAlert v-if="revDlg.error" type="danger" :description="revDlg.error" />
    </AppConfirmDialog>

    <AppDrawer :visible="refDlg.visible" title="登记心理转介" mode="modal" size="medium" @close="refDlg.visible = false">
      <div class="dr-form">
        <div class="mental-form-note">只记录客观表现、关注等级与转介必要性，不在此处填写诊断性结论。</div>
        <AppFormItem label="学生" required>
          <AppStudentPicker v-model="refDlg.studentId"
                            placeholder="按姓名 / 学号搜索" :disabled="actioning" />
        </AppFormItem>
        <AppFormItem label="关注等级" required>
          <AppSelect v-model="refDlg.level" :options="LEVELS" :disabled="actioning" />
        </AppFormItem>
        <AppFormItem label="转介去向">
          <AppSelect v-model="refDlg.channel" :options="CHANNELS" placeholder="可空" clearable :disabled="actioning" />
        </AppFormItem>
        <AppFormItem label="转介事由摘要（≥5 字）" required>
          <AppTextarea ref="refInput" v-model="refDlg.reasonSummary" :rows="3" :maxlength="500" :disabled="actioning"
                       placeholder="客观描述观察到的表现与转介必要性" />
          <AppQuickPhrases scene-key="sa.mental.referral" @pick="onPickReferral" />
          <p class="dr-hint">仅记录客观表现与转介事由，不作诊断结论。本字段按心理红线脱敏存储。</p>
        </AppFormItem>
        <AppInlineAlert v-if="refDlg.error" type="danger" :description="refDlg.error" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="actioning" @click="refDlg.visible = false">取消</AppButton>
        <AppButton variant="primary" :loading="actioning" @click="submitReferral">登记</AppButton>
      </template>
    </AppDrawer>

    <AppConfirmDialog
      v-model:visible="txtDlg.visible" :title="txtDlg.title" :type="txtDlg.type"
      :confirm-text="txtDlg.confirmText" require-reason :reason-min-length="5"
      :reason-label="txtDlg.reasonLabel" :phrase-scene-key="txtDlg.sceneKey"
      :submitting="actioning" @confirm="submitText"
    />
  </AppPageShell>
</template>

<script>
import {
  AppConfirmDialog,
  AppFormItem,
  AppGlobalState,
  AppInlineAlert,
  AppMetricCard,
  AppPageShell,
  AppPermissionButton,
  AppQuickPhrases,
  AppSectionCard,
  AppSelect,
  AppStatusTag,
  AppStudentPicker,
  AppTextarea
} from '@/components/common'
import { AppButton, AppDrawer } from '@/components/ui'
import { DataTable } from '@/components/business'
import { insertAtCursor, applyInsertion } from '@/utils/insertAtCursor'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairsB.api'
import { toast } from '@/utils/toast'
import { canCode } from '@/modules/studentAffairs/composables/permission'

const ATTENTION_COLUMNS = [
  { key: 'student', title: '学生' },
  { key: 'level', title: '关注等级' },
  { key: 'status', title: '状态' },
  { key: 'reason', title: '事由摘要' },
  { key: 'channel', title: '转介去向' },
  { key: 'lastFollow', title: '最近回访' },
  { key: 'note', title: '心理明细' },
  { key: 'actions', title: '操作', align: 'right', width: '260px' }
]
const LEVELS = [
  { value: 'GENERAL', label: '一般关注' },
  { value: 'FOCUS', label: '重点关注' },
  { value: 'CRISIS', label: '危机' }
]
const LEVEL_FILTERS = [{ value: '', label: '全部等级' }, ...LEVELS]
const CHANNELS = ['校内咨询', '校医院', '专业机构', '家长'].map((v) => ({ value: v, label: v }))

export default {
  name: 'MentalAttentionListView',
  props: { ctx: { type: Object, default: null } },
  components: {
    AppButton,
    AppConfirmDialog,
    AppDrawer,
    AppFormItem,
    AppGlobalState,
    AppInlineAlert,
    AppMetricCard,
    AppPageShell,
    AppPermissionButton,
    AppQuickPhrases,
    AppSectionCard,
    AppSelect,
    AppStatusTag,
    AppStudentPicker,
    AppTextarea,
    DataTable
  },
  data() {
    return {
      attentionColumns: ATTENTION_COLUMNS,
      loading: true, actioning: false, errorMessage: '', items: [], total: 0, statusCounts: null,
      pagination: { page: 1, pageSize: 20, total: 0 }, filters: { level: '' },
      revDlg: { visible: false, row: null, who: '', error: '' },
      refDlg: { visible: false, studentId: '', level: 'FOCUS', channel: '校内咨询', reasonSummary: '', error: '' },
      txtDlg: { visible: false, kind: '', row: null, title: '', type: 'primary', confirmText: '确认', reasonLabel: '', sceneKey: '' }
    }
  },
  computed: {
    LEVELS: () => LEVELS,
    LEVEL_FILTERS: () => LEVEL_FILTERS,
    CHANNELS: () => CHANNELS,
    pageState() {
      if (this.loading) return 'loading'
      if (this.errorMessage) return 'error'
      return 'ready'
    },
    metricCards() {
      const count = (status) => this.statusCounts === null ? '—' : (this.statusCounts[status] || 0)
      return [
        { key: 'total', label: '关注记录', value: this.total, accent: 'primary' },
        { key: 'crisis', label: '在册危机', value: '—', accent: 'risk' },
        { key: 'following', label: '回访中', value: count('FOLLOWING'), accent: 'info' },
        { key: 'closed', label: '已结案', value: count('CLOSED'), accent: 'success' }
      ]
    }
  },
  mounted() {
    this.load()
  },
  methods: {
    canBtn(code) { return canCode(this.ctx, code) },
    async load() {
      this.loading = true
      this.errorMessage = ''
      try {
        const res = await studentAffairsApi.listMentalAttention({
          level: this.filters.level, page: this.pagination.page, pageSize: this.pagination.pageSize
        })
        this.items = res.data.items || []
        this.total = res.data.total || this.items.length
        this.statusCounts = res.data.statusCounts || null
        this.pagination.total = this.total
      } catch (e) {
        this.errorMessage = e.message || '心理关注名单加载失败'
      } finally {
        this.loading = false
      }
    },
    onFilterChange() {
      this.pagination.page = 1
      this.load()
    },
    onPageChange(page) {
      this.pagination.page = page
      this.load()
    },
    reveal(row) {
      this.revDlg = { visible: true, row, who: row.realName || row.studentNo || '该生', error: '' }
    },
    async submitReveal({ reason }) {
      const row = this.revDlg.row
      this.actioning = true; this.revDlg.error = ''
      try {
        const res = await studentAffairsApi.getMentalReferral(row.referralId, reason.trim())
        if (res.data.noteMasked) {
          this.revDlg.error = '您对该生的心理明细无查看授权（需 PSY_STUDENT 专项授权），仅可见摘要。本次查看请求已留痕。'
        } else {
          row.note = res.data.note
          row.noteMasked = false
          this.revDlg.visible = false
          toast.success('已展开心理明细，查看原因已写入安全审计（SENSITIVE_VIEW）。')
        }
      } catch (e) {
        this.revDlg.error = e.message || '查看明细失败'
      } finally {
        this.actioning = false
      }
    },
    createReferral() {
      this.refDlg = { visible: true, studentId: '', level: 'FOCUS', channel: '校内咨询', reasonSummary: '', error: '' }
    },
    onPickReferral(text) {
      const el = this.$refs.refInput && this.$refs.refInput.$refs.el
      if (!el) { this.refDlg.reasonSummary += text; return }
      const r = insertAtCursor(el, this.refDlg.reasonSummary, text)
      this.refDlg.reasonSummary = r.value
      this.$nextTick(() => applyInsertion(el, r.selStart, r.selEnd))
    },
    async submitReferral() {
      const d = this.refDlg
      if (!d.studentId) { d.error = '请选择学生'; return }
      if (d.reasonSummary.trim().length < 5) { d.error = '转介事由摘要不少于 5 字'; return }
      d.error = ''
      const ok = await this.runAction(() => studentAffairsApi.createMentalReferral({
        studentId: d.studentId, level: d.level, channel: d.channel || '', reasonSummary: d.reasonSummary.trim()
      }))
      if (ok) d.visible = false
      else d.error = this.errorMessage
    },
    follow(row) {
      this.txtDlg = {
        visible: true, kind: 'follow', row, title: `登记回访 · ${row.realName || '该生'}`, type: 'primary',
        confirmText: '确认登记', reasonLabel: '本次回访记录（≥5 字）', sceneKey: 'sa.mental.followup'
      }
    },
    close(row) {
      this.txtDlg = {
        visible: true, kind: 'close', row, title: `关闭心理关注 · ${row.realName || '该生'}`, type: 'warning',
        confirmText: '确认关闭', reasonLabel: '关闭结论（≥5 字）', sceneKey: 'sa.mental.close'
      }
    },
    async submitText({ reason }) {
      const d = this.txtDlg
      const ver = d.row && d.row.version
      const fn = d.kind === 'follow'
        ? () => studentAffairsApi.followMentalReferral(d.row.referralId, reason.trim(), ver)
        : () => studentAffairsApi.closeMentalReferral(d.row.referralId, reason.trim(), ver)
      const ok = await this.runAction(fn)
      if (ok) d.visible = false
    },
    async runAction(fn) {
      this.actioning = true
      this.errorMessage = ''
      try {
        await fn()
        await this.load()
        return true
      } catch (e) {
        if (e.bizCode === 'APPROVAL_VERSION_CONFLICT') {
          this.errorMessage = '该记录已被其他人处理，数据已刷新'
          await this.load()
          return false
        }
        this.errorMessage = e.message || '操作失败'
        return false
      } finally {
        this.actioning = false
      }
    },
    levelKind(level) {
      if (level === 'CRISIS') return 'danger'
      if (level === 'FOCUS') return 'warning'
      return 'info'
    },
    statusKind(status) {
      if (status === 'CLOSED') return 'success'
      if (status === 'ESCALATED') return 'danger'
      if (status === 'FOLLOWING') return 'warning'
      return 'info'
    }
  }
}
</script>

<style scoped>
.sa-grid--metrics { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: var(--space-3); margin-bottom: var(--space-4); }
.mental-privacy-summary { border-color: var(--warning-300, #fcd34d); background: var(--warning-50, #fffbeb); }
.mental-list-note, .mental-form-note { margin-bottom: var(--space-3); padding: 10px 12px; border: 1px solid var(--warning-200, #fde68a); border-radius: var(--radius-md); background: var(--warning-50, #fffbeb); color: var(--text-secondary); font-size: var(--font-size-sm); line-height: 1.65; }
.sa-toolbar { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: var(--space-3); margin-bottom: var(--space-3); }
.sa-pick { min-width: 180px; }
.dr-form { display: flex; flex-direction: column; gap: var(--space-4); }
.dr-hint { margin: var(--space-1) 0 0; color: var(--text-tertiary); font-size: var(--font-size-sm); }
.sa-hint { color: var(--text-tertiary); font-size: var(--font-size-xs); }
.mental-reason { color: var(--text-secondary); }
.mental-followed { color: var(--success-700, #15803d); font-weight: 600; }
.mental-not-followed { color: var(--warning-700, #b45309); font-weight: 600; }
.sa-mask { color: var(--text-tertiary); font-style: italic; }
.mental-revealed { color: var(--danger-700, #b91c1c); font-size: var(--font-size-xs); }
.sa-actions { display: flex; flex-wrap: wrap; gap: var(--space-2); justify-content: flex-end; }
@media (max-width: 960px) { .sa-grid--metrics { grid-template-columns: 1fr 1fr; } }
@media (max-width: 640px) { .sa-grid--metrics { grid-template-columns: 1fr; } .sa-toolbar { align-items: stretch; } .sa-pick { width: 100%; } }
@import '@/styles/module-page.css';
</style>
