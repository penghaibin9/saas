<template>
  <AppPageShell
    title="心理关注名单"
    subtitle="强敏感红线：列表仅显示摘要与「需关注」标记；心理明细须授权角色 + 填写原因方可查看，且全程留痕。"
    role-name="心理老师 / 授权辅导员 / 学工处(专项授权)"
    data-scope-name="PSY_STUDENT 逐生授权范围"
    watermark-purpose="心理关注名单查看"
  >
    <template #actions>
      <AppPermissionButton code="studentAffairs.risk.psyDetail.view" :loading="actioning" @click="createReferral">
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
      <div class="sa-grid sa-grid--metrics">
        <AppMetricCard v-for="card in metricCards" :key="card.key" :title="card.label" :value="card.value" :accent="card.accent" />
      </div>

      <AppSectionCard title="关注名单（明细遮蔽）">
        <div class="sa-toolbar">
          <AppSelect v-model="filters.level" :options="LEVEL_FILTERS" placeholder="全部等级" class="sa-pick" @change="load" />
          <span class="sa-hint">共 {{ total }} 条 · 明细默认脱敏</span>
        </div>

        <DataTable v-if="items.length" :columns="attentionColumns" :rows="items" row-key="referralId">
          <template #cell-student="{ row }">
            <div class="mp-cell-main">{{ row.realName || '未命名学生' }}</div>
            <div class="mp-cell-sub">{{ row.studentNo || row.studentId }}</div>
          </template>
          <template #cell-level="{ row }"><AppStatusTag :type="levelKind(row.level)" :label="row.levelLabel || row.level" /></template>
          <template #cell-status="{ row }"><AppStatusTag :type="statusKind(row.status)" :label="row.statusLabel || row.status" /></template>
          <template #cell-reason="{ row }">{{ row.reasonSummary || '—' }}</template>
          <template #cell-channel="{ row }">{{ row.channel || '—' }}</template>
          <template #cell-lastFollow="{ row }">{{ (row.lastFollowTime || '').slice(0, 16) || '—' }}</template>
          <template #cell-note="{ row }"><span :class="{ 'sa-mask': row.noteMasked }">{{ row.note }}</span></template>
          <template #cell-actions="{ row }">
            <div class="sa-actions">
              <AppPermissionButton code="studentAffairs.risk.psyDetail.view" size="sm" variant="secondary" :loading="actioning" @click="reveal(row)">
                查看明细
              </AppPermissionButton>
              <AppPermissionButton v-if="row.status !== 'CLOSED'" code="studentAffairs.risk.psyDetail.view" size="sm" variant="secondary" :loading="actioning" @click="follow(row)">
                回访
              </AppPermissionButton>
              <AppPermissionButton v-if="row.status !== 'CLOSED'" code="studentAffairs.risk.psyDetail.view" size="sm" :loading="actioning" @click="close(row)">
                关闭
              </AppPermissionButton>
            </div>
          </template>
        </DataTable>
        <p v-else class="sa-empty">当前授权范围内暂无心理关注记录</p>
      </AppSectionCard>
    </AppGlobalState>

    <!-- 查看心理明细：敏感操作，原因写入 SENSITIVE_VIEW 安全审计。
         此处刻意不挂快捷用语——现有 common.revealReason 词条全是「核对联系方式/家庭经济」口径，
         与「查阅心理咨询明细」不是一回事，挂上会诱导老师填错审计原因。 -->
    <AppConfirmDialog
      v-model:visible="revDlg.visible" :title="`查看心理明细 · ${revDlg.who}`" type="warning"
      confirm-text="确认查看" require-reason :reason-min-length="5"
      reason-label="查看原因（≥5 字，将写入安全审计）"
      description="查看心理明细属敏感操作。原因、查看人、时间将完整留痕，供事后追责。请如实填写本次查阅的业务必要性。"
      :submitting="actioning" @confirm="submitReveal"
    >
      <AppInlineAlert v-if="revDlg.error" type="danger" :description="revDlg.error" />
    </AppConfirmDialog>

    <!-- 登记转介：原为「学生ID→事由摘要→等级码→去向」4 连原生弹窗 -->
    <AppDrawer :visible="refDlg.visible" title="登记心理转介" @close="refDlg.visible = false">
      <div class="dr-form">
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

    <!-- 回访 / 关闭：统一必填说明弹窗，词条已逐条核对与动作语义一致 -->
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
/** 与后端心理关注等级取值一一对应。 */
const LEVELS = [
  { value: 'GENERAL', label: '一般关注' },
  { value: 'FOCUS', label: '重点关注' },
  { value: 'CRISIS', label: '危机' }
]
const LEVEL_FILTERS = [{ value: '', label: '全部等级' }, ...LEVELS]
/** 转介去向：沿用原 prompt 提示里的四个既有选项，未自行扩充。 */
const CHANNELS = ['校内咨询', '校医院', '专业机构', '家长'].map((v) => ({ value: v, label: v }))

export default {
  name: 'MentalAttentionListView',
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
      loading: true, actioning: false, errorMessage: '', items: [], total: 0, filters: { level: '' },
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
      const crisis = this.items.filter((r) => r.level === 'CRISIS' && r.status !== 'CLOSED').length
      const following = this.items.filter((r) => r.status === 'FOLLOWING').length
      const closed = this.items.filter((r) => r.status === 'CLOSED').length
      return [
        { key: 'total', label: '关注记录', value: this.total, accent: 'primary' },
        { key: 'crisis', label: '在册危机', value: crisis, accent: crisis ? 'risk' : 'success' },
        { key: 'following', label: '回访中', value: following, accent: following ? 'warning' : 'info' },
        { key: 'closed', label: '已结案', value: closed, accent: 'success' }
      ]
    }
  },
  mounted() {
    this.load()
  },
  methods: {
    async load() {
      this.loading = true
      this.errorMessage = ''
      try {
        const res = await studentAffairsApi.listMentalAttention({ level: this.filters.level, page: 1, pageSize: 50 })
        this.items = res.data.items || []
        this.total = res.data.total || this.items.length
      } catch (e) {
        this.errorMessage = e.message || '心理关注名单加载失败'
      } finally {
        this.loading = false
      }
    },
    /* ── 查看心理明细（敏感，SENSITIVE_VIEW 审计） ── */
    reveal(row) {
      this.revDlg = { visible: true, row, who: row.realName || row.studentNo || '该生', error: '' }
    },
    async submitReveal({ reason }) {
      const row = this.revDlg.row
      this.actioning = true; this.revDlg.error = ''
      try {
        const res = await studentAffairsApi.getMentalReferral(row.referralId, reason.trim())
        if (res.data.noteMasked) {
          // 无 PSY_STUDENT 专项授权：留在弹窗里说明，不用 alert 打断
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
    /* ── 登记转介 ── */
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
    /* ── 回访 / 关闭 ── */
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
      const fn = d.kind === 'follow'
        ? () => studentAffairsApi.followMentalReferral(d.row.referralId, reason.trim())
        : () => studentAffairsApi.closeMentalReferral(d.row.referralId, reason.trim())
      const ok = await this.runAction(fn)
      if (ok) d.visible = false
    },
    /** @returns {boolean} 是否成功；失败时保留弹窗与已填内容。 */
    async runAction(fn) {
      this.actioning = true
      this.errorMessage = ''
      try {
        await fn()
        await this.load()
        return true
      } catch (e) {
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
.sa-grid--metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--space-4);
  margin-bottom: var(--space-4);
}
.sa-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-3);
  margin-bottom: var(--space-4);
}
.sa-pick {
  min-width: 160px;
}
.dr-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}
.dr-hint {
  margin: var(--space-1) 0 0;
  color: var(--text-tertiary);
  font-size: var(--font-size-sm);
}
.sa-hint {
  color: var(--text-tertiary);
}
.sa-mask {
  color: var(--text-tertiary);
  font-style: italic;
}
.sa-actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}
.sa-empty {
  color: var(--text-tertiary);
  padding: var(--space-4);
  text-align: center;
}
@media (max-width: 960px) {
  .sa-grid--metrics {
    grid-template-columns: 1fr;
  }
}
@import '@/styles/module-page.css';
</style>
