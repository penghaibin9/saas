<template>
  <AppPageShell
    title="风险详情"
    subtitle="查看单条风险记录的学生、来源、脱敏状态和处置闭环动作。"
    role-name="SCHOOL_ADMIN / COUNSELOR"
    data-scope-name="学工数据范围"
    watermark-purpose="学工风险详情查看"
  >
    <template #actions>
      <AppPermissionButton :allowed="canBtn('studentAffairs.risk.back')" code="studentAffairs.risk.back" variant="secondary" @click="$router.push('/admin/student-affairs/risk')">
        返回列表
      </AppPermissionButton>
      <AppPermissionButton :allowed="canBtn('studentAffairs.risk.refresh')" code="studentAffairs.risk.refresh" variant="secondary" @click="load">
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
            <AppPermissionButton :allowed="canBtn('studentAffairs.risk.assign')" code="studentAffairs.risk.assign" variant="secondary" :loading="actioning" @click="assign">
              分派
            </AppPermissionButton>
            <AppPermissionButton :allowed="canBtn('studentAffairs.risk.process')" code="studentAffairs.risk.process" :loading="actioning" @click="process">
              处置
            </AppPermissionButton>
            <AppPermissionButton :allowed="canBtn('studentAffairs.risk.follow')" code="studentAffairs.risk.follow" variant="secondary" :loading="actioning" @click="follow">
              持续跟进
            </AppPermissionButton>
            <AppPermissionButton :allowed="canBtn('studentAffairs.risk.transfer')" code="studentAffairs.risk.transfer" variant="secondary" :loading="actioning" @click="transfer">
              转办
            </AppPermissionButton>
            <AppPermissionButton :allowed="canBtn('studentAffairs.risk.escalate')" code="studentAffairs.risk.escalate" variant="secondary" :loading="actioning" @click="escalate">
              升级
            </AppPermissionButton>
            <AppPermissionButton :allowed="canBtn('studentAffairs.risk.takeover')" code="studentAffairs.risk.takeover" variant="secondary" :loading="actioning" @click="takeover">
              接管
            </AppPermissionButton>
            <AppPermissionButton :allowed="canBtn('studentAffairs.risk.close')" code="studentAffairs.risk.close" variant="secondary" :loading="actioning" @click="close">
              关闭
            </AppPermissionButton>
            <AppPermissionButton :allowed="canBtn('studentAffairs.risk.reopen')" code="studentAffairs.risk.reopen" variant="secondary" :loading="actioning" @click="reopen">
              重开
            </AppPermissionButton>
          </div>
          <AppAuditTrail class="sa-audit" :records="auditRecords" compact :show-ip="false" />
        </AppSectionCard>
      </div>
    </AppGlobalState>

    <!-- 分派 / 转办：责任人从后端候选集里选（只含持学工风险处置角色的在职账号），不再手打内部 ID -->
    <AppConfirmDialog
      v-model:visible="ownerDlg.visible" :title="ownerDlg.title" type="primary"
      :confirm-text="ownerDlg.confirmText" :require-reason="ownerDlg.requireReason"
      :reason-min-length="1" :reason-label="ownerDlg.reasonLabel"
      :submitting="actioning" @confirm="submitOwnerDlg"
    >
      <AppFormItem label="责任人" required>
        <AppRiskOwnerPicker
          v-model="ownerDlg.ownerId"
          placeholder="按姓名 / 工号搜索"
          data-scope-hint="仅可选持学工风险处置角色的在职账号"
        />
      </AppFormItem>
    </AppConfirmDialog>

    <!-- 处置/跟进/升级/接管/关闭/重开：统一走必填说明弹窗（原生 prompt 无法多行、样式不可控） -->
    <AppConfirmDialog
      v-model:visible="textDlg.visible" :title="textDlg.title" :type="textDlg.type"
      :confirm-text="textDlg.confirmText" require-reason
      :reason-min-length="textDlg.minLength" :reason-label="textDlg.reasonLabel"
      :phrase-scene-key="textDlg.sceneKey" :submitting="actioning" @confirm="submitTextDlg"
    />
  </AppPageShell>
</template>

<script>
import {
  AppAuditTrail,
  AppConfirmDialog,
  AppDescriptionList,
  AppFormItem,
  AppGlobalState,
  AppPageShell,
  AppPermissionButton,
  AppRiskTag,
  AppSectionCard,
  AppSensitiveText,
  AppRiskOwnerPicker
} from '@/components/common'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairsB.api'
import { canCode } from '@/modules/studentAffairs/composables/permission'


export default {
  name: 'StudentAffairsRiskDetailView',
  props: { ctx: { type: Object, default: null } },
  components: {
    AppAuditTrail,
    AppConfirmDialog,
    AppDescriptionList,
    AppFormItem,
    AppGlobalState,
    AppPageShell,
    AppPermissionButton,
    AppRiskTag,
    AppSectionCard,
    AppSensitiveText,
    AppRiskOwnerPicker
  },
  data() {
    return {
      loading: true,
      actioning: false,
      errorMessage: '',
      detail: {},
      ownerDlg: { visible: false, title: '', confirmText: '确认', reasonLabel: '', requireReason: false, ownerId: '', kind: '' },
      textDlg: { visible: false, title: '', type: 'primary', confirmText: '确认', reasonLabel: '', sceneKey: '', minLength: 5, kind: '' }
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
        { label: '责任人', value: this.ownerLabel(x) },
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
        const res = await studentAffairsApi.getRiskRecord(this.riskId)
        this.detail = res.data || {}
      } catch (e) {
        this.errorMessage = e.message || '风险详情加载失败'
      } finally {
        this.loading = false
      }
    },
    /* ── 分派 / 转办：责任人走候选集选择器 ── */
    assign() {
      this.ownerDlg = { visible: true, kind: 'assign', title: '分派责任人', confirmText: '确认分派',
        requireReason: false, reasonLabel: '', ownerId: this.detail.ownerId || '' }
    },
    transfer() {
      this.ownerDlg = { visible: true, kind: 'transfer', title: '转办给其他责任人', confirmText: '确认转办',
        requireReason: true, reasonLabel: '转办原因', ownerId: '' }
    },
    async submitOwnerDlg({ reason } = {}) {
      const d = this.ownerDlg
      if (!d.ownerId) { this.errorMessage = '请选择责任人'; return }
      const ver = this.detail.version
      const ok = await this.runAction(() => (d.kind === 'assign'
        ? studentAffairsApi.assignRisk(this.riskId, d.ownerId, ver)
        : studentAffairsApi.transferRisk(this.riskId, d.ownerId, reason || '', ver)))
      if (ok) d.visible = false
    },
    /* ── 处置类：统一走必填说明弹窗；sceneKey 均已核对与本动作语义一致 ── */
    process() { this._openText('process', '记录处置', '确认处置', '处置内容', 'sa.risk.handle') },
    follow() { this._openText('follow', '转入持续跟进', '确认跟进', '跟进说明', 'sa.risk.followup') },
    escalate() { this._openText('escalate', '升级风险', '确认升级', '升级原因', 'sa.risk.escalate', 'warning') },
    // 接管无对应词条（sa.risk.takeover 不存在），不挂 chips
    takeover() { this._openText('takeover', '上级接管', '确认接管', '接管说明', '') },
    close() { this._openText('close', '关闭风险', '确认关闭', '关闭结论（≥5字）', 'sa.risk.close', 'danger') },
    reopen() { this._openText('reopen', '重开风险', '确认重开', '重开原因', 'sa.risk.reopen', 'warning') },
    _openText(kind, title, confirmText, reasonLabel, sceneKey, type = 'primary') {
      this.textDlg = { visible: true, kind, title, type, confirmText, reasonLabel, sceneKey, minLength: 5 }
    },
    async submitTextDlg({ reason }) {
      const ver = this.detail.version
      const fnMap = {
        process: (t) => studentAffairsApi.processRisk(this.riskId, t, ver),
        follow: (t) => studentAffairsApi.followRisk(this.riskId, t, ver),
        escalate: (t) => studentAffairsApi.escalateRisk(this.riskId, t, ver),
        takeover: (t) => studentAffairsApi.takeoverRisk(this.riskId, t, ver),
        close: (t) => studentAffairsApi.closeRisk(this.riskId, t, ver),
        reopen: (t) => studentAffairsApi.reopenRisk(this.riskId, t, ver)
      }
      const fn = fnMap[this.textDlg.kind]
      if (!fn) return
      const ok = await this.runAction(() => fn(reason))
      if (ok) this.textDlg.visible = false
    },
    /** @returns {boolean} 是否成功。调用方据此决定关不关弹窗——失败时保留用户已填内容，不让人重打一遍。 */
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
    ownerLabel(x) {
      if (!x.ownerId) return '待分派'
      if (x.ownerName) {
        return x.ownerLoginName ? `${x.ownerName} / ${x.ownerLoginName}` : x.ownerName
      }
      return '责任人账号异常'
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
@media (max-width: 960px) {
  .sa-detail-layout {
    grid-template-columns: 1fr;
  }
}
</style>
