<template>
  <AppPageShell
    title="风险详情"
    subtitle="查看单条风险记录的学生、来源、脱敏状态和处置闭环动作。"
    role-name="SCHOOL_ADMIN / COUNSELOR"
    data-scope-name="学工数据范围"
    watermark-purpose="学工风险详情查看"
  >
    <template #actions>
      <AppPermissionButton code="studentAffairs.risk.back" variant="secondary" @click="$router.push('/admin/student-affairs/risk')">
        返回列表
      </AppPermissionButton>
      <AppPermissionButton code="studentAffairs.risk.refresh" variant="secondary" @click="load">
        刷新
      </AppPermissionButton>
    </template>

    <AppGlobalState
      :state="pageState"
      :description="errorMessage"
      loading-text="正在加载风险详情..."
      @retry="load"
      @back="$router.push('/admin/student-affairs/risk')"
    >
      <div class="sa-detail-layout">
        <AppSectionCard title="风险档案">
          <div class="sa-heading">
            <div>
              <h2>{{ detail.title || '风险记录' }}</h2>
              <p>{{ detail.realName || '未命名学生' }} · {{ detail.studentNo || detail.studentId }}</p>
            </div>
            <AppRiskTag :level="detail.riskLevel" />
          </div>

          <AppDescriptionList :items="detailItems" :columns="2" bordered>
            <template #detail>
              <span v-if="detail.mentalMasked" class="sa-masked">心理关注明细已按角色脱敏</span>
              <AppSensitiveText v-else :value="detail.detail" />
            </template>
          </AppDescriptionList>
        </AppSectionCard>

        <AppSectionCard title="处置动作">
          <div class="sa-actions">
            <AppPermissionButton code="studentAffairs.risk.assign" variant="secondary" :loading="actioning" @click="assign">
              分派
            </AppPermissionButton>
            <AppPermissionButton code="studentAffairs.risk.process" :loading="actioning" @click="process">
              处置
            </AppPermissionButton>
            <AppPermissionButton code="studentAffairs.risk.follow" variant="secondary" :loading="actioning" @click="follow">
              持续跟进
            </AppPermissionButton>
            <AppPermissionButton code="studentAffairs.risk.transfer" variant="secondary" :loading="actioning" @click="transfer">
              转办
            </AppPermissionButton>
            <AppPermissionButton code="studentAffairs.risk.escalate" variant="secondary" :loading="actioning" @click="escalate">
              升级
            </AppPermissionButton>
            <AppPermissionButton code="studentAffairs.risk.takeover" variant="secondary" :loading="actioning" @click="takeover">
              接管
            </AppPermissionButton>
            <AppPermissionButton code="studentAffairs.risk.close" variant="secondary" :loading="actioning" @click="close">
              关闭
            </AppPermissionButton>
            <AppPermissionButton code="studentAffairs.risk.reopen" variant="secondary" :loading="actioning" @click="reopen">
              重开
            </AppPermissionButton>
          </div>
          <AppAuditTrail class="sa-audit" :records="auditRecords" compact :show-ip="false" />
        </AppSectionCard>
      </div>
    </AppGlobalState>

    <!-- 分派/处置/跟进/升级/接管/关闭/重开 —— 统一走带原因校验的二次确认弹窗 -->
    <AppConfirmDialog
      v-model:visible="dialog.visible"
      :title="dialog.title"
      :message="dialog.message"
      :type="dialog.type"
      :confirm-text="dialog.confirmText"
      require-reason
      :reason-label="dialog.reasonLabel"
      :reason-placeholder="dialog.reasonPlaceholder"
      :reason-min-length="dialog.reasonMinLength"
      :phrase-scene-key="dialogPhraseSceneKey"
      :submitting="actioning"
      @confirm="onDialogConfirm"
    />

    <!-- 转办：换责任人（必填）+ 转办原因（选填），两个字段用抽屉承载 -->
    <AppDrawer v-model:visible="transferDrawer.visible" title="转办风险">
      <div class="sa-form">
        <AppFormItem label="新责任人 ID" required :error="transferDrawer.errors.newOwnerId">
          <AppTextInput v-model="transferDrawer.form.newOwnerId" placeholder="请输入新责任人 ID" :disabled="actioning" />
        </AppFormItem>
        <AppFormItem label="转办原因">
          <AppQuickPhrases scene-key="sa.risk.transfer" @pick="onPickTransferReason" />
          <AppTextarea ref="transferReasonTa" v-model="transferDrawer.form.reason" :rows="3" placeholder="如：职责调整，转交处理" :disabled="actioning" />
        </AppFormItem>
        <AppInlineAlert v-if="transferDrawer.errorMessage" type="danger" :description="transferDrawer.errorMessage" />
      </div>
      <template #footer>
        <button type="button" class="sa-btn" :disabled="actioning" @click="transferDrawer.visible = false">取消</button>
        <AppPermissionButton code="studentAffairs.risk.transfer" :loading="actioning" @click="submitTransfer">
          确认转办
        </AppPermissionButton>
      </template>
    </AppDrawer>
  </AppPageShell>
</template>

<script>
import {
  AppAuditTrail,
  AppConfirmDialog,
  AppDescriptionList,
  AppFormItem,
  AppGlobalState,
  AppInlineAlert,
  AppPageShell,
  AppPermissionButton,
  AppQuickPhrases,
  AppRiskTag,
  AppSectionCard,
  AppSensitiveText,
  AppTextarea,
  AppTextInput
} from '@/components/common'
import AppDrawer from '@/components/ui/AppDrawer.vue'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairsB.api'
import { insertAtCursor, applyInsertion } from '@/utils/insertAtCursor'

export default {
  name: 'StudentAffairsRiskDetailView',
  components: {
    AppAuditTrail,
    AppConfirmDialog,
    AppDescriptionList,
    AppDrawer,
    AppFormItem,
    AppGlobalState,
    AppInlineAlert,
    AppPageShell,
    AppPermissionButton,
    AppQuickPhrases,
    AppRiskTag,
    AppSectionCard,
    AppSensitiveText,
    AppTextarea,
    AppTextInput
  },
  data() {
    return {
      loading: true,
      actioning: false,
      errorMessage: '',
      detail: {},
      // 分派/处置/跟进/升级/接管/关闭/重开 共用同一个确认弹窗，按 action 分发到对应接口。
      dialog: {
        visible: false, action: '', title: '', message: '', type: 'primary', confirmText: '确认',
        reasonLabel: '原因', reasonPlaceholder: '', reasonMinLength: 1
      },
      transferDrawer: { visible: false, form: { newOwnerId: '', reason: '' }, errors: {}, errorMessage: '' }
    }
  },
  computed: {
    riskId() {
      return this.$route.params.riskId
    },
    pageState() {
      if (this.loading) return 'loading'
      if (this.errorMessage) return 'error'
      return 'ready'
    },
    detailItems() {
      const x = this.detail
      return [
        { label: '学生', value: `${x.realName || ''} ${x.studentNo || ''}`.trim() },
        { label: '来源', value: this.sourceLabel(x.source) },
        { label: '来源编号', value: x.sourceRefId },
        { label: '风险等级', value: x.riskLevel },
        { label: '状态', value: x.statusLabel || x.status },
        { label: '责任人', value: x.ownerId || '待分派' },
        { key: 'detail', label: '风险明细', value: x.detail, span: 2 },
        { label: '归档状态', value: x.isArchived ? '已归档' : '未归档' },
        { label: '版本', value: x.version }
      ]
    },
    auditRecords() {
      return [
        {
          id: 'risk-current',
          action: '当前风险状态',
          actor: '学工中心',
          target: this.detail.statusLabel || this.detail.status,
          reason: '详情由后端风险接口返回，心理来源明细按角色脱敏',
          result: '成功'
        }
      ]
    },
    // 共用弹窗按 dialog.action 切换快捷用语场景；接管（takeover）与分派（assign）词库无对应词条，返回空字符串使 AppQuickPhrases 不渲染。
    dialogPhraseSceneKey() {
      return ({
        process: 'sa.risk.handle',
        follow: 'sa.risk.followup',
        escalate: 'sa.risk.escalate',
        close: 'sa.risk.close',
        reopen: 'sa.risk.reopen'
      })[this.dialog.action] || ''
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
        const res = await studentAffairsApi.getRiskRecord(this.riskId)
        this.detail = res.data || {}
      } catch (e) {
        this.errorMessage = e.message || '风险详情加载失败'
      } finally {
        this.loading = false
      }
    },
    openDialog(action, opts) {
      this.dialog = {
        visible: true, action,
        type: 'primary', confirmText: '确认',
        reasonLabel: '原因', reasonPlaceholder: '', reasonMinLength: 1,
        ...opts
      }
    },
    assign() {
      this.openDialog('assign', {
        title: '分派责任人',
        message: '将该风险指派给指定责任人跟进处置。',
        confirmText: '确认分派',
        reasonLabel: '责任人 ID',
        reasonPlaceholder: this.detail.ownerId ? `当前责任人：${this.detail.ownerId}，请输入新的责任人 ID` : '请输入责任人 ID'
      })
    },
    process() {
      this.openDialog('process', {
        title: '处置风险',
        message: '记录本次处置过程，处置后进入处置中状态。',
        confirmText: '确认处置',
        reasonLabel: '处置内容',
        reasonPlaceholder: '如：已联系学生并记录处置过程'
      })
    },
    follow() {
      this.openDialog('follow', {
        title: '转入持续跟进',
        message: '转入持续跟进状态，并记录跟进说明。',
        confirmText: '确认跟进',
        reasonLabel: '跟进说明',
        reasonPlaceholder: '如：转入持续跟进'
      })
    },
    transfer() {
      this.transferDrawer = { visible: true, form: { newOwnerId: '', reason: '' }, errors: {}, errorMessage: '' }
    },
    onPickTransferReason(text) {
      const el = this.$refs.transferReasonTa?.$refs?.el
      const { value, selStart, selEnd } = insertAtCursor(el, this.transferDrawer.form.reason, text)
      this.transferDrawer.form.reason = value
      this.$nextTick(() => applyInsertion(el, selStart, selEnd))
    },
    async submitTransfer() {
      const { form, errors } = this.transferDrawer
      errors.newOwnerId = form.newOwnerId.trim() ? '' : '请输入新责任人 ID'
      if (errors.newOwnerId) return
      this.actioning = true
      this.transferDrawer.errorMessage = ''
      try {
        await studentAffairsApi.transferRisk(this.riskId, form.newOwnerId.trim(), form.reason.trim())
        this.transferDrawer.visible = false
        await this.load()
      } catch (e) {
        this.transferDrawer.errorMessage = e.message || '转办失败'
      } finally {
        this.actioning = false
      }
    },
    escalate() {
      this.openDialog('escalate', {
        title: '升级风险',
        type: 'warning',
        message: '升级后风险等级上调，提请上级关注处置。',
        confirmText: '确认升级',
        reasonLabel: '升级原因',
        reasonPlaceholder: '如：风险等级提升，需要上级关注'
      })
    },
    takeover() {
      this.openDialog('takeover', {
        title: '接管风险',
        message: '由你直接接管本条风险的后续处置。',
        confirmText: '确认接管',
        reasonLabel: '接管说明',
        reasonPlaceholder: '如：上级接管处置'
      })
    },
    close() {
      this.openDialog('close', {
        title: '关闭风险',
        type: 'warning',
        message: '关闭前请填写关闭结论，关闭后写入学生 360 时间线。',
        confirmText: '确认关闭',
        reasonLabel: '关闭结论',
        reasonPlaceholder: '如：学生情况稳定，风险解除'
      })
    },
    reopen() {
      this.openDialog('reopen', {
        title: '重开风险',
        type: 'warning',
        message: '重开后风险恢复为跟进中状态。',
        confirmText: '确认重开',
        reasonLabel: '重开原因',
        reasonPlaceholder: '如：风险复发，需要重新跟进'
      })
    },
    async onDialogConfirm(payload) {
      const reason = (payload && payload.reason) || ''
      const call = {
        assign: () => studentAffairsApi.assignRisk(this.riskId, reason),
        process: () => studentAffairsApi.processRisk(this.riskId, reason),
        follow: () => studentAffairsApi.followRisk(this.riskId, reason),
        escalate: () => studentAffairsApi.escalateRisk(this.riskId, reason),
        takeover: () => studentAffairsApi.takeoverRisk(this.riskId, reason),
        close: () => studentAffairsApi.closeRisk(this.riskId, reason),
        reopen: () => studentAffairsApi.reopenRisk(this.riskId, reason)
      }[this.dialog.action]
      if (!call) return
      await this.runAction(call)
      this.dialog.visible = false
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
    sourceLabel(source) {
      return ({
        ACADEMIC_WARNING: '学业预警',
        LEAVE_OVERDUE: '请假异常',
        DORM: '宿舍异常',
        MENTAL: '心理关注',
        MANUAL: '人工建单'
      })[source] || source || '未设置'
    }
  }
}
</script>

<style scoped>
.sa-detail-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.4fr) minmax(320px, 0.8fr);
  gap: var(--space-4);
}
.sa-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-4);
  margin-bottom: var(--space-4);
}
.sa-heading h2 {
  margin: 0 0 var(--space-1);
  font-size: var(--font-size-xl);
  letter-spacing: 0;
}
.sa-heading p {
  margin: 0;
  color: var(--text-tertiary);
}
.sa-actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}
.sa-audit {
  margin-top: var(--space-4);
}
.sa-masked {
  color: var(--text-tertiary);
}
.sa-form { display: flex; flex-direction: column; gap: var(--space-4); }
.sa-btn { height: 34px; padding: 0 var(--space-4); border-radius: var(--radius-base); border: 1px solid var(--border-base); background: var(--bg-card); color: var(--text-secondary); font-size: var(--font-size-base); cursor: pointer; }
.sa-btn:hover { border-color: var(--border-dark); }
.sa-btn:disabled { opacity: 0.6; cursor: not-allowed; }
@media (max-width: 960px) {
  .sa-detail-layout {
    grid-template-columns: 1fr;
  }
}
</style>
