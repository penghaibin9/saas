<template>
  <AppPageShell
    title="谈话转介与回访"
    subtitle="转介 → 回访 → 关闭 的持续跟进工作台；聚焦待回访(已转介/回访中)记录，明细遮蔽、查看留痕。"
    role-name="心理老师 / 授权辅导员"
    data-scope-name="PSY_STUDENT 逐生授权范围"
    watermark-purpose="心理转介回访处理"
  >
    <template #actions>
      <AppPermissionButton code="studentAffairs.risk.psyDetail.view" :loading="actioning" @click="openCreateReferral">
        登记转介
      </AppPermissionButton>
    </template>

    <AppGlobalState
      :state="pageState"
      :description="errorMessage"
      loading-text="正在加载转介回访工作台..."
      @retry="load"
      @back="$router.push('/admin/student-affairs/dashboard')"
    >
      <div class="sa-grid sa-grid--metrics">
        <AppMetricCard v-for="card in metricCards" :key="card.key" :title="card.label" :value="card.value" :accent="card.accent" />
      </div>

      <AppSectionCard title="待回访转介（已转介 / 回访中）">
        <table class="sa-table">
          <thead>
            <tr>
              <th>学生</th>
              <th>关注等级</th>
              <th>状态</th>
              <th>事由摘要</th>
              <th>转介去向</th>
              <th>最近回访</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in openItems" :key="row.referralId">
              <td>
                <strong>{{ row.realName || '未命名学生' }}</strong>
                <small>{{ row.studentNo || row.studentId }}</small>
              </td>
              <td><AppStatusTag :type="levelKind(row.level)" :label="row.levelLabel || row.level" /></td>
              <td><AppStatusTag :type="statusKind(row.status)" :label="row.statusLabel || row.status" /></td>
              <td>{{ row.reasonSummary || '—' }}</td>
              <td>{{ row.channel || '—' }}</td>
              <td><AppDateDisplay :value="row.lastFollowTime" mode="datetime" empty-text="尚未回访" /></td>
              <td class="sa-actions">
                <AppPermissionButton code="studentAffairs.risk.psyDetail.view" size="sm" @click="askFollow(row)">
                  回访
                </AppPermissionButton>
                <AppPermissionButton code="studentAffairs.risk.psyDetail.view" size="sm" variant="secondary" @click="askClose(row)">
                  关闭
                </AppPermissionButton>
              </td>
            </tr>
            <tr v-if="!openItems.length">
              <td colspan="7" class="sa-empty">暂无待回访转介</td>
            </tr>
          </tbody>
        </table>
      </AppSectionCard>
    </AppGlobalState>

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

    <!-- 登记转介（关注等级固定为 FOCUS，与原逻辑一致，不在此处提供等级选择） -->
    <AppDrawer v-model:visible="referralDrawer.visible" title="登记转介">
      <div class="sa-form">
        <AppFormItem label="学生 ID" required :error="referralDrawer.errors.studentId">
          <AppTextInput v-model="referralDrawer.form.studentId" placeholder="请输入学生 ID" :disabled="actioning" />
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
  AppPermissionButton,
  AppQuickPhrases,
  AppSectionCard,
  AppStatusTag,
  AppTextarea,
  AppTextInput
} from '@/components/common'
import AppDrawer from '@/components/ui/AppDrawer.vue'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairsB.api'
import { toast } from '@/utils/toast'
import { insertAtCursor, applyInsertion } from '@/utils/insertAtCursor'

function freshReferralForm() {
  return { studentId: '', channel: '校内咨询', reasonSummary: '' }
}

export default {
  name: 'MentalReferralFollowView',
  components: {
    AppConfirmDialog,
    AppDateDisplay,
    AppDrawer,
    AppFormItem,
    AppGlobalState,
    AppInlineAlert,
    AppMetricCard,
    AppPageShell,
    AppPermissionButton,
    AppQuickPhrases,
    AppSectionCard,
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
      actionDialog: { visible: false, kind: '', row: null },
      referralDrawer: { visible: false, form: freshReferralForm(), errors: {}, errorMessage: '' }
    }
  },
  computed: {
    pageState() {
      if (this.loading) return 'loading'
      if (this.errorMessage) return 'error'
      return 'ready'
    },
    openItems() {
      return this.items.filter((r) => r.status === 'REFERRED' || r.status === 'FOLLOWING')
    },
    metricCards() {
      const referred = this.items.filter((r) => r.status === 'REFERRED').length
      const following = this.items.filter((r) => r.status === 'FOLLOWING').length
      const neverFollowed = this.openItems.filter((r) => !r.lastFollowTime).length
      return [
        { key: 'open', label: '待回访', value: this.openItems.length, accent: this.openItems.length ? 'warning' : 'success' },
        { key: 'referred', label: '已转介待跟进', value: referred, accent: 'info' },
        { key: 'following', label: '回访中', value: following, accent: 'primary' },
        { key: 'never', label: '尚未回访', value: neverFollowed, accent: neverFollowed ? 'risk' : 'success' }
      ]
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
        // 注：/mental/list 接口本身支持 page/pageSize 真分页，但本页在拉取后按状态
        // (REFERRED/FOLLOWING) 二次过滤为"待回访"工作队列展示，顶部统计卡也基于同一份
        // 数据聚合；若改接 AppPagination，只能对拉取到的这一页做统计和过滤，会让分页
        // 页码与统计卡数字互相对不上，因此保留原有"一次性拉取前 100 条再过滤"的方式，
        // 不接入分页控件。
        const res = await studentAffairsApi.listMentalAttention({ page: 1, pageSize: 100 })
        this.items = res.data.items || []
      } catch (e) {
        this.errorMessage = e.message || '转介回访工作台加载失败'
      } finally {
        this.loading = false
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
          level: 'FOCUS',
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
.sa-table {
  width: 100%;
  border-collapse: collapse;
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
