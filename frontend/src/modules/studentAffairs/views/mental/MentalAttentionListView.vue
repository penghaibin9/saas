<template>
  <AppPageShell
    title="心理关注名单"
    subtitle="强敏感红线：列表仅显示摘要与「需关注」标记；心理明细须授权角色 + 填写原因方可查看，且全程留痕。"
    role-name="心理老师 / 授权辅导员 / 学工处(专项授权)"
    data-scope-name="PSY_STUDENT 逐生授权范围"
    watermark-purpose="心理关注名单查看"
  >
    <template #actions>
      <AppPermissionButton code="studentAffairs.risk.psyDetail.view" :loading="actioning" @click="openCreateReferral">
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
          <select v-model="filters.level" @change="onFilterChange">
            <option value="">全部等级</option>
            <option value="GENERAL">一般关注</option>
            <option value="FOCUS">重点关注</option>
            <option value="CRISIS">危机</option>
          </select>
          <span class="sa-hint">共 {{ pagination.total }} 条 · 明细默认脱敏</span>
        </div>

        <table class="sa-table">
          <thead>
            <tr>
              <th>学生</th>
              <th>关注等级</th>
              <th>状态</th>
              <th>事由摘要</th>
              <th>转介去向</th>
              <th>最近回访</th>
              <th>心理明细</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in items" :key="row.referralId">
              <td>
                <strong>{{ row.realName || '未命名学生' }}</strong>
                <small>{{ row.studentNo || row.studentId }}</small>
              </td>
              <td><AppStatusTag :type="levelKind(row.level)" :label="row.levelLabel || row.level" /></td>
              <td><AppStatusTag :type="statusKind(row.status)" :label="row.statusLabel || row.status" /></td>
              <td>{{ row.reasonSummary || '—' }}</td>
              <td>{{ row.channel || '—' }}</td>
              <td><AppDateDisplay :value="row.lastFollowTime" mode="datetime" empty-text="—" /></td>
              <td>
                <span :class="{ 'sa-mask': row.noteMasked }">{{ row.note }}</span>
              </td>
              <td class="sa-actions">
                <AppPermissionButton code="studentAffairs.risk.psyDetail.view" size="sm" variant="secondary" :loading="actioning" @click="askReveal(row)">
                  查看明细
                </AppPermissionButton>
                <AppPermissionButton v-if="row.status !== 'CLOSED'" code="studentAffairs.risk.psyDetail.view" size="sm" variant="secondary" :loading="actioning" @click="askFollow(row)">
                  回访
                </AppPermissionButton>
                <AppPermissionButton v-if="row.status !== 'CLOSED'" code="studentAffairs.risk.psyDetail.view" size="sm" :loading="actioning" @click="askClose(row)">
                  关闭
                </AppPermissionButton>
              </td>
            </tr>
            <tr v-if="!items.length">
              <td colspan="8" class="sa-empty">当前授权范围内暂无心理关注记录</td>
            </tr>
          </tbody>
        </table>

        <AppPagination
          :page="pagination.page"
          :page-size="pagination.pageSize"
          :total="pagination.total"
          @change="onPageChange"
        />
      </AppSectionCard>
    </AppGlobalState>

    <!-- 查看心理明细：强敏感红线，必须填写查看原因（≥5字）方可查看，并写入安全审计（SENSITIVE_VIEW） -->
    <AppConfirmDialog
      v-model:visible="revealDialog.visible"
      title="查看心理明细"
      :message="revealMessage"
      type="warning"
      require-reason
      :reason-min-length="5"
      reason-label="查看原因"
      reason-placeholder="请填写查看原因（不少于 5 字，将写入安全审计）"
      phrase-scene-key="common.revealReason"
      confirm-text="查看明细"
      :submitting="actioning"
      @confirm="confirmReveal"
      @cancel="revealDialog.visible = false"
    />

    <!-- 回访 / 关闭：共用同一二次确认弹窗，均要求填写内容（≥5字），与原 window.prompt 校验口径一致 -->
    <AppConfirmDialog
      v-model:visible="actionDialog.visible"
      :title="actionDialogTitle"
      :message="actionDialogMessage"
      :type="actionDialogType"
      require-reason
      :reason-min-length="5"
      :reason-label="actionDialogReasonLabel"
      :phrase-scene-key="actionDialogPhraseSceneKey"
      :confirm-text="actionDialogConfirmText"
      :submitting="actioning"
      @confirm="confirmActionDialog"
      @cancel="actionDialog.visible = false"
    />

    <!-- 登记转介 -->
    <AppDrawer v-model:visible="referralDrawer.visible" title="登记转介">
      <div class="sa-form">
        <AppFormItem label="学生 ID" required :error="referralDrawer.errors.studentId">
          <AppTextInput v-model="referralDrawer.form.studentId" placeholder="请输入学生 ID" :disabled="actioning" />
        </AppFormItem>
        <AppFormItem label="关注等级">
          <AppSelect v-model="referralDrawer.form.level" :options="levelOptions" :disabled="actioning" />
        </AppFormItem>
        <AppFormItem label="转介去向">
          <AppTextInput v-model="referralDrawer.form.channel" placeholder="校医院/专业机构/家长/校内咨询（可空）" :disabled="actioning" />
        </AppFormItem>
        <AppFormItem label="事由摘要" required :error="referralDrawer.errors.reasonSummary">
          <AppQuickPhrases scene-key="sa.mental.referral" @pick="onPickReasonSummary" />
          <AppTextarea ref="reasonSummaryTa" v-model="referralDrawer.form.reasonSummary" placeholder="人工填写，非诊断，不少于 5 字" :disabled="actioning" />
        </AppFormItem>
        <AppInlineAlert v-if="referralDrawer.errorMessage" type="danger" :description="referralDrawer.errorMessage" />
      </div>
      <template #footer>
        <button type="button" class="sa-btn" :disabled="actioning" @click="referralDrawer.visible = false">取消</button>
        <AppPermissionButton code="studentAffairs.risk.psyDetail.view" :loading="actioning" @click="submitCreateReferral">
          提交转介
        </AppPermissionButton>
      </template>
    </AppDrawer>
  </AppPageShell>
</template>

<script>
import {
  AppConfirmDialog,
  AppDateDisplay,
  AppFormItem,
  AppGlobalState,
  AppInlineAlert,
  AppMetricCard,
  AppPageShell,
  AppPagination,
  AppPermissionButton,
  AppQuickPhrases,
  AppSectionCard,
  AppSelect,
  AppStatusTag,
  AppTextarea,
  AppTextInput
} from '@/components/common'
import AppDrawer from '@/components/ui/AppDrawer.vue'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairsB.api'
import { toast } from '@/utils/toast'
import { insertAtCursor, applyInsertion } from '@/utils/insertAtCursor'

const LEVEL_OPTIONS = [
  { label: '一般关注', value: 'GENERAL' },
  { label: '重点关注', value: 'FOCUS' },
  { label: '危机', value: 'CRISIS' }
]

function freshReferralForm() {
  return { studentId: '', level: 'FOCUS', channel: '校内咨询', reasonSummary: '' }
}

export default {
  name: 'MentalAttentionListView',
  components: {
    AppConfirmDialog,
    AppDateDisplay,
    AppDrawer,
    AppFormItem,
    AppGlobalState,
    AppInlineAlert,
    AppMetricCard,
    AppPageShell,
    AppPagination,
    AppPermissionButton,
    AppQuickPhrases,
    AppSectionCard,
    AppSelect,
    AppStatusTag,
    AppTextarea,
    AppTextInput
  },
  data() {
    return {
      loading: true,
      actioning: false,
      errorMessage: '',
      items: [],
      filters: { level: '' },
      pagination: { page: 1, pageSize: 50, total: 0 },
      revealDialog: { visible: false, row: null },
      actionDialog: { visible: false, kind: '', row: null },
      referralDrawer: { visible: false, form: freshReferralForm(), errors: {}, errorMessage: '' },
      levelOptions: LEVEL_OPTIONS
    }
  },
  computed: {
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
        { key: 'total', label: '关注记录', value: this.pagination.total, accent: 'primary' },
        { key: 'crisis', label: '在册危机', value: crisis, accent: crisis ? 'risk' : 'success' },
        { key: 'following', label: '回访中', value: following, accent: following ? 'warning' : 'info' },
        { key: 'closed', label: '已结案', value: closed, accent: 'success' }
      ]
    },
    revealMessage() {
      const row = this.revealDialog.row
      const name = row ? (row.realName || row.studentNo || row.studentId) : ''
      return `确认查看「${name}」的心理明细？该操作将写入安全审计（SENSITIVE_VIEW）。`
    },
    actionDialogTitle() {
      return this.actionDialog.kind === 'close' ? '关闭转介' : '登记回访'
    },
    actionDialogMessage() {
      const row = this.actionDialog.row
      const name = row ? (row.realName || row.studentNo || row.studentId) : ''
      return this.actionDialog.kind === 'close'
        ? `确认关闭「${name}」的心理转介？关闭后需重新转介才能再次跟进。`
        : `为「${name}」登记本次回访记录。`
    },
    actionDialogReasonLabel() {
      return this.actionDialog.kind === 'close' ? '关闭结论' : '回访记录'
    },
    actionDialogPhraseSceneKey() {
      return this.actionDialog.kind === 'close' ? 'sa.mental.close' : 'sa.mental.followup'
    },
    actionDialogConfirmText() {
      return this.actionDialog.kind === 'close' ? '确认关闭' : '提交回访'
    },
    actionDialogType() {
      return this.actionDialog.kind === 'close' ? 'warning' : 'primary'
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
        const res = await studentAffairsApi.listMentalAttention({
          level: this.filters.level,
          page: this.pagination.page,
          pageSize: this.pagination.pageSize
        })
        this.items = res.data.items || []
        this.pagination.total = res.data.total || this.items.length
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
    onPageChange(next) {
      this.pagination.page = next.page || next
      if (next.pageSize) this.pagination.pageSize = next.pageSize
      this.load()
    },
    askReveal(row) {
      this.revealDialog = { visible: true, row }
    },
    async confirmReveal({ reason }) {
      const row = this.revealDialog.row
      this.revealDialog.visible = false
      if (!row) return
      this.actioning = true
      try {
        const res = await studentAffairsApi.getMentalReferral(row.referralId, reason)
        if (res.data.noteMasked) {
          toast.warning('您在该生的心理明细无查看授权（需 PSY_STUDENT 专项授权），仅可见摘要。')
        } else {
          row.note = res.data.note
          row.noteMasked = false
          toast.success('已记录查看原因并写入安全审计（SENSITIVE_VIEW）。')
        }
      } catch (e) {
        this.errorMessage = e.message || '查看明细失败'
      } finally {
        this.actioning = false
      }
    },
    openCreateReferral() {
      this.referralDrawer = { visible: true, form: freshReferralForm(), errors: {}, errorMessage: '' }
    },
    onPickReasonSummary(text) {
      const el = this.$refs.reasonSummaryTa && this.$refs.reasonSummaryTa.$refs && this.$refs.reasonSummaryTa.$refs.el
      if (!el) return
      const { value, selStart, selEnd } = insertAtCursor(el, this.referralDrawer.form.reasonSummary, text)
      this.referralDrawer.form.reasonSummary = value
      this.$nextTick(() => applyInsertion(el, selStart, selEnd))
    },
    async submitCreateReferral() {
      const { form, errors } = this.referralDrawer
      errors.studentId = form.studentId.trim() ? '' : '学生 ID 必填'
      errors.reasonSummary = form.reasonSummary.trim().length >= 5 ? '' : '事由摘要不少于 5 字'
      if (errors.studentId || errors.reasonSummary) return
      this.actioning = true
      this.referralDrawer.errorMessage = ''
      try {
        await studentAffairsApi.createMentalReferral({
          studentId: form.studentId.trim(),
          level: (form.level || 'FOCUS').trim().toUpperCase(),
          channel: form.channel.trim(),
          reasonSummary: form.reasonSummary.trim()
        })
        this.referralDrawer.visible = false
        toast.success('已登记转介')
        await this.load()
      } catch (e) {
        this.referralDrawer.errorMessage = e.message || '登记转介失败'
      } finally {
        this.actioning = false
      }
    },
    askFollow(row) {
      this.actionDialog = { visible: true, kind: 'follow', row }
    },
    askClose(row) {
      this.actionDialog = { visible: true, kind: 'close', row }
    },
    async confirmActionDialog({ reason }) {
      const { kind, row } = this.actionDialog
      this.actionDialog.visible = false
      if (!row) return
      if (kind === 'close') {
        await this.runAction(() => studentAffairsApi.closeMentalReferral(row.referralId, reason))
      } else {
        await this.runAction(() => studentAffairsApi.followMentalReferral(row.referralId, reason))
      }
    },
    async runAction(fn) {
      this.actioning = true
      try {
        await fn()
        await this.load()
      } catch (e) {
        this.errorMessage = e.message || '操作失败'
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
.sa-toolbar select {
  min-width: 140px;
  border: 1px solid var(--border-base);
  border-radius: var(--radius-base);
  background: var(--bg-surface);
  padding: var(--space-2) var(--space-3);
}
.sa-hint {
  color: var(--text-tertiary);
}
.sa-table {
  width: 100%;
  border-collapse: collapse;
  margin-bottom: var(--space-4);
}
.sa-table th,
.sa-table td {
  border-bottom: 1px solid var(--border-light);
  padding: var(--space-3);
  text-align: left;
  vertical-align: top;
}
.sa-table small {
  display: block;
  color: var(--text-tertiary);
  margin-top: 2px;
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
.sa-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}
.sa-btn {
  height: 34px;
  padding: 0 var(--space-4);
  border-radius: var(--radius-base);
  border: 1px solid var(--border-base);
  background: var(--bg-card);
  color: var(--text-secondary);
  font-size: var(--font-size-base);
  cursor: pointer;
}
.sa-btn:hover {
  border-color: var(--border-dark);
}
.sa-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
@media (max-width: 960px) {
  .sa-grid--metrics {
    grid-template-columns: 1fr;
  }
}
</style>
